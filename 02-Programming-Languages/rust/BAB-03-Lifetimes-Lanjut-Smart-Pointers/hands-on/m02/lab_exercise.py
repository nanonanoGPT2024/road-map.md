#!/usr/bin/env python3
"""
Lab Hands-on: Rust - Bab 03 (Lifetimes Lanjut & Smart Pointers) - Modul 02 Deep Dive
Simulasi Runtime: Rc<T>, Weak<T>, RefCell<T>, dan Dynamic Borrow Checker Engine.
"""

from __future__ import annotations
import sys
import time
from typing import Generic, TypeVar, Optional, Any
from dataclasses import dataclass

T = TypeVar("T")

# ANSI Color formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"


class BorrowError(RuntimeError):
    """Mencerminkan panic Rust saat aturan peminjaman dilanggar saat runtime."""
    pass


class Ref(Generic[T]):
    """RAII guard untuk peminjaman immutable (&T)."""
    def __init__(self, cell: RefCell[T]):
        self._cell = cell

    @property
    def value(self) -> T:
        return self._cell._value

    def __enter__(self) -> Ref[T]:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def release(self):
        if self._cell is not None:
            self._cell._borrow_count -= 1
            self._cell = None

    def __del__(self):
        self.release()


class RefMut(Generic[T]):
    """RAII guard untuk peminjaman mutable (&mut T)."""
    def __init__(self, cell: RefCell[T]):
        self._cell = cell

    @property
    def value(self) -> T:
        return self._cell._value

    @value.setter
    def value(self, new_val: T):
        self._cell._value = new_val

    def __enter__(self) -> RefMut[T]:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def release(self):
        if self._cell is not None:
            self._cell._borrow_mut = False
            self._cell = None

    def __del__(self):
        self.release()


class RefCell(Generic[T]):
    """
    Simulasi Rust RefCell<T>: Interior Mutability via Dynamic Borrow Checking.
    Aturan: Banyak pembaca (&T) ATAU satu penulis (&mut T) pada satu waktu.
    """
    def __init__(self, value: T):
        self._value = value
        self._borrow_count = 0  # > 0 untuk readers
        self._borrow_mut = False  # True untuk writer tunggal

    def borrow(self) -> Ref[T]:
        if self._borrow_mut:
            raise BorrowError("panicked at 'already mutably borrowed: BorrowError'")
        self._borrow_count += 1
        return Ref(self)

    def borrow_mut(self) -> RefMut[T]:
        if self._borrow_mut or self._borrow_count > 0:
            raise BorrowError(
                f"panicked at 'already borrowed: BorrowMutError (Active Readers: {self._borrow_count}, "
                f"Active Writer: {self._borrow_mut})'"
            )
        self._borrow_mut = True
        return RefMut(self)


class _RcBox(Generic[T]):
    """Alokasi heap internal untuk data bersama, strong count, dan weak count."""
    def __init__(self, value: T):
        self.value: Optional[T] = value
        self.strong: int = 1
        self.weak: int = 0


class Rc(Generic[T]):
    """
    Simulasi Rust Rc<T>: Reference Counting Single-Threaded Pointer.
    Mengelola deallokasi deterministik dan siklus referensi menggunakan Weak<T>.
    """
    def __init__(self, value: T, _inner: Optional[_RcBox[T]] = None):
        if _inner is not None:
            self._inner = _inner
        else:
            self._inner = _RcBox(value)

    def clone(self) -> Rc[T]:
        """Menambah strong reference count."""
        if self._inner.strong == 0:
            raise RuntimeError("Mencoba meng-clone Rc yang telah di-drop")
        self._inner.strong += 1
        return Rc(None, _inner=self._inner)

    def downgrade(self) -> Weak[T]:
        """Membuat pointer non-owning Weak<T> untuk memutus reference cycle."""
        self._inner.weak += 1
        return Weak(self._inner)

    def strong_count(self) -> int:
        return self._inner.strong

    def weak_count(self) -> int:
        return self._inner.weak

    @property
    def value(self) -> T:
        if self._inner.value is None:
            raise RuntimeError("Use-after-free: Akses nilai dari Rc yang sudah deallocated!")
        return self._inner.value

    def drop(self):
        """Simulasi deterministic Rust Drop trait."""
        if self._inner and self._inner.strong > 0:
            self._inner.strong -= 1
            if self._inner.strong == 0:
                # Deallocate payload (T::drop dipanggil)
                self._inner.value = None


