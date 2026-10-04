#!/usr/bin/env python3
"""
Lab Hands-on: Arsitektur Sistem Objek R (S3, S4, R6) & Metaprogramming Engine
Bab 06: Sistem Objek Enterprise & Non-Standard Evaluation (NSE)

Skrip ini mengimplementasikan runtime simulasi yang memodelkan secara presisi
semantik internal bahasa pemrograman R:
1. S3 Dispatcher: Single dispatch informal berbasis atribut kelas vektor.
2. S4 Engine: Validasi skema slot ketat & Multiple Dispatch Matrix.
3. R6 Framework: Objek semantik referensi (in-place mutation) dengan active bindings.
4. Tidy Metaprogramming / NSE: Non-Standard Evaluation, quosure capture, dan data-masking.
"""

import sys
import copy
import inspect
from typing import Any, Callable, Dict, List, Tuple, Type, Optional

# --- PALET WARNA ANSI ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_MAGENTA= "\033[35m"
CLR_CYAN   = "\033[36m"
CLR_GRAY   = "\033[90m"

def print_banner(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}[LAB MODULE] {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*75}{CLR_RESET}")

def print_substep(tag: str, msg: str):
    print(f"  {CLR_BOLD}{CLR_BLUE}▶{CLR_RESET} {CLR_BOLD}{tag:<16}{CLR_RESET} : {msg}")

def print_success(msg: str):
    print(f"  {CLR_BOLD}{CLR_GREEN}✔ [SUCCESS]{CLR_RESET} {msg}")

def print_alert(msg: str):
    print(f"  {CLR_BOLD}{CLR_YELLOW}⚠ [DISPATCH]{CLR_RESET} {msg}")


# =============================================================================
# MODUL 1: S3 OBJECT SYSTEM (Informal OOP & Vector-based Single Dispatch)
# =============================================================================

class S3Object:
    """Representasi objek R S3: Objek dasar dengan atribut kelas bertingkat."""
    def __init__(self, data: Any, classes: List[str]):
        self.data = data
        self.classes = classes  # Hierarki inheritance berbasis array string

    def __repr__(self):
        return f"<S3Object classes={self.classes} data={self.data}>"

class S3Generic:
    """Implementasi generic function S3 R (seperti print, summary, plot)."""
    def __init__(self, name: str):
        self.name = name
        self.method_table: Dict[str, Callable] = {}

    def register(self, class_name: str, method: Callable):
        """Mendaftarkan method dengan konvensi generic.class."""
        self.method_table[class_name] = method

    def __call__(self, obj: Any, *args, **kwargs):
        """Melakukan traversal pada vektor kelas hingga menemukan metode yang cocok."""
        if isinstance(obj, S3Object):
            for cls in obj.classes:
                if cls in self.method_table:
                    print_alert(f"S3 Dispatch: {self.name}() -> {self.name}.{cls}")
                    return self.method_table[cls](obj.data, *args, **kwargs)
        
        # Fallback ke default method
        if "default" in self.method_table:
            print_alert(f"S3 Dispatch: {self.name}() fallback -> {self.name}.default")
            raw_data = obj.data if isinstance(obj, S3Object) else obj
            return self.method_table["default"](raw_data, *args, **kwargs)
        
        raise NotImplementedError(f"Metode S3 '{self.name}' tidak ditemukan untuk kelas {getattr(obj, 'classes', type(obj))}")


# =============================================================================
# MODUL 2: S4 OBJECT SYSTEM (Formal Schema Validation & Multiple Dispatch)
# =============================================================================

class S4ClassRegistry:
    """Katalog kelas formal S4 yang mendefinisikan slots dan tipe data."""
    _classes: Dict[str, Dict[str, Type]] = {}

    @classmethod
    def setClass(cls, class_name: str, slots: Dict[str, Type]):
        cls._classes[class_name] = slots
        print_substep("S4 ClassDef", f"Kelas '{class_name}' terdaftar dengan slots: {list(slots.keys())}")

