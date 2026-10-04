# Bab 02: Dimensional Data Modeling & Relational Semantics

## Module 01: Fondasi Kimball Dimensional Modeling & Engine Semantics di Power BI

---

### 1. Learning Objectives (Spesifik & Terukur)
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang dan Mengimplementasikan** skema Kimball Star Schema tingkat enterprise menggunakan T-SQL dan TMDL (*Tabular Model Definition Language*) yang teroptimasi untuk VertiPaq Engine.
- **Menganalisis dan Membedah** dampak skema relasional (1:1, 1:N, N:M) terhadap struktur internal VertiPaq (kamus/dictionary, RLE, bit-packing) serta konsumsi RAM.
- **Mengontrol Propagasi Filter Context** secara deterministik melalui *Single-Direction*, *Bi-directional Cross-filtering*, dan *Expanded Tables* menggunakan DAX relasional primitif (`RELATED`, `RELATEDTABLE`, `USERELATIONSHIP`, `CROSSFILTER`).
- **Mendiagnosis dan Memitigasi** anomali semantik kritis seperti *Referential Integrity Violation Blank Rows*, *Chasm Traps*, *Fan Traps*, serta *Ambiguous Filter Paths*.
- **Mengevaluasi Trade-off Kinerja** antara Star Schema murni, Snowflake Schema, dan Single Flat Table (OBT - *One Big Table*) berdasarkan metrik SE (*Storage Engine*) vs FE (*Formula Engine*) latency.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Pemodelan data analitik modern di Power BI beroperasi di atas irisan dua paradigma: **Kimball Dimensional Modeling Architecture** dan **VertiPaq In-Memory Columnar Database Engine**. Kesalahan persepsi paling fatal di kalangan data engineer adalah menganggap pemodelan Power BI serupa dengan pemodelan relasional transaksional (3NF / Third Normal Form).

```
+-------------------------------------------------------------------------+
|                              MENTAL MODEL                               |
|                                                                         |
|      OLTP (3NF / Relational)              Power BI (Kimball Star Schema)|
|   +----------------------------+           +-------------------------+  |
|   | Focus: ACID, Write-Optimal |           | Focus: OLAP Read-Optimal|  |
|   | Goal: Hindari Redudansi    |    ===>   | Goal: Pangkas Jalur Join|  |
|   | Relasi: Kompleks, Deep-Tree|           | Relasi: Star Schema     |  |
|   | Engine: Row-oriented       |           | Engine: VertiPaq Columnar| |
|   +----------------------------+           +-------------------------+  |
+-------------------------------------------------------------------------+
```

#### Star Schema vs. 3NF: Paradigma Expanded Tables
Di dalam Power BI Semantic Model, relasi fisik bukanlah sekadar foreign key constraint penjamin integritas data, melainkan **jalur propagasi filter otomatis**. VertiPaq mengadopsi konsep **Expanded Tables** (*Tabel yang Diperluas*):
- Setiap tabel dimensi $D$ yang berelasi $1:N$ dengan tabel fakta $F$ secara konseptual memperluas tabel fakta tersebut ($F \rightarrow F_{expanded}$).
- $F_{expanded}$ berisi seluruh kolom lokal milik $F$ ditambah seluruh kolom dari semua tabel dimensi yang berada di sisi `1` dari relasi direct maupun transitive.
- Filter yang diterapkan pada kolom tabel dimensi langsung mereduksi baris pada $F_{expanded}$, dieksekusi secara native pada tingkat bit-vector storage engine tanpa overhead SQL JOIN tradisional.

#### VertiPaq Internal Mechanics: Mengapa Star Schema Wajib?
VertiPaq melakukan partisi vertikal data ke dalam kolom-kolom terpisah. Efisiensi kompresi ditentukan oleh **Cardinality** (jumlah nilai unik dalam kolom). 
1. **Dictionary Encoding:** Setiap nilai unik dipetakan ke integer ID (Token ID).
2. **Columnar Sorting:** VertiPaq memilih urutan sort optimal untuk memaksimalkan kompresi *Run-Length Encoding* (RLE).
3. **Bit-Packing:** Nilai Token ID dikompresi ke jumlah bit minimum berbasis $\lceil \log_2(\text{cardinality}) \rceil$.

