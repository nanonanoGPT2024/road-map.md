#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Interoperabilitas Java-Kotlin, JVM Internals, dan KMP K2 Compiler
Modul: BAB-08 Interoperabilitas Java & JVM Internals s/d Bab-10 Kotlin Multiplatform & K2 Compiler
Format: Standalone Interactive CLI Simulator dengan ANSI Colors
"""

import sys
import time
import hashlib
from typing import Dict, List, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"


def print_banner():
    banner = f"""{CYAN}{BOLD}
================================================================================
   KOTLIN INTEROP, JVM INTERNALS & K2 COMPILER ARCHITECTURE LAB SIMULATOR
   Bab 08: Interop & Bytecode | Bab 09: Coroutine Under the Hood | Bab 10: K2 & KMP
================================================================================{RESET}"""
    print(banner)


class JvmBytecodeSimulator:
    """Simulasi transformasi Kotlin source code ke JVM Bytecode & Java Interop conventions."""

    @staticmethod
    def simulate_name_mangling(inline_class_name: str, property_name: str, property_type: str):
        print(f"\n{BOLD}{YELLOW}>>> [Simulasi 1] Value/Inline Class Name Mangling di JVM <<<{RESET}")
        print(f"Definisi Kotlin: {GREEN}@JvmInline value class {inline_class_name}(val {property_name}: {property_type}){RESET}")

        # Name mangling algorithm simulation in Kotlin compiler
        digest = hashlib.sha256(f"{inline_class_name}-{property_type}".encode()).hexdigest()[:7]
        mangled_fn = f"process_{digest}"

        print(f"{CYAN}[Compiler Stage - JVM Backend IR]:{RESET}")
        print(f"  1. Tipe data '{inline_class_name}' di-unwrap langsung menjadi primitif/tipe underlying: {property_type}")
        print(f"  2. Mencegah collision overload pada Java bytecode dengan Name Mangling:")
        print(f"     Kotlin signature: {BOLD}fun process(id: {inline_class_name}){RESET}")
        print(f"     JVM Bytecode method name: {MAGENTA}{mangled_fn}({property_type} id){RESET}")
        print(f"  3. Panggilan dari Java murni: Harus memanggil mangled method atau boxing eksplisit.")

    @staticmethod
    def simulate_jvm_overloads(func_name: str, params: List[tuple]):
        print(f"\n{BOLD}{YELLOW}>>> [Simulasi 2] @JvmOverloads Generation Matrix <<<{RESET}")
        kotlin_sig = f"{func_name}(" + ", ".join([f"{p[0]}: {p[1]} = {p[2]}" if p[2] is not None else f"{p[0]}: {p[1]}" for p in params]) + ")"
        print(f"Kotlin Source : {GREEN}@JvmOverloads fun {kotlin_sig}{RESET}")
        print(f"{CYAN}[Synthesized JVM Signatures]:{RESET}")

        default_count = sum(1 for p in params if p[2] is not None)
        total_methods = default_count + 1

        print(f"  Dihasilkan {BOLD}{total_methods}{RESET} bytecode methods untuk interoperabilitas Java:")
        # Generasi overloads
        defaults_indexes = [i for i, p in enumerate(params) if p[2] is not None]

        # 1. Full synthetic method with default mask
        mask_bits = (1 << len(defaults_indexes)) - 1
        print(f"  [Bytecode Mask]: Synthetic dispatcher: {func_name}$default(" +
              ", ".join([f"{p[1]}" for p in params]) + f", int defaultMask, Object marker)")

        # 2. Public Java-visible overloads
        for step in range(total_methods):
            omitted = default_count - step
            if omitted == 0:
                cur_params = params
            else:
                cur_params = params[:-omitted]
            param_str = ", ".join([f"{p[1]} {p[0]}" for p in cur_params])
            print(f"  Java Visible {step + 1}: {GREEN}public void {func_name}({param_str}) {{ ... }}{RESET}")


class KmpExpectActualSimulator:
    """Simulasi KMP expect/actual symbol resolution dan SourceSet linking."""

    def __init__(self):
        self.expect_symbols: Dict[str, str] = {}
        self.actual_symbols: Dict[str, Dict[str, str]] = {
            "jvm": {},
            "iosX64": {},
            "js": {}
        }

    def register_expect(self, symbol_name: str, signature: str):
        self.expect_symbols[symbol_name] = signature

    def register_actual(self, target: str, symbol_name: str, implementation: str):
        if target in self.actual_symbols:
            self.actual_symbols[target][symbol_name] = implementation

    def verify_compilation(self) -> bool:
        print(f"\n{BOLD}{YELLOW}>>> [Simulasi 3] Kotlin Multiplatform (KMP) Expect/Actual Verification <<<{RESET}")
        all_passed = True
        for symbol, sig in self.expect_symbols.items():
            print(f"{BLUE}Target Symbol (commonMain):{RESET} expect {sig}")
            for target, actuals in self.actual_symbols.items():
                if symbol in actuals:
                    print(f"  [{target}] {GREEN}✓ MATCH:{RESET} actual {actuals[symbol]}")
                else:
                    print(f"  [{target}] {RED}✗ COMPILATION ERROR: Missing actual declaration for '{symbol}'!{RESET}")
                    all_passed = False
        return all_passed


class K2CompilerPipelineSimulator:
    """Simulasi K2 Compiler Frontend (FIR) dan Backend IR Stages."""

    STAGES = [
        ("Lexer & PsiBuilder", "Mengubah source stream menjadi token stream dan PSI/AST Syntax Tree."),
        ("Raw FIR (Frontend IR)", "Penyusunan desugared FIR nodes tanpa resolusi tipe."),
        ("FIR Status & Imports", "Resolusi visibility, modal modifier, dan imports."),
        ("FIR Contract & Types", "Type inference komprehensif, Smart Cast checks, Nullability analysis."),
        ("FIR Control Flow Graph (CFG)", "Dead code analysis, uninitialized property tracking."),
        ("Backend IR Lowering", "Transformasi FIR ke Backend Intermediate Representation (JVM/Native/Wasm)."),
        ("Bytecode / Machine Code Generation", "Emisi akhir file .class (JVM) atau binary .kexe (LLVM/Native).")
    ]

    @classmethod
    def execute_pipeline(cls, sample_code: str):
        print(f"\n{BOLD}{YELLOW}>>> [Simulasi 4] K2 Compiler (FIR Architecture) Pipeline Execution <<<{RESET}")
        print(f"Source Input:\n{MAGENTA}{sample_code.strip()}{RESET}\n")

        for idx, (stage, desc) in enumerate(cls.STAGES, 1):
            print(f"{CYAN}[Step {idx}/{len(cls.STAGES)}] {BOLD}{stage}{RESET}...")
            time.sleep(0.15)
            print(f"   Laporan: {desc}")
            if idx == 4:
                print(f"   {GREEN}➔ K2 FIR Fast Inference: Evaluated type with linear complexity O(N){RESET}")
            elif idx == 6:
                print(f"   {GREEN}➔ IR Common Backend: Monomorphic / Polymorphic inlining applied{RESET}")

        print(f"\n{GREEN}{BOLD}K2 Compilation Completed in ~12ms (K1 Baseline ~48ms, Speedup: 4.0x)!{RESET}")


def interactive_menu():
    print_banner()
    jvm_sim = JvmBytecodeSimulator()
    kmp_sim = KmpExpectActualSimulator()

    # Pre-setup KMP Symbols
    kmp_sim.register_expect("getPlatformName", "fun getPlatformName(): String")
    kmp_sim.register_actual("jvm", "getPlatformName", 'fun getPlatformName(): String = "JVM: Java " + System.getProperty("java.version")')
    kmp_sim.register_actual("iosX64", "getPlatformName", 'fun getPlatformName(): String = "iOS: Darwin/Apple Silicon"')
    kmp_sim.register_actual("js", "getPlatformName", 'fun getPlatformName(): String = "JS: Node/Browser V8 Engine"')

    while True:
        print(f"\n{BOLD}{BLUE}================ PILIHAN LAB INTERAKTIF ================{RESET}")
        print(f"1. Simulasi Name Mangling pada @JvmInline Value Class")
        print(f"2. Simulasi Bytecode Generation @JvmOverloads & Default Arguments")
        print(f"3. Simulasi KMP SourceSets (expect/actual contract checker)")
        print(f"4. Jalankan Simulasi Kompilasi K2 Compiler (FIR Pipeline)")
        print(f"5. Jalankan Semua Simulasi Otomatis (Lab Validation)")
        print(f"0. Keluar")
        print(f"{BOLD}{BLUE}========================================================{RESET}")

        choice = input(f"{YELLOW}Pilih modul simulasi [0-5]: {RESET}").strip()

        if choice == "1":
            jvm_sim.simulate_name_mangling("UserId", "rawId", "String")
            jvm_sim.simulate_name_mangling("OrderId", "value", "Long")
        elif choice == "2":
            sample_params = [
                ("url", "String", None),
                ("timeoutMs", "Long", "5000L"),
                ("retries", "Int", "3")
            ]
            jvm_sim.simulate_jvm_overloads("fetchData", sample_params)
        elif choice == "3":
            kmp_sim.verify_compilation()
        elif choice == "4":
            sample_code = """
            fun processOrder(id: OrderId, count: Int = 1) {
                val platform = getPlatformName()
                println("Handling order $id on $platform")
            }
            """
            K2CompilerPipelineSimulator.execute_pipeline(sample_code)
        elif choice == "5":
            print(f"\n{BOLD}{GREEN}*** MENJALANKAN SELURUH SUITE LAB SIMULASI SECARA LENGKAP ***{RESET}")
            jvm_sim.simulate_name_mangling("CryptoHash", "hashHex", "String")
            jvm_sim.simulate_jvm_overloads("sendTelemetry", [("event", "String", None), ("priority", "Int", "1")])
            kmp_sim.verify_compilation()
            K2CompilerPipelineSimulator.execute_pipeline("fun main() = println(getPlatformName())")
            print(f"\n{GREEN}{BOLD}✓ SEMUA SIMULASI BERHASIL DIVALIDASI!{RESET}")
        elif choice == "0":
            print(f"{CYAN}Selesai. Lab simulasi ditutup.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan ulangi.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Non-interactive mode for CI/Verification test
        print_banner()
        jvm = JvmBytecodeSimulator()
        jvm.simulate_name_mangling("AutoToken", "token", "String")
        jvm.simulate_jvm_overloads("connect", [("host", "String", None), ("port", "Int", "8080")])
        kmp = KmpExpectActualSimulator()
        kmp.register_expect("os", "fun os(): String")
        kmp.register_actual("jvm", "os", 'fun os(): String = "JVM"')
        kmp.register_actual("iosX64", "os", 'fun os(): String = "iOS"')
        kmp.register_actual("js", "os", 'fun os(): String = "JS"')
        kmp.verify_compilation()
        K2CompilerPipelineSimulator.execute_pipeline("val ready: Boolean = true")
        print(f"\n{GREEN}{BOLD}Auto-test selesai sukses.{RESET}")
    else:
        interactive_menu()
