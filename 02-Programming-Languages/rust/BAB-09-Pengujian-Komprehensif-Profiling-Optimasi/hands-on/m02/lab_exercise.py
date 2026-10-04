#!/usr/bin/env python3
"""
Lab Hands-on: Rust Chapter 09 - Pengujian Komprehensif, Profiling, & Optimasi
Simulasi Engine Pengujian Rust (cargo test), Benchmarking Statistik (criterion.rs),
dan Memory Allocation Profiler (dhat / valgrind global allocator simulator).
"""

import math
import random
import sys
import time
from dataclasses import dataclass
from typing import Callable, List, Tuple, Dict, Any

# ANSI Color Codes untuk output visual bergaya cargo
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"
GRAY = "\033[90m"

# ==============================================================================
# 1. SIMULASI GLOBAL ALLOCATOR & MEMORY PROFILING (Rust GlobalAlloc / DHAT)
# ==============================================================================

class MockGlobalAllocator:
    """
    Mensimulasikan trait std::alloc::GlobalAlloc di Rust.
    Melacak total bytes yang dialokasikan, deallokasi, dan peak usage
    untuk membandingkan zero-copy vs deep-cloning patterns.
    """
    def __init__(self):
        self.allocated_bytes: int = 0
        self.deallocated_bytes: int = 0
        self.current_usage: int = 0
        self.peak_usage: int = 0
        self.allocation_count: int = 0

    def alloc(self, size: int) -> int:
        self.allocated_bytes += size
        self.current_usage += size
        self.allocation_count += 1
        if self.current_usage > self.peak_usage:
            self.peak_usage = self.current_usage
        return size

    def dealloc(self, size: int):
        self.deallocated_bytes += size
        self.current_usage = max(0, self.current_usage - size)

    def reset(self):
        self.__init__()

allocator = MockGlobalAllocator()

# ==============================================================================
# 2. IMPLEMENTASI ALGORITMA: NAIVE VS OPTIMIZED
# ==============================================================================

def naive_process_records(records: List[str]) -> Dict[str, int]:
    """
    Simulasi Rust Anti-Pattern:
    - Menggunakan String::clone() berulang kali (alokasi heap boros).
    - Pencarian linear O(N) dan transformasi berulang.
    - Tanpa pre-alokasi kapasitas (reallokasi dinamis berkala).
    """
    result: Dict[str, int] = {}
    for record in records:
        # Simulasi alokasi heap saat duplikasi string via clone
        allocator.alloc(len(record) + 24)
        cloned = str(record)
        
        parts = cloned.split(":")
        allocator.alloc(len(parts) * 16)
        
        key = parts[0].strip().lower()
        allocator.alloc(len(key))
        val = int(parts[1].strip())
        
        # Linear scan / re-insertion
        if key not in result:
            result[key] = 0
        result[key] += val
        
        # Dealloc overhead simulasi scope exit
        allocator.dealloc(len(parts) * 16)
    return result

def optimized_process_records(records: List[str]) -> Dict[str, int]:
    """
    Simulasi Rust Idiomatic & Optimized Pattern:
    - Zero-copy view / string slice (&str) tanpa duplikasi heap.
    - Pre-allocation capacity (with_capacity).
    - In-place partitioning tanpa pembuatan objek sementara berlebihan.
    """
    # Alokasi awal tabel hash untuk menghindari rehashing
    allocator.alloc(len(records) * 8)
    result: Dict[str, int] = {}
    
    for record in records:
        # Menggunakan slicing / find langsung tanpa clone
        sep_idx = record.find(':')
        if sep_idx == -1:
            continue
        
        # Slice view (hanya pointer + length, nol alokasi heap baru)
        key = record[:sep_idx].strip().lower()
        val = int(record[sep_idx+1:].strip())
        
        result[key] = result.get(key, 0) + val
        
    return result

# ==============================================================================
# 3. UNIT TESTING & PROPERTY-BASED TESTING RUNNER (cargo test & quickcheck)
# ==============================================================================

@dataclass
class TestCase:
    name: str
    func: Callable[[], None]