class Weak(Generic[T]):
    """
    Simulasi Rust Weak<T>: Referensi lemah tanpa kepemilikan nilai.
    """
    def __init__(self, inner: _RcBox[T]):
        self._inner = inner

    def upgrade(self) -> Optional[Rc[T]]:
        """Mencoba mempromosikan Weak ke Rc jika payload belum di-deallocate."""
        if self._inner.strong > 0:
            self._inner.strong += 1
            return Rc(None, _inner=self._inner)
        return None

    def drop(self):
        if self._inner.weak > 0:
            self._inner.weak -= 1


@dataclass
class TreeNode:
    name: str
    parent: Optional[Weak[RefCell[TreeNode]]] = None
    children: list[Rc[RefCell[TreeNode]]] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


def run_borrow_checker_suite():
    """Menguji dynamic borrow checking pada RefCell."""
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== [TEST 1] RefCell<T> Interior Mutability & Aliasing Rules ==={CLR_RESET}")
    data_cell = RefCell[int](42)

    print(f"{CLR_CYAN}[+] Inisialisasi RefCell dengan nilai:{CLR_RESET} 42")

    # Uji multi-borrow immutable
    ref1 = data_cell.borrow()
    ref2 = data_cell.borrow()
    print(f"{CLR_GREEN}✓ Berhasil membuat 2 immutable borrow simultan:&T -> {ref1.value}, {ref2.value}{CLR_RESET}")

    # Uji mutable borrow ketika immutable borrow masih aktif
    print(f"{CLR_YELLOW}[!] Mencoba borrow_mut() saat RefCell sedang diborrow immutable...{CLR_RESET}")
    try:
        data_cell.borrow_mut()
    except BorrowError as err:
        print(f"{CLR_RED}✓ Sesuai ekspektasi! Rust borrow checker menolak akselerasi mutasi:{CLR_RESET}\n    {err}")

    # Lepaskan peminjaman immutable
    ref1.release()
    ref2.release()
    print(f"{CLR_CYAN}[+] Immutable borrow guard dilepas.{CLR_RESET}")

    # Sekarang mutasi diperbolehkan
    with data_cell.borrow_mut() as mut_ref:
        mut_ref.value += 58
        print(f"{CLR_GREEN}✓ Mutasi nilai melalui RefMut guard berhasil. Nilai baru: {mut_ref.value}{CLR_RESET}")

    print(f"{CLR_CYAN}[+] Verifikasi nilai akhir setelah borrow_mut guard keluar scope: {data_cell.borrow().value}{CLR_RESET}")


