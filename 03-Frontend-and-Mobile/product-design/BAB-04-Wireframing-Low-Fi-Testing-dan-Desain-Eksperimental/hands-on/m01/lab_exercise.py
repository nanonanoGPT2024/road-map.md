#!/usr/bin/env python3
"""
BAB-04: Wireframing, Low-Fi Testing, dan Desain Eksperimental
Hands-on Lab Exercise: Interactive Low-Fi Simulation & Experimentation Engine

Modul ini mensimulasikan tiga pilar utama Product Design:
1. Low-Fidelity ASCII Wireframe Layout & Visual Hierarchy Scanner
2. Usability Testing Simulator & SUS (System Usability Scale) Evaluator
3. A/B Testing Statistical Significance & Minimum Detectable Effect (MDE) Calculator
"""

import sys
import math
import random
from typing import List, Dict, Tuple


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


def print_header(title: str) -> None:
    border = "=" * 64
    print(f"\n{ANSI.CYAN}{ANSI.BOLD}{border}")
    print(f" {title.center(62)} ")
    print(f"{border}{ANSI.RESET}\n")


def print_section(title: str) -> None:
    print(f"\n{ANSI.YELLOW}{ANSI.BOLD}▶ {title}{ANSI.RESET}")
    print(f"{ANSI.DIM}{'-' * 50}{ANSI.RESET}")


# ============================================================================
# 1. LOW-FIDELITY WIREFRAME & VISUAL HIERARCHY
# ============================================================================
class WireframeSimulator:
    """Simulasi Layout Wireframe Low-Fidelity & Audit Hierarki Visual."""

    TEMPLATES = {
        "mobile_checkout": [
            "+--------------------------------+",
            "| [=] App Checkout          (o)  |",
            "+--------------------------------+",
            "| [IMG: Product Thumbnail]      |",
            "| Item: Ergonomic Keyboard v2    |",
            "| Price: $120.00                 |",
            "+--------------------------------+",
            "| [Input: Shipping Address]     |",
            "| [Input: Discount Code]  [Apply]|",
            "+--------------------------------+",
            "| Subtotal: $120.00              |",
            "| Tax (10%): $12.00              |",
            "| TOTAL: $132.00                 |",
            "+--------------------------------+",
            "|   [ >>> PAY NOW ($132.00) <<< ]|",
            "+--------------------------------+"
        ],
        "saas_dashboard": [
            "+---------------------------------------------------------------+",
            "| [LOGO] SaaS Metrics    [Dashboard] [Reports] [Settings]  (User)|",
            "+--------------------+------------------------------------------+",
            "| [Menu]             | [KPI Card 1]  [KPI Card 2]  [KPI Card 3] |",
            "| - Overview         |  MRR: $42.5k   Churn: 1.8%   NPS: +64    |",
            "| - Analytics        +------------------------------------------+",
            "| - Customers        | [Primary Chart: Monthly Active Retention] |",
            "| - Integrations     |  |*                                      |",
            "|                    |  |***  ***  *****                        |",
            "|                    |  +------------------------------------   |",
            "|                    +------------------------------------------+",
            "| [!] Upgrade Plan   | [Table: Recent Transactions]             |",
            "+--------------------+------------------------------------------+"
        ]
    }

    @staticmethod
    def render_wireframe(name: str) -> None:
        lines = WireframeSimulator.TEMPLATES.get(name, [])
        if not lines:
            print(f"{ANSI.RED}Template '{name}' tidak ditemukan.{ANSI.RESET}")
            return

        print(f"{ANSI.GREEN}{ANSI.BOLD}Rendering Low-Fi ASCII Wireframe: {name}{ANSI.RESET}")
        for line in lines:
            if "PAY NOW" in line or "Upgrade Plan" in line:
                # Primary CTA
                highlighted = line.replace("PAY NOW ($132.00)", f"{ANSI.BG_MAGENTA}{ANSI.WHITE} PAY NOW ($132.00) {ANSI.RESET}")
                highlighted = highlighted.replace("Upgrade Plan", f"{ANSI.YELLOW}{ANSI.BOLD}Upgrade Plan{ANSI.RESET}")
                print(highlighted)
            elif "Input:" in line or "IMG:" in line:
                print(f"{ANSI.CYAN}{line}{ANSI.RESET}")
            elif "TOTAL:" in line or "MRR:" in line:
                print(f"{ANSI.BOLD}{line}{ANSI.RESET}")
            else:
                print(f"{ANSI.DIM}{line}{ANSI.RESET}")

    @staticmethod
    def audit_hierarchy(name: str) -> Dict[str, str]:
        print(f"\n{ANSI.MAGENTA}{ANSI.BOLD}[Visual Hierarchy & Eye-Tracking Analysis]{ANSI.RESET}")
        if name == "mobile_checkout":
            analysis = {
                "Eye Pattern": "Gutenberg Diagram (Terminal Area: Bottom-right CTA)",
                "Primary CTA Anchor": "Pay Now button memiliki contrast & weight tertinggi",
                "Cognitive Load": "Rendah (Single-column layout, zero distraction)",
                "Accessibility Fitts' Law": "Lolos (Full-width thumb zone target area)"
            }
        else:
            analysis = {
                "Eye Pattern": "F-Pattern (Top Navigation bar -> Left sidebar -> KPI cards)",
                "Primary Focus": "MRR & Core SaaS Retention Chart",
                "Cognitive Load": "Sedang (Information density tinggi, modular card grid)",
                "Accessibility Fitts' Law": "Lolos (Clear navigation anchors)"
            }
        for k, v in analysis.items():
            print(f" • {ANSI.BOLD}{k:24}:{ANSI.RESET} {ANSI.CYAN}{v}{ANSI.RESET}")
        return analysis


