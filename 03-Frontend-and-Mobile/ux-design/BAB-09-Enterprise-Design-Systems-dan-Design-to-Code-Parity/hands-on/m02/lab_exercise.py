#!/usr/bin/env python3
"""
Enterprise Design Systems & Design-to-Code Parity Architecture Simulator
BAB-09: Enterprise Design Systems dan Design-to-Code Parity

Modul Hands-on Lab 02:
Simulasi komprehensif arsitektur Design Tokens Compiler, Drift Detection Engine,
WCAG 2.1 AAA Accessibility Validator, dan Multi-platform Code Generation.
"""

import sys
import json
import time
import math
from typing import Dict, Any, List, Tuple

# ==============================================================================
# ANSI Terminal Color & Style Helpers
# ==============================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    FG_BLACK = "\033[30m"
    FG_RED = "\033[31m"
    FG_GREEN = "\033[32m"
    FG_YELLOW = "\033[33m"
    FG_BLUE = "\033[34m"
    FG_MAGENTA = "\033[35m"
    FG_CYAN = "\033[36m"
    FG_WHITE = "\033[37m"
    
    # Bright Foreground
    FG_BRIGHT_RED = "\033[91m"
    FG_BRIGHT_GREEN = "\033[92m"
    FG_BRIGHT_YELLOW = "\033[93m"
    FG_BRIGHT_BLUE = "\033[94m"
    FG_BRIGHT_MAGENTA = "\033[95m"
    FG_BRIGHT_CYAN = "\033[96m"
    
    # Background
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[48;5;236m"

def print_header(title: str):
    width = 76
    print(f"\n{TermColor.BG_BLUE}{TermColor.FG_WHITE}{TermColor.BOLD}{' ' + title.center(width - 2) + ' '}{TermColor.RESET}")

def print_subbar(title: str):
    print(f"{TermColor.FG_CYAN}{TermColor.BOLD}━━━ [ {title} ] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{TermColor.RESET}")

def print_success(msg: str):
    print(f" {TermColor.FG_BRIGHT_GREEN}✔{TermColor.RESET} {msg}")

def print_warn(msg: str):
    print(f" {TermColor.FG_BRIGHT_YELLOW}▲ [WARNING]{TermColor.RESET} {msg}")

def print_error(msg: str):
    print(f" {TermColor.FG_BRIGHT_RED}✖ [DRIFT/ERROR]{TermColor.RESET} {msg}")

def print_info(msg: str):
    print(f" {TermColor.FG_BRIGHT_BLUE}ℹ{TermColor.RESET} {msg}")


# ==============================================================================
# Model & Database Mock: Design Tokens Architecture (W3C DTCG Format)
# ==============================================================================
MOCK_DESIGN_TOKENS_W3C: Dict[str, Any] = {
    "global": {
        "color": {
            "blue": {
                "50": {"$value": "#eff6ff", "$type": "color"},
                "500": {"$value": "#3b82f6", "$type": "color"},
                "600": {"$value": "#2563eb", "$type": "color"},
                "900": {"$value": "#1e3a8a", "$type": "color"}
            },
            "slate": {
                "50": {"$value": "#f8fafc", "$type": "color"},
                "900": {"$value": "#0f172a", "$type": "color"}
            },
            "emerald": {
                "500": {"$value": "#10b981", "$type": "color"}
            },
            "rose": {
                "500": {"$value": "#f43f5e", "$type": "color"}
            }
        },
        "spacing": {
            "sm": {"$value": "8px", "$type": "dimension"},
            "md": {"$value": "16px", "$type": "dimension"},
            "lg": {"$value": "24px", "$type": "dimension"},
            "xl": {"$value": "32px", "$type": "dimension"}
        },
        "radius": {
            "sm": {"$value": "4px", "$type": "dimension"},
            "md": {"$value": "8px", "$type": "dimension"},
            "full": {"$value": "9999px", "$type": "dimension"}
        }
    },
    "semantic": {
        "color": {
            "brand": {
                "primary": {"$value": "{global.color.blue.600}", "$type": "color"},
                "accent": {"$value": "{global.color.blue.500}", "$type": "color"}
            },
            "feedback": {
                "success": {"$value": "{global.color.emerald.500}", "$type": "color"},
                "danger": {"$value": "{global.color.rose.500}", "$type": "color"}
            },
            "surface": {
                "base": {"$value": "{global.color.slate.50}", "$type": "color"},
                "contrast": {"$value": "{global.color.slate.900}", "$type": "color"}
            }
        }
    },
    "component": {
        "button": {
            "primary": {
                "bg": {"$value": "{semantic.color.brand.primary}", "$type": "color"},
                "fg": {"$value": "#ffffff", "$type": "color"},
                "padding-x": {"$value": "{global.spacing.md}", "$type": "dimension"},
                "padding-y": {"$value": "{global.spacing.sm}", "$type": "dimension"},
                "radius": {"$value": "{global.radius.md}", "$type": "dimension"}
            }
        }
    }
}

# Production Codebase Snapshot (Simulasi file CSS / TypeScript repository web)
PRODUCTION_CSS_REGISTRY: Dict[str, str] = {
    "--global-color-blue-50": "#eff6ff",
    "--global-color-blue-500": "#3b82f6",
    "--global-color-blue-600": "#2563eb",
    "--global-color-blue-900": "#1e3a8a",
    "--global-color-slate-50": "#f8fafc",
    "--global-color-slate-900": "#0f172a",
    "--global-color-emerald-500": "#10b981",
    "--global-color-rose-500": "#f43f5e",
    "--global-spacing-sm": "8px",
    "--global-spacing-md": "16px",
    "--global-spacing-lg": "24px",
    "--global-spacing-xl": "32px",
    "--global-radius-sm": "4px",
    "--global-radius-md": "8px",
    "--global-radius-full": "9999px",
    "--semantic-color-brand-primary": "#2563eb",
    "--semantic-color-brand-accent": "#3b82f6",
    "--semantic-color-feedback-success": "#10b981",
    "--semantic-color-feedback-danger": "#f43f5e",
    "--semantic-color-surface-base": "#f8fafc",
    "--semantic-color-surface-contrast": "#0f172a",
    "--component-button-primary-bg": "#2563eb",
    "--component-button-primary-fg": "#ffffff",
    "--component-button-primary-padding-x": "16px",
    "--component-button-primary-padding-y": "8px",
    "--component-button-primary-radius": "8px",
}


# ==============================================================================
# WCAG Contrast Math & Luminance Engine
# ==============================================================================
def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    clean_hex = hex_str.lstrip('#')
    if len(clean_hex) == 3:
        clean_hex = "".join([c * 2 for c in clean_hex])
    return int(clean_hex[0:2], 16), int(clean_hex[2:4], 16), int(clean_hex[4:6], 16)

def relative_luminance(r: int, g: int, b: int) -> float:
    def channel_lum(val: int) -> float:
        c = val / 255.0
        return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)

