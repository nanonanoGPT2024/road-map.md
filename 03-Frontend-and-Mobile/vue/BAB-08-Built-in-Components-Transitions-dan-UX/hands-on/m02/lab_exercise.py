#!/usr/bin/env python3
"""
Lab Exercise M02: Advanced Vue 3 Built-in Components, Transitions, & UX Engine
Simulation of <Transition>, <TransitionGroup>, <KeepAlive>, <Teleport>, and <Suspense>
Production-grade Architectural Simulation with ANSI Terminal Visualizer.
"""

import sys
import time
import collections
from typing import Dict, List, Optional, Any, Callable

# ==============================================================================
# ANSI Color Formatting & Terminal Styling
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Background colors
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_BLACK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === [VUE 3 CORE ENGINE] {title.upper()} === {Color.RESET}\n")


def status_badge(name: str, state: str, color: str) -> str:
    return f"{Color.BOLD}[{color}{name}: {state}{Color.RESET}{Color.BOLD}]{Color.RESET}"


# ==============================================================================
# 1. <Transition> and <TransitionGroup> FLIP Engine
# ==============================================================================
class VueTransitionEngine:
    """Simulates Vue 3 CSS Transition lifecycle classes & FLIP animations."""
    
    def __init__(self, name: str = "v", mode: Optional[str] = "out-in"):
        self.name = name
        self.mode = mode  # 'in-out' | 'out-in' | None
        
    def transition_enter(self, element_id: str) -> None:
        print(f"  {status_badge('TRANSITION', 'ENTER_START', Color.CYAN)} Component: {Color.BOLD}{element_id}{Color.RESET}")
        phases = [
            (f"{self.name}-enter-from", "Initial state: opacity=0, transform=translateY(20px)", 0.08),
            (f"{self.name}-enter-active", "Transitioning: transition=all 300ms cubic-bezier(0.16, 1, 0.3, 1)", 0.12),
            (f"{self.name}-enter-to", "Target state: opacity=1, transform=translateY(0)", 0.08),
        ]
        for css_class, desc, delay in phases:
            print(f"    {Color.GREEN}--> Applied class .{css_class:<20}{Color.RESET} {Color.DIM}({desc}){Color.RESET}")
            time.sleep(delay)
        print(f"  {status_badge('TRANSITION', 'ENTER_COMPLETE', Color.GREEN)} {element_id} mounted smoothly.\n")

    def transition_leave(self, element_id: str) -> None:
        print(f"  {status_badge('TRANSITION', 'LEAVE_START', Color.YELLOW)} Component: {Color.BOLD}{element_id}{Color.RESET}")
        phases = [
            (f"{self.name}-leave-from", "Active state: opacity=1, transform=scale(1)", 0.08),
            (f"{self.name}-leave-active", "Transitioning: transition=opacity 250ms ease-in", 0.12),
            (f"{self.name}-leave-to", "Target state: opacity=0, transform=scale(0.95)", 0.08),
        ]
        for css_class, desc, delay in phases:
            print(f"    {Color.YELLOW}--> Applied class .{css_class:<20}{Color.RESET} {Color.DIM}({desc}){Color.RESET}")
            time.sleep(delay)
        print(f"  {status_badge('TRANSITION', 'LEAVE_COMPLETE', Color.RED)} {element_id} unmounted cleanly.\n")

    def flip_reorder(self, items: List[str], reordered: List[str]) -> None:
        """Simulates FLIP (First, Last, Invert, Play) technique used by <TransitionGroup>."""
        print(f"  {status_badge('TRANSITION_GROUP', 'FLIP_COORDINATOR', Color.MAGENTA)}")
        print(f"    {Color.BOLD}Initial List:{Color.RESET} {items}")
        # 1. First: Record bounding boxes (mock coordinates)
        first_pos = {item: idx * 40 for idx, item in enumerate(items)}
        
        # 2. Last: Target state layout
        print(f"    {Color.BOLD}Updated List:{Color.RESET} {reordered}")
        last_pos = {item: idx * 40 for idx, item in enumerate(reordered)}
        
        # 3. Invert & 4. Play
        print(f"    {Color.CYAN}Applying FLIP calculations:{Color.RESET}")
        for item in reordered:
            delta_y = first_pos[item] - last_pos[item]
            inv_str = f"transform: translateY({delta_y:+3d}px)" if delta_y != 0 else "in-place (no offset)"
            print(f"      • Item [{Color.BOLD}{item}{Color.RESET}]: Invert ({inv_str}) -> Play transition to 0px")
        time.sleep(0.2)
        print(f"  {Color.GREEN}✔ FLIP animation frame painted (v-move applied).{Color.RESET}\n")


