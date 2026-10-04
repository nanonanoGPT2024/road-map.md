# Bab 03: DAX Core Evaluation Contexts & Engine Internals — Module 01

---

## 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah Komponen Eksekusi DAX Engine**: Mengidentifikasi secara presisi kapan evaluasi berpindah antara *Formula Engine* (FE) yang *single-threaded* dan *Storage Engine* (SE/VertiPaq) yang *multi-threaded*.
- **Mendiferensiasikan Dua Pilar Konteks Evaluasi**: Menjelaskan siklus hidup dan perbedaan mendasar antara *Row Context* dan *Filter Context* tanpa ambiguitas semantik.
- **Menguasai Mekanika Context Transition**: Menjelaskan dan memprediksi determinisme dari *Context Transition* yang diinisiasi oleh kalkulasi berbasis `CALCULATE` dan `CALCULATETABLE` pada level baris.
- **Memetakan Kompresi Data VertiPaq**: Menganalisis efisiensi kompresi kolom (*Dictionary Encoding*, *Run-Length Encoding* [RLE], dan *Bit-Packing*) berdasarkan distribusi kardinalitas data.
- **Mendiagnosis Bottleneck Performa via Tracing**: Mengisolasi pola anti-pattern DAX menggunakan metrik *DAX Studio Server Timings* (membedakan *FE CPU/Duration* vs *SE CPU/Duration* dan meminimalisir pembuatan *Data Cache* berukuran masif).

---

## 2. Concept Overview (Mental Model & Teori Inti)

DAX (*Data Analysis Expressions*) bukan bahasa prosedural maupun murni berorientasi objek; DAX adalah bahasa fungsional berbasis relasi tabular dengan evaluasi berbasis konteks (*context-driven functional language*).

### Mental Model Evaluasi DAX
Eksekusi sebuah ekspresi DAX selalu beroperasi di dalam suatu **Evaluation Context**. Evaluation context mendefinisikan subset baris data yang terlihat oleh mesin (*engine*) pada setiap tahap evaluasi. Konteks ini terbagi menjadi dua:

1. **Row Context (Konteks Baris)**: 
   - Konsep: Mengetahui *posisi baris saat ini* ("baris mana yang sedang saya proses?").
   - Kemunculan: Dibuat secara otomatis di dalam *Calculated Columns* atau melalui fungsi iterator eksplisit seperti `SUMX`, `FILTER`, `AVERAGEX`, `MAXX`.
   - Batasan Kritis: **Row Context tidak memfilter model data secara otomatis**. Relasi antar tabel tidak aktif secara inheren di dalam Row Context murni.

2. **Filter Context (Konteks Filter)**:
   - Konsep: Kumpulan filter (set nilai diskrit untuk kolom tertentu) yang membatasi data tabular di seluruh model.
   - Kemunculan: Diinjeksikan oleh visual di kanvas Power BI (baris/kolom matriks, slicer, filter pane) atau dimodifikasi secara programmatic via fungsi `CALCULATE` dan `CALCULATETABLE`.
   - Propagasi: Berjalan melintasi relasi model (mengikuti arah panah relasi 1-ke-banyak atau *bidirectional*) berdasarkan konsep **Expanded Tables** (*tabel yang diperluas*).

```
   ┌─────────────────────────────────────────────────────────────────┐
   │                       EVALUATION CONTEXT                        │
   ├───────────────────────────────┬─────────────────────────────────┤
   │          Row Context          │         Filter Context          │
   ├───────────────────────────────┼─────────────────────────────────┤
   │ Menentukan baris aktif saat   │ Menentukan subset data aktif di │
   │ iterasi.                      │ seluruh tabel dalam model.      │
   │ Prosedural / Kursor virtual   │ Set-oriented / Relasional       │
   │ Tidak otomatis memfilter      │ Memfilter data dan merambat     │
   │ baris tabel berelasi.         │ melalui relasi yang valid.      │
   └───────────────────────────────┴─────────────────────────────────┘
                                   ▲
                                   │ Context Transition
                                   │ (CALCULATE / CALCULATETABLE)
   ┌───────────────────────────────┴─────────────────────────────────┐
   │ Mengonversi nilai unik baris aktif saat ini menjadi filter      │
   │ eksplisit pada seluruh kolom tabel yang sedang diiterasi.       │
   └─────────────────────────────────────────────────────────────────┘
```

