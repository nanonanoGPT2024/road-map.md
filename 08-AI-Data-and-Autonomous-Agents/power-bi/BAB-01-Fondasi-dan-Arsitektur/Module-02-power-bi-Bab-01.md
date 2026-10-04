# BAB 01: FONDASI DAN ARSITEKTUR
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Power BI

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Data Engineer, BI Architect, dan Platform Engineer diharapkan mampu:
*   Menganalisis dan mengoptimalkan struktur internal database in-memory **VertiPaq** (Dictionary Encoding, Run-Length Encoding, Bit-Packing) untuk mereduksi konsumsi RAM hingga lebih dari 70%.
*   Merancang arsitektur dataset berskala enterprise (*Composite Models*, *Dual Storage Mode*, *User-Defined Aggregations*, dan *Hybrid Tables*) yang mampu melayani analitik miliaran baris data dengan latensi *sub-second*.
*   Membangun arsitektur tata kelola *enterprise* berbasis model data terdistribusi (*Hub-and-Spoke Semantic Models*) menggunakan XMLA Endpoints, Tabular Model Definition Language (TMDL), dan pipeline Git/CI-CD modern.
*   Mengimplementasikan kontrol keamanan tingkat lanjut (*Dynamic Row-Level Security* [RLS] dan *Object-Level Security* [OLS]) tanpa mengorbankan performa *cache* VertiPaq.
*   Mendiagnosis kemacetan performa kueri menggunakan profil eksekusi *Formula Engine* (FE) vs *Storage Engine* (SE) melalui DAX Studio dan Dynamic Management Views (DMV).

---

### 2. Prerequisite
Untuk mengikuti modul teknis tingkat lanjut ini, peserta diwajibkan memiliki pemahaman:
*   Prinsip dasar pemodelan data dimensional (Ralph Kimball: *Star Schema*, *Fact & Dimension Tables*, *Surrogate Keys*).
*   Sintaks dasar DAX (fungsi skalar, filter context, kalkulasi agregasi dasar) dan antarmuka Power BI Desktop.
*   Pemahaman tentang TCP/IP, Direct Access Gateway, arsitektur data warehouse (Snowflake, BigQuery, atau Microsoft Fabric/Synapse), dan konsep ACID relational database.
*   Pengalaman dasar menggunakan Git untuk *version control* dan CLI (*command-line interface*).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur performa Power BI berpusat pada **Analysis Services Tabular Engine**, yang terbagi menjadi dua komponen komputasi utama: **Formula Engine (FE)** dan **Storage Engine (SE)**.

```
                      +---------------------------------------+
                      |           DAX Query Request           |
                      +---------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| FORMULA ENGINE (FE)                                                               |
| - Single-threaded per query request.                                              |
| - Parse, Compile, & Generate Execution Plan.                                      |
| - Handles complex, non-relational DAX logic (e.g., IF, scalar variables, loops).  |
| - Merges and evaluates intermediate result sets returned by Storage Engine.       |
+-----------------------------------------------------------------------------------+
               |                                                   |
      VertiPaq Queries                                   DirectQuery SQL / DirectLake
      (xmSQL Requests)                                   Pushdown Queries
               |                                                   |
               v                                                   v
+-------------------------------------------+     +---------------------------------+
| STORAGE ENGINE (SE: VertiPaq)             |     | EXTERNAL STORAGE ENGINE         |
| - Multi-threaded, heavily vectorized.     |     | - Relational DBs, Synapse, Lake |
| - Scans columnar memory partitions.       |     | - Query Folding to native SQL   |
| - Dictionary, RLE, and Bit-Packed data.   |     | - Dependent on source compute   |
| - Returns datacaches to FE.               |     | - Network transfer latency      |
+-------------------------------------------+     +---------------------------------+
```

#### 3.1. VertiPaq Storage Engine Mechanics
VertiPaq adalah database kolumnar *in-memory*. Data disimpan per kolom, bukan per baris (*row-oriented*). Hal ini memungkinkan pembacaan data yang sangat selektif karena *query engine* hanya perlu memuat kolom yang secara eksplisit terlibat dalam relasi, filter, atau kalkulasi.

Proses kompresi VertiPaq berjalan melalui empat tahapan berurutan (*compression pipeline*):

1.  **Value Encoding**:
    Diterapkan pada kolom bertipe data numerik integer atau desimal dengan skala tetap. VertiPaq menghitung nilai minimum kolom ($Min$) dan menyimpan selisih matematis (*delta*) antara setiap baris ($X_i$) dengan nilai minimum:
    $$\Delta = X_i - Min$$
    Contoh: Jika nilai kolom ID adalah `[10001, 10002, 10005]`, nilai $Min = 10001$. Angka yang disimpan adalah `[0, 1, 4]`, yang memangkas kebutuhan alokasi bit secara signifikan.

2.  **Dictionary (Hash) Encoding**:
    Metode standar untuk kolom non-numerik (string, UUID, tipe data campuran). VertiPaq membangun *hash map* yang memetakan setiap nilai unik ke integer ID (dimulai dari `0` hingga `N-1`, di mana $N$ adalah kardinalitas unik).
    Jika kardinalitas unik kolom mencapai 1.000.000, maka setiap referensi baris diubah menjadi integer 20-bit, terlepas dari panjang teks aslinya. Ukuran fisik dictionary ini sangat dipengaruhi oleh **kardinalitas** (tingkat keunikan data).

3.  **Run-Length Encoding (RLE)**:
    Setelah tahap Dictionary Encoding, VertiPaq mengurutkan partisi data untuk menemukan pola data yang berulang secara berurutan. RLE menyimpan pasangan nilai berupa `(Value_ID, Repeat_Count)`.
    Misalnya: Nilai yang telah di-hash bernilai `[3, 3, 3, 3, 3, 7, 7]` akan dikompresi menjadi `(3, 5)` dan `(7, 2)`. Efektivitas RLE sangat bergantung pada **urutan baris (*sort order*)** dalam partisi memori.

