#!/usr/bin/env python3
"""
Lab Hands-on: Two Pointers & Sliding Window Mechanics (Core Foundations)
Author: Lead System Programmer
Description:
    Simulasi pemrosesan stream data berkinerja tinggi menggunakan teknik:
    1. Sliding Window Dinamis (Longest Subarray with Budget Constraint)
    2. Two-Pointers Symmetric Search (Optimal Packet Pairing on Sorted Stream)
    3. Benchmarking Empiris: Brute-Force O(N^2) vs Sliding Window O(N)
"""

import sys
import time
import random
from typing import List, Tuple, Optional


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    GRAY = "\033[90m"


def header(title: str) -> None:
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}{'=' * 75}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN} [LAB] {title.upper()}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN}{'=' * 75}{ANSI.RESET}")


# ============================================================================
# 1. SLIDING WINDOW MECHANICS (Variable Size Window)
# ============================================================================
def sliding_window_max_throughput(packets: List[int], budget: int) -> Tuple[int, int, int, int]:
    """
    Mencari sub-array terpanjang dari paket jaringan yang total ukurannya (bandwidth)
    tidak melebihi kapasitas 'budget' (K).

    Kompleksitas Waktu : O(N) amortized (setiap pointer bergerak maksimal N langkah).
    Kompleksitas Ruang : O(1) in-place pointers.

    Returns:
        (max_length, start_idx, end_idx, ops_count)
    """
    left = 0
    current_sum = 0
    max_len = 0
    best_range = (-1, -1)
    ops_count = 0

    for right in range(len(packets)):
        current_sum += packets[right]
        ops_count += 1

        # Kontraksi window jika invariant 'current_sum <= budget' dilanggar
        while current_sum > budget and left <= right:
            current_sum -= packets[left]
            left += 1
            ops_count += 1

        # Evaluasi panjang window yang valid
        window_len = right - left + 1
        if window_len > max_len:
            max_len = window_len
            best_range = (left, right)

    return max_len, best_range[0], best_range[1], ops_count


def naive_max_throughput(packets: List[int], budget: int) -> Tuple[int, int, int, int]:
    """
    Baseline Brute-Force O(N^2) untuk perbandingan analitis.
    """
    n = len(packets)
    max_len = 0
    best_range = (-1, -1)
    ops_count = 0

    for i in range(n):
        current_sum = 0
        for j in range(i, n):
            current_sum += packets[j]
            ops_count += 1
            if current_sum <= budget:
                if (j - i + 1) > max_len:
                    max_len = j - i + 1
                    best_range = (i, j)
            else:
                break  # Pruning sederhana saat over budget

    return max_len, best_range[0], best_range[1], ops_count


# ============================================================================
# 2. TWO-POINTERS MECHANICS (Converging / Opposing Ends)
# ============================================================================
def two_pointer_latency_pairing(latencies: List[int], target_latency: int) -> Tuple[Optional[Tuple[int, int]], int]:
    """
    Diberikan array latency server yang terurut (sorted), temukan pasangan dua server
    yang jumlah latencynya paling mendekati 'target_latency' tanpa melebihinya.

    Mekanisme: Opposing Ends Pointers (Left menaikkan jumlah, Right menurunkan jumlah).
    Kompleksitas Waktu : O(N)
    Kompleksitas Ruang : O(1)
    """
    left = 0
    right = len(latencies) - 1
    best_pair = None
    closest_sum = -1
    ops_count = 0

    while left < right:
        ops_count += 1
        curr_sum = latencies[left] + latencies[right]

        if curr_sum <= target_latency:
            if curr_sum > closest_sum:
                closest_sum = curr_sum
                best_pair = (latencies[left], latencies[right])
            # Butuh nilai lebih besar untuk mendekati target -> majukan left
            left += 1
        else:
            # Nilai melampaui target -> mundurkan right
            right -= 1

    return best_pair, ops_count


