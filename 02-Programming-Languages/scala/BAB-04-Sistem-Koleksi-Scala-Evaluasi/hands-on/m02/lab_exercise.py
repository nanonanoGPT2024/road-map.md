#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Sistem Koleksi & Strategi Evaluasi Scala
Topik: BAB-04 - Strict vs Lazy Evaluation, View, LazyList (Stream), & Parallel Collection
Runtime: Pure Python 3 (Standar Library) dengan Rendering ANSI Terminal
"""

import sys
import time
import itertools
from dataclasses import dataclass, field
from typing import Callable, Generic, Iterator, List, Optional, TypeVar

T = TypeVar("T")
R = TypeVar("R")

# ANSI Color Codes & Styles
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"
    BG_DARK = "\033[40m"


def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
================================================================================
  SCALA COLLECTION SYSTEM & EVALUATION STRATEGY SIMULATOR (BAB-04)
  Arsitektur: Strict vs View (Pipeline Fusion) vs LazyList (Memoized Thunk)
================================================================================{Colors.RESET}"""
    print(banner)


# -------------------------------------------------------------------------
# 1. Strict Collection Simulation (Mirip Scala List / Vector)
# -------------------------------------------------------------------------
class StrictList(Generic[T]):
    """
    Simulasi Scala Strict Collection (eager evaluation).
    Setiap transformasi (map/filter) menghasilkan koleksi perantara baru di heap.
    """
    def __init__(self, elements: List[T]):
        self.elements = list(elements)

    def map(self, f: Callable[[T], R], stage_name: str = "map") -> "StrictList[R]":
        print(f"  {Colors.YELLOW}[STRICT {stage_name}]{Colors.RESET} Alokasi koleksi perantara berukuran {len(self.elements)}...")
        result = []
        for x in self.elements:
            result.append(f(x))
        return StrictList(result)

    def filter(self, predicate: Callable[[T], bool], stage_name: str = "filter") -> "StrictList[T]":
        print(f"  {Colors.YELLOW}[STRICT {stage_name}]{Colors.RESET} Memfilter elemen dan menyusun buffer perantara...")
        result = [x for x in self.elements if predicate(x)]
        return StrictList(result)

    def take(self, n: int) -> "StrictList[T]":
        print(f"  {Colors.YELLOW}[STRICT take({n})]{Colors.RESET} Mengiris elemen dari buffer hasil akhir.")
        return StrictList(self.elements[:n])

    def to_list(self) -> List[T]:
        return list(self.elements)


# -------------------------------------------------------------------------
# 2. View Simulation (Mirip Scala .view - Non-strict & Pipeline Fusion)
# -------------------------------------------------------------------------
class ScalaView(Generic[T]):
    """
    Simulasi Scala View (scala.collection.View).
    Transformasi di-fuse (pipeline fusion) tanpa alokasi struktur perantara.
    Evaluasi baru dipicu saat terminal operation (misal: to_list atau foldLeft).
    """
    def __init__(self, source_iterable: Iterator[T]):
        self._iterator_factory = lambda: iter(source_iterable)

    def map(self, f: Callable[[T], R], stage_name: str = "map") -> "ScalaView[R]":
        def transformed():
            for elem in self._iterator_factory():
                print(f"    {Colors.CYAN}[VIEW {stage_name}]{Colors.RESET} Transformasi elemen on-the-fly: {elem}")
                yield f(elem)
        return ScalaView(transformed())

    def filter(self, predicate: Callable[[T], bool], stage_name: str = "filter") -> "ScalaView[T]":
        def filtered():
            for elem in self._iterator_factory():
                passed = predicate(elem)
                status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}DROP{Colors.RESET}"
                print(f"    {Colors.CYAN}[VIEW {stage_name}]{Colors.RESET} Uji predikat elemen {elem} -> {status}")
                if passed:
                    yield elem
        return ScalaView(filtered())

    def take(self, n: int) -> "ScalaView[T]":
        def limited():
            count = 0
            for elem in self._iterator_factory():
                if count >= n:
                    print(f"    {Colors.GREEN}[VIEW Short-Circuit]{Colors.RESET} Ambang batas take({n}) terpenuhi, hentikan iterasi!")
                    break
                yield elem
                count += 1
        return ScalaView(limited())

    def to_list(self) -> List[T]:
        print(f"  {Colors.MAGENTA}{Colors.BOLD}[TERMINAL OPERATION .to_list]{Colors.RESET} Memulai traversal terpadu...")
        collected = []
        for x in self._iterator_factory():
            collected.append(x)
        return collected


# -------------------------------------------------------------------------
# 3. LazyList Simulation (Mirip Scala LazyList - Infinite Stream with Memoization)
# -------------------------------------------------------------------------
@dataclass
class LazyNode(Generic[T]):
    head: T
    _tail_thunk: Callable[[], Optional["LazyNode[T]"]]
    _evaluated_tail: Optional["LazyNode[T]"] = field(default=None, init=False)

    @property
    def tail(self) -> Optional["LazyNode[T]"]:
        if self._evaluated_tail is None and self._tail_thunk is not None:
            print(f"    {Colors.BLUE}[LazyList Thunk]{Colors.RESET} Mengevaluasi tail untuk head={self.head} (Memoizing)")
            self._evaluated_tail = self._tail_thunk()
        return self._evaluated_tail


class LazyList(Generic[T]):
    def __init__(self, root_node: Optional[LazyNode[T]]):
        self.root = root_node

    @staticmethod
    def iterate(seed: T, step: Callable[[T], T]) -> "LazyList[T]":
        def make_node(val: T) -> LazyNode[T]:
            return LazyNode(val, lambda: make_node(step(val)))
        return LazyList(make_node(seed))

    def take(self, n: int) -> List[T]:
        results = []
        current = self.root
        while current is not None and len(results) < n:
            results.append(current.head)
            current = current.tail
        return results


