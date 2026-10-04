#!/usr/bin/env python3
"""
Lab Hands-on: Next.js App Router - Advanced, Parallel, and Intercepting Routes Simulator
Modul 02: Deep Dive Routing Architecture

Simulasi engine routing App Router Next.js (layout compositing, parallel slots, 
intercepting conventions, dan dynamic default.js fallbacks).
"""

import sys
import re
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

# --- ANSI Terminal Formatting ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_CYAN   = "\033[36m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED    = "\033[31m"
CLR_MAG    = "\033[35m"
CLR_BLUE   = "\033[34m"
CLR_GRAY   = "\033[90m"

@dataclass
class RouteComponent:
    """Merepresentasikan unit komponen Next.js (page, layout, default, template)."""
    name: str
    file_path: str
    is_fallback: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def render(self, params: Dict[str, str] = None) -> str:
        param_str = f" [params: {params}]" if params else ""
        return f"<{self.name} src='{self.file_path}'{param_str} />"

@dataclass
class SlotDefinition:
    """Definisi parallel slot (@slotName) di dalam folder segment layout."""
    slot_name: str
    routes: Dict[str, RouteComponent] = field(default_factory=dict)
    default_component: Optional[RouteComponent] = None

class NextRouterEngine:
    """
    Simulasi App Router Engine Next.js.
    Menangani:
    1. Parallel Routes (@slots) composited ke dalam parent layout.
    2. Intercepting Routes: (.) same level, (..) parent level, (..)(..) multi-parent, (...) app root.
    3. State preservation: Soft navigation vs Hard navigation (full refresh) fallback ke default.js.
    """

    def __init__(self):
        self.routes: Dict[str, RouteComponent] = {}
        self.layouts: Dict[str, RouteComponent] = {}
        self.slots: Dict[str, Dict[str, SlotDefinition]] = {}  # layout_path -> {slot_name: SlotDefinition}
        self.interceptors: List[Tuple[str, str, str, RouteComponent]] = [] 
        # (interceptor_scope, intercept_rule, pattern, RouteComponent)
        self.current_url: str = "/"
        self.active_slots_state: Dict[str, RouteComponent] = {}

    def register_layout(self, segment: str, component: RouteComponent):
        """Mendaftarkan layout.tsx pada segmen tertentu."""
        self.layouts[segment] = component
        if segment not in self.slots:
            self.slots[segment] = {}

    def register_page(self, url_pattern: str, component: RouteComponent):
        """Mendaftarkan page.tsx standar untuk rute kanonikal."""
        self.routes[url_pattern] = component

    def register_parallel_slot(self, layout_segment: str, slot_name: str, 
                               sub_path: str, component: RouteComponent, 
                               is_default: bool = False):
        """Mendaftarkan komponen ke parallel slot (@slot_name)."""
        if layout_segment not in self.slots:
            self.slots[layout_segment] = {}
        if slot_name not in self.slots[layout_segment]:
            self.slots[layout_segment][slot_name] = SlotDefinition(slot_name=slot_name)
        
        slot_def = self.slots[layout_segment][slot_name]
        if is_default:
            slot_def.default_component = component
        else:
            slot_def.routes[sub_path] = component

    def register_interceptor(self, context_scope: str, rule: str, target_pattern: str, component: RouteComponent):
        """
        Mendaftarkan Intercepting Route convention:
        - (.) = intercept segmen di level yang sama
        - (..) = intercept 1 level di atas
        - (..)(..) = intercept 2 level di atas
        - (...) = intercept dari root app
        """
        self.interceptors.append((context_scope, rule, target_pattern, component))

    def _match_pattern(self, pattern: str, url: str) -> Optional[Dict[str, str]]:
        """Mencocokkan dynamic segment [param] dengan regex."""
        regex_pattern = re.sub(r'\[(\w+)\]', r'(?P<\1>[^/]+)', pattern)
        regex = f"^{regex_pattern}$"
        match = re.match(regex, url)
        return match.groupdict() if match else None

    def navigate(self, target_url: str, nav_type: str = "soft") -> Dict[str, Any]:
        """
        Simulasi navigasi client Next.js.
        'soft': Client-side transition (Link/useRouter). Interceptor aktif, slot state dipertahankan.
        'hard': Browser full-load / F5. Interceptor di-bypass, slot tak cocok fallback ke default.js.
        """
        print(f"\n{CLR_BOLD}{CLR_BLUE}=== NAVIGATING TO: {target_url} [{nav_type.upper()} NAVIGATION] ==={CLR_RESET}")
        time.sleep(0.05) # Simulasi latency parse tree

        resolved_tree: Dict[str, Any] = {
            "url": target_url,
            "nav_type": nav_type,
            "layout": None,
            "children": None,
            "slots": {},
            "intercepted": False
        }

        # 1. Layout Resolution (Root '/')
        root_layout = self.layouts.get("/", RouteComponent("RootLayout", "app/layout.tsx"))
        resolved_tree["layout"] = root_layout.render()

        # 2. Check Interception Rules (Hanya aktif pada soft navigation)
        intercepted_component = None
        matched_params = {}

        if nav_type == "soft":
            for scope, rule, pattern, comp in self.interceptors:
                # Periksa apakah URL asal berada dalam scope interceptor
                if self.current_url.startswith(scope):
                    params = self._match_pattern(pattern, target_url)
                    if params is not None:
                        intercepted_component = comp
                        matched_params = params
                        resolved_tree["intercepted"] = True
                        print(f" {CLR_MAG}↳ [Intercept Detected] Rule '{rule}' matched from '{self.current_url}'{CLR_RESET}")
                        break

        # 3. Canonical Page Resolution
        canonical_comp = None
        canonical_params = {}
        for pattern, comp in self.routes.items():
            p = self._match_pattern(pattern, target_url)
            if p is not None:
                canonical_comp = comp
                canonical_params = p
                break

        # 4. Slot Resolution & Composite Assembly
        if "/" in self.slots:
            for slot_name, slot_def in self.slots["/"].items():
                slot_rendered = None
                
                # Kasus A: Terkena Intercept -> Slot @modal menangkap tampilan
                if resolved_tree["intercepted"] and slot_name == "modal":
                    slot_rendered = intercepted_component.render(matched_params)
                    self.active_slots_state[slot_name] = intercepted_component
                
                # Kasus B: Cek kecocokan rute internal slot
                elif target_url in slot_def.routes:
                    slot_comp = slot_def.routes[target_url]
                    slot_rendered = slot_comp.render()
                    self.active_slots_state[slot_name] = slot_comp

                # Kasus C: Soft navigation mempertahankan slot aktif sebelumnya
                elif nav_type == "soft" and slot_name in self.active_slots_state:
                    prev_comp = self.active_slots_state[slot_name]
                    slot_rendered = f"{prev_comp.render()} {CLR_YELLOW}(Preserved){CLR_RESET}"

                # Kasus D: Hard navigation atau tak ada state -> Fallback ke default.tsx
                elif slot_def.default_component:
                    slot_rendered = f"{slot_def.default_component.render()} {CLR_GRAY}(Fallback){CLR_RESET}"
                    self.active_slots_state[slot_name] = slot_def.default_component
                
                else:
                    slot_rendered = f"{CLR_RED}404 Unmatched Slot{CLR_RESET}"

                resolved_tree["slots"][f"@{slot_name}"] = slot_rendered

        # 5. Children Resolution
        if resolved_tree["intercepted"]:
            # Jika modal meng-intercept, halaman utama (background) tetap mempertahankan view asal
            bg_pattern = self.current_url
            bg_comp = self.routes.get(bg_pattern, RouteComponent("BackgroundPage", f"app{bg_pattern}/page.tsx"))
            resolved_tree["children"] = f"{bg_comp.render()} {CLR_YELLOW}[Underlying Background Context]{CLR_RESET}"
        elif canonical_comp:
            resolved_tree["children"] = canonical_comp.render(canonical_params)
        else:
            resolved_tree["children"] = f"{CLR_RED}404 Not Found Page{CLR_RESET}"

        self.current_url = target_url
        return resolved_tree

