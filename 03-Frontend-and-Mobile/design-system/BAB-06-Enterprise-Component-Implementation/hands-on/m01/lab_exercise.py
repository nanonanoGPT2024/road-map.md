#!/usr/bin/env python3
"""
Enterprise Component Implementation & Design System Foundation Lab
BAB-06: Enterprise Component Implementation (Hands-on M01)

Features:
- Multi-tier Token Resolution Engine (Global -> Semantic -> Component)
- Polymorphic Component Architecture & Variant Matrix
- Compound Component State Machine & Context Propagation
- Automated WCAG 2.1 AA / WAI-ARIA Accessibility Validation
- ANSI Colored Terminal Visualizer & Test Harness
"""

from __future__ import annotations
import dataclasses
import json
import sys
import time
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# ANSI Terminal Palette & Formatting
# ============================================================================
class TerminalStyle:
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
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_DARK = "\033[40m"


def colorize(text: str, color: str, bold: bool = False) -> str:
    prefix = f"{TerminalStyle.BOLD}{color}" if bold else color
    return f"{prefix}{text}{TerminalStyle.RESET}"


# ============================================================================
# Core Foundation 1: Multi-Tier Token Resolution Engine
# ============================================================================
class TokenRegistry:
    """Manages Global, Semantic, and Component-level Design Tokens."""

    def __init__(self) -> None:
        self.global_tokens: Dict[str, str] = {
            "color.blue.600": "#2563EB",
            "color.blue.700": "#1D4ED8",
            "color.gray.100": "#F3F4F6",
            "color.gray.300": "#D1D5DB",
            "color.gray.800": "#1F2937",
            "color.red.500": "#EF4444",
            "spacing.sm": "8px",
            "spacing.md": "16px",
            "spacing.lg": "24px",
            "radius.sm": "4px",
            "radius.md": "8px",
            "font.family.base": "'Inter', system-ui, -apple-system, sans-serif",
        }

        self.semantic_tokens: Dict[str, str] = {
            "color.action.primary.default": "{color.blue.600}",
            "color.action.primary.hover": "{color.blue.700}",
            "color.feedback.danger": "{color.red.500}",
            "color.surface.card": "{color.gray.100}",
            "color.text.body": "{color.gray.800}",
            "border.subtle": "{color.gray.300}",
            "component.radius": "{radius.md}",
        }

        self.component_tokens: Dict[str, Dict[str, str]] = {
            "Button": {
                "padding.x": "{spacing.md}",
                "padding.y": "{spacing.sm}",
                "border.radius": "{component.radius}",
                "bg.primary": "{color.action.primary.default}",
                "bg.primary.hover": "{color.action.primary.hover}",
                "bg.danger": "{color.feedback.danger}",
            }
        }

    def resolve(self, reference: str, depth: int = 0) -> str:
        """Recursively resolve token references (e.g. {color.action.primary.default})."""
        if depth > 10:
            raise RecursionError(f"Circular reference detected while resolving token: {reference}")

        if not (reference.startswith("{") and reference.endswith("}")):
            return reference

        token_key = reference[1:-1]

        # 1. Check semantic tokens
        if token_key in self.semantic_tokens:
            return self.resolve(self.semantic_tokens[token_key], depth + 1)

        # 2. Check global tokens
        if token_key in self.global_tokens:
            return self.global_tokens[token_key]

        raise KeyError(f"Undefined token reference: {token_key}")

    def resolve_component_token(self, component_name: str, property_name: str) -> str:
        token_ref = self.component_tokens.get(component_name, {}).get(property_name)
        if not token_ref:
            raise KeyError(f"Component '{component_name}' has no token for '{property_name}'")
        return self.resolve(token_ref)


# ============================================================================
# Core Foundation 2: Polymorphic Component Contract & State Machine
# ============================================================================
class ComponentState:
    IDLE = "idle"
    HOVER = "hover"
    ACTIVE = "active"
    FOCUS = "focus"
    DISABLED = "disabled"
    LOADING = "loading"


@dataclasses.dataclass
class AccessibilitySpec:
    role: str
    aria_label: Optional[str] = None
    aria_expanded: Optional[bool] = None
    aria_controls: Optional[str] = None
    aria_disabled: bool = False
    focusable: bool = True

    def validate(self) -> List[str]:
        issues = []
        if self.role in ("button", "link") and not self.aria_label:
            issues.append(f"WCAG WARNING: Element with role '{self.role}' requires an accessible text name or aria-label.")
        if self.role == "dialog" and not self.aria_label:
            issues.append("WCAG ERROR: Dialog modals must provide aria-labelledby or aria-label.")
        if self.aria_expanded is not None and not self.aria_controls:
            issues.append("ARIA ERROR: aria-expanded should be paired with aria-controls ID.")
        return issues


