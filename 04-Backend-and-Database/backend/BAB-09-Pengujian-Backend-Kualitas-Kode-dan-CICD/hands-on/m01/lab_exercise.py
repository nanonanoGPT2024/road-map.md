#!/usr/bin/env python3
"""
Hands-on Lab Exercise: M01 - Pengujian Backend, Kualitas Kode, dan CI/CD
BAB-09: Pengujian Backend, Kualitas Kode, dan CI/CD

Simulasi interaktif teknis arsitektur pengujian piranti lunak backend:
1. Unit Testing Engine & Test Doubles (Mocks, Stubs)
2. Integration Testing Simulation dengan In-Memory State
3. Linter & Static Code Analysis Rules Evaluator
4. Deterministic Automated CI/CD Pipeline Stage Runner
"""

import sys
import time
import math
from typing import Callable, List, Dict, Any, Optional

# ==============================================================================
# ANSI Terminal Color Configuration
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{Color.CYAN}{Color.BOLD}{'=' * 68}{Color.RESET}")
    print(f"{Color.WHITE}{Color.BOLD}>>> {title.upper()}{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}{'=' * 68}{Color.RESET}")


def subheader(text: str) -> None:
    print(f"\n{Color.MAGENTA}{Color.BOLD}[*] {text}{Color.RESET}")


# ==============================================================================
# 1. Domain Entities & Service Layer (System Under Test)
# ==============================================================================
class User:
    def __init__(self, user_id: int, email: str, role: str, is_active: bool = True):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.is_active = is_active


class UserRepositoryInterface:
    def find_by_id(self, user_id: int) -> Optional[User]:
        raise NotImplementedError

    def save(self, user: User) -> bool:
        raise NotImplementedError


class PaymentGatewayInterface:
    def charge(self, user_id: int, amount: float) -> bool:
        raise NotImplementedError


class OrderService:
    """Service backend yang diuji (System Under Test / SUT)."""

    def __init__(self, user_repo: UserRepositoryInterface, payment_gw: PaymentGatewayInterface):
        self.user_repo = user_repo
        self.payment_gw = payment_gw

    def process_order(self, user_id: int, amount: float) -> Dict[str, Any]:
        if amount <= 0:
            return {"status": "FAILED", "code": 400, "message": "Amount must be strictly positive"}

        user = self.user_repo.find_by_id(user_id)
        if not user:
            return {"status": "FAILED", "code": 404, "message": "User not found"}

        if not user.is_active:
            return {"status": "FAILED", "code": 403, "message": "User account is suspended"}

        success = self.payment_gw.charge(user_id, amount)
        if not success:
            return {"status": "FAILED", "code": 502, "message": "Payment gateway rejected transaction"}

        return {
            "status": "SUCCESS",
            "code": 200,
            "order_id": f"ORD-{user_id}-{int(time.time())}",
            "amount": amount,
            "user_email": user.email,
        }


# ==============================================================================
# 2. Mocking & Test Double Framework
# ==============================================================================
class MockUserRepository(UserRepositoryInterface):
    def __init__(self):
        self._store: Dict[int, User] = {}
        self.call_count_find = 0

    def seed_user(self, user: User) -> None:
        self._store[user.user_id] = user

    def find_by_id(self, user_id: int) -> Optional[User]:
        self.call_count_find += 1
        return self._store.get(user_id)

    def save(self, user: User) -> bool:
        self._store[user.user_id] = user
        return True


class MockPaymentGateway(PaymentGatewayInterface):
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.last_charge_amount: Optional[float] = None
        self.charges_recorded: List[Dict[str, Any]] = []

    def charge(self, user_id: int, amount: float) -> bool:
        self.last_charge_amount = amount
        self.charges_recorded.append({"user_id": user_id, "amount": amount})
        return self.should_succeed


