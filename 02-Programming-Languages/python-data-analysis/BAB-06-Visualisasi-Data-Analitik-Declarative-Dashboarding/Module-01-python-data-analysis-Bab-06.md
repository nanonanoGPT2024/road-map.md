# Bab 06: Operasi Analitik Lanjut & Transformasi Tervektorisasi
## Module 01: Split-Apply-Combine Engine, Agregasi Kompleks, dan Window Functions

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonstruksi pipeline agregasi analitik performa tinggi menggunakan paradigma *Split-Apply-Combine* pada `pandas` dengan *throughput* pemrosesan jutaan baris per detik.
- Mengeliminasi *bottleneck* eksekusi Python runtime dengan mengimplementasikan fungsi reduksi berbasis Cython/Numba internal (`engine='numba'`) dan operasi tervektorisasi murni.
- Mendesain transformasi berbasis jendela waktu (*time-aware rolling*, *expanding*, dan *exponentially weighted moving windows*) tanpa menimbulkan *data leakage* pada data deret waktu (*time-series*).
- Menghitung metrik analitik multi-dimensi menggunakan `pd.Grouper`, *named aggregations*, dan transformasi kustom secara efisien terhadap konsumsi memori (RAM).

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Struktur Data Internal Pandas**: Pemahaman mendalam mengenai representasi memori `Series`, `DataFrame`, `Index`, dan `MultiIndex`.
- **Indexing & Slicing**: Penggunaan label-based (`.loc`) dan positional (`.iloc`) indexing serta Boolean masking.
- **Tipe Data & Memory Layout**: Perbedaan tipe data primitif NumPy (`float64`, `int64`), tipe data kategorikal (`category`), dan sistem tipe Apache Arrow (`pd.ArrowDtype`).
- **Kompleksitas Waktu & Ruang**: Notasi Big-O ($O(1)$, $O(N)$, $O(N \log N)$) untuk manipulasi array.

---

### 3. Concept
Arsitektur analitik data tabular bersandar pada paradigma **Split-Apply-Combine** (pertama kali diformulasikan secara formal oleh Hadley Wickham pada 2011). Di balik abstraksi tingkat tinggi `pandas.DataFrame.groupby`, engine internal menjalankan tiga tahapan mekanis pada tingkat memori:

```
[Input DataFrame] 
       │
       ▼
 1. SPLIT ───► Pemetaan Hash / Categorical Codes (Grup Keys -> Row Indices)
       │
       ▼
 2. APPLY ───► Eksekusi kernel komputasi (Cython C-loops / Numba JIT / Vectorized NumPy)
       │
       ▼
 3. COMBINE ─► Rekonstruksi blok memori (BlockManager / ArrayManager) menjadi Series/DataFrame
```

#### A. Mekanisme Internal Split: Hashing vs. Categorical Factorization
Ketika `df.groupby('key')` dieksekusi:
1. Pandas **tidak** menyalin (*copy*) data ke dalam sub-tabel independen. Tindakan menyalin data akan memicu alokasi memori berlebih ($O(N \times K)$ di mana $K$ adalah jumlah kolom).
2. Engine membentuk **GroupIndex** menggunakan algoritma *hash table* atau *factorization algorithm* (mirip algoritma kompresi kamus).
3. Setiap baris dipetakan ke dalam sebuah array integer 1D (`group_keys` atau *binned codes* dari interval $[0, M-1]$, dengan $M$ adalah total grup unik).
4. Relasi pemetaan disimpan dalam struktur `Grouping`: array integer offset yang mereferensikan indeks baris asli ke masing-masing *bucket* grup.

#### B. Mekanisme Apply: Cythonized Aggregators vs. Object Boxing
Tahap eksekusi (*apply*) memiliki divergensi performa ekstrem tergantung pada jenis fungsi yang dieksekusi:
- **Cython Fast-Paths (`mean`, `sum`, `std`, `var`, `min`, `max`, `first`, `last`)**: Pandas mem-bypass interpreter CPython. Engine meneruskan pointer array mentah C (`double*` atau `int64_t*`) dan array offset grup langsung ke kernel komputasi Cython. Iterasi dilakukan di tingkat CPU cache tanpa *Python object boxing/unboxing*. Kompleksitas waktu: $O(N)$.
- **Custom Python Callables via `.apply()`**: Interpreter CPython dipaksa menginstansiasi objek `Series` atau `DataFrame` baru untuk setiap partisi grup, memicu pemanggilan *call stack* interpreter Python, alokasi memori heap berulang, dan tekanan pada *Garbage Collector* (GC). Kompleksitas waktu konseptual tetap $O(N)$, namun *overhead constant factor* meningkat hingga 100x–1000x lebih lambat.
- **Numba Engine (`engine='numba'`)**: Melompati interpreter Python dengan mengompilasi fungsi agregasi kustom langsung ke instruksi mesin via LLVM, menghasilkan performa setara C untuk logika non-standar.

