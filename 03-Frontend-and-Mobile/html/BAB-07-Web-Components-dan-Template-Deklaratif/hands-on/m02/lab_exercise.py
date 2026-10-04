#!/usr/bin/env python3
"""
Lab Hands-on: Web Components & Template Deklaratif (Deep Dive)
Bab: 07 - Modul 02

Simulasi komprehensif arsitektur Web Components tingkat browser:
1. Declarative Shadow DOM (DSD) & <template> cloning engine.
2. CustomElementRegistry dengan Lifecycle Callbacks:
   - connectedCallback, disconnectedCallback, attributeChangedCallback.
3. Shadow DOM Encapsulation: Mode 'open' vs 'closed', Scoped Style tokenization.
4. Slot Distribution/Projection Algorithm: Light DOM -> Named & Default Slots.
5. Event Retargeting Engine: Penanganan batas kapsulasi (shadow boundary) 
   dan composedPath() normalization.
"""

from collections import defaultdict
import html
import json
import sys
import time

# --- ANSI Formatting Constants ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[48;5;236m"


# ============================================================================
# Core Mini-DOM Engine
# ============================================================================

class Node:
    """Dasar dari semua node dalam representasi DOM virtual."""
    def __init__(self):
        self.parent_node = None
        self.children = []

    def append_child(self, child):
        child.parent_node = self
        self.children.append(child)
        if isinstance(self, Element) and self.is_connected:
            child._set_connected(True)
        return child

    def remove_child(self, child):
        if child in self.children:
            self.children.remove(child)
            child.parent_node = None
            if isinstance(self, Element) and self.is_connected:
                child._set_connected(False)
            return child
        raise ValueError("Node tidak ditemukan dalam hierarki anak.")

    @property
    def is_connected(self):
        curr = self
        while curr.parent_node:
            curr = curr.parent_node
        return isinstance(curr, Document)

    def _set_connected(self, status: bool):
        for c in self.children:
            c._set_connected(status)


class TextNode(Node):
    """Representasi text node pada DOM."""
    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def __repr__(self):
        return f"#text('{self.text.strip()}')"


class Document(Node):
    """Root dokumen simulasi."""
    def __init__(self):
        super().__init__()


class DocumentFragment(Node):
    """Kontainer ringan untuk operasi template cloning tanpa overhead reflow."""
    def clone_node(self, deep: bool = True):
        frag = DocumentFragment()
        for child in self.children:
            frag.append_child(child.clone_node(deep) if isinstance(child, (Element, DocumentFragment)) else TextNode(child.text))
        return frag


class ShadowRoot(DocumentFragment):
    """Representasi Shadow Root yang membatasi encapsulation boundary."""
    def __init__(self, host: 'Element', mode: str = 'open'):
        super().__init__()
        self.host = host
        self.mode = mode  # 'open' atau 'closed'

    def __repr__(self):
        return f"#shadow-root ({self.mode})"