# ============================================================================
# 2. LOW-FI USABILITY TESTING & SUS EVALUATION
# ============================================================================
class UsabilitySimulator:
    """Simulasi Usability Testing 5 Partisipan & Evaluasi Skor SUS."""

    @staticmethod
    def calculate_sus(responses: List[int]) -> float:
        """
        Kalkulasi skor SUS (System Usability Scale) 10 Pertanyaan (Skala 1-5).
        - Pertanyaan Ganjil (Positif): Nilai - 1
        - Pertanyaan Genap (Negatif): 5 - Nilai
        - Total skor dikalikan 2.5 (Range 0 - 100)
        """
        if len(responses) != 10:
            raise ValueError("SUS membutuhkan tepat 10 respon instrumen.")

        adjusted_sum = 0
        for i, score in enumerate(responses):
            if i % 2 == 0:  # Odd question (index 0, 2, 4...)
                adjusted_sum += (score - 1)
            else:          # Even question (index 1, 3, 5...)
                adjusted_sum += (5 - score)

        return adjusted_sum * 2.5

    @staticmethod
    def interpret_sus(score: float) -> Tuple[str, str]:
        if score >= 85:
            return "Grade A+ (Exceptional)", ANSI.GREEN
        elif score >= 80:
            return "Grade A (Excellent)", ANSI.GREEN
        elif score >= 68:
            return "Grade C (Average / Acceptable Threshold)", ANSI.YELLOW
        elif score >= 50:
            return "Grade D (Poor / Usability Issues Detected)", ANSI.RED
        else:
            return "Grade F (Unacceptable / High Friction)", ANSI.RED

    @staticmethod
    def run_testing_simulation() -> None:
        print_section("Simulasi Sesi Usability Testing (5 Partisipan - Jakob Nielsen Standard)")
        participants = [
            {"id": "P01", "persona": "First-time Buyer", "task_success": True, "time_sec": 42, "sus_raw": [5, 1, 4, 2, 5, 1, 5, 2, 4, 1]},
            {"id": "P02", "persona": "Tech Savvy User", "task_success": True, "time_sec": 28, "sus_raw": [5, 2, 5, 1, 5, 1, 4, 1, 5, 1]},
            {"id": "P03", "persona": "Elderly / Casual", "task_success": False, "time_sec": 95, "sus_raw": [3, 4, 3, 3, 3, 4, 2, 4, 2, 4]},
            {"id": "P04", "persona": "Mobile Shopper", "task_success": True, "time_sec": 36, "sus_raw": [4, 2, 4, 1, 4, 2, 5, 2, 4, 2]},
            {"id": "P05", "persona": "Impatient User", "task_success": True, "time_sec": 31, "sus_raw": [4, 1, 5, 2, 4, 1, 4, 1, 4, 2]},
        ]

        total_sus = 0.0
        success_count = 0
        total_time = 0

        print(f"{'User':<6} | {'Persona':<18} | {'Task Status':<12} | {'Time (s)':<9} | {'SUS Score':<10}")
        print("-" * 65)

        for p in participants:
            sus = UsabilitySimulator.calculate_sus(p["sus_raw"])
            total_sus += sus
            total_time += p["time_sec"]
            if p["task_success"]:
                success_count += 1
                status = f"{ANSI.GREEN}SUCCESS{ANSI.RESET}"
            else:
                status = f"{ANSI.RED}FAILED{ANSI.RESET}"

            grade_label, color = UsabilitySimulator.interpret_sus(sus)
            print(f"{p['id']:<6} | {p['persona']:<18} | {status:<21} | {p['time_sec']:<9} | {color}{sus:>5.1f}{ANSI.RESET}")

        avg_sus = total_sus / len(participants)
        success_rate = (success_count / len(participants)) * 100
        avg_time = total_time / len(participants)
        grade_summary, summary_color = UsabilitySimulator.interpret_sus(avg_sus)

        print("-" * 65)
        print(f"{ANSI.BOLD}Task Completion Rate :{ANSI.RESET} {ANSI.CYAN}{success_rate:.1f}%{ANSI.RESET}")
        print(f"{ANSI.BOLD}Average Time on Task  :{ANSI.RESET} {ANSI.CYAN}{avg_time:.1f} detik{ANSI.RESET}")
        print(f"{ANSI.BOLD}Average SUS Score     :{ANSI.RESET} {summary_color}{avg_sus:.1f} -> {grade_summary}{ANSI.RESET}")


