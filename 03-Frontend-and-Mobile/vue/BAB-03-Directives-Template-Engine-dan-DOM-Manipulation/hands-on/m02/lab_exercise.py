#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Template Engine, Directives & DOM Reconciliation Vue.js
BAB-03: Directives, Template Engine, dan DOM Manipulation
"""

import re
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


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


class VNode:
    """Virtual DOM Node representation."""
    def __init__(
        self,
        tag: str,
        props: Optional[Dict[str, Any]] = None,
        children: Optional[List[Any]] = None,
        text: Optional[str] = None,
        key: Optional[str] = None,
    ):
        self.tag = tag
        self.props = props or {}
        self.children = children or []
        self.text = text
        self.key = key

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "key": self.key,
            "props": self.props,
            "text": self.text,
            "children_count": len(self.children),
        }


class ReactiveState:
    """Reactivity store mimicking Vue's Proxy and Dependency Tracking."""
    def __init__(self, initial_data: Dict[str, Any]):
        self._data = initial_data
        self._subscribers: List[Callable[[], None]] = []

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        old_val = self._data.get(key)
        if old_val != value:
            self._data[key] = value
            self._notify(key, old_val, value)

    def subscribe(self, callback: Callable[[], None]) -> None:
        self._subscribers.append(callback)

    def _notify(self, key: str, old_val: Any, new_val: Any) -> None:
        print(
            f"{ANSI.YELLOW}[Reactivity Trigger]{ANSI.RESET} Property "
            f"'{ANSI.BOLD}{key}{ANSI.RESET}' changed: {ANSI.RED}{repr(old_val)}{ANSI.RESET} -> "
            f"{ANSI.GREEN}{repr(new_val)}{ANSI.RESET}"
        )
        for cb in self._subscribers:
            cb()


class TemplateCompiler:
    """
    Simulates Vue's Template Compiler:
    Translates template AST / directives (v-if, v-for, v-bind, v-on, v-model) into render functions.
    """
    @staticmethod
    def interpolate(text: str, context: Dict[str, Any]) -> str:
        pattern = r"\{\{\s*([\w\.]+)\s*\}\}"
        def repl(match: re.Match) -> str:
            key = match.group(1)
            return str(context.get(key, ""))
        return re.sub(pattern, repl, text)

    @staticmethod
    def render(state: Dict[str, Any]) -> VNode:
        root_children: List[VNode] = []

        # Header node
        title_text = f"Vue Reactive Store Preview ({state.get('user_name', 'Guest')})"
        root_children.append(
            VNode(
                tag="h1",
                props={"class": "title"},
                text=title_text,
                key="header"
            )
        )

        # v-if="is_authenticated"
        if state.get("is_authenticated"):
            auth_panel = VNode(
                tag="section",
                props={"class": "badge-auth", "role": "status"},
                children=[
                    VNode(
                        tag="p",
                        text=f"Status: Authenticated as {state.get('user_name')} [Role: {state.get('role', 'Developer')}]",
                        key="auth-p"
                    )
                ],
                key="auth-panel"
            )
            root_children.append(auth_panel)
        else:
            guest_panel = VNode(
                tag="section",
                props={"class": "badge-guest"},
                children=[
                    VNode(
                        tag="p",
                        text="Status: Anonymous Guest (Please log in to submit tasks)",
                        key="guest-p"
                    )
                ],
                key="guest-panel"
            )
            root_children.append(guest_panel)

        # v-for="(item, idx) in tasks" :key="item.id"
        tasks = state.get("tasks", [])
        task_nodes: List[VNode] = []
        for task in tasks:
            status_tag = "[DONE]" if task.get("completed") else "[PENDING]"
            task_nodes.append(
                VNode(
                    tag="li",
                    props={
                        "class": "task-item",
                        "data-id": task["id"],
                        "data-status": "done" if task.get("completed") else "todo",
                    },
                    text=f"{task['id']}: {task['title']} {status_tag}",
                    key=f"task-{task['id']}"
                )
            )

        task_list_vnode = VNode(
            tag="ul",
            props={"class": "task-list", "id": "task-container"},
            children=task_nodes,
            key="task-ul"
        )
        root_children.append(task_list_vnode)

        # Footer stats
        root_children.append(
            VNode(
                tag="footer",
                props={"class": "footer"},
                text=f"Total Tasks: {len(tasks)} | Counter: {state.get('counter', 0)}",
                key="footer"
            )
        )

        return VNode(
            tag="div",
            props={"id": "app", "class": "container"},
            children=root_children,
            key="app-root"
        )


