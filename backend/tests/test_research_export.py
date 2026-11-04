"""Exporter safety tests using disposable SQLite fixtures, never real cloud data."""

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "research_export",
    Path(__file__).resolve().parents[2] / "scripts/export_research_to_supabase.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture_db(tmp_path):
    path = tmp_path / "workspace.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""
        create table organizations(id text);
        insert into organizations values ('lkpi'), ('other');
        create table users(password_hash text);
        insert into users values ('ACCOUNT_SECRET_SENTINEL');
        create table login_sessions(token_hash text);
        insert into login_sessions values ('SESSION_SECRET_SENTINEL');
        create table workspace_records(id text, org_id text, kind text, data text,
          created real, archived int);
        """)
        rows = [
            (
                "form1",
                "lkpi",
                "formulation",
                {"name": "O'Brien $baylab_import$ \\ lemon", "data_origin": "synthetic"},
                0,
            ),
            (
                "exp1",
                "lkpi",
                "experiment",
                {"formulation_id": "form1", "data_origin": "synthetic"},
                1,
            ),
            ("other1", "other", "formulation", {"name": "OTHER_ORG_SENTINEL"}, 0),
        ]
        db.executemany(
            "insert into workspace_records values (?,?,?,?,?,?)",
            [
                (rid, org, kind, json.dumps(data), 1700000000.25, archived)
                for rid, org, kind, data, archived in rows
            ],
        )
    return path


def test_export_scope_relationships_and_archive(tmp_path):
    source = fixture_db(tmp_path)
    before = source.read_bytes()
    records = module.load_records(source, "lkpi")
    form = next(r for r in records if r["kind"] == "formulation")
    trial = next(r for r in records if r["kind"] == "experiment")
    assert trial["data"]["formulation_id"] == form["id"]
    assert trial["archived"] is True
    assert form["data"]["data_origin"] == "synthetic"
    sql = module.render_sql(records, "lkpi", "admin@example.test")
    assert "O''Brien" in sql
    for sentinel in ("ACCOUNT_SECRET_SENTINEL", "SESSION_SECRET_SENTINEL", "OTHER_ORG_SENTINEL"):
        assert sentinel not in sql
    assert source.read_bytes() == before


def test_repeat_is_deterministic_and_file_not_overwritten(tmp_path):
    source = fixture_db(tmp_path)
    records = module.load_records(source, "lkpi")
    assert records == module.load_records(source, "lkpi")
    assert module.cloud_id("lkpi", "formulation", "same") != module.cloud_id(
        "other", "formulation", "same"
    )
    output = tmp_path / "export.sql"
    report = module.export(source, "lkpi", "admin@example.test", output)
    assert report["records"] == 2
    assert "on conflict (id) do nothing" in output.read_text()
    with pytest.raises(FileExistsError):
        module.export(source, "lkpi", "admin@example.test", output)


def test_missing_formula_aborts(tmp_path):
    source = fixture_db(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute("delete from workspace_records where id='form1'")
    with pytest.raises(ValueError, match="formulasi"):
        module.load_records(source, "lkpi")


def test_unexpected_secret_field_aborts(tmp_path):
    source = fixture_db(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute(
            "update workspace_records set data=? where id='form1'",
            (json.dumps({"assessment": {"password_hash": "SECRET"}}),),
        )
    with pytest.raises(ValueError, match="kredensial"):
        module.load_records(source, "lkpi")


def test_bad_org_and_nonfinite_data_aborts(tmp_path):
    source = fixture_db(tmp_path)
    with pytest.raises(ValueError, match="organisasi"):
        module.load_records(source, "lkpi';drop table users;--")
    with sqlite3.connect(source) as db:
        db.execute("update workspace_records set data=? where id='form1'", ('{"assessed_at":NaN}',))
    with pytest.raises(ValueError, match="finite"):
        module.load_records(source, "lkpi")
