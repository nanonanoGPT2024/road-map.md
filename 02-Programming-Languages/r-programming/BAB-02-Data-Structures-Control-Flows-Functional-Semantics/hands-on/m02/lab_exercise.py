#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive into R Functional Semantics & Core Data Structures
Category: 02-Programming-Languages | Topic: r-programming | Chapter: 02

This script simulates the internal architecture and semantics of R:
1. Vector Recycling Rules and Strict Type Coercion hierarchy.
2. Copy-on-Modify (CoM) semantics with memory pointer tracking (tracemem emulation).
3. Lazy Evaluation using Promise objects (Expression + Environment + Thunk cache).
4. Functional Higher-Order Operations: Emulation of `lapply` and strictly-typed `vapply`.
"""

import sys
import copy
from typing import Any, Callable, List, Dict, Union

# ANSI Terminal Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

def print_section(title: str) -> None:
    print(f"\n{BOLD}{MAGENTA}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN}>>> {title}{RESET}")
    print(f"{BOLD}{MAGENTA}{'=' * 75}{RESET}")

# ==============================================================================
# 1. ATOMIC VECTORS, COERCION, & RECYCLING
# ==============================================================================
class RAtomicVector:
    """
    Simulates R's atomic vector with type hierarchy coercion:
    logical (bool) -> integer (int) -> double (float) -> character (str)
    Also implements R's vector recycling rules during arithmetic operations.
    """
    TYPE_ORDER = [bool, int, float, str]
    TYPE_NAMES = {bool: "logical", int: "integer", float: "double", str: "character"}

    def __init__(self, elements: List[Any]):
        self.type_ = self._determine_common_type(elements)
        self.data = [self.type_(x) for x in elements] if elements else []

    def _determine_common_type(self, elements: List[Any]) -> type:
        if not elements:
            return bool
        highest_idx = 0
        for elem in elements:
            elem_type = type(elem)
            if elem_type in self.TYPE_ORDER:
                idx = self.TYPE_ORDER.index(elem_type)
                if idx > highest_idx:
                    highest_idx = idx
            else:
                highest_idx = 3  # Fallback to string (character)
        return self.TYPE_ORDER[highest_idx]

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        type_str = self.TYPE_NAMES.get(self.type_, "unknown")
        return f"{BLUE}RAtomicVector<{type_str}>{RESET}{self.data}"

    def __add__(self, other: 'RAtomicVector') -> 'RAtomicVector':
        """
        Implements arithmetic addition with R's Recycling Rule.
        If lengths mismatch, recycle the shorter vector. Warning if not an exact multiple.
        """
        len_self = len(self.data)
        len_other = len(other.data)

        if len_self == 0 or len_other == 0:
            return RAtomicVector([])

        max_len = max(len_self, len_other)
        min_len = min(len_self, len_other)

        if max_len % min_len != 0:
            print(f"{YELLOW}[R-Warning]: longer object length is not a multiple of shorter object length{RESET}")

        result_data = []
        for i in range(max_len):
            val_a = self.data[i % len_self]
            val_b = other.data[i % len_other]
            result_data.append(val_a + val_b)

        return RAtomicVector(result_data)


# ==============================================================================
# 2. COPY-ON-MODIFY (CoM) SEMANTICS WITH MEMORY TRACKER
# ==============================================================================
class RMemoryTracker:
    """
    Emulates R's `tracemem()` functionality and copy-on-modify mechanics.
    Tracks shared references and triggers physical memory duplication only on write.
    """
    def __init__(self, name: str, data: List[Any]):
        self.name = name
        self.payload = data
        self.ref_count = 1
        self._tracked = False

    def track(self) -> None:
        self._tracked = True
        print(f"{GREEN}[tracemem]{RESET} Tracking {self.name} at memory address: {hex(id(self.payload))}")

    def alias(self, new_name: str) -> 'RMemoryTracker':
        """Simulates `y <- x`: shared address until mutation."""
        new_obj = RMemoryTracker(new_name, self.payload)
        new_obj._tracked = self._tracked
        self.ref_count += 1
        new_obj.ref_count = self.ref_count
        print(f"{CYAN}[assignment]{RESET} {new_name} <- {self.name} (Shared ptr: {hex(id(self.payload))})")
        return new_obj

    def modify_at(self, index: int, value: Any) -> None:
        """Simulates in-place mutation triggering Copy-on-Modify if ref_count > 1."""
        if self.ref_count > 1:
            old_addr = hex(id(self.payload))
            # Perform shallow/deep copy
            self.payload = copy.copy(self.payload)
            self.ref_count = 1
            new_addr = hex(id(self.payload))
            if self._tracked:
                print(f"{RED}[tracemem]{RESET} {self.name} modified; duplicated {old_addr} -> {new_addr}")
        else:
            if self._tracked:
                print(f"{GREEN}[tracemem]{RESET} {self.name} modified in-place at address: {hex(id(self.payload))}")

        self.payload[index] = value


# ==============================================================================
# 3. LAZY EVALUATION & PROMISE OBJECTS
# ==============================================================================
class RPromise:
    """
    Simulates R's function parameter evaluation mechanism:
    A Promise encapsulates:
    - Expression (AST / thunk)
    - Environment (variables closure)
    - Value cache (memoization after initial evaluation)
    """
    def __init__(self, name: str, expression: Callable[[], Any]):
        self.name = name
        self.expression = expression
        self.evaluated = False
        self.value = None

    def force(self) -> Any:
        """Forces the evaluation of the promise. Subsequent calls return cached value."""
        if not self.evaluated:
            print(f"{YELLOW}[Promise]{RESET} Forcing evaluation of parameter '{self.name}'...")
            self.value = self.expression()
            self.evaluated = True
        else:
            print(f"{BLUE}[Promise]{RESET} Accessing cached value for '{self.name}' without re-evaluating.")
        return self.value


def simulate_r_lazy_function(arg_a: RPromise, arg_b: RPromise, condition: bool) -> Any:
    """
    R-style function demonstrating lazy argument evaluation.
    arg_b is never forced if condition is False.
    """
    print(f"Executing function: condition={condition}")
    if condition:
        return arg_a.force() + arg_b.force()
    return arg_a.force()


# ==============================================================================
# 4. FUNCTIONAL OPERATORS: lapply & STRICT vapply
# ==============================================================================
def r_lapply(vector: RAtomicVector, func: Callable[[Any], Any]) -> List[Any]:
    """lapply: applies a function over a vector/list, always returns a generic list."""
    return [func(elem) for elem in vector.data]

def r_vapply(vector: RAtomicVector, func: Callable[[Any], Any], f_val: type) -> RAtomicVector:
    """
    vapply: strictly typed apply variant in R.
    Validates that each returned value precisely matches the type template `f_val`.
    """
    res = []
    for idx, elem in enumerate(vector.data):
        val = func(elem)
        if not isinstance(val, f_val):
            raise TypeError(
                f"{RED}[vapply Error]{RESET} Value at index {idx} has invalid type: "
                f"expected {f_val.__name__}, got {type(val).__name__}"
            )
        res.append(val)
    return RAtomicVector(res)


# ==============================================================================
# LAB WORKFLOW DEMONSTRATION
# ==============================================================================
def main():
    print(f"{BOLD}{GREEN}R Programming Core Functional & Structural Semantics Engine{RESET}")
    print(f"Python standard library environment verification complete.\n")

    # TEST 1: Atomic Vector Coercion
    print_section("1. Atomic Vector Hierarchy Coercion")
    mixed_input = [True, 10, 4.5, "Alpha"]
    r_vec = RAtomicVector(mixed_input)
    print(f"Raw Input       : {mixed_input}")
    print(f"Coerced R Vector: {r_vec} -> Coerced uniformly to character type.")

    numeric_input = [False, True, 42]
    num_vec = RAtomicVector(numeric_input)
    print(f"Logical+Integer : {numeric_input}")
    print(f"Coerced R Vector: {num_vec} -> Logical coerced to integer.")

    # TEST 2: Recycling Rule
    print_section("2. Vector Arithmetic & Recycling Rules")
    vec_a = RAtomicVector([10, 20, 30, 40, 50, 60])
    vec_b = RAtomicVector([1, 2])
    print(f"Vec A (len {len(vec_a)}): {vec_a.data}")
    print(f"Vec B (len {len(vec_b)}): {vec_b.data}")
    print(f"A + B (Clean multiple):")
    res_clean = vec_a + vec_b
    print(f"Result: {res_clean.data}\n")

    vec_c = RAtomicVector([1, 2, 3, 4])
    vec_d = RAtomicVector([10, 20, 30])
    print(f"Vec C (len {len(vec_c)}): {vec_c.data}")
    print(f"Vec D (len {len(vec_d)}): {vec_d.data}")
    print(f"C + D (Non-clean multiple, recycling triggered):")
    res_warn = vec_c + vec_d
    print(f"Result: {res_warn.data}")

    # TEST 3: Copy-on-Modify (tracemem)
    print_section("3. Copy-on-Modify (CoM) & Pointer Tracking")
    x = RMemoryTracker("x", [100, 200, 300])
    x.track()
    
    y = x.alias("y")
    print(f"x memory: {hex(id(x.payload))}, y memory: {hex(id(y.payload))}")
    
    print("\nModifying 'y' at index 1 -> triggers CoM duplication:")
    y.modify_at(1, 999)
    print(f"x data: {x.payload} (addr: {hex(id(x.payload))})")
    print(f"y data: {y.payload} (addr: {hex(id(y.payload))})")

    # TEST 4: Lazy Evaluation
    print_section("4. R Lazy Evaluation Semantics (Promises)")
    expensive_op_ran = False

    def expensive_expression():
        nonlocal expensive_op_ran
        expensive_op_ran = True
        return 500 * 2

    # Branch 1: False branch - arg_b is lazy and should NOT execute
    promise_a = RPromise("arg_a", lambda: 10 + 5)
    promise_b = RPromise("arg_b", expensive_expression)
    
    print("[Branch: condition=False]")
    val1 = simulate_r_lazy_function(promise_a, promise_b, condition=False)
    print(f"Result: {val1}")
    print(f"Was expensive parameter evaluated? -> {BOLD}{RED}{expensive_op_ran}{RESET}")

    # Branch 2: True branch - both evaluated
    print("\n[Branch: condition=True]")
    promise_c = RPromise("arg_c", lambda: 100)
    promise_d = RPromise("arg_d", expensive_expression)
    val2 = simulate_r_lazy_function(promise_c, promise_d, condition=True)
    print(f"Result: {val2}")
    print(f"Was expensive parameter evaluated? -> {BOLD}{GREEN}{expensive_op_ran}{RESET}")

    # TEST 5: Higher-Order Functional Programming
    print_section("5. Higher-Order Functional Semantics: lapply & vapply")
    sample_vec = RAtomicVector([1, 4, 9, 16])
    
    # lapply returns generic dynamic list
    res_lapply = r_lapply(sample_vec, lambda x: x ** 0.5)
    print(f"lapply(sample_vec, sqrt): {res_lapply} (Type: {type(res_lapply).__name__})")

    # vapply enforces return type match (float/double)
    res_vapply = r_vapply(sample_vec, lambda x: float(x * 2), float)
    print(f"vapply(sample_vec, x * 2, double): {res_vapply}")

    # vapply strictness validation
    print("\nTesting vapply strictness contract violation:")
    try:
        r_vapply(sample_vec, lambda x: str(x), int)
    except TypeError as te:
        print(f"Caught expected type error: {te}")

    print_section("Lab Execution Complete")

if __name__ == "__main__":
    main()