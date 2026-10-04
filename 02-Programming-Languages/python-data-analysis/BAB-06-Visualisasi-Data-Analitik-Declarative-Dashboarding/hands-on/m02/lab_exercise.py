#!/usr/bin/env python3
"""
Lab Hands-on: Declarative Data Visualization & Dashboarding Engine
Bab: 06 - Visualisasi Data Analitik & Declarative Dashboarding (Modul 02 Deep Dive)

Implementasi self-contained mini declarative analytics & visualization engine:
1. Declarative Grammar of Graphics Spec (JSON/Dict based specifications).
2. Data Transformation & Aggregation Pipeline (Group-by, pivot, rollups).
3. Terminal Canvas Engine (ANSI character graphics, auto-scaling, rasterization).
4. Multi-view Dashboard Composition (KPI cards, bar charts, time-series lines).
5. Reactive Execution Engine (Spec -> Plan -> Aggregate -> Render).
"""

import math
import sys
import time
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

# ANSI Escape Codes untuk rendering visual dashboard
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_DARK = "\033[48;5;236m"
BG_BLUE = "\033[48;5;24m"


class DataFrame:
    """Struktur data tabular in-memory lightweight untuk analitik data."""
    def __init__(self, records: List[Dict[str, Any]]):
        self.records = records

    def filter(self, predicate) -> 'DataFrame':
        """Memfilter baris data berdasarkan lambda predicate."""
        return DataFrame([r for r in self.records if predicate(r)])

    def aggregate(self, group_by: str, agg_col: str, agg_func: str = "mean") -> Dict[str, float]:
        """
        Menjalankan transformasi agregasi data secara deklaratif.
        Mendukung: 'sum', 'mean', 'count', 'max', 'min'.
        """
        buckets = defaultdict(list)
        for r in self.records:
            if group_by in r and agg_col in r:
                buckets[r[group_by]].append(float(r[agg_col]))

        result = {}
        for key, values in buckets.items():
            if not values:
                result[key] = 0.0
            elif agg_func == "sum":
                result[key] = sum(values)
            elif agg_func == "mean":
                result[key] = sum(values) / len(values)
            elif agg_func == "count":
                result[key] = float(len(values))
            elif agg_func == "max":
                result[key] = max(values)
            elif agg_func == "min":
                result[key] = min(values)
            else:
                raise ValueError(f"Fungsi agregasi '{agg_func}' tidak dikenali.")
        return result


class TerminalCanvas:
    """Rasterizer 2D berbasis grid karakter ANSI untuk terminal canvas."""
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.buffer = [[" " for _ in range(width)] for _ in range(height)]
        self.color_buffer = [["" for _ in range(width)] for _ in range(height)]

    def draw_point(self, x: int, y: int, char: str, color: str = WHITE):
        """Memetakan koordinat diskrit ke dalam grid buffer layar."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.buffer[y][x] = char
            self.color_buffer[y][x] = color

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, char: str, color: str = WHITE):
        """Implementasi algoritma Bresenham untuk rasterisasi garis deklaratif."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            self.draw_point(x0, y0, char, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def render(self) -> str:
        """Mengompilasi karakter grid dan kode ANSI menjadi string buffer."""
        lines = []
        for y in range(self.height):
            line_str = ""
            for x in range(self.width):
                col = self.color_buffer[y][x]
                ch = self.buffer[y][x]
                if col:
                    line_str += f"{col}{ch}{RESET}"
                else:
                    line_str += ch
            lines.append(line_str)
        return "\n".join(lines)


