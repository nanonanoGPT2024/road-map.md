# Bab 04: Advanced DAX Patterns & Analytical Engineering
## Modul 01: Engine Mechanics, Context Transition & High-Performance Calculation Patterns

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal Execution Pipeline:** Mendekonstruksi pemrosesan kueri DAX antara Formula Engine (FE) dan Storage Engine (SE/VertiPaq) menggunakan DAX Studio dan Server Timings untuk mengidentifikasi bottleneck eksekusi *CallbackDataID*.
- **Menguasai Context Transition & Expanded Tables:** Mengontrol secara deterministik interaksi antara *Row Context*, *Filter Context*, dan ekspansi tabel dimensi-ke-fakta implisit (*Expanded Tables*) dalam relasi 1-ke-Banyak (*1:N*).
- **Mengembangkan Pola Analitik Kompleks Tingkat Lanjut:** Mengimplementasikan pola kalkulasi tingkat enterprise mencakup *Semi-Additive Measures*, *Dynamic Cohort/Basket Analysis*, dan *Arbitrary Date-Boundary Aggregations* memanfaatkan DAX Window Functions modern (`WINDOW`, `OFFSET`, `INDEX`).
- **Mengeliminasi Anti-Patterns:** Mendeteksi dan merestrukturisasi ekspresi DAX suboptimal yang memicu pemindaian *Full Table Scan*, materialisasi tabel virtual tak berbatas (*unbounded in-memory materialization*), serta konversi konteks implisit di dalam loop iterasi besar.
- **Mengoptimalkan Metrik Performa VertiPaq:** Mencapai minimal 80% alokasi beban kerja pada Storage Engine (SE CPU/Query Duration) dan mereduksi atau mengeliminasi *Formula Engine Single-Threaded Overhead* pada model data berskala multi-juta baris.

---

### 2. Concept Overview (Mental Model & Teori Inti)

DAX (*Data Analysis Expressions*) bukan sekadar bahasa pemrograman fungsional; DAX adalah mesin komputasi analitik in-memory berbasis logika relasional terkompresi. Memahami DAX membutuhkan mental model yang memisahkan **Deklarasi Logika Kueri** dari **Topologi Eksekusi Fisik**.

```
+--------------------------------------------------------------------------------+
|                                MENTAL MODEL DAX                                |
|                                                                                |
|   Filter Context                 Row Context                  Expanded Tables   |
|  [Dinding Pembatas]           [Penunjuk Baris]             [Jangkauan Visibilitas]|
|          │                            │                               │        |
|          ▼                            ▼                               ▼        |
| Menentukan subset baris   Hanya mengenali nilai kolom      Tabel di sisi 'Many'|
| yang aktif di seluruh      pada baris saat ini; TIDAK      otomatis menyerap   |
| data model.               memfilter model secara otomatis. kolom tabel 'One'.  |
+--------------------------------------------------------------------------------+
```

#### Dual Engine Architecture
Komputasi DAX dipecah menjadi dua subsistem independen namun saling berkomunikasi:
1. **Formula Engine (FE):** Subsistem serbaguna, *single-threaded*, mengeksekusi logika kondisional yang kompleks, menangani operasi ekspresi string tingkat lanjut, mengevaluasi fungsi windowing, dan merajut (*stitching*) potongan data tabular yang diekstrak oleh Storage Engine.
2. **Storage Engine (SE / VertiPaq):** Subsistem *multi-threaded*, memproses instruksi berbasis kolumnar yang sangat terkompresi (Dictionary Encoding, RLE, Bit-Packing). VertiPaq mengeksekusi filtering, grouping, dan agregasi dasar (`SUM`, `MIN`, `MAX`, `COUNT`) menggunakan bahasa kueri internal yang disebut **xmSQL**. Alternatif SE lainnya adalah DirectQuery (SQL Server, Snowflake, BigQuery) yang menerjemahkan instruksi ke dialek native database target.

#### Context Transition
Peristiwa kritis di mana sebuah *Row Context* diubah menjadi serangkaian *Filter Context* yang ekuivalen untuk setiap kolom pada baris saat ini. Fenomena ini dipicu secara eksklusif oleh fungsi `CALCULATE()` atau `CALCULATETABLE()`, atau oleh pemanggilan referensi measure di dalam fungsi iterator (seperti `SUMX`, `FILTER`, `GENERATE`).

---

### 3. Why It Matters (Konteks Enterprise & Skala Masif)

Pada data mart berskala kecil (<1 juta baris), kode DAX yang ditulis secara naif tetap dapat menghasilkan respons visual sub-detik. Namun, pada skala enterprise (puluhan hingga ratusan juta baris, ratusan pengguna simultan):

