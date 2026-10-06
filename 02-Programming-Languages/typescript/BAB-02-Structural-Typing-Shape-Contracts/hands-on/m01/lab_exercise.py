#!/usr/bin/env python3
"""
Lab Exercise: Structural Typing & Shape Contracts Simulation (TypeScript BAB-02)
Simulates TypeScript's compile-time structural type system, excess property checks,
and duck typing mechanics using Python 3 with ANSI terminal colors.
"""

import sys
import time
from typing import Dict, Any, List, Optional, Tuple

# --- ANSI Color Palette ---
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BG_DARK = "\033[40m"
    WHITE = "\033[97m"

def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}======================================================================
  TYPESCRIPT TYPE SYSTEM LAB: STRUCTURAL TYPING & SHAPE CONTRACTS
======================================================================{Colors.RESET}
{Colors.DIM}Simulating: Shape Compatibility, Nominal vs Structural, & Excess Property Checks{Colors.RESET}
"""
    print(banner)

def print_header(title: str):
    print(f"\n{Colors.YELLOW}{Colors.BOLD}>>> {title}{Colors.RESET}")
    print(f"{Colors.DIM}{'-' * 65}{Colors.RESET}")

def print_ts_snippet(code: str):
    print(f"{Colors.BG_DARK}{Colors.WHITE}")
    for line in code.strip().split("\n"):
        print(f"  {line}")
    print(f"{Colors.RESET}")

# --- Type System Definitions ---
class TypeContract:
    def __init__(self, name: str, schema: Dict[str, type]):
        self.name = name
        self.schema = schema

    def inspect(self) -> str:
        fields = ", ".join(f"{k}: {v.__name__}" for k, v in self.schema.items())
        return f"{Colors.MAGENTA}interface {self.name}{Colors.RESET} {{ {fields} }}"

def check_structural_compatibility(
    target_contract: TypeContract,
    candidate_obj: Dict[str, Any],
    is_literal: bool = False
) -> Tuple[bool, List[str]]:
    """
    Simulates TypeScript structural type checking.
    - Candidate must satisfy all fields of target_contract (Subtype / Shape match).
    - If is_literal=True (Fresh Object Literal), TypeScript enforces Excess Property Check.
    """
    errors = []
    
    # 1. Missing or Mismatched Properties (Contract Satisfaction)
    for prop, expected_type in target_contract.schema.items():
        if prop not in candidate_obj:
            errors.append(f"Property '{prop}' is missing in type '{type_shape_repr(candidate_obj)}' but required in '{target_contract.name}'.")
        else:
            val = candidate_obj[prop]
            if not isinstance(val, expected_type):
                actual_type = type(val).__name__
                errors.append(f"Type '{actual_type}' is not assignable to type '{expected_type.__name__}' for property '{prop}'.")

    # 2. Excess Property Check (Only triggers on fresh object literals)
    if is_literal:
        for prop in candidate_obj.keys():
            if prop not in target_contract.schema:
                errors.append(
                    f"Object literal may only specify known properties, and '{prop}' does not exist in type '{target_contract.name}'. "
                    f"{Colors.DIM}(Excess Property Check triggered){Colors.RESET}"
                )

    is_valid = len(errors) == 0
    return is_valid, errors

def type_shape_repr(obj: Dict[str, Any]) -> str:
    props = ", ".join(f"{k}: {type(v).__name__}" for k, v in obj.items())
    return f"{{ {props} }}"

# --- Interactive Modules ---

def demo_structural_vs_nominal():
    print_header("Module 1: Nominal vs Structural Typing (Duck Typing at Compile-Time)")
    print(f"{Colors.CYAN}In Java/C# (Nominal):{Colors.RESET} Class name must explicitly match.")
    print(f"{Colors.CYAN}In TypeScript (Structural):{Colors.RESET} If it has the right shape, it's accepted!\n")

    point2d = TypeContract("Point2D", {"x": int, "y": int})
    print(f"Target Contract: {point2d.inspect()}\n")

    objects = [
        ("Identical Match", {"x": 10, "y": 20}, False),
        ("Superset Object (Point3D Shape)", {"x": 10, "y": 20, "z": 30}, False),
        ("Car Object with matching x,y coords", {"x": 50, "y": 100, "brand": "Tesla"}, False),
        ("Broken Object (Missing y)", {"x": 10}, False),
        ("Mismatched Type (y is str)", {"x": 10, "y": "twenty"}, False),
    ]

    for label, obj, is_literal in objects:
        valid, errors = check_structural_compatibility(point2d, obj, is_literal)
        status = f"{Colors.GREEN}[COMPATIBLE / TYPE OK]{Colors.RESET}" if valid else f"{Colors.RED}[TYPE ERROR]{Colors.RESET}"
        print(f"Object: {Colors.BOLD}{label}{Colors.RESET}")
        print(f"  Shape: {type_shape_repr(obj)}")
        print(f"  Result: {status}")
        if not valid:
            for err in errors:
                print(f"    {Colors.RED}✖ {err}{Colors.RESET}")
        print()

def demo_excess_property_checks():
    print_header("Module 2: The Freshness Mystery (Excess Property Checks)")
    print("Why does TypeScript allow extra properties via variable reference,")
    print("but throws a compiler error on direct object literals?\n")

    user_contract = TypeContract("UserProfile", {"id": int, "username": str})
    print(f"Target Contract: {user_contract.inspect()}\n")

    raw_data = {"id": 101, "username": "alice_dev", "isAdmin": True}

    print(f"{Colors.BOLD}Case A: Direct Fresh Object Literal Assignment{Colors.RESET}")
    print_ts_snippet("""
