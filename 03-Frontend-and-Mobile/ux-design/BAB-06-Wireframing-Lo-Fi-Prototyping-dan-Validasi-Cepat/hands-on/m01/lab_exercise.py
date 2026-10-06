#!/usr/bin/env python3
"""
Lab Exercise: Wireframing, Lo-Fi Prototyping, dan Validasi Cepat (UX Design)
Simulasi teknis interaktif berbasis Terminal dengan ANSI styling:
1. Low-Fidelity Wireframe Canvas & Layout Hierarchy (ASCII Mockups)
2. State Transition Engine (Clickable Lo-Fi Prototype Navigation)
3. Rapid Usability Metrics Calculator (SUS Score, Task Completion Rate, Nielsen Severity)
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --- ANSI Color Palette ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    FG_CYAN = "\033[36m"
    FG_GREEN = "\033[32m"
    FG_YELLOW = "\033[33m"
    FG_BLUE = "\033[34m"
    FG_MAGENTA = "\033[35m"
    FG_RED = "\033[31m"
    FG_WHITE = "\033[37m"
    FG_GRAY = "\033[90m"
    
    # Background
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_GRAY = "\033[100m"


def header(title: str) -> None:
    print(f"\n{Style.BG_BLUE}{Style.FG_WHITE}{Style.BOLD} {title.center(64)} {Style.RESET}\n")


def subheader(title: str) -> None:
    print(f"{Style.FG_CYAN}{Style.BOLD}▶ {title}{Style.RESET}")


@dataclass
class WireframeBlock:
    id: str
    label: str
    element_type: str  # 'header', 'hero', 'card', 'button', 'input'
    width: int
    height: int


class WireframeRenderer:
    """Render representasi low-fidelity visual box model pada terminal."""
    
    @staticmethod
    def render_screen(title: str, blocks: List[WireframeBlock]) -> None:
        border_top = f"{Style.FG_GRAY}┌" + "─" * 58 + "┐" + Style.RESET
        border_bottom = f"{Style.FG_GRAY}└" + "─" * 58 + "┘" + Style.RESET
        
        print(border_top)
        print(f"{Style.FG_GRAY}│{Style.RESET} {Style.BOLD}{title.center(56)}{Style.RESET} {Style.FG_GRAY}│{Style.RESET}")
        print(f"{Style.FG_GRAY}├" + "─" * 58 + "┤" + Style.RESET)
        
        for b in blocks:
            if b.element_type == "header":
                print(f"{Style.FG_GRAY}│{Style.RESET} {Style.BG_GRAY}{Style.FG_WHITE}[LOGO]        [MENU 1]  [MENU 2]  [PROFILE]{Style.RESET}".ljust(69) + f"{Style.FG_GRAY}│{Style.RESET}")
            elif b.element_type == "hero":
                print(f"{Style.FG_GRAY}│{Style.RESET}   {Style.FG_YELLOW}╔═══════════════════════════════════════════════╗{Style.RESET}   {Style.FG_GRAY}│{Style.RESET}")
                print(f"{Style.FG_GRAY}│{Style.RESET}   {Style.FG_YELLOW}║ {b.label.center(45)} ║{Style.RESET}   {Style.FG_GRAY}│{Style.RESET}")
                print(f"{Style.FG_GRAY}│{Style.RESET}   {Style.FG_YELLOW}║               [CTA BUTTON (Primary)]          ║{Style.RESET}   {Style.FG_GRAY}│{Style.RESET}")
                print(f"{Style.FG_GRAY}│{Style.RESET}   {Style.FG_YELLOW}╚═══════════════════════════════════════════════╝{Style.RESET}   {Style.FG_GRAY}│{Style.RESET}")
            elif b.element_type == "card_row":
                print(f"{Style.FG_GRAY}│{Style.RESET}   {Style.FG_CYAN}┌──────────────┐ ┌──────────────┐ ┌──────────────┐{Style.RESET}   {Style.FG_GRAY}│{Style.RESET}")
                print(f"{Style.FG_GRAY}│{Style.RESET}   {Style.FG_CYAN}│ [Img] Card 1 │ │ [Img] Card 2 │ │ [Img] Card 3 │{Style.RESET}   {Style.FG_GRAY}│{Style.RESET}")
                print(f"{Style.FG_GRAY}│{Style.RESET}   {Style.FG_CYAN}│ Info & Price │ │ Info & Price │ │ Info & Price │{Style.RESET}   {Style.FG_GRAY}│{Style.RESET}")
                print(f"{Style.FG_GRAY}│{Style.RESET}   {Style.FG_CYAN}└──────────────┘ └──────────────┘ └──────────────┘{Style.RESET}   {Style.FG_GRAY}│{Style.RESET}")
            elif b.element_type == "input_group":
                print(f"{Style.FG_GRAY}│{Style.RESET}   {Style.FG_WHITE}Label: {b.label}{Style.RESET}".ljust(68) + f"{Style.FG_GRAY}│{Style.RESET}")
                print(f"{Style.FG_GRAY}│{Style.RESET}   {Style.FG_GRAY}[ __________________________________________ ]{Style.RESET}   {Style.FG_GRAY}│{Style.RESET}")
            elif b.element_type == "footer":
                print(f"{Style.FG_GRAY}├" + "─" * 58 + "┤" + Style.RESET)
                print(f"{Style.FG_GRAY}│{Style.RESET} {Style.FG_GRAY}(c) 2026 Lo-Fi Blueprint Studio | Privacy - Terms{Style.RESET}".center(68) + f"{Style.FG_GRAY}│{Style.RESET}")
        
        print(border_bottom)


class LoFiPrototypeNavigator:
    """Simulasi interactive state machine antar artboard/layar."""
    
    def __init__(self):
        self.screens: Dict[str, Dict] = {
            "HOME": {
                "title": "SCREEN 1: Home Dashboard",
                "blocks": [
                    WireframeBlock("h1", "Navigation Bar", "header", 56, 1),
                    WireframeBlock("hero", "Temukan Solusi Finansial Anda", "hero", 50, 4),
                    WireframeBlock("cards", "Pilihan Produk Rekomendasi", "card_row", 50, 4),
                    WireframeBlock("ft", "Footer", "footer", 56, 1),
                ],
                "actions": {
                    "1": ("Buka Form Pengajuan Pinjaman", "FORM"),
                    "2": ("Lihat Rincian Kartu Produk", "DETAILS"),
                }
            },
            "FORM": {
                "title": "SCREEN 2: Form Pengajuan (Checkout/Lead)",
                "blocks": [
                    WireframeBlock("h1", "Navigation Bar", "header", 56, 1),
                    WireframeBlock("in1", "Nominal Pinjaman (IDR)", "input_group", 50, 2),
                    WireframeBlock("in2", "Tenor Angsuran (Bulan)", "input_group", 50, 2),
                    WireframeBlock("ft", "Footer", "footer", 56, 1),
                ],
                "actions": {
                    "1": ("Submit Aplikasi (Validasi Sukses)", "SUCCESS"),
                    "2": ("Kembali ke Home", "HOME"),
                }
            },
            "DETAILS": {
                "title": "SCREEN 3: Spesifikasi Produk Detail",
                "blocks": [
                    WireframeBlock("h1", "Navigation Bar", "header", 56, 1),
                    WireframeBlock("hero", "Detail Suku Bunga & Biaya Admin", "hero", 50, 4),
                    WireframeBlock("ft", "Footer", "footer", 56, 1),
                ],
                "actions": {
                    "1": ("Lanjut Ajukan di Form", "FORM"),
                    "2": ("Kembali ke Home", "HOME"),
                }
            },
            "SUCCESS": {
                "title": "SCREEN 4: Konfirmasi / Success State",
                "blocks": [
                    WireframeBlock("h1", "Navigation Bar", "header", 56, 1),
                    WireframeBlock("hero", "Aplikasi Terkirim! Ref #TX-9021", "hero", 50, 4),
                    WireframeBlock("ft", "Footer", "footer", 56, 1),
                ],
                "actions": {
                    "1": ("Kembali ke Home", "HOME"),
                }
            }
        }
        self.current_screen = "HOME"

    def run_flow(self, auto_steps: Optional[List[str]] = None):
        step_idx = 0
        while True:
            screen_data = self.screens[self.current_screen]
            WireframeRenderer.render_screen(screen_data["title"], screen_data["blocks"])
            
            print(f"\n{Style.FG_GREEN}{Style.BOLD}Hotspot Interactions Tersedia:{Style.RESET}")
            for key, (label, target) in screen_data["actions"].items():
                print(f" [{Style.BOLD}{key}{Style.RESET}] {label} {Style.FG_GRAY}--> ({target}){Style.RESET}")
            print(f" [{Style.BOLD}Q{Style.RESET}] Keluar dari Click-Through Flow")

            if auto_steps is not None:
                if step_idx < len(auto_steps):
                    choice = auto_steps[step_idx]
                    step_idx += 1
                    print(f"\n{Style.FG_YELLOW}» [Auto Pilot] Memilih opsi: {choice}{Style.RESET}")
                    time.sleep(0.3)
                else:
                    print(f"\n{Style.FG_CYAN}Auto Pilot selesai.{Style.RESET}")
                    break
            else:
                choice = input(f"\n{Style.FG_WHITE}Pilih action hotspot [1-2/Q]: {Style.RESET}").strip().upper()

            if choice == "Q":
                break
            elif choice in screen_data["actions"]:
                next_target = screen_data["actions"][choice][1]
                print(f"{Style.FG_MAGENTA}Transisi ke artboard: {next_target}...{Style.RESET}")
                self.current_screen = next_target
            else:
                print(f"{Style.FG_RED}Pilihan hotspot tidak valid! Coba lagi.{Style.RESET}")


class RapidValidationMetrics:
    """Kalkulator Metrik Validasi Kualitatif & Kuantitatif (SUS, Severity, TCR)."""
    
    @staticmethod
    def calculate_sus(scores: List[int]) -> float:
        """
        System Usability Scale (SUS) 10-Item Standard Calculation.
        scores: array 10 angka skala Likert (1 - 5).
        Aturan:
        - Pertanyaan Ganjil (1,3,5,7,9): skor - 1
        - Pertanyaan Genap (2,4,6,8,10): 5 - skor
        - Total skor dikalikan 2.5 (Rentang 0 - 100).
        """
        if len(scores) != 10:
            raise ValueError("SUS membutuhkan tepat 10 respon Likert!")
        
        transformed = []
        for i, val in enumerate(scores):
            if i % 2 == 0:  # Ganjil (0-indexed)
                transformed.append(val - 1)
            else:  # Genap
                transformed.append(5 - val)
        return sum(transformed) * 2.5

    @staticmethod
    def assess_sus_grade(sus: float) -> str:
        if sus >= 80.3:
            return f"{Style.FG_GREEN}Grade A+ (Excellent / Industry Benchmark Leader){Style.RESET}"
        elif sus >= 68.0:
            return f"{Style.FG_CYAN}Grade B (Good / Average Pass Rate Benchmark){Style.RESET}"
        elif sus >= 51.0:
            return f"{Style.FG_YELLOW}Grade D (Poor / High Friction Detected){Style.RESET}"
        else:
            return f"{Style.FG_RED}Grade F (Unacceptable / High Cognitive Load){Style.RESET}"

    @staticmethod
    def nielsen_severity_guide() -> None:
        print(f"\n{Style.BOLD}Nielsen Usability Problem Severity Rating (0 - 4):{Style.RESET}")
        print(f" {Style.FG_GRAY}0 - Not a problem:{Style.RESET} Masalah kosmetik minor tanpa dampak usability.")
        print(f" {Style.FG_BLUE}1 - Cosmetic problem only:{Style.RESET} Diperbaiki jika ada waktu tersisa.")
        print(f" {Style.FG_YELLOW}2 - Minor usability problem:{Style.RESET} Prioritas rendah; pengguna masih bisa melanjutkan.")
        print(f" {Style.FG_MAGENTA}3 - Major usability problem:{Style.RESET} Prioritas tinggi; banyak pengguna terhambat.")
        print(f" {Style.FG_RED}4 - Usability catastrophe:{Style.RESET} Blocker mutlak; produk wajib ditahan sebelum rilis.")


def interactive_sus_calculator():
    header("KALKULATOR SYSTEM USABILITY SCALE (SUS)")
    sample_scores = [4, 2, 5, 1, 4, 2, 5, 2, 4, 2]
    
    print("Contoh 10 Respon Pengujian Cepat:")
    for idx, sc in enumerate(sample_scores, 1):
        print(f"  Q{idx:02d}: Respon {sc}/5")
        
    sus_score = RapidValidationMetrics.calculate_sus(sample_scores)
    grade = RapidValidationMetrics.assess_sus_grade(sus_score)
    
    print(f"\n{Style.BOLD}Hasil Kalkulasi SUS:{Style.RESET}")
    print(f" Skor Akhir : {Style.BOLD}{Style.FG_CYAN}{sus_score:.2f} / 100{Style.RESET}")
    print(f" Penilaian  : {grade}")


def main():
    header("BAB-06 UX LAB: WIREFRAMING, LO-FI & RAPID VALIDATION")
    
    # Auto-mode jika dijalankan via argument CLI --demo atau interactive
    is_demo = "--demo" in sys.argv or not sys.stdin.isatty()
    
    subheader("1. Arsitektur Komponen Wireframe Terminal")
    print("Menyiapkan grid layout dan rendering mockups berkepadatan rendah (Lo-Fi)...")
    
    navigator = LoFiPrototypeNavigator()
    
    if is_demo:
        print(f"{Style.FG_YELLOW}[Mode Non-Interaktif / Demo Dijalankan]{Style.RESET}")
        # Jalankan flow navigasi contoh: Home -> Details -> Form -> Success -> Keluar
        navigator.run_flow(auto_steps=["2", "1", "1", "1", "Q"])
        interactive_sus_calculator()
        RapidValidationMetrics.nielsen_severity_guide()
        header("LAB EXERCISE BERHASIL DISELESAIKAN")
        return

    while True:
        print(f"\n{Style.BOLD}PILIH MENU SIMULASI:{Style.RESET}")
        print(" [1] Jalankan Click-Through Lo-Fi Prototype (Interactive)")
        print(" [2] Kalkulasi Metrik Evaluasi Cepat (SUS)")
        print(" [3] Pelajari Nielsen Usability Severity Scale")
        print(" [4] Keluar")
        
        pilihan = input(f"\n{Style.FG_WHITE}Pilihan Anda [1-4]: {Style.RESET}").strip()
        if pilihan == "1":
            navigator.run_flow()
        elif pilihan == "2":
            interactive_sus_calculator()
        elif pilihan == "3":
            RapidValidationMetrics.nielsen_severity_guide()
        elif pilihan == "4":
            print(f"\n{Style.FG_GREEN}Selesai. Terima kasih telah mengeksplorasi konsep Lo-Fi UX Design!{Style.RESET}\n")
            break
        else:
            print(f"{Style.FG_RED}Pilihan tidak valid.{Style.RESET}")


if __name__ == "__main__":
    main()
