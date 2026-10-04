#!/usr/bin/env python3
"""
Lab Hands-on: SwiftUI Interoperabilitas Ekosistem (Bridge UIKit & AppKit)
Simulasi Runtime: UIViewRepresentable, Coordinator Pattern, Two-Way Binding, 
dan Lifecycle Synchronization Engine.
"""

import sys
import time
from typing import Any, Callable, Dict, Optional, Type

# ==============================================================================
# ANSI Formatting Helper
# ==============================================================================
class TerminalColor:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

def log_event(domain: str, action: str, details: str, color: str = TerminalColor.CYAN):
    print(f"{color}[{domain:^12}] {TerminalColor.BOLD}{action:<22}{TerminalColor.RESET} {TerminalColor.DIM}│{TerminalColor.RESET} {details}")

# ==============================================================================
# MOCK UIKIT ENGINE (Imperative Layer)
# ==============================================================================
class TargetAction:
    def __init__(self, target: Any, action_name: str):
        self.target = target
        self.action_name = action_name

    def invoke(self, sender: Any, event_data: Any = None):
        action = getattr(self.target, self.action_name, None)
        if callable(action):
            action(sender, event_data)

class UIView:
    """Kelas dasar yang memodelkan komponen UIKit imperative (Obj-C runtime)."""
    def __init__(self, frame: str = "CGRectZero"):
        self.frame = frame
        self.tag = 0
        self.is_destroyed = False
        self._target_actions: Dict[str, list[TargetAction]] = {}

    def add_target(self, target: Any, action_name: str, event: str):
        if event not in self._target_actions:
            self._target_actions[event] = []
        self._target_actions[event].append(TargetAction(target, action_name))

    def trigger_event(self, event: str, payload: Any = None):
        if self.is_destroyed:
            raise RuntimeError("Attempted to dispatch event on dismantled UIView!")
        for ta in self._target_actions.get(event, []):
            ta.invoke(self, payload)

    def dealloc(self):
        self.is_destroyed = True
        self._target_actions.clear()

class UISlider(UIView):
    """Representasi komponen kontrol UIKit imperatif."""
    def __init__(self):
        super().__init__(frame="CGRect(x:0, y:0, width:200, height:30)")
        self._value: float = 0.0
        self.minimum_value: float = 0.0
        self.maximum_value: float = 100.0

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, new_val: float):
        clamped = max(self.minimum_value, min(self.maximum_value, new_val))
        if self._value != clamped:
            self._value = clamped

    def simulate_user_drag(self, new_val: float):
        """Simulasi interaksi fisik pengguna pada layar sentuh (UIKit Responder Chain)."""
        self.value = new_val
        self.trigger_event("valueChanged", payload=self.value)

# ==============================================================================
# SWIFTUI DECLARATIVE INFRASTRUCTURE
# ==============================================================================
class Binding:
    """Simulasi property wrapper @Binding dua arah SwiftUI."""
    def __init__(self, getter: Callable[[], Any], setter: Callable[[Any], None]):
        self._get = getter
        self._set = setter

    @property
    def wrapped_value(self) -> Any:
        return self._get()

    @wrapped_value.setter
    def wrapped_value(self, val: Any):
        self._set(val)

class Context:
    """Context pembungkus runtime yang diteruskan ke UIViewRepresentable."""
    def __init__(self, coordinator: Any, environment: Dict[str, Any]):
        self.coordinator = coordinator
        self.environment = environment

class UIViewRepresentable:
    """
    Protokol Bridge: Menjembatani declarative view tree SwiftUI dengan 
    lifecycle imperative UIView/AppKit.
    """
    def make_coordinator(self) -> Any:
        return None

    def make_ui_view(self, context: Context) -> UIView:
        raise NotImplementedError

    def update_ui_view(self, ui_view: UIView, context: Context):
        raise NotImplementedError

    def dismantle_ui_view(self, ui_view: UIView, coordinator: Any):
        # Default implementation (SwiftUI lifecycle)
        pass

# ==============================================================================
# USER IMPLEMENTATION: Custom Slider Bridge with Coordinator
# ==============================================================================
class SliderBridge(UIViewRepresentable):
    """
    Implementasi konkret pengembang: Membungkus UISlider ke SwiftUI.
    Menggunakan Coordinator untuk mendengarkan Target-Action UIKit dan memutasi State.
    """
    class Coordinator:
        def __init__(self, value_binding: Binding):
            self.value_binding = value_binding
            self.total_mutations = 0

        # Objective-C Target-Action handler: @objc func sliderValueChanged(_ sender: UISlider)
        def slider_value_changed(self, sender: UISlider, event_data: Any):
            self.total_mutations += 1
            log_event("COORDINATOR", "Target-Action Fired", 
                      f"UIKit value {sender.value:.1f} -> Updating SwiftUI @Binding", 
                      TerminalColor.YELLOW)
            self.value_binding.wrapped_value = sender.value

    def __init__(self, value_binding: Binding):
        self.value_binding = value_binding

    def make_coordinator(self) -> Coordinator:
        return SliderBridge.Coordinator(self.value_binding)

    def make_ui_view(self, context: Context) -> UISlider:
        slider = UISlider()
        slider.minimum_value = 0.0
        slider.maximum_value = 100.0
        # Mendaftarkan coordinator target ke target-action event
        slider.add_target(context.coordinator, "slider_value_changed", "valueChanged")
        return slider

    def update_ui_view(self, ui_view: UISlider, context: Context):
        # Update hanya jika terjadi delta state untuk mencegah infinite loop cycle
        current_state = self.value_binding.wrapped_value
        if ui_view.value != current_state:
            log_event("REPRESENTABLE", "updateUIView", 
                      f"Sync declarative state ({current_state:.1f}) -> UIKit frame", 
                      TerminalColor.CYAN)
            ui_view.value = current_state
        else:
            log_event("REPRESENTABLE", "updateUIView [SKIP]", 
                      "Value identical, skipping redundant imperative mutation", 
                      TerminalColor.DIM)

    def dismantle_ui_view(self, ui_view: UISlider, coordinator: Coordinator):
        log_event("REPRESENTABLE", "dismantleUIView", 
                      f"Tear down Target-Action, release coordinator references", 
                      TerminalColor.RED)
        ui_view.dealloc()

