#!/usr/bin/env python3
"""
Lab Exercise: React Native Declarative UI, Component Lifecycle, and Styling Engine Simulation.
BAB-02: Declarative UI, Component Lifecycle, dan Styling Systems.

Fitur Simulasi Arsitektur Produksi:
1. Design Token & Theme Engine (Light / Dark Palette, Spacing, Typography).
2. StyleSheet Engine dengan ID Hashing, Style Cache, dan Flattening.
3. Declarative Virtual Node Tree & Yoga Layout Box Model Simulation.
4. Component Lifecycle Manager (Mount, Effect Hook, Memoized Diffing, Unmount/Cleanup).
5. Interactive Terminal UI dengan pewarnaan ANSI 256-color & Real-Time Action Log.
"""

import sys
import time
import json
import hashlib
from typing import Dict, Any, List, Optional, Callable

# ==========================================
# 1. ANSI Terminal Styling Utilities
# ==========================================
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground
    RED = "\033[38;5;196m"
    GREEN = "\033[38;5;46m"
    YELLOW = "\033[38;5;226m"
    BLUE = "\033[38;5;39m"
    MAGENTA = "\033[38;5;201m"
    CYAN = "\033[38;5;51m"
    WHITE = "\033[38;5;231m"
    GRAY = "\033[38;5;244m"
    DARK_GRAY = "\033[38;5;236m"
    ORANGE = "\033[38;5;208m"

    # Background
    BG_DARK = "\033[48;5;234m"
    BG_HEADER = "\033[48;5;24m"


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}================================================================================
  REACT NATIVE INTERNALS SIMULATOR: BAB 02
  Declarative UI • Component Lifecycle • Layout Tree • StyleSheet System
