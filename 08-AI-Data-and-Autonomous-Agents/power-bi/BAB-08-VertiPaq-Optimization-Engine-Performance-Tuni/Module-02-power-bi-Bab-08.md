# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 08: VertiPaq Optimization Engine & Performance Tuning**  
**Kategori: 08-AI-Data-and-Autonomous-Agents | Topik: Power BI Core Engineering**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Principal Data Architect dan Enterprise BI Engineer diharapkan mampu:

- **Menganalisis (Analyze)** struktur internal struktur data kolumnar VertiPaq (*Dictionary*, *Data Segment*, *Hierarchy*, *Relationship Indexes*) menggunakan DMV (*Data Mining Extensions/Dynamic Management Views*) dan VertiPaq Analyzer.
- **Mengevaluasi (Evaluate)** efisiensi algoritma kompresi (*Value Encoding*, *Hash/Dictionary Encoding*, *Run-Length Encoding (RLE)*, dan *Bit-Packing*) pada tingkat kolom dan partisi untuk mendeteksi degradasi performa memori.
- **Merancang & Mengimplementasikan (Design & Implement)** strategi optimasi kompresi data tingkat lanjut melalui re-ordering partisi, optimasi kardinalitas (*cardinality reduction*), partisi vertikal/horizontal, serta pemisahan atribut waktu presisi tinggi.
- **Mengontrol (Control)** eksekusi komputasi antara *Formula Engine* (FE) dan *Storage Engine* (SE), meminimalkan *materialization overhead*, dan memaksimalkan *predicate pushdown* ke tingkat SE melalui pembangkitan kueri xmSQL yang optimal.
- **Mengembangkan (Develop)** arsitektur data *in-memory* skala enterprise (ratusan juta hingga miliaran baris) dengan footprint RAM minimum dan latensi kueri sub-detik pada kapasitas Power BI Premium/Fabric.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, praktisi wajib menguasai kompetensi dasar berikut:
- Pemahaman mendalam tentang pemodelan data dimensional (Kimball Architecture: *Star Schema*, *Snowflake Schema*, *Factless Fact Tables*).
- Kemahiran menulis dan menganalisis ekspresi DAX (*Filter Context*, *Row Context*, *Context Transition*).
- Pengalaman operasional menggunakan tooling diagnostik eksternal: DAX Studio, Tabular Editor 2.x/3.x, dan SQL Server Profiler.
- Pemahaman fundamental mengenai arsitektur sistem operasi komputer: manajemen memori virtual, struktur CPU *L1/L2/L3 cache*, proses multi-threading, dan eksekusi SIMD (*Single Instruction, Multiple Data*).

---

## 3. Concept & Internal Architecture (Mendalam)

Mesin VertiPaq adalah *in-memory columnar database engine* berkecepatan tinggi yang menggerakkan Power BI, Analysis Services Tabular, dan Fabric Direct Lake. VertiPaq dirancang untuk beban kerja analitik OLAP modern dengan memprioritaskan pemindaian data (*sequential memory scan*) daripada pemrosesan transaksional baris-per-baris (OLTP).

```
+-------------------------------------------------------------------------+
|                              POWER BI HOST                              |
|                                                                         |
|  +------------------------+          +-------------------------------+  |
|  |     Formula Engine     |  DAX     |        Storage Engine         |  |
|  |          (FE)          | Query    |             (SE)              |  |
|  |                        +--------->|           (VertiPaq)          |  |
|  | - Single-threaded      |          | - Multi-threaded              |  |
|  | - Complex DAX / Logic  | xmSQL    | - Vectorized scanning (SIMD)  |  |
|  | - Evaluates expressions|<---------+ - Hardware cache friendly     |  |
|  | - Materializes tables  | datacache| - Compressed columnar storage |  |
|  +------------------------+          +---------------+---------------+  |
+------------------------------------------------------|------------------+
                                                       v
                 +---------------------------------------------------------+
                 |            VertiPaq Memory Internal Structures          |
                 |  +---------------------------------------------------+  |
                 |  | Segment Data (1,048,576 rows default slice)        |  |
                 |  | - Column A: [Bit-Packed RLE Encodings]            |  |
                 |  | - Column B: [Value Encoded Integers]              |  |
                 |  +---------------------------------------------------+  |
                 |  | Global / Local Dictionaries                       |  |
                 |  | - Distinct Values Mapping (Surrogate Keys)        |  |
                 |  +---------------------------------------------------+  |
                 |  | Physical Relationships & Hierarchies Structures   |  |
                 |  | - 64-bit Hash Pointers, Forward/Reverse Index Maps|  |
                 |  +---------------------------------------------------+  |
                 +---------------------------------------------------------+
```

### 3.1. Anatomi Alokasi Memori VertiPaq

Memori yang dikonsumsi oleh model Tabular VertiPaq terbagi ke dalam empat komponen struktural utama:

1. **Columns**: Merepresentasikan penyimpanan data aktual dari setiap kolom yang diimpor. Terdiri dari *Data*, *Dictionary*, dan *Index*.
2. **Dictionaries**: Struktur pemetaan nilai unik ke *surrogate integer id*. Dibuat untuk kolom berbasis teks (*string*) atau angka non-linier.
3. **Relationships**: Struktur biner penunjuk (*binary index tables*) yang memetakan hubungan kunci primer-kunci asing antar-tabel untuk eksekusi relasi instan tanpa proses perbandingan nilai saat waktu kueri (*query time*).
4. **Hierarchies & User Hierarchies**: Struktur data indeks *B-tree* yang dibangun secara internal untuk mendukung navigasi *drill-down* hierarki kustom dan hierarki *Date auto-generated*.

### 3.2. Triad Algoritma Kompresi VertiPaq

VertiPaq mencapai rasio kompresi tinggi (seringkali 10x hingga 50x dibanding data relasional mentah) melalui tiga algoritma berurutan:

#### A. Value Encoding
Diterapkan eksklusif pada kolom bertipe data numerik integer. Algoritma ini menentukan nilai minimum ($Min$) dalam rentang data dan menghitung nilai delta matematika ($Delta = Val - Min$). Nilai delta ini kemudian disimpan menggunakan jumlah bit seminimal mungkin (*bit-packing*).

$$\text{Bit-width} = \lceil \log_2 (Max - Min + 1) \rceil$$

*Contoh*: Sebuah kolom transaksi memiliki ID mulai dari $10.000.000$ hingga $10.000.500$.
- Nilai $Min = 10.000.000$.
- Range diferensial = $500$.
- Jumlah bit yang dibutuhkan: $\lceil \log_2(501) \rceil = 9\text{ bits per row}$.
- Tanpa kompresi, tipe `INT64` membutuhkan $64\text{ bits}$. Penghematan mencapai **85.9%** tanpa memerlukan struktur *Dictionary*.

#### B. Hash/Dictionary Encoding
Diterapkan secara *default* pada tipe data string dan kolom floating-point/variabel numerik acak. VertiPaq membangun *lookup table* (Dictionary) yang berisi seluruh nilai unik yang muncul pada kolom tersebut, kemudian memberikan ID integer pengganti (*Surrogate Key*) dari rentang $0$ hingga $N-1$ ($N$ adalah kardinalitas kolom).

