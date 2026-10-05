#!/usr/bin/env python3
"""
Growth UX & Product Analytics Optimization Engine
BAB 10: Growth UX, Product Analytics, dan Post-Launch Optimization
Hands-on Lab Exercise (Module 02)

Simulator arsitektur telemetry analitik produk, A/B Testing Bayesian/Frequentist,
analisis corong konversi (AARRR), retensi kohort, serta automated guardrail alerting.
"""

import sys
import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

# ==============================================================================
# Terminal ANSI Color Palette
# ==============================================================================
class Colors:
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
    BG_DARK = "\033[40m"
    BG_CYAN = "\033[46m"
    BG_RED = "\033[41m"

def print_banner():
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("=" * 76)
    print("   🚀 GROWTH UX ENGINE & POST-LAUNCH EXPERIMENTATION SUITE (PROD-SIM)")
    print("   Enterprise Product Analytics & Automated Statistical Decision System")
    print("=" * 76 + f"{Colors.RESET}\n")

# ==============================================================================
# Model Domain & Data Structures
# ==============================================================================
@dataclass
class ABVariant:
    name: str
    traffic_weight: float
    visitors: int = 0
    conversions: int = 0
    total_dropoffs: int = 0
    load_times_ms: List[float] = field(default_factory=list)

    @property
    def conversion_rate(self) -> float:
        return (self.conversions / self.visitors) if self.visitors > 0 else 0.0

    @property
    def avg_load_time(self) -> float:
        return (sum(self.load_times_ms) / len(self.load_times_ms)) if self.load_times_ms else 0.0

@dataclass
class FunnelStage:
    name: str
    stage_key: str
    expected_benchmark: float  # Conversion baseline (0.0 - 1.0)
    user_count: int = 0

# ==============================================================================
# Statistical Engine: Two-Sample Proportion Z-Test & SRM Detection
# ==============================================================================
class ExperimentEngine:
    """Mesin kalkulasi statistik inferensial untuk pengujian hipotesis UX."""

    @staticmethod
    def calculate_srm(control_n: int, variant_n: int, expected_ratio: float = 0.5) -> Tuple[float, bool]:
        """Sample Ratio Mismatch (SRM) Chi-Square Test (1 DOF)."""
        total = control_n + variant_n
        if total == 0:
            return 0.0, False
        expected_control = total * expected_ratio
        expected_variant = total * (1.0 - expected_ratio)
        chi2 = ((control_n - expected_control) ** 2 / expected_control) + \
               ((variant_n - expected_variant) ** 2 / expected_variant)
        # Threshold p-value < 0.001 is Chi2 > 10.828
        has_srm = chi2 > 10.828
        return chi2, has_srm

    @staticmethod
    def two_proportion_z_test(c_n: int, c_c: int, v_n: int, v_c: int) -> Tuple[float, float, float]:
        """
        Menghitung Z-score, Two-tailed p-value, dan Relative Uplift.
        """
        if c_n == 0 or v_n == 0:
            return 0.0, 1.0, 0.0
        
        p_c = c_c / c_n
        p_v = v_c / v_n
        
        if p_c == 0:
            return 0.0, 1.0, 0.0
            
        uplift = ((p_v - p_c) / p_c) * 100.0
        
        # Pooled sample proportion
        p_pool = (c_c + v_c) / (c_n + v_n)
        se_pool = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / c_n + 1.0 / v_n))
        
        if se_pool == 0:
            return 0.0, 1.0, uplift
            
        z_score = (p_v - p_c) / se_pool
        
        # Aproksimasi complementary error function untuk p-value
        p_value = math.erfc(abs(z_score) / math.sqrt(2.0))
        return z_score, p_value, uplift