Ketika skema diubah menjadi *Snowflake* (normalisasi dimensi bertingkat), efisiensi kompresi dan kecepatan pencarian indeks relasi VertiPaq menurun drastis karena *Formula Engine* (FE) terpaksa turun tangan mengelola traversal join multi-hop yang tidak dapat diselesaikan secara murni oleh *Storage Engine* (SE).

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di lingkungan enterprise dengan volume data ratusan juta baris, kegagalan menerapkan skema dimensional yang tepat berakibat langsung pada:
1. **Memory Bloat & Capacity Throttling:** Normalisasi berlebihan (Snowflake) atau penggunaan OBT (*One Big Table*) dengan string bervolume tinggi menyebabkan ukuran Semantic Model membengkak secara eksponensial, melampaui batas memori Power BI Premium/Fabric Capacity (misal SKU F64).
2. **Non-Deterministic Calculations (Silent Data Corruption):** Penggunaan relasi dua arah (*Bi-directional cross-filtering*) untuk mengatasi masalah slicer secara instan sering memicu *ambiguous path* atau *Chasm Trap*, menghasilkan angka agregasi penjualan yang terduplikasi berkali-kali lipat tanpa memicu error sintaks.
3. **Degradasi Storage Engine Batching:** Relasi *Many-to-Many* ($N:M$) fisik tanpa *bridge table* memaksa FE memproses agregasi secara sekuensial (single-threaded), membatalkan akselerasi komputasi paralel multi-core dari SE.

---

### 4. Arsitektur & Diagram Komponen

#### A. Arsitektur Star Schema Klasik Enterprise
Diagram berikut menunjukkan struktur Star Schema murni dengan tabel fakta transaksi penjualan, dimensi bertipe konform (*Conformed Dimensions*), dan implementasi *Role-Playing Dimension* melalui relasi aktif vs inaktif:

```
                  +--------------------------+
                  |   Dim_Customer (1)       |
                  +--------------------------+
                  | PK CustomerKey (Surrogate)
                  |    CustomerAlternateID   |
                  |    CustomerName          |
                  |    CustomerSegment       |
                  +-------------+------------+
                                | 1
                                | 
                                | N
+----------------------+  N   +---+-------------------------+   N   +----------------------+
|    Dim_Product (1)   +----->|       Fact_Sales (N)        |<------+   Dim_Store (1)      |
+----------------------+      +-----------------------------+       +----------------------+
| PK ProductKey        |      | FK ProductKey               |       | PK StoreKey          |
|    ProductSKU        |      | FK CustomerKey              |       |    StoreCode         |
|    ProductName       |      | FK StoreKey                 |       |    StoreRegion       |
|    Subcategory       |      | FK OrderDateKey   (Active)  |       +----------------------+
|    Category          |      | FK ShipDateKey   (Inactive) |
+----------------------+      |    SalesOrderNumber         |
                              |    SalesAmount              |
                              |    OrderQuantity            |
                              +---+------------+------------+
                                  | N          | N
             (Active: OrderDate)  |            |  (Inactive: ShipDate)
                                  | 1          | 1
                        +---------+------------+----+
                        |      Dim_Date (1)         |
                        +---------------------------+
                        | PK DateKey (YYYYMMDD)     |
                        |    FullDate               |
                        |    Year                   |
                        |    Quarter                |
                        |    MonthName              |
                        +---------------------------+
```

#### B. Propagasi Filter Engine & VertiPaq Data Structures
Di balik layar, relasi $1:N$ dikelola oleh VertiPaq melalui struktur penunjuk integer (*relationship index*) berkecepatan tinggi:

```
[Dim_Date]                                         [Fact_Sales]
PK: DateKey                                        FK: OrderDateKey
Token ID  Value        Relationship Index          Token ID  Value    Data Page Row
+-------+----------+   +-------------------+       +-------+----------+---------------+
| 0     | 20260301 |-->| Pointers to Rows: |------>| 0     | 20260301 | Row 0, Row 3  |
| 1     | 20260302 |   | Fact rows: 0, 3   |       | 1     | 20260302 | Row 1, Row 2  |
| 2     | 20260303 |   +-------------------+       +-------+----------+---------------+
+-------+----------+   
       |
       |  Slicer Filter: DateKey = 20260301 (Token 0)
       v
[Storage Engine Scan]
Filter context di Dim_Date mereduksi baris aktif.
Relationship Index langsung membatasi bitmask Fact_Sales hanya pada baris [0, 3].
Operasi agregasi (misal SUM(SalesAmount)) HANYA mengevaluasi baris yang ditandai bitmask.
Formula Engine TIDAK PERLU melakukan evaluasi nested-loop join.
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### Evaluasi Context & Expanded Table Theory
Filter context tidak menyaring tabel dimensi secara langsung di tingkat tampilan visual, melainkan menyaring *Expanded Table*. Jika kita memiliki relasi `Dim_Customer[CustomerKey] (1) ---> (N) Fact_Sales[CustomerKey]`:
- Definisi matematis dari tabel `Fact_Sales` yang diperluas adalah:
  $$\text{Expanded}(Fact\_Sales) = Fact\_Sales \bowtie Dim\_Customer \bowtie Dim\_Product \bowtie Dim\_Date$$
- Ketika sebuah filter diterapkan pada `Dim_Customer[CustomerSegment] = "Enterprise"`, ekspresi DAX:
  ```dax
  CALCULATE(COUNTROWS(Fact_Sales))
  ```
  bekerja karena filter pada `Dim_Customer` otomatis berada di dalam konteks $\text{Expanded}(Fact\_Sales)$.
- Sebaliknya, filter pada `Fact_Sales` **tidak secara default** menyaring $\text{Expanded}(Dim\_Customer)$, kecuali jika *Bi-directional Cross-filtering* diaktifkan, atau fungsi seperti `CROSSFILTER` digunakan, atau manipulasi konteks tabel eksplisit dijalankan (`CALCULATETABLE`).

#### Referential Integrity & Tabel "Blank Row" Misterius
VertiPaq menjamin konsistensi query engine bahkan ketika integritas referensial data warehouse asal rusak.
- Jika terdapat nilai Foreign Key pada `Fact_Sales` (misal: `ProductKey = 9999`) yang **tidak ada** pada Primary Key `Dim_Product`, VertiPaq secara otomatis menyisipkan sebuah **Blank Row** dummy ke dalam `Dim_Product`.
- Semua baris transaksi dengan ID yatim (*orphaned records*) ini dipetakan ke Blank Row tersebut.
- Dalam DAX, `VALUES(Dim_Product[ProductKey])` akan mengembalikan Blank Row tersebut jika terdapat pelanggaran referensial. Sebaliknya, `DISTINCT(Dim_Product[ProductKey])` akan mengabaikan Blank Row teknis ini kecuali jika blank memang eksplisit ada di data sumber.

#### Relasi Many-to-Many ($N:M$) Fisik vs Weak Relationships
Power BI mengizinkan relasi $N:M$ tanpa validasi keunikan kunci pada kedua tabel. Secara arsitektural:
1. Relasi menjadi *Weak Relationship* (Relasi Lemah).
2. Konsep *Expanded Tables* runtuh untuk relasi ini: filter dari Tabel A dapat mereduksi Tabel B, tetapi Tabel A **bukan bagian dari expanded table** Tabel B.
3. VertiPaq tidak dapat menggunakan relationship index pointer native berbasis token ID langsung. Sebagai gantinya, query dieksekusi dengan membangun tabel translasi virtual intermediate secara dinamis pada saat eksekusi query (dynamic materialization), yang meningkatkan beban memori dan mematikan optimasi komputasi Storage Engine.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi komprehensif skema data warehouse analitik di SQL Server/Fabric DW, diikuti definisi semantik layer menggunakan TMDL (*Tabular Model Definition Language*) dan DAX Enterprise Measures.

#### Step 1: SQL Enterprise Star Schema DDL & ETL Stored Procedure
Script ini menyiapkan tabel fakta dan dimensi standar Kimball dengan penanganan surrogate keys, nilai tidak valid (-1), dan index optimal.

```sql
-- ============================================================================
-- 01_STAR_SCHEMA_DDL.SQL
-- Arsitektur: Kimball Enterprise Star Schema Teroptimasi VertiPaq
-- ============================================================================

-- Skema Dimensional
CREATE SCHEMA dim;
GO
CREATE SCHEMA fact;
GO

-- 1. Dimensi Tanggal (Conformed Dimension)
CREATE TABLE dim.Date (
    DateKey INT NOT NULL,                  -- Format: YYYYMMDD
    FullDate DATE NOT NULL,
    DayNumberOfWeek TINYINT NOT NULL,
    DayName VARCHAR(10) NOT NULL,
    DayNumberOfMonth TINYINT NOT NULL,
    MonthName VARCHAR(10) NOT NULL,
    MonthNumberOfYear TINYINT NOT NULL,
    CalendarQuarter TINYINT NOT NULL,
    CalendarYear SMALLINT NOT NULL,
    IsWeekend BIT NOT NULL,
    CONSTRAINT PK_dim_Date PRIMARY KEY CLUSTERED (DateKey)
);

