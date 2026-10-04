# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: DAX Core, Evaluation Contexts & Engine Internals**  
**Kategori: 08-AI-Data-and-Autonomous-Agents (Power BI Track)**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Data Platform Engineer, BI Architect, dan Enterprise Analytics Developer diharapkan mampu:

1. **Membongkar Eksekusi DAX ke Level Mesin**: Membedah pemisahan beban kerja antara *Formula Engine* (FE) dan *Storage Engine* (SE/VertiPaq), serta mengidentifikasi pembentukan kueri internal *xmSQL*.
2. **Mengeliminasi *Performance Anti-Patterns***: Mendeteksi dan melenyapkan eksekusi *CallbackDataID* yang membebani komputasi *row-by-row* pada Formula Engine yang beroperasi secara *single-threaded*.
3. **Menguasai Arsitektur Evaluasi Tingkat Lanjut**: Mengimplementasikan manipulasi *Filter Context* kompleks, *Expanded Tables Mechanics*, serta *Context Transition* multi-level tanpa menimbulkan *side-effect memory explosion* (*materialization overhead*).
4. **Merancang Pola DAX Skala Enterprise**: Membangun kalkulasi analitik tingkat tinggi meliputi *Dynamic Currency Conversion*, *Semi-Additive Balance Sheet Accumulations*, serta *Arbitrary-shaped Security Filtering*.
5. **Melakukan Profiling dan Diagnostik Presisi**: Menggunakan *DAX Studio Server Timings* dan *Execution Metrics* untuk memangkas *Query Duration*, rasio *SE CPU / SE Duration*, serta konsumsi RAM pada dataset berukuran 100M+ baris.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, praktisi wajib menguasai kompetensi dasar berikut:
* **Pemahaman DAX Fundamental**: Memahami sintaks dasar `CALCULATE`, `FILTER`, `ALL`, `VALUES`, `SUMX`, dan relasi antartabel.
* **Dasar Relational & Dimensional Modeling**: Pemahaman tentang Star Schema, kardinalitas relasi ($1:N$, $N:M$), *active vs inactive relationships*, dan arah *cross-filtering*.
* **Tools Lingkungan Kerja**: Power BI Desktop (rilis modern) terinstal bersama **DAX Studio** (v3.x+) dan **Tabular Editor 2/3**.
* **Aljabar Relasional**: Logika operasi himpunan (*Cartesian product*, *projection*, *set difference*, dan *semi-join*).

---

## 3. Concept & Internal Architecture (Mendalam)

Arsitektur evaluasi Power BI Tabular Engine (VertiPaq) bersandar pada dua subsistem utama yang bekerja secara orkestratif: **Formula Engine (FE)** dan **Storage Engine (SE)**.

```
                              +-------------------------+
                              |   Client Visual Query   |
                              +------------+------------+
                                           |
                                           v
                              +-------------------------+
                              |     Formula Engine      |
                              |   (Single-Threaded,     |
                              |    Parse, Plan, Logic)  |
                              +------------+------------+
                                           |
                    +----------------------+----------------------+
                    | (xmSQL Batches)                             | (DirectQuery SQL)
                    v                                             v
     +------------------------------+              +------------------------------+
     |   Storage Engine (VertiPaq)  |              |    Storage Engine (RDBMS)    |
     |   (Multi-Threaded, In-Memory,|              |   (External DirectQuery/     |
     |    RLE, Bit-Packed, Columnar)|              |    Direct Lake Fabric)       |
     +--------------+---------------+              +--------------+---------------+
                    |                                             |
                    +----------------------+----------------------+
                                           |
                                           v
                              +-------------------------+
                              |     Data Cache (RAM)    |
                              | (Uncompressed Intermed.)|
                              +------------+------------+
                                           |
                                           v
                              +-------------------------+
                              | FE Aggregation / Output |
                              +-------------------------+
```

### 3.1. Formula Engine (FE) vs. Storage Engine (SE)

* **Formula Engine (FE)**:
  * Bertindak sebagai otak pengendali kueri. Ditulis menggunakan C++, mengeksekusi logika tingkat tinggi: parsing ekspresi DAX, membuat pohon eksekusi (*Logical & Physical Execution Plans*), menangani fungsi non-komputasional matriks (seperti format teks, waktu, fungsi kondisional rumit `IF`/`SWITCH` non-pushed), dan memanggil Storage Engine.
  * **Karakteristik Kritis**: Bersifat **single-threaded** per kueri pengguna. Ketika FE memproses komputasi data besar secara mandiri, performa kueri mengalami degradasi drastis.
* **Storage Engine (SE)**:
  * Mesin komputasi data fisik. Pada mode *Import*, SE adalah **VertiPaq Engine**. Pada mode *DirectQuery*, SE bertindak sebagai translator ke SQL/T-SQL target.
  * **Karakteristik Kritis**: Bersifat **massively multi-threaded**, beroperasi langsung di atas data terkompresi berbasis kolom (*in-memory columnar database*). SE memindai miliaran baris dalam hitungan milidetik melalui instruksi prosesor modern (SIMD, vektorisasi CPU). SE menerima perintah dari FE dalam dialek internal bernama **xmSQL**.

### 3.2. VertiPaq In-Memory Data Structures

VertiPaq mengoptimalkan jejak memori dan pemindaian data menggunakan 3 lapisan kompresi:
1. **Dictionary Encoding**: Mengganti string atau nilai arbitrer dengan integer ID berurutan berbasis kardinalitas. Ukuran bit ditentukan oleh $\lceil\log_2(Kardinalitas)\rceil$.
2. **Run-Length Encoding (RLE)**: Menyimpan pasangan `(Value_ID, Count)`. Sangat efektif jika data terurut, meminimalkan baris duplikat yang berturutan.
3. **Bit-Packing**: Mengompresi penyimpanan array integer ID ke tingkat bit presisi minimum tanpa *padding* byte standar.

### 3.3. xmSQL dan SE Cache

Ketika FE mengevaluasi fungsi seperti `CALCULATE(SUM(Sales[Amount]), Customers[Country] = "ID")`, FE tidak membaca baris tabel secara mandiri. FE menyusun instruksi **xmSQL**:

```sql
SELECT 
    Customers[Country], 
    SUM(Sales[Amount])
FROM Sales
    NATURAL LEFT OUTER JOIN Customers
WHERE 
    Customers[Country] = 'ID';
```

Storage Engine memproses kueri ini secara multi-threaded, mengekstrak data dari kolom terkompresi, mengagregasikannya di tingkat perangkat keras, lalu mengembalikan hasilnya ke FE dalam struktur tabel memori sementara yang disebut **Data Cache**.

