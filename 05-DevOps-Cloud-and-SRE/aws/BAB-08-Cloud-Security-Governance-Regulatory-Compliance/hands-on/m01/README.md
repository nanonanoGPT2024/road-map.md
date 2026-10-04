# Hands-On Lab M01: Simulasi AWS KMS Envelope Encryption & Defense Mechanism

## Deskripsi Laboratorium
Pada lab praktika ini, Anda akan membedah dan mengeksekusi mekanisme internal kriptografi tingkat lanjut yang digunakan oleh AWS KMS dalam mengamankan data terproteksi (Personally Identifiable Information / Protected Health Information) menggunakan arsitektur **Envelope Encryption**.

Anda akan melihat secara langsung:
1. Pembuatan data key simetrik (AES-GCM-256) menggunakan KMS CMK.
2. Proses enkripsi payload di sisi lokal aplikasi.
3. Proses pembersihan memori (*zero-out memory buffer*) untuk mengeliminasi serangan *memory-dump*.
4. Peran krusial **Encryption Context (Additional Authenticated Data - AAD)** dalam menggagalkan upaya pembajakan data antar departemen/layanan.

---

## Prasyarat Lingkungan
- Mesin Linux / macOS / WSL2 (Windows).
- Python versi `3.9` atau lebih tinggi.
- Package manager `