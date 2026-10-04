#!/usr/bin/env python3
"""
Lab Hands-on: JavaScript Functional Programming & Closures Deep Dive
Simulates JavaScript Lexical Environments, Scope Chains, Engine Closure Memory,
Currying, Function Composition, and Pure Data Pipelines.
"""

import sys
import time
import inspect
from typing import Any, Callable, Dict, List, Optional

# --- ANSI Terminal Color Palette ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"


# ============================================================================
# 1. ENGINE SIMULATION: Lexical Environment & Scope Chain
# ============================================================================
class LexicalEnvironment:
    """
    Simulates the V8 / SpiderMonkey Lexical Environment Record.
    Each environment holds an Environment Record and an outer reference [[OuterEnv]].
    """
    def __init__(self, name: str, outer: Optional['LexicalEnvironment'] = None):
        self.name = name
        self.outer = outer
        self.record: Dict[str, Any] = {}

    def declare(self, key: str, value: Any) -> None:
        """Declares an identifier in the current record (mimicking let/const)."""
        self.record[key] = value

    def resolve(self, key: str) -> Any:
        """
        Walks up the scope chain resolving identifier references.
        Raises NameError if reference cannot be resolved up to Global scope.
        """
        if key in self.record:
            return self.record[key]
        if self.outer is not None:
            return self.outer.resolve(key)
        raise NameError(f"ReferenceError: {key} is not defined in scope chain.")

    def mutate(self, key: str, value: Any) -> None:
        """Mutates an existing binding across the scope chain."""
        if key in self.record:
            self.record[key] = value
            return
        if self.outer is not None:
            self.outer.mutate(key, value)
            return
        raise NameError(f"ReferenceError: Cannot assign to undeclared variable '{key}'.")


class JSClosureFunction:
    """
    Simulates a JavaScript First-Class Function object bound to its
    lexical definition environment via [[Scopes]].
    """
    def __init__(self, name: str, logic: Callable[..., Any], parent_env: LexicalEnvironment):
        self.name = name
        self.logic = logic
        self.enclosing_env = parent_env  # Retained in memory (Closure)

    def __call__(self, *args, **kwargs) -> Any:
        # Create execution context with outer pointing to enclosing_env
        call_env = LexicalEnvironment(f"{self.name}_ActivationContext", outer=self.enclosing_env)
        return self.logic(call_env, *args, **kwargs)


# ============================================================================
# 2. FUNCTIONAL PROGRAMMING UTILITIES (Curry, Compose, Memoize)
# ============================================================================
def curry(fn: Callable) -> Callable:
    """
    Transforms a multi-arity function into a sequence of unary functions.
    Uses closure state to accumulate arguments until arity is satisfied.
    """
    sig = inspect.signature(fn)
    total_args = len(sig.parameters)

    def curried(*args):
        if len(args) >= total_args:
            return fn(*args[:total_args])
        return lambda *more_args: curried(*(args + more_args))

    return curried


def compose(*functions: Callable) -> Callable:
    """
    Performs right-to-left function composition: (f ∘ g ∘ h)(x) = f(g(h(x))).
    Pure functional pipeline pattern.
    """
    def composed_fn(arg: Any) -> Any:
        result = arg
        for fn in reversed(functions):
            result = fn(result)
        return result
    return composed_fn


def pipe(*functions: Callable) -> Callable:
    """
    Performs left-to-right function piping: pipe(f, g, h)(x) = h(g(f(x))).
    Standard syntax paradigm for modern JS pipelines.
    """
    def piped_fn(arg: Any) -> Any:
        result = arg
        for fn in functions:
            result = fn(result)
        return result
    return piped_fn


def memoize_closure(fn: Callable) -> Callable:
    """
    Implements memoization leveraging an enclosed private cache store.
    Prevents global namespace pollution and guarantees idempotency.
    """
    cache: Dict[str, Any] = {}
    stats = {"hits": 0, "misses": 0}

    def memoized_fn(*args):
        key = str(args)
        if key in cache:
            stats["hits"] += 1
            return cache[key], True, stats
        stats["misses"] += 1
        res = fn(*args)
        cache[key] = res
        return res, False, stats

    return memoized_fn


# ============================================================================
# 3. LAB EXERCISES & DEMONSTRATION WORKFLOW
# ============================================================================
def run_scope_chain_simulation():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== 1. Lexical Scope Chain & Variable Shadowing Simulation ==={CLR_RESET}")
    
    # Global Execution Context
    global_env = LexicalEnvironment("GlobalScope")
    global_env.declare("taxRate", 0.15)
    global_env.declare("currency", "USD")

    # Module / Outer Function Execution Context
    outer_env = LexicalEnvironment("InvoiceModuleScope", outer=global_env)
    outer_env.declare("baseDiscount", 5.0)
    outer_env.declare("currency", "EUR")  # Shadows global 'currency'

    # Simulated Closure Construction
    def calculate_total_logic(local_env: LexicalEnvironment, subtotal: float) -> dict:
        local_env.declare("subtotal", subtotal)
        
        # Identifier resolution via lexical chain
        rate = local_env.resolve("taxRate")         # Found in Global
        discount = local_env.resolve("baseDiscount") # Found in Outer
        curr = local_env.resolve("currency")         # Found in Outer (Shadowed)
        
        final_amount = (subtotal - discount) * (1.0 + rate)
        return {
            "subtotal": subtotal,
            "discount": discount,
            "rate": rate,
            "currency": curr,
            "final": round(final_amount, 2)
        }

    js_closure = JSClosureFunction("calculateTotal", calculate_total_logic, outer_env)
    res = js_closure(100.0)

    print(f"[{CLR_GREEN}Scope Resolved{CLR_RESET}] Result: {res['final']} {res['currency']}")
    print(f" -> Tax Rate (Resolved from Global): {res['rate']}")
    print(f" -> Base Discount (Resolved from Outer): {res['discount']}")
    print(f" -> Currency (Shadowed by InvoiceModule): {res['currency']}")


