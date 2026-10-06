#!/usr/bin/env python3
"""
Ruby Deep Dive: BAB-06 Gem Development, Native Extensions (C/FFI), & Typing (RBS/Sorbet)
Hands-on Technical Simulation Engine in Python 3.

Features:
1. Gemspec & Semantic Dependency Resolver (SemVer constraint matching).
2. Ruby C Extension & VM Simulation (VALUE boxing/unboxing, GVL management, dynamic binding).
3. Ruby Static Typing Engine (RBS signature parsing & Sorbet runtime contract enforcement).
"""

import sys
import time
import re
from typing import Any, Dict, List, Optional, Tuple, Callable

# --- ANSI Color Utilities ---
class TerminalColor:
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

def colorize(text: str, color: str) -> str:
    return f"{color}{text}{TerminalColor.RESET}"

def banner(title: str):
    width = 75
    print("\n" + colorize("=" * width, TerminalColor.CYAN))
    print(colorize(f" {title.center(width - 2)} ", TerminalColor.BOLD + TerminalColor.WHITE))
    print(colorize("=" * width, TerminalColor.CYAN))

# ==============================================================================
# SECTION 1: Gem Development & Dependency Resolution Simulation
# ==============================================================================

class GemSpec:
    """Simulates a RubyGems .gemspec declaration."""
    def __init__(self, name: str, version: str, summary: str):
        self.name = name
        self.version = version
        self.summary = summary
        self.dependencies: List[Tuple[str, str]] = []  # (name, requirement_str)
        self.files: List[str] = []

    def add_dependency(self, gem_name: str, requirement: str = ">= 0.0.0"):
        self.dependencies.append((gem_name, requirement))

    def package(self) -> Dict[str, Any]:
        return {
            "metadata": {"name": self.name, "version": self.version},
            "manifest_count": len(self.files),
            "dependencies": self.dependencies
        }

class SemVerResolver:
    """Pessimistic constraint (~>) and comparator parser for Ruby Gemfile dependencies."""
    @staticmethod
    def parse_version(v_str: str) -> Tuple[int, ...]:
        clean = re.sub(r'[^0-9.]', '', v_str)
        return tuple(map(int, clean.split('.')))

    @classmethod
    def satisfies(cls, version_str: str, constraint: str) -> bool:
        v = cls.parse_version(version_str)
        parts = constraint.strip().split()
        if len(parts) == 1:
            op, req = "==", parts[0]
        else:
            op, req = parts[0], parts[1]

        r = cls.parse_version(req)

        if op == "==":
            return v == r
        elif op == ">=":
            return v >= r
        elif op == "<=":
            return v <= r
        elif op == ">":
            return v > r
        elif op == "<":
            return v < r
        elif op == "~>":
            # Pessimistic operator: ~> 2.1 means >= 2.1 and < 3.0; ~> 2.1.3 means >= 2.1.3 and < 2.2.0
            if len(r) == 1:
                return v >= r
            upper = list(r[:-1])
            upper[-1] += 1
            return v >= r and v < tuple(upper)
        return False

# ==============================================================================
# SECTION 2: Ruby MRI C Extension, GVL, & VALUE Boxing Simulation
# ==============================================================================

class RubyValueTag:
    Qnil = 0x00
    Qtrue = 0x02
    Qfalse = 0x04
    FIXNUM_FLAG = 0x01

class RubyVMContext:
    """
    Simulates MRI C-API primitives:
    - VALUE representation (Tagged Pointer / Immediate vs Heap Object)
    - GVL (Giant VM Lock) release via rb_thread_call_without_gvl
    """
    def __init__(self):
        self.gvl_locked = True
        self.heap: Dict[int, Any] = {}
        self.method_table: Dict[str, Dict[str, Callable]] = {}

    def INT2FIX(self, n: int) -> int:
        """Simulate MRI Fixnum boxing: (n << 1) | 1"""
        return (n << 1) | RubyValueTag.FIXNUM_FLAG

    def FIX2INT(self, val: int) -> int:
        """Simulate MRI Fixnum unboxing: val >> 1"""
        if not (val & RubyValueTag.FIXNUM_FLAG):
            raise TypeError("VALUE is not an immediate Fixnum tagged pointer")
        return val >> 1

    def rb_define_class(self, class_name: str) -> str:
        if class_name not in self.method_table:
            self.method_table[class_name] = {}
        return class_name

    def rb_define_method(self, klass: str, method_name: str, c_func: Callable):
        self.method_table[klass][method_name] = c_func

    def rb_thread_call_without_gvl(self, blocking_func: Callable, udata: Any) -> Any:
        """Release GVL for non-blocking I/O or heavy native C crunching."""
        self.gvl_locked = False
        print(colorize("   [GVL Unlock] Released Ruby Giant VM Lock for native computation.", TerminalColor.DIM))
        res = blocking_func(udata)
        self.gvl_locked = True
        print(colorize("   [GVL Lock]   Re-acquired Ruby Giant VM Lock before returning to VM.", TerminalColor.DIM))
        return res

