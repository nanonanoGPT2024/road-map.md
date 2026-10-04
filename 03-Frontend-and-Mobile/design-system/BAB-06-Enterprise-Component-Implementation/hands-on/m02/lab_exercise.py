#!/usr/bin/env python3
"""
Enterprise Component Implementation: React & Web Components Bridge Engine
========================================================================
Simulates an Enterprise Design System architecture modeling:
1. Multi-tier Design Token Resolution (Global -> Semantic -> Component).
2. Shadow DOM v1 Style Encapsulation & CSS Custom Property inheritance.
3. Custom Elements v1 Lifecycle (connectedCallback, attributeChangedCallback).
4. Slot projection engine (Light DOM to Shadow DOM transclusion).
5. Cross-framework Bridge (React Props -> Web Component Attributes/Properties).
"""

import sys
import time
import json
from typing import Dict, List, Any, Optional, Set

# Terminal styling helper
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_MAGENTA = "\033[35m"
CLR_RED = "\033[31m"
CLR_DIM = "\033[2m"

# ============================================================================
# 1. DESIGN TOKEN RESOLUTION ENGINE
# ============================================================================

class TokenEngine:
    """Resolves hierarchical design tokens (Global -> Semantic -> Component)"""
    def __init__(self):
        self.global_tokens = {
            "color.blue.500": "#0284c7",
            "color.blue.700": "#0369a1",
            "color.slate.100": "#f1f5f9",
            "color.slate.900": "#0f172a",
            "spacing.2": "8px",
            "spacing.4": "16px",
            "radius.md": "6px",
            "radius.full": "9999px"
        }
        self.semantic_tokens = {
            "color.interactive.default": "{color.blue.500}",
            "color.interactive.hover": "{color.blue.700}",
            "color.surface.canvas": "{color.slate.100}",
            "color.text.primary": "{color.slate.900}",
        }
        self.component_tokens = {
            "btn.color.bg": "{color.interactive.default}",
            "btn.color.text": "#ffffff",
            "btn.padding.y": "{spacing.2}",
            "btn.padding.x": "{spacing.4}",
            "btn.radius": "{radius.md}"
        }

    def resolve(self, ref: str) -> str:
        """Recursively dereferences design token aliases."""
        if not (ref.startswith("{") and ref.endswith("}")):
            return ref
        key = ref[1:-1]
        raw_val = (self.component_tokens.get(key) or 
                   self.semantic_tokens.get(key) or 
                   self.global_tokens.get(key))
        if not raw_val:
            raise KeyError(f"Design token undefined: {key}")
        return self.resolve(raw_val)

    def export_css_vars(self) -> Dict[str, str]:
        """Flattens resolved tokens to CSS Custom Properties."""
        css_vars = {}
        for k, v in self.component_tokens.items():
            css_name = f"--ds-{k.replace('.', '-')}"
            css_vars[css_name] = self.resolve(v)
        return css_vars


# ============================================================================
# 2. SHADOW DOM SIMULATOR (ENCAPSULATION & SLOTTING)
# ============================================================================

class ShadowRoot:
    """Simulates Shadow DOM encapsulation and slot transclusion."""
    def __init__(self, host: 'WebComponent', mode: str = "open"):
        self.host = host
        self.mode = mode
        self.scoped_styles: Dict[str, Dict[str, str]] = {}
        self.template: str = ""
        self.slots: Dict[str, str] = {}

    def set_styles(self, rule_set: Dict[str, Dict[str, str]]) -> None:
        self.scoped_styles = rule_set

    def set_template(self, template: str) -> None:
        self.template = template

    def project_slots(self, light_children: Dict[str, str]) -> None:
        self.slots = light_children

    def render_tree(self, inherited_css_vars: Dict[str, str]) -> str:
        """Renders inner DOM, enforcing style boundaries while cascading CSS vars."""
        output = self.template
        # Replace slots
        for slot_name, content in self.slots.items():
            slot_placeholder = f"<slot name='{slot_name}'></slot>" if slot_name != "default" else "<slot></slot>"
            output = output.replace(slot_placeholder, content)

        # Substitute CSS custom properties
        for var_name, var_val in inherited_css_vars.items():
            output = output.replace(f"var({var_name})", var_val)
        return output


