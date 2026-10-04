# Kurikulum Enterprise: Rekayasa Data Kinerja Tinggi dengan Python
## Kategori: 02-Programming-Languages / python-data-analysis
### Bab 02: Ingesti Data Kinerja Tinggi & Storage Formats
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis & Merekayasa Tata Letak Biner (Binary Layout):** Membedah struktur fisik Apache Parquet (File Metadata, Row Groups, Column Chunks, Data Pages, Dictionary Pages) dan memori Apache Arrow (Buffer, Validity Bitmap, Offsets).
- **Mengimplementasikan Zero-Copy Ingestion:** Memanfaatkan memory-mapped I/O (`mmap`) dan Apache Arrow C Data Interface untuk mentransfer data tabular tanpa overhead duplikasi memori dan siklus serialisasi/deserialisasi CPU.
- **Mengoptimalkan Mekanisme Encoding & Kompresi:** Memilih dan mengonfigurasi algoritma kompresi (Zstandard, Snappy) serta teknik encoding (Dictionary, Run-Length Encoding/RLE, Bit-Packing) secara deterministik berbasis entropi dan kardinalitas data.
- **Mendesain Arsitektur Ingesti Skala Terabyte:** Membangun pipeline pemrosesan berbasis streaming chunking (`RecordBatchReader`) yang tahan terhadap lonjakan memori (OOM-resilient) dan mendukung *predicate pushdown* serta *projection pushdown* di level *Page Index*.

---

### 2. Prerequisites
- **Pemahaman Tingkat Lanjut Python Internals:** Python Memory Model, Buffer Protocol (PEP 3118), CPython GIL, dan manajemen garbage collection (`gc`).
- **Prinsip Arsitektur Komputer & OS:** Paging, OS Page Cache, Virtual Memory, Disk I/O (Sequential vs Random Read), CPU Cache Hierarchy (L1/L2/L3), dan Vectorization (SIMD).
- **Penguasaan Toolchain:** Python 3.11+, PyArrow $\ge$ 14.0, Polars $\ge$ 0.20, DuckDB $\ge$ 0.10, dan Fastparquet.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Anatomi Fisik File Apache Parquet
Apache Parquet adalah format penyimpanan kolumnar berbasis biner yang dirancang menggunakan protokol Apache Thrift untuk metadata.

```
+-------------------------------------------------------------------------+
| PAR1 (4-byte Magic Number)                                              |
+-------------------------------------------------------------------------+
| Row Group 0                                                             |
|   +-------------------------------------------------------------------+ |
|   | Column Chunk 0 (misal: 'transaction_id')                          |
|   |   [Dictionary Page]                                               |
|   |   [Data Page 0 (Header + Repetition/Definition Levels + Values)]   |
|   |   [Data Page 1 ...]                                               |
|   +-------------------------------------------------------------------+ |
|   | Column Chunk 1 (misal: 'amount')                                  |
|   |   [Data Page 0 ...]                                               |
|   +-------------------------------------------------------------------+ |
+-------------------------------------------------------------------------+
| Row Group 1 ...                                                         |
+-------------------------------------------------------------------------+
| File Metadata (Thrift compact format)                                   |
|   - Version & Schema Definition                                         |
|   - Row Group Metadata (Offsets, Total Compressed/Uncompressed Size)    |
|   - Column Metadata (Encodings, Compressions, Statistics: Min/Max/Null) |
|   - Column Index & Offset Index (Parquet 2.0+ Page Index)               |
+-------------------------------------------------------------------------+
| 4-byte File Metadata Length                                             |
+-------------------------------------------------------------------------+
| PAR1 (4-byte Magic Number)                                              |
+-------------------------------------------------------------------------+
```

1. **Magic Number (`PAR1`):** Menandai awal dan akhir berkas untuk integritas validasi format.
2. **Footer Metadata Layout:** Metadata ditulis di akhir file guna memfasilitasi penulisan streaming file satu kali jalan (*single-pass streaming write*). Reader akan membaca 4 byte terakhir untuk menentukan ukuran footer, kemudian melompat mundur (*seek*) untuk membaca Thrift metadata tanpa memindai seluruh file.
3. **Data Page V1 vs V2:** 
   - *Data Page V1:* Definisi level, repetisi level, dan data dikompresi secara bersamaan.
   - *Data Page V2:* Memisahkan data level (RLE) dari nilai data terkompresi. Memungkinkan pembacaan metadata filter tanpa dekompresi *payload* nilai data utama.
4. **Page Index (Offset Index & Column Index):** Menyimpan nilai minimum dan maksimum per halaman data individual. Memungkinkan pembacaan parsial (*fine-grained page skipping*), melampaui limitasi granularitas Row Group.

#### 3.2 Apache Arrow In-Memory Columnar Layout
Apache Arrow menyediakan standar tata letak memori kanonikal terpadu untuk data tabular tanpa overhead serialisasi.

Struktur array tipe data `Primitive` (misal `Int32`) terdiri dari:
- **Validity Bitmap:** Buffer bit individual penanda apakah suatu entri bernilai `NULL` (bit 0) atau valid (bit 1). Menghilangkan penggunaan *sentinel values* (seperti `NaN` pada float IEEE 754).
- **Value Buffer:** Alokasi memori biner kontigu dengan offset tetap ($4 \times i$ byte untuk indeks $i$).

Struktur array tipe data `Variable-length Binary / String`:
- **Validity Bitmap:** Indikator null.
- **Offsets Buffer:** Array bilangan bulat `int32` berurutan berukuran $N + 1$ yang menandai indeks byte awal dan akhir dari entri data ke-$i$.
- **Values Buffer:** Buffer biner mentah tempat string dikonsolidasikan secara kontigu.

```
Contoh Array String: ["FOO", null, "BARAZ"]
Validity Bitmap: [1, 0, 1] (0b00000101)
Offsets Buffer:  [0, 3, 3, 8]
Data Buffer:     ['F', 'O', 'O', 'B', 'A', 'R', 'A', 'Z']
```