-- 2. Dimensi Produk
CREATE TABLE dim.Product (
    ProductKey INT IDENTITY(1,1) NOT NULL, -- Surrogate Key
    ProductSKU NVARCHAR(50) NOT NULL,      -- Business / Natural Key
    ProductName NVARCHAR(100) NOT NULL,
    Category NVARCHAR(50) NOT NULL,
    Subcategory NVARCHAR(50) NOT NULL,
    CostPrice DECIMAL(18,4) NOT NULL,
    IsActive BIT NOT NULL DEFAULT 1,
    CONSTRAINT PK_dim_Product PRIMARY KEY CLUSTERED (ProductKey)
);

-- 3. Dimensi Pelanggan
CREATE TABLE dim.Customer (
    CustomerKey INT IDENTITY(1,1) NOT NULL,
    CustomerAlternateID NVARCHAR(50) NOT NULL,
    CustomerName NVARCHAR(150) NOT NULL,
    CustomerSegment NVARCHAR(50) NOT NULL,
    City NVARCHAR(50) NOT NULL,
    StateProvince NVARCHAR(50) NOT NULL,
    CountryRegion NVARCHAR(50) NOT NULL,
    CONSTRAINT PK_dim_Customer PRIMARY KEY CLUSTERED (CustomerKey)
);

-- 4. Tabel Fakta Penjualan
CREATE TABLE fact.Sales (
    SalesOrderNumber NVARCHAR(30) NOT NULL,
    SalesOrderLineNumber INT NOT NULL,
    OrderDateKey INT NOT NULL,              -- FK ke dim.Date (Role: Order Date)
    ShipDateKey INT NOT NULL,               -- FK ke dim.Date (Role: Ship Date)
    CustomerKey INT NOT NULL,               -- FK ke dim.Customer
    ProductKey INT NOT NULL,                -- FK ke dim.Product
    OrderQuantity INT NOT NULL,
    UnitPrice DECIMAL(18,4) NOT NULL,
    SalesAmount AS (CAST(OrderQuantity * UnitPrice AS DECIMAL(18,4))) PERSISTED,
    DiscountAmount DECIMAL(18,4) NOT NULL DEFAULT 0.0000,
    TotalProductCost DECIMAL(18,4) NOT NULL,
    CONSTRAINT PK_fact_Sales PRIMARY KEY CLUSTERED (SalesOrderNumber, SalesOrderLineNumber),
    CONSTRAINT FK_fact_Sales_OrderDate FOREIGN KEY (OrderDateKey) REFERENCES dim.Date(DateKey),
    CONSTRAINT FK_fact_Sales_ShipDate FOREIGN KEY (ShipDateKey) REFERENCES dim.Date(DateKey),
    CONSTRAINT FK_fact_Sales_Customer FOREIGN KEY (CustomerKey) REFERENCES dim.Customer(CustomerKey),
    CONSTRAINT FK_fact_Sales_Product FOREIGN KEY (ProductKey) REFERENCES dim.Product(ProductKey)
);

-- Foreign Key Indexing (Sangat penting untuk ETL & Source Read Isolation)
CREATE NONCLUSTERED INDEX IX_fact_Sales_OrderDateKey ON fact.Sales(OrderDateKey);
CREATE NONCLUSTERED INDEX IX_fact_Sales_ShipDateKey ON fact.Sales(ShipDateKey);
CREATE NONCLUSTERED INDEX IX_fact_Sales_CustomerKey ON fact.Sales(CustomerKey);
CREATE NONCLUSTERED INDEX IX_fact_Sales_ProductKey ON fact.Sales(ProductKey);
GO

-- Injeksi Nilai Default untuk Mencegah Referential Integrity Orphan Failure
SET IDENTITY_INSERT dim.Product ON;
INSERT INTO dim.Product (ProductKey, ProductSKU, ProductName, Category, Subcategory, CostPrice, IsActive)
VALUES (-1, 'UNKNOWN', 'Unknown / Unassigned', 'N/A', 'N/A', 0.00, 1);
SET IDENTITY_INSERT dim.Product OFF;

SET IDENTITY_INSERT dim.Customer ON;
INSERT INTO dim.Customer (CustomerKey, CustomerAlternateID, CustomerName, CustomerSegment, City, StateProvince, CountryRegion)
VALUES (-1, 'UNKNOWN', 'Unknown / Unassigned Customer', 'N/A', 'N/A', 'N/A', 'N/A');
SET IDENTITY_INSERT dim.Customer OFF;
GO
```

#### Step 2: Tabular Model Semantic Definition (TMDL Representation)
Berikut adalah definisi model semantik tingkat produksi dalam format TMDL yang mendefinisikan skema relasional, relasi aktif vs inaktif, dan visibilitas kolom foreign key:

```tmdl
// 02_SEMANTIC_MODEL.tmdl