1. **Konkurensi & Resource Exhaustion:** Formula Engine beroperasi secara *single-threaded per query*. Formula yang membebankan pemrosesan pada FE akan memonopoli satu core CPU, memicu antrean (*queueing*) pada Analysis Services/Power BI Premium Capacity, dan melipatgandakan latensi visual.
2. **CallbackDataID Death Spiral:** Ketika Storage Engine (VertiPaq) tidak dapat mengevaluasi ekspresi tertentu (misal: logika kondisional skalar kompleks di dalam iterator), VertiPaq terpaksa melakukan interupsi dan meminta Formula Engine mengevaluasi baris per baris (*CallbackDataID*). Ini mematikan vektorisasi VertiPaq dan menurunkan performa hingga 100x lipat.
3. **Semantik Bisnis yang Rapuh:** Ketidakpahaman tentang *Expanded Tables* dapat menyebabkan bug kalkulasi finansial fatal saat memfilter tabel fakta melalui relasi jembatan (*bridge tables*) atau relasi Many-to-Many.

---

### 4. Arsitektur & Diagram Komponen

Alur pemrosesan kueri end-to-end dari visual Power BI hingga eksekusi physical storage engine:

```
[ Power BI Visual / Client Query ]
               │
               │ (1) DAX Query Text (EVALUATE ...)
               ▼
+---------------------------------------------------------------------+
| FORMULA ENGINE (FE) - Single Threaded Orchestrator                  |
|                                                                     |
|  ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐ |
|  │ Lexer & Parser   │───▶│ Logical Query   │───▶│ Physical Plan   │ |
|  │                  │    │ Plan Generation │    │ Execution Trees │ |
|  └──────────────────┘    └─────────────────┘    └────────┬────────┘ |
+----------------------------------------------------------┼----------+
                                                           │
                        (2) Generate Scan/Agg Request      │
                            berupa xmSQL queries           ▼
+---------------------------------------------------------------------+
| STORAGE ENGINE (SE: VertiPaq / DirectQuery) - Multi Threaded Engine |
|                                                                     |
|   Thread 1 ──▶ [Segment 0..N] ──┐                                   |
|   Thread 2 ──▶ [Segment 0..N] ──┼─▶ [Columnar SIMD Scans / Bitmaps]  |
|   Thread N ──▶ [Segment 0..N] ──┘                                   |
|                                                                     |
|   xmSQL Engine:                                                     |
|     SELECT Fact[Key], SUM(Fact[Sales])                              |
|     FROM Fact WHERE Fact[RegionID] = 42                             |
|     GROUP BY Fact[Key]                                              |
+----------------------------------------------------------┬----------+
                                                           │
                    (3) In-Memory Data Caches (Datacache)  │
                        Uncompressed Data stream           ▼
+---------------------------------------------------------------------+
| FORMULA ENGINE (FE)                                                 |
|                                                                     |
|  ┌───────────────────────────────────────────────────────────────┐  |
|  │ Stitching datacaches, complex math, context resolution        │  |
|  │ (Jika ada CallbackDataID: FE bolak-balik panggil SE per baris)│  |
|  └───────────────────────────────┬───────────────────────────────┘  |
+----------------------------------┼----------------------------------+
                                   │
                                   ▼
          (4) Tabular JSON Data Stream dikirim ke Visual
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Expanded Tables Mechanics
Di dalam Tabular Model, tabel tidak berdiri sendiri secara terisolasi. Ketika tabel $F$ berada di sisi *Many* dari relasi $1:N$ dengan tabel dimensi $D$, maka **Expanded Table** dari $F$ (ditulis $F^+$) mencakup seluruh kolom fisik milik $F$ ditambah seluruh kolom milik $D$ (dan seluruh tabel lain yang terhubung via rantai relasi $1:N$ keluar).

*Implikasi Kritis:*
```dax
-- Varian A: Memfilter Dimensi secara eksplisit
CALCULATE(
    [Total Sales],
    DimProduct[Category] = "Audio"
)

