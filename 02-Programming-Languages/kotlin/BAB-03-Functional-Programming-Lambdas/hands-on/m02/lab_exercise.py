#!/usr/bin/env python3
"""
Lab Hands-on: Kotlin Functional Programming & Scope Functions Deep Dive
Simulation Engine: Simulating Kotlin's Scope Functions (let, also, apply, run)
and Lazy Evaluation Pipelines (Sequence vs List) in Python 3.
"""

import sys
import time
import random
from typing import Callable, TypeVar, Generic, Iterable, Iterator, Optional, Any
from dataclasses import dataclass, field

# Terminal styling using ANSI escape codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"

T = TypeVar("T")
R = TypeVar("R")


# ============================================================================
# Section 1: Kotlin Scope Functions Abstraction
# ============================================================================

class KotlinScopeMixin:
    """
    Simulates Kotlin's standard library scope functions:
    - let:   Context: 'it', returns lambda result. Idiomatic for null checks/transformations.
    - also:  Context: 'it', returns context object. Idiomatic for side-effects/logging.
    - apply: Context: 'this' (self), returns context object. Idiomatic for object initialization.
    - run:   Context: 'this' (self), returns lambda result. Idiomatic for scoped computations.
    """

    def let(self: T, block: Callable[[T], R]) -> R:
        """Executes 'block' with 'self' as argument ('it') and returns its result."""
        return block(self)

    def also(self: T, block: Callable[[T], Any]) -> T:
        """Executes 'block' with 'self' as argument ('it') for side-effects and returns 'self'."""
        block(self)
        return self

    def apply(self: T, block: Callable[[T], Any]) -> T:
        """Executes mutating 'block' on 'self' and returns 'self' (builder/configurator)."""
        block(self)
        return self

    def run(self: T, block: Callable[[T], R]) -> R:
        """Executes 'block' operating on 'self' and returns the computed result."""
        return block(self)


# ============================================================================
# Section 2: Domain Entity Model
# ============================================================================

@dataclass
class Transaction(KotlinScopeMixin):
    tx_id: str
    user_id: str
    amount: float
    currency: str = "USD"
    status: str = "PENDING"
    risk_score: float = 0.0
    audit_trail: list = field(default_factory=list)

    def log_event(self, event: str) -> None:
        self.audit_trail.append(f"[{time.strftime('%H:%M:%S')}] {event}")


# ============================================================================
# Section 3: Lazy Sequences vs Eager Iterables (Kotlin Sequence Engine)
# ============================================================================

class Sequence(Generic[T]):
    """
    Simulates Kotlin's Sequence: Multi-step processing is evaluated lazily,
    element-by-element, avoiding intermediate collection allocations.
    """

    def __init__(self, iterator_factory: Callable[[], Iterator[T]]) -> None:
        self._iterator_factory = iterator_factory

    def __iter__(self) -> Iterator[T]:
        return self._iterator_factory()

    def filter(self, predicate: Callable[[T], bool]) -> 'Sequence[T]':
        def _generator() -> Iterator[T]:
            for item in self:
                if predicate(item):
                    yield item
        return Sequence(_generator)

    def map(self, transform: Callable[[T], R]) -> 'Sequence[R]':
        def _generator() -> Iterator[R]:
            for item in self:
                yield transform(item)
        return Sequence(_generator)

    def take(self, count: int) -> 'Sequence[T]':
        def _generator() -> Iterator[T]:
            taken = 0
            for item in self:
                if taken >= count:
                    break
                yield item
                taken += 1
        return Sequence(_generator)

    def to_list(self) -> list[T]:
        return list(self)

    def fold(self, initial: R, operation: Callable[[R, T], R]) -> R:
        acc = initial
        for item in self:
            acc = operation(acc, item)
        return acc

    @staticmethod
    def from_iterable(iterable: Iterable[T]) -> 'Sequence[T]':
        return Sequence(lambda: iter(iterable))


# ============================================================================
# Section 4: Operational Demonstrations
# ============================================================================