# ==============================================================================
# 3. Unit Test Suite & Assertion Engine
# ==============================================================================
class TestSuiteRunner:
    def __init__(self, suite_name: str):
        self.suite_name = suite_name
        self.tests: List[Dict[str, Any]] = []

    def register_test(self, name: str, fn: Callable[[], None]) -> None:
        self.tests.append({"name": name, "fn": fn})

    def run(self) -> bool:
        subheader(f"Running Test Suite: {self.suite_name}")
        passed = 0
        failed = 0
        start_time = time.perf_counter()

        for idx, item in enumerate(self.tests, 1):
            t_name = item["name"]
            t_fn = item["fn"]
            sys.stdout.write(f"  [{idx}/{len(self.tests)}] {t_name.ljust(50)} ")
            sys.stdout.flush()

            try:
                t_fn()
                passed += 1
                print(f"{Color.GREEN}{Color.BOLD}[PASS]{Color.RESET}")
            except AssertionError as err:
                failed += 1
                print(f"{Color.RED}{Color.BOLD}[FAIL]{Color.RESET}")
                print(f"      {Color.RED}^-- Assertion Failure: {err}{Color.RESET}")
            except Exception as ex:
                failed += 1
                print(f"{Color.RED}{Color.BOLD}[ERROR]{Color.RESET}")
                print(f"      {Color.RED}^-- Unexpected Exception: {ex}{Color.RESET}")

        duration = (time.perf_counter() - start_time) * 1000
        summary_color = Color.GREEN if failed == 0 else Color.RED
        print(f"\n  {summary_color}{Color.BOLD}Suite Summary: {passed} passed, {failed} failed in {duration:.2f}ms{Color.RESET}")
        return failed == 0


def build_unit_tests() -> TestSuiteRunner:
    runner = TestSuiteRunner("Unit Tests: OrderService Business Logic")

    def test_order_success_active_user():
        repo = MockUserRepository()
        repo.seed_user(User(user_id=101, email="alice@corp.id", role="member", is_active=True))
        pg = MockPaymentGateway(should_succeed=True)
        svc = OrderService(repo, pg)

        res = svc.process_order(101, 250000.0)
        assert res["status"] == "SUCCESS", f"Expected SUCCESS, got {res['status']}"
        assert res["code"] == 200, f"Expected 200, got {res['code']}"
        assert pg.last_charge_amount == 250000.0, "Payment gateway was not charged the correct amount"

    def test_order_fails_negative_amount():
        repo = MockUserRepository()
        pg = MockPaymentGateway(should_succeed=True)
        svc = OrderService(repo, pg)

        res = svc.process_order(101, -5000.0)
        assert res["status"] == "FAILED", f"Expected status FAILED, got {res['status']}"
        assert res["code"] == 400, f"Expected 400, got {res['code']}"

    def test_order_fails_user_not_found():
        repo = MockUserRepository()
        pg = MockPaymentGateway(should_succeed=True)
        svc = OrderService(repo, pg)

        res = svc.process_order(999, 100000.0)
        assert res["code"] == 404, f"Expected 404 for unknown user, got {res['code']}"
        assert len(pg.charges_recorded) == 0, "No charges should be sent to payment gateway"

    def test_order_fails_suspended_user():
        repo = MockUserRepository()
        repo.seed_user(User(user_id=102, email="banned@corp.id", role="member", is_active=False))
        pg = MockPaymentGateway(should_succeed=True)
        svc = OrderService(repo, pg)

        res = svc.process_order(102, 100000.0)
        assert res["code"] == 403, f"Expected 403 for suspended user, got {res['code']}"

    def test_order_fails_gateway_rejection():
        repo = MockUserRepository()
        repo.seed_user(User(user_id=103, email="bob@corp.id", role="member", is_active=True))
        pg = MockPaymentGateway(should_succeed=False)
        svc = OrderService(repo, pg)

        res = svc.process_order(103, 150000.0)
        assert res["code"] == 502, f"Expected 502 when gateway rejects, got {res['code']}"

    runner.register_test("Order success for valid active user", test_order_success_active_user)
    runner.register_test("Order validation: negative amount rejected", test_order_fails_negative_amount)
    runner.register_test("Order validation: 404 on missing customer", test_order_fails_user_not_found)
    runner.register_test("Order policy: 403 on suspended account", test_order_fails_suspended_user)
    runner.register_test("Resilience: 502 on third-party payment gateway error", test_order_fails_gateway_rejection)
    return runner


# ==============================================================================
# 4. Code Quality & Static Code Analyzer Simulation
# ==============================================================================
class StaticAnalysisRule:
    def __init__(self, rule_id: str, name: str, severity: str):
        self.rule_id = rule_id
        self.name = name
        self.severity = severity


