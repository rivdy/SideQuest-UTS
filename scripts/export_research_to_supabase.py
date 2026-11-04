"""Export only one organization's research records to reviewable Supabase SQL.

No network calls; SQLite is opened read-only. Accounts and sessions are never read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    "formulation": {
        "name",
        "aroma_profile",
        "ingredients",
        "notes",
        "data_origin",
        "composition_hash",
        "assessment",
        "assessed_at",
    },
    "experiment": {
        "formulation_id",
        "batch_id",
        "protocol",
        "source_ref",
        "measured_on",
        "initial_h2o2",
        "final_h2o2",
        "ph",
        "temperature_c",
        "duration_days",
        "homogeneous",
        "aroma_intensity",
        "notes",
        "data_origin",
        "confirmed_actual",
        "formulation_name",
        "composition_hash",
        "composition_features",
        "retention_pct",
    },
    "model_run": {
        "algorithm",
        "artifact_key",
        "artifact_sha256",
        "dataset_sha256",
        "duration_seconds",
        "excluded",
        "features",
        "group_overlap",
        "grouping",
        "library_version",
        "metrics",
        "origin",
        "points",
        "protocol",
        "provenance",
        "rows",
        "scope",
        "seed",
        "status",
        "target",
        "test_groups",
        "test_rows",
        "train_groups",
        "train_rows",
        "unit",
        "warning",
    },
}
FORBIDDEN = {
    "password",
    "password_hash",
    "access_token",
    "refresh_token",
    "token_hash",
    "csrf",
    "secret_key",
    "service_role",
}


def cloud_id(org: str, kind: str, local_id: str) -> str:
    return str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"baylab-sqlite-v1:{org}:{kind}:{local_id}")
    )


def sql_string(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Teks mengandung NUL yang tidak didukung PostgreSQL.")
    return "'" + value.replace("'", "''") + "'"


def check_payload(value: object) -> None:
    if isinstance(value, dict):
        if any(str(k).lower() in FORBIDDEN for k in value):
            raise ValueError(
                "Payload riset memuat field kredensial; ekspor dibatalkan."
            )
        for child in value.values():
            check_payload(child)
    elif isinstance(value, list):
        for child in value:
            check_payload(child)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Payload memuat angka tidak finite.")
    elif isinstance(value, str) and "\x00" in value:
        raise ValueError("Payload mengandung NUL.")


def load_records(db_path: Path, organization: str) -> list[dict]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,39}", organization):
        raise ValueError("Kode organisasi tidak valid.")
    # mode=ro also prevents accidentally creating an empty database at a wrong path.
    with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        exists = db.execute(
            "select 1 from organizations where id=?", (organization,)
        ).fetchone()
        if not exists:
            raise ValueError("Organisasi sumber tidak ditemukan.")
        rows = db.execute(
            "select id, kind, data, created, archived from workspace_records "
            "where org_id=? order by created, id",
            (organization,),
        ).fetchall()
    result = []
    mapping = {r["id"]: cloud_id(organization, r["kind"], r["id"]) for r in rows}
    formulas = {r["id"] for r in rows if r["kind"] == "formulation"}
    for row in rows:
        kind = row["kind"]
        if kind not in FIELDS:
            raise ValueError("Jenis record belum didukung; ekspor dibatalkan: " + kind)
        data = json.loads(row["data"])
        if not isinstance(data, dict) or set(data) - FIELDS[kind]:
            raise ValueError(
                "Skema record berbeda dari skema ekspor yang ditinjau: " + kind
            )
        check_payload(data)
        if kind == "experiment":
            reference = data.get("formulation_id")
            if reference not in formulas:
                raise ValueError(
                    "Eksperimen merujuk formulasi yang tidak ada dalam organisasi sumber."
                )
            data["formulation_id"] = mapping[reference]
        created = datetime.fromtimestamp(float(row["created"]), UTC).isoformat()
        if row["archived"] not in (0, 1):
            raise ValueError("Status arsip tidak valid.")
        result.append(
            {
                "id": mapping[row["id"]],
                "kind": kind,
                "data": data,
                "created_at": created,
                "archived": bool(row["archived"]),
            }
        )
    return result


def render_sql(records: list[dict], organization: str, owner_email: str) -> str:
    if (
        not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", owner_email)
        or len(owner_email) > 180
    ):
        raise ValueError("Email admin tujuan tidak valid.")
    org, email = sql_string(organization), sql_string(owner_email.lower())
    lines = [
        "-- BAYLab research export. Run as administrator in Supabase SQL Editor.",
        "-- No accounts, passwords, login sessions, document text or model binaries included.",
        "-- Imports are attributed to the destination admin; original local authors are not migrated.",
        "-- Re-running identical data is safe. Conflicting existing data aborts the transaction.",
        "begin;",
        "set local standard_conforming_strings = on;",
        "create temporary table baylab_import_stage (",
        "  id uuid primary key, kind text, data jsonb, created_at timestamptz, archived boolean",
        ") on commit drop;",
    ]
    for record in records:
        payload = json.dumps(
            record["data"], ensure_ascii=True, allow_nan=False, separators=(",", ":")
        )
        lines.append(
            "insert into baylab_import_stage values ("
            + sql_string(record["id"])
            + "::uuid,"
            + sql_string(record["kind"])
            + ","
            + sql_string(payload)
            + "::jsonb,"
            + sql_string(record["created_at"])
            + "::timestamptz,"
            + str(record["archived"]).lower()
            + ");"
        )
    lines.append(f"""