Jika kueri yang sama atau subset yang kompatibel diminta kembali, SE memanfaatkan **Storage Engine Cache** tanpa membaca ulang struktur kolom fisik.

### 3.4. The Silent Performance Killer: CallbackDataID

Kondisi `CallbackDataID` muncul ketika sebuah ekspresi di dalam fungsi iterator (`SUMX`, `AVERAGEX`, `FILTER`, dsb.) atau predikat `CALCULATE` mengandung kalkulasi yang **tidak dapat diterjemahkan ke dalam operator primitif VertiPaq xmSQL**. 

Akibatnya:
1. SE memulai *scan* multithreaded.
2. Setiap kali SE menemukan baris data, SE harus menghentikan thread kompresinya dan melakukan pemanggilan balik (*callback*) ke Formula Engine untuk mengevaluasi baris tersebut secara individual.
3. Arsitektur beralih dari multi-threaded vektorisasi berkecepatan 10 GB/s menjadi loop sekuensial *single-threaded* berbasis CPU FE. Durasi kueri meningkat secara eksponensial.

### 3.5. Expanded Tables Mechanics dan Context Transition

Konsep dasar yang mendasari integritas relasional DAX adalah **Expanded Table**:
* Setiap tabel di sisi *one* dari relasi $1:N$ secara konseptual "diperluas" (*expanded*) ke dalam tabel sisi *many*.
* Saat filter diaplikasikan ke tabel anak (`Sales`), filter tersebut mengalir ke tabel `Sales` saja. Namun, saat filter diaplikasikan ke tabel induk (`Products`), filter secara otomatis membatasi baris pada tabel `Sales` karena ekspansi tabel menyertakan seluruh kolom tabel induk ke dalam definisi relasional tabel transaksi.
* **Context Transition**: Transformasi dari *Row Context* menjadi *Filter Context* yang setara. Terjadi secara otomatis saat memanggil ekspresi terukur (`Measure`) di dalam iterator, atau secara eksplisit melalui sintaks `CALCULATE()`.
  
  $$\text{Row Context} \xrightarrow{\quad\text{CALCULATE}()\quad} \text{Filter Context equivalent to all column values of current row}$$

Jika diterapkan di atas tabel berukuran $10^7$ baris tanpa filter selektif, ekspansi memori (*materialization*) akan menghabiskan ruang alokasi RAM server (Analysis Services Memory Limit Error).

---

## 4. Why & What

| Dimensi | Mengapa Ini Penting (*Why*) | Apa Konsep/Teknologinya (*What*) |
| :--- | :--- | :--- |
| **SLA Responsivitas Visual** | Visual dashboard enterprise dituntut merespons dalam < 1.000 ms pada volume ratusan juta baris transaksi. Pendekatan kalkulasi naif menghasilkan query time > 30 detik. | Penataan alur kerja DAX agar 90%+ beban dialokasikan ke VertiPaq Storage Engine (multi-threaded parallelism). |
| **Efisiensi Alokasi Memori** | Mengurangi biaya kapasitas Fabric SKU / Power BI Premium P-SKU. Formula Engine yang boros akan menyebabkan alokasi *Spool Materialization* yang masif di RAM. | Penghindaran *high-cardinality materialization* dan eliminasi transisi konteks non-deterministik pada iterator tabel besar. |
| **Akurasi Bisnis Lanjutan** | Logika pelaporan finansial dan inventory tidak bersifat aditif murni (misal: saldo kas akhir bulan tidak bisa di-`SUM`). | Penerapan kalkulasi *Semi-Additive*, penanganan *Matrix Sparsity*, dan manajemen granularitas waktu via *Expanded Tables*. |

---

## 5. How (Workflow Detail)

Alur kerja eksekusi analitik end-to-end dari visualisasi pengguna hingga rendering akhir:

```
[Visual Interaction: Klik Slicer / Filter Matrix]
                       |
                       v
[Power BI Frontend Query Generator: Membuat DAX Query]
                       |
                       v
[FE: DAX Parser & Semantic Analyzer]
                       |
                       v
[FE: Logical Query Plan Optimization]
                       |
                       v
[FE: Physical Query Plan Compilation]
                       |
       +---------------+---------------+
       |                               |
 (Perlu SE Scan?)                (Hasil Instan/Konstan?)
       |                               |
      Ya                              Tidak
       |                               |
       v                               v
[FE Mengirim Batch xmSQL ke SE]   [FE Mengembalikan Hasil]
       |                               |
       v                               v
[SE: Eksekusi Multi-Threaded Core]     +-----> [Visual Rendering Engine]
       |
  (Ada CallbackDataID?)
    /             \
   Ya             Tidak
  /                 \
 [SE Callback        [SE Membaca Kolom Terkompresi,
  ke FE per baris]    Agregasi Vektor via SIMD]
  |                   |
  +--------->+<-------+
             |
             v
 [SE Mengembalikan Uncompressed Data Cache ke FE]
             |
             v
 [FE Mengonsolidasi Hash Table, Join, Menghitung Ekspresi FE]
             |
             v
 [FE Mengirim Result Set ke Frontend Engine]
```

### Tahapan Detail Eksekusi:
1. **Penerimaan Query**: Dashboard mengeksekusi kueri DAX berbasis `EVALUATE SUMMARIZECOLUMNS(...)`.
2. **Kompilasi Rencana Eksekusi**: FE membuat pohon operator. Node seperti `Spool_Lookup`, `CrossJoin`, dan `Scan` dianalisis untuk menentukan rute eksekusi termurah.
3. **Generasi xmSQL**: SE Query Optimizer menyusun string perintah xmSQL. Variabel yang statis diisolasi sebagai parameter konstanta.
4. **Penyapuan VertiPaq**: Utilitas multi-core memindai segmen-segmen memori terkompresi secara serentak. Jika satu segmen berisi 8 juta baris, 8 core CPU dapat memindai 64 juta baris secara simultan.
5. **Penanganan Intermediate Cache**: Data Cache yang dikembalikan ke FE diformat dalam struktur tabular tereduksi (*grouped and aggregated*).
6. **Final Assembly**: FE memproses langkah non-SE (seperti pembagian akhir pada *margin ratio* atau format string dinamis) dan mendistribusikan JSON result set ke antarmuka pengguna.

---

## 6. Analogy & Diagram ASCII

### Analogi: Manajer Restoran (FE) dan Pasukan Koki Pemotong Bahan (SE)