Struktur memori kolom kemudian hanya menyimpan *Surrogate Keys*, sedangkan teks literal aslinya disimpan tepat satu kali di dalam *Dictionary*. Ukuran bit per baris pada kolom data kemudian bergantung pada kardinalitas tabel *Dictionary*:

$$\text{Surrogate Bit-width} = \lceil \log_2(N) \rceil$$

#### C. Run-Length Encoding (RLE)
RLE memampatkan segmen data yang berisi perulangan nilai berurutan yang identik (*runs*). Alih-alih menyimpan array data sekuensial $[4, 4, 4, 4, 4, 7, 7]$, RLE menyimpannya sebagai pasangan nilai dan panjang sekuens: $(4, 5), (7, 2)$.

VertiPaq mengkombinasikan *Dictionary Encoding* dengan *RLE*:
1. Data ditransformasikan menjadi array *Surrogate ID*.
2. Algoritma *Heuristic Sort Order* mencoba menentukan urutan baris optimum saat memproses partisi guna menghasilkan sekuens pengulangan nilai (*run*) sepanjang mungkin.
3. RLE mencatat *entry* berisi: `Value (Surrogate ID)`, `Row Count` (atau `Starting Row Index`).

Jika sebuah kolom dengan $10.000.000$ baris hanya memiliki 2 nilai unik yang terurut secara sempurna, kolom tersebut dapat dikompresi menjadi **hanya 2 entri fisik**.

### 3.3. Segmentasi dan Batas Partisi (Segmentation Internals)

Data di dalam tabel VertiPaq diproses dan disimpan dalam unit diskrit yang disebut **Segments**.
- Ukuran *default segment* adalah **$1.048.576$ baris ($2^{20}$ baris)**.
- Setiap segmen dienkapsulasi secara independen: memiliki struktur *RLE Metadata* dan skema kompresi bit-packing lokalnya sendiri.
- Pemrosesan paralel multi-threading oleh Storage Engine berlangsung pada level segmen. Satu core CPU menangani pemindaian satu segmen secara simultan tanpa *thread locking*.
- Segmen berukuran kecil (< $100.000$ baris) menghasilkan penalti performa karena *metadata overhead* dan hilangnya efisiensi *SIMD Vectorization*.

### 3.4. Query Execution Engine: FE vs SE Interaction Lifecycle

```
[ Incoming DAX Query from Client ]
               │
               ▼
┌──────────────────────────────┐
│    Formula Engine (FE)       │
│  - Query parsing & validation│
│  - DAX Execution Plan created│
│  - Generates xmSQL queries   │
└──────────────┬───────────────┘
               │
      xmSQL Query Requests
               │
               ▼
┌──────────────────────────────┐
│    Storage Engine (SE)       │
│  - Scans column segments     │
│  - Multi-threaded execution  │
│  - Aggregates (SUM, MIN, etc)│
│  - Filters using bitmasks    │
│  - Returns datacache         │
└──────────────┬───────────────┘
               │
          Datacache
               │
               ▼
┌──────────────────────────────┐
│    Formula Engine (FE)       │
│  - Complex DAX calculations  │
│  - Post-aggregation loops    │
│  - Materialization of result │
│  - Result sent to client     │
└──────────────────────────────┘
```

1. **Client** mengirimkan kueri DAX.
2. **Formula Engine (FE)** menerima dan mem-parsing kueri, menyusun representasi logika ekspresi (*Logical & Physical Execution Tree*).
3. FE menentukan bagian kueri yang dapat di-*push down* ke **Storage Engine (SE)** dalam bentuk kueri **xmSQL**.
4. SE mengalokasikan *worker threads* ke berbagai segmen di memori, mengeksekusi operasi filter berbasis *bitmask* dan agregasi dasar langsung di atas data terkompresi tanpa dekompresi penuh (*vectorized scan*).
5. SE mengembalikan kumpulan tabel hasil intermediet (*Datacache*) ke FE.
6. Jika kueri mengandung fungsi non-SE-pushdown (misal: iterator kompleks dengan *context transition* di dalam baris, fungsi matematika rumit, atau perlakuan string rekursif), FE terpaksa **mematerialisasi jutaan baris datacache ke memori FE**, memicu kalkulasi *single-threaded*, meningkatkan latensi kueri drastis (*bottleneck*).

---

## 4. Why & What

### Mengapa Pemahaman VertiPaq Sangat Krusial?
Model data Power BI enterprise tidak dapat diskalakan secara linier hanya dengan menambah kapasitas RAM atau CPU PPU/SKU Fabric. Masalah mendasar performa bersumber dari konsumsi memori dan inefisiensi kueri yang disebabkan oleh skema kompresi yang buruk:
- **Biaya Infrastruktur**: Kapasitas memori PPU atau Fabric Capacity (F-SKU) memiliki batas batas alokasi memori aktif (*Active Memory Limit*). Model yang tidak dioptimalkan menyebabkan *Memory Throttling*, pengusiran dataset (*Eviction*), dan kegagalan *Refresh OOM (Out Of Memory)*.
- **Latensi Pengguna Akhir**: Laporan interaktif memerlukan waktu respon visual di bawah 1 detik. FE bottleneck akibat kueri xmSQL yang tidak efisien menghasilkan *DirectQuery/Storage Engine timeouts*.

### Apa Saja yang Menentukan Footprint Memori VertiPaq?
Kompresi VertiPaq dipengaruhi oleh tiga variabel:
1. **Column Cardinality (Bobot 70%)**: Jumlah nilai unik di dalam kolom. Semakin tinggi kardinalitas, semakin besar ukuran kamus (*Dictionary*), semakin banyak bit per baris yang diperlukan untuk *bit-packing*, dan semakin kecil peluang nilai berulang untuk kompresi RLE.
2. **Sort Order Optimization (Bobot 20%)**: Urutan susunan baris fisik sebelum proses kompresi menentukan efisiensi RLE. Kolom dengan kardinalitas rendah yang diurutkan bersamaan akan menghasilkan kompresi hampir sempurna.
3. **Data Type Selection (Bobot 10%)**: Tipe data numerik integer membuka peluang penggunaan *Value Encoding*, yang secara penuh meniadakan kebutuhan alokasi memori untuk *Dictionary*.

---

## 5. How (Workflow Detail)

Berikut adalah tahapan siklus kompresi pemrosesan partisi (*Process Full / Recalc*) saat VertiPaq memuat data ke memori:

```
[ Raw Source Data ]
        │
        ▼
┌────────────────────────────────────────────────────────┐
│ Phase 1: Allocation & Dictionary Construction          │
│ - Stream data into memory buffer                       │
│ - Build temporary Hash Table of unique values          │
│ - Generate Global Dictionary and assign Surrogate Keys │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Phase 2: Algorithm Selection & Cost Evaluation         │
│ - Sample 24,000 to 1,000,000 rows                      │
│ - Test Value Encoding vs Hash Encoding candidate       │
│ - Select Sort Order heuristically to maximize RLE runs │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Phase 3: Segment Encoding & Bit-Packing                │
│ - Slice data into 1M-row partitions (Data Segments)    │
│ - Encode values using chosen algorithm                 │
│ - Bit-pack encoded integers to exact log2(N) width     │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Phase 4: Relationship & Hierarchy Index Building       │
│ - Generate binary relationship maps between PK and FK  │
│ - Build internal Natural B-Trees for hierarchy support │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
[ Final Optimized In-Memory Model Loaded ]
```

