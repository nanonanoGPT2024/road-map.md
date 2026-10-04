#!/usr/bin/env python3
"""
Lab Exercise: Core Foundations - Binary Search & Divide and Conquer (Deep Dive)
Author: Lead System Programmer

Demonstrates:
1. Binary Search over Monotonic Predicate Space (Capacity Optimization / Minimax).
2. Divide & Conquer Inversion Counter (Modified Merge Sort - O(N log N)).
3. Benchmarking and validation suite comparing optimal implementations vs. naive baselines.
"""

import sys
import time
import random
from typing import List, Tuple

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"


# ============================================================================
# MODULE 1: BINARY SEARCH ON MONOTONIC SPACE
# Problem: Distributed Workload Ingestion (Minimizing Maximum Partition Load)
# ============================================================================

def is_valid_throughput(tasks: List[int], max_workers: int, capacity_limit: int) -> bool:
    """
    Predikat Monoton: Menentukan apakah semua task dapat didistribusikan ke 
    sejumlah `max_workers` kontainer tanpa ada kontainer yang bebannya melebihi `capacity_limit`.
    Kompleksitas: O(N) waktu, O(1) memori tambahan.
    """
    workers_used = 1
    current_worker_load = 0

    for weight in tasks:
        if current_worker_load + weight > capacity_limit:
            workers_used += 1
            current_worker_load = weight
            if workers_used > max_workers:
                return False
        else:
            current_worker_load += weight

    return True


def optimize_cluster_capacity(tasks: List[int], max_workers: int, verbose: bool = False) -> int:
    """
    Mencari kapasitas minimum kontainer (Search Space: [max(tasks), sum(tasks)])
    menggunakan Binary Search on Answer Space (Lower-Bound Binary Search).
    Kompleksitas: O(N * log(sum - max)).
    """
    low = max(tasks)
    high = sum(tasks)
    optimal_capacity = high
    step = 1

    if verbose:
        print(f"{CLR_CYAN}[BS-TRACE] Target Workers: {max_workers} | Search Range: [{low}, {high}]{CLR_RESET}")

    while low <= high:
        mid = low + ((high - low) >> 1)  # Bitwise shift untuk proteksi overflow / pembagian integer
        feasible = is_valid_throughput(tasks, max_workers, mid)

        if verbose:
            status = f"{CLR_GREEN}VALID{CLR_RESET}" if feasible else f"{CLR_RED}INVALID{CLR_RESET}"
            print(f"  Step {step:02d}: Mid={mid:<6} Range=[{low:<6}, {high:<6}] => Result: {status}")

        if feasible:
            optimal_capacity = mid
            high = mid - 1  # Coba cari kapasitas yang lebih efisien (lebih rendah)
        else:
            low = mid + 1   # Kapasitas terlalu kecil, geser batas bawah

        step += 1

    return optimal_capacity


# ============================================================================
# MODULE 2: DIVIDE & CONQUER (COUNT INVERSIONS / METRIC OF DISARRAY)
# Problem: Mengukur anomali urutan aliran data dengan Merge Sort termodifikasi.
# ============================================================================

def _merge_and_count(arr: List[int], temp: List[int], left: int, mid: int, right: int) -> int:
    """
    Tahap Conquer: Menggabungkan dua sub-array terurut dan menghitung split inversions.
    Jika arr[i] > arr[j], maka seluruh elemen dari i sampai mid membentuk inversion.
    """
    i = left     # Penunjuk sub-array kiri
    j = mid + 1  # Penunjuk sub-array kanan
    k = left     # Penunjuk target array sementara
    inv_count = 0

    while i <= mid and j <= right:
        if arr[i] <= arr[j]:
            temp[k] = arr[i]
            i += 1
        else:
            temp[k] = arr[j]
            # Cross-inversion: arr[i] > arr[j] implies all arr[i...mid] > arr[j]
            inv_count += (mid - i + 1)
            j += 1
        k += 1

    # Flush sisa elemen kiri
    while i <= mid:
        temp[k] = arr[i]
        i += 1
        k += 1

    # Flush sisa elemen kanan
    while j <= right:
        temp[k] = arr[j]
        j += 1
        k += 1

    # Salin kembali ke array asli
    for idx in range(left, right + 1):
        arr[idx] = temp[idx]

    return inv_count


