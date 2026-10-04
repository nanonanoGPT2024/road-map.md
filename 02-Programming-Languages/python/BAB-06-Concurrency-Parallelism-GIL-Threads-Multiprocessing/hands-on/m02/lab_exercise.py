#!/usr/bin/env python3
"""
Lab: Deep Dive into Python Concurrency & Parallelism (GIL, Threads vs Processes)
Author: Lead System Programmer

Tujuan:
1. Membuktikan dampak Global Interpreter Lock (GIL) pada CPU-bound workload.
2. Membuktikan efisiensi multithreading pada I/O-bound workload (GIL di-release).
3. Membandingkan overhead pembuatan thread vs process secara empiris.
"""

import os
import sys
import time
import math
import hashlib
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Konfigurasi ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_CYAN = "\033[96m"
CLR_MAGENTA = "\033[95m"

# Parameter Simulasi
CPU_WORKLOAD_ITERATIONS = 400_000
IO_SIMULATED_LATENCY = 0.25  # Detik
TASK_COUNT = 4


def log_header(title: str) -> None:
    """Mencetak header section dengan formatting terstruktur."""
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")


def cpu_bound_task(task_id: int, iterations: int) -> tuple[int, str]:
    """
    Simulasi beban kerja CPU-bound: Menghitung digest SHA-256 berulang kali.
    Karena terus-menerus mengeksekusi bytecode CPython tanpa I/O, GIL akan terkunci
    secara agresif dan membatasi eksekusi multithread hanya pada satu core fisik.
    """
    current_hash = hashlib.sha256(f"seed_{task_id}".encode()).hexdigest()
    for _ in range(iterations):
        current_hash = hashlib.sha256(current_hash.encode()).hexdigest()
    return task_id, current_hash[:8]


def io_bound_task(task_id: int, duration: float) -> tuple[int, float]:
    """
    Simulasi beban kerja I/O-bound: Operasi sistem/jaringan non-blocking.
    Fungsi time.sleep() dan syscall I/O secara otomatis melepaskan (release) GIL,
    memungkinkan thread lain mengeksekusi interpreter secara paralel.
    """
    start = time.perf_counter()
    time.sleep(duration)
    elapsed = time.perf_counter() - start
    return task_id, elapsed


def run_benchmark(mode: str, task_type: str, executor_cls=None, max_workers: int = TASK_COUNT) -> float:
    """
    Menjalankan eksekusi terukur dan menghitung total wall-clock time.
    """
    start_time = time.perf_counter()

    if mode == "Sequential (1 Core)":
        for i in range(TASK_COUNT):
            if task_type == "CPU":
                cpu_bound_task(i, CPU_WORKLOAD_ITERATIONS)
            else:
                io_bound_task(i, IO_SIMULATED_LATENCY)
    else:
        with executor_cls(max_workers=max_workers) as executor:
            if task_type == "CPU":
                futures = [executor.submit(cpu_bound_task, i, CPU_WORKLOAD_ITERATIONS) for i in range(TASK_COUNT)]
            else:
                futures = [executor.submit(io_bound_task, i, IO_SIMULATED_LATENCY) for i in range(TASK_COUNT)]
            _ = [f.result() for f in futures]

    elapsed = time.perf_counter() - start_time
    return elapsed


def print_result_row(method: str, elapsed: float, baseline: float, is_cpu: bool) -> None:
    """Mencetak baris hasil benchmark dengan analisis speedup."""
    speedup = baseline / elapsed if elapsed > 0 else 1.0
    
    # Indikasi efektivitas berdasarkan GIL mechanics
    if is_cpu:
        # Pada CPU-bound: Threading lambat karena GIL; Multiprocessing cepat
        if speedup > 1.8:
            status = f"{CLR_GREEN}EFEKTIF (Bypass GIL via OS Process){CLR_RESET}"
        elif speedup <= 1.05:
            status = f"{CLR_RED}TERKUNCI GIL (Thread Contention){CLR_RESET}"
        else:
            status = f"{CLR_YELLOW}MODERAT{CLR_RESET}"
    else:
        # Pada I/O-bound: Threading dan Multiprocess sama-sama efisien
        if speedup > 2.0:
            status = f"{CLR_GREEN}EFEKTIF (GIL Dilepas saat I/O Wait){CLR_RESET}"
        else:
            status = f"{CLR_RED}INEFISIEN{CLR_RESET}"

    print(f"| {method:<28} | {elapsed:>8.4f}s | {speedup:>7.2f}x | {status}")


