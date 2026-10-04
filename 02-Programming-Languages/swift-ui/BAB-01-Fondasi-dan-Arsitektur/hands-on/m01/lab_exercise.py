#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Fondasi & Arsitektur Deklaratif SwiftUI
Topik: Declarative Paradigm, View Hierarchy Tree, State & Binding, Diffing Engine, Layout Computation
"""

import sys
import time
from typing import List, Dict, Any, Optional, Callable


# ==============================================================================
# ANSI Color Codes & Terminal Styling
# ==============================================================================
class Color:
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
    BG_DARK = "\033[100m"


# ==============================================================================
# Model State & Binding (Simulasi Property Wrappers SwiftUI: @State & @Binding)
# ==============================================================================
class State:
    """Simulasi @State property wrapper di SwiftUI."""

    def __init__(self, initial_value: Any, name: str = "State"):
        self._value = initial_value
        self.name = name
        self.listeners: List[Callable[[Any], None]] = []

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, new_val: Any):
        if self._value != new_val:
            old_val = self._value
            self._value = new_val
            for listener in self.listeners:
                listener(self._value)


class Binding:
    """Simulasi @Binding property wrapper (Two-way reference)."""

    def __init__(self, get_val: Callable[[], Any], set_val: Callable[[Any], None]):
        self._get = get_val
        self._set = set_val

    @property
    def value(self) -> Any:
        return self._get()

    @value.setter
    def value(self, new_val: Any):
        self._set(new_val)


# ==============================================================================
# Protokol View & Komponen UI (Declarative Components)
# ==============================================================================
class View:
    """Protokol dasar setiap komponen SwiftUI."""

    def __init__(self):
        self.modifiers: Dict[str, Any] = {}

    def body(self) -> "View":
        raise NotImplementedError("Subclass View harus mengimplementasikan body.")

    def padding(self, amount: int = 1) -> "View":
        self.modifiers["padding"] = amount
        return self

    def foreground_color(self, color_code: str) -> "View":
        self.modifiers["color"] = color_code
        return self

    def background(self, bg_code: str) -> "View":
        self.modifiers["background"] = bg_code
        return self

    def render_tree(self, depth: int = 0) -> str:
        """Merender struktur hierarki view menjadi representasi teks."""
        indent = "  " * depth
        mod_info = ""
        if self.modifiers:
            mod_info = f" {Color.DIM}(modifiers: {list(self.modifiers.keys())}){Color.RESET}"
        return f"{indent}{Color.CYAN}• {self.__class__.__name__}{Color.RESET}{mod_info}"


class Text(View):
    def __init__(self, content: str):
        super().__init__()
        self.content = content

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        color = self.modifiers.get("color", Color.WHITE)
        bg = self.modifiers.get("background", "")
        pad = " " * self.modifiers.get("padding", 0)
        styled_text = f"{bg}{color}{pad}\"{self.content}\"{pad}{Color.RESET}"
        return f"{indent}{Color.GREEN}Text{Color.RESET} -> {styled_text}"


class Button(View):
    def __init__(self, label: str, action: Callable[[], None]):
        super().__init__()
        self.label = label
        self.action = action

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        return f"{indent}{Color.YELLOW}[Button: '{self.label}']{Color.RESET} {Color.DIM}(triggers action){Color.RESET}"


class Toggle(View):
    def __init__(self, title: str, is_on: Binding):
        super().__init__()
        self.title = title
        self.is_on = is_on

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        status = f"{Color.GREEN}[ON]{Color.RESET}" if self.is_on.value else f"{Color.RED}[OFF]{Color.RESET}"
        return f"{indent}{Color.MAGENTA}Toggle{Color.RESET}('{self.title}'): {status}"


class VStack(View):
    def __init__(self, *children: View, spacing: int = 1):
        super().__init__()
        self.children = list(children)
        self.spacing = spacing

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        lines = [f"{indent}{Color.BLUE}VStack (spacing: {self.spacing}){Color.RESET}"]
        for child in self.children:
            lines.append(child.render_tree(depth + 1))
        return "\n".join(lines)


class HStack(View):
    def __init__(self, *children: View):
        super().__init__()
        self.children = list(children)

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        lines = [f"{indent}{Color.BLUE}HStack{Color.RESET}"]
        for child in self.children:
            lines.append(child.render_tree(depth + 1))
        return "\n".join(lines)


# ==============================================================================
# Root View Aplikasi Contoh: Counter & Dashboard App
# ==============================================================================
class DashboardView(View):
    def __init__(self):
        super().__init__()
        self.counter_state = State(0, "counter")
        self.dark_mode_state = State(False, "darkMode")
        self.notifications_state = State(True, "notifications")

    def toggle_dark_mode_binding(self) -> Binding:
        return Binding(
            get_val=lambda: self.dark_mode_state.value,
            set_val=lambda v: setattr(self.dark_mode_state, "value", v)
        )

    def toggle_notifications_binding(self) -> Binding:
        return Binding(
            get_val=lambda: self.notifications_state.value,
            set_val=lambda v: setattr(self.notifications_state, "value", v)
        )

    def body(self) -> View:
        # Deklarasi layout reaktif berdasarkan state saat ini
        theme_title = "Dark Theme Enabled" if self.dark_mode_state.value else "Light Theme Active"
        theme_color = Color.MAGENTA if self.dark_mode_state.value else Color.CYAN
        status_label = f"Score Counter: {self.counter_state.value}"

        return VStack(
            Text("=== SWIFTUI DECLARATIVE HIERARCHY ===").foreground_color(Color.BOLD + Color.YELLOW),
            Text(theme_title).foreground_color(theme_color).padding(1),
            HStack(
                Text(status_label).foreground_color(Color.GREEN),
                Button("Increment (+1)", action=lambda: setattr(self.counter_state, "value", self.counter_state.value + 1)),
                Button("Reset (0)", action=lambda: setattr(self.counter_state, "value", 0))
            ),
            Toggle("Dark Mode", self.toggle_dark_mode_binding()),
            Toggle("Push Notifications", self.toggle_notifications_binding()),
            spacing=1
        )


# ==============================================================================
# SwiftUI Engine Simulator: Diffing, Lifecycle, & Re-evaluation
# ==============================================================================
class SwiftUIRuntime:
    def __init__(self, root_view: DashboardView):
        self.root = root_view
        self.render_count = 0
        self.last_rendered_tree: Optional[str] = None

        # Hubungkan listener perubahan state agar runtime otomatis re-render (Re-evaluation of body)
        self.root.counter_state.listeners.append(self.on_state_change)
        self.root.dark_mode_state.listeners.append(self.on_state_change)
        self.root.notifications_state.listeners.append(self.on_state_change)

    def on_state_change(self, new_val: Any):
        print(f"\n{Color.YELLOW}[State Graph Invalidation]{Color.RESET} Sinyal perubahan state terdeteksi: {new_val}")
        print(f"{Color.DIM}-> Memanggil body re-evaluation & Virtual DOM/View diffing...{Color.RESET}")

    def render(self):
        self.render_count += 1
        current_tree = self.root.body().render_tree(depth=1)

        print("\n" + "=" * 65)
        print(f"{Color.BOLD}{Color.WHITE}SWIFTUI VIEW RUNTIME ENGINE (Render Cycle #{self.render_count}){Color.RESET}")
        print("=" * 65)

        # Diffing check
        if self.last_rendered_tree is None:
            print(f"{Color.GREEN}[Initial Render]{Color.RESET} Membuat view tree baru dari struct body:")
        elif self.last_rendered_tree == current_tree:
            print(f"{Color.DIM}[Diffing Engine] Tidak ada perubahan layout visual.{Color.RESET}")
        else:
            print(f"{Color.MAGENTA}[Diffing Reconciled]{Color.RESET} Perubahan terdeteksi, hanya subtree relevan yang dirender ulang.")

        print("-" * 65)
        print(current_tree)
        print("-" * 65)
        self.last_rendered_tree = current_tree


# ==============================================================================
# Interactive Terminal Loop
# ==============================================================================
def main():
    print(f"{Color.BOLD}{Color.CYAN}Memulai Hands-On Lab: SwiftUI Core Foundation Simulator{Color.RESET}")
    print(f"{Color.DIM}Mendemonstrasikan: Declarative UI, View Tree, @State, @Binding, Diffing.{Color.RESET}\n")
    time.sleep(0.5)

    app_view = DashboardView()
    runtime = SwiftUIRuntime(app_view)

    # Initial Render
    runtime.render()

    while True:
        print(f"\n{Color.BOLD}Pilihan Interaksi SwiftUI Simulator:{Color.RESET}")
        print(f"  {Color.GREEN}1{Color.RESET}. Tekan Tombol 'Increment (+1)' (Mutasi @State counter)")
        print(f"  {Color.GREEN}2{Color.RESET}. Tekan Tombol 'Reset (0)' (Reset @State counter)")
        print(f"  {Color.GREEN}3{Color.RESET}. Toggle Switch 'Dark Mode' (Two-way @Binding)")
        print(f"  {Color.GREEN}4{Color.RESET}. Toggle Switch 'Push Notifications' (Two-way @Binding)")
        print(f"  {Color.GREEN}5{Color.RESET}. Inspeksi State Graph Saat Ini")
        print(f"  {Color.RED}q{Color.RESET}. Keluar")

        try:
            choice = input(f"\n{Color.BOLD}Pilih opsi [1-5 / q]: {Color.RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            app_view.counter_state.value += 1
            runtime.render()
        elif choice == "2":
            app_view.counter_state.value = 0
            runtime.render()
        elif choice == "3":
            binding = app_view.toggle_dark_mode_binding()
            binding.value = not binding.value
            runtime.render()
        elif choice == "4":
            binding = app_view.toggle_notifications_binding()
            binding.value = not binding.value
            runtime.render()
        elif choice == "5":
            print(f"\n{Color.CYAN}--- STATUS GRAPH @STATE ---{Color.RESET}")
            print(f"• counter_state: {app_view.counter_state.value}")
            print(f"• dark_mode_state: {app_view.dark_mode_state.value}")
            print(f"• notifications_state: {app_view.notifications_state.value}")
            print(f"• Total Render Cycles: {runtime.render_count}")
        elif choice == "q":
            print(f"\n{Color.GREEN}Selesai. Lab SwiftUI Architecture Simulator berhasil dijalankan.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan coba lagi.{Color.RESET}")


if __name__ == "__main__":
    main()