test_registry: List[TestCase] = []

def test(name: str):
    """Decorator pengujian mirip attribute #[test] di Rust."""
    def decorator(fn: Callable[[], None]):
        test_registry.append(TestCase(name=name, func=fn))
        return fn
    return decorator

@test("test_exact_aggregation")
def test_exact_aggregation():
    data = ["core:10", "mem:20", "core:30", "io:5"]
    res = optimized_process_records(data)
    assert res["core"] == 40, f"Expected 40, got {res['core']}"
    assert res["mem"] == 20, f"Expected 20, got {res['mem']}"
    assert res["io"] == 5, f"Expected 5, got {res['io']}"

@test("test_empty_payload")
def test_empty_payload():
    res = optimized_process_records([])
    assert len(res) == 0, "Payload kosong harus menghasilkan mapping kosong"

@test("test_equivalence_property_fuzz")
def test_equivalence_property_fuzz():
    """
    Simulasi Property-based Testing (Rust quickcheck/proptest):
    Memastikan output fungsi naive dan optimized selalu deterministik & identik.
    """
    tags = ["gpu", "cpu", "ram", "ssd", "nic"]
    for run in range(50):
        mock_payload = [
            f"{random.choice(tags)}:{random.randint(1, 500)}"
            for _ in range(20)
        ]
        naive_out = naive_process_records(mock_payload)
        opt_out = optimized_process_records(mock_payload)
        assert naive_out == opt_out, f"Invariant failure pada iterasi {run}!"

def run_all_tests():
    print(f"\n{BOLD}{CYAN}=== Menjalankan Test Suite (Rust cargo test equivalent) ==={RESET}")
    passed = 0
    start_time = time.perf_counter()
    
    for t in test_registry:
        sys.stdout.write(f"test {t.name:<45} ... ")
        sys.stdout.flush()
        try:
            t.func()
            passed += 1
            print(f"{GREEN}ok{RESET}")
        except AssertionError as err:
            print(f"{RED}FAILED{RESET}")
            print(f"  {RED}Error: {err}{RESET}")
        except Exception as err:
            print(f"{RED}PANIC (unexpected exception){RESET}")
            print(f"  {RED}Detail: {err}{RESET}")
            
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"\nHasil: {GREEN}{passed} passed{RESET}; {RED}{len(test_registry) - passed} failed{RESET}; selesai dalam {elapsed:.2f}ms\n")

# ==============================================================================
# 4. STATISTICAL BENCHMARK ENGINE (Rust criterion.rs Simulation)
# ==============================================================================

@dataclass
class BenchReport:
    name: str
    mean_us: float
    std_dev_us: float
    throughput_items_per_sec: float
    peak_mem_kb: float
    total_alloc_count: int

def run_criterion_benchmark(name: str, payload: List[str], target_fn: Callable[[List[str]], Any], iterations: int = 150) -> BenchReport:
    """
    Melakukan sampling statistik performa:
    1. Warmup loop (instruksi cache & thread pre-warming)
    2. Sample collection
    3. Kalkulasi Mean, Standard Deviation, dan Outlier Filtering
    """
    print(f"{BOLD}[Benchmarking: {name}]{RESET}")
    print(f"  {GRAY}Warmup phase (50 iterasi)...{RESET}")
    for _ in range(50):
        target_fn(payload)

    timings_us: List[float] = []
    allocator.reset()
    
    print(f"  {GRAY}Collecting {iterations} samples...{RESET}")
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        target_fn(payload)
        t1 = time.perf_counter_ns()
        timings_us.append((t1 - t0) / 1_000.0)

    # Analisis Statistik
    mean = sum(timings_us) / len(timings_us)
    variance = sum((x - mean) ** 2 for x in timings_us) / len(timings_us)
    std_dev = math.sqrt(variance)
    throughput = (len(payload) / (mean / 1_000_000.0)) if mean > 0 else 0

    report = BenchReport(
        name=name,
        mean_us=mean,
        std_dev_us=std_dev,
        throughput_items_per_sec=throughput,
        peak_mem_kb=allocator.peak_usage / 1024.0,
        total_alloc_count=allocator.allocation_count
    )
    return report

