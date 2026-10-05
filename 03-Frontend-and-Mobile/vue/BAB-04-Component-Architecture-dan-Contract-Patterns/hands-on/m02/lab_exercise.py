#!/usr/bin/env python3
"""
Lab Exercise: Advanced Vue 3 Component Architecture & Contract Patterns Simulation
Topic: BAB-04 Component Architecture & Contract Patterns
Author: Vue Enterprise Engineering Curriculum

This standalone interactive simulation models core architectural patterns in Vue 3:
1. Typed Props & Emits Validation Engine (Runtime Schema Validation & Invariant Checking)
2. Scoped Slot Contract Projection Engine (Inversion of Control in Rendering)
3. Hierarchical Provide/Inject Dependency Injection with Symbol Keys
4. Compound Component Architecture (Orchestrator + Sub-components pattern)
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type


# ============================================================================
# ANSI Color Palette for Terminal Output
# ============================================================================
class TerminalColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground
    FG_GREEN = "\033[38;2;66;184;131m"      # Vue Emerald Green
    FG_DARK_GREEN = "\033[38;2;53;73;94m"   # Vue Navy Slate
    FG_CYAN = "\033[38;2;56;189;248m"       # Modern Sky Cyan
    FG_BLUE = "\033[38;2;99;102;241m"       # Indigo Accent
    FG_PURPLE = "\033[38;2;168;85;247m"     # Violet
    FG_YELLOW = "\033[38;2;250;204;21m"     # Warning Amber
    FG_RED = "\033[38;2;244;63;94m"         # Rose Red
    FG_WHITE = "\033[38;2;248;250;252m"     # Crisp White
    FG_MUTED = "\033[38;2;148;163;184m"     # Slate Gray

    # Background
    BG_BANNER = "\033[48;2;53;73;94m"
    BG_CODE = "\033[48;2;30;41;59m"


C = TerminalColors


def banner(title: str, subtitle: str = "") -> None:
    print(f"\n{C.BG_BANNER}{C.FG_WHITE}{C.BOLD} {'#' * 72} {C.RESET}")
    print(f"{C.BG_BANNER}{C.FG_GREEN}{C.BOLD}   🚀  {title.upper()}{' ' * max(0, 64 - len(title))} {C.RESET}")
    if subtitle:
        print(f"{C.BG_BANNER}{C.FG_MUTED}   {subtitle}{' ' * max(0, 68 - len(subtitle))} {C.RESET}")
    print(f"{C.BG_BANNER}{C.FG_WHITE}{C.BOLD} {'#' * 72} {C.RESET}\n")


def print_step(step_num: int, label: str) -> None:
    print(f"{C.FG_CYAN}{C.BOLD}[STEP {step_num:02d}]{C.RESET} {C.BOLD}{label}{C.RESET}")


def log_ok(msg: str) -> None:
    print(f"  {C.FG_GREEN}✓{C.RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"  {C.FG_YELLOW}⚠{C.RESET} {msg}")


def log_err(msg: str) -> None:
    print(f"  {C.FG_RED}✗{C.RESET} {msg}")


# ============================================================================
# Section 1: Props & Emits Contract Validation Simulation (defineProps / defineEmits)
# ============================================================================
class PropType(Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"


@dataclass
class PropDefinition:
    type_name: PropType
    required: bool = False
    default: Any = None
    validator: Optional[Callable[[Any], bool]] = None
    validator_msg: str = "Custom validator check failed"


class ComponentContractValidator:
    """Simulates runtime contract validation of defineProps and defineEmits in Vue 3."""

    def __init__(self, name: str, props_schema: Dict[str, PropDefinition], allowed_emits: List[str]):
        self.name = name
        self.props_schema = props_schema
        self.allowed_emits = allowed_emits

    def validate_props(self, raw_props: Dict[str, Any]) -> Dict[str, Any]:
        validated = {}
        errors = []

        # Check required & types
        for prop_name, prop_def in self.props_schema.items():
            if prop_name not in raw_props:
                if prop_def.required:
                    errors.append(f"Missing required prop: '{prop_name}'")
                    continue
                else:
                    validated[prop_name] = prop_def.default
                    continue

            val = raw_props[prop_name]

            # Type checking
            expected_type = {
                PropType.STRING: str,
                PropType.NUMBER: (int, float),
                PropType.BOOLEAN: bool,
                PropType.LIST: list,
                PropType.DICT: dict,
            }[prop_def.type_name]

            if not isinstance(val, expected_type):
                errors.append(
                    f"Invalid type for prop '{prop_name}': expected {prop_def.type_name.value}, got {type(val).__name__}"
                )
                continue

            # Custom validator
            if prop_def.validator and not prop_def.validator(val):
                errors.append(f"Prop '{prop_name}' failed invariant: {prop_def.validator_msg} (val={val})")
                continue

            validated[prop_name] = val

        if errors:
            raise ValueError(f"[{self.name}] Contract Violation:\n" + "\n".join(f"  - {e}" for e in errors))

        return validated

    def validate_emit(self, event_name: str, payload: Any) -> bool:
        if event_name not in self.allowed_emits:
            raise KeyError(
                f"[{self.name}] Undeclared emit: '{event_name}' is not in defineEmits({self.allowed_emits})"
            )
        return True


# ============================================================================
# Section 2: Provide / Inject Context Simulation (Dependency Injection)
# ============================================================================
class InjectionKey:
    """Models unique Symbol() injection token in Vue 3."""

    def __init__(self, description: str):
        self.description = description

    def __repr__(self) -> str:
        return f"Symbol({self.description})"


class ComponentNode:
    """Models a reactive component tree node with provide/inject hierarchy."""

    def __init__(self, name: str, parent: Optional["ComponentNode"] = None):
        self.name = name
        self.parent = parent
        self.provides: Dict[InjectionKey, Any] = {}
        self.children: List["ComponentNode"] = []
        if parent:
            parent.children.append(self)

    def provide(self, key: InjectionKey, value: Any) -> None:
        self.provides[key] = value

    def inject(self, key: InjectionKey, default: Any = None) -> Any:
        current: Optional["ComponentNode"] = self.parent
        while current:
            if key in current.provides:
                return current.provides[key]
            current = current.parent
        if default is not None:
            return default
        raise LookupError(f"Injection token '{key}' could not be resolved in ancestor tree of <{self.name}>")


# ============================================================================
# Section 3: Scoped Slot Projection Engine
# ============================================================================
class SlotRenderer:
    """Models scoped slot projection where parent controls template of child's items."""

    @staticmethod
    def render_list(
        items: List[Dict[str, Any]],
        default_slot: Optional[Callable[[Dict[str, Any], int], str]] = None,
        header_slot: Optional[Callable[[], str]] = None,
    ) -> List[str]:
        output = []
        if header_slot:
            output.append(header_slot())
        else:
            output.append(f"{C.DIM}--- Default Table Header ---{C.RESET}")

        for index, item in enumerate(items):
            if default_slot:
                # Scoped slot: Child passes item and index to parent's renderer function
                output.append(default_slot(item, index))
            else:
                # Fallback slot
                output.append(f"  [{index}] {item}")

        return output


