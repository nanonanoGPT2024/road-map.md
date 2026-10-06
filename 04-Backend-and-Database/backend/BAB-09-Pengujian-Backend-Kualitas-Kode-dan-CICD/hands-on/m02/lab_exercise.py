#!/usr/bin/env python3
"""
Hands-on Lab: BAB-09 Pengujian Backend, Kualitas Kode, dan CI/CD Pipeline
Arsitektur Simulasi Produksi: Multi-Stage Quality Gate & Automated Pipeline Engine
"""

from __future__ import annotations
import sys
import time
import random
import dataclasses
from enum import Enum
from typing import List, Dict, Tuple, Optional, Callable


# ==========================================
# 1. ANSI Color & Formatting Constants
# ==========================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"


def print_banner(text: str, color: str = Style.CYAN):
    border = "=" * 70
    print(f"\n{color}{Style.BOLD}{border}")
    print(f"  {text}")
    print(f"{border}{Style.RESET}")


def print_status(stage: str, status: str, duration_sec: float, ok: bool):
    badge = f"{Style.GREEN}[ PASS ]{Style.RESET}" if ok else f"{Style.RED}[ FAIL ]{Style.RESET}"
    time_str = f"{Style.DIM}({duration_sec:.2f}s){Style.RESET}"
    print(f" {badge} {Style.BOLD}{stage:<32}{Style.RESET} {status:<26} {time_str}")


# ==========================================
# 2. Domain Models & Pipeline Contracts
# ==========================================
class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclasses.dataclass
class QualityGateConfig:
    min_unit_test_coverage: float = 85.0
    max_lint_issues: int = 0
    max_security_vulnerabilities_high: int = 0
    max_p99_latency_ms: float = 120.0
    allow_canary_auto_rollback: bool = True


@dataclasses.dataclass
class TestCaseResult:
    name: str
    suite: str
    passed: bool
    duration_ms: float
    error_message: Optional[str] = None


@dataclasses.dataclass
class PipelineReport:
    commit_sha: str
    branch: str
    author: str
    stages_executed: int = 0
    stages_passed: int = 0
    total_duration_sec: float = 0.0
    coverage_score: float = 0.0
    critical_errors: List[str] = dataclasses.field(default_factory=list)


# ==========================================
# 3. Production Quality & Testing Engines
# ==========================================
class StaticAnalysisEngine:
    """Simulates Ruff/Flake8, Mypy Type Checker, and Bandit Security Scanner."""

    @staticmethod
    def run_linter() -> Tuple[bool, int, str]:
        time.sleep(0.4)
        issues = 0
        return True, issues, f"0 violations detected across 48 modules"

    @staticmethod
    def run_type_checker() -> Tuple[bool, int, str]:
        time.sleep(0.5)
        type_errors = 0
        return True, type_errors, f"Strict type check passed (mypy: 0 errors)"

    @staticmethod
    def run_security_scan(simulate_failure: bool = False) -> Tuple[bool, int, str]:
        time.sleep(0.6)
        if simulate_failure:
            return False, 1, "CWE-89: Potential SQL Injection detected in repository"
        return True, 0, "Bandit SAST: No high/critical severity flaws found"


class TestExecutionEngine:
    """Simulates Unit, Integration (Database/Redis Mock), and Contract Tests."""

    @staticmethod
    def run_unit_tests(simulate_failure: bool = False) -> Tuple[bool, List[TestCaseResult], float]:
        tests = [
            TestCaseResult("test_auth_jwt_token_validation", "AuthService", True, 14.2),
            TestCaseResult("test_password_hash_argon2id", "AuthService", True, 45.1),
            TestCaseResult("test_order_total_calculation_with_tax", "OrderService", True, 18.0),
            TestCaseResult("test_idempotency_key_duplicate_reject", "PaymentService", not simulate_failure, 22.5,
                           "Duplicate idempotency request accepted erroneously" if simulate_failure else None),
            TestCaseResult("test_rate_limiter_token_bucket", "Gateway", True, 11.8),
        ]
        time.sleep(0.8)
        passed = all(t.passed for t in tests)
        coverage = 89.4 if not simulate_failure else 81.2
        return passed, tests, coverage

    @staticmethod
    def run_integration_tests() -> Tuple[bool, List[TestCaseResult]]:
        time.sleep(1.0)
        tests = [
            TestCaseResult("test_db_transaction_rollback_on_error", "IntegrationDB", True, 120.4),
            TestCaseResult("test_redis_distributed_lock_ttl", "IntegrationCache", True, 88.2),
            TestCaseResult("test_kafka_event_publishing_order_created", "IntegrationEvent", True, 145.0),
        ]
        passed = all(t.passed for t in tests)
        return passed, tests


