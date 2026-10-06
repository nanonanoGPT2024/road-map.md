#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Advanced Component Patterns & Headless UI React
Modul: BAB-04-Advanced-Component-Patterns-dan-Headless-UI-Architectur (M01)

Simulasi Python 3 mandiri untuk konsep:
1. Compound Components (Context provider + child consumers)
2. Prop Getters Pattern (Headless UI accessibility & event wiring)
3. State Reducer Pattern (Inversion of Control over state transitions)
4. Render Props Pattern (Children as a Function)
"""

import sys
import json
from typing import Callable, Dict, Any, List, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BLUE = "\033[34m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}\n")


def print_step(step_name: str, desc: str) -> None:
    print(f"{BOLD}{MAGENTA}[PATTERN]{RESET} {YELLOW}{step_name}{RESET}: {desc}")


# ==============================================================================
# 1. COMPOUND COMPONENTS PATTERN SIMULATION
# ==============================================================================
class ReactContext:
    """Simulasi React.createContext() sederhana dalam runtime Python."""
    def __init__(self, default_value: Any = None):
        self.value = default_value

    def provide(self, value: Any) -> None:
        self.value = value

    def consume(self) -> Any:
        return self.value


AccordionContext = ReactContext({"active_id": None, "on_toggle": lambda _: None})


class AccordionItem:
    def __init__(self, item_id: str, title: str, content: str):
        self.item_id = item_id
        self.title = title
        self.content = content

    def render(self) -> str:
        ctx = AccordionContext.consume()
        is_open = ctx.get("active_id") == self.item_id
        icon = f"{GREEN}▼{RESET}" if is_open else f"{DIM}▶{RESET}"
        status = f"{GREEN}[OPEN]{RESET}" if is_open else f"{DIM}[CLOSED]{RESET}"

        out = [f"  {icon} {BOLD}{self.title}{RESET} {status} (id: {self.item_id})"]
        if is_open:
            out.append(f"     {CYAN}│{RESET} {self.content}")
        return "\n".join(out)


class AccordionCompound:
    """Root component yang mengelola state dan Context Provider."""
    def __init__(self):
        self.active_id: Optional[str] = None
        self.items: List[AccordionItem] = []

    def add_item(self, item_id: str, title: str, content: str) -> "AccordionCompound":
        self.items.append(AccordionItem(item_id, title, content))
        return self

    def toggle(self, item_id: str) -> None:
        self.active_id = None if self.active_id == item_id else item_id

    def render(self) -> str:
        # Simulasi <AccordionContext.Provider value={{ active_id, on_toggle }}>
        AccordionContext.provide({"active_id": self.active_id, "on_toggle": self.toggle})
        lines = [f"{BOLD}{BLUE}<Accordion (Compound Component Root)>{RESET}"]
        for it in self.items:
            lines.append(it.render())
        lines.append(f"{BOLD}{BLUE}</Accordion>{RESET}")
        return "\n".join(lines)


# ==============================================================================
# 2. STATE REDUCER PATTERN & HEADLESS PROP GETTERS SIMULATION
# ==============================================================================
class ToggleAction:
    TOGGLE = "TOGGLE"
    RESET = "RESET"
    SET_ON = "SET_ON"
    SET_OFF = "SET_OFF"


def default_toggle_reducer(state: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer standar untuk hook useToggle."""
    act_type = action.get("type")
    if act_type == ToggleAction.TOGGLE:
        return {"on": not state["on"], "click_count": state["click_count"] + 1}
    elif act_type == ToggleAction.RESET:
        return {"on": False, "click_count": 0}
    elif act_type == ToggleAction.SET_ON:
        return {"on": True, "click_count": state["click_count"] + 1}
    elif act_type == ToggleAction.SET_OFF:
        return {"on": False, "click_count": state["click_count"] + 1}
    return state


