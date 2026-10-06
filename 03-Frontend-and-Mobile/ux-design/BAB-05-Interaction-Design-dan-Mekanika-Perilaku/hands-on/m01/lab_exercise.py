#!/usr/bin/env python3
"""
Lab Exercise: BAB-05 - Interaction Design dan Mekanika Perilaku
Simulasi Komputasi & Diagnostik Interaktif:
1. Fitts's Law (Target Acquisition Time & Index of Difficulty)
2. Hick-Hyman Law (Decision Time & Cognitive Load Model)
3. Nir Eyal's Hook Model (Loop Perilaku: Trigger -> Action -> Variable Reward -> Investment)
4. Feedback Loop & Latency Tolerance Perception Thresholds
"""

import math
import sys
import time
from typing import Dict, List, Tuple

# ANSI Color Codes & Formatting
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_BLUE = "\033[44m\033[37m"
BG_GREEN = "\033[42m\033[30m"
BG_RED = "\033[41m\033[37m"


def print_banner() -> None:
    print(f"{CYAN}{BOLD}")
    print("================================================================================")
    print("   UX INTERACTION DESIGN & BEHAVIORAL MECHANICS SIMULATOR                      ")
    print("   BAB-05: Fondasi Matematis & Psikologis Interaksi Manusia-Sistem              ")
    print("================================================================================")
    print(f"{RESET}")


def calculate_fitts(distance: float, width: float, a: float = 0.05, b: float = 0.15) -> Tuple[float, float]:
    """
    Fitts's Law (MacKenzie / Shannon formulation):
    ID (Index of Difficulty) = log2(D / W + 1) bits
    MT (Movement Time) = a + b * ID seconds
    """
    if width <= 0 or distance <= 0:
        raise ValueError("Jarak (D) dan Lebar Target (W) harus lebih besar dari 0.")
    id_bits = math.log2((distance / width) + 1.0)
    mt_sec = a + (b * id_bits)
    return id_bits, mt_sec


def simulate_fitts_law() -> None:
    print(f"\n{BLUE}{BOLD}[MODUL 1] Simulasi Fitts's Law: Evaluasi Ergonomi & Fitts Acquisition{RESET}")
    print(f"{DIM}Rumus: MT = a + b * log2(D / W + 1) | MacKenzie Shannon Formulation{RESET}\n")

    scenarios = [
        {"name": "Floating Action Button (Desktop)", "D": 850.0, "W": 48.0},
        {"name": "Primary CTA Bottom Bar (Mobile thumb-zone)", "D": 120.0, "W": 360.0},
        {"name": "Corner Menu Trigger (Infinite Edge Screen)", "D": 600.0, "W": 120.0},
        {"name": "Tiny Inline Text Link (Footer Navigation)", "D": 900.0, "W": 14.0},
    ]

    print(f"{'No':<3} | {'Elemen UI / Skenario Target':<42} | {'D (px)':<7} | {'W (px)':<7} | {'ID (bits)':<9} | {'Est MT (ms)':<11}")
    print("-" * 92)

    for idx, sc in enumerate(scenarios, 1):
        id_bits, mt_sec = calculate_fitts(sc["D"], sc["W"])
        mt_ms = mt_sec * 1000.0
        color = GREEN if mt_ms < 400 else (YELLOW if mt_ms < 700 else RED)
        print(f"{idx:<3} | {sc['name']:<42} | {sc['D']:<7.0f} | {sc['W']:<7.0f} | {id_bits:<9.2f} | {color}{mt_ms:>8.1f} ms{RESET}")

    print(f"\n{YELLOW}{BOLD}Insight Interaksi:{RESET}")
    print(" - Memperbesar target (W) dan mendekatkan jarak (D) menurunkan Index of Difficulty (ID).")
    print(" - Elemen tepi layar (edge/corner) memiliki lebar efektif virtual tak hingga (infinite target width).")


