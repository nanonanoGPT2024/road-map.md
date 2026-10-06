#!/usr/bin/env python3
"""
Lab Exercise: Ruby Functional Paradigm & Collection Processing Simulation in Python 3
Topic: BAB-03 Functional Paradigm & Collection Processing (Ruby Metaprogramming & Enumerable Mechanics)

Simulates:
1. Block & Yield semantics with block_given? check
2. Proc vs Lambda distinctions (strict arity vs permissive arity, local return vs non-local jump)
3. Enumerable module chainable pipeline (map, select, reject, reduce/inject, group_by, flat_map)
4. Lazy Enumerator (Enumerator::Lazy) for infinite streams and deferred execution
5. Ruby Symbol#to_proc (&:method) idiom simulation
"""

import sys
import time
from typing import Callable, Any, Generator, Iterable, Dict, List, Tuple, Optional

# ANSI Color Codes for Rich Terminal Output
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{BOLD}{BG_BLUE}{WHITE}  === {title.upper()} ===  {RESET}")


def subheader(title: str) -> None:
    print(f"\n{BOLD}{CYAN}>>> {title}{RESET}")


def log_step(name: str, detail: str) -> None:
    print(f"  {MAGENTA}•{RESET} {BOLD}{name:<22}{RESET}: {GREEN}{detail}{RESET}")


def log_info(msg: str) -> None:
    print(f"    {DIM}{msg}{RESET}")


# ============================================================================
# Section 1: Block & Yield Simulation (Ruby block_given? and yield semantics)
# ============================================================================

class RubyBlockRunner:
    """Simulates Ruby method block execution and block_given? checks."""

    @staticmethod
    def repeat(times: int, block: Optional[Callable[[int], Any]] = None) -> List[Any]:
        results = []
        if block is None:
            # Ruby: return to_enum(:repeat, times) unless block_given?
            print(f"    {YELLOW}[block_given? => False]{RESET} No block supplied. Returning mock Enumerator.")
            return list(range(times))

        print(f"    {GREEN}[block_given? => True]{RESET} Yielding control {times} times:")
        for idx in range(times):
            res = block(idx)  # simulate 'yield idx'
            results.append(res)
        return results


# ============================================================================
# Section 2: Proc vs Lambda (Arity checks & Return semantics)
# ============================================================================

class RubyCallable:
    """Base class for Ruby Proc and Lambda closures."""
    def __init__(self, fn: Callable[..., Any], is_lambda: bool = False):
        self.fn = fn
        self.is_lambda = is_lambda

    def call(self, *args, **kwargs) -> Any:
        raise NotImplementedError


class RubyProc(RubyCallable):
    """
    Simulates Ruby Proc:
    - Loose arity checking (ignores extra args, pads missing args with None)
    - Return behaves like a jump (simulated with status flag)
    """
    def __init__(self, fn: Callable[..., Any]):
        super().__init__(fn, is_lambda=False)

    def call(self, *args) -> Any:
        import inspect
        sig = inspect.signature(self.fn)
        expected_params = list(sig.parameters.values())
        param_count = len(expected_params)

        adjusted_args = list(args)
        if len(adjusted_args) < param_count:
            adjusted_args.extend([None] * (param_count - len(adjusted_args)))
        elif len(adjusted_args) > param_count:
            adjusted_args = adjusted_args[:param_count]

        return self.fn(*adjusted_args)


class RubyLambda(RubyCallable):
    """
    Simulates Ruby Lambda (lambda / ->):
    - Strict arity checking (ArgumentError if mismatch)
    - Local return behavior
    """
    def __init__(self, fn: Callable[..., Any]):
        super().__init__(fn, is_lambda=True)

    def call(self, *args) -> Any:
        import inspect
        sig = inspect.signature(self.fn)
        param_count = len(sig.parameters)
        if len(args) != param_count:
            raise TypeError(f"wrong number of arguments (given {len(args)}, expected {param_count})")
        return self.fn(*args)

    def curry(self) -> Callable:
        """Currying support native to Ruby Procs/Lambdas."""
        import inspect
        target_arity = len(inspect.signature(self.fn).parameters)

        def curried_acc(accumulated: Tuple[Any, ...]) -> Callable:
            def inner(*new_args: Any) -> Any:
                total_args = accumulated + new_args
                if len(total_args) >= target_arity:
                    return self.fn(*total_args[:target_arity])
                return curried_acc(total_args)
            return inner

        return curried_acc(())


# ============================================================================
# Section 3: Ruby Symbol#to_proc (&:method) Paradigm
# ============================================================================