def calculate_contrast_ratio(hex1: str, hex2: str) -> float:
    r1, g1, b1 = hex_to_rgb(hex1)
    r2, g2, b2 = hex_to_rgb(hex2)
    l1 = relative_luminance(r1, g1, b1)
    l2 = relative_luminance(r2, g2, b2)
    bright = max(l1, l2)
    dark = min(l1, l2)
    return (bright + 0.05) / (dark + 0.05)


# ==============================================================================
# Token Compiler & Resolver
# ==============================================================================
class TokenEngine:
    def __init__(self, raw_tokens: Dict[str, Any]):
        self.raw_tokens = raw_tokens
        self.flat_resolved: Dict[str, str] = {}
        self.resolve_all()

    def _resolve_reference(self, val_str: str) -> str:
        if isinstance(val_str, str) and val_str.startswith("{") and val_str.endswith("}"):
            ref_path = val_str[1:-1].split(".")
            cursor = self.raw_tokens
            for part in ref_path:
                cursor = cursor[part]
            raw_val = cursor["$value"]
            return self._resolve_reference(raw_val)
        return val_str

    def _walk_tokens(self, node: Any, path_prefix: str = ""):
        if isinstance(node, dict):
            if "$value" in node:
                resolved_val = self._resolve_reference(node["$value"])
                self.flat_resolved[path_prefix] = resolved_val
            else:
                for k, v in node.items():
                    sub_path = f"{path_prefix}.{k}" if path_prefix else k
                    self._walk_tokens(v, sub_path)

    def resolve_all(self):
        self.flat_resolved.clear()
        self._walk_tokens(self.raw_tokens)

    def export_css_variables(self) -> str:
        lines = [":root {", "  /* Autogenerated by Enterprise Token Pipeline */"]
        for key, val in self.flat_resolved.items():
            css_var_name = "--" + key.replace(".", "-")
            lines.append(f"  {css_var_name}: {val};")
        lines.append("}")
        return "\n".join(lines)

    def export_typescript_tokens(self) -> str:
        lines = ["export const DesignSystemTokens = {"]
        for key, val in self.flat_resolved.items():
            ts_key = key.replace(".", "_")
            lines.append(f"  {ts_key}: \"{val}\",")
        lines.append("} as const;")
        lines.append("export type TokenName = keyof typeof DesignSystemTokens;")
        return "\n".join(lines)

    def export_android_xml(self) -> str:
        lines = ["<?xml version=\"1.0\" encoding=\"utf-8\"?>", "<resources>"]
        for key, val in self.flat_resolved.items():
            res_name = key.replace(".", "_")
            if val.startswith("#"):
                lines.append(f"    <color name=\"{res_name}\">{val}</color>")
            elif val.endswith("px"):
                dp_val = val.replace("px", "dp")
                lines.append(f"    <dimen name=\"{res_name}\">{dp_val}</dimen>")
        lines.append("</resources>")
        return "\n".join(lines)


