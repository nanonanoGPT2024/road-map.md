#!/usr/bin/env python3
"""
Lab Hands-on: TypeScript Type-Level Metaprogramming & Inference Engine
Bab 05: Type-Level Programming & Metaprogramming (Deep Dive)

Deskripsi:
Script ini memodelkan Type System Interpreter internal TypeScript secara deterministik.
Mengimplementasikan:
1. Subtyping & Type Assignability (`extends` semantics).
2. Pattern Matching & Type Inference via `infer` declarations.
3. Recursive Conditional Types dengan batas kedalaman (guard TS2589).
4. Type-level Peano/Tuple Arithmetic (operasi matematika di level tipe).
5. Mapped Type and Generic Transformation Engine.
"""

from __future__ import annotations
import sys
import time
from typing import Dict, List, Optional, Any, Tuple as PyTuple
from dataclasses import dataclass, field

# --- Terminal ANSI Styling ---
CLR_RESET  = "\033[0m"
CLR_CYAN   = "\033[96m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_MAGENTA= "\033[95m"
CLR_RED    = "\033[91m"
CLR_BOLD   = "\033[1m"
CLR_DIM    = "\033[2m"


# ============================================================================
# 1. AST DEFINITIONS UNTUK TYPESCRIPT TYPE-LEVEL SYSTEM
# ============================================================================

class TSType:
    """Basis abstrak untuk semua node Type-Level AST."""
    def inspect(self) -> str:
        raise NotImplementedError()

    def __repr__(self) -> str:
        return self.inspect()


@dataclass(frozen=True)
class PrimitiveType(TSType):
    name: str  # 'string', 'number', 'boolean', 'never', 'any', 'unknown'

    def inspect(self) -> str:
        return f"{CLR_YELLOW}{self.name}{CLR_RESET}"


@dataclass(frozen=True)
class LiteralType(TSType):
    value: Any  # "hello", 42, True

    def inspect(self) -> str:
        if isinstance(self.value, str):
            return f'{CLR_GREEN}"{self.value}"{CLR_RESET}'
        return f"{CLR_GREEN}{str(self.value).lower()}{CLR_RESET}"


@dataclass(frozen=True)
class TypeVar(TSType):
    name: str

    def inspect(self) -> str:
        return f"{CLR_CYAN}{self.name}{CLR_RESET}"


@dataclass(frozen=True)
class InferType(TSType):
    var_name: str

    def inspect(self) -> str:
        return f"{CLR_MAGENTA}infer {self.var_name}{CLR_RESET}"


@dataclass(frozen=True)
class GenericInstance(TSType):
    name: str
    type_args: PyTuple[TSType, ...]

    def inspect(self) -> str:
        args_str = ", ".join(arg.inspect() for arg in self.type_args)
        return f"{CLR_BLUE}{self.name}{CLR_RESET}<{args_str}>"


@dataclass(frozen=True)
class TupleType(TSType):
    elements: PyTuple[TSType, ...]

    def inspect(self) -> str:
        elems = ", ".join(e.inspect() for e in self.elements)
        return f"[{elems}]"


@dataclass(frozen=True)
class ObjectType(TSType):
    properties: Dict[str, TSType]
    is_readonly: bool = False

    def inspect(self) -> str:
        ro_prefix = "readonly " if self.is_readonly else ""
        props = "; ".join(f"{ro_prefix}{k}: {v.inspect()}" for k, v in self.properties.items())
        return f"{{ {props} }}"


@dataclass(frozen=True)
class ConditionalType(TSType):
    check_type: TSType
    extends_type: TSType
    true_type: TSType
    false_type: TSType

    def inspect(self) -> str:
        return (f"{self.check_type.inspect()} extends {self.extends_type.inspect()} "
                f"? {self.true_type.inspect()} : {self.false_type.inspect()}")


# Konstanta Primitive Types
T_NEVER   = PrimitiveType("never")
T_UNKNOWN = PrimitiveType("unknown")
T_ANY     = PrimitiveType("any")
T_STRING  = PrimitiveType("string")
T_NUMBER  = PrimitiveType("number")
T_BOOLEAN = PrimitiveType("boolean")


# ============================================================================
# 2. INFERENCE & REDUCTION ENGINE (TYPE-LEVEL VM)
# ============================================================================

class RecursionLimitExceeded(Exception):
    """Exception yang merefleksikan error TypeScript TS2589."""
    pass


class TypeEngine:
    """
    Mesin Evaluasi Type-Level TypeScript:
    Menjalankan reduksi AST, pattern matching, unifikasi generic, dan batasan rekursi.
    """
    MAX_RECURSION_DEPTH = 35

    def __init__(self):
        self.type_aliases: Dict[str, PyTuple[PyTuple[str, ...], TSType]] = {}
        self.reduction_count = 0

    def register_type_alias(self, name: str, params: List[str], body: TSType):
        """Mendaftarkan Type Alias generic: type Name<Params> = Body"""
        self.type_aliases[name] = (tuple(params), body)

    def is_assignable(self, source: TSType, target: TSType, env: Dict[str, TSType]) -> Tuple[bool, Dict[str, TSType]]:
        """
        Mengevaluasi apakah `source extends target`.
        Mendukung pattern matching destrukturisasi melalui `infer U`.
        """
        # Tangani inferensial pattern
        if isinstance(target, InferType):
            new_env = dict(env)
            new_env[target.var_name] = source
            return True, new_env

        # Primitive type exact match
        if source == target:
            return True, env

        if target == T_ANY or target == T_UNKNOWN:
            return True, env

        if source == T_NEVER:
            return True, env

        # Literal Subtyping (misal: "hello" extends string)
        if isinstance(source, LiteralType):
            if isinstance(target, PrimitiveType):
                if isinstance(source.value, str) and target.name == "string":
                    return True, env
                if isinstance(source.value, (int, float)) and target.name == "number":
                    return True, env
                if isinstance(source.value, bool) and target.name == "boolean":
                    return True, env

        # Generic Instance Unification (misal: Promise<infer R> match Promise<string>)
        if isinstance(source, GenericInstance) and isinstance(target, GenericInstance):
            if source.name == target.name and len(source.type_args) == len(target.type_args):
                curr_env = dict(env)
                for s_arg, t_arg in zip(source.type_args, target.type_args):
                    matched, curr_env = self.is_assignable(s_arg, t_arg, curr_env)
                    if not matched:
                        return False, env
                return True, curr_env

        # Tuple Unification & Pattern Extraction
        if isinstance(source, TupleType) and isinstance(target, TupleType):
            if len(source.elements) == len(target.elements):
                curr_env = dict(env)
                for s_elem, t_elem in zip(source.elements, target.elements):
                    matched, curr_env = self.is_assignable(s_elem, t_elem, curr_env)
                    if not matched:
                        return False, env
                return True, curr_env

        return False, env

    def substitute(self, typ: TSType, env: Dict[str, TSType]) -> TSType:
        """Mengganti variabel tipe dengan argumen konkret dari environment lexical."""
        if isinstance(typ, TypeVar):
            return env.get(typ.name, typ)

        if isinstance(typ, GenericInstance):
            new_args = tuple(self.substitute(arg, env) for arg in typ.type_args)
            return GenericInstance(typ.name, new_args)

        if isinstance(typ, TupleType):
            return TupleType(tuple(self.substitute(elem, env) for elem in typ.elements))

        if isinstance(typ, ObjectType):
            new_props = {k: self.substitute(v, env) for k, v in typ.properties.items()}
            return ObjectType(new_props, is_readonly=typ.is_readonly)

        if isinstance(typ, ConditionalType):
            return ConditionalType(
                check_type=self.substitute(typ.check_type, env),
                extends_type=self.substitute(typ.extends_type, env),
                true_type=self.substitute(typ.true_type, env),
                false_type=self.substitute(typ.false_type, env)
            )

        return typ

    def evaluate(self, typ: TSType, depth: int = 0) -> TSType:
        """
        Core Reducer: Mereduksi ekspresi type-level secara rekursif hingga normal form.
        """
        self.reduction_count += 1
        if depth > self.MAX_RECURSION_DEPTH:
            raise RecursionLimitExceeded(
                f"TS2589: Type instantiation is excessively deep and possibly infinite (depth > {self.MAX_RECURSION_DEPTH})."
            )

        # 1. Resolusi Generic Alias Call
        if isinstance(typ, GenericInstance):
            if typ.name in self.type_aliases:
                params, body = self.type_aliases[typ.name]
                if len(params) != len(typ.type_args):
                    raise ValueError(f"Expected {len(params)} type arguments, got {len(typ.type_args)}")
                
                # Evaluasi argumen terlebih dahulu
                evaluated_args = tuple(self.evaluate(arg, depth + 1) for arg in typ.type_args)
                env = dict(zip(params, evaluated_args))
                substituted_body = self.substitute(body, env)
                return self.evaluate(substituted_body, depth + 1)
            else:
                # Objek generic murni (misal Promise<T>)
                return GenericInstance(typ.name, tuple(self.evaluate(a, depth + 1) for a in typ.type_args))

        # 2. Evaluasi Conditional Types (T extends U ? TrueBranch : FalseBranch)
        if isinstance(typ, ConditionalType):
            eval_check = self.evaluate(typ.check_type, depth + 1)
            eval_extends = typ.extends_type  # Target pattern tidak direduksi penuh agar infer tetap valid

            matched, inferred_env = self.is_assignable(eval_check, eval_extends, {})

            if matched:
                resolved_branch = self.substitute(typ.true_type, inferred_env)
                return self.evaluate(resolved_branch, depth + 1)
            else:
                return self.evaluate(typ.false_type, depth + 1)

        # 3. Tuple Evaluation
        if isinstance(typ, TupleType):
            return TupleType(tuple(self.evaluate(e, depth + 1) for e in typ.elements))

        # 4. Object Evaluation
        if isinstance(typ, ObjectType):
            return ObjectType(
                {k: self.evaluate(v, depth + 1) for k, v in typ.properties.items()},
                is_readonly=typ.is_readonly
            )

        return typ


# ============================================================================
# 3. TYPE-LEVEL METAPROGRAMMING DEMONSTRATOR
# ============================================================================

def setup_type_system(engine: TypeEngine):
    """Mendaftarkan utility types meta-programming standar TypeScript."""
    
    # type UnwrapPromise<T> = T extends Promise<infer U> ? UnwrapPromise<U> : T
    engine.register_type_alias(
        "UnwrapPromise",
        ["T"],
        ConditionalType(
            check_type=TypeVar("T"),
            extends_type=GenericInstance("Promise", (InferType("U"),)),
            true_type=GenericInstance("UnwrapPromise", (TypeVar("U"),)),
            false_type=TypeVar("T")
        )
    )

    # type PopTuple<T> = T extends [infer Head, infer Tail] ? Tail : never
    engine.register_type_alias(
        "Tail",
        ["T"],
        ConditionalType(
            check_type=TypeVar("T"),
            extends_type=TupleType((TypeVar("_Head"), InferType("Rest"))),
            true_type=TypeVar("Rest"),
            false_type=T_NEVER
        )
    )

    # Type-Level Natural Addition via Tuple Concatenation Simulation
    # type Add<A, B> = [...A, ...B]['length'] (dimodelkan melalui Type Tuple Reducer)
    # type Concat<T, U> = T extends [infer Head, infer Tail] ...
    # Diimplementasikan demonstrator rekursif: Decr/Incr
    # type IsZero<N> = N extends [] ? true : false
    engine.register_type_alias(
        "IsZero",
        ["N"],
        ConditionalType(
            check_type=TypeVar("N"),
            extends_type=TupleType(()),
            true_type=LiteralType(True),
            false_type=LiteralType(False)
        )
    )


def run_benchmark_and_verification():
    engine = TypeEngine()
    setup_type_system(engine)

    print(f"{CLR_BOLD}{CLR_CYAN}=== TYPESCRIPT TYPE-LEVEL METAPROGRAMMING ENGINE SIMULATOR ==={CLR_RESET}\n")

    # Kasus 1: Deep Recursive Conditional Type (UnwrapPromise / Awaited)
    print(f"{CLR_BOLD}1. Deep Recursive Conditional Type: Awaited<T> via Pattern Matching{CLR_RESET}")
    print(f"{CLR_DIM}Code: type UnwrapPromise<T> = T extends Promise<infer U> ? UnwrapPromise<U> : T{CLR_RESET}")
    
    nested_promise = GenericInstance("Promise", (
        GenericInstance("Promise", (
            GenericInstance("Promise", (
                LiteralType("Deep Value Unlocked!"),
            )),
        )),
    ))
    
    target_query = GenericInstance("UnwrapPromise", (nested_promise,))
    print(f"Target Type : {target_query.inspect()}")
    
    t0 = time.perf_counter()
    result = engine.evaluate(target_query)
    dt = (time.perf_counter() - t0) * 1000
    
    print(f"Reduced to  : {result.inspect()}")
    print(f"Metrics     : {engine.reduction_count} reduksi dalam {dt:.4f} ms\n")

    # Kasus 2: Mapped Types & DeepReadonly Metaprogramming
    print(f"{CLR_BOLD}2. Type Metaprogramming: Mapped DeepReadonly Transformation{CLR_RESET}")
    raw_user_type = ObjectType({
        "id": T_NUMBER,
        "profile": ObjectType({
            "username": T_STRING,
            "roles": TupleType((LiteralType("ADMIN"), LiteralType("OPERATOR")))
        })
    })

    def deep_readonly(typ: TSType) -> TSType:
        """Mengemulasi: type DeepReadonly<T> = { readonly [K in keyof T]: DeepReadonly<T[K]> }"""
        if isinstance(typ, ObjectType):
            return ObjectType(
                properties={k: deep_readonly(v) for k, v in typ.properties.items()},
                is_readonly=True
            )
        elif isinstance(typ, TupleType):
            return TupleType(tuple(deep_readonly(e) for e in typ.elements))
        return typ

    print(f"Input Type  : {raw_user_type.inspect()}")
    transformed = deep_readonly(raw_user_type)
    print(f"DeepReadonly: {transformed.inspect()}\n")

    # Kasus 3: Type-Level Peano Arithmetic / Tuple Length Computation
    print(f"{CLR_BOLD}3. Type-Level Computation: Peano Nat Addition via Tuple Sizing{CLR_RESET}")
    print(f"{CLR_DIM}TypeScript memodelkan bilangan asli N melalui tuple berukuran N: [1, 1, ...]{CLR_RESET}")

    def make_nat(n: int) -> TupleType:
        return TupleType(tuple(LiteralType(1) for _ in range(n)))

    nat_3 = make_nat(3)
    nat_4 = make_nat(4)

    # type Add<A extends any[], B extends any[]> = [...A, ...B]['length']
    def type_level_add(a: TupleType, b: TupleType) -> LiteralType:
        concatenated = TupleType(a.elements + b.elements)
        # Evaluasi indexing ['length']
        return LiteralType(len(concatenated.elements))

    print(f"Type A (Nat 3) : {nat_3.inspect()}")
    print(f"Type B (Nat 4) : {nat_4.inspect()}")
    sum_type = type_level_add(nat_3, nat_4)
    print(f"Add<A, B>['length'] -> Literal Result: {sum_type.inspect()}\n")

    # Kasus 4: Guarding against Infinite Recursion (TS2589 Simulation)
    print(f"{CLR_BOLD}4. Error Simulation: Detecting Infinite Recursion (TS2589){CLR_RESET}")
    
    # Definisikan recursive loop tak hingga: type Loop<T> = Loop<Promise<T>>
    engine.register_type_alias(
        "InfiniteLoop",
        ["T"],
        GenericInstance("InfiniteLoop", (GenericInstance("Promise", (TypeVar("T"),)),))
    )
    
    bad_type = GenericInstance("InfiniteLoop", (T_STRING,))
    print(f"Evaluating  : {bad_type.inspect()}")

    try:
        engine.reduction_count = 0
        engine.evaluate(bad_type)
        print(f"{CLR_RED}FAILURE: Loop tidak terdeteksi!{CLR_RESET}")
    except RecursionLimitExceeded as e:
        print(f"Status      : {CLR_GREEN}RECURSION TRAP SUCCESSFUL{CLR_RESET}")
        print(f"Engine Log  : {CLR_RED}{e}{CLR_RESET}")

    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ Lab Berhasil: Mekanisme Inti Type-Level Programming TypeScript Tervalidasi.{CLR_RESET}")


if __name__ == "__main__":
    run_benchmark_and_verification()