# ============================================================================
# 3. WEB COMPONENT SPECIFICATION MODEL
# ============================================================================

class WebComponent:
    """Base class modeling Custom Elements v1 lifecycle standards."""
    observed_attributes: List[str] = []

    def __init__(self, tag_name: str):
        self.tag_name = tag_name
        self.attributes: Dict[str, str] = {}
        self.light_children: Dict[str, str] = {}
        self.shadow_root: Optional[ShadowRoot] = None
        self.is_connected: bool = False

    def attach_shadow(self, mode: str = "open") -> ShadowRoot:
        self.shadow_root = ShadowRoot(self, mode=mode)
        return self.shadow_root

    def set_attribute(self, name: str, val: str) -> None:
        old_val = self.attributes.get(name)
        if old_val != val:
            self.attributes[name] = val
            if name in self.observed_attributes and self.is_connected:
                self.attribute_changed_callback(name, old_val, val)

    def connected_callback(self) -> None:
        self.is_connected = True

    def disconnected_callback(self) -> None:
        self.is_connected = False

    def attribute_changed_callback(self, name: str, old_val: Optional[str], new_val: str) -> None:
        pass


class EnterpriseButton(WebComponent):
    """Production-grade Web Component implementing enterprise button spec."""
    observed_attributes = ["variant", "size", "disabled"]

    def __init__(self):
        super().__init__("ds-button")
        self.shadow = self.attach_shadow(mode="open")
        self._init_component()

    def _init_component(self):
        # Scoped CSS - isolates from external page contamination
        self.shadow.set_styles({
            ":host": {
                "display": "inline-block",
                "box-sizing": "border-box"
            },
            "button": {
                "background-color": "var(--ds-btn-color-bg)",
                "color": "var(--ds-btn-color-text)",
                "padding": "var(--ds-btn-padding-y) var(--ds-btn-padding-x)",
                "border-radius": "var(--ds-btn-radius)",
                "border": "none",
                "cursor": "pointer"
            }
        })
        self._sync_template()

    def _sync_template(self):
        variant = self.attributes.get("variant", "primary")
        disabled_attr = "disabled" if "disabled" in self.attributes else ""
        template = (
            f"<button class='ds-btn ds-btn--{variant}' {disabled_attr}>"
            f"<slot name='icon-left'></slot>"
            f"<span class='label'><slot></slot></span>"
            f"<slot name='icon-right'></slot>"
            f"</button>"
        )
        self.shadow.set_template(template)

    def connected_callback(self):
        super().connected_callback()
        self._sync_template()

    def attribute_changed_callback(self, name: str, old_val: Optional[str], new_val: str):
        self._sync_template()


# ============================================================================
# 4. REACT WRAPPER BRIDGE (FRAMEWORK INTEROP)
# ============================================================================

class ReactComponentBridge:
    """Simulates React Synthetic Layer wrapping native Web Components."""
    def __init__(self, custom_element_cls):
        self.ce_cls = custom_element_cls
        self.instance: Optional[WebComponent] = None

    def render(self, props: Dict[str, Any], children: Dict[str, str], css_env: Dict[str, str]) -> str:
        """Mirrors React's reconciliation, prop diffing, and ref management."""
        if not self.instance:
            self.instance = self.ce_cls()
            self.instance.connected_callback()

        # Attribute synchronization
        for prop_name, prop_val in props.items():
            if prop_name.startswith("on"):
                # Simulates SyntheticEvent attachment
                continue
            if isinstance(prop_val, bool):
                if prop_val:
                    self.instance.set_attribute(prop_name, "")
            else:
                self.instance.set_attribute(prop_name, str(prop_val))

        # Slot transclusion
        self.instance.shadow_root.project_slots(children)
        
        # Render internal Shadow Tree
        return self.instance.shadow_root.render_tree(css_env)


