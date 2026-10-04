#!/usr/bin/env python3
"""
Lab Hands-on: Virtual Memory, Page Allocation & RAM Subsystem Architecture
Modul: 01-Core-Foundations / Bab 05 - Deep Dive

Deskripsi:
Simulasi komprehensif subsistem Virtual Memory Management Linux:
1. MMU (Memory Management Unit) dengan TLB (Translation Lookaside Buffer).
2. Multi-entry Page Table dengan tracking bit flags (Present, Dirty, Referenced).
3. Physical Frame Allocator (RAM pool) dengan kapasitas terbatas.
4. Page Fault Handling & Swap Subsystem simulation.
5. Algoritma Eviksi Halaman: Clock / Second-Chance Replacement.
"""

import sys
import time
import random
from collections import OrderedDict

# ANSI Escape Codes untuk formatting log terminal
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

PAGE_SIZE = 4096         # 4 KiB per halaman (standar Linux x86_64)
OFFSET_BITS = 12         # log2(4096) = 12 bit untuk page offset
OFFSET_MASK = 0xFFF      # Masker untuk ekstraksi offset

class PageTableEntry:
    """Mewakili satu Page Table Entry (PTE) pada arsitektur perangkat keras."""
    def __init__(self):
        self.pfn = None          # Physical Frame Number
        self.present = False     # Present bit (apakah ada di RAM fisik?)
        self.dirty = False       # Dirty bit (perlu sinkronisasi writeback ke swap?)
        self.referenced = False  # Accessed bit (digunakan oleh algoritma Clock)
        self.swap_slot = None    # Lokasi pada secondary storage jika swapped out

class TLB:
    """Translation Lookaside Buffer: Hardware cache berkecepatan tinggi untuk VPN -> PFN."""
    def __init__(self, capacity=4):
        self.capacity = capacity
        # Menggunakan OrderedDict untuk simulasi LRU hardware cache replacement
        self.cache = OrderedDict()

    def lookup(self, vpn):
        """Memeriksa apakah VPN terdaftar dalam cache TLB."""
        if vpn in self.cache:
            self.cache.move_to_end(vpn)
            return self.cache[vpn]
        return None

    def update(self, vpn, pfn):
        """Menyimpan atau memperbarui mapping VPN ke PFN ke dalam TLB."""
        if vpn in self.cache:
            self.cache.move_to_end(vpn)
        self.cache[vpn] = pfn
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def invalidate(self, vpn):
        """TLB shootdown / invalidation saat halaman di-evict atau dimodifikasi."""
        if vpn in self.cache:
            del self.cache[vpn]

    def flush(self):
        """Membersihkan seluruh isi TLB (misal saat context switch)."""
        self.cache.clear()

