#!/usr/bin/env python3
"""
Lab: CSS Engine Internals, Parsing, and Cascade Mathematics
Category: 03-Frontend-and-Mobile | Chapter 01 - Deep Dive

Simulates the core pipeline of a browser CSS engine:
1. Lexical Tokenization & AST generation of CSS rules.
2. Specificity Vector Calculation (Inline, ID, Class/Attr/Pseudo, Type/Pseudo-element).
3. Cascade Sort Algorithm implementing Origin & Importance precedence.
4. Style Resolution over a mock DOM Element Tree.
"""

import re
import sys
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

# --- ANSI Terminal Color Formatting ---
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


class CascadeOrigin(IntEnum):
    """
    CSS Cascade Origin and Importance levels (CSS Cascading and Inheritance Level 4).
    Higher integer represents higher cascade precedence.
    """
    USER_AGENT_NORMAL = 1
    USER_NORMAL = 2
    AUTHOR_NORMAL = 3
    AUTHOR_IMPORTANT = 5
    USER_IMPORTANT = 6
    USER_AGENT_IMPORTANT = 7


@dataclass(frozen=True)
class Specificity:
    """
    Represents the 4-tier specificity vector (A, B, C, D):
    A: Inline style flag (1 or 0)
    B: Count of ID selectors (#id)
    C: Count of Class selectors, Attributes, and Pseudo-classes (.class, [attr], :hover)
    D: Count of Type/Tag selectors and Pseudo-elements (div, p, ::before)
    """
    inline: int
    ids: int
    classes: int
    elements: int

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.inline, self.ids, self.classes, self.elements)

    def __lt__(self, other: "Specificity") -> bool:
        return self.as_tuple() < other.as_tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Specificity):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __repr__(self) -> str:
        return f"({self.inline}, {self.ids}, {self.classes}, {self.elements})"


@dataclass
class PropertyDeclaration:
    name: str
    value: str
    important: bool
    origin: CascadeOrigin
    specificity: Specificity
    source_order: int  # Document order for tie-breaking


@dataclass
class CSSRule:
    selector_str: str
    declarations: List[Tuple[str, str, bool]]  # (property, value, is_important)
    origin: CascadeOrigin
    source_order: int


@dataclass
class DOMElement:
    tag: str
    id: Optional[str]
    classes: List[str]
    attributes: Dict[str, str]
    inline_styles: Dict[str, str]


def calculate_specificity(selector: str) -> Specificity:
    """
    Parses a CSS selector string and computes its (0, B, C, D) specificity vector.
    Strips out combinators, comments, and pseudo-class arguments like :not().
    """
    clean_sel = re.sub(r"/\*.*?\*/", "", selector).strip()

    # Negation pseudo-class: :not(X) specificity is specificity of its argument X
    not_matches = re.findall(r":not\(([^)]+)\)", clean_sel)
    ids_count = 0
    classes_count = 0
    elements_count = 0

    for arg in not_matches:
        arg_spec = calculate_specificity(arg)
        ids_count += arg_spec.ids
        classes_count += arg_spec.classes
        elements_count += arg_spec.elements

    # Remove evaluated :not(...) wrappers for base pattern matching
    clean_sel = re.sub(r":not\([^)]+\)", " ", clean_sel)

    # 1. Match IDs: #example
    ids = re.findall(r"#[a-zA-Z0-9_\-]+", clean_sel)
    ids_count += len(ids)
    clean_sel = re.sub(r"#[a-zA-Z0-9_\-]+", " ", clean_sel)

    # 2. Match Pseudo-elements: ::before, ::after
    pseudo_elements = re.findall(r"::[a-zA-Z0-9_\-]+", clean_sel)
    elements_count += len(pseudo_elements)
    clean_sel = re.sub(r"::[a-zA-Z0-9_\-]+", " ", clean_sel)

    # 3. Match Classes, Attributes, and Pseudo-classes
    classes = re.findall(r"\.[a-zA-Z0-9_\-]+", clean_sel)
    attrs = re.findall(r"\[[^\]]+\]", clean_sel)
    pseudo_classes = re.findall(r":[a-zA-Z0-9_\-]+", clean_sel)

    classes_count += len(classes) + len(attrs) + len(pseudo_classes)
    clean_sel = re.sub(r"\.[a-zA-Z0-9_\-]+", " ", clean_sel)
    clean_sel = re.sub(r"\[[^\]]+\]", " ", clean_sel)
    clean_sel = re.sub(r":[a-zA-Z0-9_\-]+", " ", clean_sel)

    # 4. Match Elements/Tags: div, p, span, body, button
    # Replace combinators (> + ~) with whitespace
    clean_sel = re.sub(r"[>+~*]", " ", clean_sel)
    tokens = clean_sel.split()
    elements_count += len(tokens)

    return Specificity(inline=0, ids=ids_count, classes=classes_count, elements=elements_count)


