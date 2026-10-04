#!/usr/bin/env python3
"""
Lab Hands-on: Testing Strategy, Profiling & Performance Tuning
Module: Deep Dive into Automated Performance Benchmarking, Memory Profiling & SLA Testing

Tujuan:
1. Mengimplementasikan Custom Profiling Context Manager (Wall-clock + Memory Tracing).
2. Membangun Automated Test Harness dengan Performance SLA Assertions.
3. Melakukan Benchmark Komparatif: O(N*M) Naive Transaction Audit vs O(N+M) Set-Lookup.
4. Mengidentifikasi Bottleneck dan Menganalisis Dampak Optimasi Alokasi Memori.
"""

import sys
import time
import tracemalloc
import functools
import hashlib
from dataclasses import dataclass
from typing import Callable, List, Tuple, Any, Dict

# --- ANSI Formatting Constants ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_CYAN   = "\033[96m"


@dataclass
class ProfileResult:
    """Menyimpan metrik profil eksekusi: durasi waktu dan alokasi memori."""
    name: str
    elapsed_ms: float
    current_mem_kb: float
    peak_mem_kb: float
    return_value: Any


class PerformanceProfiler:
    """
    Context Manager untuk profiling terintegrasi.
    Menggunakan time.perf_counter_ns untuk akurasi nanodetik dan
    tracemalloc untuk mengukur mutasi heap memory Python.
    """
    def __init__(self, operation_name: str):
        self.name = operation_name
        self.start_time: int = 0
        self.result: ProfileResult = None

    def __enter__(self):
        tracemalloc.start()
        tracemalloc.reset_peak()
        self.start_time = time.perf_counter_ns()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.perf_counter_ns()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        elapsed_ms = (end_time - self.start_time) / 1_000_000.0
        self.result = ProfileResult(
            name=self.name,
            elapsed_ms=elapsed_ms,
            current_mem_kb=current / 1024.0,
            peak_mem_kb=peak / 1024.0,
            return_value=None
        )


# ==============================================================================
# Domain Logic Under Test: Transaction Auditing Engine
# ==============================================================================

@dataclass(frozen=True)
class Transaction:
    tx_id: str
    sender: str
    amount: float
    signature: str


def generate_mock_data(tx_count: int, blacklist_count: int) -> Tuple[List[Transaction], List[str]]:
    """Membuat dataset sintetis transaksi finansial dan daftar entitas terlarang."""
    transactions = []
    for i in range(tx_count):
        tx_id = f"tx_{i:06d}"
        sender = f"user_{(i % 800):04d}"
        sig = hashlib.sha256(f"{tx_id}:{sender}".encode()).hexdigest()[:16]
        transactions.append(Transaction(tx_id, sender, float(i * 10), sig))

    blacklist = [f"user_{i:04d}" for i in range(200, 200 + blacklist_count)]
    return transactions, blacklist


def audit_transactions_naive(transactions: List[Transaction], blacklist: List[str]) -> List[Transaction]:
    """
    Algoritma Naive: Linear search pada Python List blacklist.
    Kompleksitas Waktu: O(N * M) di mana N = len(tx) dan M = len(blacklist).
    Alokasi: Membuat intermediate nested checking yang tidak efisien.
    """
    flagged = []
    for tx in transactions:
        # Bottleneck: 'tx.sender in blacklist' melakukan iterasi O(M) setiap transaksi
        if tx.sender in blacklist:
            flagged.append(tx)
    return flagged


def audit_transactions_optimized(transactions: List[Transaction], blacklist: List[str]) -> List[Transaction]:
    """
    Algoritma Teroptimasi: O(1) Hash-Set Lookup.
    Kompleksitas Waktu: O(N + M) - O(M) untuk build set, O(N * 1) untuk audit.
    Menggunakan generator comprehension untuk meminimalkan re-alokasi memori.
    """
    blacklist_set = set(blacklist)  # O(M) amortized
    return [tx for tx in transactions if tx.sender in blacklist_set]  # O(N) amortized


# ==============================================================================
# Micro-Testing & SLA Framework
# ==============================================================================

class PerformanceTestSuite:
    """Custom micro-testing harness dengan validasi fungsional dan batasan performa (SLA)."""

    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0

    def assert_equal(self, actual: Any, expected: Any, msg: str):
        if actual != expected:
            raise AssertionError(f"{msg} | Expected: {expected}, Got: {actual}")

    def assert_sla(self, elapsed_ms: float, max_allowed_ms: float, msg: str):
        if elapsed_ms > max_allowed_ms:
            raise AssertionError(f"SLA BREACH: {msg} | Elapsed: {elapsed_ms:.2f}ms > Limit: {max_allowed_ms:.2f}ms")

    def run_test(self, test_name: str, test_func: Callable):
        self.tests_run += 1
        print(f"{CLR_BLUE}[TEST]{CLR_RESET} Running: {test_name}...", end=" ")
        try:
            test_func(self)
            print(f"{CLR_GREEN}PASS{CLR_RESET}")
            self.tests_passed += 1
        except AssertionError as e:
            print(f"{CLR_RED}FAIL{CLR_RESET}")
            print(f"  └─ {CLR_RED}Assertion Error: {e}{CLR_RESET}")
            self.tests_failed += 1
        except Exception as e:
            print(f"{CLR_RED}ERROR{CLR_RESET}")
            print(f"  └─ {CLR_RED}Unexpected Exception: {e}{CLR_RESET}")
            self.tests_failed += 1


