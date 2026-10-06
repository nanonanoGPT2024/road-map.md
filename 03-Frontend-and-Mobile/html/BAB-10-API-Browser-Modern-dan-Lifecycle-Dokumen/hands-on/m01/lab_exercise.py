#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Modern Browser APIs & Document Lifecycle
BAB-10: Modern Browser API & Document Lifecycle Engine (HTML5 Specification)

Topik yang disimulasikan:
1. Document ReadyState Lifecycle: loading -> interactive -> complete
2. Event Sequence: readystatechange, DOMContentLoaded, load, visibilitychange
3. Modern Browser Observer APIs: IntersectionObserver & MutationObserver mock engine
4. Background Tab Throttling (Page Visibility API)
"""

import sys
import time
import random
from typing import List, Dict, Callable, Any, Optional

# ANSI Color Palette
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
BG_BLUE = "\033[44m"
BG_GRAY = "\033[100m"

def print_header(title: str) -> None:
    print(f"\n{BG_BLUE}{WHITE}{BOLD} [BROWSER RUNTIME] {title.upper()} {RESET}")
    print(f"{CYAN}{'=' * 68}{RESET}")

def log_event(event_name: str, phase: str, detail: str) -> None:
    timestamp = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
    print(f"{DIM}[{timestamp}]{RESET} {MAGENTA}[Phase: {phase:<12}]{RESET} {GREEN}{event_name:<20}{RESET} -> {detail}")

class DOMNode:
    def __init__(self, tag_name: str, attributes: Optional[Dict[str, str]] = None):
        self.tag_name = tag_name
        self.attributes = attributes or {}
        self.children: List['DOMNode'] = []
        self.text_content: str = ""

    def append_child(self, child: 'DOMNode') -> 'DOMNode':
        self.children.append(child)
        return child

class IntersectionObserverEntry:
    def __init__(self, target_id: str, is_intersecting: bool, ratio: float):
        self.target_id = target_id
        self.is_intersecting = is_intersecting
        self.intersection_ratio = ratio

class MockIntersectionObserver:
    def __init__(self, callback: Callable[[List[IntersectionObserverEntry]], None], threshold: float = 0.5):
        self.callback = callback
        self.threshold = threshold
        self.targets: List[Dict[str, Any]] = []

    def observe(self, element_id: str, top_pos: int, height: int) -> None:
        self.targets.append({"id": element_id, "top": top_pos, "height": height})

    def check_viewport(self, scroll_y: int, viewport_height: int = 500) -> None:
        entries = []
        viewport_bottom = scroll_y + viewport_height
        for target in self.targets:
            elem_top = target["top"]
            elem_bottom = elem_top + target["height"]
            overlap_top = max(scroll_y, elem_top)
            overlap_bottom = min(viewport_bottom, elem_bottom)

            if overlap_bottom > overlap_top:
                overlap_height = overlap_bottom - overlap_top
                ratio = overlap_height / target["height"]
                intersecting = ratio >= self.threshold
                entries.append(IntersectionObserverEntry(target["id"], intersecting, ratio))
            else:
                entries.append(IntersectionObserverEntry(target["id"], False, 0.0))

        if entries:
            self.callback(entries)

class DocumentLifecycleEngine:
    def __init__(self):
        self.ready_state: str = "uninitialized"
        self.dom_tree: Optional[DOMNode] = None
        self.visibility_state: str = "visible"
        self.listeners: Dict[str, List[Callable]] = {
            "readystatechange": [],
            "DOMContentLoaded": [],
            "load": [],
            "visibilitychange": [],
            "beforeunload": []
        }

    def add_event_listener(self, event_name: str, callback: Callable) -> None:
        if event_name in self.listeners:
            self.listeners[event_name].append(callback)

    def dispatch_event(self, event_name: str, phase: str, detail: str) -> None:
        log_event(event_name, phase, detail)
        for cb in self.listeners.get(event_name, []):
            cb(self)

    def run_parser_simulation(self) -> None:
        print_header("Simulasi Lifecycle Dokumen HTML5")
        
        # Phase 1: Loading
        self.ready_state = "loading"
        self.dispatch_event("readystatechange", "PARSING", "Parser HTML mulai membaca token stream bytes dari server")
        
        self.dom_tree = DOMNode("html")
        head = self.dom_tree.append_child(DOMNode("head"))
        body = self.dom_tree.append_child(DOMNode("body"))
        time.sleep(0.3)

        print(f"  {YELLOW}↳ [Parser] Menemukan <link rel='stylesheet'>: Render blocking stylesheet...{RESET}")
        time.sleep(0.2)
        print(f"  {YELLOW}↳ [Parser] Menemukan <script defer src='app.js'>: Deferred script diunduh di background...{RESET}")
        time.sleep(0.3)

        # Phase 2: Interactive
        self.ready_state = "interactive"
        self.dispatch_event("readystatechange", "DOM_READY", "Parser selesai membuat pohon DOM (DOM fully parsed)")
        self.dispatch_event("DOMContentLoaded", "DOM_READY", "Event DOMContentLoaded aktif: Script defer selesai dieksekusi")
        time.sleep(0.4)

        # External sub-resources loading (images, fonts, async frames)
        print(f"  {BLUE}↳ [Network] Mengunduh aset sub-resources (gambar, webfonts, async scripts)...{RESET}")
        for asset in ["hero.webp (1.2MB)", "font-inter.woff2 (84KB)", "analytics.js (async)"]:
            time.sleep(0.2)
            print(f"    {GREEN}✔ Loaded:{RESET} {asset}")

        # Phase 3: Complete
        self.ready_state = "complete"
        self.dispatch_event("readystatechange", "FINAL", "Semua aset sub-resources selesai dimuat")
        self.dispatch_event("load", "FINAL", "Event window.onload aktif: Halaman siap pakai sepenuhnya")

    def simulate_visibility_change(self, new_state: str) -> None:
        self.visibility_state = new_state
        status_msg = "Tab aktif / di foreground" if new_state == "visible" else "Tab diminimalkan / background (CPU Throttling diaktifkan)"
        self.dispatch_event("visibilitychange", "PAGE_VISIBILITY", f"document.visibilityState = '{new_state}' ({status_msg})")

def run_intersection_observer_demo() -> None:
    print_header("Simulasi Modern API: IntersectionObserver (Lazy Loading)")
    
    def on_intersect(entries: List[IntersectionObserverEntry]):
        for entry in entries:
            state_label = f"{GREEN}IN VIEWPORT{RESET}" if entry.is_intersecting else f"{RED}OUT OF VIEW{RESET}"
            print(f"  [Observer] Target: {BOLD}#{entry.target_id:<12}{RESET} | Ratio: {entry.intersection_ratio*100:>5.1f}% | State: {state_label}")

    observer = MockIntersectionObserver(callback=on_intersect, threshold=0.5)
    
    # Daftarkan elemen dalam viewport maya
    elements = [
        ("header-banner", 0, 200),
        ("article-intro", 250, 300),
        ("lazy-gallery-1", 600, 400),
        ("lazy-gallery-2", 1100, 400),
        ("footer-section", 1600, 200),
    ]
    for el_id, top, height in elements:
        observer.observe(el_id, top, height)

    scroll_positions = [0, 400, 900, 1400]
    for sp in scroll_positions:
        print(f"\n{BOLD}{CYAN}>>> User Melakukan Scroll ke Posisi Y: {sp}px (Viewport Height: 500px){RESET}")
        observer.check_viewport(scroll_y=sp, viewport_height=500)
        time.sleep(0.3)

def interactive_menu() -> None:
    engine = DocumentLifecycleEngine()
    
    while True:
        print(f"\n{BOLD}{WHITE}=== Browser Lifecycle & Modern API Terminal Lab ==={RESET}")
        print("1. Jalankan Simulasi Siklus Hidup Dokumen (DOM Lifecycle)")
        print("2. Jalankan Simulasi IntersectionObserver (Viewport & Lazy Loading)")
        print("3. Uji Simulasi Page Visibility API (Tab Switch & Throttling)")
        print("4. Jalankan Semua Skenario Otomatis")
        print("5. Keluar")
        
        choice = input(f"{YELLOW}Pilih menu (1-5): {RESET}").strip()
        
        if choice == "1":
            engine.run_parser_simulation()
        elif choice == "2":
            run_intersection_observer_demo()
        elif choice == "3":
            print_header("Simulasi Page Visibility API")
            engine.simulate_visibility_change("hidden")
            time.sleep(0.4)
            engine.simulate_visibility_change("visible")
        elif choice == "4":
            engine.run_parser_simulation()
            run_intersection_observer_demo()
            print_header("Simulasi Page Visibility API")
            engine.simulate_visibility_change("hidden")
            time.sleep(0.3)
            engine.simulate_visibility_change("visible")
            print(f"\n{GREEN}{BOLD}✔ Seluruh simulasi selesai dengan sukses!{RESET}\n")
            break
        elif choice == "5" or choice.lower() == "q":
            print(f"{CYAN}Menutup simulasi runtime browser. Sampai jumpa!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 1-5.{RESET}")

if __name__ == "__main__":
    # Jika dijalankan secara non-interaktif (piped/CI), jalankan skenario 4 langsung
    if not sys.stdin.isatty():
        engine = DocumentLifecycleEngine()
        engine.run_parser_simulation()
        run_intersection_observer_demo()
        engine.simulate_visibility_change("hidden")
        engine.simulate_visibility_change("visible")
        print(f"\n{GREEN}{BOLD}✔ Selesai menjalankan mode otomatis (non-interactive).{RESET}")
    else:
        interactive_menu()
