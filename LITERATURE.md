# Basis literatur BAYLab — draft 2

Diperiksa pada **3 November 2026**. Sumber publik memungkinkan pengembangan dilanjutkan tanpa spreadsheet Pak Pugoh. Sumber ini tidak diklaim sebagai aturan R-01 sampai R-12 atau kasus acuan yang telah disahkan ahli.

## Katalog dan tingkat akses

| Sumber | Cakupan | Akses yang berhasil diperiksa |
| --- | --- | --- |
| [Evonik — Stability & Decomposition](https://www.evonik.com/en/company/businesslines/ao/products-and-services/hydrogen-peroxide/general-information/stability-and-decomposition.html) | Konteks stabilitas H2O2 | Halaman teknis produsen langsung |
| [Resul et al., 2018 — DOI 10.1039/C8RE00094H](https://eprints.ncl.ac.uk/252152) | Reaksi limonene berkatalis | Abstrak dan metadata repositori penulis |
| [Kern et al., 2014 — DOI 10.1002/ffj.3210](https://onlinelibrary.wiley.com/doi/10.1002/ffj.3210) | Matriks parfum hidroalkohol | Metode dan hasil artikel langsung |
| [Hu et al., 2015 — DOI 10.1039/C5RA02234G](https://pubs.rsc.org/en/content/articlelanding/2015/ra/c5ra02234g) | Aldehida, sistem berkatalis | Abstrak penerbit dalam hasil pencarian; akses langsung 403 |
| [Roberts et al., 2018 — DOI 10.1039/C8RE00085A](https://pubs.rsc.org/en/content/articlelanding/2018/re/c8re00085a) | Alkohol primer, sistem berkatalis | Abstrak penerbit dalam hasil pencarian; akses langsung 403 |
| [RSC Advances, 2019 — DOI 10.1039/C9RA02021G](https://pubs.rsc.org/en/content/articlehtml/2019/ra/c9ra02021g) | Fenol, sistem berkatalis | Cuplikan teks penerbit dalam hasil pencarian; akses langsung 403 |

Tidak ada klaim bahwa seluruh full text ditelaah. Belum dilakukan systematic review, penelusuran menyeluruh atas koreksi/retraksi, penilaian mutu oleh ahli, atau validasi terhadap produk LKPI. Tanggal pemeriksaan tidak diperbarui otomatis.

## Penerapan dalam aplikasi

`backend/app/chemistry/evidence.py` menyimpan metadata, temuan, kondisi, batas penerapan, tanggal pemeriksaan, dan cakupan akses. Pola SMARTS tetap hanya menghasilkan kecocokan struktur; tidak ada perubahan kategori risiko dari LLM atau dari keberadaan sitasi.

Di halaman screening, buka rincian sumber di bawah gugus yang cocok, konteks formulasi H2O2, atau tombol **Lihat sumber literatur**. Untuk pola ester dan peroksida belum ada bukti spesifik yang dipetakan. Panduan stabilitas H2O2 tetap konteks umum, tidak diterapkan otomatis pada peroksida organik.

RAG mengindeks enam **ringkasan asli BAYLab**, bukan salinan artikel. Setiap ringkasan mencantumkan sumber dan batas penerapan dalam satu potongan. Kutipan RAG mengutip ringkasan tersebut; URL/DOI dipakai untuk memeriksa publikasi asli. Dokumen baru berjudul `Catatan literatur draft - ...` agar tidak disalahartikan sebagai teks asli penelitian. Generasi jawaban tetap memerlukan Ollama yang siap.

```powershell
.\.venv\Scripts\python.exe scripts/ingest_literature.py
```

Pengindeksan konten yang sama tidak membuat duplikat. Jika catatan diubah, versi lama tidak dihapus otomatis; tinjau versi lama pada panel Dokumen.

## Yang masih perlu diperoleh dari mitra

Identitas dan spesifikasi bahan, komposisi atau batas kerahasiaan parfum, kadar/pH aktual, kondisi pencampuran dan penyimpanan, mutu air serta kemasan, fasilitas uji, dan kriteria penerimaan LKPI. Literatur tidak menggantikan parameter produk dan hasil laboratorium tersebut. Tidak ditetapkan ambang mutu atau resep bahan berdasarkan artikel katalisis.
