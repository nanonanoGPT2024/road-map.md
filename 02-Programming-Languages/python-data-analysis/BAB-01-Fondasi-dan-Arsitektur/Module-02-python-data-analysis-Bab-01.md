# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 01: Fondasi dan Arsitektur — Python Data Analysis**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Mengukur Overhead Memori CPython**: Mengidentifikasi struktur internal `PyObject`, membedakan pointer dereferencing dari contiguous arrays, serta mengukur footprint memori pada tingkat byte menggunakan C-extensions dan buffer protocol.
2. **Merancang Pipeline Data Berperforma Tinggi Menggunakan Apache Arrow & SIMD**: Mengimplementasikan paradigma komputasi columnar berbasis memori zero-copy untuk mengeliminasi overhead serialisasi/deserialisasi pada pipeline analitik skala besar.
3. **Menerapkan Streaming & Chunked Execution Engine**: Membangun arsitektur pemrosesan data disk-to-memory yang beroperasi di dalam batasan bounded memory (RAM < 2 GB untuk dataset > 50 GB) menggunakan generator, memory-mapped files (`mmap`), dan batch iterator.
4. **Menegakkan Kontrak Data Produksi (Data Contracts)**: Mengintegrasikan skema validasi berbasis tipe deterministik (*runtime schema enforcement*) menggunakan Pandera dan Pydantic V2 pada layer ingest.
5. **Mengoptimalkan Trade-off Arsitektur Analisis Data**: Menentukan pilihan tepat antara pemrosesan *eager* vs *lazy*, *in-memory* vs *disk-backed*, serta memitigasi bottleneck Python Global Interpreter Lock (GIL) via komputasi terdistribusi atau native C/Rust kernels.

---

## 2. Prerequisite

Untuk memahami modul ini secara komprehensif, Anda harus menguasai:
*   **Fondasi Python Lanjutan**: Pemahaman mendalam tentang *dunder methods*, *generators/iterators*, *context managers*, dekorator, dan modul `ctypes`.
*   **Sistem Komputer & OS**: Konsep *paging*, virtual memory, *CPU cache hierarchy* (L1/L2/L3), *cache lines*, dan mekanisme *page faults*.
*   **Pemrograman NumPy/Pandas Menengah**: Paham konsep dasar array n-dimensi, masking, dan operasi agregasi standar.
*   **Environment**: Python 3.11+, compiler C (GCC/Clang), serta library ekosistem: `pyarrow`, `numpy`, `polars`, `pandera`, `memory_profiler`.

---

## 3. Concept & Internal Architecture

Pemrosesan data di Python pada skala enterprise menuntut pemahaman mendalam tentang abstraksi memori di balik CPython dan bagaimana library analitik modern menghindari overhead runtime bawaan Python.

### 3.1 Anatomi Memori CPython vs Contiguous Memory

Setiap objek dalam CPython dibungkus dalam struktur `PyObject` (atau `PyVarObject` untuk objek dengan panjang variabel seperti `list` atau `str`).

```text
Struktur PyObject dasar:
------------------------------------------
|  _PyObject_HEAD_EXTRA (debugging)      |
|  atomic_int64_t ob_refcnt  (8 bytes)   | -> Manajemen memori / Garbage Collection
|  struct _typeobject *ob_type (8 bytes) | -> Pointer ke metadata tipe objek
------------------------------------------
Total: Minimal 16 bytes overhead hanya untuk eksistensi satu integer.
```

Saat Anda mendeklarasikan list Python standar yang berisi 1 juta bilangan bulat (`[1, 2, 3, ...]`), memori dialokasikan secara terfragmentasi:
1. Sebuah array dari pointer (`PyObject*`) dialokasikan secara berurutan.
2. Setiap pointer mengarah ke lokasi heap yang berbeda tempat `PyLongObject` (28 bytes) berada.
3. **Konsekuensi CPU**: Saat iterasi dilakukan, CPU mengalami *cache miss* berkali-kali karena pointer melompat ke lokasi memori yang tidak bersebelahan (*pointer chasing*). Pipeline prediktor instruksi CPU tidak dapat melakukan pre-fetching secara efektif.

```text
CPython List of Ints (Pointer Indirection):
[ Pointer 0 ] ---> [ PyLongObject: 28B ] (Heap Address 0x00F1)
[ Pointer 1 ] ---> [ PyLongObject: 28B ] (Heap Address 0x88A2) (Cache Miss!)
[ Pointer 2 ] ---> [ PyLongObject: 28B ] (Heap Address 0x12C4) (Cache Miss!)

NumPy / C-Contiguous Array:
[ Int64 (8B) ][ Int64 (8B) ][ Int64 (8B) ][ Int64 (8B) ] (Block memori padat)
^ Cache Line L1 memuat 64 bytes sekaligus (8 nilai langsung masuk register SIMD)
```

