# Kurikulum: Python Data Analysis
## Kategori: 02-Programming-Languages
### Bab 03: Data Wrangling & Manipulasi Skala Produksi dengan Pandas
#### Modul 01: Arsitektur Internal Pandas: Series, DataFrame, BlockManager, dan Copy-on-Write (CoW)

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Menganalisis dan memetakan representasi memori internal Pandas (*Series*, *DataFrame*, dan *Index*) hingga ke layer *underlying storage* (NumPy Arrays & Extension Arrays).
*   Mendiagnosis performa dan *bottleneck* memori yang disebabkan oleh arsitektur `BlockManager` klasik versus pendekatan modern `ArrayManager`.
*   Mengonfigurasi dan memanfaatkan mesin evaluasi **Copy-on-Write (CoW)** secara deterministik guna mengeliminasi *defensive copying*, mencegah *silent bugs*, dan meniadakan `SettingWithCopyWarning`.
*   Merancang transformasi data berukuran multi-gigabyte dengan footprint memori optimal melalui teknik *zero-copy slicing*, *downcasting* presisi, dan konsolidasi blok memori.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
*   **Python Memory Model:** Pemahaman mendalam mengenai *pass-by-assignment*, alokasi *heap*, *reference counting*, dan modul `sys` / `gc`.
*   **NumPy Internals (Bab 02):** Struktur data `ndarray`, *strides*, skema memori *C-contiguous* vs *Fortran-contiguous*, serta konsep *views* vs *copies*.
*   **Dasar Penggunaan Pandas:** Kemampuan dasar memanggil API Pandas (`pd.DataFrame`, `pd.read_csv`, `.loc`, `.iloc`).

---

### 3. Concept
Pandas tidak menyimpan data tabular sebagai matriks homogen dua dimensi sederhana atau kumpulan list Python. Di balik antarmuka tingkat tinggi `DataFrame`, Pandas mengimplementasikan arsitektur hybrid yang bertumpu pada abstraksi manajemen memori heterogen:

#### Abstraksi DataFrame dan Series
*   **Series:** Struktur data satu dimensi berlabel yang membungkus *array* 1D homogen (baik `numpy.ndarray` C-contiguous maupun `ExtensionArray` seperti Apache Arrow / Categorical) bersama objek `Index`.
*   **DataFrame:** Struktur data dua dimensi berlabel yang merepresentasikan kumpulan *Series*. Namun, alih-alih menyimpan array 1D per kolom secara individual, arsitektur *default* historis Pandas mengelompokkan kolom-kolom bertipe data (*dtype*) serupa ke dalam blok array 2D terpadu melalui subsistem yang disebut **BlockManager**.

#### BlockManager vs ArrayManager
1.  **BlockManager:** 
    *   Mengonsolidasikan semua kolom dengan tipe data identik (misalnya, lima kolom `float64`) ke dalam satu array NumPy 2D (`FloatBlock`).
    *   *Tujuan Historis:* Mengoptimalkan operasi matriks vectorized NumPy secara cross-column.
    *   *Kelemahan Produksi:* Operasi penambahan kolom, mutasi *in-place*, atau konversi tipe memicu *fragmentation* dan konsolidasi memori berbiaya komputasi $O(N \times M)$, memicu lonjakan penggunaan RAM secara mendadak.
2.  **ArrayManager:**
    *   Arsitektur alternatif yang memperlakukan setiap kolom secara independen sebagai array 1D. Menghilangkan overhead konsolidasi blok, namun memiliki karakteristik konkurensi dan vektorisasi horizontal yang berbeda.

```
       DataFrame API (.loc, .iloc, transform)
                        │
                        ▼
                 [ BlockManager ]
      ┌─────────────────┼─────────────────┐
      ▼                 ▼                 ▼
[ FloatBlock (2D) ] [ IntBlock (2D) ] [ ExtensionBlock (1D/Arrow) ]
  Col 0: float64      Col 2: int64      Col 3: string/category
  Col 1: float64
```

#### Paradigma Copy-on-Write (CoW)
Diperkenalkan secara bertahap pada Pandas 2.0 dan menjadi standar *default* pada Pandas 3.0, CoW merevolusi mutabilitas Pandas:
*   Setiap operasi *indexing* atau *slicing* (`df_sub = df[['a', 'b']]` atau `df_slice = df.iloc[0:100]`) menghasilkan **View**, bukan salinan data fisik (**Zero-Copy**).
*   Kedua objek berbagi *underlying memory buffer* yang sama.
*   Alokasi memori baru (*deep copy*) ditunda secara malas (*lazy evaluation*) hingga salah satu objek mencoba memutasi data (`write`).
*   Menghilangkan ambiguitas perilaku mutasi tak terduga (*chained assignment*) dan menghapus total kemunculan peringatan `SettingWithCopyWarning`.

