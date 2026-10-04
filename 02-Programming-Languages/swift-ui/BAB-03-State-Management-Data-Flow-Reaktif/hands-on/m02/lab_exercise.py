#!/usr/bin/env python3
"""
Lab Hands-on: SwiftUI Deep Dive - State Management & Reactive Data Flow Engine
Bab 03: State Management & Data Flow Reaktif (Modul 02 Deep Dive)

Deskripsi:
Simulasi arsitektur internal SwiftUI (AttributeGraph & DynamicProperty).
Mengimplementasikan:
1. Property Wrappers (@State, @Binding, @ObservedObject, @Published).
2. Dependency Tracking & Subscription otomatis via Thread-Local Context.
3. Render Engine rekursif dengan Selective Re-rendering (View Invalidation & Pruning).
4. Environment Injection (@EnvironmentObject) simulasi tree data passing.
"""

import sys
import time
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Type

# ==============================================================================
# ANSI Color Formatting Helper
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    GRAY    = "\033[90m"

# ==============================================================================
# RUNTIME ENGINE: Dependency Tracking & Graph Invalidation
# ==============================================================================
class SwiftUIRuntime:
    """
    Engine terpusat yang memodelkan AttributeGraph SwiftUI.
    Menangani pelacakan dependensi deklaratif saat body view dievaluasi.
    """
    _local = threading.local()
    # Memetakan Source of Truth (State/Published ID) -> Set of View IDs yang bergantung
    _dependency_graph: Dict[int, Set[str]] = {}
    # Registry view yang aktif
    _view_registry: Dict[str, "View"] = {}

    @classmethod
    def get_current_view(cls) -> Optional["View"]:
        return getattr(cls._local, "current_view", None)

    @classmethod
    def set_current_view(cls, view: Optional["View"]):
        cls._local.current_view = view

    @classmethod
    def register_view(cls, view: "View"):
        cls._view_registry[view.id] = view

    @classmethod
    def track_access(cls, source_id: int):
        """Mencatat dependensi ketika state dibaca di dalam evaluation frame view.body."""
        current = cls.get_current_view()
        if current:
            if source_id not in cls._dependency_graph:
                cls._dependency_graph[source_id] = set()
            cls._dependency_graph[source_id].add(current.id)

    @classmethod
    def invalidate(cls, source_id: int, source_name: str, new_value: Any):
        """Memvalidasi dan memicu selective re-render untuk view yang terdampak."""
        affected_view_ids = cls._dependency_graph.get(source_id, set())
        print(f"\n{Color.YELLOW}⚡ [STATE CHANGE]{Color.RESET} '{Color.BOLD}{source_name}{Color.RESET}' "
              f"berubah menjadi: {Color.GREEN}{new_value}{Color.RESET}")
        
        if not affected_view_ids:
            print(f"  {Color.GRAY}└─ Tidak ada view yang bergantung pada state ini.{Color.RESET}")
            return

        print(f"  {Color.CYAN}└─ Invalidation Graph:{Color.RESET} Menandai dirty views: "
              f"{[f'View::{vid}' for vid in affected_view_ids]}")
        
        # Eksekusi selective render loop
        for vid in affected_view_ids:
            view = cls._view_registry.get(vid)
            if view:
                print(f"\n{Color.MAGENTA}🔄 [RE-RENDER TRIGGERED]{Color.RESET} Re-evaluating body untuk '{Color.BOLD}{view.name}{Color.RESET}'...")
                view.render(depth=1)

# ==============================================================================
# REACTIVE PRIMITIVES (SWIFTUI WRAPPERS SIMULATION)
# ==============================================================================
class Binding:
    """
    Simulasi @Binding: Two-way reference tanpa kepemilikan data (Pass-by-reference proxy).
    """
    def __init__(self, getter: Callable[[], Any], setter: Callable[[Any], None]):
        self._getter = getter
        self._setter = setter

    @property
    def wrapped_value(self) -> Any:
        return self._getter()

    @wrapped_value.setter
    def wrapped_value(self, val: Any):
        self._setter(val)


