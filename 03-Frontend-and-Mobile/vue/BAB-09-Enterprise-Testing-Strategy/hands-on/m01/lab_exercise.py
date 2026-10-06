#!/usr/bin/env python3
"""
Enterprise Testing Strategy for Vue 3 - Simulation Lab (Vitest + Vue Test Utils + Playwright)
Modul: BAB-09-Enterprise-Testing-Strategy / Hands-on Lab M01
Bahasa: Python 3 (Runnable standalone simulation with ANSI terminal UI)
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

# ============================================================================
# ANSI Color Codes for Terminal Formatting
# ============================================================================
class TerminalColor:
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
    BG_GREEN = "\033[42m\033[30m"
    BG_RED = "\033[41m\033[97m"
    BG_BLUE = "\033[44m\033[97m"

C = TerminalColor

def banner() -> None:
    print(f"\n{C.CYAN}{C.BOLD}{'=' * 75}{C.RESET}")
    print(f"{C.MAGENTA}{C.BOLD}  ⚡ VUE 3 ENTERPRISE TESTING SUITE SIMULATOR (VITEST & VTU) ⚡{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'=' * 75}{C.RESET}")
    print(f"{C.WHITE}  Piramida Pengujian: Unit (Vitest) ➔ Komponen (VTU) ➔ E2E (Playwright){C.RESET}\n")

# ============================================================================
# Core Domain: Vue Component Mock & Test Harness Simulation
# ============================================================================
@dataclass
class VirtualDOMNode:
    tag: str
    props: Dict[str, Any] = field(default_factory=dict)
    text: str = ""
    children: List['VirtualDOMNode'] = field(default_factory=list)

@dataclass
class SimulatedVueComponent:
    name: str
    props: Dict[str, Any]
    data: Dict[str, Any]
    emits: List[str] = field(default_factory=list)
    emitted_events: Dict[str, List[Any]] = field(default_factory=dict)

    def trigger(self, event_name: str, payload: Any = None) -> None:
        if event_name not in self.emitted_events:
            self.emitted_events[event_name] = []
        self.emitted_events[event_name].append(payload)

    def render(self) -> VirtualDOMNode:
        items_count = self.data.get("cart_items_count", 0)
        is_checkout_active = self.data.get("can_checkout", False)
        return VirtualDOMNode(
            tag="div",
            props={"class": "order-summary-card", "data-testid": "order-card"},
            text=f"Total Items: {items_count}",
            children=[
                VirtualDOMNode(
                    tag="button",
                    props={
                        "data-testid": "checkout-btn",
                        "disabled": not is_checkout_active
                    },
                    text="Proses Pembayaran"
                ),
                VirtualDOMNode(
                    tag="span",
                    props={"class": "badge-status"},
                    text="Siap Checkout" if is_checkout_active else "Keranjang Kosong"
                )
            ]
        )

class VueTestUtilsWrapper:
    """Simulasi Vue Test Utils Wrapper: mount() & shallowMount()"""
    def __init__(self, component: SimulatedVueComponent):
        self.vm = component
        self.vdom = component.render()

    def find(self, selector: str) -> Optional[VirtualDOMNode]:
        def recursive_search(node: VirtualDOMNode) -> Optional[VirtualDOMNode]:
            if selector.startswith("[data-testid='") and selector.endswith("']"):
                testid = selector[14:-2]
                if node.props.get("data-testid") == testid:
                    return node
            elif selector.startswith("."):
                css_class = selector[1:]
                if css_class in node.props.get("class", "").split():
                    return node
            for child in node.children:
                res = recursive_search(child)
                if res:
                    return res
            return None
        return recursive_search(self.vdom)

    def trigger(self, event_name: str, payload: Any = None) -> None:
        self.vm.trigger(event_name, payload)
        self.vdom = self.vm.render()

    def emitted(self) -> Dict[str, List[Any]]:
        return self.vm.emitted_events

# ============================================================================
# Enterprise Test Runner Engine
# ============================================================================
@dataclass
class TestCase:
    id: str
    tier: str  # Unit, Component, Integration, E2E
    description: str
    assertion_fn: Callable[[], bool]
    retry_count: int = 0
    max_retries: int = 2

class EnterpriseTestRunner:
    def __init__(self):
        self.test_cases: List[TestCase] = []
        self.results: Dict[str, Dict[str, Any]] = {}

    def register_test(self, test_case: TestCase) -> None:
        self.test_cases.append(test_case)

    def run_suite(self, interactive_delay: float = 0.04) -> bool:
        print(f"{C.BOLD}{C.YELLOW}❯ Menjalankan Vitest Runner (Enterprise Mode)...{C.RESET}\n")
        all_passed = True
        total = len(self.test_cases)
        passed = 0
        failed = 0

        for idx, test in enumerate(self.test_cases, 1):
            time.sleep(interactive_delay)
            attempt = 0
            success = False
            error_msg = ""

            while attempt <= test.max_retries and not success:
                try:
                    success = test.assertion_fn()
                    if not success:
                        error_msg = "AssertionError: expected conditions were not met"
                except Exception as ex:
                    error_msg = str(ex)
                    success = False

                if not success and attempt < test.max_retries:
                    attempt += 1
                    time.sleep(0.02)
                else:
                    break

            if success:
                passed += 1
                badge = f"{C.BG_GREEN} PASS {C.RESET}"
                tier_badge = f"{C.CYAN}[{test.tier}]{C.RESET}"
                retry_info = f" {C.YELLOW}(flaky resolved: retry {attempt}){C.RESET}" if attempt > 0 else ""
                print(f" {badge} {tier_badge} {test.description}{retry_info}")
            else:
                failed += 1
                all_passed = False
                badge = f"{C.BG_RED} FAIL {C.RESET}"
                tier_badge = f"{C.RED}[{test.tier}]{C.RESET}"
                print(f" {badge} {tier_badge} {test.description}")
                print(f"       {C.RED}└─ Detail: {error_msg}{C.RESET}")

        print(f"\n{C.BOLD}{'=' * 75}{C.RESET}")
        summary_color = C.GREEN if failed == 0 else C.RED
        print(f"{summary_color}{C.BOLD}Test Files : 1 passed (1 total){C.RESET}")
        print(f"{summary_color}{C.BOLD}Tests      : {passed} passed, {failed} failed, {total} total{C.RESET}")
        print(f"{C.DIM}Duration   : ~{total * 0.05:.2f}s | Snapshots: 4 written, 0 obsolete{C.RESET}\n")
        return all_passed

# ============================================================================
# Interactive Simulation Modules
# ============================================================================
def create_enterprise_test_suite() -> EnterpriseTestRunner:
    runner = EnterpriseTestRunner()

    # 1. Pure Unit: Pinia Store / Composables
    def test_pinia_auth_store():
        user_state = {"token": None, "role": "guest"}
        def login_action(user: str, role: str):
            user_state["token"] = f"jwt_mock_{user}"
            user_state["role"] = role
        login_action("alex", "admin")
        return user_state["token"] is not None and user_state["role"] == "admin"

    runner.register_test(TestCase(
        id="UT-01",
        tier="Unit",
        description="useAuthStore(): mutasi state token & role setelah action login() sukses",
        assertion_fn=test_pinia_auth_store
    ))

    # 2. Pure Unit: Enterprise Currency Filter Formatter
    def test_currency_formatter():
        def format_idr(amount: float) -> str:
            return f"Rp {int(amount):,}".replace(",", ".")
        return format_idr(150000.0) == "Rp 150.000"

    runner.register_test(TestCase(
        id="UT-02",
        tier="Unit",
        description="formatCurrency(): memformat bilangan bulat ke format Rupiah standar",
        assertion_fn=test_currency_formatter
    ))

    # 3. Component Test: Vue Test Utils mount & props
    def test_component_mount_and_props():
        comp = SimulatedVueComponent(
            name="OrderSummary",
            props={"discountRate": 0.1},
            data={"cart_items_count": 3, "can_checkout": True}
        )
        wrapper = VueTestUtilsWrapper(comp)
        card_node = wrapper.find("[data-testid='order-card']")
        return card_node is not None and "Total Items: 3" in card_node.text

    runner.register_test(TestCase(
        id="CT-01",
        tier="Component",
        description="<OrderSummary />: me-render data-testid='order-card' dengan kalkulasi props benar",
        assertion_fn=test_component_mount_and_props
    ))

    # 4. Component Test: Event Emission & Trigger
    def test_component_button_event_trigger():
        comp = SimulatedVueComponent(
            name="OrderSummary",
            props={},
            data={"cart_items_count": 2, "can_checkout": True}
        )
        wrapper = VueTestUtilsWrapper(comp)
        wrapper.trigger("submit-checkout", {"orderId": "ORD-9912"})
        emitted = wrapper.emitted()
        return "submit-checkout" in emitted and emitted["submit-checkout"][0]["orderId"] == "ORD-9912"

    runner.register_test(TestCase(
        id="CT-02",
        tier="Component",
        description="<OrderSummary />: wrapper.trigger() memancarkan custom event 'submit-checkout'",
        assertion_fn=test_component_button_event_trigger
    ))

    # 5. Integration Test: API Mocking via MSW Pattern
    def test_msw_network_mocking():
        class MockServer:
            def request(self, endpoint: str):
                if endpoint == "/api/v1/user/profile":
                    return {"status": 200, "data": {"name": "Citra", "verified": True}}
                return {"status": 404, "data": None}
        server = MockServer()
        resp = server.request("/api/v1/user/profile")
        return resp["status"] == 200 and resp["data"]["verified"] is True

    runner.register_test(TestCase(
        id="IT-01",
        tier="Integration",
        description="MSW Mock Service Worker: mencegat HTTP fetch dan mengembalikan stub JSON valid",
        assertion_fn=test_msw_network_mocking
    ))

    # 6. E2E Test: Playwright Smoke Flow with Flakiness Resilience
    flaky_state = {"attempt": 0}
    def test_playwright_e2e_flow():
        flaky_state["attempt"] += 1
        # Simulasikan flaky network jitter pada attempt pertama
        if flaky_state["attempt"] == 1:
            return False
        return True

    runner.register_test(TestCase(
        id="E2E-01",
        tier="E2E",
        description="Playwright E2E: User navigasi ➔ login ➔ tambah barang ➔ checkout (auto-retry)",
        assertion_fn=test_playwright_e2e_flow,
        max_retries=2
    ))

    return runner

def show_testing_pyramid() -> None:
    print(f"\n{C.BOLD}{C.CYAN}--- PIRAMIDA STRATEGI PENGUJIAN ENTERPRISE (VUE 3) ---{C.RESET}")
    print(f"""
          {C.RED}/\\
         /  \\         {C.BOLD}E2E Playwright / Cypress (~10%){C.RESET}
        / E2E\\        {C.DIM}Fokus: Alur bisnis kritis ujung-ke-ujung, multi-browser{C.RESET}
       /------\\
      /        \\      {C.YELLOW}Integration Tests & MSW (~20%){C.RESET}
     / INTEGR.  \\     {C.DIM}Fokus: Kontrak API mock, integrasi Router + Pinia{C.RESET}
    /------------\\
   /              \\   {C.GREEN}Unit & Component Tests: Vitest + VTU (~70%){C.RESET}
  / UNIT & COMPONENT\\ {C.DIM}Fokus: Kecepatan tinggi (millisecond), isolasi fungsi, logic{C.RESET}
 /___________________\\
    """)

def interactive_cli():
    banner()
    show_testing_pyramid()

    print(f"{C.WHITE}{C.BOLD}Pilihan Mode Simulasi:{C.RESET}")
    print(f"  {C.CYAN}1.{C.RESET} Jalankan Seluruh Test Suite (Vitest CI Mode)")
    print(f"  {C.CYAN}2.{C.RESET} Simulasi Mount Component & VTU Event Triggering")
    print(f"  {C.CYAN}3.{C.RESET} Analisis Flaky Test & Mitigation Retry Strategy")
    print(f"  {C.CYAN}4.{C.RESET} Jalankan Validasi Otomatis & Exit\n")

    # If executed non-interactively or stdin is piped, auto run option 1
    if not sys.stdin.isatty():
        print(f"{C.DIM}[Non-interactive environment terdeteksi. Menjalankan test suite otomatis...]{C.RESET}\n")
        runner = create_enterprise_test_suite()
        success = runner.run_suite(interactive_delay=0.01)
        sys.exit(0 if success else 1)

    choice = input(f"{C.BOLD}{C.YELLOW}Pilih opsi (1-4) [Default: 1]: {C.RESET}").strip()
    if choice in ("1", ""):
        runner = create_enterprise_test_suite()
        runner.run_suite()
    elif choice == "2":
        print(f"\n{C.BOLD}{C.MAGENTA}=== SIMULASI VUE TEST UTILS (SHALLOW MOUNT & EMIT) ==={C.RESET}")
        comp = SimulatedVueComponent(
            name="EnterpriseCheckoutModal",
            props={"vatRate": 0.11},
            data={"cart_items_count": 5, "can_checkout": True}
        )
        wrapper = VueTestUtilsWrapper(comp)
        print(f"{C.GREEN}✔ Wrapper berhasil diinisialisasi untuk <{comp.name} />{C.RESET}")
        btn = wrapper.find("[data-testid='checkout-btn']")
        print(f"  Node ditemukan: tag={btn.tag}, disabled={btn.props.get('disabled')}")
        print(f"  Trigger event: 'click'")
        wrapper.trigger("payment-submitted", {"amount": 2500000, "gateway": "QRIS"})
        print(f"{C.CYAN}  Emitted Events: {wrapper.emitted()}{C.RESET}")
        print(f"{C.GREEN}{C.BOLD}✔ Component Test Assertion PASSED!{C.RESET}\n")
    elif choice == "3":
        print(f"\n{C.BOLD}{C.YELLOW}=== DEMO FLAKY TEST RESILIENCE DENGAN RETRY ENGINE ==={C.RESET}")
        print(f"{C.WHITE}Menyimulasikan race-condition pada network call E2E...{C.RESET}")
        attempt = 1
        while attempt <= 3:
            time.sleep(0.3)
            if attempt < 3:
                print(f"  {C.RED}✖ Attempt {attempt}: Timeout menunggu selektor locator('.success-toast'){C.RESET}")
                attempt += 1
            else:
                print(f"  {C.GREEN}✔ Attempt {attempt}: Locator ditemukan! Toleransi flakiness berhasil diatasi.{C.RESET}")
                break
        print(f"\n{C.BOLD}{C.GREEN}✔ Enterprise Rule: Selalu gunakan web-first assertions (expect(locator).toBeVisible()){C.RESET}\n")
    elif choice == "4":
        runner = create_enterprise_test_suite()
        runner.run_suite(interactive_delay=0.01)
        sys.exit(0)
    else:
        print(f"{C.RED}Pilihan tidak dikenal. Menjalankan default suite.{C.RESET}")
        runner = create_enterprise_test_suite()
        runner.run_suite()

if __name__ == "__main__":
    interactive_cli()
