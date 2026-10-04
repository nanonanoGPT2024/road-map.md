# BAB 02: Dimensional Data Modeling (Relational & Semantic)
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis** arsitektur internal mesin VertiPaq (Dictionary Encoding, Run-Length Encoding, Bit-Packing, Value Encoding) untuk memprediksi dan meminimalkan konsumsi RAM serta memaksimalkan throughput CPU L3 Cache.
*   **Merancang** skema dimensional tingkat lanjut (*Star Schema*, *SCD Type 1/2/3/6*, *Role-Playing Dimensions*, *Junk Dimensions*, *Degenerate Dimensions*, dan *Bridge Tables*) yang secara matematis optimal bagi *Semantic Model* Power BI.
*   **Mengeliminasi** ambiguitas relasi dan masalah performa yang disebabkan oleh *Bi-directional Cross-Filtering* dan relasi *Many-to-Many* (*Many-to-Many Relationships*) menggunakan teknik desensitisasi konteks filter berbasis DAX (`USERELATIONSHIP`, `TREATAS`, `CROSSFILTER`).
*   **Mengimplementasikan** pipeline transformasi data berbasis T-SQL dan Power Query (M) yang menghasilkan struktur data berkinerja tinggi sesuai standar *Kimball Enterprise Architecture*.
*   **Mendiagnosis** dan menyelesaikan *bottleneck* performa pemodelan semantik menggunakan DAX Studio dan Tabular Editor (Analisis VertiPaq Analyzer metrics: *Dictionary Size*, *Hierarchy Size*, *Cardinality*).

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib menguasai:
*   Pemahaman mendasar tentang konsep Relational Database Management System (RDBMS), Third Normal Form (3NF), dan Normalisasi vs Denormalisasi.
*   Kemampuan menulis T-SQL tingkat menengah: CTE, Window Functions (`ROW_NUMBER()`, `LEAD()`, `LAG()`), dan sintaks DDL/DML.
*   Pemahaman dasar sintaks DAX: Filter Context, Row Context, calculated columns vs explicit measures, serta kalkulasi agregasi dasar (`SUM`, `CALCULATE`, `FILTER`).
*   Familiaritas dengan Power BI Desktop dan alur kerja Power Query (Mashup Engine).

---

### 3. Concept & Internal Architecture (Mendalam)

Power BI Semantic Model beroperasi di atas mesin analitis *in-memory columnar database* yang disebut **VertiPaq**. Memahami pemodelan dimensional untuk Power BI membutuhkan pemahaman mendalam tentang bagaimana VertiPaq memproses, mengompresi, dan mengeksekusi *query* relasional.

#### 3.1. VertiPaq Engine Storage & Compression Architecture
Tidak seperti RDBMS tradisional yang berbasis baris (*row-oriented storage* seperti Microsoft SQL Server standard rowstore engines), VertiPaq menyimpan data per kolom (*columnar storage*). Setiap kolom disimpan secara terisolasi dan dipartisi menjadi segmen-segmen (*segments* standar terdiri dari 8.388.608 baris per segmen).

```
RDBMS (Row Store):
[Row 1: OrderID, DateKey, CustomerID, Amount]
[Row 2: OrderID, DateKey, CustomerID, Amount]

VertiPaq (Column Store):
Segment 0 (Up to 8M rows):
  - OrderID    : [Value 1, Value 2, ...]
  - DateKey    : [Value 1, Value 2, ...]
  - CustomerID : [Value 1, Value 2, ...]
  - Amount     : [Value 1, Value 2, ...]
```

Saat data dimuat (*data refresh*), VertiPaq melakukan fase kompresi hierarkis dengan urutan algoritma sebagai berikut:

1.  **Value Encoding**:
    Jika suatu kolom numerik memiliki rentang nilai yang dapat direduksi menggunakan selisih dasar (*mathematical transformation*), VertiPaq menghitung nilai minimum ($Min$) dan menyimpan selisihnya:
    $$\text{StoredValue} = \text{ActualValue} - Min$$
    *Contoh*: Rentang nilai `[10001, 10002, 10005]` diubah menjadi basis $Min = 10001$, sehingga data fisik yang disimpan adalah `[0, 1, 4]`. Hal ini secara dramatis memotong jumlah bit yang diperlukan untuk menyimpan setiap integer (*bit-packing*).

2.  **Dictionary (Hash) Encoding**:
    Diterapkan pada kolom teks (string) atau integer berdensitas acak. VertiPaq membangun kamus indeks unik:
    *   String `"Platinum"` $\rightarrow$ ID `0`
    *   String `"Gold"` $\rightarrow$ ID `1`
    *   String `"Silver"` $\rightarrow$ ID `2`
    
    Data pada segmen kolom kemudian digantikan seluruhnya oleh integer ID kamus tersebut. **Implikasi Arsitektural**: Kardinalitas (*distinct values*) menentukan ukuran kamus. Jika sebuah kolom string memiliki kardinalitas 10 juta baris unik (misalnya UUID/GUID), ukuran kamus akan membengkak, memicu *RAM thrashing* dan penurunan drastis pada efisiensi *CPU L3 Cache*.

3.  **Run-Length Encoding (RLE)**:
    Setelah data dikonversi ke ID kamus atau di-*Value Encode*, segmen diurutkan untuk mendeteksi nilai yang berulang berturut-turut. RLE menyimpan entri berupa pasangan: `(Value, Count)`.
    *   Data mentah: `[0, 0, 0, 0, 1, 1, 2]`
    *   RLE: `(0, 4), (1, 2), (2, 1)`
    
    Efisiensi RLE bergantung mutlak pada urutan data (*sort order*). Skema *Star Schema* secara natural mengelompokkan fakta ke dalam kardinalitas dimensi yang konsisten, memungkinkan VertiPaq mencapai rasio kompresi hingga $10\times - 20\times$.

#### 3.2. Relational Semantic Topology: VertiPaq Expanded Tables
Ketika Anda membuat relasi satu-ke-banyak ($1:*$) antara tabel dimensi $Dim$ dan tabel fakta $Fact$, VertiPaq tidak melakukan operasi `JOIN` fisik tradisional saat eksekusi query DAX. Sebaliknya, VertiPaq mengimplementasikan konsep **Expanded Tables**.

*   Tabel fakta secara inheren mencakup seluruh kolom dari tabel dimensi yang terhubung di sepanjang jalur relasi satu-ke-banyak.
*   Jika $DimCustomer$ berelasi ke $FactSales$, secara semantik tabel $FactSales$ diperluas (*expanded*) untuk menyertakan seluruh atribut $DimCustomer$.
*   Filter yang diterapkan pada $DimCustomer$ secara otomatis ada di dalam konteks $FactSales$ tanpa perlu melakukan *merge* data secara runtime.

