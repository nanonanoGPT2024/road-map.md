#!/usr/bin/env python3
"""
Hands-on Lab Exercise: C++ Memory Management & Resource Safety Simulation
Bab 02: Memory Management & Resource Safety (C++)
Fokus: Stack vs Heap, Raw Pointers, Memory Leaks, Double Free, Use-After-Free,
       RAII, std::unique_ptr, std::shared_ptr, and Reference Counting.
"""

import sys
import time
from typing import Dict, Optional, Any

# ANSI Terminal Color Codes
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
BG_DARK = "\033[40m"


class HeapBlock:
    """Representasi blok memori pada Virtual Heap."""
    def __init__(self, address: int, size: int, tag: str):
        self.address = address
        self.size = size
        self.tag = tag
        self.is_freed = False
        self.payload: Any = f"Payload({tag})"

    def hex_addr(self) -> str:
        return f"0x{self.address:08X}"


class VirtualMemoryArena:
    """Simulator Alokasi Memori Heap dan Deteksi Kesalahan C++."""
    def __init__(self, base_address: int = 0x55A00000):
        self.current_offset = 0
        self.base_address = base_address
        self.blocks: Dict[int, HeapBlock] = {}
        self.active_allocations = 0

    def allocate(self, size: int, tag: str) -> int:
        addr = self.base_address + self.current_offset
        self.current_offset += size + 16  # Padding 16 bytes
        block = HeapBlock(addr, size, tag)
        self.blocks[addr] = block
        self.active_allocations += 1
        return addr

    def deallocate(self, addr: int) -> bool:
        if addr not in self.blocks:
            print(f"{RED}[CRASH: SEGFAULT]{RESET} Alamat {hex(addr)} bukan pointer heap valid!")
            return False
        block = self.blocks[addr]
        if block.is_freed:
            print(f"{RED}[CRASH: DOUBLE FREE]{RESET} Alamat {block.hex_addr()} ({block.tag}) sudah dibebaskan sebelumnya!")
            return False
        block.is_freed = True
        self.active_allocations -= 1
        return True

    def read_ptr(self, addr: int) -> Optional[Any]:
        if addr not in self.blocks:
            print(f"{RED}[CRASH: INVALID ACCESS]{RESET} Alamat {hex(addr)} di luar batas arena.")
            return None
        block = self.blocks[addr]
        if block.is_freed:
            print(f"{RED}[CRASH: USE-AFTER-FREE]{RESET} Membaca alamat {block.hex_addr()} ({block.tag}) yang sudah di-free!")
            return None
        return block.payload

    def dump_leaks(self):
        leaks = [b for b in self.blocks.values() if not b.is_freed]
        print(f"\n{BOLD}=== Ringkasan Status Heap Memory ==={RESET}")
        if not leaks:
            print(f"{GREEN}[CLEAN]{RESET} 0 Memory Leaks terdeteksi. Semua resource telah dibebaskan.")
        else:
            total_bytes = sum(b.size for b in leaks)
            print(f"{RED}[LEAK DETECTED]{RESET} Ditemukan {len(leaks)} blok belum dibebaskan ({total_bytes} bytes):")
            for b in leaks:
                print(f"  -> {YELLOW}{b.hex_addr()}{RESET} | Size: {b.size:3d}B | Label: {CYAN}{b.tag}{RESET}")