# ==============================================================================
# 5. MAIN EXECUTION ENTRY POINT
# ==============================================================================

def main():
    print(f"{BOLD}{MAGENTA}================================================================{RESET}")
    print(f"{BOLD}{WHITE}  RUST COMPREHENSIVE TESTING, PROFILING & OPTIMIZATION LAB     {RESET}")
    print(f"{BOLD}{MAGENTA}================================================================{RESET}")

    # Langkah 1: Eksekusi Test Suite
    run_all_tests()

    # Langkah 2: Dataset Generation untuk Profiling
    print(f"{BOLD}{CYAN}=== Mempersiapkan Dataset Beban Tinggi ==={RESET}")
    base_keys = [f"worker-node-{i:03d}" for i in range(50)]
    dataset_size = 5_000
    dataset = [f"{random.choice(base_keys)}:{random.randint(10, 1000)}" for _ in range(dataset_size)]
    print(f"Total log records : {WHITE}{dataset_size:,} entri{RESET}")
    print(f"Karakteristik data: String parsing, heap allocation, in-place slicing\n")

    # Langkah 3: Profiling & Benchmark Komparatif
    report_naive = run_criterion_benchmark("Naive Pattern (Heap Clones & Dynamic Vectors)", dataset, naive_process_records)
    report_opt = run_criterion_benchmark("Optimized Pattern (Zero-Copy & Pre-alloc)", dataset, optimized_process_records)

    # Langkah 4: Format Laporan Evaluasi Kinerja
    print(f"\n{BOLD}{CYAN}=== Laporan Komparasi Metrik Criterion & Profiler ==={RESET}")
    header = f"{'Metric':<30} | {'Naive (Anti-pattern)':<24} | {'Optimized (&str Zero-Copy)':<26}"
    print(f"{BOLD}{header}{RESET}")
    print("-" * len(header))

    def print_row(label: str, v1: str, v2: str, highlight: bool = False):
        color = GREEN if highlight else WHITE
        print(f"{label:<30} | {v1:<24} | {color}{v2:<26}{RESET}")

    print_row("Waktu Eksekusi (Mean)", f"{report_naive.mean_us:.2f} µs", f"{report_opt.mean_us:.2f} µs", True)
    print_row("Standar Deviasi", f"± {report_naive.std_dev_us:.2f} µs", f"± {report_opt.std_dev_us:.2f} µs")
    print_row("Throughput", f"{report_naive.throughput_items_per_sec:,.0f} item/s", f"{report_opt.throughput_items_per_sec:,.0f} item/s", True)
    print_row("Peak Heap Memory", f"{report_naive.peak_mem_kb:.2f} KB", f"{report_opt.peak_mem_kb:.2f} KB", True)
    print_row("Alloc Counter", f"{report_naive.total_alloc_count:,} allocs", f"{report_opt.total_alloc_count:,} allocs", True)

    speedup = report_naive.mean_us / report_opt.mean_us if report_opt.mean_us > 0 else 0
    alloc_reduction = ((report_naive.total_alloc_count - report_opt.total_alloc_count) / report_naive.total_alloc_count) * 100

    print("-" * len(header))
    print(f"\n{BOLD}{YELLOW}Ringkasan Optimasi:{RESET}")
    print(f"  • {BOLD}Speedup:{RESET} {GREEN}{speedup:.2f}x lebih cepat{RESET} dibanding implementasi naive.")
    print(f"  • {BOLD}Reduksi Alokasi Heap:{RESET} Berkurang {GREEN}{alloc_reduction:.1f}%{RESET} (menekan tekanan garbage/free).")
    print(f"  • {BOLD}Kesimpulan Teknis:{RESET} Menghindari kloning heap string yang redundan")
    print(f"    dan menggunakan zero-copy parsing mereplikasi optimasi rustc/LLVM")
    print(f"    pada kode performa tinggi level sistem.\n")

if __name__ == "__main__":
    main()