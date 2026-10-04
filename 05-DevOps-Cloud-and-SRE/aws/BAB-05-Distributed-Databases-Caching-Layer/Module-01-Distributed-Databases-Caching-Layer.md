# Modul 01: Distributed Databases & Caching Layer di AWS

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis perbedaan arsitektur, mekanisme replikasi, RPO/RTO, dan performa antara Amazon RDS Multi-AZ Deployment dan Read Replicas.
- Merancang topologi global multi-region menggunakan Amazon Aurora Global Database dengan replication lag sub-detik.
- Mengimplementasikan Amazon DynamoDB Global Tables (multi-active) dengan pemahaman mendalam tentang strategi resolusi konflik *Last-Writer-Wins* (LWW) dan *change data capture* (CDC) berbasis DynamoDB Streams.
- Memilih dan mengonfigurasi layer in-memory caching yang tepat antara Amazon ElastiCache (Redis engine) dan Amazon MemoryDB for Redis berdasarkan kebutuhan persistensi dan linearizability.
- Mengevaluasi Amazon DocumentDB untuk beban kerja semi-terstruktur berbasis dokumen JSON serta mengintegrasikan arsitektur *compute-storage separation*.

---

## 2. Prerequisite
- Pemahaman solid tentang networking AWS (VPC, Subnet, Security Groups, VPC Peering/Transit Gateway).
- Penguasaan konsep ACID, BASE (*Basically Available, Soft state, Eventual consistency*), dan Teorema CAP/PACELC.
- Kemampuan dasar AWS CLI dan Infrastructure as Code (Terraform atau AWS CDK).
- Pemahaman fundamental protokol database (SQL connection pooling, transactional isolation levels, serta struktur data Redis).

---

## 3. Concept
Dalam komputasi awan modern skala enterprise, database tidak lagi berdiri sebagai satu instans monolitik vertikal. *Distributed Databases & Caching Layer* mengabstraksi penyimpanan data melintasi batas fisik Availability Zone (AZ) dan Region AWS untuk mencapai:
1. **High Availability (HA)**: Mitigasi kegagalan node/infrastruktur lokal tanpa *data loss*.
2. **Horizontal Read/Write Scalability**: Pemisahan jalur baca (*read traffic*) dan tulis (*write traffic*) melintasi replika terdistribusi.
3. **Low-Latency Global Access**: Penempatan data sedekat mungkin dengan pengguna akhir (*edge/regional proximity*).
4. **Sub-millisecond Data Ingestion**: Akselerasi throughput menggunakan layer memori volatile maupun persistent distributed commit-log.

Pendekatan AWS memisahkan lapisan *compute* (mesin pemroses kueri) dan lapisan *storage* (disk terdistribusi), seperti yang diimplementasikan pada Amazon Aurora dan Amazon DocumentDB, atau mengadopsi model *shared-nothing multi-master/active-active* terdistribusi penuh pada DynamoDB.

---

## 4. Why
Mengapa arsitektur database terdistribusi dan caching sangat krusial dibandingkan pendekatan single-instance?

- **RTO & RPO Minim**: Kerusakan perangkat keras pada single-instance RDS memerlukan waktu pemulihan snapshot berjam-jam (RTO tinggi) dan kehilangan transaksi sejak snapshot terakhir (RPO tinggi). Replikasi terdistribusi menekan RPO menjadi 0 (atau mendekati nol) dan RTO ke level detik.
- **I/O Bottleneck Mitigation**: Disk berbasis IOPS (seperti EBS gp3/io2) memiliki batasan throughput fisik. Offloading 80-90% read query ke ElastiCache atau Read Replicas membebaskan primary compute node dari *I/O exhaustion*.
- **Blast Radius Reduction**: Kerusakan satu AZ (misal: pemadaman data center atau degradasi fiber optic) tidak melumpuhkan seluruh platform jika sistem didesain *Multi-AZ* atau *Multi-Region Active-Active*.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Amazon RDS: Multi-AZ vs Read Replicas

