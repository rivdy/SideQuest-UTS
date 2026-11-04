# RAG lokal BAYLab AI

Chat AI aktif di http://localhost:3000/baylab-figma.html#chat.

## Alur yang diimplementasikan

1. Unggah PDF berteks, TXT, atau Markdown. Isi judul, identitas sumber (DOI/SDS/dokumen internal), dan konfirmasi hak penggunaan teks.
2. Backend mengekstrak teks per halaman, memecahnya menjadi 300 kata dengan overlap 45 kata, dan menyimpan indeks SQLite FTS5 di backend/data/rag.sqlite3.
3. Pertanyaan mencari maksimal lima potongan menggunakan BM25. Pilihan dokumen pada UI membatasi pencarian. Pertanyaan tanpa kecocokan tidak dikirim ke model.
4. Qwen3 4B pada Ollama localhost:11434 merangkum dua potongan teratas dari hasil pencarian. Konteks model dibatasi 4.096 token dan keluaran 600 token, dengan permintaan maksimal dua klaim singkat, agar pemrosesan CPU tetap terjangkau. Tidak ada API cloud, tools model, atau pengambilan URL dokumen otomatis.
5. Backend memvalidasi format JSON, ID sumber, dan kecocokan kutipan verbatim. Klaim dengan rujukan palsu dibuang. UI menampilkan judul, identitas sumber, nomor halaman, dan teks sumber.

Ini retrieval leksikal BM25, belum embedding, pencarian hybrid atau pgvector. SQLite dipakai agar versi lokal dapat berjalan tanpa Docker/PostgreSQL. Pencarian sinonim lintas bahasa masih terbatas. Indeks dapat diganti pada tahap migrasi database berikutnya.

## Menjalankan (PowerShell)

Terminal backend, dari root proyek:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.lock
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-server-header
```

Terminal frontend:

```powershell
npm.cmd --prefix frontend run dev
```

Ollama harus aktif. Setelah instalasi, unduh model sekali (sekitar 2,5 GB):

```powershell
ollama pull qwen3:4b
ollama list
```

Jika Ollama belum berjalan, jalankan `ollama serve` pada terminal tersendiri. Bila PATH belum diperbarui, executable Windows ada di `$env:LOCALAPPDATA\Programs\Ollama\ollama.exe`.

Model dapat dipilih dengan `$env:BAYLAB_OLLAMA_MODEL='nama-model-lokal'` sebelum menyalakan backend. Endpoint sengaja dikunci ke 127.0.0.1:11434; environment proxy jaringan diabaikan. Backend tidak membaca .env otomatis; gunakan environment terminal. Jangan memilih model cloud.

Buka Chat AI, lalu pilih **Muat ulang status** setelah model selesai diunduh. Bila model belum tersedia, UI menampilkan potongan sumber dengan label yang jelas, tanpa menyatakan potongan tersebut sebagai jawaban generatif.

## Dokumen awal

Proposal BAYLab AI yang diberikan pengguna telah diindeks secara lokal menjadi 39 potongan, dengan identitas `PROPOSAL-BAYLAB-UTS`. Proposal adalah sumber mengenai rencana proyek, bukan bukti bahwa target sudah tercapai atau validasi ilmiah formula. Indeks tidak disertakan dalam Git; komputer lain perlu mengunggah ulang dokumennya.

Contoh pertanyaan: **Apa tujuan dan target pengembangan BAYLab AI dalam proposal?**

CLI opsional:

```powershell
.\.venv\Scripts\python.exe scripts/ingest_document.py 'C:\path\proposal.pdf' --title 'Proposal BAYLab AI' --source 'PROPOSAL-BAYLAB-UTS' --authorized
```

Penghapusan dokumen menghapus potongan dan indeks aktif. Riwayat chat pada tab yang sedang terbuka masih memuat kutipan lama; mulai percakapan baru untuk menghapusnya dari UI. Penghapusan SQLite bukan jaminan penghapusan forensik dari disk atau backup.

## Batas keamanan dan kualitas

- Semua endpoint RAG memerlukan sesi organisasi. Mutasi memerlukan CSRF dan peran admin/formulator. Indeks lama rag.sqlite3 dimiliki organisasi lkpi; organisasi lain memakai rag.<organisasi>.sqlite3 terpisah. CLI ingestion tanpa konteks akun ditujukan untuk lkpi. Belum ada otorisasi per proyek, RLS database, atau kesiapan deployment publik.
- Dokumen dan pertanyaan tidak dikirim ke API cloud. Dokumen yang ditemukan hanya diteruskan ke Ollama lokal; unduhan paket/model tetap menggunakan internet.
- Maksimum file 16 MB, PDF 80 halaman, teks 300.000 karakter, dan 100 dokumen. Hanya ekstensi PDF/TXT/MD, signature PDF, UTF-8, dan batas ukuran diperiksa. Belum ada antivirus, OCR atau isolasi parser. Gunakan dokumen yang dipercaya.
- Berkas asli tidak disimpan; hasil ekstraksi disimpan di SQLite tanpa enkripsi aplikasi. Indeks diabaikan Git. Pertimbangkan enkripsi disk untuk dokumen privat.
- Validasi kutipan membuktikan bahwa kutipan tersedia, bukan bahwa kesimpulan model benar. Tidak ada klaim akurasi RAG atau aturan kimia tervalidasi.
- Prompt memperlakukan sumber sebagai data tidak tepercaya, tetapi pertahanan prompt injection tidak sempurna. Model tidak diberi tools dan tidak boleh menentukan risiko/dosis/efikasi.
- Chat tidak otomatis membaca hasil eksperimen localStorage atau melatih model.
- Docker Compose lama belum menghubungkan Ollama host; gunakan instruksi localhost di atas.

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend scripts/ingest_document.py
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
node qa-rag.mjs
```

