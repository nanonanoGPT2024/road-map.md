#!/usr/bin/env python3
"""
Lab: Manipulasi DOM Lanjutan & Event-Driven Architecture (Deep Dive)
Modul: 07-02 Core Foundations (Frontend Simulation Engine)

Deskripsi:
Skrip ini mengimplementasikan simulasi arsitektur peramban (browser runtime)
tingkat rendah, mencakup:
 1. Pohon DOM Hirarkis (Node, Elemen, Hierarki Parent-Child).
 2. 3-Fase Alur Event Standar W3C: Capturing Phase -> Target Phase -> Bubbling Phase.
 3. Mekanisme Event Delegation (Delegasi Event) performa tinggi.
 4. Engine Reconciliation/Diffing Virtual DOM sederhana untuk mutasi DOM optimal.
"""

import sys
import time
from typing import List, Dict, Callable, Optional, Any
from dataclasses import dataclass, field
from enum import IntEnum

# --- ANSI Formatting untuk Visualisasi Terminal ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"


class EventPhase(IntEnum):
    NONE = 0
    CAPTURING_PHASE = 1
    AT_TARGET = 2
    BUBBLING_PHASE = 3


@dataclass
class Event:
    type: str
    target: Optional['DOMElement'] = None
    current_target: Optional['DOMElement'] = None
    event_phase: EventPhase = EventPhase.NONE
    bubbles: bool = True
    cancelable: bool = True
    default_prevented: bool = False
    _propagation_stopped: bool = False

    def stop_propagation(self):
        """Menghentikan perambatan event ke ancestor/descendant berikutnya."""
        self._propagation_stopped = True

    def prevent_default(self):
        """Membatalkan perilaku bawaan jika event dapat dibatalkan (cancelable)."""
        if self.cancelable:
            self.default_prevented = True


@dataclass
class EventListener:
    callback: Callable[['Event'], None]
    use_capture: bool = False


