# Status keamanan workspace lokal

Belum siap deployment publik. Status ini berlaku untuk aplikasi aktif baylab-figma.html dan FastAPI; index.html/demo.html merupakan prototipe lama yang tidak boleh memuat data rahasia.

| Kontrol checklist | Implementasi dan batas |
|---|---|
| 1?3 Rahasia/key | Tidak ada private API key frontend. .env dan backend/data diabaikan Git. Pengabaian Git tidak membuktikan histori bebas rahasia; audit histori menyeluruh belum dilakukan. Tidak memakai SDK DB publik. |
| 4,7 Otorisasi | Filter organisasi server pada record/model dan indeks RAG terpisah. SQLite tidak menyediakan kebijakan RLS native; isolasi diterapkan aplikasi. |
| 5 Enkripsi | Belum ada enkripsi disk/database atau backup otomatis. Operator perlu menyiapkan penyimpanan dan backup terenkripsi. |
| 6,9,10 Sesi | Sesi opaque server, token di-hash, password Argon2id. Cookie HttpOnly dan SameSite Strict; Secure diaktifkan dengan BAYLAB_SECURE_COOKIES=true saat HTTPS tersedia. CSRF wajib untuk mutasi. |
| 8,13,14 Payload/query | Skema Pydantic menolak field ekstra, memvalidasi rentang/nilai finite, ORM/query terparameterisasi. Peran dan organisasi diperiksa server. |
| 11,12 Rate limit | Login dibatasi per akun dan IP; RAG mempunyai guard laju. Belum ada CAPTCHA atau perlindungan bot terdistribusi. |
| 15 XSS | Konten workspace di-escape; pengujian browser mencakup nama kandidat berisi markup. Prototipe historis tidak termasuk jaminan ini. |
| 16 Upload | RAG membatasi PDF/TXT/MD 16 MB dan memeriksa tipe/signature. Belum ada antivirus atau sandbox parser. |
| 17 Respons | Tidak mengirim hash password, token sesi atau path artefak privat. ID record dipakai untuk operasi yang tetap memerlukan otorisasi. |
| 18 Headers | nosniff, DENY, no-referrer dan no-store API. Frontend memiliki CSP dasar; script-src belum ketat. |
| 19 HTTPS | Layanan loopback HTTP untuk pengembangan. TLS/HSTS dan redirect HTTPS produksi belum dikonfigurasi. |
| 20 Dependency | Lockfile dan pemeriksaan dependency tersedia. Hasil audit berlaku pada waktu pemeriksaan, bukan jaminan bebas kerentanan. |

Belum ada SSO/MFA, verifikasi email, reset email, manajemen kunci, pengujian restore backup atau audit keamanan independen. File initial-admin berisi kata sandi awal dalam plaintext untuk serah terima lokal; ganti kata sandi dan hapus file setelah dipindahkan ke penyimpanan aman. Database akun hanya menyimpan hash.

Ollama tetap loopback. Validasi kutipan RAG tidak membuktikan klaim benar secara ilmiah. Model native hanya dihasilkan server, tidak menerima unggahan pickle/model pengguna. Data pelatihan nyata merupakan pernyataan pengguna, belum diverifikasi laboratorium.

Audit npm terdahulu menemukan 16 kerentanan moderate pada rantai tooling ESLint/minimatch; tidak ada high/critical saat pemeriksaan tersebut. Periksa ulang sebelum rilis. Checklist ini bukan sertifikasi keamanan.
