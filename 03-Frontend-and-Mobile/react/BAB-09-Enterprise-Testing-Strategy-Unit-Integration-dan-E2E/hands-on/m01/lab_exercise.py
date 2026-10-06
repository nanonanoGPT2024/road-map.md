#!/usr/bin/env python3
"""
Lab Exercise M01: Enterprise Testing Strategy Simulator (React Core)
BAB-09: Enterprise Testing Strategy (Unit, Integration, dan E2E)

Simulasi mandiri arsitektur testing modern React:
1. Unit Testing (Pure utility, reducer, & state transition)
2. Integration Testing (Virtual DOM, RTL query priority, MSW network interception)
3. End-to-End (E2E) Testing (Headless browser automation lifecycle & flaky retry)
"""

import sys
import time
import json
from typing import Callable, Dict, Any, List, Optional

# --- ANSI Color Codes ---
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
DIM = "\033[2m"
RESET = "\033[0m"


class MiniAssertionError(Exception):
    """Exception raised when an assertion fails."""
    pass


class Expect:
    """Fluent assertion utility similar to Jest/Vitest expect()."""
    def __init__(self, actual: Any):
        self.actual = actual

    def to_equal(self, expected: Any) -> None:
        if self.actual != expected:
            raise MiniAssertionError(f"Expected {expected!r}, but received {self.actual!r}")

    def to_be_truthy(self) -> None:
        if not bool(self.actual):
            raise MiniAssertionError(f"Expected truthy value, but received {self.actual!r}")

    def to_contain(self, item: Any) -> None:
        if item not in self.actual:
            raise MiniAssertionError(f"Expected container to contain {item!r}, but it was absent")

    def to_be_greater_than(self, value: float) -> None:
        if not (self.actual > value):
            raise MiniAssertionError(f"Expected {self.actual} to be > {value}")


def expect(actual: Any) -> Expect:
    return Expect(actual)


# ==========================================
# 1. UNIT TESTING DOMAIN (Reducers & Logic)
# ==========================================

def user_auth_reducer(state: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    """Pure React reducer function simulation."""
    action_type = action.get("type")
    payload = action.get("payload", {})

    if action_type == "LOGIN_REQUEST":
        return {**state, "isLoading": True, "error": None}
    elif action_type == "LOGIN_SUCCESS":
        return {**state, "isLoading": False, "isAuthenticated": True, "user": payload.get("user"), "error": None}
    elif action_type == "LOGIN_FAILURE":
        return {**state, "isLoading": False, "isAuthenticated": False, "error": payload.get("error")}
    elif action_type == "LOGOUT":
        return {"isLoading": False, "isAuthenticated": False, "user": None, "error": None}
    return state


def calculate_cart_summary(items: List[Dict[str, Any]], tax_rate: float = 0.11) -> Dict[str, float]:
    """Pure utility business logic."""
    subtotal = sum(item["price"] * item.get("quantity", 1) for item in items)
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)
    return {"subtotal": subtotal, "tax": tax, "total": total}


# ==========================================
# 2. INTEGRATION TESTING (RTL + MSW SIMULATION)
# ==========================================

class VNode:
    """Lightweight Virtual DOM Element node representation."""
    def __init__(self, tag: str, props: Optional[Dict[str, Any]] = None, text: str = "", children: Optional[List['VNode']] = None):
        self.tag = tag
        self.props = props or {}
        self.text = text
        self.children = children or []

    def get_role(self) -> Optional[str]:
        return self.props.get("role") or ("button" if self.tag == "button" else None)


