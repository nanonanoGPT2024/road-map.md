# Evaluasi Bab 04: Storage Subsystems & Data Lifecycle Management

Dokumen ini berisi rangkaian pengujian pemahaman konseptual, analisis arsitektural, dan tantangan implementasi teknis untuk menguji penguasaan materi subsistem penyimpanan AWS.

---

## 1. Basic Questions (5 Soal)

### Soal 1
Manakah pernyataan yang paling tepat mengenai karakteristik Amazon EBS `gp3` dibandingkan generasi pendahulunya `gp2`?
- [A] gp3 membutuhkan alokasi disk minimal 1 TB untuk mendapatkan performa 3,000 IOPS.
- [B] gp3 memisahkan provisi kapasitas penyimpanan (GB), IOPS, dan Throughput (MB/s) secara independen tanpa bergantung pada ukuran disk.
- [C] gp3 menggunakan mekanisme burst credit balance berbasis token seperti halnya gp2.
- [D] gp3 hanya dapat dipasang pada instans EC2 generasi lama berbasis Xen hypervisor.

### Soal 2
Berapa batasan minimum ukuran objek yang dikenakan biaya penagihan (*minimum billable size*) pada tier penyimpanan Amazon S3 Standard-Infrequent Access (S3 Standard-IA) dan S3 Glacier Instant Retrieval?
- [A] 0 KB (Dihitung persis per byte aktual).
- [B] 64 KB.
- [C] 128 KB.
- [D] 256 KB.

### Soal 3
Apa perbedaan teknis mendasar antara S3 Object Lock dalam **Governance Mode** vs **Compliance Mode**?
- [A] Governance Mode mengenkripsi data dengan KMS CMK, sedangkan Compliance Mode mengenkripsi data dengan SSE-S3.
- [B] Governance Mode mengizinkan user dengan hak akses khusus (`s3:BypassGovernanceRetention`) untuk membatalkan retensi atau menghapus objek, sedangkan Compliance Mode memblokir penghapusan oleh siapapun termasuk akun AWS Root.
- [C] Governance Mode hanya berlaku untuk S3 Standard, sedangkan Compliance Mode berlaku untuk semua tier S3 Glacier.
- [D] Compliance Mode memiliki masa kedaluwarsa maksimal 30 hari, sedangkan Governance Mode tidak terbatas.

### Soal 4
Tipe file system manakah yang aman dan didukung secara teknis untuk digunakan langsung pada volume Amazon EBS `io2` yang mengaktifkan fitur **Multi-Attach** ke beberapa Linux EC2 instance?
- [A] Standard `ext4`
- [B] Standard `xfs`
- [C] Cluster-aware filesystem seperti `GFS2` atau database clustered storage engine (misal Oracle ASM)
- [D] `NTFS`

### Soal 5
Layanan AWS Storage Gateway manakah yang menyediakan integrasi penyimpanan berbasis cloud dengan menyajikan antarmuka file share lokal (NFS/SMB) yang langsung memetakan file menjadi objek pada Amazon S3?
- [A] Tape Gateway
- [B] S3 File Gateway
- [C] Volume Gateway - Cached Volume
- [D] Volume Gateway - Stored Volume

---

## 2. Intermediate Questions (5 Soal)

### Soal 6
Sebuah aplikasi web containerized berjalan di Amazon EKS lintas 3 Availability Zone. Aplikasi membutuhkan shared storage berstatus Read-Write-Many (RWX) untuk menyimpan aset dokumen pengguna. Karakteristik I/O sangat acak (*spiky*) dan tidak dapat diprediksi. Opsi penyimpanan AWS manakah yang memberikan skalabilitas otomatis, kompatibilitas POSIX, dan efisiensi operasional terbaik tanpa risiko habisnya kredit performa?
- [A] Amazon EBS gp3 dengan Multi-Attach diaktifkan di seluruh AZ.
- [B] Amazon S3 di-mount menggunakan FUSE driver (s3fs).
- [C] Amazon EFS dengan Throughput Mode disetel ke *Elastic*.
- [D] Amazon FSx for Lustre dengan konfigurasi Scratch deployment.