### Langkah Rekayasa Optimasi Model VertiPaq:
1. **Analisis Baseline Metrik**:
   Buka DAX Studio, sambungkan ke model yang aktif, jalankan menu `Advanced` -> `View Metrics` (VertiPaq Analyzer engine).
2. **Identifikasi Top Memory Consumer**:
   Analisis tabel dan kolom berdasarkan metrik:
   - `Total Size`
   - `Dictionary Size`
   - `Data Size`
   - `Cardinality`
3. **Restrukturisasi Tipe Data & Kardinalitas**:
   - Memecah tipe data `DateTime` menjadi dua kolom diskrit: `Date` (tipe tanggal) dan `Time` (tipe integer atau teks per menit/detik).
   - Menghilangkan *surrogate business keys* bernilai GUID/UUID dengan *hash integer index* atau membuangnya dari model analitik.
4. **Strategi Partisi & Sort Order Engineering**:
   - Konfigurasi partisi pada tabel fakta besar (berdasarkan tahun/bulan).
   - Pastikan data dipesan (*pre-sorted*) dari sistem hulu (ETL/Data Pipeline) berdasarkan kolom dengan kardinalitas paling rendah yang sering digunakan dalam penyaringan (*filtering*).

---

## 6. Analogy & Diagram ASCII

### Analogi: Katalog Perpustakaan vs Teks Lengkap
Bayangkan sebuah perpustakaan nasional yang menyimpan $1.000.000$ jilid buku laporan sensus.

- **Penyimpanan Berorientasi Baris (Row-Oriented / OLTP)**:
  Setiap jilid berisi formulir sensus lengkap: nama, kota, pekerjaan, status, dan pendapatan untuk setiap individu. Jika auditor ingin mengetahui berapa banyak penduduk yang berdomisili di "Surabaya", staf perpustakaan harus membuka setiap lembar dari $1.000.000$ jilid buku tersebut dari awal hingga akhir.

- **Penyimpanan VertiPaq (Columnar + Hash + RLE)**:
  Perpustakaan merobek semua buku dan menyusunnya berdasarkan kolom data:
  - Ada satu gulungan panjang khusus untuk "Kota".
  - Dibangun **Dictionary**:
    - `0 = Surabaya`
    - `1 = Jakarta`
    - `2 = Bandung`
  - Jika data telah diurutkan berdasarkan kota, gulungan "Kota" tidak menulis teks "Surabaya" berulang-ulang, melainkan kode RLE:
    - `Nilai 0: Muncul berturut-turut sebanyak 450.000 baris`.
    - `Nilai 1: Muncul berturut-turut sebanyak 350.000 baris`.
    - `Nilai 2: Muncul berturut-turut sebanyak 200.000 baris`.
  - Pertanyaan auditor selesai dijawab secara instan hanya dengan membaca 3 pasang angka RLE tersebut, tanpa perlu memindai $1.000.000$ baris data secara individual.

```
CONTOH KOMPRESI BIT-PACKING DAN RLE PADA MEMORI:

Uncompressed Data (Raw Strings) [Footprint: 7 rows * 16 bytes = 112 bytes]
Row 0: "Active"
Row 1: "Active"
Row 2: "Active"
Row 3: "Active"
Row 4: "Inactive"
Row 5: "Inactive"
Row 6: "Pending"

STEP 1: Hash / Dictionary Encoding
-----------------------------------
Surrogate Dictionary:
ID | String Value
---+-------------
0  | "Active"
1  | "Inactive"
2  | "Pending"

Cardinality = 3. Bit-width required = ceil(log2(3)) = 2 bits.
Encoded Array: [0, 0, 0, 0, 1, 1, 2]

STEP 2: Run-Length Encoding (RLE)
-----------------------------------
Run Format: (Value ID, Run Length)
Run 1: (0, 4)  --> Nilai 0 sepanjang 4 baris berturut-turut
Run 2: (1, 2)  --> Nilai 1 sepanjang 2 baris berturut-turut
Run 3: (2, 1)  --> Nilai 2 sepanjang 1 baris

Memori yang dialokasikan:
Hanya 3 entri pasangan integer (bit-packed) menggantikan alokasi 7 string penuh.
```

---

## 7. Simple Example & Practical Example

### Practical Architecture Artifacts: Skrip DMV & Diagnostik Model Otomatis

Berikut adalah skrip kueri DMV melalui antarmuka DAX Studio / SSMS untuk mengekstraksi metrik struktur kompresi VertiPaq secara terprogram.

```sql
/* Query 1: Analisis Detail Konsumsi Memori per Kolom melalui DMV */
SELECT 
    [DIMENSION_NAME] AS [Table_Name],
    [COLUMN_NAME] AS [Column_Name],
    [COLUMN_ENCODING] AS [Encoding_Type], /* 1 = Hash, 2 = Value */
    [DICTIONARY_SIZE] AS [Dictionary_Bytes],
    [COLUMN_CARDINALITY] AS [Cardinality],
    [DATA_SIZE] AS [Data_Bytes],
    ([DATA_SIZE] + [DICTIONARY_SIZE]) AS [Total_Allocated_Bytes]
FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMN_SEGMENTS
WHERE [COLUMN_TYPE] = 'BASIC_DATA'
ORDER BY [Total_Allocated_Bytes] DESC;
```

```sql
/* Query 2: Identifikasi Partisi Segmen yang Mengalami Fragmentasi */
SELECT 
    [TABLE_ID] AS [Table_Partition],
    [SEGMENT_NUMBER],
    [TABLE_PARTITION_NUMBER],
    [RECORDS_COUNT],
    [ALLOCATED_SIZE] AS [Allocated_Bytes],
    [COMPRESSION_TYPE],
    [BITS_PER_VALUE]
FROM $SYSTEM.DISCOVER_STORAGE_TABLE_SEGMENTS
ORDER BY [RECORDS_COUNT] ASC;
```

### Script Otomasi Pembersihan Kardinalitas Menggunakan Tabular Editor C# Scripting

Skrip otomasi berikut digunakan dalam pipeline CI/CD pada Tabular Editor untuk mengidentifikasi dan merekomendasikan restrukturisasi kolom berbobot tinggi:

