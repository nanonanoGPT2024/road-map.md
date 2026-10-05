#!/usr/bin/env python3
"""
Lab Exercise: Django Forms Processing Pipeline & Formsets Simulation
Fokus: Siklus full_clean(), clean_<field>(), clean(), ValidationError,
       cleaned_data dictionary, serta arsitektur ManagementForm pada Formsets.
"""

import sys
import re
from typing import Any, Dict, List, Optional, Callable


# ==============================================================================
# ANSI Color Palette untuk Output Terminal Interaktif
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[40m"


def header(title: str):
    print(f"\n{Color.BOLD}{Color.BLUE}{'=' * 72}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} [DJANGO FORMS PIPELINE LAB] {title}{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}{'=' * 72}{Color.RESET}")


def step(label: str, detail: str):
    print(f"{Color.BOLD}{Color.YELLOW}▶ {label:<22}:{Color.RESET} {detail}")


def success(msg: str):
    print(f"  {Color.GREEN}✔ {msg}{Color.RESET}")


def fail(msg: str):
    print(f"  {Color.RED}✘ {msg}{Color.RESET}")


def info(msg: str):
    print(f"  {Color.DIM}ℹ {msg}{Color.RESET}")


# ==============================================================================
# Django Validation Error Primitives
# ==============================================================================
class ValidationError(Exception):
    """Representasi eksepsi validasi form Django."""
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code


# ==============================================================================
# Field Classes & Built-in Validators
# ==============================================================================
class Field:
    def __init__(self, required: bool = True, validators: Optional[List[Callable]] = None):
        self.required = required
        self.validators = validators or []

    def to_python(self, value: Any) -> Any:
        return value

    def validate(self, value: Any):
        if value in (None, "") and self.required:
            raise ValidationError("This field is required.", code="required")

    def run_validators(self, value: Any):
        if value in (None, ""):
            return
        for v in self.validators:
            v(value)

    def clean(self, value: Any) -> Any:
        value = self.to_python(value)
        self.validate(value)
        self.run_validators(value)
        return value


class CharField(Field):
    def __init__(self, max_length: Optional[int] = None, min_length: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.max_length = max_length
        self.min_length = min_length

    def to_python(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def validate(self, value: str):
        super().validate(value)
        if self.max_length and len(value) > self.max_length:
            raise ValidationError(
                f"Ensure this value has at most {self.max_length} characters (it has {len(value)}).",
                code="max_length",
            )
        if self.min_length and len(value) < self.min_length:
            raise ValidationError(
                f"Ensure this value has at least {self.min_length} characters (it has {len(value)}).",
                code="min_length",
            )


class IntegerField(Field):
    def __init__(self, min_value: Optional[int] = None, max_value: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value

    def to_python(self, value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValidationError("Enter a valid integer.", code="invalid")

    def validate(self, value: Optional[int]):
        super().validate(value)
        if value is not None:
            if self.min_value is not None and value < self.min_value:
                raise ValidationError(f"Ensure this value is greater than or equal to {self.min_value}.")
            if self.max_value is not None and value > self.max_value:
                raise ValidationError(f"Ensure this value is less than or equal to {self.max_value}.")


class EmailField(CharField):
    def validate(self, value: str):
        super().validate(value)
        if value and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            raise ValidationError("Enter a valid email address.", code="invalid_email")


# ==============================================================================
# Base Form Implementation (Simulasi Arsitektur django.forms.Form)
# ==============================================================================
class Form:
    def __init__(self, data: Optional[Dict[str, Any]] = None, prefix: Optional[str] = None):
        self.is_bound = data is not None
        self.data = data or {}
        self.prefix = prefix
        self.errors: Dict[str, List[str]] = {}
        self.cleaned_data: Dict[str, Any] = {}
        self._fields: Dict[str, Field] = {}

        # Identifikasi deklarasi Field pada class
        for attr_name in dir(self.__class__):
            attr_val = getattr(self.__class__, attr_name)
            if isinstance(attr_val, Field):
                self._fields[attr_name] = attr_val

    def add_prefix(self, field_name: str) -> str:
        return f"{self.prefix}-{field_name}" if self.prefix else field_name

    def is_valid(self) -> bool:
        return self.is_bound and not bool(self.errors)

    def full_clean(self):
        """Memetakan Django Forms full_clean pipeline."""
        self.errors = {}
        self.cleaned_data = {}

        if not self.is_bound:
            return

        step("Pipeline Stage 1", "_clean_fields() -> to_python, field validate & clean_<fieldname>()")
        self._clean_fields()

        step("Pipeline Stage 2", "_clean_form() -> cross-field clean()")
        self._clean_form()

        step("Pipeline Stage 3", "_post_clean() -> hook pasca validasi")
        self._post_clean()

    def _clean_fields(self):
        for name, field in self._fields.items():
            prefixed_key = self.add_prefix(name)
            raw_value = self.data.get(prefixed_key)

            try:
                # 1. Clean level Field (to_python, validate, run_validators)
                value = field.clean(raw_value)
                self.cleaned_data[name] = value

                # 2. Hook clean_<fieldname>() jika ada
                clean_method_name = f"clean_{name}"
                if hasattr(self, clean_method_name):
                    clean_method = getattr(self, clean_method_name)
                    value = clean_method()
                    self.cleaned_data[name] = value

                info(f"Field '{name}' valid -> sanitized: {repr(self.cleaned_data[name])}")
            except ValidationError as e:
                self.add_error(name, e.message)
                fail(f"Field '{name}' invalid: {e.message}")

    def _clean_form(self):
        try:
            cleaned_data = self.clean()
            if cleaned_data is not None:
                self.cleaned_data = cleaned_data
            info(f"Form clean() selesai. Status error saat ini: {len(self.errors)}")
        except ValidationError as e:
            self.add_error("__all__", e.message)
            fail(f"Cross-field (__all__) invalid: {e.message}")

    def _post_clean(self):
        # Post-clean hook untuk integrasi ModelForm atau cleanup
        pass

    def clean(self) -> Dict[str, Any]:
        """Override untuk validasi lintas field (cross-field validation)."""
        return self.cleaned_data

    def add_error(self, field: str, error: str):
        if field not in self.errors:
            self.errors[field] = []
        self.errors[field].append(error)


# ==============================================================================
# Implementasi Concrete Form untuk Studi Kasus
# ==============================================================================
class UserRegistrationForm(Form):
    username = CharField(min_length=4, max_length=20)
    email = EmailField()
    age = IntegerField(min_value=18, max_value=100)
    password = CharField(min_length=8)
    password_confirm = CharField(min_length=8)

    def clean_username(self) -> str:
        username = self.cleaned_data.get("username", "")
        if "admin" in username.lower():
            raise ValidationError("Kata 'admin' dicadangkan untuk sistem dan dilarang digunakan.")
        return username.lower()

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()
        pwd = cleaned_data.get("password")
        pwd_confirm = cleaned_data.get("password_confirm")

        if pwd and pwd_confirm and pwd != pwd_confirm:
            raise ValidationError("Konfirmasi password tidak cocok dengan password awal.")
        return cleaned_data


# ==============================================================================
# Django Formset Architecture Simulation
# ==============================================================================
class ManagementForm(Form):
    TOTAL_FORMS = IntegerField(min_value=0)
    INITIAL_FORMS = IntegerField(min_value=0)
    MIN_NUM_FORMS = IntegerField(required=False)
    MAX_NUM_FORMS = IntegerField(required=False)


class OrderItemForm(Form):
    item_name = CharField(min_length=2, max_length=50)
    quantity = IntegerField(min_value=1, max_value=999)


class BaseFormSet:
    """Simulasi struktur django.forms.BaseFormSet."""
    def __init__(self, form_class: type, data: Optional[Dict[str, Any]] = None, prefix: str = "form"):
        self.form_class = form_class
        self.data = data
        self.prefix = prefix
        self.is_bound = data is not None
        self.forms: List[Form] = []
        self.non_form_errors: List[str] = []
        self._construct_forms()

    def _construct_forms(self):
        if not self.is_bound:
            return

        mgmt_data = {
            "TOTAL_FORMS": self.data.get(f"{self.prefix}-TOTAL_FORMS"),
            "INITIAL_FORMS": self.data.get(f"{self.prefix}-INITIAL_FORMS"),
        }
        self.mgmt_form = ManagementForm(mgmt_data)
        self.mgmt_form.full_clean()

        if not self.mgmt_form.is_valid():
            self.non_form_errors.append("ManagementForm data missing or tampered.")
            return

        total_forms = self.mgmt_form.cleaned_data["TOTAL_FORMS"]
        for i in range(total_forms):
            form_prefix = f"{self.prefix}-{i}"
            form_instance = self.form_class(self.data, prefix=form_prefix)
            self.forms.append(form_instance)

    def is_valid(self) -> bool:
        if not self.is_bound:
            return False
        if self.non_form_errors:
            return False

        valid = True
        for form in self.forms:
            form.full_clean()
            if not form.is_valid():
                valid = False

        self.clean()
        if self.non_form_errors:
            valid = False
        return valid

    def clean(self):
        """Cross-form validation, misal deteksi item duplikat antar form."""
        seen_items = set()
        for form in self.forms:
            if form.is_valid():
                item = form.cleaned_data.get("item_name")
                if item:
                    item_key = item.lower()
                    if item_key in seen_items:
                        self.non_form_errors.append(f"Duplikasi item terdeteksi dalam pesanan: '{item}'.")
                    seen_items.add(item_key)


# ==============================================================================
# CLI Interactive Runner & Test Harness
# ==============================================================================
def run_scenario_single_form_invalid():
    header("Skenario 1: Validasi Gagal (Field-Level & Cross-Field)")
    payload = {
        "username": "SuperAdminUser",
        "email": "not-an-email",
        "age": "15",
        "password": "secretpassword123",
        "password_confirm": "mismatchpassword",
    }
    step("Input Payload", str(payload))
    form = UserRegistrationForm(data=payload)
    form.full_clean()

    print(f"\n{Color.BOLD}Hasil Validasi is_valid(): {Color.RED}{form.is_valid()}{Color.RESET}")
    print(f"{Color.BOLD}Kumpulan Form Errors:{Color.RESET}")
    for f_name, errs in form.errors.items():
        print(f"  {Color.RED}• [{f_name}]{Color.RESET} -> {', '.join(errs)}")


def run_scenario_single_form_valid():
    header("Skenario 2: Validasi Berhasil (Pipeline Higienis)")
    payload = {
        "username": "budi_santoso",
        "email": "budi@example.com",
        "age": "28",
        "password": "DjangoSecure#2026",
        "password_confirm": "DjangoSecure#2026",
    }
    step("Input Payload", str(payload))
    form = UserRegistrationForm(data=payload)
    form.full_clean()

    print(f"\n{Color.BOLD}Hasil Validasi is_valid(): {Color.GREEN}{form.is_valid()}{Color.RESET}")
    print(f"{Color.BOLD}Isi cleaned_data (Sanitized & Typecast):{Color.RESET}")
    for k, v in form.cleaned_data.items():
        print(f"  {Color.CYAN}• {k:<18}:{Color.RESET} {repr(v)} ({type(v).__name__})")


def run_scenario_formset():
    header("Skenario 3: Formset Pipeline & ManagementForm Verification")
    formset_payload = {
        "items-TOTAL_FORMS": "3",
        "items-INITIAL_FORMS": "0",
        "items-0-item_name": "Mechanical Keyboard",
        "items-0-quantity": "2",
        "items-1-item_name": "Gaming Mouse",
        "items-1-quantity": "1",
        "items-2-item_name": "mechanical keyboard",  # duplikat case-insensitive
        "items-2-quantity": "5",
    }
    step("Input Management Form & Rows", f"Total Forms: {formset_payload['items-TOTAL_FORMS']}")
    formset = BaseFormSet(OrderItemForm, data=formset_payload, prefix="items")
    valid = formset.is_valid()

    print(f"\n{Color.BOLD}Hasil Validasi Formset is_valid(): {Color.RED if not valid else Color.GREEN}{valid}{Color.RESET}")
    if formset.non_form_errors:
        print(f"{Color.BOLD}Non-Form Errors (Cross-Form Constraint):{Color.RESET}")
        for err in formset.non_form_errors:
            fail(err)

    for idx, f in enumerate(formset.forms):
        status_color = Color.GREEN if f.is_valid() else Color.RED
        print(f"\n{Color.BOLD}Sub-form #{idx} [Valid: {status_color}{f.is_valid()}{Color.RESET}]:")
        if f.is_valid():
            print(f"  Cleaned: {f.cleaned_data}")
        else:
            print(f"  Errors: {f.errors}")


def interactive_prompt():
    header("Mode Interaktif: Input Pengujian Form Langsung")
    print(f"{Color.WHITE}Silakan masukkan data uji formulir pendaftaran akun:{Color.RESET}")
    try:
        username = input(f"{Color.CYAN}Username (min 4 char)            : {Color.RESET}").strip()
        email = input(f"{Color.CYAN}Email                            : {Color.RESET}").strip()
        age = input(f"{Color.CYAN}Usia (18-100)                    : {Color.RESET}").strip()
        pwd = input(f"{Color.CYAN}Password (min 8 char)            : {Color.RESET}").strip()
        pwd_confirm = input(f"{Color.CYAN}Konfirmasi Password              : {Color.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nInput dibatalkan.")
        return

    data = {
        "username": username,
        "email": email,
        "age": age,
        "password": pwd,
        "password_confirm": pwd_confirm,
    }
    form = UserRegistrationForm(data=data)
    form.full_clean()

    if form.is_valid():
        success("Form dinyatakan VALID!")
        print(f"Cleaned Data: {form.cleaned_data}")
    else:
        fail("Form TIDAK VALID!")
        print(f"Errors: {form.errors}")


def main():
    print(f"{Color.BOLD}{Color.MAGENTA}")
    print(r"""
  ____  _                               _____                         
 |  _ \(_) __ _ _ __   __ _  ___       |  ___|__  _ __ _ __ ___  ___  
 | | | | |/ _` | '_ \ / _` |/ _ \ _____| |_ / _ \| '__| '_ ` _ \/ __| 
 | |_| | | (_| | | | | (_| | (_) |_____|  _| (_) | |  | | | | | \__ \ 
 |____// |\__,_|_| |_|\__, |\___/      |_|  \___/|_|  |_| |_| |_|___/ 
     |__/             |___/                                           
    Pipeline & Formsets Interactive Simulation Engine
    """)
    print(f"{Color.RESET}")

    run_scenario_single_form_invalid()
    run_scenario_single_form_valid()
    run_scenario_formset()

    if "--interactive" in sys.argv:
        interactive_prompt()
    else:
        print(f"\n{Color.BOLD}{Color.YELLOW}💡 Tip: Jalankan dengan argumen '--interactive' untuk mencoba input manual.{Color.RESET}\n")


if __name__ == "__main__":
    main()
