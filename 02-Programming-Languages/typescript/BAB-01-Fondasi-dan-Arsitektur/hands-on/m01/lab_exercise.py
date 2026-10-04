#!/usr/bin/env python3
"""
Lab Exercise M01: TypeScript Compiler & Architecture Simulator
BAB-01: Fondasi dan Arsitektur TypeScript

Simulasi interaktif 5 pilar arsitektur tsc (TypeScript Compiler):
1. Scanner / Lexer (Tokenisasi source code)
2. Parser & AST Builder (Struktur pohon sintaksis)
3. Binder & Symbol Table (Resolusi scoping dan simbol)
4. Type Checker & Structural Subtyping (Duck typing validation)
5. Emitter & Type Erasure (Kompilasi TS -> JS)
"""

import sys
import time
from typing import Dict, List, Any, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"


def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{CYAN} [TSC PIPELINE] {title.upper()}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")


class Token:
    def __init__(self, token_type: str, value: str, line: int):
        self.type = token_type
        self.value = value
        self.line = line

    def __repr__(self) -> str:
        return f"{MAGENTA}{self.type}{RESET}({YELLOW}'{self.value}'{RESET})"


class MiniScanner:
    """Simulasi Scanner/Lexer TypeScript."""

    KEYWORDS = {"type", "interface", "let", "const", "string", "number", "boolean", "function"}

    def __init__(self, code: str):
        self.code = code
        self.tokens: List[Token] = []

    def scan(self) -> List[Token]:
        lines = self.code.strip().split("\n")
        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue

            # Tokenisasi sederhana berdasarkan spasi & delimiters
            cleaned = line.replace(":", " : ").replace(";", " ; ").replace("{", " { ").replace("}", " } ")
            parts = cleaned.split()
            for part in parts:
                if part in self.KEYWORDS:
                    t_type = "Keyword"
                elif part in {":", ";", "{", "}", "=", "(", ")"}:
                    t_type = "Punctuation"
                elif part.isdigit():
                    t_type = "NumericLiteral"
                elif part.startswith('"') or part.startswith("'"):
                    t_type = "StringLiteral"
                else:
                    t_type = "Identifier"
                self.tokens.append(Token(t_type, part, line_num))
        return self.tokens


class StructuralTypeChecker:
    """Simulasi Type Checker TypeScript dengan sistem Structural Typing (Duck Typing)."""

    def __init__(self):
        self.type_definitions: Dict[str, Dict[str, str]] = {}

    def register_interface(self, name: str, fields: Dict[str, str]) -> None:
        self.type_definitions[name] = fields
        print(f"  {GREEN}✔ Registered Interface:{RESET} {BOLD}{name}{RESET} -> {fields}")

    def check_assignability(self, source_name: str, source_obj: Dict[str, Any], target_type: str) -> bool:
        """Memvalidasi apakah source_obj memenuhi kontrak target_type (Subtyping)."""
        print(f"\n{BOLD}Memeriksa Assignability:{RESET} {YELLOW}{source_name}{RESET} -> {CYAN}{target_type}{RESET}")
        time.sleep(0.3)

        if target_type not in self.type_definitions:
            print(f"  {RED}✖ Type Error:{RESET} Tipe target '{target_type}' tidak ditemukan!")
            return False

        target_schema = self.type_definitions[target_type]
        missing_keys = []
        mismatched_types = []

        for req_prop, req_type in target_schema.items():
            if req_prop not in source_obj:
                missing_keys.append(req_prop)
                continue

            val = source_obj[req_prop]
            actual_type = "number" if isinstance(val, (int, float)) else "string" if isinstance(val, str) else "boolean"
            if actual_type != req_type:
                mismatched_types.append((req_prop, req_type, actual_type))

        if missing_keys:
            print(f"  {RED}✖ TS2741 Error:{RESET} Properti {missing_keys} wajib ada di '{target_type}'!")
            return False

        if mismatched_types:
            for prop, expected, actual in mismatched_types:
                print(f"  {RED}✖ TS2322 Error:{RESET} Tipe '{actual}' tidak dapat di-assign ke tipe '{expected}' pada field '{prop}'.")
            return False

        excess_keys = [k for k in source_obj.keys() if k not in target_schema]
        if excess_keys:
            print(f"  {BLUE}ℹ Structural Subtyping (Duck Typing):{RESET} Objek memiliki field tambahan {excess_keys}, namun tetap assignable karena memenuhi semua kontrak target.")

        print(f"  {GREEN}✔ Type Check PASSED!{RESET} Struktur valid secara kompatibilitas tipe.")
        return True


