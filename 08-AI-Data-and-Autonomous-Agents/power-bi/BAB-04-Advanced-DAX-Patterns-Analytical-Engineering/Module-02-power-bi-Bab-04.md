# BAB 04: Advanced DAX Patterns & Analytical Engineering
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis Internal Engine DAX**: Membedakan alur eksekusi kueri antara Formula Engine (FE) dan Storage Engine (SE/VertiPaq) menggunakan DAX Studio Metrics dan Server Timings.
- **Mengeliminasi Callback Loops**: Mengidentifikasi dan merefaktor ekspresi DAX yang memicu `CallbackDataID` untuk mengembalikan pemrosesan sepenuhnya ke VertiPaq SE multithreaded.
- **Menguasai Expanded Tables & Shadow Filter Context**: Memprediksi secara deterministik bagaimana filter merambat melintasi relasi fisik satu-ke-banyak (*one-to-many*) dan dampaknya terhadap kalkulasi semi-aditif.
- **Mengimplementasikan Advanced Analytical Patterns**: Membangun pola *Arbitrary Shape Filtering*, *Dynamic Currency Conversion* dengan volatilitas harian, *New vs Returning Customers*, dan kalkulasi matriks alokasi non-visual.
- **Mengoptimalkan Composite Models & Aggregation Tables**: Mengonfigurasi tabel agregasi berbasis Import di atas sumber DirectQuery untuk menekan latensi kueri sub-detik pada dataset multi-miliar baris.

---

### 2. Prerequisites
Sebelum menempuh modul ini, peserta wajib menguasai:
- Arsitektur Star Schema (Kimball Methodology): Fakta, Dimensi, Degenerate Dimensions, dan Surrogate Keys.
- Evaluasi dasar DAX: Filter Context, Row Context, Context Transition (`CALCULATE`/`CALCULATETABLE`), serta time intelligence standard.
- Tooling: Power BI Desktop (rilis 6 bulan terakhir), DAX Studio (v3.x ke atas), dan Tabular Editor 2/3.
- Pemahaman dasar struktur data: B-Tree, Bit-vector, Run-Length Encoding (RLE), Hash Encoding, dan Dictionary Encoding.

---

### 3. Concept & Internal Architecture

Eksekusi DAX pada Analysis Services (SSAS), Azure Analysis Services (AAS), dan Power BI Service ditopang oleh dua mesin komputasi yang bekerja secara simbiotik: **Formula Engine (FE)** dan **Storage Engine (SE)**.

```
                           +------------------------+
                           |   Client (Report/PBI)  |
                           +------------------------+
                                       |
                                  [DAX Query]
                                       v
               +------------------------------------------------+
               |             Formula Engine (FE)                |
               |  - Parser, Query Plan (Logical & Physical)    |
               |  - Single-threaded execution per query        |
               |  - Evaluates complex DAX (MDX functions, etc.) |
               +------------------------------------------------+
                          /                           \
               SE Query (xmSQL)                  SE Query (SQL)
                        /                               \
                       v                                 v
        +-----------------------------+   +-----------------------------+
        |  Storage Engine (VertiPaq)  |   |  Storage Engine (DirectQ)   |
        | - In-memory columnar        |   | - Relational pushdown       |
        | - Multi-threaded execution  |   | - Latency bound by RDBMS    |
        | - Scans, filters, hashes    |   | - Generates native T-SQL    |
        +-----------------------------+   +-----------------------------+
                       \                                 /
                        \---> [ Data Cache (Ephemaral) ]-/
                                       |
                                       v
                       FE aggregates, sorts & projects
                                       |
                                       v
                                [ Result Set ]
```

#### Formula Engine (FE)
- **Karakteristik**: Berjalan secara *single-threaded* untuk satu kueri pengguna. Ditulis menggunakan C++.
- **Tanggung Jawab**: 
  - Melakukan *parsing* sintaksis DAX dan membentuk *Logical Query Tree*.
  - Mengompilasi *Logical Plan* menjadi *Physical Execution Plan*.
  - Mengoordinasikan pemanggilan ke Storage Engine melalui kueri perantara berformat **xmSQL**.
  - Mengelola operasi yang tidak dapat dieksekusi oleh SE: *Context Transition* yang kompleks, kalkulasi finansial tingkat lanjut, string manipulation, *late-stage sorting*, dan evaluasi fungsi non-vektor (`LOOKUPVALUE`, `PATH`, iterator bersarang tertentu).
  - Menyusun dan menggabungkan *data cache* yang dikembalikan oleh SE sebelum dikirim kembali ke klien.

#### Storage Engine (SE - VertiPaq)
- **Karakteristik**: Berjalan secara *multi-threaded*, memanfaatkan teknik paralelisasi CPU secara intensif (*SIMD instruction sets*).
- **Tanggung Jawab**:
  - Membaca kolom terkompresi langsung dari RAM (Import Mode).
  - Mengeksekusi pemfilteran baris (*scan & filter*), pengelompokan (*grouping*), dan agregasi dasar (`SUM`, `MIN`, `MAX`, `COUNT`, `DISTINCTCOUNT`).
  - Mengembalikan struktur data tabular transien bernama **Datacache** ke FE.
- **Storage Engine Alternatives**: DirectQuery (menerjemahkan xmSQL menjadi SQL dialek target seperti T-SQL, Snowflake SQL, Databricks Spark SQL).

