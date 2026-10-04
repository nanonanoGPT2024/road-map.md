#!/usr/bin/env python3
"""
Lab Exercise M01: Fondasi Dua Pointer & Sliding Window
Materi: BAB-02 Two Pointers dan Sliding Window
Karakteristik: Runnable mandiri, interaktif, visualisasi ANSI terminal color.
"""

import sys
import time
from typing import List, Tuple, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

BG_CYAN = "\033[46;30m"
BG_MAGENTA = "\033[45;30m"
BG_GREEN = "\033[42;30m"
BG_YELLOW = "\033[43;30m"


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def print_banner(title: str, subtitle: str = "") -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{WHITE}  {title.center(61)}{RESET}")
    if subtitle:
        print(f"{DIM}{YELLOW}  {subtitle.center(61)}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")


def format_array_two_pointers(arr: List[int], left: int, right: int) -> str:
    """Format array dengan penanda warna untuk pointer Left dan Right."""
    cells = []
    for i, val in enumerate(arr):
        if i == left and i == right:
            cells.append(f"{BG_MAGENTA}[{val:2d}]{RESET}")
        elif i == left:
            cells.append(f"{BG_CYAN}[{val:2d}]{RESET}")
        elif i == right:
            cells.append(f"{BG_YELLOW}[{val:2d}]{RESET}")
        else:
            cells.append(f"{WHITE} {val:2d} {RESET}")
    arr_str = " ".join(cells)

    # Pointer labels below
    pointers = []
    for i in range(len(arr)):
        if i == left and i == right:
            pointers.append(f"{MAGENTA} L&R {RESET}")
        elif i == left:
            pointers.append(f"{CYAN}  L  {RESET}")
        elif i == right:
            pointers.append(f"{YELLOW}  R  {RESET}")
        else:
            pointers.append("     ")
    ptr_str = "".join(pointers)

    return f"  Array: {arr_str}\n  Index: {ptr_str}"


def format_array_sliding_window(arr: List[int], start: int, end: int) -> str:
    """Format array dengan penanda rentang jendela geser [start .. end]."""
    cells = []
    for i, val in enumerate(arr):
        if start <= i <= end:
            cells.append(f"{BG_GREEN}[{val:2d}]{RESET}")
        else:
            cells.append(f"{WHITE} {val:2d} {RESET}")
    arr_str = " ".join(cells)

    indicators = []
    for i in range(len(arr)):
        if i == start and i == end:
            indicators.append(f"{GREEN} S=E {RESET}")
        elif i == start:
            indicators.append(f"{CYAN}  S  {RESET}")
        elif i == end:
            indicators.append(f"{YELLOW}  E  {RESET}")
        elif start < i < end:
            indicators.append(f"{GREEN} --- {RESET}")
        else:
            indicators.append("     ")
    ind_str = "".join(indicators)

    return f"  Array : {arr_str}\n  Window: {ind_str}"


def simulate_two_sum_sorted(numbers: List[int], target: int, delay: float = 0.8) -> Optional[Tuple[int, int]]:
    """Simulasi visual Two Pointers: Two Sum II (Sorted Array)."""
    print_banner("SIMULASI 1: TWO POINTERS (TWO SUM II)", f"Target = {target}")
    left = 0
    right = len(numbers) - 1
    step = 1

    while left < right:
        curr_sum = numbers[left] + numbers[right]
        clear_screen()
        print_banner("SIMULASI 1: TWO POINTERS (TWO SUM II)", f"Target = {target}")
        print(f"{BOLD}{MAGENTA}[Langkah {step}]{RESET}")
        print(format_array_two_pointers(numbers, left, right))
        print(f"\n  Pointer L: idx={left} (nilai={numbers[left]}) | Pointer R: idx={right} (nilai={numbers[right]})")
        print(f"  Hitungan: {numbers[left]} + {numbers[right]} = {BOLD}{curr_sum}{RESET}")

        if curr_sum == target:
            print(f"\n  {BG_GREEN}{BOLD} DITEMUKAN TARGET! {RESET} Nilai {numbers[left]} + {numbers[right]} == {target}")
            print(f"  Indeks 1-based: ({left + 1}, {right + 1})\n")
            return (left + 1, right + 1)
        elif curr_sum < target:
            print(f"  {YELLOW}Evaluasi:{RESET} {curr_sum} < {target} -> Jumlah terlalu KECIL, geser Left ke KANAN (L++)")
            left += 1
        else:
            print(f"  {YELLOW}Evaluasi:{RESET} {curr_sum} > {target} -> Jumlah terlalu BESAR, geser Right ke KIRI (R--)")
            right -= 1

        step += 1
        time.sleep(delay)

    print(f"\n  {RED}{BOLD}TIDAK DITEMUKAN PASANGAN DENGAN TARGET {target}!{RESET}\n")
    return None