Operasi filtering dan slicing pada struktur ini merupakan manipulasi offset aritmatika pointer murni berbiaya $\mathcal{O}(1)$ tanpa alokasi memori baru (*zero-copy slicing*).

---

### 4. Why & What

| Fitur | CSV / JSON Textual | Apache Parquet | Apache Arrow (IPC / Feather v2) |
| :--- | :--- | :--- | :--- |
| **Bentuk Representasi** | Row-oriented Text | Columnar Disk Storage | Columnar In-Memory / IPC Format |
| **Kebutuhan Parsing CPU** | Sangat Tinggi (ASCII ke Biner) | Rendah (Hanya Dekompresi & RLE/Bit-Unpacking) | Nol (Langsung dipetakan ke CPU Register) |
| **Zero-Copy Serialization** | Mustahil | Tidak (Perlu transformasi format biner disk ke RAM) | Ya (Menggunakan memory-mapped buffer) |
| **Rasio Kompresi** | Rendah (Gzip generic) | Sangat Tinggi (Encoding adaptif + Zstandard/Snappy) | Rendah ke Moderat (Dukungan LZ4/ZSTD opsional) |
| **Throughput Query** | Terbatas oleh parsing throughput ($\sim 50-200$ MB/s) | Ratusan MB/s s.d. GB/s via SIMD & Pushdown | Puluhan GB/s (Memory bus bandwidth bound) |
| **Primary Use-Case** | Data Interchange Eksternal | Cold/Warm Storage Analitik Jangka Panjang | Inter-Process Communication, Compute Engine Buffer |

---

### 5. How (Workflow Detail)

Arsitektur siklus hidup data dari storage hingga register CPU dieksekusi melalui pipeline berikut:

```
[Parquet File di Disk / NVMe]
              │
              ▼  (1. Membaca 4-byte Footer Length & Thrift Metadata)
[Page Index & Metadata Evaluator]
              │  (2. Predicate Pushdown: Skip Row Groups & Data Pages via Min/Max Stats)
              ▼  
[OS Page Cache / Memory Mapped I/O]
              │  (3. DMA: Direct Memory Access dari storage ke memory pages)
              ▼  
[Decompression Engine (Zstandard/Snappy SIMD)]
              │  (4. Dekompresi Stream ke Biner Column Chunk)
              ▼  
[Decoding Subsystem (RLE / Dictionary / Bit-unpacking)]
              │  (5. Transformasi ke Layout In-Memory Arrow)
              ▼  
[Arrow RecordBatch Stream (In-Memory Columnar)]
              │  (6. Vectorized Execution via Polars / DuckDB / LLVM Engine)
              ▼  
[CPU Register Execution (AVX-512 / ARM Neon SIMD Instructions)]
```

1. **OS Read Initiation:** Aplikasi membuka *file descriptor* Parquet. Pembacaan dilakukan melalui antarmuka `mmap` untuk menghindari duplikasi buffer antara *Kernel Space* dan *User Space*.
2. **Metadata Introspection:** Header dan footer dipetakan. Kondisi query (`WHERE timestamp >= '2024-01-01'`) dievaluasi terhadap statistik `ColumnChunk` dan `Column Index`. Chunk yang berada di luar rentang dieleminasi seketika.
3. **Chunk Streaming:** Data page yang lolos filter di-stream secara bertahap menggunakan alokator memori berbasis arena (`Arrow MemoryPool`) untuk mencegah fragmentasi heap.
4. **Vectorized Decompression & Decoding:** Blok biner dikonversi langsung ke array Apache Arrow melalui instruksi vektor SIMD hardware.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Konvensional vs. Sistem Arsip Terindeks Digital

- **CSV (Format Baris Tekstual):** Bayangkan sebuah novel. Jika Anda ingin mencari total usia seluruh warga kota, Anda harus membaca kata demi kata dari halaman 1 sampai akhir, membuang informasi nama, alamat, dan pekerjaan, lalu mengonversi kata "tiga puluh lima" menjadi angka 35 di kepala Anda.
- **Parquet (Format Kolumnar Disk Terkompresi):** Buku dibongkar menjadi volume per kategori data. Seluruh "Usia" dikumpulkan dalam satu volume terikat rapi, dikompresi dengan kode ringkas (misal: "angka 30 berulang 50 kali"), dilengkapi daftar isi presisi di sampul belakang yang menyebutkan halaman mana saja yang memuat usia di atas 60. Anda hanya membuka halaman yang relevan.
- **Arrow (Format Memori Terstruktur):** Halaman buku usia tersebut diletakkan langsung di atas meja kerja, disusun secara biner presisi mengikuti lebar mata pembaca. Mesin fotokopi otomatis dapat langsung mengecek 16 data usia sekaligus dalam 1 kali kedipan mata (SIMD).

#### Diagram Pemetaan Zero-Copy Arrow IPC

```
FILE BINER ARROW IPC (DI STORAGE ATAU SHARED MEMORY)
+-------------------------------------------------------------------+
| MAGIC | Schema Metadata | RecordBatch Metadata | Buffer Data      |
+-------------------------------------------------------------------+
                             │                      │
                             │ (mmap mapping)       │ (Pointer Casting)
                             ▼                      ▼
VIRTUAL MEMORY PROSES APPLICATION USER-SPACE
+-------------------------------------------------------------------+
| pyarrow.RecordBatch                                               |
|  ├── schema (Reference metadata langsung dari header file)         |
|  └── columns: ArrayData                                           |
|       ├── validity_bitmap: *uint8_t  ───► 0x7FFF0010 (Direct addr)|
|       ├── value_offsets:   *int32_t  ───► 0x7FFF0020 (Direct addr)|
|       └── values:          *void     ───► 0x7FFF0040 (Direct addr)|
+-------------------------------------------------------------------+
*Tidak ada alokasi buffer baru via malloc(), tidak ada copy payload biner*
```

---

### 7. Practical Implementation (Standar Industri)