def demo_scope_functions() -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== DEMO 1: Kotlin Scope Functions (let, also, apply, run) ==={CLR_RESET}")

    # 1. apply: Initialize and configure mutable state
    print(f"\n{CLR_YELLOW}[1. apply]{CLR_RESET} Configuring transaction entity:")
    tx = Transaction(tx_id="TX-9021", user_id="USR-4412", amount=1250.50).apply(
        lambda t: (
            setattr(t, "currency", "EUR"),
            setattr(t, "risk_score", 0.12),
            t.log_event("Initialized with apply()")
        )
    )
    print(f"  Initialized Entity: ID={tx.tx_id}, Amount={tx.amount} {tx.currency}, Risk={tx.risk_score}")

    # 2. also: Perform decoupled side-effects (telemetry, logging) without breaking the chain
    print(f"\n{CLR_YELLOW}[2. also]{CLR_RESET} Appending audit telemetry inline:")
    tx.also(lambda it: print(f"  --> Telemetry Hook: Emitting metrics for User {it.user_id}")) \
      .also(lambda it: it.log_event("Telemetry logged via also()"))

    # 3. let: Transform context object or handle nullability checks safely
    print(f"\n{CLR_YELLOW}[3. let]{CLR_RESET} Mapping domain model into API Response DTO:")
    dto = tx.let(lambda it: {
        "reference": it.tx_id,
        "settlement": f"{it.amount:.2f} {it.currency}",
        "authorized": it.risk_score < 0.50
    })
    print(f"  Transformed DTO via let(): {dto}")

    # 4. run: Execute a contextual calculation block and yield result
    print(f"\n{CLR_YELLOW}[4. run]{CLR_RESET} Executing validation block:")
    approval_status = tx.run(
        lambda this: "APPROVED" if (this.amount < 5000 and this.risk_score < 0.25) else "REJECTED"
    )
    tx.status = approval_status
    print(f"  Evaluation result via run(): {approval_status}")
    print(f"  Final Audit History: {tx.audit_trail}")


def demo_lazy_sequences(dataset_size: int = 100_000) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== DEMO 2: Kotlin Sequences (Lazy) vs Eager Collections ==={CLR_RESET}")
    print(f"Generating synthetic payload of {dataset_size:,} transactions...")

    raw_data = [
        Transaction(
            tx_id=f"TX-{i:06d}",
            user_id=f"USR-{random.randint(100, 999)}",
            amount=round(random.uniform(5.0, 1000.0), 2),
            risk_score=round(random.random(), 2)
        )
        for i in range(dataset_size)
    ]

    target_count = 5

    # --- EAGER PIPELINE (Standard Python lists / Kotlin Iterable) ---
    print(f"\n{CLR_MAGENTA}[Eager Evaluation Pipeline]{CLR_RESET}")
    t0 = time.perf_counter()
    
    # Eager allocates memory for all filtered and transformed intermediate lists
    step1 = [t for t in raw_data if t.risk_score < 0.05]
    step2 = [t.apply(lambda it: setattr(it, "amount", it.amount * 1.05)) for t in step1]
    eager_results = step2[:target_count]
    
    t_eager = (time.perf_counter() - t0) * 1000.0
    print(f"  Processed entire dataset eagerly. Computed first {target_count} records.")
    print(f"  Elapsed Time: {CLR_BOLD}{t_eager:.2f} ms{CLR_RESET}")

    # --- LAZY SEQUENCE PIPELINE (Kotlin Sequence) ---
    print(f"\n{CLR_GREEN}[Lazy Sequence Pipeline]{CLR_RESET}")
    t1 = time.perf_counter()

    seq = Sequence.from_iterable(raw_data) \
        .filter(lambda t: t.risk_score < 0.05) \
        .map(lambda t: t.apply(lambda it: setattr(it, "amount", it.amount * 1.05))) \
        .take(target_count)

    lazy_results = seq.to_list()
    t_lazy = (time.perf_counter() - t1) * 1000.0
    print(f"  Pipeline evaluated lazily up to take({target_count}).")
    print(f"  Elapsed Time: {CLR_BOLD}{t_lazy:.2f} ms{CLR_RESET}")

    speedup = t_eager / t_lazy if t_lazy > 0 else float('inf')
    print(f"\n{CLR_BOLD}Performance Gain (Sequence Short-circuit): {CLR_GREEN}{speedup:.1f}x faster{CLR_RESET}")

    # Accumulation fold demonstration
    total_exposure = Sequence.from_iterable(lazy_results).fold(
        0.0, lambda acc, tx: acc + tx.amount
    )
    print(f"Fold aggregate exposure on sample: ${total_exposure:,.2f}")


def main() -> None:
    print(f"{CLR_BOLD}===================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}  KOTLIN DEEP DIVE: Scope Functions & Functional Pipelines in Python{CLR_RESET}")
    print(f"{CLR_BOLD}===================================================================={CLR_RESET}")

    demo_scope_functions()
    demo_lazy_sequences(dataset_size=150_000)

    print(f"\n{CLR_BOLD}{CLR_GREEN}[✔] Lab verification complete. All functional semantics executed.{CLR_RESET}\n")


if __name__ == "__main__":
    main()