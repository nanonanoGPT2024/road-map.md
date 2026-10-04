#!/usr/bin/env python3
"""
Lab Hands-on: Runtime Backend & Concurrency Model (Deep Dive)
Bab: 04 - Kategori: 01-Core-Foundations

Tujuan Praktikum:
1. Mengamati perbedaan fundamental antara Synchronous Blocking, Thread-Pool (I/O Concurrency), 
   Asyncio Event-Loop (Cooperative Multitasking), dan Multiprocessing (Parallel CPU-bound).
2. Membuktikan dampak Python Global Interpreter Lock (GIL) pada beban CPU-bound vs I/O-bound.
3. Memberikan pemahaman analitis kapan backend engineer harus memilih Event-Driven, 
   Threading, atau Multiprocessing.
"""

import sys
import os
import time
import math
import hashlib
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Konfigurasi Terminal ANSI Escape Sequences
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_CYAN    = "\033[96m"
CLR_MAGENTA = "\033[95m"

def print_banner(text: str):
    """Menampilkan banner header terformat."""
    separator = "=" * 78
    print(f"\n{CLR_CYAN}{CLR_BOLD}{separator}")
    print(f"[*] {text}")
    print(f"{separator}{CLR_RESET}\n")

def print_result_row(model: str, task_type: str, elapsed: float, throughput: float, notes: str):
    """Menampilkan baris metrik kinerja secara terstruktur."""
    print(f"| {CLR_BOLD}{model:<18}{CLR_RESET} | {task_type:<10} | {CLR_YELLOW}{elapsed:>8.4f}s{CLR_RESET} | "
          f"{CLR_GREEN}{throughput:>10.2f} req/s{CLR_RESET} | {notes:<22} |")

# ==============================================================================
# 1. DEFINISI WORKLOAD (I/O BOUND vs CPU BOUND)
# ==============================================================================

def io_bound_task(task_id: int, delay: float) -> str:
    """
    Simulasi operasi I/O-bound (misal: query database atau HTTP remote call).
    Menggunakan time.sleep() yang membebaskan GIL di runtime CPython.
    """
    time.sleep(delay)
    return f"IO-Task-{task_id} OK"

async def async_io_bound_task(task_id: int, delay: float) -> str:
    """
    Simulasi operasi I/O-bound secara non-blocking di dalam Asyncio Event Loop.
    Suspensi tugas dilakukan melalui cooperative context switching (await).
    """
    await asyncio.sleep(delay)
    return f"AsyncIO-Task-{task_id} OK"

def cpu_bound_task(task_id: int, iterations: int) -> str:
    """
    Simulasi komputasi intensif CPU-bound (hashing berulang).
    Beban ini terus memegang GIL di runtime thread standar CPython.
    """
    digest = hashlib.sha256(f"seed-{task_id}".encode()).digest()
    for _ in range(iterations):
        digest = hashlib.sha256(digest).digest()
    return f"CPU-Task-{task_id}: {digest.hex()[:8]}"

# ==============================================================================
# 2. RUNNER UNTUK PENGUJIAN I/O BOUND
# ==============================================================================

def run_io_sequential(n_tasks: int, delay: float) -> float:
    """Eksekusi I/O secara sekuensial (blocking monolitik biasa)."""
    start_time = time.perf_counter()
    for i in range(n_tasks):
        io_bound_task(i, delay)
    return time.perf_counter() - start_time

def run_io_threads(n_tasks: int, delay: float, max_workers: int) -> float:
    """Eksekusi I/O menggunakan ThreadPool (Preemptive Multithreading)."""
    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(io_bound_task, i, delay) for i in range(n_tasks)]
        for f in futures:
            f.result()
    return time.perf_counter() - start_time

async def _async_io_gather(n_tasks: int, delay: float):
    tasks = [async_io_bound_task(i, delay) for i in range(n_tasks)]
    await asyncio.gather(*tasks)

