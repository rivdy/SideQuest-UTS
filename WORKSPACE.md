# Workspace BAYLab AI lokal

Buka http://localhost:3000/baylab-figma.html#login setelah backend port 8000 dan frontend port 3000 berjalan (lihat DEVELOPMENT.md).

## Akun organisasi

Admin lokal telah dibuat: organisasi `lkpi`, email `admin@baylab.local`. Kata sandi acak ada hanya di `backend/data/initial-admin-lkpi.json`, bukan dalam dokumentasi atau Git. Setelah login, ganti kata sandi melalui Pengaturan; sesi lama dicabut. Hapus file kredensial awal setelah menyimpan kata sandi baru secara aman. Untuk instalasi baru jalankan `.venv/Scripts/python.exe scripts/bootstrap_admin.py` sekali. Skrip menolak menimpa admin lama.

Admin menambahkan akun organisasinya; formulator dapat mengolah formulasi, eksperimen dan model; viewer membaca data. Email adalah pengenal akun lokal, belum diverifikasi melalui email. Tidak ada SSO, MFA atau reset melalui email.

Database `backend/data/workspace.sqlite3` menyimpan akun, sesi, formulasi, eksperimen, metadata model dan audit. Artefak model ada di `backend/data/models/<organisasi>/`. Seluruh direktori data privat diabaikan Git. Cadangkan dengan akses terbatas; SQLite tidak otomatis terenkripsi.

## Peringkat kandidat

Buat formulasi dengan total komposisi 100%, lalu isi penilaian lima kriteria beserta sumber dan rasional: oksidasi, kelarutan, kompatibilitas, suhu dan aroma. Nilai adalah penilaian tim berbasis bukti, bukan prediksi kimia otomatis. Gunakan protokol pembandingan yang sama. Skor = jumlah(nilai kriteria ? bobot / 100); bobot harus berjumlah 100. Kriteria berbobot yang belum dinilai atau protokol tidak sesuai menghasilkan status belum lengkap tanpa peringkat. Kandidat nyata dan sintetis tidak boleh dicampur dalam satu pemeringkatan.

## Eksperimen dan pelatihan

Catat formulasi, batch, protokol, sumber, tanggal, pH, suhu, waktu, kadar awal/akhir H2O2, homogenitas dan aroma. Retensi dihitung sebagai kadar akhir / awal ? 100%. Catat juga kegagalan. Data nyata memerlukan konfirmasi pengguna; aplikasi tidak dapat membuktikan keaslian hasil lab. Arsip eksperimen tetap dicatat pada audit.

Menu Model ML menyediakan CatBoost dan XGBoost dengan dua target terpisah:

- Kelarutan air: memakai kolom measured log solubility dari CSV lokal dan sembilan deskriptor RDKit. Kolom prediksi ESOL tidak digunakan. Pemisahan train/test berdasarkan scaffold (molekul asiklik dikelompokkan memakai SMILES kanonik).
- Retensi H2O2: hanya eksperimen nyata terkonfirmasi dari organisasi dan protokol yang dipilih. Pembagian berdasarkan hash komposisi agar replikasi formula tidak bocor ke test. Data sintetis tidak memenuhi syarat.

Batas teknis minimal 12 baris dan 4 kelompok bukan bukti kecukupan ilmiah. Semua hasil tetap evaluation_only. Belum ada validasi eksternal, cross-validation, optimasi Bayesian atau prediksi keamanan/efikasi. Model kelarutan tidak memprediksi stabilitas disinfektan beraroma.

Dua pelatihan aktual dari 1.128 baris CSV: 928 train, 200 test, 584 kelompok total, tanpa tumpang tindih kelompok. CatBoost: MAE 0,4767, RMSE 0,6242, R? 0,8955. XGBoost: MAE 0,4576, RMSE 0,6263, R? 0,8948. MAE baseline rerata: 1,5630. Satuan error mengikuti log kelarutan dataset. R? bukan persentase akurasi. Grafik menampilkan hasil holdout aktual; metrik ini hanya satu pembagian data dan bukan jaminan generalisasi.

Belum ada eksperimen LKPI nyata yang dimasukkan; pelatihan retensi akan diblokir sampai data memenuhi syarat. Lihat DATASET_REVIEW.md untuk batas sumber.

## Pemeriksaan

- `.venv/Scripts/python.exe -m pytest backend/tests -q`: 62 tes backend lulus.
- Jalankan `scripts/qa_workspace_server.py`, kemudian `node qa-workspace.mjs`: 15 pemeriksaan browser lulus menggunakan database QA terpisah; bukan data lab nyata.
- Laporan lokal: `qa/workspace-browser-report.json`, `qa/workspace-training-report.json`.

Skrip check_rag_live.py dan check_rag_frontend.py memakai kredensial privat lokal atau BAYLAB_CREDENTIALS_FILE. Setelah kata sandi diganti, sediakan file privat dengan organization, email, password yang berlaku. Jangan commit file tersebut.
