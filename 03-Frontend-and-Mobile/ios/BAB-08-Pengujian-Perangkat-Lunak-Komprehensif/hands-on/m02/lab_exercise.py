#!/usr/bin/env python3
"""
Lab Hands-on: iOS Comprehensive Testing Engine (XCTest & UI Testing Simulation)
Bab 08: Pengujian Perangkat Lunak Komprehensif (XCTest & UI Testing) - Modul 02 Deep Dive

Script ini memodelkan arsitektur internal dari framework pengujian iOS:
1. XCTest Core: Lifecycle (setUp/tearDown), Assertions, Performance Measuring (`measure`).
2. Async Expectations: `XCTestExpectation` dengan timeout dan polling inverted/fulfilled.
3. XCUI Automation Engine: Accessibility Tree Hierarchy, Predicate Element Querying,
   serta simulasi interaksi pengguna (tap, typeText, waitForExistence).
"""

import sys
import time
import math
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

# --- ANSI Formatting Engine ---
class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    GRAY = "\033[90m"

# --- Model UI Tree iOS (Simulasi Accessibility Hierarchy) ---
@dataclass
class AccessibilityNode:
    identifier: str
    traits: List[str]  # e.g., ["button"], ["textField"], ["staticText"]
    label: str
    value: str = ""
    is_hittable: bool = True
    children: List['AccessibilityNode'] = field(default_factory=list)

    def find_descendant(self, predicate: Callable[['AccessibilityNode'], bool]) -> Optional['AccessibilityNode']:
        if predicate(self):
            return self
        for child in self.children:
            match = child.find_descendant(predicate)
            if match:
                return match
        return None

# --- XCUI Element & Application Simulation ---
class XCUIElement:
    """Representasi elemen UI yang diuji melalui UI Automation driver."""
    def __init__(self, node_resolver: Callable[[], Optional[AccessibilityNode]]):
        self._resolver = node_resolver

    @property
    def raw_node(self) -> Optional[AccessibilityNode]:
        return self._resolver()

    @property
    def exists(self) -> bool:
        return self._resolver() is not None

    def wait_for_existence(self, timeout_sec: float) -> bool:
        start = time.time()
        while time.time() - start < timeout_sec:
            if self.exists:
                return True
            time.sleep(0.05)
        return self.exists

    def tap(self):
        node = self._resolver()
        if not node:
            raise RuntimeError("XCUIDevice Action Error: Element does not exist in accessibility tree.")
        if not node.is_hittable:
            raise RuntimeError(f"XCUIDevice Action Error: Element '{node.identifier}' is obscured or not hittable.")
        # Simulasi event tap
        time.sleep(0.08)

    def type_text(self, text: str):
        node = self._resolver()
        if not node:
            raise RuntimeError("XCUIDevice Action Error: Element does not exist.")
        if "textField" not in node.traits and "secureTextField" not in node.traits:
            raise RuntimeError(f"XCUIDevice Action Error: Element '{node.identifier}' does not accept text input.")
        node.value = text
        time.sleep(0.05)

class XCUIApplication:
    """Simulasi lifecycle target aplikasi iOS dan root query."""
    def __init__(self):
        self.root: Optional[AccessibilityNode] = None
        self._is_running = False

    def launch(self):
        self._is_running = True
        # Inisialisasi layar login mock
        self.root = AccessibilityNode(
            identifier="RootWindow",
            traits=["window"],
            label="Main Window",
            children=[
                AccessibilityNode("username_field", ["textField"], "Username", value=""),
                AccessibilityNode("password_field", ["secureTextField"], "Password", value=""),
                AccessibilityNode("login_button", ["button"], "Sign In", is_hittable=True),
                AccessibilityNode("status_label", ["staticText"], "Ready", value="Logged Out")
            ]
        )

    def button(self, identifier: str) -> XCUIElement:
        return XCUIElement(lambda: self._find_element(lambda n: "button" in n.traits and n.identifier == identifier))

    def text_field(self, identifier: str) -> XCUIElement:
        return XCUIElement(lambda: self._find_element(lambda n: ("textField" in n.traits or "secureTextField" in n.traits) and n.identifier == identifier))

    def static_text(self, identifier: str) -> XCUIElement:
        return XCUIElement(lambda: self._find_element(lambda n: "staticText" in n.traits and n.identifier == identifier))

    def _find_element(self, predicate: Callable[[AccessibilityNode], bool]) -> Optional[AccessibilityNode]:
        if not self._is_running or not self.root:
            return None
        return self.root.find_descendant(predicate)

    def simulate_server_login(self, success: bool):
        """Simulasi update state UI asinkron dari response API jaringan."""
        def async_mutation():
            time.sleep(0.25)  # Simulasi latensi jaringan seluler
            if not self.root:
                return
            status = self.root.find_descendant(lambda n: n.identifier == "status_label")
            if status:
                if success:
                    status.value = "Dashboard Welcome"
                    status.label = "Auth Successful"
                    # Transisi layar ke dashboard
                    self.root.children = [status, AccessibilityNode("logout_button", ["button"], "Sign Out")]
                else:
                    status.value = "Error: Invalid Credentials"

        threading.Thread(target=async_mutation, daemon=True).start()

