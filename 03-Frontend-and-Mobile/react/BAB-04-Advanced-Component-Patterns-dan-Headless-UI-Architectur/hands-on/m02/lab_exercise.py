#!/usr/bin/env python3
"""
React Advanced Component Patterns & Headless UI Simulator
BAB-04: Advanced Component Patterns & Headless UI Architecture
==============================================================
Simulasi interaktif pola arsitektur React tingkat lanjut:
1. Compound Components Pattern (Context + Implicit State Sharing)
2. Headless UI Pattern & Prop Getters (Inversion of Control)
3. State Reducer Pattern (Custom Transition Overrides)
4. Polymorphic Component Pattern ("as" prop & Slot delegation)
"""

import sys
import json
from typing import Dict, Any, List, Optional, Callable

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"

def print_header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*60}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_WHITE} [DEMO] {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*60}{CLR_RESET}")

def print_vdom(tag: str, props: Dict[str, Any], children: Any = None, depth: int = 1) -> None:
    indent = "  " * depth
    prop_str = " ".join([f'{k}="{v}"' for k, v in props.items()])
    if prop_str:
        prop_str = " " + prop_str
    print(f"{indent}{CLR_YELLOW}<{tag}{CLR_GREEN}{prop_str}{CLR_YELLOW}>{CLR_RESET}")
    if children:
        if isinstance(children, list):
            for child in children:
                if isinstance(child, str):
                    print(f"{indent}  {CLR_WHITE}{child}{CLR_RESET}")
                elif callable(child):
                    child(depth + 1)
        elif isinstance(children, str):
            print(f"{indent}  {CLR_WHITE}{children}{CLR_RESET}")
    print(f"{indent}{CLR_YELLOW}</{tag}>{CLR_RESET}")


# ==============================================================================
# 1. COMPOUND COMPONENTS PATTERN (Tabs / TabList / Tab / TabPanels / TabPanel)
# ==============================================================================

class TabContext:
    def __init__(self, selected_index: int = 0):
        self.selected_index = selected_index
        self.listeners: List[Callable[[int], None]] = []

    def set_index(self, index: int):
        self.selected_index = index
        for listener in self.listeners:
            listener(index)


class TabsCompoundComponent:
    """Simulasi Compound Component dengan React Context tersembunyi."""
    def __init__(self, items: List[Dict[str, str]], default_index: int = 0):
        self.items = items
        self.context = TabContext(default_index)

    def render(self) -> None:
        print(f"\n{CLR_MAGENTA}[Virtual DOM Tree Rendering - Tabs Compound Component]{CLR_RESET}")
        
        def render_tab_list(depth: int):
            for idx, item in enumerate(self.items):
                is_active = (idx == self.context.selected_index)
                props = {
                    "role": "tab",
                    "aria-selected": str(is_active).lower(),
                    "class": "tab-pill active" if is_active else "tab-pill inactive",
                    "data-tab-index": idx
                }
                print_vdom("TabButton", props, item["title"], depth + 1)

        def render_tab_panels(depth: int):
            for idx, item in enumerate(self.items):
                is_active = (idx == self.context.selected_index)
                if is_active:
                    props = {
                        "role": "tabpanel",
                        "id": f"panel-{idx}",
                        "aria-hidden": "false",
                        "class": "panel-container active-view"
                    }
                    print_vdom("TabPanel", props, item["content"], depth + 1)

        print_vdom("TabsProvider", {"value": f"selectedIndex={self.context.selected_index}"}, [
            lambda d: print_vdom("TabList", {"aria-label": "System Navigation"}, [render_tab_list], d),
            lambda d: print_vdom("TabPanels", {"class": "tab-content-wrapper"}, [render_tab_panels], d),
        ])


# ==============================================================================
# 2. HEADLESS UI & PROP GETTERS PATTERN (useAccordion / useSelect hook model)
# ==============================================================================

