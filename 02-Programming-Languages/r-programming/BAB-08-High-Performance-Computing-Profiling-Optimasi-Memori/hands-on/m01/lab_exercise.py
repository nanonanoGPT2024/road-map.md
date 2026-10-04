#!/usr/bin/env python3
"""
Hands-on Lab Exercise: M01 - High Performance Computing, Profiling & Optimasi Memori
Simulasi Konsep R-Programming (BAB-08) dalam Python 3 Mandiri.

Konsep yang disimulasikan:
1. Copy-on-Modify semantics & memory tracking (mirip `tracemem()` & `lobstr::ref()` di R)
2. Vectorization vs Sequential Overhead (mirip optimasi vectorized R vs loop `for`)
3. Call-stack Sampling Profiler (mirip `Rprof()` & visualisasi `profvis`)
4. Parallel Worker Distribution (mirip `mclapply()` / `parallel::parLapply()`)
"""

import sys
import time
import os
import random
import tracemalloc
from typing import List, Dict, Any, Callable
from concurrent.futures import ProcessPoolExecutor

# ANSI Color Codes
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    BG_BLUE = "\033[44m"
    WHITE_BOLD = "\033[1;97m"

def print_banner(title: str) -> None:
    width = 72
    print(f"\n{TermColor.CYAN}{'=' * width}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.WHITE_BOLD}{title.center(width)}{TermColor.RESET}")
    print(f"{TermColor.CYAN}{'=' * width}{TermColor.RESET}")

def print_section(title: str) -> None:
    print(f"\n{TermColor.YELLOW}▶ {TermColor.BOLD}{title}{TermColor.RESET}")

def print_info(label: str, value: Any, color: str = TermColor.GREEN) -> None:
    print(f"  {TermColor.BOLD}{label:<28}: {color}{value}{TermColor.RESET}")

def simulate_heavy_compute(val: float) -> float:
    """Simulasi fungsi komputasi numerik intensif."""
    acc = val
    for _ in range(3500):
        acc = (acc * 1.00013 + 0.002) % 1000.0
    return acc

class RProfilerSimulator:
    """Simulasi sampling profiler seperti Rprof / profvis di R."""
    def __init__(self):
        self.call_records: List[Dict[str, Any]] = []

    def profile_function(self, name: str, func: Callable, *args, **kwargs) -> Any:
        start_time = time.perf_counter()
        tracemalloc.start()
        start_mem, _ = tracemalloc.get_traced_memory()
        
        result = func(*args, **kwargs)
        
        peak_mem = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        elapsed = (time.perf_counter() - start_time) * 1000.0  # ms
        mem_diff_kb = (peak_mem - start_mem) / 1024.0

        self.call_records.append({
            "name": name,
            "duration_ms": elapsed,
            "peak_mem_kb": mem_diff_kb
        })
        return result

    def display_report(self) -> None:
        print_section("Rprof / profvis Emulated Flame Report")
        header = f"| {'Function / Phase':<28} | {'Duration (ms)':<15} | {'Peak Mem (KB)':<15} |"
        print(f"{TermColor.BLUE}{'-' * len(header)}{TermColor.RESET}")
        print(f"{TermColor.BOLD}{header}{TermColor.RESET}")
        print(f"{TermColor.BLUE}{'-' * len(header)}{TermColor.RESET}")
        
        for item in self.call_records:
            name = item["name"]
            dur = f"{item['duration_ms']:.3f} ms"
            mem = f"{item['peak_mem_kb']:.2f} KB"
            print(f"| {TermColor.CYAN}{name:<28}{TermColor.RESET} | {dur:<15} | {mem:<15} |")
        print(f"{TermColor.BLUE}{'-' * len(header)}{TermColor.RESET}")

