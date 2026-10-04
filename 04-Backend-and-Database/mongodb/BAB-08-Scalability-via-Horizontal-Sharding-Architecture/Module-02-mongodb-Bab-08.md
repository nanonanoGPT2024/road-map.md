# BAB 08: Scalability via Horizontal Sharding Architecture
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal MongoDB Sharding Engine: siklus hidup *chunk*, protokol migrasi data 2-phase, mekanisme kerja balancer, serta internal *catalog cache* pada `mongos`.
- Mendiagnosis dan merancang strategi *Shard Key* tingkat lanjut (*Compound Hashed-Ranged Keys*, *Refining Shard Keys*, dan mitigasi *Monotonic Key Hotspotting*).
- Mengimplementasikan *Zone Sharding* (*Tag-Aware Sharding*) untuk *Geographical Data Locality* (kepatuhan regulasi GDPR/PDP) dan *Tiered Storage Lifecycle* (Hot/Cold Data Archiving).
- Mengoperasikan serta menginvestigasi kegagalan operasional cluster: pemecahan manual *Jumbo Chunks*, manajemen *Balancer Windows*, dan eksekusi mitigasi *Scatter-Gather Query*.
- Menjalankan orkestrasi arsitektur zero-downtime *Resharding* pada MongoDB 5.0+ beserta mitigasi trade-off beban I/O sistem.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, peserta harus sudah menguasai:
- Konsep dasar Sharded Cluster MongoDB (peran `mongos`, Config Server Replica Set / CSRS, dan Shard Replica Set).
- Administrasi Replica Set MongoDB tingkat lanjut (Write Concern `w: "majority"`, Read Concern `majority`, Oplog window, Heartbeat, Election).
- Dasar-dasar struktur indeks B-Tree, ESR rule (*Equality, Sort, Range*), dan profiling query via `.explain("executionStats")`.
- Pemahaman networking tingkat menengah: Latensi antar-region, round-trip time (RTT), MTU, dan konsep konsistensi terdistribusi (teorema PACELC/CAP).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Internal Routing Engine & Catalog Cache (`mongos`)
`mongos` adalah stateless routing proxy yang menjembatani driver aplikasi dengan storage node. `mongos` tidak menyimpan data persistensi di disk lokal; seluruh metadata topologi cluster, pemetaan chunk, dan rentang range disimpan secara otoritatif di database `config` pada Config Server Replica Set (CSRS).

```
+-----------------------------------------------------------------------+
|                             MONGOS PROXY                              |
|                                                                       |
|  [ Client Query ]                                                     |
|         │                                                             |
|         ▼                                                             |
|  ┌─────────────┐     Cache Miss/Stale Epoch      ┌─────────────────┐  |
|  │ Query Parser│ ──────────────────────────────> │ Refresh Worker  │  |
|  └──────┬──────┘                                 └────────┬────────┘  |
|         │                                                 │           |
|         ▼                                                 ▼           |
|  ┌─────────────┐       Read Metadata Range       ┌─────────────────┐  |
|  │ Routing Plan│ <────────────────────────────── │  Catalog Cache  │  |
|  └──────┬──────┘                                 └─────────────────┘  |
+---------┼─────────────────────────────────────────────────────────────+
          │
          ├── Targeted (Point/Range dengan Shard Key) ──> Langsung ke 1 Shard
          └── Scatter-Gather (Tanpa Shard Key) ─────────> Broadcast ke SEMUA Shard
```

1. **Epoch & Catalog Cache Refresh**:
   Setiap koleksi sharded memiliki metadata `epoch` (UUID unik penanda siklus hidup koleksi). Ketika migrasi chunk atau resharding terjadi, CSRS memperbarui versi routing table (`chunk version`: `<major>.<minor>`). `mongos` memvalidasi versi ini secara pasif saat interaksi data. Jika Shard mengembalikan sinyal `StaleConfigException`, `mongos` membekukan pipeline query lokal untuk koleksi tersebut, memicu refresh sinkron terhadap cache katalog dari CSRS, lalu mengulang routing query.

2. **Eksekusi Scatter-Gather vs. Targeted Routing**:
   - **Targeted Query**: Filter query menyertakan shard key secara deterministik. `mongos` melakukan binary search pada in-memory interval tree (berasal dari *Catalog Cache*), memetakan shard target secara tunggal, dan mengirim query ke target node.
   - **Scatter-Gather Query**: Query tidak menyertakan shard key. `mongos` membuka koneksi paralel ke *seluruh* shard primer di cluster, mengirim query secara asinkron, mengumpulkan stream data dari masing-masing shard, melakukan *merge-sort* lokal (menggunakan priority queue jika terdapat instruksi sorting), lalu meneruskan hasilnya ke klien. Hal ini menghasilkan lonjakan CPU pada `mongos` dan I/O overhead di seluruh shard.

#### B. Anatomi Migrasi Chunk & Balancer Engine
Balancer adalah proses thread terdistribusi yang dikelola secara otonom oleh primary node dari Config Server (CSRS). Balancer memantau ketimpangan jumlah chunk antar-shard berdasarkan threshold tertentu.

