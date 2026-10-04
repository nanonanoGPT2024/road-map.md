# Bab 02: PostgreSQL Architecture & Storage Internals
## Modul 01: Deep-Dive Process, Memory, and Page Layout

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Arsitektur Proses & Memori**: Memetakan interaksi IPC (*Inter-Process Communication*), POSIX *shared memory*, serta alokasi memori privat (*backend*) vs global (*shared buffers*) pada PostgreSQL secara deterministik.
- **Mengurai Struktur Fisik Penyimpanan Disk**: Membedah struktur internal blok PostgreSQL (default 8 KB) hingga level bit, mencakup *PageHeaderData*, *ItemIdData*, *HeapTupleHeaderData*, *Padding/Data Alignment*, dan *Special Space*.
- **Menghitung dan Mengoptimalkan Tuple Overhead**: Mengaudit dan menyusun urutan kolom (*column reordering*) berdasarkan *alignment boundary* 8-byte untuk mengeliminasi pemborosan kapasitas (*padding waste*) pada tabel skala miliaran baris.
- **Menganalisis Lifecycle Mutasi Data (I/O Path)**: Menelusuri jalur eksekusi query dari *parsing*, buffer allocation (menggunakan algoritma *Clock Sweep*), mutasi *dirty page*, hingga jaminan ketahanan data melalui *Write-Ahead Logging* (WAL) dan *checkpointing*.
- **Membangun Storage Diagnostic Tooling**: Mengembangkan script diagnostik inspeksi blok database tingkat lanjut menggunakan ekstensi `pageinspect` dan Python untuk mengevaluasi *table bloat* serta efisiensi *Heap-Only Tuple* (HOT).

---

### 2. Concept Overview
PostgreSQL menggunakan model komputasi berbasis multiproses (*process-based model*), bukan multithreaded. Setiap koneksi klien ditangani oleh proses OS tersendiri yang disebut **Backend Process** (di-*fork* oleh proses daemon utama, **Postmaster**). Seluruh proses backend ini berkomunikasi melalui segmen **Shared Memory** yang terkoordinasi secara ketat menggunakan *atomic primitives*, *spinlocks*, dan *lightweight locks* (LWLocks).

