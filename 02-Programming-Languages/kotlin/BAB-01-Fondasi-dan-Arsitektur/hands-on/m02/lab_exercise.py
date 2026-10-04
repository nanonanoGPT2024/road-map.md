#!/usr/bin/env python3
"""
Lab Hands-on: Kotlin Type System & Runtime Engine Simulator (KTS-Sim)
Kategori: 02-Programming-Languages | Bab 01: Fondasi Bahasa & Sistem Tipe Modern - Modul 02

Script ini mensimulasikan mekanisme inti sistem tipe modern Kotlin di tingkat compiler
dan runtime:
 1. Null-Safety Engine (T vs T?, Safe-Call `?.`, Elvis `?:`, Force Unwrap `!!`)
 2. Flow-Sensitive Typing / Smart Cast Analyzer
 3. Sealed Class Hierarchy & Exhaustive Pattern Matching (`when` expression)
 4. Static-Dispatch Extension Function Registry
"""

import sys
import time
from typing import Any, Callable, Dict, Optional, Type, TypeVar

# ANSI Escape Sequences untuk visualisasi terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"

T = TypeVar("T")
R = TypeVar("R")


class KotlinNullPointerException(Exception):
    """Representasi dari kotlin.NullPointerException."""
    pass


class CompilationError(Exception):
    """Representasi kesalahan kompilasi tipe atau exhaustiveness check."""
    pass


# ==============================================================================
# 1. NULL-SAFETY ENGINE (Simulasi Tipe Nullable & Non-Nullable)
# ==============================================================================
class KRef:
    """
    Wrapper referensi yang mensimulasikan pembatasan Nullability Kotlin.
    Jika is_nullable=False, inisialisasi atau mutasi dengan None akan ditolak.
    """
    def __init__(self, value: Optional[Any], is_nullable: bool = False, type_name: str = "Any"):
        self.is_nullable = is_nullable
        self.type_name = type_name
        if not is_nullable and value is None:
            raise CompilationError(
                f"[Compiler Error] Null cannot be a value of a non-null type '{type_name}'"
            )
        self._value = value

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, new_val: Any) -> None:
        if not self.is_nullable and new_val is None:
            raise CompilationError(
                f"[Compiler Error] Cannot assign null to non-null reference of type '{self.type_name}'"
            )
        self._value = new_val

    def safe_call(self, func: Callable[[Any], R]) -> Optional[R]:
        """Operator Safe Call (?.) -> expr?.let { ... }"""
        if self._value is None:
            return None
        return func(self._value)

    def elvis(self, default_value: Any) -> Any:
        """Operator Elvis (?:) -> expr ?: default"""
        return self._value if self._value is not None else default_value

    def force_unwrap(self) -> Any:
        """Operator Not-Null Assertion (!!) -> expr!!"""
        if self._value is None:
            raise KotlinNullPointerException(
                "[Runtime Error] NullPointerException thrown by operator !!"
            )
        return self._value


# ==============================================================================
# 2. EXTENSION FUNCTION REGISTRY (Static Dispatch)
# ==============================================================================
class ExtensionRegistry:
    """
    Simulasi Extension Functions Kotlin:
    Fungsi diperluas ke suatu kelas secara statis tanpa memodifikasi class bytecode asal.
    """
    _registry: Dict[tuple, Callable] = {}

    @classmethod
    def register(cls, target_cls: Type, func_name: str, impl: Callable):
        cls._registry[(target_cls, func_name)] = impl

    @classmethod
    def invoke(cls, receiver: Any, func_name: str, *args, **kwargs):
        target_cls = type(receiver)
        # Resolusi hierarki tipe statis
        for registered_type, name in cls._registry:
            if name == func_name and isinstance(receiver, registered_type):
                return cls._registry[(registered_type, name)](receiver, *args, **kwargs)
        raise AttributeError(f"No extension function '{func_name}' found for {target_cls.__name__}")


# ==============================================================================
# 3. SEALED CLASS & EXHAUSTIVE 'WHEN' SIMULATION
# ==============================================================================
class UiState:
    """Simulasi sealed class UiState."""
    _subclasses: set = set()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        UiState._subclasses.add(cls)


class Loading(UiState):
    def __repr__(self): return "UiState.Loading"


class Success(UiState):
    def __init__(self, data: str):
        self.data = data
    def __repr__(self): return f"UiState.Success(data='{self.data}')"


