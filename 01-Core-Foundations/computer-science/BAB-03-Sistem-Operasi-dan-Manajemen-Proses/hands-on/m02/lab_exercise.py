#!/usr/bin/env python3
"""
Lab Hands-on: Core Foundations - Chapter 03 (Module 02 Deep Dive)
Topic: Virtual Memory Architecture, TLB (Translation Lookaside Buffer),
       and Page Replacement Algorithm Simulation (LRU, FIFO, CLOCK).

Architectural Model:
  - 16-bit Virtual Address Space
  - 256-Byte Page Size (8-bit offset, 8-bit Virtual Page Number / VPN)
  - Constrained Physical Memory (Configurable physical frames)
  - Fully-Associative TLB with LRU Eviction
  - Multi-Algorithm Page Replacement Engine (LRU, FIFO, Second-Chance/CLOCK)
  - Workload Generator with Locality of Reference (Spatial & Temporal)
"""

import sys
import random
from collections import deque, OrderedDict
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

# ANSI Terminal Formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_MAGENTA = "\033[95m"

PAGE_SIZE = 256       # 8-bit offset (0x00 - 0xFF)
OFFSET_BITS = 8
OFFSET_MASK = 0xFF
VPN_MASK = 0xFF00


@dataclass
class PageTableEntry:
    frame_number: int
    valid: bool = False
    dirty: bool = False
    referenced: bool = False


@dataclass
class MemoryStats:
    total_accesses: int = 0
    tlb_hits: int = 0
    tlb_misses: int = 0
    page_faults: int = 0
    dirty_evictions: int = 0


class TLB:
    """Fully associative Translation Lookaside Buffer with LRU replacement."""
    def __init__(self, capacity: int = 4):
        self.capacity = capacity
        self.entries: OrderedDict[int, int] = OrderedDict()  # VPN -> PFN

    def lookup(self, vpn: int) -> Optional[int]:
        if vpn in self.entries:
            self.entries.move_to_end(vpn)  # Mark as recently used
            return self.entries[vpn]
        return None

    def insert(self, vpn: int, pfn: int) -> None:
        if vpn in self.entries:
            self.entries.move_to_end(vpn)
            self.entries[vpn] = pfn
            return
        if len(self.entries) >= self.capacity:
            self.entries.popitem(last=False)  # Evict least recently used
        self.entries[vpn] = pfn

    def invalidate(self, vpn: int) -> None:
        if vpn in self.entries:
            del self.entries[vpn]

    def flush(self) -> None:
        self.entries.clear()


