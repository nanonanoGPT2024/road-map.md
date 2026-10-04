# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Data Wrangling Modern (Pandas 2.x & Apache Arrow)**  
**Topik: python-data-analysis | Kategori: 02-Programming-Languages**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mendiagnosis & Mengeliminasi Bottleneck Memori**: Mengidentifikasi kelemahan alokasi memori internal Pandas berbasis NumPy (`BlockManager` fragmentation & `PyObject*` pointer overhead) dan merekonstruksi pipeline menggunakan Apache Arrow Backend (`ArrowExtensionArray`).
2. **Mengimplementasikan Pola Zero-Copy & Vectorized Wrangling**: Merancang alur pemrosesan data bebas alokasi redundan (*zero-copy views*, *dictionary encoding*, *string manipulation*) memanfaatkan spesifikasi memori kolumnar Arrow IPC.
3. **Membangun Arsitektur ETL Skala Enterprise**: Mengonstruksi modul ekstraksi dan transformasi berorientasi produksi dengan *defensive typing*, *method chaining*, validasi skema runtime, serta penanganan partisi *out-of-core* (chunking & memory-mapped I/O).
4. **Mengevaluasi Trade-off Eksekusi**: Menilai parameter latensi, throughput, dan konsumsi memori (*memory footprint*) antara PyArrow engine, NumPy engine, dan serialisasi Parquet/Feather pada lingkungan produksi berkapasitas throughput tinggi.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* **Pemrograman Python Tingkat Lanjut**: Pemahaman mendalam mengenai Python Data Model, Memory Management (Garbage Collection, Reference Counting), C-Extensions basics, typing (`typing.Annotated`, `Protocol`, `TypeVar`).
* **Dasar NumPy & Alokasi Memori C**: Pemahaman mengenai *strides*, contiguous arrays (`C-contiguous` vs `Fortran-contiguous`), dan pointer dereferencing.
* **Fondasi Pandas 1.x/2.x**: Manipulasi `DataFrame`, operasi `groupby`, agregasi dasar, dan pembacaan berkas flat (CSV, JSON).
* **Lingkungan Sistem**: Akses ke Python 3.10+ dengan dependensi: `pandas>=2.2.0`, `pyarrow>=15.0.0`, `psutil>=5.9.0`, `fastparquet>=2024.2.0`.

---

## 3. Concept & Internal Architecture

### 3.1 Evolusi Internal: BlockManager NumPy vs ArrowExtensionArray
Pada Pandas versi legacy (<2.0), representasi memori internal bertumpu pada `BlockManager`. `BlockManager` mengelompokkan kolom bertipe data homogen ke dalam array 2-dimensi NumPy. 

Struktur ini menimbulkan tiga limitasi struktural utama:
1. **Consolidation Overhead**: Operasi seperti penambahan kolom (`df['new_col'] = ...`) atau penyaringan baris memicu konsolidasi (*consolidation*) blok memori secara internal, memaksa alokasi memori baru dan operasi copy yang mahal ($O(N)$ alokasi memori).
2. **String as Python Object Pointers**: Kolom string disimpan sebagai array pointer (`PyObject*`) yang merujuk ke objek heap Python terpisah di memori. Setiap elemen membutuhkan overhead 28 byte dasar untuk header `PyObject` ditambah ukuran string sebenarnya, memicu *cache invalidation* pada CPU L1/L2/L3 cache karena data tidak disimpan secara kontigu.
3. **Nullability Bitmask**: NumPy tidak mendukung representasi data kosong (*missing value*) secara natif untuk integer atau boolean tanpa mengorbankan integritas data (misalnya mengubah `int64` menjadi `float64` untuk mengakomodasi `np.nan`).

```
PANDAS 1.X (NumPy Engine):
DataFrame
└── BlockManager
    ├── FloatBlock (2D NumPy Array: float64) [Contiguous]
    ├── IntBlock (2D NumPy Array: int64)     [Contiguous]
    └── ObjectBlock (1D NumPy Array: PyObject*)
        ├── Pointer 0 ───> Heap: "Alfa" (28B overhead + bytes)
        ├── Pointer 1 ───> Heap: "Bravo" (28B overhead + bytes)
        └── Pointer 2 ───> Heap: None (PyObject_None)
```

Pandas 2.x memperkenalkan integrasi penuh dengan **Apache Arrow Columnar Format** melalui `ArrowExtensionArray`. Arsitektur ini menyingkirkan fragmentasi pointer heap dan memisahkan metadata tipe data secara deterministik.

```
PANDAS 2.X (Arrow Backend):
DataFrame
└── ArrowExtensionArray (1D Columnar Buffer)
    ├── Validity Bitmap (1-bit per baris: 1=Valid, 0=Null)
    ├── Offsets Buffer  (int32/int64: index lokasi string)
    └── Values Buffer   (Flat contiguous UTF-8 bytes: "AlfaBravo")
```

### 3.2 Struktur Buffer Apache Arrow
Apache Arrow menetapkan standarisasi tata letak memori (*in-memory layout*) berbasis kolom yang seragam lintas bahasa (C++, Rust, Java, Python). Setiap kolom data berbasis string (`pa.string()` atau `string[pyarrow]`) terdiri dari:
1. **Validity Bitmap**: Buffer bit yang mencatat keberadaan nilai null (1 bit per elemen; $N$ elemen hanya membutuhkan $\lceil N/8 \rceil$ byte).
2. **Offsets Buffer**: Array integer 32-bit (atau 64-bit pada *large string*) yang menandai batas offset byte awal dan akhir untuk tiap string.
3. **Values Buffer**: Buffer array byte murni (`uint8_t[]`) kontigu yang menyimpan representasi UTF-8 tanpa delimeter string dan tanpa Python object wrapping.

### 3.3 Zero-Copy Slicing dan Memory-Mapped IPC
Karena struktur buffer bersifat immutable dan kontigu, operasi slicing (`df.iloc[start:end]`) pada kolom Arrow dapat dieksekusi secara **Zero-Copy**. Alih-alih menyalin data fisik, Pandas hanya membuat *Window View* baru dengan menggeser pointer offset dan memodifikasi metadata panjang baris.

Konsep ini memungkinkan komunikasi inter-process (IPC) melalui `mmap` (Memory-Mapped Files) tanpa biaya serialisasi/deserialisasi (*serde*), memangkas waktu deserialisasi dari ratusan milidetik menjadi nol detik (hanya overhead pemetaan virtual memory table oleh kernel OS).

---

## 4. Why & What

