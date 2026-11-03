# Status keamanan — fondasi tahap 0

Belum siap produksi. Penilaian berikut berlaku untuk frontend/ dan backend/ yang baru; prototipe index.html menyimpan data di localStorage tanpa enkripsi dan tidak boleh menerima data rahasia atau akun asli. Checklist bukan sertifikasi keamanan.

| No. | Kontrol | Status dan batas |
|---|---|---|
| 1 | Private API keys | Tidak ada integrasi API privat; .env diabaikan Git. Jangan gunakan NEXT_PUBLIC_ untuk rahasia. |
| 2 | Rahasia dalam Git | Belum ada repository/histori Git; belum dapat mengaudit riwayat. |
| 3 | Public DB key | Tidak memakai SDK database dari browser. |
| 4 | RLS | Belum ada skema, tenancy, atau kebijakan RLS. Wajib sebelum data privat. |
| 5 | Enkripsi data | Belum diterapkan. Compose lokal HTTP; volume bukan backup terenkripsi. |
| 6 | Auth server | Belum ada endpoint data privat atau autentikasi. Jangan membuka layanan sebagai produk. |
| 7 | Otorisasi record | Menunggu skema, kepemilikan record dan autentikasi. |
| 8 | Field tampering | /health hanya GET dengan response schema tetap; mutasi domain belum tersedia. |
| 9 | Cookie sesi | Belum ada sesi. Implementasi nanti wajib HttpOnly, Secure, SameSite dan perlindungan CSRF. |
| 10 | Hash password | Belum menyimpan password pengguna. Credential PostgreSQL lokal bukan akun aplikasi. |
| 11 | Rate limit login | Belum ada login server. |
| 12 | Bot protection | Belum diterapkan; layanan hanya localhost. |
| 13 | Parameterized queries | Belum ada query aplikasi; tahap persistence wajib ORM/parameter terikat. |
| 14 | Validasi input | Endpoint health tanpa payload; skema domain belum tersedia. |
| 15 | XSS | Frontend baru hanya konten statis React, tanpa innerHTML. Prototipe lama belum diaudit tuntas. |
| 16 | Upload | Tidak ada endpoint upload. Belum ada malware scanner, penyimpanan terisolasi, atau ekstraksi. |
| 17 | Minimisasi respons | /health hanya status, service, stage. Tidak mengembalikan env/credential. |
| 18 | Security headers | nosniff, DENY, no-referrer; frontend juga Permissions-Policy dan CSP dasar. CSP belum membatasi script-src. |
| 19 | HTTPS | Belum ada domain/TLS. Localhost HTTP; HSTS hanya setelah HTTPS produksi siap. |
| 20 | Dependency scan | Lockfile serta audit npm/pip disiapkan di CI. Hasil lokal dilaporkan terpisah; audit bersifat waktu tertentu. |

## Gerbang sebelum produksi

Autentikasi akun yang dibuat admin, otorisasi tiap record, RLS dengan role database least privilege, validasi seluruh payload, log audit tanpa rahasia, rate limiting, penanganan upload, batas lisensi literatur, perlindungan prompt injection, TLS, backup terenkripsi yang telah diuji restore, serta tinjauan keamanan harus selesai. Tetapkan pengelolaan kunci dan penyedia layanan yang disetujui untuk NDA.

Referensi: [OWASP HTML5 Security](https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html), [File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html), [CSP](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html).

## Temuan dependency lokal — 31 Oktober 2026

Audit runtime Python dan npm produksi tidak melaporkan kerentanan dikenal. Audit npm lengkap masih memiliki 16 temuan sedang dalam rantai ESLint/minimatch; tidak ada temuan tinggi/kritis. Advisory: https://github.com/advisories/GHSA-g3hv-75wg-m249. Belum ada perbaikan kompatibel yang diterapkan. CI mengaudit seluruh dependency npm dengan ambang gagal high; temuan moderate tetap tercetak dan harus ditinjau. ESLint 9 juga mengeluarkan pemberitahuan akhir dukungan saat instalasi; migrasi lint perlu diuji bersama kompatibilitas plugin Next/React sebelum produksi.

## Perubahan setelah implementasi RAG lokal

Endpoint /api/rag kini menerima unggah PDF/TXT/MD maksimal 16 MB dan menyimpan teks ekstraksi di backend/data/rag.sqlite3 (diabaikan Git, belum terenkripsi). Ada batas input, cek ekstensi/signature PDF, konfirmasi hak penggunaan, penolakan origin/host non-localhost, parameterized SQL, dan pembatasan laju sederhana. Belum ada autentikasi organisasi, pemisahan pengguna/proyek, OCR, antivirus, sandbox parser, atau backup terenkripsi. Guard localhost bukan pengganti otorisasi. Ollama dikunci ke alamat loopback dengan trust_env=False. Validasi ID/kutipan tidak membuktikan entailment klaim. Lihat RAG.md sebelum penggunaan atau deployment.
