#!/usr/bin/env python3
"""
Laboratorium Simulasi Konsep Fondasi Scala OOP Lanjutan
Modul 01: Trait, Linearization, Case Class, dan Companion Object Simulation
"""

from dataclasses import dataclass, replace
from typing import Any, Tuple, Optional, List
import sys

# ANSI Color Codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"


def header(title: str) -> None:
    border = "=" * 64
    print(f"\n{Color.CYAN}{Color.BOLD}{border}")
    print(f" {title.center(62)} ")
    print(f"{border}{Color.RESET}\n")


def log_step(name: str, desc: str) -> None:
    print(f"{Color.YELLOW}[STEP] {Color.BOLD}{name}{Color.RESET}: {desc}")


def log_success(msg: str) -> None:
    print(f"{Color.GREEN}✔ {msg}{Color.RESET}")


def log_info(msg: str) -> None:
    print(f"{Color.WHITE}  → {msg}{Color.RESET}")


# -----------------------------------------------------------------------------
# 1. SIMULASI SCALA TRAIT LINEARIZATION & STACKABLE MODIFICATIONS
# -----------------------------------------------------------------------------
class BaseQueue:
    """Simulasi abstract class / base trait: IntQueue"""
    def put(self, x: int, call_chain: List[str]) -> int:
        call_chain.append("BaseQueue.put")
        return x


class DoublingMixin:
    """Simulasi trait Doubling extends IntQueue"""
    def put(self, x: int, call_chain: List[str]) -> int:
        call_chain.append("DoublingMixin.put (x2)")
        # super.put dipanggil dalam rantai linearisasi
        return super().put(x * 2, call_chain)  # type: ignore[misc]


class IncrementingMixin:
    """Simulasi trait Incrementing extends IntQueue"""
    def put(self, x: int, call_chain: List[str]) -> int:
        call_chain.append("IncrementingMixin.put (+1)")
        return super().put(x + 1, call_chain)  # type: ignore[misc]


class FilteringMixin:
    """Simulasi trait Filtering extends IntQueue"""
    def put(self, x: int, call_chain: List[str]) -> Optional[int]:
        call_chain.append("FilteringMixin.put (filter x >= 0)")
        if x < 0:
            call_chain.append("FilteringMixin: DISCARDED")
            return None
        return super().put(x, call_chain)  # type: ignore[misc]


# Scala: class QueueA extends BaseQueue with Incrementing with Doubling
# Urutan evaluasi linearization Scala: Right-to-Left (Doubling -> Incrementing -> BaseQueue)
class ScalaQueueVariantA(DoublingMixin, IncrementingMixin, BaseQueue):
    pass


# Scala: class QueueB extends BaseQueue with Doubling with Incrementing
# Urutan evaluasi: Incrementing -> Doubling -> BaseQueue
class ScalaQueueVariantB(IncrementingMixin, DoublingMixin, BaseQueue):
    pass


def demo_linearization() -> None:
    header("1. SIMULASI SCALA TRAIT LINEARIZATION & MIXIN")
    log_info("Di Scala, urutan eksekusi method `super` pada stackable traits diselesaikan")
    log_info("dari KANAN ke KIRI (Right-to-Left order of declaration).")

    # Variant A: Doubling with Incrementing (Doubling dieksekusi duluan di MRO)
    q_a = ScalaQueueVariantA()
    chain_a: List[str] = []
    val_in = 5
    res_a = q_a.put(val_in, chain_a)

    print(f"\n{Color.BOLD}Skenario A (with Incrementing with Doubling):{Color.RESET}")
    print(f"Input: {val_in}")
    print("Call Chain Execution:")
    for idx, c in enumerate(chain_a, 1):
        print(f"  {idx}. {Color.MAGENTA}{c}{Color.RESET}")
    print(f"Hasil Akhir: {Color.GREEN}{res_a}{Color.RESET} (Harapan: (5 * 2) + 1 = 11)")

    # Variant B: Incrementing with Doubling
    q_b = ScalaQueueVariantB()
    chain_b: List[str] = []
    res_b = q_b.put(val_in, chain_b)

    print(f"\n{Color.BOLD}Skenario B (with Doubling with Incrementing):{Color.RESET}")
    print(f"Input: {val_in}")
    print("Call Chain Execution:")
    for idx, c in enumerate(chain_b, 1):
        print(f"  {idx}. {Color.MAGENTA}{c}{Color.RESET}")
    print(f"Hasil Akhir: {Color.GREEN}{res_b}{Color.RESET} (Harapan: (5 + 1) * 2 = 12)")


