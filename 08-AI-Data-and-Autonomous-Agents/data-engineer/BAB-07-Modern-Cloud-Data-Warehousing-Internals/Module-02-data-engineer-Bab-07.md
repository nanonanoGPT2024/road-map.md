# BAB 07: Modern Cloud Data Warehousing Internals
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Membedah dan menganalisis arsitektur internal *storage-compute decoupling* pada *cloud data warehouse* (Snowflake, Google BigQuery, Databricks Photon, AWS Redshift Serverless).
- Menganalisis layout penyimpanan kolumnar (*columnar storage format*), skema encoding/kompresi (Dictionary, Bit-Packing, Run-Length Encoding), serta mekanisme metadata pruning (*micro-partitioning* dan *zone maps*).
- Mengonfigurasi dan mengoptimasi strategi *clustering*, *partitioning*, serta *liquid clustering* untuk mencegah degradasi performa pada tabel berskala multi-petabyte.
- Mendiagnosis dan mengeliminasi *query bottlenecks* menggunakan analisis *Query Execution Plan* dan *Profile* (misal: *data spilling to local disk/remote storage*, *cartesian join explosions*, *shuffle skew*).
- Merancang arsitektur multi-cluster warehouse terisolasi (*workload isolation*) dengan tata kelola biaya (*FinOps cost attribution*), failover otomatis, dan kontrol konkurensi tingkat lanjut.

---

### 2. Prerequisite
Untuk memahami modul ini secara komprehensif, Anda wajib menguasai:
- **Distributed Computing Fundamentals**: Konsep shared-nothing vs shared-disk, MPP (Massively Parallel Processing), shuffle/exchange operators, dan CAP theorem.
- **Relational Algebra & Advanced SQL**: Query optimization, window functions, analytical aggregation, join algorithms (Broadcast Hash Join, Shuffle Hash Join, Sort-Merge Join).
- **Storage Systems**: Karakteristik throughput dan latency dari cloud object storage (Amazon S3, Google Cloud Storage, Azure Blob Storage) vs ephemeral NVMe/SSD cache.
- **Data Serialization Formats**: Pemahaman mendasar tentang Apache Parquet, ORC, dan format hybrid berpemilik (*proprietary*) seperti Google Capacitor dan Snowflake FDN.

---

### 3. Concept & Internal Architecture (Mendalam)

Modern Cloud Data Warehouse (CDW) tidak lagi mengadopsi arsitektur *Shared-Nothing* klasik (di mana disk dan compute terikat pada satu node fisik). Sebaliknya, CDW modern menerapkan **Multi-Cluster Shared-Data Architecture**. Arsitektur ini memisahkan sistem ke dalam tiga lapisan decoupled:

```
+-------------------------------------------------------------------------+
|                  1. CLOUD SERVICES / METADATA LAYER                     |
|  - Global Catalog & Schema          - Access Control (RBAC/ABAC)       |
|  - Optimizer (CBO & Rule-Based)     - Transaction Manager (ACID/MVCC)   |
|  - Micro-partition / File Metadata  - Result Cache Catalog             |
+-------------------------------------------------------------------------+
                                   ▲
                                   │ Metadata RPC / Grants
                                   ▼
+-------------------------------------------------------------------------+
|                  2. VIRTUAL COMPUTE WAREHOUSES                          |
|  [ Cluster 1: Ingestion ]  [ Cluster 2: BI / Serving ]  [ Cluster 3: ML] |
|   Node A       Node B       Node C       Node D       Node E   Node F   |
|  [RAM|NVMe]   [RAM|NVMe]   [RAM|NVMe]   [RAM|NVMe]   [RAM|NVMe][RAM|NVMe|
|   (Local SSD Ephemeral Cache - Vectorized Execution Engine / SIMD)      |
+-------------------------------------------------------------------------+
                                   ▲
                                   │ Read/Write columnar data blocks
                                   ▼
+-------------------------------------------------------------------------+
|               3. CENTRALIZED DURABLE OBJECT STORAGE                     |
|            (Amazon S3 / Google Cloud Storage / Azure Data Lake)         |
|  - Immutable Micro-Partitions / Parquet Data Blocks (50MB - 500MB)       |
|  - Encodings: RLE, Bit-Packed, Dictionary, Frame-of-Reference           |
+-------------------------------------------------------------------------+
```

#### A. Lapisan Metadata & Transaksi (Global Catalog & MVCC)
Lapisan ini mengelola status global tanpa menyimpan data aktual:
- **Snapshot Isolation & ACID (MVCC)**: Ketika data dimutasi (`INSERT`, `UPDATE`, `DELETE`), file data immutable baru ditulis ke object storage. Metadata layer mencatat set file aktif untuk setiap snapshot ID transaksi. Operasi `UPDATE` direpresentasikan sebagai penambahan file baru yang berisi record termutasi dan penandaan file lama sebagai tombstone/inaktif pada snapshot berikutnya.
- **Pruning Statistics**: Metadata menyimpan statistik statistik min/max, jumlah null, dan cardinalitas untuk setiap kolom per micro-partition.

#### B. Storage Engine Internals: Columnar Layout & Encoding
File data dipecah menjadi blok-blok berukuran terukur (misal: 50–500 MB sebelum kompresi pada Snowflake, atau split Parquet 128MB–1GB). Format penyimpanan kolumnar mengatur data secara kontinu per atribut:

```
Row-Oriented:
[Row 1: ID, Timestamp, User, Amount] [Row 2: ID, Timestamp, User, Amount]

Columnar-Oriented (Struktur Fisik Terfragmentasi):
[Col ID: 1, 2, 3...] 
[Col Timestamp: 1700000000, 1700000001, ...] (Delta-encoded)
[Col User: "alice", "bob", "alice"...]        (Dictionary-encoded -> [0, 1, 0])
[Col Amount: 10.5, 99.0, 14.2...]            (IEEE 754 Compressed)
```

Skema kompresi diterapkan adaptif berdasarkan tipe data dan entropi:
1. **Dictionary Encoding**: Mengganti string kardinalitas rendah-menengah dengan integer fixed-width bit-packed.
2. **Run-Length Encoding (RLE)**: Mengompresi sekuens data identik berulang (misal: `ID, ID, ID` $\rightarrow$ `(ID, 3)`). Efektivitas RLE meningkat dramatis saat tabel di-cluster/di-sort berdasarkan kolom tersebut.
3. **Delta Encoding / Frame of Reference**: Menyimpan selisih (*offset*) dari nilai baseline, ideal untuk tipe data `TIMESTAMP` monotonic atau sekuensial IDs.