# ============================================================================
# Section 4: Compound Component Architecture (<DataTable> & <DataColumn>)
# ============================================================================
@dataclass
class ColumnConfig:
    prop_key: str
    label: str
    formatter: Optional[Callable[[Any], str]] = None
    custom_render: Optional[Callable[[Dict[str, Any]], str]] = None


class DataTableCompound:
    """Simulates an enterprise Compound Component pattern in Vue 3."""

    def __init__(self, title: str, dataset: List[Dict[str, Any]]):
        self.title = title
        self.dataset = dataset
        self.columns: List[ColumnConfig] = []
        self.sort_column: Optional[str] = None
        self.sort_desc: bool = False

    def add_column(self, col: ColumnConfig) -> "DataTableCompound":
        self.columns.append(col)
        return self

    def set_sort(self, prop_key: str, desc: bool = False) -> None:
        self.sort_column = prop_key
        self.sort_desc = desc

    def render(self) -> None:
        print(f"\n{C.FG_PURPLE}{C.BOLD}┌── Compound Component: <DataTable title=\"{self.title}\"> ───┐{C.RESET}")

        # Sorting logic
        data = list(self.dataset)
        if self.sort_column:
            data.sort(key=lambda x: x.get(self.sort_column, ""), reverse=self.sort_desc)

        # Header Row
        header_cells = []
        for col in self.columns:
            sort_indicator = ""
            if self.sort_column == col.prop_key:
                sort_indicator = " ▼" if self.sort_desc else " ▲"
            header_cells.append(f"{col.label}{sort_indicator}".center(18))
        print(f"{C.BOLD}│ " + " │ ".join(header_cells) + f" │{C.RESET}")
        print("├─" + "─┼─".join(["─" * 18 for _ in self.columns]) + "─┤")

        # Body Rows with Slot/Formatter dispatch
        for row in data:
            row_cells = []
            for col in self.columns:
                if col.custom_render:
                    val_str = col.custom_render(row)
                elif col.formatter:
                    raw_val = row.get(col.prop_key)
                    val_str = col.formatter(raw_val)
                else:
                    val_str = str(row.get(col.prop_key, "-"))
                row_cells.append(val_str.ljust(18)[:18])
            print("│ " + " │ ".join(row_cells) + " │")

        print(f"{C.FG_PURPLE}{C.BOLD}└── Total Records: {len(data)} ──────────────────────────────────────────┘{C.RESET}\n")