#### 7.1 Generator & Writer: Pipeline Streaming Parquet Kinerja Tinggi
Script ini mengimplementasikan streaming writer Apache Parquet dengan optimasi kamus (Dictionary Encoding), kompresi adaptif Zstandard, dan pembuatan Page Index.

```python
"""
Module: parquet_production_writer.py
Arsitektur penulisan Apache Parquet skala enterprise dengan kontrol memory buffer.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Generator
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ParquetWriter")

# Definisi Skema Biner Eksplisit
SCHEMA = pa.schema([
    pa.field("transaction_id", pa.string(), nullable=False),
    pa.field("user_id", pa.int64(), nullable=False),
    pa.field("merchant_category", pa.dictionary(pa.int8(), pa.string()), nullable=False),
    pa.field("amount", pa.float64(), nullable=False),
    pa.field("timestamp", pa.timestamp("us", tz="UTC"), nullable=False),
    pa.field("is_fraud", pa.bool_(), nullable=False),
])


def generate_synthetic_data(batch_size: int) -> pa.RecordBatch:
    """Membuat RecordBatch Arrow secara sintetis dengan tipe memori deterministik."""
    categories = ["RETAIL", "TRAVEL", "GAMING", "FOOD", "UTILITIES"]
    
    # Primitive array buffer generation via NumPy
    tx_ids = pa.array([f"tx_{i}" for i in np.random.randint(10000000, 99999999, size=batch_size)])
    user_ids = pa.array(np.random.randint(1, 500000, size=batch_size, dtype=np.int64))
    
    # Dictionary Encoding: kategori direpresentasikan via index int8
    raw_cats = np.random.choice(categories, size=batch_size)
    merchant_cats = pa.DictionaryArray.from_arrays(
        indices=pa.array(np.searchsorted(categories, raw_cats).astype(np.int8)),
        dictionary=pa.array(categories)
    )
    
    amounts = pa.array(np.random.exponential(scale=50.0, size=batch_size), type=pa.float64())
    base_time = np.datetime64("2024-01-01T00:00:00", "us")
    random_offsets = np.random.randint(0, 86400000000, size=batch_size, dtype="timedelta64[us]")
    timestamps = pa.array(base_time + random_offsets, type=pa.timestamp("us", tz="UTC"))
    is_fraud = pa.array(np.random.binomial(1, 0.005, size=batch_size).astype(bool))

    return pa.RecordBatch.from_arrays(
        [tx_ids, user_ids, merchant_cats, amounts, timestamps, is_fraud],
        schema=SCHEMA
    )


def stream_batches(total_rows: int, batch_size: int) -> Generator[pa.RecordBatch, None, None]:
    """Generator streaming data untuk konsumsi memori konstan O(1)."""
    emitted = 0
    while emitted < total_rows:
        current_batch_size = min(batch_size, total_rows - emitted)
        yield generate_synthetic_data(current_batch_size)
        emitted += current_batch_size


def write_parquet_dataset(output_path: Path, total_rows: int, row_group_size: int) -> None:
    """Menulis berkas Parquet dengan konfigurasi produksi lanjutan."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    batch_size = 65_536  # Standar efisiensi Vector L2/L3 cache

    writer_properties = {
        "where": str(output_path),
        "schema": SCHEMA,
        "compression": "ZSTD",
        "compression_level": 7,
        "use_dictionary": ["merchant_category"],
        "write_statistics": True,
        "data_page_size": 1024 * 1024,  # 1 MB page size untuk optimalisasi scan granular
        "version": "2.6",                # Mengaktifkan Parquet Data Page V2 & Page Index
    }

    logger.info(f"Menginisialisasi penulisan ke {output_path} | Total rows: {total_rows}")
    with pq.ParquetWriter(**writer_properties) as writer:
        current_group_batches = []
        current_group_rows = 0

        for batch in stream_batches(total_rows, batch_size):
            current_group_batches.append(batch)
            current_group_rows += batch.num_rows

            if current_group_rows >= row_group_size:
                table = pa.Table.from_batches(current_group_batches)
                writer.write_table(table, row_group_size=row_group_size)
                logger.info(f"Flushed Row Group sebesar {current_group_rows} baris.")
                current_group_batches.clear()
                current_group_rows = 0

        # Flush sisa batch jika ada
        if current_group_batches:
            table = pa.Table.from_batches(current_group_batches)
            writer.write_table(table, row_group_size=row_group_size)
            logger.info(f"Flushed Final Row Group sebesar {current_group_rows} baris.")

    logger.info(f"File berhasil ditulis: {output_path} ({output_path.stat().st_size / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    out_file = Path("./data/processed/transactions.parquet")
    write_parquet_dataset(output_path=out_file, total_rows=1_000_000, row_group_size=250_000)
```

#### 7.2 Consumer Engine: Zero-Copy Scan, Predicate & Projection Pushdown
Consumer memanfaatkan antarmuka Polars dan DuckDB untuk membedah data menggunakan eksekusi tervektorisasi murni.