#### C. Mekanisme Window Functions: Frame Boundaries
Window operations (`rolling`, `expanding`) beroperasi secara independen terhadap reduksi dimensionalitas. Window tidak mengompresi baris; window memproyeksikan rentang data (*sliding interval*) untuk setiap baris.
- **Fixed-count Window (`rolling(window=k)`)**: Membutuhkan pergeseran indeks berbasis offset konstan. Algoritma internal mempertahankan buffer geser (*sliding buffer*) atau menggunakan algoritma *running sum/ring buffer* untuk menjaga kalkulasi agregasi bernilai $O(1)$ amortized per baris, menghasilkan total running time $O(N)$ alih-alih $O(N \times k)$.
- **Time-based Window (`rolling(window='7D')`)**: Membutuhkan DataFrame yang terurut secara monotonik berdasarkan `DatetimeIndex`. Engine menggunakan pencarian biner (*binary search* / `np.searchsorted`) untuk mengidentifikasi batas kiri interval waktu $[t - \Delta t, t]$ untuk setiap baris $t$.

---

### 4. Why
Dalam rekayasa data dan *feature engineering* produksi:
1. **Pencegahan Out-Of-Memory (OOM) Crash**: Eksekusi agregasi naive menggunakan perulangan (`for row in df.iterrows()`) atau `.apply()` kustom pada dataset puluhan juta baris mengalokasikan jutaan *ephemeral Python objects*, yang secara instan menghabiskan RAM server produksi.
2. **Kepatuhan Latensi Service Level Agreement (SLA)**: Sistem penipuan finansial (*fraud detection*), *real-time bidding*, dan analisis log membutuhkan komputasi statistik agregat (misalnya: *frekuensi transaksi 1 jam terakhir*) dalam orde milidetik.
3. **Pencegahan Look-Ahead Bias (Data Leakage)**: Pada pemodelan prediktif berbasis waktu (keuangan kuantitatif, proyeksi inventaris), agregasi rolling yang salah konfigurasi tanpa penanganan batas waktu tertutup/terbuka (*closed/open boundaries*) akan membocorkan data masa depan (*target leakage*) ke masa lalu, menghancurkan validitas model di fase produksi.

---

### 5. What
Komponen inti dalam ekosistem analitik lanjut Pandas meliputi:

- **`DataFrameGroupBy` / `SeriesGroupBy`**: Objek *lazy evaluation* pembungkus partisi data.
- **`Grouper(key, freq, closed, label)`**: Controller tingkat lanjut untuk pengelompokan berbasis interval temporal dan kalender spasial.
- **`NamedAgg` (`agg(new_col=('source_col', 'agg_func'))`)**: Sintaksis deklaratif *type-safe* untuk menghasilkan struktur tabular bersih tanpa *MultiIndex column flattening hacks*.
- **Transformasi (`transform`)**: Menerapkan fungsi reduksi namun memproyeksikan kembali hasilnya ke dimensi dimensi DataFrame semula ($N \rightarrow N$), esensial untuk standardisasi data (*z-score normalization per group*).
- **Filtrasi (`filter`)**: Membuang seluruh grup berdasarkan kondisi Boolean skalar pada level grup ($N \rightarrow M \le N$).
- **`Rolling` / `Expanding` / `ExponentialMovingWindow` (`ewm`)**: Objek komputasi berbasis jendela lokal untuk analisis tren dinamis.

---

### 6. How
Berikut adalah alur eksekusi internal saat memproses pipeline analitik tingkat lanjut:

```
[Raw DataFrame]
      │
      ├─► Step 1: Pre-sorting (Krusial untuk window functions & time grouping)
      │
      ├─► Step 2: Inisialisasi GroupBy/Rolling Engine
      │     ├─ Konstruksi Index Pointers (Bucket mapping)
      │     └─ Validasi Monotonicity pada Datetime Index
      │
      ├─► Step 3: Optimasi Kernel Eksekusi
      │     ├─ Fast-Path: Cython Built-in Aggregator (misal: 'mean', 'std')
      │     ├─ Vectorized Path: Custom Numba Kernel (JIT Compiled)
      │     └─ Fallback: Python Object Loop (HINDARI DI PRODUKSI)
      │
      ├─► Step 4: Rekonstruksi Struktur Data Output
      │     ├─ Konsolidasi Array Blok Primitif
      │     └─ Penataan Hierarki Index / Reset Index
      │
      └─► [Final Analytical Dataset]
```

---

### 7. Analogy
Bayangkan sebuah pusat logistik kargo internasional:
- **Metode Naive (Iterative/Python Loop)**: Seorang kurir mengambil satu paket, membaca label negara tujuan, berjalan ke sudut gudang yang ditentukan, meletakkannya di sana, lalu kembali lagi untuk mengambil paket kedua. Jika ada 1 juta paket, kurir bolak-balik 1 juta kali. Efisiensi nol, kelelahan sistem fatal.
- **Split-Apply-Combine Teroptimasi**: Sistem ban berjalan otomatis. 
  - **Split**: Paket dipindai barcode-nya menggunakan sensor optik berkecepatan tinggi, lalu dialihkan ke ban berjalan khusus untuk masing-masing negara secara simultan (*hashing/index factorization*).
  - **Apply**: Di setiap ban berjalan negara, timbangan digital otomatis menghitung total massa kontainer secara langsung saat muatan melewatinya (*Cython vectorized aggregation*).
  - **Combine**: Komputer pusat langsung mencetak lembar manifes berisi rekapitulasi berat seluruh negara dalam satu dokumen (*reconstructed DataFrame*).

---

### 8. Diagram
Struktur memori saat pemisahan grup dan agregasi rolling:

```
DataFrame Asli (Contiguous Memory):
Row ID:   0      1      2      3      4      5
User:   [Alice, Bob,   Alice, Bob,   Alice, Bob  ]
Val:    [10.0,  5.0,   20.0,  15.0,  30.0,  25.0 ]

========================== SPLIT PHASE ==========================
Index Factorization Mapping (Tanpa Salin Data):
Hash Bucket 'Alice': [Pointer Index 0, Pointer Index 2, Pointer Index 4]
Hash Bucket 'Bob'  : [Pointer Index 1, Pointer Index 3, Pointer Index 5]

========================== APPLY PHASE ==========================
Operasi Terpilih: rolling(window=2, on='Val').mean() per Group

Grup Alice Slice:           Rolling Window (k=2):        Keluaran:
Idx 0: 10.0         ───►   [10.0]               ───►    NaN (min_periods=2)
Idx 2: 20.0         ───►   [10.0, 20.0]         ───►    15.0
Idx 4: 30.0         ───►   [20.0, 30.0]         ───►    25.0

Grup Bob Slice:
Idx 1: 5.0          ───►   [5.0]                ───►    NaN
Idx 3: 15.0         ───►   [5.0, 15.0]          ───►    10.0
Idx 5: 25.0         ───►   [15.0, 25.0]         ───►    20.0

========================= COMBINE PHASE =========================
Penggabungan Hasil ke Struktur Memori Baru:
Row ID:   0      1      2      3      4      5
Result: [NaN,   NaN,   15.0,  10.0,  25.0,  20.0 ]
```

---

### 9. Simple Example
Contoh dasar komparasi efisiensi sintaksis: *Legacy MultiIndex aggregation* vs. *Modern Named Aggregation*.

```python
import numpy as np
import pandas as pd

# 1. Inisialisasi Data Sederhana
data = {
    "kategori": ["A", "B", "A", "A", "B", "C"],
    "nilai": [10, 20, 10, 30, 50, 100],
    "kuantitas": [1, 2, 1, 3, 5, 10],
}
df = pd.DataFrame(data)

# 2. Modern Named Aggregation (Menghindari MultiIndex kolom yang kompleks)
summary = df.groupby("kategori", as_index=False).agg(
    rata_rata_nilai=pd.NamedAgg(column="nilai", aggfunc="mean"),
    total_kuantitas=pd.NamedAgg(column="kuantitas", aggfunc="sum"),
    varian_nilai=pd.NamedAgg(column="nilai", aggfunc="var"),
)

print(summary)
```

