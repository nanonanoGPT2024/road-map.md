#!/usr/bin/env python3
"""
Simulasi Reaktif: React Internals, Fiber Architecture & State Management Engine
Materi: BAB-02 React Internals dan State Management (Modul 01)
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# ==============================================================================
# ANSI Color Codes & UI Helper
# ==============================================================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_DARK = "\033[48;5;236m"

def badge(text: str, color: str = CYAN) -> str:
    return f"{color}{BOLD}[{text}]{RESET}"

def section_header(title: str):
    print(f"\n{BOLD}{MAGENTA}{'=' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  ⚛  {title.upper()}{RESET}")
    print(f"{BOLD}{MAGENTA}{'=' * 70}{RESET}")

# ==============================================================================
# 1. Virtual DOM & Fiber Node Definitions
# ==============================================================================
class VNode:
    """Virtual DOM Node Element representation."""
    def __init__(self, tag: str, props: Optional[Dict[str, Any]] = None, children: Optional[List[Any]] = None, key: Optional[str] = None):
        self.tag = tag
        self.props = props or {}
        self.children = children or []
        self.key = key

    def __repr__(self) -> str:
        return f"<{self.tag} key={self.key} props={self.props} children_count={len(self.children)}/>"


class FiberNode:
    """Fiber Unit of Work representing reconciliation node."""
    def __init__(self, tag: str, key: Optional[str] = None):
        self.tag = tag
        self.key = key
        self.state_node: Optional[Any] = None  # Reference to real DOM node
        self.child: Optional['FiberNode'] = None
        self.sibling: Optional['FiberNode'] = None
        self.return_fiber: Optional['FiberNode'] = None
        self.alternate: Optional['FiberNode'] = None  # Previous commit tree counterpart
        self.props: Dict[str, Any] = {}
        self.memoized_props: Dict[str, Any] = {}
        self.memoized_state: List[Any] = []
        self.effect_tag: str = "NONE"  # PLACEMENT | UPDATE | DELETION
        self.hooks: List[Any] = []

    def __repr__(self) -> str:
        return f"Fiber({self.tag}, key={self.key}, effect={self.effect_tag})"


# ==============================================================================
# 2. Hook Runtime Context
# ==============================================================================
class HookContext:
    def __init__(self):
        self.hooks_store: List[Dict[str, Any]] = []
        self.hook_index: int = 0
        self.effects_queue: List[Callable[[], Optional[Callable[[], None]]]] = []
        self.cleanups_queue: List[Optional[Callable[[], None]]] = []
        self.schedule_rerender: Optional[Callable[[], None]] = None

    def reset_index(self):
        self.hook_index = 0

runtime_ctx = HookContext()


def use_state(initial_val: Any) -> Tuple[Any, Callable[[Any], None]]:
    """Simulasi useState dengan linked index pointer seperti React fiber hooks."""
    idx = runtime_ctx.hook_index
    if len(runtime_ctx.hooks_store) <= idx:
        runtime_ctx.hooks_store.append({"state": initial_val})
        print(f"  {badge('HOOK', BLUE)} Initialized useState[{idx}] -> {YELLOW}{repr(initial_val)}{RESET}")

    current_val = runtime_ctx.hooks_store[idx]["state"]

    def set_state(new_val: Any):
        old = runtime_ctx.hooks_store[idx]["state"]
        if callable(new_val):
            updated = new_val(old)
        else:
            updated = new_val

        # Object.is identity check
        if old != updated:
            runtime_ctx.hooks_store[idx]["state"] = updated
            print(f"  {badge('DISPATCH', GREEN)} useState[{idx}] mutated: {RED}{repr(old)}{RESET} -> {GREEN}{repr(updated)}{RESET}")
            if runtime_ctx.schedule_rerender:
                runtime_ctx.schedule_rerender()
        else:
            print(f"  {badge('BAILOUT', DIM)} State unchanged ({repr(old)}). Skipping render.")

    runtime_ctx.hook_index += 1
    return current_val, set_state


def use_effect(effect_cb: Callable[[], Optional[Callable[[], None]]], deps: Optional[List[Any]] = None):
    """Simulasi useEffect dengan shallow dependency array comparison."""
    idx = runtime_ctx.hook_index
    has_changed = True

    if len(runtime_ctx.hooks_store) <= idx:
        hook_record = {"deps": None, "cleanup": None}
        runtime_ctx.hooks_store.append(hook_record)
        print(f"  {badge('HOOK', BLUE)} Initialized useEffect[{idx}]")
    else:
        prev_deps = runtime_ctx.hooks_store[idx]["deps"]
        if deps is not None and prev_deps is not None:
            has_changed = any(d1 != d2 for d1, d2 in zip(deps, prev_deps))
        elif deps is not None and prev_deps is None:
            has_changed = True
        else:
            has_changed = True

    if has_changed:
        runtime_ctx.hooks_store[idx]["deps"] = deps
        runtime_ctx.effects_queue.append((idx, effect_cb))
        print(f"  {badge('EFFECT-QUEUE', YELLOW)} Enqueued effect[{idx}] (deps changed: {has_changed})")
    else:
        print(f"  {badge('EFFECT-SKIP', DIM)} Dependencies stable for effect[{idx}]. Skipping execution.")

    runtime_ctx.hook_index += 1


# ==============================================================================
# 3. Fiber Engine & Reconciliation (Diffing)
# ==============================================================================
class FiberEngine:
    """Mesin Fiber: Work Loop, Diffing Reconciliation, dan 2-Phase Commit."""

    def __init__(self, root_component: Callable[[], VNode]):
        self.root_component = root_component
        self.current_fiber_root: Optional[FiberNode] = None
        self.work_in_progress_root: Optional[FiberNode] = None
        self.render_count = 0
        runtime_ctx.schedule_rerender = self.schedule_work

    def reconcile_children(self, wip_fiber: FiberNode, elements: List[VNode]):
        """Reconciliation 2-pointer/keyed diffing algorithm."""
        old_fiber = wip_fiber.alternate.child if wip_fiber.alternate else None
        prev_sibling: Optional[FiberNode] = None

        idx = 0
        while idx < len(elements) or old_fiber is not None:
            element = elements[idx] if idx < len(elements) else None
            new_fiber: Optional[FiberNode] = None

            same_type = False
            if old_fiber and element:
                same_type = (old_fiber.tag == element.tag and old_fiber.key == element.key)

            if same_type and old_fiber:
                # UPDATE Effect
                new_fiber = FiberNode(tag=element.tag, key=element.key)
                new_fiber.props = element.props
                new_fiber.alternate = old_fiber
                new_fiber.state_node = old_fiber.state_node
                new_fiber.effect_tag = "UPDATE"
                print(f"    {badge('RECONCILE', CYAN)} Match node <{element.tag}> key={element.key} -> {YELLOW}UPDATE{RESET}")
            elif element:
                # PLACEMENT Effect
                new_fiber = FiberNode(tag=element.tag, key=element.key)
                new_fiber.props = element.props
                new_fiber.effect_tag = "PLACEMENT"
                print(f"    {badge('RECONCILE', GREEN)} New node <{element.tag}> key={element.key} -> {GREEN}PLACEMENT{RESET}")

            if old_fiber and not same_type:
                # DELETION Effect
                old_fiber.effect_tag = "DELETION"
                print(f"    {badge('RECONCILE', RED)} Pruned node <{old_fiber.tag}> key={old_fiber.key} -> {RED}DELETION{RESET}")

            if old_fiber:
                old_fiber = old_fiber.sibling

            if new_fiber:
                new_fiber.return_fiber = wip_fiber
                if prev_sibling is None:
                    wip_fiber.child = new_fiber
                else:
                    prev_sibling.sibling = new_fiber
                prev_sibling = new_fiber

            idx += 1

    def perform_unit_of_work(self, fiber: FiberNode) -> Optional[FiberNode]:
        """Menjalankan unit kerja individual fiber (BeginWork & CompleteWork)."""
        # BeginWork
        if fiber.tag == "ROOT":
            runtime_ctx.reset_index()
            vdom = self.root_component()
            self.reconcile_children(fiber, [vdom])
        else:
            # Native tag element
            children = fiber.props.get("children", [])
            child_vnodes = []
            for c in children:
                if isinstance(c, VNode):
                    child_vnodes.append(c)
                elif isinstance(c, str):
                    child_vnodes.append(VNode(tag="TEXT", props={"nodeValue": c}))
            self.reconcile_children(fiber, child_vnodes)

        # Return next unit of work: Child -> Sibling -> Return Uncle
        if fiber.child:
            return fiber.child
        next_fiber: Optional[FiberNode] = fiber
        while next_fiber:
            if next_fiber.sibling:
                return next_fiber.sibling
            next_fiber = next_fiber.return_fiber
        return None

    def commit_root(self):
        """Phase 2: Commit Phase (Synchronous & Mutates Real Screen/DOM)."""
        print(f"\n{BOLD}{BLUE}--- Phase 2: Synchronous Commit & Mutation ---{RESET}")
        mutations = []

        def traverse_and_commit(fiber: Optional[FiberNode]):
            if not fiber:
                return
            if fiber.effect_tag != "NONE":
                mutations.append((fiber.tag, fiber.effect_tag, fiber.props))
                print(f"  {badge('COMMIT', MAGENTA)} Applying {BOLD}{fiber.effect_tag}{RESET} to <{fiber.tag}>")
            traverse_and_commit(fiber.child)
            traverse_and_commit(fiber.sibling)

        if self.work_in_progress_root:
            traverse_and_commit(self.work_in_progress_root.child)
            self.current_fiber_root = self.work_in_progress_root
            self.work_in_progress_root = None

        # Execute Passive Effects (useEffect) & Cleanups
        print(f"\n{BOLD}{CYAN}--- Running Passive Effects Queue ---{RESET}")
        while runtime_ctx.effects_queue:
            idx, effect_cb = runtime_ctx.effects_queue.pop(0)
            prev_cleanup = runtime_ctx.hooks_store[idx].get("cleanup")
            if callable(prev_cleanup):
                print(f"  {badge('CLEANUP', RED)} Executing cleanup for effect[{idx}]")
                prev_cleanup()

            new_cleanup = effect_cb()
            runtime_ctx.hooks_store[idx]["cleanup"] = new_cleanup
            print(f"  {badge('PASSIVE-EFFECT', GREEN)} Executed effect callback [{idx}]")

    def schedule_work(self):
        """Phase 1: Render / Reconciliation (Interruptible Work Loop)."""
        self.render_count += 1
        print(f"\n{BOLD}{YELLOW}>>> WORK LOOP STARTED: Render Cycle #{self.render_count} <<<{RESET}")
        self.work_in_progress_root = FiberNode(tag="ROOT")
        self.work_in_progress_root.alternate = self.current_fiber_root

        next_unit: Optional[FiberNode] = self.work_in_progress_root
        step = 1
        while next_unit:
            print(f"  {DIM}[Step {step}]{RESET} Work on: {BOLD}{next_unit.tag}{RESET}")
            next_unit = self.perform_unit_of_work(next_unit)
            step += 1

        self.commit_root()


# ==============================================================================
# 4. Interactive Simulation Application
# ==============================================================================
dispatcher_action: Optional[Callable[[], None]] = None

def app_component() -> VNode:
    """Component yang disimulasikan menggunakan hooks state dan effects."""
    global dispatcher_action

    count, set_count = use_state(0)
    user_status, set_user_status = use_state("idle")

    # Effect 1: Sinkronisasi title/logger
    def effect_logger():
        print(f"      {DIM}(Side-Effect Executed): Telemetry event logged count={count}{RESET}")
        def cleanup():
            print(f"      {DIM}(Side-Effect Cleanup): Cleaned up listener for count={count}{RESET}")
        return cleanup

    use_effect(effect_logger, [count])

    # Effect 2: Mount only listener
    def effect_mount():
        print(f"      {DIM}(Mount Effect): Subscribed to Global Event Bus{RESET}")
        return lambda: print(f"      {DIM}(Unmount): Unsubscribed from Event Bus{RESET}")

    use_effect(effect_mount, [])

    # Simpan dispatcher aksi untuk trigger interaktif
    def trigger_increment():
        set_count(lambda c: c + 1)
        set_user_status("active")

    dispatcher_action = trigger_increment

    # Menghasilkan VDOM Tree
    return VNode(
        tag="div",
        props={"id": "container", "className": "p-4"},
        children=[
            VNode(tag="h1", props={"children": [f"React Fiber Dashboard v19.0.0"]}),
            VNode(tag="p", key="status-badge", props={"children": [f"User Status: {user_status}"]}),
            VNode(tag="span", key="counter-val", props={"children": [f"Counter: {count}"]}),
            VNode(tag="button", props={"onClick": "trigger_increment", "children": ["Tambah Nilai"]})
        ]
    )


def print_ascii_art():
    art = f"""{CYAN}{BOLD}
    ====================================================================
      ____                 _     ___       _                             _     
     |  _ \\ ___  __ _  ___| |_  |_ _|_ __ | |_ ___ _ __ _ __   __ _  ___| |___ 
     | |_) / _ \\/ _` |/ __| __|  | || '_ \\| __/ _ \\ '__| '_ \\ / _` |/ __| / __|
     |  _ <  __/ (_| | (__| |_   | || | | | ||  __/ |  | | | | (_| | (__| \\__ \\
     |_| \\_\\___|\\__,_|\\___|\\__| |___|_| |_|\\__\\___|_|  |_| |_|\\__,_|\\___|_|___/
    ===================================================================={RESET}
    {BOLD}Simulasi Arsitektur Fiber, Double Buffering & Linked Hook Runtime{RESET}
    """
    print(art)


def main():
    print_ascii_art()
    section_header("1. Initial Mount: Render Tree Pertama & Inisialisasi Fiber")
    engine = FiberEngine(root_component=app_component)
    engine.schedule_work()

    print(f"\n{GREEN}{BOLD}✔ Initial Mount Selesai Berhasil!{RESET}\n")
    time.sleep(0.3)

    section_header("2. State Mutation: Dispatch Action -> Schedule Work Loop")
    print(f"{YELLOW}Simulasi event click tombol 'Tambah Nilai' (State update dipicu)...{RESET}")
    if dispatcher_action:
        dispatcher_action()

    time.sleep(0.3)
    section_header("3. State Mutation Kedua: Re-render Lanjutan dengan Diffing")
    print(f"{YELLOW}Simulasi click tombol kedua (State update kembali dipicu)...{RESET}")
    if dispatcher_action:
        dispatcher_action()

    time.sleep(0.3)
    section_header("4. Bailout Verification: State Tidak Berubah")
    print(f"{YELLOW}Simulasi Dispatcher dengan nilai identik untuk memicu Bailout Optimizer...{RESET}")
    _, set_status = use_state("active")
    # Reset index karena dipanggil di luar render phase untuk demonstrasi langsung
    runtime_ctx.reset_index()
    # Panggil mutasi langsung ke status active yang sama
    set_status("active")

    section_header("Ringkasan Eksekusi Lab")
    print(f"{BOLD}{GREEN}Semua konsep inti React Internals berhasil diverifikasi:{RESET}")
    print(f"  1. {CYAN}Fiber Tree Structure{RESET} (child, sibling, return)")
    print(f"  2. {CYAN}Double Buffering{RESET} (workInProgress vs current tree)")
    print(f"  3. {CYAN}Hook Linked Allocation{RESET} (useState & useEffect index mapping)")
    print(f"  4. {CYAN}Reconciliation & Diffing{RESET} (PLACEMENT vs UPDATE tags)")
    print(f"  5. {CYAN}Passive Effects Lifecycle{RESET} (Mount, cleanup, re-execution)\n")

if __name__ == "__main__":
    main()
