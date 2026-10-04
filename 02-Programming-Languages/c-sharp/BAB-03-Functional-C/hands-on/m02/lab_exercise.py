#!/usr/bin/env python3
"""
Lab Hands-on: C# Internals Deep Dive
Bab 03: Functional C#, Delegasi & LINQ Internals
Modul 02: Deep Dive Simulasi Engine Delegasi, Multicast Chain, & Deferred Execution LINQ

Script ini mengimplementasikan simulasi runtime C# untuk:
 1. MulticastDelegate: Chain invocation list, delegate combination (+/-), dan exception safety.
 2. LINQ Core Engine: Deferred execution pipeline, iterator state-machine (yield return),
    operator chaining (Where, Select, Take), dan materialisasi (ToList, Aggregate).
 3. Expression Tree vs Delegate: Membedakan IQueryable (AST parsing) vs IEnumerable (in-memory execution).
"""

import sys
import time
from typing import Callable, Any, List, Generic, TypeVar, Iterator

# Generic Type Parameters setara C# T, TResult
T = TypeVar('T')
R = TypeVar('R')

# ANSI Color Codes untuk CLI output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"


class MulticastDelegate:
    """
    Simulasi System.MulticastDelegate pada CLR C#.
    Dalam C#, delegate diturunkan dari System.MulticastDelegate yang memiliki
    properti privat '_invocationList' (array object/pointer fungsi).
    """
    def __init__(self, func: Callable = None):
        self._invocation_list: List[Callable] = []
        if func is not None:
            self._invocation_list.append(func)

    def combine(self, other: 'MulticastDelegate') -> 'MulticastDelegate':
        """Setara dengan Delegate.Combine(d1, d2) atau operator +="""
        new_del = MulticastDelegate()
        new_del._invocation_list = list(self._invocation_list)
        if other and isinstance(other, MulticastDelegate):
            new_del._invocation_list.extend(other._invocation_list)
        elif callable(other):
            new_del._invocation_list.append(other)
        return new_del

    def remove(self, target: Callable) -> 'MulticastDelegate':
        """Setara dengan Delegate.Remove(d1, d2) atau operator -="""
        new_del = MulticastDelegate()
        new_del._invocation_list = list(self._invocation_list)
        # Menghapus kemunculan terakhir (LIFO pattern sesuai CLR standard)
        for i in reversed(range(len(new_del._invocation_list))):
            if new_del._invocation_list[i] == target:
                new_del._invocation_list.pop(i)
                break
        return new_del

    def __iadd__(self, other):
        return self.combine(other)

    def __isub__(self, other):
        return self.remove(other)

    def get_invocation_list(self) -> List[Callable]:
        """Setara dengan delegate.GetInvocationList()"""
        return list(self._invocation_list)

    def __call__(self, *args, **kwargs) -> Any:
        """
        Mengeksekusi chain delegate secara sekuensial.
        Mengembalikan return value dari target terakhir (standar CLR behavior).
        """
        result = None
        for func in self._invocation_list:
            result = func(*args, **kwargs)
        return result