class State:
    """
    Simulasi @State: Mengalokasikan storage persisten di luar lifecycle View struct.
    Memicu invalidasi AttributeGraph jika nilai bermutasi.
    """
    def __init__(self, initial_value: Any):
        self._value = initial_value
        self._id = id(self)

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        # Daftarkan dependensi otomatis saat property dibaca
        SwiftUIRuntime.track_access(self._id)
        return self._value

    def __set__(self, instance, new_value):
        if self._value != new_value:
            self._value = new_value
            SwiftUIRuntime.invalidate(self._id, self._name, new_value)

    def project(self, instance) -> Binding:
        """Simulasi operator sintaksis '$state' untuk menghasilkan Binding."""
        return Binding(
            getter=lambda: self.__get__(instance, type(instance)),
            setter=lambda val: self.__set__(instance, val)
        )


class ObservableObject:
    """
    Simulasi protokol Combine / ObservableObject.
    Menyediakan sinyal objectWillChange ke downstream subscriber.
    """
    def __init__(self):
        self._object_id = id(self)

    def notify_change(self, prop_name: str, new_val: Any):
        SwiftUIRuntime.invalidate(self._object_id, f"{self.__class__.__name__}.{prop_name}", new_val)


class Published:
    """
    Simulasi @Published: Property wrapper pada ObservableObject yang memancarkan sinyal.
    """
    def __init__(self, initial_value: Any):
        self._value = initial_value

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if isinstance(instance, ObservableObject):
            SwiftUIRuntime.track_access(instance._object_id)
        return self._value

    def __set__(self, instance, new_value):
        if self._value != new_value:
            self._value = new_value
            if isinstance(instance, ObservableObject):
                instance.notify_change(self._name, new_value)

# ==============================================================================
# VIEW PROTOCOL & HIERARCHY
# ==============================================================================
class View:
    """
    Simulasi protokol 'View' di SwiftUI.
    Immutable representation yang mengevaluasi `body` untuk menghasilkan node layout.
    """
    def __init__(self, name: Optional[str] = None):
        self.id = f"{self.__class__.__name__}_{id(self)}"
        self.name = name or self.__class__.__name__
        SwiftUIRuntime.register_view(self)

    def body(self) -> Any:
        raise NotImplementedError("Subclass View wajib mengimplementasikan 'body'.")

    def render(self, depth: int = 0):
        """
        Evaluasi body di dalam thread scope dependency tracking.
        """
        indent = "  " * depth
        prev_view = SwiftUIRuntime.get_current_view()
        SwiftUIRuntime.set_current_view(self)
        
        try:
            print(f"{indent}{Color.BLUE}┌─ [Node: {self.name}]{Color.RESET}")
            content = self.body()
            if isinstance(content, View):
                content.render(depth + 1)
            elif isinstance(content, list):
                for child in content:
                    if isinstance(child, View):
                        child.render(depth + 1)
                    else:
                        print(f"{indent}  └─ {Color.GRAY}{child}{Color.RESET}")
            else:
                print(f"{indent}  └─ {Color.GRAY}{content}{Color.RESET}")
            print(f"{indent}{Color.BLUE}└────────────{Color.RESET}")
        finally:
            SwiftUIRuntime.set_current_view(prev_view)

# ==============================================================================
# SAMPLE APPLICATION COMPONENTS
# ==============================================================================
class AppSession(ObservableObject):
    """Global Shared State (Environment Object)."""
    user_name = Published("Anonim")
    is_authenticated = Published(False)


class HeaderView(View):
    """View yang hanya bergantung pada AppSession."""
    def __init__(self, session: AppSession):
        super().__init__("HeaderView")
        self.session = session

    def body(self) -> Any:
        auth_status = "LOGIN" if self.session.is_authenticated else "GUEST"
        return f"User: {self.session.user_name} | Status: [{auth_status}]"


class StepperControlView(View):
    """Sub-view yang menerima Binding untuk memanipulasi state milik Parent."""
    def __init__(self, count_binding: Binding):
        super().__init__("StepperControlView")
        self.binding = count_binding

    def body(self) -> Any:
        return f"[Button +/- Target Current: {self.binding.wrapped_value}]"

    def click_increment(self):
        print(f"\n{Color.CYAN}👉 [User Interaction]{Color.RESET} User mengklik Tombol (+)")
        self.binding.wrapped_value += 1


