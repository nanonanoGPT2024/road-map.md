#!/usr/bin/env python3
"""
Lab Exercise: SwiftUI <-> UIKit / AppKit Interoperability Simulator
BAB-07: Interoperabilitas Ekosistem Bridge (UIKit & AppKit)

Simulasi siklus hidup UIViewRepresentable, UIViewControllerRepresentable,
Coordinator Delegate Pattern, dan UIHostingController.
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# --- ANSI Terminal Styling ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BLUE = "\033[34m"
BG_BLUE = "\033[44;97m"


def print_banner(title: str) -> None:
    border = "=" * 64
    print(f"\n{CYAN}{BOLD}{border}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{border}{RESET}\n")


def log_step(component: str, method: str, detail: str, color: str = GREEN) -> None:
    print(f"  {BOLD}[{component}]{RESET} -> {color}{method}(){RESET}: {detail}")


# --- Mocking UIKit Primitives ---
class MockUISearchBar:
    """Representasi komponen imperatif UIKit UISearchBar."""

    def __init__(self) -> None:
        self.text: str = ""
        self.placeholder: str = "Search..."
        self.delegate: Optional[Any] = None
        self.is_active: bool = False

    def simulate_user_typing(self, input_text: str) -> None:
        self.text = input_text
        if self.delegate and hasattr(self.delegate, "search_bar_text_did_change"):
            self.delegate.search_bar_text_did_change(self, input_text)


# --- SwiftUI Protocol Abstraction: UIViewRepresentable ---
class SearchBarCoordinator:
    """
    Coordinator bertindak sebagai jembatan (Delegate/Target-Action)
    antara UIKit event model dan SwiftUI State Binding.
    """

    def __init__(self, on_change: Callable[[str], None]) -> None:
        self.on_change = on_change
        log_step("Coordinator", "init", "Coordinator dialokasikan untuk bridging delegate.", MAGENTA)

    def search_bar_text_did_change(self, bar: MockUISearchBar, new_text: str) -> None:
        log_step(
            "Coordinator",
            "searchBar(_:textDidChange:)",
            f"Event delegate UIKit ditangkap -> Meneruskan nilai '{new_text}' ke SwiftUI Binding.",
            YELLOW,
        )
        self.on_change(new_text)


class SearchBarRepresentable:
    """
    Implementasi protokol UIViewRepresentable di SwiftUI.
    """

    def __init__(self, query_binding_get: Callable[[], str], query_binding_set: Callable[[str], None]) -> None:
        self.get_query = query_binding_get
        self.set_query = query_binding_set
        self.coordinator: Optional[SearchBarCoordinator] = None

    def make_coordinator(self) -> SearchBarCoordinator:
        log_step("UIViewRepresentable", "makeCoordinator", "Membuat instance Coordinator penghubung.", CYAN)
        self.coordinator = SearchBarCoordinator(self.set_query)
        return self.coordinator

    def make_ui_view(self, coordinator: SearchBarCoordinator) -> MockUISearchBar:
        log_step("UIViewRepresentable", "makeUIView", "Instansiasi view UIKit murni (UISearchBar).", GREEN)
        search_bar = MockUISearchBar()
        search_bar.delegate = coordinator
        search_bar.placeholder = "Cari modul arsitektur..."
        return search_bar

    def update_ui_view(self, ui_view: MockUISearchBar, query: str) -> None:
        log_step(
            "UIViewRepresentable",
            "updateUIView",
            f"Sinkronisasi State SwiftUI -> UIKit view. Current Text: '{query}'",
            BLUE,
        )
        if ui_view.text != query:
            ui_view.text = query

    def dismantle_ui_view(self, ui_view: MockUISearchBar, coordinator: SearchBarCoordinator) -> None:
        log_step(
            "UIViewRepresentable",
            "dismantleUIView",
            "Teardown & melepaskan referensi delegate/listener untuk mencegah memory leak.",
            RED,
        )
        ui_view.delegate = None


# --- Mocking UIHostingController (UIKit host SwiftUI) ---
class UIHostingController:
    """
    Jembatan sebaliknya: Menanam SwiftUI View deklaratif
    ke dalam UIViewController / UINavigationController imperatif UIKit.
    """

    def __init__(self, root_view_name: str) -> None:
        self.root_view_name = root_view_name
        self.view_loaded = False
        log_step("UIHostingController", "init(rootView:)", f"Membungkus deklaratif View <{root_view_name}>", MAGENTA)

    def load_view(self) -> None:
        self.view_loaded = True
        log_step(
            "UIHostingController",
            "viewDidLoad",
            f"Layout rendering pipeline SwiftUI dievaluasi ke UIKit render tree.",
            GREEN,
        )


# --- State Management & Simulation Engine ---
@dataclass
class SwiftUIState:
    search_query: str = ""
    render_count: int = 0


class InteropEngine:
    def __init__(self) -> None:
        self.state = SwiftUIState()
        self.representable: Optional[SearchBarRepresentable] = None
        self.coordinator: Optional[SearchBarCoordinator] = None
        self.ui_view: Optional[MockUISearchBar] = None
        self.hosting_vc: Optional[UIHostingController] = None

    def mount_bridge(self) -> None:
        print_banner("1. SIKLUS HIDUP VIEW INITIALIZATION (SwiftUI -> UIKit)")
        self.representable = SearchBarRepresentable(
            query_binding_get=lambda: self.state.search_query,
            query_binding_set=self._on_swiftui_binding_updated,
        )
        # Langkah 1: Coordinator
        self.coordinator = self.representable.make_coordinator()
        # Langkah 2: makeUIView
        self.ui_view = self.representable.make_ui_view(self.coordinator)
        # Langkah 3: updateUIView awal
        self.representable.update_ui_view(self.ui_view, self.state.search_query)
        self.state.render_count += 1
        print(f"\n{GREEN}{BOLD}[STATUS]{RESET} Bridged UISearchBar sukses ter-mount di render hierarchy.\n")

    def _on_swiftui_binding_updated(self, new_val: str) -> None:
        self.state.search_query = new_val
        self.state.render_count += 1
        print(f"    {BOLD}⚡ SwiftUI @Binding didUpdate:{RESET} State internal = '{self.state.search_query}'")

    def simulate_uikit_event(self, typed_value: str) -> None:
        print_banner(f"2. EVENT STREAM DARI UIKIT (User Mengetik: '{typed_value}')")
        if not self.ui_view:
            print(f"{RED}Error: Bridge belum diinisialisasi!{RESET}")
            return
        self.ui_view.simulate_user_typing(typed_value)
        # Re-render check
        print(f"  {CYAN}SwiftUI View Body Re-evaluated (Render Pass #{self.state.render_count}){RESET}")
        self.representable.update_ui_view(self.ui_view, self.state.search_query)

    def simulate_swiftui_state_change(self, programmatic_text: str) -> None:
        print_banner(f"3. SINGLE SOURCE OF TRUTH (SwiftUI Mutasi State: '{programmatic_text}')")
        print(f"  SwiftUI ViewModel mengubah state @State -> updateUIView dipanggil secara reaktif.")
        self.state.search_query = programmatic_text
        self.state.render_count += 1
        if self.representable and self.ui_view:
            self.representable.update_ui_view(self.ui_view, self.state.search_query)
        print(f"    UIKit UISearchBar text sekarang: '{self.ui_view.text}'")

    def simulate_reverse_hosting(self) -> None:
        print_banner("4. REVERSE INTEGRATION: UIHostingController (SwiftUI didalam UIKit)")
        self.hosting_vc = UIHostingController("SwiftUIProfileDashboardView")
        self.hosting_vc.load_view()
        print(f"  {GREEN}ViewController UIKit kini dapat mem-push SwiftUI View via UINavigationController.{RESET}")

    def teardown_bridge(self) -> None:
        print_banner("5. TEARDOWN SIKLUS HIDUP (dismantleUIView)")
        if self.representable and self.ui_view and self.coordinator:
            self.representable.dismantle_ui_view(self.ui_view, self.coordinator)
            self.ui_view = None
            self.coordinator = None
            self.representable = None
            print(f"\n{RED}{BOLD}[TEARDOWN COMPLETE]{RESET} Sumber daya UIKit dibersihkan secara aman.\n")


def interactive_menu() -> None:
    engine = InteropEngine()
    engine.mount_bridge()

    menu = f"""
{BOLD}{CYAN}--- PILIHAN SIMULASI INTERAKTIF BRIDGE ---{RESET}
1. Simulasi User Mengetik di UIKit UISearchBar (Delegate -> Coordinator -> SwiftUI Binding)
2. Simulasi State Mutasi Deklaratif SwiftUI (State -> updateUIView -> UIKit View)
3. Uji Reverse Bridging (UIHostingController dalam UIKit Hierarchy)
4. Teardown & Bersihkan Bridge (dismantleUIView)
5. Jalankan Automated Full Lifecycle Test
6. Keluar
"""

    while True:
        print(menu)
        choice = input(f"{BOLD}Pilih opsi (1-6): {RESET}").strip()
        if choice == "1":
            text = input("Ketikkan input search: ").strip() or "SwiftUI Interop"
            engine.simulate_uikit_event(text)
        elif choice == "2":
            text = input("Masukkan teks state baru: ").strip() or "Programmatic Query"
            engine.simulate_swiftui_state_change(text)
        elif choice == "3":
            engine.simulate_reverse_hosting()
        elif choice == "4":
            engine.teardown_bridge()
            break
        elif choice == "5":
            engine.simulate_uikit_event("Combine Framework")
            time.sleep(0.3)
            engine.simulate_swiftui_state_change("UIKit Navigation Stack")
            time.sleep(0.3)
            engine.simulate_reverse_hosting()
            time.sleep(0.3)
            engine.teardown_bridge()
            break
        elif choice == "6":
            print(f"{YELLOW}Keluar dari simulator.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Mode non-interaktif untuk CI/verifikasi otomatis
        sim = InteropEngine()
        sim.mount_bridge()
        sim.simulate_uikit_event("AsyncSequence")
        sim.simulate_swiftui_state_change("Observation Framework")
        sim.simulate_reverse_hosting()
        sim.teardown_bridge()
    else:
        try:
            interactive_menu()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Simulasi dihentikan.{RESET}")