#### C. Vectorized Compute Engines vs JIT Compilation
Pemrosesan data modern beralih dari model eksekusi *Volcano Iterator* klasik (`next()` per baris) ke pendekatan komputasi modern:
- **Vectorized Execution (misal: Databricks Photon, ClickHouse, Snowflake)**: Memproses data dalam batch array kolom (vektor) berisi ribuan nilai sekaligus. Memanfaatkan instruksi CPU SIMD (Single Instruction, Multiple Data seperti AVX-512) untuk mengevaluasi predikat secara paralel di tingkat register hardware tanpa overhead context switching.
- **Just-In-Time (JIT) Code Compilation (misal: Spark Tungsten, Hyper)**: Mengompilasi seluruh query graph menjadi native machine code saat runtime untuk meminimalkan instruksi CPU dan virtual method invocation.

#### D. The Caching Triad
Untuk mengatasi tingginya latency pada Cloud Object Storage (ratusan milidetik untuk first-byte transfer):
1. **Result Cache (In-Memory Metadata Layer)**: Menyimpan result set dari query deterministik selama 24 jam. Jika query teks sama persis dan underlying data tidak berubah, CDW langsung mengembalikan hasil tanpa menyalakan atau menggunakan cluster compute.
2. **Local NVMe SSD Cache (Virtual Warehouse Layer)**: Saat node membaca micro-partition dari object storage, file didekompresi/disimpan sebagian pada local scratch disk (NVMe). Eksekusi query selanjutnya yang memerlukan blok data yang sama akan membaca dari disk lokal dengan throughput gigabytes/sec.
3. **Remote Object Storage (Persistent Layer)**: Source of truth tunggal berbasis multi-AZ durability.

---

### 4. Why & What

| Fitur / Karakteristik | Shared-Nothing Klasik (Teradata, Netezza, Redshift DC1) | Modern Decoupled CDW (Snowflake, BigQuery, Databricks) | Dampak Rekayasa Data |
| :--- | :--- | :--- | :--- |
| **Penskalaan (Elasticity)** | Skala compute dan storage terikat (*coupled*). Resizing memerlukan redistribusi data (data rebalance/redistribution) berjam-jam. | Compute dapat ditambah, diubah ukurannya, atau dimatikan secara instan (detik/menit) tanpa migrasi data fisik. | Mampu menjalankan auto-scaling cluster untuk ELT berat dan mematikannya saat idle. |
| **Isolasi Beban Kerja** | Query analitik berat (ad-hoc) merebut CPU/RAM dari pipeline ingest real-time. Terjadi *resource contention*. | Dedicated compute warehouse terpisah dapat membaca dataset yang sama secara bersamaan tanpa lock. | Pipeline ingest ingestion data streaming SLA-kritis tidak terpengaruh oleh query BI eksekutif. |
| **Concurrency Scaling** | Queue latency melonjak saat concurrent users tinggi; *query queuing bottleneck*. | Multi-cluster auto-scaling secara otomatis memicu replica compute warehouse baru saat antrean terdeteksi. | Performa serving stabil pada jam sibuk tanpa *over-provisioning* statis 24/7. |
| **Struktur File** | Blok proprietary di local disk array. | Immutable columnar file (Parquet/ORC/Micro-partition) di S3/GCS. | Memungkinkan interoperabilitas (Zero-Copy Cloning, Time Travel, dan Data Sharing lintas akun). |

---

### 5. How (Workflow Detail)

Alur eksekusi query internal end-to-end dari representasi SQL teks hingga streaming output:

```
[SQL Client] 
     │ (1) Submit SQL Query string
     ▼
[Metadata & Cloud Services Layer]
     │ (2) Parser & Semantic Analysis: Memvalidasi AST, skema, tabel, hak akses (RBAC).
     │ (3) Cost-Based Optimizer (CBO):
     │     - Mengambil Min/Max Zone Maps dari metadata catalog.
     │     - Evaluasi Predicate: Menghapus partisi yang tidak cocok (Pruning).
     │     - Join Reordering: Memilih Hash Join vs Broadcast Join berdasarkan statistik ukuran.
     │ (4) Check Result Cache:
     │     └─► [HIT] Langsung return result -> DONE.
     │     └─► [MISS] Kirim Physical Execution Plan ke Virtual Warehouse.
     ▼
[Virtual Compute Warehouse (Nodes 1..N)]
     │ (5) Check Local NVMe SSD Cache:
     │     - Download micro-partition yang belum ada di local cache dari Object Storage.
     │ (6) Execution Phase (SIMD Vectorized):
     │     - Decompress & Evaluate Vectorized Filter pada kolom relevan (Late Materialization).
     │     - Shuffle & Exchange data antar node jika aggregate/join memerlukan redistribusi hash.
     │ (7) Check RAM Limits:
     │     - Jika memory hash-table melebihi RAM -> Spilling ke Local NVMe SSD.
     │     - Jika NVMe SSD penuh -> Spilling ke Remote Object Storage (Latency degradasi parah).
     │ (8) Agregasi Final & Serialisasi Result.
     ▼
[Client Output Delivery]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Modern vs Gudang Dokumen Kuno
Bayangkan sistem data tradisional sebagai **Gudang Arsip Manual**: Setiap meja kerja (node compute) memiliki lemari file masing-masing (disk lokal). Jika meja Anda kehabisan tempat, Anda harus memindahkan separuh lemari ke meja baru, menata ulang seluruh folder (reshuffle), dan selama penataan, tidak ada yang boleh membaca buku tersebut.

Modern Cloud Data Warehouse bekerja seperti **Perpustakaan Arsip Presidensial Terpusat**:
1. **Storage Terpusat (Object Storage)**: Semua buku disimpan di bunker bawah tanah yang tak terbatas dan tidak dapat diubah (immutable). Setiap halaman buku memiliki indeks nomor halaman, topik, dan rentang tanggal di katalog utama.
2. **Katalog Metadata (Cloud Services)**: Peneliti mengecek indeks. Petugas katalog berkata: *"Anda hanya butuh data tahun 2023? Jangan ambil jilid 1 sampai 50, ambil jilid 51 saja."* (Metadata Pruning).
3. **Meja Peneliti Independen (Virtual Warehouses)**: Meja Tim Finansial dan Meja Tim Data Science terpisah. Keduanya membaca salinan fotokopi dari buku yang sama dari bunker. Tim Data Science yang membaca jutaan halaman tidak akan menggoyang meja Tim Finansial.
4. **Meja Baca Lokal (Local NVMe SSD Cache)**: Peneliti meletakkan buku yang sering dibaca langsung di atas mejanya agar tidak perlu bolak-balik ke bunker.

#### Diagram: Partition Pruning & Late Materialization

```
QUERY: SELECT Customer_ID, Amount FROM Transactions WHERE Date = '2023-10-15' AND Region = 'APAC';

Object Storage: 10,000 Micro-Partitions
─────────────────────────────────────────────────────────────────────────────
[Metadata Check via Zone Maps (Min/Max)]
Partisi #001: Date [2023-01-01 s/d 2023-03-31] -> SKIP (Pruned)
Partisi #042: Date [2023-10-01 s/d 2023-10-31], Region ['APAC', 'EMEA'] -> BACA
Partisi #099: Date [2023-10-01 s/d 2023-10-31], Region ['US']           -> SKIP (Pruned)
─────────────────────────────────────────────────────────────────────────────
Hasil Pruning: Hanya membaca 1 dari 10,000 Partisi!