Tabel perbandingan mendalam karakteristik teknis keduanya:

| Parameter | RDS Multi-AZ (Standby) | RDS Read Replicas | RDS Multi-AZ Deployment with Two Readable Standbys |
| :--- | :--- | :--- | :--- |
| **Tujuan Utama** | High Availability & Disaster Recovery | Skalabilitas Pembacaan (Read Scale-out) | HA + Read Scale-out + Akselerasi Write |
| **Mekanisme Replikasi** | **Synchronous Physical Block Replication** di level storage engine. | **Asynchronous Logical Replication** (MySQL binlog / PostgreSQL WAL). | **Quorum-based Synchronous Replication** via storage and transaction log commit. |
| **Aksesibilitas** | Standby instance **tidak dapat** diakses/dibaca (*idle*). | Instance **dapat dibaca langsung** (*read-only* endpoint). | Dua standby instance **dapat dibaca** (*readable standby endpoints*). |
| **Dampak Performa Write** | Penalti latensi kecil (write harus di-ack oleh 2 AZ sebelum commit). | Hampir nol pada primary; lag terjadi di sisi replica (*replication lag*). | Latensi commit write sangat rendah via transactional commit quorum (2 dari 3). |
| **Cakupan Wilayah** | Hanya Intra-Region (antar-AZ dalam satu region). | Cross-AZ dan Cross-Region. | Intra-Region (3 AZ berbeda). |
| **Failover Mechanism** | Otomatis via dynamic DNS modification (RTO ~60-120 detik). | Promosi manual atau via skrip custom; data loss mungkin terjadi jika async lag > 0. | Otomatis via DNS failover (biasanya RTO < 35 detik). |

### 5.2 Amazon Aurora Global Database
Aurora mengabstraksi arsitektur database tradisional dengan memisahkan *compute layer* (database engine) dari *storage layer* (distribusi storage volume 6-way di 3 AZ).

- **Arsitektur Aurora Storage Engine**: Setiap penulisan menghasilkan 6 kopi data di 3 AZ (2 kopi per AZ). Penulisan dianggap sah secara konsisten jika 4 dari 6 node storage merespons (*quorum write* 4/6). Pembacaan membutuhkan *quorum read* 3 dari 6 node.
- **Aurora Global Database Engine**:
  - Replikasi storage lintas Region dilakukan langsung oleh *Aurora Distributed Storage Layer*, **bukan** oleh database compute engine melalui logical binlog.
  - Komputasi primer di *Primary Region* tidak terbebani overhead replikasi cross-region.
  - Storage replication lag umumnya **di bawah 1 detik** (rata-rata 100-300 ms).
  - Menyediakan fitur **Cross-Region Write Forwarding**, memungkinkan aplikasi pada *Secondary Region* mengirim query write ke node lokal, yang kemudian diforward secara transparan ke Primary Region.
  - Pemulihan bencana (Disaster Recovery/DR): Mendukung *Managed Planned Failover* (zero data loss) dan *Unplanned Failover / Detach* (RPO sub-detik, RTO < 1 menit).

### 5.3 Amazon DynamoDB Global Tables & DynamoDB Streams
DynamoDB adalah database NoSQL key-value dan document yang beroperasi secara serverless dengan latensi single-digit millisecond.

- **DynamoDB Streams**:
  - Menangkap urutan perubahan data (*changelog*) level-item secara berurutan dan terurut berdasarkan waktu (*strictly ordered log*).
  - Setiap record stream disimpan maksimal 24 jam.
  - Menyediakan 4 tipe tampilan (*view type*): `KEYS_ONLY`, `NEW_IMAGE`, `OLD_IMAGE`, dan `NEW_AND_OLD_IMAGES`.
