#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Type System & Static Analysis Engine
Bab 02: Advanced Type System & Static Analysis - Modul 02 Deep Dive

Mendemonstrasikan:
1. Structural Subtyping (Protocols & Runtime Checkable)
2. Generic Variance & Typed Contract Pipeline
3. Runtime Type Enforcement via Type Hint Introspection
4. Micro-AST Static Code Analyzer (Linter rule engine for typing invariants)
"""

import ast
import inspect
import sys
import time
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Protocol,
    Tuple,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
    runtime_checkable,
)

# --- ANSI Terminal Color Codes ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"


# ==============================================================================
# 1. Structural Subtyping via Protocols
# ==============================================================================

@runtime_checkable
class Serializable(Protocol):
    """Protocol mendefinisikan antarmuka struktural tanpa inheritance formal."""
    def serialize(self) -> Dict[str, Any]: ...
    def get_id(self) -> str: ...


class UserPayload:
    """Mengimplementasikan protokol Serializable secara struktural (Duck Typing)."""
    def __init__(self, user_id: str, email: str):
        self.user_id = user_id
        self.email = email

    def serialize(self) -> Dict[str, Any]:
        return {"id": self.user_id, "email": self.email}

    def get_id(self) -> str:
        return self.user_id


class IncompletePayload:
    """Gagal memenuhi Serializable karena tidak mengimplementasikan serialize()."""
    def __init__(self, token: str):
        self.token = token

    def get_id(self) -> str:
        return self.token


# ==============================================================================
# 2. Generics & Runtime Contract Validation
# ==============================================================================

T_Serializable = TypeVar("T_Serializable", bound=Serializable)
R = TypeVar("R")


class EventDispatcher(Generic[T_Serializable]):
    """Generic container yang memproses entity dengan batas atas (bound) Serializable."""
    def __init__(self) -> None:
        self._registry: List[T_Serializable] = []

    def register(self, item: T_Serializable) -> None:
        if not isinstance(item, Serializable):
            raise TypeError(f"Objek '{type(item).__name__}' melanggar kontrak protokol Serializable!")
        self._registry.append(item)

    def dispatch_all(self) -> List[Dict[str, Any]]:
        return [entry.serialize() for entry in self._registry]


def enforce_types(func: Callable[..., R]) -> Callable[..., R]:
    """
    Decorator metatyping: Memvalidasi kesesuaian tipe argumen dan return value
    pada runtime menggunakan type introspection (typing.get_type_hints).
    """
    hints = get_type_hints(func)
    sig = inspect.signature(func)

    def _validate_value(param_name: str, value: Any, expected_type: Any) -> None:
        origin = get_origin(expected_type)
        args = get_args(expected_type)

        if origin is Union:
            if not any(_is_instance_loose(value, arg) for arg in args):
                raise TypeError(
                    f"Argumen '{param_name}' bernilai {repr(value)} bertipe {type(value).__name__}, "
                    f"ekspektasi Union: {expected_type}"
                )
        elif origin is list:
            if not isinstance(value, list):
                raise TypeError(f"Argumen '{param_name}' harus berupa list, bukan {type(value).__name__}")
            if args:
                item_type = args[0]
                for idx, item in enumerate(value):
                    if not _is_instance_loose(item, item_type):
                        raise TypeError(
                            f"Elemen list '{param_name}[{idx}]' bernilai {repr(item)} melanggar sub-tipe {item_type}"
                        )
        else:
            if not _is_instance_loose(value, expected_type):
                raise TypeError(
                    f"Parameter '{param_name}' menerima tipe {type(value).__name__}, "
                    f"ekspektasi tipe: {expected_type}"
                )

    def _is_instance_loose(val: Any, target_type: Any) -> bool:
        if target_type is Any:
            return True
        target_origin = get_origin(target_type) or target_type
        if isinstance(target_origin, type):
            return isinstance(val, target_origin)
        return True

    def wrapper(*args: Any, **kwargs: Any) -> R:
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        for param_name, value in bound_args.arguments.items():
            if param_name in hints:
                _validate_value(param_name, value, hints[param_name])

        result = func(*args, **kwargs)

        if "return" in hints:
            expected_ret = hints["return"]
            if expected_ret is not None and not _is_instance_loose(result, expected_ret):
                raise TypeError(
                    f"Return value fungsi '{func.__name__}' bertipe {type(result).__name__}, "
                    f"melanggar deklarasi: {expected_ret}"
                )
        return result

    return wrapper


# ==============================================================================
# 3. Static AST Type Analyzer (Micro Static Analysis Engine)
# ==============================================================================

class StaticLintDiagnostic:
    def __init__(self, line: int, col: int, rule: str, message: str, severity: str = "ERROR"):
        self.line = line
        self.col = col
        self.rule = rule
        self.message = message
        self.severity = severity

    def __str__(self) -> str:
        color = CLR_RED if self.severity == "ERROR" else CLR_YELLOW
        return f"{color}[{self.severity}] (L{self.line}:C{self.col}) {self.rule}: {self.message}{CLR_RESET}"


class TypeSafetyASTVisitor(ast.NodeVisitor):
    """
    AST Visitor untuk menganalisis AST Python secara statis tanpa eksekusi:
    - Rule 101: Argumen fungsi tidak memiliki type annotation.
    - Rule 102: Fungsi tidak memiliki return type annotation.
    - Rule 103: Penggunaan mutable default argument (list/dict/set).
    """
    def __init__(self) -> None:
        self.diagnostics: List[StaticLintDiagnostic] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Rule 102: Missing Return Annotation
        if node.returns is None and not node.name.startswith("_"):
            self.diagnostics.append(
                StaticLintDiagnostic(
                    node.lineno, node.col_offset, "TYP102",
                    f"Fungsi publik '{node.name}' tidak memiliki deklarasi tipe return (missing '-> type')."
                )
            )

        # Rule 101: Missing Argument Annotation
        for arg in node.args.args:
            if arg.arg == "self" or arg.arg == "cls":
                continue
            if arg.annotation is None:
                self.diagnostics.append(
                    StaticLintDiagnostic(
                        arg.lineno, arg.col_offset, "TYP101",
                        f"Argumen '{arg.arg}' pada fungsi '{node.name}' tidak memiliki type annotation."
                    )
                )

        # Rule 103: Dangerous Mutable Default Arguments
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.diagnostics.append(
                    StaticLintDiagnostic(
                        default.lineno, default.col_offset, "SEC103",
                        f"Mutable default argument terdeteksi pada definisi fungsi '{node.name}'."
                    )
                )

        self.generic_visit(node)


class StaticCodeAnalyzer:
    """Wrapper untuk menjalankan static analysis AST ke source text."""
    @staticmethod
    def analyze(source_code: str) -> List[StaticLintDiagnostic]:
        tree = ast.parse(source_code)
        visitor = TypeSafetyASTVisitor()
        visitor.visit(tree)
        return visitor.diagnostics


# ==============================================================================
# 4. Target Domain Functions for Simulation
# ==============================================================================

@enforce_types
def calculate_tax(base_amount: float, rate_multiplier: float) -> float:
    """Menghitung nilai pajak dengan validasi tipe ketat."""
    return base_amount * rate_multiplier


@enforce_types
def process_batch(identifiers: List[int], mode: str) -> List[str]:
    """Memproses sekumpulan identifier numerik."""
    return [f"{mode.upper()}-0x{item:04X}" for item in identifiers]


# Sample source snippets to test static analysis engine
VALID_SNIPPET = """
def compute_metrics(delta_ms: int, scale: float) -> float:
    return delta_ms * scale