### Context Transition
*Context Transition* adalah transformasi di mana DAX mengubah nilai dari setiap kolom pada baris aktif di *Row Context* menjadi satu set *Filter Context* yang ekuivalen. Transformasi ini terjadi **hanya** ketika ekspresi `CALCULATE()` atau `CALCULATETABLE()` dipanggil di dalam lingkungan yang sedang memiliki *Row Context* aktif (termasuk implicit invocation saat memanggil *Measure* di dalam iterator atau *Calculated Column*).

---

## 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada semantic model enterprise (dataset berukuran puluhan gigabyte hingga terabyte dengan ratusan juta baris), pemahaman mekanistik ini menentukan apakah kueri analitik dieksekusi dalam **20 milidetik** atau mengalami **Query Timeout (10+ detik)** hingga **Memory Exhaustion (OOM Spill)**.

### Kegagalan Umum di Lapangan:
1. **Context Transition di dalam Loop Masif (Cartesian Iteration)**: Menjalankan kalkulasi *measure* di dalam iterator `SUMX(FactSales, [ImplicitMeasure])` pada 100 juta baris akan memaksa VertiPaq menginisiasi 100 juta *filter context* independen. Hal ini membanjiri Formula Engine dan membuat thread CPU terkunci.
2. **Formula Engine Bottleneck**: Formula Engine (FE) bersifat *single-threaded*. Jika logika DAX menggunakan fungsi non-vektor (misal: kondisional string kompleks berbasis iterasi baris), engine tidak dapat mendorong (*push-down*) kueri ke VertiPaq Storage Engine (SE). Akibatnya, SE mengekstrak seluruh tabel mentah tanpa agregasi ke FE Data Cache, menghabiskan memori RAM.
3. **Data Model Bloat Akibat Salah Encoding**: Ketidaktahuan tentang VertiPaq encoding menyebabkan developer membuat ID transaksi unik (kardinalitas tinggi, string acak) di tabel fakta, yang menghancurkan efisiensi *Dictionary Encoding* dan *Run-Length Encoding* (RLE), melipatgandakan ukuran footprint RAM hingga 10x lipat.

---

## 4. Arsitektur & Diagram Komponen

Arsitektur Analysis Services/Power BI Tabular Engine membagi pemrosesan menjadi dua subsistem independen namun terkoordinasi:

```
                                      CLIENT QUERY (DAX / MDX)
                                                 │
                                                 ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     FORMULA ENGINE (FE)                                           │
│  - Single-threaded execution per query request                                                    │
│  - Query Parsing, Syntax Tree Validation, Logical/Physical Plan Generation                        │
│  - Complex Windowing, Inter-table Stitching, Procedural Conditionals, String Manipulations        │
└──────────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                   │
                         Generates Subqueries      │ Receives Uncompressed
                         (Internal xmSQL Queries)  │ Data Caches
                                                   │
                                                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                VERTIPAQ STORAGE ENGINE (SE)                                       │
│  - Multi-threaded, vectorized in-memory columnar execution                                        │
│  - Scan, Filter, Hash Join, Basic Group By & Aggregation (SUM, MIN, MAX, COUNT, DISTINCTCOUNT)     │
├──────────────────────────────────────────────────┬────────────────────────────────────────────────┤
│            In-Memory Data Structures             │               Compression Units                │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────┐  │  ┌───────────────────┐  ┌───────────────────┐  │
│  │ Columnar Storage Partition                 │  │  │ Dictionary Hash   │  │ Bit-Packed Data   │  │
│  ├────────────────────────────────────────────┤  │  │ Mapping IDs      │  │ Column Streams    │  │
│  │ Segment 1 (e.g. 8M rows)                   │  │  └───────────────────┘  └───────────────────┘  │
│  ├────────────────────────────────────────────┤  │  ┌──────────────────────────────────────────┐  │
│  │ Segment 2 (e.g. 8M rows)                   │  │  │ Run-Length Encoding (RLE) Triplet Indices│  │
│  └────────────────────────────────────────────┘  │  └──────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Jalur Data (Query Lifecycle):
1. **Parsing & Planning**: FE menerima kueri DAX, membuat *Query Tree*, dan menyusun *Physical Query Plan*.
2. **SE Query Dispatch**: FE mengisolasi operasi yang dapat diparalelisasi dan menerjemahkannya ke dalam bahasa internal **xmSQL** (*bukan SQL standar, melainkan representasi kueri internal columnar*).
3. **Storage Engine Parallel Scan**: SE membagi pembacaan segmen data kolom (default per 8 juta baris per segmen) ke banyak core thread CPU. Data diekstrak langsung dari bentuk terkompresi.
4. **Data Cache Handoff**: SE mengumpulkan subtotal atau set baris terfilter ke dalam struktur data RAM transien yang disebut **Data Cache**.
5. **FE Post-processing**: FE mengambil data cache tersebut, menjalankan operasi komputasi non-SE (misal: divisi akhir, perbandingan skalar, pembentukan format JSON tabular), dan mengembalikannya ke klien.

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Mekanika Internal VertiPaq Compression
VertiPaq mengandalkan tiga lapisan kompresi hirarkis pada data kolom:

1. **Dictionary Encoding**:
   Nilai diskrit dari kolom dipetakan ke dalam array integer (*Index ID*).
   *Contoh:*
   Kolom Asli: `["IDN", "SGP", "IDN", "MYS", "IDN"]`  
   Dictionary: `0 -> "IDN"`, `1 -> "MYS"`, `2 -> "SGP"`  
   Data Terkodekan: `[0, 2, 0, 1, 0]`

2. **Column Bit-Packing**:
   Jika nilai unik maksimum dari suatu kamus adalah $N$, VertiPaq hanya mengalokasikan $k$ bit per nilai, di mana:
   $$k = \lceil \log_2(N) \rceil$$
   Untuk 3 nilai unik (ID 0, 1, 2), VertiPaq hanya memerlukan $\lceil \log_2(3) \rceil = 2$ bit per baris, bukan 32/64 bit standar integer.

3. **Run-Length Encoding (RLE)**:
   RLE mengompresi sekuens nilai berulang yang berurutan. Formatnya tersimpan dalam triplet internal:
   `{Value ID, Start Row, Row Count}`.
   *Contoh:* Kolom dengan data terurut `[0, 0, 0, 0, 1, 1, 2, 2, 2]` dikompresi menjadi:
   - `{0, 0, 4}`
   - `{1, 4, 2}`
   - `{2, 6, 3}`
   RLE sangat efektif jika data fisik tabel diurutkan berdasarkan kolom berkardinalitas rendah terlebih dahulu.

### 5.2 Aljabar Filter Context & CALCULATE
Secara matematis, `CALCULATE(Expression, Filter_1, Filter_2, ..., Filter_N)` beroperasi dengan urutan langkah deterministik:

1. **Salin Filter Context Awal**: Duplikasi filter context yang ada di visual/environment.
2. **Evaluasi Modifiers**: Evaluasi argumen filter eksplisit (misal: `ALL()`, `USERELATIONSHIP()`, `KEEPFILTERS()`).
3. **Eksekusi Context Transition (Jika ada)**:
   Jika ekspresi dipanggil di bawah *Row Context*, ambil seluruh nilai atribut pada baris saat ini, bentuk predikat tuple:
   $$(Col_1 = Val_1 \land Col_2 = Val_2 \land \dots \land Col_m = Val_m)$$
   Suntikkan predikat ini sebagai filter baru.
4. **Filter Overwrite / Merge**:
   Argumen filter baru dari `Filter_1 ... Filter_N` akan menimpa (*overwrite*) filter yang sudah ada pada kolom yang sama, kecuali dibungkus dengan `KEEPFILTERS()`.
5. **Aplikasi Relasi & Expanded Tables**:
   Subset tabel difilter secara transversal mengikuti hubungan *primary-foreign key*.
6. **Evaluasi Ekspresi**: Evaluasi kalkulasi skalar/agregasi pada kondisi Filter Context baru tersebut.
7. **Restorasi Context**: Mengembalikan konteks asli setelah kalkulasi selesai.

---

## 6. Production-Ready Code Implementation

Berikut adalah skrip diagnostik otomatisasi untuk menguji Context Transition dan Engine Health menggunakan **Python (Semantic-Link / ADOMD)** serta implementasi DAX dengan pola enterprise defensive standard.

### 6.1 Implementasi DAX: Pola Aman Menghindari Context Transition Overhead

```dax
/*
  SCENARIO: Menghitung persentase kontribusi penjualan pelanggan 
  terhadap total kategori produk, mengisolasi Context Transition 
  hanya pada level agregasi, bukan iterasi baris individual.
*/