# ============================================================================
# 3. A/B TESTING & EXPERIMENTAL DESIGN CALCULATOR
# ============================================================================
class ExperimentEngine:
    """Kalkulator Inferensi Statistik A/B Testing & Signifikansi Desain."""

    @staticmethod
    def calculate_ab_test(visitors_a: int, conv_a: int, visitors_b: int, conv_b: int) -> Dict[str, float]:
        """Menghitung Two-Proportion Z-Test untuk A/B testing."""
        p_a = conv_a / visitors_a
        p_b = conv_b / visitors_b
        lift = ((p_b - p_a) / p_a) * 100.0

        # Pooled sample proportion
        p_pool = (conv_a + conv_b) / (visitors_a + visitors_b)
        se_pool = math.sqrt(p_pool * (1 - p_pool) * ((1 / visitors_a) + (1 / visitors_b)))

        if se_pool == 0:
            z_score = 0.0
        else:
            z_score = (p_b - p_a) / se_pool

        # Approximasi dua sisi p-value dari z-score
        # Error function approx: p_value = 2 * (1 - norm_cdf(|z|))
        p_value = math.erfc(abs(z_score) / math.sqrt(2))

        return {
            "rate_a": p_a,
            "rate_b": p_b,
            "lift": lift,
            "z_score": z_score,
            "p_value": p_value,
            "stat_sig": (1.0 - p_value) * 100.0
        }

    @staticmethod
    def run_experiment_demo() -> None:
        print_section("A/B Testing Eksperimental: Low-Fi Baseline vs Variasi Desain")
        print("Hypothesis: Mengubah microcopy CTA dari 'Beli Sekarang' ke 'Mulai Uji Coba Gratis'")
        print("serta memperjelas visual anchor akan meningkatkan conversion rate >= 15%.\n")

        # Scenario
        vis_a, conv_a = 5200, 260   # Baseline 5.0%
        vis_b, conv_b = 5150, 345   # Variant B 6.7%

        results = ExperimentEngine.calculate_ab_test(vis_a, conv_a, vis_b, conv_b)

        print(f" • {ANSI.BOLD}Variant A (Control)   :{ANSI.RESET} {vis_a:,} visitors, {conv_a} conversions ({results['rate_a']*100:.2f}%)")
        print(f" • {ANSI.BOLD}Variant B (Challenger):{ANSI.RESET} {vis_b:,} visitors, {conv_b} conversions ({results['rate_b']*100:.2f}%)")
        print(f" • {ANSI.BOLD}Conversion Lift       :{ANSI.RESET} {ANSI.GREEN}+{results['lift']:.2f}%{ANSI.RESET}")
        print(f" • {ANSI.BOLD}Z-Score               :{ANSI.RESET} {results['z_score']:.4f}")
        print(f" • {ANSI.BOLD}p-value               :{ANSI.RESET} {results['p_value']:.5f}")
        print(f" • {ANSI.BOLD}Confidence Level      :{ANSI.RESET} {ANSI.CYAN}{results['stat_sig']:.2f}%{ANSI.RESET}")

        if results["p_value"] < 0.05:
            print(f"\n{ANSI.GREEN}{ANSI.BOLD}✔ REKOMENDASI DESAIN: Hasil signifikan secara statistik (p < 0.05).")
            print(f"Hipotesis diterima! Desain varian B siap dilanjutkan ke High-Fi & Produksi.{ANSI.RESET}")
        else:
            print(f"\n{ANSI.RED}{ANSI.BOLD}✖ REKOMENDASI DESAIN: Hasil tidak signifikan (p >= 0.05).")
            print(f"Pertahankan baseline atau uji hipotesis baru.{ANSI.RESET}")


