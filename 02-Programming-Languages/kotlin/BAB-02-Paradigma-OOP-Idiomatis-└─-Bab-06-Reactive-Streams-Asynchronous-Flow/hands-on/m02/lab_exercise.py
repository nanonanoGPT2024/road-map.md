#!/usr/bin/env python3
"""
Lab Hands-on: Paradigma OOP Idiomatis di Kotlin (Simulasi Runtime Kotlin)
Kategori: 02-Programming-Languages | Bab: 02 - Modul 02 Deep Dive

Script ini memodelkan pilar-pilar OOP idiomatis Kotlin secara mandiri:
1. Delegated Properties ('by lazy', 'by Delegates.observable')
2. Data Classes (auto toString, equals/hashCode, copy(), & componentN destructuring)
3. Sealed Classes & Exhaustive Pattern Matching ('when' expression validation)
4. Companion Objects & Factory Pattern
5. Extension Functions runtime injection
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type


# ============================================================================
# ANSI Formatting Utilities
# ============================================================================
class ConsoleStyle:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    GRAY = "\033[90m"

    @classmethod
    def header(cls, text: str) -> None:
        print(f"\n{cls.BOLD}{cls.CYAN}{'=' * 75}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN} [KOTLIN OOP ENGINE] {text.upper()}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}{'=' * 75}{cls.RESET}")

    @classmethod
    def subheader(cls, text: str) -> None:
        print(f"\n{cls.BOLD}{cls.YELLOW}>>> {text}{cls.RESET}")


# ============================================================================
# 1. Delegated Properties Simulation (lazy & observable)
# ============================================================================
class LazyProperty:
    """Simulasi kata kunci `val x: Type by lazy { initializer() }`"""
    def __init__(self, initializer: Callable[[], Any]):
        self._initializer = initializer
        self._value = None
        self._initialized = False

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if not self._initialized:
            print(f"{ConsoleStyle.GRAY}   [LazyDelegate] Menginisialisasi nilai pertama kali...{ConsoleStyle.RESET}")
            self._value = self._initializer()
            self._initialized = True
        return self._value


class ObservableProperty:
    """Simulasi `var x: Type by Delegates.observable(initial) { prop, old, new -> ... }`"""
    def __init__(self, initial_value: Any, on_change: Callable[[str, Any, Any], None]):
        self._value = initial_value
        self._on_change = on_change
        self._name = ""

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return self._value

    def __set__(self, instance, new_value):
        old_value = self._value
        if old_value != new_value:
            self._value = new_value
            self._on_change(self._name, old_value, new_value)


# ============================================================================
# 2. Data Class Simulation Decorator
# ============================================================================
def kotlin_data_class(cls: Type) -> Type:
    """
    Decorator yang menyuntikkan semantik Kotlin 'data class':
    - Auto copy() dengan field override
    - Structural equality (__eq__) & Hash code
    - Readable string representation (__repr__)
    - Destructuring declarations (component1, component2, dll via __iter__)
    """
    orig_init = cls.__init__

    def copy(self, **kwargs) -> Any:
        current_state = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        current_state.update(kwargs)
        return cls(**current_state)

    def __repr__(self) -> str:
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith('_'))
        return f"{cls.__name__}({attrs})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, cls):
            return False
        return self.__dict__ == other.__dict__

    def __iter__(self):
        # Memungkinkan destructuring: val (id, name, amount) = transaction
        for k, v in sorted(self.__dict__.items()):
            if not k.startswith('_'):
                yield v

    cls.copy = copy
    cls.__repr__ = __repr__
    cls.__eq__ = __eq__
    cls.__iter__ = __iter__
    return cls


# ============================================================================
# 3. Sealed Class & Exhaustive Pattern Matching Engine
# ============================================================================
class SealedClassMeta(type):
    """Metaclass untuk melacak seluruh turunan langsung (closed hierarchy)."""
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        if not hasattr(cls, '_subclasses_set'):
            cls._subclasses_set = set()
        for base in bases:
            if isinstance(base, SealedClassMeta):
                base._subclasses_set.add(cls)


class SealedClass(metaclass=SealedClassMeta):
    """Representasi basis 'sealed class' Kotlin."""
    @classmethod
    def get_subclasses(cls) -> Tuple[Type, ...]:
        return tuple(cls._subclasses_set)


class ExhaustiveMatchError(Exception):
    """Dilempar jika ekspresi 'when' tidak mencakup seluruh varian Sealed Class."""
    pass


def when_sealed(instance: SealedClass, branches: Dict[Type, Callable[[Any], Any]], else_branch: Optional[Callable[[Any], Any]] = None) -> Any:
    """
    Simulasi evaluasi ekspresi `when` Kotlin yang mewajibkan penanganan
    exhaustive untuk Sealed Class tanpa klausul 'else' jika semua subclass terdefinisi.
    """
    sealed_root = None
    for cls in instance.__class__.__mro__:
        if isinstance(cls, SealedClassMeta) and cls is not SealedClass and cls is not object:
            sealed_root = cls
            break

    if sealed_root and not else_branch:
        expected = sealed_root.get_subclasses()
        handled = set(branches.keys())
        missing = [cls.__name__ for cls in expected if cls not in handled]
        if missing:
            raise ExhaustiveMatchError(f"when() expression must be exhaustive! Missing branches: {missing}")

    # Eksekusi branch yang cocok
    for branch_type, handler in branches.items():
        if isinstance(instance, branch_type):
            return handler(instance)

    if else_branch:
        return else_branch(instance)

    raise ValueError(f"No match found for instance {instance} in when expression.")


# ============================================================================
# 4. Extension Functions Injection Engine
# ============================================================================
def extension_function(target_class: Type, func_name: str):
    """Decorator untuk mensimulasikan sintaks 'fun Receiver.extensionMethod()'"""
    def decorator(func: Callable):
        def wrapper(self, *args, **kwargs):
            return func(self, *args, **kwargs)
        setattr(target_class, func_name, wrapper)
        return func
    return decorator


# ============================================================================
# LAB IMPLEMENTATION DOMAIN: Payment Processing Pipeline
# ============================================================================

# Sealed Class Hierarchy
class PaymentResult(SealedClass):
    pass

class PaymentSuccess(PaymentResult):
    def __init__(self, tx_id: str, amount: float):
        self.tx_id = tx_id
        self.amount = amount

class PaymentPending(PaymentResult):
    def __init__(self, tx_id: str, provider: str):
        self.tx_id = tx_id
        self.provider = provider

class PaymentFailed(PaymentResult):
    def __init__(self, tx_id: str, error_code: int, reason: str):
        self.tx_id = tx_id
        self.error_code = error_code
        self.reason = reason


# Domain Model with Data Class & Delegates
@kotlin_data_class
class PaymentRequest:
    def __init__(self, request_id: str, user_id: str, amount: float):
        self.request_id = request_id
        self.user_id = user_id
        self.amount = amount


class PaymentEngine:
    # Companion Object simulation
    class Companion:
        VERSION = "v2.4.0-kotlin-native"

        @staticmethod
        def create_audit_log(entry: str) -> str:
            return f"AUDIT [{time.strftime('%Y-%m-%dT%H:%M:%SZ')}]: {entry}"

    companion = Companion()

    # Delegated Property: Observable
    def _status_listener(self, prop_name: str, old: str, new: str):
        print(f"{ConsoleStyle.MAGENTA}   [Observable] State `{prop_name}` berubah: '{old}' -> '{new}'{ConsoleStyle.RESET}")

    status = ObservableProperty("IDLE", _status_listener)

    # Delegated Property: Lazy
    heavy_encryption_key = LazyProperty(lambda: PaymentEngine._load_rsa_key())

    @staticmethod
    def _load_rsa_key() -> str:
        time.sleep(0.05)  # Simulasi proses decoding/IO berat
        return "RSA-2048-PUB-98a7cf23e59b"

    def execute_transaction(self, request: PaymentRequest) -> PaymentResult:
        self.status = "AUTHENTICATING"
        _ = self.heavy_encryption_key  # Memanggil lazy delegate
        self.status = "PROCESSING"

        if request.amount <= 0:
            self.status = "TERMINATED"
            return PaymentFailed(request.request_id, 400, "Nilai transaksi tidak valid")
        elif request.amount > 1000000:
            self.status = "REQUIRES_VERIFICATION"
            return PaymentPending(request.request_id, "Manual Fraud Check (Escrow)")
        else:
            self.status = "COMPLETED"
            return PaymentSuccess(f"TX-{request.request_id}", request.amount)


# Extension Function pada PaymentRequest
@extension_function(PaymentRequest, "to_audit_summary")
def payment_to_audit(self: PaymentRequest) -> str:
    """Kotlin equivalent: fun PaymentRequest.toAuditSummary(): String"""
    return f"Request ID: {self.request_id} | Client: {self.user_id} | Total: ${self.amount:,.2f}"


# ============================================================================
# Main Execution Pipeline
# ============================================================================
def main():
    ConsoleStyle.header("Kotlin Idiomatic OOP Simulation Lab")

    # 1. Companion Object Verification
    ConsoleStyle.subheader("1. Companion Object & Metadata Inspection")
    print(f"Engine Core Version : {ConsoleStyle.GREEN}{PaymentEngine.companion.VERSION}{ConsoleStyle.RESET}")
    print(PaymentEngine.companion.create_audit_log("PaymentEngine runtime booting initialized."))

    # 2. Data Class Capabilities
    ConsoleStyle.subheader("2. Idiomatic Data Class Semantics (copy, toString, destructure)")
    req1 = PaymentRequest("REQ-101", "usr_john_doe", 450.50)
    print(f"Data Class toString() : {ConsoleStyle.CYAN}{req1}{ConsoleStyle.RESET}")

    # Copy with mutation
    req2 = req1.copy(request_id="REQ-102", amount=1500000.0)
    print(f"Data Class copy()     : {ConsoleStyle.CYAN}{req2}{ConsoleStyle.RESET}")

    # Destructuring (componentN)
    amount, req_id, user = req1  # Iterasi urut alfabetik field non-privat
    print(f"Destructuring Check   : Request ID = {req_id}, User = {user}, Amount = {amount}")

    # Equality check
    req1_clone = PaymentRequest("REQ-101", "usr_john_doe", 450.50)
    print(f"Structural Equality   : req1 == req1_clone -> {ConsoleStyle.GREEN}{req1 == req1_clone}{ConsoleStyle.RESET}")

    # 3. Extension Functions
    ConsoleStyle.subheader("3. Extension Functions Execution")
    # Memanggil method yang disuntikkan secara dinamis
    print(f"Result from Extension : {ConsoleStyle.BOLD}{req1.to_audit_summary()}{ConsoleStyle.RESET}")

    # 4. Delegated Properties (Lazy & Observable) & Processing
    ConsoleStyle.subheader("4. Delegated Properties (Lazy Init & Observable Tracing)")
    engine = PaymentEngine()
    print(f"Engine status awal    : {engine.status}")

    print("Memproses transaksi pertama (req1)...")
    res1 = engine.execute_transaction(req1)

    print("\nMemproses transaksi kedua (req2: High Value)...")
    res2 = engine.execute_transaction(req2)

    invalid_req = PaymentRequest("REQ-103", "usr_hacker", -50.0)
    print("\nMemproses transaksi ketiga (invalid_req)...")
    res3 = engine.execute_transaction(invalid_req)

    # 5. Sealed Class & Exhaustive 'when' Matching
    ConsoleStyle.subheader("5. Sealed Class Exhaustive 'when' Expression Pattern Matching")

    def process_result_in_kotlin_style(result: PaymentResult) -> None:
        handler = {
            PaymentSuccess: lambda r: print(f"  {ConsoleStyle.GREEN}[MATCH: Success] Transaksi {r.tx_id} berhasil! IDR {r.amount:,.2f}{ConsoleStyle.RESET}"),
            PaymentPending: lambda r: print(f"  {ConsoleStyle.YELLOW}[MATCH: Pending] Transaksi {r.tx_id} tertahan di gateway: {r.provider}{ConsoleStyle.RESET}"),
            PaymentFailed:  lambda r: print(f"  {ConsoleStyle.RED}[MATCH: Failed]  Transaksi {r.tx_id} gagal ({r.error_code}): {r.reason}{ConsoleStyle.RESET}")
        }
        when_sealed(result, handler)

    print("Evaluasi res1:")
    process_result_in_kotlin_style(res1)
    print("Evaluasi res2:")
    process_result_in_kotlin_style(res2)
    print("Evaluasi res3:")
    process_result_in_kotlin_style(res3)

    # 6. Simulasi Kegagalan Non-Exhaustive 'when' (Kompilasi/Runtime Error Kotlin)
    ConsoleStyle.subheader("6. Exhaustive Check Violation Test (Simulasi Kotlin Compiler Error)")
    try:
        incomplete_handlers = {
            PaymentSuccess: lambda r: "Success Handled",
            # Sengaja melewatkan PaymentPending & PaymentFailed tanpa else branch
        }
        print("Mencoba mengeksekusi 'when' tanpa penanganan exhaustive...")
        when_sealed(res1, incomplete_handlers)
    except ExhaustiveMatchError as err:
        print(f"{ConsoleStyle.RED}[KOTLIN COMPILER SIMULATED EXCEPTION]: {err}{ConsoleStyle.RESET}")

    ConsoleStyle.header("Lab Selesai: Semua Pola Idiomatis Berhasil Diverifikasi")


if __name__ == "__main__":
    main()