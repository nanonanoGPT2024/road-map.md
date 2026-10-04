#!/usr/bin/env python3
"""
Lab Hands-on: Algorithmic Foundations & Amortized Complexity Deep Dive
Topic: Data Structures & Algorithms (Core Foundations - Chapter 01, Module 02)
Focus: Amortized Analysis of Dynamic Array Growth Strategies & O(1) Intrusive LRU Cache
"""

import sys
import time
import random
import math
from typing import Any, Optional, Tuple, Dict, List

# ANSI Color Codes for terminal formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"


class DynamicArrayAmortizationLab:
    """
    Simulasi alokasi memori internal array dinamis.
    Membandingkan Amortized Constant Time O(1) [Geometric Expansion: 2.0x]
    vs Worst-Case Linear Degradation O(N) [Arithmetic Expansion: +K fixed].
    """

    def __init__(self, growth_factor: float = 2.0, fixed_growth: int = 16):
        self.growth_factor = growth_factor
        self.fixed_growth = fixed_growth

    def simulate_geometric(self, n_inserts: int) -> Tuple[List[float], int]:
        """
        Simulasi alokasi geometrik (e.g., C++ std::vector, Python list amortisasi 1.125x - 2.0x).
        Menghitung microsecond latensi setiap operasi dan mencatat spike saat realokasi.
        """
        capacity = 1
        size = 0
        realloc_count = 0
        latencies = []

        # Buffer representasi raw pointer/memory
        buffer = [None] * capacity

        for _ in range(n_inserts):
            t0 = time.perf_counter_ns()
            if size == capacity:
                # Realokasi memori: allocate new buffer -> copy old elements -> delete old
                realloc_count += 1
                new_cap = int(capacity * self.growth_factor)
                new_buffer = [None] * new_cap
                for i in range(size):
                    new_buffer[i] = buffer[i]
                buffer = new_buffer
                capacity = new_cap

            buffer[size] = 0xDEADBEEF
            size += 1
            t1 = time.perf_counter_ns()
            latencies.append((t1 - t0) / 1000.0)  # microsecond

        return latencies, realloc_count

    def simulate_arithmetic(self, n_inserts: int) -> Tuple[List[float], int]:
        """
        Simulasi alokasi aritmetika (+K fixed size per realokasi).
        Menyebabkan deret aritmetika operasi penyalinan: O(N^2) total cost, O(N) amortized.
        """
        capacity = self.fixed_growth
        size = 0
        realloc_count = 0
        latencies = []
        buffer = [None] * capacity

        for _ in range(n_inserts):
            t0 = time.perf_counter_ns()
            if size == capacity:
                realloc_count += 1
                new_cap = capacity + self.fixed_growth
                new_buffer = [None] * new_cap
                for i in range(size):
                    new_buffer[i] = buffer[i]
                buffer = new_buffer
                capacity = new_cap

            buffer[size] = 0xDEADBEEF
            size += 1
            t1 = time.perf_counter_ns()
            latencies.append((t1 - t0) / 1000.0)

        return latencies, realloc_count


class LRUNode:
    """Node manual untuk doubly linked list, mengeliminasi overhead traversal."""
    __slots__ = ('key', 'val', 'prev', 'next')

    def __init__(self, key: int, val: Any):
        self.key: int = key
        self.val: Any = val
        self.prev: Optional['LRUNode'] = None
        self.next: Optional['LRUNode'] = None