table Dim_Date
    lineageTag: a3567-date-table
    
    column DateKey
        dataType: int64
        isKey
        isAvailableInMDX: false
        summarizeBy: none
        sourceColumn: DateKey

    column FullDate
        dataType: dateTime
        formatString: yyyy-MM-dd
        summarizeBy: none
        sourceColumn: FullDate

    column CalendarYear
        dataType: int64
        summarizeBy: none
        sourceColumn: CalendarYear

    column MonthName
        dataType: string
        sortByColumn: MonthNumberOfYear
        sourceColumn: MonthName

    column MonthNumberOfYear
        dataType: int64
        isHidden
        sourceColumn: MonthNumberOfYear

    annotation PBI_IsDataModelDateTable = 1

table Dim_Product
    lineageTag: b4920-product-table

    column ProductKey
        dataType: int64
        isKey
        isHidden
        summarizeBy: none
        sourceColumn: ProductKey

    column ProductName
        dataType: string
        sourceColumn: ProductName

    column Category
        dataType: string
        sourceColumn: Category

table Fact_Sales
    lineageTag: c8812-fact-sales-table

    column OrderDateKey
        dataType: int64
        isHidden
        summarizeBy: none
        sourceColumn: OrderDateKey

    column ShipDateKey
        dataType: int64
        isHidden
        summarizeBy: none
        sourceColumn: ShipDateKey

    column CustomerKey
        dataType: int64
        isHidden
        summarizeBy: none
        sourceColumn: CustomerKey

    column ProductKey
        dataType: int64
        isHidden
        summarizeBy: none
        sourceColumn: ProductKey

    column SalesAmount
        dataType: decimal
        formatString: \$#,##0.00;(\$#,##0.00);\$0.00
        summarizeBy: sum
        sourceColumn: SalesAmount

// Definisi Relasi Struktural Model
relationship Rel_Sales_Date_Order
    fromColumn: Fact_Sales.OrderDateKey
    toColumn: Dim_Date.DateKey
    isActive: true
    crossFilteringBehavior: singleDirection

relationship Rel_Sales_Date_Ship
    fromColumn: Fact_Sales.ShipDateKey
    toColumn: Dim_Date.DateKey
    isActive: false
    crossFilteringBehavior: singleDirection

relationship Rel_Sales_Product
    fromColumn: Fact_Sales.ProductKey
    toColumn: Dim_Product.ProductKey
    isActive: true
    crossFilteringBehavior: singleDirection
```

#### Step 3: DAX Core Enterprise Measures
Kumpulan measure DAX tingkat produksi yang memanfaatkan semantik relasional, traversal relasi inaktif, dan penanganan integritas referensi:

```dax
// ============================================================================
// DAX MEASURE SPECIFICATIONS: RELATIONAL CONTEXT
// ============================================================================

/// Measure: Total Base Sales (Menggunakan Active Relationship: OrderDate)
[Total Sales Amount] := 
SUM ( Fact_Sales[SalesAmount] )

/// Measure: Sales by Shipping Date (Mengaktifkan Inactive Relationship)
[Sales by Ship Date] := 
CALCULATE (
    [Total Sales Amount],
    USERELATIONSHIP ( Fact_Sales[ShipDateKey], Dim_Date[DateKey] )
)

/// Measure: Handling Ambiguous / Role-Playing Calculation Delta
[Transit Pipeline Sales Amount] := 
VAR _OrderedSales = [Total Sales Amount]
VAR _ShippedSales = [Sales by Ship Date]
RETURN
    _OrderedSales - _ShippedSales

/// Measure: Safe Customer Sales Contribution (Mencegah Blank Row Distortion)
[Enterprise Customer Sales Ratio] := 
VAR _AllValidSales = 
    CALCULATE (
        [Total Sales Amount],
        ALL ( Dim_Customer ),
        Dim_Customer[CustomerKey] <> -1
    )
VAR _EnterpriseSales = 
    CALCULATE (
        [Total Sales Amount],
        Dim_Customer[CustomerSegment] = "Enterprise"
    )
RETURN
    DIVIDE ( 
        _EnterpriseSales, 
        _AllValidSales, 
        0.00 
    )

