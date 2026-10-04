#!/usr/bin/env python3
"""
Lab: Ruby Gem Architecture, C-Native Extensions (MRI), and Runtime Typing (Sorbet/RBS)
Simulates:
 1. Gem Build Lifecycle & Specification metadata (gemspec parsing, extconf.rb compilation).
 2. Native Extension Boundary: Simulating Ruby MRI C-API (VALUE pointers, NUM2INT/INT2NUM, GIL release).
 3. RBS/Sorbet Runtime Typing System: Method signatures (sig), nilable enforcement, and type contracts.
"""

import time
import ctypes
import functools
from typing import Any, Dict, List, Callable, get_type_hints

# --- ANSI Terminal Formatting ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_CYAN   = "\033[36m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED    = "\033[31m"
CLR_MAG    = "\033[35m"

def print_section(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== {title} ==={CLR_RESET}")

def print_log(stage: str, msg: str, status: str = "INFO"):
    color = CLR_GREEN if status == "OK" else (CLR_YELLOW if status == "WARN" else CLR_CYAN)
    print(f"[{color}{status:4s}{CLR_RESET}] {CLR_BOLD}[{stage}]{CLR_RESET} {msg}")

# ============================================================================
# MODULE 1: GEM SPECIFICATION & EXTCONF.RB SIMULATION
# ============================================================================
class GemSpecification:
    """Simulates Gem::Specification defining dependencies and native build flags."""
    def __init__(self, name: str, version: str, extensions: List[str] = None):
        self.name = name
        self.version = version
        self.extensions = extensions or []
        self.dependencies: Dict[str, str] = {}

    def add_dependency(self, gem_name: str, version_req: str):
        self.dependencies[gem_name] = version_req

    def build_native_extensions(self):
        """Simulates mkmf.rb executing create_makefile and gcc compilation."""
        print_log("mkmf", f"Parsing {self.name}.gemspec (v{self.version})...")
        for ext in self.extensions:
            print_log("extconf", f"Checking for system header <ruby.h>... Found.", "OK")
            print_log("extconf", f"Generating Makefile for '{ext}' target...", "OK")
            print_log("compiler", f"gcc -shared -fPIC -O3 {ext} -o ext/{self.name}.so", "OK")
        return True


# ============================================================================
# MODULE 2: MRI C-EXTENSION SIMULATION (RUBY C-API)
# ============================================================================
class RubyVMBridge:
    """
    Simulates MRI Ruby's C-API boundary:
    - Object representation as VALUE (raw pointer / immediate values).
    - Unboxing (NUM2DBL) & Boxing (DBL2NUM).
    - rb_thread_call_without_gvl: Simulating release of GVL for intensive C routines.
    """
    @staticmethod
    def NUM2DBL(val: Any) -> float:
        """Simulate extracting raw double from Ruby Float/Fixnum VALUE struct."""
        if not isinstance(val, (int, float)):
            raise TypeError(f"TypeError: no implicit conversion of {type(val).__name__} into Float")
        return float(val)

    @staticmethod
    def DBL2NUM(val: float) -> float:
        """Simulate wrapping double into MRI Ruby VALUE (RFloat)."""
        return float(val)


def c_native_matrix_dot(val_a: List[List[float]], val_b: List[List[float]]) -> List[List[float]]:
    """
    Simulates a C-Native Extension implementation of dot product:
    Direct raw contiguous array processing bypassing VM interpreter dispatch.
    """
    rows_a = len(val_a)
    cols_a = len(val_a[0])
    cols_b = len(val_b[0])

    # Flatten and pack into raw C double buffers via ctypes
    flat_a = (ctypes.c_double * (rows_a * cols_a))(*[elem for row in val_a for elem in row])
    flat_b = (ctypes.c_double * (cols_a * cols_b))(*[elem for row in val_b for elem in row])
    flat_res = (ctypes.c_double * (rows_a * cols_b))()

    # Simulate C raw pointer execution (SIMD/tight loops without VM dispatch overhead)
    for i in range(rows_a):
        for k in range(cols_a):
            a_val = flat_a[i * cols_a + k]
            for j in range(cols_b):
                flat_res[i * cols_b + j] += a_val * flat_b[k * cols_b + j]

    # Unpack back to Ruby VALUE array structure
    result = []
    for i in range(rows_a):
        result.append([RubyVMBridge.DBL2NUM(flat_res[i * cols_b + j]) for j in range(cols_b)])
    return result


def pure_ruby_matrix_dot(val_a: List[List[float]], val_b: List[List[float]]) -> List[List[float]]:
    """
    Simulates pure interpreted Ruby matrix multiplication:
    Object lookups, hash-table dispatch, dynamic boxing on every iteration.
    """
    rows_a, cols_a = len(val_a), len(val_a[0])
    rows_b, cols_b = len(val_b), len(val_b[0])
    res = [[0.0 for _ in range(cols_b)] for _ in range(rows_a)]

    for i in range(rows_a):
        for j in range(cols_b):
            acc = 0.0
            for k in range(cols_a):
                # Simulates dynamic method send / lookup overhead in MRI
                RubyVMBridge.NUM2DBL(val_a[i][k])
                RubyVMBridge.NUM2DBL(val_b[k][j])
                acc += val_a[i][k] * val_b[k][j]
            res[i][j] = RubyVMBridge.DBL2NUM(acc)
    return res


# ============================================================================
# MODULE 3: SORBET / RBS TYPING RUNTIME SIMULATION
# ============================================================================
class T:
    """Sorbet-style type definition constructs."""
    class Nilable:
        def __init__(self, inner_type):
            self.inner_type = inner_type

    @classmethod
    def nilable(cls, inner_type):
        return cls.Nilable(inner_type)


def sig(params: Dict[str, Any], returns: Any):
    """
    Decorator implementing Sorbet's `sig { params(...).returns(...) }` contract.
    Enforces runtime type-safety similar to `sorbet-runtime`.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Resolve positional arguments into kwargs
            arg_names = func.__code__.co_varnames[:func.__code__.co_argcount]
            bound_args = dict(zip(arg_names, args))
            bound_args.update(kwargs)

            # Typecheck parameters
            for param_name, expected_type in params.items():
                if param_name in bound_args:
                    val = bound_args[param_name]
                    if isinstance(expected_type, T.Nilable):
                        if val is not None and not isinstance(val, expected_type.inner_type):
                            raise TypeError(
                                f"[Sorbet::TypeError] Parameter '{param_name}' must be "
                                f"T.nilable({expected_type.inner_type.__name__}), got {type(val).__name__} ({val!r})"
                            )
                    else:
                        if not isinstance(val, expected_type):
                            raise TypeError(
                                f"[Sorbet::TypeError] Parameter '{param_name}' expected {expected_type.__name__}, "
                                f"got {type(val).__name__} ({val!r})"
                            )

            # Execute underlying logic
            ret_val = func(*args, **kwargs)

            # Typecheck return value
            if returns is not None:
                if isinstance(returns, T.Nilable):
                    if ret_val is not None and not isinstance(ret_val, returns.inner_type):
                        raise TypeError(f"[Sorbet::TypeError] Expected return T.nilable({returns.inner_type.__name__}), got {type(ret_val).__name__}")
                elif not isinstance(ret_val, returns):
                    raise TypeError(f"[Sorbet::TypeError] Expected return {returns.__name__}, got {type(ret_val).__name__}")

            return ret_val
        return wrapper
    return decorator


# Class protected by simulated Sorbet contracts
class ComputeService:
    @sig(params={"name": str, "timeout": T.nilable(int)}, returns=str)
    def configure(self, name: str, timeout: int = None) -> str:
        timeout_str = f"{timeout}ms" if timeout else "default"
        return f"Service[{name}] configured with timeout={timeout_str}"

    @sig(params={"matrix": list, "scale": float}, returns=list)
    def scale_matrix(self, matrix: list, scale: float) -> list:
        return [[cell * scale for cell in row] for row in matrix]


# ============================================================================
# LAB EXECUTION PIPELINE
# ============================================================================
def main():
    print(f"{CLR_BOLD}{CLR_MAG}LAB DEEP DIVE: RUBY GEM, NATIVE EXTENSIONS & SORBET TYPING{CLR_RESET}")
    print("=" * 65)

    # 1. Gem Manifest & Native Compilation
    print_section("1. Gem Specification & Native Build (extconf.rb)")
    gem = GemSpecification("fast_linear_algebra", "1.4.2", extensions=["ext/fast_linear_algebra/extconf.rb"])
    gem.add_dependency("rake-compiler", "~> 1.2")
    gem.build_native_extensions()

    # 2. MRI C-Extension vs Pure Ruby Performance Benchmark
    print_section("2. MRI Native C-Extension vs. Pure Ruby Performance")
    dim = 60
    mat_a = [[float(i + j) for j in range(dim)] for i in range(dim)]
    mat_b = [[float(i * 0.1 + j * 0.2) for j in range(dim)] for i in range(dim)]

    print_log("benchmark", f"Executing {dim}x{dim} Matrix Multiply (Iterative)...")

    t0 = time.perf_counter()
    res_pure = pure_ruby_matrix_dot(mat_a, mat_b)
    t_pure = time.perf_counter() - t0
    print_log("benchmark", f"Pure Ruby Dispatch:     {t_pure*1000:7.2f} ms")

    t0 = time.perf_counter()
    res_c = c_native_matrix_dot(mat_a, mat_b)
    t_c = time.perf_counter() - t0
    print_log("benchmark", f"Native C-Ext (Optimized): {t_c*1000:7.2f} ms")

    speedup = t_pure / t_c if t_c > 0 else 1.0
    print(f"--> Native Acceleration: {CLR_GREEN}{speedup:.2f}x faster{CLR_RESET} (GVL released, contiguous C memory)")

    # 3. RBS & Sorbet Static/Runtime Typing Checks
    print_section("3. Sorbet / RBS Runtime Signature Verification")
    service = ComputeService()

    # Test Case 3A: Valid typed calls
    res1 = service.configure("FastBlasWorker", timeout=250)
    print_log("typing", f"Valid call: '{res1}'", "OK")

    res2 = service.configure("AsyncWorker", timeout=None)
    print_log("typing", f"Valid nilable call: '{res2}'", "OK")

    # Test Case 3B: Violation - Invalid type passed to non-nilable
    print_log("typing", "Triggering type contract violation (invalid param type)...")
    try:
        service.configure(12345, timeout=500)  # Name should be str
    except TypeError as e:
        print_log("contract", f"{CLR_RED}{e}{CLR_RESET}", "FAIL")

    # Test Case 3C: Violation - Invalid type passed to nilable parameter
    print_log("typing", "Triggering type contract violation on T.nilable parameter...")
    try:
        service.configure("DataPipeline", timeout="not-an-int")
    except TypeError as e:
        print_log("contract", f"{CLR_RED}{e}{CLR_RESET}", "FAIL")

    print_section("Summary")
    print(f"{CLR_GREEN}Lab completed successfully.{CLR_RESET}")
    print("Demonstrated Ruby C extension bridging, gemspec pipeline, and Sorbet type systems.")


if __name__ == "__main__":
    main()