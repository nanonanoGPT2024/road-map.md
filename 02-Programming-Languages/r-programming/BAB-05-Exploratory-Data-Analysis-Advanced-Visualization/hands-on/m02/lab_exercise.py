#!/usr/bin/env python3
"""
Lab Hands-on: R-Programming (Advanced Data Science & Visualization)
Chapter 05: Exploratory Data Analysis & Advanced Visualization - Deep Dive
Simulating R's 'tidyverse' Pipeline, Grammar of Graphics (ggplot2), and Summary Statistics
Standard Library Implementation (Zero External Dependencies)
"""

import math
import random
import sys
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

# --- ANSI Terminal Styling ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
RED = "\033[31m"
BG_DARK = "\033[48;5;236m"

# ============================================================================
# Section 1: Statistical Engine (Emulating R Base Math & Stats)
# ============================================================================

def mean(data: List[float]) -> float:
    """Computes arithmetic mean, equivalent to R's mean()."""
    return sum(data) / len(data) if data else 0.0

def variance(data: List[float], ddof: int = 1) -> float:
    """Computes sample variance, equivalent to R's var()."""
    n = len(data)
    if n <= ddof:
        return 0.0
    m = mean(data)
    return sum((x - m) ** 2 for x in data) / (n - ddof)

def sd(data: List[float]) -> float:
    """Computes standard deviation, equivalent to R's sd()."""
    return math.sqrt(variance(data, ddof=1))

def quantile(data: List[float], probs: List[float]) -> List[float]:
    """
    Computes sample quantiles using Type 7 algorithm (R's default quantile()).
    Q[p] = (1 - gamma) * x[j] + gamma * x[j+1]
    """
    if not data:
        return [0.0] * len(probs)
    sorted_d = sorted(data)
    n = len(sorted_d)
    results = []
    for p in probs:
        if p <= 0:
            results.append(float(sorted_d[0]))
        elif p >= 1:
            results.append(float(sorted_d[-1]))
        else:
            h = (n - 1) * p
            j = math.floor(h)
            gamma = h - j
            q = (1.0 - gamma) * sorted_d[j] + gamma * sorted_d[min(j + 1, n - 1)]
            results.append(q)
    return results

