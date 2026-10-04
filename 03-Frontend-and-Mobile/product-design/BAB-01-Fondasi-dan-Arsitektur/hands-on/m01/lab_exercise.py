#!/usr/bin/env python3
"""
Lab Exercise M01: Product Design Foundations & Architecture Simulator
BAB-01: Fondasi dan Arsitektur Product Design

Simulasi komprehensif konsep fondasi product design:
1. Double Diamond Discovery & Problem Framing (JTBD & HMW Framework)
2. Information Architecture (IA) Hierarchy & Cognitive Load Index
3. Design System Token Architecture & WCAG 2.1 Contrast Engine
4. Heuristic Usability Evaluation (Nielsen's 10 Heuristics)
"""

import sys
import os
import math
import json
import time
import argparse
from typing import Dict, List, Tuple, Any

# ANSI Escape Sequences for Terminal Styling
class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Background colors
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_DARK = "\033[100m"

C = TerminalColor


def print_banner():
    banner = f"""
{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════════════════════════════╗
║               PRODUCT DESIGN FOUNDATIONS & ARCHITECTURE              ║
║                  Hands-on Simulator Lab - Modul 01                   ║
╚══════════════════════════════════════════════════════════════════════╝{C.RESET}
{C.DIM}Topik: Double Diamond, JTBD, Info Architecture, Design Tokens & WCAG{C.RESET}
"""
    print(banner)


# -----------------------------------------------------------------------------
# 1. Double Diamond & JTBD Framing Engine
# -----------------------------------------------------------------------------
class JTBDProblemFramer:
    """Simulasi tahap Discover & Define dalam Double Diamond Framework"""

    @staticmethod
    def evaluate_framing(persona: str, trigger: str, action: str, outcome: str) -> Dict[str, Any]:
        score = 0
        feedback = []

        if len(trigger.strip().split()) >= 3:
            score += 25
            feedback.append(f"{C.GREEN}✔ Trigger konteks spesifik dan jelas.{C.RESET}")
        else:
            feedback.append(f"{C.YELLOW}⚠ Trigger terlalu umum. Tambahkan konteks situasional.{C.RESET}")

        if len(action.strip().split()) >= 3:
            score += 25
            feedback.append(f"{C.GREEN}✔ Action fokus pada motivasi pengguna, bukan sekadar klik UI.{C.RESET}")
        else:
            feedback.append(f"{C.YELLOW}⚠ Action terlalu dangkal atau berorientasi solusi mentah.{C.RESET}")

        if len(outcome.strip().split()) >= 3:
            score += 25
            feedback.append(f"{C.GREEN}✔ Functional & emotional outcome terdefinisi.{C.RESET}")
        else:
            feedback.append(f"{C.YELLOW}⚠ Outcome kurang terukur.{C.RESET}")

        if persona.strip():
            score += 25
            feedback.append(f"{C.GREEN}✔ Persona target valid: {persona}{C.RESET}")

        hmw_statement = f"How Might We membantu {persona} saat {trigger}, agar dapat {action}, sehingga {outcome}?"
        jtbd_statement = f"When {trigger}, I want to {action}, so I can {outcome}."

        return {
            "score": score,
            "jtbd": jtbd_statement,
            "hmw": hmw_statement,
            "feedback": feedback
        }