class S4Object:
    """Objek formal S4 dengan validasi integritas tipe slot saat inisialisasi."""
    def __init__(self, class_name: str, **slot_values):
        if class_name not in S4ClassRegistry._classes:
            raise TypeError(f"Kelas S4 '{class_name}' belum didefinisikan!")
        
        schema = S4ClassRegistry._classes[class_name]
        self._class_name = class_name
        self._slots: Dict[str, Any] = {}

        for slot_name, expected_type in schema.items():
            if slot_name not in slot_values:
                raise ValueError(f"Slot '{slot_name}' wajib diisi untuk kelas '{class_name}'")
            val = slot_values[slot_name]
            if not isinstance(val, expected_type):
                raise TypeError(f"Slot '{slot_name}' harus bertipe {expected_type.__name__}, bukan {type(val).__name__}")
            self._slots[slot_name] = val

    def get_slot(self, name: str) -> Any:
        return self._slots[name]

    def set_slot(self, name: str, value: Any):
        expected_type = S4ClassRegistry._classes[self._class_name][name]
        if not isinstance(value, expected_type):
            raise TypeError(f"Tipe slot tidak valid: {type(value).__name__} != {expected_type.__name__}")
        self._slots[name] = value

    def __repr__(self):
        return f"<S4 '{self._class_name}' slots={self._slots}>"

class S4Generic:
    """Engine Multiple Dispatch S4 R: Memilih metode berdasarkan tanda tangan n-tuple."""
    def __init__(self, name: str, signature_len: int):
        self.name = name
        self.sig_len = signature_len
        self.signatures: Dict[Tuple[str, ...], Callable] = {}

    def setMethod(self, signature: Tuple[str, ...], impl: Callable):
        if len(signature) != self.sig_len:
            raise ValueError(f"Panjang signature harus tepat {self.sig_len}")
        self.signatures[signature] = impl

    def __call__(self, *args, **kwargs):
        if len(args) < self.sig_len:
            raise ValueError(f"Generic '{self.name}' membutuhkan minimal {self.sig_len} argumen untuk dispatch.")
        
        actual_sig = []
        for arg in args[:self.sig_len]:
            if isinstance(arg, S4Object):
                actual_sig.append(arg._class_name)
            else:
                actual_sig.append(type(arg).__name__)
        
        sig_tuple = tuple(actual_sig)
        if sig_tuple in self.signatures:
            print_alert(f"S4 Multi-Dispatch: {self.name}{sig_tuple}")
            return self.signatures[sig_tuple](*args, **kwargs)
        
        raise NotImplementedError(f"Metode S4 '{self.name}' tidak didefinisikan untuk kombinasi {sig_tuple}")


# =============================================================================
# MODUL 3: R6 OBJECT SYSTEM (Encapsulated OOP, Mutable References & Active Bindings)
# =============================================================================

class R6ClassGenerator:
    """Metaclass & Factory R6: Mengisolasi public, private, active bindings, serta deep clone."""
    def __init__(self, classname: str, public: Dict[str, Any], private: Optional[Dict[str, Any]] = None,
                 active: Optional[Dict[str, Tuple[Callable, Optional[Callable]]]] = None):
        self.classname = classname
        self.public_blueprint = public
        self.private_blueprint = private or {}
        self.active_blueprint = active or {}

    def new(self, *args, **kwargs):
        return _R6Instance(self.classname, self.public_blueprint, self.private_blueprint, self.active_blueprint, *args, **kwargs)

class _R6Instance:
    def __init__(self, classname: str, public: Dict[str, Any], private: Dict[str, Any],
                 active: Dict[str, Tuple[Callable, Optional[Callable]]], *args, **kwargs):
        # Alokasi internal environment
        self._classname = classname
        self._private_env = copy.deepcopy(private)
        self._public_methods = {}
        self._public_fields = {}
        self._active_bindings = active

        # Inisialisasi public fields dan bind 'self' & 'private' ke methods
        for k, v in public.items():
            if callable(v):
                self._public_methods[k] = v
            else:
                self._public_fields[k] = copy.deepcopy(v)

        # Trigger initialize() jika didefinisikan
        if "initialize" in self._public_methods:
            self._public_methods["initialize"](self, self._private_env, *args, **kwargs)

    def __getattr__(self, item: str):
        if item in self._public_fields:
            return self._public_fields[item]
        if item in self._public_methods:
            # Bind callable dynamically passing self and private
            return lambda *args, **kwargs: self._public_methods[item](self, self._private_env, *args, **kwargs)
        if item in self._active_bindings:
            getter, _ = self._active_bindings[item]
            return getter(self, self._private_env)
        raise AttributeError(f"Instance R6 '{self._classname}' tidak memiliki member publik '{item}'")

    def __setattr__(self, key: str, value: Any):
        if key in ("_classname", "_private_env", "_public_methods", "_public_fields", "_active_bindings"):
            super().__setattr__(key, value)
            return

        if key in self._active_bindings:
            _, setter = self._active_bindings[key]
            if setter is None:
                raise AttributeError(f"Active binding '{key}' adalah READ-ONLY!")
            setter(self, self._private_env, value)
            return

        if key in self._public_fields:
            self._public_fields[key] = value
            return

        raise AttributeError(f"Member publik '{key}' tidak terdaftar pada skema R6 '{self._classname}'")

    def clone(self, deep: bool = False):
        """Kloning eksplisit semantik R6."""
        print_alert(f"R6 Cloner: Menduplikasi instance {self._classname} (deep={deep})")
        if not deep:
            # Shallow clone
            inst = _R6Instance.__new__(_R6Instance)
            inst._classname = self._classname
            inst._private_env = self._private_env
            inst._public_methods = self._public_methods
            inst._public_fields = self._public_fields
            inst._active_bindings = self._active_bindings
            return inst
        else:
            return copy.deepcopy(self)