class Element(Node):
    """Representasi HTML Element generik."""
    def __init__(self, tag_name: str, attributes: dict = None):
        super().__init__()
        self.tag_name = tag_name.lower()
        self.attributes = attributes or {}
        self.shadow_root = None
        self._listeners = defaultdict(list)

    def set_attribute(self, name: str, value: str):
        old_val = self.attributes.get(name)
        self.attributes[name] = str(value)
        if hasattr(self, 'attribute_changed_callback') and name in getattr(self, 'observed_attributes', []):
            if old_val != value:
                self.attribute_changed_callback(name, old_val, str(value))

    def get_attribute(self, name: str):
        return self.attributes.get(name)

    def attach_shadow(self, init: dict) -> ShadowRoot:
        if self.shadow_root is not None:
            raise RuntimeError(f"ShadowRoot sudah terpasang pada <{self.tag_name}>.")
        mode = init.get("mode", "open")
        self.shadow_root = ShadowRoot(host=self, mode=mode)
        return self.shadow_root

    def add_event_listener(self, event_type: str, callback):
        self._listeners[event_type].append(callback)

    def dispatch_event(self, event: 'Event') -> bool:
        """Memproses propagasi event (Capturing/Bubbling) dengan Retargeting."""
        return EventDispatcher.dispatch(self, event)

    def clone_node(self, deep: bool = True):
        new_el = Element(self.tag_name, self.attributes.copy())
        if deep:
            for child in self.children:
                if isinstance(child, Element):
                    new_el.append_child(child.clone_node(True))
                elif isinstance(child, TextNode):
                    new_el.append_child(TextNode(child.text))
        return new_el

    def _set_connected(self, status: bool):
        was_connected = self.is_connected
        super()._set_connected(status)
        if not was_connected and status:
            if hasattr(self, 'connected_callback'):
                self.connected_callback()
        elif was_connected and not status:
            if hasattr(self, 'disconnected_callback'):
                self.disconnected_callback()

    def __repr__(self):
        attrs = " ".join(f'{k}="{v}"' for k, v in self.attributes.items())
        return f"<{self.tag_name}{' ' + attrs if attrs else ''}>"


class HTMLTemplateElement(Element):
    """Simulasi elemen <template> dengan inert content fragment."""
    def __init__(self, attributes: dict = None):
        super().__init__('template', attributes)
        self.content = DocumentFragment()


class HTMLSlotElement(Element):
    """Simulasi elemen <slot> untuk komposisi Shadow DOM."""
    def __init__(self, attributes: dict = None):
        super().__init__('slot', attributes)

    @property
    def name(self):
        return self.attributes.get('name', '')

    def assigned_nodes(self, host: Element):
        """Menghitung node Light DOM yang terproyeksi ke slot ini."""
        assigned = []
        slot_name = self.name
        for child in host.children:
            child_slot = child.get_attribute('slot') if isinstance(child, Element) else None
            if slot_name == "":
                if child_slot is None:
                    assigned.append(child)
            else:
                if child_slot == slot_name:
                    assigned.append(child)
        return assigned


# ============================================================================
# Web Components Engine: CustomElementRegistry
# ============================================================================

class CustomElementRegistry:
    """Implementasi window.customElements registry."""
    def __init__(self):
        self._registry = {}

    def define(self, name: str, constructor_cls):
        name = name.lower()
        if "-" not in name:
            raise ValueError(f"Custom Element name '{name}' harus memiliki hyphen '-' (valid custom element name).")
        if name in self._registry:
            raise ValueError(f"Tag '{name}' sudah didefinisikan.")
        self._registry[name] = constructor_cls

    def get(self, name: str):
        return self._registry.get(name.lower())

    def create_element(self, tag_name: str, attributes: dict = None) -> Element:
        cls = self.get(tag_name)
        if cls:
            instance = cls(attributes)
        else:
            if tag_name.lower() == 'template':
                instance = HTMLTemplateElement(attributes)
            elif tag_name.lower() == 'slot':
                instance = HTMLSlotElement(attributes)
            else:
                instance = Element(tag_name, attributes)
        return instance

custom_elements = CustomElementRegistry()


# ============================================================================
# Event & Retargeting Engine
# ============================================================================

class Event:
    """Model DOM Event standar dengan dukungan boundary traversal."""
    def __init__(self, event_type: str, bubbles: bool = True, composed: bool = True):
        self.type = event_type
        self.bubbles = bubbles
        self.composed = composed
        self.target = None
        self.current_target = None
        self._stopped = False

    def stop_propagation(self):
        self._stopped = True