/// Measure: Dynamic Cross-Filtering Calculation (Tanpa mengubah model fisik)
[Products Sold In Selected Customer Segment] := 
CALCULATE (
    DISTINCTCOUNT ( Fact_Sales[ProductKey] ),
    KEEPFILTERS ( Fact_Sales[SalesAmount] > 0 ),
    CROSSFILTER ( Fact_Sales[CustomerKey], Dim_Customer[CustomerKey], Both )
)
```

---

### 7. Edge Cases & Failure Modes

#### 1. The Chasm Trap (Multiple Facts sharing Conformed Dimensions)
- **Skenario:** Analis membuat relasi antara `Fact_Sales` dan `Fact_InventorySnapshot` melalui tabel dimensi `Dim_Product`. Analis kemudian mencoba menarik kolom `Fact_InventorySnapshot[StockOnHand]` dan `Fact_Sales[SalesAmount]` ke dalam visual bar-chart yang sama tanpa agregasi berbasis dimensi.
- **Mekanisme Kegagalan:** Query engine menghasilkan query join Cartesian virtual antara kedua tabel fakta jika relasi dua arah diaktifkan secara naif pada kedua relasi fakta-dimensi. Nilai stok akan dikalikan dengan jumlah baris transaksi penjualan, menghasilkan angka persediaan fiktif senilai milyaran unit.
- **Mitigasi Teknis:** Jangan pernah membuat relasi langsung antara dua tabel fakta. Wajib menggunakan arsitektur Kimball: kedua fakta berelasi $N:1$ ke Conformed Dimension, dan perhitungan multi-fakta wajib dikapsulasi dalam DAX measure independen menggunakan agregasi terpisah sebelum dilakukan operasi aritmetika:
  ```dax
  Inventory Turnover Ratio = 
  DIVIDE ( 
      [Total Sales Cost], 
      [Average Inventory Value], 
      BLANK() 
  )
  ```

#### 2. The Diamond Relationship Ambiguity
- **Skenario:** Relasi membentuk siklus tertutup: `Dim_Customer` menyaring `Fact_Sales`, tetapi juga menyaring `Dim_Geography`. Di saat yang sama, `Fact_Sales` juga memiliki relasi langsung ke `Dim_Geography`.
- **Mekanisme Kegagalan:** Power BI mendeteksi *Ambiguous Relationship Path* dan secara sepihak menonaktifkan salah satu relasi menjadi inaktif. Jika dipaksa menggunakan relasi dua arah (*Bi-directional*), rute evaluasi filter menjadi non-deterministik dan bergantung pada urutan filter visual di front-end.
- **Mitigasi:** Hilangkan relasi Snowflake antara `Dim_Customer` dan `Dim_Geography`. Terapkan denormalisasi kolom wilayah (`City`, `CountryRegion`) langsung ke dalam `Dim_Customer` dan `Dim_Store` untuk menjaga topologi *Star* murni.

#### 3. Blank Row Propagation pada Visual Matrix
- **Skenario:** Sebuah dimensi memiliki nilai Primary Key yang hilang dari tabel fakta (inkonsistensi ETL).
- **Mekanisme Kegagalan:** Visual Power BI menampilkan baris kosong `(Blank)` pada baris matriks. Ketika pengguna menerapkan visual filter "Is Not Blank", transaksi yang bersangkutan ikut terbuang secara semantik, merusak total saldo akhir KPI ($Grand\ Total \neq \sum Rows$).
- **Mitigasi:** Gunakan teknik *Unknown Member Replacement* di level ETL pipeline SQL (memetakan semua `NULL` atau orphaned keys ke `-1`). Pada Semantic Layer, tandai baris surrogate key `-1` dengan label eksplisit: `"Unknown / Unassigned"`.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Parameter | Star Schema (Kimball) | Snowflake Schema | One Big Table (OBT / Flat) |
| :--- | :--- | :--- | :--- |
| **VertiPaq Memory Efficiency** | **Tertinggi**. Kamus data ramping, rasio kompresi optimal. | **Sedang**. Terlalu banyak tabel kecil menciptakan overhead dictionary internal. | **Rendah**. Duplikasi string teks bervolume tinggi meningkatkan footprint memori. |
| **Storage Engine Performance** | **Optimal**. Bitmask traversal 1-hop, eksekusi query multi-threaded native. | **Lambat**. Membutuhkan FE multi-hop join context transition. | **Sangat Cepat pada Scan Sederhana**, namun lambat pada agregasi multi-grain. |
| **Maintainability & Governance**| **Tinggi**. Dimensi bersifat terpusat (*Conformed*), mudah dipahami bisnis. | **Rumit**. Model navigasi terlalu dalam bagi self-service user. | **Sangat Buruk**. Redundansi ekstrem; logic drill-down harus diduplikasi. |
| **DirectLake / DirectQuery Compatibility** | **Native**. Skema terstandarisasi untuk Delta Parquet. | **Tidak Efisien**. Memicu subqueries join kompleks ke storage engine. | **Bagus untuk Simple Aggregations**, buruk untuk slicing kompleks. |

#### Rekomendasi Solusi:
Gunakan **Star Schema** sebagai arsitektur absolut untuk Semantic Model Power BI. Normalisasi Snowflake hanya dapat ditoleransi di tahap data lake staging, tetapi **wajib didenormalisasi** menjadi single dimension sebelum masuk ke VertiPaq tabular model. 

Penggunaan OBT (*One Big Table*) hanya diperbolehkan pada skenario machine learning real-time inference streaming dengan throughput tinggi di mana overhead relational lookup dihindari sepenuhnya.

---

### 9. Best Practices & Standard Industri

1. **Surrogate Key Berbasis Integer:**
   Gunakan tipe data integer (`INT` / `BIGINT`) untuk semua join keys antara tabel fakta dan dimensi. Jangan pernah menggunakan string (`VARCHAR`, GUID/UUID) sebagai kolom relasi karena:
   - Ukuran dictionary integer jauh lebih kecil di VertiPaq.
   - VertiPaq dapat langsung menggunakan algoritma *Primary Key - Foreign Key optimization* yang memetakan row ID tanpa lookup string translation.

2. **Sembunyikan Kolom Kunci (Foreign Keys & Primary Keys):**
   Semua kolom Primary Key pada dimensi dan Foreign Key pada tabel fakta **wajib disembunyikan** (`isHidden = true`) dari antarmuka pelaporan pengguna. Hal ini memaksa business user untuk hanya menggunakan atribut deskriptif dimensi untuk memfilter fakta, menjaga integritas filter context.

3. **Batasi Cardinality String:**
   Pecah kolom datetime menjadi dua kolom terpisah jika disimpan di tingkat fakta: `Date` (sebagai surrogate key integer `YYYYMMDD`) dan `Time` (jika benar-benar dibutuhkan, bulatkan ke tingkat jam/menit terdekat). Mempertahankan timestamp hingga milidetik pada fakta ratusan juta baris akan menghancurkan rasio kompresi VertiPaq.

4. **Hindari Bi-directional Relationships Secara Fisik:**
   Setel seluruh relasi ke arah **Single Direction** secara default. Gunakan DAX `CROSSFILTER(..., Both)` secara modular hanya di dalam measure tertentu yang membutuhkan interaksi slicer lintas fakta, sehingga query standar model tidak menanggung penalti evaluasi relasi dua arah.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertugas merapikan semantic model yang lambat dan menghasilkan angka penjualan yang salah. Masalah disebabkan oleh relasi fisik $N:M$, penggunaan tipe data teks string pada key relasi, dan relasi dua arah yang membingungkan engine. Anda akan membangun Star Schema yang benar dan mengonfigurasi relasi serta measure-nya.

#### Alat yang Diperlukan:
- SQL Server Management Studio (SSMS) atau Fabric / Azure Data Studio.
- Power BI Desktop (Versi terbaru dengan fitur TMDL / DAX Query View).

#### Langkah Eksekusi Terstruktur

##### Langkah 1: Siapkan Struktur Relasi Terisolasi di Database
Jalankan script T-SQL berikut untuk mengompilasi environment sandbox mini:

```sql
CREATE DATABASE PowerBI_Relational_Lab;
GO
USE PowerBI_Relational_Lab;
GO

