#!/usr/bin/env python3
"""
Lab Exercise: Vue 3 Component Architecture & Contract Patterns Simulator
Bab 04: Component Architecture dan Contract Patterns

Topik yang disimulasikan:
1. Props Contract & Runtime Validation (type, required, default, custom validator)
2. One-Way Data Flow (Props Mutation Guard)
3. Emits Contract Validation (Event payload type & business rule enforcement)
4. Slots Pattern (Default, Named, dan Scoped Slots)
5. Provide / Inject Hierarchy (Dependency Injection antar komponen)
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, Union


# --- ANSI Terminal Color Palette ---
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
    print(f"\n{Style.BOLD}{Style.CYAN}{'=' * 65}{Style.RESET}")
    print(f"{Style.BOLD}{Style.WHITE}  🚀 {title.upper()}{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}{'=' * 65}{Style.RESET}")


def subheader(step: str) -> None:
    print(f"\n{Style.BOLD}{Style.YELLOW}▶ {step}{Style.RESET}")
    print(f"{Style.DIM}{'-' * 55}{Style.RESET}")


def log_ok(msg: str) -> None:
    print(f"  {Style.GREEN}✔ [CONTRACT PASS]{Style.RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"  {Style.YELLOW}⚠ [VUE WARNING]{Style.RESET} {msg}")


def log_err(msg: str) -> None:
    print(f"  {Style.RED}✖ [VALIDATION FAILED]{Style.RESET} {msg}")


def log_info(label: str, val: Any) -> None:
    print(f"    {Style.MAGENTA}{label}:{Style.RESET} {val}")


# --- 1. PROPS CONTRACT DEFINITION ---
@dataclass
class PropDefinition:
    type_: Union[Type, tuple]
    required: bool = False
    default: Any = None
    validator: Optional[Callable[[Any], bool]] = None


class PropsValidator:
    @staticmethod
    def validate(name: str, definition: PropDefinition, raw_value: Any) -> Any:
        # Check required & default
        if raw_value is None:
            if definition.required:
                raise ValueError(f"Prop '{name}' ditandai required tapi bernilai None/undefined!")
            return definition.default

        # Check type
        if not isinstance(raw_value, definition.type_):
            expected = definition.type_ if isinstance(definition.type_, tuple) else definition.type_.__name__
            actual = type(raw_value).__name__
            raise TypeError(
                f"Tipe data prop '{name}' tidak valid! Ekspektasi: {expected}, Diterima: {actual}"
            )

        # Check custom validator
        if definition.validator and not definition.validator(raw_value):
            raise ValueError(f"Nilai '{raw_value}' gagal lolos custom validator untuk prop '{name}'!")

        return raw_value


# --- 2. EMITS CONTRACT DEFINITION ---
class EmitsContract:
    def __init__(self, schemas: Dict[str, Callable[[Any], bool]]):
        self.schemas = schemas

    def validate_emit(self, event_name: str, payload: Any) -> bool:
        if event_name not in self.schemas:
            log_warn(f"Event '{event_name}' di-emit tanpa dideklarasikan di defineEmits()!")
            return True
        validator_fn = self.schemas[event_name]
        is_valid = validator_fn(payload)
        if not is_valid:
            log_err(f"Payload event '{event_name}' ({payload}) gagal melewati kontrak validasi defineEmits!")
            return False
        return True


# --- 3. BASE VUE COMPONENT SIMULATOR ---
class VueComponent:
    def __init__(
        self,
        name: str,
        props_def: Optional[Dict[str, PropDefinition]] = None,
        emits_def: Optional[Dict[str, Callable[[Any], bool]]] = None,
        parent: Optional["VueComponent"] = None,
    ):
        self.name = name
        self.props_def = props_def or {}
        self.emits = EmitsContract(emits_def or {})
        self.parent = parent
        self._props: Dict[str, Any] = {}
        self._provided: Dict[str, Any] = {}
        self.slots: Dict[str, Callable[..., str]] = {}
        self.children: List["VueComponent"] = []

        if parent:
            parent.children.append(self)

    def set_props(self, input_props: Dict[str, Any]) -> None:
        for p_name, p_def in self.props_def.items():
            val = input_props.get(p_name, None)
            validated_val = PropsValidator.validate(p_name, p_def, val)
            self._props[p_name] = validated_val

    @property
    def props(self) -> Dict[str, Any]:
        return self._props

    def mutate_prop_direct(self, prop_name: str, new_val: Any) -> None:
        log_warn(
            f"Mutasi langsung prop '{prop_name}' terdeteksi pada <{self.name} />! "
            f"Melanggar One-Way Data Flow. Gunakan 'update:{prop_name}' atau emit event!"
        )
        # Vue props are reactive read-only proxies
        # Kita tolak perubahan langsung
        raise PermissionError(f"Cannot mutate prop '{prop_name}' directly in child component.")

    def emit(self, event_name: str, payload: Any = None) -> None:
        if self.emits.validate_emit(event_name, payload):
            log_ok(f"Component <{self.name} /> sukses emit event '{event_name}' dengan payload: {payload}")
            if self.parent:
                self.parent.on_child_event(self.name, event_name, payload)

    def on_child_event(self, child_name: str, event_name: str, payload: Any) -> None:
        print(f"    {Style.DIM}↳ Parent <{self.name} /> menangkap event @{event_name} dari <{child_name} />{Style.RESET}")

    # Dependency Injection: Provide / Inject
    def provide(self, key: str, value: Any) -> None:
        self._provided[key] = value

    def inject(self, key: str, default: Any = None) -> Any:
        curr: Optional["VueComponent"] = self.parent
        while curr:
            if key in curr._provided:
                return curr._provided[key]
            curr = curr.parent
        if default is not None:
            return default
        raise KeyError(f"Injection symbol '{key}' tidak ditemukan di seluruh leluhur komponen <{self.name} />!")

    # Slots Renderer
    def render_slot(self, slot_name: str = "default", **slot_props) -> str:
        if slot_name in self.slots:
            return self.slots[slot_name](**slot_props)
        return f"{Style.DIM}[Empty Slot: {slot_name}]{Style.RESET}"


# --- 4. DEMONSTRATION WORKFLOWS ---
def demo_props_contract():
    subheader("1. Props Contract: Type, Default, & Custom Validator")
    
    # Kontrak props untuk UserCard.vue
    user_card_props = {
        "userId": PropDefinition(type_=int, required=True),
        "username": PropDefinition(type_=str, required=True),
        "role": PropDefinition(
            type_=str,
            required=False,
            default="viewer",
            validator=lambda val: val in ["admin", "editor", "viewer"]
        ),
        "score": PropDefinition(
            type_=(int, float),
            required=False,
            default=0,
            validator=lambda s: 0 <= s <= 100
        )
    }

    card = VueComponent("UserCard", props_def=user_card_props)

    # Test Kasus A: Valid Props
    print(f"\n  {Style.BOLD}Kasus A: Passing Props Sesuai Kontrak (Valid){Style.RESET}")
    valid_input = {"userId": 101, "username": "alex_dev", "role": "editor", "score": 88.5}
    card.set_props(valid_input)
    log_ok("Props berhasil diverifikasi dan diinisialisasi:")
    for k, v in card.props.items():
        log_info(k, v)

    # Test Kasus B: Default Value Fallback
    print(f"\n  {Style.BOLD}Kasus B: Mengabaikan Optional Props (Default Fallback){Style.RESET}")
    minimal_input = {"userId": 202, "username": "siti_qa"}
    card.set_props(minimal_input)
    log_ok(f"Role otomatis fallback ke: '{card.props['role']}', Score: {card.props['score']}")

    # Test Kasus C: Tipe Data Salah
    print(f"\n  {Style.BOLD}Kasus C: Pelanggaran Tipe Data (Type Mismatch){Style.RESET}")
    try:
        invalid_type = {"userId": "BukanInteger", "username": "budi"}
        card.set_props(invalid_type)
    except TypeError as e:
        log_err(str(e))

    # Test Kasus D: Gagal Custom Validator
    print(f"\n  {Style.BOLD}Kasus D: Pelanggaran Custom Business Validator (Role Invalid){Style.RESET}")
    try:
        invalid_role = {"userId": 303, "username": "hacker", "role": "superadmin"}
        card.set_props(invalid_role)
    except ValueError as e:
        log_err(str(e))


def demo_one_way_data_flow():
    subheader("2. One-Way Data Flow Guard (Mutasi Prop Ditolak)")
    
    comp = VueComponent("ProfileEditor", props_def={
        "status": PropDefinition(type_=str, default="draft")
    })
    comp.set_props({"status": "published"})

    print(f"  Current prop status: {Style.BOLD}{comp.props['status']}{Style.RESET}")
    print(f"  {Style.DIM}Mencoba mengeksekusi: comp.props['status'] = 'archived' secara lokal...{Style.RESET}")
    
    try:
        comp.mutate_prop_direct("status", "archived")
    except PermissionError as e:
        log_err(f"Tindakan Dicegah: {e}")
        log_ok("Pola One-Way Data Flow terjaga aman.")


def demo_emits_contract():
    subheader("3. Emits Contract Validation (Event Payload Verification)")

    # defineEmits dengan validator fungsi
    emits_schema = {
        "submit": lambda payload: isinstance(payload, dict) and "id" in payload and payload["id"] > 0,
        "toggle-modal": lambda payload: isinstance(payload, bool)
    }

    form_comp = VueComponent("CheckoutForm", emits_def=emits_schema)

    print(f"  {Style.BOLD}Kasus A: Emit dengan Payload Valid{Style.RESET}")
    form_comp.emit("submit", {"id": 42, "item": "Keyboard Mekanikal"})
    form_comp.emit("toggle-modal", True)

    print(f"\n  {Style.BOLD}Kasus B: Emit dengan Payload Ilegal (Pelanggaran Kontrak){Style.RESET}")
    form_comp.emit("submit", {"id": -1, "item": "Invalid ID"})
    form_comp.emit("toggle-modal", "BUKAN_BOOLEAN")


def demo_slots_pattern():
    subheader("4. Slot Architecture: Default, Named, & Scoped Slots")

    # Simulasi <DataTable> component dengan scoped slot untuk custom row rendering
    table_comp = VueComponent("DataTable")

    # Parent menyediakan templates ke dalam slots child
    # 1. Named slot: 'header'
    table_comp.slots["header"] = lambda **_: (
        f"{Style.BOLD}{Style.WHITE}[HEADER TEMPLATE]: Laporan Data Pengguna Terdaftar{Style.RESET}"
    )

    # 2. Scoped slot: 'row' (Child mengekspos data ke parent)
    table_comp.slots["row"] = lambda item, index: (
        f"  [{index + 1}] User: {Style.CYAN}{item['name']}{Style.RESET} | "
        f"Role: {Style.YELLOW}{item['role']}{Style.RESET} | "
        f"Badge: {'⭐ VIP' if item['is_vip'] else '👤 Normal'}"
    )

    # Child me-render slot header
    print(table_comp.render_slot("header"))

    # Child me-render rows menggunakan scoped slot
    dummy_dataset = [
        {"name": "Andi Pratama", "role": "Fullstack", "is_vip": True},
        {"name": "Bambang Wijaya", "role": "DevOps", "is_vip": False},
        {"name": "Citra Lestari", "role": "UI/UX", "is_vip": True},
    ]

    print(f"\n  {Style.BOLD}Rendering Scoped Slot dengan Data Internal Child:{Style.RESET}")
    for idx, user in enumerate(dummy_dataset):
        rendered_row = table_comp.render_slot("row", item=user, index=idx)
        print(rendered_row)

    log_ok("Scoped slot mendistribusikan data internal child ke template parent tanpa kebocoran state.")


def demo_provide_inject():
    subheader("5. Provide / Inject Pattern (Hierarki Tree Dependency Injection)")

    # Struktur Hirarki: RootApp -> AdminDashboard -> SettingsPanel -> ThemeToggle
    app = VueComponent("RootApp")
    dashboard = VueComponent("AdminDashboard", parent=app)
    settings = VueComponent("SettingsPanel", parent=dashboard)
    toggle = VueComponent("ThemeToggle", parent=settings)

    # RootApp menyediakan global services / tema
    print("  RootApp menyediakan (provide) context:")
    app.provide("theme", "cyberpunk-neon")
    app.provide("api_endpoint", "https://api.internal.corp/v1")
    log_info("Provided 'theme'", "cyberpunk-neon")
    log_info("Provided 'api_endpoint'", "https://api.internal.corp/v1")

    # ThemeToggle di kedalaman level 4 meng-inject langsung tanpa prop drilling!
    print(f"\n  Komponen daun terpencil <{toggle.name} /> melakukan inject:")
    injected_theme = toggle.inject("theme")
    injected_api = toggle.inject("api_endpoint")

    log_ok(f"Theme berhasil di-inject ke <{toggle.name} />: '{injected_theme}'")
    log_ok(f"API Endpoint berhasil di-inject: '{injected_api}'")

    # Kasus inject key yang tidak ada
    try:
        toggle.inject("non_existent_key")
    except KeyError as e:
        log_warn(f"Inject gagal ditangani sesuai ekspektasi: {e}")


def main():
    header("Vue 3 Component Architecture & Contract Patterns Simulator")
    print(f"{Style.DIM}Lab simulasi teknis arsitektur berbasis komponen Vue modern.{Style.RESET}")

    demo_props_contract()
    demo_one_way_data_flow()
    demo_emits_contract()
    demo_slots_pattern()
    demo_provide_inject()

    print(f"\n{Style.BOLD}{Style.GREEN}{'=' * 65}{Style.RESET}")
    print(f"{Style.BOLD}{Style.GREEN}  🎉 SELURUH KONTRAK & SIMULASI ARSITEKTUR KOMPONEN SELESAI{Style.RESET}")
    print(f"{Style.BOLD}{Style.GREEN}{'=' * 65}{Style.RESET}\n")


if __name__ == "__main__":
    main()
