# Module 02: Volume Backup, Restore, Migration, & Multi-Container Shared Storage

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Menguasai pola standar industri **Volume Backup** menggunakan *ephemeral helper container*.
- Melakukan proses **Restore** data ke Named Volume baru dan memvalidasi integritas data (*checksum*).
- Menjalankan migrasi volume database antar-server fisik/cloud host yang berbeda.
- Mengimplementasikan pola **Multi-Container Shared Storage** (*Producer-Consumer Pattern*).
- Memahami konsep **Docker Volume Drivers** (NFS, AWS EFS, GlusterFS) untuk penyimpanan terdistribusi.
- Mengidentifikasi dan membersihkan volume yatim piatu (*dangling/orphaned volumes*) dengan aman.

---

## 2. Prerequisite
- Memahami konsep dasar Named Volumes dan mount points (BAB 04 Module 01).
- Mengetahui penggunaan perintah pengarsipan Linux: `tar`, `gzip`, dan kalkulasi `sha256sum`.
- Pemahaman dasar tentang protokol transfer file jaringan (`scp`, `rsync`).

---

## 3. Concept
Meskipun Named Volume tersimpan di direktori host (`/var/lib/docker/volumes/`), memanipulasi file di direktori tersebut secara langsung sangat tidak disarankan karena masalah izin akses (*file permissions*) dan risiko korupsi metadata Docker.

Pola standar industri Docker untuk mengelola backup dan restore adalah menggunakan **Ephemeral Helper Container** (container sementara yang langsung hancur setelah tugas selesai via flag `--rm`). Helper container ini me-mount volume data dalam mode *read-only* (`:ro`) bersamaan dengan folder backup host, lalu mengeksekusi utilitas arsip standar Linux (`tar` / `gzip`).

```
       DOCKER VOLUME BACKUP ARCHITECTURE (HELPER PATTERN)
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ HOST MACHINE                                                                │
 │                                                                             │
 │  ┌─────────────────────────────┐         ┌───────────────────────────────┐  │
 │  │ NAMED VOLUME: db_data       │         │ HOST BACKUP DIRECTORY         │  │
 │  │ (/var/lib/docker/volumes/..)│         │ /home/backup/                 │  │
 │  └──────────────┬──────────────┘         └───────────────▲───────────────┘  │
 │                 │                                        │                  │
 │                 │ Mount :ro                              │ Mount :rw        │
 │                 ▼                                        │                  │
 │  ┌───────────────────────────────────────────────────────┴───────────────┐  │
 │  │ EPHEMERAL HELPER CONTAINER (alpine:latest with --rm)                  │  │
 │  │  Command: tar -czvf /backup/db_backup.tar.gz -C /data .               │  │
 │  └───────────────────────────────────────────────────────────────────────┘  │
 │                                                                             │
 │  Output on Host: /home/backup/db_backup.tar.gz (Ready for S3 upload)        │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Why?
1. **Disaster Recovery & Ransomware Protection**: Jika server terkena malware atau harddisk rusak, Anda memiliki salinan arsip terkompresi di luar server (misal di AWS S3 atau NAS lokal).
2. **Migrasi Antar-Server Tanpa Downtime Lama**: Memindahkan beban kerja dari server on-premise ke cloud provider dilakukan dengan mem-backup volume, mentransfer file arsip `.tar.gz`, dan me-restore-nya ke cluster target.
3. **Kolaborasi Antar-Layanan Tanpa Overhead Jaringan**: Layanan pemroses video (*Worker*) dapat menyimpan file output hasil render ke shared volume, sementara web server Nginx dapat langsung membaca dan menyajikannya ke pengguna publik tanpa perlu mentransfer file via HTTP API internal.

---

## 5. What?
### Komponen & Perintah Kunci:
- **Pola Backup**:
  `docker run --rm -v <volume_name>:/data:ro -v $(pwd):/backup alpine tar -czvf /backup/backup.tar.gz -C /data .`
- **Pola Restore**:
  `docker run --rm -v <new_volume_name>:/data -v $(pwd):/backup alpine tar -xzvf /backup/backup.tar.gz -C /data`
- **Pola Multi-Container Sharing**:
  Dua container me-mount volume yang sama: Container A bertindak sebagai *Writer/Producer*, Container B bertindak sebagai *Reader/Consumer* (disarankan dipasang `:ro`).
- **Pembersihan Volume**:
  - `docker volume ls -f dangling=true`: Menemukan volume yang tidak lagi terhubung ke container manapun.
  - `docker volume prune -f`: Menghapus seluruh dangling volume untuk membebaskan ruang disk.

---

## 6. How?
Alur Kerja Penuh Backup dan Restore Volume:
1. **Quiesce Database**: Hentikan sementara penulisan ke database (atau gunakan perintah `docker stop` sebentar) agar file database dalam kondisi konsisten (*clean state*).
2. **Jalankan Backup Helper**: Eksekusi perintah `tar` di dalam container Alpine sementara.
3. **Hitung Checksum**: Hitung hash file backup (`sha256sum backup.tar.gz`) untuk memverifikasi integritas.
4. **Transfer File**: Kirim file `.tar.gz` ke server tujuan menggunakan `rsync` atau `aws s3 cp`.
5. **Jalankan Restore Helper**: Buat Named Volume baru di server tujuan, lalu ekstrak isi file tar ke volume baru tersebut.
6. **Nyalakan Aplikasi**: Jalankan container aplikasi dan arahkan ke volume yang baru di-restore.

---

## 7. Analogy
Bayangkan **Volume Backup via Helper Container** seperti **Jasa Pindahan Rumah Profesional**:
- Lemari dan perabot Anda di dalam rumah adalah **Named Volume**.
- Anda tidak perlu memanggil arsitek gedung atau merusak pondasi rumah (**Tidak mengutak-atik `/var/lib/docker/` langsung**).
- Anda menyewa satu truk kargo sewaan yang datang 1 jam (**Ephemeral Helper Container**).
- Karyawan truk membungkus perabot Anda ke dalam kardus kardus rapi (**`tar.gz` archive**), membawanya ke luar pagar (**Host Directory**), lalu truk sewaan tersebut langsung pergi pamit (**`--rm` destroy**).

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               MULTI-CONTAINER SHARED STORAGE (PRODUCER - CONSUMER)                |
+-----------------------------------------------------------------------------------+

 ┌──────────────────────────────────┐         ┌──────────────────────────────────┐
 │ PRODUCER CONTAINER               │         │ CONSUMER CONTAINER               │
 │ (Report Generation Worker)       │         │ (Public Nginx Web Server)        │
 │                                  │         │                                  │
 │ Generates PDF invoices every 1h: │         │ Reads and serves static PDF:     │
 │ /shared/reports/invoice_001.pdf  │         │ /usr/share/nginx/html/reports/   │
 └─────────────────┬────────────────┘         └─────────────────▲────────────────┘
                   │                                            │
                   │ Mount :rw                                  │ Mount :ro (Safety)
                   ▼                                            │
 ┌──────────────────────────────────────────────────────────────┴────────────────┐
 │ SHARED NAMED VOLUME: reports_storage                                          │
 │ (High-performance shared I/O directly on Host Filesystem)                     │
 └───────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Simple Example: Skrip Otomasi Backup Volume
Perintah satu baris untuk mem-backup volume `my_app_data` menjadi file `my_app_data_backup.tar.gz`:

```bash
# 1. Mengeksekusi backup aman (mode read-only pada source volume)
docker run --rm \
  -v my_app_data:/source_data:ro \
  -v "$(pwd)/backups":/backup_target \
  alpine \
  tar -czvf /backup_target/my_app_data_$(date +%Y%m%d).tar.gz -C /source_data .