### Soal 7
Sebuah bucket S3 memiliki Versioning aktif dan aturan Lifecycle Rule: "NoncurrentVersionTransition: 30 days to Glacier Flexible Retrieval, NoncurrentVersionExpiration: 365 days". Jika sebuah file bernama `config.json` di-overwrite setiap hari selama 40 hari, kondisi status versi objek manakah yang benar pada hari ke-41?
- [A] Bucket hanya memiliki 1 versi objek aktif di S3 Standard.
- [B] Bucket memiliki 1 versi aktif di S3 Standard, 9 versi tertua berada di S3 Glacier Flexible Retrieval, dan sisanya di S3 Standard.
- [C] Seluruh versi objek dipindahkan ke Glacier karena rule menghitung umur bucket.
- [D] Objek tidak bertransisi karena Lifecycle Rule hanya berlaku pada objek yang belum pernah ditimpa.

### Soal 8
Anda mendapati tagihan bulanan Amazon S3 membengkak signifikan meskipun jumlah objek yang terlihat di console AWS relatif sedikit. Setelah investigasi, ditemukan banyak proses upload file ukuran besar (>5 GB) melalui CLI/SDK yang terputus di tengah jalan karena timeout koneksi jaringan. Konfigurasi perbaikan apakah yang harus diterapkan pada S3 Lifecycle Rule untuk menghentikan kebocoran biaya ini secara permanen?
- [A] `AbortIncompleteMultipartUpload` dengan parameter `DaysAfterInitiation`.
- [B] `ExpiredObjectDeleteMarkers` bernilai `true`.
- [C] Mengubah Storage Class ke S3 Intelligent-Tiering.
- [D] Mengaktifkan S3 Transfer Acceleration.

### Soal 9
Sebuah tim data engineering membutuhkan high-performance shared file system untuk melatih model deep learning menggunakan kumpulan data training sebesar 50 TB yang tersimpan di Amazon S3. Sistem file harus mampu membaca dataset dengan throughput ratusan GB/s dan latensi sub-milidetik, serta menulis hasil checkpoint kembali ke S3. Solusi manakah yang paling tepat secara arsitektural?
- [A] Amazon EFS dengan Provisioned Throughput 1024 MB/s.
- [B] Amazon FSx for Lustre yang dikaitkan (*linked*) langsung ke bucket Amazon S3 sumber data.
- [C] Amazon EBS io2 Block Express 64 TB yang dipasang ke master node training.
- [D] AWS Storage Gateway Volume Gateway Cached mode.

### Soal 10
Administrator backup mengonfigurasi AWS Backup Vault Lock dengan parameter: `MinRetentionDays: 30`, `MaxRetentionDays: 365`, dan masa tenggang (*grace period*) 3 hari. Setelah 5 hari berlalu sejak Vault Lock berstatus `LOCKED`, penyerang siber berhasil mengompromikan kredensial Administrator AWS Root. Aksi apakah yang DAPAT dilakukan oleh penyerang tersebut terhadap vault tersebut?
- [A] Menghapus recovery point yang ada di dalam vault menggunakan API `DeleteRecoveryPoint`.
- [B] Menghapus konfigurasi Vault Lock dan menghapus vault seutuhnya.
- [C] Mengubah `MinRetentionDays` menjadi 1 hari untuk mempercepat kedaluwarsa.
- [D] Tidak ada satupun recovery point atau vault yang dapat dihapus atau dipersingkat retensinya hingga masa retensi berakhir.

---

## 3. Scenario-Based Questions (3 Kasus Industri)

