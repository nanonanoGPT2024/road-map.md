#!/usr/bin/env python3
"""
Lab Exercise: Enterprise Form Systems & Mutation Workflows
Simulasi Arsitektur React Enterprise: Form Controller, Schema Resolver, & Optimistic Mutation
"""

import sys
import time
import copy
from typing import Dict, Any, List, Optional, Callable, Tuple

# ==============================================================================
# ANSI Color Palette for Terminal Output
# ==============================================================================
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
BG_DARK = "\033[40m"


def print_banner(title: str) -> None:
    line = "=" * 68
    print(f"\n{CYAN}{BOLD}{line}{RESET}")
    print(f"{CYAN}{BOLD}  🚀 {title.upper()}{RESET}")
    print(f"{CYAN}{BOLD}{line}{RESET}\n")


def print_badge(label: str, text: str, color: str = CYAN) -> None:
    print(f"{color}{BOLD}[{label}]{RESET} {text}")


# ==============================================================================
# 1. Validation Schema & Resolver Engine (Simulasi Zod / Yup)
# ==============================================================================
class ValidationError(Exception):
    def __init__(self, errors: Dict[str, str]):
        super().__init__("Validation failed")
        self.errors = errors


class FieldValidator:
    def __init__(self, name: str):
        self.name = name
        self.rules: List[Tuple[Callable[[Any], bool], str]] = []

    def required(self, message: str = "Field ini wajib diisi") -> "FieldValidator":
        self.rules.append((lambda v: v is not None and str(v).strip() != "", message))
        return self

    def min_length(self, min_len: int, message: Optional[str] = None) -> "FieldValidator":
        msg = message or f"Panjang minimal {min_len} karakter"
        self.rules.append((lambda v: len(str(v or "").strip()) >= min_len, msg))
        return self

    def email(self, message: str = "Format email tidak valid") -> "FieldValidator":
        self.rules.append((lambda v: "@" in str(v) and "." in str(v), message))
        return self

    def validate(self, value: Any) -> Optional[str]:
        for predicate, err_msg in self.rules:
            if not predicate(value):
                return err_msg
        return None