---

### 4. Why
Dalam rekayasa data produksi skala enterprise, pemahaman arsitektur internal ini sangat krusial:
1.  **Mencegah Out-Of-Memory (OOM) Crashes:** 
    Pandas secara default dapat mengonsumsi memori 3 hingga 5 kali lipat ukuran dataset asli di disk jika tipe data tidak didefinisikan secara eksplisit dan konsolidasi `BlockManager` terjadi secara acak.
2.  **Eliminasi Silent Data Corruption:** 
    Sebelum mekanisme CoW, mutasi pada irisan DataFrame (`slice`) terkadang memutasi DataFrame induk, terkadang tidak (tergantung apakah operasi tersebut menghasilkan *view* internal NumPy atau salinan tersembunyi). Inkonsistensi ini dapat merusak integritas data model machine learning atau laporan finansial.
3.  **Efisiensi Pipeline Skala Besar:** 
    Mengetahui kapan Pandas melakukan alokasi ulang memori memungkinkan arsitek sistem merancang kode yang meminimalkan alokasi *garbage collection* (GC), memaksimalkan pemanfaatan L1/L2/L3 *CPU cache*, dan memproses dataset berukuran puluhan gigabyte pada mesin komputasi berspesifikasi terbatas.

---

### 5. What
Komponen-komponen utama penyusun subsistem internal Pandas:

| Komponen | Tipe Abstraksi | Deskripsi Arsitektural |
| :--- | :--- | :--- |
| `Index` | Metadata Imutabel | Array 1D yang mengelola pemetaan label sumbu (*axis labels*) ke posisi ordinal integer (*integer offsets*). Menggunakan hash-table internal untuk lookup $O(1)$. |
| `Series` | Objek Publik 1D | Pembungkus (*wrapper*) tipis di atas array 1D (`ndarray` atau `ExtensionArray`) yang dipasangkan dengan indeks tunggal. |
| `DataFrame` | Objek Publik 2D | Abstraksi tabular dua dimensi yang mengoordinasikan dua `Index` (baris/`index` dan kolom/`columns`) serta mesin data internal. |
| `BlockManager` | Mesin Penyimpanan Internal | Kelas internal (`pandas.core.internals.BlockManager`) yang mengelompokkan array 1D menjadi blok-blok 2D homogen berdasarkan tipe data. |
| `Block` | Unit Penyimpanan Fisik | Kontainer memori homogen internal (`NumpyBlock`, `ExtensionBlock`, `DatetimeBlock`). Mengontrol offset baris/kolom fisik. |
| `ExtensionArray` | Interface Ekstensibilitas | Protokol Pandas untuk tipe non-NumPy (misal: Apache Arrow data, Categorical, DatetimeTZ, Nullable integer). |
| `CoW Engine` | Manajemen Mutasi | Mekanisme pelacak referensi internal (*reference tracking*) yang menduplikasi array hanya saat eksekusi mutasi (*write*) dijalankan. |

---

### 6. How
Berikut adalah alur kerja mekanistik eksekusi *slicing* dan *mutation* di bawah kendali Copy-on-Write:

```
[User Execution: df_slice = df.iloc[0:1000]]
                      │
                      ▼
[Pandas Engine: Evaluasi Sub-Array]
                      │
                      ▼
[Buat Objek DataFrame Baru (df_slice)]
  - Salin metadata Index (Sumbu 0)
  - Salin referensi Kolom (Sumbu 1)
  - Bagikan pointer memori BlockManager/Block yang sama (Zero-Copy)
  - Naikkan status referensi underlying buffer
                      │
                      ▼
[User Execution: df_slice.iloc[0, 0] = 999.0] (Mutasi Terjadi)
                      │
                      ▼
[CoW Check: Apakah buffer dibagi dengan objek lain?]
           │                                 │
         [YA]                               [TIDAK]
           │                                 │
           ▼                                 ▼
[Trigger Deep-Copy Hanya untuk Block Terkait]   [Lakukan Mutasi In-Place]
  - Alokasikan memori baru
  - Lepas referensi ke buffer lama
  - Terapkan modifikasi (999.0)
```