#### CallbackDataID (The Architecture Killer)
Ketika ekspresi DAX di dalam iterator (seperti `SUMX`, `FILTER`, `ADDCOLUMNS`) tidak dapat diekspresikan secara utuh dalam xmSQL primitif, SE terpaksa meminta intervensi FE untuk setiap baris atau partisi data. Fenomena ini disebut **CallbackDataID**.
- **Mekanisme**: SE menghentikan pemrosesan paralelnya, melakukan pemanggilan inter-engine ke FE (*context switch*), FE menghitung nilai baris tersebut, mengembalikannya ke SE, lalu SE melanjutkan proses.
- **Dampak**: Operasi SE yang seharusnya selesai dalam mikrodetik menjadi *single-threaded*, cache CPU ter-flush, dan latensi melonjak ribuan persen (*callback loop*).

#### Expanded Tables & Shadow Filter Context
Dalam model relasional VertiPaq, tabel tidak berdiri sendiri; mereka diekspansi secara virtual ke seluruh relasi *many-to-one*.
- Jika tabel fakta `Sales` memiliki relasi *many-to-one* ke tabel dimensi `Product`:
  $$\text{Sales}_{\text{expanded}} = \text{Sales} \bowtie \text{Product} \bowtie \text{Subcategory} \bowtie \text{Category}$$
- Filter pada tabel anak (`Sales`) tidak secara inheren memfilter tabel induk (`Product`), tetapi filter pada `Product` secara fisik merepresentasikan filter pada `Sales` yang telah diekspansi.
- **Perangkap Linear Filter Context**: Menggunakan `FILTER(Sales, Sales[Qty] > 2)` tidak hanya memfilter kolom `Sales[Qty]`, melainkan menyuntikkan seluruh tabel `Sales` yang terevolusi (*expanded table*) ke dalam filter context. Akibatnya, hubungan relasional di atas tabel tersebut dapat menimpa filter dari tabel dimensi lain (*Shadow Filter Context*).

---

### 4. Why & What

| Paradigma / Komponen | Arsitektur Tradisional (SQL / RDBMS) | VertiPaq In-Memory DAX Engine |
| :--- | :--- | :--- |
| **Model Eksekusi** | Berbasis baris (Row-Store), berbasis disk dengan buffer pool. | Berbasis kolom murni (Column-Store), *in-memory* terkompresi. |
| **Paralelisasi** | Bergantung pada Optimizer RDBMS & partisi tabel fisik. | Pembagian segmen paralel otomatis (default 8M baris/segmen per thread). |
| **Mekanisme Kalkulasi** | Pre-computed aggregations via ETL / Materialized Views. | Dynamic Context Evaluation on-the-fly via SIMD scans. |
| **Context Transition** | Subquery eksplisit / `JOIN` / Window Functions (`OVER(...)`). | Mengubah Row Context menjadi Filter Context ekuivalen via `CALCULATE`. |
| **Cost Driver** | I/O Disk, locking, memory page contention. | Penggunaan FE berlebih, SE Callback loops, Hash table materialization size. |

**Mengapa Memahami Perbedaan Ini Mutlak Diperlukan?**
Menulis DAX dengan pola pikir SQL terapan (misalnya mengandalkan iterator baris layaknya kursor SQL) akan memaksa Formula Engine mengeksekusi operasi secara sekuensial pada jutaan baris data. Desain DAX enterprise mewajibkan manipulasi aljabar relasional yang mentransformasikan kalkulasi ke dalam bentuk agregasi terdistribusi di level VertiPaq.

---

### 5. How (Workflow Detail)

Alur kalkulasi kueri DAX tingkat lanjut dari penulisan sintaks hingga rendering visual:

```
[ Visual Execution Event ]
          │
          ▼
[ 1. Query Interception & Parsing ] ──▶ FE melakukan validasi sintaks & tokenisasi.
          │
          ▼
[ 2. Logical Query Tree Generation ] ──▶ FE menentukan operator relasional aljabar (Scan, Filter, Join).
          │
          ▼
[ 3. Context Transition Resolution ] ──▶ Row context aktif diubah menjadi filter context ekuivalen
          │                               (Menginjeksi expanded table tuple ke filter context).
          ▼
[ 4. Physical Query Plan Compilation ] ──▶ Menentukan batas pemisahan antara FE execution vs SE pushdown.
          │
          ├──▶ DirectQuery? ──▶ Generate Native T-SQL/Snowflake SQL ──▶ Run on External DB.
          │
          └──▶ VertiPaq Import?
                    │
                    ▼
          [ 5. xmSQL Generation ] ──▶ FE menghasilkan query xmSQL untuk SE.
                    │
                    ▼
          [ 6. Parallel Storage Engine Scan ] ──▶ SE memindai dictionary, RLE bitstreams, dan hash tables.
                    │
                    ├── Ada CallbackDataID? ──[ Ya ]──▶ Context switch ke FE (Bottleneck!).
                    │
                    └── [ Tidak (Pure SE) ]
                               │
                               ▼
          [ 7. Datacache Materialization ] ──▶ SE mengembalikan bitstream tabular terkompresi ke RAM FE.
                               │
                               ▼
[ 8. Post-Processing & Projection by FE ] ──▶ FE melakukan sorting, dynamic joins, un-pivoting, string rendering.
                               │
                               ▼
[ 9. Result Packet Transmission ] ──▶ Kirim dataset final via Tabular Object Model (TOM) ke Reporting Engine.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Restoran Skala Industri
Bayangkan FE adalah **Executive Chef** (sangat cerdas, mampu memasak teknik tinggi, tetapi hanya satu orang / *single-threaded*). VertiPaq SE adalah **Brigade Cook Assistants** (16 orang yang bekerja simultan, sangat cepat memotong bawang atau merebus air, tetapi hanya mengerti instruksi dasar: potong, cuci, timbang).

- **Kode DAX Teroptimasi**: Executive Chef memberi perintah SE: *"Kalian ber-16, ambil data transaksi 2023, filter status 'Completed', hitung totalnya per kategori produk, lalu bawa total ringkasnya ke saya!"* SE memotong jutaan data serentak dalam milidetik, membawa 5 baris ringkasan ke Chef. Chef hanya menyusun garnish di atas piring.
- **Callback Loop (Kode DAX Buruk)**: Executive Chef memberi perintah: *"Kalian ber-16, ambil data. Tapi setiap kali kalian melihat baris data, stop! Bawa baris itu ke meja saya, biarkan saya periksa nilainya menggunakan fungsi kalkulasi custom saya, lalu kalian ambil lagi satu per satu."* Kecepatan 16 asisten menjadi lumpuh; dapur kolaps karena antrean panjang menuju meja Chef.

#### Diagram Transisi Konteks dan Expanded Table

```
DimCustomer (Parent)                  FactSales (Child)
+------------+------------+          +---------+------------+-------+
| CustomerID | Region     |          | SalesID | CustomerID | NetAmt|
+------------+------------+          +---------+------------+-------+
| C001       | APAC       | <─────── | S1001   | C001       | 500   |
| C002       | EMEA       |          | S1002   | C001       | 250   |
+------------+------------+          | S1003   | C002       | 100   |
                                     +---------+------------+-------+