do $baylab_import$
declare actor uuid;
begin
  select u.id into strict actor
    from auth.users u join public.baylab_memberships m on m.user_id=u.id
    where lower(u.email)={email} and m.organization_slug={org}
      and m.active and m.role='admin' and u.confirmed_at is not null;
  if exists (
    select 1 from baylab_import_stage s join public.baylab_records r on r.id=s.id
    where r.organization_slug is distinct from {org}
      or r.kind is distinct from s.kind or r.data is distinct from s.data
      or r.created_at is distinct from s.created_at or r.archived is distinct from s.archived
  ) then
    raise exception 'Konflik record impor: data tujuan berbeda. Tidak ada data yang ditimpa.';
  end if;
  insert into public.baylab_records
    (id, organization_slug, kind, data, created_by, created_at, archived)
  select id, {org}, kind, data, actor, created_at, archived from baylab_import_stage
  on conflict (id) do nothing;
  if exists (
    select 1 from baylab_import_stage s left join public.baylab_records r on r.id=s.id
    where r.id is null or r.organization_slug is distinct from {org}
      or r.kind is distinct from s.kind or r.data is distinct from s.data
      or r.created_at is distinct from s.created_at or r.archived is distinct from s.archived
  ) then
    raise exception 'Verifikasi impor gagal. Transaksi dibatalkan.';
  end if;
exception when no_data_found then
  raise exception 'Admin tujuan belum dikonfirmasi atau belum menjadi anggota admin aktif organisasi.';
end;
$baylab_import$;
select r.kind, count(*) as records_present
from public.baylab_records r join baylab_import_stage s on r.id=s.id
group by r.kind;
commit;
""")
    return "\n".join(lines)


def export(db_path: Path, organization: str, owner_email: str, output: Path) -> dict:
    records = load_records(db_path, organization)
    sql = render_sql(records, organization, owner_email)
    # Never overwrite an existing export or the original database.
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(sql)
    return {
        "organization": organization,
        "records": len(records),
        "by_kind": dict(Counter(r["kind"] for r in records)),
        "archived": sum(r["archived"] for r in records),
        "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
        "file": str(output.resolve()),
        "model_binaries_included": False,
        "rag_documents_included": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=ROOT / "backend/data/workspace.sqlite3"
    )
    parser.add_argument("--organization", default="lkpi")
    parser.add_argument("--owner-email", default="admin@baylab.local")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "backend/data/exports" / (
        "research-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + ".sql"
    )
    report = export(args.db, args.organization, args.owner_email, output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