1.  **Evaluasi Axis Alignment:** Ketika `.iloc` atau `.loc` dipanggil, Pandas memetakan irisan label atau integer ke *indexer array* terurut.
2.  **Pointer Reference Sharing:** Tanpa CoW, Pandas mungkin membuat salinan prematur untuk tipe heterogen. Di bawah CoW, Pandas *hanya membuat metadata pembungkus baru* yang menunjuk ke *pointer* data NumPy yang sama.
3.  **Lazy Mutation Decoupling:** Modifikasi nilai data melalui setter memicu pemeriksaan referensi internal. Jika *refcount* pada *underlying buffer* $> 1$, blok memori yang menampung kolom tersebut diduplikasi secara atomik sebelum nilai baru dituliskan.

---

### 7. Analogy
Bayangkan **DataFrame** sebagai sebuah **Perpustakaan Dokumen**:
*   **Tanpa CoW (Klasik):** 
    Ketika seorang staf riset meminjam sebuah bab dokumen (`slice`), perpustakaan terkadang memberikan dokumen asli berkas aslinya, atau terkadang menyalin seluruh berkas ke lembar fotokopi baru tanpa memberi tahu si periset. Jika periset mencoret dokumen tersebut, perpustakaan tidak dapat menjamin apakah dokumen induk ikut tercoret atau tidak (`SettingWithCopyWarning`).
*   **Dengan Copy-on-Write (Modern):** 
    Perpustakaan selalu meminjamkan dokumen dengan instruksi: *"Anda boleh membaca dokumen asli ini secara langsung tanpa biaya fotokopi (Zero-Copy View). Namun, detik pertama pulpen Anda menyentuh kertas untuk mengganti angka di halaman itu, mesin otomatis kami akan secara instan memfotokopi halaman spesifik tersebut untuk Anda modifikasi (Lazy Copy), sehingga arsip pusat tetap terlindungi sempurna."*
*   **BlockManager:** 
    Alih-alih menyimpan setiap lembar dokumen per departemen secara terpisah, perpustakaan membundel seluruh dokumen yang diketik dengan tinta biru ke dalam satu map raksasa (*FloatBlock*), dan tinta hitam ke map lain (*IntBlock*). Membaca bersamaan sangat cepat, tetapi jika Anda ingin mengganti satu dokumen tinta biru menjadi tinta merah, seluruh map raksasa tersebut harus dibongkar dan ditata ulang.

---

### 8. Diagram
Diagram arsitektur alokasi memori internal Pandas:

```
+-------------------------------------------------------------------------------+
|                            PANDAS DATAFRAME                                   |
|                                                                               |
|  Index (Row Labels):    ['row_0', 'row_1', 'row_2', ..., 'row_N']             |
|  Columns (Col Labels):  ['A' (float), 'B' (float), 'C' (int), 'D' (category)] |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
                 +---------------------------------------------+
                 |                BlockManager                 |
                 +----------------------+----------------------+
                                        |
            +---------------------------+---------------------------+
            |                                                       |
            v                                                       v
+-----------------------+   +-----------------------+   +-----------------------+
|      FloatBlock       |   |       IntBlock        |   |    ExtensionBlock     |
|       (2D Array)      |   |      (2D Array)       |   |      (1D Array)       |
|    Dtype: float64     |   |     Dtype: int64      |   |    Dtype: category    |
+-----------------------+   +-----------------------+   +-----------------------+
| Shape: (2, N)         |   | Shape: (1, N)         |   | Shape: (1, N)         |
| Pointer to Kolom A, B |   | Pointer to Kolom C    |   | Pointer to Kolom D    |
+-----------+-----------+   +-----------+-----------+   +-----------+-----------+
            |                           |                           |
            v                           v                           v
+-----------------------+   +-----------------------+   +-----------------------+
| Contiguous C-Memory   |   | Contiguous C-Memory   |   | Categorical Storage   |
| [Col A data...]       |   | [Col C data...]       |   | Codes: [0, 1, 0...]   |
| [Col B data...]       |   |                       |   | Categories: ['X','Y'] |
+-----------------------+   +-----------------------+   +-----------------------+

======================= COPY-ON-WRITE MUTATION BEHAVIOR ========================

[Initial State: View Created]
df_master [Pointer X] --------+
                              |---> Memory Buffer [Data Payload: [1.1, 2.2, 3.3]]
df_sliced [Pointer Y] --------+

[State After: df_sliced.iloc[0, 0] = 99.9]
df_master [Pointer X] ------------> Memory Buffer [Data Payload: [1.1, 2.2, 3.3]]
                                    (Unchanged, Protected)

df_sliced [Pointer Z (NEW)] ------> New Memory Buffer [Data Payload: [99.9, 2.2, 3.3]]
                                    (Deep-copied on-demand strictly for df_sliced)
```

---

### 9. Simple Example
Skrip ini mendemonstrasikan perilaku `BlockManager` internal dan aktivasi **Copy-on-Write** pada Pandas modern.

