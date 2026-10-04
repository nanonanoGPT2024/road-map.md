# Bab 04 Module 01: Arsitektur Split-Apply-Combine: Deep-Dive Engine GroupBy, Reshaping, dan Window Processing Berperforma Tinggi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
* Menganalisis mekanisme internal engine *Split-Apply-Combine* pada Pandas, mencakup *hash-based grouping*, *factorization*, dan peran `BlockManager`/`ArrayManager`.
* Mengeliminasi *bottleneck* komputasi dengan mengganti eksekusi berbasis Python interpreter (`.apply()`) menggunakan vectorized aggregation, Cythonized primitives, dan engine Numba (`@jit`).
* Mengonfigurasi parameter grouping (`observed`, `sort`, `as_index`) untuk mencegah ledakan kombinatorik (*Cartesian explosion*) memori dan latensi alokasi.
* Merancang pipeline transformasi data berskala puluhan juta baris (*multi-million rows*) dengan konsumsi memori terprediksi dan efisiensi waktu linear $\mathcal{O}(N)$.

---

### 2. Prerequisite
* Penguasaan mendalam representasi memori NumPy: `ndarray`, *strides*, contiguous C vs. Fortran memory order, dan penanganan pointer data.
* Pemahaman arsitektur dasar Pandas Series dan DataFrame (Indeks, Blok tipe data, dan mekanisme *zero-copy view* vs *deep-copy*).
* Pemahaman dasar kompleksitas algoritma Big-O (khususnya amortized $\mathcal{O}(1)$ hash lookups vs $\mathcal{O}(N \log N)$ sorting).
* Familiaritas dengan profil performa Python (`cProfile`, memory_profiler, atau modul `line_profiler`).

---

### 3. Concept
Pondasi dari pengelompokan data berkinerja tinggi dalam Pandas bertumpu pada paradigma **Split-Apply-Combine**. Secara arsitektural, proses ini bukan pemisahan fisik DataFrame menjadi ribuan sub-DataFrame terisolasi, melainkan operasi berbasis pemetaan indeks yang sangat dioptimalkan:

```
[Input DataFrame]
       │
       ▼
[Factorization Engine] ──► Menghasilkan:
       │                   1. Array integer codes (0, 1, 2, ..., K-1)
       │                   2. Array unique categories
       ▼
[Grouping / Aggregation Kernel] (Cython / Numba / C)
       │
       ▼
[Reconstructed Result Blocks]
```

1. **Split via Factorization (Faktorisasi):**
   Alih-alih mempartisi memori, Pandas memanggil `factorize()` pada kolom kunci (*grouping keys*). Mesin algoritma membangun *hash table* untuk memetakan setiap nilai unik ke sebuah representasi integer *code* berukuran 64-bit/32-bit:
   $$\text{Keys} \rightarrow \text{Codes} \in [0, K-1], \quad K = \text{jumlah grup unik}$$
   Proses ini juga menghasilkan array `uniques` yang menyimpan nilai asli.

2. **Binning & Index Bucketing:**
   Pandas memanfaatkan representasi *code* ini untuk mengindeks komputasi agregasi ke dalam *bucket buffer* yang berdekatan di memori secara kontigu (*cache-friendly*), meminimalkan *cache misses* pada CPU L1/L2.

3. **Apply & Engine Dispatching:**
   Ketika fungsi dipanggil (`.mean()`, `.sum()`, dll.), Pandas melakukan *fast-path dispatch*:
   * **Fast-path (Cython Grouping):** Jika operasi berupa fungsi reduksi standar bawaan, kernel C/Cython langsung mengiterasi array primitif tanpa instansiasi objek Python.
   * **Numba Engine:** Jika flag `engine='numba'` diaktifkan, loop JIT-compiled dieksekusi langsung pada memory buffer NumPy yang mendasari.
   * **Slow-path (Python Object Fallback):** Jika menggunakan lambda atau fungsi kustom lewat `.apply()`, Pandas terpaksa membuat instansiasi *slice* DataFrame Python baru per grup, mengeksekusi interpreter Python secara iteratif, dan menanggung overhead alokasi memori yang masif.

4. **Combine (Rekonstruksi Blok):**
   Hasil reduksi atau transformasi dikumpulkan ke dalam array NumPy baru yang kemudian dibungkus kembali menjadi DataFrame melalui `BlockManager`.

