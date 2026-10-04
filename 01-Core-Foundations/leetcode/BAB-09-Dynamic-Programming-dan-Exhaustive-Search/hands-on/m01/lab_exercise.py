#!/usr/bin/env python3
"""
BAB-09: Dynamic Programming & Exhaustive Search Interactive Lab
Simulasi visual perbandingan:
1. Brute Force (Exhaustive Search / Recursion)
2. Top-Down DP (Memoization)
3. Bottom-Up DP (Tabulation)
Masalah: Coin Change & 0/1 Knapsack
"""

import sys
import time
from typing import Dict, List, Tuple

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
RESET = "\033[0m"


class RecursionTracker:
    def __init__(self):
        self.call_count = 0
        self.cache_hits = 0

    def reset(self):
        self.call_count = 0
        self.cache_hits = 0


tracker = RecursionTracker()


def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{YELLOW} [LAB BAB-09] {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")


# -------------------------------------------------------------
# 1. COIN CHANGE PROBLEM: Exhaustive vs Memoization vs Tabulation
# -------------------------------------------------------------

def coin_change_recursive(coins: List[int], amount: int, depth: int = 0) -> int:
    tracker.call_count += 1
    indent = "  " * depth
    if depth <= 3:
        print(f"{indent}{RED}→ Call coin_change({amount}){RESET}")

    if amount == 0:
        return 0
    if amount < 0:
        return float('inf')

    min_coins = float('inf')
    for coin in coins:
        res = coin_change_recursive(coins, amount - coin, depth + 1)
        if res != float('inf'):
            min_coins = min(min_coins, res + 1)

    return min_coins


def coin_change_memo(coins: List[int], amount: int, memo: Dict[int, int] = None, depth: int = 0) -> int:
    if memo is None:
        memo = {}
    tracker.call_count += 1

    if amount in memo:
        tracker.cache_hits += 1
        return memo[amount]

    indent = "  " * depth
    if depth <= 3:
        print(f"{indent}{GREEN}→ Memoize coin_change({amount}){RESET}")

    if amount == 0:
        return 0
    if amount < 0:
        return float('inf')

    min_coins = float('inf')
    for coin in coins:
        res = coin_change_memo(coins, amount - coin, memo, depth + 1)
        if res != float('inf'):
            min_coins = min(min_coins, res + 1)

    memo[amount] = min_coins
    return min_coins


def coin_change_tabulation(coins: List[int], amount: int) -> Tuple[int, List[int]]:
    dp = [float('inf')] * (amount + 1)
    parent = [-1] * (amount + 1)
    dp[0] = 0

    print(f"\n{MAGENTA}[TABULATION TABLE INITIALIZATION]{RESET}")
    print(f"Index : " + " ".join(f"{i:4}" for i in range(min(amount + 1, 15))))
    print(f"Values: " + " ".join(f"{'0' if i==0 else '∞':4}" for i in range(min(amount + 1, 15))))

    for i in range(1, amount + 1):
        for coin in coins:
            if i - coin >= 0 and dp[i - coin] + 1 < dp[i]:
                dp[i] = dp[i - coin] + 1
                parent[i] = coin

    # Backtrack path
    path = []
    curr = amount
    if dp[amount] != float('inf'):
        while curr > 0:
            coin_used = parent[curr]
            path.append(coin_used)
            curr -= coin_used

    return dp[amount], path


# -------------------------------------------------------------
# 2. 0/1 KNAPSACK PROBLEM
# -------------------------------------------------------------

def knapsack_tabulation(weights: List[int], values: List[int], capacity: int):
    n = len(weights)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        w = weights[i - 1]
        v = values[i - 1]
        for c in range(1, capacity + 1):
            if w <= c:
                dp[i][c] = max(dp[i - 1][c], dp[i - 1][c - w] + v)
            else:
                dp[i][c] = dp[i - 1][c]

    # Print DP Matrix
    print(f"\n{BOLD}{CYAN}Matriks DP Knapsack 2D (Baris: Item, Kolom: Kapasitas 0..{capacity}){RESET}")
    header_col = "Item \\ Cap |" + "".join(f"{c:4}" for c in range(capacity + 1))
    print(header_col)
    print("-" * len(header_col))
    for i in range(n + 1):
        item_label = f"Item {i:2}    |" if i > 0 else "Base (0)   |"
        row_str = "".join(f"{dp[i][c]:4}" for c in range(capacity + 1))
        print(f"{YELLOW}{item_label}{RESET}{row_str}")

    return dp[n][capacity]


# -------------------------------------------------------------
# 3. INTERACTIVE RUNNER & BENCHMARK
# -------------------------------------------------------------

def run_coin_change_simulation():
    print_header("Simulasi Coin Change: Exhaustive vs Memo vs Tabulation")
    coins = [1, 2, 5]
    amount = 12

    print(f"Koin tersedia: {BOLD}{coins}{RESET}, Target Jumlah: {BOLD}{amount}{RESET}\n")

    # 1. Exhaustive Recursion
    tracker.reset()
    start_t = time.perf_counter()
    ans_bf = coin_change_recursive(coins, amount)
    dur_bf = (time.perf_counter() - start_t) * 1000
    calls_bf = tracker.call_count

    print(f"\n{RED}[Brute Force]{RESET} Solusi: {ans_bf} koin | Panggilan Rekursif: {calls_bf} | Waktu: {dur_bf:.3f} ms")

    # 2. Top-Down DP
    tracker.reset()
    start_t = time.perf_counter()
    ans_memo = coin_change_memo(coins, amount)
    dur_memo = (time.perf_counter() - start_t) * 1000
    calls_memo = tracker.call_count
    hits_memo = tracker.cache_hits

    print(f"{GREEN}[Top-Down Memoization]{RESET} Solusi: {ans_memo} koin | Panggilan: {calls_memo} (Cache Hits: {hits_memo}) | Waktu: {dur_memo:.3f} ms")

    # 3. Bottom-Up Tabulation
    start_t = time.perf_counter()
    ans_tab, path = coin_change_tabulation(coins, amount)
    dur_tab = (time.perf_counter() - start_t) * 1000

    print(f"\n{CYAN}[Bottom-Up Tabulation]{RESET} Solusi: {ans_tab} koin | Koin Dipakai: {path} | Waktu: {dur_tab:.3f} ms")

    # Summary table
    reduction = ((calls_bf - calls_memo) / calls_bf) * 100
    print(f"\n{BOLD}{YELLOW}Efisiensi Dynamic Programming:{RESET}")
    print(f"→ Panggilan rekursi terpangkas sebesar {BOLD}{reduction:.2f}%{RESET} berkat memoization state overlap!")


def run_knapsack_simulation():
    print_header("Simulasi 0/1 Knapsack: Bottom-Up Tabulation 2D Matrix")
    weights = [2, 3, 4, 5]
    values = [3, 4, 5, 8]
    capacity = 8

    print(f"Bobot Item: {weights}")
    print(f"Nilai Item: {values}")
    print(f"Kapasitas Maksimal: {capacity}")

    max_val = knapsack_tabulation(weights, values, capacity)
    print(f"\n{GREEN}{BOLD}Nilai Maksimal yang Dapat Ditampung: {max_val}{RESET}")


def interactive_menu():
    while True:
        print_header("MENU INTERAKTIF DP & EXHAUSTIVE SEARCH")
        print(f"{BOLD}1.{RESET} Jalankan Perbandingan Coin Change (Brute Force vs Memo vs DP)")
        print(f"{BOLD}2.{RESET} Jalankan Simulasi 0/1 Knapsack 2D State Table")
        print(f"{BOLD}3.{RESET} Eksekusi Kedua Simulasi")
        print(f"{BOLD}4.{RESET} Keluar (Exit)")
        print("-" * 60)

        choice = input(f"{BOLD}{YELLOW}Pilih opsi (1-4): {RESET}").strip()
        if choice == "1":
            run_coin_change_simulation()
        elif choice == "2":
            run_knapsack_simulation()
        elif choice == "3":
            run_coin_change_simulation()
            run_knapsack_simulation()
        elif choice == "4":
            print(f"\n{GREEN}Terima kasih telah mempelajari Dynamic Programming! Selesai.{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--non-interactive":
        # Jalankan otomatis untuk CI / automated test
        run_coin_change_simulation()
        run_knapsack_simulation()
    else:
        # Mode interaktif
        interactive_menu()
