"""Fill the LOCAL workspace with a labelled demo scenario through the running backend API.

Run from the project root while FastAPI is running on port 8000:
    .venv\\Scripts\\python.exe scripts\\seed_demo.py

Everything created here is marked as illustrative example data ("synthetic"), so it is shown
as "Data contoh ilustratif" and is never used to train a model. Running it again skips what
already exists. Credentials stay in backend/data (ignored by git).
"""

import json
import secrets
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend" / "data"
API = "http://127.0.0.1:8000"
ORG = "lkpi"
FORMULATOR = {"email": "formulator@baylab.local", "name": "Formulator LKPI (demo)"}
PROTOCOL = "DEMO-RUBRIK-1"
NOTE = "Data contoh ilustratif untuk demo alur; penilaian draf tim, belum divalidasi kimiawan."

BASE = [
    {"name": "Hidrogen peroksida 50% teknis", "role": "active", "percent": 6.0, "smiles": "OO"},
    {"name": "Alcohol ethoxylate C12-14 7EO", "role": "solubilizer", "percent": 2.0},
    {"name": "HEDP ~60%", "role": "stabilizer", "percent": 0.17},
    {"name": "Asam sitrat", "role": "other", "percent": 0.2},
    {"name": "Trisodium sitrat", "role": "other", "percent": 0.1},
]
AROMA = {
    "Dihydromyrcenol": "CC(CCCC(C)(C)O)C=C",
    "Dimetol": "CC(C)CCCC(C)(C)O",
    "Styrallyl acetate": "CC(C1=CC=CC=C1)OC(=O)C",
    "Tricyclodecenyl propionate": "CCC(=O)OC1CC2CC1C3C2C=CC3",
    "Ethylene brassylate": "C1CCCCCC(=O)OCCOC(=O)CCCCC1",
    "d-Limonene": "CC1=CC[C@@H](CC1)C(=C)C",
    "Citral": "CC(=CCC/C(=C/C=O)/C)C",
}


def formula(name: str, profile: str, aroma: dict[str, float], notes: str) -> dict:
    water = round(100 - sum(i["percent"] for i in BASE) - sum(aroma.values()), 4)
    ingredients = [dict(i) for i in BASE]
    ingredients += [
        {"name": k, "role": "fragrance", "percent": v, "smiles": AROMA[k]} for k, v in aroma.items()
    ]
    ingredients.append({"name": "Air demineralisasi", "role": "water", "percent": water})
    return {
        "name": name,
        "aroma_profile": profile,
        "ingredients": ingredients,
        "notes": notes + " " + NOTE,
        "data_origin": "synthetic",
    }


def crit(score: float, source: str, rationale: str) -> dict:
    return {"score": score, "source_ref": source, "rationale": rationale}


SCREEN = "Screening komposisi BAYLab (RDKit, pola draf)"
LIMONENE = "US 8765658: formula H2O2 + d-limonene retensi 0-40% (45 C, hari 30)"
ACID = "US 4238192: formula H2O2 asam beraroma retensi ~96-98% (23 C, 1 tahun)"
PH = "US 8802613: penstabil fosfonat lemah pada pH basa; formula dibuat asam"
LYSOL = "SmartLabel Lysol H2O2 Citrus: komponen aroma diungkap"