4.  **Bit-Packing**:
    Langkah akhir dari kompresi. VertiPaq menghitung jumlah bit eksak yang diperlukan untuk merepresentasikan ID terbesar dalam partisi. Jika nilai integer terbesar adalah 7, sistem tidak akan mengalokasikan standard integer 32-bit atau 64-bit, melainkan hanya **3 bit** per slot baris ($2^3 = 8$).

#### 3.2. Formula Engine vs. Storage Engine Execution Path
Ketika kueri DAX dieksekusi:
1.  **FE** menerima kueri, melakukan parsing sintaks, memvalidasi metadata terhadap Tabular Object Model (TOM), dan menyusun *Query Execution Plan*.
2.  FE memecah kebutuhan data menjadi instruksi pembacaan batch untuk **SE** menggunakan bahasa internal yang disebut **xmSQL**.
3.  **SE** menjalankan *xmSQL* secara paralel (*multi-threaded*) di seluruh inti CPU yang tersedia, memindai blok-blok memori VertiPaq terkompresi, melakukan agregasi parsial dasar (`SUM`, `MIN`, `MAX`, `COUNT`), dan mengembalikan hasilnya ke FE dalam bentuk struktur data memori sementara bernama **datacache**.
4.  Jika logika DAX memuat kalkulasi yang tidak dapat diproses oleh SE (misalnya penggunaan fungsi non-optimizable seperti kueri string rumit, iterator non-relasional, atau penanganan *Context Transition* yang tidak efisien), FE harus mengeksekusi komputasi tersebut secara sekuensial (*single-threaded*). Fenomena ini dikenal sebagai **FE Bottleneck**.

#### 3.3. Storage Modes & Composite Models
Power BI menyediakan empat mode penyimpanan tabel:
*   **Import Mode**: Seluruh tabel dikompresi dan dimuat ke dalam RAM mesin fisik host/kapasitas Power BI Service. Performa pembacaan paling optimal, namun dibatasi oleh kuota memori dan jadwal *refresh*.
*   **DirectQuery Mode**: Tidak ada data tabel yang disimpan di RAM VertiPaq (hanya metadata struktur). Kueri DAX diterjemahkan (*translated*) saat itu juga (*on-the-fly*) menjadi dialek SQL target (*pushdown*). Latensi bergantung langsung pada kapabilitas dan beban *source system*.
*   **Dual Mode**: Tabel disimpan ganda: berada di RAM VertiPaq dan sekaligus dapat berperan sebagai target join DirectQuery. Sangat krusial untuk tabel dimensi pada **Composite Models** guna mencegah lalu lintas data lintas batas (*cross-source data transfer*).
*   **Hybrid Tables**: Partisi historis diatur sebagai *Import Mode* (terkompresi tinggi, cepat), sedangkan partisi transaksi teranyar (misalnya hari ini) diset sebagai *DirectQuery Mode*.

---

### 4. Why & What

| Dimensi Arsitektur | Traditional Relational Direct Query | Traditional SSAS Multidimensional | Power BI Enterprise Tabular (VertiPaq) |
| :--- | :--- | :--- | :--- |
| **Penyimpanan Data** | Berbasis baris di disk (*Row-oriented*) | Blok multidimensional disk pre-agregasi (MOLAP Cubes) | Kolumnar murni di dalam RAM (*In-Memory Columnar*) |
| **Kebutuhan Pemodelan** | Normalisasi 3NF seringkali lambat; butuh indeks fisik manual | Skema bintang kaku; memerlukan kalkulasi kubus MDX kompleks | Skema Bintang fleksibel; dioptimalkan oleh kompresi dinamis |
| **Skalabilitas Data** | Bergantung pada I/O disk dan tuning indeks DBMS | Memerlukan kompilasi data (*processing time*) yang masif | Mendukung puluhan miliar baris dengan *Incremental Refresh* & *Aggregations* |
| **Penggunaan CPU** | I/O wait dominan; lock contention | Multithreaded saat build, query processing terbatas | Multithreaded masif vektorisasi hardware (AVX2/AVX-512) |
| **Fleksibilitas Logika** | Terbatas pada fungsi SQL database target | Terbatas pada MDX tuple & sets | Ekspresif tinggi dengan DAX & Calculation Groups |

Mengapa memahami arsitektur ini krusial?
Pengembangan Power BI skala enterprise tidak boleh mengandalkan asumsi *self-service BI*. Sebuah kueri analitik yang ceroboh pada model berkapasitas 500 juta baris dapat mengekspansi data cache di FE hingga ratusan gigabyte, menyebabkan fenomena *out-of-memory* (OOM) pada kapasitas Premium, serta melumpuhkan performa *tenant* produksi secara global.

---

### 5. How (Workflow Detail)

Berikut alur kerja perancangan dan operasionalisasi arsitektur Power BI tingkat produksi:

```
[ Data Warehouse / Lakehouse ]
            |
            | (ETL / ELT - Star Schema)
            v
[ Gold Layer: Dimension & Fact Tables ]
            |
            | 1. Model Development (TMDL via Tabular Editor / VS Code)
            v
[ Git Repository: Feature Branch ]
            |
            | 2. CI/CD Validation (PBI Inspector / Tabular Model Analyzer)
            v
[ CI/CD Pipeline (Fabric / Azure DevOps) ]
            |
            | 3. Deploy via XMLA Endpoint to Power BI Service Workspace
            v
[ Production Power BI Semantic Model ]
      |                      |
      +-(Import Partitions)  +-(DirectQuery Live Partition)
      |  (VertiPaq via       |  (Real-Time Telemetry/Transactions)
      |   Incremental        |
      |   Refresh Engine)    |
      v                      v
[ VertiPaq In-Memory ]   [ Source Engine Pushdown ]
      \                      /
       \                    /
        v                  v
     [ User Dashboards & Reports ]
```

#### Langkah-Langkah Rekayasa Pipeline:
1.  **Strukturisasi Model (*Semantic Layer*)**:
    *   Pisahkan lapisan *Data Ingestion* dengan lapisan *Reporting*. Terapkan arsitektur **Thin Reports** yang terkoneksi langsung via *Power BI Live Connection* ke **Golden Semantic Model** terpusat.