def lab_copy_on_modify_simulation():
    """
    Laboratorium 1:
    Simulasi perilaku Copy-on-Modify R & pelacakan objek (tracemem semantic).
    Di R, ketika objek dimodifikasi tanpa single binding, R membuat salinan di RAM.
    """
    print_banner("LAB 1: COPY-ON-MODIFY & MEMORY POINTER ALLOCATION")
    print(f"{TermColor.MAGENTA}Mempelajari overhead alokasi memori ketika objek diduplikasi vs di-update di tempat.{TermColor.RESET}\n")

    # Objek Awal
    size = 200_000
    print(f"1. Mengalokasikan vector 'x' sebesar {size:,} elemen...")
    original_vec = list(range(size))
    addr_x = hex(id(original_vec))
    print_info("Pointer awal x", addr_x, TermColor.CYAN)

    # Replikasi binding: y <- x (Shared pointer / shallow copy)
    vec_y = original_vec
    addr_y = hex(id(vec_y))
    print_info("Pointer y (y <- x)", addr_y, TermColor.CYAN)
    print(f"   Status: {TermColor.GREEN}Shared Memory Pointer (Reference count meningkat, zero extra RAM){TermColor.RESET}")

    # Modifikasi elemen y: y[1] <- 999
    # Simulasi Copy-on-Modify: Pembuatan klon baru secara eksplisit seperti yang dilakukan interpreter R
    print("\n2. Memodifikasi elemen y[0] (Memicu Copy-on-Modify / tracemem)...")
    tracemalloc.start()
    t0 = time.perf_counter()
    modified_y = list(original_vec)  # Copy
    modified_y[0] = 999
    dt = (time.perf_counter() - t0) * 1000.0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    addr_y_mod = hex(id(modified_y))
    print(f"   {TermColor.RED}[tracemem LOG]{TermColor.RESET} Object duplicated at memory boundary: {addr_x} -> {addr_y_mod}")
    print_info("Pointer y setelah modify", addr_y_mod, TermColor.YELLOW)
    print_info("Waktu Copy Duplikasi", f"{dt:.2f} ms", TermColor.RED)
    print_info("Peningkatan Memori", f"{peak_mem / 1024:.2f} KB", TermColor.RED)

    # Strategi Solusi: Pre-allocation vector
    print("\n3. Solusi Optimasi R: Pre-allocation vektor untuk menghindari multiple copies")
    t0 = time.perf_counter()
    preallocated = [0] * 50_000
    for i in range(len(preallocated)):
        preallocated[i] = i * 2
    t_prealloc = (time.perf_counter() - t0) * 1000.0

    # Dynamic growing vector (Anti-pattern di R: x <- c(x, new_val))
    t0 = time.perf_counter()
    dynamic_growth: List[int] = []
    for i in range(50_000):
        dynamic_growth.append(i * 2)
    t_growth = (time.perf_counter() - t0) * 1000.0

    print_info("Waktu Pre-allocation", f"{t_prealloc:.2f} ms", TermColor.GREEN)
    print_info("Waktu Dynamic Appending", f"{t_growth:.2f} ms", TermColor.YELLOW)
    speedup = t_growth / max(t_prealloc, 0.001)
    print(f"   {TermColor.BOLD}Efisiensi pre-allocation: {TermColor.GREEN}{speedup:.2f}x lebih terukur{TermColor.RESET}\n")

def lab_vectorization_vs_loop():
    """
    Laboratorium 2:
    Simulasi efisiensi komputasi tervektorisasi vs nested loop manual.
    Di R, operasi `x + y` memanggil C level SIMD, sedangkan loop memicu interpret R overhead.
    """
    print_banner("LAB 2: VECTORIZED OPERATIONS VS INTERPRETED LOOPS")
    print(f"{TermColor.MAGENTA}Membandingkan komputasi elemen-per-elemen loop R vs Vectorized primitives.{TermColor.RESET}\n")

    n_samples = 400_000
    vec_a = [random.random() for _ in range(n_samples)]
    vec_b = [random.random() for _ in range(n_samples)]

    # Pendekatan 1: Iterasi manual (simulasi loop for(i in 1:n) di R)
    print(f"1. Menjalankan simulasi loop 'for (i in 1:N)' pada {n_samples:,} observasi...")
    t0 = time.perf_counter()
    res_loop = [0.0] * n_samples
    for i in range(n_samples):
        res_loop[i] = (vec_a[i] ** 2) + (vec_b[i] * 3.1415)
    t_loop = (time.perf_counter() - t0) * 1000.0
    print_info("Eksekusi Interpreted Loop", f"{t_loop:.2f} ms", TermColor.RED)

    # Pendekatan 2: List comprehension / SIMD vectorization emulation
    print("2. Menjalankan operasi tervektorisasi (simulasi C-internal R vector math)...")
    t0 = time.perf_counter()
    res_vec = [(a ** 2) + (b * 3.1415) for a, b in zip(vec_a, vec_b)]
    t_vec = (time.perf_counter() - t0) * 1000.0
    print_info("Eksekusi Vectorized Primitive", f"{t_vec:.2f} ms", TermColor.GREEN)

    speedup = t_loop / max(t_vec, 0.001)
    print(f"\n   {TermColor.BOLD}{TermColor.GREEN}Hasil Speedup: {speedup:.2f}x lebih cepat!{TermColor.RESET}")
    print(f"   {TermColor.CYAN}Kesimpulan: Hindari dynamic for-loop pada data besar; gunakan fungsi vectorized (Rcpp / matrix ops).{TermColor.RESET}\n")

def worker_task(chunk: List[float]) -> float:
    """Worker sub-proses untuk simulasi parallel cluster."""
    return sum(simulate_heavy_compute(x) for x in chunk)

