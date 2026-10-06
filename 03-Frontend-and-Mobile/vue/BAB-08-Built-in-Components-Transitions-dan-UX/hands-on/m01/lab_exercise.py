#!/usr/bin/env python3
"""
Simulasi Teknis Fondasi Inti Vue 3 - Built-in Components, Transitions, & UX
BAB-08: <Transition>, <TransitionGroup> (FLIP), <KeepAlive> (LRU), <Teleport>, & <Suspense>
"""

import sys
import time
import re
from typing import Dict, List, Optional, Any, Callable
from collections import OrderedDict

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BG_BLUE = "\033[44m\033[37m"
BG_GREEN = "\033[42m\033[30m"

def print_banner(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{YELLOW} [VUE 3 BUILT-IN CORE SIMULATOR] {RESET}- {BOLD}{title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")

def print_step(step: str, detail: str):
    print(f"  {BLUE}▶{RESET} {BOLD}{step:<24}{RESET}: {detail}")


# ============================================================================
# 1. <Transition> Engine (CSS Class Phase & JS Hook Lifecycle)
# ============================================================================
class TransitionEngine:
    def __init__(self, name: str = "v", mode: str = "default"):
        self.name = name
        self.mode = mode  # 'default', 'out-in', 'in-out'
        self.current_view: Optional[str] = None

    def enter(self, view_name: str, js_hooks: Optional[Dict[str, Callable]] = None):
        print(f"\n{BOLD}{MAGENTA}[Transition: ENTER Phase -> '{view_name}']{RESET}")
        
        # JS Hook: before-enter
        if js_hooks and "before_enter" in js_hooks:
            print_step("Hook: @before-enter", f"Setting initial style (opacity: 0, transform: translateY(20px))")
            js_hooks["before_enter"](view_name)
        
        # Phase 1: enter-from + enter-active
        print_step("Class Applied", f"{self.name}-enter-from + {self.name}-enter-active")
        time.sleep(0.08)

        # Phase 2: enter-to
        print_step("DOM Next Frame", f"Remove {self.name}-enter-from -> Add {self.name}-enter-to")
        if js_hooks and "enter" in js_hooks:
            print_step("Hook: @enter", f"Executing animation transition (duration: 300ms)")
            js_hooks["enter"](view_name)
        time.sleep(0.08)

        # Cleanup
        print_step("Transition End", f"Remove {self.name}-enter-active + {self.name}-enter-to (Element Mounted)")
        if js_hooks and "after_enter" in js_hooks:
            print_step("Hook: @after-enter", f"Transition complete callback triggered")
            js_hooks["after_enter"](view_name)
        self.current_view = view_name

    def leave(self, view_name: str, js_hooks: Optional[Dict[str, Callable]] = None):
        print(f"\n{BOLD}{MAGENTA}[Transition: LEAVE Phase -> '{view_name}']{RESET}")
        
        if js_hooks and "before_leave" in js_hooks:
            print_step("Hook: @before-leave", f"Capturing current computed style")
            js_hooks["before_leave"](view_name)

        print_step("Class Applied", f"{self.name}-leave-from + {self.name}-leave-active")
        time.sleep(0.08)

        print_step("DOM Next Frame", f"Remove {self.name}-leave-from -> Add {self.name}-leave-to")
        if js_hooks and "leave" in js_hooks:
            print_step("Hook: @leave", f"Executing leave animation")
            js_hooks["leave"](view_name)
        time.sleep(0.08)

        print_step("Transition End", f"Remove {self.name}-leave-active + {self.name}-leave-to -> Element Unmounted")
        if js_hooks and "after_leave" in js_hooks:
            print_step("Hook: @after-leave", f"Cleanup callback executed")
            js_hooks["after_leave"](view_name)
        self.current_view = None

    def switch_view(self, next_view: str):
        print(f"\n{BOLD}{YELLOW}Switching Component View (mode='{self.mode}') {self.current_view} -> {next_view}{RESET}")
        if self.mode == "out-in":
            if self.current_view:
                self.leave(self.current_view)
            self.enter(next_view)
        elif self.mode == "in-out":
            self.enter(next_view)
            if self.current_view:
                self.leave(self.current_view)
        else:
            # Default concurrent
            if self.current_view:
                self.leave(self.current_view)
            self.enter(next_view)


# ============================================================================
# 2. <TransitionGroup> (FLIP Technique Simulation)
# ============================================================================
class TransitionGroupFLIP:
    """Simulates Vue 3's FLIP (First, Last, Invert, Play) list reorder animation."""
    def __init__(self):
        self.items: List[str] = []
        self.positions: Dict[str, int] = {}

    def set_items(self, items: List[str]):
        self.items = list(items)
        self.positions = {item: idx * 40 for idx, item in enumerate(self.items)}

    def reorder(self, new_items: List[str]):
        print(f"\n{BOLD}{MAGENTA}[TransitionGroup: FLIP List Reorder]{RESET}")
        print_step("1. First (F)", f"Recording initial bounding rect coordinates: {self.positions}")
        old_positions = dict(self.positions)

        # 2. Last (L)
        self.items = list(new_items)
        new_positions = {item: idx * 40 for idx, item in enumerate(self.items)}
        print_step("2. Last (L)", f"Applying DOM mutations & calculating final coordinates: {new_positions}")

        # 3. Invert (I)
        print_step("3. Invert (I)", "Calculating inverted transform delta (dx, dy):")
        inversions = {}
        for item in self.items:
            if item in old_positions:
                delta_y = old_positions[item] - new_positions[item]
                inversions[item] = delta_y
                print(f"      - Element [{item}]: deltaY = {delta_y:+}px -> `transform: translateY({delta_y}px)`")

        # 4. Play (P)
        print_step("4. Play (P)", "Forcing reflow, applying .v-move { transition: transform 0.5s ease }")
        print_step("Animation", f"{GREEN}Removing inline transforms -> smoothly sliding elements into target slots!{RESET}")
        self.positions = new_positions


# ============================================================================
# 3. <KeepAlive> Component Cache (LRU Caching & Lifecycle)
# ============================================================================
class KeepAliveCache:
    """Simulates Vue 3 <KeepAlive max=N include=... exclude=...> with LRU algorithm."""
    def __init__(self, max_size: int = 3, include: Optional[str] = None, exclude: Optional[str] = None):
        self.max_size = max_size
        self.include = include
        self.exclude = exclude
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    def _is_match(self, pattern: Optional[str], name: str) -> bool:
        if not pattern:
            return False
        return bool(re.search(pattern, name))

    def render_component(self, comp_name: str, state_payload: Dict[str, Any]) -> str:
        print(f"\n{BOLD}{MAGENTA}[KeepAlive: Requesting component <{comp_name}/>]{RESET}")

        # Check include / exclude rules
        if self.include and not self._is_match(self.include, comp_name):
            print_step("Cache Rule", f"Skipping cache: '{comp_name}' does not match include='{self.include}'")
            return f"Mounted fresh (not cached): {comp_name}"

        if self.exclude and self._is_match(self.exclude, comp_name):
            print_step("Cache Rule", f"Skipping cache: '{comp_name}' matches exclude='{self.exclude}'")
            return f"Mounted fresh (excluded): {comp_name}"

        # Check Cache Hit
        if comp_name in self.cache:
            # Move to MRU (Most Recently Used)
            self.cache.move_to_end(comp_name)
            entry = self.cache[comp_name]
            print_step(f"{BG_GREEN} CACHE HIT {RESET}", f"Restoring component instance <{comp_name}/> from memory")
            print_step("Lifecycle Hook", f"{GREEN}@onActivated(){RESET} fired on <{comp_name}/>! Saved State: {entry['state']}")
            return f"Active (Cached): {comp_name}"

        # Cache Miss
        print_step(f"{RED}CACHE MISS{RESET}", f"Creating fresh instance for <{comp_name}/>")
        if len(self.cache) >= self.max_size:
            # Evict LRU (first item in OrderedDict)
            evicted_name, evicted_val = self.cache.popitem(last=False)
            print_step("Eviction (LRU)", f"{RED}Purged least recently used <{evicted_name}/> (Destroyed & Unmounted){RESET}")

        # Store in cache
        self.cache[comp_name] = {
            "name": comp_name,
            "state": state_payload,
            "created_at": time.time()
        }
        print_step("Lifecycle Hook", f"{CYAN}@onMounted(){RESET} executed for <{comp_name}/>")
        print_step("Cache Status", f"Current active cache keys: {list(self.cache.keys())}")
        return f"Active (New Cached): {comp_name}"

    def deactivate(self, comp_name: str):
        if comp_name in self.cache:
            print_step("Lifecycle Hook", f"{YELLOW}@onDeactivated(){RESET} fired for <{comp_name}/> (Preserving state in memory)")


# ============================================================================
# 4. <Teleport> Simulation (Target Container Mounting)
# ============================================================================
class TeleportManager:
    """Simulates Vue 3 <Teleport to="#target" :disabled="isDisabled">."""
    def __init__(self):
        self.dom_nodes: Dict[str, List[str]] = {
            "#app": ["<RootLayout>", "<Navbar>"],
            "#modal-root": [],
            "#toast-portal": []
        }

    def teleport_node(self, node: str, target: str, disabled: bool = False):
        print(f"\n{BOLD}{MAGENTA}[<Teleport to='{target}' :disabled={str(disabled).lower()}>]{RESET}")
        
        actual_target = "#app" if disabled else target
        
        if actual_target not in self.dom_nodes:
            print(f"  {RED}✖ Teleport Error: Target container '{actual_target}' not found in DOM!{RESET}")
            return False

        if not disabled:
            print_step("Teleporting", f"Transferring '{node}' out of local DOM hierarchy into '{actual_target}'")
        else:
            print_step("Disabled Mode", f"Rendering '{node}' directly inside current parent component (#app)")

        self.dom_nodes[actual_target].append(node)
        self.render_dom()
        return True

    def render_dom(self):
        print(f"\n{BOLD}{CYAN}Current Virtual DOM Layout:{RESET}")
        for container, children in self.dom_nodes.items():
            print(f"  {YELLOW}{container}{RESET} -> {children if children else '[Empty]'}")


# ============================================================================
# 5. <Suspense> Orchestrator (Async Dependencies Resolution)
# ============================================================================
class SuspenseOrchestrator:
    """Simulates Vue 3 <Suspense> #default and #fallback slot orchestration."""
    def __init__(self):
        self.resolved = False

    def load_async_tree(self, async_components: List[Dict[str, Any]]):
        print(f"\n{BOLD}{MAGENTA}[<Suspense> Async Boundary Execution]{RESET}")
        print_step("Slot Active", f"{YELLOW}#fallback (Skeleton Loader / Spinner Active){RESET}")
        
        for comp in async_components:
            name = comp["name"]
            delay = comp.get("delay", 0.1)
            print_step("Async Setup", f"Awaiting async setup() for <{name}/> ({int(delay*1000)}ms latency)...")
            time.sleep(delay)
            print(f"      {GREEN}✔ Component <{name}/> resolved successfully!{RESET}")

        self.resolved = True
        print_step("Slot Transition", f"{GREEN}All async dependencies resolved! Toggling #fallback -> #default slot.{RESET}")


# ============================================================================
# Interactive CLI Driver
# ============================================================================
def run_interactive_demo():
    print_banner("Vue 3 Built-in Components Technical Simulator")
    print(f"{DIM}Exploring architectural mechanics of Transition, FLIP, KeepAlive, Teleport, & Suspense.{RESET}\n")

    # 1. Transition Demo
    trans = TransitionEngine(name="fade", mode="out-in")
    trans.enter("UserProfileView")
    trans.switch_view("SettingsView")

    # 2. TransitionGroup FLIP Demo
    tg = TransitionGroupFLIP()
    tg.set_items(["Item-A", "Item-B", "Item-C", "Item-D"])
    tg.reorder(["Item-C", "Item-A", "Item-D", "Item-B"])

    # 3. KeepAlive LRU Demo
    ka = KeepAliveCache(max_size=2, exclude="^Transient")
    ka.render_component("TabPosts", {"scrollPos": 420, "inputs": "Draft text"})
    ka.render_component("TabProfile", {"userId": 101})
    ka.render_component("TransientPopup", {"ephemeral": True})
    # This 3rd cached component should trigger LRU eviction of TabPosts
    ka.render_component("TabSettings", {"theme": "dark"})
    # Re-access TabProfile (Cache Hit)
    ka.render_component("TabProfile", {"userId": 101})

    # 4. Teleport Demo
    tp = TeleportManager()
    tp.teleport_node("<CookieBannerModal/>", "#modal-root", disabled=False)
    tp.teleport_node("<InlineNotification/>", "#toast-portal", disabled=True)

    # 5. Suspense Demo
    suspense = SuspenseOrchestrator()
    suspense.load_async_tree([
        {"name": "AsyncUserFeed", "delay": 0.05},
        {"name": "AsyncCommentList", "delay": 0.08}
    ])

    print(f"\n{BOLD}{BG_GREEN} SUCCESS {RESET} {GREEN}Semua simulasi teknis Built-in Components Vue 3 selesai tanpa error!{RESET}\n")


if __name__ == "__main__":
    try:
        run_interactive_demo()
    except KeyboardInterrupt:
        print(f"\n{RED}Simulasi dihentikan oleh user.{RESET}")
        sys.exit(0)