# ==============================================================================
# Design-to-Code Parity & Drift Detection Engine
# ==============================================================================
class ParityAuditEngine:
    def __init__(self, token_engine: TokenEngine, prod_css: Dict[str, str]):
        self.token_engine = token_engine
        self.prod_css = prod_css

    def run_audit(self) -> Dict[str, Any]:
        spec_tokens = {}
        for k, v in self.token_engine.flat_resolved.items():
            var_name = "--" + k.replace(".", "-")
            spec_tokens[var_name] = v

        drift_found = []
        matched = []
        missing_in_code = []

        # Compare specs vs production code
        for token_name, spec_val in spec_tokens.items():
            if token_name in self.prod_css:
                code_val = self.prod_css[token_name]
                if code_val.lower() == spec_val.lower():
                    matched.append((token_name, spec_val, code_val))
                else:
                    drift_found.append({
                        "token": token_name,
                        "spec": spec_val,
                        "code": code_val,
                        "type": "VALUE_MISMATCH"
                    })
            else:
                missing_in_code.append((token_name, spec_val))

        total_checked = len(spec_tokens)
        parity_score = (len(matched) / total_checked * 100.0) if total_checked > 0 else 0.0

        return {
            "total_tokens": total_checked,
            "matched_count": len(matched),
            "drift_count": len(drift_found),
            "missing_count": len(missing_in_code),
            "parity_score": parity_score,
            "drifts": drift_found,
            "missing": missing_in_code,
            "matched": matched
        }

    def validate_wcag(self) -> List[Dict[str, Any]]:
        results = []
        # Check Button Primary Contrast
        bg_token = self.token_engine.flat_resolved.get("component.button.primary.bg", "#2563eb")
        fg_token = self.token_engine.flat_resolved.get("component.button.primary.fg", "#ffffff")
        
        ratio = calculate_contrast_ratio(bg_token, fg_token)
        results.append({
            "component": "Button.Primary (Normal Text)",
            "bg": bg_token,
            "fg": fg_token,
            "ratio": ratio,
            "aa_pass": ratio >= 4.5,
            "aaa_pass": ratio >= 7.0
        })

        # Check Surface contrast
        bg_surface = self.token_engine.flat_resolved.get("semantic.color.surface.base", "#f8fafc")
        fg_surface = self.token_engine.flat_resolved.get("semantic.color.surface.contrast", "#0f172a")
        ratio_surface = calculate_contrast_ratio(bg_surface, fg_surface)
        results.append({
            "component": "Surface (Base vs Contrast Text)",
            "bg": bg_surface,
            "fg": fg_surface,
            "ratio": ratio_surface,
            "aa_pass": ratio_surface >= 4.5,
            "aaa_pass": ratio_surface >= 7.0
        })

        return results


# ==============================================================================
# Interactive CLI Dashboard & Scenarios
# ==============================================================================
def display_banner():
    banner = f"""{TermColor.FG_BRIGHT_CYAN}
╔══════════════════════════════════════════════════════════════════════════╗
║  ENTERPRISE DESIGN SYSTEMS & DESIGN-TO-CODE PARITY ARCHITECTURE SUITE    ║
║  Figma Tokens (W3C DTCG) ──> Token Compiler ──> AST Drift Auditor ──> CI ║
╚══════════════════════════════════════════════════════════════════════════╝{TermColor.RESET}"""
    print(banner)

