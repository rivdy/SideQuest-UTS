# Menghubungkan login BAYLab ke Supabase

Workspace cloud menyediakan login organisasi, pembuatan formulasi, penyimpanan penilaian bersumber, pencatatan dan pengarsipan eksperimen, serta pemeringkatan berbobot melalui Next.js dan Supabase. Aktifkan migrasi v2 di bawah sebelum memakai fitur penulisan. Data lokal hanya dipindahkan lewat impor yang dijalankan pengguna; RAG, RDKit dan pelatihan model masih lokal.

## 1. Environment frontend dan Vercel

Atur tiga variabel berikut di frontend/.env.local untuk lokal, dan Vercel Project > Settings > Environment Variables untuk deployment:

```
BAYLAB_AUTH_PROVIDER=supabase
NEXT_PUBLIC_SUPABASE_URL=https://nehmhhjhwsyxhfrpkfxw.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable key project>
```

URL dan key yang diberikan sudah dimasukkan ke frontend/.env.local (diabaikan Git). Tidak diperlukan Secret Key, database password, Prisma, @supabase/server atau MCP Claude. Jangan salin secret yang disamarkan sebagai nilai konfigurasi.

Untuk kembali ke seluruh fitur lokal, ubah BAYLAB_AUTH_PROVIDER=local dan restart Next.js; backend Python dan Ollama berjalan seperti sebelumnya. Pada mode Supabase, API tidak diteruskan ke localhost.

## 2. Tabel dan RLS

Buka SQL Editor project Supabase, tempel dan jalankan supabase/migrations/202611040001_organization_auth.sql. Ini membuat tabel organisasi, keanggotaan dan record, dengan RLS aktif. Project tidak diubah otomatis melalui Publishable Key: key tersebut memang tidak memiliki hak administrasi skema.

## 3. Akun pertama

Buka Authentication > Users > Add user. Buat akun dengan email milik Anda dan kata sandi kuat. Pastikan akun sudah dikonfirmasi sesuai alur admin Supabase. Salin User UID, ganti REPLACE_WITH_AUTH_USER_UUID di supabase/bootstrap-admin.sql, lalu jalankan isinya di SQL Editor. Akun admin lokal lama tidak otomatis valid di cloud.

Buka Authentication > URL Configuration dan isi Site URL dengan URL Vercel. Untuk alur login password ini belum ada callback email. Undangan, signup publik, dan reset email belum diimplementasikan; buat akun melalui administrator. Jika tidak memakai signup publik, nonaktifkan Allow new users to sign up di konfigurasi Auth.

## 4. Aktifkan workspace cloud v2

Untuk project yang sudah memakai login dan sudah mengimpor data, jalankan seluruh isi `supabase/migrations/202611040002_cloud_workspace.sql` lewat SQL Editor. Tidak perlu mengulang bootstrap akun atau impor data. Migrasi v2 mempertahankan record yang ada dan dapat dijalankan ulang. Pada project baru, jalankan migrasi organisasi v1 terlebih dahulu.

Fitur yang aktif setelah SQL dan kode terbaru terpasang:

- Admin/formulator membuat kandidat dengan 1?30 bahan dan total 100% massa.
- Penilaian lima kriteria wajib mempunyai skor, sumber, alasan dan protokol pembandingan.
- Anggota termasuk viewer dapat menghitung peringkat. Kandidat dengan bukti belum lengkap/protokol berbeda ditampilkan tanpa peringkat; data nyata dan ilustrasi tidak dicampur.
- Admin/formulator mencatat eksperimen, termasuk hasil gagal. Retensi dan snapshot komposisi dihitung oleh database. Konfirmasi wajib untuk data lab nyata; formulasi ilustrasi tidak boleh menghasilkan catatan nyata.
- Pengukuran batch/protokol/hari yang sama ditolak. Arsip menyembunyikan catatan dari daftar aktif, tanpa menghapus record atau jejak audit.

Tidak perlu Secret Key, server Render atau perubahan environment untuk ketiga fitur ini. Koneksi menggunakan sesi Supabase milik pengguna. Privilege menulis langsung ke tabel tetap ditutup; fungsi RPC memeriksa anggota aktif, peran, organisasi dan payload sebelum mutasi. Audit disimpan di baylab_audit_events dan hanya dapat dibaca admin organisasinya.

Frontend memeriksa `/api/workspace/capabilities` setelah login. Tanpa migrasi v2, form tetap dinonaktifkan dan banner menjelaskan aktivasi SQL. Setelah migrasi, `workspace_ready` bernilai true. `/api/auth/config` menampilkan `workspace: cloud`, tetapi kesiapan SQL tetap diperiksa melalui endpoint capabilities.

Hash komposisi kandidat baru menggunakan normalisasi PostgreSQL; hash kandidat yang diimpor dipertahankan. Sebelum penggabungan data lokal/cloud untuk pelatihan model mendatang, format fingerprint perlu diseragamkan agar kelompok formulasi ekuivalen tidak terpisah.