```python
import numpy as np
import pandas as pd

# 1. Mengaktifkan mekanisme Copy-on-Write secara eksplisit
pd.options.mode.copy_on_write = True

# 2. Inisialisasi DataFrame heterogen
df = pd.DataFrame(
    {
        "a": np.array([1.0, 2.0, 3.0], dtype=np.float64),
        "b": np.array([4.0, 5.0, 6.0], dtype=np.float64),
        "c": np.array([10, 20, 30], dtype=np.int64),
    }
)

# 3. Inspeksi internal BlockManager (Struktur privat Pandas)
# Catatan: Akses _mgr hanya untuk tujuan edukasi/debugging arsitektural
print("=== STRUKTUR INTERNAL BLOCKMANAGER ===")
print(df._mgr)

# 4. Demonstrasi Zero-Copy Slicing
subset = df[["a", "b"]]

# Memeriksa apakah memori dibagi (View)
# Di bawah CoW, subset awal adalah VIEW sempurna
shares_memory = np.shares_memory(df["a"].to_numpy(), subset["a"].to_numpy())
print(f"\nApakah 'df' dan 'subset' berbagi memori fisik? {shares_memory}")

# 5. Mutasi pada subset -> Memicu mekanisme Copy-on-Write
subset.iloc[0, 0] = 999.0

# 6. Verifikasi Integritas Data
print("\n=== SETELAH MUTASI PADA SUBSET ===")
print("DataFrame Induk (df['a'][0]):", df.iloc[0]["a"])  # Tetap 1.0 (Aman)
print("Subset Mutasi (subset['a'][0]):", subset.iloc[0]["a"])  # Berubah 999.0

# Memeriksa kembali pemisahan memori
shares_memory_post = np.shares_memory(
    df["a"].to_numpy(), subset["a"].to_numpy()
)
print(
    f"Apakah 'df' dan 'subset' masih berbagi memori? {shares_memory_post}"
)
```

---

### 10. Practical Example
Implementasi kelas pemroses metrik finansial berkinerja tinggi yang mengaudit konsumsi memori internal, mendowncast data secara presisi, dan menghindari konsolidasi blok redundan.

```python
from __future__ import annotations
import gc
import sys
from typing import Dict, Any
import numpy as np
import pandas as pd


class HighThroughputDataSanitizer:
    """Sanitizer data berkinerja tinggi dengan instrumentasi profil memori

    dan mitigasi fragmentasi BlockManager.
    """

    def __init__(self, enable_cow: bool = True) -> None:
        pd.options.mode.copy_on_write = enable_cow
        self.co_w_enabled: bool = enable_cow

    def analyze_memory_footprint(self, df: pd.DataFrame) -> dict[str, Any]:
        """Audit memori mendalam (Deep Memory Audit) per blok dan tipe data."""
        deep_usage = df.memory_usage(deep=True)
        total_bytes = deep_usage.sum()

        block_structure = {}
        if hasattr(df, "_mgr"):
            for idx, blk in enumerate(df._mgr.blocks):
                block_structure[f"block_{idx}_{blk.dtype}"] = {
                    "shape": blk.shape,
                    "columns": [df.columns[loc] for loc in blk.mgr_locs],
                }

        return {
            "total_megabytes": round(total_bytes / (1024 * 1024), 3),
            "columns_detail_kb": (deep_usage // 1024).to_dict(),
            "internal_blocks": block_structure,
        }

    def optimize_types_and_consolidate(
        self, raw_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Mengonversi tipe heterogen ke representasi teringkas dan mengonsolidasi

        alokasi memori internal.
        """
        # Mulai dengan salinan independen
        optimized_df = raw_df.copy()

        # 1. Downcast integer dan float ke presisi terendah yang aman
        for col in optimized_df.select_dtypes(include=["int64"]).columns:
            optimized_df[col] = pd.to_numeric(
                optimized_df[col], downcast="integer"
            )

        for col in optimized_df.select_dtypes(include=["float64"]).columns:
            optimized_df[col] = pd.to_numeric(
                optimized_df[col], downcast="float"
            )

        # 2. Konversi object-strings dengan kardinalitas rendah ke category
        for col in optimized_df.select_dtypes(include=["object"]).columns:
            num_unique = len(optimized_df[col].unique())
            num_total = len(optimized_df[col])
            # Ambang batas kardinalitas: < 40% unik dikonversi ke categorical
            if num_unique / num_total < 0.40:
                optimized_df[col] = optimized_df[col].astype("category")

        # 3. Evaluasi Garbage Collection
        gc.collect()

        return optimized_df


# --- Pipeline Execution ---
if __name__ == "__main__":
    np.random.seed(42)
    n_rows = 500_000

    # Simulasi data transaksi mentah
    payload: dict[str, np.ndarray] = {
        "transaction_id": np.arange(n_rows, dtype=np.int64),
        "account_id": np.random.randint(1000, 9999, size=n_rows, dtype=np.int64),
        "amount": np.random.uniform(10.0, 5000.0, size=n_rows).astype(np.float64),
        "fee": np.random.uniform(0.1, 50.0, size=n_rows).astype(np.float64),
        "status": np.random.choice(
            ["PENDING", "SETTLED", "REJECTED"], size=n_rows
        ),
    }

    raw_transactions = pd.DataFrame(payload)

    engine = HighThroughputDataSanitizer(enable_cow=True)

    print("=== PROFILING SEBELUM OPTIMASI ===")
    profile_before = engine.analyze_memory_footprint(raw_transactions)
    print(f"Total Memori: {profile_before['total_megabytes']} MB")
    print("Blok Internal:", profile_before["internal_blocks"])

    optimized_transactions = engine.optimize_types_and_consolidate(
        raw_transactions
    )

    print("\n=== PROFILING SETELAH OPTIMASI ===")
    profile_after = engine.analyze_memory_footprint(optimized_transactions)
    print(f"Total Memori: {profile_after['total_megabytes']} MB")
    print("Blok Internal:", profile_after["internal_blocks"])

    compression_ratio = (
        1
        - (
            profile_after["total_megabytes"]
            / profile_before["total_megabytes"]
        )
    ) * 100
    print(f"\nPenghematan Memori Fisik: {compression_ratio:.2f}%")
```

