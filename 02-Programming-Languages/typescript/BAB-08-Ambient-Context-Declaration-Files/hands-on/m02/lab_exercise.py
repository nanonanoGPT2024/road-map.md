#!/usr/bin/env python3
"""
Lab Hands-on: TypeScript Ambient Context & Declaration Files (.d.ts)
Category: 02-Programming-Languages | Chapter 08: Deep Dive

This lab implements an Ambient Context Resolution Engine and Static Validator.
It simulates TypeScript compiler (tsc) internals for:
  1. Parsing ambient declarations ('declare var', 'declare function', 'declare module').
  2. Ambient symbol table management and Global Scope Augmentation.
  3. Declaration Merging (multiple declarations sharing the same identifier).
  4. Type checking untyped runtime code against ambient contracts without emitting JS.
"""

import sys
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

# --- Terminal Styling ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_CYAN   = "\033[36m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED    = "\033[31m"
CLR_MAG    = "\033[35m"
CLR_GRAY   = "\033[90m"

@dataclass
class TypeSignature:
    raw_type: str
    is_nullable: bool = False

@dataclass
class ParamDef:
    name: str
    type_sig: str

@dataclass
class FunctionDeclaration:
    name: str
    params: List[ParamDef]
    return_type: str
    is_ambient: bool = True

@dataclass
class VariableDeclaration:
    name: str
    type_sig: str
    is_const: bool
    is_ambient: bool = True

@dataclass
class InterfaceDeclaration:
    name: str
    fields: Dict[str, str] = field(default_factory=dict)
    methods: Dict[str, FunctionDeclaration] = field(default_factory=dict)

@dataclass
class ModuleDeclaration:
    module_name: str
    exports: Dict[str, Any] = field(default_factory=dict)

class AmbientContextEngine:
    """
    Simulates TypeScript's Ambient Context registry where ambient declarations
    inform the type system of runtime values without producing emitted JavaScript.
    """
    def __init__(self):
        self.global_vars: Dict[str, VariableDeclaration] = {}
        self.global_funcs: Dict[str, List[FunctionDeclaration]] = {}
        self.interfaces: Dict[str, InterfaceDeclaration] = {}
        self.ambient_modules: Dict[str, ModuleDeclaration] = {}

    def register_ambient_var(self, name: str, type_sig: str, is_const: bool = False):
        """Registers a 'declare const/var' into the ambient scope."""
        self.global_vars[name] = VariableDeclaration(name, type_sig, is_const, is_ambient=True)

    def register_ambient_func(self, name: str, params: List[ParamDef], return_type: str):
        """Registers a 'declare function' supporting function overloading."""
        fn = FunctionDeclaration(name, params, return_type, is_ambient=True)
        if name not in self.global_funcs:
            self.global_funcs[name] = []
        self.global_funcs[name].append(fn)

    def merge_interface(self, name: str, new_fields: Dict[str, str], new_methods: Dict[str, FunctionDeclaration] = None):
        """
        Simulates TypeScript's Declaration Merging.
        Successive declarations of the same interface combine their members.
        """
        if name not in self.interfaces:
            self.interfaces[name] = InterfaceDeclaration(name=name)
        
        target = self.interfaces[name]
        for field_name, field_type in new_fields.items():
            target.fields[field_name] = field_type
            
        if new_methods:
            for method_name, method_def in new_methods.items():
                target.methods[method_name] = method_def

    def register_ambient_module(self, module_name: str, exports: Dict[str, Any]):
        """Registers a 'declare module "x"' ambient boundary."""
        self.ambient_modules[module_name] = ModuleDeclaration(module_name=module_name, exports=exports)


