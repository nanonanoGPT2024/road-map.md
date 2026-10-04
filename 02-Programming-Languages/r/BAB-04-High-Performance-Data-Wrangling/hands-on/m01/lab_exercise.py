#!/usr/bin/env python3
"""
Hands-on Lab Exercise: High-Performance Data Wrangling Simulator (R data.table Paradigm)
BAB-04: High-Performance Data Wrangling (R Language Concept Emulation in Python)

This standalone lab demonstrates the architectural mechanics behind R's data.table:
1. Reference Semantics (In-Place Mutation `:=`) vs Copy-on-Modify (R base data.frame)
2. Fast Secondary Indexing / Binary Search (`setkey`) vs Full Vector Scan O(N)
3. Grouped Aggregation via Hash Partitioning (`DT[i, j, by]`)
"""

import sys
import time
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from bisect import bisect_left

# ANSI Terminal Color Palette
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"
C_BLUE = "\033[94m"
C_DIM = "\033[2m"

def print_banner(title: str):
    width = 76
    print(f"\n{C_CYAN}{'=' * width}{C_RESET}")
    print(f"{C_BOLD}{C_YELLOW} {title.center(width - 2)} {C_RESET}")
    print(f"{C_CYAN}{'=' * width}{C_RESET}\n")

def print_section(title: str):
    print(f"\n{C_MAGENTA}--- [ {title} ] ---{C_RESET}")

@dataclass
class Record:
    row_id: int
    region: str
    category: str
    amount: float
    discount_pct: float

class DataFrameBase:
    """Simulates R's Base data.frame with Copy-on-Modify semantics."""
    def __init__(self, data: List[Record]):
        self.rows: List[Record] = [Record(r.row_id, r.region, r.category, r.amount, r.discount_pct) for r in data]

    def modify_column_copy_on_write(self, multiplier: float) -> "DataFrameBase":
        """Simulates Base R memory duplication when updating a single column."""
        # Deep copy simulated
        new_rows = [
            Record(r.row_id, r.region, r.category, r.amount * multiplier, r.discount_pct)
            for r in self.rows
        ]
        return DataFrameBase(new_rows)

class DataTableFast:
    """
    Simulates R's data.table paradigm:
    - In-place column updates (:= operator)
    - Key indexing for binary search filtering
    - DT[i, j, by] expression model
    """
    def __init__(self, data: List[Record]):
        self.rows: List[Record] = data
        self.key_index: Dict[str, List[int]] = {}
        self.sorted_keys: List[str] = []
        self.sorted_index_map: List[Tuple[str, int]] = []
        self.has_key = False

    def in_place_update(self, multiplier: float) -> None:
        """Emulates data.table `DT[, amount := amount * multiplier]` (No memory reallocation)."""
        for r in self.rows:
            r.amount *= multiplier

    def set_key(self, column: str = "region") -> None:
        """Emulates `setkey(DT, region)` in R data.table."""
        if column != "region":
            raise NotImplementedError("Lab focuses on region key indexing.")
        
        # Build sorted list for binary search
        indexed = sorted([(self.rows[idx].region, idx) for idx in range(len(self.rows))], key=lambda x: x[0])
        self.sorted_keys = [item[0] for item in indexed]
        self.sorted_index_map = indexed
        self.has_key = True

    def scan_filter(self, target_region: str) -> List[Record]:
        """Emulates standard O(N) full vector scan in base R: `df[df$region == target, ]`"""
        return [r for r in self.rows if r.region == target_region]

    def binary_search_filter(self, target_region: str) -> List[Record]:
        """Emulates fast O(log N) key search in data.table: `DT[.(target_region)]`"""
        if not self.has_key:
            raise RuntimeError("Key not set. Run set_key() first.")
        
        left_idx = bisect_left(self.sorted_keys, target_region)
        results = []
        while left_idx < len(self.sorted_keys) and self.sorted_keys[left_idx] == target_region:
            row_idx = self.sorted_index_map[left_idx][1]
            results.append(self.rows[row_idx])
            left_idx += 1
        return results

    def aggregate_by(self, group_col: str = "region") -> Dict[str, Dict[str, float]]:
        """Emulates `DT[, .(total = sum(amount), avg = mean(amount)), by = region]`"""
        grouped: Dict[str, List[float]] = {}
        for r in self.rows:
            key = getattr(r, group_col)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r.amount)

        summary = {}
        for k, values in grouped.items():
            summary[k] = {
                "count": len(values),
                "total": sum(values),
                "mean": sum(values) / len(values) if values else 0.0
            }
        return summary