def simulate_max_water_container(heights: List[int], delay: float = 0.8) -> int:
    """Simulasi Two Pointers: Container With Most Water."""
    print_banner("SIMULASI 2: CONTAINER WITH MOST WATER", "Maksimalkan Volume Air (min(h[L], h[R]) * lebar)")
    left = 0
    right = len(heights) - 1
    max_area = 0
    best_pair = (0, 0)
    step = 1

    while left < right:
        width = right - left
        h = min(heights[left], heights[right])
        area = width * h

        clear_screen()
        print_banner("SIMULASI 2: CONTAINER WITH MOST WATER", f"Rekor Volume Tertinggi Saat Ini: {max_area}")
        print(f"{BOLD}{MAGENTA}[Langkah {step}]{RESET}")
        print(format_array_two_pointers(heights, left, right))
        print(f"\n  Lebar (R - L) = {right} - {left} = {width}")
        print(f"  Tinggi Efektif = min({heights[left]}, {heights[right]}) = {h}")
        print(f"  Volume Saat Ini = {width} x {h} = {BOLD}{area}{RESET}")

        if area > max_area:
            max_area = area
            best_pair = (left, right)
            print(f"  {GREEN}{BOLD}★ Rekor Baru! Area meningkat menjadi {max_area}{RESET}")

        if heights[left] < heights[right]:
            print(f"  {CYAN}Aksi:{RESET} Tinggi kiri ({heights[left]}) < kanan ({heights[right]}). Geser L ke kanan.")
            left += 1
        else:
            print(f"  {YELLOW}Aksi:{RESET} Tinggi kanan ({heights[right]}) <= kiri ({heights[left]}). Geser R ke kiri.")
            right -= 1

        step += 1
        time.sleep(delay)

    print(f"\n  {BG_GREEN}{BOLD} HASIL AKHIR: {RESET} Area Maksimum = {BOLD}{max_area}{RESET} pada indeks {best_pair}\n")
    return max_area


def simulate_fixed_sliding_window(nums: List[int], k: int, delay: float = 0.8) -> int:
    """Simulasi Fixed Size Sliding Window: Max Sum Subarray of Size K."""
    print_banner("SIMULASI 3: FIXED SLIDING WINDOW", f"Maksimum Jumlah Subarray Ukuran K = {k}")
    if len(nums) < k:
        print(f"{RED}Panjang array ({len(nums)}) lebih kecil dari k ({k})!{RESET}")
        return 0

    # Inisialisasi jendela pertama
    window_sum = sum(nums[:k])
    max_sum = window_sum
    best_range = (0, k - 1)

    clear_screen()
    print_banner("SIMULASI 3: FIXED SLIDING WINDOW", f"Ukuran Jendela K = {k}")
    print(f"{BOLD}{MAGENTA}[Inisialisasi Jendela Pertama (0 s/d {k-1})]{RESET}")
    print(format_array_sliding_window(nums, 0, k - 1))
    print(f"\n  Jumlah Elemen Jendela Awal = {BOLD}{window_sum}{RESET}")
    time.sleep(delay)

    # Geser jendela
    for i in range(k, len(nums)):
        outgoing = nums[i - k]
        incoming = nums[i]
        window_sum = window_sum - outgoing + incoming

        clear_screen()
        print_banner("SIMULASI 3: FIXED SLIDING WINDOW", f"Max Sum Sementara: {max_sum}")
        print(f"{BOLD}{MAGENTA}[Geser ke Indeks {i - k + 1} .. {i}]{RESET}")
        print(format_array_sliding_window(nums, i - k + 1, i))
        print(f"\n  Elemen Keluar: {RED}-{outgoing}{RESET} (idx {i-k})")
        print(f"  Elemen Masuk : {GREEN}+{incoming}{RESET} (idx {i})")
        print(f"  Jumlah Baru  : {BOLD}{window_sum}{RESET}")

        if window_sum > max_sum:
            max_sum = window_sum
            best_range = (i - k + 1, i)
            print(f"  {GREEN}{BOLD}★ Rekor Baru! Max Sum menjadi {max_sum}{RESET}")

        time.sleep(delay)

    print(f"\n  {BG_GREEN}{BOLD} SELESAI: {RESET} Max Sum Subarray = {BOLD}{max_sum}{RESET} rentang {best_range}\n")
    return max_sum