Bayangkan sebuah dapur restoran skala industri:
* **Storage Engine (SE)** adalah pasukan 16 koki pemotong bahan di gudang pendingin. Mereka sangat cepat memotong 100.000 bawang atau kentang, asalkan instruksinya sederhana: *"Potong semua bawang merah dari karung A, timbang total beratnya, buang kulitnya."* Pekerjaan ini dapat diparalelkan tanpa perlu berpikir kreatif.
* **Formula Engine (FE)** adalah Kepala Koki (*Executive Chef*). Dia bekerja sendirian (*single-threaded*). Dia merancang menu, mencampur saus khusus berformula rahasia, dan menyusun makanan di piring saji (*plating*).
* **CallbackDataID** terjadi jika Kepala Koki berkata ke para koki pemotong: *"Potong kentang itu, tapi setiap kali kalian selesai memotong satu irisan, bawa irisan itu ke saya ke dapur depan. Biarkan saya mencicipi rasanya dulu apakah sesuai dengan resep nenek saya, baru kalian boleh potong irisan kedua."* Hasilnya: Pasukan koki berhenti bekerja paralel, gudang menjadi macet, dan pesanan pelanggan tertunda lama.

```
OPERASI NORMAL (SEPARATED ROLES - OPTIMAL)
+-------------------------------------------------------+
| VertiPaq SE (16 Threads):                             |
| Scan [Qty] * [Price] WHERE Year = 2024                |
| [Thread 1] ===> 10M rows                              |
| [Thread 2] ===> 10M rows  --> Total = 400M            |
| [Thread 3] ===> 10M rows      (Direct Data Cache)     |
| [Thread 4] ===> 10M rows                              |
+---------------------------+---------------------------+
                            | Kirim Total 1 Baris
                            v
+-------------------------------------------------------+
| Formula Engine:                                       |
| Terima Total (400M) / Total Budget -> Final Output    |
+-------------------------------------------------------+

OPERASI DENGAN CALLBACKDATAID (DEGRADASI PERFORMA)
+-------------------------------------------------------+
| VertiPaq SE (Thread Terblokir Menunggu Respon FE):    |
| Ambil Row 1 -> Minta FE Evaluasi Logika Kompleks      |
+---------------------------+---------------------------+
                            | Interupsi Context
                            v
+-------------------------------------------------------+
| Formula Engine (Single-Threaded):                     |
| Evaluasi Row 1 -> Kembalikan Hasil ke SE              |
+---------------------------+---------------------------+
                            | Respon
                            v
+-------------------------------------------------------+
| VertiPaq SE:                                          |
| Ambil Row 2 -> Minta FE Evaluasi... (x 100M Rows!)    |
+-------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Anti-Pattern vs. Optimized Pattern: CallbackDataID Elimination

Skenario: Menghitung total penjualan hanya untuk transaksi dengan nilai diskon kustom yang ditentukan secara dinamis.

#### Kode Buruk (Memicu CallbackDataID & Operasi FE Masif)
```dax
-- ANTI-PATTERN: Iterasi berulang dengan ekspresi non-sederhana di dalam iterator
-- Menghasilkan CallbackDataID pada xmSQL karena fungsi IF kompleks tidak dapat ditranslasikan ke SE
DefectiveTotalSales := 
SUMX(
    FactInternetSales,
    FactInternetSales[OrderQuantity] * 
    IF(
        RELATED(DimProduct[DealerPrice]) > 500,
        FactInternetSales[UnitPrice] * 0.9,
        FactInternetSales[UnitPrice] * 0.95
    )
)
```

*Diagnosa DAX Studio:*
* SE CPU Duration: 1.200 ms | FE Duration: 8.400 ms.
* xmSQL memunculkan instruksi: `CallbackDataID(DimProduct[DealerPrice]...)`.

#### Kode Optimal (Fully Pushed to Storage Engine)
```dax
-- PRODUCTION PATTERN: Dekonstruksi logika kalkulasi menjadi aditif SE-friendly
OptimizedTotalSales := 
VAR HighPriceSales = 
    CALCULATE(
        SUMX(FactInternetSales, FactInternetSales[OrderQuantity] * FactInternetSales[UnitPrice]) * 0.90,
        DimProduct[DealerPrice] > 500
    )
VAR LowPriceSales = 
    CALCULATE(
        SUMX(FactInternetSales, FactInternetSales[OrderQuantity] * FactInternetSales[UnitPrice]) * 0.95,
        DimProduct[DealerPrice] <= 500
    )
RETURN 
    HighPriceSales + LowPriceSales
```

*Diagnosa DAX Studio:*
* Dua kueri xmSQL bersih dihasilkan, dieksekusi simultan di SE.
* SE CPU Duration: 450 ms | FE Duration: 15 ms. Total eksekusi turun dari ~9 detik menjadi < 100 ms.

---

### 7.2. Practical Example: Robust Dynamic Currency Conversion

Skenario Enterprise: Menghitung metrik sales yang harus dikonversi ke mata uang yang dipilih pengguna via Slicer, mengambil nilai kurs harian (*Daily Spot Rate*), atau menggunakan kurs penutupan terakhir jika tanggal transaksi jatuh pada hari libur bursa (*Non-trading day imputation*).

```dax
TotalSales_Converted := 
VAR SelectedCurrency = SELECTEDVALUE(DimCurrency[CurrencyCode], "USD")
VAR BaseCurrency = "USD"
RETURN
    IF(
        SelectedCurrency = BaseCurrency,
        [BaseTotalSales],
        SUMX(
            -- Granularitas minimal: Kelompokkan berdasarkan tanggal untuk menghindari materialisasi level baris faktur
            SUMMARIZE(
                FactSales,
                DimDate[DateKey]
            ),
            VAR CurrentDateKey = DimDate[DateKey]
            VAR DailyRate = 
                CALCULATE(
                    MAX(FactExchangeRate[EndOfDayRate]),
                    FactExchangeRate[CurrencyCode] = SelectedCurrency,
                    FactExchangeRate[DateKey] = CurrentDateKey
                )
            -- Fallback jika rate pada tanggal spesifik kosong (ambil tanggal transaksi valid terakhir)
            VAR FallbackRate = 
                IF(
                    ISBLANK(DailyRate),
                    CALCULATE(
                        TOPN(
                            1,
                            CALCULATETABLE(
                                FactExchangeRate,
                                FactExchangeRate[CurrencyCode] = SelectedCurrency,
                                FactExchangeRate[DateKey] <= CurrentDateKey,
                                ALL(DimDate)
                            ),
                            FactExchangeRate[DateKey],
                            DESC
                        ),
                        FactExchangeRate[EndOfDayRate]
                    ),
                    DailyRate
                )
            VAR DailySalesBase = [BaseTotalSales]
            RETURN
                DailySalesBase * COALESCE(DailyRate, FallbackRate, 1.0)
        )
    )
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Global Fintech Transaction Engine
* **Dataset**: 180.000.000 baris data ledger transaksi harian (`FactLedger`), 2.500.000 entitas akun pelanggan (`DimAccount`), 10 tahun riwayat tanggal (`DimDate`).
* **Masalah**: Visual matriks pada dashboard monitoring fraud dan likuiditas mengalami *Memory Allocation Failure* atau timeout (30+ detik) ketika pengguna melakukan *drill-down* ke level bulanan.
* **Akar Masalah (Analisis DAX Studio)**:
  1. Pengembang menggunakan `COUNTX(FILTER(FactLedger, ...), ...)` yang memicu materialisasi tabel 180 juta baris di Formula Engine.
  2. Implementasi *Row-Level Security* (RLS) berbasis dynamic user security (`USERPRINCIPALNAME`) diimplementasikan di tabel fakta transaksi, bukan di tabel dimensi.
  3. Terjadi kalkulasi saldo berjalan (*Running Total Balance*) menggunakan filter terbuka `<=' DimDate[Date]`.