def run_closure_loop_dilemma():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== 2. The Classic JS Closure-in-Loop Phenomenon (var vs let) ==={CLR_RESET}")
    
    print(f"{CLR_YELLOW}Scenario A: Variable Mutation by Reference (Simulating 'var'){CLR_RESET}")
    shared_env = LexicalEnvironment("LoopVarScope")
    shared_env.declare("i", 0)
    tasks_var: List[JSClosureFunction] = []

    for idx in range(3):
        shared_env.mutate("i", idx + 1)
        tasks_var.append(
            JSClosureFunction(
                f"callback_{idx}",
                lambda env: env.resolve("i"),
                shared_env
            )
        )

    var_outputs = [t() for t in tasks_var]
    print(f"  Call results across iterations: {var_outputs} (All share same mutable reference)")

    print(f"{CLR_GREEN}Scenario B: Block Scoping Closure Capture (Simulating 'let'){CLR_RESET}")
    tasks_let: List[JSClosureFunction] = []

    for idx in range(3):
        # Fresh lexical environment created on every iteration
        block_env = LexicalEnvironment(f"Iteration_{idx}_BlockScope", outer=None)
        block_env.declare("i", idx + 1)
        tasks_let.append(
            JSClosureFunction(
                f"block_callback_{idx}",
                lambda env: env.resolve("i"),
                block_env
            )
        )

    let_outputs = [t() for t in tasks_let]
    print(f"  Call results across iterations: {let_outputs} (Correctly isolated environments)")


def run_currying_and_composition():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== 3. Point-Free Composition & Currying Pipelines ==={CLR_RESET}")

    # Curried arithmetic primitives
    multiply = curry(lambda a, b: a * b)
    add = curry(lambda a, b: a + b)
    apply_vat = multiply(1.20)     # Partial: 20% VAT
    apply_shipping = add(15.0)     # Partial: Flat shipping
    apply_coupon = add(-10.0)      # Partial: Coupon discount

    # Pure composition: output = apply_shipping(apply_vat(apply_coupon(price)))
    checkout_pipeline = pipe(apply_coupon, apply_vat, apply_shipping)

    raw_price = 100.0
    final_price = checkout_pipeline(raw_price)
    
    print(f"  Input raw price      : ${raw_price:.2f}")
    print(f"  After coupon (-$10)  : ${raw_price - 10.0:.2f}")
    print(f"  After 20% VAT        : ${(raw_price - 10.0) * 1.20:.2f}")
    print(f"  After $15 shipping   : ${final_price:.2f}")
    print(f"[{CLR_GREEN}Pipe Verified{CLR_RESET}] Final Calculated Price: ${final_price:.2f}")


def run_memoization_benchmark():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== 4. Memoization via Enclosed Closure Scope State ==={CLR_RESET}")

    def expensive_hash(n: int) -> int:
        """Simulates computationally heavy pure operation."""
        acc = n
        for _ in range(50000):
            acc = (acc * 1664525 + 1013904223) & 0xFFFFFFFF
        return acc

    memoized_worker = memoize_closure(expensive_hash)
    test_inputs = [42, 88, 42, 1024, 88, 42]

    for val in test_inputs:
        t0 = time.perf_counter()
        result, is_cached, stats = memoized_worker(val)
        elapsed = (time.perf_counter() - t0) * 1000.0
        
        status_tag = f"{CLR_GREEN}[CACHE HIT ]{CLR_RESET}" if is_cached else f"{CLR_RED}[CACHE MISS]{CLR_RESET}"
        print(f"  {status_tag} Input: {val:<5} -> Result: {result:<10} | Time: {elapsed:.3f}ms")

    print(f"\nClosure Internal Memory Metrics: Hits={stats['hits']}, Misses={stats['misses']}")


def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}==============================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}   LAB: JAVASCRIPT FUNCTIONAL PROGRAMMING & CLOSURES DEEP DIVE {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}==============================================================={CLR_RESET}")

    start_time = time.perf_counter()
    run_scope_chain_simulation()
    run_closure_loop_dilemma()
    run_currying_and_composition()
    run_memoization_benchmark()
    total_time = (time.perf_counter() - start_time) * 1000.0

    print(f"\n{CLR_BOLD}{CLR_GREEN}Lab completed successfully in {total_time:.2f} ms.{CLR_RESET}\n")


if __name__ == "__main__":
    main()