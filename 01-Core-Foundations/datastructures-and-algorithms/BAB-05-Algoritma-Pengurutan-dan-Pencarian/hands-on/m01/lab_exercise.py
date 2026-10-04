#!/usr/bin/env python3
"""
Lab Exercise M01: Algoritma Pengurutan dan Pencarian (Sorting & Searching)
BAB-05: Algoritma Pengurutan dan Pencarian
Core Foundations - Data Structures & Algorithms

Simulasi interaktif dengan visualisasi terminal ANSI berwarna.
Mencakup:
- Bubble Sort, Insertion Sort, Merge Sort, Quick Sort (Visualisasi Step-by-Step)
- Linear Search vs Binary Search (Perbandingan Langkah & Kompleksitas O(n) vs O(log n))
- Benchmark Performa Empiris
"""

import sys
import time
import random
from typing import List, Tuple, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"
BG_YELLOW = "\033[43m"


def clear_screen() -> None:
    """Membersihkan layar terminal."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def render_array(arr: List[int], active_indices: Optional[List[int]] = None,
                 pivot_index: Optional[int] = None, sorted_indices: Optional[List[int]] = None) -> str:
    """Merender representasi grafis nilai array dalam bentuk bar ANSI."""
    active_indices = active_indices or []
    sorted_indices = sorted_indices or []
    
    parts = []
    for idx, val in enumerate(arr):
        val_str = f"{val:2d}"
        if idx == pivot_index:
            parts.append(f"{BG_YELLOW}{WHITE}{BOLD} {val_str} {RESET}")
        elif idx in active_indices:
            parts.append(f"{BG_RED}{WHITE}{BOLD} {val_str} {RESET}")
        elif idx in sorted_indices:
            parts.append(f"{BG_GREEN}{WHITE} {val_str} {RESET}")
        else:
            parts.append(f"{BLUE} {val_str} {RESET}")
    return " ".join(parts)


def bubble_sort_visual(arr_in: List[int], delay: float = 0.08) -> Tuple[List[int], int, int]:
    """Visualisasi Bubble Sort: O(n^2) waktu, O(1) ruang."""
    arr = list(arr_in)
    n = len(arr)
    comparisons = 0
    swaps = 0
    sorted_indices = []

    print(f"\n{BOLD}{CYAN}=== Memulai Bubble Sort ==={RESET}")
    print(f"{DIM}Prinsip: Mengapungkan elemen terbesar ke posisi akhir setiap pass.{RESET}\n")

    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            comparisons += 1
            print(f"\rLangkah [{comparisons:2d}] Cek {arr[j]} & {arr[j+1]}: {render_array(arr, [j, j+1], sorted_indices=sorted_indices)}", end="")
            sys.stdout.flush()
            time.sleep(delay)

            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swaps += 1
                swapped = True
                print(f"\rLangkah [{comparisons:2d}] Swap!   : {render_array(arr, [j, j+1], sorted_indices=sorted_indices)}", end="")
                sys.stdout.flush()
                time.sleep(delay)

        sorted_indices.append(n - i - 1)
        if not swapped:
            break

    sorted_indices = list(range(n))
    print(f"\rHasil Akhir       : {render_array(arr, sorted_indices=sorted_indices)}\n")
    print(f"{GREEN}✓ Selesai! Perbandingan: {comparisons}, Pertukaran (Swap): {swaps}{RESET}")
    return arr, comparisons, swaps


def insertion_sort_visual(arr_in: List[int], delay: float = 0.08) -> Tuple[List[int], int, int]:
    """Visualisasi Insertion Sort: O(n^2) waktu, O(1) ruang, adaptif."""
    arr = list(arr_in)
    n = len(arr)
    comparisons = 0
    shifts = 0

    print(f"\n{BOLD}{CYAN}=== Memulai Insertion Sort ==={RESET}")
    print(f"{DIM}Prinsip: Menyisipkan elemen ke bagian array kiri yang sudah terurut.{RESET}\n")

    for i in range(1, n):
        key = arr[i]
        j = i - 1
        print(f"\nMenyisipkan key={YELLOW}{key}{RESET} (posisi {i})")

        while j >= 0:
            comparisons += 1
            print(f"\rCek arr[{j}]={arr[j]} > {key}?: {render_array(arr, [j, j+1])}", end="")
            sys.stdout.flush()
            time.sleep(delay)

            if arr[j] > key:
                arr[j + 1] = arr[j]
                shifts += 1
                j -= 1
                time.sleep(delay)
            else:
                break

        arr[j + 1] = key
        print(f"\rTersisip di indeks [{j+1}]: {render_array(arr, sorted_indices=list(range(i + 1)))}")
        time.sleep(delay)

    print(f"\n{GREEN}✓ Selesai! Perbandingan: {comparisons}, Pergeseran (Shift): {shifts}{RESET}")
    return arr, comparisons, shifts


def quick_sort_visual(arr: List[int], low: int, high: int, stats: dict, delay: float = 0.08) -> None:
    """Visualisasi Quick Sort: O(n log n) rata-rata, Divide and Conquer."""
    if low < high:
        # Partisi Lomuto
        pivot = arr[high]
        i = low - 1
        print(f"\nPartisi range [{low}..{high}] | Pivot: {YELLOW}{pivot}{RESET}")

        for j in range(low, high):
            stats["comparisons"] += 1
            print(f"\rBandingkan arr[{j}]={arr[j]} <= {pivot}: {render_array(arr, [j], pivot_index=high)}", end="")
            sys.stdout.flush()
            time.sleep(delay)

            if arr[j] <= pivot:
                i += 1
                arr[i], arr[j] = arr[j], arr[i]
                stats["swaps"] += 1
                print(f"\rTukar ke partisi kiri: {render_array(arr, [i, j], pivot_index=high)}", end="")
                sys.stdout.flush()
                time.sleep(delay)

        arr[i + 1], arr[high] = arr[high], arr[i + 1]
        stats["swaps"] += 1
        pivot_idx = i + 1
        print(f"\rPivot {pivot} menetap di [{pivot_idx}]: {render_array(arr, sorted_indices=[pivot_idx])}")
        time.sleep(delay)

        quick_sort_visual(arr, low, pivot_idx - 1, stats, delay)
        quick_sort_visual(arr, pivot_idx + 1, high, stats, delay)


def linear_search_visual(arr: List[int], target: int, delay: float = 0.1) -> int:
    """Pencarian Linear: O(n) waktu, memeriksa berurutan satu per satu."""
    print(f"\n{BOLD}{MAGENTA}=== Linear Search (Target: {target}) ==={RESET}")
    steps = 0
    for idx, val in enumerate(arr):
        steps += 1
        print(f"\rLangkah {steps:2d} | Cek indeks [{idx}] = {val:2d}: {render_array(arr, [idx])}", end="")
        sys.stdout.flush()
        time.sleep(delay)

        if val == target:
            print(f"\n{GREEN}{BOLD}✓ Ditemukan di indeks [{idx}] dalam {steps} perbandingan!{RESET}")
            return idx

    print(f"\n{RED}✗ Target {target} tidak ditemukan setelah {steps} langkah.{RESET}")
    return -1


def binary_search_visual(sorted_arr: List[int], target: int, delay: float = 0.15) -> int:
    """Pencarian Biner: O(log n) waktu pada array yang telah terurut."""
    print(f"\n{BOLD}{MAGENTA}=== Binary Search (Target: {target}) ==={RESET}")
    left = 0
    right = len(sorted_arr) - 1
    steps = 0

    while left <= right:
        steps += 1
        mid = (left + right) // 2
        val = sorted_arr[mid]

        active = list(range(left, right + 1))
        print(f"\nLangkah {steps:2d} | Range [{left}..{right}], Mid [{mid}] = {val}")
        print(f"Jendela Aktif : {render_array(sorted_arr, active_indices=active, pivot_index=mid)}")
        time.sleep(delay)

        if val == target:
            print(f"{GREEN}{BOLD}✓ Ditemukan di indeks [{mid}] dalam {steps} perbandingan (O(log n))!{RESET}")
            return mid
        elif val < target:
            print(f"{YELLOW}  -> {val} < {target}: Buang setengah kiri. Cari ke kanan.{RESET}")
            left = mid + 1
        else:
            print(f"{YELLOW}  -> {val} > {target}: Buang setengah kanan. Cari ke kiri.{RESET}")
            right = mid - 1

    print(f"{RED}✗ Target {target} tidak ditemukan setelah {steps} langkah.{RESET}")
    return -1


def run_benchmark() -> None:
    """Benchmark perbandingan waktu eksekusi antar algoritma sorting."""
    print(f"\n{BOLD}{CYAN}=== Benchmark Algoritma Pengurutan (n = 1.000 elemen acak) ==={RESET}")
    sample_size = 1000
    dataset = [random.randint(1, 10000) for _ in range(sample_size)]

    algorithms = [
        ("Bubble Sort (O(n^2))", lambda d: [
            (d[j], d.__setitem__(j, d[j+1]), d.__setitem__(j+1, d[j])) 
            for i in range(len(d)) for j in range(len(d)-i-1) if d[j] > d[j+1]
        ]),
        ("Python Timsort (Built-in O(n log n))", lambda d: sorted(d)),
    ]

    # Bubble sort sederhana untuk benchmark
    def bench_bubble(arr):
        a = list(arr)
        n = len(a)
        for i in range(n):
            swapped = False
            for j in range(0, n - i - 1):
                if a[j] > a[j + 1]:
                    a[j], a[j + 1] = a[j + 1], a[j]
                    swapped = True
            if not swapped:
                break
        return a

    def bench_quick(arr):
        if len(arr) <= 1:
            return arr
        pivot = arr[len(arr) // 2]
        left = [x for x in arr if x < pivot]
        middle = [x for x in arr if x == pivot]
        right = [x for x in arr if x > pivot]
        return bench_quick(left) + middle + bench_quick(right)

    # 1. Bubble Sort
    t0 = time.perf_counter()
    bench_bubble(dataset[:500])  # gunakan 500 sampel agar cepat
    t_bubble = (time.perf_counter() - t0) * 1000

    # 2. Quick Sort
    t0 = time.perf_counter()
    bench_quick(dataset)
    t_quick = (time.perf_counter() - t0) * 1000

    # 3. Built-in Timsort
    t0 = time.perf_counter()
    sorted(dataset)
    t_timsort = (time.perf_counter() - t0) * 1000

    print(f"\n{BOLD}{'Algoritma':<30} | {'Ukuran Input':<12} | {'Waktu Eksekusi (ms)':<20}{RESET}")
    print("-" * 68)
    print(f"{RED}{'Bubble Sort':<30}{RESET} | {'500 item':<12} | {t_bubble:10.2f} ms")
    print(f"{CYAN}{'Quick Sort (Recursive)':<30}{RESET} | {'1000 item':<12} | {t_quick:10.2f} ms")
    print(f"{GREEN}{'Built-in Timsort':<30}{RESET} | {'1000 item':<12} | {t_timsort:10.2f} ms")
    print("\nAnalisis: Kompleksitas O(n^2) tumbuh eksponensial seiring bertambahnya n.")
    print("O(n log n) mempertahankan performa tinggi bahkan pada ribuan elemen.")


def interactive_menu() -> None:
    """Menu CLI interaktif utama."""
    while True:
        print(f"\n{BOLD}{BG_BLUE}{WHITE}  LAB M01: SIMULASI ALGORITMA PENGURUTAN & PENCARIAN  {RESET}")
        print(f"{CYAN}1.{RESET} Visualisasi Bubble Sort")
        print(f"{CYAN}2.{RESET} Visualisasi Insertion Sort")
        print(f"{CYAN}3.{RESET} Visualisasi Quick Sort")
        print(f"{CYAN}4.{RESET} Komparasi Linear Search vs Binary Search")
        print(f"{CYAN}5.{RESET} Jalankan Benchmark Empiris")
        print(f"{CYAN}6.{RESET} Keluar")
        
        try:
            choice = input(f"\n{YELLOW}Pilih opsi [1-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GREEN}Keluar dari program.{RESET}")
            break

        sample_data = [29, 10, 14, 37, 13, 8, 25, 18]

        if choice == "1":
            print(f"\nData Awal: {sample_data}")
            bubble_sort_visual(sample_data)
        elif choice == "2":
            print(f"\nData Awal: {sample_data}")
            insertion_sort_visual(sample_data)
        elif choice == "3":
            print(f"\nData Awal: {sample_data}")
            arr_copy = list(sample_data)
            stats = {"comparisons": 0, "swaps": 0}
            print(f"\n{BOLD}{CYAN}=== Memulai Quick Sort ==={RESET}")
            quick_sort_visual(arr_copy, 0, len(arr_copy) - 1, stats)
            print(f"\n{GREEN}✓ Selesai! Perbandingan: {stats['comparisons']}, Swaps: {stats['swaps']}{RESET}")
            print(f"Hasil Akhir: {render_array(arr_copy, sorted_indices=list(range(len(arr_copy))))}")
        elif choice == "4":
            sorted_data = sorted(sample_data)
            target = 25
            print(f"Dataset Acak   : {sample_data}")
            print(f"Dataset Terurut: {sorted_data}")
            print(f"Target yang dicari: {BOLD}{YELLOW}{target}{RESET}")
            
            print("\n--- 1. Pencarian Tanpa Terurut (Linear Search) ---")
            linear_search_visual(sample_data, target)
            
            print("\n--- 2. Pencarian Pada Data Terurut (Binary Search) ---")
            binary_search_visual(sorted_data, target)
        elif choice == "5":
            run_benchmark()
        elif choice == "6":
            print(f"{GREEN}Terima kasih telah mempelajari Algoritma Pengurutan & Pencarian!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 1-6.{RESET}")


if __name__ == "__main__":
    try:
        # Jika dijalankan dalam test otomatis (non-interaktif / argumen --demo)
        if len(sys.argv) > 1 and sys.argv[1] == "--demo":
            print(f"{BOLD}Mode Otomatis / Non-interaktif (--demo){RESET}")
            test_arr = [24, 5, 12, 35, 10]
            bubble_sort_visual(test_arr, delay=0.01)
            insertion_sort_visual(test_arr, delay=0.01)
            sorted_arr = sorted(test_arr)
            linear_search_visual(test_arr, 12, delay=0.01)
            binary_search_visual(sorted_arr, 12, delay=0.01)
            run_benchmark()
        else:
            interactive_menu()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interupsi terdeteksi. Sesi dihentikan.{RESET}")
        sys.exit(0)