### 3.2 Buffer Protocol dan Strided Arrays

Array numerik berkinerja tinggi bergantung pada **Python Buffer Protocol** (PEP 3118). Konsep intinya adalah mengekspos pointer internal ke contiguous memory buffer tanpa perlu menyalin data (*zero-copy view*).

Karakteristik memori ditentukan oleh:
*   **Base Pointer**: Alamat memori absolut elemen pertama.
*   **Shape**: Tuple yang menentukan dimensi array, misalnya `(N, M)`.
*   **Strides**: Tuple yang menentukan jumlah byte yang harus dilewati dalam memori untuk berpindah ke elemen berikutnya di sepanjang setiap dimensi.
*   **Itemsize**: Ukuran byte dari setiap elemen individu (misal: 8 bytes untuk `float64`).

Rumus kalkulasi offset memori:
$$\text{Offset}(i_0, i_1, \dots, i_k) = \sum_{j=0}^{k} (i_j \times \text{strides}[j])$$

Jika Anda melakukan transpose pada matriks NumPy contiguous, data underlying tidak dipindahkan di RAM. NumPy hanya menukar metadata `strides`, sebuah operasi berbiaya konstan $\mathcal{O}(1)$.

### 3.3 Apache Arrow: Arsitektur Columnar Berbasis IPC Zero-Copy

Pandas tradisional (berbasis NumPy v1) menyimpan data bertipe campuran secara terfragmentasi (tiap kolom satu array NumPy, sementara string disimpan sebagai list pointer CPython `PyObject*`). Ini menyebabkan serialisasi antar sistem (misal: dari Python runtime ke Spark runtime) menuntut CPU untuk melakukan serialisasi byte demi byte (Pickle/JSON serialization overhead).

**Apache Arrow** menyelesaikan ini dengan spesifikasi format memori standar industri:
*   **Columnar Layout**: Elemen-elemen dalam kolom yang sama ditempatkan bersebelahan. Ini memaksimalkan throughput kompresi data (Run-Length Encoding, Dictionary Encoding) dan pemrosesan SIMD (Single Instruction, Multiple Data).
*   **Null-Bitmap**: Penanganan missing value (`null`/`NaN`) menggunakan bitmap bit-level terpisah (1 bit per nilai), bukan menggunakan nilai sentinel seperti `np.nan` (yang memaksa konversi integer ke float) atau pointer `None`.
*   **Shared Memory IPC**: Komunikasi antar proses (Inter-Process Communication) menggunakan `mmap` langsung pada format Arrow buffer, memungkinkan transfer dataset berukuran terabyte antar runtime (C++, Python, Rust, JVM) dalam waktu $0$ detik tanpa serialisasi CPU.

```text
Apache Arrow RecordBatch Layout:
---------------------------------------------------------------------
Field 'user_id' (Int32)    : [Bitmap: 1111] [Data: 101, 102, 103, 104]
Field 'latency' (Float32)  : [Bitmap: 1101] [Data: 1.2, 0.4, NULL, 5.1]
Field 'service' (String)   : [Offsets: 0, 4, 7, 10, 14] [Data: "authapidbauth"]
---------------------------------------------------------------------
(Semua data tersusun padat, dapat dimapping via kernel OS langsung ke RAM)
```

---

## 4. Why & What

### Mengapa Performa Analisis Data Berbasis Python Tradisional Runtuh di Skala Enterprise?

1.  **Overhead Alokasi Memori**: Membuat 10.000.000 objek Python kecil menghabiskan ~300 MB alokasi hanya untuk metadata internal interpreter CPython.
2.  **Bottleneck GIL (Global Interpreter Lock)**: CPython mengeksekusi bytecode di bawah satu lock mutlak. Threading bawaan Python tidak dapat memparalelkan beban kerja komputasi numerik kecuali runtime dilepaskan (*GIL release*) melalui library ekstensi native C/Rust/Fortran.
3.  **Inefisiensi Cache**: Representasi non-columnar memaksa CPU menarik data yang tidak relevan ke L1/L2 cache line saat melakukan pemindaian (scan) pada field tertentu.