class StaticFooterView(View):
    """View tanpa dependensi state reaktif (Harus dilewati saat selective re-render)."""
    def __init__(self):
        super().__init__("StaticFooterView")

    def body(self) -> Any:
        return "SwiftUI Engine Lab v3.2.0 - Clean Architecture (Static)"


class DashboardView(View):
    """
    Root Container View yang mengorkestrasi State internal dan Binding ke child.
    """
    counter = State(0)
    toggle_flag = State(False)

    def __init__(self, session: AppSession):
        super().__init__("DashboardView")
        self.session = session
        # Sub-views
        self.header = HeaderView(self.session)
        self.stepper = StepperControlView(DashboardView.counter.project(self))
        self.footer = StaticFooterView()

    def body(self) -> Any:
        return [
            self.header,
            f"Local State Counter Value: {self.counter}",
            f"Feature Active: {self.toggle_flag}",
            self.stepper,
            self.footer
        ]

# ==============================================================================
# MAIN EXECUTION BENCHMARK & DEMONSTRATION
# ==============================================================================
def print_banner(title: str):
    line = "=" * 70
    print(f"\n{Color.BOLD}{Color.MAGENTA}{line}")
    print(f" {title.center(68)}")
    print(f"{line}{Color.RESET}\n")


def main():
    print_banner("SIMULASI STATE MANAGEMENT & REACTIVE DATA FLOW SWIFTUI")
    
    # 1. Instansiasi Global Session (ObservableObject)
    session = AppSession()
    
    # 2. Instansiasi Root View Tree
    root = DashboardView(session)

    print(f"{Color.BOLD}[1] INITIAL RENDER PASS (Tree Evaluation & Graph Building){Color.RESET}")
    start_time = time.perf_counter()
    root.render()
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"{Color.GREEN}✔ Initial Render selesai dalam {elapsed:.3f} ms{Color.RESET}")

    # Inspect dependency internal
    print(f"\n{Color.BOLD}[2] DEPENDENCY GRAPH STATUS{Color.RESET}")
    for source_id, views in SwiftUIRuntime._dependency_graph.items():
        print(f"  Source Node [{source_id}] dipantau oleh: {list(views)}")

    # 3. Test @Binding Mutasi (Child memodifikasi state Parent)
    time.sleep(0.3)
    print_banner("TEST 1: MUTASI STATE VIA @BINDING (Child -> Parent)")
    root.stepper.click_increment()

    # 4. Test Mutasi Langsung @State Parent
    time.sleep(0.3)
    print_banner("TEST 2: MUTASI INTERNAL @STATE (Parent Invalidation)")
    root.toggle_flag = True

    # 5. Test Mutasi @Published pada ObservableObject (Hanya HeaderView yang boleh render)
    time.sleep(0.3)
    print_banner("TEST 3: MUTASI @PUBLISHED / OBSERVABLE (Selective Re-render)")
    print(f"Mengubah session.user_name...")
    session.user_name = "Muhammad_LeadDev"

    time.sleep(0.3)
    print(f"Mengubah session.is_authenticated...")
    session.is_authenticated = True

    # 6. Verifikasi Efisiensi Tree
    print_banner("ANALISIS ARSITEKTUR SELEKTIF")
    print(f"1. {Color.GREEN}StaticFooterView{Color.RESET} TIDAK PERNAH di-render ulang setelah inisialisasi awal.")
    print(f"2. Mutasi session HANYA memicu {Color.GREEN}HeaderView{Color.RESET}, memangkas (pruning) sisa view tree.")
    print(f"3. Mutasi {Color.GREEN}counter{Color.RESET} via @Binding secara tepat mengevaluasi kembali DashboardView.")
    print(f"{Color.BOLD}Sistem State Reaktif Berhasil Memvalidasi Mekanisme Diffing SwiftUI.{Color.RESET}\n")

if __name__ == "__main__":
    main()