Ketika CALCULATE dieksekusi di dalam iterasi baris FactSales:
Baris aktif: S1001 ──▶ Context Transition mengonversi baris S1001 menjadi:
Filter Context: FactSales[SalesID] = S1001 
             && FactSales[CustomerID] = C001 
             && FactSales[NetAmt] = 500
Dampaknya pada EXPANDED TABLE:
FactSales diekspansi mencakup seluruh relasi:
             && DimCustomer[CustomerID] = C001
             && DimCustomer[Region] = "APAC"

Filter menyebar naik (propagate upward) dari anak ke induk melalui expanded table!
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengeliminasi CallbackDataID pada Iterasi
*Kasus:* Menghitung total penjualan hanya untuk transaksi dengan nilai di atas rata-rata kategori.

##### Anti-Pattern (Menghasilkan CallbackDataID)
```dax
-- Buruk: Iterator memanggil CALCULATE berulang kali di dalam loop baris
TotalSales_AntiPattern = 
SUMX(
    FactSales,
    IF(
        FactSales[Amount] > CALCULATE(AVERAGE(FactSales[Amount]), ALL(FactSales)),
        FactSales[Amount],
        0
    )
)
```

##### Optimized Pattern (100% Storage Engine Pushdown)
```dax
-- Bersih: Menghitung skalar terlebih dahulu ke dalam variabel (FE hitung 1x), 
-- lalu evaluasi agregasi berbasis kolom via SE
TotalSales_Optimized = 
VAR _GlobalAvg = 
    CALCULATE(
        AVERAGE(FactSales[Amount]), 
        ALL(FactSales)
    )
RETURN
    CALCULATE(
        SUM(FactSales[Amount]),
        KEEPFILTERS(FactSales[Amount] > _GlobalAvg)
    )
```

---

#### Practical Example: Dynamic Currency Conversion dengan Historical Exchange Rate
Model skala enterprise mewajibkan konversi mata uang dinamis di mana transaksi faktur menggunakan mata uang lokal, dan dikonversi ke mata uang yang dipilih pelapor menggunakan kurs harian penutupan (*closing daily spot rate*).

##### Data Model
- `FactSales` (`SalesID`, `DateKey`, `CurrencyKey`, `LocalAmount`)
- `FactExchangeRate` (`DateKey`, `SourceCurrencyKey`, `TargetCurrencyKey`, `SpotRate`)
- `DimCurrency` (`CurrencyKey`, `CurrencyCode`)
- Disconnected slicer: `ReportingCurrency` (`TargetCurrencyKey`, `TargetCurrencyCode`)