class MMU:
    """Memory Management Unit & Linux Kernel Paging Engine Simulator."""
    def __init__(self, num_virtual_pages=32, num_physical_frames=8, tlb_size=4):
        self.num_virtual_pages = num_virtual_pages
        self.num_physical_frames = num_physical_frames
        
        # Inisialisasi Page Table (Linear / Single Level untuk penyederhanaan konseptual)
        self.page_table = [PageTableEntry() for _ in range(num_virtual_pages)]
        self.tlb = TLB(capacity=tlb_size)
        
        # Frame table: merepresentasikan slot fisik RAM (None = free, int = vpn yang menempati)
        self.frames = [None] * num_physical_frames
        self.clock_hand = 0      # Pointer untuk Algoritma Eviksi Clock
        self.swap_storage = {}   # Mock block device storage (swap space)
        
        # Metrik performa
        self.stats = {
            "accesses": 0,
            "tlb_hits": 0,
            "tlb_misses": 0,
            "page_faults": 0,
            "evictions": 0,
            "swap_writes": 0,
            "swap_reads": 0
        }

    def _allocate_free_frame(self):
        """Mencari physical frame yang masih kosong."""
        for pfn in range(self.num_physical_frames):
            if self.frames[pfn] is None:
                return pfn
        return None

    def _clock_evict(self):
        """
        Algoritma Eviksi Linux Clock (Second-Chance Page Replacement):
        Menginspeksi bit referenced secara melingkar. Jika 1 diubah ke 0; jika 0 dipilih untuk eviksi.
        """
        while True:
            candidate_vpn = self.frames[self.clock_hand]
            pte = self.page_table[candidate_vpn]
            
            if not pte.referenced:
                # Korban eviksi ditemukan
                evicted_pfn = self.clock_hand
                evicted_vpn = candidate_vpn
                self.clock_hand = (self.clock_hand + 1) % self.num_physical_frames
                return evicted_pfn, evicted_vpn
            else:
                # Beri kesempatan kedua, reset bit referenced
                pte.referenced = False
                self.clock_hand = (self.clock_hand + 1) % self.num_physical_frames

    def _handle_page_fault(self, vpn):
        """
        Kernel Page Fault Handler:
        Mengalokasikan frame kosong atau melakukan eviksi halaman jika RAM penuh.
        """
        self.stats["page_faults"] += 1
        pte = self.page_table[vpn]
        
        pfn = self._allocate_free_frame()
        if pfn is None:
            # Physical RAM jenuh: Lakukan eviksi halaman menggunakan algoritma Clock
            self.stats["evictions"] += 1
            evicted_pfn, evicted_vpn = self._clock_evict()
            evicted_pte = self.page_table[evicted_vpn]
            
            # Jika halaman kotor (dirty), tulis perubahan ke mock swap partition
            if evicted_pte.dirty:
                self.stats["swap_writes"] += 1
                self.swap_storage[evicted_vpn] = f"DATA_SWAP_VPN_{evicted_vpn}"
                print(f"    {Color.YELLOW}[FLUSH SWAP]{Color.RESET} VPN {evicted_vpn} kotor -> disinkronkan ke swap.")
            
            # Update metadata PTE halaman yang didepak
            evicted_pte.present = False
            evicted_pte.pfn = None
            evicted_pte.dirty = False
            self.tlb.invalidate(evicted_vpn)
            
            print(f"    {Color.MAGENTA}[EVICTION]{Color.RESET} Page replacement: Mengeluarkan VPN {evicted_vpn} dari PFN {evicted_pfn}")
            pfn = evicted_pfn

        # Jika halaman sebelumnya ada di swap, baca kembali ke RAM
        if vpn in self.swap_storage:
            self.stats["swap_reads"] += 1
            print(f"    {Color.BLUE}[SWAP IN]{Color.RESET} Memulihkan VPN {vpn} dari swap ke PFN {pfn}.")
            del self.swap_storage[vpn]
        else:
            print(f"    {Color.CYAN}[ALLOC]{Color.RESET} Menetapkan zeroed anonymous page baru ke PFN {pfn}.")

        # Assign PFN ke PTE baru
        self.frames[pfn] = vpn
        pte.pfn = pfn
        pte.present = True
        pte.referenced = True
        pte.dirty = False
        return pfn

    def access(self, virtual_address, write=False):
        """
        Alur Eksekusi Translasi Alamat:
        Virtual Address -> Ekstraksi VPN/Offset -> TLB -> Page Table (Fault Handler) -> Physical Address
        """
        self.stats["accesses"] += 1
        vpn = virtual_address >> OFFSET_BITS
        offset = virtual_address & OFFSET_MASK

        if vpn >= self.num_virtual_pages:
            raise MemoryError(f"Segmentation fault: Alamat 0x{virtual_address:08X} melampaui virtual memory bounds!")

        print(f"-> Mengakses VA {Color.BOLD}0x{virtual_address:04X}{Color.RESET} (VPN: {vpn:2d}, Offset: 0x{offset:03X}) Mode: {'WRITE' if write else 'READ'}")

        # Tahap 1: Evaluasi TLB Lookup
        pfn = self.tlb.lookup(vpn)
        if pfn is not None:
            self.stats["tlb_hits"] += 1
            print(f"    {Color.GREEN}[TLB HIT]{Color.RESET} VPN {vpn} dipetakan ke PFN {pfn} via TLB")
        else:
            self.stats["tlb_misses"] += 1
            print(f"    {Color.YELLOW}[TLB MISS]{Color.RESET} VPN {vpn} tidak ditemukan di TLB. Membaca Page Table...")
            
            # Tahap 2: Evaluasi Page Table & Present Bit
            pte = self.page_table[vpn]
            if not pte.present:
                print(f"    {Color.RED}[PAGE FAULT]{Color.RESET} Interrupt raised: Halaman VPN {vpn} tidak ada di memori fisik.")
                pfn = self._handle_page_fault(vpn)
            else:
                pfn = pte.pfn
                print(f"    [PT HIT] VPN {vpn} valid pada PFN {pfn}")

            # Perbarui TLB
            self.tlb.update(vpn, pfn)

        # Tandai metadata PTE
        pte = self.page_table[vpn]
        pte.referenced = True
        if write:
            pte.dirty = True

        physical_address = (pfn << OFFSET_BITS) | offset
        print(f"    Resolusi Fisik: {Color.BOLD}0x{physical_address:04X}{Color.RESET} [PFN: {pfn:2d}, Offset: 0x{offset:03X}]")
        return physical_address

    def print_memory_map(self):
        """Visualisasi status frame fisik di RAM."""
        print(f"\n{Color.BOLD}--- PETA ALOKASI PHYSICAL RAM ---{Color.RESET}")
        bar = []
        for i, vpn in enumerate(self.frames):
            if vpn is None:
                bar.append(f"[{i:02d}: EMPTY ]")
            else:
                d = "D" if self.page_table[vpn].dirty else "-"
                r = "R" if self.page_table[vpn].referenced else "-"
                bar.append(f"[{i:02d}: V{vpn:02d} {d}{r}]")
        print(" ".join(bar))
        print(f"{Color.CYAN}Hand Posisi Clock Engine: Frame {self.clock_hand}{Color.RESET}\n")

