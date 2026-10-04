# Bab 05 Module 01: Advanced Data Transformation & Split-Apply-Combine Engine Internals

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta mampu:
*   Menganalisis dan mengoptimalkan siklus komputasi pola **Split-Apply-Combine** pada Pandas hingga level C-extension / Cython.
*   Merancang transformasi data berdimensi tinggi menggunakan metode agregasi vektor, *windowing*, dan *expanding calculations* tanpa memicu degradasi performa akibat Python *interpreter loop overhead*.
*   Mengintegrasikan kompilasi JIT via *engine* Numba pada operasi kustom `GroupBy` untuk mempercepat komputasi matematika kompleks hingga 10x–50x lipat.
*   Mengontrol konsumsi memori dan memitigasi fragmentasi memori pada agregasi bertingkat (*Multi-level Aggregations*) dengan *high-cardinality keys*.

---

### 2. Prerequisite
*   Pemahaman mendalam mengenai struktur array NumPy (`ndarray`), *strides*, dan penataan memori (C-contiguous vs. Fortran-contiguous).
*   Penguasaan hierarki memori internal Pandas (`Series`, `DataFrame`, `BlockManager`, dan `Index`).
*   Pengalaman teknis dalam profiling kode Python menggunakan *profiler* standar (`cProfile`, `line_profiler`, atau `memory_profiler`).

---

### 3. Concept
Pola **Split-Apply-Combine** (diperkenalkan secara formal oleh Hadley Wickham) adalah fondasi transformasi data tabular. Di balik antarmuka `df.groupby()`, Pandas tidak memecah DataFrame secara fisik menjadi sub-DataFrame Python terpisah karena overhead alokasi memori objek akan menyebabkan kompleksitas ruang melonjak menjadi $\mathcal{O}(N \times K)$ (di mana $N$ adalah jumlah baris dan $K$ adalah jumlah grup).

```
         DataFrame Asal (Tabel Utuh)
         +----+-------+-------+
         | ID | Group | Value |
         +----+-------+-------+
         | 0  |   A   |  10   |
         | 1  |   B   |  20   |
         | 2  |   A   |  15   |
         | 3  |   B   |  30   |
         +----+-------+-------+
                    |
      [1. SPLIT: Hash Indexer Engine]
                    v
    Group A -> [Row 0, Row 2]  (Index Pointers)
    Group B -> [Row 1, Row 3]  (Index Pointers)
                    |
      [2. APPLY: Cython / Numba Kernel]
      Compute: sum(Value), mean(Value)
                    |
      [3. COMBINE: Memory Reassembly]
                    v
         +-------+-------+-------+
         | Group | Sum   | Mean  |
         +-------+-------+-------+
         |   A   |  25   | 12.5  |
         |   B   |  50   | 25.0  |
         +-------+-------+-------+
```

Secara internal, proses ini beroperasi melalui mekanisme berikut:
1.  **Split via Hash Table / Categorical Codes**: Mesin C-level Pandas membaca kolom kunci pengelompokan (*grouping keys*). Nilai-nilai unik dipetakan ke dalam array integer berdimensi 1 yang disebut array label/kode grup (`group_info`), bersama dengan array hitungan (`counts`) dan posisi indeks baris.
2.  **Apply via Cython Fast-Path**: Agregasi standar (seperti `sum`, `mean`, `min`, `max`, `std`) diarahkan langsung ke kernel C/Cython yang telah dikompilasi sebelumnya. Kernel ini mengiterasi array nilai menggunakan pointer indeks grup secara kontigu tanpa *boxing* tipe data primitif ke objek `PyObject`.
3.  **Combine via Block Construction**: Hasil kalkulasi ditampung langsung ke dalam buffer memori baru yang berukuran tepat sesuai jumlah grup unik, kemudian dibungkus kembali menjadi DataFrame.

---

