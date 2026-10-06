#!/usr/bin/env python3
"""
Lab Exercise: SwiftUI Reactive Data Flow & State Management Engine Simulation
BAB 03: State Management & Data Flow Reaktif

Simulasi teknis mandiri (in-memory) untuk mekanisme internal SwiftUI:
1. @State & Storage Allocation (Single Source of Truth)
2. @Binding (Two-Way Proxy Projection)
3. ObservableObject & @Published / @Observable (Publisher-Subscriber Pipeline)
4. View Graph Invalidation & Granular Re-rendering (Dirty Flags)
5. @EnvironmentObject (Contextual Dependency Injection)
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Set

# --- ANSI Color Codes ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
BG_DARK = "\033[40m"


class StateGraphEngine:
    """Mesin pelacak ketergantungan reaktif (SwiftUI View Dependency Graph)."""
    _current_evaluating_view: Optional["View"] = None

    def __init__(self) -> None:
        # Menghubungkan id state ke view IDs yang membacanya
        self.subscribers: Dict[int, Set["View"]] = {}
        self.render_count: int = 0

    def register_access(self, state_id: int) -> None:
        """Mencatat dependensi saat properti State dibaca oleh View.body."""
        if self._current_evaluating_view is not None:
            if state_id not in self.subscribers:
                self.subscribers[state_id] = set()
            self.subscribers[state_id].add(self._current_evaluating_view)

    def notify_change(self, state_id: int, old_val: Any, new_val: Any, name: str) -> None:
        """Memvalidasi dan menandai dirty bit pada view yang terhubung."""
        print(f"  {YELLOW}⚡ [State Mutation]{RESET} '{BOLD}{name}{RESET}': {RED}{old_val}{RESET} -> {GREEN}{new_val}{RESET}")
        target_views = self.subscribers.get(state_id, set())
        if not target_views:
            print(f"  {DIM}  ↳ Tidak ada view terikat (orphan state){RESET}")
            return
        
        for view in target_views:
            view.mark_dirty()


GLOBAL_ENGINE = StateGraphEngine()


class State:
    """Simulasi Property Wrapper @State."""
    _counter = 0

    def __init__(self, wrapped_value: Any, name: str = "State") -> None:
        State._counter += 1
        self._id = State._counter
        self._value = wrapped_value
        self.name = name

    @property
    def wrapped_value(self) -> Any:
        GLOBAL_ENGINE.register_access(self._id)
        return self._value

    @wrapped_value.setter
    def wrapped_value(self, new_value: Any) -> None:
        if self._value != new_value:
            old = self._value
            self._value = new_value
            GLOBAL_ENGINE.notify_change(self._id, old, new_value, self.name)

    @property
    def projected_value(self) -> "Binding":
        """Sintaks projection '$' pada SwiftUI untuk menghasilkan Binding."""
        return Binding(
            get=lambda: self.wrapped_value,
            set=lambda val: setattr(self, "wrapped_value", val),
            name=f"${self.name}"
        )


class Binding:
    """Simulasi Property Wrapper @Binding (Two-Way Read/Write Proxy)."""

    def __init__(self, get: Callable[[], Any], set: Callable[[Any], None], name: str = "Binding") -> None:
        self._get = get
        self._set = set
        self.name = name

    @property
    def wrapped_value(self) -> Any:
        return self._get()

    @wrapped_value.setter
    def wrapped_value(self, val: Any) -> None:
        self._set(val)


class ObservableObject:
    """Simulasi protokol ObservableObject dengan Publisher objectWillChange."""

    def __init__(self) -> None:
        self._listeners: List[Callable[[], None]] = []

    def object_will_change(self) -> None:
        for listener in self._listeners:
            listener()

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)


class Published:
    """Simulasi Property Wrapper @Published yang mentrigger objectWillChange."""

    def __init__(self, initial_value: Any, name: str = "Published") -> None:
        self.name = name
        self.initial_value = initial_value
        self.values: Dict[int, Any] = {}

    def __set_name__(self, owner: Any, name: str) -> None:
        self.name = name

    def __get__(self, instance: Any, owner: Any) -> Any:
        if instance is None:
            return self
        if id(instance) not in self.values:
            self.values[id(instance)] = self.initial_value
        return self.values[id(instance)]

    def __set__(self, instance: Any, value: Any) -> None:
        if id(instance) not in self.values:
            self.values[id(instance)] = self.initial_value
        old_val = self.values.get(id(instance), None)
        if old_val != value:
            if isinstance(instance, ObservableObject):
                instance.object_will_change()
            self.values[id(instance)] = value
            print(f"  {MAGENTA}📡 [@Published Emit]{RESET} {instance.__class__.__name__}.{self.name}: {RED}{old_val}{RESET} -> {GREEN}{value}{RESET}")


class EnvironmentStorage:
    """Simulasi Environment container untuk @EnvironmentObject."""
    _registry: Dict[type, Any] = {}

    @classmethod
    def inject(cls, obj: Any) -> None:
        cls._registry[type(obj)] = obj
        print(f"  {BLUE}📦 [Environment]{RESET} Injected instance of {BOLD}{type(obj).__name__}{RESET}")

    @classmethod
    def resolve(cls, target_type: type) -> Any:
        if target_type not in cls._registry:
            raise RuntimeError(f"EnvironmentObject {target_type.__name__} tidak ditemukan di hierarki view!")
        return cls._registry[target_type]


class View:
    """Struktur dasar komponen SwiftUI View."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.is_dirty: bool = True
        self.last_rendered_content: str = ""

    def mark_dirty(self) -> None:
        self.is_dirty = True
        print(f"    {CYAN}↻ [Invalidate View]{RESET} '{BOLD}{self.name}{RESET}' ditandai DIRTY -> dijadwalkan untuk re-render.")

    def render(self) -> None:
        if not self.is_dirty:
            print(f"    {DIM}⏭ [Skip Render]{RESET} '{self.name}' bersih (state tidak berubah).")
            return

        GLOBAL_ENGINE.render_count += 1
        prev_view = StateGraphEngine._current_evaluating_view
        StateGraphEngine._current_evaluating_view = self
        
        try:
            self.last_rendered_content = self.body()
            self.is_dirty = False
            print(f"    {GREEN}✔ [Rendered Body]{RESET} '{BOLD}{self.name}{RESET}' -> {self.last_rendered_content}")
        finally:
            StateGraphEngine._current_evaluating_view = prev_view

    def body(self) -> str:
        raise NotImplementedError("Setiap View wajib mengimplementasikan property body()")


