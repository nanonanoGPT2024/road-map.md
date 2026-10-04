#!/usr/bin/env python3
"""
Lab Exercise: Simulating TypeScript's Structural Typing Engine & Shape Contracts
Module: 02 - Structural Typing & Shape Contracts (TypeScript Deep Dive)

This script implements a lightweight TypeScript-style structural type checker.
It models:
1. Shape-based compatibility (Duck Typing / Width Subtyping).
2. Strict Excess Property Checks on object literals vs. reference assignments.
3. Recursive nested shape validation.
4. Readonly modifier and optional field contract enforcement.
"""

import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

# ==============================================================================
# ANSI Formatting Helpers
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

def print_header(title: str):
    print(f"\n{Color.BOLD}{Color.CYAN}{'='*70}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} [TS ENGINE] {title.upper()}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'='*70}{Color.RESET}")

def print_result(label: str, success: bool, reason: str = ""):
    status = f"{Color.GREEN}✔ ASSIGNABLE{Color.RESET}" if success else f"{Color.RED}✖ TYPE ERROR{Color.RESET}"
    print(f"  {Color.BOLD}{label:<35}{Color.RESET} -> {status}")
    if reason:
        print(f"    {Color.GRAY}tsc diagnostic: {reason}{Color.RESET}")


# ==============================================================================
# Type System Models (Shape Contracts)
# ==============================================================================
class BaseKind(Enum):
    PRIMITIVE = auto()
    INTERFACE = auto()

@dataclass
class TypeContract:
    name: str
    kind: BaseKind

@dataclass
class PrimitiveType(TypeContract):
    def __init__(self, name: str):
        super().__init__(name=name, kind=BaseKind.PRIMITIVE)

    def __repr__(self):
        return self.name

# Built-in Primitive Singletons
TS_NUMBER = PrimitiveType("number")
TS_STRING = PrimitiveType("string")
TS_BOOLEAN = PrimitiveType("boolean")

@dataclass
class PropertySignature:
    """Represents property constraints on a TypeScript interface."""
    prop_type: TypeContract
    optional: bool = False
    readonly: bool = False

@dataclass
class InterfaceType(TypeContract):
    """Represents an object contract (Structural Shape)."""
    fields: Dict[str, PropertySignature] = field(default_factory=dict)

    def __init__(self, name: str, fields: Dict[str, PropertySignature]):
        super().__init__(name=name, kind=BaseKind.INTERFACE)
        self.fields = fields

    def __repr__(self):
        body = ", ".join(
            f"{'readonly ' if p.readonly else ''}{k}{'?' if p.optional else ''}: {p.prop_type.name}"
            for k, p in self.fields.items()
        )
        return f"{self.name} {{ {body} }}"


# ==============================================================================
# Structural Compatibility & Assignment Engine
# ==============================================================================
class StructuralTypeEngine:
    """
    Evaluates subtyping and structural compatibility mimicking 'tsc' behaviour.
    """

    @staticmethod
    def check_assignment(
        source: TypeContract,
        target: TypeContract,
        is_literal_assignment: bool = False
    ) -> Tuple[bool, str]:
        """
        Determines whether 'source' can be assigned to 'target' (source :> target).
        Implements:
          - Primitive exact matching.
          - Structural width subtyping (source must contain at least all required fields of target).
          - Depth subtyping (nested field compatibility).
          - Excess property checking if assigned directly via object literal.
        """
        # 1. Identity Check
        if source == target:
            return True, ""

        # 2. Primitive Assignment Rules
        if source.kind == BaseKind.PRIMITIVE or target.kind == BaseKind.PRIMITIVE:
            if source.name != target.name:
                return False, f"Type '{source.name}' is not assignable to type '{target.name}'."
            return True, ""

        # 3. Interface vs Interface (Structural Compatibility)
        if isinstance(source, InterfaceType) and isinstance(target, InterfaceType):
            target_fields = target.fields
            source_fields = source.fields

            # A. Strict Excess Property Checks for Literals
            # TypeScript rejects unknown properties ONLY when initializing via direct object literal
            if is_literal_assignment:
                for src_key in source_fields:
                    if src_key not in target_fields:
                        return False, (
                            f"Object literal may only specify known properties, "
                            f"and '{src_key}' does not exist in type '{target.name}'."
                        )

            # B. Required Fields Verification
            for tgt_key, tgt_sig in target_fields.items():
                if tgt_key not in source_fields:
                    if not tgt_sig.optional:
                        return False, (
                            f"Property '{tgt_key}' is missing in type '{source.name}' "
                            f"but required in type '{target.name}'."
                        )
                    continue

                src_sig = source_fields[tgt_key]

                # C. Deep recursive structural check
                ok, err = StructuralTypeEngine.check_assignment(
                    src_sig.prop_type,
                    tgt_sig.prop_type,
                    is_literal_assignment=False
                )
                if not ok:
                    return False, f"Types of property '{tgt_key}' are incompatible: {err}"

            return True, ""

        return False, f"Type '{source.name}' is incompatible with '{target.name}'."


