#!/usr/bin/env python3
"""
SwiftUI Navigation Engine & Structural Routing Simulator
BAB-04: NavigationStack, NavigationPath, Type-Safe Destinations & Deep Linking
"""

import sys
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


# --- ANSI Colors for Terminal UI ---
class Style:
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
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


# --- Hashable / Codable Destination Types (SwiftUI Representation) ---
@dataclass(frozen=True)
class ProductRoute:
    item_id: str
    category: str


@dataclass(frozen=True)
class UserProfileRoute:
    username: str
    badge_level: int


@dataclass(frozen=True)
class SettingsRoute:
    section: str


# --- SwiftUI Navigation Engine Core ---
class NavigationPath:
    """Simulates SwiftUI's type-erased NavigationPath backing stack."""

    def __init__(self):
        self._elements: List[Any] = []

    def append(self, value: Any) -> None:
        self._elements.append(value)

    def remove_last(self, count: int = 1) -> None:
        if count > len(self._elements):
            self._elements.clear()
        else:
            self._elements = self._elements[:-count]

    def count(self) -> int:
        return len(self._elements)

    def is_empty(self) -> bool:
        return len(self._elements) == 0

    def elements(self) -> List[Any]:
        return list(self._elements)

    def to_json(self) -> str:
        """Simulates state restoration via Codable representation."""
        serializable = []
        for elem in self._elements:
            serializable.append({
                "type": elem.__class__.__name__,
                "data": elem.__dict__
            })
        return json.dumps(serializable, indent=2)


class NavigationDestinationRegistry:
    """Simulates type-safe .navigationDestination(for: Destination.self) view builders."""

    def __init__(self):
        self._resolvers: Dict[type, Any] = {}

    def register(self, target_type: type, render_fn):
        self._resolvers[target_type] = render_fn

    def resolve(self, item: Any) -> str:
        render_fn = self._resolvers.get(type(item))
        if render_fn:
            return render_fn(item)
        return f"[Unknown Destination: {type(item).__name__}]"


class NavigationStackCoordinator:
    """Manages the lifecycle of views, sheets, and routing state."""

    def __init__(self, root_title: str = "HomeView"):
        self.root_title = root_title
        self.path = NavigationPath()
        self.registry = NavigationDestinationRegistry()
        self.active_sheet: Optional[str] = None
        self._setup_destinations()

    def _setup_destinations(self):
        self.registry.register(
            ProductRoute,
            lambda p: f"{Style.CYAN}📦 ProductDetailView(id='{p.item_id}', category='{p.category}'){Style.RESET}"
        )
        self.registry.register(
            UserProfileRoute,
            lambda u: f"{Style.GREEN}👤 UserProfileView(user='@{u.username}', level={u.badge_level}){Style.RESET}"
        )
        self.registry.register(
            SettingsRoute,
            lambda s: f"{Style.YELLOW}⚙️  SettingsSectionView(section='{s.section.upper()}'){Style.RESET}"
        )

    def push(self, destination: Any) -> None:
        self.path.append(destination)

    def pop(self) -> Optional[Any]:
        if not self.path.is_empty():
            item = self.path.elements()[-1]
            self.path.remove_last(1)
            return item
        return None

    def pop_to_root(self) -> None:
        self.path.remove_last(self.path.count())

    def present_sheet(self, sheet_name: str) -> None:
        self.active_sheet = sheet_name

    def dismiss_sheet(self) -> None:
        self.active_sheet = None

    def handle_deep_link(self, url: str) -> bool:
        """Parses URL schemes into programmatic navigation path mutations."""
        parts = url.strip("/").split("/")
        if not parts or parts[0] != "swiftui-app":
            return False

        self.pop_to_root()
        i = 1
        while i < len(parts):
            seg = parts[i]
            if seg == "product" and i + 2 < len(parts):
                self.push(ProductRoute(item_id=parts[i + 1], category=parts[i + 2]))
                i += 3
            elif seg == "user" and i + 2 < len(parts):
                self.push(UserProfileRoute(username=parts[i + 1], badge_level=int(parts[i + 2])))
                i += 3
            elif seg == "settings" and i + 1 < len(parts):
                self.push(SettingsRoute(section=parts[i + 1]))
                i += 2
            else:
                break
        return True

    def render_stack(self) -> str:
        lines = []
        lines.append(f"{Style.BOLD}{Style.WHITE}┌── [NavigationStack Root] ──────────────────────┐{Style.RESET}")
        lines.append(f"│  {Style.MAGENTA}📱 {self.root_title} (Depth 0){Style.RESET}")
        
        elements = self.path.elements()
        for idx, item in enumerate(elements, start=1):
            view_rendered = self.registry.resolve(item)
            prefix = "├──" if idx < len(elements) else "└──"
            lines.append(f"│  {prefix} {Style.BOLD}[Depth {idx}]{Style.RESET} {view_rendered}")

        if not elements:
            lines.append(f"│  {Style.DIM}(No pushed destinations on stack){Style.RESET}")

        lines.append(f"{Style.BOLD}{Style.WHITE}└───────────────────────────────────────────────┘{Style.RESET}")

        if self.active_sheet:
            lines.append(f"{Style.BG_MAGENTA}{Style.WHITE} [MODAL SHEET] 🗂️  {self.active_sheet} (isPresented: True) {Style.RESET}")

        return "\n".join(lines)


