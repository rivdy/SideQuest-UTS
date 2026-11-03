## Pembaruan 3 November 2026

Enam sumber publik telah dihubungkan ke screening dan diindeks sebagai catatan literatur draft dalam RAG lokal. Kondisi studi dan batas penerapan ikut ditampilkan; tidak mengubah status validasi ahli. Lihat [LITERATURE.md](LITERATURE.md).

Screening RDKit + PubChem live tersedia di http://localhost:3000/baylab-figma.html#screening. Semua aturan masih draft. Panduan dan hasil pengujian: [CHEMISTRY.md](CHEMISTRY.md).

# Halaman utama terbaru

Buka http://localhost:3000 untuk landing dari file landing.html yang diberikan pengguna. Semua tombol Coba demo menuju /baylab-figma.html (login dan dashboard sesuai file Figma). Tiga screenshot berada di frontend/public/screens. Three.js, GSAP, ScrollTrigger, dan Google Fonts pada landing masih dimuat dari CDN seperti pada sumber; animasi lengkap memerlukan internet.

File sumber aktif: frontend/public/landing.html dan frontend/public/baylab-figma.html. Next.js memetakan / ke landing.html melalui beforeFiles rewrite. File index.html dan /demo.html tetap menyimpan prototipe terdahulu. Jangan memakai scripts/sync-login.mjs untuk memperbarui landing Figma; script itu hanya untuk login prototipe terdahulu.

Validasi integrasi: lint, production build, smoke HTTP, dan 10 pemeriksaan browser lulus, termasuk WebGL, library animasi, screenshot, layout ponsel, mini screening, login, serta dashboard. Ulangi dengan node qa-landing.mjs saat server berjalan di port 3000.

# Pengembangan bertahap

Fondasi aplikasi server tersedia di frontend/ dan backend/. Lihat [DEVELOPMENT.md](DEVELOPMENT.md) untuk menjalankan dan [SECURITY.md](SECURITY.md) untuk status 20 kontrol keamanan. Server RAG dan screening struktur telah ditambahkan; sebagian uraian di bawah membahas prototipe HTML sebelumnya. Status terkini ada pada Batas implementasi.

# BAYLab AI

Website lokal dalam satu index.html, mengikuti desain BAYLab AI di ZIP. Buka index.html di Chrome/Edge, lalu pilih **Masuk dengan akun demo**. Tidak memerlukan instalasi atau build. Google Fonts menggunakan internet; fungsi lokal tetap tersedia tanpa font tersebut.

## Modul yang terintegrasi

1. **Knowledge Screening** — tambah nama/CAS senyawa, jalankan pemetaan gugus dari katalog terkurasi, lihat aturan yang terpicu, alasan, dan sumber. Nama yang belum dikenal ditandai Belum diketahui. Kadar/pH disimpan sebagai konteks, belum memengaruhi klasifikasi.
2. **Literatur** — sembilan sumber primer/struktur/paten, ringkasan, batas penerapan, pencarian lokal, dan ekspor daftar sumber.
3. **Rekonstruksi & Substitusi** — tabel senyawa asal → risiko → kandidat → rasionalisasi. Memilih usulan memperbarui identitas komponen F-01. Dihydromyrcenol tetap ditandai C=C; tidak ada klaim bahwa kelas alkohol/ester otomatis stabil.
4. **Chat** — menelusuri catatan lokal melalui kata kunci, menampilkan sumber relevan, dan menyatakan saat tidak menemukan catatan. Bukan layanan LLM/RAG langsung.
5. **Dataset Simulasi** — 10 baris sintetis dalam rentang prompt 15–25% H₂O₂, dengan kadar akhir dan label yang dihitung ulang. Kadar ini bukan rekomendasi penggunaan produk. Data dapat diedit serta diekspor sebagai CSV atau tabel Markdown.
6. **Pitching Demo Day** — naskah 391 kata, indikator target proposal, timer mulai/jeda/reset selama 3 menit, dan unduhan naskah.

Alur dashboard, formulasi, rekomendasi, evaluasi eksperimen, Library Bahan, serta pengaturan tetap tersedia. Dua menu baru adalah Dataset Simulasi dan Pitching Demo Day.

## Dataset dan label

Retensi = kadar akhir / kadar awal × 100%.

- Lolos: retensi ≥90% dan jernih.
- Gagal: retensi <80%, keruh, atau pemisahan fase.
- Perlu tinjauan: 80–<90% dan jernih.

Kriteria adalah asumsi MVP, bukan standar produk tervalidasi. Semua baris ekspor memiliki Data_Origin=synthetic dan Eligible_For_Training=false. Dataset sintetis terpisah dari state.results dan tidak menambah data latih. Nilai sintetis menguji logika aplikasi, bukan hubungan ilmiah antar bahan.

## Batas implementasi terkini

Aplikasi aktif di localhost:3000 sudah memiliki server FastAPI, RAG lokal berbasis dokumen, serta screening RDKit dan PubChem live. Lihat [CHEMISTRY.md](CHEMISTRY.md) dan [RAG.md](RAG.md).