# ==============================================================================
# 2. <KeepAlive> LRU Cache Simulation
# ==============================================================================
class VueKeepAliveContainer:
    """Simulates Vue 3 <KeepAlive :max="N" :include="..." :exclude="..."> LRU Cache."""
    
    def __init__(self, max_capacity: int = 3):
        self.max_capacity = max_capacity
        self.cache: collections.OrderedDict[str, Dict[str, Any]] = collections.OrderedDict()
        self.current_active: Optional[str] = None
        
    def render_component(self, comp_name: str, state_payload: Dict[str, Any]) -> None:
        print(f"\n{status_badge('KEEPALIVE', 'NAVIGATE', Color.CYAN)} Requested: {Color.BOLD}{comp_name}{Color.RESET}")
        
        # Deactivate current if active
        if self.current_active and self.current_active != comp_name:
            self._deactivate(self.current_active)
            
        if comp_name in self.cache:
            # Cache hit: Move to MRU position
            self.cache.move_to_end(comp_name)
            vnode = self.cache[comp_name]
            print(f"  {Color.GREEN}✔ Cache Hit! Restoring VNode state from cache.{Color.RESET}")
            self._activate(comp_name, vnode)
        else:
            # Cache miss: instantiate and mount
            print(f"  {Color.YELLOW}⚡ Cache Miss! Initializing new instance & component lifecycle.{Color.RESET}")
            if len(self.cache) >= self.max_capacity:
                evicted_key, evicted_val = self.cache.popitem(last=False)  # LRU eviction
                print(f"  {Color.RED}⚠ Max capacity ({self.max_capacity}) reached! Evicting LRU: [{evicted_key}] (Destroyed){Color.RESET}")
            
            new_vnode = {
                "name": comp_name,
                "state": state_payload,
                "created_at": time.time(),
            }
            self.cache[comp_name] = new_vnode
            self._activate(comp_name, new_vnode, is_initial=True)
            
        self.current_active = comp_name
        self.inspect_cache()

    def _activate(self, comp_name: str, vnode: Dict[str, Any], is_initial: bool = False) -> None:
        if is_initial:
            print(f"    ↳ {Color.CYAN}onMounted(){Color.RESET} executed for {comp_name}")
        print(f"    ↳ {Color.GREEN}onActivated(){Color.RESET} invoked. Restored form state: {vnode['state']}")

    def _deactivate(self, comp_name: str) -> None:
        print(f"    ↳ {Color.YELLOW}onDeactivated(){Color.RESET} invoked for {comp_name}. Frozen in cache.")

    def inspect_cache(self) -> None:
        cached_keys = list(self.cache.keys())
        print(f"  {Color.DIM}Current LRU Cache Stack (Most Recent at Right): {Color.RESET}"
              f"{Color.MAGENTA}{cached_keys}{Color.RESET} ({len(cached_keys)}/{self.max_capacity})")


