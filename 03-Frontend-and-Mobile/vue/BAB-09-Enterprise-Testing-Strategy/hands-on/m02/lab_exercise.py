#!/usr/bin/env python3
"""
Lab Exercise: Enterprise Testing Strategy for Vue 3 Production Apps
Topic: BAB-09 - Enterprise Testing Strategy (Vitest, MSW, Pinia, Playwright)
Architecture: Multi-Tier Testing Pipeline (Unit, Component, Store, Contract/MSW, E2E)
"""

import sys
import time
import random
from typing import Callable, List, Dict, Any

# ANSI Color Codes for Terminal UI
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"


class AssertionFailed(Exception):
    pass


class VueTestUtilsMock:
    """Simulates @vue/test-utils Component Mounting & Reactive DOM state."""
    def __init__(self, component_name: str, props: Dict[str, Any] = None):
        self.component_name = component_name
        self.props = props or {}
        self.emitted_events: Dict[str, List[Any]] = {}
        self.dom_tree: Dict[str, str] = {
            "button.submit": "Submit Order",
            "span.price": f"${self.props.get('price', 0):.2f}",
            "div.status": "idle"
        }

    def trigger(self, selector: str, event_name: str, payload: Any = None):
        if selector not in self.dom_tree:
            raise AssertionFailed(f"DOM Node '{selector}' not found in {self.component_name} wrapper!")
        
        if event_name == "click" and selector == "button.submit":
            self.dom_tree["div.status"] = "processing"
            self.emitted_events.setdefault("order-submit", []).append(payload or {"status": "success"})
            self.dom_tree["div.status"] = "completed"

    def find(self, selector: str) -> str:
        if selector not in self.dom_tree:
            raise AssertionFailed(f"Selector '{selector}' not found in rendered DOM template.")
        return self.dom_tree[selector]


class PiniaStoreMock:
    """Simulates Enterprise Pinia State Management & Actions testing."""
    def __init__(self):
        self.state = {
            "user": {"id": "usr_99", "role": "admin", "token": "jwt-token-xyz"},
            "cart": [],
            "checkout_status": "IDLE"
        }

    def add_to_cart(self, item: Dict[str, Any]):
        self.state["cart"].append(item)

    def checkout(self, msw_client: "MSWMockEngine") -> bool:
        self.state["checkout_status"] = "PENDING"
        resp = msw_client.dispatch_request("POST", "/api/v1/checkout", {"items": self.state["cart"]})
        if resp.get("status") == 200:
            self.state["checkout_status"] = "SUCCESS"
            self.state["cart"].clear()
            return True
        self.state["checkout_status"] = "FAILED"
        return False


class MSWMockEngine:
    """Simulates Mock Service Worker (MSW) Network Level Mocking."""
    def __init__(self):
        self.routes: Dict[str, Callable] = {}
        self.intercepted_logs: List[str] = []

    def register(self, method: str, endpoint: str, handler: Callable):
        self.routes[f"{method.upper()} {endpoint}"] = handler

    def dispatch_request(self, method: str, endpoint: str, body: Any = None) -> Dict[str, Any]:
        key = f"{method.upper()} {endpoint}"
        self.intercepted_logs.append(f"[MSW Intercept] {key} (Payload: {len(str(body))} bytes)")
        if key in self.routes:
            return self.routes[key](body)
        return {"status": 404, "body": {"error": "Mock Route Not Found"}}


class PlaywrightE2ESimulator:
    """Simulates Headless Chromium E2E Testing with Visual Snapshots."""
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.current_path = "/"
        self.network_idle = True

    def goto(self, path: str):
        self.current_path = path
        self.network_idle = True

    def wait_for_selector(self, selector: str, timeout_ms: int = 3000) -> bool:
        time.sleep(0.08)
        return True

    def take_screenshot_hash(self) -> str:
        # Generates deterministic visual regression baseline hash
        return f"sha256_{hash(self.current_path + '_vue_v3') & 0xffffffff:08x}"


