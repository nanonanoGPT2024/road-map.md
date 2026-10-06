#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Engine Angular Reactive Forms Enterprise & Validasi Reaktif Lanjutan
Topik: BAB-06 - Form Enterprise dan Validasi Reaktif Lanjutan
Materi:
  - AbstractControl, FormControl, FormGroup, FormArray
  - Status flags: pristine/dirty, touched/untouched, valid/invalid/pending
  - Sync Validators, Cross-Field / Multi-field Validators
  - Async Validators (Simulasi network delay & server-side uniqueness check)
  - Reactive streams simulation (valueChanges & statusChanges observables)
"""

import sys
import time
import re
from typing import Callable, List, Dict, Any, Optional

# ANSI Color Codes for terminal formatting
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


class ValidationErrors(dict):
    """Representasi Angular ValidationErrors object."""
    pass


# Type aliases
ValidatorFn = Callable[['AbstractControl'], Optional[ValidationErrors]]
AsyncValidatorFn = Callable[['AbstractControl'], Optional[ValidationErrors]]


class AbstractControl:
    """Kelas dasar meniru @angular/forms AbstractControl."""
    def __init__(self, validators: Optional[List[ValidatorFn]] = None,
                 async_validators: Optional[List[AsyncValidatorFn]] = None):
        self.validators: List[ValidatorFn] = validators or []
        self.async_validators: List[AsyncValidatorFn] = async_validators or []
        self.errors: Optional[ValidationErrors] = None
        self.status: str = "VALID"  # VALID, INVALID, PENDING
        self.pristine: bool = True
        self.touched: bool = False
        self._value_listeners: List[Callable[[Any], None]] = []
        self._status_listeners: List[Callable[[str], None]] = []

    @property
    def dirty(self) -> bool:
        return not self.pristine

    @property
    def untouched(self) -> bool:
        return not self.touched

    @property
    def valid(self) -> bool:
        return self.status == "VALID"

    @property
    def invalid(self) -> bool:
        return self.status == "INVALID"

    @property
    def pending(self) -> bool:
        return self.status == "PENDING"

    def mark_as_touched(self) -> None:
        self.touched = True

    def mark_as_dirty(self) -> None:
        self.pristine = False

    def subscribe_value_changes(self, callback: Callable[[Any], None]) -> None:
        self._value_listeners.append(callback)

    def subscribe_status_changes(self, callback: Callable[[str], None]) -> None:
        self._status_listeners.append(callback)

    def _notify_changes(self, value: Any) -> None:
        for listener in self._value_listeners:
            listener(value)

    def _notify_status(self, status: str) -> None:
        for listener in self._status_listeners:
            listener(status)

    def set_validators(self, validators: List[ValidatorFn]) -> None:
        self.validators = validators

    def update_value_and_validity(self, emit_event: bool = True) -> None:
        raise NotImplementedError


class FormControl(AbstractControl):
    """Meniru @angular/forms FormControl."""
    def __init__(self, initial_value: Any = None,
                 validators: Optional[List[ValidatorFn]] = None,
                 async_validators: Optional[List[AsyncValidatorFn]] = None):
        super().__init__(validators, async_validators)
        self.value: Any = initial_value
        self.update_value_and_validity(emit_event=False)

    def set_value(self, new_value: Any, emit_event: bool = True) -> None:
        self.value = new_value
        self.mark_as_dirty()
        self.update_value_and_validity(emit_event=emit_event)
        if emit_event:
            self._notify_changes(self.value)

    def update_value_and_validity(self, emit_event: bool = True) -> None:
        # 1. Jalankan synchronous validators
        errors = ValidationErrors()
        for v in self.validators:
            res = v(self)
            if res:
                errors.update(res)

        if errors:
            self.errors = errors
            self.status = "INVALID"
            if emit_event:
                self._notify_status(self.status)
            return

        # 2. Jika sync lolos & ada async validator -> status PENDING
        if self.async_validators:
            self.status = "PENDING"
            self.errors = None
            if emit_event:
                self._notify_status(self.status)

            # Jalankan simulasi async (microtask / network request)
            for av in self.async_validators:
                async_res = av(self)
                if async_res:
                    errors.update(async_res)

            if errors:
                self.errors = errors
                self.status = "INVALID"
            else:
                self.errors = None
                self.status = "VALID"

            if emit_event:
                self._notify_status(self.status)
        else:
            self.errors = None
            self.status = "VALID"
            if emit_event:
                self._notify_status(self.status)


class FormGroup(AbstractControl):
    """Meniru @angular/forms FormGroup."""
    def __init__(self, controls: Dict[str, AbstractControl],
                 validators: Optional[List[ValidatorFn]] = None):
        super().__init__(validators)
        self.controls: Dict[str, AbstractControl] = controls
        self.update_value_and_validity(emit_event=False)

    def get(self, name: str) -> Optional[AbstractControl]:
        return self.controls.get(name)

    @property
    def value(self) -> Dict[str, Any]:
        return {k: getattr(ctrl, 'value', None) for k, ctrl in self.controls.items()}

    def patch_value(self, values: Dict[str, Any], emit_event: bool = True) -> None:
        for k, v in values.items():
            if k in self.controls:
                ctrl = self.controls[k]
                if isinstance(ctrl, FormControl):
                    ctrl.set_value(v, emit_event=emit_event)
        self.mark_as_dirty()
        self.update_value_and_validity(emit_event=emit_event)

    def update_value_and_validity(self, emit_event: bool = True) -> None:
        # Cek anak kontrol terlebih dahulu
        any_invalid = False
        any_pending = False
        for ctrl in self.controls.values():
            if ctrl.pending:
                any_pending = True
            elif ctrl.invalid:
                any_invalid = True

        if any_pending:
            self.status = "PENDING"
            self.errors = None
            if emit_event:
                self._notify_status(self.status)
            return

        if any_invalid:
            self.status = "INVALID"
            if emit_event:
                self._notify_status(self.status)
            return

        # Jalankan cross-field form-level validators
        errors = ValidationErrors()
        for v in self.validators:
            res = v(self)
            if res:
                errors.update(res)

        if errors:
            self.errors = errors
            self.status = "INVALID"
        else:
            self.errors = None
            self.status = "VALID"

        if emit_event:
            self._notify_status(self.status)


class FormArray(AbstractControl):
    """Meniru @angular/forms FormArray."""
    def __init__(self, controls: Optional[List[AbstractControl]] = None,
                 validators: Optional[List[ValidatorFn]] = None):
        super().__init__(validators)
        self.controls: List[AbstractControl] = controls or []
        self.update_value_and_validity(emit_event=False)

    @property
    def value(self) -> List[Any]:
        return [ctrl.value for ctrl in self.controls]

    def push(self, control: AbstractControl) -> None:
        self.controls.append(control)
        self.mark_as_dirty()
        self.update_value_and_validity(emit_event=True)

    def remove_at(self, index: int) -> None:
        if 0 <= index < len(self.controls):
            del self.controls[index]
            self.mark_as_dirty()
            self.update_value_and_validity(emit_event=True)

    def update_value_and_validity(self, emit_event: bool = True) -> None:
        any_invalid = any(ctrl.invalid for ctrl in self.controls)
        any_pending = any(ctrl.pending for ctrl in self.controls)

        if any_pending:
            self.status = "PENDING"
        elif any_invalid:
            self.status = "INVALID"
        else:
            errors = ValidationErrors()
            for v in self.validators:
                res = v(self)
                if res:
                    errors.update(res)
            if errors:
                self.errors = errors
                self.status = "INVALID"
            else:
                self.errors = None
                self.status = "VALID"

        if emit_event:
            self._notify_status(self.status)


# ==============================================================================
# Enterprise Validators (Sync, Async & Cross-Field)
# ==============================================================================

class Validators:
    @staticmethod
    def required(control: AbstractControl) -> Optional[ValidationErrors]:
        val = getattr(control, 'value', None)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return ValidationErrors({"required": True})
        return None

    @staticmethod
    def email(control: AbstractControl) -> Optional[ValidationErrors]:
        val = getattr(control, 'value', "")
        if not val:
            return None
        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(pattern, str(val)):
            return ValidationErrors({"email": "Format email tidak valid"})
        return None

    @staticmethod
    def min_length(min_len: int) -> ValidatorFn:
        def validator(control: AbstractControl) -> Optional[ValidationErrors]:
            val = getattr(control, 'value', "")
            if val and len(str(val)) < min_len:
                return ValidationErrors({
                    "minlength": {
                        "requiredLength": min_len,
                        "actualLength": len(str(val))
                    }
                })
            return None
        return validator

    @staticmethod
    def min_array_items(min_items: int) -> ValidatorFn:
        def validator(control: AbstractControl) -> Optional[ValidationErrors]:
            if isinstance(control, FormArray):
                if len(control.controls) < min_items:
                    return ValidationErrors({
                        "minItems": {
                            "required": min_items,
                            "actual": len(control.controls)
                        }
                    })
            return None
        return validator


def password_match_validator(control: AbstractControl) -> Optional[ValidationErrors]:
    """Cross-field validator pada level FormGroup untuk verifikasi konfirmasi password."""
    if not isinstance(control, FormGroup):
        return None
    pwd_ctrl = control.get("password")
    confirm_ctrl = control.get("confirmPassword")
    if not pwd_ctrl or not confirm_ctrl:
        return None

    pwd = pwd_ctrl.value
    confirm = confirm_ctrl.value
    if pwd and confirm and pwd != confirm:
        return ValidationErrors({"passwordMismatch": True})
    return None


def enterprise_domain_validator(allowed_domains: List[str]) -> ValidatorFn:
    """Custom validator untuk memastikan email menggunakan corporate domain."""
    def validator(control: AbstractControl) -> Optional[ValidationErrors]:
        val = str(getattr(control, 'value', '') or '')
        if not val or '@' not in val:
            return None
        domain = val.split('@')[-1].lower()
        if domain not in [d.lower() for d in allowed_domains]:
            return ValidationErrors({
                "corporateDomain": {
                    "allowedDomains": allowed_domains,
                    "actualDomain": domain
                }
            })
        return None
    return validator


def async_unique_username_validator(simulated_delay_sec: float = 0.15) -> AsyncValidatorFn:
    """Async validator: meniru HTTP call debounce ke API database keunikan username."""
    registered_users = {"admin", "root", "superman", "budi.santoso", "angular.architect"}

    def async_validator(control: AbstractControl) -> Optional[ValidationErrors]:
        val = str(getattr(control, 'value', '') or '').strip().lower()
        if not val:
            return None
        # Simulasi network latency
        time.sleep(simulated_delay_sec)
        if val in registered_users:
            return ValidationErrors({
                "usernameTaken": {
                    "suggestedAlternative": f"{val}_{int(time.time()) % 1000}"
                }
            })
        return None
    return async_validator


# ==============================================================================
# Visual Form Inspector & UI Renderer
# ==============================================================================

def print_banner() -> None:
    print(f"{CYAN}{BOLD}================================================================={RESET}")
    print(f"{CYAN}{BOLD}  ANGULAR ENTERPRISE REACTIVE FORMS ENGINE - SIMULASI INTERAKTIF  {RESET}")
    print(f"{CYAN}{BOLD}       Topik: Validasi Reaktif, Async Check & Cross-Field         {RESET}")
    print(f"{CYAN}{BOLD}================================================================={RESET}\n")


def display_control_card(title: str, control: AbstractControl) -> None:
    status_color = GREEN if control.valid else (YELLOW if control.pending else RED)
    status_badge = f"{status_color}{BOLD}[ {control.status} ]{RESET}"

    dirty_badge = f"{YELLOW}DIRTY{RESET}" if control.dirty else f"{DIM}PRISTINE{RESET}"
    touched_badge = f"{MAGENTA}TOUCHED{RESET}" if control.touched else f"{DIM}UNTOUCHED{RESET}"

    print(f"  {BOLD}* {title}{RESET} {status_badge} ({dirty_badge}, {touched_badge})")
    if hasattr(control, 'value'):
        print(f"    Value  : {CYAN}{control.value}{RESET}")
    if control.errors:
        print(f"    Errors : {RED}{control.errors}{RESET}")
    print()


def run_enterprise_form_demo() -> None:
    print_banner()

    print(f"{YELLOW}[Langkah 1/5] Inisialisasi Enterprise Employee Registration Form{RESET}")
    print("Membangun FormGroup dengan kontrol bertingkat, form array, dan cross-field validator...")

    # Form initialization
    reg_form = FormGroup(
        controls={
            "username": FormControl(
                "",
                validators=[Validators.required, Validators.min_length(4)],
                async_validators=[async_unique_username_validator()]
            ),
            "email": FormControl(
                "",
                validators=[
                    Validators.required,
                    Validators.email,
                    enterprise_domain_validator(["corporate.id", "enterprise.org"])
                ]
            ),
            "password": FormControl(
                "",
                validators=[Validators.required, Validators.min_length(8)]
            ),
            "confirmPassword": FormControl(
                "",
                validators=[Validators.required]
            ),
            "roles": FormArray(
                controls=[FormControl("Employee")],
                validators=[Validators.min_array_items(2)]
            )
        },
        validators=[password_match_validator]
    )

    # Listen to reactive observables (valueChanges & statusChanges)
    reg_form.subscribe_status_changes(lambda status: print(
        f"    {MAGENTA}⚡ [Stream statusChanges Event]{RESET} Form Status berubah menjadi -> {BOLD}{status}{RESET}"
    ))

    print(f"\n{CYAN}Status Awal Form (Sebelum Input):{RESET}")
    display_control_card("Registration FormGroup", reg_form)

    # Langkah 2: Simulasi Input Tidak Valid & Pelanggaran Domain
    print(f"{YELLOW}[Langkah 2/5] User memasukkan data awal tidak valid{RESET}")
    print("Set username='adm' (terlalu pendek), email='user@gmail.com' (domain publik non-enterprise)...")

    username_ctrl = reg_form.get("username")
    email_ctrl = reg_form.get("email")

    if isinstance(username_ctrl, FormControl):
        username_ctrl.set_value("adm")
        username_ctrl.mark_as_touched()

    if isinstance(email_ctrl, FormControl):
        email_ctrl.set_value("user@gmail.com")
        email_ctrl.mark_as_touched()

    reg_form.update_value_and_validity()

    display_control_card("Control 'username'", username_ctrl)
    display_control_card("Control 'email'", email_ctrl)
    display_control_card("FormGroup Root", reg_form)

    # Langkah 3: Simulasi Async Validator (Username Conflict)
    print(f"{YELLOW}[Langkah 3/5] Uji Coba Async Validator (Cek Database ''){RESET}")
    print("Menguji username 'admin' yang sudah terdaftar di backend mock database...")

    if isinstance(username_ctrl, FormControl):
        username_ctrl.set_value("admin")

    display_control_card("Control 'username' (Async Evaluated)", username_ctrl)

    # Perbaiki username dengan id unik
    print("Memperbaiki username menjadi 'budi.developer' (lolos keunikan DB)...")
    if isinstance(username_ctrl, FormControl):
        username_ctrl.set_value("budi.developer")
    display_control_card("Control 'username' (Lolos)", username_ctrl)

    # Langkah 4: Cross-Field Password Match Validator
    print(f"{YELLOW}[Langkah 4/5] Menguji Cross-Field Validation (Password Mismatch){RESET}")
    pwd_ctrl = reg_form.get("password")
    confirm_ctrl = reg_form.get("confirmPassword")

    if isinstance(pwd_ctrl, FormControl) and isinstance(confirm_ctrl, FormControl):
        pwd_ctrl.set_value("Secret@12345")
        confirm_ctrl.set_value("Secret@Typo")

    reg_form.update_value_and_validity()
    display_control_card("FormGroup (Check passwordMismatch)", reg_form)

    print("Sinkronisasi konfirmasi password agar cocok...")
    if isinstance(confirm_ctrl, FormControl):
        confirm_ctrl.set_value("Secret@12345")

    if isinstance(email_ctrl, FormControl):
        email_ctrl.set_value("budi@corporate.id")

    reg_form.update_value_and_validity()
    display_control_card("FormGroup Setelah Password Selaras", reg_form)

    # Langkah 5: FormArray Dynamic Controls
    print(f"{YELLOW}[Langkah 5/5] FormArray Dynamic Controls (Minimal 2 Role Jabatan){RESET}")
    roles_array = reg_form.get("roles")
    if isinstance(roles_array, FormArray):
        print(f"Role saat ini: {roles_array.value} -> Status Array: {roles_array.status} ({roles_array.errors})")
        print("Menambahkan role kedua: 'Lead Developer' secara dinamis...")
        roles_array.push(FormControl("Lead Developer"))
        print(f"Role terbaru : {roles_array.value} -> Status Array: {roles_array.status}")

    reg_form.update_value_and_validity()

    print(f"\n{GREEN}{BOLD}=== REKAPITULASI AKHIR STATUS FORM ENTERPRISE ==={RESET}")
    display_control_card("Final Registration FormGroup", reg_form)

    if reg_form.valid:
        print(f"{GREEN}{BOLD}✔ SUKSES: Semua validasi reaktif enterprise berhasil dipenuhi! Form siap disubmit.{RESET}\n")
    else:
        print(f"{RED}{BOLD}✘ Form masih memiliki kendala validasi.{RESET}\n")


if __name__ == "__main__":
    run_enterprise_form_demo()