2.  **Konfigurasi Partisi & Incremental Refresh**:
    *   Definisikan parameter `RangeStart` dan `RangeEnd` bertipe data `DateTime`.
    *   Bagi partisi historis (misal: data 5 tahun terakhir) menjadi partisi statis tahunan/bulanan, dan partisi aktif (misal: 7 hari terakhir) yang di-refresh secara periodik.
3.  **Implementasi Aggregation Tables**:
    *   Buat tabel agregasi yang memadatkan data faktual transaksi detail ke tingkat butiran (*grain*) yang sering diakses (misalnya: `TokoID`, `TanggalID`, `TotalPenjualan`).
    *   Petakan tabel agregasi tersebut ke tabel fakta DirectQuery detail melalui konfigurasi *Manage Aggregations* di Power BI.
4.  **Deployment Terotomatisasi**:
    *   Simpan kode definisi model dalam format file berbasis teks: **TMDL (Tabular Model Definition Language)**.
    *   Gunakan XMLA endpoint untuk mengeksekusi operasi pembaruan metadata dan *refresh* partisi secara presisi via skrip TMSL atau PowerShell.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan vs. Gudang Kontainer Indeks
Bayangkan sistem data tradisional berbasis baris (*row-oriented*) seperti tumpukan buku novel di mana setiap halaman memuat satu transaksi utuh lengkap dengan nama pembeli, waktu, barang, dan harga. Jika Anda ingin menjumlahkan seluruh total transaksi, Anda harus membuka setiap halaman satu per satu dari halaman 1 sampai 1.000.000 hanya untuk membaca angka di baris terbawah.

Arsitektur kolumnar VertiPaq mengoyak buku tersebut dan mengelompokkan halaman berdasarkan kategori data: satu lembaran raksasa hanya memuat angka harga, lembaran lain hanya memuat nama produk. Jika nama produk "Kopi Susu" muncul 500.000 kali berurutan, VertiPaq tidak menulisnya berulang-ulang, melainkan hanya menulis: `"Kopi Susu, ulangi 500.000 kali"`. Menghitung total harga kini hanya membutuhkan operasi scan linear cepat pada lembaran numerik yang sangat tipis langsung di memori kecepatan tinggi.

#### Diagram Arsitektur Internal Storage Engine & Composite Routing

```
                                  [ DAX Inbound Query ]
                                            |
                                            v
                              [ Formula Engine (Parsing) ]
                                            |
                       +--------------------+--------------------+
                       |                                         |
     [ Apakah data ada di Aggregation Table? ]                   |
                       |                                         |
             +---------+---------+                               |
             | YES               | NO                            |
             v                   v                               |
    [ VertiPaq Storage ]   [ Storage Mode Faktanya? ]            |
    [ Aggregated Cache ]         |                               |
    (Respon: <50ms)        +-----+-----+                         |
                           |           |                         |
                        [IMPORT]   [DIRECTQUERY]                 |
                           |           |                         |
                           v           v                         |
                     [ VertiPaq ]  [ SQL Translator (xmSQL -> SQL) ]
                     [ In-Memory]      |
                     (Respon:          v
                      <500ms)      [ Remote DW / Database ]
                                   (Respon: Tergantung DB & Jaringan)
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Deteksi Kardinalitas & Memory Footprint via DMV
Eksekusi kueri Dynamic Management View (DMV) berikut melalui DAX Studio atau SQL Server Profiler yang terhubung ke XMLA Endpoint lokal/remote untuk mendeteksi kolom mana yang membebani alokasi RAM VertiPaq:

```sql
-- Mengambil metrik ukuran kamus data dan kardinalitas kolom pada tabel
SELECT 
    [DIMENSION_NAME] AS [Table_Name],
    [COLUMN_NAME] AS [Column_Name],
    [DICTIONARY_SIZE] AS [Dictionary_Bytes],
    [DICTIONARY_ROW_COUNT] AS [Cardinality_Unique_Values]
FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMNS
WHERE [DICTIONARY_ROW_COUNT] > 0
ORDER BY [DICTIONARY_SIZE] DESC;
```
*Analisis:* Kolom dengan `Cardinality_Unique_Values` bernilai jutaan akan menghasilkan `Dictionary_Bytes` yang besar dan secara signifikan membatasi rasio kompresi RLE.

#### 7.2. Practical Enterprise Example: Calculation Groups via TMDL Scripting
Berikut adalah skrip definisi TMDL untuk mengimplementasikan **Calculation Group: Time Intelligence**. Metode ini mengeliminasi kebutuhan penulisan puluhan *measure* redundan (seperti YTD, QTD, PY) untuk setiap metrik bisnis tunggal.

```tmdl
table 'Time Intelligence'
	calculationGroup
		precedence: 20

		calculationItem YTD = 
				VAR _SelectedDate = MAX('Date'[Date])
				RETURN
				    CALCULATE(
				        SELECTEDMEASURE(),
				        DATESYTD('Date'[Date])
				    )

		calculationItem PY = 
				CALCULATE(
				    SELECTEDMEASURE(),
				    SAMEPERIODLASTYEAR('Date'[Date])
				)

		calculationItem 'YoY %' = 
				VAR _Current = SELECTEDMEASURE()
				VAR _Previous = CALCULATE(SELECTEDMEASURE(), SAMEPERIODLASTYEAR('Date'[Date]))
				RETURN
				    DIVIDE(_Current - _Previous, _Previous, BLANK())
			formatStringDefinition = "0.00%"

		calculationItem 'Moving 30D' = 
				CALCULATE(
				    SELECTEDMEASURE(),
				    DATESINPERIOD('Date'[Date], MAX('Date'[Date]), -30, DAY)
				)

	column 'Time Calculation'
		dataType: string
		sourceColumn: Name
		sortByColumn: Ordinal

	column Ordinal
		dataType: int64
		isHidden
		sourceColumn: Ordinal
```

Skrip C# berikut dapat dieksekusi di dalam **Tabular Editor 3** untuk mengotomatisasi pembuatan Calculation Items berskala besar:

```csharp
// Tabular Editor C# Script: Membuat Format Mask Dinamis untuk Multi-Mata Uang
var cg = Model.AddCalculationGroup("Currency Selector");
cg.Precedence = 10;

