#!/usr/bin/env python3
"""
Lab Exercise: Product Metrics, Analytics & Continuous Experimentation Simulation
BAB-09 Product Design: Product Metrics, Analytics & Continuous Experimentation
"""

import sys
import math
import random
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

# ANSI Color Codes for terminal UI
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

@dataclass
class FunnelStage:
    name: str
    count: int
    conversion_from_prev: float
    dropoff_rate: float

class ProductAnalyticsLab:
    def __init__(self):
        self.banner()

    def banner(self):
        print(f"{Colors.HEADER}{Colors.BOLD}========================================================================{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}  LAB SIMULASI: PRODUCT METRICS, ANALYTICS & EXPERIMENTATION ENGINE     {Colors.RESET}")
        print(f"{Colors.HEADER}{Colors.BOLD}  BAB-09: Product Design - Quantitative & Experimentation Mastery        {Colors.RESET}")
        print(f"{Colors.HEADER}{Colors.BOLD}========================================================================{Colors.RESET}\n")

    # -------------------------------------------------------------
    # 1. AARRR Pirate Metrics Funnel Simulation
    # -------------------------------------------------------------
    def simulate_aarrr_funnel(self, visitors: int = 10000) -> List[FunnelStage]:
        print(f"{Colors.YELLOW}{Colors.BOLD}[1] SIMULASI PIRATE METRICS FUNNEL (AARRR){Colors.RESET}")
        print(f"Menjalankan simulasi perjalanan pengguna dari akuisisi awal hingga revenue...\n")

        # Realistic conversion benchmarks
        acquisition = visitors
        activation = int(acquisition * 0.42)      # 42% sign up & hit aha-moment
        retention = int(activation * 0.35)        # 35% return weekly (W1 retention)
        revenue = int(retention * 0.22)           # 22% convert to paying tier
        referral = int(retention * 0.15)          # 15% invite/refer peers

        stages = [
            FunnelStage("Acquisition (Visitors)", acquisition, 1.0, 0.0),
            FunnelStage("Activation (Activated Users)", activation, activation / acquisition, 1.0 - (activation / acquisition)),
            FunnelStage("Retention (Day-7 Active)", retention, retention / activation, 1.0 - (retention / activation)),
            FunnelStage("Revenue (Paying Customers)", revenue, revenue / retention, 1.0 - (revenue / retention)),
            FunnelStage("Referral (Advocates/Shares)", referral, referral / retention, 1.0 - (referral / retention)),
        ]

        max_bar_width = 40
        print(f"{Colors.BOLD}{'Tahap Funnel':<30} | {'Jumlah':<10} | {'Conv %':<8} | {'Drop %':<8} | Visualisasi Funnel{Colors.RESET}")
        print("-" * 80)

        for s in stages:
            bar_len = int((s.count / acquisition) * max_bar_width)
            bar_color = Colors.GREEN if s.conversion_from_prev > 0.30 else (Colors.YELLOW if s.conversion_from_prev > 0.15 else Colors.RED)
            bar_visual = f"{bar_color}{'█' * bar_len}{'░' * (max_bar_width - bar_len)}{Colors.RESET}"
            conv_pct = f"{s.conversion_from_prev * 100:6.1f}%"
            drop_pct = f"{s.dropoff_rate * 100:6.1f}%"
            print(f"{s.name:<30} | {s.count:<10} | {conv_pct:<8} | {drop_pct:<8} | {bar_visual}")

        print(f"\n{Colors.CYAN}Analisis Diagnostik:{Colors.RESET}")
        print(f"• Bottleneck terbesar terdeteksi pada transisi: {Colors.RED}Activation -> Retention{Colors.RESET} (Dropoff: 65.0%)")
        print(f"• Rekomendasi Design: Perbaiki Onboarding Habit Loop, Push Notification, dan Day-3 Trigger Re-engagement.\n")
        return stages

    # -------------------------------------------------------------
    # 2. Cohort Retention Matrix
    # -------------------------------------------------------------
    def simulate_cohort_retention(self):
        print(f"{Colors.YELLOW}{Colors.BOLD}[2] ANALISIS MATRIKS RETENSI KOHOR (WEEKLY COHORTS){Colors.RESET}")
        print("Menganalisis retensi kohor pengguna baru selama 4 minggu berurutan:\n")

        weeks = ["Week 0", "Week 1", "Week 2", "Week 3", "Week 4"]
        cohorts = [
            {"cohort": "Cohort 1 (W1)", "size": 1200, "rates": [1.00, 0.45, 0.32, 0.28, 0.25]},
            {"cohort": "Cohort 2 (W2)", "size": 1450, "rates": [1.00, 0.48, 0.36, 0.31, None]},
            {"cohort": "Cohort 3 (W3)", "size": 1600, "rates": [1.00, 0.52, 0.40, None, None]},
            {"cohort": "Cohort 4 (W4)", "size": 1800, "rates": [1.00, 0.55, None, None, None]},
        ]

        # Table header
        header_str = f"{'Cohort':<16} | {'Size':<6} | " + " | ".join([f"{w:<8}" for w in weeks])
        print(f"{Colors.BOLD}{header_str}{Colors.RESET}")
        print("-" * len(header_str))

        for c in cohorts:
            row_vals = []
            for r in c["rates"]:
                if r is None:
                    row_vals.append(f"{Colors.DIM}{'-':<8}{Colors.RESET}")
                else:
                    pct = r * 100
                    # Heatmap coloring based on retention level
                    if pct >= 50:
                        color = Colors.GREEN
                    elif pct >= 30:
                        color = Colors.CYAN
                    elif pct >= 20:
                        color = Colors.YELLOW
                    else:
                        color = Colors.RED
                    row_vals.append(f"{color}{pct:5.1f}%  {Colors.RESET}")
            print(f"{c['cohort']:<16} | {c['size']:<6} | " + " | ".join(row_vals))

        print(f"\n{Colors.GREEN}Evaluasi Tren Retensi:{Colors.RESET}")
        print(f"• Retensi Week 1 meningkat dari {Colors.BOLD}45.0% -> 55.0%{Colors.RESET} dari Cohort 1 ke Cohort 4.")
        print(f"• Menunjukkan indikasi kuat bahwa iterasi UX onboarding terbaru berhasil menahan drop-off awal.\n")

    # -------------------------------------------------------------
    # 3. Continuous A/B Testing & Hypothesis Validation Engine
    # -------------------------------------------------------------
    def run_ab_test_simulation(self, n_control: int = 5000, n_variant: int = 5000,
                               conv_control_true: float = 0.052,
                               conv_variant_true: float = 0.063):
        print(f"{Colors.YELLOW}{Colors.BOLD}[3] SIMULASI CONTINUOUS A/B EXPERIMENTATION ENGINE{Colors.RESET}")
        print(f"Hipotesis Desain: 'Redesain CTA Checkout satu kolom meningkatkan conversion rate minimal +15% relatif.'\n")

        # Simulate observed conversions with binomial trials
        conv_c = sum(1 for _ in range(n_control) if random.random() < conv_control_true)
        conv_v = sum(1 for _ in range(n_variant) if random.random() < conv_variant_true)

        p_c = conv_c / n_control
        p_v = conv_v / n_variant
        relative_lift = ((p_v - p_c) / p_c) * 100

        # Pooled sample standard error for two proportion z-test
        p_pool = (conv_c + conv_v) / (n_control + n_variant)
        se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / n_control + 1 / n_variant))

        z_score = (p_v - p_c) / se_pool if se_pool > 0 else 0.0

        # Two-tailed p-value approximation using complementary error function
        p_value = math.erfc(abs(z_score) / math.sqrt(2.0))

        # 95% Confidence Interval for difference (p_v - p_c)
        se_diff = math.sqrt((p_c * (1 - p_c) / n_control) + (p_v * (1 - p_v) / n_variant))
        ci_lower = ((p_v - p_c) - 1.96 * se_diff) * 100
        ci_upper = ((p_v - p_c) + 1.96 * se_diff) * 100

        print(f"{'Metrik Uji':<28} | {'Control (Default)':<18} | {'Variant (Redesign)':<18}")
        print("-" * 70)
        print(f"{'Sample Size (Traffic)':<28} | {n_control:<18} | {n_variant:<18}")
        print(f"{'Conversions (Success)':<28} | {conv_c:<18} | {conv_v:<18}")
        print(f"{'Conversion Rate (CR)':<28} | {p_c * 100:6.2f}%            | {p_v * 100:6.2f}%")
        print("-" * 70)
        print(f"• Relative Lift (Peningkatan) : {Colors.BOLD}{Colors.GREEN if relative_lift > 0 else Colors.RED}{relative_lift:+.2f}%{Colors.RESET}")
        print(f"• Z-Score Statistik            : {z_score:+.4f}")
        print(f"• P-Value Dua Arah             : {p_value:.5f}")
        print(f"• 95% Confidence Interval Diff : [{ci_lower:+.2f}%, {ci_upper:+.2f}%]")

        alpha = 0.05
        is_significant = p_value < alpha

        print("\n" + "=" * 50)
        print(f"{Colors.BOLD}KEPUTUSAN EXPERIMENTATION BOARD:{Colors.RESET}")
        if is_significant and relative_lift > 0:
            print(f"{Colors.GREEN}{Colors.BOLD}✓ STATISTICALLY SIGNIFICANT WINNER (p < {alpha}){Colors.RESET}")
            print(f"Keputusan: {Colors.GREEN}ROLLOUT 100% VARIANT KE PRODUKSI.{Colors.RESET}")
            print(f"Dampak: Memvalidasi hipotesis desain dan mendongkrak North Star Metric.")
        elif is_significant and relative_lift < 0:
            print(f"{Colors.RED}{Colors.BOLD}✗ STATISTICALLY SIGNIFICANT REGRESSION (p < {alpha}){Colors.RESET}")
            print(f"Keputusan: {Colors.RED}SEGERA ROLLBACK KE CONTROL.{Colors.RESET}")
            print(f"Dampak: Variant menyebabkan degradasi metrik konversi pengguna.")
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠ INCONCLUSIVE (P-Value {p_value:.4f} >= {alpha}){Colors.RESET}")
            print(f"Keputusan: Perpanjang durasi eksperimen atau kumpulkan sample size lebih besar.")
        print("=" * 50 + "\n")

    # -------------------------------------------------------------
    # 4. Sample Size & Duration Calculator (Pre-experiment planning)
    # -------------------------------------------------------------
    def calculate_sample_size_requirement(self, baseline_cr: float = 0.05, mde: float = 0.15):
        print(f"{Colors.YELLOW}{Colors.BOLD}[4] KALKULATOR MINIMUM DETECTABLE EFFECT (MDE) & SAMPLE SIZE{Colors.RESET}")
        print(f"Menghitung kebutuhan ukuran sampel sebelum meluncurkan eksperimen A/B...")

        # Standard parameters: alpha=0.05 (Z_alpha/2 = 1.96), power=80% (Z_beta = 0.84)
        z_alpha = 1.96
        z_beta = 0.84
        p1 = baseline_cr
        p2 = baseline_cr * (1 + mde)
        p_avg = (p1 + p2) / 2

        # Evan Miller's formula for sample size per variation
        n_per_variant = int(((z_alpha * math.sqrt(2 * p_avg * (1 - p_avg)) +
                              z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / ((p2 - p1) ** 2))

        daily_traffic = 1500
        days_needed = math.ceil((n_per_variant * 2) / daily_traffic)

        print(f"• Baseline Conversion Rate : {p1 * 100:.1f}%")
        print(f"• Minimum Detectable Effect : {mde * 100:.1f}% (Target Variant CR: {p2 * 100:.2f}%)")
        print(f"• Target Statistical Power : 80% (β = 0.20), Significance Level α = 0.05")
        print(f"• Required Sample Size/Arm : {Colors.BOLD}{Colors.CYAN}{n_per_variant:,} pengguna{Colors.RESET}")
        print(f"• Total Sample Diperlukan  : {Colors.BOLD}{n_per_variant * 2:,} pengguna{Colors.RESET}")
        print(f"• Estimasi Waktu Running   : {Colors.BOLD}{Colors.GREEN}{days_needed} hari{Colors.RESET} (Asumsi {daily_traffic} pengunjung/hari)\n")

    def run_full_suite(self):
        self.simulate_aarrr_funnel()
        self.simulate_cohort_retention()
        self.calculate_sample_size_requirement()
        self.run_ab_test_simulation()

        print(f"{Colors.GREEN}{Colors.BOLD}✓ Seluruh simulasi analitik produk dan eksperimentasi berhasil dieksekusi.{Colors.RESET}")


def interactive_menu():
    lab = ProductAnalyticsLab()
    while True:
        print(f"{Colors.BOLD}PILIH MENU SIMULASI INTERAKTIF:{Colors.RESET}")
        print("1. Jalankan Simulasi Funnel AARRR (Pirate Metrics)")
        print("2. Tampilkan Matriks Retensi Kohor (Cohort Matrix)")
        print("3. Hitung Kebutuhan Ukuran Sampel Uji A/B (Power Analysis)")
        print("4. Eksekusi Simulasi Uji A/B dengan Pengujian Hipotesis Z-Test")
        print("5. Jalankan Seluruh Skenario (End-to-End Simulation)")
        print("0. Keluar dari Lab")

        try:
            choice = input(f"\n{Colors.CYAN}Masukkan pilihan [0-5]: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        print()
        if choice == "1":
            lab.simulate_aarrr_funnel()
        elif choice == "2":
            lab.simulate_cohort_retention()
        elif choice == "3":
            lab.calculate_sample_size_requirement()
        elif choice == "4":
            lab.run_ab_test_simulation()
        elif choice == "5":
            lab.run_full_suite()
        elif choice == "0":
            print(f"{Colors.GREEN}Terima kasih telah menggunakan Lab Product Metrics!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan pilih 0-5.{Colors.RESET}\n")

if __name__ == "__main__":
    # If piped, non-interactive terminal, or argument provided, run automated full suite
    if len(sys.argv) > 1 or not sys.stdin.isatty():
        lab = ProductAnalyticsLab()
        lab.run_full_suite()
    else:
        interactive_menu()
