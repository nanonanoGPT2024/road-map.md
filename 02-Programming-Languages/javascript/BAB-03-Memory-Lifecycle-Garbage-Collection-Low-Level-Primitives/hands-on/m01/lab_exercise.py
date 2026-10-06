#!/usr/bin/env python3
"""
Interactive Simulation: JavaScript Memory Lifecycle, Garbage Collection & Low-Level Primitives
Topic: BAB-03 Memory Lifecycle & Low-Level Primitives
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


def header(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 65}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}  {title}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 65}{Color.RESET}")


def pause(prompt: str = "Tekan [Enter] untuk melanjutkan...") -> None:
    try:
        input(f"\n{Color.GRAY}{prompt}{Color.RESET}")
    except (EOFError, KeyboardInterrupt):
        print()


# ---------------------------------------------------------------------------
# Section 1: Memory Lifecycle (Stack vs Heap)
# ---------------------------------------------------------------------------
@dataclass
class StackFrame:
    fn_name: str
    variables: Dict[str, str] = field(default_factory=dict)


@dataclass
class HeapObject:
    addr: str
    type_name: str
    payload: Dict[str, any]
    ref_count: int = 0
    marked: bool = False
    generation: int = 0  # 0: Young/Nursery, 1: Old Gen


class MemoryManager:
    def __init__(self):
        self.stack: List[StackFrame] = []
        self.heap: Dict[str, HeapObject] = {}
        self._next_id = 0x1000

    def alloc_heap(self, type_name: str, payload: Dict[str, any]) -> str:
        addr = f"0x{self._next_id:X}"
        self._next_id += 0x10
        self.heap[addr] = HeapObject(addr=addr, type_name=type_name, payload=payload)
        return addr

    def push_frame(self, fn_name: str) -> StackFrame:
        frame = StackFrame(fn_name=fn_name)
        self.stack.append(frame)
        return frame

    def pop_frame(self) -> Optional[StackFrame]:
        if self.stack:
            return self.stack.pop()
        return None

    def display(self) -> None:
        print(f"\n{Color.BOLD}[CALL STACK (Execution Context)]{Color.RESET}")
        if not self.stack:
            print(f"  {Color.GRAY}<Stack Kosong>{Color.RESET}")
        else:
            for i, frame in enumerate(reversed(self.stack)):
                idx = len(self.stack) - 1 - i
                vars_str = ", ".join(f"{k}={v}" for k, v in frame.variables.items())
                print(f"  [{idx}] {Color.GREEN}{frame.fn_name}(){Color.RESET} -> {{{vars_str}}}")

        print(f"\n{Color.BOLD}[HEAP MEMORY (Dynamic Objects)]{Color.RESET}")
        if not self.heap:
            print(f"  {Color.GRAY}<Heap Kosong>{Color.RESET}")
        else:
            for addr, obj in self.heap.items():
                mark_flag = f"{Color.GREEN}[MARKED]{Color.RESET}" if obj.marked else f"{Color.GRAY}[UNMARKED]{Color.RESET}"
                gen_flag = f"{Color.YELLOW}Gen-{obj.generation}{Color.RESET}"
                refs = f"{Color.MAGENTA}Refs:{obj.ref_count}{Color.RESET}"
                print(f"  {Color.CYAN}{addr}{Color.RESET} | {gen_flag} | {mark_flag} | {refs} | {obj.type_name}: {obj.payload}")


def demo_stack_heap() -> None:
    header("SIMULASI 1: Stack vs Heap Allocation")
    mm = MemoryManager()

    print(f"{Color.YELLOW}Langkah 1: Script global dieksekusi.{Color.RESET}")
    global_frame = mm.push_frame("global")
    global_frame.variables["primitive_x"] = "42 (Smi 31-bit)"
    mm.display()
    time.sleep(0.5)

    print(f"\n{Color.YELLOW}Langkah 2: Memanggil createUser('Alice'). Objek dialokasikan di Heap.{Color.RESET}")
    fn_frame = mm.push_frame("createUser")
    obj_addr = mm.alloc_heap("Object", {"name": "Alice", "role": "admin"})
    fn_frame.variables["userRef"] = f"*Pointer({obj_addr})"
    mm.heap[obj_addr].ref_count = 1
    mm.display()
    time.sleep(0.5)

    print(f"\n{Color.YELLOW}Langkah 3: createUser() selesai (Stack frame di-pop, pointer hilang!){Color.RESET}")
    mm.pop_frame()
    mm.heap[obj_addr].ref_count = 0  # no direct stack pointer left
    mm.display()
    print(f"{Color.RED}Objek di {obj_addr} sekarang berstatus UNREACHABLE (Orphan/Leak kandidat GC).{Color.RESET}")
    pause()


# ---------------------------------------------------------------------------
# Section 2: Garbage Collection (Reference Counting vs Mark-and-Sweep)
# ---------------------------------------------------------------------------
def demo_garbage_collection() -> None:
    header("SIMULASI 2: Garbage Collection Mechanisms")
    mm = MemoryManager()

    print(f"{Color.BOLD}Skenario: Circular Reference Problem (Kegagalan Reference Counting){Color.RESET}")
    frame = mm.push_frame("setupCycle")
    nodeA = mm.alloc_heap("NodeA", {"id": "A", "next": None})
    nodeB = mm.alloc_heap("NodeB", {"id": "B", "prev": None})

    # Circular link
    mm.heap[nodeA].payload["next"] = nodeB
    mm.heap[nodeB].payload["prev"] = nodeA
    mm.heap[nodeA].ref_count = 2  # dari frame dan dari nodeB
    mm.heap[nodeB].ref_count = 2  # dari frame dan dari nodeA

    frame.variables["a"] = nodeA
    frame.variables["b"] = nodeB
    mm.display()

    print(f"\n{Color.YELLOW}Fungsi setupCycle selesai. Pointer lokal dihapus.{Color.RESET}")
    mm.pop_frame()
    mm.heap[nodeA].ref_count -= 1
    mm.heap[nodeB].ref_count -= 1
    mm.display()

    print(f"{Color.RED}-> Masalah Ref-Counting: Ref count masing-masing tetap 1 (Saling merujuk)!{Color.RESET}")
    print(f"{Color.RED}   Ref Counting GAGAL menghapus objek ini dari RAM.{Color.RESET}")

    pause("Tekan [Enter] untuk menjalankan V8 Mark-and-Sweep...")

    print(f"\n{Color.BOLD}{Color.GREEN}=== Menjalankan V8 Mark-and-Sweep (Reachability Graph) ==={Color.RESET}")
    # Root roots: globals / active stack frames
    roots: Set[str] = set()
    for f in mm.stack:
        for val in f.variables.values():
            if val in mm.heap:
                roots.add(val)

    print(f"1. FASE MARK: Menelusuri GC Roots dari stack... (Roots aktif: {list(roots)})")
    visited = set()
    queue = list(roots)
    while queue:
        curr = queue.pop(0)
        if curr not in visited and curr in mm.heap:
            visited.add(curr)
            mm.heap[curr].marked = True
            for target in mm.heap[curr].payload.values():
                if isinstance(target, str) and target in mm.heap:
                    queue.append(target)

    mm.display()
    print(f"\n2. FASE SWEEP: Membebaskan seluruh objek dengan marked == False...")
    sweep_targets = [addr for addr, obj in mm.heap.items() if not obj.marked]
    for addr in sweep_targets:
        print(f"   {Color.RED}[RECLAIMED]{Color.RESET} Heap memory at {addr} dihapus.")
        del mm.heap[addr]

    # Reset marks
    for obj in mm.heap.values():
        obj.marked = False

    print(f"\n{Color.GREEN}Hasil setelah Mark-and-Sweep:{Color.RESET}")
    mm.display()
    pause()


# ---------------------------------------------------------------------------
# Section 3: Low-Level Primitives (ArrayBuffer, TypedArray, DataView)
# ---------------------------------------------------------------------------
class SimulatedArrayBuffer:
    def __init__(self, byte_length: int):
        self.byte_length = byte_length
        self._raw_memory = bytearray(byte_length)

    def read_byte(self, offset: int) -> int:
        return self._raw_memory[offset]

    def write_byte(self, offset: int, value: int) -> None:
        self._raw_memory[offset] = value & 0xFF

    def inspect_hex(self) -> str:
        return " ".join(f"{b:02X}" for b in self._raw_memory)

    def inspect_bin(self) -> str:
        return " ".join(f"{b:08b}" for b in self._raw_memory)


def demo_low_level_primitives() -> None:
    header("SIMULASI 3: Low-Level Primitives (ArrayBuffer & TypedArrays)")
    print(f"{Color.WHITE}Membuat ArrayBuffer 8-byte mentah di off-heap / contiguous memory.{Color.RESET}")
    buffer = SimulatedArrayBuffer(8)
    print(f"Buffer Byte Length: {buffer.byte_length}")
    print(f"Raw Hex: [{buffer.inspect_hex()}]")

    print(f"\n{Color.YELLOW}Langkah 1: Menulis nilai via Uint8Array View pada offset 0..3{Color.RESET}")
    # Simulasikan menulis string ASCII 'CODE' (0x43, 0x4F, 0x44, 0x45)
    chars = [0x43, 0x4F, 0x44, 0x45]
    for i, val in enumerate(chars):
        buffer.write_byte(i, val)

    print(f"Raw Hex Sekarang: [{Color.GREEN}{buffer.inspect_hex()}{Color.RESET}]")

    print(f"\n{Color.YELLOW}Langkah 2: DataView Endianness Test (Offset 4..7 as 32-bit Integer){Color.RESET}")
    # Nilai 0x12345678
    val = 0x12345678
    # Big Endian (Network Order): 12 34 56 78
    # Little Endian (V8 / x86 Architecture): 78 56 34 12
    print(f"Menulis integer 0x12345678 ke offset 4 dengan Little-Endian (standar CPU x86-64/ARM):")
    buffer.write_byte(4, 0x78)
    buffer.write_byte(5, 0x56)
    buffer.write_byte(6, 0x34)
    buffer.write_byte(7, 0x12)

    print(f"Raw Hex Buffer : [{Color.CYAN}{buffer.inspect_hex()}{Color.RESET}]")
    print(f"Binary Layout  : [{Color.MAGENTA}{buffer.inspect_bin()}{Color.RESET}]")

    print(f"\n{Color.BOLD}Analisis TypedArray Zero-Copy Interpretation:{Color.RESET}")
    print(f" - Byte 0..3 sebagai ASCII        : {''.join(chr(buffer.read_byte(i)) for i in range(4))}")
    print(f" - Byte 4..7 dibaca Little Endian : 0x{buffer.read_byte(7):02X}{buffer.read_byte(6):02X}{buffer.read_byte(5):02X}{buffer.read_byte(4):02X}")
    print(f" - Byte 4..7 dibaca Big Endian    : 0x{buffer.read_byte(4):02X}{buffer.read_byte(5):02X}{buffer.read_byte(6):02X}{buffer.read_byte(7):02X}")
    pause()


# ---------------------------------------------------------------------------
# Section 4: Generational Hypothesis & Scavenger (Young vs Old Generation)
# ---------------------------------------------------------------------------
def demo_generational_gc() -> None:
    header("SIMULASI 4: V8 Generational Hypothesis & Scavenge Cycle")
    print("Prinsip Utama: Sebagian besar objek mati muda (Infant Mortality).")
    print("V8 membagi heap menjadi: Nursery/Semi-spaces (From/To) dan Old Pointer Space.\n")

    nursery: List[HeapObject] = [
        HeapObject("0x2000", "ClosureEnv", {"scopeId": 1}, ref_count=0, generation=0),
        HeapObject("0x2010", "TempString", {"str": "concatenation"}, ref_count=0, generation=0),
        HeapObject("0x2020", "PersistentState", {"appId": "root-store"}, ref_count=1, generation=0),
    ]

    old_generation: List[HeapObject] = []

    print(f"{Color.BOLD}Alokasi Baru di New Space (Nursery):{Color.RESET}")
    for obj in nursery:
        status = f"{Color.GREEN}ALIVE (Ref > 0){Color.RESET}" if obj.ref_count > 0 else f"{Color.RED}DEAD (Ref = 0){Color.RESET}"
        print(f" - {obj.addr}: {obj.type_name} [{status}]")

    pause("Jalankan Cheney's Scavenger Cycle...")

    survivors = []
    for obj in nursery:
        if obj.ref_count > 0:
            obj.generation += 1
            if obj.generation >= 1:
                print(f"  {Color.YELLOW}[PROMOTION]{Color.RESET} Objek {obj.addr} ({obj.type_name}) dipromosikan ke Old Generation.")
                old_generation.append(obj)
            else:
                survivors.append(obj)
        else:
            print(f"  {Color.RED}[EVACUATED/DISCARDED]{Color.RESET} Objek singkat {obj.addr} langsung dibuang tanpa GC pause berat.")

    nursery = survivors
    print(f"\n{Color.BOLD}Status Akhir Setelah Scavenge:{Color.RESET}")
    print(f"New Space / Nursery Count : {len(nursery)}")
    print(f"Old Space Count           : {len(old_generation)} ({[o.addr for o in old_generation]})")
    pause()


# ---------------------------------------------------------------------------
# Main Interactive Loop
# ---------------------------------------------------------------------------
def main():
    while True:
        header("LAB EXERCISE: JS MEMORY LIFECYCLE & LOW-LEVEL PRIMITIVES")
        print(f"{Color.BOLD}Pilih Modul Simulasi:{Color.RESET}")
        print(f"  {Color.CYAN}1.{Color.RESET} Stack vs Heap Allocation (Call Stack & Pointers)")
        print(f"  {Color.CYAN}2.{Color.RESET} Garbage Collection (Ref-Count Failure & Mark-Sweep)")
        print(f"  {Color.CYAN}3.{Color.RESET} Low-Level Primitives (ArrayBuffer, Endianness, Views)")
        print(f"  {Color.CYAN}4.{Color.RESET} V8 Generational Hypothesis & Scavenger Cycle")
        print(f"  {Color.CYAN}5.{Color.RESET} Jalankan Seluruh Rangkaian Simulasi")
        print(f"  {Color.RED}0.{Color.RESET} Keluar")

        try:
            choice = input(f"\n{Color.YELLOW}Masukkan pilihan (0-5): {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            sys.exit(0)

        if choice == "1":
            demo_stack_heap()
        elif choice == "2":
            demo_garbage_collection()
        elif choice == "3":
            demo_low_level_primitives()
        elif choice == "4":
            demo_generational_gc()
        elif choice == "5":
            demo_stack_heap()
            demo_garbage_collection()
            demo_low_level_primitives()
            demo_generational_gc()
        elif choice == "0":
            print(f"\n{Color.GREEN}Lab selesai. Selamat belajar fondasi internal JavaScript!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")
            time.sleep(0.8)


if __name__ == "__main__":
    main()
