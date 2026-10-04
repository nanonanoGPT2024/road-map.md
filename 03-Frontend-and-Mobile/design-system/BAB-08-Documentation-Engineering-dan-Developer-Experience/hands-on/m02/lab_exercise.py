#!/usr/bin/env python3
"""
Lab Exercise: Documentation Engineering & Developer Experience (DX)
Deep Dive: Automated Component DocGen, AST Prop Contract Linter, and Inverted Search Index
Category: 03-Frontend-and-Mobile / Design-System / Chapter 08
"""

import re
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple

# Terminal ANSI Styling
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
GRAY = "\033[90m"


@dataclass
class PropContract:
    """Represents a component prop schema parsed from design system tokens/specs."""
    name: str
    type_name: str
    required: bool = False
    default: Optional[str] = None
    allowed_values: Optional[List[str]] = None
    deprecated: bool = False
    deprecation_reason: Optional[str] = None
    description: str = ""


@dataclass
class ComponentSpec:
    """Design System Component Specification AST equivalent."""
    name: str
    category: str
    description: str
    a11y_guidelines: List[str]
    tokens_consumed: List[str]
    props: Dict[str, PropContract] = field(default_factory=dict)


@dataclass
class Diagnostic:
    """DX diagnostic warning or error report."""
    severity: str  # 'ERROR' | 'WARNING'
    component: str
    message: str
    suggested_fix: Optional[str] = None
    line_snippet: Optional[str] = None