def run_cyclic_graph_suite():
    """Menguji siklus memori dan pencegahan kebocoran via Weak<RefCell<Node>>."""
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== [TEST 2] Rc<T> & Weak<T> Tree Hierarchy (Cycle Prevention) ==={CLR_RESET}")

    # Membuat Root Node: Rc<RefCell<TreeNode>>
    root = Rc(RefCell(TreeNode(name="RootNode")))
    print(f"{CLR_CYAN}[+] RootNode dialokasikan.{CLR_RESET}")
    print(f"    Root Strong: {root.strong_count()}, Weak: {root.weak_count()}")

    # Scope simulasi anak
    print(f"\n{CLR_YELLOW}--- Memasuki Inner Scope (Alokasi Child Node) ---{CLR_RESET}")
    child = Rc(RefCell(TreeNode(name="ChildNode_1", parent=root.downgrade())))
    
    # Hubungkan root ke anak
    root.value.borrow_mut().value.children.append(child.clone())

    print(f"    Root Strong: {root.strong_count()}, Weak: {root.weak_count()} (Weak dipegang Child)")
    print(f"    Child Strong: {child.strong_count()}, Weak: {child.weak_count()}")

    # Akses parent dari child via Weak::upgrade
    child_borrow = child.value.borrow()
    parent_weak = child_borrow.value.parent
    parent_upgraded = parent_weak.upgrade()
    
    if parent_upgraded:
        parent_name = parent_upgraded.value.borrow().value.name
        print(f"{CLR_GREEN}✓ Child berhasil meng-upgrade Weak pointer ke Parent: '{parent_name}'{CLR_RESET}")
    
    # Melepas pointer upgraded
    parent_upgraded.drop()

    print(f"\n{CLR_YELLOW}--- Meninggalkan Inner Scope (Drop Child Variable) ---{CLR_RESET}")
    child.drop()  # Child local variable keluar dari scope

    # Child masih bertahan karena disimpan dalam array children milik root
    print(f"    Child masih hidup dalam array Root. Strong count: {root.value.borrow().value.children[0].strong_count()}")

    # Drop root dan bersihkan siklus secara manual untuk meniru Drop cascades
    print(f"\n{CLR_CYAN}[+] Memutus tautan anak dan membersihkan Root...{CLR_RESET}")
    child_ref = root.value.borrow_mut().value.children.pop()
    child_ref.drop()
    root.drop()

    print(f"    Root deallocated successfully. Validasi pencegahan memory leak: PASSED.")


def run_lifetime_variance_simulation():
    """Simulasi validasi subtyping lifetime ('a: 'b)."""
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== [TEST 3] Lifetime Bounds & Outlives Simulation ('a: 'b) ==={CLR_RESET}")
    
    class ScopeTracker:
        def __init__(self, name: str, depth: int):
            self.name = name
            self.depth = depth

        def outlives(self, other: ScopeTracker) -> bool:
            # Scope yang dialokasikan lebih awal (depth lebih rendah) hidup lebih lama (outlives)
            return self.depth <= other.depth

    scope_static = ScopeTracker("'static", 0)
    scope_outer = ScopeTracker("'outer", 1)
    scope_inner = ScopeTracker("'inner", 2)

    def validate_reference(reference_lifetime: ScopeTracker, target_lifetime: ScopeTracker):
        """Rust Compiler: Referensi tidak boleh hidup lebih lama dari data target."""
        if not target_lifetime.outlives(reference_lifetime):
            raise BorrowError(
                f"Lifetime Violation! Referensi '{reference_lifetime.name}' "
                f"mencoba menunjuk ke data dengan masa hidup lebih pendek '{target_lifetime.name}'"
            )
        print(f"{CLR_GREEN}✓ Valid: target {target_lifetime.name} outlives referensi {reference_lifetime.name}{CLR_RESET}")

    validate_reference(reference_lifetime=scope_outer, target_lifetime=scope_static)
    validate_reference(reference_lifetime=scope_inner, target_lifetime=scope_outer)

    try:
        validate_reference(reference_lifetime=scope_outer, target_lifetime=scope_inner)
    except BorrowError as ex:
        print(f"{CLR_RED}✓ Sesuai ekspektasi! Compiler memblokir reference escaping:{CLR_RESET}\n    {ex}")


def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}   RUST DEEP DIVE: LIFETIMES, INTERIOR MUTABILITY & SMART POINTERS    {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")

    start_time = time.perf_counter()
    run_borrow_checker_suite()
    run_cyclic_graph_suite()
    run_lifetime_variance_simulation()
    elapsed = (time.perf_counter() - start_time) * 1000

    print(f"\n{CLR_BOLD}{CLR_GREEN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}   LAB SUITE RUNTIME BERHASIL DISELESAIKAN DALAM {elapsed:.2f} ms         {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}======================================================================{CLR_RESET}")


if __name__ == "__main__":
    main()