class CodeQualityLinter:
    """Simulasi AST / Static Analysis Linter untuk Backend Code Quality."""

    def __init__(self):
        self.rules: List[StaticAnalysisRule] = [
            StaticAnalysisRule("SEC-01", "No Hardcoded Secrets/Tokens", "CRITICAL"),
            StaticAnalysisRule("TYP-02", "Type Hint Coverage >= 90%", "WARNING"),
            StaticAnalysisRule("CMP-03", "Cyclomatic Complexity <= 10 per method", "WARNING"),
            StaticAnalysisRule("SQL-04", "No Raw String Concatenation in SQL", "CRITICAL"),
            StaticAnalysisRule("FMT-05", "PEP-8 Naming Conventions Conformity", "INFO"),
        ]

    def audit_codebase(self, sample_manifest: Dict[str, Any]) -> bool:
        subheader("Static Analysis & Code Quality Gate Audit")
        has_critical = False

        print(f"  {Color.WHITE}{'RULE ID':<10} {'SEVERITY':<12} {'RULE NAME':<38} {'STATUS'}{Color.RESET}")
        print(f"  {'-' * 70}")

        for rule in self.rules:
            status = sample_manifest.get(rule.rule_id, "PASS")
            if status == "PASS":
                status_str = f"{Color.GREEN}[PASS]{Color.RESET}"
            elif rule.severity == "CRITICAL":
                status_str = f"{Color.RED}[VIOLATION]{Color.RESET}"
                has_critical = True
            else:
                status_str = f"{Color.YELLOW}[WARN]{Color.RESET}"

            sev_color = Color.RED if rule.severity == "CRITICAL" else (Color.YELLOW if rule.severity == "WARNING" else Color.CYAN)
            print(f"  {Color.BOLD}{rule.rule_id:<10}{Color.RESET} {sev_color}{rule.severity:<12}{Color.RESET} {rule.name:<38} {status_str}")

        if has_critical:
            print(f"\n  {Color.RED}{Color.BOLD}[!] Quality Gate FAILED: Critical security or architectural rule violation!{Color.RESET}")
            return False
        else:
            print(f"\n  {Color.GREEN}{Color.BOLD}[✓] Quality Gate PASSED: Clean static analysis report.{Color.RESET}")
            return True


# ==============================================================================
# 5. CI/CD Automated Pipeline Stage Runner
# ==============================================================================
class PipelineStage:
    def __init__(self, name: str, action: Callable[[], bool], required: bool = True):
        self.name = name
        self.action = action
        self.required = required


class CICDPipelineEngine:
    """Simulasi automated delivery pipeline dengan fail-fast semantics."""

    def __init__(self, pipeline_name: str):
        self.pipeline_name = pipeline_name
        self.stages: List[PipelineStage] = []

    def add_stage(self, name: str, action: Callable[[], bool], required: bool = True) -> None:
        self.stages.append(PipelineStage(name, action, required))

    def trigger(self) -> bool:
        header(f"CI/CD Pipeline Execution: {self.pipeline_name}")
        overall_success = True

        for idx, stage in enumerate(self.stages, 1):
            print(f"\n{Color.BLUE}{Color.BOLD}>>> STAGE [{idx}/{len(self.stages)}]: {stage.name}...{Color.RESET}")
            time.sleep(0.15)  # simulate processing duration

            stage_ok = stage.action()
            if not stage_ok:
                print(f"{Color.RED}{Color.BOLD}✖ Stage '{stage.name}' FAILED.{Color.RESET}")
                if stage.required:
                    print(f"{Color.RED}{Color.BOLD}[FATAL] Pipeline halted due to fail-fast rule at stage '{stage.name}'!{Color.RESET}")
                    overall_success = False
                    break
            else:
                print(f"{Color.GREEN}{Color.BOLD}✔ Stage '{stage.name}' completed successfully.{Color.RESET}")

        print(f"\n{Color.CYAN}{'=' * 68}{Color.RESET}")
        if overall_success:
            print(f"{Color.GREEN}{Color.BOLD}🎉 PIPELINE SUCCEEDED: Build artifact promoted to Staging/Production!{Color.RESET}")
        else:
            print(f"{Color.RED}{Color.BOLD}🚫 PIPELINE FAILED: Build rejected. Notifications dispatched to Slack/Webhook.{Color.RESET}")
        print(f"{Color.CYAN}{'=' * 68}{Color.RESET}")
        return overall_success


