#!/usr/bin/env python3
"""
Lab Exercise: Exploratory Data Analysis & Advanced Visualization (EDA Simulation)
Simulasi Interaktif R Programming (Grammar of Graphics & EDA Pipeline)
Target: BAB-05 Exploratory Data Analysis & Advanced Visualization
"""

import math
import random
import sys
import time

# ==============================================================================
# ANSI Color Codes & Terminal Styling
# ==============================================================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"
    BG_MAGENTA = "\033[45m"
    BG_GRAY = "\033[100m"

# ==============================================================================
# Synthetic Dataset Generation (Simulasi palmerpenguins / mtcars)
# ==============================================================================
def generate_dataset(n=120, seed=42):
    random.seed(seed)
    species_list = ["Adelie", "Chinstrap", "Gentoo"]
    islands = ["Biscoe", "Dream", "Torgersen"]
    
    data = []
    for i in range(1, n + 1):
        sp = random.choice(species_list)
        isl = random.choice(islands)
        
        # Base distributions per species
        if sp == "Adelie":
            bill_len = round(random.gauss(38.8, 2.7), 1)
            bill_dep = round(random.gauss(18.3, 1.2), 1)
            flipper = int(random.gauss(190, 6.5))
            body_mass = int(random.gauss(3700, 450))
        elif sp == "Chinstrap":
            bill_len = round(random.gauss(48.8, 3.3), 1)
            bill_dep = round(random.gauss(18.4, 1.1), 1)
            flipper = int(random.gauss(195, 7.1))
            body_mass = int(random.gauss(3733, 380))
        else: # Gentoo
            bill_len = round(random.gauss(47.5, 3.1), 1)
            bill_dep = round(random.gauss(14.9, 1.0), 1)
            flipper = int(random.gauss(217, 6.5))
            body_mass = int(random.gauss(5076, 500))
            
        # Add correlation bill_len vs flipper
        bill_len += (flipper - 200) * 0.05
        bill_len = max(30.0, round(bill_len, 1))
        
        data.append({
            "id": i,
            "species": sp,
            "island": isl,
            "bill_length_mm": bill_len,
            "bill_depth_mm": bill_dep,
            "flipper_length_mm": flipper,
            "body_mass_g": body_mass
        })
    return data

# ==============================================================================
# EDA Descriptive Statistics & Outlier Detection
# ==============================================================================
def calculate_summary(values):
    n = len(values)
    if n == 0:
        return {}
    sorted_v = sorted(values)
    mean_val = sum(sorted_v) / n
    variance = sum((x - mean_val) ** 2 for x in sorted_v) / (n - 1 if n > 1 else 1)
    sd = math.sqrt(variance)
    
    def quantile(p):
        idx = p * (n - 1)
        low = int(math.floor(idx))
        high = int(math.ceil(idx))
        weight = idx - low
        return sorted_v[low] * (1.0 - weight) + sorted_v[high] * weight
        
    q1 = quantile(0.25)
    median = quantile(0.50)
    q3 = quantile(0.75)
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    outliers = [x for x in sorted_v if x < lower_fence or x > upper_fence]
    
    return {
        "n": n,
        "mean": mean_val,
        "sd": sd,
        "min": sorted_v[0],
        "q1": q1,
        "median": median,
        "q3": q3,
        "max": sorted_v[-1],
        "iqr": iqr,
        "outliers": outliers
    }

def print_summary_table(dataset):
    print(f"\n{Style.BOLD}{Style.CYAN}=== 1. DESCRIPTIVE SUMMARY STATISTICS (Base R `summary()` & psych) ==={Style.RESET}\n")
    numeric_cols = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"]
    header = f"{'Variable':<18} | {'N':>4} | {'Mean':>8} | {'StdDev':>8} | {'Min':>7} | {'Q1':>7} | {'Median':>7} | {'Q3':>7} | {'Max':>7} | {'Outliers':>8}"
    print(f"{Style.BOLD}{header}{Style.RESET}")
    print("-" * len(header))
    
    for col in numeric_cols:
        vals = [row[col] for row in dataset]
        stat = calculate_summary(vals)
        out_cnt = len(stat["outliers"])
        out_str = f"{Style.RED}{out_cnt:>8}{Style.RESET}" if out_cnt > 0 else f"{Style.GREEN}{'0':>8}{Style.RESET}"
        print(f"{col:<18} | {stat['n']:>4} | {stat['mean']:>8.2f} | {stat['sd']:>8.2f} | {stat['min']:>7.1f} | {stat['q1']:>7.1f} | {stat['median']:>7.1f} | {stat['q3']:>7.1f} | {stat['max']:>7.1f} | {out_str}")
    print("-" * len(header))