-- Varian B: Filter tabel Fakta secara langsung (Memicu Table Expansion Trap)
CALCULATE(
    [Total Sales],
    FILTER(
        FactSales,
        FactSales[ProductKey] IN { 101, 102, 103 }
    )
)
```
Pada Varian B, `FILTER(FactSales, ...)` mempertahankan *seluruh kolom dari expanded table* FactSales. Ini mengunci baris-baris tertentu pada dimensi yang berelasi dan dapat menonaktifkan filter silang lain yang datang dari dimensi lain, memboroskan memori cache FE secara masif.

#### B. Anatomi Context Transition
Ketika eksekusi berpindah dari Baris ke Filter:
1. Iterasi baris aktif pada tabel $T$.
2. Fungsi `CALCULATE` dipanggil.
3. Nilai dari setiap kolom fisik tabel $T$ pada baris aktif saat ini diekstraksi.
4. Nilai-nilai tersebut disuntikkan ke dalam Filter Context baru sebagai kondisi kesetaraan granular: `T[Col1] = val1 && T[Col2] = val2 && ... && T[ColN] = valN`.
5. Jika tabel memiliki kolom tersembunyi ber-kardinalitas tinggi, filter context membengkak seketika.

#### C. VertiPaq Optimization: Eliminasi CallbackDataID
Sebuah *CallbackDataID* terjadi jika Formula Engine harus mengintervensi eksekusi VertiPaq.
Contoh pemicu:
- Penggunaan pembagian tanpa proteksi SE (`DIVIDE` dengan fallback yang memanggil FE).
- Ekspresi bersyarat nonsimetris (`IF( [Measure] > 0, [Calc A], [Calc B] )` di dalam iterator level baris).
- Penggunaan fungsi-fungsi non-VertiPaq native (misal string manipulation dinamis di tengah agregasi).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi pola analitik tingkat tinggi enterprise yang mematuhi standar performa (Fully SE vectorized, Zero CallbackDataID, Explicit Filter Context Management).

#### Pattern 1: High-Performance Dynamic Customer Segmentation (Non-Cartesian)
Pola ini menghindari iterasi `FILTER(ALL(Customer), ...)` yang memicu materialisasi cache masif. Menggunakan model virtual bucket dengan Windowing/TREATAS.

```dax
DEFINE
    MEASURE FactSales[Total Revenue] = 
        SUMX(
            FactSales,
            FactSales[Quantity] * FactSales[NetPrice]
        )

    MEASURE FactSales[Customer Revenue (Customer Context)] = 
        CALCULATE(
            [Total Revenue],
            ALLEXCEPT(FactSales, DimCustomer[CustomerKey])
        )

    MEASURE FactSales[Segmented Customer Count] = 
        VAR _CurrentBucket = SELECTEDVALUE('DimensionSegmentation'[BucketName])
        VAR _MinThreshold = SELECTEDVALUE('DimensionSegmentation'[MinSales])
        VAR _MaxThreshold = SELECTEDVALUE('DimensionSegmentation'[MaxSales])
        
        -- Ekstrak ringkasan agregat di level SE, bukan scanning customer table in FE
        VAR _CustomerSpendTable = 
            SUMMARIZE(
                FactSales,
                DimCustomer[CustomerKey],
                "@Spend", [Total Revenue]
            )
            
        -- Filter baris dalam memori virtual tanpa merusak expanded table architecture
        VAR _QualifiedCustomers = 
            FILTER(
                _CustomerSpendTable,
                [@Spend] >= _MinThreshold &&
                (ISBLANK(_MaxThreshold) || [@Spend] < _MaxThreshold)
            )
            
        RETURN
            COUNTROWS(_QualifiedCustomers)

EVALUATE
    SUMMARIZECOLUMNS(
        'DimensionSegmentation'[BucketName],
        "ActiveCustomersInSegment", [Segmented Customer Count]
    )
```

#### Pattern 2: Semi-Additive Measures (Opening & Closing Balance Pattern)
Menghindari penggunaan `FIRSTDATE`/`LASTDATE` yang sering menimbulkan evaluasi filter context yang salah ketika rentang tanggal tidak memiliki transaksi.

```dax
DEFINE
    MEASURE FactInventory[Closing Inventory Balance] = 
        VAR _MaxDateInContext = MAX('DimDate'[Date])
        VAR _LastTransactionDate = 
            CALCULATE(
                MAX(FactInventory[SnapshotDate]),
                'DimDate'[Date] <= _MaxDateInContext,
                REMOVEFILTERS('DimDate')
            )
        RETURN
            IF(
                NOT ISBLANK(_LastTransactionDate),
                CALCULATE(
                    SUM(FactInventory[EndingUnits]),
                    'DimDate'[Date] = _LastTransactionDate,
                    REMOVEFILTERS('DimDate')
                )
            )

    -- Evaluasi Moving Average berbasis Window Function (VertiPaq Native Engine)
    MEASURE FactInventory[Smooth Inventory 30D Window] = 
        VAR _WindowCalculation = 
            AVERAGEX(
                WINDOW(
                    -29, RELATIVE,
                    0, RELATIVE,
                    SUMMARIZE(ALLSELECTED('DimDate'), 'DimDate'[Date]),
                    ORDERBY('DimDate'[Date], ASC)
                ),
                [Closing Inventory Balance]
            )
        RETURN
            _WindowCalculation
