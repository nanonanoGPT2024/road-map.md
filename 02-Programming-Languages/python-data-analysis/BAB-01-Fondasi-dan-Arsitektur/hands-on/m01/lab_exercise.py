#!/usr/bin/env python3
"""
Lab Exercise: Fondasi dan Arsitektur Python untuk Data Analysis (BAB 01)
Simulasi arsitektur memori CPython, overhead PyObject, komputasi vectorized vs interpreted loops,
dan penyimpanan Baris (Row-Oriented) vs Kolom (Columnar).
"""

import sys
import time
import math
import struct
from typing import List, Dict, Any, Tuple

# ANSI Escape Sequences untuk Pewarnaan Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"
BG_BLUE = "\033[44m"
BG_DARK = "\033[100m"

def print_banner() -> None:
    banner = f"""
{CLR_CYAN}{CLR_BOLD}================================================================================
  PY-DATA ARCHITECTURE LAB: BAB 01 - FONDASI & ARSITEKTUR MEMORI DATA
================================================================================{CLR_RESET}
{CLR_WHITE}Eksplorasi Mendalam Arsitektur CPython:
  1. Boxed PyObject vs Contiguous Memory Buffer
  2. Bytecode Loop Overhead vs Vectorized Native Simulation
  3. Row-Oriented (Record-Based) vs Columnar Memory Layout
{CLR_CYAN}--------------------------------------------------------------------------------{CLR_RESET}
"""
    print(banner)

def simulate_pyobject_vs_buffer() -> None:
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[MODUL 1] SIMULASI OVERHEAD PYOBJECT VS CONTIGUOUS BUFFER{CLR_RESET}")
    print(f"{CLR_DIM}Menganalisis footprint memori data mentah vs boxed Python integer object...{CLR_RESET}\n")

    num_elements = 100_000
    
    # 1. Native CPython Int List (Pointer Array pointing to individual PyLongObject)
    sample_int = 42
    sample_size = sys.getsizeof(sample_int)
    ptr_size = 8  # 64-bit pointer
    list_overhead = sys.getsizeof([])
    
    total_python_list_est = list_overhead + (num_elements * ptr_size) + (num_elements * sample_size)
    
    # 2. Contiguous C-Style Buffer (e.g. Int64 array / struct packing)
    raw_buffer = bytearray(num_elements * 8)
    contiguous_size = sys.getsizeof(raw_buffer)

    print(f"{CLR_WHITE}Ukuran Sample Elemen:{CLR_RESET}")
    print(f"  • Single Python Int ({sample_int}): {CLR_RED}{sample_size} bytes{CLR_RESET} (ob_refcnt + ob_type + ob_size + ob_digit)")
    print(f"  • Raw 64-bit Integer:       {CLR_GREEN}8 bytes{CLR_RESET} (Unboxed primitive)")
    print(f"\n{CLR_WHITE}Alokasi Memori untuk {num_elements:,} Elemen:{CLR_RESET}")
    print(f"  • Standard Python List (Boxed):     ~{CLR_RED}{total_python_list_est / (1024 * 1024):.2f} MB{CLR_RESET}")
    print(f"  • Contiguous Flat Buffer (Compact):  {CLR_GREEN}{contiguous_size / (1024 * 1024):.2f} MB{CLR_RESET}")
    
    ratio = total_python_list_est / contiguous_size
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}>> Rasio Penghematan Memori: {ratio:.1f}x lebih hemat dengan contiguous memory buffer!{CLR_RESET}")
    print(f"{CLR_DIM}Insight: NumPy ndarray dan Apache Arrow menghindari boxed PyObject untuk memaksimalkan densitas cache L1/L2.{CLR_RESET}\n")

def simulate_loop_vs_vectorized() -> None:
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[MODUL 2] BENCHMARK INTERPRETER LOOP VS EMULASI VECTORIZED{CLR_RESET}")
    print(f"{CLR_DIM}Menguji dampak dynamic type dispatch & pointer dereferencing pada komputasi...{CLR_RESET}\n")

    n = 200_000
    print(f"Mengalokasikan data sintetis ({n:,} angka desimal)...")
    
    # Python List Float
    py_list = [float(i) * 0.5 for i in range(n)]
    
    # Flat Contiguous Binary Buffer (Double Precision IEEE 754, 8 bytes per item)
    raw_bytes = bytearray(struct.pack(f"{n}d", *py_list))

    print(f"\n{CLR_CYAN}1. Menjalankan Python Bytecode Loop (Dynamic Dispatch):{CLR_RESET}")
    t0 = time.perf_counter()
    accum_py = 0.0
    for val in py_list:
        accum_py += (val * 1.05) - 0.2
    t1 = time.perf_counter()
    py_time = t1 - t0
    print(f"   Hasil: {accum_py:.2f} | Durasi: {CLR_RED}{py_time * 1000:.2f} ms{CLR_RESET}")

    print(f"\n{CLR_CYAN}2. Menjalankan Emulasi Vectorized / Bulk Memory Sweep:{CLR_RESET}")
    t2 = time.perf_counter()
    # Emulasi manipulasi contiguous block menggunakan format un-pack bulk/chunking
    doubles_unpacked = struct.unpack(f"{n}d", raw_bytes)
    # Math built-in fsum beroperasi pada C-level buffer
    accum_vec = math.fsum(doubles_unpacked)
    t3 = time.perf_counter()
    vec_time = t3 - t2
    print(f"   Hasil: {accum_vec:.2f} | Durasi: {CLR_GREEN}{vec_time * 1000:.2f} ms{CLR_RESET}")

    speedup = py_time / (vec_time if vec_time > 0 else 0.000001)
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}>> Speedup Eksploitasi Memory Buffer / C-Level Aggregation: {speedup:.1f}x lebih cepat{CLR_RESET}")
    print(f"{CLR_DIM}Insight: Python loop harus memeriksa `tp_as_number` dan memvalidasi type di setiap iterasi.{CLR_RESET}\n")

