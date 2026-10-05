#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Kompleksitas & Analisis Algoritma (BAB-01)
Modul: Data Structures & Algorithms Core Foundations

Fitur Utama:
1. Benchmark Empiris vs Teoretis (O(1), O(log n), O(n), O(n log n), O(n^2))
2. Analisis Amortisasi Operasi Dinamis (Resizing Array O(1) amortized vs O(N) worst-case)
3. Space Complexity & Recursion Stack Profiler
4. Visualisasi Interaktif Terminal dengan ANSI Color
"""

import sys
import time
import math
import random

# ==========================================
# Konfigurasi ANSI Terminal Styling
# ==========================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Background accents
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def header_banner(title: str) -> None:
    print(f"\n{Style.CYAN}{Style.BOLD}{'=' * 70}{Style.RESET}")
    print(f"{Style.YELLOW}{Style.BOLD} [SIMULASI] {title.center(56)} {Style.RESET}")
    print(f"{Style.CYAN}{Style.BOLD}{'=' * 70}{Style.RESET}\n")


def print_success(msg: str) -> None:
    print(f"{Style.GREEN}{Style.BOLD}[✓] {msg}{Style.RESET}")


def print_info(msg: str) -> None:
    print(f"{Style.BLUE}[i] {msg}{Style.RESET}")


def print_warning(msg: str) -> None:
    print(f"{Style.YELLOW}[!]{Style.RESET} {msg}")


def print_alert(msg: str) -> None:
    print(f"{Style.RED}{Style.BOLD}[!] {msg}{Style.RESET}")


# ==========================================
# Modul 1: Operasi Pencarian (O(log n) vs O(n))
# ==========================================
def linear_search_profiled(arr: list, target: int) -> tuple:
    comparisons = 0
    start_time = time.perf_counter_ns()
    found_idx = -1
    for i, val in enumerate(arr):
        comparisons += 1
        if val == target:
            found_idx = i
            break
    duration_ns = time.perf_counter_ns() - start_time
    return found_idx, comparisons, duration_ns


def binary_search_profiled(arr: list, target: int) -> tuple:
    comparisons = 0
    start_time = time.perf_counter_ns()
    left, right = 0, len(arr) - 1
    found_idx = -1
    while left <= right:
        comparisons += 1
        mid = (left + right) // 2
        if arr[mid] == target:
            found_idx = mid
            break
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    duration_ns = time.perf_counter_ns() - start_time
    return found_idx, comparisons, duration_ns


def run_search_benchmark() -> None:
    header_banner("Simulasi 1: Linear Search O(n) vs Binary Search O(log n)")
    sizes = [10_000, 100_000, 500_000, 1_000_000]
    
    print(f"{Style.BOLD}{'Ukuran N':<12} | {'Linear Search (Operasi)':<25} | {'Binary Search (Operasi)':<25} | {'Speedup':<10}{Style.RESET}")
    print("-" * 78)
    
    for n in sizes:
        dataset = list(range(n))
        target = n - 1  # Worst-case scenario (elemen paling ujung)
        
        _, lin_ops, lin_time = linear_search_profiled(dataset, target)
        _, bin_ops, bin_time = binary_search_profiled(dataset, target)
        
        speedup = (lin_time / bin_time) if bin_time > 0 else 1.0
        
        print(f"{Style.CYAN}{n:<12,}{Style.RESET} | "
              f"{Style.RED}{lin_ops:<10,} ops ({lin_time/1000:>8.1f} µs){Style.RESET} | "
              f"{Style.GREEN}{bin_ops:<10,} ops ({bin_time/1000:>8.1f} µs){Style.RESET} | "
              f"{Style.YELLOW}{speedup:>7.1f}x{Style.RESET}")
        
    print("\n" + Style.DIM + "Analisis Matematis:" + Style.RESET)
    print(f" • Linear Search Worst-Case : O(N)     -> N langkah jika target di ujung/tidak ada")
    print(f" • Binary Search Worst-Case : O(log₂ N)-> Membagi domain pencarian menjadi separuh")


# ==========================================
# Modul 2: Sorting Growth Rate (O(n²) vs O(n log n))
# ==========================================
def bubble_sort_profiled(arr: list) -> tuple:
    comparisons = 0
    swaps = 0
    a = arr.copy()
    n = len(a)
    start_time = time.perf_counter()
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            comparisons += 1
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swaps += 1
                swapped = True
        if not swapped:
            break
    duration_ms = (time.perf_counter() - start_time) * 1000
    return comparisons, swaps, duration_ms


def merge_sort_profiled(arr: list) -> tuple:
    ops = [0]  # mutable counter
    
    def _merge(left, right):
        result = []
        i = j = 0
        while i < len(left) and j < len(right):
            ops[0] += 1
            if left[i] <= right[j]:
                result.append(left[i])
                i += 1
            else:
                result.append(right[j])
                j += 1
        result.extend(left[i:])
        result.extend(right[j:])
        ops[0] += (len(left) - i) + (len(right) - j)
        return result

    def _divide(lst):
        if len(lst) <= 1:
            return lst
        mid = len(lst) // 2
        left = _divide(lst[:mid])
        right = _divide(lst[mid:])
        return _merge(left, right)

    start_time = time.perf_counter()
    _ = _divide(arr)
    duration_ms = (time.perf_counter() - start_time) * 1000
    return ops[0], duration_ms


def run_sort_benchmark() -> None:
    header_banner("Simulasi 2: Polinomial O(n²) vs Linearitmik O(n log n)")
    sizes = [500, 1000, 2000, 4000]
    
    print(f"{Style.BOLD}{'Ukuran N':<10} | {'Bubble Sort O(n²)':<28} | {'Merge Sort O(n log n)':<28} | {'Rasio Waktu':<12}{Style.RESET}")
    print("-" * 84)
    
    for n in sizes:
        dataset = [random.randint(1, 100_000) for _ in range(n)]
        
        b_comp, _, b_time = bubble_sort_profiled(dataset)
        m_ops, m_time = merge_sort_profiled(dataset)
        
        ratio = (b_time / m_time) if m_time > 0 else 0
        
        print(f"{Style.CYAN}{n:<10}{Style.RESET} | "
              f"{Style.RED}{b_comp:<12,} ({b_time:>7.2f} ms){Style.RESET} | "
              f"{Style.GREEN}{m_ops:<12,} ({m_time:>7.2f} ms){Style.RESET} | "
              f"{Style.MAGENTA}{ratio:>8.1f}x lebih lambat{Style.RESET}")

    print("\n" + Style.DIM + "Observasi Perubahan Skala (N x 2):" + Style.RESET)
    print(f" • Bubble Sort: Jika N naik 2x, operasi naik ~(2)² = 4x lipat.")
    print(f" • Merge Sort : Jika N naik 2x, operasi hanya naik ~2(log 2N) lipat.")


# ==========================================
# Modul 3: Analisis Amortisasi (Dynamic Array)
# ==========================================
class DynamicArraySimulator:
    def __init__(self, growth_factor: float = 2.0):
        self.capacity = 1
        self.size = 0
        self.growth_factor = growth_factor
        self.history = []

    def append(self, item) -> int:
        cost = 1
        is_resized = False
        if self.size == self.capacity:
            old_cap = self.capacity
            self.capacity = int(math.ceil(self.capacity * self.growth_factor))
            cost += self.size  # Copy all existing items
            is_resized = True
        self.size += 1
        self.history.append((self.size, self.capacity, cost, is_resized))
        return cost


def run_amortized_benchmark() -> None:
    header_banner("Simulasi 3: Analisis Amortisasi (Dynamic Array Expansion)")
    sim = DynamicArraySimulator(growth_factor=2.0)
    total_elements = 32
    
    for val in range(1, total_elements + 1):
        sim.append(val)
        
    print(f"{Style.BOLD}{'Operasi #':<10} | {'Size':<6} | {'Kapasitas':<10} | {'Biaya Operasi':<16} | {'Status Amortisasi'}{Style.RESET}")
    print("-" * 72)
    
    total_cost = 0
    for op_id, size, cap, cost, resized in sim.history:
        total_cost += cost
        amortized_avg = total_cost / op_id
        
        if resized:
            status = f"{Style.RED}RESIZE! Copying {cost - 1} elements (O(N) Spike){Style.RESET}"
            cost_str = f"{Style.RED}{cost:>3} unit{Style.RESET}"
        else:
            status = f"{Style.GREEN}Normal insert (O(1)){Style.RESET}"
            cost_str = f"{Style.GREEN}{cost:>3} unit{Style.RESET}"
            
        print(f"{op_id:<10} | {size:<6} | {cap:<10} | {cost_str:<25} | {status}")
        
    print("-" * 72)
    print_success(f"Total Operasi Nyata  : {total_cost} unit kalkulasi")
    print_success(f"Biaya Rata-Rata/Item : {total_cost / total_elements:.2f} unit (Terbukti O(1) Teramortisasi)")
    print_info("Kesimpulan: Walau ekspansi memakan O(N), frekuensinya meluruh secara geometrik.")


# ==========================================
# Modul 4: Kompleksitas Ruang & Call Stack
# ==========================================
def run_space_benchmark() -> None:
    header_banner("Simulasi 4: Space Complexity & Recursion Stack Overhead")
    
    depths = [100, 300, 500, 800]
    
    def recursive_factorial_call(n: int, current_depth: int = 1) -> int:
        if n <= 1:
            return 1
        return n * recursive_factorial_call(n - 1, current_depth + 1)
    
    def iterative_factorial(n: int) -> int:
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result

    print(f"{Style.BOLD}{'Input N':<10} | {'Iteratif Stack':<18} | {'Rekursif Stack':<22} | {'Space Complexity'}{Style.RESET}")
    print("-" * 75)
    
    for d in depths:
        # Rekursif memakan O(N) frames pada call stack
        iter_frames = 1
        rec_frames = d
        print(f"{Style.CYAN}{d:<10}{Style.RESET} | "
              f"{Style.GREEN}{iter_frames} call frame (O(1)){Style.RESET} | "
              f"{Style.RED}{rec_frames} call frames (O(N)){Style.RESET}   | "
              f"{Style.YELLOW}Potential StackOverflow jika N >> sys.recursionlimit{Style.RESET}")
              
    print("\n" + Style.DIM + "Peringatan Arsitektur:" + Style.RESET)
    print(" • Space complexity O(N) rekursif beresiko melebihi batas thread stack memori.")
    print(" • Pendekatan dynamic programming/iteratif mereduksi overhead stack menjadi O(1).")


# ==========================================
# Main Menu & Interactive CLI Controller
# ==========================================
def display_menu() -> None:
    print(f"\n{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} [MENU LABORATORIUM STRUKTUR DATA & ALGORITMA] {Style.RESET}")
    print(f"{Style.CYAN}1.{Style.RESET} Benchmark Pencarian: O(N) Linear vs O(log N) Binary Search")
    print(f"{Style.CYAN}2.{Style.RESET} Benchmark Pengurutan: O(N²) Bubble vs O(N log N) Merge Sort")
    print(f"{Style.CYAN}3.{Style.RESET} Simulasi Analisis Amortisasi Dynamic Array Resizing")
    print(f"{Style.CYAN}4.{Style.RESET} Profiling Space Complexity & Call Stack Recursion")
    print(f"{Style.CYAN}5.{Style.RESET} Eksekusi Seluruh Skenario Pengujian")
    print(f"{Style.RED}0.{Style.RESET} Keluar (Exit)")


def main():
    while True:
        display_menu()
        try:
            choice = input(f"\n{Style.BOLD}Pilih opsi [0-5]: {Style.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n" + Style.YELLOW + "Proses dibatalkan pengguna. Keluar..." + Style.RESET)
            break
            
        if choice == '1':
            run_search_benchmark()
        elif choice == '2':
            run_sort_benchmark()
        elif choice == '3':
            run_amortized_benchmark()
        elif choice == '4':
            run_space_benchmark()
        elif choice == '5':
            run_search_benchmark()
            run_sort_benchmark()
            run_amortized_benchmark()
            run_space_benchmark()
            print_success("Seluruh simulasi fondasi algoritma berhasil diselesaikan.")
        elif choice == '0':
            print(f"{Style.GREEN}Sesi laboratorium selesai. Terima kasih.{Style.RESET}")
            sys.exit(0)
        else:
            print_warning("Pilihan tidak valid! Silakan masukkan angka 0 sampai 5.")


if __name__ == "__main__":
    # Verifikasi langsung jika dipanggil dengan argument non-interaktif
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        run_search_benchmark()
        run_sort_benchmark()
        run_amortized_benchmark()
        run_space_benchmark()
    else:
        main()