class Error(UiState):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
    def __repr__(self): return f"UiState.Error(code={self.code}, message='{self.message}')"


def evaluate_ui_state(state: UiState, branches: Dict[Type[UiState], Callable[[Any], str]]) -> str:
    """
    Evaluasi ekspresi `when(state)` Kotlin.
    Memeriksa exhaustive coverage terhadap semua subtipe sealed class.
    """
    handled_types = set(branches.keys())
    missing_branches = UiState._subclasses - handled_types

    # Kotlin menggaransi kelengkapan (exhaustiveness) pada sealed class
    if missing_branches:
        names = [c.__name__ for c in missing_branches]
        raise CompilationError(
            f"[Compiler Error] 'when' expression must be exhaustive, missing: {', '.join(names)}"
        )

    branch_handler = branches.get(type(state))
    if branch_handler:
        return branch_handler(state)
    raise RuntimeError("Unreachable state in exhaustive branch.")


# ==============================================================================
# 4. SMART CAST ANALYZER
# ==============================================================================
class SmartCastContext:
    """
    Simulasi Smart Cast Kotlin:
    Jika compiler mendeteksi `if (obj is TargetType)`, variabel secara otomatis
    dapat diperlakukan sebagai TargetType di dalam blok tersebut.
    """
    @staticmethod
    def process(obj: Any) -> str:
        # Simulasi pemeriksaan flow-typing
        if isinstance(obj, str):
            # Smart-cast ke String: operasi string langsung valid tanpa explicit cast
            return f"{CLR_GREEN}[Smart Cast -> String]{CLR_RESET} Length: {len(obj)}, Upper: '{obj.upper()}'"
        elif isinstance(obj, int):
            # Smart-cast ke Int: operasi numerik
            return f"{CLR_BLUE}[Smart Cast -> Int]{CLR_RESET} Hex: {hex(obj)}, Squared: {obj ** 2}"
        elif isinstance(obj, list):
            # Smart-cast ke List
            return f"{CLR_YELLOW}[Smart Cast -> List]{CLR_RESET} Size: {len(obj)}, First: {obj[0] if obj else 'Empty'}"
        else:
            return f"{CLR_RED}[Unknown Type]{CLR_RESET} Any: {repr(obj)}"


