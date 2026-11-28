"""Add published reference compositions to the LOCAL workspace as "literature" candidates.

Run from the project root while FastAPI is running on port 8000:
    .venv\\Scripts\\python.exe scripts\\seed_literature.py

Each composition is transcribed from a public source (USP-NF monograph, US patent examples).
They are labelled "Data literatur": real published compositions, not LKPI lab results, and
never used as model training rows. Amounts are % w/w of the final product as written in the
source; water is the stated balance ("qs to 100%"). Only criteria with a numeric result in the
source get a score; everything else stays empty ("belum diketahui"). Running it again skips
what already exists.
"""

import httpx
from seed_demo import API, ensure_formulator, login

PROTOCOL = "LIT-RUBRIK-1"
RUBRIC = (
    "LIT-RUBRIK-1: skor stabilitas suhu = batas bawah retensi H2O2 (%) yang dilaporkan sumber "
    "pada uji dipercepat. Kriteria tanpa angka di sumber dibiarkan kosong."
)
CAVEAT = (
    "Komposisi literatur, bukan hasil lab LKPI dan bukan klaim efikasi BAYLab. "
    "Cocokkan dengan dokumen asli sebelum dipakai."
)
NPE_NOTE = (
    "Nonilfenol etoksilat dibatasi di UE (Direktif 2003/53/EC; REACH Annex XIV lewat Regulasi "
    "(UE) 2017/999); untuk formula baru gunakan alkohol etoksilat."
)

US4238192 = "US 4238192 A"
US4238192_URL = "https://patents.google.com/patent/US4238192A/en"
US4238192_COMMON = [
    ("Hidrogen peroksida 35% (Albone 35 CG, terstabilkan)", "active", 17.14, "OO"),
    ("Nonilfenol etoksilat 9,5 EO", "solubilizer", 3.00, ""),
    ("Parfum (nama tidak diungkap paten)", "fragrance", 0.15, ""),
    ("Chloramine Brilliant Violet B (pewarna)", "other", 0.000165, ""),
    ("Tinopal CBS (pencerah optik)", "other", 0.10, ""),
    ("Tinopal SWN (pencerah optik)", "other", 0.05, ""),
]
US4238192_RESULT = (
    "Hasil di paten: dipanaskan 100 °C selama 24 jam, kehilangan H2O2 kurang dari 5%, warna dan "
    "parfum tidak berubah; menurut paten setara kira-kira 1 tahun umur simpan."
)
US4238192_EXAMPLES = [
    (
        "I",
        4.2,
        0.001794,
        [
            ("Amonium hidroksida 28%", "other", 1.2138, ""),
            ("DL-metionin (Racemethionine USP)", "stabilizer", 0.10, "CSCCC(C(=O)O)N"),
            ("Asam ftalat", "stabilizer", 1.6613, "OC(=O)c1ccccc1C(=O)O"),
        ],
    ),
    (
        "III",
        5.2,
        0.04794,
        [
            ("Amonium hidroksida 28%", "other", 1.8207, ""),
            (
                "DL-metionin (Racemethionine USP)",
                "stabilizer",
                0.1000,
                "CSCCC(C(=O)O)N",
            ),
            ("Asam sitrat", "stabilizer", 1.9212, "OC(=O)CC(O)(CC(=O)O)C(=O)O"),
        ],
    ),
    (
        "V",
        2.8,
        0.001794,
        [
            ("DL-metionin (Racemethionine USP)", "stabilizer", 0.10, "CSCCC(C(=O)O)N"),
            ("Asam adipat (Adipic Acid NF)", "stabilizer", 0.14619, "OC(=O)CCCCC(=O)O"),
        ],
    ),
    (
        "VI",
        1.9,
        0.001794,
        [
            ("DL-metionin (Racemethionine USP)", "stabilizer", 0.10, "CSCCC(C(=O)O)N"),
            ("Asam adipat (Adipic Acid NF)", "stabilizer", 1.4619, "OC(=O)CCCCC(=O)O"),
        ],
    ),
    (
        "VIII",
        5.5,
        0.001794,
        [
            ("Trietanolamina", "other", 7.4595, "OCCN(CCO)CCO"),
            ("DTPA (asam dietilenatriaminapentaasetat)", "stabilizer", 3.93, ""),
        ],
    ),
]