---

### 4. Why
Dalam lingkungan produksi (data engineering pipelines, real-time analytics, quantitative finance), dataset sering kali berukuran gigabytes hingga terabytes. Eksekusi pengelompokan data yang naif dapat menyebabkan dua malapetaka infrastruktur:

1. **Latensi Komputasi Ekstrem:**
   Eksekusi kustom `.apply(lambda x: ...)` memicu overhead Python function call berulang kali sebanyak $K$ grup unik. Untuk 1.000.000 grup, overhead pemanggilan frame fungsi Python saja dapat menelan waktu belasan detik, di luar waktu komputasi matematika aktual.
2. **Out-Of-Memory (OOM) Crash:**
   Pada kolom bertipe `category` dengan kardinalitas tinggi, jika grouping dilakukan tanpa flag `observed=True`, Pandas default lama akan mengevaluasi produk Kartesian penuh dari seluruh kemungkinan kategori, mengalokasikan matriks grup berukuran $C_1 \times C_2 \times \dots \times C_n$ yang dapat menembus limit RAM container k8s/worker secara instan.
3. **Cache Inefficiency:**
   Akses memori acak non-vektor membunuh efisiensi *hardware prefetcher* CPU. Pengetahuan mendalam atas internal groupby memungkinkan perancangan algoritma yang memaksimalkan *SIMD (Single Instruction, Multiple Data)* vectorization.

---

### 5. What
Komponen kunci dalam subsystem GroupBy Pandas meliputi:

* **`pandas.core.groupby.generic.DataFrameGroupBy`**: Wrapper API tingkat tinggi yang menyimpan metadata grup, indeks, dan konfigurasi operasi.
* **`Grouper` / `Grouping`**: Objek internal yang mengekstraksi vektor nilai dari target DataFrame, menangani tipe data, dan memegang algoritma faktorisasi.
* **`sorter` & `codes`**: Array 1D integer (NumPy `intp` atau `int64`) yang mendefinisikan kepemilikan baris asli terhadap ID grup tertentu.
* **Reduction Kernels (`pandas._libs.groupby`)**: Kumpulan modul Cython terkompilasi (`group_sum`, `group_mean`, `group_quantile`, dsb.) yang beroperasi pada C-arrays secara mutlak tanpa Global Interpreter Lock (GIL) contention.
* **Transform Engine vs. Aggregation Engine**:
  * *Aggregation*: Menghasilkan dimensi output $\mathbb{R}^K$ (mereduksi baris menjadi sebanyak grup unik).
  * *Transform*: Menghasilkan dimensi output $\mathbb{R}^N$ (memproyeksikan kembali hasil kalkulasi ke bentuk dimensi baris asli DataFrame, mempertahankan *broadcasting*).

---

### 6. How
Alur eksekusi internal saat mengeksekusi `.groupby(by='key').agg({'value': 'sum'})`:

```
1. Input DataFrame
   │
   ├──► 2. Ekstraksi Kolom Grouping ('key')
   │       └── Call: Categorical/Factorize Algorithm
   │
   ├──► 3. Pembangunan Hash Table & Codes
   │       ├── codes: array([0, 1, 0, 2, 1, ...], dtype=intp)
   │       └── unique_keys: Index(['A', 'B', 'C'])
   │
   ├──► 4. Ekstraksi Target Data Buffer ('value')
   │       └── Ambil underlying 1D contiguous array (NumPy pointer)
   │
   ├──► 5. Dispatching ke Kernel C/Cython
   │       └── Call: pandas._libs.groupby.group_sum_float64(out, counts, values, codes)
   │           (Zero-overhead loop, memanfaatkan registers CPU secara efisien)
   │
   └──► 6. Pembentukan Output
           ├── Rekonstruksi Index dari unique_keys
           └── Konstruksi Block baru untuk menampung array 'out'
```

---

### 7. Analogy
Bayangkan sebuah pusat logistik pengiriman paket dengan 1.000.000 paket harian yang ditujukan ke 500 kota.

* **Pendekatan Naif (`.apply` lamban):**
  Petugas mengambil paket satu per satu, mendirikan 500 tenda terpisah (alokasi memori per grup), memindahkan paket ke masing-masing tenda secara fisik (copy memory), lalu menyewa 500 manajer independen untuk masuk ke masing-masing tenda dan menghitung total berat paket (Python interpreter overhead).