- **Global Tables (Version 2019.11.21 / Fully Managed)**:
  - Menyediakan model replikasi **Multi-Region Active-Active**. Aplikasi dapat membaca dan menulis ke Region terdekat secara lokal.
  - Menggunakan DynamoDB Streams secara internal untuk mereplikasi mutasi data antar region secara asynchronous.
  - **Mekanisme Resolusi Konflik**: Menggunakan teknik **Last-Writer-Wins (LWW)**. Jika ada dua penulisan bersamaan pada item yang sama di dua region berbeda, DynamoDB mengevaluasi metadata *internal timestamp*. Penulisan dengan timestamp paling akhir akan menimpa penulisan sebelumnya.
  - Sifat Konsistensi: *Eventual Consistency* antar-region (replikasi selesai biasanya dalam rentang < 1 detik). Transaksi ACID (`TransactWriteItems`) diisolasi secara lokal di dalam satu region dan direplikasi secara eventual ke region lain.

### 5.4 Amazon ElastiCache (Redis OSS / Valkey) vs Amazon MemoryDB
Dua solusi in-memory berbasis Redis dari AWS dengan perbedaan arsitektural yang mendasar:

```
ElastiCache:  [Client] -> [Primary Node (In-Memory)] --async--> [Replica Node]
                                    |
                            (Async Snapshot ke S3) -> Resiko Data Loss saat Crash

MemoryDB:     [Client] -> [Compute Node (In-Memory)]
                                    |
                          (Synchronous Write)
                                    v
                     [Multi-AZ Transaction Log (Storage)] -> Zero Data Loss!
```

- **Amazon ElastiCache for Redis**:
  - Ditujukan sebagai **caching layer** akselerasi read/write.
  - Replikasi antara Primary dan Replica bersifat asynchronous.
  - Jika primary instance mengalami kegagalan fatal sebelum data di-flush atau direplikasi, **potensi kehilangan data (data loss) dapat terjadi**.
  - Menggunakan in-memory caching engine tanpa *durable write guarantees*.
- **Amazon MemoryDB for Redis**:
  - Ditujukan sebagai **Primary Database** utama, bukan sekadar cache.
  - Memanfaatkan **Multi-AZ Transaction Log** terdistribusi yang mirip dengan arsitektur storage Aurora.
  - Penulisan (write) baru dinyatakan sukses (ACK) ke client setelah transaksi tersimpan secara durable di distributed transactional log multi-AZ.
  - Karakteristik: Kompatibel penuh dengan API Redis, durabilitas setara database relasional, latensi read mikrodetik (karena disajikan dari memori), dan latensi write single-digit milidetik.

### 5.5 Amazon DocumentDB (with MongoDB Compatibility)
- Database dokumen JSON non-relasional terkelola penuh.
- Mengadopsi arsitektur storage Aurora: Lapisan *compute* stateless yang terpisah dari lapisan *storage engine* berkapasitas auto-growth hingga 128 TiB.
- Kompatibilitas: Mengemulasikan API MongoDB (versi 3.6, 4.0, 5.0) menggunakan proprietary compute engine AWS di atas storage terdistribusi.
- Menjamin isolasi komputasi dan penyimpanan, memungkinkan scaling hingga 15 read replicas dengan shared underlying storage tanpa overhead replikasi data independen pada disk.

---

## 6. How
Implementasi lapisan database terdistribusi dan caching harus mengikuti tata kelola alur data standar industri:

1. **Write-Path Optimization**:
   - Write diarahkan ke *Primary Write Endpoint* (RDS/Aurora) atau node DynamoDB regional terdekat.
   - Jika persistensi tinggi dibutuhkan dengan kompatibilitas Redis, gunakan MemoryDB.
2. **Read-Path Acceleration (Cache-Aside / Lazy Loading)**:
   - Aplikasi memeriksa keberadaan data di ElastiCache terlebih dahulu (*Cache Hit*).
   - Jika tidak ada (*Cache Miss*), aplikasi mengambil data dari Read Replica / DynamoDB, menuliskan hasilnya ke ElastiCache dengan konfigurasi Time-To-Live (TTL), kemudian mengembalikannya ke client.