class UniquePtr:
    """Simulasi std::unique_ptr (Exclusive Ownership & Move Semantics)."""
    def __init__(self, arena: VirtualMemoryArena, tag: str, size: int = 64):
        self.arena = arena
        self.tag = tag
        self.ptr: Optional[int] = arena.allocate(size, tag)
        print(f"  {GREEN}[std::unique_ptr::make_unique]{RESET} '{self.tag}' dialokasikan di {hex(self.ptr)}")

    def release(self) -> Optional[int]:
        raw = self.ptr
        self.ptr = None
        print(f"  {YELLOW}[std::unique_ptr::release]{RESET} Kepemilikan '{self.tag}' dilepas ke raw pointer.")
        return raw

    def move_to(self, target_name: str) -> "UniquePtr":
        if self.ptr is None:
            raise RuntimeError(f"Cannot move null unique_ptr '{self.tag}'")
        moved = UniquePtr.__new__(UniquePtr)
        moved.arena = self.arena
        moved.tag = f"{self.tag} -> {target_name}"
        moved.ptr = self.ptr
        self.ptr = None
        print(f"  {MAGENTA}[std::move]{RESET} Kepemilikan dipindah ke '{target_name}'. Asal kini bernilai nullptr.")
        return moved

    def get(self) -> Optional[int]:
        return self.ptr

    def __del__(self):
        if self.ptr is not None:
            print(f"  {CYAN}[RAII Destructor]{RESET} unique_ptr '{self.tag}' keluar scope -> Deallocate {hex(self.ptr)}")
            self.arena.deallocate(self.ptr)
            self.ptr = None


class ControlBlock:
    """Control Block untuk std::shared_ptr & std::weak_ptr."""
    def __init__(self, addr: int, tag: str):
        self.addr = addr
        self.tag = tag
        self.strong_count = 1
        self.weak_count = 0


class SharedPtr:
    """Simulasi std::shared_ptr dengan Reference Counting."""
    def __init__(self, arena: VirtualMemoryArena, tag: str, size: int = 64, existing_cb: Optional[ControlBlock] = None):
        self.arena = arena
        if existing_cb:
            self.cb = existing_cb
            self.cb.strong_count += 1
            print(f"  {GREEN}[std::shared_ptr COPY]{RESET} RefCount('{self.cb.tag}') naik -> {BOLD}{self.cb.strong_count}{RESET}")
        else:
            addr = arena.allocate(size, tag)
            self.cb = ControlBlock(addr, tag)
            print(f"  {GREEN}[std::make_shared]{RESET} '{tag}' di {hex(addr)} | RefCount awal: {BOLD}{self.cb.strong_count}{RESET}")

    def clone(self) -> "SharedPtr":
        return SharedPtr(self.arena, self.cb.tag, existing_cb=self.cb)

    def use_count(self) -> int:
        return self.cb.strong_count

    def reset(self):
        if self.cb:
            self._cleanup()
            self.cb = None

    def _cleanup(self):
        self.cb.strong_count -= 1
        print(f"  {YELLOW}[std::shared_ptr DROP]{RESET} RefCount('{self.cb.tag}') turun -> {BOLD}{self.cb.strong_count}{RESET}")
        if self.cb.strong_count == 0:
            print(f"  {RED}[RAII DELETE]{RESET} strong_count mencapai 0! Membebaskan memori {hex(self.cb.addr)}")
            self.arena.deallocate(self.cb.addr)

    def __del__(self):
        if hasattr(self, 'cb') and self.cb is not None:
            self._cleanup()


def print_banner():
    banner = f"""{CYAN}{BOLD}
========================================================================
     C++ MEMORY MANAGEMENT & RESOURCE SAFETY - INTERACTIVE LAB
       (Stack vs Heap, Raw Pointer Hazards, RAII & Smart Pointers)
========================================================================{RESET}"""
    print(banner)


def demo_raw_pointer_hazards(arena: VirtualMemoryArena):
    print(f"\n{BOLD}{BLUE}[DEMO 1] Bahaya Raw Pointers (Leak, Double Free, Use-After-Free){RESET}")
    print("1. Mengalokasikan 2 objek heap secara manual (new MyObject)...")
    p1 = arena.allocate(128, "RawBuffer_A")
    p2 = arena.allocate(256, "RawBuffer_B")
    print(f"   p1 di {hex(p1)}, p2 di {hex(p2)}")

    print("\n2. Membaca data dari p1:")
    val = arena.read_ptr(p1)
    print(f"   Hasil baca: {GREEN}{val}{RESET}")

    print("\n3. Mendealokasikan p1 (delete p1)...")
    arena.deallocate(p1)

    print("\n4. Mencoba Use-After-Free pada p1:")
    arena.read_ptr(p1)

    print("\n5. Mencoba Double Free pada p1 (delete p1 lagi):")
    arena.deallocate(p1)

    print("\n6. Mengabaikan p2 tanpa 'delete p2' (Simulasi Memory Leak)...")


