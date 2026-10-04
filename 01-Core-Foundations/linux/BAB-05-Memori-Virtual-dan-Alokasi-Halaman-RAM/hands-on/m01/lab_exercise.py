#!/usr/bin/env python3
"""
Simulasi Fondasi Inti Linux: Memori Virtual, Paging, TLB, dan Alokasi Frame RAM
BAB-05: Memori Virtual dan Alokasi Halaman RAM
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ANSI Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_GRAY = "\033[90m"

PAGE_SIZE = 4096       # 4 KB Page standard
PAGE_OFFSET_BITS = 12  # 2^12 = 4096 bytes
NUM_FRAMES = 8         # 8 Physical frames (32 KB total RAM simulator)
TLB_CAPACITY = 4       # TLB entries


@dataclass
class PageTableEntry:
    frame_number: Optional[int] = None
    present: bool = False
    read_write: bool = True
    user_mode: bool = True
    dirty: bool = False
    accessed: bool = False
    swapped: bool = False
    swap_slot: Optional[int] = None


@dataclass
class TLBEntry:
    page_number: int
    frame_number: int
    read_write: bool
    last_access: float = field(default_factory=time.time)


class MemoryManagementUnit:
    def __init__(self, num_frames: int = NUM_FRAMES, tlb_capacity: int = TLB_CAPACITY):
        self.num_frames = num_frames
        self.tlb_capacity = tlb_capacity
        self.page_table: Dict[int, PageTableEntry] = {}
        self.tlb: List[TLBEntry] = []
        self.physical_frames: List[Optional[Tuple[int, bytes]]] = [None] * num_frames
        self.swap_space: Dict[int, bytes] = {}
        self.next_swap_slot = 0
        self.tlb_hits = 0
        self.tlb_misses = 0
        self.page_faults = 0

    def print_banner(self):
        print(f"{CLR_CYAN}{CLR_BOLD}{'=' * 68}{CLR_RESET}")
        print(f"{CLR_GREEN}{CLR_BOLD}  LINUX VIRTUAL MEMORY & PAGE ALLOCATION SIMULATOR (MMU) {CLR_RESET}")
        print(f"{CLR_YELLOW}  BAB-05: Paging, TLB, Page Fault Handler, Swap, & Frame Allocation{CLR_RESET}")
        print(f"{CLR_CYAN}{CLR_BOLD}{'=' * 68}{CLR_RESET}\n")

    def _tlb_lookup(self, page_num: int) -> Optional[TLBEntry]:
        for entry in self.tlb:
            if entry.page_number == page_num:
                entry.last_access = time.time()
                self.tlb_hits += 1
                return entry
        self.tlb_misses += 1
        return None

    def _tlb_insert(self, page_num: int, frame_num: int, rw: bool):
        for entry in self.tlb:
            if entry.page_number == page_num:
                entry.frame_number = frame_num
                entry.read_write = rw
                entry.last_access = time.time()
                return

        if len(self.tlb) >= self.tlb_capacity:
            # Evict least recently used TLB entry
            self.tlb.sort(key=lambda x: x.last_access)
            evicted = self.tlb.pop(0)
            print(f"  {CLR_GRAY}[TLB Evict]{CLR_RESET} Mengeluarkan VPN {CLR_YELLOW}0x{evicted.page_number:X}{CLR_RESET} dari TLB cache.")

        self.tlb.append(TLBEntry(page_number=page_num, frame_number=frame_num, read_write=rw))

    def _find_free_frame(self) -> Optional[int]:
        for idx, frame in enumerate(self.physical_frames):
            if frame is None:
                return idx
        return None

    def _evict_frame(self) -> int:
        """Page replacement policy: Pseudo-LRU clock algorithm."""
        print(f"  {CLR_RED}[OOM/Pressure]{CLR_RESET} Semua frame RAM penuh! Memilih victim frame untuk swapping...")
        victim_candidates = [i for i, f in enumerate(self.physical_frames) if f is not None]
        victim_frame = random.choice(victim_candidates)
        vpn, data = self.physical_frames[victim_frame]

        pte = self.page_table[vpn]
        if pte.dirty:
            slot = self.next_swap_slot
            self.next_swap_slot += 1
            self.swap_space[slot] = data
            pte.swapped = True
            pte.swap_slot = slot
            print(f"  {CLR_MAGENTA}[Swap Out]{CLR_RESET} VPN {CLR_YELLOW}0x{vpn:X}{CLR_RESET} kotor (dirty bit=1). Ditulis ke Swap Slot #{slot}.")
        else:
            print(f"  {CLR_CYAN}[Drop Clean]{CLR_RESET} VPN {CLR_YELLOW}0x{vpn:X}{CLR_RESET} bersih. Langsung dibuang dari RAM frame {victim_frame}.")

        pte.present = False
        pte.frame_number = None

        # Invalidate TLB if present
        self.tlb = [t for t in self.tlb if t.page_number != vpn]

        self.physical_frames[victim_frame] = None
        return victim_frame

    def handle_page_fault(self, vpn: int, is_write: bool) -> int:
        self.page_faults += 1
        print(f"  {CLR_RED}{CLR_BOLD}[PAGE FAULT]{CLR_RESET} Interrupt 14 (PF) terpicu untuk VPN: {CLR_YELLOW}0x{vpn:X}{CLR_RESET}")
        time.sleep(0.3)

        frame = self._find_free_frame()
        if frame is None:
            frame = self._evict_frame()

        pte = self.page_table.setdefault(vpn, PageTableEntry())

        if pte.swapped and pte.swap_slot is not None:
            print(f"  {CLR_GREEN}[Swap In]{CLR_RESET} Membaca kembali data VPN 0x{vpn:X} dari Swap Slot #{pte.swap_slot} -> RAM Frame {frame}")
            data = self.swap_space.pop(pte.swap_slot, b"\x00" * 32)
            pte.swapped = False
            pte.swap_slot = None
        else:
            print(f"  {CLR_BLUE}[Demand Zeroing]{CLR_RESET} Kernel mengalokasikan anonymous zeroed frame #{frame} untuk VPN 0x{vpn:X}")
            data = b"\x00" * 32

        pte.present = True
        pte.frame_number = frame
        pte.accessed = True
        if is_write:
            pte.dirty = True

        self.physical_frames[frame] = (vpn, data)
        return frame

    def access_memory(self, virtual_address: int, is_write: bool = False, payload: str = "") -> Tuple[int, int]:
        vpn = virtual_address >> PAGE_OFFSET_BITS
        offset = virtual_address & (PAGE_SIZE - 1)

        print(f"\n{CLR_BOLD}>>> Akses Alamat Virtual: {CLR_CYAN}0x{virtual_address:08X}{CLR_RESET} "
              f"({'WRITE' if is_write else 'READ'}) | VPN: {CLR_YELLOW}0x{vpn:X}{CLR_RESET}, Offset: {CLR_YELLOW}{offset}{CLR_RESET}")

        # Step 1: TLB Lookup
        tlb_hit = self._tlb_lookup(vpn)
        if tlb_hit:
            print(f"  {CLR_GREEN}[TLB HIT]{CLR_RESET} Hardware MMU menemukan mapping di TLB -> Frame #{tlb_hit.frame_number}")
            frame = tlb_hit.frame_number
            pte = self.page_table[vpn]
            pte.accessed = True
            if is_write:
                pte.dirty = True
        else:
            print(f"  {CLR_YELLOW}[TLB MISS]{CLR_RESET} Mapping tidak ada di TLB, MMU melakukan page table walk...")
            pte = self.page_table.get(vpn)

            # Step 2: Page Table check
            if pte is None or not pte.present:
                frame = self.handle_page_fault(vpn, is_write)
            else:
                frame = pte.frame_number
                pte.accessed = True
                if is_write:
                    pte.dirty = True
                print(f"  {CLR_GREEN}[PTE PRESENT]{CLR_RESET} Ditemukan di Page Table -> Frame #{frame}")

            # Refill TLB
            self._tlb_insert(vpn, frame, pte.read_write)

        # Step 3: Compute Physical Address
        paddr = (frame << PAGE_OFFSET_BITS) | offset
        if is_write and payload:
            encoded = payload.encode("utf-8")[:32].ljust(32, b"\x00")
            self.physical_frames[frame] = (vpn, encoded)
            print(f"  {CLR_MAGENTA}[RAM Write]{CLR_RESET} Menulis payload \"{payload}\" ke Frame #{frame}")

        print(f"  {CLR_GREEN}{CLR_BOLD}[OK]{CLR_RESET} Physical Address: {CLR_CYAN}0x{paddr:08X}{CLR_RESET} (Frame: {frame}, Offset: {offset})")
        return vpn, paddr

    def display_status(self):
        print(f"\n{CLR_BOLD}--- STATUS HARDWARE MMU & RAM ---{CLR_RESET}")
        print(f"TLB Hits: {CLR_GREEN}{self.tlb_hits}{CLR_RESET} | "
              f"TLB Misses: {CLR_YELLOW}{self.tlb_misses}{CLR_RESET} | "
              f"Page Faults: {CLR_RED}{self.page_faults}{CLR_RESET}")

        # TLB Visual
        print(f"\n{CLR_BOLD}[Translation Lookaside Buffer (TLB)]{CLR_RESET}")
        if not self.tlb:
            print(f"  {CLR_GRAY}(TLB Kosong){CLR_RESET}")
        else:
            for i, entry in enumerate(self.tlb):
                print(f"  Slot [{i}]: VPN=0x{entry.page_number:X} -> Frame #{entry.frame_number} "
                      f"(RW: {'W' if entry.read_write else 'R'})")

        # Physical RAM Frames
        print(f"\n{CLR_BOLD}[Physical RAM Frames ({self.num_frames} Slots x 4KB)]{CLR_RESET}")
        for f_idx in range(self.num_frames):
            frame_data = self.physical_frames[f_idx]
            if frame_data is None:
                print(f"  Frame #{f_idx}: {CLR_GRAY}[FREE / UNALLOCATED]{CLR_RESET}")
            else:
                vpn, val = frame_data
                preview = val.decode("utf-8", errors="replace").strip("\x00")
                pte = self.page_table.get(vpn)
                dirty_str = f"{CLR_RED}D{CLR_RESET}" if pte and pte.dirty else f"{CLR_GRAY}-{CLR_RESET}"
                acc_str = f"{CLR_GREEN}A{CLR_RESET}" if pte and pte.accessed else f"{CLR_GRAY}-{CLR_RESET}"
                print(f"  Frame #{f_idx}: {CLR_GREEN}[MAPPED]{CLR_RESET} VPN=0x{vpn:X} | Flags:[{dirty_str}{acc_str}] | Data: \"{preview}\"")

        # Swap Space
        print(f"\n{CLR_BOLD}[Swap Space Disk Partition]{CLR_RESET}")
        if not self.swap_space:
            print(f"  {CLR_GRAY}(Swap Space Bersih / 0 KB Terpakai){CLR_RESET}")
        else:
            for s_idx, data in self.swap_space.items():
                preview = data.decode("utf-8", errors="replace").strip("\x00")
                print(f"  Slot #{s_idx}: {CLR_MAGENTA}[SWAPPED PAGE]{CLR_RESET} Data: \"{preview}\"")
        print()


def interactive_menu():
    mmu = MemoryManagementUnit()
    mmu.print_banner()

    # Pre-populate demo scenario
    print(f"{CLR_BLUE}Menginisialisasi simulasi interaktif...{CLR_RESET}")
    print("Contoh alur: Demand paging, dirty page handling, TLB cache warm-up, dan page eviction.\n")

    menu_text = f"""{CLR_BOLD}PILIHAN AKSI SIMULASI:{CLR_RESET}
  1. Akses Read Virtual Address (e.g. 0x00001000)
  2. Akses Write Virtual Address (e.g. 0x00001000 dengan data teks)
  3. Jalankan Skenario Otomatis (Demo Page Fault + TLB Hit + Trashing/Swap)
  4. Tampilkan Tabel Frame RAM & TLB
  5. Reset Simulasi
  6. Keluar