def generate_synthetic_dataset(num_records: int = 150_000) -> List[Record]:
    regions = ["North", "South", "East", "West", "Central", "Overseas"]
    categories = ["Tech", "Office", "Furniture", "Hardware", "Cloud"]
    random.seed(42)
    
    print(f"{C_DIM}Generating {num_records:,} rows of synthetic transactional records...{C_RESET}")
    records = []
    for i in range(num_records):
        records.append(Record(
            row_id=i + 1,
            region=random.choice(regions),
            category=random.choice(categories),
            amount=round(random.uniform(10.0, 5000.0), 2),
            discount_pct=round(random.uniform(0.0, 0.35), 2)
        ))
    return records

def run_experiment_1_memory_semantics(sample_data: List[Record]):
    print_section("Eksperimen 1: Copy-on-Modify (data.frame) vs In-Place Mutation (data.table `:=`)")
    
    # 1. Base R Copy-on-Write emulation
    df_base = DataFrameBase(sample_data[:50_000])
    t0 = time.perf_counter()
    _ = df_base.modify_column_copy_on_write(1.05)
    t_base = (time.perf_counter() - t0) * 1000

    # 2. data.table In-Place emulation
    dt_fast = DataTableFast([Record(r.row_id, r.region, r.category, r.amount, r.discount_pct) for r in sample_data[:50_000]])
    t0 = time.perf_counter()
    dt_fast.in_place_update(1.05)
    t_dt = (time.perf_counter() - t0) * 1000

    print(f"  {C_RED}[Base R data.frame]{C_RESET} Duplicate + Update : {C_BOLD}{t_base:8.2f} ms{C_RESET}")
    print(f"  {C_GREEN}[R data.table `:=`]{C_RESET} Direct In-Place Modify: {C_BOLD}{t_dt:8.2f} ms{C_RESET}")
    speedup = t_base / t_dt if t_dt > 0 else float("inf")
    print(f"  {C_CYAN}--> In-place speedup factor: {speedup:.2f}x (Zero Allocation Overhead){C_RESET}")

def run_experiment_2_key_indexing(sample_data: List[Record]):
    print_section("Eksperimen 2: Full Vector Scan O(N) vs Secondary Key Binary Search O(log N)")
    
    dt = DataTableFast([Record(r.row_id, r.region, r.category, r.amount, r.discount_pct) for r in sample_data])
    target_region = "Central"

    # Full Vector Scan
    t0 = time.perf_counter()
    res_scan = dt.scan_filter(target_region)
    t_scan = (time.perf_counter() - t0) * 1000

    # Indexing setup
    t0 = time.perf_counter()
    dt.set_key("region")
    t_key = (time.perf_counter() - t0) * 1000
    print(f"  {C_DIM}Waktu indexing `setkey(DT, region)`: {t_key:.2f} ms{C_RESET}")

    # Binary Search Query
    t0 = time.perf_counter()
    res_index = dt.binary_search_filter(target_region)
    t_query = (time.perf_counter() - t0) * 1000

    assert len(res_scan) == len(res_index), "Inkonsistensi hasil query filter!"
    print(f"  {C_YELLOW}[Vector Scan O(N)]{C_RESET} Query records ({len(res_scan):,} rows): {C_BOLD}{t_scan:8.3f} ms{C_RESET}")
    print(f"  {C_GREEN}[data.table Key]{C_RESET}   Binary Search ({len(res_index):,} rows): {C_BOLD}{t_query:8.3f} ms{C_RESET}")
    speedup = t_scan / t_query if t_query > 0 else float("inf")
    print(f"  {C_CYAN}--> Query retrieval speedup factor: {speedup:.2f}x{C_RESET}")

