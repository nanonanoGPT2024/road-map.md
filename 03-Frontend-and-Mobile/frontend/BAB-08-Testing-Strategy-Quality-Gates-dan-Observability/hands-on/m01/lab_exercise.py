#!/usr/bin/env python3
"""
Hands-on Lab M01: Frontend Testing Strategy, Quality Gates, & Observability
Simulasi pipeline teknis komprehensif: Unit, Integration, E2E, Quality Gates (SonarQube/Lighthouse),
dan Telemetri Observability Frontend (Core Web Vitals, Error Tracking, Tracing Spans).
"""

import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# --- ANSI Formatting Constants ---
class Color:
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

def print_banner(text: str) -> None:
    border = "=" * 68
    print(f"\n{Color.CYAN}{Color.BOLD}{border}")
    print(f" {text}")
    print(f"{border}{Color.RESET}")

def print_badge(label: str, text: str, color: str) -> None:
    print(f"{color}{Color.BOLD}[{label}]{Color.RESET} {text}")

# --- Domain Enums & Models ---
class TestLayer(Enum):
    UNIT = "Unit (Jest/Vitest)"
    INTEGRATION = "Integration (RTL/MSW)"
    E2E = "End-to-End (Playwright)"

class GateStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"

@dataclass
class TestCase:
    id: str
    layer: TestLayer
    description: str
    duration_ms: float
    passed: bool
    error_msg: Optional[str] = None

@dataclass
class QualityMetrics:
    line_coverage_pct: float
    branch_coverage_pct: float
    bundle_size_kb: float
    lcp_ms: float
    cls_score: float
    inp_ms: float
    critical_vulns: int

# --- Simulator Components ---
class TestRunnerSimulator:
    """Simulasi eksekusi piramida testing frontend."""

    def __init__(self):
        self.tests: List[TestCase] = []

    def run_unit_tests(self) -> List[TestCase]:
        scenarios = [
            ("UT-01", "formatCurrency() handles IDR formatting accurately", 12.4, True, None),
            ("UT-02", "useAuthStore() updates session on LOGIN_SUCCESS", 25.1, True, None),
            ("UT-03", "sanitizeHtml() strips XSS vector <script> tags", 18.0, True, None),
            ("UT-04", "calculateCartTotal() computes tax and discounts correctly", 14.8, True, None),
            ("UT-05", "datePickerReducer() dispatches SELECT_RANGE boundary", 22.3, True, None),
        ]
        return self._execute_suite(TestLayer.UNIT, scenarios)

    def run_integration_tests(self) -> List[TestCase]:
        scenarios = [
            ("IT-01", "LoginForm component submits credentials and triggers MSW mock", 142.5, True, None),
            ("IT-02", "ProductCatalog renders pagination and syncs URL search params", 188.2, True, None),
            ("IT-03", "CheckoutModal handles Payment Gateway webhook callback error", 210.0, True, None),
            ("IT-04", "HeaderProfile reflects reactive user context switch", 95.4, True, None),
        ]
        return self._execute_suite(TestLayer.INTEGRATION, scenarios)

    def run_e2e_tests(self) -> List[TestCase]:
        scenarios = [
            ("E2E-01", "Critical Journey: Guest user adds to cart -> Checkouts -> Order Confirmation", 1250.0, True, None),
            ("E2E-02", "Visual Regression: Home landing page matches Golden Snapshot (0.01% diff)", 840.5, True, None),
            ("E2E-03", "A11y Audit: Axe Core passes WCAG 2.1 AA rules on Checkout View", 620.1, True, None),
        ]
        return self._execute_suite(TestLayer.E2E, scenarios)

    def _execute_suite(self, layer: TestLayer, raw_cases: list) -> List[TestCase]:
        print(f"\n{Color.YELLOW}{Color.BOLD}>>> Executing Test Suite: {layer.value}...{Color.RESET}")
        suite_results = []
        for cid, desc, duration, passed, err in raw_cases:
            time.sleep(0.08)  # Efek visual progres
            if passed:
                status_icon = f"{Color.GREEN}✔ PASS{Color.RESET}"
            else:
                status_icon = f"{Color.RED}✖ FAIL{Color.RESET}"
            print(f"  {status_icon} {Color.WHITE}{cid}{Color.RESET}: {desc} {Color.DIM}({duration:.1f}ms){Color.RESET}")
            tc = TestCase(cid, layer, desc, duration, passed, err)
            suite_results.append(tc)
            self.tests.append(tc)
        return suite_results

