#!/usr/bin/env python3
"""
Lab Hands-on: Kotlin Multiplatform (KMP) & K2 Compiler Deep Dive
Memodelkan Arsitektur K2 Compiler Frontend (FIR - Frontend Intermediate Representation)
dan Mekanisme Resolusi 'expect' / 'actual' pada Kotlin Multiplatform.
"""

import sys
import time
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple, Set

# --- ANSI Formatting Helper ---
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

class TargetPlatform(Enum):
    COMMON = "commonMain"
    JVM = "jvmMain"
    IOS = "iosMain"
    JS = "jsMain"

class DeclarationKind(Enum):
    CLASS = auto()
    FUNCTION = auto()
    PROPERTY = auto()

@dataclass
class SourceFile:
    filename: str
    platform: TargetPlatform
    content: str

@dataclass
class FirSymbol:
    name: str
    kind: DeclarationKind
    is_expect: bool
    is_actual: bool
    signature: str
    return_type: str
    platform: TargetPlatform
    body: Optional[str] = None

@dataclass
class FirDiagnostic:
    severity: str  # ERROR, WARNING, INFO
    message: str
    source_file: str
    line: int

# --- K2 Frontend: FIR (Frontend Intermediate Representation) Engine ---
class K2CompilerFrontend:
    """
    Simulasi arsitektur K2 (FIR pipeline):
    Fase 1: Raw FIR Building (Parsing AST ke FIR node tanpa tipe lengkap)
    Fase 2: Supertypes & Imports Resolution
    Fase 3: Status & Contract Resolution
    Fase 4: Multiplatform Expect/Actual Matcher & FIR Body Checker
    """
    def __init__(self, sources: List[SourceFile]):
        self.sources = sources
        self.diagnostics: List[FirDiagnostic] = []
        self.fir_symbols: Dict[TargetPlatform, List[FirSymbol]] = {p: [] for p in TargetPlatform}

    def compile(self) -> bool:
        print(f"{TermColor.BOLD}{TermColor.CYAN}=== MEMULAI K2 COMPILER FRONTEND PIPELINE ==={TermColor.RESET}\n")
        
        # Phase 1: Raw FIR Builder
        start = time.perf_counter()
        self._phase_raw_fir_building()
        dur_p1 = (time.perf_counter() - start) * 1000
        print(f"[{TermColor.GREEN}✓{TermColor.RESET}] {TermColor.BOLD}Fase 1: Raw FIR Tree Construction{TermColor.RESET} ({dur_p1:.2f} ms)")

        # Phase 2: Symbol Definition & Scope Indexing
        start = time.perf_counter()
        self._phase_scope_indexing()
        dur_p2 = (time.perf_counter() - start) * 1000
        print(f"[{TermColor.GREEN}✓{TermColor.RESET}] {TermColor.BOLD}Fase 2: Supertypes, Imports & Scope Resolution{TermColor.RESET} ({dur_p2:.2f} ms)")

        # Phase 3: Expect/Actual Linker (KMP Core Invariant)
        start = time.perf_counter()
        self._phase_expect_actual_resolution()
        dur_p3 = (time.perf_counter() - start) * 1000
        print(f"[{TermColor.GREEN}✓{TermColor.RESET}] {TermColor.BOLD}Fase 3: KMP Expect/Actual Binding & Contract Checking{TermColor.RESET} ({dur_p3:.2f} ms)")

        self._render_diagnostics()
        has_errors = any(d.severity == "ERROR" for d in self.diagnostics)
        return not has_errors

    def _phase_raw_fir_building(self):
        """Mem-parsing syntax deklarasi multiplatform dari source code menjadi FIR node."""
        for src in self.sources:
            lines = src.content.splitlines()
            for idx, line in enumerate(lines, start=1):
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("//"):
                    continue

                # Parse deklarasi expect/actual functions & classes
                is_expect = "expect " in clean_line
                is_actual = "actual " in clean_line

                # Match class
                class_match = re.search(r'(expect\s+|actual\s+)?class\s+([A-Za-z0-9_]+)', clean_line)
                if class_match:
                    name = class_match.group(2)
                    self.fir_symbols[src.platform].append(
                        FirSymbol(
                            name=name,
                            kind=DeclarationKind.CLASS,
                            is_expect=is_expect,
                            is_actual=is_actual,
                            signature=f"class {name}",
                            return_type=name,
                            platform=src.platform
                        )
                    )
                    continue

                # Match function: expect/actual fun name(args): ReturnType
                fn_match = re.search(r'(expect\s+|actual\s+)?fun\s+([A-Za-z0-9_]+)\s*\((.*?)\)\s*:\s*([A-Za-z0-9_]+)', clean_line)
                if fn_match:
                    name = fn_match.group(2)
                    args = fn_match.group(3).strip()
                    ret = fn_match.group(4).strip()
                    self.fir_symbols[src.platform].append(
                        FirSymbol(
                            name=name,
                            kind=DeclarationKind.FUNCTION,
                            is_expect=is_expect,
                            is_actual=is_actual,
                            signature=f"fun {name}({args}): {ret}",
                            return_type=ret,
                            platform=src.platform,
                            body=clean_line
                        )
                    )

    def _phase_scope_indexing(self):
        """Index symbols and verify no duplicate declarations exist within identical scope."""
        seen_signatures: Dict[Tuple[TargetPlatform, str], str] = {}
        for platform, symbols in self.fir_symbols.items():
            for sym in symbols:
                key = (platform, sym.name)
                if key in seen_signatures:
                    self.diagnostics.append(
                        FirDiagnostic(
                            severity="ERROR",
                            message=f"Redeclaration conflict symbol '{sym.name}' pada {platform.value}",
                            source_file=platform.value,
                            line=1
                        )
                    )
                else:
                    seen_signatures[key] = sym.signature

    def _phase_expect_actual_resolution(self):
        """
        Validasi Inti KMP K2 Compiler:
        1. Setiap 'expect' di commonMain WAJIB memiliki 'actual' di setiap platform target.
        2. Tipe kembalian, nama, dan parameter harus kompatibel.
        3. 'actual' tanpa 'expect' diperbolehkan (sebagai API platform-spesifik) tapi dicatat.
        """
        common_symbols = [s for s in self.fir_symbols[TargetPlatform.COMMON] if s.is_expect]
        target_platforms = [TargetPlatform.JVM, TargetPlatform.IOS, TargetPlatform.JS]

        for expect_sym in common_symbols:
            for platform in target_platforms:
                actual_candidates = [
                    s for s in self.fir_symbols[platform]
                    if s.name == expect_sym.name and s.is_actual
                ]

                if not actual_candidates:
                    self.diagnostics.append(
                        FirDiagnostic(
                            severity="ERROR",
                            message=f"Missing actual declaration untuk '{expect_sym.signature}' di target [{platform.value}]",
                            source_file="commonMain",
                            line=1
                        )
                    )
                    continue

                actual_sym = actual_candidates[0]
                # Verifikasi kompatibilitas signature
                if actual_sym.kind != expect_sym.kind:
                    self.diagnostics.append(
                        FirDiagnostic(
                            severity="ERROR",
                            message=f"Kind mismatch pada '{actual_sym.name}': expect {expect_sym.kind.name} vs actual {actual_sym.kind.name}",
                            source_file=platform.value,
                            line=1
                        )
                    )
                elif actual_sym.return_type != expect_sym.return_type:
                    self.diagnostics.append(
                        FirDiagnostic(
                            severity="ERROR",
                            message=f"Return type mismatch untuk actual '{actual_sym.name}': diharapkan {expect_sym.return_type}, didapat {actual_sym.return_type}",
                            source_file=platform.value,
                            line=1
                        )
                    )

    def _render_diagnostics(self):
        if not self.diagnostics:
            print(f"[{TermColor.GREEN}SUCCESS{TermColor.RESET}] Tidak ada FIR diagnostic errors. Tree valid.\n")
            return

        print(f"\n{TermColor.BOLD}Diagnostic Results ({len(self.diagnostics)} items):{TermColor.RESET}")
        for diag in self.diagnostics:
            color = TermColor.RED if diag.severity == "ERROR" else TermColor.YELLOW
            print(f"  {color}[{diag.severity}]{TermColor.RESET} {diag.source_file}: {diag.message}")
        print()