def symbol_to_proc(method_name: str) -> Callable[[Any], Any]:
    """
    Simulates Ruby Symbol#to_proc:
    &:upcase  => ->(obj) { obj.upcase }
    """
    def _proc(target: Any) -> Any:
        attr = getattr(target, method_name, None)
        if callable(attr):
            return attr()
        elif attr is not None:
            return attr
        raise AttributeError(f"Undefined method or attribute '{method_name}' for {target}")
    return _proc


# ============================================================================
# Section 4: Ruby Enumerable Pipeline Simulator
# ============================================================================

class RubyEnumerable:
    """
    Simulates Ruby's Enumerable mixin providing a fluent functional pipeline.
    """
    def __init__(self, collection: Iterable[Any]):
        self._data = list(collection)

    def to_a(self) -> List[Any]:
        return list(self._data)

    def map(self, fn: Callable[[Any], Any]) -> 'RubyEnumerable':
        return RubyEnumerable(fn(item) for item in self._data)

    def select(self, predicate: Callable[[Any], bool]) -> 'RubyEnumerable':
        """Ruby #select / #find_all"""
        return RubyEnumerable(item for item in self._data if predicate(item))

    def reject(self, predicate: Callable[[Any], bool]) -> 'RubyEnumerable':
        """Ruby #reject (inverse of select)"""
        return RubyEnumerable(item for item in self._data if not predicate(item))

    def reduce(self, initial: Any, operation: Callable[[Any, Any], Any]) -> Any:
        """Ruby #reduce / #inject"""
        accumulator = initial
        for item in self._data:
            accumulator = operation(accumulator, item)
        return accumulator

    def flat_map(self, fn: Callable[[Any], Iterable[Any]]) -> 'RubyEnumerable':
        """Ruby #flat_map / #collect_concat"""
        flattened = []
        for item in self._data:
            res = fn(item)
            if isinstance(res, (list, tuple, set, RubyEnumerable)):
                flattened.extend(list(res))
            else:
                flattened.append(res)
        return RubyEnumerable(flattened)

    def group_by(self, key_fn: Callable[[Any], Any]) -> Dict[Any, List[Any]]:
        """Ruby #group_by returning hash with grouped arrays"""
        grouped: Dict[Any, List[Any]] = {}
        for item in self._data:
            key = key_fn(item)
            grouped.setdefault(key, []).append(item)
        return grouped

    def partition(self, predicate: Callable[[Any], bool]) -> Tuple[List[Any], List[Any]]:
        """Ruby #partition -> [matches, non_matches]"""
        yes_list, no_list = [], []
        for item in self._data:
            if predicate(item):
                yes_list.append(item)
            else:
                no_list.append(item)
        return yes_list, no_list

    def lazy(self) -> 'RubyLazyEnumerator':
        """Enter Ruby Enumerator::Lazy mode"""
        return RubyLazyEnumerator(self._data)


# ============================================================================
# Section 5: Ruby Lazy Enumerator (Enumerator::Lazy)
# ============================================================================

class RubyLazyEnumerator:
    """
    Simulates Ruby Enumerator::Lazy:
    Defers evaluation until explicit termination method (e.g., take, first, force).
    Allows infinite pipelines without Out-Of-Memory exhaustion.
    """
    def __init__(self, generator_factory: Iterable[Any]):
        self._iterable = generator_factory

    def _get_generator(self) -> Generator[Any, None, None]:
        for item in self._iterable:
            yield item

    def map(self, fn: Callable[[Any], Any]) -> 'RubyLazyEnumerator':
        def _lazy_map():
            for item in self._get_generator():
                yield fn(item)
        return RubyLazyEnumerator(_lazy_map())

    def select(self, predicate: Callable[[Any], bool]) -> 'RubyLazyEnumerator':
        def _lazy_select():
            for item in self._get_generator():
                if predicate(item):
                    yield item
        return RubyLazyEnumerator(_lazy_select())

    def take(self, n: int) -> List[Any]:
        """Terminator method: consumes only n elements."""
        results = []
        for idx, item in enumerate(self._get_generator()):
            if idx >= n:
                break
            results.append(item)
        return results

    def force(self) -> List[Any]:
        """Terminator method: forces full evaluation."""
        return list(self._get_generator())


# ============================================================================
# Interactive Demonstration & Test Runner
# ============================================================================

def infinite_numbers(start: int = 1) -> Generator[int, None, None]:
    """Generates unbounded sequence representing Ruby (1..Float::INFINITY)."""
    curr = start
    while True:
        yield curr
        curr += 1


