#!/usr/bin/env python3
"""
Hands-On Lab: Binary Search & Divide and Conquer Visualizer
BAB-04: Binary Search & Divide and Conquer Core Foundations
Self-contained interactive Python 3 simulation with ANSI terminal styling.
"""

import sys
import time
from typing import List, Tuple, Optional

# ANSI Escape Sequences for terminal styling
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

FG_BLACK = "\033[30m"
FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_MAGENTA = "\033[35m"
FG_CYAN = "\033[36m"
FG_WHITE = "\033[37m"

BG_BLACK = "\033[40m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"
BG_YELLOW = "\033[43m"
BG_MAGENTA = "\033[45m"
BG_CYAN = "\033[46m"


def print_header(title: str) -> None:
    width = 68
    print(f"\n{FG_CYAN}{BOLD}{'=' * width}{RESET}")
    print(f"{FG_YELLOW}{BOLD}{title.center(width)}{RESET}")
    print(f"{FG_CYAN}{BOLD}{'=' * width}{RESET}\n")


def print_step(step_num: int, message: str) -> None:
    print(f"{FG_MAGENTA}{BOLD}[Step {step_num:02d}]{RESET} {FG_WHITE}{message}{RESET}")


def render_array_state(arr: List[int], left: int, mid: Optional[int], right: int, target: Optional[int] = None) -> None:
    """Visualizes array with pointer indicators for Left (L), Mid (M), and Right (R)."""
    indices_str = "Idx : "
    values_str = "Val : "
    ptr_str = "Ptr : "

    for idx, val in enumerate(arr):
        idx_label = f"{idx:3d} "
        val_label = f"{val:3d} "
        
        # Color coding values
        if idx == mid:
            val_formatted = f"{BG_GREEN}{FG_BLACK}{BOLD}{val:3d}{RESET} "
        elif left <= idx <= right:
            val_formatted = f"{BG_BLUE}{FG_WHITE}{BOLD}{val:3d}{RESET} "
        else:
            val_formatted = f"{FG_BLACK}{BOLD}{val:3d}{RESET} "
        
        # Pointer markings
        ptrs = []
        if idx == left:
            ptrs.append("L")
        if idx == mid:
            ptrs.append("M")
        if idx == right:
            ptrs.append("R")
        
        ptr_label = f"{'/'.join(ptrs):^3s} " if ptrs else "    "
        
        indices_str += f"{DIM}{idx_label}{RESET}"
        values_str += val_formatted
        if "M" in ptr_label:
            ptr_str += f"{FG_GREEN}{BOLD}{ptr_label}{RESET}"
        elif "L" in ptr_label or "R" in ptr_label:
            ptr_str += f"{FG_YELLOW}{BOLD}{ptr_label}{RESET}"
        else:
            ptr_str += ptr_label

    print(f"  {indices_str}")
    print(f"  {values_str}")
    print(f"  {ptr_str}")
    if target is not None:
        print(f"  Target: {FG_YELLOW}{BOLD}{target}{RESET} | Range active: [{left} .. {right}]")
    print()


# ----------------------------------------------------------------------
# 1. Classical Binary Search (Exact Match)
# ----------------------------------------------------------------------
def binary_search_exact(arr: List[int], target: int) -> int:
    print_header(f"Binary Search: Exact Match (Target = {target})")
    left, right = 0, len(arr) - 1
    step = 1

    while left <= right:
        mid = left + (right - left) // 2
        print_step(step, f"Evaluating Range: L={left}, R={right} -> Calculated Mid={mid} (Val={arr[mid]})")
        render_array_state(arr, left, mid, right, target)
        
        if arr[mid] == target:
            print(f"  {BG_GREEN}{FG_BLACK}{BOLD} FOUND! {RESET} Target {target} located at index {mid}.")
            return mid
        elif arr[mid] < target:
            print(f"  {FG_CYAN}arr[mid] ({arr[mid]}) < target ({target}) -> Eliminating left half. Left = mid + 1 ({mid + 1}){RESET}\n")
            left = mid + 1
        else:
            print(f"  {FG_CYAN}arr[mid] ({arr[mid]}) > target ({target}) -> Eliminating right half. Right = mid - 1 ({mid - 1}){RESET}\n")
            right = mid - 1
        step += 1

    print(f"  {BG_RED}{FG_WHITE}{BOLD} NOT FOUND {RESET} Target {target} is not in the array.")
    return -1