# --- K2 Backend: Target Code Generator (IR Lowering Simulation) ---
class K2BackendCodeGenerator:
    """
    Menyimulasikan K2 Backend IR Lowering:
    - Target JVM: Menghasilkan class structure JVM Bytecode
    - Target Native/iOS: Menghasilkan representasi LLVM IR binding
    - Target JS: Menghasilkan ECMAScript modul (ESM)
    """
    def __init__(self, frontend: K2CompilerFrontend):
        self.frontend = frontend

    def emit_artifacts(self):
        print(f"{TermColor.BOLD}{TermColor.MAGENTA}=== K2 IR LOWERING & MULTIPLATFORM CODE GENERATION ==={TermColor.RESET}")
        for platform in [TargetPlatform.JVM, TargetPlatform.IOS, TargetPlatform.JS]:
            self._lower_for_platform(platform)

    def _lower_for_platform(self, platform: TargetPlatform):
        symbols = self.frontend.fir_symbols[platform]
        print(f"\n{TermColor.BOLD}{TermColor.YELLOW}• Target Backend: {platform.value.upper()}{TermColor.RESET}")
        
        for sym in symbols:
            if platform == TargetPlatform.JVM:
                ir_dump = f"INVOKESTATIC java/lang/System.out -> {sym.name} ()L{sym.return_type};"
                target_file = f"build/classes/kotlin/jvm/{sym.name}.class"
            elif platform == TargetPlatform.IOS:
                ir_dump = f"define dso_local {sym.return_type.lower()} @kfun:{sym.name}() #0 {{ llvm.arc.retain }}"
                target_file = f"build/bin/iosArm64/releaseFramework/{sym.name}.dylib"
            elif platform == TargetPlatform.JS:
                ir_dump = f"export function {sym.name}() {{ return Kotlin.wrapPrimitive('{sym.return_type}'); }}"
                target_file = f"build/dist/js/productionExecutable/{sym.name}.js"
            else:
                continue

            print(f"  {TermColor.CYAN}[IR Emit]{TermColor.RESET} {sym.signature}")
            print(f"    {TermColor.GRAY}Payload :{TermColor.RESET} {ir_dump}")
            print(f"    {TermColor.GREEN}Output  :{TermColor.RESET} {target_file}")