---

### 10. Practical Example
Pipeline rekayasa fitur (*feature engineering*) untuk **Deteksi Anomali Transaksi Keuangan**. Melibatkan:
- Named aggregations multi-kolom.
- Grouped transform untuk deteksi deviasi (Z-Score transaksi lokal).
- Time-aware rolling window untuk menghitung volume transaksi 30 menit ke belakang per nasabah.

```python
from datetime import datetime
import numpy as np
import pandas as pd

# Setup data simulasi transaksi perbankan
np.random.seed(42)
n_rows = 100_000

customer_ids = np.random.choice([f"CUST_{i:04d}" for i in range(100)], size=n_rows)
base_time = pd.Timestamp("2026-03-30 08:00:00")
time_offsets = np.random.exponential(scale=60, size=n_rows).cumsum()
timestamps = [base_time + pd.Timedelta(seconds=s) for s in time_offsets]
amounts = np.random.exponential(scale=150.0, size=n_rows).round(2)

df_transaksi = pd.DataFrame(
    {"timestamp": timestamps, "customer_id": customer_ids, "amount": amounts}
)

# PASTIKAN DATA TERURUT BERDASARKAN WAKTU SEBELUM WINDOWING
df_transaksi = df_transaksi.sort_values("timestamp").reset_index(drop=True)

# -------------------------------------------------------------
# LANGKAH 1: Grouped Transform untuk Normalisasi Statis Grup (Z-Score)
# -------------------------------------------------------------
# Menghitung Z-score pengeluaran nasabah terhadap historis global nasabah tersebut
grp_cust = df_transaksi.groupby("customer_id")["amount"]

cust_mean = grp_cust.transform("mean")
cust_std = grp_cust.transform("std").replace(
    0, np.nan
)  # Tangani divide-by-zero

df_transaksi["amount_zscore_cust"] = (
    (df_transaksi["amount"] - cust_mean) / cust_std
).fillna(0.0)

# -------------------------------------------------------------
# LANGKAH 2: Time-Aware Rolling Aggregation per Customer
# -------------------------------------------------------------
# Metrik: Total belanja dan frekuensi transaksi dalam 30 menit terakhir (30min)
# Catatan: Kita harus mengindeks timestamp untuk rolling berbasis interval waktu
df_transaksi = df_transaksi.set_index("timestamp")

# Menggunakan GroupBy + Rolling time window
rolling_features = (
    df_transaksi.groupby("customer_id")["amount"]
    .rolling("30min", closed="left")  # closed='left' mencegah target data leakage
    .agg(rolling_sum_30m="sum", rolling_count_30m="count")
    .reset_index()
)

# -------------------------------------------------------------
# LANGKAH 3: Merge Kembali Fitur Temporal
# -------------------------------------------------------------
df_transaksi = df_transaksi.reset_index()

df_final = pd.merge(
    df_transaksi,
    rolling_features,
    on=["customer_id", "timestamp"],
    how="left",
)

# Isi nilai awal rolling window (NaN karena closed='left') dengan 0
df_final["rolling_sum_30m"] = df_final["rolling_sum_30m"].fillna(0.0)
df_final["rolling_count_30m"] = df_final["rolling_count_30m"].fillna(0)

print("Pipeline Eksekusi Selesai. Struktur Output:")
print(df_final.head(10))
```

---

### 11. Real World Example
#### Kasus Nyata: Dynamic Pricing & Surge Multiplier pada Sistem Ride-Hailing Skala Besar (misal: Arsitektur Gojek / Uber)

**Konteks Masalah**:
Platform transportasi daring menerima ribuan ping pesanan per menit per zona area (*geohash*). Algoritma dynamic pricing membutuhkan metrik agregasi instan:
1. Rasio lonjakan permintaan (*demand velocity*) 15 menit terakhir vs baseline 2 jam terakhir per geohash.
2. Filter ketat: Menghapus area dengan aktivitas pesanan rendah agar model pricing tidak mengalami bias *sample variance*.

**Implementasi Kode Produksi**:

```python
import numpy as np
import pandas as pd

# 1. Bangun Data Telemetri Geohash
np.random.seed(1337)
records = 500_000

geohashes = [f"gh_{np.random.randint(100, 150)}" for _ in range(records)]
timestamps = pd.date_range(
    start="2026-03-30 00:00:00", periods=records, freq="200ms"
)
trip_fares = np.random.uniform(15000, 150000, size=records).round(-2)

df_orders = pd.DataFrame(
    {"timestamp": timestamps, "geohash": geohashes, "fare": trip_fares}
).sort_values("timestamp")

# 2. Filter Grup Skala Rendah (Eliminasi Geohash dengan data tidak representatif)
# Menggunakan .filter() berbasis agregasi cepat
MIN_EVENTS_THRESHOLD = 5000
df_filtered = df_orders.groupby("geohash").filter(
    lambda x: len(x) >= MIN_EVENTS_THRESHOLD
)

# 3. Hitung Agregasi Multi-Interval Temporal menggunakan Window Functions
df_filtered = df_filtered.set_index("timestamp")

# Gunakan pipeline teroptimasi: Grouping -> Rolling -> Agg
surge_metrics = (
    df_filtered.groupby("geohash")["fare"]
    .rolling("15min", closed="right")
    .agg(["count", "mean"])
    .rename(
        columns={"count": "demand_count_15m", "mean": "avg_fare_instant_15m"}
    )
)

# 4. Integrasi Baseline Jangka Panjang (2 Jam Expanding/Rolling)
surge_metrics["baseline_fare_2h"] = (
    df_filtered.groupby("geohash")["fare"]
    .rolling("2h", closed="right")
    .mean()
    .values
)

# 5. Hitung Multiplier Lonjakan Harga (Surge Ratio) secara Vektor murni
surge_metrics["surge_factor"] = (
    surge_metrics["avg_fare_instant_15m"] / surge_metrics["baseline_fare_2h"]
).clip(lower=1.0, upper=3.5)

surge_metrics = surge_metrics.dropna().reset_index()

print("Metrik Dynamic Pricing Terkalkulasi (Sampel Baris Terakhir):")
print(surge_metrics.tail())
```

---

### 12. Trade-offs

| Aspek | Pandas Built-in (Cython Vectorized) | Python `.apply(custom_func)` | Numba JIT Engine (`engine='numba'`) | Polars / DuckDB Alternative |
| :--- | :--- | :--- | :--- | :--- |
| **Kecepatan Eksekusi** | Sangat Tinggi ($1\times$ baseline) | Sangat Rendah ($50\times - 200\times$ lambat) | Sangat Tinggi ($1\times - 2\times$ setara Cython) | Tertinggi ($2\times - 5\times$ lebih cepat dari Pandas) |
| **Konsumsi Memori** | Rendah (Zero-copy in-place hash pointer) | Sangat Tinggi (Instansiasi jutaan Python Series) | Rendah (Akses langsung raw memory pointer) | Minimal (Apache Arrow zero-copy memory native) |
| **Fleksibilitas Logika**| Terbatas pada primitif matematika standar | Tidak terbatas (Semua sintaks Python valid) | Terbatas pada subset kompilasi math NumPy | Sangat Tinggi via Expressions API |
| **Overhead Kompilasi** | Tidak ada (Precompiled C) | Tidak ada (Interpreted) | Ada kompilasi awal (*warm-up latency* pada run pertama) | Tidak ada |
| **Kesiapan Produksi** | Wajib untuk operasi standar | Dilarang keras pada dataset $>100k$ baris | Direkomendasikan untuk Custom Vectorized Math | Direkomendasikan saat dataset melebihi kapasitas RAM |

---

### 13. When To Use
- Gunakan **Vectorized Groupby Aggregations (`agg`)**: Ketika melakukan metrik statistik standar (Mean, Sum, Quantile, Min, Max, Count) pada dataset berukuran pas di memori RAM ($< 70\%$ utilisasi host RAM).
- Gunakan **`transform`**: Ketika membutuhkan fitur level-grup yang dipadukan secara paralel dengan baris observasi individual (misal: normalisasi Z-score, persentase kontribusi individu terhadap total kategori).
- Gunakan **Rolling Window dengan parameter waktu (`'10min'`, `'1D'`)**: Ketika memproses log transaksi/event tidak reguler yang terjadi pada interval waktu acak.
- Gunakan **`engine='numba'` pada `apply` / `aggregate`**: Ketika operasi analitik Anda memiliki ketergantungan sekuensial yang rumit (misal: simulasi monte-carlo per-grup, integrasi diferensial numerik) yang tidak dapat dipecahkan dengan fungsi Cython bawaan.