class QualityGateEngine:
    """Evaluasi batas metrik kualitas kode (Quality Gate) sebelum rilis ke Production."""

    THRESHOLDS = {
        "min_line_coverage": 80.0,
        "min_branch_coverage": 75.0,
        "max_bundle_size_kb": 250.0,
        "max_lcp_ms": 2500.0,
        "max_cls": 0.10,
        "max_inp_ms": 200.0,
        "max_critical_vulns": 0,
    }

    def evaluate(self, metrics: QualityMetrics) -> Dict[str, tuple]:
        evaluations = {}
        evaluations["Line Coverage"] = (
            metrics.line_coverage_pct >= self.THRESHOLDS["min_line_coverage"],
            f"{metrics.line_coverage_pct}% (Target >= {self.THRESHOLDS['min_line_coverage']}%)"
        )
        evaluations["Branch Coverage"] = (
            metrics.branch_coverage_pct >= self.THRESHOLDS["min_branch_coverage"],
            f"{metrics.branch_coverage_pct}% (Target >= {self.THRESHOLDS['min_branch_coverage']}%)"
        )
        evaluations["Bundle Size Budget"] = (
            metrics.bundle_size_kb <= self.THRESHOLDS["max_bundle_size_kb"],
            f"{metrics.bundle_size_kb} KB (Target <= {self.THRESHOLDS['max_bundle_size_kb']} KB)"
        )
        evaluations["LCP (Largest Contentful Paint)"] = (
            metrics.lcp_ms <= self.THRESHOLDS["max_lcp_ms"],
            f"{metrics.lcp_ms} ms (Target <= {self.THRESHOLDS['max_lcp_ms']} ms)"
        )
        evaluations["CLS (Cumulative Layout Shift)"] = (
            metrics.cls_score <= self.THRESHOLDS["max_cls"],
            f"{metrics.cls_score} (Target <= {self.THRESHOLDS['max_cls']})"
        )
        evaluations["INP (Interaction to Next Paint)"] = (
            metrics.inp_ms <= self.THRESHOLDS["max_inp_ms"],
            f"{metrics.inp_ms} ms (Target <= {self.THRESHOLDS['max_inp_ms']} ms)"
        )
        evaluations["Security Vulnerabilities"] = (
            metrics.critical_vulns <= self.THRESHOLDS["max_critical_vulns"],
            f"{metrics.critical_vulns} Critical (Target == 0)"
        )
        return evaluations

class ObservabilityTelemetrySimulator:
    """Simulasi RUM (Real User Monitoring) dan distributed tracing frontend."""

    @staticmethod
    def inspect_rum_telemetry():
        print(f"\n{Color.MAGENTA}{Color.BOLD}=== Telemetri Observability: Real User Monitoring (RUM) ==={Color.RESET}")
        events = [
            {"time": "09:42:01", "type": "CWV_METRIC", "metric": "LCP", "value": "1840ms", "rating": "GOOD"},
            {"time": "09:42:02", "type": "CWV_METRIC", "metric": "CLS", "value": "0.04", "rating": "GOOD"},
            {"time": "09:42:05", "type": "CWV_METRIC", "metric": "INP", "value": "88ms", "rating": "GOOD"},
            {"time": "09:42:12", "type": "BREADCRUMB", "category": "ui.click", "target": "button#submit-order"},
            {"time": "09:42:13", "type": "TRACE_SPAN", "trace_id": "4bf92f3577b34da6", "span": "fetch /api/v1/orders", "duration": "142ms", "status": "201"},
            {"time": "09:42:15", "type": "LOG_INFO", "message": "SPA Route Transition -> /orders/confirmation/ORD-9881"},
        ]

        for ev in events:
            time.sleep(0.05)
            badge_color = Color.GREEN if ev.get("rating") == "GOOD" or ev.get("status") == "201" else Color.CYAN
            print(f"  {Color.DIM}[{ev['time']}]{Color.RESET} {badge_color}[{ev['type']}]{Color.RESET} {ev}")