class DeploymentEngine:
    """Simulates Canary Deployment and Smoke Verification."""

    @staticmethod
    def deploy_canary(target_traffic_pct: int = 10) -> Tuple[bool, str]:
        time.sleep(0.7)
        return True, f"Canary deployed ({target_traffic_pct}% traffic routed to v2.4.0-prod)"

    @staticmethod
    def run_canary_health_check(simulate_anomaly: bool = False) -> Tuple[bool, float, str]:
        time.sleep(0.8)
        p99 = 48.5 if not simulate_anomaly else 240.2
        if simulate_anomaly:
            return False, p99, f"P99 latency degraded to {p99}ms (threshold <= 120ms)"
        return True, p99, f"P99 latency stable at {p99}ms, 5xx error rate = 0.00%"

    @staticmethod
    def promote_to_full_production() -> Tuple[bool, str]:
        time.sleep(0.6)
        return True, "100% traffic promoted to Production Cluster (Blue/Green switch)"

    @staticmethod
    def trigger_auto_rollback() -> str:
        time.sleep(0.5)
        return "Automatic rollback initiated: Traffic restored to stable release v2.3.9"


# ==========================================
# 4. CI/CD Orchestrator Engine
# ==========================================
class CICDPipelineOrchestrator:
    def __init__(self, config: QualityGateConfig):
        self.config = config

    def execute_pipeline(self, commit_sha: str, branch: str, author: str, chaos_mode: bool = False) -> PipelineReport:
        report = PipelineReport(commit_sha=commit_sha, branch=branch, author=author)
        start_time = time.time()

        print_banner(f"CI/CD PIPELINE RUNNER - REF: {branch} [{commit_sha}]", Style.MAGENTA)
        print(f" {Style.DIM}Triggered by: {author} | Quality Gate: Strict Mode{Style.RESET}\n")

        # Stage 1: Lint & Formatting
        t0 = time.time()
        l_ok, l_cnt, l_msg = StaticAnalysisEngine.run_linter()
        report.stages_executed += 1
        if l_ok and l_cnt <= self.config.max_lint_issues:
            report.stages_passed += 1
            print_status("1. Static Code Analysis (Ruff)", l_msg, time.time() - t0, True)
        else:
            report.critical_errors.append(f"Linting failed: {l_msg}")
            print_status("1. Static Code Analysis (Ruff)", l_msg, time.time() - t0, False)
            return self._finalize_report(report, start_time)

        # Stage 2: Strict Typing
        t0 = time.time()
        t_ok, t_cnt, t_msg = StaticAnalysisEngine.run_type_checker()
        report.stages_executed += 1
        if t_ok:
            report.stages_passed += 1
            print_status("2. Static Type Checking (Mypy)", t_msg, time.time() - t0, True)
        else:
            report.critical_errors.append(f"Type check failed: {t_msg}")
            print_status("2. Static Type Checking (Mypy)", t_msg, time.time() - t0, False)
            return self._finalize_report(report, start_time)

        # Stage 3: SAST Security Audit
        t0 = time.time()
        s_ok, s_cnt, s_msg = StaticAnalysisEngine.run_security_scan(simulate_failure=(chaos_mode and random.choice([True, False])))
        report.stages_executed += 1
        if s_ok:
            report.stages_passed += 1
            print_status("3. Security Audit (SAST/Bandit)", s_msg, time.time() - t0, True)
        else:
            report.critical_errors.append(f"Security vulnerability detected: {s_msg}")
            print_status("3. Security Audit (SAST/Bandit)", s_msg, time.time() - t0, False)
            return self._finalize_report(report, start_time)

        # Stage 4: Unit Testing & Coverage Gate
        t0 = time.time()
        u_ok, u_results, coverage = TestExecutionEngine.run_unit_tests(simulate_failure=chaos_mode)
        report.stages_executed += 1
        report.coverage_score = coverage
        if u_ok and coverage >= self.config.min_unit_test_coverage:
            report.stages_passed += 1
            msg = f"{len(u_results)} passed (Coverage: {coverage:.1f}% >= {self.config.min_unit_test_coverage}%)"
            print_status("4. Unit Tests & Coverage Gate", msg, time.time() - t0, True)
        else:
            failed_test = next((t.name for t in u_results if not t.passed), "Coverage below threshold")
            err_msg = f"Failed on {failed_test} (Coverage: {coverage:.1f}%)"
            report.critical_errors.append(err_msg)
            print_status("4. Unit Tests & Coverage Gate", err_msg, time.time() - t0, False)
            return self._finalize_report(report, start_time)

        # Stage 5: Integration Testing
        t0 = time.time()
        i_ok, i_results = TestExecutionEngine.run_integration_tests()
        report.stages_executed += 1
        if i_ok:
            report.stages_passed += 1
            print_status("5. Integration Tests (DB/Redis)", f"{len(i_results)} passed against testcontainers", time.time() - t0, True)
        else:
            report.critical_errors.append("Integration test assertions failed")
            print_status("5. Integration Tests (DB/Redis)", "Failure during end-to-end handshake", time.time() - t0, False)
            return self._finalize_report(report, start_time)

        # Stage 6: Canary Deployment & Health Check
        t0 = time.time()
        d_ok, d_msg = DeploymentEngine.deploy_canary(target_traffic_pct=10)
        report.stages_executed += 1
        report.stages_passed += 1
        print_status("6. Canary Deployment", d_msg, time.time() - t0, True)

        # Stage 7: Production Telemetry & Canary Gate
        t0 = time.time()
        h_ok, p99, h_msg = DeploymentEngine.run_canary_health_check(simulate_anomaly=chaos_mode)
        report.stages_executed += 1
        if h_ok:
            report.stages_passed += 1
            print_status("7. Canary Health Verification", h_msg, time.time() - t0, True)
        else:
            report.critical_errors.append(f"Canary SLO violated: {h_msg}")
            print_status("7. Canary Health Verification", h_msg, time.time() - t0, False)
            if self.config.allow_canary_auto_rollback:
                rb_msg = DeploymentEngine.trigger_auto_rollback()
                print(f" {Style.YELLOW}[ ROLLBACK ] {Style.BOLD}{rb_msg}{Style.RESET}")
            return self._finalize_report(report, start_time)

        # Stage 8: Production Promotion
        t0 = time.time()
        p_ok, p_msg = DeploymentEngine.promote_to_full_production()
        report.stages_executed += 1
        report.stages_passed += 1
        print_status("8. Promotion to 100% Traffic", p_msg, time.time() - t0, True)

        return self._finalize_report(report, start_time)

    def _finalize_report(self, report: PipelineReport, start_time: float) -> PipelineReport:
        report.total_duration_sec = time.time() - start_time
        success = len(report.critical_errors) == 0 and report.stages_passed == report.stages_executed

        print("\n" + "-" * 70)
        if success:
            print(f"{Style.BG_GREEN}{Style.WHITE}{Style.BOLD}  PIPELINE STATUS: SUCCEEDED (READY FOR ZERO-DOWNTIME SERVING)  {Style.RESET}")
        else:
            print(f"{Style.BG_RED}{Style.WHITE}{Style.BOLD}  PIPELINE STATUS: BLOCKED BY QUALITY GATE (BUILD FAILED)        {Style.RESET}")

        print(f" Stages Passed    : {report.stages_passed}/{report.stages_executed}")
        print(f" Total Duration   : {report.total_duration_sec:.2f} seconds")
        print(f" Test Coverage    : {report.coverage_score:.1f}%")

        if report.critical_errors:
            print(f"\n{Style.RED}{Style.BOLD}Root Causes:{Style.RESET}")
            for err in report.critical_errors:
                print(f"  {Style.RED}• {err}{Style.RESET}")
        print("-" * 70)
        return report