# ============================================================================
# 3. VERIFICATION & BENCHMARK HARNESS
# ============================================================================
def run_sliding_window_demo():
    header("Demonstrasi 1: Dynamic Sliding Window (Bandwidth Throttling)")
    stream = [12, 45, 23, 67, 10, 15, 8, 30, 42, 18, 5, 2]
    budget = 80

    print(f"{ANSI.GRAY}Data Stream (Packets KB) : {stream}{ANSI.RESET}")
    print(f"{ANSI.YELLOW}Max Budget Limit        : {budget} KB{ANSI.RESET}\n")

    max_len, s, e, ops = sliding_window_max_throughput(stream, budget)
    selected_slice = stream[s:e + 1] if s != -1 else []
    total_consumed = sum(selected_slice)

    print(f"{ANSI.GREEN}Hasil Optimasi Sliding Window:{ANSI.RESET}")
    print(f"  -> Window Terpanjang : {ANSI.BOLD}{max_len} paket{ANSI.RESET} (Index [{s}..{e}])")
    print(f"  -> Paket Terpilih    : {selected_slice}")
    print(f"  -> Total Bandwidth   : {total_consumed}/{budget} KB")
    print(f"  -> Operasi Pointer   : {ops} langkah (O(N) scale)")


def run_two_pointer_demo():
    header("Demonstrasi 2: Two-Pointers Converging Search (Pair Matching)")
    # Data latensi dalam milidetik (sudah terurut)
    server_latencies = sorted([14, 55, 28, 89, 41, 105, 33, 17, 72, 60, 9, 94])
    target = 100

    print(f"{ANSI.GRAY}Sorted Latency Nodes (ms): {server_latencies}{ANSI.RESET}")
    print(f"{ANSI.YELLOW}Target Max Latency Sum   : {target} ms{ANSI.RESET}\n")

    pair, ops = two_pointer_latency_pairing(server_latencies, target)

    if pair:
        pair_sum = pair[0] + pair[1]
        print(f"{ANSI.GREEN}Pasangan Node Optimal Ditemukan:{ANSI.RESET}")
        print(f"  -> Nodes Selected   : Node-A = {pair[0]} ms, Node-B = {pair[1]} ms")
        print(f"  -> Latensi Total    : {pair_sum} ms (Delta ke Target: {target - pair_sum} ms)")
        print(f"  -> Langkah Eksekusi : {ops} perbandingan (Maksimal N langkah)")
    else:
        print(f"{ANSI.RED}Tidak ada pasangan valid di bawah target.{ANSI.RESET}")


def run_benchmark():
    header("Demonstrasi 3: Benchmark Empiris (Brute Force O(N^2) vs Sliding Window O(N))")
    dataset_sizes = [500, 1500, 3000]
    
    print(f"{'Input Size (N)':<15} | {'Algorithm':<18} | {'Latency (ms)':<15} | {'Operation Steps':<15}")
    print(f"{'-' * 70}")

    for n in dataset_sizes:
        # Generate random traffic packet sizes
        random.seed(42 + n)
        data = [random.randint(1, 100) for _ in range(n)]
        budget = n * 15

        # Benchmark Naive O(N^2)
        t0 = time.perf_counter()
        naive_len, _, _, naive_ops = naive_max_throughput(data, budget)
        t_naive = (time.perf_counter() - t0) * 1000.0

        # Benchmark Sliding Window O(N)
        t0 = time.perf_counter()
        opt_len, _, _, opt_ops = sliding_window_max_throughput(data, budget)
        t_opt = (time.perf_counter() - t0) * 1000.0

        # Verifikasi konsistensi hasil
        assert naive_len == opt_len, f"Inkonsistensi: {naive_len} != {opt_len}"

        print(f"{n:<15} | {ANSI.RED}Naive O(N^2){ANSI.RESET:<27} | {t_naive:<15.3f} | {naive_ops:<15}")
        print(f"{'':<15} | {ANSI.GREEN}Sliding Win O(N){ANSI.RESET:<27} | {t_opt:<15.3f} | {opt_ops:<15}")
        print(f"{ANSI.GRAY}{'-' * 70}{ANSI.RESET}")


def main():
    print(f"{ANSI.BOLD}{ANSI.MAGENTA}Inisialisasi Sistem Lab: Two Pointers & Sliding Window Core Engine...{ANSI.RESET}")
    run_sliding_window_demo()
    run_two_pointer_demo()
    run_benchmark()
    print(f"\n{ANSI.BOLD}{ANSI.GREEN}[✓] Seluruh modul eksekusi selesai dengan validasi algoritma sempurna.{ANSI.RESET}\n")


if __name__ == "__main__":
    main()