# Bab 01: Arsitektur Fundamental Mesin Power BI
## Module 01: VertiPaq Engine, Tabular Object Model (TOM), dan Pipeline Evaluasi Data

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** siklus hidup kueri DAX end-to-end melalui interaksi *Formula Engine* (FE) dan *Storage Engine* (SE/VertiPaq).
- **Mengevaluasi** struktur internal VertiPaq (*Columnar In-Memory Database*) mencakup *Dictionary Encoding*, *Run-Length Encoding* (RLE), *Bit-Packing*, dan *Hash Encoding*.
- **Membedah** metadata model semantik menggunakan *Tabular Object Model* (TOM) dan *Tabular Model Scripting Language* (TMSL).
- **Mendiagnosis** *bottleneck* performa pemrosesan data antara single-threaded FE versus multi-threaded SE menggunakan trace event xmSQL.
- **Mengoptimalkan** efisiensi kompresi data vertikal guna meminimalkan jejak memori (*RAM footprint*) pada model skala enterprise.

---

### 2. Conceptual Deep-Dive
Power BI bukanlah sekadar visualisasi data di atas *relational database*; engine intinya adalah instans lokal dari **Microsoft SQL Server Analysis Services (SSAS) Tabular Mode**. Mesin yang menggerakkannya disebut **VertiPaq Engine** (xVelocity In-Memory Analytical Engine).

VertiPaq adalah *columnar in-memory database*. Berbeda dengan sistem *Row-Store* transaksional (OLTP) yang menyimpan data sebagai tuple horizontal berurutan dalam *data page* (8 KB pada SQL Server), VertiPaq menyimpan seluruh data kolom secara vertikal dan kontinu dalam RAM. 

```
Row-Store (OLTP):
[Row 1: ID, CustName, Amount] -> [Row 2: ID, CustName, Amount]

Column-Store / VertiPaq (OLAP):
[Column ID: 1, 2, ...]
[Column CustName: "Alice", "Bob", ...]
[Column Amount: 100.50, 250.00, ...]
```

Keuntungan struktural ini berbasis pada:
1. **Prinsip Lokalisasi Data (Locality of Reference):** Analitik data jarang mengeksekusi `SELECT *`. Agregasi biasanya memindai 2-5 kolom dari tabel yang memiliki 50 kolom. VertiPaq hanya membaca memori untuk kolom-kolom yang relevan dengan kalkulasi, menghindari *cache miss* pada L1/L2/L3 cache CPU.
2. **Homogenitas Tipe Data:** Nilai dalam satu kolom memiliki tipe data yang sama persis, memaksimalkan rasio kompresi matematis melalui transformasi aljabar matriks dan algoritma kompresi sekuensial.

---

### 3. The "Why"
Model arsitektur tradisional *Row-Oriented Relational OLAP* (ROLAP) memicu degradasi performa masif saat menangani volume data ratusan juta baris:
- **I/O Bottleneck:** Pembacaan data dari media penyimpanan persisten (SSD/NVMe/HDD) ke memori terlalu lambat untuk visual interaktif (SLA < 1000ms).
- **CPU Cycle Inefficiency:** Struktur row-store menyulitkan instruksi SIMD (Single Instruction, Multiple Data) CPU untuk memproses vektor numerik secara paralel.
- **Biaya Infrastruktur:** Database disk-bound membutuhkan optimasi indeks non-clustered, indexing b-tree redundan, dan fragmentasi disk yang memerlukan alokasi *compute* tinggi.

VertiPaq memecahkan masalah ini dengan mereduksi data masuk ke dalam representasi kompresi integer mutlak, menahan seluruh struktur model di RAM (L1/L2/L3 cache friendly), dan mendistribusikan pemindaian agregasi ke seluruh core CPU fisik secara paralel tanpa konkurensi lock.

---

### 4. The "What"
Arsitektur internal Power BI Desktop dan Service beroperasi melalui komponen-komponen inti berikut:

#### Formula Engine (FE)
- **Karakteristik:** Berjalan pada thread tunggal (*single-threaded* per kueri pengguna).
- **Fungsi:** Mengurai (*parse*) DAX, menghasilkan *logical query plan*, menghasilkan *physical query plan*, mengelola *Evaluation Context* (*Row Context* dan *Filter Context*), memanggil *Storage Engine* untuk mendapatkan data mentah terkondensasi, dan mengeksekusi kalkulasi kompleks non-komutatif (misalnya: `MEDIAN`, `RANKX`, operasi string, atau logika kondisional rekursif).

#### Storage Engine (SE)
- **Varian:** VertiPaq (In-Memory Columnar), DirectQuery (Relational SQL/External push-down), atau Direct Lake (Delta Parquet bypass).
- **Karakteristik:** *Multi-threaded*, memanfaatkan instruksi paralel SIMD pada modern superscalar microprocessors.
- **Fungsi:** Menjawab instruksi kueri internal FE yang diekspresikan dalam dialek tingkat rendah bernama **xmSQL**. Mengambil segmen kolom terkompresi, melakukan filter vertikal (*bitmask scan*), dan menjalankan operasi agregasi dasar (`SUM`, `MIN`, `MAX`, `COUNT`, `DISTINCTCOUNT`).

#### Tabular Object Model (TOM)
Struktur objek hirarkis berbasis model metadata (*Database*, *DataSources*, *Tables*, *Partitions*, *Columns*, *Measures*, *Hierarchies*, *Roles*) yang diekspos melalui API kompatibel AMO (Analysis Management Objects) dan direpresentasikan dalam format tekstual JSON sebagai TMSL atau TMDL (*Tabular Model Definition Language*).

---

### 5. The "How"
Siklus kompresi dan eksekusi kueri pada VertiPaq beroperasi melalui fase deterministik berikut:

#### A. Data Ingestion & VertiPaq Compression Pipeline
Saat data di-refresh (melalui Power Query M engine):
1. **Dictionary Encoding:** VertiPaq memindai kolom dan mengekstrak nilai-nilai unik ke dalam kamus data terurut (*zero-based index*). Nilai string/desimal dipetakan ke integer terkecil yang memungkinkan.
2. **Column Partition Allocation:** Data dibagi ke dalam *Data Segments* (secara default per 8 juta baris per segmen data).
3. **Encoding Selection (VertiPaq Hierarchy):**
   - *Value Encoding:* Mengurangi nilai angka dengan konstanta dasar menggunakan formula matematis: 
     $$V' = V - \min(V)$$
     Memungkinkan penyimpanan data numerik murni tanpa kamus tambahan.
   - *Hash Encoding:* Digunakan saat rentang nilai lebar atau tipe non-integer (string, GUID). Dictionary dibuat, nilai asli diganti integer ID kamus.
4. **Run-Length Encoding (RLE):** Mengompresi baris berulang yang berdekatan. Misalnya urutan ID: `1, 1, 1, 2, 2` dienkode menjadi tuple: `(1, 3), (2, 2)` (nilai 1 sebanyak 3 kali, nilai 2 sebanyak 2 kali).
5. **Bit-Packing:** Mengurangi alokasi memori fisik per baris. Jika kamus berisi 4 nilai unik, VertiPaq hanya menggunakan 2 bit per baris ($2^2 = 4$), alih-alih 32-bit (4 byte) atau 64-bit integer standar.

#### B. Query Execution Lifecycle
1. Visual mengirim kueri DAX ke Formula Engine.
2. FE menganalisis DAX, menghasilkan kueri operasional primitif xmSQL.
3. FE mendistribusikan xmSQL ke Storage Engine melintasi banyak thread CPU.
4. SE melakukan agregasi bitwise secara simultan dari cache segmen data terkompresi di RAM.
5. SE mengembalikan *datacache* (tabel sementara uncompressed kecil) ke FE.
6. FE menyatukan hasil dari SE, mengevaluasi konteks filter DAX kompleks tingkat lanjut, dan mengirim hasil akhir (biasanya JSON tabular) kembali ke visual.

---

### 6. ASCII Architecture Diagram