```dax
-- Ukuran Enterprise untuk Konversi Mata Uang Dinamis Berbasis Vektor
Sales_Converted_ReportedCurrency = 
VAR _SelectedTargetCurrency = 
    SELECTEDVALUE( 'ReportingCurrency'[TargetCurrencyKey] )
VAR _IsSingleCurrencySelected = 
    NOT( ISBLANK( _SelectedTargetCurrency ) )

RETURN
    IF(
        NOT( _IsSingleCurrencySelected ),
        -- Guard clause jika pengguna memilih lebih dari satu mata uang di slicer
        BLANK(),
        
        -- Memanfaatkan SUMX di atas granularity gabungan (Date & Currency) bukan granularity baris FactSales
        -- Menurunkan jumlah iterasi dari ratusan juta baris menjadi ribuan partisi harian
        SUMX(
            SUMMARIZE(
                FactSales,
                FactSales[DateKey],
                FactSales[CurrencyKey]
            ),
            VAR _CurrentDateKey = FactSales[DateKey]
            VAR _CurrentSourceCurrency = FactSales[CurrencyKey]
            
            -- Ambil kurs tukar yang relevan untuk partisi saat ini
            VAR _ExchangeRate = 
                LOOKUPVALUE(
                    FactExchangeRate[SpotRate],
                    FactExchangeRate[DateKey], _CurrentDateKey,
                    FactExchangeRate[SourceCurrencyKey], _CurrentSourceCurrency,
                    FactExchangeRate[TargetCurrencyKey], _SelectedTargetCurrency,
                    1.0 -- Fallback jika source == target
                )
                
            -- Agregasi FactSales untuk partisi date-currency aktif
            VAR _LocalAmount = 
                CALCULATE( SUM( FactSales[LocalAmount] ) )
                
            RETURN
                _LocalAmount * _ExchangeRate
        )
    )
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Semi-Additive Inventory Snapshot & Non-Visual Allocations pada Bank/FinTech
Sebuah institusi perbankan global memiliki tabel fakta ledger `FactAccountDailySnapshot` dengan total data **1,8 miliar baris** (pencatatan saldo harian rekening nasabah selama 3 tahun terakhir). 

##### Permasalahan:
1. Menghitung saldo akhir periode (*Closing Balance*) pada rentang tanggal dinamis (Bulan, Kuartal, Tahun berjalan).
2. Saldo bersifat *semi-additive* (tidak dapat dijumlahkan melintasi dimensi waktu; harus mengambil saldo tanggal transaksi terakhir yang tercatat dalam periode tersebut).
3. Melakukan alokasi biaya overhead pusat secara proporsional ke unit bisnis berdasarkan saldo akhir rata-rata tertimbang (*Weighted Average Daily Balance*), tanpa menyebabkan kehabisan memori (*out-of-memory crash* / visual memory limits 2 GB per query).

##### Solusi Arsitektural:
1. Hindari penggunaan fungsi `LASTDATE` atau `CLOSINGBALANCEMONTH` standar yang memicu iterasi lambat pada miliaran baris.
2. Gunakan teknik *Window Reduction* memanfaatkan kombinasi `CALCULATE`, `KEEPFILTERS`, dan pembacaan Max DateKey secara presisi melalui Storage Engine.
3. Alokasikan overhead menggunakan tabel jembatan tervirtualisasi via `TREATAS` untuk memangkas *Shadow Context Transition*.

```dax
-- 1. Saldo Penutupan Akun Efisien (Pure SE Pushdown)
Balance_Closing = 
VAR _MaxDateKeyInContext = MAX( 'DimDate'[DateKey] )
VAR _LatestSnapshotDateKey = 
    CALCULATE(
        MAX( FactAccountDailySnapshot[DateKey] ),
        FactAccountDailySnapshot[DateKey] <= _MaxDateKeyInContext,
        REMOVEFILTERS( 'DimDate' )
    )
RETURN
    IF(
        NOT( ISBLANK( _LatestSnapshotDateKey ) ),
        CALCULATE(
            SUM( FactAccountDailySnapshot[BalanceAmount] ),
            FactAccountDailySnapshot[DateKey] = _LatestSnapshotDateKey,
            REMOVEFILTERS( 'DimDate' )
        )
    )

-- 2. Average Daily Balance (ADB)
Balance_AverageDaily = 
AVERAGEX(
    VALUES( 'DimDate'[DateKey] ),
    [Balance_Closing]
)

-- 3. Dynamic Allocation of Center Overhead ke Sub-Unit Bisnis
Overhead_Allocated_Amount = 
VAR _TotalADBGlobal = 
    CALCULATE(
        [Balance_AverageDaily],
        ALL( 'DimBusinessUnit' )
    )
VAR _CurrentUnitADB = [Balance_AverageDaily]
VAR _AllocationWeight = 
    DIVIDE( _CurrentUnitADB, _TotalADBGlobal, 0 )
VAR _TotalOverheadPool = 
    CALCULATE(
        SUM( FactCorporateOverhead[OverheadCost] ),
        -- Mengalirkan filter waktu dari slicer ke tabel overhead yang disconnected via TREATAS
        TREATAS(
            VALUES( 'DimDate'[MonthYearKey] ),
            FactCorporateOverhead[MonthYearKey]
        )
    )
RETURN
    _TotalOverheadPool * _AllocationWeight
