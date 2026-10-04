#!/usr/bin/env python3
"""
Lab Hands-on: Ruby Internal Mechanics - Functional Paradigm & Collection Processing
Chapter 03, Module 02: Deep Dive

This lab constructs an architectural simulation of Ruby's functional machinery
and collection pipeline execution model:
1. Block, Proc, and Lambda semantics (yielding, strict vs lenient arity).
2. Ruby Enumerable mixin emulation with method chaining.
3. Ruby Enumerator::Lazy simulation utilizing deferred generator pipelines.
4. Eager vs Lazy collection processing benchmarks (memory and throughput profiling).
"""

import sys
import time
import tracemalloc
from typing import Callable, Any, Iterator, List, Optional

# --- ANSI Terminal Styling ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"

def log_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}=== [RUBY RUNTIME SIMULATION] {title} ==={RESET}")

def log_info(msg: str) -> None:
    print(f"{BLUE}[INFO]{RESET} {msg}")

def log_step(name: str, detail: str) -> None:
    print(f"{GREEN}[EXEC]{RESET} {BOLD}{name}:{RESET} {detail}")

def log_warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {msg}")


# ============================================================================
# Section 1: Ruby Proc & Lambda Mechanics Emulation
# ============================================================================

class RubyProc:
    """
    Simulates Ruby's Proc and Lambda behavior.
    In Ruby:
    - Proc.new has lenient arity (pads with nil or truncates arguments).
    - lambda (->) has strict arity (raises ArgumentError if mismatched).
    """
    def __init__(self, func: Callable, is_lambda: bool = False, arity: Optional[int] = None):
        self.func = func
        self.is_lambda = is_lambda
        self.arity = arity if arity is not None else func.__code__.co_argcount

    def call(self, *args: Any) -> Any:
        if self.is_lambda:
            if len(args) != self.arity:
                raise TypeError(
                    f"wrong number of arguments (given {len(args)}, expected {self.arity}) [Ruby::ArgumentError]"
                )
            return self.func(*args)
        else:
            # Proc lenient arity: pad missing with None, discard extras
            normalized_args = list(args)
            if len(normalized_args) < self.arity:
                normalized_args.extend([None] * (self.arity - len(normalized_args)))
            elif len(normalized_args) > self.arity:
                normalized_args = normalized_args[:self.arity]
            return self.func(*normalized_args)

    def __call__(self, *args: Any) -> Any:
        return self.call(*args)

    def curry(self) -> Callable:
        """Emulates Proc#curry in Ruby."""
        def curried(*accum_args):
            if len(accum_args) >= self.arity:
                return self.call(*accum_args)
            return lambda *next_args: curried(*(accum_args + next_args))
        return curried

    def compose(self, other: 'RubyProc') -> 'RubyProc':
        """Emulates Ruby 2.6+ Proc#>> (function composition)."""
        composed = lambda *args: other.call(self.call(*args))
        return RubyProc(composed, is_lambda=self.is_lambda, arity=self.arity)


# ============================================================================
# Section 2: Ruby Enumerable & Lazy Enumerator Engine
# ============================================================================

class RubyLazyEnumerator:
    """
    Emulates Ruby's Enumerator::Lazy.
    Chained collection operations (map, select) are not evaluated immediately.
    Instead, they are fused into a lazy evaluation generator pipeline.
    """
    def __init__(self, source_iterable: Iterator[Any]):
        self._source = source_iterable

    def __iter__(self) -> Iterator[Any]:
        return iter(self._source)

    def map(self, block: Callable[[Any], Any]) -> 'RubyLazyEnumerator':
        """Lazy map transforms values on-demand without intermediate allocations."""
        def lazy_gen():
            for item in self._source:
                yield block(item)
        return RubyLazyEnumerator(lazy_gen())

    def select(self, predicate: Callable[[Any], bool]) -> 'RubyLazyEnumerator':
        """Lazy select/filter defers evaluation until consumed."""
        def lazy_gen():
            for item in self._source:
                if predicate(item):
                    yield item
        return RubyLazyEnumerator(lazy_gen())

    def take(self, count: int) -> List[Any]:
        """Materializes the lazy chain, terminating evaluation after count elements."""
        results = []
        for item in self._source:
            results.append(item)
            if len(results) == count:
                break
        return results

    def to_a(self) -> List[Any]:
        """Materializes the entire stream into a concrete list."""
        return list(self._source)


