#!/usr/bin/env python3
"""
Lab Exercise: TypeScript Type System Internals & Advanced Patterns Simulator
BAB-02: TypeScript Type System Internals dan Advanced Patterns
Simulasi interaktif algoritma type checker TypeScript dalam Python 3 murni.
"""

import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# ANSI Color Codes untuk visualisasi terminal
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
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"

def print_header(title: str) -> None:
    line = "=" * 70
    print(f"\n{Style.CYAN}{Style.BOLD}{line}{Style.RESET}")
    print(f"{Style.CYAN}{Style.BOLD} >>> {title.upper()} <<<{Style.RESET}")
    print(f"{Style.CYAN}{Style.BOLD}{line}{Style.RESET}\n")

def print_step(title: str, desc: str) -> None:
    print(f"{Style.YELLOW}{Style.BOLD}[SIMULATOR]{Style.RESET} {Style.BOLD}{title}{Style.RESET}")
    print(f"  {Style.DIM}{desc}{Style.RESET}")

# ---------------------------------------------------------------------------
# 1. Structural Subtyping Engine (Duck Typing / Assignability)
# ---------------------------------------------------------------------------
class TypeScriptStructuralType:
    def __init__(self, name: str, properties: Dict[str, str], exact: bool = False):
        self.name = name
        self.properties = properties
        self.exact = exact

    def is_assignable_to(self, target: "TypeScriptStructuralType") -> Tuple[bool, Optional[str]]:
        """
        S is assignable to T (S <: T) if for all properties p: T_p in T,
        there exists p: S_p in S such that S_p is assignable to T_p.
        Extra properties in S are permitted (structural subtyping / width subtyping).
        """
        for prop, expected_type in target.properties.items():
            if prop not in self.properties:
                return False, f"Properti '{prop}' hilang pada tipe '{self.name}'."
            actual_type = self.properties[prop]
            if actual_type != expected_type:
                return False, (f"Ketidakcocokan tipe properti '{prop}': "
                              f"diharapkan '{expected_type}', ditemukan '{actual_type}'.")
        
        if target.exact:
            extra_props = set(self.properties.keys()) - set(target.properties.keys())
            if extra_props:
                return False, f"Excess Property Check: properti tak terduga {extra_props} pada tipe ketat."

        return True, None

# ---------------------------------------------------------------------------
# 2. Discriminated Union & Exhaustiveness Checking (never type)
# ---------------------------------------------------------------------------
class DiscriminatedUnionEngine:
    def __init__(self):
        self.registered_actions = {
            "ADD_TODO": {"text": "string"},
            "TOGGLE_TODO": {"id": "number"},
            "DELETE_TODO": {"id": "number"},
            "RESET_ALL": {}
        }

    def simulate_reducer(self, action: Dict[str, Any], handled_cases: Set[str]) -> Tuple[bool, str]:
        kind = action.get("type")
        if not kind or kind not in self.registered_actions:
            return False, f"Unknown action discriminator: {kind}"

        # Exhaustiveness checking simulation
        all_cases = set(self.registered_actions.keys())
        unhandled = all_cases - handled_cases

        if kind in handled_cases:
            return True, f"Action '{kind}' ditangani secara safe. Payload tervalidasi."
        else:
            return False, (f"{Style.RED}[TS2366 Error]{Style.RESET} Exhaustiveness check failed! "
                          f"Kasus tak tertangani: {unhandled}. Gagal assign ke 'never'.")

# ---------------------------------------------------------------------------
# 3. Distributive Conditional Types Simulator: T extends U ? X : Y
# ---------------------------------------------------------------------------
def simulate_distributive_conditional(
    union_input: List[str], 
    extends_target: str, 
    true_branch: str, 
    false_branch: str
) -> List[Tuple[str, str]]:
    """
    Distributivity over naked type parameters:
    (A | B | C) extends Target ? TrueBranch : FalseBranch
    evaluates to:
    (A extends Target ? ...) | (B extends Target ? ...) | (C extends Target ? ...)
    """
    results = []
    for item in union_input:
        if item == extends_target:
            resolved = true_branch.replace("T", item)
            results.append((item, resolved))
        else:
            resolved = false_branch.replace("T", item)
            results.append((item, resolved))
    return results