CREATE TABLE dbo.Staging_Sales (
    OrderNumber NVARCHAR(50),
    OrderDate DATE,
    CustomerEmail NVARCHAR(100),
    ProductName NVARCHAR(100),
    ProductCategory NVARCHAR(50),
    Quantity INT,
    Price DECIMAL(10,2)
);

INSERT INTO dbo.Staging_Sales VALUES
('SO-1001', '2026-03-01', 'budi@corp.com', 'Laptop Pro 15', 'Electronics', 1, 1500.00),
('SO-1002', '2026-03-01', 'ani@corp.com', 'Wireless Mouse', 'Accessories', 2, 25.00),
('SO-1003', '2026-03-02', 'budi@corp.com', 'Mechanical Keyboard', 'Accessories', 1, 100.00),
('SO-1004', '2026-03-03', 'citra@corp.com', 'External Monitor 4K', 'Electronics', 2, 450.00),
('SO-1005', '2026-03-03', 'orphan@corp.com', 'Laptop Pro 15', 'Electronics', 1, 1500.00);
```

##### Langkah 2: ETL Transformasi ke Star Schema Murni
Transformasi data staging flat menjadi bentuk dimensional:

```sql
-- Dimensi Customer
CREATE TABLE dbo.Dim_Customer (
    CustomerKey INT IDENTITY(1,1) PRIMARY KEY,
    CustomerEmail NVARCHAR(100) NOT NULL UNIQUE
);

