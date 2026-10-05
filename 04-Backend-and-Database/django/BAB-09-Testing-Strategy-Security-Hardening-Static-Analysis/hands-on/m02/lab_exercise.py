#!/usr/bin/env python3
"""
Lab Exercise M02: Django Production Hardening, SAST & Testing Strategy Simulator
Bab 09: Testing Strategy, Security Hardening, and Static Analysis.

Standalone interactive simulation replicating Django security audits,
AST-based static analysis (Bandit/Semgrep simulation), and test pyramid execution.
"""

import sys
import time
import re
import json
import hashlib
import hmac
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# ANSI Color Codes
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
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_BLUE = "\033[44m"


def header(text: str):
    print(f"\n{BOLD}{CYAN}=== {text} ==={RESET}")


def success(text: str):
    print(f" {GREEN}[✓] PASS:{RESET} {text}")


def warning(text: str):
    print(f" {YELLOW}[!] WARN:{RESET} {text}")


def failure(text: str):
    print(f" {RED}[✗] FAIL:{RESET} {text}")


def info(text: str):
    print(f" {BLUE}[i] INFO:{RESET} {text}")


@dataclass
class DjangoSettingsProfile:
    name: str
    DEBUG: bool
    ALLOWED_HOSTS: List[str]
    SECURE_SSL_REDIRECT: bool
    SESSION_COOKIE_SECURE: bool
    CSRF_COOKIE_SECURE: bool
    SECURE_HSTS_SECONDS: int
    SECURE_HSTS_INCLUDE_SUBDOMAINS: bool
    SECURE_HSTS_PRELOAD: bool
    SECURE_CONTENT_TYPE_NOSNIFF: bool
    X_FRAME_OPTIONS: str
    CSP_ENABLED: bool
    SECRET_KEY: str


@dataclass
class CodeSample:
    filename: str
    code: str
    description: str


class SecurityAuditEngine:
    """Evaluates Django configuration against production CIS benchmarks."""

    def __init__(self, profile: DjangoSettingsProfile):
        self.profile = profile

    def run_check(self) -> Tuple[int, int, List[str]]:
        passed = 0
        failed = 0
        findings = []

        header(f"Django System Check (`python manage.py check --deploy`) - [{self.profile.name}]")

        # 1. DEBUG flag
        if not self.profile.DEBUG:
            success("security.W018: DEBUG is disabled for production.")
            passed += 1
        else:
            failure("security.W018: DEBUG = True exposes stack traces and configuration secrets.")
            findings.append("Set DEBUG = False")
            failed += 1

        # 2. ALLOWED_HOSTS
        if self.profile.ALLOWED_HOSTS and "*" not in self.profile.ALLOWED_HOSTS:
            success(f"security.W020: ALLOWED_HOSTS strictly configured ({', '.join(self.profile.ALLOWED_HOSTS)}).")
            passed += 1
        else:
            failure("security.W020: ALLOWED_HOSTS contains '*' or is empty; susceptible to Host Header attacks.")
            findings.append("Specify exact domain hostnames in ALLOWED_HOSTS")
            failed += 1

        # 3. HTTPS & HSTS
        if self.profile.SECURE_SSL_REDIRECT and self.profile.SECURE_HSTS_SECONDS >= 31536000:
            success(f"security.W004/008: SSL redirect and HSTS ({self.profile.SECURE_HSTS_SECONDS}s) enforced.")
            passed += 1
        else:
            failure("security.W004/008: Inadequate SSL Redirect or HSTS < 1 year.")
            findings.append("Enable SECURE_SSL_REDIRECT = True and SECURE_HSTS_SECONDS >= 31536000")
            failed += 1

        # 4. Cookies Protection
        if self.profile.SESSION_COOKIE_SECURE and self.profile.CSRF_COOKIE_SECURE:
            success("security.W012/016: SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE are active.")
            passed += 1
        else:
            failure("security.W012/016: Session or CSRF cookies allowed over plain HTTP.")
            findings.append("Set SESSION_COOKIE_SECURE = True and CSRF_COOKIE_SECURE = True")
            failed += 1

        # 5. Clickjacking & MIME Sniffing
        if self.profile.X_FRAME_OPTIONS == "DENY" and self.profile.SECURE_CONTENT_TYPE_NOSNIFF:
            success("security.W002/006: X-Frame-Options: DENY and nosniff header verified.")
            passed += 1
        else:
            failure("security.W002/006: Missing Clickjacking or MIME-sniffing protection.")
            findings.append("Enforce X_FRAME_OPTIONS = 'DENY' and SECURE_CONTENT_TYPE_NOSNIFF = True")
            failed += 1

        # 6. CSP (Content Security Policy)
        if self.profile.CSP_ENABLED:
            success("django-csp: Content-Security-Policy headers active.")
            passed += 1
        else:
            warning("django-csp: No CSP configured; vulnerable to cross-site script injection.")
            findings.append("Install and configure django-csp middleware")
            failed += 1

        return passed, failed, findings