3. **Cross-Region Replication Setup**:
   - Tentukan topology: Active-Passive (Aurora Global Database) atau Active-Active (DynamoDB Global Tables).
   - Pastikan Network MTU, Security Group inter-region, dan skema enkripsi KMS multi-region key terkonfigurasi seragam.

---

## 7. Analogy
Bayangkan operasional sebuah **Koran Harian Nasional**:
- **RDS Multi-AZ**: Memiliki ruang percetakan cadangan identik di seberang jalan yang menyalin setiap plat cetakan secara bersamaan. Jika ruang cetak utama mati listrik, ruang cadangan langsung beroperasi mencetak koran yang sama persis tanpa tertinggal satu artikel pun.
- **RDS Read Replica**: Menugaskan ratusan kurir fotokopi. Mereka mengambil salinan koran dari percetakan utama, lalu membagikannya ke berbagai stasiun kereta untuk dibaca orang. Kurir tidak berhak mengedit artikel baru, hanya mendistribusikan salinan. Terkadang kurir terlambat datang (*replication lag*).
- **Aurora Global Database**: Saluran teleks satelit dedicated berkecepatan cahaya yang menyalurkan rancangan plat koran secara instan ke percetakan di New York, Tokyo, dan London tanpa mengganggu mesin cetak utama di Jakarta.
- **ElastiCache**: Papan pengumuman kaca di depan kantor. Judul berita terpopuler ditempel di situ agar pejalan kaki tidak perlu masuk ke gudang arsip untuk membaca. Jika papan terkena hujan badai dan kertasnya rusak, beritanya hilang sementara, tetapi arsip aslinya tetap aman di gudang.
- **MemoryDB**: Papan pengumuman kaca interaktif yang dihubungkan langsung ke brankas baja bertinta emas tahan api; setiap huruf yang ditulis di kaca otomatis terukir permanen di dalam brankas sebelum dianggap sah.

---

## 8. Diagram (ASCII)

```
========================================================================================
                      ENTERPRISE MULTI-REGION DATABASE TOPOLOGY
========================================================================================

   [REGION: us-east-1 (Primary Write Region)]          [REGION: eu-west-1 (Secondary Region)]
  +-----------------------------------------+         +--------------------------------------+
  |                                         |         |                                      |
  |             +------------+              |         |            +------------+            |
  |             |  Client /  |              |         |            |  Client /  |            |
  |             |  App Node  |              |         |            |  App Node  |            |
  |             +-----+------+              |         |            +-----+------+            |
  |                   |                     |         |                  |                   |
  |        +----------+----------+          |         |        +---------+---------+         |
  |        | (Write)             | (Read)   |         |        | (Read Miss)       |         |
  |        v                     v          |         |        v                   v         |
  |  +-----------+         +-----------+    |         |  +-----------+       +-----------+   |
  |  |  Aurora   |         |ElastiCache|    |         |  |  Aurora   |       |ElastiCache|   |
  |  |  Compute  |         |   Redis   |    |         |  | Compute   |       |   Redis   |   |
  |  |  Primary  |         |  Cluster  |    |         |  | (Replica) |       |  Cluster  |   |
  |  +-----+-----+         +-----------+    |         |  +-----+-----+       +-----------+   |
  |        |                                |         |        |                             |
  |  ======|==============================  |         |  ======|===========================  |
  |  Aurora Storage Engine (Shared Multi-AZ)|         |  Aurora Storage Engine (Secondary)   |
  |  +------------------------------------+ |         |  +---------------------------------+ |
  |  | AZ-A (Data) | AZ-B (Data) | AZ-C   | | Storage |  | AZ-A (Data)| AZ-B (Data)| AZ-C  | |
  |  | Log Stream  | Log Stream  | (Data) | | Replic. |  | Log Stream | Log Stream | (Data)| |
  |  +------------------------------------+ | ------->|  +---------------------------------+ |
  |        | Sub-second dedicated link      | (< 1s)  |                                      |
  +--------|--------------------------------+         +--------------------------------------+
           |
           | CDC (Change Data Capture)
           v
  +-----------------------------------------+         +--------------------------------------+
  |  DynamoDB Global Table (us-east-1)     |         |  DynamoDB Global Table (eu-west-1)   |
  |  [Active Multi-Master Partition]       |         |  [Active Multi-Master Partition]     |
  |  Stream Enabled: NEW_AND_OLD_IMAGES    |<=======>|  Stream Enabled: NEW_AND_OLD_IMAGES  |
  |                                         | Async   |                                      |
  |                                         | (LWW)   |                                      |
  +-----------------------------------------+         +--------------------------------------+
========================================================================================
```

