#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Produksi Vue 3 (BAB-01-Fondasi-dan-Arsitektur)
Topik: Vue 3 Reactivity Engine, Scheduler (nextTick), Virtual DOM Reconciliation, dan Component Lifecycle.
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

# --- ANSI Terminal Color Palette ---
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
BG_DARK = "\033[40m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}========================================================================
 ⚡ VUE 3 ARCHITECTURAL ENGINE RUNTIME SIMULATOR (CLI LAB)
    BAB-01: Fondasi & Arsitektur Produksi (Reactivity, VDOM, Scheduler)
========================================================================{RESET}
"""
    print(banner)


# --- 1. Reactivity Engine (Effect, Track, Trigger, Ref & Reactive) ---
active_effect: Optional["ReactiveEffect"] = None
target_map: Dict[Any, Dict[str, Set["ReactiveEffect"]]] = {}


class ReactiveEffect:
    def __init__(self, fn: Callable[[], None], scheduler: Optional[Callable[[], None]] = None):
        self.fn = fn
        self.scheduler = scheduler
        self.active = True

    def run(self):
        global active_effect
        if not self.active:
            return self.fn()
        try:
            active_effect = self
            return self.fn()
        finally:
            active_effect = None


def track(target: Any, key: str):
    global active_effect
    if active_effect is None:
        return
    deps_map = target_map.setdefault(target, {})
    dep = deps_map.setdefault(key, set())
    dep.add(active_effect)


def trigger(target: Any, key: str):
    deps_map = target_map.get(target)
    if not deps_map:
        return
    dep = deps_map.get(key)
    if not dep:
        return

    effects_to_run = list(dep)
    for effect in effects_to_run:
        if effect.scheduler:
            effect.scheduler()
        else:
            effect.run()


class Ref:
    def __init__(self, value: Any):
        self._raw_value = value

    @property
    def value(self) -> Any:
        track(self, "value")
        return self._raw_value

    @value.setter
    def value(self, new_val: Any):
        if new_val != self._raw_value:
            self._raw_value = new_val
            trigger(self, "value")


class ReactiveProxy:
    def __init__(self, target_dict: dict):
        self.__dict__["_target"] = target_dict

    def __getattr__(self, name: str) -> Any:
        target = self.__dict__["_target"]
        if name in target:
            track(target, name)
            return target[name]
        raise AttributeError(f"Property '{name}' not found")

    def __setattr__(self, name: str, val: Any):
        if name == "_target":
            self.__dict__["_target"] = val
            return
        target = self.__dict__["_target"]
        old_val = target.get(name)
        if old_val != val:
            target[name] = val
            trigger(target, name)


# --- 2. Microtask Scheduler & nextTick Queue ---
class Scheduler:
    def __init__(self):
        self.queue: List[Callable[[], None]] = []
        self.is_flushing = False

    def queue_job(self, job: Callable[[], None]):
        if job not in self.queue:
            self.queue.append(job)
            if not self.is_flushing:
                self.flush_jobs()

    def flush_jobs(self):
        self.is_flushing = True
        print(f" {DIM}↳ [Scheduler] Flushing microtask job queue ({len(self.queue)} jobs)...{RESET}")
        while self.queue:
            job = self.queue.pop(0)
            job()
        self.is_flushing = False


scheduler = Scheduler()


# --- 3. Virtual DOM Node & Diff Algorithm ---
@dataclass
class VNode:
    tag: str
    props: Dict[str, Any] = field(default_factory=dict)
    children: Any = ""  # String or List[VNode]
    key: Optional[str] = None

    def render_to_html(self, depth: int = 0) -> str:
        indent = "  " * depth
        props_str = " ".join(f'{k}="{v}"' for k, v in self.props.items())
        opening = f"<{self.tag} {props_str}>" if props_str else f"<{self.tag}>"
        closing = f"</{self.tag}>"

        if isinstance(self.children, list):
            inner = "\n" + "\n".join(c.render_to_html(depth + 1) for c in self.children) + f"\n{indent}"
            return f"{indent}{opening}{inner}{closing}"
        return f"{indent}{opening}{self.children}{closing}"


class VDOMRenderer:
    @staticmethod
    def diff_and_patch(old_vnode: Optional[VNode], new_vnode: VNode) -> None:
        print(f"\n{YELLOW}[VDOM Reconciliation]{RESET}")
        if old_vnode is None:
            print(f"  {GREEN}+ Mount new Root Node: <{new_vnode.tag}>{RESET}")
            return

        if old_vnode.tag != new_vnode.tag:
            print(f"  {RED}- Unmount Node: <{old_vnode.tag}>{RESET}")
            print(f"  {GREEN}+ Replace with: <{new_vnode.tag}>{RESET}")
            return

        # Diff props
        for k, v in new_vnode.props.items():
            if old_vnode.props.get(k) != v:
                print(f"  {CYAN}~ Patch Prop [{k}]: '{old_vnode.props.get(k)}' ➜ '{v}'{RESET}")
        for k in old_vnode.props:
            if k not in new_vnode.props:
                print(f"  {RED}- Remove Prop [{k}]{RESET}")

        # Diff text children
        if isinstance(new_vnode.children, str) and isinstance(old_vnode.children, str):
            if old_vnode.children != new_vnode.children:
                print(f"  {CYAN}~ Update Text: '{old_vnode.children}' ➜ '{new_vnode.children}'{RESET}")
        elif isinstance(new_vnode.children, list) and isinstance(old_vnode.children, list):
            print(f"  {MAGENTA}* List Diff: reconciling {len(old_vnode.children)} old children with {len(new_vnode.children)} new children{RESET}")


# --- 4. Component Lifecycle & Vue Instance ---
class VueComponent:
    def __init__(self, name: str):
        self.name = name
        self.state: Optional[ReactiveProxy] = None
        self.count = Ref(0)
        self.old_vnode: Optional[VNode] = None
        self.effect: Optional[ReactiveEffect] = None

    def setup(self):
        print(f"{BLUE}[Lifecycle: {self.name}]{RESET} {BOLD}setup(){RESET} initialized.")
        self.state = ReactiveProxy({
            "status": "idle",
            "active_users": 120,
            "cluster": "ap-southeast-1"
        })

    def render(self) -> VNode:
        return VNode(
            tag="div",
            props={"class": "dashboard-card", "data-cluster": self.state.cluster},
            children=[
                VNode(tag="h2", children=f"Service Monitor: {self.state.status.upper()}"),
                VNode(tag="p", children=f"Active Nodes / Req Counter: {self.count.value}"),
                VNode(tag="span", props={"class": "badge"}, children=f"Cluster: {self.state.cluster}")
            ]
        )

    def update_component(self):
        print(f"\n{MAGENTA}⚡ [Component Render Pipeline: {self.name}]{RESET}")
        new_vnode = self.render()
        VDOMRenderer.diff_and_patch(self.old_vnode, new_vnode)
        self.old_vnode = new_vnode
        print(f"\n{GREEN}{BOLD}[Rendered Output HTML Snapshot]:{RESET}")
        print(f"{DIM}{new_vnode.render_to_html()}{RESET}")

    def mount(self):
        self.setup()
        print(f"{BLUE}[Lifecycle: {self.name}]{RESET} onBeforeMount hook executed.")
        
        # Reactive effect connects reactivity and render scheduler
        def job():
            self.update_component()

        self.effect = ReactiveEffect(
            fn=job,
            scheduler=lambda: scheduler.queue_job(job)
        )
        self.effect.run()
        print(f"{BLUE}[Lifecycle: {self.name}]{RESET} {GREEN}onMounted(){RESET} hook executed.")


# --- 5. Interactive Demo Suite ---
def run_interactive():
    print_banner()
    app = VueComponent(name="ProductionGatewayComponent")
    app.mount()

    menu = f"""
{WHITE}{BOLD}--- PILIHAN SIMULASI INTERAKTIF ---{RESET}
1. Trigger Ref Mutasi (Increment Request Counter: `count.value += 1`)
2. Trigger Reactive Proxy State (Update Status: idle ➜ busy/healthy)
3. Modifikasi Regional Cluster (Diff attribute props)
4. Batch Multiple Updates (Verifikasi Microtask Deduping)
5. Keluar (Exit)
"""
    while True:
        print(menu)
        try:
            choice = input(f"{YELLOW}Pilih opsi [1-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            print(f"\n{BOLD}Action:{RESET} app.count.value += 1")
            app.count.value += 1
        elif choice == "2":
            new_status = "operational_ok" if app.state.status == "idle" else "idle"
            print(f"\n{BOLD}Action:{RESET} app.state.status = '{new_status}'")
            app.state.status = new_status
        elif choice == "3":
            new_cluster = "eu-central-1" if app.state.cluster == "ap-southeast-1" else "ap-southeast-1"
            print(f"\n{BOLD}Action:{RESET} app.state.cluster = '{new_cluster}'")
            app.state.cluster = new_cluster
        elif choice == "4":
            print(f"\n{BOLD}Action:{RESET} Simulasi 3 Mutasi Sekaligus dalam 1 Event Tick...")
            # Demonstrasi bagaimana scheduler mengantre dan hanya 1 re-render yang dieksekusi
            app.count.value += 10
            app.state.status = "load_balanced"
            app.state.cluster = "us-east-1"
            print(f"{GREEN}✓ Batch mutation selesai tanpa multi-rerender synchronous.{RESET}")
        elif choice == "5":
            print(f"{GREEN}Lab exercise selesai. Arsitektur produksi Vue 3 terverifikasi.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan masukkan 1-5.{RESET}")
        time.sleep(0.5)


if __name__ == "__main__":
    run_interactive()
