#!/usr/bin/env python3
"""
Lab Hands-on: Core Foundations - Data Structures & Algorithms
Deep Dive: Custom High-Performance Eviction Engines (O(1) LRU vs. O(1) LFU)
Simulasi komparasi hit-rate dan throughput cache di bawah beban kerja terdistribusi Zipfian.
"""

import sys
import time
import random
from typing import Optional, Dict, Any, Tuple

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"


class DLLNode:
    """Node untuk Doubly Linked List yang menyimpan metadata frekuensi dan payload."""
    __slots__ = ('key', 'val', 'freq', 'prev', 'next')

    def __init__(self, key: int, val: Any):
        self.key: int = key
        self.val: Any = val
        self.freq: int = 1
        self.prev: Optional['DLLNode'] = None
        self.next: Optional['DLLNode'] = None


class DoublyLinkedList:
    """Struktur data Doubly Linked List circular-sentinel untuk operasi O(1) penambahan/penghapusan."""
    __slots__ = ('head', 'tail', 'size')

    def __init__(self):
        self.head = DLLNode(-1, None)
        self.tail = DLLNode(-1, None)
        self.head.next = self.tail
        self.tail.prev = self.head
        self.size: int = 0

    def append_left(self, node: DLLNode) -> None:
        """Menambahkan node tepat di belakang dummy head (Most Recently Used slot)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node
        self.size += 1

    def remove(self, node: DLLNode) -> DLLNode:
        """Memutuskan node dari rantai linked list dalam O(1)."""
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = None
        node.next = None
        self.size -= 1
        return node

    def pop_tail(self) -> Optional[DLLNode]:
        """Mengeluarkan node tepat sebelum dummy tail (Least Recently Used slot)."""
        if self.size == 0:
            return None
        return self.remove(self.tail.prev)

    def is_empty(self) -> bool:
        return self.size == 0


class LRUCache:
    """Implementasi O(1) Least Recently Used Cache dengan Hash-Map dan Doubly Linked List."""
    def __init__(self, capacity: int):
        self.capacity: int = capacity
        self.map: Dict[int, DLLNode] = {}
        self.dll: DoublyLinkedList = DoublyLinkedList()
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    def get(self, key: int) -> Optional[Any]:
        if key not in self.map:
            self.misses += 1
            return None
        node = self.map[key]
        self.dll.remove(node)
        self.dll.append_left(node)
        self.hits += 1
        return node.val

    def put(self, key: int, val: Any) -> None:
        if self.capacity <= 0:
            return
        if key in self.map:
            node = self.map[key]
            node.val = val
            self.dll.remove(node)
            self.dll.append_left(node)
            return

        if len(self.map) >= self.capacity:
            evicted = self.dll.pop_tail()
            if evicted:
                del self.map[evicted.key]
                self.evictions += 1

        new_node = DLLNode(key, val)
        self.dll.append_left(new_node)
        self.map[key] = new_node


class LFUCache:
    """
    Implementasi O(1) Least Frequently Used Cache.
    Menggunakan Hash-Map untuk lookup node dan Frequency Map berisi DLL untuk pengelompokan frekuensi.
    """
    def __init__(self, capacity: int):
        self.capacity: int = capacity
        self.min_freq: int = 0
        self.key_map: Dict[int, DLLNode] = {}
        self.freq_map: Dict[int, DoublyLinkedList] = {}
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    def _update_frequency(self, node: DLLNode) -> None:
        freq = node.freq
        self.freq_map[freq].remove(node)
        if self.freq_map[freq].is_empty():
            del self.freq_map[freq]
            if self.min_freq == freq:
                self.min_freq += 1

        node.freq += 1
        if node.freq not in self.freq_map:
            self.freq_map[node.freq] = DoublyLinkedList()
        self.freq_map[node.freq].append_left(node)

    def get(self, key: int) -> Optional[Any]:
        if key not in self.key_map:
            self.misses += 1
            return None
        node = self.key_map[key]
        self._update_frequency(node)
        self.hits += 1
        return node.val

    def put(self, key: int, val: Any) -> None:
        if self.capacity <= 0:
            return

        if key in self.key_map:
            node = self.key_map[key]
            node.val = val
            self._update_frequency(node)
            return

        if len(self.key_map) >= self.capacity:
            # Eviksi elemen terlama dari frekuensi minimum
            min_list = self.freq_map[self.min_freq]
            evicted = min_list.pop_tail()
            if evicted:
                del self.key_map[evicted.key]
                self.evictions += 1
                if min_list.is_empty():
                    del self.freq_map[self.min_freq]

        new_node = DLLNode(key, val)
        self.key_map[key] = new_node
        self.min_freq = 1
        if 1 not in self.freq_map:
            self.freq_map[1] = DoublyLinkedList()
        self.freq_map[1].append_left(new_node)


def generate_zipf_workload(unique_keys: int, operations_count: int, alpha: float = 1.25) -> list:
    """
    Menghasilkan simulasi akses berbasis distribusi Heavy-Tail (Power Law/Zipfian),
    mencerminkan pola akses data produksi di mana sebagian kecil keys mendominasi request.
    """
    random.seed(42)
    workload = []
    for _ in range(operations_count):
        # Transformasi Pareto variate ke boundary unique_keys
        sample = int(random.paretovariate(alpha))
        key = sample % unique_keys
        workload.append(key)
    return workload


def run_benchmark(engine_name: str, cache_engine: Any, workload: list) -> Tuple[float, int, int, int]:
    """Eksekusi benchmark throughput dan capture hit rate ratio."""
    start_time = time.perf_counter()
    for key in workload:
        val = cache_engine.get(key)
        if val is None:
            # Simulate fetching from backend storage and caching
            cache_engine.put(key, f"payload_data_{key}")
    elapsed = time.perf_counter() - start_time
    return elapsed, cache_engine.hits, cache_engine.misses, cache_engine.evictions


def main() -> None:
    print(f"{CLR_BOLD}{CLR_CYAN}=== ADVANCED DSA LAB: O(1) CACHING ARCHITECTURE BENCHMARK ==={CLR_RESET}\n")

    cache_capacity = 256
    universe_size = 4096
    total_ops = 100_000

    print(f"Konfigurasi Beban Kerja:")
    print(f"  • Kapasitas Cache       : {CLR_YELLOW}{cache_capacity} slot{CLR_RESET}")
    print(f"  • Total Unique Keys    : {CLR_YELLOW}{universe_size} entri{CLR_RESET}")
    print(f"  • Jumlah Operasi Get/Put: {CLR_YELLOW}{total_ops:,} request{CLR_RESET}")
    print(f"  • Pola Akses            : {CLR_YELLOW}Zipfian (Skewed/Heavy-tail, Alpha=1.25){CLR_RESET}\n")

    print(f"Generating synthetic workload stream...", end=" ", flush=True)
    workload = generate_zipf_workload(universe_size, total_ops, alpha=1.25)
    print(f"{CLR_GREEN}[DONE]{CLR_RESET}\n")

    # Instance engine
    lru = LRUCache(cache_capacity)
    lfu = LFUCache(cache_capacity)

    print(f"{CLR_BOLD}Menjalankan Pengujian Stres...{CLR_RESET}")

    # Benchmark LRU
    t_lru, lru_hits, lru_miss, lru_evict = run_benchmark("LRU", lru, workload)
    lru_hr = (lru_hits / total_ops) * 100
    lru_throughput = total_ops / t_lru

    # Benchmark LFU
    t_lfu, lfu_hits, lfu_miss, lfu_evict = run_benchmark("LFU", lfu, workload)
    lfu_hr = (lfu_hits / total_ops) * 100
    lfu_throughput = total_ops / t_lfu

    # Output Metrik Komparasi
    border = "+----------------------+-------------------+-------------------+"
    header = "| Metrik Evaluasi      | LRU Engine        | LFU Engine        |"
    
    print(border)
    print(header)
    print(border)
    print(f"| Latensi Total (s)    | {t_lru:>17.4f} | {t_lfu:>17.4f} |")
    print(f"| Throughput (ops/sec) | {lru_throughput:>17.0f} | {lfu_throughput:>17.0f} |")
    print(f"| Cache Hits           | {lru_hits:>17,d} | {lfu_hits:>17,d} |")
    print(f"| Cache Misses         | {lru_miss:>17,d} | {lfu_miss:>17,d} |")
    print(f"| Eviction Count       | {lru_evict:>17,d} | {lfu_evict:>17,d} |")
    print(f"| Hit Ratio (%)        | {CLR_GREEN}{lru_hr:>16.2f}%{CLR_RESET} | {CLR_GREEN}{lfu_hr:>16.2f}%{CLR_RESET} |")
    print(border)

    # Analisis Algoritmik
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}Analisis Algoritma & Kompleksitas Runtime:{CLR_RESET}")
    if lfu_hr >= lru_hr:
        diff = lfu_hr - lru_hr
        print(f"  • {CLR_GREEN}LFU lebih unggul sebesar +{diff:.2f}% Hit Ratio.{CLR_RESET} LFU berhasil menahan 'hot keys' frekuensi tinggi")
        print("    meskipun rentang waktu akses terpecah, menjadikannya ideal untuk access pattern skewed.")
    else:
        diff = lru_hr - lfu_hr
        print(f"  • {CLR_GREEN}LRU lebih unggul sebesar +{diff:.2f}% Hit Ratio.{CLR_RESET} Menunjukkan adaptabilitas temporal yang lebih baik.")

    print(f"  • Kompleksitas Waktu: Kedua algoritma beroperasi strictly {CLR_BOLD}O(1) amortized{CLR_RESET} untuk get() dan put().")
    print(f"  • Kompleksitas Ruang: {CLR_BOLD}O(N){CLR_RESET} di mana N adalah kapasitas maksimum elemen cache.\n")


if __name__ == "__main__":
    main()