class HeadlessUseToggle:
    """
    Simulasi Headless Hook 'useToggle' dengan:
    - State Reducer Pattern (inversion of control)
    - Prop Getters Pattern (getTogglerProps, getResetProps)
    """
    def __init__(self, reducer: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = None):
        self.state = {"on": False, "click_count": 0}
        self.custom_reducer = reducer or default_toggle_reducer

    def dispatch(self, action: Dict[str, Any]) -> None:
        self.state = self.custom_reducer(self.state, action)

    # Prop Getter: getTogglerProps
    def get_toggler_props(self, custom_props: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        custom_props = custom_props or {}
        user_on_click = custom_props.get("onClick")

        def composite_click():
            if callable(user_on_click):
                user_on_click()
            self.dispatch({"type": ToggleAction.TOGGLE})

        props = {
            "aria-pressed": self.state["on"],
            "aria-expanded": self.state["on"],
            "role": "switch",
            "data-state": "checked" if self.state["on"] else "unchecked",
            "onClick": composite_click
        }
        # Menggabungkan custom props dari user (prop composition)
        for k, v in custom_props.items():
            if k != "onClick":
                props[k] = v
        return props

    # Prop Getter: getResetProps
    def get_reset_props(self, custom_props: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        custom_props = custom_props or {}
        user_on_click = custom_props.get("onClick")

        def composite_reset():
            if callable(user_on_click):
                user_on_click()
            self.dispatch({"type": ToggleAction.RESET})

        props = {
            "role": "button",
            "type": "button",
            "onClick": composite_reset
        }
        for k, v in custom_props.items():
            if k != "onClick":
                props[k] = v
        return props


# ==============================================================================
# 3. RENDER PROPS PATTERN SIMULATION
# ==============================================================================
class RenderPropsDownshiftDemo:
    """Simulasi Children-as-a-function / Render Props pattern."""
    def __init__(self, items: List[str]):
        self.items = items
        self.selected_item: Optional[str] = None
        self.is_open: bool = False

    def select(self, item: str) -> None:
        self.selected_item = item
        self.is_open = False

    def toggle_menu(self) -> None:
        self.is_open = not self.is_open

    def render(self, children_fn: Callable[[Dict[str, Any]], str]) -> str:
        # Mengoper state dan handlers ke render callback
        props_bag = {
            "isOpen": self.is_open,
            "selectedItem": self.selected_item,
            "items": self.items,
            "toggle": self.toggle_menu,
            "select": self.select
        }
        return children_fn(props_bag)


# ==============================================================================
# INTERACTIVE DEMO RUNNER
# ==============================================================================
def demo_compound_components():
    header("DEMO 1: Compound Components Pattern")
    print_step("Concept", "Implicit state sharing antar elemen via Context tanpa prop drilling.")

    accordion = (
        AccordionCompound()
        .add_item("sec1", "Bagian 1: Inversion of Control", "Membagi kontrol internal komponen ke konsumen API.")
        .add_item("sec2", "Bagian 2: Context Provider Subtree", "Meneruskan state aktif ke child item secara implisit.")
        .add_item("sec3", "Bagian 3: Headless UI Integration", "Memisahkan logika interaksi murni dari styling CSS/Tailwind.")
    )

    print("\nState Awal (Semua tertutup):")
    print(accordion.render())

    print(f"\n{YELLOW}==> Toggle item 'sec2' dibuka:{RESET}")
    accordion.toggle("sec2")
    print(accordion.render())

    print(f"\n{YELLOW}==> Toggle item 'sec3' dibuka (sec2 otomatis tertutup):{RESET}")
    accordion.toggle("sec3")
    print(accordion.render())


def demo_headless_and_state_reducer():
    header("DEMO 2: Headless UI Prop Getters & State Reducer Pattern")
    print_step("Concept", "Konsumen dapat membatasi atau merombak state transition menggunakan State Reducer.")

    MAX_CLICKS = 3

    # Custom State Reducer: melarang toggle jika click_count >= MAX_CLICKS
    def guarded_reducer(state: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
        if action.get("type") == ToggleAction.TOGGLE and state["click_count"] >= MAX_CLICKS:
            print(f"  {RED}[GUARDED]{RESET} State Reducer menolak aksi TOGGLE! Limit {MAX_CLICKS} klik tercapai.")
            return {**state, "blocked": True}
        new_state = default_toggle_reducer(state, action)
        new_state["blocked"] = False
        return new_state

    headless = HeadlessUseToggle(reducer=guarded_reducer)

    log_custom_click: List[str] = []
    # Mengambil prop getters dengan custom onClick injection
    toggler_props = headless.get_toggler_props({
        "className": "btn-headless-primary",
        "id": "theme-switch-btn",
        "onClick": lambda: log_custom_click.append("Telemetry: user clicked switch!")
    })

    print(f"\n{BOLD}Inisialisasi Prop Getters result (A11y attributes):{RESET}")
    print(json.dumps({k: v for k, v in toggler_props.items() if k != "onClick"}, indent=2))

    print(f"\n{YELLOW}Menjalankan klik berulang untuk menguji State Reducer (Maks {MAX_CLICKS} klik):{RESET}")
    for i in range(1, 6):
        print(f"\n-- Percobaan Klik #{i} --")
        toggler_props = headless.get_toggler_props()
        # Eksekusi onClick dari prop getter
        toggler_props["onClick"]()
        curr_state = headless.state
        status_color = GREEN if curr_state["on"] else DIM
        print(f"  Status Switch : {status_color}{'ON' if curr_state['on'] else 'OFF'}{RESET}")
        print(f"  Click Count   : {curr_state['click_count']}")
        print(f"  aria-pressed  : {toggler_props['aria-pressed']}")
        print(f"  Blocked flag  : {curr_state.get('blocked', False)}")

    print(f"\n{YELLOW}Melakukan Reset State via getResetProps():{RESET}")
    reset_props = headless.get_reset_props()
    reset_props["onClick"]()
    print(f"  Status Pasca-Reset: on={headless.state['on']}, count={headless.state['click_count']}")


def demo_render_props():
    header("DEMO 3: Render Props Pattern (Children as a Function)")
    print_step("Concept", "Komponen membungkus logika state dan mendelegasikan template UI kepada fungsi callback.")

    data = ["React.js", "TypeScript", "TailwindCSS", "Zustand"]
    dropdown = RenderPropsDownshiftDemo(data)

    # Definisi callback UI consumer (Slot rendering)
    def custom_theme_ui(bag: Dict[str, Any]) -> str:
        out = [f"{BOLD}[Custom Render Props Dropdown UI]{RESET}"]
        out.append(f"  Status Menu : {'OPEN' if bag['isOpen'] else 'CLOSED'}")
        out.append(f"  Selected    : {GREEN}{bag['selectedItem'] or 'Belum ada pilihan'}{RESET}")
        if bag["isOpen"]:
            out.append("  Pilihan Tersedia:")
            for idx, item in enumerate(bag["items"]):
                pointer = "👉 " if item == bag["selectedItem"] else "   "
                out.append(f"    {pointer}[{idx+1}] {item}")
        return "\n".join(out)

    dropdown.toggle_menu()
    dropdown.select("TypeScript")
    print(dropdown.render(custom_theme_ui))


def interactive_menu():
    while True:
        print(f"\n{BOLD}{CYAN}======================================================{RESET}")
        print(f"{BOLD}{GREEN}  React Advanced Component Patterns Lab (BAB-04)      {RESET}")
        print(f"{BOLD}{CYAN}======================================================{RESET}")
        print(" [1] Jalankan Demo Compound Components")
        print(" [2] Jalankan Demo Headless UI & State Reducer (Prop Getters)")
        print(" [3] Jalankan Demo Render Props Pattern")
        print(" [4] Jalankan Semua Skenario Sekaligus")
        print(" [q] Keluar")
        choice = input(f"\n{BOLD}Pilih opsi [1-4 / q]: {RESET}").strip().lower()

        if choice == "1":
            demo_compound_components()
        elif choice == "2":
            demo_headless_and_state_reducer()
        elif choice == "3":
            demo_render_props()
        elif choice == "4":
            demo_compound_components()
            demo_headless_and_state_reducer()
            demo_render_props()
        elif choice in ("q", "quit", "exit"):
            print(f"\n{GREEN}Lab selesai. Terima kasih!{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")


if __name__ == "__main__":
    # Jika dijalankan non-interaktif (pipe/CI), jalankan opsi 4 secara otomatis
    if not sys.stdin.isatty():
        print(f"{YELLOW}[Non-interactive mode detected] Running all test suites...{RESET}")
        demo_compound_components()
        demo_headless_and_state_reducer()
        demo_render_props()
        print(f"\n{GREEN}Semua simulasi pola React berhasil dieksekusi.{RESET}")
    else:
        interactive_menu()
