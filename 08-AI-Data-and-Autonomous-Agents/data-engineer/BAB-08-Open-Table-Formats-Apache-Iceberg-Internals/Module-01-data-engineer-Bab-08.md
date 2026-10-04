# Bab 08: Open Table Formats Apache Iceberg Internals
**Module 01: Core Architecture, Metadata Hierarchy, and Atomic Operations**

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Hierarki Metadata Apache Iceberg**: Mengurai relasi struktural antara Catalog Pointer, Table Metadata (`vN.metadata.json`), Manifest List (`snap-*.avro`), Manifest File (`*.avro`), dan Data/Delete Files (`*.parquet`).
- **Mengevaluasi Mekanisme ACID & Concurrency**: Memvalidasi operasi atomik berbasis *Optimistic Concurrency Control* (OCC) dan memitigasi *commit collisions* pada catalog level.
- **Mengimplementasikan Hidden Partitioning & Partition Evolution**: Mengonfigurasi fungsi transformasi partisi (identity, bucket, truncate, time-based) tanpa mengharuskan rewrites data fisik ataupun rekayasa query manual oleh end-user.
- **Mendeteksi & Mengoptimasi Two-Phase Pruning**: Mengkalkulasi reduksi I/O read amplification menggunakan evaluasi batas metrik (*column-level min/max statistics*) pada level Manifest List dan Manifest File.
- **Membangun Pipeline Data Terisolasi (Snapshot Isolation)**: Mengimplementasikan transaksi write-audit-publish (WAP) serta *time-travel debugging* secara programmatic menggunakan Python dan format engine PyIceberg/PyArrow.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Secara historis, Apache Hive mendefinisikan *table* sebagai kumpulan direktori fisik di dalam file system distributed (HDFS/S3). Pendekatan ini memiliki cacat arsitektural fundamental:
1. **State disimpan di direktori**: Operasi partisi menuntut listing direktori `O(N)` via filesystem client, yang sangat lambat pada S3/GCS.
2. **Tidak atomik**: Perubahan skema, pembaruan partisi berganda, dan *concurrent appends* rentan terhadap *partial writes* serta *inconsistent state*.

Apache Iceberg membalik paradigma ini: **Table state tidak didefinisikan oleh lokasi direktori, melainkan oleh daftar berkas eksplisit (explicit canonical list of files) yang diikat secara hierarkis dalam pohon metadata imutabel (immutable metadata tree)**.

```
[Hive Model: Directory-as-Table]
/warehouse/orders/year=2024/month=03/part-0001.parquet  <-- Kehilangan state eksplisit; butuh recursive listing

[Iceberg Model: File-list-as-Table via Snapshot Tree]
Catalog Pointer -> v1.metadata.json -> Snapshot A -> Manifest List -> Manifest -> [Explicit File References]
```

#### Mental Model: The Distributed Merkle-Tree Analogy
Iceberg berfungsi mirip dengan Git:
- **Catalog** bertindak seperti branch pointer (misalnya `HEAD` atau `refs/heads/main`), yang menunjuk secara atomik ke versi metadata table aktif saat ini.
- **Snapshot** merepresentasikan commit Git yang membekukan kondisi tabel pada waktu tertentu.
- **Manifest List dan Manifest Files** bertindak sebagai tree nodes dan commit blobs, yang menyimpan referensi ke berkas data fisik beserta statistik kolom lengkap.
- **Data Files** bersifat murni *append-only* dan *immutable*. Perubahan data (update/delete) tidak pernah mengubah berkas fisik secara in-place; melainkan menghasilkan berkas metadata baru yang mereferensikan subset data yang valid atau menambahkan delete files.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada skala petabyte, kegagalan arsitektur metastore berbasis direktori menimbulkan implikasi kritis:

1. **Object Store Throttling & List Latency**:
   Pada cloud storage (misalnya Amazon S3), operasi `LIST` dibatasi oleh rate limit request (misal: 3.500 `PUT`/5.500 `GET` per prefix per detik). Sebuah query Hive/Presto yang membaca tabel terpartisi dengan ribuan partisi memerlukan ribuan `LIST calls`, mengakibatkan latensi puluhan detik hanya untuk fase *query planning*. Iceberg mengeliminasi `LIST` call sepenuhnya: seluruh file location dibaca langsung dari Manifest AVRO file secara paralel.

2. **Race Conditions & File Corruption**:
   Dua pipeline streaming/batch yang menulis data secara bersamaan ke partisi Hive yang sama akan saling menimpa data atau meninggalkan staging file parsial jika salah satu job gagal di tengah jalan. Iceberg menggunakan **Compare-And-Swap (CAS)** pada Catalog untuk menjamin serializable atau snapshot isolation.