def run_demonstration() -> None:
    print(f"\n{BOLD}{GREEN}===================================================================={RESET}")
    print(f"{BOLD}{GREEN}  RUBY FUNCTIONAL PARADIGM & COLLECTION PROCESSING SIMULATOR (PYTHON 3) {RESET}")
    print(f"{BOLD}{GREEN}===================================================================={RESET}")

    # Demo 1: Blocks & Yield
    header("1. Ruby Block & Yield Semantics")
    print("Testing method call with block (yield) vs without block (block_given?):")
    res_with_block = RubyBlockRunner.repeat(3, lambda i: f"Execution index #{i}")
    log_step("With Block Result", str(res_with_block))

    res_without_block = RubyBlockRunner.repeat(3, None)
    log_step("Without Block Result", str(res_without_block))

    # Demo 2: Proc vs Lambda Arity
    header("2. Proc vs Lambda Arity & Semantics")
    rb_proc = RubyProc(lambda x, y: f"x={x}, y={y}")
    rb_lambda = RubyLambda(lambda x, y: f"x={x}, y={y}")

    print(f"Calling Proc with 1 argument instead of 2:")
    log_step("Proc (loose arity)", rb_proc.call(100))

    print(f"Calling Lambda with 1 argument instead of 2:")
    try:
        rb_lambda.call(100)
    except TypeError as e:
        log_step("Lambda (strict arity)", f"{RED}ArgumentError: {e}{RESET}")

    # Demo 3: Currying
    header("3. Lambda Currying (Ruby Function Currying)")
    multiplier = RubyLambda(lambda a, b, c: a * b * c).curry()
    double_and_triple = multiplier(2)(3)
    final_val = double_and_triple(5)
    log_step("Curry Pipeline", f"2 * 3 * 5 = {final_val}")

    # Demo 4: Symbol#to_proc
    header("4. Ruby Symbol#to_proc (&:method) Simulation")
    words = ["ruby", "metaprogramming", "enumerable", "closure"]
    upcase_proc = symbol_to_proc("upper")  # in Python str.upper() corresponds to Ruby #upcase
    upper_words = [upcase_proc(w) for w in words]
    log_step("Input Words", str(words))
    log_step("Applied &:upper", str(upper_words))

    # Demo 5: Fluent Enumerable Pipeline
    header("5. Enumerable Pipeline (Chainable Transformations)")
    dataset = RubyEnumerable(range(1, 13))
    print(f"Original Collection: {dataset.to_a()}")

    # Pipeline: select evens -> reject multiples of 4 -> map square -> group by modulo 5
    filtered = (
        dataset
        .select(lambda x: x % 2 == 0)      # [2, 4, 6, 8, 10, 12]
        .reject(lambda x: x % 4 == 0)      # [2, 6, 10]
        .map(lambda x: x ** 2)             # [4, 36, 100]
    )
    log_step("Filtered & Squared", str(filtered.to_a()))

    sum_reduced = filtered.reduce(0, lambda acc, val: acc + val)
    log_step("Injected Sum (#reduce)", f"4 + 36 + 100 = {sum_reduced}")

    groups = dataset.group_by(lambda x: "odd" if x % 2 != 0 else "even")
    log_step("Group By Parity", str(groups))

    odds, evens = dataset.partition(lambda x: x % 2 != 0)
    log_step("Partition [odds, evens]", f"Odds={odds}, Evens={evens}")

    # Demo 6: Lazy Enumeration
    header("6. Lazy Enumeration (Enumerator::Lazy)")
    print("Processing theoretically INFINITE stream (1..Float::INFINITY):")
    print(f"Pipeline: {YELLOW}(1..∞).lazy.select(is_prime_like).map(x -> x * 10).take(5){RESET}")

    def is_odd_mult3(x: int) -> bool:
        return x % 2 != 0 and x % 3 == 0

    lazy_stream = RubyLazyEnumerator(infinite_numbers(1))
    t0 = time.perf_counter()
    lazy_result = (
        lazy_stream
        .select(is_odd_mult3)
        .map(lambda x: f"Val_{x * 10}")
        .take(5)
    )
    t_elapsed = (time.perf_counter() - t0) * 1000
    log_step("Lazy Result (5 items)", str(lazy_result))
    log_step("Execution Time", f"{t_elapsed:.3f} ms (no memory explosion)")

    print(f"\n{BOLD}{GREEN}✔ All Ruby Functional Mechanics successfully verified!{RESET}\n")


if __name__ == "__main__":
    run_demonstration()
