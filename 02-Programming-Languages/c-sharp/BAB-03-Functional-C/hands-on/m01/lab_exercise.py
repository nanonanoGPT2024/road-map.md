#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Paradigma Functional Programming di C# (BAB-03)
Implementasi simulasi konsep C# Functional Programming:
1. Immutability & Record Types (C# 9+ record & with-expression)
2. Advanced Pattern Matching & Switch Expressions (C# 8+)
3. LINQ Functional Pipeline (Select, Where, Aggregate)
4. Monadic Error Handling (Option / Result Type pattern)
"""

import sys
from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Callable, Generic, List, Optional, TypeVar

# ANSI Escape Sequences untuk Terminal Styling
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")


# -----------------------------------------------------------------------------
# 1. C# Records & Non-Destructive Mutation (with-expression)
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class OrderItem:
    sku: str
    price: float
    qty: int


@dataclass(frozen=True)
class OrderRecord:
    id: str
    customer: str
    items: tuple[OrderItem, ...]
    is_discounted: bool = False

    def with_discount(self, applied: bool) -> "OrderRecord":
        """Simulasi C# syntax: order with { IsDiscounted = applied }"""
        return replace(self, is_discounted=applied)


# -----------------------------------------------------------------------------
# 2. Functional Option / Result Monad (Mencegah NullReferenceException)
# -----------------------------------------------------------------------------
class Result(Generic[T, E]):
    def __init__(self, value: Optional[T] = None, error: Optional[E] = None, is_ok: bool = True):
        self._value = value
        self._error = error
        self._is_ok = is_ok

    @classmethod
    def ok(cls, value: T) -> "Result[T, E]":
        return cls(value=value, is_ok=True)

    @classmethod
    def fail(cls, error: E) -> "Result[T, E]":
        return cls(error=error, is_ok=False)

    def match(self, on_ok: Callable[[T], U], on_fail: Callable[[E], U]) -> U:
        if self._is_ok:
            return on_ok(self._value)  # type: ignore
        return on_fail(self._error)  # type: ignore

    def bind(self, fn: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":
        """Monadic bind / C# SelectMany"""
        if not self._is_ok:
            return Result.fail(self._error)  # type: ignore
        return fn(self._value)  # type: ignore


# -----------------------------------------------------------------------------
# 3. LINQ-Style Fluent Pipeline
# -----------------------------------------------------------------------------
class LinqStream(Generic[T]):
    def __init__(self, data: List[T]):
        self._data = list(data)

    def where(self, predicate: Callable[[T], bool]) -> "LinqStream[T]":
        """C# LINQ .Where(x => ...)"""
        return LinqStream([x for x in self._data if predicate(x)])

    def select(self, selector: Callable[[T], U]) -> "LinqStream[U]":
        """C# LINQ .Select(x => ...)"""
        return LinqStream([selector(x) for x in self._data])

    def aggregate(self, seed: U, accumulator: Callable[[U, T], U]) -> U:
        """C# LINQ .Aggregate(seed, (acc, cur) => ...)"""
        current = seed
        for item in self._data:
            current = accumulator(current, item)
        return current

    def to_list(self) -> List[T]:
        return list(self._data)


# -----------------------------------------------------------------------------
# 4. Pattern Matching & Switch Expression Simulation
# -----------------------------------------------------------------------------
class Tier(Enum):
    STANDARD = auto()
    VIP = auto()
    ENTERPRISE = auto()


def calculate_discount_switch(tier: Tier, total_spend: float) -> float:
    """
    Simulasi C# Switch Expression:
    tier switch {
        Tier.Enterprise when total > 1000 => 0.25,
        Tier.Enterprise => 0.20,
        Tier.Vip when total > 500 => 0.15,
        Tier.Vip => 0.10,
        _ => 0.0
    }
    """
    match (tier, total_spend):
        case (Tier.ENTERPRISE, spend) if spend > 1000:
            return 0.25
        case (Tier.ENTERPRISE, _):
            return 0.20
        case (Tier.VIP, spend) if spend > 500:
            return 0.15
        case (Tier.VIP, _):
            return 0.10
        case _:
            return 0.0


# -----------------------------------------------------------------------------
# Interactive Runner & Verification Suite
# -----------------------------------------------------------------------------
def print_banner() -> None:
    print(f"{CYAN}{BOLD}=============================================================={RESET}")
    print(f"{BLUE}{BOLD}   LAB EXERCISE: C# FUNCTIONAL PROGRAMMING PARADIGM (BAB-03)   {RESET}")
    print(f"{CYAN}{BOLD}=============================================================={RESET}\n")


def demo_records() -> None:
    print(f"{YELLOW}[Demo 1] C# 9+ Immutable Record & 'with' Non-destructive Mutation{RESET}")
    item1 = OrderItem("SKU-DOTNET", 150.0, 2)
    item2 = OrderItem("SKU-CSHARP", 80.0, 1)
    original_order = OrderRecord("ORD-101", "Budi Santoso", (item1, item2), is_discounted=False)
    
    modified_order = original_order.with_discount(True)
    
    print(f"  {BOLD}Original Record :{RESET} ID={original_order.id}, Discounted={original_order.is_discounted}")
    print(f"  {BOLD}Cloned 'with'   :{RESET} ID={modified_order.id}, Discounted={modified_order.is_discounted}")
    print(f"  {GREEN}Immutable Check :{RESET} Identik referensi? {original_order is modified_order} (Aman dari side-effect)\n")


def demo_switch_pattern() -> None:
    print(f"{YELLOW}[Demo 2] C# 8+ Pattern Matching & Switch Expression{RESET}")
    test_cases = [
        (Tier.ENTERPRISE, 1500.0),
        (Tier.ENTERPRISE, 300.0),
        (Tier.VIP, 750.0),
        (Tier.STANDARD, 1200.0),
    ]
    for tier, spend in test_cases:
        disc = calculate_discount_switch(tier, spend)
        print(f"  Pattern: ({tier.name:10}, Spend=${spend:7.2f}) => Diskon: {GREEN}{disc*100:4.1f}%{RESET}")
    print()


def demo_linq_pipeline() -> None:
    print(f"{YELLOW}[Demo 3] C# LINQ Functional Pipeline (Fluent Chaining){RESET}")
    scores = [45, 82, 91, 58, 77, 63, 89, 95]
    print(f"  Data Asli: {scores}")

    # LINQ: scores.Where(s => s >= 70).Select(s => s + 5).Aggregate(0, (acc, cur) => acc + cur)
    pipeline = LinqStream(scores)
    passed_boosted = pipeline.where(lambda s: s >= 70).select(lambda s: s + 5)
    total_val = passed_boosted.aggregate(0, lambda acc, cur: acc + cur)

    print(f"  Passed & Boosted (+5) : {passed_boosted.to_list()}")
    print(f"  Total Aggregate Sum   : {GREEN}{total_val}{RESET}\n")


def demo_monadic_result() -> None:
    print(f"{YELLOW}[Demo 4] Monadic Error Handling (Railway Oriented Programming){RESET}")
    
    def validate_positive(num: float) -> Result[float, str]:
        if num < 0:
            return Result.fail(f"Input {num} tidak boleh negatif")
        return Result.ok(num)

    def compute_sqrt_reciprocal(num: float) -> Result[float, str]:
        if num == 0:
            return Result.fail("Divisi dengan nol!")
        return Result.ok(100.0 / num)

    inputs = [25.0, -5.0, 0.0]
    for inp in inputs:
        res = validate_positive(inp).bind(compute_sqrt_reciprocal)
        output = res.match(
            on_ok=lambda v: f"{GREEN}Success -> {v:.2f}{RESET}",
            on_fail=lambda err: f"{RED}Fault -> {err}{RESET}"
        )
        print(f"  Pipeline Test ({inp:5.1f}) : {output}")
    print()


def main() -> None:
    print_banner()
    demo_records()
    demo_switch_pattern()
    demo_linq_pipeline()
    demo_monadic_result()
    print(f"{MAGENTA}{BOLD}>>> Simulasi Konsep Functional C# Selesai dengan Sukses. <<<{RESET}")


if __name__ == "__main__":
    main()