class DTSParser:
    """
    A lightweight parser that translates simulated .d.ts syntax into AmbientContext entries.
    """
    def __init__(self, context: AmbientContextEngine):
        self.context = context

    def parse_dts_content(self, dts_source: str):
        lines = [line.strip() for line in dts_source.splitlines() if line.strip() and not line.strip().startswith("//")]
        
        i = 0
        while i < len(lines):
            line = lines[i]

            # Match 'declare const/var <name>: <type>;'
            var_match = re.match(r"^declare\s+(const|var|let)\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*:\s*([^;]+);", line)
            if var_match:
                kw, name, raw_type = var_match.groups()
                self.context.register_ambient_var(name, raw_type.strip(), is_const=(kw == "const"))
                i += 1
                continue

            # Match 'declare function <name>(<params>): <type>;'
            fn_match = re.match(r"^declare\s+function\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*\((.*?)\)\s*:\s*([^;]+);", line)
            if fn_match:
                name, raw_params, ret_type = fn_match.groups()
                params = []
                if raw_params.strip():
                    for p in raw_params.split(","):
                        p_parts = p.split(":")
                        params.append(ParamDef(name=p_parts[0].strip(), type_sig=p_parts[1].strip()))
                self.context.register_ambient_func(name, params, ret_type.strip())
                i += 1
                continue

            # Match interface declaration block
            if line.startswith("interface ") and line.endswith("{"):
                iface_name = line.split()[1]
                fields = {}
                i += 1
                while i < len(lines) and lines[i] != "}":
                    f_line = lines[i].rstrip(";")
                    if ":" in f_line:
                        fname, ftype = f_line.split(":", 1)
                        fields[fname.strip()] = ftype.strip()
                    i += 1
                self.context.merge_interface(iface_name, fields)
                i += 1
                continue

            # Match declare module "xyz" { ... }
            mod_match = re.match(r'^declare\s+module\s+["\']([^"\']+)["\']\s*\{', line)
            if mod_match:
                mod_name = mod_match.group(1)
                exports = {}
                i += 1
                while i < len(lines) and lines[i] != "}":
                    m_line = lines[i]
                    exp_fn = re.match(r"export\s+function\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*\((.*?)\)\s*:\s*([^;]+);", m_line)
                    if exp_fn:
                        fname, raw_params, ret_type = exp_fn.groups()
                        params = [ParamDef(p.split(":")[0].strip(), p.split(":")[1].strip()) 
                                  for p in raw_params.split(",") if p.strip()]
                        exports[fname] = FunctionDeclaration(fname, params, ret_type.strip())
                    i += 1
                self.context.register_ambient_module(mod_name, exports)
                i += 1
                continue

            i += 1


class TypeScriptSemanticValidator:
    """
    Validates simulated TS runtime statements against the populated AmbientContext.
    Verifies type safety, emits errors (e.g., TS2304, TS2345), and ensures zero JS emit for .d.ts.
    """
    def __init__(self, context: AmbientContextEngine):
        self.context = context
        self.diagnostics: List[str] = []

    def validate_variable_access(self, var_name: str, expected_type: Optional[str] = None) -> bool:
        """Verifies if variable exists in ambient context and matches expected type."""
        if var_name not in self.context.global_vars:
            self.diagnostics.append(f"{CLR_RED}error TS2304{CLR_RESET}: Cannot find name '{var_name}'.")
            return False
        
        actual = self.context.global_vars[var_name]
        if expected_type and actual.type_sig != expected_type:
            self.diagnostics.append(
                f"{CLR_RED}error TS2322{CLR_RESET}: Type '{actual.type_sig}' is not assignable to type '{expected_type}'."
            )
            return False
        return True

    def validate_function_invocation(self, func_name: str, arg_types: List[str]) -> bool:
        """Verifies function call against registered ambient overloads."""
        if func_name not in self.context.global_funcs:
            self.diagnostics.append(f"{CLR_RED}error TS2304{CLR_RESET}: Cannot find function '{func_name}'.")
            return False

        overloads = self.context.global_funcs[func_name]
        for candidate in overloads:
            if len(candidate.params) != len(arg_types):
                continue
            match = True
            for param, arg_type in zip(candidate.params, arg_types):
                if param.type_sig != "any" and param.type_sig != arg_type:
                    match = False
                    break
            if match:
                return True

        self.diagnostics.append(
            f"{CLR_RED}error TS2345{CLR_RESET}: Argument types ({', '.join(arg_types)}) do not match overload for '{func_name}'."
        )
        return False

    def validate_module_import(self, module_name: str, member: str) -> bool:
        """Verifies imports against 'declare module' ambient boundaries."""
        if module_name not in self.ambient_modules:
            self.diagnostics.append(f"{CLR_RED}error TS2307{CLR_RESET}: Cannot find module '{module_name}' or its type declarations.")
            return False
        
        mod = self.ambient_modules[module_name]
        if member not in mod.exports:
            self.diagnostics.append(f"{CLR_RED}error TS2614{CLR_RESET}: Module '{module_name}' has no exported member '{member}'.")
            return False
        return True