```csharp
// Tabular Editor C# Advanced Script: VertiPaq Memory Optimization Audit
// Mendeteksi kolom DateTime presisi tinggi dan Hidden Key yang membebani memori.

var sb = new System.Text.StringBuilder();
sb.AppendLine("Table,Column,DataType,IssueDetected,ActionRequired");

foreach(var table in Model.Tables)
{
    foreach(var col in table.Columns)
    {
        // Deteksi Kolom DateTime dengan Kardinalitas Tersembunyi Tinggi
        if(col.DataType == DataType.DateTime)
        {
            sb.AppendLine(string.Format("\"{0}\",\"{1}\",\"{2}\",\"{3}\",\"{4}\"",
                table.Name,
                col.Name,
                col.DataType,
                "DateTime Precision High Cardinality Risk",
                "Split into discrete Date and Time components or integer DateKey"));
        }
        
        // Deteksi String Columns berakhiran ID yang tidak terlibat dalam Relationship
        if(col.DataType == DataType.String && (col.Name.EndsWith("Id") || col.Name.EndsWith("ID") || col.Name.EndsWith("GUID")))
        {
            bool isUsedInRelationship = false;
            foreach(var rel in Model.Relationships)
            {
                if(rel.FromColumn == col || rel.ToColumn == col)
                {
                    isUsedInRelationship = true;
                    break;
                }
            }
            
            if(!isUsedInRelationship && !col.IsHidden)
            {
                sb.AppendLine(string.Format("\"{0}\",\"{1}\",\"{2}\",\"{3}\",\"{4}\"",
                    table.Name,
                    col.Name,
                    col.DataType,
                    "Degenerate Dimension Key (String ID unused in relationship)",
                    "Remove from tabular model or hash into surrogate int64 in ETL"));
            }
        }
    }
}

// Output log audit
sb.ToString().Output();
```

### Analisis Kueri xmSQL & Storage Engine Execution Tracing

Contoh DAX Measure yang tidak efisien (*Formula Engine Intensive*):

```dax
-- ANTI-PATTERN: Menghitung rata-rata penjualan dengan logika IF baris-per-baris
Ventas_Problematic = 
SUMX(
    FactInternetSales,
    IF(
        FactInternetSales[OrderDate] >= DATE(2023, 1, 1),
        FactInternetSales[SalesAmount] * 1.1,
        FactInternetSales[SalesAmount]
    )
)
```

**Hasil jejak Server Timings xmSQL (Fragmented SE queries + FE iteration):**
```text
FE Execution Time: 840ms | SE Execution Time: 42ms | Total: 882ms
Storage Engine CPU: 120ms | SE Queries: 2
Line 1: SELECT [FactInternetSales].[OrderDate], [FactInternetSales].[SalesAmount] FROM [FactInternetSales];
-- PERINGATAN: FE mematerialisasi 15.000.000 baris ke RAM untuk mengevaluasi ekspresi IF!
```

Solusi penulisan ulang berbasis aljabar relasional (*SE Pushdown Friendly*):

```dax
-- OPTIMIZED PATTERN: Memungkinkan SE melakukan agregasi langsung di tingkat bit-stream
Ventas_Optimized = 
VAR BasePost2023 = 
    CALCULATE(
        SUM(FactInternetSales[SalesAmount]),
        FactInternetSales[OrderDate] >= DATE(2023, 1, 1)
    ) * 1.1
VAR BasePre2023 = 
    CALCULATE(
        SUM(FactInternetSales[SalesAmount]),
        FactInternetSales[OrderDate] < DATE(2023, 1, 1)
    )
RETURN
    BasePost2023 + BasePre2023
```

**Hasil jejak Server Timings xmSQL Teroptimasi:**
```text
FE Execution Time: 2ms | SE Execution Time: 14ms | Total: 16ms
Storage Engine CPU: 96ms (Multi-threaded scan across segments) | SE Queries: 2
Line 1: SELECT SUM([FactInternetSales].[SalesAmount]) FROM [FactInternetSales] WHERE [FactInternetSales].[OrderDate] >= '2023-01-01';
Line 2: SELECT SUM([FactInternetSales].[SalesAmount]) FROM [FactInternetSales] WHERE [FactInternetSales].[OrderDate] < '2023-01-01';
-- HASIL: Materialisasi FE = 0 baris. Seluruh kalkulasi diselesaikan di Storage Engine.
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Bisnis
Sistem Telemetri Smart-Grid Transaksi Energi Nasional (`Fact_SmartMeterReadings`) mencakup **650.000.000 baris data** transaksi listrik per 15 menit. 

### Gejala Masalah di Lingkungan Produksi:
- Konsumsi memori model Tabular mencapai **112 GB RAM**, menyebabkan *Out-Of-Memory (OOM)* pada kapasitas Power BI Premium P2 (SKU P2 membatasi memori dataset maksimal 50 GB sebelum *paging*).
- *Refresh* dataset terjadwal sering *timeout* setelah berjalan 4 jam.
- Laporan DAX interaktif memerlukan waktu respon visual 8 hingga 14 detik per *click filter*.

### Audit VertiPaq Analyzer:
Hasil ekspor metrik VertiPaq Analyzer memperlihatkan distribusi ukuran memori internal sebagai berikut:

| Table Name | Column Name | Cardinality | Data Size | Dictionary Size | Total Size | % of Model |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Fact_SmartMeterReadings` | `TransactionID` (GUID) | 650,000,000 | 2.1 GB | 54.3 GB | 56.4 GB | 50.3% |
| `Fact_SmartMeterReadings` | `ReadingTimestamp` | 35,040,000 | 4.8 GB | 2.9 GB | 7.7 GB | 6.8% |
| `Fact_SmartMeterReadings` | `MeterSerialNumber` | 2,500,000 | 1.8 GB | 18.2 GB | 20.0 GB | 17.8% |
| `Fact_SmartMeterReadings` | `ConsumptionKwh` | 89,000,000 | 12.1 GB | 4.4 GB | 16.5 GB | 14.7% |
| *(Other 24 Columns)* | *(Various)* | *(Low)* | 8.2 GB | 3.2 GB | 11.4 GB | 10.4% |

### Analisis Akar Masalah (Root Causes):
1. **TransactionID**: Kolom string GUID 36 karakter unik untuk setiap baris. Kolom ini memicu pembuatan kamus (*Dictionary*) sebesar 54.3 GB. Kardinalitas sama dengan jumlah baris tabel ($N = 650.000.000$), sehingga algoritma RLE tidak bekerja ($Run = 1$).
2. **ReadingTimestamp**: Kolom `DateTime` presisi milidetik. Menghasilkan puluhan juta entri unik pada kamus data.
3. **ConsumptionKwh**: Disimpan dalam tipe data desimal floating-point (`Double` presisi 8 desimal), memaksa VertiPaq menggunakan *Hash Encoding* alih-alih *Value Encoding*.

### Eksekusi Solusi Rekayasa:

#### 1. Menghilangkan Degenerate Dimension yang Tidak Digunakan
`TransactionID` dipastikan tidak digunakan oleh analis bisnis dalam agregasi visual, relasi, maupun filter DAX. Kolom ini dihapus secara permanen dari model tabular data lakehouse view/ETL.
- **Dampak Penghematan**: **-56.4 GB**.

#### 2. Dekomposisi Atribut Temporal
Kolom `ReadingTimestamp` dipecah menjadi:
- `ReadingDateKey` (Tipe `Int32`, format `YYYYMMDD`). Kardinalitas turun drastis menjadi hanya $1.095$ nilai unik (3 tahun data). Menggunakan kompresi *Value Encoding*.
- `ReadingTimeKey` (Tipe `Int32`, rentang interval per 15 menit: $0$ s.d. $95$). Kardinalitas hanya $96$ nilai unik. RLE bekerja maksimal.
- **Dampak Penghematan**: Memori turun dari 7.7 GB menjadi **210 MB**.

