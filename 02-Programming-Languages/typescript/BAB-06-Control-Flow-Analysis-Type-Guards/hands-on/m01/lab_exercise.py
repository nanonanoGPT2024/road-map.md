#!/usr/bin/env python3
"""
================================================================================
LAB EXERCISE M01: CONTROL FLOW ANALYSIS (CFA) & TYPE GUARDS SIMULATOR
Modul 01 - Fondasi Inti Control Flow Analysis & Type Narrowing (TypeScript)
================================================================================
Simulasi teknis interaktif berbasis Python 3 yang mereplikasi cara kerja engine
TypeScript (tsc) dalam memetakan Control Flow Graph (CFG), melakukan reachability
analysis, dan mengevaluasi type guard (typeof, instanceof, in, custom predicates,
serta exhaustiveness checking dengan never).
================================================================================
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union


# ==============================================================================
# ANSI Color Palette & Terminal Styling
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright Foreground
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def print_banner(title: str) -> None:
    border = "=" * 76
    print(f"\n{Color.BRIGHT_CYAN}{border}{Color.RESET}")
    print(f"{Color.BOLD}{Color.BRIGHT_YELLOW} [TS-CFA ENGINE] {Color.BRIGHT_WHITE}{title}{Color.RESET}")
    print(f"{Color.BRIGHT_CYAN}{border}{Color.RESET}")


def print_step(step_num: int, label: str) -> None:
    print(f"\n{Color.BOLD}{Color.BRIGHT_BLUE}▶ LANGKAH {step_num}: {Color.BRIGHT_WHITE}{label}{Color.RESET}")


def print_type_state(var_name: str, before_type: str, guard: str, after_type: str) -> None:
    print(
        f"  {Color.BOLD}{Color.YELLOW}{var_name:<10}{Color.RESET} "
        f"Semula: {Color.RED}{before_type:<25}{Color.RESET} "
        f"Guard: {Color.CYAN}{guard:<22}{Color.RESET} "
        f"➔ Menyempit: {Color.BRIGHT_GREEN}{after_type}{Color.RESET}"
    )


# ==============================================================================
# Model Representasi Tipe Data & AST Sederhana
# ==============================================================================
class TypeKind(Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"
    UNDEFINED = "undefined"
    ARRAY = "any[]"
    OBJECT = "object"
    NEVER = "never"
    CUSTOM = "custom"


@dataclass
class TypeRep:
    name: str
    kind: TypeKind
    props: Dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.name


class UnionType:
    def __init__(self, types: List[TypeRep]):
        self.members: List[TypeRep] = types

    def remove(self, kind_to_remove: TypeKind) -> Union["UnionType", TypeRep]:
        filtered = [t for t in self.members if t.kind != kind_to_remove]
        if not filtered:
            return TypeRep("never", TypeKind.NEVER)
        if len(filtered) == 1:
            return filtered[0]
        return UnionType(filtered)

    def filter_by_kind(self, kind: TypeKind) -> Union["UnionType", TypeRep]:
        matched = [t for t in self.members if t.kind == kind]
        if not matched:
            return TypeRep("never", TypeKind.NEVER)
        if len(matched) == 1:
            return matched[0]
        return UnionType(matched)

    def filter_by_property(self, prop_name: str, prop_val: Optional[str] = None) -> Union["UnionType", TypeRep]:
        matched = []
        for t in self.members:
            if prop_name in t.props:
                if prop_val is None or t.props[prop_name] == prop_val:
                    matched.append(t)
        if not matched:
            return TypeRep("never", TypeKind.NEVER)
        if len(matched) == 1:
            return matched[0]
        return UnionType(matched)

    def __str__(self) -> str:
        if not self.members:
            return "never"
        return " | ".join(t.name for t in self.members)


# ==============================================================================
# Simulasi Skenario 1: Built-in 'typeof' & Truthiness Guard
# ==============================================================================
def demo_typeof_guard() -> None:
    print_banner("SKENARIO 1: Built-in 'typeof' & Truthiness Narrowing")
    print(f"{Color.DIM}Kode TS yang disimulasikan:{Color.RESET}")
    print(f"""{Color.BRIGHT_BLACK}
    function processInput(val: string | number | boolean | null) {{
        if (val === null) return;          // Truthiness / Null check
        if (typeof val === "string") {{      // typeof guard -> string
            console.log(val.toUpperCase());
        }} else if (typeof val === "number") {{ // typeof guard -> number
            console.log(val.toFixed(2));
        }} else {{                           // Remaining branch -> boolean
            console.log(!val);
        }}
    }}
    {Color.RESET}""")

    t_str = TypeRep("string", TypeKind.STRING)
    t_num = TypeRep("number", TypeKind.NUMBER)
    t_bool = TypeRep("boolean", TypeKind.BOOLEAN)
    t_null = TypeRep("null", TypeKind.NULL)

    current_union = UnionType([t_str, t_num, t_bool, t_null])

    print_step(1, "Inisialisasi Variabel pada Entry Node")
    print(f"  Tipe Awal parameter 'val': {Color.BOLD}{Color.RED}{current_union}{Color.RESET}")

    print_step(2, "Evaluasi Branch 1: `if (val === null) return;`")
    current_union = current_union.remove(TypeKind.NULL)
    print_type_state("val", "string | number | boolean | null", "val !== null", str(current_union))

    print_step(3, "Evaluasi Branch 2: `if (typeof val === 'string')`")
    narrowed_str = current_union.filter_by_kind(TypeKind.STRING)
    remaining_after_str = current_union.remove(TypeKind.STRING)
    print_type_state("val (if)", str(current_union), 'typeof === "string"', str(narrowed_str))
    print_type_state("val (else)", str(current_union), 'typeof !== "string"', str(remaining_after_str))

    print_step(4, "Evaluasi Branch 3: `else if (typeof val === 'number')`")
    narrowed_num = remaining_after_str.filter_by_kind(TypeKind.NUMBER)
    final_else = remaining_after_str.remove(TypeKind.NUMBER)
    print_type_state("val (if)", str(remaining_after_str), 'typeof === "number"', str(narrowed_num))
    print_type_state("val (else)", str(remaining_after_str), 'sisa branch (else)', str(final_else))


# ==============================================================================
# Simulasi Skenario 2: 'instanceof' Guard & Class Prototyping
# ==============================================================================
class HTTPError:
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


class NetworkError:
    def __init__(self, code: str):
        self.code = code


def demo_instanceof_guard() -> None:
    print_banner("SKENARIO 2: Prototype Narrowing dengan 'instanceof'")
    print(f"""{Color.BRIGHT_BLACK}
    class HTTPError extends Error {{ status: number; }}
    class NetworkError extends Error {{ code: string; }}
    function handleError(err: HTTPError | NetworkError | Error) {{
        if (err instanceof HTTPError) {{
            // err narrowed to HTTPError (akses .status diizinkan)
        }} else if (err instanceof NetworkError) {{
            // err narrowed to NetworkError (akses .code diizinkan)
        }}
    }}
    {Color.RESET}""")

    items: List[Union[HTTPError, NetworkError, Exception]] = [
        HTTPError(404, "Not Found"),
        NetworkError("ECONNREFUSED"),
        Exception("Generic Runtime Exception"),
    ]

    for idx, item in enumerate(items, 1):
        print(f"\n{Color.CYAN}--- Pengujian Objek #{idx}: {item.__class__.__name__} ---{Color.RESET}")
        print(f"  Tipe Union: {Color.YELLOW}HTTPError | NetworkError | Error{Color.RESET}")

        if isinstance(item, HTTPError):
            print(f"  {Color.GREEN}✔ instanceof HTTPError terpenuhi!{Color.RESET}")
            print(f"    Narrowed Type : {Color.BOLD}HTTPError{Color.RESET}")
            print(f"    Available Prop: status = {Color.BRIGHT_MAGENTA}{item.status}{Color.RESET}")
        elif isinstance(item, NetworkError):
            print(f"  {Color.GREEN}✔ instanceof NetworkError terpenuhi!{Color.RESET}")
            print(f"    Narrowed Type : {Color.BOLD}NetworkError{Color.RESET}")
            print(f"    Available Prop: code = {Color.BRIGHT_MAGENTA}{item.code}{Color.RESET}")
        else:
            print(f"  {Color.YELLOW}✔ Fallback ke basis Error!{Color.RESET}")
            print(f"    Narrowed Type : {Color.BOLD}Error{Color.RESET}")
            print(f"    Safe Fallback : {item}")


# ==============================================================================
# Simulasi Skenario 3: Discriminated Unions & Exhaustiveness (never)
# ==============================================================================
def demo_discriminated_unions() -> None:
    print_banner("SKENARIO 3: Discriminated Unions & Exhaustiveness Check (never)")
    print(f"""{Color.BRIGHT_BLACK}
    type Circle = {{ kind: "circle"; radius: number }};
    type Square = {{ kind: "square"; size: number }};
    type Shape  = Circle | Square;

    function getArea(shape: Shape): number {{
        switch (shape.kind) {{
            case "circle": return Math.PI * shape.radius ** 2;
            case "square": return shape.size ** 2;
            default:
                const _exhaustiveCheck: never = shape;
                return _exhaustiveCheck;
        }}
    }}
    {Color.RESET}""")

    shapes = [
        {"kind": "circle", "radius": 7},
        {"kind": "square", "size": 10},
        {"kind": "triangle", "base": 5, "height": 8},  # unhandled branch!
    ]

    t_circle = TypeRep("Circle", TypeKind.CUSTOM, {"kind": "circle", "radius": "number"})
    t_square = TypeRep("Square", TypeKind.CUSTOM, {"kind": "square", "size": "number"})
    shape_union = UnionType([t_circle, t_square])

    print(f"  Definisi Tipe Union: {Color.BOLD}{Color.YELLOW}{shape_union}{Color.RESET}")

    for idx, shape in enumerate(shapes, 1):
        kind = shape.get("kind")
        print(f"\n  {Color.BOLD}Evaluasi Shape [{idx}] (kind = '{kind}'):{Color.RESET}")

        if kind == "circle":
            rad = shape["radius"]
            area = 3.14159265 * (rad**2)
            print(f"    {Color.GREEN}[Case 'circle'] Narrowed -> Circle. Luas: {area:.2f}{Color.RESET}")
        elif kind == "square":
            size = shape["size"]
            area = size**2
            print(f"    {Color.GREEN}[Case 'square'] Narrowed -> Square. Luas: {area:.2f}{Color.RESET}")
        else:
            # Simulasi tsc exhaustiveness error saat ada varian tak tertangani
            print(
                f"    {Color.BRIGHT_RED}[COMPILE ERROR: Type Exhaustion Failure!]{Color.RESET}\n"
                f"    {Color.RED}Type '{kind}' tidak dapat di-assign ke tipe 'never'.{Color.RESET}\n"
                f"    {Color.DIM}CFA membuktikan branch ini reachable karena belum semua union ditangani!{Color.RESET}"
            )


# ==============================================================================
# Simulasi Skenario 4: User-Defined Type Guard (is) & Assertion Guard
# ==============================================================================
def is_fish(pet: Dict[str, Any]) -> bool:
    """Simulasi: function isFish(pet: Fish | Bird): pet is Fish"""
    return "swim" in pet and callable(pet["swim"])


def assert_is_authenticated(user: Optional[Dict[str, Any]]) -> None:
    """Simulasi: function assertAuth(user: User | null): asserts user is User"""
    if user is None:
        raise ValueError("AssertionError: User must be authenticated! (CFA halts path)")


def demo_custom_guards() -> None:
    print_banner("SKENARIO 4: User-Defined Type Predicate ('is') & Assertion Signature")
    print(f"""{Color.BRIGHT_BLACK}
    interface Fish {{ swim(): void; }}
    interface Bird {{ fly(): void; }}

    function isFish(pet: Fish | Bird): pet is Fish {{
        return (pet as Fish).swim !== undefined;
    }}
    {Color.RESET}""")

    pet_a = {"name": "Nemo", "swim": lambda: "Berenang di laut"}
    pet_b = {"name": "Hedwig", "fly": lambda: "Terbang di angkasa"}

    for p in [pet_a, pet_b]:
        p_name = p.get("name", "Unknown")
        print(f"  Menganalisis Pet '{Color.BOLD}{p_name}{Color.RESET}':")
        if is_fish(p):
            print(f"    {Color.GREEN}✔ isFish() == True ➔ Tipe menyempit menjadi: {Color.BOLD}Fish{Color.RESET}")
            print(f"    Aksi: {p['swim']()}")
        else:
            print(f"    {Color.CYAN}ℹ isFish() == False ➔ Tipe menyempit menjadi: {Color.BOLD}Bird{Color.RESET}")
            print(f"    Aksi: {p['fly']()}")

    print(f"\n{Color.BOLD}{Color.BRIGHT_BLUE}Pengujian Assertion Guard ('asserts val is T'):{Color.RESET}")
    session_user: Optional[Dict[str, str]] = None

    try:
        print("  Memeriksa token user yang bernilai null...")
        assert_is_authenticated(session_user)
        print("  Akses user diperbolehkan.")
    except ValueError as e:
        print(f"  {Color.RED}✖ CFA Cut-off: {e}{Color.RESET}")
        print(f"  {Color.DIM}Engine TypeScript menghentikan eksekusi path ini (Reachability: Unreachable){Color.RESET}")


# ==============================================================================
# Interactive Terminal Runner & Control Loop
# ==============================================================================
def run_interactive_menu() -> None:
    while True:
        print(f"\n{Color.BG_BLUE}{Color.BRIGHT_WHITE}{Color.BOLD} TS CONTROL FLOW ANALYSIS (CFA) LAB MENU {Color.RESET}")
        print(f"{Color.CYAN}1.{Color.RESET} Jalankan Simulasi 1: Built-in 'typeof' & Truthiness Guard")
        print(f"{Color.CYAN}2.{Color.RESET} Jalankan Simulasi 2: 'instanceof' Guard Hierarchy")
        print(f"{Color.CYAN}3.{Color.RESET} Jalankan Simulasi 3: Discriminated Unions & Exhaustiveness (never)")
        print(f"{Color.CYAN}4.{Color.RESET} Jalankan Simulasi 4: User-Defined Predicate ('is') & Assertion Guard")
        print(f"{Color.CYAN}5.{Color.RESET} {Color.BOLD}Jalankan Semua Skenario Sekaligus (Batch Verification){Color.RESET}")
        print(f"{Color.RED}0. Keluar{Color.RESET}")

        try:
            choice = input(f"\n{Color.BOLD}Pilih opsi [0-5]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Color.YELLOW}Sesi lab diakhiri.{Color.RESET}")
            break

        if choice == "1":
            demo_typeof_guard()
        elif choice == "2":
            demo_instanceof_guard()
        elif choice == "3":
            demo_discriminated_unions()
        elif choice == "4":
            demo_custom_guards()
        elif choice == "5":
            demo_typeof_guard()
            time.sleep(0.3)
            demo_instanceof_guard()
            time.sleep(0.3)
            demo_discriminated_unions()
            time.sleep(0.3)
            demo_custom_guards()
            print(f"\n{Color.BRIGHT_GREEN}✔ Semua modul uji CFA berhasil disimulasikan secara valid!{Color.RESET}")
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih telah menggunakan TS-CFA Lab Simulator!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan masukkan nomor 0-5.{Color.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        demo_typeof_guard()
        demo_instanceof_guard()
        demo_discriminated_unions()
        demo_custom_guards()
        print(f"\n{Color.BRIGHT_GREEN}✔ Batch execution complete!{Color.RESET}")
    else:
        run_interactive_menu()