def run_simulation():
    print(f"{Color.BOLD}{Color.CYAN}=================================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}LAB: ANALISIS SUBSISTEM MEMORI VIRTUAL & PAGE ALLOCATION LINUX    {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}=================================================================={Color.RESET}")
    
    # Parameter sistem:
    # 32 Virtual Pages (128 KiB ruang virtual), 8 Physical Frames (32 KiB RAM fisik), TLB size: 4 entri
    mmu = MMU(num_virtual_pages=32, num_physical_frames=8, tlb_size=4)
    
    # Skenario 1: Spatial & Temporal Locality (mengakses working set kecil berulang kali)
    print(f"\n{Color.BOLD}SKENARIO 1: Pengujian Temporal Locality & Pengisian Awal RAM{Color.RESET}")
    addresses = [0x0100, 0x0150, 0x1200, 0x0180, 0x12A0, 0x2400]
    for addr in addresses:
        mmu.access(addr, write=False)
        time.sleep(0.02)
    mmu.print_memory_map()

    # Skenario 2: Memory Pressure dan Trigger Page Fault Swapping
    print(f"\n{Color.BOLD}SKENARIO 2: Alokasi Melebihi Batas Fisik RAM (Clock Replacement){Color.RESET}")
    # Akses VPN unik baru dari 3 hingga 9 untuk memenuhi 8 frame fisik dan memicu eviksi
    for vpn in range(3, 10):
        target_addr = (vpn << OFFSET_BITS) | random.randint(0, 0x100)
        # Menulis beberapa halaman untuk menandai 'dirty' flag
        is_write = (vpn % 2 == 0)
        mmu.access(target_addr, write=is_write)
        time.sleep(0.02)
    mmu.print_memory_map()

    # Skenario 3: Mengakses kembali halaman yang di-swap out (Memverifikasi Swap-in dan Writeback)
    print(f"\n{Color.BOLD}SKENARIO 3: Re-access Evicted Page (Swap Fault Restoration){Color.RESET}")
    mmu.access(0x0100, write=True) # VPN 0 kemungkinan telah dieviksi ke swap
    mmu.print_memory_map()

    # Ringkasan Statistik
    stats = mmu.stats
    tlb_hit_ratio = (stats["tlb_hits"] / stats["accesses"]) * 100 if stats["accesses"] > 0 else 0
    fault_ratio = (stats["page_faults"] / stats["accesses"]) * 100 if stats["accesses"] > 0 else 0

    print(f"{Color.BOLD}================ HASIL ANALISIS SUBSISTEM MEMORI ================{Color.RESET}")
    print(f" Total Akses Memori       : {stats['accesses']}")
    print(f" TLB Hits / Misses         : {Color.GREEN}{stats['tlb_hits']}{Color.RESET} / {Color.YELLOW}{stats['tlb_misses']}{Color.RESET}")
    print(f" TLB Hit Ratio             : {Color.BOLD}{tlb_hit_ratio:.2f}%{Color.RESET}")
    print(f" Major/Minor Page Faults   : {Color.RED}{stats['page_faults']}{Color.RESET} ({fault_ratio:.2f}%)")
    print(f" Total Evictions (Clock)   : {stats['evictions']}")
    print(f" Swap Page Out (Dirty)     : {stats['swap_writes']}")
    print(f" Swap Page In (Restored)   : {stats['swap_reads']}")
    print(f"{Color.BOLD}=================================================================={Color.RESET}")

if __name__ == "__main__":
    run_simulation()