---

### 14. When NOT To Use
- **Dataset Melebihi Ukuran RAM (Out-of-Core Processing)**: Jangan gunakan Pandas GroupBy jika ukuran dataset $> 1.5\times$ ukuran RAM mesin Anda. Alihkan arsitektur ke **DuckDB**, **Polars (LazyFrame Engine)**, atau **Apache Spark**.
- **Agregasi Multi-Dimensi Sangat Besar (Cube / Rollup)**: Pandas tidak memiliki implementasi native `CUBE` atau `ROLLUP` yang efisien. Melakukan multi-level looping GroupBy pada kardinalitas tinggi menghasilkan overhead komputasi ekstrem; gunakan engine OLAP berbasis SQL (ClickHouse, DuckDB).
- **Kardinalitas Kunci Ekstrem Tinggi ($M \approx N$)**: Jika pengelompokan dilakukan pada kolom di mana hampir setiap baris memiliki nilai unik (misal: UUID atau Primary Key unik), fase split hashing Pandas akan menghabiskan memori hanya untuk memelihara hash table metadata grup.

---

### 15. Common Mistakes
1. **Mengabaikan Pengurutan Waktu Sebelum Window Operations**:
   ```python
   # SALAH: Rolling time-window pada dataset yang tidak terurut menghasilkan data korup/eksepsi
   df.groupby("user_id").rolling("7D").mean()

   # BENAR: Urutkan indeks waktu terlebih dahulu
   df = df.sort_values(["user_id", "timestamp"]).set_index("timestamp")
   df.groupby("user_id").rolling("7D").mean()
   ```

2. **Data Leakage Melalui Default Boundary `closed='right'` pada Time Series**:
   Secara default, `rolling(window='1h')` bersifat *right-inclusive*. Artinya, nilai pada titik waktu $t$ menyertakan data pada $t$ itu sendiri. Jika Anda memprediksi apakah transaksi pada $t$ adalah penipuan menggunakan fitur akumulasi transaksi masa lalu, Anda harus menyetel `closed='left'` untuk memastikan observasi terkini tidak membocorkan informasi ke dirinya sendiri.

3. **Penggunaan Lambdas Tanpa Alasan yang Valid pada `.agg()`**:
   ```python
   # SALAH: Memicu Python object fallback loop
   df.groupby("kategori")["nilai"].agg(lambda x: x.sum())

   # BENAR: Menggunakan Cython Fast-Path String Identifier
   df.groupby("kategori")["nilai"].sum()
   ```

4. **MultiIndex Flattening Hacks Menggunakan String Concatenation Manual**:
   Menghasilkan kode rapuh (*fragile code*) yang sering rusak akibat perubahan skema. Gunakan selalu Named Aggregation (`pd.NamedAgg` atau argumen tuple).

---

### 16. Best Practices (Production Checklist)
- [ ] **Optimasi Tipe Kunci (Grouping Keys)**: Konversi kolom grup string bertipe *object* menjadi `category` sebelum melakukan groupby jika kardinalitasnya rendah/menengah (`df['kategori'] = df['kategori'].astype('category')`). Ini memotong waktu fase *Split* hingga $5\times$.
- [ ] **Gunakan `observed=True` pada Categorical Grouping**: Mencegah ekspansi Cartesian seluruh kombinasi kategori yang tidak pernah muncul di dataset (sangat penting untuk menghemat RAM).
- [ ] **Hindari `.reset_index()` Prematur**: Tahan index sebagai penanda referensi cepat sampai seluruh agregasi selesai dieksekusi untuk meminimalkan alokasi memori ulang.
- [ ] **Konfigurasi `as_index=False`**: Gunakan `df.groupby('col', as_index=False)` jika hasil akhir akan segera diekspor ke format tabular murni (Parquet, SQL, Feather) tanpa manipulasi hierarki indeks lebih lanjut.
- [ ] **Manfaatkan Numba Engine**: Selalu sertakan library `numba` di dependensi produksi dan berikan flag `engine='numba', engine_kwargs={'parallel': True}` untuk aggregasi fungsi kalkulasi rumit non-vektor.

---

