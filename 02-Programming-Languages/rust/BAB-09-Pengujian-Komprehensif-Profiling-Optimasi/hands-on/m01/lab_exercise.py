#!/usr/bin/env python3
"""
Simulasi Teknis Interaktif: Rust Testing, Benchmarking, Profiling & Optimasi
Bab 09: Pengujian Komprehensif, Profiling, dan Optimasi (Rust Engineering Lab)
"""

import sys
import time
import math
import random
from typing import Callable, List, Dict, Any, Tuple

# ANSI Color Codes untuk Terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_DARK = "\033[40m"

def print_header(title: str):
    width = 72
    print(f"\n{Color.CYAN}{'=' * width}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}  RUST QA & OPTIMIZATION LAB :: {title.upper()}{Color.RESET}")
    print(f"{Color.CYAN}{'=' * width}{Color.RESET}")

def print_success(msg: str):
    print(f"{Color.GREEN}[PASS / OK]{Color.RESET} {msg}")

def print_fail(msg: str):
    print(f"{Color.RED}[FAIL / ERR]{Color.RESET} {msg}")

def print_info(msg: str):
    print(f"{Color.BLUE}[INFO]{Color.RESET} {msg}")

def print_metric(label: str, val: str):
    print(f"  {Color.YELLOW}•{Color.RESET} {label.ljust(28)}: {Color.BOLD}{Color.MAGENTA}{val}{Color.RESET}")


# ==============================================================================
# 1. SIMULASI UNIT TESTING & PROPERTY-BASED TESTING (proptest / quickcheck)
# ==============================================================================

def rust_safe_divide(numerator: int, denominator: int) -> Tuple[bool, int]:
    """Simulasi fungsi Rust: fn safe_divide(n: i64, d: i64) -> Result<i64, MathError>"""
    if denominator == 0:
        return False, 0
    # Rust integer division truncates toward zero (berbeda dengan Python // yang floor)
    return True, int(numerator / denominator)

def run_unit_and_property_tests():
    print_header("Modul 1: Unit Test & Property-Based Test (proptest)")
    print_info("Menjalankan test suite unit standar...")
    
    # 1. Deterministic Unit Tests
    unit_cases = [
        (10, 2, True, 5),
        (25, 5, True, 5),
        (7, 0, False, 0),
        (-15, 3, True, -5),
    ]
    
    for n, d, expected_ok, expected_val in unit_cases:
        ok, res = rust_safe_divide(n, d)
        if ok == expected_ok and (not ok or res == expected_val):
            print_success(f"test_divide({n}, {d}) -> Result({ok}, val={res})")
        else:
            print_fail(f"test_divide({n}, {d}) gagal! Ekspektasi: ({expected_ok}, {expected_val})")

    # 2. Property-Based Testing (Random Invariant Fuzzing)
    print_info("\nMenjalankan Property-Based Fuzzing (100 generasi acak)...")
    print_info("Invarian 1: Jika d != 0, maka abs(res * d) <= abs(n)")
    print_info("Invarian 2: Jika d == 0, fungsi tidak boleh panic (Result::Err)")

    violations = 0
    test_runs = 100
    for _ in range(test_runs):
        n = random.randint(-10000, 10000)
        d = random.randint(-100, 100)
        ok, res = rust_safe_divide(n, d)

        if d == 0:
            if ok:
                violations += 1
                print_fail(f"Fuzz invariant breached on d=0: return ok=True")
        else:
            if not ok:
                violations += 1
                print_fail(f"Fuzz invariant breached on valid d={d}")
            elif abs(res * d) > abs(n):
                violations += 1
                print_fail(f"Invarian truncating division breached: {n}/{d} = {res}")

    if violations == 0:
        print_success(f"Property-Based Testing lolos 100% ({test_runs}/100 invariants valid).")
    else:
        print_fail(f"Ditemukan {violations} pelanggaran properti!")


# ==============================================================================
# 2. SIMULASI CRITERION.RS MICRO-BENCHMARKING
# ==============================================================================

def heavy_computation_naive(n: int) -> int:
    """Implementasi Naive (O(n)) simulasi kalkulasi tanpa SIMD"""
    acc = 0
    for i in range(n):
        acc = (acc + (i * 37) ^ 0x5A) % 1000000007
    return acc

