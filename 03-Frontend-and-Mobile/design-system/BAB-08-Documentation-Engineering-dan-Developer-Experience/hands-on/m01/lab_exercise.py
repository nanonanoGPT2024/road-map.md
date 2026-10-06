#!/usr/bin/env python3
"""
BAB-08: Documentation Engineering & Developer Experience (DevX) in Design Systems
Hands-on Lab Exercise: Interactive DocGen, Token Sync & Component Playground Simulator.

Fitur Simulasi:
1. Automated Component DocGen Parser (AST docstring & prop extraction)
2. Token Documentation Synchronization & Drift Detection
3. Interactive CLI Component Live Playground
4. DevX Quality Gate & Doc Linter (Rule-based doc linting)
"""

import sys
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# ANSI Color Codes for Terminal UX
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_BLUE = "\033[44m"
BG_DARK = "\033[100m"

@dataclass
class PropDoc:
    name: str
    type_signature: str
    required: bool
    default_val: Optional[str]
    description: str

@dataclass
class ComponentMeta:
    name: str
    category: str
    status: str  # 'stable', 'beta', 'deprecated'
    description: str
    props: List[PropDoc] = field(default_factory=list)
    deprecation_notice: Optional[str] = None

@dataclass
class TokenDoc:
    name: str
    category: str
    raw_value: str
    resolved_css: str
    documented: bool

# Simulated Design System Repository Data
MOCK_COMPONENTS: List[ComponentMeta] = [
    ComponentMeta(
        name="Button",
        category="Actions",
        status="stable",
        description="Komponen tombol utama dengan varian primary, secondary, dan outline.",
        props=[
            PropDoc("variant", "'primary' | 'secondary' | 'danger'", False, "'primary'", "Gaya visual tombol"),
            PropDoc("size", "'sm' | 'md' | 'lg'", False, "'md'", "Ukuran padding dan font tombol"),
            PropDoc("disabled", "boolean", False, "false", "Menonaktifkan interaksi klik pengguna"),
            PropDoc("children", "ReactNode", True, None, "Label teks atau elemen anak di dalam tombol"),
            PropDoc("onClick", "() => void", False, "undefined", ""),  # undocumented description intended for linter
        ]
    ),
    ComponentMeta(
        name="LegacyAlert",
        category="Feedback",
        status="deprecated",
        description="Komponen notifikasi lama sebelum sistem Banner v2.",
        props=[
            PropDoc("message", "string", True, None, "Pesan peringatan"),
        ],
        deprecation_notice=None  # Missing migration note intended for linter
    ),
    ComponentMeta(
        name="Badge",
        category="Data Display",
        status="stable",
        description="Label status ringkas untuk metrik atau kategori entitas.",
        props=[
            PropDoc("count", "number", False, "0", "Angka numerik penanda badge"),
            PropDoc("color", "'neutral' | 'success' | 'warning' | 'error'", False, "'neutral'", "Warna latar semantik"),
        ]
    )
]

MOCK_TOKENS: List[TokenDoc] = [
    TokenDoc("color.brand.primary", "Color", "#2563EB", "--ds-color-brand-primary", True),
    TokenDoc("color.brand.secondary", "Color", "#475569", "--ds-color-brand-secondary", True),
    TokenDoc("spacing.sm", "Dimension", "8px", "--ds-spacing-sm", True),
    TokenDoc("spacing.md", "Dimension", "16px", "--ds-spacing-md", False),  # Undocumented token
    TokenDoc("radii.full", "Radius", "9999px", "--ds-radii-full", True),
]

def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{WHITE}{title.center(65)}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")

def run_docgen_parser():
    print_header("1. COMPONENT DOCGEN AST EXTRACTOR")
    print(f"{DIM}Memindai source code & mengekstrak metadata komponen secara otomatis...{RESET}\n")
    time.sleep(0.3)

    for comp in MOCK_COMPONENTS:
        status_badge = (
            f"{GREEN}[STABLE]{RESET}" if comp.status == "stable"
            else f"{YELLOW}[BETA]{RESET}" if comp.status == "beta"
            else f"{RED}[DEPRECATED]{RESET}"
        )
        print(f"{BOLD}{WHITE}• <{comp.name} />{RESET} {status_badge}  {DIM}(Category: {comp.category}){RESET}")
        print(f"  {CYAN}Deskripsi:{RESET} {comp.description}")
        print(f"  {BOLD}Props Specification ({len(comp.props)} props):{RESET}")
        
        for p in comp.props:
            req_str = f"{RED}wajib{RESET}" if p.required else f"{DIM}opsional{RESET}"
            default_str = f" [default: {YELLOW}{p.default_val}{RESET}]" if p.default_val else ""
            desc = p.description if p.description else f"{RED}(BELUM TERDOKUMENTASI){RESET}"
            print(f"    - {BOLD}{p.name}{RESET}: {MAGENTA}{p.type_signature}{RESET} ({req_str}){default_str}")
            print(f"      {DIM}Ket: {desc}{RESET}")
        print()

def run_token_sync():
    print_header("2. DESIGN TOKEN SYNC & DRIFT AUDIT")
    print(f"{DIM}Memeriksa sinkronisasi token Figma/Style-Dictionary dengan Documentation Site...{RESET}\n")
    time.sleep(0.3)

    drift_count = 0
    for tok in MOCK_TOKENS:
        if tok.documented:
            status = f"{GREEN}✓ SYNCHRONIZED{RESET}"
        else:
            status = f"{RED}✗ DRIFT DETECTED (Missing in Docs){RESET}"
            drift_count += 1
            
        print(f"  [{tok.category:<9}] {BOLD}{tok.name:<24}{RESET} -> {YELLOW}{tok.raw_value:<9}{RESET} ({tok.resolved_css}) {status}")

    print(f"\n{BOLD}Ringkasan Token:{RESET} Total: {len(MOCK_TOKENS)} | Sinkron: {len(MOCK_TOKENS) - drift_count} | Drift: {RED}{drift_count}{RESET}")