var ciUSD = cg.AddCalculationItem("To USD");
ciUSD.Expression = "SELECTEDMEASURE() * SELECTEDVALUE('FxRate'[RateToUSD], 1.0)";
ciUSD.FormatStringExpression = "\"$\"#,##0.00";

var ciEUR = cg.AddCalculationItem("To EUR");
ciEUR.Expression = "SELECTEDMEASURE() * SELECTEDVALUE('FxRate'[RateToEUR], 1.0)";
ciEUR.FormatStringExpression = "\"€\"#,##0.00";

var ciIDR = cg.AddCalculationItem("To IDR");
ciIDR.Expression = "SELECTEDMEASURE() * SELECTEDVALUE('FxRate'[RateToIDR], 1.0)";
ciIDR.FormatStringExpression = "\"Rp\"#,##0";
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Klien
Sebuah institusi perbankan multinasional memiliki tabel transaksi kartu kredit (`Fact_CreditCardTransactions`) dengan volume **12 miliar baris**, bertumbuh rata-rata 15 juta baris per hari. 

#### Masalah Kritis
1.  Model data awal berbasis DirectQuery murni ke Snowflake mengalami degradasi performa: waktu render visualisasi rata-rata dashboard mencapai **18 hingga 35 detik**.
2.  Beban komputasi Snowflake melonjak tajam, memicu konsumsi biaya *warehouse* sebesar $45,000 per bulan hanya untuk melayani kueri interaktif dari 800 *business analyst*.
3.  Kapasitas Power BI Premium P1 sering kali mengalami *throttling* akibat transmisi data lintas jaringan (*cross-network data serialization*).

#### Solusi Arsitektur Produksi
Arsitek mengimplementasikan **Composite Aggregation Architecture with Hybrid Partitions**:

```
[ User Query: Interaksi Dashboard ]
                 |
                 v
+-----------------------------------------------------------------------------------+
| POWER BI SEMANTIC MODEL                                                           |
|                                                                                   |
| 1. AGGREGATION TABLE (Import Mode - VertiPaq Memory)                             |
|    - Grain: CustomerSegmentID, TransactionDate, MerchantCategoryID, CountryID     |
|    - Footprint: 8.5 Juta baris (Diringkas dari 12 Miliar baris)                   |
|    - Update: Refresh 4x sehari via Enhanced Refresh REST API                     |
|                                                                                   |
| 2. DETAILED FACT (Composite / Hybrid Table)                                       |
|    +-- Historical Partitions (T-3 Tahun s/d Kemarin): Import Mode                 |
|    |   - Dipadatkan dengan Bit-Packing & Dictionary Encoding optimal              |
|    +-- Real-Time Partition (Hari Ini / T-0): DirectQuery Partition               |
|        - Pushdown langsung ke Snowflake Small Warehouse via Native SQL Query      |
|                                                                                   |
| 3. DIMENSION TABLES (Dual Storage Mode)                                           |
|    - Dim_Date, Dim_Merchant, Dim_Customer                                         |
|    - Bertindak lokal saat join dengan Agregasi (No Network I/O)                   |
|    - Bertindak remote saat join dengan Detailed DirectQuery                       |
+-----------------------------------------------------------------------------------+
```

#### Hasil Metrik Implementasi
*   **Latency Penurunan Kueri**: 94% kueri pengguna dijawab langsung oleh *Aggregation Table* di memori VertiPaq dengan respons visual rata-rata **380 milidetik** (sub-second).
*   **Efisiensi Biaya Cloud**: Beban kueri ke Snowflake terpangkas drastis hingga 85%, menurunkan tagihan bulanan dari $45,000 menjadi $7,200.
*   **Konsumsi RAM Model**: Melalui pemisahan tanggal dan waktu (*splitting timestamp*) serta penghapusan kolom GUID/Text transaksi mentah, 12 miliar baris transaksi historis dikompresi ke dalam RAM hanya memakan kapasitas **42 GB** di Power BI Premium Capacity.

---

### 9. Trade-offs

Setiap keputusan arsitektur data pada Power BI melibatkan kompromi teknis:

| Pendekatan Arsitektur | Keuntungan Utama (*Pros*) | Konsekuensi Negatif (*Cons / Trade-offs*) | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **Pure Import Mode** | Performa analitik DAX maksimal, semua fungsi DAX didukung penuh tanpa limitasi. | Refresh memakan bandwidth dan waktu; batas ukuran RAM kapasitas membatasi batas atas data. | Data historis hingga <100GB RAM yang hanya butuh update terjadwal. |
| **Pure DirectQuery Mode** | *Real-time data*, tidak ada batasan ukuran memori VertiPaq, audit log terpusat di source DB. | Pembatasan ketat sintaks DAX, latensi visual lambat, beban konkurensi database sumber sangat tinggi. | Regulasi kepatuhan ketat (data tidak boleh keluar dari DB fisik/on-premise). |
| **User-Defined Aggregations** | Latensi *sub-second* pada data masif; transparansi query bagi user akhir. | Kompleksitas pemodelan data berlipat; sinkronisasi partisi agregasi dan detail harus presisi. | Solusi standar data warehouse enterprise (Volume >500 juta baris). |
| **Calculation Groups** | Mencegah *measure explosion*; pemeliharaan kode DAX terpusat dan rapi. | Menonaktifkan optimasi kueri skalar tertentu (*Trivial Query Elimination*); berisiko mengubah format visual tak terduga. | Laporan keuangan / korporat kompleks dengan metrik multi-periode berulang. |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus Kesalahan Kritis 1: Kolom Bertipe `DateTime` Resolusi Tinggi (High Cardinality Trap)
*   **Gejala**: File PBIX berukuran gigabyte saat disimpan; konsumsi RAM melonjak ratusan persen.
*   **Akar Masalah**: Kolom `TransactionTimestamp` memiliki format `YYYY-MM-DD HH:MM:SS.FFF`. Nilai unik mendekati jumlah total baris (*cardinality* 1:1). VertiPaq Dictionary Encoding tidak dapat mengompresi data ini, dan RLE menjadi tidak berguna ($0\%$ kompresi).
*   **Solusi Rekayasa**: Pisahkan kolom menjadi dua di lapisan ETL data: `DateKey` (tipe Integer: `YYYYMMDD`) dan `TimeKey` (tipe Integer atau SmallInt: representasi jam/menit, maksimum 1.440 nilai unik harian).