### Kasus 1: Krisis Degradasi I/O Database Produksi
**Skenario**: Sistem basis data relasional PostgreSQL mission-critical perusahaan e-commerce mengalami lonjakan transaksi mendadak saat kampanye flash sale. Volume data database menggunakan EBS `gp3` dengan kapasitas 500 GB, 3,000 IOPS, dan 125 MB/s throughput. Tim SRE menerima alert P1 bahwa sistem mengalami I/O latency spike hingga 150ms (baseline <3ms), dan metrik CloudWatch `VolumeThroughputPercentage` mencapai 100%. Tim dilarang melakukan reboot server atau memutus koneksi database pelanggan.
- **Tugas Evaluasi**:
  1. Analisis akar masalah teknis dari degradasi tersebut.
  2. Rancang urutan langkah mitigasi langsung (*zero-downtime*) menggunakan AWS CLI untuk mengembalikan latensi database ke baseline.
  3. Identifikasi batas limitasi (*cooldown period*) dari fitur EBS Elastic Volumes yang harus diantisipasi tim pasca-perubahan.

### Kasus 2: Implementasi Kepatuhan Perbankan WORM & Multi-Region DR
**Skenario**: Bank Nasional perlu merancang penyimpanan laporan transaksi perbankan digital. Regulasi perbankan mewajibkan:
1. Rekam data transaksi harus disimpan secara non-rewritable and non-erasable (WORM) selama 10 tahun.
2. Data harus memiliki RPO (Recovery Point Objective) maksimal 15 menit dan RTO (Recovery Time Objective) maksimal 1 jam di region cadangan (Disaster Recovery) yang berjarak minimal 500 km.
3. Seluruh data saat transit maupun at-rest harus dienkripsi menggunakan kunci KMS yang dikelola sendiri oleh bank (*Customer Managed Key*), di mana kunci di Region Primary berbeda dengan Region Cadangan.
- **Tugas Evaluasi**:
  1. Rancang arsitektur penyimpanan Amazon S3 yang memenuhi seluruh aspek di atas.
  2. Jelaskan konfigurasi spesifik pada S3 Object Lock, S3 Replication Time Control (RTC), dan delegasi enkripsi KMS Cross-Region yang wajib dibuat.

### Kasus 3: Migrasi Storage File Server Enterprise Hybrid
**Skenario**: Perusahaan manufaktur memiliki file server lokal (on-premises) berbasis SMB sebesar 120 TB yang diakses oleh ribuan workstation desainer grafis dan engineer CAD. Kapasitas SAN lokal telah mencapai 95%. Perusahaan ingin memigrasikan penyimpanan ke AWS dengan kriteria:
1. Pengguna di kantor cabang tetap memerlukan akses latensi rendah lokal terhadap file-file proyek yang sedang aktif dikerjakan (hot data, sekitar 15 TB).
2. Data lama (cold data) harus ditampung di cloud storage berbiaya murah secara otomatis.
3. Harus tetap mempertahankan izin akses berbasis Windows Active Directory Domain Services (ACLs) yang sudah ada.
- **Tugas Evaluasi**:
  1. Tentukan subsistem penyimpanan AWS (atau kombinasi layanan) yang paling tepat untuk skenario ini.
  2. Jelaskan mekanisme sinkronisasi, caching lokal, dan alur proteksi data jangka panjangnya.

---

## 4. Practical Chapter Challenge: Arsitektur Multi-Tier Storage & Disaster Recovery Orkestrasi

### Deskripsi Tantangan
Anda ditunjuk sebagai Principal Infrastructure Architect untuk merancang arsitektur penyimpanan end-to-end bagi sebuah platform analitik kesehatan (*Healthcare Analytics Platform*). Platform ini mengolah data log telemetri medis pasien dan citra diagnostik (DICOM images).

### Batasan Arsitektur & Kebutuhan Teknis:
1. **Ingestion Layer**:
   - Puluhan microservices ingest mengunggah citra DICOM dan log secara serentak ke Amazon S3 Bucket `healthcare-ingest-primary` (Region: `ap-southeast-1`).
   - Setiap objek harus dilindungi dari modifikasi/penghapusan selama 5 tahun penuh menggunakan regulasi kepatuhan HIPAA/WORM.