# --- Mock View Hierarchy & Domain Model ---

class AppTheme(ObservableObject):
    """Observable data model terpusat."""
    dark_mode = Published(True, name="dark_mode")
    accent_color = Published("OceanBlue", name="accent_color")


class ToggleSwitchView(View):
    """Child View yang hanya menerima @Binding boolean."""
    def __init__(self, is_active_binding: Binding) -> None:
        super().__init__("ToggleSwitchView")
        self.is_active_binding = is_active_binding

    def toggle(self) -> None:
        print(f"\n{BOLD}>> Interaksi User: Klik Saklar ToggleSwitchView <<{RESET}")
        self.is_active_binding.wrapped_value = not self.is_active_binding.wrapped_value

    def body(self) -> str:
        val = self.is_active_binding.wrapped_value
        status_badge = f"{GREEN}[ON]{RESET}" if val else f"{RED}[OFF]{RESET}"
        return f"<Toggle Status={status_badge}>"


class CounterDisplayView(View):
    """Child View yang hanya bergantung pada nilai integer counter."""
    def __init__(self, count_binding: Binding) -> None:
        super().__init__("CounterDisplayView")
        self.count_binding = count_binding

    def increment(self) -> None:
        print(f"\n{BOLD}>> Interaksi User: Klik Tombol (+) CounterDisplayView <<{RESET}")
        self.count_binding.wrapped_value += 1

    def body(self) -> str:
        return f"<Counter Badge='Value: {BOLD}{self.count_binding.wrapped_value}{RESET}'>"