#### Kasus Kesalahan Kritis 2: Mengabaikan Query Folding pada Power Query (M Engine)
*   **Gejala**: Refresh *dataset* timeout (>2 jam) saat menarik data dari PostgreSQL atau Oracle.
*   **Akar Masalah**: Terdapat langkah transformasi non-standard (misal: memanggil fungsi kustom Python/R atau melakukan kalkulasi string rumit) di tahap awal pipeline Power Query M. Hal ini memutuskan **Query Folding**, memaksa Power BI menarik seluruh tabel puluhan juta baris ke mesin lokal sebelum melakukan filter.
*   **Solusi Rekayasa**: Pastikan indikator *View Native Query* tetap aktif pada langkah transformasi akhir. Pindahkan kalkulasi yang tidak didukung *folding* ke dalam database sumber melalui *SQL Views* resmi.

#### Panduan Troubleshooting DAX Studio Profiling:
1.  Jalankan **DAX Studio** dan koneksikan ke port lokal Power BI Desktop atau XMLA endpoint.
2.  Aktifkan tab **Server Timings** dan centang opsi **SE Queries** dan **FE Execution**.
3.  Eksekusi kueri visual Anda:
    *   Jika **FE Time > 40%**: Mengindikasikan penulisan DAX bermasalah (terdapat *context transition* di iterator, penggunaan filter tabel utuh alih-alih filter kolom, atau kegagalan SE cache).
    *   Jika **SE Query Count > 50 kueri parsial**: Menandakan terjadinya kueri loop atau *callback data engine*, perbaiki formula menggunakan variabel (`VAR`) untuk mengevaluasi *scalar result* sekali saja.

---

### 11. Best Practices (Production Checklist)

Gunakan matriks operasional berikut sebelum merilis model ke lingkungan *Production*:

| Kategori | Parameter Pemeriksaan | Target Standar Produksi |
| :--- | :--- | :--- |
| **Model Optimization** | Star Schema Topology | Fakta hanya memiliki relasi *1-to-Many* dengan Dimensi. Hindari relasi *Many-to-Many* fisik. |
| **Data Types** | Auto Date/Time Setting | Wajib dinonaktifkan secara global di options untuk menghentikan pembuatan tabel waktu tersembunyi (*local date tables*). |
| **Cardinality** | Primary Key & Foreign Key GUID | Hapus seluruh string/UUID ID dari Fact table jika tidak digunakan secara riil dalam relasi analitik visual. |
| **Security Architecture** | Dynamic RLS Logic | Pastikan tabel keamanan RLS terpisah, gunakan relasi berarah tunggal dengan pola `USERPRINCIPALNAME()`. |
| **Performance** | Bidirectional Filtering | Tidak boleh ada filter dua arah (*Both*) kecuali dijustifikasi secara ketat pada model bridge dimensi spesifik. |
| **Query Folding** | ETL Source Folding | 100% langkah M Query pada tabel fakta berskala besar harus mempertahankan status *Query Folding*. |
| **Storage Modes** | Dimension Tables in Composite | Seluruh tabel dimensi yang berelasi dengan DirectQuery Fact dan Import Fact harus diset ke **Dual Mode**. |
| **Enterprise Refresh** | Incremental Refresh Policy | Wajib dikonfigurasi untuk seluruh tabel transaksi di atas 10 juta baris dengan deteksi data termodifikasi. |

---

### 12. Hands-on Practice

Struktur direktori kerja praktikum ini harus disiapkan dan dieksekusi di `hands-on/m02/`:

```
hands-on/m02/
├── 01-vertipaq-analyzer.dax
├── 02-advanced-calculation-group.cs
└── 03-sales-hybrid-model.tmdl
```

#### Langkah 1: Diagnosis Footprint VertiPaq via DMV DAX Studio
Simpan skrip berikut sebagai `hands-on/m02/01-vertipaq-analyzer.dax`. Buka DAX Studio, koneksikan ke model aktif, lalu jalankan kueri ini untuk mengidentifikasi 5 kolom paling tidak efisien:

```dax
// File: hands-on/m02/01-vertipaq-analyzer.dax
EVALUATE
TOPN(
    5,
    SELECTCOLUMNS(
        FILTER(
            $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMN_SEGMENTS,
            [SEGMENT_NUMBER] = 0
        ),
        "Table", [TABLE_ID],
        "Column", [COLUMN_ID],
        "Allocated_Bytes", [ALLOCATED_SIZE],
        "Used_Bits_Per_Value", [USED_SIZE]
    ),
    [Allocated_Bytes],
    DESC
)
```

#### Langkah 2: Otomatisasi Time-Intelligence via Tabular Editor CLI / Scripting
Simpan skrip C# berikut sebagai `hands-on/m02/02-advanced-calculation-group.cs`. Jalankan di Tabular Editor Advanced Scripting Console:

```csharp
// File: hands-on/m02/02-advanced-calculation-group.cs
// Menghasilkan otomatis Calculation Group untuk pemfilteran dinamis
var group = Model.AddCalculationGroup("Advanced Analytics");
group.Description = "Enterprise grade calculation group for operational analytics.";

// 1. Current Period
var itemCurrent = group.AddCalculationItem("Base Metric");
itemCurrent.Expression = "SELECTEDMEASURE()";

// 2. Rolling 7-Day Average
var itemR7 = group.AddCalculationItem("Rolling 7D Avg");
itemR7.Expression = @"
AVERAGEX(
    DATESINPERIOD('Dim_Date'[FullDateAlternateKey], MAX('Dim_Date'[FullDateAlternateKey]), -7, DAY),
    SELECTEDMEASURE()
)";

// 3. Year-over-Year Growth Delta
var itemYoY = group.AddCalculationItem("YoY Absolute Growth");
itemYoY.Expression = @"
SELECTEDMEASURE() - CALCULATE(SELECTEDMEASURE(), SAMEPERIODLASTYEAR('Dim_Date'[FullDateAlternateKey]))
";

// Simpan struktur ke model internal
ScriptHelper.Info("Calculation Group successfully injected.");
```

