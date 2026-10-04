#!/usr/bin/env python3
"""
Lab Hands-on: Sistem Formulir Enterprise & Validasi Deklaratif
Topik: HTML5 Constraint Validation API & Server-side Declarative Mirroring Engine
Kategori: 03-Frontend-and-Mobile (Bab 04 - Modul 02 Deep Dive)

Skrip ini mereplikasi spesifikasi W3C HTML5 Constraint Validation API dan
arsitektur validasi deklaratif enterprise. Mengimplementasikan lifecycle evaluasi:
1. Validasi Sintaks Deklaratif (typeMismatch, patternMismatch, valueMissing, rangeUnderflow/Overflow)
2. State Management ValidityState Interface
3. Normalisasi Payload & Serialisasi Representasi Form HTML
"""

import re
import sys
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Callable

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_CYAN = "\033[96m"
CLR_MAGENTA = "\033[95m"
CLR_GRAY = "\033[90m"

@dataclass
class ValidityState:
    """
    Representasi langsung dari antarmuka W3C HTML5 ValidityState.
    Setiap flag merefleksikan kegagalan constraint deklaratif tertentu.
    """
    valueMissing: bool = False
    typeMismatch: bool = False
    patternMismatch: bool = False
    tooLong: bool = False
    tooShort: bool = False
    rangeUnderflow: bool = False
    rangeOverflow: bool = False
    stepMismatch: bool = False
    customError: bool = False

    @property
    def valid(self) -> bool:
        """Mengembalikan True jika dan hanya jika semua bendera constraint False."""
        return not any([
            self.valueMissing, self.typeMismatch, self.patternMismatch,
            self.tooLong, self.tooShort, self.rangeUnderflow,
            self.rangeOverflow, self.stepMismatch, self.customError
        ])

@dataclass
class FormField:
    """
    Definisi deklaratif elemen input HTML berspesifikasi enterprise.
    """
    name: str
    input_type: str = "text"
    required: bool = False
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    custom_rule: Optional[Callable[[Any], Optional[str]]] = None
    validation_message: str = ""

    def render_html(self) -> str:
        """Serialisasi model data ke tag markup HTML deklaratif."""
        attrs = [f'name="{self.name}"', f'type="{self.input_type}"']
        if self.required:
            attrs.append("required")
        if self.pattern:
            attrs.append(f'pattern="{self.pattern}"')
        if self.min_length is not None:
            attrs.append(f'minlength="{self.min_length}"')
        if self.max_length is not None:
            attrs.append(f'maxlength="{self.max_length}"')
        if self.min_val is not None:
            attrs.append(f'min="{self.min_val}"')
        if self.max_val is not None:
            attrs.append(f'max="{self.max_val}"')
        if self.step is not None:
            attrs.append(f'step="{self.step}"')
        return f"<input {' '.join(attrs)} />"