# ==========================================
# 5. Interactive CLI Simulation Driver
# ==========================================
def interactive_menu():
    config = QualityGateConfig()
    orchestrator = CICDPipelineOrchestrator(config)

    while True:
        print_banner("BAB-09: SISTEM PENGUJIAN BACKEND, KUALITAS KODE & CI/CD", Style.BLUE)
        print(f"{Style.BOLD}Pilih skenario simulasi arsitektur produksi:{Style.RESET}")
        print(" [1] Jalankan Pipeline Normal (Happy Path: All Quality Gates Pass)")
        print(" [2] Jalankan Pipeline dengan Chaos Injection (Simulasi Kegagalan & Rollback)")
        print(" [3] Inspeksi Konfigurasi Quality Gate SLO/SLA")
        print(" [4] Ubah Threshold Cakupan Kode (Coverage Gate)")
        print(" [5] Keluar dari Lab")
        print("-" * 70)

        choice = input(f"{Style.CYAN}Masukkan pilihan (1-5): {Style.RESET}").strip()

        if choice == "1":
            orchestrator.execute_pipeline(
                commit_sha="a7f4c91",
                branch="main",
                author="backend-eng@corp.internal",
                chaos_mode=False
            )
            input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu...{Style.RESET}")

        elif choice == "2":
            print(f"\n{Style.YELLOW}{Style.BOLD}[CHAOS MODE ACTIVE] Menyuntikkan kegagalan regresi acak...{Style.RESET}")
            orchestrator.execute_pipeline(
                commit_sha="b81e302",
                branch="feature/payment-v2",
                author="junior-dev@corp.internal",
                chaos_mode=True
            )
            input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu...{Style.RESET}")

        elif choice == "3":
            print(f"\n{Style.BOLD}--- KONFIGURASI QUALITY GATE PRODUKSI ---{Style.RESET}")
            print(f" • Min Unit Test Coverage      : {config.min_unit_test_coverage}%")
            print(f" • Max Tolerable Lint Issues   : {config.max_lint_issues}")
            print(f" • Max High Vulnerabilities    : {config.max_security_vulnerabilities_high}")
            print(f" • Max P99 Latency Threshold   : {config.max_p99_latency_ms} ms")
            print(f" • Auto-Rollback Enabled       : {config.allow_canary_auto_rollback}")
            input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu...{Style.RESET}")

        elif choice == "4":
            try:
                val = float(input(f"{Style.CYAN}Masukkan target minimum coverage (misal 90.0): {Style.RESET}").strip())
                if 0.0 <= val <= 100.0:
                    config.min_unit_test_coverage = val
                    print(f"{Style.GREEN}Target coverage diperbarui ke {val}%!{Style.RESET}")
                else:
                    print(f"{Style.RED}Nilai harus antara 0 dan 100.{Style.RESET}")
            except ValueError:
                print(f"{Style.RED}Format angka tidak valid.{Style.RESET}")
            time.sleep(1.2)

        elif choice == "5":
            print(f"\n{Style.GREEN}Terima kasih! Lab CI/CD selesai.{Style.RESET}\n")
            sys.exit(0)

        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan coba lagi.{Style.RESET}")
            time.sleep(1.0)


if __name__ == "__main__":
    try:
        # Non-interactive fallback when stdin is closed or piped
        if not sys.stdin.isatty():
            cfg = QualityGateConfig()
            app = CICDPipelineOrchestrator(cfg)
            app.execute_pipeline("c0ffee9", "release/v2.4.0", "ci-bot", chaos_mode=False)
        else:
            interactive_menu()
    except KeyboardInterrupt:
        print(f"\n\n{Style.YELLOW}Sesi dibatalkan oleh user. Keluar...{Style.RESET}")
        sys.exit(0)