class DXDocEngine:
    """
    Automated DocGen Engine and DX Linter.
    Features:
    1. Prop Contract Compilation & Markdown Generation.
    2. Real-time Consumer Code Linter (validating JSX against contracts).
    3. Inverted Full-Text Search Engine for tokens and component docs.
    """

    def __init__(self):
        self.registry: Dict[str, ComponentSpec] = {}
        self.search_index: Dict[str, Set[str]] = defaultdict(set)

    def register_component(self, spec: ComponentSpec) -> None:
        """Registers a component spec and indexes its tokens for rapid DX search."""
        self.registry[spec.name] = spec
        self._index_component(spec)

    def _index_component(self, spec: ComponentSpec) -> None:
        """Builds an inverted index mapping tokens and keywords to component names."""
        tokens = set()
        # Index component identity
        tokens.update(self._tokenize(spec.name))
        tokens.update(self._tokenize(spec.category))
        tokens.update(self._tokenize(spec.description))

        # Index props
        for p_name, prop in spec.props.items():
            tokens.update(self._tokenize(p_name))
            if prop.allowed_values:
                for val in prop.allowed_values:
                    tokens.update(self._tokenize(val))

        # Index consumed design tokens
        for dt in spec.tokens_consumed:
            tokens.update(self._tokenize(dt))

        for t in tokens:
            self.search_index[t.lower()].add(spec.name)

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer handling camelCase, kebab-case, and words."""
        cleaned = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        cleaned = re.sub(r'[^a-zA-Z0-9]', ' ', cleaned)
        return [word.lower() for word in cleaned.split() if len(word) > 2]

    def search_docs(self, query: str) -> List[Tuple[str, float]]:
        """Queries the inverted search index with term relevance scoring."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: Dict[str, float] = defaultdict(float)
        for token in query_tokens:
            matches = self.search_index.get(token, set())
            for comp_name in matches:
                # Give higher weight to matches in component name or tokens
                weight = 1.0
                if token in comp_name.lower():
                    weight += 2.0
                scores[comp_name] += weight

        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results

    def lint_jsx_usage(self, jsx_code: str) -> List[Diagnostic]:
        """
        DX Linter: Parses pseudo-JSX/TSX snippets used by consumers, validating
        prop names, types, allowed enum values, deprecated props, and mandatory a11y props.
        """
        diagnostics: List[Diagnostic] = []
        
        # Regex extraction of JSX tags: <ComponentName prop1="val" prop2={val} ... />
        tag_pattern = re.compile(r'<([A-Z][a-zA-Z0-9]+)\s*([^>]*?)(?:/>|>)')
        prop_pattern = re.compile(r'([a-zA-Z0-9_-]+)(?:=(?:"([^"]*)"|\{([^}]*)\}))?')

        matches = tag_pattern.findall(jsx_code)
        for comp_name, raw_props in matches:
            if comp_name not in self.registry:
                diagnostics.append(Diagnostic(
                    severity="ERROR",
                    component=comp_name,
                    message=f"Unknown design system component '{comp_name}'."
                ))
                continue

            spec = self.registry[comp_name]
            parsed_props: Dict[str, str] = {}
            for p_match in prop_pattern.finditer(raw_props):
                p_key = p_match.group(1)
                p_val = p_match.group(2) if p_match.group(2) is not None else p_match.group(3)
                parsed_props[p_key] = p_val if p_val is not None else "true"

            # Check 1: Missing Required Props
            for req_prop, prop_schema in spec.props.items():
                if prop_schema.required and req_prop not in parsed_props:
                    diagnostics.append(Diagnostic(
                        severity="ERROR",
                        component=comp_name,
                        message=f"Missing required prop: '{req_prop}' ({prop_schema.type_name}).",
                        suggested_fix=f"Pass `{req_prop}=...` according to component spec.",
                        line_snippet=f"<{comp_name} {raw_props.strip()} />"
                    ))

            # Check 2: Prop Validation & Deprecation Warnings
            for passed_prop, passed_val in parsed_props.items():
                if passed_prop not in spec.props:
                    diagnostics.append(Diagnostic(
                        severity="ERROR",
                        component=comp_name,
                        message=f"Prop '{passed_prop}' does not exist on component '{comp_name}'.",
                        suggested_fix=f"Remove or rename '{passed_prop}'.",
                        line_snippet=f"<{comp_name} ... {passed_prop}={passed_val} />"
                    ))
                    continue

                prop_schema = spec.props[passed_prop]

                # Check Deprecation
                if prop_schema.deprecated:
                    diagnostics.append(Diagnostic(
                        severity="WARNING",
                        component=comp_name,
                        message=f"Prop '{passed_prop}' is deprecated. {prop_schema.deprecation_reason or ''}",
                        suggested_fix="Refer to migration guide in design system docs.",
                        line_snippet=f"{passed_prop}={passed_val}"
                    ))

                # Check Allowed Enum Values
                if prop_schema.allowed_values and passed_val not in prop_schema.allowed_values:
                    diagnostics.append(Diagnostic(
                        severity="ERROR",
                        component=comp_name,
                        message=f"Invalid value '{passed_val}' for prop '{passed_prop}'. Allowed: {prop_schema.allowed_values}",
                        suggested_fix=f"Use one of: {', '.join(prop_schema.allowed_values)}",
                        line_snippet=f"{passed_prop}=\"{passed_val}\""
                    ))

            # Check 3: A11y heuristic (e.g., IconButton requires aria-label)
            if "icon" in comp_name.lower() or "button" in comp_name.lower():
                if "aria-label" not in parsed_props and "children" not in parsed_props and "label" not in parsed_props:
                    diagnostics.append(Diagnostic(
                        severity="WARNING",
                        component=comp_name,
                        message="Accessibility check failed: Interactive element lacks an accessible text/label.",
                        suggested_fix="Supply an 'aria-label' or descriptive children.",
                        line_snippet=f"<{comp_name} {raw_props.strip()} />"
                    ))

        return diagnostics

    def generate_markdown_doc(self, comp_name: str) -> str:
        """Generates comprehensive MDX/Markdown documentation artifact for a component."""
        if comp_name not in self.registry:
            raise ValueError(f"Component '{comp_name}' not found.")

        spec = self.registry[comp_name]
        lines = [
            f"# {spec.name}",
            f"**Category:** `{spec.category}`  ",
            f"**Description:** {spec.description}\n",
            "## Design Tokens Consumed",
            ", ".join([f"`{t}`" for t in spec.tokens_consumed]) if spec.tokens_consumed else "_None_",
            "\n## Component Props (Contract Table)",
            "| Prop Name | Type | Required | Default | Allowed Values | Deprecated? | Description |",
            "| :--- | :--- | :---: | :---: | :--- | :---: | :--- |"
        ]

        for p_name, p in spec.props.items():
            req_str = "Yes" if p.required else "No"
            def_str = f"`{p.default}`" if p.default else "-"
            enum_str = f"`{' | '.join(p.allowed_values)}`" if p.allowed_values else "-"
            dep_str = "⚠️ Deprecated" if p.deprecated else "No"
            lines.append(f"| `{p_name}` | `{p.type_name}` | {req_str} | {def_str} | {enum_str} | {dep_str} | {p.description} |")

        lines.append("\n## Accessibility Guidelines")
        for g in spec.a11y_guidelines:
            lines.append(f"- [x] {g}")

        return "\n".join(lines)