class EnterpriseFormEngine:
    """
    Engine validasi deklaratif yang menyinkronkan perilaku klien HTML5 ke server-side.
    """
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    URL_REGEX = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")

    def __init__(self, form_id: str, action: str, method: str = "POST"):
        self.form_id = form_id
        self.action = action
        self.method = method.upper()
        self.fields: Dict[str, FormField] = {}

    def add_field(self, field: FormField) -> None:
        """Mendaftarkan field ke schema form."""
        self.fields[field.name] = field

    def validate_field(self, field: FormField, raw_val: Any) -> Tuple[ValidityState, str]:
        """
        Mengeksekusi alur evaluasi Constraint Validation API W3C.
        """
        state = ValidityState()
        val_str = str(raw_val).strip() if raw_val is not None else ""
        is_empty = raw_val is None or val_str == ""

        # 1. valueMissing
        if field.required and is_empty:
            state.valueMissing = True
            return state, f"Bidang '{field.name}' wajib diisi (valueMissing)."

        # Jika kosong dan tidak required, lewati validasi format
        if is_empty:
            return state, ""

        # 2. typeMismatch
        if field.input_type == "email" and not self.EMAIL_REGEX.match(val_str):
            state.typeMismatch = True
            return state, f"Format alamat email '{val_str}' tidak valid (typeMismatch)."
        elif field.input_type == "url" and not self.URL_REGEX.match(val_str):
            state.typeMismatch = True
            return state, f"Protokol URL '{val_str}' tidak valid (typeMismatch)."
        elif field.input_type == "number":
            try:
                float(val_str)
            except ValueError:
                state.typeMismatch = True
                return state, f"Nilai '{val_str}' bukan angka numerik (typeMismatch)."

        # 3. patternMismatch
        if field.pattern and not re.fullmatch(field.pattern, val_str):
            state.patternMismatch = True
            return state, f"Nilai tidak sesuai pola ekspresi regular (patternMismatch): {field.pattern}"

        # 4. tooShort / tooLong
        if field.min_length is not None and len(val_str) < field.min_length:
            state.tooShort = True
            return state, f"Panjang teks ({len(val_str)}) kurang dari minlength ({field.min_length})."
        if field.max_length is not None and len(val_str) > field.max_length:
            state.tooLong = True
            return state, f"Panjang teks ({len(val_str)}) melampaui maxlength ({field.max_length})."

        # 5. rangeUnderflow / rangeOverflow / stepMismatch
        if field.input_type == "number":
            num = float(val_str)
            if field.min_val is not None and num < field.min_val:
                state.rangeUnderflow = True
                return state, f"Nilai numerik ({num}) di bawah batas minimum ({field.min_val})."
            if field.max_val is not None and num > field.max_val:
                state.rangeOverflow = True
                return state, f"Nilai numerik ({num}) melampaui batas maksimum ({field.max_val})."
            if field.step is not None:
                base = field.min_val if field.min_val is not None else 0.0
                remainder = round((num - base) % field.step, 6)
                if remainder != 0.0 and remainder != round(field.step, 6):
                    state.stepMismatch = True
                    return state, f"Nilai inkremental step ({field.step}) tidak valid."

        # 6. customError (Enterprise Business Rules)
        if field.custom_rule:
            err = field.custom_rule(raw_val)
            if err:
                state.customError = True
                return state, f"Aturan kustom gagal: {err}"

        return state, ""

    def process_submission(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Memproses seluruh data POST dan menghasilkan diagnostik formulir."""
        report = {}
        all_valid = True

        for name, field_def in self.fields.items():
            val = payload.get(name)
            state, msg = self.validate_field(field_def, val)
            report[name] = {
                "value": val,
                "valid": state.valid,
                "message": msg,
                "validity_state": state
            }
            if not state.valid:
                all_valid = False

        return all_valid, report

    def dump_schema_markup(self) -> str:
        """Menghasilkan representasi dokumen HTML form."""
        lines = [f'<form id="{self.form_id}" action="{self.action}" method="{self.method}" novalidate="false">']
        for field in self.fields.values():
            lines.append(f"  <label for=\"{field.name}\">{field.name.replace('_', ' ').capitalize()}</label>")
            lines.append(f"  {field.render_html()}")
        lines.append('  <button type="submit">Submit Form</button>')
        lines.append("</form>")
        return "\n".join(lines)

def build_enterprise_onboarding_form() -> EnterpriseFormEngine:
    """Membangun konfigurasi form registrasi korporat tingkat enterprise."""
    engine = EnterpriseFormEngine(
        form_id="corp-onboarding-form",
        action="/api/v2/corporations/onboard",
        method="POST"
    )

    # 1. Company Identifier (Alphanumeric 4-12 chars)
    engine.add_field(FormField(
        name="company_id",
        input_type="text",
        required=True,
        pattern=r"CORP-[A-Z0-9]{5}",
        min_length=10,
        max_length=10
    ))

    # 2. Corporate Tax ID (Format: XX-XXXXXXX)
    engine.add_field(FormField(
        name="tax_ein",
        input_type="text",
        required=True,
        pattern=r"^\d{2}-\d{7}$"
    ))

    # 3. Enterprise Email
    engine.add_field(FormField(
        name="corp_email",
        input_type="email",
        required=True,
        custom_rule=lambda v: "Domain publik tidak diizinkan!" if str(v).endswith(("@gmail.com", "@yahoo.com")) else None
    ))

    # 4. Allocated Node Cluster Instances (Numeric bounds + step)
    engine.add_field(FormField(
        name="node_instances",
        input_type="number",
        required=True,
        min_val=2.0,
        max_val=64.0,
        step=2.0
    ))

    # 5. Production Portal URL
    engine.add_field(FormField(
        name="portal_url",
        input_type="url",
        required=False
    ))

    return engine

def print_banner(text: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== {text} ==={CLR_RESET}")

def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}------------------------------------------------------------{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA} LAB: HTML5 Form Engine & Declarative Constraint Validation {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}------------------------------------------------------------{CLR_RESET}")

    engine = build_enterprise_onboarding_form()

    print_banner("1. Serialisasi Markup Form Deklaratif (HTML Schema Definition)")
    print(f"{CLR_GRAY}{engine.dump_schema_markup()}{CLR_RESET}")

    # Kumpulan payload uji skenario
    test_scenarios = [
        {
            "name": "Payload 1: Valid Production Transaction",
            "data": {
                "company_id": "CORP-9481B",
                "tax_ein": "12-3456789",
                "corp_email": "infra-ops@cloud-corp.internal",
                "node_instances": "8",
                "portal_url": "https://portal.cloud-corp.internal"
            }
        },
        {
            "name": "Payload 2: Multi-Constraint Violations (Type, Step, & Regex Mismatch)",
            "data": {
                "company_id": "corp-bad-id",       # Pattern mismatch (lowercase, format salah)
                "tax_ein": "1234567",              # Pattern mismatch
                "corp_email": "bad_email_format",  # typeMismatch
                "node_instances": "7",             # stepMismatch (min 2, step 2)
                "portal_url": "invalid://url"      # typeMismatch
            }
        },
        {
            "name": "Payload 3: Boundary & Business Logic Violations",
            "data": {
                "company_id": "CORP-9481B",
                "tax_ein": "99-9999999",
                "corp_email": "sysadmin@gmail.com", # customError (public domain block)
                "node_instances": "128",            # rangeOverflow (max: 64)
                "portal_url": ""                    # Valid (not required)
            }
        },
        {
            "name": "Payload 4: Missing Required Structural Fields (valueMissing)",
            "data": {
                "company_id": "",                  # valueMissing
                "tax_ein": None,                   # valueMissing
                "corp_email": "support@infra.com",
                "node_instances": "4",
                "portal_url": None
            }
        }
    ]

    print_banner("2. Eksekusi Engine Constraint Validation")

    for idx, scenario in enumerate(test_scenarios, 1):
        print(f"\n{CLR_BOLD}[Skenario {idx}] {scenario['name']}{CLR_RESET}")
        is_valid, report = engine.process_submission(scenario["data"])

        status_tag = f"{CLR_GREEN}[VALID/ACCEPTED]{CLR_RESET}" if is_valid else f"{CLR_RED}[REJECTED/INVALID]{CLR_RESET}"
        print(f"Status Keseluruhan: {status_tag}")
        print(f"{'Field':<18} | {'Input Value':<32} | {'State':<9} | {'Diagnostic Message'}")
        print("-" * 95)

        for field_name, res in report.items():
            val_display = str(res["value"]) if res["value"] is not None else "<NULL>"
            if len(val_display) > 30:
                val_display = val_display[:27] + "..."

            if res["valid"]:
                state_str = f"{CLR_GREEN}VALID{CLR_RESET}"
                msg_str = f"{CLR_GRAY}Semua constraint terpenuhi.{CLR_RESET}"
            else:
                state_str = f"{CLR_RED}FAIL{CLR_RESET}"
                msg_str = f"{CLR_YELLOW}{res['message']}{CLR_RESET}"

            print(f"{field_name:<18} | {val_display:<32} | {state_str:<18} | {msg_str}")

    print_banner("3. Ringkasan Diagnostik Arsitektur Enterprise")
    print(f"✓ Mirroring Server-Side menjamin integritas data identik dengan browser W3C ValidityState.")
    print(f"✓ Mencegah bypass validasi klien (DevTools / bypass script automation).")
    print(f"✓ Pipeline siap untuk deployment microservice validasi kontrak schema.")

if __name__ == "__main__":
    main()