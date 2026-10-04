# BAB 03: Advanced Data Modeling & Schema Design Patterns
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Membedah Internal Storage Engine**: Mengkorelasikan desain skema dokumen dengan alokasi memori internal WiredTiger, *cache eviction*, *checkpointing*, dan representasi BSON di tingkat disk.
2. **Mengimplementasikan Pola Tingkat Lanjut Terpadu**: Menggabungkan pola *Bucket*, *Outlier*, dan *Computed* secara sinergis untuk menangani beban kerja ekstrem (skala ingest >100.000 ops/detik) tanpa melanggar batas 16 MB BSON.
3. **Mendesain Struktur Hierarki & Pohon Berskala Enterprise**: Memilih dan mengeksekusi strategi pemodelan graf/pohon (*Materialized Paths*, *Array of Ancestors*, dan nested queries via `$graphLookup`) berdasarkan rasio *Read-to-Write*.
4. **Mengeksekusi Strategi Migrasi Skema Zero-Downtime**: Menerapkan *Schema Versioning Pattern* dengan siklus hidup migrasi bertahap (*Dual-Write*, *Lazy Migration*, *Background Batch Mutator*) pada sistem perbankan/fintech aktif.
5. **Memitigasi Anti-Pattern Arsitektural**: Mendeteksi dan merekayasa ulang skema yang rentan terhadap fragmentasi disk, kebocoran memori kerja (*working set thrashing*), dan *unbounded array growth*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Fundamental MongoDB: CRUD API, Aggregation Framework dasar (`$match`, `$group`, `$project`, `$unwind`).
* Konsep B-Tree Indexing: Compound Index, Multikey Index, Partial Index, dan Index Prefix rules.
* Dasar Pemodelan Data Relasional vs Non-Relasional (Embed vs Reference trade-offs).
* Penggunaan Node.js runtime dengan Native MongoDB Driver (`mongodb` npm package v6.x) atau TypeScript equivalent.
* Pemahaman fundamental sistem operasi: Linux memory management (VFS, dirty pages, file system buffers).

---

### 3. Concept & Internal Architecture (Mendalam)

Desain skema dalam MongoDB tidak dapat dipisahkan dari arsitektur storage engine **WiredTiger**. Ketidakpahaman atas cara WiredTiger mengeksekusi I/O dapat memicu degradasi performa catastrophic pada skala enterprise.

```
+-----------------------------------------------------------------------+
|                           CLIENT APPLICATION                          |
+-----------------------------------------------------------------------+
                                   |
                     BSON Wire Protocol Payload
                                   v
+-----------------------------------------------------------------------+
|                         WIREDTIGER ENGINE                             |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  |                        WiredTiger Cache                         |  |
|  |  +-----------------------+     +-----------------------------+  |  |
|  |  | Clean Uncompressed    |     | Dirty In-Memory Pages       |  |  |
|  |  | B-Tree Pages          |     | (hazard pointers, modified) |  |  |
|  |  +-----------------------+     +-----------------------------+  |  |
|  |              ^                                |                 |  |
|  |              | Eviction Workers               | Checkpointer    |  |
|  |              | (LRU / Hazard Checks)          | (Default: 60s)  |  |
|  +--------------|--------------------------------|-----------------+  |
|                 |                                v                    |
|  +-----------------------------------------------------------------+  |
|  |                        Block Manager                            |  |
|  |  - Block Allocator & Free Lists                                 |  |
|  |  - Compression (Snappy, Zstandard, Prefix Compression)          |  |
|  |  - Checksumming (CRC32)                                         |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------|-----------------------------------+
                                    v
+-----------------------------------------------------------------------+
|                    PHYSICAL STORAGE (NVMe / SSD)                      |
|  - collection-*.wt (Data Blocks)                                      |
|  - index-*.wt (B-Tree Leaf Blocks)                                    |
|  - journal/WiredTigerLog.* (Write-Ahead Logging)                      |
+-----------------------------------------------------------------------+
```

#### A. WiredTiger Cache, Hazard Pointers, dan B-Tree Pages
Data di disk disimpan dalam blok terkompresi (secara *default* menggunakan Snappy, atau Zstandard untuk rasio kompresi lebih tinggi). Ketika dibaca ke dalam memori (*WiredTiger Cache*), blok diekstrak menjadi representasi B-Tree berbasis pointer yang **tidak terkompresi**.

* **Page Sizing**: Ukuran halaman memori internal WiredTiger bervariasi dari 4 KB hingga batas alokasi disk (umumnya maksimum 32 KB untuk leaf page). Jika sebuah dokumen yang dimodifikasi ukurannya bertambah melampaui batas halaman, WiredTiger terpaksa melakukan **Page Split**.
* **Hazard Pointers**: WiredTiger menggunakan struktur *hazard pointer* untuk memvalidasi thread pembacaan yang mengakses halaman memori secara concurrent tanpa mengunci (latch-free) seluruh pohon. Dokumen yang terlalu sering dimodifikasi di tempat yang sama meningkatkan perebutan *hazard pointer* dan memicu latensi tinggi pada konkurensi ekstrem.

#### B. Anatomi Update: In-Place vs Out-of-Place Rewrite
* **In-Place Update**: Terjadi jika modifikasi dokumen tidak mengubah ukuran byte fisik dokumen tersebut, atau jika tipe data field diubah ke ukuran yang sama persis (misal mengubah integer 64-bit ke integer 64-bit lain via `$set`). Ini hanya memodifikasi dirty page di memori tanpa merealokasi posisi data.
* **Out-of-Place Allocation**: Terjadi saat memanipulasi dokumen menggunakan `$push` (tanpa batas), menambahkan *field* baru, atau menambah panjang string. Jika dokumen tumbuh melewati batas slot alokasi B-Tree di memory block:
  1. Halaman dialokasikan ulang.
  2. Dokumen lama ditandai sebagai *dead space* (fragmentasi internal).
  3. Dokumen baru ditulis ulang di segmen memori baru.
  4. Seluruh index yang merujuk pada `RecordId` dokumen lama harus dimutasi jika struktur B-Tree internal berubah.

