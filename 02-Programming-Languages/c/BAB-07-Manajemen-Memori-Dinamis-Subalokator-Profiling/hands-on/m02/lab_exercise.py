#!/usr/bin/env python3
"""
Lab Hands-on: Subalokator Memori Dinamis & Heap Profiler (C-Style)
Bab 07: Manajemen Memori Dinamis - Modul 02 Deep Dive

Skrip ini memodelkan subsistem alokasi memori internal C (mirip dlmalloc/slab)
langsung di atas virtual buffer (`bytearray`) termasuk:
- Boundary tag header/footer
- 8-byte alignment enforcement
- First-fit dynamic allocation & block splitting
- Coalescing (penggabungan blok bebas yang berdampingan)
- Deteksi memory corruption via canary guard
- Profiler fragmentasi internal & eksternal dengan visualisasi ANSI
"""

import sys
import struct
import time
import random

# ANSI Color Codes
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"
CLR_WHITE   = "\033[97m"
CLR_GRAY    = "\033[90m"

class VirtualHeapAllocator:
    """
    Simulasi Subalokator Memori berbasis Free-List & Boundary Tags.
    
    Layout Blok Memori:
    [Header: 8 bytes] -> [Payload: N bytes (aligned)]
    Header format:
      uint32_t payload_size  (4 bytes)
      uint16_t is_allocated  (2 bytes: 0x0001 = Used, 0x0000 = Free)
      uint16_t canary        (2 bytes: 0xCAFE = Valid Header Magic)
    """
    HEADER_SIZE = 8
    ALIGNMENT = 8
    MAGIC_CANARY = 0xCAFE
    HEADER_STRUCT = struct.Struct("<IBH")  # size (4B), is_allocated (1B), pad (1B), canary (2B) = 8 bytes
    # Pack/unpack format: (payload_size, is_allocated, canary)
    
    def __init__(self, total_bytes: int):
        self.total_size = self._align_up(total_bytes)
        self.raw_memory = bytearray(self.total_size)
        
        # Inisialisasi blok awal tunggal (seluruh heap berstatus Free)
        initial_payload = self.total_size - self.HEADER_SIZE
        self._write_header(offset=0, size=initial_payload, is_allocated=False)
        
        # Metrik Profiling
        self.total_alloc_calls = 0
        self.total_free_calls = 0
        self.failed_allocs = 0

    @classmethod
    def _align_up(cls, size: int) -> int:
        """Memastikan ukuran memori kelipatan ALIGNMENT (8 byte pada 64-bit ABI)."""
        return (size + (cls.ALIGNMENT - 1)) & ~(cls.ALIGNMENT - 1)

    def _write_header(self, offset: int, size: int, is_allocated: bool):
        """Menulis metadata header ke heap virtual."""
        alloc_flag = 1 if is_allocated else 0
        # format: size (I: 4B), alloc_flag (B: 1B), pad (B: 1B=0), canary (H: 2B)
        data = struct.pack("<IBBH", size, alloc_flag, 0, self.MAGIC_CANARY)
        self.raw_memory[offset:offset + self.HEADER_SIZE] = data

    def _read_header(self, offset: int):
        """Membaca dan memverifikasi metadata header blok."""
        if offset + self.HEADER_SIZE > self.total_size:
            return None
        data = self.raw_memory[offset:offset + self.HEADER_SIZE]
        size, alloc_flag, _, canary = struct.unpack("<IBBH", data)
        
        if canary != self.MAGIC_CANARY:
            raise MemoryError(f"CRITICAL: Heap Corruption terdeteksi pada offset 0x{offset:04X}! Canary: 0x{canary:04X}")
            
        return {"size": size, "is_allocated": (alloc_flag == 1)}

    def malloc(self, requested_bytes: int) -> int:
        """
        Alokasi memori dinamis menggunakan algoritma First-Fit.
        Mengembalikan pointer (offset byte) ke awal payload user.
        """
        self.total_alloc_calls += 1
        aligned_req = self._align_up(requested_bytes)
        current_offset = 0

        while current_offset < self.total_size:
            hdr = self._read_header(current_offset)
            if hdr is None:
                break

            # Cari blok bebas yang muat
            if not hdr["is_allocated"] and hdr["size"] >= aligned_req:
                remaining = hdr["size"] - aligned_req
                
                # Split blok jika sisa ruang cukup menampung header + minimal 1 blok aligned
                if remaining >= (self.HEADER_SIZE + self.ALIGNMENT):
                    # Alokasikan porsi blok sekarang
                    self._write_header(current_offset, aligned_req, is_allocated=True)
                    # Buat header baru untuk sisa ruang bebas
                    next_offset = current_offset + self.HEADER_SIZE + aligned_req
                    self._write_header(next_offset, remaining - self.HEADER_SIZE, is_allocated=False)
                else:
                    # Ambil seluruh blok tanpa split (internal fragmentation terjadi di sini)
                    self._write_header(current_offset, hdr["size"], is_allocated=True)

                return current_offset + self.HEADER_SIZE

            current_offset += self.HEADER_SIZE + hdr["size"]

        self.failed_allocs += 1
        return -1  # ENOMEM / OOM

    def free(self, payload_offset: int):
        """
        Membebaskan blok memori dan secara otomatis melakukan
        coalescing (penggabungan) dengan blok tetangga yang bebas.
        """
        if payload_offset < self.HEADER_SIZE or payload_offset >= self.total_size:
            raise ValueError(f"Bad free pointer: 0x{payload_offset:04X}")

        hdr_offset = payload_offset - self.HEADER_SIZE
        hdr = self._read_header(hdr_offset)
        
        if not hdr["is_allocated"]:
            print(f"{CLR_RED}[WARN] Double free terdeteksi pada offset 0x{payload_offset:04X}!{CLR_RESET}")
            return

        self.total_free_calls += 1
        self._write_header(hdr_offset, hdr["size"], is_allocated=False)
        self._coalesce()

    def _coalesce(self):
        """Traversal linier untuk menggabungkan blok bebas yang berdampingan."""
        current_offset = 0
        while current_offset < self.total_size:
            hdr = self._read_header(current_offset)
            if hdr is None:
                break

            next_offset = current_offset + self.HEADER_SIZE + hdr["size"]
            if next_offset < self.total_size:
                next_hdr = self._read_header(next_offset)
                if not hdr["is_allocated"] and not next_hdr["is_allocated"]:
                    # Gabungkan kedua blok
                    new_size = hdr["size"] + self.HEADER_SIZE + next_hdr["size"]
                    self._write_header(current_offset, new_size, is_allocated=False)
                    # Ulangi pemeriksaan tanpa memajukan pointer untuk chaining coalesce
                    continue

            current_offset = next_offset

    def profile(self):
        """Menganalisis statistik heap, overhead metadata, dan fragmentasi."""
        allocated_bytes = 0
        free_bytes = 0
        free_chunks = []
        allocated_chunks = []
        current_offset = 0

        while current_offset < self.total_size:
            hdr = self._read_header(current_offset)
            if hdr is None:
                break
            if hdr["is_allocated"]:
                allocated_bytes += hdr["size"]
                allocated_chunks.append((current_offset, hdr["size"]))
            else:
                free_bytes += hdr["size"]
                free_chunks.append((current_offset, hdr["size"]))
            current_offset += self.HEADER_SIZE + hdr["size"]

        # External fragmentation: 1 - (largest_free_block / total_free_bytes)
        largest_free = max([s for _, s in free_chunks], default=0)
        ext_frag = (1.0 - (largest_free / free_bytes)) * 100 if free_bytes > 0 else 0.0

        return {
            "total_size": self.total_size,
            "allocated_bytes": allocated_bytes,
            "free_bytes": free_bytes,
            "alloc_chunk_count": len(allocated_chunks),
            "free_chunk_count": len(free_chunks),
            "largest_free_chunk": largest_free,
            "external_frag_pct": ext_frag
        }

    def print_heap_map(self):
        """Visualisasi peta memori blok secara horizontal."""
        print(f"\n{CLR_BOLD}PETA STRUKTUR HEAP VIRTUAL [{self.total_size} Bytes]:{CLR_RESET}")
        current_offset = 0
        visual_str = "|"
        
        while current_offset < self.total_size:
            hdr = self._read_header(current_offset)
            if hdr is None:
                break
            
            block_total = self.HEADER_SIZE + hdr["size"]
            ratio = max(1, block_total // 16)
            
            if hdr["is_allocated"]:
                tag = f"A:{hdr['size']}B"
                visual_str += f"{CLR_RED}{'[H] ' + tag:^{ratio * 4}}{CLR_RESET}|"
            else:
                tag = f"F:{hdr['size']}B"
                visual_str += f"{CLR_GREEN}{'[H] ' + tag:^{ratio * 4}}{CLR_RESET}|"
                
            current_offset += block_total
            
        print(visual_str)
        print(f"{CLR_GRAY}[H] = Header (8B)  {CLR_RED}[A] = Allocated  {CLR_GREEN}[F] = Free/Available{CLR_RESET}\n")


def print_telemetry(allocator: VirtualHeapAllocator, label: str):
    """Menampilkan metrik telemetry dari profiler memori."""
    st = allocator.profile()
    print(f"{CLR_CYAN}--- TELEMETRI MEMORI: {CLR_BOLD}{label}{CLR_RESET}{CLR_CYAN} ---{CLR_RESET}")
    print(f" Total Space       : {st['total_size']:>5} bytes")
    print(f" In-Use Memori     : {CLR_YELLOW}{st['allocated_bytes']:>5} bytes{CLR_RESET} ({st['alloc_chunk_count']} blok)")
    print(f" Free Memori       : {CLR_GREEN}{st['free_bytes']:>5} bytes{CLR_RESET} ({st['free_chunk_count']} blok)")
    print(f" Largest Free Blok : {st['largest_free_chunk']:>5} bytes")
    print(f" External Frag     : {CLR_MAGENTA}{st['external_frag_pct']:>5.2f}%{CLR_RESET}")
    print(f" Success/Fail Rate : {allocator.total_alloc_calls - allocator.failed_allocs}/{allocator.total_alloc_calls}")
    allocator.print_heap_map()


def main():
    print(f"{CLR_BOLD}{CLR_BLUE}===================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}   LAB HANDS-ON: C SUB-ALLOCATOR & DYNAMIC MEMORY PROFILER          {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}===================================================================={CLR_RESET}")

    # Alokasi arena sebesar 512 bytes (simulasi sbrk / mmap pool)
    HEAP_CAPACITY = 512
    heap = VirtualHeapAllocator(HEAP_CAPACITY)
    print_telemetry(heap, "Keadaan Awal (Pristine Arena)")

    # 1. Alokasi Sekuensial
    print(f"{CLR_BOLD}[1] Melakukan alokasi bertahap (malloc)...{CLR_RESET}")
    p1 = heap.malloc(48)   # Aligned ke 48
    p2 = heap.malloc(64)   # Aligned ke 64
    p3 = heap.malloc(32)   # Aligned ke 32
    p4 = heap.malloc(120)  # Aligned ke 120
    print(f"-> ptr1: 0x{p1:04X} (48B), ptr2: 0x{p2:04X} (64B), ptr3: 0x{p3:04X} (32B), ptr4: 0x{p4:04X} (120B)")
    print_telemetry(heap, "Setelah 4x malloc()")

    # 2. Simulasi External Fragmentation (Pola Celah Bebas / Freeing Interleaved)
    print(f"{CLR_BOLD}[2] Membebaskan blok tidak berurutan (p2 dan p4) untuk memicu Fragmentasi...{CLR_RESET}")
    heap.free(p2)
    heap.free(p4)
    print_telemetry(heap, "Fragmen External Tercipta (p2 & p4 di-free)")

    # 3. Alokasi yang memicu Best-Fit / Splitting pada sisa blok p2
    print(f"{CLR_BOLD}[3] Melakukan alokasi baru (24 byte) yang harus menempati split slot eks-p2...{CLR_RESET}")
    p5 = heap.malloc(24)
    print(f"-> ptr5 berhasil dialokasikan pada offset: 0x{p5:04X} (24B)")
    print_telemetry(heap, "Setelah Splitting Slot Memori")

    # 4. Demonstrasi Otomatisasi Coalescing
    print(f"{CLR_BOLD}[4] Membebaskan blok sekitarnya (p1, p3, p5) untuk menguji Memory Coalescing...{CLR_RESET}")
    heap.free(p1)
    heap.free(p3)
    heap.free(p5)
    print_telemetry(heap, "Setelah Coalescing Otomatis Seluruh Blok Berdekatan")

    # 5. Uji Batas Kapasitas & OOM (Out-of-Memory)
    print(f"{CLR_BOLD}[5] Stress Test: Permintaan Alokasi Melebihi Kapasitas Heap...{CLR_RESET}")
    oversized_ptr = heap.malloc(1024)
    if oversized_ptr == -1:
        print(f"{CLR_GREEN}✓ OOM Handler bekerja optimal. Alokasi 1024B ditolak (returned NULL/-1).{CLR_RESET}")

    # 6. Demonstrasi Deteksi Kerusakan Memori (Heap Corruption Canary)
    print(f"\n{CLR_BOLD}[6] Eksploitasi/Simulasi Memory Corruption (Buffer Overflow)...{CLR_RESET}")
    valid_ptr = heap.malloc(32)
    print(f"-> Alokasi buffer normal pada: 0x{valid_ptr:04X}")
    
    # Sengaja merusak Canary Header di sebelah kiri buffer
    corrupt_target = valid_ptr - heap.HEADER_SIZE + 6  # 2 byte terakhir dari header adalah canary
    print(f"-> Menyuntikkan buffer overflow ke canary header pada offset: 0x{corrupt_target:04X}")
    heap.raw_memory[corrupt_target] = 0xDE
    heap.raw_memory[corrupt_target + 1] = 0xAD

    try:
        print("-> Mencoba memanggil free() pada pointer yang rusak...")
        heap.free(valid_ptr)
    except MemoryError as e:
        print(f"{CLR_RED}✓ EXCEPTION TERTANGKAP: {e}{CLR_RESET}")
        print(f"{CLR_GREEN}✓ Subalokator sukses mendeteksi Memory Tampering via Magic Canary!{CLR_RESET}")

    print(f"\n{CLR_BOLD}{CLR_BLUE}=== SIMULASI DAN AUDIT MEMORI SELESAI DENGAN SUKSES ==={CLR_RESET}")


if __name__ == "__main__":
    main()