def pearson_cor(x: List[float], y: List[float]) -> float:
    """Computes Pearson correlation coefficient r, equivalent to R's cor(x, y)."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    mx, my = mean(x), mean(y)
    numerator = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denominator = math.sqrt(sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y))
    return numerator / denominator if denominator != 0 else 0.0

# ============================================================================
# Section 2: Data Frame & Tidy Operations (Emulating dplyr)
# ============================================================================

class DataFrame:
    """Columnar Data Frame representing an R data.frame/tibble."""
    def __init__(self, data: Dict[str, List[Any]]):
        self.columns = list(data.keys())
        self._data = data
        self._nrows = len(data[self.columns[0]]) if self.columns else 0

    def nrow(self) -> int:
        return self._nrows

    def ncol(self) -> int:
        return len(self.columns)

    def __getitem__(self, col_name: str) -> List[Any]:
        return self._data[col_name]

    def summary(self) -> Dict[str, Dict[str, float]]:
        """Generates 5-number summary + Mean for numeric columns."""
        res = {}
        for col in self.columns:
            vals = self._data[col]
            if isinstance(vals[0], (int, float)):
                fvals = [float(v) for v in vals]
                q0, q25, q50, q75, q100 = quantile(fvals, [0.0, 0.25, 0.50, 0.75, 1.0])
                res[col] = {
                    "Min.": q0,
                    "1st Qu.": q25,
                    "Median": q50,
                    "Mean": mean(fvals),
                    "3rd Qu.": q75,
                    "Max.": q100,
                    "IQR": q75 - q25
                }
        return res

    def group_by(self, group_col: str) -> Dict[str, 'DataFrame']:
        """Groups data by a factor variable (emulates dplyr::group_by)."""
        groups = defaultdict(lambda: defaultdict(list))
        for row_idx in range(self._nrows):
            key = str(self._data[group_col][row_idx])
            for col in self.columns:
                groups[key][col].append(self._data[col][row_idx])
        return {k: DataFrame(v) for k, v in groups.items()}

# ============================================================================
# Section 3: Grammar of Graphics Terminal Engine (Emulating ggplot2)
# ============================================================================

class TerminalCanvas:
    """Text-based 2D Coordinate Grid with ANSI color layer."""
    def __init__(self, width: int = 60, height: int = 18):
        self.width = width
        self.height = height
        self.grid = [[" " for _ in range(width)] for _ in range(height)]
        self.colors = [["" for _ in range(width)] for _ in range(height)]

    def draw_point(self, x_cell: int, y_cell: int, char: str, color_code: str):
        if 0 <= x_cell < self.width and 0 <= y_cell < self.height:
            self.grid[y_cell][x_cell] = char
            self.colors[y_cell][x_cell] = color_code

    def render(self, y_min: float, y_max: float, x_min: float, x_max: float,
               x_label: str, y_label: str):
        """Draws axes, ticks, grid, and colored glyphs."""
        print(f"\n{BOLD}{CYAN}=== ggplot2 ANSI Visual Canvas ==={RESET}")
        print(f"{DIM}Mapping: [Y: {y_label}] vs [X: {x_label}]{RESET}\n")

        # Top border
        print(f"       {DIM}┌" + "─" * self.width + f"┐{RESET}")
        for r in range(self.height):
            # Calculate tick label for Y axis
            y_val = y_max - (r / (self.height - 1)) * (y_max - y_min)
            row_str = "".join(f"{self.colors[r][c]}{self.grid[r][c]}{RESET}" for c in range(self.width))
            print(f"{y_val:6.1f} {DIM}│{RESET}{row_str}{DIM}│{RESET}")

        # Bottom border
        print(f"       {DIM}└" + "─" * self.width + f"┘{RESET}")
        # X-axis ticks
        x_ticks = f"       {x_min:<8.1f}" + " " * (self.width - 24) + f"{x_max:>16.1f}"
        print(f"{DIM}{x_ticks}{RESET}")
        print(f"       {BOLD}{x_label:^{self.width}}{RESET}\n")

def geom_point(df: DataFrame, x_col: str, y_col: str, color_col: str,
               width: int = 58, height: int = 16):
    """
    Renders a scatter plot mapping aesthetics (x, y, color) to terminal grid.
    Emulates ggplot(df, aes(x=x, y=y, color=factor)) + geom_point()
    """
    x_vals = [float(v) for v in df[x_col]]
    y_vals = [float(v) for v in df[y_col]]
    c_vals = [str(v) for v in df[color_col]]

    x_min, x_max = min(x_vals), max(x_vals)
    y_min, y_max = min(y_vals), max(y_vals)
    
    # Margin extension
    x_span = (x_max - x_min) if (x_max - x_min) > 0 else 1.0
    y_span = (y_max - y_min) if (y_max - y_min) > 0 else 1.0

    canvas = TerminalCanvas(width, height)

    # Color palette mapping for categorical factor
    unique_levels = sorted(list(set(c_vals)))
    palette = [GREEN, MAGENTA, CYAN, YELLOW, BLUE]
    color_map = {level: palette[i % len(palette)] for i, level in enumerate(unique_levels)}
    glyphs = ["●", "▲", "◆", "■", "✦"]
    glyph_map = {level: glyphs[i % len(glyphs)] for i, level in enumerate(unique_levels)}

    for x, y, cat in zip(x_vals, y_vals, c_vals):
        # Map values to grid coordinates
        col_idx = int(((x - x_min) / x_span) * (width - 1))
        row_idx = int(((y_max - y) / y_span) * (height - 1))
        canvas.draw_point(col_idx, row_idx, glyph_map[cat], color_map[cat])

    canvas.render(y_min, y_max, x_min, x_max, x_col, y_col)

    # Legend
    legend = "Legend: " + "  ".join(
        f"{color_map[k]}{glyph_map[k]} {k}{RESET}" for k in unique_levels
    )
    print(f"  {legend}\n")

def geom_boxplot(df: DataFrame, cat_col: str, num_col: str, canvas_width: int = 50):
    """
    Generates terminal ASCII Tukey Box-and-Whisker plots across factors.
    Emulates ggplot(df, aes(x=cat, y=num)) + geom_boxplot()
    """
    groups = df.group_by(cat_col)
    all_num = [float(v) for v in df[num_col]]
    global_min, global_max = min(all_num), max(all_num)
    span = (global_max - global_min) if (global_max - global_min) > 0 else 1.0

    print(f"{BOLD}{CYAN}=== EDA: Tukey Boxplot & Outlier Detection [{num_col} by {cat_col}] ==={RESET}")
    print(f"{DIM}Global Range: [{global_min:.2f} ... {global_max:.2f}]{RESET}\n")

    for cat_name, sub_df in groups.items():
        vals = sorted([float(v) for v in sub_df[num_col]])
        q0, q25, q50, q75, q100 = quantile(vals, [0.0, 0.25, 0.50, 0.75, 1.0])
        iqr = q75 - q25
        lower_fence = max(q0, q25 - 1.5 * iqr)
        upper_fence = min(q100, q75 + 1.5 * iqr)
        
        # Outliers identification
        outliers = [v for v in vals if v < lower_fence or v > upper_fence]

        # Project to text positions
        def to_idx(val: float) -> int:
            return max(0, min(canvas_width - 1, int(((val - global_min) / span) * (canvas_width - 1))))

        line = [" "] * canvas_width
        
        i_lf = to_idx(lower_fence)
        i_q25 = to_idx(q25)
        i_q50 = to_idx(q50)
        i_q75 = to_idx(q75)
        i_uf = to_idx(upper_fence)

        # Draw whiskers
        for i in range(i_lf, i_q25):
            line[i] = "─"
        for i in range(i_q75 + 1, i_uf + 1):
            line[i] = "─"

        # Draw Whisker Caps
        line[i_lf] = "├"
        line[i_uf] = "┤"

        # Draw Interquartile Box
        for i in range(i_q25, i_q75 + 1):
            line[i] = "▒"
        line[i_q25] = "│"
        line[i_q75] = "│"
        line[i_q50] = f"{YELLOW}█{RESET}"

        # Draw Outliers
        for out in outliers:
            line[to_idx(out)] = f"{RED}*{RESET}"

        formatted_line = "".join(line)
        print(f" {BOLD}{cat_name:<8}{RESET} |{formatted_line}| {DIM}[Med: {q50:5.1f}, IQR: {iqr:4.1f}]{RESET}")

    # Scale bar
    print(" " * 11 + "└" + "─" * (canvas_width - 2) + "┘")
    print(f"           {global_min:<8.1f}" + " " * (canvas_width - 20) + f"{global_max:>8.1f}\n")

# ============================================================================
# Section 4: Correlation Matrix & EDA Diagnostics
# ============================================================================

def correlation_matrix(df: DataFrame, num_cols: List[str]):
    """Computes and formats a Pearson correlation matrix, like R's cor()."""
    print(f"{BOLD}{CYAN}=== Correlation Matrix (Pearson's r) ==={RESET}")
    header = "          " + "".join(f"{col:>10}" for col in num_cols)
    print(f"{DIM}{header}{RESET}")

    for row_col in num_cols:
        row_str = f"{BOLD}{row_col:<10}{RESET}"
        for col_col in num_cols:
            r = pearson_cor(
                [float(x) for x in df[row_col]],
                [float(y) for y in df[col_col]]
            )
            color = GREEN if r > 0.6 else (RED if r < -0.6 else DIM)
            row_str += f"{color}{r:10.3f}{RESET}"
        print(row_str)
    print()

