#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Pengujian Perangkat Lunak Komprehensif iOS (XCTest, XCUITest & Mocks)
Modul: BAB-08-Pengujian-Perangkat-Lunak-Komprehensif - Modul 01
Simulasi interaktif test runner berbasis paradigma XCTest pada platform Apple (iOS).
"""

import sys
import time
import uuid
import random
from typing import Callable, List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# ANSI Terminal Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"

class TestStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    MEASURED = "MEASURED"

@dataclass
class TestResult:
    name: str
    status: TestStatus
    duration_ms: float
    message: str = ""
    details: Optional[Dict[str, Any]] = None

# ---------------------------------------------------------
# Mock Domain Models & Protocol Contracts (Swift Equivalent)
# ---------------------------------------------------------
@dataclass
class UserSession:
    user_id: str
    token: str
    is_authenticated: bool

class AuthenticationServiceProtocol:
    """Mock interface mewakili Swift protocol AuthenticationServiceProtocol"""
    def authenticate(self, username: str, pin: str) -> UserSession:
        raise NotImplementedError

class MockAuthenticationService(AuthenticationServiceProtocol):
    """Test Double (Mock/Stub) untuk autentikasi iOS"""
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.invoked_count = 0
        self.captured_username = ""

    def authenticate(self, username: str, pin: str) -> UserSession:
        self.invoked_count += 1
        self.captured_username = username
        if not self.should_succeed:
            raise PermissionError("Autentikasi Biometrik/PIN Gagal.")
        return UserSession(user_id="usr_98172", token=str(uuid.uuid4()), is_authenticated=True)

class AccountViewModel:
    """SUT (System Under Test) yang mengonsumsi protocol dependency"""
    def __init__(self, auth_service: AuthenticationServiceProtocol):
        self.auth_service = auth_service
        self.current_user: Optional[UserSession] = None
        self.error_message: Optional[str] = None

    def login(self, username: str, pin: str) -> bool:
        try:
            session = self.auth_service.authenticate(username, pin)
            self.current_user = session
            self.error_message = None
            return True
        except Exception as exc:
            self.current_user = None
            self.error_message = str(exc)
            return False

# ---------------------------------------------------------
# XCTest Simulation Engine
# ---------------------------------------------------------
class XCTestCase:
    def __init__(self):
        self.results: List[TestResult] = []

    def assert_true(self, condition: bool, message: str = ""):
        if not condition:
            raise AssertionError(message or "XCTAssertTrue failed: condition was False")

    def assert_equal(self, actual: Any, expected: Any, message: str = ""):
        if actual != expected:
            raise AssertionError(message or f"XCTAssertEqual failed: ({actual}) != ({expected})")

    def assert_not_nil(self, value: Any, message: str = ""):
        if value is None:
            raise AssertionError(message or "XCTAssertNotNil failed: value is nil/None")

    def measure(self, block: Callable[[], None], iterations: int = 5) -> float:
        """Simulasi XCTMetric / measure block untuk profiling performa"""
        samples = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            block()
            t1 = time.perf_counter()
            samples.append((t1 - t0) * 1000.0)
        avg = sum(samples) / len(samples)
        return avg

class XCUITestApp:
    """Simulasi accessibility hierarchy dan UI query pada XCUIApplication"""
    def __init__(self):
        self.elements = {
            "welcome_label": {"type": "StaticText", "label": "Selamat Datang di Banking App", "visible": True},
            "username_field": {"type": "TextField", "value": "", "visible": True},
            "pin_field": {"type": "SecureTextField", "value": "", "visible": True},
            "login_button": {"type": "Button", "enabled": True, "visible": True},
            "dashboard_balance": {"type": "StaticText", "label": "Rp 15.750.000", "visible": False},
        }

    def type_text(self, identifier: str, text: str):
        if identifier not in self.elements:
            raise KeyError(f"XCUIElement not found: {identifier}")
        self.elements[identifier]["value"] = text

    def tap(self, identifier: str):
        if identifier not in self.elements:
            raise KeyError(f"XCUIElement not found: {identifier}")
        if identifier == "login_button":
            if self.elements["username_field"]["value"] and self.elements["pin_field"]["value"]:
                self.elements["dashboard_balance"]["visible"] = True

    def exists(self, identifier: str) -> bool:
        return identifier in self.elements and self.elements[identifier]["visible"]

# ---------------------------------------------------------
# Test Suite Implementations
# ---------------------------------------------------------
class iOSComprehensiveTestSuite(XCTestCase):

    def test_unit_auth_success(self):
        mock_auth = MockAuthenticationService(should_succeed=True)
        sut = AccountViewModel(auth_service=mock_auth)

        login_status = sut.login("satria.dev", "123456")

        self.assert_true(login_status, "Login sukses harus mengembalikan True")
        self.assert_equal(mock_auth.invoked_count, 1, "Mock authenticate dipanggil tepat 1 kali")
        self.assert_equal(mock_auth.captured_username, "satria.dev", "Username tersalurkan ke service")
        self.assert_not_nil(sut.current_user, "User session terisi")
        self.assert_true(sut.current_user.is_authenticated, "Status sesi aktif")

    def test_unit_auth_failure_handling(self):
        mock_auth = MockAuthenticationService(should_succeed=False)
        sut = AccountViewModel(auth_service=mock_auth)

        login_status = sut.login("unknown_user", "000000")

        self.assert_true(not login_status, "Login harus gagal jika kredensial tidak valid")
        self.assert_equal(sut.current_user, None, "Sesi harus nil saat gagal")
        self.assert_not_nil(sut.error_message, "Pesan galat harus tercatat")

    def test_performance_crypto_signature(self):
        """Simulasi XCTMetric pengujian beban algoritma enkripsi token iOS"""
        def heavy_crypto_workload():
            data = [random.random() for _ in range(15000)]
            _ = sorted(data)

        avg_ms = self.measure(heavy_crypto_workload, iterations=4)
        # Ambang batas SLA latency: < 50.0 ms
        self.assert_true(avg_ms < 50.0, f"Eksekusi crypto lambat ({avg_ms:.2f}ms > 50ms)")
        return {"avg_ms": avg_ms}

    def test_xcui_login_flow(self):
        """Simulasi XCUIApplication end-to-end integration test"""
        app = XCUITestApp()
        self.assert_true(app.exists("welcome_label"), "Welcome label harus tampil")

        app.type_text("username_field", "satria.dev")
        app.type_text("pin_field", "882910")
        app.tap("login_button")

        self.assert_true(app.exists("dashboard_balance"), "Dashboard balance harus muncul pasca-login")

    def test_snapshot_golden_master_verification(self):
        """Simulasi Snapshot Testing (memverifikasi UI Layout hash match)"""
        view_rendered_json = '{"view": "DashboardView", "components": 5, "palette": "systemDark"}'
        golden_master_checksum = hash(view_rendered_json)
        current_checksum = hash('{"view": "DashboardView", "components": 5, "palette": "systemDark"}')

        self.assert_equal(current_checksum, golden_master_checksum, "Render snapshot cocok dengan baseline golden master")

# ---------------------------------------------------------
# Interactive Runner & Terminal Visualizer
# ---------------------------------------------------------
def run_test_item(suite: iOSComprehensiveTestSuite, test_func: Callable, test_name: str) -> TestResult:
    start_time = time.perf_counter()
    details = None
    try:
        ret = test_func()
        if isinstance(ret, dict):
            details = ret
            status = TestStatus.MEASURED
        else:
            status = TestStatus.PASSED
        duration = (time.perf_counter() - start_time) * 1000.0
        return TestResult(name=test_name, status=status, duration_ms=duration, details=details)
    except AssertionError as ae:
        duration = (time.perf_counter() - start_time) * 1000.0
        return TestResult(name=test_name, status=TestStatus.FAILED, duration_ms=duration, message=str(ae))
    except Exception as ex:
        duration = (time.perf_counter() - start_time) * 1000.0
        return TestResult(name=test_name, status=TestStatus.FAILED, duration_ms=duration, message=f"Unexpected: {str(ex)}")

def print_banner():
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{BG_BLUE}   XCODE XCTEST TEST SUITE HARNESS - iOS TESTING COMPREHENSIVE LAB   {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{DIM}Target: iOS 17 SDK | Simulator: iPhone 15 Pro | Framework: XCTest & XCUITest{RESET}\n")

def display_menu():
    print(f"{BOLD}Pilih Skenario Pengujian:{RESET}")
    print(f"  {CYAN}[1]{RESET} Jalankan Unit Testing & Dependency Injection Mocking")
    print(f"  {CYAN}[2]{RESET} Jalankan Performance Metric Profiling (measure metric block)")
    print(f"  {CYAN}[3]{RESET} Jalankan XCUITest UI Accessibility Query Simulation")
    print(f"  {CYAN}[4]{RESET} Jalankan Snapshot/Golden Master Regression Check")
    print(f"  {CYAN}[5]{RESET} {BOLD}Jalankan Semua Test (Comprehensive Suite Run){RESET}")
    print(f"  {CYAN}[0]{RESET} Keluar")

def execute_suite(selected_indices: List[int]):
    suite = iOSComprehensiveTestSuite()
    catalog = [
        (suite.test_unit_auth_success, "test_unit_auth_success", "Unit Test: Authentication Flow Success"),
        (suite.test_unit_auth_failure_handling, "test_unit_auth_failure_handling", "Unit Test: Auth Error & Exception Handling"),
        (suite.test_performance_crypto_signature, "test_performance_crypto_signature", "Performance Metric: Crypto Measure Loop"),
        (suite.test_xcui_login_flow, "test_xcui_login_flow", "XCUITest: Element Query & User Interaction Flow"),
        (suite.test_snapshot_golden_master_verification, "test_snapshot_golden_master_verification", "Snapshot: Golden Master Hash Diff Verification"),
    ]

    selected_tests = [catalog[i] for i in selected_indices if 0 <= i < len(catalog)]
    print(f"\n{BOLD}{YELLOW}Memulai Eksekusi {len(selected_tests)} Uji Coba...{RESET}\n")

    passed_count = 0
    failed_count = 0

    for func, code_name, description in selected_tests:
        print(f"{DIM}Running {code_name}...{RESET}", end="\r")
        time.sleep(0.15)  # Animasi interaktif terminal
        result = run_test_item(suite, func, code_name)

        if result.status == TestStatus.PASSED:
            passed_count += 1
            status_badge = f"{BOLD}{GREEN}[PASS]{RESET}"
            extra = ""
        elif result.status == TestStatus.MEASURED:
            passed_count += 1
            status_badge = f"{BOLD}{MAGENTA}[PERF]{RESET}"
            extra = f"{DIM}(Avg Latency: {result.details['avg_ms']:.2f}ms){RESET}"
        else:
            failed_count += 1
            status_badge = f"{BOLD}{RED}[FAIL]{RESET}"
            extra = f"\n    {RED}-> Reason: {result.message}{RESET}"

        print(f"  {status_badge} {BOLD}{description}{RESET} ({result.duration_ms:.2f}ms) {extra}")

    print(f"\n{BOLD}{CYAN}----------------------------------------------------------------------{RESET}")
    summary_color = GREEN if failed_count == 0 else RED
    print(f"{BOLD}Hasil Akhir:{RESET} Total: {len(selected_tests)} | "
          f"{GREEN}Lolos: {passed_count}{RESET} | "
          f"{RED}Gagal: {failed_count}{RESET}")
    if failed_count == 0:
        print(f"{BOLD}{GREEN}*** SEMUA PENGUJIAN XCTEST DINYATAKAN VALID & MEMENUHI SLA IOS ***{RESET}")
    else:
        print(f"{BOLD}{RED}*** TERDAPAT REGRESI ATAU KEGAGALAN ASERSI PENGUJIAN ***{RESET}")
    print(f"{BOLD}{CYAN}----------------------------------------------------------------------{RESET}\n")

def main():
    print_banner()

    # Mode Non-Interaktif jika flag --all diberikan
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a"):
        execute_suite([0, 1, 2, 3, 4])
        return

    while True:
        display_menu()
        try:
            choice = input(f"\n{BOLD}{BLUE}Masukkan pilihan [0-5]: {RESET}").strip()
            if choice == "0":
                print(f"{DIM}Keluar dari lab testing iOS.{RESET}")
                break
            elif choice == "1":
                execute_suite([0, 1])
            elif choice == "2":
                execute_suite([2])
            elif choice == "3":
                execute_suite([3])
            elif choice == "4":
                execute_suite([4])
            elif choice == "5":
                execute_suite([0, 1, 2, 3, 4])
            else:
                print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Sesi dihentikan pengguna.{RESET}")
            break

if __name__ == "__main__":
    main()