---

## 9. Simple Example
Inisialisasi tabel DynamoDB dengan Streams diaktifkan via AWS CLI:

```bash
aws dynamodb create-table \
    --table-name InventoryLedger \
    --attribute-definitions AttributeName=SKU,AttributeType=S AttributeName=WarehouseID,AttributeType=S \
    --key-schema AttributeName=SKU,KeyType=HASH AttributeName=WarehouseID,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES
```
Penjelasan: Konfigurasi `StreamViewType=NEW_AND_OLD_IMAGES` memvalidasi bahwa setiap mutasi item akan memancarkan data sebelum (*old*) dan sesudah (*new*) peristiwa operasi `PutItem`, `UpdateItem`, atau `DeleteItem` ke stream, memungkinkan replikasi cross-region dan pipeline CDC.

---

## 10. Practical Example (Terraform / HCL)
Berikut adalah konfigurasi IaC Terraform standar produksi untuk provisioning **Aurora Global Database Cluster** yang terdistribusi antara `us-east-1` (Primary) dan `eu-west-1` (Secondary).

```hcl
# --- Provider Configs ---
provider "aws" {
  alias  = "primary"
  region = "us-east-1"
}

provider "aws" {
  alias  = "secondary"
  region = "eu-west-1"
}

# --- Aurora Global Database Hub ---
resource "aws_rds_global_cluster" "global_database" {
  provider                  = aws.primary
  global_cluster_identifier = "enterprise-core-global-db"
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"
  database_name             = "core_transactional"
  storage_encrypted         = true
  deletion_protection       = true
}

# --- Primary Cluster (us-east-1) ---
resource "aws_rds_cluster" "primary_cluster" {
  provider                  = aws.primary
  cluster_identifier        = "core-db-primary-cluster"
  engine                    = aws_rds_global_cluster.global_database.engine
  engine_version            = aws_rds_global_cluster.global_database.engine_version
  global_cluster_identifier = aws_rds_global_cluster.global_database.id
  master_username           = "sysadmin"
  master_password           = "StrongVaultPassword99#!" # Gunakan AWS Secrets Manager di produksi
  db_subnet_group_name      = "vpc-database-subnet-group-useast1"
  vpc_security_group_ids    = ["sg-0123456789abcdef0"]
  backup_retention_period   = 7
  preferred_backup_window   = "02:00-03:00"
  storage_encrypted         = true

  skip_final_snapshot       = false
  final_snapshot_identifier = "core-db-primary-final-snapshot"
}

resource "aws_rds_cluster_instance" "primary_instances" {
  provider             = aws.primary
  count                = 2
  identifier           = "core-db-primary-node-${count.index + 1}"
  cluster_identifier   = aws_rds_cluster.primary_cluster.id
  instance_class       = "db.r6g.xlarge"
  engine               = aws_rds_cluster.primary_cluster.engine
  engine_version       = aws_rds_cluster.primary_cluster.engine_version
  publicly_accessible  = false
  db_subnet_group_name = "vpc-database-subnet-group-useast1"
}

# --- Secondary Cluster (eu-west-1) ---
resource "aws_rds_cluster" "secondary_cluster" {
  provider                  = aws.secondary
  cluster_identifier        = "core-db-secondary-cluster"
  engine                    = aws_rds_global_cluster.global_database.engine
  engine_version            = aws_rds_global_cluster.global_database.engine_version
  global_cluster_identifier = aws_rds_global_cluster.global_database.id
  db_subnet_group_name      = "vpc-database-subnet-group-euwest1"
  vpc_security_group_ids    = ["sg-0fedcba9876543210"]
  storage_encrypted         = true
  enable_global_write_forwarding = true

  depends_on = [
    aws_rds_cluster_instance.primary_instances
  ]
}

resource "aws_rds_cluster_instance" "secondary_instances" {
  provider             = aws.secondary
  count                = 2
  identifier           = "core-db-secondary-node-${count.index + 1}"
  cluster_identifier   = aws_rds_cluster.secondary_cluster.id
  instance_class       = "db.r6g.xlarge"
  engine               = aws_rds_cluster.secondary_cluster.engine
  engine_version       = aws_rds_cluster.secondary_cluster.engine_version
  publicly_accessible  = false
  db_subnet_group_name = "vpc-database-subnet-group-euwest1"
}
```