### Solusi Arsitektur & Optimasi

```dax
-- IMPLEMENTASI SEBELUMNYA (CRITICAL FAULT)
FaultyRunningBalance := 
SUMX(
    FILTER(
        ALL(FactLedger),
        FactLedger[AccountKey] = SELECTEDVALUE(DimAccount[AccountKey]) &&
        FactLedger[PostingDate] <= MAX(DimDate[FullDate])
    ),
    FactLedger[PostingAmount]
)
```

```dax
-- PRODUCTION-GRADE ARCHITECTURE: Semi-Additive Pre-Aggregated Approach
-- Solusi 1: Menerapkan Filter Context Pushdown melalui Expanded Tables & KEEPFILTERS
ProductionRunningBalance := 
VAR MaxSelectedDate = MAX(DimDate[FullDate])
VAR CurrentAccount = SELECTEDVALUE(DimAccount[AccountKey])
RETURN
    IF(
        ISINSCOPE(DimAccount[AccountKey]),
        -- Evaluasi jika berada di granularitas akun
        CALCULATE(
            SUM(FactLedger[PostingAmount]),
            FILTER(
                ALL(DimDate[FullDate]),
                DimDate[FullDate] <= MaxSelectedDate
            )
        ),
        -- Optimasi granularitas agregat (Total Saldo Tingkat Portofolio)
        SUMX(
            VALUES(DimAccount[AccountKey]),
            CALCULATE(
                SUM(FactLedger[PostingAmount]),
                FILTER(
                    ALL(DimDate[FullDate]),
                    DimDate[FullDate] <= MaxSelectedDate
                )
            )
        )
    )
```

### Hasil Metrik Profiling (Benchmarking)

| Metrik Diagnostik | Implementasi Lama | Optimasi Produksi | Peningkatan |
| :--- | :--- | :--- | :--- |
| **Total Query Duration** | 34.218 ms | 412 ms | **83x Lebih Cepat** |
| **Formula Engine Duration**| 29.800 ms | 28 ms | **1.064x Pengurangan FE**|
| **Storage Engine Duration**| 4.418 ms | 384 ms | **11,5x Peningkatan SE** |
| **SE Queries (Batch)** | 1 (Mengambil masif dump)| 3 (Teragregasi granular) | Efisiensi Alokasi I/O |
| **Storage Engine CPU Net** | 12.800 ms (Throttled) | 3.072 ms (Multi-threaded)| Utilisasi 8-core CPU optimal |
| **Peak Memory Allocation** | 1,48 GB (Out of RAM) | 4,2 MB | **99,7% Penurunan RAM** |

---

## 9. Trade-offs: Architectural Decisions

| Dimensi Pendekatan | Pilihan A | Pilihan B | Analisis Trade-off Arsitektural |
| :--- | :--- | :--- | :--- |
| **Calculated Column vs. Dynamic Measure** | **Calculated Column** *(Data dihitung saat Refresh)* | **DAX Measure** *(Data dihitung runtime saat Visual me-render)* | **Calculated Column**: Memakan RAM fisik, meningkatkan ukuran file `.pbix`, tetapi biaya CPU query time = 0 (karena nilainya sudah terindeks di VertiPaq).<br>**Measure**: Ukuran RAM 0 byte saat rest, kompresi file maksimal, namun mengonsumsi CPU cycle server saat visual diakses oleh ribuan *concurrent users*. |
| **Data Modeling: Snowflake vs. Flat Star Schema** | **Star Schema** *(Denormalized Dimens)* | **Snowflake Schema** *(Highly Normalized)* | **Star Schema**: Optimal untuk VertiPaq. Menghindari operasi *join hop* internal FE. Menghasilkan relasi 1:N langsung yang mudah diproses via *Expanded Tables*.<br>**Snowflake**: Menghemat ruang desain relasional klasik, namun pada VertiPaq justru dapat memperlambat performa SE karena join path yang panjang. |
| **Filtering Paradigm: TREATAS vs. INTERSECT / FILTER** | **TREATAS** *(Virtual Relational Lineage)* | **FILTER(..., RELATED(...))** | **TREATAS**: Menyuntikkan filter context langsung ke *column search tree* VertiPaq tanpa evaluasi baris demi baris. Sangat cepat.<br>**FILTER**: Memaksa materialisasi tabel perantara di FE sebelum pemotongan set data dilakukan. |
| **Evaluation Strategy: Eager vs. Strict Evaluation** | **Strict Evaluation** *(IF standard)* | **Eager Evaluation** *(Coalesce / Math branching)* | Power BI mengoptimalkan percabangan. Pada kasus tertentu, FE mengevaluasi *kedua* cabang nilai `IF` secara spekulatif (*Eager*) sebelum kondisi diputuskan. Memilih restrukturisasi boolean algebra dapat mencegah eksekusi ganda yang memboroskan SE scans. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Common Mistake: Konteks Transisi yang Tidak Disengaja pada Iterasi
* **Pola Kesalahan**: Memanggil Measure kalkulasi dasar (misal `[Total Quantity]`) di dalam sebuah `SUMX` yang melintasi tabel transaksi besar.
```dax
-- SALAH: Memicu jutaan transisi konteks individual
BadMeasure := 
SUMX(
    FactSales, 
    [BasePrice] * FactSales[Quantity] -- BasePrice adalah measure!
)
```
* **Dampak**: `[BasePrice]` membungkus dirinya dengan `CALCULATE()`. Ini memaksa SE melakukan context transition per setiap baris unik tabel `FactSales`. Jika ada 20 juta baris, maka terjadi 20 juta operasi context transition.
* **Koreksi**: Gunakan referensi kolom langsung atau simpan skalar konstanta di luar loop jika nilai tidak berubah.
```dax
-- BENAR: Menggunakan pure row context primitif
CorrectMeasure := 
SUMX(
    FactSales, 
    FactSales[UnitPrice] * FactSales[Quantity]
)
```