INSERT INTO dbo.Dim_Customer (CustomerEmail)
SELECT DISTINCT CustomerEmail FROM dbo.Staging_Sales;

-- Dimensi Product
CREATE TABLE dbo.Dim_Product (
    ProductKey INT IDENTITY(1,1) PRIMARY KEY,
    ProductName NVARCHAR(100) NOT NULL UNIQUE,
    ProductCategory NVARCHAR(50) NOT NULL
);

INSERT INTO dbo.Dim_Product (ProductName, ProductCategory)
SELECT DISTINCT ProductName, ProductCategory FROM dbo.Staging_Sales;

-- Tabel Fakta
CREATE TABLE dbo.Fact_Sales (
    SalesOrderID INT IDENTITY(1,1) PRIMARY KEY,
    OrderNumber NVARCHAR(50),
    OrderDateKey INT,
    CustomerKey INT,
    ProductKey INT,
    Quantity INT,
    TotalAmount DECIMAL(12,2)
);

INSERT INTO dbo.Fact_Sales (OrderNumber, OrderDateKey, CustomerKey, ProductKey, Quantity, TotalAmount)
SELECT 
    s.OrderNumber,
    CONVERT(INT, CONVERT(VARCHAR(8), s.OrderDate, 112)) AS OrderDateKey,
    c.CustomerKey,
    p.ProductKey,
    s.Quantity,
    (s.Quantity * s.Price) AS TotalAmount
FROM dbo.Staging_Sales s
JOIN dbo.Dim_Customer c ON s.CustomerEmail = c.CustomerEmail
JOIN dbo.Dim_Product p ON s.ProductName = p.ProductName;
```

##### Langkah 3: Import ke Power BI & Validasi Hubungan Semantik
1. Buka **Power BI Desktop**, pilih **Get Data** -> **SQL Server**, arahkan ke database `PowerBI_Relational_Lab`.
2. Muat tabel `dbo.Dim_Customer`, `dbo.Dim_Product`, dan `dbo.Fact_Sales`.
3. Buka **Model View**:
   - Pastikan relasi dari `Dim_Customer[CustomerKey]` ke `Fact_Sales[CustomerKey]` disetel ke **1 to Many (1:*)**, Cross-filter direction: **Single**.
   - Pastikan relasi dari `Dim_Product[ProductKey]` ke `Fact_Sales[ProductKey]` disetel ke **1 to Many (1:*)**, Cross-filter direction: **Single**.
   - Sembunyikan kolom `CustomerKey` dan `ProductKey` pada tabel `Fact_Sales`.

##### Langkah 4: Tulis dan Evaluasi DAX Verifikasi
Buka tab **DAX Query View** dan jalankan query berikut untuk memverifikasi propagasi filter dan eksekusi expanded table:

```dax
DEFINE
    MEASURE Fact_Sales[Total Revenue] = 
        SUM(Fact_Sales[TotalAmount])
        
    MEASURE Fact_Sales[Transactions Count] = 
        COUNTROWS(Fact_Sales)

EVALUATE
SUMMARIZECOLUMNS(
    Dim_Product[ProductCategory],
    "Revenue", [Total Revenue],
    "Transactions", [Transactions Count]
)
ORDER BY [Revenue] DESC
```

##### Expected Output Verification:
Tabel output wajib menampilkan pembagian hasil yang deterministik:
- `Electronics`: Total Revenue **\$3,400.00**, Transactions **3**
- `Accessories`: Total Revenue **\$150.00**, Transactions **2**

Jika visual matriks menampilkan total baris yang identik di setiap kategori (misal: semua kategori memunculkan $3,550.00), ini menandakan relasi fisik terputus atau foreign key tidak cocok. Verifikasi integritas skema berhasil jika agregasi baris terpecah secara tepat mengikuti irisan kategori produk.