- Screening pada baylab-figma.html#screening dihitung dari SMILES input, bukan metadata gugus tetap. SMARTS benar-benar dijalankan oleh RDKit. Enam pola berstatus draft; bukan aturan LKPI R-01 sampai R-12 dan belum menghasilkan kesimpulan risiko/kompatibilitas.
- PubChem diakses saat diminta pengguna, dengan URL sumber dan waktu pengambilan. Rujukan ilmiah lama tidak otomatis diverifikasi ulang oleh pencarian identitas ini.
- RAG menelusuri dokumen lokal. Jawaban generatif memerlukan model Ollama tersedia; tanpa model, UI hanya menampilkan hasil retrieval. Status model harus diperiksa saat menjalankan aplikasi.
- Autentikasi organisasi belum tersedia. Login dan profil aplikasi masih demo. Skor kandidat serta grafik ML lama tetap ilustrasi; belum ada pelatihan CatBoost/XGBoost maupun pemeringkatan ulang berbasis formulasi.
- Spreadsheet aturan ahli, 20 kasus acuan, serta data eksperimen nyata belum tersedia. Validasi risiko dan kelayakan model tidak dapat digantikan dengan data buatan.

Batas prototipe lama: index.html dan demo.html masih menggunakan metadata terkurasi serta localStorage, dan bukan antarmuka screening server. Jangan gunakan akun asli atau data rahasia pada bagian demo. Screening baru menyimpan input/hasil hanya dalam memori halaman; dokumen RAG disimpan di backend/data yang diabaikan Git.

Metrik pitching — 35%, Rp140 juta/tahun, 12 ke 8 bulan, dan TKT 2 ke 4 — ditulis sebagai target proposal, bukan hasil yang telah dicapai.

## Pengujian

Jalankan node qa.mjs untuk alur utama, dan node qa-modules.mjs untuk modul integrasi. Keduanya memakai Chrome headless dengan profil khusus di qa/chrome-profile dan tidak menyentuh profil browser utama. Hasil ada di qa/report.json serta qa/modules-report.json. Screenshot tersimpan di qa/.

references/ memuat gambar asli ZIP. soda-backup.html menyimpan halaman awal; baylab-before-modules.html menyimpan versi BAYLab sebelum integrasi modul.


## Login animasi bergaya Soda

Login kini memakai identitas BAYLab dengan latar violet/teal, botol laboratorium berbasis CSS, molekul melayang, partikel, parallax pointer, serta tombol jeda. Pengaturan prefers-reduced-motion menonaktifkan animasi. Tidak menambahkan library animasi atau aset 3D eksternal.

Buka index.html untuk mencoba langsung. Versi Next.js ada di frontend/src/app/page.tsx; tombol Jelajahi demo membuka public/demo.html yang berisi prototipe lama. Autentikasi organisasi belum terhubung; form tidak mengirim atau menyimpan password.

Setelah mengubah komponen login atau login.css, jalankan node scripts/sync-login.mjs dari root untuk menyamakan versi HTML dan salinan demo. Setelah itu build ulang frontend. Pengujian login: node qa-login.mjs (memerlukan server frontend lokal pada port 3318). Hasil terbaru: 24 pemeriksaan browser lolos untuk versi HTML dan Next.js, termasuk viewport 320/390/768 px. Screenshot ada di qa/login-soda-*.png.

## Koleksi parfum pada login

Visual login diperbarui menjadi tiga botol parfum: Citrus Lemon, Green Bergamot, dan Soft Lavender. Irisan citrus, lemon utuh, daun, serta lavender memiliki gerakan independen. Semua ilustrasi dibuat sebagai CSS/SVG lokal untuk identitas BAYLab; bukan foto produk yang diunduh atau produk parfum siap jual. Tema aroma tidak menyatakan kompatibilitas dengan H2O2.

Referensi internet untuk arah visual dan bahan aroma:
- LabSolue 101 Bergamotto: https://labsolueperfume.com/en/products/101-bergamotto-eau-de-parfum
- Presentasi botol dengan lemon, bergamot, dan lavender: https://www.intenseoud.com/products/rome-imagine-eau-de-parfum-spray-100ml-3-4-oz-by-mast-perfume

Validasi setelah perubahan: lint dan build lulus; 28 pemeriksaan browser lulus pada versi HTML dan Next.js, termasuk tiga botol, enam elemen bahan, kontrol animasi, form, demo, serta ukuran 320/390/768 px.

## Adaptasi template KIMI

Login memakai permukaan terang, tipografi condensed, aksen ungu/teal, panel bersudut, kontur Canvas, scan line, floating botanical, dan spring reveal. Hero mengecil saat panel riset menutupinya pada desktop. Bagian tambahan menampilkan jalur riset yang digambar selama enam detik dan tiga kartu karakter aroma. Ini adaptasi visual BAYLab, bukan replika aset pembalap, shader helm, atau keseluruhan situs KIMI.

Animasi menggunakan satu requestAnimationFrame dengan cleanup saat login ditinggalkan; pause dan prefers-reduced-motion didukung. Canvas dan SVG dibuat lokal, tanpa tambahan dependensi WebGL. Template sumber: lampiran pengguna 8ea1c099-bc42-4190-9da9-7d44aa756d7d/Pasted text.txt.

Validasi adaptasi: lint, production build, smoke HTTP, dan 32 pemeriksaan browser lulus. Pengujian mencakup HTML tunggal serta Next.js, ukuran 320/390/768 px, form, demo, pause, koleksi parfum, dan jalur riset. Autentikasi organisasi tetap belum terhubung.

## RAG lokal

Chat AI pada aplikasi Figma kini menggunakan indeks dokumen lokal dan adapter Ollama. Panduan instalasi, batas keamanan, sumber awal, serta cara menjalankan tersedia di [RAG.md](RAG.md). Model harus selesai diunduh agar mode jawaban generatif aktif; statusnya diperlihatkan di UI. Tanpa model, hasil hanya berupa kutipan sumber hasil pencarian.