### 10.2. Troubleshooting Guide Menggunakan DAX Studio

Jika query dashboard terindikasi lambat:
1. **Buka DAX Studio** $\rightarrow$ Hubungkan ke PBI Desktop session $\rightarrow$ Aktifkan menu **Server Timings**.
2. Centang opsi **Storage Engine (SE)** dan **Formula Engine (FE)**.
3. Jalankan kueri analitik target.
4. **Analisis Output**:
   * **Kasus FE > 50% Total Duration**: Terjadi *CallbackDataID*, penggunaan fungsi teks berlebihan (`CONCATENATEX`), atau iterasi kompleks (`FILTER(ALL(...))`).
     * *Aksi*: Dekonstruksi logika fungsi iterator, gantikan dengan native filters.
   * **Kasus SE CPU / SE Duration $\approx$ 1.0**: VertiPaq tidak berjalan secara paralel (*Single Core Throttling*).
     * *Aksi*: Periksa kardinalitas kolom, hindari relationship bi-directional multi-table.
   * **Pesan "CallbackDataID" muncul di panel xmSQL**:
     * *Aksi*: Identifikasi baris xmSQL tersebut. Periksa ekspresi kondisional `IF`, `DIVIDE`, atau perbandingan floating-point non-kompatibel yang disematkan dalam measure iterator.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis model semantik tabular ke kapasitas Fabric/Premium:

- [ ] **Kardinalitas Kolom Terkendali**: Kolom *ID/Hash Key/Timestamp* berpresisi tinggi telah dipisah menjadi *Date* terpisah dan *Time* terpisah, atau dihapus jika tidak dibutuhkan visual.
- [ ] **Bebas CallbackDataID**: Trace *DAX Studio Server Timings* membuktikan 0 kemunculan *CallbackDataID* pada visual KPI dan Matrix utama.
- [ ] **Rasio Beban Kerja Ideal**: Setidaknya **80% - 90% waktu eksekusi berada di Storage Engine (SE)**, dan durasi Formula Engine (FE) berada di level minimal (< 100 ms).
- [ ] **Tidak Menggunakan Table Filters Utuh di CALCULATE**: Selalu gunakan filter kolom spesifik (`CALCULATE(..., Dim[Col] = "Val")`) bukan filter tabel utuh (`CALCULATE(..., FILTER(Dim, Dim[Col] = "Val"))`), untuk mencegah overhead *Expanded Tables*.
- [ ] **Measure Reference Integrity**: Tidak pernah menyisipkan kalkulasi skalar berbasis Measure di dalam baris *Fact-level iterator* tanpa membatasi set data terlebih dahulu via `SUMMARIZE`/`VALUES`.
- [ ] **Penggunaan DIVIDE Ketimbang Slash Operator**: Menggunakan native safe function `DIVIDE(Numerator, Denominator, AlternateResult)` untuk mengeliminasi error *divide-by-zero* yang memaksa fallback penanganan exception di FE.
- [ ] **Penggunaan KEEPFILTERS pada Konteks Luar**: Mempertahankan filter asli pengguna saat memodifikasi Filter Context via `CALCULATE` agar tidak menimpa slice dimensi yang sah secara tidak sengaja.
- [ ] **Star Schema Enforcement**: Memastikan model tabular sepenuhnya Star Schema; hindari *Bi-directional Cross-filtering* pada relasi berkardinalitas tinggi ($M:N$).

---

## 12. Hands-on Practice

Simpan seluruh skrip uji pada direktori: `hands-on/m02/`

### Kasus Praktikum: Mengidentifikasi dan Memusnahkan CallbackDataID

#### Langkah 1: Persiapan Environment
1. Buka Power BI Desktop dengan dataset ritel sampel (misal: *AdventureWorks DW* atau *Contoso Retail*).
2. Hubungkan **DAX Studio** ke instance model lokal Anda.
3. Buat file baru di path: `hands-on/m02/01_bottleneck_profiling.dax`.

#### Langkah 2: Menjalankan Baseline Query Bermasalah
Tulis skrip berikut pada editor DAX Studio:

```dax
-- hands-on/m02/01_bottleneck_profiling.dax
-- EVALUASI BASELINE: Measure dengan CallbackDataID eksplisit

DEFINE
    MEASURE FactOnlineSales[DefectiveLineProfit] = 
        SUMX(
            FactOnlineSales,
            FactOnlineSales[SalesQuantity] * (
                FactOnlineSales[UnitPrice] - 
                -- Logika bersyarat yang memaksa SE callback ke FE
                IF(
                    RELATED(DimProductCategory[ProductCategoryKey]) = 1,
                    FactOnlineSales[UnitCost] * 1.1,
                    FactOnlineSales[UnitCost] * 1.05
                )
            )
        )

EVALUATE
SUMMARIZECOLUMNS(
    DimDate[CalendarYear],
    "TotalLineProfit", [DefectiveLineProfit]
)
```

#### Langkah 3: Profiling Hasil
1. Aktifkan tab **Server Timings** di DAX Studio.
2. Klik **Run** (F5).
3. Buka tab Server Timings di bagian bawah.
4. **Catat Temuan Anda**:
   * Amati teks merah/oranye pada *Scan details*. Cari teks: `Line matching: CallbackDataID(...)`.
   * Catat rasio `FE Duration` vs `SE Duration`.

#### Langkah 4: Rekayasa Ulang Menggunakan SE Pushdown Pattern
Buat file baru di path: `hands-on/m02/02_optimized_pushdown.dax`:

```dax
-- hands-on/m02/02_optimized_pushdown.dax
-- EVALUASI REFACTOR: Mengeliminasi callback dengan pemisahan predikat SE murni

DEFINE
    MEASURE FactOnlineSales[RefactoredLineProfit] = 
        VAR CostCategory1 = 
            CALCULATE(
                SUMX(
                    FactOnlineSales,
                    FactOnlineSales[SalesQuantity] * (FactOnlineSales[UnitPrice] - (FactOnlineSales[UnitCost] * 1.1))
                ),
                DimProductCategory[ProductCategoryKey] = 1
            )
        VAR CostCategoryOther = 
            CALCULATE(
                SUMX(
                    FactOnlineSales,
                    FactOnlineSales[SalesQuantity] * (FactOnlineSales[UnitPrice] - (FactOnlineSales[UnitCost] * 1.05))
                ),
                DimProductCategory[ProductCategoryKey] <> 1
            )
        RETURN
            CostCategory1 + CostCategoryOther

EVALUATE
SUMMARIZECOLUMNS(
    DimDate[CalendarYear],
    "TotalLineProfit", [RefactoredLineProfit]
)
```