```python
"""
Module: parquet_production_consumer.py
Mengeksekusi pembacaan data kinerja tinggi berbasis pushdown predicates.
"""

from __future__ import annotations

import logging
from pathlib import Path
import duckdb
import polars as pl
import pyarrow.dataset as ds

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ParquetReader")


def inspect_parquet_metadata(file_path: Path) -> None:
    """Inspeksi struktural internal Row Groups dan Page Indexes."""
    metadata = ds.parquet_dataset(file_path).schema
    logger.info(f"Schema Inferred via Dataset Metadata:\n{metadata}")

    parquet_file = pq.ParquetFile(file_path)
    file_meta = parquet_file.metadata
    logger.info(f"Jumlah Row Groups: {file_meta.num_row_groups}")
    logger.info(f"Format Versi: {file_meta.format_version}")

    for i in range(file_meta.num_row_groups):
        rg_meta = file_meta.row_group(i)
        logger.info(
            f"Row Group {i}: Baris={rg_meta.num_rows}, "
            f"Ukuran Terkompresi={rg_meta.total_byte_size} bytes"
        )
        # Ambil statistik min/max dari kolom user_id
        col_meta = rg_meta.column(1)
        logger.info(
            f"  Col 1 (user_id) Stats -> Min: {col_meta.statistics.min}, "
            f"Max: {col_meta.statistics.max}, HasDictionary: {col_meta.has_dictionary_page}"
        )


def query_via_polars_lazy(file_path: Path) -> pl.DataFrame:
    """Mengeksekusi scan teroptimasi dengan Projection & Predicate Pushdown."""
    logger.info("Mengeksekusi Lazy Scan via Polars Engine...")
    
    # Polars scan_parquet TIDAK memuat seluruh data ke RAM (Hanya membaca metadata)
    lazy_query = (
        pl.scan_parquet(file_path)
        .filter(pl.col("amount") > 150.0)
        .filter(pl.col("merchant_category") == "TRAVEL")
        .select(["transaction_id", "user_id", "amount", "timestamp"])
    )

    # Tampilkan Execution Plan untuk verifikasi Pushdown
    logger.info(f"Optimized Engine Plan:\n{lazy_query.explain()}")
    
    # Eksekusi streaming sink
    result = lazy_query.collect(streaming=True)
    return result


def query_via_duckdb_zero_copy(file_path: Path) -> None:
    """Eksekusi query agregasi in-memory DuckDB membaca file Parquet langsung."""
    logger.info("Mengeksekusi Vectorized Aggregation via DuckDB...")
    con = duckdb.connect(database=":memory:")
    
    # DuckDB membaca Parquet secara multi-thread dengan fine-grained chunk reading
    query = f"""
        SELECT 
            merchant_category,
            COUNT(*) as total_tx,
            AVG(amount) as mean_amount,
            MAX(amount) as peak_amount
        FROM read_parquet('{file_path}')
        WHERE is_fraud = true
        GROUP BY merchant_category
        ORDER BY total_tx DESC;
    """
    df = con.execute(query).arrow()
    logger.info(f"Hasil Agregasi DuckDB (Arrow Table Representation):\n{df.to_pandas()}")


if __name__ == "__main__":
    data_path = Path("./data/processed/transactions.parquet")
    if data_path.exists():
        inspect_parquet_metadata(data_path)
        polars_res = query_via_polars_lazy(data_path)
        logger.info(f"Polars hasil scan: {polars_res.shape[0]} baris dimuat.")
        query_via_duckdb_zero_copy(data_path)
    else:
        logger.error("Dataset belum dibuat. Jalankan parquet_production_writer.py terlebih dahulu.")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sistem analitik transaksi perbankan global memproses **1.2 Miliar baris log mutasi transaksi per hari** ($\approx 250\text{ GB}$ JSON mentah terkompresi Gstandard per hari). Pipeline awal menggunakan parser JSON line-by-line berbasis Pandas di instans AWS `r5.8xlarge` (32 vCPU, 256 GB RAM).

**Pain Points:**
1. Pipeline runtime: **6.8 jam/hari**.
2. Sering terjadi Out-Of-Memory (OOM) crash ketika ukuran berkas harian melonjak di atas $300\text{ GB}$.
3. Biaya cloud komputasi bulanan membengkak secara signifikan.
4. Downstream Data Scientist mengeluhkan waktu tunggu query analitik (pembacaan subset kolom butuh waktu lebih dari 45 menit).

#### Solusi Arsitektur Baru
Merombak pipeline ingest menjadi decoupled streaming architecture:

```
[S3 Bucket: Raw JSON Streams]
              │
              ▼  (Async I/O Multi-Part Fetching via aiohttp & PyArrow FileSystem)
[Ingestion Workers: c6i.4xlarge (16 vCPU, 32 GB RAM)]
              │
              ├── Mengurai chunk JSON menggunakan SimdJSON
              ├── Konversi ke RecordBatch Arrow In-Memory
              └── Mengurutkan data berdasarkan `[transaction_date, user_id]` (Data Clustering)
              │
              ▼  (Parquet Writer: Row Group 1,000,000 baris, ZSTD Level 6, Bloom Filters)
[Target Analytics Lake: Optimized Partitioned Parquet]
              │
              ├── Partisi: year=YYYY/month=MM/
              └── Page Index aktif untuk user_id dan amount
```

#### Hasil Metrik Kinerja (Before vs After)

| Metrik | Arsitektur Lama (Pandas + JSON) | Arsitektur Baru (Arrow + Parquet + SIMD) | Delta Peningkatan |
| :--- | :--- | :--- | :--- |
| **Waktu Ingesti Harian** | 6.8 Jam | 38 Menit | **$10.7\times$ Lebih Cepat** |
| **Konsumsi Memori RAM Puncak** | 210 GB | 14 GB (Bounded Streaming) | **$93.3\%$ Reduksi Memori** |
| **Ukuran Data di Storage** | 250 GB/hari (JSON.gz) | 38 GB/hari (Parquet ZSTD-6) | **$84.8\%$ Efisiensi Biaya Storage** |
| **Latency Query Analitik P95** | 2,750 detik ($\sim 45$ mnt) | 4.2 detik | **$654\times$ Peningkatan Akselerasi** |
| **Biaya Komputasi AWS/Bulan** | \$4,850 | \$980 | **$79.8\%$ Penghematan Biaya** |

---

### 9. Trade-offs: Analisis Matriks Rekayasa

Setiap keputusan tata letak data melibatkan kompromi fundamental sistem:

```
                  FLEKSIBILITAS KOMPRESI
                            ▲
                            │      ● Parquet Zstandard (Level 12+)
                            │        (Rasio tinggi, CPU bound)
                            │
                            │             ● Parquet Zstandard (Level 3-5)
                            │               (Sweet Spot Produksi)
                            │
                            │   ● Parquet Snappy
                            │
       ● Arrow IPC (Uncompressed)
         (Memory-bound, Latency-critical)
  ───┼─────────────────────────────────────────────► THROUGHPUT I/O &
  0  │                                               DESERIALISASI CEPAT