```
+-------------------------------------------------------------------------------+
|                             POWER BI APPLICATION                              |
|   +-----------------------------------------------------------------------+   |
|   |                      Visuals / UI (Client Layer)                      |   |
|   +-----------------------------------------------------------------------+   |
|                                       | (Generates DAX Query)                 |
|                                       v                                       |
|   +-----------------------------------------------------------------------+   |
|   |                         FORMULA ENGINE (FE)                           |   |
|   |  - Single-Threaded Evaluation                                         |   |
|   |  - DAX Parser -> Logical Plan -> Physical Plan Generator              |   |
|   |  - Context Transition & Advanced Functions (e.g. Iterators, RANKX)    |   |
|   +-----------------------------------------------------------------------+   |
|                 |                                           ^                 |
|                 | (xmSQL Internal Query)                    | (DataCaches)    |
|                 v                                           |                 |
|   +-----------------------------------------------------------------------+   |
|   |                         STORAGE ENGINE (SE)                           |   |
|   |  +-----------------------------------------------------------------+  |   |
|   |  |                   VertiPaq Core (Multi-Threaded)                |  |   |
|   |  |  +-----------------------------------------------------------+  |  |   |
|   |  |  | Thread 1 (Core 0) | Thread 2 (Core 1) | Thread N (Core n) |  |  |   |
|   |  |  +-------------------+-------------------+-------------------+  |  |   |
|   |  |  - SIMD Scans         - Filter Bitmasks   - Parallel Hash Join|  |   |
|   |  +-----------------------------------------------------------------+  |   |
|   |                                   |                                   |   |
|   |                                   v                                   |   |
|   |  +-----------------------------------------------------------------+  |   |
|   |  |                 RAM Data Hierarchy (In-Memory)                  |  |   |
|   |  |  +----------------------+ +----------------------------------+  |  |   |
|   |  |  | Column Dictionaries  | | Segments (Default 8M Rows/chunk) |  |  |   |
|   |  |  | [Hash / Value Map]   | | [RLE + Bit-Packed Vector Blocks] |  |  |   |
|   |  |  +----------------------+ +----------------------------------+  |  |   |
|   |  +-----------------------------------------------------------------+  |   |
|   +-----------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------+
```

---

### 7. Minimalist Code/Config Example
Menganalisis metadata struktur internal VertiPaq menggunakan DMV (Dynamic Management Views) melalui DAX Studio atau XMLA Endpoint.

#### Query DMV: Inspeksi Kompresi Kolom dan Dictionary
```sql
-- Mengekstrak metrik fisik segmentasi memory VertiPaq
SELECT 
    [DIMENSION_NAME] AS [Table],
    [COLUMN_NAME] AS [Column],
    [SEGMENT_NUMBER],
    [TABLE_PARTITION_NUMBER],
    [USED_SIZE] AS [SizeBytes],
    [COMPRESSION_TYPE],
    [BITS_COUNT],
    [RECORD_COUNT]
FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMN_SEGMENTS
WHERE [COLUMN_NAME] <> '$RowNumber$'
ORDER BY [USED_SIZE] DESC;
```

#### Query DMV: Inspeksi Kardinalitas dan Dictionary Size
```sql
-- Mengukur memori yang terkonsumsi oleh kamus data (Dictionary)
SELECT 
    [TABLE_ID] AS [Table],
    [COLUMN_ID] AS [Column],
    [DICTIONARY_SIZE] AS [DictionarySizeBytes],
    [DICTIONARY_ENTRIES] AS [Cardinality]
FROM $SYSTEM.DISCOVER_STORAGE_TABLE_COLUMNS
WHERE [DICTIONARY_ENTRIES] > 0
ORDER BY [DICTIONARY_SIZE] DESC;
```

---

### 8. Production-Grade Implementation
Skenario: Pembangunan Model Semantik Enterprise Skala 20 Juta Baris (*FactInternetSales*) menggunakan Tabular Model Definition Language (TMDL) melalui Tabular Editor 3, menerapkan kontrol partisi, enkoding eksplisit, dan isolasi *columnar dictionary*.

