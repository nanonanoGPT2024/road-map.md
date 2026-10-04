#!/usr/bin/env python3
"""
Lab Exercise M01: GitHub Actions CI/CD & Automation Workflow Simulator
BAB-08: GitHub Actions CI/CD dan Automation
Panduan Interaktif Simulasi Lifecycle Runner, Triggers, Jobs Matrix, dan Status Checks
"""

import sys
import time
import random
from typing import Dict, List, Optional
from dataclasses import dataclass, field

# --- ANSI Terminal Color Palette ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Foreground Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # High-intensity Foreground
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background Colors
    BG_DARK = "\033[48;5;236m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_BLUE = "\033[44m"


@dataclass
class Step:
    id: str
    name: str
    command_or_action: str
    is_action: bool = False
    env: Dict[str, str] = field(default_factory=dict)
    status: str = "QUEUED"  # QUEUED, RUNNING, SUCCESS, FAILED, SKIPPED
    duration: float = 0.0
    output_log: List[str] = field(default_factory=list)


@dataclass
class Job:
    id: str
    name: str
    runs_on: str
    needs: List[str] = field(default_factory=list)
    steps: List[Step] = field(default_factory=list)
    matrix_var: Optional[str] = None
    status: str = "QUEUED"  # QUEUED, IN_PROGRESS, SUCCESS, FAILED, SKIPPED
    duration: float = 0.0


class WorkflowSimulator:
    def __init__(self, name: str, event_trigger: str, branch: str):
        self.name = name
        self.event_trigger = event_trigger
        self.branch = branch
        self.jobs: Dict[str, Job] = {}
        self.secrets = {"GITHUB_TOKEN": "ghp_simulated***token", "DOCKER_PASSWORD": "••••••••••••"}
        self.setup_default_workflow()

    def setup_default_workflow(self):
        """Membangun representasi pipeline GitHub Actions standar CI/CD"""
        # Job 1: Linting & Code Style
        lint_steps = [
            Step("checkout", "Checkout repository code", "actions/checkout@v4", is_action=True),
            Step("setup-python", "Setup Python runtime", "actions/setup-python@v5 (v=3.11)", is_action=True),
            Step("cache-pip", "Restore Pip cache", "actions/cache@v4", is_action=True),
            Step("run-linter", "Run Ruff and Flake8 linter", "ruff check . && flake8 src/ tests/"),
            Step("run-typing", "Check Type Safety", "mypy --strict src/")
        ]
        self.jobs["lint"] = Job("lint", "Code Quality & Static Analysis", "ubuntu-latest", [], lint_steps)

        # Job 2: Unit and Integration Testing (Simulasi Matrix Strategy)
        test_steps = [
            Step("checkout", "Checkout repository code", "actions/checkout@v4", is_action=True),
            Step("setup-python", "Setup Python runtime", "actions/setup-python@v5 (matrix)", is_action=True),
            Step("install-deps", "Install dependencies", "pip install -r requirements.txt pytest pytest-cov"),
            Step("run-pytest", "Execute Pytest with Coverage", "pytest --cov=src tests/ --cov-report=xml"),
            Step("upload-artifact", "Upload Test Report Artifact", "actions/upload-artifact@v4 (path=coverage.xml)", is_action=True)
        ]
        self.jobs["test"] = Job("test", "Unit & Integration Tests", "ubuntu-latest", ["lint"], test_steps, matrix_var="python: [3.10, 3.11, 3.12]")

        # Job 3: Security & Secret Audit
        sec_steps = [
            Step("checkout", "Checkout repository code", "actions/checkout@v4", is_action=True),
            Step("run-trivy", "Scan Vulnerabilities", "aquasecurity/trivy-action@master", is_action=True),
            Step("run-gitleaks", "Audit Hardcoded Secrets", "gitleaks detect --verbose")
        ]
        self.jobs["security"] = Job("security", "Security & Supply Chain Audit", "ubuntu-latest", ["lint"], sec_steps)

        # Job 4: Build & Containerize
        build_steps = [
            Step("checkout", "Checkout repository code", "actions/checkout@v4", is_action=True),
            Step("setup-buildx", "Set up Docker Buildx", "docker/setup-buildx-action@v3", is_action=True),
            Step("login-ghcr", "Log in to GitHub Container Registry", "docker/login-action@v3 (registry=ghcr.io)", is_action=True),
            Step("build-push", "Build & Push Docker Image", "docker/build-push-action@v5 --tag ghcr.io/org/app:sha")
        ]
        self.jobs["build"] = Job("build", "Docker Build & Containerize", "ubuntu-latest", ["test", "security"], build_steps)

        # Job 5: Deploy to Staging / Production
        deploy_steps = [
            Step("checkout", "Checkout repository code", "actions/checkout@v4", is_action=True),
            Step("verify-env", "Verify Target Environment", "echo 'Deploying to environment: staging'"),
            Step("deploy-k8s", "Apply Kubernetes Manifests", "kubectl apply -k k8s/overlays/staging/"),
            Step("smoke-test", "Run Post-deployment Smoke Tests", "curl -sf https://staging.internal.net/healthz")
        ]
        self.jobs["deploy"] = Job("deploy", "Automated Staging Deployment", "ubuntu-latest", ["build"], deploy_steps)

    def print_workflow_spec(self):
        """Menampilkan deklarasi YAML representasi pipeline"""
        print(f"\n{Style.BRIGHT_MAGENTA}=== DEKLARASI GITHUB ACTIONS WORKFLOW YAML (.github/workflows/ci.yml) ==={Style.RESET}")
        spec_yaml = f"""{Style.CYAN}name:{Style.RESET} {self.name}
{Style.CYAN}on:{Style.RESET}
  {Style.CYAN}{self.event_trigger}:{Style.RESET}
    {Style.CYAN}branches:{Style.RESET} [ {self.branch} ]

{Style.CYAN}concurrency:{Style.RESET}
  {Style.CYAN}group:{Style.RESET} {{{{ github.workflow }}}}-{{{{ github.ref }}}}
  {Style.CYAN}cancel-in-progress:{Style.RESET} true

{Style.CYAN}jobs:{Style.RESET}"""
        print(spec_yaml)
        for job_id, job in self.jobs.items():
            needs_str = f" [ {', '.join(job.needs)} ]" if job.needs else " []"
            matrix_str = f"\n    {Style.CYAN}strategy:{Style.RESET}\n      {Style.CYAN}matrix:{Style.RESET} {job.matrix_var}" if job.matrix_var else ""
            print(f"  {Style.YELLOW}{job_id}:{Style.RESET}")
            print(f"    {Style.CYAN}name:{Style.RESET} {job.name}")
            print(f"    {Style.CYAN}runs-on:{Style.RESET} {job.runs_on}")
            print(f"    {Style.CYAN}needs:{Style.RESET}{needs_str}{matrix_str}")
            print(f"    {Style.CYAN}steps:{Style.RESET}")
            for step in job.steps:
                key = "uses" if step.is_action else "run"
                print(f"      - {Style.CYAN}name:{Style.RESET} {step.name}")
                print(f"        {Style.CYAN}{key}:{Style.RESET} {step.command_or_action}")
        print("-" * 75)

    def run_step(self, step: Step, fail_simulated: bool = False) -> bool:
        """Menjalankan step runner secara realistis dengan live log feedback"""
        step.status = "RUNNING"
        prefix = f"{Style.BRIGHT_BLUE}⚙️  [STEP]{Style.RESET} {step.name}"
        sys.stdout.write(f"\r  {prefix:<55} {Style.YELLOW}[RUNNING...]{Style.RESET}")
        sys.stdout.flush()

        time.sleep(0.35)
        step.duration = round(random.uniform(0.4, 1.8), 2)

        if fail_simulated:
            step.status = "FAILED"
            step.output_log.append(f"Error: Command '{step.command_or_action}' exited with code 1.")
            step.output_log.append("AssertionError: Test item 14 expected HTTP 200, got HTTP 500.")
            sys.stdout.write(f"\r  {prefix:<55} {Style.BRIGHT_RED}[FAILED ✖] ({step.duration}s){Style.RESET}\n")
            for log in step.output_log:
                print(f"      {Style.RED}│ ↳ {log}{Style.RESET}")
            return False
        else:
            step.status = "SUCCESS"
            step.output_log.append(f"Exit code 0: {step.command_or_action} completed.")
            sys.stdout.write(f"\r  {prefix:<55} {Style.BRIGHT_GREEN}[SUCCESS ✔] ({step.duration}s){Style.RESET}\n")
            return True

    def execute_pipeline(self, fail_target_job: Optional[str] = None):
        """Menjalankan dependency graph pipeline CI/CD dengan deteksi kegagalan bertingkat"""
        print(f"\n{Style.BG_BLUE}{Style.BOLD} 🚀 GITHUB ACTIONS RUNNER DISPATCHED {Style.RESET}")
        print(f"{Style.DIM}Event: {self.event_trigger} | Ref: refs/heads/{self.branch} | SHA: a1b2c3d | Actor: dev-lead{Style.RESET}\n")

        overall_start = time.time()
        executed_jobs: Dict[str, str] = {}

        # Urutan eksekusi terstruktur berdasarkan dependency (DAG)
        execution_order = ["lint", "test", "security", "build", "deploy"]

        for j_id in execution_order:
            job = self.jobs[j_id]
            print(f"{Style.BOLD}{Style.BRIGHT_WHITE}▶ Job: {job.name} ({j_id}){Style.RESET}")
            print(f"  {Style.DIM}Virtual Machine OS: {job.runs_on} | Matrix: {job.matrix_var or 'None'}{Style.RESET}")

            # Periksa dependency prerequisites
            dependency_failed = False
            for dep in job.needs:
                if executed_jobs.get(dep) != "SUCCESS":
                    dependency_failed = True
                    break

            if dependency_failed:
                job.status = "SKIPPED"
                print(f"  {Style.DIM}Status: SKIPPED (Syarat dependensi: {', '.join(job.needs)} tidak terpenuhi){Style.RESET}\n")
                executed_jobs[j_id] = "SKIPPED"
                continue

            job.status = "IN_PROGRESS"
            job_start = time.time()
            job_failed = False

            for idx, step in enumerate(job.steps):
                should_fail = (fail_target_job == j_id and idx == len(job.steps) - 2)
                success = self.run_step(step, fail_simulated=should_fail)
                if not success:
                    job_failed = True
                    # Skip sisa steps
                    for remaining_step in job.steps[idx + 1:]:
                        remaining_step.status = "SKIPPED"
                        print(f"  {Style.DIM}⚙️  [STEP] {remaining_step.name:<45} [SKIPPED]{Style.RESET}")
                    break

            job.duration = round(time.time() - job_start, 2)
            if job_failed:
                job.status = "FAILED"
                executed_jobs[j_id] = "FAILED"
                print(f"  {Style.BRIGHT_RED}Result Job {j_id}: FAILED (Durasi: {job.duration}s){Style.RESET}\n")
            else:
                job.status = "SUCCESS"
                executed_jobs[j_id] = "SUCCESS"
                print(f"  {Style.BRIGHT_GREEN}Result Job {j_id}: COMPLETED (Durasi: {job.duration}s){Style.RESET}\n")

        total_time = round(time.time() - overall_start, 2)
        self.render_summary(executed_jobs, total_time)

    def render_summary(self, results: Dict[str, str], duration: float):
        """Menampilkan matrix summary dan GitHub Check Status Badge"""
        all_passed = all(status == "SUCCESS" for status in results.values())
        header_color = Style.BG_GREEN if all_passed else Style.BG_RED

        print(f"{header_color}{Style.BOLD} 📋 RUN SUMMARY & CHECK SUITE STATUS 📋 {Style.RESET}")
        print(f"Total Workflow Execution Time: {duration}s\n")
        print(f"{'Job Identifier':<18} | {'Job Name':<34} | {'Status':<12} | {'Time (s)':<8}")
        print("-" * 80)

        for j_id, job in self.jobs.items():
            st = job.status
            color = Style.BRIGHT_GREEN if st == "SUCCESS" else (Style.BRIGHT_RED if st == "FAILED" else Style.DIM)
            badge = "✔ PASS" if st == "SUCCESS" else ("✖ FAIL" if st == "FAILED" else "⊘ SKIP")
            print(f"{job.id:<18} | {job.name:<34} | {color}{badge:<12}{Style.RESET} | {job.duration:<8.2f}")

        print("-" * 80)
        if all_passed:
            print(f"{Style.BRIGHT_GREEN}{Style.BOLD}STATUS CHECKS: All checks have passed! PR can be safely merged.{Style.RESET}\n")
        else:
            print(f"{Style.BRIGHT_RED}{Style.BOLD}STATUS CHECKS: Some checks were not successful. Merging is BLOCKED by branch protection rules.{Style.RESET}\n")


def display_interactive_menu():
    """Menu Navigasi CLI Interaktif untuk Eksplorasi CI/CD"""
    sim = WorkflowSimulator(name="Production Deployment & CI Pipeline", event_trigger="push", branch="main")

    while True:
        print(f"{Style.BRIGHT_CYAN}{Style.BOLD}===================================================================={Style.RESET}")
        print(f"{Style.BRIGHT_YELLOW}{Style.BOLD} ⚙️  INTERACTIVE LAB: GITHUB ACTIONS CI/CD ENGINE & AUTOMATION {Style.RESET}")
        print(f"{Style.BRIGHT_CYAN}===================================================================={Style.RESET}")
        print(f"{Style.WHITE}1. Lihat Skema Workflow YAML (.github/workflows/ci.yml){Style.RESET}")
        print(f"{Style.WHITE}2. Jalankan Pipeline Normal (Full Success Run - push event){Style.RESET}")
        print(f"{Style.WHITE}3. Simulasi Pipeline Gagal pada Tahap Test (Pull Request Blocked){Style.RESET}")
        print(f"{Style.WHITE}4. Simulasi Pipeline Gagal pada Tahap Security Audit{Style.RESET}")
        print(f"{Style.WHITE}5. Konfigurasi Event Trigger Baru (pull_request / workflow_dispatch){Style.RESET}")
        print(f"{Style.WHITE}6. Keluar dari Lab{Style.RESET}")
        print("-" * 68)

        choice = input(f"{Style.BOLD}Pilih opsi latihan (1-6): {Style.RESET}").strip()

        if choice == "1":
            sim.print_workflow_spec()
        elif choice == "2":
            sim.setup_default_workflow()
            sim.execute_pipeline(fail_target_job=None)
        elif choice == "3":
            sim.setup_default_workflow()
            print(f"\n{Style.YELLOW}⚠️  Simulasi: Pengujian unit test mendeteksi regresi kode.{Style.RESET}")
            sim.execute_pipeline(fail_target_job="test")
        elif choice == "4":
            sim.setup_default_workflow()
            print(f"\n{Style.YELLOW}⚠️  Simulasi: Scanner menemukan vulnerability CVE kritis pada dependensi.{Style.RESET}")
            sim.execute_pipeline(fail_target_job="security")
        elif choice == "5":
            print(f"\nPilih event trigger GitHub:")
            print("1. push")
            print("2. pull_request")
            print("3. workflow_dispatch (Manual trigger via GitHub UI/CLI)")
            print("4. schedule (Cron Automation)")
            ev_opt = input("Pilih (1-4): ").strip()
            events = {"1": "push", "2": "pull_request", "3": "workflow_dispatch", "4": "schedule"}
            sim.event_trigger = events.get(ev_opt, "push")
            branch_in = input("Target branch (default: main): ").strip()
            if branch_in:
                sim.branch = branch_in
            print(f"{Style.BRIGHT_GREEN}✓ Trigger diperbarui ke '{sim.event_trigger}' pada branch '{sim.branch}'!{Style.RESET}\n")
        elif choice == "6":
            print(f"\n{Style.BRIGHT_CYAN}Terima kasih telah menyelesaikan modul latihan hands-on GitHub Actions CI/CD!{Style.RESET}\n")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid, silakan coba lagi.{Style.RESET}\n")


if __name__ == "__main__":
    try:
        # Jika dijalankan secara non-interaktif (contoh: di test pipe atau CI)
        if not sys.stdin.isatty():
            quick_sim = WorkflowSimulator("CI Non-Interactive Pipeline", "push", "main")
            quick_sim.print_workflow_spec()
            quick_sim.execute_pipeline(fail_target_job=None)
        else:
            display_interactive_menu()
    except KeyboardInterrupt:
        print(f"\n{Style.YELLOW}Sesi lab dihentikan oleh pengguna.{Style.RESET}")
        sys.exit(0)
