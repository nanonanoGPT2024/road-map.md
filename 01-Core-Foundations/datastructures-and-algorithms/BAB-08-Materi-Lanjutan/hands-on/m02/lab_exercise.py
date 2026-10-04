#!/usr/bin/env python3
"""
================================================================================
LAB HANDS-ON: ADVANCED DATA STRUCTURES & ALGORITHMS (MODULE 08 - DEEP DIVE)
Topic: High-Performance O(1) LFU (Least Frequently Used) Cache vs LRU
Architecture: Hash Map + Frequency-Bucketed Doubly Linked Lists
================================================================================
This script implements a strict O(1) average time complexity LFU Cache.
It models real-world storage tiering and memory eviction mechanics, comparing
performance against an LRU cache under Zipfian (skewed) workload distributions.
"""

import sys
import time
import random
import math
from typing import Optional, Dict, Any, Tuple

# Terminal ANSI Color Palette
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BG_DARK = "\033[40m"


class DLLNode:
    """
    Simpul Doubly Linked List yang menyimpan pasangan Key-Value dan Metadata Frekuensi.
    """
    __slots__ = ('key', 'val', 'freq', 'prev', 'next')

    def __init__(self, key: Any, val: Any, freq: int = 1):
        self.key: Any = key
        self.val: Any = val
        self.freq: int = freq
        self.prev: Optional['DLLNode'] = None
        self.next: Optional['DLLNode'] = None