def setup_mock_design_system(engine: DXDocEngine) -> None:
    """Populates the engine with canonical enterprise components."""
    # 1. Button Component
    button = ComponentSpec(
        name="Button",
        category="General / Actions",
        description="High-frequency interactive element triggering workflows or submits.",
        a11y_guidelines=[
            "Supports keyboard focus ring (WCAG 2.4.7)",
            "Must announce state via aria-disabled or aria-busy",
            "Must have accessible text or aria-label for screen readers"
        ],
        tokens_consumed=[
            "color.brand.primary.500",
            "spacing.md",
            "radius.sm",
            "elevation.button.active"
        ]
    )
    button.props["variant"] = PropContract(
        name="variant",
        type_name="string",
        required=False,
        default="solid",
        allowed_values=["solid", "outline", "ghost", "danger"],
        description="Visual emphasis hierarchy."
    )
    button.props["size"] = PropContract(
        name="size",
        type_name="string",
        required=False,
        default="md",
        allowed_values=["sm", "md", "lg"],
        description="Size metrics and touch-target padding."
    )
    button.props["disabled"] = PropContract(
        name="disabled",
        type_name="boolean",
        default="false",
        description="Controls interaction accessibility and styling."
    )
    button.props["isPrimary"] = PropContract(
        name="isPrimary",
        type_name="boolean",
        deprecated=True,
        deprecation_reason="Use `variant='solid'` instead.",
        description="Legacy flag for primary styling."
    )
    engine.register_component(button)

    # 2. Modal Dialog
    modal = ComponentSpec(
        name="Modal",
        category="Feedback / Overlays",
        description="Interruptive layer trapping user focus to complete a workflow.",
        a11y_guidelines=[
            "Focus must be trapped inside modal until dismissed",
            "Esc key must fire onClose handler",
            "Must declare role='dialog' and aria-modal='true'"
        ],
        tokens_consumed=[
            "color.surface.overlay.backdrop",
            "elevation.modal",
            "spacing.xl"
        ]
    )
    modal.props["isOpen"] = PropContract(
        name="isOpen",
        type_name="boolean",
        required=True,
        description="Visibility state trigger."
    )
    modal.props["onClose"] = PropContract(
        name="onClose",
        type_name="() => void",
        required=True,
        description="Callback fired upon dismiss request."
    )
    modal.props["title"] = PropContract(
        name="title",
        type_name="string",
        required=True,
        description="Accessible modal title linked via aria-labelledby."
    )
    engine.register_component(modal)

    # 3. Avatar
    avatar = ComponentSpec(
        name="Avatar",
        category="Media / Display",
        description="Visual representation of a user profile with fallback initials.",
        a11y_guidelines=["Must provide alt text or role='img' with aria-label"],
        tokens_consumed=["radius.full", "color.background.neutral.subtle"]
    )
    avatar.props["src"] = PropContract(
        name="src",
        type_name="string",
        required=False,
        description="Image URL of the user avatar."
    )
    avatar.props["name"] = PropContract(
        name="name",
        type_name="string",
        required=True,
        description="Full name utilized for initials fallback and a11y."
    )
    engine.register_component(avatar)