CANDIDATES = [
    (
        formula(
            "F-01 aroma tahan oksidasi (contoh)",
            "Citrus segar",
            {"Dihydromyrcenol": 0.16, "Dimetol": 0.08, "Styrallyl acetate": 0.06,
             "Tricyclodecenyl propionate": 0.06, "Ethylene brassylate": 0.04},
            "Formula usulan: 5 komponen aroma dari produk H2O2 komersial.",
        ),
        {
            "oxidation": crit(70, SCREEN, "2 dari 5 komponen aroma punya C=C; tidak ada aldehida atau fenol."),
            "solubility": crit(65, "Rasio surfaktan : aroma = 5 : 1", "Perlu dibuktikan jernih pada uji kejernihan."),
            "compatibility": crit(70, PH, "Tanpa NPE, ada kelat logam HEDP, pH asam 3,5-4,0."),
            "temperature": crit(60, ACID, "Belum ada data 54 C; acuan paten formula asam beraroma."),
            "aroma": crit(70, LYSOL, "Profil citrus-fresh; intensitas perlu panel."),
        },
    ),
    (
        formula(
            "F-02 aroma 0,2% (contoh)",
            "Citrus segar, lebih lembut",
            {"Dihydromyrcenol": 0.08, "Dimetol": 0.04, "Styrallyl acetate": 0.03,
             "Tricyclodecenyl propionate": 0.03, "Ethylene brassylate": 0.02},
            "Variasi F-01 dengan kadar aroma separuh (level rendah DoE B).",
        ),
        {
            "oxidation": crit(75, SCREEN, "Komponen sama dengan F-01, kadar aroma separuh."),
            "solubility": crit(75, "Rasio surfaktan : aroma = 10 : 1", "Lebih mudah larut daripada F-01."),
            "compatibility": crit(70, PH, "Basis sama dengan F-01."),
            "temperature": crit(65, ACID, "Beban aroma lebih rendah."),
            "aroma": crit(55, "Dataset DoE B: faktor kadar parfum 0,2-0,6%", "Penanda aroma bisa terlalu lemah; uji panel."),
        },
    ),
    (
        formula(
            "F-01 + limonene (pembanding, contoh)",
            "Citrus lebih tajam",
            {"Dihydromyrcenol": 0.12, "d-Limonene": 0.08, "Dimetol": 0.08,
             "Styrallyl acetate": 0.06, "Tricyclodecenyl propionate": 0.03,
             "Ethylene brassylate": 0.03},
            "Pembanding DoE B: sebagian aroma diganti d-limonene.",
        ),
        {
            "oxidation": crit(50, SCREEN, "Limonene menambah 2 ikatan C=C."),
            "solubility": crit(65, "Rasio surfaktan : aroma = 5 : 1", "Sama dengan F-01."),
            "compatibility": crit(65, PH, "Basis sama; limonene rentan oksidasi."),
            "temperature": crit(40, LIMONENE, "Formula paten dengan limonene kehilangan sebagian besar H2O2."),
            "aroma": crit(75, "Dataset file 02: aroma lemon populer di Indonesia", "Lebih mirip citrus pasar."),
        },
    ),
    (
        formula(
            "Lemon klasik: limonene + citral (pembanding, contoh)",
            "Lemon klasik",
            {"d-Limonene": 0.3, "Citral": 0.1},
            "Pembanding aroma populer Indonesia yang berisiko di basis H2O2.",
        ),
        {
            "oxidation": crit(25, SCREEN, "Semua komponen aroma punya C=C; citral juga aldehida."),
            "solubility": crit(60, "Rasio surfaktan : aroma = 5 : 1", "Terpen hidrofobik."),
            "compatibility": crit(55, "Dataset file 02: kecocokan basis H2O2 draf", "Aldehida citral reaktif terhadap oksidator."),
            "temperature": crit(35, LIMONENE, "Acuan paten formula limonene."),
            "aroma": crit(85, "Dataset file 02: profil lemon populer", "Paling mirip aroma lemon pasar."),
        },
    ),
]
EXPERIMENTS = {
    "F-01 aroma tahan oksidasi (contoh)": (3.0, 2.85, 3.8, True, 4.0),
    "Lemon klasik: limonene + citral (pembanding, contoh)": (3.0, 2.1, 3.5, False, 2.0),
}


def login(client: httpx.Client, email: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"organization": ORG, "email": email, "password": password})
    response.raise_for_status()
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]


def ensure_formulator() -> dict:
    path = DATA / "demo-formulator.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    admin = json.loads((DATA / "initial-admin-lkpi.json").read_text(encoding="utf-8"))
    password = secrets.token_urlsafe(14)
    with httpx.Client(base_url=API, trust_env=False) as client:
        login(client, admin["email"], admin["password"])
        response = client.post("/api/auth/users", json={"organization": ORG, "role": "formulator",
                                                         "password": password, **FORMULATOR})
        if response.status_code == 409:
            sys.exit("Akun formulator sudah ada tapi kata sandinya tidak tersimpan. Hapus akunnya "
                     "atau buat file backend/data/demo-formulator.json secara manual.")
        response.raise_for_status()
    creds = {"organization": ORG, "email": FORMULATOR["email"], "password": password}
    path.write_text(json.dumps(creds, indent=1), encoding="utf-8")
    return creds