class HighPerfLRUCache:
    """
    Sistem Cache O(1) deterministik murni menggunakan HashMap + Intrusive Doubly-Linked List.
    Tanpa menggunakan collections.OrderedDict untuk mengekspos mekanika low-level pointer.
    """

    def __init__(self, capacity: int):
        self.capacity: int = capacity
        self.lookup: Dict[int, LRUNode] = {}
        # Sentinel dummy nodes untuk menghindari edge-case null checks
        self.head: LRUNode = LRUNode(-1, -1)
        self.tail: LRUNode = LRUNode(-1, -1)
        self.head.next = self.tail
        self.tail.prev = self.head
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    def _remove(self, node: LRUNode) -> None:
        """Memutuskan node dari doubly-linked list dalam O(1) pointer operations."""
        prev_node = node.prev
        next_node = node.next
        if prev_node:
            prev_node.next = next_node
        if next_node:
            next_node.prev = prev_node

    def _add_to_front(self, node: LRUNode) -> None:
        """Menyisipkan node tepat di belakang sentinel head (Most Recently Used)."""
        node.next = self.head.next
        node.prev = self.head
        if self.head.next:
            self.head.next.prev = node
        self.head.next = node

    def get(self, key: int) -> Optional[Any]:
        """Lookup O(1): update posisi node ke head jika ditemukan."""
        if key in self.lookup:
            self.hits += 1
            node = self.lookup[key]
            self._remove(node)
            self._add_to_front(node)
            return node.val
        self.misses += 1
        return None

    def put(self, key: int, val: Any) -> None:
        """Insert O(1): mutasi data atau alokasi node baru + eviksi tail jika penuh."""
        if key in self.lookup:
            node = self.lookup[key]
            node.val = val
            self._remove(node)
            self._add_to_front(node)
        else:
            if len(self.lookup) >= self.capacity:
                # Eviksi node tepat sebelum tail (Least Recently Used)
                lru_node = self.tail.prev
                if lru_node and lru_node != self.head:
                    self._remove(lru_node)
                    del self.lookup[lru_node.key]
                    self.evictions += 1

            new_node = LRUNode(key, val)
            self.lookup[key] = new_node
            self._add_to_front(new_node)


def print_banner(title: str) -> None:
    width = 75
    print(f"\n{CLR_BLUE}{'=' * width}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BLUE}{'=' * width}{CLR_RESET}")


def run_amortization_benchmark():
    print_banner("1. Dynamic Array: Amortized Growth vs Arithmetic Penalty")
    
    n_ops = 50_000
    print(f"{CLR_YELLOW}Menjalankan simulasi {n_ops:,} mutasi append...{CLR_RESET}\n")
    
    lab = DynamicArrayAmortizationLab(growth_factor=2.0, fixed_growth=256)
    
    # Test Geometric
    t_start = time.perf_counter()
    geo_latencies, geo_reallocs = lab.simulate_geometric(n_ops)
    t_geo_total = (time.perf_counter() - t_start) * 1000.0

    # Test Arithmetic
    t_start = time.perf_counter()
    arith_latencies, arith_reallocs = lab.simulate_arithmetic(n_ops)
    t_arith_total = (time.perf_counter() - t_start) * 1000.0

    geo_avg = sum(geo_latencies) / len(geo_latencies)
    arith_avg = sum(arith_latencies) / len(arith_latencies)
    geo_max = max(geo_latencies)
    arith_max = max(arith_latencies)

    # Output Metrik
    print(f"{CLR_BOLD}Parameter:{CLR_RESET} Geometric (Factor: 2.0x) | Arithmetic (Step: +256 elements)")
    print("-" * 75)
    print(f"{'Metrik':<30} | {'Geometric (O(1) Amortized)':<20} | {'Arithmetic (Linear)':<18}")
    print("-" * 75)
    print(f"{'Total Runtime':<30} | {CLR_GREEN}{t_geo_total:10.2f} ms{CLR_RESET}        | {CLR_RED}{t_arith_total:10.2f} ms{CLR_RESET}")
    print(f"{'Reallocation Triggers':<30} | {CLR_GREEN}{geo_reallocs:10d} ops{CLR_RESET}       | {CLR_RED}{arith_reallocs:10d} ops{CLR_RESET}")
    print(f"{'Mean Op Latency':<30} | {CLR_GREEN}{geo_avg:10.4f} µs{CLR_RESET}        | {CLR_RED}{arith_avg:10.4f} µs{CLR_RESET}")
    print(f"{'Worst-case Spike (Max)':<30} | {CLR_YELLOW}{geo_max:10.2f} µs{CLR_RESET}        | {CLR_RED}{arith_max:10.2f} µs{CLR_RESET}")
    print("-" * 75)

    speedup = arith_avg / geo_avg if geo_avg > 0 else 1.0
    print(f"{CLR_BOLD}Kesimpulan Amortisasi:{CLR_RESET} Pola geometrik menunjukkan efisiensi {CLR_GREEN}{speedup:.2f}x{CLR_RESET} lebih stabil.")