```
       Config Server (Primary)
     [ Balancer Thread Running ]
                 │
                 │ 1. Acquire Distributed Lock (config.locks)
                 │ 2. Find Imbalance (Chunks per shard delta >= Threshold)
                 ▼
+---------------------------------+        +---------------------------------+
|          DONOR SHARD            |        |         RECIPIENT SHARD         |
|                                 |        |                                 |
| 1. Dump Range Documents         |───────>| 2. Bulk Insert Documents        |
|    (Read uncommitted/committed) |        |                                 |
|                                 |        |                                 |
| 3. Buffer Incoming Changes      |        |                                 |
|    (Oplog extraction during     |───────>| 4. Apply Oplog Transformations  |
|     transfer window)            |        |                                 |
|                                 |        |                                 |
| 5. Enter Critical Section       |        |                                 |
|    (Block writes to this range) |        |                                 |
|                                 |        |                                 |
| 6. Commit Metadata to CSRS      |<───────| 5a. Acknowledge catch-up sync   |
|    (Update 'config.chunks'      |        |                                 |
|     with writeConcern: majority)|        |                                 |
|                                 |        |                                 |
| 7. Release Critical Section     |        |                                 |
|                                 |        |                                 |
| 8. Async Range Deletion Worker  |        |                                 |
|    (TCMalloc & WiredTiger sweep)|        |                                 |
+---------------------------------+        +---------------------------------+
```

- **Fase 1: Inisiasi & Penguncian**: Balancer mengakuisisi distributed lock pada koleksi `config.locks` menggunakan lease berbasis timeout.
- **Fase 2: Stream Dokumen**: Donor Shard mengirim seluruh dokumen dalam chunk ke Recipient Shard secara streaming via internal network commands.
- **Fase 3: Oplog Catch-Up**: Selama proses transfer data berlangsung, mutasi data baru (writes/updates/deletes) pada rentang chunk yang sedang ditransfer tetap diterima oleh Donor Shard dan dicatat ke buffer transit (oplog donor). Recipient Shard menarik dan menerapkan oplog tersebut.
- **Fase 4: Critical Section (Paus Transaksi)**: Ketika sisa delta oplog mendekati nol, Donor Shard menghentikan sementara penulisan baru (*quiesce*) pada rentang kunci tersebut selama beberapa milidetik.
- **Fase 5: Komitmen Metadata**: Donor Shard mengonfirmasi penyelesaian ke CSRS. CSRS mengupdate chunk boundary di database `config` dengan write concern `w: "majority"`.
- **Fase 6: Pembersihan Asinkron (Range Deletion)**: Donor Shard menandai blok data lama sebagai *orphaned documents*. Garbage collection thread internal (`rangeDeleter`) membersihkan dokumen-dokumen ini secara asinkron dari storage engine WiredTiger donor tanpa memblokir I/O throughput reguler.

#### C. Mekanisme Resharding (MongoDB 5.0+)
Resharding memungkinkan perubahan Shard Key dari koleksi aktif tanpa downtime aplikasi secara total.
- **Arsitektur Koordinator**: CSRS Primary bertindak sebagai *Resharding Coordinator*, mengontrol state machine koleksi secara terdistribusi.
- **Donor-Recipient Mesh**: Setiap shard dapat bertindak sebagai donor sekaligus recipient secara simultan. Shard membuat koleksi internal sementara (format: `system.resharding.<UUID>`).
- **Catch-up Streaming**: Query mutasi langsung direplikasi ke temporary collection melalui streaming oplog engine internal.
- **Critical Phase / Commit Window**: Koordinator membekukan penulisan global (aplikasi mengalami latensi tinggi sesaat, umumnya di bawah 2 detik), melakukan *swap* pointer metadata namespace secara atomik di Config Server, menginstruksikan `mongos` membersihkan cache katalognya, lalu membuka kembali akses tulis.

---

### 4. Why & What

| Fitur / Masalah | Solusi Tingkat Lanjut | Alasan Arsitektural & Dampak Produksi |
| :--- | :--- | :--- |
| **Monotonic Insert Bottleneck** | Hashed Sharding / Compound Hashed Sharding | Nilai `_id` berbasis `ObjectId` atau timestamp bertambah secara monotonik. Tanpa hashed key, 100% operasi insert akan menuju chunk paling kanan di satu shard (MaxKey), menyebabkan kegagalan scaling write throughput secara horizontal. |
| **Data Locality & Compliance** | Zone Sharding (Tag-Aware Sharding) | Memenuhi regulasi kedaulatan data regional (misal: GDPR Uni Eropa, UU PDP Indonesia). Data disimpan secara deterministik pada Shard yang berlokasi fisik di region hukum target. |
| **Storage Cost Optimization** | Tiered Storage via Zone Ranges | Memisahkan data aktif (transaksi 30 hari terakhir) ke shard berbasis high-IOPS NVMe, dan data riwayat/audit ke shard berbasis low-cost high-capacity HDD/EBS cold storage. |
| **Jumbo Chunk Deadlock** | Refine Shard Key / Manual Split Bypass | Chunk melebihi ukuran batas (default 64MB) dan tidak dapat di-split secara natural karena kardinalitas shard key rendah (*jumbo status*). Balancer menolak memigrasikannya, menyebabkan shard storage menjadi asimetris dan memicu degradasi sistem. |

---

### 5. How (Workflow Detail)

#### Workflow A: Penentuan Shard Key Komprehensif
```
                                 [ Calon Entitas Data ]
                                           │
                                           ▼
                            Apakah Write Throughput Ekstrem?
                                   ├── Ya ──> Kardinalitas Key Tinggi?
                                   │              ├── Ya ──> Pilih: HASHED SHARD KEY
                                   │              └── Tidak ─> Gabungkan: COMPOUND (LowCard + HighCard Hashed)
                                   │
                                   └── Tidak ─> Apakah Butuh Eksekusi Range Query Masif?
                                                  ├── Ya ──> Pilih: RANGED SHARD KEY (Tunggal / Compound)
                                                  └── Tidak ─> Butuh Segmentasi Lokasi / Tiering?
                                                                 ├── Ya ──> Pilih: ZONE-BASED COMPOUND KEY
                                                                 └── Tidak ─> Default: HASHED _id
```

