# Bab 05: Information Design, UX Semantics & Visual Hierarchy

## Module 01: Fondasi UX Semantics, Design Systems, dan Visual Hierarchy dalam Power BI

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Merancang Semantic Design System Enterprise**: Mengonstruksi tokenisasi desain (warna, tipografi, grid layout, dan spacing) ke dalam Power BI Theme JSON Schema v2 yang terintegrasi dengan standar aksesibilitas WCAG 2.1 AA.
- **Mengimplementasikan IBCS (International Business Communication Standards)**: Menerapkan notasi visual standar industri untuk membedakan data *Actual*, *Plan*, *Forecast*, dan *Previous Year* secara deterministik pada visual native dan custom visuals.
- **Membangun Dynamic Semantic DAX untuk UX**: Mengembangkan pola DAX (*Data Analysis Expressions*) tingkat lanjut untuk conditional formatting, dynamic titles, micro-copy naratif otomatis, dan dynamic SVG data URI indicators berbasis konteks filter data.
- **Mengoptimalkan Visual Canvas Engine**: Menekan latensi rendering browser/client-side dengan mengeliminasi *visual bloat*, meminimalkan query per-canvas, dan menyusun layer hierarchy menggunakan *Selection Pane* dan *Grouping* yang terotomatisasi.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Penyajian data analitis pada skala enterprise bukan sekadar persoalan estetika grafis, melainkan arsitektur transmisi kognitif: meminimalkan *extraneous cognitive load* (beban kognitif asing) agar kapasitas kognitif pengguna teralokasi penuh pada *germane cognitive load* (pemrosesan wawasan dan pengambilan keputusan).

```
[ Mental Model: Pipeline Transmisi Kognitif Visual ]

Raw Enterprise Data
      │
      ▼
┌───────────────────────────┐
│ Semantic Data Modeling    │ (Tabular / Dimensional Model)
└─────────────┬─────────────┘
              │ DAX Measures & Context Transition
              ▼
┌───────────────────────────┐
│ UX Semantic Layer         │ (Status, Thresholds, Variances, Intent)
└─────────────┬─────────────┘
              │ Design Tokens & Visual Rules (IBCS / WCAG)
              ▼
┌───────────────────────────┐
│ Visual Hierarchy & Layout │ (Z-Pattern, Card KPI, Drill-path)
└─────────────┬─────────────┘
              │ Pre-attentive Processing (< 200 ms)
              ▼
Executive / Operational Decision
```

#### Prinsip Gestalt dalam Power BI Canvas
1. **Proximity (Kedekatan)**: Elemen visual yang berdekatan secara spasial dianggap berada dalam satu kelompok fungsional. Dalam Power BI, visual metrik KPI diletakkan bersebelahan dengan visual kontributor variansi (*decomposition tree* atau *waterfall*).
2. **Similarity (Kesamaan)**: Kesamaan warna, bentuk, dan ukuran menandakan status semantik yang sama. Warna merah pada seluruh report page hanya boleh merepresentasikan satu status: *Negatif/Di bawah Target/Ekspektasi Buruk*.
3. **Common Region (Area Bersama)**: Memanfaatkan visual *Shape/Card Containers* untuk mengikat filter (slicers) dengan visual dependen guna mencegah ambiguitas konteks filter.
4. **Focal Point (Hierarki Visual)**: Elemen dengan kontras visual paling tinggi (misal: Card Visual 44pt Semi-Bold dengan delta percentage berbingkai kontras) menjadi titik tangkap mata pertama sebelum visualisasi tren garis sekunder.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di lingkungan korporat, kegagalan adopsi platform Business Intelligence (BI) dan kesalahan interpretasi metrik kritis 80% bersumber dari defisit desain informasi:
- **Dashboard Jam Pasir (Visual Bloat)**: Dashboard operasional memuat 40 visual terpisah pada satu canvas. Hal ini memicu 40 DAX queries paralel secara konkuren ke VertiPaq engine, memperlambat rendering hingga >8 detik dan membingungkan eksekutif (*decision paralysis*).
- **Semantik Inkonsisten**: Metrik *Margin %* menggunakan palet hijau di Halaman A, tetapi di Halaman B palet hijau menandakan *Gross Sales*, memicu disorientasi kognitif saat cross-analysis.
- **Ketidaksesuaian Aksesibilitas**: Sekitar 8% populasi pria mengalami *Color Vision Deficiency* (CVD/buta warna Deuteranopia/Protanopia). Penggunaan gradien *Green/Red* murni tanpa redundansi bentuk (shapes/icons) menghasilkan visualisasi data yang tidak terbaca oleh stakeholder terkait.