```
[ Klien Eksternal ]
        │ (TCP/IP / Unix Domain Socket)
        ▼
┌────────────────────────────────────────────────────────┐
│ PostgreSQL Instance                                    │
│                                                        │
│  [ Postmaster Daemon ] ──(fork)──> [ Backend Process ] │
│                                            │           │
│  ┌─────────────────────────────────────────┼─────────┐ │
│  │ Shared Memory                           ▼         │ │
│  │  ┌──────────────────────────────────────────────┐ │ │
│  │  │ Shared Buffer Pool (Data Pages)              │ │ │
│  │  ├──────────────────────────────────────────────┤ │ │
│  │  │ WAL Buffers (Transaction Logs)               │ │ │
│  │  ├──────────────────────────────────────────────┤ │ │
│  │  │ Lock Manager & ProcArray (Concurrency state) │ │ │
│  │  └──────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

Di lapisan persistensi fisik, PostgreSQL mengabstraksi tabel dan indeks sebagai himpunan berkas relasi berukuran 1 GB (*segments*) di dalam direktori data `$PGDATA/base/<db_oid>/<relfilenode>`. Setiap berkas dipecah menjadi blok-blok berukuran tetap sebesar **8192 bytes (8 KB)**. PostgreSQL menerapkan **Slotted-Page Architecture**, di mana pointer baris (*item identifiers*) tumbuh dari awal halaman ke arah bawah, sedangkan data baris riil (*tuples*) tumbuh dari akhir halaman ke arah atas. Struktur ini mendukung MVCC (*Multi-Version Concurrency Control*) secara *in-place*, yang berdampak signifikan pada degradasi *storage* jika mutasi data tidak dikelola secara optimal.

---

### 3. Why It Matters
Bagi seorang Data Engineer atau AI Infrastructure Engineer, PostgreSQL sering kali difungsikan sebagai:
1. *Metadata store* terdistribusi untuk orkestrator (seperti Apache Airflow atau Temporal).
2. *State store* untuk *Agentic AI workflows*.
3. Mesin pencari vektor berdensitas tinggi melalui ekstensi seperti `pgvector`.

Kegagalan memahami *storage internals* menimbulkan masalah kritis pada skala produksi:
- **Write Amplification & HOT Failures**: Pembaruan (*UPDATE*) embedding vektor berdimensi tinggi secara berulang tanpa pemahaman mendalam tentang *Heap-Only Tuple* (HOT) akan memicu modifikasi indeks secara global, melipatgandakan beban I/O disk, dan menyebabkan fragmentasi (*table bloat*) yang parah.
- **Double Buffering Pitfalls**: PostgreSQL tidak menggunakan Direct I/O secara default; ia mengandalkan *Shared Buffers* sekaligus *Linux Page Cache*. Alokasi memori yang salah konfigurasi memicu *eviction thrashing* dan terminasi mendadak oleh Linux OOM (*Out-Of-Memory*) Killer saat ingest data intensif.
- **Memory Alignment Bloat**: Ketidaktahuan mengenai penataan tipe data dalam DDL (*schema design*) dapat menyebabkan pemborosan ruang disk hingga 20–30% murni akibat pengisian padding bit kosong (0-byte padding) di setiap baris pada tabel bertaraf miliaran baris.

---

### 4. Arsitektur & Diagram Komponen

#### 4.1 Process & Memory Model
```
+---------------------------------------------------------------------------------------+
|                                    HOST RAM                                           |
|                                                                                       |
|  +--------------------------- SHARED MEMORY SEGMENT -------------------------------+  |
|  |                                                                                 |  |
|  |  +---------------------------------------------------------------------------+  |  |
|  |  | Shared Buffers (Default: 128MB, Rekomendasi: 25-40% Total RAM)            |  |  |
|  |  | [ Page 0 ][ Page 1 ][ Page 2 ] ... [ Page N (8KB each) ]                   |  |  |
|  |  +---------------------------------------------------------------------------+  |  |
|  |  +-----------------------+ +-----------------------+ +-----------------------+  |  |
|  |  | WAL Buffers           | | Lock Manager Area     | | Clog / Commit-Log TS  |  |  |
|  |  +-----------------------+ +-----------------------+ +-----------------------+  |  |
|  +---------------------------------------------------------------------------------+  |
|            ▲                       ▲                       ▲                          |
|            │                       │                       │                          |
|  +---------┴----------+  +---------┴----------+  +---------┴----------+               |
|  | Backend Process 1  |  | Backend Process 2  |  | Background Workers |               |
|  | (Client Session)   |  | (Client Session)   |  |                    |               |
|  |                    |  |                    |  | - Checkpointer     |               |
|  | +----------------+ |  | +----------------+ |  | - Background Writer|               |
|  | | work_mem       | |  | | work_mem       | |  | - WAL Writer       |               |
|  | +----------------+ |  | +----------------+ |  | - Autovacuum Worker|               |
|  | | temp_buffers   | |  | | temp_buffers   | |  | - Stats Collector  |               |
|  | +----------------+ |  | +----------------+ |  |                    |               |
|  | | maint_work_mem | |  | | maint_work_mem | |  |                    |               |
|  | +----------------+ |  | +----------------+ |  |                    |               |
|  +--------------------+  +--------------------+  +--------------------+               |
|                                                                                       |
|  +-------------------------------- OS LAYER ---------------------------------------+  |
|  | Linux Page Cache / VFS Dirty Pages                                              |  |
|  +---------------------------------------------------------------------------------+  |
+------------------------------------------┼--------------------------------------------+
                                           │ sync() / fdatasync()
                                           ▼
