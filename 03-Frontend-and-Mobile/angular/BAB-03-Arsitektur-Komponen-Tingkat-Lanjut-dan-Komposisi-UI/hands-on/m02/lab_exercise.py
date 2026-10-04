#!/usr/bin/env python3
"""
Lab Hands-on: Arsitektur Komponen Tingkat Lanjut & Komposisi UI (Angular Deep Dive)
Simulasi Mesin Runtime Angular:
  1. Hierarchical Component Tree & View Container Management.
  2. Multi-slot Content Projection (ng-content select="...").
  3. Dynamic Component Instantiation (ViewContainerRef.createComponent).
  4. Change Detection Engine (Default vs OnPush Dirty Checking & markForCheck traversal).
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import time
import sys

# ANSI Colors untuk output visual terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


class ChangeDetectionStrategy(Enum):
    DEFAULT = "Default (CheckAlways)"
    ON_PUSH = "OnPush (CheckOnceOrDirty)"


class ProjectedContent:
    """Merepresentasikan node template yang diproyeksikan melalui ng-content."""
    def __init__(self, slot: str, content: str):
        self.slot = slot
        self.content = content


class ChangeDetectorRef:
    """Abstraksi API Angular ChangeDetectorRef untuk manipulasi siklus CD."""
    def __init__(self, component: 'Component'):
        self._component = component

    def mark_for_check(self) -> None:
        """Menandai path dari node saat ini ke root sebagai dirty (OnPush requirement)."""
        curr: Optional['Component'] = self._component
        while curr:
            curr.is_dirty = True
            curr = curr.parent


class Component:
    """
    Abstraksi Komponen Angular tingkat lanjut yang mendukung lifecycle,
    proyeksi konten multi-slot, dan strategi deteksi perubahan.
    """
    def __init__(self, name: str, strategy: ChangeDetectionStrategy = ChangeDetectionStrategy.DEFAULT):
        self.name = name
        self.strategy = strategy
        self.parent: Optional['Component'] = None
        self.children: List['Component'] = []
        self.inputs: Dict[str, Any] = {}
        self.prev_inputs: Dict[str, Any] = {}
        self.is_dirty: bool = True
        self.projected_slots: Dict[str, List[str]] = {}
        self.cdr = ChangeDetectorRef(self)
        self.check_count: int = 0

    def add_child(self, child: 'Component') -> 'Component':
        child.parent = self
        self.children.append(child)
        return child

    def set_input(self, key: str, value: Any) -> None:
        """Memperbarui input bindings (@Input) dan mengecek kesetaraan referensi."""
        if self.inputs.get(key) is not value:
            self.inputs[key] = value
            # OnPush mengecek perubahan via kesetaraan referensial (Object.is)
            self.is_dirty = True

    def project(self, slot: str, content: str) -> None:
        """Simulasi <ng-content select="[slot]">."""
        if slot not in self.projected_slots:
            self.projected_slots[slot] = []
        self.projected_slots[slot].append(content)

    def render(self) -> str:
        """Simulasi evaluasi template dan rendering slot proyeksi."""
        slots_str = ", ".join(f"[{k}]: '{' '.join(v)}'" for k, v in self.projected_slots.items())
        inputs_str = ", ".join(f"{k}={v}" for k, v in self.inputs.items())
        return f"{self.name}(Inputs: {{{inputs_str}}}, Slots: {{{slots_str}}})"


class ViewContainerRef:
    """Simulasi ViewContainerRef untuk instansiasi komponen dinamis secara imperatif."""
    def __init__(self, host: Component):
        self.host = host

    def create_component(self, name: str, strategy: ChangeDetectionStrategy) -> Component:
        dynamic_comp = Component(name=name, strategy=strategy)
        self.host.add_child(dynamic_comp)
        return dynamic_comp


class AngularEngine:
    """Engine runtime untuk eksekusi Change Detection pass."""
    def __init__(self, root: Component):
        self.root = root
        self.total_checks_performed = 0

    def tick(self) -> None:
        """Satu siklus lengkap Change Detection dari Root ke Leaf."""
        self.total_checks_performed = 0
        print(f"\n{Color.BOLD}{Color.CYAN}=== Memulai Siklus Change Detection (ApplicationRef.tick()) ==={Color.RESET}")
        self._traverse_and_check(self.root, depth=0)
        print(f"{Color.BOLD}Siklus Selesai. Total Node Diperiksa: {self.total_checks_performed}{Color.RESET}\n")

    def _traverse_and_check(self, comp: Component, depth: int) -> None:
        indent = "  " * depth
        should_check = False

        if comp.strategy == ChangeDetectionStrategy.DEFAULT:
            should_check = True
        elif comp.strategy == ChangeDetectionStrategy.ON_PUSH:
            # OnPush hanya dicek jika ditandai dirty (input ref berubah atau markForCheck dipanggil)
            if comp.is_dirty:
                should_check = True

        if should_check:
            comp.check_count += 1
            self.total_checks_performed += 1
            state_label = f"{Color.GREEN}[CHECKED]{Color.RESET}"
            comp.is_dirty = False  # Reset dirty flag setelah inspeksi template
        else:
            state_label = f"{Color.GRAY}[SKIPPED - Clean OnPush]{Color.RESET}"

        print(f"{indent}├─ {comp.name} {Color.YELLOW}({comp.strategy.value}){Color.RESET} -> {state_label}")
        if comp.projected_slots:
            for slot, contents in comp.projected_slots.items():
                print(f"{indent}│   └─ ng-content [{slot}] => {' '.join(contents)}")

        # Lanjutkan traversal ke seluruh child nodes
        for child in comp.children:
            self._traverse_and_check(child, depth + 1)


def build_app_tree() -> tuple[Component, Component, Component, Component]:
    """
    Membangun arsitektur komponen bertingkat:
    AppRoot (Default)
      ├── HeaderComponent (OnPush)
      │     └── Multi-slot content projection
      ├── DashboardComponent (OnPush)
      │     ├── CardWidgetComponent (OnPush)
      │     └── FeedWidgetComponent (Default)
      └── DynamicHostComponent (Default)
    """
    root = Component("AppRoot", ChangeDetectionStrategy.DEFAULT)
    
    # 1. Header dengan Content Projection
    header = Component("HeaderComponent", ChangeDetectionStrategy.ON_PUSH)
    header.project("brand", "Acme Cloud Portal")
    header.project("actions", "<button>Logout</button>")
    root.add_child(header)

    # 2. Dashboard Subtree
    dashboard = Component("DashboardComponent", ChangeDetectionStrategy.ON_PUSH)
    dashboard.set_input("theme", "dark")
    root.add_child(dashboard)

    card = Component("CardWidgetComponent", ChangeDetectionStrategy.ON_PUSH)
    card.set_input("metrics", [10, 20, 30])
    dashboard.add_child(card)

    feed = Component("FeedWidgetComponent", ChangeDetectionStrategy.DEFAULT)
    dashboard.add_child(feed)

    # 3. Dynamic Host
    dyn_host = Component("DynamicHostComponent", ChangeDetectionStrategy.DEFAULT)
    root.add_child(dyn_host)

    return root, header, card, dyn_host


def main():
    print(f"{Color.BOLD}{Color.MAGENTA}============================================================{Color.RESET}")
    print(f"{Color.BOLD}{Color.MAGENTA}   LAB: ADVANCED COMPONENT ARCHITECTURE & COMPOSITION       {Color.RESET}")
    print(f"{Color.BOLD}{Color.MAGENTA}============================================================{Color.RESET}")

    root, header, card, dyn_host = build_app_tree()
    engine = AngularEngine(root)

    # STEP 1: Initial Tick (Seluruh pohon komponen diperiksa untuk render pertama)
    print(f"\n{Color.BOLD}[SKENARIO 1: First Render Pass]{Color.RESET}")
    engine.tick()

    # STEP 2: Tick kedua tanpa ada perubahan state
    print(f"{Color.BOLD}[SKENARIO 2: No-op Tick (Membuktikan OnPush Subtree Pruning)]{Color.RESET}")
    engine.tick()

    # STEP 3: Mutasi Data Objek Langsung (In-place Mutation - Anti Pattern di OnPush)
    print(f"{Color.BOLD}[SKENARIO 3: In-Place Object Mutation (Metrics Mutation)]{Color.RESET}")
    print(f"{Color.GRAY}Memodifikasi array 'metrics' secara in-place tanpa mengubah referensi...{Color.RESET}")
    card.inputs["metrics"].append(40) # Referensi list tetap sama
    engine.tick()
    print(f"{Color.RED}>> Terbukti: CardWidgetComponent TIDAK diperiksa karena referensi pointer tidak berubah!{Color.RESET}")

    # STEP 4: Immutable Input Update (Praktik Terbaik Angular OnPush)
    print(f"\n{Color.BOLD}[SKENARIO 4: Immutable Input Update (Reference Change)]{Color.RESET}")
    print(f"{Color.GRAY}Memperbarui 'metrics' dengan list referensi baru (Spread syntax clone)...{Color.RESET}")
    card.set_input("metrics", [10, 20, 30, 40, 50])
    engine.tick()

    # STEP 5: Imperative markForCheck() dari Deep Nested Asynchronous Event
    print(f"{Color.BOLD}[SKENARIO 5: Manual markForCheck() via ChangeDetectorRef]{Color.RESET}")
    print(f"{Color.GRAY}Header menerima Webhook Event async dan memicu cdr.mark_for_check()...{Color.RESET}")
    header.project("brand", "Acme Cloud Portal [SYNCED]")
    header.cdr.mark_for_check()
    engine.tick()

    # STEP 6: Dynamic Component Instantiation via ViewContainerRef
    print(f"{Color.BOLD}[SKENARIO 6: Dynamic Component Creation (ViewContainerRef)]{Color.RESET}")
    print(f"{Color.GRAY}Menginstansiasi ModalComponent secara runtime di dalam DynamicHostComponent...{Color.RESET}")
    vcr = ViewContainerRef(dyn_host)
    dynamic_modal = vcr.create_component("ModalOverlayComponent", ChangeDetectionStrategy.ON_PUSH)
    dynamic_modal.set_input("backdrop", True)
    dynamic_modal.project("body", "<p>Critical Session Expiring</p>")
    engine.tick()

    # Rekapitulasi Efisiensi
    print(f"{Color.BOLD}{Color.CYAN}=== REKAPITULASI PEMERIKSAAN SIKLUS HIDUP ==={Color.RESET}")
    def display_metrics(c: Component, depth=0):
        print(f"{'  ' * depth}• {c.name:25} Checked: {Color.GREEN}{c.check_count}x{Color.RESET} ({c.strategy.value})")
        for ch in c.children:
            display_metrics(ch, depth + 1)

    display_metrics(root)
    print(f"\n{Color.BOLD}{Color.GREEN}Lab Selesai: Konsep arsitektur komponen Angular sukses diverifikasi.{Color.RESET}")


if __name__ == "__main__":
    main()