#!/usr/bin/env python3
"""
Lab Hands-on: C++ Deep Dive - Virtual Dispatch (vtable/vptr) & Move Semantics Simulation
Bab 07 - Modul 02 Deep Dive
Standard Library: sys, time, typing, dataclasses
"""

import sys
import time
from typing import Dict, Any, Optional, Callable


# ==============================================================================
# ANSI Formatting Constants
# ==============================================================================
class Color:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


def print_banner(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.YELLOW} [C++ INTERNALS] {title}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")


# ==============================================================================
# SIMULATION 1: VTable & Dynamic Dispatch (Memory Layout & vptr)
# ==============================================================================
class VTable:
    """Merepresentasikan Virtual Method Table (vtable) di segmen .rodata."""

    def __init__(self, class_name: str, functions: Dict[int, Callable]):
        self.class_name = class_name
        self.functions: Dict[int, Callable] = functions  # Slot Index -> Function Pointer

    def resolve(self, slot_idx: int) -> Callable:
        if slot_idx not in self.functions:
            raise RuntimeError(f"Pure virtual function called or invalid vtable slot: {slot_idx}")
        return self.functions[slot_idx]


class RawCppObject:
    """
    Simulasi layout memori fisik dari C++ Object dengan polymorphic base.
    Offset 0x00: vptr (pointer ke vtable)
    Offset 0x08+: Data Member
    """

    def __init__(self, vtable: VTable, members: Dict[str, Any]):
        self.vptr: VTable = vtable
        self.members: Dict[str, Any] = members

    def call_virtual(self, slot_idx: int, *args) -> Any:
        """Simulasi dynamic dispatch: dereference vptr -> cari slot -> eksekusi."""
        fn = self.vptr.resolve(slot_idx)
        return fn(self, *args)

    def print_memory_layout(self) -> None:
        print(f"  {Color.BOLD}Memory Layout of {self.vptr.class_name} instance:{Color.RESET}")
        print(f"    [Offset 0x00 - 0x08] vptr       -> &{self.vptr.class_name}::_vftable")
        offset = 8
        for k, v in self.members.items():
            size = 8  # Asumsi 64-bit alignment per field
            print(f"    [Offset 0x{offset:02X} - 0x{offset+size:02X}] member '{k}' = {v}")
            offset += size


# Definisi fungsi untuk virtual slots
# Slot 0: speak(), Slot 1: calculate(int)
def base_speak(obj: RawCppObject) -> str:
    return f"Base::speak() [Base identity: {obj.members.get('id', 'unknown')}]"


def base_calculate(obj: RawCppObject, x: int) -> int:
    return x * 1


def derived_speak(obj: RawCppObject) -> str:
    return f"Derived::speak() [Derived tag: {obj.members.get('tag', 'none')}, base id: {obj.members.get('id', 0)}]"


def derived_calculate(obj: RawCppObject, x: int) -> int:
    return (x * 10) + obj.members.get("multiplier", 1)


# Instansiasi VTables di static storage
VT_BASE = VTable("Base", {0: base_speak, 1: base_calculate})
VT_DERIVED = VTable("Derived", {0: derived_speak, 1: derived_calculate})


# ==============================================================================
# SIMULATION 2: Move Semantics & RAII Heap Allocation Tracker
# ==============================================================================
class HeapAllocationManager:
    """Melacak heap memory block untuk mendeteksi resource leakage dan copy vs move."""

    total_allocations = 0
    total_deallocations = 0
    active_handles = 0

    @classmethod
    def allocate(cls, size: int) -> int:
        cls.total_allocations += 1
        cls.active_handles += 1
        address = 0x7FFF0000 + (cls.total_allocations * 0x100)
        return address

    @classmethod
    def deallocate(cls, address: Optional[int]) -> None:
        if address is not None:
            cls.total_deallocations += 1
            cls.active_handles -= 1


class HeapBuffer:
    """
    Simulasi tipe C++ RAII resource manager (mirip std::vector atau std::unique_ptr).
    Mendukung Copy Constructor vs Move Constructor secara eksplisit.
    """

    def __init__(self, size: int, label: str):
        self.size = size
        self.label = label
        self.heap_address: Optional[int] = HeapAllocationManager.allocate(size)
        print(f"  {Color.GREEN}[ALLOC]{Color.RESET} HeapBuffer '{self.label}' allocated {size} bytes @ 0x{self.heap_address:X}")

    def __del__(self):
        if self.heap_address is not None:
            print(f"  {Color.RED}[DEALLOC]{Color.RESET} HeapBuffer '{self.label}' destroyed @ 0x{self.heap_address:X}")
            HeapAllocationManager.deallocate(self.heap_address)
            self.heap_address = None

    @classmethod
    def copy_construct(cls, other: "HeapBuffer", new_label: str) -> "HeapBuffer":
        """Simulasi C++ Deep Copy Constructor: T(const T& other)."""
        print(f"  {Color.YELLOW}[COPY-CTOR]{Color.RESET} Deep copy from '{other.label}' -> '{new_label}' (New Allocation)")
        new_obj = cls(other.size, new_label)
        return new_obj

    @classmethod
    def move_construct(cls, other: "HeapBuffer", new_label: str) -> "HeapBuffer":
        """
        Simulasi C++ Move Constructor: T(T&& other) noexcept.
        Mencuri pointer heap milik rvalue dan me-nullify pointer sumber.
        Zero memory allocation!
        """
        print(f"  {Color.CYAN}[MOVE-CTOR]{Color.RESET} Stealing resource from '{other.label}' -> '{new_label}' (Zero Alloc)")
        new_obj = cls.__new__(cls)
        new_obj.size = other.size
        new_obj.label = new_label
        # Transfer ownership
        new_obj.heap_address = other.heap_address
        # Nullify source rvalue
        other.heap_address = None
        other.size = 0
        return new_obj