def menu_view_tokens(engine: TokenEngine):
    print_header("CURRENT RESOLVED DESIGN TOKENS (W3C SPEC)")
    print(f"{TermColor.BOLD}{'TOKEN NAME':<40} {'RESOLVED VALUE':<20}{TermColor.RESET}")
    print("─" * 65)
    for k, v in engine.flat_resolved.items():
        val_color = TermColor.FG_BRIGHT_GREEN if v.startswith("#") else TermColor.FG_BRIGHT_YELLOW
        print(f"{TermColor.FG_WHITE}{k:<40}{TermColor.RESET} {val_color}{v:<20}{TermColor.RESET}")
    print("─" * 65)

def menu_run_audit(engine: TokenEngine, audit_engine: ParityAuditEngine):
    print_header("DESIGN-TO-CODE PARITY & DRIFT AUDIT REPORT")
    print_info("Analyzing synchronization contract between Token Registry and Production Codebase...")
    time.sleep(0.3)

    report = audit_engine.run_audit()
    score = report["parity_score"]
    
    score_color = TermColor.FG_BRIGHT_GREEN if score >= 90.0 else (TermColor.FG_BRIGHT_YELLOW if score >= 70.0 else TermColor.FG_BRIGHT_RED)
    print(f"\n Parity Synchronization Index : {score_color}{TermColor.BOLD}{score:.1f}%{TermColor.RESET}")
    print(f" Total Tokens Audited         : {report['total_tokens']}")
    print(f" In-Sync & Validated          : {TermColor.FG_BRIGHT_GREEN}{report['matched_count']}{TermColor.RESET}")
    print(f" Drift Violations Detected    : {TermColor.FG_BRIGHT_RED}{report['drift_count']}{TermColor.RESET}")
    print(f" Missing Tokens in Codebase   : {TermColor.FG_BRIGHT_YELLOW}{report['missing_count']}{TermColor.RESET}\n")

    if report["drift_count"] > 0:
        print_subbar("DETECTED CODE DRIFTS")
        for d in report["drifts"]:
            print_error(f"Token: {TermColor.BOLD}{d['token']}{TermColor.RESET}")
            print(f"       Design Spec: {TermColor.FG_GREEN}{d['spec']}{TermColor.RESET} | Codebase: {TermColor.FG_RED}{d['code']}{TermColor.RESET}")
    else:
        print_success("Zero token drift detected. Perfect Design-to-Code parity!")

    if report["missing_count"] > 0:
        print_subbar("MISSING TOKENS IN PRODUCTION")
        for m in report["missing"][:5]:
            print_warn(f"Unimplemented token: {m[0]} (Value: {m[1]})")

    print_subbar("ACCESSIBILITY (WCAG 2.1) TOKENS CONTRAST VALIDATION")
    wcag_results = audit_engine.validate_wcag()
    for w in wcag_results:
        aa_badge = f"{TermColor.FG_BRIGHT_GREEN}[PASS AA]{TermColor.RESET}" if w["aa_pass"] else f"{TermColor.FG_BRIGHT_RED}[FAIL AA]{TermColor.RESET}"
        aaa_badge = f"{TermColor.FG_BRIGHT_GREEN}[PASS AAA]{TermColor.RESET}" if w["aaa_pass"] else f"{TermColor.FG_BRIGHT_YELLOW}[FAIL AAA]{TermColor.RESET}"
        print(f" • {w['component']}")
        print(f"   Colors: BG={w['bg']} FG={w['fg']} | Contrast Ratio: {TermColor.BOLD}{w['ratio']:.2f}:1{TermColor.RESET} -> {aa_badge} {aaa_badge}")

def menu_simulate_drift(prod_css: Dict[str, str]):
    print_header("SIMULATE ACCIDENTAL CODEBASE DRIFT / REGRESSION")
    print_warn("Simulating uncoordinated developer patch directly in production CSS...")
    # Intentionally corrupt primary brand and button background
    prod_css["--semantic-color-brand-primary"] = "#ff0055"  # Unapproved hot-pink
    prod_css["--component-button-primary-bg"] = "#ff0055"
    prod_css["--component-button-primary-radius"] = "2px"   # Designer specified 8px
    time.sleep(0.3)
    print_success("3 Rogue mutations injected into '--semantic-color-brand-primary', '--component-button-primary-bg', '--component-button-primary-radius'.")
    print_info("Run Parity Audit now to inspect how CI Drift Gate detects this divergence!")

