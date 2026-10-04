#!/usr/bin/env python3
"""
Lab Hands-on: Scala 3 Contextual Abstractions & Type Classes Simulation
Bab 06 - Modul 02 Deep Dive

Skrip ini memodelkan subsistem compiler Scala 3 untuk Contextual Abstractions:
1. Type Class pattern (`trait Show[T]`, `trait JsonEncoder[T]`, `trait Monoid[T]`)
2. Contextual Instances (`given`) dan Implicit Resolution Scope
3. Synthesized / Derived Instances (Recursive Given Resolution: `given [T: Encoder]: Encoder[List[T]]`)
4. Context Parameters (`using`) yang di-inject otomatis via reflection runtime
5. Extension Methods yang memanfaatkan Context Bound
"""

import sys
import time
from typing import TypeVar, Generic, Any, Callable, Dict, Tuple, List, Optional, get_origin, get_args
from dataclasses import dataclass

# ==============================================================================
# ANSI Color Formatting Helper
# ==============================================================================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

T = TypeVar('T')
U = TypeVar('U')

# ==============================================================================
# Core Engine: Scala 3 Contextual Resolution Engine
# ==============================================================================
class ContextEngine:
    """
    Simulasi Implicit Scope & Search Engine milik Scala 3 Compiler.
    Menyimpan 'given' definitions dan menangani resolusi rekursif (derivation).
    """
    _given_registry: Dict[Tuple[type, type], Any] = {}
    _derivers: List[Callable[[type, type], Optional[Any]]] = []

    @classmethod
    def register_given(cls, typeclass: type, target_type: type, instance: Any) -> None:
        """Mendaftarkan instance 'given' eksplisit (misal: given Show[Int])."""
        cls._given_registry[(typeclass, target_type)] = instance

    @classmethod
    def register_deriver(cls, deriver_fn: Callable[[type, type], Optional[Any]]) -> None:
        """Mendaftarkan fungsi derivation sintetis (misal: given [T](using Show[T]): Show[List[T]])."""
        cls._derivers.append(deriver_fn)

    @classmethod
    def summon(cls, typeclass: type, target_type: type) -> Any:
        """
        Mensimulasikan 'summon[TypeClass[Target]]' Scala 3.
        Mencari instance di registry, jika tidak ada, mencoba sintesis via derivers.
        """
        # 1. Exact match di registry
        if (typeclass, target_type) in cls._given_registry:
            return cls._given_registry[(typeclass, target_type)]

        # 2. Type derivation check (Generics seperti List[T])
        origin = get_origin(target_type)
        if origin is not None:
            for deriver in cls._derivers:
                synthesized = deriver(typeclass, target_type)
                if synthesized is not None:
                    # Cache the derived instance
                    cls._given_registry[(typeclass, target_type)] = synthesized
                    return synthesized

        raise TypeError(
            f"{Colors.RED}[Resolution Error]{Colors.RESET} Could not find given instance for: "
            f"{Colors.BOLD}{typeclass.__name__}[{getattr(target_type, '__name__', str(target_type))}]{Colors.RESET}"
        )

def given(typeclass: type, target_type: type):
    """Decorator untuk mendaftarkan instance 'given'."""
    def decorator(cls_or_instance):
        instance = cls_or_instance() if isinstance(cls_or_instance, type) else cls_or_instance
        ContextEngine.register_given(typeclass, target_type, instance)
        return cls_or_instance
    return decorator

def using(typeclass: type, target_type: type) -> Any:
    """Helper untuk memanggil 'summon' secara eksplisit di dalam blok fungsi."""
    return ContextEngine.summon(typeclass, target_type)

# ==============================================================================
# Type Class Contracts (Traits)
# ==============================================================================
class Show(Generic[T]):
    """Trait Show[T]: Abstraksi konversi tipe T menjadi representasi textual."""
    def show(self, value: T) -> str:
        raise NotImplementedError

class Monoid(Generic[T]):
    """Trait Monoid[T]: Operasi biner asosiatif (combine) dengan elemen netral (empty)."""
    def empty(self) -> T:
        raise NotImplementedError

    def combine(self, x: T, y: T) -> T:
        raise NotImplementedError

class JsonEncoder(Generic[T]):
    """Trait JsonEncoder[T]: Serialisasi data structure ke JSON string."""
    def encode(self, value: T) -> str:
        raise NotImplementedError