# ============================================================================
# MAIN INTERACTIVE CLI
# ============================================================================
def display_menu() -> None:
    print(f"\n{ANSI.YELLOW}{ANSI.BOLD}PILIH MENU SIMULASI PRODUCT DESIGN:{ANSI.RESET}")
    print(f" {ANSI.CYAN}1.{ANSI.RESET} Render Mobile Checkout Wireframe + Audit Hierarki")
    print(f" {ANSI.CYAN}2.{ANSI.RESET} Render SaaS Dashboard Wireframe + F-Pattern Scan")
    print(f" {ANSI.CYAN}3.{ANSI.RESET} Jalankan Usability Testing & Evaluasi SUS Score")
    print(f" {ANSI.CYAN}4.{ANSI.RESET} Jalankan A/B Testing Significance Calculator")
    print(f" {ANSI.CYAN}5.{ANSI.RESET} Eksekusi Full End-to-End Walkthrough (Semua Modul)")
    print(f" {ANSI.RED}0.{ANSI.RESET} Keluar")


def run_full_suite() -> None:
    print_header("FULL SIMULATION: WIREFRAMING TO EXPERIMENTATION")
    WireframeSimulator.render_wireframe("mobile_checkout")
    WireframeSimulator.audit_hierarchy("mobile_checkout")

    print("\n" + "="*60 + "\n")
    WireframeSimulator.render_wireframe("saas_dashboard")
    WireframeSimulator.audit_hierarchy("saas_dashboard")

    UsabilitySimulator.run_testing_simulation()
    ExperimentEngine.run_experiment_demo()

    print_header("SIMULASI SUKSES - PRODUCT DESIGN LAB BERHASIL DIJALANKAN")


def main() -> None:
    # Jika dijalankan dengan flag non-interaktif atau tanpa TTY
    if "--demo" in sys.argv or "--all" in sys.argv or not sys.stdin.isatty():
        run_full_suite()
        return

    print_header("PRODUCT DESIGN LAB: BAB-04 EXPERIMENTAL ENGINE")
    while True:
        display_menu()
        try:
            choice = input(f"\n{ANSI.BOLD}Masukkan pilihan (0-5): {ANSI.RESET}").strip()
            if choice == "1":
                WireframeSimulator.render_wireframe("mobile_checkout")
                WireframeSimulator.audit_hierarchy("mobile_checkout")
            elif choice == "2":
                WireframeSimulator.render_wireframe("saas_dashboard")
                WireframeSimulator.audit_hierarchy("saas_dashboard")
            elif choice == "3":
                UsabilitySimulator.run_testing_simulation()
            elif choice == "4":
                ExperimentEngine.run_experiment_demo()
            elif choice == "5":
                run_full_suite()
            elif choice in ("0", "q", "exit"):
                print(f"\n{ANSI.GREEN}Terima kasih telah menggunakan Product Design Lab Engine!{ANSI.RESET}\n")
                break
            else:
                print(f"{ANSI.RED}Pilihan tidak valid, silakan coba lagi.{ANSI.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{ANSI.YELLOW}Sesi dihentikan.{ANSI.RESET}\n")
            break


if __name__ == "__main__":
    main()