class StatusSummaryView(View):
    """View pengamat @EnvironmentObject global."""
    def __init__(self) -> None:
        super().__init__("StatusSummaryView")
        self.theme: AppTheme = EnvironmentStorage.resolve(AppTheme)
        self.theme.add_listener(self.mark_dirty)

    def body(self) -> str:
        mode = "DARK" if self.theme.dark_mode else "LIGHT"
        return f"<SystemTheme Mode='{mode}' Accent='{self.theme.accent_color}'>"


class DashboardRootView(View):
    """Parent View pembawa Single Source of Truth (@State)."""
    def __init__(self) -> None:
        super().__init__("DashboardRootView")
        self._is_engine_active = State(False, name="is_engine_active")
        self._metrics_count = State(10, name="metrics_count")

        # Inisialisasi child views dengan two-way binding ($)
        self.toggle_subview = ToggleSwitchView(self._is_engine_active.projected_value)
        self.counter_subview = CounterDisplayView(self._metrics_count.projected_value)
        self.status_subview = StatusSummaryView()

    def body(self) -> str:
        # Parent membaca state sendiri
        active_str = "ACTIVE" if self._is_engine_active.wrapped_value else "IDLE"
        return (
            f"[Dashboard Frame: Engine={active_str}, MetricSnapshot={self._metrics_count.wrapped_value}]"
        )

    def render_tree(self) -> None:
        print(f"\n{BLUE}{BOLD}--- Memulai Siklus Render Tree ---{RESET}")
        self.render()
        self.toggle_subview.render()
        self.counter_subview.render()
        self.status_subview.render()
        print(f"{BLUE}{BOLD}----------------------------------{RESET}")


def run_interactive_simulation() -> None:
    """Menjalankan skenario pengujian reaktif."""
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}{CYAN}     SWIFTUI REACTIVE DATA FLOW & STATE GRAPH SIMULATION LAB     {RESET}")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    # 1. Inisialisasi Environment
    theme = AppTheme()
    EnvironmentStorage.inject(theme)

    # 2. Bangun View Hierarchy
    print(f"\n{BOLD}[FASE 1: Inisialisasi Pohon View & Dependency Registration]{RESET}")
    dashboard = DashboardRootView()
    dashboard.render_tree()

    # 3. Mutasi State 1: Mutasi melalui Binding pada child view (Toggle)
    print(f"\n{BOLD}[FASE 2: Mutasi Lewat @Binding (Two-Way Binding)]{RESET}")
    dashboard.toggle_subview.toggle()
    dashboard.render_tree()

    # 4. Mutasi State 2: Mutasi Counter Display
    print(f"\n{BOLD}[FASE 3: Mutasi Counter (Hanya View yang Bergantung yang Render)]{RESET}")
    dashboard.counter_subview.increment()
    dashboard.render_tree()

    # 5. Mutasi State 3: Perubahan Environment / ObservableObject
    print(f"\n{BOLD}[FASE 4: Mutasi Global State via @Published/ObservableObject]{RESET}")
    print(f"\n{BOLD}>> Event: Perubahan preferensi user ke Light Mode & Gold <<{RESET}")
    theme.dark_mode = False
    theme.accent_color = "SunsetGold"
    dashboard.render_tree()

    # 6. Ringkasan Evaluasi Performa
    print(f"\n{BOLD}{GREEN}================================================================={RESET}")
    print(f"{BOLD}{GREEN}                      LAB SELESAI DENGAN SUKSES                  {RESET}")
    print(f"{BOLD}Total siklus evaluasi render: {CYAN}{GLOBAL_ENGINE.render_count}{RESET} pass")
    print(f"Semua prinsip SwiftUI dipenuhi: Single Source of Truth,")
    print(f"Unidirectional Data Flow, & Granular Dependency Invalidation.")
    print(f"{BOLD}{GREEN}================================================================={RESET}\n")


if __name__ == "__main__":
    run_interactive_simulation()