# ==============================================================================
# SWIFTUI HOSTING & RECONCILIATION RUNTIME SIMULATOR
# ==============================================================================
class MockSwiftUIRuntime:
    """Simulasi mesin rendering declarative SwiftUI."""
    def __init__(self):
        self._state_store: Dict[str, Any] = {"volume": 25.0}
        self.active_node: Optional[Dict[str, Any]] = None

    def get_state(self, key: str) -> Any:
        return self._state_store[key]

    def set_state(self, key: str, val: Any):
        old_val = self._state_store[key]
        if old_val != val:
            self._state_store[key] = val
            log_event("SWIFTUI-STATE", "@State Changed", 
                      f"Key '${key}' mutasi: {old_val} -> {val}", 
                      TerminalColor.MAGENTA)
            self.reconcile()

    def mount(self, representable_cls: Type[UIViewRepresentable]):
        log_event("RUN-CYCLE", "Mounting Node", "Membuat node Representable ke View Graph", TerminalColor.GREEN)
        binding = Binding(
            getter=lambda: self.get_state("volume"),
            setter=lambda val: self.set_state("volume", val)
        )
        instance = representable_cls(binding)
        coordinator = instance.make_coordinator()
        context = Context(coordinator=coordinator, environment={"colorScheme": "dark"})
        
        ui_view = instance.make_ui_view(context)
        log_event("RUN-CYCLE", "makeUIView", f"Instansiasi native UIView: {ui_view.__class__.__name__}", TerminalColor.GREEN)
        
        # Initial Pass
        instance.update_ui_view(ui_view, context)

        self.active_node = {
            "instance": instance,
            "ui_view": ui_view,
            "coordinator": coordinator,
            "context": context
        }

    def reconcile(self):
        """Memicu declarative layout pass ketika State SwiftUI termutasi."""
        if not self.active_node:
            return
        log_event("RUN-CYCLE", "Reconciliation Pass", "Body re-evaluation dipicu oleh state change", TerminalColor.MAGENTA)
        node = self.active_node
        node["instance"].update_ui_view(node["ui_view"], node["context"])

    def unmount(self):
        """Membersihkan alokasi memory saat Representable dihapus dari tree."""
        if not self.active_node:
            return
        node = self.active_node
        node["instance"].dismantle_ui_view(node["ui_view"], node["coordinator"])
        self.active_node = None
        log_event("RUN-CYCLE", "Unmounted", "View Graph Node berhasil dilepaskan dari memori", TerminalColor.RED)

# ==============================================================================
# MAIN TEST DRIVER / DEMONSTRASI
# ==============================================================================
def main():
    print(f"{TerminalColor.BOLD}=== SwiftUI ⟷ UIKit/AppKit Interoperability Engine Lab ==={TerminalColor.RESET}\n")

    runtime = MockSwiftUIRuntime()

    print(f"{TerminalColor.BOLD}[FASE 1: Lifecycle Initialization & Mounting]{TerminalColor.RESET}")
    runtime.mount(SliderBridge)
    active_view: UISlider = runtime.active_node["ui_view"]
    print(f"State Awal: volume={runtime.get_state('volume')} | UIKit Slider Value={active_view.value}\n")

    print(f"{TerminalColor.BOLD}[FASE 2: SwiftUI Mengubah State Imperative (SwiftUI -> UIKit)]{TerminalColor.RESET}")
    # Mutasi dari sisi deklaratif SwiftUI (misal dari button di view parent)
    runtime.set_state("volume", 75.0)
    print(f"State Hasil: volume={runtime.get_state('volume')} | UIKit Slider Value={active_view.value}\n")

    print(f"{TerminalColor.BOLD}[FASE 3: User Interaction Event Imperatif (UIKit -> SwiftUI via Coordinator)]{TerminalColor.RESET}")
    # User menggeser slider secara fisik di layar UIKit
    log_event("UIKIT-TOUCH", "Touch Drag Event", "Pengguna menggeser slider fisik ke posisi 92.5", TerminalColor.YELLOW)
    active_view.simulate_user_drag(92.5)
    print(f"State Hasil: volume={runtime.get_state('volume')} | UIKit Slider Value={active_view.value}\n")

    print(f"{TerminalColor.BOLD}[FASE 4: Loop Prevention Protection Check]{TerminalColor.RESET}")
    # Simulasikan declarative pass redundant untuk membuktikan idempotency updateUIView
    runtime.reconcile()
    print()

    print(f"{TerminalColor.BOLD}[FASE 5: Teardown & Lifecycle Dismantle]{TerminalColor.RESET}")
    runtime.unmount()

    # Verifikasi status view pasca-dismantle
    assert active_view.is_destroyed is True, "Validation Failed: UIView tidak di-dealloc!"
    print(f"\n{TerminalColor.GREEN}{TerminalColor.BOLD}✔ Eksekusi Lab Sukses: Coordinator Target-Action, Two-Way Binding & Lifecycle Tear Down tervalidasi.{TerminalColor.RESET}")

if __name__ == "__main__":
    main()