```
+------------------+         +-------------------------------+
|   DimCustomer    |         |           FactSales           |
+------------------+         +-------------------------------+
| CustomerKey (PK) | <--1--* | SalesOrderNumber              |
| CustomerName     |         | CustomerKey (FK)              |
| Segment          |         | OrderDateKey                  |
+------------------+         | SalesAmount                   |
                             +-------------------------------+
                                            |
                                            v (Semantic Expansion)
                             +-------------------------------+
                             |      Expanded FactSales       |
                             +-------------------------------+
                             | FactSales[SalesOrderNumber]   |
                             | FactSales[CustomerKey]        |
                             | FactSales[OrderDateKey]       |
                             | FactSales[SalesAmount]        |
                             | DimCustomer[CustomerName]     | <--- Available in
                             | DimCustomer[Segment]          | <--- Table Context
                             +-------------------------------+
```

**Bi-directional Relationships Hazard**: Mengaktifkan relasi dua arah (*cross-filtering direction = Both*) memaksa mesin VertiPaq memperluas kedua tabel secara timbal balik. Hal ini tidak hanya melipatgandakan ukuran topologi relasi dalam memori, tetapi juga memicu risiko ketidakpastian jalur (*ambiguity path*), *circular dependencies*, dan degradasi eksponensial pada kalkulasi matriks DAX yang kompleks (*context transition*).

---

### 4. Why & What

#### Mengapa Star Schema, Bukan Normalized 3NF atau Flat Denormalized Single Table?
*   **Kegagalan 3NF (Snowflake ekstrem) di Tabular Engine**: RDBMS transaksional (OLTP) memecah tabel menjadi bentuk 3NF untuk menghindari anomali penulisan (*write anomalies*). Namun, pada sistem analisis analitik (OLAP/VertiPaq), setiap tingkat normalisasi tambahan (*Snowflaking*: Faktur $\rightarrow$ DimProduk $\rightarrow$ DimSubKategori $\rightarrow$ DimKategori) memaksa mesin DAX melintasi beberapa lompatan relasi pointer (*relationship traversal hops*). Ini menghambat vektorisasi SIMD pada CPU dan meningkatkan latensi query DAX.
*   **Kegagalan Flat Table Tunggal (One Big Table / OBT)**: Meskipun OBT bekerja cepat pada mesin berbasis scan murni tanpa relasi seperti ClickHouse atau Google BigQuery, di Power BI OBT menghasilkan duplikasi atribut dimensi bernilai string jutaan kali. Ini menyebabkan *dictionary size* membengkak secara masif, mematikan optimasi filter skalar, serta merusak hierarki navigasi visualisasi analitik bagi end-user.
*   **Keunggulan Star Schema**: Star Schema menyeimbangkan ukuran kamus dan kecepatan agregasi. Tabel dimensi berisi nilai unik (*cardinality control*), sedangkan tabel fakta hanya menyimpan foreign key numerik kompak dan metrik pengukuran (*measures*), yang memaksimalkan efisiensi kompresi RLE dan *Value Encoding*.

---

### 5. How (Workflow Detail)

Alur kerja rekayasa model dimensional enterprise mencakup lima fase berurutan:

```
[Phase 1: Source System] (OLTP / Data Lakehouse)
         |
         v
[Phase 2: Data Cleansing & Surrogacy] (T-SQL Pipeline / Staging Views)
  - Generate Integer Surrogate Keys (HASHBYTES / IDENTITY)
  - Handle Early Arriving Facts & Null FKs
  - Resolve SCD Type 2 Timelines (ValidFrom, ValidTo, IsCurrent)
         |
         v
[Phase 3: Semantic Data Layer Preparation] (Power Query / Direct Lake)
  - Strip Out Unused High-Cardinality Columns
  - Enforce Proper Native Data Types
  - Disable Query Load for Intermediate Transformations
         |
         v
[Phase 4: Tabular Object Relational Modeling] (Power BI Desktop / Tabular Editor)
  - Build Star Schema (Strict 1:* Single-Direction Relationships)
  - Configure Role-Playing Dimensions (Inactive Relationships)
  - Isolate Degenerate & Junk Dimensions
         |
         v
[Phase 5: Performance Validation & Optimization] (DAX Studio & VertiPaq Analyzer)
  - Audit Cardinality vs Dictionary Memory
  - Benchmark Measure SE (Storage Engine) vs FE (Formula Engine) Query Times
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Modern vs Gudang Terbuka
Bayangkan Anda mengelola katalog perpustakaan global dengan 10 juta buku:
*   **Flat Table (OBT)**: Setiap kali buku dicatat, nama lengkap pengarang, riwayat hidupnya, institusi penerbit, dan alamat lengkap penerbit ditulis ulang secara manual di sampul buku. Anda kehabisan kertas, lemari menjadi luar biasa tebal, dan sulit mencari semua buku dari pengarang yang sama jika ada sedikit variasi penulisan.
*   **Snowflake Schema**: Anda memisahkan buku ke lemari A, pengarang ke lemari B, kota lahir pengarang ke lemari C, kode pos kota ke lemari D, dan negara kode pos ke lemari E. Saat pembaca bertanya "Tampilkan penjualan buku untuk negara Indonesia", Anda harus berlari melintasi 5 lemari untuk menyatukan benang informasi.
*   **Star Schema**: Buku (Fakta) diletakkan di tengah dengan label nomor ID pendek. Pengarang (Dimensi) berada di lemari satelit yang mengelilinginya, lengkap dengan seluruh atribut relevannya tanpa dipecah-pecah lagi. Satu lompatan langsung memberikan jawaban instan.

#### Arsitektur Star Schema Tingkat Enterprise
```
                       +-----------------------+
                       |    DimDate (Role)     |
                       |  (ShipDate / Inactive)|
                       +-----------------------+
                       | PK DateKey (int)      |
                       | FullDateAlternateKey  |
                       | Year, Quarter, Month  |
                       +-----------------------+
                                  |
                                  | 0..1 (Inactive: USERELATIONSHIP)
                                  v
+------------------+   * +-----------------------+ *   +--------------------+
|   DimCustomer    |---->|       FactSales       |<----|     DimProduct     |
+------------------+ 1   +-----------------------+   1 +--------------------+
| PK CustomerSK    |     | PK/FK SalesOrderNo(DG)|     | PK ProductSK       |
| BK CustomerID    |     | FK CustomerSK         |     | BK ProductID       |
| Name, Segment    |     | FK ProductSK          |     | ProductName        |
| SCD2 ValidFrom   |     | FK OrderDateKey       |     | Subcategory        |
| SCD2 ValidTo     |     | FK ShipDateKey        |     | Category           |
| SCD2 IsCurrent   |     | FK SalesTerritorySK   |     | StandardCost       |
+------------------+     | FK SalesJunkSK        |     +--------------------+
                         | OrderQuantity         |
                         | SalesAmount           |
                         +-----------------------+
                               |           |
             1..* (Active)     |           | 1..* (Active)
      +------------------------+           +------------------+
      v                                                       v
