#!/usr/bin/env python3
"""
Hands-on Lab Exercise: BAB 06 - Wireframing, Lo-Fi Prototyping, & Rapid Validation
Interactive CLI simulation of production-grade UX Lo-Fi wireframing and user testing telemetry engine.
"""

import sys
import time
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional


# ==============================================================================
# ANSI Color Palette & Terminal Styling
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    FG_RED = "\033[31m"
    FG_GREEN = "\033[32m"
    FG_YELLOW = "\033[33m"
    FG_BLUE = "\033[34m"
    FG_MAGENTA = "\033[35m"
    FG_CYAN = "\033[36m"
    FG_WHITE = "\033[37m"
    
    # High-intensity Foreground
    FG_HI_BLACK = "\033[90m"
    FG_HI_WHITE = "\033[97m"

    # Background
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"
    BG_MAGENTA = "\033[45m"
    BG_DARK_GRAY = "\033[100m"


def header(text: str) -> str:
    line = "=" * 68
    return f"{Color.FG_CYAN}{Color.BOLD}{line}\n  {text}\n{line}{Color.RESET}"


def subheader(text: str) -> str:
    return f"{Color.FG_YELLOW}{Color.BOLD}>>> {text}{Color.RESET}"


def badge(label: str, text: str, color: str = Color.FG_GREEN) -> str:
    return f"[{color}{Color.BOLD}{label}{Color.RESET}] {text}"


# ==============================================================================
# Domain Models: Lo-Fi Wireframing & Usability Testing
# ==============================================================================
class ViewportType(Enum):
    MOBILE = "Mobile (375x667)"
    DESKTOP = "Desktop (1280x800)"