#### Workflow B: Tahapan Zero-Downtime Zone-Based Data Tiering
1. **Analisis Pola Data**: Identifikasi atribut segregasi (misalnya `countryCode` atau `createdDate`).
2. **Pemberian Tag Shard**: Tandai Shard A sebagai "ZONE_HOT", Shard B sebagai "ZONE_COLD".
3. **Pemberian Aturan Range**: Ikat rentang data Shard Key tertentu ke tag terkait.
4. **Intervensi Balancer**: Balancer mendeteksi pelanggaran penempatan data berdasarkan konfigurasi zone baru, lalu mengeksekusi chunk migration secara otomatis hingga seluruh dokumen berada di shard yang ditentukan.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Logistik Hub & Spoke Global
- **CSRS**: Kantor Regulasi Sentral yang memegang peta otentik kepemilikan kode pos global.
- **`mongos`**: Gerbang pemilah logistik (*Sorting Facility*). Saat ada paket masuk, petugas membaca stiker alamat (Shard Key) untuk langsung melemparnya ke armada truk spesifik tanpa memeriksa isi paket.
- **Shard**: Gudang Wilayah (*Fulfillment Center*). Masing-masing melayani kontainer (*chunks*) miliknya sendiri.
- **Balancer**: Truk transfer antar-gudang malam hari yang bertugas menyeimbangkan muatan agar tidak ada gudang yang kelebihan beban (*over-capacity*).
- **Scatter-Gather**: Situasi darurat di mana paket tidak memiliki kode pos; manajer terpaksa menelepon seluruh gudang di seluruh dunia secara serentak untuk mencari pemilik paket tersebut.

#### Diagram Topologi Terdistribusi Multi-Zone
```
                      CLIENT APPLICATIONS
             (Web, Mobile, Enterprise Microservices)
                                │
                                ▼
                   LAYER 4 LOAD BALANCER (TCP)
                   ┌────────────┴────────────┐
                   ▼                         ▼
            [ mongos 01 ]             [ mongos 02 ]
                   │                         │
       ┌───────────┴─────────────────────────┴───────────┐
       │     Distributed Cache Synchronization (Epoch)   │
       ▼                                                 ▼
+─────────────────────────────────────────────────────────────+
|               CONFIG SERVER REPLICA SET (CSRS)              |
|        [csrs-primary] <-> [csrs-sec01] <-> [csrs-sec02]     |
|             (Stores authoritative metadata & locks)         |
+─────────────────────────────────────────────────────────────+
       │                                         │
       │                                         │
       ▼ (Zone: APAC / Fast NVMe)                ▼ (Zone: EMEA / Cold Storage)
+───────────────────────────────+         +───────────────────────────────+
|     SHARD 01 REPLICA SET      |         |     SHARD 02 REPLICA SET      |
|                               |         |                               |
| [shard01-pri]                 |         | [shard02-pri]                 |
|   ├── Chunk: {country: "ID"}  |         |   ├── Chunk: {country: "DE"}  |
|   └── Chunk: {country: "SG"}  |         |   └── Chunk: {country: "FR"}  |
| [shard01-sec] [shard01-arb]   |         | [shard02-sec] [shard02-arb]   |
+───────────────────────────────+         +───────────────────────────────+
```

---

### 7. Simple Example & Practical Example

#### A. Konfigurasi Dasar Sharded Cluster Setup (Administrative Shell Script)
Skrip berikut menginisialisasi sharding pada database dan koleksi menggunakan administrative commands pada `mongosh`:

```javascript
// Connect to: mongos
// 1. Mengaktifkan fitur sharding untuk database target
sh.enableSharding("enterprise_ledger");

// 2. Membuat compound index pendukung shard key
// Pola: { tenantId: 1, transactionTime: 1 }
db.getSiblingDB("enterprise_ledger").transactions.createIndex({
  tenantId: 1,
  transactionTime: 1
});

// 3. Shard koleksi dengan ranged key berdasarkan compound index tersebut
sh.shardCollection("enterprise_ledger.transactions", {
  tenantId: 1,
  transactionTime: 1
});
```

#### B. Implementasi Lanjutan: Multi-Zone Data Pinning & Refining Shard Key
Kasus: Perusahaan FinTech multi-nasional mengimplementasikan Zone Sharding untuk memastikan kepatuhan regulasi lokalisasi data regional (EU vs APAC), sekaligus memodifikasi shard key yang aktif untuk mengatasi hotspotting.