Tes backend memakai indeks sementara dan mock transport model, mencakup deduplikasi, persistensi, halaman, filter dokumen, file invalid, input, origin, respons offline, abstention, serta penolakan sitasi palsu. Mock bukan bukti kualitas model nyata. Tes browser membutuhkan frontend:3000, backend:8000, dan proposal awal terindeks; dokumen QA dibuat lalu dihapus otomatis.

Dokumentasi implementasi: https://docs.ollama.com/api/chat dan https://ollama.com/library/qwen3:4b.


## Status model lokal ? 3 November 2026

Qwen3 4B (Q4_K_M) sudah diunduh, diverifikasi Ollama, dan berhasil menghasilkan jawaban bersitasi. Komputer pengujian menjalankan model di CPU. Sembilan dokumen tersedia pada indeks lokal saat pengujian.

Jalur yang diuji: halaman Chat -> POST /api/rag/ask pada Next.js port 3000 -> FastAPI port 8000 -> Ollama port 11434. Frontend menggunakan alamat relatif /api/rag; tidak memanggil Ollama secara langsung. GET /api/rag/status memperlihatkan kesiapan model.

Batas tunggu proxy Next.js dinaikkan dari default 30 detik menjadi 210 detik. Batas panggilan model backend tetap 180 detik dan batas browser 195 detik. Uji terakhir melalui frontend selesai dalam 80,3 detik; ini hasil satu pengujian, bukan jaminan waktu respons. Pemuatan awal dan beban CPU memengaruhi waktu tunggu.

Uji nyata lulus untuk jawaban proposal, jawaban literatur dengan dokumen terpilih, kecocokan kutipan, dan pertanyaan tanpa sumber. Laporan lokal: qa/rag-live.json dan qa/ollama-local-integration.json. Seluruh 50 tes backend lulus setelah penyesuaian konteks. Tidak ada perubahan status validasi aturan kimia.

Untuk mengulang uji nyata saat ketiga layanan aktif:

```powershell
.\.venv\Scripts\python.exe scripts/check_rag_live.py
.\.venv\Scripts\python.exe scripts/check_rag_frontend.py
```

Uji kedua membutuhkan catatan EVONIK-H2O2-STABILITY dalam indeks. Setelah memulai ulang komputer, pastikan aplikasi Ollama, backend, dan frontend aktif. Model tidak perlu diunduh ulang. Di halaman Chat, klik Muat ulang status; jika dokumen belum ada di komputer lain, unggah atau indeks kembali.