# ----------------------------------------------------------------------
# 2. Lower Bound (Bisect Left) & Upper Bound (Bisect Right)
# ----------------------------------------------------------------------
def binary_search_lower_bound(arr: List[int], target: int) -> int:
    """Finds the first index where arr[i] >= target (bisect_left)."""
    print_header(f"Binary Search: Lower Bound / bisect_left (First >= {target})")
    left, right = 0, len(arr)
    step = 1

    while left < right:
        mid = left + (right - left) // 2
        print_step(step, f"L={left}, R={right}, Mid={mid} (Val={arr[mid]})")
        render_array_state(arr, left, mid, min(right, len(arr) - 1), target)

        if arr[mid] >= target:
            print(f"  {FG_BLUE}arr[{mid}] >= {target} -> Candidate answer at {mid}. Shrink right: R = {mid}{RESET}\n")
            right = mid
        else:
            print(f"  {FG_YELLOW}arr[{mid}] < {target} -> Target must be to the right. L = {mid + 1}{RESET}\n")
            left = mid + 1
        step += 1

    print(f"  {BG_GREEN}{FG_BLACK}{BOLD} LOWER BOUND RESULT {RESET} Index = {left} (Val = {arr[left] if left < len(arr) else 'Out of Bounds'})\n")
    return left


def binary_search_upper_bound(arr: List[int], target: int) -> int:
    """Finds the first index where arr[i] > target (bisect_right)."""
    print_header(f"Binary Search: Upper Bound / bisect_right (First > {target})")
    left, right = 0, len(arr)
    step = 1

    while left < right:
        mid = left + (right - left) // 2
        print_step(step, f"L={left}, R={right}, Mid={mid} (Val={arr[mid]})")
        render_array_state(arr, left, mid, min(right, len(arr) - 1), target)

        if arr[mid] > target:
            print(f"  {FG_BLUE}arr[{mid}] > {target} -> Candidate boundary at {mid}. Shrink right: R = {mid}{RESET}\n")
            right = mid
        else:
            print(f"  {FG_YELLOW}arr[{mid}] <= {target} -> Target duplicates exist to right. L = {mid + 1}{RESET}\n")
            left = mid + 1
        step += 1

    print(f"  {BG_GREEN}{FG_BLACK}{BOLD} UPPER BOUND RESULT {RESET} Index = {left} (Val = {arr[left] if left < len(arr) else 'Out of Bounds'})\n")
    return left


# ----------------------------------------------------------------------
# 3. Binary Search on Answer Space (Monotonic Predicate)
# Problem: Capacity To Ship Packages Within D Days (LeetCode 1011)
# ----------------------------------------------------------------------
def ship_within_days_simulation(weights: List[int], days: int) -> int:
    print_header(f"Binary Search on Answer: Ship Packages Within {days} Days")
    print(f"Packages: {weights}")
    
    def can_ship(capacity: int) -> Tuple[bool, int]:
        total_days = 1
        current_load = 0
        for w in weights:
            if current_load + w > capacity:
                total_days += 1
                current_load = w
            else:
                current_load += w
        return total_days <= days, total_days

    low = max(weights)
    high = sum(weights)
    print(f"Search Space for Capacity: [{low} (max weight) .. {high} (sum of weights)]\n")

    step = 1
    best_capacity = high

    while low <= high:
        mid = low + (high - low) // 2
        feasible, days_needed = can_ship(mid)
        status_color = FG_GREEN if feasible else FG_RED
        status_str = "FEASIBLE" if feasible else "OVERLOAD (TOO SLOW)"
        
        print_step(step, f"Test Capacity = {BOLD}{mid}{RESET} -> Days Required: {days_needed} (Quota: {days}) => {status_color}{status_str}{RESET}")
        
        if feasible:
            best_capacity = mid
            print(f"    {FG_CYAN}Capacity {mid} works! Try finding a smaller minimal capacity: high = mid - 1 ({mid - 1}){RESET}")
            high = mid - 1
        else:
            print(f"    {FG_YELLOW}Capacity {mid} failed (needs {days_needed} > {days} days). Must increase: low = mid + 1 ({mid + 1}){RESET}")
            low = mid + 1
        step += 1

    print(f"\n  {BG_GREEN}{FG_BLACK}{BOLD} OPTIMAL SHIP CAPACITY {RESET} Minimum Capacity = {FG_YELLOW}{BOLD}{best_capacity}{RESET}\n")
    return best_capacity