---

## 11. Real World Example
Sistem *Core Banking FinTech* global yang melayani transaksi di Asia Tenggara dan Eropa:
- **Write Transaction (Ledger Buku Besar)**: Menggunakan **Aurora Global Database**. Primary Region di `ap-southeast-1` (Singapura), Secondary Region di `eu-central-1` (Frankfurt). Pembukuan debit/kredit ditangani secara ketat dengan transaksi ACID di Singapura. Replikasi fisik penyimpanan sub-detik menjaga data sinkron di Frankfurt untuk audit real-time lokal dan disaster recovery dengan zero data loss.
- **Session Management & Token Auth**: Menggunakan **DynamoDB Global Tables** multi-active. Ketika pengguna terbang dari Jakarta ke Berlin, data session langsung terbaca di node `eu-central-1` dalam latensi single-digit ms tanpa harus transit network melintasi benua.
- **High-Velocity Rate Limiting**: Menggunakan **Amazon MemoryDB for Redis**. Transaksi API rate-limiting per customer diproses dalam memory-speed, namun setiap state tersimpan aman di multi-AZ transaction log untuk audit regulasi kepatuhan moneter.

---

## 12. Trade-offs
Dalam merancang distributed storage, arsitek cloud terikat pada Teorema PACELC (*If Partition, choose Availability or Consistency; Else, choose Latency or Consistency*):

| Kategori | Consistency Priority | Latency/Availability Priority |
| :--- | :--- | :--- |
| **AWS Solutions** | RDS Multi-AZ Standby, MemoryDB, Aurora (Strong Read on Primary) | DynamoDB Global Tables, ElastiCache Redis, Aurora Cross-Region Replicas |
| **Keuntungan** | Konsistensi data mutlak (no stale reads, zero transaction anomalies). RPO = 0. | Throughput sangat masif, latensi sub-detik hingga mikrodetik, degradasi parsial tanpa total outage. |
| **Kerugian** | Bottleneck pada kecepatan jaringan, lock contention, latensi commit lebih tinggi. | *Stale reads* (eventual consistency), potensi resolusi konflik menimpa data valid (LWW anomalies). |

---

## 13. When To Use
- Gunakan **RDS Multi-AZ**: Aplikasi monolitik standar SQL yang membutuhkan jaminan ketersediaan infrastruktur (HA) otomatis tanpa perlu perubahan arsitektur kode aplikasi.
- Gunakan **Aurora Global Database**: Database relational berbasis SQL dengan traffic pembacaan berskala benua dan persyaratan RPO < 1 detik serta RTO < 1 menit untuk regulasi DR enterprise.
- Gunakan **DynamoDB Global Tables**: Sistem IoT global, profile store, keranjang belanja (shopping cart), atau state management terdistribusi yang membutuhkan kapabilitas multi-region active-active write tanpa pengelolaan database cluster manual.
- Gunakan **ElastiCache**: Caching layer murni untuk query database mahal, session caching non-kritikal, dan leaderboard di mana data dapat dibangun ulang jika cluster mengalami crash.
- Gunakan **MemoryDB**: Workload membutuhkan performa struktur data canggih Redis (Sets, Sorted Sets, Hashes) namun bertindak sebagai *source-of-truth database* permanen yang tidak boleh kehilangan satu pun data commit.
- Gunakan **Amazon DocumentDB**: Backend aplikasi berbasis Node.js/Python yang bekerja dominan dengan skema JSON fleksibel dan memerlukan integrasi native ekosistem AWS (IAM, KMS, CloudWatch) dengan kapasitas data melebihi 10 TB.