# ============================================================================
# Section 5: Mock Synthetic Dataset Generation (Synthetic mtcars/iris equivalent)
# ============================================================================

def generate_telemetry_dataset(n: int = 120) -> DataFrame:
    """Generates synthetic multi-factor telemetry dataset for EDA exploration."""
    random.seed(42)
    categories = ["Cluster-A", "Cluster-B", "Cluster-C"]
    
    cpu_loads, memory_usages, latencies, clusters = [], [], [], []

    for _ in range(n):
        cat = random.choices(categories, weights=[0.4, 0.35, 0.25])[0]
        clusters.append(cat)
        
        if cat == "Cluster-A":
            cpu = random.gauss(35.0, 8.0)
            mem = cpu * 1.8 + random.gauss(20.0, 5.0)
            lat = mem * 0.4 + random.gauss(15.0, 3.0)
        elif cat == "Cluster-B":
            cpu = random.gauss(65.0, 10.0)
            mem = cpu * 1.2 + random.gauss(40.0, 8.0)
            lat = mem * 0.8 + random.gauss(30.0, 6.0)
        else: # Cluster-C (High Load & Outliers)
            cpu = random.gauss(80.0, 12.0)
            mem = cpu * 2.1 + random.gauss(10.0, 12.0)
            lat = mem * 1.5 + random.gauss(50.0, 15.0)

        # Inject periodic edge anomalies
        if random.random() < 0.05:
            lat += random.uniform(80.0, 120.0)

        cpu_loads.append(max(5.0, round(cpu, 2)))
        memory_usages.append(max(10.0, round(mem, 2)))
        latencies.append(max(2.0, round(lat, 2)))

    return DataFrame({
        "cluster": clusters,
        "cpu_load": cpu_loads,
        "mem_usage": memory_usages,
        "latency_ms": latencies
    })