# --- XCTest Core Architecture ---
class XCTestExpectation:
    def __init__(self, description: str):
        self.description = description
        self.is_fulfilled = False
        self._event = threading.Event()

    def fulfill(self):
        self.is_fulfilled = True
        self._event.set()

    def wait(self, timeout: float) -> bool:
        return self._event.wait(timeout)

class XCTestAssertionError(AssertionError):
    pass

class XCTestCase:
    def __init__(self):
        self._failures: List[str] = []

    def set_up(self):
        pass

    def tear_down(self):
        pass

    def assert_true(self, expression: bool, message: str = ""):
        if not expression:
            msg = message or "Assertion failed: Expression is false."
            self._failures.append(msg)
            raise XCTestAssertionError(msg)

    def assert_false(self, expression: bool, message: str = ""):
        if expression:
            msg = message or "Assertion failed: Expression is true."
            self._failures.append(msg)
            raise XCTestAssertionError(msg)

    def assert_equal(self, expected: Any, actual: Any, message: str = ""):
        if expected != actual:
            msg = message or f"Assertion failed: Expected '{expected}', but got '{actual}'."
            self._failures.append(msg)
            raise XCTestAssertionError(msg)

    def expectation(self, description: str) -> XCTestExpectation:
        return XCTestExpectation(description)

    def wait_for_expectations(self, expectations: List[XCTestExpectation], timeout: float):
        for exp in expectations:
            success = exp.wait(timeout)
            if not success:
                msg = f"Asynchronous wait failed: Exceeded timeout of {timeout}s for '{exp.description}'"
                self._failures.append(msg)
                raise XCTestAssertionError(msg)

    def measure(self, iterations: int, block: Callable[[], None]) -> Dict[str, float]:
        """Simulasi XCTest block-based performance metrics profiling."""
        samples: List[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            block()
            samples.append(time.perf_counter() - start)
        
        avg = sum(samples) / len(samples)
        variance = sum((x - avg) ** 2 for x in samples) / len(samples)
        stdev = math.sqrt(variance)
        return {"average_sec": avg, "std_dev": stdev, "iterations": iterations}

# --- Test Suites (Implementasi Skenario Uji Nyata) ---
class AuthUnitAndPerfTests(XCTestCase):
    """Unit Testing logic bisnis otentikasi & Performance profiling."""
    
    def test_credential_validator(self):
        def validate(username, password):
            return len(username) >= 4 and len(password) >= 6

        self.assert_true(validate("developer", "secret123"), "Valid credentials should pass.")
        self.assert_false(validate("dev", "123"), "Weak credentials must fail.")

    def test_token_hash_performance(self):
        import hashlib
        # XCTest Metric: Menjamin hashing token tidak menimbulkan frame drop di main thread
        metrics = self.measure(iterations=5, block=lambda: hashlib.sha256(b"secure_user_token_payload").hexdigest())
        self.assert_true(metrics["average_sec"] < 0.005, "Hash computation took too long!")

    def test_async_refresh_token(self):
        exp = self.expectation("Token Refresh API Network Callback")
        
        def fake_network_worker():
            time.sleep(0.12)
            exp.fulfill()

        threading.Thread(target=fake_network_worker, daemon=True).start()
        self.wait_for_expectations([exp], timeout=1.0)

class LoginFlowUITests(XCTestCase):
    """UI Testing end-to-end mensimulasikan XCUIApplication, interaksi touch, dan element verification."""
    
    def set_up(self):
        self.app = XCUIApplication()
        self.app.launch()

    def test_successful_login_flow(self):
        user_field = self.app.text_field("username_field")
        pass_field = self.app.text_field("password_field")
        login_btn = self.app.button("login_button")

        self.assert_true(user_field.exists, "Username field must be present on load.")
        self.assert_true(pass_field.exists, "Password field must be present on load.")

        user_field.type_text("lead_mobile_dev")
        pass_field.type_text("CoreDataRules!")
        self.assert_equal("lead_mobile_dev", user_field.raw_node.value)

        login_btn.tap()
        self.app.simulate_server_login(success=True)

        # XCUITest wait pattern: asynchronous waiting for dashboard arrival
        dashboard_msg = self.app.static_text("status_label")
        exp = self.expectation("Wait for dashboard status label transition")
        
        def check_status():
            for _ in range(20):
                node = dashboard_msg.raw_node
                if node and node.value == "Dashboard Welcome":
                    exp.fulfill()
                    return
                time.sleep(0.05)

        threading.Thread(target=check_status, daemon=True).start()
        self.wait_for_expectations([exp], timeout=2.0)

        # Verifikasi bahwa tombol Sign Out sekarang muncul di hierarki
        logout_btn = self.app.button("logout_button")
        self.assert_true(logout_btn.wait_for_existence(timeout_sec=0.5), "Logout button should exist post-auth.")

# --- Test Runner Engine (Simulasi xcodebuild test execution) ---
class XCTestRunner:
    @staticmethod
    def run_suite(suite_class):
        suite_name = suite_class.__name__
        print(f"\n{TerminalColor.BOLD}{TerminalColor.CYAN}Test Suite '{suite_name}' started.{TerminalColor.RESET}")
        
        instance = suite_class()
        test_methods = [m for m in dir(instance) if m.startswith("test_") and callable(getattr(instance, m))]
        
        passed = 0
        failed = 0
        total_time = 0.0

        for method_name in test_methods:
            instance.set_up()
            method = getattr(instance, method_name)
            start_ts = time.perf_counter()
            error_log = None
            
            try:
                method()
                status_str = f"{TerminalColor.GREEN}PASSED{TerminalColor.RESET}"
                passed += 1
            except Exception as e:
                status_str = f"{TerminalColor.RED}FAILED{TerminalColor.RESET}"
                error_log = str(e)
                failed += 1
            finally:
                instance.tear_down()
                duration = time.perf_counter() - start_ts
                total_time += duration

            duration_ms = duration * 1000.0
            print(f"  Test Case '-[{suite_name} {method_name}]' [{status_str}] ({duration_ms:.2f} ms)")
            if error_log:
                print(f"    {TerminalColor.RED}↳ Assertion Failure: {error_log}{TerminalColor.RESET}")

        summary_color = TerminalColor.GREEN if failed == 0 else TerminalColor.RED
        print(f"{summary_color}Executed {len(test_methods)} tests, with {failed} failure(s) in {total_time:.3f} seconds.{TerminalColor.RESET}")
        return failed == 0

def main():
    print(f"{TerminalColor.BOLD}{TerminalColor.MAGENTA}=== iOS XCTest & XCUI Automation Engine Harness ==={TerminalColor.RESET}")
    print(f"{TerminalColor.GRAY}Memverifikasi test suites: Unit Tests, Metrics, dan Accessibility UI Testing...{TerminalColor.RESET}")

    all_passed = True
    all_passed &= XCTestRunner.run_suite(AuthUnitAndPerfTests)
    all_passed &= XCTestRunner.run_suite(LoginFlowUITests)

    print("\n" + "=" * 60)
    if all_passed:
        print(f"{TerminalColor.BOLD}{TerminalColor.GREEN}✔ ALL XCTEST SUITES PASSED SUCCESSFULLY.{TerminalColor.RESET}")
        sys.exit(0)
    else:
        print(f"{TerminalColor.BOLD}{TerminalColor.RED}✘ SOME XCTEST CASES FAILED.{TerminalColor.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()