// =========================================================================
// ANTI-PATTERN: Context Transition di dalam loop baris tabel fakta
// SE bottleneck: Jutaan subquery xmSQL / FE memory spill
// =========================================================================
[Total Sales Inefficient] := 
SUMX(
    FactInternetSales,
    FactInternetSales[UnitPrice] * FactInternetSales[OrderQuantity] 
        * CALCULATE(MAX(DimCurrency[ConversionRate])) -- PER-ROW CONTEXT TRANSITION!
)

// =========================================================================
// PRODUCTION-READY PATTERN: Set-Oriented DAX, Engine Push-Down Friendly
// SE Execution: Tunggal, vectorized scan, multi-threaded
// =========================================================================
[Total Sales Optimized] := 
VAR _RawSales = 
    SUMX(
        FactInternetSales,
        FactInternetSales[UnitPrice] * FactInternetSales[OrderQuantity]
    )
RETURN
    _RawSales

[Category Sales Clean] := 
CALCULATE(
    [Total Sales Optimized],
    ALLSELECTED(DimProduct[ProductCategoryName])
)

[Sales Contribution Pct] := 
VAR _CurrentSales = [Total Sales Optimized]
VAR _CategorySales = [Category Sales Clean]
VAR _SafeResult = 
    DIVIDE(
        _CurrentSales, 
        _CategorySales, 
        0.00
    )
RETURN
    IF(
        NOT ISBLANK(_CurrentSales),
        _SafeResult
    )
```

### 6.2 Python Automation Script: Tracing FE/SE Metric Spills via Dynamic Management Views (DMVs)

Skrip Python ini memantau kinerja penyimpanan VertiPaq internal dan membedah apakah skema metadata model memiliki kolom yang memicu *cardinality bloat* pada VertiPaq dictionary:

```python
"""
VertiPaq Model Optimization Scanner
Queries Analysis Services/Power BI XMLA Endpoint using ADOMD/PyADOMD
to extract column-level compression health statistics.
"""

from typing import Dict, List, Any
import pandas as pd
from pyadomd import Pyadomd

CONNECTION_STR = (
    "Provider=MSOLAP;"
    "Data Source=localhost:50005;"  # Local Power BI Desktop instance or Fabric XMLA
    "Catalog=SemanticModelId;"
    "Integrated Security=SSPI;"
)

DISCOVER_STORAGE_TABLE_COLUMNS = """
SELECT 
    [DATABASE_NAME],
    [TABLE_ID],
    [COLUMN_ID],
    [DICTIONARY_SIZE],
    [USED_SIZE],
    [ROWS_COUNT]
FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMNS
WHERE [DICTIONARY_SIZE] > 0
ORDER BY [USED_SIZE] DESC;
"""

def analyze_vertipaq_footprint(conn_str: str) -> pd.DataFrame:
    """
    Executes Analysis Services DMV query to determine high-cardinality columns
    and memory-heavy dictionaries that impede SE performance.
    """
    column_metrics: List[Dict[str, Any]] = []

    try:
        with Pyadomd(conn_str) as conn:
            with conn.cursor().execute(DISCOVER_STORAGE_TABLE_COLUMNS) as cur:
                rows = cur.fetchall()
                for row in rows:
                    column_metrics.append({
                        "Database": row[0],
                        "Table": row[1],
                        "Column": row[2],
                        "DictionarySize_Bytes": float(row[3]),
                        "UsedSize_Bytes": float(row[4]),
                        "RowCount": int(row[5])
                    })
    except Exception as exc:
        raise ConnectionError(f"Gagal menghubungkan ke DAX Engine via ADOMD: {str(exc)}") from exc

    df = pd.DataFrame(column_metrics)
    
    # Feature Engineering untuk deteksi kompresi buruk
    if not df.empty:
        df["BytesPerRow"] = df["UsedSize_Bytes"] / df["RowCount"]
        df["CompressionEfficiencyFactor"] = (
            df["DictionarySize_Bytes"] / df["UsedSize_Bytes"]
        )
        
    return df