const user: UserProfile = {
  id: 101,
  username: "alice_dev",
  isAdmin: true // Error: Object literal may only specify known properties!
};
    """)
    valid_a, errs_a = check_structural_compatibility(user_contract, raw_data, is_literal=True)
    print(f"Compiler Output: {Colors.RED}[FAIL]{Colors.RESET}")
    for err in errs_a:
        print(f"  {Colors.RED}✖ {err}{Colors.RESET}")
    print()

    print(f"{Colors.BOLD}Case B: Assigning through Intermediate Variable Reference{Colors.RESET}")
    print_ts_snippet("""
const rawData = { id: 101, username: "alice_dev", isAdmin: true };
const user: UserProfile = rawData; // OK! TypeScript allows superset shape!
    """)
    valid_b, _ = check_structural_compatibility(user_contract, raw_data, is_literal=False)
    status_b = f"{Colors.GREEN}[PASS - Structural Subtyping Satisfied]{Colors.RESET}" if valid_b else "[FAIL]"
    print(f"Compiler Output: {status_b}")
    print(f"{Colors.DIM}Rationale: Prevents developer typos in literals while preserving open-world polymorphism.{Colors.RESET}\n")

def interactive_sandbox():
    print_header("Module 3: Interactive Structural Type Evaluator")
    print("Define an object shape and test it against a TypeScript Contract.")
    
    contract = TypeContract("ProductContract", {"sku": str, "price": int, "inStock": bool})
    print(f"Active Interface: {contract.inspect()}\n")

    test_samples = [
        ("Valid Standard Product", {"sku": "PROD-01", "price": 45000, "inStock": True}),
        ("Valid Extra Metadata (Assigned Var)", {"sku": "PROD-02", "price": 12000, "inStock": True, "discount": 0.1}),
        ("Typo in Literal (in_stock instead of inStock)", {"sku": "PROD-03", "price": 5000, "in_stock": True}),
        ("Invalid Price Type (float instead of int)", {"sku": "PROD-04", "price": 99.9, "inStock": True}),
    ]

    for idx, (desc, sample) in enumerate(test_samples, 1):
        print(f"{Colors.BOLD}[Sample {idx}] {desc}{Colors.RESET}")
        print(f"Data: {sample}")
        
        # Test as literal
        lit_ok, lit_errs = check_structural_compatibility(contract, sample, is_literal=True)
        # Test as variable reference
        ref_ok, ref_errs = check_structural_compatibility(contract, sample, is_literal=False)

        print(f"  As Direct Literal : {'✔ ' + Colors.GREEN + 'VALID' if lit_ok else '✖ ' + Colors.RED + 'TYPE ERROR'}{Colors.RESET}")
        if not lit_ok:
            for e in lit_errs:
                print(f"     {Colors.RED}→ {e}{Colors.RESET}")

        print(f"  As Variable Ref   : {'✔ ' + Colors.GREEN + 'VALID' if ref_ok else '✖ ' + Colors.RED + 'TYPE ERROR'}{Colors.RESET}")
        if not ref_ok:
            for e in ref_errs:
                print(f"     {Colors.RED}→ {e}{Colors.RESET}")
        print()

def run_lab_quiz():
    print_header("Module 4: Mini Assessment (Knowledge Check)")
    questions = [
        {
            "q": "1. What is the fundamental difference between Nominal and Structural typing?",
            "options": [
                "A) Nominal compares explicit type names; Structural compares internal shapes/properties.",
                "B) Nominal is compile-time; Structural is runtime only.",
                "C) TypeScript is nominal; Java is structural.",
            ],
            "answer": "A",
            "explanation": "TypeScript uses structural typing: if two objects have matching shapes, they are compatible regardless of class names."
        },
        {
            "q": "2. Why does TypeScript perform Excess Property Checks on fresh object literals?",
            "options": [
                "A) To forbid subtyping entirely in TypeScript.",
                "B) To catch accidental typos and unused properties that would otherwise silently pass.",
                "C) Because JavaScript objects cannot hold more than 3 properties.",
            ],
            "answer": "B",
            "explanation": "Fresh object literals cannot be reused elsewhere; having excess properties is almost always an accidental typo."
        }
    ]

    for item in questions:
        print(f"{Colors.BOLD}{item['q']}{Colors.RESET}")
        for opt in item['options']:
            print(f"  {opt}")
        print(f"  {Colors.GREEN}{Colors.BOLD}Answer: {item['answer']}{Colors.RESET}")
        print(f"  {Colors.CYAN}Explanation: {item['explanation']}{Colors.RESET}\n")

def main():
    print_banner()
    demo_structural_vs_nominal()
    time.sleep(0.3)
    demo_excess_property_checks()
    time.sleep(0.3)
    interactive_sandbox()
    time.sleep(0.3)
    run_lab_quiz()
    print(f"{Colors.GREEN}{Colors.BOLD}✔ Simulation Completed Successfully! All contracts and checks verified.{Colors.RESET}\n")

if __name__ == "__main__":
    main()