### 4. Why
*   **Mengeliminasi Global Interpreter Lock (GIL) Overhead**: Pemanggilan `.apply(lambda x: ...)` memaksa eksekusi keluar dari konteks C dan memanggil Python interpreter berulang kali sebanyak jumlah grup unik. Jika terdapat $100.000$ grup, Python runtime akan mengalokasikan dan mendealokasikan frame stack $100.000$ kali.
*   **Efisiensi Memori Skala Produksi**: Memproses puluhan juta baris transaksi finansial menuntut algoritma pengelompokan yang tidak menggandakan data mentah. Memahami pointer internal grup mencegah terjadinya *Out-Of-Memory* (OOM) error.
*   **Determinisme Data Pipeline**: Penggunaan transformasi vektor dan penanganan MultiIndex yang terstruktur menjamin hasil operasi pipeline dapat diprediksi (*deterministic*), bebas dari efek samping (*idempotent*), dan siap dijalankan pada batch maupun streaming inference.

---

### 5. What
Komponen arsitektural utama dalam sub-sistem transformasi data Pandas:
*   **`pandas.core.groupby.generic.DataFrameGroupBy`**: Objek proxy yang memegang referensi ke data asli dan konfigurasi pengelompokan (`Grouping` metadata).
*   **`Grouping` Engine**: Modul internal yang mengekstrak nilai sumbu (*axis*), menghasilkan representasi hash internal, dan memetakan indeks baris ke `group_index`.
*   **Fast-path Cython Reductions**: Kumpulan fungsi internal (contoh: `group_sum_float64`, `group_mean_float64`) yang beroperasi pada C-array.
*   **`transform()` vs `agg()`**: 
    *   `agg()` (*Aggregation*): Melakukan reduksi dimensionalitas. Output memiliki dimensi baris sama dengan jumlah grup unik ($M$).
    *   `transform()`: Mempertahankan dimensionalitas data asal ($N$ baris). Setiap baris hasil memiliki ukuran yang selaras dengan data input, ideal untuk normalisasi (misalnya, z-score per grup).
*   **Numba JIT Engine Integration**: Ekstensi performa yang memungkinkan fungsi transformasi Python kustom dikompilasi menjadi machine code via LLVM saat runtime (`engine="numba"`).

---

### 6. How
Berikut adalah alur eksekusi komputasi GroupBy tingkat lanjut dari pemanggilan kode hingga alokasi memori akhir:

```
[User API Call: df.groupby('key').agg(...) / transform(...)]
                              |
                              v
             [Inspeksi Kolom Kunci Pengelompokan]
                              |
       +----------------------+----------------------+
       |                                             |
[Kunci berupa Kategorikal]             [Kunci Non-Kategorikal]
       |                                             |
Ekstraksi array integer codes           Hash table lookup C-level
(Zero-copy, O(1) step)                 (Membangun group_index, O(N))
       |                                             |
       +----------------------+----------------------+
                              |
                              v
                [Evaluasi Kernel Agregasi]
                              |
       +----------------------+----------------------+
       |                                             |
[Fungsi Standar: sum, mean]           [Fungsi Kustom / Custom Logic]
       |                                             |
Fast-path Cython                       +-------------+-------------+
Kernel dieksekusi                      |                           |
       |                         [engine="cython"]         [engine="numba"]
       |                               |                           |
       |                         Python Loop               LLVM JIT Compile
       |                         Slow / GIL Bound          High-Speed Machine Code
       +-------------------------------+---------------------------+
                                       |
                                       v
                     [Rekonstruksi Objek Return]
         Alokasi buffer NumPy baru -> Buat BlockManager -> DataFrame
```

---

### 7. Analogy
Bayangkan sebuah gudang sortir logistik paket internasional.
*   **Naive Approach (`.apply` loop)**: Petugas mengambil setiap paket satu per satu, membaca negara tujuan, membawa paket tersebut ke ruangan khusus untuk negara itu, memprosesnya, lalu kembali lagi ke tumpukan awal. Jika terdapat 1.000.000 paket dan 200 negara, petugas bolak-balik jutaan kali (interupsi GIL dan alokasi memori berlebih).
*   **Engineered GroupBy (Split-Apply-Combine internal)**: Petugas menempelkan stiker barcode warna integer (0-199) pada setiap paket secara instan di ban berjalan utama (*Split/Indexing*). Kemudian, mesin lengan robotik otomatis membaca stiker tersebut langsung menyalurkan kalkulasi metrik berat per barcode secara paralel tanpa memindahkan fisik paket (*Apply via Cython*). Terakhir, hasil kalkulasi dicetak dalam satu lembar manifest ringkasan (*Combine*).

