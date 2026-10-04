#!/usr/bin/env python3
"""
===============================================================================
LAB EXERCISE M02: ADVANCED SIDE EFFECTS, REFS & IMPERATIVE INTEROP BOUNDARY
SIMULASI ARSITEKTUR RUNTIME PRODUKSI REACT (FIBER COMMIT, REFS & IMPERATIVE HANDLE)
===============================================================================

Topik Pokok Pembahasan:
1. Fiber Lifecycle Pipeline: Render Phase -> Commit Mutation -> LayoutEffect -> Paint -> Passive Effect (useEffect)
2. Dependency Equality & Effect Cleanup (Deterministic Unmount/Remount Lifecycles)
3. Ref Stability & Instance Variables (useRef) vs Reactive State
4. Imperative Interop Boundary: forwardRef + useImperativeHandle memayungi Imperative 3rd-Party SDK (Canvas/Chart)
5. Race Condition Management: Token AbortController & Async Stale Response Discarding
"""

import sys
import time
import uuid
import threading
from typing import Callable, Any, Dict, List, Optional, Tuple

# ANSI Terminal Colors
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


# =============================================================================
# 1. CORE MINI-FIBER & HOOK ENGINE
# =============================================================================

class RefObject:
    def __init__(self, initial_value: Any = None):
        self.current = initial_value

    def __repr__(self):
        return f"RefObject(current={self.current})"


class EffectTag:
    PASSIVE = "PASSIVE_EFFECT"   # useEffect: Async post-paint
    LAYOUT  = "LAYOUT_EFFECT"    # useLayoutEffect: Sync pre-paint


class HookEffect:
    def __init__(self, tag: str, create: Callable[[], Optional[Callable[[], None]]], deps: Optional[List[Any]]):
        self.tag = tag
        self.create = create
        self.deps = deps
        self.destroy: Optional[Callable[[], None]] = None
        self.has_run = False


class FiberNode:
    def __init__(self, name: str):
        self.name = name
        self.hooks: List[Any] = []
        self.hook_index: int = 0
        self.mounted: bool = False
        self.dom_node: Optional[Dict[str, Any]] = None


class ReactRuntimeContext:
    """Simulasi Single-Threaded Event Loop & Work-In-Progress Fiber Dispatcher"""
    def __init__(self):
        self.current_fiber: Optional[FiberNode] = None
        self.passive_effects_queue: List[Tuple[FiberNode, HookEffect]] = []
        self.layout_effects_queue: List[Tuple[FiberNode, HookEffect]] = []

    def are_deps_equal(self, prev_deps: Optional[List[Any]], next_deps: Optional[List[Any]]) -> bool:
        if prev_deps is None or next_deps is None:
            return False
        if len(prev_deps) != len(next_deps):
            return False
        return all(p == n for p, n in zip(prev_deps, next_deps))


# Global Runtime Singleton
_RUNTIME = ReactRuntimeContext()


# =============================================================================
# 2. REACT HOOKS IMPLEMENTATION
# =============================================================================

def use_ref(initial_value: Any = None) -> RefObject:
    fiber = _RUNTIME.current_fiber
    idx = fiber.hook_index
    if len(fiber.hooks) <= idx:
        ref_cell = RefObject(initial_value)
        fiber.hooks.append(ref_cell)
    else:
        ref_cell = fiber.hooks[idx]
    fiber.hook_index += 1
    return ref_cell


def use_effect(create: Callable[[], Optional[Callable[[], None]]], deps: Optional[List[Any]] = None):
    _push_effect(EffectTag.PASSIVE, create, deps)


def use_layout_effect(create: Callable[[], Optional[Callable[[], None]]], deps: Optional[List[Any]] = None):
    _push_effect(EffectTag.LAYOUT, create, deps)


