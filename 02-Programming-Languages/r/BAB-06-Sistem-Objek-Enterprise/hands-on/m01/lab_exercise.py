#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Internal Sistem Objek Enterprise R (S3, S4, R6, S7)
Kategori: R Programming - Enterprise Object-Oriented Systems
File: hands-on/m01/lab_exercise.py
"""

from __future__ import annotations
import sys
import copy
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type


# ANSI Escape Codes untuk Visualisasi Terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {title.upper()} === {Color.RESET}\n")


def log_step(name: str, desc: str) -> None:
    print(f"{Color.CYAN}[STEP]{Color.RESET} {Color.BOLD}{name}{Color.RESET}: {desc}")


def log_info(msg: str) -> None:
    print(f"  {Color.BLUE}ℹ{Color.RESET} {msg}")


def log_success(msg: str) -> None:
    print(f"  {Color.GREEN}✓{Color.RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"  {Color.YELLOW}⚠ {msg}{Color.RESET}")


def log_error(msg: str) -> None:
    print(f"  {Color.RED}✖ {msg}{Color.RESET}")


# ==============================================================================
# 1. SIMULATOR SISTEM S3 (Informal, Attribute-based, Single Dispatch UseMethod)
# ==============================================================================
class S3Object:
    """Simulasi struktur S3 di R: Data dasar + list attribute 'class'."""
    def __init__(self, data: Any, classes: List[str]):
        self.data = copy.deepcopy(data)
        self.attributes: Dict[str, Any] = {"class": list(classes)}

    @property
    def class_vector(self) -> List[str]:
        return self.attributes.get("class", ["default"])

    def __repr__(self) -> str:
        return f"<S3Object classes={self.class_vector} data={self.data}>"


class S3GenericRegistry:
    """Simulasi UseMethod() dispatch table milik R S3."""
    def __init__(self, generic_name: str):
        self.generic_name = generic_name
        self.methods: Dict[str, Callable[[S3Object], str]] = {}

    def register_method(self, class_name: str, fn: Callable[[S3Object], str]) -> None:
        self.methods[class_name] = fn

    def dispatch(self, obj: S3Object) -> str:
        log_info(f"S3 UseMethod('{self.generic_name}') memicu traversal vector class: {obj.class_vector}")
        for cls in obj.class_vector:
            candidate = cls
            if candidate in self.methods:
                log_success(f"Resolusi Method Berhasil: '{self.generic_name}.{candidate}'")
                return self.methods[candidate](obj)
            log_warn(f"Method '{self.generic_name}.{candidate}' tidak ditemukan. Mencoba fallback...")

        if "default" in self.methods:
            log_warn(f"Fallback ke method default: '{self.generic_name}.default'")
            return self.methods["default"](obj)

        raise AttributeError(f"Tidak ada method S3 yang cocok untuk '{self.generic_name}' pada class {obj.class_vector}")


# ==============================================================================
# 2. SIMULATOR SISTEM S4 (Formal Slots, Strict Validation, Multi-Dispatch)
# ==============================================================================
class S4ClassDef:
    """Simulasi setClass(): Mendefinisikan slots tipe ketat & validator."""
    def __init__(self, name: str, slots: Dict[str, Type], validator: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None):
        self.name = name
        self.slots = slots
        self.validator = validator


class S4Object:
    """Simulasi new('ClassName', ...): Formal slot storage."""
    def __init__(self, class_def: S4ClassDef, **kwargs):
        self.class_def = class_def
        self.slot_values: Dict[str, Any] = {}

        # Slot type conformance check
        for slot_name, expected_type in class_def.slots.items():
            if slot_name not in kwargs:
                raise TypeError(f"S4 Error: Slot wajib '{slot_name}' bertipe {expected_type.__name__} belum diinisialisasi")
            val = kwargs[slot_name]
            if not isinstance(val, expected_type):
                raise TypeError(f"S4 Validation Error: Slot '{slot_name}' mengharapkan {expected_type.__name__}, diterima {type(val).__name__}")
            self.slot_values[slot_name] = val

        # Custom validator execution
        if class_def.validator:
            err = class_def.validator(self.slot_values)
            if err:
                raise ValueError(f"S4 Custom Validity Failure ({class_def.name}): {err}")


class S4Generic:
    """Simulasi setGeneric() dan setMethod() dengan multi-signature dispatch."""
    def __init__(self, name: str):
        self.name = name
        self.table: Dict[Tuple[str, ...], Callable[..., str]] = {}

    def set_method(self, signature: Tuple[str, ...], method_fn: Callable[..., str]) -> None:
        self.table[signature] = method_fn

    def dispatch(self, *objects: S4Object) -> str:
        sig = tuple(obj.class_def.name for obj in objects)
        log_info(f"S4 Multi-Dispatch Signature: {sig}")
        if sig in self.table:
            log_success(f"Ditemukan exact signature method untuk {sig}")
            return self.table[sig](*objects)
        raise NotImplementedError(f"S4 dispatch gagal: Tidak ada implementasi {self.name} untuk signature {sig}")


# ==============================================================================
# 3. SIMULATOR SISTEM R6 (Reference Semantics, Encapsulation, State Mutation)
# ==============================================================================
class R6Simulator:
    """
    Simulasi R6Class() environment:
    - Reference semantics (modifikasi di tempat, bukan Copy-on-Modify)
    - Enkapsulasi: Public vs Private fields
    """
    def __init__(self, name: str, public_init: Dict[str, Any], private_init: Dict[str, Any]):
        self._classname = name
        self._id = id(self)
        self._public: Dict[str, Any] = copy.deepcopy(public_init)
        self._private: Dict[str, Any] = copy.deepcopy(private_init)
        self._locked = False

    def get_public(self, key: str) -> Any:
        return self._public.get(key)

    def set_public(self, key: str, value: Any) -> None:
        if self._locked:
            raise PermissionError("R6 Environment terkunci: instance berstatus read-only/locked")
        self._public[key] = value

    def deposit_via_private(self, amount: float) -> None:
        """Contoh method public yang memanipulasi private state."""
        if amount <= 0:
            raise ValueError("Nominal transaksi harus positif")
        old_bal = self._private.get("balance", 0.0)
        new_bal = old_bal + amount
        self._private["balance"] = new_bal
        self._private["audit_log"].append(f"+{amount} @ {time.strftime('%H:%M:%S')}")
        self._public["last_modified"] = time.strftime("%H:%M:%S")

    def inspect_state(self) -> str:
        return (f"R6<{self._classname}> @ MemoryAddr:{hex(self._id)}\n"
                f"    Public:  {self._public}\n"
                f"    Private: {{'balance': {self._private.get('balance')}, "
                f"'audit_count': {len(self._private.get('audit_log', []))}}}")

    def clone(self, deep: bool = False) -> R6Simulator:
        log_info(f"Mengeksekusi $clone(deep={deep})...")
        if not deep:
            # Shallow clone
            cloned = copy.copy(self)
            cloned._id = id(cloned)
            return cloned
        else:
            # Deep clone
            cloned = copy.deepcopy(self)
            cloned._id = id(cloned)
            return cloned


# ==============================================================================
# 4. MODUL PRAKTIKUM & DEMONSTRASI TEKNIKAL INTERAKTIF
# ==============================================================================
def demo_s3_system() -> None:
    header("Lab 1: Simulasi S3 Dynamic Dispatch & Class Hierarchy")
    log_step("Inisialisasi Generic", "Membangun generic function 'summary'")
    summary_generic = S3GenericRegistry("summary")

    # Mendaftarkan method implementation
    summary_generic.register_method("lm", lambda obj: f"[lm summary]: Residual standard error: {obj.data.get('rse')}")
    summary_generic.register_method("glm", lambda obj: f"[glm summary]: AIC: {obj.data.get('aic')}, Family: {obj.data.get('family')}")
    summary_generic.register_method("default", lambda obj: f"[default summary]: Raw representation: {str(obj.data)}")

    # Objek 1: Class hierarki ['glm', 'lm']
    obj_glm = S3Object(data={"aic": 210.4, "family": "binomial", "rse": 0.45}, classes=["glm", "lm"])
    print(f"\nTarget S3: {obj_glm}")
    res1 = summary_generic.dispatch(obj_glm)
    print(f"Hasil Dispatch: {Color.BOLD}{res1}{Color.RESET}\n")

    # Objek 2: Polymorphism fallback ke 'lm' jika subkelas tidak ada
    obj_custom = S3Object(data={"rse": 0.12, "weights": [1, 2, 3]}, classes=["robust_lm", "lm"])
    print(f"Target S3 Subclass: {obj_custom}")
    res2 = summary_generic.dispatch(obj_custom)
    print(f"Hasil Dispatch: {Color.BOLD}{res2}{Color.RESET}\n")

    # Objek 3: Fallback ke default
    obj_raw = S3Object(data="Vector Numerik 1:100", classes=["vector", "numeric"])
    print(f"Target S3 Tanpa Method Spesifik: {obj_raw}")
    res3 = summary_generic.dispatch(obj_raw)
    print(f"Hasil Dispatch: {Color.BOLD}{res3}{Color.RESET}\n")


def demo_s4_system() -> None:
    header("Lab 2: Simulasi S4 Formal Slots & Multi-Dispatch")
    log_step("Definisi Class Formal", "Membuat class 'PortfolioRisk' dengan slot tertipe dan validator")

    def risk_validator(slots: Dict[str, Any]) -> Optional[str]:
        if slots["var_95"] < 0:
            return "Value at Risk (VaR 95%) tidak boleh bernilai negatif!"
        if not (0.0 <= slots["confidence_level"] <= 1.0):
            return "Confidence level harus berada pada rentang [0.0, 1.0]"
        return None

    portfolio_class = S4ClassDef(
        name="PortfolioRisk",
        slots={"portfolio_name": str, "var_95": float, "confidence_level": float, "is_active": bool},
        validator=risk_validator
    )

    log_step("Validasi Sukses", "Membuat instance yang memenuhi invariant")
    inst = S4Object(portfolio_class, portfolio_name="Global Tech Fund", var_95=1450000.50, confidence_level=0.95, is_active=True)
    log_success(f"Instance S4 valid terbentuk: {inst.slot_values}")

    log_step("Validasi Gagal (Slot Type Mismatch)", "Mencoba mengisi slot float dengan tipe string")
    try:
        S4Object(portfolio_class, portfolio_name="Invalid Fund", var_95="TIDAK_VALID", confidence_level=0.95, is_active=True)
    except TypeError as e:
        log_error(f"Ditangkap oleh S4 type-checker: {e}")

    log_step("Validasi Gagal (Business Invariant)", "Mencoba mengisi confidence_level = 1.8 (> 1.0)")
    try:
        S4Object(portfolio_class, portfolio_name="Invalid Fund", var_95=200.0, confidence_level=1.8, is_active=True)
    except ValueError as e:
        log_error(f"Ditangkap oleh S4 custom validity: {e}")

    log_step("Multi-Dispatch S4", "Generic 'audit_against' memerlukan signature (PortfolioRisk, MarketRegulator)")
    regulator_class = S4ClassDef(name="MarketRegulator", slots={"code": str, "threshold": float})
    regulator = S4Object(regulator_class, code="OJK-FIN-01", threshold=2000000.0)

    audit_generic = S4Generic("audit_against")
    audit_generic.set_method(
        ("PortfolioRisk", "MarketRegulator"),
        lambda p, r: f"Audit Passed: Portfolio '{p.slot_values['portfolio_name']}' VaR {p.slot_values['var_95']} < Threshold {r.slot_values['threshold']}"
    )

    audit_res = audit_generic.dispatch(inst, regulator)
    print(f"Hasil Multi-Dispatch: {Color.BOLD}{Color.GREEN}{audit_res}{Color.RESET}\n")


def demo_r6_system() -> None:
    header("Lab 3: Simulasi R6 Reference Semantics & Mutasi State")
    log_step("Inisialisasi R6 Class", "Membuat objek 'EnterpriseAccount' dengan private state")

    acc1 = R6Simulator(
        name="EnterpriseAccount",
        public_init={"account_number": "ACC-ID-9921", "owner": "PT Inovasi Finansial", "last_modified": "00:00:00"},
        private_init={"balance": 500_000_000.0, "audit_log": ["Akun Dibuat"]}
    )

    print(f"Instance Awal (acc1):\n{acc1.inspect_state()}\n")

    log_step("Reference Semantics vs Copy-on-Modify", "Menetapkan alias acc2 = acc1")
    acc2 = acc1  # Referensi alamat yang persis sama
    log_info(f"acc1 id: {hex(id(acc1))}")
    log_info(f"acc2 id: {hex(id(acc2))}")

    log_step("Mutasi via Method", "Mendepositkan dana 250,000,000 melalui acc2")
    acc2.deposit_via_private(250_000_000.0)

    print(f"\n{Color.YELLOW}Periksa acc1 (terbukti termutasi secara in-place karena Reference Semantics):{Color.RESET}")
    print(f"{acc1.inspect_state()}\n")

    log_step("Deep Clone", "Melakukan clone terpisah untuk memutus referensi memori")
    acc_cloned = acc1.clone(deep=True)
    acc_cloned.deposit_via_private(50_000_000.0)
    print(f"acc_cloned (Alamat berbeda {hex(id(acc_cloned))}):\n{acc_cloned.inspect_state()}\n")
    print(f"acc1 Asli tetap stabil:\n{acc1.inspect_state()}\n")


def interactive_menu() -> None:
    banner = f"""{Color.BOLD}{Color.CYAN}
