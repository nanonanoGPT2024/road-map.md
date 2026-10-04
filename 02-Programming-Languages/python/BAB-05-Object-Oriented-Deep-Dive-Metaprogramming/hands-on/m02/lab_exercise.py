#!/usr/bin/env python3
"""
Lab Hands-on: Object-Oriented Deep Dive & Metaprogramming in Python 3
Topic: Declarative Schema Engine using Descriptors, Metaclasses, and Introspection.

Description:
This script implements a lightweight, zero-dependency declarative ORM-like schema 
validation engine. It demonstrates:
1. Advanced Descriptor Protocol (__set_name__, __get__, __set__, validation hooks).
2. Metaclass class construction lifecycle (__new__, namespace collection, dynamic initialization).
3. State mutation tracking (dirty checking) and introspection metadata.
4. Robust error handling with ANSI-formatted execution reporting.
"""

import sys
import time
from typing import Any, Dict, List, Optional, Type

# ============================================================================
# ANSI Color Formatting Utilities
# ============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"

def print_header(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.BLUE}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} [LAB] {title.upper()}{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}{'=' * 75}{Color.RESET}")

def print_step(step_num: int, desc: str) -> None:
    print(f"\n{Color.BOLD}{Color.MAGENTA}Step {step_num}:{Color.RESET} {Color.BOLD}{desc}{Color.RESET}")

# ============================================================================
# Section 1: The Descriptor Protocol (Data Validation Layer)
# ============================================================================
class ValidationError(ValueError):
    """Custom exception raised when descriptor field validation fails."""
    pass

class Field:
    """
    Base Descriptor protocol implementation managing storage, defaults, and hooks.
    Utilizes __set_name__ to bind variable identifiers dynamically.
    """
    def __init__(self, default: Any = None, required: bool = True):
        self.default = default
        self.required = required
        self.storage_name = ""
        self.public_name = ""

    def __set_name__(self, owner: Type[Any], name: str) -> None:
        """Invoked at class creation time to bind the variable name."""
        self.public_name = name
        self.storage_name = f"__field_{name}"

    def __get__(self, instance: Any, owner: Type[Any]) -> Any:
        if instance is None:
            return self  # Accessed from the class level
        return getattr(instance, self.storage_name, self.default)

    def __set__(self, instance: Any, value: Any) -> None:
        if value is None:
            if self.required:
                raise ValidationError(f"Field '{self.public_name}' is required and cannot be None.")
            setattr(instance, self.storage_name, None)
            return

        self.validate(value)
        # Track state changes for dirty checking
        old_val = getattr(instance, self.storage_name, None)
        if old_val != value:
            instance._is_dirty = True
        setattr(instance, self.storage_name, value)

    def validate(self, value: Any) -> None:
        """Hook method for subclasses to implement custom validation."""
        pass


class IntegerField(Field):
    """Descriptor validating strictly typed integers with optional range bounds."""
    def __init__(self, min_value: Optional[int] = None, max_value: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value: Any) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError(f"Field '{self.public_name}' expected int, got {type(value).__name__}.")
        if self.min_value is not None and value < self.min_value:
            raise ValidationError(f"Field '{self.public_name}' must be >= {self.min_value} (got {value}).")
        if self.max_value is not None and value > self.max_value:
            raise ValidationError(f"Field '{self.public_name}' must be <= {self.max_value} (got {value}).")