# -----------------------------------------------------------------------------
# 2. Information Architecture & Navigation Cognitive Load
# -----------------------------------------------------------------------------
class InformationArchitectureEvaluator:
    """Simulasi Information Architecture, visualisasi Sitemap, dan perhitungan Cognitive Load Index"""

    DEFAULT_SITEMAP = {
        "Home": {
            "Dashboard": {
                "Analytics Summary": {},
                "Quick Actions": {}
            },
            "Projects": {
                "Active Tasks": {
                    "Task Details": {
                        "Activity Logs": {}
                    }
                },
                "Archived": {}
            },
            "Settings": {
                "Profile": {},
                "Security": {
                    "2FA Authentication": {},
                    "Session History": {}
                },
                "Design Tokens": {}
            }
        }
    }

    @classmethod
    def calculate_depth_and_items(cls, tree: Dict[str, Any], current_depth: int = 1) -> Tuple[int, int, List[int]]:
        max_depth = current_depth
        total_items = len(tree)
        depth_list = [current_depth] * len(tree)

        for _, subtree in tree.items():
            if subtree:
                sub_max, sub_items, sub_depths = cls.calculate_depth_and_items(subtree, current_depth + 1)
                max_depth = max(max_depth, sub_max)
                total_items += sub_items
                depth_list.extend(sub_depths)

        return max_depth, total_items, depth_list

    @classmethod
    def render_tree(cls, tree: Dict[str, Any], prefix: str = "", is_last: bool = True):
        items = list(tree.items())
        count = len(items)
        for i, (key, subtree) in enumerate(items):
            last_item = (i == count - 1)
            connector = "└── " if last_item else "├── "
            print(f"{C.DIM}{prefix}{connector}{C.RESET}{C.BOLD}{C.BLUE}{key}{C.RESET}")
            new_prefix = prefix + ("    " if last_item else "│   ")
            if subtree:
                cls.render_tree(subtree, new_prefix, last_item)

    @classmethod
    def analyze_cognitive_load(cls, tree: Dict[str, Any]) -> Dict[str, Any]:
        max_depth, total_nodes, depth_list = cls.calculate_depth_and_items(tree)
        # Miller's Law (7 ± 2 items per level) & 3-Click Rule evaluation
        avg_depth = sum(depth_list) / len(depth_list) if depth_list else 1
        friction_index = (max_depth * 1.5) + (total_nodes * 0.25)

        status = "OPTIMAL" if max_depth <= 3 and friction_index < 12 else "MODERATE FRICTION"
        if max_depth > 4:
            status = "HIGH COGNITIVE OVERHEAD (Deep Nesting Detected)"

        return {
            "max_depth": max_depth,
            "total_nodes": total_nodes,
            "avg_depth": round(avg_depth, 2),
            "friction_index": round(friction_index, 2),
            "status": status
        }


