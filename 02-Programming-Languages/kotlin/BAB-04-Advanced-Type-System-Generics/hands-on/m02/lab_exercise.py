#!/usr/bin/env python3
"""
Lab Hands-on: Kotlin Advanced Type System & Generics Simulation
Bab 04: Advanced Type System & Generics - Modul 02 Deep Dive

Skrip ini memodelkan dan mengeksekusi mesin semantik sistem tipe Kotlin di Python:
1. Subtyping Hierarchy & Lattice (Any, Nothing, Number, Int, Double, String).
2. Declaration-site Variance (`out` / Covariant, `in` / Contravariant, Invariant).
3. Upper Bound Enforcement (Generic constraints: T : Number).
4. Reified Type Parameters Simulation (Menembus JVM Type Erasure).
5. Star Projection (`*`) Read/Write Safety Constraints.
"""

from __future__ import annotations
import sys
import time
from enum import Enum
from typing import Any as PyAny, List, Optional, Set, Dict

# ==============================================================================
# ANSI Color Formatting Helper
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    CYAN    = "\033[36m"
    MAGENTA = "\033[35m"

def print_header(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'='*75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} [KOTLIN TYPE ENGINE] {title.upper()}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'='*75}{Color.RESET}")

def print_result(label: str, passed: bool, detail: str = "") -> None:
    tag = f"{Color.GREEN}PASS{Color.RESET}" if passed else f"{Color.RED}FAIL / REJECTED{Color.RESET}"
    detail_str = f" -> {Color.YELLOW}{detail}{Color.RESET}" if detail else ""
    print(f"  [{tag}] {Color.BOLD}{label}{Color.RESET}{detail_str}")

# ==============================================================================
# Model: Kotlin Type Hierarchy (Subtyping Lattice)
# ==============================================================================
class KType:
    """Merepresentasikan tipe data Kotlin dengan relasi inheritance hierarkis."""
    def __init__(self, name: str, supertypes: Optional[List[KType]] = None, is_nullable: bool = False):
        self.name = name
        self.supertypes: List[KType] = supertypes or []
        self.is_nullable = is_nullable

    def make_nullable(self) -> KType:
        return KType(self.name, self.supertypes, is_nullable=True)

    def is_subtype_of(self, other: KType) -> bool:
        """
        Mengecek relasi subtyping (A <: B).
        Aturan Kotlin:
        - Non-nullable T adalah subtype dari T?
        - T? BUKAN subtype dari T
        - Nothing adalah subtype dari semua tipe non-null
        - Nothing? adalah subtype dari semua tipe nullable
        """
        # Penanganan Nullability
        if not self.is_nullable and other.is_nullable:
            # T <: T? -> cek apakah bentuk non-nullable self adalah subtype dari non-nullable other
            return self._is_raw_subtype_of(other)
        elif self.is_nullable and not other.is_nullable:
            # T? tidak bisa diassign ke non-nullable T
            return False
        else:
            return self._is_raw_subtype_of(other)

    def _is_raw_subtype_of(self, other: KType) -> bool:
        # Bottom type Nothing check
        if self.name == "Nothing":
            return True
        # Reflexivity: T <: T
        if self.name == other.name:
            return True
        # Top type Any check
        if other.name == "Any":
            return True

        # Transitivity: DFS traverse parent hierarki
        visited: Set[str] = set()
        queue = list(self.supertypes)
        while queue:
            curr = queue.pop(0)
            if curr.name == other.name:
                return True
            if curr.name not in visited:
                visited.add(curr.name)
                queue.extend(curr.supertypes)
        return False

    def __repr__(self) -> str:
        return f"{self.name}{'?' if self.is_nullable else ''}"

# Definisi Standar Primitif & Objek Hierarchy
KAny = KType("Any")
KNumber = KType("Number", supertypes=[KAny])
KInt = KType("Int", supertypes=[KNumber])
KDouble = KType("Double", supertypes=[KNumber])
KString = KType("String", supertypes=[KAny])
KNothing = KType("Nothing")

# ==============================================================================
# Model: Variance (Declaration-site & Use-site)
# ==============================================================================
class Variance(Enum):
    INVARIANT = "invariant"      # Class<T>
    COVARIANT = "out"            # Class<out T> (Producer)
    CONTRAVARIANT = "in"         # Class<in T>  (Consumer)

class KGenericDefinition:
    """Definisi generik (seperti class Producer<out T>, Consumer<in T>)."""
    def __init__(self, name: str, variance: Variance, upper_bound: KType = KAny):
        self.name = name
        self.variance = variance
        self.upper_bound = upper_bound

