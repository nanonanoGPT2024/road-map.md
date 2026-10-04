# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 05: Information Design, UX Semantics, & Visual Hierarchy**  
**Kategori: 08-AI-Data-and-Autonomous-Agents | Topik: Power BI Enterprise**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Siklus Hidup Rendering Visual**: Memahami lifecycle visual Power BI dari evaluasi *DAX Formula Engine (FE)*, *Storage Engine (SE)*, hingga serialisasi JSON dan kompilasi DOM/Canvas di browser.
2. **Mengembangkan High-Density Micro-Visuals Berbasis SVG Native**: Mengeliminasi overhead visual container ganda dengan memprogram komponen visual dinamis (sparklines, KPI bullet-bars) langsung via DAX Image Strings.
3. **Mengimplementasikan Arsitektur Semantic Formatting Skala Enterprise**: Membangun Calculation Groups untuk standardisasi format string dinamis, visual state toggling, dan currency conversion terpusat menggunakan Tabular Model Definition Language (TMDL).
4. **Menerapkan Standar Aksesibilitas Enterprise & Design System**: Mengonfigurasi WCAG 2.1 AA compliant color tokens, programmatic tab ordering, dan ARIA screen-reader labels menggunakan Power BI Enhanced Report Format (PBIR) dan Theme JSON.
5. **Mengoptimalkan Visual Query Pipeline untuk Concurrency Tinggi**: Mengurangi beban query visual hingga >60% melalui konsolidasi visual, pemangkasan *Visual Cardinality*, dan eliminasi antipattern visual synchronization.

---

## 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut:
* **Advanced Tabular Modeling**: Pemahaman mendalam terkait *Filter Context*, *Context Transition*, dan *Row Context* pada DAX.
* **DAX Internals**: Familiaritas dengan cara kerja *Formula Engine* (FE single-threaded) versus *Storage Engine* (VertiPaq multi-threaded / DirectQuery pushdown).
* **Power BI Developer Mode (PBIP)**: Menguasai struktur folder `.pbip`, khususnya format metadata visual modern (`/definition.pbir` dan file JSON pendukung).
* **Tooling Eksternal**: Penguasaan teknis Tabular Editor 3, DAX Studio, dan Browser Developer Tools (Performance Profiling).

---

## 3. Concept & Internal Architecture (Mendalam)

### Visual Rendering Lifecycle & The Cost of Visual Containers
Power BI Report Canvas bukanlah sekadar kanvas grafis statis, melainkan sebuah aplikasi web berbasis Angular/React-hybrid yang mengeksekusi visualisasi data melalui abstraksi iframe dan HTML5 Canvas/SVG.