---

### 8. Diagram
```
DataFrame di Memory (Contiguous Memory Buffers)
Index:   0    1    2    3    4    5
Key:   ['A', 'B', 'A', 'C', 'B', 'A']
Val:   [10,  20,  30,  40,  50,  60]

Step 1: SPLIT (Fase Grouping via Indexer Array)
Hash Map menghasilkan group_ids array:
group_ids: [0, 1, 0, 2, 1, 0]  (A->0, B->1, C->2)
Pointers:
Group 0 (A) -> Indeks [0, 2, 5]
Group 1 (B) -> Indeks [1, 4]
Group 2 (C) -> Indeks [3]

Step 2: APPLY (Operasi Reduksi Matematika Vektor)
Cython Group Engine mengalokasikan array hasil:
out_array: [size = 3 unique groups]
out_array[0] = Sum([10, 30, 60]) = 100
out_array[1] = Sum([20, 50])     = 70
out_array[2] = Sum([40])         = 40

Step 3: COMBINE (Rekonstruksi DataFrame Akhir)
Key Index: ['A', 'B', 'C']
Val Data:  [100, 70, 40]
```

---

### 9. Simple Example
Contoh berikut menunjukkan perbedaan eksekusi antara pendekatan non-idiomatik (lambat) versus idiomatik (cepat) pada dataset sintetis:

```python
import time
import numpy as np
import pandas as pd

# 1. Bangun dataset simulasi transaksi
np.random.seed(42)
n_rows = 1_000_000
df = pd.DataFrame(
    {
        "merchant_id": np.random.randint(1, 1000, size=n_rows),
        "amount": np.random.uniform(5.0, 500.0, size=n_rows),
    }
)

# 2. Pendekatan Lambat: Iterasi / Custom Python Lambda Apply
t0 = time.perf_counter()
res_slow = df.groupby("merchant_id")["amount"].apply(lambda s: s.sum())
t_slow = time.perf_counter() - t0

# 3. Pendekatan Idiomatik: Cython Built-in Engine
t0 = time.perf_counter()
res_fast = df.groupby("merchant_id")["amount"].sum()
t_fast = time.perf_counter() - t0

print(f"Slow Apply Time : {t_slow:.4f} detik")
print(f"Fast Cython Time: {t_fast:.4f} detik")
print(f"Akselerasi      : {t_slow / t_fast:.2f}x lebih cepat")

# Validasi ekivalensi numerik
pd.testing.assert_series_equal(res_slow, res_fast)
```

---

### 10. Practical Example
Sistem analisis latensi transaksi finansial: Menghitung metrik agregasi multi-level, *rolling average* per grup merchant, dan mengidentifikasi anomali deviasi transaksi menggunakan `engine="numba"` serta `transform()`.