---

## 14. When NOT To Use
- **JANGAN gunakan DynamoDB Global Tables** jika beban kerja Anda membutuhkan transaksi relasional lintas tabel yang kompleks (*complex SQL JOINs*) atau isolasi serializable multi-region instan.
- **JANGAN gunakan ElastiCache for Redis** sebagai database permanen tanpa backing persistent database di belakangnya; ElastiCache dapat kehilangan data saat failover atau hardware crash.
- **JANGAN gunakan Aurora Global Database** jika skenario aplikasi Anda membutuhkan arsitektur Active-Active Write serentak di mana semua region menerima write mutasi lokal pada baris tabel yang sama (gunakan DynamoDB Global Tables untuk kebutuhan ini).
- **JANGAN gunakan DocumentDB** jika Anda hanya membutuhkan key-value lookup sederhana (DynamoDB jauh lebih efisien dari sisi biaya dan performa).

---

## 15. Common Mistakes
1. **Mengabaikan Cache Stampede (Thundering Herd)**: Ketika kunci cache populer expired, ribuan request bersamaan langsung menghantam primary database secara mendadak. Solusi: Implementasikan caching locking (*mutex*) atau *probabilistic early expiration* (algoritma XFetch).
2. **Koneksi Aplikasi Tidak Memisahkan Reader dan Writer Endpoints**: Mengarahkan seluruh query ke primary cluster endpoint Aurora, sehingga Read Replica menganggur sementara CPU Primary Instance mencapai 100%.
3. **Mengabaikan Split-Brain pada Active-Active DynamoDB**: Melakukan operasi *increment* sederhana tanpa conditional update atau atomic operations pada dua region berbeda, menyebabkan nilai counter terdistorsi akibat penimpaan *Last-Writer-Wins* (LWW).
4. **Salah Memilih Redis Cluster Mode**: Menggunakan ElastiCache Redis dalam *Cluster Mode Disabled* untuk dataset berukuran masif, yang membatasi kapasitas memori hanya pada satu node master tunggal.

---

## 16. Best Practices
1. **Gunakan Connection Pooling**: Pasang **Amazon RDS Proxy** di antara aplikasi serverless (Lambda/ECS) dan database (RDS/Aurora) untuk mengelola pool ribuan koneksi konkuren, mengurangi overhead memory swapping pada DB engine, serta mempercepat waktu failover hingga 66%.
2. **Implementasikan Circuit Breaker Pattern**: Bungkus pemanggilan layer ElastiCache dengan circuit breaker. Jika Redis mengalami latency spike atau timeout, aplikasi langsung fallback membaca ke database tanpa membiarkan worker thread HTTP hang.
3. **Terapkan TTL (Time-to-Live) yang Ketat pada Cache**: Selalu tetapkan batas umur data pada Redis untuk mencegah memory bloat (Error: `OOM command not allowed when used memory > 'maxmemory'`).
4. **Gunakan DynamoDB TransactWriteItems Secara Terencana**: Minimalkan penggunaan transaksi terdistribusi multi-item pada DynamoDB hanya untuk alur finansial/transaksional krusial guna menghindari konsumsi 2x Write Capacity Unit (WCU).
5. **Konfigurasikan Auto-Scaling Read Replica**: Tetapkan CloudWatch metric `CPUUtilization` atau `DatabaseConnections` untuk memicu scale-out instans read-replica Aurora secara dinamis.