class DeclarativeEngine:
    """
    Compiler declarative visualisasi: Mengubah spesifikasi deklaratif
    menjadi eksekusi analitik dan visual representasi grafis.
    """
    def __init__(self, df: DataFrame):
        self.df = df

    def render_kpi(self, spec: Dict[str, Any]) -> str:
        """Kompilasi spesifikasi KPI metric card."""
        title = spec.get("title", "METRIC")
        col = spec.get("column")
        op = spec.get("op", "sum")
        unit = spec.get("unit", "")
        color = spec.get("color", CYAN)

        vals = [float(r[col]) for r in self.df.records if col in r]
        val = 0.0
        if vals:
            val = sum(vals) if op == "sum" else (sum(vals) / len(vals) if op == "mean" else max(vals))

        box_width = 24
        header = f" {BOLD}{title}{RESET} "
        formatted_val = f"{val:,.2f} {unit}".strip()

        line1 = f"┌{'─' * (box_width - 2)}┐"
        line2 = f"│ {header.ljust(box_width - 4 + len(BOLD) + len(RESET))}│"
        line3 = f"│ {color}{BOLD}{formatted_val.center(box_width - 4)}{RESET} │"
        line4 = f"└{'─' * (box_width - 2)}┘"
        return f"{line1}\n{line2}\n{line3}\n{line4}"

    def render_bar(self, spec: Dict[str, Any], max_width: int = 40) -> str:
        """Kompilasi spesifikasi Mark: Bar Chart dengan label dinamis & auto-scaling."""
        group_by = spec["encoding"]["x"]
        metric = spec["encoding"]["y"]
        agg_func = spec["encoding"].get("aggregate", "sum")
        title = spec.get("title", f"{metric.upper()} by {group_by.upper()}")

        data_points = self.df.aggregate(group_by, metric, agg_func)
        if not data_points:
            return "No data available."

        max_val = max(data_points.values()) if data_points.values() else 1.0
        max_label_len = max(len(str(k)) for k in data_points.keys())

        output = [f"{BOLD}{CYAN}■ {title}{RESET}"]
        palette = [GREEN, BLUE, MAGENTA, YELLOW, CYAN]

        idx = 0
        for label, val in sorted(data_points.items(), key=lambda x: x[1], reverse=True):
            bar_len = int((val / max_val) * (max_width - 10)) if max_val > 0 else 0
            bar_str = "█" * bar_len
            col = palette[idx % len(palette)]
            label_fmt = str(label).ljust(max_label_len)
            output.append(f"  {DIM}{label_fmt}{RESET} │ {col}{bar_str}{RESET} {BOLD}{val:,.1f}{RESET}")
            idx += 1

        return "\n".join(output)

    def render_line_plot(self, spec: Dict[str, Any], width: int = 55, height: int = 10) -> str:
        """Kompilasi spesifikasi Mark: Line Chart ke Canvas 2D."""
        x_col = spec["encoding"]["x"]
        y_col = spec["encoding"]["y"]
        title = spec.get("title", f"Trend {y_col} vs {x_col}")

        # Urutkan berdasarkan waktu/dimensi X
        sorted_records = sorted(self.df.records, key=lambda r: r[x_col])
        if not sorted_records:
            return "No data for plot."

        x_vals = [r[x_col] for r in sorted_records]
        y_vals = [float(r[y_col]) for r in sorted_records]

        min_y, max_y = min(y_vals), max(y_vals)
        if min_y == max_y:
            max_y += 1.0

        canvas = TerminalCanvas(width, height)

        # Plot rasterized line
        prev_cx, prev_cy = None, None
        for i, (xv, yv) in enumerate(zip(x_vals, y_vals)):
            cx = int((i / (len(x_vals) - 1)) * (width - 1)) if len(x_vals) > 1 else 0
            # Flip koordinat Y untuk terminal (0 berada di atas)
            norm_y = (yv - min_y) / (max_y - min_y)
            cy = height - 1 - int(norm_y * (height - 1))

            if prev_cx is not None:
                canvas.draw_line(prev_cx, prev_cy, cx, cy, "•", GREEN)
            else:
                canvas.draw_point(cx, cy, "●", GREEN)
            prev_cx, prev_cy = cx, cy

        canvas_rendered = canvas.render()
        
        # Susun Frame dengan sumbu vertikal
        lines = canvas_rendered.split("\n")
        output = [f"{BOLD}{GREEN}▲ {title}{RESET}"]
        for idx, row in enumerate(lines):
            ratio = (height - 1 - idx) / (height - 1)
            axis_val = min_y + ratio * (max_y - min_y)
            output.append(f"{DIM}{axis_val:6.1f} ┤{RESET}{row}")
        
        # Sumbu horizontal
        output.append(f"       └{'─' * width}")
        output.append(f"        {DIM}start: {x_vals[0]} ───> end: {x_vals[-1]}{RESET}")
        return "\n".join(output)