```python
import numpy as np
import pandas as pd
from numba import jit

# 1. Penyiapan data transaksional berkala
n_records = 2_000_000
merchants = [f"MCH_{i:04d}" for i in range(500)]

df_transactions = pd.DataFrame(
    {
        "merchant_id": np.random.choice(merchants, size=n_records),
        "timestamp": pd.date_range(
            start="2026-01-01", periods=n_records, freq="ms"
        ),
        "latency_ms": np.random.exponential(scale=50.0, size=n_records),
        "amount": np.random.uniform(10.0, 2000.0, size=n_records),
    }
)

# Optimalisasi tipe data: Konversi merchant_id ke Categorical untuk kompresi memori & kecepatan hash
df_transactions["merchant_id"] = df_transactions["merchant_id"].astype(
    "category"
)

# 2. Custom Aggregator menggunakan Numba JIT engine
# Menghitung trimmed mean (membuang outlier 5% teratas & terbawah) secara instan di level C
@jit(nopython=True)
def numba_trimmed_mean(values):
    # Algoritma komputasi level native
    sorted_vals = np.sort(values)
    n = len(sorted_vals)
    if n < 10:
        return np.mean(sorted_vals)
    k = int(n * 0.05)
    trimmed = sorted_vals[k : n - k]
    return np.mean(trimmed)

# 3. Eksekusi Agregasi Kompleks
agg_results = df_transactions.groupby("merchant_id", observed=True).agg(
    total_volume=("amount", "sum"),
    avg_amount=("amount", "mean"),
    p95_latency=("latency_ms", lambda x: np.percentile(x, 95)),
    trimmed_mean_latency=(
        "latency_ms",
        numba_trimmed_mean,
    ),  # Numba-powered function
)

# 4. Transformasi Berdimensi Penuh: Normalisasi z-score per merchant
merchant_grouped = df_transactions.groupby("merchant_id", observed=True)[
    "latency_ms"
]
mean_latency = merchant_grouped.transform("mean")
std_latency = merchant_grouped.transform("std")

# Deteksi transaksi lambat anomalus (> 3 standard deviasi dari baseline merchant bersangkutan)
df_transactions["is_latency_anomaly"] = (
    df_transactions["latency_ms"] - mean_latency
) > (3 * std_latency)

print("--- Hasil Ringkasan Metrik Merchant (Top 5) ---")
print(agg_results.head())
print("\n--- Total Transaksi Teridentifikasi Anomali ---")
print(df_transactions["is_latency_anomaly"].value_counts())
```

---

### 11. Real World Example
**Sektor FinTech**: Pipeline Rekonsiliasi Finansial Global (*Fraud Detection Pipeline*).

Pada penyedia dompet digital skala enterprise (volume: 100 juta transaksi per hari), tim kuantitatif dan rekayasa data harus menghitung **Velocity Features** secara dinamis:
*   Berapa total volume transaksi akun tertentu dalam durasi 1 jam terakhir?
*   Berapa deviasi nilai transaksi saat ini dibandingkan median transaksi akun tersebut selama 30 hari ke belakang?

**Solusi Arsitektural**:
Alih-alih mengeksekusi *self-join* SQL database relational yang membebani cluster I/O, dataset dipecah ke dalam partisi partisi waktu di memori menggunakan Pandas. Tim mengimplementasikan pola:
1.  Pengelompokan menggunakan `user_id` bertipe *Categorical*.
2.  Pengurutan data berbasis *in-place sort* pada kolom waktu (`timestamp`).
3.  Operasi transformasi jendela waktu berjalan via `.groupby("user_id").rolling("1h", on="timestamp")["amount"].sum()`.
4.  Fitur deviasi dihitung secara tervektor via kombinasi `.transform('median')` dan ekspresi NumPy murni.

**Hasil**: Pipa fitur yang sebelumnya membutuhkan waktu 4 jam komputasi batch berhasil ditekan menjadi 7,5 menit per batch, menghemat biaya komputasi cloud sebesar 65% dan memungkinkan inferensi model deteksi fraud berjalan secara sub-detik pada data transaksi batch terkini.

---

### 12. Trade-offs
Berikut adalah analisis komparasi pendekatan transformasi data pada Pandas:

| Karakteristik | Vectorized Cython Engine (`.sum()`, `.mean()`) | Custom JIT Engine (`engine="numba"`) | Standard Python Loop (`.apply(lambda)`) |
| :--- | :--- | :--- | :--- |
| **Kecepatan Eksekusi** | Ekstrem ($\approx \mathcal{O}(N)$ level C) | Sangat Tinggi (Mendekati native C) | Rendah (Terhambat GIL & boxing) |
| **Alokasi Memori** | Minimal (In-place & single buffer reuse) | Rendah (NumPy pointer passing) | Tinggi (Alokasi objek `Series` berkali-kali) |
| **Fleksibilitas Kode** | Terbatas pada fungsi bawaan Pandas | Menengah (Dukungan subset Python & NumPy) | Absolut (Dapat memuat objek/logika apa pun) |
| **Startup Overhead** | Nol | Ada (Waktu kompilasi pertama / *cold-start*) | Nol |
| **Keterbacaan & Debugging** | Sederhana & Deklaratif | Moderat (Perlu pemahaman batas tipe Numba) | Mudah didebug via standard debugger |