```javascript
// ============================================================================
// LANGKAH 1: Assign Tags/Zones ke Shard Terdistribusi
// ============================================================================
sh.addShardToZone("shard-apac-01", "ZONE_APAC");
sh.addShardToZone("shard-apac-02", "ZONE_APAC");
sh.addShardToZone("shard-eu-01", "ZONE_EU");

// ============================================================================
// LANGKAH 2: Buat Indeks Sesuai Spesifikasi Shard Key Baru
// ============================================================================
db.getSiblingDB("payment_gateway").settlements.createIndex({
  region: 1,
  customerId: "hashed"
});

// ============================================================================
// LANGKAH 3: Eksekusi Shard Collection Berdasarkan Zone
// ============================================================================
sh.shardCollection("payment_gateway.settlements", {
  region: 1,
  customerId: "hashed"
});

// ============================================================================
// LANGKAH 4: Konfigurasi Range Mapping untuk Setiap Zone
// MinKey dan MaxKey digunakan untuk mencakup seluruh namespace nilai hashed
// ============================================================================
sh.updateZoneKeyRange(
  "payment_gateway.settlements",
  { region: "APAC", customerId: MinKey },
  { region: "APAC", customerId: MaxKey },
  "ZONE_APAC"
);

sh.updateZoneKeyRange(
  "payment_gateway.settlements",
  { region: "EMEA", customerId: MinKey },
  { region: "EMEA", customerId: MaxKey },
  "ZONE_EU"
);

// ============================================================================
// LANGKAH 5: Memodifikasi Shard Key Aktif (Refining Shard Key - MongoDB 5.0+)
// Tambahkan field `settlementDate` untuk mencegah hotspotting pada range customerId
// ============================================================================
// Wajib membuat indeks baru yang menyertakan field tambahan
db.getSiblingDB("payment_gateway").settlements.createIndex({
  region: 1,
  customerId: "hashed",
  settlementDate: 1
});

// Jalankan refineCollectionShardKey
db.adminCommand({
  refineCollectionShardKey: "payment_gateway.settlements",
  key: {
    region: 1,
    customerId: "hashed",
    settlementDate: 1
  }
});
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Skenario: Arsitektur Transaksi Core-Banking 100 Juta Transaksi/Hari
- **Nama Sistem**: Global E-Commerce Core Order Engine.
- **Permasalahan**: Sistem mengalami kegagalan skalabilitas saat flash-sale. Database MongoDB eksisting menggunakan shard key berbasis tanggal tunggal `{ orderDate: 1 }`.
- **Dampak Kegagalan**: Terjadi fenomena *monotonically increasing key disaster*. 100% write traffic dialirkan ke satu node Shard (shard pemegang chunk `MaxKey`). Pemanfaatan CPU Shard primer tersebut menyentuh angka 99%, sementara 9 shard lainnya berada dalam kondisi idle (CPU < 5%). Replikasi oplog mengalami lagging parah (>300 detik), memicu timeouts pada aplikasi gateway checkout.

#### Analisis Akar Masalah (Root Cause Analysis)
1. **Shard Key Defect**: Nilai `orderDate` bergerak maju secara sekuensial. Pembuatan chunk baru selalu dialokasikan pada batas akhir range, meniadakan kemampuan Balancer untuk membagi dokumen baru sebelum transaksi terjadi.
2. **Kueri Pemrosesan**: Kueri aplikasi analitik backend mengeksekusi pencarian status order berbasis `orderId` tanpa menyertakan `orderDate`, memicu pembacaan Scatter-Gather ke seluruh shard.

#### Solusi Arsitektural Terapan
1. **Transisi ke Compound Shard Key dengan Hashed Component**:
   Mengubah shard key menjadi `{ customerId: "hashed", orderId: 1 }`. 
   - Komponen `customerId: "hashed"` mendistribusikan penulisan secara merata ke seluruh shard melalui hash algorithm (MurmurHash3).
   - Penambahan `orderId` mempertahankan selektivitas indeks dan memungkinkan optimasi targeted range scan per akun pelanggan.
2. **Implementasi MongoDB Resharding**:
   Karena database memproses beban transaksi aktif 24/7, tim engineering mengeksekusi perintah zero-downtime resharding:

```javascript
// Eksekusi Resharding Terjadwal di Maintenance Window
db.adminCommand({
  reshardCollection: "core_commerce.orders",
  key: { customerId: "hashed", orderId: 1 },
  writeConcern: { w: "majority", wtimeout: 60000 }
});