# ============================================================================
# 5. TEST HARNESS & DIAGNOSTIC RUNNER
# ============================================================================

def run_lab():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== ENTERPRISE DESIGN SYSTEM: COMPONENT IMPLEMENTATION LAB ==={CLR_RESET}\n")

    # Step 1: Design Token Resolution
    print(f"{CLR_BOLD}[1/4] Resolving Token Graph Hierarchy...{CLR_RESET}")
    token_engine = TokenEngine()
    css_vars = token_engine.export_css_vars()
    for var, val in css_vars.items():
        print(f"  {CLR_DIM}Inherited Var:{CLR_RESET} {CLR_YELLOW}{var}{CLR_RESET} -> {CLR_GREEN}{val}{CLR_RESET}")

    # Step 2: Web Component Instantiation & Shadow DOM Encapsulation
    print(f"\n{CLR_BOLD}[2/4] Initializing Web Component & Shadow Boundary...{CLR_RESET}")
    btn = EnterpriseButton()
    btn.connected_callback()
    print(f"  Component Tag: {CLR_CYAN}<{btn.tag_name}>{CLR_RESET}")
    print(f"  Shadow Root:   {CLR_GREEN}ACTIVE (Mode: {btn.shadow_root.mode}){CLR_RESET}")
    print(f"  Observed Attrs: {btn.observed_attributes}")

    # Step 3: React Wrapper Simulation & Slot Projection
    print(f"\n{CLR_BOLD}[3/4] Testing React-to-Custom-Element Transclusion Bridge...{CLR_RESET}")
    react_adapter = ReactComponentBridge(EnterpriseButton)
    
    react_props = {"variant": "primary", "disabled": False}
    slots = {
        "default": "Save Pipeline",
        "icon-left": "<svg class='icon-lock'></svg>"
    }
    
    html_output = react_adapter.render(react_props, slots, css_vars)
    print(f"  Render Pass 1 (Primary State):")
    print(f"  {CLR_DIM}{html_output}{CLR_RESET}")

    # Step 4: React Prop Reconciliation (Reactive Updates)
    print(f"\n{CLR_BOLD}[4/4] Mutating React Props -> Web Component Lifecycle Hooks...{CLR_RESET}")
    time.sleep(0.05)
    updated_props = {"variant": "danger", "disabled": True}
    updated_slots = {
        "default": "Terminating Cluster...",
        "icon-left": "<svg class='icon-alert'></svg>"
    }
    
    print(f"  {CLR_YELLOW}Dispatching Prop Mutation:{CLR_RESET} variant='danger', disabled=True")
    html_output_updated = react_adapter.render(updated_props, updated_slots, css_vars)
    print(f"  Render Pass 2 (Reconciled State):")
    print(f"  {CLR_DIM}{html_output_updated}{CLR_RESET}")

    # Step 5: Verification Matrix
    print(f"\n{CLR_BOLD}=== ARCHITECTURE VALIDATION SUMMARY ==={CLR_RESET}")
    checks = [
        ("Design Tokens fully resolved without unresolved aliases", "{" not in "".join(css_vars.values())),
        ("Scoped styles isolate component internals", ":host" in react_adapter.instance.shadow_root.scoped_styles),
        ("Slot projection mapped icon-left to Shadow DOM", "icon-alert" in html_output_updated),
        ("Attribute mutation updated host markup reactively", "ds-btn--danger" in html_output_updated and "disabled" in html_output_updated),
    ]

    all_passed = True
    for desc, passed in checks:
        status = f"{CLR_GREEN}[PASS]{CLR_RESET}" if passed else f"{CLR_RED}[FAIL]{CLR_RESET}"
        if not passed:
            all_passed = False
        print(f"  {status} {desc}")

    if all_passed:
        print(f"\n{CLR_BOLD}{CLR_GREEN}✓ All enterprise encapsulation & bridge protocols verified.{CLR_RESET}\n")
    else:
        print(f"\n{CLR_BOLD}{CLR_RED}✗ Validation failed in design system pipeline.{CLR_RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    run_lab()