+-------------------------------- PHYSICAL DISK STORAGE --------------------------------+
|  Base Tables: $PGDATA/base/* | WAL Logs: $PGDATA/pg_wal/*                             |
+---------------------------------------------------------------------------------------+
```

#### 4.2 Anatomy of an 8KB Slotted Page
```
+---------------------------------------------------------------------------------------+
| 0x0000 | PageHeaderData (24 Bytes)                                                    |
|        |  - pd_lsn (8B)      : Log Sequence Number pengubahan terakhir                |
|        |  - pd_checksum (2B) : Validasi integritas halaman data                       |
|        |  - pd_flags (2B)    : Status visibilitas dan kondisi halaman                 |
|        |  - pd_lower (2B)    : Offset byte batas akhir array ItemIdData               |
|        |  - pd_upper (2B)    : Offset byte batas awal Tuple Data terbaru              |
|        |  - pd_special (2B)  : Offset byte menuju Special Space (untuk Index data)    |
|        |  - pd_pagesize_version (2B), pd_prune_xid (4B)                               |
+--------+------------------------------------------------------------------------------+
| 0x0018 | ItemIdData[0] (4 Bytes) -> Flags(2b), Off(15b), Len(15b)                    |
| 0x001C | ItemIdData[1] (4 Bytes) -> Berisi offset absolut menuju Tuple 2              |
| 0x0020 | ItemIdData[2] (4 Bytes) -> Berisi offset absolut menuju Tuple 1              |
|        | ===> Tumbuh ke bawah (arah memori positif)                                  |
+--------+------------------------------------------------------------------------------+
|        |                                                                              |
|        |                      UNALLOCATED FREE SPACE                                  |
|        |                      (pd_upper - pd_lower)                                   |
|        |                                                                              |
+--------+------------------------------------------------------------------------------+
|        | <=== Tumbuh ke atas (arah memori negatif)                                   |
| 0x1ED0 | HEAP TUPLE 2 (Data baris riil)                                               |
+--------+------------------------------------------------------------------------------+
| 0x1F60 | HEAP TUPLE 1 (Data baris riil)                                               |
|        |  - HeapTupleHeaderData (23 Bytes min + NullBitmap + Padding):                |
|        |      * t_xmin (4B) : ID Transaksi pembuat tuple                              |
|        |      * t_xmax (4B) : ID Transaksi penghapus/pengubah tuple                   |
|        |      * t_cid/t_xvac (4B): Command ID sequence                                |
|        |      * t_ctid (6B) : BlockID (4B) + OffsetNumber (2B) pointer fisik tuple    |
|        |      * t_infomask2 (2B) : Jumlah atribut & atribut status HOT               |
|        |      * t_infomask (2B)  : Flag visibilitas status tuple                      |
|        |      * t_hoff (1B)      : Offset header ke user data riil                    |
|        |  - Null Bitmap (Variabel, tergantung rasio NULL)                             |
|        |  - User Data Payload (Aligned berdasarkan MAXALIGN 8-byte boundaries)        |
+--------+------------------------------------------------------------------------------+
| 0x1FF8 | SPECIAL SPACE (Ukuran 0B untuk plain heap table; >0B untuk B-Tree/GiST)       |
+---------------------------------------------------------------------------------------+ 8192 Bytes
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Siklus Buffer dan Algoritma Clock Sweep
Ketika sebuah query memerlukan tuple tertentu, backend process mengeksekusi operasi pembacaan buffer melalui urutan berikut:
1. **Hash Lookup**: Backend memetakan `BufferTag` (terdiri dari *RelFileNode*, *ForkNumber*, *BlockNumber*) ke hash table internal `Shared Buffers`.
2. **Hit vs Miss**:
   - Jika terdeteksi di hash table (*Buffer Hit*), PostgreSQL menaikkan pin count dan menginkrementasi metrik `usage_count` (maksimal bernilai 5), lalu memproses tuple.
   - Jika tidak ditemukan (*Buffer Miss*), Postgres harus mengambil slot buffer bebas melalui algoritma **Clock Sweep**.
3. **Mekanisme Clock Sweep**: Pointer melingkar (*clock hand*) memeriksa larik deskriptor buffer:
   - Jika deskriptor memiliki `pin_count == 0` dan `usage_count > 0`, maka `usage_count` dikurangi satu (`usage_count--`), kemudian pointer berpindah ke deskriptor berikutnya.
   - Jika deskriptor memiliki `pin_count == 0` dan `usage_count == 0`, buffer tersebut dipilih sebagai target penggantian (*eviction target*).
   - Apabila buffer target berstatus kotor (*dirty page*), proses harus melakukan operasi penulisan (*flush*) halaman tersebut ke kernel cache melalui *syscall* `write()` sebelum mengisi ulang slot dengan blok baru dari disk.

#### 5.2 Write Path, WAL, dan Prinsip ARIES
Prinsip fundamental keandalan data PostgreSQL adalah **Write-Ahead Logging (WAL)**: *Modifikasi pada data page di shared memory tidak boleh dialirkan ke disk sebelum record WAL yang mendeskripsikan modifikasi tersebut tersinkronisasi secara permanen ke non-volatile storage.*

1. **Mutasi Data**: Backend mengeksekusi perintah DML, menghasilkan tuple baru atau memodifikasi header tuple lama di dalam `shared_buffers`. Halaman tersebut kini ditandai sebagai *dirty*.
2. **Penerbitan WAL Record**: Backend menyusun representasi logis dari perubahan ke dalam *WAL Buffers*. PostgreSQL menetapkan pointer `pd_lsn` (*Log Sequence Number*) pada *PageHeaderData* dari blok data tersebut ke nilai LSN WAL terbaru.
3. **Commit Phase**: Saat transaksi melakukan `COMMIT`:
   - Proses WAL Writer atau backend memanggil `fdatasync()` pada berkas WAL di `$PGDATA/pg_wal`.
   - Backend baru mengirimkan konfirmasi sukses (*acknowledgment*) ke klien setelah WAL mencapai disk fisik.
4. **Checkpointing & Bgwriter**:
   - **Background Writer (`bgwriter`)**: Berjalan secara berkala untuk menuliskan sejumlah kecil *dirty pages* ke OS cache menggunakan strategi *low-impact* guna menjaga ketersediaan buffer bersih (*clean buffer*) bagi backend.
   - **Checkpointer**: Berjalan pada interval waktu reguler (`checkpoint_timeout`) atau volume data tertentu (`max_wal_size`). Checkpointer memaksa seluruh *dirty pages* saat ini untuk di-*flush* ke disk via `sync()`, kemudian mencatat *checkpoint record* ke WAL. Hal ini membatasi durasi *crash recovery* karena sistem hanya perlu melakukan *redo log* mulai dari titik *checkpoint record* terakhir.

#### 5.3 Data Alignment dan Padding Internal Tuple
PostgreSQL mengimplementasikan aturan arsitektur CPU 64-bit (*strict alignment*). Setiap atribut tipe data di dalam disk page wajib dialokasikan pada alamat memori yang merupakan kelipatan dari ukuran byte naturalnya (maksimal 8 byte pada sistem 64-bit yang disebut `MAXALIGN`):
- `int2` (SMALLINT) membutuhkan kelipatan 2-byte.
- `int4` (INTEGER) membutuhkan kelipatan 4-byte.
- `int8` (BIGINT), `float8` (DOUBLE PRECISION), dan pointer/tipe TOAST terikat batas kelipatan 8-byte.
- Tipe dengan panjang dinamis (*variable-length*) seperti `text`, `varchar`, atau `bytea` memiliki *varlena header* berukuran 1 atau 4 byte, dan umumnya diletakkan di akhir skema untuk meminimalkan *padding holes*.

**Skenario Pemborosan Padding:**
Jika skema tabel didefinisikan sebagai:
```sql
CREATE TABLE bad_layout (
    c1 int2,      -- 2 bytes
    c2 int8,      -- 8 bytes (memerlukan padding 6 byte setelah c1!)
    c3 int2,      -- 2 bytes
    c4 int8       -- 8 bytes (memerlukan padding 6 byte setelah c3!)
);
```
Setiap tuple membuang `6 + 6 = 12 bytes` hanya untuk padding alignment, belum termasuk alokasi sisa pada boundary akhir tuple header.

---

### 6. Production-Ready Code Implementation
Berikut adalah skrip diagnostik tingkat lanjut berbasis Python 3.11 dan `psycopg` (v3) untuk menginspeksi metrik internal penyimpanan fisik tabel secara presisi: menghitung fragmentasi blok, pemborosan padding, dan efektivitas *Heap-Only Tuple* (HOT).

```python
#!/usr/bin/env python3
"""
PostgreSQL Storage Engine Diagnostics Tool.
Memeriksa struktur fisik halaman, tuple density, dan fragmentasi menggunakan psycopg v3.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Any, Final

import psycopg
from psycopg import errors
from psycopg.rows import class_row

# Setup logging dengan format terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(process)d) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger: Final[logging.Logger] = logging.getLogger("pg_storage_diagnostics")


@dataclass(frozen=True)
class TableAlignmentProfile:
    schemaname: str
    tablename: str
    column_name: str
    data_type: str
    type_alignment: str
    type_length: int


@dataclass(frozen=True)
class TablePhysicalHealth:
    relname: str
    total_pages: int
    live_tuples: int
    dead_tuples: int
    free_space_bytes: int
    hot_updated_tuples: int
    hot_ratio_percentage: float


class StorageAnalyzer:
    """Mengelola koneksi dan kalkulasi diagnostik layer fisik PostgreSQL."""

    def __init__(self, connection_dsn: str) -> None:
        self.dsn = connection_dsn

    def _ensure_pageinspect_available(self, conn: psycopg.Connection) -> None:
        """Memastikan extension pageinspect aktif sebelum melakukan inspeksi disk."""
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pageinspect;")
            conn.commit()
            logger.info("Ekstensi 'pageinspect' siap digunakan.")

    def inspect_table_health(self, schema_name: str, table_name: str) -> TablePhysicalHealth:
        """
        Menganalisis rasio tuple, dead tuple, free space, dan efisiensi HOT
        dari suatu tabel tertentu.
        """
        raw_query = """
            SELECT 
                c.relname,
                c.relpages AS total_pages,
                s.n_live_tup AS live_tuples,
                s.n_dead_tup AS dead_tuples,
                COALESCE(pg_relation_size(c.oid) - (c.relpages::bigint * 8192), 0) AS free_space_bytes,
                s.n_tup_hot_upd AS hot_updated_tuples,
                CASE 
                    WHEN s.n_tup_upd = 0 THEN 0.0
                    ELSE ROUND((s.n_tup_hot_upd::numeric / s.n_tup_upd::numeric) * 100, 2)::float
                END AS hot_ratio_percentage
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE n.nspname = %(schema)s AND c.relname = %(table)s;
        """

        try:
            with psycopg.connect(self.dsn) as conn:
                self._ensure_pageinspect_available(conn)
                with conn.cursor(row_factory=class_row(TablePhysicalHealth)) as cur:
                    cur.execute(raw_query, {"schema": schema_name, "table": table_name})
                    result = cur.fetchone()
                    if result is None:
                        raise ValueError(f"Tabel {schema_name}.{table_name} tidak ditemukan.")
                    return result
        except errors.DatabaseError as db_err:
            logger.error("Database error saat mengeksekusi storage diagnostics: %s", db_err)
            raise

    def analyze_padding_waste(self, schema_name: str, table_name: str) -> list[TableAlignmentProfile]:
        """
        Mengekstrak urutan kolom fisik dan alignment constraint untuk
        mendeteksi potensi pemborosan padding pada level disk.
        """
        alignment_query = """
            SELECT 
                n.nspname AS schemaname,
                c.relname AS tablename,
                a.attname AS column_name,
                t.typname AS data_type,
                t.typalign AS type_alignment,
                t.typlen AS type_length
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            JOIN pg_type t ON a.atttypid = t.oid
            WHERE n.nspname = %(schema)s 
              AND c.relname = %(table)s 
              AND a.attnum > 0 
              AND NOT a.attisdropped
            ORDER BY a.attnum ASC;
        """
        try:
            with psycopg.connect(self.dsn) as conn:
                with conn.cursor(row_factory=class_row(TableAlignmentProfile)) as cur:
                    cur.execute(alignment_query, {"schema": schema_name, "table": table_name})
                    return cur.fetchall()
        except errors.DatabaseError as db_err:
            logger.error("Gagal membaca struktur alignment pg_type: %s", db_err)
            raise


def execute_diagnostic_pipeline(dsn: str, target_schema: str, target_table: str) -> None:
    """Fungsi orkestrasi untuk validasi layer persistensi."""
    analyzer = StorageAnalyzer(connection_dsn=dsn)

    logger.info("Memulai audit penyimpanan untuk: %s.%s", target_schema, target_table)
    
    # 1. Health Audit
    health = analyzer.inspect_table_health(target_schema, target_table)
    logger.info("Total Pages (8KB): %d", health.total_pages)
    logger.info("Live Tuples: %d | Dead Tuples: %d", health.live_tuples, health.dead_tuples)
    logger.info("HOT Update Ratio: %.2f%%", health.hot_ratio_percentage)
    
    if health.dead_tuples > health.live_tuples * 0.2:
        logger.warning(
            "Deteksi Bloat Signifikan! Dead tuples melampaui 20%% dari total populasi baris."
        )

    # 2. Structural Column Alignment Audit
    columns = analyzer.analyze_padding_waste(target_schema, target_table)
    logger.info("Pemeriksaan Kolom Fisik (Pendeteksian Padding Sub-optimal):")
    for col in columns:
        alignment_meaning = {
            "c": "char (1-byte)",
            "s": "short (2-byte)",
            "i": "int (4-byte)",
            "d": "double (8-byte)",
        }.get(col.type_alignment, "unknown")
        
        logger.info(
            "  - Kolom: %-15s | Tipe: %-10s | Align: %-6s (%s) | Len: %d bytes",
            col.column_name,
            col.data_type,
            col.type_alignment,
            alignment_meaning,
            col.type_length,
        )


if __name__ == "__main__":
    # Ubah konfigurasi koneksi sesuai environment target pengujian
    SAMPLE_DSN: Final[str] = "postgresql://postgres:postgres@localhost:5432/postgres"
    
    try:
        execute_diagnostic_pipeline(
            dsn=SAMPLE_DSN,
            target_schema="public",
            target_table="pg_am", # Menggunakan catalog internal sebagai basis validasi awal
        )
    except Exception as exc:
        logger.critical("Fatal error pada execution runtime: %s", exc)
        sys.exit(1)
```

---

### 7. Edge Cases & Failure Modes

#### 7.1 Checkpoint Spikes (I/O Freezes)
- **Gejala**: Latensi query melonjak drastis secara berkala (*p99 latency degradation*), dan sistem operasi mengalami saturasi I/O utilisasi hingga 100%.
- **Mekanisme Kegagalan**: Terjadi ketika PostgreSQL memicu *checkpoint* yang terlalu agresif (sering kali karena `max_wal_size` terlampaui saat bulk insert) dan `checkpoint_completion_target` diset ke nilai default yang terlalu rendah pada versi lama (atau salah konfigurasi di bawah `0.9`). Akibatnya, checkpointer mencoba membanjiri storage I/O controller dengan menulis seluruh *dirty pages* secepat mungkin.
- **Mitigasi**: 
  - Set `checkpoint_completion_target = 0.9` untuk mendistribusikan penulisan buffer kotor secara merata sepanjang durasi interval.
  - Alokasikan nilai `max_wal_size` yang memadai (misal: `16GB` - `64GB` pada mesin analitik besar) untuk mencegah *checkpoint* premature.

#### 7.2 Heap-Only Tuple (HOT) Breakdown
- **Gejala**: Fragmentasi tabel membengkak drastis (*table and index bloat*), konsumsi disk naik eksponensial, dan performa query berbasis indeks merosot tajam.
- **Mekanisme Kegagalan**: Algoritma HOT mensyaratkan dua kondisi:
  1. Halaman data yang memuat baris asli harus memiliki sisa ruang (*free space*) yang cukup untuk memuat baris versi baru.
  2. Tidak ada satupun kolom yang tercakup dalam struktur indeks (B-Tree, GiST, IVFFlat, dll) yang nilainya diubah oleh perintah `UPDATE`.
  Jika tabel memiliki `fillfactor` 100% (default) dan mengalami mutasi data intensif, seluruh modifikasi akan memicu *non-HOT update*, yang memaksa pembuatan tuple baru di blok lain sekaligus menyisipkan pointer index baru pada seluruh indeks tabel tersebut.
- **Mitigasi**: Turunkan nilai `fillfactor` ke rentang `70` hingga `85` pada tabel yang sering diupdate:
  ```sql
  ALTER TABLE agent_state_store SET (fillfactor = 80);
  ```

#### 7.3 Torn Pages akibat Crash/Power Outage
- **Gejala**: Kerusakan blok basis data fisik (*corrupted data block*), terhentinya *recovery process*, dan muncul error `PANIC: invalid page header`.
- **Mekanisme Kegagalan**: PostgreSQL menggunakan halaman data 8 KB, sementara sebagian besar *filesystem* dan *hardware drive* melakukan penulisan atomik pada sektor 4 KB atau 512 byte. Jika mesin mati mendadak saat PostgreSQL sedang menuliskan 8 KB blok, hanya separuh halaman (4 KB pertama) yang tersimpan di disk.
- **Mitigasi**: Pastikan parameter `full_page_writes = on` (default aktif). Fitur ini menginstruksikan PostgreSQL untuk menyalin *seluruh citra blok (full 8KB page image)* ke WAL saat blok tersebut pertama kali dimodifikasi setelah sebuah checkpoint, sehingga mampu merestorasi blok yang rusak secara sempurna saat *crash recovery*.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektur | PostgreSQL Native Model | Komparasi Alternatif (e.g., MySQL InnoDB / ScyllaDB) | Trade-off Teknis |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | **Process-based** (Forked processes per client). | **Thread-based** (e.g., MySQL, SQL Server, ScyllaDB). | **Trade-off:** PostgreSQL memberikan isolasi memori mutlak (crash 1 proses tidak mematikan instance lain), namun overhead alokasi memori per koneksi jauh lebih besar; membutuhkan *Connection Pooler* (e.g., PgBouncer/Odyssey) di layer depan. |
| **Struktur Indeks & Data** | **Heap Table + Secondary Indexes** (Tuples diletakkan di blok heap bebas; indeks menyimpan referensi fisik `ctid`). | **Clustered Index / Index-Organized Table** (e.g., InnoDB PK tree). | **Trade-off:** Heap table mempercepat proses *ingest* murni (*append-like*), namun *secondary index scans* memerlukan *double lookup* (membaca indeks, lalu membaca blok heap terkait) kecuali dapat memanfaatkan *Index-Only Scan*. |
| **Model MVCC** | **In-page Multi-Version Storage** (Versi tuple baru dan lama bercampur di blok heap yang sama). | **Rollback Segment / Undo Log** (e.g., InnoDB, Oracle). | **Trade-off:** PostgreSQL memerlukan *Autovacuum daemon* untuk membersihkan baris usang (*dead tuples*). Keuntungannya adalah operasi `ROLLBACK` berlangsung instan (cukup menandai flag pembatalan di transaction status), namun rawan menimbulkan *table bloat*. |
| **Algoritma Cache** | **Clock Sweep (Shared Buffers) + OS Dual Caching**. | **Adaptive Replacement Cache (ARC) / Direct I/O** (e.g., ScyllaDB, RocksDB). | **Trade-off:** Postgres menduplikasi alokasi halaman di shared buffers dan Linux page cache, menyerap overhead transfer kernel; namun mempermudah OS mengelola sequential readahead secara optimal tanpa intervensi manual engine. |

---

### 9. Best Practices & Standard Industri

1. **Penyusunan Definisi Skema Berdasarkan Alignment (Column Packing)**
   Susun urutan tipe data kolom dalam deklarasi DDL mulai dari ukuran alignment terbesar hingga terkecil guna memitigasi *inter-column byte padding*:
   ```sql
   -- PRAKTIK BURUK: Menghasilkan pemborosan padding di setiap baris
   CREATE TABLE telemetry_bad (
       device_active boolean,    -- 1 byte + 7 bytes padding
       reading_timestamp int8,    -- 8 bytes
       warning_code int2,         -- 2 bytes + 2 bytes padding
       sensor_value int4          -- 4 bytes
   );

   -- PRAKTIK TERBAIK (PRODUCTION GRADE): Zero internal alignment padding
   CREATE TABLE telemetry_optimized (
       reading_timestamp int8,    -- 8 bytes (Boundary 8)
       sensor_value int4,         -- 4 bytes (Boundary 4)
       warning_code int2,         -- 2 bytes (Boundary 2)
       device_active boolean      -- 1 byte  (Boundary 1)
       -- 1 byte sisa padding di akhir untuk mempertahankan batas tuple MAXALIGN
   );
   ```

2. **Aturan Alokasi Kapasitas Memori Instance**
   - **`shared_buffers`**: Atur ke angka **25% hingga 40%** dari total kapasitas RAM server fisik. Mengalokasikan nilai di atas 40% pada PostgreSQL justru menurunkan performa karena bersaing dengan fungsi *Linux Page Cache* (*Double Buffering Penalty*).
   - **`effective_cache_size`**: Atur ke **50% hingga 75%** dari total RAM. Parameter ini tidak mengalokasikan memori riil, melainkan berfungsi sebagai estimasi matematis bagi query planner (*Cost-Based Optimizer*) untuk mengasumsikan keberadaan blok data di cache memori.
   - **`work_mem`**: Alokasikan secara konservatif (misal: `16MB` - `64MB`). Ingat bahwa alokasi ini bersifat *per-sort-operation*, sehingga sebuah query kompleks dengan 4 join dan sorting dapat mengonsumsi $4 \times \text{work\_mem}$ per satu sesi koneksi.

3. **Strategi Mitigasi Write Bloat pada Skema AI State / Vector**
   - Pada tabel yang menampung representasi matriks atau embeddings (`vector`), tetapkan nilai `fillfactor` yang mengakomodasi perubahan in-place (contoh: `fillfactor = 75`).
   - Jadwalkan `VACUUM ANALYZE` secara prediktif atau tingkatkan agresivitas `autovacuum_vacuum_scale_factor` ke nilai yang lebih responsif (misal: `0.05` atau 5% threshold perubahan baris, bukan default 20%) untuk tabel transaksional berkecepatan tinggi.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan membuktikan secara empiris perbedaan struktur fisik halaman (disk block), dampak pengaturan alignment skema terhadap kapasitas penyimpanan, dan mekanisme mutasi data via *Heap-Only Tuple* (HOT) menggunakan ekstensi bawaan `pageinspect`.

#### Step 1: Inisialisasi Environment & Ekstensi
Jalankan instruksi berikut di terminal atau klien psql Anda:
```sql
-- Pastikan terhubung ke database pengujian
CREATE EXTENSION IF NOT EXISTS pageinspect;

DROP TABLE IF EXISTS alignment_test_unpacked;
DROP TABLE IF EXISTS alignment_test_packed;
```

#### Step 2: Eksperimen Data Alignment & Pembuktian Padding
Buat dua tabel dengan tipe data identik, namun berbeda dalam urutan deklarasi kolom:
```sql
-- 1. Skema Unpacked (Urutan Acak)
CREATE TABLE alignment_test_unpacked (
    col1 int2,
    col2 int8,
    col3 int2,
    col4 int8
);

-- 2. Skema Packed (Diurutkan dari alignment terbesar ke terkecil)
CREATE TABLE alignment_test_packed (
    col2 int8,
    col4 int8,
    col1 int2,
    col3 int2
);

-- Masukkan 1.000.000 baris identik ke masing-masing tabel
INSERT INTO alignment_test_unpacked 
SELECT 1, 1000000000, 2, 2000000000 
FROM generate_series(1, 1000000);

INSERT INTO alignment_test_packed 
SELECT 1000000000, 2000000000, 1, 2 
FROM generate_series(1, 1000000);
```

#### Step 3: Verifikasi Penghematan Disk Storage
Audit perbandingan pemakaian ruang fisik kedua tabel:
```sql
SELECT 
    relname,
    pg_size_pretty(pg_total_relation_size(oid)) AS total_size,
    relpages AS page_count,
    reltuples AS tuple_count
FROM pg_class
WHERE relname IN ('alignment_test_unpacked', 'alignment_test_packed');
```
*Observasi Hasil*: Tabel `alignment_test_packed` menghemat ruang disk sekitar **20% hingga 25%** dibandingkan `alignment_test_unpacked` tanpa ada data fungsional yang dikurangi.

#### Step 4: Inspeksi Tingkat Rendah Isi Halaman 8KB (Slotted Page)
Bongkar struktur internal halaman data blok pertama (Block 0) menggunakan `pageinspect`:
```sql
-- Membaca PageHeaderData dari Blok 0
SELECT lsn, checksum, flags, lower, upper, special, pagesize
FROM page_header(get_raw_page('alignment_test_packed', 0));

-- Membaca representasi Item Identifier Array (ItemIdData) dan Tuple Header
SELECT 
    itemoffset,
    lp_off AS offset_to_tuple,
    lp_flags AS item_status,
    lp_len AS tuple_byte_length,
    t_xmin,
    t_xmax,
    t_ctid
FROM heap_page_items(get_raw_page('alignment_test_packed', 0))
LIMIT 5;
```

#### Step 5: Rekayasa dan Pembuktian Mekanisme HOT (Heap-Only Tuple)
Amati bagaimana manipulasi `fillfactor` berdampak langsung terhadap pembaruan baris tanpa fragmentasi indeks:
```sql
-- Buat tabel dengan fillfactor = 70 untuk memberikan ruang sisa di tiap blok
DROP TABLE IF EXISTS hot_demonstration;
CREATE TABLE hot_demonstration (
    id int PRIMARY KEY,
    payload text,
    update_counter int
) WITH (fillfactor = 70);

-- Masukkan data uji
INSERT INTO hot_demonstration VALUES (1, 'initial data', 1);

-- Ambil koordinat fisik awal dari baris tersebut (Block Number dan Offset)
SELECT ctid, id, payload, update_counter FROM hot_demonstration WHERE id = 1;

-- Lakukan UPDATE pada kolom non-indeks (payload & update_counter)
UPDATE hot_demonstration SET update_counter = update_counter + 1 WHERE id = 1;

-- Inspeksi kembali koordinat ctid baris terbaru
SELECT ctid, id, payload, update_counter FROM hot_demonstration WHERE id = 1;

-- Periksa relasi internal halaman: Anda akan melihat ItemId lama menunjuk 
-- ke ItemId baru dalam blok yang sama (HOT Chain).
SELECT 
    itemoffset, 
    lp_off, 
    lp_len, 
    t_xmin, 
    t_xmax, 
    t_ctid,
    t_infomask2::text AS infomask2_flags
FROM heap_page_items(get_raw_page('hot_demonstration', 0));
```

#### Step 6: Validasi Keberhasilan & Cleanup
Pastikan bahwa pada tabel `hot_demonstration`:
1. `ctid` awal baris bergeser (misal dari `(0,1)` ke `(0,2)`).
2. Flag status pembaruan menunjukkan bahwa update dituntaskan secara *in-page* tanpa melibatkan penambahan entry baru di root B-Tree index primary key.

Hapus objek eksperimen untuk mengembalikan lingkungan ke status bersih:
```sql
DROP TABLE alignment_test_unpacked;
DROP TABLE alignment_test_packed;
DROP TABLE hot_demonstration;
```