class StaticAnalysisEngine:
    """AST / Pattern SAST scanning simulation (Bandit & Semgrep rules)."""

    PATTERNS = [
        (r"(?i)django\.db\.connection\.cursor\(\).*?\.execute\(f?['\"].*?%s.*?\)", "HIGH", "Raw SQL formatting detected; potential SQL Injection vulnerability (B608)."),
        (r"(?i)execute\([\"'].*?\+.*?[\"']\)", "HIGH", "String concatenation in database query (B608)."),
        (r"(?i)eval\(|exec\(", "HIGH", "Dangerous dynamic execution via eval/exec detected (B307)."),
        (r"(?i)yaml\.load\(.*?,?\s*Loader=yaml\.Loader\)", "HIGH", "Unsafe PyYAML deserialization detected (B506)."),
        (r"(?i)SECRET_KEY\s*=\s*['\"][a-zA-Z0-9_\-\+@#\$\%]{10,}['\"]", "CRITICAL", "Hardcoded SECRET_KEY in source code repository (B105)."),
    ]

    @classmethod
    def scan(cls, samples: List[CodeSample]):
        header("Static Code Analysis (SAST - Bandit/Semgrep Rules Engine)")
        total_issues = 0

        for sample in samples:
            print(f"\n{BOLD}Scanning file:{RESET} {CYAN}{sample.filename}{RESET} ({sample.description})")
            file_issues = 0
            lines = sample.code.strip().split("\n")

            for line_idx, line in enumerate(lines, 1):
                for regex, severity, msg in cls.PATTERNS:
                    if re.search(regex, line):
                        sev_color = RED if severity in ("HIGH", "CRITICAL") else YELLOW
                        print(f"  {sev_color}[{severity}]{RESET} Line {line_idx}: {msg}")
                        print(f"  {DIM}  > {line.strip()}{RESET}")
                        file_issues += 1
                        total_issues += 1

            if file_issues == 0:
                success(f"Clean. No SAST vulnerabilities detected in {sample.filename}.")

        return total_issues


