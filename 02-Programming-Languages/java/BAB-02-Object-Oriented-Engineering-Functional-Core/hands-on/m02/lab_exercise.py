#!/usr/bin/env python3
"""
Lab: Java Enterprise Architecture Simulation
Chapter: 02 (Object-Oriented Engineering & Functional Core)
Module: Deep Dive into JVM Idiomatic Polymorphism, Records, and Stream Pipeline
"""

import abc
import dataclasses
import enum
import sys
import time
from typing import Callable, Generic, Iterator, List, Optional as PyOptional, TypeVar

# ANSI Escape Sequences for Enterprise Terminal Dashboard
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_GRAY = "\033[90m"

T = TypeVar("T")
R = TypeVar("R")


# ============================================================================
# Section 1: Java Functional Core (java.util.Optional & Lazy Stream<T>)
# ============================================================================

class Optional(Generic[T]):
    """
    Simulates java.util.Optional<T> monadic container to eliminate null pointer exceptions.
    Provides functional composition via map, filter, and flatMap.
    """
    def __init__(self, value: PyOptional[T]) -> None:
        self._value = value

    @staticmethod
    def of(value: T) -> "Optional[T]":
        if value is None:
            raise ValueError("NullPointerException: Optional.of cannot contain null")
        return Optional(value)

    @staticmethod
    def of_nullable(value: PyOptional[T]) -> "Optional[T]":
        return Optional(value)

    @staticmethod
    def empty() -> "Optional[T]":
        return Optional(None)

    def is_present(self) -> bool:
        return self._value is not None

    def get(self) -> T:
        if self._value is None:
            raise KeyError("NoSuchElementException: No value present in Optional")
        return self._value

    def or_else(self, other: T) -> T:
        return self._value if self._value is not None else other

    def filter(self, predicate: Callable[[T], bool]) -> "Optional[T]":
        if not self.is_present() or predicate(self._value):  # type: ignore
            return self
        return Optional.empty()

    def map(self, mapper: Callable[[T], PyOptional[R]]) -> "Optional[R]":
        if not self.is_present():
            return Optional.empty()
        result = mapper(self._value)  # type: ignore
        return Optional.of_nullable(result)


class Stream(Generic[T]):
    """
    Simulates java.util.stream.Stream<T>.
    Implements pull-based lazy pipeline processing using Python generators.
    Intermediate operations are not evaluated until a terminal operation is invoked.
    """
    def __init__(self, generator_func: Callable[[], Iterator[T]]) -> None:
        self._generator_func = generator_func

    @staticmethod
    def of(iterable: List[T]) -> "Stream[T]":
        return Stream(lambda: iter(iterable))

    def filter(self, predicate: Callable[[T], bool]) -> "Stream[T]":
        """Intermediate Operation: Lazily filters elements based on a Predicate."""
        def lazy_gen() -> Iterator[T]:
            for item in self._generator_func():
                if predicate(item):
                    yield item
        return Stream(lazy_gen)

    def map(self, mapper: Callable[[T], R]) -> "Stream[R]":
        """Intermediate Operation: Lazily transforms elements via a Function."""
        def lazy_gen() -> Iterator[R]:
            for item in self._generator_func():
                yield mapper(item)
        return Stream(lazy_gen)

    def limit(self, max_size: int) -> "Stream[T]":
        """Intermediate Operation: Short-circuiting stateful intermediate op."""
        def lazy_gen() -> Iterator[T]:
            count = 0
            for item in self._generator_func():
                if count >= max_size:
                    break
                yield item
                count += 1
        return Stream(lazy_gen)

    # Terminal Operations: Trigger pipeline execution
    def to_list(self) -> List[T]:
        return list(self._generator_func())

    def count(self) -> int:
        return sum(1 for _ in self._generator_func())

    def reduce(self, identity: R, accumulator: Callable[[R, T], R]) -> R:
        accum = identity
        for item in self._generator_func():
            accum = accumulator(accum, item)
        return accum

    def find_first(self) -> Optional[T]:
        for item in self._generator_func():
            return Optional.of(item)
        return Optional.empty()