"""

DEFECTIVE_SNIPPET = """
def bad_worker(task_id, data=[], debug=True):
    val = data
    return val

def run_untyped(x):
    return x * 2
"""


# ==============================================================================
# 5. Execution Runner & Visual Feedback
# ==============================================================================

def print_header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== {title} ==={CLR_RESET}")


def run_lab() -> None:
    print(f"{CLR_BOLD}{CLR_BLUE}================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE} LAB ENGINE: ADVANCED TYPE SYSTEM & STATIC ANALYSIS (DEEP DIVE) {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}================================================================{CLR_RESET}")

    # TEST 1: Structural Subtyping (Protocol)
    print_header("1. Structural Subtyping & Protocol Verification")
    user = UserPayload("usr-9081", "dev_ops@system.internal")
    broken = IncompletePayload("tok-secret-555")

    print(f"Instansi UserPayload: is Serializable? -> "
          f"{CLR_GREEN if isinstance(user, Serializable) else CLR_RED}{isinstance(user, Serializable)}{CLR_RESET}")
    print(f"Instansi IncompletePayload: is Serializable? -> "
          f"{CLR_GREEN if isinstance(broken, Serializable) else CLR_RED}{isinstance(broken, Serializable)}{CLR_RESET}")

    dispatcher: EventDispatcher[UserPayload] = EventDispatcher()
    dispatcher.register(user)
    print(f"Payload terdaftar di Dispatcher: {dispatcher.dispatch_all()}")

    try:
        print("Mencoba meregistrasi IncompletePayload ke EventDispatcher...")
        dispatcher.register(broken)  # type: ignore
    except TypeError as exc:
        print(f"{CLR_YELLOW}[INTERCEPTED CONTRACT VIOLATION]{CLR_RESET} {exc}")

    # TEST 2: Dynamic Runtime Type Enforcement via Type Hints
    print_header("2. Runtime Type Enforcement & Signature Introspection")
    res_tax = calculate_tax(150000.0, 0.11)
    print(f"Tax execution normal (150000.0, 0.11): {CLR_GREEN}{res_tax}{CLR_RESET}")

    try:
        print("Memanggil calculate_tax('150000', 0.11) dengan string...")
        calculate_tax("150000", 0.11)  # type: ignore
    except TypeError as exc:
        print(f"{CLR_YELLOW}[INTERCEPTED TYPE VIOLATION]{CLR_RESET} {exc}")

    res_batch = process_batch([10, 255, 1024], "sync")
    print(f"Batch execution valid: {CLR_GREEN}{res_batch}{CLR_RESET}")

    try:
        print("Memanggil process_batch([10, '255', 1024], 'sync') dengan elemen list invalid...")
        process_batch([10, "255", 1024], "sync")  # type: ignore
    except TypeError as exc:
        print(f"{CLR_YELLOW}[INTERCEPTED TYPE VIOLATION]{CLR_RESET} {exc}")

    # TEST 3: AST Static Code Analyzer Simulation
    print_header("3. AST Static Analysis & Linter Rule Pipeline")

    print("Menganalisis kode sumber valid via AST Analyzer:")
    diag_valid = StaticCodeAnalyzer.analyze(VALID_SNIPPET)
    if not diag_valid:
        print(f"{CLR_GREEN}[PASS] Valid code bebas dari anomali typing.{CLR_RESET}")
    else:
        for diag in diag_valid:
            print(f"  {diag}")

    print("\nMenganalisis source code dengan kecacatan tipe (DEFECTIVE_SNIPPET):")
    diag_defective = StaticCodeAnalyzer.analyze(DEFECTIVE_SNIPPET)
    print(f"Ditemukan {len(diag_defective)} pelanggaran statis:")
    for diag in diag_defective:
        print(f"  {diag}")

    print(f"\n{CLR_BOLD}{CLR_GREEN}Pipeline Advanced Typing & Static Engine Selesai Dieksekusi dengan Sukses.{CLR_RESET}")


if __name__ == "__main__":
    t_start = time.perf_counter()
    run_lab()
    t_end = time.perf_counter()
    print(f"\n{CLR_BLUE}Total Execution Latency: {(t_end - t_start) * 1000:.3f} ms{CLR_RESET}")
    sys.exit(0)