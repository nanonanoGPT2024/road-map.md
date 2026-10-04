#!/usr/bin/env python3
"""
Lab Exercise: C# Modern Type System & OOP Kontemporer (Modul 02 Deep Dive)
Simulasi Arsitektur Type System C#:
 1. Value Type (struct / stack) vs Reference Type (class / managed heap).
 2. C# Records: Value Equality & Non-Destructive Mutation (with-expressions).
 3. Pattern Matching Engine: Type patterns, Property patterns, Relational patterns.
"""

from __future__ import annotations
import copy
import dataclasses
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable
from enum import Enum
import time

# --- ANSI Color Codes ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"

# ============================================================================
# 1. SIMULASI MEMORI RUNTIME (Stack vs Managed Heap Semantics)
# ============================================================================

class AllocationKind(Enum):
    STACK_VALUE_TYPE = "Stack (Value Copy)"
    HEAP_REF_TYPE = "Heap (Reference Pointer)"

class MemorySimulator:
    """
    Simulasi alokasi memori CLR (Common Language Runtime).
    Menunjukkan perbedaan mutasi pada C# struct vs C# class.
    """
    def __init__(self):
        self._heap_storage: Dict[int, Any] = {}
        self._next_heap_addr = 0x1000

    def allocate_heap(self, payload: Any) -> int:
        addr = self._next_heap_addr
        self._heap_storage[addr] = payload
        self._next_heap_addr += 0x08
        return addr

    def dereference(self, addr: int) -> Any:
        return self._heap_storage.get(addr)

    def write_heap(self, addr: int, payload: Any) -> None:
        if addr in self._heap_storage:
            self._heap_storage[addr] = payload

class CSharpStruct:
    """Basis representasi C# Value Type (struct). Ditransmisikan via pass-by-value."""
    def copy_value(self) -> CSharpStruct:
        return copy.deepcopy(self)

class PointStruct(CSharpStruct):
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"PointStruct(x={self.x}, y={self.y})"

class EntityRef:
    """Basis representasi C# Reference Type (class). Ditransmisikan via pointer reference."""
    def __init__(self, name: str, level: int):
        self.name = name
        self.level = level

    def __repr__(self) -> str:
        return f"EntityRef(name='{self.name}', level={self.level})"

# ============================================================================
# 2. SIMULASI C# RECORDS (Immutable Data & Value Equality)
# ============================================================================

class RecordBase:
    """
    Simulasi C# 'record class' / 'record struct'.
    Menyediakan sintaksis modifikasi non-destruktif 'with' dan equality berbasis nilai.
    """
    def with_mutation(self, **kwargs) -> Any:
        """Emulasi operator 'with' pada C# 9.0+."""
        cloned = copy.deepcopy(self)
        for key, value in kwargs.items():
            if not hasattr(cloned, key):
                raise AttributeError(f"Field '{key}' tidak ditemukan di record {self.__class__.__name__}")
            setattr(cloned, key, value)
        return cloned

    def __eq__(self, other: Any) -> bool:
        """Record equality di C# didasarkan pada perbandingan nilai tiap field."""
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))

@dataclass(frozen=True)
class OrderRecord(RecordBase):
    order_id: str
    symbol: str
    price: float
    quantity: int
    is_settled: bool

# ============================================================================
# 3. ADVANCED PATTERN MATCHING ENGINE
# ============================================================================

class PatternMatcher:
    """
    Engine untuk mengevaluasi switch expression kontemporer C#.
    Mendukung Type, Property, dan Relational Patterns.
    """
    @staticmethod
    def evaluate_order_risk(order: Any) -> Tuple[str, str]:
        """
        Simulasi C# 9+ switch expression:
        order switch {
            OrderRecord { price: > 1000.0, quantity: > 100 } => ("HIGH", ...),
            OrderRecord { is_settled: true }                  => ("NONE", ...),
            OrderRecord { quantity: <= 0 }                    => ("INVALID", ...),
            EntityRef e                                       => ("UNSUPPORTED_TYPE", ...),
            null                                              => ("NULL_ARGUMENT", ...),
            _                                                 => ("STANDARD", ...)
        }
        """
        # Null check pattern
        if order is None:
            return ("NULL_REFERENCE", "Null parameter tidak diperbolehkan (Nullable Reference Types Violation).")

        # Type & Property pattern matching
        if isinstance(order, OrderRecord):
            # Property + Relational Pattern: price > 1000.0 and quantity > 100
            if order.price > 1000.0 and order.quantity > 100:
                return ("CRITICAL_RISK", f"Volume & Notional Tinggi: {order.quantity} @ ${order.price:.2f}")

            # Property Pattern: is_settled == True
            if order.is_settled:
                return ("ZERO_RISK", "Order telah diselesaikan sebelumnya.")

            # Relational Pattern: quantity <= 0
            if order.quantity <= 0:
                return ("REJECTED", f"Quantity order tidak valid: {order.quantity}")

            # Relational Pattern: standard range
            if 0 < order.quantity <= 100:
                return ("LOW_RISK", f"Eksekusi ritel standar: {order.symbol}")

            return ("MEDIUM_RISK", f"Order institusi moderate: {order.symbol} (${order.price:.2f})")

        # Type Pattern fallback
        if isinstance(order, EntityRef):
            return ("TYPE_MISMATCH", f"Objek EntityRef('{order.name}') bukan OrderRecord.")

        # Discard pattern '_'
        return ("UNKNOWN", "Pola objek tidak dikenali oleh matcher engine.")