```
+-----------------------------------------------------------------------------------+
|                              POWER BI RUNTIME ENGINE                              |
|                                                                                   |
|  [ User Action ] ---> [ Cross-Filter / Slicer Event Triggered ]                   |
|                                   |                                               |
|                                   v                                               |
|  +-----------------------------------------------------------------------------+  |
|  | VISUAL CONTAINER PIPELINE (Per Visual Engine)                               |  |
|  |                                                                             |  |
|  |  1. Visual Query Generation                                                 |  |
|  |     Transforms Visual Buckets (Axis, Legend, Values) into DAX Query         |  |
|  |                                |                                            |  |
|  |                                v                                            |  |
|  |  2. Query Dispatch to Analysis Services / VertiPaq                         |  |
|  |     +-------------------------+-------------------------+                   |  |
|  |     | Formula Engine (FE)     | Storage Engine (SE)     |                   |  |
|  |     | Evaluates MDX/DAX logic | Scans compressed memory |                   |  |
|  |     +-------------------------+-------------------------+                   |  |
|  |                                |                                            |  |
|  |                                v                                            |  |
|  |  3. Tabular Serialization                                                   |  |
|  |     Result Set -> Compressed JSON payload over WebSocket/HTTPS             |  |
|  |                                |                                            |  |
|  |                                v                                            |  |
|  |  4. Client-side Data Binding & Layout Engine                                |  |
|  |     Transforms JSON records -> D3.js / SVG / HTML5 Canvas Elements          |  |
|  |                                |                                            |  |
|  |                                v                                            |  |
|  |  5. Browser Paint & Compositing                                             |  |
|  |     Rasterization of visual shapes to client display hardware               |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

#### Komponen Kritis Siklus Rendering:
1. **Query Generation Overhead**: Setiap native visual pada canvas mengompilasi setidaknya **1 query DAX mandiri**. Jika sebuah halaman memuat 30 kartu KPI (Card Visual), maka client engine mengeksekusi 30 query secara konkuren. Hal ini menyebabkan antrean (*queueing*) pada HTTP connection pool browser (maksimal 6 koneksi simultan per domain) dan menghabiskan thread Analysis Services.
2. **DOM Node Inflation**: Satu visual container kompleks (misalnya Matrix dengan custom formatting) menghasilkan ratusan elemen `<div>`, `<svg>`, dan `<text>`. Jumlah total DOM node di atas 1.500 dalam satu halaman memicu *layout thrashing* dan penurunan drastis *frame rate* (jank) saat interaksi rendering.
3. **Data Serialization vs. Render Time**: Pada visual densitas tinggi (Scatter plot dengan 10.000 titik data), bottleneck bergeser dari VertiPaq ke client-side serialization dan kompilasi D3.js di browser thread.

### Arsitektur Micro-Visual Menggunakan Pure SVG injection via DAX
Untuk mengatasi overhead DOM dan visual container explosion, arsitektur enterprise menggunakan **Data URI Scheme** (`data:image/svg+xml;utf8,...`) yang diinjeksikan langsung ke dalam cell native Matrix atau Table via DAX String measure.

* Pendekatan ini mereduksi 50 visual terpisah menjadi **1 Matrix Visual tunggal**.
* Hanya **1 DAX Query** yang dikirimkan ke Analysis Services.
* Render engine hanya memproses satu visual container, meminimalkan memory footprint browser dari ratusan MB menjadi beberapa puluh KB.

---

## 4. Why & What

### Mengapa Information Design & Visual Hierarchy Berdampak pada Performa?
Dalam arsitektur data enterprise, **Information Design bukanlah persoalan estetika kosmetik, melainkan optimasi alokasi kognitif dan komputasi**.
* **Masalah**: Visual clutter (misal: 40 visual dalam 1 dashboard eksekutif) tidak hanya membingungkan pengguna (analisis terhambat), tetapi juga memicu starvation pada Analysis Services thread pool.
* **Solusi Arsitektural**: Mengadopsi prinsip *Visual Hierarchy 3-30-300*:
  * **3 Detik**: Memberikan status makro (KPI utama + status alert) secara instan.
  * **30 Detik**: Menampilkan visualisasi konteks (trend sparklines, variansi target, segmentasi).
  * **300 Detik**: Menyajikan detail granular (tabular drill-through, decompose tree, root-cause exploration).

### Apa itu Enterprise Semantic UX?
Enterprise Semantic UX adalah integrasi antara:
1. **Design Tokens**: Standardisasi warna, tipografi, dan padding melalui skema JSON terpusat.
2. **Semantic State Dynamic DAX**: Variansi warna dan format visual tidak diatur secara manual per visual (hardcoded), melainkan dikendalikan secara dinamis via metadata model (*Calculation Groups* & *Format Expressions*).
3. **Universal Accessibility (a11y)**: Penyusunan canvas report yang memenuhi spesifikasi WCAG 2.1 AA (kontras rasio minimal 4.5:1, dynamic screen reader focus, keyboard navigation traversal).

---

## 5. How (Workflow Detail)

Berikut adalah tahapan implementasi visual architecture enterprise dari hulu ke hilir:

```
[ Step 1: Token Definition ]
       |
       v  Mendefinisikan enterprise design system tokens (JSON theme schema)
[ Step 2: Semantic Layer Integration ]
       |
       v  Membangun Calculation Groups untuk Dynamic Formatting & Visual Indicators via TMDL
[ Step 3: High-Density Visual Engineering ]
       |
       v  Mengembangkan native DAX SVG Measures untuk visualisasi multi-metrik
[ Step 4: Canvas Layout & Viewport Structuring ]
       |
       v  Mengatur Visual Tree, Layering, dan Page Size (Grid 8px standard)
[ Step 5: a11y & Navigation Pipeline ]
       |
       v  Konfigurasi Programmatic Tab Order dan Accessible Dynamic Alt-Text
[ Step 6: Telemetry & Performance Auditing ]
          Validasi via Performance Analyzer & Browser Profiler (Target: Render < 1.2 detik)
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Monolithic Micro-Frontends vs. Consolidated Micro-Visuals
Bayangkan sebuah halaman dashboard seperti bandara internasional:
* **Pola Buruk (Visual Container Explosion)**: Anda membangun 30 terminal bandara mini terpisah untuk 30 penumpang. Masing-masing terminal membutuhkan tim sekuriti, check-in counter, landasan, dan ATC sendiri. Infrastruktur kolaps karena overhead koordinasi.
* **Pola Baik (Consolidated Layout & SVG Micro-Visuals)**: Anda membangun 1 terminal pusat modern yang sangat teratur. Setiap penumpang berjalan melalui gerbang terpadu, sistem navigasi tertera jelas di lantai dan papan digital, serta arus pergerakan teroptimasi secara aerodinamis.

### Diagram: Alur Render Query Batching vs. Render Thread