# ============================================================================
# Interactive Verification Lab Scenarios
# ============================================================================
def run_props_contract_lab() -> None:
    print_step(1, "Testing Component Contract Boundaries (defineProps / defineEmits)")

    contract = ComponentContractValidator(
        name="EnterpriseUserCard",
        props_schema={
            "userId": PropDefinition(type_name=PropType.STRING, required=True),
            "reputation": PropDefinition(
                type_name=PropType.NUMBER,
                required=False,
                default=100,
                validator=lambda v: 0 <= v <= 1000,
                validator_msg="Reputation must be between 0 and 1000",
            ),
            "tier": PropDefinition(
                type_name=PropType.STRING,
                required=True,
                validator=lambda v: v in ["STANDARD", "PRO", "ENTERPRISE"],
                validator_msg="Tier must be STANDARD, PRO, or ENTERPRISE",
            ),
        },
        allowed_emits=["update:tier", "action-executed"],
    )

    # 1. Valid Input
    valid_payload = {"userId": "usr_9981", "reputation": 850, "tier": "ENTERPRISE"}
    validated = contract.validate_props(valid_payload)
    log_ok(f"Valid props passed contract verification: {validated}")

    # 2. Emit verification
    contract.validate_emit("update:tier", {"newTier": "PRO"})
    log_ok("Declared emit 'update:tier' dispatched successfully")

    # 3. Contract violation testing
    print(f"\n  {C.DIM}Triggering intentional contract violation (Reputation out of bounds)...{C.RESET}")
    invalid_payload = {"userId": "usr_bad", "reputation": 9999, "tier": "PRO"}
    try:
        contract.validate_props(invalid_payload)
        log_err("Expected contract violation did not trigger!")
    except ValueError as e:
        log_ok(f"Contract safely caught violation:\n    {C.FG_RED}{e}{C.RESET}")

    # 4. Undeclared emit testing
    print(f"\n  {C.DIM}Triggering intentional undeclared emit ('delete-account')...{C.RESET}")
    try:
        contract.validate_emit("delete-account", {})
        log_err("Undeclared emit was not caught!")
    except KeyError as e:
        log_ok(f"Strict emit check rejected event:\n    {C.FG_RED}{e}{C.RESET}")


def run_dependency_injection_lab() -> None:
    print_step(2, "Hierarchical Provide/Inject Context Resolution")

    # Define unique injection tokens
    THEME_KEY = InjectionKey("theme_config")
    AUTH_CONTEXT_KEY = InjectionKey("auth_context")
    FEATURE_FLAG_KEY = InjectionKey("feature_flags")

    # Build Component Tree: RootApp -> AdminLayout -> UserManagementView -> RoleBadge
    root = ComponentNode("RootApp")
    layout = ComponentNode("AdminLayout", parent=root)
    view = ComponentNode("UserManagementView", parent=layout)
    badge = ComponentNode("RoleBadge", parent=view)

    # Root provides Theme and Auth
    root.provide(THEME_KEY, {"mode": "dark", "primaryColor": "#42b883"})
    root.provide(AUTH_CONTEXT_KEY, {"user": "admin@vue-architecture.internal", "role": "SuperAdmin"})

    # Layout overrides Theme (Scoped theming)
    layout.provide(THEME_KEY, {"mode": "high-contrast", "primaryColor": "#38bdf8"})

    # Badge consumes from ancestors
    resolved_theme = badge.inject(THEME_KEY)
    resolved_auth = badge.inject(AUTH_CONTEXT_KEY)
    fallback_flags = badge.inject(FEATURE_FLAG_KEY, default={"v2Enabled": False})

    log_ok(f"Badge injected scoped theme from closest ancestor: {C.FG_CYAN}{resolved_theme}{C.RESET}")
    log_ok(f"Badge injected auth from distant Root ancestor: {C.FG_GREEN}{resolved_auth}{C.RESET}")
    log_ok(f"Badge resolved fallback default for missing provider: {C.FG_YELLOW}{fallback_flags}{C.RESET}")