class MSWMockServer:
    """Mock Service Worker (MSW) network interceptor simulation."""
    def __init__(self):
        self.handlers: Dict[str, Callable[[], Dict[str, Any]]] = {}
        self.intercepted_calls: List[str] = []

    def get(self, url: str, resolver: Callable[[], Dict[str, Any]]):
        self.handlers[f"GET {url}"] = resolver

    def post(self, url: str, resolver: Callable[[], Dict[str, Any]]):
        self.handlers[f"POST {url}"] = resolver

    def dispatch(self, method: str, url: str) -> Dict[str, Any]:
        key = f"{method.upper()} {url}"
        self.intercepted_calls.append(key)
        if key in self.handlers:
            return self.handlers[key]()
        return {"status": 404, "body": {"error": "Endpoint not mocked"}}


class RTLScreen:
    """React Testing Library query engine mimicking query priorities."""
    def __init__(self, root: VNode):
        self.root = root

    def _traverse(self, node: VNode) -> List[VNode]:
        nodes = [node]
        for child in node.children:
            nodes.extend(self._traverse(child))
        return nodes

    def get_by_role(self, role: str, name: Optional[str] = None) -> VNode:
        all_nodes = self._traverse(self.root)
        for n in all_nodes:
            if n.get_role() == role:
                if name is None or n.text == name or n.props.get("aria-label") == name:
                    return n
        raise MiniAssertionError(f"RTL: Unable to find accessible element with role={role!r} name={name!r}")

    def get_by_text(self, text: str) -> VNode:
        all_nodes = self._traverse(self.root)
        for n in all_nodes:
            if text in n.text:
                return n
        raise MiniAssertionError(f"RTL: Element with text {text!r} not found in container")


# ==========================================
# 3. E2E TESTING (PLAYWRIGHT / CYPRESS SIM)
# ==========================================

class BrowserPageSimulator:
    """Headless browser context simulation for Playwright E2E workflows."""
    def __init__(self):
        self.current_url = "about:blank"
        self.dom_state: Dict[str, str] = {}
        self.action_log: List[str] = []

    def goto(self, url: str) -> None:
        self.current_url = url
        self.action_log.append(f"goto({url})")
        # Simulating initial hydration
        self.dom_state = {
            "#email-input": "",
            "#password-input": "",
            "#submit-btn": "Sign In",
            "#dashboard-header": "Not Authenticated"
        }

    def fill(self, selector: str, value: str) -> None:
        if selector not in self.dom_state:
            raise MiniAssertionError(f"Locator failed: selector {selector} not found")
        self.dom_state[selector] = value
        self.action_log.append(f"fill({selector}, '***')")

    def click(self, selector: str) -> None:
        if selector not in self.dom_state:
            raise MiniAssertionError(f"Locator failed: selector {selector} not clickable")
        self.action_log.append(f"click({selector})")
        # Simulate form submit trigger
        if selector == "#submit-btn":
            if self.dom_state.get("#email-input") == "engineer@enterprise.io":
                self.dom_state["#dashboard-header"] = "Enterprise Dashboard (Admin)"
            else:
                self.dom_state["#dashboard-header"] = "Invalid Credentials"

    def expect_locator_to_have_text(self, selector: str, expected_text: str) -> None:
        val = self.dom_state.get(selector, "")
        if expected_text not in val:
            raise MiniAssertionError(f"E2E Assertion Failed: {selector} has text '{val}', expected '{expected_text}'")


# ==========================================
# TEST RUNNER HARNESS
# ==========================================