# ---------------------------------------------------------------------------
# 4. Variance Engine: Covariance & Contravariance
# ---------------------------------------------------------------------------
class FunctionType:
    def __init__(self, param_type: str, return_type: str):
        self.param_type = param_type  # In TS: Contravariant under --strictFunctionTypes
        self.return_type = return_type # In TS: Covariant

def check_variance_assignability(
    source_fn: FunctionType, 
    target_fn: FunctionType, 
    hierarchy: Dict[str, List[str]]
) -> Tuple[bool, str]:
    """
    source_fn (S_p -> S_r) assignable to target_fn (T_p -> T_r)?
    Rule:
    1. Param: Target param must be subtype of Source param (Contravariance: T_p <: S_p)
    2. Return: Source return must be subtype of Target return (Covariance: S_r <: T_r)
    """
    def is_subtype(sub: str, sup: str) -> bool:
        if sub == sup:
            return True
        return sup in hierarchy.get(sub, [])

    # Return covariance check: S_r <: T_r
    if not is_subtype(source_fn.return_type, target_fn.return_type):
        return False, (f"Gagal Covariance pada Return Type: '{source_fn.return_type}' "
                      f"bukan subtype dari '{target_fn.return_type}'.")

    # Param contravariance check: T_p <: S_p
    if not is_subtype(target_fn.param_type, source_fn.param_type):
        return False, (f"Gagal Contravariance pada Param Type: Parameter target '{target_fn.param_type}' "
                      f"tidak dapat dioperkan aman ke parameter source '{source_fn.param_type}'.")

    return True, "Valid! Memenuhi aturan Covariant Return dan Contravariant Parameter."

# ---------------------------------------------------------------------------
# CLI Interactive Loop & Test Suite
# ---------------------------------------------------------------------------
def run_structural_subtyping_demo():
    print_header("Modul 1: Structural Typing & Width Subtyping")
    user_model = TypeScriptStructuralType("UserSummary", {"id": "number", "name": "string"})
    db_entity = TypeScriptStructuralType("FullUserRecord", {
        "id": "number", 
        "name": "string", 
        "email": "string", 
        "created_at": "string"
    })
    invalid_entity = TypeScriptStructuralType("GuestSession", {"sessionId": "string", "name": "string"})

    print_step("Uji Assignability 1: FullUserRecord -> UserSummary",
               "Target mengharapkan {id, name}. Source memiliki {id, name, email, created_at}.")
    ok, err = db_entity.is_assignable_to(user_model)
    if ok:
        print(f"  {Style.GREEN}[SUCCESS]{Style.RESET} Assignable! Width subtyping mengizinkan properti tambahan.")
    else:
        print(f"  {Style.RED}[ERROR]{Style.RESET} {err}")

    print_step("\nUji Assignability 2: GuestSession -> UserSummary",
               "Target mengharapkan {id, name}. Source memiliki {sessionId, name}.")
    ok, err = invalid_entity.is_assignable_to(user_model)
    if ok:
        print(f"  {Style.GREEN}[SUCCESS]{Style.RESET} Assignable!")
    else:
        print(f"  {Style.RED}[TYPE CHECK ERROR]{Style.RESET} {err}")