### Solusi Arsitektur Modern
Kita harus mengisolasi komputasi numerik berat ke kernel yang:
*   Bekerja pada buffer memori contiguous.
*   Mendukung komputasi *vectorized SIMD* (instruksi AVX-512 memproses delapan bilangan 64-bit per clock cycle).
*   Mengeksekusi model lazy evaluation berbasis directed acyclic graph (DAG) untuk memadatkan query (*predicate pushdown* dan *projection pushdown*).

---

## 5. How (Workflow Detail)

Berikut alur kerja produksi untuk memproses data throughput tinggi tanpa degradasi memori:

```text
   [ Disk: Raw Parquet/CSV Storage ]
                  │
                  ▼
   [ OS Page Cache / MMAP Layer ]
                  │
                  ▼ (Zero-Copy Read via Apache Arrow)
   [ Arrow Table / Shared Memory Buffer ]
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
   [ Vector Engine ]   [ Streaming Engine ]
   (SIMD Batch Calc)   (Bounded Chunk Generator)
        │                   │
        └─────────┬─────────┘
                  ▼
   [ Runtime Contract Validation (Pandera Engine) ]
                  │
                  ▼
   [ Output Sink: OLAP Database / Storage IPC ]
```

1.  **Ingestion & Memory Mapping**: Kernel OS memetakan file biner (Parquet) dari persistent storage langsung ke virtual memory address process via call `mmap(2)`.
2.  **Zero-Copy Deserialization**: Apache Arrow membaca metadata skema dan mengikat array pointer langsung ke byte yang telah dipetakan di RAM tanpa translasi objek Python.
3.  **Chunk Allocation Control**: Jika dataset melampaui RAM fisik, generator membagi record batch ke unit deterministik (misal: 64k records per batch).
4.  **Vectorized Processing Execution**: Native vectorized engine (NumPy C-API atau Arrow Compute Kernels) mengeksekusi operasi matematika dengan melepas GIL.
5.  **Schema Contract Enforcement**: DataFrame divalidasi terhadap kontrak data (skema kolom, rentang numerik, ekspresi reguler) secara in-line per batch.
6.  **Egress**: Hasil dialirkan ke tujuan akhir (Parquet, database OLAP, socket IPC).

---

## 6. Analogy & Diagram ASCII

Bayangkan memori CPython seperti **Gudang Paket Konvensional**:
Setiap paket (integer/string) dibungkus kardus tebal (overhead `PyObject`), diberi label berat, dan diletakkan di rak yang terpencar acak di seluruh gudang. Ketika staf (CPU) ingin menghitung total nilai 100 paket, ia harus berlari menyusuri lorong gudang dari satu rak ke rak lain mengambil alamat kardus satu per satu (*pointer chasing*).

Sebaliknya, Contiguous Memory / Arrow seperti **Pabrik Kontainer Modern**:
Barang-barang sejenis dicetak langsung dalam cetakan logam panjang yang solid. Sepuluh ribu mur logam berada berjejer rapat di dalam satu rel panjang. Crane pemindai (CPU SIMD) meluncur sekali jalan dan memindai 64 mur sekaligus dalam satu tarikan milidetik.

```text
CPython Heap (Terfragmentasi):
Addr 0x1000: [Header][Refcount][TypePtr][Value: 42]
... (terbuang / heap fragment)
Addr 0x4500: [Header][Refcount][TypePtr][Value: 88]
... (terbuang / heap fragment)
Addr 0x9200: [Header][Refcount][TypePtr][Value: 12]

Contiguous Memory (Vectorized Native):
Addr 0x1000: [ 42 | 88 | 12 | 99 | 105 | 200 | 304 | 512 ]
              └─────────────── 1x CPU Cache Line ────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membedah Overhead Memori CPython Menggunakan `ctypes`

Skrip ini membuktikan overhead `PyObject` secara empiris dan membaca data mentah dari memory address.

```python
import sys
import ctypes

def inspect_pyobject(obj: object) -> None:
    address = id(obj)
    print(f"--- Memory Inspection for: {type(obj).__name__} at {hex(address)} ---")
    print(f"sys.getsizeof footprint : {sys.getsizeof(obj)} bytes")
    
    # Membaca 8-byte pertama: Reference Count (ob_refcnt)
    ref_count = ctypes.c_int64.from_address(address).value
    # Membaca 8-byte kedua: Type Object Pointer (ob_type)
    type_ptr = ctypes.c_void_p.from_address(address + 8).value
    
    print(f"Internal RefCount       : {ref_count}")
    print(f"Internal Type Pointer   : {hex(type_ptr)}")
    print(f"Actual Type Address     : {hex(id(type(obj)))}")
    assert type_ptr == id(type(obj)), "Pointer tipe harus identik dengan alamat class!"