class EventDispatcher:
    """
    Mengimplementasikan Event Retargeting sesuai spesifikasi W3C DOM.
    Ketika event melewati batas Shadow DOM, 'target' dikembalikan ke Shadow Host
    jika dilihat dari luar boundary pohon komponen.
    """
    @staticmethod
    def calculate_path(start_node: Node) -> list:
        path = []
        curr = start_node
        while curr:
            path.append(curr)
            if isinstance(curr, ShadowRoot):
                curr = curr.host
            else:
                curr = curr.parent_node
        return path

    @staticmethod
    def retarget(target_node: Node, receiver_node: Node) -> Node:
        """Menghitung retargeted event target dari sudut pandang receiver_node."""
        curr = target_node
        target_ancestors = EventDispatcher.calculate_path(target_node)
        receiver_ancestors = EventDispatcher.calculate_path(receiver_node)
        
        # Cari common ancestor terendah
        common = None
        for a in target_ancestors:
            if a in receiver_ancestors:
                common = a
                break

        # Tentukan representasi target dari perspektif receiver
        for node in target_ancestors:
            if node == common:
                return node
            if isinstance(node.parent_node, ShadowRoot) and node.parent_node.mode == "closed":
                return node.parent_node.host
        return target_node

    @classmethod
    def dispatch(cls, target: Element, event: Event) -> bool:
        event.target = target
        path = cls.calculate_path(target)

        # Bubble phase dengan dynamic retargeting
        for current_node in path:
            if event._stopped:
                break
            
            # Jika event non-composed dan mencoba keluar dari shadow root
            if not event.composed and isinstance(current_node, ShadowRoot):
                break

            adjusted_target = cls.retarget(event.target, current_node)
            event.current_target = current_node

            if isinstance(current_node, Element) and event.type in current_node._listeners:
                for cb in current_node._listeners[event.type]:
                    # Override target property saat execution context berganti
                    cb(event, adjusted_target)

            if not event.bubbles and current_node == target:
                break

        return not event._stopped


# ============================================================================
# Declarative Shadow DOM (DSD) Parser & Renderer
# ============================================================================

class DeclarativeShadowDOMParser:
    """
    Menganalisis dan menyusun pohon DOM yang mencakup sintaks DSD:
    <template shadowrootmode="open|closed">
    """
    @staticmethod
    def parse_mock_declarative(template_str: str, host_element: Element):
        """Simulasi parser DSD: membaca template string dan mengaitkan shadow root."""
        # Ekstrak mode
        mode = "open"
        if 'shadowrootmode="closed"' in template_str:
            mode = "closed"
        
        shadow = host_element.attach_shadow({"mode": mode})
        
        # Parsing minimalis tokenisasi HTML ke dalam Shadow DOM
        lines = [line.strip() for line in template_str.strip().split("\n") if line.strip()]
        for line in lines:
            if line.startswith("<style>"):
                # Shadow scoped styles
                css_body = line.replace("<style>", "").replace("</style>", "")
                style_el = custom_elements.create_element("style")
                style_el.append_child(TextNode(css_body))
                shadow.append_child(style_el)
            elif line.startswith("<slot"):
                # Menangani slot deklaratif
                attrs = {}
                if 'name="' in line:
                    start = line.find('name="') + 6
                    end = line.find('"', start)
                    attrs['name'] = line[start:end]
                slot_el = custom_elements.create_element("slot", attrs)
                shadow.append_child(slot_el)
            elif line.startswith("<button"):
                btn = custom_elements.create_element("button")
                inner = line[line.find(">") + 1: line.rfind("<")]
                btn.append_child(TextNode(inner))
                shadow.append_child(btn)
            elif line.startswith("<div") or line.startswith("<span"):
                tag = line[1:line.find(" ")] if " " in line else line[1:line.find(">")]
                el = custom_elements.create_element(tag)
                inner = line[line.find(">") + 1: line.rfind("<")]
                if inner:
                    el.append_child(TextNode(inner))
                shadow.append_child(el)
        return shadow


# ============================================================================
# Komponen Nyata: <user-profile-badge>
# ============================================================================