| Dimensi | Pendekatan Tradisional (Pandas 1.x / NumPy) | Pendekatan Modern (Pandas 2.x + Apache Arrow) | Dampak Produksi |
| :--- | :--- | :--- | :--- |
| **Representasi Null** | Memerlukan sentinel values (`np.nan` memaksa cast `int` ke `float64`) | Bitmask validity terdedikasi (`pd.NA`, tipe asli tidak bermutasi) | Mengeliminasi bug konversi tipe; menjaga integritas data keuangan & ID transaksi |
| **Konsumsi Memori Teks** | Sangat boros (28-56 byte overhead per entri string via pointer heap) | Padat & Kontigu (0 overhead per-objek, murni offset + byte UTF-8) | Reduksi footprint memori sebesar 70% hingga 85% pada dataset textual/kategorikal |
| **Performa I/O Parquet** | Wajib konversi tipe dari format Parquet (C++) $\to$ PyObject $\to$ NumPy array | Direct zero-copy atau direct buffer copy dari C++ Arrow Table ke DataFrame | Peningkatan throughput pembacaan Parquet hingga 3x-10x |
| **Efisiensi Filter / Mask** | Boolean array menggunakan 1 byte per baris (`bool_` NumPy) | Validity bitmask menggunakan 1 bit per baris | Mengurangi beban memory bandwidth CPU saat operasi filtering intensif |

---

## 5. How (Workflow Detail)

Untuk menerapkan arsitektur *wrangling* modern berbasis Arrow secara sistematis, ikuti alur eksekusi deterministik berikut:

```
[Parquet / CSV Raw Source]
         │
         ▼
[PyArrow Native Reader Engine] ─── (Zero-Copy Buffer Allocation / Memory Map)
         │
         ▼
[Pandas 2.x DataFrame] (dtype_backend='pyarrow')
         │
         ├───> [Method Chaining Pipeline]
         │       ├── Vectorized Math (C++ Simd Instructions)
         │       ├── Bitmask Filtering (Zero-Copy Slicing)
         │       └── Zero-Copy Dictionary Encoding (Categorical)
         │
         ▼
[Runtime Schema & Memory Assertions]
         │
         ▼
[Arrow IPC / Feather / Parquet Storage Sink] (ZSTD Compression)
```

1. **Ingestion & Engine Selection**:
   * Gunakan `engine="pyarrow"` dan parameter `dtype_backend="pyarrow"` pada `pd.read_csv()` atau `pd.read_parquet()`.
   * Hindari pembacaan *default* yang menginisialisasi NumPy BlockManager.
2. **Schema Definition & Casting**:
   * Tentukan skema masukan eksplisit menggunakan tipe data native Arrow (`pa.int64()`, `pa.string()`, `pa.timestamp()`).
3. **Execution via Method Chaining**:
   * Terapkan fungsional murni tanpa mutasi *in-place* (`inplace=False`).
   * Gunakan `.assign()` untuk transformasi turunan dan filter terindeks bitmask.
4. **Optimasi Struktur String & Low-Cardinality**:
   * Konversi kolom teks berulang ke `dictionary[pyarrow]` (ekuivalen dengan `category`, namun divalidasi langsung oleh Arrow C++ engine).
5. **Egress Pipeline**:
   * Serialisasi langsung ke format Arrow IPC Stream atau Parquet terkompresi Zstandard (ZSTD) tanpa rekonversi tipe data.

---

## 6. Analogy & Diagram ASCII

### Analogi Perpustakaan: NumPy Object vs Apache Arrow Memory Layout

* **NumPy Object (Pandas 1.x)**: Bayangkan sebuah rak katalog kartu. Setiap entri pada kartu tidak menuliskan isi buku secara langsung, melainkan alamat gudang lain di seberang kota tempat buku itu disimpan. Jika Anda ingin membaca 1.000 judul buku, kurir Anda harus bolak-balik 1.000 kali ke berbagai penjuru kota (**pointer chasing/cache miss**).
* **Apache Arrow (Pandas 2.x)**: Seluruh teks dicetak langsung pada satu gulungan kertas raksasa yang bersambung (*contiguous bytes buffer*), disertai indeks penggaris yang mencatat batas awal dan akhir dari setiap kalimat (*offsets buffer*). Pembacaan dilakukan secara berurutan dan cepat tanpa melangkah keluar dari ruangan (**CPU cache hit via SIMD**).

```
NUMPY OBJECT MEMORY LAYOUT (Fragmented Pointers):
Memory Address Space
[0x00A0]: Pointer -> [0x9920: "Jakarta\0"] (Heap Allocation 1)
[0x00A8]: Pointer -> [0x1140: "Surabaya\0"] (Heap Allocation 2)
[0x00B0]: Pointer -> [0x5580: "Bandung\0"] (Heap Allocation 3)
*CPU Cache Line harus memuat pointer, lalu fetch memory acak di heap -> Menghancurkan performa!

APACHE ARROW STRING LAYOUT (Contiguous & Deterministic):
Validity Bitmap:  [ 1 ,  1 ,  1 ] (Binary bits, 1 byte fits 8 rows)
Offsets Buffer:   [ 0 ,  7 , 15 , 22 ] (Array of int32)
Values Buffer:    [ 'J','a','k','a','r','t','a','S','u','r','a','b','a','y','a','B','a','n','d','u','n','g' ]
*Data dibaca sequensial: "Jakarta" = offset[0:7], "Surabaya" = offset[7:15], "Bandung" = offset[15:22]
*100% Cache Friendly, Vectorized, SIMD-Compatible!
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Memverifikasi Arrow Backend vs NumPy
Kode ini mendemonstrasikan perbedaan tipe data internal dan efisiensi alokasi memori antara backend bawaan Pandas 1.x (NumPy) dan backend Arrow pada Pandas 2.x.

```python
import pandas as pd
import pyarrow as pa

# 1. Dataset sederhana dengan Nullable Data
raw_data = {
    "transaction_id": [1001, 1002, None, 1004],
    "merchant_city": ["Jakarta", "Surabaya", "Medan", None],
    "amount": [250000.50, 75000.00, 120000.00, 450000.75]
}

# 2. DataFrame Tradisional (NumPy Engine)
df_numpy = pd.DataFrame(raw_data)

# 3. DataFrame Modern (Arrow Engine)
df_arrow = pd.DataFrame(raw_data).convert_dtypes(dtype_backend="pyarrow")

print("=== NUMPY BACKEND TYPES & MISSING VALUE BEHAVIOR ===")
print(df_numpy.dtypes)
print(f"Transaction ID dtype: {df_numpy['transaction_id'].dtype}") 
# Catatan: Kolom integer otomatis berubah menjadi float64 karena adanya None/NaN