def run_discriminated_union_demo():
    print_header("Modul 2: Discriminated Unions & Exhaustiveness Check")
    engine = DiscriminatedUnionEngine()

    print_step("Skenario Reducer Lengkap", "Menangani seluruh union member: ADD, TOGGLE, DELETE, RESET_ALL")
    handled_all = {"ADD_TODO", "TOGGLE_TODO", "DELETE_TODO", "RESET_ALL"}
    test_action = {"type": "TOGGLE_TODO", "id": 42}
    ok, msg = engine.simulate_reducer(test_action, handled_all)
    print(f"  Status: {Style.GREEN if ok else Style.RED}{msg}{Style.RESET}")

    print_step("\nSkenario Reducer Cacat (Missing RESET_ALL)", "Simulasi kelalaian developer saat menambahkan varian baru")
    handled_partial = {"ADD_TODO", "TOGGLE_TODO", "DELETE_TODO"}
    test_action_unhandled = {"type": "RESET_ALL"}
    ok, msg = engine.simulate_reducer(test_action_unhandled, handled_partial)
    print(f"  Status: {msg}")

def run_conditional_types_demo():
    print_header("Modul 3: Distributive Conditional Types (T extends U ? X : Y)")
    union_types = ["string", "number", "null", "undefined", "boolean"]
    print_step("Definisi Tipe Utilitas", "type NonNullable<T> = T extends null | undefined ? never : T")
    print(f"  Input Union: {Style.CYAN}{' | '.join(union_types)}{Style.RESET}\n")

    print(f"  {Style.BOLD}Mekanisme Resolusi per Cabang Union:{Style.RESET}")
    for item in union_types:
        is_nullable = item in ("null", "undefined")
        outcome = "never" if is_nullable else item
        color = Style.RED if outcome == "never" else Style.GREEN
        print(f"   * {item:<10} extends null | undefined ? {color}{outcome:<8}{Style.RESET}")

    filtered = [item for item in union_types if item not in ("null", "undefined")]
    print(f"\n  {Style.BOLD}Hasil Akhir (never dieliminasi dari union):{Style.RESET} {Style.GREEN}{' | '.join(filtered)}{Style.RESET}")

def run_variance_demo():
    print_header("Modul 4: Subtyping Variance (Covariance vs Contravariance)")
    # Type hierarchy: Dog <: Animal, Cat <: Animal
    type_hierarchy = {
        "Dog": ["Animal"],
        "Cat": ["Animal"],
        "Animal": []
    }
    print("  Hirarki Tipe: Dog <: Animal, Cat <: Animal")
    print("  Aturan TS --strictFunctionTypes: Parameter adalah CONTRAVARIANT, Return adalah COVARIANT.\n")

    f1 = FunctionType(param_type="Animal", return_type="Dog")   # (a: Animal) => Dog
    f2 = FunctionType(param_type="Dog", return_type="Animal")   # (d: Dog) => Animal

    print_step("Uji: Apakah (a: Animal) => Dog assignable ke (d: Dog) => Animal?",
               "Param: Animal vs Dog (Contravariant). Return: Dog vs Animal (Covariant).")
    ok, msg = check_variance_assignability(f1, f2, type_hierarchy)
    print(f"  Hasil: {Style.GREEN if ok else Style.RED}{msg}{Style.RESET}\n")

    print_step("Uji Terbalik: Apakah (d: Dog) => Animal assignable ke (a: Animal) => Dog?",
               "Ini akan ditolak karena melanggar keselamatan tipe runtime.")
    ok, msg = check_variance_assignability(f2, f1, type_hierarchy)
    print(f"  Hasil: {Style.RED if not ok else Style.GREEN}{msg}{Style.RESET}")

def main():
    print(f"{Style.BG_BLUE}{Style.WHITE}{Style.BOLD}  LAB EXERCISE: TYPESCRIPT TYPE SYSTEM INTERNALS  {Style.RESET}\n")
    print(f"Script ini mendemonstrasikan secara visual 4 pilar sistem tipe TypeScript.")
    
    run_structural_subtyping_demo()
    run_discriminated_union_demo()
    run_conditional_types_demo()
    run_variance_demo()

    print(f"\n{Style.BG_GREEN}{Style.WHITE}{Style.BOLD}  SEMUA SIMULASI BERJALAN DENGAN SUKSES!  {Style.RESET}\n")

if __name__ == "__main__":
    main()
