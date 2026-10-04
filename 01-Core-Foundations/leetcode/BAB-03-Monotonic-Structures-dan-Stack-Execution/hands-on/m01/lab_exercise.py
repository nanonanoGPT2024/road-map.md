#!/usr/bin/env python3
"""
BAB-03: Monotonic Structures & Stack Execution
Interactive Hands-On Lab Exercise (Module 01)

Simulasi visual dan interaktif algoritma berbasis Monotonic Stack:
1. Next Greater Element (NGE) - Monotonic Decreasing Stack
2. Daily Temperatures - Monotonic Decreasing Index Stack
3. Largest Rectangle in Histogram - Monotonic Increasing Stack Boundary Detection
"""

import sys
import time
from typing import List, Tuple, Optional

# ANSI Color Codes for Terminal Output
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"
CLR_BG_DARK = "\033[40m"


def header(title: str) -> None:
    border = "=" * 65
    print(f"\n{CLR_CYAN}{CLR_BOLD}{border}{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}  >>> {title.upper()} <<<{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}{border}{CLR_RESET}\n")


def print_stack_state(stack: list, action_desc: str, current_val: any) -> None:
    stack_repr = " | ".join(str(x) for x in stack)
    stack_visual = f"[{stack_repr}]" if stack else "[] (KOSONG)"
    print(
        f"  {CLR_YELLOW}Action:{CLR_RESET} {action_desc:<28} "
        f"| {CLR_BLUE}Current:{CLR_RESET} {str(current_val):<4} "
        f"| {CLR_MAGENTA}Stack State:{CLR_RESET} {CLR_BOLD}{stack_visual}{CLR_RESET}"
    )


# =====================================================================
# 1. NEXT GREATER ELEMENT (NGE)
# =====================================================================
def run_next_greater_element(nums: List[int], delay: float = 0.05) -> List[int]:
    """
    Menemukan elemen lebih besar pertama di sebelah kanan setiap elemen.
    Menggunakan Monotonic Decreasing Stack menyimpan indeks elemen.
    Time Complexity: O(N) amortized
    Space Complexity: O(N)
    """
    header("Simulasi: Next Greater Element (Monotonic Decreasing Stack)")
    print(f"{CLR_BOLD}Input Array:{CLR_RESET} {nums}\n")
    
    n = len(nums)
    result = [-1] * n
    stack: List[int] = []  # Stack menyimpan indeks

    print(f"{CLR_BOLD}{'Langkah':<8} {'Idx':<5} {'Elemen':<8} {'Operasi Stack / Resolusi Target':<40}{CLR_RESET}")
    print("-" * 65)

    step = 1
    for i in range(n):
        curr = nums[i]
        # Invarian Monotonic: Elemen di stack harus monotonically decreasing.
        # Jika curr > nums[stack[-1]], pop stack dan resolve result untuk elemen tersebut!
        while stack and nums[stack[-1]] < curr:
            top_idx = stack.pop()
            result[top_idx] = curr
            print(
                f"{step:<8} {i:<5} {curr:<8} "
                f"{CLR_GREEN}POP idx {top_idx} ({nums[top_idx]}) -> NGE adalah {curr}{CLR_RESET}"
            )
            step += 1
            if delay > 0:
                time.sleep(delay)

        stack.append(i)
        print_stack_state([nums[idx] for idx in stack], f"PUSH idx {i} ({curr})", curr)
        step += 1
        if delay > 0:
            time.sleep(delay)

    # Elemen yang tersisa di stack tidak memiliki NGE (tetap -1)
    while stack:
        rem_idx = stack.pop()
        print(f"{step:<8} {'-':<5} {'-':<8} {CLR_RED}Sisa stack idx {rem_idx} ({nums[rem_idx]}) -> NGE = -1{CLR_RESET}")
        step += 1

    print("-" * 65)
    print(f"\n{CLR_GREEN}{CLR_BOLD}Hasil NGE Array:{CLR_RESET} {result}\n")
    return result