* **Pendekatan Arsitektur Internal Pandas (Vectorized GroupBy Engine):**
  Petugas tidak memindahkan paket. Petugas menempelkan barcode angka `0` s.d. `499` pada paket (faktorisasi `codes`). Kemudian, sebuah mesin ban berjalan otomatis memindai barcode dan langsung menambahkan nilai timbangan paket ke dalam 500 counter elektronik register memori yang sudah disiapkan (`group_sum` Cython kernel). Tidak ada tenda yang dibuat, tidak ada pemindahan paket fisik.

---

### 8. Diagram
Arsitektur aliran memori dan eksekusi pada Pandas GroupBy:

```
+---------------------------------------------------------------+
|                      Original DataFrame                       |
|   Index: [0, 1, 2, 3, 4]                                      |
|   Col "Dept": ["IT", "HR", "IT", "OPS", "HR"] (string ptrs)   |
|   Col "Cost": [10.0, 20.0, 15.0, 50.0, 30.0]  (float64 array) |
+---------------------------------------------------------------+
                                │
                                ▼
         [Grouping Engine: Factorize Step (Hash Table)]
                                │
    +---------------------------+---------------------------+
    │ Codes Array: [0, 1, 0, 2, 1]                          │
    │ Uniques:     ["IT", "HR", "OPS"]                      │
    +-------------------------------------------------------+
                                │
                 Dispatching via Block Pointer
                                │
                                ▼
        [Cython Fast-Path Kernel: group_sum_float64]
    +-------------------------------------------------------+
    | In-Memory Buffer Accumulator (Pre-allocated):         |
    | Slot 0 (IT)  : 10.0 + 15.0 = 25.0                     |
    | Slot 1 (HR)  : 20.0 + 30.0 = 50.0                     |
    | Slot 2 (OPS) : 50.0        = 50.0                     |
    +-------------------------------------------------------+
                                │
                                ▼
+---------------------------------------------------------------+
|                       Result DataFrame                        |
|   Index: ["IT", "HR", "OPS"]                                  |
|   Col "Cost": [25.0, 50.0, 50.0] (float64 Block)              |
+---------------------------------------------------------------+
```

---

### 9. Simple Example
Kode demonstrasi perbedaan fundamental antara *Fast-Path Cython* vs *Slow-Path Apply*:

```python
import numpy as np
import pandas as pd

# Inisialisasi DataFrame sederhana
df = pd.DataFrame(
    {
        "category": ["A", "B", "A", "B", "C", "A"],
        "value": [10.0, 25.0, 15.0, 35.0, 5.0, 20.0],
    }
)

# 1. Fast-Path Aggregation (Menggunakan C-engine bawaan)
agg_fast = df.groupby("category", as_index=False)["value"].sum()
print("Fast-Path Result:")
print(agg_fast)

# 2. Vectorized Transformation (Mempertahankan dimensi asli via broadcasting code)
df["category_sum"] = df.groupby("category")["value"].transform("sum")
print("\nTransform Result (Broadcasting):")
print(df)
```

---

### 10. Practical Example
Pipeline ingest data transaksi berskala 5.000.000 baris dengan agregasi multi-kolom tingkat lanjut, implementasi Numba engine, dan kontrol ketat atas konsumsi memori.

