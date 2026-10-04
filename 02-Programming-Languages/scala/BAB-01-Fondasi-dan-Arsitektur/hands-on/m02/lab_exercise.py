#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi Bahasa & Ekosistem Scala (Deep Dive)
Simulasi Komprehensif Arsitektur Fondasi Scala:
1. Trait Linearization Engine (Resolusi Pewarisan Berlapis & Diamond Problem)
2. Algebraic Data Types (ADTs) & Pattern Matching dengan Extractor (unapply)
3. Implicit / Contextual Resolution System (Scala 3 Given/Using Typeclass Pattern)
"""

import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Type


# ANSI Escape Codes untuk Visualisasi Terminal
class TerminalColor:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


# ==============================================================================
# 1. TRAIT LINEARIZATION ENGINE
# ==============================================================================
# Di Scala, urutan eksekusi method trait ditentukan oleh Linearization Order:
# L(C) = [C] + [elemen dari L(Tn) ... L(T1) + L(SuperClass), eliminasi duplikasi dari kiri]
class ScalaTraitLinearizer:
    """
    Mensimulasikan algoritma komputasi linierisasi hierarki tipe Scala
    untuk menyelesaikan 'Diamond Problem' pada multi-trait mixing.
    """

    def __init__(self):
        # Struktur deklarasi: Nama Kelas/Trait -> List[SuperClass/Traits]
        # Dimana index 0 adalah base class/superclass, sisanya adalah mixed-in traits
        self.hierarchy: Dict[str, List[str]] = {}

    def register(self, name: str, parents: List[str]) -> None:
        """Mendaftarkan kelas atau trait beserta rantai pewarisannya."""
        self.hierarchy[name] = parents

    def linearize(self, class_name: str) -> List[str]:
        """
        Menghitung urutan linierisasi formal Scala.
        Algoritma: L(C) = C + (L(Trait_k) + ... + L(Trait_1) + L(SuperClass))
        dengan mempertahankan hanya kemunculan terakhir dari setiap elemen (right-bias).
        """
        if class_name not in self.hierarchy or not self.hierarchy[class_name]:
            return [class_name]

        parents = self.hierarchy[class_name]
        # Evaluasi linierisasi dari kanan ke kiri (Trait terakhir diprioritaskan)
        accumulated: List[str] = []
        for parent in reversed(parents):
            parent_lin = self.linearize(parent)
            accumulated.extend(parent_lin)

        # Bangun linierisasi: [Class] + reversed elements yang dide-duplikasi
        seen = set()
        deduped = []
        # Membaca dari kanan (prioritas paling dasar/Any) untuk deduplikasi
        for item in reversed(accumulated):
            if item not in seen:
                seen.add(item)
                deduped.append(item)

        # Balikkan kembali agar urutan eksekusi: Kelas -> Trait N -> ... -> AnyRef -> Any
        return [class_name] + list(reversed(deduped))


# ==============================================================================
# 2. ALGEBRAIC DATA TYPES (ADT) & EXTRACTOR PATTERN MATCHING
# ==============================================================================
# Scala sealed trait Tree / case class simulasi
class Expr:
    """Base Sealed Trait untuk representasi AST (Algebraic Data Type)."""
    pass


@dataclass(frozen=True)
class Const(Expr):
    value: float


@dataclass(frozen=True)
class Var(Expr):
    name: str


@dataclass(frozen=True)
class Add(Expr):
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Mul(Expr):
    left: Expr
    right: Expr


class ExtractorAdd:
    """Mensimulasikan Scala 'object Add { def unapply(e: Expr) = ... }'."""

    @staticmethod
    def unapply(expr: Expr) -> Optional[Tuple[Expr, Expr]]:
        if isinstance(expr, Add):
            return (expr.left, expr.right)
        return None


class ExtractorMul:
    """Mensimulasikan Scala 'object Mul { def unapply(e: Expr) = ... }'."""

    @staticmethod
    def unapply(expr: Expr) -> Optional[Tuple[Expr, Expr]]:
        if isinstance(expr, Mul):
            return (expr.left, expr.right)
        return None


def eval_pattern_match(expr: Expr, env: Dict[str, float]) -> float:
    """
    Evaluator ekspresi menggunakan simulasi Scala Pattern Matching
    dengan exhaustiveness dan recursive structure decomposition.
    """
    # Pattern 1: Const(v)
    if isinstance(expr, Const):
        return expr.value

    # Pattern 2: Var(x)
    if isinstance(expr, Var):
        if expr.name not in env:
            raise ValueError(f"Variabel tidak terdefinisi: {expr.name}")
        return env[expr.name]

    # Pattern 3: Add(l, r) via Extractor unapply
    add_match = ExtractorAdd.unapply(expr)
    if add_match is not None:
        left, right = add_match
        return eval_pattern_match(left, env) + eval_pattern_match(right, env)

    # Pattern 4: Mul(l, r) via Extractor unapply
    mul_match = ExtractorMul.unapply(expr)
    if mul_match is not None:
        left, right = mul_match
        return eval_pattern_match(left, env) * eval_pattern_match(right, env)

    raise TypeError(f"MatchError: Pola ekspresi tidak dikenal: {type(expr)}")


def pretty_print_ast(expr: Expr) -> str:
    """Format string ekspresi layaknya case class stringifier Scala."""
    if isinstance(expr, Const):
        return f"Const({expr.value})"
    if isinstance(expr, Var):
        return f"Var({expr.name})"
    if isinstance(expr, Add):
        return f"Add({pretty_print_ast(expr.left)}, {pretty_print_ast(expr.right)})"
    if isinstance(expr, Mul):
        return f"Mul({pretty_print_ast(expr.left)}, {pretty_print_ast(expr.right)})"
    return str(expr)


# ==============================================================================
# 3. CONTEXTUAL ABSTRACTIONS (GIVEN / USING & TYPECLASS RESOLVER)
# ==============================================================================
class ContextScope:
    """
    Mensimulasikan implicit scope / given instance registry pada Scala 3.
    Mendukung resolusi typeclass otomatis berbasis tipe data target.
    """

    def __init__(self):
        # Pemetaan (NamaTypeclass, TipeTarget) -> Instance Implementasi
        self._registry: Dict[Tuple[str, Type], Any] = {}

    def register_given(self, typeclass_name: str, target_type: Type, instance: Any) -> None:
        """Mendaftarkan 'given instance' ke dalam compiler context table."""
        self._registry[(typeclass_name, target_type)] = instance

    def summon(self, typeclass_name: str, target_type: Type) -> Any:
        """
        Mensimulasikan 'summon[TypeClass[T]]' atau compiler search:
        mencari given instance yang cocok di implicit scope.
        """
        key = (typeclass_name, target_type)
        if key not in self._registry:
            raise LookupError(
                f"No given instance of type {typeclass_name}[{target_type.__name__}] found!"
            )
        return self._registry[key]


# Typeclass: Show[T] (Format String untuk Tipe T)
class ShowTypeclass:
    def __init__(self, show_func: Callable[[Any], str]):
        self.show_func = show_func

    def show(self, value: Any) -> str:
        return self.show_func(value)


# Typeclass: NumericSerializer[T]
class SerializerTypeclass:
    def __init__(self, serialize_func: Callable[[Any], str]):
        self.serialize_func = serialize_func

    def serialize(self, value: Any) -> str:
        return self.serialize_func(value)


# Method yang menggunakan 'using' context parameter
def format_data(value: Any, ctx: ContextScope) -> str:
    """Simulasi fungsi Scala: def formatData[T](v: T)(using s: Show[T]): String."""
    show_instance: ShowTypeclass = ctx.summon("Show", type(value))
    return show_instance.show(value)


# ==============================================================================
# PIPELINE DEMO & VERIFIKASI INTERAKTIF
# ==============================================================================
def print_header(title: str) -> None:
    print(f"\n{TerminalColor.BOLD}{TerminalColor.CYAN}{'='*70}{TerminalColor.RESET}")
    print(f"{TerminalColor.BOLD}{TerminalColor.HEADER}>>> {title}{TerminalColor.RESET}")
    print(f"{TerminalColor.BOLD}{TerminalColor.CYAN}{'='*70}{TerminalColor.RESET}")


def run_linearization_demo() -> None:
    print_header("1. DEMO: SCALA TRAIT LINEARIZATION & DIAMOND RESOLUTION")
    linearizer = ScalaTraitLinearizer()

    # Struktur Hirarki Klasik Scala:
    # Any -> AnyRef -> BaseService -> (LoggingTrait, MetricTrait) -> PaymentService
    linearizer.register("Any", [])
    linearizer.register("AnyRef", ["Any"])
    linearizer.register("BaseService", ["AnyRef"])
    linearizer.register("LoggingTrait", ["BaseService"])
    linearizer.register("MetricTrait", ["BaseService"])
    # PaymentService extends BaseService with LoggingTrait with MetricTrait
    linearizer.register("PaymentService", ["BaseService", "LoggingTrait", "MetricTrait"])

    print(f"{TerminalColor.YELLOW}[Deklarasi Hierarki]{TerminalColor.RESET}")
    print("  class BaseService extends AnyRef")
    print("  trait LoggingTrait extends BaseService")
    print("  trait MetricTrait extends BaseService")
    print("  class PaymentService extends BaseService with LoggingTrait with MetricTrait\n")

    result = linearizer.linearize("PaymentService")
    print(f"{TerminalColor.GREEN}[Hasil Linierisasi Scala - Urutan Resolusi 'super']{TerminalColor.RESET}")
    for idx, node in enumerate(result):
        prefix = f"  {idx + 1}. "
        if idx == 0:
            print(f"{prefix}{TerminalColor.BOLD}{node}{TerminalColor.RESET} (Origin Invocation)")
        else:
            print(f"{prefix}--> super redirects to: {TerminalColor.BLUE}{node}{TerminalColor.RESET}")


def run_adt_pattern_matching_demo() -> None:
    print_header("2. DEMO: ADT & EXTRACTOR-BASED PATTERN MATCHING")

    # Membangun AST: (x + 10.5) * (y + 2.0)
    ast: Expr = Mul(
        Add(Var("x"), Const(10.5)),
        Add(Var("y"), Const(2.0))
    )
    env = {"x": 4.5, "y": 8.0}

    print(f"{TerminalColor.YELLOW}[Representasi AST Scala Case Class]{TerminalColor.RESET}")
    print(f"  Expr = {pretty_print_ast(ast)}")
    print(f"  Environment = {env}\n")

    print(f"{TerminalColor.GREEN}[Eksekusi Recursive Pattern Matcher]{TerminalColor.RESET}")
    start_time = time.perf_counter()
    eval_result = eval_pattern_match(ast, env)
    duration_us = (time.perf_counter() - start_time) * 1_000_000

    print(f"  Sub-ekspresi kiri  : (4.5 + 10.5) = 15.0")
    print(f"  Sub-ekspresi kanan : (8.0 + 2.0)  = 10.0")
    print(f"  Hasil Evaluasi AST : {TerminalColor.BOLD}{eval_result}{TerminalColor.RESET}")
    print(f"  Evaluated in       : {duration_us:.2f} µs")


def run_contextual_typeclass_demo() -> None:
    print_header("3. DEMO: SCALA 3 GIVEN/USING CONTEXTUAL RESOLUTION")
    scope = ContextScope()

    # Mendaftarkan 'given' instances ke compiler scope
    scope.register_given("Show", int, ShowTypeclass(lambda i: f"Scala.Int({i})"))
    scope.register_given("Show", str, ShowTypeclass(lambda s: f'Scala.String("{s}")'))
    scope.register_given(
        "Show",
        dict,
        ShowTypeclass(lambda d: f"Scala.Map({', '.join(f'{k} -> {v}' for k, v in d.items())})")
    )

    test_payloads = [
        42,
        "Reactive Microservice",
        {"cluster_id": 101, "status": "UP"}
    ]

    print(f"{TerminalColor.YELLOW}[Resolusi Otomatis Typeclass via Context Scope]{TerminalColor.RESET}")
    for item in test_payloads:
        formatted = format_data(item, scope)
        print(f"  Input: {str(item):<35} => Output Show[T]: {TerminalColor.GREEN}{formatted}{TerminalColor.RESET}")

    # Uji verifikasi kegagalan compile-time/summon jika instance tidak ada
    print(f"\n{TerminalColor.YELLOW}[Pengujian Missing Given Instance (Compile Error Simulation)]{TerminalColor.RESET}")
    try:
        format_data(3.14159, scope)  # Float belum didaftarkan
    except LookupError as err:
        print(f"  {TerminalColor.RED}[Expected Resolution Error]{TerminalColor.RESET} {err}")


def main() -> None:
    print(f"{TerminalColor.BOLD}{TerminalColor.GREEN}")
    print("┌──────────────────────────────────────────────────────────────────┐")
    print("│   SCALA ECOSYSTEM & RUNTIME ARCHITECTURE SIMULATION HARNESS      │")
    print("│   Fokus: Linearization, ADTs, Unapply, & Contextual Typeclasses  │")
    print("└──────────────────────────────────────────────────────────────────┘")
    print(f"{TerminalColor.RESET}")

    try:
        run_linearization_demo()
        run_adt_pattern_matching_demo()
        run_contextual_typeclass_demo()
        print(f"\n{TerminalColor.BOLD}{TerminalColor.GREEN}✓ Seluruh modul simulasi fondasi Scala berhasil dieksekusi.{TerminalColor.RESET}\n")
    except Exception as exc:
        print(f"\n{TerminalColor.RED}CRITICAL: Eksekusi gagal: {exc}{TerminalColor.RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()