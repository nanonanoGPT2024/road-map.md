#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Sistem Formulir Enterprise & Validasi Deklaratif HTML5
Modul 01 - BAB 04: Sistem Formulir Enterprise dan Validasi Deklaratif

Skrip ini mereplikasi mekanisme mesin browser (Constraint Validation API,
atribut validasi deklaratif, encoding form data, dan proteksi CSRF)
dalam CLI interaktif dengan output pewarnaan ANSI.
"""

from dataclasses import dataclass, field
import math
import re
import sys
from typing import Any, Dict, List, Optional
import urllib.parse
import uuid

# --- ANSI Terminal Color Palette ---
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_CYAN = "\033[36m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_MAGENTA = "\033[35m"
COLOR_BLUE = "\033[34m"
COLOR_GRAY = "\033[90m"


def print_banner(text: str) -> None:
    line = "=" * 70
    print(f"\n{COLOR_CYAN}{COLOR_BOLD}{line}{COLOR_RESET}")
    print(f"{COLOR_CYAN}{COLOR_BOLD}  {text}{COLOR_RESET}")
    print(f"{COLOR_CYAN}{COLOR_BOLD}{line}{COLOR_RESET}\n")


def print_badge(label: str, text: str, color: str = COLOR_CYAN) -> None:
    print(f"[{color}{COLOR_BOLD}{label}{COLOR_RESET}] {text}")


@dataclass
class ValidityState:
    """Simulasi antarmuka DOM ValidityState pada elemen HTMLFormElement."""
    value_missing: bool = False      # required tapi kosong
    type_mismatch: bool = False      # tipe email, url tidak sesuai format
    pattern_mismatch: bool = False   # tidak sesuai regex pattern
    too_short: bool = False          # panjang < minlength
    too_long: bool = False           # panjang > maxlength
    range_underflow: bool = False    # nilai < min
    range_overflow: bool = False     # nilai > max
    step_mismatch: bool = False      # nilai melanggar step
    custom_error: bool = False       # validasi kustom bisnis
    validation_message: str = ""

    @property
    def valid(self) -> bool:
        return not (
            self.value_missing
            or self.type_mismatch
            or self.pattern_mismatch
            or self.too_short
            or self.too_long
            or self.range_underflow
            or self.range_overflow
            or self.step_mismatch
            or self.custom_error
        )


@dataclass
class FormField:
    """Mewakili elemen <input>, <select>, atau <textarea> dengan atribut deklaratif."""
    name: str
    label: str
    field_type: str = "text"
    required: bool = False
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    options: List[str] = field(default_factory=list)
    placeholder: str = ""
    autocomplete: str = "off"
    description: str = ""

    def validate(self, raw_value: str) -> ValidityState:
        state = ValidityState()
        val = raw_value.strip()

        # 1. Atribut 'required' (valueMissing)
        if self.required and not val:
            state.value_missing = True
            state.validation_message = f"Field '{self.label}' wajib diisi (valueMissing)."
            return state

        if not val and not self.required:
            return state  # Field opsional kosong dianggap valid

        # 2. Atribut tipe email / url / number (typeMismatch)
        if self.field_type == "email":
            email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            if not re.match(email_regex, val):
                state.type_mismatch = True
                state.validation_message = f"Format email tidak valid (typeMismatch): '{val}'"
                return state

        elif self.field_type == "url":
            url_regex = r"^https?:\/\/[^\s\/$.?#].[^\s]*$"
            if not re.match(url_regex, val):
                state.type_mismatch = True
                state.validation_message = f"Format URL harus valid (typeMismatch, e.g. https://domain.com)"
                return state

        # 3. Atribut minlength & maxlength (tooShort & tooLong)
        if self.min_length is not None and len(val) < self.min_length:
            state.too_short = True
            state.validation_message = (
                f"Panjang minimal {self.min_length} karakter, saat ini {len(val)} (tooShort)."
            )
            return state

        if self.max_length is not None and len(val) > self.max_length:
            state.too_long = True
            state.validation_message = (
                f"Panjang maksimal {self.max_length} karakter, saat ini {len(val)} (tooLong)."
            )
            return state

        # 4. Atribut pattern (patternMismatch)
        if self.pattern is not None:
            if not re.search(self.pattern, val):
                state.pattern_mismatch = True
                state.validation_message = (
                    f"Nilai tidak sesuai pola deklaratif regex: /{self.pattern}/ (patternMismatch)."
                )
                return state

        # 5. Atribut min, max, step untuk number/range (rangeUnderflow, rangeOverflow, stepMismatch)
        if self.field_type in ("number", "range"):
            try:
                num_val = float(val)
                if self.min_val is not None and num_val < self.min_val:
                    state.range_underflow = True
                    state.validation_message = f"Nilai minimal {self.min_val} (rangeUnderflow)."
                    return state

                if self.max_val is not None and num_val > self.max_val:
                    state.range_overflow = True
                    state.validation_message = f"Nilai maksimal {self.max_val} (rangeOverflow)."
                    return state

                if self.step is not None:
                    base = self.min_val if self.min_val is not None else 0.0
                    diff = (num_val - base) / self.step
                    if not math.isclose(diff, round(diff), abs_tol=1e-5):
                        state.step_mismatch = True
                        state.validation_message = f"Nilai harus berupa kelipatan step {self.step} (stepMismatch)."
                        return state
            except ValueError:
                state.custom_error = True
                state.validation_message = "Input harus berupa angka valid (badInput)."
                return state

        return state


class EnterpriseForm:
    """Mewakili formulir arsitektur enterprise dengan encoding dan proteksi CSRF."""
    def __init__(
        self,
        form_id: str,
        action: str,
        method: str = "POST",
        enctype: str = "application/x-www-form-urlencoded",
        novalidate: bool = False,
    ):
        self.form_id = form_id
        self.action = action
        self.method = method.upper()
        self.enctype = enctype
        self.novalidate = novalidate
        self.csrf_token = uuid.uuid4().hex
        self.fields: Dict[str, FormField] = {}
        self.submitted_data: Dict[str, str] = {}

    def add_field(self, field_obj: FormField) -> None:
        self.fields[field_obj.name] = field_obj

    def serialize_payload(self) -> str:
        payload_data = dict(self.submitted_data)
        payload_data["_csrf"] = self.csrf_token

        if self.enctype == "application/x-www-form-urlencoded":
            return urllib.parse.urlencode(payload_data)

        if self.enctype == "multipart/form-data":
            boundary = "----WebKitFormBoundary" + uuid.uuid4().hex[:16]
            parts = []
            for k, v in payload_data.items():
                parts.append(f"--{boundary}")
                parts.append(f'Content-Disposition: form-data; name="{k}"\r\n')
                parts.append(str(v))
            parts.append(f"--{boundary}--\r\n")
            return "\r\n".join(parts)

        # Fallback text/plain
        return "\n".join(f"{k}={v}" for k, v in payload_data.items())

    def print_form_contract(self) -> None:
        print_badge("HTML CONTRACT", f"<form id='{self.form_id}' method='{self.method}' action='{self.action}' enctype='{self.enctype}'>")
        print(f"  {COLOR_GRAY}Hidden CSRF Security Input:{COLOR_RESET}")
        print(f"    <input type='hidden' name='_csrf' value='{self.csrf_token}'>")
        print(f"  {COLOR_GRAY}Fieldsets & Declarative Inputs:{COLOR_RESET}")
        for f in self.fields.values():
            req_attr = " required" if f.required else ""
            pat_attr = f' pattern="{f.pattern}"' if f.pattern else ""
            min_attr = f' minlength="{f.min_length}"' if f.min_length else ""
            num_range = ""
            if f.min_val is not None:
                num_range += f' min="{f.min_val}"'
            if f.max_val is not None:
                num_range += f' max="{f.max_val}"'
            if f.step is not None:
                num_range += f' step="{f.step}"'

            print(
                f"    <label for='{f.name}'>{f.label}:</label>\n"
                f"    <input type='{f.field_type}' id='{f.name}' name='{f.name}'"
                f"{req_attr}{pat_attr}{min_attr}{num_range} autocomplete='{f.autocomplete}'>"
            )
        print("</form>\n")


def create_enterprise_registration_form() -> EnterpriseForm:
    form = EnterpriseForm(
        form_id="enterprise-vendor-reg",
        action="/api/v1/vendors/register",
        method="POST",
        enctype="application/x-www-form-urlencoded",
    )

    form.add_field(
        FormField(
            name="company_tax_id",
            label="Nomor Pokok Wajib Pajak (NPWP / Tax ID)",
            field_type="text",
            required=True,
            pattern=r"^\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}$",
            placeholder="01.234.567.8-901.000",
            description="Format baku NPWP 15 digit Indonesia: XX.XXX.XXX.X-XXX.XXX",
        )
    )

    form.add_field(
        FormField(
            name="official_email",
            label="Email Korporat Resmi",
            field_type="email",
            required=True,
            autocomplete="email",
            placeholder="vendor-admin@perusahaan.co.id",
            description="Harus berformat email RFC 5322 standar",
        )
    )

    form.add_field(
        FormField(
            name="portal_url",
            label="Portal Situs Perusahaan",
            field_type="url",
            required=True,
            placeholder="https://company.co.id",
            description="Harus diawali skema http:// atau https://",
        )
    )

    form.add_field(
        FormField(
            name="sla_tier",
            label="Komitmen Tingkat Layanan SLA (Persen)",
            field_type="number",
            required=True,
            min_val=90.0,
            max_val=99.99,
            step=0.01,
            placeholder="99.95",
            description="Batas toleransi SLA: 90.00% s/d 99.99%, step presisi 0.01",
        )
    )

    form.add_field(
        FormField(
            name="auth_passcode",
            label="Passphrase Akses API",
            field_type="password",
            required=True,
            min_length=8,
            max_length=32,
            placeholder="Minimal 8 karakter unik",
            description="Deklarasi minlength=8 maxlength=32",
        )
    )

    return form


def run_automated_test_suite() -> bool:
    print_banner("1. AUTOMATED SELF-VERIFICATION SUITE (Constraint Validation)")
    form = create_enterprise_registration_form()
    all_passed = True

    test_cases = [
        # (field_name, test_value, expected_valid, expected_violation)
        ("company_tax_id", "", False, "value_missing"),
        ("company_tax_id", "12345", False, "pattern_mismatch"),
        ("company_tax_id", "01.234.567.8-901.000", True, "none"),
        ("official_email", "bukan-email", False, "type_mismatch"),
        ("official_email", "admin@enterprise.corp", True, "none"),
        ("portal_url", "ftp://files.corp", False, "type_mismatch"),
        ("portal_url", "https://enterprise.corp", True, "none"),
        ("sla_tier", "85.0", False, "range_underflow"),
        ("sla_tier", "105.0", False, "range_overflow"),
        ("sla_tier", "99.955", False, "step_mismatch"),
        ("sla_tier", "99.95", True, "none"),
        ("auth_passcode", "short", False, "too_short"),
        ("auth_passcode", "ValidEnterpriseKey#2026", True, "none"),
    ]

    for field_name, test_val, expected_valid, expected_violation in test_cases:
        field_obj = form.fields[field_name]
        state = field_obj.validate(test_val)

        status_ok = (state.valid == expected_valid)
        violation_matched = True
        if not expected_valid:
            violation_matched = getattr(state, expected_violation, False)

        test_success = status_ok and violation_matched
        if not test_success:
            all_passed = False

        res_icon = f"{COLOR_GREEN}PASS{COLOR_RESET}" if test_success else f"{COLOR_RED}FAIL{COLOR_RESET}"
        print(
            f"  [{res_icon}] Field '{COLOR_BOLD}{field_name}{COLOR_RESET}' | "
            f"Input: '{COLOR_YELLOW}{test_val}{COLOR_RESET}' -> "
            f"Valid: {state.valid} ({state.validation_message or 'Valid'})"
        )

    print()
    if all_passed:
        print_badge("VERIFIKASI SUKSES", "Seluruh 13 pengujian validasi deklaratif terpenuhi 100%!", COLOR_GREEN)
    else:
        print_badge("VERIFIKASI GAGAL", "Ada kejanggalan dalam validasi.", COLOR_RED)
    return all_passed


def run_interactive_simulation() -> None:
    print_banner("2. SIMULASI TERMINAL INTERAKTIF: SUBMISI FORM ENTERPRISE")
    form = create_enterprise_registration_form()
    form.print_form_contract()

    print(f"{COLOR_YELLOW}{COLOR_BOLD}Instruksi:{COLOR_RESET} Masukkan nilai sesuai petunjuk atribut deklaratif.")
    print(f"Tekan {COLOR_BOLD}[Enter]{COLOR_RESET} langsung untuk mengisi otomatis nilai default valid.\n")

    default_inputs = {
        "company_tax_id": "01.234.567.8-901.000",
        "official_email": "procurement@bumn-enterprise.id",
        "portal_url": "https://vendor.bumn-enterprise.id",
        "sla_tier": "99.95",
        "auth_passcode": "EnterpriseToken2026!",
    }

    user_values: Dict[str, str] = {}

    for name, field_obj in form.fields.items():
        while True:
            default_val = default_inputs.get(name, "")
            prompt_label = (
                f"{COLOR_BOLD}{field_obj.label}{COLOR_RESET}\n"
                f"  {COLOR_GRAY}(Atribut: {field_obj.description}) [Default: {default_val}]{COLOR_RESET}\n"
                f"  {COLOR_CYAN}>> {COLOR_RESET}"
            )

            # Jika non-interaktif (e.g. pipa otomatis CI/CD), pakai default
            if not sys.stdin.isatty():
                entered = default_val
                print(f"{prompt_label}{entered}")
            else:
                try:
                    entered = input(prompt_label).strip()
                    if not entered:
                        entered = default_val
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{COLOR_RED}Interupsi terdeteksi. Menggunakan default.{COLOR_RESET}")
                    entered = default_val

            # Jalankan validasi
            state = field_obj.validate(entered)
            if state.valid:
                print(f"  {COLOR_GREEN}[VALID]{COLOR_RESET} Input diterima: '{entered}'\n")
                user_values[name] = entered
                break
            else:
                print(f"  {COLOR_RED}[INVALID CONSTRAINT]{COLOR_RESET} {state.validation_message}\n")
                if not sys.stdin.isatty():
                    # Jika dalam mode otomatis dan invalid, ganti ke default langsung
                    user_values[name] = default_val
                    break

    form.submitted_data = user_values

    # Simulasi Submission HTTP Payload
    print_banner("3. HASIL SERIALISASI PAYLOAD HTTP ENTERPRISE")
    print_badge("ENCTYPE", form.enctype)
    print_badge("HTTP ACTION", f"{form.method} {form.action}")
    print("\n" + COLOR_MAGENTA + form.serialize_payload() + COLOR_RESET + "\n")

    print_badge(
        "KESIMPULAN LAB",
        "Formulir sukses divalidasi pada client-side secara deklaratif sebelum transmisi payload jaringan.",
        COLOR_GREEN
    )


def main() -> int:
    print(f"{COLOR_BOLD}{COLOR_BLUE}=== HTML5 ENTERPRISE FORM & DECLARATIVE VALIDATION LAB ==={COLOR_RESET}")
    tests_ok = run_automated_test_suite()
    run_interactive_simulation()
    return 0 if tests_ok else 1


if __name__ == "__main__":
    sys.exit(main())
