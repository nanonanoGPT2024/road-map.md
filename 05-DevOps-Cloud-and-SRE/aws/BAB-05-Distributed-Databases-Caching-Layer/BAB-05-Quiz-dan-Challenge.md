# Bab 05: Evaluasi Pembelajaran - Distributed Databases & Caching Layer

Dokumen ini berisi pengujian pemahaman konsep teknis, analisis arsitektur, dan penugasan implementasi mendalam terkait basis data terdistribusi dan caching pada platform Amazon Web Services (AWS).

---

## 1. Basic Questions (5 Soal)

### Soal 1
Apa perbedaan mendasar antara mekanisme replikasi Amazon RDS Multi-AZ Standby Deployment standar dengan Amazon RDS Read Replica?
- A. Multi-AZ menggunakan logical binlog replication; Read Replica menggunakan physical block-level storage replication.
- B. Multi-AZ menggunakan synchronous physical block replication; Read Replica menggunakan asynchronous logical replication engine.
- C. Multi-AZ dapat diakses oleh client untuk read-only; Read Replica tidak dapat diakses sama sekali.
- D. Multi-AZ mendukung replikasi lintas region; Read Replica hanya dapat dibuat di dalam Availability Zone yang sama.

### Soal 2
Berapa quorum data write dan data read yang digunakan oleh distributed storage engine Amazon Aurora dalam satu Region (6 salinan data di 3 AZ)?
- A. Write Quorum: 3 dari 6; Read Quorum: 3 dari 6.
- B. Write Quorum: 4 dari 6; Read Quorum: 3 dari 6.
- C. Write Quorum: 6 dari 6; Read Quorum: 1 dari 6.
- D. Write Quorum: 2 dari 6; Read Quorum: 4 dari 6.

### Soal 3
Bagaimana mekanisme default Amazon DynamoDB Global Tables dalam menyelesaikan konflik penulisan simultan (*concurrent write conflict*) pada item yang sama di dua Region berbeda?
- A. First-In, First-Out (FIFO) berdasarkan antrean jaringan.
- B. Memunculkan error `TransactionConflictException` dan membatalkan kedua penulisan.
- C. Last-Writer-Wins (LWW) berdasarkan evaluasi timestamp internal rekaman data.
- D. Menggabungkan kedua payload data menjadi atribut list JSON secara rekursif.

### Soal 4
Fitur manakah pada DynamoDB Streams yang harus diaktifkan jika aplikasi hilir (*downstream consumer*) perlu membandingkan nilai atribut sebelum dan sesudah data dimodifikasi?
- A. `KEYS_ONLY`
- B. `OLD_IMAGE`
- C. `NEW_IMAGE`
- D. `NEW_AND_OLD_IMAGES`

### Soal 5
Apa perbedaan arsitektur persistensi data yang paling krusial antara Amazon ElastiCache for Redis dan Amazon MemoryDB for Redis?
- A. ElastiCache menulis data ke disk SSD lokal NVMe, sedangkan MemoryDB hanya menyimpan data murni di RAM.
- B. MemoryDB mencatat setiap transaksi secara synchronous ke Multi-AZ Transaction Log sebelum mengembalikan respons sukses penulisan, sedangkan ElastiCache mereplikasi data ke read replica secara asynchronous.
- C. ElastiCache mendukung clustering hingga 500 shard, sedangkan MemoryDB hanya mendukung single-node instance.
- D. ElastiCache kompatibel dengan MongoDB, sedangkan MemoryDB kompatibel dengan Redis OSS.

---

## 2. Intermediate Questions (5 Soal)

### Soal 6
Sebuah aplikasi web berbasis Aurora PostgreSQL mengalami insiden di mana CPU utilization pada Primary Writer Instance melonjak ke 99%, sementara dua Read Replica yang tersedia memiliki CPU utilization di bawah 10%. Manakah dari tindakan berikut yang secara langsung menyelesaikan akar masalah arsitektur ini?
- A. Menambahkan 3 unit Read Replica baru ke dalam cluster.
- B. Mengubah endpoint koneksi pada konfigurasi datasource microservice pelaporan/query baca agar merujuk ke Aurora Reader Endpoint, bukan Cluster Writer Endpoint.
- C. Mengonfigurasi Auto Scaling pada Aurora Cluster.
- D. Melakukan reboot manual pada instans Primary Writer.

