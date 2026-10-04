#!/usr/bin/env python3
"""
Lab Exercise: High Performance Computing in R (Simulation Lab)
BAB-09: High-Performance-Computing
Hands-on Module 01: Vectorization, Profiling, Parallelism, and Native Compilation

Simulates core HPC concepts in R:
1. Vectorization vs Iterative Looping (C-level vector ops vs R interpreter overhead)
2. Memory Profiling & Copy-on-Modify (tracemem semantics)
3. Parallel Worker Pools (mclapply / foreach / future backend)
4. Native Compilation & Rcpp Speedup Simulation
"""

import sys
import time
import os
import math
import random
from concurrent.futures import ProcessPoolExecutor, as_completed

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"

def print_banner():
    print(f"{CLR_CYAN}{CLR_BOLD}" + "=" * 70)
    print("   R HIGH PERFORMANCE COMPUTING (HPC) - INTERACTIVE LAB SIMULATOR")
    print("   Topik: Vectorization | Memory semantics | Parallel | Rcpp Engine")
    print("=" * 70 + f"{CLR_RESET}\n")

def simulate_vectorization():
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[MODUL 1] SIMULASI: Vectorization vs Naive Interpreter Loop{CLR_RESET}")
    print("Di R, operasi berbasis vektor (e.g. `x + y`, `colSums`) mengeksekusi loop internal C.")
    print("Sedangkan for-loop manual terkena overhead dynamic type checking & dispatch R interpreter.\n")

    n = 200_000
    data = [random.random() for _ in range(n)]

    # 1. Interpreter loop simulation (simulasi overhead R interpreter loop)
    print(f"{CLR_BLUE}--> Menjalankan simulasi R for-loop (N = {n:,})...{CLR_RESET}")
    t0 = time.perf_counter()
    loop_res = []
    for val in data:
        # Simulasi overhead dynamic dispatch & allocation
        res = math.sqrt(val * 4.2) + math.sin(val)
        loop_res.append(res)
    t_loop = time.perf_counter() - t0
    print(f"    Waktu R For-Loop   : {CLR_RED}{t_loop * 1000:.2f} ms{CLR_RESET}")

    # 2. Vectorized simulation (simulasi compiled vector primitives)
    print(f"{CLR_BLUE}--> Menjalankan simulasi R Vectorized Primitive (simulasi SIMD / C backend)...{CLR_RESET}")
    t1 = time.perf_counter()
    # List comprehension / bulk math mapping
    vec_res = [math.sqrt(x * 4.2) + math.sin(x) for x in data]
    t_vec = time.perf_counter() - t1
    print(f"    Waktu Vectorized   : {CLR_GREEN}{t_vec * 1000:.2f} ms{CLR_RESET}")

    speedup = t_loop / (t_vec if t_vec > 0 else 1e-6)
    print(f"\n{CLR_GREEN}{CLR_BOLD}Hasil Evaluasi:{CLR_RESET}")
    print(f"  Speedup Factor: {CLR_MAGENTA}{speedup:.2f}x lebih cepat!{CLR_RESET}")
    print(f"  Prinsip R: Selalu prioritaskan `apply` ber-vektor C / BLAS ketimbang iterative loop.")

def simulate_copy_on_modify():
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[MODUL 2] SIMULASI: Memory Management & Copy-on-Modify (tracemem){CLR_RESET}")
    print("Di R, objek secara default bersifat immutable dengan mekanisme Copy-on-Modify.")
    print("Modifikasi elemen dalam vektor seringkali menduplikasi seluruh chunk RAM!\n")

    class RVectorSimulation:
        def __init__(self, name, size):
            self.name = name
            self.size = size
            self.mem_address = hex(id(self))
            self.data = list(range(size))

        def modify_element_naive(self, idx, val):
            print(f"    {CLR_CYAN}[tracemem]{CLR_RESET} Objek <{self.name}> dimodifikasi di indeks {idx}.")
            print(f"    {CLR_RED}Trigger Duplikasi Memori (Copy-on-Modify)!{CLR_RESET}")
            # Duplikasi data
            new_data = list(self.data)
            new_data[idx] = val
            self.data = new_data
            self.mem_address = hex(id(new_data))
            return self.mem_address

    vec = RVectorSimulation("df_data", 500_000)
    print(f"  Objek teralokasi: {vec.name} (Ukuran: {vec.size:,} elemen)")
    print(f"  Pointer Awal RAM : {CLR_MAGENTA}{vec.mem_address}{CLR_RESET}\n")

    addr1 = vec.modify_element_naive(0, 999)
    print(f"  Pointer Baru RAM : {CLR_YELLOW}{addr1}{CLR_RESET} (Alamat berubah -> Full Copy terjadi)")

    addr2 = vec.modify_element_naive(1, 888)
    print(f"  Pointer Baru RAM : {CLR_YELLOW}{addr2}{CLR_RESET} (Alamat berubah lagi)\n")
    print(f"{CLR_GREEN}Solusi HPC R:{CLR_RESET} Gunakan package `data.table` (operator `:=` in-place) atau reference class (R6)!")

def _heavy_compute_worker(task_id, iterations):
    # Simulasi perhitungan intensif per chunk (Monte Carlo Pi Estimation)
    inside = 0
    rng = random.Random(task_id + 42)
    for _ in range(iterations):
        x = rng.random()
        y = rng.random()
        if (x * x + y * y) <= 1.0:
            inside += 1
    return 4.0 * inside / iterations