def run_scoped_slots_lab() -> None:
    print_step(3, "Inversion of Control via Scoped Slots Projection")

    users = [
        {"id": 1, "name": "Alice Cooper", "role": "Architect", "active": True},
        {"id": 2, "name": "Bob Dylan", "role": "Lead Engineer", "active": False},
        {"id": 3, "name": "Charlie Parker", "role": "Security Reviewer", "active": True},
    ]

    # Custom Scoped Slot defined by Parent
    def parent_custom_slot(item: Dict[str, Any], idx: int) -> str:
        status_badge = f"{C.FG_GREEN}[ACTIVE]{C.RESET}" if item["active"] else f"{C.FG_RED}[INACTIVE]{C.RESET}"
        return (
            f"  {C.FG_CYAN}#{idx+1}{C.RESET} | {C.BOLD}{item['name']:<16}{C.RESET} | "
            f"{C.FG_BLUE}{item['role']:<18}{C.RESET} | {status_badge}"
        )

    def parent_header() -> str:
        return f"{C.FG_WHITE}{C.BOLD}  === Production User Directory (Parent Slot Projection) ==={C.RESET}"

    rendered = SlotRenderer.render_list(users, default_slot=parent_custom_slot, header_slot=parent_header)
    for line in rendered:
        print(line)


def run_compound_component_lab() -> None:
    print_step(4, "Compound Component Execution (<DataTable> + <DataColumn>)")

    sample_metrics = [
        {"service": "auth-service", "latency_ms": 28, "throughput": 1250, "status": "HEALTHY"},
        {"service": "payment-gateway", "latency_ms": 142, "throughput": 420, "status": "DEGRADED"},
        {"service": "search-indexer", "latency_ms": 15, "throughput": 3400, "status": "HEALTHY"},
        {"service": "report-worker", "latency_ms": 620, "throughput": 45, "status": "CRITICAL"},
    ]

    def status_formatter(row: Dict[str, Any]) -> str:
        s = row.get("status")
        if s == "HEALTHY":
            return f"{C.FG_GREEN}● HEALTHY{C.RESET}"
        elif s == "DEGRADED":
            return f"{C.FG_YELLOW}▲ DEGRADED{C.RESET}"
        return f"{C.FG_RED}✖ CRITICAL{C.RESET}"

    table = (
        DataTableCompound("Cluster Microservice Observability", sample_metrics)
        .add_column(ColumnConfig(prop_key="service", label="Service Name"))
        .add_column(
            ColumnConfig(
                prop_key="latency_ms",
                label="Latency",
                formatter=lambda val: f"{val} ms",
            )
        )
        .add_column(
            ColumnConfig(
                prop_key="throughput",
                label="Req / sec",
                formatter=lambda val: f"{val:,} rps",
            )
        )
        .add_column(
            ColumnConfig(
                prop_key="status",
                label="Health Status",
                custom_render=status_formatter,
            )
        )
    )

    table.set_sort("latency_ms", desc=True)
    table.render()


def main() -> None:
    banner(
        "Vue 3 Enterprise Component Architecture & Contracts",
        "BAB-04 Interactive Hands-on Architecture Lab",
    )

    print(f"{C.BOLD}Choose Execution Mode:{C.RESET}")
    print(f"  1. Run All Architecture Verifications Sequentially")
    print(f"  2. Test Props & Emits Contract Validation")
    print(f"  3. Test Hierarchical Provide/Inject Engine")
    print(f"  4. Test Scoped Slot Projection")
    print(f"  5. Test Compound Component Pattern (<DataTable>)")
    print(f"  0. Exit\n")

    # Support non-interactive CLI flags or interactive prompt
    choice = "1"
    if sys.stdin.isatty():
        try:
            choice = input(f"{C.FG_CYAN}Select option [1-5, default=1]: {C.RESET}").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            choice = "1"

    print("\n" + "=" * 74)

    if choice == "1":
        run_props_contract_lab()
        print("\n" + "-" * 74)
        time.sleep(0.1)
        run_dependency_injection_lab()
        print("\n" + "-" * 74)
        time.sleep(0.1)
        run_scoped_slots_lab()
        print("\n" + "-" * 74)
        time.sleep(0.1)
        run_compound_component_lab()
    elif choice == "2":
        run_props_contract_lab()
    elif choice == "3":
        run_dependency_injection_lab()
    elif choice == "4":
        run_scoped_slots_lab()
    elif choice == "5":
        run_compound_component_lab()
    elif choice == "0":
        print("Exiting lab.")
        return
    else:
        print(f"{C.FG_YELLOW}Unknown selection. Running complete test suite by default.{C.RESET}")
        run_props_contract_lab()
        run_dependency_injection_lab()
        run_scoped_slots_lab()
        run_compound_component_lab()

    print("=" * 74)
    print(f"\n{C.FG_GREEN}{C.BOLD}All architecture simulation contracts validated successfully!{C.RESET}\n")


if __name__ == "__main__":
    main()
