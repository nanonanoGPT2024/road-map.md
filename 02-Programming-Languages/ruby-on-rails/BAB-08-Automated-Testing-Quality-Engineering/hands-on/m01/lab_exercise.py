#!/usr/bin/env python3
"""
Ruby on Rails - BAB 08: Automated Testing & Quality Engineering
Interactive CLI Simulator & Testing Framework Emulation in Python 3.

Covers:
1. Minitest & RSpec DSL Emulation (describe, it, expect, assert)
2. Test Pyramid: Model (Unit), Request (Integration), and System (E2E)
3. Fixtures vs FactoryBot Pattern Simulation
4. Test Doubles: Stubs, Mocks, and Spies
5. Quality Engineering: Code Coverage, Flaky Test Detection, and CI Gate
"""

import sys
import time
import random
from typing import Any, Callable, Dict, List, Optional


# ==============================================================================
# ANSI Color Palette for Terminal Output
# ==============================================================================
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
======================================================================
  RAILS TESTING & QUALITY ENGINEERING SIMULATOR (BAB-08)
  Frameworks: Minitest | RSpec | FactoryBot | Capybara Emulation
======================================================================{Colors.RESET}"""
    print(banner)


# ==============================================================================
# Mini Testing Framework & Assertion Library (Rails Style)
# ==============================================================================
class TestResult:
    def __init__(self, description: str, passed: bool, error: Optional[str] = None, duration_ms: float = 0.0):
        self.description = description
        self.passed = passed
        self.error = error
        self.duration_ms = duration_ms


class Expectation:
    def __init__(self, actual: Any):
        self.actual = actual

    def to_equal(self, expected: Any):
        if self.actual != expected:
            raise AssertionError(f"Expected {expected!r}, but got {self.actual!r}")

    def to_be_valid(self):
        if hasattr(self.actual, "is_valid"):
            if not self.actual.is_valid():
                errors = getattr(self.actual, "errors", [])
                raise AssertionError(f"Expected object to be valid, but got errors: {errors}")
        else:
            raise AssertionError(f"Object {self.actual!r} does not support validation checking")

    def to_have_http_status(self, expected_status: int):
        status = getattr(self.actual, "status_code", None)
        if status != expected_status:
            raise AssertionError(f"Expected HTTP status {expected_status}, received {status}")


def expect(actual: Any) -> Expectation:
    return Expectation(actual)


# ==============================================================================
# Domain Entities (Simulated Rails Models & Controller Actions)
# ==============================================================================
class Article:
    def __init__(self, title: str, body: str, status: str = "draft"):
        self.title = title
        self.body = body
        self.status = status
        self.errors: List[str] = []

    def is_valid(self) -> bool:
        self.errors.clear()
        if not self.title or len(self.title.strip()) < 5:
            self.errors.append("Title must be present and at least 5 characters long")
        if not self.body or len(self.body.strip()) < 10:
            self.errors.append("Body must be present and at least 10 characters long")
        if self.status not in ["draft", "published", "archived"]:
            self.errors.append(f"Status '{self.status}' is not included in the list")
        return len(self.errors) == 0


class PaymentGatewayService:
    def charge(self, amount_cents: int, currency: str = "USD") -> Dict[str, Any]:
        # Remote external call simulation
        time.sleep(0.05)
        return {"success": True, "charge_id": f"ch_{random.randint(1000, 9999)}"}


class ArticlesController:
    def __init__(self, db: List[Article]):
        self.db = db

    def create(self, params: Dict[str, str]) -> Dict[str, Any]:
        article = Article(title=params.get("title", ""), body=params.get("body", ""), status=params.get("status", "draft"))
        if article.is_valid():
            self.db.append(article)
            return {"status_code": 201, "body": {"message": "Article created successfully", "article": article}}
        return {"status_code": 422, "body": {"errors": article.errors}}


# ==============================================================================
# FactoryBot & Test Double Simulation
# ==============================================================================
class FactoryBot:
    _sequences: Dict[str, int] = {"article_title": 0}

    @classmethod
    def build_article(cls, **overrides) -> Article:
        cls._sequences["article_title"] += 1
        seq = cls._sequences["article_title"]
        defaults = {
            "title": f"Rails Quality Post #{seq}",
            "body": "Comprehensive testing ensures rock-solid production reliability.",
            "status": "published",
        }
        defaults.update(overrides)
        return Article(**defaults)


class MockDouble:
    def __init__(self, target_obj: Any, method_name: str, return_value: Any):
        self.target_obj = target_obj
        self.method_name = method_name
        self.return_value = return_value
        self.orig_method = getattr(target_obj, method_name, None)
        self.call_count = 0

    def __enter__(self):
        def patched_method(*args, **kwargs):
            self.call_count += 1
            return self.return_value
        setattr(self.target_obj, self.method_name, patched_method)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.orig_method:
            setattr(self.target_obj, self.method_name, self.orig_method)
        else:
            delattr(self.target_obj, self.method_name)


# ==============================================================================
# Test Suites Execution Engine
# ==============================================================================
class TestSuiteRunner:
    def __init__(self):
        self.results: List[TestResult] = []

    def run_case(self, desc: str, test_fn: Callable):
        start = time.perf_counter()
        try:
            test_fn()
            duration = (time.perf_counter() - start) * 1000
            res = TestResult(desc, True, duration_ms=duration)
            print(f"  {Colors.GREEN}✓ [PASS]{Colors.RESET} {desc} ({duration:.2f}ms)")
        except AssertionError as e:
            duration = (time.perf_counter() - start) * 1000
            res = TestResult(desc, False, error=str(e), duration_ms=duration)
            print(f"  {Colors.RED}✗ [FAIL]{Colors.RESET} {desc} ({duration:.2f}ms)\n    {Colors.RED}Error: {e}{Colors.RESET}")
        except Exception as ex:
            duration = (time.perf_counter() - start) * 1000
            res = TestResult(desc, False, error=f"Unhandled: {ex}", duration_ms=duration)
            print(f"  {Colors.RED}⚡ [ERROR]{Colors.RESET} {desc} ({duration:.2f}ms)\n    {Colors.RED}{ex}{Colors.RESET}")
        self.results.append(res)


# ==============================================================================
# Laboratory Test Modules
# ==============================================================================
def run_unit_tests():
    print(f"\n{Colors.BOLD}{Colors.YELLOW}>>> Running Level 1: Unit Tests (ActiveRecord Model Specs){Colors.RESET}")
    runner = TestSuiteRunner()

    def test_valid_article():
        art = FactoryBot.build_article()
        expect(art).to_be_valid()

    def test_invalid_short_title():
        art = FactoryBot.build_article(title="Hey")
        if art.is_valid():
            raise AssertionError("Article should be invalid when title length < 5")
        expect(art.errors[0]).to_equal("Title must be present and at least 5 characters long")

    def test_invalid_status_enum():
        art = FactoryBot.build_article(status="deleted")
        if art.is_valid():
            raise AssertionError("Status 'deleted' is not an allowed enum state")

    runner.run_case("Model: Article is valid with default factory traits", test_valid_article)
    runner.run_case("Model: Article validates presence and length of title", test_invalid_short_title)
    runner.run_case("Model: Article enforces status enum inclusion", test_invalid_status_enum)


def run_integration_tests():
    print(f"\n{Colors.BOLD}{Colors.BLUE}>>> Running Level 2: Request & Integration Tests (API Endpoints){Colors.RESET}")
    runner = TestSuiteRunner()
    db: List[Article] = []
    controller = ArticlesController(db)

    class HttpResponse:
        def __init__(self, data: Dict[str, Any]):
            self.status_code = data["status_code"]
            self.body = data["body"]

    def test_create_article_success():
        payload = {"title": "Mastering RSpec in Rails", "body": "Writing readable specs with context and let blocks."}
        raw_res = controller.create(payload)
        res = HttpResponse(raw_res)
        expect(res).to_have_http_status(201)
        expect(len(db)).to_equal(1)

    def test_create_article_validation_failure():
        payload = {"title": "Bad", "body": "Short"}
        raw_res = controller.create(payload)
        res = HttpResponse(raw_res)
        expect(res).to_have_http_status(422)

    runner.run_case("POST /api/v1/articles - returns 201 Created and persists record", test_create_article_success)
    runner.run_case("POST /api/v1/articles - returns 422 Unprocessable on invalid input", test_create_article_validation_failure)


def run_system_mock_tests():
    print(f"\n{Colors.BOLD}{Colors.CYAN}>>> Running Level 3: System Tests & Test Doubles (Mocks/Stubs){Colors.RESET}")
    runner = TestSuiteRunner()
    gateway = PaymentGatewayService()

    def test_payment_stubbing():
        fake_response = {"success": True, "charge_id": "ch_mock_9999"}
        with MockDouble(gateway, "charge", fake_response) as stub:
            res = gateway.charge(5000, "USD")
            expect(res["charge_id"]).to_equal("ch_mock_9999")
            expect(stub.call_count).to_equal(1)

    def test_simulated_capybara_checkout_flow():
        # Simulated Headless Browser DOM interaction
        session = {"page": "checkout", "inputs": {"card": "4242..."}, "button_clicked": True}
        time.sleep(0.04)  # Simulate browser rendering latency
        expect(session["button_clicked"]).to_equal(True)

    runner.run_case("Stubs: External PaymentGatewayService is isolated using mock double", test_payment_stubbing)
    runner.run_case("System: Capybara E2E simulates headless user checkout submission", test_simulated_capybara_checkout_flow)


def run_quality_pipeline():
    print(f"\n{Colors.BOLD}{Colors.HEADER}>>> Running Automated Quality Engineering CI/CD Pipeline{Colors.RESET}")
    total_loc = 1420
    covered_loc = 1350
    coverage_pct = (covered_loc / total_loc) * 100
    quality_threshold = 90.0

    print(f"  {Colors.DIM}[Quality Gate] SimpleCov Metric Assessment...{Colors.RESET}")
    time.sleep(0.05)
    print(f"  Total Lines of Code: {total_loc}")
    print(f"  Covered Lines      : {covered_loc}")
    print(f"  Branch Coverage    : {coverage_pct:.2f}%")

    if coverage_pct >= quality_threshold:
        print(f"  {Colors.GREEN}{Colors.BOLD}✓ QUALITY GATE PASSED (Threshold >= {quality_threshold}%){Colors.RESET}")
    else:
        print(f"  {Colors.RED}{Colors.BOLD}✗ QUALITY GATE FAILED: Under threshold{Colors.RESET}")


# ==============================================================================
# Interactive Menu Loop
# ==============================================================================
def interactive_menu():
    print_banner()
    while True:
        print(f"\n{Colors.BOLD}PILIH MENU LAB TESTING & QUALITY ENGINEERING:{Colors.RESET}")
        print("  1. Run Unit Tests (ActiveRecord Model Validation & Business Logic)")
        print("  2. Run Integration Tests (Controller Request / Response Specs)")
        print("  3. Run System & Stubs Tests (Capybara E2E + External Service Mocking)")
        print("  4. Run Full CI/CD Quality Pipeline (All Suites + Coverage Audit)")
        print("  5. Exit Simulator")

        try:
            choice = input(f"\n{Colors.BOLD}Masukkan pilihan (1-5): {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            run_unit_tests()
        elif choice == "2":
            run_integration_tests()
        elif choice == "3":
            run_system_mock_tests()
        elif choice == "4":
            run_unit_tests()
            run_integration_tests()
            run_system_mock_tests()
            run_quality_pipeline()
        elif choice == "5":
            print(f"{Colors.GREEN}Terima kasih! Lab Automated Testing & Quality Engineering selesai.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan masukkan angka 1 - 5.{Colors.RESET}")


if __name__ == "__main__":
    interactive_menu()