---

### 11. Real World Example
**Kasus Industri: Platform Risk Engine & Anti-Money Laundering (AML) di Tier-1 FinTech Bank.**

*   **Latar Belakang Kasus:** Pipeline agregasi transaksi AML mengevaluasi 10 juta event per jam. Setiap batch memicu proses *windowing*, *feature extraction*, dan *flagging*. 
*   **Permasalahan:** Mesin pipeline (AWS ECS Container berkapasitas memori 16GB) sering mati secara mendadak akibat *Out-of-Memory (OOM-Killed)*. Investigasi menunjukkan bahwa saat mengeksekusi *slicing* kompleks:
    ```python
    # Pola lama bermasalah (Pandas 1.x / Non-CoW)
    flagged = df[df["amount"] > 10000]
    flagged["risk_score"] = calculate_risk(flagged)  # Memicu SettingWithCopyWarning
```
    Pandas melakukan duplikasi memori defensif (*defensive full copy*) berkali-kali untuk setiap sub-operasi. Di samping itu, `BlockManager` secara reguler melakukan konsolidasi array 2D yang memecah blok memori kontigu, meningkatkan fragmentasi memori *heap* sebesar 350%.
*   **Solusi Rekayasa:**
    1.  Upgrade *runtime* ke Pandas 2.2+ dengan mengunci instruksi operasional `pd.set_option("mode.copy_on_write", True)`.
    2.  Menghentikan pola mutasi berantai (*chained assignment*) dan beralih ke pembuatan kolom deklaratif menggunakan `.assign()` atau konstruksi array NumPy murni sebelum injeksi ke DataFrame.
    3.  Mengganti tipe kolom string teks reguler berbasis NumPy `object` ke PyArrow Backend (`string[pyarrow]`), yang merepresentasikan array string secara *compact zero-copy* di luar heap Python.
*   **Hasil:**
    *   Pengurangan alokasi puncak memori (*peak memory consumption*) dari 14.8 GB menjadi 3.2 GB (Penurunan footprint memori sebesar 78%).
    *   Peningkatan throughput pemrosesan dari 22 menit menjadi 6.5 menit per batch data transaksi.
    *   Eliminasi total crash OOM pada kluster komputasi container.

---

### 12. Trade-offs