+-----------------------+                           +-------------------+
|  DimDate (OrderDate)  |                           |   DimSalesJunk    |
+-----------------------+                           +-------------------+
| PK DateKey (int)      |                           | PK SalesJunkSK    |
| CalendarHierarchy     |                           | OrderStatus       |
+-----------------------+                           | PaymentMethod     |
                                                    | DeliveryType      |
                                                    +-------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Inactive Relationship Handling via DAX
Sering kali tabel fakta memiliki beberapa tanggal (misalnya `OrderDateKey` dan `ShipDateKey`). Jangan membuat dua salinan fisik tabel kalender jika tidak mutlak diperlukan (*unnecessary memory allocation*). Gunakan *Role-Playing Dimension* dengan relasi tidak aktif (*inactive relationship*).

```dax
-- Definisi Kalkulasi Standar (Menggunakan Active Relationship: OrderDateKey)
Total Sales := 
SUM ( FactSales[SalesAmount] )

-- Mengalihkan Filter Context ke ShipDateKey (Inactive Relationship)
Total Sales Shipped := 
CALCULATE (
    [Total Sales],
    USERELATIONSHIP ( FactSales[ShipDateKey], DimDate[DateKey] )
)
```

#### 7.2. Practical Example: Enterprise T-SQL Pipeline & DAX Bridge Table Resolution

##### Step 1: Ekstraksi & Desain Dimensi Junk pada Data Warehouse (T-SQL)
Junk dimension menyatukan flag dan indikator biner/kardinalitas rendah untuk mencegah polusi kolom pada tabel fakta.

```sql
-- DDL & ETL: Pembuatan Dimensi Junk untuk Transaksi Finansial
CREATE TABLE dbo.DimTransactionFlags (
    TransactionFlagsSK INT IDENTITY(1,1) NOT NULL,
    PaymentStatus NVARCHAR(20) NOT NULL,
    AuthorizationChannel NVARCHAR(20) NOT NULL,
    IsFraudulent BIT NOT NULL,
    CONSTRAINT PK_DimTransactionFlags PRIMARY KEY CLUSTERED (TransactionFlagsSK)
);

-- Pengisian Nilai Cartesian Komprehensif
INSERT INTO dbo.DimTransactionFlags (PaymentStatus, AuthorizationChannel, IsFraudulent)
SELECT DISTINCT 
    ISNULL(src.PaymentStatus, 'UNKNOWN'),
    ISNULL(src.AuthorizationChannel, 'UNKNOWN'),
    ISNULL(src.IsFraudulent, 0)
FROM stg.SourceTransactions src;

-- Indeks optimasi pemuatan pipeline
CREATE NONCLUSTERED INDEX IX_DimTransactionFlags_Lookup 
ON dbo.DimTransactionFlags (PaymentStatus, AuthorizationChannel, IsFraudulent);
```

##### Step 2: Implementasi Resolusi Relasi Many-to-Many Tanpa Bi-Directional (DAX)
Kasus: Seorang nasabah (*Customer*) dapat memiliki banyak rekening (*Account*), dan satu rekening bersama dapat dimiliki oleh banyak nasabah (*Joint Account*).

```
+---------------+       +-----------------------+       +-------------------+
|  DimCustomer  | 1   * | BridgeCustomerAccount | *   1 |    DimAccount     |
+---------------+------>+-----------------------+<------+-------------------+
| CustomerSK    |       | CustomerSK            |       | AccountSK         |
+---------------+       | AccountSK             |       +-------------------+
                        +-----------------------+                 | 1
                                                                  |
                                                                  | *
                                                        +-------------------+
                                                        |    FactBalance    |
                                                        +-------------------+
                                                        | AccountSK         |
                                                        | BalanceAmount     |
                                                        +-------------------+
```

Pendekatan Tradisional (Keliru): Menyalakan *bi-directional cross-filtering* pada `BridgeCustomerAccount` $\leftrightarrow$ `DimAccount`. Hal ini merusak skala performa model.

Pendekatan Arsitektur Enterprise: Biarkan semua relasi berarah tunggal (*Single Direction*), injeksikan propagasi konteks filter secara eksplisit menggunakan DAX Pattern:

```dax
-- Metrik Saldo Finansial dengan Resolusi Many-to-Many Dinamis
Customer Propagated Balance := 
CALCULATE (
    SUM ( FactBalance[BalanceAmount] ),
    TREATAS (
        CALCULATETABLE (
            VALUES ( BridgeCustomerAccount[AccountSK] ),
            -- Baris berikut menangkap CustomerSK yang sedang aktif pada Visual Context
            SUMMARIZE ( DimCustomer, DimCustomer[CustomerSK] )
        ),
        FactBalance[AccountSK]
    )
)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah korporasi logistik global memproses lebih dari 450 juta data pengiriman per tahun. Model semantik Power BI mereka saat ini berukuran **18 GB di RAM**, memakan waktu refresh lebih dari 3 jam, dan performa visual report mengalami degradasi berat (*render time* rata-rata 14 detik per klik).

#### Analisis Diagnostik (Audit Tabular Editor & VertiPaq Analyzer)
1.  **Ditemukan Snowflake Chains**: Skema memiliki rantai: `FactShipment` $\rightarrow$ `DimDepot` $\rightarrow$ `DimCity` $\rightarrow$ `DimCountry` $\rightarrow$ `DimRegion`.
2.  **High-Cardinality Degenerate Key**: Kolom `TrackingNumber` (string acak, 450 juta baris unik) disimpan langsung di dalam tabel fakta.
3.  **Tipe Data Tidak Tepat**: Nilai moneter `FreightCharge` bertipe data `Decimal(18, 4)` yang dimuat ke Power BI sebagai floating point float (8 byte, kardinalitas ekstrem) alih-alih `Fixed Decimal Currency`.
4.  **SCD Type 2 Desynchronization**: Tabel dimensi armada (*Fleet*) memiliki riwayat perubahan status armada yang menggunakan string tanggal tanpa integer surrogate, mengakibatkan join non-integer.

#### Solusi Arsitektural (Refactoring)
1.  **Denormalisasi Snowflake menjadi Pure Star**: Menggabungkan `DimCity`, `DimCountry`, dan `DimRegion` langsung ke dalam `DimDepot` melalui layer SQL View. Hasil: Mengeliminasi 3 lompatan relasional.
2.  **Pemisahan Degenerate Dimension**: Mengekstrak `TrackingNumber` keluar dari semantic import model. Menggantinya dengan deep linking URL dinamis berbasis parameter DirectQuery jika pengguna membutuhkan audit audit-trail tingkat granularitas atomik.
3.  **Encoding Optimization**: Mengubah `FreightCharge` menjadi tipe data `Fixed Decimal Number` (Currency) di Power Query. Ini memaksa VertiPaq menggunakan integer-scale value encoding 4-desimal tetap, memotong konsumsi memori hingga 75%.
4.  **SCD Type 2 Timeline Alignment**: Menambahkan Integer Surrogate Key (`FleetSK`) yang di-generate via hashing kombinasi `BusinessKey + ValidFromDate`.

#### Hasil Arsitektur Baru
*   **Ukuran Memori Model**: Turun dari 18 GB menjadi **2.1 GB** (Kompresi $\approx 88\%$).
*   **Waktu Refresh Dataset**: Berkurang dari 180 menit menjadi **14 menit**.
*   **Visual Render Latency**: Berkurang dari 14 detik menjadi **450 milidetik** (95th percentile).

---

### 9. Trade-offs

| Parameter Arsitektur | Flat Table (OBT - One Big Table) | Pure Star Schema | Over-Normalized (Snowflake) |
| :--- | :--- | :--- | :--- |
| **VertiPaq Memory Footprint** | Sangat Buruk (Kamus string membengkak akibat duplikasi baris). | **Sangat Baik** (Kamus terpusat pada tabel dimensi ringkas). | Buruk-Sedang (Banyak relasi pointer & overhead metadata internal). |
| **Kecepatan Query DAX** | Cepat untuk scan tunggal; Lambat untuk agregasi hirarki kompleks. | **Maksimal** (Vektorisasi SIMD efisien via Expanded Tables). | Lambat (Penelusuran relasi multi-hop membebani Formula Engine). |
| **Kompleksitas ETL Pipeline** | Sederhana (Hanya denormalisasi flat view tunggal). | Terukur (Membutuhkan manajemen Dimensi, Fakta, & Surrogate Keys). | Sangat Rumit (Banyak relasi foreign key berantai bertingkat). |
| **Fleksibilitas Semantic DAX** | Kaku (Sulit menangani multi-fact, multi-granularity, role-playing). | **Sangat Fleksibel** (Mendukung pola DAX modern tingkat lanjut). | Fleksibel secara teori, rapuh secara komputasi engine. |
| **Biaya Pemeliharaan Schema** | Tinggi (Perubahan atribut memaksa re-ingestion ratusan juta baris). | **Rendah** (Perubahan atribut terisolasi pada dimensi terkait). | Sangat Tinggi (Cascading updates pada banyak level normalisasi). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal 1: Menggunakan Nilai String UUID/GUID sebagai Kunci Relasi
*   *Symptom*: File `.pbix` sangat besar, penggunaan memori dataset melesat saat refresh, join lambat.
*   *Root Cause*: GUID (misal: `4a2e4b30-7c22-4a97-9e0c-d4cf36102be8`) memiliki kardinalitas 100% unik. Kamus VertiPaq tidak dapat mengompresi string acak ini, dan Run-Length Encoding gagal total.
*   *Mitigasi*: Generate Integer Surrogate Key menggunakan fungsi `DENSE_RANK()`, `IDENTITY()`, atau hash 64-bit integer di data warehouse sebelum data ditarik ke Power BI.

#### Kesalahan Fatal 2: Mengaktifkan Bi-Directional Cross-Filtering Secara Global
*   *Symptom*: Angka metrik bergeser tak terduga (*context bleeding*), muncul error circular reference, performa slicer anjlok.
*   *Root Cause*: Pola filter timbal balik mengubah relasi $1:*$ menjadi jalur ambivalen yang ambigu bagi *Formula Engine*.
*   *Mitigasi*: Set seluruh relasi menjadi **Single Direction**. Jika filter interaktif antar dimensi diperlukan, selesaikan melalui ekspresi DAX spesifik menggunakan `CROSSFILTER(..., BOTH)` atau kalkulasi berbasis `TREATAS`.

#### Kesalahan Fatal 3: Membiarkan Nilai NULL pada Foreign Key Tabel Fakta
*   *Symptom*: Muncul baris kosong misterius (*blank row*) pada setiap visualisasi tabel/matriks yang menggunakan dimensi.
*   *Root Cause*: Integritas referensial tabular engine menemukan nilai foreign key di tabel fakta yang tidak memiliki pasangan di tabel dimensi. Mesin terpaksa membuat baris *Blank surrogate* internal untuk menampung fakta yatim (*orphan rows*).
*   *Mitigasi*: Tangani di SQL/Power Query:
    ```sql
    COALESCE(FactSource.CustomerKey, -1) AS CustomerKey
    ```
    Dan pastikan pada `DimCustomer` terdapat baris fallback:
    `CustomerKey = -1`, `CustomerName = 'Unknown / Unassigned'`.

---

### 11. Best Practices (Production Checklist)

* [ ] **Aturan Surrogate Key**: Pastikan seluruh foreign key dan primary key relasi bertipe data `Whole Number (Int64)`. Jangan pernah merelasikan tabel menggunakan string, float, atau datetime.
* [ ] **Hidden Keys Policy**: Sembunyikan (*Hide in Report View*) seluruh kolom Foreign Key di tabel fakta dan Primary Key di tabel dimensi. User hanya boleh mengekspos atribut deskriptif dimensi dan eksplisit measure.
* [ ] **Cardinality Slicing**: Hapus kolom non-analitis seperti timestamp presisi tinggi (`HH:mm:ss.fff`). Pisahkan menjadi dua kolom terpisah: `DateKey` (Integer) dan `TimeKey` (Integer menit dalam sehari: 0 - 1439).
* [ ] **Role-Playing Strategy**: Implementasikan satu dimensi kalender utama (`DimDate`) dan gunakan `USERELATIONSHIP` untuk tanggal alternatif daripada membuat duplikasi fisik tabel kalender berulang-ulang.
* [ ] **SCD Type 2 Modeling**: Sediakan kolom penanda masa berlaku integer atau biner: `DateFromKey`, `DateToKey`, dan `IsCurrentRow (1/0)`.
* [ ] **No Snowflaking Policy**: Gabungkan tabel subkategori, kategori, region, dan level hierarki deskriptif lainnya ke dalam dimensi master induknya.
* [ ] **Zero-Null Enforcement**: Pastikan seluruh kolom relasional di tabel fakta terbebas dari `NULL` dengan menggunakan nilai fallback default (misal `-1`).

---

### 12. Hands-on Practice

Buat skrip pengujian pemodelan dimensional berikut di lingkungan lab lokal Anda. Direktori kerja target: `hands-on/m02/`.

#### Langkah 1: Script DDL & Mock Data Pipeline (File: `hands-on/m02/setup_dw.sql`)
Jalankan skrip berikut di database Microsoft SQL Server atau Azure SQL Database untuk membangun *star schema* simulasi performa:

```sql
-- Buat Skema Simulasi
CREATE SCHEMA dw;
GO

