# Pengembangan BAYLab AI

Tahap 0 membuat aplikasi baru di frontend/ dan backend/. Prototipe index.html tetap menjadi referensi UI, bukan aplikasi produksi. Modul dan skor ilustrasi di prototipe belum dipindahkan ke layanan server.

## Menjalankan tanpa Docker (PowerShell)

Prasyarat: Node.js 24, Python 3.12. Jalankan dari root proyek:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.lock
npm.cmd --prefix frontend ci
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Di terminal kedua:

```powershell
npm.cmd --prefix frontend run dev
```

Frontend: http://localhost:3000. API: http://localhost:8000/health. Dokumentasi API: http://localhost:8000/docs.
Respons health adalah liveness proses API saja, bukan pemeriksaan koneksi database atau Redis. Frontend tahap ini berupa halaman status fondasi, belum klien modul kimia.

## Docker Compose

Jalankan Docker Desktop terlebih dahulu. Salin .env.example ke .env dan ganti POSTGRES_PASSWORD dengan password acak lokal. Jangan commit .env.

```powershell
Copy-Item .env.example .env
# Edit .env sebelum menjalankan perintah berikut.
docker compose up --build
```

PostgreSQL dengan ekstensi vector dan Redis hanya berada di jaringan internal Compose. Port frontend/backend terikat ke 127.0.0.1. Database disimpan dalam volume postgres_data; init.sql dijalankan hanya saat volume pertama dibuat. Jangan menghapus volume untuk memperbarui skema; gunakan Alembic pada tahap berikutnya. Redis belum menyimpan antrean tugas dan persistence dinonaktifkan pada tahap ini.

Dockerfile memakai pengguna non-root. Compose ini untuk pengembangan lokal, belum konfigurasi produksi atau penyimpanan data NDA. API belum menggunakan database/Redis sampai modul persistence dibuat.

## Pemeriksaan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend audit --omit=dev --audit-level=high
.\.venv\Scripts\python.exe -m pip_audit -r backend/requirements.lock
```

Alternatif Make: `make dev`, `make test PYTHON=/path/to/venv/python`, `make lint`, `make build`. Di Windows gunakan perintah PowerShell di atas bila Make tidak tersedia.

CI menjalankan pytest, lint, pemeriksaan tipe, build, dan audit dependency. File workflow sudah disiapkan; eksekusi GitHub Actions memerlukan repository GitHub. Tidak ada repository Git yang diinisialisasi atau diunggah otomatis.

## Batas tahap dan pekerjaan berikutnya

- Tahap 0: scaffold Next.js/TypeScript/Tailwind, FastAPI, health, Docker Compose, CI dan tes.
- Tahap 1: skema SQLAlchemy, migrasi Alembic, seed bahan bersumber. Belum diimplementasikan.
- Tahap 2–3: PubChem/RDKit dan rule engine. Memerlukan spreadsheet R-01–R-12 serta 20 kasus acuan dari ahli; status awal aturan draft. Jangan membuat aturan ilmiah dari nama ID saja.
- Tahap 4–8: RAG, MCDA, eksperimen/ML, migrasi layar sesuai ZIP dan keamanan produksi. Belum diimplementasikan.

Komponen shadcn/ui ditambahkan saat migrasi layar memerlukannya. Klien API bertipe akan dibuat dari OpenAPI saat endpoint domain tersedia. Model Anthropic belum dipilih atau dipanggil; nama model dalam prompt bukan konfigurasi terverifikasi. Tidak ada data yang dikirim ke layanan AI.

Sumber implementasi: [instalasi Next.js](https://nextjs.org/docs/app/getting-started/installation), [pengujian FastAPI](https://fastapi.tiangolo.com/tutorial/testing/).

## Hasil pemeriksaan lokal — 31 Oktober 2026

- Backend pytest: 5 lulus. Ada peringatan deprecation httpx dari TestClient Starlette; tidak ada tes gagal.
- Ruff backend dan script Python: lulus.
- Frontend ESLint: lulus tanpa warning setelah perbaikan konfigurasi PostCSS.
- TypeScript: lulus.
- Next.js production build: lulus.
- Smoke HTTP frontend: lulus (halaman berbahasa Indonesia, security headers, file privat/backup mengembalikan 404).
- Docker Compose config: valid. Build dan startup container belum diuji karena Docker Engine belum berjalan.
- Audit runtime Python: tidak ada kerentanan dikenal yang dilaporkan.
- npm audit produksi: 0 temuan. Audit lengkap: 16 temuan sedang pada rantai tooling lint akibat minimatch <11.0.1 (GHSA-g3hv-75wg-m249), 0 tinggi/kritis. Perbaikan otomatis yang ditawarkan berupa downgrade besar ESLint/konfigurasi Next; tidak diterapkan karena tidak kompatibel dengan fondasi ini. Ini tetap pekerjaan terbuka, bukan hasil audit bersih.
- GitHub Actions belum dijalankan di GitHub. Belum ada pengujian browser visual untuk halaman fondasi baru.

Jalankan `node scripts/smoke_frontend.mjs` setelah build untuk mengulang smoke HTTP. Script membuka port localhost sementara dan menghentikan prosesnya setelah selesai.