def run_lru_workload_simulation():
    print_banner("2. O(1) Cache Pipeline: HashMap + Doubly-Linked Engine")
    
    capacity = 1000
    operations = 100_000
    cache = HighPerfLRUCache(capacity=capacity)
    
    print(f"Konfigurasi Cache: Kapasitas={capacity}, Total Operasi={operations:,}")
    print(f"Beban Kerja: Zipfian-like Distribution (80% akses mengarah ke 20% working-set)\n")

    # Simulasi 80/20 locality access distribution
    hot_boundary = 200
    cold_boundary = 3000

    t0 = time.perf_counter()
    for _ in range(operations):
        # 80% probabilitas mengakses data panas
        if random.random() < 0.8:
            key = random.randint(1, hot_boundary)
        else:
            key = random.randint(hot_boundary + 1, cold_boundary)

        # 70% Read, 30% Write
        if random.random() < 0.7:
            cache.get(key)
        else:
            cache.put(key, {"payload": 0xCAFEBABE, "ts": time.time()})

    total_time = (time.perf_counter() - t0) * 1000.0
    throughput = operations / (total_time / 1000.0)
    hit_ratio = (cache.hits / (cache.hits + cache.misses)) * 100.0 if (cache.hits + cache.misses) > 0 else 0

    print(f"{CLR_BOLD}Hasil Eksekusi Cache Engine:{CLR_RESET}")
    print(f"  • Throughput           : {CLR_CYAN}{throughput:,.0f} ops/sec{CLR_RESET}")
    print(f"  • Total Time Elapsed   : {total_time:.2f} ms")
    print(f"  • Cache Hits           : {CLR_GREEN}{cache.hits:,}{CLR_RESET}")
    print(f"  • Cache Misses         : {CLR_YELLOW}{cache.misses:,}{CLR_RESET}")
    print(f"  • Hit Ratio            : {CLR_BOLD}{CLR_GREEN if hit_ratio > 70 else CLR_RED}{hit_ratio:.2f}%{CLR_RESET}")
    print(f"  • Forced Evictions     : {CLR_MAGENTA}{cache.evictions:,}{CLR_RESET}")

    # Validasi invarian integritas linked list
    curr = cache.head
    forward_count = 0
    while curr.next:
        curr = curr.next
        forward_count += 1
    
    backward_count = 0
    while curr.prev:
        curr = curr.prev
        backward_count += 1

    invariant_ok = (forward_count == backward_count) and (len(cache.lookup) <= capacity)
    status_str = f"{CLR_GREEN}PASSED (Structure Balanced){CLR_RESET}" if invariant_ok else f"{CLR_RED}CORRUPTED{CLR_RESET}"
    print(f"  • Pointer Invariant    : {status_str}")


def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}SYSTEM ARCHITECTURE BENCHMARK TOOL{CLR_RESET}")
    print(f"Python Runtime: {sys.version.split()[0]} on {sys.platform}")
    
    random.seed(42)  # Menjaga determinisme hasil tes
    
    run_amortization_benchmark()
    run_lru_workload_simulation()
    
    print(f"\n{CLR_GREEN}{CLR_BOLD}Semua tes fundamental DSA selesai dengan sukses.{CLR_RESET}\n")


if __name__ == "__main__":
    main()