class DOMReconciler:
    """
    Virtual DOM Diffing & Patch Engine.
    Emulates Vue 3 Fast Path & Keyed Children Reconciliation.
    """
    def __init__(self):
        self.patch_log: List[str] = []

    def diff_and_patch(
        self,
        old_vnode: Optional[VNode],
        new_vnode: Optional[VNode],
        depth: int = 0
    ) -> None:
        indent = "  " * depth

        # 1. Mount new node
        if old_vnode is None and new_vnode is not None:
            msg = f"{indent}{ANSI.GREEN}+ MOUNT <{new_vnode.tag}> key={new_vnode.key} text={repr(new_vnode.text)}{ANSI.RESET}"
            self.patch_log.append(msg)
            for child in new_vnode.children:
                self.diff_and_patch(None, child, depth + 1)
            return

        # 2. Unmount old node
        if old_vnode is not None and new_vnode is None:
            msg = f"{indent}{ANSI.RED}- UNMOUNT <{old_vnode.tag}> key={old_vnode.key}{ANSI.RESET}"
            self.patch_log.append(msg)
            return

        if old_vnode is None or new_vnode is None:
            return

        # 3. Replace node completely if tags or keys mismatch
        if old_vnode.tag != new_vnode.tag or old_vnode.key != new_vnode.key:
            msg = (
                f"{indent}{ANSI.MAGENTA}~ REPLACE <{old_vnode.tag} key={old_vnode.key}> "
                f"WITH <{new_vnode.tag} key={new_vnode.key}>{ANSI.RESET}"
            )
            self.patch_log.append(msg)
            return

        # 4. Patch Props
        if old_vnode.props != new_vnode.props:
            prop_diffs = []
            all_keys = set(old_vnode.props.keys()) | set(new_vnode.props.keys())
            for k in all_keys:
                if old_vnode.props.get(k) != new_vnode.props.get(k):
                    prop_diffs.append(f"{k}: {old_vnode.props.get(k)} -> {new_vnode.props.get(k)}")
            msg = f"{indent}{ANSI.CYAN}* PATCH PROPS <{new_vnode.tag}>: [{', '.join(prop_diffs)}]{ANSI.RESET}"
            self.patch_log.append(msg)

        # 5. Patch Text
        if old_vnode.text != new_vnode.text:
            msg = (
                f"{indent}{ANSI.YELLOW}* PATCH TEXT <{new_vnode.tag}>: "
                f"{repr(old_vnode.text)} -> {repr(new_vnode.text)}{ANSI.RESET}"
            )
            self.patch_log.append(msg)

        # 6. Reconcile Children (Keyed Diffing)
        self._diff_children(old_vnode.children, new_vnode.children, depth + 1)

    def _diff_children(
        self,
        old_children: List[VNode],
        new_children: List[VNode],
        depth: int
    ) -> None:
        old_map = {node.key: node for node in old_children if node.key}
        new_map = {node.key: node for node in new_children if node.key}

        # Check unmounted children
        for k, old_node in old_map.items():
            if k not in new_map:
                self.diff_and_patch(old_node, None, depth)

        # Check matched and new children
        for k, new_node in new_map.items():
            if k in old_map:
                self.diff_and_patch(old_map[k], new_node, depth)
            else:
                self.diff_and_patch(None, new_node, depth)


class VueRuntimeSimulator:
    """Complete Vue Runtime Lifecycle orchestrator."""
    def __init__(self, initial_state: Dict[str, Any]):
        self.state = ReactiveState(initial_state)
        self.compiler = TemplateCompiler()
        self.reconciler = DOMReconciler()
        self.current_vnode: Optional[VNode] = None

        # Wire automatic render on state mutation
        self.state.subscribe(self.update)

    def mount(self) -> None:
        print(f"\n{ANSI.BOLD}{ANSI.BG_BLUE} === [MOUNT LIFECYCLE HOOK] === {ANSI.RESET}")
        self.reconciler.patch_log.clear()
        vnode = self.compiler.render(self.state._data)
        self.reconciler.diff_and_patch(None, vnode)
        self.current_vnode = vnode
        self.print_patch_results()

    def update(self) -> None:
        print(f"\n{ANSI.BOLD}{ANSI.BG_MAGENTA} === [UPDATE LIFECYCLE HOOK (NEXT TICK)] === {ANSI.RESET}")
        self.reconciler.patch_log.clear()
        new_vnode = self.compiler.render(self.state._data)
        self.reconciler.diff_and_patch(self.current_vnode, new_vnode)
        self.current_vnode = new_vnode
        self.print_patch_results()

    def print_patch_results(self) -> None:
        print(f"{ANSI.CYAN}Operations executed on Real DOM (Simulated):{ANSI.RESET}")
        if not self.reconciler.patch_log:
            print(f"  {ANSI.DIM}[No DOM changes needed - Virtual DOM trees identical]{ANSI.RESET}")
        else:
            for log in self.reconciler.patch_log:
                print(log)

    def print_current_dom(self) -> None:
        print(f"\n{ANSI.BOLD}{ANSI.WHITE}--- Rendered Virtual DOM Output ---{ANSI.RESET}")
        def dump(node: Optional[VNode], level: int = 0):
            if not node:
                return
            indent = "  " * level
            text_part = f" text={repr(node.text)}" if node.text else ""
            key_part = f" key='{node.key}'" if node.key else ""
            props_part = f" props={node.props}" if node.props else ""
            print(f"{indent}<{ANSI.GREEN}{node.tag}{ANSI.RESET}{key_part}{props_part}>{text_part}")
            for c in node.children:
                dump(c, level + 1)
            print(f"{indent}</{ANSI.GREEN}{node.tag}{ANSI.RESET}>")

        dump(self.current_vnode)
        print(f"{ANSI.BOLD}{ANSI.WHITE}-----------------------------------{ANSI.RESET}\n")