def _sort_and_count(arr: List[int], temp: List[int], left: int, right: int) -> int:
    """
    Tahap Divide: Membelah array secara rekursif hingga basis T(1) = 0.
    Kompleksitas Total: T(N) = 2T(N/2) + O(N) => O(N log N) Master Theorem Case 2.
    """
    inv_count = 0
    if left < right:
        mid = left + ((right - left) >> 1)

        inv_count += _sort_and_count(arr, temp, left, mid)
        inv_count += _sort_and_count(arr, temp, mid + 1, right)
        inv_count += _merge_and_count(arr, temp, left, mid, right)

    return inv_count


def count_inversions_dc(data: List[int]) -> int:
    """Entry point Divide and Conquer Inversion Counting."""
    arr_copy = list(data)
    temp = [0] * len(arr_copy)
    return _sort_and_count(arr_copy, temp, 0, len(arr_copy) - 1)


def count_inversions_naive(data: List[int]) -> int:
    """
    Metode brute force O(N^2) sebagai oracle verifikasi kebenaran (Ground Truth).
    """
    count = 0
    n = len(data)
    for i in range(n):
        for j in range(i + 1, n):
            if data[i] > data[j]:
                count += 1
    return count


# ============================================================================
# BENCHMARK & TEST HARNESS
# ============================================================================

def run_binary_search_lab():
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}=== [EXPERIMENT 1: BINARY SEARCH ON ANSWER SPACE] ==={CLR_RESET}")
    tasks = [10, 20, 5, 25, 15, 30, 12, 18, 40, 8]
    workers = 4

    print(f"Tasks: {tasks}")
    print(f"Available Workers: {workers}")
    print("Initiating Bounded Binary Search...\n")

    optimal_cap = optimize_cluster_capacity(tasks, workers, verbose=True)
    print(f"\n{CLR_BOLD}Optimal Bottleneck Capacity:{CLR_RESET} {CLR_GREEN}{optimal_cap}{CLR_RESET} units/worker.")


def run_divide_and_conquer_lab():
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}=== [EXPERIMENT 2: DIVIDE & CONQUER INVERSION BENCHMARK] ==={CLR_RESET}")
    sizes = [500, 1500, 3000]

    header = f"{'Array Size':<12} | {'DC Inversions':<15} | {'Naive (ms)':<12} | {'D&C (ms)':<12} | {'Speedup':<10}"
    print(CLR_BOLD + header + CLR_RESET)
    print("-" * len(header))

    for size in sizes:
        # Generate random permutation dataset
        dataset = [random.randint(1, 100000) for _ in range(size)]

        # Benchmark Naive O(N^2)
        start_naive = time.perf_counter()
        naive_inv = count_inversions_naive(dataset)
        time_naive = (time.perf_counter() - start_naive) * 1000

        # Benchmark Divide and Conquer O(N log N)
        start_dc = time.perf_counter()
        dc_inv = count_inversions_dc(dataset)
        time_dc = (time.perf_counter() - start_dc) * 1000

        # Assert correctness between approaches
        assert naive_inv == dc_inv, f"Sanity check failed: Naive={naive_inv} != DC={dc_inv}"

        speedup = f"{time_naive / time_dc:.2f}x" if time_dc > 0 else "inf"
        print(f"{size:<12} | {dc_inv:<15} | {time_naive:<12.2f} | {time_dc:<12.3f} | {CLR_GREEN}{speedup:<10}{CLR_RESET}")


def main():
    print(f"{CLR_BOLD}{CLR_YELLOW}Initializing Module 02 Deep Dive: Binary Search & Divide and Conquer{CLR_RESET}")
    print("System Profiler & Algorithmic Correctness Engine Active.\n")

    run_binary_search_lab()
    run_divide_and_conquer_lab()

    print(f"\n{CLR_BOLD}{CLR_GREEN}[STATUS] All algorithmic invariants passed successfully.{CLR_RESET}\n")


if __name__ == "__main__":
    main()