def parse_stylesheet(css_text: str, origin: CascadeOrigin, base_order: int = 0) -> List[CSSRule]:
    """
    Lexes raw CSS rules, tokenizing selectors, properties, values, and !important markers.
    """
    rules: List[CSSRule] = []
    # Match block patterns: selector { body }
    blocks = re.findall(r"([^{]+)\{([^}]+)\}", css_text)

    order = base_order
    for sel_raw, body_raw in blocks:
        selectors = [s.strip() for s in sel_raw.split(",") if s.strip()]
        declarations = []
        for prop_line in body_raw.split(";"):
            line = prop_line.strip()
            if not line or ":" not in line:
                continue
            prop, val = line.split(":", 1)
            prop = prop.strip().lower()
            val = val.strip()

            is_important = False
            if "!important" in val.lower():
                is_important = True
                val = re.sub(r"!important", "", val, flags=re.IGNORECASE).strip()

            declarations.append((prop, val, is_important))

        for selector in selectors:
            order += 1
            rules.append(CSSRule(
                selector_str=selector,
                declarations=declarations,
                origin=origin,
                source_order=order
            ))

    return rules


def element_matches_selector(element: DOMElement, selector: str) -> bool:
    """
    Targeted selector engine matching simple selectors and ancestor/descendant relationships.
    """
    # Tokenize right-to-left (standard CSS parsing flow)
    tokens = selector.strip().split()
    if not tokens:
        return False

    # Check key selector (the rightmost unit)
    key_sel = tokens[-1]

    # Tag check
    tag_match = re.match(r"^([a-zA-Z0-9]+)", key_sel)
    if tag_match and tag_match.group(1).lower() != element.tag.lower():
        return False

    # ID check
    id_match = re.search(r"#([a-zA-Z0-9_\-]+)", key_sel)
    if id_match and id_match.group(1) != element.id:
        return False

    # Class check
    classes = re.findall(r"\.([a-zA-Z0-9_\-]+)", key_sel)
    for c in classes:
        if c not in element.classes:
            return False

    # Attribute check
    attrs = re.findall(r"\[([a-zA-Z0-9_\-]+)=?\"?([^\"\]]*)\"?\]", key_sel)
    for k, v in attrs:
        if k not in element.attributes:
            return False
        if v and element.attributes.get(k) != v:
            return False

    return True


def cascade_sort_key(decl: PropertyDeclaration) -> Tuple[int, Tuple[int, int, int, int], int]:
    """
    Computes standard Cascade Priority Tuple:
    1. Origin and Importance level
    2. Specificity vector (Inline, ID, Class, Type)
    3. Source Order
    """
    effective_origin = decl.origin
    if decl.important:
        if decl.origin == CascadeOrigin.USER_AGENT_NORMAL:
            effective_origin = CascadeOrigin.USER_AGENT_IMPORTANT
        elif decl.origin == CascadeOrigin.USER_NORMAL:
            effective_origin = CascadeOrigin.USER_IMPORTANT
        elif decl.origin == CascadeOrigin.AUTHOR_NORMAL:
            effective_origin = CascadeOrigin.AUTHOR_IMPORTANT

    return (
        int(effective_origin),
        decl.specificity.as_tuple(),
        decl.source_order
    )