```

#### Pattern 3: Arbitrary Boundary Comparative Analytics via Virtual Relationship (`TREATAS`)
Pola performan tinggi untuk perbandingan periode arbitrary (tanpa merusak model schema fisik).

```dax
DEFINE
    MEASURE FactSales[Revenue In Selected Custom Period] = 
        VAR _ComparisonPeriodDates = 
            CALCULATETABLE(
                VALUES('DimDate'[Date]),
                'DimDate'[PeriodGroup] = "Custom Benchmark Period",
                REMOVEFILTERS('DimDate')
            )
        VAR _Result = 
            CALCULATE(
                [Total Revenue],
                -- Mengganti dependensi fisik ke virtual injection
                TREATAS(
                    _ComparisonPeriodDates,
                    'DimDate'[Date]
                ),
                REMOVEFILTERS('DimDate')
            )
        RETURN
            _Result
```

---

### 7. Edge Cases & Failure Modes (Root Cause & Mitigasi)

#### Kasus 1: Expanded Table Filter Context Leaks
- **Gejala:** Nilai measure pada visual Card tetap tidak berubah saat slicer tabel dimensi turunan dipilih.
- **Mekanisme Kegagalan:** Penggunaan formula seperti `CALCULATE([Sales], FILTER(FactSales, FactSales[Discount] > 0.1))` mengubah filter context atas seluruh baris `FactSales`. Melalui *Expanded Tables*, ini mempertahankan seluruh keys dimensi yang terikat saat ekspresi dievaluasi, menimpa slicer luar secara tidak terduga.
- **Mitigasi:** Jangan memfilter tabel fisik secara penuh. Hanya filter kolom target spesifik menggunakan `KEEPFILTERS`:
  ```dax
  CALCULATE(
      [Total Revenue],
      KEEPFILTERS(FactSales[Discount] > 0.1)
  )
  ```

#### Kasus 2: The Nested Context Transition Performance Cliff
- **Gejala:** Kueri memakan waktu >30 detik dan menghabiskan RAM hingga limit kapasitas (*Out of Memory*).
- **Mekanisme Kegagalan:**
  ```dax
  SUMX(
      Customer,
      SUMX(
          Product,
          [Total Revenue] -- Measure memicu context transition ganda!
      )
  )
  ```
  Jika terdapat 50.000 Customer dan 2.000 Product, DAX mengeksekusi $100.000.000$ (100 juta) evaluasi `CALCULATE` independen via Formula Engine.
- **Mitigasi:** Vektorisasi kalkulasi menggunakan `SUMMARIZECOLUMNS` atau `ADDCOLUMNS` pada dataset yang sudah diagregasi oleh Storage Engine sebelum melakukan iterasi.

#### Kasus 3: Division-by-Zero Callback Trap
- **Gejala:** Timbul trace event *CallbackDataID* masif pada Storage Engine trace.
- **Mekanisme Kegagalan:** Menulis ekspresi `IF(SUM(Table[Denom]) = 0, BLANK(), SUM(Table[Num]) / SUM(Table[Denom]))` memaksa VertiPaq memanggil FE untuk memeriksa kesetaraan nilai logis pada setiap perpotongan granularitas.
- **Mitigasi:** Gunakan fungsi intrinsik SE-friendly `DIVIDE(SUM(Table[Num]), SUM(Table[Denom]))`.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Dynamic DAX Calculation | Physical Calculated Columns | Power Query / ETL Pre-agg |
| :--- | :--- | :--- | :--- |
| **Konsumsi Memori VertiPaq** | Sangat Rendah (0 byte runtime footprint) | Tinggi (Mengurangi rasio kompresi dictionary) | Minimal pada level fakta, menambah dimensi baru |
| **Waktu Pemrosesan Refresh** | Nol | Menambah waktu proses CPU saat refresh | Tergantung kapasitas warehouse/pipeline |
| **Kecepatan Query (End-User)** | Bergantung efisiensi formula (10ms - 2s) | Sangat cepat (Terindeks secara kolumnar) | Instan (Telah dikomputasi sebelumnya) |
| **Fleksibilitas Filter Dinamis** | Penuh (Responsif terhadap slicer & keamanan RLS) | Statis (Konteks baris saat refresh engine) | Kaku (Hanya pada granularitas agregat) |

#### Komparasi Strategis: `USERELATIONSHIP` vs `TREATAS`
- **Gunakan `USERELATIONSHIP`:** Jika schema model stabil dan relasi antar tabel bersifat 1:N statis. Memanfaatkan internal pointer VertiPaq yang sangat cepat (native bitmapped filtering).
- **Gunakan `TREATAS`:** Jika ingin menghindari overhead pengelolaan banyak relasi inaktif di schema diagram, atau saat memetakan relasi N:N virtual ad-hoc antara dua tabel dimensi independen. Konsekuensinya: sedikit penurunan kecepatan dibanding relasi fisik native.

---

### 9. Best Practices & Standar Industri

1. **Aturan Skalaritas:** Jangan pernah merujuk measure tanpa nama tabel (`[Total Sales]`) dan jangan pernah merujuk kolom tanpa menyertakan nama tabel (`Table[Column]`). Hal ini menghapus ambiguitas sintaksis bagi parser FE.
2. **KEEPFILTERS Secara Default:** Gunakan fungsi `KEEPFILTERS()` saat menyuntikkan filter predikat dalam `CALCULATE` agar tidak menimpa konteks filter eksplisit yang sudah ditetapkan oleh pengguna dari visual slicer:
   ```dax
   CALCULATE([Total Sales], KEEPFILTERS(DimProduct[Brand] = "Contoso"))
   ```
3. **Pemberantasan CallbackDataID:** Pantau Trace DAX Studio Server Timings:
   - Pastikan metrik rasio waktu: $\text{Storage Engine (SE) Time} > 80\%$.
   - Flag *xmSQL Callback*: Jika terdapat string `CallbackDataID`, modifikasi logika kalkulasi agar evaluasi logika dapat diselesaikan oleh VertiPaq SIMD engine.
4. **Alokasi Agregasi Menggunakan DAX Modern Windows:** Tinggalkan manipulasi tanggal menggunakan filter tabel penuh `FILTER(ALL(DimDate), ...)` untuk kalkulasi moving period. Gunakan rangkaian fungsi modern DAX: `OFFSET`, `WINDOW`, atau `INDEX` yang dieksekusi secara fully-vectorized di tingkat core tabular engine.

---

### 10. Hands-on Lab Exercise

#### Skenario Enterprise:
Sistem Core Banking mencatat 15 juta baris mutasi rekening. Bisnis membutuhkan metrik performa tinggi: *Saldo Harian Efektif Akhir Periode*, dikelompokkan ke dalam kategori likuiditas nasabah secara dinamis tanpa menurunkan SLA visual Power BI (respons render harus tetap berada di bawah 600 milidetik).

#### Langkah Eksekusi Terstruktur:

1. **Langkah 1: Setup Model & Buka DAX Studio**
   - Buka file PBIX berisikan model transaksi.
   - Sambungkan DAX Studio ke model Power BI Desktop yang terbuka.
   - Aktifkan menu **Server Timings** (Pastikan opsi *SE Events* dan *Cache* tercentang).

2. **Langkah 2: Menulis Baseline Measure (Naive Implementation)**
   Tuliskan measure baseline berikut dan jalankan profiling kueri di DAX Studio:
   ```dax
   EVALUATE
   SUMMARIZECOLUMNS(
       DimAccount[AccountID],
       "Balance",
       CALCULATE(
           SUM(FactTransaction[Amount]),
           FILTER(
               ALL(DimDate),
               DimDate[Date] <= MAX(DimDate[Date])
           )
       )
   )
   ```
   *Amati trace Server Timings:* Catat nilai FE CPU time, SE CPU time, dan kemunculan event *CallbackDataID* akibat pemindaian `FILTER(ALL(DimDate), ...)`.

3. **Langkah 3: Transformasi ke Vektor Native VertiPaq**
   Tulis ulang measure menggunakan optimasi batas relasional tanpa melakukan looping Formula Engine:
   ```dax
   EVALUATE
   VAR _MaxSelectedDate = MAX(DimDate[Date])
   RETURN
   SUMMARIZECOLUMNS(
       DimAccount[AccountID],
       "OptimizedBalance",
       CALCULATE(
           SUM(FactTransaction[Amount]),
           DimDate[Date] <= _MaxSelectedDate,
           ALLEXCEPT(FactTransaction, DimAccount[AccountID])
       )
   )
   ```

4. **Langkah 4: Evaluasi Peningkatan Kinerja**
   - Bandingkan Server Timings antara Langkah 2 dan Langkah 3:
     - Apakah kueri SE turun dari multi-batch menjadi satu batch scan teragregasi?
     - Apakah waktu total eksekusi berkurang drastis (target: >70% reduksi latency)?
     - Pastikan Formula Engine (FE) time mendekati rentang 0–15% dari total durasi kueri.