### 17. Troubleshooting
- **Error: `ValueError: index must be monotonic` saat Rolling Window**:
  - *Penyebab*: Dataset yang di-pass ke `rolling(time_interval)` memiliki DatetimeIndex yang tidak berurutan secara linier (ada timestamp acak/mundur).
  - *Solusi*: Jalankan `.sort_index()` secara eksplisit pada index temporal sebelum memanggil method `.rolling()`.
- **Error: `MemoryError` saat melakukan `.unstack()` setelah GroupBy**:
  - *Penyebab*: Kombinasi multi-kunci menghasilkan matrix sparse raksasa yang tidak muat dalam alokasi array NumPy 2D kontigu.
  - *Solusi*: Hindari unstack ke format wide-table. Tetap pertahankan format *tall/tidy data*, atau gunakan tipe data Sparse Pandas (`pd.arrays.SparseArray`).
- **Peringatan Emisi: `FutureWarning: ... will be deprecated` pada Custom Transform**:
  - *Penyebab*: Mengembalikan tipe data yang tidak konsisten antar grup dalam blok transformasi.
  - *Solusi*: Pastikan fungsi mengembalikan objek Series/Array dengan *dtype* yang strictly homogen di seluruh sub-kelompok data.

---

### 18. Exercise
Diberikan dataset metrik pemantauan server cloud:
```python
import numpy as np
import pandas as pd

np.random.seed(99)
n = 10_000
df_servers = pd.DataFrame(
    {
        "timestamp": pd.date_range("2026-03-30", periods=n, freq="10s"),
        "server_id": np.random.choice(
            ["srv_alpha", "srv_beta", "srv_gamma"], size=n
        ),
        "cpu_usage": np.random.uniform(10.0, 95.0, size=n),
        "ram_usage": np.random.uniform(20.0, 85.0, size=n),
    }
)
```

**Tugas Anda**:
1. Buat pipeline transformasi tervektorisasi untuk menghitung **Mean CPU Usage** dan **Max RAM Usage** per server dalam interval *rolling window 5 menit*.
2. Window harus dikonfigurasi secara temporal (`'5min'`) dan bersifat *closed on left* (`closed='left'`) untuk menghindari bias instan.
3. Tambahkan kolom baru: `cpu_anomaly_spike`, bertipe Boolean (`True` jika `cpu_usage` saat ini lebih tinggi dari $1.5\times$ rata-rata CPU server tersebut pada 5 menit terakhir).

---

### 19. Challenge
Implementasikan fungsi komputasi kustom **Rolling Maximum Drawdown** (MDD) finansial per portofolio saham tanpa menggunakan Python loops (`for`, `while`) atau `df.iterrows()`.

**Spesifikasi Teknis**:
- Diberikan dataset transaksi saham harian: `[date, ticker, daily_return]`.
- Akumulasikan `daily_return` menjadi *cumulative wealth index* per ticker ($W_t = \prod (1 + R_t)$).
- Hitung Peak Berjalan: $P_t = \max_{\tau \le t}(W_\tau)$ menggunakan expanding window.
- Hitung Drawdown Berjalan: $DD_t = \frac{W_t - P_t}{P_t}$.
- Hitung Maximum Drawdown pada jendela bergulir 30 hari (*rolling 30-day window*): $MDD_t = \min_{\tau \in [t-30, t]}(DD_\tau)$.
- **Batasan**: Waktu eksekusi harus di bawah 1 detik untuk 250.000 baris data pada prosesor standar. Seluruh eksekusi wajib menggunakan operasi tervektorisasi internal Pandas/NumPy.

---

### 20. Summary
- **Split-Apply-Combine** adalah engine fundamental pemrosesan analitik data. Performa optimal dicapai bukan dengan menghindari operasi grup, melainkan dengan meminimalkan crossing boundary antara C/Cython internal Pandas dan CPython runtime.
- Selalu prioritaskan **Named Aggregation** untuk keterbacaan kode (*code readability*), kemudahan pemeliharaan (*maintainability*), dan eksekusi bebas MultiIndex flattening hack.
- Gunakan **Transform** untuk memproyeksikan metrik grup kembali ke granularitas data baris tanpa perlu melakukan operasi `pd.merge()` yang memakan resource memori besar.
- Pastikan dataset selalu terurut secara monotonik (`sort_values` / `sort_index`) sebelum melakukan operasi berbasis jendela waktu (**Rolling Windows**) untuk menjamin konsistensi matematika dan menghindari *data leakage*.