---

### 13. When To Use
*   Ketika dataset berukuran ratusan ribu hingga puluhan juta baris dan membutuhkan komputasi agregasi bertingkat.
*   Saat melakukan transformasi fitur machine learning yang membutuhkan kalkulasi relatif per grup (misal: normalisasi per kategori, imputation berbasis median per cohort).
*   Pada perancangan *window functions* berbasis waktu (misal: analisis volatilitas, rolling metrics).
*   Ketika algoritma agregasi kustom bersifat intensif secara numerik (kombinasikan dengan Numba).

---

### 14. When NOT To Use
*   **Dataset Multi-Terabyte**: Jangan gunakan Pandas pada satu mesin jika data melampaui RAM fisik. Gunakan Polars (multi-threaded query engine berbasis Rust) atau Apache Spark / DuckDB.
*   **Operasi Non-Relasional Berorientasi Graf**: Jika data membutuhkan penelusuran relasi rekursif yang dalam, gunakan Graph Engine (misalnya NetworkX atau Neo4J) alih-alih memaksa penggunaan `groupby`.
*   **Manipulasi String Non-Vektor yang Berat**: GroupBy pada string dengan kardinalitas unik tinggi tanpa representasi kategorikal dapat menyebabkan *bottleneck* hashing.

---

### 15. Common Mistakes
1.  **Menggunakan `.apply()` untuk operasi reduksi standar**:
    ```python
    # SALAH: Overhead eksekusi Python interpreter masif
    df.groupby("category")["price"].apply(lambda x: x.max() - x.min())

    # BENAR: Gunakan ekspresi vektor langsung atau engine bawaan
    g = df.groupby("category")["price"]
    diff = g.max() - g.min()
    ```
2.  **Lupa menyetel `observed=True` pada kolom Kategorikal**:
    Pada Pandas modern, melakukan `groupby` pada kolom `category` tanpa `observed=True` akan menghasilkan agregasi untuk seluruh kombinasi kategori yang mungkin ada (termasuk yang bernilai 0 baris pada dataset), menyebabkan lonjakan konsumsi memori secara masif (*Cartesian product explosion*).
3.  **Mengubah objek input (*Mutating state*) di dalam fungsi transform/apply**:
    Fungsi kustom yang dilewatkan ke dalam groupby harus bersifat murni (*pure function* tanpa *side effects*). Pandas sering kali mengevaluasi grup pertama sebanyak dua kali untuk menentukan path komputasi internal, sehingga mutasi objek akan menghasilkan data korup.

---

### 16. Best Practices
*   [ ] **Konversi Kunci Pengelompokan**: Ubah kolom string dengan pengulangan menjadi tipe data `category` sebelum melakukan operasi `.groupby()`.
*   [ ] **Gunakan `observed=True`**: Selalu aktifkan parameter `observed=True` saat mengelompokkan data berdasarkan tipe kategorikal.
*   [ ] **Gunakan Kamus Named Aggregation**: Gunakan sintaks tuple named aggregation `.agg(alias_output=('kolom_asal', 'fungsi'))` untuk keterbacaan kode dan proteksi tipe data.
*   [ ] **Matikan Indeks jika Tidak Dibutuhkan**: Gunakan `as_index=False` jika hasil akhir akan disimpan langsung ke database atau format flat (Parquet/CSV) untuk menghindari alokasi `MultiIndex` yang mahal.
*   [ ] **Sort Data Sebelum Rolling**: Selalu jalankan pemilahan waktu (`.sort_values('timestamp')`) sebelum memicu operasi windowing / rolling per grup.

