#!/usr/bin/env python3
"""
Lab Hands-on: C++ Deep Dive - Memory Internals, RAII, Move Semantics & VTable
Kategori: 02-Programming-Languages / cpp / Bab 03 - Modul 02

Deskripsi:
Script ini memodelkan subsistem runtime C++ tingkat rendah:
1. Heap Allocation Tracker & RAII Lifetime Controller.
2. Smart Pointer Mechanics: UniquePtr (Move-only) & SharedPtr (Reference Counting).
3. Move Semantics: Ownership transfer vs deep-copy overhead.
4. Polymorphism Engine: Virtual Method Table (vtable) & vptr dynamic dispatch.
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# ANSI Formatting Helpers
# ============================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


def print_header(title: str) -> None:
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}{'='*70}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.YELLOW} [C++ RUNTIME EMULATOR] {title}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}{'='*70}{TermColor.RESET}")


def print_step(msg: str) -> None:
    print(f"{TermColor.BOLD}{TermColor.GREEN}[+] {msg}{TermColor.RESET}")


def print_warn(msg: str) -> None:
    print(f"{TermColor.BOLD}{TermColor.RED}[!] {msg}{TermColor.RESET}")


# ============================================================================
# 1. SIMULASI HEAP & RAII LIFECYCLE
# ============================================================================
class HeapMemoryManager:
    """Mensimulasikan low-level heap allocator C++ (malloc/free & new/delete)."""
    def __init__(self):
        self._allocations: Dict[int, int] = {}  # Address -> Size in bytes
        self._next_address: int = 0x1000

    def allocate(self, size: int) -> int:
        addr = self._next_address
        self._allocations[addr] = size
        self._next_address += max(size, 8)
        print(f"  {TermColor.BLUE}[heap::new]{TermColor.RESET} Allocated {size} bytes at 0x{addr:X}")
        return addr

    def deallocate(self, addr: int) -> None:
        if addr in self._allocations:
            size = self._allocations.pop(addr)
            print(f"  {TermColor.MAGENTA}[heap::delete]{TermColor.RESET} Freed {size} bytes at 0x{addr:X}")
        else:
            print_warn(f"Double Free or Invalid Pointer Detected at 0x{addr:X}!")

    def active_leak_bytes(self) -> int:
        return sum(self._allocations.values())


GLOBAL_HEAP = HeapMemoryManager()


# ============================================================================
# 2. MOVE SEMANTICS & SMART POINTER ENGINE (std::unique_ptr & std::shared_ptr)
# ============================================================================
class UniquePtr:
    """
    Simulasi std::unique_ptr<T>:
    - Exclusive ownership.
    - Copy construction/assignment dilarang (Deleted).
    - Move construction/assignment mentransfer address ownership.
    """
    def __init__(self, raw_addr: Optional[int] = None, data_repr: str = ""):
        self._addr = raw_addr
        self._repr = data_repr

    def __del__(self):
        # Destructor otomatis (RAII)
        if self._addr is not None:
            print(f"  {TermColor.YELLOW}[~UniquePtr]{TermColor.RESET} RAII Cleanup on payload: '{self._repr}'")
            GLOBAL_HEAP.deallocate(self._addr)
            self._addr = None

    def release(self) -> Optional[int]:
        """Menyerahkan kepemilikan tanpa mendestruksi resource."""
        res = self._addr
        self._addr = None
        return res

    def move(self) -> 'UniquePtr':
        """Simulasi std::move(): mentransfer ownership, mengosongkan objek asal."""
        if self._addr is None:
            raise RuntimeError("Attempted to move an empty or already moved unique_ptr!")
        new_ptr = UniquePtr(self._addr, self._repr)
        self._addr = None  # Sumber beralih ke state null/moved-from
        return new_ptr

    def get(self) -> Optional[int]:
        return self._addr

    def is_valid(self) -> bool:
        return self._addr is not None


class ControlBlock:
    """Simulasi control block pada std::shared_ptr (strong & weak ref counting)."""
    def __init__(self, addr: int, data_repr: str):
        self.addr: int = addr
        self.data_repr: str = data_repr
        self.strong_count: int = 1


class SharedPtr:
    """Simulasi std::shared_ptr<T> dengan Shared Ownership & Reference Counting."""
    def __init__(self, target: Optional['SharedPtr'] = None, new_addr: Optional[int] = None, data_repr: str = ""):
        if target is not None:
            # Copy Constructor: Inc ref count
            self._cb = target._cb
            if self._cb:
                self._cb.strong_count += 1
                print(f"  {TermColor.CYAN}[shared_ptr::copy]{TermColor.RESET} RefCount incremented: {self._cb.strong_count}")
        elif new_addr is not None:
            # Direct constructor
            self._cb = ControlBlock(new_addr, data_repr)
            print(f"  {TermColor.CYAN}[shared_ptr::init]{TermColor.RESET} RefCount initialized: 1")
        else:
            self._cb = None

    def __del__(self):
        if self._cb is not None:
            self._cb.strong_count -= 1
            print(f"  {TermColor.YELLOW}[~SharedPtr]{TermColor.RESET} RefCount decremented: {self._cb.strong_count}")
            if self._cb.strong_count == 0:
                print(f"  {TermColor.MAGENTA}[SharedPtr RAII]{TermColor.RESET} Strong ref count 0! Releasing resource.")
                GLOBAL_HEAP.deallocate(self._cb.addr)
                self._cb = None

    def use_count(self) -> int:
        return self._cb.strong_count if self._cb else 0


# ============================================================================
# 3. POLIMORFISME RUNTIME: VTABLE & VPTR DISPATCH SIMULATION
# ============================================================================
class VTable:
    """Representasi tabel virtual function lookup table internal C++."""
    def __init__(self, class_name: str, methods: Dict[str, Callable[['CppObject'], str]]):
        self.class_name = class_name
        self.methods = methods


class CppObject:
    """Simulasi base layout dari objek C++ dengan Virtual Pointer (vptr)."""
    def __init__(self, vtable: VTable, name: str):
        # 8-byte vptr tersembunyi pada header objek (simulasi)
        self.vptr: VTable = vtable
        self.name: str = name

    def dynamic_dispatch(self, method_name: str) -> str:
        """Emulasi call resolusi runtime melalui vptr->vtable[func_offset]"""
        if method_name in self.vptr.methods:
            func = self.vptr.methods[method_name]
            return func(self)
        raise NotImplementedError(f"Virtual method {method_name} tidak ditemukan pada {self.vptr.class_name}")


# VTable Method Definitions
def base_render(obj: CppObject) -> str:
    return f"Base::render() -> Generic Component [{obj.name}]"

def derived_ui_render(obj: CppObject) -> str:
    return f"UIButton::render() -> [Modern Widget UI Component: '{obj.name}']"

def derived_canvas_render(obj: CppObject) -> str:
    return f"GLCanvas::render() -> [OpenGL Framebuffer Context: '{obj.name}']"

# Instansiasi VTable statis (hanya 1 per class type di level text/rodata)
VTABLE_BASE = VTable("BaseComponent", {"render": base_render})
VTABLE_UI = VTable("UIButton", {"render": derived_ui_render})
VTABLE_CANVAS = VTable("GLCanvas", {"render": derived_canvas_render})


# ============================================================================
# 4. BENCHMARK MOVE SEMANTICS VS DEEP COPY
# ============================================================================
def benchmark_move_vs_copy():
    print_step("Memulai Benchmark: Deep Copy (C++98) vs Move Semantics (C++11/Modern)")
    payload_size = 500_000
    iterations = 20

    # 1. Deep Copy Simulation
    start_copy = time.perf_counter()
    for _ in range(iterations):
        buffer = list(range(payload_size))
        copied_buffer = list(buffer)  # Deep memory clone
        del buffer
        del copied_buffer
    elapsed_copy = (time.perf_counter() - start_copy) * 1000

    # 2. Move Semantics Simulation (Pointer swapping / metadata transfer)
    start_move = time.perf_counter()
    for _ in range(iterations):
        buffer = list(range(payload_size))
        moved_buffer = buffer  # Re-bind pointer reference tanpa cloning payload
        buffer = None          # Invalidasi origin rvalue
        del moved_buffer
    elapsed_move = (time.perf_counter() - start_move) * 1000

    print(f"  {TermColor.WHITE}Deep Copy Elapsed ({iterations} ops): {TermColor.RED}{elapsed_copy:.2f} ms{TermColor.RESET}")
    print(f"  {TermColor.WHITE}Move Semantics Elapsed ({iterations} ops): {TermColor.GREEN}{elapsed_move:.2f} ms{TermColor.RESET}")
    speedup = elapsed_copy / max(elapsed_move, 0.0001)
    print(f"  {TermColor.BOLD}Kalkulasi Speedup Move: {TermColor.YELLOW}{speedup:.1f}x lebih efisien{TermColor.RESET}")


# ============================================================================
# MAIN EXECUTION ROUTINE
# ============================================================================
def main():
    print_header("MODUL DEEP DIVE: C++ MEMORY, RAII, SMART PTR & VTABLE")

    # Bagian 1: Move Semantics & RAII dengan UniquePtr
    print_step("1. Pengujian Eksklusivitas std::unique_ptr & std::move")
    addr1 = GLOBAL_HEAP.allocate(64)
    u_ptr1 = UniquePtr(addr1, "Matrix4x4_Transform")
    print(f"  u_ptr1 aktif pada: 0x{u_ptr1.get():X}")

    print("  Mentransfer kepemilikan: u_ptr2 = std::move(u_ptr1)...")
    u_ptr2 = u_ptr1.move()

    print(f"  Status u_ptr1 setelah di-move: {'Valid' if u_ptr1.is_valid() else 'Nullptr/Empty'}")
    print(f"  Status u_ptr2 memegang address: 0x{u_ptr2.get():X}")
    print("  Keluar scope u_ptr1 & u_ptr2...")
    del u_ptr1
    del u_ptr2

    # Bagian 2: Shared Ownership dengan SharedPtr
    print_step("2. Pengujian std::shared_ptr Reference Counting Mechanics")
    addr2 = GLOBAL_HEAP.allocate(128)
    sp1 = SharedPtr(new_addr=addr2, data_repr="AudioBuffer_Asset")
    print(f"  Instance sp1 dibuat. Use Count = {sp1.use_count()}")

    print("  Membuat copy reference: sp2 = sp1, sp3 = sp1")
    sp2 = SharedPtr(target=sp1)
    sp3 = SharedPtr(target=sp1)
    print(f"  Current active references: {sp1.use_count()}")

    print("  Menghapus reference sp3 dan sp2...")
    del sp3
    print(f"  Count setelah sp3 hilang: {sp1.use_count()}")
    del sp2
    print(f"  Count setelah sp2 hilang: {sp1.use_count()}")
    print("  Menghapus reference terakhir (sp1)...")
    del sp1

    # Bagian 3: VTable Dynamic Dispatch
    print_step("3. Dynamic Dispatch & VTable Resolution Simulation")
    instances: List[CppObject] = [
        CppObject(VTABLE_BASE, "AbstractPanel"),
        CppObject(VTABLE_UI, "SubmitButton_OK"),
        CppObject(VTABLE_CANVAS, "Viewport3D")
    ]

    print(f"  {'Object Name':<20} | {'VTable Class':<15} | {'Resolved Function Call'}")
    print(f"  {'-'*20}-+-{'-'*15}-+-{'-'*30}")
    for inst in instances:
        resolved_call = inst.dynamic_dispatch("render")
        print(f"  {inst.name:<20} | {inst.vptr.class_name:<15} | {resolved_call}")

    # Bagian 4: Benchmark Move vs Copy
    print_step("4. Performance Profiling")
    benchmark_move_vs_copy()

    # Bagian 5: Memory Leak Audit
    print_step("5. Memory Leak Sanity Check (Heap Audit)")
    leaks = GLOBAL_HEAP.active_leak_bytes()
    if leaks == 0:
        print(f"  {TermColor.GREEN}[PASSED] Tidak ada kebocoran memori terdeteksi! Semua resource di-cleanup via RAII.{TermColor.RESET}")
    else:
        print_warn(f"Kebocoran terdeteksi: {leaks} bytes tertinggal di heap!")

    print(f"\n{TermColor.BOLD}{TermColor.GREEN}=== Lab Eksekusi C++ Berhasil Selesai Secara Valid ==={TermColor.RESET}\n")


if __name__ == "__main__":
    main()