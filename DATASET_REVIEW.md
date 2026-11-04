# Peninjauan dataset untuk BAYLab AI

Ditinjau pada pengembangan 4 November 2026. Kesesuaian target lebih penting daripada ukuran dataset. Tidak ada sumber berikut yang menyediakan hasil stabilitas formula H2O2-parfum LKPI.

| Sumber | Isi dan penggunaan |
|---|---|
| data/aqueous solubility dataset.csv | 1.128 baris, SMILES dan measured log solubility. Dipakai untuk pelatihan eksploratif kelarutan air; sumber asli, lisensi dan kesetaraan persis dengan ESOL belum diaudit. |
| data/fra_cleaned.csv | 24.063 baris metadata parfum, cp1252, delimiter titik koma. Bukan target laboratorium dan tidak dipakai melatih model. |
| data/fra_perfumes.csv | 70.103 baris metadata/rating parfum. Bukan hasil uji stabilitas dan tidak dipakai melatih model. |
| [Listeria QAC tolerance WGS](https://huggingface.co/datasets/food-ai-nexus/listeria-qac-tolerance-wgs) | Toleransi QAC pada isolat Listeria, bukan oksidasi parfum atau stabilitas H2O2. Kartu mencantumkan CC BY 4.0. Tidak diimpor. |
| [PubChemWikiPairClassification](https://huggingface.co/datasets/mteb/PubChemWikiPairClassification) | Pasangan kalimat dan label pencocokan semantik, bukan label kompatibilitas kimia. CC BY-NC-SA 4.0 perlu diperhatikan untuk penggunaan komersial. Tidak diimpor. |
| [ComplianceKnowledgeBase](https://huggingface.co/datasets/carehomecleaning/ComplianceKnowledgeBase) | Saat ditinjau belum menyediakan data; kartu membahas kepatuhan care home Inggris. Bukan sumber primer regulasi Indonesia. Tidak diimpor. |

[Publikasi ESOL](https://pubs.acs.org/doi/10.1021/ci034243x) menjelaskan target kelarutan air; kemiripan format tidak membuktikan asal-usul CSV lokal. Model memanfaatkan nilai terukur, bukan kolom prediksi ESOL. Hash dataset tercatat bersama setiap run, untuk melacak file yang digunakan, bukan membuktikan validitas ilmiah atau lisensi.

Executive Summary.pdf diperlakukan sebagai dokumen draft yang perlu verifikasi sumber. Token sitasi yang tidak dapat diselesaikan dan batas dari konteks kosmetik tidak otomatis dijadikan aturan produk disinfektan. Penetapan ambang kelulusan, protokol stabilitas dan efikasi tetap memerlukan persetujuan ahli/mitra dan bukti primer.
