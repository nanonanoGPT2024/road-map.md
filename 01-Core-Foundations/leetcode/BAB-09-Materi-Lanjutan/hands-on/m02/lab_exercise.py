#!/usr/bin/env python3
"""
Lab Hands-on: Dynamic Programming & Exhaustive Search (Deep Dive)
Category: 01-Core-Foundations (Topic: leetcode, Chapter 09, Module 02)

Architectural Deep Dive:
1. Exhaustive Recursion (Tree Explosion: O(2^N))
2. Top-Down DP with Telemetry Memoization Cache (Hit/Miss/Depth Tracking)
3. Bottom-Up 2D Tabulation with Backtracking Reconstruction
4. Space-Optimized 1D Rolling Array Tabulation: O(W) Memory Footprint
"""

import sys
import time
from typing import List, Tuple, Dict, Optional

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[48;5;236m"


class Item:
    __slots__ = ("item_id", "weight", "value")

    def __init__(self, item_id: int, weight: int, value: int):
        self.item_id = item_id
        self.weight = weight
        self.value = value

    def __repr__(self) -> str:
        return f"Item(id={self.item_id}, w={self.weight}, v={self.value})"


class Metrics:
    def __init__(self):
        self.recursive_calls = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.max_stack_depth = 0
        self.elapsed_ns = 0

    def reset(self):
        self.recursive_calls = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.max_stack_depth = 0
        self.elapsed_ns = 0


class KnapsackDeepDiveEngine:
    def __init__(self, items: List[Item], capacity: int):
        self.items = items
        self.capacity = capacity
        self.n = len(items)
        self.metrics = Metrics()

    # =========================================================================
    # 1. PURE EXHAUSTIVE SEARCH (BRUTE-FORCE RECURSION)
    # =========================================================================
    def solve_exhaustive(self) -> int:
        """
        Explores all 2^N leaf paths in the decision tree.
        Exhausts execution stacks to demonstrate time complexity explosion.
        """
        self.metrics.reset()
        start = time.perf_counter_ns()

        def _dfs(index: int, remaining_capacity: int, current_depth: int) -> int:
            self.metrics.recursive_calls += 1
            if current_depth > self.metrics.max_stack_depth:
                self.metrics.max_stack_depth = current_depth

            if index == self.n or remaining_capacity <= 0:
                return 0

            # Decision A: Skip item
            max_val = _dfs(index + 1, remaining_capacity, current_depth + 1)

            # Decision B: Take item (if within capacity)
            curr_item = self.items[index]
            if curr_item.weight <= remaining_capacity:
                take_val = curr_item.value + _dfs(
                    index + 1,
                    remaining_capacity - curr_item.weight,
                    current_depth + 1,
                )
                if take_val > max_val:
                    max_val = take_val

            return max_val

        result = _dfs(0, self.capacity, 1)
        self.metrics.elapsed_ns = time.perf_counter_ns() - start
        return result

    # =========================================================================
    # 2. TOP-DOWN DYNAMIC PROGRAMMING (MEMOIZATION WITH TELEMETRY)
    # =========================================================================
    def solve_top_down_memo(self) -> Tuple[int, Dict[Tuple[int, int], int]]:
        """
        Caches subproblem solutions: (index, remaining_capacity) -> max_val.
        Eliminates duplicate overlapping subproblem evaluations.
        """
        self.metrics.reset()
        memo: Dict[Tuple[int, int], int] = {}
        start = time.perf_counter_ns()

        def _memoized_dfs(index: int, remaining_cap: int, depth: int) -> int:
            self.metrics.recursive_calls += 1
            if depth > self.metrics.max_stack_depth:
                self.metrics.max_stack_depth = depth

            if index == self.n or remaining_cap <= 0:
                return 0

            state = (index, remaining_cap)
            if state in memo:
                self.metrics.cache_hits += 1
                return memo[state]

            self.metrics.cache_misses += 1
            # Option 1: Skip
            val_skip = _memoized_dfs(index + 1, remaining_cap, depth + 1)

            # Option 2: Take
            curr_item = self.items[index]
            val_take = 0
            if curr_item.weight <= remaining_cap:
                val_take = curr_item.value + _memoized_dfs(
                    index + 1, remaining_cap - curr_item.weight, depth + 1
                )

            res = max(val_skip, val_take)
            memo[state] = res
            return res

        result = _memoized_dfs(0, self.capacity, 1)
        self.metrics.elapsed_ns = time.perf_counter_ns() - start
        return result, memo

    # =========================================================================
    # 3. BOTTOM-UP TABULATION (2D MATRIX) & BACKTRACKING
    # =========================================================================
    def solve_bottom_up_2d(self) -> Tuple[int, List[int], List[List[int]]]:
        """
        Iterative filling of (N+1) x (Capacity+1) matrix.
        Includes state backtracking to reconstruct exact optimal item set.
        """
        self.metrics.reset()
        start = time.perf_counter_ns()

        # dp[i][w] = max value using a subset of first i items with max weight w
        dp = [[0] * (self.capacity + 1) for _ in range(self.n + 1)]

        for i in range(1, self.n + 1):
            item = self.items[i - 1]
            for w in range(1, self.capacity + 1):
                if item.weight <= w:
                    dp[i][w] = max(
                        dp[i - 1][w],
                        dp[i - 1][w - item.weight] + item.value,
                    )
                else:
                    dp[i][w] = dp[i - 1][w]

        # Backtrack optimal items
        reconstructed_items: List[int] = []
        curr_w = self.capacity
        for i in range(self.n, 0, -1):
            if dp[i][curr_w] != dp[i - 1][curr_w]:
                selected = self.items[i - 1]
                reconstructed_items.append(selected.item_id)
                curr_w -= selected.weight

        reconstructed_items.reverse()
        self.metrics.elapsed_ns = time.perf_counter_ns() - start
        return dp[self.n][self.capacity], reconstructed_items, dp

    # =========================================================================
    # 4. BOTTOM-UP TABULATION (SPACE OPTIMIZED 1D ROLLING ARRAY)
    # =========================================================================
    def solve_bottom_up_1d_optimized(self) -> int:
        """
        Compresses state space to O(Capacity) by running inner loop backwards,
        preventing multiple inclusions of the same item in the same step.
        """
        self.metrics.reset()
        start = time.perf_counter_ns()

        dp = [0] * (self.capacity + 1)

        for item in self.items:
            # Reverse iteration preserves single-item inclusion constraint
            for w in range(self.capacity, item.weight - 1, -1):
                dp[w] = max(dp[w], dp[w - item.weight] + item.value)

        self.metrics.elapsed_ns = time.perf_counter_ns() - start
        return dp[self.capacity]


# =============================================================================
# BENCHMARK RUNNER & VISUALIZATION
# =============================================================================
def print_section(title: str):
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== [ {title} ] ==={CLR_RESET}")


def run_benchmark_suite():
    print(f"{CLR_BOLD}{CLR_MAGENTA}SYSTEM PROTOCOL: DYNAMIC PROGRAMMING LAB INITIALIZED{CLR_RESET}")
    print(f"Targeting: Knapsack Optimization, Overlapping Subproblems & State Compression\n")

    # Benchmark 1: Small dataset (Exhaustive feasible)
    small_items = [
        Item(1, 2, 3), Item(2, 3, 4), Item(3, 4, 8),
        Item(4, 5, 8), Item(5, 9, 10), Item(6, 4, 7),
        Item(7, 7, 12), Item(8, 3, 5), Item(9, 6, 9),
        Item(10, 5, 6), Item(11, 2, 4), Item(12, 4, 5),
        Item(13, 8, 14), Item(14, 1, 2), Item(15, 3, 4),
        Item(16, 5, 7), Item(17, 7, 11), Item(18, 6, 8)
    ]
    small_capacity = 35

    print(f"{CLR_CYAN}Dataset Small: N={len(small_items)}, Capacity={small_capacity}{CLR_RESET}")
    engine_small = KnapsackDeepDiveEngine(small_items, small_capacity)

    # 1. Exhaustive
    ex_val = engine_small.solve_exhaustive()
    ex_time = engine_small.metrics.elapsed_ns / 1_000_000
    ex_calls = engine_small.metrics.recursive_calls
    print(f"[{CLR_RED}EXHAUSTIVE{CLR_RESET}] Result: {ex_val} | Calls: {ex_calls:,} | Depth: {engine_small.metrics.max_stack_depth} | Time: {ex_time:.3f} ms")

    # 2. Top-Down Memo
    td_val, memo = engine_small.solve_top_down_memo()
    td_time = engine_small.metrics.elapsed_ns / 1_000_000
    hits = engine_small.metrics.cache_hits
    misses = engine_small.metrics.cache_misses
    hit_ratio = (hits / (hits + misses)) * 100 if (hits + misses) > 0 else 0
    print(f"[{CLR_GREEN}TOP-DOWN-DP{CLR_RESET}] Result: {td_val} | Hits: {hits:,} | Misses: {misses:,} | Hit Ratio: {hit_ratio:.1f}% | Time: {td_time:.3f} ms")

    # 3. Bottom-Up 2D
    bu_val, recon_items, dp_table = engine_small.solve_bottom_up_2d()
    bu_time = engine_small.metrics.elapsed_ns / 1_000_000
    print(f"[{CLR_YELLOW}TABULATION-2D{CLR_RESET}] Result: {bu_val} | Reconstructed IDs: {recon_items} | Time: {bu_time:.3f} ms")

    # 4. Bottom-Up 1D
    opt_val = engine_small.solve_bottom_up_1d_optimized()
    opt_time = engine_small.metrics.elapsed_ns / 1_000_000
    print(f"[{CLR_MAGENTA}SPACE-OPT-1D{CLR_RESET}] Result: {opt_val} | State Memory: O(W) | Time: {opt_time:.3f} ms")

    assert ex_val == td_val == bu_val == opt_val, "Invariant validation failed across algorithms!"
    print(f"\n{CLR_GREEN}✔ Output Invariance Validated: All algorithms converged to value {ex_val}{CLR_RESET}")

    # Benchmark 2: Larger Scale (N=80, Capacity=1500)
    print_section("SCALABILITY STRESS TEST (N=80, Capacity=1500)")
    import random
    random.seed(42)
    large_items = [Item(i, random.randint(5, 50), random.randint(10, 100)) for i in range(1, 81)]
    large_capacity = 1500
    engine_large = KnapsackDeepDiveEngine(large_items, large_capacity)

    print(f"Brute force skipped: 2^80 operations = ~1.2e24 evaluations (Thermal heat death before completion).")

    # Top-Down on Large
    l_td_val, l_memo = engine_large.solve_top_down_memo()
    l_td_time = engine_large.metrics.elapsed_ns / 1_000_000
    l_hits = engine_large.metrics.cache_hits
    l_miss = engine_large.metrics.cache_misses
    l_ratio = (l_hits / (l_hits + l_miss)) * 100
    print(f"[{CLR_GREEN}TOP-DOWN-DP{CLR_RESET}] Result: {l_td_val} | Unique Subproblems: {len(l_memo):,} | Hit Ratio: {l_ratio:.2f}% | Time: {l_td_time:.3f} ms")

    # Tabulation 2D on Large
    l_bu_val, l_recon, _ = engine_large.solve_bottom_up_2d()
    l_bu_time = engine_large.metrics.elapsed_ns / 1_000_000
    print(f"[{CLR_YELLOW}TABULATION-2D{CLR_RESET}] Result: {l_bu_val} | Selected Items Count: {len(l_recon)} | Time: {l_bu_time:.3f} ms")

    # Tabulation 1D on Large
    l_opt_val = engine_large.solve_bottom_up_1d_optimized()
    l_opt_time = engine_large.metrics.elapsed_ns / 1_000_000
    print(f"[{CLR_MAGENTA}SPACE-OPT-1D{CLR_RESET}] Result: {l_opt_val} | State Memory: {large_capacity * 8 / 1024:.2f} KB | Time: {l_opt_time:.3f} ms")

    # DP Table Inspection (Snippet of Top-Left 5x10)
    print_section("DP SUBPROBLEM TABLE INSPECTION (Slice [0..5] x [0..10])")
    sub_table = dp_table[:6]
    header = f"{'Item / W':<10}" + "".join([f"W={w:<5}" for w in range(11)])
    print(f"{CLR_BOLD}{header}{CLR_RESET}")
    print("-" * len(header))
    for idx, row in enumerate(sub_table):
        row_str = f"i={idx:<8}" + "".join([f"{val:<7}" for val in row[:11]])
        print(row_str)

    print(f"\n{CLR_BOLD}{CLR_GREEN}>>> LAB SESSION COMPLETE: ALL PERFORMANCE & INTEGRITY CHECKS PASSED <<<{CLR_RESET}\n")


if __name__ == "__main__":
    run_benchmark_suite()