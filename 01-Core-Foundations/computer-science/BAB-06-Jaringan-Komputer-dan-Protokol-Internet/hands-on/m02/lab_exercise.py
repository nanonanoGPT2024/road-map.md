#!/usr/bin/env python3
"""
Lab Hands-on: CS Core Foundations - Deep Dive: Memory Hierarchy & Cache Coherency Simulation
Simulasi Multi-Level Cache (L1, L2, L3) + DRAM Controller dengan N-Way Set Associative & LRU.
Mengevaluasi Average Memory Access Time (AMAT), Locality of Reference (Spatial vs Temporal),
serta dampaknya pada performa komputasi berkecepatan tinggi.
"""

import sys
import math
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_CYAN = "\033[36m"
CLR_MAGENTA = "\033[35m"

@dataclass
class CacheLine:
    """Merepresentasikan satu baris cache (Cache Line/Slot)."""
    valid: bool = False
    dirty: bool = False
    tag: int = 0
    last_access_tick: int = 0

class CacheSet:
    """Kumpulan CacheLine dengan kebijakan eviksi Least Recently Used (LRU)."""
    def __init__(self, associativity: int):
        self.associativity = associativity
        self.lines: List[CacheLine] = [CacheLine() for _ in range(associativity)]

    def lookup(self, tag: int) -> Optional[CacheLine]:
        """Cari tag yang cocok dan valid di dalam set."""
        for line in self.lines:
            if line.valid and line.tag == tag:
                return line
        return None

    def allocate(self, tag: int, current_tick: int) -> Tuple[CacheLine, bool]:
        """
        Alokasikan slot untuk tag baru.
        Mengembalikan (slot_terpilih, dirty_eviction).
        """
        # 1. Cari slot invalid terlebih dahulu
        for line in self.lines:
            if not line.valid:
                line.valid = True
                line.dirty = False
                line.tag = tag
                line.last_access_tick = current_tick
                return line, False

        # 2. Jika penuh, eviksi line dengan tick paling usang (LRU)
        lru_line = min(self.lines, key=lambda l: l.last_access_tick)
        dirty_eviction = lru_line.dirty
        
        # Inisialisasi ulang slot LRU
        lru_line.valid = True
        lru_line.dirty = False
        lru_line.tag = tag
        lru_line.last_access_tick = current_tick
        return lru_line, dirty_eviction

class CacheLevel:
    """
    Satu layer dalam hierarki cache (L1, L2, atau L3).
    Menghitung address mapping: Tag, Index, Offset bits.
    """
    def __init__(self, name: str, size_bytes: int, associativity: int, block_size_bytes: int, latency_ns: float):
        self.name = name
        self.size_bytes = size_bytes
        self.associativity = associativity
        self.block_size = block_size_bytes
        self.latency_ns = latency_ns

        # Validasi properti biner
        assert (size_bytes & (size_bytes - 1)) == 0, "Ukuran cache harus pangkat dua."
        assert (block_size_bytes & (block_size_bytes - 1)) == 0, "Block size harus pangkat dua."

        self.num_lines = size_bytes // block_size_bytes
        self.num_sets = self.num_lines // associativity
        assert (self.num_sets & (self.num_sets - 1)) == 0, "Jumlah set harus pangkat dua."

        self.offset_bits = int(math.log2(block_size_bytes))
        self.index_bits = int(math.log2(self.num_sets))
        self.tag_bits = 64 - (self.offset_bits + self.index_bits)

        self.index_mask = self.num_sets - 1
        self.sets = [CacheSet(associativity) for _ in range(self.num_sets)]

        # Metrik performa
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.dirty_writebacks = 0

    def parse_address(self, addr: int) -> Tuple[int, int, int]:
        """Dekomposisi 64-bit pointer address menjadi (Tag, Index, Offset)."""
        offset = addr & ((1 << self.offset_bits) - 1)
        idx = (addr >> self.offset_bits) & self.index_mask
        tag = addr >> (self.offset_bits + self.index_bits)
        return tag, idx, offset

    def access(self, addr: int, is_write: bool, current_tick: int) -> Tuple[bool, bool]:
        """
        Mengecek keberadaan data di cache.
        Returns: (hit: bool, evicted_dirty: bool)
        """
        tag, idx, _ = self.parse_address(addr)
        cset = self.sets[idx]
        line = cset.lookup(tag)

        if line:
            self.hits += 1
            line.last_access_tick = current_tick
            if is_write:
                line.dirty = True
            return True, False
        else:
            self.misses += 1
            allocated_line, dirty_eviction = cset.allocate(tag, current_tick)
            if dirty_eviction:
                self.dirty_writebacks += 1
            self.evictions += 1
            if is_write:
                allocated_line.dirty = True
            return False, dirty_eviction

