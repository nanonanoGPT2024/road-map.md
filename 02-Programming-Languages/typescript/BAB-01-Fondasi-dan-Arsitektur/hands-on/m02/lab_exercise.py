#!/usr/bin/env python3
"""
Lab: TypeScript Core Semantics & Execution Architecture Deep Dive
Simulates the TypeScript compiler pipeline:
1. Lexical Scope & Symbol Resolution (Binder)
2. Structural Type System & Assignability Engine (Checker)
3. Type Erasure & Downlevel Transpilation (Emitter)
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Union

# --- Terminal ANSI Styling ---
class Style:
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

# --- Type System Representation ---
class TypeKind(Enum):
    ANY = auto()
    NEVER = auto()
    NUMBER = auto()
    STRING = auto()
    BOOLEAN = auto()
    OBJECT = auto()
    UNION = auto()

@dataclass
class Type:
    kind: TypeKind
    name: str

    def __str__(self) -> str:
        return self.name

@dataclass
class PropertySignature:
    name: str
    prop_type: Type
    optional: bool = False

@dataclass
class ObjectType(Type):
    properties: Dict[str, PropertySignature] = field(default_factory=dict)

    def __init__(self, name: str, properties: Dict[str, PropertySignature]):
        super().__init__(TypeKind.OBJECT, name)
        self.properties = properties

    def __str__(self) -> str:
        props = ", ".join(
            f"{p.name}{'?' if p.optional else ''}: {p.prop_type}"
            for p in self.properties.values()
        )
        return f"{{ {props} }}" if props else "{}"

@dataclass
class UnionType(Type):
    members: List[Type] = field(default_factory=list)

    def __init__(self, members: List[Type]):
        super().__init__(TypeKind.UNION, " | ".join(str(m) for m in members))
        self.members = members

# Built-in Primitive Singletons
TYPE_ANY = Type(TypeKind.ANY, "any")
TYPE_NEVER = Type(TypeKind.NEVER, "never")
TYPE_NUMBER = Type(TypeKind.NUMBER, "number")
TYPE_STRING = Type(TypeKind.STRING, "string")
TYPE_BOOLEAN = Type(TypeKind.BOOLEAN, "boolean")

# --- AST Node Definitions ---
@dataclass
class Node:
    line: int
    col: int

@dataclass
class Expression(Node):
    pass

@dataclass
class LiteralExpr(Expression):
    value: Union[int, float, str, bool]
    inferred_type: Type

@dataclass
class ObjectLiteralExpr(Expression):
    fields: Dict[str, Expression]

@dataclass
class IdentifierExpr(Expression):
    name: str

@dataclass
class Statement(Node):
    pass

@dataclass
class InterfaceDecl(Statement):
    name: str
    properties: Dict[str, PropertySignature]

@dataclass
class VarDecl(Statement):
    name: str
    type_annotation: Optional[Type]
    initializer: Expression
    is_const: bool = False

# --- Compiler Diagnostics ---
@dataclass
class Diagnostic:
    code: int
    message: str
    line: int
    col: int

    def format(self) -> str:
        return (f"{Style.RED}error TS{self.code}{Style.RESET}: "
                f"{self.message} {Style.DIM}(line {self.line}:{self.col}){Style.RESET}")

# --- TypeScript Type Checker (Structural Subtyping) ---
class TypeChecker:
    """
    Simulates TypeScript's Structural Assignability Rules:
    - S is assignable to T (S <: T) via duck typing / structural shapes.
    - Excess property checking applies during direct object literal assignments.
    - Union type handling: S <: (T1 | T2) if S <: T1 or S <: T2;
      (S1 | S2) <: T if S1 <: T and S2 <: T.
    """
    def __init__(self):
        self.diagnostics: List[Diagnostic] = []

    def check_assignable(self, source: Type, target: Type, node: Node, is_literal: bool = False) -> bool:
        # 1. Identity or Any
        if target.kind == TypeKind.ANY or source.kind == TypeKind.ANY:
            return True
        if source == target:
            return True

        # 2. Target is a Union Type (T1 | T2)
        if target.kind == TypeKind.UNION:
            assert isinstance(target, UnionType)
            for member in target.members:
                if self.check_assignable(source, member, node, is_literal=False):
                    return True
            self.diagnostics.append(Diagnostic(
                2322,
                f"Type '{source}' is not assignable to type '{target}'.",
                node.line, node.col
            ))
            return False

        # 3. Source is a Union Type (S1 | S2)
        if source.kind == TypeKind.UNION:
            assert isinstance(source, UnionType)
            for member in source.members:
                if not self.check_assignable(member, target, node, is_literal=False):
                    return False
            return True

        # 4. Structural Object Subtyping
        if target.kind == TypeKind.OBJECT and source.kind == TypeKind.OBJECT:
            assert isinstance(target, ObjectType)
            assert isinstance(source, ObjectType)

            # Excess Property Check (Direct object literals cannot specify unlisted properties)
            if is_literal:
                for src_prop in source.properties:
                    if src_prop not in target.properties:
                        self.diagnostics.append(Diagnostic(
                            2353,
                            f"Object literal may only specify known properties, and '{src_prop}' does not exist in type '{target.name}'.",
                            node.line, node.col
                        ))
                        return False

            # Check that source satisfies all target properties
            for prop_name, target_prop in target.properties.items():
                if prop_name not in source.properties:
                    if not target_prop.optional:
                        self.diagnostics.append(Diagnostic(
                            2741,
                            f"Property '{prop_name}' is missing in type '{source}' but required in type '{target.name}'.",
                            node.line, node.col
                        ))
                        return False
                else:
                    src_prop = source.properties[prop_name]
                    if not self.check_assignable(src_prop.prop_type, target_prop.prop_type, node, is_literal=False):
                        return False
            return True

        # Incompatible primitives
        self.diagnostics.append(Diagnostic(
            2322,
            f"Type '{source}' is not assignable to type '{target}'.",
            node.line, node.col
        ))
        return False

# --- Symbol Binder and Execution Pipeline ---
class TypeScriptCompilerPipeline:
    """
    Executes the multi-stage TypeScript architecture:
    Parse -> Bind Symbols -> Type Check -> Emit (Type Erasure & Downleveling)
    """
    def __init__(self):
        self.symbol_table: Dict[str, Type] = {}
        self.checker = TypeChecker()

    def bind_and_check(self, ast: List[Statement]):
        for stmt in ast:
            if isinstance(stmt, InterfaceDecl):
                # Bind type definition structurally
                obj_type = ObjectType(stmt.name, stmt.properties)
                self.symbol_table[stmt.name] = obj_type
            elif isinstance(stmt, VarDecl):
                # Infer or evaluate initializer type
                init_type, is_lit = self._infer_expr_type(stmt.initializer)
                target_type = stmt.type_annotation if stmt.type_annotation else init_type

                if stmt.type_annotation:
                    self.checker.check_assignable(init_type, target_type, stmt, is_literal=is_lit)

                self.symbol_table[stmt.name] = target_type

    def _infer_expr_type(self, expr: Expression) -> Tuple[Type, bool]:
        if isinstance(expr, LiteralExpr):
            return expr.inferred_type, True
        elif isinstance(expr, IdentifierExpr):
            if expr.name in self.symbol_table:
                return self.symbol_table[expr.name], False
            self.checker.diagnostics.append(Diagnostic(2304, f"Cannot find name '{expr.name}'.", expr.line, expr.col))
            return TYPE_ANY, False
        elif isinstance(expr, ObjectLiteralExpr):
            props = {}
            for k, v in expr.fields.items():
                t, _ = self._infer_expr_type(v)
                props[k] = PropertySignature(k, t)
            return ObjectType("anonymous", props), True
        return TYPE_ANY, False

    def emit_javascript(self, ast: List[Statement], target_es5: bool = True) -> str:
        """
        Emits clean JavaScript via Type Erasure.
        Optionally performs ES5 downleveling (e.g. const/let -> var).
        """
        lines = []
        for stmt in ast:
            if isinstance(stmt, InterfaceDecl):
                # Completely erased at runtime
                continue
            elif isinstance(stmt, VarDecl):
                var_keyword = "var" if target_es5 else ("const" if stmt.is_const else "let")
                init_str = self._emit_expr(stmt.initializer)
                lines.append(f"{var_keyword} {stmt.name} = {init_str};")
        return "\n".join(lines)

    def _emit_expr(self, expr: Expression) -> str:
        if isinstance(expr, LiteralExpr):
            return f"\"{expr.value}\"" if isinstance(expr.value, str) else str(expr.value).lower()
        elif isinstance(expr, IdentifierExpr):
            return expr.name
        elif isinstance(expr, ObjectLiteralExpr):
            inner = ", ".join(f"{k}: {self._emit_expr(v)}" for k, v in expr.fields.items())
            return f"{{ {inner} }}"
        return "undefined"

# --- Interactive Test Suite & Lab Harness ---
def run_lab():
    print(f"{Style.BOLD}{Style.CYAN}======================================================================{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN} TypeScript Compiler Architecture Deep Dive: Semantics & Type Erasure {Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}======================================================================{Style.RESET}\n")

    time.sleep(0.1)

    # 1. Define Declarations (Source Code Representation)
    # interface Point2D { x: number; y: number; }
    point2d_props = {
        "x": PropertySignature("x", TYPE_NUMBER),
        "y": PropertySignature("y", TYPE_NUMBER)
    }
    # interface Point3D { x: number; y: number; z: number; }
    point3d_props = {
        "x": PropertySignature("x", TYPE_NUMBER),
        "y": PropertySignature("y", TYPE_NUMBER),
        "z": PropertySignature("z", TYPE_NUMBER)
    }

    ast: List[Statement] = [
        InterfaceDecl(1, 1, "Point2D", point2d_props),
        InterfaceDecl(2, 1, "Point3D", point3d_props),
        
        # Valid assignment: Point3D is a structural subtype of Point2D
        # const p3d: Point3D = { x: 10, y: 20, z: 30 };
        VarDecl(3, 1, "p3d", ObjectType("Point3D", point3d_props), ObjectLiteralExpr(3, 22, {
            "x": LiteralExpr(3, 27, 10, TYPE_NUMBER),
            "y": LiteralExpr(3, 34, 20, TYPE_NUMBER),
            "z": LiteralExpr(3, 41, 30, TYPE_NUMBER)
        }), is_const=True),

        # Structural Assignability: p2d = p3d (Should PASS: Point3D has all props of Point2D)
        VarDecl(4, 1, "p2d", ObjectType("Point2D", point2d_props), IdentifierExpr(4, 22, "p3d")),

        # Semantic Error 1: Excess property check violation (Direct object literal assignment)
        # const pInvalid: Point2D = { x: 5, y: 10, extra: 42 };
        VarDecl(5, 1, "pInvalid", ObjectType("Point2D", point2d_props), ObjectLiteralExpr(5, 27, {
            "x": LiteralExpr(5, 29, 5, TYPE_NUMBER),
            "y": LiteralExpr(5, 35, 10, TYPE_NUMBER),
            "extra": LiteralExpr(5, 44, 42, TYPE_NUMBER)
        })),

        # Semantic Error 2: Type mismatch
        # const count: number = "not_a_number";
        VarDecl(6, 1, "count", TYPE_NUMBER, LiteralExpr(6, 23, "not_a_number", TYPE_STRING)),

        # Valid Union:
        # const id: number | string = 101;
        VarDecl(7, 1, "id", UnionType([TYPE_NUMBER, TYPE_STRING]), LiteralExpr(7, 31, 101, TYPE_NUMBER))
    ]

    print(f"{Style.YELLOW}[Stage 1] Executing Symbol Resolution & Structural Type Checker...{Style.RESET}")
    compiler = TypeScriptCompilerPipeline()
    compiler.bind_and_check(ast)

    if compiler.checker.diagnostics:
        print(f"\n{Style.RED}[!] Diagnostics emitted during type checking:{Style.RESET}")
        for diag in compiler.checker.diagnostics:
            print(f"  {diag.format()}")
    else:
        print(f"{Style.GREEN}[OK] No type errors encountered.{Style.RESET}")

    print(f"\n{Style.YELLOW}[Stage 2] Demonstrating Subtype Structural Verification:{Style.RESET}")
    t_2d = compiler.symbol_table["Point2D"]
    t_3d = compiler.symbol_table["Point3D"]
    
    # Test Point3D <: Point2D
    checker_probe = TypeChecker()
    is_sub = checker_probe.check_assignable(t_3d, t_2d, Node(0, 0))
    print(f"  • Shape(Point3D) <: Shape(Point2D)? -> {Style.GREEN if is_sub else Style.RED}{is_sub}{Style.RESET}")
    print(f"    {Style.DIM}TypeScript accepts this because Point3D has all members of Point2D.{Style.RESET}")

    # Test Point2D <: Point3D
    checker_probe_rev = TypeChecker()
    is_sub_rev = checker_probe_rev.check_assignable(t_2d, t_3d, Node(0, 0))
    print(f"  • Shape(Point2D) <: Shape(Point3D)? -> {Style.GREEN if is_sub_rev else Style.RED}{is_sub_rev}{Style.RESET}")
    print(f"    {Style.DIM}Point2D lacks member 'z', violating structural satisfaction.{Style.RESET}")

    print(f"\n{Style.YELLOW}[Stage 3] Emitting JavaScript Output (Type Erasure & Downleveling):{Style.RESET}")
    print(f"{Style.DIM}--- Compiled JavaScript Target (ES5) ---{Style.RESET}")
    js_code = compiler.emit_javascript(ast, target_es5=True)
    for line in js_code.splitlines():
        print(f"  {Style.GREEN}{line}{Style.RESET}")
    print(f"{Style.DIM}----------------------------------------{Style.RESET}")

    print(f"\n{Style.BOLD}{Style.WHITE}Execution Architecture Key Takeaways:{Style.RESET}")
    print(f"  1. {Style.CYAN}Structural Assignability{Style.RESET}: Types are checked purely based on shape/contracts, not nominal tags.")
    print(f"  2. {Style.CYAN}Type Erasure{Style.RESET}: Interfaces and type annotations exist strictly at compile time; runtime cost is zero.")
    print(f"  3. {Style.CYAN}Soundness vs Pragmatism{Style.RESET}: Excess property checks apply specifically to object literals to catch typos.")

if __name__ == "__main__":
    run_lab()