#### Langkah 5: Validasi Akhir
Jalankan skrip refactor tersebut di DAX Studio. Pastikan pada panel Server Timings:
* Teks `CallbackDataID` **lenyap 100%**.
* Waktu total eksekusi berkurang secara signifikan.

---

## 13. Exercises

### Level Easy
Terdapat ekspresi DAX:
```dax
CustomerCount := COUNTROWS(FILTER(DimCustomer, DimCustomer[YearlyIncome] > 50000))
```
Tulis ulang kode di atas menjadi bentuk yang lebih optimal menggunakan `CALCULATE` dan native column filter. Jelaskan mengapa bentuk baru tersebut lebih cepat dieksekusi oleh VertiPaq.

```dax
-- SKELETON SOLUSI (LENGKAPI):
CustomerCount_Optimized := 
CALCULATE(
    /* Masukkan fungsi agregasi baris di sini */,
    /* Masukkan predikat kolom langsung */
)
```

<details>
<summary>Lihat Solusi Easy</summary>

```dax
CustomerCount_Optimized := 
CALCULATE(
    COUNTROWS(DimCustomer),
    DimCustomer[YearlyIncome] > 50000
)
```
*Penjelasan*: Sintaks ini memungkinkan VertiPaq mengevaluasi filter langsung di tingkat index bitmap/RLE tanpa perlu mematerialisasi tabel virtual perantara melalui fungsi `FILTER` di Formula Engine.
</details>

---

### Level Medium
Sebuah tabel transaksi `FactInventory` (25 juta baris) mencatat stok harian. Anda diminta membuat Measure `ClosingStock` yang mengambil angka `FactInventory[StockUnits]` pada hari terakhir di mana stok tercatat dalam periode filter yang dipilih pengguna.

```dax
-- SKELETON SOLUSI:
ClosingStock := 
VAR LastAvailableDate = 
    CALCULATE(
        MAX(FactInventory[SnapshotDate]),
        /* Hint: Tangani restriksi filter konteks tanggal */
    )
RETURN
    CALCULATE(
        SUM(FactInventory[StockUnits]),
        /* Sinkronisasikan dengan tanggal terakhir */
    )
```

<details>
<summary>Lihat Solusi Medium</summary>

```dax
ClosingStock := 
VAR LastAvailableDate = 
    CALCULATE(
        MAX(FactInventory[SnapshotDate]),
        CALCULATETABLE(
            FactInventory,
            ALL(DimDate)
        )
    )
RETURN
    IF(
        NOT ISBLANK(LastAvailableDate),
        CALCULATE(
            SUM(FactInventory[StockUnits]),
            FactInventory[SnapshotDate] = LastAvailableDate,
            ALL(DimDate)
        )
    )
```
</details>

---

### Level Hard
Optimalkan kalkulasi analitik *Customer Churn Status* di bawah ini yang berjalan sangat lambat pada dataset 50 juta baris. Kriteria *churn*: Pelanggan yang tidak memiliki transaksi dalam kurun waktu 90 hari sebelum tanggal maksimum yang dipilih pada filter konteks aktif.

```dax
-- SKELETON AWAL (ANTI-PATTERN):
SlowChurnedCustomers := 
COUNTROWS(
    FILTER(
        VALUES(DimCustomer[CustomerKey]),
        VAR LastPurchase = 
            CALCULATE(MAX(FactSales[OrderDate]))
        RETURN
            LastPurchase < MAX(DimDate[Date]) - 90
    )
)
```

Tulis ulang secara komprehensif menggunakan aljabar relasional himpunan (`EXCEPT` atau lineage mapping via `TREATAS`) untuk memaksimalkan SE processing.

<details>
<summary>Lihat Solusi Hard</summary>

```dax
OptimizedChurnedCustomers := 
VAR MaxSelectedDate = MAX(DimDate[Date])
VAR ThresholdDate = MaxSelectedDate - 90
-- Seluruh pelanggan yang pernah aktif hingga periode saat ini
VAR ActiveHistoryCustomers = 
    CALCULATETABLE(
        VALUES(FactSales[CustomerKey]),
        DimDate[Date] <= MaxSelectedDate,
        ALL(DimDate)
    )
-- Pelanggan yang aktif dalam 90 hari terakhir
VAR RecentActiveCustomers = 
    CALCULATETABLE(
        VALUES(FactSales[CustomerKey]),
        DimDate[Date] > ThresholdDate,
        DimDate[Date] <= MaxSelectedDate,
        ALL(DimDate)
    )
-- Churned = Memiliki transaksi di masa lalu tetapi tidak ada dalam 90 hari terakhir
VAR ChurnedCustomersTable = 
    EXCEPT(ActiveHistoryCustomers, RecentActiveCustomers)
RETURN
    COUNTROWS(ChurnedCustomersTable)
```
*Mengapa ini jauh lebih cepat?* Menghilangkan context transition baris-per-baris (`CALCULATE(MAX(...))`) di dalam fungsi `FILTER`. Menggantinya dengan dua scan VertiPaq yang sangat cepat, lalu melakukan operasi himpunan memory hash set `EXCEPT` di FE.
</details>

---

## 14. Challenge

### Skenario Kasus Arsitektural Kompleks

Sebuah institusi perbankan investasi multinasional mengelola portofolio derivatif dengan tabel transaksi faktur `FactPositions` berisi 350 juta baris data.

#### Persyaratan Sistem & Kendala Teknis:
1. **Dynamic Security Boundary**: Filter baris berlaku secara asimetris:
   * *Trader* hanya dapat melihat posisi trading milik dirinya sendiri (`TraderID = USERPRINCIPALNAME()`).
   * *Risk Manager* dapat melihat posisi portofolio yang diawasi jika skor eksposur risiko instrumen melampaui ambang batas dinamis yang dihitung dari tabel parameter volatilitas pasar `DimVolatilityParam[VaR_Threshold]`.
2. **Arbitrary-shaped Slicing**: Visual pelaporan harus mendukung analisis matriks di mana pengguna memilih kombinasi hierarki atribut tidak teratur: `{Tahun: 2023, Wilayah: "APAC"} DAN {Tahun: 2024, Wilayah: "EMEA"}` dalam satu state filter konteks visual.
3. **SLA Ketat**: Durasi total rendering visual pada Power BI Premium Dedicated Capacity P2 **tidak boleh melebihi 1.200 ms**.
4. **Kendala Fisik**: Data model berjalan pada mode *Import*. Dilarang menambah Calculated Column fisik apa pun pada tabel `FactPositions` untuk menghemat konsumsi RAM yang saat ini berada di ambang batas 78% limit memori kapasitas.

