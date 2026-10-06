#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Rust Lifetimes Lanjut & Smart Pointers
Topik: BAB-03-Lifetimes-Lanjut-Smart-Pointers
Bahasa Simulasi: Python 3 (Standalone Runnable)

Modul ini mengemulasikan mekanisme inti rust:
1. Lifetime Borrow Checker & Scope Tracking (Pencegahan Dangling Reference)
2. Box<T> (Single Unique Heap Ownership & Deterministic RAII Drop)
3. Rc<T> / Arc<T> (Reference Counting, Strong/Weak Counts, Thread-Safety Marker)
4. RefCell<T> (Interior Mutability & Dynamic Runtime Borrow Checking)
"""

import sys
import time
from typing import Any, Dict, List, Optional


class AnsiColor:
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


def header(text: str) -> None:
    print(f"\n{AnsiColor.BOLD}{AnsiColor.CYAN}{'=' * 65}{AnsiColor.RESET}")
    print(f"{AnsiColor.BOLD}{AnsiColor.WHITE} [SIMULASI] {text}{AnsiColor.RESET}")
    print(f"{AnsiColor.BOLD}{AnsiColor.CYAN}{'=' * 65}{AnsiColor.RESET}")


def log_step(component: str, msg: str, status: str = "INFO") -> None:
    palette = {
        "INFO": AnsiColor.BLUE,
        "OK": AnsiColor.GREEN,
        "WARN": AnsiColor.YELLOW,
        "DROP": AnsiColor.MAGENTA,
        "PANIC": AnsiColor.RED,
    }
    color = palette.get(status, AnsiColor.WHITE)
    print(f" {color}[{status:<5}]{AnsiColor.RESET} {AnsiColor.BOLD}{component:<12}{AnsiColor.RESET} | {msg}")


# ============================================================================
# 1. EMULASI LIFETIME & BORROW CHECKER
# ============================================================================
class LifetimeScope:
    def __init__(self, name: str, parent: Optional["LifetimeScope"] = None):
        self.name = name
        self.parent = parent
        self.alive = True
        self.active_borrows: List[str] = []

    def borrow_resource(self, resource_name: str, target_lifetime: "LifetimeScope") -> bool:
        if not self.alive:
            log_step("BorrowChecker", f"Gagal meminjam '{resource_name}': Scope '{self.name}' sudah mati!", "PANIC")
            return False
        if not target_lifetime.alive:
            log_step("BorrowChecker", f"E0597: '{resource_name}' does not live long enough!", "PANIC")
            return False

        # In Rust, referent (target_lifetime) harus hidup minimal selama referensi (self)
        # Artinya target_lifetime harus ancestor dari self atau sama dengan self (T: 'a)
        curr = self
        target_outlives_self = False
        while curr is not None:
            if curr == target_lifetime:
                target_outlives_self = True
                break
            curr = curr.parent

        if not target_outlives_self:
            log_step(
                "BorrowChecker",
                f"E0597: '{resource_name}' does not live long enough! Scope target '{target_lifetime.name}' berumur lebih pendek dari peminjam '{self.name}'.",
                "PANIC",
            )
            return False

        self.active_borrows.append(f"{resource_name} (borrowed from {target_lifetime.name})")
        log_step("BorrowChecker", f"Borrow valid: '{resource_name}' di-pinjam dalam scope '{self.name}'.", "OK")
        return True

    def drop(self) -> None:
        self.alive = False
        log_step("BorrowChecker", f"Scope '{self.name}' berakhir! Semua referensi lokal dihapus.", "DROP")
        self.active_borrows.clear()


# ============================================================================
# 2. EMULASI Box<T> (Heap Allocation & RAII Drop)
# ============================================================================
class BoxPointer:
    _heap_counter = 1000

    def __init__(self, value: Any):
        BoxPointer._heap_counter += 4
        self.heap_address = hex(BoxPointer._heap_counter)
        self.value = value
        self.valid = True
        log_step("Box<T>", f"Alokasi Heap {self.heap_address} -> Nilai: {self.value}", "OK")

    def move_to(self, new_owner_name: str) -> "BoxPointer":
        if not self.valid:
            log_step("Box<T>", f"Use of moved value at {self.heap_address}!", "PANIC")
            raise RuntimeError("Borrow Checker Violation: Use of moved value")

        self.valid = False
        log_step("Box<T>", f"Ownership {self.heap_address} berpindah (Moved) ke '{new_owner_name}'. Pointer lama hangus.", "WARN")
        new_box = BoxPointer.__new__(BoxPointer)
        new_box.heap_address = self.heap_address
        new_box.value = self.value
        new_box.valid = True
        return new_box

    def drop(self) -> None:
        if self.valid:
            log_step("Box<T>", f"RAII Drop: Memori heap {self.heap_address} dibebaskan (free).", "DROP")
            self.valid = False
        else:
            log_step("Box<T>", f"Skip drop: Nilai pada {self.heap_address} sudah pernah dimove.", "INFO")


# ============================================================================
# 3. EMULASI Rc<T> / Arc<T> (Reference Counting)
# ============================================================================
class RcSharedPayload:
    def __init__(self, value: Any, is_atomic: bool = False):
        self.value = value
        self.strong_count = 1
        self.weak_count = 0
        self.is_atomic = is_atomic
        self.address = hex(id(self))


class RcPointer:
    def __init__(self, value: Any = None, _payload: Optional[RcSharedPayload] = None, is_atomic: bool = False):
        if _payload is not None:
            self._inner = _payload
        else:
            self._inner = RcSharedPayload(value, is_atomic=is_atomic)
            t_name = "Arc<T>" if is_atomic else "Rc<T>"
            log_step(t_name, f"Instansiasi baru di {self._inner.address} | Strong Count: {self._inner.strong_count}", "OK")

    def clone(self) -> "RcPointer":
        self._inner.strong_count += 1
        t_name = "Arc<T>" if self._inner.is_atomic else "Rc<T>"
        log_step(t_name, f"Clone dipanggil! Alamat: {self._inner.address} | Strong Count naik: {self._inner.strong_count}", "OK")
        return RcPointer(_payload=self._inner)

    def get_value(self) -> Any:
        return self._inner.value

    def strong_count(self) -> int:
        return self._inner.strong_count

    def drop(self) -> None:
        t_name = "Arc<T>" if self._inner.is_atomic else "Rc<T>"
        self._inner.strong_count -= 1
        if self._inner.strong_count > 0:
            log_step(t_name, f"Drop instance. Strong count tersisa: {self._inner.strong_count}", "INFO")
        else:
            log_step(t_name, f"Strong count mencapai 0! Heap payload di {self._inner.address} dideallokasi.", "DROP")


# ============================================================================
# 4. EMULASI RefCell<T> (Dynamic Borrow Checking & Interior Mutability)
# ============================================================================
class RefCellBorrow:
    def __init__(self, cell: "RefCell", is_mut: bool):
        self.cell = cell
        self.is_mut = is_mut
        self.active = True

    def release(self) -> None:
        if self.active:
            self.cell._release_borrow(self.is_mut)
            self.active = False


class RefCell:
    def __init__(self, initial_value: Any):
        self._value = initial_value
        self._borrow_count = 0  # > 0 for immutable borrows, -1 for mutable borrow
        log_step("RefCell<T>", f"Dibuat dengan nilai awal: {self._value} (Borrow state: Clean)", "OK")

    def borrow(self) -> RefCellBorrow:
        if self._borrow_count < 0:
            log_step("RefCell<T>", "AlreadyMutablyBorrowed: Tidak bisa borrow() saat borrow_mut() aktif!", "PANIC")
            raise RuntimeError("BorrowMutError: AlreadyMutablyBorrowed")
        self._borrow_count += 1
        log_step("RefCell<T>", f"borrow() sukses. Active immutable borrows: {self._borrow_count}", "INFO")
        return RefCellBorrow(self, is_mut=False)

    def borrow_mut(self) -> RefCellBorrow:
        if self._borrow_count != 0:
            status = "AlreadyBorrowed" if self._borrow_count > 0 else "AlreadyMutablyBorrowed"
            log_step("RefCell<T>", f"{status}: Tidak bisa borrow_mut() saat ada peminjam lain!", "PANIC")
            raise RuntimeError(f"BorrowError: {status}")
        self._borrow_count = -1
        log_step("RefCell<T>", "borrow_mut() sukses! Exclusive mutable lease diberikan.", "WARN")
        return RefCellBorrow(self, is_mut=True)

    def _release_borrow(self, is_mut: bool) -> None:
        if is_mut:
            self._borrow_count = 0
            log_step("RefCell<T>", "Exclusive mutable borrow dikembalikan.", "INFO")
        else:
            self._borrow_count -= 1
            log_step("RefCell<T>", f"Immutable borrow dikembalikan. Sisa: {self._borrow_count}", "INFO")

    def set_value(self, new_val: Any) -> None:
        if self._borrow_count != -1:
            log_step("RefCell<T>", "Mutasi nilai ditolak! Harus memiliki borrow_mut() aktif.", "PANIC")
            raise RuntimeError("Mutasi tanpa lease mutable eksklusif")
        self._value = new_val
        log_step("RefCell<T>", f"Interior Mutability: Nilai diubah menjadi -> {self._value}", "OK")

    def get_value(self) -> Any:
        return self._value


# ============================================================================
# DEMO FLOW & INTERAKTIF MENU
# ============================================================================
def demo_lifetimes():
    header("DEMO 1: Lifetimes & Borrow Checker (Pencegahan Dangling Ref)")
    print(f"{AnsiColor.DIM}Skenario: Mencoba membuat referensi dari inner scope yang bocor ke outer scope.{AnsiColor.RESET}\n")

    outer_scope = LifetimeScope(name="'outer")
    inner_scope = LifetimeScope(name="'inner", parent=outer_scope)

    # Valid borrow
    outer_scope.borrow_resource("ConfigData", outer_scope)

    # Invalid borrow attempt: outer referensi menunjuk resource di inner scope
    print(f"\n{AnsiColor.YELLOW}Simulasi E0597: Referensi outer mencoba meminjam nilai inner...{AnsiColor.RESET}")
    outer_scope.borrow_resource("TempSecretKey", inner_scope)

    # Drop inner
    inner_scope.drop()

    # Drop outer
    outer_scope.drop()


def demo_box():
    header("DEMO 2: Box<T> (Unique Ownership & Move Semantics)")
    print(f"{AnsiColor.DIM}Skenario: Alokasi heap unik, pemindahan kepemilikan (move), dan proteksi double-free.{AnsiColor.RESET}\n")

    b1 = BoxPointer({"user_id": 42, "role": "admin"})
    print(f"Data di b1: {b1.value}")

    print(f"\n{AnsiColor.YELLOW}Memindahkan kepemilikan b1 -> b2...{AnsiColor.RESET}")
    b2 = b1.move_to("b2")

    print(f"\n{AnsiColor.YELLOW}Mencoba membaca b1 setelah dipindahkan (Move):{AnsiColor.RESET}")
    try:
        b1.move_to("b3")
    except RuntimeError as e:
        print(f" {AnsiColor.RED}>> Tangkapan Error: {e}{AnsiColor.RESET}")

    print(f"\n{AnsiColor.YELLOW}Membersihkan b1 dan b2 saat keluar scope:{AnsiColor.RESET}")
    b1.drop()
    b2.drop()


def demo_rc_arc():
    header("DEMO 3: Rc<T> / Arc<T> (Multiple Ownership melalui Reference Counting)")
    print(f"{AnsiColor.DIM}Skenario: Shared ownership node graf/tree dengan visualisasi penurunan count.{AnsiColor.RESET}\n")

    print(f"{AnsiColor.CYAN}--- Rc<T> (Single-Threaded Reference Counting) ---{AnsiColor.RESET}")
    node = RcPointer("Node A (Config Database)")
    branch1 = node.clone()
    branch2 = node.clone()

    print(f"Status: Total pemilik bersama = {node.strong_count()}")

    print(f"\n{AnsiColor.YELLOW}Menghapus kepemilikan satu per satu:{AnsiColor.RESET}")
    branch1.drop()
    branch2.drop()
    node.drop()


def demo_refcell():
    header("DEMO 4: RefCell<T> (Interior Mutability & Dynamic Panic)")
    print(f"{AnsiColor.DIM}Skenario: Memodifikasi data di balik referensi immutable dan deteksi runtime borrow panic.{AnsiColor.RESET}\n")

    cell = RefCell(100)

    # Pinjam immutably dua kali (valid di Rust)
    b1 = cell.borrow()
    b2 = cell.borrow()

    # Mencoba pinjam mutably saat masih ada immutable borrows
    print(f"\n{AnsiColor.YELLOW}Mencoba borrow_mut() saat 2 immutable lease aktif (Harus Panic):{AnsiColor.RESET}")
    try:
        cell.borrow_mut()
    except RuntimeError as e:
        print(f" {AnsiColor.RED}>> Runtime Panic Terdeteksi: {e}{AnsiColor.RESET}")

    # Kembalikan pinjaman
    b1.release()
    b2.release()

    # Sekarang pinjam mutably
    print(f"\n{AnsiColor.GREEN}Meminjam mutably setelah semua lease immutable dilepas:{AnsiColor.RESET}")
    b_mut = cell.borrow_mut()
    cell.set_value(250)
    b_mut.release()

    print(f"Nilai akhir dalam cell: {cell.get_value()}")


def run_all_benchmarks():
    demo_lifetimes()
    time.sleep(0.3)
    demo_box()
    time.sleep(0.3)
    demo_rc_arc()
    time.sleep(0.3)
    demo_refcell()
    print(f"\n{AnsiColor.BOLD}{AnsiColor.GREEN}✓ Semua simulasi Rust Memory Management selesai dijalankan tanpa crash tak tertangani!{AnsiColor.RESET}\n")


def print_menu():
    print(f"\n{AnsiColor.BOLD}{AnsiColor.WHITE}=== Rust Lifetimes & Smart Pointers Terminal Lab ==={AnsiColor.RESET}")
    print(f" {AnsiColor.CYAN}1.{AnsiColor.RESET} Simulasi Lifetime Scope & Borrow Checker (E0597)")
    print(f" {AnsiColor.CYAN}2.{AnsiColor.RESET} Simulasi Box<T> (Heap Ownership & Move Semantics)")
    print(f" {AnsiColor.CYAN}3.{AnsiColor.RESET} Simulasi Rc<T> / Arc<T> (Shared Ownership & Strong Counts)")
    print(f" {AnsiColor.CYAN}4.{AnsiColor.RESET} Simulasi RefCell<T> (Interior Mutability & Panic)")
    print(f" {AnsiColor.CYAN}5.{AnsiColor.RESET} Jalankan Seluruh Simulasi Otomatis")
    print(f" {AnsiColor.RED}0.{AnsiColor.RESET} Keluar")
    print(f"{AnsiColor.DIM}{'-' * 52}{AnsiColor.RESET}")


def main():
    # Jika dipanggil dengan argumen non-interaktif seperti 'all' atau 'test'
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("all", "test", "--auto"):
        run_all_benchmarks()
        return

    while True:
        print_menu()
        try:
            choice = input(f"{AnsiColor.BOLD}Pilih opsi [0-5]: {AnsiColor.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar...")
            break

        if choice == "1":
            demo_lifetimes()
        elif choice == "2":
            demo_box()
        elif choice == "3":
            demo_rc_arc()
        elif choice == "4":
            demo_refcell()
        elif choice == "5":
            run_all_benchmarks()
        elif choice == "0":
            print(f"{AnsiColor.GREEN}Terima kasih telah menjalankan simulasi Rust Smart Pointers.{AnsiColor.RESET}")
            break
        else:
            print(f"{AnsiColor.RED}Pilihan tidak valid, silakan coba lagi.{AnsiColor.RESET}")


if __name__ == "__main__":
    main()
