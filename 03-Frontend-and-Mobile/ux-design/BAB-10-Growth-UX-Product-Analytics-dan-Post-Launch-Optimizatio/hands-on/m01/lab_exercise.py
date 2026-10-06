#!/usr/bin/env python3
"""
Growth UX & Product Analytics Simulator (BAB-10)
Lab Exercise: Post-Launch Optimization, Funnel Diagnostics, and A/B Testing Engine.

Konsep yang disimulasikan:
1. AARRR Pirate Metrics Funnel Analysis & Drop-off Diagnostics
2. Frequentist Two-Sample Z-Test Engine for Conversion Rate A/B Testing
3. Cohort Retention Heatmap Simulation (Day 0 to Day 30)
4. Net Promoter Score (NPS) & Customer Feedback Quadrant
"""

import math
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


@dataclass
class FunnelStage:
    name: str
    users: int
    benchmark_dropoff_pct: float


@dataclass
class ABExperiment:
    name: str
    control_visitors: int
    control_conversions: int
    variant_visitors: int
    variant_conversions: int
    alpha: float = 0.05  # 95% Confidence Level


def normal_cdf(z: float) -> float:
    """Approximation of the standard normal cumulative distribution function (CDF)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def print_banner() -> None:
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("=" * 72)
    print("   GROWTH UX & PRODUCT ANALYTICS LAB ENGINE -- BAB 10")
    print("   Post-Launch UX Optimization & Experimentation Suite")
    print("=" * 72)
    print(f"{Colors.RESET}")


def run_funnel_diagnostics() -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}--- [1] AARRR PIRATE FUNNEL & DROP-OFF DIAGNOSTICS ---{Colors.RESET}")
    print(f"{Colors.DIM}Menganalisis friksi UX sepanjang lifecycle user dari Akuisisi hingga Monetisasi.{Colors.RESET}\n")

    stages = [
        FunnelStage("1. Acquisition (Landing Page View)", 24500, 0.0),
        FunnelStage("2. Activation (Onboarding Completed)", 11270, 50.0),
        FunnelStage("3. Retention (Active Week 2)", 4508, 55.0),
        FunnelStage("4. Revenue (Subscribed / Transacted)", 1127, 70.0),
        FunnelStage("5. Referral (Shared Invite / Advocate)", 225, 75.0),
    ]

    base_users = stages[0].users
    print(f"{Colors.BOLD}{'Tahap Funnel':<35} {'Users':<10} {'Step Conv %':<12} {'Overall %':<10} {'Visual Drop-off'}{Colors.RESET}")
    print("-" * 75)

    for i, stage in enumerate(stages):
        step_conv = 100.0 if i == 0 else (stage.users / stages[i - 1].users) * 100.0
        overall_conv = (stage.users / base_users) * 100.0
        bar_len = int(overall_conv / 2.5)
        bar = "█" * bar_len

        color = Colors.GREEN if step_conv >= 40.0 else (Colors.YELLOW if step_conv >= 25.0 else Colors.RED)

        print(
            f"{stage.name:<35} {stage.users:<10} {color}{step_conv:>8.2f}%{Colors.RESET}   "
            f"{Colors.CYAN}{overall_conv:>7.2f}%{Colors.RESET}  {color}{bar}{Colors.RESET}"
        )

    print("-" * 75)
    print(f"{Colors.YELLOW}{Colors.BOLD}Diagnosa UX & Area Intervensi:{Colors.RESET}")
    print(f" • {Colors.RED}Bottleneck Kritis:{Colors.RESET} Onboarding Activation ke Retention drop ~60%.")
    print(f"   {Colors.DIM}Rekomendasi: Terapkan Empty State guidance, in-app micro-walkthrough, dan checklist onboarding.{Colors.RESET}")
    print(f" • {Colors.YELLOW}Monetization Leakage:{Colors.RESET} Drop dari Retention ke Revenue ~75%.")
    print(f"   {Colors.DIM}Rekomendasi: Kurangi checkout friction, hadirkan transparansi pricing tier, dan contextual paywall.{Colors.RESET}\n")


def calculate_ab_significance(exp: ABExperiment) -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}--- [2] STATISTICAL A/B TESTING ENGINE (Z-TEST) ---{Colors.RESET}")
    print(f"{Colors.DIM}Evaluasi validitas hasil uji coba UX Variant vs Control.{Colors.RESET}\n")

    p1 = exp.control_conversions / exp.control_visitors
    p2 = exp.variant_conversions / exp.variant_visitors
    p_pool = (exp.control_conversions + exp.variant_conversions) / (exp.control_visitors + exp.variant_visitors)

    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / exp.control_visitors + 1.0 / exp.variant_visitors))
    z_score = (p2 - p1) / se if se > 0 else 0.0
    p_value = 2.0 * (1.0 - normal_cdf(abs(z_score)))
    relative_lift = ((p2 - p1) / p1) * 100.0 if p1 > 0 else 0.0

    print(f"{Colors.BOLD}Eksperimen:{Colors.RESET} {exp.name}")
    print(f" • Control (A) : {exp.control_conversions:,}/{exp.control_visitors:,} ({p1 * 100:.2f}%)")
    print(f" • Variant (B) : {exp.variant_conversions:,}/{exp.variant_visitors:,} ({p2 * 100:.2f}%)")
    print(f" • Relative Lift : {Colors.GREEN if relative_lift > 0 else Colors.RED}{relative_lift:+.2f}%{Colors.RESET}")
    print(f" • Z-Score       : {z_score:.4f}")
    print(f" • p-Value       : {p_value:.6f} (Alpha: {exp.alpha})")

    if p_value < exp.alpha:
        print(
            f"\n{Colors.GREEN}{Colors.BOLD}[✓] STATISTICALLY SIGNIFICANT ({ (1 - exp.alpha) * 100:.0f}% Confidence Level){Colors.RESET}"
        )
        print(f"   Hasil bukan fluktuasi acak. Variant B dapat dideploy permanen ke 100% user traffic.")
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}[!] STATISTICALLY INCONCLUSIVE (p >= {exp.alpha}){Colors.RESET}")
        print(f"   Belum cukup bukti statistik untuk menyatakan Variant B unggul. Pertahankan Control atau kumpulkan lebih banyak sampel.")
    print()


def render_cohort_retention() -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}--- [3] COHORT RETENTION HEATMAP (WEEKLY) ---{Colors.RESET}")
    print(f"{Colors.DIM}Retensi pengguna dari W0 hingga W4 pasca peluncuran redesign onboarding.{Colors.RESET}\n")

    cohorts = [
        ("Cohort 2026-W1", [100.0, 48.2, 34.5, 29.1, 26.4]),
        ("Cohort 2026-W2", [100.0, 52.6, 38.1, 33.0, 30.2]),
        ("Cohort 2026-W3 (Redesign)", [100.0, 64.8, 49.3, 44.5, 41.0]),
        ("Cohort 2026-W4", [100.0, 67.2, 52.0, 47.1, 43.8]),
    ]

    header_cols = f"{'Cohort Group':<26} {'W0':<8} {'W1':<8} {'W2':<8} {'W3':<8} {'W4':<8}"
    print(f"{Colors.BOLD}{header_cols}{Colors.RESET}")
    print("-" * 68)

    for cohort_name, vals in cohorts:
        row = f"{cohort_name:<26} "
        for v in vals:
            if v >= 60.0:
                color = Colors.GREEN
            elif v >= 40.0:
                color = Colors.CYAN
            elif v >= 30.0:
                color = Colors.YELLOW
            else:
                color = Colors.RED
            row += f"{color}{v:>5.1f}%{Colors.RESET}   "
        print(row)
    print("-" * 68)
    print(f"{Colors.GREEN}Insight:{Colors.RESET} Intervensi Redesign pada W3 meningkatkan D30 retention plateau dari ~26% ke >40%.\n")


def calculate_nps_breakdown() -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}--- [4] NET PROMOTER SCORE (NPS) & CSAT ANALYZER ---{Colors.RESET}")
    print(f"{Colors.DIM}Distribusi sentimen kepuasan dan loyalitas pengguna.{Colors.RESET}\n")

    ratings = {
        "Promoters (9-10)": 642,
        "Passives (7-8)": 288,
        "Detractors (0-6)": 154,
    }
    total_resp = sum(ratings.values())
    pct_prom = (ratings["Promoters (9-10)"] / total_resp) * 100.0
    pct_detr = (ratings["Detractors (0-6)"] / total_resp) * 100.0
    nps_score = pct_prom - pct_detr

    for segment, count in ratings.items():
        pct = (count / total_resp) * 100.0
        bar = "■" * int(pct / 2)
        color = Colors.GREEN if "Promoter" in segment else (Colors.YELLOW if "Passive" in segment else Colors.RED)
        print(f"{segment:<20} : {count:>5} ({pct:>5.1f}%) {color}{bar}{Colors.RESET}")

    status_color = Colors.GREEN if nps_score >= 50 else (Colors.YELLOW if nps_score >= 20 else Colors.RED)
    print(f"\n{Colors.BOLD}Total Responden :{Colors.RESET} {total_resp:,}")
    print(f"{Colors.BOLD}NPS Score       :{Colors.RESET} {status_color}{nps_score:+.1f}{Colors.RESET} (Skala -100 s/d +100)")
    if nps_score > 40:
        print(f"{Colors.GREEN}Klasifikasi: EXCELLENT / WORLD CLASS PRODUCT FIT{Colors.RESET}\n")
    else:
        print(f"{Colors.YELLOW}Klasifikasi: AVERAGE / PERLU UX AUDIT PADA DETRACTORS{Colors.RESET}\n")


def interactive_menu() -> None:
    while True:
        print(f"{Colors.BOLD}Menu Simulasi UX Analytics:{Colors.RESET}")
        print(" [1] Jalankan Analisis Funnel AARRR & Drop-off")
        print(" [2] Uji Signifikansi Statistik A/B Testing (Z-Test)")
        print(" [3] Tampilkan Cohort Retention Heatmap")
        print(" [4] Hitung Net Promoter Score (NPS) Breakdown")
        print(" [5] Jalankan Seluruh Audit Komprehensif (Full Report)")
        print(" [0] Keluar")

        try:
            choice = input(f"\n{Colors.CYAN}Pilih opsi [0-5]: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            run_funnel_diagnostics()
        elif choice == "2":
            exp = ABExperiment(
                name="One-Click Checkout & Simplified KYC vs Legacy Wizard",
                control_visitors=12500,
                control_conversions=780,
                variant_visitors=12650,
                variant_conversions=945,
            )
            calculate_ab_significance(exp)
        elif choice == "3":
            render_cohort_retention()
        elif choice == "4":
            calculate_nps_breakdown()
        elif choice == "5":
            run_funnel_diagnostics()
            time.sleep(0.3)
            exp = ABExperiment(
                name="Frictionless Onboarding Experiment (Variant B)",
                control_visitors=14200,
                control_conversions=1562,
                variant_visitors=14180,
                variant_conversions=1890,
            )
            calculate_ab_significance(exp)
            time.sleep(0.3)
            render_cohort_retention()
            time.sleep(0.3)
            calculate_nps_breakdown()
        elif choice == "0":
            print(f"{Colors.GREEN}Selesai. Selamat mengoptimalkan UX!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan coba lagi.{Colors.RESET}\n")


def main() -> None:
    print_banner()
    # Check if run non-interactively or with flags
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "--demo", "-a"):
        run_funnel_diagnostics()
        exp = ABExperiment(
            name="One-Click Onboarding Experiment (Variant B)",
            control_visitors=15000,
            control_conversions=1200,
            variant_visitors=15200,
            variant_conversions=1480,
        )
        calculate_ab_significance(exp)
        render_cohort_retention()
        calculate_nps_breakdown()
    else:
        # Check if stdin is interactive
        if sys.stdin.isatty():
            interactive_menu()
        else:
            # Fallback to demo mode in pipes/automated tests
            run_funnel_diagnostics()
            exp = ABExperiment(
                name="Automated Non-TTY Pipeline Check",
                control_visitors=10000,
                control_conversions=800,
                variant_visitors=10000,
                variant_conversions=960,
            )
            calculate_ab_significance(exp)
            render_cohort_retention()
            calculate_nps_breakdown()


if __name__ == "__main__":
    main()