# =====================================================================
# 2. DAILY TEMPERATURES (LeetCode 739)
# =====================================================================
def run_daily_temperatures(temperatures: List[int], delay: float = 0.05) -> List[int]:
    """
    Menghitung jumlah hari yang harus ditunggu hingga suhu lebih hangat.
    """
    header("Simulasi: Daily Temperatures (LeetCode 739)")
    print(f"{CLR_BOLD}Input Suhu:{CLR_RESET} {temperatures}\n")

    n = len(temperatures)
    days_to_wait = [0] * n
    stack: List[int] = []  # Menyimpan indeks hari

    for i, temp in enumerate(temperatures):
        print(f"\n{CLR_BOLD}--- Hari ke-{i}: Suhu = {temp}°C ---{CLR_RESET}")
        while stack and temperatures[stack[-1]] < temp:
            prev_day = stack.pop()
            diff = i - prev_day
            days_to_wait[prev_day] = diff
            print(
                f"  {CLR_GREEN}✓ Hari ke-{prev_day} ({temperatures[prev_day]}°C) "
                f"menemukan hari lebih hangat pada hari ke-{i} ({temp}°C)! "
                f"Tunggu {diff} hari.{CLR_RESET}"
            )
            if delay > 0:
                time.sleep(delay)

        stack.append(i)
        print_stack_state([temperatures[idx] for idx in stack], f"PUSH hari {i}", f"{temp}°C")
        if delay > 0:
            time.sleep(delay)

    print("\n" + "=" * 65)
    print(f"{CLR_GREEN}{CLR_BOLD}Array Hari Menunggu:{CLR_RESET} {days_to_wait}\n")
    return days_to_wait


# =====================================================================
# 3. LARGEST RECTANGLE IN HISTOGRAM (LeetCode 84)
# =====================================================================
def run_largest_rectangle(heights: List[int], delay: float = 0.05) -> int:
    """
    Mencari area persegi panjang terbesar pada histogram.
    Monotonic Increasing Stack digunakan untuk mendeteksi batas kiri dan kanan.
    """
    header("Simulasi: Largest Rectangle in Histogram (LeetCode 84)")
    print(f"{CLR_BOLD}Histogram Heights:{CLR_RESET} {heights}\n")

    extended_heights = heights + [0]  # Dummy height 0 di akhir untuk flush stack
    stack: List[int] = []  # Stack menyimpan indeks
    max_area = 0
    best_rect: Tuple[int, int, int] = (0, 0, 0)  # (area, width, height)

    for i, h in enumerate(extended_heights):
        bar_label = f"{h}" if i < len(heights) else "0 (Sentinel)"
        print(f"\n{CLR_BOLD}Memeriksa Index {i} [Tinggi: {bar_label}]:{CLR_RESET}")

        while stack and extended_heights[stack[-1]] > h:
            popped_idx = stack.pop()
            popped_h = extended_heights[popped_idx]
            # Lebar dihitung antara batas kiri (elemen teratas stack setelah pop) dan batas kanan (i)
            width = i if not stack else i - stack[-1] - 1
            area = popped_h * width

            print(
                f"  {CLR_YELLOW}HITUNG AREA:{CLR_RESET} Height={popped_h}, "
                f"LeftBoundIdx={stack[-1] if stack else -1}, RightBoundIdx={i}, "
                f"Width={width} -> {CLR_CYAN}Area = {area}{CLR_RESET}"
            )

            if area > max_area:
                max_area = area
                best_rect = (area, width, popped_h)
                print(f"  {CLR_GREEN}{CLR_BOLD}★ REKOR MAKSIMUM BARU DITEMUKAN: {max_area}{CLR_RESET}")

            if delay > 0:
                time.sleep(delay)

        stack.append(i)
        print_stack_state(
            [extended_heights[idx] for idx in stack],
            f"PUSH idx {i} (h={h})",
            h
        )
        if delay > 0:
            time.sleep(delay)

    print("\n" + "=" * 65)
    print(
        f"{CLR_GREEN}{CLR_BOLD}Hasil Area Terbesar:{CLR_RESET} {max_area} "
        f"(Tinggi: {best_rect[2]}, Lebar: {best_rect[1]})\n"
    )
    return max_area


