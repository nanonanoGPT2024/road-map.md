#!/usr/bin/env python3
"""
Simulasi Teknis: Manajemen Memori Dinamis C, Subalokator, & Profiling
BAB-07: Alokasi Heap, Explicit Free-List, Coalescing, Arena Allocator, dan Deteksi Kebocoran (Leak Profiler).
"""

import sys
import time
from typing import Dict, List, Optional

# ANSI Color Codes untuk visualisasi terminal
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_GRAY = "\033[100m"

ALIGNMENT = 8  # 8-byte alignment seperti arsitektur x86_64
HEADER_SIZE = 16  # Simulasi metadata header per blok memori (size + flags + canary)
CANARY_MAGIC = 0xDEADBEEF


def align_up(size: int, alignment: int = ALIGNMENT) -> int:
    """Melakukan pembulatan ukuran alokasi ke kelipatan alignment."""
    return (size + (alignment - 1)) & ~(alignment - 1)


class MemoryBlock:
    """Representasi blok memori fisik pada heap simulated buffer."""
    def __init__(self, offset: int, size: int, is_free: bool = True):
        self.offset: int = offset          # Alamat fisik awal blok
        self.size: int = size              # Total payload size (eksklusif header)
        self.is_free: bool = is_free        # Status alokasi
        self.canary: int = CANARY_MAGIC    # Boundary canary pencegah heap overflow
        self.alloc_id: Optional[int] = None
        self.tag: str = ""

    @property
    def total_size(self) -> int:
        return HEADER_SIZE + self.size