# ==============================================================================
# Lab Scenarios & Demonstrations
# ==============================================================================
def run_lab():
    engine = StructuralTypeEngine()

    # Define Contracts
    Point2D = InterfaceType("Point2D", {
        "x": PropertySignature(TS_NUMBER),
        "y": PropertySignature(TS_NUMBER),
    })

    Point3D = InterfaceType("Point3D", {
        "x": PropertySignature(TS_NUMBER),
        "y": PropertySignature(TS_NUMBER),
        "z": PropertySignature(TS_NUMBER),
    })

    Point1D = InterfaceType("Point1D", {
        "x": PropertySignature(TS_NUMBER),
    })

    # SCENARIO 1: Basic Width Subtyping (Shape Conformance)
    print_header("Scenario 1: Structural Equivalence & Width Subtyping")
    print(f"Target: {Point2D}")
    print(f"Source A: {Point3D}")
    print(f"Source B: {Point1D}\n")

    # Point3D -> Point2D (Should pass: Point3D has x, y, and extra z)
    ok, err = engine.check_assignment(Point3D, Point2D, is_literal_assignment=False)
    print_result("Assign (Point3D -> Point2D)", ok, err)

    # Point1D -> Point2D (Should fail: Missing required property 'y')
    ok, err = engine.check_assignment(Point1D, Point2D, is_literal_assignment=False)
    print_result("Assign (Point1D -> Point2D)", ok, err)

    # SCENARIO 2: Excess Property Checking (Freshness)
    print_header("Scenario 2: Excess Property Checks (Fresh Literal vs Reference)")
    print("TypeScript applies strict excess checking to inline object literals to prevent typos.\n")

    LiteralWithZ = InterfaceType("{ x: number, y: number, z: number }", {
        "x": PropertySignature(TS_NUMBER),
        "y": PropertySignature(TS_NUMBER),
        "z": PropertySignature(TS_NUMBER),
    })

    # Variable reference assignment: const p: Point2D = point3DInstance (Allowed)
    ok, err = engine.check_assignment(LiteralWithZ, Point2D, is_literal_assignment=False)
    print_result("Via Intermediate Variable Ref", ok, err)

    # Direct literal assignment: const p: Point2D = { x: 1, y: 2, z: 3 } (Disallowed)
    ok, err = engine.check_assignment(LiteralWithZ, Point2D, is_literal_assignment=True)
    print_result("Via Fresh Object Literal", ok, err)

    # SCENARIO 3: Deep Nested Structural Verification
    print_header("Scenario 3: Deep Recursive Structural Verification")

    AddressSchema = InterfaceType("Address", {
        "street": PropertySignature(TS_STRING),
        "zipCode": PropertySignature(TS_NUMBER),
    })

    UserSchema = InterfaceType("User", {
        "id": PropertySignature(TS_STRING),
        "address": PropertySignature(AddressSchema),
    })

    # Compatible structurally, even with nominal name variance
    ClientAddress = InterfaceType("ClientAddress", {
        "street": PropertySignature(TS_STRING),
        "zipCode": PropertySignature(TS_NUMBER),
        "country": PropertySignature(TS_STRING, optional=True),
    })

    ClientPayload = InterfaceType("ClientPayload", {
        "id": PropertySignature(TS_STRING),
        "address": PropertySignature(ClientAddress),
        "extraFlag": PropertySignature(TS_BOOLEAN, optional=True),
    })

    InvalidClientPayload = InterfaceType("InvalidClientPayload", {
        "id": PropertySignature(TS_STRING),
        "address": InterfaceType("CorruptAddress", {
            "street": PropertySignature(TS_STRING),
            "zipCode": PropertySignature(TS_STRING), # Incompatible type!
        }),
    })

    ok, err = engine.check_assignment(ClientPayload, UserSchema, is_literal_assignment=False)
    print_result("Nested ClientPayload -> User", ok, err)

    ok, err = engine.check_assignment(InvalidClientPayload, UserSchema, is_literal_assignment=False)
    print_result("Invalid Nested Payload -> User", ok, err)

    # SCENARIO 4: Optional Property Handling
    print_header("Scenario 4: Optional Fields & Shape Relaxation")

    ConfigContract = InterfaceType("DatabaseConfig", {
        "host": PropertySignature(TS_STRING),
        "port": PropertySignature(TS_NUMBER, optional=True),
        "ssl": PropertySignature(TS_BOOLEAN, optional=True),
    })

    MinimalConfig = InterfaceType("MinimalConfig", {
        "host": PropertySignature(TS_STRING),
    })

    print(f"Target: {ConfigContract}")
    print(f"Source: {MinimalConfig}\n")

    ok, err = engine.check_assignment(MinimalConfig, ConfigContract, is_literal_assignment=False)
    print_result("MinimalConfig -> DatabaseConfig", ok, err)

    print(f"\n{Color.BOLD}{Color.GREEN}Lab 02 Diagnostic Simulation Completed Successfully.{Color.RESET}\n")

if __name__ == "__main__":
    run_lab()