# -----------------------------------------------------------------------------
# 2. SIMULASI CASE CLASS, EXTRACTOR (unapply), DAN VALUE EQUALITY
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class CasePerson:
    """
    Simulasi Scala:
    case class Person(name: String, age: Int, role: String)
    - Immutability bawaan
    - Value-based equality (bukan referensi pointer)
    - copy() method
    """
    name: str
    age: int
    role: str

    def copy(self, **changes: Any) -> "CasePerson":
        return replace(self, **changes)

    @classmethod
    def unapply(cls, instance: Any) -> Optional[Tuple[str, int, str]]:
        """Simulasi extractor object unapply pada Scala pattern matching"""
        if isinstance(instance, cls):
            return (instance.name, instance.age, instance.role)
        return None


def pattern_match_person(person: Any) -> str:
    """Simulasi konstruksi pattern match Scala: person match { ... }"""
    extracted = CasePerson.unapply(person)
    if extracted is not None:
        name, age, role = extracted
        if role == "Admin":
            return f"Superuser Authorization: Akses Penuh untuk {name} (Usia {age})"
        elif age < 18:
            return f"Junior Profile: {name} membutuhkan supervisi wali"
        else:
            return f"Standard Member: {name}, Usia {age}, Divisi: {role}"
    return "Unknown Entity"


def demo_case_class() -> None:
    header("2. SIMULASI SCALA CASE CLASS & PATTERN MATCHING")

    p1 = CasePerson("Ahmad", 28, "Engineer")
    p2 = CasePerson("Ahmad", 28, "Engineer")
    p3 = p1.copy(role="Admin")

    log_step("Value Equality", "Menguji kesetaraan struktural bawaan case class")
    print(f"p1: {p1}")
    print(f"p2: {p2}")
    print(f"p1 == p2 ? -> {Color.GREEN}{p1 == p2}{Color.RESET} (Identik secara nilai)")
    print(f"p1 is p2 ? -> {Color.YELLOW}{p1 is p2}{Color.RESET} (Instance memori berbeda)")

    log_step("Copy & Immuntability", "Membuat modifikasi record dengan copy()")
    print(f"p3 (modified copy): {Color.CYAN}{p3}{Color.RESET}")

    log_step("Extractor unapply()", "Simulasi Pattern Matching Scala")
    sample_entities = [
        p1,
        p3,
        CasePerson("Budi", 16, "Intern"),
        "Bukan Object Person"
    ]
    for e in sample_entities:
        result = pattern_match_person(e)
        print(f"  Matcher -> {Color.WHITE}{result}{Color.RESET}")


# -----------------------------------------------------------------------------
# 3. SIMULASI COMPANION OBJECT & FACTORY (apply)
# -----------------------------------------------------------------------------
class Currency:
    """Simulasi class Currency dengan private constructor representation"""
    def __init__(self, code: str, amount: float, _token: object):
        if _token is not CurrencyCompanion._SECRET_TOKEN:
            raise PermissionError("Gunakan Companion Object Currency(...) untuk instansiasi!")
        self.code = code
        self.amount = amount

    def __repr__(self) -> str:
        return f"Currency({self.code} {self.amount:,.2f})"