"""

    while True:
        print(menu_text)
        try:
            choice = input(f"{CLR_CYAN}Pilih opsi [1-6]: {CLR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if choice == "1":
            vaddr_str = input("Masukkan Virtual Address Hex (contoh: 0x1020 atau 4096): ").strip()
            try:
                vaddr = int(vaddr_str, 16 if vaddr_str.lower().startswith("0x") else 10)
                mmu.access_memory(vaddr, is_write=False)
            except ValueError:
                print(f"{CLR_RED}Alamat tidak valid!{CLR_RESET}")

        elif choice == "2":
            vaddr_str = input("Masukkan Virtual Address Hex (contoh: 0x2050): ").strip()
            payload = input("Masukkan Teks String untuk disimpan di halaman RAM: ").strip()
            try:
                vaddr = int(vaddr_str, 16 if vaddr_str.lower().startswith("0x") else 10)
                mmu.access_memory(vaddr, is_write=True, payload=payload)
            except ValueError:
                print(f"{CLR_RED}Alamat tidak valid!{CLR_RESET}")

        elif choice == "3":
            print(f"\n{CLR_BOLD}{CLR_MAGENTA}--- MEMULAI AUTOMATED SIMULATION WORKLOAD ---{CLR_RESET}")
            # Step A: Cold misses & page faults
            print(f"{CLR_YELLOW}Tahap 1: Mengakses 4 Halaman Berurutan (Harus memicu Page Fault){CLR_RESET}")
            addresses = [0x1000, 0x2000, 0x3000, 0x4000]
            for addr in addresses:
                mmu.access_memory(addr, is_write=True, payload=f"Data_Page_0x{addr:X}")
                time.sleep(0.15)

            # Step B: TLB Hit test
            print(f"\n{CLR_YELLOW}Tahap 2: Akses Ulang Halaman yang Sama (Harus memicu TLB HIT murni){CLR_RESET}")
            for addr in addresses:
                mmu.access_memory(addr + 0x20, is_write=False)
                time.sleep(0.15)

            # Step C: Fill all frames to force eviction
            print(f"\n{CLR_YELLOW}Tahap 3: Tekanan Memori - Mengalokasikan 6 Halaman Baru (Frame Penuh -> Eviction/Swap){CLR_RESET}")
            overflow_addrs = [0x5000, 0x6000, 0x7000, 0x8000, 0x9000, 0xA000]
            for addr in overflow_addrs:
                mmu.access_memory(addr, is_write=True, payload=f"Data_Burst_0x{addr:X}")
                time.sleep(0.15)

            # Step D: Read back evicted page
            print(f"\n{CLR_YELLOW}Tahap 4: Mengakses kembali Halaman Pertama 0x1000 (Swap In){CLR_RESET}")
            mmu.access_memory(0x1000, is_write=False)

            mmu.display_status()

        elif choice == "4":
            mmu.display_status()

        elif choice == "5":
            mmu = MemoryManagementUnit()
            print(f"{CLR_GREEN}Status MMU & RAM berhasil di-reset.{CLR_RESET}")

        elif choice == "6":
            print(f"{CLR_GREEN}Terima kasih telah mempelajari arsitektur Virtual Memory Linux!{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid, silakan ulangi.{CLR_RESET}")


if __name__ == "__main__":
    interactive_menu()