#### Definisi Tabel TMDL (`Tables/FactInternetSales.tmdl`)
```tmdl
table FactInternetSales
	lineageTag: 7a82c619-21ef-4235-859a-df9c1db884b2

	partition FactInternetSales-2023 = m
		mode: import
		source = 
			let
			    Source = Sql.Database("tcp:sql-ent-dw.database.windows.net", "DW_Production"),
			    Data = Source{[Schema="dw", Item="FactInternetSales"]}[Data],
			    FilteredRows = Table.SelectRows(Data, each [OrderDateKey] >= 20230101 and [OrderDateKey] <= 20231231)
			in
			    FilteredRows

	column SalesOrderNumber
		dataType: string
		sourceColumn: SalesOrderNumber
		summarizeBy: none
		sourceProviderType: varchar(20)
		// Matikan Hierarki Default untuk Menghemat Struktur B-Tree
		dataCategory: Uncategorized
		isAvailableInMdx: false
		columnStorage:
			encodingHint: hash

	column OrderDateKey
		dataType: int64
		sourceColumn: OrderDateKey
		summarizeBy: none
		columnStorage:
			encodingHint: value // Optimasi Value-Encoding: Eliminasi hash dictionary RAM

	column SalesAmount
		dataType: decimal
		sourceColumn: SalesAmount
		summarizeBy: sum
		formatString: \$#,0.00;(\$#,0.00);\$#,0.00
		columnStorage:
			encodingHint: value

	measure 'Total Revenue' = 
		CALCULATE(
			SUM(FactInternetSales[SalesAmount]),
			KEEPFILTERS(FactInternetSales[SalesAmount] > 0)
		)
		formatString = \$#,0.00
		displayFolder: KPIs
```

#### Trace Analisis xmSQL (Dihasilkan saat visual memanggil measure `[Total Revenue]`)
```sql
-- Storage Engine xmSQL Query execution scan
-- Diekstrak via DAX Studio Server Timings
DEFINE
    MEASURE FactInternetSales[Total Revenue] = 
        CALCULATE(
            SUM(FactInternetSales[SalesAmount]),
            FactInternetSales[SalesAmount] > 0
        )
EVALUATE
    SUMMARIZECOLUMNS(
        'FactInternetSales'[OrderDateKey],
        "Total Revenue", [Total Revenue]
    )

// Terjemahan internal ke xmSQL (SE Scan):
// VertiPaq mengeksekusi multi-core scan langsung pada bit-packed vector:
SELECT 
    'FactInternetSales'[OrderDateKey], 
    SUM ( 'FactInternetSales'[SalesAmount] )
FROM 'FactInternetSales'
WHERE 
    'FactInternetSales'[SalesAmount] > 0.0000;
```

---

### 9. Trade-offs & Alternatives

| Dimensi Arsitektural | Import Mode (VertiPaq) | DirectQuery | Direct Lake (Fabric Synapse) | Composite Models |
| :--- | :--- | :--- | :--- | :--- |
| **Penyimpanan Data** | Salinan data penuh dalam RAM server Analysis Services. | Tetap di source relational database (RDBMS). | File Delta Parquet di OneLake (dimuat on-demand ke RAM). | Campuran VertiPaq dan DirectQuery. |
| **Kecepatan Kueri** | **Sub-detik (Optimal)** via pemindaian columnar memory. | Tergantung beban & indexing source engine (Sering lambat). | Hampir setara Import Mode (bypasses Power Query layer). | Bervariasi; bottleneck pada persilangan kueri FE. |
| **Batas Volume Data** | Dibatasi kapasitas RAM instance (e.g. 25-400 GB SKU PBI). | Terbatas pada kapasitas fisik source RDBMS (Terabyte+). | Skala multi-terabyte tanpa batas RAM Import konvensional. | Fleksibel: Data agregasi di RAM, data detail di DQ. |
| **Latensi Data** | Memerlukan Scheduled/Incremental Refresh. | **Real-Time mutlak** (kueri dialihkan saat interaksi). | Nyaris real-time via V-Order Delta logs ingestion. | Dual-state: Sebagian real-time, sebagian batch. |
| **Dukungan Fungsi DAX**| 100% Dukungan fungsi (FE + SE). | Sangat terbatas (bergantung pada translasi dialek native SQL). | Dukungan hampir 100% (bila tidak jatuh kembali ke DQ). | 100% Dukungan (kalkulasi antar model dievaluasi oleh FE). |

