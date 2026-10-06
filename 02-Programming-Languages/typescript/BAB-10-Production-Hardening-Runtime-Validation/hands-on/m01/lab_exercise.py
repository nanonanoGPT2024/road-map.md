#!/usr/bin/env python3
"""
TypeScript Production Hardening & Runtime Validation Simulator
Hands-on Lab Exercise: M01 - Runtime Schema Validation & Boundary Defense

Konsep yang disimulasikan:
1. Type Erasure Boundary & Unsafe JSON Ingestion
2. Zod/TypeBox-style Composable Schema Validation Engine
3. Result Pattern (SafeParse vs Parse with Error Paths)
4. Nominal / Branded Types Simulation
5. Unknown Type Narrowing & Custom Type Guard Verification
"""

import sys
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

# ANSI Terminal Styling
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BG_DARK = "\033[48;5;236m"

def print_header(title: str) -> None:
    line = "=" * 65
    print(f"\n{Style.CYAN}{Style.BOLD}{line}")
    print(f" {title.center(63)} ")
    print(f"{line}{Style.RESET}\n")

def print_status(label: str, status: bool, message: str = "") -> None:
    tag = f"{Style.GREEN}[PASS]{Style.RESET}" if status else f"{Style.RED}[FAIL]{Style.RESET}"
    detail = f" - {Style.DIM}{message}{Style.RESET}" if message else ""
    print(f" {tag} {Style.BOLD}{label}{Style.RESET}{detail}")

# -------------------------------------------------------------------------
# Core Schema Engine (Mimicking Zod in TypeScript)
# -------------------------------------------------------------------------

class ValidationError(Exception):
    def __init__(self, issues: List[Dict[str, Any]]):
        super().__init__("Validation failed")
        self.issues = issues

class ValidationResult:
    def __init__(self, success: bool, data: Any = None, errors: Optional[List[Dict[str, Any]]] = None):
        self.success = success
        self.data = data
        self.errors = errors or []

    def __repr__(self) -> str:
        if self.success:
            return f"SafeParseSuccess(data={self.data})"
        return f"SafeParseError(errors={self.errors})"

class BaseSchema:
    def parse(self, value: Any) -> Any:
        res = self.safe_parse(value)
        if not res.success:
            raise ValidationError(res.errors)
        return res.data

    def safe_parse(self, value: Any, path: str = "root") -> ValidationResult:
        raise NotImplementedError

class StringSchema(BaseSchema):
    def __init__(self):
        self._min_len: Optional[int] = None
        self._regex: Optional[Tuple[re.Pattern, str]] = None

    def min(self, length: int) -> 'StringSchema':
        self._min_len = length
        return self

    def email(self) -> 'StringSchema':
        pattern = re.compile(r"^[\w\.-]+@([\w-]+\.)+[\w-]{2,4}$")
        self._regex = (pattern, "Format email tidak valid")
        return self

    def safe_parse(self, value: Any, path: str = "root") -> ValidationResult:
        if not isinstance(value, str):
            return ValidationResult(False, errors=[{"path": path, "expected": "string", "received": type(value).__name__}])
        
        if self._min_len is not None and len(value) < self._min_len:
            return ValidationResult(False, errors=[{
                "path": path,
                "code": "too_small",
                "message": f"Panjang string minimal {self._min_len} karakter"
            }])
            
        if self._regex is not None:
            regex_pat, msg = self._regex
            if not regex_pat.match(value):
                return ValidationResult(False, errors=[{"path": path, "code": "invalid_string", "message": msg}])

        return ValidationResult(True, data=value)

class NumberSchema(BaseSchema):
    def __init__(self):
        self._min_val: Optional[float] = None
        self._is_int: bool = False

    def min(self, val: float) -> 'NumberSchema':
        self._min_val = val
        return self

    def int(self) -> 'NumberSchema':
        self._is_int = True
        return self

    def safe_parse(self, value: Any, path: str = "root") -> ValidationResult:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return ValidationResult(False, errors=[{"path": path, "expected": "number", "received": type(value).__name__}])
        
        if self._is_int and not isinstance(value, int):
            return ValidationResult(False, errors=[{"path": path, "code": "invalid_type", "message": "Expected integer"}])

        if self._min_val is not None and value < self._min_val:
            return ValidationResult(False, errors=[{
                "path": path,
                "code": "too_small",
                "message": f"Nilai angka minimal {self._min_val}"
            }])

        return ValidationResult(True, data=value)