class TestPyramidRunner:
    """Simulates Test Pyramid execution with timing, coverage and rollback checks."""

    def __init__(self):
        self.tests = [
            ("unit", "test_user_password_hasher_argon2", 0.04, True),
            ("unit", "test_hsts_middleware_header_injection", 0.02, True),
            ("unit", "test_jwt_signature_expiration_validator", 0.03, True),
            ("integration", "test_checkout_atomic_db_transaction_rollback", 0.12, True),
            ("integration", "test_api_throttling_rate_limit_redis", 0.09, True),
            ("integration", "test_csrf_token_rotation_on_login", 0.08, True),
            ("e2e_security", "test_sqli_tamper_attempt_on_search_endpoint", 0.25, True),
            ("e2e_security", "test_idor_unauthorized_tenant_data_access", 0.21, True),
        ]

    def run_suite(self):
        header("Automated Test Suite (Django TestCase & Pytest runner)")
        passed = 0
        total_time = 0.0

        for tier, name, duration, result in self.tests:
            time.sleep(0.08)  # simulation pause
            total_time += duration
            tier_badge = f"{BLUE}[{tier.upper()}]{RESET}"
            if result:
                passed += 1
                print(f"  {tier_badge} {name:<48} {GREEN}PASSED{RESET} ({duration:.2f}s)")
            else:
                print(f"  {tier_badge} {name:<48} {RED}FAILED{RESET} ({duration:.2f}s)")

        coverage = 94.2
        print(f"\n{BOLD}Test Summary:{RESET} {passed}/{len(self.tests)} tests passed in {total_time:.2f}s")
        print(f"{BOLD}Code Coverage:{RESET} {GREEN if coverage >= 80 else RED}{coverage}%{RESET} (Target: >=80.0%)")
        return passed == len(self.tests)


def get_default_profiles() -> Dict[str, DjangoSettingsProfile]:
    insecure = DjangoSettingsProfile(
        name="Development / Legacy Insecure",
        DEBUG=True,
        ALLOWED_HOSTS=["*"],
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
        SECURE_HSTS_SECONDS=0,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_PRELOAD=False,
        SECURE_CONTENT_TYPE_NOSNIFF=False,
        X_FRAME_OPTIONS="SAMEORIGIN",
        CSP_ENABLED=False,
        SECRET_KEY="django-insecure-hardcoded-test-key-do-not-use-in-prod",
    )

    hardened = DjangoSettingsProfile(
        name="Production CIS Hardened",
        DEBUG=False,
        ALLOWED_HOSTS=["api.company.id", "admin.company.id"],
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SECURE_HSTS_SECONDS=63072000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
        SECURE_CONTENT_TYPE_NOSNIFF=True,
        X_FRAME_OPTIONS="DENY",
        CSP_ENABLED=True,
        SECRET_KEY="os.environ['DJANGO_SECRET_KEY']",
    )
    return {"insecure": insecure, "hardened": hardened}


def get_sample_codebases() -> List[CodeSample]:
    return [
        CodeSample(
            filename="apps/analytics/views.py",
            description="Vulnerable raw query endpoint",
            code="""
from django.db import connection
from django.http import JsonResponse

def custom_report_view(request):
    user_input = request.GET.get('metric', 'sales')
    cursor = connection.cursor()
    # Flaw: String formatting raw query
    cursor.execute(f"SELECT * FROM stats WHERE metric_name = '%s'" % user_input)
    row = cursor.fetchall()
    return JsonResponse({'data': row})
""",
        ),
        CodeSample(
            filename="config/settings/base.py",
            description="Exposed credentials in repository",
            code="""
import os
# Flaw: Hardcoded secret key
SECRET_KEY = "django-insecure-9f3$8!k#d0291_a1z38v56123490"
DEBUG = False
""",
        ),
        CodeSample(
            filename="apps/users/services.py",
            description="Hardened service using ORM parameterization",
            code="""
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

@transaction.atomic
def activate_enterprise_membership(user_id: int):
    # Hardened: Django ORM parameterizes queries automatically
    user = User.objects.select_for_update().get(id=user_id)
    user.is_enterprise = True
    user.save(update_fields=['is_enterprise'])
    return user
""",
        ),
    ]