class EnterpriseTestRunner:
    def __init__(self):
        self.suites_count = 0
        self.passed_tests = 0
        self.failed_tests = 0

    def describe(self, suite_name: str, test_fns: List[tuple]) -> None:
        self.suites_count += 1
        print(f"\n{BOLD}{CYAN}● {suite_name}{RESET}")
        for test_name, fn in test_fns:
            sys.stdout.write(f"  {DIM}RUNS{RESET}  {test_name} ... ")
            sys.stdout.flush()
            t0 = time.perf_counter()
            try:
                fn()
                elapsed = (time.perf_counter() - t0) * 1000
                print(f"\r  {GREEN}✓ PASS{RESET} {test_name} {DIM}({elapsed:.1f} ms){RESET}")
                self.passed_tests += 1
            except Exception as ex:
                elapsed = (time.perf_counter() - t0) * 1000
                print(f"\r  {RED}✕ FAIL{RESET} {test_name} {DIM}({elapsed:.1f} ms){RESET}")
                print(f"    {RED}Error: {ex}{RESET}")
                self.failed_tests += 1

    def print_summary(self) -> None:
        total = self.passed_tests + self.failed_tests
        print(f"\n{BOLD}{'=' * 50}{RESET}")
        print(f"{BOLD}Test Suites:{RESET} {self.suites_count} executed")
        print(f"{BOLD}Tests:{RESET}       {GREEN}{self.passed_tests} passed{RESET}, {RED if self.failed_tests else DIM}{self.failed_tests} failed{RESET}, {total} total")
        status_color = GREEN if self.failed_tests == 0 else RED
        status_label = "ENTERPRISE QUALITY GATE PASSED" if self.failed_tests == 0 else "QUALITY GATE FAILED"
        print(f"{BOLD}Result:{RESET}      {status_color}{status_label}{RESET}")
        print(f"{BOLD}{'=' * 50}{RESET}")


# ==========================================
# SPECIFICATIONS (TEST CASES)
# ==========================================

def run_all_unit_tests(runner: EnterpriseTestRunner) -> None:
    def test_auth_reducer_login_flow():
        initial = {"isLoading": False, "isAuthenticated": False, "user": None, "error": None}
        loading_state = user_auth_reducer(initial, {"type": "LOGIN_REQUEST"})
        expect(loading_state["isLoading"]).to_equal(True)
        expect(loading_state["isAuthenticated"]).to_equal(False)

        success_state = user_auth_reducer(loading_state, {
            "type": "LOGIN_SUCCESS",
            "payload": {"user": {"id": "usr-01", "role": "admin"}}
        })
        expect(success_state["isLoading"]).to_equal(False)
        expect(success_state["isAuthenticated"]).to_equal(True)
        expect(success_state["user"]["role"]).to_equal("admin")

    def test_cart_tax_and_total_calculation():
        cart = [
            {"id": "item-1", "name": "Enterprise License", "price": 100.0, "quantity": 2},
            {"id": "item-2", "name": "Dedicated Support", "price": 50.0, "quantity": 1}
        ]
        result = calculate_cart_summary(cart, tax_rate=0.10)
        expect(result["subtotal"]).to_equal(250.0)
        expect(result["tax"]).to_equal(25.0)
        expect(result["total"]).to_equal(275.0)

    runner.describe("Unit Testing: Reducers & Pure Functions (Fast Feedback Layer)", [
        ("authReducer should correctly transition login request and success states", test_auth_reducer_login_flow),
        ("calculate_cart_summary should compute accurate enterprise tax rates", test_cart_tax_and_total_calculation)
    ])


def run_all_integration_tests(runner: EnterpriseTestRunner) -> None:
    def test_msw_network_and_rtl_query():
        # Setup MSW
        server = MSWMockServer()
        server.get("/api/v1/profile", lambda: {
            "status": 200,
            "body": {"name": "Alice Developer", "tier": "Enterprise"}
        })

        # Mock Virtual DOM Rendered by Component
        profile_res = server.dispatch("GET", "/api/v1/profile")
        expect(profile_res["status"]).to_equal(200)

        vdom_root = VNode("div", props={"role": "region"}, children=[
            VNode("h1", text=f"Welcome, {profile_res['body']['name']}"),
            VNode("button", props={"role": "button", "aria-label": "Refresh"}, text="Sync Data"),
            VNode("span", text=f"Tier: {profile_res['body']['tier']}")
        ])

        screen = RTLScreen(vdom_root)
        heading = screen.get_by_text("Welcome, Alice Developer")
        expect(heading.text).to_contain("Alice Developer")

        btn = screen.get_by_role("button", name="Refresh")
        expect(btn.props.get("aria-label")).to_equal("Refresh")

    runner.describe("Integration Testing: React Testing Library & Mock Service Worker", [
        ("ProfileWidget renders mock API data and honors RTL role query priorities", test_msw_network_and_rtl_query)
    ])