class ObjectSchema(BaseSchema):
    def __init__(self, shape: Dict[str, BaseSchema], strict: bool = True):
        self.shape = shape
        self.strict = strict

    def safe_parse(self, value: Any, path: str = "root") -> ValidationResult:
        if not isinstance(value, dict):
            return ValidationResult(False, errors=[{"path": path, "expected": "object", "received": type(value).__name__}])

        cleaned_data: Dict[str, Any] = {}
        all_errors: List[Dict[str, Any]] = []

        # Validate shape
        for key, schema in self.shape.items():
            field_path = f"{path}.{key}" if path != "root" else key
            if key not in value:
                all_errors.append({"path": field_path, "code": "required", "message": f"Field '{key}' wajib diisi"})
                continue
            
            field_result = schema.safe_parse(value[key], path=field_path)
            if not field_result.success:
                all_errors.extend(field_result.errors)
            else:
                cleaned_data[key] = field_result.data

        # Check unknown keys in strict mode
        if self.strict:
            for key in value.keys():
                if key not in self.shape:
                    field_path = f"{path}.{key}" if path != "root" else key
                    all_errors.append({"path": field_path, "code": "unrecognized_key", "message": f"Field tidak dikenal '{key}' (Strict Mode)"})

        if all_errors:
            return ValidationResult(False, errors=all_errors)
        return ValidationResult(True, data=cleaned_data)

# -------------------------------------------------------------------------
# TypeScript Concepts Demonstrator
# -------------------------------------------------------------------------

def demo_type_erasure_hazard():
    print_header("DEMO 1: The TypeScript Type Erasure Dilemma")
    print(f"{Style.YELLOW}[Context]{Style.RESET} Di compile-time TypeScript, tipe data melindungi Anda.")
    print(f"Tetapi di runtime browser/Node.js, semua tipe terhapus (Type Erasure).")
    print(f"Data eksternal (fetch API/DB) bertipe `{Style.MAGENTA}unknown{Style.RESET}`, bukan tipe yang Anda deklarasikan!\n")

    untrusted_payload = '{"id": 101, "email": "admin@example.com", "role": "admin", "injected_hack": true}'
    print(f"{Style.BOLD}Raw Ingested JSON:{Style.RESET} {untrusted_payload}")

    # Definisi skema runtime Zod-style
    UserSchema = ObjectSchema({
        "id": NumberSchema().int().min(1),
        "email": StringSchema().email(),
        "role": StringSchema().min(3)
    }, strict=True)

    print(f"\n{Style.CYAN}Menjalankan SafeParse Runtime Guard...{Style.RESET}")
    parsed = json.loads(untrusted_payload)
    result = UserSchema.safe_parse(parsed)

    if not result.success:
        print_status("Strict Schema Ingestion", False, "Mencegah data kotor masuk sistem!")
        print(f"  {Style.RED}Rejected issues detected:{Style.RESET}")
        for err in result.errors:
            print(f"   -> Path: {Style.YELLOW}{err['path']}{Style.RESET} | Error: {err['message']}")
    else:
        print_status("Strict Schema Ingestion", True, "Data bersih tervalidasi")