class MiniEmitter:
    """Simulasi Transpiler TypeScript: Type Erasure & Emit JavaScript."""

    def __init__(self, ts_code: str):
        self.ts_code = ts_code

    def emit_js(self) -> str:
        """Melakukan eliminasi type annotations (Type Erasure) sederhana."""
        lines = self.ts_code.strip().split("\n")
        js_lines = []
        in_type_declaration = False

        for line in lines:
            line_str = line.strip()
            # 1. Deteksi blok type & interface untuk dihapus total
            if line_str.startswith("type ") or line_str.startswith("interface "):
                in_type_declaration = True
                continue
            if in_type_declaration:
                if line_str.endswith("}"):
                    in_type_declaration = False
                continue

            # 2. Hapus anotasi tipe ': string', ': number', dll
            for type_kw in [": string", ": number", ": boolean", ": User"]:
                line_str = line_str.replace(type_kw, "")

            if line_str:
                js_lines.append(line_str)

        return "\n".join(js_lines)


def run_pipeline_demo() -> None:
    sample_ts = """
interface User {
    id: number;
    username: string;
}

let activeUser: User = {
    id: 101,
    username: "alex",
    role: "admin"
};
"""

    print(f"{BOLD}{MAGENTA}=== SIMULASI TS ARSITEKTUR & PIPELINE INTERAKTIF ==={RESET}\n")
    print(f"{DIM}Kode Sumber TypeScript yang akan dianalisis:{RESET}")
    print(f"{YELLOW}{sample_ts.strip()}{RESET}\n")

    # Tahap 1: Scanner
    print_header("Fase 1: Scanner & Lexical Analysis")
    scanner = MiniScanner(sample_ts)
    tokens = scanner.scan()
    print(f"Dihasilkan {BOLD}{len(tokens)}{RESET} tokens:")
    print(" ".join(str(t) for t in tokens[:12]) + " ...\n")
    time.sleep(0.4)

    # Tahap 2 & 3: Parser & Binder
    print_header("Fase 2 & 3: Parser (AST) & Binder (Symbol Table)")
    print(f"  {GREEN}✔ AST Node Created:{RESET} SourceFile -> InterfaceDeclaration ('User')")
    print(f"  {GREEN}✔ AST Node Created:{RESET} VariableStatement -> VariableDeclaration ('activeUser')")
    print(f"  {BLUE}✔ Symbol Bound:{RESET} Symbol('User', Flags.Interface)")
    print(f"  {BLUE}✔ Symbol Bound:{RESET} Symbol('activeUser', Flags.BlockScopedVariable)")
    time.sleep(0.4)

    # Tahap 4: Type Checker
    print_header("Fase 4: Type Checker (Structural Assignability)")
    checker = StructuralTypeChecker()
    checker.register_interface("User", {"id": "number", "username": "string"})

    # Validasi objek dengan structural duck typing (memiliki extra field 'role')
    user_object_valid = {"id": 101, "username": "alex", "role": "admin"}
    checker.check_assignability("activeUser (Object Literal)", user_object_valid, "User")

    # Uji coba objek invalid (salah tipe data)
    user_object_invalid = {"id": "NOT_A_NUMBER", "username": "alex"}
    checker.check_assignability("invalidUser (Type Mismatch)", user_object_invalid, "User")
    time.sleep(0.4)

    # Tahap 5: Emitter (Type Erasure)
    print_header("Fase 5: Emitter & Type Erasure (Emit JS)")
    print(f"{DIM}TypeScript menghapus seluruh anotasi tipe saat runtime (Zero Runtime Overhead).{RESET}\n")
    emitter = MiniEmitter(sample_ts)
    compiled_js = emitter.emit_js()

    print(f"{BOLD}{GREEN}[Output JavaScript]:{RESET}")
    print(f"{CYAN}{compiled_js}{RESET}\n")

    print(f"{BOLD}{GREEN}✓ Pipeline simulasi arsitektur TypeScript selesai dieksekusi dengan sukses!{RESET}\n")


def interactive_menu() -> None:
    while True:
        print(f"{BOLD}Pilih Mode Simulasi:{RESET}")
        print("  1. Jalankan Seluruh Pipeline TSC (Scanner -> Parser -> Checker -> Emitter)")
        print("  2. Uji Coba Structural Typing (Duck Typing) Custom")
        print("  3. Keluar")
        choice = input(f"{YELLOW}Masukkan pilihan (1-3) [default: 1]: {RESET}").strip()

        if choice in ("", "1"):
            run_pipeline_demo()
            break
        elif choice == "2":
            checker = StructuralTypeChecker()
            checker.register_interface("Product", {"name": "string", "price": "number"})
            test_obj = {"name": "Laptop", "price": 1500, "inStock": True}
            checker.check_assignability("CustomProduct", test_obj, "Product")
            break
        elif choice == "3":
            print("Keluar dari simulator.")
            break
        else:
            print(f"{RED}Pilihan tidak valid, coba lagi.{RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--non-interactive":
        run_pipeline_demo()
    else:
        # Jalankan demo pipeline secara langsung dan interaktif
        run_pipeline_demo()