def heavy_computation_vectorized(n: int) -> int:
    """Simulasi kalkulasi vektorisasi / unrolled loop compiler"""
    acc = 0
    step = 4
    for i in range(0, n - (n % step), step):
        t0 = (i * 37) ^ 0x5A
        t1 = ((i + 1) * 37) ^ 0x5A
        t2 = ((i + 2) * 37) ^ 0x5A
        t3 = ((i + 3) * 37) ^ 0x5A
        acc = (acc + t0 + t1 + t2 + t3) % 1000000007
    for i in range(n - (n % step), n):
        acc = (acc + (i * 37) ^ 0x5A) % 1000000007
    return acc

def run_criterion_benchmark():
    print_header("Modul 2: Micro-Benchmarking Engine (Simulasi Criterion.rs)")
    print_info("Menghitung estimasi throughput, standard deviation, dan outlier...")

    benchmarks: Dict[str, Callable[[int], int]] = {
        "naive_scalar_loop": heavy_computation_naive,
        "vectorized_unrolled": heavy_computation_vectorized,
    }

    n_samples = 40
    input_size = 25000

    results: Dict[str, List[float]] = {}

    for name, fn in benchmarks.items():
        print(f"\n{Color.BOLD}Benchmarking: [{name}]{Color.RESET}")
        # Warmup loop
        for _ in range(5):
            fn(input_size)

        timings = []
        for _ in range(n_samples):
            t_start = time.perf_counter()
            fn(input_size)
            t_end = time.perf_counter()
            timings.append((t_end - t_start) * 1_000_000) # Microseconds

        timings.sort()
        mean = sum(timings) / len(timings)
        variance = sum((x - mean) ** 2 for x in timings) / len(timings)
        std_dev = math.sqrt(variance)
        median = timings[len(timings) // 2]
        p95 = timings[int(len(timings) * 0.95)]

        results[name] = timings

        print_metric("Samples Iteration", str(n_samples))
        print_metric("Mean Latency", f"{mean:.2f} µs")
        print_metric("Median Latency", f"{median:.2f} µs")
        print_metric("Std Deviation", f"{std_dev:.2f} µs ({std_dev/mean*100:.1f}%)")
        print_metric("Percentile 95 (P95)", f"{p95:.2f} µs")

    # Hitung rasio peningkatan
    mean_naive = sum(results["naive_scalar_loop"]) / n_samples
    mean_vec = sum(results["vectorized_unrolled"]) / n_samples
    speedup = mean_naive / mean_vec if mean_vec > 0 else 1.0

    print(f"\n{Color.GREEN}{Color.BOLD}>>> Criterion Regression Assessment:{Color.RESET}")
    print(f"    Peningkatan performa (Speedup): {Color.BOLD}{speedup:.2f}x{Color.RESET}")
    if speedup > 1.0:
        print_success("Optimasi menunjukkan peningkatan signifikan tanpa regresi throughput.")
    else:
        print_fail("Terdeteksi regresi performa!")


# ==============================================================================
# 3. SIMULASI PROFILING & CALLSTACK SAMPLING (Flamegraph / perf)
# ==============================================================================

def run_profiler_simulation():
    print_header("Modul 3: Callstack Profiling & Flamegraph Tree")
    print_info("Simulasi sampling interrupt (1000 Hz) menggunakan kernel perf/dtrace...")

    stack_samples = [
        ("main -> server::listen -> accept_conn", 420),
        ("main -> worker::pool -> json::parse -> serde_json::from_str", 1350),
        ("main -> worker::pool -> json::parse -> alloc::raw_vec::reserve", 980),
        ("main -> worker::pool -> crypto::sha256 -> simd::transform", 2100),
        ("main -> worker::pool -> crypto::sha256 -> alloc::heap_box", 350),
        ("main -> logger::flush -> io::sys::write", 300),
    ]

    total_ticks = sum(samples for _, samples in stack_samples)

    print(f"\n{Color.BOLD}{'CALL STACK TRACE':<50} {'TICKS':<8} {'PERCENTAGE'}{Color.RESET}")
    print("-" * 72)
    
    for stack, count in sorted(stack_samples, key=lambda x: x[1], reverse=True):
        pct = (count / total_ticks) * 100
        bar_len = int(pct / 2.5)
        bar_color = Color.RED if pct > 25 else (Color.YELLOW if pct > 15 else Color.GREEN)
        bar = f"{bar_color}{'█' * bar_len}{Color.RESET}"
        print(f"{stack:<50} {count:<8} {pct:5.1f}% {bar}")

    print("\n" + Color.BOLD + "Analisis Bottleneck Profiler:" + Color.RESET)
    print_info("1. Fungsi 'crypto::sha256 -> simd::transform' memakan 38.2% cpu ticks (Compute-Bound).")
    print_info("2. Fungsi 'serde_json::from_str' & heap allocation memakan 42.4% (Memory/Alloc Overhead).")
    print_info("Rekomendasi Rust: Gunakan arena allocator (bumpalo) dan zero-copy parsing.")


# ==============================================================================
# 4. SIMULASI MATRIKS RUST COMPILER PROFILES (Cargo.toml release flags)
# ==============================================================================

def run_compiler_optimization_matrix():
    print_header("Modul 4: Compiler Profile Matrix (Release Flags)")
    print_info("Membandingkan dampak konfigurasi Cargo profile terhadap binary size & runtime:")

    profiles = [
        {
            "name": "dev (debug default)",
            "opt_level": "0",
            "lto": "off",
            "codegen_units": 16,
            "bin_size_mb": 42.5,
            "exec_time_ms": 145.0,
            "build_time_s": 3.2
        },
        {
            "name": "release (default)",
            "opt_level": "3",
            "lto": "off",
            "codegen_units": 16,
            "bin_size_mb": 12.8,
            "exec_time_ms": 28.4,
            "build_time_s": 14.8
        },
        {
            "name": "release (aggressive LTO)",
            "opt_level": "3",
            "lto": "fat (full)",
            "codegen_units": 1,
            "bin_size_mb": 7.4,
            "exec_time_ms": 19.1,
            "build_time_s": 48.5
        },
        {
            "name": "release (size-opt -Oz)",
            "opt_level": "\"z\"",
            "lto": "fat (full)",
            "codegen_units": 1,
            "bin_size_mb": 3.1,
            "exec_time_ms": 34.0,
            "build_time_s": 36.2
        }
    ]

    header_fmt = f"{Color.BOLD}{'PROFILE':<26} {'OPT':<5} {'LTO':<12} {'CGU':<5} {'SIZE':<9} {'EXEC TIME':<12} {'BUILD'}{Color.RESET}"
    print(f"\n{header_fmt}")
    print("-" * 78)

    for p in profiles:
        size_str = f"{p['bin_size_mb']} MB"
        exec_str = f"{p['exec_time_ms']} ms"
        build_str = f"{p['build_time_s']} s"
        print(f"{p['name']:<26} {p['opt_level']:<5} {p['lto']:<12} {p['codegen_units']:<5} {size_str:<9} {exec_str:<12} {build_str}")

    print(f"\n{Color.GREEN}[Insight LTO]{Color.RESET} Full LTO + codegen-units=1 memangkas ukuran binary sebesar 42% dan latency 32%,")
    print("              dengan kompromi waktu kompilasi meningkat 3.2x.")


# ==============================================================================
# MAIN INTERACTIVE MENU
# ==============================================================================

def display_menu():
    print(f"\n{Color.BOLD}{Color.WHITE}=== Rust QA, Profiling & Optimization Simulator ==={Color.RESET}")
    print(f"{Color.CYAN}1.{Color.RESET} Jalankan Unit Tests & Property-Based Testing (proptest)")
    print(f"{Color.CYAN}2.{Color.RESET} Jalankan Micro-Benchmarking Engine (Criterion.rs)")
    print(f"{Color.CYAN}3.{Color.RESET} Jalankan Callstack Profiler & Bottleneck Analysis (perf/flamegraph)")
    print(f"{Color.CYAN}4.{Color.RESET} Tampilkan Rust Compiler Profile Matrix (LTO, opt-level, size)")
    print(f"{Color.CYAN}5.{Color.RESET} Jalankan Seluruh Pipeline Pengujian & Optimasi")
    print(f"{Color.CYAN}0.{Color.RESET} Keluar")

def main():
    # Jika dipanggil non-interaktif atau dengan argument
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a"):
        run_unit_and_property_tests()
        run_criterion_benchmark()
        run_profiler_simulation()
        run_compiler_optimization_matrix()
        print(f"\n{Color.GREEN}{Color.BOLD}Seluruh simulasi selesai dijalankan dengan sukses.{Color.RESET}\n")
        return

    while True:
        display_menu()
        try:
            choice = input(f"\n{Color.YELLOW}Pilih modul [0-5]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            run_unit_and_property_tests()
        elif choice == "2":
            run_criterion_benchmark()
        elif choice == "3":
            run_profiler_simulation()
        elif choice == "4":
            run_compiler_optimization_matrix()
        elif choice == "5":
            run_unit_and_property_tests()
            run_criterion_benchmark()
            run_profiler_simulation()
            run_compiler_optimization_matrix()
        elif choice == "0" or choice.lower() == "exit":
            print(f"{Color.GREEN}Terima kasih! Sesi lab simulasi selesai.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 0-5.{Color.RESET}")

if __name__ == "__main__":
    main()