# =============================================================================
# MODUL 4: METAPROGRAMMING & TIDY EVALUATION (AST Defusal, Quoting & Data-Mask)
# =============================================================================

class Quosure:
    """Enkapsulasi unevaluated expression bersama lexical environment-nya."""
    def __init__(self, expr_str: str, env: Dict[str, Any]):
        self.expr_str = expr_str
        self.env = env

    def __repr__(self):
        return f"<Quosure: `{self.expr_str}` with env_keys={list(self.env.keys())}>"

def enquo(expr_str: str, caller_frame_offset: int = 1) -> Quosure:
    """Defuse ekspresi dan capture frame variabel lokal pemanggil (mirip rlang::enquo)."""
    frame = inspect.currentframe()
    for _ in range(caller_frame_offset):
        if frame and frame.f_back:
            frame = frame.f_back
    env_snapshot = frame.f_locals.copy() if frame else {}
    return Quosure(expr_str, env_snapshot)

def eval_tidy(quo: Quosure, data_mask: Dict[str, Any]) -> Any:
    """Evaluasi quosure di mana data_mask mendahului environment leksikal objek."""
    print_alert(f"NSE Eval: Mengevaluasi `{quo.expr_str}` dengan data-masking")
    # Masking priority: data_mask overrides quo.env overrides built-in functions
    combined_scope = {}
    combined_scope.update(quo.env)
    combined_scope.update(data_mask)
    return eval(quo.expr_str, {}, combined_scope)


# =============================================================================
# EKSEKUSI INTEGRASI DAN TEST-SUITE ENTERPRISE
# =============================================================================