#### Tugas Anda:
* Rancang arsitektur formula DAX teroptimasi untuk mengkalkulasi `NetRiskAdjustedExposure` yang memenuhi kondisi pemfilteran kompleks tersebut.
* Pastikan kueri tidak membangkitkan *CallbackDataID* dan tidak menghasilkan *cross-join explosion materialization* saat Risk Manager mengakses portofolio gabungan.

*(Tantangan mandiri tingkat arsitek data: Evaluasi rancangan Anda di DAX Studio menggunakan Query Plan and Server Timings).*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)

1. **Komponen manakah pada mesin evaluasi Power BI yang beroperasi secara single-threaded?**
   * A) VertiPaq Storage Engine
   * B) DirectQuery Engine
   * C) Formula Engine
   * D) Network Gateway Layer
   * *Jawaban:* **C**. Formula Engine berjalan secara *single-threaded* per query.

2. **Apa yang dimaksud dengan Context Transition pada DAX?**
   * A) Konversi dari Filter Context menjadi Row Context otomatis.
   * B) Transformasi Row Context aktif menjadi Filter Context yang setara menggunakan fungsi `CALCULATE`.
   * C) Perubahan mode koneksi DirectQuery menjadi Import mode saat runtime visual.
   * D) Migrasi relasi non-aktif menjadi relasi aktif menggunakan `USERELATIONSHIP`.
   * *Jawaban:* **B**. Context Transition mentransformasikan Row Context yang ada menjadi Filter Context ekuivalen di bawah instruksi `CALCULATE`.

3. **Format kueri internal yang digunakan oleh Formula Engine untuk meminta data ke VertiPaq Storage Engine disebut...**
   * A) T-SQL
   * B) MDX
   * C) DAX Native String
   * D) xmSQL
   * *Jawaban:* **D**. xmSQL adalah representasi query internal SE.

4. **Jenis kompresi data VertiPaq yang memanfaatkan pengulangan data berurutan berturut-turut adalah...**
   * A) Dictionary Encoding
   * B) Run-Length Encoding (RLE)
   * C) Bit-Packing
   * D) Huffman Coding
   * *Jawaban:* **B**. RLE menyimpan baris duplikat berurutan dalam bentuk counter.

5. **Apa dampak langsung bagi performa jika fungsi `CALCULATE()` dipanggil di dalam fungsi `SUMX` yang melintasi tabel 10 juta baris?**
   * A) Peningkatan pemanfaatan paralelisasi CPU SE.
   * B) Otomatisasi kompresi memory cache.
   * C) Terjadi 10 juta kali Context Transition yang berpotensi membebani CPU secara masif.
   * D) Kueri akan langsung gagal (*fail compile*) karena sintaks terlarang.
   * *Jawaban:* **C**. Context Transition dijalankan untuk setiap baris dari 10 juta baris iterasi.

---

### Bagian 2: Intermediate (5 Pertanyaan)

6. **Mengapa kemunculan indikator `CallbackDataID` pada log DAX Studio Server Timings dianggap berbahaya bagi kinerja query?**
   * A) Karena mengindikasikan koneksi gateway jaringan terputus.
   * B) Karena Storage Engine terpaksa menghentikan multithreading untuk meminta FE mengevaluasi ekspresi per baris.
   * C) Karena data cache di-flush dari RAM secara permanen.
   * D) Karena data model dipaksa berpindah ke mode DirectQuery.
   * *Jawaban:* **B**. CallbackDataID mematahkan kecepatan eksekusi paralel SE dengan mengembalikan alur komputasi ke FE baris demi baris.

7. **Bagaimana konsep Expanded Tables memengaruhi fungsi filter `CALCULATE(..., FactSales[Qty] > 10)` dibandingkan `CALCULATE(..., DimProduct[Color] = "Red")`?**
   * A) Filter pada `FactSales` tidak memperluas tabel; filter pada `DimProduct` memperluas relasi 1:N dan menyaring baris `FactSales` yang berhubungan.
   * B) Filter pada `DimProduct` menyalin seluruh isi `FactSales` ke tabel dimensi.
   * C) Keduanya memiliki dampak ekspansi tabel yang sama persis tanpa perbedaan relasional.
   * D) Expanded Tables hanya aktif jika relasi model dikonfigurasi secara Bi-directional.
   * *Jawaban:* **A**. Sisi 1 (DimProduct) memperluas tabel sisi N (FactSales) di dalam arsitektur Expanded Table VertiPaq.

8. **Manakah dari sintaks filter berikut yang memiliki performa eksekusi tercepat pada VertiPaq?**
   * A) `FILTER(DimCustomer, DimCustomer[City] = "Jakarta")`
   * B) `FILTER(ALL(DimCustomer[City]), DimCustomer[City] = "Jakarta")`
   * C) `KEEPFILTERS(DimCustomer[City] = "Jakarta")`
   * D) `FILTER(VALUES(DimCustomer[City]), DimCustomer[City] = "Jakarta")`
   * *Jawaban:* **C**. Native filter dengan `KEEPFILTERS` langsung memanipulasi filter konteks tanpa mematerialisasi iterasi tabel virtual perantara.

9. **Apa perbedaan mendasar antara perilaku fungsi `ALL()` dan `ALLSELECTED()` dalam pohon filter konteks?**
   * A) `ALL()` menghapus filter dari baris visual saja, `ALLSELECTED()` menghapus semua filter model.
   * B) `ALL()` mengabaikan seluruh filter context pada kolom target, sedangkan `ALLSELECTED()` hanya menghapus filter konteks internal visual tanpa menghilangkan filter luar dari slicer/page.
   * C) `ALLSELECTED()` tidak pernah memicu context transition.
   * D) `ALL()` memaksa kueri dijalankan pada Formula Engine, sedangkan `ALLSELECTED()` di Storage Engine.
   * *Jawaban:* **B**. `ALLSELECTED` mempertahankan filter kontekstual yang berasal dari pemfilteran luar visual (slicer/canvas).

