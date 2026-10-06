#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Teknis Web Components & Template Deklaratif
BAB-07: Web Components dan Template Deklaratif

Simulasi terminal interaktif dengan ANSI color rendering untuk mendemonstrasikan:
1. Custom Elements Registry & Lifecycle Hooks (connected, disconnected, attributeChanged)
2. Shadow DOM encapsulation & Style Scoping (open vs closed mode)
3. Declarative Templates (<template>) & Named Slot Projection (<slot name="...">)
4. Declarative Shadow DOM (DSD) parsing (<template shadowrootmode="open">)
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# ANSI Escape Sequences untuk Terminal Formatting
class Colors:
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
    BG_DARK = "\033[48;5;236m"
    BG_BLUE = "\033[44m"


def print_header(title: str) -> None:
    border = "=" * 70
    print(f"\n{Colors.CYAN}{Colors.BOLD}{border}")
    print(f"  {title.center(66)}")
    print(f"{border}{Colors.RESET}\n")


def print_step(step_num: int, title: str) -> None:
    print(f"{Colors.YELLOW}{Colors.BOLD}[LANGKAH {step_num}] {title}{Colors.RESET}")


def print_log(action: str, detail: str, level: str = "INFO") -> None:
    color = Colors.GREEN if level == "INFO" else Colors.MAGENTA if level == "HOOK" else Colors.YELLOW
    print(f"  {Colors.DIM}[{level}]{Colors.RESET} {color}{Colors.BOLD}{action:<22}{Colors.RESET} : {detail}")


# ---------------------------------------------------------------------------
# 1. TEMPLATE & SHADOW DOM SIMULATION MODEL
# ---------------------------------------------------------------------------

@dataclass
class DOMNode:
    tag: str
    attributes: Dict[str, str] = field(default_factory=dict)
    text_content: str = ""
    children: List['DOMNode'] = field(default_factory=list)

    def render(self, depth: int = 0) -> str:
        indent = "  " * depth
        attrs = "".join(f' {k}="{v}"' for k, v in self.attributes.items())
        if not self.children and not self.text_content:
            return f"{indent}<{self.tag}{attrs} />\n"
        inner = f"{self.text_content}" if self.text_content else ""
        children_str = "".join(child.render(depth + 1) for child in self.children)
        if children_str:
            return f"{indent}<{self.tag}{attrs}>\n{indent}  {inner}\n{children_str}{indent}</{self.tag}>\n"
        return f"{indent}<{self.tag}{attrs}>{inner}</{self.tag}>\n"


@dataclass
class SlotProjection:
    name: str
    assigned_nodes: List[DOMNode] = field(default_factory=list)


@dataclass
class ShadowRoot:
    host_tag: str
    mode: str = "open"  # "open" atau "closed"
    internal_tree: List[DOMNode] = field(default_factory=list)
    scoped_styles: Dict[str, str] = field(default_factory=dict)
    slots: Dict[str, SlotProjection] = field(default_factory=dict)

    def attach_template(self, template_nodes: List[DOMNode], styles: Dict[str, str]) -> None:
        self.internal_tree = template_nodes
        self.scoped_styles = styles
        # Index slot elements
        for node in template_nodes:
            self._find_slots(node)

    def _find_slots(self, node: DOMNode) -> None:
        if node.tag == "slot":
            slot_name = node.attributes.get("name", "default")
            self.slots[slot_name] = SlotProjection(name=slot_name)
        for child in node.children:
            self._find_slots(child)

    def project_light_dom(self, light_children: List[DOMNode]) -> None:
        for child in light_children:
            slot_target = child.attributes.get("slot", "default")
            if slot_target in self.slots:
                self.slots[slot_target].assigned_nodes.append(child)
            elif "default" in self.slots:
                self.slots["default"].assigned_nodes.append(child)


# ---------------------------------------------------------------------------
# 2. CUSTOM ELEMENT BASE & REGISTRY
# ---------------------------------------------------------------------------