#### Langkah 3: Skrip Definisi Partisi Hybrid Model Menggunakan TMDL
Simpan file konfigurasi partisi hybrid berikut sebagai `hands-on/m02/03-sales-hybrid-model.tmdl`:

```tmdl
// File: hands-on/m02/03-sales-hybrid-model.tmdl
table Fact_EnterpriseSales
	lineageTag: a7e923e1-382a-4dfb-9ef1-c91cbfa791a2

	partition 'Historical-2023' = m
		mode: import
		source = 
			let
			    Source = Sql.Database("dw-prod-cluster.database.windows.net", "EDW_Prod"),
			    dbo_Sales = Source{[Schema="dbo",Item="Fact_Sales"]}[Data],
			    FilteredRows = Table.SelectRows(dbo_Sales, each [OrderDate] >= #datetime(2023, 1, 1, 0, 0, 0) and [OrderDate] < #datetime(2024, 1, 1, 0, 0, 0))
			in
			    FilteredRows

	partition 'RealTime-Current' = m
		mode: directQuery
		source = 
			let
			    Source = Sql.Database("dw-prod-cluster.database.windows.net", "EDW_Prod"),
			    dbo_Sales = Source{[Schema="dbo",Item="Fact_Sales"]}[Data],
			    FilteredRows = Table.SelectRows(dbo_Sales, each [OrderDate] >= #datetime(2024, 1, 1, 0, 0, 0))
			in
			    FilteredRows

	measure 'Gross Revenue' = SUM(Fact_EnterpriseSales[LineTotal])
		formatString: \$#,##0.00
```

---

### 13. Exercise

#### Level Easy
Ekstrak daftar seluruh kolom dalam dataset yang memiliki status kompresi bertipe `Hash (Dictionary)` dan urutkan berdasarkan kardinalitas unik dari terbesar ke terkecil menggunakan Dynamic Management View (DMV) `$SYSTEM.DISCOVER_STORAGE_TABLE_COLUMNS`.

#### Level Medium
Buat sebuah skrip DAX Measure untuk metrik akumulasi `Sales YTD` yang menggunakan pola `FILTER` dan `ALL` secara eksplisit, lalu perbaiki kode tersebut menggunakan fungsi kalkulasi native Time Intelligence (`DATESYTD`). Bandingkan jumlah *Storage Engine Sub-queries* dan total durasi eksekusi FE/SE dari kedua pendekatan tersebut menggunakan modul DAX Studio Server Timings.

#### Level Hard
Rancang model skema bintang gabungan (*Composite Model*) yang melibatkan:
1.  Tabel `Fact_OnlineSales` (DirectQuery ke Azure Synapse / Snowflake).
2.  Tabel agregasi `Agg_Sales_Monthly` yang disimpan dalam VertiPaq Import Mode.
Konfigurasikan relasi *Manage Aggregations* pada Power BI Desktop sehingga ketika user membuat visualisasi berbasis `Bulan` dan `Kategori Produk`, kueri otomatis dijawab oleh VertiPaq, namun saat visualisasi diubah hingga ke tingkat detail `OrderID`, kueri secara transparan melakukan *fallback* ke DirectQuery Synapse. Tunjukkan trace bukti tangkapan visualisasi melalui SQL Profiler.

---

### 14. Challenge

**Skenario Kasus Kompleks**:
Sebuah platform logistik global menangani **25 miliar data rekaman sensor telemetri armada GPS**. Anda ditunjuk sebagai Chief Enterprise BI Architect dengan batasan teknis berikut:
*   Kapasitas yang disewa adalah **Fabric F64 Capacity** (memiliki limit memori fisik aktif ~64 GB).
*   Data sensor mentah bertambah **100 juta baris per 24 jam**.
*   SLA kueri interaktif untuk dashboard tingkat Country Manager harus berada di bawah **800 milidetik**.
*   Namun, tim audit investigasi kecelakaan harus dapat menelusuri detail interval detik sensor per kendaraan secara ad-hoc (*sub-second fallback* tidak diwajibkan untuk audit, tetapi kueri audit tidak boleh melempar status error OOM ke kapasitas).
*   Data memiliki otorisasi ketat: Branch Manager hanya boleh mengakses armada di zona geofence masing-masing secara dinamis (*Dynamic RLS*).

**Tugas Arsitektur**:
1.  Rancang blueprint skema pemodelan data fisik (uraikan konfigurasi *Storage Mode* masing-masing tabel: Detail Fact, Aggregation Fact, Dim_Vehicle, Dim_Date, Dim_Geography, Dim_SecurityMap).
2.  Tentukan arsitektur partisi dan siklus *refresh* tabel telemetry, termasuk bagaimana parameter `RangeStart` dan `RangeEnd` bekerja harmonis dengan partisi *DirectQuery Live*.
3.  Jelaskan secara mendalam bagaimana Anda mengimplementasikan Dynamic RLS pada arsitektur hybrid ini tanpa memicu fenomena pemutusan *DirectQuery pushdown folding* dan tanpa membuat SE mengeksekusi *table scan* berulang kali.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)

1.  Komponen internal Tabular Engine yang bertanggung jawab merencanakan eksekusi kueri, mengompilasi logika DAX non-relasional, dan bersifat single-threaded adalah:
    *   A. Storage Engine
    *   B. Formula Engine
    *   C. VertiPaq Compressor
    *   D. On-Premises Data Gateway

2.  Teknik kompresi data VertiPaq yang menggantikan nilai-nilai berulang yang berurutan dengan pasangan (ID Nilai, Jumlah Kemunculan) adalah:
    *   A. Bit-Packing
    *   B. Value Encoding
    *   C. Run-Length Encoding (RLE)
    *   D. Hash Dictionary Encoding

