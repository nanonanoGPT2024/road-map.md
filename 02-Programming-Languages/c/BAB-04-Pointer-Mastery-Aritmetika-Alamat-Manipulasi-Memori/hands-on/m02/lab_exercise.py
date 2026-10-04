#!/usr/bin/env python3
"""
Lab Hands-on: Pointer Mastery, Aritmetika Alamat, & Manipulasi Memori (C Deep Dive)
Modul 02: Arsitektur Memori Virtual, Dereferensi Tingkat Rendah, & Allocator Simulator.

Skrip ini mensimulasikan mekanisme runtime C:
1. Address Space & Virtual RAM (linear bytearray storage).
2. Pointer Representation & Typed Scaling (sizeof scaling dalam pointer arithmetic).
3. Type Punning / Reinterpret Cast (membaca alamat yang sama dengan tipe berbeda).
4. Mini-Heap Memory Allocator (Header blok, split, dan coalescing).
5. Hex Memory Dumper untuk visualisasi inspeksi memori C secara real-time.
"""

import sys
import struct
from typing import Any, Optional

# ANSI Color Codes untuk visualisasi output
RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
MAGENTA= "\033[35m"
CYAN   = "\033[36m"


class SegmentationFault(Exception):
    """Pengecualian ketika akses memori berada di luar rentang virtual address space."""
    pass


class VirtualRAM:
    """
    Mensimulasikan Address Space memori fisik/virtual C.
    Semua alokasi dan pointer beroperasi di atas bytearray linear ini.
    """
    def __init__(self, base_addr: int = 0x7FFF0000, size: int = 1024):
        self.base_addr = base_addr
        self.size = size
        self.memory = bytearray(size)

    def is_valid(self, addr: int, byte_len: int = 1) -> bool:
        offset = addr - self.base_addr
        return 0 <= offset and (offset + byte_len) <= self.size

    def read_bytes(self, addr: int, length: int) -> bytes:
        if not self.is_valid(addr, length):
            raise SegmentationFault(f"{RED}SIGSEGV: Invalid read at 0x{addr:08X} (len: {length}){RESET}")
        offset = addr - self.base_addr
        return bytes(self.memory[offset:offset + length])

    def write_bytes(self, addr: int, data: bytes) -> None:
        length = len(data)
        if not self.is_valid(addr, length):
            raise SegmentationFault(f"{RED}SIGSEGV: Invalid write at 0x{addr:08X} (len: {length}){RESET}")
        offset = addr - self.base_addr
        self.memory[offset:offset + length] = data


class CPointer:
    """
    Representasi abstraksi C Pointer typed (T*).
    Mendukung aritmetika pointer: ptr + n == addr + (n * sizeof(T)).
    """
    # Mapping C type specifiers ke (struct_fmt, sizeof, typename)
    TYPE_REGISTRY = {
        'char':   ('c', 1, 'char'),
        'int8':   ('b', 1, 'int8_t'),
        'uint8':  ('B', 1, 'uint8_t'),
        'int16':  ('h', 2, 'int16_t'),
        'uint16': ('H', 2, 'uint16_t'),
        'int32':  ('i', 4, 'int32_t'),
        'uint32': ('I', 4, 'uint32_t'),
        'float':  ('f', 4, 'float'),
        'int64':  ('q', 8, 'int64_t'),
        'double': ('d', 8, 'double'),
        'void':   (None, 1, 'void'),  # GNU C extension: sizeof(void) = 1
    }

    def __init__(self, ram: VirtualRAM, addr: int, dtype: str = 'int32'):
        if dtype not in self.TYPE_REGISTRY:
            raise ValueError(f"Unknown type: {dtype}")
        self.ram = ram
        self.addr = addr
        self.dtype = dtype
        self.fmt, self.size, self.type_name = self.TYPE_REGISTRY[dtype]

    def __add__(self, offset: int) -> 'CPointer':
        """Implementasi aritmetika alamat C: ptr + offset * sizeof(*ptr)"""
        new_addr = self.addr + (offset * self.size)
        return CPointer(self.ram, new_addr, self.dtype)

    def __sub__(self, other: Any) -> Any:
        """Selisih dua pointer mengembalikan jumlah elemen: (ptrA - ptrB) / sizeof(T)"""
        if isinstance(other, CPointer):
            if other.dtype != self.dtype:
                raise TypeError("Pointer subtraction requires identical base types.")
            return (self.addr - other.addr) // self.size
        elif isinstance(other, int):
            return self.__add__(-other)
        raise TypeError("Invalid subtraction operand.")

    def deref(self) -> Any:
        """Operator dereference (*ptr)."""
        if self.dtype == 'void':
            raise TypeError("Cannot dereference void pointer (void*).")
        raw = self.ram.read_bytes(self.addr, self.size)
        val = struct.unpack(f"<{self.fmt}", raw)[0]
        if self.dtype == 'char':
            return chr(val) if isinstance(val, int) else val.decode('latin1', errors='replace')
        return val

    def set(self, val: Any) -> None:
        """Operator dereference write (*ptr = value)."""
        if self.dtype == 'void':
            raise TypeError("Cannot assign value through void pointer (void*).")
        if self.dtype == 'char' and isinstance(val, str):
            val = ord(val[0])
        packed = struct.pack(f"<{self.fmt}", val)
        self.ram.write_bytes(self.addr, packed)

    def cast(self, new_dtype: str) -> 'CPointer':
        """Reinterpret cast (type punning): (new_type*)ptr"""
        return CPointer(self.ram, self.addr, new_dtype)

    def __getitem__(self, index: int) -> Any:
        """Akses array style: ptr[i] <=> *(ptr + i)"""
        return (self + index).deref()

    def __setitem__(self, index: int, val: Any) -> None:
        """Mutasi array style: ptr[i] = val <=> *(ptr + i) = val"""
        (self + index).set(val)

    def __repr__(self) -> str:
        return f"({self.type_name}*)0x{self.addr:08X}"