def interactive_menu():
    profiles = get_default_profiles()
    active_profile = profiles["insecure"]
    samples = get_sample_codebases()

    while True:
        print(f"\n{BOLD}{BG_BLUE}{WHITE}  DJANGOPRO SECURITY & TESTING HARNESS - LAB EXERCISE M02  {RESET}")
        print(f"{DIM}Current Active Profile:{RESET} {YELLOW if active_profile.DEBUG else GREEN}{active_profile.name}{RESET}")
        print("\nPilih Operasi:")
        print("  1. Jalankan Django Production Security Audit (`check --deploy`)")
        print("  2. Jalankan SAST Static Analysis (Bandit / AST Scanner)")
        print("  3. Jalankan Automated Testing Pyramid (Unit + Integration + Security E2E)")
        print("  4. Toggle Profile: Switch ke Production CIS Hardened")
        print("  5. Toggle Profile: Switch ke Insecure Development")
        print("  6. Tampilkan Rekomendasi Hardening & Compliance Checklist")
        print("  0. Keluar")

        try:
            choice = input(f"\n{BOLD}Masukkan pilihan (0-6): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Program dihentikan.{RESET}")
            break

        if choice == "1":
            auditor = SecurityAuditEngine(active_profile)
            passed, failed, findings = auditor.run_check()
            score = (passed / (passed + failed)) * 100
            print(f"\n{BOLD}Compliance Score:{RESET} {GREEN if score >= 80 else RED}{score:.1f}%{RESET}")
            if findings:
                print(f"{YELLOW}Action Items:{RESET}")
                for idx, item in enumerate(findings, 1):
                    print(f"  {idx}. {item}")

        elif choice == "2":
            issues = StaticAnalysisEngine.scan(samples)
            if issues > 0:
                print(f"\n{RED}{BOLD}SAST Gate: REJECTED{RESET} ({issues} critical vulnerabilities flagged by security gate)")
            else:
                print(f"\n{GREEN}{BOLD}SAST Gate: APPROVED{RESET} (0 critical findings)")

        elif choice == "3":
            runner = TestPyramidRunner()
            success_status = runner.run_suite()
            if success_status:
                print(f"\n{GREEN}{BOLD}CI/CD Pipeline Status: STABLE & PASSING{RESET}")
            else:
                print(f"\n{RED}{BOLD}CI/CD Pipeline Status: BROKEN{RESET}")

        elif choice == "4":
            active_profile = profiles["hardened"]
            print(f"\n{GREEN}Profile dialihkan ke: {active_profile.name}{RESET}")

        elif choice == "5":
            active_profile = profiles["insecure"]
            print(f"\n{YELLOW}Profile dialihkan ke: {active_profile.name}{RESET}")

        elif choice == "6":
            header("Production Security Hardening Checklist (BAB 09)")
            print(f"""
{CYAN}1. Security Headers & Network:{RESET}
   - SECURE_SSL_REDIRECT = True
   - SECURE_HSTS_SECONDS = 31536000 (includeSubDomains=True, preload=True)
   - SECURE_CONTENT_TYPE_NOSNIFF = True
   - X_FRAME_OPTIONS = 'DENY'

{CYAN}2. Cookie Protection:{RESET}
   - SESSION_COOKIE_SECURE = True, SESSION_COOKIE_HTTPONLY = True, SESSION_COOKIE_SAMESITE = 'Lax'
   - CSRF_COOKIE_SECURE = True, CSRF_COOKIE_HTTPONLY = False

{CYAN}3. Static & Dynamic Analysis (DevSecOps):{RESET}
   - Bandit: `bandit -r apps/ -ll` (Catch high-severity AST code vulnerabilities)
   - Pip-Audit / Safety: Audit CVE dependencies in requirements.txt
   - Django Deploy Check: `python manage.py check --deploy`

{CYAN}4. Test Automation Strategy:{RESET}
   - Unit Tests: Isolation with fast mocked external layers (70%)
   - Integration Tests: TransactionTestCase / Database rollback isolation (20%)
   - Security Regression: Parameterized SQLi/XSS/IDOR payload integration (10%)
""")
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih. Latihan lab selesai.{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan masukkan angka 0-6.{RESET}")


if __name__ == "__main__":
    interactive_menu()
