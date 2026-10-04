#!/usr/bin/env python3
"""
Lab Hands-on: Core Foundations - Bab 09: Modul 02 Deep Dive
Topik: Arsitektur Memori Virtual - Simulasi MMU, TLB, Page Table, dan Algoritma Page Replacement

Deskripsi:
Program ini memodelkan subsistem Memory Management Unit (MMU) pada sistem operasi modern.
Mensimulasikan translasi alamat virtual ke fisik, Translation Lookaside Buffer (TLB),
penanganan Page Fault, dan benchmark komparasi algoritma page replacement:
1. FIFO (First-In, First-Out)
2. LRU (Least Recently Used)
3. Clock / Second-Chance Algorithm
"""

import sys
import time
import random
from collections import deque, OrderedDict
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

# Konfigurasi Kode Warna ANSI Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_BG_DARK = "\033[40m"

# Parameter Arsitektur Hardware Simulasi
PAGE_SIZE_BYTES = 4096      # 4 KB per halaman (Offset 12 bit)
OFFSET_BITS = 12
PAGE_MASK = 0xFFFFF000
OFFSET_MASK = 0x00000FFF

# Latensi Hardware Relatif (dalam Nanodetik)
LATENCY_TLB_HIT_NS = 1
LATENCY_RAM_ACCESS_NS = 100
LATENCY_PAGE_FAULT_NS = 8_000_000  # Disk I/O ~8ms


@dataclass
class PageTableEntry:
    """Representasi entri tabel halaman (PTE) pada arsitektur x86/ARM."""
    frame_number: int = -1
    valid: bool = False
    dirty: bool = False
    referenced: bool = False


class TranslationLookasideBuffer:
    """TLB Cache terasosiasi penuh dengan kebijakan LRU evict."""
    def __init__(self, capacity: int = 4):
        self.capacity = capacity
        self.cache: OrderedDict[int, int] = OrderedDict()  # virtual_page -> physical_frame

    def lookup(self, vpn: int) -> Optional[int]:
        if vpn in self.cache:
            self.cache.move_to_end(vpn)
            return self.cache[vpn]
        return None

    def insert(self, vpn: int, pfn: int):
        if vpn in self.cache:
            self.cache.move_to_end(vpn)
            self.cache[vpn] = pfn
            return
        if len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)  # Evict least recently used
        self.cache[vpn] = pfn

    def invalidate(self, vpn: int):
        if vpn in self.cache:
            del self.cache[vpn]

    def clear(self):
        self.cache.clear()


class MemoryManagementUnit:
    """
    MMU bertanggung jawab atas segmentasi/paging, lookup TLB,
    serta paging-in/out saat terjadi page fault.
    """
    def __init__(self, num_frames: int, policy: str = "LRU"):
        self.num_frames = num_frames
        self.policy = policy.upper()
        
        # State Memori
        self.tlb = TranslationLookasideBuffer(capacity=4)
        self.page_table: Dict[int, PageTableEntry] = {}
        self.physical_frames: List[Optional[int]] = [None] * num_frames  # Indeks = Frame ID, Nilai = VPN
        
        # Data Struktur Tracking Algoritma Replacement
        self.fifo_queue: deque = deque()
        self.lru_order: OrderedDict = OrderedDict()
        self.clock_hand: int = 0
        
        # Metrik Simulasi
        self.total_accesses = 0
        self.tlb_hits = 0
        self.page_faults = 0
        self.cumulative_latency_ns = 0

    def _get_free_frame(self) -> Optional[int]:
        for idx, vpn in enumerate(self.physical_frames):
            if vpn is None:
                return idx
        return None

    def _evict_page(self) -> int:
        """Menjalankan algoritma pemilih frame korban untuk digusur (eviction)."""
        if self.policy == "FIFO":
            evicted_vpn = self.fifo_queue.popleft()
            frame_to_free = self.page_table[evicted_vpn].frame_number
            return frame_to_free, evicted_vpn

        elif self.policy == "LRU":
            evicted_vpn, _ = self.lru_order.popitem(last=False)
            frame_to_free = self.page_table[evicted_vpn].frame_number
            return frame_to_free, evicted_vpn

        elif self.policy == "CLOCK":
            while True:
                candidate_vpn = self.physical_frames[self.clock_hand]
                pte = self.page_table[candidate_vpn]
                if not pte.referenced:
                    frame_to_free = self.clock_hand
                    self.clock_hand = (self.clock_hand + 1) % self.num_frames
                    return frame_to_free, candidate_vpn
                else:
                    pte.referenced = False
                    self.clock_hand = (self.clock_hand + 1) % self.num_frames
        else:
            raise ValueError(f"Kebijakan tidak dikenal: {self.policy}")

    def translate(self, virtual_address: int, write: bool = False) -> Tuple[int, bool, bool]:
        """
        Translasi virtual address menjadi physical address.
        Return: (physical_address, tlb_hit, page_fault)
        """
        self.total_accesses += 1
        vpn = (virtual_address & PAGE_MASK) >> OFFSET_BITS
        offset = virtual_address & OFFSET_MASK
        
        tlb_hit = False
        page_fault = False

        # 1. Hardware TLB Lookup
        cached_frame = self.tlb.lookup(vpn)
        if cached_frame is not None:
            self.tlb_hits += 1
            tlb_hit = True
            self.cumulative_latency_ns += LATENCY_TLB_HIT_NS
            pfn = cached_frame
        else:
            # TLB Miss: Perlu akses Page Table di memori utama (RAM)
            self.cumulative_latency_ns += (LATENCY_TLB_HIT_NS + LATENCY_RAM_ACCESS_NS)
            
            pte = self.page_table.get(vpn)
            if pte is None or not pte.valid:
                # 2. PAGE FAULT TRAP
                self.page_faults += 1
                page_fault = True
                self.cumulative_latency_ns += LATENCY_PAGE_FAULT_NS
                
                # Alokasi Frame
                pfn = self._get_free_frame()
                if pfn is None:
                    # Memori fisik penuh -> lakukan eviksi
                    pfn, evicted_vpn = self._evict_page()
                    # Invalidate entri lama
                    self.page_table[evicted_vpn].valid = False
                    self.tlb.invalidate(evicted_vpn)

                # Inisialisasi PTE jika belum ada
                if vpn not in self.page_table:
                    self.page_table[vpn] = PageTableEntry()

                self.page_table[vpn].frame_number = pfn
                self.page_table[vpn].valid = True
                self.physical_frames[pfn] = vpn
                
                if self.policy == "FIFO":
                    self.fifo_queue.append(vpn)
            else:
                pfn = pte.frame_number

            # Update TLB setelah resolusi PT
            self.tlb.insert(vpn, pfn)

        # 3. Update Status Algoritma & PTE
        pte = self.page_table[vpn]
        pte.referenced = True
        if write:
            pte.dirty = True

        if self.policy == "LRU":
            self.lru_order[vpn] = True
            self.lru_order.move_to_end(vpn)

        physical_address = (pfn << OFFSET_BITS) | offset
        return physical_address, tlb_hit, page_fault