US9149550 = "US 9149550 B2"
US9149550_URL = "https://patents.google.com/patent/US9149550B2/en"


def comma(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def ingredients(rows: list[tuple[str, str, float, str]], water_name: str) -> list[dict]:
    items = [
        {"name": n, "role": r, "percent": p, **({"smiles": s} if s else {})}
        for n, r, p, s in rows
    ]
    water = round(100 - sum(i["percent"] for i in items), 6)
    return [*items, {"name": water_name, "role": "water", "percent": water}]


def temperature(source: str) -> dict:
    return {
        "comparison_protocol": PROTOCOL,
        "temperature": {"score": 95, "source_ref": source, "rationale": RUBRIC},
    }


def candidates() -> list[tuple[dict, dict | None]]:
    out: list[tuple[dict, dict | None]] = [
        (
            {
                "name": "USP Hydrogen Peroxide Topical Solution 3% (acuan monografi)",
                "aroma_profile": "Tanpa aroma",
                "ingredients": ingredients(
                    [("Hidrogen peroksida 50% (kadar aktif 3%)", "active", 6.0, "OO")],
                    "Air murni (Purified Water USP)",
                ),
                "notes": (
                    "Sumber: USP-NF monografi Hydrogen Peroxide Topical Solution "
                    "(https://doi.usp.org/USPNF/USPNF_M38590_03_01.html). Syarat: 2,5-3,5 g "
                    "H2O2/100 mL; pengawet bila ada maks. 0,05%; wadah tertutup rapat, tidak "
                    "tembus cahaya, suhu ruang terkendali; penetapan kadar titrasi KMnO4 0,1 N "
                    "(1 mL = 1,701 mg H2O2). Komposisi = titik tengah 3%, asumsi densitas "
                    "mendekati 1 g/mL. Ini antiseptik topikal, dipakai sebagai acuan mutu bahan "
                    "dan metode uji kadar, bukan formula disinfektan permukaan. "
                    + CAVEAT
                ),
                "data_origin": "literature",
            },
            None,
        ),
        (
            {
                "name": "US 6346279 Solution A: H2O2 dipercepat pH 1,27 (paten Virox)",
                "aroma_profile": "Tanpa aroma",
                "ingredients": ingredients(
                    [
                        ("Asam fosfat 75%", "stabilizer", 2.0, "OP(=O)(O)O"),
                        ("ATMP 50% (Briquest 301-50A)", "stabilizer", 7.5, ""),
                        (
                            "Alkil difenil oksida disulfonat dinatrium 45% (Dowfax)",
                            "solubilizer",
                            2.5,
                            "",
                        ),
                        (
                            "Asam dodesilbenzena sulfonat 98% (Biosoft)",
                            "solubilizer",
                            2.5,
                            "",
                        ),
                        (
                            "Oktilfenol etoksilat 70% (Triton X-405)",
                            "solubilizer",
                            1.0,
                            "",
                        ),
                        ("Hidrogen peroksida 50%", "active", 15.0, "OO"),
                    ],
                    "Air suling",
                ),
                "notes": (
                    "Sumber: US 6346279 B1, Example I (Solution A), "
                    "https://patents.google.com/patent/US6346279B1/en. Paten menulis bagian "
                    "berat per 1000 (jumlah 1000), di sini dibagi 10 menjadi % b/b. pH 1,27. "
                    "Dibuat di bejana terpasivasi, H2O2 ditambahkan terakhir. Kadar H2O2 aktif "
                    "7,5%. Paten melaporkan uji mikrobiologi di Tabel I-V; itu klaim paten, "
                    "bukan hasil BAYLab. Tidak ada data stabilitas penyimpanan. Oktilfenol "
                    "etoksilat masuk REACH Annex XIV (Regulasi (UE) 2017/999). "
                    + CAVEAT
                ),
                "data_origin": "literature",
            },
            None,
        ),
    ]
    for number, ph, blue, specific in US4238192_EXAMPLES:
        rows = [
            *US4238192_COMMON,
            ("Polar Brilliant Blue GAW (pewarna)", "other", blue, ""),
            *specific,
        ]
        out.append(
            (
                {
                    "name": f"{US4238192} Ex. {number}: H2O2 6% beraroma, pH {comma(ph)}",
                    "aroma_profile": "Parfum 0,15% (nama tidak diungkap)",
                    "ingredients": ingredients(rows, "Air deionisasi (qs 100%)"),
                    "notes": (
                        f"Sumber: {US4238192}, Example {number}, {US4238192_URL}. Semua angka % b/b "
                        f"seperti di paten; H2O2 35% 17,14% setara kira-kira 6% aktif. pH {comma(ph)}. "
                        f"{US4238192_RESULT} {NPE_NOTE} {CAVEAT}"
                    ),
                    "data_origin": "literature",
                },
                temperature(
                    f"{US4238192} Ex. {number}: 100 °C 24 jam, kehilangan H2O2 <5%"
                ),
            )
        )
    for number, ph, rows, buffer in [
        (
            1,
            4.38,
            [
                ("Asam fosfat 85%", "stabilizer", 0.04, "OP(=O)(O)O"),
                ("Natrium hidroksida 10%", "other", 0.17, ""),
                ("Isopropanol 91%", "solvent", 5.00, "CC(C)O"),
            ],
            "Penyangga fosfat/NaOH dengan isopropanol 5%; paten menyebut pH stabil.",
        ),
        (
            16,
            4.90,
            [
                ("Asam fosfat 85%", "stabilizer", 0.02, "OP(=O)(O)O"),
                (
                    "Asam sitrat anhidrat",
                    "stabilizer",
                    0.07,
                    "OC(=O)CC(O)(CC(=O)O)C(=O)O",
                ),
                ("Natrium sitrat dihidrat", "stabilizer", 0.19, ""),
            ],
            "Penyangga sitrat; paten melaporkan perubahan pH <0,2 unit.",
        ),
    ]:
        base = [
            ("Hidrogen peroksida 35% (0,11% aktif)", "active", 0.30, "OO"),
            ("Polisorbat 20 (Polysorbate 20 NF)", "solubilizer", 5.00, ""),
            (
                "Fragrance premix Preblend (parfum + asam undesilenat)",
                "fragrance",
                1.00,
                "",
            ),
        ]
        out.append(
            (
                {
                    "name": f"{US9149550} Ex. {number}: H2O2 0,11% + parfum 1%, pH {comma(ph)}",
                    "aroma_profile": "Fragrance premix 1% (varian Preblend menurut tabel paten)",
                    "ingredients": ingredients(
                        [*base, *rows], "Air deionisasi (sampai 100%)"
                    ),
                    "notes": (
                        f"Sumber: {US9149550}, Example {number}, {US9149550_URL}. pH {comma(ph)}. "
                        f"{buffer} Uji 45 °C minimal 8 minggu (dievaluasi tiap 2 minggu sampai 12 "
                        "minggu); paten menyatakan diperkirakan stabil minimal 1 tahun. Retensi "
                        "H2O2 tidak diberi angka, jadi skor dibiarkan kosong. Nama varian "
                        f"premix perlu dicek di PDF paten. {CAVEAT}"
                    ),
                    "data_origin": "literature",
                },
                None,
            )
        )
    return out


def main() -> None:
    creds = ensure_formulator()
    with httpx.Client(base_url=API, trust_env=False, timeout=60) as client:
        login(client, creds["email"], creds["password"])
        forms = {f["name"]: f for f in client.get("/api/workspace/formulations").json()}
        created = scored = 0
        for body, assessment in candidates():
            if body["name"] not in forms:
                response = client.post("/api/workspace/formulations", json=body)
                if response.status_code == 422:
                    raise SystemExit(
                        "Backend belum mengenal asal data 'literature'. Mulai ulang uvicorn lalu "
                        f"jalankan lagi. Detail: {response.text}"
                    )
                response.raise_for_status()
                forms[body["name"]] = response.json()
                created += 1
            record = forms[body["name"]]
            if assessment and not record.get("assessment"):
                client.put(
                    f"/api/workspace/formulations/{record['id']}/assessment",
                    json=assessment,
                ).raise_for_status()
                scored += 1
    print(
        f"Formulasi literatur baru: {created} · penilaian dari angka sumber: {scored}"
    )


if __name__ == "__main__":
    main()