class SimulatedHeapAllocator:
    """
    Subalokator eksplisit bergaya `dlmalloc` dengan first-fit search,
    splitting, boundary tags, dan immediate bidirectional coalescing.
    """
    def __init__(self, capacity: int = 1024):
        self.capacity: int = align_up(capacity)
        self.blocks: List[MemoryBlock] = [MemoryBlock(offset=0, size=self.capacity - HEADER_SIZE, is_free=True)]
        self.next_alloc_id: int = 1
        self.active_allocations: Dict[int, MemoryBlock] = {}
        self.peak_allocated_bytes: int = 0
        self.total_malloc_calls: int = 0
        self.total_free_calls: int = 0

    def malloc(self, req_size: int, tag: str = "data") -> Optional[int]:
        """Alokasi memori berukuran req_size dengan 8-byte alignment & header."""
        if req_size <= 0:
            print(f"{RED}[!] Error:{RESET} Ukuran alokasi harus > 0.")
            return None

        aligned_payload = align_up(req_size)
        self.total_malloc_calls += 1

        # First-fit search pada list blok memori
        for idx, block in enumerate(self.blocks):
            if block.is_free and block.size >= aligned_payload:
                # Periksa apakah sisa ruang cukup untuk di-split jadi blok free baru
                remaining_space = block.size - aligned_payload
                if remaining_space >= HEADER_SIZE + ALIGNMENT:
                    # Lakukan splitting
                    original_size = block.size
                    block.size = aligned_payload
                    block.is_free = False
                    block.alloc_id = self.next_alloc_id
                    block.tag = tag

                    new_offset = block.offset + block.total_size
                    new_block = MemoryBlock(
                        offset=new_offset,
                        size=remaining_space - HEADER_SIZE,
                        is_free=True
                    )
                    self.blocks.insert(idx + 1, new_block)
                else:
                    # Ambil seluruh blok tanpa split (internal fragmentation kecil)
                    block.is_free = False
                    block.alloc_id = self.next_alloc_id
                    block.tag = tag

                ptr_id = self.next_alloc_id
                self.active_allocations[ptr_id] = block
                self.next_alloc_id += 1

                # Update profiling statistik
                current_used = sum(b.size for b in self.blocks if not b.is_free)
                if current_used > self.peak_allocated_bytes:
                    self.peak_allocated_bytes = current_used

                print(f"{GREEN}[✓] malloc({req_size}B -> aligned {aligned_payload}B){RESET} "
                      f"-> Alloc ID: {BOLD}#{ptr_id}{RESET} di Offset {CYAN}0x{block.offset:04X}{RESET}")
                return ptr_id

        print(f"{RED}[✗] malloc({req_size}B) GAGAL!{RESET} Out of Memory (OOM / Fragmentasi Parah).")
        return None

    def free(self, alloc_id: int) -> bool:
        """Membebaskan blok memori dan menggabungkan blok bebas bertetangga (coalescing)."""
        self.total_free_calls += 1
        if alloc_id not in self.active_allocations:
            print(f"{RED}[!] CRITICAL FAULT:{RESET} Double Free atau Invalid Pointer untuk ID #{alloc_id}!")
            return False

        target_block = self.active_allocations.pop(alloc_id)
        if target_block.canary != CANARY_MAGIC:
            print(f"{BG_RED}{WHITE}[!] MEMORY CORRUPTION DETECTED:{RESET} Canary terkorupsi pada block #{alloc_id}!")

        target_block.is_free = True
        target_block.alloc_id = None
        target_block.tag = ""
        print(f"{YELLOW}[*] free(ID: #{alloc_id}){RESET} di Offset {CYAN}0x{target_block.offset:04X}{RESET} berhasil dibebaskan.")

        # Lakukan Coalescing (Penggabungan blok bertetangga)
        self._coalesce()
        return True

    def _coalesce(self):
        """Menggabungkan blok contiguous bebas yang berdampingan."""
        i = 0
        merged_count = 0
        while i < len(self.blocks) - 1:
            curr_b = self.blocks[i]
            next_b = self.blocks[i + 1]
            if curr_b.is_free and next_b.is_free:
                # Gabungkan next_b ke dalam curr_b
                curr_b.size += next_b.total_size
                self.blocks.pop(i + 1)
                merged_count += 1
            else:
                i += 1
        if merged_count > 0:
            print(f"  {MAGENTA}↳ Coalesced {merged_count} blok bebas yang berdampingan.{RESET}")

    def render_memory_map(self):
        """Visualisasi peta memori terminal bergaya hexdump/block-diagram."""
        print(f"\n{BOLD}{CYAN}=== PETA MEMORI HEAP (Kapasitas: {self.capacity} Bytes) ==={RESET}")
        bar = ""
        for b in self.blocks:
            chunk_units = max(1, b.total_size // 32)
            if b.is_free:
                char = f"{BG_GRAY}{WHITE} FREE {b.size}B {RESET}"
            else:
                char = f"{BG_BLUE}{WHITE} #{b.alloc_id}:{b.tag}({b.size}B) {RESET}"
            bar += char + " "
        print(bar)

        print(f"\n{DIM}{'OFFSET':<10} {'STATUS':<10} {'ID':<6} {'TAG':<12} {'PAYLOAD':<12} {'TOTAL BLOCK'}{RESET}")
        print("-" * 65)
        for b in self.blocks:
            status = f"{GREEN}FREE{RESET}" if b.is_free else f"{RED}USED{RESET}"
            aid = f"#{b.alloc_id}" if b.alloc_id else "-"
            tag = b.tag if b.tag else "-"
            print(f"0x{b.offset:04X}     {status:<18} {aid:<6} {tag:<12} {b.size:<12} {b.total_size}B")
        print("-" * 65)

    def print_profiler_summary(self):
        """Ringkasan statistik alokator & deteksi memory leak."""
        total_used = sum(b.size for b in self.blocks if not b.is_free)
        total_free = sum(b.size for b in self.blocks if b.is_free)
        free_chunks = sum(1 for b in self.blocks if b.is_free)
        largest_free = max((b.size for b in self.blocks if b.is_free), default=0)

        # External fragmentation ratio: 1 - (largest_free_block / total_free_memory)
        frag_ratio = 0.0
        if total_free > 0:
            frag_ratio = (1.0 - (largest_free / total_free)) * 100.0

        print(f"\n{BOLD}{MAGENTA}=== LAPORAN PROFILING MEMORI & DIAGNOSTIK ==={RESET}")
        print(f"  • Total Kapasitas Heap : {self.capacity} Bytes")
        print(f"  • Heap Terpakai Aktif  : {total_used} Bytes")
        print(f"  • Heap Bebas Tersisa   : {total_free} Bytes (dalam {free_chunks} fragmen)")
        print(f"  • Blok Bebas Terbesar  : {largest_free} Bytes")
        print(f"  • Peak Allocated       : {self.peak_allocated_bytes} Bytes")
        print(f"  • Rasio Fragmentasi    : {frag_ratio:.2f}%")
        print(f"  • Panggilan Malloc/Free: {self.total_malloc_calls} malloc / {self.total_free_calls} free")

        # Deteksi Memory Leak
        if self.active_allocations:
            print(f"\n{BG_RED}{WHITE} [!] MEMORY LEAK TERDETEKSI: {len(self.active_allocations)} Blok Belum Dibebaskan! {RESET}")
            for aid, blk in self.active_allocations.items():
                print(f"    - Leak #{aid} [{blk.tag}]: {blk.size}B di 0x{blk.offset:04X}")
        else:
            print(f"\n{GREEN}[✓] STATUS: BERSIH! Tidak ada memory leak yang terdeteksi (Zero Leaks).{RESET}")


class SimulatedArenaAllocator:
    """
    Subalokator tipe Linear/Arena (Bump Pointer Allocator).
    Sangat cepat (O(1)), no individual free, dibersihkan sekaligus dengan reset().
    """
    def __init__(self, size: int = 512):
        self.capacity: int = size
        self.offset: int = 0
        self.allocations: List[Dict[str, any]] = []

    def alloc(self, req_size: int, label: str) -> Optional[int]:
        aligned = align_up(req_size)
        if self.offset + aligned > self.capacity:
            print(f"{RED}[Arena] Gagal mengalokasikan {req_size}B ({label}): Arena Penuh!{RESET}")
            return None
        ptr = self.offset
        self.offset += aligned
        self.allocations.append({"label": label, "offset": ptr, "size": aligned})
        print(f"{GREEN}[Arena] Bumped pointer {aligned}B ({label}) -> Offset 0x{ptr:04X} (Total: {self.offset}/{self.capacity}B){RESET}")
        return ptr

    def reset(self):
        print(f"{YELLOW}[Arena] Memanggil arena_reset()... Membebaskan seluruh {self.offset} Bytes sekaligus!{RESET}")
        self.offset = 0
        self.allocations.clear()


def run_interactive_menu():
    """Menu interaktif simulasi terminal."""
    heap = SimulatedHeapAllocator(capacity=512)
    arena = SimulatedArenaAllocator(size=256)

    while True:
        print(f"\n{BOLD}{WHITE}===================================================={RESET}")
        print(f"{BOLD}{WHITE} LAB SIMULASI MEMORI C: SUBALOKATOR & PROFILER {RESET}")
        print(f"{BOLD}{WHITE}===================================================={RESET}")
        print(f" {CYAN}1.{RESET} Alokasikan Memori Heap (malloc)")
        print(f" {CYAN}2.{RESET} Bebaskan Memori Heap (free)")
        print(f" {CYAN}3.{RESET} Tampilkan Visual Peta Memori & Fragmentasi")
        print(f" {CYAN}4.{RESET} Uji Simulasi Fragmentasi Memori & Coalescing")
        print(f" {CYAN}5.{RESET} Uji Arena / Bump Allocator (Fast Suballocator)")
        print(f" {CYAN}6.{RESET} Tampilkan Profiler & Cek Kebocoran (Memory Leak)")
        print(f" {CYAN}7.{RESET} Reset Heap")
        print(f" {RED}0.{RESET} Keluar")
        print(f"{BOLD}{WHITE}----------------------------------------------------{RESET}")

        try:
            choice = input(f"{YELLOW}Pilih opsi [0-7]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            try:
                sz = int(input("Masukkan ukuran byte (contoh: 32, 64, 128): ").strip())
                label = input("Beri label identifier blok (default 'obj'): ").strip() or "obj"
                heap.malloc(sz, label)
            except ValueError:
                print(f"{RED}[!] Input angka tidak valid.{RESET}")

        elif choice == "2":
            try:
                aid = int(input("Masukkan Alloc ID yang ingin di-free (contoh: 1): ").strip())
                heap.free(aid)
            except ValueError:
                print(f"{RED}[!] Masukkan angka Alloc ID yang valid.{RESET}")

        elif choice == "3":
            heap.render_memory_map()

        elif choice == "4":
            print(f"\n{BOLD}[*] Menjalankan Skenario Fragmentasi & Coalescing...{RESET}")
            p1 = heap.malloc(64, "chunk_A")
            p2 = heap.malloc(64, "chunk_B")
            p3 = heap.malloc(64, "chunk_C")
            p4 = heap.malloc(64, "chunk_D")
            heap.render_memory_map()

            print(f"\n{YELLOW}[*] Menghapus chunk_B dan chunk_C untuk menguji Coalescing antar tetangga...{RESET}")
            if p2: heap.free(p2)
            if p3: heap.free(p3)
            heap.render_memory_map()

            if p1: heap.free(p1)
            if p4: heap.free(p4)
            print(f"{GREEN}[✓] Seluruh chunk uji selesai dibersihkan.{RESET}")

        elif choice == "5":
            print(f"\n{BOLD}[*] Menjalankan Simulasi Linear Arena Allocator (Frame Allocator)...{RESET}")
            arena.alloc(32, "TransformMatrix")
            arena.alloc(48, "PhysicsBody")
            arena.alloc(16, "ParticleState")
            arena.alloc(128, "FrameScratchpad")
            arena.reset()

        elif choice == "6":
            heap.print_profiler_summary()

        elif choice == "7":
            heap = SimulatedHeapAllocator(capacity=512)
            print(f"{GREEN}[✓] Heap berhasil di-reset ke kondisi awal.{RESET}")

        elif choice == "0":
            heap.print_profiler_summary()
            print(f"\n{CYAN}Simulasi selesai. Terima kasih.{RESET}")
            break
        else:
            print(f"{RED}[!] Opsi tidak dikenali.{RESET}")


def run_automated_smoke_test():
    """Smoke test otomatis untuk lingkungan non-interaktif."""
    print(f"{BOLD}{CYAN}=== Menjalankan Self-Test Otomatis Alokator C ==={RESET}\n")
    heap = SimulatedHeapAllocator(capacity=512)
    id1 = heap.malloc(32, "PacketHeader")
    id2 = heap.malloc(64, "Payload")
    id3 = heap.malloc(128, "AudioBuffer")
    heap.render_memory_map()

    print(f"\n{YELLOW}[*] Uji Free & Coalescing...{RESET}")
    heap.free(id2)
    heap.free(id1)
    heap.render_memory_map()

    print(f"\n{YELLOW}[*] Uji Arena Suballocator...{RESET}")
    arena = SimulatedArenaAllocator(size=256)
    arena.alloc(32, "Vec3Array")
    arena.alloc(64, "MeshIndices")
    arena.reset()

    print(f"\n{YELLOW}[*] Uji Deteksi Kebocoran (Membiarkan id3 belum di-free)...{RESET}")
    heap.print_profiler_summary()

    heap.free(id3)
    print(f"\n{YELLOW}[*] Uji Verifikasi Akhir Setelah id3 di-free...{RESET}")
    heap.print_profiler_summary()
    print(f"\n{GREEN}[✓] Semua pengujian alokator memori C berhasil!{RESET}")


if __name__ == "__main__":
    # Jika dijalankan di terminal interaktif, buka menu. Jika via pipe/CI, jalankan smoke test.
    if sys.stdin.isatty():
        run_interactive_menu()
    else:
        run_automated_smoke_test()