#### 3. Rekayasa Tipe Data Skala Tetap (Fixed Decimal)
Nilai `ConsumptionKwh` diubah di tingkat ETL hulu dari `Float` (8 desimal) menjadi `Fixed Decimal Number` (`Currency` di Analysis Services, 4 angka di belakang koma) atau dikalikan $1.000$ dan disimpan sebagai `Int64`. VertiPaq beralih secara otomatis dari *Hash Encoding* ke **Value Encoding**.
- **Dampak Penghematan**: Dari 16.5 GB turun menjadi **2.4 GB**.

#### 4. Pengurutan Fisik & Partisioning Berdasarkan Akses Kueri (Sort Order Pipeline)
Di layer ETL (Apache Spark / Databricks), tabel diatur dengan partisi bulanan dan diurutkan secara fisik sebelum ditulis ke Parquet/Delta:
```sql
OPTIMIZE Fact_SmartMeterReadings 
ZORDER BY (GridSubstationID, ReadingDateKey);
```
Pengurutan fisik berdasarkan `GridSubstationID` (kardinalitas rendah: 450 gardu induk) memaksimalkan run-length RLE segmen VertiPaq secara masif.

### Hasil Akhir (Post-Implementation Architecture):
- **Ukuran Total Memori VertiPaq**: Dari **112 GB** menjadi **7.6 GB** (**Kompresi 93.2%**).
- **Waktu Refresh Partisi Harian**: Dari **240 menit** menjadi **8.5 menit**.
- **Latensi Kueri Rata-rata (P95)**: Dari **8.200ms** menjadi **180ms**.
- Kapasitas infrastruktur berhasil diturunkan dari SKU P2 ke SKU P1 (Penghematan biaya lisensi cloud sebesar **$5.000 USD per bulan**).

---

## 9. Trade-offs

Setiap keputusan optimasi mesin penyimpanan tabular membawa konsekuensi teknis arsitektur:

| Desain Optimasi | Keuntungan (Pros) | Trade-off / Konsekuensi (Cons) | Biaya / Dampak Arsitektur |
| :--- | :--- | :--- | :--- |
| **Menghapus Kunci Unik (GUID / Primary Key)** | Mengeliminasi hingga 80% ukuran Dictionary; menghemat puluhan gigabyte RAM. | Kehilangan kemampuan *drill-through* ke level satu transaksi spesifik pada visual laporan. | Memerlukan implementasi pola *Hybrid Table* atau *Composite Model* (DirectQuery fallback) jika detail transaksi individual wajib diakses auditor. |
| **Dekomposisi DateTime ke Date + Time** | Mengurangi kardinalitas drastis; memaksimalkan kompresi Value Encoding dan RLE. | Skema model memerlukan dua kolom. Formula DAX filter temporal yang menyatukan tanggal dan jam menjadi sedikit lebih rumit. | Memerlukan standarisasi kueri DAX dalam visual layer untuk mengonsumsi *Date dimension* terpisah. |
| **Mengubah Float ke Fixed Decimal / Scaled Int** | Memaksa transisi dari *Hash Encoding* ke *Value Encoding*; memotong alokasi Dictionary menjadi 0 byte. | Pembulatan matematis melebihi tingkat presisi yang ditentukan (kehilangan presisi di atas 4 desimal). | Tidak cocok untuk perhitungan sains/kimia/fisika analitik dengan toleransi galat mikroskopis. |
| **Optimasi Sort Order Kolom Spesifik** | Memaksimalkan RLE untuk kolom utama yang diurutkan; ukuran segmen mengecil. | Kolom lain yang memiliki korelasi negatif terhadap urutan tersebut akan mengalami penurunan efisiensi RLE (*scattering*). | Pipeline data processing (ETL/Spark) membutuhkan komputasi tambahan untuk tahapan sort global sebelum penulisan. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Kritis yang Sering Ditemui di Lingkungan Produksi

1. **Membiarkan Fitur "Auto Date/Time" Aktif**:
   Power BI Desktop secara otomatis membuat tabel tanggal tersembunyi (*local date tables*) untuk setiap kolom `DateTime` yang ada di model. Jika model memiliki 30 kolom tanggal pada tabel dimensional dan fakta, sistem menghasilkan 30 tabel B-Tree lokal tersembunyi yang mengonsumsi ratusan megabyte RAM tanpa visibilitas langsung.
   - *Solusi*: Nonaktifkan `Auto Date/Time for new files` di Global Options, dan hapus melalui Tabular Editor dengan mengatur `System Date Tables = Off`.

2. **Penggunaan Relationship Bi-directional (Cross-filtering Both)**:
   Memicu pembangunan struktur *Expanded Tables* internal di Formula Engine yang sangat besar. SE tidak dapat mengaplikasikan filter via *Bitmap Indexing* secara langsung, memaksa kueri jatuh ke FE (*CallbackDataID / Slow Scan*).
   - *Solusi*: Gunakan relasi *Single-Direction* dan pecahkan ambiguitas agregasi menggunakan `CROSSFILTER()` di tingkat DAX Measure spesifik.

3. **CallbackDataID pada Storage Engine xmSQL**:
   Ketika meneliti log kueri menggunakan DAX Studio Profiler, adanya token `CallbackDataID` di dalam baris perintah xmSQL mengindikasikan bahwa SE **tidak dapat menyelesaikan perhitungan secara internal** dan terpaksa memanggil Formula Engine berulang-ulang untuk setiap baris di dalam segmen.
   - *Penyebab*: Penggunaan fungsi DAX non-sederhana (seperti `ROUND`, `FORMAT`, perhitungan pembagian nol, atau referensi *Measure* kompleks) di dalam iterator (`SUMX`, `FILTER`, `CONCATENATEX`).
   - *Solusi*: Pindahkan komputasi ekspresi ke tingkat *Calculated Column* terkompresi atau proses langsung di layer SQL/Data Engineering hulu.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mempromosikan model Power BI / Analysis Services ke lingkungan produksi (Fabric / Premium Capacity):

### Schema & Modeling
- [ ] Model menggunakan **100% Star Schema** murni (menghindari pola relasi *Snowflake* bertingkat atau *Many-to-Many Direct Relationships*).
- [ ] Fitur **Auto Date/Time** telah dimatikan secara global dan lokal pada model.
- [ ] Seluruh kolom Foreign Key relasi dipastikan memiliki tipe data integer numerik (`Int64`).
- [ ] Tidak ada kolom berbasis UUID/GUID yang tersisa di dalam model impor VertiPaq.

### Cardinality & Data Types
- [ ] Seluruh atribut temporal bertipe data `DateTime` telah dipisahkan menjadi kolom `Date` dan `Time` mandiri.
- [ ] Kolom desimal finansial atau moneter telah dikonversi ke tipe data `Fixed Decimal Number` (`Currency`).
- [ ] Kolom teks deskriptif panjang (catatan pengguna, alamat jalan, memo) diisolasi ke tabel audit terpisah atau dieksklusikan dari model memori.