def run_lab():
    print_banner("1. SIMULASI POLIMORFISME S3 (INFORMAL DISPATCH)")
    # Setup Generic
    generic_render = S3Generic("render_report")
    
    # Register Methods
    generic_render.register("financial_risk", lambda d: f"[S3-FinancialReport] Portofolio VaR: ${d['var_millions']}M | Status: {d['risk_tier']}")
    generic_render.register("tabular", lambda d: f"[S3-Tabular] Kolom: {list(d.keys())} | Baris: {len(next(iter(d.values())))}")
    generic_render.register("default", lambda d: f"[S3-DefaultFallback] Format teks standar: {str(d)}")

    # Objek dengan inheritance S3: subclass mewarisi 'tabular'
    obj_credit_risk = S3Object(
        data={"var_millions": 4.82, "risk_tier": "HIGH_EXPOSURE"},
        classes=["financial_risk", "tabular", "default"]
    )
    
    obj_raw_table = S3Object(
        data={"id": [101, 102], "symbol": ["AAPL", "GOOG"]},
        classes=["tabular", "default"]
    )
    
    obj_primitive = S3Object(data=9999.45, classes=["scalar_metric"])

    print_substep("Exec S3", generic_render(obj_credit_risk))
    print_substep("Exec S3", generic_render(obj_raw_table))
    print_substep("Exec S3", generic_render(obj_primitive))
    print_success("S3 single dispatch hierarchy berhasil diverifikasi.")

    print_banner("2. SISTEM OBJEK S4 FORMAL (SLOT ENFORCEMENT & MULTIPLE DISPATCH)")
    S4ClassRegistry.setClass("CorporateBond", {
        "ticker": str,
        "notional": float,
        "yield_rate": float
    })
    S4ClassRegistry.setClass("CreditRatingAgency", {
        "name": str,
        "min_grade": str
    })

    bond = S4Object("CorporateBond", ticker="ACME-CORP", notional=50_000_000.0, yield_rate=0.065)
    agency = S4Object("CreditRatingAgency", name="MoodyStandard", min_grade="BBB")

    print_substep("Instansiasi S4", f"Bond Instance: {bond}")
    print_substep("Instansiasi S4", f"Agency Instance: {agency}")

    # Validasi slot type checking
    try:
        print_substep("Strict Type Check", "Mencoba mengisi slot notional dengan string (ilegal)...")
        bond.set_slot("notional", "INVALID_NOTIONAL_STRING")
    except TypeError as e:
        print_success(f"Type Constraint bekerja: {e}")

    # Multiple Dispatch: collide(CorporateBond, CreditRatingAgency)
    evaluate_risk = S4Generic("evaluate_bond_risk", signature_len=2)

    def _eval_bond_agency(b: S4Object, a: S4Object) -> str:
        score = (b.get_slot("yield_rate") * 100) / 2.0
        return f"Hasil Analisis: {a.get_slot('name')} mengevaluasi {b.get_slot('ticker')} -> Skor Risiko: {score:.2f}"

    evaluate_risk.setMethod(("CorporateBond", "CreditRatingAgency"), _eval_bond_agency)
    result = evaluate_risk(bond, agency)
    print_substep("Multiple Dispatch", result)
    print_success("S4 Formal Slots dan Multiple Dispatch sukses dieksekusi.")

    print_banner("3. ARSITEKTUR R6: REFERENCE SEMANTICS & ACTIVE BINDINGS")
    
    # Factory methods & active bindings
    def acc_init(self, private, account_id: str, initial_balance: float):
        private["id"] = account_id
        private["balance"] = initial_balance

    def acc_deposit(self, private, amount: float):
        if amount <= 0:
            raise ValueError("Deposit harus positif")
        private["balance"] += amount
        return private["balance"]

    def acc_get_balance(self, private):
        return private["balance"]

    def acc_set_balance(self, private, val):
        raise PermissionError("Direct balance overwrite dilarang! Gunakan deposit()")

    def acc_get_id(self, private):
        return private["id"]

    BankAccountR6 = R6ClassGenerator(
        classname="EnterpriseBankAccount",
        public={
            "initialize": acc_init,
            "deposit": acc_deposit,
            "currency": "USD"
        },
        private={
            "id": None,
            "balance": 0.0
        },
        active={
            "balance": (acc_get_balance, acc_set_balance),
            "account_id": (acc_get_id, None)
        }
    )

    acc1 = BankAccountR6.new(account_id="ACC-CORP-9801", initial_balance=1000.0)
    print_substep("R6 Read Active", f"ID: {acc1.account_id} | Saldo: ${acc1.balance} {acc1.currency}")

    # Semantik Referensi: Mutasi in-place
    acc1.deposit(750.0)
    print_substep("R6 Mutation", f"Saldo setelah deposit: ${acc1.balance}")

    # Test Shallow Assignment (Reference Semantic)
    acc_alias = acc1
    acc_alias.deposit(250.0)
    print_substep("Ref Semantic", f"Saldo acc1 setelah acc_alias diubah: ${acc1.balance} (Harus 2000.0)")
    assert acc1.balance == 2000.0

    # Deep Clone
    acc_cloned = acc1.clone(deep=True)
    acc_cloned.deposit(500.0)
    print_substep("Clone Isolation", f"Saldo Original: ${acc1.balance} | Saldo Kloning: ${acc_cloned.balance}")
    assert acc1.balance == 2000.0 and acc_cloned.balance == 2500.0

    # Read-Only Active Binding Check
    try:
        acc1.account_id = "ILLEGAL_WRITE"
    except AttributeError as e:
        print_success(f"Proteksi Active Binding Read-Only terbukti: {e}")

    print_banner("4. METAPROGRAMMING & TIDY EVALUATION (NON-STANDARD EVALUATION)")
    # Mocking Data Frame (Context Masking)
    market_dataframe = {
        "price": 150.0,
        "volume": 2000,
        "spread": 0.25
    }

    # Context Frame Caller
    market_tax_rate = 0.12  # Diambil dari Lexical Environment pemanggil

    # Ekstrak formula tanpa dievaluasi terlebih dahulu (Defused AST)
    unevaluated_code = "(price * volume) * (1 - market_tax_rate) - (volume * spread)"
    quo = enquo(unevaluated_code)
    print_substep("Quosure Captured", f"{quo}")

    # Evaluasi dengan data mask mendahului lexical environment
    net_liquidity = eval_tidy(quo, data_mask=market_dataframe)
    expected = (150.0 * 2000) * (1 - 0.12) - (2000 * 0.25)
    print_substep("NSE Output", f"Evaluated Value = ${net_liquidity:,.2f}")
    assert net_liquidity == expected
    print_success("Tidy data masking evaluasi sukses tanpa runtime leak.")

    print_banner("LAB SELESAI: SEMUA SUBSISTEM R BERFUNGSI SEMPURNA")

if __name__ == "__main__":
    run_lab()