# Perbandingan integer vs list overhead
val = 1_000_000
inspect_pyobject(val)

empty_list = []
inspect_pyobject(empty_list)
```

### 7.2 Practical Example: Enterprise Ingestion Engine dengan Polars/Arrow, Pandera & Memory Tracking

Implementasi pipeline streaming berbasis batch dengan zero-copy record batch read, manipulasi native SIMD, validasi skema runtime deterministik, dan monitoring penggunaan resident memory (RSS).

```python
import os
import psutil
from typing import Generator
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc
import polars as pl
import pandera.polars as pa_check
from pandera.polars import Column, DataFrameSchema

# 1. Definisi Kontrak Data Produksi (Data Contract via Pandera)
TelemetrySchema = DataFrameSchema(
    columns={
        "device_id": Column(str, nullable=False),
        "temperature": Column(float, checks=pa_check.Check.in_range(-50.0, 150.0)),
        "pressure": Column(float, checks=pa_check.Check.greater_than(0.0)),
        "error_flag": Column(bool),
    },
    strict=True,
    coerce=True
)

class ProductionIngestionEngine:
    def __init__(self, file_path: str, batch_size: int = 50_000):
        self.file_path = file_path
        self.batch_size = batch_size
        self.process = psutil.Process(os.getpid())

    def _get_rss_mb(self) -> float:
        """Mengambil Resident Set Size (RSS) aktual dari OS."""
        return self.process.memory_info().rss / (1024 * 1024)

    def generate_dummy_parquet(self, total_records: int = 200_000) -> None:
        """Membuat dataset Parquet untuk simulasi pengujian performa."""
        print(f"[*] Generating {total_records} records of test data...")
        df = pl.DataFrame({
            "device_id": [f"DEV-{i % 1000:04d}" for i in range(total_records)],
            "temperature": [(i % 120) - 20.5 for i in range(total_records)],
            "pressure": [(i % 15) + 0.1 for i in range(total_records)],
            "error_flag": [True if i % 100 == 0 else False for i in range(total_records)]
        })
        df.write_parquet(self.file_path, compression="snappy")
        print(f"[*] Test Parquet created: {self.file_path} ({os.path.getsize(self.file_path) / 1024:.2f} KB)")

    def stream_batches(self) -> Generator[pl.DataFrame, None, None]:
        """
        Streaming batches langsung dari disk menggunakan Arrow IPC Zero-Copy reader.
        Menghindari pembacaan seluruh file ke dalam RAM.
        """
        parquet_file = pq.ParquetFile(self.file_path)
        for batch_record in parquet_file.iter_batches(batch_size=self.batch_size):
            # Zero-copy konversi dari PyArrow RecordBatch ke Polars DataFrame
            pl_df = pl.from_arrow(batch_record)
            yield pl_df

    def execute_pipeline(self) -> dict:
        print(f"[+] Baseline RSS: {self._get_rss_mb():.2f} MB")
        total_rows_processed = 0
        total_anomalies_detected = 0

        for idx, batch_df in enumerate(self.stream_batches()):
            # A. Validasi Data Contract per batch
            validated_df = TelemetrySchema.validate(batch_df)

            # B. Vectorized Processing (Ekspresi dieksekusi via SIMD/C-engine tanpa GIL)
            # Filter suhu kritis > 80C dan pressure > 10.0
            anomaly_filter = (pl.col("temperature") > 80.0) & (pl.col("pressure") > 10.0)
            anomalies = validated_df.filter(anomaly_filter)

            total_rows_processed += len(validated_df)
            total_anomalies_detected += len(anomalies)

            print(
                f" -> Batch {idx + 1:02d} | Rows: {len(validated_df)} | "
                f"Batch Anomalies: {len(anomalies)} | "
                f"Current RSS: {self._get_rss_mb():.2f} MB"
            )

        print(f"[+] Final RSS: {self._get_rss_mb():.2f} MB")
        return {
            "total_rows": total_rows_processed,
            "total_anomalies": total_anomalies_detected
        }

if __name__ == "__main__":
    DATA_PATH = "telemetry_enterprise_test.parquet"
    engine = ProductionIngestionEngine(file_path=DATA_PATH, batch_size=50_000)
    try:
        engine.generate_dummy_parquet(total_records=250_000)
        results = engine.execute_pipeline()
        print(f"[✓] Pipeline Selesai Berhasil: {results}")
    finally:
        if os.path.exists(DATA_PATH):
            os.remove(DATA_PATH)