# ==============================================================================
# Growth UX & Funnel Telemetry Simulator
# ==============================================================================
class GrowthUXSimulator:
    def __init__(self):
        self.control = ABVariant(name="Control (Checkout v1: Standard Multi-step)", traffic_weight=0.5)
        self.variant = ABVariant(name="Variant B (Checkout v2: 1-Click Accordion UX)", traffic_weight=0.5)
        
        self.funnel_stages: List[FunnelStage] = [
            FunnelStage("1. Acquisition (Landing / Catalog)", "acquisition", 1.0),
            FunnelStage("2. Activation (Added to Cart)", "activation", 0.52),
            FunnelStage("3. Conversion (Started Checkout)", "checkout_start", 0.35),
            FunnelStage("4. Retention Intent (Created Account)", "account_created", 0.22),
            FunnelStage("5. Revenue (Payment Success)", "payment_success", 0.14),
        ]

    def simulate_telemetry_stream(self, sample_size: int = 1500, chaos_latency: bool = False):
        """Menjalankan simulasi event stream real-time dengan variasi UX friction."""
        print(f"{Colors.YELLOW}⚡ Menjalankan simulasi {sample_size} sesi pengguna dengan model probabilistik UX...{Colors.RESET}")
        
        # Karakteristik UX: Variant B mengoptimalkan friction pada checkout_start -> payment
        for _ in range(sample_size):
            assigned_group = self.control if random.random() < 0.5 else self.variant
            assigned_group.visitors += 1
            
            # Simulasi latensi render UI (ms)
            base_latency = random.gauss(650, 80) if assigned_group == self.variant else random.gauss(1150, 150)
            if chaos_latency and random.random() < 0.05:
                base_latency += 2400.0  # Spike degradasi jaringan
            assigned_group.load_times_ms.append(base_latency)

            # Probabilitas konversi dipengaruhi friction flow
            # Baseline checkout friction: Control = 14% konversi, Variant B = 19.5% konversi
            base_p = 0.14 if assigned_group == self.control else 0.195
            
            # Dampak penalti performa (load time > 1500ms menurunkan konversi UX)
            if base_latency > 1500:
                base_p *= 0.65

            if random.random() < base_p:
                assigned_group.conversions += 1
            else:
                assigned_group.total_dropoffs += 1

        print(f"{Colors.GREEN}✔ Sesi simulasi selesai diproses ke dalam telemetry pipeline.{Colors.RESET}\n")

    def render_ab_results(self):
        """Menampilkan laporan statistik eksperimen A/B testing."""
        engine = ExperimentEngine()
        z, p_val, uplift = engine.two_proportion_z_test(
            self.control.visitors, self.control.conversions,
            self.variant.visitors, self.variant.conversions
        )
        chi2, srm_detected = engine.calculate_srm(self.control.visitors, self.variant.visitors)

        print(f"{Colors.BOLD}{Colors.MAGENTA}--- HASIL STATISTIK A/B EXPERIMENTATION ---{Colors.RESET}")
        print(f"{'Metrik':<32} | {'Control (A)':<18} | {'Variant (B)':<18}")
        print("-" * 74)
        print(f"{'Ukuran Sampel (Visitors)':<32} | {self.control.visitors:<18} | {self.variant.visitors:<18}")
        print(f"{'Konversi Pembayaran':<32} | {self.control.conversions:<18} | {self.variant.conversions:<18}")
        print(f"{'Conversion Rate (CR)':<32} | {self.control.conversion_rate*100:>6.2f}%{' ':>11} | {self.variant.conversion_rate*100:>6.2f}%{' ':>11}")
        print(f"{'Avg UX Latency':<32} | {self.control.avg_load_time:>6.1f} ms{' ':>9} | {self.variant.avg_load_time:>6.1f} ms{' ':>9}")
        print("-" * 74)

        # Diagnosa SRM (Sample Ratio Mismatch)
        srm_color = Colors.RED if srm_detected else Colors.GREEN
        srm_status = "CRITICAL BIAS: SRM TERDETEKSI!" if srm_detected else "NORMAL (SRM Free, Chi² < 10.8)"
        print(f"Sample Ratio Mismatch Check : {srm_color}{srm_status} (Chi² = {chi2:.3f}){Colors.RESET}")

        # Signifikansi Statistik
        stat_sig = p_val < 0.05
        sig_color = Colors.GREEN if stat_sig else Colors.YELLOW
        print(f"Observed Relative Uplift    : {Colors.BOLD}{uplift:+.2f}%{Colors.RESET}")
        print(f"Z-Score                     : {z:.4f}")
        print(f"p-value                     : {sig_color}{p_val:.5f}{Colors.RESET} (Alpha threshold = 0.05)")

        # Keputusan Rekomendasi UX
        print("\n" + f"{Colors.BOLD}[DECISION ENGINE RECOMMENDATION]{Colors.RESET}")
        if srm_detected:
            print(f"{Colors.BG_RED}{Colors.WHITE} [STOP ROLLOUT] {Colors.RESET} Jangan lakukan deploy! Ditemukan SRM pada alokasi bucket.")
        elif stat_sig and uplift > 0:
            print(f"{Colors.BG_CYAN}{Colors.WHITE} [WINNER: ROLLOUT 100%] {Colors.RESET} {Colors.GREEN}Variant B membuktikan keunggulan UX signifikan secara statistik.{Colors.RESET}")
        elif stat_sig and uplift < 0:
            print(f"{Colors.BG_RED}{Colors.WHITE} [ROLLBACK] {Colors.RESET} Variant B menurunkan metrik kunci secara signifikan. Pertahankan Control.")
        else:
            print(f"{Colors.YELLOW} [INCONCLUSIVE] {Colors.RESET} Belum mencapai statistical power yang memadai. Tambah sampel durasi eksperimen.")
        print()

    def render_funnel_waterfall(self):
        """Visualisasi waterfall corong AARRR dengan highlighting friction drop-off."""
        print(f"{Colors.BOLD}{Colors.CYAN}--- ANALISIS CORONG KONVERSI UX (AARRR FUNNEL) ---{Colors.RESET}")
        total_entrants = max(self.control.visitors + self.variant.visitors, 1000)
        
        current_users = total_entrants
        for idx, stage in enumerate(self.funnel_stages):
            if idx == 0:
                stage.user_count = total_entrants
            else:
                drop_rate = random.uniform(0.72, 0.88)
                stage.user_count = int(current_users * drop_rate)
            
            pct_of_top = (stage.user_count / total_entrants) * 100.0
            step_conversion = (stage.user_count / current_users * 100.0) if current_users > 0 else 0.0
            dropoff_users = current_users - stage.user_count if idx > 0 else 0
            
            bar_len = int(pct_of_top / 3.0)
            bar_graph = f"{Colors.BLUE}{'█' * bar_len}{Colors.RESET}{' ' * (34 - bar_len)}"
            
            print(f"{stage.name:<35} | {stage.user_count:>6} users | {bar_graph} | {pct_of_top:>5.1f}% Total")
            if idx > 0 and step_conversion < 75.0:
                print(f"  {Colors.RED}↳ [UX Friction Spike]: Kehilangan {dropoff_users} users (-{100.0 - step_conversion:.1f}% step drop){Colors.RESET}")
            current_users = stage.user_count
        print()

    def render_cohort_matrix(self):
        """Simulasi matriks retensi kohort pasca rilis (Day 0 - Day 30)."""
        print(f"{Colors.BOLD}{Colors.YELLOW}--- MATRIKS RETENSI KOHORT PASCA-PELUNCURAN (RETENTION DECAY) ---{Colors.RESET}")
        weeks = ["W-01 (Baseline)", "W-02 (Feature Push)", "W-03 (UX Micro-fix)", "W-04 (Current)"]
        print(f"{'Cohort Week':<22} | {'Users':<8} | {'D-0':<7} | {'D-1':<7} | {'D-7':<7} | {'D-14':<7} | {'D-30':<7}")
        print("-" * 74)

        decay_profiles = [
            (1200, [100.0, 42.1, 23.4, 15.2, 10.1]),
            (1450, [100.0, 44.8, 25.1, 16.8, 11.5]),
            (1600, [100.0, 52.3, 33.7, 24.1, 18.3]),  # UX Intervention boosted retention
            (1850, [100.0, 56.7, 38.2, 28.5, 22.0]),
        ]

        for idx, (label, (size, profile)) in enumerate(zip(weeks, decay_profiles)):
            formatted_vals = []
            for val in profile:
                color = Colors.GREEN if val >= 30.0 else (Colors.YELLOW if val >= 20.0 else Colors.DIM)
                formatted_vals.append(f"{color}{val:>5.1f}%{Colors.RESET}")
            print(f"{label:<22} | {size:<8} | {' | '.join(formatted_vals)}")
        print(f"\n{Colors.CYAN}💡 Insight: Retensi D-7 naik dari 23.4% ke 38.2% berkat perbaikan UX onboarding di W-03.{Colors.RESET}\n")