# ==============================================================================
# Extension Methods Mechanism
# ==============================================================================
class ExtensionWrapper(Generic[T]):
    """
    Mensimulasikan Extension Methods di Scala 3:
    extension (x: T)(using Show[T]) def show: String = ...
    """
    def __init__(self, value: T, target_type: type):
        self.value = value
        self.target_type = target_type

    def show(self) -> str:
        instance: Show[T] = ContextEngine.summon(Show, self.target_type)
        return instance.show(self.value)

    def to_json(self) -> str:
        instance: JsonEncoder[T] = ContextEngine.summon(JsonEncoder, self.target_type)
        return instance.encode(self.value)

def extension(value: Any, target_type: Optional[type] = None) -> ExtensionWrapper:
    t_type = target_type if target_type is not None else type(value)
    return ExtensionWrapper(value, t_type)

# ==============================================================================
# Domain Entities
# ==============================================================================
@dataclass(frozen=True)
class Money:
    amount: float
    currency: str

@dataclass(frozen=True)
class Transaction:
    id: str
    amount: Money
    status: str

# ==============================================================================
# Given Instances Definitions (Scala 3: given Show[Money] with ...)
# ==============================================================================
@given(Show, Money)
class MoneyShow(Show[Money]):
    def show(self, value: Money) -> str:
        return f"{value.currency} {value.amount:,.2f}"

@given(Monoid, Money)
class MoneyMonoid(Monoid[Money]):
    def empty(self) -> Money:
        return Money(0.0, "USD")

    def combine(self, x: Money, y: Money) -> Money:
        if x.currency != y.currency and x.amount != 0.0 and y.amount != 0.0:
            raise ValueError(f"Currency mismatch: {x.currency} vs {y.currency}")
        curr = x.currency if x.amount != 0.0 else y.currency
        return Money(x.amount + y.amount, curr)

@given(JsonEncoder, Money)
class MoneyJsonEncoder(JsonEncoder[Money]):
    def encode(self, value: Money) -> str:
        return f'{{"amount": {value.amount}, "currency": "{value.currency}"}}'

@given(Show, Transaction)
class TransactionShow(Show[Transaction]):
    def show(self, value: Transaction) -> str:
        money_str = extension(value.amount, Money).show()
        return f"Txn[{value.id}]({money_str}, Status={value.status})"

@given(JsonEncoder, Transaction)
class TransactionJsonEncoder(JsonEncoder[Transaction]):
    def encode(self, value: Transaction) -> str:
        money_json = extension(value.amount, Money).to_json()
        return f'{{"id": "{value.id}", "amount": {money_json}, "status": "{value.status}"}}'

# ==============================================================================
# Recursive Derivation Engine (Synthesizing List[T] Type Classes)
# Equivalent to: given [T](using encoder: JsonEncoder[T]): JsonEncoder[List[T]]
# ==============================================================================
def derive_list_typeclasses(typeclass: type, target_type: type) -> Optional[Any]:
    origin = get_origin(target_type)
    if origin is list or origin is List:
        type_args = get_args(target_type)
        if not type_args:
            return None
        elem_type = type_args[0]

        # Sintesis JsonEncoder[List[T]]
        if typeclass is JsonEncoder:
            elem_encoder: JsonEncoder = ContextEngine.summon(JsonEncoder, elem_type)
            class DerivedListEncoder(JsonEncoder[List[Any]]):
                def encode(self, values: List[Any]) -> str:
                    encoded_elems = [elem_encoder.encode(item) for item in values]
                    return "[" + ", ".join(encoded_elems) + "]"
            return DerivedListEncoder()

        # Sintesis Show[List[T]]
        if typeclass is Show:
            elem_show: Show = ContextEngine.summon(Show, elem_type)
            class DerivedListShow(Show[List[Any]]):
                def show(self, values: List[Any]) -> str:
                    shown_elems = [elem_show.show(item) for item in values]
                    return "List(" + ", ".join(shown_elems) + ")"
            return DerivedListShow()

    return None

ContextEngine.register_deriver(derive_list_typeclasses)

# ==============================================================================
# Contextual Functions (Injecting 'using' instances)
# ==============================================================================
def summarize_ledger(items: List[T], item_type: type) -> T:
    """
    Scala 3 equivalent:
    def summarizeLedger[T: Monoid](items: List[T]): T =
        items.foldLeft(summon[Monoid[T]].empty)(_ combine _)
    """
    monoid_instance: Monoid[T] = ContextEngine.summon(Monoid, item_type)
    total = monoid_instance.empty()
    for item in items:
        total = monoid_instance.combine(total, item)
    return total