print("\n=== ARROW BACKEND TYPES & MISSING VALUE BEHAVIOR ===")
print(df_arrow.dtypes)
print(f"Transaction ID dtype: {df_arrow['transaction_id'].dtype}")
# Catatan: Tetap int64[pyarrow] dengan validitas bitmask terisolasi
```

### 7.2 Practical Example: Enterprise Modern Wrangling Pipeline
Contoh arsitektur pipa data produksi dengan method chaining, skema defensif, optimasi kamus, dan logging performa memori.

```python
import sys
import time
import logging
from typing import Dict, Any
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class EnterpriseDataPipeline:
    def __init__(self, target_schema: Dict[str, Any]):
        self.target_schema = target_schema

    def log_memory_footprint(self, df: pd.DataFrame, stage_name: str) -> None:
        total_bytes = df.memory_usage(deep=True).sum()
        mb = total_bytes / (1024 * 1024)
        logging.info(f"[{stage_name}] Baris: {len(df):,} | Alokasi Memori: {mb:.2f} MB")

    def extract_from_csv(self, file_path: str) -> pd.DataFrame:
        logging.info(f"Membaca data secara native dengan pyarrow engine dari: {file_path}")
        # Membaca dengan zero-overhead pyarrow engine dan instansiasi langsung ke Arrow types
        df = pd.read_csv(
            file_path,
            engine="pyarrow",
            dtype_backend="pyarrow"
        )
        return df

    def transform_pipeline(self, df: pd.DataFrame) -> pd.DataFrame:
        """Eksekusi alur manipulasi data murni dengan method chaining, 
        menjaga zero-mutation, zero-redundant copy."""
        return (
            df
            # Tahap 1: Standardisasi Nama Kolom & Penghapusan Whitespace
            .rename(columns=lambda col: col.strip().lower())
            
            # Tahap 2: Defensif Filtering via Vectorized Predicate
            .query("status.isin(['COMPLETED', 'SETTLED']) and amount > 0.0")
            
            # Tahap 3: Pembuatan Kolom Terhitung & Arrow Dictionary Encoding
            .assign(
                # Cast status ke Dictionary Arrow (Sangat hemat memori untuk kardinalitas rendah)
                status=lambda d: d["status"].astype("category").astype("string[pyarrow]"),
                # Konversi waktu secara presisi tanpa loop
                timestamp=lambda d: pd.to_datetime(d["timestamp"], format="ISO8601", utc=True).astype("timestamp[us, tz=UTC][pyarrow]"),
                # Komputasi pajak flat 11% secara tervaktorisasi
                tax_amount=lambda d: d["amount"] * 0.11,
                # Normalisasi string kota: lowercase + replace
                merchant_city=lambda d: d["merchant_city"].str.strip().str.title()
            )
            
            # Tahap 4: Penanganan Missing Values secara deterministik
            .assign(
                merchant_city=lambda d: d["merchant_city"].fillna("Unknown")
            )
            
            # Tahap 5: Sorting berbasis indeks native C++ Arrow
            .sort_values(by="timestamp", ascending=False)
            .reset_index(drop=True)
        )

    def validate_schema(self, df: pd.DataFrame) -> None:
        """Validasi ketat skema runtime terhadap target_schema."""
        for col, expected_type in self.target_schema.items():
            if col not in df.columns:
                raise KeyError(f"Skema Invalid: Kolom '{col}' tidak ditemukan.")
            actual_type = str(df[col].dtype)
            if expected_type not in actual_type:
                raise TypeError(
                    f"Skema Mismatch pada kolom '{col}': Ekspektasi {expected_type}, "
                    f"Diterima: {actual_type}"
                )
        logging.info("Validasi skema berhasil: Seluruh tipe data sesuai kontrak.")

# --- Simulasi Eksekusi Pipeline Produksi ---
if __name__ == "__main__":
    # Generate Mock Production CSV Data
    csv_path = "/tmp/enterprise_transactions_sample.csv"
    mock_payload = (
        "transaction_id,timestamp,status,amount,merchant_city\n"
        "TX-001,2024-03-29T10:00:00Z,COMPLETED,150000.0,JAKARTA\n"
        "TX-002,2024-03-29T10:05:00Z,FAILED,20000.0,SURABAYA\n"
        "TX-003,2024-03-29T10:10:00Z,SETTLED,1200000.0,BANDUNG\n"
        "TX-004,2024-03-29T10:15:00Z,COMPLETED,50000.0,JAKARTA\n"
        "TX-005,2024-03-29T10:20:00Z,SETTLED,750000.0,\n"
    )
    with open(csv_path, "w") as f:
        f.write(mock_payload)

    contract = {
        "transaction_id": "string",
        "timestamp": "timestamp",
        "status": "string",
        "amount": "double",
        "tax_amount": "double",
        "merchant_city": "string"
    }

    pipeline = EnterpriseDataPipeline(target_schema=contract)
    
    start_time = time.perf_counter()
    raw_df = pipeline.extract_from_csv(csv_path)
    pipeline.log_memory_footprint(raw_df, "Raw Extraction")

    processed_df = pipeline.transform_pipeline(raw_df)
    pipeline.validate_schema(processed_df)
    pipeline.log_memory_footprint(processed_df, "Post Transformation")
    
    elapsed = time.perf_counter() - start_time
    logging.info(f"Pipeline selesai dalam {elapsed:.4f} detik.")
    print(processed_df)
```

---

## 8. Real World Case Study: High-Throughput Reconciliation System

### 8.1 Latar Belakang Masalah
Sebuah platform gateway pembayaran memproses 20.000.000 transaksi per hari. Sistem rekonsiliasi harian berjalan menggunakan instance virtual machine `c5.2xlarge` (8 vCPU, 16 GB RAM). 

**Masalah**: Pipeline rekonsiliasi warisan (*legacy*) berbasis Pandas 1.4 + NumPy sering mengalami `OutOfMemory (OOM) Killer` dari kernel Linux ketika memuat dump data transaksi harian (file CSV berukuran ~4.8 GB). Konversi teks mentah menjadi pointer objek Python membengkakkan konsumsi memori menjadi lebih dari 22 GB RAM ($>4.5\times$ dari ukuran disk).

### 8.2 Solusi Arsitektur
Pipeline direkayasa ulang dengan arsitektur:
1. **PyArrow Chunked Multi-File Reader**: Membaca data menggunakan streaming chunking tanpa memuat seluruh file ke memori sekaligus jika melebihi batas threshold, atau memanfaatkan format Parquet dengan kompresi ZSTD.
2. **Arrow String & Dictionary Backend**: Kolom berulang seperti `payment_method`, `currency`, dan `response_code` di-encode sebagai `dictionary[pyarrow]`. Kolom string bebas menggunakan `string[pyarrow]`.
3. **Partitioned In-Memory Join**: Rekonsiliasi antara log internal dan log mitra eksternal dilakukan berbasis hash bucket menggunakan Arrow memory-native join.

```
+---------------------------------------------------------------------------------------------------+
| PIPELINE SEBELUMNYA (Pandas 1.x - OOM):                                                           |
| CSV (4.8 GB) ──> Python Heap Ingestion ──> PyObject Pointers Allocation (~22.5 GB RAM) ──> CRASH  |
+---------------------------------------------------------------------------------------------------+
| PIPELINE MODERN (Pandas 2.x + Apache Arrow):                                                      |
| Parquet (1.1 GB ZSTD) ──> PyArrow Stream ──> Arrow Contiguous Buffer (~3.2 GB RAM) ──> SUCCESS   |
| (Eksekusi 5.2x Lebih Cepat, Memory Footprint Turun 85%, Cloud Compute Cost Turun 65%)             |
+---------------------------------------------------------------------------------------------------+
```

### 8.3 Implementasi Produksi

```python
import os
import psutil
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