class EnterpriseButton:
    """Enterprise-grade polymorphic Button component model."""

    def __init__(
        self,
        label: str,
        variant: str = "primary",
        size: str = "medium",
        as_tag: str = "button",
        disabled: bool = False,
        loading: bool = False,
        tokens: Optional[TokenRegistry] = None,
    ) -> None:
        self.label = label
        self.variant = variant
        self.size = size
        self.as_tag = as_tag
        self.disabled = disabled
        self.loading = loading
        self.tokens = tokens or TokenRegistry()
        self.state = ComponentState.DISABLED if disabled else ComponentState.IDLE

        self.a11y = AccessibilitySpec(
            role="button",
            aria_label=label,
            aria_disabled=disabled or loading,
            focusable=not disabled,
        )

    def transition_to(self, new_state: str) -> None:
        if self.disabled and new_state != ComponentState.DISABLED:
            return  # Locked when disabled
        self.state = new_state

    def render(self) -> str:
        bg_token = "bg.primary" if self.variant == "primary" else "bg.danger"
        resolved_bg = self.tokens.resolve_component_token("Button", bg_token)
        resolved_radius = self.tokens.resolve_component_token("Button", "border.radius")
        resolved_px = self.tokens.resolve_component_token("Button", "padding.x")

        # Color mapping for terminal visualization
        ansi_color = TerminalStyle.CYAN if self.variant == "primary" else TerminalStyle.RED
        if self.state == ComponentState.HOVER:
            ansi_color = TerminalStyle.BLUE
        elif self.state == ComponentState.DISABLED:
            ansi_color = TerminalStyle.DIM

        display_text = "⏳ Loading..." if self.loading else self.label
        tag_info = colorize(f"<{self.as_tag}>", TerminalStyle.MAGENTA)
        rendered_badge = colorize(f"[{display_text}]", ansi_color, bold=True)

        metadata = (
            f"variant='{self.variant}' state='{self.state}' "
            f"token(bg)='{resolved_bg}' radius='{resolved_radius}' px='{resolved_px}'"
        )
        return f"{tag_info} {rendered_badge} {colorize(metadata, TerminalStyle.DIM)}"


# ============================================================================
# Core Foundation 3: Compound Component Pattern (Accordion Context)
# ============================================================================
class AccordionContext:
    def __init__(self, allow_multiple: bool = False) -> None:
        self.allow_multiple = allow_multiple
        self.expanded_ids: set[str] = set()

    def toggle(self, item_id: str) -> None:
        if item_id in self.expanded_ids:
            self.expanded_ids.remove(item_id)
        else:
            if not self.allow_multiple:
                self.expanded_ids.clear()
            self.expanded_ids.add(item_id)

    def is_expanded(self, item_id: str) -> bool:
        return item_id in self.expanded_ids


class AccordionItem:
    def __init__(self, item_id: str, title: str, content: str, context: AccordionContext) -> None:
        self.item_id = item_id
        self.title = title
        self.content = content
        self.context = context

    @property
    def a11y(self) -> AccessibilitySpec:
        is_open = self.context.is_expanded(self.item_id)
        return AccessibilitySpec(
            role="button",
            aria_label=self.title,
            aria_expanded=is_open,
            aria_controls=f"panel-{self.item_id}",
        )

    def render(self) -> str:
        is_open = self.context.is_expanded(self.item_id)
        icon = colorize("▼", TerminalStyle.GREEN) if is_open else colorize("▶", TerminalStyle.YELLOW)
        header = f"{icon} {colorize(self.title, TerminalStyle.BOLD)} (aria-expanded={is_open})"

        if is_open:
            panel_content = colorize(f"    └─ {self.content}", TerminalStyle.CYAN)
            return f"{header}\n{panel_content}"
        return header