def run_experiment_3_group_aggregation(sample_data: List[Record]):
    print_section("Eksperimen 3: DT[i, j, by] Aggregation Engine Mechanics")
    
    dt = DataTableFast([Record(r.row_id, r.region, r.category, r.amount, r.discount_pct) for r in sample_data])
    
    t0 = time.perf_counter()
    grouped_stats = dt.aggregate_by("region")
    t_agg = (time.perf_counter() - t0) * 1000

    print(f"  {C_GREEN}Aggregation selesai dalam {t_agg:.2f} ms{C_RESET} across {len(grouped_stats)} distinct regions.\n")
    print(f"  {C_BOLD}{'Region':<12} | {'Count':>10} | {'Total Amount ($)':>18} | {'Mean Amount ($)':>16}{C_RESET}")
    print("  " + "-" * 64)
    for reg, stats in sorted(grouped_stats.items()):
        print(f"  {C_BLUE}{reg:<12}{C_RESET} | {stats['count']:10,d} | {stats['total']:18,.2f} | {stats['mean']:16,.2f}")

def interactive_cli():
    print_banner("R BAB-04: High-Performance Data Wrangling (Interactive Lab)")
    print(f"{C_BOLD}Simulasi Arsitektur R data.table vs Base data.frame di Terminal{C_RESET}\n")
    
    dataset = generate_synthetic_dataset(120_000)
    
    while True:
        print(f"\n{C_YELLOW}PILIHAN LAB INTERAKTIF:{C_RESET}")
        print("  [1] Jalankan Benchmark In-Place Mutation `:=` vs Copy-on-Modify")
        print("  [2] Jalankan Benchmark Secondary Key `setkey()` vs Vector Scan")
        print("  [3] Jalankan Simulasi `DT[i, j, by]` Group-by Aggregation")
        print("  [4] Jalankan Semua Benchmark Sekaligus (Automated Full Audit)")
        print("  [0] Keluar")
        
        choice = input(f"\n{C_CYAN}Masukkan nomor pilihan (0-4): {C_RESET}").strip()
        
        if choice == "1":
            run_experiment_1_memory_semantics(dataset)
        elif choice == "2":
            run_experiment_2_key_indexing(dataset)
        elif choice == "3":
            run_experiment_3_group_aggregation(dataset)
        elif choice == "4":
            run_experiment_1_memory_semantics(dataset)
            run_experiment_2_key_indexing(dataset)
            run_experiment_3_group_aggregation(dataset)
            print(f"\n{C_GREEN}{C_BOLD}[OK] Semua modul verifikasi kinerja selesai dieksekusi.{C_RESET}\n")
        elif choice == "0":
            print(f"\n{C_MAGENTA}Sesi Hands-on Lab selesai. Terima kasih.{C_RESET}\n")
            sys.exit(0)
        else:
            print(f"{C_RED}Pilihan tidak valid. Silakan pilih 0-4.{C_RESET}")

if __name__ == "__main__":
    # If run in non-interactive / automated pipe mode, execute full benchmarks
    if not sys.stdin.isatty():
        print_banner("R BAB-04: High-Performance Data Wrangling (Automated Run)")
        data = generate_synthetic_dataset(80_000)
        run_experiment_1_memory_semantics(data)
        run_experiment_2_key_indexing(data)
        run_experiment_3_group_aggregation(data)
        print(f"\n{C_GREEN}{C_BOLD}[OK] Automated execution completed successfully.{C_RESET}\n")
    else:
        interactive_cli()