class TestRunnerEngine:
    """Industrial Test Runner with ANSI Reports and Metrics."""
    def __init__(self):
        self.tests: List[Dict[str, Any]] = []

    def register_test(self, suite: str, name: str, fn: Callable):
        self.tests.append({"suite": suite, "name": name, "fn": fn})

    def run_suite(self, target_suite: str = None) -> bool:
        selected = [t for t in self.tests if target_suite is None or t["suite"].lower() == target_suite.lower()]
        if not selected:
            print(f"{YELLOW}[WARN] No tests matched filter: {target_suite}{RESET}")
            return False

        print(f"\n{BOLD}{BG_BLUE}  VITEST & PLAYWRIGHT ENTERPRISE HARNESS v3.2.0  {RESET}")
        print(f"{CYAN}Running {len(selected)} enterprise verification tests...{RESET}\n")

        passed = 0
        failed = 0
        start_time = time.time()

        for idx, item in enumerate(selected, 1):
            print(f"{DIM}[{idx:02d}/{len(selected):02d}]{RESET} {BOLD}{item['suite']}{RESET} > {item['name']} ... ", end="", flush=True)
            t0 = time.time()
            try:
                item["fn"]()
                dur = (time.time() - t0) * 1000
                print(f"{GREEN}PASS{RESET} {DIM}({dur:.1f}ms){RESET}")
                passed += 1
            except Exception as e:
                dur = (time.time() - t0) * 1000
                print(f"{RED}FAIL{RESET} {DIM}({dur:.1f}ms){RESET}")
                print(f"      {RED}Error: {e}{RESET}")
                failed += 1

        total_time = time.time() - start_time
        print(f"\n{DIM}{'='*60}{RESET}")
        print(f"{BOLD}Test Suites Summary:{RESET}")
        color = GREEN if failed == 0 else RED
        print(f"Tests:    {color}{passed} passed{RESET}, {RED if failed else ''}{failed} failed{RESET}, {len(selected)} total")
        print(f"Duration: {total_time:.2f}s")
        print(f"{DIM}{'='*60}{RESET}\n")
        return failed == 0


def build_enterprise_harness() -> TestRunnerEngine:
    runner = TestRunnerEngine()

    # 1. Component Unit Testing (Vue Test Utils)
    def test_vue_order_component_mount():
        wrapper = VueTestUtilsMock("OrderCheckout.vue", {"price": 149.99})
        price_text = wrapper.find("span.price")
        if price_text != "$149.99":
            raise AssertionFailed(f"Expected price '$149.99', got '{price_text}'")

    def test_vue_order_component_reactivity():
        wrapper = VueTestUtilsMock("OrderCheckout.vue", {"price": 50.0})
        wrapper.trigger("button.submit", "click", {"sku": "VUE-BOOK-01"})
        status = wrapper.find("div.status")
        if status != "completed":
            raise AssertionFailed(f"Expected status 'completed', received '{status}'")
        if "order-submit" not in wrapper.emitted_events:
            raise AssertionFailed("Custom event 'order-submit' was not emitted by component")

    # 2. Pinia State Management
    def test_pinia_mutation_and_action():
        store = PiniaStoreMock()
        store.add_to_cart({"id": "sku_101", "name": "Enterprise Vue License", "price": 499.00})
        if len(store.state["cart"]) != 1:
            raise AssertionFailed("Pinia cart state did not register item addition")

    # 3. Contract / MSW Mock Testing
    def test_msw_network_interception_checkout():
        msw = MSWMockEngine()
        msw.register("POST", "/api/v1/checkout", lambda body: {"status": 200, "body": {"transactionId": "tx_9981"}})
        
        store = PiniaStoreMock()
        store.add_to_cart({"id": "p1", "qty": 2})
        ok = store.checkout(msw)
        if not ok or store.state["checkout_status"] != "SUCCESS":
            raise AssertionFailed(f"Store checkout flow failed under MSW. Status: {store.state['checkout_status']}")
        if len(msw.intercepted_logs) == 0:
            raise AssertionFailed("MSW failed to intercept the network call!")

    # 4. Playwright End-to-End Simulation
    def test_playwright_e2e_critical_path():
        browser = PlaywrightE2ESimulator("http://localhost:5173")
        browser.goto("/checkout/summary")
        if not browser.wait_for_selector("button.confirm-payment"):
            raise AssertionFailed("Timeout waiting for confirm payment selector")
        snapshot_hash = browser.take_screenshot_hash()
        if not snapshot_hash.startswith("sha256_"):
            raise AssertionFailed(f"Invalid visual screenshot token generated: {snapshot_hash}")

    runner.register_test("Unit:VueTestUtils", "Mount and render reactive DOM props", test_vue_order_component_mount)
    runner.register_test("Unit:VueTestUtils", "Trigger user click events & assert emitted events", test_vue_order_component_reactivity)
    runner.register_test("Store:Pinia", "Mutate state & verify reactive store subscriptions", test_pinia_mutation_and_action)
    runner.register_test("Contract:MSW", "Mock network boundary /api/v1/checkout via Service Worker", test_msw_network_interception_checkout)
    runner.register_test("E2E:Playwright", "Headless browser flow & visual baseline hash check", test_playwright_e2e_critical_path)
    return runner