# ==============================================================================
# 3. <Teleport> DOM Target Resolver
# ==============================================================================
class VueTeleportEngine:
    """Simulates Vue 3 <Teleport to="#modal-target" :disabled="isDisabled">."""
    
    def __init__(self):
        self.dom_tree = {
            "#app": ["HeaderBar", "MainLayout", "Footer"],
            "#modal-target": [],
            "#notification-drawer": []
        }
        
    def teleport(self, component_name: str, to: str, disabled: bool = False) -> None:
        target = "#app" if disabled else to
        print(f"\n{status_badge('TELEPORT', 'MOUNT', Color.BLUE)} Component: {Color.BOLD}{component_name}{Color.RESET}")
        print(f"  Param: to='{to}' | :disabled={disabled}")
        
        if target not in self.dom_tree:
            print(f"  {Color.RED}✖ Error: Target container '{target}' not found in DOM.{Color.RESET}")
            return
            
        # Clean from other targets
        for container in self.dom_tree.values():
            if component_name in container:
                container.remove(component_name)
                
        self.dom_tree[target].append(component_name)
        mode_text = "Standard Normal App Flow (Disabled)" if disabled else f"Ported to DOM '{target}'"
        print(f"  {Color.GREEN}✔ Successfully mounted: {mode_text}{Color.RESET}")
        self.dump_dom()

    def dump_dom(self) -> None:
        print(f"  {Color.CYAN}DOM Hierarchy Snapshot:{Color.RESET}")
        for selector, nodes in self.dom_tree.items():
            print(f"    ├── {Color.BOLD}{selector}{Color.RESET} -> {nodes}")


# ==============================================================================
# 4. <Suspense> Async Resolution & Fallback Coordinator
# ==============================================================================
class VueSuspenseCoordinator:
    """Simulates Vue 3 <Suspense> async component loading and error boundaries."""
    
    def load_async_branch(self, component_name: str, delay_sec: float, should_fail: bool = False) -> None:
        print(f"\n{status_badge('SUSPENSE', 'PENDING', Color.YELLOW)} Loading: {Color.BOLD}{component_name}{Color.RESET}")
        print(f"  {Color.DIM}Rendering #fallback slot: <SkeletonLoader :animated=\"true\" />...{Color.RESET}")
        
        # Simulate loading tick
        ticks = 4
        interval = delay_sec / ticks
        for i in range(ticks):
            time.sleep(interval)
            print(f"    {Color.YELLOW}• [Suspense] Async setup promise pending... ({(i+1)*25}%){Color.RESET}")
            
        if should_fail:
            print(f"  {status_badge('SUSPENSE', 'ERROR', Color.RED)} Async setup() rejected!")
            print(f"  {Color.RED}↳ onErrorCaptured() triggered: Displaying fallback error state.{Color.RESET}\n")
        else:
            print(f"  {status_badge('SUSPENSE', 'RESOLVED', Color.GREEN)} Promise resolved successfully!")
            print(f"  {Color.GREEN}↳ Transitioning from #fallback slot to default slot: <{component_name} />.{Color.RESET}\n")


# ==============================================================================
# Main Interactive Runner & Scenarios
# ==============================================================================
def print_menu() -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}===================================================={Color.RESET}")
    print(f"{Color.BOLD}   VUE 3 BUILT-IN COMPONENTS & UX ARCHITECTURE LAB   {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}===================================================={Color.RESET}")
    print(f" {Color.BOLD}1.{Color.RESET} Test <Transition> (Enter / Leave CSS Lifecycle)")
    print(f" {Color.BOLD}2.{Color.RESET} Test <TransitionGroup> (FLIP List Reordering)")
    print(f" {Color.BOLD}3.{Color.RESET} Test <KeepAlive> (LRU Memory & Activation Cycles)")
    print(f" {Color.BOLD}4.{Color.RESET} Test <Teleport> (DOM Target Switching & Portals)")
    print(f" {Color.BOLD}5.{Color.RESET} Test <Suspense> (Async Dependencies & Fallbacks)")
    print(f" {Color.BOLD}6.{Color.RESET} Run Full Automated Architectural Test Suite")
    print(f" {Color.BOLD}0.{Color.RESET} Exit")
    print(f"{Color.CYAN}----------------------------------------------------{Color.RESET}")


