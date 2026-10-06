#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Abstraksi Kontekstual & Type Classes (Scala 3 Mechanics)
Bahasan: Type Classes, `given` instances, `using` clauses, Context Bounds, dan Extension Methods.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, Type, TypeVar
import sys
import time

# --- ANSI Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_GRAY = "\033[90m"

T = TypeVar("T")
A = TypeVar("A")

# --- Domain Data Models ---
@dataclass(frozen=True)
class User:
    id: int
    name: str
    tier: str

@dataclass(frozen=True)
class Transaction:
    tx_id: str
    amount: float
    currency: str


# --- Type Class Definitions (Simulasi Trait Scala) ---
class Show(Generic[T]):
    """Scala: trait Show[A] { def show(a: A): String }"""
    def show(self, a: T) -> str:
        raise NotImplementedError

class Eq(Generic[T]):
    """Scala: trait Eq[A] { def eqv(x: A, y: A): Boolean }"""
    def eqv(self, x: T, y: T) -> bool:
        raise NotImplementedError

class Monoid(Generic[T]):
    """Scala: trait Monoid[A] { def empty: A; def combine(x: A, y: A): A }"""
    def empty(self) -> T:
        raise NotImplementedError
    def combine(self, x: T, y: T) -> T:
        raise NotImplementedError


# --- Contextual Scope Registry (Simulasi Scala Given Resolution Scope) ---
class ContextRegistry:
    def __init__(self):
        # Key: (TypeClass, TargetType) -> Instance
        self._instances: Dict[Tuple[Type, Type], Any] = {}

    def register_given(self, tc_class: Type, target_type: Type, instance: Any) -> None:
        self._instances[(tc_class, target_type)] = instance

    def resolve(self, tc_class: Type, target_type: Type) -> Any:
        instance = self._instances.get((tc_class, target_type))
        if instance is None:
            raise LookupError(
                f"No given instance of type {tc_class.__name__}[{target_type.__name__}] was found for parameter in using clause"
            )
        return instance

    def summon(self, tc_class: Type, target_type: Type) -> Any:
        """Scala: summon[Show[User]]"""
        return self.resolve(tc_class, target_type)


global_context = ContextRegistry()


# --- Given Instances (Simulasi: given Show[User] with ...) ---
class UserShowInstance(Show[User]):
    def show(self, a: User) -> str:
        return f"User(id={a.id}, name='{a.name}', tier={a.tier})"

class TransactionShowInstance(Show[Transaction]):
    def show(self, a: Transaction) -> str:
        return f"Transaction[{a.tx_id}]: {a.amount:,.2f} {a.currency}"

class IntMonoidInstance(Monoid[int]):
    def empty(self) -> int:
        return 0
    def combine(self, x: int, y: int) -> int:
        return x + y

class StringMonoidInstance(Monoid[str]):
    def empty(self) -> str:
        return ""
    def combine(self, x: str, y: str) -> str:
        return x + y

class UserEqInstance(Eq[User]):
    def eqv(self, x: User, y: User) -> bool:
        return x.id == y.id


# Registrasi ke dalam Contextual Scope
global_context.register_given(Show, User, UserShowInstance())
global_context.register_given(Show, Transaction, TransactionShowInstance())
global_context.register_given(Monoid, int, IntMonoidInstance())
global_context.register_given(Monoid, str, StringMonoidInstance())
global_context.register_given(Eq, User, UserEqInstance())


# --- Contextual Functions (Simulasi 'using' clauses & Context Bounds) ---
def render(value: A, tc_type: Type, context: ContextRegistry = global_context) -> str:
    """
    Simulasi Scala 3:
    def render[A](value: A)(using s: Show[A]): String = s.show(value)
    """
    show_instance: Show[A] = context.summon(Show, type(value))
    return show_instance.show(value)


def combine_all(items: List[A], context: ContextRegistry = global_context) -> A:
    """
    Simulasi Scala 3 Context Bound:
    def combineAll[A: Monoid](items: List[A]): A = ...
    """
    if not items:
        raise ValueError("Cannot infer type from empty list")
    elem_type = type(items[0])
    monoid_instance: Monoid[A] = context.summon(Monoid, elem_type)
    
    result = monoid_instance.empty()
    for item in items:
        result = monoid_instance.combine(result, item)
    return result


def are_equal(val1: A, val2: A, context: ContextRegistry = global_context) -> bool:
    """
    Simulasi Scala 3:
    def areEqual[A](x: A, y: A)(using eq: Eq[A]): Boolean = eq.eqv(x, y)
    """
    eq_instance: Eq[A] = context.summon(Eq, type(val1))
    return eq_instance.eqv(val1, val2)


# --- Extension Methods (Simulasi: extension [A](a: A)(using s: Show[A]) def display) ---
class ContextSyntaxWrapper(Generic[A]):
    def __init__(self, value: A, context: ContextRegistry = global_context):
        self._value = value
        self._ctx = context

    def display(self) -> str:
        show_inst: Show[A] = self._ctx.summon(Show, type(self._value))
        return show_inst.show(self._value)

    def is_identical_to(self, other: A) -> bool:
        eq_inst: Eq[A] = self._ctx.summon(Eq, type(self._value))
        return eq_inst.eqv(self._value, other)


