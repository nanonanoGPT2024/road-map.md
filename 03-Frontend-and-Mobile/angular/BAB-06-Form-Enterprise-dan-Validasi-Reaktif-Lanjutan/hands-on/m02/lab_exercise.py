#!/usr/bin/env python3
"""
Lab Hands-on: Angular Enterprise Reactive Forms & Advanced Validation Engine
Simulasi runtime arsitektur Reactive Forms Angular (AbstractControl, FormControl,
FormGroup, Async Validators dengan simulasi RxJS SwitchMap/Debounce, dan Cross-Field Validation).
"""

import re
import time
import threading
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum


# =====================================================================
# ANSI Color Codes untuk visualisasi CLI yang profesional
# =====================================================================
class CLIColor:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class ControlStatus(Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    PENDING = "PENDING"
    DISABLED = "DISABLED"


ValidationErrors = Dict[str, Any]
ValidatorFn = Callable[["AbstractControl"], Optional[ValidationErrors]]
AsyncValidatorFn = Callable[["AbstractControl"], Optional[ValidationErrors]]


# =====================================================================
# Core Reactive Forms Engine (Memodelkan Angular Reactive Engine)
# =====================================================================
class AbstractControl:
    """Kelas abstrak dasar yang memodelkan AbstractControl di Angular."""
    def __init__(
        self,
        validators: Optional[List[ValidatorFn]] = None,
        async_validators: Optional[List[AsyncValidatorFn]] = None
    ):
        self.validators: List[ValidatorFn] = validators or []
        self.async_validators: List[AsyncValidatorFn] = async_validators or []
        self.errors: Optional[ValidationErrors] = None
        self.status: ControlStatus = ControlStatus.VALID
        self.pristine: bool = True
        self.touched: bool = False
        self.parent: Optional["FormGroup"] = None
        self._value_change_listeners: List[Callable[[Any], None]] = []

    @property
    def valid(self) -> bool:
        return self.status == ControlStatus.VALID

    @property
    def invalid(self) -> bool:
        return self.status == ControlStatus.INVALID

    @property
    def pending(self) -> bool:
        return self.status == ControlStatus.PENDING

    @property
    def dirty(self) -> bool:
        return not self.pristine

    def mark_as_touched(self) -> None:
        self.touched = True

    def mark_as_dirty(self) -> None:
        self.pristine = False

    def subscribe_value_changes(self, listener: Callable[[Any], None]) -> None:
        """Simulasi Observable valueChanges.subscribe(...)"""
        self._value_change_listeners.append(listener)

    def _notify_value_changes(self, val: Any) -> None:
        for listener in self._value_change_listeners:
            listener(val)

    def update_value_and_validity(self, emit_event: bool = True) -> None:
        raise NotImplementedError


class FormControl(AbstractControl):
    """
    Memodelkan FormControl: melacak value, status, eksekusi validator sinkron
    serta pembatalan async-request (mirip RxJS switchMap) via generation-token.
    """
    def __init__(
        self,
        initial_value: Any = None,
        validators: Optional[List[ValidatorFn]] = None,
        async_validators: Optional[List[AsyncValidatorFn]] = None
    ):
        super().__init__(validators, async_validators)
        self._value: Any = initial_value
        self._async_request_token: int = 0
        self.update_value_and_validity(emit_event=False)

    @property
    def value(self) -> Any:
        return self._value

    def set_value(self, new_value: Any, emit_event: bool = True) -> None:
        """Mengubah nilai, mengubah flag pristine, dan memicu revalidasi."""
        self._value = new_value
        self.mark_as_dirty()
        self.update_value_and_validity(emit_event=emit_event)

    def set_validators(self, new_validators: List[ValidatorFn]) -> None:
        self.validators = new_validators

    def update_value_and_validity(self, emit_event: bool = True) -> None:
        self.errors = None
        # 1. Jalankan sinkron validator
        for validator in self.validators:
            err = validator(self)
            if err:
                if self.errors is None:
                    self.errors = {}
                self.errors.update(err)

        if self.errors:
            self.status = ControlStatus.INVALID
        elif self.async_validators:
            # 2. Masuk ke state PENDING jika ada async validator
            self.status = ControlStatus.PENDING
            self._execute_async_validators()
        else:
            self.status = ControlStatus.VALID

        if emit_event:
            self._notify_value_changes(self._value)

        # Bubble-up notifikasi validitas ke parent group
        if self.parent:
            self.parent.calculate_group_validity()

    def _execute_async_validators(self) -> None:
        """
        Simulasi async validator dengan switchMap semantics:
        Hanya request terbaru yang diperbolehkan meng-update status.
        """
        self._async_request_token += 1
        current_token = self._async_request_token

        def worker():
            combined_async_errors: ValidationErrors = {}
            for async_val in self.async_validators:
                res = async_val(self)
                if res:
                    combined_async_errors.update(res)

            # Batalkan hasil jika ada input baru yang masuk selama processing (switchMap)
            if current_token != self._async_request_token:
                return

            if combined_async_errors:
                self.errors = combined_async_errors
                self.status = ControlStatus.INVALID
            else:
                self.status = ControlStatus.VALID

            if self.parent:
                self.parent.calculate_group_validity()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()


class FormGroup(AbstractControl):
    """
    Memodelkan FormGroup: memaketkan banyak control dan mendukung
    enterprise cross-field validation (validasi lintas field).
    """
    def __init__(
        self,
        controls: Dict[str, AbstractControl],
        validators: Optional[List[ValidatorFn]] = None
    ):
        super().__init__(validators=validators)
        self.controls: Dict[str, AbstractControl] = controls
        for ctrl in self.controls.values():
            ctrl.parent = self
        self.calculate_group_validity()

    def get(self, path: str) -> Optional[AbstractControl]:
        return self.controls.get(path)

    @property
    def value(self) -> Dict[str, Any]:
        return {name: ctrl.value for name, ctrl in self.controls.items()}

    def calculate_group_validity(self) -> None:
        # Cek status child controls terlebih dahulu
        any_pending = any(ctrl.status == ControlStatus.PENDING for ctrl in self.controls.values())
        any_invalid = any(ctrl.status == ControlStatus.INVALID for ctrl in self.controls.values())

        if any_pending:
            self.status = ControlStatus.PENDING
            self.errors = None
            return

        if any_invalid:
            self.status = ControlStatus.INVALID
            return

        # Jalankan Cross-Field Validators tingkat Group jika seluruh child valid
        self.errors = None
        for validator in self.validators:
            err = validator(self)
            if err:
                if self.errors is None:
                    self.errors = {}
                self.errors.update(err)

        if self.errors:
            self.status = ControlStatus.INVALID
        else:
            self.status = ControlStatus.VALID


# =====================================================================
# Enterprise Validators Suite (Built-in & Custom Enterprise Rules)
# =====================================================================
class Validators:
    @staticmethod
    def required() -> ValidatorFn:
        def _validator(control: AbstractControl) -> Optional[ValidationErrors]:
            val = getattr(control, "value", None)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                return {"required": True}
            return None
        return _validator

    @staticmethod
    def min_length(min_len: int) -> ValidatorFn:
        def _validator(control: AbstractControl) -> Optional[ValidationErrors]:
            val = getattr(control, "value", "")
            if val and len(str(val)) < min_len:
                return {"minlength": {"requiredLength": min_len, "actualLength": len(str(val))}}
            return None
        return _validator

    @staticmethod
    def email() -> ValidatorFn:
        regex = re.compile(r"^[\w\.-]+@([\w\.-]+\.)+[\w-]{2,4}$")
        def _validator(control: AbstractControl) -> Optional[ValidationErrors]:
            val = getattr(control, "value", "")
            if val and not regex.match(str(val)):
                return {"email": True}
            return None
        return _validator


class EnterpriseValidators:
    @staticmethod
    def password_match_validator(password_key: str, confirm_key: str) -> ValidatorFn:
        """Cross-Field Validator: Memastikan password dan konfirmasi identik."""
        def _validator(control: AbstractControl) -> Optional[ValidationErrors]:
            if not isinstance(control, FormGroup):
                return None
            pwd = control.get(password_key)
            confirm = control.get(confirm_key)
            if not pwd or not confirm:
                return None
            if pwd.value != confirm.value and confirm.value != "":
                return {"passwordMismatch": True}
            return None
        return _validator

    @staticmethod
    def unique_username_api(existing_users: List[str], delay_sec: float = 0.4) -> AsyncValidatorFn:
        """Simulasi Async Validator Angular dengan mock HTTP Network Latency."""
        def _async_validator(control: AbstractControl) -> Optional[ValidationErrors]:
            val = getattr(control, "value", "")
            time.sleep(delay_sec)  # Simulasi I/O Backend API
            if str(val).lower() in [u.lower() for u in existing_users]:
                return {"usernameTaken": True}
            return None
        return _async_validator


# =====================================================================
# Runner Visualisasi Lab
# =====================================================================
def print_form_state(step_name: str, form: FormGroup):
    print(f"\n{CLIColor.BOLD}{CLIColor.CYAN}--- {step_name} ---{CLIColor.RESET}")
    print(f"Group Status : {CLIColor.GREEN if form.valid else CLIColor.FAIL if form.invalid else CLIColor.WARNING}{form.status.value}{CLIColor.RESET}")
    print(f"Group Errors : {form.errors}")
    print(f"Form Values  : {form.value}")
    print("Controls Details:")
    for name, ctrl in form.controls.items():
        status_color = CLIColor.GREEN if ctrl.valid else CLIColor.FAIL if ctrl.invalid else CLIColor.WARNING
        print(
            f"  - [{name:<15}] Value: '{ctrl.value}' | Status: {status_color}{ctrl.status.value:<7}{CLIColor.RESET} "
            f"| Dirty: {ctrl.dirty!s:<5} | Errors: {ctrl.errors}"
        )


def main():
    print(f"{CLIColor.HEADER}{CLIColor.BOLD}======================================================================")
    print(" LAB ADVANCED ANGULAR: Enterprise Form Architecture & Async Validators")
    print(f"======================================================================{CLIColor.RESET}")

    mock_user_database = ["admin", "root", "devops_lead", "superman"]

    # 1. Inisialisasi Enterprise FormGroup (Dynamic Registration Form)
    signup_form = FormGroup(
        controls={
            "username": FormControl(
                "",
                validators=[Validators.required(), Validators.min_length(4)],
                async_validators=[EnterpriseValidators.unique_username_api(mock_user_database, delay_sec=0.3)]
            ),
            "email": FormControl("", validators=[Validators.required(), Validators.email()]),
            "role": FormControl("OPERATOR", validators=[Validators.required()]),
            "securityCode": FormControl(""),  # Kondisional validator dinamis
            "password": FormControl("", validators=[Validators.required(), Validators.min_length(6)]),
            "confirmPassword": FormControl("", validators=[Validators.required()]),
        },
        validators=[
            EnterpriseValidators.password_match_validator("password", "confirmPassword")
        ]
    )

    print_form_state("1. Initial Form State (Empty / Untouched)", signup_form)

    # 2. Dynamic Validation: Ubah Role ke ADMIN memicu requirement securityCode
    # Memodelkan pattern Angular: form.get('role').valueChanges.subscribe(...)
    def on_role_change(new_role: str):
        sec_code_ctrl = signup_form.get("securityCode")
        if not sec_code_ctrl:
            return
        if new_role == "ADMIN":
            print(f"{CLIColor.BLUE}[Event: role -> ADMIN] Dynamic Rule Applied: securityCode IS REQUIRED{CLIColor.RESET}")
            sec_code_ctrl.set_validators([Validators.required(), Validators.min_length(4)])
        else:
            print(f"{CLIColor.BLUE}[Event: role -> {new_role}] Dynamic Rule Cleared for securityCode{CLIColor.RESET}")
            sec_code_ctrl.set_validators([])
        sec_code_ctrl.update_value_and_validity()

    signup_form.get("role").subscribe_value_changes(on_role_change)

    # 3. Input Nilai Awal & Tes Async Validation (Duplikat Username)
    print(f"\n{CLIColor.WARNING}[Action] Mengetik username yang sudah terpakai: 'admin'...{CLIColor.RESET}")
    signup_form.get("username").set_value("admin")
    
    # Periksa status sementara: PENDING (RxJS async validator sedang jalan di background)
    print(f"Status Seketika (Async Running): {CLIColor.WARNING}{signup_form.status.value}{CLIColor.RESET}")
    time.sleep(0.4)  # Tunggu thread mock API selesai
    print_form_state("2. State Pasca Async Validation Username 'admin'", signup_form)

    # 4. Memperbaiki Username & Mengisi Field Lainnya (Memicu Cross-Field Error)
    print(f"\n{CLIColor.WARNING}[Action] Memperbaiki username menjadi 'john_doe' dan mengisi password yang tidak cocok...{CLIColor.RESET}")
    signup_form.get("username").set_value("john_doe")
    signup_form.get("email").set_value("john@enterprise.internal")
    signup_form.get("password").set_value("P@ssw0rd123")
    signup_form.get("confirmPassword").set_value("WrongPassword")
    time.sleep(0.4)  # Tunggu async validasi username baru
    print_form_state("3. State Cross-Field Validation (Password Mismatch)", signup_form)

    # 5. Dynamic Conditional Validator Trigger (Set Role = ADMIN)
    print(f"\n{CLIColor.WARNING}[Action] Mencocokkan password dan menaikkan role ke 'ADMIN'...{CLIColor.RESET}")
    signup_form.get("confirmPassword").set_value("P@ssw0rd123")
    signup_form.get("role").set_value("ADMIN")
    print_form_state("4. State Setelah Role ADMIN (securityCode belum diisi)", signup_form)

    # 6. Memenuhi seluruh kriteria validasi enterprise
    print(f"\n{CLIColor.WARNING}[Action] Memasukkan securityCode 'SEC-9988' untuk ADMIN...{CLIColor.RESET}")
    signup_form.get("securityCode").set_value("SEC-9988")
    print_form_state("5. Final Enterprise Form State (Semua Valid)", signup_form)

    # Verifikasi Kelayakan Submit
    print(f"\n{CLIColor.BOLD}Evaluasi Pengiriman Form:{CLIColor.RESET}")
    if signup_form.valid:
        print(f"{CLIColor.GREEN}✔ Form SIAP DISUBMIT ke Enterprise API Gateway.{CLIColor.RESET}")
        print(f"Payload JSON:\n{signup_form.value}")
    else:
        print(f"{CLIColor.FAIL}✘ Form DITOLAK: Masih terdapat error validasi.{CLIColor.RESET}")


if __name__ == "__main__":
    main()