```
TRADITIONAL ANTI-PATTERN (Multiple Single Cards & Sparkline Visuals):
User Click 
   │
   ├──> Visual 1  ──(DAX Query 1)──> AS Engine ──(Wait/Queue)──> Render DOM 1
   ├──> Visual 2  ──(DAX Query 2)──> AS Engine ──(Wait/Queue)──> Render DOM 2
   ├──> Visual 3  ──(DAX Query 3)──> AS Engine ──(Wait/Queue)──> Render DOM 3
   ... (x30 Visuals: Browser Connection Starvation & High Thread Lock)

ENTERPRISE CONSOLIDATED PATTERN (1 Matrix Visual + DAX SVG Engine):
User Click 
   │
   └──> Consolidated Matrix ──(Single DAX Query)──> AS Engine (VertiPaq Batch)
                                                          │
                                                          ▼
                                              Tabular Stream Result
                                                          │
                                                          ▼
                                            [Browser Paints 1 HTML Element]
                                            (Sub-second rendering achieved)
```

---

## 7. Simple Example & Practical Example

### Simple Example: Dynamic Format String via Calculation Group
Penerapan string format dinamis berbasis mata uang tenant tanpa mengubah logika kalkulasi metrik dasar.

```dax
-- Didefinisikan dalam Calculation Item: "Dynamic Currency"
-- Expression:
SELECTEDMEASURE()

-- Format String Expression:
VAR _TenantCurrency = SELECTEDVALUE(dim_tenant[currency_code], "USD")
RETURN
    SWITCH(
        _TenantCurrency,
        "IDR", """Rp"" #,,0;(""Rp"" #,,0);""Rp"" 0",
        "USD", "$#,##0.00;($#,##0.00);$0.00",
        "EUR", "€#,##0.00;(€#,##0.00);€0.00",
        "#,##0.00"
    )
```

### Practical Example: Enterprise DAX SVG Micro-Bullet Chart
Measure berikut menghasilkan komponen visual Micro-Bullet Chart langsung ke dalam cell Matrix. Visual ini merender bar realisasi, target line, dan state background alert secara reaktif tanpa library visual pihak ketiga.

```dax
Revenue_Bullet_SVG = 
VAR _Actual = [Total Revenue]
VAR _Target = [Budget Revenue]
VAR _MaxScale = MAX(_Actual, _Target) * 1.15

-- Menghindari divide by zero
VAR _SafeScale = IF(_MaxScale = 0, 1, _MaxScale)

-- Kalkulasi koordinat SVG (dimensi viewbox: 200 x 30)
VAR _ActualWidth = MIN(200, INT(DIVIDE(_Actual, _SafeScale) * 200))
VAR _TargetX = MIN(198, INT(DIVIDE(_Target, _SafeScale) * 200))

-- Dynamic Palette berbasis Business Rule (WCAG Compliant)
VAR _IsGood = _Actual >= _Target
VAR _BarColor = IF(_IsGood, "%2300805A", "%23C4314B") -- URL encoded HEX: #00805A (Green), #C4314B (Red)
VAR _TargetColor = "%231A1A1A"                         -- #1A1A1A (Near Black)
VAR _BgTrackColor = "%23E1E4E8"                       -- #E1E4E8 (Muted Gray)

-- SVG XML Assembly
VAR _SVG = 
    "data:image/svg+xml;utf8," & 
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 30' width='100%25' height='100%25'>" &
        "<!-- Background Track -->" &
        "<rect x='0' y='6' width='200' height='18' rx='3' fill='" & _BgTrackColor & "' />" &
        
        "<!-- Performance Bar -->" &
        "<rect x='0' y='6' width='" & _ActualWidth & "' height='18' rx='3' fill='" & _BarColor & "' />" &
        
        "<!-- Target Marker Line -->" &
        "<line x1='" & _TargetX & "' y1='2' x2='" & _TargetX & "' y2='28' stroke='" & _TargetColor & "' stroke-width='3' stroke-linecap='round' />" &
    "</svg>"

RETURN
    IF(NOT(ISBLANK(_Actual)), _SVG, BLANK())
```
*Pastikan properti `Data Category` dari Measure ini diset ke **Image URL** pada Power BI Desktop.*

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Global Fintech Executive Operations Dashboard
* **Skala Data**: 280 Juta baris transaksi, 12 regional hub global, DirectQuery ke Snowflake + Import Dual Aggregations.
* **Problem**: 
  * Waktu render awal halaman mencapai **8,4 detik**.
  * Canvas berisi **42 visual individual**: 12 KPI card, 12 target comparison indicator, 12 sparklines, 6 operational charts.
  * Formula Engine (FE) mengalami antrean parah karena mengeksekusi 42 query simultan per filter selection.
  * Pengguna mobile dan laptop performa standar mengalami browser freezing (DOM nodes > 2.800).
* **Solusi Arsitektur UX & Semantik**:
  1. **Visual Consolidation**: Menghapus seluruh individual card dan sparkline visual. Menggantinya dengan **1 Visual Matrix terpadu** yang memuat seluruh KPI, Sparklines (DAX SVG), dan Bullet charts (DAX SVG).
  2. **TMDL Calculation Group**: Mengonsolidasikan komputasi Year-over-Year (YoY), Year-to-Date (YTD), dan Variance ke dalam satu Calculation Group tunggal, mengurangi kompleksitas model.
  3. **Metadata Semantic Layout**: Mengaplikasikan enterprise design tokens via custom Theme JSON untuk standardisasi padding, margin, dan warna tanpa manual visual override.