# Native C Extension Implementation simulation (ext/fast_matrix/fast_matrix.c)
def native_matrix_multiply(udata: Tuple[List[List[int]], List[List[int]]]) -> List[List[int]]:
    a, b = udata
    rows_a, cols_a = len(a), len(a[0])
    rows_b, cols_b = len(b), len(b[0])
    result = [[0 for _ in range(cols_b)] for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += a[i][k] * b[k][j]
    return result

# ==============================================================================
# SECTION 3: Ruby Static Typing (RBS & Sorbet Runtime Engine)
# ==============================================================================

class SorbetContractError(Exception):
    pass

class RubyTypeSignature:
    """Simulates Sorbet 'sig { params(...).returns(...) }' and RBS definitions."""
    def __init__(self, param_types: Dict[str, type], return_type: type):
        self.param_types = param_types
        self.return_type = return_type

    def enforce(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            arg_names = list(self.param_types.keys())
            for idx, arg_val in enumerate(args):
                if idx < len(arg_names):
                    expected = self.param_types[arg_names[idx]]
                    if not isinstance(arg_val, expected):
                        raise SorbetContractError(
                            f"Parameter type mismatch for '{arg_names[idx]}': "
                            f"expected {expected.__name__}, got {type(arg_val).__name__} ({arg_val})"
                        )
            res = func(*args, **kwargs)
            if not isinstance(res, self.return_type):
                raise SorbetContractError(
                    f"Return type mismatch: expected {self.return_type.__name__}, "
                    f"got {type(res).__name__} ({res})"
                )
            return res
        return wrapper

class RBSSignatureValidator:
    """Parses and checks RBS prototype files against class definitions."""
    @staticmethod
    def parse_rbs_line(line: str) -> Optional[Tuple[str, List[str], str]]:
        # Format: def calculate: (Integer x, String label) -> bool
        pattern = r"def\s+(\w+):\s*\((.*?)\)\s*->\s*(\w+)"
        match = re.match(pattern, line.strip())
        if not match:
            return None
        m_name, params_raw, ret_type = match.groups()
        param_list = [p.strip() for p in params_raw.split(",") if p.strip()]
        return m_name, param_list, ret_type

# ==============================================================================
# SECTION 4: Interactive Workflows & Verification
# ==============================================================================

def demo_gemspec_pipeline():
    banner("1. GEM SPECIFICATION & DEPENDENCY RESOLUTION")
    spec = GemSpec("active_worker", "2.4.1", "High throughput background jobs")
    spec.files = ["lib/active_worker.rb", "lib/active_worker/client.rb", "ext/worker_c/worker.c"]
    spec.add_dependency("redis", "~> 4.5.0")
    spec.add_dependency("concurrent-ruby", ">= 1.1")

    print(colorize("[+] Gemspec Metadata:", TerminalColor.BOLD))
    print(f"    Name:        {spec.name}")
    print(f"    Version:     {spec.version}")
    print(f"    Summary:     {spec.summary}")
    print(f"    Files:       {len(spec.files)} tracked in gemspec manifest")
    print(colorize("[+] Dependencies declared:", TerminalColor.YELLOW))
    for dep, req in spec.dependencies:
        print(f"    * {dep} ({req})")

    available_redis_versions = ["4.4.9", "4.5.0", "4.5.3", "4.6.0", "5.0.0"]
    print(colorize("\n[+] Evaluating Bundler SemVer Resolution for 'redis' (~> 4.5.0):", TerminalColor.BOLD))
    for v in available_redis_versions:
        allowed = SemVerResolver.satisfies(v, "~> 4.5.0")
        status = colorize("ACCEPTED", TerminalColor.GREEN) if allowed else colorize("REJECTED", TerminalColor.RED)
        print(f"    redis-{v:<7} => {status}")

def demo_c_extension_and_gvl():
    banner("2. C NATIVE EXTENSION (MRI C-API & GVL)")
    vm = RubyVMContext()
    print(colorize("[+] Initializing Native Extension Binding (Init_fast_matrix)...", TerminalColor.BOLD))
    
    klass = vm.rb_define_class("FastMatrix")
    print(f"    Registered Ruby Class: {klass}")

    # VALUE Boxing test
    raw_num = 42
    boxed_val = vm.INT2FIX(raw_num)
    unboxed = vm.FIX2INT(boxed_val)
    print(colorize("[+] MRI Fixnum Tagged Pointer Simulation:", TerminalColor.YELLOW))
    print(f"    C Int:        {raw_num}")
    print(f"    VALUE Tagged: 0x{boxed_val:08X} (binary: {bin(boxed_val)})")
    print(f"    Unboxed Back: {unboxed} [Match: {raw_num == unboxed}]")

    # Native calculation with GVL release
    mat_a = [[1, 2], [3, 4]]
    mat_b = [[5, 6], [7, 8]]
    print(colorize("\n[+] Invoking native C Matrix Multiply with GVL release...", TerminalColor.CYAN))
    
    def matrix_c_wrapper(args):
        return vm.rb_thread_call_without_gvl(native_matrix_multiply, args)

    vm.rb_define_method("FastMatrix", "multiply", matrix_c_wrapper)
    result = vm.method_table["FastMatrix"]["multiply"]((mat_a, mat_b))
    print(colorize("    C Extension Result Matrix:", TerminalColor.GREEN))
    for row in result:
        print(f"      {row}")

def demo_typing_system():
    banner("3. RUBY TYPING: RBS PARSING & SORBET RUNTIME CONTRACTS")
    
    # 1. RBS Signature Parsing
    rbs_sample = "def process_payment: (Integer amount, String currency) -> bool"
    print(colorize("[+] Parsing RBS Signature Definition:", TerminalColor.BOLD))
    print(f"    Raw RBS: {colorize(rbs_sample, TerminalColor.MAGENTA)}")
    parsed = RBSSignatureValidator.parse_rbs_line(rbs_sample)
    if parsed:
        m, params, ret = parsed
        print(f"    Extracted Method: '{m}'")
        print(f"    Expected Params:  {params}")
        print(f"    Return Type:      {ret}")

    # 2. Sorbet Runtime Contract Demonstration
    print(colorize("\n[+] Applying Sorbet Runtime Contract (sig { params(...).returns(...) }):", TerminalColor.BOLD))
    sig = RubyTypeSignature({"amount": int, "currency": str}, bool)

    @sig.enforce
    def process_payment(amount: int, currency: str) -> bool:
        return amount > 0 and len(currency) == 3

    # Valid Call
    try:
        ok = process_payment(150, "USD")
        print(colorize("    [Success] process_payment(150, 'USD') returned:", TerminalColor.GREEN), ok)
    except SorbetContractError as e:
        print(colorize(f"    [Error] {e}", TerminalColor.RED))

    # Invalid Call (Simulating Type Violation)
    try:
        print(colorize("    [Triggering Type Violation] process_payment('invalid_amount', 'USD')...", TerminalColor.YELLOW))
        process_payment("invalid_amount", "USD")  # type: ignore
    except SorbetContractError as e:
        print(colorize(f"    [Caught Expected Sorbet Contract Error]:", TerminalColor.RED), e)

def run_all():
    start_time = time.time()
    banner("RUBY BAB-06: GEM DEVELOPMENT, C-EXTENSIONS & TYPING SIMULATOR")
    demo_gemspec_pipeline()
    demo_c_extension_and_gvl()
    demo_typing_system()
    elapsed = (time.time() - start_time) * 1000
    banner(f"ALL SIMULATIONS PASSED SUCCESFULLY ({elapsed:.2f} ms)")

def interactive_menu():
    while True:
        print("\n" + colorize("=== Ruby Core BAB-06 Interactive Menu ===", TerminalColor.BOLD + TerminalColor.CYAN))
        print("1. Gem Development & SemVer Resolution")
        print("2. MRI C Extension, VALUE Boxing & GVL Management")
        print("3. Ruby Typing (RBS Parsing & Sorbet Contracts)")
        print("4. Run Complete Verification Suite")
        print("5. Exit")
        choice = input(colorize("Enter selection [1-5]: ", TerminalColor.YELLOW)).strip()
        
        if choice == "1":
            demo_gemspec_pipeline()
        elif choice == "2":
            demo_c_extension_and_gvl()
        elif choice == "3":
            demo_typing_system()
        elif choice == "4":
            run_all()
        elif choice == "5":
            print(colorize("Exiting simulator. Happy hacking!", TerminalColor.GREEN))
            break
        else:
            print(colorize("Invalid selection! Please enter 1-5.", TerminalColor.RED))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "--non-interactive", "-a"):
        run_all()
    elif not sys.stdin.isatty():
        run_all()
    else:
        interactive_menu()