def _push_effect(tag: str, create: Callable[[], Optional[Callable[[], None]]], deps: Optional[List[Any]]):
    fiber = _RUNTIME.current_fiber
    idx = fiber.hook_index

    if len(fiber.hooks) <= idx:
        effect = HookEffect(tag, create, deps)
        fiber.hooks.append(effect)
        should_queue = True
    else:
        prev_effect: HookEffect = fiber.hooks[idx]
        if not _RUNTIME.are_deps_equal(prev_effect.deps, deps):
            effect = HookEffect(tag, create, deps)
            effect.destroy = prev_effect.destroy
            fiber.hooks[idx] = effect
            should_queue = True
        else:
            effect = prev_effect
            should_queue = False

    fiber.hook_index += 1

    if should_queue:
        if tag == EffectTag.LAYOUT:
            _RUNTIME.layout_effects_queue.append((fiber, effect))
        else:
            _RUNTIME.passive_effects_queue.append((fiber, effect))


def use_imperative_handle(ref: RefObject, create_handle: Callable[[], Any], deps: Optional[List[Any]] = None):
    """
    Exposes an imperative handle to the parent component ref.
    Internally registered as a useLayoutEffect to ensure imperative API is attached
    BEFORE parent effects execute.
    """
    def effect_action():
        handle = create_handle()
        ref.current = handle
        def cleanup():
            ref.current = None
        return cleanup

    use_layout_effect(effect_action, deps)


# =============================================================================
# 3. IMPERATIVE THIRD-PARTY ENGINE (e.g., Chart / WebGL / Audio Library)
# =============================================================================

class ImperativeChartSDK:
    """
    Simulasi Third-Party Imperative Library yang bukan bagian dari React.
    Memiliki lifecycle ketat: init() -> updateViewport() -> destroy().
    Jika tidak didestroy saat unmount, akan terjadi memory leak fatal.
    """
    def __init__(self, dom_container_id: str):
        self.container_id = dom_container_id
        self.is_destroyed = False
        self.internal_dataset: List[int] = []
        self.zoom_level = 1.0
        print(f"  {C.YELLOW}[SDK Native Engine]{C.RESET} Instantiating Canvas Context on #{dom_container_id}")

    def render_series(self, data: List[int]):
        if self.is_destroyed:
            raise RuntimeError("Attempted to render to a destroyed Canvas Context!")
        self.internal_dataset = list(data)
        print(f"  {C.YELLOW}[SDK Native Engine]{C.RESET} Re-drawing series: {self.internal_dataset} at zoom={self.zoom_level:.1f}x")

    def zoom_in(self):
        if self.is_destroyed:
            raise RuntimeError("Canvas Context destroyed.")
        self.zoom_level += 0.5
        print(f"  {C.YELLOW}[SDK Native Engine]{C.RESET} Hardware Zoom applied: {self.zoom_level:.1f}x")

    def export_snapshot(self) -> str:
        return f"PNG_BLOB(pts={len(self.internal_dataset)}, zoom={self.zoom_level:.1f})"

    def destroy(self):
        if not self.is_destroyed:
            self.is_destroyed = True
            print(f"  {C.YELLOW}[SDK Native Engine]{C.RESET} GL Context & WebGL Listeners DESTROYED cleanly on #{self.container_id}")


# =============================================================================
# 4. COMPONENTS SIMULATION: IMPERATIVE BOUNDARY & FORWARD REF
# =============================================================================

class ChartWidgetComponent:
    """
    Representasi komponen React:
    const ChartWidget = forwardRef((props, ref) => { ... })
    """
    def __init__(self, fiber: FiberNode):
        self.fiber = fiber

    def render(self, props: Dict[str, Any], external_ref: Optional[RefObject]):
        _RUNTIME.current_fiber = self.fiber
        self.fiber.hook_index = 0

        data_series = props.get("series", [])
        theme = props.get("theme", "dark")

        # 1. Internal Ref to hold the mutable instance of SDK
        sdk_instance_ref = use_ref(None)

        # 2. Layout Effect: Attach SDK synchronously before browser repaint
        def init_or_update_sdk():
            if sdk_instance_ref.current is None:
                sdk = ImperativeChartSDK(f"chart-canvas-{self.fiber.name}")
                sdk_instance_ref.current = sdk
            sdk_instance_ref.current.render_series(data_series)

            def cleanup():
                if sdk_instance_ref.current:
                    sdk_instance_ref.current.destroy()
                    sdk_instance_ref.current = None
            return cleanup

        use_layout_effect(init_or_update_sdk, [data_series])

        # 3. Imperative Interop Boundary: Expose ONLY controlled subset to parent
        if external_ref is not None:
            def create_boundary_handle():
                return {
                    "zoomIn": lambda: sdk_instance_ref.current.zoom_in() if sdk_instance_ref.current else None,
                    "getSnapshot": lambda: sdk_instance_ref.current.export_snapshot() if sdk_instance_ref.current else "N/A",
                    "getDatasetLength": lambda: len(sdk_instance_ref.current.internal_dataset) if sdk_instance_ref.current else 0
                }
            use_imperative_handle(external_ref, create_boundary_handle, [sdk_instance_ref])

        # 4. Passive Effect: Telemetry / Subscriptions
        def log_telemetry():
            print(f"  {C.CYAN}[Passive Effect]{C.RESET} Telemetry: Chart viewed with theme '{theme}' ({len(data_series)} items)")
            def cleanup():
                print(f"  {C.MAGENTA}[Passive Cleanup]{C.RESET} Telemetry session closed for theme '{theme}'")
            return cleanup

        use_effect(log_telemetry, [theme])

        _RUNTIME.current_fiber = None
        return f"<CanvasContainer id='{self.fiber.name}' theme='{theme}' />"