class MemorySubsystem:
    """
    Controller Memory Hierarkis terintegrasi: L1 -> L2 -> L3 -> DRAM Main Memory.
    """
    def __init__(self):
        # Konfigurasi latensi modern:
        # L1: 32 KB, 8-way, ~1.2 ns (~4 cycle)
        # L2: 256 KB, 8-way, ~4.5 ns (~14 cycle)
        # L3: 2 MB, 16-way, ~15.0 ns (~45 cycle)
        # DRAM: ~75.0 ns (~220 cycle)
        self.l1 = CacheLevel("L1-Data", size_bytes=32 * 1024, associativity=8, block_size_bytes=64, latency_ns=1.2)
        self.l2 = CacheLevel("L2-Shared", size_bytes=256 * 1024, associativity=8, block_size_bytes=64, latency_ns=4.5)
        self.l3 = CacheLevel("L3-LLC", size_bytes=2 * 1024 * 1024, associativity=16, block_size_bytes=64, latency_ns=15.0)
        self.dram_latency_ns = 75.0
        
        self.current_tick = 0
        self.total_accesses = 0
        self.total_penalty_ns = 0.0

    def memory_access(self, address: int, is_write: bool = False) -> float:
        """
        Simulasi alur traversing hardware memory saat CPU meminta address tertentu.
        Menghitung total cumulative stall/access latency (ns).
        """
        self.current_tick += 1
        self.total_accesses += 1
        access_latency = self.l1.latency_ns

        # Akses L1
        l1_hit, l1_dirty = self.l1.access(address, is_write, self.current_tick)
        if l1_hit:
            self.total_penalty_ns += access_latency
            return access_latency

        # Akses L2
        access_latency += self.l2.latency_ns
        l2_hit, l2_dirty = self.l2.access(address, is_write, self.current_tick)
        if l2_hit:
            self.total_penalty_ns += access_latency
            return access_latency

        # Akses L3 (Last Level Cache)
        access_latency += self.l3.latency_ns
        l3_hit, l3_dirty = self.l3.access(address, is_write, self.current_tick)
        if l3_hit:
            self.total_penalty_ns += access_latency
            return access_latency

        # L3 Miss -> DRAM Access
        access_latency += self.dram_latency_ns
        self.total_penalty_ns += access_latency
        return access_latency

    def print_diagnostics(self):
        """Menampilkan metrik performa tiap tingkatan memory secara terformat."""
        amat = self.total_penalty_ns / max(1, self.total_accesses)
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== LAPORAN TELEMETRI SISTEM MEMORI ==={CLR_RESET}")
        print(f"Total Operasi Memori: {CLR_BOLD}{self.total_accesses:,}{CLR_RESET}")
        print(f"Average Memory Access Time (AMAT): {CLR_BOLD}{CLR_YELLOW}{amat:.3f} ns{CLR_RESET}\n")

        header = f"{'Layer':<12} | {'Akses':<9} | {'Hits':<9} | {'Misses':<9} | {'Hit Rate':<9} | {'Evictions':<9}"
        print(CLR_BOLD + header + CLR_RESET)
        print("-" * len(header))

        for cache in [self.l1, self.l2, self.l3]:
            total = cache.hits + cache.misses
            rate = (cache.hits / total * 100.0) if total > 0 else 0.0
            print(f"{cache.name:<12} | {total:<9} | {cache.hits:<9} | {cache.misses:<9} | {rate:>7.2f}% | {cache.evictions:<9}")

        dram_fetches = self.l3.misses
        print("-" * len(header))
        print(f"{'DRAM (RAM)':<12} | {dram_fetches:<9} | {'-':<9} | {'-':<9} | {'0.00%':<9} | {'-':<9}\n")