class KAppliedType:
    """Tipe generik terinstansiasi (seperti Producer<Int>, Box<Number>)."""
    def __init__(self, generic_def: KGenericDefinition, type_argument: Optional[KType]):
        # type_argument None merepresentasikan Star Projection (*)
        self.generic_def = generic_def
        self.type_argument = type_argument
        self._validate_bounds()

    def _validate_bounds(self) -> None:
        """Memvalidasi Upper Bound (T : UpperBound)."""
        if self.type_argument is not None:
            if not self.type_argument.is_subtype_of(self.generic_def.upper_bound):
                raise TypeError(
                    f"Type argument '{self.type_argument}' melanggar upper bound "
                    f"'{self.generic_def.upper_bound}' pada {self.generic_def.name}"
                )

    def is_assignable_from(self, source: KAppliedType) -> bool:
        """
        Mengecek kompatibilitas penugasan berdasarkan Variansi:
        - Covariant (out T): Source<Sub> dapat ditugaskan ke Target<Super>
        - Contravariant (in T): Source<Super> dapat ditugaskan ke Target<Sub>
        - Invariant (T): Source<T> hanya menerima Target<T>
        - Star Projection (*): covariant menerima Any?, contravariant menerima Nothing
        """
        if self.generic_def.name != source.generic_def.name:
            return False

        # Star Projection handling pada target
        if self.type_argument is None:
            # Target adalah Generic<*>
            return True

        if source.type_argument is None:
            # Source adalah Generic<*>, tidak aman ditugaskan ke target bertipe spesifik
            return False

        var = self.generic_def.variance
        if var == Variance.INVARIANT:
            return self.type_argument.name == source.type_argument.name and \
                   self.type_argument.is_nullable == source.type_argument.is_nullable
        elif var == Variance.COVARIANT:
            # Producer: Subtype argumen boleh diberikan ke Supertype
            return source.type_argument.is_subtype_of(self.type_argument)
        elif var == Variance.CONTRAVARIANT:
            # Consumer: Supertype argumen boleh diberikan ke Subtype
            return self.type_argument.is_subtype_of(source.type_argument)
        return False

    def __repr__(self) -> str:
        arg_str = "*" if self.type_argument is None else repr(self.type_argument)
        var_str = f"{self.generic_def.variance.value} " if self.generic_def.variance != Variance.INVARIANT else ""
        return f"{self.generic_def.name}<{var_str}{arg_str}>"

# ==============================================================================
# Reified Type Parameter Simulator
# ==============================================================================
class ReifiedTypeInspector:
    """
    Simulasi pemrosesan Reified Generics vs Type Erasure.
    JVM secara default menghapus (erase) metadata generic saat runtime.
    Kotlin 'inline' + 'reified' menjaga metadata tipe tetap hidup untuk runtime check.
    """
    @staticmethod
    def type_erased_filter(items: List[PyAny]) -> List[PyAny]:
        # Simulasi behavior Java/JVM konvensional: Tipe terhapus menjadi Object (Any)
        # Tidak dapat memfilter berdasarkan instance tipe runtime secara aman
        return items

    @staticmethod
    def reified_filter_is_instance(items: List[PyAny], target_type: KType) -> List[PyAny]:
        """Meniru: inline fun <reified T> filterIsInstance(list: List<Any>): List<T>"""
        filtered = []
        for item in items:
            # Petakan nilai python ke KType runtime
            actual_type: Optional[KType] = None
            if isinstance(item, int):
                actual_type = KInt
            elif isinstance(item, float):
                actual_type = KDouble
            elif isinstance(item, str):
                actual_type = KString

            if actual_type and actual_type.is_subtype_of(target_type):
                filtered.append(item)
        return filtered