================================================================================{Colors.RESET}"""
    print(banner)


# ==========================================
# 2. Design Tokens & StyleSheet System
# ==========================================
THEMES = {
    "light": {
        "colors": {
            "background": "#F8FAFC",
            "surface": "#FFFFFF",
            "text": "#0F172A",
            "mutedText": "#64748B",
            "primary": "#2563EB",
            "accent": "#10B981",
            "border": "#E2E8F0",
        },
        "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
        "radius": {"sm": 4, "md": 8, "lg": 16, "full": 9999},
    },
    "dark": {
        "colors": {
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F8FAFC",
            "mutedText": "#94A3B8",
            "primary": "#3B82F6",
            "accent": "#34D399",
            "border": "#334155",
        },
        "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
        "radius": {"sm": 4, "md": 8, "lg": 16, "full": 9999},
    },
}


class StyleSheet:
    """
    Simulasi StyleSheet.create() React Native:
    - Mendaftarkan style object ke memory cache.
    - Mengembalikan ID numerik / referensi konstan untuk mencegah serialisasi ulang ke Yoga/Bridge.
    """
    _registry: Dict[int, Dict[str, Any]] = {}
    _counter: int = 1000

    @classmethod
    def create(cls, styles_dict: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
        result = {}
        for key, style_props in styles_dict.items():
            cls._counter += 1
            style_id = cls._counter
            cls._registry[style_id] = style_props
            result[key] = style_id
        return result

    @classmethod
    def get(cls, style_id: int) -> Dict[str, Any]:
        return cls._registry.get(style_id, {})

    @classmethod
    def flatten(cls, style_input: Any) -> Dict[str, Any]:
        """Meniru StyleSheet.flatten() array of styles."""
        if not style_input:
            return {}
        if isinstance(style_input, int):
            return cls.get(style_input).copy()
        if isinstance(style_input, dict):
            return style_input.copy()
        if isinstance(style_input, list):
            flattened = {}
            for item in style_input:
                flattened.update(cls.flatten(item))
            return flattened
        return {}


# ==========================================
# 3. Virtual Node & Simulated Yoga Layout
# ==========================================
class LayoutBox:
    def __init__(self, x: int = 0, y: int = 0, width: int = 60, height: int = 10):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def __repr__(self):
        return f"Rect({self.x}, {self.y}, {self.width}x{self.height})"


class VirtualNode:
    """
    Representasi Shadow Node React Native yang menampung props, style komputasi,
    serta layout geometrik hasil komputasi Yoga.
    """
    def __init__(self, tag: str, props: Optional[Dict[str, Any]] = None, children: Optional[List['VirtualNode']] = None):
        self.tag = tag
        self.props = props or {}
        self.children = children or []
        self.layout = LayoutBox()
        self.computed_style: Dict[str, Any] = {}

    def compute_layout(self, parent_width: int = 60, start_y: int = 0) -> int:
        """Simulasi kalkulasi flexbox sederhana (Flex Direction: column/row)."""
        flattened_style = StyleSheet.flatten(self.props.get("style", {}))
        self.computed_style = flattened_style

        pad = flattened_style.get("padding", 0)
        self.layout.width = flattened_style.get("width", parent_width)
        flex_dir = flattened_style.get("flexDirection", "column")

        current_y = start_y + pad
        current_x = pad

        total_child_height = 0
        for child in self.children:
            child_h = child.compute_layout(parent_width=self.layout.width - (pad * 2), start_y=current_y)
            if flex_dir == "column":
                child.layout.x = current_x
                child.layout.y = current_y
                current_y += child_h + flattened_style.get("rowGap", 1)
                total_child_height += child_h
            else:
                child.layout.x = current_x
                child.layout.y = start_y + pad
                current_x += child.layout.width + flattened_style.get("columnGap", 1)
                total_child_height = max(total_child_height, child_h)

        self.layout.height = flattened_style.get("height", max(2, total_child_height + (pad * 2)))
        return self.layout.height

    def render_ascii(self, indent: int = 0) -> List[str]:
        pad_str = "  " * indent
        bg_color = self.computed_style.get("backgroundColor", "")
        text_content = self.props.get("children", "")

        lines = []
        if self.tag == "View":
            border_col = Colors.GRAY if not bg_color else Colors.CYAN
            header = f"{pad_str}{border_col}┌── [View] {self.layout} bg:{bg_color or 'transparent'}{Colors.RESET}"
            lines.append(header)
            for child in self.children:
                lines.extend(child.render_ascii(indent + 1))
            lines.append(f"{pad_str}{border_col}└──{Colors.RESET}")
        elif self.tag == "Text":
            font_col = Colors.WHITE if self.computed_style.get("color") == "#F8FAFC" else Colors.YELLOW
            weight = Colors.BOLD if self.computed_style.get("fontWeight") == "bold" else ""
            lines.append(f"{pad_str}{font_col}{weight}↳ Text: \"{text_content}\"{Colors.RESET}")
        elif self.tag == "TouchableOpacity":
            lines.append(f"{pad_str}{Colors.GREEN}[Button] {text_content} ({self.props.get('title', 'Action')}){Colors.RESET}")
        return lines


# ==========================================
# 4. Declarative Component & Lifecycle Engine
# ==========================================
class ComponentLifecycle:
    """
    Mengontrol fase hidup:
    1. constructor / init state
    2. render() -> VirtualNode
    3. commit & mounting (useEffect on mount)
    4. update state -> re-render -> dependency check -> effect re-run
    5. unmount -> effect cleanup function
    """
    def __init__(self, name: str):
        self.name = name
        self.state: Dict[str, Any] = {}
        self.prev_state: Dict[str, Any] = {}
        self.is_mounted = False
        self._effects: List[Dict[str, Any]] = []
        self._cleanups: List[Callable[[], None]] = []

    def set_state(self, updates: Dict[str, Any]):
        self.prev_state = self.state.copy()
        self.state.update(updates)
        self.on_state_updated()

    def register_effect(self, effect_fn: Callable[[], Optional[Callable[[], None]]], deps: Optional[List[Any]] = None):
        self._effects.append({
            "effect_fn": effect_fn,
            "deps": deps,
            "prev_deps": None,
            "cleanup": None
        })

    def mount(self):
        self.is_mounted = True
        print(f"  {Colors.GREEN}● [Mounting]{Colors.RESET} Komponen <{self.name}/> dipasang ke Fiber Tree.")
        self._run_effects(is_mount=True)

    def on_state_updated(self):
        print(f"  {Colors.YELLOW}↺ [Re-rendering]{Colors.RESET} State diperbarui: {json.dumps(self.state)}")
        self._run_effects(is_mount=False)

    def _run_effects(self, is_mount: bool):
        for eff in self._effects:
            deps = eff["deps"]
            prev_deps = eff["prev_deps"]

            should_run = False
            if is_mount:
                should_run = True
            elif deps is None:
                should_run = True
            elif prev_deps is None or len(deps) != len(prev_deps):
                should_run = True
            else:
                for idx, val in enumerate(deps):
                    if val != prev_deps[idx]:
                        should_run = True
                        break

            if should_run:
                # Jalankan cleanup sebelumnya bila ada
                if eff["cleanup"] and callable(eff["cleanup"]):
                    print(f"  {Colors.ORANGE}🧹 [Cleanup]{Colors.RESET} Menjalankan unmount/cleanup effect sebelumnya.")
                    eff["cleanup"]()

                cleanup_fn = eff["effect_fn"]()
                eff["cleanup"] = cleanup_fn
                eff["prev_deps"] = list(deps) if deps is not None else None

    def unmount(self):
        print(f"  {Colors.RED}✖ [Unmounting]{Colors.RESET} Melepas <{self.name}/> dari memory...")
        for eff in self._effects:
            if eff["cleanup"] and callable(eff["cleanup"]):
                eff["cleanup"]()
        self.is_mounted = False
        print(f"  {Colors.GRAY}✓ Selesai membersihkan listener & timer subscription.{Colors.RESET}")


# ==========================================
# 5. Production Component Implementation
# ==========================================
class UserProfileDashboard(ComponentLifecycle):
    def __init__(self, initial_theme: str = "dark"):
        super().__init__(name="UserProfileDashboard")
        self.theme_name = initial_theme
        self.state = {
            "user_id": 402,
            "name": "Budi Santoso",
            "role": "Lead Mobile Engineer",
            "is_active": True,
            "counter": 0,
        }

        # Definisikan Stylesheet
        self.static_styles = StyleSheet.create({
            "container": {
                "padding": 2,
                "flexDirection": "column",
                "width": 64,
                "rowGap": 1,
            },
            "headerBox": {
                "padding": 1,
                "height": 3,
                "flexDirection": "column",
            },
            "metricCard": {
                "padding": 1,
                "flexDirection": "column",
                "height": 4,
            },
            "button": {
                "padding": 1,
                "height": 2,
            }
        })

        # Daftarkan Hooks / Lifecycle Effects
        self.setup_effects()

    def setup_effects(self):
        def websocket_sync():
            user_id = self.state["user_id"]
            print(f"  {Colors.CYAN}⚡ [Effect: WebSocket]{Colors.RESET} Membuka koneksi socket telemetry untuk User #{user_id}")

            def cleanup():
                print(f"  {Colors.CYAN}🔌 [Cleanup: WebSocket]{Colors.RESET} Menutup koneksi socket User #{user_id}")

            return cleanup

        # Effect terikat pada dependensi [user_id]
        self.register_effect(websocket_sync, deps=[self.state["user_id"]])

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        print(f"  {Colors.MAGENTA}🎨 [Theme Switch]{Colors.RESET} Berpindah ke tema: {self.theme_name.upper()}")
        self.on_state_updated()

    def increment_metric(self):
        self.set_state({"counter": self.state["counter"] + 1})

    def switch_user(self):
        new_id = 505 if self.state["user_id"] == 402 else 402
        new_name = "Siti Rahma" if new_id == 505 else "Budi Santoso"
        self.set_state({"user_id": new_id, "name": new_name})

    def render(self) -> VirtualNode:
        """
        Declarative UI Tree (menyerupai JSX):
        <View style={[styles.container, { backgroundColor }]}>
            <View style={[styles.headerBox, { backgroundColor: surface }]}>
                <Text style={{ fontWeight: 'bold' }}>{name} ({role})</Text>
                <Text>ID: #{user_id} | Status: Active</Text>
            </View>
            <View style={styles.metricCard}>
                <Text>Session Heartbeats: {counter}</Text>
                <TouchableOpacity title="Increment Beat" />
            </View>
        </View>
        """
        current_theme = THEMES[self.theme_name]
        theme_colors = current_theme["colors"]

        # Container Root
        root_style = [
            self.static_styles["container"],
            {"backgroundColor": theme_colors["background"]}
        ]

        # Header Node
        header_style = [
            self.static_styles["headerBox"],
            {"backgroundColor": theme_colors["surface"]}
        ]
        header_node = VirtualNode("View", props={"style": header_style}, children=[
            VirtualNode("Text", props={
                "children": f"{self.state['name']} - {self.state['role']}",
                "style": {"fontWeight": "bold", "color": theme_colors["text"]}
            }),
            VirtualNode("Text", props={
                "children": f"User UID: #{self.state['user_id']} | Status: {'ONLINE' if self.state['is_active'] else 'IDLE'}",
                "style": {"color": theme_colors["mutedText"]}
            })
        ])

        # Metrics Card Node
        metric_style = [
            self.static_styles["metricCard"],
            {"backgroundColor": theme_colors["surface"]}
        ]
        metric_node = VirtualNode("View", props={"style": metric_style}, children=[
            VirtualNode("Text", props={
                "children": f"Activity Counter: {self.state['counter']} ticks",
                "style": {"color": theme_colors["primary"], "fontWeight": "bold"}
            }),
            VirtualNode("TouchableOpacity", props={
                "title": "Trigger Action",
                "children": "TAP TO SYNC DATA"
            })
        ])

        root = VirtualNode("View", props={"style": root_style}, children=[header_node, metric_node])
        return root


# ==========================================
# 6. Interactive CLI Application Loop
# ==========================================
def render_screen(app: UserProfileDashboard):
    print(f"\n{Colors.DARK_GRAY}────────────────────────────────────────────────────────────────────────────────{Colors.RESET}")
    print(f"{Colors.BOLD}Tampilan Virtual DOM & Yoga Layout Output (Tema: {app.theme_name.upper()}):{Colors.RESET}")

    # 1. Render Declarative Tree
    vtree = app.render()
    # 2. Yoga Layout Phase
    vtree.compute_layout(parent_width=64, start_y=0)
    # 3. Terminal ASCII Representation
    for line in vtree.render_ascii():
        print(line)

    print(f"{Colors.DARK_GRAY}────────────────────────────────────────────────────────────────────────────────{Colors.RESET}")


def interactive_session():
    print_banner()
    print(f"{Colors.GRAY}Inisialisasi Runtime React Native Native-Fiber Simulation...{Colors.RESET}")
    time.sleep(0.3)

    app = UserProfileDashboard(initial_theme="dark")
    app.mount()
    render_screen(app)

    menu = f"""
{Colors.CYAN}{Colors.BOLD}[PILIHAN MENU INTERAKTIF]{Colors.RESET}
  1. Increment Counter (Uji State Update & Virtual DOM Re-render)
  2. Ganti Tema Light/Dark (Uji StyleSheet Dynamic Token Resolution)
  3. Ganti Akun Pengguna (Uji useEffect Dependency Trigger & Cleanup)
  4. Inspect StyleSheet Registry (Bongkar Struktur Memory ID & Flattening)
  5. Unmount Component & Keluar (Uji Siklus Hidup Unmounting)
