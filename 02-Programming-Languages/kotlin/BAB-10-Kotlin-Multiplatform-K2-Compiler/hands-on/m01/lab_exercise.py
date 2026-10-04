#!/usr/bin/env python3
"""
Lab Exercise M01: Kotlin 2.0 (K2) Compiler & Kotlin Multiplatform (KMP) Architecture Simulator
BAB-10: Kotlin Multiplatform & K2 Compiler Pipeline

Simulates the K2 compilation stages:
1. Lexical & Syntax Analysis -> PSI (Program Structure Interface)
2. Frontend IR (FIR) Resolution & Type Inference
3. Expect / Actual Contract Verification across KMP Source Sets
4. Backend IR Lowering & Target Code Generation (JVM, Native LLVM, Wasm/JS)
"""

import sys
import time
from typing import Dict, List, Optional, Tuple

# ANSI Terminal Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_BLUE = "\033[44m"
WHITE = "\033[97m"

def print_banner():
    print(f"{BOLD}{BG_BLUE}{WHITE}  KOTLIN K2 COMPILER & KMP PIPELINE SIMULATOR  {RESET}")
    print(f"{CYAN}Module 01: Frontend IR (FIR), Expect/Actual Matching & Backend Lowering{RESET}\n")

class SourceSymbol:
    def __init__(self, name: str, symbol_type: str, signature: str, is_expect: bool = False, is_actual: bool = False):
        self.name = name
        self.symbol_type = symbol_type
        self.signature = signature
        self.is_expect = is_expect
        self.is_actual = is_actual

class TargetArtifact:
    def __init__(self, target_name: str, backend_engine: str, output_ext: str):
        self.target_name = target_name
        self.backend_engine = backend_engine
        self.output_ext = output_ext

class K2CompilerSimulation:
    def __init__(self):
        self.targets = {
            "jvm": TargetArtifact("Kotlin/JVM", "JVM Bytecode Generator (IR-based)", ".class / .jar"),
            "iosX64": TargetArtifact("Kotlin/Native (iOS x64)", "LLVM Bitcode + Clang Toolchain", ".klib / .framework"),
            "wasmJs": TargetArtifact("Kotlin/Wasm", "Binaryen / Wasm GC CodeGen", ".wasm")
        }
        self.common_expect_symbols: List[SourceSymbol] = []
        self.platform_actual_symbols: Dict[str, List[SourceSymbol]] = {
            "jvm": [],
            "iosX64": [],
            "wasmJs": []
        }
        self._init_default_kmp_project()

    def _init_default_kmp_project(self):
        # commonMain declarations
        self.common_expect_symbols = [
            SourceSymbol("getPlatformName", "function", "fun getPlatformName(): String", is_expect=True),
            SourceSymbol("HttpClientEngine", "class", "expect class HttpClientEngine()", is_expect=True),
            SourceSymbol("getSystemEntropy", "function", "fun getSystemEntropy(): ByteArray", is_expect=True),
        ]
        
        # jvmMain actuals
        self.platform_actual_symbols["jvm"] = [
            SourceSymbol("getPlatformName", "function", "actual fun getPlatformName(): String", is_actual=True),
            SourceSymbol("HttpClientEngine", "class", "actual class HttpClientEngine()", is_actual=True),
            SourceSymbol("getSystemEntropy", "function", "actual fun getSystemEntropy(): ByteArray", is_actual=True),
        ]
        
        # iosX64 actuals (missing entropy to demonstrate diagnostic)
        self.platform_actual_symbols["iosX64"] = [
            SourceSymbol("getPlatformName", "function", "actual fun getPlatformName(): String", is_actual=True),
            SourceSymbol("HttpClientEngine", "class", "actual class HttpClientEngine()", is_actual=True),
        ]

        # wasmJs actuals
        self.platform_actual_symbols["wasmJs"] = [
            SourceSymbol("getPlatformName", "function", "actual fun getPlatformName(): String", is_actual=True),
            SourceSymbol("HttpClientEngine", "class", "actual class HttpClientEngine()", is_actual=True),
            SourceSymbol("getSystemEntropy", "function", "actual fun getSystemEntropy(): ByteArray", is_actual=True),
        ]

    def display_project_structure(self):
        print(f"{BOLD}{YELLOW}[+] Current KMP Project Source Sets Hierarchy:{RESET}")
        print(f"  {MAGENTA}commonMain{RESET} (Shared Business Logic & Expect Declarations)")
        for sym in self.common_expect_symbols:
            print(f"    ├─ [expect] {CYAN}{sym.signature}{RESET}")
        
        for target, actuals in self.platform_actual_symbols.items():
            print(f"  {BLUE}{target}Main{RESET} (Platform Implementation)")
            for act in actuals:
                print(f"    ├─ [actual] {GREEN}{act.signature}{RESET}")
        print()

    def run_k2_frontend(self) -> bool:
        print(f"{BOLD}{BLUE}[Phase 1] K2 Frontend IR (FIR) Resolution & Smart Casts Analysis...{RESET}")
        stages = [
            ("Raw FIR Generation", "Building FIR tree from AST & PSI structures..."),
            ("Imports & Scope Building", "Resolving package scopes & star imports..."),
            ("Type Supertype Resolution", "Validating inheritance hierarchy & sealed classes..."),
            ("Body Resolution & Flow Analysis", "Smart casting, contract validation & lambda returns...")
        ]
        for name, desc in stages:
            print(f"  {DIM}-->{RESET} {BOLD}{name}:{RESET} {desc}", end=" ", flush=True)
            time.sleep(0.18)
            print(f"[{GREEN}OK{RESET}]")
        print(f"{GREEN}✓ K2 Frontend IR built with zero resolution errors (Speedup vs K1: ~2.1x){RESET}\n")
        return True

    def run_expect_actual_matching(self) -> Dict[str, List[str]]:
        print(f"{BOLD}{BLUE}[Phase 2] Multiplatform Expect/Actual Consistency Verification...{RESET}")
        diagnostics = {}

        for target_key, actual_list in self.platform_actual_symbols.items():
            missing_symbols = []
            actual_names = {s.name for s in actual_list}
            
            print(f"  Checking target {BOLD}{target_key}{RESET}:")
            for expect_sym in self.common_expect_symbols:
                if expect_sym.name not in actual_names:
                    missing_symbols.append(expect_sym.name)
                    print(f"    {RED}✘ Missing actual for expect declaration: '{expect_sym.name}'{RESET}")
                else:
                    print(f"    {GREEN}✔ Matched expect '{expect_sym.name}' with actual counterpart.{RESET}")

            diagnostics[target_key] = missing_symbols

        print()
        return diagnostics

    def run_backend_lowering(self, diagnostics: Dict[str, List[str]]):
        print(f"{BOLD}{BLUE}[Phase 3] Backend IR Lowering & Code Generation...{RESET}")
        for target_key, artifact in self.targets.items():
            issues = diagnostics.get(target_key, [])
            print(f"  Target: {BOLD}{artifact.target_name}{RESET} via {DIM}{artifact.backend_engine}{RESET}")
            if issues:
                print(f"    {RED}Compilation FAILED: Unresolved expect/actual declarations: {issues}{RESET}")
                print(f"    {YELLOW}Diagnostic code: [NO_ACTUAL_FOR_EXPECT]{RESET}")
            else:
                print(f"    Generating target artifact: {GREEN}build/bin/{target_key}/app{artifact.output_ext}{RESET}")
                print(f"    {GREEN}✔ Target compilation finished successfully.{RESET}")
        print()

    def fix_ios_actual_symbol(self):
        print(f"{YELLOW}[!] Patching iosX64Main with missing 'getSystemEntropy' actual implementation...{RESET}")
        self.platform_actual_symbols["iosX64"].append(
            SourceSymbol("getSystemEntropy", "function", "actual fun getSystemEntropy(): ByteArray (via SecRandomCopyBytes)", is_actual=True)
        )
        time.sleep(0.3)
        print(f"{GREEN}✔ iosX64Main updated successfully.{RESET}\n")

