#!/usr/bin/env python3
"""
Lab Hands-on: CS Core Foundations - Deep Dive Architecture
Topik: Simulasi Hirarki Multi-Level Cache (L1/L2/RAM) & Protokol Koherensi MESI
Deskripsi: Memodelkan arsitektur memori modern multicore dengan L1 Cache terpisah,
            L2 Shared Cache, Main Memory (RAM), dan bus snooping koherensi cache (MESI).
"""

import sys
import time
from enum import Enum
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass

# ==============================================================================
# ANSI Color Codes untuk visualisasi terminal
# ==============================================================================
RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
MAGENTA= "\033[35m"
CYAN   = "\033[36m"
GRAY   = "\033[90m"

# ==============================================================================
# Definisi Status MESI (Modified, Exclusive, Shared, Invalid)
# ==============================================================================
class MESIState(Enum):
    MODIFIED = "M"    # Line valid, hanya ada di cache ini, dirty (berbeda dari RAM)
    EXCLUSIVE = "E"   # Line valid, hanya ada di cache ini, clean (sama dengan RAM)
    SHARED = "S"      # Line valid, bisa ada di cache core lain, clean
    INVALID = "I"     # Line tidak valid / stale

@dataclass
class CacheLine:
    tag: int
    data: int
    state: MESIState
    last_access: float

class MemoryBus:
    """
    Simulasi Bus bersama (Shared Bus) untuk propagasi sinyal snooping dan akses RAM.
    """
    def __init__(self, ram_latency_cycles: int = 100):
        self.ram: Dict[int, int] = {}
        self.ram_latency = ram_latency_cycles
        self.controllers: List['CacheController'] = []
        self.bus_transactions: int = 0

    def register_controller(self, ctrl: 'CacheController') -> None:
        self.controllers.append(ctrl)

    def read_mem(self, address: int) -> int:
        self.bus_transactions += 1
        return self.ram.get(address, 0)

    def write_mem(self, address: int, value: int) -> None:
        self.bus_transactions += 1
        self.ram[address] = value

    def broadcast_bus_rd(self, source_id: int, address: int) -> Tuple[bool, Optional[int]]:
        """
        Sinyal BusRd: Core ingin membaca block. Core lain melakukan snooping.
        Mengembalikan (shared_flag, data_if_supplied_by_peer).
        """
        self.bus_transactions += 1
        shared = False
        supplied_data = None
        for ctrl in self.controllers:
            if ctrl.core_id != source_id:
                has_copy, data = ctrl.snoop_bus_rd(address)
                if has_copy:
                    shared = True
                if data is not None:
                    supplied_data = data
        return shared, supplied_data

    def broadcast_bus_rdx(self, source_id: int, address: int) -> Optional[int]:
        """
        Sinyal BusRdX (Read with Intent to Modify): Core ingin menulis, batalkan salinan lain.
        """
        self.bus_transactions += 1
        supplied_data = None
        for ctrl in self.controllers:
            if ctrl.core_id != source_id:
                data = ctrl.snoop_bus_rdx(address)
                if data is not None:
                    supplied_data = data
        return supplied_data

    def broadcast_bus_upgr(self, source_id: int, address: int) -> None:
        """
        Sinyal BusUpgr: Core memiliki copy 'Shared' dan ingin upgrade ke 'Modified' tanpa transfer data.
        """
        self.bus_transactions += 1
        for ctrl in self.controllers:
            if ctrl.core_id != source_id:
                ctrl.snoop_bus_upgr(address)