# =============================================================================
# 5. COMMIT & FLUSH PIPELINE (SIMULATING REACT RUNTIME)
# =============================================================================

def execute_commit_cycle(fiber: FiberNode, render_output: str):
    print(f"\n{C.BOLD}{C.BLUE}>>> [REACT COMMIT PIPELINE: START]{C.RESET}")
    print(f"  {C.WHITE}[Phase 1: Render Phase]{C.RESET} Virtual Output: {render_output}")
    print(f"  {C.WHITE}[Phase 2: DOM Mutation]{C.RESET} Mutations applied to Host Tree.")

    # Phase 3: Flush Layout Effects (Synchronous BEFORE Paint)
    print(f"  {C.BOLD}{C.YELLOW}[Phase 3: Synchronous Layout Effects (useLayoutEffect)]{C.RESET}")
    while _RUNTIME.layout_effects_queue:
        target_fiber, effect = _RUNTIME.layout_effects_queue.pop(0)
        # Flush previous cleanup if exists
        if effect.destroy:
            print(f"    {C.MAGENTA}[Layout Cleanup]{C.RESET} Unwinding previous layout effect...")
            effect.destroy()
            effect.destroy = None
        effect.destroy = effect.create()
        effect.has_run = True

    # Phase 4: Browser Paint
    print(f"  {C.GREEN}[Phase 4: Browser Paint & Composite]{C.RESET} Frame rendered on user screen.")

    # Phase 5: Flush Passive Effects (Asynchronous POST Paint)
    print(f"  {C.BOLD}{C.CYAN}[Phase 5: Asynchronous Passive Effects (useEffect)]{C.RESET}")
    while _RUNTIME.passive_effects_queue:
        target_fiber, effect = _RUNTIME.passive_effects_queue.pop(0)
        if effect.destroy:
            print(f"    {C.MAGENTA}[Passive Cleanup]{C.RESET} Running cleanup before new effect...")
            effect.destroy()
            effect.destroy = None
        effect.destroy = effect.create()
        effect.has_run = True

    fiber.mounted = True
    print(f"{C.BOLD}{C.BLUE}<<< [REACT COMMIT PIPELINE: COMPLETE]{C.RESET}\n")


def unmount_fiber(fiber: FiberNode):
    print(f"\n{C.BOLD}{C.RED}>>> [TEARDOWN / UNMOUNT COMPONENT: {fiber.name}]{C.RESET}")
    for hook in reversed(fiber.hooks):
        if isinstance(hook, HookEffect) and hook.destroy:
            tag_name = "Layout" if hook.tag == EffectTag.LAYOUT else "Passive"
            color = C.YELLOW if hook.tag == EffectTag.LAYOUT else C.MAGENTA
            print(f"  {color}[{tag_name} Destroy]{C.RESET} Executing destructor hook...")
            try:
                hook.destroy()
            except Exception as e:
                print(f"  {C.RED}[Error in Cleanup]{C.RESET} {e}")
            hook.destroy = None
    fiber.mounted = False
    print(f"{C.BOLD}{C.RED}<<< [TEARDOWN COMPLETE]{C.RESET}\n")


