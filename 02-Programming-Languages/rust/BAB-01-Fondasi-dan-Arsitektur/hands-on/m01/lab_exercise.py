#!/usr/bin/env python3
"""
Lab Exercise: Rust Core Architecture & Memory Model Simulator
BAB-01: Fondasi dan Arsitektur Rust

Simulasi interaktif konsep inti Rust dalam Python 3:
1. Stack vs Heap Memory Allocation
2. Ownership & Move Semantics
3. Borrow Checker (Aliasing XOR Mutability)
4. RAII & Deterministic Drop Semantics
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class Color:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


class TypeKind(Enum):
    PRIMITIVE_COPY = "Copy (Stack)"
    HEAP_OWNED = "Move (Heap-allocated)"


@dataclass
class HeapBlock:
    address: int
    data: str
    owner: str


@dataclass
class StackVariable:
    name: str
    type_kind: TypeKind
    value_or_ptr: str
    heap_addr: Optional[int] = None
    is_valid: bool = True


class BorrowType(Enum):
    IMMUTABLE = "&T (Shared)"
    MUTABLE = "&mut T (Exclusive)"


@dataclass
class ActiveBorrow:
    borrower_name: str
    target_var: str
    borrow_type: BorrowType
    scope_depth: int


class RustMemorySimulator:
    def __init__(self):
        self.stack: Dict[str, StackVariable] = {}
        self.heap: Dict[int, HeapBlock] = {}
        self.borrows: List[ActiveBorrow] = []
        self.heap_counter = 0x1000
        self.current_scope = 1

    def print_state(self, action_desc: str):
        print(f"\n{Color.CYAN}{'=' * 65}{Color.RESET}")
        print(f"{Color.BOLD}AKSI:{Color.RESET} {Color.YELLOW}{action_desc}{Color.RESET}")
        print(f"{Color.CYAN}{'-' * 65}{Color.RESET}")

        # Stack View
        print(f"{Color.BOLD}[STACK FRAME (Scope {self.current_scope})]{Color.RESET}")
        if not self.stack:
            print(f"  {Color.DIM}(Kosong){Color.RESET}")
        for name, var in self.stack.items():
            status = (
                f"{Color.GREEN}ACTIVE{Color.RESET}"
                if var.is_valid
                else f"{Color.RED}MOVED / INVALID{Color.RESET}"
            )
            heap_info = (
                f" -> Heap @{hex(var.heap_addr)}" if var.heap_addr else ""
            )
            print(
                f"  • {Color.BOLD}{name}{Color.RESET}: [{var.type_kind.value}] val={var.value_or_ptr}{heap_info} [{status}]"
            )

        # Heap View
        print(f"\n{Color.BOLD}[HEAP ALLOCATIONS]{Color.RESET}")
        if not self.heap:
            print(f"  {Color.DIM}(Kosong){Color.RESET}")
        for addr, block in self.heap.items():
            print(
                f"  • {hex(addr)}: \"{block.data}\" (Owner: {Color.GREEN}{block.owner}{Color.RESET})"
            )

        # Active Borrows
        print(f"\n{Color.BOLD}[BORROW CHECKER TABLE]{Color.RESET}")
        if not self.borrows:
            print(f"  {Color.DIM}(Tidak ada active borrow){Color.RESET}")
        for b in self.borrows:
            b_color = (
                Color.BLUE
                if b.borrow_type == BorrowType.IMMUTABLE
                else Color.YELLOW
            )
            print(
                f"  • {b.borrower_name} -> {b.target_var} [{b_color}{b.borrow_type.value}{Color.RESET}] (Scope {b.scope_depth})"
            )
        print(f"{Color.CYAN}{'=' * 65}{Color.RESET}\n")

    def allocate_copy(self, name: str, value: int):
        self.stack[name] = StackVariable(
            name=name, type_kind=TypeKind.PRIMITIVE_COPY, value_or_ptr=str(value)
        )
        self.print_state(f"let {name} = {value}; (Allocated on Stack via Copy)")

    def allocate_heap(self, name: str, data: str):
        addr = self.heap_counter
        self.heap_counter += 0x10
        self.heap[addr] = HeapBlock(address=addr, data=data, owner=name)
        self.stack[name] = StackVariable(
            name=name,
            type_kind=TypeKind.HEAP_OWNED,
            value_or_ptr=f"ptr:{hex(addr)}",
            heap_addr=addr,
            is_valid=True,
        )
        self.print_state(
            f'let {name} = String::from("{data}"); (Heap Buffer Allocated)'
        )

    def move_or_copy(self, src_name: str, dst_name: str):
        if src_name not in self.stack or not self.stack[src_name].is_valid:
            print(
                f"{Color.RED}[RUST COMPILE ERROR]{Color.RESET} use of moved or undeclared value: `{src_name}`"
            )
            return False

        src_var = self.stack[src_name]
        if src_var.type_kind == TypeKind.PRIMITIVE_COPY:
            # Copy Semantics
            self.stack[dst_name] = StackVariable(
                name=dst_name,
                type_kind=TypeKind.PRIMITIVE_COPY,
                value_or_ptr=src_var.value_or_ptr,
                is_valid=True,
            )
            self.print_state(
                f"let {dst_name} = {src_name}; (Copy Semantics: bits diduplikasi di stack)"
            )
            return True
        else:
            # Move Semantics
            addr = src_var.heap_addr
            if addr and addr in self.heap:
                self.heap[addr].owner = dst_name
            self.stack[dst_name] = StackVariable(
                name=dst_name,
                type_kind=TypeKind.HEAP_OWNED,
                value_or_ptr=src_var.value_or_ptr,
                heap_addr=addr,
                is_valid=True,
            )
            src_var.is_valid = False
            self.print_state(
                f"let {dst_name} = {src_name}; (Move Semantics: Ownership ditransfer, `{src_name}` diinvalidation!)"
            )
            return True

    def borrow(self, borrower: str, target: str, borrow_type: BorrowType):
        if target not in self.stack or not self.stack[target].is_valid:
            print(
                f"{Color.RED}[RUST COMPILE ERROR]{Color.RESET} cannot borrow `{target}` as it is moved or uninitialized"
            )
            return False

        # Cek aturan aliasing XOR mutability
        active_for_target = [b for b in self.borrows if b.target_var == target]

        if borrow_type == BorrowType.MUTABLE:
            if active_for_target:
                print(
                    f"{Color.RED}[RUST COMPILE ERROR E0502]{Color.RESET} cannot borrow `{target}` as mutable because it is already borrowed!"
                )
                return False
        else:
            # Immutable borrow request
            has_mut = any(
                b.borrow_type == BorrowType.MUTABLE for b in active_for_target
            )
            if has_mut:
                print(
                    f"{Color.RED}[RUST COMPILE ERROR E0502]{Color.RESET} cannot borrow `{target}` as immutable because it is also borrowed as mutable!"
                )
                return False

        self.borrows.append(
            ActiveBorrow(
                borrower_name=borrower,
                target_var=target,
                borrow_type=borrow_type,
                scope_depth=self.current_scope,
            )
        )
        syntax = (
            f"let {borrower} = &mut {target};"
            if borrow_type == BorrowType.MUTABLE
            else f"let {borrower} = &{target};"
        )
        self.print_state(f"{syntax} (Borrow checker approve: aliasing rules terpenuhi)")
        return True

    def drop_scope(self):
        print(
            f"\n{Color.HEADER}=== Exiting Scope {self.current_scope} -> Menjalankan RAII Drop ==={Color.RESET}"
        )
        # Drop borrows di scope ini
        self.borrows = [
            b for b in self.borrows if b.scope_depth < self.current_scope
        ]

        # Drop stack vars yang merupakan owner heap
        for name, var in list(self.stack.items()):
            if var.is_valid and var.heap_addr and var.heap_addr in self.heap:
                addr = var.heap_addr
                data = self.heap[addr].data
                del self.heap[addr]
                print(
                    f"  {Color.RED}* DROP MEMORY *{Color.RESET} Heap @{hex(addr)} (\"{data}\") dibebaskan otomatis tanpa Garbage Collector!"
                )
            del self.stack[name]

        self.current_scope = max(1, self.current_scope - 1)
        self.print_state("Scope ditutup & Resource di-deallokasi (Zero-Cost RAII)")


def run_demo_1(sim: RustMemorySimulator):
    print(f"\n{Color.BOLD}{Color.GREEN}>>> DEMO 1: MOVE VS COPY SEMANTICS <<<{Color.RESET}")
    sim.allocate_copy("x", 42)
    sim.move_or_copy("x", "y")
    print(
        f"{Color.GREEN}[Info]{Color.RESET} Keduanya `x` dan `y` valid karena tipe integer mengimplementasi Trait `Copy`."
    )
    time.sleep(1)

    sim.allocate_heap("s1", "Hello Rustaceans")
    sim.move_or_copy("s1", "s2")
    print(
        f"{Color.YELLOW}[Percobaan Ilegal]{Color.RESET} Mencoba mengakses `s1` setelah dipindahkan:"
    )
    sim.move_or_copy("s1", "s3")


def run_demo_2(sim: RustMemorySimulator):
    print(
        f"\n{Color.BOLD}{Color.GREEN}>>> DEMO 2: BORROW CHECKER (ALIASING XOR MUTABILITY) <<<{Color.RESET}"
    )
    sim.allocate_heap("data", "Sistem Bersama")
    sim.borrow("r1", "data", BorrowType.IMMUTABLE)
    sim.borrow("r2", "data", BorrowType.IMMUTABLE)
    print(
        f"{Color.GREEN}[Info]{Color.RESET} Memiliki banyak immutable reference (&T) diperbolehkan (Aliasing aman)."
    )
    time.sleep(1)

    print(
        f"\n{Color.YELLOW}[Percobaan Ilegal]{Color.RESET} Mencoba membuat mutable reference saat ada immutable borrow aktif:"
    )
    sim.borrow("r_mut", "data", BorrowType.MUTABLE)


def run_demo_3(sim: RustMemorySimulator):
    print(
        f"\n{Color.BOLD}{Color.GREEN}>>> DEMO 3: DETERMINISTIC DESTRUCTION (RAII) <<<{Color.RESET}"
    )
    sim.current_scope = 2
    sim.allocate_heap("payload", "Koneksi Socket/File Descriptor")
    time.sleep(1)
    sim.drop_scope()


def main():
    print(f"{Color.HEADER}{Color.BOLD}")
    print("=================================================================")
    print("   RUST ARCHITECTURE & MEMORY ENGINE SIMULATOR (BAB-01)          ")
    print("   Memahami Ownership, Borrowing, dan RAII Tanpa Runtime GC     ")
    print("=================================================================")
    print(f"{Color.RESET}")

    sim = RustMemorySimulator()

    while True:
        print(f"\n{Color.BOLD}PILIH SKENARIO LAB:{Color.RESET}")
        print("  1. Simulasi Move vs Copy Semantics")
        print("  2. Simulasi Borrow Checker (Aliasing XOR Mutability)")
        print("  3. Simulasi RAII & Deterministic Drop")
        print("  4. Jalankan Semua Skenario Berurutan (Automated Tour)")
        print("  5. Keluar")

        try:
            choice = input(f"\n{Color.CYAN}Masukkan nomor (1-5): {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            sim = RustMemorySimulator()
            run_demo_1(sim)
        elif choice == "2":
            sim = RustMemorySimulator()
            run_demo_2(sim)
        elif choice == "3":
            sim = RustMemorySimulator()
            run_demo_3(sim)
        elif choice == "4":
            sim = RustMemorySimulator()
            run_demo_1(sim)
            time.sleep(1)
            sim = RustMemorySimulator()
            run_demo_2(sim)
            time.sleep(1)
            sim = RustMemorySimulator()
            run_demo_3(sim)
        elif choice == "5":
            print(f"{Color.GREEN}Terima kasih telah mempelajari arsitektur Rust! Happy Hacking.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 1-5.{Color.RESET}")


if __name__ == "__main__":
    main()
