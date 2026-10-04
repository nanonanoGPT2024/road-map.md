#!/usr/bin/env python3
"""
Lab Hands-on: CS Core Foundations - Bab 01 / Modul 02 Deep Dive
Topik: Simulasi Hirarki Memori CPU & Analisis Eviction Policy Multi-Level Cache (L1/L2/RAM)

Deskripsi:
Program ini memodelkan subsistem memori perangkat keras nyata, mencakup:
- Arsitektur Cache 2-Tingkat (L1 & L2) berbasis Cache Lines berukuran tetap.
- Algoritma Penggantian Cache (Cache Eviction Policies): LRU (Least Recently Used) & FIFO.
- Profiling penalti siklus akses (Latency Cost: L1 = 1 cycle, L2 = 10 cycles, RAM = 100 cycles).
- Simulasi pola akses memori nyata: Temporal Locality (Hotspot), Spatial Locality (Sequential),
  dan Cache Thrashing (Strided Access).
"""

from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import random
import sys
import time

# --- ANSI Terminal Color Codes ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_CYAN   = "\033[96m"
CLR_WHITE  = "\033[97m"

@dataclass
class AccessResult:
    level_hit: str       # 'L1', 'L2', atau 'RAM'
    latency_cycles: int  # Total latensi siklus akses memori
    evicted_key: Optional[int] = None

class CacheLevel:
    """
    Representasi satu tingkat cache (L1 atau L2) dengan limit kapasitas entri
    dan strategi pembersihan (LRU atau FIFO).
    """
    def __init__(self, name: str, capacity: int, policy: str = "LRU"):
        self.name = name
        self.capacity = capacity
        self.policy = policy.upper()
        # OrderedDict menyimpan pasangan: block_addr -> payload
        self.storage: OrderedDict[int, int] = OrderedDict()
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    def get(self, block_addr: int) -> bool:
        """Mengecek keberadaan block di cache; memodifikasi urutan bila policy == LRU."""
        if block_addr in self.storage:
            self.hits += 1
            if self.policy == "LRU":
                self.storage.move_to_end(block_addr)
            return True
        self.misses += 1
        return False

    def put(self, block_addr: int, value: int) -> Optional[int]:
        """
        Menyimpan block ke cache. Jika kapasitas penuh, lakukan eviction
        sesuai policy (LRU / FIFO) dan kembalikan block_addr yang dikeluarkan.
        """
        evicted = None
        if block_addr in self.storage:
            if self.policy == "LRU":
                self.storage.move_to_end(block_addr)
            self.storage[block_addr] = value
            return None

        if len(self.storage) >= self.capacity:
            # FIFO / LRU pop elemen tertua di awal
            evicted, _ = self.storage.popitem(last=False)
            self.evictions += 1

        self.storage[block_addr] = value
        return evicted

    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100.0) if total > 0 else 0.0


class MemorySubsystem:
    """
    Mengintegrasikan L1 Cache, L2 Cache, dan simulated Backing RAM.
    Menghitung latensi agregat berdasarkan siklus akses hardware riil:
      - L1 Hit: 1 cycle
      - L2 Hit: 10 cycles (1 cycle L1 miss + 9 cycles L2 fetch)
      - RAM Hit: 100 cycles (1 L1 miss + 9 L2 miss + 90 cycles RAM fetch)
    """
    L1_LATENCY = 1
    L2_LATENCY = 10
    RAM_LATENCY = 100
    BLOCK_SIZE = 64  # Ukuran Cache Line dalam bytes

    def __init__(self, l1_size: int = 4, l2_size: int = 16, policy: str = "LRU"):
        self.l1 = CacheLevel("L1", l1_size, policy)
        self.l2 = CacheLevel("L2", l2_size, policy)
        self.ram: Dict[int, int] = {}
        self.total_cycles: int = 0
        self.access_count: int = 0

    def _to_block_addr(self, byte_addr: int) -> int:
        """Memetakan alamat byte memory fisik ke cache line block address."""
        return byte_addr // self.BLOCK_SIZE

    def access(self, byte_addr: int) -> AccessResult:
        """
        Mensimulasikan satu memory read-through. Data dicari dari L1 -> L2 -> RAM.
        Menerapkan write-allocate / fetch-on-miss policy ke level atas.
        """
        self.access_count += 1
        block_addr = self._to_block_addr(byte_addr)
        
        # 1. Cek L1
        if self.l1.get(block_addr):
            self.total_cycles += self.L1_LATENCY
            return AccessResult("L1", self.L1_LATENCY)

        # 2. L1 Miss -> Cek L2
        if self.l2.get(block_addr):
            # Tarik data dari L2 ke L1 (Inclusive/Promote)
            val = self.l2.storage[block_addr]
            evicted_l1 = self.l1.put(block_addr, val)
            self.total_cycles += self.L2_LATENCY
            return AccessResult("L2", self.L2_LATENCY, evicted_key=evicted_l1)

        # 3. L2 Miss -> Fetch dari RAM
        if block_addr not in self.ram:
            # Simulasi initial DRAM cold load
            self.ram[block_addr] = random.randint(0x00, 0xFF)

        val = self.ram[block_addr]
        
        # Isi ke L2 terlebih dahulu
        evicted_l2 = self.l2.put(block_addr, val)
        # Kemudian isi ke L1
        evicted_l1 = self.l1.put(block_addr, val)

        self.total_cycles += self.RAM_LATENCY
        return AccessResult("RAM", self.RAM_LATENCY, evicted_key=evicted_l1)

    def print_telemetry(self):
        """Menampilkan metrik statistik kinerja memori."""
        amat = self.total_cycles / self.access_count if self.access_count > 0 else 0
        print(f"  Total Accesses      : {self.access_count}")
        print(f"  Total Cycles Expended: {self.total_cycles:,} cycles")
        print(f"  AMAT (Avg Memory Access Time): {CLR_BOLD}{amat:.2f} cycles/access{CLR_RESET}")
        print(f"  L1 Hit Rate         : {CLR_GREEN}{self.l1.hit_rate():.2f}%{CLR_RESET} "
              f"(Hits: {self.l1.hits}, Misses: {self.l1.misses}, Evictions: {self.l1.evictions})")
        print(f"  L2 Hit Rate         : {CLR_GREEN}{self.l2.hit_rate():.2f}%{CLR_RESET} "
              f"(Hits: {self.l2.hits}, Misses: {self.l2.misses}, Evictions: {self.l2.evictions})")