```

##### Hasil Pengujian DAX Studio:
- **Baseline (Standard DAX Pattern with LASTDATE & ITERATORS)**:
  - Total Query Duration: **18.420 ms**
  - Formula Engine: **88,2%** (Penyebab utama: ribuan panggilan iterasi FE).
  - Memory Granted: **1.840 MB**.
- **Refactored Architecture**:
  - Total Query Duration: **312 ms**
  - Storage Engine: **94,6%** (4 kueri xmSQL paralel, 0 CallbackDataID).
  - Memory Granted: **48 MB**.

---

### 9. Trade-offs

```
+-------------------------------------------------------------------------------+
|                       TRADE-OFF ANALYSIS IN ADVANCED DAX                      |
+------------------------------------+------------------------------------------+
| STRATEGI                           | KONSEKUENSI & BIAYA SISTEM               |
+------------------------------------+------------------------------------------+
| DirectQuery vs Import Mode         | Import memakan RAM tinggi, tetapi latensi|
|                                    | sub-detik. DirectQuery hemat RAM di PBI, |
|                                    | namun membebani underlying DB & latency  |
|                                    | query terikat oleh konkurensi DB.        |
+------------------------------------+------------------------------------------+
| Expanded Table Filtering vs        | Expanded table filter (via relasi) cepat |
| TREATAS / KEEPFILTERS              | tapi rentan "side-effects" memfilter     |
|                                    | kolom lain secara tidak disengaja.       |
|                                    | TREATAS deterministik, aman, tapi        |
|                                    | butuh optimasi memori pada tabel besar.  |
+------------------------------------+------------------------------------------+
| Pre-calculated Measures vs         | Pre-calculated di ETL menghemat CPU saat |
| Dynamic DAX Calculated Measures    | report dirender, namun menggelembungkan  |
|                                    | ukuran file PBIP & mematikan fleksibilitas|
|                                    | drill-down analitik multi-dimensi.       |
+------------------------------------+------------------------------------------+
| Bi-directional Cross Filtering     | Mempermudah analisis data many-to-many,  |
|                                    | namun menghancurkan performa SE scan,    |
|                                    | memicu ambiguitas jalur relationship,    |
|                                    | dan memperbesar risiko query cycle error.|
+------------------------------------+------------------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### 1. Melakukan Context Transition di Dalam Calculated Column pada Tabel Fakta
*Penyebab:* Penggunaan `CALCULATE()` di dalam calculated column tabel fakta tanpa filter pembatas akan memindai seluruh tabel dan mengevaluasi transisi konteks untuk setiap baris. Pada 10 juta baris, formula ini mengevaluasi 10 juta filter context independen.
*Solusi:* Pindahkan logika ke tingkat ETL (Power Query, SQL View, dbt) atau buat sebagai *Measure* eksplisit.

#### 2. Kueri xmSQL Mengalami Degenerasi ke CallbackDataID
*Diagnosa via DAX Studio:*
Lihat tab **Server Timings**. Apabila muncul teks berwarna oranye/merah bertuliskan:
`CallbackDataID [ 'FactSales'[Amount] ... ]`
Ini indikasi tegas bahwa Storage Engine tidak sanggup memproses kalkulasi secara internal.
*Troubleshooting Protocol:*
1. Periksa ekspresi di dalam `FILTER()`, `SUMX()`, atau iterator lainnya.
2. Pastikan tidak ada fungsi penanganan teks (`CONCATENATE`, `SUBSTRING`), `FORMAT()`, pemanggilan measure kompleks, atau perbandingan tipe data yang berbeda (`DataType Mismatch`) di dalam blok loop SE.
3. Pecah kalkulasi menjadi bentuk *pre-filtered calculated tables* atau sederhanakan predikat filter menjadi kondisi skalar eksplisit: `Column = Value`.

#### 3. Overriding Context Tidak Sengaja dengan Penggunaan `ALL`
*Penyebab:* Pemula sering menulis `CALCULATE([Sales], ALL(DimCustomer))` untuk mengambil grand total, tetapi tidak sengaja menghapus filter cross-highlighting dari dimensi geografis atau demografis lain yang berelasi dengan tabel `DimCustomer`.
*Solusi:* Gunakan `ALLSELECTED()` untuk visual dynamic contextual totals, atau gunakan `REMOVEFILTERS(DimCustomer[CustomerKey])` jika hanya atribut spesifik yang ingin diabaikan konteksnya.

---

### 11. Best Practices (Production Checklist)

| Tahapan | Item Validasi | Status Verifikasi |
| :--- | :--- | :--- |
| **Model Design** | Skema 100% Star Schema murni (Semua snowflake dinormalisasi balik ke dimensi jika memungkinkan). | [ ] |
| **Relationship** | Menghilangkan relasi Many-to-Many fisik (*bi-directional cross-filtering* dilarang di tabel fakta). | [ ] |
| **Relationship** | Semua Foreign Key di tabel fakta memiliki padanan Primary Key di dimensi (Mencegah timbulnya baris *Blank Blank row*). | [ ] |
| **DAX Measures** | Tidak ada referensi kolom tanpa nama tabel: gunakan `Table[Column]` untuk kolom, dan `[Measure]` murni untuk ukuran. | [ ] |
| **DAX Performance** | Query Metrics di DAX Studio menunjukkan rasio Formula Engine di bawah 25% dari total durasi kueri. | [ ] |
| **DAX Performance** | 0 CallbackDataID terdeteksi pada skenario pengujian volume beban puncak (Stress Test). | [ ] |
| **Formatting** | Semua kode DAX diformat menggunakan standar Tabular Editor / DAX Formatter (Long format). | [ ] |
| **Memory** | Kolom dengan kardinalitas tinggi yang tidak terpakai dalam reporting (seperti `TransactionGUID`, timestamp detail ke milidetik) dihapus dari model memori. | [ ] |

---

### 12. Hands-on Practice

Buat skrip pengujian performa tinggi berikut dan jalankan langsung pada instance DAX Studio yang terhubung ke Power BI Desktop Anda.

#### Skenario Latihan
Simulasikan model transaksi penjualan retail dan uji perbaikan *query plan* secara empiris.

#### Step 1: Penyiapan Query Baseline (Anti-Pattern)
Jalankan skrip berikut di DAX Studio dengan mengaktifkan fitur **Server Timings** (Trace -> Server Timings):

```dax
DEFINE
    MEASURE FactSales[BadDistinctCustomers] = 
        SUMX(
            VALUES(DimProduct[ProductKey]),
            CALCULATE(
                DISTINCTCOUNT(FactSales[CustomerKey]),
                FILTER(
                    FactSales,
                    FactSales[SalesQuantity] > 5
                )
            )
        )

EVALUATE
    SUMMARIZECOLUMNS(
        DimProductCategory[CategoryName],
        "ActiveHighVolumeCustomers", [BadDistinctCustomers]
    )
```
*Amati Server Timings*: Perhatikan jumlah pemanggilan xmSQL dan durasi Formula Engine yang tinggi akibat perulangan `FILTER(FactSales, ...)`.