def simulate_workloads():
    """
    Eksekusi dua pola akses memori berlawanan:
    1. Sequential Processing (Row-major traversal - Optimal Spatial Locality)
    2. Strided / Matrix Transposition (Column-major traversal - Cache Trashing)
    """
    print(f"{CLR_BOLD}{CLR_MAGENTA}------------------------------------------------------------{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}   LAB ARCHITECTURE: EFEK LOCALITY PADA CACHE PERFORMANCE   {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}------------------------------------------------------------{CLR_RESET}")

    matrix_rows = 128
    matrix_cols = 128
    element_size = 8  # 64-bit float / integer = 8 bytes
    base_address = 0x7FFF00000000

    # -------------------------------------------------------------
    # SKENARIO 1: Sequential Access (Row-Major Order)
    # -------------------------------------------------------------
    print(f"\n{CLR_BOLD}[EKSPERIMEN 1]{CLR_RESET} Menjalankan Traversing Row-Major ({CLR_GREEN}Spatial Locality Tinggi{CLR_RESET})...")
    mem_seq = MemorySubsystem()
    start_time = time.perf_counter()

    for r in range(matrix_rows):
        for c in range(matrix_cols):
            # Rumus Row-major: base + (r * COLS + c) * element_size
            addr = base_address + (r * matrix_cols + c) * element_size
            mem_seq.memory_access(addr, is_write=False)

    exec_time_seq = time.perf_counter() - start_time
    mem_seq.print_diagnostics()

    # -------------------------------------------------------------
    # SKENARIO 2: Strided Access (Column-Major Order)
    # -------------------------------------------------------------
    print(f"{CLR_BOLD}[EKSPERIMEN 2]{CLR_RESET} Menjalankan Traversing Column-Major ({CLR_RED}Cache Trashing / Bad Stride{CLR_RESET})...")
    mem_strided = MemorySubsystem()
    start_time = time.perf_counter()

    for c in range(matrix_cols):
        for r in range(matrix_rows):
            # Rumus Column-major: base + (r * COLS + c) * element_size (stride loncat 128 * 8 = 1024 byte)
            addr = base_address + (r * matrix_cols + c) * element_size
            mem_strided.memory_access(addr, is_write=False)

    exec_time_str = time.perf_counter() - start_time
    mem_strided.print_diagnostics()

    # Analisis Komparatif
    amat_seq = mem_seq.total_penalty_ns / mem_seq.total_accesses
    amat_str = mem_strided.total_penalty_ns / mem_strided.total_accesses
    speedup = amat_str / amat_seq

    print(f"{CLR_BOLD}{CLR_YELLOW}=== KESIMPULAN ANALISIS ARSITEKTUR ==={CLR_RESET}")
    print(f"Row-major AMAT     : {CLR_GREEN}{amat_seq:.3f} ns / fetch{CLR_RESET}")
    print(f"Column-major AMAT  : {CLR_RED}{amat_str:.3f} ns / fetch{CLR_RESET}")
    print(f"Penurunan Latensi  : {CLR_BOLD}{CLR_CYAN}{speedup:.2f}x lebih cepat{CLR_RESET} dengan mematuhi spatial locality.")
    print(f"L1 Hit Rate Delta  : {CLR_GREEN}{(mem_seq.l1.hits/mem_seq.total_accesses)*100:.1f}%{CLR_RESET} (Row-major) vs {CLR_RED}{(mem_strided.l1.hits/mem_strided.total_accesses)*100:.1f}%{CLR_RESET} (Column-major)\n")

if __name__ == "__main__":
    simulate_workloads()