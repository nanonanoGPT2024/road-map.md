#!/usr/bin/env python3
"""
React Core Engine Simulation: Side Effects, Refs, and Imperative Interop Boundaries
BAB-03: Side Effects, Refs, dan Imperative Interop Boundary

Simulates:
1. Fiber Node Hook slots (useState, useRef, useEffect)
2. Dependency array comparison (Object.is / shallow equality)
3. Effect lifecycle: Mount -> Commit Effect -> Update -> Cleanup -> Re-run -> Unmount Cleanup
4. useRef: Persistent mutable container across renders without re-triggering render
5. Imperative Interop Boundary: Integrating and tearing down a non-React 3rd-party widget safely
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def log_phase(phase: str, msg: str):
    print(f"{ANSI.BOLD}{ANSI.MAGENTA}[{phase.upper()}]{ANSI.RESET} {msg}")


def log_hook(hook: str, msg: str):
    print(f"  {ANSI.CYAN}⚡ {hook}:{ANSI.RESET} {msg}")


def log_effect(action: str, msg: str, success: bool = True):
    color = ANSI.GREEN if success else ANSI.YELLOW
    print(f"    {color}▶ Effect {action}:{ANSI.RESET} {msg}")


def log_interop(msg: str):
    print(f"    {ANSI.BLUE}🔌 [3rd-Party Imperative Widget]:{ANSI.RESET} {msg}")


class RefObject:
    def __init__(self, initial_value: Any = None):
        self.current = initial_value

    def __repr__(self):
        return f"RefObject(current={self.current!r})"


class EffectRecord:
    def __init__(self, create_fn: Callable[[], Optional[Callable[[], None]]], deps: Optional[List[Any]]):
        self.create_fn = create_fn
        self.deps = deps
        self.cleanup_fn: Optional[Callable[[], None]] = None
        self.has_run = False


class ImperativeChartWidget:
    """Simulates a legacy/imperative non-React library (like Chart.js or D3)."""

    def __init__(self, container_id: str, title: str):
        self.container_id = container_id
        self.title = title
        self.data_points: List[int] = []
        self.is_destroyed = False
        log_interop(f"INSTANTIATED widget on #{self.container_id} (title='{self.title}')")

    def update_data(self, points: List[int]):
        if self.is_destroyed:
            raise RuntimeError("Attempted to update destroyed imperative widget!")
        self.data_points = list(points)
        log_interop(f"RENDERED points: {self.data_points} inside #{self.container_id}")

    def destroy(self):
        self.is_destroyed = True
        log_interop(f"DESTROYED DOM listeners and cleared memory for #{self.container_id}")


class ReactFiberDispatcher:
    def __init__(self):
        self.hooks_state: List[Any] = []
        self.hooks_refs: List[RefObject] = []
        self.hooks_effects: List[EffectRecord] = []
        self.state_cursor = 0
        self.ref_cursor = 0
        self.effect_cursor = 0
        self.is_mounted = False
        self.render_count = 0
        self.pending_re_render = False

    def reset_cursors(self):
        self.state_cursor = 0
        self.ref_cursor = 0
        self.effect_cursor = 0

    def use_state(self, initial_value: Any) -> Tuple[Any, Callable[[Any], None]]:
        idx = self.state_cursor
        if idx >= len(self.hooks_state):
            self.hooks_state.append(initial_value)
            log_hook("useState", f"Initialized slot {idx} with {initial_value!r}")
        value = self.hooks_state[idx]

        def set_state(new_val: Any):
            old_val = self.hooks_state[idx]
            if callable(new_val):
                resolved = new_val(old_val)
            else:
                resolved = new_val
            if resolved != old_val:
                self.hooks_state[idx] = resolved
                self.pending_re_render = True
                log_hook("useState", f"Slot {idx} updated: {old_val!r} -> {resolved!r} (re-render scheduled)")
            else:
                log_hook("useState", f"Slot {idx} unchanged ({resolved!r}), bailout render")

        self.state_cursor += 1
        return value, set_state

    def use_ref(self, initial_value: Any = None) -> RefObject:
        idx = self.ref_cursor
        if idx >= len(self.hooks_refs):
            ref_obj = RefObject(initial_value)
            self.hooks_refs.append(ref_obj)
            log_hook("useRef", f"Allocated persistent ref slot {idx}: {ref_obj}")
        ref = self.hooks_refs[idx]
        self.ref_cursor += 1
        return ref

    def use_effect(self, create: Callable[[], Optional[Callable[[], None]]], deps: Optional[List[Any]] = None):
        idx = self.effect_cursor
        if idx >= len(self.hooks_effects):
            record = EffectRecord(create, deps)
            self.hooks_effects.append(record)
            log_hook("useEffect", f"Registered effect slot {idx} (deps: {deps})")
        else:
            record = self.hooks_effects[idx]
            record.create_fn = create
            record.deps = deps
        self.effect_cursor += 1

    def are_deps_equal(self, prev_deps: Optional[List[Any]], next_deps: Optional[List[Any]]) -> bool:
        if prev_deps is None or next_deps is None:
            return False
        if len(prev_deps) != len(next_deps):
            return False
        for p, n in zip(prev_deps, next_deps):
            if p is not n and p != n:
                return False
        return True

    def commit_passive_effects(self, prev_effects: List[Tuple[Optional[List[Any]], Optional[Callable[[], None]]]]):
        log_phase("commit", "Flushing Passive Effects (post-render DOM synchronization)...")
        for idx, effect in enumerate(self.hooks_effects):
            prev_dep, prev_clean = prev_effects[idx] if idx < len(prev_effects) else (None, None)
            should_run = False

            if not effect.has_run:
                should_run = True
                log_effect("check", f"Slot {idx}: Initial mount -> Must run effect", success=True)
            elif effect.deps is None:
                should_run = True
                log_effect("check", f"Slot {idx}: No deps supplied -> Must run on every render", success=True)
            else:
                if not self.are_deps_equal(prev_dep, effect.deps):
                    should_run = True
                    log_effect("check", f"Slot {idx}: Deps changed: {prev_dep} -> {effect.deps}", success=True)
                else:
                    log_effect("check", f"Slot {idx}: Deps unchanged {effect.deps} -> Bailout (Skip)", success=False)

            if should_run:
                if effect.cleanup_fn:
                    log_effect("cleanup", f"Slot {idx}: Executing prior cleanup function before re-firing")
                    try:
                        effect.cleanup_fn()
                    except Exception as err:
                        print(f"{ANSI.RED}Error in cleanup: {err}{ANSI.RESET}")
                    effect.cleanup_fn = None

                log_effect("execute", f"Slot {idx}: Invoking effect callback")
                cleanup = effect.create_fn()
                if callable(cleanup):
                    effect.cleanup_fn = cleanup
                effect.has_run = True

    def unmount(self):
        log_phase("teardown", "Unmounting component instance and cleaning up effects...")
        for idx, effect in reversed(list(enumerate(self.hooks_effects))):
            if effect.cleanup_fn:
                log_effect("unmount cleanup", f"Slot {idx}: Invoking unmount cleanup handler")
                try:
                    effect.cleanup_fn()
                except Exception as err:
                    print(f"{ANSI.RED}Error in unmount cleanup: {err}{ANSI.RESET}")
                effect.cleanup_fn = None
        self.is_mounted = False
        print(f"{ANSI.GREEN}✓ Component fiber unmounted cleanly.{ANSI.RESET}\n")


# Global runtime instance
runtime = ReactFiberDispatcher()


def analytics_dashboard_component():
    """
    Simulated React Component:
    Demonstrates:
    - useState: metric counter and active dataset ID
    - useRef: tracks click count without re-render & holds imperative widget instance
    - useEffect 1: Document title / telemetry synchronization
    - useEffect 2: Imperative interop boundary managing ImperativeChartWidget
    """
    click_ref = runtime.use_ref(initial_value=0)
    widget_ref = runtime.use_ref(initial_value=None)

    dataset_id, set_dataset_id = runtime.use_state("sales-q1")
    tick, set_tick = runtime.use_state(0)

    # Effect 1: Telemetry sync
    def effect_telemetry():
        print(f"      {ANSI.WHITE}[Telemetry Effect] Syncing session token for dataset '{dataset_id}'...{ANSI.RESET}")

        def cleanup_telemetry():
            print(f"      {ANSI.WHITE}[Telemetry Cleanup] Disconnecting session for dataset '{dataset_id}'{ANSI.RESET}")

        return cleanup_telemetry

    runtime.use_effect(effect_telemetry, [dataset_id])

    # Effect 2: Imperative Widget Interop Boundary
    def effect_interop():
        print(f"      {ANSI.YELLOW}[Interop Effect] Binding imperative chart to DOM container...{ANSI.RESET}")
        chart = ImperativeChartWidget(container_id="chart-root", title=f"Dataset {dataset_id}")
        widget_ref.current = chart

        if dataset_id == "sales-q1":
            chart.update_data([100, 220, 310])
        else:
            chart.update_data([450, 680, 890])

        def cleanup_interop():
            print(f"      {ANSI.YELLOW}[Interop Cleanup] Tearing down chart widget before next swap/unmount...{ANSI.RESET}")
            if widget_ref.current:
                widget_ref.current.destroy()
                widget_ref.current = None

        return cleanup_interop

    runtime.use_effect(effect_interop, [dataset_id])

    return {
        "dataset_id": dataset_id,
        "set_dataset_id": set_dataset_id,
        "tick": tick,
        "set_tick": set_tick,
        "click_ref": click_ref,
        "widget_ref": widget_ref,
    }


def render_cycle():
    runtime.render_count += 1
    log_phase("render", f"Triggering Render Cycle #{runtime.render_count}")

    # Capture previous effect state before current render pass
    prev_effects = [(eff.deps, eff.cleanup_fn) for eff in runtime.hooks_effects]

    runtime.reset_cursors()
    bindings = analytics_dashboard_component()
    runtime.pending_re_render = False

    runtime.commit_passive_effects(prev_effects)
    return bindings


def print_banner():
    banner = f"""
{ANSI.CYAN}{ANSI.BOLD}========================================================================
 REACT INTERNALS LAB: BAB-03 SIDE EFFECTS, REFS & INTEROP BOUNDARIES
