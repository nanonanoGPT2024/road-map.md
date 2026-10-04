#!/usr/bin/env python3
"""
Lab Hands-on: Component Primitives & Headless UI Architecture
Category: 03-Frontend-and-Mobile | Chapter: 05 - Deep Dive

Deskripsi:
Simulasi arsitektur Headless UI dan Component Primitives pada terminal.
Memisahkan state logic, state machine, focus management, dan kepatuhan WAI-ARIA
secara decoupled dari layer presentasi/rendering (Prop Getters Pattern).
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional
import sys
import time

# --- ANSI Formatting Constants ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BG_BLUE = "\033[44m"
BG_GRAY = "\033[100m"

# --- Domain & Accessibility (WAI-ARIA) Enums ---
class KeyCode(Enum):
    ARROW_DOWN = "ArrowDown"
    ARROW_UP = "ArrowUp"
    ENTER = "Enter"
    ESCAPE = "Escape"
    HOME = "Home"
    END = "End"
    TAB = "Tab"


@dataclass
class OptionItem:
    id: str
    label: str
    value: Any
    disabled: bool = False


# ============================================================================
# HEADLESS PRIMITIVE: STATE MACHINE & PROP GETTERS
# ============================================================================
class HeadlessSelectPrimitive:
    """
    Primitive non-visual headless component.
    Mengelola state transitions, keyboard navigation (roving tabindex/activedescendant),
    dan menghasilkan property contract (Prop Getters) sesuai standar WAI-ARIA.
    """

    def __init__(
        self,
        items: List[OptionItem],
        default_selected: Optional[OptionItem] = None,
        on_change: Optional[Callable[[OptionItem], None]] = None,
    ):
        self.items = items
        self.is_open: bool = False
        self.selected_item: Optional[OptionItem] = default_selected
        self.highlighted_index: int = -1
        self.on_change = on_change
        self._sync_initial_highlight()

    def _sync_initial_highlight(self) -> None:
        if self.selected_item and self.selected_item in self.items:
            self.highlighted_index = self.items.index(self.selected_item)
        else:
            self.highlighted_index = -1

    def _find_next_index(self, start: int, step: int) -> int:
        """Helper internal untuk melewati disabled options saat navigasi keyboard."""
        total = len(self.items)
        if total == 0:
            return -1

        curr = (start + step) % total
        traversed = 0
        while traversed < total:
            if not self.items[curr].disabled:
                return curr
            curr = (curr + step) % total
            traversed += 1
        return start

    def dispatch_keyboard_event(self, key: KeyCode) -> None:
        """
        State Machine reducer untuk event keyboard berdasarkan spesifikasi
        W3C WAI-ARIA Combobox / Select Pattern.
        """
        if not self.is_open:
            if key in (KeyCode.ARROW_DOWN, KeyCode.ARROW_UP, KeyCode.ENTER):
                self.is_open = True
                if self.highlighted_index == -1:
                    self.highlighted_index = self._find_next_index(-1, 1)
            return

        # Ketika Menu sedang Terbuka (Open)
        if key == KeyCode.ARROW_DOWN:
            self.highlighted_index = self._find_next_index(self.highlighted_index, 1)
        elif key == KeyCode.ARROW_UP:
            self.highlighted_index = self._find_next_index(self.highlighted_index, -1)
        elif key == KeyCode.HOME:
            self.highlighted_index = self._find_next_index(-1, 1)
        elif key == KeyCode.END:
            self.highlighted_index = self._find_next_index(len(self.items), -1)
        elif key == KeyCode.ENTER:
            if 0 <= self.highlighted_index < len(self.items):
                target = self.items[self.highlighted_index]
                if not target.disabled:
                    self.selected_item = target
                    self.is_open = False
                    if self.on_change:
                        self.on_change(target)
        elif key in (KeyCode.ESCAPE, KeyCode.TAB):
            self.is_open = False

    # --- Prop Getters (Inversion of Control for UI Adapters) ---

    def get_trigger_props(self) -> Dict[str, Any]:
        """Mengembalikan accessibility props untuk tombol/trigger pembuka."""
        activedescendant = None
        if self.is_open and 0 <= self.highlighted_index < len(self.items):
            activedescendant = f"option-{self.items[self.highlighted_index].id}"

        return {
            "role": "combobox",
            "aria-haspopup": "listbox",
            "aria-expanded": self.is_open,
            "aria-activedescendant": activedescendant,
            "aria-controls": "headless-listbox-content",
            "tabindex": 0,
        }

    def get_menu_props(self) -> Dict[str, Any]:
        """Mengembalikan accessibility props untuk container popup menu."""
        return {
            "id": "headless-listbox-content",
            "role": "listbox",
            "aria-orientation": "vertical",
            "tabindex": -1,
            "hidden": not self.is_open,
        }

    def get_item_props(self, index: int) -> Dict[str, Any]:
        """Mengembalikan state dan accessibility props untuk setiap opsi."""
        item = self.items[index]
        is_highlighted = self.highlighted_index == index
        is_selected = self.selected_item is not None and self.selected_item.id == item.id

        return {
            "id": f"option-{item.id}",
            "role": "option",
            "aria-selected": is_selected,
            "aria-disabled": item.disabled,
            "is_highlighted": is_highlighted,
            "is_selected": is_selected,
            "data-state": "highlighted" if is_highlighted else ("selected" if is_selected else "idle"),
        }


# ============================================================================
# RENDERER IMPLEMENTATIONS (SEPARATION OF CONCERNS)
# ============================================================================
class TerminalComponentRenderer:
    """Renderer A: Design System Visual Theme (Clean UI)"""

    @staticmethod
    def render(primitive: HeadlessSelectPrimitive, width: int = 42) -> None:
        trigger_props = primitive.get_trigger_props()
        label = primitive.selected_item.label if primitive.selected_item else "Select option..."

        print(f"\n{BOLD}{CYAN}=== DESIGN SYSTEM: THEME 'NEO-MODERN' ==={RESET}")

        # Render Trigger Button
        border_color = GREEN if trigger_props["aria-expanded"] else CYAN
        expand_symbol = "▲" if trigger_props["aria-expanded"] else "▼"
        print(f"{border_color}┌{'─' * (width - 2)}┐{RESET}")
        print(f"{border_color}│{RESET} {BOLD}{label:<{width - 6}}{RESET} {border_color}{expand_symbol} │{RESET}")
        print(f"{border_color}└{'─' * (width - 2)}┘{RESET}")

        # Render Dropdown Box jika Menu Terbuka
        if trigger_props["aria-expanded"]:
            print(f"{DIM}  ┌{'─' * (width - 6)}┐{RESET}")
            for idx, item in enumerate(primitive.items):
                props = primitive.get_item_props(idx)

                # Format indikator status
                if props["aria-disabled"]:
                    line = f"{DIM}{item.label} (disabled){RESET}"
                    prefix = "  "
                elif props["is_highlighted"]:
                    line = f"{BG_GRAY}{BOLD} {item.label} {RESET}"
                    prefix = f"{GREEN}▶{RESET} "
                elif props["is_selected"]:
                    line = f"{MAGENTA}{item.label} ✓{RESET}"
                    prefix = "  "
                else:
                    line = item.label
                    prefix = "  "

                # Padding formatting
                print(f"{DIM}  │{RESET} {prefix}{line:<{width - 9}} {DIM}│{RESET}")
            print(f"{DIM}  └{'─' * (width - 6)}┘{RESET}")


class AriaA11yInspectorRenderer:
    """Renderer B: Accessibility & Virtual DOM Inspector (Headless Contract Debugger)"""

    @staticmethod
    def render(primitive: HeadlessSelectPrimitive) -> None:
        trigger_props = primitive.get_trigger_props()
        menu_props = primitive.get_menu_props()

        print(f"\n{BOLD}{YELLOW}=== ACCESSIBILITY & STATE TREE INSPECTOR ==={RESET}")
        print(f"{MAGENTA}<DOM::TriggerNode>{RESET}")
        for k, v in trigger_props.items():
            print(f"  {DIM}attr:{RESET} {CYAN}{k}{RESET} = {GREEN}\"{v}\"{RESET}")

        if not menu_props["hidden"]:
            print(f"{MAGENTA}<DOM::ListNode>{RESET}")
            for k, v in menu_props.items():
                print(f"    {DIM}attr:{RESET} {CYAN}{k}{RESET} = {GREEN}\"{v}\"{RESET}")

            print(f"    {DIM}<!-- Child Option Nodes -->{RESET}")
            for idx, item in enumerate(primitive.items):
                item_props = primitive.get_item_props(idx)
                print(f"    {MAGENTA}<DOM::OptionNode label=\"{item.label}\">{RESET}")
                for k, v in item_props.items():
                    print(f"      {DIM}attr:{RESET} {CYAN}{k}{RESET} = {GREEN}\"{v}\"{RESET}")


# ============================================================================
# EXECUTION SIMULATOR & TEST HARNESS
# ============================================================================
def run_simulation() -> None:
    # 1. Inisialisasi Kumpulan Data Primitives
    options = [
        OptionItem("tokyo", "Tokyo (HND)", "HND"),
        OptionItem("osaka", "Osaka (KIX)", "KIX"),
        OptionItem("kyoto", "Kyoto Rail Center (NA)", "UKY", disabled=True),
        OptionItem("sapporo", "Sapporo Chitose (CTS)", "CTS"),
        OptionItem("fukuoka", "Fukuoka (FUK)", "FUK"),
    ]

    selected_history = []

    def on_selection_callback(item: OptionItem) -> None:
        selected_history.append(item.label)

    # 2. Instansiasi Headless Logic (Inversion of Control)
    combobox = HeadlessSelectPrimitive(
        items=options,
        default_selected=options[0],
        on_change=on_selection_callback,
    )

    # 3. Urutan Action Keyboard Simulation
    actions = [
        ("Buka Dropdown dengan KeyCode.ENTER", KeyCode.ENTER),
        ("Navigasi ke bawah (Pindah highlight ke Osaka)", KeyCode.ARROW_DOWN),
        ("Navigasi ke bawah (Lewati Kyoto yang DISABLED menuju Sapporo)", KeyCode.ARROW_DOWN),
        ("Navigasi ke bawah menuju Fukuoka", KeyCode.ARROW_DOWN),
        ("Pilih Opsi dengan KeyCode.ENTER (Commit selection & close)", KeyCode.ENTER),
        ("Buka kembali Dropdown dengan KeyCode.ARROW_DOWN", KeyCode.ARROW_DOWN),
        ("Tutup Dropdown tanpa memilih dengan KeyCode.ESCAPE", KeyCode.ESCAPE),
    ]

    print(f"{BOLD}{GREEN}Laboratorium: Headless Component & WAI-ARIA Architecture{RESET}")
    print(f"{DIM}Menguji State Machine, Accessible Prop Injection, dan Separation of UI.{RESET}\n")

    for step_num, (desc, key) in enumerate(actions, start=1):
        print(f"\n{BOLD}------------------------------------------------------------{RESET}")
        print(f"Step {step_num}: {YELLOW}{desc}{RESET} [Event: {CYAN}{key.value}{RESET}]")
        combobox.dispatch_keyboard_event(key)

        # Multi-Renderer Consumer Membuktikan Arsitektur Headless
        TerminalComponentRenderer.render(combobox)
        AriaA11yInspectorRenderer.render(combobox)

        time.sleep(0.1)

    print(f"\n{BOLD}{GREEN}=== SIMULASI BERHASIL LENGKAP ==={RESET}")
    print(f"Audit Selection Dispatch Callback History: {selected_history}")
    print(
        f"{DIM}Konsep Terverifikasi: Decoupled State Machine, WAI-ARIA Dynamic Attributes, "
        f"Disabled-item Traversals, Multiple Isolated UI Renderers.{RESET}\n"
    )


if __name__ == "__main__":
    run_simulation()
    sys.exit(0)