### Segment & Storage Tuning
- [ ] Partisi tabel fakta memiliki ukuran baris minimal $1.000.000$ baris per partisi aktif (menghindari fragmentasi segmen < $100.000$ baris).
- [ ] Urutan data fisik (*Clustering/Sorting*) di layer Lakehouse/Data Warehouse ditata sesuai urutan kolom kardinalitas terendah yang sering difilter.
- [ ] Semua *Calculated Columns* yang kompleks telah dipindahkan ke layer data hulu (SQL View / Bronze-Silver Transformation).

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan mempraktikkan proses optimasi model yang mengalami kebocoran memori secara sistematis. Struktur direktori praktikum:

```text
hands-on/
└── m02/
    ├── telemetry_unoptimized.bim
    ├── optimize_model.cs
    ├── verify_compression.dax
    └── result_benchmark.json
```

### Langkah 1: Eksplorasi Baseline Model (`telemetry_unoptimized.bim`)
Model memuat tabel `ServerMetrics` dengan $5.000.000$ baris data yang memiliki skema:
- `MetricGUID` (String UUID)
- `ServerID` (Integer, 50 Server)
- `Timestamp` (DateTime: '2024-01-01 10:15:32.124')
- `CpuLoadPercentage` (Float: 45.12938472)
- `StatusDescription` (String: 'OK', 'WARNING', 'CRITICAL')

### Langkah 2: Mengaudit Baseline Menggunakan DAX Studio
1. Buka DAX Studio, koneksikan ke port model Tabular lokal atau file PBIX yang memuat model tersebut.
2. Navigasikan ke menu **Advanced** -> **View Metrics**.
3. Amati ukuran `Dictionary Size` dari `MetricGUID` dan `Timestamp`.
4. Ekspor metrik VertiPaq Analyzer ke format file `.vpax`.

### Langkah 3: Eksekusi Transformasi melalui Tabular Editor Script
Jalankan skrip refaktorisasi skema berikut di **Tabular Editor** (Tab C# Script):

```csharp
// Refactoring Script: hands-on/m02/optimize_model.cs
var table = Model.Tables["ServerMetrics"];

// 1. Drop Column GUID yang tidak memiliki referensi relasi
var guidCol = table.Columns["MetricGUID"];
if(guidCol != null) {
    table.Columns.Remove(guidCol);
}

// 2. Ubah tipe data CpuLoadPercentage menjadi Decimal terkompresi
var cpuCol = table.Columns["CpuLoadPercentage"];
if(cpuCol != null) {
    cpuCol.DataType = DataType.Decimal;
}

// Model refresh required in PBI Desktop / Engine
```

### Langkah 4: Modifikasi Ekspresi Kolom Tanggal di ETL / Power Query
Buka Power Query Advanced Editor untuk sumber data tersebut, lalu terapkan transformasi pembagian DateTime:

```powerquery
let
    Source = Sql.Database("sql-telemetry.corp", "TelemetryDB"),
    MetricsTable = Source{[Schema="dbo",Item="ServerMetrics"]}[Data],
    RemovedGUID = Table.RemoveColumns(MetricsTable, {"MetricGUID"}),
    AddedDateKey = Table.AddColumn(RemovedGUID, "ReadingDate", each DateTime.Date([Timestamp]), type date),
    AddedTimeKey = Table.AddColumn(AddedDateKey, "ReadingTimeBucket", each Time.Hour([Timestamp]) * 60 + Time.Minute([Timestamp]), Int32.Type),
    RemovedOldTimestamp = Table.RemoveColumns(AddedTimeKey, {"Timestamp"}),
    ChangedFixedDecimal = Table.TransformColumnTypes(RemovedOldTimestamp, {{"CpuLoadPercentage", Currency.Type}})
in
    ChangedFixedDecimal
```

### Langkah 5: Verifikasi Hasil Optimasi (`verify_compression.dax`)
Jalankan kueri pengujian performa SE berikut di DAX Studio Server Timings untuk mengonfirmasi eliminasi `CallbackDataID`:

```dax
-- verify_compression.dax
EVALUATE
SUMMARIZECOLUMNS(
    'ServerMetrics'[StatusDescription],
    "AvgCpu", AVERAGE('ServerMetrics'[CpuLoadPercentage]),
    "TotalReadings", COUNTROWS('ServerMetrics')
)
```

Amati metrik pada tab **Server Timings**:
- Total CPU Storage Engine harus mendekati $0\text{ ms}$ Formula Engine time.
- Verifikasi bahwa `xmSQL` query tidak memuat ekspresi `CallbackDataID`.
- Muat kembali VertiPaq Analyzer: Catat penurunan ukuran total dataset.

---

## 13. Exercise

### Level Easy
Terdapat sebuah tabel dimensional `DimCustomer` dengan $200.000$ baris data. Kolom `Gender` berisi nilai string `"M"` dan `"F"`.
1. Berapa bit yang dibutuhkan oleh mesin VertiPaq untuk menyimpan *Surrogate Key* kolom `Gender` pada tingkat *Data Segment*?
2. Berapa alokasi memori teoritis yang dibutuhkan untuk kolom tersebut jika dikompresi murni dengan *Bit-Packing* (asumsikan tanpa RLE)?
3. **Jawaban Ekspektasi**:
   - $\text{Kardinalitas} = 2$.
   - Bit width: $\lceil \log_2(2) \rceil = 1\text{ bit per baris}$.
   - Memori: $200.000\text{ baris} \times 1\text{ bit} = 200.000\text{ bits} = 25.000\text{ bytes} \approx 24.41\text{ KB}$ (di luar ukuran kamus).

### Level Medium
Sebuah tabel transaksi `FactOrders` memiliki $40.000.000$ baris data. Salah satu kolomnya adalah `OrderType` yang memiliki 4 nilai unik: `"Standard"`, `"Express"`, `"SameDay"`, dan `"International"`. 
Saat ini urutan baris data bersifat acak berdasarkan `CustomerID`.
1. Bagaimana Anda merestrukturisasi proses penyimpanan agar ukuran memori kolom `OrderType` berkurang lebih dari 90% tanpa menghapus satu barispun data transaksi?
2. Jelaskan algoritma VertiPaq mana yang berperan dalam penurunan memori tersebut.

### Level Hard
Sebuah visual Matrix di Power BI menjalankan kalkulasi DAX kustom. Saat diuji pada DAX Studio, metrik kueri menunjukkan:
- `Total Duration`: $12.450\text{ ms}$
- `FE Duration`: $11.890\text{ ms}$ (95.5%)
- `SE Duration`: $560\text{ ms}$ (4.5%)
- `SE Queries`: $1.420$ kueri individual!

Lakukan diagnosis teknis:
1. Apa fenomena yang terjadi pada Formula Engine dan Storage Engine?
2. Bagaimana pola penulisan DAX Measure yang memicu gejala tersebut?
3. Rancang formula DAX baru untuk mengatasi masalah pemanggilan Storage Engine berulang (*query thrashing*) tersebut.

---

## 14. Challenge

### Arsitektur Multi-Tenant Triliun Baris (High-Scale Optimization Challenge)

Anda berperan sebagai Lead Tabular Architect pada perusahaan SaaS FinTech global yang mengelola platform akuntansi awan. 

**Kondisi Sistem:**
- Tabel `Fact_GeneralLedger` diproyeksikan menampung **1.500.000.000 baris data** per tahun buku.
- Terdapat $50.000$ penyewa (*tenants*). Atribut utama: `TenantID`, `AccountCode`, `PostingDate`, `FiscalYear`, `VoucherNumber`, `AmountDebit`, `AmountCredit`.
- Model di-hosting pada Azure Analysis Services / Power BI Premium P3 Capacity (Batas memori model aktif: 100 GB).
- Tenant berukuran besar (*Tier 1*) memiliki ratusan juta baris, sedangkan puluhan ribu tenant kecil (*Tier 3*) hanya memiliki beberapa ribu baris.
- Query report pengguna memerlukan filter berdasarkan `TenantID` dan `PostingDate` dengan ekspektasi respon P99 di bawah 1.5 detik.

**Tantangan Arsitektur yang Harus Diselesaikan:**
1. **Partitioning & Sort Engineering**: Rancang strategi partisi (*segment boundaries*) dan tentukan urutan hierarki pengurutan kolom fisik (*Z-Order / Sort Keys*) sebelum data diinjeksikan ke dalam mesin VertiPaq.
2. **Kardinalitas Voucher**: `VoucherNumber` memiliki kardinalitas $400.000.000$ nilai unik. Analis membutuhkan pencarian voucher tertentu, namun memori VertiPaq tidak sanggup menampung kamus string sebesar itu. Rancang arsitektur hybrid yang memisahkan storage engine tanpa mengorbankan fungsionalitas pencarian.
3. **Segment Health Preservation**: Tentukan arsitektur segmentasi data agar puluhan ribu tenant berskala kecil tidak memicu fragmentasi segmen (menghindari terciptanya puluhan ribu segmen mini berukuran < 10.000 baris yang menghancurkan efisiensi SE Vectorization).
4. Dokumentasikan seluruh arsitektur solusi dalam bentuk spesifikasi teknis dan diagram alur data pemrosesan.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda)

