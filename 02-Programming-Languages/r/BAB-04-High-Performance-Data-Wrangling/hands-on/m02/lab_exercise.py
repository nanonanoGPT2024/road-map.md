#!/usr/bin/env python3
"""
Lab Exercise: High-Performance Data Wrangling (Tidyverse vs data.table Internals)
Simulating R's Data Processing Paradigms: Copy-on-Modify vs In-Place Reference Semantics,
Full Columnar Scans vs Keyed Binary Search Indices, and Split-Apply-Combine vs Single-Pass Grouping.
"""

import sys
import time
import random
from collections import defaultdict
from bisect import bisect_left, bisect_right

# Terminal ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# -------------------------------------------------------------------------
# Paradigm 1: Tidyverse Simulation (Copy-on-Modify & Full Vectorized Scans)
# -------------------------------------------------------------------------
class TidyFrame:
    """
    Simulates dplyr / tibble semantics.
    Enforces functional immutability: modifications clone internal column buffers
    (Copy-on-Modify), and filtering executes full sequential predicate evaluations.
    """
    def __init__(self, data_dict):
        self.columns = {k: list(v) for k, v in data_dict.items()}
        self.nrow = len(next(iter(self.columns.values()))) if self.columns else 0

    def mutate(self, col_name, values):
        """Simulates dplyr::mutate() with deep copy of column dictionary."""
        new_cols = {k: list(v) for k, v in self.columns.items()}
        new_cols[col_name] = list(values)
        return TidyFrame(new_cols)

    def filter(self, predicate_col, target_val):
        """Simulates dplyr::filter() via exhaustive sequential predicate evaluation."""
        mask = [val == target_val for val in self.columns[predicate_col]]
        new_cols = {
            col: [val for val, keep in zip(data, mask) if keep]
            for col, data in self.columns.items()
        }
        return TidyFrame(new_cols)

    def summarize_group(self, group_col, agg_col):
        """Simulates dplyr::group_by() %>% summarize() via Split-Apply-Combine."""
        # 1. Split phase: build distinct partitions
        partitions = defaultdict(list)
        for g_val, a_val in zip(self.columns[group_col], self.columns[agg_col]):
            partitions[g_val].append(a_val)
        
        # 2. Apply & Combine phase
        result = {}
        for group, vals in partitions.items():
            result[group] = sum(vals)
        return result


# -------------------------------------------------------------------------
# Paradigm 2: data.table Simulation (Reference Semantics & Keyed Fast-Lookups)
# -------------------------------------------------------------------------
class DataTable:
    """
    Simulates R data.table semantics.
    Applies in-place modifications (:=), secondary key ordering for sub-linear
    binary searches, and single-pass hash accumulation for grouping.
    """
    def __init__(self, data_dict):
        # Stores columns directly by reference
        self.columns = data_dict
        self.nrow = len(next(iter(self.columns.values()))) if self.columns else 0
        self.keys = {}
        self.sorted_orders = {}

    def update_inplace(self, col_name, values):
        """Simulates data.table `:=` operator modifying pointer without full copy."""
        self.columns[col_name] = values
        if self.nrow == 0:
            self.nrow = len(values)
        return self

    def setkey(self, key_col):
        """
        Simulates data.table::setkey(). Pre-computes radix/sort indices
        to allow O(log N) binary search lookups on vector slices.
        """
        col_vals = self.columns[key_col]
        # Generate row indices sorted by column values
        sorted_indices = sorted(range(self.nrow), key=lambda i: col_vals[i])
        sorted_values = [col_vals[i] for i in sorted_indices]
        
        self.keys[key_col] = sorted_values
        self.sorted_orders[key_col] = sorted_indices

    def fast_filter(self, key_col, target_val):
        """Simulates binary search subsetting DT[J(target_val)]."""
        if key_col not in self.keys:
            raise KeyError(f"No key index built for '{key_col}'. Call setkey() first.")

        sorted_values = self.keys[key_col]
        sorted_indices = self.sorted_orders[key_col]

        # Binary search for left and right boundaries
        left = bisect_left(sorted_values, target_val)
        right = bisect_right(sorted_values, target_val)

        matched_row_ids = sorted_indices[left:right]
        return {
            col: [data[idx] for idx in matched_row_ids]
            for col, data in self.columns.items()
        }

    def fast_summarize(self, group_col, agg_col):
        """Simulates data.table fast aggregation using single-pass hash accumulator."""
        groups = self.columns[group_col]
        aggs = self.columns[agg_col]
        agg_table = defaultdict(float)

        # Single-pass accumulation: avoiding memory overhead of partition lists
        for i in range(self.nrow):
            agg_table[groups[i]] += aggs[i]
        return agg_table


# -------------------------------------------------------------------------
# Benchmark Engine & Visual Comparison
# -------------------------------------------------------------------------
def generate_synthetic_data(n_rows):
    """Generates synthetic dataset simulating enterprise OLAP records."""
    departments = ["Engineering", "Marketing", "Finance", "Sales", "HR", "Support", "R&D", "Legal"]
    ids = list(range(100000, 100000 + n_rows))
    depts = [random.choice(departments) for _ in range(n_rows)]
    metrics = [round(random.uniform(30000.0, 150000.0), 2) for _ in range(n_rows)]
    return {"emp_id": ids, "dept": depts, "salary": metrics}