### Soal 7
Dalam skenario Cache-Aside (Lazy Loading) menggunakan ElastiCache Redis, fenomena *Cache Stampede* (Thundering Herd) terjadi saat sebuah key cache yang diakses ribuan pengguna per detik tiba-tiba kedaluwarsa (expired). Manakah pendekatan arsitektur yang paling efektif untuk memitigasi dampak tersebut terhadap underlying database?
- A. Mengatur TTL kunci menjadi 0 (tidak pernah kedaluwarsa).
- B. Menerapkan algoritma mutual exclusion (mutex lock) terdistribusi saat cache miss, atau menggunakan pendekatan probabilistik early expiration (seperti XFetch).
- C. Memperbesar ukuran instance class RDS menjadi instans terbesar (`db.r6g.16xlarge`).
- D. Mengubah Redis eviction policy menjadi `allkeys-random`.

### Soal 8
Anda mengonfigurasi Aurora Global Database yang mencakup Region `us-east-1` (Primary) dan `ap-southeast-1` (Secondary). Terjadi pemadaman total pada Region `us-east-1`. Tim SRE harus melakukan failover darurat (*unplanned disaster recovery failover*). Apa langkah teknis yang dilakukan AWS pada secondary cluster selama proses *detach and promote*?
- A. Secondary cluster menunggu primary pulih secara otomatis melalui synchronous heartbeat.
- B. Storage volume secondary cluster dihapus dan di-restore ulang dari backup snapshot S3 terakhir.
- C. Secondary cluster dipisahkan dari replikasi global, diubah menjadi cluster standalone yang mandiri dengan kemampuan read-write penuh, dan endpoint lokalnya mulai menerima koneksi penulisan.
- D. AWS secara otomatis membelokkan seluruh Public IP DNS dari `us-east-1` ke `ap-southeast-1` tanpa perubahan status cluster.

### Soal 9
Sebuah sistem telemetri IoT menulis jutaan metrik per detik ke tabel DynamoDB. Tabel tersebut mengalami penurunan performa drastis dan mengembalikan error `ProvisionedThroughputExceededException`, padahal total WCU yang dialokasikan masih jauh di atas rata-rata konsumsi harian. Apa kemungkinan penyebab paling logis dari fenomena ini?
- A. Replikasi DynamoDB Streams mengalami dead-letter queue saturation.
- B. Terjadi masalah *Hot Partitioning* akibat pemilihan Partition Key dengan kardinalitas sangat rendah (misalnya seluruh perangkat menulis menggunakan Partition Key berformat status `DEVICE_ACTIVE`).
- C. Waktu TTL pada item terlalu pendek sehingga background reaper menghambat I/O mesin.
- D. Tabel tersebut tidak memiliki Global Secondary Index (GSI).

### Soal 10
Amazon DocumentDB mengadopsi model pemisahan komputasi dan penyimpanan (*compute-storage separation*). Apa implikasi dari arsitektur ini terhadap skalabilitas penambahan Read Replica?
- A. Setiap penambahan Read Replica baru memerlukan duplikasi penuh data 10 TB ke disk instans baru, membutuhkan waktu berjam-jam.
- B. Penambahan Read Replica baru dapat selesai dalam hitungan menit terlepas dari ukuran database, karena replika baru langsung dipasang (*mount*) ke shared storage volume yang sudah ada tanpa replikasi data independen.
- C. Read Replica DocumentDB harus selalu memiliki instance type yang dua kali lebih besar dari Primary Instance.
- D. DocumentDB tidak mendukung replikasi pembacaan lebih dari 1 node.

---

## 3. Scenario-Based Questions (3 Soal Kasus Nyata)

### Skenario 1: Platform Tiket Konser Skala Global
Sebuah platform penjualan tiket internasional menyelenggarakan penjualan tiket konser musik dunia. Dalam 5 menit pertama, diprediksi terdapat 250.000 transaksi per detik secara bersamaan untuk memperebutkan 50.000 kursi terbatas.
- Sistem tidak boleh menjual tiket melebihi kuota (*zero over-selling guarantee*).
- Status ketersediaan kursi harus ditampilkan ke pengguna di 15 negara dengan latensi rendering di bawah 50 milidetik.
- Arsitektur saat ini menggunakan RDS MySQL single-instance dan langsung mengalami crash total saat traffic memuncak.