Di Dalam Partisi #042 (Columnar Late Materialization):
  Step 1: Pindai hanya kolom 'Date' (Array terkompresi)
          -> Filter bitmask: [0, 0, 1, 0, 1]
  Step 2: Terapkan bitmask ke kolom 'Region'
          -> Filter bitmask: [0, 0, 1, 0, 0] (Hanya indeks ke-2 valid)
  Step 3: Baca HANYA baris ke-2 dari kolom 'Customer_ID' dan 'Amount'
  (I/O bandwidth dihemat hingga 99.8% karena kolom lain sama sekali tidak di-load dari disk)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Demonstrasi Pruning Degradation vs Optimized Clustering (Snowflake SQL Engine)

Skenario: Membandingkan dampak clustering key terhadap micro-partition pruning pada tabel log transaksi bervolume tinggi.

```sql
-- 1. Setup Tabel Tanpa Clustering Key (Natural Insertion Order - Acak)
CREATE OR REPLACE TABLE raw_web_events (
    event_id STRING,
    event_timestamp TIMESTAMP_NTZ,
    tenant_id STRING,
    payload VARIANT
);

-- Simulasi ingest 10.000.000 baris data acak
INSERT INTO raw_web_events
SELECT 
    UUID_STRING(),
    DATEADD(second, UNIFORM(1, 2592000, RANDOM(1)), '2023-01-01'::TIMESTAMP_NTZ),
    'TENANT_' || LPAD(UNIFORM(1, 1000, RANDOM(2))::STRING, 4, '0'),
    PARSE_JSON('{"browser":"Chrome","ip":"192.168.1.1"}')
FROM TABLE(GENERATOR(ROWCOUNT => 10000000));

-- Cek metadata partisi default
SELECT SYSTEM$CLUSTERING_INFORMATION('raw_web_events');

-- 2. Query Predikat Spesifik (Cold Run: Cache Dimatikan)
ALTER SESSION SET USE_CACHED_RESULT = FALSE;

SELECT COUNT(*), AVG(LENGTH(payload:browser::STRING))
FROM raw_web_events
WHERE tenant_id = 'TENANT_0420'
  AND event_timestamp BETWEEN '2023-01-10 00:00:00' AND '2023-01-12 23:59:59';
-- Amati Query Profile: Partitions Total vs Partitions Scanned (Hampir scan 100% data)

-- 3. Optimalisasi: Buat Clustering Key Berdasarkan Pola Akses Terbanyak
ALTER TABLE raw_web_events CLUSTER BY (tenant_id, to_date(event_timestamp));

-- Paksa re-clustering sinkron (Production: biarkan Automatic Clustering Service)
ALTER TABLE raw_web_events RECLUSTER;

-- Jalankan ulang query yang sama
SELECT COUNT(*), AVG(LENGTH(payload:browser::STRING))
FROM raw_web_events
WHERE tenant_id = 'TENANT_0420'
  AND event_timestamp BETWEEN '2023-01-10 00:00:00' AND '2023-01-12 23:59:59';
-- Query Profile Pasca-Clustering: Menunjukkan efisiensi pruning ekstrem (misal scan < 1% partisi)
```

#### B. Practical Enterprise Example: Monitoring & Mitigasi Disk Spilling Secara Otomatis via DDL & Warehouse Sizing Engine

Berikut adalah Python Utility untuk Data Platform Engine yang memonitor query historis pada Snowflake via `ACCOUNT_USAGE` untuk mendeteksi *Disk Spilling to Remote Storage* (penyebab utama query lambat dan pembengkakan biaya compute), serta menyarankan penyesuaian warehouse size:

```python
"""
Warehouse Sizing & Spilling Diagnostics Engine
Path: platform_tools/spill_analyzer.py
"""

from typing import List, Dict, Any
import snowflake.connector
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class WarehouseSpillAnalyzer:
    def __init__(self, connection_params: Dict[str, Any]):
        self.conn = snowflake.connector.connect(**connection_params)

    def analyze_warehouse_spillage(self, lookback_days: int = 7) -> pd.DataFrame:
        """
        Menganalisis query yang mengalami memory starvation dan terpaksa
        melakukan spilling data ke Local Storage (NVMe) dan Remote Storage (S3/GCS).
        """
        query = f"""
        SELECT 
            query_id,
            warehouse_name,
            warehouse_size,
            user_name,
            execution_status,
            total_elapsed_time / 1000 AS execution_time_seconds,
            bytes_scanned / POWER(1024, 3) AS gb_scanned,
            bytes_spilled_to_local_storage / POWER(1024, 3) AS gb_spilled_local,
            bytes_spilled_to_remote_storage / POWER(1024, 3) AS gb_spilled_remote,
            ROUND((bytes_spilled_to_remote_storage / NULLIF(bytes_scanned, 0)) * 100, 2) AS remote_spill_ratio
        FROM snowflake.account_usage.query_history
        WHERE start_time >= DATEADD(day, -{lookback_days}, CURRENT_TIMESTAMP())
          AND (bytes_spilled_to_local_storage > 0 OR bytes_spilled_to_remote_storage > 0)
          AND query_type IN ('SELECT', 'INSERT', 'MERGE', 'CREATE_TABLE_AS_SELECT')
        ORDER BY bytes_spilled_to_remote_storage DESC
        LIMIT 50;
        """
        logging.info("Mengeksekusi analisis spillage query...")
        with self.conn.cursor() as cur:
            cur.execute(query)
            df = cur.fetch_pandas_all()
        return df

    def generate_remediation_strategy(self, row: pd.Series) -> str:
        """
        Menghasilkan rekomendasi teknis berbasis metrik spill.
        """
        local_spill = row['GB_SPILLED_LOCAL']
        remote_spill = row['GB_SPILLED_REMOTE']

        if remote_spill > 50.0:
            return (
                f"CRITICAL: Warehouse '{row['WAREHOUSE_NAME']}' (Size: {row['WAREHOUSE_SIZE']}) "
                f"mengalami Remote Spilling parah ({remote_spill:.2f} GB). "
                f"Rekomendasi: Upgrade warehouse minimal 2 level lebih tinggi (misal M -> XL) "
                f"atau perbaiki cartesian/skewed join pada Query ID {row['QUERY_ID']}."
            )
        elif local_spill > 20.0 and remote_spill == 0:
            return (
                f"WARNING: Warehouse '{row['WAREHOUSE_NAME']}' mengalami Local Spilling ({local_spill:.2f} GB). "
                f"Memory node jenuh tetapi belum menyentuh remote storage. "
                f"Rekomendasi: Tingkatkan warehouse 1 level atau optimasi memory footprint (hindari DISTINCT/GROUP BY pada kolom berdensitas tinggi)."
            )
        return "STABLE: Spilling dalam batas toleransi wajar."

    def execute_diagnostic_run(self):
        df_spills = self.analyze_warehouse_spillage(lookback_days=3)
        if df_spills.empty:
            logging.info("Tidak ditemukan query dengan memory spillage signifikan.")
            return

        logging.warning(f"Terdeteksi {len(df_spills)} query bermasalah dengan memory spillage.")
        for idx, row in df_spills.head(10).iterrows():
            recommendation = self.generate_remediation_strategy(row)
            print(f"\n[QUERY: {row['QUERY_ID']}] - User: {row['USER_NAME']}")
            print(f"Exec Time: {row['EXECUTION_TIME_SECONDS']}s | Local Spill: {row['GB_SPILLED_LOCAL']:.2f} GB | Remote Spill: {row['GB_SPILLED_REMOTE']:.2f} GB")
            print(f"Action: {recommendation}")

if __name__ == "__main__":
    # Konfigurasi koneksi menggunakan Environment Credentials
    connection_params = {
        "user": "DATA_ARCHITECT_USER",
        "password": "ProductionSuperSecurePassword123!",
        "account": "xy12345.ap-southeast-1",
        "role": "ACCOUNTADMIN",
        "warehouse": "OPS_ADMIN_WH"
    }
    # Jalankan analyzer
    # analyzer = WarehouseSpillAnalyzer(connection_params)
    # analyzer.execute_diagnostic_run()
    print("Modul Analyzer siap diintegrasikan ke monitoring pipeline orchestration.")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Logistik Global Multi-Nasional (Fintech & Supply Chain)
- **Kondisi Awal**: 
  - Volume data: 4.8 Petabyte tabel transaksi armada logistik global.
  - Arsitektur: Snowflake Single Monolithic Warehouse Size 4X-Large (128 node compute, 128 credits/jam).
  - Masalah Utama:
    1. Pipeline micro-batch ingest (tiap 1 menit) sering timeout karena antrean lock transaksi.
    2. Query dashboard analitik eksekutif melambat dari 5 detik menjadi 40 menit saat batch sinkronisasi armada masuk.
    3. Biaya bulanan membengkak hingga $180,000 USD/bulan akibat warehouse 4X-Large beroperasi 24/7 tanpa auto-suspend yang memadai.
    4. Sering terjadi remote disk spilling pada query rekonsiliasi akhir bulan (skala TB).

#### Root Cause Analysis (RCA) via Query Profile Internals:
1. **Resource Contention**: Monolithic warehouse membagi resource yang sama antara read-heavy BI, ETL transformations, dan streaming micro-batches.
2. **Metadata Pruning Ineffective**: Tabel transaksi di-cluster berdasarkan kolom `TRANSACTION_ID` (kardinalitas tinggi, UUID), menyebabkan min/max zone map tidak berguna untuk predikat query analitik yang memfilter berdasarkan `CREATED_DATE` dan `COUNTRY_CODE`.
3. **Explosive Shuffle Skew**: Pada saat rekonsiliasi join antara tabel transaksi dan master merchant, 40% record tertumpuk pada satu ID merchant global default (`NULL` atau dummy merchant ID `'0000'`), menyebabkan satu node compute kehabisan memori dan spilling 1.2 TB ke object storage.

#### Solusi Arsitektural (Implementasi Produksi):
1. **Workload Decoupling (Domain-Driven Warehouses)**:
   - `INGEST_WH`: Size Medium (Multi-cluster auto-scaling 1-3 cluster) khusus snowpipe streaming & batch ingestion.
   - `TRANSFORM_WH`: Size X-Large (Tersedia terjadwal jam 01:00 - 05:00 UTC) untuk dbt heavy transformations.
   - `BI_REPORTING_WH`: Size Large (Multi-cluster auto-scaling 1-5 cluster) khusus query PowerBI/Tableau dengan auto-suspend 60 detik.
2. **Re-clustering Strategy**:
   - Menghapus clustering `TRANSACTION_ID`.
   - Mengubah cluster key menjadi: `CLUSTER BY (to_date(CREATED_DATE), COUNTRY_CODE)`.
3. **Data Skew Join Optimization**:
   - Menerapkan teknik *Null-Salting* pada join query untuk mendistribusikan dummy ID transaksi secara merata ke seluruh worker node:
   ```sql
   SELECT a.*, b.*
   FROM transactions a
   LEFT JOIN merchants b
     ON CASE WHEN a.merchant_id IS NULL OR a.merchant_id = '0000'
             THEN CONCAT('DUMMY_', UNIFORM(1, 10, RANDOM())) 
             ELSE a.merchant_id END = b.merchant_id;
   ```

#### Hasil Kuantitatif (Post-Implementation Metrics):
- Biaya operasional warehouse turun 58% (dari $180,000/bulan menjadi $75,600/bulan).
- Rata-rata latency query BI turun dari 40 menit menjadi 3.2 detik (99.8% peningkatan kecepatan).
- Remote disk spilling turun hingga 0 GB (eliminasi total).
- SLA Ingestion logistik tercapai 99.99% tanpa kegagalan lock timeout.

---

### 9. Trade-offs

| Parameter | High Clustering / Fine Partitioning | Low / Zero Clustering (Natural Order) | Analisis Trade-off Arsitektural |
| :--- | :--- | :--- | :--- |
| **Query Performance (Latency)** | **Sangat Cepat**: Metadata pruning bekerja optimal, data scan tereduksi hingga 99%. | **Lambat**: Sering terjadi full table scan pada dataset multi-terabyte. | Jika query SLA membutuhkan sub-second, re-clustering adalah keharusan. |
| **Write / Ingestion Throughput** | **Terganggu**: Biaya pemeliharaan (*sorting/re-clustering*) konstan pasca-insert baru. | **Maksimal**: Data langsung di-*dump* ke micro-partition baru tanpa overhead sorting. | Streaming ingestion kecepatan tinggi rentan terhadap biaya maintenance clustering yang mahal. |
| **Total Cost of Ownership (FinOps)** | **Tinggi Compute Metadata**: Background auto-clustering service mengonsumsi credits secara kontinyu. | **Tinggi Query Cost**: Tiap query ad-hoc membakar compute credits lebih banyak karena scan byte besar. | Titik impas (*break-even point*): Re-clustering hanya ekonomis jika tabel dibaca berulang kali (> puluhan kali) per siklus ingest. |

| Parameter | Upsizing Warehouse (Scale-Up: M -> 2XL) | Multi-Cluster Out (Scale-Out: Min 1 -> Max 5) | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- |
| **Fokus Solusi** | Menyelesaikan **Query Complexity** (Spilling, Large Joins, Aggregation). | Menyelesaikan **Query Concurrency** (Banyak user membuka dashboard serentak). | Jangan scale-up jika antrean query disebabkan oleh ratusan concurrent users; gunakan scale-out. |
| **Dampak Finansial** | Biaya per unit waktu naik eksponensial ($2^N$ credit multiplier). | Biaya hanya naik linier saat concurrency meledak, kembali ke min-cluster saat idle. | Terapkan auto-suspend ketat (60s) untuk Scale-Up, dan auto-scaling policy *Standard* untuk Scale-Out. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns)
1. **Over-Clustering Antipattern**: Mengatur lebih dari 4 kolom pada clustering key (misal: `CLUSTER BY (colA, colB, colC, colD, colE)`). 
   - *Dampak*: Metadata explosion. Kardinalitas gabungan terlalu tinggi sehingga setiap micro-partition hanya berisi sedikit irisan data, mematikan efisiensi RLE/kompresi dan meningkatkan komputasi clustering background secara masif.
2. **Result Cache Invalidation Failure**: Memasukkan fungsi non-deterministik ke dalam query analytics (misal: `WHERE event_time < CURRENT_TIMESTAMP()` atau `WHERE random_flag = RANDOM()`).
   - *Dampak*: Menghancurkan kapabilitas query result cache. Query identik terpaksa selalu menyalakan compute warehouse.
3. **Data Type Mismatch Implicit Casting**: Melakukan join antara string dan numeric yang memicu cast implisit: `ON table_a.string_id = table_b.numeric_id`.
   - *Dampak*: Optimizer tidak dapat menggunakan zone map min/max; vector engine harus mengeksekusi konversi tipe per baris secara iterative, mematikan pruning.

#### Panduan Troubleshooting Langkah demi Langkah: Query Spilling & Memory Starvation

```
            [ Deteksi Masalah: Query Berjalan Lambat / Timeout ]
                                     │
                                     ▼
                [ Buka Query Profile / Execution Graph ]
                                     │
           Apakah terdapat metrik 'Bytes Spilled to Storage'?
                                     │
                   ┌─────────────────┴─────────────────┐
                  YA                                  TIDAK
                   │                                   │
      Spilled to Remote Storage?            Periksa Partitions Scanned
         ┌─────────┴─────────┐                         │
        YA                  TIDAK         Partitions Scanned == Total Partitions?
         │                   │                         │