# ============================================================================
# Section 6: Main Execution Pipeline
# ============================================================================

def main():
    print(f"\n{BOLD}{MAGENTA}=================================================================={RESET}")
    print(f"{BOLD}{MAGENTA}   R-PROGRAMMING: EXPLORATORY DATA ANALYSIS & GGPLOT2 ENGINE      {RESET}")
    print(f"{BOLD}{MAGENTA}   Lab Chapter 05 - Deep Dive Technical Simulation                {RESET}")
    print(f"{BOLD}{MAGENTA}=================================================================={RESET}\n")

    # 1. Dataset Initialization
    df = generate_telemetry_dataset(n=150)
    print(f"{GREEN}[✓]{RESET} Loaded Synthetic Dataset: {df.nrow()} rows x {df.ncol()} columns")
    print(f"    Variables: {', '.join(df.columns)}\n")

    # 2. EDA Summary (Tukey 5-Number + Mean)
    print(f"{BOLD}{CYAN}=== R-Style summary() Five-Number Summary Output ==={RESET}")
    summaries = df.summary()
    for col_name, stats in summaries.items():
        print(f"{BOLD}${col_name}{RESET}")
        stats_line = "  ".join(f"{k}: {v:6.2f}" for k, v in stats.items())
        print(f"  {stats_line}")
    print()

    # 3. Correlation Diagnostics
    numeric_vars = ["cpu_load", "mem_usage", "latency_ms"]
    correlation_matrix(df, numeric_vars)

    # 4. Boxplot Visualization (geom_boxplot)
    geom_boxplot(df, cat_col="cluster", num_col="latency_ms", canvas_width=48)

    # 5. Grammar of Graphics Scatter Plot (geom_point + aes)
    geom_point(df, x_col="cpu_load", y_col="mem_usage", color_col="cluster", width=62, height=14)

    # 6. Grouped Aggregation (dplyr::summarise)
    print(f"{BOLD}{CYAN}=== Grouped Aggregation (dplyr: group_by(cluster) %>% summarize()) ==={RESET}")
    grouped = df.group_by("cluster")
    print(f"  {'Cluster':<12} {'Count':<8} {'Mean CPU':<12} {'Mean Latency':<14} {'Latency SD':<12}")
    print(f"  {DIM}{'-'*58}{RESET}")
    for grp_name, grp_df in sorted(grouped.items()):
        cpu_m = mean([float(x) for x in grp_df["cpu_load"]])
        lat_m = mean([float(x) for x in grp_df["latency_ms"]])
        lat_s = sd([float(x) for x in grp_df["latency_ms"]])
        cnt = grp_df.nrow()
        print(f"  {grp_name:<12} {cnt:<8} {cpu_m:<12.2f} {lat_m:<14.2f} {lat_s:<12.2f}")

    print(f"\n{GREEN}[✓] EDA & Graphics Pipeline executed cleanly without third-party libraries.{RESET}\n")

if __name__ == "__main__":
    main()