# --- Interactive CLI & Demo Execution ---
def run_interactive_demo():
    coordinator = NavigationStackCoordinator("DashboardView")

    def print_header():
        print(f"\n{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} === SwiftUI 4.0+ Navigation Engine Simulator === {Style.RESET}")
        print(f"{Style.DIM}Testing NavigationPath, .navigationDestination, Deep Linking & Pop-to-Root{Style.RESET}\n")

    def print_menu():
        print(f"{Style.BOLD}Commands:{Style.RESET}")
        print(f"  [{Style.CYAN}1{Style.RESET}] Push Product View        [{Style.CYAN}2{Style.RESET}] Push User Profile")
        print(f"  [{Style.CYAN}3{Style.RESET}] Push Settings Section    [{Style.YELLOW}4{Style.RESET}] Pop View (Back)")
        print(f"  [{Style.RED}5{Style.RESET}] Pop to Root              [{Style.MAGENTA}6{Style.RESET}] Toggle Modal Sheet")
        print(f"  [{Style.BLUE}7{Style.RESET}] Inject Deep Link         [{Style.GREEN}8{Style.RESET}] Dump JSON State")
        print(f"  [{Style.WHITE}9{Style.RESET}] Run Automated Test Suite [{Style.WHITE}0{Style.RESET}] Exit")

    # If non-interactive or invoked with tests
    if "--test" in sys.argv or not sys.stdin.isatty():
        run_automated_tests(coordinator)
        return

    while True:
        print_header()
        print(coordinator.render_stack())
        print()
        print_menu()
        try:
            choice = input(f"\n{Style.BOLD}Select action [0-9]: {Style.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting simulator.")
            break

        if choice == "0":
            print(f"{Style.GREEN}Session terminated.{Style.RESET}")
            break
        elif choice == "1":
            item_id = f"PROD-{int(time.time()) % 1000}"
            coordinator.push(ProductRoute(item_id=item_id, category="Electronics"))
        elif choice == "2":
            coordinator.push(UserProfileRoute(username="swift_dev", badge_level=42))
        elif choice == "3":
            coordinator.push(SettingsRoute(section="Notifications"))
        elif choice == "4":
            popped = coordinator.pop()
            if popped:
                print(f"{Style.YELLOW}Popped: {popped}{Style.RESET}")
            else:
                print(f"{Style.RED}Stack is already at root!{Style.RESET}")
        elif choice == "5":
            coordinator.pop_to_root()
            print(f"{Style.RED}Popped back to Root.{Style.RESET}")
        elif choice == "6":
            if coordinator.active_sheet:
                coordinator.dismiss_sheet()
            else:
                coordinator.present_sheet("OAuthLoginSheetView")
        elif choice == "7":
            test_url = "swiftui-app/product/ITEM-99/Books/settings/Security"
            coordinator.handle_deep_link(test_url)
            print(f"{Style.BLUE}Deep link applied: {test_url}{Style.RESET}")
        elif choice == "8":
            print(f"\n{Style.WHITE}{Style.BOLD}Serialized NavigationPath:{Style.RESET}")
            print(coordinator.path.to_json())
            input("\nPress Enter to continue...")
        elif choice == "9":
            run_automated_tests(coordinator)
            input("\nPress Enter to continue...")
        else:
            print(f"{Style.RED}Invalid option!{Style.RESET}")


def run_automated_tests(coordinator: NavigationStackCoordinator):
    print(f"\n{Style.BOLD}{Style.CYAN}--- Executing Automated Verification Suite ---{Style.RESET}")
    
    # Test 1: Push and Depth
    coordinator.pop_to_root()
    assert coordinator.path.count() == 0, "Root must have depth 0"
    coordinator.push(ProductRoute(item_id="P1", category="Hardware"))
    coordinator.push(UserProfileRoute(username="alice", badge_level=1))
    assert coordinator.path.count() == 2, "Depth must be 2 after pushes"
    print(f"[{Style.GREEN}PASS{Style.RESET}] Push navigation elements verified (Depth = 2)")

    # Test 2: Serialized JSON state restoration
    json_state = coordinator.path.to_json()
    assert "ProductRoute" in json_state and "UserProfileRoute" in json_state
    print(f"[{Style.GREEN}PASS{Style.RESET}] Codable NavigationPath serialization verified")

    # Test 3: Deep Link Routing
    dl_success = coordinator.handle_deep_link("swiftui-app/product/A100/Cloud/settings/Privacy")
    assert dl_success and coordinator.path.count() == 2
    assert isinstance(coordinator.path.elements()[0], ProductRoute)
    assert isinstance(coordinator.path.elements()[1], SettingsRoute)
    print(f"[{Style.GREEN}PASS{Style.RESET}] Deep-linking route parsing verified")

    # Test 4: Pop to Root
    coordinator.pop_to_root()
    assert coordinator.path.count() == 0
    print(f"[{Style.GREEN}PASS{Style.RESET}] Programmatic Pop-to-Root verified")

    # Test 5: Modal Presentation
    coordinator.present_sheet("TermsOfServiceModal")
    assert coordinator.active_sheet == "TermsOfServiceModal"
    coordinator.dismiss_sheet()
    assert coordinator.active_sheet is None
    print(f"[{Style.GREEN}PASS{Style.RESET}] Modal Sheet lifecyle verified")

    print(f"{Style.BOLD}{Style.GREEN}>>> ALL 5 NAVIGATION ARCHITECTURE TESTS PASSED SUCCESSFULLY! <<<{Style.RESET}\n")


if __name__ == "__main__":
    run_interactive_demo()