---

### 10. Anti-patterns & Edge Cases

#### Anti-Pattern 1: Menyertakan Stempel Waktu Berkardinalitas Tinggi (High-Cardinality DateTime)
```dax
-- BURUK: Menyimpan DateTime gabungan hingga tingkat milidetik
[TransactionTimestamp] -> "2023-11-21 14:32:01.423" 
-- Efek: Jutaan nilai unik -> Ukuran Dictionary membengkak hingga ratusan MB, RLE gagal total.

-- BENAR: Pisahkan menjadi 2 kolom diskrit di level Transformasi Power Query
[TransactionDate] -> 2023-11-21 (Date, kardinalitas rendah, kompresi tinggi)
[TransactionTime] -> 14:32 (Time, dibulatkan ke menit atau jam, kardinalitas maksimal 1.440 unik)
```

#### Anti-Pattern 2: Surrogate Key / GUID sebagai Tipe Data String
Menggunakan GUID `(e.g. "4a8c9b20-6d33-4f93-bc42-df2e5b721e90")` berukuran 36 karakter pada tabel fakta. VertiPaq dipaksa membuat *hash dictionary* masif. Jika kolom tersebut tidak terhubung ke relasi aktif atau visual, ini membuang kapasitas RAM. Hapus surrogate keys dari tabel fakta jika kunci natural terikat relasi atau gunakan integer mapping via Hash surrogate sequence.

---

### 11. Debugging & Diagnostics
Untuk menganalisis performa mesin antara Formula Engine dan Storage Engine, gunakan **DAX Studio** dengan mengaktifkan fitur **Server Timings**.

#### Mengurai Metrik Server Timings:
1. **Total Duration:** Total waktu dari visual request hingga completion.
2. **Formula Engine (FE) Duration:** Waktu evaluasi single-thread. Jika **FE > 30%** dari total waktu eksekusi, DAX Anda mengalami inefisiensi arsitektural (misalnya: eksekusi iterasi baris yang berlebihan via `FILTER()`, `EARLIER()`, atau penggunaan kalkulasi skalar berulang).
3. **Storage Engine (SE) Duration:** Waktu yang dihabiskan untuk VertiPaq memindai data fisik. Multi-threading diukur dengan membandingkan **SE CPU** terhadap **SE Duration**.
   $$\text{Paralelisme SE} = \frac{\text{SE CPU}}{\text{SE Duration}}$$
   Jika nilai mendekati jumlah core CPU mesin Anda (misal: 8x pada CPU 8-Core), kompresi dan paralelisasi berjalan optimal.
4. **xmSQL Trace Analysis:** Periksa query trace. Jika xmSQL menghasilkan flag `CallbackDataID`, ini adalah indikator kritis bahwa Storage Engine tidak dapat memproses kalkulasi secara native dan terpaksa memanggil Formula Engine berulang-ulang untuk setiap baris data (*Row-by-Row Context switch*), yang merusak skalabilitas kueri.

---

### 12. Performance & Optimization

Gunakan metrik matematis keterurutan data (*Sorting Order*) untuk memaksimalkan Run-Length Encoding (RLE). RLE mengompresi urutan nilai identik berulang.

#### Strategi Pengurutan Data ETL:
Jika sebuah tabel memiliki kolom:
- `Country` (Kardinalitas: 10)
- `State` (Kardinalitas: 200)
- `City` (Kardinalitas: 15.000)

**Instruksi ETL (SQL Source):**
```sql
SELECT Country, State, City, SalesAmount
FROM dbo.FactSales
ORDER BY Country ASC, State ASC, City ASC; -- Mengelompokkan blok memori identik
```
Dengan mengurutkan data fisik berdasarkan kolom dengan kardinalitas terendah terlebih dahulu sebelum diimpor oleh VertiPaq, panjang *run-length* kolom `Country` dan `State` bernilai jutaan baris kontinu, mereduksi konsumsi bit vector hingga lebih dari **85%**.