**Tugas Analisis**:
1. Rancang layer caching dan layer database baru menggunakan kombinasi layanan AWS (MemoryDB/ElastiCache, DynamoDB, atau Aurora).
2. Tentukan di layer mana operasi dekremen kuota tiket (*atomic decrement*) harus dieksekusi untuk menjamin integritas data tanpa mengorbankan performa throughput.
3. Jelaskan strategi invalidasi atau sinkronisasi data ketersediaan kursi dari sistem backend ke browser pengguna global.

---

### Skenario 2: Modernisasi Sistem Core Banking Multi-Region
Sebuah bank digital beroperasi di Indonesia (`ap-southeast-3`) dan ingin membuka operasional penuh di Singapura (`ap-southeast-1`).
- Regulasi moneter mengharuskan setiap transaksi debit/kredit bersifat *Strictly Consistent* (ACID) dan tersimpan secara durable di region asal rekening.
- Rekening nasabah Singapura dapat melakukan penarikan saat bepergian di Indonesia.
- Target RPO jika terjadi bencana total di satu Region adalah 0 detik untuk data keuangan, dan RTO maksimal 5 menit.

**Tugas Analisis**:
1. Evaluasi apakah arsitektur *DynamoDB Global Tables Multi-Active* cocok untuk modul saldo buku besar perbankan ini. Berikan justifikasi teknis berdasarkan mekanisme resolusi konfliknya.
2. Jika Anda memilih Aurora Global Database atau RDS Multi-Region Read Replicas, jelaskan alur penulisan data rekening nasabah dan bagaimana strategi penanganan saat terjadi network partition (split-brain) antar kedua negara.

---

### Skenario 3: Krisis Latensi & Replikasi Data E-Commerce Flash Sale
Perusahaan e-commerce multinasional melaporkan bahwa selama event Flash Sale, terjadi anomali di mana pengguna di Region Australia (`ap-southeast-2`) melihat harga barang promosi lama yang belum diupdate, padahal administrator di Region Singapura (`ap-southeast-1`) telah memperbarui harga 15 detik sebelumnya.
- Database utama menggunakan Aurora PostgreSQL Global Database.
- Layer cache menggunakan ElastiCache Redis Cluster di setiap region.
- Aplikasi menggunakan pola Cache-Aside standar dengan TTL 1 jam.

**Tugas Analisis**:
1. Diagnosis akar masalah mengapa pengguna di Australia melihat data harga usang selama lebih dari beberapa detik.
2. Identifikasi apakah masalah terjadi di storage replication Aurora atau di layer ElastiCache regional.
3. Rancang arsitektur event-driven berbasis DynamoDB Streams atau Aurora CDC + SNS/SQS untuk memvalidasi/menginvalidasi cache di seluruh region secara real-time saat terjadi modifikasi data katalog.

---

## 4. Practical Chapter Challenge: Distributed Order & Cache Simulator
Implementasikan skrip simulasi Python terdistribusi lengkap yang mensimulasikan mekanisme replikasi data Active-Active, pendeteksian konflik *Last-Writer-Wins* (LWW), serta sinkronisasi layer caching (Cache-Aside pattern).

Kriteria teknis yang harus dipenuhi:
1. File kode mandiri: `hands-on/m01/dynamodb_global_replication_sim.py`.
2. Mensimulasikan dua region AWS (`us-east-1` dan `eu-west-1`).
3. Mengimplementasikan struktur data *Item* dengan metadata timestamp desimal presisi tinggi.
4. Mensimulasikan konflik penulisan konkuren pada item yang sama dan mendemonstrasikan secara transparan bagaimana LWW mempertahankan state data yang benar.
5. Mengimplementasikan layer *Local In-Memory Cache* dengan eviction time dan verifikasi cache invalidation saat stream mutasi data masuk.

---

## Kunci Jawaban Singkat
- **Soal 1**: B
- **Soal 2**: B
- **Soal 3**: C
- **Soal 4**: D
- **Soal 5**: B
- **Soal 6**: B
- **Soal 7**: B
- **Soal 8**: C
- **Soal 9**: B
- **Soal 10**: B

---