def print_rss_memory(stage: str):
    process = psutil.Process(os.getpid())
    rss_mb = process.memory_info().rss / (1024 * 1024)
    print(f"[Resource Profiler] {stage} -> RSS Memory: {rss_mb:.2f} MB")

def run_reconciliation_pipeline(internal_file: str, partner_file: str) -> pd.DataFrame:
    print_rss_memory("Start Pipeline")

    # 1. Pembacaan Teroptimasi dengan Skema Eksplisit Arrow Engine
    internal_df = pd.read_parquet(
        internal_file,
        engine="pyarrow",
        dtype_backend="pyarrow",
        columns=["transaction_ref", "amount", "currency", "recon_status"]
    )
    print_rss_memory("Internal Data Loaded")

    partner_df = pd.read_parquet(
        partner_file,
        engine="pyarrow",
        dtype_backend="pyarrow",
        columns=["partner_ref", "settled_amount", "settled_currency"]
    )
    print_rss_memory("Partner Data Loaded")

    # 2. Vectorized Reconciliation via Chaining
    recon_result = (
        internal_df
        .merge(
            partner_df,
            left_on="transaction_ref",
            right_on="partner_ref",
            how="outer"
        )
        .assign(
            # Logika komparasi tervektorisasi murni (C++ Arrow execution)
            discrepancy_amount=lambda d: (d["amount"] - d["settled_amount"]).abs(),
            is_matched=lambda d: (
                (d["transaction_ref"].notna()) & 
                (d["partner_ref"].notna()) & 
                (d["discrepancy_amount"] < 0.01)
            ),
            resolution_action=lambda d: pc.case_when(
                pc.build_boolean_mask(
                    d["is_matched"] == True,
                    (d["transaction_ref"].isna()) & (d["partner_ref"].notna()),
                    (d["transaction_ref"].notna()) & (d["partner_ref"].isna())
                ),
                "NO_ACTION",
                "INVESTIGATE_MISSING_INTERNAL",
                "INVESTIGATE_MISSING_PARTNER",
                "DISCREPANCY_FLAG"
            ).to_pandas().astype("string[pyarrow]")
        )
    )
    print_rss_memory("Post-Reconciliation Processing")

    return recon_result
```

---

## 9. Trade-offs

Implementasi Pandas 2.x dengan Apache Arrow backend menghadirkan trade-off struktural yang harus dipertimbangkan:

| Aspek | Pandas 2.x (Arrow Backend) | Pandas Legacy (NumPy Backend) | Parameter Pertimbangan Rekayasa |
| :--- | :--- | :--- | :--- |
| **Throughput String** | **Sangat Cepat**: Operasi regex, split, substring hingga 10x-30x lebih cepat melalui Arrow C++ Compute Functions. | **Lambat**: Loop tingkat Python pada array pointer dereferencing. | Wajib menggunakan Arrow jika pipeline memproses banyak data teks (NLP preprocessing, log parsing). |
| **Ekosistem Library Eksternal** | **Terbatas**: Sebagian pustaka machine learning legacy (misal: Scikit-learn versi lama atau custom Cython) mengharapkan array NumPy C-contiguous float. | **Sangat Matang**: Standar *de facto* integrasi dengan SciPy, Statsmodels, dan model eksternal. | Memerlukan `.to_numpy()` konversi eksplisit pada layer feeding model ML, yang menimbulkan biaya alokasi memori sementara. |
| **Kompleksitas Mutasi (In-Place)** | **Ketat**: Arrow memori secara desain bersifat **immutable**. Mutasi in-place tidak dianjurkan dan sering memicu defensive copy tersembunyi. | **Longgar**: Array NumPy dapat dimutasi *in-place* secara langsung di tingkat memori. | Tim engineering harus bergeser dari pola prosedural imperatif ke pola fungsional declarative *method chaining*. |
| **Cold-Start Deserialization** | **Nol / Sangat Rendah**: Direct buffer mapping via Arrow IPC atau Parquet format. | **Tinggi**: Re-parsing serialisasi string per elemen. | Menguntungkan arsitektur serverless (AWS Lambda, Cloud Run) yang sensitif terhadap cold-start latency. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Anti-Pattern 1: Mengabaikan Default Backend Saat Membaca Data
* **Symptom**: Penggunaan `pd.read_csv("large_data.csv")` pada Pandas 2.x tetap mengakibatkan OOM.
* **Root Cause**: Meskipun Pandas versi 2.x terpasang, pemanggilan `pd.read_csv()` secara default masih menggunakan backend `numpy_nullable` atau *legacy* NumPy engine demi backward compatibility.
* **Remediasi**: Selalu eksplisit mendefinisikan backend:
  ```python
  # SALAH (Masih menggunakan pointer NumPy)
  df = pd.read_csv("large_data.csv")

  # BENAR (Menggunakan engine & backend native Arrow)
  df = pd.read_csv("large_data.csv", engine="pyarrow", dtype_backend="pyarrow")
  ```

### 10.2 Anti-Pattern 2: Menggunakan Loop Python Mengakses Row (`iterrows` / `itertuples`)
* **Symptom**: Degradasi performa parah ($>100\times$ lebih lambat) saat melakukan manipulasi string.
* **Root Cause**: Iterasi baris per baris memaksa konversi elemen Arrow C++ menjadi objek skalar Python pada setiap siklus loop, meniadakan manfaat vektorisasi cache CPU.
* **Remediasi**: Gunakan `.str` accessor bawaan yang langsung terhubung ke C++ compute kernel, atau gunakan `pyarrow.compute`:
  ```python
  # SALAH (Iterasi Python Lambat)
  for idx, row in df.iterrows():
      df.at[idx, "clean_code"] = row["raw_code"].strip().upper()

  # BENAR (Vectorized Arrow C++)
  df["clean_code"] = df["raw_code"].str.strip().str.upper()
  ```

### 10.3 Anti-Pattern 3: Involuntarily Downcasting ke NumPy
* **Symptom**: Tiba-tiba konsumsi RAM melonjak di tengah-tengah alur data pipeline.
* **Root Cause**: Menggunakan fungsi pustaka pihak ketiga yang tidak mendukung extension array, sehingga Pandas secara implisit mengonversi seluruh DataFrame menjadi NumPy `object`.
* **Diagnosis**:
  ```python
  # Cek apakah ada kolom yang bermutasi kembali ke numpy object:
  leaked_columns = [col for col in df.columns if df[col].dtype == "object"]
  if leaked_columns:
      raise RuntimeError(f"Memory leak detected! Kolom kembali ke Object: {leaked_columns}")
  ```

### 10.4 Anti-Pattern 4: Silent Memory Spike pada Operasi GroupBy String Berulang
* **Symptom**: Lonjakan memori masif saat melakukan `.groupby()` pada kolom berfrekuensi tinggi.
* **Remediasi**: Ubah string tersebut menjadi dictionary encoding sebelum agregasi:
  ```python
  # Mengurangi memory overhead hash table groupby
  df["merchant_id"] = df["merchant_id"].astype("category") # Native Arrow dictionary representation
  result = df.groupby("merchant_id")["amount"].sum()
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan checklist arsitektur ini sebelum mendistribusikan pipeline Pandas 2.x ke production:

```markdown
[ ] Engine Definition:
    - [ ] Semua I/O read (CSV, JSON, Parquet) menyertakan `dtype_backend="pyarrow"`.
    - [ ] `engine="pyarrow"` dipasang eksplisit pada parser yang mendukung.

[ ] Memory Layout & Types:
    - [ ] Tidak ada tipe data bertipe `object` pada `df.dtypes`.
    - [ ] Kolom teks dengan kardinalitas < 10% dari total baris dikonversi ke dictionary / categorical type.
    - [ ] Timestamp memiliki timezone explicit (UTC) dan resolusi mikrodetik (`[us]`).

[ ] Functional Immutability:
    - [ ] Tidak ada penggunaan `inplace=True` di seluruh basis kode.
    - [ ] Transformasi menerapkan method chaining terstruktur (`.assign()`, `.query()`, `.pipe()`).

[ ] Serialization:
    - [ ] Format penyimpanan jangka menengah/panjang menggunakan Parquet dengan kompresi Snappy atau ZSTD.
    - [ ] Aliran antarmuka IPC/Microservices menggunakan Arrow IPC Stream Format (`.feather` atau Arrow Stream Record Batches).

[ ] Defensive Testing:
    - [ ] Terdapat modul assertion validasi tipe data pasca-ingestion.
    - [ ] Uji coba memory profiling (RSS) dijalankan di CI/CD pipeline menggunakan batas threshold toleransi maksimal.
```

---

## 12. Hands-on Practice

Buatlah berkas implementasi mandiri pada path direktori: `hands-on/m02/production_wrangling.py`. Ikuti seluruh fase instruksi di bawah ini tanpa memotong logika program.

### Langkah 1: Struktur Direktori & Dependensi
Pastikan struktur direktori lokal Anda telah siap:
```bash
mkdir -p hands-on/m02/data
cd hands-on/m02/
```

### Langkah 2: Implementasi Skrip Produksi Lengkap
Simpan kode berikut sebagai `hands-on/m02/production_wrangling.py`:

```python
"""
Path: hands-on/m02/production_wrangling.py
Deskripsi: Pipeline ETL Modern Pandas 2.x dengan Apache Arrow Native Backend
"""

import os
import sys
import time
import psutil
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

DATA_DIR = "hands-on/m02/data"
SOURCE_CSV = os.path.join(DATA_DIR, "telemetry_logs.csv")
TARGET_PARQUET = os.path.join(DATA_DIR, "telemetry_analytics.parquet")

def generate_telemetry_dataset(file_path: str, rows: int = 500_000) -> None:
    """Membuat synthetic production telemetry dataset berukuran masif."""
    print(f"[*] Menghasilkan {rows:,} baris mock data ke {file_path}...")
    import numpy as np
    
    np.random.seed(42)
    device_ids = [f"DEV-{i:04d}" for i in range(1, 101)]
    statuses = ["HEALTHY", "WARNING", "CRITICAL", None]
    
    df_gen = pd.DataFrame({
        "event_id": [f"EVT-{i}" for i in range(rows)],
        "device_id": np.random.choice(device_ids, rows),
        "status": np.random.choice(statuses, rows, p=[0.7, 0.2, 0.05, 0.05]),
        "cpu_utilization": np.random.uniform(5.0, 99.9, rows),
        "payload_bytes": np.random.randint(100, 1048576, rows),
        "timestamp": pd.date_range("2024-01-01", periods=rows, freq="ms").astype(str)
    })
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    df_gen.to_csv(file_path, index=False)
    print(f"[✓] File mock data berhasil dibuat. Ukuran: {os.path.getsize(file_path) / (1024*1024):.2f} MB")

def get_process_memory() -> float:
    """Mengembalikan resident set size memory proses saat ini dalam MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def execute_pipeline() -> None:
    print("\n--- MEMULAI ENTERPRISE WRANGLING PIPELINE (PANDAS 2.X + ARROW) ---")
    mem_init = get_process_memory()
    start_time = time.perf_counter()

    # 1. READ dengan Zero-Overhead Configuration
    print(f"[1] Membaca data dengan pyarrow engine...")
    df_raw = pd.read_csv(
        SOURCE_CSV,
        engine="pyarrow",
        dtype_backend="pyarrow"
    )
    mem_after_read = get_process_memory()
    print(f"    Memory Baseline: {mem_init:.2f} MB | After Read: {mem_after_read:.2f} MB")
    print(f"    Schema Tipe Data Awal:\n{df_raw.dtypes}\n")

    # 2. TRANSFORM via Functional Method Chaining
    print("[2] Menjalankan transformasi tervektorisasi...")
    df_transformed = (
        df_raw
        # Filter anomaly dan null record
        .dropna(subset=["status", "device_id"])
        .query("cpu_utilization > 50.0")
        
        # Manipulasi kolom terhitung & Arrow Encoding
        .assign(
            # Ubah string ID & Status ke Dictionary Arrow untuk efisiensi ruang
            device_id=lambda d: d["device_id"].astype("category"),
            status=lambda d: d["status"].astype("category"),
            
            # Parsing Timestamp dengan Arrow Native Resolver
            timestamp=lambda d: pd.to_datetime(d["timestamp"], utc=True).astype("timestamp[us, tz=UTC][pyarrow]"),
            
            # Hitung payload dalam Megabyte
            payload_mb=lambda d: d["payload_bytes"] / (1024.0 * 1024.0),
            
            # Kategori beban kerja dengan ekspresi kondisi
            workload_class=lambda d: pd.Series(
                pd.NA, index=d.index, dtype="string[pyarrow]"
            ).mask(d["cpu_utilization"] >= 85.0, "HEAVY")
             .mask((d["cpu_utilization"] < 85.0) & (d["cpu_utilization"] >= 50.0), "MODERATE")
        )
        
        # Sort data berbasis timestamp descending
        .sort_values(by="timestamp", ascending=False)
        .reset_index(drop=True)
    )
    mem_after_transform = get_process_memory()
    print(f"    After Transform Memory: {mem_after_transform:.2f} MB")

    # 3. RUNTIME CONTRACT ASSERTION
    print("[3] Memverifikasi data contract...")
    assert df_transformed["device_id"].dtype.name == "category"
    assert "timestamp[us, tz=UTC]" in str(df_transformed["timestamp"].dtype)
    assert df_transformed["payload_mb"].isna().sum() == 0
    print("    [✓] Kontrak Skema Terpenuhi.")

    # 4. EGRESS WRITE TO PARQUET (ZSTD COMPRESSION)
    print(f"[4] Menyimpan artefak analitik ke {TARGET_PARQUET}...")
    df_transformed.to_parquet(
        TARGET_PARQUET,
        engine="pyarrow",
        compression="zstd",
        index=False
    )
    
    total_time = time.perf_counter() - start_time
    parquet_size_mb = os.path.getsize(TARGET_PARQUET) / (1024 * 1024)
    csv_size_mb = os.path.getsize(SOURCE_CSV) / (1024 * 1024)
    
    print("\n--- RINGKASAN METRIK PERFORMA ---")
    print(f"Total Waktu Eksekusi   : {total_time:.2f} detik")
    print(f"Input CSV Size         : {csv_size_mb:.2f} MB")
    print(f"Output Parquet Size    : {parquet_size_mb:.2f} MB")
    print(f"Kompresi Disk Storage  : {((1 - (parquet_size_mb / csv_size_mb)) * 100):.2f}% efisiensi")
    print(f"Peak RSS Memory        : {mem_after_transform:.2f} MB")
    print("----------------------------------------------------------------\n")

if __name__ == "__main__":
    generate_telemetry_dataset(SOURCE_CSV, rows=500_000)
    execute_pipeline()
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan file praktikum dari terminal:
```bash
python hands-on/m02/production_wrangling.py
```

---

## 13. Exercise

### Latihan 1 (Level: Easy)
Ubah pembacaan konfigurasi berikut agar secara penuh menggunakan Arrow Backend dan pastikan kolom teks tidak beralih ke `object`.
* **Input**: File JSON flat berisi kolom `username`, `signup_ip`, dan `login_count`.
* **Acceptance Criteria**:
  1. `df["username"].dtype` wajib bertipe `string[pyarrow]`.
  2. Tidak ada tipe `np.float64` yang dihasilkan jika `login_count` memiliki nilai null (harus `int64[pyarrow]`).

### Latihan 2 (Level: Medium)
Buat fungsi transformasi data `clean_financial_ledger(df: pd.DataFrame) -> pd.DataFrame` yang melakukan sanitasi tanpa membuat memory copy:
* **Tugas**:
  1. Parsing kolom string moneter format mata uang (misal: `"$ 1,250,400.50"`) menjadi numeric Arrow double (`float64[pyarrow]`) menggunakan Arrow string accessor tanpa pemanggilan `.apply(lambda x: ...)`.
  2. Konversi kolom string kode cabang (`branch_code`) menjadi `dictionary[pyarrow]`.
* **Acceptance Criteria**:
  1. Execution time untuk 1.000.000 baris harus selesai di bawah 1.5 detik pada spesifikasi standar 4-core machine.
  2. Zero-object allocation: `assert len([d for d in df.dtypes if d == 'object']) == 0`.

### Latihan 3 (Level: Hard)
Rancang arsitektur pipeline streaming rekonsiliasi berbasis partisi Arrow Table:
* **Tugas**:
  1. Buat class `ChunkedParquetReconciler` yang membaca file Parquet masif berukuran puluhan gigabyte secara streaming (batch per batch) menggunakan `pyarrow.parquet.ParquetFile.iter_batches()`.
  2. Bungkus tiap RecordBatch menjadi Pandas DataFrame Arrow backend tanpa mengonversi memory buffer ke NumPy.
  3. Lakukan agregasi running-total terhadap kolom `revenue` berdasarkan `region` secara streaming tanpa menampung seluruh dataset di RAM.
* **Acceptance Criteria**:
  1. Konsumsi RSS Memory maksimum selama pemrosesan tidak boleh melampaui 512 MB, terlepas dari ukuran dataset input (uji dengan file sintesis 5 GB).
  2. Mengembalikan artefak ringkasan final dalam format dictionary yang terverifikasi presisi agregasinya.

---

## 14. Challenge

### Studi Kasus: Telemetry Out-of-Core Sliding-Window Anomaly Ingestion
Platform Internet of Things (IoT) otomotif Anda menerima streaming telemetry berukuran **25 GB per jam** dalam ratusan file format CSV terkompresi GZIP. Mesin pemrosesan worker container Anda dibatasi oleh konfigurasi Kubernetes Resource Limit: **RAM maksimal 4.0 GB dan 2 CPU Core**.

**Target Rekayasa**:
1. Rancang modul pipeline Python utuh yang memproses data telemetry log berukuran 25 GB tersebut tanpa memicu status Kubernetes pod `OOMKilled` (Exit Code 137).
2. Terapkan algoritma pendeteksi lonjakan temperatur mesin (*Engine Overheating Anomaly*):
   * Anomali didefinisikan jika dalam rolling interval waktu 5 menit, median temperatur mesin melebihi 105 derajat Celcius dan deviasi standar pembacaan sensor mendekati 0 (sensor macet).
3. Pipeline wajib melakukan normalisasi string model armada (*fleet model*), deduplikasi duplikat event berbasis `event_id`, dan serialisasi keluaran anomali ke file Parquet terpartisi berbasis direktori tanggal (`/year=YYYY/month=MM/day=DD/`).

**Larangan Keras**:
* Dilarang menggunakan platform cluster eksternal terdistribusi seperti Apache Spark atau Dask (seluruh arsitektur harus murni dijalankan pada instance Python runtime tunggal berbasis Pandas 2.x, PyArrow, dan standar pustaka OS/multiprocessing).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (5 Soal)

**Q1: Apa perbedaan mendasar antara representasi string bawaan NumPy (`object`) dan Apache Arrow (`string[pyarrow]`) di dalam memori?**
* A. NumPy menyimpan string sebagai UTF-8 kontigu, Arrow menyimpannya sebagai array pointer dereference.
* B. NumPy menyimpan string sebagai pointer `PyObject*` di heap memori Python yang terfragmentasi, sedangkan Arrow menyimpannya dalam flat contiguous bytes buffer disertai validity bitmap dan offsets buffer.
* C. NumPy secara native mendukung integer bitmask nullability, Arrow mengonversi missing value ke float NaN.
* D. Tidak ada perbedaan arsitektural; PyArrow string hanyalah alias penamaan untuk efisiensi sintaks Pandas.

**Q2: Mengapa pada Pandas legacy (<2.0), kolom integer yang memiliki satu nilai `NaN` secara otomatis berubah tipe data menjadi `float64`?**
* A. Karena representasi array C bawaan NumPy untuk integer tidak memiliki representasi native bit untuk nilai NULL/missing tanpa memodifikasi representasi bit nilai integer itu sendiri.
* B. Karena Pandas menghemat alokasi ukuran byte di memori dengan menggunakan float.
* C. Hal tersebut merupakan bug pada versi CPython 3.8 yang belum teratasi.
* D. Karena NumPy BlockManager melarang keberadaan tipe integer jika tabel memiliki indeks bertipe datetime.

**Q3: Parameter apa yang wajib disertakan pada method `pd.read_csv()` di Pandas 2.x agar seluruh tipe data keluaran otomatis menggunakan tipe data native Apache Arrow?**
* A. `engine="c"`
* B. `dtype_backend="pyarrow"`
* C. `use_arrow_types=True`
* D. `experimental_arrow=True`

**Q4: Apa karakteristik utama sifat alokasi memori dari Apache Arrow format?**
* A. Memori bersifat mutable dan thread-unsafe.
* B. Seluruh data disimpan dalam struktur circular linked list di heap.
* C. Memori bersifat immutable (tidak dapat diubah langsung in-place), columnar, dan cache-friendly.
* D. Setiap sel baris dialokasikan terpisah bersama metadata skema di L1 CPU cache.

**Q5: Manakah format penyimpanan serialisasi disk berikut yang memiliki integrasi zero-copy atau paling minim biaya deserialisasi (*lowest CPU serde overhead*) saat dibaca ke Pandas 2.x dengan Arrow backend?**
* A. JSON Lines
* B. BZIP2 Compressed CSV
* C. Apache Feather (Arrow IPC File Format)
* D. SQLite3 Table

---

### 15.2 Pertanyaan Intermediate (5 Soal)

**Q6: Bagaimana mekanisme operasi slicing `df.iloc[100:200]` bekerja pada Pandas DataFrame yang didukung oleh Apache Arrow backend?**
* A. Pandas menduplikasi 100 baris memori data tersebut ke blok RAM yang baru.
* B. Arrow membuat view baru (slice) dengan mengatur ulang referensi pointer offset awal dan panjang baris tanpa menyalin buffer byte aslinya (*Zero-Copy operation*).
* C. Sistem operasi kernel melakukan disk swapping sementara sebelum slice dibaca oleh CPython.
* D. Arrow mengonversi 100 baris tersebut menjadi Python Dictionary di heap.

**Q7: Kapan representasi `dictionary[pyarrow]` sebaiknya digunakan menggantikan `string[pyarrow]` biasa?**
* A. Hanya jika seluruh teks memiliki panjang karakter yang seragam.
* B. Saat kolom string memiliki kardinalitas rendah (*low-cardinality*), yaitu nilai string yang berulang-ulang, untuk memangkas duplikasi data byte dan mempercepat operasi join/groupby.
* C. Saat data string akan diekspor ke format format XML.
* D. Saat kolom string tersebut sering dikenakan operasi regex parsing yang kompleks.

**Q8: Pada arsitektur transformasi data Pandas modern, mengapa penggunaan `inplace=True` sangat tidak dianjurkan (*deprecated practice*)?**
* A. Karena `inplace=True` selalu menghapus indeks utama secara acak.
* B. Karena `inplace=True` tidak menjamin mutasi memori terjadi *in-place* sesungguhnya di layer C++, sering kali menciptakan salinan memori defensif (*hidden defensive copies*), serta merusak keterbacaan method chaining.
* C. Karena fungsi tersebut memicu memory leak permanen pada Garbage Collector Linux.
* D. Karena `inplace=True` hanya kompatibel dengan arsitektur GPU CUDA.

**Q9: Jika Anda menjalankan fungsi Python berikut pada DataFrame bervolume 10 juta baris: `df['amount'].apply(lambda x: x * 1.11)`, mengapa pendekatan ini dianggap sebagai anti-pattern kritis di lingkungan produksi?**
* A. Karena fungsi lambda memicu serialisasi string pada nilai numerik.
* B. Karena `.apply()` dengan lambda keluar dari runtime Arrow C++ berkecepatan tinggi dan memaksa eksekusi kembali ke interpreter Python loop baris per baris yang lambat serta membebani alokasi wrapper skalar Python.
* C. Karena lambda mengabaikan pengaturan timezone pada kolom.
* D. Karena ekspresi float multiplication dilarang pada skema Arrow.

**Q10: Manakah strategi yang paling optimal untuk menangani agregasi data berukuran 50 GB pada mesin lokal dengan kapasitas RAM hanya 8 GB menggunakan kombinasi Pandas 2.x dan PyArrow?**
* A. Membaca seluruh file CSV sekaligus menggunakan `dtype_backend="pyarrow"`.
* B. Mengonfigurasi Virtual Memory Linux Swap hingga 100 GB dan mengeksekusi pipeline standar.
* C. Mengonversi data ke format Parquet, lalu membaca secara streaming batch-by-batch (*RecordBatch chunking*) menggunakan `iter_batches()` dari PyArrow untuk agregasi parsial akumulatif.
* D. Menggunakan multi-threading `ThreadPoolExecutor` untuk memuat CSV secara paralel ke satu DataFrame yang sama.

---

### 15.3 Skenario Kasus Produksi (3 Soal)

**Q11: Skenario Crash Debugging pada Microservice Extraction**  
Sebuah microservice analitik berbasis FastAPI mengekstraksi data log dari AWS S3. Setelah Anda meng-upgrade dependensi ke Pandas 2.2 dengan `dtype_backend="pyarrow"`, pod container Anda mengalami silent error: data hasil pemrosesan yang diteruskan ke pustaka Machine Learning warisan (*legacy cythonized model*) mengeluarkan error: `TypeError: Buffer has wrong number of dimensions (expected 1, got 0)` atau `ValueError: Array-like object not understood`.  
*Pertanyaan*: Apa penyebab arsitektural dari kegagalan ini dan bagaimana solusi perbaikannya tanpa menurunkan kembali (*downgrade*) versi Pandas?

**Q12: Skenario Latensi Tinggi pada Text Pipeline**  
Pipeline pemrosesan teks keluhan pelanggan membaca 5 juta baris string data. Tim engineer menggunakan Pandas 2.x tetapi mendapati operasi pembersihan teks (`.str.replace(...)`) berjalan lambat, memakan waktu hingga 12 menit dan menggunakan CPU 100% pada 1 core saja.  
*Pertanyaan*: Diagnosis apa yang paling mungkin terkait eksekusi komputasi teks tersebut, dan bagaimana transformasi arsitektural yang harus diterapkan agar seluruh vCPU core termanfaatkan secara optimal?

**Q13: Skenario Kebocoran Memori (Memory Fragmentation)**  
Sebuah daemon worker berjalan non-stop (24/7) untuk melakukan wrangling data tiap 10 menit menggunakan Pandas 2.x. Tim SRE mengamati grafik memori (RSS) worker tersebut tidak pernah turun, melainkan terus meningkat secara linear (*creeping memory growth*) hingga container terbunuh oleh OOM Killer setiap 48 jam sekali, meskipun perintah `del df` dan `gc.collect()` telah dipanggil di akhir tiap iterasi pemrosesan.  
*Pertanyaan*: Jelaskan fenomena alokator memori C (misal: glibc `malloc`) yang menyebabkan memori tidak dikembalikan ke sistem operasi, dan bagaimana arsitektur penanganannya pada level runtime Python/OS?

---

### Kunci Jawaban & Pembahasan Quiz

#### Kunci Soal Basic
1. **B** — Arrow memisahkan buffer data bytes UTF-8 kontigu dari offset indeks dan bitmap nullability, sedangkan NumPy menyimpannya sebagai array pointer C yang merujuk ke lokasi heap acak objek string Python.
2. **A** — Array integer murni pada NumPy tidak memiliki representasi sentinel untuk status NA/Null. Untuk mengakomodasi keberadaan missing value (`np.nan` yang bertipe IEEE floating-point), NumPy terpaksa mendowncast seluruh kolom menjadi `float64`.
3. **B** — Parameter `dtype_backend="pyarrow"` memerintahkan engine pembacaan Pandas 2.x untuk langsung membungkus kolom ke dalam tipe data `ArrowExtensionArray`.
4. **C** — Tata letak memori Apache Arrow mengedepankan sifat immutable, columnar, dan kontigu agar dapat dibaca langsung oleh instruksi SIMD prosesor modern tanpa deserialisasi.
5. **C** — Format Apache Feather adalah implementasi disk persisten dari Apache Arrow IPC format, sehingga pembacaannya bersifat memory-mappable mendekati zero CPU deserialization.

#### Kunci Soal Intermediate
6. **B** — Slicing pada Arrow backend adalah operasi O(1) yang hanya membuat wrapper baru (*slice descriptor*) dengan mengatur offset awal dan batas buffer tanpa menduplikasi data alokasi byte fisik.
7. **B** — `dictionary[pyarrow]` memetakan entri berulang ke array integer token dan menyimpan tabel lookup teks tunggal, mereduksi footprint memori secara dramatis pada kolom kategori/kardinalitas rendah.
8. **B** — Di balik layar, operasi `inplace=True` sering kali membuat deep copy baru lalu memindahkan pointer referensi internal, sehingga tidak memberikan garansi optimasi memori dan justru merusak fungsionalitas deklaratif method chaining.
9. **B** — Fungsi `.apply()` dengan lambda mentransfer kontrol eksekusi dari C++ Arrow/Vectorized kernel kembali ke Python Virtual Machine interpreter untuk setiap baris data secara individual ($O(N)$ inter-op context switching), menghancurkan throughput pemrosesan.
10. **C** — Teknik chunking out-of-core menggunakan `iter_batches()` pada PyArrow membaca data sebesar ukuran batch yang dapat dimuat oleh kapasitas RAM, mengeksekusi agregasi parsial, membuang batch dari memori, dan mengakumulasikan hasil akhir secara streaming.

#### Pembahasan Skenario Kasus Produksi
11. **Pembahasan Skenario 11**:  
    * *Penyebab*: Modul ML legacy tersebut mengharapkan memori buffer C-contiguous 1D/2D array mentah khas NumPy (`np.ndarray`), namun Pandas meneruskan `ArrowExtensionArray`. Meskipun kompatibel di level interface, representasi buffer internal keduanya berbeda.  
    * *Solusi*: Terapkan adapter layer sebelum data dialirkan ke model prediksi: eksplisit panggil `.to_numpy(dtype=np.float32)` hanya pada array fitur/fitur matriks target inferensi, memastikan transisi tipe data terjadi secara terkontrol tanpa mengubah keseluruhan pipeline ingestion Arrow.
12. **Pembahasan Skenario 12**:  
    * *Penyebab*: Meskipun Arrow menyediakan vectorized string kernels, operasi `.str.replace()` dengan regex engine kustom di Pandas dapat beralih secara implisit ke single-threaded evaluation jika regex tersebut tidak didukung secara natif oleh C++ compute functions PyArrow (PC).  
    * *Solusi*: Pastikan parameter `regex=False` jika hanya melakukan substring replacement biasa agar PyArrow native C++ kernel digunakan, atau gunakan modul `pyarrow.compute` secara langsung. Jika regex kompleks tetap diperlukan, partisi DataFrame menjadi N partisi logis dan manfaatkan multiprocessing worker (`concurrent.futures.ProcessPoolExecutor`) untuk memanfaatkan seluruh core CPU yang tersedia.
13. **Pembahasan Skenario 13**:  
    * *Penyebab*: Ini adalah problem klasik *Memory Fragmentation* pada alokator memori C runtime (`glibc malloc`). Ketika Pandas dan PyArrow mengalokasikan dan membebaskan jutaan buffer memori kecil secara terus-menerus, memori fisik (pages) terfragmentasi. Walaupun Python telah membebaskan objek (`gc.collect()`), alokator glibc menahan virtual memory pages tersebut dan tidak mengembalikannya (*unmap*) ke kernel OS karena puncak heap masih terisi sebagian fragmen kecil.  
    * *Solusi*: Ganti alokator sistem standar Linux glibc dengan alokator alternatif berperforma tinggi yang memiliki manajemen defragmentasi agresif, seperti **Jemalloc** (`LD_PRELOAD=/usr/lib/libjemalloc.so`) atau panggil secara manual `ctypes.CDLL('libc.so.6').malloc_trim(0)` pada akhir setiap siklus loop worker untuk memaksa alokator membersihkan fragmen dan mengembalikan heap memory ke OS.

---

## 16. Summary

1. **Paradigma Baru Pandas 2.x**: Pandas 2.x mendisrupsi ketergantungan eksklusif pada arsitektur internal NumPy `BlockManager` dengan mengintegrasikan Apache Arrow sebagai backend memori kelas satu (*first-class backend*).
2. **Keunggulan Arrow Backend**: Integrasi struktur memori Apache Arrow menuntaskan tiga masalah klasik data wrangling di Python: mengeliminasi mutasi tipe data akibat missing values via native bitmask nullability, memangkas overhead konsumsi RAM string hingga 80%, dan membuka kemampuan zero-copy inter-process communication.
3. **Pola Desain Produksi**: Arsitektur wrangling modern menuntut pergeseran dari paradigma imperatif berbasis manipulasi `inplace` dan loop lambat `.apply()` menuju fungsional deklaratif murni menggunakan **Method Chaining**, pemanfaatan **Arrow Compute Kernels**, skema typing defensif, serta optimalisasi kardinalitas berbasis **Dictionary Encoding**.
4. **Efisiensi Sistem**: Kombinasi Pandas 2.x, PyArrow I/O engine, dan penyimpanan terkompresi berbasis format Parquet/Feather menyajikan arsitektur analitik dengan performa tinggi, latensi deserialisasi rendah, serta konsumsi memori minimal yang siap diterapkan pada infrastruktur komputasi awan skala enterprise.