def ops(value: A) -> ContextSyntaxWrapper[A]:
    """Helper untuk mensimulasikan extension method syntax di Python."""
    return ContextSyntaxWrapper(value)


# --- Terminal Simulation UI ---
def print_header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== {title} ==={CLR_RESET}")

def print_substep(step: str, detail: str) -> None:
    print(f"  {CLR_YELLOW}➤ [{step}]{CLR_RESET} {detail}")

def print_scala_code(snippet: str) -> None:
    print(f"{CLR_GRAY}┌── Scala 3 Concept Equivalence ───────────────")
    for line in snippet.strip().splitlines():
        print(f"│  {CLR_MAGENTA}{line}{CLR_RESET}")
    print(f"{CLR_GRAY}└──────────────────────────────────────────────{CLR_RESET}")


def run_demo():
    print(f"{CLR_BOLD}{CLR_GREEN}╔═══════════════════════════════════════════════════════════════════╗{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}║ LAB 06: ABSTRAKSI KONTEKSTUAL & TYPE CLASSES (SCALA 3 ENGINE)     ║{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}╚═══════════════════════════════════════════════════════════════════╝{CLR_RESET}")

    # Step 1: Type Class & Summon
    print_header("1. Type Class Instantiation & 'using' Resolution")
    scala_step1 = """
trait Show[A]:
  def show(a: A): String

given Show[User] with
  def show(u: User): String = s"User(${u.id}, ${u.name}, ${u.tier})"

def render[A](a: A)(using s: Show[A]): String = s.show(a)
    """
    print_scala_code(scala_step1)
    
    alice = User(id=101, name="Alice", tier="Enterprise")
    tx = Transaction(tx_id="TX-9902", amount=4500000.0, currency="IDR")

    print_substep("EXEC", "Memanggil render() dengan implicit resolution...")
    rendered_user = render(alice, Show)
    rendered_tx = render(tx, Show)
    print(f"   {CLR_GREEN}✔ Output User       :{CLR_RESET} {rendered_user}")
    print(f"   {CLR_GREEN}✔ Output Transaction:{CLR_RESET} {rendered_tx}")

    # Step 2: Context Bounds & Monoid Combine
    print_header("2. Context Bounds: [A : Monoid]")
    scala_step2 = """
def combineAll[A: Monoid](list: List[A]): A =
  val m = summon[Monoid[A]]
  list.foldLeft(m.empty)(m.combine)
    """
    print_scala_code(scala_step2)

    int_nums = [10, 25, 30, 45, 90]
    str_chunks = ["Scala", " 3 ", "Contextual", " ", "Abstractions"]

    print_substep("EXEC", f"Menggabungkan list integer: {int_nums}")
    sum_res = combine_all(int_nums)
    print(f"   {CLR_GREEN}✔ Monoid[Int].combineAll    :{CLR_RESET} {sum_res}")

    print_substep("EXEC", f"Menggabungkan list string: {str_chunks}")
    concat_res = combine_all(str_chunks)
    print(f"   {CLR_GREEN}✔ Monoid[String].combineAll :{CLR_RESET} '{concat_res}'")

    # Step 3: Extension Methods & Eq
    print_header("3. Extension Methods & Type Class Eq")
    scala_step3 = """
extension [A](a: A)(using eq: Eq[A])
  def === (other: A): Boolean = eq.eqv(a, other)

extension [A](a: A)(using s: Show[A])
  def display: String = s.show(a)
    """
    print_scala_code(scala_step3)

    user1 = User(id=42, name="Bob", tier="Developer")
    user2 = User(id=42, name="Bob (Updated)", tier="Developer")
    user3 = User(id=99, name="Charlie", tier="Free")

    print_substep("EXEC", "Menguji User1 == User2 berdasarkan Eq[User] (id-equality):")
    is_eq_1_2 = ops(user1).is_identical_to(user2)
    is_eq_1_3 = ops(user1).is_identical_to(user3)
    print(f"   {CLR_GREEN}✔ user1.is_identical_to(user2) [ID:42 vs ID:42]:{CLR_RESET} {is_eq_1_2}")
    print(f"   {CLR_GREEN}✔ user1.is_identical_to(user3) [ID:42 vs ID:99]:{CLR_RESET} {is_eq_1_3}")
    print(f"   {CLR_GREEN}✔ user1.display() via Extension Method         :{CLR_RESET} {ops(user1).display()}")

    # Step 4: Simulasi Compile Error (Missing Given Instance)
    print_header("4. Simulasi Error: Missing Given / Implicit Instance")
    print_substep("EXEC", "Mencoba summon Show untuk tipe yang belum didaftarkan (Float)...")
    try:
        render(3.14159, Show)
    except LookupError as err:
        print(f"   {CLR_RED}✖ Compiler Error Simulation Caught:{CLR_RESET}\n   {CLR_RED}↳ {err}{CLR_RESET}")

    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ Seluruh simulasi kontekstual Scala 3 berhasil dieksekusi.{CLR_RESET}\n")


if __name__ == "__main__":
    run_demo()