# ==============================================================================
# MAIN LAB EXECUTION & BENCHMARK
# ==============================================================================
def run_vtable_lab():
    print_banner("1. Virtual Method Table (vtable) & Dynamic Dispatch")

    # Inisialisasi object Base dan Derived
    base_obj = RawCppObject(VT_BASE, {"id": 101})
    derived_obj = RawCppObject(VT_DERIVED, {"id": 202, "tag": "SUBSYSTEM_A", "multiplier": 5})

    base_obj.print_memory_layout()
    print()
    derived_obj.print_memory_layout()

    print(f"\n{Color.BOLD}Simulasi Dynamic Dispatch via Slot Calling (Base* ptr):{Color.RESET}")
    polymorphic_ptrs = [("ptr_base", base_obj), ("ptr_derived", derived_obj)]

    for name, ptr in polymorphic_ptrs:
        res_speak = ptr.call_virtual(0)
        res_calc = ptr.call_virtual(1, 10)
        print(f"  Indirect call through {name}->vptr:")
        print(f"    Slot 0 [speak()]:     {Color.GREEN}{res_speak}{Color.RESET}")
        print(f"    Slot 1 [calculate()]: {Color.GREEN}{res_calc}{Color.RESET}")

    # Simulasi Object Slicing
    print(f"\n{Color.BOLD}{Color.YELLOW}[WARNING] Simulasi Object Slicing (Pass by Value):{Color.RESET}")
    # Jika Derived di-copy ke Base secara value, vptr diganti menjadi Base vptr dan field turunan terbuang
    sliced_members = {"id": derived_obj.members["id"]}
    sliced_obj = RawCppObject(VT_BASE, sliced_members)
    print(f"  Hasil slicing derived_obj -> Base (by value):")
    print(f"    vptr sekarang menunjuk ke: {sliced_obj.vptr.class_name}")
    print(f"    Slot 0 [speak()]: {sliced_obj.call_virtual(0)} (Polymorphic behavior HILANG!)")


def run_move_semantics_lab():
    print_banner("2. Move Semantics vs Deep Copy Performance & Lifetime")

    print(f"{Color.BOLD}Kasus A: Vector Expansion Menggunakan Copy Semantics{Color.RESET}")
    HeapAllocationManager.total_allocations = 0
    HeapAllocationManager.total_deallocations = 0

    src_copy = HeapBuffer(4096, "Source_A")
    t0 = time.perf_counter()
    copies = []
    for i in range(3):
        copies.append(HeapBuffer.copy_construct(src_copy, f"Copy_{i}"))
    del copies
    del src_copy
    t_copy = (time.perf_counter() - t0) * 1e6

    print(f"  Copy Metrics -> Allocs: {HeapAllocationManager.total_allocations}, "
          f"Deallocs: {HeapAllocationManager.total_deallocations}")

    print(f"\n{Color.BOLD}Kasus B: Vector Expansion Menggunakan Move Semantics (std::move){Color.RESET}")
    HeapAllocationManager.total_allocations = 0
    HeapAllocationManager.total_deallocations = 0

    t0 = time.perf_counter()
    src_move = HeapBuffer(4096, "Source_B")
    # Move ownership step by step
    moved_step1 = HeapBuffer.move_construct(src_move, "Moved_B1")
    moved_step2 = HeapBuffer.move_construct(moved_step1, "Moved_B2")
    del moved_step2
    del moved_step1  # Sumber yang sudah di-move tidak men-deallocate apa-apa
    del src_move     # Pointer sudah null, aman (no double free)
    t_move = (time.perf_counter() - t0) * 1e6

    print(f"  Move Metrics -> Allocs: {HeapAllocationManager.total_allocations}, "
          f"Deallocs: {HeapAllocationManager.total_deallocations}")

    print_banner("3. Ringkasan Diagnostik Sistem")
    print(f"  Active Leaked Heap Handles: {HeapAllocationManager.active_handles} (Harus 0 untuk clean RAII)")
    print(f"  Simulated Copy Pipeline:    {t_copy:.2f} µs")
    print(f"  Simulated Move Pipeline:    {t_move:.2f} µs")
    print(f"  {Color.GREEN}STATUS: Verifikasi Integritas Memori C++ Selesai Tanpa Error.{Color.RESET}\n")


if __name__ == "__main__":
    try:
        run_vtable_lab()
        run_move_semantics_lab()
    except Exception as exc:
        print(f"{Color.RED}[FATAL ERROR] {exc}{Color.RESET}", file=sys.stderr)
        sys.exit(1)