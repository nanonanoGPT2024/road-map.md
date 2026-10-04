#!/usr/bin/env python3
"""
Lab Hands-on: TypeScript Modern Decorators & Enterprise OOP Simulator
Bab 07 (Object-Oriented TypeScript & Modern Decorators) - Modul 02 Deep Dive

Skrip ini mengimplementasikan simulasi runtime engine dari TypeScript 5.x / TC39 Stage 3
Modern Decorator pipeline, sistem metadata reflection (Symbol.metadata), serta
arsitektur OOP berbasis kontrak (Interface/Abstract Class, Access Modifiers, dan Inheritance).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
import functools
import inspect
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type


# ============================================================================
# ANSI Formatting Helper
# ============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def print_step(title: str):
    print(f"\n{Color.BOLD}{Color.CYAN}===[ {title} ]==={Color.RESET}")


def print_sub(title: str):
    print(f"  {Color.MAGENTA}▸ {title}{Color.RESET}")


# ============================================================================
# TC39 Stage 3 / TypeScript 5.0+ Modern Decorator Specification Model
# ============================================================================
class DecoratorKind(Enum):
    CLASS = "class"
    METHOD = "method"
    GETTER = "getter"
    SETTER = "setter"
    FIELD = "field"
    ACCESSOR = "accessor"


@dataclass
class DecoratorContext:
    """
    Merefleksikan spesifikasi resmi TypeScript 5.0 DecoratorContext.
    Menyediakan context metadata, nama anggota, kind, dan hook addInitializer.
    """
    kind: DecoratorKind
    name: str
    metadata: Dict[str, Any]
    is_static: bool = False
    is_private: bool = False
    _initializers: List[Callable[[], None]] = field(default_factory=list)

    def add_initializer(self, initializer: Callable[[], None]) -> None:
        self._initializers.append(initializer)

    def run_initializers(self, instance: Any) -> None:
        for init in self._initializers:
            init(instance)


# Global Symbol.metadata Registry (Emulasi ECMAScript TC39 / TS 5.2+)
METADATA_REGISTRY: Dict[Any, Dict[str, Any]] = {}


def get_metadata(target: Any) -> Dict[str, Any]:
    """Mengambil metadata dictionary dari class target."""
    return METADATA_REGISTRY.setdefault(target, {})


# ============================================================================
# Decorator Implementations (TC39 Signature: (value, context) -> replacement)
# ============================================================================
def ts_method_decorator(decorator_fn: Callable[[Callable, DecoratorContext], Callable]):
    """
    Adapter/Bridge dari Decorator TS Modern (value, context) ke Python function wrapper.
    Memvalidasi context metadata sebelum eksekusi.
    """
    def wrapper_factory(func: Callable) -> Callable:
        context = DecoratorContext(
            kind=DecoratorKind.METHOD,
            name=func.__name__,
            metadata={},
            is_static=False,
            is_private=func.__name__.startswith("__")
        )
        return decorator_fn(func, context)
    return wrapper_factory


def audit_log(target_method: Callable, context: DecoratorContext) -> Callable:
    """
    Method Decorator: Mencatat setiap invokasi method beserta runtime benchmarking.
    Menyimpan log audit langsung ke metadata context.
    """
    context.metadata["audited"] = True

    @functools.wraps(target_method)
    def wrapped(self, *args, **kwargs):
        start = time.perf_counter()
        arg_repr = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
        print(f"    {Color.GRAY}[AUDIT-PRE]{Color.RESET} {self.__class__.__name__}::{context.name}({arg_repr})")
        
        try:
            result = target_method(self, *args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000.0
            print(f"    {Color.GRAY}[AUDIT-POST]{Color.RESET} {self.__class__.__name__}::{context.name} "
                  f"-> {result!r} ({duration_ms:.3f} ms)")
            return result
        except Exception as err:
            duration_ms = (time.perf_counter() - start) * 1000.0
            print(f"    {Color.RED}[AUDIT-FAIL]{Color.RESET} {self.__class__.__name__}::{context.name} "
                  f"failed: {err} ({duration_ms:.3f} ms)")
            raise

    # Daftarkan metadata ke target
    wrapped.__ts_context__ = context
    return wrapped


def authorize(required_role: str):
    """
    Parameterized Method Decorator: Menegakkan Role-Based Access Control (RBAC).
    Membaca security context pada runtime instance.
    """
    def decorator(target_method: Callable, context: DecoratorContext) -> Callable:
        context.metadata["required_role"] = required_role

        @functools.wraps(target_method)
        def wrapped(self, *args, **kwargs):
            current_role = getattr(self, "current_user_role", "GUEST")
            if current_role != required_role:
                raise PermissionError(
                    f"Akses Ditolak ke '{context.name}'! Role yang dibutuhkan: '{required_role}', "
                    f"Role aktual: '{current_role}'"
                )
            return target_method(self, *args, **kwargs)

        wrapped.__ts_context__ = context
        return wrapped
    return ts_method_decorator(decorator)


def memoize(cache_limit: int = 128):
    """
    Method Decorator: Menyimpan cache hasil komputasi berbasis hash argumen.
    Menghindari re-kalkulasi operasi kriptografi/finansial yang berat.
    """
    def decorator(target_method: Callable, context: DecoratorContext) -> Callable:
        cache: Dict[Tuple, Any] = {}
        context.metadata["cached"] = True
        context.metadata["cache_limit"] = cache_limit

        @functools.wraps(target_method)
        def wrapped(self, *args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            if key in cache:
                print(f"    {Color.GREEN}[CACHE-HIT]{Color.RESET} Mengambil nilai dari cache untuk {context.name}{key}")
                return cache[key]
            
            result = target_method(self, *args, **kwargs)
            if len(cache) >= cache_limit:
                cache.pop(next(iter(cache)))  # Simple FIFO eviction
            cache[key] = result
            print(f"    {Color.YELLOW}[CACHE-MISS]{Color.RESET} Menyimpan hasil baru ke cache untuk {context.name}{key}")
            return result

        wrapped.__ts_context__ = context
        return wrapped
    return ts_method_decorator(decorator)


# ============================================================================
# Object-Oriented Domain Layer (Simulasi TypeScript Enterprise OOP)
# ============================================================================

class UserRole(Enum):
    ADMIN = "ADMIN"
    TELLER = "TELLER"
    CUSTOMER = "CUSTOMER"


class IAuditSubject(ABC):
    """Interface simulasi: Setiap entitas harus mengimplementasikan health check & audit."""
    @abstractmethod
    def get_service_status(self) -> Dict[str, Any]:
        pass


class AbstractBankingGateway(ABC, IAuditSubject):
    """
    TypeScript Abstract Class:
    Menyediakan template method pattern dan protected state simulation.
    """
    def __init__(self, gateway_id: str, operating_currency: str):
        self._gateway_id = gateway_id                 # protected equivalent
        self._operating_currency = operating_currency # protected equivalent
        self.__secret_kernel_key = "KRNL-90823-X"     # private (#field) equivalent

    @property
    def currency(self) -> str:
        """TypeScript Readonly Getter"""
        return self._operating_currency

    @abstractmethod
    def execute_settlement(self, source_acc: str, target_acc: str, amount: float) -> str:
        """Abstract method wajib di-override oleh concrete subclass."""
        pass


class EnterpriseCorePaymentProcessor(AbstractBankingGateway):
    """
    Implementasi Konkrit Class yang memanfaatkan Decorators & OOP TS.
    """
    def __init__(self, gateway_id: str, currency: str, current_role: str):
        super().__init__(gateway_id, currency)
        self.current_user_role = current_role
        self._tx_counter = 0

    def get_service_status(self) -> Dict[str, Any]:
        """Implementasi kontrak interface IAuditSubject."""
        return {
            "gateway_id": self._gateway_id,
            "currency": self._operating_currency,
            "tx_processed": self._tx_counter,
            "status": "ONLINE"
        }

    @memoize(cache_limit=4)
    @ts_method_decorator(audit_log)
    def calculate_cross_border_fee(self, amount: float, destination_country: str) -> float:
        """
        Simulasi kalkulasi kurs/biaya yang berat (diberi Decorator @memoize & @audit_log).
        """
        time.sleep(0.08)  # Simulasi latency I/O atau komputasi matematika rumit
        rate_table = {"USA": 0.025, "JPN": 0.018, "SGP": 0.012, "DEU": 0.021}
        rate = rate_table.get(destination_country, 0.035)
        fee = round(amount * rate, 2)
        return fee

    @authorize(required_role=UserRole.ADMIN.value)
    @ts_method_decorator(audit_log)
    def execute_settlement(self, source_acc: str, target_acc: str, amount: float) -> str:
        """
        Operasi kritis: Hanya boleh dipanggil oleh ADMIN. Diberi Decorator @authorize & @audit_log.
        """
        self._tx_counter += 1
        tx_id = f"TXN-{self._operating_currency}-{self._tx_counter:05d}"
        return f"SUCCESS: Dana {amount:.2f} {self.currency} ditransfer dari {source_acc} ke {target_acc} [Ref: {tx_id}]"


# ============================================================================
# Reflection Helper (Menginspeksi Metaprogramming / Decorator Metadata)
# ============================================================================
def reflect_class_architecture(cls: Type[Any]) -> None:
    """Menginspeksi decorators, metadata context, dan class inheritance tree."""
    print_sub(f"Refleksi Arsitektur Kelas: {Color.BOLD}{cls.__name__}{Color.RESET}")
    print(f"    Basis Turunan (MRO): {[c.__name__ for c in cls.mro()[:-1]]}")
    
    # Periksa decorated methods
    methods = [m for m in inspect.getmembers(cls, predicate=inspect.isfunction) if not m[0].startswith("__")]
    for name, method in methods:
        ctx = getattr(method, "__ts_context__", None)
        if ctx:
            print(f"    Method '{Color.GREEN}{name}{Color.RESET}': "
                  f"Kind={ctx.kind.value}, Metadata={ctx.metadata}")
        else:
            print(f"    Method '{name}': Standard Method (Undecorated)")


# ============================================================================
# Main Execution Pipeline (Demonstrasi Interaktif)
# ============================================================================
def main():
    print(f"{Color.BOLD}{Color.BLUE}======================================================================{Color.RESET}")
    print(f"{Color.BOLD}{Color.GREEN}   LAB: TypeScript Modern Decorators & OOP Architecture Engine       {Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}======================================================================{Color.RESET}")

    # 1. Refleksi Struktur Kelas & Metadata
    print_step("1. Reflection & TC39 Decorator Metadata Inspection")
    reflect_class_architecture(EnterpriseCorePaymentProcessor)

    # 2. Testing Memoization & Auditing
    print_step("2. Method Decorators: @memoize & @audit_log Simulation")
    processor = EnterpriseCorePaymentProcessor(
        gateway_id="GTW-CENTRAL-01",
        currency="USD",
        current_role=UserRole.ADMIN.value
    )

    print("  Memanggil 'calculate_cross_border_fee' pertama kali (Cache Miss diharapkan):")
    fee1 = processor.calculate_cross_border_fee(10_000.0, "JPN")
    print(f"  Biaya: ${fee1}")

    print("\n  Memanggil 'calculate_cross_border_fee' kedua kali dengan parameter identik (Cache Hit):")
    fee2 = processor.calculate_cross_border_fee(10_000.0, "JPN")
    print(f"  Biaya: ${fee2}")

    print("\n  Memanggil 'calculate_cross_border_fee' dengan parameter negara baru:")
    fee3 = processor.calculate_cross_border_fee(10_000.0, "SGP")
    print(f"  Biaya: ${fee3}")

    # 3. Testing RBAC Access Control Guard
    print_step("3. Security Guard Decorator: @authorize(ADMIN) Execution")
    try:
        print("  Eksekusi transaksi settlement sebagai ADMIN:")
        res = processor.execute_settlement("ACC-10029", "ACC-99812", 250_000.0)
        print(f"  {Color.GREEN}✔ Hasil: {res}{Color.RESET}")
    except PermissionError as e:
        print(f"  {Color.RED}✘ Gagal: {e}{Color.RESET}")

    # Ubah role menjadi unauthorized
    print("\n  Simulasi eskalasi hak akses / sesi unauthorized (CUSTOMER):")
    processor.current_user_role = UserRole.CUSTOMER.value

    try:
        print("  Eksekusi transaksi settlement sebagai CUSTOMER (Harus Ditolak Decorator):")
        processor.execute_settlement("ACC-10029", "ACC-99812", 500.0)
    except PermissionError as e:
        print(f"  {Color.RED}✔ Tertangkap Sesuai Desain Keamanan: {e}{Color.RESET}")

    # 4. Interface Compliance Verification
    print_step("4. Interface/Contract Compliance (IAuditSubject)")
    status = processor.get_service_status()
    for k, v in status.items():
        print(f"    • {k:<15}: {Color.BOLD}{v}{Color.RESET}")

    print(f"\n{Color.BOLD}{Color.GREEN}✔ Lab Berhasil: Pola TypeScript Modern Decorators & OOP tervalidasi sempurna.{Color.RESET}\n")


if __name__ == "__main__":
    main()