| Parameter | Pandas BlockManager (Default) | Pandas ArrayManager (`mode.data_manager = "array"`) | Copy-on-Write (Aktif) | Non-CoW (Historis) |
| :--- | :--- | :--- | :--- | :--- |
| **Operasi Cross-Column (misal: Transposisi, Aggregasi matriks)** | Sangat Cepat ($O(1)$ untuk array homogen terintegrasi) | Lebih Lambat (Harus mengonsolidasi array 1D menjadi matriks 2D) | Tidak Ada Penalti | Cepat, tapi tidak deterministik |
| **Penyisipan Kolom Baru (*Column Insertion*)** | Mahal ($O(N \times M)$) jika memicu konsolidasi blok | Sangat Murah ($O(1)$ pointer append) | Tidak Ada Penalti | Lambat jika terjadi realokasi blok |
| **Footprint Memori Slicing** | Bervariasi, rawan *defensive copy* | Stabil per-kolom | Minimal ($O(1)$ alokasi metadata awal) | Berpotensi menduplikasi seluruh dataset |
| **Kompleksitas Debugging** | Tinggi (Status view vs copy terselubung) | Rendah (Setiap kolom berdiri sendiri) | Sangat Rendah (Perilaku mutasi bersifat deterministik) | Ekstrem (Penyebab `SettingWithCopyWarning`) |
| **Overhead Metadata** | Rendah (Sedikit blok untuk banyak kolom) | Tinggi jika ribuan kolom (banyak objek array 1D) | Ada sedikit overhead pelacakan referensi | Rendah |

---

### 13. When To Use
Gunakan arsitektur dan pola CoW Pandas ketika:
*   Membangun pipeline data batch ETL/ELT berukuran sedang hingga besar (ratusan megabyte hingga batas RAM mesin).
*   Membutuhkan jaminan integritas data tinggi, di mana mutasi pada suatu subset tidak boleh memengaruhi DataFrame induk dalam kondisi apa pun.
*   Dataset memiliki tipe data heterogen yang memerlukan operasi manipulasi kolom secara intensif (*feature engineering*).
*   Melakukan migrasi dan standarisasi *codebase* menuju arsitektur Pandas modern (versi 2.x ke atas / Pandas 3.0-ready).

---

### 14. When NOT To Use
Jangan gunakan Pandas atau hindari arsitektur internalnya ketika:
*   **Dataset Melebihi Kapasitas RAM Fisik (Out-of-Core Processing):** Gunakan **Polars**, **DuckDB**, atau **Apache Spark**. Pandas tidak memiliki *query planner* berbasis lazy execution untuk optimasi disk-to-memory streaming.
*   **Latency-Critical Streaming Pipeline (< 1-10 milidetik):** Overhead pembuatan objek Python, validasi indeks, dan abstraksi BlockManager Pandas terlalu lambat. Gunakan array homogen NumPy primitif atau modul bertipe statis (C Extensions, Cython, atau Rust).
*   **Iterasi Baris-per-Baris (*Row-by-Row Iteration*):** Pandas dirancang untuk eksekusi kolumnar tervektorisasi. Operasi iteratif baris via `.iterrows()` adalah anti-pattern berat.

---

### 15. Common Mistakes
1.  **Chained Assignment Mutasi Gagal:**
    ```python
    # SALAH (Menghasilkan bugs / tidak berefek pada CoW)
    df[df["status"] == "FAILED"]["retry_count"] = 5

    # BENAR (Eksplisit dan kompatibel secara arsitektural)
    df.loc[df["status"] == "FAILED", "retry_count"] = 5
```
2.  **Mengabaikan Dtype `object` pada Kolom String/Teks:**
    Menyimpan string sebagai tipe `object` menghasilkan array pointer yang mengarah ke objek Python string di berbagai alamat heap acak (*cache misses* parah). Gunakan tipe `string[pyarrow]` atau `category`.
3.  **Mengasumsikan `.copy()` Selalu Diperlukan:**
    Sebelum CoW, developer sering menulis `sub_df = df.iloc[0:100].copy()` secara defensif untuk menghindari warning. Di bawah CoW, pemanggilan `.copy()` eksplisit justru membuang memori karena CoW sudah menjamin pemisahan mutasi secara otomatis (*lazy copying*).
4.  **Melakukan Concatenation di Dalam Loop:**
    ```python
    # SALAH: Menghasilkan realokasi BlockManager N kali (Kompleksitas O(N^2))
    result = pd.DataFrame()
    for chunk in data_stream:
        result = pd.concat([result, chunk])

    # BENAR: Konsolidasi buffer list satu kali di memori
    accumulator = [chunk for chunk in data_stream]
    result = pd.concat(accumulator, ignore_index=True)
```

---