// Monitoring State Resharding
// Output state harus bertransisi: preparing -> cloning -> applying -> critical section -> completed
db.getSiblingDB("core_commerce").orders.aggregate([
  { $currentOp: { allUsers: true, idleConnections: true } },
  { $match: { type: "reshardCoordinator" } }
]);
```

- **Hasil Metrik**:
  - Penetrasi write throughput terdistribusi secara homogen (deviasi throughput CPU antar-shard < 4%).
  - P99 Write Latency terpangkas dari 1,800ms menjadi 18ms.
  - Oplog lag stabil pada level < 1 detik di seluruh cluster node.

---

### 9. Trade-offs

| Aspek | Pilihan A: Hashed Sharding | Pilihan B: Ranged Sharding | Analisis Kompromi Teknis |
| :--- | :--- | :--- | :--- |
| **Write Distribution** | Sangat Merata (Deterministic Hash) | Rentan Hotspotting (jika key monotonik) | Hashed mencegah I/O bottleneck secara instan, namun mematikan efisiensi pencarian range scan. |
| **Range Queries** | Menghasilkan Scatter-Gather (Lambat & Boros CPU) | Terlokalisasi pada Chunk Tertentu (Sangat Efisien) | Jika query berulang banyak menggunakan operasi `$gte` dan `$lte`, Ranged Sharding mengungguli Hashed secara drastis dalam latency. |
| **Chunk Migration Overhead** | Migrasi seragam secara terus-menerus | Migrasi terjadi dalam burst masif | Balancer pada Hashed Key bekerja konstan; Ranged Key hanya memindahkan data saat range tertentu melebihi ukuran kapasitas chunk. |
| **Memory / Cache Impact** | Working set menyebar ke seluruh RAM shard | Working set terisolasi pada Shard pemegang data aktif | Hashed Sharding membutuhkan kapasitas RAM (WiredTiger Cache) yang seimbang di seluruh Shard node. |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus A: Terbentuknya Jumbo Chunks
- **Penyebab**: Kardinalitas data pada Shard Key sangat rendah (misalnya melakukan sharding pada field `status: "ACTIVE|INACTIVE"`), atau operasi penulisan terpusat pada satu nilai tunggal yang mengakibatkan ukuran chunk melampaui `maxChunkSize` (64MB) tanpa adanya titik pemisah (split point) yang valid.
- **Deteksi**:
  ```javascript
  // Jalankan sh.status() dan cari flag "jumbo"
  // Atau query metadata config database secara langsung:
  use config;
  db.chunks.find({ jumbo: true });
  ```
- **Solusi & Troubleshooting**:
  1. *MongoDB 5.0+*: Gunakan `refineCollectionShardKey` untuk menambahkan field dengan kardinalitas tinggi ke dalam shard key.
  2. *Paksa split manual (jika terdapat titik potong dokumen yang valid)*:
  ```javascript
  sh.splitFind("enterprise_ledger.transactions", { tenantId: "CORP_XYZ", transactionTime: ISODate("2023-01-01T00:00:00Z") });
  ```
  3. Hapus flag jumbo secara manual setelah validasi struktur data:
  ```javascript
  sh.clearJumboFlag("enterprise_ledger.transactions", { tenantId: "CORP_XYZ", transactionTime: ISODate("2023-01-01T00:00:00Z") });
  ```

#### Kasus B: Balancer Bekerja Tanpa Kontrol pada Jam Operasional Sibuk
- **Penyebab**: Balancer berjalan 24 jam penuh tanpa pembatasan window waktu migrasi, menyebabkan bandwidth jaringan antar-node terpakai penuh dan latency IOPS storage melonjak drastis saat traffic pengguna berada pada jam sibuk.
- **Deteksi**: Menemukan lonjakan latensi read/write bersamaan dengan event migrasi chunk di dalam file log `mongod` pada donor/recipient shard.
- **Mitigasi**: Batasi jendela kerja Balancer hanya pada periode off-peak (misal: pukul 01:00 - 05:00 subuh):
  ```javascript
  use config;
  db.settings.updateOne(
     { _id: "balancer" },
     { $set: { activeWindow: { start: "01:00", stop: "05:00" } } },
     { upsert: true }
  );
  ```

---

### 11. Best Practices (Production Checklist)

1. **Konfigurasi Shard Key**:
   - [ ] Field shard key memiliki kardinalitas minimum > 100,000 kombinasi unik.
   - [ ] Hindari monotonic keys (Timestamp murni, ObjectId murni, Incrementing IDs) kecuali dikombinasikan dengan Hashed Prefix.
2. **Manajemen Indeks**:
   - [ ] Indeks yang menopang shard key harus dibangun sebelum cluster di-shard atau diverifikasi keberadaannya di semua shard node.
3. **Ketersediaan & Keamanan Routing**:
   - [ ] Pasang instance `mongos` secara lokal (co-located via sidecar) dengan server aplikasi, atau gunakan Layer 4 TCP Balancer dengan keep-alive timeout minimal 300 detik.
   - [ ] Set `maxConns` pada `mongod` minimal 2x lebih besar daripada akumulasi total koneksi dari seluruh pool instance `mongos`.
4. **Strategi Pemeliharaan & Kapasitas**:
   - [ ] Pertahankan sisa disk storage di setiap shard minimal 30% dari total kapasitas (Headroom untuk de-duplikasi WiredTiger dan proses data transit oplog saat migrasi chunk).
   - [ ] Tentukan Balancer Window di luar jam operasional puncak (*peak hours*).
   - [ ] Ukuran chunk standar disarankan tetap pada 64MB kecuali throughput cluster memiliki karakteristik khusus.

---

### 12. Hands-on Practice

Simulasi ini dirancang untuk dijalankan pada environment multi-node lokal menggunakan `mongosh`. Kita akan mempraktekkan inisiasi sharded cluster sederhana, zone setup, dan monitoring chunk routing.

#### Direktori Kerja: `hands-on/m02/`

#### File: `hands-on/m02/01_cluster_setup.js`
Inisialisasi database dan koleksi di tingkat admin cluster:

```javascript
// Hubungkan terminal ke mongos instance (Port: 27017)
// File: hands-on/m02/01_cluster_setup.js

const adminDB = db.getSiblingDB("admin");
const targetDB = db.getSiblingDB("global_erp");

print("--- [1] Mengaktifkan Sharding pada Database ---");
adminDB.runCommand({ enableSharding: "global_erp" });

print("--- [2] Membuat Indeks Komposit Shard Key ---");
targetDB.invoices.createIndex({ companyRegion: 1, invoiceId: "hashed" });

print("--- [3] Melakukan Sharding Koleksi ---");
adminDB.runCommand({
  shardCollection: "global_erp.invoices",
  key: { companyRegion: 1, invoiceId: "hashed" }
});
```

#### File: `hands-on/m02/02_configure_zones.js`
Menerapkan segmentasi geografis data:

```javascript
// Konfigurasi Zone Sharding
// File: hands-on/m02/02_configure_zones.js

const adminDB = db.getSiblingDB("admin");

print("--- [1] Menghubungkan Tag Zone ke Nama Shard Terdaftar ---");
// Asumsi cluster memiliki 2 shard: shard01 dan shard02
sh.addShardToZone("shard01", "ZONE_ASIA");
sh.addShardToZone("shard02", "ZONE_AMERICAS");