---

### 17. Troubleshooting
*   **Gejala**: Komputasi `groupby().apply()` memakan waktu sangat lama dan pemakaian RAM terus meningkat.
    *   *Solusi*: Periksa apakah operasi tersebut dapat dipecah menjadi kombinasi fungsi `.agg()`, `.transform()`, atau `.filter()`. Hindari mengembalikan objek DataFrame baru dari fungsi `.apply()`.
*   **Peringatan (Warning)**: `PerformanceWarning: grouping on a non-flat Index...`
    *   *Solusi*: Jalankan `.reset_index()` sebelum pengelompokan atau pastikan sumbu pengelompokan tidak memiliki struktur MultiIndex yang terfragmentasi.
*   **Numba Typing Error**: Saat menggunakan `engine="numba"` muncul error `TypingError: Failed in nopython mode`.
    *   *Solusi*: Numba tidak memahami objek Pandas (`Series` atau `DataFrame`). Pastikan fungsi komputasi Anda hanya mengeksekusi komputasi numerik murni pada array 1D NumPy primitif.

---

### 18. Exercise
**Tugas Praktik**: Optimasi Pipeline Retensi Pelanggan.

Diberikan dataset historis interaksi pengguna dengan format:
```python
df_events = pd.DataFrame(
    {
        "user_id": np.random.randint(1000, 5000, size=500_000),
        "event_type": np.random.choice(
            ["click", "purchase", "scroll"], size=500_000
        ),
        "revenue": np.random.exponential(scale=10.0, size=500_000),
        "days_since_reg": np.random.randint(1, 365, size=500_000),
    }
)
```

**Instruksi**:
1.  Ubah kolom `event_type` menjadi bertipe `category`.
2.  Hitung agregasi berikut dalam **satu pemanggilan deklaratif** tanpa menggunakan `.apply(lambda)`:
    *   Total revenue khusus transaksi.
    *   Rata-rata hari sejak registrasi (`days_since_reg`) untuk seluruh aktivitas per user.
    *   Jumlah event yang tercatat per user.
3.  Gunakan `.transform()` untuk menambahkan kolom baru `relative_user_revenue_share`: rasio antara `revenue` baris transaksi terhadap total revenue pengguna bersangkutan.

---

### 19. Challenge
**Tantangan Sistem**: Implementasi *Sessionization Engine* Berkecepatan Tinggi.

*Skenario*: Anda menerima log clickstream mentah berukuran 5.000.000 baris. Pengguna berpindah dari satu sesi ke sesi lain jika tidak ada aktivitas selama lebih dari 30 menit.
*   **Syarat**:
    1.  Dilarang menggunakan perulangan `for` dalam konteks baris Python.
    2.  Dilarang menggunakan `apply(lambda)`.
    3.  Tentukan `session_id` unik untuk setiap interaksi dengan memadukan operasi vectorization: `.diff()`, perbandingan boolean, dan fungsi akumulasi `.cumsum()` di dalam grup pengguna.
    4.  Komputasi seluruh sesi untuk 5 juta baris harus diselesaikan dalam waktu kurang dari 3 detik pada mesin lokal standar.

---

### 20. Summary
*   Arsitektur **Split-Apply-Combine** pada Pandas dirancang untuk meminimalkan *data copying* melalui representasi hash indeks dan integer grouping array.
*   Performa maksimal dicapai saat eksekusi diarahkan ke jalur **Cython Fast-path** atau dikompilasi menggunakan **Numba JIT Engine**, menghindari biaya interpretasi Python/GIL.
*   Pemilihan antara `.agg()` dan `.transform()` ditentukan oleh kebutuhan dimensi: reduksi dimensi ke ringkasan grup ($M$ baris) atau penyesuaian skala elemen terhadap dimensi asal ($N$ baris).
*   Manajemen tipe data (khususnya penggunaan tipe `category` dan parameter `observed=True`) merupakan prasyarat teknis untuk mencegah ledakan penggunaan memori (*combinatorial state explosion*) pada dataset berskala besar.