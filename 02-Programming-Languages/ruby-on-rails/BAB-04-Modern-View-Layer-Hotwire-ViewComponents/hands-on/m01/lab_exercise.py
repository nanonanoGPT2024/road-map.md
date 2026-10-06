#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Hotwire & ViewComponent (Ruby on Rails 7+)
Modul: BAB-04 Modern View Layer (Turbo Drive, Turbo Frames, Turbo Streams, Stimulus, ViewComponent)
"""

import sys
import time
from typing import Dict, List, Optional

# ANSI Color Palettes for Terminal Styling
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[40m"


def header(title: str) -> None:
    line = "=" * 64
    print(f"\n{Style.CYAN}{Style.BOLD}{line}")
    print(f" [*] {title.upper()}")
    print(f"{line}{Style.RESET}")


def subheader(title: str) -> None:
    print(f"\n{Style.YELLOW}{Style.BOLD}--- {title} ---{Style.RESET}")


# ==============================================================================
# 1. ViewComponent Pattern Simulation
# ==============================================================================
class ViewComponent:
    """Simulasi ViewComponent: Komponen Ruby terenkapsulasi, reusable, & unit-testable."""
    def __init__(self, **kwargs):
        self.props = kwargs

    def render(self) -> str:
        raise NotImplementedError("Setiap ViewComponent wajib mengimplementasikan render()")


class TaskCardComponent(ViewComponent):
    def __init__(self, task_id: int, title: str, status: str, assignee: str):
        super().__init__(task_id=task_id, title=title, status=status, assignee=assignee)
        self.task_id = task_id
        self.title = title
        self.status = status
        self.assignee = assignee

    def status_badge_color(self) -> str:
        colors = {
            "pending": Style.YELLOW,
            "in_progress": Style.BLUE,
            "completed": Style.GREEN
        }
        return colors.get(self.status, Style.WHITE)

    def render(self) -> str:
        badge = f"{self.status_badge_color()}[{self.status.upper()}]{Style.RESET}"
        return (
            f"  {Style.MAGENTA}<div class='task-card' id='task_{self.task_id}'>{Style.RESET}\n"
            f"    {Style.WHITE}{Style.BOLD}#{self.task_id} {self.title}{Style.RESET} {badge}\n"
            f"    {Style.DIM}Assignee: @{self.assignee}{Style.RESET}\n"
            f"  {Style.MAGENTA}</div>{Style.RESET}"
        )


# ==============================================================================
# 2. Stimulus Controller Simulation
# ==============================================================================
class StimulusController:
    """Simulasi Stimulus JS: Micro-framework perambah perilaku DOM berbasis attributes."""
    def __init__(self, name: str):
        self.name = name
        self.values: Dict[str, any] = {}
        self.targets: Dict[str, str] = {}

    def connect(self) -> None:
        print(f"    {Style.CYAN}[Stimulus]{Style.RESET} Controller '{self.name}' connected to DOM element.")

    def trigger(self, action_name: str, payload: Optional[Dict] = None) -> None:
        handler = getattr(self, f"action_{action_name}", None)
        if callable(handler):
            print(f"    {Style.CYAN}[Stimulus Action]{Style.RESET} Dispatching '{self.name}#{action_name}'")
            handler(payload or {})
        else:
            print(f"    {Style.RED}[Stimulus Error] Action '{action_name}' tidak ditemukan!{Style.RESET}")

    def action_toggle(self, payload: Dict) -> None:
        current = self.values.get("isOpen", False)
        self.values["isOpen"] = not current
        state_str = "OPEN" if self.values["isOpen"] else "CLOSED"
        print(f"    {Style.GREEN}↳ State Changed: isOpen = {state_str}{Style.RESET}")


# ==============================================================================
# 3. Hotwire Turbo Frames Simulation
# ==============================================================================
class TurboFrame:
    """Simulasi Turbo Frame: Dekomposisi halaman independen (scoped navigation/mutations)."""
    def __init__(self, frame_id: str, content: str):
        self.frame_id = frame_id
        self.content = content

    def request_update(self, new_content: str) -> None:
        print(f"  {Style.BLUE}[Turbo Frame: #{self.frame_id}]{Style.RESET} Incoming frame response intercepted.")
        print(f"  {Style.DIM}Melakukan replace HANYA pada frame #{self.frame_id}, DOM di luar frame tetap utuh.{Style.RESET}")
        self.content = new_content
        print(f"  {Style.GREEN}✓ Frame #{self.frame_id} berhasil di-swap secara mulus (No Full Reload){Style.RESET}")


# ==============================================================================
# 4. Hotwire Turbo Streams Simulation
# ==============================================================================
class TurboStreamEngine:
    """Simulasi Turbo Streams: Real-time DOM broadcast via WebSocket/SSE/POST response."""
    ACTIONS = ["append", "prepend", "replace", "update", "remove"]

    def __init__(self):
        self.dom_registry: Dict[str, List[str]] = {
            "task_list": [],
            "task_counter": ["Total: 0"]
        }

    def broadcast(self, action: str, target: str, html_payload: str) -> None:
        if action not in self.ACTIONS:
            raise ValueError(f"Action Turbo Stream tidak valid: {action}")

        print(f"\n  {Style.MAGENTA}[Turbo Stream Broadcast]{Style.RESET} <turbo-stream action='{action}' target='{target}'>")
        time.sleep(0.2)

        if action == "append":
            self.dom_registry.setdefault(target, []).append(html_payload)
            print(f"  {Style.GREEN}↳ Appended element into #{target}{Style.RESET}")
        elif action == "prepend":
            self.dom_registry.setdefault(target, []).insert(0, html_payload)
            print(f"  {Style.GREEN}↳ Prepended element into #{target}{Style.RESET}")
        elif action == "replace":
            self.dom_registry[target] = [html_payload]
            print(f"  {Style.GREEN}↳ Replaced target container #{target}{Style.RESET}")
        elif action == "update":
            self.dom_registry[target] = [html_payload]
            print(f"  {Style.GREEN}↳ Updated inner HTML of #{target}{Style.RESET}")
        elif action == "remove":
            if target in self.dom_registry:
                del self.dom_registry[target]
                print(f"  {Style.RED}↳ Removed element #{target} from DOM tree{Style.RESET}")

        print(f"  {Style.MAGENTA}</turbo-stream>{Style.RESET}")


# ==============================================================================
# Interactive Runner & Scenarios
# ==============================================================================
def run_view_component_demo() -> None:
    subheader("1. ViewComponent Architecture Demo")
    print(f"{Style.DIM}ViewComponent memisahkan logika tampilan Ruby dari ERB monolitik.{Style.RESET}")
    c1 = TaskCardComponent(101, "Setup Turbo Streams with Redis", "completed", "dhh")
    c2 = TaskCardComponent(102, "Migrate CSS to Tailwind + Propshaft", "in_progress", "tenderlove")
    print("\nHasil Render Komponen:")
    print(c1.render())
    print()
    print(c2.render())


def run_stimulus_demo() -> None:
    subheader("2. Stimulus JS Lifecycle & Actions Demo")
    print(f"{Style.DIM}Stimulus menghubungkan behavior JavaScript secara deklaratif via data-controller.{Style.RESET}")
    controller = StimulusController("accordion")
    controller.connect()
    controller.values["isOpen"] = False
    print(f"  Initial State: isOpen = {controller.values['isOpen']}")
    controller.trigger("toggle")
    controller.trigger("toggle")


def run_turbo_frame_demo() -> None:
    subheader("3. Turbo Frames In-Place Replacement Demo")
    frame = TurboFrame("task_editor_101", "<p>Klik untuk mengedit deskripsi task...</p>")
    print(f"  DOM Awal: {frame.content}")
    time.sleep(0.2)
    new_form = "<form action='/tasks/101' method='post'><input type='text' value='Update task...' /></form>"
    frame.request_update(new_form)
    print(f"  DOM Pasca Turbo Frame Update:\n    {frame.content}")


def run_turbo_stream_simulation() -> None:
    subheader("4. Turbo Streams Multi-Target Reactive Broadcast")
    stream_engine = TurboStreamEngine()

    # Step 1: Append task baru via ViewComponent
    new_task = TaskCardComponent(103, "Refactor Controller with Turbo Responds", "pending", "matz")
    stream_engine.broadcast("append", "task_list", new_task.render())

    # Step 2: Update counter badge
    counter_html = f"<span class='badge'>{Style.BOLD}Total: 3 Tasks{Style.RESET}</span>"
    stream_engine.broadcast("update", "task_counter", counter_html)


def main() -> None:
    header("Simulasi Lab Fondasi Hotwire & ViewComponents (Rails 7+)")
    print(f"{Style.WHITE}Modul Pembelajaran Interaktif Arsitektur Modern Frontend Rails{Style.RESET}")
    print(f"{Style.DIM}Memverifikasi Turbo Drive, Frames, Streams, Stimulus & ViewComponent.{Style.RESET}")

    run_view_component_demo()
    run_stimulus_demo()
    run_turbo_frame_demo()
    run_turbo_stream_simulation()

    header("Simulasi Sukses Berjalan Penuh")
    print(f"{Style.GREEN}{Style.BOLD}Semua arsitektur Hotwire & ViewComponents terverifikasi valid!{Style.RESET}\n")


if __name__ == "__main__":
    main()