#### Step 2: Implementasi Solusi Teroptimasi (Pure VertiPaq Execution)
Ganti measure dengan pola *vectorized execution* menggunakan `KEEPFILTERS` dan `CALCULATETABLE`:

```dax
DEFINE
    MEASURE FactSales[OptimizedDistinctCustomers] = 
        CALCULATE(
            DISTINCTCOUNT(FactSales[CustomerKey]),
            KEEPFILTERS(FactSales[SalesQuantity] > 5)
        )

EVALUATE
    SUMMARIZECOLUMNS(
        DimProductCategory[CategoryName],
        "ActiveHighVolumeCustomers", [OptimizedDistinctCustomers]
    )
```

#### Step 3: Verifikasi Metrik Kueri
1. Buka tab **Server Timings**.
2. Bandingkan metrik:
   - **FE Duration**: Harusnya turun mendekati rentang < 15ms.
   - **SE Duration**: Berada dalam rentang optimal.
   - **SE Queries**: Berkurang secara dramatis (biasanya menjadi 1 atau 2 batch query saja).
   - **SE CPU**: Rasio efisiensi thread meningkat (misal: CPU SE 40ms / Duration 10ms = 4x Core Parallelism).

---

### 13. Exercise

#### Level: Easy
Diberikan tabel `DimEmployee` dan `FactSalaries`. Buatlah sebuah Measure DAX teroptimasi bernama `[CountHighEarners]` yang menghitung jumlah karyawan yang memiliki rata-rata gaji (`FactSalaries[Salary]`) lebih besar dari 100.000 USD pada departemen aktif, tanpa menggunakan iterator baris eksplisit `FILTER(FactSalaries, ...)`.

#### Level: Medium
Buat sebuah Measure DAX `[Sales_NewCustomers_MTD]` yang menghitung total penjualan bulan berjalan (Month-to-Date) yang dihasilkan **hanya** oleh pelanggan baru (*New Customers*). Pelanggan baru didefinisikan sebagai pelanggan yang transaksi pertamanya terjadi di dalam bulan kalender yang sama dengan tanggal transaksi saat ini.

#### Level: Hard
Kembangkan pola alokasi dinamis (*Dynamic Matrix Allocation Pattern*):
Diberikan tabel fakta `FactIndirectExpense` (dicatat pada level `ExpenseCategoryKey` dan `DateKey`) dan tabel fakta terpisah `FactOperationalCost` (dicatat pada level `DepartmentKey`, `ExpenseCategoryKey`, dan `DateKey`). 
Tuliskan measure DAX untuk meredistribusikan `FactIndirectExpense` ke setiap departemen berdasarkan proporsi penggunaan operasional masing-masing departemen per kategori beban pada rentang tanggal dinamis yang dipilih user di dashboard, dengan kondisi:
1. Tidak boleh ada relasi fisik langsung antara kedua tabel fakta tersebut.
2. Tidak boleh mengubah context filter global dari slicer lain.
3. Kueri harus dievaluasi sepenuhnya menggunakan Storage Engine tanpa materialisasi baris di memori FE melebihi batas 100.000 sel per batch.

---

### 14. Challenge

**Studi Kasus Arsitektural: Real-time Multi-Tier Fraud Scoring Allocation pada Sistem Pembayaran Terdistribusi**

Sebuah penyedia sistem gateway pembayaran memproses 200 juta transaksi harian. Anda diminta mendesain arsitektur kalkulasi analitik pada Power BI Premium Capacity dengan spesifikasi:
- Tabel `FactPayments` berukuran 1,2 miliar baris (DirectQuery mode ke Google BigQuery / Snowflake).
- Tabel `AggPaymentsDaily` berukuran 5 juta baris (Import Mode in-memory VertiPaq).
- Kebutuhan bisnis: Melakukan perbandingan real-time antara *Daily Rolling 30-Day Fraud Incident Ratio* (membutuhkan data agregasi historis cepat) versus *Real-time Transaction Anomaly Score* dari transaksi 10 menit terakhir yang belum teragregasi.

**Tantangan Arsitektur:**
1. Rancang arsitektur **Composite Model** dan konfigurasi **User-defined Aggregations (Dual/Import/DirectQuery)** yang tepat.
2. Tuliskan formula skrip DAX murni untuk ukuran `[Hybrid_Fraud_Ratio]` yang secara otomatis mengalihkan eksekusi ke tabel agregasi `AggPaymentsDaily` jika visualisasi disajikan pada granularity harian/mingguan, tetapi secara transparan melakukan *pushdown* SQL kueri ke DirectQuery `FactPayments` saat operator melakukan drill-down ke level transaksi spesifik (menit/detik).
3. Buktikan secara teoritis dan melalui arsitektur logika DAX bahwa kueri tersebut tidak akan menyebabkan kegagalan out-of-memory pada FE capacity node saat visualisasi dieksekusi bersamaan oleh 200 pengguna aktif.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. **Komponen mesin eksekusi DAX manakah yang berjalan secara single-threaded?**
   - A. VertiPaq Storage Engine
   - B. DirectQuery Storage Engine
   - C. Formula Engine
   - D. Analysis Services Segment Allocator
   *(Jawaban: C. Formula Engine beroperasi secara single-threaded per kueri).*