# ==============================================================================
# Test Scenario Runner
# ==============================================================================
def run_lab_benchmarks() -> None:
    print_header("1. Validasi Subtyping Lattice & Nullability Rules")
    
    cases_subtyping = [
        ("Int <: Number", KInt.is_subtype_of(KNumber), True),
        ("Number <: Any", KNumber.is_subtype_of(KAny), True),
        ("Int <: Any", KInt.is_subtype_of(KAny), True),
        ("String <: Number", KString.is_subtype_of(KNumber), False),
        ("Int <: Int?", KInt.is_subtype_of(KInt.make_nullable()), True),
        ("Int? <: Int", KInt.make_nullable().is_subtype_of(KInt), False),
        ("Nothing <: String", KNothing.is_subtype_of(KString), True),
    ]

    for expr, result, expected in cases_subtyping:
        print_result(f"Evaluasi Subtipe: {expr}", result == expected, f"Actual: {result}")

    print_header("2. Upper Bound Constraints Enforcement (T : Number)")
    
    # Generic Class definitions
    gen_numeric_repo = KGenericDefinition("NumericRepo", Variance.INVARIANT, upper_bound=KNumber)
    
    try:
        valid_repo = KAppliedType(gen_numeric_repo, KInt)
        print_result("Instansiasi NumericRepo<Int>", True, f"Berhasil: {valid_repo}")
    except TypeError as e:
        print_result("Instansiasi NumericRepo<Int>", False, str(e))

    try:
        invalid_repo = KAppliedType(gen_numeric_repo, KString)
        print_result("Instansiasi NumericRepo<String>", False, "Harusnya gagal!")
    except TypeError as e:
        print_result("Instansiasi NumericRepo<String> (Constraint Violation)", True, f"Ditolak: {e}")

    print_header("3. Declaration-Site Variance Matrix (out vs in vs invariant)")

    # 1. Invariant: Box<T>
    box_def = KGenericDefinition("Box", Variance.INVARIANT)
    box_number = KAppliedType(box_def, KNumber)
    box_int = KAppliedType(box_def, KInt)

    res_inv = box_number.is_assignable_from(box_int)
    print_result(
        "Invariant: Box<Number> = Box<Int>",
        res_inv == False,
        f"Kesesuaian Invariant ditolak (Aman): assignable={res_inv}"
    )

    # 2. Covariant: Producer<out T> (Source: Int, Target: Number -> Legal karena Int <: Number)
    prod_def = KGenericDefinition("Producer", Variance.COVARIANT)
    prod_number = KAppliedType(prod_def, KNumber)
    prod_int = KAppliedType(prod_def, KInt)

    res_cov = prod_number.is_assignable_from(prod_int)
    print_result(
        "Covariant (out): Producer<Number> = Producer<Int>",
        res_cov == True,
        f"Subtype parameter diizinkan sebagai Producer: assignable={res_cov}"
    )

    # 3. Contravariant: Consumer<in T> (Source: Number, Target: Int -> Legal karena Int <: Number)
    cons_def = KGenericDefinition("Consumer", Variance.CONTRAVARIANT)
    cons_number = KAppliedType(cons_def, KNumber)
    cons_int = KAppliedType(cons_def, KInt)

    res_contra = cons_int.is_assignable_from(cons_number)
    print_result(
        "Contravariant (in): Consumer<Int> = Consumer<Number>",
        res_contra == True,
        f"Supertype consumer aman menerima data bertipe Int: assignable={res_contra}"
    )

    print_header("4. Star Projection (*) Inspection & Bounds")
    
    star_target = KAppliedType(prod_def, None) # Producer<*>
    res_star_accept = star_target.is_assignable_from(prod_int)
    print_result(
        "Star Projection: Producer<*> = Producer<Int>",
        res_star_accept == True,
        "Producer<*> aman menerima varian concrete apapun"
    )

    concrete_target = KAppliedType(prod_def, KInt)
    res_star_reject = concrete_target.is_assignable_from(star_target)
    print_result(
        "Star Projection: Producer<Int> = Producer<*>",
        res_star_reject == False,
        "Producer<Int> menolak generic bertipe unknown/star"
    )

    print_header("5. JVM Type Erasure vs Reified Type Parameter")
    
    dataset: List[PyAny] = [100, "Kotlin Native", 45.67, 200, "Coroutines", 3.14]
    print(f"  {Color.BLUE}Dataset Input:{Color.RESET} {dataset}")

    # Simulasi Reified Function
    filtered_numbers = ReifiedTypeInspector.reified_filter_is_instance(dataset, KNumber)
    filtered_strings = ReifiedTypeInspector.reified_filter_is_instance(dataset, KString)
    filtered_ints    = ReifiedTypeInspector.reified_filter_is_instance(dataset, KInt)

    print_result(
        "inline fun <reified T : Number> filterIsInstance()",
        len(filtered_numbers) == 4,
        f"Hasil (Number): {filtered_numbers}"
    )
    print_result(
        "inline fun <reified T : String> filterIsInstance()",
        len(filtered_strings) == 2,
        f"Hasil (String): {filtered_strings}"
    )
    print_result(
        "inline fun <reified T : Int> filterIsInstance()",
        len(filtered_ints) == 2,
        f"Hasil (Int): {filtered_ints}"
    )

    print(f"\n{Color.BOLD}{Color.GREEN}Semua modul verifikasi Type System & Generics Kotlin berhasil dieksekusi.{Color.RESET}\n")

if __name__ == "__main__":
    t_start = time.perf_counter()
    run_lab_benchmarks()
    t_elapsed = (time.perf_counter() - t_start) * 1000
    print(f"Execution finished in {t_elapsed:.2f} ms")