# Menghubungkan login BAYLab ke Supabase

Integrasi ini menambahkan login Supabase melalui server Next.js di Vercel. Akun dan data lokal tidak otomatis dipindahkan. Workspace cloud saat ini hanya dapat membaca data organisasi; penulisan formulasi/eksperimen, ranking, unggah dokumen, pelatihan dan layanan kimia masih menggunakan aplikasi lokal. Jangan menganggap semua modul sudah online.

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

## 4. Deploy dan periksa

Push perubahan kode ke GitHub, lalu deploy ulang Vercel dengan Root Directory frontend. Environment baru berlaku pada build/deployment baru. Buka /api/auth/config: harus menampilkan provider supabase. Buka /baylab-figma.html#login, gunakan kode lkpi dan akun Supabase yang baru dibuat.

Email/kata sandi yang salah ditolak Supabase. User terautentikasi tanpa keanggotaan lkpi tetap ditolak aplikasi. Cookie sesi HttpOnly dan SameSite Strict, Secure di Vercel. Semua mutasi memakai pengecekan origin dan CSRF; identitas diperiksa memakai auth.getUser() pada setiap permintaan. Refresh token dipersistenkan di Route Handler; tidak diperlukan middleware untuk halaman HTML statis ini. Token tidak diberikan ke JS browser.

## Batas tahap koneksi

- Hanya login, sesi, logout, perubahan password, profil organisasi, daftar anggota admin dan pembacaan record yang diimplementasikan di cloud.
- Write privilege tabel dicabut dari anon/authenticated. RLS dan UI tidak menerima peran dari metadata yang dapat diedit pengguna.
- Migrasi lokal ke cloud, API mutasi dan audit cloud belum dibuat. Data aktual/model lokal tidak diunggah.
- RAG, RDKit, model dan dokumen tetap lokal. UI cloud menjelaskan fitur yang belum tersambung dan tidak memakai angka contoh sebagai data cloud.
- Perubahan password melakukan global sign-out; token akses Supabase yang sudah diterbitkan dapat berlaku sampai kedaluwarsa sesuai kebijakan Supabase.
- Rate limiting login mengikuti Supabase Auth; proxy Vercel dapat menggabungkan IP sumber, sehingga perlu pengaturan rate limit/WAF lebih lanjut sebelum skala publik.
- SQL dan akun nyata belum dapat diverifikasi sampai administrator menjalankan setup. Publishable Key bukan akses SQL Editor.

## Verifikasi implementasi

Build dan lint frontend lulus. `node scripts/check_supabase.mjs` menguji 20 kontrak HTTP dengan Auth/PostgREST tiruan terisolasi, bukan verifikasi SQL/RLS pada project asli. Audit npm produksi: 0 kerentanan dikenal saat pemeriksaan. Endpoint Auth settings project asli merespons 200, tetapi tabel baylab_organizations merespons PGRST205 sebelum setup SQL dijalankan.

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