#### C. BSON Overhead & Structural Footprint
BSON bukan format ringkas seperti Protobuf. Setiap key dalam BSON menyimpan metadata lengkap:
* 1-byte tipe data.
* N-bytes nama field diakhiri null terminator (`\0`).
* N-bytes data payload.

Jika Anda memiliki skema dengan nama field deskriptif yang tertanam pada jutaan dokumen:
```json
// Buruk: Field overhead masif
{
  "device_telemetry_temperature_celsius": 24.5,
  "device_telemetry_humidity_percentage": 60.2
}
```
Nama field `device_telemetry_temperature_celsius` (37 byte) diulang untuk setiap pembacaan. Untuk 1 miliar dokumen, overhead nama field saja memakan **37 GB RAM** di WiredTiger Cache murni untuk string representasi kunci skema.

---

### 4. Why & What

| Paradigma | Karakteristik | Masalah Skala Besar | Pola Solusi Enterprise |
| :--- | :--- | :--- | :--- |
| **Fully Normalized (RDBMS Style)** | Memecah semua entitas ke koleksi terpisah dan menggunakan `$lookup` runtime. | Latensi read anjlok drastis (CPU-bound) pada relasi multi-hop (M:N). `$lookup` melakukan nested loop scanning jika index tidak ideal. | **Extended Reference Pattern**: Denormalisasi atribut yang sering dibaca saja; biarkan sisanya di dokumen asal. |
| **Naive Embedded (Anti-Pattern)** | Memasukkan seluruh relasi anak ke dalam array di dokumen induk tanpa batas. | Pelanggaran batas BSON 16 MB. B-Tree leaf page splits konstan. Fragmentasi RAM tinggi. | **Subset Pattern** & **Bucket Pattern**: Potong array menjadi chunk tetap atau pisahkan histori dingin (*cold data*). |
| **Polymorphic Monolith** | Mencampur aduk semua subtype ke satu skema tanpa diskriminator jelas. | Query index sparsity tinggi; index membesar (*bloated*) karena sebagian besar field bernilai `null` / tidak ada. | **Polymorphic Pattern with Schema Discriminator**: Penyatuan koleksi dengan struktur deterministik berbasis field `type`. |

Pola skema lanjutan dirancang untuk:
1. **Menghilangkan disk I/O acak** dengan memastikan dokumen yang sering diakses bersama disimpan dalam satu blok penyimpanan contiguous.
2. **Memaksimalkan Working Set Efficiency**: Memastikan hanya data aktif (*hot data*) yang berada di memori WiredTiger Cache.
3. **Mencegah Unbounded Array Growth**: Menjamin dokumen stabil dalam batas ukuran terprediksi sepanjang siklus hidup sistem.

---

### 5. How (Workflow Detail)

#### Implementasi Pola Terpadu: Bucket + Outlier + Computed Pattern

Workflow berikut menguraikan arsitektur penanganan data *streaming high-throughput* (contoh: log transaksi, analitik IoT) yang memiliki lonjakan volume abnormal (*outliers*):

```
+--------------------------------------------------------------------+
| Incoming Event Stream (Sensor Data / Financial Ticks)              |
+--------------------------------------------------------------------+
                                  |
                                  v
+--------------------------------------------------------------------+
| Step 1: Pre-aggregation & Threshold Checking Engine                |
| - Verifikasi apakah Bucket saat ini sudah penuh (count == 1000)    |
| - Verifikasi anomali: apakah event berukuran > ambang batas normal?|
+--------------------------------------------------------------------+
           |                                             |
     [Normal Size]                               [Outlier Size]
           |                                             |
           v                                             v
+-------------------------------------+   +--------------------------+
| Step 2A: Write to Standard Bucket   |   | Step 2B: Route to        |
| - Gunakan `updateOne` upsert        |   | Outlier Collection       |
| - Operator: $push (Bounded $slice)  |   | - Simpan payload besar   |
| - Hitung state: $inc, $min, $max    |   |   secara direct reference|
+-------------------------------------+   | - Set flag: outlier: true|
           |                              +--------------------------+
           v                                             |
+--------------------------------------------------------------------+
| Step 3: Materialization to WiredTiger Cache                        |
| - Dokumen bucket memiliki ukuran terprediksi (~120 KB)             |
| - Menghindari fragmentasi memory & page split                      |
+--------------------------------------------------------------------+
```

1. **Bucket Initialization**: Alih-alih membuat satu dokumen per event, buat dokumen penampung (*bucket*) yang merepresentasikan interval waktu (misal: per jam) atau jumlah kuantitas tertentu (misal: 500 item per bucket).
2. **Atomic Ingest via Aggregation Operators**:
   * Gunakan `$setOnInsert` untuk mengunci metadata statis (device ID, start time).
   * Gunakan `$push` dipadukan dengan modifier `$slice` dan `$sort` untuk menjaga batas ukuran array di dalam dokumen.
   * Gunakan `$inc`, `$min`, `$max` secara serentak untuk menghasilkan metrik *Computed* real-time tanpa parsing ulang isi bucket saat read.
3. **Outlier Mitigation**:
   * Jika ada perangkat yang mengirimkan data anomali (misal: log debug 5 MB alih-alih 200 byte), rute dialihkan ke koleksi `telemetry_outliers`.
   * Dokumen bucket utama hanya menyimpan *extended reference* ke ID outlier tersebut dan menaikkan flag Boolean `has_overflow: true`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Lemari Arsip Gudang (WiredTiger Cache & Document Growth)

