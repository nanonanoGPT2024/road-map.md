#!/usr/bin/env python3
"""
TypeScript Compiler Internals & Monorepo Tooling Simulation
Focus: AST Transformation, Declaration Emit (.d.ts), Type Checking Diagnostics,
       and Composite Monorepo Graph Engine with Incremental Build Caching (.tsbuildinfo).

Author: Lead System Programmer
Standard Library Only: sys, os, time, hashlib, json, dataclasses, typing, collections
"""

import sys
import os
import time
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict, deque

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[1;31m"
CLR_GREEN = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_BLUE = "\033[1;34m"
CLR_MAGENTA = "\033[1;35m"
CLR_CYAN = "\033[1;36m"
CLR_GRAY = "\033[90m"


# ==============================================================================
# SECTION 1: COMPILER INTERNALS (AST, BINDER, CHECKER, EMITTER)
# ==============================================================================

@dataclass
class Token:
    type: str
    value: str
    pos: int

@dataclass
class TypeSignature:
    name: str
    kind: str  # 'interface', 'type', 'primitive'
    fields: Dict[str, str] = field(default_factory=dict)

@dataclass
class ExportSymbol:
    name: str
    type_sig: str
    is_type_only: bool = False

@dataclass
class SourceAST:
    package_name: str
    file_name: str
    imports: Dict[str, str] = field(default_factory=dict)  # local_var -> pkg_source
    exports: Dict[str, ExportSymbol] = field(default_factory=dict)
    type_declarations: Dict[str, TypeSignature] = field(default_factory=dict)
    body_statements: List[str] = field(default_factory=list)


class TypeScriptScannerParser:
    """
    Simulates TypeScript's Scanner (Lexer) and Parser phases.
    Translates raw TypeScript-like code into a simplified Abstract Syntax Tree (AST).
    """
    @staticmethod
    def parse(pkg_name: str, file_name: str, code: str) -> SourceAST:
        ast = SourceAST(package_name=pkg_name, file_name=file_name)
        lines = [l.strip() for l in code.splitlines() if l.strip() and not l.strip().startswith("//")]

        for line in lines:
            # Match imports: import { X } from "pkg";
            if line.startswith("import"):
                parts = line.split('"')
                if len(parts) >= 2:
                    source_pkg = parts[1]
                    raw_symbols = line[line.find("{") + 1 : line.find("}")].split(",")
                    for sym in raw_symbols:
                        ast.imports[sym.strip()] = source_pkg

            # Match type interfaces: interface X { f: t; }
            elif line.startswith("export interface ") or line.startswith("interface "):
                is_export = line.startswith("export")
                tokens = line.replace("export ", "").split()
                name = tokens[1]
                body = line[line.find("{") + 1 : line.rfind("}")]
                fields = {}
                for field_def in body.split(";"):
                    field_def = field_def.strip()
                    if ":" in field_def:
                        fname, ftype = field_def.split(":", 1)
                        fields[fname.strip()] = ftype.strip()
                
                sig = TypeSignature(name=name, kind="interface", fields=fields)
                ast.type_declarations[name] = sig
                if is_export:
                    ast.exports[name] = ExportSymbol(name=name, type_sig="interface", is_type_only=True)

            # Match exports: export const X: Type = ...
            elif line.startswith("export const ") or line.startswith("export function "):
                parts = line.split()
                sym_name = parts[2].split(":")[0].split("(")[0]
                type_sig = "any"
                if ":" in line:
                    type_sig = line.split(":", 1)[1].split("=")[0].split("{")[0].strip()
                ast.exports[sym_name] = ExportSymbol(name=sym_name, type_sig=type_sig, is_type_only=False)
                ast.body_statements.append(line)
            else:
                ast.body_statements.append(line)

        return ast


class TypeChecker:
    """
    Simulates TypeScript's Type Checker & Binder phase.
    Resolves symbols across compilation contexts and detects type mismatches.
    """
    def __init__(self, global_dts_registry: Dict[str, Dict[str, ExportSymbol]]):
        self.global_registry = global_dts_registry

    def check(self, ast: SourceAST) -> List[str]:
        diagnostics = []
        for symbol, source_pkg in ast.imports.items():
            if source_pkg not in self.global_registry:
                diagnostics.append(
                    f"TS2307: Cannot find module '{source_pkg}' or its corresponding type declarations."
                )
            else:
                exported_symbols = self.global_registry[source_pkg]
                if symbol not in exported_symbols:
                    diagnostics.append(
                        f"TS2614: Module '{source_pkg}' has no exported member '{symbol}'."
                    )
        return diagnostics


class Emitter:
    """
    Simulates TypeScript's Emitter phase.
    Emits both JavaScript output (.js) and Type Declaration outputs (.d.ts).
    Computes a cryptographic Public API Signature for Declaration Tracking.
    """
    @staticmethod
    def emit(ast: SourceAST) -> Tuple[str, str, str]:
        # 1. Emit JS output (stripping type definitions)
        js_lines = [f"// [Generated JS from {ast.file_name}]"]
        for stmt in ast.body_statements:
            clean_stmt = stmt.replace("export ", "").replace("public ", "")
            js_lines.append(clean_stmt)
        js_code = "\n".join(js_lines)

        # 2. Emit .d.ts API Surface
        dts_lines = [f"// TypeScript Declaration File: {ast.file_name}"]
        for name, sig in ast.type_declarations.items():
            fields_str = "; ".join([f"{k}: {v}" for k, v in sig.fields.items()])
            dts_lines.append(f"export interface {name} {{ {fields_str}; }}")
        for exp_name, exp_meta in ast.exports.items():
            if not exp_meta.is_type_only:
                dts_lines.append(f"export declare const {exp_name}: {exp_meta.type_sig};")
        dts_code = "\n".join(dts_lines)

        # 3. Compute API Surface Hash (Signature)
        # Any change inside function bodies does NOT alter this hash, avoiding cascade invalidation!
        api_signature_hash = hashlib.sha256(dts_code.encode("utf-8")).hexdigest()[:16]

        return js_code, dts_code, api_signature_hash


# ==============================================================================
# SECTION 2: MONOREPO TOOLING & COMPOSITE GRAPH ENGINE
# ==============================================================================

@dataclass
class TSBuildInfo:
    """Represents the .tsbuildinfo state file used in incremental builds."""
    version: str = "5.4.0"
    file_hashes: Dict[str, str] = field(default_factory=dict)
    api_signature_hash: str = ""
    upstream_signatures: Dict[str, str] = field(default_factory=dict)
    last_build_duration_ms: float = 0.0


@dataclass
class ProjectPackage:
    name: str
    path: str
    tsconfig_references: List[str]
    source_files: Dict[str, str]  # file_name -> raw_code
    build_info: Optional[TSBuildInfo] = None


class MonorepoEngine:
    """
    Simulates Project References, Topological Dependency Ordering (Kahn's Algo),
    and Signature-Aware Incremental Rebuilds (like Turborepo / tsc --build).
    """
    def __init__(self):
        self.packages: Dict[str, ProjectPackage] = {}
        self.dts_registry: Dict[str, Dict[str, ExportSymbol]] = {}
        self.build_cache: Dict[str, TSBuildInfo] = {}

    def register_package(self, pkg: ProjectPackage):
        self.packages[pkg.name] = pkg

    def get_build_order(self) -> List[str]:
        """Kahn's Algorithm for Topological Sort of Project References."""
        in_degree = {pkg: 0 for pkg in self.packages}
        adj = defaultdict(list)

        for name, pkg in self.packages.items():
            for dep in pkg.tsconfig_references:
                adj[dep].append(name)
                in_degree[name] += 1

        queue = deque([pkg for pkg, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.packages):
            raise RuntimeError(f"{CLR_RED}Cyclic dependency detected in project references!{CLR_RESET}")
        return order

    def build_project(self, force: bool = False) -> None:
        build_order = self.get_build_order()
        print(f"{CLR_BOLD}{CLR_CYAN}=== Starting Monorepo Graph Orchestration ==={CLR_RESET}")
        print(f"Topological Execution Order: {' -> '.join(build_order)}\n")

        for pkg_name in build_order:
            pkg = self.packages[pkg_name]
            self._compile_package(pkg, force)

    def _compile_package(self, pkg: ProjectPackage, force: bool):
        start_time = time.perf_counter()
        print(f"{CLR_BOLD}Package: {CLR_BLUE}{pkg.name}{CLR_RESET} ({pkg.path})")

        # 1. Compute current content hashes of all files in this project
        current_file_hashes = {}
        for fname, content in pkg.source_files.items():
            current_file_hashes[fname] = hashlib.sha256(content.encode()).hexdigest()[:16]

        # 2. Gather current upstream signatures
        current_upstream_signatures = {}
        for dep in pkg.tsconfig_references:
            if dep in self.build_cache:
                current_upstream_signatures[dep] = self.build_cache[dep].api_signature_hash

        # 3. Incremental Evaluation (.tsbuildinfo checks)
        cached_info = self.build_cache.get(pkg.name)
        if not force and cached_info:
            files_unchanged = (cached_info.file_hashes == current_file_hashes)
            upstreams_unchanged = (cached_info.upstream_signatures == current_upstream_signatures)

            if files_unchanged and upstreams_unchanged:
                print(f"  {CLR_GREEN}⚡ [TSBUILDINFO HIT]{CLR_RESET} Package is up-to-date. Skipped compilation.")
                return

            if files_unchanged and not upstreams_unchanged:
                print(f"  {CLR_YELLOW}↻ [UPSTREAM INVALIDATED]{CLR_RESET} Upstream public API signatures changed.")
            else:
                print(f"  {CLR_YELLOW}↻ [SOURCE DIRTY]{CLR_RESET} Local source files modified.")

        # 4. Compilation Pipeline: Scan/Parse -> TypeCheck -> Emit
        combined_exports: Dict[str, ExportSymbol] = {}
        last_sig_hash = ""

        for fname, content in pkg.source_files.items():
            # Phase A: Parser
            ast = TypeScriptScannerParser.parse(pkg.name, fname, content)
            
            # Phase B: Type Checker
            checker = TypeChecker(self.dts_registry)
            diagnostics = checker.check(ast)
            if diagnostics:
                for diag in diagnostics:
                    print(f"  {CLR_RED}✖ Error in {fname}: {diag}{CLR_RESET}")
                sys.exit(1)

            # Phase C: Emitter
            js_code, dts_code, sig_hash = Emitter.emit(ast)
            last_sig_hash = sig_hash
            combined_exports.update(ast.exports)

            print(f"  {CLR_GRAY}→ Compiled {fname}: [Sig: {sig_hash}]{CLR_RESET}")

        # Register Public API Symbols for downstream consumers
        self.dts_registry[pkg.name] = combined_exports

        elapsed = (time.perf_counter() - start_time) * 1000
        # 5. Persist .tsbuildinfo
        self.build_cache[pkg.name] = TSBuildInfo(
            file_hashes=current_file_hashes,
            api_signature_hash=last_sig_hash,
            upstream_signatures=current_upstream_signatures,
            last_build_duration_ms=elapsed
        )
        print(f"  {CLR_GREEN}✔ Output emitted (.js, .d.ts, .tsbuildinfo){CLR_RESET} in {elapsed:.2f}ms\n")


# ==============================================================================
# SECTION 3: LAB WORKBENCH SIMULATION
# ==============================================================================

def main():
    os.system("") # Enable ANSI colors on Windows terminals
    engine = MonorepoEngine()

    # --- Setup Monorepo Workspace Packages ---
    # 1. Base Core Types
    engine.register_package(ProjectPackage(
        name="@core/types",
        path="packages/core-types",
        tsconfig_references=[],
        source_files={
            "user.ts": """
                export interface UserSession { id: string; role: string; }
                export interface TenantMeta { tenantId: string; active: boolean; }
            """
        }
    ))

    # 2. Database/Auth Utility (Depends on @core/types)
    engine.register_package(ProjectPackage(
        name="@core/auth",
        path="packages/core-auth",
        tsconfig_references=["@core/types"],
        source_files={
            "authenticator.ts": """
                import { UserSession } from "@core/types";
                export const verifyToken: (token: string) => UserSession = (token) => { return token; };
                export const DEFAULT_TIMEOUT: number = 3600;
            """
        }
    ))

    # 3. HTTP Server App (Depends on @core/auth and @core/types)
    engine.register_package(ProjectPackage(
        name="@apps/api-server",
        path="apps/api-server",
        tsconfig_references=["@core/auth", "@core/types"],
        source_files={
            "server.ts": """
                import { verifyToken } from "@core/auth";
                import { TenantMeta } from "@core/types";
                export const startServer: () => void = () => { /* Server init logic */ };
            """
        }
    ))

    # --------------------------------------------------------------------------
    # EXECUTION STEP 1: Cold Clean Build
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA} STEP 1: INITIAL MONOREPO COLD BUILD (tsc -b --composite)           {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    engine.build_project()

    # --------------------------------------------------------------------------
    # EXECUTION STEP 2: Incremental Run Without Changes (Full Cache Hit)
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA} STEP 2: INCREMENTAL REBUILD - ZERO MODIFICATIONS                     {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    engine.build_project()

    # --------------------------------------------------------------------------
    # EXECUTION STEP 3: Implementation Change Only in Upstream (No API Change)
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA} STEP 3: MODIFY IMPLEMENTATION ONLY IN '@core/auth'                   {CLR_RESET}")
    print(f" (Public .d.ts API stays identical. Demonstrating Smart Invalidation){CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    
    # Internal body changes, but exported signature does NOT change!
    engine.packages["@core/auth"].source_files["authenticator.ts"] = """
        import { UserSession } from "@core/types";
        export const verifyToken: (token: string) => UserSession = (token) => { 
            console.log("Internal audit logging added!"); 
            return token; 
        };
        export const DEFAULT_TIMEOUT: number = 3600;
    """
    engine.build_project()

    # --------------------------------------------------------------------------
    # EXECUTION STEP 4: Breaking Declaration API Change in '@core/types'
    # --------------------------------------------------------------------------
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA} STEP 4: BREAKING PUBLIC TYPE CHANGE IN ROOT '@core/types'            {CLR_RESET}")
    print(f" (Cascades build invalidation down to all consumer packages)         {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")

    engine.packages["@core/types"].source_files["user.ts"] = """
        export interface UserSession { id: string; role: string; permissions: string[]; }
        export interface TenantMeta { tenantId: string; active: boolean; }
    """
    engine.build_project()


if __name__ == "__main__":
    main()