* **Hasil (Benchmarking)**:
  * Jumlah Visual Query per halaman: Turun dari **42 query** menjadi **4 query** (reduksi 90.4%).
  * Halaman Initial Render Time: Turun dari **8,4 detik** menjadi **850 milidetik**.
  * Total DOM Node: Turun dari **2.800+** menjadi **420**.
  * User Satisfaction Score (CSAT internal): Meningkat dari 2.4/5.0 menjadi 4.8/5.0.

---

## 9. Trade-offs

| Aspek Arsitektur | Opsi A: Native Modular Visuals | Opsi B: Consolidated DAX SVG Micro-Visuals | Analisis Konsekuensi Teknikal |
| :--- | :--- | :--- | :--- |
| **Visual Render Latency** | Tinggi (7.0 - 12.0s pada data besar) | Sangat Rendah (< 1.2s konsisten) | Opsi B mengeliminasi query queuing dan eksekusi event pipeline berganda di browser. |
| **Maintenance Complexity** | Rendah (Konfigurasi GUI Point-and-Click) | Menengah-Tinggi (Membutuhkan penguasaan SVG path syntax & DAX string manipulation) | Opsi B memerlukan engineer yang memahami rendering web, bukan sekadar report designer dasar. |
| **Tooltips & Interactivity** | Bawaan (Out-of-the-box Rich Tooltip) | Terbatas (Tooltip hanya pada cell level, bukan individual path di dalam SVG) | Opsi B mengorbankan mikro-interaksi hovering pada elemen detail visual demi performa rendering masif. |
| **Mobile Responsiveness** | Otomatis diatur via Power BI Mobile Layout | Perlu kalkulasi eksplisit viewBox SVG agar responsive | SVG membutuhkan pengaturan preserveAspectRatio yang tepat agar tidak terdistorsi saat di-render di layar kecil. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Antipattern: Slicer Overflow & Over-Synchronization
* **Kesalahan**: Menempatkan 15 slicer dropdown individual di kanvas dan menyinkronkan seluruh slicer antar 10 halaman report.
* **Dampak**: Setiap slicer memicu query evaluasi DISTINCT values ke Storage Engine. 15 slicer = 15 query tambahan sebelum visual utama dieksekusi.
* **Remediasi**: Gunakan **Filter Pane** bawaan untuk filter ad-hoc sekunder. Batasi slicer on-canvas hanya untuk 2-3 dimensi navigasi kritis dan nonaktifkan fitur *Sync Slicers* pada halaman yang tidak relevan secara kontekstual.

### 2. Antipattern: "Card Visual Explosion"
* **Kesalahan**: Membangun satu blok metrik menggunakan 3 visual bertumpuk: 1 Card untuk Label, 1 Card untuk Nilai, 1 Shape untuk Background.
* **Dampak**: 3 visual x 10 metrik = 30 visual container hanya untuk menampilkan angka dasar.
* **Remediasi**: Gunakan **New Card Visual (Core)** yang mendukung multiple measures, integrated visual states, dan dynamic sub-labels dalam satu visual container tunggal.

### 3. Masalah: SVG Image Render Blank / Broken Image
* **Akar Masalah**: Panjang string Data URI melebihi batas internal data-string Power BI (maksimal 32.766 karakter per text cell sebelum truncation) atau URL encoding karakter reserved (`#`, `%`, `<`).
* **Troubleshooting Engine**:
  * Encode seluruh warna HEX: Ganti `#` dengan `%23`.
  * Optimalkan path SVG: Hapus whitespace yang tidak perlu dan kurangi densitas decimal koordinat titik (gunakan `ROUND(_val, 1)` alih-alih float 10 digit).

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mempromosikan artefak report ke Production Workspace:

- [ ] **Batas Maksimal Visual**: Tidak lebih dari 8–10 visual container aktif dalam satu halaman dashboard.
- [ ] **Resolusi Grid Terpadu**: Mengaktifkan *Snap to Grid* dengan standard 8px visual grid spacing.
- [ ] **Eliminasi Hidden Visuals**: Bookmark tidak boleh menyembunyikan visual berat yang tetap mengeksekusi query di background (gunakan page branching jika layout berbeda signifikan).
- [ ] **Standarisasi Design Tokens (Theme JSON)**: Tidak ada styling manual (font, background, margins) yang di-override di level visual formatting pane.
- [ ] **Accessible Tab Order**: Seluruh elemen visual memiliki urutan navigasi keyboard terstruktur dari kiri-atas ke kanan-bawah melalui panel *Selection > Tab order*.
- [ ] **Accessible Color Contrast**: Rasio kontras teks utama terhadap background minimal 4.5:1 (Level AA) dan 3:1 untuk graphical elements.
- [ ] **Data Category Assignment**: Semua measure yang menghasilkan SVG telah tervalidasi memiliki `Data Category = Image URL`.
- [ ] **Performance Analyzer SLA**: Visual display time total di bawah 1.500 ms pada cold cache dan di bawah 800 ms pada warm cache.