print("--- [2] Menetapkan Batasan Rentang Data untuk Zone ---");
sh.updateZoneKeyRange(
  "global_erp.invoices",
  { companyRegion: "ASIA", invoiceId: MinKey },
  { companyRegion: "ASIA", invoiceId: MaxKey },
  "ZONE_ASIA"
);

sh.updateZoneKeyRange(
  "global_erp.invoices",
  { companyRegion: "AMERICA", invoiceId: MinKey },
  { companyRegion: "AMERICA", invoiceId: MaxKey },
  "ZONE_AMERICAS"
);
```

#### File: `hands-on/m02/03_data_verification.js`
Injeksi data dan analisis eksekusi targeted query:

```javascript
// Validasi Distribusi Data dan Eksekusi Explain Plan
// File: hands-on/m02/03_data_verification.js

const erpDB = db.getSiblingDB("global_erp");

print("--- [1] Injeksi Data Multi-Region ---");
erpDB.invoices.insertMany([
  { companyRegion: "ASIA", invoiceId: "INV-001", amount: 1250.00 },
  { companyRegion: "ASIA", invoiceId: "INV-002", amount: 8900.50 },
  { companyRegion: "AMERICA", invoiceId: "INV-003", amount: 450.25 },
  { companyRegion: "AMERICA", invoiceId: "INV-004", amount: 23000.00 }
]);

print("--- [2] Eksekusi Targeted Query Explain Plan ---");
const targetedExplain = erpDB.invoices.find({
  companyRegion: "ASIA",
  invoiceId: "INV-001"
}).explain("executionStats");

print("Tipe Routing: " + targetedExplain.queryPlanner.winningPlan.stage);
print("Shard Target Array Length: " + targetedExplain.executionStats.executionStages.shards.length);

print("--- [3] Eksekusi Scatter-Gather Query Explain Plan (Unbounded) ---");
const scatterExplain = erpDB.invoices.find({
  amount: { $gt: 1000 }
}).explain("executionStats");

