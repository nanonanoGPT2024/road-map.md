#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Sistem Koleksi Scala & Strategi Evaluasi
Topik: BAB 04 - Sistem Koleksi Scala & Evaluasi (Strict, Lazy, View, Immutable Hierarchy)

Skrip interaktif ini mendemonstrasikan perilaku internal arsitektur koleksi Scala:
1. Strict Collection Evaluation (List / Vector) & Intermediate Allocation
2. Lazy Evaluation via Scala-style View & LazyList / Stream
3. Persistent Immutable Data Structures & Structural Sharing
4. Parallel vs Sequential Simulation (Map / Filter / Fold)
"""

import sys
import time
from typing import Callable, Generic, Iterable, Iterator, List, Optional, TypeVar

T = TypeVar("T")
R = TypeVar("R")

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{YELLOW} [SIMULASI SCALA] {title.upper()}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


def subheader(title: str) -> None:
    print(f"\n{BOLD}{BLUE}--- {title} ---{RESET}")


class ScalaStrictList(Generic[T]):
    """Simulasi List Scala: Evaluasi eager (strict) dengan alokasi intermediate buffer."""

    def __init__(self, items: Iterable[T]):
        self._data: List[T] = list(items)

    def map(self, f: Callable[[T], R], log_prefix: str = "StrictList.map") -> "ScalaStrictList[R]":
        result: List[R] = []
        for x in self._data:
            print(f"  {DIM}[{log_prefix}] transform elemen: {x}{RESET}")
            result.append(f(x))
        return ScalaStrictList(result)

    def filter(self, p: Callable[[T], bool], log_prefix: str = "StrictList.filter") -> "ScalaStrictList[T]":
        result: List[T] = []
        for x in self._data:
            passed = p(x)
            print(f"  {DIM}[{log_prefix}] cek predikat: {x} -> {passed}{RESET}")
            if passed:
                result.append(x)
        return ScalaStrictList(result)

    def take(self, n: int) -> "ScalaStrictList[T]":
        return ScalaStrictList(self._data[:n])

    def to_list(self) -> List[T]:
        return list(self._data)


class ScalaView(Generic[T]):
    """Simulasi scala.collection.View: Evaluasi non-strict tanpa intermediate collections."""

    def __init__(self, iterator_factory: Callable[[], Iterator[T]]):
        self._factory = iterator_factory

    def __iter__(self) -> Iterator[T]:
        return self._factory()

    def map(self, f: Callable[[T], R]) -> "ScalaView[R]":
        parent_iter = self._factory

        def generator() -> Iterator[R]:
            for x in parent_iter():
                print(f"  {MAGENTA}[View.map PIPELINE] on-demand transform: {x}{RESET}")
                yield f(x)

        return ScalaView(generator)

    def filter(self, p: Callable[[T], bool]) -> "ScalaView[T]":
        parent_iter = self._factory

        def generator() -> Iterator[T]:
            for x in parent_iter():
                passed = p(x)
                print(f"  {MAGENTA}[View.filter PIPELINE] on-demand filter: {x} -> {passed}{RESET}")
                if passed:
                    yield x

        return ScalaView(generator)

    def take(self, n: int) -> "ScalaView[T]":
        parent_iter = self._factory

        def generator() -> Iterator[T]:
            count = 0
            for x in parent_iter():
                if count >= n:
                    break
                count += 1
                yield x

        return ScalaView(generator)

    def to_list(self) -> List[T]:
        print(f"  {GREEN}[View Terminal] Memaksa evaluasi (toList)...{RESET}")
        return list(self)


class LazyNode(Generic[T]):
    """Simulasi sel LazyList/Stream: Head bernilai strict, Tail dievaluasi on-demand (thunk memoized)."""

    def __init__(self, head: T, tail_thunk: Optional[Callable[[], Optional["LazyNode[T]"]]] = None):
        self.head: T = head
        self._tail_thunk = tail_thunk
        self._memoized_tail: Optional["LazyNode[T]"] = None
        self._evaluated: bool = False

    @property
    def tail(self) -> Optional["LazyNode[T]"]:
        if not self._evaluated:
            if self._tail_thunk is not None:
                print(f"  {YELLOW}[LazyList Memoization] Menghitung Tail dari head={self.head}{RESET}")
                self._memoized_tail = self._tail_thunk()
            self._evaluated = True
        else:
            print(f"  {DIM}[LazyList Cache] Mengambil Tail yang telah dimemoize (head={self.head}){RESET}")
        return self._memoized_tail


def lazy_range(start: int) -> LazyNode[int]:
    """Infinite stream generator mirip Scala LazyList.from(start)."""
    return LazyNode(start, lambda: lazy_range(start + 1))


def demo_strict_vs_view() -> None:
    header("1. Strict vs View Evaluation Pipeline")
    dataset = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    print(f"Dataset Input : {dataset}")

    subheader("A. Scala Strict List Pipeline (.map(...).filter(...).take(2))")
    print(f"{YELLOW}Tahap 1: map(x => x * 10){RESET}")
    strict = ScalaStrictList(dataset)
    step1 = strict.map(lambda x: x * 10)

    print(f"{YELLOW}Tahap 2: filter(x => x > 30){RESET}")
    step2 = step1.filter(lambda x: x > 30)

    print(f"{YELLOW}Tahap 3: take(2){RESET}")
    result_strict = step2.take(2).to_list()
    print(f"{GREEN}Hasil Strict : {result_strict}{RESET}")
    print(f"{RED}Catatan: Seluruh 10 elemen diproses & dialokasikan di memori pada setiap step.{RESET}")

    subheader("B. Scala View Pipeline (.view.map(...).filter(...).take(2).toList)")
    view = ScalaView(lambda: iter(dataset))
    pipeline = view.map(lambda x: x * 10).filter(lambda x: x > 30).take(2)
    print(f"{CYAN}Pipeline terbentuk secara deklaratif tanpa eksekusi langsung.{RESET}")
    result_view = pipeline.to_list()
    print(f"{GREEN}Hasil View   : {result_view}{RESET}")
    print(f"{GREEN}Catatan: Evaluasi berhenti seketika saat take(2) terpenuhi. Zero intermediate buffer!{RESET}")


def demo_lazylist() -> None:
    header("2. Infinite LazyList & Memoization")
    print("Membangun deret tak hingga mulai dari angka 10: LazyList.from(10)")
    stream = lazy_range(10)

    print(f"\n{BLUE}Membaca elemen ke-1:{RESET}")
    print(f"Head: {BOLD}{stream.head}{RESET}")

    print(f"\n{BLUE}Membaca elemen ke-2 (memicu thunk tail pertama):{RESET}")
    n2 = stream.tail
    if n2:
        print(f"Head ke-2: {BOLD}{n2.head}{RESET}")

    print(f"\n{BLUE}Membaca kembali elemen ke-2 (harus memakai memoized cache):{RESET}")
    n2_again = stream.tail
    if n2_again:
        print(f"Head ke-2 (cached): {BOLD}{n2_again.head}{RESET}")


def demo_immutable_structural_sharing() -> None:
    header("3. Structural Sharing pada Immutable Cons List")
    print("Dalam Scala: val listA = 2 :: 3 :: Nil; val listB = 1 :: listA")

    class ConsCell:
        def __init__(self, value: int, next_node: Optional["ConsCell"] = None):
            self.value = value
            self.next = next_node

        def display(self) -> str:
            curr = self
            elems = []
            while curr:
                elems.append(str(curr.value))
                curr = curr.next
            return " -> ".join(elems) + " -> Nil"

    tail_shared = ConsCell(2, ConsCell(3, None))
    list_a = tail_shared
    list_b = ConsCell(1, tail_shared)

    print(f"List A       : {list_a.display()} (id_node_2: {hex(id(list_a))})")
    print(f"List B       : {list_b.display()} (id_node_2: {hex(id(list_b.next))})")
    same_ptr = list_a is list_b.next
    print(f"\n{GREEN}Verifikasi Pointer Sharing: list_a is list_b.tail == {BOLD}{same_ptr}{RESET}")
    print("List B tidak menyalin elemen 2 dan 3, melainkan menunjuk langsung pada node List A.")


def run_interactive_benchmark() -> None:
    header("4. Benchmark: Strict vs Lazy View pada Koleksi Besar")
    size = 200_000
    print(f"Membuat dataset sebanyak {size:,} integer...")
    raw_data = list(range(1, size + 1))

    # Benchmark Strict
    t0 = time.perf_counter()
    # Simulasikan eager map & filter
    m_res = [x * 2 for x in raw_data]
    f_res = [x for x in m_res if x % 3 == 0]
    strict_head = f_res[:5]
    t1 = time.perf_counter()
    strict_duration = (t1 - t0) * 1000

    # Benchmark Lazy View Generator
    t2 = time.perf_counter()
    gen = (x for x in (y * 2 for y in raw_data) if x % 3 == 0)
    lazy_head = [next(gen) for _ in range(5)]
    t3 = time.perf_counter()
    lazy_duration = (t3 - t2) * 1000

    print(f"\n{BOLD}Strict Processing:{RESET}")
    print(f"  Hasil (5 elemen pertama) : {strict_head}")
    print(f"  Durasi                    : {RED}{strict_duration:.2f} ms{RESET}")

    print(f"\n{BOLD}Lazy View Processing:{RESET}")
    print(f"  Hasil (5 elemen pertama) : {lazy_head}")
    print(f"  Durasi                    : {GREEN}{lazy_duration:.4f} ms{RESET}")

    speedup = strict_duration / max(lazy_duration, 0.0001)
    print(f"\n{BOLD}{CYAN}Akselerasi Lazy View: ~{speedup:.1f}x lebih cepat untuk operasi tereduksi (take/head).{RESET}")


def main() -> None:
    print(f"{BOLD}{GREEN}=== SIMULATOR LAB KOLEKSI SCALA & EVALUASI STRATEGY ==={RESET}")
    print("Materi BAB 04: Sistem Koleksi Scala & Evaluasi")

    while True:
        print(f"\n{BOLD}Pilih Menu Demonstrasi:{RESET}")
        print("  1. Strict List vs Scala View (Pipeline Inspection)")
        print("  2. LazyList / Stream Memoization")
        print("  3. Immutable Structural Sharing (Cons Cell Memory Reuse)")
        print("  4. Benchmark Skala Besar (Strict vs View Performance)")
        print("  5. Jalankan Semua Demonstrasi")
        print("  0. Keluar")

        try:
            choice = input(f"\n{CYAN}Masukkan nomor menu [0-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            demo_strict_vs_view()
        elif choice == "2":
            demo_lazylist()
        elif choice == "3":
            demo_immutable_structural_sharing()
        elif choice == "4":
            run_interactive_benchmark()
        elif choice == "5":
            demo_strict_vs_view()
            demo_lazylist()
            demo_immutable_structural_sharing()
            run_interactive_benchmark()
        elif choice in ("0", "exit", "q"):
            print(f"{GREEN}Simulator selesai. Terima kasih.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 0-5.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        demo_strict_vs_view()
        demo_lazylist()
        demo_immutable_structural_sharing()
        run_interactive_benchmark()
    else:
        main()