def print_interactive_menu():
    print(f"\n{BOLD}{CYAN}=== ENTERPRISE VUE 3 TESTING BENCHMARK LAB ==={RESET}")
    print(f"{CYAN}1.{RESET} Run All Enterprise Test Suites (Unit, Component, Store, MSW, E2E)")
    print(f"{CYAN}2.{RESET} Run Component Unit Suite (@vue/test-utils + Vitest)")
    print(f"{CYAN}3.{RESET} Run Pinia Store & Actions Suite")
    print(f"{CYAN}4.{RESET} Run MSW Network Boundary Contract Suite")
    print(f"{CYAN}5.{RESET} Run Playwright Headless E2E Simulation")
    print(f"{CYAN}6.{RESET} Print Architecture Coverage Matrix (NYC/C8)")
    print(f"{CYAN}0.{RESET} Exit Lab Runner")
    print(f"{CYAN}-----------------------------------------------{RESET}")


def display_coverage_report():
    print(f"\n{BOLD}{BLUE}================ CODE COVERAGE MATRIX (Vitest / v8 engine) ================{RESET}")
    print(f"{BOLD}{'File / Layer':<35} {'% Stmts':<10} {'% Branch':<10} {'% Funcs':<10} {'% Lines':<10}{RESET}")
    print(f"{DIM}{'-'*75}{RESET}")
    rows = [
        ("src/components/OrderCheckout.vue", "98.2%", "94.1%", "100.0%", "98.0%"),
        ("src/stores/orderStore.ts",         "100.0%", "92.0%", "100.0%", "100.0%"),
        ("src/mocks/handlers.ts (MSW)",      "95.4%", "88.9%", "93.3%",  "95.1%"),
        ("src/composables/useTelemetry.ts",  "91.7%", "85.0%", "90.0%",  "91.7%"),
        ("e2e/flows/checkout.spec.ts",        "100.0%", "100.0%", "100.0%", "100.0%"),
    ]
    for filename, stmt, branch, funcs, lines in rows:
        print(f"{CYAN}{filename:<35}{RESET} {GREEN}{stmt:<10}{RESET} {GREEN}{branch:<10}{RESET} {GREEN}{funcs:<10}{RESET} {GREEN}{lines:<10}{RESET}")
    print(f"{DIM}{'-'*75}{RESET}")
    print(f"{BOLD}All files overall coverage:{RESET} {GREEN}97.06%{RESET} (Threshold required: >90%)\n")


def main():
    harness = build_enterprise_harness()

    # If run in non-interactive batch mode (e.g. CI/CD or piped stdin)
    if not sys.stdin.isatty():
        print(f"{BOLD}{MAGENTA}[CI Mode Detected]{RESET} Executing full test matrix non-interactively...")
        success = harness.run_suite(None)
        display_coverage_report()
        sys.exit(0 if success else 1)

    while True:
        print_interactive_menu()
        try:
            choice = input(f"{BOLD}Select an option [0-6]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Terminated by user.{RESET}")
            break

        if choice == "1":
            harness.run_suite(None)
        elif choice == "2":
            harness.run_suite("Unit:VueTestUtils")
        elif choice == "3":
            harness.run_suite("Store:Pinia")
        elif choice == "4":
            harness.run_suite("Contract:MSW")
        elif choice == "5":
            harness.run_suite("E2E:Playwright")
        elif choice == "6":
            display_coverage_report()
        elif choice == "0":
            print(f"{GREEN}Lab session completed. Exiting...{RESET}")
            break
        else:
            print(f"{RED}[!] Invalid selection. Please choose 0 to 6.{RESET}")


if __name__ == "__main__":
    main()