3. **Regulatory Compliance (GDPR/CCPA Right-to-be-Forgotten)**:
   Menghapus satu record pelanggan dalam dataset 100 TB dengan Hive mengharuskan rewrite partisi penuh dan menimbulkan risiko inkonsistensi pembacaan data selama proses rewrite berlangsung. Melalui pola *Merge-on-Read* (MoR) dengan *Position Delete Files*, Iceberg memungkinkan penandaan baris yang dihapus dalam hitungan milidetik secara atomik tanpa downtime pembacaan.

4. **Reliable LLM Feature Stores & ML Reproducibility**:
   Model AI memerlukan deterministic training sets. Dengan kapabilitas *Zero-Copy Snapshot Time-Travel*, data engineer dapat mengeksekusi model training pada snapshot ID spesifik yang menjamin dataset yang digunakan identik, bahkan ketika data ingest terus berjalan di layer produksi.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah struktur hierarki metadata Apache Iceberg yang mengontrol persistensi data dan koordinasi status transaksi:

```
+-------------------------------------------------------------------------------+
|                            ICEBERG CATALOG LAYER                              |
|     (REST Catalog / Project Nessie / AWS Glue / JDBC / Hive Metastore)        |
|                                                                               |
|               Pointer: current-table-metadata -> "v2.metadata.json"           |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                         TABLE METADATA LAYER (JSON)                           |
|  v2.metadata.json:                                                            |
|  - table-uuid, format-version: 2                                              |
|  - current-snapshot-id: 1002                                                  |
|  - schemas: [ {id: 0, fields: [...]}, ... ]                                   |
|  - partition-specs: [ {spec-id: 0, fields: [date(ts)]}, ... ]                 |
|  - snapshots: [                                                               |
|      { snapshot-id: 1001, manifest-list: "snap-1001.avro", ... },             |
|      { snapshot-id: 1002, manifest-list: "snap-1002.avro", parent-id: 1001 }   |
|    ]                                                                          |
+-------------------------------------------------------------------------------+
                                      |
                     Points to Snapshot 1002 Manifest List
                                      v
+-------------------------------------------------------------------------------+
|                         MANIFEST LIST LAYER (AVRO)                            |
|  snap-1002.avro:                                                              |
|  +--------------------------------------------------------------------------+ |
|  | Entry 1:                                                                 | |
|  | - manifest-path: "m1.avro"                                               | |
|  | - partitions: [field_id: 1000, lower_bound: 2024-03-01, upper: 2024-03-15] | |
|  | - added-snapshot-id: 1001                                                | |
|  +--------------------------------------------------------------------------+ |
|  | Entry 2:                                                                 | |
|  | - manifest-path: "m2.avro"                                               | |
|  | - partitions: [field_id: 1000, lower_bound: 2024-03-16, upper: 2024-03-31] | |
|  | - added-snapshot-id: 1002                                                | |
|  +--------------------------------------------------------------------------+ |
+-------------------------------------------------------------------------------+
                           /                            \
                          /                              \
                         v                                v
+------------------------------------+  +-------------------------------------+
|        MANIFEST FILE (AVRO)        |  |        MANIFEST FILE (AVRO)         |
|  m1.avro:                          |  |  m2.avro:                           |
|  - data_file:                      |  |  - data_file:                       |
|    * file_path: "f1.parquet"       |  |    * file_path: "f3.parquet"        |
|    * partition_values: {2024-03-01}|  |    * partition_values: {2024-03-16} |
|    * record_count: 500,000         |  |    * record_count: 750,000          |
|    * column_sizes: {1: 4MB, 2: 8MB}|  |    * column_sizes: {1: 6MB, 2: 12MB}|
|    * lower_bounds: {id: 1, val: A} |  |    * lower_bounds: {id: 501, val: X}|
|    * upper_bounds: {id: 500,val: Z}|  |    * upper_bounds: {id: 1250,val: Z}|
|  - data_file:                      |  |  - delete_file:                     |
|    * file_path: "f2.parquet"       |  |    * file_path: "pos-del-1.parquet" |
|    * ...                           |  |    * referenced_data_file: "f3.pq"  |
+------------------------------------+  +-------------------------------------+
                  |                                        |
                  +-------------------+                    |
                                      |                    |
                                      v                    v
                       +-----------------------------------------------+
                       |               DATA STORAGE LAYER              |
                       |                  (Parquet/ORC)                |
                       |                                               |
                       |  /data/ts_day=2024-03-01/f1.parquet           |
                       |  /data/ts_day=2024-03-01/f2.parquet           |
                       |  /data/ts_day=2024-03-16/f3.parquet           |
                       |  /data/ts_day=2024-03-16/pos-del-1.parquet     |
                       +-----------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Snapshot Isolation & The Commit Workflow
Ketika engine (Spark, Flink, Trino, atau PyIceberg) melakukan operasi penulisan (*write commit*), engine tidak langsung menimpa tabel. Alur mutasi mengikuti tahapan berikut:

1. **Read Stage**: Engine membaca state snapshot aktif ($S_0$) dari Table Metadata saat ini.
2. **Write Stage**: Engine menulis data baru ke dalam Data File Parquet independen.
3. **Manifest Construction**: Engine menulis satu atau beberapa Manifest File baru yang mereferensikan berkas Parquet yang baru dibuat beserta data statistik metriknya.
4. **Manifest List Creation**: Engine membuat Manifest List baru yang menggabungkan manifest-manifest dari snapshot $S_0$ yang masih valid dengan manifest baru yang dihasilkan pada langkah 3.
5. **Table Metadata Assembly**: Sebuah berkas metadata tabel baru (`v(N+1).metadata.json`) dirakit di storage. Snapshot ID baru ($S_1$) ditambahkan sebagai `current-snapshot-id`.
6. **Atomic Catalog Commit (CAS)**:
   Engine mengirim permintaan pembaruan ke Catalog:
   $$\text{CAS}(\text{expected: } vN, \text{ new: } v(N+1))$$
   Jika pointer catalog saat ini bernilai $vN$, update berhasil, dan $S_1$ resmi menjadi representasi tabel publik. Jika ada proses lain yang berhasil melakukan commit lebih dahulu (mengubah catalog menjadi $v(N+1)_{other}$), CAS gagal, memicu resolusi OCC.

#### B. Optimistic Concurrency Control (OCC) Resolution
Ketika terjadi *commit conflict*, Iceberg tidak langsung membatalkan transaksi. Sebaliknya, protokol OCC mengevaluasi apakah perubahan konkuren memiliki irisan data yang overlap:
- Jika transaksi $T_A$ menambahkan file ke partisi `2024-03-01`, dan transaksi konkuren $T_B$ menambahkan file ke partisi `2024-03-02`, catalog akan me-rebase commit $T_B$ di atas commit $T_A$ secara otomatis tanpa harus membatalkan operasi write data.
- Jika $T_A$ menghapus file atau memodifikasi data yang sedang diubah oleh $T_B$ (misalnya, data delete/update conflict), commit ditolak dengan memicu `CommitFailedException`.

#### C. Hidden Partitioning & Partition Evolution
Tabel tradisional mengharuskan nilai partisi ditulis secara eksplisit sebagai kolom virtual di path filesystem (misalnya `/year=2024/month=03/`). Akibatnya:
- User harus mengubah query: `WHERE event_time >= '2024-03-01'` harus diubah menjadi `WHERE year = 2024 AND month = 3 AND event_time >= '2024-03-01'`. Jika tidak, engine melakukan full table scan.

Iceberg memisahkan logical schema dari physical partition spec melalui **Partition Transforms**:
- Transformasi yang didukung: `identity`, `bucket(N)`, `truncate(W)`, `year`, `month`, `day`, `hour`.
- Nilai partisi dikalkulasi secara internal saat proses tulis dan dicatat langsung di Manifest File.
- **Partition Evolution**: Skema partisi dapat diubah di tengah jalan tanpa me-rewrite data lama.
  - Contoh: Tahun 2023 menggunakan partisi bulanan (`month(ts)`). Tahun 2024 data meningkat drastis sehingga diubah ke partisi harian (`day(ts)`).
  - Iceberg memberikan `spec-id` baru (misal `spec-id: 1`). Manifest lama dievaluasi menggunakan `spec-id: 0`, manifest baru dievaluasi menggunakan `spec-id: 1`. Query engine secara transparan menyelaraskan predikat tanpa kegagalan filter.

#### D. Two-Phase Query Pruning
Untuk meminimalkan pembacaan berkas fisik, Iceberg mengeksekusi dua tahapan eliminasi file:
1. **Manifest List Pruning**: Setiap entry manifest di dalam berkas Manifest List menyimpan bounds partisi minimum dan maksimum (`lower_bound` dan `upper_bound` per partition field). Jika klausa `WHERE` berada di luar rentang ini, manifest file tersebut tidak akan dibaca sama sekali dari storage.
2. **Manifest File Pruning**: Di dalam manifest file yang lolos fase pertama, setiap entri Data File menyimpan statistik kolom (min/max/null value count per column). Jika predikat query (misal `id = 450`) berada di luar rentang `id: [500, 1000]`, berkas Parquet tersebut langsung dieksklusi dari daftar pemindaian (*file planning*).

---

### 6. Production-Ready Code Implementation

Berikut implementasi production-grade menggunakan Python dengan library `pyiceberg` dan `pyarrow` untuk membangun arsitektur tabel Iceberg, memanipulasi snapshot, dan menangani OCC conflict.

```python
"""
Production-grade script for managing Apache Iceberg internal structures,
handling partition evolution, concurrent transactions, and snapshot inspection.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Generator

import pyarrow as pa
from pyiceberg.catalog import Catalog, load_catalog
from pyiceberg.exceptions import CommitFailedException, NoSuchTableError
from pyiceberg.expressions import EqualTo, GreaterThanOrEqual
from pyiceberg.partitioning import PartitionField, PartitionSpec
from pyiceberg.schema import Schema
from pyiceberg.table import Table
from pyiceberg.transforms import DayTransform, IdentityTransform
from pyiceberg.types import (
    DoubleType,
    LongType,
    NestedField,
    StringType,
    TimestampType,
)

# -------------------------------------------------------------------------
# Logging Configuration
# -------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("IcebergInternalsEngine")


# -------------------------------------------------------------------------
# Catalog & Table Factory
# -------------------------------------------------------------------------
class IcebergRepository:
    def __init__(self, warehouse_path: str, catalog_name: str = "local_catalog"):
        self.warehouse_path = warehouse_path
        self.catalog_name = catalog_name
        self.catalog: Catalog = load_catalog(
            catalog_name,
            **{
                "type": "sql",
                "uri": f"sqlite:///{os.path.join(warehouse_path, 'iceberg_catalog.db')}",
                "warehouse": f"file://{warehouse_path}",
            },
        )
        logger.info("Catalog initialized with warehouse path: %s", warehouse_path)

    def get_or_create_table(self, namespace: str, table_name: str) -> Table:
        identifier = f"{namespace}.{table_name}"
        try:
            table = self.catalog.load_table(identifier)
            logger.info("Loaded existing table: %s", identifier)
            return table
        except NoSuchTableError:
            logger.info("Table %s not found. Creating new table.", identifier)
            self.catalog.create_namespace_if_not_exists(namespace)
            return self._create_initial_table(identifier)

    def _create_initial_table(self, identifier: str) -> Table:
        schema = Schema(
            NestedField(field_id=1, name="transaction_id", field_type=LongType(), required=True),
            NestedField(field_id=2, name="customer_id", field_type=StringType(), required=True),
            NestedField(field_id=3, name="amount", field_type=DoubleType(), required=True),
            NestedField(
                field_id=4,
                name="timestamp",
                field_type=TimestampType(),
                required=True,
            ),
        )

        # Initial Partitioning: Transform timestamp to daily partitions
        partition_spec = PartitionSpec(
            PartitionField(
                source_id=4,
                field_id=1000,
                transform=DayTransform(),
                name="timestamp_day",
            )
        )

        table = self.catalog.create_table(
            identifier=identifier,
            schema=schema,
            partition_spec=partition_spec,
            properties={
                "write.format.default": "parquet",
                "write.parquet.compression-codec": "zstd",
                "write.parquet.compression-level": "7",
                "history.expire.max-snapshot-age-ms": "604800000",  # 7 Days
            },
        )
        logger.info("Successfully created table %s with spec ID: %d", identifier, partition_spec.spec_id)
        return table


# -------------------------------------------------------------------------
# Ingestion & Transaction Handlers
# -------------------------------------------------------------------------
class IngestionPipeline:
    def __init__(self, table: Table):
        self.table = table

    def generate_batch(self, start_id: int, count: int, date_str: str) -> pa.Table:
        """Generates deterministic PyArrow RecordBatches for ingestion testing."""
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
        tx_ids = [start_id + i for i in range(count)]
        cust_ids = [f"CUST_{i % 100:04d}" for i in range(count)]
        amounts = [float(10.50 + (i * 1.25)) for i in range(count)]
        timestamps = [dt for _ in range(count)]

        return pa.Table.from_arrays(
            [
                pa.array(tx_ids, type=pa.int64()),
                pa.array(cust_ids, type=pa.string()),
                pa.array(amounts, type=pa.float64()),
                pa.array(timestamps, type=pa.timestamp("us", tz="UTC")),
            ],
            schema=self.table.schema().as_arrow(),
        )

    def write_atomic(self, arrow_data: pa.Table) -> int:
        """Appends data atomically and returns the resulting Snapshot ID."""
        logger.info("Starting atomic append of %d records...", arrow_data.num_rows)
        self.table.append(arrow_data)
        
        # Reload metadata to ensure fresh state
        self.table.refresh()
        current_snapshot = self.table.current_snapshot()
        if not current_snapshot:
            raise RuntimeError("Commit completed but current snapshot is null.")
            
        logger.info(
            "Append successful. Current Snapshot ID: %d, Manifest List: %s",
            current_snapshot.snapshot_id,
            current_snapshot.manifest_list,
        )
        return current_snapshot.snapshot_id


# -------------------------------------------------------------------------
# Metadata Inspection & Internal Diagnostics
# -------------------------------------------------------------------------
class IcebergInspector:
    def __init__(self, table: Table):
        self.table = table

    def audit_metadata_tree(self) -> None:
        """Traverses the full Iceberg internal tree: Metadata -> Manifest Lists -> Manifests -> Files."""
        self.table.refresh()
        current_snapshot = self.table.current_snapshot()
        if not current_snapshot:
            logger.warning("No snapshot available to audit.")
            return

        print("\n" + "=" * 80)
        print(f"ICEBERG METADATA TREE DIAGNOSTIC: {self.table.name()}")
        print("=" * 80)
        print(f"Current Version File: {self.table.metadata_location}")
        print(f"Format Version      : {self.table.metadata.format_version}")
        print(f"Active Snapshot ID  : {current_snapshot.snapshot_id}")
        print(f"Manifest List Path  : {current_snapshot.manifest_list}")
        print("-" * 80)

        # Inspect Manifest Files inside the Manifest List
        manifests = current_snapshot.manifests(io=self.table.io)
        for idx, manifest in enumerate(manifests):
            print(f"--> [Manifest #{idx + 1}] Path: {manifest.manifest_path}")
            print(f"    Added Snapshot ID: {manifest.added_snapshot_id}")
            print(f"    Partition Spec ID: {manifest.partition_spec_id}")
            print(f"    Added Data Files : {manifest.added_files_count}")
            print(f"    Existing Files   : {manifest.existing_files_count}")
            print(f"    Deleted Files    : {manifest.deleted_files_count}")

            # Inspect Data Files referenced inside the Manifest
            entries = manifest.fetch_manifest_entry(io=self.table.io)
            for entry in entries:
                data_file = entry.data_file
                print(f"    └── Data File: {data_file.file_path}")
                print(f"        Records  : {data_file.record_count}")
                print(f"        File Size: {data_file.file_size_in_bytes} bytes")
                print(f"        Bounds   : Lower={data_file.lower_bounds} | Upper={data_file.upper_bounds}")
        print("=" * 80 + "\n")

    def execute_time_travel(self, snapshot_id: int) -> int:
        """Scans the table at a fixed historical point in time."""
        logger.info("Executing Time Travel query targeting Snapshot ID: %d", snapshot_id)
        scan = self.table.scan(snapshot_id=snapshot_id)
        arrow_table = scan.to_arrow()
        logger.info("Retrieved %d rows from snapshot %d", arrow_table.num_rows, snapshot_id)
        return arrow_table.num_rows


# -------------------------------------------------------------------------
# Execution Verification Runtime
# -------------------------------------------------------------------------
def main() -> None:
    temp_dir = tempfile.mkdtemp(prefix="iceberg_engine_")
    try:
        # 1. Initialize Catalog & Table
        repo = IcebergRepository(warehouse_path=temp_dir)
        table = repo.get_or_create_table(namespace="fintech", table_name="ledger")
        pipeline = IngestionPipeline(table)
        inspector = IcebergInspector(table)

        # 2. Ingest Day 1 Data (Snapshot 1)
        data_day_1 = pipeline.generate_batch(start_id=1, count=1000, date_str="2024-03-01")
        snap_1 = pipeline.write_atomic(data_day_1)

        # 3. Ingest Day 2 Data (Snapshot 2)
        data_day_2 = pipeline.generate_batch(start_id=1001, count=1500, date_str="2024-03-02")
        snap_2 = pipeline.write_atomic(data_day_2)

        # 4. Audit Metadata Tree
        inspector.audit_metadata_tree()

        # 5. Verify Time-Travel Determinism
        rows_snap_1 = inspector.execute_time_travel(snap_1)
        rows_snap_2 = inspector.execute_time_travel(snap_2)

        assert rows_snap_1 == 1000, f"Expected 1000 rows in snap 1, got {rows_snap_1}"
        assert rows_snap_2 == 2500, f"Expected 2500 rows in snap 2, got {rows_snap_2}"
        logger.info("ACID Snapshot Isolation validation passed successfully.")

        # 6. Schema & Partition Evolution on-the-fly
        logger.info("Evolving partition schema to include Customer Hash (Bucket Transform)...")
        with table.update_spec() as update:
            update.add_field("customer_id", IdentityTransform(), "customer_id_identity")
        
        logger.info("Updated Partition Specs: %s", table.specs())

    finally:
        shutil.rmtree(temp_dir)
        logger.info("Cleaned temporary warehouse directory: %s", temp_dir)


if __name__ == "__main__":
    main()
```

---

### 7. Edge Cases & Failure Modes (Error Recovery, Validasi, Fallback)

| Edge Case / Failure Mode | Root Cause Internal | Dampak Teknis | Strategi Mitigasi / Error Recovery |
| :--- | :--- | :--- | :--- |
| **Commit Collision (`CommitFailedException`)** | Dua *concurrent writers* mencoba memperbarui catalog pointer secara bersamaan (OCC CAS failure). | Penulisan gagal pada layer commit meskipun data file Parquet sudah terunggah ke storage. | Terapkan *exponential backoff with jitter*. Lakukan `table.refresh()` dan evaluasi konflik: jika modifikasi terjadi pada partisi terisolasi (*non-overlapping partitions*), generate Manifest List baru dan retry CAS secara transparan. |
| **Metadata File Bloat ("Small Manifest Syndrome")** | Pipeline streaming *micro-batch* (misal commit per 30 detik) menghasilkan ribuan Manifest File berukuran < 100 KB. | Latensi *query planning* melonjak drastis karena engine harus membaca ribuan file AVRO kecil. | Jalankan prosedur *manifest compaction* (`rewrite_manifests()`) secara terjadwal untuk menggabungkan manifest-manifest kecil menjadi target ukuran standar (8 MB - 16 MB). |
| **Orphan Data Files Accumulation** | Engine crash di tengah eksekusi penulisan, tepat setelah file Parquet tertulis tetapi sebelum Snapshot Metadata dikomit. | Storage cost membengkak karena berkas data tidak terdaftar di metadata snapshot manapun. | Implementasikan automated garbage collection script menggunakan utility `expire_snapshots` dan `remove_orphan_files` dengan lookback window minimum 24-48 jam. |
| **Delete Amplification (Merge-on-Read)** | Penumpukan file *Position Delete* (`.parquet`) tanpa dilakukan full rewrite compactions. | Query read performance terdegradasi parah (*severe read latency*) karena engine harus memetakan bitmasks/join position deletes saat runtime. | Batasi ambang batas rasio berkas delete: Jika ukuran berkas delete > 20% dari total partition size, jadwalkan proses rewrite CoW (*Copy-on-Write*) atau compaction asynchronous via Spark. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap table format mengimplementasikan detail internal yang berbeda dalam menangani ACID, modifikasi data, dan cataloging:

```
                  ┌──────────────────────────────┐
                  │      OPEN TABLE FORMATS      │
                  └──────────────┬───────────────┘
         ┌───────────────────────┼────────────────────────┐
         ▼                       ▼                        ▼
┌──────────────────┐   ┌───────────────────┐    ┌──────────────────┐
│  Apache Iceberg  │   │    Delta Lake     │    │   Apache Hudi    │
├──────────────────┤   ├───────────────────┤    ├──────────────────┤
│• Complete Engine │   │• Spark First      │    │• Streaming First │
│  Independence    │   │  Optimization     │    │• Native Indexing │
│• Immutable Trees │   │• JSON Transaction │    │• Complex Tuning  │
│  (AVRO + JSON)   │   │  Log (Delta Log)  │    │  (MoR Specialized│
│• Hidden Part.    │   │• Directory Based  │    │• Dynamic Part.   │
└──────────────────┘   └───────────────────┘    └──────────────────┘
```

#### Komparasi Arsitektural Mendalam

| Fitur / Karakteristik | Apache Iceberg | Delta Lake | Apache Hudi |
| :--- | :--- | :--- | :--- |
| **Metadata Representation** | Merkle-Tree: Table JSON $\rightarrow$ Manifest List $\rightarrow$ Manifests (AVRO). | Single-line Transaction Log (`_delta_log/*.json`) + Checkpoints (Parquet). | Commit timeline timeline files + Timeline Service Metadata. |
| **Partitioning Paradigm** | **Hidden Partitioning**: Dihitung runtime, decoupled dari kolom logical. | Directory-based physical partitioning (mirip Hive, meski mendukung liquid clustering). | Directory-based physical partitioning dengan key-based index lookup. |
| **Catalog Independence** | Sangat Tinggi. Catalog memegang kontrol atomik pointer; mendukung REST, Glue, Nessie, JDBC. | Sedang. Bertumpu kuat pada filesystem atomicity (`put-if-absent` S3/ADLS) atau Unity Catalog. | Sedang. Terikat pada metastore dan lock providers (Zookeeper/DynamoDB). |
| **Engine Agnosticism** | Ekosistem sangat netral: First-class support pada Trino, Spark, Flink, DuckDB, Presto. | Awalnya berpusat di Spark, kini meluas via Delta-RS dan Delta Universal Format (UniForm). | Dominan di Spark dan Flink; engine query query ad-hoc membutuhkan custom input formats. |

---

### 9. Best Practices & Standard Industri

Untuk menjamin performa Iceberg pada environment enterprise petabyte-scale, terapkan standard operasional berikut:

1. **REST Catalog Adoption**:
   Tinggalkan Hive Metastore (HMS) tradisional. Gunakan **Iceberg REST Catalog Spec** (misal via Apache Polaris, Tabular/Databricks, Project Nessie, atau AWS Glue Iceberg Engine). REST Catalog memindahkan otorisasi, mutasi metadata, dan penanganan commit conflict ke remote service yang stateless dan scalable.

2. **Partition Specification Guidelines**:
   - Hindari partisi berlebih (*over-partitioning*). Usahakan setiap partisi fisik berukuran antara **100 MB hingga beberapa Gigabyte**.
   - Jangan pernah menggunakan high-cardinality values (seperti UUID, email, exact epoch timestamp) sebagai partisi. Gunakan transformasi: `bucket(100, user_id)` atau `day(transaction_ts)`.

3. **Orchestrated Table Maintenance**:
   Jalankan batch job harian yang menjalankan pemeliharaan tabel secara berkala:
   ```sql
   -- Standard Maintenance Routine (Spark SQL syntax)
   -- 1. Compact data files into optimized 512MB Parquet blocks
   CALL catalog.system.rewrite_data_files(
       table => 'db.events',
       strategy => 'binpack',
       options => map('target-file-size-bytes','536870912')
   );

   -- 2. Consolidate AVRO manifests
   CALL catalog.system.rewrite_manifests(table => 'db.events');

   -- 3. Expire snapshots older than 7 days
   CALL catalog.system.expire_snapshots(
       table => 'db.events',
       older_than => TIMESTAMP '2024-03-01 00:00:00'
   );

   -- 4. Clean orphan files outside the metadata scope
   CALL catalog.system.remove_orphan_files(
       table => 'db.events',
       older_than => TIMESTAMP '2024-03-02 00:00:00'
   );
   ```

4. **Write-Audit-Publish (WAP) Pattern**:
   Gunakan branch/tag feature Iceberg untuk testing:
   - Buat branch staging: `ALTER TABLE db.orders CREATE BRANCH audit_branch;`
   - Ingest data ke branch tersebut: `INSERT INTO db.orders.branch_audit_branch SELECT ...;`
   - Eksekusi unit data testing/data assertion.
   - Jika pass, fast-forward branch utama ke snapshot audit: `CALL catalog.system.fast_forward('db.orders', 'main', 'audit_branch');`

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda adalah Staff Data Platform Engineer yang ditugaskan untuk mengonfigurasi penyimpanan raw clickstream log berkecepatan tinggi. Anda harus membuktikan bahwa perubahan skema partisi (Partition Evolution) dan transaksi rollback dapat dieksekusi secara instan tanpa kehilangan histori audit data.

#### Langkah 1: Persiapan Environment
Siapkan environment lokal menggunakan Python 3.10+ di virtual environment terisolasi:

```bash
python3 -m venv iceberg_lab
source iceberg_lab/bin/activate
pip install --upgrade pip
pip install "pyiceberg[pyarrow,sql-sqlite]"==0.6.0
mkdir -p /tmp/iceberg_lab_warehouse
```

#### Langkah 2: Script Eksekusi Lab
Simpan script berikut sebagai `run_iceberg_lab.py`:

```python
import os
from datetime import datetime, timezone
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, LongType, StringType, TimestampType
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import DayTransform, TruncateTransform

WAREHOUSE_DIR = "/tmp/iceberg_lab_warehouse"

# 1. Initialize SQLite-backed REST-simulating Catalog
catalog = load_catalog(
    "lab_catalog",
    **{
        "type": "sql",
        "uri": f"sqlite:///{os.path.join(WAREHOUSE_DIR, 'catalog.db')}",
        "warehouse": f"file://{WAREHOUSE_DIR}",
    }
)
catalog.create_namespace_if_not_exists("analytics")

# 2. Define Initial Schema: ID, User, Action, Timestamp
schema = Schema(
    NestedField(1, "id", LongType(), required=True),
    NestedField(2, "user_id", StringType(), required=True),
    NestedField(3, "action", StringType(), required=True),
    NestedField(4, "timestamp", TimestampType(), required=True),
)

# Partition initially by day(timestamp)
initial_spec = PartitionSpec(
    PartitionField(source_id=4, field_id=1000, transform=DayTransform(), name="ts_day")
)

table_identifier = "analytics.clickstream"
if catalog.table_exists(table_identifier):
    catalog.drop_table(table_identifier)

table = catalog.create_table(
    identifier=table_identifier,
    schema=schema,
    partition_spec=initial_spec,
)
print(f"[Lab Step 1] Created Table: {table_identifier} | Spec ID: {table.spec().spec_id}")

# 3. Write Batch 1 (V1 Partitioning)
batch1_data = pa.Table.from_arrays(
    [
        pa.array([1, 2], type=pa.int64()),
        pa.array(["user_a", "user_b"], type=pa.string()),
        pa.array(["login", "view"], type=pa.string()),
        pa.array([datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                  datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)], 
                 type=pa.timestamp("us", tz="UTC")),
    ],
    schema=table.schema().as_arrow()
)
table.append(batch1_data)
table.refresh()
v1_snapshot_id = table.current_snapshot().snapshot_id
print(f"[Lab Step 2] Committed Batch 1 | Snapshot ID: {v1_snapshot_id}")

# 4. Partition Evolution: Menambahkan Sub-partitioning tanpa me-rewrite tabel
with table.update_spec() as update:
    update.add_field("user_id", TruncateTransform(width=2), "user_prefix")

table.refresh()
print(f"[Lab Step 3] Evolved Table Partitioning. New Active Spec ID: {table.spec().spec_id}")

# 5. Write Batch 2 (V2 Partitioning)
batch2_data = pa.Table.from_arrays(
    [
        pa.array([3, 4], type=pa.int64()),
        pa.array(["user_c", "user_d"], type=pa.string()),
        pa.array(["click", "logout"], type=pa.string()),
        pa.array([datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                  datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc)], 
                 type=pa.timestamp("us", tz="UTC")),
    ],
    schema=table.schema().as_arrow()
)
table.append(batch2_data)
table.refresh()
v2_snapshot_id = table.current_snapshot().snapshot_id
print(f"[Lab Step 4] Committed Batch 2 under Spec ID {table.spec().spec_id} | Snapshot ID: {v2_snapshot_id}")

# 6. Verification: Seamless Read Across Partition Generations
full_read = table.scan().to_arrow()
print(f"[Lab Step 5] Querying entire table across different specs. Rows returned: {full_read.num_rows}")
assert full_read.num_rows == 4

# 7. Verification: Time Travel back to Snapshot 1
past_read = table.scan(snapshot_id=v1_snapshot_id).to_arrow()
print(f"[Lab Step 6] Time Travel to Snapshot {v1_snapshot_id}. Rows returned: {past_read.num_rows}")
assert past_read.num_rows == 2

print("\n>>> Lab Exercise Successfully Executed: All ACID assertions verified. <<<")
```

#### Langkah 3: Eksekusi dan Output Validasi
Jalankan skrip:
```bash
python run_iceberg_lab.py
```

Output terminal yang diharapkan:
```text
[Lab Step 1] Created Table: analytics.clickstream | Spec ID: 0
[Lab Step 2] Committed Batch 1 | Snapshot ID: <SNAPSHOT_ID_1>
[Lab Step 3] Evolved Table Partitioning. New Active Spec ID: 1
[Lab Step 4] Committed Batch 2 under Spec ID 1 | Snapshot ID: <SNAPSHOT_ID_2>
[Lab Step 5] Querying entire table across different specs. Rows returned: 4
[Lab Step 6] Time Travel to Snapshot <SNAPSHOT_ID_1>. Rows returned: 2

>>> Lab Exercise Successfully Executed: All ACID assertions verified. <<<
```

#### Langkah 4: Lab Cleanup
```bash
rm -rf /tmp/iceberg_lab_warehouse
deactivate
```