---

### 13. Security & Governance
Pada level mesin Tabular, Row-Level Security (RLS) dan Object-Level Security (OLS) diatur dalam metadata model semantik dan dieksekusi langsung oleh Formula Engine sebelum filter context diterjemahkan ke Storage Engine.

#### Definisi Metadata TMSL Role Keamanan:
```json
{
  "name": "Finance_EU_Restricted",
  "modelPermission": "read",
  "tablePermissions": [
    {
      "name": "FactInternetSales",
      "filterExpression": "FactInternetSales[SalesTerritoryGroup] = \"Europe\""
    },
    {
      "name": "DimPayroll",
      "metadataPermission": "none" // OLS: Kolom dan Tabel disembunyikan total dari skema metadata kueri
    }
  ]
}
```
*Catatan Keamanan:* Penerapan RLS dinamis menggunakan `USERPRINCIPALNAME()` memaksa Formula Engine menyuntikkan filter predikat tambahan ke setiap blok kueri xmSQL, yang menonaktifkan pemanfaatan global Storage Engine datacache antarpengguna berbeda.

---

### 14. Hardware / System Considerations
- **Memory Subsystem (RAM Channels):** VertiPaq adalah sistem in-memory compute-heavy. Bandwidth memori adalah penentu kecepatan pemindaian utama. Server atau workstation dengan arsitektur Quad-Channel atau Octa-Channel DDR4/DDR5 memberikan Throughput agregasi 2x-4x lebih cepat dibanding konfigurasi Dual-Channel, terlepas dari clock speed CPU.
- **CPU L3 Cache Size:** Cache L3 CPU yang besar (misalnya: AMD EPYC dengan 3D V-Cache atau Intel Xeon Max) memungkinkan segmen kamus VertiPaq tetap berada di cache silikon tanpa harus memanggil *bus* DRAM utama, mereduksi latency pemrosesan baris.
- **Non-Uniform Memory Access (NUMA):** Model VertiPaq berukuran masif di SSAS/Power BI Premium dapat mengalami penurunan efisiensi jika *thread* SE pada Node NUMA 1 mengakses alokasi memori yang berada di kontroler memori fisik Node NUMA 0. Atur afinitas NUMA node BIOS dan sesuaikan ukuran partisi dengan batas per-node RAM.

---

### 15. Ecosystem Integration
Pengembangan model enterprise modern tidak bergantung pada GUI Power BI Desktop:

```
[ Git Repository / Azure DevOps ]
               |
               v (TMDL/TMSL scripts)
    [ Tabular Editor 3 ] <------- (Schema manipulation via TOM API)
               |
               v (XMLA Read/Write Endpoint)
[ Power BI Service Premium / Fabric Capacity ]
               ^
               | (Port 5XXXX Ad-hoc Profiling)
       [ DAX Studio ]
```

1. **Tabular Editor 3:** Mengakses langsung Tabular Object Model (TOM) untuk modifikasi partisi, metadata translation, dan pembuatan calculation groups tanpa memuat visual layer.
2. **ALM Toolkit:** Melakukan pembandingan skema model (*Schema Comparison*), validasi diff antar partisi, dan *incremental metadata deployment* melalui XMLA Read/Write endpoints.
3. **DAX Studio:** Menghubungkan engine instance melalui port lokal Analysis Services yang dihasilkan secara acak oleh Power BI Desktop untuk trace event diagnostik.

---

### 16. Failure Modes & Recovery

#### Kegagalan: Out-Of-Memory (OOM) Selama Refresh
- **Akar Masalah:** VertiPaq memproses refresh tabel secara transaksional (*ACID compliance*). Struktur data lama ditahan di RAM sementara segmen data baru dikompresi dan dibangun secara terpisah di RAM. Memori yang dibutuhkan saat refresh puncak adalah:
  $$\text{RAM}_{\text{peak}} \approx \text{Ukuran Model Aktif} + \text{Ukuran Model Baru} + \text{Overhead Dictionary Engine}$$