# -----------------------------------------------------------------------------
# 3. Design Tokens Architecture & WCAG Contrast Engine
# -----------------------------------------------------------------------------
class DesignTokenEngine:
    """Evaluasi Primitive Token -> Semantic Token -> Accessibility WCAG 2.1 APCA/Luminance"""

    SAMPLE_DESIGN_TOKENS = {
        "primitive": {
            "color-blue-500": "#2563EB",
            "color-blue-900": "#1E3A8A",
            "color-slate-50": "#F8FAFC",
            "color-slate-900": "#0F172A",
            "color-amber-500": "#F59E0B"
        },
        "semantic": {
            "surface-primary": "color-slate-900",
            "surface-secondary": "color-slate-50",
            "text-primary-on-dark": "color-slate-50",
            "text-muted-on-dark": "color-amber-500",
            "action-brand-bg": "color-blue-500",
            "action-brand-fg": "color-slate-50"
        }
    }

    @staticmethod
    def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
        hex_clean = hex_str.lstrip("#")
        if len(hex_clean) == 3:
            hex_clean = "".join([c * 2 for c in hex_clean])
        return tuple(int(hex_clean[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore

    @classmethod
    def calculate_relative_luminance(cls, hex_color: str) -> float:
        r, g, b = cls.hex_to_rgb(hex_color)
        s_rgb = [x / 255.0 for x in (r, g, b)]
        lum_components = []
        for c in s_rgb:
            if c <= 0.03928:
                lum_components.append(c / 12.92)
            else:
                lum_components.append(((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * lum_components[0] + 0.7152 * lum_components[1] + 0.0722 * lum_components[2]

    @classmethod
    def calculate_contrast_ratio(cls, hex1: str, hex2: str) -> float:
        l1 = cls.calculate_relative_luminance(hex1)
        l2 = cls.calculate_relative_luminance(hex2)
        brightest = max(l1, l2)
        darkest = min(l1, l2)
        return (brightest + 0.05) / (darkest + 0.05)

    @classmethod
    def audit_contrast_pair(cls, name: str, fg_hex: str, bg_hex: str) -> Dict[str, Any]:
        ratio = cls.calculate_contrast_ratio(fg_hex, bg_hex)
        pass_aa_normal = ratio >= 4.5
        pass_aa_large = ratio >= 3.0
        pass_aaa_normal = ratio >= 7.0

        return {
            "name": name,
            "fg": fg_hex,
            "bg": bg_hex,
            "ratio": round(ratio, 2),
            "wcag_aa_body": pass_aa_normal,
            "wcag_aa_large": pass_aa_large,
            "wcag_aaa": pass_aaa_normal
        }


# -----------------------------------------------------------------------------
# 4. Nielsen Usability Heuristics Audit Matrix
# -----------------------------------------------------------------------------
class UsabilityHeuristicsAuditor:
    """10 Nielsen Usability Heuristics Scorecard Assessment"""

    HEURISTICS = [
        ("Visibility of System Status", "Apakah antarmuka memberikan feedback status realtime?"),
        ("Match between System and Real World", "Apakah terminologi familiar bagi mental model pengguna?"),
        ("User Control and Freedom", "Tersedia emergency exit, undo, redo, dan konfirmasi pembatalan?"),
        ("Consistency and Standards", "Komponen dan pola interaksi seragam sesuai design system?"),
        ("Error Prevention", "Mencegah kesalahan input sebelum submit terjadi?"),
        ("Recognition Rather Than Recall", "Informasi penting terlihat langsung tanpa memaksa mengingat?"),
        ("Flexibility and Efficiency of Use", "Mendukung shortcut untuk power user dan onboarding untuk pemula?"),
        ("Aesthetic and Minimalist Design", "Bebas dari visual noise, rasio sinyal terhadap gangguan tinggi?"),
        ("Help Users Recognize and Recover", "Pesan error bahasa manusia yang konstruktif dan solutif?"),
        ("Help and Documentation", "Dokumentasi kontekstual mudah diakses saat diperlukan?")
    ]

    @classmethod
    def run_benchmark(cls, scores: List[int]) -> Dict[str, Any]:
        total_possible = len(cls.HEURISTICS) * 5
        actual_total = sum(scores)
        percentage = (actual_total / total_possible) * 100

        if percentage >= 85:
            grade = f"{C.GREEN}EXCELLENT (Production Ready UX){C.RESET}"
        elif percentage >= 70:
            grade = f"{C.CYAN}ACCEPTABLE (Minor Usability Friction){C.RESET}"
        elif percentage >= 50:
            grade = f"{C.YELLOW}NEEDS REVISION (Critical Heuristic Gaps){C.RESET}"
        else:
            grade = f"{C.RED}POOR (High Risk of User Drop-off){C.RESET}"

        return {
            "total_score": actual_total,
            "max_score": total_possible,
            "percentage": round(percentage, 1),
            "grade": grade
        }


# -----------------------------------------------------------------------------
# Interactive CLI Workflow
# -----------------------------------------------------------------------------
def run_interactive_lab():
    print_banner()

    print(f"{C.BOLD}{C.MAGENTA}=== SIMULASI 1: Double Diamond & JTBD Problem Framing ==={C.RESET}")
    default_persona = "Data Analyst / Senior Product Designer"
    default_trigger = "memeriksa anomali metrics churn rate mingguan di dashboard"
    default_action = "mengelompokkan segmentasi user berdasarkan friksi onboarding"
    default_outcome = "merumuskan solusi arsitektur fitur baru yang menekan churn hingga 15%"

    print(f"{C.DIM}Menggunakan parameter arsitektur problem framing default...{C.RESET}")
    result_jtbd = JTBDProblemFramer.evaluate_framing(
        default_persona, default_trigger, default_action, default_outcome
    )
    print(f"\n{C.BOLD}Framing Score:{C.RESET} {C.GREEN}{result_jtbd['score']}/100{C.RESET}")
    print(f"{C.BOLD}Jobs-To-Be-Done:{C.RESET}\n  {C.CYAN}\"{result_jtbd['jtbd']}\"{C.RESET}")
    print(f"{C.BOLD}How Might We (HMW):{C.RESET}\n  {C.YELLOW}\"{result_jtbd['hmw']}\"{C.RESET}")
    for item in result_jtbd["feedback"]:
        print(f"  {item}")

    print(f"\n{C.BOLD}{C.MAGENTA}=== SIMULASI 2: Information Architecture & Cognitive Friction Tree ==={C.RESET}")
    print(f"{C.DIM}Struktur Navigasi Hierarkis App:{C.RESET}")
    InformationArchitectureEvaluator.render_tree(InformationArchitectureEvaluator.DEFAULT_SITEMAP)

    ia_metrics = InformationArchitectureEvaluator.analyze_cognitive_load(InformationArchitectureEvaluator.DEFAULT_SITEMAP)
    print(f"\n{C.BOLD}IA Metrics:{C.RESET}")
    print(f"  • Max Depth Level      : {C.CYAN}{ia_metrics['max_depth']}{C.RESET}")
    print(f"  • Total Navigation Nodes: {C.CYAN}{ia_metrics['total_nodes']}{C.RESET}")
    print(f"  • Avg Interaction Depth : {C.CYAN}{ia_metrics['avg_depth']}{C.RESET}")
    print(f"  • Cognitive Friction Idx: {C.YELLOW}{ia_metrics['friction_index']}{C.RESET}")
    print(f"  • Architecture Status   : {C.GREEN}{ia_metrics['status']}{C.RESET}")

    print(f"\n{C.BOLD}{C.MAGENTA}=== SIMULASI 3: Design Token System & WCAG 2.1 Contrast Engine ==={C.RESET}")
    tokens = DesignTokenEngine.SAMPLE_DESIGN_TOKENS
    print(f"{C.DIM}Primitive Tokens resolved to Semantic UI Pairs:{C.RESET}")

    pairs_to_test = [
        ("Dark Surface vs Light Text", tokens["primitive"]["color-slate-50"], tokens["primitive"]["color-slate-900"]),
        ("Brand Blue Button vs White Text", tokens["primitive"]["color-slate-50"], tokens["primitive"]["color-blue-500"]),
        ("Dark Surface vs Amber Warning", tokens["primitive"]["color-amber-500"], tokens["primitive"]["color-slate-900"]),
        ("Brand Blue Button vs Amber Accent", tokens["primitive"]["color-amber-500"], tokens["primitive"]["color-blue-500"])
    ]

    for label, fg, bg in pairs_to_test:
        audit = DesignTokenEngine.audit_contrast_pair(label, fg, bg)
        aa_badge = f"{C.GREEN}PASS AA{C.RESET}" if audit["wcag_aa_body"] else f"{C.RED}FAIL AA{C.RESET}"
        aaa_badge = f"{C.GREEN}PASS AAA{C.RESET}" if audit["wcag_aaa"] else f"{C.DIM}FAIL AAA{C.RESET}"
        print(f"  • [{audit['ratio']}:1] {C.BOLD}{label:<35}{C.RESET} (FG:{fg} BG:{bg}) -> {aa_badge} | {aaa_badge}")

    print(f"\n{C.BOLD}{C.MAGENTA}=== SIMULASI 4: Nielsen Usability Heuristics Scoring Audit ==={C.RESET}")
    simulated_scores = [5, 4, 4, 5, 4, 3, 4, 5, 4, 4]
    for i, (heuristic_name, desc) in enumerate(UsabilityHeuristicsAuditor.HEURISTICS):
        sc = simulated_scores[i]
        stars = f"{C.YELLOW}{'★' * sc}{C.DIM}{'☆' * (5 - sc)}{C.RESET}"
        print(f"  {i+1:02d}. {heuristic_name:<38} {stars} ({sc}/5)")

    audit_summary = UsabilityHeuristicsAuditor.run_benchmark(simulated_scores)
    print(f"\n{C.BOLD}Audit Score Result:{C.RESET} {audit_summary['total_score']}/{audit_summary['max_score']} "
          f"({audit_summary['percentage']}%) -> {audit_summary['grade']}")

    print(f"\n{C.GREEN}{C.BOLD}✔ Seluruh simulasi fondasi dan arsitektur product design berhasil dieksekusi.{C.RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Product Design Foundations Interactive Simulator")
    parser.add_argument("--demo", action="store_true", help="Jalankan otomatis simulasi demo komprehensif")
    parser.add_argument("--json", action="store_true", help="Output metrik evaluasi dalam format JSON")
    args = parser.parse_args()

    if args.json:
        result = {
            "module": "BAB-01-Fondasi-dan-Arsitektur",
            "ia_analysis": InformationArchitectureEvaluator.analyze_cognitive_load(
                InformationArchitectureEvaluator.DEFAULT_SITEMAP
            ),
            "heuristics_benchmark": UsabilityHeuristicsAuditor.run_benchmark([5, 4, 4, 5, 4, 3, 4, 5, 4, 4]),
            "timestamp": time.time(),
            "status": "success"
        }
        print(json.dumps(result, indent=2))
        return

    run_interactive_lab()


if __name__ == "__main__":
    main()