# ============================================================================
# Section 2: OOP Engineering (Records, Interfaces, and Template Pattern)
# ============================================================================

class TxStatus(enum.Enum):
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"


@dataclasses.dataclass(frozen=True)
class TransactionRecord:
    """
    Simulates Java 16+ Record construct:
    Immutable data carrier with automatic equals, hashCode, and structural typing.
    """
    tx_id: str
    account_id: str
    amount: float
    currency: str
    status: TxStatus
    risk_score: float


class Auditable(abc.ABC):
    """Simulates a Java Contract/Interface."""
    @abc.abstractmethod
    def audit_trail(self, tx: TransactionRecord) -> str:
        pass


class AbstractTransactionPipeline(abc.ABC):
    """
    Template Method Pattern:
    Encapsulates core processing skeleton while delegating hook methods to subclasses.
    """
    def execute(self, transactions: List[TransactionRecord]) -> List[TransactionRecord]:
        start = time.perf_counter_ns()
        self.pre_hook()
        
        # Stream pipeline execution
        processed = (
            Stream.of(transactions)
            .filter(self.validate_criteria)
            .map(self.mutate_state)
            .to_list()
        )
        
        duration_us = (time.perf_counter_ns() - start) / 1000.0
        self.post_hook(len(processed), duration_us)
        return processed

    @abc.abstractmethod
    def validate_criteria(self, tx: TransactionRecord) -> bool:
        pass

    @abc.abstractmethod
    def mutate_state(self, tx: TransactionRecord) -> TransactionRecord:
        pass

    def pre_hook(self) -> None:
        pass

    def post_hook(self, record_count: int, duration_us: float) -> None:
        pass


class FraudDetectionPipeline(AbstractTransactionPipeline, Auditable):
    """Concrete Processor evaluating enterprise fraud heuristics."""
    
    def validate_criteria(self, tx: TransactionRecord) -> bool:
        # Flag transactions with high risk or amounts above threshold
        return tx.risk_score > 0.65 or tx.amount >= 10000.0

    def mutate_state(self, tx: TransactionRecord) -> TransactionRecord:
        # Immutability pattern: Create a new Record instance with updated status
        return TransactionRecord(
            tx_id=tx.tx_id,
            account_id=tx.account_id,
            amount=tx.amount,
            currency=tx.currency,
            status=TxStatus.FLAGGED,
            risk_score=tx.risk_score
        )

    def audit_trail(self, tx: TransactionRecord) -> str:
        return f"[AUDIT-ALERT] High risk TX '{tx.tx_id}' for Account '{tx.account_id}' marked as FLAGGED."

    def pre_hook(self) -> None:
        print(f"{CLR_GRAY}[PIPELINE] Initializing Real-Time Heuristic Guard...{CLR_RESET}")

    def post_hook(self, record_count: int, duration_us: float) -> None:
        print(f"{CLR_GRAY}[PIPELINE] Completed in {duration_us:.2f} µs. Flagged count: {record_count}{CLR_RESET}")


# ============================================================================
# Section 3: Lab Verification & Execution Suite
# ============================================================================

def generate_mock_ledger() -> List[TransactionRecord]:
    """Generates immutable mock ledger records."""
    return [
        TransactionRecord("TX-1001", "ACC-US-882", 250.00, "USD", TxStatus.PENDING, 0.12),
        TransactionRecord("TX-1002", "ACC-EU-331", 12500.00, "EUR", TxStatus.PENDING, 0.45),
        TransactionRecord("TX-1003", "ACC-AP-990", 85.50, "USD", TxStatus.PENDING, 0.05),
        TransactionRecord("TX-1004", "ACC-US-411", 4500.00, "USD", TxStatus.PENDING, 0.88),
        TransactionRecord("TX-1005", "ACC-SA-119", 99000.00, "USD", TxStatus.PENDING, 0.95),
        TransactionRecord("TX-1006", "ACC-EU-512", 340.00, "EUR", TxStatus.PENDING, 0.20),
    ]