# ==============================================================================
# Interactive Terminal Controller
# ==============================================================================
def main():
    print_banner()
    sim = GrowthUXSimulator()
    
    # Inisialisasi awal telemetry baseline
    sim.simulate_telemetry_stream(sample_size=2000, chaos_latency=False)

    while True:
        print(f"{Colors.BOLD}PILIH MENU SIMULASI EKSPERIMEN & ANALITIK:{Colors.RESET}")
        print(f"  {Colors.CYAN}[1]{Colors.RESET} Jalankan Evaluasi Statistik A/B Testing & Keputusan Rollout")
        print(f"  {Colors.CYAN}[2]{Colors.RESET} Visualisasikan Analisis Corong Konversi (AARRR Funnel)")
        print(f"  {Colors.CYAN}[3]{Colors.RESET} Tampilkan Matriks Retensi Kohort (Post-Launch Retention)")
        print(f"  {Colors.CYAN}[4]{Colors.RESET} Injeksi Chaos Latency & Telusuri Anomali Guardrail Telemetry")
        print(f"  {Colors.CYAN}[5]{Colors.RESET} Reset & Jalankan Batch Baru (Custom Sample Size)")
        print(f"  {Colors.CYAN}[6]{Colors.RESET} Keluar (Exit)")

        try:
            choice = input(f"\n{Colors.BOLD}Masukkan pilihan [1-6]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Sesi dihentikan.{Colors.RESET}")
            break

        print()
        if choice == "1":
            sim.render_ab_results()
        elif choice == "2":
            sim.render_funnel_waterfall()
        elif choice == "3":
            sim.render_cohort_matrix()
        elif choice == "4":
            print(f"{Colors.RED}🔥 Menginjeksi degradasi latensi backend untuk menguji respon guardrail UX...{Colors.RESET}")
            sim.simulate_telemetry_stream(sample_size=1500, chaos_latency=True)
            sim.render_ab_results()
        elif choice == "5":
            try:
                n = int(input("Masukkan jumlah sampel pengunjung per varian [500 - 50000]: ").strip())
                sim = GrowthUXSimulator()
                sim.simulate_telemetry_stream(sample_size=n, chaos_latency=False)
                sim.render_ab_results()
            except ValueError:
                print(f"{Colors.RED}Nilai sampel harus berupa angka valid.{Colors.RESET}\n")
        elif choice == "6" or choice.lower() == "q":
            print(f"{Colors.GREEN}Selesai. Telemetry pipeline dinonaktifkan secara aman.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan pilih 1-6.{Colors.RESET}\n")

if __name__ == "__main__":
    main()