## 5. Deploy dan periksa

Push perubahan kode ke GitHub, lalu deploy ulang Vercel dengan Root Directory frontend. Environment baru berlaku pada build/deployment baru. Buka /api/auth/config: harus menampilkan provider supabase. Buka /baylab-figma.html#login, gunakan kode lkpi dan akun Supabase yang baru dibuat.

Email/kata sandi yang salah ditolak Supabase. User terautentikasi tanpa keanggotaan lkpi tetap ditolak aplikasi. Cookie sesi HttpOnly dan SameSite Strict, Secure di Vercel. Semua mutasi memakai pengecekan origin dan CSRF; identitas diperiksa memakai auth.getUser() pada setiap permintaan. Refresh token dipersistenkan di Route Handler; tidak diperlukan middleware untuk halaman HTML statis ini. Token tidak diberikan ke JS browser.

## Batas tahap koneksi

- Cloud mendukung akun, profil, pembacaan record, formulasi, penilaian, eksperimen, arsip dan ranking. Pembuatan anggota dari aplikasi belum diaktifkan.
- Write privilege tabel dicabut dari anon/authenticated. RLS dan UI tidak menerima peran dari metadata yang dapat diedit pengguna.
- Skrip ekspor riset menyediakan migrasi record lokal; API mutasi dan audit cloud tersedia setelah migrasi v2. Data dan berkas lokal tidak diunggah otomatis.
- RAG, RDKit, pelatihan dan berkas dokumen/model tetap lokal. Metrik model yang diimpor tetap dapat dibaca di cloud; tidak ada pelatihan model otomatis di Supabase.
- Perubahan password melakukan global sign-out; token akses Supabase yang sudah diterbitkan dapat berlaku sampai kedaluwarsa sesuai kebijakan Supabase.
- Rate limiting login mengikuti Supabase Auth; proxy Vercel dapat menggabungkan IP sumber, sehingga perlu pengaturan rate limit/WAF lebih lanjut sebelum skala publik.
- SQL dan akun nyata belum dapat diverifikasi sampai administrator menjalankan setup. Publishable Key bukan akses SQL Editor.

## Verifikasi implementasi

Build dan lint frontend lulus. Verifikasi v2:

- `node scripts/check_cloud_workspace.mjs`: 35 pemeriksaan fungsi PostgreSQL dan RLS memakai PGlite, termasuk akses lintas organisasi dan payload tidak valid.
- `node scripts/check_supabase.mjs --browser`: 30 pemeriksaan API Next.js dan 13 pemeriksaan browser. Transport Auth/PostgREST ditiru, tetapi operasi data menjalankan SQL PostgreSQL yang sebenarnya di database uji terisolasi.
- Pemeriksaan browser mencakup penyimpanan, penilaian, ranking, eksperimen, reload sesi/data dan tampilan 390 px. Tidak menghasilkan PNG baru.

Semua fixture sintetis hanya ada di database pengujian. Hasil ini tidak menyatakan migrasi v2 sudah dijalankan di Supabase pengguna; aktivasi project asli tetap melalui SQL Editor. Laporan tersimpan di qa/cloud-workspace-sql-report.json, qa/supabase-contract-report.json dan qa/cloud-workspace-browser-report.json.

Contoh environment: frontend/.env.example. Domain frontend: https://side-quest-uts.vercel.app. File contoh bukan konfigurasi yang otomatis dimuat Vercel; masukkan nilainya melalui dashboard.

## Ekspor data riset lokal

Skrip `scripts/export_research_to_supabase.py` membuka SQLite read-only, hanya membaca organisasi dan workspace_records milik organisasi yang dipilih. Akun, password, sesi, audit pengguna, dokumen RAG dan berkas model tidak diekspor. SQL output disimpan di backend/data/exports yang diabaikan Git; jangan unggah ke repository publik.

Dari root proyek di PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts/export_research_to_supabase.py
```

Default organisasi lkpi dan admin tujuan admin@baylab.local. Gunakan --organization, --owner-email, --db atau --output untuk sumber/tujuan lain. Output dengan nama sama tidak ditimpa. Jalankan seluruh file SQL melalui Supabase SQL Editor setelah setup organisasi dan akun admin aktif selesai.

UUID tujuan deterministik berdasarkan organisasi/jenis/ID lokal; tautan eksperimen ke formulasi dikonversi. Status arsip serta label sintetis tetap dipertahankan. Menjalankan ulang snapshot yang sama tidak membuat duplikat. Jika record tujuan dengan ID sama sudah berbeda, seluruh transaksi dibatalkan agar tidak menimpa perubahan cloud. created_by tujuan adalah admin pengimpor, bukan pemetaan penulis asli; riwayat audit lokal tidak dimigrasikan.

Metrik dan titik grafik model dapat dibaca setelah impor. Artifact key/hash merupakan referensi sumber; berkas model belum diunggah atau dapat dijalankan dari cloud. Data prototipe browser/localStorage tidak termasuk database server ini.