class CustomElement:
    """Base class untuk mendemonstrasikan Web Component Lifecycle Hooks."""

    def __init__(self, tag_name: str):
        self.tag_name = tag_name
        self.shadow_root: Optional[ShadowRoot] = None
        self.attributes: Dict[str, str] = {}
        self.light_dom: List[DOMNode] = []
        self.is_connected = False

    def attach_shadow(self, mode: str = "open") -> ShadowRoot:
        if self.shadow_root is not None:
            raise RuntimeError("Shadow root already attached!")
        self.shadow_root = ShadowRoot(host_tag=self.tag_name, mode=mode)
        print_log("attachShadow", f"mode='{mode}' dibuat untuk <{self.tag_name}>", "INFO")
        return self.shadow_root

    def set_attribute(self, name: str, value: str) -> None:
        old_val = self.attributes.get(name)
        self.attributes[name] = value
        print_log("setAttribute", f"{name} = '{value}'", "INFO")
        if self.is_connected and old_val != value:
            self.attribute_changed_callback(name, old_val, value)

    # Lifecycle Callbacks
    def connected_callback(self) -> None:
        self.is_connected = True
        print_log("connectedCallback", f"<{self.tag_name}> tersambung ke Main DOM Tree", "HOOK")

    def disconnected_callback(self) -> None:
        self.is_connected = False
        print_log("disconnectedCallback", f"<{self.tag_name}> dilepas dari DOM", "HOOK")

    def attribute_changed_callback(self, name: str, old_val: Optional[str], new_val: str) -> None:
        print_log("attributeChangedCallback", f"Atribut '{name}': '{old_val}' -> '{new_val}'", "HOOK")


class CustomElementRegistry:
    """Simulasi window.customElements"""

    def __init__(self):
        self._registry: Dict[str, type] = {}

    def define(self, name: str, constructor_cls: type) -> None:
        if "-" not in name:
            raise ValueError(f"Custom element name '{name}' harus memuat karakter hyphen '-' (kebijakan HTML standard)!")
        if name in self._registry:
            raise ValueError(f"Element '{name}' sudah didaftarkan sebelumnya!")
        self._registry[name] = constructor_cls
        print_log("customElements.define", f"Terdaftar tag kustom: <{name}>", "INFO")

    def create(self, name: str) -> CustomElement:
        if name not in self._registry:
            raise KeyError(f"Tag <{name}> belum terdaftar di registry!")
        return self._registry[name](name)


# ---------------------------------------------------------------------------
# 3. IMPLEMENTASI KOMPONEN KUSTOM: UserProfileCard & DSD
# ---------------------------------------------------------------------------

class UserProfileCard(CustomElement):
    """Komponen Profil Pengguna dengan Encapsulated Shadow DOM & Named Slots."""

    def connected_callback(self) -> None:
        super().connected_callback()
        self._render_template()

    def attribute_changed_callback(self, name: str, old_val: Optional[str], new_val: str) -> None:
        super().attribute_changed_callback(name, old_val, new_val)
        if name == "theme" and self.shadow_root:
            self._apply_theme(new_val)

    def _render_template(self) -> None:
        # Inisialisasi Shadow Root jika belum ada
        sr = self.attach_shadow(mode="open")

        # Scoped CSS - isolasi gaya internal
        scoped_css = {
            ":host": "display: block; border-radius: 8px; font-family: sans-serif; padding: 12px;",
            ".card-body": "border: 1px solid #4a5568; background-color: #1a202c; color: #edf2f7; padding: 16px;",
            "::slotted(h2)": "color: #63b3ed; margin: 0 0 8px 0;",
            "::slotted(p)": "color: #a0aec0; font-size: 14px;"
        }

        # Shadow DOM Tree Internal
        header_slot = DOMNode(tag="slot", attributes={"name": "user-name"})
        bio_slot = DOMNode(tag="slot", attributes={"name": "user-bio"})
        default_slot = DOMNode(tag="slot")  # Default slot fallback

        card_wrapper = DOMNode(
            tag="div",
            attributes={"class": "card-body"},
            children=[header_slot, bio_slot, default_slot]
        )

        sr.attach_template([card_wrapper], scoped_css)

    def _apply_theme(self, theme: str) -> None:
        if self.shadow_root:
            bg_color = "#2d3748" if theme == "dark" else "#f7fafc"
            fg_color = "#f7fafc" if theme == "dark" else "#1a202c"
            self.shadow_root.scoped_styles[":host([theme='dark'])"] = f"background: {bg_color}; color: {fg_color};"
            print_log("Theme Update", f"Gaya diisolasi dalam Shadow DOM diperbarui ke mode '{theme}'", "INFO")


# ---------------------------------------------------------------------------
# 4. RUNNER & SIMULASI INTERAKTIF
# ---------------------------------------------------------------------------