[CRITICAL ALERT]      [WARNING ALERT]         ┌────────┴────────┐
Memory jenuh total.   Memory jenuh di RAM,    YA                TIDAK
Data tumpah ke S3/GCS. tumpah ke NVMe SSD.     │                 │
Solusi:               Solusi:             [Pruning Rusak]   [Skew / CPU Bottleneck]
1. Upsize Warehouse   1. Naikkan size 1x  Periksa Predikat   Periksa eksekusi Join.
   minimal 1-2 tier.     (misal S -> M).  WHERE. Gunakan     Identifikasi apakah 1
2. Cek Join Cardinality 2. Kurangi memory  Clustering key     node memproses 90%
   apakah terjadi        footprint window yang sesuai tipe   data (Gunakan salting
   Cartesian Product     functions.       kueri.             atau filter skew keys).
   (M x N rows).
```

---

### 11. Best Practices (Production Checklist)

#### Pre-Production & DDL Design Checklist
- [ ] **Data Types**: Gunakan tipe data paling spesifik (jangan gunakan `VARCHAR(16777216)` atau `STRING` untuk seluruh data jika panjang string dapat diestimasi; jangan gunakan `VARIANT`/`JSON` untuk kolom yang sering dijadikan filter predikat).
- [ ] **Clustering Strategy**: Pilih 1-3 kolom dengan kardinalitas yang meningkat secara bertahap (misal: `Date` kemudian `CountryCode`). Pastikan volume tabel > 100 GB sebelum menerapkan explicit clustering.
- [ ] **Temporal Partitioning**: Format timestamp harus konsisten dalam bentuk timezone-agnostic UTC (`TIMESTAMP_NTZ`).

#### Infrastructure & Compute Configuration Checklist
- [ ] **Decoupled Architecture**: Pisahkan warehouse berdasarkan fungsi: Ingestion, Transformation (dbt/Airflow), Ad-hoc Analytics, dan Reporting (BI).
- [ ] **Auto-Suspend Rules**: Set auto-suspend compute warehouse:
  - Ad-hoc / Analytics: 300 detik (5 menit).
  - Production Batch / ETL: 60 detik.
  - BI Dashboard Server: 120 detik.
- [ ] **Concurrency Scaling**: Aktifkan Multi-Cluster Warehouse (Scale-Out) dengan mode auto-scaling *Standard* untuk BI tools dengan concurrency fluktuatif.
- [ ] **Statement Timeout**: Set parameter `STATEMENT_TIMEOUT_IN_SECONDS` (misal 3600 detik) untuk mencegah orphaned query berjalan tanpa batas akibat error pada script aplikasi.

#### Query Writing Best Practices
- [ ] **Deterministic Filters**: Gunakan ekspresi konstan dalam filter untuk memanfaatkan query result cache (hindari `CURRENT_TIMESTAMP()`, ganti dengan snapshot parameter yang disuntikkan oleh orchestrator: `'2023-10-25 00:00:00'`).
- [ ] **Projection Pruning**: Jangan pernah menggunakan `SELECT *` pada lingkungan produksi berbasis columnar warehouse; tentukan secara eksplisit kolom yang dibutuhkan.
- [ ] **Safe Joins**: Hindari join dengan ekspresi predikat kompleks (misal menggunakan regex atau concatenation dalam clause `ON`).

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori repositori: `hands-on/m02/`.

#### Langkah 1: Struktur Proyek
Buat struktur direktori lokal:
```bash
mkdir -p hands-on/m02/scripts
mkdir -p hands-on/m02/sql
cd hands-on/m02
```

#### Langkah 2: Setup Terraform / DDL Environment (`sql/01_init_warehouse_and_tables.sql`)
Simpan skrip SQL berikut untuk menyiapkan multi-tier environment:

```sql
-- hands-on/m02/sql/01_init_warehouse_and_tables.sql
-- Inisialisasi Warehouses Terpisah (Isolasi Beban Kerja)

CREATE OR REPLACE WAREHOUSE ETL_WH 
WITH 
    WAREHOUSE_SIZE = 'SMALL' 
    AUTO_SUSPEND = 60 
    AUTO_RESUME = TRUE 
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Dedicated compute warehouse for data ingestion and ETL';

CREATE OR REPLACE WAREHOUSE ANALYTICS_WH 
WITH 
    WAREHOUSE_SIZE = 'MEDIUM' 
    MIN_CLUSTER_COUNT = 1 
    MAX_CLUSTER_COUNT = 3 
    SCALING_POLICY = 'STANDARD'
    AUTO_SUSPEND = 120 
    AUTO_RESUME = TRUE 
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Dedicated auto-scaling warehouse for BI and Ad-hoc queries';