def simulate_dynamic_sliding_window(nums: List[int], target: int, delay: float = 0.8) -> int:
    """Simulasi Dynamic Sliding Window: Minimum Size Subarray Sum (sum >= target)."""
    print_banner("SIMULASI 4: DYNAMIC SLIDING WINDOW", f"Cari Panjang Subarray Terpendek dengan Sum >= {target}")
    min_len = float("inf")
    curr_sum = 0
    start = 0
    step = 1

    for end in range(len(nums)):
        curr_sum += nums[end]

        clear_screen()
        print_banner("SIMULASI 4: DYNAMIC SLIDING WINDOW", f"Target Sum >= {target} | Min Panjang Saat Ini: {min_len if min_len != float('inf') else 'N/A'}")
        print(f"{BOLD}{MAGENTA}[Langkah {step} - Ekspansi Jendela (End = {end})]{RESET}")
        print(format_array_sliding_window(nums, start, end))
        print(f"\n  Menambahkan nums[{end}] = {nums[end]}. Total Sum = {BOLD}{curr_sum}{RESET}")

        while curr_sum >= target:
            window_len = end - start + 1
            if window_len < min_len:
                min_len = window_len
                print(f"  {GREEN}{BOLD}✓ Target Terpenuhi! Panjang Jendela = {window_len} (Baru Terpendek){RESET}")

            time.sleep(delay)
            # Ciutkan jendela dari kiri
            curr_sum -= nums[start]
            print(f"  {YELLOW}Penyusutan Jendela: Buang nums[{start}] = {nums[start]}. Sisa Sum = {curr_sum}{RESET}")
            start += 1
            if start <= end:
                print(format_array_sliding_window(nums, start, end))

        step += 1
        time.sleep(delay)

    result = 0 if min_len == float("inf") else int(min_len)
    print(f"\n  {BG_GREEN}{BOLD} HASIL AKHIR: {RESET} Panjang Minimum Subarray = {BOLD}{result}{RESET}\n")
    return result


def run_automated_tests() -> None:
    """Menjalankan unit test internal untuk memverifikasi kebenaran algoritma."""
    print_banner("MENJALANKAN SUITE VALIDASI OTOMATIS", "Memverifikasi Algoritma Inti")
    
    # Test 1: Two Sum Sorted
    t1 = [2, 7, 11, 15]
    ans1 = simulate_two_sum_sorted(t1, 9, delay=0.0)
    assert ans1 == (1, 2), f"Expected (1, 2), got {ans1}"
    print(f"  [{GREEN}PASS{RESET}] Two Sum II Test 1 (Target 9) -> Output: {ans1}")

    # Test 2: Container With Most Water
    t2 = [1, 8, 6, 2, 5, 4, 8, 3, 7]
    ans2 = simulate_max_water_container(t2, delay=0.0)
    assert ans2 == 49, f"Expected 49, got {ans2}"
    print(f"  [{GREEN}PASS{RESET}] Container Most Water Test 2 -> Max Area: {ans2}")

    # Test 3: Fixed Sliding Window
    t3 = [2, 1, 5, 1, 3, 2]
    ans3 = simulate_fixed_sliding_window(t3, 3, delay=0.0)
    assert ans3 == 9, f"Expected 9, got {ans3}"
    print(f"  [{GREEN}PASS{RESET}] Fixed Sliding Window Test 3 (K=3) -> Max Sum: {ans3}")

    # Test 4: Dynamic Sliding Window
    t4 = [2, 3, 1, 2, 4, 3]
    ans4 = simulate_dynamic_sliding_window(t4, 7, delay=0.0)
    assert ans4 == 2, f"Expected 2, got {ans4}"
    print(f"  [{GREEN}PASS{RESET}] Dynamic Sliding Window Test 4 (Target 7) -> Min Len: {ans4}")

    print(f"\n{BOLD}{GREEN}Semua 4 Test Kasus Berhasil Lolos 100%!{RESET}\n")


def interactive_menu() -> None:
    """Menu CLI interaktif untuk navigasi pembelajaran."""
    while True:
        clear_screen()
        print_banner("LAB INTERAKTIF: TWO POINTERS & SLIDING WINDOW", "LeetCode Algorithmic Foundation Simulator")
        print(f"  {BOLD}[1]{RESET} Simulasi Two Pointers (Two Sum II Sorted)")
        print(f"  {BOLD}[2]{RESET} Simulasi Two Pointers (Container With Most Water)")
        print(f"  {BOLD}[3]{RESET} Simulasi Fixed Sliding Window (Max Sum Subarray Size K)")
        print(f"  {BOLD}[4]{RESET} Simulasi Dynamic Sliding Window (Min Size Subarray Sum)")
        print(f"  {BOLD}[5]{RESET} Jalankan Otomasi Test Verifikasi (Tanpa Delay)")
        print(f"  {BOLD}[0]{RESET} Keluar (Exit)")
        print(f"\n{CYAN}{'-' * 65}{RESET}")

        try:
            choice = input(f"{BOLD}Pilih menu [0-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            nums = [2, 3, 5, 8, 11, 15, 20]
            simulate_two_sum_sorted(nums, target=19, delay=1.0)
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        elif choice == "2":
            heights = [1, 8, 6, 2, 5, 4, 8, 3, 7]
            simulate_max_water_container(heights, delay=0.9)
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        elif choice == "3":
            nums = [2, 1, 5, 1, 3, 2, 9, 4, 1]
            simulate_fixed_sliding_window(nums, k=3, delay=0.8)
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        elif choice == "4":
            nums = [2, 3, 1, 2, 4, 3, 7]
            simulate_dynamic_sliding_window(nums, target=7, delay=0.8)
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        elif choice == "5":
            run_automated_tests()
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah belajar fondasi Two Pointers & Sliding Window!{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan ulangi.{RESET}")
            time.sleep(1.0)


if __name__ == "__main__":
    # Jika dipanggil dengan flag --test, jalankan test mode non-interaktif
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_automated_tests()
    else:
        interactive_menu()
