#!/usr/bin/env python3
"""
Lab Exercise: Continuous Integration (CI) Automation Simulator
BAB-06: Continuous Integration & CI Automation (DevOps Beginner)

Simulasi pipeline CI otomatis mandiri dengan validasi tahapan:
1. Code Checkout & Dependency Cache
2. Linter & Static Code Analysis (PEP8 / Formatting)
3. Unit Testing & Code Coverage Threshold
4. SAST / Security Vulnerability Scanning
5. Artifact Build & Container Packaging
6. Pipeline Reporting & Status Notification
"""

import sys
import time
import random

# ANSI Color Codes for terminal UI
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
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}======================================================================
  🚀 DEVOPS LAB: CONTINUOUS INTEGRATION (CI) AUTOMATION PIPELINE
  BAB-06: Continuous Integration Engine & Automated Quality Gates
======================================================================{RESET}
{DIM}Simulasi engine CI (GitHub Actions / GitLab CI) dengan Quality Gates.{RESET}
"""
    print(banner)


def status_badge(passed: bool) -> str:
    if passed:
        return f"{BG_GREEN}{WHITE}{BOLD} PASSED {RESET}"
    return f"{BG_RED}{WHITE}{BOLD} FAILED {RESET}"


def progress_spinner(task_name: str, duration: float = 1.0):
    spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    start_time = time.time()
    idx = 0
    while time.time() - start_time < duration:
        symbol = spinners[idx % len(spinners)]
        sys.stdout.write(f"\r  {CYAN}{symbol}{RESET} {task_name}...")
        sys.stdout.flush()
        time.sleep(0.08)
        idx += 1
    sys.stdout.write("\r" + " " * (len(task_name) + 10) + "\r")


class CIPipelineRunner:
    def __init__(self, commit_sha: str, branch: str, author: str):
        self.commit_sha = commit_sha
        self.branch = branch
        self.author = author
        self.stages_result = []

    def log_stage_header(self, step_no: int, name: str):
        print(f"\n{BLUE}{BOLD}▶ Stage {step_no}: {name}{RESET}")
        print(f"{DIM}{'─' * 55}{RESET}")

    def run_stage_checkout(self) -> bool:
        self.log_stage_header(1, "Source Checkout & Dependency Cache")
        progress_spinner("Mengunduh repository snapshot dari VCS", 0.7)
        print(f"  {GREEN}✔{RESET} HEAD diarahkan ke commit {BOLD}{self.commit_sha[:7]}{RESET} [{self.branch}]")
        progress_spinner("Memeriksa cache hash dependencies (pip/npm)", 0.6)
        print(f"  {GREEN}✔{RESET} Cache hit: dependencies ditemukan di cache runner (saved 45s)")
        self.stages_result.append(("Source Checkout & Cache", True, 1.3))
        return True

    def run_stage_linter(self, inject_failure: bool = False) -> bool:
        self.log_stage_header(2, "Static Code Analysis & Linting (flake8/black)")
        progress_spinner("Menjalankan AST syntax check & PEP8 verification", 0.9)
        if inject_failure:
            print(f"  {RED}✖ E501: Line too long (124 > 79 characters) at services/auth.py:42{RESET}")
            print(f"  {RED}✖ F401: 'os.path' imported but unused at routes/api.py:5{RESET}")
            print(f"  {RED}Gagal memenuhi standard kualitas kode (Quality Gate Lint Error){RESET}")
            self.stages_result.append(("Code Linting", False, 0.9))
            return False
        print(f"  {GREEN}✔{RESET} Semua modul (48 file) lolos aturan PEP8 & code standard.")
        self.stages_result.append(("Code Linting", True, 0.9))
        return True

    def run_stage_unit_tests(self, inject_failure: bool = False) -> bool:
        self.log_stage_header(3, "Automated Unit Tests & Coverage (pytest)")
        test_suites = [
            ("tests/test_auth.py", 8),
            ("tests/test_cart.py", 14),
            ("tests/test_payment.py", 10),
            ("tests/test_metrics.py", 6),
        ]
        total_tests = 0
        for suite, count in test_suites:
            progress_spinner(f"Menjalankan {suite} ({count} test cases)", 0.4)
            total_tests += count
            print(f"  {GREEN}✔{RESET} {suite:<25} {GREEN}{count}/{count} passed{RESET}")

        if inject_failure:
            print(f"\n  {RED}✖ Assertion Error in tests/test_payment.py::test_refund_calculation{RESET}")
            print(f"  {RED}  Expected total: 150000, Actual: 145000 (Mismatch discount tax){RESET}")
            self.stages_result.append(("Unit Tests & Coverage", False, 1.6))
            return False

        coverage = random.uniform(85.5, 94.0)
        min_cov = 80.0
        print(f"\n  {CYAN}ℹ Test Summary:{RESET} {total_tests} tests executed. Code Coverage: {BOLD}{coverage:.1f}%{RESET}")
        print(f"  {GREEN}✔ Quality Gate Coverage Pass:{RESET} {coverage:.1f}% >= threshold {min_cov}%")
        self.stages_result.append(("Unit Tests & Coverage", True, 1.6))
        return True

    def run_stage_sast_security(self, inject_failure: bool = False) -> bool:
        self.log_stage_header(4, "SAST & Secret Detection Scan (Trivy / Bandit)")
        progress_spinner("Memeriksa hardcoded secrets (API Keys, tokens, private keys)", 0.6)
        print(f"  {GREEN}✔{RESET} Secret Scanner: 0 leaks terdeteksi pada commit diff.")

        progress_spinner("Menjalankan SAST vulnerability scanner pada dependency lockfile", 0.7)
        if inject_failure:
            print(f"  {RED}✖ CVE-2023-43804 (CRITICAL): Urllib3 Cookie leak vulnerability{RESET}")
            print(f"  {RED}Security Policy Block: Temuan Severity Critical memblokir pipeline build!{RESET}")
            self.stages_result.append(("Security SAST Scan", False, 1.3))
            return False

        print(f"  {GREEN}✔{RESET} Security Audit: 0 High/Critical vulnerabilities ditemukan.")
        self.stages_result.append(("Security SAST Scan", True, 1.3))
        return True

    def run_stage_build_artifact(self) -> bool:
        self.log_stage_header(5, "Artifact Compilation & Container Image Packaging")
        progress_spinner("Membangun production wheel binary artifact", 0.8)
        print(f"  {GREEN}✔{RESET} Binary package created: dist/order-service-1.4.2-py3-none-any.whl")

        progress_spinner("Membangun OCI Container Image (Docker buildx)", 1.0)
        image_tag = f"registry.internal.io/devops/order-service:{self.commit_sha[:7]}"
        print(f"  {GREEN}✔{RESET} Image built & tagged: {BOLD}{image_tag}{RESET}")
        self.stages_result.append(("Build & Container Packaging", True, 1.8))
        return True

    def run_stage_reporting(self) -> bool:
        self.log_stage_header(6, "Pipeline Summary & Quality Gate Status")
        all_passed = all(status for _, status, _ in self.stages_result)
        total_time = sum(dur for _, _, dur in self.stages_result)

        print(f"\n{BOLD}{'Pipeline Stage':<35} | {'Duration':<10} | {'Status'}{RESET}")
        print("─" * 60)
        for name, passed, dur in self.stages_result:
            color = GREEN if passed else RED
            sym = "PASS" if passed else "FAIL"
            print(f"{name:<35} | {dur:4.1f}s     | {color}{sym}{RESET}")
        print("─" * 60)
        print(f"{BOLD}Total Pipeline Time:{RESET} {total_time:.2f} seconds")
        print(f"{BOLD}Final Quality Gate :{RESET} {status_badge(all_passed)}\n")

        if all_passed:
            print(f"{GREEN}{BOLD}🎉 CI BERHASIL! Kode terverifikasi otomatis dan siap dimerge ke branch target.{RESET}")
        else:
            print(f"{RED}{BOLD}🚨 CI PIPELINE GAGAL! Merge request diblokir sampai issue diperbaiki.{RESET}")
        return all_passed


def run_pipeline_scenario(mode_name: str, lint_err=False, test_err=False, sec_err=False):
    print(f"\n{MAGENTA}{BOLD}>>> MENJALANKAN SKENARIO: {mode_name} <<<{RESET}")
    sha = f"{random.randint(1000000, 9999999):x}"
    runner = CIPipelineRunner(commit_sha=sha, branch="feature/checkout-flow", author="devops-student")

    # Jalankan berurutan (Fail-Fast Mechanism)
    if not runner.run_stage_checkout():
        runner.run_stage_reporting()
        return

    if not runner.run_stage_linter(inject_failure=lint_err):
        print(f"\n{YELLOW}⚡ Fail-Fast: Pipeline dihentikan segera pada Stage 2.{RESET}")
        runner.run_stage_reporting()
        return

    if not runner.run_stage_unit_tests(inject_failure=test_err):
        print(f"\n{YELLOW}⚡ Fail-Fast: Pipeline dihentikan segera pada Stage 3.{RESET}")
        runner.run_stage_reporting()
        return

    if not runner.run_stage_sast_security(inject_failure=sec_err):
        print(f"\n{YELLOW}⚡ Fail-Fast: Pipeline dihentikan segera pada Stage 4.{RESET}")
        runner.run_stage_reporting()
        return

    runner.run_stage_build_artifact()
    runner.run_stage_reporting()


def main_interactive_menu():
    while True:
        print_banner()
        print(f"{BOLD}Pilih skenario simulasi CI Automation:{RESET}")
        print(" [1] Happy Path Pipeline (Semua Stage Lolos / Clean Build)")
        print(" [2] Quality Gate Failure: Linter & Formatting Error (PEP8)")
        print(" [3] Test Failure: Broken Logic pada Unit Testing (pytest)")
        print(" [4] Security Gate Failure: Critical Vulnerability (CVE SAST)")
        print(" [5] Simulasi Otomatis (Demo Semua Kasus Berturut-turut)")
        print(" [0] Keluar")
        print()

        try:
            choice = input(f"{YELLOW}Masukkan pilihan [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nProgram dihentikan pengguna.")
            sys.exit(0)

        if choice == "1":
            run_pipeline_scenario("Happy Path (All Stages Pass)")
        elif choice == "2":
            run_pipeline_scenario("Linting & Code Style Failure", lint_err=True)
        elif choice == "3":
            run_pipeline_scenario("Unit Test Failure", test_err=True)
        elif choice == "4":
            run_pipeline_scenario("Security Vulnerability Gate Failure", sec_err=True)
        elif choice == "5":
            print("\nMenjalankan demo komprehensif...")
            run_pipeline_scenario("1. Clean Pipeline", lint_err=False)
            time.sleep(1.0)
            run_pipeline_scenario("2. Broken Test Case", test_err=True)
            time.sleep(1.0)
            run_pipeline_scenario("3. Security Vulnerability", sec_err=True)
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah mempelajari fondasi CI Automation!{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")

        input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu utama...{RESET}")


if __name__ == "__main__":
    main_interactive_menu()