# =====================================================================
# UNIT VERIFICATION & INTERACTIVE RUNNER
# =====================================================================
def run_verification_tests() -> None:
    print(f"{CLR_CYAN}Menjalankan uji verifikasi otomatis (Sanity Checks)...{CLR_RESET}")
    # 1. NGE Tests
    assert run_next_greater_element([2, 1, 2, 4, 3], delay=0.0) == [4, 2, 4, -1, -1]
    assert run_next_greater_element([4, 3, 2, 1], delay=0.0) == [-1, -1, -1, -1]
    
    # 2. Daily Temperatures Tests
    assert run_daily_temperatures([73, 74, 75, 71, 69, 72, 76, 73], delay=0.0) == [1, 1, 4, 2, 1, 1, 0, 0]
    
    # 3. Largest Rectangle Tests
    assert run_largest_rectangle([2, 1, 5, 6, 2, 3], delay=0.0) == 10
    assert run_largest_rectangle([2, 4], delay=0.0) == 4
    
    print(f"{CLR_GREEN}{CLR_BOLD}Semua verifikasi algoritma monotonic stack 100% SUKSES!{CLR_RESET}\n")


def display_menu() -> None:
    print(f"{CLR_BOLD}=== PILIHAN SIMULASI INTERAKTIF MONOTONIC STRUCTURES ==={CLR_RESET}")
    print("1. Next Greater Element (NGE) Visualizer")
    print("2. Daily Temperatures (LC 739) Step-by-Step")
    print("3. Largest Rectangle in Histogram (LC 84) Boundary Explorer")
    print("4. Jalankan Semua Simulasi (Demo Mode)")
    print("5. Run Automated Unit Tests (Verify All)")
    print("0. Keluar")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--verify"):
        run_verification_tests()
        sys.exit(0)

    while True:
        display_menu()
        try:
            choice = input(f"\n{CLR_YELLOW}Pilih opsi [0-5]: {CLR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSelesai.")
            break

        if choice == "1":
            raw_input = input("Masukkan array angka dipisah spasi (default: 2 1 2 4 3): ").strip()
            arr = [int(x) for x in raw_input.split()] if raw_input else [2, 1, 2, 4, 3]
            run_next_greater_element(arr, delay=0.05)
        elif choice == "2":
            raw_input = input("Masukkan suhu harian dipisah spasi (default: 73 74 75 71 69 72 76 73): ").strip()
            temps = [int(x) for x in raw_input.split()] if raw_input else [73, 74, 75, 71, 69, 72, 76, 73]
            run_daily_temperatures(temps, delay=0.05)
        elif choice == "3":
            raw_input = input("Masukkan tinggi balok histogram (default: 2 1 5 6 2 3): ").strip()
            bars = [int(x) for x in raw_input.split()] if raw_input else [2, 1, 5, 6, 2, 3]
            run_largest_rectangle(bars, delay=0.05)
        elif choice == "4":
            run_next_greater_element([2, 1, 2, 4, 3], delay=0.02)
            run_daily_temperatures([73, 74, 75, 71, 69, 72, 76, 73], delay=0.02)
            run_largest_rectangle([2, 1, 5, 6, 2, 3], delay=0.02)
        elif choice == "5":
            run_verification_tests()
        elif choice == "0":
            print(f"{CLR_CYAN}Keluar dari lab. Selamat belajar!{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid, silakan coba lagi.{CLR_RESET}")


if __name__ == "__main__":
    main()