# --- Test Case Driver ---
def main():
    print(f"{TermColor.BOLD}{TermColor.BLUE}================================================================={TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.BLUE}   K2 COMPILER & KOTLIN MULTIPLATFORM (KMP) DEEP DIVE LAB        {TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.BLUE}================================================================={TermColor.RESET}\n")

    # Mendefinisikan kode sumber simulasi KMP
    sources = [
        # Common source set
        SourceFile(
            filename="commonMain/Platform.kt",
            platform=TargetPlatform.COMMON,
            content="""
            package com.example.kmp
            expect class PlatformClient
            expect fun getPlatformName(): String
            expect fun getCpuCores(): Int
            """
        ),
        # JVM target source set
        SourceFile(
            filename="jvmMain/Platform.jvm.kt",
            platform=TargetPlatform.JVM,
            content="""
            package com.example.kmp
            actual class PlatformClient
            actual fun getPlatformName(): String { return "JVM: OpenJDK 21" }
            actual fun getCpuCores(): Int { return Runtime.getRuntime().availableProcessors() }
            """
        ),
        # iOS / Native target source set
        SourceFile(
            filename="iosMain/Platform.ios.kt",
            platform=TargetPlatform.IOS,
            content="""
            package com.example.kmp
            actual class PlatformClient
            actual fun getPlatformName(): String { return "Apple Darwin/XNU" }
            actual fun getCpuCores(): Int { return 8 }
            """
        ),
        # JS target source set
        SourceFile(
            filename="jsMain/Platform.js.kt",
            platform=TargetPlatform.JS,
            content="""
            package com.example.kmp
            actual class PlatformClient
            actual fun getPlatformName(): String { return "V8/WebBrowser" }
            actual fun getCpuCores(): Int { return 4 }
            """
        )
    ]

    # Jalankan Frontend K2
    frontend = K2CompilerFrontend(sources)
    success = frontend.compile()

    if success:
        # Jalankan Backend Generator
        backend = K2BackendCodeGenerator(frontend)
        backend.emit_artifacts()
        print(f"\n{TermColor.BOLD}{TermColor.GREEN}BUILD SUCCESSFUL! Semua target KMP berhasil di-resolve oleh K2 FIR.{TermColor.RESET}")
    else:
        print(f"\n{TermColor.BOLD}{TermColor.RED}BUILD FAILED! Terdapat inkonsistensi metadata expect/actual.{TermColor.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()