# =============================================================================
# 6. RACE CONDITION & ASYNC ABORT CONTROLLER SIMULATOR
# =============================================================================

class AbortSignal:
    def __init__(self):
        self.aborted = False

    def abort(self):
        self.aborted = True


class AbortController:
    def __init__(self):
        self.signal = AbortSignal()

    def abort(self):
        self.signal.abort()


def simulate_race_condition():
    """
    Simulasi mengapa useEffect memerlukan AbortController atau boolean flag.
    Query ID berganti cepat: Req A (lambat) vs Req B (cepat).
    Jika tanpa abort, Req A akan menimpa Req B (stale data bug).
    """
    print(f"\n{C.BG_BLUE}{C.WHITE}{C.BOLD} [DEMO: ASYNC EFFECT RACE CONDITION & ABORT CONTROLLER] {C.RESET}\n")
    print("Skenario: User memilih Filter 'Query 1' (latensi 0.6s), lalu segera beralih ke 'Query 2' (latensi 0.2s).")

    active_controller: Optional[AbortController] = None
    state = {"data": "INITIAL"}

    def fetch_data(query_id: str, latency: float, controller: AbortController):
        def worker():
            print(f"  {C.CYAN}[Network Dispatch]{C.RESET} Request for '{query_id}' started (latensi {latency}s)...")
            time.sleep(latency)
            if controller.signal.aborted:
                print(f"  {C.RED}[Stale Response Dropped]{C.RESET} Response for '{query_id}' IGNORED (Signal Aborted)!")
                return
            state["data"] = f"RESULT_FOR_{query_id}"
            print(f"  {C.GREEN}[State Committed]{C.RESET} State updated successfully: {state['data']}")

        t = threading.Thread(target=worker)
        t.start()
        return t

    # Effect Run 1: Query 1 (Slow)
    active_controller = AbortController()
    print(f"{C.BOLD}Step 1: Mounting Effect with Query 1 (Slow){C.RESET}")
    t1 = fetch_data("QUERY_1_SLOW", 0.6, active_controller)

    time.sleep(0.1)

    # Effect Dependency changed before Query 1 finished!
    # Cleanup runs for Effect 1
    print(f"\n{C.BOLD}Step 2: Props changed to Query 2 -> Effect Cleanup triggers controller.abort(){C.RESET}")
    active_controller.abort()

    # Effect Run 2: Query 2 (Fast)
    active_controller = AbortController()
    print(f"{C.BOLD}Step 3: Mounting Effect with Query 2 (Fast){C.RESET}")
    t2 = fetch_data("QUERY_2_FAST", 0.2, active_controller)

    t1.join()
    t2.join()
    print(f"\n{C.GREEN}{C.BOLD}Hasil Akhir State Aman:{C.RESET} {state['data']} (Bukan data basi dari Query 1!)\n")


# =============================================================================
# 7. INTERACTIVE CLI RUNNER
# =============================================================================

def print_header():
    print(f"{C.CYAN}{C.BOLD}" + "=" * 78 + f"{C.RESET}")
    print(f"{C.WHITE}{C.BOLD}  LAB M02: SIDE EFFECTS, REFS & IMPERATIVE INTEROP BOUNDARY WORKSHOP{C.RESET}")
    print(f"{C.DIM}  Simulasi Fiber Pipeline, forwardRef, useImperativeHandle & Race Conditions{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}" + "=" * 78 + f"{C.RESET}\n")