2. **Peristiwa apa yang terjadi saat sebuah Calculated Column dihitung menggunakan fungsi `CALCULATE()`?**
   - A. Row context dihilangkan tanpa jejak.
   - B. Context Transition terjadi: row context aktif dikonversi menjadi filter context ekuivalen.
   - C. Terjadi direct pass-through ke SQL Server tanpa memori.
   - D. Storage Engine langsung membuat partisi baru.
   *(Jawaban: B).*

3. **Format bahasa perantara apakah yang digunakan oleh Formula Engine untuk berkomunikasi dengan VertiPaq Storage Engine?**
   - A. T-SQL
   - B. Kusto (KQL)
   - C. xmSQL
   - D. DAX Native Bytecode
   *(Jawaban: C).*

4. **Operasi manakah di bawah ini yang membatasi pemrosesan paralel pada Storage Engine dan memicu context switch kembali ke Formula Engine?**
   - A. Bit-vector filtration
   - B. Hash Join pada kolom integer
   - C. CallbackDataID
   - D. Aggregation pushdown
   *(Jawaban: C).*

5. **Apa fungsi utama dari `KEEPFILTERS` dalam ekspresi DAX?**
   - A. Menghapus seluruh filter context yang ada sebelumnya.
   - B. Memodifikasi semantik `CALCULATE` agar tidak menimpa filter context yang sudah ada untuk kolom yang sama, melainkan melakukan interseksi (AND).
   - C. Mengunci memori agar tidak dialokasikan ulang oleh garbage collection.
   - D. Menjaga query plan agar tetap berada di Formula Engine.
   *(Jawaban: B).*

---

#### Intermediate Questions
6. **Perhatikan ekspresi berikut:**
   ```dax
   CALCULATE(
       [Total Sales],
       FactSales[Quantity] > 10
   )
   ```
   **Secara internal oleh Formula Engine, predikat filter tersebut diubah menjadi ekspresi apa?**
   - A. `FILTER(FactSales, FactSales[Quantity] > 10)`
   - B. `FILTER(ALL(FactSales[Quantity]), FactSales[Quantity] > 10)`
   - C. `KEEPFILTERS(FactSales[Quantity] > 10)`
   - D. `VALUES(FactSales[Quantity])`
   *(Jawaban: B. Predikat skalar sederhana diubah menjadi `FILTER(ALL(Column), Condition)` sehingga secara default membersihkan filter lain pada kolom yang sama).*

7. **Apa bahaya dari konsep *Expanded Tables* ketika melakukan filtering dengan tabel utuh seperti `CALCULATE([Sales], FILTER(FactSales, ...))`?**
   - A. Tabel fakta tidak bisa dibaca oleh VertiPaq.
   - B. Filter context akan menyuntikkan seluruh kolom tabel fakta dan seluruh kolom dimensi terkait yang berelasi many-to-one, berpotensi menghapus/menimpa filter dimensi lain yang ada di report visual (*Shadow Context*).
   - C. Menyebabkan DirectQuery database mengalami table lock permanen.
   - D. Menghapus relasi skema star secara ireversibel.
   *(Jawaban: B).*

8. **Manakah dari fungsi berikut yang paling efisien untuk mentransfer filter context antar tabel yang tidak memiliki relasi fisik resmi tanpa memicu perluasan tabel?**
   - A. `LOOKUPVALUE`
   - B. `RELATEDTABLE`
   - C. `TREATAS`
   - D. `CROSSJOIN`
   *(Jawaban: C. `TREATAS` mentransfer silsilah data (*data lineage*) di tingkat memori secara virtual tanpa membangkitkan cost relasi fisik).*

9. **Dalam DAX Studio Server Timings, metrik CPU SE bernilai 1.200 ms sedangkan SE Duration bernilai 150 ms. Apa arti dari angka ini?**
   - A. Terjadi bottleneck parah pada Formula Engine.
   - B. VertiPaq memanfaatkan multithreading secara efektif di mana rata-rata 8 thread CPU bekerja simultan (1200 / 150 = 8).
   - C. Server kehabisan resource memori dan mengalami paging disk.
   - D. Kueri tersebut gagal dan dihitung ulang 8 kali.
   *(Jawaban: B).*

10. **Kapan sebuah kalkulasi `DISTINCTCOUNT` dapat didorong secara murni (pure pushdown) ke VertiPaq Storage Engine?**
    - A. Hanya jika tabel fakta memiliki kurang dari 1.000 baris.
    - B. Jika ekspresi distinct count diterapkan langsung pada kolom fisik tanpa adanya iterator Formula Engine atau callback yang disuntikkan ke dalam filter context.
    - C. DISTINCTCOUNT tidak pernah bisa dieksekusi di Storage Engine.
    - D. Hanya jika cardinality kolom bernilai biner (0 atau 1).
    *(Jawaban: B).*

---

#### Production Scenario Questions