class Enumerable(Generic[T]):
    """
    Simulasi System.Linq.Enumerable<T> dan interface IEnumerable<T>.
    Mendemonstrasikan deferred execution: query tidak dievaluasi saat dideklarasikan,
    melainkan saat konsumen memanggil GetEnumerator() / iterasi.
    """
    def __init__(self, generator_factory: Callable[[], Iterator[T]]):
        self._generator_factory = generator_factory

    def __iter__(self) -> Iterator[T]:
        # Membuka iterator baru setiap kali enumerasi dijalankan
        return self._generator_factory()

    @staticmethod
    def from_iterable(iterable: List[T]) -> 'Enumerable[T]':
        """Entry point pembungkus koleksi in-memory."""
        return Enumerable(lambda: iter(iterable))

    def where(self, predicate: Callable[[T], bool]) -> 'Enumerable[T]':
        """
        Simulasi LINQ .Where(x => ...).
        Menerapkan lazy filter menggunakan generator pipeline.
        """
        def iterator():
            for item in self:
                print(f"  {MAGENTA}[LINQ: Where Eval]{RESET} Memeriksa item: {item}")
                if predicate(item):
                    yield item
        return Enumerable(iterator)

    def select(self, selector: Callable[[T], R]) -> 'Enumerable[R]':
        """
        Simulasi LINQ .Select(x => ...).
        Menerapkan lazy projection transform.
        """
        def iterator():
            for item in self:
                print(f"  {CYAN}[LINQ: Select Eval]{RESET} Memproyeksikan: {item}")
                yield selector(item)
        return Enumerable(iterator)

    def take(self, count: int) -> 'Enumerable[T]':
        """
        Simulasi LINQ .Take(n).
        Mendemonstrasikan short-circuiting: iterasi berhenti sebelum koleksi habis.
        """
        def iterator():
            taken = 0
            for item in self:
                if taken >= count:
                    print(f"  {YELLOW}[LINQ: Take Limit]{RESET} Capai batas {count}, short-circuit pipeline.")
                    break
                taken += 1
                yield item
        return Enumerable(iterator)

    def to_list(self) -> List[T]:
        """
        Operator Materialisasi. Memaksa eksekusi rantai query LINQ.
        Setara dengan .ToList() di C#.
        """
        print(f"{BOLD}{GREEN}--> [Materialisasi Diinisiasi via ToList()]{RESET}")
        result = []
        for item in self:
            result.append(item)
        return result

    def aggregate(self, seed: R, accumulator: Callable[[R, T], R]) -> R:
        """
        Operator Pengurangan/Fold.
        Setara dengan .Aggregate(seed, (acc, item) => ...) di C#.
        """
        acc = seed
        for item in self:
            acc = accumulator(acc, item)
        return acc


class ExpressionNode:
    """
    Simulasi sederhana System.Linq.Expressions.ExpressionTree.
    IQueryable<T> menerima Expression<Func<T, bool>> bukan delegate compiled,
    sehingga query dapat di-parse dan diterjemahkan menjadi target query (misal: SQL).
    """
    def __init__(self, node_type: str, left=None, right=None, value=None):
        self.node_type = node_type
        self.left = left
        self.right = right
        self.value = value

    def to_sql_where_clause(self) -> str:
        """Menterjemahkan struktur Expression Tree menjadi klausa SQL."""
        if self.node_type == "BINARY_OP":
            left_sql = self.left.to_sql_where_clause()
            right_sql = self.right.to_sql_where_clause()
            op = "=" if self.value == "==" else self.value
            return f"({left_sql} {op} {right_sql})"
        elif self.node_type == "MEMBER_ACCESS":
            return str(self.value)
        elif self.node_type == "CONSTANT":
            if isinstance(self.value, str):
                return f"'{self.value}'"
            return str(self.value)
        return ""


def run_delegate_lab():
    print(f"\n{BOLD}{CYAN}=== DEMO 1: C# MulticastDelegate Internals ==={RESET}")
    
    logs: List[str] = []
    def audit_logger(msg: str):
        logs.append(f"Audit: {msg}")
        print(f"  [Handler 1] Log Audit dipanggil: '{msg}'")

    def security_monitor(msg: str):
        logs.append(f"Security: {msg}")
        print(f"  [Handler 2] SIEM Alert dipanggil: '{msg}'")

    def metrics_collector(msg: str):
        logs.append(f"Metric: {msg}")
        print(f"  [Handler 3] Prometheus Counter tercatat: '{msg}'")

    # Inisialisasi delegate
    pipeline = MulticastDelegate(audit_logger)
    print(f"{YELLOW}[Delegate State]{RESET} Inisialisasi awal dengan 1 target.")
    
    # Delegate combination (+ operator)
    pipeline += security_monitor
    pipeline += metrics_collector
    print(f"{YELLOW}[Delegate State]{RESET} Menambahkan 2 target via '+=' operator.")
    print(f"  Panjang Invocation List: {len(pipeline.get_invocation_list())}")

    print(f"\n{BOLD}Menjalankan Invocation Chain (Signal: 'Unauthorized Access'):{RESET}")
    pipeline("Unauthorized Access")

    # Delegate subtraction (- operator)
    print(f"\n{YELLOW}[Delegate State]{RESET} Melepas 'security_monitor' via '-=' operator.")
    pipeline -= security_monitor
    print(f"  Panjang Invocation List sekarang: {len(pipeline.get_invocation_list())}")
    
    print(f"{BOLD}Menjalankan Invocation Chain pasca pengurangan (Signal: 'User Logout'):{RESET}")
    pipeline("User Logout")