1. **Algoritma kompresi VertiPaq mana yang sama sekali TIDAK memerlukan struktur Dictionary (Kamus Data)?**
   - A. Hash Encoding
   - B. Run-Length Encoding (RLE)
   - C. Value Encoding
   - D. Bit-Packed Surrogate Encoding

2. **Berapa ukuran default baris dalam satu Data Segment VertiPaq sebelum segmen baru dibuat?**
   - A. 65,536 baris
   - B. 524,288 baris
   - C. 1,048,576 baris
   - D. 2,097,152 baris

3. **Berapa jumlah bit per baris yang dialokasikan oleh VertiPaq jika sebuah kolom menggunakan Hash Encoding dengan kardinalitas tepat 128 nilai unik?**
   - A. 6 bit
   - B. 7 bit
   - C. 8 bit
   - D. 128 bit

4. **Karakteristik eksekusi utama Formula Engine (FE) pada Analysis Services / VertiPaq adalah:**
   - A. Multi-threaded dan beroperasi langsung pada bit-stream terkompresi.
   - B. Single-threaded, mengevaluasi fungsi DAX non-SE pushdown, dan mengelola materialisasi memori.
   - C. Terdistribusi ke seluruh worker node GPU cluster.
   - D. Hanya bertugas melakukan pembacaan metadata disk.

5. **Apa efek langsung dari mengaktifkan fitur bawaan "Auto Date/Time" pada Power BI terhadap arsitektur penyimpanan internal?**
   - A. Mempercepat kompresi RLE pada kolom numerik.
   - B. Mengonversi tipe data DateTime menjadi Epoch timestamp secara transparan.
   - C. Membangun tabel hierarki tanggal lokal tersembunyi untuk setiap kolom DateTime di dalam file model, meningkatkan ukuran file dan memori.
   - D. Menonaktifkan kueri xmSQL Storage Engine.

---

### Bagian B: Intermediate (Analisis Pilihan Ganda & Analisis Kasus Singkat)

6. **Mengapa tipe data string dengan kardinalitas tinggi (seperti URL atau GUID) merupakan ancaman terbesar bagi arsitektur memori VertiPaq?**
   - A. VertiPaq tidak dapat membaca karakter UTF-8.
   - B. Dictionary table yang dibangun menjadi sangat besar sehingga melampaui efisiensi kompresi kolom data itu sendiri.
   - C. Formula Engine secara otomatis mematikan Storage Engine jika mendeteksi teks di atas 10 karakter.
   - D. Menyebabkan tabel fakta terpecah menjadi beberapa model data fisik yang terisolasi.

7. **Ketika meneliti kueri xmSQL pada trace DAX Studio, Anda menemukan instruksi: `WHERE CallbackDataID(...)`. Apa implikasi performa dari fenomena ini?**
   - A. Kueri dieksekusi dengan kecepatan maksimal menggunakan instruksi CPU AVX-512.
   - B. Storage Engine memanggil kembali Formula Engine secara berulang untuk setiap baris, merusak eksekusi multi-threading paralel SE.
   - C. VertiPaq berhasil melakukan pemangkasan partisi secara hardware-level.
   - D. Data telah didekompresi dan dipindahkan secara permanen ke hard drive.

8. **Diberikan kolom bertipe integer dengan nilai minimum $5.000.000$ dan nilai maksimum $5.000.060$. Jika VertiPaq memilih Value Encoding, berapa bit yang dialokasikan per baris data?**
   - A. 32 bit
   - B. 6 bit
   - C. 64 bit
   - D. 26 bit

9. **Di antara skenario urutan kolom (*sort order*) berikut, mana yang menghasilkan efisiensi kompresi Run-Length Encoding (RLE) TERTINGGI pada tabel transaksi penjualan ritel?**
   - A. Diurutkan berdasarkan `SalesAmount` (Kardinalitas: 2.000.000) lalu `Country` (Kardinalitas: 5).
   - B. Diurutkan berdasarkan `TransactionUUID` (Kardinalitas: 50.000.000) lalu `DateKey` (Kardinalitas: 1.000).
   - C. Diurutkan berdasarkan `Country` (Kardinalitas: 5) lalu `ProductCategory` (Kardinalitas: 20) lalu `DateKey` (Kardinalitas: 1.000).
   - D. Urutan data acak sesuai kedatangan transaksi pada server OLTP.

10. **Bagaimana hubungan fisik (*Relationships*) antar-tabel disimpan di dalam arsitektur internal VertiPaq?**
    - A. Dihitung secara komparatif saat kueri dijalankan menggunakan algoritma Nested Loops Join.
    - B. Disimpan dalam bentuk binary index map terkompresi yang memetakan baris tabel dimensi ke baris tabel fakta secara langsung tanpa kalkulasi join run-time.
    - C. Dibuat salinan fisik tabel gabungan (*materialized physical table*) secara penuh di memori.
    - D. Didelegasikan ke SQL Server instance eksternal melalui koneksi TCP/IP loopback.

---

### Bagian C: Kasus Masalah Produksi