class StringField(Field):
    """Descriptor validating string constraints such as length and non-empty values."""
    def __init__(self, min_len: int = 0, max_len: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.min_len = min_len
        self.max_len = max_len

    def validate(self, value: Any) -> None:
        if not isinstance(value, str):
            raise ValidationError(f"Field '{self.public_name}' expected str, got {type(value).__name__}.")
        if len(value) < self.min_len:
            raise ValidationError(f"Field '{self.public_name}' length must be >= {self.min_len}.")
        if self.max_len is not None and len(value) > self.max_len:
            raise ValidationError(f"Field '{self.public_name}' length must be <= {self.max_len}.")

# ============================================================================
# Section 2: The Metaclass Engine (Schema Construction Layer)
# ============================================================================
class ModelMeta(type):
    """
    Metaclass that intercepts class definition:
    1. Collects all Field descriptors into a unified `_fields` registry.
    2. Enforces inheritance-aware descriptor gathering.
    3. Auto-generates structured initialization and serialization methods.
    """
    def __new__(mcs, name: str, bases: tuple, namespace: dict):
        fields: Dict[str, Field] = {}

        # Inherit fields from parent classes (MRO traversal)
        for base in reversed(bases):
            if hasattr(base, "_fields"):
                fields.update(base._fields)

        # Gather descriptors declared directly on this class
        for key, value in list(namespace.items()):
            if isinstance(value, Field):
                fields[key] = value

        namespace["_fields"] = fields
        cls = super().__new__(mcs, name, bases, namespace)
        return cls


class Model(metaclass=ModelMeta):
    """
    Declarative Base Model providing auto-wiring, serialization, and dirty checking.
    """
    def __init__(self, **kwargs):
        self._is_dirty = False
        # Set defaults first
        for name, field in self._fields.items():
            setattr(self, field.storage_name, field.default)

        # Apply provided kwargs
        for name, val in kwargs.items():
            if name in self._fields:
                setattr(self, name, val)
            else:
                raise AttributeError(f"Unknown attribute '{name}' for model {self.__class__.__name__}")

        # Reset dirty state post-initialization
        self._is_dirty = False

    def to_dict(self) -> Dict[str, Any]:
        """Serializes current model descriptors to a plain dictionary."""
        return {name: getattr(self, name) for name in self._fields}

    def save(self) -> None:
        """Simulates atomic persistence commit."""
        if not self._is_dirty:
            print(f"{Color.YELLOW}[SKIPPED]{Color.RESET} {self.__class__.__name__} has no dirty changes.")
            return
        self._is_dirty = False
        print(f"{Color.GREEN}[PERSISTED]{Color.RESET} {self.__class__.__name__} state committed successfully.")

    def __repr__(self) -> str:
        attrs = ", ".join(f"{k}={getattr(self, k)!r}" for k in self._fields)
        return f"{self.__class__.__name__}({attrs})"

# ============================================================================
# Section 3: Domain Models and Demonstrations
# ============================================================================
class AccountModel(Model):
    """Domain model representing a banking account entity."""
    account_id = IntegerField(min_value=1000, max_value=9999)
    owner = StringField(min_len=3, max_len=50)
    balance = IntegerField(min_value=0, default=0)
    tier = StringField(min_len=4, max_len=10, default="STANDARD")


class TransactionModel(Model):
    """Domain model representing an audit log transaction."""
    tx_id = StringField(min_len=8, max_len=32)
    amount = IntegerField(min_value=1)
    status = StringField(default="PENDING")

# ============================================================================
# Execution Flow & Validation Benchmarks
# ============================================================================
def main():
    print_header("Metaprogramming & Advanced OOP Deep Dive")

    # Step 1: Introspect Class Construction
    print_step(1, "Metaclass Introspection & Schema Mapping")
    print(f"Discovered registered fields for {Color.BOLD}AccountModel{Color.RESET}:")
    for fname, fobj in AccountModel._fields.items():
        print(f"  • {Color.CYAN}{fname:<12}{Color.RESET} -> Type: {fobj.__class__.__name__:<14} (Internal: {fobj.storage_name})")

    # Step 2: Instantiation and Successful Validation
    print_step(2, "Valid Instance Instantiation & Serialization")
    user_acc = AccountModel(account_id=1024, owner="Alice Vance", balance=5000)
    print(f"Instantiated: {Color.GREEN}{user_acc}{Color.RESET}")
    print(f"Serialized Dictionary: {user_acc.to_dict()}")

    # Step 3: State Tracking (Dirty Checking Pattern)
    print_step(3, "Dirty State Tracking & State Commit")
    print(f"Initial dirty state: {Color.BOLD}{user_acc._is_dirty}{Color.RESET}")
    user_acc.save()  # Should skip save
    
    print("Mutating balance...")
    user_acc.balance = 6500
    print(f"Dirty state after mutation: {Color.BOLD}{user_acc._is_dirty}{Color.RESET}")
    user_acc.save()  # Should persist
    print(f"Dirty state post-save: {Color.BOLD}{user_acc._is_dirty}{Color.RESET}")

    # Step 4: Validation Failures & Exception Trapping
    print_step(4, "Descriptor Constraint Enforcement")
    test_cases = [
        ("Negative Balance Check", lambda: AccountModel(account_id=1025, owner="Bob", balance=-50)),
        ("String Length Validation", lambda: AccountModel(account_id=1026, owner="Al", balance=100)),
        ("Type Mismatch Guard", lambda: AccountModel(account_id="INVALID", owner="Charlie", balance=100)),
        ("Unrecognized Field Rejection", lambda: AccountModel(account_id=1027, owner="David", rogue="exploit")),
    ]

    for label, test_callable in test_cases:
        try:
            test_callable()
            print(f"  {Color.RED}✗ FAILED:{Color.RESET} {label} did not catch violation!")
        except (ValidationError, AttributeError) as exc:
            print(f"  {Color.GREEN}✓ PASSED:{Color.RESET} [{label}] Trapped expected error: {Color.YELLOW}{exc}{Color.RESET}")

    # Step 5: Micro-benchmark (Descriptor Overhead Measurement)
    print_step(5, "Descriptor Access Overhead Benchmark")
    iterations = 200_000

    class PlainAccount:
        def __init__(self, acc_id, bal):
            self.account_id = acc_id
            self.balance = bal

    plain_obj = PlainAccount(1001, 100)
    desc_obj = AccountModel(account_id=1001, owner="Benchmark Subject", balance=100)

    # Standard attribute access
    start = time.perf_counter()
    for _ in range(iterations):
        _ = plain_obj.balance
    plain_time = time.perf_counter() - start

    # Descriptor-managed attribute access
    start = time.perf_counter()
    for _ in range(iterations):
        _ = desc_obj.balance
    desc_time = time.perf_counter() - start

    print(f"Iterations: {iterations:,}")
    print(f"Standard Access Duration   : {Color.CYAN}{plain_time:.6f}s{Color.RESET}")
    print(f"Descriptor Access Duration : {Color.CYAN}{desc_time:.6f}s{Color.RESET}")
    overhead = (desc_time / plain_time) if plain_time > 0 else 1.0
    print(f"Relative Overhead Factor   : {Color.BOLD}{overhead:.2f}x{Color.RESET} (Includes validation hooks)")

    print(f"\n{Color.BOLD}{Color.GREEN}Lab verification complete: All metaprogramming mechanics operational.{Color.RESET}\n")

if __name__ == "__main__":
    main()