# --- Test Cases ---

def test_correctness_parity(suite: PerformanceTestSuite):
    """Memastikan kedua implementasi menghasilkan audit set yang identik."""
    txs, bl = generate_mock_data(tx_count=500, blacklist_count=50)
    naive_res = audit_transactions_naive(txs, bl)
    opt_res = audit_transactions_optimized(txs, bl)

    suite.assert_equal(len(naive_res), len(opt_res), "Hasil audit harus konsisten secara kuantitas")
    suite.assert_equal([t.tx_id for t in naive_res], [t.tx_id for t in opt_res], "ID transaksi yang ditandai harus cocok")


def test_optimized_performance_sla(suite: PerformanceTestSuite):
    """
    SLA Test: Algoritma teroptimasi harus memproses 20.000 transaksi
    dan 1.000 entri blacklist dalam waktu di bawah 25 milidetik.
    """
    txs, bl = generate_mock_data(tx_count=20000, blacklist_count=1000)

    with PerformanceProfiler("SLA_Audit_Optimized") as profiler:
        res = audit_transactions_optimized(txs, bl)

    elapsed = profiler.result.elapsed_ms
    suite.assert_sla(elapsed, max_allowed_ms=25.0, msg="Optimized Audit 20k TX")
    suite.assert_equal(len(res) > 0, True, "Harus menemukan transaksi yang melanggar")


# ==============================================================================
# Benchmarking & Profiling Deep-Dive
# ==============================================================================

def execute_profiling_benchmark():
    """Menjalankan comparative profiling komprehensif antara Naive dan Optimized."""
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== MENJALANKAN BENCHMARK PROFILING (CPU & HEAP MEMORY) ==={CLR_RESET}")
    tx_count = 15000
    bl_count = 1500
    print(f"Beban Data: {CLR_YELLOW}{tx_count:,}{CLR_RESET} Transaksi | {CLR_YELLOW}{bl_count:,}{CLR_RESET} Blacklist Entries\n")

    txs, bl = generate_mock_data(tx_count, bl_count)

    # 1. Profiling Naive
    with PerformanceProfiler("Algoritma Naive (List O(N*M))") as p_naive:
        res_naive = audit_transactions_naive(txs, bl)

    # 2. Profiling Optimized
    with PerformanceProfiler("Algoritma Optimized (Set O(N+M))") as p_opt:
        res_opt = audit_transactions_optimized(txs, bl)

    # Output Metrik Terstruktur
    results = [p_naive.result, p_opt.result]

    header = f"{'Metrik':<30} | {'Naive List O(N*M)':<22} | {'Optimized Set O(N+M)':<22}"
    print(CLR_BOLD + header + CLR_RESET)
    print("-" * len(header))

    row_time = f"{'Durasi Eksekusi':<30} | {results[0].elapsed_ms:>18.2f} ms | {results[1].elapsed_ms:>18.2f} ms"
    row_peak_mem = f"{'Peak Memory Allocated':<30} | {results[0].peak_mem_kb:>18.2f} KB | {results[1].peak_mem_kb:>18.2f} KB"
    row_count = f"{'Transaksi Ditandai':<30} | {len(res_naive):>21} | {len(res_opt):>21}"

    print(row_time)
    print(row_peak_mem)
    print(row_count)
    print("-" * len(header))

    speedup = results[0].elapsed_ms / max(results[1].elapsed_ms, 0.0001)
    print(f"{CLR_BOLD}Analisis Efisiensi:{CLR_RESET}")
    print(f"• Peningkatan Kecepatan (Speedup): {CLR_GREEN}{speedup:.2f}x LEBIH CEPAT{CLR_RESET}")
    print(f"• Pengurangan Latensi: {CLR_GREEN}{results[0].elapsed_ms - results[1].elapsed_ms:.2f} ms saved{CLR_RESET}\n")


# ==============================================================================
# Main Orchestrator
# ==============================================================================

def main():
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  SISTEM PROFILING, PENGUJIAN SLA & PERFORMANCE TUNING PYTHON 3       {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")

    # Tahap 1: Eksekusi Unit & Performance SLA Tests
    suite = PerformanceTestSuite()
    suite.run_test("Verifikasi Kesetaraan Logika (Parity Test)", test_correctness_parity)
    suite.run_test("Verifikasi Ambang Batas Performa (SLA Test)", test_optimized_performance_sla)

    print(f"\nHasil Pengujian: {CLR_GREEN}{suite.tests_passed} Passed{CLR_RESET}, "
          f"{CLR_RED if suite.tests_failed else CLR_RESET}{suite.tests_failed} Failed{CLR_RESET} "
          f"dari {suite.tests_run} Pengujian.")

    if suite.tests_failed > 0:
        print(f"{CLR_RED}Pengujian gagal! Menghentikan eksekusi benchmark.{CLR_RESET}")
        sys.exit(1)

    # Tahap 2: Profiling Mendalam
    execute_profiling_benchmark()

    print(f"{CLR_GREEN}Lab Selesai: Seluruh SLA terpenuhi dan metrik profil tervalidasi.{CLR_RESET}")


if __name__ == "__main__":
    main()