def print_audit_log(entity: T, entity_type: type) -> None:
    """
    Scala 3 equivalent:
    def printAuditLog[T](entity: T)(using s: Show[T], j: JsonEncoder[T]): Unit
    """
    show_instance: Show[T] = ContextEngine.summon(Show, entity_type)
    json_instance: JsonEncoder[T] = ContextEngine.summon(JsonEncoder, entity_type)

    print(f"  {Colors.CYAN}Readable:{Colors.RESET} {show_instance.show(entity)}")
    print(f"  {Colors.DIM}Payload :{Colors.RESET} {json_instance.encode(entity)}")

# ==============================================================================
# Execution Pipeline & Interactive Verification
# ==============================================================================
def run_lab() -> None:
    print(f"{Colors.HEADER}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD} LAB HANDS-ON: Scala 3 Contextual Abstractions & Type Classes Engine {Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}======================================================================{Colors.RESET}\n")

    time.sleep(0.2)
    print(f"{Colors.YELLOW}[Step 1] Initializing Domain Models & Contextual Registry...{Colors.RESET}")
    txns = [
        Transaction("TX-901", Money(1500.50, "USD"), "COMPLETED"),
        Transaction("TX-902", Money(2499.00, "USD"), "COMPLETED"),
        Transaction("TX-903", Money(450.75, "USD"), "PENDING"),
    ]
    print(f"Loaded {len(txns)} ledger transactions successfully.\n")

    # 1. Type Class Show & JsonEncoder via Extension Methods
    print(f"{Colors.YELLOW}[Step 2] Testing Extension Methods (Syntax Enrichment)...{Colors.RESET}")
    sample_money = Money(88500.0, "EUR")
    print(f"Target Object: {sample_money}")
    print(f"Invoking .show()   -> {Colors.GREEN}{extension(sample_money).show()}{Colors.RESET}")
    print(f"Invoking .to_json()-> {Colors.GREEN}{extension(sample_money).to_json()}{Colors.RESET}\n")

    # 2. Contextual Summoning in Polymorphic Functions
    print(f"{Colors.YELLOW}[Step 3] Context Bound Aggregation with Monoid[Money]...{Colors.RESET}")
    money_stream = [t.amount for t in txns]
    total_revenue = summarize_ledger(money_stream, Money)
    print(f"Summed items: {[extension(m).show() for m in money_stream]}")
    print(f"Result (Monoid.combine reduce) -> {Colors.BOLD}{Colors.GREEN}{extension(total_revenue).show()}{Colors.RESET}\n")

    # 3. Recursive Contextual Derivation (Synthesized Instances)
    print(f"{Colors.YELLOW}[Step 4] Recursive Instance Derivation: Synthesizing JsonEncoder[List[Transaction]]...{Colors.RESET}")
    list_txn_type = List[Transaction]
    print(f"Querying summon(JsonEncoder, List[Transaction])...")
    
    # Derivation terjadi on-the-fly karena tidak ada instance statis List[Transaction]
    list_encoder = ContextEngine.summon(JsonEncoder, list_txn_type)
    serialized_batch = list_encoder.encode(txns)
    print(f"{Colors.CYAN}Derived Serializer Output:{Colors.RESET}\n{serialized_batch}\n")

    # 4. Context Parameter Verification (Multi-typeclass constraints)
    print(f"{Colors.YELLOW}[Step 5] Context Parameter Injection (using Show[T], JsonEncoder[T])...{Colors.RESET}")
    for idx, txn in enumerate(txns, 1):
        print(f"Auditing Record #{idx}:")
        print_audit_log(txn, Transaction)

    # 5. Negative Test (Resolution Failure like Compiler Divergence/Missing Implicit)
    print(f"\n{Colors.YELLOW}[Step 6] Verifying Implicit Search Failure Guarantee...{Colors.RESET}")
    class UnsupportedData:
        pass

    try:
        ContextEngine.summon(Show, UnsupportedData)
    except TypeError as e:
        print(f"Caught Expected Ambiguity/Resolution Error:\n  {e}")

    print(f"\n{Colors.GREEN}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.GREEN}{Colors.BOLD} SUCCESS: Scala 3 Contextual Engine Emulation Executed Cleanly.      {Colors.RESET}")
    print(f"{Colors.GREEN}{Colors.BOLD}======================================================================{Colors.RESET}")

if __name__ == "__main__":
    run_lab()