def generate_telemetry_dataset() -> List[Dict[str, Any]]:
    """Simulasi data streaming telemetry latency & throughput server multi-region."""
    regions = ["us-east", "us-west", "eu-central", "ap-southeast"]
    base_time = 1711929600
    dataset = []

    # Simulasi 24 time tick data time-series
    for tick in range(24):
        timestamp = time.strftime("%H:%M", time.gmtime(base_time + tick * 3600))
        for reg in regions:
            # Pola variasi beban sinusoidal deterministik
            phase = (tick / 24.0) * (2 * math.pi)
            reg_offset = regions.index(reg) * 0.7
            load = math.sin(phase + reg_offset) * 20 + 50
            latency = (100 - load) * 1.5 + (tick % 5) * 3
            errors = int(max(0, math.cos(phase + reg_offset) * 8))

            dataset.append({
                "time": timestamp,
                "region": reg,
                "latency_ms": round(latency, 2),
                "throughput_rps": round(load * 12.5, 2),
                "errors": errors
            })
    return dataset


def main():
    print(f"{BOLD}{BG_BLUE}{WHITE}  ENTERPRISE ANALYTICS & DASHBOARDING ENGINE (MODULE 02)  {RESET}\n")

    # Inisialisasi Mock Real-world Dataset
    raw_telemetry = generate_telemetry_dataset()
    df = DataFrame(raw_telemetry)
    engine = DeclarativeEngine(df)

    print(f"{DIM}Dataset dimuat: {len(raw_telemetry)} records analitik telemetri multi-wilayah.{RESET}\n")

    # --- 1. Declarative KPI Metric Cards (Composite Flex Layout) ---
    print(f"{BOLD}1. DEKLARATIF METRIC KPIS (Executive Summary){RESET}")
    kpi_spec_1 = {"title": "AVG LATENCY", "column": "latency_ms", "op": "mean", "unit": "ms", "color": YELLOW}
    kpi_spec_2 = {"title": "TOTAL REQ", "column": "throughput_rps", "op": "sum", "unit": "req", "color": CYAN}
    kpi_spec_3 = {"title": "TOTAL ERRORS", "column": "errors", "op": "sum", "unit": "err", "color": RED}

    c1 = engine.render_kpi(kpi_spec_1).split("\n")
    c2 = engine.render_kpi(kpi_spec_2).split("\n")
    c3 = engine.render_kpi(kpi_spec_3).split("\n")

    # Susun KPI cards berdampingan secara horizontal
    for r1, r2, r3 in zip(c1, c2, c3):
        print(f" {r1}  {r2}  {r3}")
    print()

    # --- 2. Declarative Bar Visualizations ---
    print(f"{BOLD}2. DEKLARATIF AGGREGATION & BAR CHART MARK{RESET}")
    bar_spec = {
        "title": "Rata-rata Latensi Berdasarkan Wilayah Deployment",
        "mark": "bar",
        "encoding": {
            "x": "region",
            "y": "latency_ms",
            "aggregate": "mean"
        }
    }
    bar_view = engine.render_bar(bar_spec, max_width=45)
    print(bar_view)
    print()

    # --- 3. Declarative Time-Series Line Plot ---
    print(f"{BOLD}3. DEKLARATIF 2D TIME-SERIES RASTERIZATION (ap-southeast Latency){RESET}")
    # Filter dataset deklaratif khusus untuk visualisasi satu wilayah
    filtered_df = df.filter(lambda r: r["region"] == "ap-southeast")
    engine_filtered = DeclarativeEngine(filtered_df)

    line_spec = {
        "title": "Profil Latensi Sepanjang Hari (ap-southeast)",
        "mark": "line",
        "encoding": {
            "x": "time",
            "y": "latency_ms"
        }
    }
    line_view = engine_filtered.render_line_plot(line_spec, width=50, height=8)
    print(line_view)
    print()

    # --- 4. Interactive Spec Mutation & Re-evaluation Simulation ---
    print(f"{BOLD}4. REACTIVE STATE ENGINE BENCHMARK{RESET}")
    start_t = time.perf_counter()
    iterations = 500
    for _ in range(iterations):
        _ = df.aggregate("region", "throughput_rps", "sum")
    duration = time.perf_counter() - start_t

    ops_per_sec = iterations / duration
    print(f"  {GREEN}✔{RESET} Aggregation Benchmark: {iterations} run dalam {duration*1000:.2f} ms ({ops_per_sec:,.0f} ops/sec)")
    print(f"  {GREEN}✔{RESET} Declarative Specification Pipeline valid & berhasil dirender.\n")
    print(f"{BOLD}{BG_DARK}{GREEN} [LAB SELESAI] Pipeline Declarative Dashboarding berjalan sukses. {RESET}")


if __name__ == "__main__":
    main()