def run_interactive_suite():
    fiber = FiberNode("AnalyticsChart")
    chart_component = ChartWidgetComponent(fiber)
    parent_chart_ref = RefObject()

    print_header()

    while True:
        print(f"{C.BOLD}PILIHAN LAB & SKENARIO:{C.RESET}")
        print(" [1] Mount & Initial Render (LayoutEffect -> Paint -> PassiveEffect)")
        print(" [2] Re-render dengan Data Series Baru (Verify Dependency Delta & Cleanup)")
        print(" [3] Invokasi Imperative Boundary via Parent Ref (forwardRef/useImperativeHandle)")
        print(" [4] Simulasi Race Condition & Async AbortController")
        print(" [5] Unmount Component (Verifikasi Full Teardown & Anti-Memory Leak)")
        print(" [6] Jalankan Seluruh Skenario Otomatis (Full Verification Flow)")
        print(" [0] Keluar")

        try:
            choice = input(f"\n{C.CYAN}Masukkan nomor skenario [0-6]: {C.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            sys.exit(0)

        if choice == "1":
            print(f"\n{C.BOLD}--- SKENARIO 1: MOUNT INITIAL RENDER ---{C.RESET}")
            output = chart_component.render(
                {"series": [10, 20, 35, 50], "theme": "dark"},
                parent_chart_ref
            )
            execute_commit_cycle(fiber, output)

        elif choice == "2":
            if not fiber.mounted:
                print(f"{C.RED}Error: Komponen belum dimount! Jalankan pilihan [1] terlebih dahulu.{C.RESET}\n")
                continue
            print(f"\n{C.BOLD}--- SKENARIO 2: RE-RENDER DENGAN PERUBAHAN DEPS ---{C.RESET}")
            output = chart_component.render(
                {"series": [10, 20, 35, 50, 80, 120], "theme": "solarized"},
                parent_chart_ref
            )
            execute_commit_cycle(fiber, output)

        elif choice == "3":
            print(f"\n{C.BOLD}--- SKENARIO 3: TESTING IMPERATIVE BOUNDARY ---{C.RESET}")
            if parent_chart_ref.current is None:
                print(f"{C.RED}Ref is empty! Komponen belum di-mount atau ref belum terpasang.{C.RESET}\n")
                continue
            handle = parent_chart_ref.current
            print(f"Parent Ref Attached API Keys: {list(handle.keys())}")
            print("Memanggil handle['zoomIn']() dari Parent...")
            handle["zoomIn"]()
            print("Memanggil handle['getSnapshot']() dari Parent...")
            snapshot = handle["getSnapshot"]()
            print(f"Snapshot Result: {C.GREEN}{snapshot}{C.RESET}")
            print(f"Total Points: {handle['getDatasetLength']()} points\n")

        elif choice == "4":
            simulate_race_condition()

        elif choice == "5":
            if not fiber.mounted:
                print(f"{C.YELLOW}Komponen sudah dalam keadaan unmounted.{C.RESET}\n")
            else:
                unmount_fiber(fiber)

        elif choice == "6":
            print(f"\n{C.BG_BLUE}{C.WHITE}{C.BOLD} === MENJALANKAN AUTOMATED FULL VERIFICATION FLOW === {C.RESET}\n")
            # Step 1: Mount
            print(f"{C.BOLD}[STEP 1: INITIAL MOUNT]{C.RESET}")
            out1 = chart_component.render({"series": [5, 15, 25], "theme": "midnight"}, parent_chart_ref)
            execute_commit_cycle(fiber, out1)

            # Step 2: Imperative Zoom
            print(f"{C.BOLD}[STEP 2: IMPERATIVE CONTROL FROM PARENT]{C.RESET}")
            parent_chart_ref.current["zoomIn"]()
            print(f"Snapshot: {parent_chart_ref.current['getSnapshot']()}")

            # Step 3: Update Props
            print(f"\n{C.BOLD}[STEP 3: PROPS UPDATE / RE-RENDER]{C.RESET}")
            out2 = chart_component.render({"series": [5, 15, 25, 40], "theme": "midnight"}, parent_chart_ref)
            execute_commit_cycle(fiber, out2)

            # Step 4: Race condition
            print(f"{C.BOLD}[STEP 4: RACE CONDITION TEST]{C.RESET}")
            simulate_race_condition()

            # Step 5: Unmount
            print(f"{C.BOLD}[STEP 5: COMPONENT UNMOUNT]{C.RESET}")
            unmount_fiber(fiber)
            print(f"{C.GREEN}{C.BOLD}Seluruh siklus arsitektur terverifikasi sukses!{C.RESET}\n")

        elif choice == "0":
            print(f"{C.GREEN}Terima kasih telah menyelesaikan Lab M02.{C.RESET}")
            sys.exit(0)
        else:
            print(f"{C.RED}Pilihan tidak valid. Masukkan 0-6.{C.RESET}\n")


if __name__ == "__main__":
    run_interactive_suite()