class MiniHeap:
    """
    Simulasi Heap Allocator sederhana (Implicit Free List / First-fit).
    Header: [size: uint32 | is_free: uint8 | padding: 3 bytes] -> total 8 bytes header.
    """
    HEADER_SIZE = 8
    MAGIC_FREE = 0xAA
    MAGIC_ALLOC = 0xBB

    def __init__(self, ram: VirtualRAM, heap_start: int, heap_size: int):
        self.ram = ram
        self.start = heap_start
        self.size = heap_size
        self.end = heap_start + heap_size

        # Inisialisasi blok awal sebagai satu blok kosong besar
        self._write_header(self.start, heap_size - self.HEADER_SIZE, is_free=True)

    def _write_header(self, addr: int, payload_size: int, is_free: bool) -> None:
        magic = self.MAGIC_FREE if is_free else self.MAGIC_ALLOC
        header_data = struct.pack("<IB3x", payload_size, magic)
        self.ram.write_bytes(addr, header_data)

    def _read_header(self, addr: int) -> tuple[int, bool]:
        data = self.ram.read_bytes(addr, self.HEADER_SIZE)
        payload_size, magic = struct.unpack("<IB3x", data)
        return payload_size, (magic == self.MAGIC_FREE)

    def malloc(self, req_bytes: int) -> Optional[CPointer]:
        """Alokasi memori berukuran req_bytes menggunakan algoritma First-Fit."""
        # Align ke batas 4-byte
        aligned_req = (req_bytes + 3) & ~3
        curr = self.start

        while curr < self.end:
            payload_size, is_free = self._read_header(curr)
            if is_free and payload_size >= aligned_req:
                # Cek apakah blok bisa di-split
                excess = payload_size - aligned_req - self.HEADER_SIZE
                if excess >= 8: # Minimal split chunk
                    self._write_header(curr, aligned_req, is_free=False)
                    split_addr = curr + self.HEADER_SIZE + aligned_req
                    self._write_header(split_addr, excess, is_free=True)
                else:
                    self._write_header(curr, payload_size, is_free=False)

                payload_ptr = curr + self.HEADER_SIZE
                return CPointer(self.ram, payload_ptr, 'void')
            
            curr += self.HEADER_SIZE + payload_size
        
        return None  # Out of Memory

    def free(self, ptr: CPointer) -> None:
        """Membebaskan blok dan menggabungkan blok bebas adjacent (coalescing)."""
        block_addr = ptr.addr - self.HEADER_SIZE
        payload_size, is_free = self._read_header(block_addr)
        if is_free:
            print(f"{YELLOW}[WARN] Double free detected at 0x{block_addr:08X}!{RESET}")
            return
        
        self._write_header(block_addr, payload_size, is_free=True)
        self._coalesce()

    def _coalesce(self) -> None:
        """Menggabungkan fragmen blok bebas berurutan."""
        curr = self.start
        while curr < self.end:
            payload_size, is_free = self._read_header(curr)
            next_block = curr + self.HEADER_SIZE + payload_size

            if next_block < self.end:
                next_size, next_free = self._read_header(next_block)
                if is_free and next_free:
                    # Gabungkan kedua blok
                    new_size = payload_size + self.HEADER_SIZE + next_size
                    self._write_header(curr, new_size, is_free=True)
                    continue  # Cek kembali jika blok setelahnya juga free
            curr = next_block


def hex_dump(ram: VirtualRAM, start_addr: int, length: int) -> None:
    """Menampilkan memori dengan layout hexa & karakter ASCII ala debugger GDB/xxd."""
    print(f"{BOLD}{CYAN}--- Memory Hex Dump [0x{start_addr:08X} - 0x{start_addr + length:08X}] ---{RESET}")
    for i in range(0, length, 16):
        curr = start_addr + i
        chunk = ram.read_bytes(curr, min(16, length - i))
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        print(f"{YELLOW}0x{curr:08X}{RESET}  {hex_str:<48}  |{GREEN}{ascii_str}{RESET}|")
    print(f"{BOLD}{CYAN}--------------------------------------------------------------{RESET}")


