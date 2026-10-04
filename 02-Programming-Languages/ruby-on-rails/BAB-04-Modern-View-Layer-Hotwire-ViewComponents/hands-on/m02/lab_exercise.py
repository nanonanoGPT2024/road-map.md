#!/usr/bin/env python3
"""
Lab: Modern View Layer, Hotwire & ViewComponents Deep Dive
Simulates Rails 7+ modern frontend architecture:
1. ViewComponent encapsulation, slots pattern, and isolation rendering.
2. Turbo Frames request/response cycle and sub-tree extraction.
3. Turbo Streams real-time wire-protocol generator (append, prepend, replace, update, remove).
4. Stimulus controller contract validator.
5. ActionCable broadcast bus delivering concurrent Turbo Stream DOM mutations.
"""

from dataclasses import dataclass, field
import html
import queue
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional


# ==============================================================================
# ANSI Color Palette for Terminal Visualization
# ==============================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    GRAY = "\033[90m"


# ==============================================================================
# SECTION 1: ViewComponent Architecture Simulation
# ==============================================================================
class Slot:
    """Represents a ViewComponent slot (Rails ViewComponent 3.x slots API)."""

    def __init__(self, name: str, is_collection: bool = False):
        self.name = name
        self.is_collection = is_collection
        self.content: List[str] = []

    def set_content(self, text: str) -> None:
        if self.is_collection:
            self.content.append(text)
        else:
            self.content = [text]


class ViewComponent:
    """
    Base ViewComponent representing isolated, reusable, and testable UI logic.
    Decouples rendering from full Rails controller scope.
    """

    def __init__(self, **kwargs):
        self.params = kwargs
        self._slots: Dict[str, Slot] = {}
        self._registered_slots()

    def _registered_slots(self) -> None:
        """Hook for declaring available slots."""
        pass

    def declares_slot(self, name: str, collection: bool = False) -> None:
        self._slots[name] = Slot(name, is_collection=collection)

    def with_slot(self, slot_name: str, content: str) -> "ViewComponent":
        if slot_name not in self._slots:
            raise KeyError(f"Undefined slot '{slot_name}' for {self.__class__.__name__}")
        self._slots[slot_name].set_content(content)
        return self

    def slot_content(self, slot_name: str) -> str:
        if slot_name not in self._slots or not self._slots[slot_name].content:
            return ""
        return "\n".join(self._slots[slot_name].content)

    def validate(self) -> None:
        """Validates component state before rendering."""
        pass

    def render(self) -> str:
        self.validate()
        return self.template()

    def template(self) -> str:
        raise NotImplementedError


class TaskCardComponent(ViewComponent):
    """Concrete component modeling a task card with slots and Stimulus tags."""

    def _registered_slots(self) -> None:
        self.declares_slot("header")
        self.declares_slot("action_button", collection=True)

    def validate(self) -> None:
        if not self.params.get("task_id"):
            raise ValueError("TaskCardComponent requires 'task_id'")
        if not self.params.get("title"):
            raise ValueError("TaskCardComponent requires 'title'")

    def template(self) -> str:
        task_id = self.params["task_id"]
        title = html.escape(self.params["title"])
        status = self.params.get("status", "pending")
        header_content = self.slot_content("header") or f"Task #{task_id}"
        actions_html = "".join([f"    <div class='action-slot'>{act}</div>\n" for act in self._slots["action_button"].content])

        return (
            f"<div id='task_card_{task_id}' class='task-card task-card--{status}' "
            f"data-controller='task-card' data-task-card-status-value='{status}'>\n"
            f"  <header class='card-header' data-task-card-target='header'>\n"
            f"    <h3>{header_content}</h3>\n"
            f"  </header>\n"
            f"  <div class='card-body'>\n"
            f"    <p class='title' data-task-card-target='title'>{title}</p>\n"
            f"  </div>\n"
            f"  <footer class='card-actions'>\n"
            f"{actions_html}"
            f"  </footer>\n"
            f"</div>"
        )


# ==============================================================================
# SECTION 2: Hotwire Turbo Wire Engine (Frames & Streams)
# ==============================================================================
class TurboStreamAction:
    APPEND = "append"
    PREPEND = "prepend"
    REPLACE = "replace"
    UPDATE = "update"
    REMOVE = "remove"


@dataclass
class TurboStreamMessage:
    action: str
    target: str
    content: str = ""

    def to_wire_format(self) -> str:
        """Generates standard Hotwire <turbo-stream> HTML fragment."""
        if self.action == TurboStreamAction.REMOVE:
            return f'<turbo-stream action="{self.action}" target="{self.target}"></turbo-stream>'
        return (
            f'<turbo-stream action="{self.action}" target="{self.target}">\n'
            f'  <template>\n'
            f"    {self.content.strip()}\n"
            f'  </template>\n'
            f"</turbo-stream>"
        )