```

#### 1. Ukuran Row Group Parquet (Row Group Sizing)
- **Kecil ($10.000 - 50.000$ baris):**
  - *Kelebihan:* Granularitas filtering tinggi via metadata skipping; jejak memori (*footprint*) saat *flushing* sangat rendah.
  - *Kekurangan:* Metadata overhead membengkak; rasio kompresi dictionary dan algoritma Zstandard menurun drastis karena ukuran blok referensi terlalu sempit.
- **Besar ($1.000.000 - 2.000.000$ baris):**
  - *Kelebihan:* Rasio kompresi optimal; pembacaan sequential I/O masif sangat efisien; vektorisasi SIMD berjalan pada utilisasi puncak.
  - *Kekurangan:* Membutuhkan buffer RAM besar saat menulis file; filter skipping kurang selektif jika distribusi data tidak berurutan (*unsorted*).

#### 2. Snappy vs. Zstandard (ZSTD)
- **Snappy:** Dirancang untuk kecepatan dekompresi ekstrim ($>2\text{ GB/s}$ per core) dengan rasio kompresi moderat. Cocok untuk *hot-tier data* yang diakses berulang dalam analitik interaktif langsung.
- **Zstandard:** Fleksibel dengan skala level 1-22. Level 3-7 memberikan rasio kompresi 30-50% lebih superior dibanding Snappy dengan kecepatan dekompresi yang hampir menyamai Snappy. Sangat ideal untuk *warm/cold tier warehousing*.

#### 3. Arrow IPC Stream vs. Arrow IPC File (Feather v2)
- **Stream Format:** Berorientasi transmisi jaringan tanpa *random access*. Cocok untuk inter-service streaming socket (Arrow Flight).
- **File Format:** Menyertakan footer metadata dan offset array yang mendukung *zero-copy memory mapping* (`mmap`). Reader dapat membaca kolom acak secara instan tanpa mengonsumsi seluruh isi berkas.

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: "Small File Problem" & Memory Fragmentation
* **Gejala:** Jutaan berkas Parquet berukuran $\le 5\text{ MB}$ memenuhi storage. Query Spark/Polars/DuckDB mengalami degradasi drastis (*listing metadata bottleneck*).
* **Akar Masalah:** Pipeline menulis data langsung per partisi streaming micro-batch tanpa konsolidasi (*coalescing*).
* **Solusi Perbaikan:** Implementasikan buffer writer lokal yang menahan mutasi data hingga mencapai batas threshold ($\ge 128\text{ MB} - 512\text{ MB}$) sebelum me-release commit berkas baru ke S3/GCS.

#### Kasus 2: Dictionary Page Overflow
* **Gejala:** Ukuran file Parquet melonjak tajam dan kecepatan penulisan anjlok drastis.
* **Akar Masalah:** Menerapkan *Dictionary Encoding* pada kolom dengan kardinalitas mendekati rasio unik 1:1 (misal `uuid` atau `timestamp_nanosecond`). Mesin encoding kehabisan kapasitas kamus, memicu *fallback* ke *Plain Encoding* di tengah jalan dengan overhead kamus yang terbuang sia-sia.
* **Solusi Perbaikan:**
  ```python
  # MATIKAN dictionary encoding eksplisit pada kolom kardinalitas tinggi
  writer_properties = {
      "use_dictionary": ["status", "country_code"], # Tepat: Kardinalitas rendah
      # Kolom UUID otomatis diabaikan, atau set eksplisit:
      "column_encoding": {"transaction_id": "PLAIN"}
  }
  ```

#### Kasus 3: OOM Tersembunyi pada Reader PyArrow/Pandas
* **Gejala:** Container Docker mengalami SIGKILL (Exit Code 137) saat memuat file Parquet berukuran $8\text{ GB}$ pada mesin dengan RAM $16\text{ GB}$.
* **Akar Masalah:** Penggunaan fungsi `read_table().to_pandas()` menduplikasi alokasi heap: satu untuk buffer Apache Arrow biner, satu lagi untuk *block manager* NumPy/Pandas.
* **Solusi Perbaikan:**
  ```python
  # Gunakan zero-copy engine atau konversi berbasis PyArrow backend di Pandas 2.0+
  import pandas as pd
  # Menggunakan direct engine tanpa duplikasi internal block manager numpy
  df = pd.read_parquet("large_file.parquet", engine="pyarrow", dtype_backend="pyarrow")
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Data Types Explicitly Enforced:** Jangan pernah bergantung pada *schema inference*. Definisikan `pa.schema` secara kaku untuk menjaga konsistensi biner.
- [ ] **Row Group Sizing Bound:** Konfigurasi ukuran Row Group antara $500.000$ hingga $1.500.000$ baris, atau target ukuran uncompressed $128\text{ MB} - 512\text{ MB}$.
- [ ] **Compression Standards:** Terapkan `ZSTD` level 5 s.d. 7 sebagai standar kompresi de-facto produksi analitik.
- [ ] **Data Sorting on Write:** Lakukan penyortiran (*pre-sorting*) data sebelum penulisan berdasarkan kolom yang sering digunakan dalam klausa filter (misalnya: `sort_by(["organization_id", "created_at"])`). Hal ini memaksimalkan efisiensi *Page Index* dan rasio dekompresi RLE.
- [ ] **Column Ordering:** Letakkan kolom dengan tipe data primitif berukuran tetap (*fixed-width*) di depan kolom bertipe dinamis (*variable-width string/json*) guna menjaga efisiensi alokasi memori lokalitas prosesor.
- [ ] **Memory-Mapped Reads:** Selalu buka berkas lokal menggunakan `memory_map=True` pada `pyarrow.parquet.ParquetFile` untuk memindahkan beban caching ke kernel OS Page Cache.

---

### 12. Hands-on Practice

Buat struktur direktori untuk praktikum:
```bash
mkdir -p hands-on/m02/data
cd hands-on/m02
```