---

## 17. Troubleshooting

| Gejala Masalah | Akar Penyebab (Root Cause) | Prosedur Solusi / Remediasi |
| :--- | :--- | :--- |
| Aurora Replica Lag melonjak tinggi (> 10 detik). | Long-running queries pada reader instance memblokir penerapan perubahan storage log; atau I/O bottleneck pada instans kecil. | Matikan kueri lambat via `pg_terminate_backend()` atau `KILL QUERY`. Naikkan ukuran instance class reader (`db.r6g.*`) dan optimalkan index query. |
| ElastiCache Redis Error: `OOM command not allowed`. | Penggunaan memori melebihi batas `maxmemory` dan policy eviction diatur ke `noeviction`. | Ubah parameter group `maxmemory-policy` menjadi `volatile-lru` atau `allkeys-lru`. Tambahkan shard baru atau scale up node size. |
| DynamoDB `TransactionCanceledException`. | *ConditionalCheckFailed* atau write contention tinggi pada item yang sama secara serentak. | Evaluasi ekspresi kondisi penulisan. Terapkan strategi *Exponential Backoff* dengan jitter pada SDK klien. |
| RDS Multi-AZ Failover memakan waktu sangat lama (> 5 menit). | Terlalu banyak data dirty pages dalam memory yang belum di-checkpoint, atau query transaction rollback yang sangat masif. | Optimalkan konfigurasi checkpoint database engine. Pastikan transaksi batch besar dipecah menjadi chunk berukuran lebih kecil. |

---

## 18. Exercise
**Skenario**: Anda diminta membangun layer data untuk sistem e-commerce global Flash Sale.
1. Identifikasi komponen data apa saja yang harus disimpan di DynamoDB, Aurora PostgreSQL, dan ElastiCache Redis.
2. Buat skema partisi DynamoDB untuk menampung inventory flash sale dengan memitigasi *hot-partitioning issue*.
3. Tuliskan pseudocode implementasi Cache-Aside pattern yang dilengkapi dengan penanganan error jika cluster Redis down.

---

## 19. Challenge
Rancang arsitektur database multi-region hybrid:
- Region Primary: `ap-southeast-1` (Singapura).
- Region Disaster Recovery: `ap-southeast-3` (Jakarta).
- Persyaratan:
  1. RPO untuk data transaksi perbankan harus < 1 detik, RTO < 2 menit.
  2. Data analitik dibaca di Jakarta tanpa membebani IOPS Singapura.
  3. Session customer harus sinkron dua arah (active-active) dengan toleransi latency minimal.
- Sajikan dokumen desain teknis yang mencakup pemetaan produk AWS, diagram alur data, dan mekanisme mitigasi konflik data write secara terperinci.

---

## 20. Summary
- **RDS Multi-AZ** menjamin ketersediaan fisik melalui sinkronisasi disk block storage, sedangkan **Read Replicas** mengatasi beban pembacaan dengan replikasi log asynchronous.
- **Aurora Global Database** membedakan diri secara revolusioner dengan melakukan replikasi langsung pada storage subsystem, memangkas lag antar-region hingga < 1 detik tanpa membebani primary compute.
- **DynamoDB Global Tables** menghadirkan kapabilitas Active-Active Multi-Region sejati, mengandalkan DynamoDB Streams dan algoritma Last-Writer-Wins (LWW) untuk eventual consistency global.
- **ElastiCache** unggul untuk akselerasi kueri sementara berlatensi sub-milidetik, sedangkan **MemoryDB** memadukan kecepatan memori Redis dengan jaminan durabilitas ACID setara relational database melalui distributed transaction log engine.
- Integrasi harmonis antara relational persistence, distributed document/key-value storage, dan distributed in-memory caching merupakan fondasi mutlak untuk arsitektur berdaya tahan tinggi (*fault-tolerant*) dan berskala global.

---