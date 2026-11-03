# Screening struktur nyata — tahap draft

Buka http://localhost:3000/baylab-figma.html#screening. Halaman ini menggantikan hasil screening tetap pada aplikasi Figma. Prototipe index.html dan demo.html tetap terpisah.

## Yang berjalan

- FastAPI menjalankan RDKit lokal untuk membaca dan menyanitasi SMILES satu molekul, maksimum 200 atom / 2.000 karakter.
- Enam SMARTS draft mendeteksi ikatan C=C nonaromatik, aldehida, alkohol, fenol, ester, dan ikatan peroksida. Setiap hasil menyertakan indeks atom, jumlah kecocokan, versi aturan, versi RDKit, dan waktu komputasi.
- Gambar molekul dibuat RDKit dengan atom yang cocok disorot; rumus, massa molekul, muatan formal, dan SMILES kanonik dihitung dari input.
- PubChem live menerima nama/CAS atau CID setelah tombol Cari ditekan. Hanya identitas pencarian yang dikirim ke endpoint NIH tetap. Tidak ada pengiriman SMILES manual, dokumen RAG, atau formula ke layanan ini.
- Identitas PubChem disertai URL sumber dan waktu pengambilan baru. Tidak ada fallback diam-diam ke data simulasi saat jaringan gagal. Pencarian ambigu meminta CID.
- Laporan JSON dapat diunduh. Input dan hasil screening hanya berada dalam memori halaman, tidak disimpan dalam localStorage atau database.

## Status ilmiah

Semua pola ber-ID DRAFT-*, bukan R-01 sampai R-12. Spreadsheet dan 20 kasus acuan Pak Pugoh belum tersedia. Pola merupakan detektor struktur, bukan aturan risiko kimia tervalidasi. Tidak tersedia endpoint untuk mengubah status menjadi validated. Penilaian oleh ahli dan kasus acuan diperlukan sebelum aturan risiko dapat ditambahkan.

Jumlah kecocokan bukan skor risiko. Tidak ada kecocokan tidak berarti aman. Sistem belum mengevaluasi pH, suhu, konsentrasi, logam jejak, kelarutan, stabilitas, atau interaksi campuran. Tidak ada klaim efikasi antimikroba. Komposisi parfum rahasia tidak ditebak; campuran dan wildcard ditolak.

Sumber implementasi: [RDKit — pembacaan molekul dan substructure matching](https://www.rdkit.org/docs/GettingStartedInPython.html), [PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest). Sumber tersebut mendukung mekanisme perangkat lunak/identitas; bukan bukti ketidakcocokan kimia. Versi literature-draft-2 menambahkan catatan literatur kontekstual pada empat pola: alkena, aldehida, alkohol, dan fenol. Pola ester dan peroksida tetap tanpa bukti spesifik. Panduan H2O2 ditampilkan terpisah sebagai konteks formulasi, bukan diterapkan ke semua peroksida. Lihat [LITERATURE.md](LITERATURE.md).

## Menjalankan

Dari root proyek, pada terminal terpisah:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-server-header
```

```powershell
cd frontend
npm.cmd run dev
```

Jangan membuka akses publik: autentikasi organisasi belum tersedia. Endpoint memakai pembatasan localhost/origin, batas request, dan rate limit sederhana per proses. Data privat dan deployment produksi tetap memerlukan kontrol akses serta hardening lanjutan.

## API

- GET /api/chemistry/rules — versi dan daftar pola draft.
- POST /api/chemistry/screen — JSON `{"smiles":"CCO"}`.
- POST /api/chemistry/pubchem — JSON `{"query":"702","namespace":"cid","consent_external_lookup":true}`; namespace name untuk nama/CAS.

## Verifikasi 3 November 2026

39 tes backend lulus (17 kasus baru screening/PubChem termasuk parametrization), 10 pemeriksaan browser lulus. Pemeriksaan mencakup perubahan fitur terhadap input, tidak salah membaca aromatik sebagai alkena, input invalid/campuran/wildcard, larangan field status tambahan, asal permintaan, respons PubChem gagal/timeout, gambar, desktop dan ponsel. Ini tes perangkat lunak, **bukan** 20 kasus acuan kimia dari ahli.

PubChem live melalui proxy Next.js berhasil mengembalikan ethanol, CID 702, SMILES CCO. Uji otomatis memakai mock transport untuk kestabilan; uji live dilakukan terpisah.

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
node qa-chemistry.mjs
```


Pembaruan literatur 3 November 2026: enam sumber tersedia melalui GET /api/chemistry/evidence. Catatan berlabel draft sudah diindeks lokal; ulangi dengan `.\.venv\Scripts\python.exe scripts/ingest_literature.py` (idempoten untuk konten yang sama). 49 tes backend lulus setelah penambahan bukti. Sepuluh pemeriksaan browser di atas berasal dari versi screening sebelumnya; penambahan literatur diuji pada backend dan render JavaScript.