class UserProfileBadge(Element):
    """
    Komponen Kustom Tingkat Tinggi:
    Memadukan observed attributes, template encapsulation, dan slot distribution.
    """
    observed_attributes = ["status", "role"]

    def __init__(self, attributes: dict = None):
        super().__init__("user-profile-badge", attributes)
        self.render_count = 0

    def connected_callback(self):
        print(f"{CLR_GREEN}  [Lifecycle] <user-profile-badge> tersambung ke DOM!{CLR_RESET}")
        self._init_shadow()

    def disconnected_callback(self):
        print(f"{CLR_RED}  [Lifecycle] <user-profile-badge> dicabut dari DOM!{CLR_RESET}")

    def attribute_changed_callback(self, name: str, old_val: str, new_val: str):
        print(f"{CLR_MAGENTA}  [Lifecycle] AttributeChanged: '{name}' berubah dari '{old_val}' -> '{new_val}'{CLR_RESET}")
        self._update_internal_state()

    def _init_shadow(self):
        # Jika belum di-attach oleh Declarative Shadow DOM
        if not self.shadow_root:
            dsd_template = """
                <style>:host { display: block; border: 1px solid #444; padding: 12px; } .status { font-weight: bold; }</style>
                <div class="header">
                    <slot name="avatar"></slot>
                    <slot name="username"></slot>
                </div>
                <div class="content">
                    <slot></slot>
                </div>
                <button id="action-btn">Ping Host</button>
            """
            DeclarativeShadowDOMParser.parse_mock_declarative(dsd_template, self)
            
            # Setup internal listener untuk uji retargeting
            btn = self._find_in_shadow("button")
            if btn:
                btn.add_event_listener("component-ping", lambda ev, target: 
                    print(f"    {CLR_CYAN}-> [Internal Shadow Listener] Tangkap event dari Target: {target}{CLR_RESET}")
                )

    def _find_in_shadow(self, tag_name: str):
        if not self.shadow_root:
            return None
        for child in self.shadow_root.children:
            if isinstance(child, Element) and child.tag_name == tag_name:
                return child
        return None

    def _update_internal_state(self):
        # Mutasi visual internal berdasarkan attribute
        pass


# Register komponen
custom_elements.define("user-profile-badge", UserProfileBadge)


# ============================================================================
# Composed Tree Inspector (Visualizer)
# ============================================================================

def print_composed_tree(root: Node, indent: int = 0):
    """
    Melakukan flattening pohon visual (Composed Tree) yang sesungguhnya 
    ditampilkan browser setelah resolusi Slot Projection.
    """
    prefix = "  " * indent
    if isinstance(root, TextNode):
        val = root.text.strip()
        if val:
            print(f"{prefix}{CLR_YELLOW}\"{val}\"{CLR_RESET}")
        return

    if isinstance(root, Element):
        is_custom = "-" in root.tag_name
        tag_color = CLR_GREEN if is_custom else CLR_BLUE
        print(f"{prefix}{tag_color}<{root.tag_name}>{CLR_RESET}")

        # Jika memiliki shadow root, yang dirender adalah shadow root
        if root.shadow_root:
            s_mode = root.shadow_root.mode
            print(f"{prefix}  {CLR_CYAN}#shadow-root ({s_mode}){CLR_RESET}")
            for s_child in root.shadow_root.children:
                if isinstance(s_child, HTMLSlotElement):
                    slot_name = s_child.name
                    label = f'name="{slot_name}"' if slot_name else "(default)"
                    print(f"{prefix}    {CLR_MAGENTA}⇄ slot {label} [Assigned Nodes]:{CLR_RESET}")
                    assigned = s_child.assigned_nodes(root)
                    for assigned_node in assigned:
                        print_composed_tree(assigned_node, indent + 3)
                else:
                    print_composed_tree(s_child, indent + 2)
        else:
            for child in root.children:
                print_composed_tree(child, indent + 1)


# ============================================================================
# Main Execution Simulation
# ============================================================================