# ----------------------------------------------------------------------
# 4. Divide and Conquer: Merge Sort with Execution Tree Trace
# ----------------------------------------------------------------------
def merge_sort_visualizer(arr: List[int], depth: int = 0, side: str = "Root") -> List[int]:
    indent = "  " * depth
    prefix = f"{indent}{FG_MAGENTA}[{side} Depth {depth}]{RESET}"
    
    if len(arr) <= 1:
        print(f"{prefix} Base Case Reached: {FG_CYAN}{arr}{RESET}")
        return arr

    mid = len(arr) // 2
    print(f"{prefix} Divide: {FG_YELLOW}{arr[:mid]}{RESET} | {FG_BLUE}{arr[mid:]}{RESET}")

    left_sorted = merge_sort_visualizer(arr[:mid], depth + 1, "Left")
    right_sorted = merge_sort_visualizer(arr[mid:], depth + 1, "Right")

    # Conquer (Merge step)
    merged = []
    i = j = 0
    while i < len(left_sorted) and j < len(right_sorted):
        if left_sorted[i] <= right_sorted[j]:
            merged.append(left_sorted[i])
            i += 1
        else:
            merged.append(right_sorted[j])
            j += 1
    merged.extend(left_sorted[i:])
    merged.extend(right_sorted[j:])

    print(f"{prefix} {FG_GREEN}Conquer/Merge:{RESET} {FG_YELLOW}{left_sorted}{RESET} + {FG_BLUE}{right_sorted}{RESET} -> {BOLD}{FG_GREEN}{merged}{RESET}")
    return merged


# ----------------------------------------------------------------------
# Interactive CLI Menu
# ----------------------------------------------------------------------
def run_interactive_menu():
    sample_sorted = [2, 5, 8, 12, 16, 23, 23, 23, 38, 56, 72, 91]
    sample_packages = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    sample_unsorted = [38, 27, 43, 3, 9, 82, 10]

    menu = f"""
{FG_CYAN}{BOLD}======================================================================
  BAB-04: BINARY SEARCH & DIVIDE AND CONQUER INTERACTIVE LAB
======================================================================{RESET}
{FG_WHITE}Pilih simulasi fondasi algoritma:{RESET}
  {FG_GREEN}[1]{RESET} Classic Binary Search (Exact Match Visualizer)
  {FG_GREEN}[2]{RESET} Binary Search Lower Bound & Upper Bound (Duplicates Handling)
  {FG_GREEN}[3]{RESET} Binary Search on Answer Space (Capacity to Ship Packages)
  {FG_GREEN}[4]{RESET} Divide & Conquer: Merge Sort Execution Tree Visualizer
  {FG_GREEN}[5]{RESET} Run Full Automated Suite (All Tests sequentially)
  {FG_RED}[0]{RESET} Exit
"""

    while True:
        print(menu)
        try:
            choice = input(f"{FG_YELLOW}Pilihan Anda (0-5) [default 5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not choice:
            choice = "5"

        if choice == "1":
            binary_search_exact(sample_sorted, 23)
            binary_search_exact(sample_sorted, 40)
        elif choice == "2":
            print(f"Sample Array with Duplicates: {sample_sorted}")
            binary_search_lower_bound(sample_sorted, 23)
            binary_search_upper_bound(sample_sorted, 23)
        elif choice == "3":
            ship_within_days_simulation(sample_packages, days=5)
        elif choice == "4":
            print_header("Divide & Conquer: Merge Sort Recursive Trace")
            print(f"Original Array: {sample_unsorted}\n")
            result = merge_sort_visualizer(sample_unsorted)
            print(f"\n{BOLD}{FG_GREEN}Final Sorted Result:{RESET} {result}\n")
        elif choice == "5":
            print_header("RUNNING COMPLETE AUTOMATED LAB SUITE")
            binary_search_exact(sample_sorted, 23)
            binary_search_exact(sample_sorted, 99)
            binary_search_lower_bound(sample_sorted, 23)
            binary_search_upper_bound(sample_sorted, 23)
            ship_within_days_simulation(sample_packages, days=5)
            print_header("Divide & Conquer: Merge Sort Visualizer")
            sorted_res = merge_sort_visualizer(sample_unsorted)
            print(f"\n{BOLD}{FG_GREEN}Sorted Outcome:{RESET} {sorted_res}\n")
            print(f"{BG_GREEN}{FG_BLACK}{BOLD} ALL DEMOS COMPLETED SUCCESSFULLY {RESET}\n")
            break
        elif choice == "0":
            print(f"{FG_CYAN}Terima kasih telah menjalankan simulasi BAB-04.{RESET}")
            break
        else:
            print(f"{FG_RED}Pilihan tidak valid, silakan coba lagi.{RESET}")


if __name__ == "__main__":
    # If arguments are passed (e.g. --all), run suite directly
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        sample_sorted = [2, 5, 8, 12, 16, 23, 23, 23, 38, 56, 72, 91]
        sample_packages = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        sample_unsorted = [38, 27, 43, 3, 9, 82, 10]
        binary_search_exact(sample_sorted, 23)
        binary_search_lower_bound(sample_sorted, 23)
        binary_search_upper_bound(sample_sorted, 23)
        ship_within_days_simulation(sample_packages, 5)
        merge_sort_visualizer(sample_unsorted)
    else:
        run_interactive_menu()