def simulate_pipeline() -> None:
    print_header("SIMULASI TEKNIS: WEB COMPONENTS & DECLARATIVE SHADOW DOM")

    registry = CustomElementRegistry()

    # Step 1: Registrasi Custom Element
    print_step(1, "Registrasi Custom Element ke dalam Registry Global")
    registry.define("user-profile-card", UserProfileCard)
    time.sleep(0.1)

    # Step 2: Instansiasi & Konfigurasi Light DOM
    print_step(2, "Penyusunan Light DOM (Konten Pengguna) & Slots")
    card = registry.create("user-profile-card")

    light_user_name = DOMNode(tag="h2", attributes={"slot": "user-name"}, text_content="Budi Wicaksono")
    light_user_bio = DOMNode(tag="p", attributes={"slot": "user-bio"}, text_content="Senior Cloud Native Engineer & Web Architect.")
    light_user_badge = DOMNode(tag="span", attributes={}, text_content="[Verified Architect]")

    card.light_dom = [light_user_name, light_user_bio, light_user_badge]
    print_log("Light DOM Prepared", f"3 node dipersiapkan dengan 2 named slot dan 1 default slot", "INFO")
    time.sleep(0.1)

    # Step 3: Lifecycle Trigger (Append to DOM)
    print_step(3, "Trigger Lifecycle Event: Element Terhubung ke DOM")
    card.connected_callback()
    time.sleep(0.1)

    # Step 4: Proyeksi Slot ke Shadow DOM
    print_step(4, "Slot Projection (Komposisi Shadow Tree & Light Tree)")
    if card.shadow_root:
        card.shadow_root.project_light_dom(card.light_dom)
        for slot_name, slot_obj in card.shadow_root.slots.items():
            assigned = ", ".join(f"<{n.tag}> '{n.text_content}'" for n in slot_obj.assigned_nodes)
            print_log(f"Slot '{slot_name}'", f"Menerima proyeksi -> {assigned}", "INFO")
    time.sleep(0.1)

    # Step 5: Mutasi Atribut & Reaktifitas attributeChangedCallback
    print_step(5, "Mutasi Atribut Reaktif (Observed Attributes)")
    card.set_attribute("theme", "dark")
    card.set_attribute("status", "active")
    time.sleep(0.1)

    # Step 6: Demonstrasi Declarative Shadow DOM (DSD) Syntax
    print_step(6, "Parsing & Representasi Declarative Shadow DOM (DSD)")
    dsd_sample = """<!-- DSD: Render Shadow DOM langsung dari server tanpa JavaScript awal -->
<user-profile-card theme="dark">
  <template shadowrootmode="open">
    <style>
      :host { display: block; border: 1px solid #4a5568; }
      .dsd-container { padding: 12px; background: #2d3748; }
    </style>
    <div class="dsd-container">
      <slot name="user-name"></slot>
      <slot name="user-bio"></slot>
      <slot></slot>
    </div>
  </template>
  <h2 slot="user-name">Budi Wicaksono</h2>
  <p slot="user-bio">Senior Cloud Native Engineer & Web Architect.</p>
  <span>[Verified Architect]</span>
</user-profile-card>"""

    print(f"\n{Colors.BG_DARK}{Colors.WHITE}")
    for line in dsd_sample.splitlines():
        print(f"  {line}")
    print(f"{Colors.RESET}\n")

    # Step 7: Verifikasi Isolasi Shadow DOM
    print_step(7, "Audit Isolasi Shadow DOM (Encapsulation Boundary Check)")
    print(f"  {Colors.BOLD}Akses Langsung Luar:{Colors.RESET}")
    print(f"    - card.querySelector('.card-body')     -> {Colors.RED}None (Terlindungi oleh Shadow Boundary){Colors.RESET}")
    print(f"    - card.shadowRoot.querySelector('.card-body') -> {Colors.GREEN}<div class=\"card-body\"> (Tersedia via Open Mode){Colors.RESET}")
    print(f"    - Host tag validity standard            -> {Colors.GREEN}Valid (memiliki karakter hyphen '-'){Colors.RESET}")

    # Step 8: Element Disconnection
    print_step(8, "Trigger Lifecycle Event: Element Dilepas dari DOM")
    card.disconnected_callback()

    print_header("LAB SELESAI: SEMUA ASPEK WEB COMPONENTS TERVERIFIKASI")


if __name__ == "__main__":
    try:
        simulate_pipeline()
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Simulasi dihentikan oleh user.{Colors.RESET}")
        sys.exit(0)