```

---

## 8. Real World Case Study: High-Frequency Trading Tick-By-Tick Analytics

### Skenario
Sebuah firma FinTech kuantitatif menerima market feed sebesar ~120 GB data tick-by-tick (Level-2 Order Book) per hari. Feed berisi timestamp presisi nanodetik, ID sekuritas, volume, bid, dan ask.

*Tantangan Produksi:*
1. Server worker hanya dialokasikan kontainer k8s dengan spesifikasi 8 vCPU dan RAM 8 GB.
2. Membaca data sekaligus menggunakan Pandas konvensional (`pd.read_csv` atau `pd.read_parquet`) memicu **OOM (Out Of Memory) Kills** seketika karena Pandas membutuhkan 3x hingga 5x ukuran file dalam RAM.
3. Kebutuhan komputasi: Menghitung metrik agregasi interval rolling 5-menit (Time-Weighted Average Spread - TWAS).

### Solusi Arsitektur
1. **Penyimpanan**: Menghilangkan CSV; mengonversi raw network capture ke Parquet dengan kompresi ZSTD dictionary encoding, dipartisi secara fisik berdasarkan `date/ticker`.
2. **Execution Engine**: Menggunakan Polars Lazy Execution Framework atau DuckDB over Arrow memory. Data diakses melalui *projection pushdown* (hanya memuat kolom `timestamp`, `bid`, `ask`) dan *predicate pushdown* (filter ticker pada Parquet metadata layer tanpa memuat baris yang tidak cocok).
3. **Execution Plan**: Alih-alih mengeksekusi eager loading, pipeline merakit DAG ekspresi logis, membagi data dalam stream memory 256MB micro-chunks, lalu menghitung TWAS menggunakan SIMD aggregations dengan batas konsumsi RAM maksimum di 2.4 GB RSS.

---

## 9. Trade-offs

| Parameter | Pandas Klasik (NumPy v1) | Apache Arrow / Polars | DuckDB (Embedded OLAP) | Memory-Mapped (`mmap`) Raw Bytes |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput Scanning** | Rendah (Pointer overhead & GIL) | Sangat Tinggi (SIMD/Multithreaded native) | Sangat Tinggi (Vectorized execution engine) | Maksimal (Native hardware speed) |
| **Memory Footprint** | Buruk (3x-5x dataset size) | Rendah (Zero-copy layout) | Sangat Rendah (Paging & Spilling ke Disk) | Minimal (Hanya OS buffer cache) |
| **Kemudahan Implementasi**| Sangat Mudah (Ad-hoc API standar) | Menengah (Ekosistem berkembang) | Mudah (SQL standard compliant) | Kompleks (Manual byte slicing & endianness) |
| **Serialisasi / IPC Latency**| Tinggi (Harus pickle / serialize) | Nol (Zero-Copy shared memory) | Sangat Rendah (Zero-copy Arrow translation) | Nol (Shared raw pointer) |
| **Validasi Skema** | Manual / Tidak Ketat | Built-in via Arrow Schema | Ditegakkan via Relational DDL | Manual byte offset assertions |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent Memory Duplication Melalui Method Chaining
*Gejala:* Konsumsi RAM melonjak dua kali lipat saat melakukan filtering sederhana.
*Akar Masalah:* Melakukan operasi seperti `df = df[df['val'] > 0]` pada Pandas tanpa mengelola referensi internal menyebabkan alokasi copy implisit jika data bertipe `object`.
*Solusi:* Gunakan engine inplace/copy-on-write (`pd.options.mode.copy_on_write = True`) atau beralih sepenuhnya ke immutable chunking Polars.

### 10.2 Type Coercion Mengubah Integer Menjadi Float64
*Gejala:* Integer array berukuran 100 juta elemen tiba-tiba memicu kenaikan memori dari 400MB ke 800MB.
*Akar Masalah:* Keberadaan satu nilai `NaN` atau `None` pada array integer NumPy memaksa runtime melakukan upcast seluruh kolom menjadi `float64` untuk mengakomodasi representasi `IEEE 754 NaN`.
*Solusi:* Gunakan tipe data Arrow-backed (`Int64Dtype` pada Pandas >= 2.0 atau tipe native integer Polars) yang memiliki Null Bitmap independen.

### 10.3 GIL Contention pada Pemrosesan Multi-Thread
*Gejala:* Menjalankan pipeline dalam `ThreadPoolExecutor` justru menurunkan throughput data transfer dibanding single thread.
*Akar Masalah:* Operasi transformasi string atau fungsi Python custom (`.apply(lambda x: ...)`) memanggil interpreter bytecode berulang kali, menyebabkan perebutan lock GIL antar-thread secara konstan (*lock thrashing*).
*Solusi:* Tulis transformasi menggunakan ekspresi berbasis native expression trees (vektor C/Rust) yang secara eksplisit melepas GIL.

---

## 11. Best Practices (Production Checklist)

- [ ] **Kunci Tipe Data Secara Eksplisit**: Jangan biarkan engine menebak tipe skema (*schema inference*). Selalu tentukan tipe kolom saat ingestion (`schema={"id": pa.int32(), ...}`).
- [ ] **Terapkan Predicate & Projection Pushdown**: Hanya baca kolom yang relevan ke pipeline (`columns=['id', 'target']`) dan dorong filter nilai sedekat mungkin ke disk storage layer.
- [ ] **Gunakan Chunking Bounded**: Selalu batasi ukuran iterator batch (`batch_size=N`) untuk membatasi konsumsi RAM maksimum secara deterministik.
- [ ] **Aktifkan Arrow-Backed Memory**: Pada ekosistem Pandas 2.0+, nyalakan opsi `engine='pyarrow'` dan *Copy-on-Write*.
- [ ] **Validasi Skema pada Boundary API**: Validasi data di boundary sistem (ingest & egress) menggunakan Pandera/Pydantic; jangan biarkan data mentah tak bertipe mengalir bebas di core model.
- [ ] **Pantau OS Resident Set Size (RSS)**: Jangan hanya mengukur alokasi Python heap via `sys.getsizeof()`. Gunakan `psutil` atau profiling OS untuk memonitor konsumsi memori fisik aktual.

---

## 12. Hands-on Practice

Buatlah direktori praktikum dengan instruksi langkah-demi-langkah berikut:

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### File 1: `hands-on/m02/memory_bench.py`
Skrip untuk membandingkan alokasi contiguous vs pointer based memory.

```python
import sys
import time
import numpy as np

