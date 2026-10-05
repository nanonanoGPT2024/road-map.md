#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Django Forms Processing, Validation Pipeline & Formsets Architecture
Simulasi Arsitektur Produksi Pipeline Validasi Django (Standalone Runnable Python 3)

Topik BAB-05:
1. Field-Level Validation (to_python, validate, run_validators)
2. Form-Level Validation Hook (clean_<fieldname>)
3. Cross-Field Validation Hook (clean())
4. BaseForm Lifecycle (full_clean, cleaned_data, errors)
5. BaseFormSet Architecture & ManagementForm validation (TOTAL_FORMS, duplicate detection)
"""

import re
import sys
import time
from typing import Any, Dict, List, Optional, Callable


# ==============================================================================
# ANSI Color Palette for Interactive Terminal Display
# ==============================================================================
class TermColor:
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
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"


def header(text: str) -> None:
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}{'=' * 78}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.YELLOW} >> {text.upper()}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}{'=' * 78}{TermColor.RESET}")


def step_log(step_name: str, detail: str) -> None:
    print(f"{TermColor.MAGENTA}[PIPELINE STEP]{TermColor.RESET} {TermColor.BOLD}{step_name:<20}{TermColor.RESET} | {TermColor.DIM}{detail}{TermColor.RESET}")


def success_log(msg: str) -> None:
    print(f"{TermColor.GREEN}✔ [OK]{TermColor.RESET} {msg}")


def error_log(msg: str) -> None:
    print(f"{TermColor.RED}✘ [VALIDATION ERROR]{TermColor.RESET} {msg}")


# ==============================================================================
# Django Validation Error Core Primitives
# ==============================================================================
class ValidationError(Exception):
    """Representasi django.core.exceptions.ValidationError"""
    def __init__(self, message: Any, code: Optional[str] = None):
        super().__init__(message)
        if isinstance(message, list):
            self.messages = message
        else:
            self.messages = [str(message)]
        self.code = code

    def __str__(self):
        return ", ".join(self.messages)


# ==============================================================================
# Form Fields & Standard Validators
# ==============================================================================
def validate_email(value: str):
    email_regex = r"^[\w\.-]+@([\w-]+\.)+[\w-]{2,4}$"
    if not re.match(email_regex, value):
        raise ValidationError("Masukkan alamat email yang valid dengan domain yang benar.", code="invalid_email")


def min_value_validator(min_val: int):
    def validator(value: int):
        if value < min_val:
            raise ValidationError(f"Nilai tidak boleh lebih kecil dari {min_val}.", code="min_value")
    return validator


class Field:
    def __init__(
        self,
        required: bool = True,
        validators: Optional[List[Callable]] = None,
        error_messages: Optional[Dict[str, str]] = None
    ):
        self.required = required
        self.validators = validators or []
        self.error_messages = error_messages or {}

    def to_python(self, value: Any) -> Any:
        """Konversi raw input HTTP string ke tipe Python primitif."""
        if value in (None, ""):
            return None
        return value

    def validate(self, value: Any) -> None:
        """Memeriksa constraint field dasar seperti is_required."""
        if self.required and value in (None, ""):
            msg = self.error_messages.get("required", "Field ini wajib diisi.")
            raise ValidationError(msg, code="required")

    def run_validators(self, value: Any) -> None:
        """Mengeksekusi seluruh callable validators terdaftar."""
        if value in (None, ""):
            return
        errors = []
        for validator in self.validators:
            try:
                validator(value)
            except ValidationError as err:
                errors.extend(err.messages)
        if errors:
            raise ValidationError(errors)

    def clean(self, value: Any) -> Any:
        """Atomic field cleaning execution flow."""
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
        if value in (None, ""):
            return ""
        return str(value).strip()

    def validate(self, value: str) -> None:
        super().validate(value)
        if self.max_length and len(value) > self.max_length:
            raise ValidationError(f"Maksimal panjang karakter adalah {self.max_length}.", code="max_length")
        if self.min_length and len(value) < self.min_length:
            raise ValidationError(f"Minimal panjang karakter adalah {self.min_length}.", code="min_length")


class IntegerField(Field):
    def to_python(self, value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValidationError("Harap masukkan bilangan bulat yang valid.", code="invalid")


class DecimalField(Field):
    def to_python(self, value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            raise ValidationError("Harap masukkan angka desimal yang valid.", code="invalid")


# ==============================================================================
# Django Base Form Engine & Full Validation Lifecycle
# ==============================================================================
class FormMeta(type):
    """Metaclass untuk mendaftarkan field deklaratif layaknya Django Forms."""
    def __new__(mcs, name, bases, attrs):
        declared_fields = {}
        for key, value in list(attrs.items()):
            if isinstance(value, Field):
                declared_fields[key] = attrs.pop(key)
        attrs["base_fields"] = declared_fields
        return super().__new__(mcs, name, bases, attrs)


class Form(metaclass=FormMeta):
    base_fields: Dict[str, Field] = {}

    def __init__(self, data: Optional[Dict[str, Any]] = None, prefix: str = ""):
        self.is_bound = data is not None
        self.data = data or {}
        self.prefix = f"{prefix}-" if prefix else ""
        self.fields = {k: v for k, v in self.base_fields.items()}
        self.cleaned_data: Dict[str, Any] = {}
        self._errors: Dict[str, List[str]] = {}

    @property
    def errors(self) -> Dict[str, List[str]]:
        if not self._errors and self.is_bound:
            self.full_clean()
        return self._errors

    def is_valid(self) -> bool:
        return self.is_bound and not bool(self.errors)

    def full_clean(self) -> None:
        """
        Alur Eksekusi Produksi Django:
        1. _clean_fields(): field.clean() -> clean_<fieldname>() hook
        2. _clean_form(): cross-field clean() hook
        3. _post_clean(): hook finalisasi (ModelForm dsb.)
        """
        self._errors = {}
        self.cleaned_data = {}

        if not self.is_bound:
            return

        self._clean_fields()
        self._clean_form()
        self._post_clean()

    def _clean_fields(self) -> None:
        for name, field in self.fields.items():
            prefixed_name = f"{self.prefix}{name}"
            raw_value = self.data.get(prefixed_name, self.data.get(name))
            step_log(f"_clean_fields", f"Cleaning field '{name}' with raw value: {raw_value!r}")
            try:
                value = field.clean(raw_value)
                self.cleaned_data[name] = value

                # Hook spesifik clean_<fieldname>()
                custom_clean = getattr(self, f"clean_{name}", None)
                if callable(custom_clean):
                    step_log(f"clean_{name}()", f"Executing custom hook for '{name}'")
                    value = custom_clean()
                    self.cleaned_data[name] = value
            except ValidationError as e:
                self.add_error(name, e.messages)
                if name in self.cleaned_data:
                    del self.cleaned_data[name]

    def _clean_form(self) -> None:
        """Cross-field validation hook: self.clean()"""
        try:
            step_log("form.clean()", "Executing cross-field validation clean() hook")
            cleaned_data = self.clean()
            if cleaned_data is not None:
                self.cleaned_data = cleaned_data
        except ValidationError as e:
            self.add_error("__all__", e.messages)

    def _post_clean(self) -> None:
        pass

    def clean(self) -> Dict[str, Any]:
        """Dapat di-override subclass untuk cross-field validation."""
        return self.cleaned_data

    def add_error(self, field: str, error: Any) -> None:
        if field not in self._errors:
            self._errors[field] = []
        if isinstance(error, list):
            self._errors[field].extend(error)
        else:
            self._errors[field].append(str(error))


# ==============================================================================
# Django FormSet Engine: Multi-Form Processing & Cross-Form Logic
# ==============================================================================
class FormSet:
    """Simulasi django.forms.BaseFormSet"""
    TOTAL_FORMS_KEY = "TOTAL_FORMS"
    INITIAL_FORMS_KEY = "INITIAL_FORMS"

    def __init__(
        self,
        form_class: type,
        data: Optional[Dict[str, Any]] = None,
        prefix: str = "form",
        min_num: int = 1,
        max_num: int = 10
    ):
        self.form_class = form_class
        self.data = data or {}
        self.prefix = prefix
        self.min_num = min_num
        self.max_num = max_num
        self.is_bound = data is not None
        self.forms: List[Form] = []
        self._non_form_errors: List[str] = []
        self._is_valid_cache: Optional[bool] = None

        if self.is_bound:
            self._construct_forms()

    def _management_form_valid(self) -> int:
        step_log("ManagementForm", "Validating formset TOTAL_FORMS integrity...")
        total_key = f"{self.prefix}-{self.TOTAL_FORMS_KEY}"
        raw_total = self.data.get(total_key)

        if raw_total is None:
            raise ValidationError(
                f"ManagementForm data rusak atau hilang: '{total_key}' tidak ditemukan. Kemungkinan security tampering!",
                code="missing_management"
            )
        try:
            total = int(raw_total)
        except ValueError:
            raise ValidationError("TOTAL_FORMS bukan integer valid.", code="invalid_management")

        if total < self.min_num:
            raise ValidationError(f"Minimal form yang disubmit adalah {self.min_num}.", code="min_num")
        if total > self.max_num:
            raise ValidationError(f"Maksimal form yang disubmit adalah {self.max_num}.", code="max_num")
        return total

    def _construct_forms(self) -> None:
        try:
            total = self._management_form_valid()
            self.forms = [
                self.form_class(data=self.data, prefix=f"{self.prefix}-{i}")
                for i in range(total)
            ]
        except ValidationError as e:
            self._non_form_errors.extend(e.messages)

    def is_valid(self) -> bool:
        if not self.is_bound:
            return False
        if self._non_form_errors:
            return False

        all_valid = True
        for form in self.forms:
            if not form.is_valid():
                all_valid = False

        try:
            step_log("formset.clean()", "Running cross-form validation check")
            self.clean()
        except ValidationError as e:
            self._non_form_errors.extend(e.messages)
            all_valid = False

        return all_valid

    def clean(self) -> None:
        """Hook untuk validasi antar form (misal duplicate entry)."""
        pass

    @property
    def non_form_errors(self) -> List[str]:
        return self._non_form_errors


# ==============================================================================
# Domain Production Implementation: Order Checkout & OrderLine Items
# ==============================================================================
class OrderCheckoutForm(Form):
    customer_name = CharField(min_length=3, max_length=50)
    email = CharField(validators=[validate_email])
    payment_method = CharField()
    promo_code = CharField(required=False)
    subtotal = DecimalField()

    def clean_payment_method(self) -> str:
        """Field-specific hook: clean_<fieldname>()"""
        method = self.cleaned_data.get("payment_method", "").upper()
        allowed = ["CREDIT_CARD", "QRIS", "BANK_TRANSFER", "COD"]
        if method not in allowed:
            raise ValidationError(f"Metode '{method}' tidak didukung. Pilihan: {', '.join(allowed)}")
        return method

    def clean(self) -> Dict[str, Any]:
        """Cross-field validation hook"""
        cleaned_data = self.cleaned_data
        promo = cleaned_data.get("promo_code")
        payment = cleaned_data.get("payment_method")
        subtotal = cleaned_data.get("subtotal") or 0.0

        if promo == "CASHLESS50" and payment == "COD":
            raise ValidationError(
                "Promo code 'CASHLESS50' hanya berlaku untuk metode pembayaran non-tunai (bukan COD).",
                code="invalid_promo_combo"
            )

        if promo == "SUPERVIP" and subtotal < 500000:
            raise ValidationError(
                f"Promo code 'SUPERVIP' membutuhkan minimal belanja Rp 500.000 (Subtotal saat ini: Rp {subtotal:,.2f}).",
                code="min_spend_unmet"
            )

        return cleaned_data


class OrderItemForm(Form):
    sku = CharField(min_length=4, max_length=15)
    quantity = IntegerField(validators=[min_value_validator(1)])
    unit_price = DecimalField()


class OrderItemFormSet(FormSet):
    def clean(self) -> None:
        super().clean()
        skus_seen = set()
        for idx, form in enumerate(self.forms):
            if not form.is_valid():
                continue
            sku = form.cleaned_data.get("sku")
            if sku in skus_seen:
                raise ValidationError(
                    f"Barang duplikat terdeteksi pada Form #{idx + 1} dengan SKU '{sku}'. Gabungkan jumlah kuantitas!",
                    code="duplicate_sku"
                )
            if sku:
                skus_seen.add(sku)


# ==============================================================================
# Interactive Terminal Simulation Scenarios
# ==============================================================================
def display_result(form: Form, title: str) -> None:
    print(f"\n{TermColor.BOLD}{TermColor.WHITE}--- {title} ---{TermColor.RESET}")
    is_valid = form.is_valid()
    if is_valid:
        success_log(f"Status: VALID (is_valid=True)")
        print(f"{TermColor.CYAN}Cleaned Data Payload:{TermColor.RESET}")
        for k, v in form.cleaned_data.items():
            print(f"  {TermColor.GREEN}✔ {k:<18}{TermColor.RESET} : {v}")
    else:
        error_log(f"Status: INVALID (is_valid=False)")
        print(f"{TermColor.RED}Validation Errors Dict:{TermColor.RESET}")
        for k, v in form.errors.items():
            print(f"  {TermColor.RED}✘ {k:<18}{TermColor.RESET} : {v}")


def run_scenario_1():
    header("Skenario 1: Order Checkout - Valid Data & Full Pipeline Success")
    data = {
        "customer_name": "Budi Pratama",
        "email": "budi.pratama@enterprise.id",
        "payment_method": "qris",
        "promo_code": "CASHLESS50",
        "subtotal": "650000.00"
    }
    form = OrderCheckoutForm(data=data)
    display_result(form, "Order Form Clean Pipeline")


def run_scenario_2():
    header("Skenario 2: Order Checkout - Field-Level Hook & Regex Failures")
    data = {
        "customer_name": "Al",
        "email": "bukan-alamat-email-resmi",
        "payment_method": "PAYLATER_ILLEGAL",
        "promo_code": "",
        "subtotal": "invalid_number"
    }
    form = OrderCheckoutForm(data=data)
    display_result(form, "Order Form Field Validation Failures")


def run_scenario_3():
    header("Skenario 3: Cross-Field Validation Failure (COD + CASHLESS50)")
    data = {
        "customer_name": "Siti Nurhaliza",
        "email": "siti@ecommerce.org",
        "payment_method": "cod",
        "promo_code": "CASHLESS50",
        "subtotal": "350000.00"
    }
    form = OrderCheckoutForm(data=data)
    display_result(form, "Cross-Field Conflict in clean()")


def run_scenario_4():
    header("Skenario 4: FormSet Multi-Form - Valid Line Items with Prefix")
    data = {
        "items-TOTAL_FORMS": "2",
        "items-INITIAL_FORMS": "0",
        "items-0-sku": "PROD-A101",
        "items-0-quantity": "3",
        "items-0-unit_price": "125000.00",
        "items-1-sku": "PROD-B202",
        "items-1-quantity": "1",
        "items-1-unit_price": "250000.00",
    }
    formset = OrderItemFormSet(OrderItemForm, data=data, prefix="items")
    valid = formset.is_valid()
    print(f"\n{TermColor.BOLD}FormSet Validation Status: {TermColor.GREEN if valid else TermColor.RED}{valid}{TermColor.RESET}")
    for idx, f in enumerate(formset.forms):
        display_result(f, f"Sub-Form #{idx+1} [SKU: {f.data.get(f'items-{idx}-sku')}]")


def run_scenario_5():
    header("Skenario 5: FormSet Cross-Form Duplicate SKU & Tampering Test")
    data = {
        "items-TOTAL_FORMS": "2",
        "items-INITIAL_FORMS": "0",
        "items-0-sku": "PROD-DUPLICATE",
        "items-0-quantity": "2",
        "items-0-unit_price": "50000.00",
        "items-1-sku": "PROD-DUPLICATE",
        "items-1-quantity": "5",
        "items-1-unit_price": "50000.00",
    }
    formset = OrderItemFormSet(OrderItemForm, data=data, prefix="items")
    valid = formset.is_valid()
    print(f"\n{TermColor.BOLD}FormSet Validation Status: {TermColor.GREEN if valid else TermColor.RED}{valid}{TermColor.RESET}")
    if formset.non_form_errors:
        error_log(f"Non-Form Errors (Cross-Form): {formset.non_form_errors}")


def interactive_terminal():
    print(f"{TermColor.BOLD}{TermColor.GREEN}")
    print(r"""
  ____  _                               ____  _            _ _             
 |  _ \(_) __ _ _ __   __ _  ___       |  _ \(_)_ __   ___| (_)_ __   ___  
 | | | | |/ _` | '_ \ / _` |/ _ \ _____| |_) | | '_ \ / _ \ | | '_ \ / _ \ 
 | |_| | | (_| | | | | (_| | (_) |_____|  __/| | |_) |  __/ | | | | |  __/ 
 |____// |\__,_|_| |_|\__, |\___/      |_|   |_| .__/ \___|_|_|_| |_|\___| 
     |__/             |___/                    |_|                         
    """)
    print(f"  [DJANGO PRODUCTION SIMULATION] BAB-05: Forms Processing & Formsets")
    print(f"  Architecture: Field Clean -> Custom Hook -> Cross-Field -> Formsets{TermColor.RESET}\n")

    scenarios = [
        ("Jalankan Skenario 1: Order Checkout Sukses (Full Pipeline)", run_scenario_1),
        ("Jalankan Skenario 2: Field Validation & Regex Errors", run_scenario_2),
        ("Jalankan Skenario 3: Cross-field Conflict (clean() hook)", run_scenario_3),
        ("Jalankan Skenario 4: FormSet Processing (Valid Multi-Form)", run_scenario_4),
        ("Jalankan Skenario 5: FormSet Duplicate SKU Detection", run_scenario_5),
        ("Jalankan Semua Skenario Secara Berurutan (Automated Suite)", None),
    ]

    if not sys.stdin.isatty():
        # Non-interactive / headless CI mode
        print(f"{TermColor.YELLOW}[INFO] Non-interactive environment detected. Menjalankan seluruh test suite otomatis...{TermColor.RESET}")
        run_scenario_1()
        run_scenario_2()
        run_scenario_3()
        run_scenario_4()
        run_scenario_5()
        print(f"\n{TermColor.BOLD}{TermColor.BG_GREEN}{TermColor.WHITE} Seluruh pipeline simulasi Django BAB-05 tuntas dieksekusi dengan sempurna. {TermColor.RESET}\n")
        return

    while True:
        print(f"\n{TermColor.BOLD}{TermColor.CYAN}Pilih Menu Simulasi Lab:{TermColor.RESET}")
        for idx, (label, _) in enumerate(scenarios, 1):
            print(f"  {TermColor.YELLOW}[{idx}]{TermColor.RESET} {label}")
        print(f"  {TermColor.RED}[0]{TermColor.RESET} Keluar")

        try:
            choice = input(f"\n{TermColor.BOLD}Masukkan pilihan (0-6): {TermColor.RESET}").strip()
            if choice == "0":
                print(f"{TermColor.GREEN}Selesai. Terima kasih!{TermColor.RESET}")
                break
            elif choice in ("1", "2", "3", "4", "5"):
                scenarios[int(choice) - 1][1]()
            elif choice == "6":
                for i in range(5):
                    scenarios[i][1]()
                    time.sleep(0.5)
            else:
                print(f"{TermColor.RED}Pilihan tidak valid. Silakan coba lagi.{TermColor.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{TermColor.YELLOW}Dibatalkan oleh user.{TermColor.RESET}")
            break


if __name__ == "__main__":
    interactive_terminal()