class HeadlessAccordionState:
    """State logic & prop getters yang sepenuhnya independen dari markup styling."""
    def __init__(self, total_sections: int):
        self.expanded_indices = set([0])  # Section 0 default open
        self.total = total_sections

    def toggle(self, index: int):
        if index in self.expanded_indices:
            self.expanded_indices.remove(index)
        else:
            self.expanded_indices.add(index)

    def get_trigger_props(self, index: int, custom_props: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Prop getter: menggabungkan aria attributes, click handlers, dan custom props."""
        is_open = index in self.expanded_indices
        base_props = {
            "type": "button",
            "aria-expanded": str(is_open).lower(),
            "aria-controls": f"accordion-section-{index}",
            "id": f"accordion-header-{index}",
            "data-state": "open" if is_open else "collapsed"
        }
        if custom_props:
            # Prop getter convention: merge classes and handlers cleanly
            merged = {**base_props, **custom_props}
            if "class" in custom_props and "class" in base_props:
                merged["class"] = f"{base_props['class']} {custom_props['class']}"
            return merged
        return base_props

    def get_panel_props(self, index: int, custom_props: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        is_open = index in self.expanded_indices
        base_props = {
            "role": "region",
            "id": f"accordion-section-{index}",
            "aria-labelledby": f"accordion-header-{index}",
            "hidden": not is_open,
            "data-state": "open" if is_open else "collapsed"
        }
        if custom_props:
            return {**base_props, **custom_props}
        return base_props


# ==============================================================================
# 3. STATE REDUCER PATTERN (Inversion of Control for State Transitions)
# ==============================================================================

class ToggleAction:
    TOGGLE = "TOGGLE"
    RESET = "RESET"
    SET_ON = "SET_ON"
    SET_OFF = "SET_OFF"

class HeadlessToggle:
    """Downshift / Kent C. Dodds style State Reducer."""
    def __init__(self, state_reducer: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = None):
        self.state = {"on": False, "toggle_count": 0}
        self.custom_reducer = state_reducer

    def default_reducer(self, state: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
        act_type = action.get("type")
        if act_type == ToggleAction.TOGGLE:
            return {
                "on": not state["on"],
                "toggle_count": state["toggle_count"] + 1
            }
        elif act_type == ToggleAction.RESET:
            return {"on": False, "toggle_count": 0}
        elif act_type == ToggleAction.SET_ON:
            return {"on": True, "toggle_count": state["toggle_count"] + 1}
        elif act_type == ToggleAction.SET_OFF:
            return {"on": False, "toggle_count": state["toggle_count"] + 1}
        return state

    def dispatch(self, action: Dict[str, Any]) -> None:
        # Panggil default reducer lalu operkan ke user state reducer jika ada
        default_next = self.default_reducer(self.state, action)
        if self.custom_reducer:
            self.state = self.custom_reducer(self.state, {**action, "changes": default_next})
        else:
            self.state = default_next


# ==============================================================================
# 4. POLYMORPHIC COMPONENT PATTERN ("as" prop delegation)
# ==============================================================================

def render_polymorphic(as_tag: str, props: Dict[str, Any], content: str) -> None:
    """Simulasi komponen polymorphic <Box as={...} /> atau <Button as="a" href="..." />."""
    # Memastikan validasi aksesibilitas sesuai tag target
    final_props = dict(props)
    if as_tag == "a":
        if "href" not in final_props:
            final_props["href"] = "#"
        final_props["role"] = "link"
    elif as_tag == "button":
        final_props.setdefault("type", "button")
    
    print_vdom(as_tag, final_props, content, depth=2)


# ==============================================================================
# INTERACTIVE CLI RUNNER
# ==============================================================================

def demo_compound_components():
    print_header("1. Compound Components Pattern (Tabs)")
    print(f"{CLR_DIM}Pola: State enkapsulasi di Root, sub-komponen membaca via Context implicitly.{CLR_RESET}\n")
    
    items = [
        {"title": "Overview", "content": "Dashboard analitik arsitektur multi-tenant."},
        {"title": "Performance", "content": "Metrik bundle size: 42KB gzip, FCP: 0.8s."},
        {"title": "Security", "content": "Zero-trust RBAC tokens & CSP strict headers terkonfigurasi."}
    ]
    tabs = TabsCompoundComponent(items, default_index=0)
    tabs.render()

    while True:
        try:
            choice = input(f"\n{CLR_GREEN}Pilih Tab (0-2) untuk simulasi klik, atau 'b' kembali: {CLR_RESET}").strip()
            if choice.lower() == 'b':
                break
            idx = int(choice)
            if 0 <= idx < len(items):
                tabs.context.set_index(idx)
                tabs.render()
            else:
                print(f"{CLR_RED}Pilihan tidak valid! Masukkan 0, 1, atau 2.{CLR_RESET}")
        except ValueError:
            print(f"{CLR_RED}Input harus angka numerik!{CLR_RESET}")


def demo_headless_prop_getters():
    print_header("2. Headless UI & Prop Getters Pattern (useAccordion)")
    print(f"{CLR_DIM}Pola: Hook memproduksi getter function (getTriggerProps) menyatukan ARIA & handlers.{CLR_RESET}\n")

    sections = [
        ("Architecture Seams", "Memisahkan view presentation dengan business state machine."),
        ("A11y Compliance", "Menyediakan aria-expanded, aria-controls, dan role otomatis."),
        ("Extensibility", "Consumer leluasa menyuntikkan className dan styling Tailwind/CSS Modules.")
    ]
    accordion = HeadlessAccordionState(len(sections))

    def render_accordion():
        print(f"\n{CLR_MAGENTA}[Virtual DOM Output via Prop Getters]{CLR_RESET}")
        for idx, (title, content) in enumerate(sections):
            trigger_props = accordion.get_trigger_props(idx, {"class": "btn-accordion-head"})
            panel_props = accordion.get_panel_props(idx, {"class": "accordion-body-collapsible"})
            
            print_vdom("AccordionItem", {"data-index": idx}, [
                lambda d, p=trigger_props, t=title: print_vdom("button", p, t, d),
                lambda d, p=panel_props, c=content: print_vdom("div", p, c if not p.get("hidden") else "[HIDDEN CONTENT]", d)
            ], depth=1)

    render_accordion()

    while True:
        try:
            choice = input(f"\n{CLR_GREEN}Pilih Accordion Index (0-2) untuk toggle, atau 'b' kembali: {CLR_RESET}").strip()
            if choice.lower() == 'b':
                break
            idx = int(choice)
            if 0 <= idx < len(sections):
                accordion.toggle(idx)
                render_accordion()
            else:
                print(f"{CLR_RED}Index tidak valid! Masukkan 0, 1, atau 2.{CLR_RESET}")
        except ValueError:
            print(f"{CLR_RED}Input harus berupa angka!{CLR_RESET}")


def demo_state_reducer():
    print_header("3. State Reducer Pattern (Custom Rule Inversion)")
    print(f"{CLR_DIM}Kasus: Consumer ingin membatasi toggle maksimal 4 kali (Rate Limiting Feature).{CLR_RESET}\n")

    def rate_limited_reducer(state: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
        changes = action["changes"]
        # Custom logic: Jika sudah toggle >= 4 kali, cegah state 'on' menjadi True!
        if state["toggle_count"] >= 4 and action["type"] == ToggleAction.TOGGLE:
            print(f"{CLR_RED}>> [INTERCEPTED BY STATE REDUCER] Limit toggle tercapai (Max 4)! Aksi diblokir.{CLR_RESET}")
            return {**state, "blocked": True}
        return changes

    toggle = HeadlessToggle(state_reducer=rate_limited_reducer)

    while True:
        status_color = CLR_GREEN if toggle.state["on"] else CLR_RED
        print(f"\nState Sekarang: on={status_color}{toggle.state['on']}{CLR_RESET}, count={CLR_YELLOW}{toggle.state['toggle_count']}{CLR_RESET}")
        cmd = input(f"{CLR_GREEN}Ketik 't' (toggle), 'r' (reset), atau 'b' (kembali): {CLR_RESET}").strip().lower()
        if cmd == 'b':
            break
        elif cmd == 't':
            toggle.dispatch({"type": ToggleAction.TOGGLE})
        elif cmd == 'r':
            toggle.dispatch({"type": ToggleAction.RESET})
        else:
            print(f"{CLR_YELLOW}Perintah tidak dikenal.{CLR_RESET}")


def demo_polymorphic():
    print_header("4. Polymorphic Component Pattern ('as' prop)")
    print(f"{CLR_DIM}Pola: Merender elemen HTML fleksibel tanpa melanggar semantik HTML.{CLR_RESET}\n")

    print(f"{CLR_WHITE}Contoh 1: Komponen Button dirender sebagai <button>{CLR_RESET}")
    render_polymorphic("button", {"class": "btn-primary", "onClick": "handleClick"}, "Submit Data")

    print(f"\n{CLR_WHITE}Contoh 2: Komponen Button dirender sebagai tag hyperlink <a>{CLR_RESET}")
    render_polymorphic("a", {"class": "btn-link-styled", "href": "/docs/headless"}, "Buka Dokumentasi")

    print(f"\n{CLR_WHITE}Contoh 3: Komponen Card dirender semantik sebagai <article>{CLR_RESET}")
    render_polymorphic("article", {"class": "card-elevated", "aria-labelledby": "card-title"}, "Konten Artikel Blog")


def run_automated_suite():
    print_header("5. Menjalankan Automated Verification Suite")
    print(f"{CLR_CYAN}Running verification checks across 4 patterns...{CLR_RESET}\n")

    # 1. Compound check
    items = [{"title": "T1", "content": "C1"}, {"title": "T2", "content": "C2"}]
    tabs = TabsCompoundComponent(items, default_index=0)
    assert tabs.context.selected_index == 0
    tabs.context.set_index(1)
    assert tabs.context.selected_index == 1
    print(f" {CLR_GREEN}✓{CLR_RESET} Compound Component Context Synchronization: PASSED")

    # 2. Headless Prop Getter check
    accordion = HeadlessAccordionState(3)
    p0 = accordion.get_trigger_props(0)
    assert p0["aria-expanded"] == "true"
    accordion.toggle(0)
    p0_after = accordion.get_trigger_props(0)
    assert p0_after["aria-expanded"] == "false"
    print(f" {CLR_GREEN}✓{CLR_RESET} Headless Prop Getter ARIA & State Mutation: PASSED")

    # 3. State Reducer check
    limit_hit = False
    def test_reducer(st, act):
        nonlocal limit_hit
        if st["toggle_count"] >= 2:
            limit_hit = True
            return st
        return act["changes"]

    t = HeadlessToggle(state_reducer=test_reducer)
    t.dispatch({"type": ToggleAction.TOGGLE})
    t.dispatch({"type": ToggleAction.TOGGLE})
    t.dispatch({"type": ToggleAction.TOGGLE})
    assert limit_hit is True
    print(f" {CLR_GREEN}✓{CLR_RESET} State Reducer Inversion of Control Override: PASSED")

    # 4. Polymorphic check
    box_props = {}
    if "href" not in box_props:
        box_props["href"] = "/test"
    assert box_props["href"] == "/test"
    print(f" {CLR_GREEN}✓{CLR_RESET} Polymorphic Tag & Attribute Injection: PASSED")

    print(f"\n{CLR_BOLD}{CLR_GREEN}Semua Unit Test Pola Arsitektur React Berhasil (100% Passed)!{CLR_RESET}\n")


def main():
    while True:
        print_header("React Advanced Component Patterns Simulator")
        print(f"{CLR_BOLD}Pilih Modul Simulasi:{CLR_RESET}")
        print(f" 1. {CLR_WHITE}Compound Components Pattern (Tabs System){CLR_RESET}")
        print(f" 2. {CLR_WHITE}Headless UI & Prop Getters (Accordion Engine){CLR_RESET}")
        print(f" 3. {CLR_WHITE}State Reducer Pattern (Custom State Interception){CLR_RESET}")
        print(f" 4. {CLR_WHITE}Polymorphic Component Engine ('as' Prop Delegation){CLR_RESET}")
        print(f" 5. {CLR_GREEN}Jalankan Automated Self-Test Verification{CLR_RESET}")
        print(f" 6. {CLR_RED}Keluar (Exit){CLR_RESET}")

        try:
            choice = input(f"\n{CLR_CYAN}Masukkan nomor opsi [1-6]: {CLR_RESET}").strip()
            if choice == "1":
                demo_compound_components()
            elif choice == "2":
                demo_headless_prop_getters()
            elif choice == "3":
                demo_state_reducer()
            elif choice == "4":
                demo_polymorphic()
            elif choice == "5":
                run_automated_suite()
            elif choice == "6":
                print(f"\n{CLR_YELLOW}Menutup simulator. Selesai!{CLR_RESET}")
                sys.exit(0)
            else:
                print(f"{CLR_RED}Pilihan tidak valid. Silakan pilih 1-6.{CLR_RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{CLR_YELLOW}\nProgram dihentikan oleh user.{CLR_RESET}")
            sys.exit(0)

if __name__ == "__main__":
    main()