# --- Pipeline Orchestrator & CLI Flow ---
def run_full_pipeline():
    print_banner("CI/CD QUALITY GATES & OBSERVABILITY VERIFICATION PIPELINE")

    runner = TestRunnerSimulator()
    runner.run_unit_tests()
    runner.run_integration_tests()
    runner.run_e2e_tests()

    total_tests = len(runner.tests)
    passed_tests = sum(1 for t in runner.tests if t.passed)
    print(f"\n{Color.BOLD}Total Tests Evaluated:{Color.RESET} {total_tests} | "
          f"{Color.GREEN}Passed: {passed_tests}{Color.RESET} | "
          f"{Color.RED}Failed: {total_tests - passed_tests}{Color.RESET}")

    # 2. Quality Gate Evaluation
    print_banner("EVALUASI QUALITY GATE (SonarQube + Lighthouse CI)")
    gate_engine = QualityGateEngine()
    current_metrics = QualityMetrics(
        line_coverage_pct=88.5,
        branch_coverage_pct=81.2,
        bundle_size_kb=214.6,
        lcp_ms=1950.0,
        cls_score=0.03,
        inp_ms=120.0,
        critical_vulns=0,
    )

    eval_results = gate_engine.evaluate(current_metrics)
    all_passed = True

    for rule, (status, detail) in eval_results.items():
        if status:
            tag = f"{Color.GREEN}[PASSED]{Color.RESET}"
        else:
            tag = f"{Color.RED}[FAILED]{Color.RESET}"
            all_passed = False
        print(f"  {tag:<18} {Color.BOLD}{rule:<32}{Color.RESET} -> {detail}")

    print("-" * 68)
    if all_passed:
        print_badge("SUCCESS", "QUALITY GATE STATUS: PASSED (Siap Deploy ke Canary / Production)", Color.GREEN)
    else:
        print_badge("BLOCKED", "QUALITY GATE STATUS: FAILED (Pipeline dihentikan)", Color.RED)

    # 3. Observability Telemetry
    ObservabilityTelemetrySimulator.inspect_rum_telemetry()
    print_banner("LAB SELESAI: SEMUA STRATEGI TESTING & OBSERVABILITY VALID")

def interactive_menu():
    while True:
        print(f"\n{Color.CYAN}{Color.BOLD}--- Interactive Testing & Observability Console ---{Color.RESET}")
        print("1. Jalankan Seluruh CI/CD Pipeline (Testing + Quality Gate + Observability)")
        print("2. Jalankan Hanya Piramida Testing (Unit, Integration, E2E)")
        print("3. Audit Quality Gate & Core Web Vitals")
        print("4. Streaming Live Observability RUM Telemetry")
        print("5. Keluar")
        choice = input(f"{Color.YELLOW}Pilih opsi [1-5]: {Color.RESET}").strip()

        if choice == "1":
            run_full_pipeline()
        elif choice == "2":
            runner = TestRunnerSimulator()
            runner.run_unit_tests()
            runner.run_integration_tests()
            runner.run_e2e_tests()
        elif choice == "3":
            gate_engine = QualityGateEngine()
            metrics = QualityMetrics(88.5, 81.2, 214.6, 1950.0, 0.03, 120.0, 0)
            evals = gate_engine.evaluate(metrics)
            print_banner("AUDIT QUALITY GATE")
            for r, (st, det) in evals.items():
                tag = f"{Color.GREEN}[OK]{Color.RESET}" if st else f"{Color.RED}[FAIL]{Color.RESET}"
                print(f"  {tag} {r}: {det}")
        elif choice == "4":
            ObservabilityTelemetrySimulator.inspect_rum_telemetry()
        elif choice == "5" or choice.lower() == "exit":
            print(f"{Color.GREEN}Terima kasih! Sesi lab selesai.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")

def main():
    # Jika dijalankan secara non-interaktif atau dengan argumen CLI
    if len(sys.argv) > 1 and sys.argv[1] in ("--auto", "--ci", "-y"):
        run_full_pipeline()
    elif not sys.stdin.isatty():
        run_full_pipeline()
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