╔═════════════════════════════════════════════════════════════════════╗
║  ENTERPRISE R OBJECT SYSTEM (S3, S4, R6, S7) INTERACTIVE SIMULATOR  ║
║         Architecture & Runtime Dispatch Engine Demonstration        ║
╚═════════════════════════════════════════════════════════════════════╝{Color.RESET}"""
    print(banner)

    while True:
        print(f"\n{Color.BOLD}Pilihan Praktikum:{Color.RESET}")
        print("  1. Uji Mekanisme S3 (Informal Class Vector & Dynamic Dispatch UseMethod)")
        print("  2. Uji Mekanisme S4 (Formal Typed Slots, Validity Checks & Multi-Dispatch)")
        print("  3. Uji Mekanisme R6 (Reference Semantics, Encapsulation & Mutasi State)")
        print("  4. Jalankan Semua Uji Rancang Bangun Sekaligus (Comprehensive Lab Test)")
        print("  5. Keluar (Exit)")

        try:
            choice = input(f"\n{Color.CYAN}Masukkan nomor pilihan (1-5): {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nProses selesai.")
            break

        if choice == "1":
            demo_s3_system()
        elif choice == "2":
            demo_s4_system()
        elif choice == "3":
            demo_r6_system()
        elif choice == "4":
            demo_s3_system()
            demo_s4_system()
            demo_r6_system()
        elif choice == "5":
            print(f"\n{Color.GREEN}Terima kasih telah menjalankan simulator Enterprise R Object System.{Color.RESET}\n")
            break
        else:
            log_warn("Pilihan tidak valid. Silakan pilih 1-5.")


if __name__ == "__main__":
    # Jika dijalankan secara non-interaktif (piped/CI), jalankan mode otomatis
    if not sys.stdin.isatty():
        header("Non-Interactive Environment Detected: Running Automated Full Suite")
        demo_s3_system()
        demo_s4_system()
        demo_r6_system()
    else:
        interactive_menu()