print("Shard Terlibat pada Scatter-Gather: " + scatterExplain.executionStats.executionStages.shards.length);
```

---

### 13. Exercises

#### Level Easy
Koleksi `ecommerce.logs` di-shard menggunakan shard key tunggal berbasis hash `{ _id: "hashed" }`. Tuliskan query administratif untuk memverifikasi jumlah total chunk saat ini beserta lokasinya di setiap shard.
- *Petunjuk*: Gunakan method agregasi pada namespace database `config.chunks`.

#### Level Medium
Sebuah aplikasi audit keuangan memiliki dokumen berstruktur:
```json
{
  "_id": ObjectId("..."),
  "branchCode": "JKT01",
  "auditDate": ISODate("2023-10-15T00:00:00Z"),
  "payload": { ... }
}
```
Mayoritas kueri aplikasi berupa pencarian dokumen berdasarkan `branchCode` untuk rentang waktu (`auditDate`) tertentu. Namun, beberapa kantor cabang memproduksi transaksi 500x lebih masif daripada cabang lain. Tentukan konfigurasi shard key terbaik yang mampu mencegah write hotspotting pada cabang masif tersebut, namun tetap menjaga efisiensi range scan waktu. Tuliskan syntax sharding lengkapnya.

#### Level Hard
Sebuah cluster produksi berada pada status `balancer: locked` permanen akibat proses migrasi yang terputus secara tidak wajar saat network partition. Tuliskan pipeline investigasi dan mitigasi pembersihan distributed locks pada Config Server untuk mengembalikan operasional Balancer ke kondisi normal secara aman tanpa me-restart service CSRS.

---

### 14. Challenge

Rancang arsitektur Sharding tingkat produksi untuk sistem IoT Smart Grid dengan spesifikasi berikut:
- **Volume**: 200,000 unit meteran listrik pintar di seluruh dunia.
- **Ingestion**: Setiap unit mengirimkan telemetri per 5 detik (akumulasi >3.4 miliar data poin per hari, estimasi ~400GB/hari).
- **Karakteristik Kueri**: 
  1. 90% traffic kueri real-time hanya mengakses data 7 hari terakhir berdasarkan rentang `meterId`.
  2. Data berumur lebih dari 30 hari hingga 3 tahun harus dipertahankan untuk audit dan compliance, namun dengan biaya storage terendah (Tiered Storage).
- **Batasan**: Penulisan data telemetri baru tidak boleh mengalami write starvation/blocking akibat aktivitas chunk migration.

**Tugas Arsitektur**:
1. Definisikan Compound Shard Key yang digunakan beserta justifikasi teknisnya.
2. Gambarkan topologi Zone Sharding (Hot Storage vs Cold Storage) dan transisi siklus datanya secara otomatis tanpa downtime.
3. Definisikan strategi pemisahan hardware (Disk type, IOPS allocation, RAM distribution) antara Shard Hot Node dan Shard Cold Node.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi esensial dari parameter `epoch` pada metadata routing MongoDB Sharding?
   - A. Menghitung interval eksekusi Balancer.
   - B. Penanda unik versi masa aktif koleksi untuk mendeteksi `StaleConfigException`.
   - C. Token enkripsi transfer data antar-shard.
   - D. Waktu kedaluwarsa dokumen (TTL) di level metadata.

2. Komponen manakah dalam sharded cluster yang bertanggung jawab secara otoritatif untuk mengelola distributed balancer lock?
   - A. Instance `mongos` aktif.
   - B. Shard yang memiliki chunk terbanyak.
   - C. Primary node pada Config Server Replica Set (CSRS).
   - D. Arbiters pada Shard Primer.

3. Kueri yang tidak menyertakan shard key dalam predikat pencariannya disebut:
   - A. Point-to-Point query.
   - B. Targeted query.
   - C. Scatter-Gather query.
   - D. Ephemeral query.

4. Kapan proses pembersihan dokumen lama (orphaned documents) pada Donor Shard dieksekusi selama siklus chunk migration?
   - A. Sebelum data dikirimkan ke Recipient Shard.
   - B. Bersamaan dengan fase kritis pemblokiran transaksi.
   - C. Secara asinkron setelah metadata chunk resmi dikomit ke CSRS.
   - D. Hanya saat server MongoDB di-restart.

5. Berapakah ukuran default chunk (`maxChunkSize`) pada instalasi MongoDB standar?
   - A. 16 MB.
   - B. 64 MB.
   - C. 128 MB.
   - D. 512 MB.

#### B. Pertanyaan Intermediate
6. Mengapa shard key komposit `{ country: 1, createdDate: 1 }` berisiko mengalami write bottleneck jika seluruh data yang masuk berasal dari satu negara yang sama?
   - A. Nilai hash tidak terdistribusi dengan baik.
   - B. Nilai `createdDate` yang bertambah secara serial menyebabkan write terpusat pada satu shard penampung nilai akhir (MaxKey).
   - C. Ukuran chunk akan otomatis menjadi tak terbatas (infinite size).
   - D. Config Server menolak insert yang memiliki field tanggal.

7. Perhatikan skenario berikut: Administrator mengeksekusi perintah pemecahan chunk (split), namun sistem memunculkan error: `could not find a split point`. Apa indikasi utama dari pesan kesalahan ini?
   - A. Konfigurasi disk storage shard telah penuh (100% capacity).
   - B. CSRS tidak dapat dihubungi melalui jaringan.
   - C. Seluruh dokumen dalam chunk tersebut memiliki nilai Shard Key yang identik (Low/Single Cardinality).
   - D. Versi WireTiger storage engine sudah usang.

8. Bagaimana MongoDB meminimalisasi durasi blocking penulisan ke aplikasi saat fase *Commit* pada eksekusi zero-downtime Resharding?
   - A. Menolak seluruh koneksi aplikasi baru via `mongos`.
   - B. Melakukan sinkronisasi oplog donor secara streaming dan hanya mengaktifkan *Critical Section* selama beberapa detik di titik akhir transisi metadata.
   - C. Menghapus indeks cluster yang ada terlebih dahulu.
   - D. Membagi data menjadi 1 chunk besar tanpa replikasi.

9. Apa dampak langsung dari menonaktifkan Balancer (`sh.stopBalancer()`) di cluster enterprise?
   - A. Operasi penulisan dan pembacaan data dihentikan total.
   - B. Migrasi chunk antar-shard otomatis berhenti, namun cluster tetap melayani query operasi normal.
   - C. Dokumen yang ada akan langsung digabungkan menjadi satu shard utama.
   - D. Seluruh `mongos` mengalami crash akibat hilangnya referensi sinkronisasi.

10. Mengapa implementasi Hashed Sharding pada sebuah field tanggal historis merugikan performa analytical reporting yang membutuhkan rentang waktu bulanan?
    - A. Ukuran storage membengkak hingga 10x lipat.
    - B. Algoritma hash memecah tanggal berurutan ke berbagai shard acak, memaksa reporting query melakukan Scatter-Gather ke semua node.
    - C. Hash function MongoDB tidak mendukung tipe data BSON Date.
    - D. Shard Key bertipe hash tidak mendukung pembuatan indeks sekunder.

#### C. Skenario Kasus Produksi
11. **Skenario Kasus 1**:
    Sebuah aplikasi FinTech melaporkan kenaikan tajam pada metrik P99 latency. Berdasarkan log analisis, ditemukan sejumlah query laporan harian dieksekusi dengan syntax:
    ```javascript
    db.orders.find({ status: "PAID" }).sort({ createdAt: -1 });
    ```
    Cluster memiliki 16 shard, dan shard key koleksi tersebut adalah `{ customerId: "hashed" }`. Jelaskan secara teknis mengapa query ini menyebabkan degradasi sistem di tingkat `mongos` proxy!

12. **Skenario Kasus 2**:
    Sebuah chunk pada Shard-03 berstatus `jumbo: true`. Kapasitas chunk telah mencapai 1.2 GB dan balancer gagal memindahkannya ke shard lain. Field Shard Key adalah `{ merchantId: 1 }`, dan seluruh dokumen di dalam chunk tersebut memang dimiliki oleh satu merchant retail berskala raksasa. Bagaimana arsitek basis data harus mengatasi masalah skalabilitas ini tanpa menghapus data merchant tersebut?

13. **Skenario Kasus 3**:
    Perusahaan Anda baru saja mengakuisisi entitas bisnis di Jerman (EU) dan wajib tunduk pada GDPR yang melarang data warga Jerman disimpan di server luar region Eropa. Cluster MongoDB Anda saat ini tersebar di Singapore Shard (APAC) dan Frankfurt Shard (EU). Tuliskan langkah-langkah komprehensif implementasi MongoDB Sharding agar seluruh dokumen yang memiliki atribut `{ legalResidence: "DE" }` berpindah dan terkunci secara permanen di Shard Frankfurt!

---

### Kunci Jawaban Evaluasi

#### Kunci Pilihan Ganda (Basic & Intermediate)
1. **B** — `epoch` adalah identifikasi siklus hidup koleksi; perbedaan epoch menandakan koleksi telah di-drop/resharded, memicu invalidasi `Catalog Cache`.
2. **C** — Distributed balancer locks dikoordinasikan secara eksklusif oleh Primary node dari Config Server (CSRS).
3. **C** — Scatter-Gather query menyebarkan filter ke semua shard karena tidak mengetahui lokasi pasti data tanpa Shard Key.
4. **C** — Pembersihan data orphan dieksekusi oleh thread internal `rangeDeleter` secara asinkron pasca commit metadata di CSRS.
5. **B** — Standar default ukuran chunk di MongoDB adalah 64 Megabytes.
6. **B** — Sifat nilai waktu yang monotonik membuat chunk selalu mencapai nilai batas atas di shard yang sama, meniadakan distribusi penulisan secara horizontal.
7. **C** — Jika nilai shard key sama pada seluruh dokumen di chunk tersebut, sistem tidak dapat menemukan split point di B-Tree boundary.
8. **B** — Pendekatan streaming oplog catch-up memungkinkan critical section (penundaan write) ditekan seminimal mungkin (lazimnya 1-2 detik) hanya untuk swap pointer metadata.
9. **B** — Mematikan balancer hanya menghentikan perpindahan chunk antar-shard; aktivitas read/write klien tetap berjalan normal.
10. **B** — Hashed sharding mendistribusikan data secara pseudo-random, sehingga rentang tanggal yang berdekatan tersebar ke berbagai shard, memaksa scatter-gather query.

#### Jawaban Skenario Kasus Produksi
11. **Analisis Skenario 1**:
    Query tidak menyertakan shard key `customerId`. Dampak teknis:
    - `mongos` terpaksa mengirim query ini ke seluruh 16 Shard secara broadcast (Scatter-Gather).
    - Masing-masing shard mengeksekusi table scan/index scan parsial, lalu mengirim seluruh hasil yang cocok kembali ke `mongos`.
    - `mongos` harus menampung seluruh dataset dari 16 node di RAM, melakukan operasi in-memory merge-sort untuk field `createdAt`, lalu memproses pagination. Hal ini memicu memory footprint ekstrem dan lonjakan latency P99 di proxy layer.
12. **Analisis Skenario 2**:
    Karena shard key saat ini `{ merchantId: 1 }` memiliki kardinalitas 1 untuk merchant raksasa tersebut, split internal menjadi mustahil dilakukan. Solusi arsitektur:
    - Manfaatkan fitur **Refining Shard Key** (MongoDB 5.0+): Tambahkan field kedua dengan kardinalitas tinggi untuk membentuk compound shard key, misalnya `{ merchantId: 1, transactionId: 1 }`.
    - Buat indeks pendukung: `db.orders.createIndex({ merchantId: 1, transactionId: 1 })`.
    - Eksekusi perintah administratif: `db.adminCommand({ refineCollectionShardKey: "db.orders", key: { merchantId: 1, transactionId: 1 } })`.
    - Setelah shard key menjadi komposit, MongoDB akan memiliki titik pemisah baru dan memecah (split) chunk 1.2 GB tersebut secara otomatis menjadi sub-chunk yang dapat dimigrasikan oleh Balancer.
13. **Analisis Skenario 3**:
    Langkah implementasi:
    1. Tambahkan Tag pada Shard Frankfurt: `sh.addShardToZone("shard-frankfurt", "ZONE_EU")`.
    2. Pastikan field `legalResidence` masuk ke dalam indeks shard key (misalnya menggunakan compound shard key `{ legalResidence: 1, customerId: "hashed" }`).
    3. Konfigurasi Zone Range:
       ```javascript
       sh.updateZoneKeyRange(
         "app.customers",
         { legalResidence: "DE", customerId: MinKey },
         { legalResidence: "DE", customerId: MaxKey },
         "ZONE_EU"
       );
       ```
    4. Pastikan Balancer aktif: `sh.startBalancer()`. Balancer akan memvalidasi routing, menemukan dokumen berlabel `DE` yang berada di Shard APAC, lalu memigrasikan seluruh chunk yang melanggar batasan tersebut ke Shard Frankfurt secara otomatis hingga compliant.

---

### 16. Summary

Implementasi sharding tingkat enterprise bukan sekadar memecah data ke banyak node, melainkan seni menjaga keseimbangan antara **Write Distribution Uniformity** dan **Query Locality Optimization**. 

```
                                ARSITEKTUR SHARDING
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
     WRITE OPTIMIZATION                                    READ OPTIMIZATION
  - Hashed Shard Keys                                   - Ranged Shard Keys
  - Mencegah Monotonic Bottleneck                       - Targeted Single-Shard Routing
  - Eliminasi Hotspotting Cluster                       - Minimalisasi Scatter-Gather Latency
             │                                                     │
             └──────────────────────────┬──────────────────────────┘
                                        ▼
                             ENTERPRISE GOVERNANCE
                         - Zone Sharding (PDP/GDPR)
                         - Tiered Storage (Hot/Cold Data)
                         - Zero-Downtime Resharding (Mongo 5.0+)
```

Keputusan desain Shard Key bersifat fundamental dan menentukan batas performa sistem secara permanen. Pemahaman mendalam tentang internal query routing `mongos`, fase kritis migrasi chunk, pemecahan *jumbo chunks*, dan pemanfaatan *Zone Sharding* membedakan infrastruktur database yang rapuh dari arsitektur data terdistribusi yang resilient, scalable, dan hemat biaya operasional.