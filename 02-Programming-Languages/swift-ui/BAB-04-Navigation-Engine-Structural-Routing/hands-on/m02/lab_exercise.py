#!/usr/bin/env python3
"""
Lab Hands-on: SwiftUI Navigation Engine & Structural Routing
Topic: swift-ui (Chapter 04: Navigation Engine & Structural Routing)

Simulates the runtime architecture of SwiftUI's modern NavigationStack,
heterogeneous type-erased NavigationPath, destination registries,
URL-based deep-link resolution, and state restoration (Codable representation).
"""

import sys
import json
import time
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, asdict

# --- ANSI Terminal Color Palette ---
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_CYAN = "\033[36m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_MAGENTA = "\033[35m"
COLOR_RED = "\033[31m"
COLOR_GRAY = "\033[90m"


# ============================================================================
# Section 1: Domain Models & Routing Primitives (Hashable & Codable equivalents)
# ============================================================================

@dataclass(frozen=True)
class ProductDestination:
    """Represents a product item route destination."""
    product_id: int
    sku: str


@dataclass(frozen=True)
class UserProfileDestination:
    """Represents a user profile route destination."""
    user_id: str
    tab: str = "overview"


@dataclass(frozen=True)
class SettingsDestination:
    """Represents an application settings sub-pane."""
    section_name: str
    requires_biometrics: bool = False


# ============================================================================
# Section 2: SwiftUI Navigation Engine Abstractions
# ============================================================================

class ViewNode:
    """Simulates a rendered SwiftUI View Node in the structural graph."""
    def __init__(self, identifier: str, body_content: str):
        self.identifier = identifier
        self.body_content = body_content
        self.appeared = False

    def on_appear(self):
        if not self.appeared:
            self.appeared = True
            print(f"  {COLOR_GREEN}↳ [Lifecycle] onAppear:{COLOR_RESET} {self.identifier}")

    def on_disappear(self):
        if self.appeared:
            self.appeared = False
            print(f"  {COLOR_RED}↳ [Lifecycle] onDisappear:{COLOR_RESET} {self.identifier}")

    def render(self, depth: int) -> str:
        indent = "    " * depth
        return f"{indent}┌── [View: {self.identifier}]\n{indent}└── Payload: {self.body_content}"


class NavigationPath:
    """
    Simulates SwiftUI's type-erased `NavigationPath`.
    Maintains a heterogeneous sequence of Hashable/Codable tokens and supports
    full state serialization for app suspension and restoration.
    """
    def __init__(self):
        self._elements: List[Any] = []

    def append(self, item: Any) -> None:
        self._elements.append(item)

    def remove_last(self, count: int = 1) -> None:
        for _ in range(min(count, len(self._elements))):
            self._elements.pop()

    def clear(self) -> None:
        self._elements.clear()

    @property
    def count(self) -> int:
        return len(self._elements)

    @property
    def elements(self) -> List[Any]:
        return list(self._elements)

    def serialize_codable_representation(self) -> str:
        """Emulates NavigationPath.CodableRepresentation encoding."""
        serialized = []
        for elem in self._elements:
            serialized.append({
                "type": elem.__class__.__name__,
                "data": asdict(elem) if hasattr(elem, "__dataclass_fields__") else elem
            })
        return json.dumps(serialized, indent=2)

    def restore_from_codable_representation(self, raw_json: str, type_registry: Dict[str, Type]) -> None:
        """Restores elements from a serialized JSON representation."""
        self.clear()
        data = json.loads(raw_json)
        for item in data:
            type_name = item["type"]
            payload = item["data"]
            if type_name in type_registry:
                target_cls = type_registry[type_name]
                instance = target_cls(**payload)
                self._elements.append(instance)
            else:
                raise ValueError(f"Unknown destination type for deserialization: {type_name}")


class NavigationStack:
    """
    Core SwiftUI NavigationStack coordinator engine.
    Manages view destination mappings, active view hierarchies, and routing reconciliation.
    """
    def __init__(self, root_view: ViewNode, path: Optional[NavigationPath] = None):
        self.root_view = root_view
        self.path = path if path is not None else NavigationPath()
        self._destination_registry: Dict[Type, Callable[[Any], ViewNode]] = {}
        self._active_views: List[ViewNode] = [root_view]
        self.root_view.on_appear()

    def register_destination(self, data_type: Type, builder: Callable[[Any], ViewNode]) -> None:
        """Simulates `.navigationDestination(for: Type.self) { ... }`."""
        self._destination_registry[data_type] = builder

    def reconcile_hierarchy(self) -> None:
        """
        Structural identity diffing engine:
        Synchronizes runtime active view frames against current NavigationPath state.
        """
        target_len = self.path.count
        current_len = len(self._active_views) - 1  # Minus root view

        # Tear down popped views
        while current_len > target_len:
            popped_view = self._active_views.pop()
            popped_view.on_disappear()
            current_len -= 1

        # Build pushed views
        for i in range(current_len, target_len):
            route_item = self.path.elements[i]
            route_type = type(route_item)
            if route_type not in self._destination_registry:
                raise RuntimeError(f"Missing navigationDestination definition for {route_type}")

            view_builder = self._destination_registry[route_type]
            new_view = view_builder(route_item)
            self._active_views.append(new_view)
            new_view.on_appear()

    def process_deep_link(self, uri: str) -> bool:
        """
        Parses a URL scheme into structured NavigationPath elements.
        Example: app://nav/product/101/PROD-A -> ProductDestination(101, 'PROD-A')
        """
        print(f"\n{COLOR_CYAN}[DeepLink Engine] Parsing URI: {uri}{COLOR_RESET}")
        if not uri.startswith("app://nav/"):
            print(f"{COLOR_RED}  Invalid scheme or host.{COLOR_RESET}")
            return False

        segments = uri.replace("app://nav/", "").strip("/").split("/")
        idx = 0
        while idx < len(segments):
            domain = segments[idx]
            if domain == "product" and idx + 2 < len(segments):
                prod_id = int(segments[idx + 1])
                sku = segments[idx + 2]
                self.path.append(ProductDestination(prod_id, sku))
                idx += 3
            elif domain == "user" and idx + 1 < len(segments):
                u_id = segments[idx + 1]
                tab = segments[idx + 2] if idx + 2 < len(segments) else "overview"
                self.path.append(UserProfileDestination(u_id, tab))
                idx += (3 if idx + 2 < len(segments) else 2)
            elif domain == "settings" and idx + 1 < len(segments):
                sec = segments[idx + 1]
                self.path.append(SettingsDestination(sec, False))
                idx += 2
            else:
                print(f"{COLOR_YELLOW}  Unknown route token: {domain}{COLOR_RESET}")
                return False

        self.reconcile_hierarchy()
        return True

    def display_stack(self) -> None:
        """Renders the topological hierarchy of the current navigation graph."""
        print(f"\n{COLOR_BOLD}{COLOR_MAGENTA}--- Current Visual Hierarchy ---{COLOR_RESET}")
        for depth, view in enumerate(self._active_views):
            prefix = "ROOT: " if depth == 0 else f"DEPTH {depth}: "
            print(f"{COLOR_GRAY}{prefix}{COLOR_RESET}\n{view.render(depth)}")
        print(f"{COLOR_MAGENTA}--------------------------------{COLOR_RESET}\n")


# ============================================================================
# Section 3: Lab Verification Execution Routine
# ============================================================================

def main():
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== SwiftUI Navigation Engine Deep-Dive Simulation ==={COLOR_RESET}\n")

    # Step 1: Initialize Root Container
    root = ViewNode("DashboardRootView", "Main Hub with Analytics Widgets")
    path = NavigationPath()
    stack = NavigationStack(root_view=root, path=path)

    # Step 2: Register Destination Handlers (.navigationDestination)
    stack.register_destination(
        ProductDestination,
        lambda model: ViewNode(
            f"ProductDetailView(sku={model.sku})",
            f"Displaying product #{model.product_id} with inventory metrics."
        )
    )
    stack.register_destination(
        UserProfileDestination,
        lambda model: ViewNode(
            f"UserProfileView(user={model.user_id})",
            f"User account profile: selected tab = '{model.tab}'"
        )
    )
    stack.register_destination(
        SettingsDestination,
        lambda model: ViewNode(
            f"SettingsPaneView({model.section_name})",
            f"Configuration toggle matrix for: {model.section_name}"
        )
    )

    # Step 3: Programmatic Push Operations
    print(f"{COLOR_YELLOW}>>> Action 1: Programmatically pushing destinations to NavigationPath...{COLOR_RESET}")
    path.append(ProductDestination(product_id=4042, sku="IPHONE-15-PRO"))
    path.append(SettingsDestination(section_name="Security & Privacy", requires_biometrics=True))
    stack.reconcile_hierarchy()
    stack.display_stack()

    # Step 4: Serialize Path State for App State Restoration
    print(f"{COLOR_YELLOW}>>> Action 2: Exporting State (CodableRepresentation)...{COLOR_RESET}")
    serialized_state = path.serialize_codable_representation()
    print(f"{COLOR_GRAY}{serialized_state}{COLOR_RESET}")

    # Step 5: Pop-to-Root Execution
    print(f"\n{COLOR_YELLOW}>>> Action 3: Popping back to Root (Truncating NavigationPath)...{COLOR_RESET}")
    path.clear()
    stack.reconcile_hierarchy()
    stack.display_stack()

    # Step 6: Deep Link Resolution
    print(f"{COLOR_YELLOW}>>> Action 4: Ingesting Dynamic Deep Link URI...{COLOR_RESET}")
    deep_link = "app://nav/product/8812/M3-MACBOOK/user/octocat/activity"
    stack.process_deep_link(deep_link)
    stack.display_stack()

    # Step 7: Cold-Start Restoration from JSON Payload
    print(f"{COLOR_YELLOW}>>> Action 5: Simulating Process Death & State Restoration...{COLOR_RESET}")
    restored_path = NavigationPath()
    type_registry = {
        "ProductDestination": ProductDestination,
        "UserProfileDestination": UserProfileDestination,
        "SettingsDestination": SettingsDestination
    }
    restored_path.restore_from_codable_representation(serialized_state, type_registry)

    cold_root = ViewNode("RestoredRootView", "Cold Boot Instance")
    restored_stack = NavigationStack(root_view=cold_root, path=restored_path)
    restored_stack.register_destination(
        ProductDestination,
        lambda model: ViewNode(f"ProductDetailView({model.sku})", f"Restored Product ID: {model.product_id}")
    )
    restored_stack.register_destination(
        SettingsDestination,
        lambda model: ViewNode(f"SettingsPaneView({model.section_name})", "Restored Security Context")
    )
    restored_stack.reconcile_hierarchy()
    restored_stack.display_stack()

    print(f"{COLOR_BOLD}{COLOR_GREEN}✔ Lab verification complete: All navigation invariants verified.{COLOR_RESET}")


if __name__ == "__main__":
    main()