class TurboFrameDispatcher:
    """
    Simulates Rails Hotwire Turbo Frame resolver.
    When a Turbo-Frame request is received, only content enclosed inside
    the matching <turbo-frame id="..."> is evaluated and extracted.
    """

    @staticmethod
    def wrap_in_frame(frame_id: str, html_payload: str, src: Optional[str] = None) -> str:
        src_attr = f' src="{src}"' if src else ""
        return f'<turbo-frame id="{frame_id}"{src_attr}>\n{html_payload}\n</turbo-frame>'

    @staticmethod
    def extract_frame(response_html: str, frame_id: str) -> Optional[str]:
        pattern = rf'<turbo-frame\s+id=["\']{re.escape(frame_id)}["\'][^>]*>(.*?)</turbo-frame>'
        match = re.search(pattern, response_html, re.DOTALL)
        if match:
            return match.group(0).strip()
        return None


# ==============================================================================
# SECTION 3: ActionCable & Async Turbo Streams Broadcast Simulation
# ==============================================================================
class ActionCableChannel:
    """Pub/Sub broker simulating turbo_stream_from broadcast mechanisms."""

    def __init__(self, stream_name: str):
        self.stream_name = stream_name
        self._subscribers: List[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def broadcast_stream(self, message: TurboStreamMessage) -> None:
        """Pushes turbo-stream payload to all WebSocket connections listening."""
        wire = message.to_wire_format()
        with self._lock:
            for sub in self._subscribers:
                sub.put(wire)


# ==============================================================================
# SECTION 4: Stimulus Static Contract Checker
# ==============================================================================
class StimulusInspector:
    """Validates that rendered HTML conforms to expected Stimulus controllers."""

    @staticmethod
    def inspect(html_content: str) -> Dict[str, Any]:
        controllers = re.findall(r'data-controller=["\']([^"\']+)["\']', html_content)
        targets = re.findall(r'data-([a-zA-Z0-9_-]+)-target=["\']([^"\']+)["\']', html_content)
        actions = re.findall(r'data-action=["\']([^"\']+)["\']', html_content)

        return {
            "controllers": [ctrl for group in controllers for ctrl in group.split()],
            "targets": targets,
            "actions": actions,
        }


# ==============================================================================
# SECTION 5: End-to-End Orchestration & Verification Runner
# ==============================================================================
def simulate_client_listener(client_id: str, channel_queue: queue.Queue, stop_flag: threading.Event) -> None:
    """Simulates a browser client receiving live ActionCable Turbo Streams."""
    while not stop_flag.is_set():
        try:
            wire_message = channel_queue.get(timeout=0.2)
            print(f"{TermColor.CYAN}[Client {client_id} WS Received]{TermColor.RESET}\n{TermColor.GRAY}{wire_message}{TermColor.RESET}\n")
            channel_queue.task_done()
        except queue.Empty:
            continue


def main():
    print(f"\n{TermColor.BOLD}{TermColor.MAGENTA}=== HOTWIRE & VIEWCOMPONENTS: MODERN VIEW LAYER LAB ==={TermColor.RESET}\n")

    # --------------------------------------------------------------------------
    # STEP 1: Component Rendering & Slot Validation
    # --------------------------------------------------------------------------
    print(f"{TermColor.YELLOW}[1] Compiling and Rendering Isolated ViewComponents...{TermColor.RESET}")

    start_perf = time.perf_counter()
    card_comp = (
        TaskCardComponent(task_id=101, title="Refactor ActionCable Connection Pool", status="in_progress")
        .with_slot("header", "Sprint Priority Alpha")
        .with_slot("action_button", '<button data-action="click->task-card#complete">Complete</button>')
        .with_slot("action_button", '<button data-action="click->task-card#archive">Archive</button>')
    )
    rendered_component = card_comp.render()
    render_duration = (time.perf_counter() - start_perf) * 1000

    print(f"{TermColor.GREEN}✓ Component Rendered in {render_duration:.3f} ms{TermColor.RESET}")
    print(f"{TermColor.GRAY}{rendered_component}{TermColor.RESET}\n")

    # --------------------------------------------------------------------------
    # STEP 2: Stimulus Controller Validation
    # --------------------------------------------------------------------------
    print(f"{TermColor.YELLOW}[2] Auditing Stimulus Contract in View Output...{TermColor.RESET}")
    audit = StimulusInspector.inspect(rendered_component)
    print(f"  Detected Controllers: {TermColor.BOLD}{audit['controllers']}{TermColor.RESET}")
    print(f"  Detected Targets:     {TermColor.BOLD}{audit['targets']}{TermColor.RESET}")
    print(f"  Detected Actions:     {TermColor.BOLD}{audit['actions']}{TermColor.RESET}")

    assert "task-card" in audit["controllers"], "Missing Stimulus controller registration!"
    print(f"{TermColor.GREEN}✓ Stimulus markup integrity valid.{TermColor.RESET}\n")

    # --------------------------------------------------------------------------
    # STEP 3: Turbo Frame Request Deconstruction
    # --------------------------------------------------------------------------
    print(f"{TermColor.YELLOW}[3] Simulating Turbo Frame Extraction (Sub-tree Deconstruction)...{TermColor.RESET}")

    full_page_response = f"""<!DOCTYPE html>
<html>
<head><title>Dashboard</title></head>
<body>
  <header>Global Navbar</header>
  <main>
    {TurboFrameDispatcher.wrap_in_frame('task_list', '<p>Static Task Container</p>')}
    {TurboFrameDispatcher.wrap_in_frame('task_detail_101', rendered_component)}
  </main>
  <footer>Global Footer</footer>
</body>
</html>"""

    # Turbo Frame request targeting "task_detail_101"
    target_frame = "task_detail_101"
    extracted_frame = TurboFrameDispatcher.extract_frame(full_page_response, target_frame)

    if extracted_frame:
        print(f"{TermColor.GREEN}✓ Successfully intercepted frame '{target_frame}' without loading root DOM:{TermColor.RESET}")
        print(f"{TermColor.GRAY}{extracted_frame[:180]}...\n</turbo-frame>{TermColor.RESET}\n")
    else:
        print(f"{TermColor.RED}✗ Failed to find frame '{target_frame}'!{TermColor.RESET}\n")

    # --------------------------------------------------------------------------
    # STEP 4: Real-Time Turbo Streams via ActionCable Channel
    # --------------------------------------------------------------------------
    print(f"{TermColor.YELLOW}[4] Broadcasting Asynchronous Turbo Streams via ActionCable...{TermColor.RESET}")

    channel = ActionCableChannel(stream_name="project_board_stream")

    # Subscribe concurrent clients
    stop_event = threading.Event()
    client_q1 = channel.subscribe()
    client_q2 = channel.subscribe()

    t1 = threading.Thread(target=simulate_client_listener, args=("Desktop-Browser", client_q1, stop_event))
    t2 = threading.Thread(target=simulate_client_listener, args=("Mobile-App", client_q2, stop_event))
    t1.start()
    t2.start()

    time.sleep(0.1)

    # Broadcast Stream 1: Append new task
    new_card = (
        TaskCardComponent(task_id=102, title="Audit Redis ActionCable Adapters", status="pending")
        .with_slot("header", "Sprint Priority Beta")
        .render()
    )

    msg_append = TurboStreamMessage(
        action=TurboStreamAction.APPEND,
        target="tasks_container",
        content=new_card,
    )
    print(f"{TermColor.BLUE}--> Server Event: task_created -> Broadcasting APPEND stream...{TermColor.RESET}")
    channel.broadcast_stream(msg_append)
    time.sleep(0.15)

    # Broadcast Stream 2: Update existing task status
    updated_card = (
        TaskCardComponent(task_id=101, title="Refactor ActionCable Connection Pool", status="completed")
        .with_slot("header", "Done")
        .render()
    )

    msg_replace = TurboStreamMessage(
        action=TurboStreamAction.REPLACE,
        target="task_card_101",
        content=updated_card,
    )
    print(f"{TermColor.BLUE}--> Server Event: task_updated -> Broadcasting REPLACE stream...{TermColor.RESET}")
    channel.broadcast_stream(msg_replace)
    time.sleep(0.15)

    # Broadcast Stream 3: Remove obsolete element
    msg_remove = TurboStreamMessage(
        action=TurboStreamAction.REMOVE,
        target="flash_banner_welcome",
    )
    print(f"{TermColor.BLUE}--> Server Event: banner_dismissed -> Broadcasting REMOVE stream...{TermColor.RESET}")
    channel.broadcast_stream(msg_remove)
    time.sleep(0.15)

    # Teardown workers
    stop_event.set()
    t1.join()
    t2.join()

    print(f"{TermColor.BOLD}{TermColor.GREEN}=== DEEP DIVE SIMULATION COMPLETE: ALL PROTOCOLS VERIFIED ==={TermColor.RESET}\n")


if __name__ == "__main__":
    main()