```python
from typing import Dict, Any
import numpy as np
import pandas as pd
import time


def generate_transaction_workload(n_rows: int = 5_000_000) -> pd.DataFrame:
    """Menghasilkan dataset transaksi sintetis untuk benchmarking skala produksi."""
    rng = np.random.default_rng(seed=42)

    merchants = np.array([f"merchant_{i:04d}" for i in range(1_000)], dtype=object)
    categories = np.array(["RETAIL", "TECH", "FOOD", "AUTO", "TRAVEL"], dtype=object)

    df = pd.DataFrame(
        {
            "merchant_id": rng.choice(merchants, size=n_rows),
            "category": rng.choice(categories, size=n_rows),
            "amount": rng.exponential(scale=50.0, size=n_rows).astype(np.float64),
            "fraud_flag": rng.choice([0, 1], size=n_rows, p=[0.99, 0.01]).astype(
                np.int8
            ),
        }
    )

    # Optimalisasi Dtype ke categorical untuk fast factorizer pointer
    df["merchant_id"] = df["merchant_id"].astype("category")
    df["category"] = df["category"].astype("category")
    return df


def execute_high_performance_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Menjalankan agregasi teroptimasi:
    - observed=True untuk memitigasi Cartesian explosion.
    - Dict aggregation untuk eksekusi single-pass Cython kernel.
    - Transformasi window quantile berbasis Cython.
    """
    start_time = time.perf_counter()

    # 1. Agregasi multi-fungsi menggunakan fast Cython implementations
    agg_rules: Dict[str, Any] = {
        "amount": ["sum", "mean", "std"],
        "fraud_flag": "sum",
    }

    # observed=True krusial pada data categorical
    aggregated_metrics = df.groupby(
        ["merchant_id", "category"], observed=True, as_index=False
    ).agg(agg_rules)

    # Flatten hierarchical multi-index column names
    aggregated_metrics.columns = [
        "_".join(col).strip("_") for col in aggregated_metrics.columns.values
    ]

    # 2. Window normalization menggunakan transform (O(N) operation)
    # Menghitung deviasi nilai transaksi terhadap rata-rata per kategori
    category_means = df.groupby("category", observed=True)["amount"].transform("mean")
    df["normalized_amount"] = df["amount"] / category_means

    elapsed = time.perf_counter() - start_time
    print(f"[PIPELINE SUCCESS] 5M baris diproses dalam: {elapsed:.4f} detik")

    return aggregated_metrics


if __name__ == "__main__":
    workload_df = generate_transaction_workload(5_000_000)
    result = execute_high_performance_pipeline(workload_df)
    print(result.head(5))
```

---

### 11. Real World Example
**Domain:** Financial Fraud Detection Engine (Fintech Payment Gateway).

**Masalah:**
Sebuah platform gateway pembayaran memproses 20.000.000 log transaksi per jam. Mesin penilaian risiko fraud memerlukan kalkulasi *Z-Score* transaksi pengguna secara real-time/micro-batch relatif terhadap riwayat transaksi kategori pedagang (*merchant categories*) dalam 24 jam terakhir.

Implementasi awal pengembang menggunakan:
```python
# IMPLEMENTASI FATAL DI PRODUCTION
df.groupby("merchant_category").apply(
    lambda g: (g["amount"] - g["amount"].mean()) / g["amount"].std()
)
```
Eksekusi ini memicu degradasi server: memakan waktu **42 menit**, lonjakan memori sebesar 28 GB RAM akibat instansiasi objek sub-DataFrame secara berulang, dan menyebabkan timeout pada micro-batch streaming queue.

**Solusi:**
Arsitek data merekonstruksi pipeline menggunakan *vectorized transform primitives*:
```python
# IMPLEMENTASI LEVEL SISTEM ARSITEKTUR
grp = df.groupby("merchant_category", observed=True)["amount"]
means = grp.transform("mean")
stds = grp.transform("std")
df["z_score"] = (df["amount"] - means) / stds
```

**Hasil:**
* Waktu eksekusi terpangkas dari **42 menit** menjadi **1,3 detik** (peningkatan efisiensi $\approx 1.900\times$).
* Jejak memori berkurang dari 28 GB menjadi **0.3 GB footprint alokasi**, karena eksekusi dialihkan ke Cythonized vector code tanpa alokasi sub-frame per grup.

---

### 12. Trade-offs

| Aspek | Fast-Path Cython (`.agg('mean')`) | Numba Engine (`engine='numba'`) | Slow-Path Python (`.apply(fn)`) |
| :--- | :--- | :--- | :--- |
| **Throughput Eksekusi** | Tertinggi ($\sim \text{Level C}$) | Sangat Tinggi (JIT-optimized) | Sangat Rendah (Interpreter overhead) |
| **Kompilasi Cold-Start**| Tidak Ada (Pre-compiled) | Ada overhead pada pemanggilan pertama | Tidak Ada |
| **Fleksibilitas Logika**| Terbatas pada fungsi matematis bawaan | Mendukung custom loop NumPy array | Arbitrer (Dapat mengeksekusi sembarang objek Python) |
| **Konsumsi Memori** | Minimal (In-place buffer) | Minimal (Array pointer) | Sangat Masif (Objek sub-DataFrame dibuat per grup) |
| **Kompleksitas Kode** | Rendah (Deklaratif) | Menengah (Harus conform ke nopython rules) | Rendah (Imperatif Pythonic biasa) |