def generate_trace(workload_type: str, count: int) -> List[Tuple[int, bool]]:
    """Menghasilkan jejak memori sintetis: (Virtual Address, is_write)."""
    random.seed(42)
    trace = []
    
    if workload_type == "locality":
        # Mensimulasikan perulangan ketat (loop), lokalitas spasial & temporal tinggi
        pages_working_set = [0x01, 0x02, 0x03, 0x04]
        for _ in range(count):
            vpn = random.choice(pages_working_set)
            offset = random.randint(0, 1024)
            is_write = random.random() < 0.2
            trace.append(((vpn << OFFSET_BITS) | offset, is_write))
            
    elif workload_type == "sequential_scan":
        # Scanning array besar melampaui kapasitas RAM
        for i in range(count):
            vpn = (i // 16) % 32
            offset = (i * 64) % PAGE_SIZE_BYTES
            trace.append(((vpn << OFFSET_BITS) | offset, False))
            
    else:  # Mixed Random Stress
        for _ in range(count):
            vpn = random.randint(0, 15)
            offset = random.randint(0, PAGE_SIZE_BYTES - 1)
            trace.append(((vpn << OFFSET_BITS) | offset, random.random() < 0.3))
            
    return trace


def run_benchmark():
    print(f"{CLR_BOLD}{CLR_CYAN}=== LAB VIRTUAL MEMORY & MMU SUBSYSTEM EMULATION ==={CLR_RESET}")
    print(f"Konfigurasi: 4KB Page, TLB Capacity=4, Physical Frames=4 (Overcommitted Model)")
    print("-" * 75)

    num_frames = 4
    num_requests = 1000
    workload_types = ["locality", "sequential_scan", "mixed_random"]
    policies = ["FIFO", "LRU", "CLOCK"]

    results_table = []

    for workload in workload_types:
        trace = generate_trace(workload, num_requests)
        for policy in policies:
            mmu = MemoryManagementUnit(num_frames=num_frames, policy=policy)
            
            start_wall = time.perf_counter()
            for v_addr, is_write in trace:
                mmu.translate(v_addr, is_write)
            wall_time_ms = (time.perf_counter() - start_wall) * 1000.0

            tlb_hit_pct = (mmu.tlb_hits / mmu.total_accesses) * 100.0
            pf_pct = (mmu.page_faults / mmu.total_accesses) * 100.0
            emat_ns = mmu.cumulative_latency_ns / mmu.total_accesses  # Effective Memory Access Time

            results_table.append({
                "workload": workload,
                "policy": policy,
                "tlb_hit": tlb_hit_pct,
                "pf_count": mmu.page_faults,
                "pf_pct": pf_pct,
                "emat": emat_ns,
                "wall_time": wall_time_ms
            })

    # Header Tabulasi
    print(f"{CLR_BOLD}{'WORKLOAD':<18} | {'POLICY':<6} | {'TLB HIT %':<10} | {'PAGE FAULTS':<12} | {'PF RATE %':<10} | {'EMAT (ns)':<12}{CLR_RESET}")
    print("-" * 75)

    current_w = ""
    for r in results_table:
        if r["workload"] != current_w:
            current_w = r["workload"]
            print(f"{CLR_MAGENTA}{CLR_BOLD}>> Workload: {current_w.upper()}{CLR_RESET}")

        pf_color = CLR_GREEN if r["pf_pct"] < 5.0 else (CLR_YELLOW if r["pf_pct"] < 25.0 else CLR_RED)
        
        print(f"  {r['workload']:<16} | {CLR_BOLD}{r['policy']:<6}{CLR_RESET} | "
              f"{r['tlb_hit']:>9.2f}% | "
              f"{pf_color}{r['pf_count']:>12}{CLR_RESET} | "
              f"{pf_color}{r['pf_pct']:>9.2f}%{CLR_RESET} | "
              f"{r['emat']:>12.1f}")
    
    print("-" * 75)
    print(f"{CLR_BOLD}{CLR_GREEN}[*] Eksekusi simulasi MMU selesai tanpa anomali hardware.{CLR_RESET}")
    print(f"Catatan: EMAT (Effective Memory Access Time) merefleksikan penalti dramatis disk swapping.")


if __name__ == "__main__":
    run_benchmark()