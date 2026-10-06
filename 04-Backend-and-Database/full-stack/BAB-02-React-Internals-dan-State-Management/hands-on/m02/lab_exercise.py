#!/usr/bin/env python3
"""
BAB-02: React Internals & Advanced State Management Interactive Simulation Engine
Simulates React Fiber Reconciliation, Hook Linked List, Time-Slicing Scheduler,
and Production Zustand-like Atomic Store with Selector Subscriptions.
"""

import sys
import time
import enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[100m"

    @classmethod
    def badge(cls, text: str, bg: str, fg: str = WHITE) -> str:
        return f"{bg}{fg}{cls.BOLD} {text} {cls.RESET}"


class WorkTag(enum.IntEnum):
    FUNCTION_COMPONENT = 0
    CLASS_COMPONENT = 1
    HOST_ROOT = 2
    HOST_COMPONENT = 3
    HOST_TEXT = 4


class EffectFlags(enum.IntFlag):
    NO_EFFECT = 0b0000
    PLACEMENT = 0b0001
    UPDATE = 0b0010
    DELETION = 0b0100
    PASSIVE = 0b1000


class LanePriority(enum.IntEnum):
    SYNC = 1
    INPUT_CONTINUOUS = 2
    DEFAULT = 4
    TRANSITION = 8
    IDLE = 16


class Hook:
    def __init__(self, memoized_state: Any = None):
        self.memoized_state: Any = memoized_state
        self.base_queue: List[Callable[[Any], Any]] = []
        self.next_hook: Optional["Hook"] = None


class FiberNode:
    def __init__(
        self,
        tag: WorkTag,
        key: Optional[str],
        type_: Any,
        pending_props: Dict[str, Any],
    ):
        self.tag: WorkTag = tag
        self.key: Optional[str] = key
        self.type: Any = type_
        self.pending_props: Dict[str, Any] = pending_props
        self.memoized_props: Dict[str, Any] = {}
        self.memoized_state: Optional[Hook] = None
        self.child: Optional["FiberNode"] = None
        self.sibling: Optional["FiberNode"] = None
        self.return_fiber: Optional["FiberNode"] = None
        self.alternate: Optional["FiberNode"] = None
        self.flags: EffectFlags = EffectFlags.NO_EFFECT
        self.lane: LanePriority = LanePriority.DEFAULT

    def __repr__(self) -> str:
        type_name = getattr(self.type, "__name__", str(self.type))
        return f"<Fiber {type_name} tag={self.tag.name} flags={self.flags.name}>"


class FiberReconciler:
    """Simulates React 18 Fiber Reconciliation, WorkInProgress Tree & Commit Phase."""

    def __init__(self):
        self.current_root: Optional[FiberNode] = None
        self.work_in_progress: Optional[FiberNode] = None
        self.active_hook: Optional[Hook] = None
        self.current_hook: Optional[Hook] = None

    def create_work_in_progress(self, current: FiberNode) -> FiberNode:
        wip = current.alternate
        if wip is None:
            wip = FiberNode(
                current.tag,
                current.key,
                current.type,
                current.pending_props.copy(),
            )
            wip.alternate = current
            current.alternate = wip
        else:
            wip.pending_props = current.pending_props.copy()
            wip.flags = EffectFlags.NO_EFFECT

        wip.child = current.child
        wip.memoized_props = current.memoized_props.copy()
        wip.memoized_state = current.memoized_state
        wip.sibling = current.sibling
        wip.return_fiber = current.return_fiber
        return wip

    def mount_host_root(self, root_name: str = "AppRoot") -> FiberNode:
        root = FiberNode(WorkTag.HOST_ROOT, None, root_name, {"children": []})
        self.current_root = root
        return root

    def reconcile_children(
        self,
        return_fiber: FiberNode,
        current_first_child: Optional[FiberNode],
        new_children: List[Tuple[WorkTag, str, Any, Dict[str, Any]]],
    ) -> Optional[FiberNode]:
        prev_new_fiber: Optional[FiberNode] = None
        first_new_child: Optional[FiberNode] = None

        for tag, key, type_, props in new_children:
            existing = current_first_child
            matched: Optional[FiberNode] = None

            while existing:
                if existing.key == key and existing.type == type_:
                    matched = existing
                    break
                existing = existing.sibling

            if matched:
                new_fiber = self.create_work_in_progress(matched)
                new_fiber.pending_props = props
                new_fiber.flags = EffectFlags.UPDATE
            else:
                new_fiber = FiberNode(tag, key, type_, props)
                new_fiber.flags = EffectFlags.PLACEMENT

            new_fiber.return_fiber = return_fiber

            if prev_new_fiber is None:
                first_new_child = new_fiber
            else:
                prev_new_fiber.sibling = new_fiber
            prev_new_fiber = new_fiber

        return_fiber.child = first_new_child
        return first_new_child

    def commit_root(self, wip_root: FiberNode) -> List[str]:
        mutations: List[str] = []

        def traverse(node: Optional[FiberNode]):
            if not node:
                return
            if node.flags & EffectFlags.PLACEMENT:
                mutations.append(
                    f"[DOM Commit] PLACEMENT -> Node '{node.type}' (key={node.key}) injected into DOM."
                )
            if node.flags & EffectFlags.UPDATE:
                mutations.append(
                    f"[DOM Commit] UPDATE    -> Node '{node.type}' (key={node.key}) patched with props: {node.pending_props}"
                )
            node.memoized_props = node.pending_props.copy()
            node.flags = EffectFlags.NO_EFFECT
            traverse(node.child)
            traverse(node.sibling)

        traverse(wip_root)
        self.current_root = wip_root
        return mutations


class ConcurrentScheduler:
    """Simulates React 18 Concurrent Time-Slicing and Lane Preemption."""

    def __init__(self, time_slice_ms: float = 12.0):
        self.time_slice_ms = time_slice_ms
        self.task_queue: List[Dict[str, Any]] = []

    def schedule(self, name: str, priority: LanePriority, total_work_units: int):
        self.task_queue.append({
            "name": name,
            "priority": priority,
            "remaining_units": total_work_units,
            "total_units": total_work_units,
        })
        self.task_queue.sort(key=lambda t: t["priority"].value)

    def run_simulation(self) -> List[str]:
        logs: List[str] = []
        while self.task_queue:
            task = self.task_queue[0]
            start = time.perf_counter()
            slice_done = 0

            logs.append(
                f"{ANSI.CYAN}[Scheduler]{ANSI.RESET} Commencing task '{task['name']}' "
                f"[{task['priority'].name}] ({task['remaining_units']}/{task['total_units']} units left)"
            )

            while task["remaining_units"] > 0:
                time.sleep(0.002)
                task["remaining_units"] -= 1
                slice_done += 1
                elapsed = (time.perf_counter() - start) * 1000

                if elapsed >= self.time_slice_ms and task["remaining_units"] > 0:
                    logs.append(
                        f"  {ANSI.YELLOW}⏸ Time-slice exceeded ({elapsed:.1f}ms >= {self.time_slice_ms}ms). "
                        f"Yielding thread to host loop.{ANSI.RESET}"
                    )
                    break

            if task["remaining_units"] == 0:
                self.task_queue.pop(0)
                logs.append(
                    f"  {ANSI.GREEN}✓ Task '{task['name']}' fully completed and committed.{ANSI.RESET}"
                )
        return logs


class ZustandStore:
    """Production-grade reactive Store simulating Zustand micro-store architecture."""

    def __init__(self, initial_state: Dict[str, Any]):
        self._state: Dict[str, Any] = initial_state.copy()
        self._listeners: Set[Callable[[Dict[str, Any], Dict[str, Any]], None]] = set()

    def get_state(self) -> Dict[str, Any]:
        return self._state.copy()

    def set_state(self, updater: Callable[[Dict[str, Any]], Dict[str, Any]]):
        prev = self._state.copy()
        next_state = updater(prev)
        if next_state != self._state:
            self._state = next_state
            for listener in list(self._listeners):
                listener(self._state, prev)

    def subscribe_with_selector(
        self,
        selector: Callable[[Dict[str, Any]], Any],
        listener: Callable[[Any, Any], None],
        equality_fn: Optional[Callable[[Any, Any], bool]] = None,
    ) -> Callable[[], None]:
        if equality_fn is None:
            equality_fn = lambda a, b: a == b

        current_slice = selector(self._state)

        def store_listener(next_state: Dict[str, Any], prev_state: Dict[str, Any]):
            nonlocal current_slice
            new_slice = selector(next_state)
            if not equality_fn(new_slice, current_slice):
                old_val = current_slice
                current_slice = new_slice
                listener(new_slice, old_val)

        self._listeners.add(store_listener)

        def unsubscribe():
            self._listeners.discard(store_listener)

        return unsubscribe


def run_fiber_demo():
    print(f"\n{ANSI.badge('DEMO 1', ANSI.BG_BLUE)} {ANSI.BOLD}React Fiber Double Buffering & Reconciliation{ANSI.RESET}")
    reconciler = FiberReconciler()
    root = reconciler.mount_host_root("Root")

    print(f"{ANSI.DIM}Mounting Initial Component Tree...{ANSI.RESET}")
    v1_children = [
        (WorkTag.FUNCTION_COMPONENT, "navbar", "Header", {"title": "FullStack Store"}),
        (WorkTag.HOST_COMPONENT, "cart-btn", "button", {"count": 0, "color": "blue"}),
        (WorkTag.HOST_COMPONENT, "footer", "Footer", {"year": 2026}),
    ]

    wip_root = reconciler.create_work_in_progress(root)
    reconciler.reconcile_children(wip_root, root.child, v1_children)
    mutations_1 = reconciler.commit_root(wip_root)
    for m in mutations_1:
        print(f"  {ANSI.GREEN}{m}{ANSI.RESET}")

    print(f"\n{ANSI.DIM}Dispatching State Update (Increment cart count & modify footer)...{ANSI.RESET}")
    v2_children = [
        (WorkTag.FUNCTION_COMPONENT, "navbar", "Header", {"title": "FullStack Store"}),
        (WorkTag.HOST_COMPONENT, "cart-btn", "button", {"count": 1, "color": "emerald"}),
        (WorkTag.HOST_COMPONENT, "footer", "Footer", {"year": 2026, "cached": True}),
    ]

    wip_root_2 = reconciler.create_work_in_progress(reconciler.current_root)
    reconciler.reconcile_children(wip_root_2, reconciler.current_root.child, v2_children)
    mutations_2 = reconciler.commit_root(wip_root_2)
    for m in mutations_2:
        print(f"  {ANSI.CYAN}{m}{ANSI.RESET}")


def run_scheduler_demo():
    print(f"\n{ANSI.badge('DEMO 2', ANSI.BG_MAGENTA)} {ANSI.BOLD}Concurrent Time-Slicing Scheduler (React 18 Lane Model){ANSI.RESET}")
    scheduler = ConcurrentScheduler(time_slice_ms=8.0)
    scheduler.schedule("Analytics Logger (Background)", LanePriority.IDLE, 6)
    scheduler.schedule("Keyboard Typing Input (Interactive)", LanePriority.INPUT_CONTINUOUS, 4)
    scheduler.schedule("Data Table Filtering (Transition)", LanePriority.TRANSITION, 9)

    logs = scheduler.run_simulation()
    for log in logs:
        print(log)


def run_zustand_demo():
    print(f"\n{ANSI.badge('DEMO 3', ANSI.BG_DARK)} {ANSI.BOLD}Zustand Reactive Store with Selector Subscriptions{ANSI.RESET}")
    store = ZustandStore({
        "user": {"name": "Alex", "role": "admin"},
        "cart": {"items": [], "total": 0},
        "theme": "dark",
    })

    events: List[str] = []

    def on_cart_change(new_cart, old_cart):
        events.append(
            f"🛒 {ANSI.GREEN}Cart Updated:{ANSI.RESET} {old_cart} -> {new_cart}"
        )

    def on_theme_change(new_theme, old_theme):
        events.append(
            f"🎨 {ANSI.MAGENTA}Theme Shift:{ANSI.RESET} {old_theme} -> {new_theme}"
        )

    store.subscribe_with_selector(lambda s: s["cart"], on_cart_change)
    store.subscribe_with_selector(lambda s: s["theme"], on_theme_change)

    print(f"{ANSI.DIM}Triggering Mutation 1: Adding cart item...{ANSI.RESET}")
    store.set_state(lambda prev: {
        **prev,
        "cart": {"items": ["React In-Depth Pro Guide"], "total": 85},
    })

    print(f"{ANSI.DIM}Triggering Mutation 2: Irrelevant update (User Role)...{ANSI.RESET}")
    store.set_state(lambda prev: {
        **prev,
        "user": {"name": "Alex", "role": "superadmin"},
    })

    print(f"{ANSI.DIM}Triggering Mutation 3: Theme Toggle...{ANSI.RESET}")
    store.set_state(lambda prev: {
        **prev,
        "theme": "light",
    })

    for event in events:
        print(f"  {event}")
    print(f"  {ANSI.YELLOW}⚡ Selector optimization notice: Mutation 2 bypassed cart/theme re-render listeners!{ANSI.RESET}")


def interactive_menu():
    while True:
        print(f"\n{ANSI.BOLD}=================================================================={ANSI.RESET}")
        print(f"{ANSI.BOLD}{ANSI.WHITE}  BAB-02: React Internals & State Management Interactive Lab{ANSI.RESET}")
        print(f"{ANSI.BOLD}=================================================================={ANSI.RESET}")
        print(f"  [{ANSI.CYAN}1{ANSI.RESET}] Fiber Reconciliation & Double-Buffering Simulation")
        print(f"  [{ANSI.CYAN}2{ANSI.RESET}] Concurrent Lanes & Time-Slicing Scheduler")
        print(f"  [{ANSI.CYAN}3{ANSI.RESET}] Zustand Micro-Store with Fine-Grained Selectors")
        print(f"  [{ANSI.CYAN}4{ANSI.RESET}] Run Full End-to-End Suite")
        print(f"  [{ANSI.RED}q{ANSI.RESET}] Exit Lab")
        choice = input(f"\n{ANSI.BOLD}Select an option (1-4, q): {ANSI.RESET}").strip().lower()

        if choice == "1":
            run_fiber_demo()
        elif choice == "2":
            run_scheduler_demo()
        elif choice == "3":
            run_zustand_demo()
        elif choice == "4":
            run_fiber_demo()
            run_scheduler_demo()
            run_zustand_demo()
        elif choice == "q":
            print(f"{ANSI.GREEN}Lab completed successfully. Exiting.{ANSI.RESET}")
            break
        else:
            print(f"{ANSI.RED}Invalid selection. Please choose 1, 2, 3, 4, or q.{ANSI.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_fiber_demo()
        run_scheduler_demo()
        run_zustand_demo()
    else:
        interactive_menu()