def calculate_hick(n_options: int, b_coef: float = 0.155) -> float:
    """
    Hick-Hyman Law:
    RT = b * log2(n + 1)
    """
    if n_options < 1:
        raise ValueError("Jumlah pilihan opsi minimal 1.")
    return b_coef * math.log2(n_options + 1)


def simulate_hick_law() -> None:
    print(f"\n{MAGENTA}{BOLD}[MODUL 2] Simulasi Hick-Hyman Law: Cognitive Load & Decision Latency{RESET}")
    print(f"{DIM}Rumus: RT = b * log2(n + 1) | Beban kognitif pemilihan menu/opsi{RESET}\n")

    options_counts = [2, 4, 7, 12, 24, 48]
    print(f"{'Jumlah Opsi (n)':<16} | {'Entropy (bits)':<16} | {'Estimasi Reaction Time':<24} | {'Status UX'}")
    print("-" * 80)

    for n in options_counts:
        rt = calculate_hick(n)
        bits = math.log2(n + 1)
        if n <= 4:
            status = f"{GREEN}Ringan (Quick Scan){RESET}"
        elif n <= 7:
            status = f"{YELLOW}Miller's 7±2 Threshold{RESET}"
        else:
            status = f"{RED}Cognitive Friction / Decision Paralysis{RESET}"
        print(f"{n:<16} | {bits:<16.2f} | {rt * 1000:>8.1f} ms             | {status}")

    print(f"\n{YELLOW}{BOLD}Rekomendasi Arsitektur Informasi:{RESET}")
    print(" - Terapkan Progressive Disclosure untuk menu lebih dari 7 pilihan.")
    print(" - Kelompokkan (chunking) opsi serumpun guna mereduksi entropy keputusan.")


class HookModelEngine:
    def __init__(self, product_name: str):
        self.product = product_name
        self.retention_score = 0
        self.history: List[str] = []

    def execute_stage(self, stage: str, description: str, score_delta: int) -> None:
        self.retention_score += score_delta
        self.history.append(f"[{stage.upper()}] {description} (Δ: +{score_delta})")
        print(f"  {CYAN}▸ {stage.ljust(16)}:{RESET} {description} {GREEN}(Score: {self.retention_score}){RESET}")
        time.sleep(0.08)

    def run_simulation(self) -> None:
        print(f"\n{GREEN}{BOLD}[MODUL 3] Simulasi Hook Model (Nir Eyal): Siklus Pembentukan Habit{RESET}")
        print(f"Aplikasi Target: {BOLD}{self.product}{RESET}\n")

        print(f"{BOLD}--- Siklus 1: Onboarding & Immediate Payoff ---{RESET}")
        self.execute_stage("1. Trigger", "Eksternal: Notifikasi push 'Rekan Anda memberi kudos pada review Anda'", 15)
        self.execute_stage("2. Action", "Membuka notifikasi dalam 1 tap (Friction minimal)", 25)
        self.execute_stage("3. Reward", "Variable Reward: Variasi pesan feedback & lencana apresiasi tim", 30)
        self.execute_stage("4. Investment", "Pengguna menulis respon balik dan mengatur profil keahlian", 30)

        print(f"\n{BOLD}--- Siklus 2: Internalization of Habits ---{RESET}")
        self.execute_stage("1. Trigger", "Internal: Rasa penasaran & dorongan profesional (FOMO / Belonging)", 20)
        self.execute_stage("2. Action", "Membuka feed proyek sebelum sesi stand-up pagi", 25)
        self.execute_stage("3. Reward", "Reward of the Hunt: Insight baru yang relevan dengan tugas harian", 35)
        self.execute_stage("4. Investment", "Menyimpan 3 template kerja ke workspace pribadi (Data Lock-in)", 40)

        print(f"\n{BG_GREEN} Total Retention Capital: {self.retention_score} poin {RESET}")
        print(f"{DIM}Insight: Investasi data (kustomisasi, riwayat, kontak) memperkuat trigger internal.{RESET}\n")