def lab_parallel_hpc_simulation():
    """
    Laboratorium 3:
    Simulasi Parallel Processing & Amdahl's Law (mirip parallel::parLapply / future di R).
    """
    print_banner("LAB 3: HIGH-PERFORMANCE PARALLEL COMPUTING & AMDAHL'S LAW")
    print(f"{TermColor.MAGENTA}Mengevaluasi skalabilitas batch task pada multiprocessing cluster.{TermColor.RESET}\n")

    items = [float(i) for i in range(120)]
    num_cores = os.cpu_count() or 4
    worker_count = min(4, num_cores)

    # Eksekusi Sekuensial (Single Core)
    print(f"1. Menjalankan {len(items)} batch task secara Sekuensial (1 Core)...")
    t0 = time.perf_counter()
    seq_results = [simulate_heavy_compute(x) for x in items]
    t_seq = time.perf_counter() - t0
    print_info("Waktu Sekuensial", f"{t_seq:.3f} detik", TermColor.YELLOW)

    # Eksekusi Paralel (Multi Core)
    print(f"\n2. Menjalankan batch task secara Paralel ({worker_count} Workers / Forked Processes)...")
    chunk_size = (len(items) + worker_count - 1) // worker_count
    chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        par_results = list(executor.map(worker_task, chunks))
    t_par = time.perf_counter() - t0
    print_info("Waktu Paralel", f"{t_par:.3f} detik", TermColor.GREEN)

    speedup = t_seq / max(t_par, 0.0001)
    efficiency = (speedup / worker_count) * 100.0
    print_info("Speedup Teramati", f"{speedup:.2f}x", TermColor.CYAN)
    print_info("Efisiensi Paralel", f"{efficiency:.1f}%", TermColor.CYAN)

    # Evaluasi overhead inter-process communication (IPC)
    print(f"\n   {TermColor.WHITE_BOLD}Catatan Arsitektur HPC:{TermColor.RESET}")
    print(f"   - Keuntungan paralel dibatasi oleh IPC overhead & serial fraction (Amdahl's Law).")
    print(f"   - Jika task komputasi terlalu kecil, overhead spawning worker akan lebih besar dari runtime.{TermColor.RESET}\n")

def run_profiler_suite():
    """Laboratorium 4: Menjalankan profiler terintegrasi."""
    print_banner("LAB 4: PROFILING CALL STACK DENGAN RPROF SIMULATOR")
    profiler = RProfilerSimulator()

    def phase_matrix_generation():
        return [[random.random() for _ in range(100)] for _ in range(100)]

    def phase_matrix_multiplication(mat):
        n = len(mat)
        res = [[0.0] * n for _ in range(n)]
        for i in range(min(n, 60)):
            for j in range(min(n, 60)):
                res[i][j] = sum(mat[i][k] * mat[k][j] for k in range(min(n, 60)))
        return res

    def phase_garbage_cleanup():
        import gc
        gc.collect()

    m = profiler.profile_function("Matrix Initialization", phase_matrix_generation)
    profiler.profile_function("Dense Matrix Sub-Ops", phase_matrix_multiplication, m)
    profiler.profile_function("Memory GC Collect", phase_garbage_cleanup)

    profiler.display_report()

def interactive_menu():
    """Tampilan menu interaktif."""
    while True:
        print_banner("KONSOL INTERAKTIF: HPC, PROFILING & OPTIMASI MEMORI (R)")
        print(f"{TermColor.BOLD}Pilih Modul Lab Hands-on:{TermColor.RESET}")
        print(f"  {TermColor.GREEN}[1]{TermColor.RESET} Lab 1: Copy-on-Modify Semantics & Pre-allocation")
        print(f"  {TermColor.GREEN}[2]{TermColor.RESET} Lab 2: Vectorized vs Interpreted Loops")
        print(f"  {TermColor.GREEN}[3]{TermColor.RESET} Lab 3: Parallel Processing & HPC Cluster Emulation")
        print(f"  {TermColor.GREEN}[4]{TermColor.RESET} Lab 4: Call Stack Profiling (Rprof & Flame Graph)")
        print(f"  {TermColor.GREEN}[5]{TermColor.RESET} Jalankan SEMUA Modul Sekaligus")
        print(f"  {TermColor.RED}[0]{TermColor.RESET} Keluar / Exit")
        
        try:
            choice = input(f"\n{TermColor.BOLD}Masukkan pilihan (0-5) [Default 5]: {TermColor.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{TermColor.YELLOW}Selesai.{TermColor.RESET}")
            break

        if not choice:
            choice = "5"

        if choice == "1":
            lab_copy_on_modify_simulation()
        elif choice == "2":
            lab_vectorization_vs_loop()
        elif choice == "3":
            lab_parallel_hpc_simulation()
        elif choice == "4":
            run_profiler_suite()
        elif choice == "5":
            lab_copy_on_modify_simulation()
            lab_vectorization_vs_loop()
            lab_parallel_hpc_simulation()
            run_profiler_suite()
            break
        elif choice == "0":
            print(f"{TermColor.GREEN}Terima kasih telah menjalankan simulasi HPC R-Programming!{TermColor.RESET}")
            break
        else:
            print(f"{TermColor.RED}Pilihan tidak valid. Silakan coba lagi.{TermColor.RESET}")

if __name__ == "__main__":
    # Jika dijalankan non-interaktif dalam batch CI/CD atau test pipe, jalankan mode komprehensif
    if not sys.stdin.isatty():
        lab_copy_on_modify_simulation()
        lab_vectorization_vs_loop()
        lab_parallel_hpc_simulation()
        run_profiler_suite()
    else:
        interactive_menu()