def demo_raii_and_unique_ptr(arena: VirtualMemoryArena):
    print(f"\n{BOLD}{BLUE}[DEMO 2] RAII Idiom & std::unique_ptr (Move Semantics){RESET}")
    print("1. Membuat scope buatan { ... } dengan std::unique_ptr:")
    
    def scoped_work():
        u1 = UniquePtr(arena, "UniqueSocket", 128)
        print(f"   u1 alamat aktif: {hex(u1.get() or 0)}")
        print("   Memindahkan u1 ke u2 via std::move...")
        u2 = u1.move_to("u2_Worker")
        print(f"   u1 setelah move: {u1.get()} (nullptr)")
        print(f"   u2 alamat aktif: {hex(u2.get() or 0)}")
        print("   Meninggalkan scope lokal...")

    scoped_work()
    print("2. Di luar scope lokal: Memori otomatis di-cleanup oleh RAII destructor!")


def demo_shared_ptr_ref_count(arena: VirtualMemoryArena):
    print(f"\n{BOLD}{BLUE}[DEMO 3] Shared Ownership via std::shared_ptr & Ref Count{RESET}")
    print("1. Membuat master shared_ptr:")
    sp1 = SharedPtr(arena, "SharedDatabaseConnection", 512)
    
    print("\n2. Menduplikasi pointer ke thread/komponen lain (sp2, sp3):")
    sp2 = sp1.clone()
    sp3 = sp2.clone()
    print(f"   Total active owners: {BOLD}{sp1.use_count()}{RESET}")

    print("\n3. Melepaskan sp3:")
    sp3.reset()
    print(f"   Total active owners sekarang: {BOLD}{sp1.use_count()}{RESET}")

    print("\n4. Melepaskan sp2:")
    sp2.reset()
    print(f"   Total active owners sekarang: {BOLD}{sp1.use_count()}{RESET}")

    print("\n5. Melepaskan owner terakhir (sp1):")
    sp1.reset()


def run_interactive_menu():
    arena = VirtualMemoryArena()
    print_banner()

    menu = f"""{BOLD}Pilih Mode Simulasi:{RESET}
  {CYAN}1.{RESET} Demo Bahaya Raw Pointer (Leak, Use-After-Free, Double Free)
  {CYAN}2.{RESET} Demo RAII & std::unique_ptr (Move Semantics)
  {CYAN}3.{RESET} Demo std::shared_ptr (Reference Counting & Cleanup)
  {CYAN}4.{RESET} Jalankan Seluruh Demo Berurutan
  {CYAN}5.{RESET} Tampilkan Status Heap Memory & Leak Report
  {CYAN}q.{RESET} Keluar
"""

    while True:
        print(menu)
        try:
            choice = input(f"{YELLOW}Masukkan pilihan (1-5, q): {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting lab.")
            break

        if choice == '1':
            demo_raw_pointer_hazards(arena)
        elif choice == '2':
            demo_raii_and_unique_ptr(arena)
        elif choice == '3':
            demo_shared_ptr_ref_count(arena)
        elif choice == '4':
            demo_raw_pointer_hazards(arena)
            demo_raii_and_unique_ptr(arena)
            demo_shared_ptr_ref_count(arena)
            arena.dump_leaks()
        elif choice == '5':
            arena.dump_leaks()
        elif choice in ('q', 'exit'):
            print(f"{GREEN}Menutup Lab Simulator. Selamat belajar!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid!{RESET}")
        
        print("\n" + "-" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--auto", "--test", "-a"):
        # Mode otomatis tanpa input blocking (berguna untuk testing/CI)
        arena = VirtualMemoryArena()
        print_banner()
        demo_raw_pointer_hazards(arena)
        demo_raii_and_unique_ptr(arena)
        demo_shared_ptr_ref_count(arena)
        arena.dump_leaks()
    else:
        run_interactive_menu()