---

### 13. When To Use
* Gunakan native Cython aggregations (`.sum()`, `.mean()`, `.min()`, `.max()`, `.prod()`, `.std()`, `.var()`) untuk setiap kebutuhan perangkuman data numerik skala besar.
* Gunakan `.transform()` saat membutuhkan metrik agregasi yang diproyeksikan kembali ke level granularity data mentah (misal: normalisasi per grup, deteksi anomali deviasi).
* Gunakan parameter `engine='numba'` ketika algoritma agregasi kustom melibatkan iterasi sekuensial yang kompleks (misalnya: rolling exponential tracking atau custom dynamic programming) yang tidak didukung fungsi standar Pandas.
* Selalu set `observed=True` saat mengelompokkan data berbasis kolom `pd.Categorical`.

---

### 14. When NOT To Use
* **Streaming Data Baris-per-Baris Berlatensi Mikrodetik:**
  Arsitektur Pandas GroupBy didesain untuk *in-memory batch computation*. Jangan gunakan GroupBy untuk agregasi streaming event-by-event per request HTTP; gunakan specialized low-latency state-stores seperti Redis, Apache Flink, atau sliding window memory buffers.
* **Dataset Multi-Terabyte yang Melampaui Kapasitas RAM:**
  Pandas memproses data sepenuhnya di dalam memori fisik (*in-memory*). Jika ukuran dataset melebihi kapasitas memori node tunggal, GroupBy Pandas akan memicu Kernel OOM-Killer. Alihkan ke *out-of-core computing* engines seperti Polars, Apache Spark, atau Dask.

---

### 15. Common Mistakes

1. **Mengabaikan Parameter `observed=True` pada Categorical Index:**
   ```python
   # SALAH: Cartesian explosion memory crash
   df["cat1"] = df["cat1"].astype("category")  # 1000 categories
   df["cat2"] = df["cat2"].astype("category")  # 1000 categories
   # Mengalokasikan 1000 x 1000 = 1.000.000 grup, meski hanya 500 yang eksis
   df.groupby(["cat1", "cat2"]).sum()

   # BENAR:
   df.groupby(["cat1", "cat2"], observed=True).sum()
   ```

2. **Menggunakan `.apply()` untuk Operasi yang Tersedia di `.transform()` atau `.agg()`:**
   ```python
   # SALAH: Overhead eksekusi Python frame masif
   df.groupby("id").apply(lambda g: g["val"].sum())

   # BENAR: Memanfaatkan direct C-dispatch
   df.groupby("id")["val"].sum()
   ```

3. **Memodifikasi Data Asli di Dalam Fungsi Lambda (`Side-Effects`):**
   Mengeksekusi mutasi state global atau mutating in-place array di dalam `.apply()` menyebabkan race conditions, bug konkurensi, dan kegagalan idempotensi karena Pandas sering kali mengevaluasi grup pertama sebanyak *dua kali* untuk mendeteksi tipe data kembalian (*type inference step*).

---

### 16. Best Practices (Production Checklist)

- [ ] **Data Types Downcasting:** Pastikan kolom kunci telah dikonversi ke tipe data integer terendah atau `category` sebelum operasi pengelompokan.
- [ ] **Indeks Non-Preservation Saat Tidak Diperlukan:** Berikan parameter `as_index=False` pada `.groupby()` guna menghindari overhead rekonstruksi objek hierarki `pd.MultiIndex`.
- [ ] **Explicit Aggregation Engine:** Gunakan dictionary explicit mapping untuk operasi multi-kolom guna memicu vectorized paths: `df.groupby(...).agg({'A': 'sum', 'B': 'mean'})`.
- [ ] **Sorting Control:** Jika hasil pengelompokan tidak membutuhkan keterurutan kunci alfabetik/numerik, tentukan `sort=False` untuk mengeliminasi overhead $\mathcal{O}(K \log K)$ sorting step.
- [ ] **Evaluasi Memory Multi-Index:** Saat memproses grouping multi-kolom, verifikasi konsumsi memori sebelum eksekusi untuk memastikan kardinalitas grup tidak melampaui RAM limit worker.

---

### 17. Troubleshooting