class MemoryManagementUnit:
    """Simulates hardware MMU address translation, paging, and fault handling."""
    def __init__(self, physical_frames: int, tlb_size: int, algorithm: str):
        self.num_frames = physical_frames
        self.tlb = TLB(capacity=tlb_size)
        self.algorithm = algorithm.upper()
        self.stats = MemoryStats()

        # Page Table: VPN (0..255) -> PageTableEntry
        self.page_table: Dict[int, PageTableEntry] = {
            vpn: PageTableEntry(frame_number=-1, valid=False) for vpn in range(256)
        }

        # Frame allocation tracking: Frame Number -> VPN
        self.frame_table: Dict[int, Optional[int]] = {
            fn: None for fn in range(physical_frames)
        }

        # Algorithm-specific replacement metadata
        self.fifo_queue: deque = deque()
        self.lru_tracker: OrderedDict = OrderedDict()  # Frame -> None
        self.clock_pointer: int = 0

    def _allocate_or_evict_frame(self, faulting_vpn: int) -> int:
        """Finds a free frame or evicts a victim frame using the configured algorithm."""
        # 1. Allocate unallocated frame if available
        for frame, assigned_vpn in self.frame_table.items():
            if assigned_vpn is None:
                self.fifo_queue.append(frame)
                self.lru_tracker[frame] = None
                return frame

        # 2. Select victim frame based on replacement strategy
        victim_frame = -1
        if self.algorithm == "FIFO":
            victim_frame = self.fifo_queue.popleft()
            self.fifo_queue.append(victim_frame)

        elif self.algorithm == "LRU":
            victim_frame, _ = self.lru_tracker.popitem(last=False)
            self.lru_tracker[victim_frame] = None

        elif self.algorithm == "CLOCK":
            while True:
                candidate_frame = self.clock_pointer
                candidate_vpn = self.frame_table[candidate_frame]
                pte = self.page_table[candidate_vpn]

                if not pte.referenced:
                    victim_frame = candidate_frame
                    self.clock_pointer = (self.clock_pointer + 1) % self.num_frames
                    break
                else:
                    # Give second chance: reset reference bit
                    pte.referenced = False
                    self.clock_pointer = (self.clock_pointer + 1) % self.num_frames
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

        # Evict current resident page from victim frame
        old_vpn = self.frame_table[victim_frame]
        if old_vpn is not None:
            old_pte = self.page_table[old_vpn]
            if old_pte.dirty:
                self.stats.dirty_evictions += 1  # Write-back to backing store
            old_pte.valid = False
            old_pte.dirty = False
            old_pte.referenced = False
            self.tlb.invalidate(old_vpn)

        return victim_frame

    def access(self, virtual_address: int, is_write: bool = False) -> Tuple[int, bool, bool]:
        """
        Translates virtual address to physical address.
        Returns: (Physical Address, TLB Hit Flag, Page Fault Flag)
        """
        self.stats.total_accesses += 1
        vpn = (virtual_address & VPN_MASK) >> OFFSET_BITS
        offset = virtual_address & OFFSET_MASK

        tlb_hit = False
        page_fault = False

        # Step 1: TLB Lookup
        cached_pfn = self.tlb.lookup(vpn)
        if cached_pfn is not None:
            tlb_hit = True
            self.stats.tlb_hits += 1
            pfn = cached_pfn
        else:
            self.stats.tlb_misses += 1
            # Step 2: Page Table Lookup
            pte = self.page_table[vpn]
            if not pte.valid:
                # Page Fault Triggered
                page_fault = True
                self.stats.page_faults += 1
                pfn = self._allocate_or_evict_frame(vpn)

                # Initialize Page Table Entry
                pte.frame_number = pfn
                pte.valid = True
                pte.dirty = False
                pte.referenced = False
                self.frame_table[pfn] = vpn

            pfn = pte.frame_number
            # Update TLB
            self.tlb.insert(vpn, pfn)

        # Update metadata for algorithms
        pte = self.page_table[vpn]
        pte.referenced = True
        if is_write:
            pte.dirty = True

        if self.algorithm == "LRU":
            self.lru_tracker.move_to_end(pfn)

        physical_address = (pfn << OFFSET_BITS) | offset
        return physical_address, tlb_hit, page_fault


def generate_workload(num_requests: int = 1000) -> List[Tuple[int, bool]]:
    """
    Generates a realistic instruction and data memory access stream.
    Demonstrates spatial locality (loops) and temporal locality (stack/heap access).
    """
    random.seed(42)
    workload: List[Tuple[int, bool]] = []
    working_set = [0x0400, 0x0410, 0x0420, 0x0500, 0x1200, 0x1210, 0x2000]

    for _ in range(num_requests):
        dice = random.random()
        if dice < 0.65:
            # High Temporal & Spatial Locality (Inner loop)
            base = random.choice(working_set)
            addr = base + random.randint(0, 31)
            is_write = random.random() < 0.25
        elif dice < 0.85:
            # Sequential scan across pages (Spatial Locality)
            addr = (random.randint(0x10, 0x18) << 8) | random.randint(0, 255)
            is_write = random.random() < 0.10
        else:
            # Random pointer jumps / Cache thrashing phase
            addr = random.randint(0x0000, 0x3FFF)
            is_write = random.random() < 0.50

        workload.append((addr, is_write))
    return workload


def print_system_state(mmu: MemoryManagementUnit, sample_vpn_range: range) -> None:
    """Renders visual representation of TLB and Page Table."""
    print(f"\n{CLR_BOLD}{CLR_CYAN}--- TLB Cache Status ({mmu.tlb.capacity} Entries) ---{CLR_RESET}")
    if not mmu.tlb.entries:
        print("  [TLB Empty]")
    for vpn, pfn in mmu.tlb.entries.items():
        print(f"  VPN: 0x{vpn:02X} -> PFN: 0x{pfn:02X} [{CLR_GREEN}ACTIVE{CLR_RESET}]")

    print(f"\n{CLR_BOLD}{CLR_CYAN}--- Page Table Snapshot (Range: 0x{sample_vpn_range.start:02X}-0x{sample_vpn_range.stop-1:02X}) ---{CLR_RESET}")
    print(f"  {'VPN':<6} {'PFN':<6} {'Valid':<8} {'Dirty':<8} {'Ref':<6}")
    print("  " + "-" * 34)
    for vpn in sample_vpn_range:
        pte = mmu.page_table[vpn]
        v_str = f"{CLR_GREEN}1{CLR_RESET}" if pte.valid else f"{CLR_RED}0{CLR_RESET}"
        d_str = f"{CLR_YELLOW}1{CLR_RESET}" if pte.dirty else "0"
        r_str = f"{CLR_CYAN}1{CLR_RESET}" if pte.referenced else "0"
        pfn_str = f"0x{pte.frame_number:02X}" if pte.valid else "--"
        print(f"  0x{vpn:02X}   {pfn_str:<6} {v_str:<16} {d_str:<16} {r_str:<6}")


