#!/usr/bin/env python3
"""
Lab Hands-on: Rust Memory Model & Ownership Engine Simulator
Bab 01: Fondasi Bahasa & Sistem Kepemilikan (Ownership & Memory Model) - Modul 02 Deep Dive

Skrip ini memodelkan semantik inti Rust secara deterministik:
1. Ownership & Move Semantics vs Copy Semantics.
2. Borrow Checker: Aturan Aliasing XOR Mutability (&T vs &mut T).
3. RAII (Resource Acquisition Is Initialization) & Automatic Drop Lifecycles.
4. Non-Lexical Lifetimes (NLL) & Pendeteksian Dangling Reference/Use-After-Move.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set
import sys
import time

# --- ANSI Color Utilities ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

def log_info(msg: str) -> None:
    print(f"{Color.CYAN}[INFO]{Color.RESET} {msg}")

def log_success(msg: str) -> None:
    print(f"{Color.GREEN}[PASS]{Color.RESET} {msg}")

def log_warn(msg: str) -> None:
    print(f"{Color.YELLOW}[WARN]{Color.RESET} {msg}")

def log_error(msg: str) -> None:
    print(f"{Color.RED}[BORROW_CHECKER_ERR]{Color.RESET} {msg}")

# --- Data Structures & Types ---

class TraitType(Enum):
    MOVE = auto()  # Tipe heap, memindahkan ownership (misal: String, Vec<T>)
    COPY = auto()  # Tipe bitwise-copy di stack (misal: i32, bool, usize)

class BorrowKind(Enum):
    IMMUTABLE = auto()  # &T (Shared Reference)
    MUTABLE = auto()    # &mut T (Exclusive Reference)

@dataclass
class HeapBlock:
    """Representasi alokasi heap dengan metadata siklus hidup (RAII)."""
    address: int
    data: str
    is_dropped: bool = False

    def drop(self) -> None:
        """Simulasi eksekusi implementasi Drop trait di Rust."""
        if not self.is_dropped:
            self.is_dropped = True
            print(f"    {Color.MAGENTA}↳ [RAII Drop]{Color.RESET} HeapBlock @ 0x{self.address:04X} ('{self.data}') didestruksi dari memori.")

@dataclass
class VariableBinding:
    """Representasi variabel pada Stack Frame."""
    name: str
    trait_type: TraitType
    heap_ptr: Optional[HeapBlock] = None
    stack_val: Optional[int] = None
    is_valid: bool = True  # Menjadi False jika value telah di-MOVE

@dataclass
class ActiveBorrow:
    """Metadata peminjaman aktif untuk Borrow Checker."""
    borrower_name: str
    target_var: str
    kind: BorrowKind
    scope_depth: int

# --- Engine Simulasi Borrow Checker & Memory Rust ---

class RustMemoryEngine:
    def __init__(self):
        self.heap: Dict[int, HeapBlock] = {}
        self.scopes: List[Dict[str, VariableBinding]] = [{}]  # Scope stack
        self.active_borrows: List[ActiveBorrow] = []
        self._next_heap_addr = 0x1000

    @property
    def current_scope(self) -> Dict[str, VariableBinding]:
        return self.scopes[-1]

    def enter_scope(self, scope_name: str = "") -> None:
        """Membuka lexical block baru ({)."""
        self.scopes.append({})
        depth = len(self.scopes) - 1
        print(f"\n{Color.BLUE}--- MEMASUKI SCOPE DEPTH [{depth}] {scope_name} ---{Color.RESET}")

    def exit_scope(self) -> None:
        """Menutup lexical block (}). Memicu otomatis Drop trait pada owner yang out-of-scope."""
        depth = len(self.scopes) - 1
        print(f"\n{Color.BLUE}--- KELUAR DARI SCOPE DEPTH [{depth}] ---{Color.RESET}")
        
        exiting_bindings = self.scopes.pop()
        
        # Bersihkan borrow yang terikat pada scope ini
        self.active_borrows = [b for b in self.active_borrows if b.scope_depth < depth]

        # RAII: Evaluasi variabel yang out of scope
        for var_name, binding in exiting_bindings.items():
            if binding.is_valid and binding.heap_ptr is not None:
                # Pemilik sah melepaskan resource di akhir scope
                binding.heap_ptr.drop()
            elif not binding.is_valid:
                print(f"    {Color.GRAY}↳ [Skip Drop]{Color.RESET} Variabel '{var_name}' dilewati karena status ownership: MOVED.")

    def declare_primitive(self, name: str, value: int) -> None:
        """Deklarasi tipe Copy primitif: let name: i32 = value;"""
        binding = VariableBinding(name=name, trait_type=TraitType.COPY, stack_val=value)
        self.current_scope[name] = binding
        log_info(f"Stack binding dialokasikan: '{name}' (i32) = {value}")

    def allocate_heap(self, name: str, data: str) -> None:
        """Deklarasi tipe Move: let name: String = String::from(data);"""
        addr = self._next_heap_addr
        self._next_heap_addr += 0x10
        block = HeapBlock(address=addr, data=data)
        self.heap[addr] = block
        binding = VariableBinding(name=name, trait_type=TraitType.MOVE, heap_ptr=block)
        self.current_scope[name] = binding
        log_info(f"Heap binding dialokasikan: '{name}' (String) -> 0x{addr:04X} [\"{data}\"]")

    def _resolve_var(self, name: str) -> Optional[VariableBinding]:
        """Cari variable binding dari scope terdalam ke terluar."""
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def read_var(self, name: str) -> Optional[str]:
        """Membaca isi variabel dengan validasi borrow checker."""
        binding = self._resolve_var(name)
        if not binding:
            log_error(f"Cannot find value '{name}' in this scope.")
            return None

        if not binding.is_valid:
            log_error(f"E0382: Use of moved value: '{name}'. Value has been moved previously!")
            return None

        # Periksa apakah ada mutable borrow aktif yang mengunci data
        active_mut = [b for b in self.active_borrows if b.target_var == name and b.kind == BorrowKind.MUTABLE]
        if active_mut:
            borrower = active_mut[0].borrower_name
            log_error(f"E0503: Cannot use '{name}' because it was mutably borrowed by '{borrower}'!")
            return None

        val = f"{binding.stack_val}" if binding.trait_type == TraitType.COPY else f"\"{binding.heap_ptr.data}\""
        log_success(f"Berhasil membaca variabel '{name}' => {val}")
        return val

    def move_or_copy(self, src_name: str, dest_name: str) -> None:
        """Simulasi: let dest_name = src_name;"""
        src = self._resolve_var(src_name)
        if not src:
            log_error(f"E0425: Cannot find value '{src_name}' in this scope.")
            return

        if not src.is_valid:
            log_error(f"E0382: Use of moved value: '{src_name}'. Cannot transfer ownership!")
            return

        # Cek apakah variabel sedang dipinjam
        if any(b.target_var == src_name for b in self.active_borrows):
            log_error(f"E0505: Cannot move out of '{src_name}' because it is currently borrowed!")
            return

        if src.trait_type == TraitType.COPY:
            # Trait Copy: Bitwise duplicate stack memory
            new_binding = VariableBinding(name=dest_name, trait_type=TraitType.COPY, stack_val=src.stack_val)
            self.current_scope[dest_name] = new_binding
            log_info(f"Copy Semantics: '{src_name}' disalin ke '{dest_name}'. Keduanya tetap valid.")
        else:
            # Trait Move: Ownership berpindah, source invalid
            new_binding = VariableBinding(name=dest_name, trait_type=TraitType.MOVE, heap_ptr=src.heap_ptr)
            self.current_scope[dest_name] = new_binding
            src.is_valid = False
            log_info(f"Move Semantics: Ownership pointer 0x{src.heap_ptr.address:04X} dipindahkan dari '{src_name}' -> '{dest_name}'. '{src_name}' invalid!")

    def borrow(self, borrower: str, target: str, kind: BorrowKind) -> bool:
        """
        Simulasi pinjaman:
        let borrower = &target;      (IMMUTABLE)
        let borrower = &mut target;  (MUTABLE)
        """
        target_var = self._resolve_var(target)
        if not target_var or not target_var.is_valid:
            log_error(f"Cannot borrow invalid/moved value '{target}'.")
            return False

        current_borrows = [b for b in self.active_borrows if b.target_var == target]

        if kind == BorrowKind.MUTABLE:
            # Aturan: Hanya boleh 1 mut borrow, dan 0 immut borrow
            if len(current_borrows) > 0:
                owners = ", ".join([f"'{b.borrower_name}' ({b.kind.name})" for b in current_borrows])
                log_error(f"E0499/E0502: Cannot borrow '{target}' as mutable more than once at a time. Aktif dipinjam oleh: {owners}")
                return False
        else:
            # Aturan: Immut borrow diizinkan banyak, asalkan TIDAK ADA mut borrow
            mut_borrows = [b for b in current_borrows if b.kind == BorrowKind.MUTABLE]
            if mut_borrows:
                log_error(f"E0502: Cannot borrow '{target}' as immutable because it is also borrowed as mutable by '{mut_borrows[0].borrower_name}'.")
                return False

        depth = len(self.scopes) - 1
        borrow = ActiveBorrow(borrower_name=borrower, target_var=target, kind=kind, scope_depth=depth)
        self.active_borrows.append(borrow)
        sym = "&mut" if kind == BorrowKind.MUTABLE else "&"
        log_success(f"BorrowChecker lolos: let {borrower} = {sym}{target}; terdaftar pada scope [{depth}].")
        return True

    def release_borrow(self, borrower: str) -> None:
        """Simulasi Non-Lexical Lifetimes (NLL): pelepasan pinjaman setelah titik akhir penggunaan."""
        initial_len = len(self.active_borrows)
        self.active_borrows = [b for b in self.active_borrows if b.borrower_name != borrower]
        if len(self.active_borrows) < initial_len:
            print(f"    {Color.GRAY}↳ [NLL Released]{Color.RESET} Reference '{borrower}' out-of-life/dilepas.")

# --- Skrip Demonstrasi Interaktif Hands-on Lab ---

def run_lab():
    print(f"{Color.BOLD}======================================================================{Color.RESET}")
    print(f"{Color.BOLD}   LAB ENGINE: SISTEM KEPEMILIKAN (OWNERSHIP) & MEMORY MODEL RUST   {Color.RESET}")
    print(f"{Color.BOLD}======================================================================{Color.RESET}\n")

    engine = RustMemoryEngine()

    print(f"{Color.YELLOW}[EKSPERIMEN 1] Move Semantics vs Use-After-Move (String / Heap Type){Color.RESET}")
    engine.allocate_heap("s1", "Distributed Systems Engine")
    engine.read_var("s1")
    print("\nEksekusi: let s2 = s1; (Transfer ownership)")
    engine.move_or_copy("s1", "s2")
    
    print("\nPercobaan membaca s1 setelah di-move (Ekspektasi: E0382):")
    engine.read_var("s1")
    
    print("\nMembaca pemilik baru (s2):")
    engine.read_var("s2")

    print(f"\n{Color.YELLOW}[EKSPERIMEN 2] Copy Semantics pada Primitif (Stack Only Types){Color.RESET}")
    engine.declare_primitive("x", 42)
    print("\nEksekusi: let y = x; (Stack bitwise copy)")
    engine.move_or_copy("x", "y")
    print("\nMembaca x dan y (Ekspektasi: Dua-duanya valid):")
    engine.read_var("x")
    engine.read_var("y")

    print(f"\n{Color.YELLOW}[EKSPERIMEN 3] Borrow Checker: Aturan Aliasing XOR Mutability (& vs &mut){Color.RESET}")
    engine.allocate_heap("buffer", "TCP Packet Payload")
    
    print("\nKasus 3.1: Multiple Immutable Borrows (&buffer)")
    engine.borrow("ref1", "buffer", BorrowKind.IMMUTABLE)
    engine.borrow("ref2", "buffer", BorrowKind.IMMUTABLE)
    engine.read_var("buffer")

    print("\nKasus 3.2: Mencoba Mutable Borrow saat Shared Borrow aktif (Ekspektasi: E0502)")
    engine.borrow("mut_ref", "buffer", BorrowKind.MUTABLE)

    print("\nKasus 3.3: Mensimulasikan NLL (Non-Lexical Lifetimes) - release ref1 & ref2")
    engine.release_borrow("ref1")
    engine.release_borrow("ref2")
    
    print("\nKasus 3.4: Re-attempt Mutable Borrow setelah pelepasan")
    engine.borrow("mut_ref", "buffer", BorrowKind.MUTABLE)
    print("\nMencoba membaca variabel buffer langsung saat mutably borrowed (Ekspektasi: E0503):")
    engine.read_var("buffer")
    
    engine.release_borrow("mut_ref")

    print(f"\n{Color.YELLOW}[EKSPERIMEN 4] RAII & Deterministic Destruction via Scope Boundaries{Color.RESET}")
    engine.enter_scope("Worker_Thread_Block")
    engine.allocate_heap("thread_local_cache", "Redis Shard Mapping")
    engine.allocate_heap("temp_socket", "Raw FD 12")
    
    print("\nMemindahkan 'temp_socket' keluar dari sub-scope ke scope luar...")
    # Daftarkan penampung di scope luar dahulu
    engine.scopes[0]["persistent_socket"] = None
    engine.move_or_copy("temp_socket", "persistent_socket")

    print("\nMenutup sub-scope Worker_Thread_Block...")
    engine.exit_scope()

    print("\nEvaluasi di Scope Utama:")
    engine.read_var("persistent_socket")

    print(f"\n{Color.YELLOW}[EKSPERIMEN 5] Membersihkan Scope Utama (Global Teardown){Color.RESET}")
    engine.exit_scope()

    print(f"\n{Color.GREEN}{Color.BOLD}Semua simulasi siklus memori dan aturan Borrow Checker selesai dengan akurat.{Color.RESET}")

if __name__ == "__main__":
    run_lab()