class CurrencyCompanion:
    """
    Simulasi object Currency (Companion Object):
    - Berbagi priviledge akses
    - Menyediakan factory method `apply`
    - Konstanta & caching
    """
    _SECRET_TOKEN = object()
    SUPPORTED = {"IDR", "USD", "EUR", "SGD"}

    @classmethod
    def apply(cls, code: str, amount: float) -> Currency:
        upper_code = code.upper()
        if upper_code not in cls.SUPPORTED:
            raise ValueError(f"Mata uang '{code}' tidak didukung!")
        if amount < 0:
            raise ValueError("Nilai moneter tidak boleh negatif!")
        return Currency(upper_code, amount, cls._SECRET_TOKEN)

    @classmethod
    def idr(cls, amount: float) -> Currency:
        return cls.apply("IDR", amount)


def demo_companion_object() -> None:
    header("3. SIMULASI COMPANION OBJECT & APPLY FACTORY")
    log_info("Di Scala, class dan object dengan nama yang sama dalam satu file saling")
    log_info("memiliki akses penuh ke member private dan sering bertindak sebagai factory.")

    log_step("Factory apply()", "Membuat instance melalui companion object")
    c1 = CurrencyCompanion.apply("USD", 125.50)
    c2 = CurrencyCompanion.idr(3500000.0)

    print(f"Created USD instance: {Color.GREEN}{c1}{Color.RESET}")
    print(f"Created IDR instance: {Color.GREEN}{c2}{Color.RESET}")

    log_step("Private Constructor Protection", "Mencoba bypass Companion Object")
    try:
        # Percobaan instansiasi langsung tanpa token resmi
        Currency("USD", 100.0, object())
    except PermissionError as pe:
        print(f"Terciduk Exception: {Color.RED}{pe}{Color.RESET}")
        log_success("Enkapsulasi berhasil dipertahankan via Companion Object!")


# -----------------------------------------------------------------------------
# 4. SIMULASI SEALED TRAIT (ALGEBRAIC DATA TYPES / ADT)
# -----------------------------------------------------------------------------
class ApiResponseADT:
    """Base Sealed Trait simulation"""
    pass


@dataclass(frozen=True)
class ApiSuccess(ApiResponseADT):
    data: dict
    status_code: int = 200


@dataclass(frozen=True)
class ApiError(ApiResponseADT):
    error_message: str
    status_code: int = 400


@dataclass(frozen=True)
class ApiLoading(ApiResponseADT):
    progress: int = 0


def handle_api_response(response: ApiResponseADT) -> None:
    """Exhaustive pattern matching check"""
    match response:
        case ApiSuccess(data=d, status_code=sc):
            print(f"[{Color.GREEN}SUCCESS {sc}{Color.RESET}] Payload diterima: {d}")
        case ApiError(error_message=em, status_code=sc):
            print(f"[{Color.RED}ERROR {sc}{Color.RESET}] Kegagalan API: {em}")
        case ApiLoading(progress=p):
            print(f"[{Color.YELLOW}LOADING {p}%{Color.RESET}] Sedang mengunduh sumber daya...")
        case _:
            print(f"{Color.RED}Warning: Unhandled ADT branch!{Color.RESET}")


def demo_sealed_trait() -> None:
    header("4. SIMULASI SEALED TRAIT & ALGEBRAIC DATA TYPES (ADT)")
    log_info("Sealed trait membatasi inheritance hanya dalam satu berkas,")
    log_info("memungkinkan compiler memverifikasi exhaustiveness pada pattern matching.")

    responses = [
        ApiLoading(progress=45),
        ApiSuccess(data={"userId": 101, "name": "Dewi Sartika"}),
        ApiError(error_message="Kredensial kadaluarsa", status_code=401)
    ]

    for resp in responses:
        handle_api_response(resp)


# -----------------------------------------------------------------------------
# MAIN CLI RUNNER
# -----------------------------------------------------------------------------
def run_all() -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === SCALA OOP SIMULATION LAB (PYTHON 3 RUNNABLE) === {Color.RESET}")
    demo_linearization()
    demo_case_class()
    demo_companion_object()
    demo_sealed_trait()
    header("LAB VALIDATION & SUMMARY")
    log_success("Semua 4 pilar fondasi Scala OOP Lanjutan berhasil disimulasikan 100%!")
    print(f"{Color.CYAN}Lab exercise selesai tanpa error.{Color.RESET}\n")


if __name__ == "__main__":
    run_all()