# ==============================================================================
# Grammar of Graphics Layer 1: geom_histogram() with Facets
# ==============================================================================
def render_histogram(dataset, col="flipper_length_mm", bins=12):
    print(f"\n{Style.BOLD}{Style.MAGENTA}=== 2. ADVANCED HISTOGRAM: ggplot(df, aes(x={col})) + geom_histogram() ==={Style.RESET}\n")
    vals = [row[col] for row in dataset]
    min_v, max_v = min(vals), max(vals)
    bin_width = (max_v - min_v) / bins
    
    bin_counts = [0] * bins
    for v in vals:
        idx = min(int((v - min_v) / bin_width), bins - 1)
        bin_counts[idx] += 1
        
    max_count = max(bin_counts)
    scale_bar = 35 / max_count if max_count > 0 else 1.0
    
    for i in range(bins):
        low_b = min_v + i * bin_width
        high_b = low_b + bin_width
        cnt = bin_counts[i]
        bar_len = int(cnt * scale_bar)
        bar = f"{Style.BG_CYAN}{' ' * bar_len}{Style.RESET}"
        print(f"[{low_b:>6.1f} - {high_b:>6.1f}] | {bar} {Style.BOLD}{cnt:>3}{Style.RESET} obs")

# ==============================================================================
# Grammar of Graphics Layer 2: geom_boxplot() (Tukey Visualizer)
# ==============================================================================
def render_boxplot(dataset, col="flipper_length_mm", group_by="species"):
    print(f"\n{Style.BOLD}{Style.YELLOW}=== 3. TUKEY BOXPLOT: ggplot(df, aes(x={group_by}, y={col})) + geom_boxplot() ==={Style.RESET}\n")
    groups = sorted(list(set(row[group_by] for row in dataset)))
    all_vals = [row[col] for row in dataset]
    global_min, global_max = min(all_vals), max(all_vals)
    width = 50
    
    def val_to_pos(v):
        return int(((v - global_min) / (global_max - global_min)) * (width - 1))
        
    print(f"{'Global Range:':<15} {global_min:.1f} {' ' * (width - 16)} {global_max:.1f}")
    print(f"{'Axis:':<15} |{'-' * (width - 2)}|")
    
    colors = {
        "Adelie": Style.GREEN,
        "Chinstrap": Style.CYAN,
        "Gentoo": Style.MAGENTA
    }
    
    for grp in groups:
        vals = [row[col] for row in dataset if row[group_by] == grp]
        st = calculate_summary(vals)
        c = colors.get(grp, Style.WHITE)
        
        p_min = val_to_pos(st["min"])
        p_q1 = val_to_pos(st["q1"])
        p_med = val_to_pos(st["median"])
        p_q3 = val_to_pos(st["q3"])
        p_max = val_to_pos(st["max"])
        
        line = [" "] * width
        # Whisker left
        for i in range(p_min, p_q1):
            line[i] = "─"
        line[p_min] = "├"
        # Box IQR
        for i in range(p_q1, p_q3 + 1):
            line[i] = "█"
        line[p_med] = "║"
        # Whisker right
        for i in range(p_q3 + 1, p_max + 1):
            line[i] = "─"
        line[p_max] = "┤"
        
        # Outliers
        for out in st["outliers"]:
            pos = val_to_pos(out)
            line[pos] = "●"
            
        rendered_line = "".join(line)
        print(f"{c}{grp:<15}{Style.RESET} {c}{rendered_line}{Style.RESET} (Med: {st['median']:.1f})")

# ==============================================================================
# Grammar of Graphics Layer 3: geom_point() Scatter Plot Simulation
# ==============================================================================
def render_scatterplot(dataset, x_col="bill_length_mm", y_col="body_mass_g", color_col="species"):
    print(f"\n{Style.BOLD}{Style.GREEN}=== 4. SCATTER PLOT: aes(x={x_col}, y={y_col}, color={color_col}) + geom_point() ==={Style.RESET}\n")
    grid_w, grid_h = 45, 15
    xs = [row[x_col] for row in dataset]
    ys = [row[y_col] for row in dataset]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    grid = [[(" ", None) for _ in range(grid_w)] for _ in range(grid_h)]
    species_colors = {
        "Adelie": Style.GREEN,
        "Chinstrap": Style.CYAN,
        "Gentoo": Style.MAGENTA
    }
    
    for row in dataset:
        gx = int(((row[x_col] - min_x) / (max_x - min_x)) * (grid_w - 1))
        gy = int(((row[y_col] - min_y) / (max_y - min_y)) * (grid_h - 1))
        # Invert gy for terminal row orientation
        row_idx = (grid_h - 1) - gy
        sp = row[color_col]
        grid[row_idx][gx] = ("*", species_colors.get(sp, Style.WHITE))
        
    print(f"{'Mass(g)':<8}")
    for r in range(grid_h):
        y_val = max_y - (r / (grid_h - 1)) * (max_y - min_y)
        row_str = "".join([f"{col}{ch}{Style.RESET}" if col else ch for ch, col in grid[r]])
        print(f"{y_val:>6.0f} | {row_str}")
    print(" " * 7 + "└" + "─" * grid_w)
    print(f"{'':>9}{min_x:<8.1f} {x_col} {' ' * (grid_w - 30)} {max_x:>8.1f}")
    print(f"Legend: {Style.GREEN}* Adelie{Style.RESET}   {Style.CYAN}* Chinstrap{Style.RESET}   {Style.MAGENTA}* Gentoo{Style.RESET}")

