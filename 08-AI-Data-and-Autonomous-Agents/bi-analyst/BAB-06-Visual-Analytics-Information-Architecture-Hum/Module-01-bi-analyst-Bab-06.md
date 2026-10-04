# Bab 06: Visual Analytics, Information Architecture & Human Cognition
## Modul 01: Fondasi Kognitif, Visual Encoding, dan Information Architecture untuk Modern BI

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Keterbatasan Kognitif Manusia (Human Cognitive Bandwidth)**: Mengidentifikasi batas *Sensory Memory*, *Working Memory* ($4 \pm 1$ *chunks* menurut Cowan), dan *Long-Term Memory* dalam konteks konsumsi informasi analitis berkecepatan tinggi.
2. **Menerapkan Hirarki Visual Encoding Cleveland & McGill**: Memetakan tipe data (nominal, ordinal, kuantitatif interval/rasio) ke dalam saluran visual (*visual channels*) dengan tingkat akurasi persepsi tertinggi secara deterministik.
3. **Mengoptimasi Information Architecture (IA) Berbasis Shneiderman’s Mantra**: Merancang arsitektur navigasi analitik hierarkis (*Overview first, zoom and filter, then details-on-demand*) untuk mencegah fenomena *dashboard fatigue*.
4. **Mengimplementasikan Standar IBCS (International Business Communication Standards)**: Menstandarisasi representasi varians, skenario bisnis (Actual, Budget, Forecast), dan kalkulasi *Data-to-Ink Ratio* menurut prinsip Edward Tufte.
5. **Membangun Automated Cognitive-Aware Visualization Pipeline**: Menulis kode Python level *production* yang memvalidasi data, memilih visualisasi secara heuristik berdasarkan tipe variabel, menghitung *Data-to-Ink Ratio*, serta memvalidasi kepatuhan aksesibilitas kontras warna (WCAG 2.1 AA).

---

### 2. Concept Overview

Visual Analytics bukan sekadar disiplin estetika ("membuat grafik yang indah"), melainkan sebuah sub-sistem antarmuka komputasi antara mesin dan korteks visual manusia (*human visual cortex*). Dalam rekayasa *Business Intelligence* modern, visualisasi data berfungsi sebagai saluran dekompresi data biner berkecepatan tinggi menjadi representasi spasial yang dapat diolah oleh kognisi manusia dengan latensi serendah mungkin.

```
+-------------------------------------------------------------------------+
|                        HUMAN COGNITIVE PIPELINE                         |
|                                                                         |
|  [ Stimulus Visual ]                                                    |
|          │                                                              |
|          ▼                                                              |
|  ┌────────────────┐    Preattentive Processing (< 200ms)                |
|  │ Sensory Memory │ ── Raw channels: Posisi, Panjang, Warna, Orientasi  |
|  └───────┬────────┘                                                     |
|          │ Cognitive Bottleneck (Perhatian Terarah)                     |
|          ▼                                                              |
|  ┌────────────────┐    Kapasitas Terbatas (~4 Chunks)                   |
|  │ Working Memory │ ── Cognitive Load: Intrinsic + Extraneous + Germane |
|  └───────┬────────┘                                                     |
|          │ Konsolidasi Semantik                                         |
|          ▼                                                              |
|  ┌───────────────────┐                                                  |
|  │ Long-Term Memory  │ ── Mental Models, Schema Bisnis & Keputusan      |
|  └───────────────────┘                                                  |
+-------------------------------------------------------------------------+
```

#### Teori Inti

1. **Cognitive Load Theory (Sweller)**:
   * **Intrinsic Load**: Beban esensial dari kompleksitas data bisnis itu sendiri (misalnya, korelasi multi-dimensi antara churn, ARPU, dan CAC).
   * **Extraneous Load**: Beban kognitif parasitik yang ditimbulkan oleh desain visual yang buruk (chart junk, distorsi skala 3D, warna acak, gridlines berlebihan).
   * **Germane Load**: Beban kerja kognitif yang memfasilitasi pembentukan pola mental dan pemahaman mendalam (*insight generation*).
   * **Hukum Desain BI**: *Minimalkan Extraneous Load secara ekstrem untuk membebaskan bandwidth Working Memory bagi Intrinsic dan Germane Load.*