def run_io_asyncio(n_tasks: int, delay: float) -> float:
    """Eksekusi I/O menggunakan single-threaded Asyncio Event Loop."""
    start_time = time.perf_counter()
    asyncio.run(_async_io_gather(n_tasks, delay))
    return time.perf_counter() - start_time

# ==============================================================================
# 3. RUNNER UNTUK PENGUJIAN CPU BOUND & GIL BOTTLENECK
# ==============================================================================

def run_cpu_sequential(n_tasks: int, iterations: int) -> float:
    """Eksekusi CPU sekuensial pada satu thread tunggal."""
    start_time = time.perf_counter()
    for i in range(n_tasks):
        cpu_bound_task(i, iterations)
    return time.perf_counter() - start_time

def run_cpu_threads(n_tasks: int, iterations: int, max_workers: int) -> float:
    """
    Eksekusi CPU menggunakan ThreadPool.
    Karena GIL CPython, multi-thread CPU-bound TIDAK memberikan percepatan paralel,
    bahkan berpotensi lebih lambat karena thread context switching overhead.
    """
    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(cpu_bound_task, i, iterations) for i in range(n_tasks)]
        for f in futures:
            f.result()
    return time.perf_counter() - start_time

def run_cpu_processes(n_tasks: int, iterations: int, max_workers: int) -> float:
    """
    Eksekusi CPU menggunakan ProcessPool.
    Tiap prosesor memiliki interpreter dan GIL independen di tingkat OS core.
    """
    start_time = time.perf_counter()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(cpu_bound_task, i, iterations) for i in range(n_tasks)]
        for f in futures:
            f.result()
    return time.perf_counter() - start_time

# ==============================================================================
# MAIN EXECUTION ROUTINE
# ==============================================================================