* **Skema Naif (Unbounded Array)**: Anda memiliki binder lipat. Setiap kali ada surat masuk, Anda menyelipkannya ke dalam binder tersebut. Lama kelamaan binder menjadi setebal 2 meter. Saat Anda ingin menambahkan satu lembar kertas, binder tidak muat lagi di rak. Gudang terpaksa mengeluarkan binder, membongkar rak, menggeser binder lain, lalu menaruh binder baru di lantai. (*Page split, high disk fragmentation, cache eviction stall*).
* **Pola Bucket & Subset**: Anda membatasi bahwa 1 map hanya boleh berisi tepat 100 lembar surat. Begitu lembar ke-101 datang, Anda wajib mengambil map baru dengan kode barcode lanjutan. Rak tersusun rapi, ukuran map standar, staf gudang dapat mengambil map secara cepat dan memindahkannya ke rak arsip dingin tanpa merusak tatanan rak utama.

```
Pola Unbounded (Anti-Pattern):
[ Doc A (10KB) ] -> Push -> [ Doc A (64KB) ] -> Push -> [ Doc A (16MB Crash) ]
  (In-place)               (Memory Re-alloc)            (FATAL: BSON Size Exceeded)
                                                         WiredTiger Cache Stalls!

Pola Bounded Bucket (Production Standard):
Collection: sensor_buckets
+-------------------------------------------------------------------------------+
| _id: device_101_2026_03_30_08                                                 |
| range: [2026-03-30T08:00:00Z - 2026-03-30T08:59:59Z]                         |
| count: 500 (MAX_BOUNDED)                                                      |
| metrics: { min: 18.2, max: 29.4, sum: 11200.5, avg: 22.401 }                 |
| samples: [                                                                    |
|    { t: 0, v: 22.1 }, { t: 1, v: 22.4 }, ... (fixed size elements)            |
| ]                                                                             |
+-------------------------------------------------------------------------------+
  Ukuran BSON terkunci konstan (~48KB). Memori dialokasikan secara homogen.
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Schema Versioning Pattern (TypeScript)

Berikut pola penanganan evolusi skema dokumen secara zero-downtime tanpa script migrasi massal yang membebani database:

```typescript
import { MongoClient, Db, ObjectId } from 'mongodb';

interface UserV1 {
  _id: ObjectId;
  schemaVersion: 1;
  name: string; // Bentuk gabungan lama
  email: string;
}

interface UserV2 {
  _id: ObjectId;
  schemaVersion: 2;
  firstName: string; // Transformasi pemisahan nama
  lastName: string;
  email: string;
  normalizedEmail: string;
}

type UserDocument = UserV1 | UserV2;

export class UserRepository {
  constructor(private db: Db) {}

  private get collection() {
    return this.db.collection<UserDocument>('users');
  }

  // Lazy Schema Migration Read Adapter
  async findByIdAndMigrate(id: ObjectId): Promise<UserV2 | null> {
    const rawDoc = await this.collection.findOne({ _id: id });
    if (!rawDoc) return null;

    if (rawDoc.schemaVersion === 2) {
      return rawDoc as UserV2;
    }

    // Eksekusi mutasi skema on-the-fly (Lazy Migration)
    if (rawDoc.schemaVersion === 1) {
      const v1 = rawDoc as UserV1;
      const [firstName, ...lastNames] = v1.name.split(' ');
      
      const v2Payload: UserV2 = {
        _id: v1._id,
        schemaVersion: 2,
        firstName: firstName || 'N/A',
        lastName: lastNames.join(' ') || '',
        email: v1.email,
        normalizedEmail: v1.email.trim().toLowerCase(),
      };

      // Tulis balik secara asinkron tanpa memblokir pembacaan utama
      await this.collection.replaceOne({ _id: v1._id }, v2Payload);
      return v2Payload;
    }

    throw new Error(`Unsupported schema version: ${(rawDoc as any).schemaVersion}`);
  }
}
```

#### B. Practical Example: Production Telemetry Ingest Engine (Bucket + Computed Pattern)

Contoh sistem produksi untuk menangani jutaan metrik IoT dengan atomisitas level enterprise, penghitungan agregat langsung di database (*in-flight computation*), dan pemotongan batas kapasitas.

```typescript
import { MongoClient, Db, UpdateFilter } from 'mongodb';

export interface TelemetryReading {
  timestamp: Date;
  voltage: number;
  current: number;
}

export interface MetricBucketDocument {
  deviceId: string;
  bucketStartTime: Date;
  bucketEndTime: Date;
  count: number;
  stats: {
    minVoltage: number;
    maxVoltage: number;
    sumVoltage: number;
    avgVoltage: number;
  };
  readings: TelemetryReading[];
}

export class TelemetryIngestionService {
  private static readonly MAX_BUCKET_SIZE = 1000;

  constructor(private db: Db) {}

  private get buckets() {
    return this.db.collection<MetricBucketDocument>('device_telemetry_buckets');
  }

  /**
   * Menginjeksi pembacaan sensor secara atomik.
   * Menggunakan pola Bucket terkontrol dengan dynamic upsert windowing.
   */
  async ingestMetric(deviceId: string, reading: TelemetryReading): Promise<void> {
    // Rounding timestamp ke awal jam untuk deterministic windowing
    const bucketHour = new Date(reading.timestamp);
    bucketHour.setMinutes(0, 0, 0, 0);

    const filter = {
      deviceId,
      bucketStartTime: bucketHour,
      count: { $lt: TelemetryIngestionService.MAX_BUCKET_SIZE }
    };

    const update: UpdateFilter<MetricBucketDocument> = {
      $setOnInsert: {
        deviceId,
        bucketStartTime: bucketHour,
        bucketEndTime: new Date(bucketHour.getTime() + 60 * 60 * 1000 - 1)
      },
      $inc: {
        count: 1,
        'stats.sumVoltage': reading.voltage
      },
      $min: {
        'stats.minVoltage': reading.voltage
      },
      $max: {
        'stats.maxVoltage': reading.voltage
      },
      $push: {
        readings: {
          $each: [reading],
          $slice: TelemetryIngestionService.MAX_BUCKET_SIZE
        }
      }
    };

    const result = await this.buckets.updateOne(filter, update, { upsert: true });

    // Edge-case recovery: Jika bucket sudah penuh (count >= 1000) dan upsert gagal 
    // karena balapan kunci unique, buat bucket sekunder dengan offset millisecond.
    if (!result.acknowledged) {
      throw new Error(`Write pipeline failed to acknowledge for device: ${deviceId}`);
    }
  }