2. **Lifecycle Optimization Layer**:
   - Hari 0–30: S3 Standard (Data sering dianalisis oleh pipeline AI).
   - Hari 31–90: Pindah ke S3 Glacier Instant Retrieval (Analisis retrospektif dokter).
   - Hari 91–1825 (Tahun ke-5): Pindah ke S3 Glacier Deep Archive (Kepatuhan audit rekam medis).
   - Setelah 1825 hari: Objek kedaluwarsa dan dihapus secara otomatis.
   - Sisa file incomplete multipart upload harus dihapus otomatis setelah 3 hari.
3. **Disaster Recovery Layer**:
   - Replikasi otomatis ke Region DR (`ap-southeast-3` Jakarta) menggunakan S3 Cross-Region Replication dengan Replication Time Control (RTC) untuk menjamin SLA replikasi < 15 menit.
   - Menggunakan KMS Customer Managed Key (CMK) independen di kedua region.
4. **App Worker Shared Scratch Space**:
   - Kelompok node komputasi worker di Amazon EKS membutuhkan file storage bersama (POSIX) untuk menampung cache rendering citra medis sementara.
   - Storage harus bersifat serverless tanpa memprovisi kapasitas GB di awal, mampu menahan beban burst throughput tinggi, dan otomatis mengarsipkan data cache yang tidak diakses dalam 7 hari ke Infrequent Access.

### Deliverables yang Harus Dibuat:
1. **Diagram Alur Topologi Penyimpanan (Format ASCII)**.
2. **Spesifikasi Terraform (.tf)** lengkap dan valid yang memprovisikan seluruh arsitektur S3 (Primary, DR, KMS Keys, IAM Roles, RTC Replication, Object Lock, Lifecycle) dan Amazon EFS (Elastic Throughput, EFS Lifecycle Policy).
3. **Runbook Operasional** singkat untuk tim SRE dalam menangani insiden kegagalan replikasi S3 dan pemantauan CloudWatch metrics storage.

---

## Kunci Jawaban & Panduan Evaluasi

### Bagian 1: Basic Questions
1. **[B]** - EBS gp3 memisahkan ukuran disk, IOPS, dan throughput secara independen tanpa bergantung pada kapasitas storage.
2. **[C]** - 128 KB adalah batas minimum penagihan ukuran objek untuk S3 Standard-IA dan S3 Glacier Instant Retrieval.
3. **[B]** - Governance Mode memungkinkan pengguna dengan permission bypass khusus untuk menghapus objek, sedangkan Compliance Mode memblokir semua pihak secara absolut hingga masa retensi habis.
4. **[C]** - EBS Multi-Attach memerlukan cluster-aware filesystem (seperti GFS2 atau Oracle ASM) untuk mengelola penulisan konkuren dan mencegah korupsi metadata disk.
5. **[B]** - S3 File Gateway mengekspos protokol standar NFS/SMB lokal dan menyimpannya secara 1:1 sebagai objek di S3.

### Bagian 2: Intermediate Questions
6. **[C]** - Amazon EFS mendukung multi-AZ POSIX access secara native dan mode Elastic Throughput otomatis beradaptasi dengan traffic spiky tanpa perlu manajemen kredit burst.
7. **[B]** - 1 versi aktif di S3 Standard (current), objek berumur $>30$ hari (hari 1 s.d. 9 noncurrent) bertransisi ke Glacier, sisanya (hari 10 s.d. 39 noncurrent) masih di S3 Standard.
8. **[A]** - `AbortIncompleteMultipartUpload` membersihkan partisi upload yang menggantung dan membatalkan penagihan kapasitas tersembunyi.
9. **[B]** - FSx for Lustre dirancang khusus untuk throughput masif ratusan GB/s dengan integrasi native bidirectional sync ke Amazon S3 data lake.
10. **[D]** - Sekali AWS Backup Vault Lock berada dalam kondisi `LOCKED` dan melewati masa tenggang (*grace period*), tidak ada satupun akun (termasuk AWS Root) yang dapat menghapus vault atau recovery point di dalamnya sebelum retensi habis.