### 16. Best Practices (Production Checklist)
*   [ ] **Aktifkan CoW Secara Global:** Konfigurasikan `pd.options.mode.copy_on_write = True` pada file konfigurasi inisialisasi modul atau *entry point* aplikasi.
*   [ ] **Tetapkan Skema Tipe Data Eksplisit:** Definisikan parameter `dtype` saat memuat data melalui `pd.read_csv()` atau `pd.read_parquet()` untuk memblokir inferensi tipe otomatis yang memboroskan memori.
*   [ ] **Terapkan Downcasting Numerik:** Konversikan nilai `float64` ke `float32` jika presisi 7 desimal mencukupi; ubah `int64` ke `int32` atau `int16`.
*   [ ] **Gunakan Extension Dtypes Modern:** Migrasikan kolom teks ke `string[pyarrow]` untuk memotong alokasi memori heap Python hingga 70%.
*   [ ] **Verifikasi Ukuran Memori Riil:** Hindari audit dangkal melalui `df.info()`. Selalu gunakan parameter `df.memory_usage(deep=True)` guna menghitung alokasi memori sebenarnya dari tipe `object`.
*   [ ] **Hindari Operasi In-Place Fiktif:** Parameter seperti `df.dropna(inplace=True)` tidak lagi menjamin performa in-place riil di bawah arsitektur modern dan akan didepresiasi. Biasakan menggunakan reassignment: `df = df.dropna()`.

---

### 17. Troubleshooting

#### 1. Masalah: `SettingWithCopyWarning` Muncul Tanpa Henti
*   **Penyebab Root-Cause:** Pandas mendeteksi adanya mutasi pada objek yang merupakan *view* tidak pasti dari DataFrame lain di bawah *runtime* non-CoW.
*   **Solusi Definitif:** 
    Aktifkan Copy-on-Write untuk menonaktifkan kode warning usang ini:
    ```python
    pd.options.mode.copy_on_write = True
```
    Pastikan penulisan dilakukan menggunakan indeks aksis tunggal: `df.loc[kondisi, 'target_kolom'] = nilai`.

#### 2. Masalah: Lonjakan Memori Tajam Saat Memodifikasi Kolom Tunggal
*   **Penyebab Root-Cause:** Kolom tersebut berbagi `FloatBlock` 2D raksasa dengan 50 kolom lainnya di dalam `BlockManager`. Saat kolom tersebut dimodifikasi atau diubah dtypenya, Pandas menduplikasi atau merekonstruksi seluruh array 2D tersebut.
*   **Solusi Definitif:** 
    Pisahkan kolom tersebut dari blok komposit dengan mengisolasi referensi dtypenya, atau jalankan evaluasi di bawah `ArrayManager`:
    ```python
    # Jalankan interpretasi terisolasi
    pd.options.mode.data_manager = "array"  # Opsional: Uji coba per-kolom array
```

#### 3. Masalah: DataFrame Mengonsumsi Memori Berlipat Pasca Transformasi Bertingkat
*   **Penyebab Root-Cause:** Objek `Index` atau `BlockManager` lama tertahan di memori karena referensi tersembunyi pada irisan (*slice*) data yang belum dibersihkan oleh Garbage Collector.
*   **Solusi Definitif:**
    Putus rantai referensi metadata dengan me-reset atau mengkloning DataFrame secara terputus:
    ```python
    df_clean = df.reset_index(drop=True).copy(deep=False)
    import gc

    gc.collect()
```

---

### 18. Exercise
Selesaikan skrip berikut untuk membuktikan pemahaman Anda mengenai *BlockManager internals* dan *Copy-on-Write*.

**Instruksi Tugas:**
1.  Buat `DataFrame` yang memiliki 2 kolom bertipe `int32` dan 2 kolom bertipe `float32`.
2.  Inspeksi panjang blok `_mgr.blocks` (Buktikan bahwa ada 2 blok internal yang terbentuk).
3.  Aktifkan CoW. Buat irisan (*slice*) data untuk 1 kolom `int32`.
4.  Lakukan verifikasi bahwa `np.shares_memory` bernilai `True`.
5.  Ubah salah satu nilai pada irisan tersebut. Tunjukkan bahwa memori sekarang telah terpisah secara otomatis (`np.shares_memory` bernilai `False`).

```python
# Tuliskan kode implementasi Anda di bawah ini:
import numpy as np
import pandas as pd

# Konfigurasi CoW
pd.options.mode.copy_on_write = True

# 1. Konstruksi DataFrame
df_task = pd.DataFrame(
    {
        "int_1": np.array([1, 2, 3], dtype=np.int32),
        "int_2": np.array([4, 5, 6], dtype=np.int32),
        "flt_1": np.array([1.1, 2.2, 3.3], dtype=np.float32),
        "flt_2": np.array([4.4, 5.5, 6.6], dtype=np.float32),
    }
)

# 2. Inspeksi Jumlah Blok
# TODO: Cetak jumlah blok internal pada df_task._mgr.blocks
num_blocks = ...
print(f"Jumlah blok internal: {num_blocks}")

# 3. Slicing
# TODO: Buat slice kolom 'int_1' ke dalam variabel target_slice
target_slice = ...

# 4. Verifikasi Pembagian Memori
# TODO: Lakukan evaluasi memory share antara df_task['int_1'] dan target_slice
shared_init = ...
print(f"Apakah memori dibagi sebelum mutasi? {shared_init}")

# 5. Mutasi dan Verifikasi CoW
# TODO: Ubah indeks ke-0 dari target_slice menjadi 999
# TODO: Lakukan evaluasi ulang memory share
shared_after = ...
print(f"Apakah memori dibagi setelah mutasi? {shared_after}")
```