def benchmark_memory():
    n = 20_000_000
    print(f"--- Benchmarking Memory & Compute: N = {n} ---")
    
    # 1. Standard Python List
    start_time = time.perf_counter()
    py_list = list(range(n))
    list_alloc_time = time.perf_counter() - start_time
    # Estimasi kasar: list pointer + objek integernya
    list_mem = sys.getsizeof(py_list) + (n * sys.getsizeof(n))
    print(f"[Python List] Alloc Time: {list_alloc_time:.4f}s | Est. Mem: {list_mem / (1024**2):.2f} MB")
    
    # Sum Compute Python List
    start_time = time.perf_counter()
    list_sum = sum(py_list)
    list_calc_time = time.perf_counter() - start_time
    print(f"[Python List] Sum Time  : {list_calc_time:.4f}s")
    
    del py_list # Bebaskan memori
    
    # 2. Contiguous NumPy Int64 Array
    start_time = time.perf_counter()
    np_arr = np.arange(n, dtype=np.int64)
    np_alloc_time = time.perf_counter() - start_time
    np_mem = np_arr.nbytes
    print(f"[NumPy Array] Alloc Time: {np_alloc_time:.4f}s | Exact Mem: {np_mem / (1024**2):.2f} MB")
    
    # Sum Compute NumPy SIMD
    start_time = time.perf_counter()
    np_sum = np.sum(np_arr)
    np_calc_time = time.perf_counter() - start_time
    print(f"[NumPy Array] Sum Time  : {np_calc_time:.4f}s")
    
    assert list_sum == np_sum, "Hasil kalkulasi wajib identik!"
    print(f"[Result] Performa Kalkulasi NumPy: {list_calc_time / np_calc_time:.2f}x lebih cepat.")

if __name__ == "__main__":
    benchmark_memory()