2. **Hirarki Cleveland & McGill (1984)**:
   Akurasi persepsi manusia terhadap decoding nilai numerik memiliki urutan hierarkis matematis:
   $$\text{Posisi (skala sama)} > \text{Posisi (skala tak sama)} > \text{Panjang} > \text{Arah/Kemiringan} > \text{Sudut} > \text{Luas} > \text{Volume} > \text{Saturasi Warna}$$

3. **Prinsip Grafis Edward Tufte**:
   $$\text{Data-Ink Ratio} = \frac{\text{Data-Ink}}{\text{Total Ink yang Digunakan untuk Mencetak/Menampilkan Grafik}}$$
   Target optimal adalah mendekati nilai $1.0$, di mana setiap piksel non-data dieliminasi kecuali jika memiliki fungsi struktural yang kritis.

---

### 3. Why It Matters

Di lingkungan enterprise kontemporer, BI Analyst sering berhadapan dengan kegagalan sistemik adopsi analitik. Masalah utamanya jarang terletak pada latensi query SQL atau pipeline ETL, melainkan pada **kegagalan antarmuka visual (Cognitive Impedance Mismatch)**:

* **Executive Dashboard Abandonment**: Eksekutif C-level rata-rata hanya memiliki waktu 15–30 detik untuk membaca laporan performa. Dashboard dengan 20 KPI terfragmentasi tanpa hierarki spasial menyebabkan *paralysis by analysis*, memicu penolakan sistem analitik dan kembalinya keputusan berbasis intuisi subjektif (*gut feeling*).
* **Bias Pengambilan Keputusan Fatal**: Penggunaan sumbu ganda (*dual-axis*) dengan skala tidak proporsional atau *pie charts* 3D mendistorsi korelasi metrik secara signifikan. Dalam industri perbankan atau kesehatan, kesalahan interpretasi tren varians 2% dapat berujung pada kerugian jutaan dolar atau kesalahan alokasi risiko portofolio.
* **Latency to Action**: Desain visual yang tidak menerapkan prinsip Gestalt memaksa analis membolak-balik legenda (*legend hopping*), menghitung angka secara mental, dan mencari letak anomali. Visualisasi yang dioptimalkan secara kognitif menggunakan *preattentive attributes* untuk mengarahkan fovea mata langsung ke varians di luar ambang batas (*threshold exceptions*) dalam waktu $< 200 \text{ ms}$.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur Information Architecture (IA) dan Visual Analytics Pipeline berikut mendefinisikan transformasi data transaksional mentah menjadi antarmuka kognitif berkecepatan tinggi:

```
+---------------------------------------------------------------------------------------------------+
|                        COGNITIVE-AWARE VISUAL ANALYTICS ARCHITECTURE                              |
+---------------------------------------------------------------------------------------------------+

 [ Enterprise Semantic Layer ] (Cube, Mart, Wide-Table: Measures, Dimensions, Metadata)
               │
               ▼
+───────────────────────────────────────────────────────────────────────────────────────────────────+
| [LAYER 1: Semantic Typing & Heuristic Engine]                                                     |
|  - Data Type Classifier (Nominal, Ordinal, Interval, Ratio, Temporal)                             |
|  - Cardinality & Variance Analyzer                                                                |
|  - Cognitive Task Identification (Komparasi, Komposisi, Distribusi, Korelasi, Deviasi)            |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
               │
               ▼
+───────────────────────────────────────────────────────────────────────────────────────────────────+
| [LAYER 2: Visual Encoding & Accessibility Synthesizer]                                            |
|  - Cleveland-McGill Channel Allocator (Posisi vs. Panjang vs. Area)                               |
|  - IBCS Formatter (Skenario: Solid=Actual, Hatched=Plan, Outline=Forecast)                       |
|  - Color Engine: CIE LCh / Lab (Isoluminan, CVD Safe: Deuteranopia/Protanopia/Tritanopia)          |
|  - Dynamic Data-to-Ink Pruner (Menghapus background, border, ticks sekunder)                     |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
               │
               ▼
+───────────────────────────────────────────────────────────────────────────────────────────────────+
| [LAYER 3: Information Architecture Layout Engine (Shneiderman’s Pattern)]                         |
|  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐  |
|  │ LEVEL 1: Strategic Canvas (Overview, Single-glance Macro-KPIs, Sparklines, Delta Varians)   │  |
|  ├─────────────────────────────────────────────────────────────────────────────────────────────┤  |
|  │ LEVEL 2: Exploratory Slice (Faceted Small Multiples, Slice-and-Dice, Linked Brushing)       │  |
|  ├─────────────────────────────────────────────────────────────────────────────────────────────┤  |
|  │ LEVEL 3: Transactional Micro-View (Details-on-Demand, Tabular Granularity, Log Audit)       │  |
|  └─────────────────────────────────────────────────────────────────────────────────────────────┘  |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
               │
               ▼
 [ Human Visual Cortex: Decision Engine ] (Latensi Persepsi Rendah, Zero Ambiguity)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Mekanisme Pemrosesan Visual Manusia (*Preattentive Processing*)
Sebelum kesadaran sadar (*conscious focal attention*) terpicu dalam otak, jalur sensorik mata memproses fitur-fitur visual dasar secara paralel dalam waktu kurang dari 200 milidetik. Fitur ini disebut atribut *preattentive*:
* **Bentuk (*Form*)**: Panjang, lebar, orientasi, ukuran spasial, bentuk kurva, batas (*enclosure*).
* **Warna (*Color*)**: *Hue* (identifikasi kategori nominal), *Intensity/Saturation* (magnitudo kuantitatif).
* **Spasial (*Spatial Position*)**: Posisi 2D $(x, y)$.

Dalam rekayasa analitik, atribut preattentive tidak boleh digunakan untuk hiasan. Atribut ini harus dikonservasi secara ketat dan dialokasikan hanya untuk **sinyal peringatan dan varians signifikan**. Jika sebuah dashboard menggunakan 8 warna berbeda untuk 8 divisi organisasi yang berbeda, sistem pengenalan preattentive mata akan mengalami saturasi sinyal (*visual noise*), memicu degradasi performa interpretasi.

#### B. Teori Gestalt dalam Desain Antarmuka Analitik
Otak manusia secara otomatis menyatukan elemen visual ke dalam suatu sistem yang teratur berdasarkan prinsip perseptual:
1. **Proximity (Kedekatan)**: Elemen yang posisinya saling berdekatan diasumsikan memiliki relasi fungsional yang sama. Tempatkan label metrik langsung di samping titik akhir data (*direct labeling*), bukan di dalam legenda terpisah di sudut kanvas.
2. **Similarity (Kesamaan)**: Elemen dengan bentuk, warna, atau orientasi visual yang identik dipersepsikan sebagai kelompok kategori yang sama.
3. **Enclosure (Pengurungan)**: Penggunaan border tipis atau *subtle background fill* dapat mengelompokkan metrik terkait jauh lebih kuat dibandingkan ruang kosong (*whitespace*).
4. **Continuity (Kontinuitas)**: Mata manusia cenderung mengikuti jalur garis linier. Sumbu tren waktu harus selalu berupa garis kontinu tanpa interupsi ortogonal yang tidak relevan.

#### C. Standar IBCS (International Business Communication Standards)
IBCS mendefinisikan bahasa visual terstandarisasi untuk analitik bisnis perusahaan:
* **Representasi Waktu (Temporal)**: Waktu *harus* selalu direpresentasikan pada sumbu horizontal (kiri ke kanan).
* **Representasi Struktur (Kategori)**: Variasi kategori hierarkis non-temporal direpresentasikan pada sumbu vertikal (grafik batang horizontal).
* **Kode Notasi Skenario Bisnis**:
  * **Actual (Realisasi)**: Batang hitam/abu-abu pekat (*solid fill*).
  * **Previous Year (Tahun Lalu)**: Batang abu-abu muda (*light solid fill*).
  * **Budget / Plan (Rencana)**: Batang bergaris arsir miring (*hatched pattern*) atau berbingkai tipis terbuka.
  * **Forecast (Prakiraan)**: Batang putus-putus (*dashed line*) atau garis tepi tipis dengan arsiran ringan.
* **Varians Dinamis**: Varians absolut disimbolkan dengan batang tebal; varians relatif disimbolkan dengan format pin/lollipop (*line with a head*). Varians positif terhadap budget diwarnai hijau secara deterministik hanya jika itu menguntungkan laba perusahaan; varians negatif diwarnai merah.

---

### 6. Production-Ready Code Implementation

Berikut adalah modul Python level enterprise yang mengimplementasikan **Cognitive Visual Specification Engine**. Kode ini memvalidasi input data analitik, mengevaluasi tipe data dan kardinalitasnya, memilih encoding visual berdasarkan hierarki Cleveland-McGill, menghitung *Data-to-Ink Ratio*, mengevaluasi kontras WCAG 2.1 AA, dan mengekspor spesifikasi visual Plotly/JSON yang siap digunakan pada platform analitik modern.

```python
"""
Module: cognitive_visual_engine.py
Author: Principal Data Architect & BI Specialist
Description: Production-ready engine for generating cognitive-compliant visual analytics
             specifications, enforcing IBCS, Cleveland-McGill hierarchy, and accessibility standards.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


class DataType(enum.Enum):
    NOMINAL = "nominal"
    ORDINAL = "ordinal"
    INTERVAL_RATIO = "interval_ratio"
    TEMPORAL = "temporal"


class BusinessScenario(enum.Enum):
    ACTUAL = "actual"
    BUDGET = "budget"
    FORECAST = "forecast"
    PREVIOUS_YEAR = "previous_year"


@dataclass(frozen=True)
class VisualChannelAllocation:
    mark_type: str
    x_axis: str
    y_axis: str
    color_scale: Optional[Dict[str, str]] = None
    data_ink_score: float = 1.0
    accessibility_passed: bool = True
    warnings: List[str] = field(default_factory=list)


class AccessibilityValidator:
    """Memvalidasi kontras warna teks dan elemen grafis berdasarkan pedoman WCAG 2.1 AA."""

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            raise ValueError(f"Hex color '{hex_color}' tidak valid. Harus 6 karakter.")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore

    @classmethod
    def _relative_luminance(cls, hex_color: str) -> float:
        r, g, b = cls._hex_to_rgb(hex_color)
        srgb = [c / 255.0 for c in (r, g, b)]
        transformed = [
            c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)
            for c in srgb
        ]
        return 0.2126 * transformed[0] + 0.7152 * transformed[1] + 0.0722 * transformed[2]

    @classmethod
    def calculate_contrast_ratio(cls, foreground_hex: str, background_hex: str) -> float:
        """Menghitung rasio kontras luminansi relatif antara dua warna hex (1:1 hingga 21:1)."""
        lum1 = cls._relative_luminance(foreground_hex)
        lum2 = cls._relative_luminance(background_hex)
        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def validate_wcag_aa(
        cls,
        foreground_hex: str,
        background_hex: str,
        is_large_text_or_ui: bool = True,
    ) -> bool:
        """
        Threshold WCAG 2.1 AA:
        - Teks normal: >= 4.5:1
        - Komponen UI dan Grafis Data: >= 3.0:1
        """
        ratio = cls.calculate_contrast_ratio(foreground_hex, background_hex)
        threshold = 3.0 if is_large_text_or_ui else 4.5
        return ratio >= threshold


class CognitiveVisualEngine:
    """
    Mesin optimasi encoding visual berbasis Cleveland-McGill, Tufte, dan IBCS.
    """

    IBCS_PALETTE = {
        BusinessScenario.ACTUAL: "#212529",         # Deep Slate Charcoal (Solid Fill)
        BusinessScenario.BUDGET: "#6C757D",         # Slate Gray (Hatched/Outline)
        BusinessScenario.FORECAST: "#ADB5BD",       # Light Gray (Dotted/Dashed pattern)
        BusinessScenario.PREVIOUS_YEAR: "#DEE2E6",  # Very Light Gray
        "POSITIVE_VARIANCE": "#2B8A3E",             # Accessible Dark Green
        "NEGATIVE_VARIANCE": "#C92A2A",             # Accessible Dark Red
        "CANVAS_BACKGROUND": "#FFFFFF",             # Pure White
    }

    def __init__(self, dataframe: pd.DataFrame) -> None:
        if dataframe.empty:
            raise ValueError("DataFrame input tidak boleh kosong.")
        self.df = dataframe.copy()

    def profile_column(self, col_name: str) -> DataType:
        """Mengidentifikasi tipe semantik data kolom."""
        if col_name not in self.df.columns:
            raise KeyError(f"Kolom '{col_name}' tidak ditemukan di DataFrame.")

        series = self.df[col_name]

        if pd.api.types.is_datetime64_any_dtype(series):
            return DataType.TEMPORAL
        elif pd.api.types.is_numeric_dtype(series):
            return DataType.INTERVAL_RATIO
        elif isinstance(series.dtype, pd.CategoricalDtype) and series.dtype.ordered:
            return DataType.ORDINAL
        else:
            # Uji apakah tipe objek merupakan string tanggal yang belum diparse
            try:
                pd.to_datetime(series.dropna().head(10))
                return DataType.TEMPORAL
            except (ValueError, TypeError):
                return DataType.NOMINAL

    def evaluate_data_ink_budget(self, elements_present: Dict[str, bool]) -> float:
        """
        Menghitung estimasi Data-to-Ink Ratio secara heuristik.
        Penalti diberikan pada elemen non-data yang berlebihan.
        """
        base_ink = 1.0
        penalties = {
            "heavy_gridlines": 0.20,
            "redundant_legend": 0.15,
            "background_fill": 0.25,
            "three_d_effects": 0.40,
            "duplicate_labels": 0.10,
        }

        current_score = base_ink
        for element, present in elements_present.items():
            if present and element in penalties:
                current_score -= penalties[element]

        return max(round(current_score, 2), 0.0)

    def recommend_encoding(
        self,
        dimension_col: str,
        measure_col: str,
        scenario: BusinessScenario = BusinessScenario.ACTUAL,
    ) -> VisualChannelAllocation:
        """
        Menghasilkan rekomendasi saluran visual deterministik berdasarkan prinsip Cleveland-McGill.
        """
        dim_type = self.profile_column(dimension_col)
        measure_type = self.profile_column(measure_col)
        warnings: List[str] = []

        if measure_type != DataType.INTERVAL_RATIO:
            raise TypeError(
                f"Kolom ukuran '{measure_col}' harus bertipe numerik (INTERVAL_RATIO)."
            )

        cardinality = self.df[dimension_col].nunique()

        # Validasi Aksesibilitas Warna IBCS terhadap Background
        fill_color = self.IBCS_PALETTE[scenario]
        bg_color = self.IBCS_PALETTE["CANVAS_BACKGROUND"]
        is_accessible = AccessibilityValidator.validate_wcag_aa(
            fill_color, bg_color, is_large_text_or_ui=True
        )

        if not is_accessible:
            warnings.append(
                f"Kontras warna skenario {scenario.value} gagal memenuhi batas standar WCAG 2.1 AA."
            )

        # Hirarki Rekomendasi
        if dim_type == DataType.TEMPORAL:
            # Waktu diposisikan pada sumbu-X horisontal secara linier
            mark = "line" if cardinality > 12 else "column"
            x_axis = dimension_col
            y_axis = measure_col
        elif dim_type == DataType.NOMINAL:
            # Kategori diskrit non-temporal: Gunakan batang horizontal untuk keterbacaan teks label
            mark = "bar_horizontal"
            x_axis = measure_col
            y_axis = dimension_col

            if cardinality > 15:
                warnings.append(
                    f"Kardinalitas dimensi '{dimension_col}' tinggi ({cardinality}). "
                    "Terapkan aturan top-N filtering + agregasi 'Other' untuk mengurangi Cognitive Load."
                )
        else:
            mark = "scatter"
            x_axis = dimension_col
            y_axis = measure_col

        # Evaluasi Data-Ink
        default_elements = {
            "heavy_gridlines": False,
            "redundant_legend": False,
            "background_fill": False,
            "three_d_effects": False,
            "duplicate_labels": False,
        }
        data_ink = self.evaluate_data_ink_budget(default_elements)

        return VisualChannelAllocation(
            mark_type=mark,
            x_axis=x_axis,
            y_axis=y_axis,
            color_scale={scenario.value: fill_color},
            data_ink_score=data_ink,
            accessibility_passed=is_accessible,
            warnings=warnings,
        )

    def generate_plotly_spec(
        self,
        dimension_col: str,
        measure_col: str,
        scenario: BusinessScenario = BusinessScenario.ACTUAL,
    ) -> Dict[str, Any]:
        """
        Menghasilkan payload JSON spesifikasi Plotly terstruktur yang bersih dari 'chart junk'
        dan menerapkan kaidah Data-to-Ink rasio Edward Tufte serta IBCS.
        """
        allocation = self.recommend_encoding(dimension_col, measure_col, scenario)
        sorted_df = self.df.sort_values(by=measure_col, ascending=True)

        if allocation.mark_type == "bar_horizontal":
            trace = {
                "type": "bar",
                "x": sorted_df[allocation.x_axis].tolist(),
                "y": sorted_df[allocation.y_axis].astype(str).tolist(),
                "orientation": "h",
                "marker": {
                    "color": allocation.color_scale[scenario.value],
                    "line": {"width": 0},
                },
                "text": sorted_df[allocation.x_axis].apply(lambda v: f"{v:,.0f}").tolist(),
                "textposition": "outside",
                "cliponaxis": False,
            }
            layout = {
                "plot_bgcolor": self.IBCS_PALETTE["CANVAS_BACKGROUND"],
                "paper_bgcolor": self.IBCS_PALETTE["CANVAS_BACKGROUND"],
                "xaxis": {
                    "showgrid": True,
                    "gridcolor": "#E9ECEF",
                    "gridwidth": 0.8,
                    "zeroline": True,
                    "zerolinecolor": "#495057",
                    "showline": False,
                    "title": None,
                },
                "yaxis": {
                    "showgrid": False,
                    "showline": True,
                    "linecolor": "#495057",
                    "title": None,
                    "ticks": "",
                },
                "margin": {"l": 120, "r": 50, "t": 40, "b": 30},
                "font": {"family": "Arial, sans-serif", "size": 12, "color": "#212529"},
            }
        else:
            # Fallback implementasi linier temporal
            trace = {
                "type": "scatter",
                "mode": "lines+markers",
                "x": self.df[allocation.x_axis].tolist(),
                "y": self.df[allocation.y_axis].tolist(),
                "line": {"color": allocation.color_scale[scenario.value], "width": 2},
                "marker": {"size": 6},
            }
            layout = {
                "plot_bgcolor": self.IBCS_PALETTE["CANVAS_BACKGROUND"],
                "xaxis": {"showgrid": False, "showline": True, "linecolor": "#495057"},
                "yaxis": {"showgrid": True, "gridcolor": "#E9ECEF"},
            }

        return {
            "data": [trace],
            "layout": layout,
            "meta": {
                "data_ink_score": allocation.data_ink_score,
                "warnings": allocation.warnings,
                "accessibility": "WCAG_2.1_AA_COMPLIANT"
                if allocation.accessibility_passed
                else "NON_COMPLIANT",
            },
        }


# =====================================================================
# Unit Validation & Demonstration
# =====================================================================
if __name__ == "__main__":
    raw_data = {
        "Cost_Center": [
            "Logistics & Fleet",
            "Human Resources",
            "Software R&D",
            "Marketing & Acquisition",
            "Customer Support",
        ],
        "Actual_Expenses_USD": [152000.0, 48000.0, 310000.0, 220000.0, 94000.0],
    }

    test_df = pd.DataFrame(raw_data)
    engine = CognitiveVisualEngine(test_df)

    spec = engine.generate_plotly_spec(
        dimension_col="Cost_Center",
        measure_col="Actual_Expenses_USD",
        scenario=BusinessScenario.ACTUAL,
    )

    import json

    print(json.dumps(spec, indent=2))
```

---

### 7. Edge Cases & Failure Modes

Pada implementasi skala enterprise, kegagalan penyampaian visual umumnya disebabkan oleh skenario anomali data berikut:

| Skenario Anomali Data | Dampak Kegagalan Kognitif | Mekanisme Resolusi Teknis |
| :--- | :--- | :--- |
| **Kardinalitas Ekstrem Nominal ($N > 30$)** | Teks sumbu tumpang tindih (*label collision*); visual memory kelebihan muatan. | Menerapkan algoritma *Pareto Ranking*: Tampilkan Top 7 hingga Top 10 kategori, sisanya digabungkan (*aggregated sum*) ke dalam satu kategori `Other/Lainnya`. |
| **Penyimpangan Skala Outlier ($> 10\times$ IQR)** | Skala visual terdistorsi; variabilitas data normal menjadi garis datar tak terlihat (*variance flattening*). | Gunakan pendekatan *Broken Axis Panel* atau berikan representasi multi-panel bertingkat (*zoomed-in small multiple panel*) daripada menggunakan transformasi skala logaritmik yang sering disalahartikan oleh audiens non-teknis. |
| **Defisiensi Penglihatan Warna (CVD)** | Pengambilan keputusan yang salah akibat ketidakmampuan membedakan varians untung/rugi pada palet konvensional merah-hijau murni. | Gunakan palet isoluminan yang telah dikalibrasi: kombinasikan warna dengan simbol redundant (misal: segitiga ke atas $\Delta$ untuk positif, panah ke bawah $\nabla$ untuk negatif) dan pastikan kontras rasio $> 3.0:1$. |
| **Zero Baseline Violation pada Bar Chart** | Pemotongan sumbu-Y non-nol mendistorsi perbandingan visual panjang (*length decoding*), melebih-lebihkan perbedaan kecil secara artifisial. | Validasi ketat pada level schema rendering: Sumbu nilai pada diagram batang *wajib secara mutlak* dimulai dari $0.0$. Jika varians absolut kecil, alihkan encoding dari diagram batang (*bar chart*) ke diagram titik varians (*variance dot plot*) dengan basis nol terpusat. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan visual encoding membawa konsekuensi komputasi dan persepsi:

```
                EKSPLORATIF                                  EKSPLANATIF
     (Kaya Interaktivitas, Fleksibel)              (Terkurasi, Deterministik)
                    ▲                                          ▲
                    │                                          │
    Kompleksitas Kognitif Tinggi               Kompleksitas Kognitif Terkontrol
    Bandwidth Analisis Luas                    Eksekusi Keputusan Sangat Cepat
                    │                                          │
  [Linked Brushing / High Filtering]            [IBCS Variance Waterfall / Bullet]
```

| Pendekatan Desain | Keuntungan | Kerugian & Konsekuensi | Situasi Penggunaan Optimal |
| :--- | :--- | :--- | :--- |
| **Single Rich Canvas (Semua KPI Terkonsentrasi)** | Meminimalkan klik navigasi; seluruh parameter teknis terlihat dalam satu layar. | Tingginya *Extraneous Cognitive Load*; membingungkan pemangku kepentingan tingkat eksekutif. | Ruang kontrol operasional teknis (NOC, Security Operations Center, Trading Desk). |
| **Faceted Small Multiples** | Mengeliminasi legenda warna yang membingungkan; memanfaatkan skala dan grid yang sama untuk membaca puluhan dimensi secara instan. | Mengonsumsi *viewport* layar secara masif; sulit diterapkan secara optimal pada resolusi mobile/tablet. | Komparasi pola deret waktu lintas wilayah, produk, atau segmen demografis. |
| **Dynamic Tooltips & Hover States** | Kanvas utama tetap bersih (memaksimalkan Data-Ink Ratio); detail hanya muncul saat diminta. | Memerlukan aksi fisik pengguna (*hover latency*); informasi tidak dapat diprint langsung dalam format PDF eksekutif. | Dashboard manajerial desktop interaktif (*Self-Service BI*). |

---

### 9. Best Practices & Standard Industri

Untuk menjamin kualitas visual analitik di tingkat enterprise, terapkan standar deviasi visual berikut:

* **Penerapan Standar IBCS SUCCESS**:
  * **S**ay: Tuliskan pesan analitik utama sebagai judul grafik (*action title*), bukan sekadar judul deskriptif metrik.
    * *Buruk*: "Grafik Penjualan Q1–Q4 2023"
    * *Benar*: "Penjualan Q4 Menurun 12% Akibat Disrupsi Logistik Regional"
  * **U**nify: Standarisasi warna, bentuk visual, dan terminologi di seluruh departemen perusahaan.
  * **C**ondense: Tampilkan informasi secara padat dan bermakna tinggi menggunakan *small multiples*, bukan layout kartu KPI kosong yang boros tempat.
  * **C**heck: Pastikan integritas skala (hindari sumbu terpotong pada representasi berbasis panjang).
  * **E**xpress: Pilih visualisasi yang tepat sesuai relasi analitik data.
  * **S**implify: Buang elemen dekoratif (efek gloss, bayangan, border 3D, gridlines gelap).
  * **S**tructure: Rancang layout mengikuti Information Architecture berbasis piramida (*Overview to Details*).

* **Standar Aksesibilitas WCAG 2.1 AA**:
  * Elemen grafis data (garis tren, batang) wajib memiliki rasio kontras minimal **3.0:1** terhadap latar belakang kanvas.
  * Hindari mengandalkan warna sebagai satu-satunya variabel pembeda data (*dual encoding*: gunakan warna + posisi / bentuk visual / teks langsung).

---

### 10. Hands-on Lab Exercise

#### Skenario Kasus
Manajemen operasional mengeluhkan dashboard performa biaya logistik armada truk yang dinilai membingungkan. Diagram awal yang ada adalah *3D Pie Chart* berisi 18 rute pengiriman dengan label warna acak dan legenda yang terpisah. 

#### Tugas Lab
1. Eksekusi kode Python di bawah ini untuk mensimulasikan data logistik mentah.
2. Lakukan transformasi data: identifikasi kategori dengan kardinalitas tinggi, ambil Top 5 rute termahal, dan gabungkan sisanya ke dalam kategori "Other Routes".
3. Bangun visualisasi horizontal bar chart berbasis prinsip Tufte/IBCS menggunakan engine yang telah dibuat di Section 6.
4. Lakukan validasi output spesifikasi teknis: hitung *Data-to-Ink ratio* dan pastikan kepatuhan kontras WCAG.

#### Skrip Lab Dimulai
```python
# Jalankan script ini di environment Python Anda
import pandas as pd
from cognitive_visual_engine import BusinessScenario, CognitiveVisualEngine

# 1. Dataset Simulasi Kasus Nyata
raw_logistics_data = {
    "Route_Name": [
        "Route-JKT-SBY", "Route-JKT-BDG", "Route-SBY-DPS", "Route-MDN-PDG",
        "Route-SMG-YOG", "Route-BPN-SMD", "Route-MKS-MND", "Route-PLM-LMP",
        "Route-PKU-PDG", "Route-JKT-SMG", "Route-BDG-CRB", "Route-DPS-LMB",
        "Route-KDI-MKS", "Route-TRK-BPN", "Route-PNK-SKD", "Route-JBR-SBY",
        "Route-BGR-JKT", "Route-TGL-PKL"
    ],
    "Variance_to_Budget_USD": [
        45000, 38000, 29000, 24000, 19000, 15000, 12000, 11000,
        9500, 8000, 7200, 6100, 5400, 4800, 3900, 3100, 2200, 1500
    ]
}

df_raw = pd.DataFrame(raw_logistics_data)

# 2. Refaktorisasi Data (Mengatasi High Cardinality: Top 5 + Other)
TOP_N = 5
df_sorted = df_raw.sort_values(by="Variance_to_Budget_USD", ascending=False).reset_index(drop=True)

top_records = df_sorted.iloc[:TOP_N].copy()
other_variance = df_sorted.iloc[TOP_N:]["Variance_to_Budget_USD"].sum()

other_record = pd.DataFrame({
    "Route_Name": ["Other Routes (Aggregated)"],
    "Variance_to_Budget_USD": [other_variance]
})

clean_df = pd.concat([top_records, other_record], ignore_index=True)

# 3. Jalankan Engine Visual Analitik
pipeline = CognitiveVisualEngine(clean_df)
visual_spec = pipeline.generate_plotly_spec(
    dimension_col="Route_Name",
    measure_col="Variance_to_Budget_USD",
    scenario=BusinessScenario.ACTUAL
)

# 4. Verifikasi Keberhasilan Desain Visual
print("=== VERIFIKASI SISTEM ANALITIK KOGNITIF ===")
print(f"Status Kepatuhan Aksesibilitas : {visual_spec['meta']['accessibility']}")
print(f"Data-to-Ink Ratio Score        : {visual_spec['meta']['data_ink_score']}")
print(f"Peringatan Engine              : {visual_spec['meta']['warnings']}")
print("\nSpesifikasi Trace Berhasil Dibentuk:")
print(f"Tipe Mark Visual               : {visual_spec['data'][0]['type']}")
print(f"Orientasi                      : {visual_spec['data'][0].get('orientation')}")
print(f"Total Batang Ditampilkan       : {len(visual_spec['data'][0]['y'])}")
```

#### Hasil yang Diharapkan
* Status Kepatuhan Aksesibilitas: `WCAG_2.1_AA_COMPLIANT`.
* Nilai Data-to-Ink Ratio: $\ge 0.85$ (tidak ada penalti garis bantu tebal atau pewarnaan latar belakang yang tidak fungsional).
* Total batang terkontrol sebanyak 6 kategori (5 rute utama + 1 kategori gabungan), mengeliminasi *label collision* dan menjaga muatan memori kerja (*Working Memory*) pada batas ideal kognisi manusia.