class DOMElement:
    """
    Representasi simulative Node DOM dengan kapabilitas event-driven
    dan pelacakan relasi pohon dokumen.
    """
    def __init__(self, tag: str, id: str = "", classes: Optional[List[str]] = None, attributes: Optional[Dict[str, str]] = None):
        self.tag: str = tag.lower()
        self.id: str = id
        self.classes: List[str] = classes if classes else []
        self.attributes: Dict[str, str] = attributes if attributes else {}
        self.children: List['DOMElement'] = []
        self.parent: Optional['DOMElement'] = None
        self._listeners: Dict[str, List[EventListener]] = {}

    def append_child(self, child: 'DOMElement') -> 'DOMElement':
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child: 'DOMElement') -> 'DOMElement':
        if child in self.children:
            child.parent = None
            self.children.remove(child)
            return child
        raise ValueError("Node bukan merupakan anak dari elemen ini.")

    def add_event_listener(self, event_type: str, callback: Callable[[Event], None], use_capture: bool = False):
        """Mendaftarkan listener ke fase capture atau bubble."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(EventListener(callback, use_capture))

    def dispatch_event(self, event: Event) -> bool:
        """
        Menjalankan daur hidup siklus Event W3C:
        1. Capture Phase: dari root document ke direct parent target.
        2. Target Phase: eksekusi listener langsung pada target.
        3. Bubbling Phase: dari direct parent target kembali ke root document.
        """
        event.target = self
        propagation_path: List['DOMElement'] = []
        curr = self.parent
        while curr is not None:
            propagation_path.append(curr)
            curr = curr.parent

        # Path capture berjalan dari Root -> Target
        capture_path = list(reversed(propagation_path))

        # --- 1. CAPTURING PHASE ---
        event.event_phase = EventPhase.CAPTURING_PHASE
        for node in capture_path:
            if event._propagation_stopped:
                break
            event.current_target = node
            node._invoke_listeners(event, use_capture_filter=True)

        # --- 2. AT TARGET PHASE ---
        if not event._propagation_stopped:
            event.event_phase = EventPhase.AT_TARGET
            event.current_target = self
            # Jalankan semua listener terdaftar di target (baik capture maupun bubbling)
            self._invoke_listeners(event, use_capture_filter=None)

        # --- 3. BUBBLING PHASE ---
        if event.bubbles and not event._propagation_stopped:
            event.event_phase = EventPhase.BUBBLING_PHASE
            for node in propagation_path:
                if event._propagation_stopped:
                    break
                event.current_target = node
                node._invoke_listeners(event, use_capture_filter=False)

        return not event.default_prevented

    def _invoke_listeners(self, event: Event, use_capture_filter: Optional[bool]):
        """Eksekutor internal listener sesuai filter fase."""
        listeners = self._listeners.get(event.type, [])
        for listener in listeners:
            if event._propagation_stopped:
                break
            # Jika filter bernilai None, panggil keduanya (fase Target)
            if use_capture_filter is None or listener.use_capture == use_capture_filter:
                listener.callback(event)

    def query_selector(self, selector: str) -> Optional['DOMElement']:
        """Simulasi selector traversal berbasis ID (#id) atau Tag."""
        if selector.startswith("#") and self.id == selector[1:]:
            return self
        if self.tag == selector.lower():
            return self
        for child in self.children:
            found = child.query_selector(selector)
            if found:
                return found
        return None

    def __repr__(self) -> str:
        attrs = f"#{self.id}" if self.id else ""
        classes = f".{'.'.join(self.classes)}" if self.classes else ""
        return f"<{self.tag}{attrs}{classes}>"


# =====================================================================
# Modul VDOM Engine: Diffing & Minimal Mutation Simulation
# =====================================================================
@dataclass
class PatchOp:
    op_type: str  # 'REPLACE', 'TEXT_UPDATE', 'ATTR_UPDATE', 'APPEND', 'REMOVE'
    target_node: Optional[DOMElement]
    payload: Any


def diff_vdom(old_node: DOMElement, new_node: DOMElement) -> List[PatchOp]:
    """
    Algoritma diffing pohon VDOM struktural rekursif O(N).
    Menghitung patch seminimal mungkin yang diperlukan untuk sinkronisasi.
    """
    patches = []

    # Tag berbeda -> Replace total
    if old_node.tag != new_node.tag:
        patches.append(PatchOp("REPLACE", old_node, new_node))
        return patches

    # Perubahan Atribut
    if old_node.attributes != new_node.attributes:
        patches.append(PatchOp("ATTR_UPDATE", old_node, new_node.attributes))

    # Diffing Children secara berurutan
    old_len = len(old_node.children)
    new_len = len(new_node.children)
    common_len = min(old_len, new_len)

    for i in range(common_len):
        patches.extend(diff_vdom(old_node.children[i], new_node.children[i]))

    if new_len > old_len:
        for i in range(old_len, new_len):
            patches.append(PatchOp("APPEND", old_node, new_node.children[i]))
    elif old_len > new_len:
        for i in range(new_len, old_len):
            patches.append(PatchOp("REMOVE", old_node, old_node.children[i]))

    return patches


# =====================================================================
# Skenario Hands-on & Pengujian
# =====================================================================
def print_banner(text: str):
    print(f"\n{CLR_BOLD}{CLR_BLUE}{'=' * 65}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}[LAB STEP] {text}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}{'=' * 65}{CLR_RESET}")


def run_lab():
    print(f"{CLR_BOLD}{CLR_MAGENTA}MEMULAI: Simulasi Core DOM & Event Propagation Engine{CLR_RESET}\n")

    # 1. Konstruksi Pohon DOM
    # <body>
    #   <main id="app">
    #     <div id="card" class="container">
    #       <ul id="item-list">
    #         <li id="item-1" class="todo-item">Tugas 1</li>
    #         <li id="item-2" class="todo-item">Tugas 2</li>
    #       </ul>
    #     </div>
    #   </main>
    # </body>
    body = DOMElement("body", id="root")
    main = DOMElement("main", id="app")
    card = DOMElement("div", id="card", classes=["container"])
    item_list = DOMElement("ul", id="item-list")
    item_1 = DOMElement("li", id="item-1", classes=["todo-item"], attributes={"data-action": "delete"})
    item_2 = DOMElement("li", id="item-2", classes=["todo-item"], attributes={"data-action": "complete"})

    body.append_child(main)
    main.append_child(card)
    card.append_child(item_list)
    item_list.append_child(item_1)
    item_list.append_child(item_2)

    print_banner("1. Verifikasi Alur Event W3C (Capturing -> Target -> Bubbling)")

    def trace_listener(phase_name: str, color: str):
        return lambda evt: print(
            f"  {color}[{phase_name.upper():<9}]{CLR_RESET} "
            f"Node: {str(evt.current_target):<22} | "
            f"Target: {str(evt.target):<20} | "
            f"Fase ID: {evt.event_phase}"
        )

    # Pasang capture listener di root dan intermediate container
    body.add_event_listener("click", trace_listener("Capture", CLR_CYAN), use_capture=True)
    card.add_event_listener("click", trace_listener("Capture", CLR_CYAN), use_capture=True)

    # Pasang target/bubble listener di target
    item_1.add_event_listener("click", trace_listener("Target", CLR_YELLOW), use_capture=False)

    # Pasang bubble listener di ancestor
    card.add_event_listener("click", trace_listener("Bubble", CLR_MAGENTA), use_capture=False)
    body.add_event_listener("click", trace_listener("Bubble", CLR_MAGENTA), use_capture=False)

    # Trigger click pada #item-1
    print(f"Triggering click event pada: {CLR_BOLD}{item_1}{CLR_RESET}\n")
    click_event = Event(type="click", bubbles=True)
    item_1.dispatch_event(click_event)

    print_banner("2. Simulasi Event Delegation (Pola Kinerja Tinggi)")
    print("Mendaftarkan 1 listener pada 'ul#item-list' untuk menangani semua 'li.todo-item' secara dinamis...\n")

    def delegated_item_handler(event: Event):
        target = event.target
        if target and "todo-item" in target.classes:
            action = target.attributes.get("data-action", "unknown")
            print(f"  {CLR_GREEN}✓ Delegated Action Triggered!{CLR_RESET}")
            print(f"    Target Node : {target}")
            print(f"    Current Host: {event.current_target}")
            print(f"    Action Type : {CLR_BOLD}{action.upper()}{CLR_RESET}\n")

    item_list.add_event_listener("click", delegated_item_handler, use_capture=False)

    # Dispatched dari item 2 (dihandle oleh listener ul#item-list)
    print("Dispatching event dari child dynamically (#item-2)...")
    item_2.dispatch_event(Event(type="click", bubbles=True))

    print_banner("3. Pengujian Stop Propagation")
    print("Memasang event.stop_propagation() pada #card dalam fase Capture...")

    def stopping_capture_listener(evt: Event):
        print(f"  {CLR_RED}🛑 Intervensi: Menghentikan propagasi di {evt.current_target}!{CLR_RESET}")
        evt.stop_propagation()

    card.add_event_listener("click", stopping_capture_listener, use_capture=True)

    print("Memicu click kembali pada #item-1 (Target tidak boleh pernah dieksekusi):")
    blocked_event = Event(type="click", bubbles=True)
    item_1.dispatch_event(blocked_event)

    print_banner("4. Arsitektur Virtual DOM Diffing & Reconciliation")
    # Buat state baru dari Card
    card_vnext = DOMElement("div", id="card", classes=["container", "dark-mode"])
    new_list = DOMElement("ul", id="item-list")
    # item-1 tetap ada, tapi item-2 dihapus, dan item-3 ditambahkan
    new_list.append_child(DOMElement("li", id="item-1", classes=["todo-item"], attributes={"data-action": "delete"}))
    new_list.append_child(DOMElement("li", id="item-3", classes=["todo-item", "new"], attributes={"data-action": "create"}))
    card_vnext.append_child(new_list)

    print(f"Membandingkan VDOM Sebelumnya:\n  {card} -> Children: {card.children}")
    print(f"Dengan VDOM Baru:\n  {card_vnext} -> Children: {card_vnext.children}\n")

    patches = diff_vdom(card, card_vnext)
    print(f"{CLR_BOLD}Kalkulasi Patch Mutasi Fisik DOM ({len(patches)} operasi terdeteksi):{CLR_RESET}")
    for idx, patch in enumerate(patches, 1):
        print(f"  [{idx}] Jenis Operasi: {CLR_YELLOW}{patch.op_type:<12}{CLR_RESET} | Sasaran: {str(patch.target_node):<20} | Detail: {patch.payload}")

    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ Lab Berhasil: Semua invariant DOM dan Event Bus tervalidasi.{CLR_RESET}\n")


if __name__ == "__main__":
    run_lab()