========================================================================{ANSI.RESET}
 {ANSI.WHITE}• Simulates Fiber Hook slots (State, Ref, Effect){ANSI.RESET}
 {ANSI.WHITE}• Strict cleanup ordering: Old cleanup -> New effect{ANSI.RESET}
 {ANSI.WHITE}• Mutable ref container mutation vs State re-render{ANSI.RESET}
 {ANSI.WHITE}• Imperative 3rd-party widget lifecycle management{ANSI.RESET}
------------------------------------------------------------------------"""
    print(banner)


def prompt_step(msg: str):
    try:
        input(f"\n{ANSI.CYAN}[{msg} - Tekan Enter]{ANSI.RESET}")
    except (EOFError, KeyboardInterrupt):
        print(f"\n{ANSI.CYAN}[Auto-advancing: {msg}]{ANSI.RESET}")
        time.sleep(0.3)


def run_interactive_simulation():
    print_banner()

    print(f"\n{ANSI.BOLD}Step 1: Initial Component Mount{ANSI.RESET}")
    bindings = render_cycle()
    runtime.is_mounted = True

    prompt_step("Lanjut ke Step 2: State update yang memicu effect deps")

    print(f"\n{ANSI.BOLD}Step 2: Change 'dataset_id' ('sales-q1' -> 'sales-q2'){ANSI.RESET}")
    bindings["set_dataset_id"]("sales-q2")
    if runtime.pending_re_render:
        bindings = render_cycle()

    prompt_step("Lanjut ke Step 3: State update TANPA merubah effect deps")

    print(f"\n{ANSI.BOLD}Step 3: Increment 'tick' (tick 0 -> 1, dataset_id tetap 'sales-q2'){ANSI.RESET}")
    bindings["set_tick"](lambda t: t + 1)
    if runtime.pending_re_render:
        bindings = render_cycle()

    prompt_step("Lanjut ke Step 4: Mutasi useRef tanpa re-render")

    print(f"\n{ANSI.BOLD}Step 4: Mutate Ref Directly without Triggering Render{ANSI.RESET}")
    click_ref = bindings["click_ref"]
    click_ref.current += 1
    log_hook("useRef", f"Mutated click_ref.current directly to {click_ref.current}. Render requested? {runtime.pending_re_render}")
    print(f"      {ANSI.GREEN}✓ Component DID NOT re-render because ref mutation is silent!{ANSI.RESET}")

    prompt_step("Lanjut ke Step 5: Komponen Unmount & Cleanup")

    print(f"\n{ANSI.BOLD}Step 5: Teardown / Unmount Lifecycle{ANSI.RESET}")
    runtime.unmount()

    print(f"{ANSI.BOLD}{ANSI.GREEN}✔ Simulasi Bab 3 Selesai 100% dengan Sukses.{ANSI.RESET}")


if __name__ == "__main__":
    run_interactive_simulation()