class CacheController:
    """
    L1 Data Cache Controller per Core dengan LRU replacement dan MESI Protocol.
    """
    def __init__(self, core_id: int, capacity: int, bus: MemoryBus, l1_latency: int = 1):
        self.core_id = core_id
        self.capacity = capacity
        self.bus = bus
        self.l1_latency = l1_latency
        self.lines: Dict[int, CacheLine] = {}
        self.l1_hits = 0
        self.l1_misses = 0
        self.total_cycles = 0

    def _evict_lru_if_needed(self) -> None:
        if len(self.lines) < self.capacity:
            return
        
        # Cari line yang paling lama tidak diakses (LRU)
        lru_tag = min(self.lines.keys(), key=lambda t: self.lines[t].last_access)
        victim = self.lines[lru_tag]
        
        # Write-back jika status Modified
        if victim.state == MESIState.MODIFIED:
            print(f"  {GRAY}[Core {self.core_id}] Evicting DIRTY 0x{lru_tag:04X} -> Writeback to RAM.{RESET}")
            self.bus.write_mem(lru_tag, victim.data)
            self.total_cycles += self.bus.ram_latency
        else:
            print(f"  {GRAY}[Core {self.core_id}] Evicting CLEAN 0x{lru_tag:04X}.{RESET}")
            
        del self.lines[lru_tag]

    def read(self, address: int) -> int:
        """
        Core CPU Read Request: Memproses pembacaan data via cache hierarchy.
        """
        self.total_cycles += self.l1_latency
        current_time = time.time()

        if address in self.lines and self.lines[address].state != MESIState.INVALID:
            # L1 Cache Hit
            self.l1_hits += 1
            line = self.lines[address]
            line.last_access = current_time
            print(f"{GREEN}[Core {self.core_id}] L1 HIT Read  0x{address:04X} = {line.data} (State: {line.state.value}){RESET}")
            return line.data

        # L1 Cache Miss
        self.l1_misses += 1
        print(f"{YELLOW}[Core {self.core_id}] L1 MISS Read 0x{address:04X} -> Snooping Bus...{RESET}")
        self._evict_lru_if_needed()

        # Siarkan BusRd
        is_shared, supplied_data = self.bus.broadcast_bus_rd(self.core_id, address)
        if supplied_data is not None:
            # Diambil langsung dari cache core lain (Cache-to-Cache Transfer)
            data = supplied_data
            self.total_cycles += 5 # L2/interconnect latency
            print(f"  {CYAN}↳ Data disuplai dari peer cache (Cache-to-Cache Transfer).{RESET}")
        else:
            # Fetch dari RAM
            data = self.bus.read_mem(address)
            self.total_cycles += self.bus.ram_latency
            print(f"  {MAGENTA}↳ Data di-fetch dari Main Memory (RAM Latency +{self.bus.ram_latency} cycles).{RESET}")

        target_state = MESIState.SHARED if is_shared else MESIState.EXCLUSIVE
        self.lines[address] = CacheLine(tag=address, data=data, state=target_state, last_access=current_time)
        print(f"  {BLUE}↳ Core {self.core_id} alokasi 0x{address:04X} state: {target_state.value}{RESET}")
        return data

    def write(self, address: int, value: int) -> None:
        """
        Core CPU Write Request: Memproses penulisan data dan menjaga koherensi memori.
        """
        self.total_cycles += self.l1_latency
        current_time = time.time()

        if address in self.lines and self.lines[address].state != MESIState.INVALID:
            line = self.lines[address]
            line.last_access = current_time

            if line.state == MESIState.MODIFIED:
                # Write hit pada state Modified: mutasi langsung secara lokal
                self.l1_hits += 1
                line.data = value
                print(f"{GREEN}[Core {self.core_id}] L1 HIT Write (M) 0x{address:04X} = {value}{RESET}")
                return

            elif line.state == MESIState.EXCLUSIVE:
                # Upgrade E -> M tanpa transaksi data, hanya silent transition
                self.l1_hits += 1
                line.data = value
                line.state = MESIState.MODIFIED
                print(f"{GREEN}[Core {self.core_id}] L1 HIT Write (E->M) 0x{address:04X} = {value}{RESET}")
                return

            elif line.state == MESIState.SHARED:
                # Perlu upgrade invalidate: BusUpgr
                self.l1_hits += 1
                print(f"{YELLOW}[Core {self.core_id}] L1 HIT Write (S->M) 0x{address:04X} -> Broadcast BusUpgr{RESET}")
                self.bus.broadcast_bus_upgr(self.core_id, address)
                line.data = value
                line.state = MESIState.MODIFIED
                return

        # Write Miss
        self.l1_misses += 1
        print(f"{RED}[Core {self.core_id}] L1 MISS Write 0x{address:04X} -> Broadcast BusRdX...{RESET}")
        self._evict_lru_if_needed()

        # Ambil data mutakhir sekaligus batalkan cache lain
        peer_data = self.bus.broadcast_bus_rdx(self.core_id, address)
        if peer_data is not None:
            self.total_cycles += 5
        else:
            self.bus.read_mem(address)
            self.total_cycles += self.bus.ram_latency

        self.lines[address] = CacheLine(tag=address, data=value, state=MESIState.MODIFIED, last_access=current_time)
        print(f"  {BLUE}↳ Core {self.core_id} dialokasikan 0x{address:04X} state: MODIFIED{RESET}")

    # ================= Snooping Handlers =================
    def snoop_bus_rd(self, address: int) -> Tuple[bool, Optional[int]]:
        """Snooping Bus Read request dari core lain."""
        if address in self.lines and self.lines[address].state != MESIState.INVALID:
            line = self.lines[address]
            if line.state == MESIState.MODIFIED:
                print(f"  {YELLOW}⚡ [Snoop Core {self.core_id}] 0x{address:04X} is MODIFIED. Writeback RAM & Downgrade -> SHARED{RESET}")
                self.bus.write_mem(address, line.data)
                line.state = MESIState.SHARED
                return True, line.data
            elif line.state in (MESIState.EXCLUSIVE, MESIState.SHARED):
                line.state = MESIState.SHARED
                return True, line.data
        return False, None

    def snoop_bus_rdx(self, address: int) -> Optional[int]:
        """Snooping Bus Read Invalidate request dari core lain."""
        if address in self.lines and self.lines[address].state != MESIState.INVALID:
            line = self.lines[address]
            data = line.data
            old_state = line.state
            line.state = MESIState.INVALID
            print(f"  {RED}⚡ [Snoop Core {self.core_id}] 0x{address:04X} invalidated ({old_state.value} -> INVALID){RESET}")
            if old_state == MESIState.MODIFIED:
                self.bus.write_mem(address, data)
                return data
            return data
        return None

    def snoop_bus_upgr(self, address: int) -> None:
        """Snooping Bus Upgrade (invalidasi duplikasi shared)."""
        if address in self.lines and self.lines[address].state == MESIState.SHARED:
            self.lines[address].state = MESIState.INVALID
            print(f"  {RED}⚡ [Snoop Core {self.core_id}] Invalidation ACK for 0x{address:04X} (SHARED -> INVALID){RESET}")