def run_devx_linter():
    print_header("3. DEVX QUALITY GATE & DOC LINTER")
    print(f"{DIM}Menjalankan aturan linting dokumentasi untuk mencegah degradasi DX...{RESET}\n")
    time.sleep(0.3)

    violations = []

    # Rule 1: Prop Documentation Completeness
    for comp in MOCK_COMPONENTS:
        for p in comp.props:
            if not p.description.strip():
                violations.append({
                    "rule": "E001_UNDOCUMENTED_PROP",
                    "severity": "ERROR",
                    "target": f"<{comp.name} /> -> prop '{p.name}'",
                    "message": "Setiap prop publik wajib menyertakan JSDoc deskripsi fungsional."
                })

    # Rule 2: Deprecated Component Migration Guide
    for comp in MOCK_COMPONENTS:
        if comp.status == "deprecated" and not comp.deprecation_notice:
            violations.append({
                "rule": "W002_MISSING_DEPRECATION_MIGRATION",
                "severity": "WARN",
                "target": f"<{comp.name} />",
                "message": "Komponen deprecated wajib memiliki petunjuk migrasi pengganti."
            })

    # Rule 3: Token Coverage
    for tok in MOCK_TOKENS:
        if not tok.documented:
            violations.append({
                "rule": "W003_ORPHAN_TOKEN",
                "severity": "WARN",
                "target": f"Token: {tok.name}",
                "message": "Token terdaftar dalam build engine tetapi tidak memiliki entri di docusite."
            })

    # Display Linter Results
    for v in violations:
        badge = f"{RED}[FAIL ERROR]{RESET}" if v["severity"] == "ERROR" else f"{YELLOW}[WARNING]{RESET}"
        print(f"  {badge} {BOLD}{v['rule']}{RESET} pada {WHITE}{v['target']}{RESET}")
        print(f"     {DIM}└─ {v['message']}{RESET}")

    score = max(0, 100 - (len([v for v in violations if v['severity'] == 'ERROR']) * 30 + len([v for v in violations if v['severity'] == 'WARN']) * 15))
    color = GREEN if score >= 80 else YELLOW if score >= 50 else RED
    print(f"\n{BOLD}DevX Doc Health Score:{RESET} {color}{score}/100{RESET}")

def run_interactive_playground():
    print_header("4. INTERACTIVE COMPONENT PLAYGROUND")
    print(f"{DIM}Simulasi live sandbox preview berbasis terminal props renderer.{RESET}\n")

    variants = ["primary", "secondary", "danger"]
    sizes = ["sm", "md", "lg"]

    print(f"{BOLD}Pilih Props untuk <Button /> preview:{RESET}")
    print(f"1. Variant : [1] Primary, [2] Secondary, [3] Danger")
    print(f"2. Size    : [1] Small, [2] Medium, [3] Large")
    print(f"3. State   : [1] Normal, [2] Disabled\n")

    # Automated demonstration of rendering
    test_configs = [
        {"variant": "primary", "size": "md", "disabled": False, "label": "Simpan Perubahan"},
        {"variant": "danger", "size": "sm", "disabled": False, "label": "Hapus Item"},
        {"variant": "secondary", "size": "lg", "disabled": True, "label": "Tombol Dinonaktifkan"},
    ]

    for idx, cfg in enumerate(test_configs, start=1):
        bg = BG_BLUE if cfg["variant"] == "primary" else "\033[41m" if cfg["variant"] == "danger" else BG_DARK
        state_str = f"{DIM}(disabled){RESET}" if cfg["disabled"] else f"{GREEN}(active){RESET}"
        pad = "  " if cfg["size"] == "lg" else " "
        
        print(f"{BOLD}Preview Kasus #{idx}:{RESET} variant={cfg['variant']} size={cfg['size']} {state_str}")
        print(f"  Code: {CYAN}<Button variant=\"{cfg['variant']}\" size=\"{cfg['size']}\" disabled={{{str(cfg['disabled']).lower()}}}>{cfg['label']}</Button>{RESET}")
        
        # Render terminal button box
        btn_face = f"{bg}{WHITE}{pad}{BOLD}{cfg['label']}{RESET}{bg}{pad}{RESET}"
        if cfg["disabled"]:
            btn_face = f"{BG_DARK}{DIM}{pad}{cfg['label']}{pad}{RESET}"
            
        print(f"  Render:\n    {btn_face}\n")

def main():
    print(f"{BOLD}{GREEN}=== DESIGN SYSTEM LAB: BAB 08 DOCUMENTATION ENGINEERING & DEVX ==={RESET}")
    print(f"Sistem manajemen otomasi dokumentasi, prop extraction & governance tooling.\n")
    
    run_docgen_parser()
    run_token_sync()
    run_devx_linter()
    run_interactive_playground()
    
    print_header("LAB VERIFIKASI SELESAI")
    print(f"{GREEN}✓ Semua modul DocGen, Token Sync, Linter, dan Playground tereksekusi dengan sukses.{RESET}\n")

if __name__ == "__main__":
    main()