def main():
    cpu_count = os.cpu_count() or 4
    io_tasks = 20
    io_delay = 0.05  # 50ms latency per request (simulasi query DB)
    
    cpu_tasks = 8
    cpu_iterations = 250_000  # Iterasi SHA-256

    print_banner(f"LAB RUNTIME BACKEND: CONCURRENCY MODELS & GIL ANALYSIS\n"
                 f"Host Core Count: {cpu_count} vCPU | Python: {sys.version.split()[0]}")

    # --------------------------------------------------------------------------
    # BENCHMARK 1: I/O-BOUND WORKLOAD
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}SKENARIO 1: Simulasi Web Server I/O Bound (Database/Remote API Calls){CLR_RESET}")
    print(f"Total Requests: {io_tasks} | Artificial Delay per Request: {io_delay * 1000:.0f} ms\n")

    print("+" + "-"*20 + "+" + "-"*12 + "+" + "-"*11 + "+" + "-"*13 + "+" + "-"*24 + "+")
    print(f"| {'Concurrency Model':<18} | {'Workload':<10} | {'Duration':<9} | {'Throughput':<11} | {'Engine Efficiency':<22} |")
    print("+" + "-"*20 + "+" + "-"*12 + "+" + "-"*11 + "+" + "-"*13 + "+" + "-"*24 + "+")

    # 1. Sequential I/O
    seq_time = run_io_sequential(io_tasks, io_delay)
    print_result_row("Sequential Sync", "I/O Bound", seq_time, io_tasks / seq_time, "Baseline (Blocking)")

    # 2. ThreadPool I/O
    thread_time = run_io_threads(io_tasks, io_delay, max_workers=cpu_count * 2)
    thread_eff = f"Speedup: {seq_time / thread_time:.1f}x"
    print_result_row("ThreadPoolExecutor", "I/O Bound", thread_time, io_tasks / thread_time, thread_eff)

    # 3. Asyncio I/O
    async_time = run_io_asyncio(io_tasks, io_delay)
    async_eff = f"Speedup: {seq_time / async_time:.1f}x (Zero OS Thr)"
    print_result_row("Asyncio Event-Loop", "I/O Bound", async_time, io_tasks / async_time, async_eff)
    print("+" + "-"*20 + "+" + "-"*12 + "+" + "-"*11 + "+" + "-"*13 + "+" + "-"*24 + "+")

    print(f"\n{CLR_GREEN}[i] Analisis I/O:{CLR_RESET} Asyncio dan Multi-threading menang mutlak atas Sequential.")
    print(f"    Pada I/O bound, syscall I/O melepaskan GIL, sehingga Thread pool dan Event Loop sangat efisien.")

    # --------------------------------------------------------------------------
    # BENCHMARK 2: CPU-BOUND WORKLOAD (EKSPLORASI GIL)
    # --------------------------------------------------------------------------
    print_banner(f"SKENARIO 2: Komputasi CPU-Bound (Crypto Hash & GIL Contention)")
    print(f"Total Heavy Tasks: {cpu_tasks} | SHA-256 Iterations per Task: {cpu_iterations:,}\n")

    print("+" + "-"*20 + "+" + "-"*12 + "+" + "-"*11 + "+" + "-"*13 + "+" + "-"*24 + "+")
    print(f"| {'Concurrency Model':<18} | {'Workload':<10} | {'Duration':<9} | {'Throughput':<11} | {'GIL Impact':<22} |")
    print("+" + "-"*20 + "+" + "-"*12 + "+" + "-"*11 + "+" + "-"*13 + "+" + "-"*24 + "+")

    # 1. Sequential CPU
    cpu_seq_time = run_cpu_sequential(cpu_tasks, cpu_iterations)
    print_result_row("Sequential Sync", "CPU Bound", cpu_seq_time, cpu_tasks / cpu_seq_time, "Single Core Ref")

    # 2. ThreadPool CPU (GIL Bottleneck)
    cpu_thr_time = run_cpu_threads(cpu_tasks, cpu_iterations, max_workers=cpu_count)
    gil_penalty = f"Speedup: {cpu_seq_time / cpu_thr_time:.2f}x (Locked by GIL)"
    print_result_row("ThreadPool (GIL)", "CPU Bound", cpu_thr_time, cpu_tasks / cpu_thr_time, gil_penalty)

    # 3. Multiprocessing CPU (True Parallelism)
    cpu_mp_time = run_cpu_processes(cpu_tasks, cpu_iterations, max_workers=cpu_count)
    mp_boost = f"Speedup: {cpu_seq_time / cpu_mp_time:.2f}x (Multi-Process)"
    print_result_row("ProcessPool (Multi)", "CPU Bound", cpu_mp_time, cpu_tasks / cpu_mp_time, mp_boost)
    print("+" + "-"*20 + "+" + "-"*12 + "+" + "-"*11 + "+" + "-"*13 + "+" + "-"*24 + "+")

    # --------------------------------------------------------------------------
    # RINGKASAN REKOMENDASI ARSITEKTUR BACKEND
    # --------------------------------------------------------------------------
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}KESIMPULAN ENGINEERING ARSITEKTUR RUNTIME:{CLR_RESET}")
    print(f"1. {CLR_CYAN}Asyncio / Event-Loop:{CLR_RESET} Sangat cocok untuk High-Concurrency I/O (REST API, WebSocket, Chat Backend).")
    print(f"   Hemat memori karena berjalan dalam single thread tanpa context-switch overhead OS thread.")
    print(f"2. {CLR_CYAN}ThreadPoolExecutor:{CLR_RESET} Pilihan aman saat mengintegrasikan library I/O legacy/blocking yang belum mendukung `async/await`.")
    print(f"3. {CLR_RED}GIL Limitation:{CLR_RESET} ThreadPool TIDAK meningkatkan performa CPU-bound di Python runtime (CPython).")
    print(f"4. {CLR_GREEN}ProcessPoolExecutor / Background Worker (Celery/RQ):{CLR_RESET} Mutlak diperlukan untuk pemrosesan CPU-bound")
    print(f"   (kompresi citra, model training ML, kriptografi) guna utilisasi multi-core server.")
    print(f"\n{CLR_GREEN}[+] Lab selesai dengan sukses.{CLR_RESET}\n")

if __name__ == "__main__":
    # Menjaga kompatibilitas spawn process di Windows dan macOS
    main()