def interactive_loop():
    print_banner()
    sim = K2CompilerSimulation()

    while True:
        print(f"{BOLD}=== Interactive Options ==={RESET}")
        print(f" {CYAN}1.{RESET} View Project Source Sets & Contracts (commonMain vs targets)")
        print(f" {CYAN}2.{RESET} Run K2 Full Compilation Pipeline")
        print(f" {CYAN}3.{RESET} Inject Missing 'actual' in iosX64 Source Set")
        print(f" {CYAN}4.{RESET} Explain K2 Architecture & Performance Benefits")
        print(f" {CYAN}5.{RESET} Exit Simulation")
        
        choice = input(f"\n{BOLD}Select an action [1-5]: {RESET}").strip()
        print("-" * 65)

        if choice == "1":
            sim.display_project_structure()
        elif choice == "2":
            sim.run_k2_frontend()
            diags = sim.run_expect_actual_matching()
            sim.run_backend_lowering(diags)
        elif choice == "3":
            sim.fix_ios_actual_symbol()
        elif choice == "4":
            print(f"{BOLD}{MAGENTA}K2 Compiler Architecture Highlights:{RESET}")
            print(f"  1. {BOLD}Unified Backend IR:{RESET} Single Kotlin IR intermediate representation for JVM, Native, JS, and Wasm.")
            print(f"  2. {BOLD}FIR (Frontend Intermediate Representation):{RESET} Desugars language features early, avoiding AST duplications.")
            print(f"  3. {BOLD}Parallel Analysis:{RESET} Up to 2x faster build times on multi-core workstations.")
            print(f"  4. {BOLD}Contract-Driven Smart Casts:{RESET} More precise flow analysis with fewer required explicit assertions.")
            print("-" * 65 + "\n")
        elif choice == "5" or choice.lower() in ("exit", "quit"):
            print(f"{GREEN}Exiting K2 Multiplatform Simulation. Selamat belajar!{RESET}")
            break
        else:
            print(f"{RED}Invalid selection. Please choose options 1 to 5.{RESET}\n")

if __name__ == "__main__":
    try:
        interactive_loop()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Simulation interrupted by user. Goodbye!{RESET}")
        sys.exit(0)