def demo_branded_types():
    print_header("DEMO 2: Branded Types & Invariant Enforcement")
    print(f"{Style.YELLOW}[Context]{Style.RESET} Nominal Typing vs Structural Typing.")
    print("TypeScript menggunakan Structural Typing. String UserId dan String Email bisa saling tertukar tanpa compile error.")
    print(f"Solusi Production: {Style.CYAN}Branded / Flavoring Types{Style.RESET} via Runtime Constructor/Smart Constructor.\n")

    class UserId:
        def __init__(self, raw: str):
            if not re.match(r"^usr_[a-zA-Z0-9]{8}$", raw):
                raise ValueError(f"Invalid UserId brand: '{raw}'. Format harus 'usr_<8_alphanumeric>'")
            self._value = raw

        @property
        def value(self) -> str:
            return self._value

        def __repr__(self) -> str:
            return f"UserId<{self._value}>"

    valid_id = "usr_99abx123"
    invalid_id = "plain_string_12"

    try:
        branded = UserId(valid_id)
        print_status("Brand Verification (Valid Token)", True, f"Berhasil dicap sebagai {branded}")
    except ValueError as e:
        print_status("Brand Verification (Valid Token)", False, str(e))

    try:
        branded_bad = UserId(invalid_id)
        print_status("Brand Verification (Invalid Token)", False, f"Seharusnya gagal: {branded_bad}")
    except ValueError as e:
        print_status("Brand Verification (Invalid Token)", True, f"Ditolak secara ketat: {e}")

def run_interactive_suite():
    print_header("INTERACTIVE LABORATORY SUITE: BAB-10")
    print(f"{Style.BOLD}Pilih skenario pengujian runtime hardening:{Style.RESET}")
    print(" 1. Jalankan Analisis Type Erasure Hazard (Strict Parsing)")
    print(" 2. Uji Branded Types & Domain Invariants")
    print(" 3. Uji Kustom Payload JSON Interaktif")
    print(" 4. Jalankan Semua Skenario Uji Otomatis")
    print(" 5. Keluar")

    choice = input(f"\n{Style.CYAN}Masukkan nomor opsi [1-5]: {Style.RESET}").strip()

    if choice == "1":
        demo_type_erasure_hazard()
    elif choice == "2":
        demo_branded_types()
    elif choice == "3":
        interactive_json_tester()
    elif choice == "4":
        demo_type_erasure_hazard()
        demo_branded_types()
        print(f"\n{Style.GREEN}{Style.BOLD}✓ Semua skenario otomatis berhasil dieksekusi.{Style.RESET}\n")
    elif choice == "5":
        print(f"\n{Style.YELLOW}Sesi lab diakhiri.{Style.RESET}")
        sys.exit(0)
    else:
        print(f"\n{Style.RED}Pilihan tidak valid. Menjalankan semua skenario secara default.{Style.RESET}")
        demo_type_erasure_hazard()
        demo_branded_types()

def interactive_json_tester():
    print_header("DEMO 3: Custom JSON Ingestion Tester")
    print("Skema target:")
    print("  id: integer (min 1)")
    print("  email: string (email valid)")
    print("  role: string (min 3 char)")
    print("Strict mode: AKTIF (tidak mengizinkan kolom tambahan)\n")

    default_sample = '{"id": 42, "email": "dev@typescript.org", "role": "engineer"}'
    user_input = input(f"Masukkan JSON [Tekan Enter untuk contoh: {default_sample}]:\n").strip()
    if not user_input:
        user_input = default_sample

    schema = ObjectSchema({
        "id": NumberSchema().int().min(1),
        "email": StringSchema().email(),
        "role": StringSchema().min(3)
    }, strict=True)

    try:
        raw_obj = json.loads(user_input)
    except json.JSONDecodeError as err:
        print(f"{Style.RED}Format JSON rusak:{Style.RESET} {err}")
        return

    result = schema.safe_parse(raw_obj)
    if result.success:
        print(f"\n{Style.GREEN}{Style.BOLD}SUCCESS! Data aman masuk ke runtime engine:{Style.RESET}")
        print(json.dumps(result.data, indent=2))
    else:
        print(f"\n{Style.RED}{Style.BOLD}REJECTED! Data melanggar type contract:{Style.RESET}")
        for err in result.errors:
            print(f" - [{err.get('path')}]: {err.get('message') or err.get('code')}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        demo_type_erasure_hazard()
        demo_branded_types()
    else:
        run_interactive_suite()
