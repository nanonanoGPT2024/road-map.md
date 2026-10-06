#!/usr/bin/env python3
"""
Lab Exercise: Ambient Context & Declaration Files (.d.ts) Simulator
BAB 08: TypeScript Ambient Context & Declaration Files

Simulasi teknis konsep fondasi ambient context pada TypeScript:
1. Ambient Symbol Table & Zero-Emit Verification (Type-only, 0 bytes runtime output)
2. Ambient Script vs Module Context (Deteksi top-level import/export)
3. Declaration Merging (Interface & Namespace Augmentation)
4. Ambient Module & Wildcard Resolution (declare module "..." & declare module "*.svg")
5. Global Augmentation (declare global { ... })
"""

import sys
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

# --- Terminal ANSI Color Constants ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    # Background colors
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[40m"


def header(title: str) -> None:
    line = "=" * 65
    print(f"\n{Style.CYAN}{Style.BOLD}{line}")
    print(f"  {title.upper()}")
    print(f"{line}{Style.RESET}\n")


def subheader(title: str) -> None:
    print(f"\n{Style.YELLOW}{Style.BOLD}--- {title} ---{Style.RESET}")


def info(msg: str) -> None:
    print(f"{Style.BLUE}[INFO]{Style.RESET} {msg}")


def success(msg: str) -> None:
    print(f"{Style.GREEN}[SUCCESS]{Style.RESET} {msg}")


def warning(msg: str) -> None:
    print(f"{Style.YELLOW}[WARNING]{Style.RESET} {msg}")


def error(msg: str) -> None:
    print(f"{Style.RED}[ERROR]{Style.RESET} {msg}")


# --- Domain Models: TypeScript Ambient Context Representation ---

@dataclass
class TypeProperty:
    name: str
    type_sig: str
    is_optional: bool = False
    is_readonly: bool = False


@dataclass
class AmbientDeclaration:
    identifier: str
    kind: str  # 'var', 'const', 'function', 'class', 'interface', 'namespace', 'module'
    type_signature: str
    source_file: str
    is_ambient: bool = True
    properties: Dict[str, TypeProperty] = field(default_factory=dict)

    def emit_javascript(self) -> str:
        """TypeScript ambient declarations produce exactly ZERO runtime JS bytes."""
        if self.is_ambient:
            return ""  # Zero-Emit Guarantee
        return f"var {self.identifier} = ...; // Transpiled JS"


@dataclass
class SourceFile:
    filename: str
    content: str
    is_dts: bool
    is_external_module: bool = False
    reference_tags: List[str] = field(default_factory=list)
    declarations: List[AmbientDeclaration] = field(default_factory=list)

    def analyze_module_kind(self) -> None:
        """
        TypeScript rule: A file is an external module if and only if it contains
        at least one top-level 'import' or 'export' statement. Otherwise, it is
        treated as an ambient script living in the global namespace.
        """
        lines = [line.strip() for line in self.content.splitlines()]
        has_import_export = any(
            line.startswith("import ") or
            line.startswith("export ") or
            line.startswith("export {") or
            line.startswith("import {")
            for line in lines
        )
        self.is_external_module = has_import_export


# --- TypeScript Type Checker & Ambient Resolver Engine ---

class AmbientContextEngine:
    def __init__(self):
        # Global symbol table (ambient scope)
        self.global_symbols: Dict[str, AmbientDeclaration] = {}
        # External module definitions: 'module_name' -> Dict[export_name, AmbientDeclaration]
        self.ambient_modules: Dict[str, Dict[str, AmbientDeclaration]] = {}
        # Wildcard module patterns (e.g. '*.css', '*.svg')
        self.wildcard_modules: Dict[str, str] = {}
        # Registered source files
        self.files: Dict[str, SourceFile] = {}

    def register_file(self, filename: str, content: str) -> SourceFile:
        is_dts = filename.endswith(".d.ts")
        sf = SourceFile(filename=filename, content=content, is_dts=is_dts)
        sf.analyze_module_kind()
        
        # Scan triple-slash reference directives: /// <reference path="..." /> or <reference types="..." />
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("/// <reference"):
                sf.reference_tags.append(line_str)

        self.files[filename] = sf
        return sf

    def declare_ambient_var(self, file: SourceFile, name: str, type_sig: str, kind: str = "const") -> None:
        decl = AmbientDeclaration(
            identifier=name,
            kind=kind,
            type_signature=type_sig,
            source_file=file.filename,
            is_ambient=True
        )
        file.declarations.append(decl)
        
        # If file is not an external module, symbol enters global ambient scope
        if not file.is_external_module:
            self.global_symbols[name] = decl
        else:
            warning(f"File '{file.filename}' is a module! Ambient 'declare' without 'declare global' is module-scoped.")

    def declare_interface(self, file: SourceFile, name: str, properties: Dict[str, str]) -> None:
        """Simulates Declaration Merging on interfaces."""
        if name in self.global_symbols and self.global_symbols[name].kind == "interface":
            # Declaration Merging occurs!
            target = self.global_symbols[name]
            for p_name, p_type in properties.items():
                target.properties[p_name] = TypeProperty(name=p_name, type_sig=p_type)
            info(f"Declaration Merging applied for interface '{Style.BOLD}{name}{Style.RESET}' from {file.filename}")
        else:
            decl = AmbientDeclaration(
                identifier=name,
                kind="interface",
                type_signature=f"interface {name}",
                source_file=file.filename,
                is_ambient=True
            )
            for p_name, p_type in properties.items():
                decl.properties[p_name] = TypeProperty(name=p_name, type_sig=p_type)
            self.global_symbols[name] = decl
            file.declarations.append(decl)

    def declare_ambient_module(self, module_name: str, exports: Dict[str, str]) -> None:
        """Simulates `declare module 'express'` or wildcard `declare module '*.png'`."""
        if "*" in module_name:
            self.wildcard_modules[module_name] = "Record<string, any>"
            info(f"Wildcard ambient module registered: {Style.MAGENTA}{module_name}{Style.RESET}")
            return

        if module_name not in self.ambient_modules:
            self.ambient_modules[module_name] = {}

        for sym_name, sym_type in exports.items():
            self.ambient_modules[module_name][sym_name] = AmbientDeclaration(
                identifier=sym_name,
                kind="export",
                type_signature=sym_type,
                source_file="<ambient-module-block>",
                is_ambient=True
            )
        info(f"Ambient module registered: {Style.MAGENTA}'{module_name}'{Style.RESET} with {len(exports)} export(s).")

    def resolve_type(self, identifier: str, caller_file: Optional[SourceFile] = None) -> Optional[AmbientDeclaration]:
        """Resolves identifier from global ambient scope."""
        return self.global_symbols.get(identifier)

    def resolve_module_import(self, module_specifier: str, import_symbol: str) -> Optional[str]:
        """Resolves import from ambient modules or wildcard definitions."""
        if module_specifier in self.ambient_modules:
            mod = self.ambient_modules[module_specifier]
            if import_symbol in mod:
                return mod[import_symbol].type_signature
            return None

        # Wildcard check (e.g. '*.svg', '*.css')
        for pattern, type_sig in self.wildcard_modules.items():
            prefix, ext = pattern.split("*")
            if module_specifier.endswith(ext):
                return type_sig

        return None


# --- Interactive Simulation Experiments ---

def experiment_zero_emit(engine: AmbientContextEngine) -> None:
    header("Eksperimen 1: Zero-Emit Guarantee (.d.ts & declare)")
    print(f"{Style.BOLD}Konsep Inti:{Style.RESET}")
    print("TypeScript compiler (tsc) tidak pernah menghasilkan kode JavaScript untuk")
    print("konstruksi ambient (`declare var`, `declare function`, `.d.ts`).")
    print("Semua deklarasi ambient murni type-only metadata saat compile time.\n")

    code_snippet = """// globals.d.ts
declare const __API_VERSION__: string;
declare function getAuthToken(): string;
declare interface AppConfig {
    debug: boolean;
    timeoutMs: number;
}
"""
    print(f"{Style.DIM}{code_snippet}{Style.RESET}")

    sf = engine.register_file("globals.d.ts", code_snippet)
    engine.declare_ambient_var(sf, "__API_VERSION__", "string", kind="const")
    engine.declare_ambient_var(sf, "getAuthToken", "() => string", kind="function")
    engine.declare_interface(sf, "AppConfig", {"debug": "boolean", "timeoutMs": "number"})

    print(f"Memeriksa emisi JavaScript untuk {len(sf.declarations)} deklarasi...")
    total_emitted_bytes = sum(len(d.emit_javascript().encode("utf-8")) for d in sf.declarations)

    time.sleep(0.3)
    if total_emitted_bytes == 0:
        success(f"Transpiled JS size: {Style.BOLD}{total_emitted_bytes} bytes!{Style.RESET}")
        print(f"  {Style.GREEN}✔ Zero-Emit terverifikasi: Seluruh token ambient context dieliminasi saat runtime.{Style.RESET}")
    else:
        error(f"Terjadi kesalahan: Emitted {total_emitted_bytes} bytes.")


def experiment_ambient_vs_module(engine: AmbientContextEngine) -> None:
    header("Eksperimen 2: Ambient Script Context vs External Module Context")
    print(f"{Style.BOLD}Aturan TypeScript:{Style.RESET}")
    print("1. File TANPA top-level import/export -> Global Ambient Script.")
    print("2. File DENGAN top-level import/export -> External Module (Scoping terisolasi).")
    print("   Untuk mengekspos tipe ke global dari module, harus menggunakan 'declare global { ... }'.\n")

    script_code = """// analytics.d.ts
declare const trackEvent: (name: string, payload: any) => void;
"""
    module_code = """// logger.ts
import { Logger } from './vendor';
declare const internalLogLevel: number; // Tidak bocor ke global!
export const log = (msg: string) => console.log(msg);
"""
    sf_script = engine.register_file("analytics.d.ts", script_code)
    sf_mod = engine.register_file("logger.ts", module_code)

    info(f"File 1: {sf_script.filename} -> External Module: {sf_script.is_external_module}")
    info(f"File 2: {sf_mod.filename} -> External Module: {sf_mod.is_external_module}")

    engine.declare_ambient_var(sf_script, "trackEvent", "(name: string, payload: any) => void")
    engine.declare_ambient_var(sf_mod, "internalLogLevel", "number")

    # Lookup test
    res1 = engine.resolve_type("trackEvent")
    res2 = engine.resolve_type("internalLogLevel")

    print("\nHasil Resolusi Global Scope:")
    if res1:
        success(f"'trackEvent' ditemukan di global scope! (Type: {res1.type_signature})")
    else:
        error("'trackEvent' gagal diselesaikan.")

    if not res2:
        success(f"'internalLogLevel' TIDAK bocor ke global scope karena didefinisikan dalam module!")
    else:
        warning("'internalLogLevel' bocor ke global scope.")


def experiment_declaration_merging(engine: AmbientContextEngine) -> None:
    header("Eksperimen 3: Declaration Merging & Global Augmentation")
    print(f"{Style.BOLD}Konsep Inti:{Style.RESET}")
    print("Interface TypeScript bersifat 'open-ended'. Dua interface dengan nama yang sama")
    print("pada scope yang sama akan otomatis digabung (merged).")
    print("Teknik ini adalah fondasi penambahan properti baru pada `Window`, `ProcessEnv`, atau DOM.\n")

    # Base definition
    sf_base = engine.register_file("lib.dom.d.ts", "interface Window { readonly document: Document; }")
    engine.declare_interface(sf_base, "Window", {"document": "Document"})

    # Augmentation
    sf_ext = engine.register_file("custom-window.d.ts", """
    interface Window {
        __REDUX_DEVTOOLS_EXTENSION__: any;
        appConfig: { apiUrl: string; retryCount: number };
    }
    """)
    engine.declare_interface(sf_ext, "Window", {
        "__REDUX_DEVTOOLS_EXTENSION__": "any",
        "appConfig": "{ apiUrl: string; retryCount: number }"
    })

    win_decl = engine.resolve_type("Window")
    if win_decl:
        print(f"\n{Style.BOLD}Hasil Penggabungan Interface Window:{Style.RESET}")
        for p_name, prop in win_decl.properties.items():
            print(f"  • {Style.CYAN}window.{p_name}{Style.RESET}: {Style.YELLOW}{prop.type_sig}{Style.RESET}")
        
        expected_props = {"document", "__REDUX_DEVTOOLS_EXTENSION__", "appConfig"}
        if set(win_decl.properties.keys()) == expected_props:
            success("Declaration Merging berhasil 100%! Semua properti tergabung sempurna.")
        else:
            error("Properties tidak lengkap sesuai ekspektasi.")


def experiment_ambient_modules(engine: AmbientContextEngine) -> None:
    header("Eksperimen 4: Ambient Module & Wildcard Asset Shims")
    print(f"{Style.BOLD}Konsep Inti:{Style.RESET}")
    print("Ketika mengimpor modul tanpa deklarasi tipe (JS murni) atau asset statis non-JS (.png, .css),")
    print("TypeScript membutuhkan `declare module 'pkg'` atau wildcard `declare module '*.svg'`.\n")

    # Registering third-party ambient module
    engine.declare_ambient_module("fast-math", {
        "calculateVariance": "(nums: number[]) => number",
        "DEFAULT_PRECISION": "number"
    })

    # Registering wildcard module for SVG
    engine.declare_ambient_module("*.svg", {})

    print(f"\n{Style.BOLD}Pengujian Type Checker Import:{Style.RESET}")

    # Test 1: named import from fast-math
    t1 = engine.resolve_module_import("fast-math", "calculateVariance")
    if t1:
        success(f"import {{ calculateVariance }} from 'fast-math' -> Valid! (Type: {t1})")
    else:
        error("Import dari 'fast-math' gagal!")

    # Test 2: unknown export from fast-math
    t2 = engine.resolve_module_import("fast-math", "nonExistentMethod")
    if t2 is None:
        success("import { nonExistentMethod } from 'fast-math' -> Ditangkal compiler (Type Error: Module has no exported member).")

    # Test 3: Wildcard asset import
    t3 = engine.resolve_module_import("./assets/logo.svg", "default")
    if t3:
        success(f"import logo from './assets/logo.svg' -> Ter-resolve melalui wildcard '*.svg' (Type: {t3})")
    else:
        error("Wildcard import *.svg gagal!")


def run_full_interactive_cli() -> None:
    engine = AmbientContextEngine()
    
    print(f"{Style.BOLD}{Style.BG_BLUE}{Style.WHITE} TS AMBIENT CONTEXT & DECLARATION FILES SIMULATOR (.d.ts) {Style.RESET}")
    print(f"{Style.DIM}TypeScript Architecture Interactive Diagnostic Tool{Style.RESET}\n")

    menu = """Pilih simulasi konsep:
[1] Uji Zero-Emit Guarantee (declare const / .d.ts emit 0 bytes)
[2] Uji Ambient Script vs Module Context Scoping
[3] Uji Declaration Merging & Global Window Augmentation
[4] Uji Ambient Module ('declare module') & Wildcard Asset Shims
[5] Jalankan Seluruh Pengujian Sekaligus (Automated Full Suite)
[q] Keluar dari Lab Exercise
"""

    if not sys.stdin.isatty():
        # Non-interactive mode (e.g. CI/script runner)
        info("Mode non-interaktif terdeteksi. Menjalankan seluruh pengujian otomatis...")
        experiment_zero_emit(engine)
        experiment_ambient_vs_module(engine)
        experiment_declaration_merging(engine)
        experiment_ambient_modules(engine)
        header("Semua Lab Simulation Selesai dengan Sukses!")
        return

    while True:
        print(f"\n{Style.MAGENTA}{menu}{Style.RESET}")
        try:
            choice = input(f"{Style.BOLD}Pilihan Anda (1-5, q): {Style.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar...")
            break

        if choice == "1":
            experiment_zero_emit(engine)
        elif choice == "2":
            experiment_ambient_vs_module(engine)
        elif choice == "3":
            experiment_declaration_merging(engine)
        elif choice == "4":
            experiment_ambient_modules(engine)
        elif choice == "5":
            experiment_zero_emit(engine)
            experiment_ambient_vs_module(engine)
            experiment_declaration_merging(engine)
            experiment_ambient_modules(engine)
            header("Semua Lab Simulation Selesai dengan Sukses!")
        elif choice.lower() in ("q", "quit", "exit"):
            print("Keluar dari lab simulation. Sampai jumpa!")
            break
        else:
            warning("Pilihan tidak valid. Silakan masukkan angka 1-5 atau 'q'.")


if __name__ == "__main__":
    run_full_interactive_cli()