def main():
    print(f"\n{CLR_BOLD}{CLR_BG_DARK}=== LAB: WEB COMPONENTS & DECLARATIVE TEMPLATE ENGINE ==={CLR_RESET}\n")

    # 1. Bangun Light Document
    doc = Document()
    app_root = custom_elements.create_element("div", {"id": "app"})
    doc.append_child(app_root)

    print(f"{CLR_BOLD}1. Declarative Instantiation & Custom Element Mounting{CLR_RESET}")
    # Buat Custom Element
    badge = custom_elements.create_element("user-profile-badge", {
        "status": "online",
        "role": "engineer"
    })
    
    # Isi Light DOM (Anak yang nantinya terdistribusi via Slotting)
    avatar = custom_elements.create_element("img", {"slot": "avatar", "src": "avatar.png"})
    username = custom_elements.create_element("h3", {"slot": "username"})
    username.append_child(TextNode("Arya Stanza"))
    bio = custom_elements.create_element("p")
    bio.append_child(TextNode("Lead Systems Programmer yang fokus pada performa Web Runtime."))

    badge.append_child(avatar)
    badge.append_child(username)
    badge.append_child(bio)

    # Trigger connectedCallback saat disambungkan ke DOM aktif
    app_root.append_child(badge)

    # 2. Reaktivitas Atribut
    print(f"\n{CLR_BOLD}2. Menguji Reaktivitas Attribute Callback{CLR_RESET}")
    badge.set_attribute("status", "busy")
    badge.set_attribute("role", "architect")

    # 3. Composed Tree Flattening Simulation
    print(f"\n{CLR_BOLD}3. Rendering Resolusi Composed Tree (Slot Projection){CLR_RESET}")
    print(f"Hierarki gabungan Light DOM x Shadow DOM:")
    print_composed_tree(app_root)

    # 4. Event Retargeting & Encapsulation Boundary
    print(f"\n{CLR_BOLD}4. Event Retargeting Across Shadow DOM Boundaries{CLR_RESET}")
    
    # Outer Listener pada level #app
    def app_listener(evt: Event, target: Node):
        print(f"  {CLR_GREEN}[Outer Listener (#app)]{CLR_RESET}")
        print(f"    - Event Type    : {evt.type}")
        print(f"    - True Target   : {target}")
        print(f"    - Retargeted?   : {'YA (Boundary Protection Terjaga)' if target == badge else 'TIDAK'}")

    app_root.add_event_listener("component-ping", app_listener)

    # Ambil tombol di dalam shadow root dan klik
    internal_btn = badge._find_in_shadow("button")
    if internal_btn:
        print(f"  Memancarkan custom event dari dalam Shadow DOM: {internal_btn}...")
        ping_event = Event("component-ping", bubbles=True, composed=True)
        internal_btn.dispatch_event(ping_event)

    # Uji Non-Composed Event (tidak boleh bocor ke luar shadow)
    print(f"\n{CLR_BOLD}5. Menguji Non-Composed Event Boundary Isolation{CLR_RESET}")
    isolated_leak = False
    def leak_listener(evt: Event, target: Node):
        nonlocal isolated_leak
        isolated_leak = True

    app_root.add_event_listener("internal-secret", leak_listener)
    secret_event = Event("internal-secret", bubbles=True, composed=False)
    internal_btn.dispatch_event(secret_event)
    
    if not isolated_leak:
        print(f"  {CLR_GREEN}✓ SUKSES: Event dengan composed=False berhasil diisolasi di dalam Shadow DOM!{CLR_RESET}")
    else:
        print(f"  {CLR_RED}✗ GAGAL: Event bocor melintasi batas Shadow boundary!{CLR_RESET}")

    # 6. Unmounting Lifecycle
    print(f"\n{CLR_BOLD}6. Siklus Hidup Unmounting{CLR_RESET}")
    app_root.remove_child(badge)

    print(f"\n{CLR_BOLD}{CLR_GREEN}=== LAB BERHASIL DISELESAIKAN SECARA LENGKAP ==={CLR_RESET}\n")

if __name__ == "__main__":
    main()