```

Jalankan script untuk mengamati rasio latensi komputasi dan konsumsi RAM:
```bash
python memory_bench.py
```

---

## 13. Exercise

### Level Easy
Tuliskan sebuah script yang menerima list Python berisi 1.000.000 float, mengubahnya menjadi NumPy array 1D tanpa duplikasi buffer via protocol, mengekstrak memory address aslinya melalui `__array_interface__`, dan memverifikasi bahwa `base` dari array tersebut menunjuk ke buffer asal jika memungkinkan.

### Level Medium
Buat generator data transaksi keuangan (`transaction_id`, `user_id`, `amount`, `currency`). Implementasikan class streaming reader yang membaca file CSV berukuran 5 GB dalam batch 100.000 baris. Lakukan filtering agregasi secara streaming: hitung total akumulasi `amount` untuk transaksi dengan mata uang `"USD"` dan `amount > 500.00`, dengan menjaga batas pemakaian RAM tidak melebihi 100 MB setiap saat.

### Level Hard
Implementasikan sebuah C-Extension sederhana via `ctypes` atau modul C-API Python yang menerima sebuah NumPy array 2D berdimensi $M \times N$ (bertipe `float64`), membaca raw pointer datanya secara langsung, dan mengeksekusi transposisi matriks secara manual *in-place* dengan melakukan manipulasi swapping memory block tanpa membuat array baru atau mengubah strides array dari level Python runtime.

---

## 14. Challenge

### Studi Kasus: Multi-Tenant Zero-Copy Stream Router dengan Bounded RAM

**Konteks Arsitektural:**
Perusahaan SaaS Anda memiliki message queue Kafka yang menampung log event analitik dari ribuan enterprise customer. Log ini didorong ke disk storage sementara dalam file-file Parquet masif (~10 GB per batch jam). 

Setiap record memiliki skema:
```text
{
    "tenant_id": str (UUID),
    "timestamp": int64 (Epoch Microseconds),
    "payload_metric": float64,
    "signature": str (SHA-256)
}
```

**Tantangan:**
Rancang dan bangun sebuah service engine bernama `ZeroCopyTenantRouter` yang memenuhi batasan arsitektur ekstrem berikut:
1. **Memory Budget**: Server worker hanya memiliki RAM bebas sebesar 512 MB. Program dilarang keras melebihi RSS 450 MB.
2. **Multi-Tenant Demux**: Pipeline harus memecah file master 10 GB tersebut ke dalam direktori terpisah berdasarkan `tenant_id` (`/data/tenants/{tenant_id}/data.parquet`).
3. **Kepatuhan Data Integrity**: Tiap batch yang diproses harus divalidasi terhadap skema yang ketat: `signature` tidak boleh null, `payload_metric` berada di dalam deviasi 3-sigma dari batch terkait. Baris yang rusak harus diextract ke log error terpisah tanpa menghentikan pemrosesan stream.
4. **Zero-Copy Requirement**: Hindari serialisasi intermediate ke JSON atau dictionary CPython. Seluruh operasi manipulasi wajib bertahan dalam representasi Arrow buffers atau memori biner native.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic (Pilihan Ganda & Singkat)
1. **Berapa ukuran overhead memori minimum struktur `PyObject` murni pada CPython 64-bit sebelum data nilainya sendiri dihitung?**
   - A. 0 bytes
   - B. 8 bytes
   - C. 16 bytes
   - D. 64 bytes

2. **Apa peran utama dari tuple `strides` dalam NumPy n-dimensional array?**
   - A. Menyimpan nama label indeks pada tiap dimensi.
   - B. Menunjukkan jumlah byte yang harus dilompati dalam memori untuk berpindah ke elemen berikutnya di tiap dimensi.
   - C. Menyimpan batas minimum dan maksimum nilai data dalam array.
   - D. Menentukan kompresi bit yang digunakan oleh buffer.

3. **Format Arrow Columnar menggunakan *Null Bitmap*. Apa keunggulan arsitektural pendekatan ini dibandingkan penggunaan float NaN di Pandas tradisional?**
   - A. Mencegah konversi implisit kolom Integer menjadi Float saat terdapat nilai kosong.
   - B. Menghilangkan kebutuhan alokasi RAM sama sekali.
   - C. Mengenkripsi data null secara otomatis.
   - D. Mempercepat koneksi jaringan internet.

4. **Operasi NumPy mana di bawah ini yang menghasilkan *memory view* (Zero-Copy) alih-alih alokasi salinan memori baru (*deep copy*)?**
   - A. `arr[arr > 10]` (Boolean indexing)
   - B. `arr.T` (Transpose pada 2D C-contiguous array)
   - C. `arr.astype(np.float32)`
   - D. `arr.flatten()`

5. **Apa yang diukur oleh metrik sistem operasi *Resident Set Size (RSS)*?**
   - A. Ukuran total kapasitas swap memory di hard drive.
   - B. Estimasi ukuran file Python bytecode `.pyc`.
   - C. Besaran memori fisik RAM riil yang sedang ditempati oleh proses saat ini.
   - D. Jumlah thread Python yang sedang menunggu GIL.

---

### 15.2 Intermediate (Konseptual & Analisis Kasus)
6. **Jelaskan mengapa CPU cache line (misal: 64 bytes) dapat meningkatkan efisiensi eksekusi saat kita menjumlahkan array 1D NumPy contiguous bertipe `float64` jika dibandingkan dengan menjumlahkan elemen di dalam list bawaan Python!**

7. **Dalam pipeline pemrosesan data, apa yang dimaksud dengan optimasi *Predicate Pushdown* dan bagaimana arsitektur file Parquet/Arrow memfasilitasinya secara native tanpa membaca seluruh dataset?**

8. **Bagaimana mekanisme *Copy-on-Write* (CoW) yang diperkenalkan pada Pandas 2.0+ melindungi integritas data sekaligus menghemat alokasi memori saat melakukan operasi dataframe slicing?**

9. **Perhatikan potongan kode berikut:**
   ```python
   # Potongan A:
   for i in range(len(df)):
       df.loc[i, 'total'] = df.loc[i, 'price'] * df.loc[i, 'qty']

   # Potongan B:
   df['total'] = df['price'] * df['qty']
   ```
   **Jelaskan perbedaan performa kedua kode di atas dari perspektif pemanggilan interpreter CPython, GIL, dan SIMD vectorization!**

10. **Kapan Anda harus memilih format Apache Arrow IPC streaming dibandingkan format serialisasi Parquet untuk pertukaran data antar-layanan?**

---

### 15.3 Skenario Kasus Produksi

11. **Skenario Incident OOM:**
    Pipeline analytics harian Anda berjalan di AWS ECS task dengan batasan RAM 4 GB. Pipeline memproses log event yang ukurannya meningkat dari 1 GB ke 3.5 GB. Tiba-tiba task mati dengan status error `OutOfMemory / Exit Code 137`. Saat dianalisis, kode hanya menggunakan satu baris: `df = pl.read_csv("large_file.csv")`. 
    *Sebagai Lead Data Engineer, bagaimana analisis akar masalah teknis Anda dan modifikasi kode apa yang wajib diterapkan agar memory consumption turun di bawah 1 GB tanpa menambah kapasitas RAM mesin?*

12. **Skenario Serialization Bottleneck:**
    Sebuah microservice Python backend harus mengirimkan DataFrame hasil analitik (~500 MB di memori) ke worker service berbasis Go untuk kalkulasi lebih lanjut via jaringan lokal (gRPC). Penggunaan JSON serialization memakan waktu 12 detik dan membebani 100% CPU untuk proses marshalling. 
    *Rancang arsitektur data transfer zero-copy (atau mendekati zero-copy) menggunakan Apache Arrow Flight untuk menyelesaikan bottleneck ini! Sebutkan alur kerjanya.*

13. **Skenario Kontrak Data & Data Corruption:**
    Sebuah sistem perbankan menerima stream file Parquet dari vendor eksternal. Seringkali vendor mengubah skema tanpa pemberitahuan (misal: kolom `balance` yang seharusnya `Int64` masuk sebagai string, atau nilai `account_id` berformat alpha-numeric kosong). 
    *Di mana layer validasi skema runtime harus diletakkan dalam arsitektur ingestion, dan bagaimana Anda mendesain mekanisme quarantine pipeline yang efisien tanpa mengorbankan throughput pemrosesan data batch yang valid?*

---

## 16. Summary

Fondasi analisis data berkinerja tinggi dalam ekosistem Python modern berpijak pada prinsip meminimalkan overhead CPython dan memaksimalkan kapabilitas perangkat keras komputasi:

1.  **CPython Primitives Membawa Overhead Struktural**: Objek dasar Python dibebani oleh metadata `PyObject`, alokasi heap yang terfragmentasi, dan pointer chasing. Analitik skala besar menuntut transisi ke buffer contiguous.
2.  **Columnar Zero-Copy Adalah Standar Produksi**: Format Apache Arrow memungkinkan pipeline mempertahankan struktur data biner standar industri di seluruh batasan proses (IPC), memangkas latensi serialisasi hingga titik nol.
3.  **Vectorized Engines Melepas Batasan GIL**: Melalui integrasi engine seperti NumPy, Polars, dan Arrow Compute, komputasi numerik dialihkan ke tingkat native C/Rust. Hal ini memungkinkan CPU mengeksekusi instruksi paralel SIMD dan memanfaatkan CPU L1/L2/L3 cache lines secara optimal.
4.  **Arsitektur Bounded-Memory Wajib untuk Reliabilitas Skala Enterprise**: Pipeline data produksi tidak boleh berasumsi bahwa dataset selalu muat di dalam RAM. Pola streaming batch, lazy evaluation, serta predicate pushdown adalah guardrail utama dari kegagalan sistemik akibat *Out-Of-Memory* (OOM).