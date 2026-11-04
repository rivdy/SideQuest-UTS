# Uji deployment backend di Render

Frontend tetap di Vercel. Layanan ini memakai backend Python yang sudah ada, belum terintegrasi dengan sesi Supabase. Jangan menganggap deploy berhasil berarti seluruh fitur cloud sudah tersambung.

Isian Create Web Service:
- Name: baylab-api
- Language: Docker
- Branch: main
- Region: Singapore jika tersedia, atau region yang dipilih bersama layanan terkait.
- Root Directory: kosong.
- Dockerfile Path: ./backend/Dockerfile
- Advanced > Docker Build Context Directory: ./backend
- Docker Command: kosong (memakai CMD Dockerfile).
- Health Check Path: /health

Environment:
- PORT=10000
- BAYLAB_SECURE_COOKIES=true
- BAYLAB_ALLOWED_ORIGINS=https://side-quest-uts.vercel.app
- BAYLAB_DATA_DIR=/app/data
- BAYLAB_DB=/app/data/workspace.sqlite3
- BAYLAB_RAG_DB=/app/data/rag.sqlite3

Pastikan Dockerfile terbaru sudah di-push sebelum deploy. Dockerfile memakai PORT dan menyediakan direktori data writable bagi UID 10001. Build Docker Linux belum diuji dalam sesi konfigurasi ini.

Free hanya untuk mencoba startup/health. RAM 512 MB belum diverifikasi memadai untuk semua dependensi ilmiah. Free tidak memiliki persistent disk; SQLite, unggahan dan model akan hilang ketika filesystem diganti. Jangan simpan data riset nyata. Jangan menganggap Supabase sudah digunakan oleh backend karena ada env SUPABASE_URL: backend Python belum membaca konfigurasi tersebut.

Untuk penyimpanan permanen dibutuhkan migrasi database/storage atau layanan berbayar dengan persistent disk. Jika memakai disk, mount ke /app/data dan pastikan izin tulis UID 10001. Biaya komputasi/disk perlu dipilih pengguna; tidak ada layanan berbayar dibuat otomatis.

Setelah status Live, periksa https://NAMA-SERVICE.onrender.com/health. Health hanya liveness proses, bukan bukti database, login atau model siap. Kirim URL backend dan domain frontend untuk penyambungan berikutnya.

Hal yang masih belum aktif: verifikasi token Supabase pada Python, pengiriman permintaan frontend cloud ke Python, RAG publik (masih dibatasi localhost), Ollama pada server, bootstrap akun Python, migrasi data/artefak dan dataset kelarutan. Jangan memasukkan key Supabase ke Render dengan harapan hal-hal ini berjalan otomatis.

Contoh environment siap disalin: backend/.env.example. Isi nilai di dashboard Render; mengunggah file contoh ke Git tidak mengatur environment server.
