#!/usr/bin/env python3
"""
Lab Hands-on: Control Flow Analysis (CFA) & Type Guards Engine Simulator
Topic: TypeScript - Chapter 06: Control Flow Analysis & Type Guards
Module: 02 Deep Dive

Deskripsi:
Script ini memodelkan mesin Control Flow Analysis (CFA) internal TypeScript.
Mensimulasikan cara compiler melakukan Type Narrowing via:
1. 'typeof' Type Guards (string, number, boolean)
2. Discriminated Unions (tag checks seperti kind === 'circle')
3. User-Defined Type Predicates (param is Type)
4. Truthiness / Nullability Narrowing
5. Exhaustiveness Checking via Type 'never'
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Union
import sys

# ==========================================
# ANSI Color Codes untuk Visualisasi Terminal
# ==========================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"

# ==========================================
# Type System Model
# ==========================================
class TSNode:
    """Base class untuk tipe data dalam sistem tipe TypeScript."""
    def type_str(self) -> str:
        raise NotImplementedError

@dataclass(frozen=True)
class PrimitiveType(TSNode):
    name: str  # 'string', 'number', 'boolean', 'null', 'undefined'
    def type_str(self) -> str:
        return self.name

@dataclass(frozen=True)
class ObjectType(TSNode):
    name: str
    props: Dict[str, str]  # property name -> literal or type value
    def type_str(self) -> str:
        props_repr = ", ".join(f"{k}: '{v}'" for k, v in self.props.items())
        return f"{self.name} {{{props_repr}}}"

@dataclass(frozen=True)
class NeverType(TSNode):
    def type_str(self) -> str:
        return f"{Style.RED}never{Style.RESET}"

@dataclass(frozen=True)
class UnionType(TSNode):
    members: Tuple[TSNode, ...]

    def __post_init__(self):
        # Flatten nested unions & remove duplicates
        flattened: Set[TSNode] = set()
        for m in self.members:
            if isinstance(m, UnionType):
                flattened.update(m.members)
            elif not isinstance(m, NeverType):
                flattened.add(m)
        object.__setattr__(self, 'members', tuple(sorted(flattened, key=lambda x: str(x))))

    def type_str(self) -> str:
        if not self.members:
            return f"{Style.RED}never{Style.RESET}"
        return " | ".join(m.type_str() for m in self.members)

# Factory helper untuk union
def make_union(*types: TSNode) -> TSNode:
    filtered = [t for t in types if not isinstance(t, NeverType)]
    if not filtered:
        return NeverType()
    if len(filtered) == 1:
        return filtered[0]
    return UnionType(tuple(filtered))

# ==========================================
# Type Guards & Predicates
# ==========================================
class Guard:
    """Representasi ekspresi kondisional (Type Guard)."""
    def narrow(self, current_type: TSNode, branch: bool) -> TSNode:
        raise NotImplementedError

class TypeofGuard(Guard):
    """Simulasi guard: typeof x === 'typename'"""
    def __init__(self, target_var: str, expected_type: str):
        self.target_var = target_var
        self.expected_type = expected_type

    def narrow(self, current_type: TSNode, branch: bool) -> TSNode:
        members = current_type.members if isinstance(current_type, UnionType) else (current_type,)
        matched = []
        unmatched = []

        for m in members:
            if isinstance(m, PrimitiveType) and m.name == self.expected_type:
                matched.append(m)
            else:
                unmatched.append(m)

        selected = matched if branch else unmatched
        return make_union(*selected)

class DiscriminantGuard(Guard):
    """Simulasi guard: x.kind === 'literal_value' pada Discriminated Union."""
    def __init__(self, target_var: str, prop: str, expected_value: str):
        self.target_var = target_var
        self.prop = prop
        self.expected_value = expected_value

    def narrow(self, current_type: TSNode, branch: bool) -> TSNode:
        members = current_type.members if isinstance(current_type, UnionType) else (current_type,)
        matched = []
        unmatched = []

        for m in members:
            if isinstance(m, ObjectType) and m.props.get(self.prop) == self.expected_value:
                matched.append(m)
            else:
                unmatched.append(m)

        selected = matched if branch else unmatched
        return make_union(*selected)

class CustomTypePredicateGuard(Guard):
    """Simulasi User-Defined Type Guard: isFish(pet): pet is Fish"""
    def __init__(self, target_var: str, narrowed_target: TSNode):
        self.target_var = target_var
        self.narrowed_target = narrowed_target

    def narrow(self, current_type: TSNode, branch: bool) -> TSNode:
        members = current_type.members if isinstance(current_type, UnionType) else (current_type,)
        matched = []
        unmatched = []

        for m in members:
            if m == self.narrowed_target:
                matched.append(m)
            else:
                unmatched.append(m)

        selected = matched if branch else unmatched
        return make_union(*selected)

# ==========================================
# Control Flow Analysis (CFA) Engine
# ==========================================
@dataclass
class FlowScope:
    name: str
    var_types: Dict[str, TSNode] = field(default_factory=dict)
    unreachable: bool = False

class CFAEngine:
    """
    Mesin CFA TypeScript: Menelusuri jalur eksekusi kode,
    mempersempit ruang tipe (type narrowing), dan memverifikasi exhaustiveness.
    """
    def __init__(self):
        self.history: List[str] = []

    def log(self, message: str):
        self.history.append(message)
        print(message)

    def analyze_branch(
        self,
        scope_name: str,
        initial_scope: FlowScope,
        guard: Guard,
        branch_cond: bool
    ) -> FlowScope:
        """
        Menganalisis satu jalur kontrol alir (True/False branch).
        Menerapkan pereduksian tipe via Guard.
        """
        new_scope = FlowScope(name=scope_name, var_types=dict(initial_scope.var_types))
        
        # Cari variabel yang ditargetkan
        var_name = getattr(guard, 'target_var', None)
        if var_name and var_name in new_scope.var_types:
            current_type = new_scope.var_types[var_name]
            narrowed = guard.narrow(current_type, branch=branch_cond)
            new_scope.var_types[var_name] = narrowed
            
            # Jika tipe menyusut ke 'never', tandai branch sebagai unreachable/exhausted
            if isinstance(narrowed, NeverType):
                new_scope.unreachable = True

        return new_scope

    def check_exhaustiveness(self, var_name: str, final_scope: FlowScope) -> Tuple[bool, str]:
        """
        Simulasi TypeScript exhaustive checking:
        default: const _exhaustiveCheck: never = x;
        """
        final_type = final_scope.var_types.get(var_name, NeverType())
        if isinstance(final_type, NeverType):
            return True, f"{Style.GREEN}Exhaustive check PASSED: '{var_name}' narrowed to 'never'. Tidak ada kasus unhandled.{Style.RESET}"
        else:
            return False, f"{Style.RED}Exhaustive check FAILED: Unhandled case for '{var_name}'. Remaining type: {final_type.type_str()}{Style.RESET}"

# ==========================================
# Skenario Hands-on & Eksekusi
# ==========================================
def print_header(title: str):
    print(f"\n{Style.BOLD}{Style.BLUE}=== [LAB] {title} ==={Style.RESET}")

def main():
    engine = CFAEngine()
    
    # ---------------------------------------------------------
    # SKENARIO 1: 'typeof' Narrowing pada Primitive Union
    # Union: string | number | boolean
    # ---------------------------------------------------------
    print_header("Skenario 1: Control Flow Analysis dengan 'typeof' Type Guards")
    
    t_str = PrimitiveType("string")
    t_num = PrimitiveType("number")
    t_bool = PrimitiveType("boolean")
    input_union = make_union(t_str, t_num, t_bool)
    
    scope_init = FlowScope("Function Entry", {"val": input_union})
    print(f"Scope: {scope_init.name}")
    print(f"  Tipe Awal 'val': {Style.CYAN}{scope_init.var_types['val'].type_str()}{Style.RESET}")
    
    # if (typeof val === 'string')
    guard_str = TypeofGuard(target_var="val", expected_type="string")
    scope_then_str = engine.analyze_branch("If (typeof val === 'string')", scope_init, guard_str, True)
    scope_else_str = engine.analyze_branch("Else Branch 1", scope_init, guard_str, False)
    
    print(f"\n-> Evaluasi: if (typeof val === 'string')")
    print(f"   [THEN Branch]  'val': {Style.GREEN}{scope_then_str.var_types['val'].type_str()}{Style.RESET}")
    print(f"   [ELSE Branch]  'val': {Style.YELLOW}{scope_else_str.var_types['val'].type_str()}{Style.RESET}")
    
    # Dalam ELSE: if (typeof val === 'number')
    guard_num = TypeofGuard(target_var="val", expected_type="number")
    scope_then_num = engine.analyze_branch("If (typeof val === 'number')", scope_else_str, guard_num, True)
    scope_else_num = engine.analyze_branch("Else Final", scope_else_str, guard_num, False)
    
    print(f"\n-> Evaluasi Bersarang di ELSE: if (typeof val === 'number')")
    print(f"   [THEN Branch]  'val': {Style.GREEN}{scope_then_num.var_types['val'].type_str()}{Style.RESET}")
    print(f"   [ELSE Branch]  'val': {Style.MAGENTA}{scope_else_num.var_types['val'].type_str()}{Style.RESET} (Otomatis menyusut ke boolean)")

    # ---------------------------------------------------------
    # SKENARIO 2: Discriminated Unions & Exhaustiveness Check
    # Union: Circle | Square | Triangle
    # ---------------------------------------------------------
    print_header("Skenario 2: Discriminated Unions & Exhaustiveness Checking (never)")

    circle = ObjectType("Circle", {"kind": "circle"})
    square = ObjectType("Square", {"kind": "square"})
    triangle = ObjectType("Triangle", {"kind": "triangle"})
    shape_union = make_union(circle, square, triangle)

    shape_scope = FlowScope("Switch Entry", {"shape": shape_union})
    print(f"Scope: {shape_scope.name}")
    print(f"  Tipe Awal 'shape': {Style.CYAN}{shape_scope.var_types['shape'].type_str()}{Style.RESET}")

    # Case 1: case 'circle'
    guard_circle = DiscriminantGuard("shape", "kind", "circle")
    scope_case_circle = engine.analyze_branch("case 'circle'", shape_scope, guard_circle, True)
    scope_rem_1 = engine.analyze_branch("fallthrough 1", shape_scope, guard_circle, False)
    print(f"\n[Case 'circle'] -> Narrows to: {Style.GREEN}{scope_case_circle.var_types['shape'].type_str()}{Style.RESET}")
    print(f"                 Remaining : {Style.YELLOW}{scope_rem_1.var_types['shape'].type_str()}{Style.RESET}")

    # Case 2: case 'square'
    guard_square = DiscriminantGuard("shape", "kind", "square")
    scope_case_square = engine.analyze_branch("case 'square'", scope_rem_1, guard_square, True)
    scope_rem_2 = engine.analyze_branch("fallthrough 2", scope_rem_1, guard_square, False)
    print(f"[Case 'square'] -> Narrows to: {Style.GREEN}{scope_case_square.var_types['shape'].type_str()}{Style.RESET}")
    print(f"                 Remaining : {Style.YELLOW}{scope_rem_2.var_types['shape'].type_str()}{Style.RESET}")

    # Case 3: case 'triangle'
    guard_triangle = DiscriminantGuard("shape", "kind", "triangle")
    scope_case_tri = engine.analyze_branch("case 'triangle'", scope_rem_2, guard_triangle, True)
    scope_default = engine.analyze_branch("default block", scope_rem_2, guard_triangle, False)
    print(f"[Case 'triangle']-> Narrows to: {Style.GREEN}{scope_case_tri.var_types['shape'].type_str()}{Style.RESET}")
    print(f"                 Remaining : {scope_default.var_types['shape'].type_str()}")

    print(f"\n[Validasi default block (Exhaustive)]:")
    success, msg = engine.check_exhaustiveness("shape", scope_default)
    print(f"  {msg}")

    # ---------------------------------------------------------
    # SKENARIO 3: Non-Exhaustive Flaw (Bug Detection)
    # Lupa meng-handle 'Triangle'
    # ---------------------------------------------------------
    print_header("Skenario 3: Deteksi Bug Kompilasi (Missing Union Discriminant)")
    print(f"Simulasi: Developer lupa menulis case 'triangle':")
    success_broken, msg_broken = engine.check_exhaustiveness("shape", scope_rem_2)
    print(f"  {msg_broken}")

    # ---------------------------------------------------------
    # SKENARIO 4: User-Defined Type Guard Predicate (pet is Fish)
    # ---------------------------------------------------------
    print_header("Skenario 4: User-Defined Type Guard Predicates")
    
    fish = ObjectType("Fish", {"swim": "true"})
    bird = ObjectType("Bird", {"fly": "true"})
    pet_union = make_union(fish, bird)
    pet_scope = FlowScope("Pet Shelter", {"pet": pet_union})

    print(f"Tipe Target: pet = {Style.CYAN}{pet_scope.var_types['pet'].type_str()}{Style.RESET}")
    
    predicate_guard = CustomTypePredicateGuard(target_var="pet", narrowed_target=fish)
    scope_is_fish = engine.analyze_branch("if isFish(pet)", pet_scope, predicate_guard, True)
    scope_not_fish = engine.analyze_branch("else (pet is Bird)", pet_scope, predicate_guard, False)

    print(f"-> Fungsi Predikat: isFish(pet: Fish | Bird): pet is Fish")
    print(f"   [pet is Fish branch] : {Style.GREEN}{scope_is_fish.var_types['pet'].type_str()}{Style.RESET}")
    print(f"   [else branch]        : {Style.MAGENTA}{scope_not_fish.var_types['pet'].type_str()}{Style.RESET}")

    print(f"\n{Style.BOLD}{Style.GREEN}✓ Simulasi Control Flow Analysis selesai tanpa error.{Style.RESET}\n")

if __name__ == "__main__":
    main()