class UserFeedbackSentiment(Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    CONFUSED = "CONFUSED"
    CRITICAL = "CRITICAL"


@dataclass
class UsabilityMetric:
    task_id: str
    task_name: str
    duration_seconds: float
    completed_successfully: bool
    misclicks: int
    user_sentiment: UserFeedbackSentiment
    qualitative_notes: str


@dataclass
class WireframeComponent:
    comp_id: str
    label: str
    wireframe_representation: str
    action_trigger: Optional[str] = None


@dataclass
class WireframeScreen:
    screen_id: str
    title: str
    viewport: ViewportType
    components: List[WireframeComponent]
    description: str


# ==============================================================================
# Wireframe ASCII Rendering Engine
# ==============================================================================
class WireframeRenderer:
    """Renders low-fidelity wireframe blueprints directly onto the terminal."""

    @staticmethod
    def render_mobile_frame(screen: WireframeScreen) -> None:
        width = 46
        print(f"\n{Color.FG_HI_BLACK}┌{'─' * (width - 2)}┐{Color.RESET}")
        print(f"{Color.FG_HI_BLACK}│{Color.RESET}{Color.BOLD}{screen.title.center(width - 2)}{Color.RESET}{Color.FG_HI_BLACK}│{Color.RESET}")
        print(f"{Color.FG_HI_BLACK}├{'─' * (width - 2)}┤{Color.RESET}")
        print(f"{Color.FG_HI_BLACK}│ [≡ MENU]                [🔍 SEARCH] [👤] │{Color.RESET}")
        print(f"{Color.FG_HI_BLACK}├{'┄' * (width - 2)}┤{Color.RESET}")

        for comp in screen.components:
            lines = comp.wireframe_representation.split("\n")
            for line in lines:
                padded = line.ljust(width - 4)
                print(f"{Color.FG_HI_BLACK}│ {Color.RESET}{padded}{Color.FG_HI_BLACK} │{Color.RESET}")

        print(f"{Color.FG_HI_BLACK}├{'─' * (width - 2)}┤{Color.RESET}")
        print(f"{Color.FG_HI_BLACK}│ [🏠 Home]   [📋 Workflow]   [⚙ Settings] │{Color.RESET}")
        print(f"{Color.FG_HI_BLACK}└{'─' * (width - 2)}┘{Color.RESET}")

    @staticmethod
    def render_desktop_frame(screen: WireframeScreen) -> None:
        width = 68
        print(f"\n{Color.FG_BLUE}╔{'═' * (width - 2)}╗{Color.RESET}")
        print(f"{Color.FG_BLUE}║ [● ● ●] Browser: Lo-Fi Prototype Sandbox - {screen.title[:30]} ║{Color.RESET}")
        print(f"{Color.FG_BLUE}╠{'═' * (width - 2)}╣{Color.RESET}")
        print(f"{Color.FG_BLUE}║ {Color.BOLD}BRAND LOGO{Color.RESET}{' ' * 16}Nav: [Overview] [Flows] [Validations] ║{Color.RESET}")
        print(f"{Color.FG_BLUE}╠{'─' * (width - 2)}╢{Color.RESET}")

        for comp in screen.components:
            lines = comp.wireframe_representation.split("\n")
            for line in lines:
                padded = line.ljust(width - 4)
                print(f"{Color.FG_BLUE}║ {Color.RESET}{padded}{Color.FG_BLUE} ║{Color.RESET}")

        print(f"{Color.FG_BLUE}╚{'═' * (width - 2)}╝{Color.RESET}")


# ==============================================================================
# SUS (System Usability Scale) & Validation Telemetry Engine
# ==============================================================================
class ValidationTelemetryEngine:
    """Calculates System Usability Scale (SUS) scores and validation KPIs."""

    SUS_QUESTIONS = [
        "1. Saya merasa ingin sering menggunakan prototipe sistem ini.",
        "2. Saya merasa sistem ini terlalu rumit dan tidak perlu serumit ini.",
        "3. Saya merasa prototipe ini sangat mudah digunakan.",
        "4. Saya rasa saya butuh bantuan teknis untuk bisa memakai sistem ini.",
        "5. Berbagai fungsi pada prototipe terintegrasi dengan sangat baik.",
        "6. Terlalu banyak inkonsistensi yang membingungkan dalam prototipe ini.",
        "7. Pengguna awam akan cepat memahami sistem ini dalam beberapa menit.",
        "8. Alur navigasi terasa sangat kaku dan membingungkan (cumbersome).",
        "9. Saya merasa sangat percaya diri saat menyelesaikan alur tugas.",
        "10. Saya harus belajar banyak hal dulu sebelum terbiasa dengan sistem."
    ]

    @staticmethod
    def calculate_sus_score(responses: List[int]) -> float:
        """
        Brooke's SUS Standard:
        Odd items: score - 1
        Even items: 5 - score
        Sum multiplied by 2.5 (Range 0 - 100).
        """
        if len(responses) != 10:
            raise ValueError("SUS Calculation requires exactly 10 question responses.")

        score_sum = 0
        for i, ans in enumerate(responses):
            if i % 2 == 0:  # Odd indexed in 1-based (0, 2, 4...)
                score_sum += (ans - 1)
            else:  # Even indexed in 1-based (1, 3, 5...)
                score_sum += (5 - ans)
        return score_sum * 2.5

    @staticmethod
    def get_sus_grade(score: float) -> Dict[str, str]:
        if score >= 85.0:
            return {"grade": "A+", "rating": "Best Imaginable", "adjective": "Excellent", "color": Color.FG_GREEN}
        elif score >= 80.0:
            return {"grade": "A", "rating": "Excellent", "adjective": "Good", "color": Color.FG_GREEN}
        elif score >= 68.0:
            return {"grade": "C", "rating": "Above Average (Industry Benchmark 68.0)", "adjective": "OK", "color": Color.FG_CYAN}
        elif score >= 51.0:
            return {"grade": "D", "rating": "Below Average (Needs Iteration)", "adjective": "Poor", "color": Color.FG_YELLOW}
        else:
            return {"grade": "F", "rating": "Unacceptable (High Risk Friction)", "adjective": "Worst", "color": Color.FG_RED}


# ==============================================================================
# Interactive Lab State Manager
# ==============================================================================
class UxLabSession:
    def __init__(self, non_interactive: bool = False):
        self.non_interactive = non_interactive
        self.recorded_metrics: List[UsabilityMetric] = []
        self.screens: Dict[str, WireframeScreen] = self._init_screen_catalog()

    def _init_screen_catalog(self) -> Dict[str, WireframeScreen]:
        s1 = WireframeScreen(
            screen_id="SCR_01_ONBOARDING",
            title="Wireframe: Onboarding & Value Prop",
            viewport=ViewportType.MOBILE,
            description="Wireframe beresolusi rendah untuk mengetes pemahaman nilai utama sistem.",
            components=[
                WireframeComponent("C1", "Hero Image Placeholder", "[X] ===== [HERO ILLUSTRATION PLACEHOLDER] ===== [X]"),
                WireframeComponent("C2", "Headline H1", "Title: Solusi Cepat Kelola Proyek Lo-Fi\nSubtitle: Validasi ide produk dalam hitungan jam."),
                WireframeComponent("C3", "Value Prop Points", "* [✓] Wireframe Instan\n* [✓] Testing Guerilla Terpadu\n* [✓] Telemetri SUS Otomatis"),
                WireframeComponent("C4", "CTA Primary", "[ === (1) MULAI FREE TRIAL SEKARANG === ]", action_trigger="GO_FORM"),
                WireframeComponent("C5", "Secondary Link", "            (2) Lihat Dokumentasi Alur")
            ]
        )

        s2 = WireframeScreen(
            screen_id="SCR_02_FORM",
            title="Wireframe: Registration & Flow Setup",
            viewport=ViewportType.MOBILE,
            description="Formulir pendaftaran minimal untuk mengukur cognitive load dan drop-off rate.",
            components=[
                WireframeComponent("C6", "Form Header", "Daftarkan Tim Desain Anda (Step 1 of 2)"),
                WireframeComponent("C7", "Input Email", "Email Kantor:\n[ user@company.domain _________________ ]"),
                WireframeComponent("C8", "Input Password", "Kata Sandi (min 8 karakter):\n[ **********                            ]"),
                WireframeComponent("C9", "Checkbox Consent", "[x] Saya setuju dengan Kebijakan Privasi Data"),
                WireframeComponent("C10", "Action Buttons", "[ (1) LANJUT KE PEMBAYARAN ]  [ (2) BATAL ]", action_trigger="GO_CONFIRM")
            ]
        )

        s3 = WireframeScreen(
            screen_id="SCR_03_CONFIRM",
            title="Wireframe: Confirmation & Dashboard",
            viewport=ViewportType.DESKTOP,
            description="Layar desktop konfirmasi keberhasilan checkout dan instruksi tindak lanjut.",
            components=[
                WireframeComponent("C11", "Success Banner", "[✓] REGISTRASI DAN INISIALISASI TIM BERHASIL!\nID Transaksi: #TRX-99482-LOFI"),
                WireframeComponent("C12", "Task Guidance", "Langkah Selanjutnya:\n 1. Undang 3 anggota tim ke kanban board\n 2. Unduh template stensil wireframe kertas\n 3. Jalankan sesi Guerilla User Test pertama"),
                WireframeComponent("C13", "Quick Actions", "[ (1) Buka Testing Dashboard ]   [ (2) Cetak Hasil Audit ]", action_trigger="GO_SUMMARY")
            ]
        )
        return {"SCR_01_ONBOARDING": s1, "SCR_02_FORM": s2, "SCR_03_CONFIRM": s3}

    def simulate_telemetry_capture(self) -> None:
        """Simulates rapid user testing telemetry with realistic distributions."""
        tasks = [
            ("TSK-01", "Identifikasi Value Proposition Utama pada Onboarding", 4.2, True, 0, UserFeedbackSentiment.POSITIVE, "Pengguna langsung paham tanpa scroll berlebih."),
            ("TSK-02", "Penyelesaian Form Pendaftaran Akun", 14.8, True, 1, UserFeedbackSentiment.NEUTRAL, "Satu misclick pada checkbox consent privasi."),
            ("TSK-03", "Navigasi ke Halaman Validasi & Konfirmasi", 6.5, True, 0, UserFeedbackSentiment.POSITIVE, "Hierarki tombol CTA jelas terlihat."),
            ("TSK-04", "Pencarian Tombol Batal pada Formulir", 8.9, False, 3, UserFeedbackSentiment.CONFUSED, "Tombol batal diletakkan terlalu dekat dengan aksi submit.")
        ]
        for tid, tname, dur, success, misclicks, sent, note in tasks:
            self.recorded_metrics.append(UsabilityMetric(
                task_id=tid,
                task_name=tname,
                duration_seconds=dur,
                completed_successfully=success,
                misclicks=misclicks,
                user_sentiment=sent,
                qualitative_notes=note
            ))

    def run_interactive_simulation(self) -> None:
        print(header("LAB EXERCISE: LO-FI WIREFRAME & RAPID VALIDATION ENGINE"))
        print(f"{Color.FG_CYAN}Modul 02: BAB-06 UX Design Production Architecture Simulation{Color.RESET}\n")

        print(badge("INFO", "Memuat arsitektur stensil wireframe dan modul telemetri..."))
        time.sleep(0.3 if not self.non_interactive else 0.0)

        # 1. Tampilkan Katalog Wireframe
        print(subheader("FASE 1: INSPEKSI LO-FI WIREFRAME (LOW-FIDELITY BLUEPRINT)"))
        for screen_key, screen in self.screens.items():
            print(f"\n{Color.BOLD}» Screen ID: {screen_key} ({screen.viewport.value}){Color.RESET}")
            print(f"  {Color.DIM}{screen.description}{Color.RESET}")
            if screen.viewport == ViewportType.MOBILE:
                WireframeRenderer.render_mobile_frame(screen)
            else:
                WireframeRenderer.render_desktop_frame(screen)

        # 2. Eksekusi Telemetri Usability Testing
        print("\n" + subheader("FASE 2: SIMULASI PENGUJIAN PENGGUNA (RAPID GUERILLA TESTING)"))
        self.simulate_telemetry_capture()
        print(f"Berhasil mengumpulkan data telemetri dari {len(self.recorded_metrics)} skenario uji task.")

        print(f"\n{'TASK ID':<10} {'NAMA TUGAS':<38} {'DURASI':<10} {'STATUS':<12} {'MISCLICKS'}")
        print("-" * 78)
        for m in self.recorded_metrics:
            status_str = f"{Color.FG_GREEN}SUCCESS{Color.RESET}" if m.completed_successfully else f"{Color.FG_RED}FAILED{Color.RESET}"
            print(f"{m.task_id:<10} {m.task_name[:36]:<38} {f'{m.duration_seconds:.1f}s':<10} {status_str:<21} {m.misclicks}")

        # 3. Kalkulasi Metrik Utama (Task Completion Rate & Misclick Density)
        total_tasks = len(self.recorded_metrics)
        success_tasks = sum(1 for m in self.recorded_metrics if m.completed_successfully)
        tcr = (success_tasks / total_tasks) * 100.0 if total_tasks > 0 else 0.0
        avg_dur = sum(m.duration_seconds for m in self.recorded_metrics) / total_tasks

        print("\n" + subheader("FASE 3: STATISTIK PERFORMA USABILITY"))
        print(badge("TCR", f"Task Completion Rate: {tcr:.1f}%", Color.FG_GREEN if tcr >= 75 else Color.FG_RED))
        print(badge("TIME", f"Rata-rata Waktu per Tugas: {avg_dur:.2f} detik", Color.FG_CYAN))

        # 4. Kuis & Evaluasi SUS (System Usability Scale)
        print("\n" + subheader("FASE 4: AUDIT SYSTEM USABILITY SCALE (SUS BROOKE 1986)"))
        # Standar benchmark answers (Skala Likert 1-5)
        simulated_sus_responses = [4, 2, 5, 1, 4, 2, 5, 2, 4, 1]
        
        print("Pertanyaan Standar Evaluasi SUS:")
        for idx, q_text in enumerate(ValidationTelemetryEngine.SUS_QUESTIONS):
            resp_val = simulated_sus_responses[idx]
            print(f"  {Color.DIM}{q_text:<70}{Color.RESET} Score: {Color.FG_YELLOW}{resp_val}/5{Color.RESET}")

        sus_final = ValidationTelemetryEngine.calculate_sus_score(simulated_sus_responses)
        grade_info = ValidationTelemetryEngine.get_sus_grade(sus_final)

        print("\n" + "=" * 68)
        print(f"  {Color.BOLD}HASIL PERHITUNGAN SKOR AKHIR SUS:{Color.RESET}")
        print(f"  Skor Numerik  : {grade_info['color']}{Color.BOLD}{sus_final:.1f} / 100.0{Color.RESET}")
        print(f"  Predikat Grade: {grade_info['color']}{Color.BOLD}{grade_info['grade']}{Color.RESET}")
        print(f"  Evaluasi      : {grade_info['color']}{grade_info['rating']} - {grade_info['adjective']}{Color.RESET}")
        print("=" * 68)

        # 5. Rekomendasi Iterasi UX Lanjutan
        print("\n" + subheader("FASE 5: REKOMENDASI PERBAIKAN WIREFRAME"))
        print("1. [High Priority] Redesign SCR_02_FORM: Pindahkan tombol 'Batal' lebih jauh dari 'Lanjut'")
        print("   untuk mengeliminasi 3 misclick dan kebingungan pengguna (TSK-04).")
        print("2. [Medium Priority] Berikan visual cue progress bar yang lebih kontras pada mobile wireframe.")
        print("3. [Next Step] Lanjutkan transisi dari Lo-Fi Wireframe ke Mid-Fi Prototype di Figma/Penpot.\n")

        print(badge("SUCCESS", "Simulasi Arsitektur Produksi UX Validasi Cepat Selesai.", Color.FG_GREEN))


# ==============================================================================
# Main Execution Entrypoint
# ==============================================================================
def main() -> int:
    is_non_interactive = "--auto" in sys.argv or "--test" in sys.argv
    try:
        session = UxLabSession(non_interactive=is_non_interactive)
        session.run_interactive_simulation()
        return 0
    except Exception as exc:
        print(f"{Color.FG_RED}[ERROR] Simulasi terhenti: {str(exc)}{Color.RESET}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