#### Langkah 1: Eksperimen Benchmark Format Data
Simpan skrip berikut sebagai `hands-on/m02/benchmark_storage.py`. Skrip ini menguji efisiensi I/O, rasio kompresi, dan waktu deserialisasi antara CSV, Parquet Snappy, Parquet Zstandard, dan Feather v2 (Arrow IPC).

```python
"""
hands-on/m02/benchmark_storage.py
Benchmark perbandingan komprehensif format storage data modern.
"""

from __future__ import annotations

import time
from pathlib import Path
import numpy as np
import polars as pl
import pyarrow as pa
import pyarrow.feather as feather
import pyarrow.parquet as pq

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)
NUM_ROWS = 2_000_000


def build_dataset() -> pa.Table:
    print(f"[1/5] Membangun dataset in-memory Arrow ({NUM_ROWS:,} baris)...")
    np.random.seed(42)
    categories = np.array(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"])
    
    schema = pa.schema([
        ("event_id", pa.int64()),
        ("severity", pa.string()),
        ("metric_value", pa.float64()),
        ("is_active", pa.bool_()),
    ])
    
    table = pa.Table.from_arrays([
        pa.array(np.arange(NUM_ROWS, dtype=np.int64)),
        pa.array(np.random.choice(categories, size=NUM_ROWS)),
        pa.array(np.random.normal(loc=100.0, scale=15.0, size=NUM_ROWS)),
        pa.array(np.random.binomial(1, 0.7, size=NUM_ROWS).astype(bool)),
    ], schema=schema)
    return table


def benchmark_io(table: pa.Table) -> None:
    csv_path = DATA_DIR / "dataset.csv"
    pq_snappy_path = DATA_DIR / "dataset_snappy.parquet"
    pq_zstd_path = DATA_DIR / "dataset_zstd.parquet"
    feather_path = DATA_DIR / "dataset.feather"

    results = []

    # 1. CSV Benchmark
    t0 = time.perf_counter()
    pl_table = pl.from_arrow(table)
    pl_table.write_csv(csv_path)
    csv_write_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    _ = pl.read_csv(csv_path)
    csv_read_time = time.perf_counter() - t0
    results.append(("CSV (Textual)", csv_path.stat().st_size, csv_write_time, csv_read_time))

    # 2. Parquet Snappy Benchmark
    t0 = time.perf_counter()
    pq.write_table(table, pq_snappy_path, compression="SNAPPY", row_group_size=500_000)
    pq_snappy_write_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    _ = pq.read_table(pq_snappy_path, memory_map=True)
    pq_snappy_read_time = time.perf_counter() - t0
    results.append(("Parquet (Snappy)", pq_snappy_path.stat().st_size, pq_snappy_write_time, pq_snappy_read_time))

    # 3. Parquet ZSTD Benchmark
    t0 = time.perf_counter()
    pq.write_table(table, pq_zstd_path, compression="ZSTD", compression_level=7, row_group_size=500_000)
    pq_zstd_write_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    _ = pq.read_table(pq_zstd_path, memory_map=True)
    pq_zstd_read_time = time.perf_counter() - t0
    results.append(("Parquet (ZSTD Level 7)", pq_zstd_path.stat().st_size, pq_zstd_write_time, pq_zstd_read_time))

    # 4. Feather (Arrow IPC File) Benchmark
    t0 = time.perf_counter()
    feather.write_feather(table, feather_path, compression="uncompressed")
    feather_write_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    _ = feather.read_table(feather_path, memory_map=True)
    feather_read_time = time.perf_counter() - t0
    results.append(("Feather v2 (Zero-Copy MMap)", feather_path.stat().st_size, feather_write_time, feather_read_time))

    print("\n" + "=" * 80)
    print(f"{'Format':<25} | {'File Size (MB)':<15} | {'Write Time (s)':<15} | {'Read Time (s)':<15}")
    print("=" * 80)
    for fmt, size, w_time, r_time in results:
        print(f"{fmt:<25} | {size / (1024*1024):<15.2f} | {w_time:<15.4f} | {r_time:<15.4f}")
    print("=" * 80)


if __name__ == "__main__":
    raw_table = build_dataset()
    benchmark_io(raw_table)
```

Jalankan script benchmark:
```bash
python hands-on/m02/benchmark_storage.py
```

---

### 13. Exercises

#### Level 1: Easy
Tulis skrip Python menggunakan PyArrow untuk membaca hanya kolom `metric_value` dan `severity` dari file `dataset_zstd.parquet` yang dihasilkan pada hands-on. Pastikan Anda tidak memuat seluruh kolom ke dalam memori.
- **Kunci Evaluasi:** Memanfaatkan argumen `columns` pada `pq.read_table` atau `ds.dataset` scanning.

#### Level 2: Medium
Tulis fungsi Python `filter_high_metrics(file_path: Path, threshold: float) -> pa.Table` menggunakan pustaka `pyarrow.dataset` yang:
1. Membaca dataset Parquet dengan mengaplikasikan ekspresi filter pushdown: `pl.col("metric_value") > threshold`.
2. Menghindari pembacaan Row Group yang tidak memenuhi syarat secara komputasi.
3. Mencetak jumlah baris yang berhasil dieliminasi di tingkat I/O filter.

#### Level 3: Hard
Bangun sebuah custom streaming pipeline dengan ketentuan:
1. Menerima generator yang menghasilkan stream batched record Arrow berkardinalitas tinggi ($10\text{ Juta baris}$).
2. Mengurutkan partisi data secara deterministik di memori menggunakan buffer terikat (maksimal alokasi RAM $512\text{ MB}$).
3. Menulis file Parquet terpartisi secara paralel dengan mekanisme multi-threading, di mana data dikelompokkan ke dalam direktori berdasarkan kolom `severity` (Hive-style partitioning: `/severity=CRITICAL/data.parquet`), lengkap dengan *Bloom Filter* aktif pada kolom `event_id`.

---

### 14. Real-World Architectural Challenge