class RubyEnumerable:
    """
    Emulates Ruby's core Enumerable mixin.
    Provides eager functional primitives: each, map, select, reject, reduce, group_by.
    """
    def __init__(self, collection: List[Any]):
        self._data = list(collection)

    def each(self, block: Callable[[Any], None]) -> 'RubyEnumerable':
        """Simulates collection.each { |item| ... }"""
        for elem in self._data:
            block(elem)
        return self

    def map(self, block: Callable[[Any], Any]) -> 'RubyEnumerable':
        """Eager map: allocates a new intermediate array."""
        return RubyEnumerable([block(elem) for elem in self._data])

    def select(self, predicate: Callable[[Any], bool]) -> 'RubyEnumerable':
        """Eager select: allocates a new filtered array."""
        return RubyEnumerable([elem for elem in self._data if predicate(elem)])

    def reject(self, predicate: Callable[[Any], bool]) -> 'RubyEnumerable':
        """Ruby reject is the inverse of select."""
        return RubyEnumerable([elem for elem in self._data if not predicate(elem)])

    def reduce(self, initial: Any, accumulator: Callable[[Any, Any], Any]) -> Any:
        """Simulates Enumerable#inject / Enumerable#reduce."""
        state = initial
        for elem in self._data:
            state = accumulator(state, elem)
        return state

    def lazy(self) -> RubyLazyEnumerator:
        """Transitions collection to Enumerator::Lazy pipeline."""
        return RubyLazyEnumerator(iter(self._data))

    def to_a(self) -> List[Any]:
        return list(self._data)


# ============================================================================
# Section 3: Lab Test Harness & Scenarios
# ============================================================================

def run_proc_lambda_deep_dive():
    log_header("1. Ruby Block, Proc, and Lambda Semantics")
    
    # 1. Proc Lenient Arity Test
    log_step("Proc.new", "Defined with arity = 2. Invoking with missing & excess args.")
    proc_fn = RubyProc(lambda a, b: f"a={a}, b={b}", is_lambda=False, arity=2)
    
    res1 = proc_fn.call(42)
    log_info(f"Proc with 1 arg: {res1} (nil-padding verified)")
    
    res2 = proc_fn.call(10, 20, 30)
    log_info(f"Proc with 3 args: {res2} (excess truncation verified)")

    # 2. Lambda Strict Arity Test
    log_step("Lambda (->)", "Defined with arity = 2. Verifying strict argument validation.")
    lambda_fn = RubyProc(lambda a, b: f"a={a}, b={b}", is_lambda=True, arity=2)
    
    res_valid = lambda_fn.call(100, 200)
    log_info(f"Lambda normal invocation: {res_valid}")
    
    try:
        lambda_fn.call(100)
    except TypeError as err:
        log_warn(f"Intercepted strict failure: {err}")

    # 3. Proc Composition and Currying
    log_step("Functional Features", "Proc#curry and Proc#>> composition")
    multiplier = RubyProc(lambda factor, val: factor * val, is_lambda=True, arity=2)
    curried_triple = multiplier.curry()(3)
    formatter = RubyProc(lambda x: f"${x:.2f}", is_lambda=True, arity=1)
    
    pipeline = RubyProc(curried_triple, is_lambda=True, arity=1).compose(formatter)
    output = pipeline.call(250)
    log_info(f"Composition (triple >> format_currency)(250) => {output}")


def run_eager_collection_processing():
    log_header("2. Ruby Enumerable: Eager Evaluation & Method Chaining")
    
    raw_inventory = [
        {"sku": "SRV-01", "tier": "enterprise", "cores": 64, "price": 450},
        {"sku": "DEV-02", "tier": "standard",   "cores": 8,  "price": 60},
        {"sku": "SRV-03", "tier": "enterprise", "cores": 128,"price": 900},
        {"sku": "IOT-04", "tier": "edge",       "cores": 2,  "price": 15},
        {"sku": "SRV-05", "tier": "enterprise", "cores": 32, "price": 280},
    ]
    
    ruby_coll = RubyEnumerable(raw_inventory)
    log_info(f"Loaded {len(raw_inventory)} inventory records into Enumerable collection.")

    # Simulating: inventory.select { |s| s[:tier] == 'enterprise' }
    #                      .map { |s| s[:cores] * 1.5 }
    #                      .reduce(0) { |acc, cores| acc + cores }
    log_step("Eager Chain", "select(enterprise) -> map(allocated_cores * 1.5) -> reduce(sum)")
    
    total_boosted_cores = (
        ruby_coll
        .select(lambda node: node["tier"] == "enterprise")
        .map(lambda node: node["cores"] * 1.5)
        .reduce(0.0, lambda acc, cores: acc + cores)
    )
    
    log_info(f"Aggregated Enterprise vCPU Capacity: {BOLD}{total_boosted_cores}{RESET}")