def main() -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}===================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} LAB: JAVA OOP ENGINEERING & FUNCTIONAL CORE ARCHITECTURE (JVM-CORE) {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}===================================================================={CLR_RESET}\n")

    ledger = generate_mock_ledger()
    print(f"{CLR_BOLD}[1] Initial Immutable Ledger State:{CLR_RESET}")
    for tx in ledger:
        print(f"  • {tx.tx_id} | Acct: {tx.account_id:10} | Amt: ${tx.amount:>9.2f} | Risk: {tx.risk_score:.2f}")

    # Test OOP Template Method & Polymorphic Behavior
    print(f"\n{CLR_BOLD}[2] Executing Template Method Pattern (FraudDetectionPipeline):{CLR_RESET}")
    fraud_pipeline = FraudDetectionPipeline()
    flagged_txs = fraud_pipeline.execute(ledger)

    for flagged in flagged_txs:
        audit_log = fraud_pipeline.audit_trail(flagged)
        print(f"  {CLR_RED}⚡ {flagged.tx_id} -> Status: {flagged.status.value} (Risk: {flagged.risk_score}){CLR_RESET}")
        print(f"    {CLR_MAGENTA}↳ {audit_log}{CLR_RESET}")

    # Test Java 8 Stream Lazy Pipeline & Reductions
    print(f"\n{CLR_BOLD}[3] Java Stream Processing (Intermediate & Terminal Operations):{CLR_RESET}")
    
    # Calculate aggregated total exposure of flagged items using Stream.reduce()
    total_exposure = (
        Stream.of(flagged_txs)
        .map(lambda tx: tx.amount)
        .reduce(0.0, lambda acc, amt: acc + amt)
    )
    print(f"  {CLR_GREEN}✔ Aggregated High-Risk Exposure (reduce): ${total_exposure:,.2f}{CLR_RESET}")

    # Stream short-circuit evaluation via limit()
    limited_scan = (
        Stream.of(ledger)
        .filter(lambda tx: tx.amount > 100.0)
        .limit(2)
        .to_list()
    )
    print(f"  {CLR_GREEN}✔ Short-Circuit Evaluation (limit=2): {[x.tx_id for x in limited_scan]}{CLR_RESET}")

    # Test Monadic Optional
    print(f"\n{CLR_BOLD}[4] Monadic Null-Safety Verification (Optional<T>):{CLR_RESET}")
    
    first_flagged = (
        Stream.of(ledger)
        .filter(lambda tx: tx.amount > 50000.0)
        .find_first()
    )

    result_status = (
        first_flagged
        .filter(lambda tx: tx.currency == "USD")
        .map(lambda tx: f"Account {tx.account_id} exceeded critical exposure limit!")
        .or_else("No critical accounts detected.")
    )
    print(f"  {CLR_YELLOW}★ Optional Pipeline Result: {result_status}{CLR_RESET}")

    # Empty Optional test
    empty_optional: Optional[str] = Optional.empty()
    fallback = empty_optional.map(str.upper).or_else("DEFAULT_FALLBACK")
    print(f"  {CLR_YELLOW}★ Optional Fallback Handling: {fallback}{CLR_RESET}")

    # Assertions for Automated Verification
    assert len(flagged_txs) == 3, f"Expected 3 flagged transactions, got {len(flagged_txs)}"
    assert total_exposure == 116000.0, f"Expected exposure 116000.0, got {total_exposure}"
    assert fallback == "DEFAULT_FALLBACK", "Optional fallback logic failed"

    print(f"\n{CLR_BOLD}{CLR_GREEN}===================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN} ALL VERIFICATION CONTRACTS PASSED (OOP & FUNCTIONAL CORE SOUND) {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}===================================================================={CLR_RESET}\n")


if __name__ == "__main__":
    main()