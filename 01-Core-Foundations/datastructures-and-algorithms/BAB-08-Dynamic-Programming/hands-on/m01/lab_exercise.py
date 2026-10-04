#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Dynamic Programming Fundamentals
BAB-08: Dynamic Programming (DSA Foundation Series)

Topics Covered:
1. Overlapping Subproblems & Optimal Substructure (Fibonacci Benchmark)
2. Top-Down Memoization vs Bottom-Up Tabulation
3. 0/1 Knapsack Problem with DP Table Visualization
4. Coin Change Problem (Unbounded / Minimum Coins)
"""

import sys
import time
from typing import List, Dict, Tuple, Optional

# ANSI Color Codes for Rich Terminal Output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright Foreground
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

def print_header(title: str) -> None:
    print("\n" + f"{Colors.BRIGHT_CYAN}{'=' * 65}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BRIGHT_YELLOW} >>> {title.upper()} <<<{Colors.RESET}")
    print(f"{Colors.BRIGHT_CYAN}{'=' * 65}{Colors.RESET}\n")

def print_substep(step: str, desc: str) -> None:
    print(f"{Colors.BOLD}{Colors.MAGENTA}[{step}]{Colors.RESET} {Colors.WHITE}{desc}{Colors.RESET}")

# -------------------------------------------------------------------------
# 1. Fibonacci Comparison: Naive Recursion vs Memoization vs Tabulation
# -------------------------------------------------------------------------

class FibCounters:
    naive_calls = 0
    memo_calls = 0

def fib_naive(n: int) -> int:
    FibCounters.naive_calls += 1
    if n <= 1:
        return n
    return fib_naive(n - 1) + fib_naive(n - 2)

def fib_memo(n: int, memo: Optional[Dict[int, int]] = None) -> int:
    if memo is None:
        memo = {}
    FibCounters.memo_calls += 1
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fib_memo(n - 1, memo) + fib_memo(n - 2, memo)
    return memo[n]

def fib_tabulation(n: int) -> Tuple[int, List[int]]:
    if n == 0:
        return 0, [0]
    dp = [0] * (n + 1)
    dp[0] = 0
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i - 1] + dp[i - 2]
    return dp[n], dp

def demo_fibonacci(n: int = 30) -> None:
    print_header(f"1. Core Principles: Fibonacci Call Tree & State Caching (N = {n})")
    
    print_substep("1.1", "Benchmarking Naive Recursion vs Memoization vs Tabulation")
    
    # 1. Naive Recursion
    FibCounters.naive_calls = 0
    t0 = time.perf_counter()
    res_naive = fib_naive(n)
    t_naive = time.perf_counter() - t0
    
    # 2. Top-down Memoization
    FibCounters.memo_calls = 0
    t0 = time.perf_counter()
    res_memo = fib_memo(n)
    t_memo = time.perf_counter() - t0
    
    # 3. Bottom-up Tabulation
    t0 = time.perf_counter()
    res_tab, dp_arr = fib_tabulation(n)
    t_tab = time.perf_counter() - t0
    
    print(f"\n{Colors.BOLD}{'Approach':<20} | {'Result':<10} | {'Function Calls':<16} | {'Exec Time (s)':<14}{Colors.RESET}")
    print("-" * 68)
    print(f"{Colors.RED}{'Naive O(2^n)':<20}{Colors.RESET} | {res_naive:<10} | {FibCounters.naive_calls:<16} | {t_naive:.6f}s")
    print(f"{Colors.YELLOW}{'Memoized O(n)':<20}{Colors.RESET} | {res_memo:<10} | {FibCounters.memo_calls:<16} | {t_memo:.6f}s")
    print(f"{Colors.BRIGHT_GREEN}{'Tabulation O(n)':<20}{Colors.RESET} | {res_tab:<10} | {'1 (iterative)':<16} | {t_tab:.6f}s")
    
    efficiency_gain = FibCounters.naive_calls / max(1, FibCounters.memo_calls)
    print(f"\n{Colors.BRIGHT_GREEN}[INSIGHT]{Colors.RESET} Memoization eliminated {Colors.BOLD}{efficiency_gain:.1f}x{Colors.RESET} redundant calls!")
    print(f"Sample DP Table Slice (first 10 elements): {Colors.CYAN}{dp_arr[:10]}{Colors.RESET}")

# -------------------------------------------------------------------------
# 2. 0/1 Knapsack Problem with Live DP Matrix
# -------------------------------------------------------------------------

def knapsack_01_solve(weights: List[int], values: List[int], capacity: int) -> Tuple[int, List[List[int]], List[int]]:
    n = len(weights)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    
    # Build DP Table
    for i in range(1, n + 1):
        w = weights[i - 1]
        v = values[i - 1]
        for c in range(capacity + 1):
            if w <= c:
                dp[i][c] = max(dp[i - 1][c], dp[i - 1][c - w] + v)
            else:
                dp[i][c] = dp[i - 1][c]
                
    # Backtrack chosen items
    chosen_items = []
    curr_c = capacity
    for i in range(n, 0, -1):
        if dp[i][curr_c] != dp[i - 1][curr_c]:
            chosen_items.append(i - 1)
            curr_c -= weights[i - 1]
            
    chosen_items.reverse()
    return dp[n][capacity], dp, chosen_items

def print_knapsack_table(weights: List[int], values: List[int], capacity: int, dp: List[List[int]]) -> None:
    print(f"\n{Colors.BOLD}{Colors.WHITE}=== 0/1 Knapsack 2D DP Table ==={Colors.RESET}")
    header_str = f"{'Item (w, v)':<14} | " + " ".join(f"{c:>4}" for c in range(capacity + 1))
    print(f"{Colors.BRIGHT_CYAN}{header_str}{Colors.RESET}")
    print("-" * len(header_str))
    
    for i in range(len(dp)):
        item_label = "Base (i=0)" if i == 0 else f"Item {i} ({weights[i-1]}kg, ${values[i-1]})"
        row_str = f"{item_label:<14} | "
        for c in range(capacity + 1):
            val = dp[i][c]
            if val == 0:
                row_str += f"{Colors.WHITE}{val:>4}{Colors.RESET} "
            elif i > 0 and val != dp[i-1][c]:
                # Cell changed value because item was included
                row_str += f"{Colors.BRIGHT_GREEN}{Colors.BOLD}{val:>4}{Colors.RESET} "
            else:
                row_str += f"{Colors.YELLOW}{val:>4}{Colors.RESET} "
        print(row_str)
    print(f"{Colors.WHITE}Legend: {Colors.BRIGHT_GREEN}Green = Item Chosen/State Jump{Colors.RESET}, {Colors.YELLOW}Yellow = Inherited previous state{Colors.RESET}\n")

def demo_knapsack() -> None:
    print_header("2. Classic 0/1 Knapsack Decision Matrix")
    
    # Items: (weight, value)
    items = [
        {"name": "Laptop", "weight": 3, "val": 50},
        {"name": "Guitar", "weight": 1, "val": 15},
        {"name": "Drone",  "weight": 2, "val": 40},
        {"name": "Camera", "weight": 4, "val": 60},
    ]
    capacity = 6
    
    weights = [it["weight"] for it in items]
    values = [it["val"] for it in items]
    
    print_substep("2.1", f"Item Inventory (Knapsack Max Capacity = {capacity}kg):")
    for idx, it in enumerate(items, 1):
        print(f"    Item {idx}: {it['name']:<8} -> Weight: {it['weight']}kg | Value: ${it['val']}")
        
    max_val, dp_table, chosen = knapsack_01_solve(weights, values, capacity)
    print_knapsack_table(weights, values, capacity, dp_table)
    
    total_w = sum(items[i]["weight"] for i in chosen)
    print(f"{Colors.BOLD}{Colors.BRIGHT_GREEN}Optimal Knapsack Solution:{Colors.RESET}")
    print(f" - Max Achievable Value: {Colors.BOLD}${max_val}{Colors.RESET}")
    print(f" - Total Weight Used:    {total_w} / {capacity} kg")
    print(f" - Selected Items:       {[items[i]['name'] for i in chosen]}")

# -------------------------------------------------------------------------
# 3. Coin Change Problem (Minimum Coins - Bottom-Up 1D DP)
# -------------------------------------------------------------------------

def coin_change_min(coins: List[int], amount: int) -> Tuple[int, List[int], List[int]]:
    # dp[i] = min coins needed to form amount i
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0
    parent = [-1] * (amount + 1)
    
    for a in range(1, amount + 1):
        for c in coins:
            if a - c >= 0 and dp[a - c] + 1 < dp[a]:
                dp[a] = dp[a - c] + 1
                parent[a] = c
                
    # Reconstruct coin combination
    res_coins = []
    curr = amount
    while curr > 0 and parent[curr] != -1:
        coin_used = parent[curr]
        res_coins.append(coin_used)
        curr -= coin_used
        
    min_coins = dp[amount] if dp[amount] != float('inf') else -1
    return min_coins, dp, res_coins

def demo_coin_change() -> None:
    print_header("3. Coin Change Problem: Minimum Coins (1D Tabulation)")
    coins = [1, 3, 4]
    amount = 6
    
    print_substep("3.1", f"Available Coin Denominations: {coins}")
    print_substep("3.2", f"Target Amount to Exchange: {amount}")
    
    min_coins, dp_array, used_coins = coin_change_min(coins, amount)
    
    print(f"\n{Colors.BOLD}1D DP Array Evolution (Index represents Amount):{Colors.RESET}")
    idx_str = "Amount (a):  " + " ".join(f"{i:>3}" for i in range(amount + 1))
    val_str = "DP[a] (coins):" + " ".join(f"{v:>3}" for v in dp_array)
    print(f"{Colors.CYAN}{idx_str}{Colors.RESET}")
    print(f"{Colors.BRIGHT_GREEN}{val_str}{Colors.RESET}\n")
    
    print(f"{Colors.BOLD}Result Summary:{Colors.RESET}")
    print(f" - Min Coins Count: {Colors.BOLD}{Colors.YELLOW}{min_coins}{Colors.RESET}")
    print(f" - Coins Chosen:    {Colors.BOLD}{Colors.GREEN}{used_coins}{Colors.RESET} (Sum = {sum(used_coins)})")
    print(f" - Greedy Pitfall Note: Greedy (4, 1, 1) uses 3 coins, but DP found optimal (3, 3) using {min_coins} coins!")

# -------------------------------------------------------------------------
# Interactive Main CLI Loop
# -------------------------------------------------------------------------

def interactive_menu() -> None:
    while True:
        print("\n" + f"{Colors.BRIGHT_WHITE}{Colors.BOLD}=== DYNAMIC PROGRAMMING LAB SIMULATOR (BAB-08) ==={Colors.RESET}")
        print(f"{Colors.CYAN}1.{Colors.RESET} Run Fibonacci Overlapping Subproblems Benchmark")
        print(f"{Colors.CYAN}2.{Colors.RESET} Run 0/1 Knapsack 2D Matrix Simulation")
        print(f"{Colors.CYAN}3.{Colors.RESET} Run Coin Change (Min Coins) Optimization")
        print(f"{Colors.CYAN}4.{Colors.RESET} Run All Demos Sequentially")
        print(f"{Colors.RED}5.{Colors.RESET} Exit Lab")
        
        try:
            choice = input(f"\n{Colors.BOLD}Pilih simulasi [1-5]: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}Exiting lab gracefully...{Colors.RESET}")
            break
            
        if choice == "1":
            demo_fibonacci(32)
        elif choice == "2":
            demo_knapsack()
        elif choice == "3":
            demo_coin_change()
        elif choice == "4":
            demo_fibonacci(30)
            demo_knapsack()
            demo_coin_change()
        elif choice == "5":
            print(f"\n{Colors.BRIGHT_GREEN}DP Lab simulation complete. Teruslah berlatih!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan coba lagi.{Colors.RESET}")

if __name__ == "__main__":
    # If executed non-interactively or with flags
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        demo_fibonacci(28)
        demo_knapsack()
        demo_coin_change()
    else:
        interactive_menu()