11. **Skenario 1:**
Sebuah laporan operasional di Power BI Service mengalami timeout (eksekusi > 225 detik). Tim Anda menemukan measure berikut yang digunakan di dalam visual Matrix dengan ribuan baris:
```dax
BadMarginRatio = 
SUMX(
    FactInternetSales,
    RELATED(DimProduct[StandardCost]) * FactInternetSales[OrderQuantity]
)
```
Tabel `FactInternetSales` berisi 85 juta baris. 
**Tindakan rekayasa sistem manakah yang harus segera diambil untuk menurunkan waktu kueri menjadi < 1 detik?**
- A. Mengganti DirectQuery menjadi Import mode lalu menambahkan RAM server.
- B. Menghilangkan iterasi baris dengan membuat calculated column di ETL/SQL untuk `TotalCost = StandardCost * OrderQuantity`, lalu menulis measure `SUM(FactInternetSales[TotalCost])`, atau memanfaatkan `SUMX(DimProduct, DimProduct[StandardCost] * [TotalQty])` untuk mereduksi ruang iterasi dari 85 juta baris menjadi ribuan baris produk.
- C. Membungkus fungsi dengan `CALCULATE(..., KEEPFILTERS())`.
- D. Mengubah relasi antara `FactInternetSales` dan `DimProduct` menjadi bi-directional.
*(Jawaban: B. Solusi utama: hindari iterasi baris pada tabel fakta 85 juta baris untuk komputasi perkalian kolom dimensi. Pindahkan kalkulasi ke level materialisasi data pipeline atau balikkan iterasi ke tabel dimensi yang lebih ramping).*

12. **Skenario 2:**
Anda memiliki model composite. Visualisasi berbasis agregasi harian merespons lambat (8 detik). Saat diperiksa di DAX Studio, visual memicu kueri T-SQL DirectQuery langsung ke database Cloud RDBMS, padahal tabel `Agg_Sales_Daily` (Import Mode) sudah tersedia di model.
**Mengapa optimizer query tidak menggunakan Aggregation Table yang sudah dibuat?**
- A. Karena ukuran tabel import terlalu kecil.
- B. Granularity kolom grouping atau measure yang diminta visualisasi tidak cocok dengan pemetaan pada konfigurasi *Manage Aggregations* (misal: kolom foreign key atau formula measure tidak memiliki mapping agregasi eksplisit: `Sum`, `Count`, `GroupBy`).
- C. Karena Formula Engine menolak kueri DirectQuery secara otomatis.
- D. Karena tipe data kolom adalah string.
*(Jawaban: B. Power BI Aggregation Engine hanya akan memotong rute (hit the aggregation table) jika semua field dalam visualisasi tercakup dalam metadata konfigurasi tabel agregasi. Jika ada 1 field yang absen, kueri akan jatuh (miss) langsung ke DirectQuery).*

13. **Skenario 3:**
Diimplementasikan Row-Level Security (RLS) berbasis dynamic user permissions:
```dax
DimUserSecurity[Email] = USERPRINCIPALNAME()
```
Tabel `DimUserSecurity` terhubung ke `DimCustomer` via relasi many-to-many bi-directional filter context. Setelah implementasi, seluruh performa dashboard global turun drastis (latensi naik 500%).
**Apa akar masalah arsitektur tersebut dan bagaimana memitigasinya?**
- A. Bi-directional security filter memaksa Formula Engine memproses relasi secara non-vektor untuk setiap visual, menghalangi VertiPaq datacache sharing antar visual. Solusinya: Ubah relasi menjadi satu arah (one-to-many) dari security table ke dimension, atau manfaatkan `TREATAS` di dalam ekspresi filter RLS pada tabular model.
- B. `USERPRINCIPALNAME()` mengunci disk I/O sistem operasi Analysis Services.
- C. RLS hanya boleh digunakan maksimal untuk 5 user aktif per capacity.
- D. Skema Star harus diubah menjadi Snowflake agar bi-directional filter bekerja optimal.
*(Jawaban: A. Relasi bi-directional dinamis pada tabel otorisasi RLS menghancurkan kemampuan caching VertiPaq dan memaksa evaluasi per-user secara sekuensial pada Formula Engine).*

---

### 16. Summary

```
                 ADVANCED DAX PERFORMANCE MATRIX SUMMARY
┌─────────────────────────────────┬───────────────────────────────────────────┐
│ PRINCIPLE                       │ ARCHITECTURAL RULE                        │
├─────────────────────────────────┼───────────────────────────────────────────┤
│ Engine Optimization             │ Maximize VertiPaq Storage Engine (SE)     │
│                                 │ scans; Minimize Formula Engine (FE) steps. │
├─────────────────────────────────┼───────────────────────────────────────────┤
│ Callback Elimination            │ Eradicate CallbackDataID by refactoring   │
│                                 │ nested iterative measures into pure scalar│
│                                 │ column predicates.                        │
├─────────────────────────────────┼───────────────────────────────────────────┤
│ Relationship Propagation        │ Respect Expanded Tables topology; beware  │
│                                 │ unintended filter propagation and shadow  │
│                                 │ filter context overwrites.                │
├─────────────────────────────────┼───────────────────────────────────────────┤
│ Context Transition Control      │ Avoid CALCULATE in large table iterations │
│                                 │ and Fact table Calculated Columns.        │
├─────────────────────────────────┼───────────────────────────────────────────┤
│ Enterprise Scale Engineering    │ Implement Composite Aggregations and      │
│                                 │ virtual relationships (TREATAS) for       │
│                                 │ high-cardinality multi-billion datasets.  │
└─────────────────────────────────┴───────────────────────────────────────────┘
```

Penguasaan DAX pada skala enterprise berakar pada komputasi efisien di tingkat perangkat keras. Dengan mendesain ekspresi analitik yang memanfaatkan arsitektur penyimpanan kolumnar *in-memory*, paralelisasi core CPU melalui VertiPaq, dan penanganan relasi secara deterministik, arsitek data dapat menghadirkan analitik analitis yang instan dan scalable di atas beban kerja data volume tinggi.