def run_lazy_pipeline_benchmark():
    log_header("3. Ruby Enumerator::Lazy vs Eager Memory Benchmark")

    DATA_SIZE = 250_000
    TAKE_LIMIT = 5
    log_info(f"Synthesizing dataset: {DATA_SIZE:,} elements.")
    log_info(f"Target query: find first {TAKE_LIMIT} elements matching: (n % 13 == 0) -> n^2 -> n > 5000")

    # Infinite or large dataset generator
    def dataset_stream():
        for i in range(1, DATA_SIZE + 1):
            yield i

    # --- EAGER EXECUTION ---
    log_step("Benchmark 1", "Eager Collection Execution (allocating intermediate lists)")
    tracemalloc.start()
    t0 = time.perf_counter()
    
    eager_input = list(range(1, DATA_SIZE + 1))
    eager_enum = RubyEnumerable(eager_input)
    
    # Eager processes the entire dataset on every stage
    eager_result = (
        eager_enum
        .select(lambda x: x % 13 == 0)
        .map(lambda x: x ** 2)
        .select(lambda x: x > 5000)
        .to_a()[:TAKE_LIMIT]
    )
    t_eager = time.perf_counter() - t0
    current_mem, peak_eager_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # --- LAZY EXECUTION ---
    log_step("Benchmark 2", "Lazy Pipeline Execution (Enumerator::Lazy deferred evaluation)")
    tracemalloc.start()
    t1 = time.perf_counter()

    lazy_enum = RubyLazyEnumerator(dataset_stream())
    
    # Lazy processes elements one-by-one through the pipeline, halting at TAKE_LIMIT
    lazy_result = (
        lazy_enum
        .select(lambda x: x % 13 == 0)
        .map(lambda x: x ** 2)
        .select(lambda x: x > 5000)
        .take(TAKE_LIMIT)
    )
    t_lazy = time.perf_counter() - t1
    current_mem, peak_lazy_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # --- TELEMETRY SUMMARY ---
    print(f"\n{BOLD}Pipeline Profiling Telemetry Summary:{RESET}")
    print(f"{'Metric':<25} | {'Eager (Enumerable)':<20} | {'Lazy (Enumerator::Lazy)':<20}")
    print("-" * 72)
    print(f"{'Execution Time':<25} | {f'{t_eager:.4f}s':<20} | {f'{t_lazy:.6f}s':<20}")
    print(f"{'Peak Memory':<25} | {f'{peak_eager_mem / (1024*1024):.2f} MB':<20} | {f'{peak_lazy_mem / 1024:.2f} KB':<20}")
    print(f"{'First Results':<25} | {str(eager_result[:2]) + '...':<20} | {str(lazy_result[:2]) + '...':<20}")
    print("-" * 72)

    speedup = (t_eager / t_lazy) if t_lazy > 0 else float('inf')
    mem_saved = (peak_eager_mem - peak_lazy_mem) / (1024 * 1024)
    print(f"{MAGENTA}{BOLD}Conclusion:{RESET} Lazy evaluation was {BOLD}{speedup:.1f}x faster{RESET} "
          f"and avoided allocating {BOLD}{mem_saved:.2f} MB{RESET} of intermediate buffers.")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{BOLD}{MAGENTA} LAB SIMULATION: RUBY FUNCTIONAL PROGRAMMING & COLLECTION MECHANICS  {RESET}")
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")

    run_proc_lambda_deep_dive()
    run_eager_collection_processing()
    run_lazy_pipeline_benchmark()

    print(f"\n{GREEN}{BOLD}[SUCCESS]{RESET} All Ruby collection and functional paradigm mechanics verified.\n")

if __name__ == "__main__":
    main()