---

## 12. Hands-on Practice

Simpan seluruh file implementasi berikut ke direktori: `hands-on/m02/`

### File 1: `hands-on/m02/theme_enterprise_tokens.json`
Theme JSON enterprise yang mendefinisikan color tokens, accessibility contrast, dan reset margin container.

```json
{
  "name": "Enterprise Design System Token",
  "dataColors": [
    "#0B5CAD",
    "#00805A",
    "#C4314B",
    "#F28B00",
    "#5C2D91",
    "#008272",
    "#A4262C",
    "#69797E"
  ],
  "background": "#FFFFFF",
  "foreground": "#1A1A1A",
  "tableAccent": "#0B5CAD",
  "visualStyles": {
    "*": {
      "*": {
        "outspace": [{ "margin": 4 }],
        "background": [{ "show": true, "color": { "solid": { "color": "#FFFFFF" } } }],
        "border": [{ "show": false }],
        "visualHeader": [{ "show": true }]
      }
    },
    "page": {
      "*": {
        "background": [{ "color": { "solid": { "color": "#F8F9FA" } }, "transparency": 0 }]
      }
    }
  }
}
```

### File 2: `hands-on/m02/sparkline_matrix.dax`
DAX Measure untuk merender multi-point mini trend line (SVG) dalam visual Matrix.

```dax
Sparkline_Trend_SVG = 
VAR _PointsCount = 12
VAR _YMinRange = 0

-- Ambil data series temporal
VAR _Table = 
    ADDCOLUMNS(
        SUMMARIZE(dim_calendar, dim_calendar[MonthOffset], dim_calendar[MonthShort]),
        "@Value", [Total Revenue]
    )
VAR _FilteredTable = 
    TOPN(_PointsCount, FILTER(_Table, dim_calendar[MonthOffset] <= 0), dim_calendar[MonthOffset], DESC)

VAR _MaxVal = MAXX(_FilteredTable, [@Value])
VAR _MinVal = MINX(_FilteredTable, [@Value])
VAR _ValRange = IF(_MaxVal = _MinVal, 1, _MaxVal - _MinVal)

-- Dimensi Canvas SVG: 150 x 30
VAR _StepX = DIVIDE(150, _PointsCount - 1)

-- Iterasi pembuatan SVG polyline coordinates
VAR _Coords = 
    CONCATENATEX(
        _FilteredTable,
        VAR _X = INT((dim_calendar[MonthOffset] + _PointsCount - 1) * _StepX)
        VAR _Y = INT(26 - DIVIDE([@Value] - _MinVal, _ValRange) * 22)
        RETURN _X & "," & _Y,
        " ",
        dim_calendar[MonthOffset],
        ASC
    )

VAR _LastValue = MAXX(TOPN(1, _FilteredTable, dim_calendar[MonthOffset], DESC), [@Value])
VAR _FirstValue = MINX(TOPN(1, _FilteredTable, dim_calendar[MonthOffset], ASC), [@Value])
VAR _LineColor = IF(_LastValue >= _FirstValue, "%2300805A", "%23C4314B")

RETURN
    IF(
        HASONEVALUE(dim_product[category]),
        "data:image/svg+xml;utf8," &
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 150 30' width='100%25' height='100%25'>" &
            "<polyline fill='none' stroke='" & _LineColor & "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' points='" & _Coords & "' />" &
        "</svg>",
        BLANK()
    )
```

### File 3: `hands-on/m02/calcgroup_semantic_formatting.tmdl`
Definisi TMDL (Tabular Model Definition Language) untuk Calculation Group visual semantic.

```tmdl
table 'Semantic UX Helper'
	lineageTag: 5b4d7c81-81d3-4f9e-a038-f1c6db984812

	calculationGroup
		precedence: 10

		calculationItem 'Variance Status Color' = 
			VAR _Val = SELECTEDMEASURE()
			RETURN
				IF ( _Val >= 0, "#00805A", "#C4314B" )

		calculationItem 'Dynamic Unit Formatter' = 
			SELECTEDMEASURE()
			formatStringDefinition = 
				VAR _Val = ABS(SELECTEDMEASURE())
				RETURN
					SWITCH(
						TRUE(),
						_Val >= 1e9, "$#,##0.00,,,""B""",
						_Val >= 1e6, "$#,##0.00,,""M""",
						_Val >= 1e3, "$#,##0.00,""K""",
						"$#,##0.00"
					)

	column 'UX Transformation'
		dataType: string
		sourceColumn: Name
		sortByColumn: Ordinal
		lineageTag: 7a8e9d21-4f12-4c22-b5e1-8f812b1d31a5

	column Ordinal
		dataType: int64
		isHidden
		sourceColumn: Ordinal
		lineageTag: 3c2d1e0f-9a8b-4c7d-8e6f-5a4b3c2d1e0f
```

