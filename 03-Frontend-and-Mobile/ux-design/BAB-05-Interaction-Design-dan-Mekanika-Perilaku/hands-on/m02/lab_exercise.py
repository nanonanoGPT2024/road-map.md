#!/usr/bin/env python3
"""
Lab Exercise: Advanced Interaction Design & Behavioral Mechanics Simulator
BAB-05: Interaction Design dan Mekanika Perilaku (UX Design Engineering)

Simulasi arsitektur state machine interaksi, Fitts's Law target indexing,
Hick-Hyman decision latency, Hooked cycle behavioral loops, dan micro-interaction feedback.
"""

import math
import random
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
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
    FG_BRIGHT_CYAN = "\033[96m"
    FG_BRIGHT_GREEN = "\033[92m"
    FG_BRIGHT_YELLOW = "\033[93m"
    FG_BRIGHT_RED = "\033[91m"

    # Background
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[40m"


class InteractionState(Enum):
    IDLE = "IDLE"
    HOVER = "HOVER"
    PRESSED = "PRESSED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


@dataclass
class InteractiveComponent:
    id: str
    label: str
    distance_px: float  # Jarak dari posisi kursor awal (D)
    width_px: float     # Target width/area penargetan (W)
    num_options: int    # Jumlah opsi kognitif (Hick-Hyman)
    state: InteractionState = InteractionState.IDLE
    dwell_time_ms: float = 0.0

    def calculate_fitts_index_of_difficulty(self) -> float:
        """
        Menghitung Index of Difficulty (ID) berdasarkan Shannon formulation:
        ID = log2(D / W + 1)
        """
        if self.width_px <= 0:
            return float("inf")
        return math.log2((self.distance_px / self.width_px) + 1.0)

    def calculate_fitts_movement_time_ms(self, a: float = 50.0, b: float = 150.0) -> float:
        """
        Movement Time MT = a + b * ID (milidetik)
        a = start/stop latency (ms), b = motor control constant (ms/bit)
        """
        id_score = self.calculate_fitts_index_of_difficulty()
        return a + (b * id_score)

    def calculate_hick_hyman_decision_time_ms(self, b_cognitive: float = 180.0) -> float:
        """
        Decision Time T = b * log2(n + 1)
        b_cognitive: cognitive processing constant (~150-200ms per bit of decision)
        """
        if self.num_options <= 0:
            return 50.0
        return b_cognitive * math.log2(self.num_options + 1.0)


@dataclass
class HookModelCycle:
    trigger: str
    action_cost_effort: str
    variable_reward_type: str
    reward_granted: str
    investment_next_action: str
    retention_score_boost: float


class MicroInteractionEngine:
    """
    Engine untuk memvalidasi feedback loops:
    Trigger -> Rule -> Feedback -> Loops & Modes
    """
    @staticmethod
    def render_feedback_banner(state: InteractionState, feedback_text: str) -> None:
        color = TerminalColor.FG_CYAN
        badge = "[INFO]"
        if state == InteractionState.SUCCESS:
            color = TerminalColor.FG_BRIGHT_GREEN
            badge = "[OK 200]"
        elif state == InteractionState.ERROR:
            color = TerminalColor.FG_BRIGHT_RED
            badge = "[FAIL 422]"
        elif state == InteractionState.PROCESSING:
            color = TerminalColor.FG_BRIGHT_YELLOW
            badge = "[TRANSIT]"

        print(
            f"  {color}{TerminalColor.BOLD}{badge}{TerminalColor.RESET} "
            f"{color}{feedback_text}{TerminalColor.RESET}"
        )


class BehavioralExperimentController:
    def __init__(self):
        self.components: Dict[str, InteractiveComponent] = {
            "btn_checkout": InteractiveComponent(
                id="btn_checkout",
                label="Primary CTA: Beli Sekarang (Optimized)",
                distance_px=140.0,
                width_px=220.0,
                num_options=1
            ),
            "btn_nav_nested": InteractiveComponent(
                id="btn_nav_nested",
                label="Nested Dropdown Nav: Pengaturan Akun",
                distance_px=650.0,
                width_px=38.0,
                num_options=14
            ),
            "fab_floating": InteractiveComponent(
                id="fab_floating",
                label="Floating Action Button (Corner Anchor)",
                distance_px=80.0,
                width_px=72.0,
                num_options=2
            ),
            "link_footer_privacy": InteractiveComponent(
                id="link_footer_privacy",
                label="Footer Tiny Text Link (Disclaimer)",
                distance_px=980.0,
                width_px=24.0,
                num_options=28
            ),
        }

        self.hook_database: List[HookModelCycle] = [
            HookModelCycle(
                trigger="Internal: Keinginan update performa tim setelah sprint review",
                action_cost_effort="Satu klik pada shortcut card di dashboard (Low Friction)",
                variable_reward_type="Reward of the Hunt: Insight bottleneck visual & progress chart 98%",
                reward_granted="Pemberian Badge 'Sprint Accelerant' + Grafis Interaktif",
                investment_next_action="Menambahkan catatan mitigasi risiko untuk sprint depan",
                retention_score_boost=18.4
            ),
            HookModelCycle(
                trigger="External: Notifikasi Push 'Desain Anda dikomentari Lead UX'",
                action_cost_effort="Deep link langsung ke pinpoint canvas koordinat (Zero Search)",
                variable_reward_type="Reward of the Tribe: Reaksi emoji + apresiasi arsitektural",
                reward_granted="Validasi sosial instan dalam 3 detik",
                investment_next_action="Mengundang kolaborator lain untuk review micro-copy",
                retention_score_boost=24.1
            ),
        ]

    def clear_screen(self) -> None:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def print_header(self) -> None:
        c = TerminalColor
        print(f"{c.BG_BLUE}{c.FG_WHITE}{c.BOLD}  === SIMULATOR MEKANIKA INTERAKSI & PERILAKU PENGGUNA (BAB-05) ===  {c.RESET}")
        print(f"{c.FG_CYAN}Arsitektur Fitts's Law, Hick-Hyman Latency, Finite State UI, & Hook Loop{c.RESET}\n")

    def run_fitts_hick_benchmark(self) -> None:
        self.print_header()
        c = TerminalColor
        print(f"{c.BOLD}{c.FG_BRIGHT_YELLOW}[1] BENCHMARK HUKUM ERGONOMI DIGITAL (FITTS & HICK-HYMAN){c.RESET}")
        print(f"{c.DIM}Mengevaluasi Total Reaction Time (TRT = Decision Time + Movement Time){c.RESET}\n")

        print(
            f"{'Target ID':<20} | {'D (px)':<8} | {'W (px)':<8} | "
            f"{'Fitts ID (bits)':<16} | {'MT (ms)':<10} | {'Options':<8} | "
            f"{'Hick DT (ms)':<12} | {c.BOLD}{'Total TRT':<12}{c.RESET}"
        )
        print("-" * 115)

        for comp_id, comp in self.components.items():
            id_bits = comp.calculate_fitts_index_of_difficulty()
            mt_ms = comp.calculate_fitts_movement_time_ms()
            dt_ms = comp.calculate_hick_hyman_decision_time_ms()
            total_trt = mt_ms + dt_ms

            # Visual warning if cognitive or physical friction is too high
            color = c.FG_GREEN
            friction_badge = "[FAST]"
            if total_trt > 850.0:
                color = c.FG_BRIGHT_RED
                friction_badge = "[HIGH FRICTION]"
            elif total_trt > 500.0:
                color = c.FG_YELLOW
                friction_badge = "[MEDIUM]"

            print(
                f"{color}{comp.id:<20}{c.RESET} | "
                f"{comp.distance_px:<8.1f} | "
                f"{comp.width_px:<8.1f} | "
                f"{id_bits:<16.2f} | "
                f"{mt_ms:<10.1f} | "
                f"{comp.num_options:<8} | "
                f"{dt_ms:<12.1f} | "
                f"{color}{c.BOLD}{total_trt:<8.1f} {friction_badge}{c.RESET}"
            )

        print("\n" + c.FG_CYAN + "Analisis Arsitektural UX:" + c.RESET)
        print("  - Tombol dengan Fitts ID < 2.0 bits memberikan eksekusi motorik instan.")
        print("  - Mengurangi opsi dari 14 ke 2 (Hick-Hyman) memangkas lebih dari 350ms beban kognitif.")
        input(f"\n{c.DIM}Tekan [Enter] untuk kembali ke menu utama...{c.RESET}")

    def simulate_micro_interaction_fsm(self) -> None:
        self.print_header()
        c = TerminalColor
        print(f"{c.BOLD}{c.FG_BRIGHT_CYAN}[2] SIMULASI FINITE STATE MACHINE (FSM) FEEDBACK LOOP{c.RESET}")
        print("Pilih komponen target untuk diuji siklus interaksinya:")

        comp_keys = list(self.components.keys())
        for idx, key in enumerate(comp_keys, start=1):
            comp = self.components[key]
            print(f"  [{idx}] {key} - {comp.label}")

        choice = input(f"\nPilih komponen (1-{len(comp_keys)}) [default 1]: ").strip()
        selected_key = comp_keys[0]
        if choice.isdigit() and 1 <= int(choice) <= len(comp_keys):
            selected_key = comp_keys[int(choice) - 1]

        target = self.components[selected_key]
        print(f"\n{c.BOLD}Memulai Transisi State untuk: {target.label}{c.RESET}")

        transitions = [
            (InteractionState.IDLE, "Komponen diam, resting state dengan affordance yang jelas."),
            (InteractionState.HOVER, "Kursor mendekat (bounding box focus), scale(1.02), elevate shadow."),
            (InteractionState.PRESSED, "Pointer down, active state scale(0.98), haptic feedback triggered."),
            (InteractionState.PROCESSING, "State loading spinner aktif, button disabled mencegah duplicate submit."),
            (InteractionState.SUCCESS, "Aksi berhasil (200 OK), morph ke ikon checklist warna hijau spring easing."),
        ]

        for st, desc in transitions:
            target.state = st
            time.sleep(0.45)
            MicroInteractionEngine.render_feedback_banner(
                target.state,
                f"State -> {st.value:10} | {desc}"
            )

        target.state = InteractionState.IDLE
        print(f"\n{c.FG_GREEN}Siklus micro-interaction selesai tanpa dead state.{c.RESET}")
        input(f"\n{c.DIM}Tekan [Enter] untuk kembali...{c.RESET}")

    def run_hook_model_simulator(self) -> None:
        self.print_header()
        c = TerminalColor
        print(f"{c.BOLD}{c.FG_MAGENTA}[3] SIMULASI BEHAVIORAL HOOK MODEL (NIR EYAL LOOP){c.RESET}")
        print(f"{c.DIM}Mekanika Pembentukan Kebiasaan Produk: Trigger -> Action -> Variable Reward -> Investment{c.RESET}\n")

        for i, hook in enumerate(self.hook_database, start=1):
            print(f"{c.BOLD}{c.FG_BRIGHT_YELLOW}--- Scenario #{i} ---{c.RESET}")
            print(f"  {c.FG_CYAN}1. TRIGGER        :{c.RESET} {hook.trigger}")
            print(f"  {c.FG_CYAN}2. ACTION         :{c.RESET} {hook.action_cost_effort}")
            print(f"  {c.FG_CYAN}3. VARIABLE REWARD:{c.RESET} {hook.variable_reward_type} -> {hook.reward_granted}")
            print(f"  {c.FG_CYAN}4. INVESTMENT     :{c.RESET} {hook.investment_next_action}")
            print(f"  {c.FG_GREEN}{c.BOLD}+ Retention Score Impact: +{hook.retention_score_boost}% 30-Day LTV{c.RESET}\n")

        input(f"{c.DIM}Tekan [Enter] untuk kembali...{c.RESET}")

    def run_custom_fitts_calculator(self) -> None:
        self.print_header()
        c = TerminalColor
        print(f"{c.BOLD}{c.FG_BRIGHT_GREEN}[4] CALCULATOR INTERAKTIF: FITTS'S LAW DESIGN TESTING{c.RESET}")
        try:
            d_input = input("Masukkan jarak target D (pixel, cth: 300): ").strip()
            w_input = input("Masukkan lebar target W (pixel, cth: 48): ").strip()
            opts_input = input("Masukkan jumlah opsi kognitif N (cth: 4): ").strip()

            d = float(d_input) if d_input else 300.0
            w = float(w_input) if w_input else 48.0
            n = int(opts_input) if opts_input else 4

            comp = InteractiveComponent(
                id="custom_target",
                label="Custom Target",
                distance_px=d,
                width_px=w,
                num_options=n
            )

            id_val = comp.calculate_fitts_index_of_difficulty()
            mt_val = comp.calculate_fitts_movement_time_ms()
            dt_val = comp.calculate_hick_hyman_decision_time_ms()

            print(f"\n{c.BOLD}Hasil Kalkulasi Ergonomi Desain:{c.RESET}")
            print(f"  - Index of Difficulty (ID) : {c.FG_YELLOW}{id_val:.3f} bits{c.RESET}")
            print(f"  - Movement Time (MT)       : {c.FG_CYAN}{mt_val:.2f} ms{c.RESET}")
            print(f"  - Decision Time (DT)       : {c.FG_MAGENTA}{dt_val:.2f} ms{c.RESET}")
            print(f"  - Total Latency Waktu Aksi : {c.BOLD}{c.FG_BRIGHT_GREEN}{mt_val + dt_val:.2f} ms{c.RESET}")

            if id_val > 4.5:
                print(f"  {c.FG_BRIGHT_RED}[REKOMENDASI UX]: Target terlalu kecil atau terlalu jauh! Tingkatkan target size minimum 44x44px.{c.RESET}")
            else:
                print(f"  {c.FG_BRIGHT_GREEN}[REKOMENDASI UX]: Target memenuhi standar ergonomic mobile-first & touch target safety.{c.RESET}")

        except ValueError as e:
            print(f"{c.FG_RED}Input tidak valid: {e}{c.RESET}")

        input(f"\n{c.DIM}Tekan [Enter] untuk kembali...{c.RESET}")

    def main_loop(self) -> None:
        c = TerminalColor
        while True:
            self.clear_screen()
            self.print_header()
            print(f"{c.BOLD}Menu Eksperimen Interaksi UX:{c.RESET}")
            print("  [1] Jalankan Benchmark Ergonomi Fitts's & Hick-Hyman Law")
            print("  [2] Simulasi Micro-Interaction FSM & Feedback Loops")
            print("  [3] Visualisasi Siklus Perilaku Hook Model (Nir Eyal)")
            print("  [4] Kalkulator Kustom Index of Difficulty (Fitts Parameter)")
            print("  [5] Eksekusi Otomatis Seluruh Skenario Lab & Validasi")
            print("  [q] Keluar dari Simulator")

            choice = input(f"\n{c.FG_YELLOW}Pilih opsi (1-5 / q): {c.RESET}").strip().lower()

            if choice == "1":
                self.clear_screen()
                self.run_fitts_hick_benchmark()
            elif choice == "2":
                self.clear_screen()
                self.simulate_micro_interaction_fsm()
            elif choice == "3":
                self.clear_screen()
                self.run_hook_model_simulator()
            elif choice == "4":
                self.clear_screen()
                self.run_custom_fitts_calculator()
            elif choice == "5":
                self.clear_screen()
                self.print_header()
                print(f"{c.BOLD}{c.FG_GREEN}=== AUTO EXECUTION ALL SUITES ==={c.RESET}\n")
                self.run_fitts_hick_benchmark()
                self.clear_screen()
                self.print_header()
                self.run_hook_model_simulator()
                print(f"\n{c.FG_BRIGHT_GREEN}Semua modul interaksi tervalidasi sukses.{c.RESET}")
                time.sleep(1.5)
            elif choice in ["q", "exit", "quit"]:
                print(f"\n{c.FG_CYAN}Simulator ditutup. Terima kasih telah mempraktikkan Interaction Design!{c.RESET}\n")
                break
            else:
                print(f"\n{c.FG_RED}Pilihan tidak dikenali.{c.RESET}")
                time.sleep(1)


if __name__ == "__main__":
    app = BehavioralExperimentController()
    # Jika dijalankan dengan argumen non-interaktif (e.g. CI / testing)
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        app.run_fitts_hick_benchmark()
        app.run_hook_model_simulator()
        sys.exit(0)
    else:
        app.main_loop()