-- Database dan Schema
CREATE OR REPLACE DATABASE ENTERPRISE_DW;
CREATE OR REPLACE SCHEMA ENTERPRISE_DW.CORE;

USE SCHEMA ENTERPRISE_DW.CORE;

-- Tabel Transaksi Skala Besar Tanpa Optimasi Awal
CREATE OR REPLACE TABLE telemetry_events (
    device_id VARCHAR(64),
    event_time TIMESTAMP_NTZ,
    firmware_version VARCHAR(16),
    location_iso VARCHAR(8),
    cpu_utilization FLOAT,
    memory_spill_kb NUMBER,
    payload VARIANT
);
```

#### Langkah 3: Data Generator Sintetis Skala Menengah (`scripts/datagen.py`)
Skrip Python ini menghasilkan 5.000.000 data telemetri JSON langsung di-*stream* atau ditulis ke staging Parquet lokal:

```python
# hands-on/m02/scripts/datagen.py
import datetime
import random
import uuid
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

def generate_telemetry_batch(num_records: int, file_path: str):
    print(f"Menghasilkan {num_records} rekaman telemetri...")
    devices = [f"DEV-{i:06d}" for i in range(1000)]
    locations = ['US', 'ID', 'SG', 'JP', 'DE', 'GB', 'BR', 'AU']
    firmwares = ['v1.0.0', 'v1.1.2', 'v2.0.0-rc1', 'v2.1.0']

    base_time = datetime.datetime(2023, 1, 1, 0, 0, 0)

    data = {
        "device_id": [random.choice(devices) for _ in range(num_records)],
        "event_time": [base_time + datetime.timedelta(seconds=random.randint(0, 31536000)) for _ in range(num_records)],
        "firmware_version": [random.choice(firmwares) for _ in range(num_records)],
        "location_iso": [random.choice(locations) for _ in range(num_records)],
        "cpu_utilization": [round(random.uniform(5.0, 99.9), 2) for _ in range(num_records)],
        "memory_spill_kb": [random.randint(0, 1048576) for _ in range(num_records)],
        "payload": ['{"status": "ONLINE", "sensor_mode": "ACTIVE"}' for _ in range(num_records)]
    }

    df = pd.DataFrame(data)
    table = pa.Table.from_pandas(df)
    pq.write_table(table, file_path, compression='snappy')
    print(f"File Parquet berhasil ditulis ke: {file_path}")

if __name__ == "__main__":
    generate_telemetry_batch(1000000, "telemetry_data_sample.parquet")
```

#### Langkah 4: Skrip Eksekusi Diagnosis & Optimasi (`sql/02_benchmark_and_tuning.sql`)

```sql
-- hands-on/m02/sql/02_benchmark_and_tuning.sql
USE DATABASE ENTERPRISE_DW;
USE SCHEMA ENTERPRISE_DW.CORE;
USE WAREHOUSE ANALYTICS_WH;

-- Nonaktifkan Result Cache untuk memastikan testing membaca disk/SSD
ALTER SESSION SET USE_CACHED_RESULT = FALSE;

-- Query 1: Filter dengan predikat majemuk pada tabel unclustered
SELECT 
    location_iso,
    firmware_version,
    AVG(cpu_utilization) AS avg_cpu,
    MAX(memory_spill_kb) AS max_spill
FROM telemetry_events
WHERE event_time BETWEEN '2023-06-01' AND '2023-06-30'
  AND location_iso IN ('ID', 'SG')
GROUP BY 1, 2;

-- CATAT HASIL QUERY PROFILE:
-- 1. Berapa Partitions Scanned vs Total Partitions?
-- 2. Berapa volume Local SSD Cache Read vs Remote Read?

-- Terapkan Optimalisasi: Terapkan Multi-Column Clustering Key
ALTER TABLE telemetry_events CLUSTER BY (location_iso, to_date(event_time));

-- Tunggu background re-clustering atau trigger manual
ALTER TABLE telemetry_events RECLUSTER;

-- Jalankan ulang Query 1 yang sama persis
SELECT 
    location_iso,
    firmware_version,
    AVG(cpu_utilization) AS avg_cpu,
    MAX(memory_spill_kb) AS max_spill
FROM telemetry_events
WHERE event_time BETWEEN '2023-06-01' AND '2023-06-30'
  AND location_iso IN ('ID', 'SG')
GROUP BY 1, 2;