---

## 13. Exercise

### Level Easy
1. Buat file JSON theme minimal yang mengesampingkan default font family seluruh visual menjadi `"Segoe UI Semibold"` dan warna kanvas dasar menjadi `#F3F4F6`.
2. Ubah properti accessibility pada 3 visual card sederhana dengan menambahkan Dynamic Alternative Text yang menyatakan kondisi metrik (contoh: *"Current Revenue is $12M, which is 5% above target"*).

### Level Medium
1. Kembangkan DAX SVG Measure bernama `KPI_Donut_Mini_SVG` yang menghasilkan Donut Chart mini dengan persentase pencapaian (ViewBox: 40 x 40). Implementasikan parameter `stroke-dasharray` dan `stroke-dashoffset` untuk menghitung rasio lingkaran.
2. Terapkan Calculation Group untuk membalikkan format angka negatif menjadi format akuntansi finansial standar `(1,234.00)` secara global tanpa mengubah measure original.

### Level Hard
1. Rancang arsitektur visual Matrix berdensitas tinggi untuk 50 portofolio investasi:
   * Menggabungkan Name, AUM (Asset Under Management), Target Line SVG, Micro-Sparkline 12-Bulan SVG, dan Status Badge SVG.
   * Total response time halaman tidak boleh melebihi 1 detik pada dataset 10 juta baris fact table.
   * Matrix harus 100% dapat di-traverse menggunakan navigasi keyboard murni (*Tab, Up, Down arrow keys*).

---

## 14. Challenge

### Skenario Kasus Kompleks (Production War-Room)
Anda bertindak sebagai Lead BI Architect pada platform e-commerce multinasional. Halaman utama **"Real-Time Merchant Operations"** memiliki latency p95 rendering sebesar **11.2 detik** di workspace Premium Gen2 saat peak traffic (Black Friday).

**Kondisi Teknis Saat Ini:**
* Menggunakan DirectQuery pushdown ke Google BigQuery via On-Premises Data Gateway (Enterprise Cluster).
* Halaman memuat 16 KPI cards, 4 visual donut charts, 6 column charts terpisah, dan 2 slicer multiselect dengan logic bidirectional cross-filtering.
* Memory usage browser melonjak hingga 1.4 GB di tab Edge/Chrome pengguna, menyebabkan crash pada mesin operasional gudang berspesifikasi RAM 4 GB.
* Stakeholder C-level menolak menyederhanakan data; mereka menuntut seluruh 26 indikator metrik tetap terlihat di halaman utama tanpa scroll vertikal.

**Tantangan Arsitektur:**
1. Desain ulang Information Architecture halaman tersebut ke dalam **maksimal 3 visual container visual utama**.
2. Rancang arsitektur DAX SVG multi-tier untuk menggantikan visual donut dan column charts ke dalam visual matrix agregat terpadu.
3. Eliminasi bottleneck On-Premises Data Gateway dengan meniadakan saturasi koneksi simultan (mereduksi 26 single queries per render cycle menjadi <= 3 batched queries).
4. Sediakan spesifikasi desain layout teknis lengkap (koordinat canvas, grid baseline, semantic tokens, WCAG contrast compliance schema) yang menjamin browser memory load stabil di bawah **150 MB** dan render time **< 1.5 detik**.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. **Mengapa menempatkan 30 visual card individual pada satu halaman sangat membebani kinerja rendering Power BI?**
   * A. Karena file `.pbix` akan melebihi batas ukuran 1 GB.
   * B. Karena setiap visual mengompilasi dan mengeksekusi setidaknya satu query DAX independen serta menciptakan isolated DOM elements.
   * C. Karena Analysis Services tidak mendukung visualisasi bertipe Card lebih dari 10 unit.
   * D. Karena Power BI service otomatis menolak me-render halaman dengan elemen melebihi 20 visual.

2. **Karakter apa yang WAJIB di-encode menjadi `%23` saat mengonstruksi dynamic SVG string di dalam DAX?**
   * A. Simbol Dollar (`$`)
   * B. Simbol Kurung Siku (`[`)
   * C. Simbol Pagar/Hash (`#`)
   * D. Simbol Titik Koma (`;`)

3. **Data Category apa yang harus dipilih pada metadata measure DAX agar teks SVG XML dirender sebagai visual grafis di Power BI?**
   * A. Web URL
   * B. Image URL
   * C. Barcode
   * D. Binary Object

4. **Berapa rasio kontras visual minimum (WCAG 2.1 Level AA) antara teks standar dengan background-nya?**
   * A. 2.0:1
   * B. 3.0:1
   * C. 4.5:1
   * D. 7.0:1