def run_workload_simulation(name: str, description: str, addresses: List[int], policy: str):
    """Mengeksekusi workload spesifik terhadap subsistem memori."""
    print(f"\n{CLR_CYAN}{'=' * 75}{CLR_RESET}")
    print(f"{CLR_BOLD}[WORKLOAD: {name.upper()} | POLICY: {policy}]{CLR_RESET}")
    print(f"{CLR_WHITE}{description}{CLR_RESET}")
    print(f"{CLR_CYAN}{'=' * 75}{CLR_RESET}")

    mem = MemorySubsystem(l1_size=8, l2_size=32, policy=policy)
    
    # Track ringkasan sampel
    l1_hits = 0
    l2_hits = 0
    ram_hits = 0

    for addr in addresses:
        res = mem.access(addr)
        if res.level_hit == "L1":
            l1_hits += 1
        elif res.level_hit == "L2":
            l2_hits += 1
        else:
            ram_hits += 1

    mem.print_telemetry()
    print(f"  Hit Distribution    : L1={l1_hits} | L2={l2_hits} | RAM={ram_hits}")


def generate_temporal_workload(num_accesses: int = 1000) -> List[int]:
    """Menghasilkan pola akses Temporal Locality: 80% akses tertuju pada 20% alamat."""
    hot_set = [i * 64 for i in range(4)]       # 4 hot blocks (muat di L1)
    cold_set = [i * 64 for i in range(10, 80)] # Banyak cold blocks
    workload = []
    for _ in range(num_accesses):
        if random.random() < 0.85:
            workload.append(random.choice(hot_set))
        else:
            workload.append(random.choice(cold_set))
    return workload


def generate_spatial_workload(num_lines: int = 200, stride: int = 4) -> List[int]:
    """Menghasilkan pola akses Sequential/Spatial: Akses byte berkelanjutan."""
    return [addr for addr in range(0, num_lines * 64, stride)]


def generate_thrashing_workload(num_accesses: int = 1000) -> List[int]:
    """
    Menghasilkan pola Cache Thrashing / Stride Besar:
    Meminta alamat yang memetakan ke set cache yang sama secara berulang melebihi kapasitas L1/L2.
    """
    # 64 block unik, diakses secara circular loop, menyebabkan rolling cache evictions konstan
    loop_set = [i * 1024 for i in range(40)]
    workload = []
    for _ in range(num_accesses // len(loop_set) + 1):
        workload.extend(loop_set)
    return workload[:num_accesses]


def main():
    print(f"{CLR_YELLOW}{CLR_BOLD}")
    print("=" * 75)
    print(" LAB HANDS-ON: SIMULATOR HIRARKI MEMORI CPU (L1/L2/RAM CACHE ENGINE)")
    print("=" * 75)
    print(f"{CLR_RESET}")

    random.seed(42)

    # 1. Eksperimen Temporal Locality (LRU vs FIFO)
    temporal_data = generate_temporal_workload(1200)
    run_workload_simulation(
        name="Temporal Locality (Hotspot Loops)",
        description="Akses terkonsentrasi pada working set kecil berulang kali (Loop counter / lokal variabel).",
        addresses=temporal_data,
        policy="LRU"
    )

    run_workload_simulation(
        name="Temporal Locality under FIFO Policy",
        description="Akses dataset yang sama menggunakan FIFO eviction policy sebagai pembanding kinerja.",
        addresses=temporal_data,
        policy="FIFO"
    )

    # 2. Eksperimen Spatial Locality (Sequential Array Traversal)
    spatial_data = generate_spatial_workload(num_lines=150, stride=8)
    run_workload_simulation(
        name="Spatial Locality (Sequential Array Iteration)",
        description="Iterasi memori linear rapat (Step kecil di dalam cache line 64-byte yang sama).",
        addresses=spatial_data,
        policy="LRU"
    )

    # 3. Eksperimen Cache Thrashing
    thrashing_data = generate_thrashing_workload(1200)
    run_workload_simulation(
        name="Pathological Cache Thrashing (Stride Jump)",
        description="Akses looping pada set alamat yang melampaui ukuran L1 dan L2 secara periodik konstan.",
        addresses=thrashing_data,
        policy="LRU"
    )

    print(f"\n{CLR_GREEN}{CLR_BOLD}[LAB COMPLETE] Simulasi arsitektur subsistem memori selesai tanpa anomali.{CLR_RESET}\n")

if __name__ == "__main__":
    main()