def run_lab() -> None:
    print(f"{BOLD}{MAGENTA}=================================================================={RESET}")
    print(f"{BOLD}{MAGENTA}   LAB: POINTER MASTERY & MEMORY MANIPULATION ENGINE (C DEEP DIVE){RESET}")
    print(f"{BOLD}{MAGENTA}=================================================================={RESET}\n")

    # Inisialisasi Virtual RAM
    ram = VirtualRAM(base_addr=0x7FFF0000, size=256)
    print(f"[*] Inisialisasi Virtual RAM: Base=0x{ram.base_addr:08X}, Size={ram.size} bytes.\n")

    # -------------------------------------------------------------
    # 1. Pointer Arithmetic & Scaling
    # -------------------------------------------------------------
    print(f"{BOLD}{BLUE}[DEMO 1: Pointer Arithmetic & Scale Factor]{RESET}")
    ptr_int = CPointer(ram, 0x7FFF0010, 'int32')
    ptr_char = CPointer(ram, 0x7FFF0010, 'char')

    print(f"Base Address: 0x{ptr_int.addr:08X}")
    print(f"Type (ptr_int) : {ptr_int.type_name} (sizeof: {ptr_int.size} bytes)")
    print(f"Type (ptr_char): {ptr_char.type_name} (sizeof: {ptr_char.size} bytes)")

    ptr_int_next = ptr_int + 2
    ptr_char_next = ptr_char + 2

    print(f"(ptr_int + 2)  -> 0x{ptr_int_next.addr:08X} (Delta: +{ptr_int_next.addr - ptr_int.addr} bytes)")
    print(f"(ptr_char + 2) -> 0x{ptr_char_next.addr:08X} (Delta: +{ptr_char_next.addr - ptr_char.addr} bytes)")

    # Isi array integer
    print("\n[*] Menulis array integer int32_t arr[3] = {0x11223344, 0x55667788, 0xAABBCCDD}")
    ptr_int[0] = 0x11223344
    ptr_int[1] = 0x55667788
    ptr_int[2] = 0xAABBCCDD
    hex_dump(ram, 0x7FFF0010, 16)

    # -------------------------------------------------------------
    # 2. Type Punning / Reinterpret Casting
    # -------------------------------------------------------------
    print(f"\n{BOLD}{BLUE}[DEMO 2: Type Punning & Little-Endian Byte Inspection]{RESET}")
    byte_inspector = ptr_int.cast('uint8')
    print(f"Membaca {ptr_int} via {byte_inspector}:")
    for i in range(4):
        val = byte_inspector[i]
        print(f"  *(byte_inspector + {i}) -> [0x{byte_inspector.addr + i:08X}] = 0x{val:02X}")
    print(f"{GREEN}=> Byte terendah (0x44) berada di alamat memori terendah (Little-Endian).{RESET}")

    # -------------------------------------------------------------
    # 3. Dynamic Memory Allocation Simulation (MiniHeap: malloc & free)
    # -------------------------------------------------------------
    print(f"\n{BOLD}{BLUE}[DEMO 3: Heap Allocator (First-Fit, Split, & Coalescing)]{RESET}")
    heap = MiniHeap(ram, heap_start=0x7FFF0080, heap_size=128)
    print(f"Heap initialized di [0x{heap.start:08X} - 0x{heap.end:08X}]")

    print("\n[*] Alokasi blok p1 = malloc(16)")
    p1 = heap.malloc(16)
    print(f"  -> Alamat p1: {p1}")

    print("[*] Alokasi blok p2 = malloc(24)")
    p2 = heap.malloc(24)
    print(f"  -> Alamat p2: {p2}")

    print("\n[*] Menulis string 'SYSTEM_C' ke blok p1")
    p1_str = p1.cast('char')
    for idx, ch in enumerate("SYSTEM_C"):
        p1_str[idx] = ch
    p1_str[8] = '\0'

    print("[*] Menulis 32-bit floats ke blok p2")
    p2_float = p2.cast('float')
    p2_float[0] = 3.141592
    p2_float[1] = 2.718281

    hex_dump(ram, 0x7FFF0080, 64)

    print("\n[*] Freeing p1...")
    heap.free(p1)
    print("[*] Freeing p2 (Triggering Coalescing)...")
    heap.free(p2)
    print(f"{GREEN}[OK] Kedua blok digabungkan kembali menjadi satu continuous chunk.{RESET}")
    hex_dump(ram, 0x7FFF0080, 32)

    # -------------------------------------------------------------
    # 4. Out-of-bounds Memory Safety Violation (SIGSEGV Simulation)
    # -------------------------------------------------------------
    print(f"\n{BOLD}{BLUE}[DEMO 4: Bounds Safety / Segmentation Fault Trap]{RESET}")
    wild_pointer = CPointer(ram, 0x7FFFFFFF, 'int32')
    print(f"Mencoba dereferensi dangling/invalid pointer: {wild_pointer}")
    try:
        wild_pointer.deref()
    except SegmentationFault as seg_err:
        print(f"Captured: {seg_err}")

    print(f"\n{BOLD}{GREEN}[LAB COMPLETE] Semua model arsitektur memori C sukses diverifikasi.{RESET}")


if __name__ == '__main__':
    run_lab()