def run_benchmark():
    print(f"{CLR_BOLD}{CLR_MAGENTA}=================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}  CS DEEP DIVE: VIRTUAL MEMORY, TLB & PAGE REPLACEMENT BENCHMARK  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}=================================================================={CLR_RESET}")

    total_accesses = 1200
    num_frames = 6
    tlb_size = 4
    algorithms = ["FIFO", "LRU", "CLOCK"]

    print(f"Configurations:")
    print(f"  - Physical Frames Allocated: {CLR_YELLOW}{num_frames}{CLR_RESET}")
    print(f"  - TLB Capacity:             {CLR_YELLOW}{tlb_size} entries{CLR_RESET}")
    print(f"  - Total Memory Trace Ops:   {CLR_YELLOW}{total_accesses}{CLR_RESET}")
    print(f"  - Page Size:                {CLR_YELLOW}{PAGE_SIZE} Bytes{CLR_RESET}")

    trace = generate_workload(total_accesses)
    results = {}

    for algo in algorithms:
        mmu = MemoryManagementUnit(physical_frames=num_frames, tlb_size=tlb_size, algorithm=algo)

        # Trace Execution
        for va, is_write in trace:
            mmu.access(va, is_write)

        results[algo] = mmu

    # Display Side-by-Side Comparison
    print(f"\n{CLR_BOLD}{CLR_CYAN}--- Benchmark Execution Summary ---{CLR_RESET}")
    header = f"{'Metric':<25} | " + " | ".join([f"{algo:<12}" for algo in algorithms])
    print(header)
    print("-" * len(header))

    def format_row(label: str, getter):
        row = f"{label:<25} | "
        values = []
        for algo in algorithms:
            val = getter(results[algo].stats)
            values.append(f"{val:<12}")
        return row + " | ".join(values)

    print(format_row("Total Accesses", lambda s: str(s.total_accesses)))
    print(format_row("TLB Hits", lambda s: f"{s.tlb_hits} ({s.tlb_hits/s.total_accesses*100:.1f}%)"))
    print(format_row("TLB Misses", lambda s: f"{s.tlb_misses}"))
    print(format_row("Page Faults", lambda s: f"{CLR_RED}{s.page_faults}{CLR_RESET} ({s.page_faults/s.total_accesses*100:.1f}%)"))
    print(format_row("Dirty Page Evictions", lambda s: f"{CLR_YELLOW}{s.dirty_evictions}{CLR_RESET}"))

    # Detailed Step Simulation Sample for CLOCK
    print(f"\n{CLR_BOLD}{CLR_BLUE}--- Stepping Through Real-Time Translations (Algorithm: CLOCK) ---{CLR_RESET}")
    clock_mmu = results["CLOCK"]
    print_system_state(clock_mmu, range(0x04, 0x08))

    # Realtime test of translations
    test_addresses = [0x041A, 0x052B, 0x04FF, 0x3010]
    print(f"\n{CLR_BOLD}Sample Live Translations:{CLR_RESET}")
    for target_va in test_addresses:
        pa, hit, fault = clock_mmu.access(target_va, is_write=True)
        hit_str = f"{CLR_GREEN}TLB-HIT{CLR_RESET}" if hit else f"{CLR_YELLOW}TLB-MISS{CLR_RESET}"
        fault_str = f"{CLR_RED}[PAGE FAULT]{CLR_RESET}" if fault else f"{CLR_GREEN}[PAGED]{CLR_RESET}"
        print(f"  VA: 0x{target_va:04X} -> PA: 0x{pa:04X} | {hit_str:<18} | {fault_str}")

    print(f"\n{CLR_GREEN}{CLR_BOLD}[+] Deep Dive Simulation completed successfully.{CLR_RESET}\n")


if __name__ == "__main__":
    try:
        run_benchmark()
    except KeyboardInterrupt:
        sys.exit(0)