def run_full_suite() -> None:
    header("Automated End-to-End Architectural Test Suite")
    
    # 1. Transitions
    print(f"{Color.BOLD}--- Step 1: Transition Lifecycle ---{Color.RESET}")
    t_engine = VueTransitionEngine(name="fade-slide")
    t_engine.transition_enter("UserProfileModal")
    t_engine.transition_leave("UserProfileModal")
    
    # 2. FLIP
    print(f"{Color.BOLD}--- Step 2: TransitionGroup FLIP ---{Color.RESET}")
    initial_items = ["Task-A", "Task-B", "Task-C", "Task-D"]
    reordered_items = ["Task-C", "Task-A", "Task-D", "Task-B"]
    t_engine.flip_reorder(initial_items, reordered_items)
    
    # 3. KeepAlive
    print(f"{Color.BOLD}--- Step 3: KeepAlive LRU Engine ---{Color.RESET}")
    keepalive = VueKeepAliveContainer(max_capacity=2)
    keepalive.render_component("InboxTab", {"unread": 12, "draft": "Draft v1"})
    keepalive.render_component("SettingsTab", {"theme": "dark", "lang": "id"})
    keepalive.render_component("AnalyticsTab", {"charts_loaded": True})  # Causes InboxTab eviction
    keepalive.render_component("SettingsTab", {"theme": "dark", "lang": "id"}) # Cache hit
    
    # 4. Teleport
    print(f"\n{Color.BOLD}--- Step 4: Teleport Portals ---{Color.RESET}")
    teleport = VueTeleportEngine()
    teleport.teleport("ConfirmDialog", "#modal-target", disabled=False)
    teleport.teleport("ConfirmDialog", "#modal-target", disabled=True)
    
    # 5. Suspense
    print(f"\n{Color.BOLD}--- Step 5: Suspense Async Resolution ---{Color.RESET}")
    suspense = VueSuspenseCoordinator()
    suspense.load_async_branch("AsyncDashboardWidget", delay_sec=0.4, should_fail=False)
    suspense.load_async_branch("FaultyMicrofrontend", delay_sec=0.3, should_fail=True)
    
    print(f"{Color.BOLD}{Color.GREEN}✔ Architectural simulation suite completed with zero failures.{Color.RESET}\n")


def interactive_loop() -> None:
    while True:
        try:
            print_menu()
            choice = input(f"{Color.BOLD}Select an option [0-6]: {Color.RESET}").strip()
            
            if choice == "1":
                header("Interactive <Transition>")
                name = input("Enter transition name prefix [default: 'fade']: ").strip() or "fade"
                engine = VueTransitionEngine(name=name)
                comp = input("Component identifier [e.g., DialogView]: ").strip() or "DialogView"
                engine.transition_enter(comp)
                engine.transition_leave(comp)
            elif choice == "2":
                header("Interactive <TransitionGroup> FLIP")
                engine = VueTransitionEngine()
                items = ["Auth", "Dashboard", "Billing", "Settings"]
                engine.flip_reorder(items, ["Billing", "Settings", "Auth", "Dashboard"])
            elif choice == "3":
                header("Interactive <KeepAlive> Cache Engine")
                ka = VueKeepAliveContainer(max_capacity=3)
                ka.render_component("Tab1-Feed", {"scrollPos": 450})
                ka.render_component("Tab2-Messages", {"activeChat": 42})
                ka.render_component("Tab3-Profile", {"dirty": False})
                ka.render_component("Tab4-Settings", {"volume": 80})  # Evicts Tab1
                ka.render_component("Tab2-Messages", {"activeChat": 42}) # Hit
            elif choice == "4":
                header("Interactive <Teleport>")
                tp = VueTeleportEngine()
                tp.teleport("AlertModal", "#modal-target", disabled=False)
                input(f"{Color.DIM}Press Enter to toggle :disabled='true'...{Color.RESET}")
                tp.teleport("AlertModal", "#modal-target", disabled=True)
            elif choice == "5":
                header("Interactive <Suspense>")
                sp = VueSuspenseCoordinator()
                sp.load_async_branch("HeavyDatagridAsync", delay_sec=0.6, should_fail=False)
            elif choice == "6":
                run_full_suite()
            elif choice == "0":
                print(f"\n{Color.CYAN}Exiting Vue UX Architecture Lab. Goodbye!{Color.RESET}")
                break
            else:
                print(f"{Color.RED}Invalid option, please choose between 0 and 6.{Color.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.CYAN}Session terminated.{Color.RESET}")
            break


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--auto", "-a"):
        run_full_suite()
    else:
        interactive_loop()
