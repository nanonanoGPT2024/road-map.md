#!/usr/bin/env python3
"""
===============================================================================
LAB HANDS-ON: 01-Core-Foundations / Bab 02: Memory Hierarchy & Cache Emulation
===============================================================================
Deskripsi:
  Script ini mengimplementasikan simulasi arsitektur perangkat keras memori
  nyata: N-Way Set-Associative Cache dengan kebijakan penggantian LRU
  (Least Recently Used) dan Write-Back/Write-Allocate.
  
  Mendemonstrasikan:
  1. Mekanisme Bit Splitting (Tag, Set Index, Block Offset).
  2. Latency Penalty: Cache Hit vs Cache Miss (Memori Utama / RAM).
  3. Benchmarking Temporal & Spatial Locality (Row-Major vs Column-Major Traversal).
===============================================================================
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import math
import sys
import time

# --- ANSI Formatting Constants ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_CYAN   = "\033[96m"

@dataclass
class CacheLine:
    """Representasi satu baris cache hardware."""
    valid: bool = False
    dirty: bool = False
    tag: int = 0
    data: bytearray = field(default_factory=bytearray)
    last_access_cycle: int = 0

class SetAssociativeCache:
    """
    Simulasi N-Way Set-Associative Cache.
    
    Format Alamat Memori (32-bit):
    [             TAG             |   SET INDEX   |  BYTE OFFSET  ]
    [ (32 - index_bits - off_bits)|  index_bits   |  offset_bits  ]
    """
    def __init__(self, total_size_bytes: int, block_size_bytes: int, ways: int):
        self.total_size = total_size_bytes
        self.block_size = block_size_bytes
        self.ways = ways
        
        self.num_lines = total_size_bytes // block_size_bytes
        self.num_sets = self.num_lines // ways
        
        # Validasi eksponen 2 untuk operasi bitwise
        assert (block_size_bytes & (block_size_bytes - 1)) == 0, "Block size harus kelipatan 2"
        assert (self.num_sets & (self.num_sets - 1)) == 0, "Jumlah sets harus kelipatan 2"
        
        self.offset_bits = int(math.log2(block_size_bytes))
        self.index_bits = int(math.log2(self.num_sets))
        self.tag_bits = 32 - self.index_bits - self.offset_bits
        
        # Masking bit
        self.offset_mask = (1 << self.offset_bits) - 1
        self.index_mask = (1 << self.index_bits) - 1
        
        # Inisialisasi Bank Cache Set
        self.sets: List[List[CacheLine]] = [
            [CacheLine(data=bytearray(self.block_size)) for _ in range(self.ways)]
            for _ in range(self.num_sets)
        ]
        
        # Metrik Siklus & Operasi
        self.cycle_counter: int = 0
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0
        self.writebacks: int = 0
        
        # Konfigurasi Latensi Akses (Simulasi Siklus Clock CPU)
        self.LATENCY_L1_HIT = 1        # 1 cycle hit
        self.LATENCY_RAM_PENALTY = 100  # 100 cycles penalty per round-trip RAM

    def _decode_address(self, address: int) -> Tuple[int, int, int]:
        """Memecah alamat byte 32-bit menjadi Tag, Index Set, dan Block Offset."""
        offset = address & self.offset_mask
        set_idx = (address >> self.offset_bits) & self.index_mask
        tag = address >> (self.offset_bits + self.index_bits)
        return tag, set_idx, offset

    def read_byte(self, address: int, ram: bytearray) -> Tuple[int, int]:
        """
        Membaca byte dari cache. Jika Miss, lakukan fetch line dari RAM.
        Mengembalikan tuple: (nilai_byte, siklus_yang_dibutuhkan).
        """
        self.cycle_counter += 1
        tag, set_idx, offset = self._decode_address(address)
        cache_set = self.sets[set_idx]
        
        # 1. Evaluasi Hit
        for line in cache_set:
            if line.valid and line.tag == tag:
                self.hits += 1
                line.last_access_cycle = self.cycle_counter
                return line.data[offset], self.LATENCY_L1_HIT
        
        # 2. Cache Miss: Memerlukan load dari Main Memory
        self.misses += 1
        cycles_consumed = self.LATENCY_L1_HIT + self.LATENCY_RAM_PENALTY
        
        # Cari slot kosong atau korban LRU (Least Recently Used)
        target_line = self._evict_or_allocate(set_idx, ram)
        
        # Fetch block baru dari RAM ke dalam baris cache
        block_start = (address >> self.offset_bits) << self.offset_bits
        target_line.data[:] = ram[block_start : block_start + self.block_size]
        target_line.valid = True
        target_line.dirty = False
        target_line.tag = tag
        target_line.last_access_cycle = self.cycle_counter
        
        return target_line.data[offset], cycles_consumed

    def write_byte(self, address: int, value: int, ram: bytearray) -> int:
        """
        Menulis byte menggunakan strategi Write-Allocate dan Write-Back.
        Mengembalikan total siklus yang dikonsumsi operasi ini.
        """
        self.cycle_counter += 1
        tag, set_idx, offset = self._decode_address(address)
        cache_set = self.sets[set_idx]
        
        # 1. Evaluasi Hit
        for line in cache_set:
            if line.valid and line.tag == tag:
                self.hits += 1
                line.data[offset] = value & 0xFF
                line.dirty = True  # Modifikasi lokal, belum disinkronkan ke RAM
                line.last_access_cycle = self.cycle_counter
                return self.LATENCY_L1_HIT
        
        # 2. Miss (Write-Allocate): Ambil block ke cache terlebih dahulu
        self.misses += 1
        cycles_consumed = self.LATENCY_L1_HIT + self.LATENCY_RAM_PENALTY
        
        target_line = self._evict_or_allocate(set_idx, ram)
        block_start = (address >> self.offset_bits) << self.offset_bits
        target_line.data[:] = ram[block_start : block_start + self.block_size]
        target_line.valid = True
        target_line.tag = tag
        target_line.data[offset] = value & 0xFF
        target_line.dirty = True
        target_line.last_access_cycle = self.cycle_counter
        
        return cycles_consumed

    def _evict_or_allocate(self, set_idx: int, ram: bytearray) -> CacheLine:
        """Mencari entry invalid atau mengorbankan baris dengan LRU terendah."""
        cache_set = self.sets[set_idx]
        
        # Jalur A: Entry kosong/invalid tersedia
        for line in cache_set:
            if not line.valid:
                return line
        
        # Jalur B: Cache Set Penuh. Pilih LRU victim
        self.evictions += 1
        victim = min(cache_set, key=lambda l: l.last_access_cycle)
        
        # Jika kotor (dirty), lakukan Write-Back ke RAM sebelum overwrite
        if victim.dirty:
            self.writebacks += 1
            # Rekonstruksi alamat fisik blok asal
            evicted_addr = (victim.tag << (self.index_bits + self.offset_bits)) | (set_idx << self.offset_bits)
            ram[evicted_addr : evicted_addr + self.block_size] = victim.data[:]
        
        return victim

    def reset_stats(self):
        """Mereset counter statistik untuk benchmark baru."""
        self.cycle_counter = 0
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.writebacks = 0
        for s in self.sets:
            for line in s:
                line.valid = False
                line.dirty = False
                line.last_access_cycle = 0


# --- BENCHMARK WORKLOADS: LOCALITY DEMONSTRATION ---

def run_locality_benchmark():
    """
    Menguji performa cache saat melintasi matriks 2D (64x64 elemen, 4-byte int).
    Total ukuran data: 64 * 64 * 4 = 16,384 Bytes (16 KB).
    Kapasitas Cache: 4 KB (Direct-Mapped vs 2-Way) -> Miss masif terjadi pada pola buruk.
    """
    DIM = 64
    ELEMENT_SIZE = 4  # 4 bytes integer
    RAM_SIZE = 64 * 1024  # 64 KB RAM
    ram = bytearray(RAM_SIZE)
    
    # 2-Way Set-Associative Cache: Kapasitas 2048 Byte (2 KB), Block 32 Byte
    cache = SetAssociativeCache(total_size_bytes=2048, block_size_bytes=32, ways=2)
    
    print(f"{CLR_BOLD}{CLR_CYAN}=== SISTEM ARSITEKTUR MEMORI: CPU CACHE CONTROLLER EMULATOR ==={CLR_RESET}")
    print(f"Kapasitas Cache : {CLR_YELLOW}{cache.total_size} Bytes{CLR_RESET} ({cache.ways}-Way Set Associative)")
    print(f"Ukuran Blok     : {CLR_YELLOW}{cache.block_size} Bytes{CLR_RESET}")
    print(f"Jumlah Set      : {CLR_YELLOW}{cache.num_sets}{CLR_RESET}")
    print(f"Alamat Decoding : Tag={cache.tag_bits} bits | Index={cache.index_bits} bits | Offset={cache.offset_bits} bits\n")

    # --- PENGUJIAN 1: Row-Major Traversal (High Spatial Locality) ---
    cache.reset_stats()
    total_latency_row = 0
    t0 = time.perf_counter()
    
    for row in range(DIM):
        for col in range(DIM):
            addr = (row * DIM + col) * ELEMENT_SIZE
            # Lakukan baca 4-byte (word)
            for b in range(ELEMENT_SIZE):
                _, cycles = cache.read_byte(addr + b, ram)
                total_latency_row += cycles
                
    time_row = time.perf_counter() - t0
    hits_row = cache.hits
    misses_row = cache.misses
    hit_rate_row = (hits_row / (hits_row + misses_row)) * 100

    print(f"{CLR_BOLD}[1] Uji Traversal: Row-Major (Pola Berurutan / Sequential){CLR_RESET}")
    print(f"  Akses Total   : {hits_row + misses_row:,} ops")
    print(f"  Cache Hits    : {CLR_GREEN}{hits_row:,}{CLR_RESET}")
    print(f"  Cache Misses  : {CLR_RED}{misses_row:,}{CLR_RESET}")
    print(f"  Hit Ratio     : {CLR_GREEN}{hit_rate_row:.2f}%{CLR_RESET}")
    print(f"  Siklus CPU    : {CLR_YELLOW}{total_latency_row:,} cycles{CLR_RESET}")
    print(f"  Waktu Emulasi : {time_row * 1000:.2f} ms\n")

    # --- PENGUJIAN 2: Column-Major Traversal (Cache Thrashing / Zero Spatial Locality) ---
    cache.reset_stats()
    total_latency_col = 0
    t0 = time.perf_counter()
    
    for col in range(DIM):
        for row in range(DIM):
            addr = (row * DIM + col) * ELEMENT_SIZE
            for b in range(ELEMENT_SIZE):
                _, cycles = cache.read_byte(addr + b, ram)
                total_latency_col += cycles
                
    time_col = time.perf_counter() - t0
    hits_col = cache.hits
    misses_col = cache.misses
    hit_rate_col = (hits_col / (hits_col + misses_col)) * 100

    print(f"{CLR_BOLD}[2] Uji Traversal: Column-Major (Pola Melompat / Strided){CLR_RESET}")
    print(f"  Akses Total   : {hits_col + misses_col:,} ops")
    print(f"  Cache Hits    : {CLR_GREEN}{hits_col:,}{CLR_RESET}")
    print(f"  Cache Misses  : {CLR_RED}{misses_col:,}{CLR_RESET}")
    print(f"  Hit Ratio     : {CLR_RED}{hit_rate_col:.2f}%{CLR_RESET}")
    print(f"  Siklus CPU    : {CLR_YELLOW}{total_latency_col:,} cycles{CLR_RESET}")
    print(f"  Waktu Emulasi : {time_col * 1000:.2f} ms\n")

    # --- KOMPARASI PERFORMA ---
    cycle_diff = total_latency_col / total_latency_row if total_latency_row > 0 else 0
    print(f"{CLR_BOLD}{CLR_BLUE}=== EVALUASI ANALISIS SISTEM ==={CLR_RESET}")
    print(f"Penalti Waktu Siklus : Pola Kolom membutuhkan {CLR_RED}{cycle_diff:.2f}x{CLR_RESET} siklus CPU lebih lama!")
    print(f"Penjelasan Teknis    : Pada baris berurutan, blok {cache.block_size}-byte mengambil data tetangga ke L1,")
    print("                       memenuhi spatial locality. Pada akses kolom, pembacaan melompati")
    print(f"                       {DIM * ELEMENT_SIZE} bytes per iterasi, membatalkan isi cache line (Cache Eviction cascade).\n")

if __name__ == "__main__":
    run_locality_benchmark()