# ==============================================================================
# 6. Interactive CLI & Demonstration Orchestrator
# ==============================================================================
def run_full_pipeline_demo() -> None:
    header("Backend Quality Assurance & CI/CD Pipeline Simulator")
    print(f"{Color.WHITE}Materi BAB-09: Unit Testing, Mocking, Quality Gates & CI/CD Pipeline{Color.RESET}\n")

    # Step 1: Quality Gate Manifest
    linter = CodeQualityLinter()
    clean_manifest = {
        "SEC-01": "PASS",
        "TYP-02": "PASS",
        "CMP-03": "PASS",
        "SQL-04": "PASS",
        "FMT-05": "PASS",
    }

    # Step 2: Build pipeline stages
    pipeline = CICDPipelineEngine("backend-api-production-release")

    # Pipeline Actions
    def stage_lint() -> bool:
        return linter.audit_codebase(clean_manifest)

    def stage_unit_tests() -> bool:
        unit_runner = build_unit_tests()
        return unit_runner.run()

    def stage_integration_tests() -> bool:
        subheader("Running In-Memory HTTP Integration Test Suite")
        print("  [1/2] POST /api/v1/orders (Active Session)  --> 200 OK (latency: 14ms)")
        print("  [2/2] POST /api/v1/orders (Auth Missing)   --> 401 Unauthorized (latency: 3ms)")
        return True

    def stage_security_scan() -> bool:
        subheader("Dependency Vulnerability & Secret Scanning (Trivy / Snyk simulation)")
        print(f"  {Color.GREEN}✔ Zero high/critical CVEs identified in locked dependencies.{Color.RESET}")
        print(f"  {Color.GREEN}✔ Git history verified: no API keys or private certificates found.{Color.RESET}")
        return True

    def stage_container_build() -> bool:
        subheader("Docker Image Build & Container Artifact Publishing")
        print("  [+] Compiling bytecode & building multi-stage distroless container image...")
        print("  [+] Image: registry.internal.corp/backend-api:sha-a87f2e1 (Size: 84.2 MB)")
        return True

    pipeline.add_stage("Code Quality & Static Analysis", stage_lint)
    pipeline.add_stage("Unit Testing & Mock Verification", stage_unit_tests)
    pipeline.add_stage("Service Integration Testing", stage_integration_tests)
    pipeline.add_stage("Static Application Security Testing (SAST)", stage_security_scan)
    pipeline.add_stage("Docker Artifact Build & OCI Push", stage_container_build)

    pipeline.trigger()


def interactive_menu() -> None:
    while True:
        header("Interactive Testing & CI/CD Terminal Menu")
        print(f" {Color.BOLD}1.{Color.RESET} Run Unit Tests Suite (OrderService Mock Tests)")
        print(f" {Color.BOLD}2.{Color.RESET} Run Code Quality Linter (Static Analysis Audit)")
        print(f" {Color.BOLD}3.{Color.RESET} Run Full Automated CI/CD Pipeline (Happy Path)")
        print(f" {Color.BOLD}4.{Color.RESET} Simulate Pipeline Failure (Quality Gate Failure Demonstration)")
        print(f" {Color.BOLD}5.{Color.RESET} Exit Lab")
        print(f"{Color.CYAN}{'-' * 68}{Color.RESET}")

        try:
            choice = input(f"{Color.YELLOW}Enter your choice [1-5] (or Press Enter to run all): {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "" or choice == "3":
            run_full_pipeline_demo()
            break
        elif choice == "1":
            runner = build_unit_tests()
            runner.run()
        elif choice == "2":
            linter = CodeQualityLinter()
            linter.audit_codebase({
                "SEC-01": "PASS",
                "TYP-02": "PASS",
                "CMP-03": "PASS",
                "SQL-04": "PASS",
                "FMT-05": "PASS",
            })
        elif choice == "4":
            header("Simulating CI/CD Failure Due to Quality Gate Violation")
            linter = CodeQualityLinter()
            fail_manifest = {
                "SEC-01": "FAIL",  # Hardcoded token violation
                "TYP-02": "PASS",
                "CMP-03": "WARN",
                "SQL-04": "PASS",
                "FMT-05": "PASS",
            }
            fail_pipeline = CICDPipelineEngine("failing-security-pipeline")
            fail_pipeline.add_stage("Code Quality Gate", lambda: linter.audit_codebase(fail_manifest))
            fail_pipeline.add_stage("Unit Tests", lambda: build_unit_tests().run())
            fail_pipeline.trigger()
        elif choice == "5":
            print(f"{Color.GREEN}Lab completed successfully. Have a great day!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Invalid option selected. Please choose between 1 and 5.{Color.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_full_pipeline_demo()
    else:
        # Check if stdin is a tty for interactive input or automated runner
        if sys.stdin.isatty():
            interactive_menu()
        else:
            run_full_pipeline_demo()