# ============================================================================
# LAB HARNESS & DEMONSTRATION RUNNER
# ============================================================================

def run_value_vs_reference_lab(mem: MemorySimulator) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== [1] VALUE TYPES (struct) VS REFERENCE TYPES (class) ==={CLR_RESET}")
    
    # 1. Value Type Semantics
    print(f"{CLR_YELLOW}1.1 Demonstrasi C# Value Type (struct Point):{CLR_RESET}")
    val_a = PointStruct(10, 20)
    val_b = val_a.copy_value() # Simulasi push copy ke frame call stack
    val_b.x = 999

    print(f"  Origin val_a: {val_a} (Address: Stack Frame Variable A)")
    print(f"  Copied val_b: {val_b} (Address: Stack Frame Variable B)")
    assert val_a.x == 10, "Value isolation violation!"
    print(f"  {CLR_GREEN}✔ Mutation pada copy TIDAK berdampak ke origin (True Stack Isolation){CLR_RESET}")

    # 2. Reference Type Semantics
    print(f"\n{CLR_YELLOW}1.2 Demonstrasi C# Reference Type (class Entity):{CLR_RESET}")
    heap_obj = EntityRef("Player_1", level=1)
    addr = mem.allocate_heap(heap_obj)

    # Reference variables memegang pointer alamat yang sama
    ref_a_addr = addr
    ref_b_addr = addr

    print(f"  Pointer Variable ref_a -> Heap Address 0x{ref_a_addr:X}")
    print(f"  Pointer Variable ref_b -> Heap Address 0x{ref_b_addr:X}")

    target: EntityRef = mem.dereference(ref_b_addr)
    target.level = 88 # Mutasi melalui salah satu alias reference
    
    inspected_origin: EntityRef = mem.dereference(ref_a_addr)
    print(f"  Diverifikasi via ref_a: {inspected_origin}")
    assert inspected_origin.level == 88, "Reference alias mutation failed!"
    print(f"  {CLR_GREEN}✔ Mutasi via pointer merubah payload bersama pada Managed Heap{CLR_RESET}")

def run_records_immutability_lab() -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== [2] C# MODERN RECORDS & NON-DESTRUCTIVE MUTATION ==={CLR_RESET}")
    
    order1 = OrderRecord("ORD-890", "MSFT", 420.50, 150, False)
    
    # Value equality check
    order1_duplicate = OrderRecord("ORD-890", "MSFT", 420.50, 150, False)
    print(f"  Instans Record 1: {order1}")
    print(f"  Instans Record 2: {order1_duplicate}")
    
    is_value_equal = (order1 == order1_duplicate)
    is_ref_identical = (order1 is order1_duplicate)
    print(f"  Structural Value Equality (order1 == order2) : {CLR_GREEN}{is_value_equal}{CLR_RESET}")
    print(f"  Reference Identity        (order1 is order2) : {CLR_RED}{is_ref_identical}{CLR_RESET}")

    # Non-destructive mutation (C# 'with' expression)
    print(f"\n{CLR_YELLOW}2.1 Mutasi Non-Destruktif (simulasi: var order2 = order1 with {{ ... }}):{CLR_RESET}")
    order2 = order1.with_mutation(quantity=200, is_settled=True)
    
    print(f"  Original (Immutable): {order1}")
    print(f"  Mutated  (Clone)    : {order2}")
    assert order1.quantity == 150, "Original record terbukti termediasi / mutable!"
    assert order2.quantity == 200, "With mutation gagal mengupdate clone target!"
    print(f"  {CLR_GREEN}✔ Original data utuh; New Record dialokasikan secara atomik{CLR_RESET}")

def run_pattern_matching_lab() -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== [3] C# SWITCH EXPRESSION & PATTERN MATCHING ENGINE ==={CLR_RESET}")

    test_matrix = [
        OrderRecord("ORD-1", "AAPL", 1500.0, 500, False), # High risk: price > 1000 & qty > 100
        OrderRecord("ORD-2", "NVDA", 850.0, 50, False),   # Low risk: qty <= 100
        OrderRecord("ORD-3", "TSLA", 250.0, 0, False),    # Relational: qty <= 0
        OrderRecord("ORD-4", "GOOG", 180.0, 150, True),   # Property: is_settled == True
        EntityRef("NonCompatiblePayload", 99),             # Type Pattern match
        None                                              # Null safety check
    ]

    for idx, item in enumerate(test_matrix, 1):
        category, reason = PatternMatcher.evaluate_order_risk(item)
        print(f"  Case #{idx:02d} | Input: {str(item):<48} -> [{CLR_MAGENTA}{category:<16}{CLR_RESET}] {CLR_BLUE}{reason}{CLR_RESET}")

def main() -> None:
    print(f"{CLR_BOLD}{CLR_GREEN}===================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}  LABORATORIUM: MODERN TYPE SYSTEM & OOP KONTEMPORER (C# ENGINE)     {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}===================================================================={CLR_RESET}")
    
    start_time = time.perf_counter()
    mem = MemorySimulator()
    
    run_value_vs_reference_lab(mem)
    run_records_immutability_lab()
    run_pattern_matching_lab()
    
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ Seluruh spesifikasi type-safety berhasil divalidasi ({elapsed_ms:.2f} ms).{CLR_RESET}\n")

if __name__ == "__main__":
    main()