# -------------------------------------------------------------------------
# 4. Modul Perbandingan Kinerja & Arsitektur
# -------------------------------------------------------------------------
def run_strict_vs_view_comparison():
    print(f"\n{Colors.BOLD}{Colors.UNDERLINE}=== Skenario 1: Evaluasi Eager (Strict) vs Lazy (View) ==={Colors.RESET}")
    dataset = list(range(1, 11))
    print(f"Dataset masukan: {dataset}")

    print(f"\n{Colors.BOLD}[1] Menjalankan Pipeline Strict (Scala List/Vector):{Colors.RESET}")
    t0 = time.perf_counter()
    strict_coll = StrictList(dataset)
    step1 = strict_coll.map(lambda x: x * 2, "Kali-Dua")
    step2 = step1.filter(lambda x: x % 4 == 0, "Kelipatan-4")
    final_strict = step2.take(2).to_list()
    t_strict = (time.perf_counter() - t0) * 1000
    print(f"Hasil Strict: {final_strict} (Waktu simulasi: {t_strict:.3f} ms)")

    print(f"\n{Colors.BOLD}[2] Menjalankan Pipeline View (Scala View Pipeline Fusion):{Colors.RESET}")
    t1 = time.perf_counter()
    view_coll = ScalaView(iter(dataset))
    # Deklarasi pipeline tanpa evaluasi komputasi seketika
    lazy_pipeline = (
        view_coll.map(lambda x: x * 2, "Kali-Dua")
                 .filter(lambda x: x % 4 == 0, "Kelipatan-4")
                 .take(2)
    )
    print(f"  {Colors.GREEN}[INFO]{Colors.RESET} Pipeline didefinisikan secara deklaratif, belum ada komputasi yang berjalan.")
    final_view = lazy_pipeline.to_list()
    t_view = (time.perf_counter() - t1) * 1000
    print(f"Hasil View: {final_view} (Waktu simulasi: {t_view:.3f} ms)")


def run_lazylist_demo():
    print(f"\n{Colors.BOLD}{Colors.UNDERLINE}=== Skenario 2: Infinite Stream / LazyList dengan Memoized Thunk ==={Colors.RESET}")
    print("Mendefinisikan deret Fibonacci tak-hingga dengan Scala-like LazyList...")

    def fib_stream(a: int = 0, b: int = 1) -> LazyNode[int]:
        return LazyNode(a, lambda: fib_stream(b, a + b))

    fib_lazy = LazyList(fib_stream(0, 1))

    print(f"{Colors.YELLOW}[Langkah A]{Colors.RESET} Mengambil 5 elemen pertama:")
    res_a = fib_lazy.take(5)
    print(f"  -> Hasil 5 elemen pertama: {res_a}")

    print(f"\n{Colors.YELLOW}[Langkah B]{Colors.RESET} Meminta 8 elemen (Perhatikan memoization, elemen 1-5 tidak dievaluasi ulang):")
    res_b = fib_lazy.take(8)
    print(f"  -> Hasil 8 elemen: {res_b}")


def run_collection_hierarchy_overview():
    print(f"\n{Colors.BOLD}{Colors.UNDERLINE}=== Skenario 3: Taksonomi Hirarki Koleksi Scala 2.13+ ==={Colors.RESET}")
    hierarchy = [
        ("Iterable[+A]", "Root trait dari seluruh koleksi yang dapat ditraversal."),
        ("Seq[+A]", "Urutan berindeks atau linier (teratur): IndexedSeq (Vector) vs LinearSeq (List)."),
        ("Set[A]", "Koleksi elemen unik tanpa duplikasi (HashSet, TreeSet)."),
        ("Map[K, +V]", "Koleksi pasangan kunci-nilai (HashMap, TreeMap)."),
        ("View[+A]", "Transformasi non-strict terfusi tanpa intermediate collection."),
        ("LazyList[+A]", "Linked list lazy dengan head dievaluasi eager & tail memoized thunk.")
    ]
    for trait_name, desc in hierarchy:
        print(f"  • {Colors.CYAN}{Colors.BOLD}{trait_name:<16}{Colors.RESET} : {desc}")


def interactive_cli():
    print_banner()
    while True:
        print(f"\n{Colors.BOLD}PILIHAN MENU SIMULASI:{Colors.RESET}")
        print(f"  {Colors.GREEN}[1]{Colors.RESET} Jalankan Perbandingan Strict vs View (Pipeline Fusion)")
        print(f"  {Colors.GREEN}[2]{Colors.RESET} Jalankan Demo Infinite LazyList (Memoized Thunk)")
        print(f"  {Colors.GREEN}[3]{Colors.RESET} Tampilkan Taksonomi Hirarki Koleksi Scala")
        print(f"  {Colors.GREEN}[4]{Colors.RESET} Eksekusi Semua Skenario Pengujian")
        print(f"  {Colors.RED}[0]{Colors.RESET} Keluar dari Program")
        
        try:
            choice = input(f"\n{Colors.BOLD}Pilih opsi [0-4]: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}Keluar dari simulator.{Colors.RESET}")
            break

        if choice == "1":
            run_strict_vs_view_comparison()
        elif choice == "2":
            run_lazylist_demo()
        elif choice == "3":
            run_collection_hierarchy_overview()
        elif choice == "4":
            run_strict_vs_view_comparison()
            run_lazylist_demo()
            run_collection_hierarchy_overview()
        elif choice == "0":
            print(f"{Colors.GREEN}Sesi simulasi selesai. Terima kasih.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Opsi tidak valid, silakan masukkan nomor 0-4.{Colors.RESET}")


if __name__ == "__main__":
    interactive_cli()