def generate_optimization_report(df: pd.DataFrame, threshold_bytes_per_row: float = 4.0) -> pd.DataFrame:
    """
    Filters columns that are candidates for optimization:
    - High Used Size
    - High Bytes per row (indicating Bit-Packing/RLE inefficiency)
    """
    outliers = df[df["BytesPerRow"] > threshold_bytes_per_row].copy()
    outliers.sort_values(by="UsedSize_Bytes", ascending=False, inplace=True)
    return outliers

if __name__ == "__main__":
    try:
        df_stats = analyze_vertipaq_footprint(CONNECTION_STR)
        inefficient_cols = generate_optimization_report(df_stats)
        
        print("=== HIGHEST MEMORY CONSUMING VERTIPAQ COLUMNS ===")
        print(inefficient_cols[["Table", "Column", "UsedSize_Bytes", "BytesPerRow"]].head(10))
    except ConnectionError as ce:
        print(f"[ERROR] Eksekusi analitik gagal: {ce}")
```

---

## 7. Edge Cases & Failure Modes

### 1. Expanded Table Context Leak
*Mekanisme*: Dalam DAX, memfilter tabel anak (misal: `Sales`) sebenarnya memfilter **Expanded Table** dari tabel tersebut, yang mencakup semua tabel induk dari relasi 1-ke-banyak (`Product`, `Customer`, dsb).  
*Failure Mode*:
```dax
CALCULATE(
    [Total Sales],
    FILTER(Sales, Sales[Quantity] > 5) -- DANGEROUS! Mengunci seluruh Expanded Table Sales
)
```
*Dampak*: Semua filter aktif sebelumnya pada tabel `Product` dan `Customer` terhapus/ditimpa karena `FILTER(Sales, ...)` menyuntikkan seluruh entitas `Sales` (beserta kunci induk) ke Filter Context.  
*Mitigasi*: Filter kolom spesifik, bukan seluruh tabel:
```dax
CALCULATE(
    [Total Sales],
    KEEPFILTERS(Sales[Quantity] > 5)
)
```

### 2. Circular Dependency pada Calculated Columns
*Mekanisme*: Dua atau lebih *calculated columns* menggunakan `CALCULATE` (memicu Context Transition). Context Transition membutuhkan keunikan baris yang bergantung pada *semua* kolom tabel.  
*Failure*: VertiPaq compiler memunculkan error: `A circular dependency was detected`.  
*Solusi*: Gunakan variabel skalar eksplisit tanpa `CALCULATE`, atau pecah kalkulasi menjadi *measures*, atau pastikan terdapat primary key definitif yang tidak bergantung pada komputasi silang.

### 3. Cartesian Product Spill di Formula Engine
*Mekanisme*: Menulis kueri yang mengharuskan FE menggabungkan dua datacache besar di memori karena kondisi relasi tidak dapat diselesaikan oleh VertiPaq hash-join (misal: non-equi join condition di DAX).  
*Failure*: Memori Power BI melesat naik hingga limit node Fabric/SSAS (Out of Memory - 0xC1000016).

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi Pendekatan | Calculated Columns (VertiPaq) | DAX Measures (On-the-Fly Dynamic) | Pre-aggregasi di ETL (SQL/dbt) |
| :--- | :--- | :--- | :--- |
| **Footprint RAM** | Sangat Tinggi (Kolom tersimpan permanen di memori & diindeks). | Nol (Hanya memori transien saat kueri dieksekusi). | Rendah di layer model tabular jika detail data granular ditiadakan. |
| **Beban CPU saat Kueri** | Nol (Nilai langsung dibaca dari disk/RAM). | Moderat hingga Tinggi (Tergantung kompleksitas FE vs SE). | Minimal (Hanya membaca subtotal). |
| **Sifat Evaluasi Konteks** | Row Context statis saat refresh data. | Dinamis, merespons Filter Context pengguna saat klik. | Statis, tidak merespons perubahan slicer fleksibel. |
| **Kemampuan Relasional** | Buruk untuk slicing dinamis tingkat lanjut. | Maksimal, mampu menangani time intelligence & parameter dinamis. | Nol interaktivitas analitik ad-hoc. |

---

## 9. Best Practices & Standard Industri

1. **Avoid `CALCULATE` inside `FILTER` loops**:
   Jangan pernah menggunakan iterator baris yang memanggil `CALCULATE` pada tabel fakta masif:
   $$\text{Kompleksitas Komputasi: } \mathcal{O}(N \times M) \quad \text{di mana } N \text{ baris fakta, } M \text{ operasi transitions}$$
2. **Defensive Blank Handling**: Gunakan `DIVIDE(num, den, blank())` sebagai ganti operator `/` untuk mencegah FE membatalkan eksekusi paralel akibat evaluasi penanganan pembagian dengan nol.
3. **Explicit Context Preservation via `KEEPFILTERS`**: Selalu pertimbangkan pembungkusan predikat di dalam `KEEPFILTERS()` untuk mempertahankan filter context di level visual agar tidak tertimpa tanpa disengaja (*non-destructive filtering*).
4. **Minimalisir Kardinalitas Kunci Kolom**: Hapus timestamp dari kolom tanggal (pisahkan Date dan Time). Pisahkan UUID/GUID menjadi integer sequential jika memungkinkan untuk menghemat bit allocation VertiPaq.

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda bertugas merekayasa ulang query performa buruk pada semantic model berukuran 15 juta baris (`FactOnlineSales`). Kueri awal mengalami latency **4.8 detik** dan mendominasi penggunaan *Formula Engine*.

### Langkah 1: Pengamatan Baseline di DAX Studio
1. Buka DAX Studio, koneksikan ke model tabular lokal Anda.
2. Aktifkan **Server Timings** (Tab *Home* -> centang *Server Timings*).
3. Jalankan baseline kueri tidak efisien berikut:

```dax
EVALUATE
SUMMARIZECOLUMNS(
    DimProductCategory[ProductCategoryName],
    "HighValueTransactionCount", 
    COUNTX(
        FactOnlineSales,
        IF(
            CALCULATE(SUM(FactOnlineSales[SalesAmount])) > 1000, 
            1, 
            BLANK()
        )
    )
)
```

**Hasil Metrik Server Timings Awal:**
- Total Duration: ~4,800 ms
- FE Duration: ~4,200 ms (87.5% - FE Bottleneck masif!)
- SE Duration: ~600 ms
- SE Queries: Ribuan *Data Caches* kecil (Context Transition per baris).

### Langkah 2: Mengisolasi Penyebab Masalah
Kombinasi `COUNTX` yang membaca `FactOnlineSales` (baris per baris) dengan `CALCULATE(SUM(...))` di dalamnya memicu jutaan context transitions. VertiPaq tidak bisa melakukan vektorisasi; kontrol diserahkan seutuhnya ke FE yang beroperasi secara *single-threaded*.

### Langkah 3: Rekayasa Ulang Menggunakan Pure Filter Context & SE Push-Down
Tulis ulang formula analitik tersebut untuk memaksimalkan paralelisasi SE (Storage Engine) menggunakan filtering set tabular:

```dax
EVALUATE
SUMMARIZECOLUMNS(
    DimProductCategory[ProductCategoryName],
    "HighValueTransactionCount",
    VAR _HighValueOrders = 
        FILTER(
            SUMMARIZE(
                FactOnlineSales,
                FactOnlineSales[SalesOrderNumber],
                "@OrderTotal", SUM(FactOnlineSales[SalesAmount])
            ),
            [@OrderTotal] > 1000
        )
    RETURN
        COUNTROWS(_HighValueOrders)
)
```

### Langkah 4: Validasi & Benchmarking
Jalankan kueri baru di DAX Studio dengan *Clear Cache then Run*.

**Ekspektasi Metrik Server Timings Akhir:**
- Total Duration: < 120 ms
- FE Duration: < 20 ms
- SE Duration: ~100 ms (multi-threaded, ~800% CPU utilization across cores)
- SE Queries: 1 atau 2 agregasi xmSQL terkuantifikasi.

### Post-Lab Verification Checklist
- [x] Pastikan `SE Queries` berkurang drastis (maksimal 2-3 kueri xmSQL per visual).
- [x] Pastikan `FE Duration` berada di bawah 25% dari total durasi eksekusi kueri.
- [x] Verifikasi hasil agregasi numerik identik antara baseline dan kueri optimal.