11. **Kasus 1: Out of Memory Saat Refresh Terjadwal**
    Sebuah model data tabular berukuran 18 GB RAM di Azure Analysis Services mengalami galat *Out of Memory* setiap kali proses *Data Refresh* harian dijalankan, meskipun kapasitas memori server memiliki kuota 35 GB RAM. Mengapa hal ini terjadi, dan bagaimana arsitektur internal pemrosesan partisi VertiPaq menjelaskan fenomena ini?

12. **Kasus 2: Degradasi Drastis Kolom Desimal**
    Tabel keuangan enterprise memuat kolom `ExchangeRate` dengan kardinalitas $15.000$ nilai unik. Tipe data kolom tersebut adalah `Decimal Number` (Floating Point). Saat dicek melalui VertiPaq Analyzer, kolom ini mengonsumsi alokasi memori yang luar biasa besar pada struktur *Data Size* dan *Dictionary Size*. Mengapa mesin tidak menggunakan *Value Encoding*, dan langkah konfigurasi spesifik apa yang harus dieksekusi?

13. **Kasus 3: Kueri DAX Thrashing Akibat Relasi Many-to-Many**
    Sebuah laporan interaktif mengalami waktu render visual lebih dari 20 detik saat pengguna memilih nilai pada *slicer*. Hasil penelusuran DAX Studio menunjukkan bahwa kueri Formula Engine menghabiskan ribuan putaran iterasi untuk mengevaluasi filter yang melintasi relasi fisik bertipe *Many-to-Many* dengan arah penyaringan ganda (*Bi-directional*). Jelaskan apa yang terjadi di dalam memori FE dan SE, serta bagaimana cara memulihkan performa kueri tersebut!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A:
1. **C** - Value Encoding melakukan perhitungan delta matematika terhadap nilai numerik murni tanpa memerlukan alokasi memori Dictionary/Kamus data.
2. **C** - VertiPaq mengelompokkan baris ke dalam segmen dengan batasan standar $1.048.576$ baris ($2^{20}$).
3. **B** - Jumlah bit dihitung dengan $\lceil \log_2(128) \rceil = 7\text{ bits}$.
4. **B** - Formula Engine bersifat single-threaded, bertugas memproses ekspresi DAX kompleks yang tidak dapat ditangani Storage Engine, dan mengelola materialisasi tabel intermediet.
5. **C** - Auto Date/Time secara otomatis membuat tabel kalender internal tersembunyi untuk seluruh kolom bertipe DateTime, memperbesar footprint model secara masif.

#### Bagian B:
6. **B** - Kardinalitas unik yang mendekati jumlah baris membuat kamus string memakan alokasi gigabyte RAM, mematikan efisiensi RLE dan bit-packing.
7. **B** - `CallbackDataID` menandakan ketidakmampuan SE menyelesaikan operasi di segmen internal, memaksa interupsi sinkron ke Formula Engine untuk setiap baris data.
8. **B** - Range: $5.000.060 - 5.000.000 = 60$. Jumlah bit yang dibutuhkan: $\lceil \log_2(60 + 1) \rceil = \lceil \log_2(61) \rceil = 6\text{ bits}$.
9. **C** - Pengurutan dari kardinalitas terendah ke tinggi (`Country` -> `Category` -> `Date`) menciptakan deret baris identik terpanjang (*longest runs*) untuk dikompresi RLE.
10. **B** - Relasi Tabular VertiPaq diindeks secara biner ke dalam *64-bit forward/reverse surrogate maps*, meniadakan proses join dinamis yang lambat pada waktu kueri.

#### Bagian C (Panduan Solusi Kasus):
11. **Analisis Kasus 1**:
    VertiPaq menggunakan teknik pemrosesan transaksi ACID berbasis *Shadow Copying* saat memproses partisi (*Process Full / Add*). Segmen memori lama tetap aktif melayani kueri pengguna sementara struktur segmen memori baru dibangun secara paralel di area memori lain. Akibatnya, pemrosesan membutuhkan memori hingga $2\times$ lipat dari ukuran dataset ($18\text{ GB} \times 2 = 36\text{ GB}$). Karena batas server adalah $35\text{ GB}$, sistem mengalami crash OOM.  
    *Solusi*: Implementasikan pemrosesan per-partisi independen (*Process Defrag / Recalc* terpisah) atau naikkan batas memori sementara (*Scale-Up SKU*) selama jendela refresh berlangsung.

12. **Analisis Kasus 2**:
    VertiPaq secara default menerapkan *Hash/Dictionary Encoding* pada tipe data floating-point desimal standar karena perbedaan nilai fraksional di belakang koma menghasilkan variasi angka kontinu yang sulit dipetakan menggunakan delta integer.  
    *Solusi*: Ubah tipe data kolom menjadi `Fixed Decimal Number` (`Currency` di Analysis Services/Tabular Engine). Ini mengonversi nilai menjadi integer berbasis skalar tetap (dikalikan $10.000$), sehingga mengaktifkan algoritma *Value Encoding* dan meniadakan struktur Dictionary sepenuhnya.

13. **Analisis Kasus 3**:
    Relasi Many-to-Many dengan *Both Cross-filter Direction* memaksa Formula Engine membangun tabel Cartesian virtual di memori (*datacache materialization*) untuk memverifikasi validitas baris relasional di kedua arah secara independen. Storage Engine tidak dapat melakukan *Direct Bit-mask Filter*.  
    *Solusi*: Ubah relasi menjadi *Single Direction*. Masukkan tabel jembatan (*Bridge Table*) dimensional murni jika diperlukan, atau ganti logika propagasi konteks filter menggunakan kombinasi fungsi DAX terisolasi seperti `CALCULATE(..., CROSSFILTER(...), KEEPFILTERS(...))`.

---

## 16. Summary

Optimalisasi mesin VertiPaq bukan sekadar proses kosmetik DAX, melainkan disiplin rekayasa sistem penyimpanan berbasis memori (*in-memory storage engineering*). Fondasi performa tinggi bertumpu pada arsitektur model yang menghormati karakteristik internal perangkat keras modern:

1. **Prinsip Eliminasi Kardinalitas**: Kardinalitas kolom adalah musuh utama mesin kompresi kolumnar. Menghapus ID redundan, memecah tipe data `DateTime`, dan mengonversi representasi string acak menjadi integer adalah langkah paling berdampak dalam memotong jejak memori model.
2. **Mekanika Kompresi Berlapis**: Pahami bagaimana *Value Encoding*, *Dictionary Encoding*, *RLE*, dan *Bit-Packing* bekerja secara simbiosis. RLE bergantung mutlak pada urutan data fisik (*Sort Order*), sedangkan Value Encoding mengandalkan rentang diferensial angka minimum-maksimum.
3. **Pemisahan Peran FE vs SE**: Jaga agar Formula Engine tetap berada pada peran orkestrasinya. Desain ekspresi DAX Anda agar seluruh operasi pemfilteran, pemindaian, dan agregasi data terdorong sepenuhnya (*pushdown*) ke tingkat Storage Engine via xmSQL, menghilangkan jebakan memori *materialization* dan interupsi performa *CallbackDataID*.