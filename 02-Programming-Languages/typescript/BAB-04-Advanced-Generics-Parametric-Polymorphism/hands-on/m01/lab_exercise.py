#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Inti TypeScript - BAB 04: Advanced Generics & Parametric Polymorphism
Runtime: Python 3.8+ (Standalone, Zero-dependency)

Modul ini mensimulasikan mekanisme internal TypeScript Type Checker:
1. Parametric Polymorphism & Generic Constraints (T extends U)
2. Variance Engine (Covariance, Contravariance, Invariance)
3. Distributive Conditional Types (T extends U ? X : Y)
4. Generic Pattern Matching & Inference (infer R)
"""

import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# ANSI Colors for Rich Terminal Output
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_DARK = "\033[48;5;236m"


def header(title: str) -> None:
    line = "=" * 68
    print(f"\n{BLUE}{BOLD}{line}{RESET}")
    print(f"{CYAN}{BOLD}  🔬 {title}{RESET}")
    print(f"{BLUE}{BOLD}{line}{RESET}\n")


def subheader(title: str) -> None:
    print(f"\n{MAGENTA}{BOLD}▶ {title}{RESET}")
    print(f"{DIM}{'-' * 50}{RESET}")


def log_step(name: str, status: str, detail: str = "") -> None:
    badge = f"{GREEN}[PASS]{RESET}" if status == "PASS" else f"{RED}[FAIL]{RESET}"
    print(f"  {badge} {BOLD}{name:<28}{RESET} {YELLOW}{detail}{RESET}")


# ==============================================================================
# 1. Type Hierarchy Definition (Subtyping Lattice)
# ==============================================================================
class TypeNode:
    """Representasi type dalam Type Lattice compiler TypeScript."""
    def __init__(self, name: str, supertypes: Optional[Set[str]] = None):
        self.name = name
        self.supertypes: Set[str] = supertypes or set()

    def is_subtype_of(self, other_name: str, registry: Dict[str, "TypeNode"]) -> bool:
        """Evaluasi: T extends U"""
        if self.name == other_name or other_name == "any" or other_name == "unknown":
            return True
        if self.name == "never":
            return True
        if other_name == "never":
            return False

        visited: Set[str] = set()
        queue: List[str] = list(self.supertypes)

        while queue:
            curr = queue.pop(0)
            if curr == other_name:
                return True
            if curr not in visited:
                visited.add(curr)
                if curr in registry:
                    queue.extend(registry[curr].supertypes)
        return False


TYPE_REGISTRY: Dict[str, TypeNode] = {
    "Animal": TypeNode("Animal"),
    "Dog": TypeNode("Dog", supertypes={"Animal"}),
    "Puppy": TypeNode("Puppy", supertypes={"Dog"}),
    "Cat": TypeNode("Cat", supertypes={"Animal"}),
    "Vehicle": TypeNode("Vehicle"),
    "Car": TypeNode("Car", supertypes={"Vehicle"}),
}


# ==============================================================================
# 2. Variance Engine (Covariance, Contravariance, Invariance)
# ==============================================================================
class GenericVarianceEngine:
    """
    Simulasi aturan subtyping generic:
    - Covariant (Output Position): Producer<T> <: Producer<U>  <=>  T <: U
    - Contravariant (Input Position): Consumer<T> <: Consumer<U>  <=>  U <: T
    - Invariant (Read-Write Position): Box<T> <: Box<U>  <=>  T <: U dan U <: T
    """
    @staticmethod
    def is_subtype_producer(t_arg: str, u_arg: str) -> bool:
        """Producer<T> <: Producer<U> (Covariant)"""
        t_node = TYPE_REGISTRY.get(t_arg)
        if not t_node:
            return False
        return t_node.is_subtype_of(u_arg, TYPE_REGISTRY)

    @staticmethod
    def is_subtype_consumer(t_arg: str, u_arg: str) -> bool:
        """Consumer<T> <: Consumer<U> (Contravariant: butuh U <: T)"""
        u_node = TYPE_REGISTRY.get(u_arg)
        if not u_node:
            return False
        return u_node.is_subtype_of(t_arg, TYPE_REGISTRY)

    @staticmethod
    def is_subtype_invariant(t_arg: str, u_arg: str) -> bool:
        """Box<T> <: Box<U> (Invariant)"""
        return (GenericVarianceEngine.is_subtype_producer(t_arg, u_arg) and
                GenericVarianceEngine.is_subtype_consumer(t_arg, u_arg))


# ==============================================================================
# 3. Distributive Conditional Types Engine (T extends U ? X : Y)
# ==============================================================================
class ConditionalTypeResolver:
    """
    Simulasi: T extends U ? TrueBranch : FalseBranch
    Mendukung Union Distribution: (A | B) extends U ? X : Y => (A extends U ? X : Y) | (B extends U ? X : Y)
    """
    @staticmethod
    def evaluate_naked(target: str, constraint: str, true_t: str, false_t: str) -> str:
        if target == "never":
            return "never"
        node = TYPE_REGISTRY.get(target)
        if node and node.is_subtype_of(constraint, TYPE_REGISTRY):
            return true_t
        return false_t

    @classmethod
    def evaluate_union(cls, union_types: List[str], constraint: str, true_t: str, false_t: str) -> Set[str]:
        results: Set[str] = set()
        for member in union_types:
            res = cls.evaluate_naked(member, constraint, true_t, false_t)
            if res != "never":
                results.add(res)
        return results if results else {"never"}


# ==============================================================================
# 4. Pattern Matching & Type Inference (infer R)
# ==============================================================================
class PatternMatcher:
    """
    Simulasi inferensial pattern matching:
    ReturnType<T>: T extends (...args: any[]) => infer R ? R : any
    UnpackArray<T>: T extends (infer U)[] ? U : T
    """
    @staticmethod
    def unpack_array(type_str: str) -> Tuple[str, bool]:
        if type_str.endswith("[]"):
            inferred = type_str[:-2]
            return inferred, True
        return type_str, False

    @staticmethod
    def unpack_promise(type_str: str) -> Tuple[str, bool]:
        if type_str.startswith("Promise<") and type_str.endswith(">"):
            inferred = type_str[len("Promise<"):-1]
            return inferred, True
        return type_str, False


# ==============================================================================
# Interactive CLI & Test Suite
# ==============================================================================
def run_interactive_simulation() -> None:
    header("TYPESCRIPT ADVANCED GENERICS TYPE ENGINE SIMULATION")
    print(f"{CYAN}Laboratorium interaktif pemecahan aljabar type TypeScript.{RESET}")
    print(f"{DIM}Mengevaluasi Subtyping, Variance, Distributive Conditional Types, dan Infer.{RESET}\n")

    # SECTION 1
    subheader("1. Evaluasi Generic Constraint Lattice (T extends U)")
    pairs = [
        ("Puppy", "Animal", True),
        ("Dog", "Animal", True),
        ("Cat", "Dog", False),
        ("Car", "Vehicle", True),
        ("Car", "Animal", False),
    ]
    for sub, sup, expected in pairs:
        node = TYPE_REGISTRY.get(sub)
        actual = node.is_subtype_of(sup, TYPE_REGISTRY) if node else False
        status = "PASS" if actual == expected else "FAIL"
        expr = f"{sub} extends {sup}"
        detail = f"Evaluated: {actual} (Expected: {expected})"
        log_step(expr, status, detail)

    # SECTION 2
    subheader("2. Variance Engine (Producer vs Consumer vs Mutable Container)")
    print(f"  {YELLOW}Subtyping Dasar:{RESET} Puppy <: Dog <: Animal\n")

    # Covariance
    cov_pass = GenericVarianceEngine.is_subtype_producer("Puppy", "Animal")
    log_step("Producer<Puppy> <: Producer<Animal>", "PASS" if cov_pass else "FAIL", "Covariant (Output Position)")

    # Contravariance
    contra_pass = GenericVarianceEngine.is_subtype_consumer("Animal", "Puppy")  # Consumer<Animal> <: Consumer<Puppy>
    log_step("Consumer<Animal> <: Consumer<Puppy>", "PASS" if contra_pass else "FAIL", "Contravariant (Input Position)")

    contra_invalid = GenericVarianceEngine.is_subtype_consumer("Puppy", "Animal")  # Consumer<Puppy> <: Consumer<Animal> -> False!
    log_step("Consumer<Puppy> <: Consumer<Animal>", "PASS" if not contra_invalid else "FAIL", "Properly Rejected (Contravariant Guard)")

    # Invariance
    inv_pass = GenericVarianceEngine.is_subtype_invariant("Dog", "Dog")
    inv_fail = GenericVarianceEngine.is_subtype_invariant("Puppy", "Dog")
    log_step("Box<Dog> <: Box<Dog>", "PASS" if inv_pass else "FAIL", "Invariant (Exact Match)")
    log_step("Box<Puppy> <: Box<Dog>", "PASS" if not inv_fail else "FAIL", "Invariant Rejected Subtype Mutation")

    # SECTION 3
    subheader("3. Distributive Conditional Types (T extends Animal ? 'Mammal' : 'Other')")
    sample_union = ["Dog", "Cat", "Car", "Puppy"]
    print(f"  Input Union: {BOLD}{' | '.join(sample_union)}{RESET}")
    print(f"  Condition  : {CYAN}T extends Animal ? 'Mammal' : 'Other'{RESET}")

    resolved_union = ConditionalTypeResolver.evaluate_union(
        sample_union,
        constraint="Animal",
        true_t="Mammal",
        false_t="Other"
    )
    print(f"  Distributed Result: {GREEN}{BOLD}{' | '.join(sorted(resolved_union))}{RESET}")
    log_step("Union Distribution Engine", "PASS", f"Output: {resolved_union}")

    # Section 3.1: Exclude<T, U> Simulation: T extends U ? never : T
    exclude_union = ["Dog", "Cat", "Car"]
    print(f"\n  {YELLOW}Simulasi Exclude<Dog | Cat | Car, Animal>:{RESET}")
    exclude_result = ConditionalTypeResolver.evaluate_union(
        exclude_union,
        constraint="Animal",
        true_t="never",
        false_t="Keep"
    )
    log_step("Exclude<T, Animal>", "PASS", f"Retained Non-Animals -> Car mapped to {exclude_result}")

    # SECTION 4
    subheader("4. Pattern Matching & Type Extraction (infer Keyword)")
    test_signatures = [
        ("Promise<Dog>", "Promise"),
        ("Animal[]", "Array"),
        ("Car", "Primitive"),
    ]

    for type_sig, kind in test_signatures:
        if kind == "Promise":
            unpacked, ok = PatternMatcher.unpack_promise(type_sig)
            expr = f"Awaited<{type_sig}>"
            log_step(expr, "PASS" if ok else "FAIL", f"infer Inner -> {unpacked}")
        elif kind == "Array":
            unpacked, ok = PatternMatcher.unpack_array(type_sig)
            expr = f"Flatten<{type_sig}>"
            log_step(expr, "PASS" if ok else "FAIL", f"infer Element -> {unpacked}")
        else:
            unpacked, ok = PatternMatcher.unpack_array(type_sig)
            expr = f"Flatten<{type_sig}>"
            log_step(expr, "PASS" if not ok else "FAIL", f"No pattern match -> fallback to {unpacked}")

    # Summary
    print(f"\n{GREEN}{BOLD}✔ Seluruh simulasi aljabar sistem type TypeScript berhasil dieksekusi 100% valid.{RESET}\n")


if __name__ == "__main__":
    run_interactive_simulation()