def simulate_row_vs_columnar() -> None:
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[MODUL 3] ROW-ORIENTED VS COLUMNAR STORAGE ENGINE{CLR_RESET}")
    print(f"{CLR_DIM}Simulasi query OLAP: 'SELECT AVG(salary) WHERE active = True'{CLR_RESET}\n")

    num_records = 150_000
    
    # Row-Oriented: Array of Dictionaries / Structs (Record format: Python list of dicts)
    row_table: List[Dict[str, Any]] = [
        {"id": i, "active": (i % 3 != 0), "salary": 50000.0 + (i % 1000), "dept": "Engineering"}
        for i in range(num_records)
    ]

    # Columnar-Oriented: Separate contiguous lists / columns
    col_active = [(i % 3 != 0) for i in range(num_records)]
    col_salary = [50000.0 + (i % 1000) for i in range(num_records)]

    # Query pada Row-Store
    print(f"{CLR_CYAN}Querying Row-Oriented Layout (Membaca seluruh object record ke cache):{CLR_RESET}")
    t0 = time.perf_counter()
    row_sum = 0.0
    row_count = 0
    for record in row_table:
        if record["active"]:
            row_sum += record["salary"]
            row_count += 1
    row_avg = row_sum / row_count if row_count else 0
    t1 = time.perf_counter()
    row_time = t1 - t0
    print(f"   Avg: {row_avg:.2f} | Rows: {row_count:,} | Durasi: {CLR_RED}{row_time * 1000:.2f} ms{CLR_RESET}")

    # Query pada Columnar-Store
    print(f"\n{CLR_CYAN}Querying Columnar Layout (Hanya memuat array aktif & array salary):{CLR_RESET}")
    t2 = time.perf_counter()
    col_sum = 0.0
    col_count = 0
    # Vector mask filtering concept
    for is_active, salary in zip(col_active, col_salary):
        if is_active:
            col_sum += salary
            col_count += 1
    col_avg = col_sum / col_count if col_count else 0
    t3 = time.perf_counter()
    col_time = t3 - t2
    print(f"   Avg: {col_avg:.2f} | Rows: {col_count:,} | Durasi: {CLR_GREEN}{col_time * 1000:.2f} ms{CLR_RESET}")

    diff = ((row_time - col_time) / row_time) * 100
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}>> Efisiensi Columnar Access: Reduksi latency sebesar {diff:.1f}%{CLR_RESET}")
    print(f"{CLR_DIM}Insight: Columnar memory layout menghindari cache thrashing dari kolom yang tidak diperlukan ('id', 'dept').{CLR_RESET}\n")

def run_interactive_menu() -> None:
    print_banner()
    while True:
        print(f"{CLR_BOLD}PILIH MENU PRAKTIKUM ARSITEKTUR:{CLR_RESET}")
        print(f"  {CLR_GREEN}[1]{CLR_RESET} Simulasi PyObject Overhead vs Contiguous Native Buffer")
        print(f"  {CLR_GREEN}[2]{CLR_RESET} Benchmark Interpreter Loop vs Vectorized C-Level Aggregation")
        print(f"  {CLR_GREEN}[3]{CLR_RESET} Simulasi Row-Oriented vs Columnar Memory Access")
        print(f"  {CLR_GREEN}[4]{CLR_RESET} Jalankan Seluruh Eksperimen Berurutan")
        print(f"  {CLR_RED}[0]{CLR_RESET} Keluar")
        
        try:
            choice = input(f"\n{CLR_BOLD}Masukkan pilihan (0-4) [default: 4]: {CLR_RESET}").strip()
            if not choice:
                choice = "4"
        except (EOFError, KeyboardInterrupt):
            print(f"\n{CLR_YELLOW}Selesai.{CLR_RESET}")
            break

        if choice == "1":
            simulate_pyobject_vs_buffer()
        elif choice == "2":
            simulate_loop_vs_vectorized()
        elif choice == "3":
            simulate_row_vs_columnar()
        elif choice == "4":
            simulate_pyobject_vs_buffer()
            simulate_loop_vs_vectorized()
            simulate_row_vs_columnar()
            print(f"\n{CLR_GREEN}{CLR_BOLD}=== Seluruh Modul Berhasil Dijalankan ==={CLR_RESET}\n")
            break
        elif choice == "0":
            print(f"\n{CLR_CYAN}Terima kasih telah menjalankan lab arsitektur!{CLR_RESET}\n")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan masukkan angka 0-4.{CLR_RESET}\n")

if __name__ == "__main__":
    run_interactive_menu()
