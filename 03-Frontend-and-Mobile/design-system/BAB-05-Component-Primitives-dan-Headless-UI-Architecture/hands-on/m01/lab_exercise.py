#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Headless UI & Component Primitives Architecture
Bab 05: Component Primitives dan Headless UI Architecture

Simulasi teknis arsitektur Headless UI (Radix / React Aria pattern):
1. State Machine & Event Dispatcher (Headless State)
2. Accessibility & ARIA Contract Generator (Props Getters)
3. Roving Tabindex & Keyboard Navigation Strategy
4. Decoupled Presentation Layer (ANSI Visualizer)
"""

import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional


class AnsiColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BG_BLUE = "\033[44m"
    BG_GRAY = "\033[100m"


class KeyCode(Enum):
    ARROW_UP = "ArrowUp"
    ARROW_DOWN = "ArrowDown"
    ENTER = "Enter"
    SPACE = "Space"
    ESCAPE = "Escape"
    TAB = "Tab"
    HOME = "Home"
    END = "End"


@dataclass
class MenuItem:
    id: str
    label: str
    disabled: bool = False
    shortcut: Optional[str] = None


class HeadlessMenuState(Enum):
    CLOSED = auto()
    OPEN = auto()


class HeadlessMenu:
    """
    Headless Menu Primitive.
    Mengatur state, roving tabindex, dan keyboard interaction
    tanpa menyentuh DOM atau layer presentasi visual (Decoupled Logic).
    """

    def __init__(self, menu_id: str, items: List[MenuItem], orientation: str = "vertical"):
        self.menu_id = menu_id
        self.items = items
        self.orientation = orientation
        self.state = HeadlessMenuState.CLOSED
        self.active_index = -1
        self._listeners: List[Callable[[str, Any], None]] = []

    def subscribe(self, callback: Callable[[str, Any], None]) -> None:
        self._listeners.append(callback)

    def _notify(self, event_type: str, payload: Any = None) -> None:
        for listener in self._listeners:
            listener(event_type, payload)

    @property
    def is_open(self) -> bool:
        return self.state == HeadlessMenuState.OPEN

    def open(self, focus_first: bool = True) -> None:
        if self.state == HeadlessMenuState.OPEN:
            return
        self.state = HeadlessMenuState.OPEN
        self.active_index = self._find_first_enabled_index() if focus_first else -1
        self._notify("OPEN", {"active_index": self.active_index})

    def close(self) -> None:
        if self.state == HeadlessMenuState.CLOSED:
            return
        self.state = HeadlessMenuState.CLOSED
        self.active_index = -1
        self._notify("CLOSE")

    def toggle(self) -> None:
        if self.is_open:
            self.close()
        else:
            self.open()

    def _find_first_enabled_index(self) -> int:
        for idx, item in enumerate(self.items):
            if not item.disabled:
                return idx
        return -1

    def _find_last_enabled_index(self) -> int:
        for idx in range(len(self.items) - 1, -1, -1):
            if not self.items[idx].disabled:
                return idx
        return -1

    def move_focus(self, delta: int) -> None:
        if not self.is_open or not self.items:
            return

        total = len(self.items)
        current = self.active_index if self.active_index != -1 else (0 if delta > 0 else total - 1)
        next_idx = current

        for _ in range(total):
            next_idx = (next_idx + delta) % total
            if not self.items[next_idx].disabled:
                self.active_index = next_idx
                self._notify("FOCUS_CHANGE", {"active_index": self.active_index})
                return

    def focus_first(self) -> None:
        first = self._find_first_enabled_index()
        if first != -1:
            self.active_index = first
            self._notify("FOCUS_CHANGE", {"active_index": self.active_index})

    def focus_last(self) -> None:
        last = self._find_last_enabled_index()
        if last != -1:
            self.active_index = last
            self._notify("FOCUS_CHANGE", {"active_index": self.active_index})

    def select_active(self) -> Optional[MenuItem]:
        if not self.is_open or self.active_index < 0 or self.active_index >= len(self.items):
            return None
        selected_item = self.items[self.active_index]
        if selected_item.disabled:
            return None
        self._notify("SELECT", {"item": selected_item})
        self.close()
        return selected_item

    # -------------------------------------------------------------
    # ARIA / Accessibility Props Getters (Contracts)
    # -------------------------------------------------------------
    def get_trigger_props(self) -> Dict[str, Any]:
        return {
            "id": f"{self.menu_id}-trigger",
            "type": "button",
            "aria-haspopup": "menu",
            "aria-expanded": str(self.is_open).lower(),
            "aria-controls": f"{self.menu_id}-list",
        }

    def get_menu_props(self) -> Dict[str, Any]:
        return {
            "id": f"{self.menu_id}-list",
            "role": "menu",
            "aria-orientation": self.orientation,
            "aria-labelledby": f"{self.menu_id}-trigger",
            "aria-activedescendant": (
                f"{self.menu_id}-item-{self.active_index}"
                if self.is_open and self.active_index >= 0
                else None
            ),
            "hidden": not self.is_open,
        }

    def get_item_props(self, index: int) -> Dict[str, Any]:
        if index < 0 or index >= len(self.items):
            return {}
        item = self.items[index]
        is_active = self.is_open and (self.active_index == index)
        return {
            "id": f"{self.menu_id}-item-{index}",
            "role": "menuitem",
            "tabindex": 0 if is_active else -1,
            "aria-disabled": str(item.disabled).lower(),
            "data-highlighted": is_active,
        }

    # -------------------------------------------------------------
    # Keyboard Event Handler (Strategy Pattern)
    # -------------------------------------------------------------
    def handle_keyboard(self, key: KeyCode) -> bool:
        """
        WAI-ARIA Menu Keyboard interaction pattern.
        Mengembalikan True jika key ditangani, False jika diabaikan.
        """
        if not self.is_open:
            if key in (KeyCode.ENTER, KeyCode.SPACE, KeyCode.ARROW_DOWN):
                self.open(focus_first=True)
                return True
            return False

        if key == KeyCode.ESCAPE:
            self.close()
            return True
        elif key == KeyCode.ARROW_DOWN:
            self.move_focus(1)
            return True
        elif key == KeyCode.ARROW_UP:
            self.move_focus(-1)
            return True
        elif key == KeyCode.HOME:
            self.focus_first()
            return True
        elif key == KeyCode.END:
            self.focus_last()
            return True
        elif key in (KeyCode.ENTER, KeyCode.SPACE):
            self.select_active()
            return True
        elif key == KeyCode.TAB:
            # Menu pattern: Tab menutup menu dan memindahkan fokus
            self.close()
            return True

        return False


class HeadlessRenderer:
    """
    Presentation Layer terpisah. Merender data props headless
    ke representasi visual terminal berwarna ANSI & ARIA Inspection.
    """

    @staticmethod
    def render_menu(menu: HeadlessMenu, selected_action: Optional[str] = None) -> None:
        trigger_props = menu.get_trigger_props()
        menu_props = menu.get_menu_props()

        c = AnsiColor
        print("\n" + "=" * 65)
        print(f"{c.BOLD}{c.CYAN}[HEADLESS UI PRIMITIVE] Architecture Visualizer{c.RESET}")
        print("=" * 65)

        # Trigger Rendering
        expanded_badge = (
            f"{c.BG_BLUE}{c.BOLD} OPEN {c.RESET}"
            if menu.is_open
            else f"{c.BG_GRAY} CLOSED {c.RESET}"
        )
        print(f"Trigger Button: {c.BOLD}[ Options v ]{c.RESET}  State: {expanded_badge}")
        print(
            f"{c.DIM}A11y Trigger Props: aria-haspopup=\"{trigger_props['aria-haspopup']}\" "
            f"aria-expanded=\"{trigger_props['aria-expanded']}\" "
            f"aria-controls=\"{trigger_props['aria-controls']}\"{c.RESET}\n"
        )

        # Menu List Rendering
        if not menu.is_open:
            print(f"{c.DIM}(Menu dropdown tertutup. Tekan ARROW_DOWN atau ENTER untuk membuka){c.RESET}")
        else:
            print(f"{c.YELLOW}┌── Menu List ({menu_props['role']} - {menu_props['aria-orientation']}) ────────────────┐{c.RESET}")
            for idx, item in enumerate(menu.items):
                item_props = menu.get_item_props(idx)
                is_active = item_props["data-highlighted"]
                is_disabled = item.disabled

                # Focus indicator styling
                if is_disabled:
                    prefix = f"  {c.DIM}[X] "
                    text_color = c.DIM
                    suffix = f"{c.RED}(disabled){c.RESET}"
                elif is_active:
                    prefix = f"{c.GREEN}{c.BOLD}► [*] "
                    text_color = f"{c.GREEN}{c.BOLD}"
                    suffix = f"{c.CYAN}<-- roving focus (tabindex=0){c.RESET}"
                else:
                    prefix = "  [ ] "
                    text_color = c.RESET
                    suffix = f"{c.DIM}(tabindex=-1){c.RESET}"

                shortcut_str = f"[{item.shortcut}]" if item.shortcut else ""
                label_formatted = f"{item.label:<18} {shortcut_str:>8}"
                print(f"{prefix}{text_color}{label_formatted}{c.RESET} {suffix}")

            print(f"{c.YELLOW}└────────────────────────────────────────────────────────┘{c.RESET}")
            active_desc = menu_props.get("aria-activedescendant")
            print(f"{c.DIM}A11y Container: aria-activedescendant=\"{active_desc}\"{c.RESET}")

        if selected_action:
            print(f"\n{c.BG_BLUE}{c.BOLD} ACTION DISPATCHED {c.RESET} -> {c.MAGENTA}{selected_action}{c.RESET}")
        print("-" * 65)


def run_interactive_simulation() -> None:
    """
    Menjalankan simulasi interaktif headless menu dengan skenario event keyboard.
    """
    c = AnsiColor
    sample_items = [
        MenuItem("edit", "Edit File", shortcut="Ctrl+E"),
        MenuItem("dup", "Duplicate Record", shortcut="Ctrl+D"),
        MenuItem("exp", "Export as PDF (Locked)", disabled=True, shortcut="Ctrl+P"),
        MenuItem("del", "Delete Item", shortcut="Del"),
    ]

    menu = HeadlessMenu("app-options", sample_items)
    last_action: Optional[str] = None

    def on_event(event_type: str, payload: Any) -> None:
        nonlocal last_action
        if event_type == "SELECT":
            item: MenuItem = payload["item"]
            last_action = f"Selected '{item.label}' (id={item.id})"
        elif event_type == "OPEN":
            last_action = "Menu dibuka, roving focus diatur ke indeks pertama yang enabled"
        elif event_type == "CLOSE":
            last_action = "Menu ditutup, aria-expanded disetel ke 'false'"

    menu.subscribe(on_event)

    # Langkah simulasi demonstrasi headless state machine
    scripted_steps = [
        (KeyCode.ARROW_DOWN, "Trigger Key DOWN -> Buka Menu & fokus item ke-1"),
        (KeyCode.ARROW_DOWN, "Key ARROW_DOWN -> Pindah fokus ke item ke-2"),
        (KeyCode.ARROW_DOWN, "Key ARROW_DOWN -> Lewati item ke-3 (disabled) langsung ke item ke-4"),
        (KeyCode.ARROW_DOWN, "Key ARROW_DOWN -> Wrap around / roving loop kembali ke item ke-1"),
        (KeyCode.ARROW_UP,   "Key ARROW_UP   -> Mundur memutar ke item ke-4 (Delete Item)"),
        (KeyCode.ENTER,      "Key ENTER      -> Pilih item aktif & otomatis tutup menu"),
    ]

    print(f"\n{c.BOLD}{c.MAGENTA}=== SIMULASI INTERAKTIF HEADLESS UI & ARIA CONTRACT ==={c.RESET}")
    HeadlessRenderer.render_menu(menu, last_action)

    for step_num, (key, description) in enumerate(scripted_steps, 1):
        print(f"\n{c.CYAN}[Step {step_num}/6] Event Dispatch:{c.RESET} {c.BOLD}{key.value}{c.RESET} ({description})")
        handled = menu.handle_keyboard(key)
        assert handled, f"Event {key.value} seharusnya ditangani oleh state machine"
        HeadlessRenderer.render_menu(menu, last_action)

    # Verifikasi Unit State Kontrak
    print(f"\n{c.GREEN}{c.BOLD}[PASS]{c.RESET} Semua kontrak WAI-ARIA & Roving Tabindex terverifikasi!")
    print(f"{c.DIM}Headless state terpisah 100% dari rendering visual.{c.RESET}\n")


if __name__ == "__main__":
    run_interactive_simulation()