# ==============================================================================
# MAIN TEST SUITE & DEMONSTRATION RUNNER
# ==============================================================================
def print_header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}>>> {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")


def run_lab():
    print(f"{CLR_BOLD}KOTLIN TYPE SYSTEM & FOUNDATIONS (PYTHON ENGINE SIMULATOR){CLR_RESET}")
    print(f"Platform: Python {sys.version.split()[0]} | Environment: Standalone Execution\n")

    # --------------------------------------------------------------------------
    # DEMO 1: Null-Safety Constraints
    # --------------------------------------------------------------------------
    print_header("1. SISTEM NULL-SAFETY: NON-NULL vs NULLABLE")

    # Uji coba assign null ke Non-Null (String)
    try:
        print("[TEST 1.1] Mencoba deklarasi: val name: String = null")
        KRef(None, is_nullable=False, type_name="String")
    except CompilationError as e:
        print(f"  {CLR_RED}✓ Ditolak Compiler:{CLR_RESET} {e}")

    # Deklarasi Nullable (String?)
    print("\n[TEST 1.2] Deklarasi: var nickname: String? = 'kotlin_dev'")
    ref_nullable = KRef("kotlin_dev", is_nullable=True, type_name="String?")
    print(f"  Nilai awal: {ref_nullable.value}")

    ref_nullable.value = None
    print(f"  Setelah mutasi ke null: {ref_nullable.value}")

    # Operator Safe-Call (?.) & Elvis (?:)
    print("\n[TEST 1.3] Operator Safe-Call (?.) & Elvis (?:)")
    safe_result = ref_nullable.safe_call(lambda s: s.upper())
    elvis_result = ref_nullable.safe_call(lambda s: s.upper()) or "ANONYMOUS"
    print(f"  nickname?.uppercase()     -> {safe_result} (Safe!)")
    print(f"  nickname?.uppercase() ?: \"ANONYMOUS\" -> '{elvis_result}'")

    # Operator !! (Not-Null Assertion)
    print("\n[TEST 1.4] Operator !! (Force Unwrap)")
    try:
        print("  Mengeksekusi nickname!!...")
        ref_nullable.force_unwrap()
    except KotlinNullPointerException as e:
        print(f"  {CLR_RED}✓ Exception Ditangkap:{CLR_RESET} {e}")

    # --------------------------------------------------------------------------
    # DEMO 2: Smart Cast Engine
    # --------------------------------------------------------------------------
    print_header("2. FLOW ANALYSIS: SMART CASTING DYNAMICS")
    test_samples = ["Kotlin Multiplatform", 1024, [10, 20, 30], 3.14159]

    for sample in test_samples:
        result = SmartCastContext.process(sample)
        print(f"  Input: {str(sample):<25} Output: {result}")

    # --------------------------------------------------------------------------
    # DEMO 3: Sealed Class Hierarchy & Exhaustive 'when'
    # --------------------------------------------------------------------------
    print_header("3. SEALED CLASSES & EXHAUSTIVE WHEN-EXPRESSIONS")

    states = [Loading(), Success("Payload Synchronized"), Error(404, "Not Found")]

    # Handler exhaustif
    exhaustive_branches = {
        Loading: lambda s: f"{CLR_YELLOW}[LOADING]{CLR_RESET} Spinner active...",
        Success: lambda s: f"{CLR_GREEN}[SUCCESS]{CLR_RESET} Data received: '{s.data}'",
        Error: lambda s: f"{CLR_RED}[ERROR]{CLR_RESET} Code {s.code}: '{s.message}'",
    }

    print("Mengevaluasi cabang exhaustive 'when':")
    for state in states:
        out = evaluate_ui_state(state, exhaustive_branches)
        print(f"  Evaluating {state!r:<35} => {out}")

    print("\n[TEST 3.2] Menguji Non-Exhaustive 'when' (Error branch sengaja dihapus):")
    non_exhaustive = {
        Loading: lambda s: "Loading...",
        Success: lambda s: "Success!",
    }
    try:
        evaluate_ui_state(Success("Test"), non_exhaustive)
    except CompilationError as e:
        print(f"  {CLR_RED}✓ Ditolak Compiler:{CLR_RESET} {e}")

    # --------------------------------------------------------------------------
    # DEMO 4: Extension Functions Engine
    # --------------------------------------------------------------------------
    print_header("4. EXTENSION FUNCTIONS (STATIC RESOLUTION ENGINE)")

    # Menambahkan extension function ke kelas native str
    def mask_credentials(receiver: str, visible_chars: int = 4) -> str:
        """Extension: String.mask(visible_chars: Int = 4)"""
        if len(receiver) <= visible_chars:
            return "*" * len(receiver)
        return receiver[:visible_chars] + ("*" * (len(receiver) - visible_chars))

    ExtensionRegistry.register(str, "mask", mask_credentials)

    raw_token = "kt-sec-9988112233445566"
    masked = ExtensionRegistry.invoke(raw_token, "mask", visible_chars=6)

    print(f"  Original Receiver: {raw_token}")
    print(f"  Extension Applied: rawToken.mask(6) -> {CLR_GREEN}{masked}{CLR_RESET}")

    # --------------------------------------------------------------------------
    # BENCHMARK: Safety vs Raw Overhead
    # --------------------------------------------------------------------------
    print_header("5. PERFORMANCE MICRO-BENCHMARK: NULL-SAFE ACCESS OVERHEAD")
    iterations = 200_000

    # Benchmark Raw Python Access
    start = time.perf_counter()
    raw_val = "Kotlin Native Performance"
    raw_accum = 0
    for _ in range(iterations):
        if raw_val is not None:
            raw_accum += len(raw_val)
    raw_duration = time.perf_counter() - start

    # Benchmark KRef Null-Safe Access
    kref_val = KRef("Kotlin Native Performance", is_nullable=True, type_name="String?")
    start = time.perf_counter()
    safe_accum = 0
    for _ in range(iterations):
        res = kref_val.safe_call(len)
        if res is not None:
            safe_accum += res
    safe_duration = time.perf_counter() - start

    print(f"  Total Iterasi: {iterations:,}")
    print(f"  Direct Primitive Check : {raw_duration:.4f}s (Baseline)")
    print(f"  Kotlin Safe-Call Engine: {safe_duration:.4f}s")
    print(f"  Overhead Faktor        : {safe_duration / raw_duration:.2f}x (Software-Layer Overhead)")

    print(f"\n{CLR_GREEN}{CLR_BOLD}LAB SELESAI: Seluruh simulasi sistem tipe modern Kotlin berhasil dieksekusi.{CLR_RESET}")


if __name__ == "__main__":
    run_lab()