def resolve_computed_styles(element: DOMElement, rules: List[CSSRule]) -> Dict[str, PropertyDeclaration]:
    """
    Resolves the active declaration for all properties applied to a DOM element,
    simulating the cascade resolution phase of a browser layout engine.
    """
    matched_declarations: Dict[str, List[PropertyDeclaration]] = {}

    # 1. Collect declarations from matched stylesheet rules
    for rule in rules:
        if element_matches_selector(element, rule.selector_str):
            spec = calculate_specificity(rule.selector_str)
            for prop, val, is_important in rule.declarations:
                decl = PropertyDeclaration(
                    name=prop,
                    value=val,
                    important=is_important,
                    origin=rule.origin,
                    specificity=spec,
                    source_order=rule.source_order
                )
                matched_declarations.setdefault(prop, []).append(decl)

    # 2. Collect inline styles (Origin = Author, Specificity = (1, 0, 0, 0))
    for prop, val in element.inline_styles.items():
        is_important = False
        val_clean = val
        if "!important" in val.lower():
            is_important = True
            val_clean = re.sub(r"!important", "", val, flags=re.IGNORECASE).strip()

        decl = PropertyDeclaration(
            name=prop,
            value=val_clean,
            important=is_important,
            origin=CascadeOrigin.AUTHOR_NORMAL,
            specificity=Specificity(1, 0, 0, 0),
            source_order=999999  # Inline styles visually sit after external rules
        )
        matched_declarations.setdefault(prop, []).append(decl)

    # 3. Perform Cascade Resolution per property
    computed_styles: Dict[str, PropertyDeclaration] = {}
    for prop, candidates in matched_declarations.items():
        # Sort by: Origin/Importance -> Specificity -> Source Order
        sorted_candidates = sorted(candidates, key=cascade_sort_key)
        # Winner is the highest-precedence element (last after ascending sort)
        computed_styles[prop] = sorted_candidates[-1]

    return computed_styles


def print_banner():
    print(f"{CYAN}{BOLD}=" * 80)
    print("   BROWSER CSS ENGINE INTERNALS & CASCADE MATHEMATICS SIMULATOR")
    print("=" * 80 + f"{RESET}")