3.  Tipe Storage Mode yang memuat metadata ke Power BI, namun data fisik transaksi tetap tersimpan sepenuhnya di database sumber adalah:
    *   A. Import Mode
    *   B. Dual Mode
    *   C. DirectLake
    *   D. DirectQuery Mode

4.  Apa dampak utama penggunaan kolom bertipe data `DateTime` dengan presisi milidetik terhadap VertiPaq Storage Engine?
    *   A. Menyebabkan model beralih otomatis ke DirectQuery
    *   B. Meningkatkan kardinalitas secara ekstrem, melipatgandakan ukuran Dictionary dan membatasi RLE
    *   C. Mengoptimalkan performa fungsi DAX berbasis Time Intelligence
    *   D. Menyebabkan kegagalan saat proses serialisasi XMLA

5.  Format bahasa berbasis teks baru yang dirancang untuk merepresentasikan Tabular Object Model (TOM) dan dioptimalkan untuk integrasi Git adalah:
    *   A. JSON
    *   B. TMDL
    *   C. XML
    *   D. DAX

*Kunci Jawaban Basic:*
1.  **B** — Formula Engine (FE) bersifat single-threaded dan menangani eksekusi logika kompleks serta orkestrasi kueri.
2.  **C** — Run-Length Encoding (RLE) mengompresi data berurutan menjadi pasangan nilai dan frekuensi repetisi.
3.  **D** — DirectQuery tidak menyimpan salinan data di RAM internal melainkan membaca langsung ke sumber.
4.  **B** — Nilai unik yang sangat tinggi (kardinalitas tinggi) membengkakkan ukuran memory kamus (*dictionary*) dan mengeliminasi efektivitas RLE.
5.  **B** — TMDL (*Tabular Model Definition Language*) adalah format deklaratif manusiawi yang ramah git.

---

#### Bagian 2: Intermediate (5 Pertanyaan)

6.  Tabel dimensi dalam arsitektur *Composite Model* sebaiknya dikonfigurasi menggunakan mode penyimpanan **Dual Mode**. Mengapa?
    *   A. Agar tabel tersebut dapat dibaca dari dua database relasional yang berbeda secara simultan.
    *   B. Mengizinkan Power BI bertindak sebagai VertiPaq in-memory saat di-join dengan tabel Import, dan bertindak sebagai DirectQuery native join saat di-join dengan tabel DirectQuery guna menghindari cross-source queries.
    *   C. Menjamin data tabel dimensi di-refresh otomatis setiap 5 detik tanpa gateway.
    *   D. Mengaktifkan fitur multi-language translation secara native.

7.  Perhatikan skenario berikut: Eksekusi measure DAX menghasilkan trace *Server Timings* dengan metrik: FE Duration = 3200ms, SE Duration = 150ms. Apa interpretasi teknis yang paling tepat?
    *   A. VertiPaq memory kekurangan alokasi core CPU.
    *   B. Kueri terhambat oleh antrean I/O disk database sumber.
    *   C. Terjadi FE Bottleneck; DAX measure kemungkinan besar mengeksekusi iterasi baris yang tidak optimal atau mengevaluasi formula yang tidak dapat di-pushdown ke Storage Engine.
    *   D. Jaringan lokal gateway mengalami packet loss.

8.  Apa batasan fungsional dari fitur **Calculation Groups** ketika diimplementasikan pada model enterprise?
    *   A. Calculation groups tidak dapat dikombinasikan dengan tabel bertipe DirectQuery.
    *   B. Properti `FormatStringDefinition` tidak dapat diubah secara dinamis.
    *   C. Mengharuskan penghapusan seluruh measure eksplisit yang ada di dalam model.
    *   D. Dapat menonaktifkan optimasi kueri internal tertentu (*trivial query reduction*) dan berpotensi memicu perilaku tak terduga pada visual yang mengandalkan implisit format strings.

9.  Dalam proses kompresi VertiPaq, pada kondisi seperti apa **Value Encoding** ditolak oleh engine dan dialihkan menjadi **Dictionary Encoding**?
    *   A. Jika kolom berisi tipe data teks murni atau terdapat nilai non-numerik dalam baris kolom tersebut.
    *   B. Jika kardinalitas kolom numerik lebih kecil dari 100 nilai unik.
    *   C. Jika memori server melebihi ambang batas 80%.
    *   D. Jika tabel diset ke dalam mode Incremental Refresh.

10. Mengapa penerapan fungsi skalar DAX seperti `FORMAT()` di dalam kalkulasi measure berpotensi merusak latensi dashboard pada visual berukuran besar?
    *   A. Karena fungsi tersebut memicu write-lock pada dataset.
    *   B. Karena fungsi `FORMAT()` mengembalikan output teks dan memaksa evaluasi dijalankan baris demi baris di Formula Engine tanpa pemanfaatan paralelisasi Storage Engine.
    *   C. Karena fungsi tersebut memutus integrasi DirectLake.
    *   D. Karena fungsi tersebut mengubah storage mode tabel fakta menjadi DirectQuery.

*Kunci Jawaban Intermediate:*
6.  **B** — Dual mode memungkinkan fleksibilitas join in-memory internal atau pushdown relational join untuk meminimalkan beban transfer data.
7.  **C** — Dominasi waktu Formula Engine (FE) menandakan komputasi DAX yang tidak dapat diproses secara terparalelisasi oleh Storage Engine (SE).
8.  **D** — Calculation groups mengevaluasi ekspresi di atas konteks kueri yang ada sehingga membatasi optimasi primitif engine tertentu.
9.  **A** — Value Encoding hanya bekerja untuk angka integer atau desimal murni yang memiliki rentang matematis terdefinisi; adanya teks memaksa engine beralih ke Dictionary Encoding.
10. **B** — Fungsi format string mengubah representasi data menjadi objek teks individual yang memerlukan intervensi penuh dari Formula Engine secara sekuensial.

---

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Kompleks)