-- 1. Dimensi Pelanggan (SCD Type 2)
CREATE TABLE dw.DimCustomer (
    CustomerSK INT IDENTITY(1,1) NOT NULL,
    CustomerBK INT NOT NULL,
    CustomerName NVARCHAR(100) NOT NULL,
    CustomerTier NVARCHAR(20) NOT NULL,
    ValidFromDate DATE NOT NULL,
    ValidToDate DATE NOT NULL,
    IsCurrent BIT NOT NULL,
    CONSTRAINT PK_DimCustomer PRIMARY KEY CLUSTERED (CustomerSK)
);

-- 2. Dimensi Tanggal Terpadu
CREATE TABLE dw.DimDate (
    DateKey INT NOT NULL,
    FullDate DATE NOT NULL,
    CalendarYear INT NOT NULL,
    MonthNumberOfYear INT NOT NULL,
    MonthName NVARCHAR(20) NOT NULL,
    CONSTRAINT PK_DimDate PRIMARY KEY CLUSTERED (DateKey)
);

-- 3. Dimensi Junk
CREATE TABLE dw.DimSalesJunk (
    SalesJunkSK INT IDENTITY(1,1) NOT NULL,
    Channel NVARCHAR(20) NOT NULL,
    PromotionApplied NVARCHAR(10) NOT NULL,
    CONSTRAINT PK_DimSalesJunk PRIMARY KEY CLUSTERED (SalesJunkSK)
);

-- 4. Tabel Fakta Penjualan
CREATE TABLE dw.FactSales (
    SalesOrderLineNumber INT NOT NULL,
    CustomerSK INT NOT NULL,
    OrderDateKey INT NOT NULL,
    DeliveryDateKey INT NOT NULL,
    SalesJunkSK INT NOT NULL,
    OrderQuantity INT NOT NULL,
    SalesAmount DECIMAL(18,4) NOT NULL,
    CONSTRAINT PK_FactSales PRIMARY KEY CLUSTERED (SalesOrderLineNumber, OrderDateKey)
);

-- Injeksi Mock Data
INSERT INTO dw.DimCustomer (CustomerBK, CustomerName, CustomerTier, ValidFromDate, ValidToDate, IsCurrent)
VALUES 
(101, 'PT Alpha Teknologi', 'Tier 1', '2023-01-01', '2023-06-30', 0),
(101, 'PT Alpha Teknologi Global', 'Tier 1 Prime', '2023-07-01', '9999-12-31', 1),
(102, 'CV Maju Digital', 'Tier 2', '2023-01-01', '9999-12-31', 1);

INSERT INTO dw.DimDate (DateKey, FullDate, CalendarYear, MonthNumberOfYear, MonthName)
VALUES 
(20230615, '2023-06-15', 2023, 6, 'June'),
(20230620, '2023-06-20', 2023, 6, 'June'),
(20230710, '2023-07-10', 2023, 7, 'July'),
(20230715, '2023-07-15', 2023, 7, 'July');

INSERT INTO dw.DimSalesJunk (Channel, PromotionApplied)
VALUES 
('Online', 'PROMOA'),
('Enterprise Direct', 'NONE');

INSERT INTO dw.FactSales (SalesOrderLineNumber, CustomerSK, OrderDateKey, DeliveryDateKey, SalesJunkSK, OrderQuantity, SalesAmount)
VALUES 
(1001, 1, 20230615, 20230620, 1, 5, 25000000.0000),
(1002, 2, 20230710, 20230715, 2, 10, 75000000.0000);
```

#### Langkah 2: Query M Power Query Pemodelan Semantik (File: `hands-on/m02/PowerQuery_M_Script.m`)
Gunakan skrip Power Query M berikut pada *Advanced Editor* Power BI Desktop untuk memuat dan mengunci tipe data skema:

```powerquery
// Let Expression for Loading FactSales with strict native data types
let
    Source = Sql.Database("localhost", "YourDatabaseName"),
    dw_FactSales = Source{[Schema="dw",Item="FactSales"]}[Data],
    TransformedTypes = Table.TransformColumnTypes(dw_FactSales,{
        {"SalesOrderLineNumber", Int64.Type},
        {"CustomerSK", Int64.Type},
        {"OrderDateKey", Int64.Type},
        {"DeliveryDateKey", Int64.Type},
        {"SalesJunkSK", Int64.Type},
        {"OrderQuantity", Int64.Type},
        {"SalesAmount", Currency.Type} // Fixed Decimal untuk VertiPaq Value Encoding Optimization
    })
in
    TransformedTypes
```

#### Langkah 3: Skrip Pengaturan Model DAX & Ukuran (File: `hands-on/m02/ModelMeasures.dax`)
Definisikan relasi:
*   `dw.FactSales[CustomerSK]` $\rightarrow$ `dw.DimCustomer[CustomerSK]` (Active, 1 to Many)
*   `dw.FactSales[OrderDateKey]` $\rightarrow$ `dw.DimDate[DateKey]` (Active, 1 to Many)
*   `dw.FactSales[DeliveryDateKey]` $\rightarrow$ `dw.DimDate[DateKey]` (Inactive, 1 to Many)
*   `dw.FactSales[SalesJunkSK]` $\rightarrow$ `dw.DimSalesJunk[SalesJunkSK]` (Active, 1 to Many)

Lalu buat *Model Measures*:

```dax
-- Metrik Dasar Menggunakan Active OrderDate
Total Revenue Ordered := 
SUM ( FactSales[SalesAmount] )

-- Metrik Lanjutan Menggunakan Role-Playing DeliveryDate
Total Revenue Delivered := 
CALCULATE (
    [Total Revenue Ordered],
    USERELATIONSHIP ( FactSales[DeliveryDateKey], DimDate[DateKey] )
)