# 2. Memeriksa file hasil backup di host
ls -lh ./backups/
```

---

## 10. Practical Example: Skrip Otomasi Restore ke Volume Baru
Mengembalikan data cadangan ke Named Volume baru bernama `my_app_data_restored`:

```bash
# 1. Membuat volume baru
docker volume create my_app_data_restored

# 2. Mengekstrak file tarball ke dalam volume baru
docker run --rm \
  -v my_app_data_restored:/target_data \
  -v "$(pwd)/backups":/backup_source \
  alpine \
  tar -xzvf /backup_source/my_app_data_20260911.tar.gz -C /target_data

# 3. Memverifikasi isi volume baru
docker run --rm -v my_app_data_restored:/data alpine ls -la /data
```

---

## 11. Real World Example: Migrasi Zero-Downtime Media Storage E-Commerce
Sebuah toko online memiliki 200GB foto produk di dalam Docker Named Volume di penyedia VPS lama:
- **Masalah**: Harus migrasi ke server baru di AWS tanpa menghentikan penjualan.
- **Implementasi**:
  1. *Fase 1*: Tim menjalankan skrip helper backup parsial saat jam sepi traffic (pukul 02:00 pagi) dan melakukan sync ke AWS S3 via CLI.
  2. *Fase 2*: Di server AWS EKS baru, Named Volume dibuat menggunakan driver **AWS EFS (Elastic File System)**, memungkinkan ratusan pod membaca dan menulis katalog foto secara terdistribusi.
  3. *Fase 3*: Helper container di AWS mengekstrak data dari S3 ke volume EFS.
  4. *Fase 4*: DNS dialihkan ke server baru.
- **Hasil**: Migrasi 200GB data selesai dengan lancar tanpa ada link gambar produk yang rusak (*broken images*).

---

## 12. Trade-offs

| Aspek | Backup File Level (tar via Helper) | Backup Blok Storage Host (LVM/EBS Snapshot) |
|---|---|---|
| **Portabilitas Antar-OS** | Sangat Tinggi (Bisa restore ke macOS, Ubuntu, RHEL) | Terikat pada vendor cloud/tipe filesystem host |
| **Kebutuhan Tool Eksternal** | Nol (Hanya butuh Docker Engine & image Alpine) | Butuh CLI AWS/Cloud Provider atau hak akses root OS |
| **Kecepatan Backup Data Raksasa (>1TB)**| Sedang-Lambat (CPU terbebani kompresi gzip) | Instan (Snapshot blok disk dalam hitungan detik) |
| **Granularitas Restore** | Fleksibel (Bisa ekstrak satu file spesifik) | Kaku (Harus me-restore seluruh partisi disk) |

---

## 13. When To Use
- Rutinitas pencadangan terjadwal harian (Cron) untuk container database dan file upload.
- Membagikan direktori aset statis antara build container dan web server container.
- Melakukan replikasi data staging dari snapshot produksi untuk pengujian bug.

---

## 14. When NOT To Use
- Jangan mem-backup database aktif berkapasitas ratusan gigabyte hanya dengan `tar` saat database sedang menerima jutaan penulisan write intensif tanpa locking, karena file data bisa berstatus *torn page / corrupt*. Gunakan utilitas dump native database terlebih dahulu (`pg_dump`, `mysqldump`) atau pause database sesaat.

---

## 15. Common Mistakes
1. **Lupa Memberikan Flag `:ro` pada Source Volume saat Backup**: Me-mount volume sumber dalam mode read-write. Jika script backup tidak sengaja melakukan perintah modifikasi, data produksi dapat rusak. Selalu gunakan `-v my_vol:/data:ro`.
2. **Menumpuk Dangling Volumes**: Menghapus container berulang kali tanpa flag `-v`. Ratusan anonymous volume yang tidak terikat menumpuk di `/var/lib/docker/volumes/` dan menghabiskan 80% kuota disk server.
3. **Mengabaikan Path Root Archive pada Tar**: Menjalankan `tar -czvf /backup.tar.gz /data` alih-alih menggunakan opsi `-C /data .`. Hal ini menyebabkan saat di-restore, file akan diekstrak ke dalam subfolder bersarang `/data/data/...`.

---

## 16. Best Practices
### Must Have
- Jalankan proses backup dengan me-mount volume sumber dalam mode **Read-Only (`:ro`)**.
- Gunakan flag `--rm` pada helper container agar container sementara langsung terhapus setelah proses kompresi selesai.
- Uji coba proses **Restore** secara berkala (minimal sebulan sekali) ke cluster staging untuk membuktikan bahwa file backup tidak korup.

### Recommended
- Sertakan stempel waktu tanggal pada nama file backup: `$(date +%Y%m%d_%H%M%S).tar.gz`.
- Pasang cron job pembersihan volume yatim piatu mingguan: `docker volume prune -f`.

### Advanced
- Gabungkan backup helper container dengan enkripsi GPG simetris (`gpg -c`) sebelum mengunggah file tarball ke public cloud storage.

---

## 17. Troubleshooting
- **Masalah**: File backup berukuran sangat kecil (hanya beberapa byte) dan saat di-restore kosong.
  - *Penyebab*: Kesalahan path direktori di dalam container helper (misal salah ketik `/data` menjadi `/data/`).
  - *Solusi*: Uji perintah `ls` di dalam helper container terlebih dahulu sebelum mengeksekusi `tar`.
- **Masalah**: `docker volume prune` menolak menghapus volume: `volume is in use`.
  - *Penyebab*: Masih ada container dalam status *Exited* yang mereferensikan volume tersebut.
  - *Solusi*: Bersihkan container yang sudah mati terlebih dahulu dengan `docker container prune -f`.

---

## 18. Exercise
1. Buat Named Volume bernama `website_assets`. Tulis 3 file dummy ke dalamnya. Gunakan helper container untuk membuat file cadangan `website_assets.tar.gz` di folder lokal host Anda!
2. Hapus volume `website_assets`, buat volume baru `website_assets_v2`, dan lakukan restore dari file arsip sebelumnya. Verifikasi integritas isi filenya!

---

## 19. Challenge
Rancang pipeline pencadangan otomatis (Automated Backup Runner):
- Tulis script shell/Node.js yang:
  1. Menemukan seluruh volume yang memiliki label `backup=daily`.
  2. Mem-backup masing-masing volume ke file `.tar.gz` berstempel waktu.
  3. Menghitung nilai SHA256 checksum untuk setiap arsip.
  4. Menghapus file backup lokal yang berusia lebih dari 7 hari (*retention policy*).

---

## 20. Summary
- Pola **Ephemeral Helper Container** adalah metode paling portabel, aman, dan standar untuk melakukan backup dan restore volume Docker.
- Selalu mount volume sumber dengan hak akses **Read-Only (`:ro`)** selama proses pencadangan.
- **Shared Storage** memungkinkan kolaborasi performa tinggi antara container Producer dan Consumer tanpa dependensi jaringan.
- Kebersihan disk harus dijaga dengan memonitor dan membersihkan *dangling volumes* secara teratur.
