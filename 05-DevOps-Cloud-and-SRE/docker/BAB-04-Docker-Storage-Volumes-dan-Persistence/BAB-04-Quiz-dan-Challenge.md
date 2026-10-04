# BAB 04 — Quiz, Challenge, & Knowledge Check: Docker Storage & Persistence

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Jelaskan perbedaan mendasar antara Named Volume, Bind Mount, dan tmpfs Mount di Docker!
2. Mengapa menulis data transaksi database ke dalam layer reguler container (OverlayFS UpperDir) sangat dilarang di lingkungan produksi?
3. Di manakah lokasi direktori fisik default di host Linux tempat Docker menyimpan data Named Volume?
4. Apa keunggulan menggunakan sintaks modern `--mount` dibandingkan flag legacy `-v` atau `--volume`?
5. Apa yang terjadi pada data yang tersimpan di dalam `tmpfs` mount ketika container dihentikan (`docker stop`)?

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Jelaskan bagaimana pola *Ephemeral Helper Container* (menggunakan image `alpine` dengan `--rm`) bekerja untuk mem-backup data Named Volume ke file `.tar.gz` di host!
7. Mengapa saat melakukan backup volume, volume sumber sangat disarankan di-mount dengan mode *Read-Only* (`:ro`)?
8. Bagaimana Anda mengatasi masalah izin berkas (*permission denied*) saat menggunakan Bind Mount di Linux, di mana file yang dibuat oleh container dimiliki oleh `root` (UID 0)?
9. Apa yang dimaksud dengan *Dangling / Orphaned Volumes* di Docker, dan bagaimana cara membersihkannya secara aman?
10. Bagaimana pola *Multi-Container Shared Storage* memungkinkan arsitektur Producer-Consumer antara worker pemroses data dan web server publik?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Seorang administrator ingin memperbarui database PostgreSQL dari versi 14 ke versi 16 pada server yang sama. Database tersebut memiliki ukuran data sebesar 350GB. Jelaskan langkah demi langkah tercepat melakukan upgrade menggunakan Named Volume tanpa perlu menyalin atau mentransfer data lewat jaringan!
12. **Skenario 2**: Seorang developer frontend menggunakan Bind Mount di laptop macOS untuk me-mount folder project React ke container Docker. Namun, proses build dan rendering halaman web terasa sangat lambat (memakan waktu 15 detik untuk refresh). Jelaskan mengapa masalah performa ini terjadi di macOS/Windows dan optimasi apa yang dapat diterapkan!
13. **Skenario 3**: Sebuah aplikasi fintech menghasilkan token sesi JWT sementara yang hanya berlaku 5 menit. Jika token disimpan di disk fisik, terjadi pelanggaran kepatuhan PCI-DSS karena jejak file bisa dipulihkan dengan teknik forensik disk. Rancang konfigurasi storage Docker yang menjamin data sesi hanya tersimpan di memori RAM host tanpa pernah menyentuh harddisk!

---

## B. Practical Chapter Challenge: Automated Disaster Recovery Backup Pipeline

### Deskripsi Skenario
Rancang script otomatisasi pencadangan dan pemulihan bencana untuk container database transaksi e-commerce.

### Persyaratan Implementasi:
1. **Penyediaan Volume Produksi**:
   - Buat Named Volume bernama `ecommerce_prod_db`.
   - Simulasikan penulisan data transaksi penting ke dalam volume tersebut.
2. **Pola Backup Ephemeral Helper**:
   - Tulis perintah Docker yang memicu helper container Alpine untuk memampatkan isi volume menjadi file terkompresi `ecommerce_backup_$(date +%F).tar.gz` di folder `/backups` host.
   - Pastikan volume produksi dipasang dalam mode *Read-Only* (`:ro`).
   - Hitung nilai SHA256 checksum dari file arsip tersebut.
3. **Simulasi Disaster & Restore**:
   - Simulasikan kerusakan dengan menghapus volume asli `ecommerce_prod_db`.
   - Jalankan helper container baru untuk me-restore arsip `.tar.gz` ke dalam volume baru bernama `ecommerce_recovered_db`.
   - Verifikasi bahwa seluruh data kembali 100% utuh dengan checksum yang identik.
4. **Volume Hygiene**:
   - Bersihkan seluruh anonymous/dangling volume yang tidak lagi terikat pada container aktif.

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] 3 Tipe penyimpanan Docker: Named Volume, Bind Mount, tmpfs Mount.
- [ ] Dampak buruk Copy-on-Write (CoW) pada performa database transaksi tinggi.
- [ ] Pola Ephemeral Helper Container untuk Backup dan Restore volume.
- [ ] Masalah pemetaan UID/GID host vs container pada Bind Mount.
- [ ] Manajemen volume: `docker volume create`, `ls`, `inspect`, `rm`, `prune`.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh parameter plugin storage cloud vendor (AWS EBS CSI, GCP PD).
- [ ] Struktur heksadesimal file inode sistem operasi Linux.

### Saya Harus Bisa Melakukan:
- [ ] Memasang Named Volume dan Bind Mount menggunakan sintaks `--mount`.
- [ ] Menginjeksi file konfigurasi sensitif dengan mode `readonly`.
- [ ] Mengonfigurasi penyimpanan RAM disk menggunakan `tmpfs`.
- [ ] Mengeksekusi backup dan restore volume database menggunakan utilitas `tar`.

```text
Checklist Kesiapan BAB 04:
[ ] Memahami konsep Docker storage & persistensi
[ ] Menjalankan hands-on storage types simulator m01
[ ] Menjalankan hands-on volume backup & restore pipeline m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```