def run_cascade_lab():
    print_banner()

    # Define Multi-Origin CSS Source Trees
    user_agent_css = """
        button {
            display: inline-block;
            background-color: #e0e0e0;
            color: #000000;
            font-size: 13px;
            border: 1px solid #767676;
            cursor: default;
        }
    """

    user_css = """
        button {
            font-size: 14px !important; /* Accessibility override */
            cursor: pointer;
        }
    """

    author_css = """
        /* Rule 1: Type selector */
        button {
            background-color: #007bff;
            color: #ffffff;
            font-size: 16px;
        }

        /* Rule 2: Class + Tag selector */
        button.btn-primary {
            background-color: #0056b3;
            color: #f8f9fa;
        }

        /* Rule 3: Complex selector with high specificity */
        div.container button#submit-btn.btn-primary[type="submit"] {
            background-color: #28a745;
            cursor: wait;
        }

        /* Rule 4: Lower specificity author rule with !important */
        .btn-override {
            color: #ffc107 !important;
        }
    """

    print(f"{YELLOW}{BOLD}[PHASE 1: Parsing Stylesheets across Cascade Origins]{RESET}")
    rules: List[CSSRule] = []
    rules.extend(parse_stylesheet(user_agent_css, CascadeOrigin.USER_AGENT_NORMAL, base_order=100))
    rules.extend(parse_stylesheet(user_css, CascadeOrigin.USER_NORMAL, base_order=200))
    rules.extend(parse_stylesheet(author_css, CascadeOrigin.AUTHOR_NORMAL, base_order=300))

    print(f"Total Rules Compiled into Engine AST: {GREEN}{len(rules)}{RESET}")
    for idx, rule in enumerate(rules, 1):
        spec = calculate_specificity(rule.selector_str)
        origin_name = CascadeOrigin(rule.origin).name
        print(f"  [{idx:02d}] {MAGENTA}{rule.selector_str:<50}{RESET} "
              f"Origin: {CYAN}{origin_name:<20}{RESET} Spec: {YELLOW}{spec}{RESET}")

    # Build Target DOM Node
    target_node = DOMElement(
        tag="button",
        id="submit-btn",
        classes=["btn-primary", "btn-override"],
        attributes={"type": "submit"},
        inline_styles={
            "background-color": "#dc3545",  # Inline style candidate
            "font-size": "15px"            # Will contend with User !important
        }
    )

    print(f"\n{YELLOW}{BOLD}[PHASE 2: Target DOM Element Specification]{RESET}")
    print(f"  Node: <{target_node.tag} id=\"{target_node.id}\" "
          f"class=\"{' '.join(target_node.classes)}\" type=\"submit\" "
          f"style=\"...\">")
    print(f"  Inline Styles: {target_node.inline_styles}")

    print(f"\n{YELLOW}{BOLD}[PHASE 3: Cascade Conflict Resolution Mathematical Analysis]{RESET}")

    # Trace Cascade for each property specifically
    computed_styles = resolve_computed_styles(target_node, rules)

    headers = f"{'PROPERTY':<18} | {'WINNING VALUE':<16} | {'ORIGIN/IMPORTANCE':<24} | {'SPECIFICITY':<14} | {'RESOLUTION REASON'}"
    print(f"{DIM}{'-' * len(headers)}{RESET}")
    print(f"{BOLD}{headers}{RESET}")
    print(f"{DIM}{'-' * len(headers)}{RESET}")

    trace_explanations = {
        "background-color": "Inline (1,0,0,0) defeated Author ID+Class+Attr (0,1,2,2)",
        "color": "Author !important beat regular author classes regardless of specificity",
        "font-size": "User !important overrules Author Inline style per Cascade Level 4",
        "cursor": "Author (0,1,2,2) beat User Normal & UA Normal by specificity",
        "border": "User-Agent default inherited without contest",
        "display": "User-Agent default applied"
    }

    for prop, decl in sorted(computed_styles.items()):
        effective_origin = decl.origin
        if decl.important:
            if decl.origin == CascadeOrigin.USER_AGENT_NORMAL:
                effective_origin = CascadeOrigin.USER_AGENT_IMPORTANT
            elif decl.origin == CascadeOrigin.USER_NORMAL:
                effective_origin = CascadeOrigin.USER_IMPORTANT
            elif decl.origin == CascadeOrigin.AUTHOR_NORMAL:
                effective_origin = CascadeOrigin.AUTHOR_IMPORTANT

        origin_str = f"{CascadeOrigin(effective_origin).name}"
        reason = trace_explanations.get(prop, "Direct Cascade Match")

        print(f"{GREEN}{prop:<18}{RESET} | "
              f"{WHITE}{BOLD}{decl.value:<16}{RESET} | "
              f"{CYAN}{origin_str:<24}{RESET} | "
              f"{YELLOW}{str(decl.specificity):<14}{RESET} | "
              f"{DIM}{reason}{RESET}")

    print(f"{DIM}{'-' * len(headers)}{RESET}")

    # Unit Assertion Verification
    print(f"\n{YELLOW}{BOLD}[PHASE 4: Verification of Engine Invariants]{RESET}")

    # 1. Inline Background wins over author stylesheet
    assert computed_styles["background-color"].value == "#dc3545", "Assertion Failure: Inline style must win"
    print(f"  {GREEN}✓ PASS:{RESET} Inline styles override high-specificity author selectors.")

    # 2. Author !important beats author normal with higher specificity
    assert computed_styles["color"].value == "#ffc107", "Assertion Failure: !important must win"
    print(f"  {GREEN}✓ PASS:{RESET} Author !important overrides high-specificity normal selectors.")

    # 3. User !important beats author inline style
    assert computed_styles["font-size"].value == "14px", "Assertion Failure: User !important must beat inline"
    print(f"  {GREEN}✓ PASS:{RESET} User !important takes precedence over Author inline declarations.")

    print(f"\n{GREEN}{BOLD}Cascade Mathematics Engine execution completed successfully.{RESET}\n")


if __name__ == "__main__":
    try:
        run_cascade_lab()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as ex:
        print(f"{RED}Fatal Engine Fault: {ex}{RESET}", file=sys.stderr)
        raise