# ============================================================================
# Interactive Terminal Simulation & Diagnostics Engine
# ============================================================================
class EnterpriseDesignSystemLab:
    def __init__(self) -> None:
        self.registry = TokenRegistry()

    def print_banner(self) -> None:
        banner = f"""
{TerminalStyle.BOLD}{TerminalStyle.CYAN}======================================================================
  ENTERPRISE DESIGN SYSTEM LAB | BAB-06 COMPONENT IMPLEMENTATION
======================================================================{TerminalStyle.RESET}
{colorize("Architecture: Token Graph -> State Machine -> Compound Context -> A11y Audit", TerminalStyle.DIM)}
"""
        print(banner)

    def run_token_resolution_demo(self) -> None:
        print(colorize("\n[Step 1/4] Multi-Tier Token Resolution Graph", TerminalStyle.YELLOW, bold=True))
        keys_to_resolve = [
            ("Global Reference", "{color.blue.600}"),
            ("Semantic Alias", "{color.action.primary.default}"),
            ("Component Token", "{component.radius}"),
        ]

        for category, ref in keys_to_resolve:
            val = self.registry.resolve(ref)
            print(f"  • {category:<20} {colorize(ref, TerminalStyle.MAGENTA):<35} ──► {colorize(val, TerminalStyle.GREEN, bold=True)}")

    def run_component_matrix_demo(self) -> None:
        print(colorize("\n[Step 2/4] Polymorphic Button State Matrix", TerminalStyle.YELLOW, bold=True))

        btn_primary = EnterpriseButton("Submit Application", variant="primary", tokens=self.registry)
        btn_hover = EnterpriseButton("Submit Application", variant="primary", tokens=self.registry)
        btn_hover.transition_to(ComponentState.HOVER)

        btn_danger = EnterpriseButton("Delete Workspace", variant="danger", tokens=self.registry)
        btn_loading = EnterpriseButton("Processing", variant="primary", loading=True, tokens=self.registry)
        btn_disabled = EnterpriseButton("Disabled Action", variant="primary", disabled=True, tokens=self.registry)
        btn_link = EnterpriseButton("View Documentation", variant="primary", as_tag="a", tokens=self.registry)

        for btn in [btn_primary, btn_hover, btn_danger, btn_loading, btn_disabled, btn_link]:
            print(f"  {btn.render()}")

    def run_compound_component_demo(self) -> None:
        print(colorize("\n[Step 3/4] Compound Component Context (Accordion Single-Select)", TerminalStyle.YELLOW, bold=True))
        ctx = AccordionContext(allow_multiple=False)
        item1 = AccordionItem("item-1", "Design Tokens Pipeline", "Tokens are compiled to CSS custom properties & JSON definitions.", ctx)
        item2 = AccordionItem("item-2", "Accessibility & ARIA", "WCAG AA contrast ratios and correct state flags are mandatory.", ctx)
        item3 = AccordionItem("item-3", "Automated Visual Regression", "Playwright snapshots capture delta diffs across viewport sizes.", ctx)

        # Initial state
        ctx.toggle("item-1")
        print("  State: Item 1 Expanded:")
        for item in [item1, item2, item3]:
            print(f"  {item.render()}")

        print("\n  State: User clicks Item 2 (auto-collapses Item 1):")
        ctx.toggle("item-2")
        for item in [item1, item2, item3]:
            print(f"  {item.render()}")

    def run_accessibility_audit(self) -> None:
        print(colorize("\n[Step 4/4] Automated Accessibility (A11y) Engine Diagnostic", TerminalStyle.YELLOW, bold=True))
        specs: List[Tuple[str, AccessibilitySpec]] = [
            ("Valid Primary Button", AccessibilitySpec(role="button", aria_label="Save Record")),
            ("Violating Button", AccessibilitySpec(role="button", aria_label=None)),
            ("Accordion Trigger with Orphan Expanded", AccessibilitySpec(role="button", aria_label="FAQ", aria_expanded=True)),
            ("Valid Accessible Modal Dialog", AccessibilitySpec(role="dialog", aria_label="Confirm Order")),
        ]

        for name, spec in specs:
            issues = spec.validate()
            if issues:
                status = colorize("[FAIL]", TerminalStyle.RED, bold=True)
                print(f"  {status} {colorize(name, TerminalStyle.WHITE, bold=True)}")
                for issue in issues:
                    print(f"         └─ {colorize(issue, TerminalStyle.RED)}")
            else:
                status = colorize("[PASS]", TerminalStyle.GREEN, bold=True)
                print(f"  {status} {colorize(name, TerminalStyle.WHITE, bold=True)} - All WCAG & ARIA constraints satisfied.")

    def run_all(self) -> None:
        self.print_banner()
        self.run_token_resolution_demo()
        self.run_component_matrix_demo()
        self.run_compound_component_demo()
        self.run_accessibility_audit()
        print(colorize("\n✔ Design System Foundation Simulation Completed Successfully!\n", TerminalStyle.GREEN, bold=True))


# ============================================================================
# Entry Point
# ============================================================================
if __name__ == "__main__":
    lab = EnterpriseDesignSystemLab()
    lab.run_all()