class Schema:
    def __init__(self, fields: Dict[str, FieldValidator]):
        self.fields = fields

    def validate(self, values: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
        errors: Dict[str, str] = {}
        for field_name, validator in self.fields.items():
            err = validator.validate(values.get(field_name))
            if err:
                errors[field_name] = err
        return len(errors) == 0, errors


# ==============================================================================
# 2. Form Controller (Simulasi React Hook Form State Machine)
# ==============================================================================
class FormController:
    def __init__(self, initial_values: Dict[str, Any], schema: Schema):
        self.initial_values = copy.deepcopy(initial_values)
        self.values = copy.deepcopy(initial_values)
        self.schema = schema
        self.errors: Dict[str, str] = {}
        self.touched: Dict[str, bool] = {k: False for k in initial_values}
        self.is_submitting: bool = False
        self.submit_count: int = 0

    @property
    def is_dirty(self) -> bool:
        return any(self.values.get(k) != self.initial_values.get(k) for k in self.initial_values)

    @property
    def is_valid(self) -> bool:
        is_valid, _ = self.schema.validate(self.values)
        return is_valid

    def set_field_value(self, field: str, value: Any) -> None:
        self.values[field] = value
        self.touched[field] = True
        # Re-validate field per input change (Simulasi mode: 'onChange')
        if field in self.schema.fields:
            err = self.schema.fields[field].validate(value)
            if err:
                self.errors[field] = err
            else:
                self.errors.pop(field, None)

    def trigger_blur(self, field: str) -> None:
        self.touched[field] = True

    def reset(self) -> None:
        self.values = copy.deepcopy(self.initial_values)
        self.errors.clear()
        self.touched = {k: False for k in self.initial_values}
        self.is_submitting = False

    def render_debug_state(self) -> None:
        print(f"{DIM}┌───────────────────────── FORM STATE MONITOR ────────────────────────┐{RESET}")
        dirty_badge = f"{GREEN}DIRTY{RESET}" if self.is_dirty else f"{DIM}PRISTINE{RESET}"
        valid_badge = f"{GREEN}VALID{RESET}" if self.is_valid else f"{RED}INVALID{RESET}"
        submit_badge = f"{YELLOW}SUBMITTING{RESET}" if self.is_submitting else f"{DIM}IDLE{RESET}"

        print(f"{DIM}│{RESET} Status: [{dirty_badge}] [{valid_badge}] [{submit_badge}] | Submits: {self.submit_count}")
        print(f"{DIM}├─────────────────────────────────────────────────────────────────────┤{RESET}")
        for field, val in self.values.items():
            t_flag = f"{CYAN}touched{RESET}" if self.touched.get(field) else f"{DIM}untouched{RESET}"
            err = self.errors.get(field)
            err_label = f" -> {RED}✖ {err}{RESET}" if err else f" -> {GREEN}✔ OK{RESET}"
            val_display = f"'{val}'" if val else f"{DIM}(empty){RESET}"
            print(f"{DIM}│{RESET}  • {BOLD}{field:<12}{RESET}: {val_display:<20} [{t_flag}]{err_label}")
        print(f"{DIM}└─────────────────────────────────────────────────────────────────────┘{RESET}\n")


# ==============================================================================
# 3. Optimistic Mutation Engine (Simulasi TanStack Query / React 19 Actions)
# ==============================================================================
class RemoteServerDB:
    def __init__(self):
        self.records: Dict[str, Dict[str, Any]] = {
            "usr-101": {
                "id": "usr-101",
                "username": "octocat",
                "email": "octo@enterprise.io",
                "role": "Admin",
            }
        }

    def update(self, user_id: str, new_data: Dict[str, Any], should_fail: bool = False) -> Dict[str, Any]:
        time.sleep(0.6)  # Simulated Network RTT
        if should_fail:
            raise RuntimeError("500 Internal Server Error: Database deadlock occurred!")
        if user_id not in self.records:
            raise KeyError(f"User {user_id} not found")
        self.records[user_id].update(new_data)
        return copy.deepcopy(self.records[user_id])


class MutationClient:
    def __init__(self, server: RemoteServerDB):
        self.server = server
        self.query_cache: Dict[str, Any] = copy.deepcopy(server.records)

    def mutate_optimistic(
        self,
        mutation_key: str,
        user_id: str,
        payload: Dict[str, Any],
        simulate_failure: bool = False,
    ) -> bool:
        print_badge("MUTATION", f"Memulai optimistik mutasi untuk [{user_id}]", MAGENTA)

        # 1. Snapshot previous state (rollback checkpoint)
        previous_snapshot = copy.deepcopy(self.query_cache.get(user_id))
        print_badge("CACHE", f"Membuat snapshot rollback: {previous_snapshot}", DIM)

        # 2. Apply Optimistic Update to UI Cache immediately
        print_badge("OPTIMISTIC", f"Mengaplikasikan data baru ke client cache instan...", YELLOW)
        if user_id in self.query_cache:
            self.query_cache[user_id].update(payload)
        print(f"  {CYAN}⚡ Current Cache (Optimistic UI):{RESET} {self.query_cache.get(user_id)}")

        # 3. Send mutation to remote server
        print_badge("NETWORK", "Mengirim payload ke server backend (RTT 600ms)...", BLUE)
        try:
            confirmed_data = self.server.update(user_id, payload, should_fail=simulate_failure)
            # 4a. On Success: Commit to cache & revalidate
            self.query_cache[user_id] = confirmed_data
            print_badge("SUCCESS", f"Server 200 OK. Cache diverifikasi: {confirmed_data}", GREEN)
            return True
        except Exception as e:
            # 4b. On Error: Automatic Rollback
            print_badge("ERROR", f"Mutasi Gagal: {e}", RED)
            print_badge("ROLLBACK", "Mengembalikan client cache ke snapshot sebelumnya...", RED)
            self.query_cache[user_id] = previous_snapshot
            print(f"  {YELLOW}↺ Restored Cache:{RESET} {self.query_cache.get(user_id)}")
            return False


# ==============================================================================
# 4. Interactive Simulation & Scenarios
# ==============================================================================
def create_sample_schema() -> Schema:
    return Schema({
        "username": FieldValidator("username").required().min_length(4, "Minimal 4 karakter"),
        "email": FieldValidator("email").required().email(),
        "role": FieldValidator("role").required("Pilih salah satu role"),
    })


def run_automated_scenarios():
    print_banner("SIMULASI 1: VALIDASI ENTERPRISE FORM (REACT HOOK FORM + RESOLVER)")
    schema = create_sample_schema()
    initial_user = {"username": "octocat", "email": "octo@enterprise.io", "role": "Admin"}
    form = FormController(initial_user, schema)

    form.render_debug_state()

    print_badge("USER EVENT", "User mengetik username tidak valid 'ab'...")
    form.set_field_value("username", "ab")
    form.render_debug_state()

    print_badge("USER EVENT", "User memasukkan email salah 'not-an-email'...")
    form.set_field_value("email", "not-an-email")
    form.render_debug_state()

    print_badge("USER EVENT", "User memperbaiki input form secara valid...")
    form.set_field_value("username", "superdev")
    form.set_field_value("email", "superdev@enterprise.io")
    form.render_debug_state()

    # --------------------------------------------------------------------------
    print_banner("SIMULASI 2: OPTIMISTIC MUTATION WORKFLOW & AUTOMATIC ROLLBACK")
    server = RemoteServerDB()
    client = MutationClient(server)

    print(f"{BOLD}Kondisi Awal Server:{RESET} {server.records['usr-101']}\n")

    print(f"{WHITE}{BOLD}--- Skenario A: Mutasi Berhasil (Happy Path) ---{RESET}")
    success_payload = {"username": "superdev", "email": "superdev@enterprise.io"}
    client.mutate_optimistic("updateUser", "usr-101", success_payload, simulate_failure=False)

    print(f"\n{WHITE}{BOLD}--- Skenario B: Mutasi Gagal (Server Deadlock & Auto Rollback) ---{RESET}")
    fail_payload = {"username": "corrupt_data", "email": "hacked@bad.com"}
    client.mutate_optimistic("updateUser", "usr-101", fail_payload, simulate_failure=True)

    print(f"\n{GREEN}{BOLD}✔ Status Akhir Cache Konsisten dengan Server!{RESET}")
    print(f"  Client Cache : {client.query_cache['usr-101']}")
    print(f"  Server State : {server.records['usr-101']}")


def interactive_mode():
    schema = create_sample_schema()
    initial = {"username": "tech_lead", "email": "lead@company.com", "role": "Member"}
    form = FormController(initial, schema)
    server = RemoteServerDB()
    server.records["usr-101"] = copy.deepcopy(initial)
    server.records["usr-101"]["id"] = "usr-101"
    client = MutationClient(server)

    while True:
        print_banner("INTERACTIVE ENTERPRISE FORM LAB")
        form.render_debug_state()
        print(f"{BOLD}PILIH TINDAKAN:{RESET}")
        print("  1. Edit Field 'username'")
        print("  2. Edit Field 'email'")
        print("  3. Edit Field 'role'")
        print("  4. Submit Form (Optimistic Mutation - Normal)")
        print("  5. Submit Form (Simulasi 500 Network Crash -> Rollback)")
        print("  6. Reset Form")
        print("  7. Jalankan Otomatisasi Lengkap & Keluar")
        print("  0. Keluar")

        choice = input(f"\n{CYAN}Pilihan Anda [0-7]: {RESET}").strip()
        if choice == "0":
            print(f"{GREEN}Terima kasih telah menjalankan simulasi.{RESET}")
            break
        elif choice == "1":
            val = input("Masukkan username baru: ").strip()
            form.set_field_value("username", val)
        elif choice == "2":
            val = input("Masukkan email baru: ").strip()
            form.set_field_value("email", val)
        elif choice == "3":
            val = input("Masukkan role baru (Admin/Member/Guest): ").strip()
            form.set_field_value("role", val)
        elif choice in ("4", "5"):
            form.submit_count += 1
            if not form.is_valid:
                print_badge("BLOCKED", "Form tidak valid! Perbaiki error terlebih dahulu.", RED)
                input(f"{DIM}Tekan Enter untuk lanjut...{RESET}")
                continue
            should_fail = (choice == "5")
            form.is_submitting = True
            form.render_debug_state()
            success = client.mutate_optimistic(
                "updateUser",
                "usr-101",
                form.values,
                simulate_failure=should_fail,
            )
            form.is_submitting = False
            if success:
                form.initial_values = copy.deepcopy(form.values)
            input(f"{DIM}Tekan Enter untuk lanjut...{RESET}")
        elif choice == "6":
            form.reset()
        elif choice == "7":
            run_automated_scenarios()
            break
        else:
            print(f"{RED}Pilihan tidak valid.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_automated_scenarios()
    elif not sys.stdin.isatty():
        # Non-interactive terminal fallback
        run_automated_scenarios()
    else:
        interactive_mode()