def run_linq_internals_lab():
    print(f"\n{BOLD}{CYAN}=== DEMO 2: LINQ Pipeline, Lazy Evaluation & Short-Circuit ==={RESET}")
    
    raw_telemetry = [12, 45, 68, 88, 102, 135, 150, 192, 210]
    print(f"Data Mentah Sumber (Dataset Ukuran {len(raw_telemetry)}): {raw_telemetry}\n")

    # Membangun Query LINQ (Hanya konstruksi expression/pipeline, BELUM ADA EKSEKUSI)
    print(f"{BOLD}[Tahap 1: Deklarasi Query Pipeline]{RESET}")
    source = Enumerable.from_iterable(raw_telemetry)
    
    # Query: Ambil angka genap > 50, kalikan 10, ambil 2 hasil pertama
    query = (source
             .where(lambda x: x > 50 and x % 2 == 0)
             .select(lambda x: x * 10)
             .take(2))

    print(f"{GREEN}Query pipeline berhasil didefinisikan! Perhatikan: Belum ada data yang diproses.{RESET}\n")
    time.sleep(0.5)

    # Tahap 2: Eksekusi melalui Materialisasi (.ToList())
    print(f"{BOLD}[Tahap 2: Eksekusi Nyata via Materialisasi]{RESET}")
    materialized_result = query.to_list()
    
    print(f"\n{BOLD}{GREEN}Hasil Akhir Evaluasi LINQ: {materialized_result}{RESET}")
    print(f"{YELLOW}Analisis Arsitektur:{RESET} Perhatikan bahwa angka 135, 150, 192, 210 "
          f"TIDAK PERNAH dievaluasi oleh Where/Select berkat iterator state-machine dan short-circuiting Take(2).")


def run_linq_aggregation_lab():
    print(f"\n{BOLD}{CYAN}=== DEMO 3: LINQ Aggregate / Folding Internals ==={RESET}")
    scores = Enumerable.from_iterable([10, 20, 30, 40, 50])
    
    # Simulasi .Aggregate(0, (acc, item) => acc + item)
    total = scores.aggregate(0, lambda acc, val: acc + val)
    print(f"Total Nilai via .Aggregate(): {BOLD}{GREEN}{total}{RESET}")
    
    # Simulasi agregasi bentuk string
    csv = scores.select(lambda x: str(x)).aggregate("", lambda acc, val: val if acc == "" else f"{acc},{val}")
    print(f"CSV serialization via Pipeline: {BOLD}{YELLOW}{csv}{RESET}")


def run_expression_tree_lab():
    print(f"\n{BOLD}{CYAN}=== DEMO 4: Expression<Func<T>> vs Func<T> (IQueryable Mechanics) ==={RESET}")
    print("IEnumerable mengeksekusi IL Bytecode in-memory.")
    print("IQueryable menerjemahkan Expression Tree (AST) ke target engine (misal: SQL).\n")

    # Merepresentasikan AST untuk: (User.Age >= 18)
    expr_tree = ExpressionNode(
        node_type="BINARY_OP",
        value=">=",
        left=ExpressionNode(node_type="MEMBER_ACCESS", value="User.Age"),
        right=ExpressionNode(node_type="CONSTANT", value=18)
    )

    sql = expr_tree.to_sql_where_clause()
    print(f"{BOLD}Ekspresi Code (C#):{RESET}  builder.Where(user => user.Age >= 18)")
    print(f"{BOLD}Parsed AST ke SQL:{RESET}   {GREEN}SELECT * FROM Users WHERE {sql};{RESET}")


def main():
    print(f"{BOLD}{MAGENTA}===================================================================={RESET}")
    print(f"{BOLD}{MAGENTA} LAB RUNTIME C#: DELEGATE INTERNALS & LINQ DEFERRED EXECUTION ENGINE {RESET}")
    print(f"{BOLD}{MAGENTA}===================================================================={RESET}")
    
    start_time = time.perf_counter()
    
    run_delegate_lab()
    run_linq_internals_lab()
    run_linq_aggregation_lab()
    run_expression_tree_lab()
    
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"\n{BOLD}{CYAN}Semua modul deep dive selesai dieksekusi dalam {elapsed:.2f} ms.{RESET}")


if __name__ == "__main__":
    main()