def simulate_feedback_latency() -> None:
    print(f"\n{YELLOW}{BOLD}[MODUL 4] Benchmarking Toleransi Latensi Respons Interaksi (Nielsen / Miller Norm){RESET}")
    print(f"{DIM}Threshold persepsi kontrol pengguna terhadap umpan balik sistem:{RESET}\n")

    benchmarks = [
        {"threshold": "0.1 detik (100 ms)", "perception": "Instantaneous", "action_needed": "Umpan balik langsung (hover, button click, micro-animation)", "status": GREEN},
        {"threshold": "1.0 detik (1000 ms)", "perception": "Flow Limit", "action_needed": "Progress indicator ringan, user masih merasakan kontrol langsung", "status": YELLOW},
        {"threshold": "10.0 detik (10000 ms)", "perception": "Attention Loss", "action_needed": "Wajib asynchronous notification / multi-stage progress modal", "status": RED},
    ]

    for b in benchmarks:
        print(f"{b['status']}{BOLD}● {b['threshold']}{RESET}")
        print(f"  Persepsi Kognitif: {b['perception']}")
        print(f"  Desain Interaksi : {b['action_needed']}\n")


def run_interactive_audit() -> None:
    print(f"\n{CYAN}{BOLD}[MODUL 5] Evaluator Interaktif: Skor Ergonomi Tombol (Fitts's Quick Audit){RESET}")
    try:
        dist_input = input("Masukkan jarak kursor/jari ke target (pixel, default 450): ").strip()
        width_input = input("Masukkan ukuran/lebar target (pixel, default 44): ").strip()

        dist = float(dist_input) if dist_input else 450.0
        width = float(width_input) if width_input else 44.0

        id_bits, mt_sec = calculate_fitts(dist, width)
        mt_ms = mt_sec * 1000.0

        print(f"\n{BOLD}Hasil Diagnostik:{RESET}")
        print(f" - Index of Difficulty (ID): {id_bits:.2f} bits")
        print(f" - Estimasi Waktu Capai     : {mt_ms:.1f} ms")

        if mt_ms < 350:
            print(f" - Status Penilaian       : {GREEN}{BOLD}EXCELLENT (Optimal Touch Target){RESET}")
        elif mt_ms < 600:
            print(f" - Status Penilaian       : {YELLOW}{BOLD}ACCEPTABLE (Standard Desktop/Web Target){RESET}")
        else:
            print(f" - Status Penilaian       : {RED}{BOLD}HIGH FRICTION (Target Terlalu Jauh / Kecil - Resiko Miss-click){RESET}")
    except (ValueError, EOFError):
        print(f"{YELLOW}Input tidak valid atau mode non-interaktif, menggunakan nilai default evaluasi.{RESET}")


def self_verify() -> bool:
    """Verifikasi unit internal matematika interaksi."""
    id_test, mt_test = calculate_fitts(300.0, 100.0)
    # log2(300/100 + 1) = log2(4) = 2.0
    assert round(id_test, 2) == 2.0, f"Expected ID 2.0, got {id_test}"
    assert mt_test > 0.1, "MT must be positive realistic time"

    hick_test = calculate_hick(3)
    assert round(hick_test, 4) == round(0.155 * math.log2(4), 4)
    return True


def main() -> None:
    print_banner()

    # Jalankan self-verification
    if not self_verify():
        print(f"{BG_RED} GAGAL VERIFIKASI KALKULASI SISTEM {RESET}")
        sys.exit(1)

    simulate_fitts_law()
    simulate_hick_law()

    engine = HookModelEngine("CollabCraft (Design Workspace App)")
    engine.run_simulation()

    simulate_feedback_latency()

    # Jika terminal interaktif (stdin tty), jalankan modul interaktif audit
    if sys.stdin.isatty():
        run_interactive_audit()
    else:
        print(f"{DIM}[Info] Mode non-interaktif terdeteksi; audit Fitts manual dilewati.{RESET}")

    print(f"{CYAN}================================================================================")
    print(f"   [OK] Simulasi Interaksi & Mekanika Perilaku Selesai Dijalankan Valid 100%    ")
    print(f"================================================================================{RESET}")


if __name__ == "__main__":
    main()