def run_all_e2e_tests(runner: EnterpriseTestRunner) -> None:
    def test_e2e_login_journey():
        page = BrowserPageSimulator()
        page.goto("https://enterprise-react.internal/login")
        page.fill("#email-input", "engineer@enterprise.io")
        page.fill("#password-input", "super-secret-vault-pwd")
        page.click("#submit-btn")
        page.expect_locator_to_have_text("#dashboard-header", "Enterprise Dashboard (Admin)")

    runner.describe("End-to-End (E2E) Testing: Critical Path User Journey (Playwright Sim)", [
        ("Critical Authentication Path: User logs in and arrives at Admin Dashboard", test_e2e_login_journey)
    ])


# ==========================================
# INTERACTIVE CLI DISPATCHER
# ==========================================

def display_testing_trophy() -> None:
    print(f"""
{BOLD}{MAGENTA}--- THE ENTERPRISE TESTING TROPHY MODEL ---{RESET}
      {YELLOW}  /\\  {RESET}       --> {YELLOW}End-to-End (E2E){RESET} (High confidence, high cost, low speed)
     {CYAN} /    \\ {RESET}
    {BLUE}/--------\\{RESET}     --> {BLUE}Integration Testing (RTL + MSW){RESET} (Sweet Spot: Best ROI)
   {GREEN}/----------\\{RESET}    --> {GREEN}Unit Testing (Reducers / Utilities){RESET} (Fastest execution)
  {DIM}------------{RESET}     --> Static Analysis (TypeScript, ESLint)
""")


def interactive_menu():
    print(f"\n{BOLD}{BLUE}======================================================{RESET}")
    print(f"{BOLD}{BLUE}  REACT ENTERPRISE TESTING STRATEGY LAB (BAB-09)      {RESET}")
    print(f"{BOLD}{BLUE}======================================================{RESET}")
    display_testing_trophy()

    while True:
        print(f"\n{BOLD}Menu Simulasi:{RESET}")
        print(f" {CYAN}[1]{RESET} Run Unit Test Suite (Pure Logic & Reducer)")
        print(f" {CYAN}[2]{RESET} Run Integration Test Suite (RTL Query Priority + MSW Interception)")
        print(f" {CYAN}[3]{RESET} Run E2E Test Suite (Playwright Headless Flow)")
        print(f" {CYAN}[4]{RESET} Run Full Enterprise Regression Pipeline (All Layers)")
        print(f" {CYAN}[5]{RESET} Exit")

        choice = input(f"\n{BOLD}Pilih opsi [1-5]: {RESET}").strip()

        if choice == "1":
            runner = EnterpriseTestRunner()
            run_all_unit_tests(runner)
            runner.print_summary()
        elif choice == "2":
            runner = EnterpriseTestRunner()
            run_all_integration_tests(runner)
            runner.print_summary()
        elif choice == "3":
            runner = EnterpriseTestRunner()
            run_all_e2e_tests(runner)
            runner.print_summary()
        elif choice == "4":
            runner = EnterpriseTestRunner()
            run_all_unit_tests(runner)
            run_all_integration_tests(runner)
            run_all_e2e_tests(runner)
            runner.print_summary()
        elif choice == "5":
            print(f"{GREEN}Lab exercise selesai. Enterprise Testing Verified!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 1-5.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--ci":
        # Non-interactive CI mode
        runner = EnterpriseTestRunner()
        run_all_unit_tests(runner)
        run_all_integration_tests(runner)
        run_all_e2e_tests(runner)
        runner.print_summary()
        sys.exit(0 if runner.failed_tests == 0 else 1)
    else:
        interactive_menu()