def simulate_compiler_pipeline():
    print(f"{CLR_BOLD}{CLR_CYAN}=== TypeScript Ambient Context & Declaration Files Lab ==={CLR_RESET}\n")

    context = AmbientContextEngine()
    parser = DTSParser(context)

    # --- Phase 1: Load Global Ambient Declarations (.d.ts) ---
    global_dts = """
    // Global runtime environment variables injected by host (e.g., Node.js / Browser)
    declare const __VERSION__: string;
    declare const __DEBUG_MODE__: boolean;
    declare function nativeAlert(message: string): void;
    declare function nativeAlert(message: string, code: number): void;
    """

    print(f"{CLR_BOLD}[1] Loading Global Ambient Definitions (global.d.ts)...{CLR_RESET}")
    parser.parse_dts_content(global_dts)
    for v in context.global_vars.values():
        print(f"  {CLR_GRAY}• Registered ambient var:{CLR_RESET} {v.name} -> {CLR_YELLOW}{v.type_sig}{CLR_RESET}")
    for fname, overloads in context.global_funcs.items():
        print(f"  {CLR_GRAY}• Registered ambient func:{CLR_RESET} {fname} with {len(overloads)} overload(s)")

    # --- Phase 2: Simulating Declaration Merging ---
    print(f"\n{CLR_BOLD}[2] Demonstrating Declaration Merging on Interfaces...{CLR_RESET}")
    iface_part_1 = """
    interface UserSession {
        userId: string;
        token: string;
    }
    """
    iface_part_2 = """
    interface UserSession {
        role: string;
        permissions: string[];
    }
    """
    parser.parse_dts_content(iface_part_1)
    parser.parse_dts_content(iface_part_2)

    merged = context.interfaces["UserSession"]
    print(f"  {CLR_GREEN}✓ Successfully merged 'UserSession' across 2 declarations:{CLR_RESET}")
    for k, v in merged.fields.items():
        print(f"    - {k}: {CLR_YELLOW}{v}{CLR_RESET}")

    # --- Phase 3: Shimming Third-Party Library via Ambient Module ---
    print(f"\n{CLR_BOLD}[3] Shimming Untyped Third-Party JS Module (ambient-shim.d.ts)...{CLR_RESET}")
    module_dts = """
    declare module "crypto-native-shim" {
        export function hashBuffer(data: string): string;
        export function verifySignature(token: string, key: string): boolean;
    }
    """
    parser.parse_dts_content(module_dts)
    shim_mod = context.ambient_modules["crypto-native-shim"]
    print(f"  {CLR_GREEN}✓ Ambient module resolved:{CLR_RESET} '{shim_mod.module_name}'")
    for exp_name, exp_fn in shim_mod.exports.items():
        sig = f"({', '.join(p.name + ': ' + p.type_sig for p in exp_fn.params)}) => {exp_fn.return_type}"
        print(f"    - export {exp_name}: {CLR_YELLOW}{sig}{CLR_RESET}")

    # --- Phase 4: Static Validation & Type-Checking Simulated TS Code ---
    print(f"\n{CLR_BOLD}[4] Running TypeChecker on Consumer Source Code...{CLR_RESET}")
    validator = TypeScriptSemanticValidator(context)
    
    test_cases: List[Tuple[str, callable]] = [
        ("Accessing valid ambient global '__VERSION__'", 
         lambda: validator.validate_variable_access("__VERSION__", "string")),
        
        ("Accessing undeclared global '__ENV_SECRET__'", 
         lambda: validator.validate_variable_access("__ENV_SECRET__", "string")),
        
        ("Invoking valid overload: nativeAlert(string)", 
         lambda: validator.validate_function_invocation("nativeAlert", ["string"])),
         
        ("Invoking valid overload: nativeAlert(string, number)", 
         lambda: validator.validate_function_invocation("nativeAlert", ["string", "number"])),

        ("Invoking invalid overload: nativeAlert(number, boolean)", 
         lambda: validator.validate_function_invocation("nativeAlert", ["number", "boolean"])),

        ("Importing member from 'crypto-native-shim'", 
         lambda: validator.validate_module_import("crypto-native-shim", "hashBuffer")),

        ("Importing non-existent member from 'crypto-native-shim'", 
         lambda: validator.validate_module_import("crypto-native-shim", "nonExistentHelper")),

        ("Importing from untyped, undeclared module 'fast-json'", 
         lambda: validator.validate_module_import("fast-json", "parse")),
    ]

    for label, action in test_cases:
        passed = action()
        status = f"{CLR_GREEN}[PASS]{CLR_RESET}" if passed else f"{CLR_RED}[FAIL]{CLR_RESET}"
        print(f"  {status} Test: {label}")

    # --- Phase 5: Diagnostic Report & Zero-Emit Verification ---
    print(f"\n{CLR_BOLD}[5] Diagnostic Logs & Emitted JavaScript Verification...{CLR_RESET}")
    if validator.diagnostics:
        print(f"{CLR_YELLOW}Diagnostics detected ({len(validator.diagnostics)} issue(s)):{CLR_RESET}")
        for diag in validator.diagnostics:
            print(f"  {diag}")
    
    print(f"\n{CLR_BOLD}[6] Ambient Context Compiler Invariant:{CLR_RESET}")
    dts_input_size = len(global_dts) + len(iface_part_1) + len(iface_part_2) + len(module_dts)
    emitted_js_size = 0  # Invariant: ambient declarations NEVER emit runtime code
    print(f"  • Raw Declarations (.d.ts) Parsed: {CLR_CYAN}{dts_input_size} bytes{CLR_RESET}")
    print(f"  • Emitted JavaScript Artifacts:    {CLR_GREEN}{emitted_js_size} bytes (Zero runtime overhead){CLR_RESET}")
    print(f"  • Compiler Status: Ambient Context verification complete.")


if __name__ == "__main__":
    simulate_compiler_pipeline()