#### Jawaban Exercise:
```python
# Kunci Validasi:
num_blocks = len(df_task._mgr.blocks)  # Bernilai 2 (Satu IntBlock, Satu FloatBlock)
target_slice = df_task[["int_1"]]
shared_init = np.shares_memory(
    df_task["int_1"].to_numpy(), target_slice["int_1"].to_numpy()
)  # True
target_slice.iloc[0, 0] = 999
shared_after = np.shares_memory(
    df_task["int_1"].to_numpy(), target_slice["int_1"].to_numpy()
)  # False
```

---

### 19. Challenge
**Deskripsi Skenario:**
Anda adalah Principal Data Engineer yang menerima kode warisan (*legacy pipeline*) pemrosesan log infrastruktur. Pipeline ini sering mengalami crash OOM pada server produksi ketika memproses file log berukuran 2.5 GB. Kode legacy ini ditulis dengan banyak anti-pattern mutasi in-place dan konversi tipe yang salah:

```python
# KODE LEGACY BERMASALAH (JANGAN DIJALANKAN DI PRODUKSI)
def process_logs_legacy(file_path):
    df = pd.read_csv(file_path)
    # Masalah 1: Banyak chained assignments
    # Masalah 2: Tipe object dibiarkan tidak terkendali
    # Masalah 3: Memory footprint membengkak 4x lipat
    df["response_code"] = df["response_code"].astype(float)
    df["endpoint"] = df["endpoint"].astype(str)
    for i in range(len(df)):
        if df["response_code"][i] >= 500:
            df["is_error"][i] = 1
        else:
            df["is_error"][i] = 0
    return df
```

**Misi Anda:**
Tulis ulang fungsi di atas ke dalam arsitektur kelas berstandar enterprise bernama `ProductionLogProcessor`:
1.  Gunakan PyArrow engine saat memuat / mengelola string (`string[pyarrow]`).
2.  Aktifkan dan manfaatkan mekanisme Copy-on-Write (CoW).
3.  Eliminasi iterasi baris sepenuhnya; ganti dengan vektorisasi NumPy / Pandas kondisional teroptimasi (`np.where` atau boolean masking).
4.  Lakukan downcasting tipe data: `response_code` menjadi `int16`, `is_error` menjadi `bool` atau `int8`.
5.  Sediakan fungsi instrumentasi yang membuktikan bahwa kode refaktor Anda mengonsumsi memori **kurang dari 30%** dibandingkan implementasi tanpa optimalisasi tipe data.

```python
# Implementasikan arsitektur solusi kelas Anda di sini:
class ProductionLogProcessor:

    def __init__(self) -> None:
        pd.options.mode.copy_on_write = True

    def process_logs_optimized(self, df_input: pd.DataFrame) -> pd.DataFrame:
        """Eksekusi alur data berkecepatan tinggi dengan footprint memori minimal."""
        # Terapkan refactoring komprehensif di sini
        pass
```

---

### 20. Summary
*   **Arsitektur DataFrame:** Pandas DataFrame bukanlah matriks datar sederhana, melainkan koordinasi metadata indeks di atas subsistem **BlockManager** yang mengelompokkan array 1D menjadi blok-blok 2D berdasarkan tipe data.
*   **BlockManager Limitations:** Meskipun menguntungkan untuk operasi matriks 2D homogen, BlockManager menimbulkan penalti komputasi dan memori yang signifikan saat terjadi insersi, penghapusan, atau downcasting kolom secara heterogen.
*   **Revolusi Copy-on-Write (CoW):** Standar modern Pandas 2.x/3.0 menerapkan CoW secara menyeluruh, di mana *slicing* selalu menghasilkan *view* (Zero-Copy), sementara alokasi memori fisik baru ditangguhkan sampai mutasi eksplisit dilakukan.
*   **Stabilitas Produksi:** Penggunaan CoW secara fundamental mematikan bugs laten mutasi tak terduga (*chained assignment*), menghapus `SettingWithCopyWarning`, serta menyederhanakan siklus alokasi memori pada sistem skala enterprise.