* **Problem: MemoryError saat operasi GroupBy pada DataFrame yang ukurannya relatif lebih kecil dari RAM.**
  * *Root Cause:* Kombinatorik kategorikal tidak terbatas (`observed=False`) mengalokasikan matriks grup sparse raksasa.
  * *Solusi:* Set `observed=True` pada deklarasi groupby.
* **Problem: GroupBy running sangat lambat meski hanya menggunakan `.agg(custom_func)`.**
  * *Root Cause:* Fungsi kustom menggunakan library Python native (misal math standard lib) yang memblokir Cython auto-vectorization.
  * *Solusi:* Tulis ulang kalkulasi menggunakan ekspresi NumPy murni, atau kompilasi fungsi menggunakan decorator `@numba.jit(nopython=True)` dan pass ke groupby dengan parameter `engine='numba'`.
* **Problem: Peringatan `DeprecationWarning: DataFrameGroupBy.apply operated on the grouping columns`.**
  * *Root Cause:* Pandas versi terbaru melarang kolom grouping diakses secara implisit di dalam transformasi sub-DataFrame.
  * *Solusi:* Seleksi kolom data secara eksplisit sebelum melakukan aggregasi/apply: `df.groupby('key')[['target_col']].apply(...)`.

---

### 18. Exercise
**Instruksi:**
Tulis sebuah modul Python yang mengoptimalkan kode analitik lambat berikut. Modul Anda harus melewati assert test performa dan integritas data numerik.

**Kode Bermasalah (Baseline):**
```python
import pandas as pd
import numpy as np


def slow_metric_calculation(df: pd.DataFrame) -> pd.DataFrame:
    # Problem: Sangat lambat dan memakan memori berlebih
    def calculate_metrics(g):
        return pd.Series(
            {
                "scaled_sum": (g["metric_a"] * g["metric_b"]).sum(),
                "normalized_max": g["metric_a"].max() / (g["metric_b"].mean() + 1e-9),
            }
        )

    return df.groupby("segment_id").apply(calculate_metrics)
```

**Tugas:**
Implementasikan fungsi `fast_metric_calculation(df: pd.DataFrame) -> pd.DataFrame` yang menghasilkan output yang identik secara numerik dengan batas toleransi `1e-5`, namun berjalan minimal **$10\times$ lebih cepat** pada dataset dengan $1.000.000$ baris dan $5.000$ unik segment.

```python
# Kriteria Test Assertion:
# 1. np.allclose(res_slow.values, res_fast.values) == True
# 2. Execution time res_fast <= (Execution time res_slow / 10)
```

---

### 19. Challenge
**Skenario Rekayasa:**
Rancang sebuah algoritma kustom agregasi windowing: *Exponentially Weighted Moving Average (EWMA) with Dynamic Time Decay per Group* pada data transaksi finansial tak-beraturan (*irregular time-spaced transactions*).

**Kondisi Batasan:**
* Dataset berisi 10.000.000 baris.
* Tidak boleh menggunakan `df.groupby().apply()`.
* Waktu peluruhan waktu ditentukan oleh formula matematika:
  $$w_i = e^{-\lambda \cdot (t_i - t_{i-1})}$$
* Wajib diselesaikan menggunakan kombinasi NumPy strides, `numba.njit` engine parallel processing, atau Cythonized loop dispatching langsung ke pointer memori DataFrame. Konsumsi puncak RAM tidak boleh melebihi $2\times$ ukuran memory buffer data mentah.

---

### 20. Summary
* **Arsitektur Pemisahan:** Pandas tidak memotong memori secara fisik dalam fase *Split*; melainkan menjalankan algoritma faktorisasi untuk memetakan baris asli ke array integer `codes` berbasis *hash tables*.
* **Vektorisasi vs Interpreter:** Penggunaan `.apply()` mengorbankan kecepatan hingga hitungan orde magnitudo karena memicu Python call frames per grup unik. Pemanfaatan Cython internal dispatch (`.agg()`, `.transform()`) adalah standar mutlak performa produksi.
* **Manajemen Alokasi:** Menyetel konfigurasi `observed=True` pada tipe data kategorikal dan `sort=False` pada query agregasi non-urutan adalah strategi arsitektur dasar untuk mencegah lonjakan latensi algoritma dan pembengkakan memori tak terkendali.