5. **Di mana arsitek visual mengatur urutan navigasi fokus keyboard (keyboard tab traversal) pada Power BI Desktop?**
   * A. File > Options > Accessibility Settings
   * B. View > Selection Pane > Tab Order
   * C. Format Pane > Page Size
   * D. Model View > Relationship Matrix

---

### Bagian 2: Intermediate (5 Soal)
6. **Apa keuntungan arsitektural utama menggunakan Calculation Groups dibandingkan membuat individual measure terpisah untuk formatting variansi?**
   * A. Calculation Groups mengeksekusi kalkulasi langsung di browser tanpa menyentuh Analysis Services.
   * B. Calculation Groups memungkinkan modifikasi logika ekspresi atau string format secara dinamis terhadap measure yang sedang dievaluasi (`SELECTEDMEASURE()`) secara terpusat.
   * C. Calculation Groups otomatis mengubah tipe data tabular menjadi visual bitmap.
   * D. Calculation Groups menonaktifkan fitur DirectQuery sehingga render lebih cepat.

7. **Pada kasus visual matrix yang lambat merender ribuan baris SVG, apa penyebab utama bottleneck jika VertiPaq SE CPU Time tercatat mendekati 0 ms?**
   * A. Jaringan internet gateway putus.
   * B. Client-side browser thread mengalami layout thrashing saat merender ribuan string SVG kompleks ke dalam DOM.
   * C. VertiPaq kehabisan disk space cache.
   * D. Driver kartu grafis GPU klien tidak kompatibel dengan Power BI Desktop.

8. **Bagaimana cara mengamankan visual sparkline SVG agar tidak crash saat dataset menghasilkan rentang data flat/konstan (Max Value = Min Value)?**
   * A. Menggunakan exception handling `TRY...CATCH` di DAX.
   * B. Menghitung range menggunakan formula safe scale `IF(_MaxVal = _MinVal, 1, _MaxVal - _MinVal)` untuk mencegah *divide-by-zero*.
   * C. Menghapus data flat dari fact table sebelum di-load.
   * D. Mengonversi visual sparkline menjadi format GIF animasi.

9. **Apa fungsi dari atribut `viewBox='0 0 200 30'` pada root element SVG yang di-render di dalam cell Matrix Power BI?**
   * A. Membatasi alokasi RAM browser sebesar 200KB per 30 visual.
   * B. Mendefinisikan sistem koordinat internal dan aspek rasio SVG sehingga grafik dapat diskalakan (scalable) secara proporsional mengikuti lebar kolom.
   * C. Mengunci ukuran tabel agar tidak bisa di-resize oleh pengguna akhir.
   * D. Menginstruksikan DirectQuery untuk mengambil 200 baris pertama data.

10. **Manakah dari pendekatan styling berikut yang paling tepat diterapkan pada skala enterprise untuk menjaga konsistensi visual di 50 report terpisah?**
    * A. Menyalin visual secara manual dari report template master.
    * B. Mengonfigurasi properti border dan font pada format pane tiap visual satu per satu.
    * C. Mengimpor file Enterprise Theme JSON terpusat ke dalam workspace template dan mendistribusikannya via organizational theme library.
    * D. Menggunakan bookmark untuk menyimpan preferensi style masing-masing report.

---

### Bagian 3: Production Case Scenarios (3 Soal)

11. **Skenario 1**: Sebuah report finance memiliki 1 visual Matrix besar. Anda menambahkan measure SVG Bullet Chart ke dalam kolom matrix tersebut. Ketika dijalankan di laptop C-level executive, report tersebut crash dan menampilkan pesan *"Out of Memory"*. Saat diperiksa di DAX Studio, data query hanya menghasilkan 5.000 baris. Apa akar masalah arsitektur teknikalnya dan bagaimana solusinya?
    * A. **Masalah**: 5.000 baris string SVG resolusi tinggi dengan koordinat poligon yang rumit menyebabkan browser DOM kehabisan memori saat mengompilasi grafis.  
      **Solusi**: Terapkan virtualisasi data (halaman/top-N pagination) atau sederhanakan path SVG menggunakan native horizontal bar (`<rect>`) sederhana dengan koordinat yang dibulatkan (`INT`).
    * B. **Masalah**: Ukuran memory VertiPaq Analysis Services melebihi batas 100 GB.  
      **Solusi**: Scale-up kapasitas Power BI Premium dari P1 ke P3.
    * C. **Masalah**: Tipe data kolom Matrix diubah menjadi Binary secara sepihak oleh DirectQuery.  
      **Solusi**: Re-import dataset dari SQL Server menggunakan mode Dual.
    * D. **Masalah**: SVG tidak mendukung warna HEX di perangkat laptop eksekutif.  
      **Solusi**: Ubah seluruh SVG menjadi gambar file PNG statis di folder lokal.