# ==============================================================================
# Correlation Matrix & Correlation Heatmap (corrplot simulation)
# ==============================================================================
def render_correlation_matrix(dataset):
    print(f"\n{Style.BOLD}{Style.BLUE}=== 5. CORRELATION HEATMAP (simulasi R `ggcorrplot` / `corrplot`) ==={Style.RESET}\n")
    cols = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"]
    
    def pearson(x, y):
        n = len(x)
        mx, my = sum(x) / n, sum(y) / n
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        den = math.sqrt(sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y))
        return num / den if den != 0 else 0.0
        
    print(f"{'Variable':<18} | " + " | ".join([f"{c[:10]:>10}" for c in cols]))
    print("-" * 65)
    
    for r_col in cols:
        row_str = f"{r_col:<18} | "
        for c_col in cols:
            vx = [row[r_col] for row in dataset]
            vy = [row[c_col] for row in dataset]
            r = pearson(vx, vy)
            
            if r == 1.0:
                color = Style.BOLD + Style.WHITE
            elif r > 0.5:
                color = Style.GREEN + Style.BOLD
            elif r > 0.2:
                color = Style.GREEN
            elif r < -0.5:
                color = Style.RED + Style.BOLD
            elif r < -0.2:
                color = Style.RED
            else:
                color = Style.DIM
                
            row_str += f"{color}{r:>10.2f}{Style.RESET} | "
        print(row_str)
    print("-" * 65)

# ==============================================================================
# Interactive CLI Menu
# ==============================================================================
def interactive_menu():
    dataset = generate_dataset(n=150)
    
    # Check if automated flag passed
    if "--demo" in sys.argv or "--all" in sys.argv or not sys.stdin.isatty():
        print(f"{Style.BOLD}{Style.BG_BLUE} RUNNING AUTOMATED EDA SUITE & VISUALIZATION PIPELINE {Style.RESET}")
        print_summary_table(dataset)
        render_histogram(dataset)
        render_boxplot(dataset)
        render_scatterplot(dataset)
        render_correlation_matrix(dataset)
        print(f"\n{Style.BOLD}{Style.GREEN}✓ Seluruh modul visualisasi & EDA telah berhasil dieksekusi.{Style.RESET}\n")
        return
        
    while True:
        print(f"\n{Style.BOLD}{Style.BG_CYAN} R-PROGRAMMING BAB-05 EDA & ADVANCED VISUALIZATION LAB {Style.RESET}")
        print(f"{Style.CYAN}1.{Style.RESET} Tampilkan Descriptive Summary Statistics")
        print(f"{Style.CYAN}2.{Style.RESET} Visualisasi Geom Histogram (Distribusi Frekuensi)")
        print(f"{Style.CYAN}3.{Style.RESET} Visualisasi Geom Boxplot (Tukey Five-Number Summary & Outliers)")
        print(f"{Style.CYAN}4.{Style.RESET} Visualisasi Geom Scatter Plot (Multivariate Aesthetics Mapping)")
        print(f"{Style.CYAN}5.{Style.RESET} Matriks Korelasi & Heatmap (Pearson Correlation)")
        print(f"{Style.CYAN}6.{Style.RESET} Jalankan Seluruh Pipeline EDA Secara Sekuensial")
        print(f"{Style.CYAN}0.{Style.RESET} Keluar (Exit)")
        
        choice = input(f"\n{Style.BOLD}Pilih menu [0-6]: {Style.RESET}").strip()
        
        if choice == "1":
            print_summary_table(dataset)
        elif choice == "2":
            render_histogram(dataset)
        elif choice == "3":
            render_boxplot(dataset)
        elif choice == "4":
            render_scatterplot(dataset)
        elif choice == "5":
            render_correlation_matrix(dataset)
        elif choice == "6":
            print_summary_table(dataset)
            render_histogram(dataset)
            render_boxplot(dataset)
            render_scatterplot(dataset)
            render_correlation_matrix(dataset)
        elif choice == "0":
            print(f"{Style.YELLOW}Sesi Lab EDA selesai. Sampai jumpa!{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan pilih 0-6.{Style.RESET}")

if __name__ == "__main__":
    interactive_menu()