11. **Skenario Kasus 1: Row-Level Security Performance Degradation**
    Model semantic enterprise Anda memiliki 200 juta baris transaksi penjualan. Anda menerapkan *Dynamic RLS* menggunakan formula berikut pada tabel dimensi `Dim_Employee`:
    `[Email] = USERPRINCIPALNAME()`
    Relasi antara `Dim_Employee` dan `Fact_Sales` adalah *1-to-Many*, namun opsi *Cross-filter direction* diatur ke **Both** karena kebutuhan historis. Setelah RLS diterapkan ke security role, performa rendering kartu KPI anjlok dari 400ms menjadi 12 detik.
    Sebagai Lead Architect, apa langkah perbaikan teknis berbobot performa tertinggi yang harus Anda ambil?
    *   A. Mengubah mode penyimpanan `Fact_Sales` menjadi DirectQuery murni.
    *   B. Menghapus konfigurasi filter dua arah (*Both*), mengembalikan relasi menjadi arah tunggal (*Single*), dan menerapkan logika filtering keamanan langsung pada dimensi perantara atau menggunakan pola *bridge security table* dengan DAX pattern berbasis `TREATAS` atau filter kontekstual satu arah.
    *   C. Mengonversi tipe data kolom `Email` menjadi Binary hash.
    *   D. Menambahkan memori RAM pada kapasitas Power BI Premium sebesar 2x lipat.

    *Rasional Jawaban 11:*
    **B** — Relasi *bidirectional* (*Both*) yang bersilangan dengan aturan RLS memaksa Storage Engine mematikan optimasi cache global dan menyebabkan eksekusi evaluasi keamanan diperluas secara non-deterministik ke seluruh tabel fakta untuk setiap kueri visual, membebani Formula Engine.

12. **Skenario Kasus 2: Failure pada Query Folding di DirectQuery Architecture**
    Sebuah kueri analitik DirectQuery diarahkan ke Snowflake. Data Engineer menambahkan measure kompleks berikut:
    `Sales_Rank = RANKX(ALL(Fact_Sales[RegionID]), CALCULATE(SUM(Fact_Sales[Amount])))`
    Visual matriks yang memuat measure ini gagal me-render data dan melempar error: *"The visual query exceeds the maximum allowed limits or cannot be folded."*
    Apa akar penyebab masalah teknis ini?
    *   A. Tabel fakta di Snowflake tidak memiliki clustering key.
    *   B. Fungsi `RANKX` pada DirectQuery model seringkali tidak dapat diterjemahkan (*unfoldable*) secara langsung menjadi native ANSI SQL Window Function efisien oleh translator engine, memaksa Power BI menarik seluruh hasil agregasi ke RAM lokal sebelum eksekusi ranking. Ketika data agregat melebihi limit baris internal (biasanya 1.000.000 baris intermediate), kueri dibatalkan oleh engine.
    *   C. DirectQuery tidak mengizinkan referensi ke kolom bertipe numerik.
    *   D. Power BI Desktop mewajibkan instalasi driver ODBC khusus untuk fungsi ranking.

    *Rasional Jawaban 12:*
    **B** — M-Engine / DAX Translator memiliki limitasi dalam menerjemahkan fungsi iterasi kontekstual rumit ke SQL murni. Jika komputasi gagal di-*pushdown*, sistem mencoba melakukan fallback evaluasi lokal hingga membentur limitasi konkurensi atau memori data transfer DirectQuery.

13. **Skenario Kasus 3: Incremental Refresh Partition Swapping Failure**
    Anda mengonfigurasi *Incremental Refresh* pada tabel `Fact_Shipments` (500 juta baris) dengan kebijakan: simpan data historis 5 tahun, dan refresh partisi data 10 hari terakhir. Deteksi perubahan data (*Detect Data Changes*) diaktifkan menggunakan kolom `LastModifiedDate`. Setelah migrasi database sumber dari On-Premise SQL ke Cloud Data Warehouse, proses refresh via REST API gagal dengan notifikasi kesalahan: *"Partition range does not evaluate to valid datetime sequence."*
    Apa penyebab arsitektural dari kegagalan ini?
    *   A. Cloud Data Warehouse memiliki zona waktu UTC, sementara On-Premise SQL memiliki zona waktu lokal, menyebabkan benturan tipe data `DateTimeZone` yang tidak dapat dipetakan ke parameter skalar `RangeStart`/`RangeEnd` yang bertipe murni `DateTime`.
    *   B. Fitur *Incremental Refresh* tidak didukung pada Cloud DW.
    *   C. Kolom `LastModifiedDate` memiliki nilai NULL pada partisi statis 5 tahun lalu.
    *   D. Ukuran file PBIX lokal sebelum dipublish melebihi 1 GB.

    *Rasional Jawaban 13:*
    **A** — Mesin *partitioning* VertiPaq mensyaratkan parameter `RangeStart` dan `RangeEnd` bertipe data `DateTime` tanpa penanda zona waktu (*timezone offsets*). Perbedaan tipe implisit antara tipe data sumber cloud (`DateTimeZone` / `Timestamp with TZ`) dan parameter M menyebabkan partisi partisi internal gagal melakukan isolasi rentang baris matematis (*boundary calculation failure*).

---

### 16. Summary
Performa, ketahanan, dan skalabilitas ekosistem enterprise Power BI tidak ditentukan oleh visual antarmuka pengguna, melainkan oleh pemahaman mendalam atas arsitektur internal mesin **VertiPaq** dan **Analysis Services Tabular Model**.

Kunci utama efisiensi model data volume masif mencakup:
1.  **Reduksi Kardinalitas**: Mengoptimalkan struktur data tabular dengan mengeliminasi string resolusi tinggi, memisahkan timestamp, dan mengandalkan *Dictionary* serta *Run-Length Encoding (RLE)* secara maksimal.
2.  **Arsitektur Penyimpanan Hibrida (*Composite Models*)**: Mengawinkan latensi *sub-second* VertiPaq melalui *Aggregation Tables* dengan kapasitas data tak terbatas dari *DirectQuery Pushdown*.
3.  **Modern Code Lifecycle**: Beralih dari file biner `.pbix` monolitik menuju paradigma deklaratif berbasis teks modern (**TMDL**), konfigurasi otomatisasi via **Tabular Editor**, dan deployment terkelola berbasis **XMLA Endpoints** serta integrasi Git/CI-CD.