def run_benchmarks():
    N_ROWS = 250_000
    print(f"{BOLD}{CYAN}=== High-Performance Data Wrangling: R Paradigms Simulation ==={RESET}")
    print(f"Allocating synthetic workload: {BOLD}{N_ROWS:,}{RESET} rows...\n")

    raw_data = generate_synthetic_data(N_ROWS)

    # ---------------------------------------------------------------------
    # Test 1: Column Mutation / Addition
    # ---------------------------------------------------------------------
    print(f"{BOLD}[Benchmark 1: Mutation Semantics]{RESET}")
    
    bonus_data = [round(s * 0.10, 2) for s in raw_data["salary"]]
    tidy_df = TidyFrame(raw_data)
    dt = DataTable({k: list(v) for k, v in raw_data.items()})

    # Tidyverse Mutate (Cloning / Copy-on-Modify)
    t0 = time.perf_counter_ns()
    mutated_tidy = tidy_df.mutate("bonus", bonus_data)
    t_tidy_mutate = (time.perf_counter_ns() - t0) / 1e6

    # data.table Update In-Place (:=)
    t0 = time.perf_counter_ns()
    dt.update_inplace("bonus", bonus_data)
    t_dt_mutate = (time.perf_counter_ns() - t0) / 1e6

    print(f"  Tidyverse (Copy-on-Modify mutate) : {YELLOW}{t_tidy_mutate:8.2f} ms{RESET}")
    print(f"  data.table (In-place `:=` update) : {GREEN}{t_dt_mutate:8.2f} ms{RESET}")
    speedup_mutate = t_tidy_mutate / max(t_dt_mutate, 0.0001)
    print(f"  {BOLD}Performance Delta:{RESET} {GREEN}{speedup_mutate:.2f}x faster{RESET} using reference modification.\n")

    # ---------------------------------------------------------------------
    # Test 2: Subsetting / Filtering
    # ---------------------------------------------------------------------
    print(f"{BOLD}[Benchmark 2: Filtering / Subsetting]{RESET}")
    target_dept = "Finance"

    # Tidyverse Full Scan Filter
    t0 = time.perf_counter_ns()
    filtered_tidy = tidy_df.filter("dept", target_dept)
    t_tidy_filter = (time.perf_counter_ns() - t0) / 1e6

    # data.table Keying & Binary Search
    t0 = time.perf_counter_ns()
    dt.setkey("dept")
    t_index = (time.perf_counter_ns() - t0) / 1e6

    t0 = time.perf_counter_ns()
    filtered_dt = dt.fast_filter("dept", target_dept)
    t_dt_filter = (time.perf_counter_ns() - t0) / 1e6

    print(f"  Tidyverse (Full Scan Filter)       : {YELLOW}{t_tidy_filter:8.2f} ms{RESET}")
    print(f"  data.table (Binary Search Subsetting): {GREEN}{t_dt_filter:8.2f} ms{RESET} (Key Indexing: {t_index:.2f} ms)")
    speedup_filter = t_tidy_filter / max(t_dt_filter, 0.0001)
    print(f"  {BOLD}Performance Delta:{RESET} {GREEN}{speedup_filter:.2f}x faster{RESET} during query evaluation phase.\n")

    # ---------------------------------------------------------------------
    # Test 3: Grouped Aggregation
    # ---------------------------------------------------------------------
    print(f"{BOLD}[Benchmark 3: Group-by Aggregation]{RESET}")

    # Tidyverse Split-Apply-Combine
    t0 = time.perf_counter_ns()
    tidy_agg = tidy_df.summarize_group("dept", "salary")
    t_tidy_agg = (time.perf_counter_ns() - t0) / 1e6

    # data.table Hash Aggregation
    t0 = time.perf_counter_ns()
    dt_agg = dt.fast_summarize("dept", "salary")
    t_dt_agg = (time.perf_counter_ns() - t0) / 1e6

    print(f"  Tidyverse (Split-Apply-Combine)    : {YELLOW}{t_tidy_agg:8.2f} ms{RESET}")
    print(f"  data.table (Single-pass Hash Group): {GREEN}{t_dt_agg:8.2f} ms{RESET}")
    speedup_agg = t_tidy_agg / max(t_dt_agg, 0.0001)
    print(f"  {BOLD}Performance Delta:{RESET} {GREEN}{speedup_agg:.2f}x faster{RESET} avoiding intermediate list allocations.\n")

    # ---------------------------------------------------------------------
    # Summary Table
    # ---------------------------------------------------------------------
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}{'Operation':<24} | {'Tidyverse':<14} | {'data.table':<14} | {'Winner':<10}{RESET}")
    print(f"{'-'*60}")
    print(f"{'Column Mutate':<24} | {t_tidy_mutate:8.2f} ms    | {t_dt_mutate:8.2f} ms    | {GREEN}data.table{RESET}")
    print(f"{'Keyed Query':<24} | {t_tidy_filter:8.2f} ms    | {t_dt_filter:8.2f} ms    | {GREEN}data.table{RESET}")
    print(f"{'Group Aggregation':<24} | {t_tidy_agg:8.2f} ms    | {t_dt_agg:8.2f} ms    | {GREEN}data.table{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{CYAN}Architectural Conclusion:{RESET} Tidyverse optimizes for functional purity and expressive readability,")
    print(f"while data.table optimizes for cache locality, reference stability, and pointer manipulation.")


if __name__ == "__main__":
    run_benchmarks()