"""

    while True:
        print(menu)
        choice = input(f"{Colors.YELLOW}Pilih opsi [1-5]: {Colors.RESET}").strip()

        if choice == "1":
            print(f"\n{Colors.BLUE}==> Memicu aksi setState({{ counter }}){Colors.RESET}")
            app.increment_metric()
            render_screen(app)
        elif choice == "2":
            print(f"\n{Colors.BLUE}==> Memicu perubahan Theme Provider{Colors.RESET}")
            app.toggle_theme()
            render_screen(app)
        elif choice == "3":
            print(f"\n{Colors.BLUE}==> Mengganti User ID (Memicu perubahan dependensi useEffect){Colors.RESET}")
            app.switch_user()
            render_screen(app)
        elif choice == "4":
            print(f"\n{Colors.MAGENTA}=== REGISTRY STYLESHEET CACHE ==={Colors.RESET}")
            print(f"Total Cached Styles: {len(StyleSheet._registry)}")
            for sid, val in StyleSheet._registry.items():
                print(f"  [ID {sid}]: {json.dumps(val)}")
        elif choice == "5":
            print(f"\n{Colors.RED}==> Melepas komponen dari root container...{Colors.RESET}")
            app.unmount()
            print(f"\n{Colors.GREEN}Simulasi selesai. Semua siklus hidup terverifikasi aman.{Colors.RESET}\n")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan masukkan angka 1 - 5.{Colors.RESET}")


if __name__ == "__main__":
    interactive_session()