def upload_documents(client: httpx.Client) -> list[str]:
    existing = {d["title"] for d in client.get("/api/rag/documents").json()}
    dataset = ROOT / "data" / "Dataset" / "BAYLab_dataset_final"
    docs = [
        ("Brief tantangan LKPI-01", "LKPI-01-USER-BRIEF", ROOT / "backend" / "data" / "sources" / "lkpi-01-brief.md"),
        ("Dataset BAYLab: bahan master", "BAYLab dataset file 01", dataset / "6_rag" / "dokumen" / "01_bahan_master.md"),
        ("Dataset BAYLab: aroma populer Indonesia", "BAYLab dataset file 02", dataset / "6_rag" / "dokumen" / "02_parfum_populer_indonesia.md"),
        ("Dataset BAYLab: formulasi paten berlabel", "BAYLab dataset file 06", dataset / "6_rag" / "dokumen" / "06_formulasi_paten_berlabel.md"),
        ("Dataset BAYLab: produk referensi", "BAYLab dataset file 08", dataset / "6_rag" / "dokumen" / "08_produk_referensi.md"),
        ("Rencana eksperimen LKPI", "BAYLab RENCANA_EKSPERIMEN_LKPI", dataset / "RENCANA_EKSPERIMEN_LKPI.md"),
        ("Panduan dataset BAYLab", "BAYLab PANDUAN", dataset / "PANDUAN.md"),
    ]
    added = []
    for title, ref, path in docs:
        if title in existing or not path.exists():
            continue
        response = client.post(
            "/api/rag/documents",
            data={"title": title, "source_ref": ref, "authorized": "true"},
            files={"file": (path.name, path.read_bytes(), "text/markdown")},
        )
        response.raise_for_status()
        added.append(title)
    return added


def main() -> None:
    creds = ensure_formulator()
    with httpx.Client(base_url=API, trust_env=False, timeout=60) as client:
        login(client, creds["email"], creds["password"])
        forms = {f["name"]: f for f in client.get("/api/workspace/formulations").json()}
        created = 0
        for body, assessment in CANDIDATES:
            if body["name"] not in forms:
                response = client.post("/api/workspace/formulations", json=body)
                response.raise_for_status()
                forms[body["name"]] = response.json()
                created += 1
            record = forms[body["name"]]
            if not record.get("assessment"):
                client.put(
                    f"/api/workspace/formulations/{record['id']}/assessment",
                    json={**assessment, "comparison_protocol": PROTOCOL},
                ).raise_for_status()
        batches = {e["batch_id"] for e in client.get("/api/workspace/experiments").json()}
        logged = 0
        for i, (name, (start, end, ph, homogeneous, aroma)) in enumerate(EXPERIMENTS.items(), 1):
            batch = f"DEMO-B{i}"
            if batch in batches:
                continue
            client.post("/api/workspace/experiments", json={
                "formulation_id": forms[name]["id"], "batch_id": batch, "protocol": "DEMO-54C-14H",
                "source_ref": "Nilai rekaan untuk demo; bukan hasil uji", "measured_on": "2026-11-28",
                "initial_h2o2": start, "final_h2o2": end, "ph": ph, "temperature_c": 54,
                "duration_days": 14, "homogeneous": homogeneous, "aroma_intensity": aroma,
                "notes": NOTE, "data_origin": "synthetic",
            }).raise_for_status()
            logged += 1
        added = upload_documents(client)
    print(f"Formulator demo : {creds['email']} (kata sandi di backend/data/demo-formulator.json)")
    print(f"Formulasi baru  : {created} · eksperimen contoh baru: {logged}")
    print(f"Dokumen RAG baru: {len(added)} {added}")


if __name__ == "__main__":
    main()
