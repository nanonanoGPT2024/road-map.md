# BAB 03: Quiz, Challenge, & Knowledge Check
**Data Wrangling Modern: Pandas 2.x & Apache Arrow Backend**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Memori Layout Columnar vs. C-Array Contiguous
Jelaskan perbedaan struktural fundamental antara representasi memori 2D array berbasis NumPy (blok contiguous C-order/F-order) dengan arsitektur columnar berbasis Apache Arrow di dalam Pandas 2.x. Fokuskan jawaban Anda pada bagaimana kedua backend ini menangani data dengan tipe heterogen dan alokasi memori saat operasi seleksi kolom dilakukan.

### Soal 1.2: Mekanisme Nullability (Validity Bitmap vs. Sentinel Value)
Sebelum integrasi Apache Arrow, Pandas merepresentasikan nilai hilang (*missing values*) pada kolom numerik menggunakan standar IEEE 754 Floating-Point `NaN` sebagai *sentinel value*. Jelaskan dampak arsitektural dari pendekatan tersebut terhadap integritas tipe data (misal: kolom integer yang dipaksa menjadi float). Bandingkan mekanisme ini dengan penggunaan **Validity Bitmap** (1-bit mask per entri) pada backend PyArrow di Pandas 2.x.

### Soal 1.3: Anatomi String Storage dan Cache Locality
Jelaskan mengapa representasi string konvensional pada Pandas (`dtype="object"`) menyebabkan fragmentasi memori ekstrem dan merusak *CPU L1/L2 cache locality*. Bagaimana Arrow backend mengatasi masalah ini melalui skema **Variable-length Binary Layout** (terdiri dari *Offset Buffer* dan *Value Buffer* contiguous)?

### Soal 1.4: Semantik Copy-on-Write (CoW)
Pandas 2.x memperkenalkan implementasi penuh Copy-on-Write (`pd.options.mode.copy_on_write = True`). 
1. Terangkan siklus hidup (*lifecycle*) sebuah blok memori ketika operasi *slicing* (`df_slice = df[["col_a"]]`) dieksekusi di bawah mode CoW.
2. Kondisi persis apa yang memicu mutasi fisik (*deep-copy*) memori saat operasi `df_slice["col_a"] = new_values` dijalankan?