- **Mitigasi:**
  1. Jangan refresh semua tabel secara serentak; bagi pipeline refresh menggunakan TMSL sequence scripts.
  2. Implementasikan *Incremental Refresh* berbasis partisi range tanggal, sehingga VertiPaq hanya memproses dan mengompresi ulang partisi data historis yang berubah (*hot partition*), membiarkan partisi *cold data* tidak tersentuh di memori.

---

### 17. Testing & Verification
Otomasi validasi kesehatan arsitektur internal model menggunakan script PowerShell dan modul `Microsoft.AnalysisServices.Tabular`.

#### Verifikasi Model Health Script:
```powershell
# Script untuk mengevaluasi ukuran tabel dan kardinalitas kolom bermasalah
# Membutuhkan modul AMO/TOM
[System.Reflection.Assembly]::LoadWithPartialName("Microsoft.AnalysisServices.Tabular") | Out-Null

$ServerConnection = "Provider=MSOLAP;Data Source=localhost:51234;" # Ganti port Desktop aktif
$Server = New-Object Microsoft.AnalysisServices.Tabular.Server
$Server.Connect($ServerConnection)

$Database = $Server.Databases[0]
Write-Host "Model Analyzed: " $Database.Name

foreach ($table in $Database.Model.Tables) {
    Write-Host "Table: $($table.Name)"
    foreach ($col in $table.Columns) {
        # Validasi Kolom dengan Kardinalitas Ekstrem yang berpotensi merusak VertiPaq
        # Mengambil referensi via DMV internal
    }
}
$Server.Disconnect()
```

---

### 18. Real-world Operational Playbook

#### Triage Playbook: Degradasi Respon Visual Laporan (> 10 Detik)

```
[Laporan Lambat Dilaporkan]
         |
         v
[Buka DAX Studio -> Hubungkan ke Report -> Aktifkan Server Timings]
         |
         v
[Jalankan Kueri DAX Visual yang Bermasalah]
         |
         +---------------------------------------+
         |                                       |
    [FE % > 50%]                            [SE % > 80%]
         |                                       |
         v                                       v
[Bottleneck: Formula Engine]            [Bottleneck: Storage Engine]
- Evaluasi penggunaan fungsi iterasi    - Buka VertiPaq Analyzer
  (SUMX, FILTER, ADDCOLUMNS)            - Cek ukuran kolom memori terbesar
- Cari 'CallbackDataID' di xmSQL        - Identifikasi kolom kardinalitas tinggi
- Konversi iterasi baris ke Boolean     - Hapus kolom presisi tinggi/GUID
  relational filter natif               - Pastikan Value Encoding aktif
                                        - Tinjau partisi fisik tabel
```

---

### 19. Key Takeaways
- VertiPaq adalah *columnar in-memory analytical engine* yang performanya sangat ditentukan oleh kompresi bit-packing dan dictionary encoding.
- Formula Engine bersifat *single-threaded* dan menangani kalkulasi kompleks; Storage Engine bersifat *multi-threaded*, memproses agregasi data terkompresi menggunakan *xmSQL*.
- Kunci penghematan memori dan kecepatan kueri bergantung pada kardinalitas kolom (*number of unique values*), bukan jumlah baris data secara absolut.
- Kehadiran `CallbackDataID` dalam eksekusi xmSQL menandakan fallback performa dari SE ke FE yang harus dihilangkan.

---

### 20. Next Step Prerequisites
Sebelum melanjutkan ke **Bab 01 Module 02: Logika Komputasi DAX Lanjutan (Filter Context, Evaluation Context Transitions, dan Iterators)**, pastikan Anda telah:
1. Memasang **DAX Studio** versi terbaru (v3.x+) dan **Tabular Editor 2/3**.
2. Memahami konsep relasi skema bintang (*Star Schema* vs *Snowflake Schema*).
3. Menyiapkan database sampel *AdventureWorksDW* atau dataset transaksional dengan minimal 1 juta baris untuk evaluasi *Server Timings* secara langsung.