def simulate_parallel_computing():
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[MODUL 3] SIMULASI: Parallel Worker Backend (mclapply / future / foreach){CLR_RESET}")
    print("Memanfaatkan multi-core workstation untuk tugas embarrassingly parallel.\n")

    num_chunks = 4
    iterations_per_chunk = 500_000
    total_iters = num_chunks * iterations_per_chunk

    print(f"  Total Monte Carlo Iterations: {total_iters:,} dibagi menjadi {num_chunks} task.")

    # Serial Execution
    print(f"\n{CLR_BLUE}--> [1/2] Eksekusi Serial (Simulasi R base `lapply`):{CLR_RESET}")
    t0 = time.perf_counter()
    serial_results = []
    for i in range(num_chunks):
        res = _heavy_compute_worker(i, iterations_per_chunk)
        serial_results.append(res)
    pi_serial = sum(serial_results) / num_chunks
    t_serial = time.perf_counter() - t0
    print(f"      Estimasi Pi: {pi_serial:.5f} | Waktu: {CLR_RED}{t_serial:.3f} s{CLR_RESET}")

    # Parallel Execution
    cores = min(4, os.cpu_count() or 2)
    print(f"\n{CLR_BLUE}--> [2/2] Eksekusi Paralel (Simulasi `future::plan(multisession, workers={cores})`):{CLR_RESET}")
    t1 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=cores) as executor:
        futures = [executor.submit(_heavy_compute_worker, i, iterations_per_chunk) for i in range(num_chunks)]
        parallel_results = [f.result() for f in as_completed(futures)]
    pi_parallel = sum(parallel_results) / num_chunks
    t_parallel = time.perf_counter() - t1
    print(f"      Estimasi Pi: {pi_parallel:.5f} | Waktu: {CLR_GREEN}{t_parallel:.3f} s{CLR_RESET}")

    speedup = t_serial / (t_parallel if t_parallel > 0 else 1e-6)
    print(f"\n{CLR_GREEN}{CLR_BOLD}Parallel Efficiency:{CLR_RESET}")
    print(f"  Speedup: {CLR_MAGENTA}{speedup:.2f}x{CLR_RESET} pada {cores} worker cores.")
    print(f"  Perhatikan: IPC overhead dan serialization cost (misal export environment di clusterCall).")

def simulate_rcpp_engine():
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[MODUL 4] SIMULASI: Rcpp Native C++ Accelerator Engine{CLR_RESET}")
    print("Rcpp menyambungkan R dengan C++ untuk loop super cepat tanpa overhead interpreter.\n")

    iterations = 1_000_000

    print(f"--> Menghitung Fibonacci / Cumulative Math Sequence ({iterations:,} iterasi)...")

    # Pure Python simulating pure R interpreted loop
    t0 = time.perf_counter()
    acc_r = 0.0
    for i in range(1, iterations + 1):
        acc_r += (i % 7) * 0.123
    t_r = time.perf_counter() - t0
    print(f"    R Interpreted Baseline : {CLR_RED}{t_r * 1000:.2f} ms{CLR_RESET}")

    # Simulated Rcpp compiled execution (compiled loop model)
    t1 = time.perf_counter()
    # Emulating compiled branchless accumulator speed
    acc_cpp = sum((i % 7) * 0.123 for i in range(1, iterations + 1))
    t_cpp = (time.perf_counter() - t1) * 0.15  # Scaled factor representing compiled C++ assembly
    print(f"    Rcpp Compiled C++ Simul: {CLR_GREEN}{t_cpp * 1000:.2f} ms{CLR_RESET}")

    speedup = t_r / (t_cpp if t_cpp > 0 else 1e-6)
    print(f"\n{CLR_GREEN}{CLR_BOLD}Rcpp Benchmark Summary:{CLR_RESET}")
    print(f"  Estimasi Akselerasi Native: {CLR_MAGENTA}{speedup:.1f}x speedup{CLR_RESET}")
    print("  Karakteristik: Zero memory copy via `NumericVector` pointers, zero GC pressure!")

def run_all_simulations():
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}>>> MENJALANKAN SELURUH SUITE SIMULASI HPC R <<<{CLR_RESET}")
    simulate_vectorization()
    simulate_copy_on_modify()
    simulate_parallel_computing()
    simulate_rcpp_engine()
    print(f"\n{CLR_GREEN}{CLR_BOLD}[SELESAI] Seluruh benchmark HPC R berhasil disimulasikan.{CLR_RESET}\n")

def interactive_cli():
    print_banner()
    while True:
        print(f"{CLR_BOLD}Menu Simulasi HPC R:{CLR_RESET}")
        print("  1. Benchmark Vectorization vs Interpreted Loop")
        print("  2. Memory Tracing: Copy-on-Modify Semantics")
        print("  3. Parallel Worker Acceleration (Monte Carlo)")
        print("  4. Rcpp Native Compiled Speedup Simulation")
        print("  5. Jalankan Semua Simulasi")
        print("  0. Keluar")
        print("-" * 50)

        try:
            choice = input(f"{CLR_CYAN}Pilih opsi [0-5]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            simulate_vectorization()
        elif choice == "2":
            simulate_copy_on_modify()
        elif choice == "3":
            simulate_parallel_computing()
        elif choice == "4":
            simulate_rcpp_engine()
        elif choice == "5":
            run_all_simulations()
        elif choice == "0":
            print(f"{CLR_GREEN}Sampai jumpa! Lab selesai.{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan coba lagi.{CLR_RESET}")
        print("\n" + "=" * 50 + "\n")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "--non-interactive"):
        print_banner()
        run_all_simulations()
    else:
        interactive_cli()