### Soal 1.5: Zero-Copy Data Interchange via Arrow IPC / C Data Interface
Salah satu keunggulan terbesar ekosistem Arrow adalah kemampuan *interoperability*. Jelaskan bagaimana protokol **Arrow C Data Interface** memungkinkan transfer data tabular dari Pandas 2.x (dengan backend PyArrow) ke runtime analitik lain (seperti DuckDB atau Polars) tanpa overhead serialisasi/deserialisasi dan alokasi memori tambahan (*zero-copy*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Debugging Chained Assignment & Mutation Under CoW
Perhatikan cuplikan kode Python berikut:

```python
import pandas as pd

pd.options.mode.copy_on_write = True

df = pd.DataFrame({"sensor_id": ["A1", "A2", "A3"], "reading": [10.5, 20.0, 15.2]})

# Developer ingin mengoreksi nilai reading untuk sensor 'A1'
subset = df[df["sensor_id"] == "A1"]
subset["reading"] = 12.0

print(df["reading"].iloc[0])
```

**Pertanyaan:**
1. Apa nilai output dari `print(df["reading"].iloc[0])` di atas, dan mengapa *warning* `SettingWithCopyWarning` tidak lagi muncul di Pandas 2.x dengan CoW aktif?
2. Bagaimana mekanisme pelacakan referensi internal (*Reference Counting* / *Shared Object Tracker*) Pandas 2.x bekerja di balik layar untuk mengisolasi mutasi pada `subset` dari `df` asli?

### Soal 2.2: Memory Fragmentation dan Rekonstruksi ChunkedArray
Ketika operasi filter/slice berulang dieksekusi pada DataFrame yang menggunakan backend PyArrow, tipe internal kolom direpresentasikan sebagai `pyarrow.ChunkedArray`.
Jelaskan implikasi performa dari akumulasi puluhan *discontinuous chunks* terhadap eksekusi algoritma komputasi vektor (misalnya agregasi `.mean()` atau pemfilteran boolean). Kapan dan bagaimana engineer harus memaksa konsolidasi chunk via konsolidasi memori internal?

### Soal 2.3: I/O Execution Engine: C Engine vs. PyArrow Engine
Pada Pandas 2.x, fungsi ingestion seperti `pd.read_csv()` mendukung `engine="pyarrow"` dan parameter `dtype_backend="pyarrow"`.
Jelaskan proses internal multi-threaded yang dieksekusi oleh PyArrow CSV reader (misalnya *SIMD parsing*, *thread-pooled chunk allocation*) yang membuatnya 5-10x lebih cepat daripada Pandas C Engine standar, serta sebutkan minimal 2 limitasi atau edge-case di mana `engine="pyarrow"` akan gagal mem-parsing data CSV dibandingkan engine konvensional.

### Soal 2.4: Dictionary Encoding vs. Categorical Dtype
Pandas memiliki `CategoricalDtype` (berbasis NumPy), sementara Arrow menyediakan `pa.dictionary()` (Dictionary Array). 
Analisis perbedaan keduanya dalam penanganan:
1. Operasi penggabungan (*join/merge*) antara dua DataFrame di mana level *dictionary categories*-nya tidak selaras (*unaligned keys*).
2. Overhead memori dan performa komparatif saat data kolom memiliki kardinalitas sangat tinggi (*high-cardinality strings* > 1.000.000 kategori unik).

### Soal 2.5: Degradasi Performa Akibat "Implicit Fallback" ke NumPy/Python
Jelaskan mengapa pemanggilan fungsi arbitrary Python via `.apply(lambda x: custom_func(x))` pada `Series` bertipe `int64[pyarrow]` dapat menghasilkan degradasi performa yang jauh lebih buruk dibandingkan pemanggilan yang sama pada `Series` bertipe `int64` native NumPy. Uraikan jalur konversi tipe data yang terjadi pada batas antarmuka C++ Arrow ke runtime CPython dalam skenario ini.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM pada Pipeline Ingestion Data Transaksi Finansial (Batch Scale)
* **Konteks:** Sebuah microservice data ETL memproses file transaksi perbankan harian sebesar 45 GB (format Parquet, terkompresi Snappy) di instance EC2 dengan RAM 64 GB. Pipeline berjalan menggunakan Pandas 2.x default (`dtype_backend="numpy_nullable"`).
* **Gejala:** Service mendadak mati karena Linux *OOM (Out-Of-Memory) Killer* tepat saat mengeksekusi operasi:
  ```python
  df = pd.read_parquet("daily_transactions.parquet")
  df["account_number"] = df["account_number"].astype(str)
  grouped = df.groupby(["account_number", "merchant_category"]).agg(
      {"amount": "sum"}
  )
  ```
* **Diagnostik & Pertanyaan Arsitektur:**
  1. Identifikasi secara presisi alokasi memori tersembunyi (*hidden allocation explosion*) yang terjadi saat membaca 45 GB Parquet ke dalam memori dengan konfigurasi default Pandas. Mengapa RAM 64 GB tidak mencukupi padahal ukuran file disk hanya 45 GB?
  2. Rekonstruksi kode di atas agar memanfaatkan `dtype_backend="pyarrow"`, *projection pushdown*, dan pembacaan batch/zero-copy. Jelaskan estimasi reduksi memori yang dicapai melalui eliminasi pointer `object` Python pada `account_number`.

### Skenario B: Race Condition dan Integritas Data pada Multi-threaded Feature Store
* **Konteks:** Sebuah sistem serving Machine Learning waktu nyata (*real-time inference*) membagikan DataFrame `features_df` global (Arrow backend, 20 juta baris) ke beberapa worker thread menggunakan `concurrent.futures.ThreadPoolExecutor`. Setiap worker bertugas mengambil slice data berdasarkan `tenant_id`, melakukan transformasi normalisasi fitur, dan mengirimkannya ke model inference.
* **Gejala:** Pada pengujian beban tinggi (*stress testing*), beberapa tenant menerima hasil inferensi dari data tenant lain, meskipun secara logika kode setiap worker thread hanya membaca slice miliknya:
  ```python
  def process_tenant(tenant_id):
      tenant_data = features_df[features_df["tenant_id"] == tenant_id]
      # Transformasi data
      tenant_data.loc[:, "feature_scaled"] = (
          tenant_data["raw_feature"] - tenant_data["raw_feature"].mean()
      ) / tenant_data["raw_feature"].std()
      return model.predict(tenant_data)
  ```
* **Diagnostik & Pertanyaan Arsitektur:**
  1. Jika sistem ini dijalankan pada Pandas 1.x vs Pandas 2.x dengan Copy-on-Write (CoW), bagaimana perilaku mutasi `tenant_data.loc[:, "feature_scaled"]` mempengaruhi DataFrame `features_df` induk di memory heap proses Python?
  2. Bagaimana interaksi antara *Global Interpreter Lock* (GIL), thread-safety pada level blok data Apache Arrow (C++ shared pointers), dan semantik mutasi Pandas 2.x menyebabkan *data cross-talk* atau race conditions? Rancang pola penulisan kode yang 100% aman dan deterministik untuk skenario ini.

### Skenario C: Trade-off Arsitektur Migrasi Ekosistem Legacy Analytics
* **Konteks:** Sebuah platform analitik Enterprise memiliki 300+ modul analitik yang ditulis selama 7 tahun menggunakan Pandas 1.x, NumPy, Numba (`@jit`), dan ekstensi custom C-Cython. Tim engineering dituntut memodernisasi stack ke Pandas 2.x dengan full PyArrow backend untuk mempercepat I/O dan mengurangi konsumsi RAM cluster Kubernetes.
* **Gejala:** Upaya awal mengaktifkan global setting `pd.set_option("mode.dtype_backend", "pyarrow")` memicu kerusakan massal pada fungsi-fungsi Numba dan custom C-extensions dengan error:
  `TypingError: Failed in nopython mode pipeline (cannot reflect PyArrow type to native buffer)`.
* **Diagnostik & Pertanyaan Arsitektur:**
  1. Analisis benturan teknis mendasar antara *memory view protocol* / *buffer protocol* C-Python native (yang diasumsikan oleh NumPy, Numba, dan Cython) dengan struktur data Arrow columnar (`Array` / `RecordBatch`). Mengapa pointer raw memory C-array konvensional tidak kompatibel langsung dengan Arrow data buffer?
  2. Rancang arsitektur transisi (*migration strategy*) bertingkat (*hybrid-backend strategy*) yang memungkinkan pipeline I/O dan filter/agregasi berat memanfaatkan efisiensi PyArrow, namun tetap mengekspos representasi NumPy array dengan *overhead copy minimal* hanya pada batas antarmuka modul Numba/Cython legacy.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Out-of-Core Financial Ledger Aggregator & Memory Profiler

#### Deskripsi Masalah
Anda ditugaskan membangun engine pemrosesan batch untuk data transaksi pasar finansial (*Tick Data*) berukuran besar. Sistem harus memproses stream file data semi-terstruktur berukuran puluhan juta baris, melakukan standardisasi tipe, memfilter anomali transaksi, dan menghasilkan agregasi statistik volume-weighted average price (VWAP) per emiten saham secara efisien.

#### Functional Requirements
1. **Zero Object Allocation:**
   Seluruh pipeline ingest, transformasi, dan agregasi tidak boleh mengalokasikan satu pun kolom bertipe `object` NumPy. Seluruh tipe data teks, timestamp, dan numerik wajib menggunakan backend PyArrow (`string[pyarrow]`, `timestamp[ns, tz=UTC][pyarrow]`, `int64[pyarrow]`, `double[pyarrow]`).
2. **Robust Null Management:**
   Data transaksi memiliki data `order_id` yang hilang (*null*) pada transaksi jenis tertentu, serta pembatalan volume (`volume` null). Pipeline harus melakukan propagasi null berbasis bitmask secara deterministik tanpa memaksa konversi integer ke float.
3. **Execution Pipeline:**
   - Baca dataset yang terfragmentasi (simulasikan pembacaan 5 juta baris data transaksi).
   - Terapkan CoW untuk memastikan integritas data saat memisahkan data menjadi partisi valid dan anomali (*isolation verification*).
   - Hitung matriks finansial:
     $$\text{VWAP} = \frac{\sum (\text{Price} \times \text{Volume})}{\sum \text{Volume}}$$
     dikelompokkan per `ticker` dan jendela waktu 1 jam (`1H`).
4. **Memory Profiling & Benchmark:**
   Implementasikan komparator performa otomatis menggunakan modul `tracemalloc` dan `time`. Sistem harus membandingkan:
   - Skenario A: Pandas legacy behavior (NumPy backend, no CoW).
   - Skenario B: Pandas 2.x Modern behavior (PyArrow backend, CoW aktif).

#### Constraints (Batasan Teknis)
- **Library Terlarang:** Dilarang menggunakan Polars, DuckDB, Dask, atau PySpark. Solusi murni menggunakan **Pandas 2.2+** dan **PyArrow**.
- **Memory Ceiling:** Puncak alokasi memori (*peak memory consumption*) untuk pemrosesan 5 juta baris pada Skenario B **tidak boleh melampaui 40%** dari alokasi memori pada Skenario A.
- **Strict Mode:** Wajib mengaktifkan:
  ```python
  pd.options.mode.copy_on_write = True
  ```

#### Expected Output
Program Python mandiri (executable script) yang menghasilkan output terminal berformat tabel:

```text
========================================================================================
PERFORMANCE & MEMORY BENCHMARK: PANDAS 1.X (LEGACY) VS PANDAS 2.X (ARROW BACKEND + COW)
========================================================================================
Dataset Rows: 5,000,000 | Tickers: 500 Unique
----------------------------------------------------------------------------------------
Metric                          Legacy (NumPy)          Modern (Arrow + CoW)    Improvement
----------------------------------------------------------------------------------------
Ingestion + Parse Time          X.XX seconds            Y.YY seconds            Z.ZZx Faster
Peak Memory Usage               AAA.AA MB               BBB.BB MB               CC.C% Reduced
VWAP GroupBy Agg Time           X.XX seconds            Y.YY seconds            Z.ZZx Faster
String Column Footprint         AAA.AA MB               BBB.BB MB               CC.C% Reduced
Zero-Copy Slice Mutation Safety FAIL (Warned/Mutated)   PASS (Isolated)         Strict Safe
========================================================================================
Dtype Architecture Validation:
- All dtypes verified as pyarrow backed: [PASS/FAIL]
- No object dtypes detected in df.dtypes: [PASS/FAIL]
```

---

## 5. Knowledge Check & Checklist

Tinjau pemahaman teknis Anda sebelum melanjutkan ke bab berikutnya. Tandai kotak yang sesuai berdasarkan kapabilitas riil Anda.

### Saya harus memahami:
- [ ] Arsitektur fisik memori Apache Arrow: pemisahan Value Buffer, Offset Buffer, dan Validity Bitmap.
- [ ] Dampak penghapusan Sentinel Value (`NaN`) terhadap kestabilan sistem downstream berbasis tipe statis.
- [ ] Mekanisme internal pelacakan dependensi objek pada implementasi Copy-on-Write (CoW) Pandas 2.x.
- [ ] Mengapa Arrow `string[pyarrow]` menyelesaikan problem fragmentasi heap memory yang inheren pada pointer `object` Python.
- [ ] Konsep zero-copy interop melalui protokol Arrow C Data Interface dan batas-batas interoperabilitasnya dengan ekosistem berbasis C-Array contiguous (NumPy/Numba).

### Saya tidak perlu menghafal:
- [ ] Rincian bit-level alignment atau padding byte spesifik pada spesifikasi biner protokol IPC Apache Arrow.
- [ ] Ratusan binding API internal C++ PyArrow (`pyarrow.compute.*`) yang sudah terabstraksi secara mulus di balik API reguler Pandas 2.x.
- [ ] Nama-nama C++ class signature internal pengelola memori Arrow (misal: `arrow::Buffer`, `arrow::MemoryPool`).

### Saya harus bisa melakukan:
- [ ] Mengkonfigurasi runtime Pandas 2.x untuk beroperasi secara global menggunakan backend PyArrow (`dtype_backend="pyarrow"`) dan mode CoW (`mode.copy_on_write = True`).
- [ ] Melakukan profiling konsumsi memori aktual (*deep memory usage*) antar-backend menggunakan metode `df.info(memory_usage="deep")` dan modul low-level Python `tracemalloc`.
- [ ] Mendeteksi dan mendiagnosis degradasi performa akibat *implicit fallback* dari Arrow array ke NumPy array/CPython interpreter.
- [ ] Mengonversi pipeline I/O berbasis CSV dan Parquet untuk memanfaatkan reader multithreaded PyArrow dengan pembatasan skema yang ketat (*explicit casting*).
- [ ] Menulis transformasi data yang sepenuhnya bebas dari bug mutasi tersembunyi (*in-place side effects*) dengan memanfaatkan garansi isolasi CoW.