def interactive_menu(app: VueRuntimeSimulator) -> None:
    while True:
        print(f"\n{ANSI.BOLD}{ANSI.CYAN}Interactive Controls (Vue Directives & DOM Manipulation):{ANSI.RESET}")
        print("  1. Toggle Authentication (v-if / v-else switch)")
        print("  2. Add New Task (v-for / v-bind key insert)")
        print("  3. Complete/Toggle Task #1 (v-bind :class / prop patch)")
        print("  4. Remove Last Task (v-for unmount)")
        print("  5. Update Counter (v-on:click / reactive state)")
        print("  6. Change Username (v-model emulation)")
        print("  7. Print Full DOM Tree")
        print("  0. Exit")

        try:
            choice = input(f"\n{ANSI.YELLOW}Select option [0-7]: {ANSI.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{ANSI.GREEN}Exiting cleanly.{ANSI.RESET}")
            break

        if choice == "1":
            curr = app.state.get("is_authenticated")
            app.state.set("is_authenticated", not curr)
        elif choice == "2":
            tasks = list(app.state.get("tasks"))
            new_id = len(tasks) + 1
            tasks.append({"id": new_id, "title": f"Production Deployment Phase #{new_id}", "completed": False})
            app.state.set("tasks", tasks)
        elif choice == "3":
            tasks = list(app.state.get("tasks"))
            if tasks:
                tasks[0] = {**tasks[0], "completed": not tasks[0]["completed"]}
                app.state.set("tasks", tasks)
            else:
                print(f"{ANSI.RED}No tasks available to toggle.{ANSI.RESET}")
        elif choice == "4":
            tasks = list(app.state.get("tasks"))
            if tasks:
                popped = tasks.pop()
                print(f"Removed task id {popped['id']}")
                app.state.set("tasks", tasks)
            else:
                print(f"{ANSI.RED}Task list already empty.{ANSI.RESET}")
        elif choice == "5":
            c = app.state.get("counter")
            app.state.set("counter", c + 1)
        elif choice == "6":
            name = input("Enter new user name: ").strip() or "Anonymous Engineer"
            app.state.set("user_name", name)
        elif choice == "7":
            app.print_current_dom()
        elif choice == "0":
            print(f"{ANSI.GREEN}Simulation finished.{ANSI.RESET}")
            break
        else:
            print(f"{ANSI.RED}Invalid option selected.{ANSI.RESET}")


def main() -> None:
    print(f"{ANSI.BOLD}{ANSI.CYAN}================================================================={ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN}   BAB-03: Vue Directives, Template Engine & DOM Reconciliation  {ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN}================================================================={ANSI.RESET}")

    initial_dataset = {
        "user_name": "Senior Frontend Architect",
        "role": "Tech Lead",
        "is_authenticated": True,
        "counter": 42,
        "tasks": [
            {"id": 1, "title": "Setup Custom Directives (v-focus, v-pin)", "completed": True},
            {"id": 2, "title": "Implement Compiler AST Generator", "completed": False},
            {"id": 3, "title": "Benchmark Keyed vs Unkeyed Children Diffing", "completed": False},
        ],
    }

    app = VueRuntimeSimulator(initial_dataset)
    app.mount()
    app.print_current_dom()

    # Non-interactive automated showcase if stdin is not a tty
    if not sys.stdin.isatty():
        print(f"\n{ANSI.YELLOW}[Automated Headless Mode Detected]{ANSI.RESET}")
        print("Demonstrating reactive update sequence...")
        time.sleep(0.1)
        app.state.set("is_authenticated", False)
        time.sleep(0.1)
        tasks = list(app.state.get("tasks"))
        tasks.append({"id": 4, "title": "Ship Vue 3.5 Vapor Mode Engine", "completed": True})
        app.state.set("tasks", tasks)
        app.print_current_dom()
        print(f"{ANSI.GREEN}Auto-run verification complete.{ANSI.RESET}")
    else:
        interactive_menu(app)


if __name__ == "__main__":
    main()