def main() -> None:
    print(f"\n{BOLD}{MAGENTA}====================================================================={RESET}")
    print(f"{BOLD}{MAGENTA}  DESIGN SYSTEM LAB: Documentation Engineering & DX Tooling Engine   {RESET}")
    print(f"{BOLD}{MAGENTA}====================================================================={RESET}\n")

    engine = DXDocEngine()
    setup_mock_design_system(engine)
    print(f"{GREEN}[✓]{RESET} Registered {len(engine.registry)} components in Design System Registry.\n")

    # TEST CASE 1: Component Doc Generation
    print(f"{BOLD}{CYAN}--- PART 1: Automated MDX / Markdown Doc Compilation ---{RESET}")
    doc_markdown = engine.generate_markdown_doc("Button")
    print(GRAY + "-" * 70 + RESET)
    print(doc_markdown)
    print(GRAY + "-" * 70 + RESET)

    # TEST CASE 2: DX Linter Validation on Consumer Code
    print(f"\n{BOLD}{CYAN}--- PART 2: Real-time Developer Experience (DX) Story / JSX Linter ---{RESET}")
    test_snippets = [
        # Snippet A: Valid usage
        ('<Button variant="solid" size="md" disabled="false" />', "Valid Button Scenario"),
        # Snippet B: Invalid prop values + Deprecated prop + Missing A11y
        ('<Button variant="glowing" isPrimary="true" />', "Defective Button Usage"),
        # Snippet C: Missing required props on Modal
        ('<Modal isOpen="true" />', "Defective Modal Usage (Missing required props)"),
        # Snippet D: Unknown component
        ('<DatePicker mode="range" />', "Unregistered Component Usage")
    ]

    for snippet, label in test_snippets:
        print(f"\n{BOLD}Linting Snippet [{label}]:{RESET}")
        print(f"  Code: {YELLOW}{snippet}{RESET}")
        diagnostics = engine.lint_jsx_usage(snippet)

        if not diagnostics:
            print(f"  {GREEN}[PASS]{RESET} No DX diagnostics reported! Contract intact.")
        else:
            for diag in diagnostics:
                color = RED if diag.severity == "ERROR" else YELLOW
                print(f"  {color}[{diag.severity}]{RESET} ({diag.component}) {diag.message}")
                if diag.suggested_fix:
                    print(f"    {CYAN}↳ Fix:{RESET} {diag.suggested_fix}")

    # TEST CASE 3: Inverted Full-Text Documentation Search Engine
    print(f"\n{BOLD}{CYAN}--- PART 3: DX Documentation & Token Inverted Search Index ---{RESET}")
    queries = ["modal overlay", "brand primary", "ghost action", "unknown query"]

    for query in queries:
        start_time = time.perf_counter_ns()
        results = engine.search_docs(query)
        elapsed_us = (time.perf_counter_ns() - start_time) / 1000.0

        print(f"\nSearch Query: '{YELLOW}{query}{RESET}' ({elapsed_us:.2f} µs)")
        if not results:
            print(f"  {GRAY}No documentation or token matches found.{RESET}")
        else:
            for comp_name, score in results:
                print(f"  • Found {BOLD}{comp_name}{RESET} (Relevance Score: {score:.1f})")

    print(f"\n{GREEN}{BOLD}[LAB COMPLETE] Documentation Engineering Pipeline & DX Engine Executed Successfully.{RESET}\n")


if __name__ == "__main__":
    main()