def menu_auto_remediate(prod_css: Dict[str, str], engine: TokenEngine):
    print_header("AUTOMATED CI REMEDIATION (DESIGN-TO-CODE SYNC)")
    print_info("Compiling Design Token truth source into CSS declarations...")
    time.sleep(0.2)
    for k, v in engine.flat_resolved.items():
        var_name = "--" + k.replace(".", "-")
        prod_css[var_name] = v
    print_success("Remediation complete! All production CSS variables overwritten with Token Registry.")

def menu_multiplatform_export(engine: TokenEngine):
    print_header("MULTI-PLATFORM COMPILER EXPORT")
    print(f"\n{TermColor.BOLD}[1] Web CSS Variables (:root){TermColor.RESET}")
    print(f"{TermColor.FG_CYAN}{engine.export_css_variables()[:280]}...\n{TermColor.RESET}")
    
    print(f"{TermColor.BOLD}[2] TypeScript Theme Definition (Type-Safe React/Vue){TermColor.RESET}")
    print(f"{TermColor.FG_MAGENTA}{engine.export_typescript_tokens()[:280]}...\n{TermColor.RESET}")
    
    print(f"{TermColor.BOLD}[3] Android Native (colors.xml / dimens.xml){TermColor.RESET}")
    print(f"{TermColor.FG_BRIGHT_BLUE}{engine.export_android_xml()[:280]}...\n{TermColor.RESET}")


# ==============================================================================
# Main Interactive Loop
# ==============================================================================
def main():
    token_engine = TokenEngine(MOCK_DESIGN_TOKENS_W3C)
    audit_engine = ParityAuditEngine(token_engine, PRODUCTION_CSS_REGISTRY)

    # Check if run non-interactively (e.g. CI / pipe)
    is_interactive = sys.stdin.isatty()

    if not is_interactive:
        display_banner()
        print_info("Non-interactive terminal detected. Running automated comprehensive demo suite...\n")
        menu_view_tokens(token_engine)
        menu_run_audit(token_engine, audit_engine)
        menu_simulate_drift(PRODUCTION_CSS_REGISTRY)
        menu_run_audit(token_engine, audit_engine)
        menu_auto_remediate(PRODUCTION_CSS_REGISTRY, token_engine)
        menu_run_audit(token_engine, audit_engine)
        menu_multiplatform_export(token_engine)
        print_success("Automated test run successfully concluded. Parity verified.")
        return

    while True:
        display_banner()
        print(f" {TermColor.BOLD}1.{TermColor.RESET} View Active Design Tokens (W3C Resolved)")
        print(f" {TermColor.BOLD}2.{TermColor.RESET} Run Parity Audit & WCAG Drift Gate")
        print(f" {TermColor.BOLD}3.{TermColor.RESET} Inject Rogue CSS Code Drift (Simulate Divergence)")
        print(f" {TermColor.BOLD}4.{TermColor.RESET} Auto-Remediate Codebase from Token Source of Truth")
        print(f" {TermColor.BOLD}5.{TermColor.RESET} Export Multi-platform Artifacts (CSS, TS, Android)")
        print(f" {TermColor.BOLD}6.{TermColor.RESET} Exit Simulator\n")

        try:
            choice = input(f"{TermColor.FG_BRIGHT_YELLOW}Select Menu [1-6]: {TermColor.RESET}").strip()
            if choice == "1":
                menu_view_tokens(token_engine)
            elif choice == "2":
                menu_run_audit(token_engine, audit_engine)
            elif choice == "3":
                menu_simulate_drift(PRODUCTION_CSS_REGISTRY)
            elif choice == "4":
                menu_auto_remediate(PRODUCTION_CSS_REGISTRY, token_engine)
            elif choice == "5":
                menu_multiplatform_export(token_engine)
            elif choice == "6" or choice.lower() == "q":
                print_info("Exiting Enterprise Design System Simulator. Goodbye!")
                break
            else:
                print_warn("Invalid option. Please choose between 1 and 6.")
        except (KeyboardInterrupt, EOFError):
            print("\n")
            print_info("Session interrupted. Exiting.")
            break

        print("\n" + TermColor.DIM + "Press Enter to return to main menu..." + TermColor.RESET)
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    main()
