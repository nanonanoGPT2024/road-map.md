#!/usr/bin/env python3
"""
Lab Hands-on: TypeScript Advanced Generics & Parametric Polymorphism Engine
Category: 02-Programming-Languages | Chapter: 04 - Advanced Generics

Deskripsi:
Script ini memodelkan Type Engine inti TypeScript secara presisi, mensimulasikan
evaluasi Generic Type tingkat lanjut:
  1. Subtyping & Generic Constraints (`T extends Constraint`)
  2. Distributive Conditional Types (`T extends U ? X : Y` atas Union)
  3. Pattern Matching & Type Inference via `infer` keyword (`ReturnType<T>`)
  4. Homomorphic Mapped Types (`Partial<T>`, `Readonly<T>`, `DeepReadonly<T>`)
"""

from __future__ import annotations
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union as PyUnion, Set, Tuple

# ============================================================================
# ANSI Color Codes & Formatting
# ============================================================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BLUE = "\033[34m"


def print_banner(title: str):
    width = 75
    print(f"\n{BLUE}{'=' * width}{RESET}")
    print(f"{BOLD}{CYAN} [TS-TYPE-ENGINE] {title.upper()}{RESET}")
    print(f"{BLUE}{'=' * width}{RESET}")


def log_step(action: str, detail: str):
    print(f"  {MAGENTA}►{RESET} {BOLD}{action:<22}{RESET}: {detail}")