def main() -> None:
    """Titik masuk utama untuk eksekusi laboratorium komparatif."""
    cpu_cores = os.cpu_count() or 1
    log_header(f"System Info: {cpu_cores} Logical Cores Tersedia | Target: {TASK_COUNT} Tasks")

    # ==========================================
    # BENCHMARK 1: CPU-BOUND EXPERIMENT
    # ==========================================
    print(f"\n{CLR_BOLD}--- SKENARIO 1: CPU-Bound Task (SHA-256 Cryptographic Hashing) ---{CLR_RESET}")
    print(f"{CLR_MAGENTA}Analisis: Menguji dampak GIL contention pada thread vs isolasi proses.{CLR_RESET}")
    
    cpu_base = run_benchmark("Sequential (1 Core)", "CPU")
    print(f"+{'-' * 30}+{'-' * 11}+{'-' * 10}+{'-' * 38}+")
    print(f"| {'Metode Eksekusi':<28} | {'Durasi':<9} | {'Speedup':<8} | {'Dampak Mekanikal'}")
    print(f"+{'-' * 30}+{'-' * 11}+{'-' * 10}+{'-' * 38}+")
    print_result_row("Sequential (Baseline)", cpu_base, cpu_base, is_cpu=True)

    cpu_threaded = run_benchmark("Multithreading", "CPU", ThreadPoolExecutor)
    print_result_row(f"ThreadPool ({TASK_COUNT} Threads)", cpu_threaded, cpu_base, is_cpu=True)

    cpu_proc = run_benchmark("Multiprocessing", "CPU", ProcessPoolExecutor)
    print_result_row(f"ProcessPool ({TASK_COUNT} Procs)", cpu_proc, cpu_base, is_cpu=True)
    print(f"+{'-' * 30}+{'-' * 11}+{'-' * 10}+{'-' * 38}+")

    # ==========================================
    # BENCHMARK 2: I/O-BOUND EXPERIMENT
    # ==========================================
    print(f"\n{CLR_BOLD}--- SKENARIO 2: I/O-Bound Task (Simulated Network/Socket Latency) ---{CLR_RESET}")
    print(f"{CLR_MAGENTA}Analisis: Menguji efisiensi concurrency saat syscall melepaskan interpreter lock.{CLR_RESET}")

    io_base = run_benchmark("Sequential (1 Core)", "I/O")
    print(f"+{'-' * 30}+{'-' * 11}+{'-' * 10}+{'-' * 38}+")
    print(f"| {'Metode Eksekusi':<28} | {'Durasi':<9} | {'Speedup':<8} | {'Dampak Mekanikal'}")
    print(f"+{'-' * 30}+{'-' * 11}+{'-' * 10}+{'-' * 38}+")
    print_result_row("Sequential (Baseline)", io_base, io_base, is_cpu=False)

    io_threaded = run_benchmark("Multithreading", "I/O", ThreadPoolExecutor)
    print_result_row(f"ThreadPool ({TASK_COUNT} Threads)", io_threaded, io_base, is_cpu=False)

    io_proc = run_benchmark("Multiprocessing", "I/O", ProcessPoolExecutor)
    print_result_row(f"ProcessPool ({TASK_COUNT} Procs)", io_proc, io_base, is_cpu=False)
    print(f"+{'-' * 30}+{'-' * 11}+{'-' * 10}+{'-' * 38}+")

    # ==========================================
    # KESIMPULAN ARSITEKTURAL
    # ==========================================
    print(f"\n{CLR_BOLD}{CLR_CYAN}[KESIMPULAN LEAD SYSTEM PROGRAMMER]{CLR_RESET}")
    print(f"1. {CLR_YELLOW}CPU-BOUND:{CLR_RESET} ThreadPool GAGAL memberikan speedup signifikan karena interpreter")
    print(f"   secara berkala mengunci GIL. ProcessPool mem-bypass batasan ini dengan memori terpisah.")
    print(f"2. {CLR_YELLOW}I/O-BOUND:{CLR_RESET} ThreadPool SANGAT EFEKTIF karena GIL di-release saat thread tidur / I/O wait.")
    print(f"   ThreadPool lebih direkomendasikan daripada ProcessPool untuk I/O karena memori yang jauh lebih ringan.")


if __name__ == "__main__":
    # Standard safeguard untuk multiprocessing di semua platform (POSIX/Windows)
    main()