#### Deskripsi Tantangan
Sebuah platform sistem transaksi perbankan nasional mendeteksi kendala latensi kritis pada proses rekonsiliasi harian. File transaksi historis tersimpan dalam format Parquet di Object Storage (S3 kompatibel) dengan volume sebesar $8\text{ TB}$ per hari, terpecah ke dalam ribuan berkas. 

Setiap transaksi memiliki skema berikut:
```protobuf
message Transaction {
  string transaction_id = 1;      // UUIDv4 (High-cardinality)
  int64 account_id = 2;            // Integer ID
  int64 timestamp_epoch_ms = 3;    // Milliseconds
  double amount = 4;               // Transaction value
  string currency = 5;             // ISO Code: IDR, USD, SGD (Low-cardinality)
  string terminal_ip = 6;          // IP Address v4
  string payload_metadata = 7;     // Semi-structured JSON string
}
```

Klausa query yang paling mendominasi (90% beban analitik) adalah:
```sql
SELECT currency, SUM(amount), COUNT(transaction_id)
FROM transactions
WHERE timestamp_epoch_ms BETWEEN 1704067200000 AND 1704153600000
  AND account_id = 98234120
GROUP BY currency;
```

#### Persyaratan Rekayasa:
1. **Rancang Blueprint Encoding & Storage Physical Layout:** Tentukan konfigurasi skema Parquet secara mendalam: encoding per kolom (PLAIN, RLE, DICTIONARY), algoritma kompresi per kolom, ukuran Row Group, dan strategi data ordering (*sorting key*).
2. **Eliminasi Full-Scan Overhead:** Bagaimana Anda memanfaatkan *Bloom Filters*, *Column Index (Page Index)*, dan *Data Clustering* untuk memotong waktu scan query di atas sehingga engine hanya membaca kurang dari 0.1% total data tanpa membuat basis data relational sekunder?
3. **Analisis Mitigasi Skema:** `payload_metadata` merupakan string JSON dengan ukuran bervariasi ($100\text{ byte} - 5\text{ KB}$). Bagaimana memitigasi dampak kolom ini agar tidak merusak efisiensi I/O scan ketika query analitik sama sekali tidak mengakses kolom `payload_metadata`?

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Di manakah letak metadata skema dan statistik disimpan di dalam file Apache Parquet, dan mengapa diletakkan di sana?**
   * *Jawaban:* Di bagian akhir file (Footer). Hal ini memungkinkan berkas ditulis secara sekuensial satu kali jalan (*single-pass streaming write*) tanpa perlu mengetahui ukuran akhir file di awal. Reader hanya membaca 4 byte terakhir untuk mencari lokasi awal metadata footer.
2. **Apa perbedaan mendasar antara representasi memori Apache Arrow dan Pandas DataFrame standar berbasis NumPy v1?**
   * *Jawaban:* Apache Arrow menggunakan representasi biner kolumnar terpadu yang memisahkan data kontigu dari validity bitmap (mendukung nullability native tanpa manipulasi float `NaN`) serta mendukung tipe bersarang/string tanpa alokasi objek pointer Python (`PyObject*`). NumPy v1 mengalokasikan array pointer independen untuk tipe objek/string yang menyebabkan fragmentasi memori.
3. **Apa kegunaan Magic Number `PAR1` pada berkas Apache Parquet?**
   * *Jawaban:* Berfungsi sebagai identifikasi format biner berkas di tingkat filesystem (4 byte pertama dan 4 byte terakhir berkas) guna memverifikasi integritas berkas bahwa format tersebut benar-benar Parquet yang valid dan proses penulisan telah selesai secara sempurna.
4. **Mengapa kompresi Zstandard (ZSTD) sering dipilih menggantikan GZIP dalam sistem analitik data modern?**
   * *Jawaban:* Karena Zstandard menawarkan kecepatan dekompresi yang jauh lebih tinggi (mendekati batas bandwidth hardware I/O via akselerasi SIMD) dengan rasio kompresi yang setara atau lebih baik dibanding Gstandard, serta memiliki rentang fleksibilitas level tuning kompresi yang luas (level 1-22).
5. **Apa yang dimaksud dengan Zero-Copy Deserialization?**
   * *Jawaban:* Proses mengakses data biner dari media penyimpanan atau shared memory langsung ke register program dengan memetakan pointer memori secara fisik tanpa menyalin data tersebut dari buffer satu ke alokasi buffer lainnya di RAM.

#### Intermediate (5 Soal)
6. **Jelaskan mekanisme kerja Predicate Pushdown di tingkat Parquet Page Index!**
   * *Jawaban:* Page Index menyimpan metadata statistik nilai minimum dan maksimum untuk setiap Data Page individual di dalam Column Chunk. Jika query memiliki filter (misal: `val > 100`), pembaca dapat memeriksa statistik tersebut dan melompati pembacaan/dekompresi halaman data tertentu di dalam Row Group jika nilai maksimumnya $\le 100$.
7. **Kapan teknik Dictionary Encoding pada Apache Parquet mengalami degradasi performa (*worst-case scenario*)?**
   * *Jawaban:* Ketika diterapkan pada kolom dengan kardinalitas yang sangat tinggi mendekati nilai unik total baris (misal UUID atau hash unik). Hal ini menyebabkan ukuran kamus melampaui limit ukuran dictionary page, memaksa format beralih ke representasi PLAIN encoding di tengah penulisan, meninggalkan beban overhead kamus yang mubazir.
8. **Apa perbedaan arsitektural antara Apache Arrow IPC Stream Format dan Apache Arrow IPC File Format?**
   * *Jawaban:* IPC Stream Format tidak memerlukan random access; data ditransmisikan secara kontinu chunk-per-chunk dan dibaca secara forward-only hingga aliran ditutup. IPC File Format menyertakan metadata footer dengan offset table array yang memungkinkan pembaca melakukan random seek dan memory mapping (`mmap`) langsung ke RecordBatch tertentu.
