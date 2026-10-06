#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Ruby Testing Rigor & Static Analysis
Topik: RSpec/Minitest DSL, RuboCop AST Linting, Steep/Sorbet Static Typing, & SimpleCov
BAB-07: Testing Rigor & Static Analysis
"""

import sys
import time
import re
from typing import Callable, List, Dict, Any, Optional

# --- Terminal ANSI Color Constants ---
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
BG_DARK = "\033[40m"


def header(title: str) -> None:
    line = "=" * 70
    print(f"\n{BLUE}{BOLD}{line}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{BLUE}{BOLD}{line}{RESET}\n")


def status_badge(label: str, success: bool) -> str:
    if success:
        return f"{GREEN}{BOLD}[PASS] {label}{RESET}"
    return f"{RED}{BOLD}[FAIL] {label}{RESET}"


# ==============================================================================
# 1. RSpec / Minitest Specification DSL Simulation
# ==============================================================================
class ExpectationTarget:
    def __init__(self, actual: Any):
        self.actual = actual

    def to_eq(self, expected: Any) -> None:
        if self.actual != expected:
            raise AssertionError(f"Expected {expected!r} ({type(expected).__name__}), but got {self.actual!r} ({type(self.actual).__name__})")

    def not_to_be_nil(self) -> None:
        if self.actual is None:
            raise AssertionError("Expected value to not be nil, but got None")

    def to_include(self, item: Any) -> None:
        if item not in self.actual:
            raise AssertionError(f"Expected collection to include {item!r}, but it was missing in {self.actual!r}")

    def to_raise(self, exc_type: type) -> None:
        if not callable(self.actual):
            raise TypeError("Target must be a callable to assert exceptions")
        try:
            self.actual()
            raise AssertionError(f"Expected exception {exc_type.__name__}, but nothing was raised")
        except exc_type:
            pass  # Expected behavior
        except Exception as e:
            raise AssertionError(f"Expected {exc_type.__name__}, but caught {type(e).__name__}: {e}")


def expect(target: Any) -> ExpectationTarget:
    return ExpectationTarget(target)


class RSpecRunner:
    def __init__(self):
        self.examples: List[Dict[str, Any]] = []

    def describe(self, context_name: str, definition_fn: Callable) -> None:
        definition_fn(self, context_name)

    def it(self, description: str, test_fn: Callable) -> None:
        self.examples.append({"desc": description, "fn": test_fn})

    def run(self) -> None:
        print(f"{BOLD}{WHITE}Menjalankan Test Suite (RSpec Simulation)...{RESET}")
        passed = 0
        failed = 0
        failures = []

        start_time = time.time()
        for idx, ex in enumerate(self.examples, 1):
            try:
                ex["fn"]()
                print(f"{GREEN}.{RESET}", end="", flush=True)
                passed += 1
            except AssertionError as err:
                print(f"{RED}F{RESET}", end="", flush=True)
                failed += 1
                failures.append((ex["desc"], str(err)))
            time.sleep(0.04)

        elapsed = time.time() - start_time
        print("\n")

        if failures:
            print(f"{RED}{BOLD}Failures / Kegagalan Spec:{RESET}")
            for i, (desc, reason) in enumerate(failures, 1):
                print(f"  {RED}{i}) Failure in spec: {desc}{RESET}")
                print(f"     {YELLOW}Penyebab: {reason}{RESET}")
            print()

        total = passed + failed
        print(f"Finished in {elapsed:.4f} seconds")
        summary_color = GREEN if failed == 0 else RED
        print(f"{summary_color}{BOLD}{total} examples, {failed} failures, 0 pending{RESET}\n")


# ==============================================================================
# 2. RuboCop Static Analysis & AST Linting Cop Simulation
# ==============================================================================
class RuboCopSimulation:
    def __init__(self):
        self.rules = [
            ("Style/FrozenStringLiteralComment", r"^#\s*frozen_string_literal:\s*true", "Tambahkan `# frozen_string_literal: true` di baris pertama untuk optimasi memori string."),
            ("Naming/MethodName", r"def\s+[a-z_][a-z0-9_]*[!?]?", "Nama method harus snake_case."),
            ("Layout/LineLength", None, "Panjang baris maksimal 80 karakter (RuboCop Style Guide)."),
            ("Lint/UselessAssignment", r"^\s*([a-zA-Z_]\w*)\s*=\s*[^=]", "Variabel dideklarasikan namun tidak pernah dibaca.")
        ]

    def analyze(self, ruby_code: str) -> None:
        lines = ruby_code.strip().split("\n")
        print(f"{BOLD}{WHITE}Menganalisis Kode Ruby dengan RuboCop Engine (Simulasi AST/Cops)...{RESET}")
        print(f"{DIM}Target buffer: {len(lines)} baris kode{RESET}\n")

        offenses = []

        # Check rule 1: Frozen String Literal
        if not re.search(self.rules[0][1], lines[0]):
            offenses.append((1, 1, "C", self.rules[0][0], self.rules[0][2]))

        # Check line lengths and naming conventions
        for idx, line in enumerate(lines, start=1):
            if len(line) > 80:
                offenses.append((idx, 81, "C", "Layout/LineLength", f"Baris terlalu panjang ({len(line)}/80 karakter)."))
            
            # Check CamelCase method names
            method_match = re.search(r"def\s+([A-Za-z0-9_]+)", line)
            if method_match:
                name = method_match.group(1)
                if any(c.isupper() for c in name):
                    offenses.append((idx, line.find(name) + 1, "C", "Naming/MethodName", f"Method `{name}` melanggar konvensi snake_case."))

        # Display results in RuboCop standard format
        if not offenses:
            print(f"{GREEN}Inspecting 1 file{RESET}")
            print(f"{GREEN}.{RESET}\n1 file inspected, {GREEN}no offenses detected{RESET}\n")
            return

        print(f"{RED}Inspecting 1 file{RESET}")
        print(f"{RED}W{RESET}\nOffenses:")

        for line_no, col, severity, cop, msg in offenses:
            sev_color = YELLOW if severity == "W" else CYAN
            print(f"  sample_service.rb:{line_no}:{col}: {sev_color}{severity}{RESET}: [{cop}] {msg}")
            snippet = lines[line_no - 1]
            print(f"    {DIM}{snippet}{RESET}")
            print(f"    {' ' * (col - 1)}{RED}^{RESET}")

        print(f"\n1 file inspected, {RED}{len(offenses)} offenses detected{RESET} (RuboCop Linting Failure)\n")


# ==============================================================================
# 3. Static Type Analysis (Sorbet / Steep RBS Simulation)
# ==============================================================================
class StaticTypeChecker:
    def __init__(self):
        self.signatures: Dict[str, Dict[str, Any]] = {}

    def register_sig(self, method_name: str, params: Dict[str, type], return_type: type) -> None:
        self.signatures[method_name] = {"params": params, "return": return_type}

    def type_check_call(self, method_name: str, args: Dict[str, Any], simulated_ret: Any) -> None:
        if method_name not in self.signatures:
            return

        sig = self.signatures[method_name]
        print(f"{CYAN}[Sorbet/Steep Check]{RESET} Memeriksa pemanggilan method `{method_name}`:")

        # Param type validation
        for param, expected_type in sig["params"].items():
            val = args.get(param)
            actual_type = type(val)
            if not isinstance(val, expected_type):
                print(f"  {RED}[TypeError] Parameter `{param}`: ekspektasi {expected_type.__name__}, ditemukan {actual_type.__name__} ({val!r}){RESET}")
                return
            else:
                print(f"  {GREEN}[TypeOK] Param `{param}`: {expected_type.__name__} valid.{RESET}")

        # Return type validation
        if not isinstance(simulated_ret, sig["return"]):
            print(f"  {RED}[TypeError] Return type: ekspektasi {sig['return'].__name__}, dihasilkan {type(simulated_ret).__name__}{RESET}")
        else:
            print(f"  {GREEN}[TypeOK] Return type: {sig['return'].__name__} valid.{RESET}\n")


# ==============================================================================
# 4. SimpleCov Code Coverage Simulation
# ==============================================================================
class SimpleCovReporter:
    def __init__(self, filename: str, total_lines: int):
        self.filename = filename
        self.total_lines = total_lines
        self.executed_lines: set = set()

    def hit(self, line_num: int) -> None:
        self.executed_lines.add(line_num)

    def print_report(self) -> None:
        covered = len(self.executed_lines)
        ratio = (covered / self.total_lines) * 100.0
        color = GREEN if ratio >= 90.0 else (YELLOW if ratio >= 75.0 else RED)

        print(f"{BOLD}{WHITE}SimpleCov Coverage Report:{RESET}")
        print(f"  Target File : {self.filename}")
        print(f"  Total Lines : {self.total_lines}")
        print(f"  Lines Hit   : {covered}")
        print(f"  Missed Lines: {self.total_lines - covered}")
        print(f"  Coverage    : {color}{BOLD}{ratio:.2f}%{RESET}")
        
        # ASCII Progress Bar
        bar_len = 30
        filled = int((ratio / 100.0) * bar_len)
        bar = f"{color}{'#' * filled}{DIM}{'-' * (bar_len - filled)}{RESET}"
        print(f"  Metric      : [{bar}]\n")


# ==============================================================================
# Interactive Runner & Demo Execution
# ==============================================================================
def demo_rspec_suite():
    header("Modul 1: Simulasi RSpec / Minitest Specification DSL")
    runner = RSpecRunner()

    def bank_account_specs(r: RSpecRunner, ctx: str):
        print(f"{DIM}Mendefinisikan context: {ctx}{RESET}")

        r.it("bisa melakukan inisialisasi saldo dengan benar", lambda: (
            expect(100_000).to_eq(100_000),
            expect("IDR").not_to_be_nil()
        ))

        r.it("dapat menambah saldo saat transfer masuk diterima", lambda: (
            expect(100_000 + 50_000).to_eq(150_000)
        ))

        r.it("mencegah penarikan melebihi batas saldo (raise InsufficientFunds)", lambda: (
            expect(lambda: (_ for _ in ()).throw(ValueError("Saldo Tidak Cukup"))).to_raise(ValueError)
        ))

        r.it("memastikan whitelist mata uang didukung sistem", lambda: (
            expect(["IDR", "USD", "EUR"]).to_include("SGD")  # Sengaja dibuat gagal untuk demonstrasi
        ))

    runner.describe("BankAccount", bank_account_specs)
    runner.run()


def demo_rubocop():
    header("Modul 2: Simulasi RuboCop Static Code Analysis & AST Linter")
    sample_dirty_ruby = (
        "class OrderPaymentProcessor\n"
        "  def calculateDiscountPercentage(user, total_amount)\n"
        "    tax = 0.11\n"
        "    discount = total_amount * 0.15\n"
        "    puts 'Executing very long processing statement that definitely violates the standard line length rule of rubocop!'\n"
        "    discount\n"
        "  end\n"
        "end"
    )
    rubocop = RuboCopSimulation()
    rubocop.analyze(sample_dirty_ruby)


def demo_type_checker():
    header("Modul 3: Simulasi Static Typing (Sorbet sig / Steep RBS)")
    checker = StaticTypeChecker()

    # sig { params(user_id: Integer, amount: Float).returns(TrueClass) }
    checker.register_sig("charge_credit_card", {"user_id": int, "amount": float}, bool)

    print(f"{WHITE}Skenario A: Pemanggilan Valid (Sesuai signature RBS/Sorbet){RESET}")
    checker.type_check_call("charge_credit_card", {"user_id": 4201, "amount": 250.75}, True)

    print(f"{WHITE}Skenario B: Type Violation / Bug Statis Terdeteksi{RESET}")
    checker.type_check_call("charge_credit_card", {"user_id": "USER-4201", "amount": 250.75}, True)


def demo_simplecov():
    header("Modul 4: Simulasi SimpleCov Code Coverage Tracker")
    cov = SimpleCovReporter("app/services/payment_service.rb", total_lines=24)
    # Simulate execution of lines
    for line in [1, 2, 3, 4, 5, 8, 9, 10, 11, 14, 15, 16, 20, 21, 22, 23]:
        cov.hit(line)
    cov.print_report()


def main():
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{BOLD}{WHITE}  SIMULASI INTERAKTIF: RUBY TESTING RIGOR & STATIC ANALYSIS TOOLCHAIN{RESET}")
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{DIM}Mengintegrasikan konsep: RSpec, Minitest, RuboCop, Sorbet/Steep, SimpleCov{RESET}\n")

    if len(sys.argv) > 1 and sys.argv[1] == "--non-interactive":
        demo_rspec_suite()
        demo_rubocop()
        demo_type_checker()
        demo_simplecov()
        print(f"{GREEN}{BOLD}Semua pengujian dan simulasi statis selesai dijalankan.{RESET}\n")
        return

    menu = (
        f"{CYAN}Pilih Modul Simulasi:{RESET}\n"
        f"  {BOLD}1.{RESET} Jalankan RSpec / Minitest DSL Runner\n"
        f"  {BOLD}2.{RESET} Jalankan RuboCop AST Static Analysis\n"
        f"  {BOLD}3.{RESET} Jalankan Sorbet/Steep RBS Type Checker\n"
        f"  {BOLD}4.{RESET} Tampilkan SimpleCov Coverage Metrics\n"
        f"  {BOLD}5.{RESET} Jalankan Seluruh CI/CD Quality Gate Pipeline\n"
        f"  {BOLD}0.{RESET} Keluar\n"
    )

    while True:
        print(menu)
        try:
            choice = input(f"{YELLOW}Masukkan pilihan (0-5): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Keluar dari program.{RESET}")
            break

        if choice == "1":
            demo_rspec_suite()
        elif choice == "2":
            demo_rubocop()
        elif choice == "3":
            demo_type_checker()
        elif choice == "4":
            demo_simplecov()
        elif choice == "5":
            demo_rspec_suite()
            demo_rubocop()
            demo_type_checker()
            demo_simplecov()
            print(f"{GREEN}{BOLD}Pipeline Verifikasi Rigor Selesai.{RESET}\n")
        elif choice == "0":
            print(f"{GREEN}Terima kasih. Terus terapkan Testing Rigor di Ruby!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}\n")


if __name__ == "__main__":
    main()
