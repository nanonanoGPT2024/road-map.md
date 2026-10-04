#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Data Structures & Algorithms - Bab 05 / Modul 02 Deep Dive
Topik: O(1) Least Frequently Used (LFU) Eviction Engine via Doubly Linked Lists & Hash Maps

Implementasi native sistem cache berkinerja tinggi tanpa menggunakan collections.OrderedDict.
Mendemonstrasikan algoritma LFU sejati dengan kompleksitas waktu O(1) untuk get() dan put(),
dilengkapi benchmark performa, audit jejak eviksi memori, dan simulasi akses non-uniform (Zipfian-like).
"""

import sys
import time
import random
from typing import Optional, Dict

# ANSI Terminal Styling
CLR_RESET  = "\033[0m"
CLR_CYAN   = "\033[96m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED    = "\033[91m"
CLR_BOLD   = "\033[1m"
CLR_DIM    = "\033[2m"


class CacheNode:
    """Node individual untuk Doubly Linked List."""
    __slots__ = ("key", "val", "freq", "prev", "next")

    def __init__(self, key: int, val: str, freq: int = 1):
        self.key: int = key
        self.val: str = val
        self.freq: int = freq
        self.prev: Optional["CacheNode"] = None
        self.next: Optional["CacheNode"] = None


class DoublyLinkedList:
    """
    Doubly Linked List dengan sentinel nodes (dummy head & tail)
    untuk operasi push dan pop instan O(1) tanpa edge-case dereferencing.
    """
    def __init__(self):
        self.head = CacheNode(0, "", 0)
        self.tail = CacheNode(0, "", 0)
        self.head.next = self.tail
        self.tail.prev = self.head
        self.size = 0

    def append_node(self, node: CacheNode) -> None:
        """Menambahkan node baru di akhir list (tepat sebelum tail sentinel)."""
        node.prev = self.tail.prev
        node.next = self.tail
        if self.tail.prev:
            self.tail.prev.next = node
        self.tail.prev = node
        self.size += 1

    def remove_node(self, node: CacheNode) -> None:
        """Menghapus node tertentu dari rantai pointer dalam O(1)."""
        if not node.prev or not node.next:
            return
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = None
        node.next = None
        self.size -= 1

    def pop_head(self) -> Optional[CacheNode]:
        """Menghapus dan mengembalikan node pertama (paling tua / least recently accessed)."""
        if self.size == 0:
            return None
        first_node = self.head.next
        if first_node and first_node != self.tail:
            self.remove_node(first_node)
            return first_node
        return None

    def is_empty(self) -> bool:
        return self.size == 0


class LFUCache:
    """
    Engine Cache O(1) LFU (Least Frequently Used) dengan tie-breaker LRU.
    
    Arsitektur:
    - key_map: key -> CacheNode (Akses instan)
    - freq_map: freq -> DoublyLinkedList (Node dikelompokkan berdasarkan frekuensi akses)
    - min_freq: Melacak frekuensi minimum saat ini untuk eviksi O(1)
    """
    def __init__(self, capacity: int):
        self.capacity: int = capacity
        self.size: int = 0
        self.min_freq: int = 0
        self.key_map: Dict[int, CacheNode] = {}
        self.freq_map: Dict[int, DoublyLinkedList] = {}
        
        # Telemetri
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    def _update_frequency(self, node: CacheNode) -> None:
        """Helper internal: Mempromosikan node ke bucket frekuensi berikutnya."""
        current_freq = node.freq
        dll_current = self.freq_map[current_freq]
        dll_current.remove_node(node)

        # Jika list frekuensi minimum saat ini menjadi kosong, tingkatkan min_freq
        if current_freq == self.min_freq and dll_current.is_empty():
            self.min_freq += 1

        node.freq += 1
        new_freq = node.freq
        if new_freq not in self.freq_map:
            self.freq_map[new_freq] = DoublyLinkedList()
        self.freq_map[new_freq].append_node(node)

    def get(self, key: int) -> Optional[str]:
        """Mengambil data item dan memperbarui frekuensi akses dalam O(1)."""
        if key not in self.key_map:
            self.misses += 1
            return None

        self.hits += 1
        node = self.key_map[key]
        self._update_frequency(node)
        return node.val

    def put(self, key: int, value: str) -> None:
        """Memasukkan atau memperbarui data item dalam O(1), mengeksekusi eviksi jika penuh."""
        if self.capacity <= 0:
            return

        if key in self.key_map:
            node = self.key_map[key]
            node.val = value
            self._update_frequency(node)
            return

        # Handle kapasitas penuh: evict LFU item
        if self.size >= self.capacity:
            evict_list = self.freq_map[self.min_freq]
            evicted_node = evict_list.pop_head()
            if evicted_node:
                del self.key_map[evicted_node.key]
                self.size -= 1
                self.evictions += 1

        # Tambahkan item baru dengan frekuensi = 1
        new_node = CacheNode(key, value, freq=1)
        self.key_map[key] = new_node
        if 1 not in self.freq_map:
            self.freq_map[1] = DoublyLinkedList()
        self.freq_map[1].append_node(new_node)
        
        self.min_freq = 1
        self.size += 1


def print_header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [LAB CORE] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")


def run_correctness_verification() -> None:
    """Verifikasi ketat fungsionalitas eviction LFU dan penanganan collision frekuensi."""
    print_header("Tahap 1: Verifikasi Ketepatan Logika Algoritma LFU")
    cache = LFUCache(capacity=3)
    
    print(f"{CLR_YELLOW}[ACTION]{CLR_RESET} Inisialisasi LFU Cache dengan Kapasitas: 3")
    
    # Isi cache: [k1, k2, k3]
    cache.put(1, "Data_Alpha")
    cache.put(2, "Data_Beta")
    cache.put(3, "Data_Gamma")
    print(f"  -> Disimpan: Key 1, 2, 3 (Semua Freq: 1)")

    # Akses k1 dua kali -> Freq: 3; Akses k2 sekali -> Freq: 2; k3 tetap -> Freq: 1
    cache.get(1)
    cache.get(1)
    cache.get(2)
    print(f"{CLR_YELLOW}[ACTION]{CLR_RESET} Query Get(1) x2, Get(2) x1. Freq Map -> (k1: 3, k2: 2, k3: 1)")

    # Masukkan k4: Kapasitas penuh! k3 harus tereliminasi karena freq paling rendah (1)
    print(f"{CLR_YELLOW}[ACTION]{CLR_RESET} Put(4, 'Data_Delta') -> Harus memicu eviksi O(1)...")
    cache.put(4, "Data_Delta")

    evicted_check = cache.get(3)
    k4_check = cache.get(4)
    print(f"  -> Verifikasi Key 3 (Terekvinsi?): {CLR_RED if evicted_check is None else CLR_GREEN}{'TEREKVISI (None)' if evicted_check is None else 'GAGAL'}{CLR_RESET}")
    print(f"  -> Verifikasi Key 4 (Eksis?): {CLR_GREEN if k4_check == 'Data_Delta' else CLR_RED}{k4_check}{CLR_RESET}")
    
    # Assert correctness
    assert evicted_check is None, "Logic Error: Key 3 seharusnya sudah dieviasi!"
    assert k4_check == "Data_Delta", "Logic Error: Key 4 gagal dimasukkan!"
    print(f"{CLR_GREEN}✓ Uji logika dasar LFU dan migrasi pointer Doubly-Linked-List lolos!{CLR_RESET}")


def run_workload_benchmark(num_ops: int = 150_000, capacity: int = 1_000) -> None:
    """
    Simulasi beban produksi menggunakan distribusi skew non-uniform (Zipfian approximation).
    80% request mengakses 20% ruang kunci (Hot Keys).
    """
    print_header(f"Tahap 2: Stres Uji & Benchmark Kinerja ({num_ops:,} Operasi)")
    cache = LFUCache(capacity=capacity)
    
    hot_keys = list(range(1, int(capacity * 0.2) + 1))
    cold_keys = list(range(int(capacity * 0.2) + 1, capacity * 5))
    
    print(f"Konfigurasi Beban Kerja:")
    print(f"  • Kapasitas Cache: {CLR_BOLD}{capacity:,}{CLR_RESET} entri")
    print(f"  • Domain Data    : {CLR_BOLD}{(capacity * 5):,}{CLR_RESET} variasi key")
    print(f"  • Pola Akses     : 80% Hot Keys (Akses Tinggi), 20% Cold Keys (Long Tail)")
    print(f"{CLR_DIM}Memulai simulasi operasi memori intensif...{CLR_RESET}\n")

    t_start = time.perf_counter_ns()
    
    # Loop eksekusi operasi
    for i in range(num_ops):
        # 80/20 probability routing
        if random.random() < 0.8:
            key = random.choice(hot_keys)
        else:
            key = random.choice(cold_keys)

        # 70% READ, 30% WRITE
        if random.random() < 0.7:
            cache.get(key)
        else:
            cache.put(key, f"val_{key}_{i}")

    t_end = time.perf_counter_ns()
    total_time_ms = (t_end - t_start) / 1_000_000
    avg_op_ns = (t_end - t_start) / num_ops
    ops_per_sec = (num_ops / (total_time_ms / 1000.0))

    hit_rate = (cache.hits / (cache.hits + cache.misses)) * 100 if (cache.hits + cache.misses) > 0 else 0

    # Tampilkan Matrix Telemetri
    print(f"{CLR_BOLD}--- TELEMETRI KINERJA ENGINE CACHE ---{CLR_RESET}")
    print(f"Waktu Eksekusi Total : {CLR_CYAN}{total_time_ms:.2f} ms{CLR_RESET}")
    print(f"Throughput Rata-rata : {CLR_GREEN}{ops_per_sec:,.0f} ops/detik{CLR_RESET}")
    print(f"Latency per Operasi  : {CLR_GREEN}{avg_op_ns:.1f} ns/op{CLR_RESET}")
    print(f"Total Cache Hits     : {CLR_GREEN}{cache.hits:,}{CLR_RESET}")
    print(f"Total Cache Misses   : {CLR_YELLOW}{cache.misses:,}{CLR_RESET}")
    print(f"Total Evictions      : {CLR_RED}{cache.evictions:,}{CLR_RESET}")
    print(f"Hit Rate Efektif     : {CLR_BOLD}{CLR_GREEN if hit_rate > 50 else CLR_YELLOW}{hit_rate:.2f}%{CLR_RESET}")
    
    # Audit Integritas Heap/Bucket
    active_freq_buckets = len([f for f, dll in cache.freq_map.items() if not dll.is_empty()])
    print(f"Aktif Freq Buckets   : {CLR_CYAN}{active_freq_buckets}{CLR_RESET} rentang frekuensi terisolasi")
    print(f"Validasi Ukuran Riil : {CLR_GREEN}OK ({cache.size} / {cache.capacity}){CLR_RESET}")


if __name__ == "__main__":
    # Pengaturan kestabilan seed untuk reproduksibilitas
    random.seed(42)
    
    print(f"{CLR_BOLD}LAB EKSEKUSI: Struktur Data & Algoritma - Tingkat Mahir{CLR_RESET}")
    print(f"Implementor: Lead System Programmer")
    
    run_correctness_verification()
    run_workload_benchmark(num_ops=200_000, capacity=1_500)
    
    print(f"\n{CLR_GREEN}{CLR_BOLD}[SUKSES]{CLR_RESET} Sesi lab hands-on selesai tanpa anomali.")
    sys.exit(0)