9. **Mengapa menyortir (*sorting*) dataset sebelum menuliskannya ke berkas Parquet dapat mengurangi ukuran berkas secara signifikan?**
   * *Jawaban:* Karena data yang tersortir mengelompokkan nilai-nilai yang identik atau berdekatan secara fisik. Hal ini memaksimalkan efisiensi algoritma kompresi Run-Length Encoding (RLE) dan Bit-Packing, sehingga menghasilkan urutan bit redundan yang sangat mudah dimampatkan oleh kompresor seperti ZSTD/Snappy.
10. **Bagaimana parameter `data_page_size` memengaruhi performa pembacaan data Parquet?**
    * *Jawaban:* Nilai `data_page_size` yang lebih kecil meningkatkan efektivitas fine-grained page skipping via Page Index (mengurangi konsumsi transfer I/O untuk query yang sangat selektif), namun memperbesar ukuran metadata footer file. Ukuran yang terlalu besar mengurangi overhead metadata, namun menurunkan efisiensi filtering karena lebih banyak data yang tidak relevan ikut terdekompresi.

#### Production Scenarios (3 Soal Kasus Nyata)
11. **Skenario Kasus 1:** Pipeline pemrosesan log jaringan menghasilkan file Parquet harian dengan 10.000 Row Groups, di mana setiap Row Group hanya berisi 500 baris. Saat dieksekusi menggunakan DuckDB atau Trino, query sederhana memerlukan waktu 10 menit meskipun total baris hanya 5 juta data. Jelaskan penyebab utama kegagalan kinerja ini dan bagaimana solusinya.
    * *Jawaban:* Terjadi masalah *Row Group Fragmentation* (ukuran row group terlalu kecil). Engine analitik menghabiskan sebagian besar siklus CPU untuk mem-parsing puluhan ribu struktur metadata Row Group dari footer ketimbang membaca data biner aktual. Selain itu, rasio kompresi sangat buruk karena kamus tidak dapat mengumpulkan data berulang dalam jumlah yang memadai. Solusi: Lakukan konsolidasi ulang (*rewriting/compaction*) dengan ukuran Row Group target antara 500.000 hingga 1.000.000 baris.
12. **Skenario Kasus 2:** Server API berbasis FastAPI melayani download analitik dalam format CSV. Ketika melayani 20 request konkuren untuk dataset 500 MB, server mengalami lonjakan CPU hingga 100% dan konsumsi RAM mencapai batas maksimum, sehingga container di-kill oleh Kubernetes OOM-Killer. Usulkan transformasi arsitektur data format dan streaming protokol untuk mengatasi masalah ini secara permanen tanpa menambah node server.
    * *Jawaban:* Ganti format transfer dari CSV ke Apache Arrow IPC Stream melalui protokol streaming murni (atau Apache Arrow Flight berbasis gRPC). Gunakan Polars/DuckDB untuk men-stream data langsung dari storage Parquet sebagai `RecordBatchReader`. Tuliskan stream biner tersebut langsung ke socket network HTTP response via chunked transfer encoding. Hal ini mengeliminasi 100% CPU overhead parsing ASCII/String Formatting dan menjaga konsumsi memori API server pada batas konstan $\mathcal{O}(1)$ terlepas dari ukuran dataset.
13. **Skenario Kasus 3:** Pipeline ingesti data ingest transaksi e-commerce gagal mempertahankan konsistensi skema. Kolom `customer_notes` pada 99% berkas Parquet bertipe data `string`, tetapi ada worker lama yang menulis berkas dengan data `customer_notes` yang sepenuhnya `null` dan secara inferensial bertipe `pa.null()`. Ketika sistem analitik Polars/DuckDB membaca partisi gabungan ini, query crash dengan error *Schema Mismatch/Type Collision*. Bagaimana rancangan defensive engineering pada kode ingesti untuk mencegah hal tersebut terjadi di level storage?
    * *Jawaban:* 1) Terapkan skema eksplisit (*strict schema enforcement*) menggunakan PyArrow Schema yang diikat secara kaku di level CI/CD writer; tolak penulisan berkas jika tipe data kolom tidak valid. 2) Jangan pernah menggunakan skema inferensial (`pa.Table.from_pandas` tanpa parameter `schema`). 3) Pada lapisan reader, definisikan `schema` secara statis pada deklarasi dataset (`pl.scan_parquet(..., schema=EXPECTED_SCHEMA)` atau `pyarrow.dataset.dataset(..., schema=EXPECTED_SCHEMA)`) agar reader secara otomatis mempromosikan atau meng-cast kolom null tersebut ke tipe `pa.string()` tanpa memicu error fatal.

---

### 16. Summary

1. **Efisiensi Kolumnar:** Format biner kolumnar (Apache Parquet & Apache Arrow) adalah pondasi dasar rekayasa data analitik modern. Pemisahan data per kolom menggeser paradigma komputasi dari pemborosan I/O baris tekstual mentah menjadi operasi terfokus berbasis seleksi kolom (*projection pushdown*) dan filtrasi nilai (*predicate pushdown*).
2. **Zero-Copy Architecture:** Apache Arrow menghilangkan batasan laten transformasi data antar sistem. Melalui pemetaan memori (`mmap`) dan C Data Interface, data dipindahkan antar pustaka komputasi (DuckDB, Polars, PyTorch) dalam skala gigabyte per detik tanpa alokasi duplikat memori dan tanpa siklus interupsi serialisasi CPU.
3. **Storage vs Compute Decoupling:** Apache Parquet bertindak sebagai standar *Cold/Warm Storage on Disk* yang menawarkan kompresi ekstrem (Zstandard/Snappy) serta struktur indeks metadata mikro (Row Group & Page Index). Sementara itu, Apache Arrow bertindak sebagai standar representasi *Hot In-Memory Execution*, memungkinkan vektorisasi SIMD hardware modern beroperasi pada kapasitas komputasi register puncak. Perancangan pipeline data analitik kelas enterprise yang tangguh bertumpu pada sinergi optimal antara kedua format biner ini.