12. **Skenario 2**: Anda mengaudit halaman dashboard yang lambat (render 9 detik). Anda membuka *Performance Analyzer* dan melihat metrik berikut pada salah satu Slicer:
    * DAX Query: 4.800 ms
    * Visual Display: 120 ms
    * Other (Wait Time): 4.080 ms  
    Apa yang sebenarnya terjadi di balik layar dan langkah mitigasi yang paling tepat?
    * A. Browser lambat memproses CSS; solusinya adalah restart browser.
    * B. Slicer tersebut mengantre (*queueing*) karena ada terlalu banyak visual lain yang dieksekusi bersamaan, menghabiskan thread Analysis Services dan pool HTTP browser. Solusinya adalah mengurangi visual di kanvas dan mematikan interaksi silang yang tidak perlu (*Edit Interactions*).
    * C. Slicer memiliki resolusi gambar terlalu besar. Solusinya perkecil ukuran teks slicer.
    * D. DirectQuery cache expired. Solusinya ubah query mode menjadi pushdown aggregations.

13. **Skenario 3**: Sebuah organisasi perbankan mewajibkan seluruh dashboard internal lolos audit kepatuhan tuna netra (Screen Reader Accessibility Audit). Developer telah menambahkan Dynamic Alt Text pada semua visual, tetapi penguji screen-reader mengeluhkan urutan pembacaan metrik melompat secara acak (misal: dari Footer langsung ke KPI tengah, lalu ke Header). Apa langkah remediation yang harus diambil di tingkat metadata layout?
    * A. Menulis ulang kode DAX measures dari awal.
    * B. Mengatur urutan layer visual di Selection Pane secara acak hingga benar.
    * C. Mengonfigurasi ulang urutan pada *Selection Pane > Tab Order* secara sekuensial dari kiri-ke-kanan dan atas-ke-bawah, serta mengaktifkan flag un-tabbable (`Hide from tab order`) pada elemen hiasan dekoratif seperti garis dan shape statis.
    * D. Menyetel background visual menjadi hitam-putih (monochrome).

---

### Kunci Jawaban & Rasional Singkat

#### Bagian 1: Basic
1. **B** - Setiap visual membebani frontend DOM dan memicu thread DAX individual ke backend Analysis Services.
2. **C** - Karakter `#` merepresentasikan fragment identifier dalam standar URI; harus di-escape menjadi `%23`.
3. **B** - `Image URL` memberitahu browser engine untuk menginterpretasikan string Data URI sebagai payload grafik visual.
4. **C** - WCAG 2.1 AA memandatkan rasio kontras minimal 4.5:1 untuk teks berukuran reguler.
5. **B** - Tab order dikelola secara eksplisit melalui Selection Pane di tab View.

#### Bagian 2: Intermediate
6. **B** - Calculation Groups bertindak sebagai middleware dinamis untuk logic ekspresi dan string format pada measure yang aktif.
7. **B** - Jika engine Analysis Services cepat (0 ms), jeda panjang di visual display disebabkan oleh client-side UI thread yang mengalami overhead parsing DOM/SVG.
8. **B** - Pembagian dengan angka nol (*divide-by-zero*) menghasilkan status invalid atau tak hingga pada koordinat SVG, merusak rendering vector.
9. **B** - Atribut `viewBox` mendefinisikan rasio aspek grafis vektor internal agar dapat beradaptasi secara fleksibel terhadap kontainer tabel.
10. **C** - File Theme JSON mendistribusikan konfigurasi styling secara deterministik dan terpusat tanpa risiko human error.

#### Bagian 3: Production Cases
11. **A** - Merender 5.000 SVG path kompleks secara simultan di browser memicu DOM heap exhaustion; reduksi kompleksitas path dan gunakan pembulatan koordinat integer.
12. **B** - Tingginya nilai "Other (Wait Time)" menunjukkan visual menunggu antrean slot eksekusi thread Analysis Services atau keterbatasan koneksi paralel browser.
13. **C** - Urutan pembacaan screen reader diatur secara mutlak oleh Tab Order list; elemen dekoratif wajib disembunyikan agar pembacaan tidak terdistraksi.

---

## 16. Summary

* **Visual Architecture adalah Performance Architecture**: Setiap elemen yang diletakkan di atas kanvas Power BI memicu biaya komputasi berlapis—mulai dari serialisasi query di Formula Engine hingga rendering alokasi memori DOM di browser.
* **Information Design Mengatur Beban Kognitif & Komputasi**: Menjalankan prinsip hierarki visual *3-30-300* memastikan pengguna mendapatkan wawasan bisnis secara cepat tanpa memaksa sistem memproses puluhan query visual yang tidak esensial.
* **High-Density Consolidation via SVG**: Mengintegrasikan grafik mikro (Sparklines, Bullet-charts) langsung via DAX Image URI ke dalam visual tunggal (Matrix) terbukti memangkas waktu load dashboard eksekutif dari detik ke sub-detik secara deterministik.
* **Semantic Decoupling via TMDL & Design Tokens**: Standarisasi enterprise dijamin melalui pemisahan antara layout styling (Theme JSON), dynamic formatting (Calculation Groups), dan data retrieval (VertiPaq/DirectQuery Engine).