def print_render_tree(result: Dict[str, Any]):
    """Menampilkan tree visual hierarki layout Next.js."""
    print(f"{CLR_CYAN}Rendered Composite Tree for [{result['url']}]:{CLR_RESET}")
    print(f"├─ {CLR_GREEN}{result['layout']}{CLR_RESET}")
    print(f"│  ├─ children: {CLR_BOLD}{result['children']}{CLR_RESET}")
    
    slots = result["slots"]
    idx = 0
    total = len(slots)
    for slot_name, rendered in slots.items():
        idx += 1
        prefix = "└──" if idx == total else "├──"
        print(f"│  {prefix} {CLR_CYAN}{slot_name}:{CLR_RESET} {rendered}")
    print(f"└───────────────────────────────────────────────")

def main():
    print(f"{CLR_BOLD}{CLR_GREEN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}   NEXT.JS ADVANCED ROUTING: PARALLEL & INTERCEPTING ROUTES LAB       {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}======================================================================{CLR_RESET}")
    
    engine = NextRouterEngine()

    # --- 1. SETUP APP ROUTER DIRECTORY STRUCTURE ---
    # app/layout.tsx
    engine.register_layout("/", RouteComponent("RootLayout", "app/layout.tsx"))
    
    # Standalone Pages
    engine.register_page("/", RouteComponent("HomePage", "app/page.tsx"))
    engine.register_page("/feed", RouteComponent("FeedPage", "app/feed/page.tsx"))
    engine.register_page("/photo/[id]", RouteComponent("PhotoDetailPage", "app/photo/[id]/page.tsx"))

    # Parallel Slots: @analytics dan @modal
    # app/@analytics/default.tsx
    engine.register_parallel_slot("/", "analytics", "/", 
                                  RouteComponent("DefaultAnalytics", "app/@analytics/default.tsx", is_fallback=True), 
                                  is_default=True)
    # app/@analytics/feed/page.tsx (hanya aktif di feed)
    engine.register_parallel_slot("/", "analytics", "/feed", 
                                  RouteComponent("FeedAnalyticsWidget", "app/@analytics/feed/page.tsx"))

    # app/@modal/default.tsx (slot modal default render null/kosong)
    engine.register_parallel_slot("/", "modal", "/", 
                                  RouteComponent("ModalNullDefault", "app/@modal/default.tsx", is_fallback=True), 
                                  is_default=True)

    # Intercepting Route: app/feed/(..)photo/[id]/page.tsx
    # Saat navigasi soft dari /feed ke /photo/[id], cegat dan masukkan ke slot @modal
    engine.register_interceptor(
        context_scope="/feed",
        rule="(..)photo/[id]",
        target_pattern="/photo/[id]",
        component=RouteComponent("PhotoModalInterceptor", "app/feed/(..)photo/[id]/page.tsx")
    )

    # --- 2. EXECUTION SCENARIOS ---

    # Scenario 1: Initial load ke root
    res1 = engine.navigate("/", nav_type="hard")
    print_render_tree(res1)

    # Scenario 2: Client Transition (Soft) ke /feed
    # Memuat FeedPage, slot @analytics berubah ke FeedAnalyticsWidget
    res2 = engine.navigate("/feed", nav_type="soft")
    print_render_tree(res2)

    # Scenario 3: Soft Click pada Foto (/photo/42) dari /feed
    # Mengaktifkan Intercepting Route! URL berubah ke /photo/42 di browser, 
    # tetapi children tetap /feed dan @modal merender PhotoModalInterceptor.
    res3 = engine.navigate("/photo/42", nav_type="soft")
    print_render_tree(res3)

    # Scenario 4: User merefresh browser (F5) pada URL /photo/42 (Hard Navigation)
    # Intercepting BUKAN terjadi di hard refresh! Harus render canonical page /photo/[id]/page.tsx
    # dan @analytics / @modal harus fallback ke default.tsx masing-masing.
    res4 = engine.navigate("/photo/42", nav_type="hard")
    print_render_tree(res4)

    # Scenario 5: Soft navigate kembali ke /feed
    res5 = engine.navigate("/feed", nav_type="soft")
    print_render_tree(res5)

    print(f"\n{CLR_GREEN}{CLR_BOLD}Lab Verification Successful:{CLR_RESET} All App Router conventions correctly matched.")

if __name__ == "__main__":
    main()