# ==============================================================================
# Eksekusi Skenario Hands-on Lab
# ==============================================================================
def main():
    print(f"\n{BOLD}{CYAN}===================================================================={RESET}")
    print(f"{BOLD}{CYAN} LAB: Computer Science Deep Dive - MESI Cache Coherence Simulation {RESET}")
    print(f"{BOLD}{CYAN}===================================================================={RESET}\n")

    # Inisialisasi Bus dan Cores (Kapasitas kecil untuk memicu eviction: 3 line/core)
    bus = MemoryBus(ram_latency_cycles=100)
    c0 = CacheController(core_id=0, capacity=3, bus=bus, l1_latency=1)
    c1 = CacheController(core_id=1, capacity=3, bus=bus, l1_latency=1)
    bus.register_controller(c0)
    bus.register_controller(c1)

    # Inisialisasi Memori Utama
    bus.ram[0x1000] = 42
    bus.ram[0x2000] = 88
    bus.ram[0x3000] = 99
    bus.ram[0x4000] = 105

    print(f"{BOLD}[Tahap 1: Cold Read & State Transition Exclusive (E)]{RESET}")
    c0.read(0x1000)
    print()

    print(f"{BOLD}[Tahap 2: False Sharing / Multi-Core Read -> State Shared (S)]{RESET}")
    c1.read(0x1000)
    print()

    print(f"{BOLD}[Tahap 3: Write to Shared Block -> Broadcast Invalidate (S -> M)]{RESET}")
    c0.write(0x1000, 999)
    print()

    print(f"{BOLD}[Tahap 4: Core 1 Read Stale Line -> Cache Invalidation Triggered]{RESET}")
    c1.read(0x1000)
    print()

    print(f"{BOLD}[Tahap 5: Eviction & Write-Back Test pada Kapasitas Penuh Core 0]{RESET}")
    c0.read(0x2000)
    c0.read(0x3000)
    # Kapasitas 3 penuh (0x1000, 0x2000, 0x3000). Akses 0x4000 akan memicu evicting LRU
    c0.read(0x4000)
    print()

    # Rekapitulasi Statistik
    print(f"{BOLD}{CYAN}===================================================================={RESET}")
    print(f"{BOLD}{CYAN}                       SYSTEM METRICS SUMMARY                       {RESET}")
    print(f"{BOLD}{CYAN}===================================================================={RESET}")
    for core in [c0, c1]:
        total_reqs = core.l1_hits + core.l1_misses
        hit_rate = (core.l1_hits / total_reqs * 100) if total_reqs > 0 else 0.0
        print(f"{BOLD}Core {core.core_id}:{RESET}")
        print(f"  ├─ L1 Hit Rate       : {GREEN}{hit_rate:.2f}%{RESET} ({core.l1_hits} hits / {total_reqs} total)")
        print(f"  ├─ Accumulated Latency: {YELLOW}{core.total_cycles} cycles{RESET}")
        active_lines = [f"0x{tag:04X}: {line.state.value}" for tag, line in core.lines.items()]
        print(f"  └─ Cache Slots       : [{', '.join(active_lines)}]")

    print(f"\n{BOLD}Bus Transactions Total : {MAGENTA}{bus.bus_transactions}{RESET}")
    print(f"{BOLD}Final Memory 0x1000    : {GREEN}{bus.ram[0x1000]}{RESET}")
    print(f"{BOLD}{CYAN}===================================================================={RESET}\n")

if __name__ == "__main__":
    main()