  /**
   * Ekstraksi metrik agregat instan O(1) tanpa memindai seluruh array
   */
  async getDeviceAggregates(deviceId: string, startHour: Date, endHour: Date) {
    return this.buckets.aggregate([
      {
        $match: {
          deviceId,
          bucketStartTime: { $gte: startHour, $lte: endHour }
        }
      },
      {
        $project: {
          bucketStartTime: 1,
          count: 1,
          minVoltage: '$stats.minVoltage',
          maxVoltage: '$stats.maxVoltage',
          avgVoltage: {
            $divide: ['$stats.sumVoltage', '$count']
          }
        }
      },
      { $sort: { bucketStartTime: 1 } }
    ]).toArray();
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Sistem Logistik & Rantai Pasok Global (Fleet & Parcel Tracking)
* **Konteks**: Perusahaan logistik global memantau 500.000 armada truk pengiriman. Setiap truk mengirim koordinat geospasial, temperatur muatan, dan status mesin setiap 5 detik. Total event per hari: **8,64 miliar dokumen**.
* **Problem**: Awalnya tim mengadopsi model relasional terdistribusi dan kemudian beralih ke MongoDB murni satu-dokumen-per-event. 
  * *Dampak Fatal*: Koleksi membengkak hingga 4 TB per hari. RAM server 512 GB tersaturasi penuh dalam waktu 3 jam akibat working set cache thrashing. Latensi query agregasi historis armada mencapai 45 detik. Batas IOPS SSD NVMe terlampaui karena pembacaan terus-menerus ke blok disk yang terfragmentasi.

```
ARUS DATA TRUK (5 DETIK SEKALI)
                |
                v
+-------------------------------+
|  Ingest Gateway API (Node.js) |
+-------------------------------+
                |
                +----------------------------+
                | Routing Berdasarkan Status |
                v                            v
  [ Payload Standar (<1 KB) ]     [ Crash/Engine Diagnostic (>50 KB) ]
                |                            |
                v                            v
+-------------------------------+  +---------------------------------+
| Collection: fleet_telemetry   |  | Collection: fleet_telemetry_raw |
| (Bucket Pattern: 720 points   |  | (Direct Point Writes)           |
|  = 1 jam data per dokumen)    |  | (Outlier Pattern Reference)     |
+-------------------------------+  +---------------------------------+
                |                                  |
                +-----------------+----------------+
                                  v
+--------------------------------------------------------------------+
| Aggregation Dashboard via Computed Metadata Cache                 |
| Rata-rata response query historis: 8ms (Turun dari 45 detik)       |
+--------------------------------------------------------------------+
```

* **Solusi Arsitektur Menggunakan Pattern Synergy**:
  1. **Bucket Pattern**: Data di-chunk per 1 jam per truk (720 titik sampel per dokumen BSON). Ukuran dokumen terkunci pada ~65 KB.
  2. **Computed Pattern**: Di tingkat dokumen bucket, dihitung langsung `totalDistanceKm`, `maxSpeedKmh`, dan `minEngineTemp` secara atomic via `$inc` dan `$max`.
  3. **Outlier Pattern**: Jika terjadi insiden kritis (misal tabrakan kendaraan), paket telemetri menyertakan crash-dump berukuran besar (>50 KB). Logika gateway memotong payload besar ini ke koleksi `fleet_telemetry_raw` dan hanya menanamkan `outlierRefId` pada array bucket normal.
* **Hasil Produksi**:
  * Volume dokumen turun drastis dari 8,64 miliar menjadi **12 juta dokumen per hari**.
  * Ruang disk terpangkas 78% berkat kompresi Snappy yang bekerja optimal pada array struktur homogen.
  * Query jejak rute armada 24 jam hanya memerlukan 24 pembacaan dokumen BSON (sebelumnya membutuhkan 17.280 dokumen), memangkas *Execution Time* dari **45.000 ms menjadi 8 ms**.

---

### 9. Trade-offs

Setiap keputusan desain skema adalah kompromi arsitektural. Berikut analisis trade-off formal:

| Pendekatan Desain Skema | Keuntungan Utama | Kerugian / Trade-off | Dampak Resource (CPU/RAM/IO) | Kapan Harus Digunakan |
| :--- | :--- | :--- | :--- | :--- |
| **Pola Bucket Terkompresi** | Read I/O efisien; volume dokumen drop drastis; index footprint sangat kecil. | Kerumitan penulisan query `$slice`; sulit memanipulasi titik sampel individual di tengah array. | **RAM**: Sangat rendah.<br>**CPU**: Sedang (karena operasi array).<br>**Disk IO**: Minimal. | Time-series, metrik IoT, clickstream logs, chat audit logs. |
| **Materialized Path (Pohon/Hierarki)** | Query pencarian hierarki (seperti: "cari semua anak dari cabang X") instan via regex prefix index. | Update struktur pohon (memindahkan node) mahal karena memerlukan mutasi cascading pada path semua anak. | **RAM**: Rendah.<br>**CPU**: Tinggi saat mutasi struktur.<br>**Disk IO**: Menengah. | Kategori e-commerce, struktur organisasi statis. |
| **Array of Ancestors (Pohon/Hierarki)** | Sangat mudah menemukan seluruh parent; pembacaan query breadcrumb instan via satu index array. | Sinkronisasi multi-level deep update berisiko inkonsistensi jika tidak diisolasi via transaksi. | **RAM**: Menengah.<br>**CPU**: Rendah.<br>**Disk IO**: Menengah. | File system directories, navigasi hierarki multi-tier. |
| **Outlier Pattern (Document Splitting)** | Menjaga ukuran dokumen utama seragam; mencegah limit 16 MB secara deterministik. | Memerlukan logika aplikasi untuk mengecek pointer/flag outlier; query fallback read 2 kali. | **RAM**: Optimal.<br>**CPU**: Sedang (aplikasi layer routing).<br>**Disk IO**: Sedikit meningkat untuk outlier. | Akun selebriti media sosial, entitas finansial anomali, event log raksasa. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Unbounded Array Menggunakan `$push` Sederhana
* **Gejala**: CPU spike periodik, I/O disk tinggi pada operasi update reguler, fragmentasi koleksi melonjak (*storageSize* jauh lebih besar daripada *dataSize*).
* **Akar Masalah**: Array terus bertambah seiring waktu tanpa batas. WiredTiger terpaksa mengalokasikan ulang halaman dokumen berulang kali di memori dan memicu alokasi disk non-contiguous.
* **Solusi Perbaikan**: Gunakan kombinasi modifier `$each` dan `$slice` untuk membatasi ukuran array maksimal dokumen:
  ```javascript
  // Fix: Array dibatasi maksimal 100 elemen terakhir
  db.audit_logs.updateOne(
    { userId: targetUserId },
    {
      $push: {
        events: {
          $each: [newEvent],
          $sort: { timestamp: -1 },
          $slice: 100
        }
      }
    }
  );
  ```

#### Kesalahan 2: Menggunakan Hierarki Parent-Reference dengan `$graphLookup` Tanpa Batas Kedalaman (*Depth Limit*)
* **Gejala**: Query graph tiba-tiba menghasilkan *OOM (Out Of Memory)* error dan menghentikan mongod instance (*killed by Linux OOM-killer*).
* **Akar Masalah**: `$graphLookup` terjebak dalam circular dependency loop atau menelusuri ratusan ribu edge pohon secara recursive tanpa batas memori internal.
* **Solusi Perbaikan**: Tetapkan selalu parameter `maxDepth` dan implementasikan validasi cycle prevention:
  ```javascript
  db.categories.aggregate([
    { $match: { _id: rootId } },
    {
      $graphLookup: {
        from: "categories",
        startWith: "$_id",
        connectFromField: "_id",
        connectToField: "parentId",
        as: "descendants",
        maxDepth: 5, // Batasi kedalaman traversal
        depthField: "hierarchyLevel"
      }
    }
  ]);
  ```

#### Kesalahan 3: Tidak Menyediakan Schema Discriminator pada Polymorphic Pattern
* **Gejala**: Developer menggunakan pola `$or` multi-kondisi yang lambat dan gagal memanfaatkan compound index untuk tipe polymorphic yang berbeda.
* **Akar Masalah**: Tidak adanya field skema eksplisit (misal: `kind` atau `schemaType`) membuat query harus memeriksa keberadaan field tertentu menggunakan `$exists: true` yang tidak efisien.
* **Solusi Perbaikan**: Tambahkan discriminator wajib di tingkat root dan pasang compound partial index:
  ```javascript
  // Buat index berbasis discriminator
  db.payment_methods.createIndex(
    { provider: 1, routingNumber: 1 },
    { partialFilterExpression: { type: "BANK_TRANSFER" } }
  );
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis skema database ke environment produksi:

- [ ] **BSON 16 MB Safety Net**: Apakah dokumen memiliki array berpotensi tanpa batas (*unbounded*)? Jika ya, implementasikan pola *Bucket* atau *Subset*.
- [ ] **Short Key Aliasing vs Compression**: Pada skema ingestion massal (>1.000.000 ops/hari), perpendek nama key BSON jika WiredTiger compression level dikonfigurasi ke Snappy/None, atau evaluasi Zstandard jika memprioritaskan disk footprint.
- [ ] **Deterministic Working Set**: Pastikan index dan hot-data muat di dalam kapasitas WiredTiger Cache (`(Total RAM - 1GB) * 50%`).
- [ ] **Penyertaan Field Schema Version**: Setiap dokumen harus memiliki field `schemaVersion: <Number>` untuk mendukung migrasi zero-downtime.
- [ ] **Index Sparsity Mitigation**: Gunakan Partial Indexes untuk sub-dokumen atau field opsional ketimbang membiarkan B-Tree dipenuhi entri `null`.
- [ ] **Atomic Aggregations Check**: Hindari membaca array dokumen ke server aplikasi hanya untuk menghitung panjang array atau rata-rata; gunakan `$inc` dan `$computed` langsung di write-pipeline.
- [ ] **Write Concern Tuning**: Pastikan skema yang menggunakan Bucket terkompresi ditulis minimal dengan `{ w: "majority", j: true }` untuk mencegah dirty-read rollback pada saat node failover.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`.

#### Langkah 1: Setup Environment
Inisialisasi workspace di direktori `hands-on/m02/`:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install mongodb typescript @types/node ts-node
npx tsc --init
```

#### Langkah 2: Buat File Migrasi Pohon Hierarki & Ingestion (`hands-on/m02/hierarchical_engine.ts`)
Implementasikan skema hierarki kategori dengan pola *Materialized Path* terindeks dan sistem mutasi path otomatis:

```typescript
import { MongoClient, ObjectId, Db } from 'mongodb';

export interface CategoryNode {
  _id: ObjectId;
  name: string;
  path: string; // Format: ,Electronics,Computers,Laptops,
  parentName: string | null;
  updatedAt: Date;
}

export class CategoryTreeService {
  constructor(private db: Db) {}

  private get collection() {
    return this.db.collection<CategoryNode>('hierarchical_categories');
  }

  async setupIndices() {
    // Prefix index sangat efisien untuk query regex "^,Path,"
    await this.collection.createIndex({ path: 1 });
  }

  async insertCategory(name: string, parentPath: string | null = null): Promise<ObjectId> {
    const calculatedPath = parentPath ? `${parentPath}${name},` : `,${name},`;
    const doc: CategoryNode = {
      _id: new ObjectId(),
      name,
      path: calculatedPath,
      parentName: parentPath ? parentPath.split(',').filter(Boolean).pop() || null : null,
      updatedAt: new Date()
    };
    
    await this.collection.insertOne(doc);
    return doc._id;
  }

  // Mengambil seluruh turunan (sub-tree) dari cabang tertentu
  async findSubTree(categoryPath: string): Promise<CategoryNode[]> {
    return this.collection.find({
      path: { $regex: new RegExp(`^${categoryPath}`) }
    }).toArray();
  }

  // Mutasi pemindahan cabang (Reparenting) dengan cascading path rewrite
  async moveSubTree(oldPath: string, newBasePath: string): Promise<void> {
    const nodes = await this.findSubTree(oldPath);
    
    for (const node of nodes) {
      const updatedPath = node.path.replace(oldPath, newBasePath);
      await this.collection.updateOne(
        { _id: node._id },
        { 
          $set: { 
            path: updatedPath,
            updatedAt: new Date()
          } 
        }
      );
    }
  }
}

async function run() {
  const uri = process.env.MONGO_URI || 'mongodb://localhost:27017';
  const client = new MongoClient(uri);

  try {
    await client.connect();
    const db = client.db('enterprise_patterns');
    const service = new CategoryTreeService(db);

    console.log('--- Setting up Hierarchy Engine ---');
    await service.setupIndices();

    // Buat Top-Level
    await service.insertCategory('EnterpriseHardware');
    // Buat Children
    await service.insertCategory('Servers', ',EnterpriseHardware,');
    await service.insertCategory('BladeServers', ',EnterpriseHardware,Servers,');
    await service.insertCategory('RackServers', ',EnterpriseHardware,Servers,');

    console.log('Querying sub-tree under Servers:');
    const serversSubTree = await service.findSubTree(',EnterpriseHardware,Servers,');
    console.table(serversSubTree, ['name', 'path']);

    console.log('Executing Reparenting: Moving Servers under Root level Infrastructure...');
    await service.moveSubTree(',EnterpriseHardware,Servers,', ',Infrastructure,Servers,');

    const updatedSubTree = await service.findSubTree(',Infrastructure,Servers,');
    console.table(updatedSubTree, ['name', 'path']);

  } finally {
    await client.close();
  }
}

run().catch(console.error);
```

#### Langkah 3: Eksekusi
Jalankan skrip menggunakan `ts-node`:
```bash
npx ts-node hands-on/m02/hierarchical_engine.ts
```

---

### 13. Exercise

#### Level: Easy
Diberikan koleksi `users` yang memiliki array riwayat login `loginHistory` tanpa batas. Modifikasi perintah pembaruan berikut agar hanya menyimpan **10 data login terakhir** (terurut dari yang terbaru):
```javascript
// Data Masuk
const loginEvent = { ip: "192.168.1.1", loggedAt: new Date() };

// Tuliskan MongoDB update query yang menggunakan operator $each, $sort, dan $slice
```

#### Level: Medium
Sebuah platform E-Commerce memiliki koleksi dokumen produk dengan ragam atribut bervariasi (Pakaian: ukuran, bahan, warna; Komputer: RAM, CPU, Storage). 
* Rancang skema menggunakan **Attribute Pattern** untuk field spesifikasi teknis dinamis.
* Buat *Compound Index* yang memungkinkan pencarian cepat berdasarkan nama atribut dan nilai atribut tanpa membuat index individual untuk tiap atribut baru.

#### Level: Hard
Kembangkan script pipeline agregasi zero-downtime background migration dari format skema V1 ke format skema V2 pada koleksi sebesar 10 juta dokumen:
* V1: `{ _id: 1, address: "Jl. Sudirman No 1, Jakarta, 10220" }`
* V2: `{ _id: 1, address: { street: "Jl. Sudirman No 1", city: "Jakarta", postalCode: "10220" }, schemaVersion: 2 }`
* Skrip harus berjalan menggunakan mekanisme **Batch Throttling** (memproses per 5.000 dokumen dengan `bulkWrite`), tidak memicu lock contention pada WiredTiger, dan mencatat checkpoint ID terakhir jika migrasi terhenti di tengah jalan.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Database Architect untuk sistem *Core Banking Ledger* multi-cabang.
* Sistem harus mencatat jutaan mutasi rekening per hari.
* Saldo rekening tidak boleh dihitung dengan cara mengunci baris (*row lock*) dan melakukan update langsung ke satu field saldo pusat, karena ini menyebabkan kegagalan konkurensi masif (*write ticket depletion* di WiredTiger) saat ratusan transaksi terjadi di detik yang sama pada rekening penampung (*hot account*).
* Setiap dokumen tidak boleh melebihi batas BSON 16 MB.
* Audit trail harus bersifat *immutable* (tidak boleh ada update fisik yang menimpa dokumen yang sudah ditulis).

**Tantangan**:
1. Buat arsitektur skema perpaduan antara **Bucket Pattern** (untuk mengelompokkan riwayat mutasi per blok transaksi) dan **Delta Sharded Counters** (untuk mengurai kontensi saldo).
2. Tuliskan desain skema lengkap beserta spesifikasi index-nya.
3. Rancang mekanisme rekonsiliasi yang menghitung saldo konsisten akun secara real-time pada level read concern `majority` dengan latensi di bawah 15 ms, tanpa pernah melakukan *full collection scan*.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Berapa ukuran dokumen BSON maksimum absolut yang dialokasikan oleh MongoDB?
   * A. 8 MB
   * B. 16 MB
   * C. 32 MB
   * D. 64 MB

2. Algoritma kompresi default yang digunakan oleh storage engine WiredTiger untuk data collection adalah:
   * A. Gzip
   * B. Zstandard
   * C. Snappy
   * D. LZ4

3. Operator mutasi array mana yang digunakan untuk membatasi panjang array secara deterministik saat melakukan push?
   * A. `$limit`
   * B. `$cut`
   * C. `$trim`
   * D. `$slice`

4. Mengapa representasi BSON di dalam WiredTiger Cache lebih besar dibandingkan representasi data di disk?
   * A. Data di memori cache tidak terkompresi dan memuat pointer metadata dereference.
   * B. MongoDB menduplikasi data 3 kali di dalam RAM.
   * C. WiredTiger menyimpan seluruh log journal di dalam RAM dokumen.
   * D. Dokumen BSON dienkripsi secara penuh di memori.

5. Field yang umum digunakan dalam *Schema Versioning Pattern* untuk mendeteksi struktur payload dokumen secara programatis adalah:
   * A. `_id`
   * B. `schemaVersion`
   * C. `__v`
   * D. `classRef`

#### Bagian 2: Intermediate (Pilihan Ganda)
6. Kapan *Page Split* internal terjadi pada B-Tree WiredTiger?
   * A. Saat checkpoint 60 detik tercapai.
   * B. Ketika operasi update/insert menyebabkan dokumen membesar melampaui ukuran halaman B-Tree maksimum.
   * C. Saat koneksi aplikasi ditutup secara mendadak.
   * D. Ketika indeks multikey dihapus secara manual.

7. Apa tujuan utama dari penerapan *Outlier Pattern*?
   * A. Menghapus data histori yang sudah tidak pernah diakses.
   * B. Memisahkan segelintir dokumen yang ukurannya melonjak ekstrim dari kumpulan dokumen standar untuk mencegah penurunan performa massal.
   * C. Menggabungkan ratusan dokumen kecil menjadi satu dokumen raksasa.
   * D. Menghindari pembuatan compound index.

8. Dalam pemodelan hierarki pohon, pola manakah yang paling ideal untuk query yang mengutamakan kecepatan pencarian seluruh subtree menggunakan pola Prefix Index Regex?
   * A. Parent References Pattern
   * B. Child References Pattern
   * C. Materialized Path Pattern
   * D. Normalized Foreign Key Pattern

9. Apa dampak langsung terhadap WiredTiger storage engine jika aplikasi sering melakukan modifikasi dokumen yang memicu pertambahan ukuran (*Out-of-place allocation*)?
   * A. Meningkatnya fragmentasi internal, memicu dirty cache eviction berlebih, dan degradasi latensi I/O.
   * B. Hilangnya Write-Ahead Log (Journal).
   * C. Otomatis terjadi restart pada process mongod.
   * D. Storage engine beralih ke mode read-only.

10. Mengapa Pola *Bucket* sangat direkomendasikan untuk data time-series dibanding menyimpan 1 dokumen per 1 titik data?
    * A. Karena MongoDB tidak mendukung indexing pada tipe data waktu.
    * B. Mengurangi metadata overhead BSON, mengecilkan ukuran index secara drastis, dan memanfaatkan kompresi storage secara maksimal.
    * C. Agar query wajib menggunakan aggregate `$lookup`.
    * D. Mencegah dokumen dibaca oleh replica set secondary node.

#### Bagian 3: Skenario Kasus Produksi (Analisis Arsitektur)

11. **Skenario 1**: Sebuah startup e-commerce meluncurkan flash-sale global. Sistem mereka mencatat lonjakan traffic tajam, dan monitoring menunjukkan `writeTickets` pada WiredTiger turun menjadi 0 (depleted), mengakibatkan seluruh request aplikasi antre (*connection queue explosion*). Investigasi menemukan bahwa skrip mencatat order id ke dalam sebuah array tunggal di dokumen profil penjual `merchant.orders.push(orderId)`. Analisis akar masalah internal WiredTiger dan berikan solusi skema yang benar.

12. **Skenario 2**: Anda diminta merekayasa ulang skema database dokumen katalog produk yang memiliki 5.000 jenis barang dengan spesifikasi yang sangat acak (polymorphic). Jelaskan bagaimana Anda mendesain skema dan konfigurasi indeksnya agar pengguna dapat melakukan filter kombinasi atribut (misal: "Color: Red" dan "ScreenSize: 15-inch") tanpa menimbulkan *index explosion* (pembuatan ratusan indeks tunggal untuk setiap field atribut).

13. **Skenario 3**: Sebuah bank digital ingin mengubah struktur penyimpanan dokumen nasabah dari skema V1 ke V2. Basis data memiliki 40 juta dokumen nasabah dan sistem memiliki SLA ketersediaan 99.999% (toleransi downtime maksimal ~5 menit per tahun). Jelaskan arsitektur migrasi bertahap (*Zero-Downtime Migration Architecture*) yang harus dieksekusi oleh tim engineering tanpa mengunci database dan tanpa membebani kapasitas RAM server.

---

### Kunci Jawaban & Panduan Pembahasan Quiz

#### Bagian 1: Basic
1. **B (16 MB)** - Batas dokumen BSON individual tunggal di MongoDB dibatasi secara hard-coded sebesar 16 megabyte untuk mencegah pemborosan memori dan latensi transfer jaringan yang ekstrem.
2. **C (Snappy)** - Snappy adalah algoritma kompresi default WiredTiger yang mengutamakan trade-off seimbang antara rasio kompresi dan konsumsi CPU minimal.
3. **D (`$slice`)** - Modifier `$slice` digunakan bersama `$push` untuk memotong dan membatasi ukuran array maksimum dalam operasi atomic update.
4. **A** - Di disk data terkompresi, namun saat ditarik ke WiredTiger Cache, data diekstrak menjadi struktur raw B-Tree uncompressed yang menampung pointer internal sistem operasi.
5. **B (`schemaVersion`)** - Merupakan konvensi standar industri untuk membedakan bentuk dokumen pada database schemaless.

#### Bagian 2: Intermediate
6. **B** - Page split adalah mekanisme alokasi ulang halaman saat dokumen tumbuh melewati batas slot halaman B-Tree di memory.
7. **B** - Mengisolasi entitas anomali (misal: akun Twitter selebriti dengan jutaan follower) ke koleksi terpisah agar 99% data pengguna normal lainnya memiliki ukuran dan performa seragam.
8. **C (Materialized Path Pattern)** - Menyimpan jalur hierarki lengkap (contoh: `,A,B,C,`) memungkinkan pencarian seluruh subtree di bawah node B cukup dengan query prefix regex `{ path: /^,A,B,/ }` yang dapat menggunakan index secara optimal.
9. **A** - Realokasi out-of-place meninggalkan ruang kosong (dead space) yang belum dipadatkan, memaksa cache worker melakukan komparasi hazard pointers dan eviction konstan.
10. **B** - Menggabungkan event ke dalam bucket mengeliminasi repetisi key BSON, menurunkan IOPS disk, dan memungkinkan kompresi beruntun pada tipe data yang serupa.

#### Bagian 3: Skenario Kasus Produksi (Panduan Evaluasi)
11. **Analisis Skenario 1**: 
    * *Akar Masalah*: Dokumen merchant menjadi *hot document* dengan ukuran yang membengkak cepat via `$push` tanpa batas. Ini memaksa WiredTiger mengunci dokumen secara eksklusif (exclusive write intent) berulang kali untuk melakukan out-of-place memory reallocation. Karena dokumen terkunci lama di RAM, thread write lain kehabisan tiket eksekusi (`writeTickets: 0`), memicu antrean cascading pada layer pooling aplikasi.
    * *Solusi*: Hilangkan array `orders` dari dokumen merchant. Balikkan relasi menjadi *Reference Pattern*: setiap dokumen order menyimpan referensi `merchantId`. Tambahkan index `{ merchantId: 1, createdAt: -1 }`. Dokumen merchant hanya menyimpan status agregat ringkas (*Computed Pattern*).
12. **Analisis Skenario 2**:
    * Gunakan **Attribute Pattern**. Representasikan spesifikasi teknis dalam bentuk key-value array:
      `specs: [ { k: "color", v: "red" }, { k: "screenSize", v: 15 } ]`.
    * Pasang satu *Compound Multikey Index*: `{ "specs.k": 1, "specs.v": 1 }`.
    * Query filter memanfaatkan index yang sama:
      `db.products.find({ specs: { $all: [ { $elemMatch: { k: "color", v: "red" } }, { $elemMatch: { k: "screenSize", v: 15 } } ] } })`. Pola ini menghentikan *index explosion*.
13. **Analisis Skenario 3**:
    * Terapkan strategi migrasi **3-Phase Zero-Downtime Migration**:
      1. *Phase 1 (Code Deployment)*: Update service aplikasi dengan pola *Lazy Migration* (Read-Repair) dan *Dual-Write*. Setiap pembacaan dokumen V1 dikonversi secara on-the-fly di memory dan disimpan kembali ke format V2. Setiap dokumen baru langsung ditulis dalam format V2.
      2. *Phase 2 (Background Asynchronous Batch)*: Jalankan batch worker terpisah yang membaca dokumen bertahap per batch kecil (misal: 1.000 dokumen via cursor dengan parameter `batchSize`, diproses menggunakan `bulkWrite`) hanya untuk dokumen yang masih memiliki `schemaVersion: 1`. Sisipkan sleep throttling (misal 50ms per batch) agar pemakaian resource server database di bawah 30%.
      3. *Phase 3 (Cleanup)*: Setelah worker selesai memverifikasi tidak ada dokumen dengan format V1, hapus kode backward compatibility V1 dari aplikasi. Zero downtime dicapai tanpa lock database global.

---

### 16. Summary

1. **Simetri Desain Skema & Storage Engine**: Desain skema dokumen di tingkat aplikasi menentukan siklus hidup data pada level memori terkelola WiredTiger Cache, frekuensi alokasi B-Tree page splits, dan efisiensi throughput I/O disk.
2. **Pertahanan Melawan Unbounded Growth**: Array tanpa batas (*Unbounded Array*) adalah anti-pattern fatal pada MongoDB enterprise scale. Penggunaan operator `$push` dengan modifier `$slice` dan penerapan *Bucket Pattern* adalah mekanisme mutlak untuk menjamin stabilitas dokumen.
3. **Pola Tingkat Lanjut Terpadu**: Kombinasi pola *Bucket*, *Outlier*, dan *Computed* secara atomik mampu mendongkrak performa ingest streaming hingga ribuan kali lipat sekaligus meniadakan komputasi agregasi yang mahal saat proses pembacaan.
4. **Schema Evolution Zero-Downtime**: Menjaga integritas operasional enterprise membutuhkan strategi evolusi skema berbasis versi (*Schema Versioning*) yang mengandalkan teknik mutasi bertahap (*Lazy Read-Repair* dan *Background Batching*) tanpa pernah menghentikan traffic layanan produksi.