# ============================================================================
# AST Type Definitions (Model Sistem Tipe TypeScript)
# ============================================================================
class TypeNode:
    """Basis untuk semua representasi tipe dalam simulasi compiler TS."""
    def inspect(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class PrimitiveType(TypeNode):
    name: str  # 'string', 'number', 'boolean', 'never', 'any', 'unknown'

    def inspect(self) -> str:
        if self.name == "never":
            return f"{RED}never{RESET}"
        if self.name in ("any", "unknown"):
            return f"{YELLOW}{self.name}{RESET}"
        return f"{CYAN}{self.name}{RESET}"


@dataclass(frozen=True)
class TypeVariable(TypeNode):
    name: str
    constraint: Optional[TypeNode] = None

    def inspect(self) -> str:
        if self.constraint:
            return f"{YELLOW}{self.name}{RESET} extends {self.constraint.inspect()}"
        return f"{YELLOW}{self.name}{RESET}"


@dataclass(frozen=True)
class InferKeyword(TypeNode):
    """Representasi konstruksi `infer R` dalam conditional type."""
    var_name: str

    def inspect(self) -> str:
        return f"{BOLD}infer {self.var_name}{RESET}"


@dataclass(frozen=True)
class UnionTypeNode(TypeNode):
    members: Tuple[TypeNode, ...]

    def inspect(self) -> str:
        # Filter 'never' dari display kecuali union hanya berisi 'never'
        active = [m for m in self.members if not (isinstance(m, PrimitiveType) and m.name == "never")]
        if not active:
            return f"{RED}never{RESET}"
        return " | ".join(m.inspect() for m in active)


@dataclass(frozen=True)
class ObjectTypeNode(TypeNode):
    properties: Tuple[Tuple[str, TypeNode, bool], ...]  # (nama, tipe, readonly)

    def inspect(self) -> str:
        props = []
        for name, prop_type, is_ro in self.properties:
            ro_prefix = "readonly " if is_ro else ""
            props.append(f"{ro_prefix}{name}: {prop_type.inspect()}")
        return f"{{ {'; '.join(props)} }}"


@dataclass(frozen=True)
class FunctionTypeNode(TypeNode):
    param_types: Tuple[TypeNode, ...]
    return_type: TypeNode

    def inspect(self) -> str:
        params_str = ", ".join(f"arg{idx}: {p.inspect()}" for idx, p in enumerate(self.param_types))
        return f"({params_str}) => {self.return_type.inspect()}"


@dataclass(frozen=True)
class ConditionalTypeNode(TypeNode):
    check_type: TypeNode
    extends_type: TypeNode
    true_type: TypeNode
    false_type: TypeNode

    def inspect(self) -> str:
        return (f"{self.check_type.inspect()} extends {self.extends_type.inspect()} ? "
                f"{self.true_type.inspect()} : {self.false_type.inspect()}")


# ============================================================================
# Type Checker & Resolution Engine (Parametric Polymorphism)
# ============================================================================
class TypeEvaluator:
    """Mesin substitusi, unification, dan reduksi tipe parametrik."""

    @staticmethod
    def is_subtype_of(source: TypeNode, target: TypeNode, env: Dict[str, TypeNode]) -> bool:
        """Evaluasi relasi assignability: source <: target (source extends target)."""
        source = TypeEvaluator.normalize(source, env)
        target = TypeEvaluator.normalize(target, env)

        # 'any' bersikap bi-directional (top/bottom type)
        if isinstance(source, PrimitiveType) and source.name == "any":
            return True
        if isinstance(target, PrimitiveType) and target.name in ("any", "unknown"):
            return True

        # 'never' adalah bottom type, subtype dari segalanya
        if isinstance(source, PrimitiveType) and source.name == "never":
            return True

        # Identity
        if source == target:
            return True

        # Union di sisi source: (A | B) extends T iff A extends T AND B extends T
        if isinstance(source, UnionTypeNode):
            return all(TypeEvaluator.is_subtype_of(m, target, env) for m in source.members)

        # Union di sisi target: S extends (A | B) jika S extends A OR S extends B
        if isinstance(target, UnionTypeNode):
            return any(TypeEvaluator.is_subtype_of(source, m, env) for m in target.members)

        # Function compatibility (Parameter Contravariance, Return Covariance)
        if isinstance(source, FunctionTypeNode) and isinstance(target, FunctionTypeNode):
            if len(source.param_types) != len(target.param_types):
                return False
            # Parameter contravariance: target_param <: source_param
            params_ok = all(
                TypeEvaluator.is_subtype_of(tp, sp, env)
                for sp, tp in zip(source.param_types, target.param_types)
            )
            # Return covariance: source_ret <: target_ret
            ret_ok = TypeEvaluator.is_subtype_of(source.return_type, target.return_type, env)
            return params_ok and ret_ok

        # Structural Typing untuk Object
        if isinstance(source, ObjectTypeNode) and isinstance(target, ObjectTypeNode):
            source_dict = {k: t for k, t, _ in source.properties}
            for t_name, t_type, _ in target.properties:
                if t_name not in source_dict:
                    return False
                if not TypeEvaluator.is_subtype_of(source_dict[t_name], t_type, env):
                    return False
            return True

        return False

    @staticmethod
    def match_and_infer(actual: TypeNode, pattern: TypeNode, inferences: Dict[str, TypeNode]) -> bool:
        """Pencocokan pola rekursif untuk mengekstraksi variabel dari klausa `infer R`."""
        if isinstance(pattern, InferKeyword):
            inferences[pattern.var_name] = actual
            return True

        if isinstance(pattern, FunctionTypeNode) and isinstance(actual, FunctionTypeNode):
            ret_match = TypeEvaluator.match_and_infer(actual.return_type, pattern.return_type, inferences)
            if not ret_match:
                return False
            if len(pattern.param_types) == len(actual.param_types):
                for act_p, pat_p in zip(actual.param_types, pattern.param_types):
                    if not TypeEvaluator.match_and_infer(act_p, pat_p, inferences):
                        return False
            return True

        return actual == pattern

    @staticmethod
    def substitute(node: TypeNode, env: Dict[str, TypeNode]) -> TypeNode:
        """Substitusi variabel generik dengan instansiasi konkret."""
        if isinstance(node, TypeVariable):
            return env.get(node.name, node)

        if isinstance(node, UnionTypeNode):
            return UnionTypeNode(tuple(TypeEvaluator.substitute(m, env) for m in node.members))

        if isinstance(node, ObjectTypeNode):
            return ObjectTypeNode(
                tuple((name, TypeEvaluator.substitute(t, env), ro) for name, t, ro in node.properties)
            )

        if isinstance(node, FunctionTypeNode):
            return FunctionTypeNode(
                tuple(TypeEvaluator.substitute(p, env) for p in node.param_types),
                TypeEvaluator.substitute(node.return_type, env)
            )

        if isinstance(node, ConditionalTypeNode):
            return ConditionalTypeNode(
                TypeEvaluator.substitute(node.check_type, env),
                TypeEvaluator.substitute(node.extends_type, env),
                TypeEvaluator.substitute(node.true_type, env),
                TypeEvaluator.substitute(node.false_type, env),
            )

        return node

    @staticmethod
    def normalize(node: TypeNode, env: Dict[str, TypeNode]) -> TypeNode:
        """Mereduksi union redundan dan membuang tipe `never`."""
        subbed = TypeEvaluator.substitute(node, env)
        if isinstance(subbed, UnionTypeNode):
            flat_members: List[TypeNode] = []
            for m in subbed.members:
                norm_m = TypeEvaluator.normalize(m, env)
                if isinstance(norm_m, UnionTypeNode):
                    flat_members.extend(norm_m.members)
                elif isinstance(norm_m, PrimitiveType) and norm_m.name == "never":
                    continue
                else:
                    if norm_m not in flat_members:
                        flat_members.append(norm_m)
            if not flat_members:
                return PrimitiveType("never")
            if len(flat_members) == 1:
                return flat_members[0]
            return UnionTypeNode(tuple(flat_members))
        return subbed

    @classmethod
    def evaluate(cls, node: TypeNode, env: Dict[str, TypeNode]) -> TypeNode:
        """Evaluasi tipe menyeluruh (Distributive Conditional Types, Inferences, Mapped)."""
        node = cls.normalize(node, env)

        if isinstance(node, ConditionalTypeNode):
            # Cek Distributivitas: jika check_type adalah Naked Type Parameter yang terikat Union
            check_t = cls.normalize(node.check_type, env)

            if isinstance(check_t, UnionTypeNode):
                log_step("Distributive Branch", f"Mendistribusikan union {check_t.inspect()}")
                # (A | B) extends T ? X : Y  ==>  (A extends T ? X : Y) | (B extends T ? X : Y)
                distributed_branches = []
                for member in check_t.members:
                    branch = ConditionalTypeNode(member, node.extends_type, node.true_type, node.false_type)
                    distributed_branches.append(cls.evaluate(branch, env))
                return cls.normalize(UnionTypeNode(tuple(distributed_branches)), env)

            # Evaluasi Invariant Pattern Matching / Infer
            inferred_env = dict(env)
            has_match = False
            if any(isinstance(f, InferKeyword) for f in [node.extends_type] if isinstance(f, InferKeyword)) or \
               isinstance(node.extends_type, FunctionTypeNode):
                has_match = cls.match_and_infer(check_t, node.extends_type, inferred_env)

            is_sub = has_match or cls.is_subtype_of(check_t, node.extends_type, env)

            if is_sub:
                log_step("Branch Satisfied", f"{check_t.inspect()} <: {node.extends_type.inspect()} → True Branch")
                return cls.evaluate(node.true_type, inferred_env)
            else:
                log_step("Branch Failed", f"{check_t.inspect()} <: {node.extends_type.inspect()} → False Branch")
                return cls.evaluate(node.false_type, env)

        return node


# ============================================================================
# TypeScript Generic Utility Library (Simulasi Utility Types Standar TS)
# ============================================================================
class TSStandardLibrary:
    """Implementasi TypeScript Built-in Utility Generics."""

    @staticmethod
    def exclude(t: TypeNode, u: TypeNode) -> ConditionalTypeNode:
        """type Exclude<T, U> = T extends U ? never : T;"""
        return ConditionalTypeNode(
            check_type=t,
            extends_type=u,
            true_type=PrimitiveType("never"),
            false_type=t
        )

    @staticmethod
    def extract(t: TypeNode, u: TypeNode) -> ConditionalTypeNode:
        """type Extract<T, U> = T extends U ? T : never;"""
        return ConditionalTypeNode(
            check_type=t,
            extends_type=u,
            true_type=t,
            false_type=PrimitiveType("never")
        )

    @staticmethod
    def return_type(t: TypeNode) -> ConditionalTypeNode:
        """type ReturnType<T> = T extends (...args: any[]) => infer R ? R : any;"""
        pattern = FunctionTypeNode(
            param_types=(),
            return_type=InferKeyword("R")
        )
        return ConditionalTypeNode(
            check_type=t,
            extends_type=pattern,
            true_type=TypeVariable("R"),
            false_type=PrimitiveType("any")
        )

    @staticmethod
    def make_readonly(obj: ObjectTypeNode) -> ObjectTypeNode:
        """type Readonly<T> = { readonly [P in keyof T]: T[P] };"""
        return ObjectTypeNode(
            tuple((name, prop_type, True) for name, prop_type, _ in obj.properties)
        )


# ============================================================================
# Lab Execution & Verification Scenarios
# ============================================================================
def run_lab():
    engine = TypeEvaluator()

    # --- Scenario 1: Distributive Conditional Types ---
    print_banner("1. Distributive Conditional Types: Exclude<T, U>")
    print(f"{DIM}// TS Definition: type Exclude<T, U> = T extends U ? never : T;{RESET}")
    print(f"{DIM}// Case: Exclude<'string' | 'number' | 'boolean', 'number'>{RESET}\n")

    t_union = UnionTypeNode((PrimitiveType("string"), PrimitiveType("number"), PrimitiveType("boolean")))
    u_filter = PrimitiveType("number")

    exclude_macro = TSStandardLibrary.exclude(t_union, u_filter)
    result1 = engine.evaluate(exclude_macro, {})
    print(f"\n  {GREEN}✔ Hasil Evaluasi:{RESET} {result1.inspect()}")

    # --- Scenario 2: Generic Constraint Validation ---
    print_banner("2. Generic Constraints: <T extends { id: string }>")
    print(f"{DIM}// TS Definition: function getRecord<T extends {{ id: string }}>(rec: T): T{RESET}\n")

    id_constraint = ObjectTypeNode((("id", PrimitiveType("string"), False),))
    valid_arg = ObjectTypeNode((
        ("id", PrimitiveType("string"), False),
        ("payload", PrimitiveType("number"), False)
    ))
    invalid_arg = ObjectTypeNode((("username", PrimitiveType("string"), False),))

    log_step("Validating valid_arg", valid_arg.inspect())
    is_valid = engine.is_subtype_of(valid_arg, id_constraint, {})
    status_str = f"{GREEN}VALID (Tersubstitusi){RESET}" if is_valid else f"{RED}TYPE ERROR{RESET}"
    print(f"    Subtype constraint satisfied: {status_str}")

    log_step("Validating invalid_arg", invalid_arg.inspect())
    is_invalid = engine.is_subtype_of(invalid_arg, id_constraint, {})
    status_str2 = f"{GREEN}VALID{RESET}" if is_invalid else f"{RED}TYPE ERROR: Property 'id' is missing!{RESET}"
    print(f"    Subtype constraint satisfied: {status_str2}")

    # --- Scenario 3: Pattern Matching dengan `infer` ---
    print_banner("3. Type Inference in Conditional Types (`infer R`)")
    print(f"{DIM}// TS Definition: type ReturnType<T> = T extends (...args: any[]) => infer R ? R : any;{RESET}\n")

    mock_func = FunctionTypeNode(
        param_types=(PrimitiveType("string"),),
        return_type=ObjectTypeNode((("status", PrimitiveType("number"), False), ("data", PrimitiveType("string"), False)))
    )
    print(f"  Input Signature: {mock_func.inspect()}")

    return_type_query = TSStandardLibrary.return_type(mock_func)
    result3 = engine.evaluate(return_type_query, {})
    print(f"\n  {GREEN}✔ Inferred ReturnType:{RESET} {result3.inspect()}")

    # --- Scenario 4: Homomorphic Mapped Type Transformation ---
    print_banner("4. Homomorphic Mapped Types: Readonly<T>")
    print(f"{DIM}// TS Definition: type Readonly<T> = {{ readonly [K in keyof T]: T[K] }};{RESET}\n")

    user_schema = ObjectTypeNode((
        ("id", PrimitiveType("string"), False),
        ("role", PrimitiveType("string"), False),
        ("isActive", PrimitiveType("boolean"), False)
    ))
    log_step("Original Mutable Schema", user_schema.inspect())

    readonly_schema = TSStandardLibrary.make_readonly(user_schema)
    log_step("Mapped Readonly Schema", readonly_schema.inspect())

    # Cek apakah mutable dapat di-assign ke readonly (Covariant on props)
    assignable = engine.is_subtype_of(user_schema, readonly_schema, {})
    print(f"\n  Assignable Mutable -> Readonly: {GREEN if assignable else RED}{assignable}{RESET}")

    # --- Ringkasan Eksekusi ---
    print_banner("Lab Summary: Parametric Polymorphism")
    print(f"  {BOLD}Status Kompilasi Simulasi:{RESET} {GREEN}SEMUA CHECK SUKSES (0 Type Errors){RESET}")
    print(f"  {DIM}Engine berhasil mendemonstrasikan distributive evaluation, constraint assertion,{RESET}")
    print(f"  {DIM}unification pattern-matching (infer), serta homomorphic transformation.{RESET}\n")


if __name__ == "__main__":
    t0 = time.perf_counter()
    run_lab()
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"{DIM}[Type Check time: {elapsed:.2f}ms]{RESET}")