Penerapan *enterprise-grade UX semantics* mentransformasi Power BI dari sekadar "kanvas gambar statistik" menjadi instrumen sistem saraf operasional perusahaan yang deterministik, responsif, dan patuh standar regulasi.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut memetakan arsitektur end-to-end integrasi Design System, Custom Theme JSON, DAX Dynamic Layer, dan Visual Engine di Power BI.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DESIGN SYSTEM REPOSITORY                        │
│   (Figma Tokens / Design Tokens JSON: Colors, Typography, Spacing)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼ Python / CI-CD Compiler
┌────────────────────────────────────────────────────────────────────────┐
│                       POWER BI THEME JSON SCHEMA                       │
│  ┌───────────────────────┐ ┌──────────────────┐ ┌────────────────────┐ │
│  │ dataColors (Palet)    │ │ visualStyles     │ │ textClasses        │ │
│  │ Base: Primary/Neutral │ │ Global Container │ │ Callout: 32pt/44pt │ │
│  │ Semantic: Alert/Good  │ │ Borders/Padding  │ │ Body: 10pt/11pt    │ │
│  └───────────────────────┘ └──────────────────┘ └────────────────────┘ │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Ingest ke PBIX Template (.pbit)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     CANVAS RUNTIME ARCHITECTURE                        │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Level 1: Global Context Bar (Breadcrumbs, Slicers, Global State) │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Level 2: Executive Summary (Semantic Cards + Inline Sparklines)  │  │
│  │          [KPI 1: $14.2M]   [KPI 2: +4.8% YoY]   [Status: OK]     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────┐ ┌──────────────────────────────┐  │
│  │ Level 3: Structural Breakdown   │ │ Level 4: Context / Outliers  │  │
│  │ (IBCS Variance / Waterfall)     │ │ (Matrix Grid / Top-N Drivers)│  │
│  │                                 │ │ Dynamic SVG Alerts via DAX   │  │
│  └─────────────────────────────────┘ └──────────────────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        DAX UX SEMANTIC ENGINE                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Measures Format Strings (Dynamic Format Strings per Currencies) │  │
│  │ Dynamic Color Resolvers (Hex Strings: #D9381E vs #00875A)        │  │
│  │ SVG String Builders (data:image/svg+xml;utf8,<svg>...)           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Notasi IBCS (International Business Communication Standards)
IBCS menetapkan standarisasi representasi numerik dan grafis:
1. **Waktu / Temporal**: Sumbu horizontal selalu merepresentasikan dimensi waktu dari kiri ke kanan.
2. **Kategori Struktur**: Sumbu vertikal digunakan untuk hierarki atau perbandingan kategori (divisi, produk, geografi).
3. **Scenarios Kodifikasi Visual**:
   - **Solid Fill (Hitam/Abu-abu Gelap)**: Merepresentasikan nilai aktual (*Actual / AC*).
   - **Hollow / Outline (Garis Luar)**: Merepresentasikan rencana anggaran (*Plan / PL*).
   - **Hatched / Arsiran diagonal**: Merepresentasikan perkiraan (*Forecast / FC*).
   - **Abu-abu terang**: Merepresentasikan periode tahun lalu (*Previous Year / PY*).
4. **Variansi Relatif vs Absolut**:
   - Variansi Absolut ($\Delta = AC - PL$): Ditampilkan menggunakan bar chart horizontal/vertikal.
   - Variansi Relatif ($\Delta\% = \frac{AC - PL}{PL}$): Ditampilkan menggunakan pin/lollipop chart.

#### B. Palet Semantik dan WCAG 2.1 AA Compliance
Rasio kontras luminans antara teks/objek visual utama terhadap background kanvas minimum wajib bernilai:
- **4.5:1** untuk teks reguler (< 18pt non-bold, < 14pt bold).
- **3.0:1** untuk elemen grafis interaktif dan teks ukuran besar ($\ge$ 18pt regular, $\ge$ 14pt bold).

Gunakan tri-warna semantik fungsional:
- **Neutral Primary**: `#1E242B` (Dark Slate) untuk teks judul & angka utama.
- **Neutral Canvas**: `#F4F5F7` (Off-white/Light Gray) untuk mengurangi *eye-strain* dibandingkan `#FFFFFF` kontras tinggi.
- **Positive Variance**: `#00875A` (Forest Green - WCAG compliant pada background light).
- **Negative Variance**: `#DE350B` (Crimson Red - bukan saturated bright red).
- **Benchmark / Baseline**: `#5E6C84` (Slate Neutral).

#### C. Visual Layout: F-Pattern vs Z-Pattern Scanning
- **Z-Pattern Grid**: Diterapkan pada dashboard eksekutif dengan kepadatan data sedang. Alur pandang bergerak dari kiri atas (Logo, Global Filter, Entity) $\rightarrow$ kanan atas (Date, Dynamic Status) $\rightarrow$ kiri bawah (Core Trend Waterfall) $\rightarrow$ kanan bawah (Detail Breakdown).
- **F-Pattern Grid**: Diterapkan pada monitoring operasional/analitik detail tinggi. Bagian atas diisi oleh metrik KPI summary cards, diikuti visualisasi data berdensitas tinggi di panel kiri bawah (Matrix tabular), dan panel analitik pendukung di sisi kanan.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem desain analitik end-to-end yang terdiri dari skrip Python generator token tema Power BI dan kode DAX untuk kalkulasi semantik berbasis IBCS serta Dynamic SVG rendering.

#### A. Theme Automation Engine (Python)

Skrip ini memvalidasi kontras warna menggunakan algoritma W3C relative luminance dan mengompilasi schema JSON tema resmi Power BI.

```python
"""
Power BI Semantic Theme Compiler & Contrast Validator
Engineered to output Production-Ready Power BI Theme Schema v2.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import json
import math
import sys


@dataclass(frozen=True)
class ColorToken:
    name: str
    hex_code: str


def srgb_to_linear(channel: float) -> float:
    """Converts 8-bit sRGB channel normalized to [0, 1] into linear luminance."""
    return channel / 12.92 if channel <= 0.04045 else math.pow((channel + 0.055) / 1.055, 2.4)


def calculate_relative_luminance(hex_str: str) -> float:
    """Calculates relative luminance according to W3C WCAG 2.1 definitions."""
    hex_clean = hex_str.lstrip('#')
    r = int(hex_clean[0:2], 16) / 255.0
    g = int(hex_clean[2:4], 16) / 255.0
    b = int(hex_clean[4:6], 16) / 255.0

    r_lin = srgb_to_linear(r)
    g_lin = srgb_to_linear(g)
    b_lin = srgb_to_linear(b)

    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(foreground_hex: str, background_hex: str) -> float:
    """Calculates the WCAG contrast ratio between two hex colors."""
    lum1 = calculate_relative_luminance(foreground_hex)
    lum2 = calculate_relative_luminance(background_hex)
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


class EnterpriseThemeBuilder:
    def __init__(self, theme_name: str, background_color: str):
        self.theme_name = theme_name
        self.background_color = background_color
        self.data_colors: List[ColorToken] = []

    def add_palette_token(self, name: str, hex_code: str) -> None:
        contrast = calculate_contrast_ratio(hex_code, self.background_color)
        if contrast < 3.0:
            print(
                f"[WARNING] Token '{name}' ({hex_code}) has a contrast ratio of {contrast:.2f}:1 "
                f"against background ({self.background_color}), failing WCAG UI Component threshold (3.0:1).",
                file=sys.stderr,
            )
        self.data_colors.append(ColorToken(name=name, hex_code=hex_code))

    def build_pbi_theme_json(self) -> Dict:
        """Constructs the valid Power BI Theme JSON."""
        return {
            "name": self.theme_name,
            "dataColors": [token.hex_code for token in self.data_colors],
            "background": self.background_color,
            "foreground": "#1E242B",
            "tableAccent": "#0052CC",
            "visualStyles": {
                "*": {
                    "*": {
                        "visualHeader": [
                            {"visible": True}
                        ],
                        "background": [
                            {"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}
                        ],
                        "border": [
                            {"show": False}
                        ],
                        "dropShadow": [
                            {"show": False}
                        ],
                        "padding": [
                            {"top": 8, "bottom": 8, "left": 8, "right": 8}
                        ]
                    }
                },
                "card": {
                    "*": {
                        "labels": [
                            {"color": {"solid": {"color": "#1E242B"}}, "fontSize": 28, "fontFamily": "Segoe UI"}
                        ],
                        "categoryLabels": [
                            {"color": {"solid": {"color": "#6B778C"}}, "fontSize": 10, "fontFamily": "Segoe UI"}
                        ]
                    }
                }
            },
            "textClasses": {
                "callout": {"fontSize": 32, "fontFace": "Segoe UI Semibold", "color": "#1E242B"},
                "title": {"fontSize": 14, "fontFace": "Segoe UI Semibold", "color": "#1E242B"},
                "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#253858"},
                "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": "#6B778C"}
            }
        }


if __name__ == "__main__":
    builder = EnterpriseThemeBuilder(
        theme_name="Enterprise_IBCS_Compliant_V1",
        background_color="#F4F5F7"
    )

    # Core IBCS Palette
    builder.add_palette_token("Actual_Primary", "#172B4D")      # High contrast dark slate
    builder.add_palette_token("Variance_Positive", "#00875A")  # Forest green (4.5:1 compliant)
    builder.add_palette_token("Variance_Negative", "#DE350B")  # Crimson Red (4.5:1 compliant)
    builder.add_palette_token("Plan_Secondary", "#5E6C84")     # Slate grey
    builder.add_palette_token("Accent_Interactive", "#0052CC") # Corporate Blue

    theme_payload = builder.build_pbi_theme_json()
    output_filename = "enterprise_theme.json"

    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(theme_payload, f, indent=2)

    print(f"Theme successfully compiled to {output_filename}")
```

---

#### B. Dynamic UX Semantics & SVG Indicators (DAX)

Kumpulan measure DAX berikut mengeksekusi standarisasi IBCS: mengomputasi variansi data, dynamic visual color mapping, dan me-render dynamic SVG bullet indicator langsung di dalam Card/Matrix Visual tanpa custom visual pihak ketiga.

```dax
----------------------------------------------------------------------
-- 1. BASE MEASURES: Actuals, Plan, Variance
----------------------------------------------------------------------
Total Revenue AC = 
SUM ( 'FactSales'[Revenue] )

Total Revenue PL = 
SUM ( 'FactSales'[BudgetRevenue] )

-- Variance AC vs PL (Absolute)
Var Revenue Abs = 
VAR _AC = [Total Revenue AC]
VAR _PL = [Total Revenue PL]
RETURN
    IF ( NOT ISBLANK ( _AC ) && NOT ISBLANK ( _PL ), _AC - _PL, BLANK () )

-- Variance AC vs PL (Relative %)
Var Revenue Pct = 
VAR _Abs = [Var Revenue Abs]
VAR _PL = [Total Revenue PL]
RETURN
    DIVIDE ( _Abs, _PL, BLANK () )

----------------------------------------------------------------------
-- 2. SEMANTIC COLOR RESOLVERS (HEX Mapping)
----------------------------------------------------------------------
-- Digunakan untuk Conditional Formatting: Background / Font
Format Color Var Revenue = 
VAR _VarPct = [Var Revenue Pct]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( _VarPct ), "#00000000", -- Transparent / fallback
        _VarPct >= 0, "#00875A",         -- Accessible Green
        _VarPct < 0, "#DE350B"           -- Accessible Red
    )

----------------------------------------------------------------------
-- 3. DYNAMIC METRIC CALLOUT WITH MICRO-COPY (Executive Summary)
----------------------------------------------------------------------
UX Executive Header KPI = 
VAR _AC = [Total Revenue AC]
VAR _VarPct = [Var Revenue Pct]
VAR _DirectionText = 
    IF ( _VarPct >= 0, "surpassing", "lagging" )
VAR _FormattedAC = FORMAT ( _AC, "$#,##0.0,, 'M'" )
VAR _FormattedPct = FORMAT ( ABS ( _VarPct ), "0.0%" )
RETURN
    "Revenue sits at " & _FormattedAC & ", " & _DirectionText & 
    " Plan by " & _FormattedPct & " YTD."

----------------------------------------------------------------------
-- 4. DYNAMIC SVG METRIC BADGE (Visual Micro-Indicator)
-- Me-render Data URI SVG secara deterministik untuk Column Matrix/Table
----------------------------------------------------------------------
SVG Dynamic Trend Indicator = 
VAR _VarPct = [Var Revenue Pct]
VAR _FillColor = [Format Color Var Revenue]
VAR _ArrowPath = 
    IF ( 
        _VarPct >= 0, 
        "M12 4 L4 16 L20 16 Z",        -- Segitiga Panah Ke Atas
        "M12 20 L4 8 L20 8 Z"          -- Segitiga Panah Ke Bawah
    )
VAR _SvgHeader = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='24' height='24'>"
VAR _SvgContent = "<path d='" & _ArrowPath & "' fill='" & _FillColor & "'/>"
VAR _SvgFooter = "</svg>"
RETURN
    IF ( 
        ISBLANK ( _VarPct ), 
        BLANK (), 
        _SvgHeader & _SvgContent & _SvgFooter 
    )
```

---

### 7. Edge Cases & Failure Modes

| Skenario Error / Edge Case | Dampak Operasional | Solusi Teknis Teruji (Mitigasi) |
| :--- | :--- | :--- |
| **Nilai Variansi Null/Zero Division** | KPI Card menampilkan `Infinity%`, `NaN`, atau blank visual crash. | Gunakan fungsi `DIVIDE(Numerator, Denominator, AlternateResult)` secara ketat dengan fallback parameter eksplisit `BLANK()` atau `0.0`. Validasi konteks filter menggunakan `ISBLANK()`. |
| **High-DPI / Multi-Monitor Scaling** | Teks callout terpotong (*clipped*), visual scrollbar muncul tanpa disengaja. | Matikan opsi *Auto-scale font* pada Card Visuals baru (New Card Visual). Kunci resolusi kanvas ke rasio standar 16:9 fixed pixels (1280x720 atau 1920x1080). Jangan gunakan dynamic sizing berbasis canvas percentage. |
| **Color Vision Deficiency (CVD)** | Stakeholder protanopia/deuteranopia tidak dapat membedakan status positif vs negatif. | Terapkan *Redundant Coding*: Jangan bergantung hanya pada warna. Tambahkan ikon delta ($\blacktriangle$ / $\blacktriangledown$), arah stroke, atau text badge pendukung di samping metrik nilai. |
| **SVG String Truncation** | String URI SVG terpotong di engine rendering Power BI jika ukuran data measure > 32.766 karakter. | Jaga agar ukuran SVG payload minimalis (< 1KB). Hindari menyematkan path SVG yang kompleks (*vector bloat*). Gunakan *viewBox* standard (misal: 0 0 24 24) dengan path primitif (`path`, `circle`, `rect`). |
| **Filter-Induced Information Loss** | Drilldown pengguna menghasilkan kartu KPI tanpa konteks unit (`$M` vs `$K`). | Terapkan *Dynamic Format Strings* (fitur native PBI) berbasis ekspresi DAX: Mengubah ekspresi format string secara otomatis ketika nilai aggregate turun di bawah threshold tertentu (misal: `$#,##0.0,, "M"` jika $\ge 10^6$, else `$#,##0.0, "K"`). |

---

### 8. Trade-offs & Alternatif Solusi

| Pendekatan / Pola | Keuntungan | Kerugian / Trade-off | Kapan Harus Digunakan |
| :--- | :--- | :--- | :--- |
| **Single Complex Matrix + Embedded SVGs** | Menurunkan jumlah total query kanvas hingga 75%. Render cepat, performa visual konsisten. | Kompleksitas *maintenance* DAX SVG sangat tinggi; visual tidak memiliki interaktivitas hover standar native visuals. | Dashboard eksekutif performa tinggi yang memuat banyak metrik tabular per page. |
| **Multiple Isolated Native Card Visuals** | Pembangunan kanvas sangat cepat; interaktivitas bawaan (*cross-highlight*, native tooltips). | Beban engine ekstrim (setiap Card mengeksekusi 1 query independen). Menghasilkan latensi tinggi pada DirectQuery. | Prototyping awal atau canvas monitoring sederhana dengan jumlah metrik $\le 6$. |
| **Custom Visuals Marketplace (e.g., Zebra BI)** | 100% patuh standar IBCS out-of-the-box tanpa kode DAX kustom; layout responsif optimal. | Lisensi berbayar; potensi audit sekuritas pihak ketiga; dependensi pada maintainer eksternal. | Perusahaan berskala enterprise dengan budget khusus reporting standards yang memprioritaskan TTM (*Time to Market*). |
| **Global JSON Theme Styling** | Memastikan uniformitas CSS/Hex seluruh visual; governance terpusat; pembaruan visual instan. | Tidak semua properti visual native terekspos dalam JSON Theme Schema v2; dokumentasi schema Microsoft terkadang tertinggal. | Mandatori untuk semua deployment Power BI skala institusional/enterprise. |

---

### 9. Best Practices & Standar Industri

1. **Konstruksi Grid Berdasarkan Modul 8-Point Spacing**: Semua margin antar-visual, padding container, dan whitespace harus merupakan kelipatan dari **8px** (8px, 16px, 24px, 32px). Menghindari layout yang terlihat renggang atau asimetris.
2. **Eliminasi Decorative Chart Junk**: Hilangkan background 3D, border visual tebal, drop-shadow pekat, garis grid horizontal/vertikal dengan kontras tinggi (turunkan transparansi gridline ke $\ge 80\%$ atau hilangkan sepenuhnya jika nilai data labels sudah ada).
3. **Kategorisasi Hirarki Tipografi**:
   - Primary Metric (Callout): Segoe UI Bold, 24pt s.d. 32pt.
   - Section / Category Header: Segoe UI Semibold, 12pt s.d. 14pt.
   - Body / Data Matrix Cells: Segoe UI Regular, 9pt s.d. 10pt.
   - Metadata / Context Footers: Segoe UI, 8pt s.d. 9pt dengan color contrast non-distraktif (`#6B778C`).
4. **Synchronized Slicing & Filter Visibility**: Jangan menduplikasi slicer yang sama di setiap tab tanpa *Sync Slicers*. Manfaatkan *Filter Pane* bawaan untuk filter sekunder dan sediakan kanvas utama hanya untuk filter interaktif berorientasi aksi langsung (misal: Date Grain, Division Toggle).
5. **Deterministic Selection Pane Naming**: Seluruh visual di *Selection Pane* wajib diberi nama yang jelas (contoh: `grp_executive_kpis`, `card_rev_actual`, `chart_waterfall_variance`). Ini esensial untuk visual layering, screen reader navigation, dan maintainability tim.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda ditugaskan mendesain ulang (refactor) kanvas ringkasan eksekutif penjualan bulanan perusahaan yang mengalami masalah visual clutter, penurunan performa rendering, dan tidak patuh standar kontras warna enterprise.

#### Tahap 1: Setup Theme JSON
1. Jalankan skrip Python pada Bab 6 Bagian A untuk menghasilkan `enterprise_theme.json`.
2. Buka Power BI Desktop.
3. Masuk ke tab ribbon **View** $\rightarrow$ Dropdown **Themes** $\rightarrow$ Klik **Browse for themes...**
4. Pilih file `enterprise_theme.json`. Pastikan canvas background berubah menjadi `#F4F5F7` secara seragam.

#### Tahap 2: Implementasi Dynamic Measures
1. Masuk ke panel **Model View**, pastikan tabel `FactSales` memiliki kolom `Revenue` dan `BudgetRevenue`.
2. Buat measure DAX untuk implementasi IBCS:
   - `Total Revenue AC`
   - `Total Revenue PL`
   - `Var Revenue Abs`
   - `Var Revenue Pct`
   - `Format Color Var Revenue`
   - `SVG Dynamic Trend Indicator` (Pastikan tipe data Measure diatur: Properties $\rightarrow$ Advanced $\rightarrow$ Data category: **Image URL**).

#### Tahap 3: Konstruksi Visual Hierarchy
1. **Container Setup**:
   - Buat satu shape *Rectangle* di posisi paling atas: $X = 16, Y = 16, \text{Width} = 1248, \text{Height} = 64$. Set fill `#FFFFFF`, border `None`.
   - Tambahkan *Text Box* judul: `"FINANCIAL PERFORMANCE SUMMARY"` (Segoe UI Semibold, 16pt, `#172B4D`).
2. **Executive KPI Block (Z-Pattern Top Left)**:
   - Masukkan visual *New Card* (Card multi-row 2.0).
   - Masukkan measure `Total Revenue AC` dan `Var Revenue Pct`.
   - Konfigurasi Conditional Formatting font color pada `Var Revenue Pct`:
     - Format style: **Field value**.
     - What field should we base this on?: Pilih Measure `Format Color Var Revenue`.
3. **Data Matrix with Embedded Trend Indicator**:
   - Buat visual *Matrix* di bawah blok KPI: $X = 16, Y = 96, \text{Width} = 800, \text{Height} = 400$.
   - Rows: `DimProduct[Category]`.
   - Values: `Total Revenue AC`, `Total Revenue PL`, `Var Revenue Abs`, `SVG Dynamic Trend Indicator`.
   - Buka Format Visual $\rightarrow$ Grid $\rightarrow$ Options: ubah Row padding menjadi `6px`.
   - Buka Column Headers: Set background color `#FFFFFF`, font color `#172B4D`, border bottom only.
4. **Variance Waterfall Chart (IBCS Structural Visual)**:
   - Tambahkan *Waterfall Chart* di sebelah kanan matriks: $X = 832, Y = 96, \text{Width} = 432, \text{Height} = 400$.
   - Category: `DimProduct[Category]`.
   - Breakdown: kosongkan.
   - Y-Axis: `Var Revenue Abs`.
   - Ubah warna sentral: Sentiment Colors $\rightarrow$ Increase: `#00875A`, Decrease: `#DE350B`, Total: `#5E6C84`.

#### Tahap 4: Verifikasi & Audit Aksesibilitas
1. Buka *Performance Analyzer* (Ribbon **Optimize** $\rightarrow$ **Performance Analyzer**).
2. Klik **Start Recording** lalu klik **Refresh visuals**.
3. Validasi bahwa total visual display duration berada di bawah ambang batas **800 ms**.
4. Periksa visual menggunakan *Color Oracle* atau accessibility simulator (Deuteranopia filter) untuk memastikan arah panah SVG dan delta percentage tetap terbaca jelas tanpa bergantung hanya pada spektrum warna.