class DoublyLinkedList:
    """
    Doubly Linked List dengan Sentinel Nodes (Head & Tail) untuk operasi O(1) add/remove.
    """
    def __init__(self):
        self.head: DLLNode = DLLNode(None, None, 0)
        self.tail: DLLNode = DLLNode(None, None, 0)
        self.head.next = self.tail
        self.tail.prev = self.head
        self._size: int = 0

    def append_left(self, node: DLLNode) -> None:
        """Menambahkan simpul tepat di belakang sentinel head (posisi Most Recently Used)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node
        self._size += 1

    def remove(self, node: DLLNode) -> DLLNode:
        """Menghapus simpul yang ditargetkan dari linked list secara O(1)."""
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = None
        node.next = None
        self._size -= 1
        return node

    def pop_tail(self) -> Optional[DLLNode]:
        """Menghapus dan mengembalikan simpul sebelum tail (posisi Least Recently Used)."""
        if self._size == 0:
            return None
        return self.remove(self.tail.prev)

    def is_empty(self) -> bool:
        return self._size == 0

    def __len__(self) -> int:
        return self._size


class LFUCache:
    """
    Cache LFU Berkinerja Tinggi: O(1) Get, O(1) Put.
    Menggunakan dua Hash Map:
      1. node_map: key -> DLLNode
      2. freq_map: frequency_count -> DoublyLinkedList
    Melacak 'min_freq' global untuk eviksi O(1) instan saat kapasitas penuh.
    """
    def __init__(self, capacity: int):
        self.capacity: int = capacity
        self.min_freq: int = 0
        self.node_map: Dict[Any, DLLNode] = {}
        self.freq_map: Dict[int, DoublyLinkedList] = {}
        # Metrik Telemetri
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    def _update_frequency(self, node: DLLNode) -> None:
        """Mempromosikan simpul ke bucket frekuensi berikutnya secara O(1)."""
        old_freq = node.freq
        old_list = self.freq_map[old_freq]
        old_list.remove(node)

        # Jika bucket min_freq menjadi kosong setelah simpul dipromosikan, naikkan min_freq
        if old_freq == self.min_freq and old_list.is_empty():
            self.min_freq += 1

        node.freq += 1
        new_freq = node.freq
        if new_freq not in self.freq_map:
            self.freq_map[new_freq] = DoublyLinkedList()
        self.freq_map[new_freq].append_left(node)

    def get(self, key: Any) -> Optional[Any]:
        """O(1) Access: Memperbarui frekuensi akses simpul."""
        if key not in self.node_map:
            self.misses += 1
            return None

        self.hits += 1
        node = self.node_map[key]
        self._update_frequency(node)
        return node.val

    def put(self, key: Any, value: Any) -> None:
        """O(1) Insertion & Eviction."""
        if self.capacity <= 0:
            return

        # Kasus 1: Key sudah ada, perbarui nilai dan tingkatkan frekuensi
        if key in self.node_map:
            node = self.node_map[key]
            node.val = value
            self._update_frequency(node)
            return

        # Kasus 2: Key baru, periksa kapasitas dan eviksi jika perlu
        if len(self.node_map) >= self.capacity:
            evict_list = self.freq_map[self.min_freq]
            evicted_node = evict_list.pop_tail()
            if evicted_node:
                del self.node_map[evicted_node.key]
                self.evictions += 1

        # Buat simpul baru dengan frekuensi = 1
        new_node = DLLNode(key, value, freq=1)
        self.node_map[key] = new_node
        if 1 not in self.freq_map:
            self.freq_map[1] = DoublyLinkedList()
        self.freq_map[1].append_left(new_node)
        self.min_freq = 1


class LRUCache:
    """
    Standard LRU Cache Baseline menggunakan Hash Map + Singly/Doubly Linked List logic.
    Digunakan sebagai kontrol pembanding benchmark.
    """
    def __init__(self, capacity: int):
        self.capacity: int = capacity
        self.node_map: Dict[Any, DLLNode] = {}
        self.dll: DoublyLinkedList = DoublyLinkedList()
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    def get(self, key: Any) -> Optional[Any]:
        if key not in self.node_map:
            self.misses += 1
            return None
        self.hits += 1
        node = self.node_map[key]
        self.dll.remove(node)
        self.dll.append_left(node)
        return node.val

    def put(self, key: Any, value: Any) -> None:
        if key in self.node_map:
            node = self.node_map[key]
            node.val = value
            self.dll.remove(node)
            self.dll.append_left(node)
            return

        if len(self.node_map) >= self.capacity:
            evicted = self.dll.pop_tail()
            if evicted:
                del self.node_map[evicted.key]
                self.evictions += 1

        new_node = DLLNode(key, value)
        self.node_map[key] = new_node
        self.dll.append_left(new_node)


def generate_zipfian_keys(num_keys: int, num_samples: int, alpha: float = 1.25) -> list:
    """
    Menghasilkan urutan key dengan distribusi Zipfian/Pareto Skewed (80/20 rule).
    Mensimulasikan beban kerja caching dunia nyata di mana subset kecil key diakses masif.
    """
    weights = [1.0 / (i ** alpha) for i in range(1, num_keys + 1)]
    sum_weights = sum(weights)
    probabilities = [w / sum_weights for w in weights]
    
    # Cumulative Distribution Function (CDF)
    cdf = []
    current = 0.0
    for p in probabilities:
        current += p
        cdf.append(current)

    samples = []
    for _ in range(num_samples):
        r = random.random()
        # Binary Search over CDF
        low, high = 0, num_keys - 1
        idx = num_keys - 1
        while low <= high:
            mid = (low + high) // 2
            if r <= cdf[mid]:
                idx = mid
                high = mid - 1
            else:
                low = mid + 1
        samples.append(f"resource_key_{idx}")
    return samples


def run_correctness_trace():
    """Verifikasi step-by-step invarian internal LFU."""
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== STEP 1: VERIFIKASI LOGIKA & TRACKING INVARIAN LFU ==={CLR_RESET}")
    cache = LFUCache(capacity=3)
    operations = [
        ("PUT", "K1", "v1.0"),
        ("PUT", "K2", "v2.0"),
        ("PUT", "K3", "v3.0"),
        ("GET", "K1", None),      # K1 freq -> 2
        ("GET", "K1", None),      # K1 freq -> 3
        ("GET", "K2", None),      # K2 freq -> 2
        ("PUT", "K4", "v4.0"),    # K3 (freq 1) harus dieviksi!
        ("GET", "K3", None),      # Harus Miss (None)
        ("GET", "K4", None),      # K4 freq -> 2
    ]

    for op, k, val in operations:
        if op == "PUT":
            cache.put(k, val)
            print(f"  {CLR_YELLOW}[PUT]{CLR_RESET} Key: {k:<3} | Val: {val:<5} -> State: Size={len(cache.node_map)}, MinFreq={cache.min_freq}")
        else:
            res = cache.get(k)
            color = CLR_GREEN if res is not None else CLR_RED
            print(f"  {color}[GET]{CLR_RESET} Key: {k:<3} | Result: {str(res):<5} -> State: MinFreq={cache.min_freq}")

    print(f"\n  Pemeriksaan Validitas Eviksi K3:")
    if "K3" not in cache.node_map:
        print(f"  {CLR_GREEN}✔ PASS:{CLR_RESET} 'K3' berhasil dieviksi secara deterministik berdasarkan LFU policy.")
    else:
        print(f"  {CLR_RED}✘ FAIL:{CLR_RESET} 'K3' masih ditemukan di dalam cache.")


def run_benchmark_comparison():
    """Benchmark LFU vs LRU dengan beban kerja Zipfian nyata."""
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== STEP 2: STRESS BENCHMARK SKEWED WORKLOAD (LFU vs LRU) ==={CLR_RESET}")

    UNIQUE_KEYS = 500
    WORKLOAD_SIZE = 50000
    CACHE_CAPACITY = 50  # 10% dari total unique keys

    print(f"  Total Unique Keys : {CLR_BOLD}{UNIQUE_KEYS}{CLR_RESET}")
    print(f"  Total Operasi IO  : {CLR_BOLD}{WORKLOAD_SIZE:,}{CLR_RESET}")
    print(f"  Kapasitas Cache   : {CLR_BOLD}{CACHE_CAPACITY}{CLR_RESET} (10% Working Set)")
    print(f"  Menghasilkan pola beban kerja Zipfian (Skews: alpha=1.35)...")

    workload = generate_zipfian_keys(UNIQUE_KEYS, WORKLOAD_SIZE, alpha=1.35)

    lfu = LFUCache(capacity=CACHE_CAPACITY)
    lru = LRUCache(capacity=CACHE_CAPACITY)

    # 1. Benchmark LFU
    t0 = time.perf_counter()
    for k in workload:
        val = lfu.get(k)
        if val is None:
            lfu.put(k, f"payload_{k}")
    lfu_duration = (time.perf_counter() - t0) * 1000

    # 2. Benchmark LRU
    t0 = time.perf_counter()
    for k in workload:
        val = lru.get(k)
        if val is None:
            lru.put(k, f"payload_{k}")
    lru_duration = (time.perf_counter() - t0) * 1000

    # Kalkulasi Metrik
    lfu_hit_rate = (lfu.hits / WORKLOAD_SIZE) * 100
    lru_hit_rate = (lru.hits / WORKLOAD_SIZE) * 100

    print(f"\n{CLR_BOLD}{'ALGORITMA':<12} | {'HIT RATE (%)':<14} | {'HITS':<10} | {'MISSES':<10} | {'EVICTIONS':<10} | {'DURASI (ms)':<10}{CLR_RESET}")
    print("-" * 75)
    print(f"{CLR_MAGENTA}{'LFU Cache':<12}{CLR_RESET} | {CLR_GREEN}{lfu_hit_rate:>12.2f}%{CLR_RESET} | {lfu.hits:>10,}"
          f" | {lfu.misses:>10,} | {lfu.evictions:>10,} | {lfu_duration:>9.2f} ms")
    print(f"{CLR_YELLOW}{'LRU Cache':<12}{CLR_RESET} | {lru_hit_rate:>12.2f}% | {lru.hits:>10,}"
          f" | {lru.misses:>10,} | {lru.evictions:>10,} | {lru_duration:>9.2f} ms")
    print("-" * 75)

    delta_hits = lfu.hits - lru.hits
    pct_improvement = ((lfu_hit_rate - lru_hit_rate) / lru_hit_rate) * 100
    print(f"\n{CLR_BOLD}Analisis Performa Tingkat Sistem:{CLR_RESET}")
    if delta_hits > 0:
        print(f"  {CLR_GREEN}✔ LFU mengungguli LRU sebesar +{pct_improvement:.2f}% Hit Ratio efisiensi.{CLR_RESET}")
        print(f"  Penyebab: LFU mempertahankan frekuensi jangka panjang pada 'hot' dataset,")
        print(f"  mencegah polusi cache akibat fluktuasi transien sementara.")
    else:
        print(f"  LFU dan LRU menunjukkan performa sebanding pada parameter distribusi ini.")


def main():
    print(f"{CLR_BOLD}{CLR_GREEN}" + "=" * 75)
    print(f"  SISTEM DSA LAB: DUAL-HASH DOUBLY-LINKED O(1) LFU ENGINE")
    print(f"  Eksekusi: Standar Python 3 | Modul 08 - Deep Dive")
    print("=" * 75 + f"{CLR_RESET}")

    run_correctness_trace()
    run_benchmark_comparison()

    print(f"\n{CLR_BOLD}{CLR_GREEN}[LAB SELESAI] Eksekusi simulasi dan benchmark berhasil diselesaikan.{CLR_RESET}\n")


if __name__ == "__main__":
    main()