10. **Kondisi manakah yang menyebabkan metrik "SE CPU / SE Duration" bernilai lebih dari 1.0 (misal: 8.5) di DAX Studio?**
    * A) Telah terjadi bottleneck memori cache.
    * B) Kueri dieksekusi secara efisien menggunakan paralelisasi multi-core CPU pada Storage Engine.
    * C) Kueri dialihkan secara paksa ke Formula Engine yang lambat.
    * D) Terjadi kegagalan pembacaan segment index pada VertiPaq.
    * *Jawaban:* **B**. Nilai rasio > 1.0 membuktikan multi-threading bekerja (contoh: 8 CPU core bekerja secara bersamaan sehingga total CPU time lebih besar dari total *wall-clock duration*).

---

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

#### Skenario 1: The Spool Materialization Memory Outbreak
Sebuah dashboard enterprise menampilkan visual tabel dengan 10 kolom dari berbagai tabel dimensi dan sebuah measure:
```dax
MarginRank = RANKX(ALL(DimCustomer), [TotalMargin], , DESC)
```
Saat visual di-render pada kapasitas P1, terjadi error: *"Resource Governing: This visual has exceeded the available memory of 10,240 MB"*. Padahal total baris `DimCustomer` hanya 100.000 baris.  
**Pertanyaan**: Apa yang menyebabkan lonjakan alokasi memori puluhan gigabyte secara tiba-tiba tersebut?  
**Analisis Solusi**:
Visual memicu *Spool Materialization Explosion*. Pada visual matrix/table yang mengelompokkan data berdasarkan atribut banyak, `RANKX` dievaluasi pada setiap irisan baris visual. Karena `RANKX` memanggil Measure `[TotalMargin]`, context transition dipanggil di dalam iterasi `ALL(DimCustomer)`. Akibatnya, Formula Engine mencoba mematerialisasikan hash table perantara (100.000 baris dikalikan dengan jumlah sel matriks visual yang dirender).  
*Solusi*: Gunakan fungsi *Window functions* modern seperti `RANK()` berbasis aljabar relasional native atau batasi ruang evaluasi menggunakan variabel tabel tereduksi hanya untuk customer yang memiliki transaksi aktif pada filter konteks saat ini (`CALCULATETABLE(VALUES(FactSales[CustomerKey]))`).

#### Skenario 2: The Direct Lake Fallback Dilemma
Sebuah model semantik berukuran 500 GB di Microsoft Fabric menggunakan koneksi *Direct Lake*. Pada jam kerja normal, beberapa visual kartu mendadak mengalami lonjakan latensi dari 300 ms menjadi 45 detik. Dari trace log diketahui query mengalami status **"Fallback to DirectQuery"**.  
**Pertanyaan**: Apa akar masalah arsitektural dari kejadian fallback tersebut dan langkah apa yang wajib diambil?  
**Analisis Solusi**:
Direct Lake membaca file Parquet langsung dari OneLake ke memory VertiPaq. Fallback ke DirectQuery (melewati T-SQL endpoint yang jauh lebih lambat) terjadi karena:
1. Kapasitas SKU melampaui ambang batas memori paging (*memory limit paging threshold*).
2. Terdapat ekspresi DAX yang menggunakan fitur yang tidak didukung Direct Lake (misal: kompleksitas RLS tertentu atau view yang belum di-warm up).
3. Kolom teks berukuran masif mengalami de-kompresi mendadak yang melampaui RAM limit Fabric SKU.  
*Solusi*: Terapkan *Framing* dan partisi pada OneLake Parquet files, pantau batasan Fabric SKU menggunakan Capacity Metrics App, dan ganti DAX logic yang memicu context transitions ekstrem agar pembacaan kolom tetap *in-memory* tanpa memicu fallback ke SQL endpoint.

#### Skenario 3: The Currency Conversion Cross-Join Explosion
Pengembang mengimplementasikan Measure konversi mata uang pada faktur penjualan 80 juta baris dengan mengalikan transaksi terhadap tabel kurs valuta asing:
```dax
BadConverted = 
SUMX(
    FactSales,
    FactSales[Amount] * RELATED(FactExchangeRate[Rate])
)
```
Model memiliki relasi ganda antara tanggal dan mata uang. Kueri berjalan lebih dari 20 detik.  
**Pertanyaan**: Mengapa pendekatan di atas salah secara mendasar, dan bagaimana rekonstruksi arsitektur kuerinya agar tuntas dalam < 500 ms?  
**Analisis Solusi**:
Tabel `FactSales` memiliki 80 juta baris. Menjalankan `SUMX` di level baris transaksi memaksa FE melakukan iterasi 80 juta kali. Selain itu, fungsi `RELATED` melintasi relasi multi-kondisi menyebabkan keterbatasan SE xmSQL compilation.  
*Solusi*: Agregasikan data terlebih dahulu di level granularitas kurs (Tanggal dan Mata Uang) menggunakan `SUMMARIZECOLUMNS` atau `SUMMARIZE` ke dalam sebuah tabel virtual perantara kecil, baru kalikan total penjualan per hari terhadap kurs hari tersebut:
```dax
OptimizedConverted = 
SUMX(
    SUMMARIZE(
        FactSales,
        DimDate[DateKey],
        FactSales[CurrencyKey]
    ),
    CALCULATE(SUM(FactSales[Amount])) * 
    CALCULATE(MAX(FactExchangeRate[Rate]))
)
```
Jumlah iterasi terpangkas dari 80.000.000 baris menjadi hanya sejumlah hari $\times$ mata uang aktif (misal: $365 \times 5 = 1.825$ baris virtual), memangkas waktu proses hingga < 200 ms.

---

## 16. Summary

1. **Formula Engine (FE)** dan **Storage Engine (SE)** bekerja dalam kemitraan asimetris: FE memproses alur logika kueri secara *single-threaded*, sementara SE (VertiPaq) mengeksekusi kompresi dan agregasi data secara *multi-threaded*.
2. **Kunci Performa DAX Skala Besar**: Menjaga agar 90%+ kalkulasi dieksekusi di SE dalam format **xmSQL bersih**, dan meniadakan indikator **CallbackDataID**.
3. **Context Transition** adalah pedang bermata dua: Fundamental bagi kalkulasi bisnis tingkat lanjut, namun dapat menjadi sumber bencana performa jika diaktifkan secara tidak sengaja di dalam *row-level iterators* pada tabel berkardinalitas tinggi.
4. **Expanded Tables**: Pemfilteran tabel dimensi mengalir ke tabel fakta via relasi relasional konseptual yang melebar, sehingga memfilter tabel fakta menggunakan tabel dimensi secara komparatif jauh lebih efisien daripada memfilter tabel fakta secara langsung.
5. **Standard Industri Enterprise**: Hindari iterasi level transaksi, maksimalkan operasi berbasis himpunan (*set-based relational operations*), dan jadikan *DAX Studio Server Timings* sebagai instrumen audit performa utama pada setiap implementasi sistem analitik produksi.