-- EVALUASI: Bandingkan Partitions Scanned. Reduksi scan partisi harus mencapai > 80%.
```

---

### 13. Exercise

#### Level: Easy
1. Ubah konfigurasi auto-suspend warehouse `ETL_WH` menjadi 180 detik, dan atur `STATEMENT_QUEUED_TIMEOUT_IN_SECONDS` menjadi 60 detik melalui perintah DDL SQL.
2. Tuliskan kueri eksplorasi metadata menggunakan `SYSTEM$CLUSTERING_DEPTH` untuk mengevaluasi kualitas pengelompokan (*clustering quality*) pada tabel `telemetry_events`.

#### Level: Medium
1. Terdapat query join berikut yang sering mengalami kegagalan performa:
   ```sql
   SELECT a.device_id, b.firmware_branch
   FROM telemetry_events a
   JOIN firmware_metadata b 
     ON a.firmware_version = b.version_code
   WHERE a.cpu_utilization > 90.0;
   ```
   Jika tabel `firmware_metadata` hanya berisi 50 baris dan `telemetry_events` berisi 2 miliar baris, analisislah jenis Join Operator apa yang seharusnya dipilih oleh Cost-Based Optimizer (*Broadcast Hash Join* atau *Shuffle Hash Join*). Tuliskan instruksi SQL/Hint untuk memverifikasi apakah optimizer tidak melakukan broad-scale network shuffle yang tidak perlu.

#### Level: Hard
1. Buat skrip automasi alerting SQL (menggunakan Snowflake Tasks dan Stored Procedure) yang berjalan setiap 30 menit. Alerting ini harus mendeteksi jika ada query di warehouse `ANALYTICS_WH` yang menghasilkan `BYTES_SPILLED_TO_REMOTE_STORAGE > 10GB` dalam 30 menit terakhir, lalu otomatis menuliskan query ID, user, dan bytes spilled tersebut ke dalam audit table `ENTERPRISE_DW.MONITORING.SPILL_INCIDENTS`.

---

### 14. Challenge (Kompleks Enterprise Scenario)

#### Deskripsi Tantangan
Anda diangkat sebagai Principal Data Platform Architect di sebuah bank digital unicorn dengan throughput transaksi 50.000 write ops/detik. 

#### Masalah Sistem:
1. **The Midnight Degradation**: Setiap pukul 00:01 UTC, proses rekonsiliasi end-of-day (EoD) berjalan menggunakan dbt. Pada saat yang sama, tim Customer Service sedang melayani ribuan nasabah dengan dashboard live support.
2. Saat proses EoD berjalan, dashboard Customer Service mengalami lonjakan respon dari 200 milidetik menjadi 120 detik, menghasilkan status HTTP 504 Gateway Timeout pada API Core Banking.
3. Tabel `LEDGER_ENTRIES` berukuran 12 Petabyte. Tim engineering sebelumnya membuat clustering key: `CLUSTER BY (ENTRY_ID, ACCOUNT_ID, EVENT_TIMESTAMP)`. Akibatnya, biaya Auto-Clustering background service mencapai $45,000 USD per bulan hanya untuk tabel ini.
4. Muncul transaksi skew parah: Akun penampung internal sistem (`ACCOUNT_ID = 'INTERNAL_SETTLEMENT'`) menampung 35% dari seluruh total baris ledger di seluruh database. Join apa pun pada akun ini menyebabkan crash pada worker compute nodes karena kehabisan alokasi scratch memory.

#### Tugas Rekayasa Anda:
1. Rancang arsitektur isolasi warehouse produksi lengkap (termasuk sizing, auto-scaling policy, concurrency scaling, dan resource monitors) untuk menjamin beban kerja EoD batch terisolasi 100% dari Customer Service dashboard API tanpa over-provisioning resource di luar jam sibuk.
2. Redesain strategi clustering dan partitioning tabel `LEDGER_ENTRIES`. Hapus anti-pattern yang ada, susun formulasi cluster key baru yang hemat biaya, dan justifikasi dampaknya terhadap metadata micro-partition pruning.
3. Rancang strategi mitigasi untuk menangani *hotspot data skew* pada join akun internal `INTERNAL_SETTLEMENT` tanpa mengubah source logic bisnis aplikasi transaksi core.
4. Sajikan solusi Anda dalam bentuk Technical Design Document (TDD) arsitektur tingkat enterprise disertai diagram komponen ASCII, rancangan DDL, dan skema tata kelola biaya (FinOps quota attribution).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa keunggulan fundamental arsitektur *Decoupled Storage-Compute* dibanding *Shared-Nothing* klasik?
   - A. Storage terhubung langsung ke motherboard compute via PCIe.
   - B. Compute nodes dapat diskalakan atau dimatikan secara instan tanpa perlu mendistribusikan ulang (rebalancing) data fisik pada persistent storage.
   - C. Menghilangkan kebutuhan akan caching data pada local node.
   - D. Membatasi ukuran kueri hanya pada satu node master.

2. Di lapisan manakah *Result Cache* pada arsitektur Snowflake beroperasi?
   - A. Persistent Remote Cloud Object Storage (S3/GCS).
   - B. Worker Node Local Scratch NVMe SSD.
   - C. Cloud Services Layer / Metadata Layer.
   - D. Client Browser Memory.

3. Apa fungsi utama dari statistik *Zone Maps* (Min/Max Metadata) pada Modern Cloud Data Warehouse?
   - A. Mengenkripsi kolom sensitif menggunakan AES-256.
   - B. Memungkinkan query engine melewati (pruning) file/blok data yang tidak memenuhi predikat filter WHERE tanpa membacanya dari disk.
   - C. Menyusun data secara otomatis dalam bentuk urutan B-Tree.
   - D. Menghubungkan primary key dan foreign key secara paksa.

4. Format penyimpanan data kolumnar sangat efisien untuk kueri analitik (OLAP) terutama karena:
   - A. Membaca seluruh atribut baris data dalam satu continuous memory block.
   - B. Mengeliminasi I/O disk untuk kolom-kolom yang tidak diperlukan dalam klausa `SELECT` (Projection Pruning).
   - C. Menjamin operasi `INSERT` satu baris (single-row transactional) lebih cepat dari row-store.
   - D. Tidak membutuhkan kompresi file.

5. Apa arti metrik *Bytes Spilled to Remote Storage* pada eksekusi query profile?
   - A. Data berhasil ditransfer ke client storage tanpa error.
   - B. RAM node compute habis, kemudian local NVMe scratch disk juga habis, memaksa engine menulis intermediate state kueri ke cloud object storage lambat.
   - C. Terjadi replikasi data multi-region secara sukses.
   - D. Data diekspor secara manual ke format CSV.

#### Bagian 2: Intermediate (Analisis Singkat)
1. Mengapa menyertakan predikat `WHERE transaction_date >= CURRENT_DATE()` menggagalkan pemanfaatan *Result Cache*?
2. Jelaskan bagaimana algoritma kompresi *Run-Length Encoding (RLE)* bekerja pada penyimpanan data kolumnar dan mengapa performanya meningkat drastis setelah tabel di-cluster dengan baik!
3. Apa perbedaan fundamental antara *Vectorized Execution* (seperti Databricks Photon) dengan metode evaluasi *Volcano Iterator Model* klasik?
4. Dalam kondisi apa teknik *Broadcast Hash Join* jauh lebih unggul dibandingkan *Shuffle Hash Join*? Jelaskan dampaknya terhadap jaringan antar-node!
5. Sebutkan trade-off arsitektural penggunaan fitur *Zero-Copy Cloning* terhadap retensi *Time Travel* dan biaya penyimpanan (storage cost)!

#### Bagian 3: Skenario Kasus Produksi
1. **Skenario A**: Tim BI mengeluhkan query dashboard mendadak membutuhkan waktu 25 menit (biasanya 5 detik). Saat memeriksa Query Profile, Anda melihat `Partitions Scanned: 45,000` dari `Total Partitions: 45,000`, padahal query menyertakan filter `WHERE order_date = '2023-11-01'`. Setelah diteliti, klausa predikat ditulis sebagai: `WHERE TO_CHAR(order_date, 'YYYY-MM-DD') = '2023-11-01'`. Analisis akar masalah internal engine dan jelaskan cara memperbaikinya!
2. **Skenario B**: Pipeline ingestion micro-batch yang berjalan tiap 2 menit mulai sering mengalami insiden `Resource limit exceeded / Transaction lock timeout`. Pipeline dijalankan pada warehouse yang sama dengan warehouse analitik ad-hoc data scientist. Bagaimana Anda menyelesaikan masalah contention ini tanpa menambah biaya cloud secara eksponensial?
3. **Skenario C**: Sebuah query analitik join yang memproses 500 GB data mengalami degradasi ekstrem akibat *Data Skew*. Query profile menunjukkan 1 dari 16 node compute memiliki waktu eksekusi 20x lebih lama dibanding node lainnya dan mencatatkan puluhan gigabyte *Remote Disk Spill*. Identifikasi penyebab teknis di tingkat network shuffle dan berikan dua alternatif pendekatan teknis untuk mengatasinya!

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B**: Penskalaan independen tanpa beban redistribusi/rebalancing blok disk fisik antar node.
2. **C**: Result cache tersimpan di Cloud Services/Metadata Layer, sehingga dapat diakses bahkan ketika seluruh compute warehouse dalam kondisi suspend (0 credit cost).
3. **B**: Zone Maps menyimpan statistik min/max tiap blok/partisi untuk melakukan eliminasi partisi (*pruning*) seawal mungkin sebelum pembacaan I/O dilakukan.
4. **B**: Columnar storage hanya memuat array kolom yang diminta oleh query ke memori/CPU (*late materialization* & *projection pruning*).
5. **B**: Remote spilling menandakan kapasitas memori kerja RAM maupun local SSD cache pada worker cluster telah terlampaui seluruhnya, menyebabkan data intermediet harus dibuang ke storage berlatensi tinggi (S3/GCS).

#### Bagian 2: Intermediate
1. **Evaluasi Fungsi Non-Deterministik**: `CURRENT_DATE()` dievaluasi ulang saat runtime query diterima. Karena ekspresi dinilai berpotensi menghasilkan status berbeda secara dinamis, Cloud Services Metadata Layer menandai query sebagai non-deterministik dan mewajibkan eksekusi ulang pada engine compute tanpa mengambil hasil statis Result Cache.
2. **RLE & Clustering**: RLE merepresentasikan rangkaian data identik berurutan sebagai pasangan `(nilai, panjang_kemunculan)`. Jika tabel tidak di-sort, data tersebar acak (misal: `ID, US, ID, JP`), sehingga RLE tidak efisien. Setelah tabel di-cluster berdasarkan negara, urutannya menjadi kontinu (`ID, ID, ID, ...`), memungkinkan jutaan baris dikompresi menjadi satu entri ringkas: `('ID', 1000000)`, mereduksi I/O disk dan konsumsi RAM secara masif.
3. **Vectorized vs Volcano Iterator**: Model Volcano klasik memanggil method `next()` virtual secara rekursif per satu baris record data (overhead instruksi CPU tinggi). Vectorized Execution memproses blok data kolom (misal: 1024 elemen) dalam register CPU secara bersamaan menggunakan set instruksi SIMD, meminimalkan branching, meningkatkan L1/L2 cache locality, dan melipatgandakan throughput pemrosesan.
4. **Broadcast vs Shuffle Join**: Broadcast join menyalin (broadcast) tabel kecil secara utuh ke seluruh node worker compute, menghilangkan kebutuhan untuk melakukan hash redistribusi network shuffle pada tabel besar. Jaringan terhindar dari saturasi data exchange antar node (*all-to-all communication* tereliminasi), sangat ideal jika salah satu tabel berukuran kecil (< puluhan MB).
5. **Trade-offs Zero-Copy Cloning**: Cloning tidak menggandakan data fisik saat pertama kali dibuat (hanya menduplikasi pointer metadata partisi, instan dan gratis). Namun, begitu tabel clone atau tabel asal mengalami mutasi (`UPDATE`/`DELETE`), blok-blok partisi lama tidak dapat dilepas oleh garbage collector/purging engine karena masih direferensikan oleh snapshot clone. Akibatnya, biaya persistent storage melonjak seiring bertambahnya lifecycle Time Travel dan Fail-safe.

#### Bagian 3: Skenario Kasus Produksi
1. **Akar Masalah Skenario A**: Membungkus kolom partisi `order_date` di dalam ekspresi fungsi skalar `TO_CHAR(...)` menghasilkan kondisi *Non-Sargable Predicate*. Metadata Optimizer tidak dapat memetakan hasil transformasi fungsi runtime tersebut terhadap Min/Max Zone Maps kolom asli, mematikan fungsi pruning dan memaksa terjadinya Full Table Scan (45.000 partisi).
   - **Perbaikan**: Ubah filter menjadi format sargable tanpa memodifikasi kolom target: `WHERE order_date = '2023-11-01'::DATE` atau gunakan interval bounded: `WHERE order_date >= '2023-11-01' AND order_date < '2023-11-02'`.
2. **Solusi Skenario B**: Terapkan isolasi komputasi (*workload decoupling*). Buat warehouse baru `INGESTION_WH` (Size XS atau S, auto-suspend 60 detik) khusus untuk micro-batch. Biarkan query ad-hoc berjalan di `ANALYTICS_WH`. Pisahkan transaksi keduanya agar tidak terjadi resource starvation atau shared lock contention. Karena ingestion micro-batch berukuran kecil namun sering, sizing warehouse kecil yang beroperasi tepat waktu jauh lebih hemat biaya dan menjamin ketersediaan throughput.
3. **Solusi Skenario C**: 
   - **Penyebab**: Terjadi hash join key distribution skew parah. Seluruh record dengan key yang sama di-*hash* ke satu node worker compute yang sama dalam cluster MPP selama fase Network Data Exchange/Shuffle, membebani node tersebut secara asimetris (straggler node) dan memicu memory spillage.
   - **Solusi Alternatif 1 (Salting Key)**: Tambahkan postfix acak (salt) 1..N pada join key untuk nilai hotspot tersebut di tabel sisi kiri, dan lakukan ekspansi baris serupa pada tabel sisi kanan agar data tersebar ke seluruh node worker secara merata.
   - **Solusi Alternatif 2 (Split Queries)**: Pisahkan query menjadi dua cabang: Cabang 1 mengeksekusi subset data tanpa skewed key menggunakan standard hash join, dan Cabang 2 menangani skewed key (`ACCOUNT_ID = 'INTERNAL_SETTLEMENT'`) secara isolatif menggunakan teknik broadcast atau simple filtering, kemudian satukan hasilnya menggunakan `UNION ALL`.

---

### 16. Summary

Modern Cloud Data Warehouse internals menandai evolusi dari sistem basis data monolitik menuju sistem enterprise terdesentralisasi yang tangguh. Keberhasilan implementasi performa berskala petabyte tidak lagi ditentukan oleh kapasitas hardware server tunggal, melainkan oleh pemahaman mendalam tentang abstraksi internal:
1. **Storage-Compute Separation**: Fondasi elastisitas cloud yang memungkinkan isolasi beban kerja, auto-scaling horizontal/vertikal, dan interoperabilitas metadata global tanpa migrasi data fisik.
2. **Columnar Pruning & Layout Engine**: Kinerja query kencang bertumpu pada minimalisasi bytes scanned melalui *Zone Maps metadata pruning*, *sargable filters*, dan pengelompokan (*clustering*) yang memfasilitasi kompresi entropi tinggi seperti RLE dan Dictionary Encoding.
3. **Execution & Memory Hierarchy**: Pemrosesan vectorized berbasis SIMD memeras efisiensi komputasi modern. Kegagalan memahami batas hierarki memori (RAM $\rightarrow$ Local NVMe Scratch Cache $\rightarrow$ Remote Object Storage) berakibat langsung pada fenomena *Disk Spilling*, degradasi latency kueri, dan pembengkakan biaya cloud platform (FinOps). Implementasi arsitektur produksi yang solid menuntut isolasi beban kerja yang disiplin, monitoring query metrics secara proaktif, serta strategi clustering yang terukur.