-- Analisis Kepatuhan SLA: Penjualan yang terkirim di bulan yang sama dengan pemesanan
Revenue Delivered Same Month := 
CALCULATE (
    [Total Revenue Delivered],
    FILTER (
        VALUES ( DimDate[MonthNumberOfYear] ),
        DimDate[MonthNumberOfYear] = CALCULATE ( MAX ( DimDate[MonthNumberOfYear] ) )
    )
)
```

---

### 13. Exercise

#### Level Easy
Ubah skema Snowflake berikut menjadi Star Schema:
*   Struktur Asal: `FactInventory` berelasi ke `DimWarehouse`, `DimWarehouse` berelasi ke `DimPostalCode`, `DimPostalCode` berelasi ke `DimCountry`.
*   *Tugas*: Tulis skrip SQL View untuk menghasilkan entitas tunggal terdenormalisasi bernama `DimWarehouseExpanded` yang siap disambungkan langsung ke `FactInventory` dengan relasi $1:*$.

#### Level Medium
Sebuah tabel fakta transaksi keuangan memiliki kolom `PaymentStatusFlag` (`'PAID'`, `'PENDING'`, `'REJECTED'`), `IsInternational` (`0`, `1`), dan `ApprovalType` (`'MANUAL'`, `'AUTO'`). Saat ini ketiga atribut tersebut berada di tabel fakta yang berukuran 50 juta baris.
*   *Tugas*: Rancang struktur skema *Junk Dimension* (`DimTransactionJunk`), sertakan perhitungan berapa total kombinasi unik (kardinalitas) yang dimungkinkan, dan tunjukkan transformasi mapping foreign key-nya ke tabel fakta.

#### Level Hard
Sebuah perusahaan asuransi memiliki entitas polis di mana klaim dapat diajukan bertahun-tahun setelah polis aktif. Anda diwajibkan menghitung rasio klaim historis terhadap kondisi polis pada saat kejadian klaim terjadi (*Loss Date*), bukan pada saat klaim dilaporkan (*Reported Date*) maupun status terkini polis. Dimensi polis dikelola menggunakan **SCD Type 2**.
*   *Tugas*: Rancang relasi pemodelan dimensional dan tulis ekspresi DAX murni tanpa memicu looping dependensi konteks untuk mencocokkan fakta kejadian klaim terhadap baris SCD Type 2 yang valid saat tanggal kejadian perkara terjadi (`FactClaim[IncidentDate] BETWEEN DimPolicy[ValidFrom] AND DimPolicy[ValidTo]`).

---

### 14. Challenge

#### Skenario Kompleks: Healthcare Clinical Analytics & Dynamic Provider Hierarchies
Sebuah jaringan rumah sakit nasional mengelola 80 juta rekam medis kunjungan pasien (*FactEncounters*). 

**Kondisi Lapangan**:
1.  **Multi-Dimensional Attributions**: Setiap kunjungan memiliki:
    *   Dokter Penanggung Jawab Pasien (*Attending Physician*).
    *   Dokter yang Merujuk (*Referring Physician*).
    *   Dokter Bedah Utama (*Operating Physician*).
    Seluruh dokter ini bermuara pada satu master data dokter (`DimPhysician`), tetapi satu kunjungan bisa saja melibatkan hingga 5 dokter asisten (*Co-Surgeons*) tambahan dengan peran yang fleksibel.
2.  **Parent-Child Dynamic Hierarchy**: Dokter terikat pada departemen medis yang memiliki hierarki organisasi dinamis hingga 7 kedalaman (*Sub-specialty* $\rightarrow$ *Specialty* $\rightarrow$ *Department* $\rightarrow$ *Division* $\rightarrow$ *Facility* $\rightarrow$ *Regional Network* $\rightarrow$ *Corporate*). Struktur hierarki ini berubah sewaktu-waktu akibat restrukturisasi operasional internal.
3.  **Performance Constraint**: Power BI Premium Capacity dibatasi maksimal RAM 10 GB. Visual matriks dokter harus mampu menampilkan total biaya klaim agregat per departemen dalam waktu sub-detik (< 1 detik).

**Target Arsitektur**:
Rancang arsitektur dimensional menyeluruh yang meliputi:
*   Desain fisik tabel (Fakta, Dimensi Peran, Bridge Table, dan Flattened Hierarchies).
*   Strategi pemodelan Parent-Child menggunakan DAX `PATH` dan `PATHITEM` di ETL/Power Query untuk menghindari relasi rekursif dinamis yang mematikan *Formula Engine*.
*   Resolusi Many-to-Many untuk dokter pendamping tanpa mengaktifkan relasi dua arah (*Bi-directional cross filter*).
*   Justifikasi teknis terhadap alokasi memori VertiPaq berdasarkan estimasi kardinalitas kolom.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (1 - 5)
1.  **Mengapa VertiPaq bekerja jauh lebih efisien pada skema Star dibandingkan skema Snowflake yang dinormalisasi penuh?**
    *   *A.* Karena Star Schema memiliki lebih banyak foreign key di tabel dimensi.
    *   *B.* Karena Star Schema mengurangi jumlah lompatan relasional antartabel, memaksimalkan kompresi berbasis kolom dan mempermudah resolusi Expanded Table.
    *   *C.* Karena Snowflake Schema tidak didukung oleh Power BI Mashup Engine.
    *   *D.* Karena VertiPaq menyimpan data dalam format rowstore B-Tree index.
2.  **Algoritma encoding VertiPaq apa yang pertama kali dievaluasi pada kolom bertipe data numerik integer?**
    *   *A.* Huffman Encoding
    *   *B.* Run-Length Encoding (RLE)
    *   *C.* Value Encoding
    *   *D.* LZW Dictionary Compression
3.  **Apa karakteristik pembeda utama dari Degenerate Dimension?**
    *   *A.* Dimensi yang memiliki validitas waktu seperti SCD Type 2.
    *   *B.* Atribut dimensi yang disimpan langsung di tabel fakta tanpa tabel dimensi terpisah (misalnya Nomor Invoice/Surat Jalan).
    *   *C.* Dimensi yang menghubungkan dua tabel fakta secara bersamaan.
    *   *D.* Dimensi yang berisi kombinasi flag dan status operasional.
4.  **Tipe data apa di Power BI Desktop yang secara default dialokasikan sebagai 4-decimal integer scaled fixed currency di mesin VertiPaq?**
    *   *A.* Decimal Number (Floating Point)
    *   *B.* Fixed Decimal Number (Currency)
    *   *C.* Whole Number
    *   *D.* Text
5.  **Kapan Anda harus menggunakan fungsi DAX `USERELATIONSHIP`?**
    *   *A.* Ketika membuat relasi Many-to-Many dinamis antar dua tabel fakta.
    *   *B.* Untuk mengaktifkan relasi non-aktif (*inactive relationship*) yang sudah didefinisikan di semantic model selama durasi evaluasi ekspresi `CALCULATE`.
    *   *C.* Untuk memaksa relasi satu arah menjadi dua arah secara permanen di model.
    *   *D.* Untuk merelasikan dua tabel yang tidak memiliki foreign key yang cocok.

#### Soal Intermediate (6 - 10)
6.  **Apa bahaya arsitektural utama dari mengaktifkan opsi "Cross-filtering: Both" pada relasi satu-ke-banyak?**
    *   *A.* VertiPaq tidak bisa melakukan refresh data terjadwal.
    *   *B.* Terjadi ambiguitas konteks filter, peningkatan konsumsi memori akibat ekspansi relasi multi-arah, dan risiko hasil kalkulasi DAX yang keliru (*context leakage*).
    *   *C.* Power Query otomatis menonaktifkan query folding pada data source SQL.
    *   *D.* DAX Studio menolak melakukan trace koneksi DirectQuery.
7.  **Bagaimana penanganan integritas referensial yang paling benar saat menemukan nilai NULL pada kolom Foreign Key di tabel fakta?**
    *   *A.* Biarkan NULL agar VertiPaq otomatis menghapus baris tersebut.
    *   *B.* Ganti nilai NULL dengan angka default `-1` di data staging dan sediakan baris penampung `'Unknown'` di tabel dimensi terkait.
    *   *C.* Ubah tipe data foreign key menjadi string kosong `""`.
    *   *D.* Nyalakan relasi Many-to-Many pada tabel model.
8.  **Apa dampak kardinalitas kolom (*Column Cardinality*) terhadap Dictionary Encoding VertiPaq?**
    *   *A.* Kardinalitas tidak mempengaruhi ukuran dictionary, hanya mempengaruhi ukuran RLE.
    *   *B.* Semakin tinggi kardinalitas (jumlah nilai unik), semakin besar memori yang dialokasikan untuk Dictionary, dan bit-packing per baris menjadi semakin tidak efisien.
    *   *C.* VertiPaq otomatis menghapus kolom jika kardinalitasnya melebihi 1 juta baris unik.
    *   *D.* Nilai unik yang tinggi akan otomatis diubah menjadi format biner terenkripsi.
9.  **Pada skenario Slowly Changing Dimension (SCD) Type 2, bagaimana cara terbaik menghubungkan fakta transaksi historis ke dimensi pelanggan jika pelaporan menuntut pelaporan status pelanggan saat transaksi itu terjadi?**
    *   *A.* Relasikan Business Key (`CustomerBK`) langsung ke fakta menggunakan relasi bi-directional.
    *   *B.* Relasikan Surrogate Key (`CustomerSK`) unik per versi record dimensi ke foreign key `CustomerSK` yang dicocokkan di pipeline ETL saat fakta terjadi.
    *   *C.* Gunakan SCD Type 1 untuk menimpa seluruh baris pelanggan lama.
    *   *D.* Pisahkan pelanggan lama dan baru ke dua dataset Power BI yang berbeda.
10. **Perhatikan fungsi DAX berikut:**
    ```dax
    MeasureX := CALCULATE(SUM(FactSales[Amount]), TREATAS(VALUES(DimA[ID]), FactB[ID]))
    ```
    **Apa fungsi sebenarnya dari `TREATAS` dalam pemodelan data tingkat lanjut?**
    *   *A.* Mengubah tipe data kolom `DimA[ID]` menjadi sama dengan `FactB[ID]`.
    *   *B.* Menyuntikkan konteks filter dari sekumpulan nilai (*table expression*) ke kolom target tanpa memerlukan relasi fisik aktif di model tabular.
    *   *C.* Menghapus seluruh filter context yang berasal dari `DimA`.
    *   *D.* Menghitung rata-rata bergerak antar dua tabel secara otomatis.

#### Skenario Kasus Produksi (11 - 13)
11. **Skenario Kasus 1**:
    Sebuah model data retail enterprise memiliki tabel fakta transaksi kasir berukuran 100 juta baris. Terdapat kolom `TransactionTimestamp` dengan format `YYYY-MM-DD HH:mm:ss.fff`. VertiPaq Analyzer menunjukkan bahwa kolom ini mengonsumsi **62% dari total memori RAM model**.
    *Tindakan arsitektural mana yang paling tepat dan memberikan dampak optimalisasi performa tertinggi tanpa menghilangkan nilai analitis bisnis?*
    *   *A.* Kompres kolom tersebut menggunakan DAX Calculated Column bertipe teks.
    *   *B.* Pisahkan kolom tersebut di data pipeline menjadi dua: `DateKey` (Integer `YYYYMMDD`) yang berelasi ke `DimDate`, dan `TimeKey` (Integer `0 - 86399` untuk level detik atau `0 - 1439` untuk level menit) yang berelasi ke `DimTime`.
    *   *C.* Ubah tipe data kolom tersebut menjadi teks murni agar VertiPaq mengompresnya dengan Dictionary Encoding.
    *   *D.* Aktifkan DirectQuery khusus untuk tabel transaksi kasir tersebut.
12. **Skenario Kasus 2**:
    Laporan kinerja keuangan Anda mendadak lambat setelah Anda menambahkan tabel bridging untuk memetakan hierarki multi-manajer ke akun portofolio. Trace di DAX Studio menunjukkan metrik *Formula Engine (FE) CPU Time* mencapai 85% dari total waktu eksekusi.
    *Apa diagnosis teknis paling logis atas masalah ini?*
    *   *A.* VertiPaq Storage Engine bekerja terlalu cepat sehingga Formula Engine tidak dapat mengimbanginya.
    *   *B.* Keberadaan relasi many-to-many fisik dengan cross-filtering aktif memaksa Formula Engine mengeksekusi transisi konteks baris-per-baris (*interleaved execution*) alih-alih melempar query agregasi ke Storage Engine (VertiPaq).
    *   *C.* RAM server kehabisan kapasitas swap file.
    *   *D.* Ukuran database telah melebihi batas 100 MB.
13. **Skenario Kasus 3**:
    Sebuah dimensi produk memiliki 50 atribut tekstual yang dinormalisasi ke dalam 4 tingkatan snowflake (`DimProduct` $\rightarrow$ `DimSubcategory` $\rightarrow$ `DimCategory` $\rightarrow$ `DimSuperCategory`). Visualisasi matriks Power BI mengalami *timeout* saat pengguna melakukan drill-down pada level tertinggi.
    *Bagaimana rekayasa ulang model yang harus dilakukan untuk mengeliminasi timeout tersebut?*
    *   *A.* Gunakan DirectQuery pada tabel dimensi dan Import pada tabel fakta.
    *   *B.* Denormalisasi seluruh atribut `DimSubcategory`, `DimCategory`, dan `DimSuperCategory` ke dalam satu tabel fisik `DimProduct` di level data warehouse staging, lalu hubungkan ke fakta melalui satu relasi 1 to Many.
    *   *C.* Buat 4 tabel fakta terpisah untuk masing-masing level kategori produk.
    *   *D.* Tambahkan DAX Calculated Column pada tabel fakta untuk setiap level hierarki produk.

---

#### Kunci Jawaban & Pembahasan Evaluasi

##### 1. Jawaban: B
*Pembahasan*: VertiPaq adalah *columnar columnar in-memory engine*. Star Schema memangkas relasi pointer berantai. Setiap kali relasi dilewati, mesin harus memproses *table expansion*. Star Schema membatasi lompatan traversal menjadi tepat 1 lompatan, sehingga evaluasi eksekusi dapat diparalelisasi langsung pada level bit-packed column segment menggunakan CPU vectorization.

##### 2. Jawaban: C
*Pembahasan*: VertiPaq selalu memeriksa apakah suatu nilai integer numerik dapat dihemat rentang variasinya menggunakan selisih nilai terkecil (*Value Encoding*). Jika kardinalitas atau tipe datanya tidak mendukung pengurangan matematis dasar, baris tersebut akan dialihkan ke *Dictionary (Hash) Encoding*.

##### 3. Jawaban: B
*Pembahasan*: *Degenerate Dimension* adalah atribut dimensional (seperti Nomor Invoice, Nomor Resi, Bukti Bayar) yang disimpan langsung di tabel fakta karena tidak memiliki atribut konteks lain selain identifier itu sendiri, sehingga tidak membutuhkan tabel dimensi tersendiri.

##### 4. Jawaban: B
*Pembahasan*: *Fixed Decimal Number* (dalam DAX / Power Query setara tipe `Currency`) dikonversi secara native di memori tabular sebagai integer 64-bit yang diskalakan dengan pembagian $10.000$. Hal ini memungkinkan VertiPaq menerapkan Value Encoding murni alih-alih floating point IEEE 754 float representation.

##### 5. Jawaban: B
*Pembahasan*: Fungsi `USERELATIONSHIP` dirancang khusus untuk memanggil jalur relasi yang sudah ada dalam metadata namun diset sebagai non-aktif (*inactive*), biasanya digunakan untuk skenario *Role-Playing Dimensions* seperti pemilihan tanggal order vs tanggal kirim.

##### 6. Jawaban: B
*Pembahasan*: Mengaktifkan bi-directional cross filtering secara global menciptakan sirkuit evaluasi melingkar (*circular loops*), meningkatkan tabel yang harus dievaluasi di memori (*Expanded Table bloat*), dan kerap menyebabkan hasil metrik tidak akurat karena penyaringan melompat ke dimensi lain di luar fokus analitis.

##### 7. Jawaban: B
*Pembahasan*: Keberadaan NULL pada foreign key memicu pembentukan *internal blank row* di level tabular engine untuk menjaga konsistensi join. Praktik rekayasa data standar enterprise mengharuskan mapping nilai NULL menjadi entitas eksplisit `-1` (*Unknown / Unassigned*) di pipeline data source/ETL.

##### 8. Jawaban: B
*Pembahasan*: Pada VertiPaq, kamus data (*Dictionary*) menyimpan representasi unik dari setiap nilai string. Jika sebuah kolom memiliki jutaan nilai unik, ukuran kamus akan mendominasi penggunaan RAM, dan indeks bit (*bit-width*) yang dialokasikan untuk setiap baris data akan semakin lebar, merusak rasio kompresi.

##### 9. Jawaban: B
*Pembahasan*: Pada SCD Type 2, setiap kali atribut berubah, sebuah baris baru dengan Surrogate Key baru dibuat. Dengan memetakan transaksi ke `CustomerSK` spesifik yang aktif pada waktu transaksi terjadi di pipeline ETL, laporan akan secara otomatis menampilkan profil pelanggan yang akurat secara historis (*point-in-time state*) tanpa memerlukan logika DAX yang lambat.

##### 10. Jawaban: B
*Pembahasan*: `TREATAS` menerapkan hasil ekspresi tabel virtual sebagai konteks filter aktif pada kolom fisik target. Ini adalah teknik *virtual relationship* performa tinggi yang tidak memerlukan pembuatan garis relasi fisik di diagram model, sangat berguna untuk arsitektur many-to-many atau transfer filter dinamis.

##### 11. Jawaban: B
*Pembahasan*: Nilai timestamp presisi tinggi memiliki kardinalitas sangat ekstrem (mendekati total baris transaksi itu sendiri). Memisahkan Date (kardinalitas rendah, misal 365 per tahun) dan Time (kardinalitas maksimal 1.440 jika menit, atau 86.400 jika detik) akan mereduksi ukuran kamus dari puluhan juta baris menjadi beberapa ribu saja, memotong ukuran memori hingga puluhan kali lipat.

##### 12. Jawaban: B
*Pembahasan*: Relasi many-to-many fisik dengan cross-filtering yang rumit sering kali tidak dapat di-*push* ke Storage Engine (VertiPaq) dalam bentuk *SE Query Cache*. Sebaliknya, Formula Engine (FE) yang berbasis thread tunggal (*single-threaded*) terpaksa mengambil data kasar dan memproses kalkulasi filter secara sekuensial di memori aplikasi, menyebabkan metrik waktu CPU FE melonjak tinggi.

##### 13. Jawaban: B
*Pembahasan*: Pemecahan normalisasi berjenjang (*Snowflake*) pada model dimensi memaksa query evaluasi DAX melakukan multi-hop navigation melintasi metadata hierarki. Menggabungkan semuanya (*flattening / denormalizing*) langsung ke level tabel dimensi produk terluar mengembalikan topologi model ke Star Schema murni, memungkinkan mesin VertiPaq melakukan agregasi seketika dalam satu sapuan scan storage engine.

---

### 16. Summary

1.  **VertiPaq Core Mechanics**: Pemodelan data untuk Power BI bukan sekadar meletakkan kotak dan garis relasi. Efisiensi model ditentukan oleh cara kerja internal mesin VertiPaq: **Value Encoding**, **Dictionary Encoding**, dan **Run-Length Encoding (RLE)**. Optimasi data berpusat pada pemangkasan kardinalitas kolom (*distinct values*) dan pengurutan data untuk meningkatkan rasio kompresi memori RAM.
2.  **Star Schema adalah Standar Mutlak**: Arsitektur Snowflake terfragmentasi dan One Big Table (OBT) flat tunggal terbukti tidak optimal untuk mesin analitik analitis tabular columnar. Star Schema memberikan rasio kompresi terbaik, meminimalkan ukuran kamus atribut, dan memberdayakan mekanisme *Expanded Tables* untuk eksekusi DAX super cepat.
3.  **Preservasi Integritas Relasional**: Hindari relasi *Bi-directional Cross-Filtering* dan *Many-to-Many* fisik yang tidak terkontrol. Gunakan relasi fisik searah (*Single Direction*) dengan pasangan kunci numerik bertipe integer (`Whole Number`), dan selesaikan tantangan relasional tingkat lanjut (*Role-Playing Dimensions*, multi-fact attribution) menggunakan pola kalkulasi DAX performa tinggi seperti `USERELATIONSHIP` dan `TREATAS`.