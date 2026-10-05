#!/usr/bin/env python3
"""
Lab Exercise: Usability Testing Terukur & Metrik UX Standar (BAB 07)
Arsitektur Evaluasi Metrik Kuantitatif UX Produksi:
- System Usability Scale (SUS) Calculator & Grading Engine
- Single Ease Question (SEQ) & UMUX-Lite Pipeline
- Task Performance Metrics (Completion Rate, Time on Task, Error Rate)
- Wilson Score Interval & Benchmark Validator
"""

import sys
import time
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


# ==========================================
# Terminal ANSI Color Palette
# ==========================================
class Color:
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
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_RED = "\033[41m"


def header(text: str) -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} {text.upper()} {Color.RESET}")


def alert(level: str, message: str) -> None:
    colors = {
        "INFO": Color.CYAN,
        "PASS": Color.GREEN,
        "WARN": Color.YELLOW,
        "FAIL": Color.RED,
    }
    col = colors.get(level, Color.WHITE)
    print(f"{col}[{level}] {message}{Color.RESET}")


# ==========================================
# Data Models & Enums
# ==========================================
class ErrorType(Enum):
    SLIP = "Slip (Unintentional Action)"
    MISTAKE = "Mistake (Flawed Mental Model)"


@dataclass
class TaskMetric:
    task_id: str
    task_name: str
    completed: bool
    duration_seconds: float
    error_count: int
    primary_error_type: Optional[ErrorType]
    seq_score: int  # 1 (Very Difficult) to 7 (Very Easy)


@dataclass
class ParticipantSession:
    participant_id: str
    cohort: str
    tasks: List[TaskMetric] = field(default_factory=list)
    sus_raw_responses: List[int] = field(default_factory=list)  # 10 questions (1-5 Likert)
    umux_lite_responses: Tuple[int, int] = (5, 5)  # Q1 (Capability), Q2 (Ease of Use) 1-7 scale


# ==========================================
# Core Analytics Engine
# ==========================================
class SUSCalculator:
    """
    Standard System Usability Scale (SUS) Calculator
    10 items on a 5-point Likert scale (1 = Strongly Disagree, 5 = Strongly Agree).
    - Odd questions (1, 3, 5, 7, 9): score contribution = response - 1
    - Even questions (2, 4, 6, 8, 10): score contribution = 5 - response
    - Total multiplied by 2.5 gives 0-100 scale.
    """

    GRADE_SCALE = [
        (84.1, "A+", "Best Imaginable (Percentile 96-100%)", Color.GREEN),
        (80.3, "A", "Excellent (Percentile 90-95%)", Color.GREEN),
        (74.0, "B", "Good (Percentile 70-89%)", Color.CYAN),
        (68.0, "C", "Average / Industry Benchmark Baseline (Percentile 50-69%)", Color.YELLOW),
        (51.0, "D", "Poor / Requires UX Rework (Percentile 15-49%)", Color.MAGENTA),
        (0.0, "F", "Awful / Critical Usability Failure (Percentile 0-14%)", Color.RED),
    ]

    @classmethod
    def calculate_score(cls, responses: List[int]) -> float:
        if len(responses) != 10:
            raise ValueError(f"SUS requires exactly 10 responses, got {len(responses)}")

        sum_contributions = 0
        for i, val in enumerate(responses):
            val = max(1, min(5, val))
            if (i + 1) % 2 == 1:
                # Odd-numbered items: response - 1
                sum_contributions += (val - 1)
            else:
                # Even-numbered items: 5 - response
                sum_contributions += (5 - val)

        return round(sum_contributions * 2.5, 2)

    @classmethod
    def get_grade(cls, score: float) -> Tuple[str, str, str]:
        for threshold, grade, desc, color in cls.GRADE_SCALE:
            if score >= threshold:
                return grade, desc, color
        return "F", "Critical Failure", Color.RED


class WilsonScoreInterval:
    """Calculates Wilson Score Confidence Interval for Small Sample Completion Rates."""
    @staticmethod
    def calculate(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
        if total == 0:
            return 0.0, 0.0
        z = 1.96 if confidence == 0.95 else 1.645
        p = successes / total
        denominator = 1 + (z ** 2) / total
        centre = (p + (z ** 2) / (2 * total)) / denominator
        margin = (z * math.sqrt((p * (1 - p) + (z ** 2) / (4 * total)) / total)) / denominator
        lower = max(0.0, centre - margin)
        upper = min(1.0, centre + margin)
        return round(lower * 100, 1), round(upper * 100, 1)


class UsabilityAnalyticsPipeline:
    """Aggregates multi-session lab data into enterprise UX benchmarking reports."""

    def __init__(self, target_sus_benchmark: float = 72.0, target_completion_rate: float = 85.0):
        self.target_sus = target_sus_benchmark
        self.target_completion = target_completion_rate
        self.sessions: List[ParticipantSession] = []

    def ingest_session(self, session: ParticipantSession) -> None:
        self.sessions.append(session)

    def generate_report(self) -> None:
        if not self.sessions:
            alert("FAIL", "Belum ada sesi partisipan terdaftar.")
            return

        header("Eksekutif UX Usability Testing Dashboard")
        total_participants = len(self.sessions)
        print(f"Total Partisipan Teruji: {Color.BOLD}{total_participants}{Color.RESET}")

        # 1. Analisis SUS
        sus_scores = [SUSCalculator.calculate_score(s.sus_raw_responses) for s in self.sessions]
        mean_sus = round(sum(sus_scores) / len(sus_scores), 2)
        grade, desc, grade_col = SUSCalculator.get_grade(mean_sus)

        print(f"\n{Color.BOLD}--- System Usability Scale (SUS) ---{Color.RESET}")
        print(f"Rata-rata Skor SUS : {grade_col}{Color.BOLD}{mean_sus} / 100{Color.RESET}")
        print(f"Predikat Evaluasi  : {grade_col}{grade} - {desc}{Color.RESET}")
        print(f"Target Benchmark   : {self.target_sus} (Industry Standard: 68.0)")

        if mean_sus >= self.target_sus:
            alert("PASS", f"Skor melampaui target minimum organisasi (+{round(mean_sus - self.target_sus, 2)})")
        else:
            alert("WARN", f"Skor berada di bawah target benchmark (-{round(self.target_sus - mean_sus, 2)})")

        # 2. Analisis Task Performance
        print(f"\n{Color.BOLD}--- Evaluasi Kinerja Tugas (Task Performance) ---{Color.RESET}")
        task_ids = list({t.task_id for s in self.sessions for t in s.tasks})
        task_ids.sort()

        print(f"{'Task ID':<10} | {'Nama Tugas':<24} | {'Success Rate':<14} | {'95% CI (Wilson)':<16} | {'Avg Time (s)':<12} | {'Avg SEQ (1-7)':<14}")
        print("-" * 105)

        for tid in task_ids:
            task_records = [t for s in self.sessions for t in s.tasks if t.task_id == tid]
            success_count = sum(1 for t in task_records if t.completed)
            total_tasks = len(task_records)
            success_rate = (success_count / total_tasks) * 100 if total_tasks > 0 else 0
            ci_low, ci_high = WilsonScoreInterval.calculate(success_count, total_tasks)
            avg_time = sum(t.duration_seconds for t in task_records) / total_tasks
            avg_seq = sum(t.seq_score for t in task_records) / total_tasks
            task_name = task_records[0].task_name

            sr_col = Color.GREEN if success_rate >= self.target_completion else Color.RED
            seq_col = Color.GREEN if avg_seq >= 5.5 else (Color.YELLOW if avg_seq >= 4.0 else Color.RED)

            ci_str = f"[{ci_low}% - {ci_high}%]"
            print(f"{tid:<10} | {task_name[:24]:<24} | {sr_col}{success_rate:>5.1f}%{Color.RESET}        | {ci_str:<16} | {avg_time:>10.1f}s | {seq_col}{avg_seq:>5.2f} / 7{Color.RESET}")

        # 3. Analisis Kesalahan (Slip vs Mistake)
        print(f"\n{Color.BOLD}--- Diagnostik Human Errors (Slip vs Mistake) ---{Color.RESET}")
        total_slips = sum(1 for s in self.sessions for t in s.tasks if t.primary_error_type == ErrorType.SLIP)
        total_mistakes = sum(1 for s in self.sessions for t in s.tasks if t.primary_error_type == ErrorType.MISTAKE)
        print(f"Total Slips    (Action Execution Failure) : {Color.YELLOW}{total_slips}{Color.RESET}")
        print(f"Total Mistakes (Mental Model Mismatch)   : {Color.RED}{total_mistakes}{Color.RESET}")
        if total_mistakes > total_slips:
            alert("FAIL", "Kritis: Frekuensi Mistake mendominasi. Arsitektur informasi & affordance navigasi perlu perombakan.")
        else:
            alert("INFO", "Mayoritas kesalahan adalah Slips. Fokuskan perbaikan pada microcopy, error prevention, dan visual feedback.")


# ==========================================
# Interactive & Mock Simulation Generator
# ==========================================
def generate_sample_cohort(cohort_name: str, count: int, baseline_ux_quality: float = 0.75) -> List[ParticipantSession]:
    """Menghasilkan dataset realistis pengujian usability lab."""
    sessions = []
    tasks_meta = [
        ("T01", "Pencarian Produk & Filter"),
        ("T02", "Konfigurasi Varian & Cart"),
        ("T03", "One-Click Checkout & Pembayaran"),
    ]

    for i in range(1, count + 1):
        pid = f"{cohort_name}-U{i:02d}"
        session_tasks = []

        # SUS generator berbasis quality score
        sus_items = []
        for q_idx in range(10):
            if (q_idx + 1) % 2 == 1:
                # Odd (Positif): Nilai tinggi jika quality tinggi
                val = 4 if random.random() < baseline_ux_quality else random.randint(2, 3)
                if random.random() < 0.2:
                    val = 5
            else:
                # Even (Negatif): Nilai rendah jika quality tinggi
                val = 2 if random.random() < baseline_ux_quality else random.randint(3, 4)
                if random.random() < 0.2:
                    val = 1
            sus_items.append(val)

        for tid, tname in tasks_meta:
            is_success = random.random() < (0.92 * baseline_ux_quality + 0.1)
            duration = round(random.uniform(25.0, 75.0) / (baseline_ux_quality + 0.2), 1)
            err_count = 0 if is_success and random.random() > 0.4 else random.randint(1, 3)
            err_type = None
            if err_count > 0:
                err_type = ErrorType.MISTAKE if random.random() > baseline_ux_quality else ErrorType.SLIP

            seq = random.randint(5, 7) if is_success else random.randint(2, 4)

            session_tasks.append(
                TaskMetric(
                    task_id=tid,
                    task_name=tname,
                    completed=is_success,
                    duration_seconds=duration,
                    error_count=err_count,
                    primary_error_type=err_type,
                    seq_score=seq,
                )
            )

        sessions.append(
            ParticipantSession(
                participant_id=pid,
                cohort=cohort_name,
                tasks=session_tasks,
                sus_raw_responses=sus_items,
            )
        )
    return sessions


def run_interactive_wizard() -> None:
    """Menjalankan wizard simulasi dan evaluasi UX interaktif di terminal."""
    header("Lab Simulasi Usability Testing & Metrik UX Produksi")
    print(f"{Color.CYAN}Platform Evaluasi Metrik Kuantitatif Desain Pengalaman Pengguna{Color.RESET}")
    print("Mendukung SUS, Single Ease Question (SEQ), & Wilson Score Confidence Intervals.\n")

    pipeline = UsabilityAnalyticsPipeline(target_sus_benchmark=74.0, target_completion_rate=80.0)

    print(f"{Color.BOLD}PILIH MODE OPERASI:{Color.RESET}")
    print("1. Jalankan Simulasi Otomatis (Batch Cohort A/B Usability Benchmark)")
    print("2. Input Sesi Partisipan Manual (Live Evaluasi Kuesioner SUS 10-Item)")
    print("3. Keluar")

    choice = input(f"\n{Color.YELLOW}Masukkan pilihan (1-3) [default: 1]: {Color.RESET}").strip() or "1"

    if choice == "1":
        alert("INFO", "Menginisialisasi dataset pengujian Cohort A (Mobile V2 Redesign) & Cohort B (Legacy)...")
        time.sleep(0.5)

        cohort_a = generate_sample_cohort("Redesign-V2", count=15, baseline_ux_quality=0.88)
        for s in cohort_a:
            pipeline.ingest_session(s)

        pipeline.generate_report()

        print(f"\n{Color.GREEN}{Color.BOLD}Rekomendasi Keputusan Produk:{Color.RESET}")
        print(f"- Desain siap untuk transisi ke tahap Release Candidate (RC).")
        print(f"- Evaluasi Single Ease Question (SEQ) menunjukkan kepuasan tinggi pada alur Checkout.")

    elif choice == "2":
        header("Input Data Kuesioner SUS Partisipan")
        pid = input("Masukkan ID Partisipan (misal: P-01): ").strip() or "P-01"
        print(f"\nMasukkan skor 1-5 (1: Sangat Tidak Setuju, 5: Sangat Setuju) untuk 10 pernyataan SUS:\n")
        questions = [
            "1. Saya rasa saya akan sering menggunakan sistem ini.",
            "2. Saya merasa sistem ini terlalu rumit padahal tidak perlu.",
            "3. Saya rasa sistem ini mudah digunakan.",
            "4. Saya rasa saya memerlukan bantuan teknisi untuk dapat menggunakan sistem ini.",
            "5. Saya merasa berbagai fungsi dalam sistem ini terintegrasi dengan baik.",
            "6. Saya rasa ada terlalu banyak ketidakkonsistenan pada sistem ini.",
            "7. Saya rasa kebanyakan orang akan mempelajari sistem ini dengan sangat cepat.",
            "8. Saya merasa sistem ini sangat membingungkan saat digunakan.",
            "9. Saya merasa sangat percaya diri saat menggunakan sistem ini.",
            "10. Saya harus belajar banyak hal sebelum saya bisa menggunakan sistem ini.",
        ]
        responses = []
        for q in questions:
            while True:
                try:
                    val_str = input(f"{q} [1-5]: ").strip()
                    val = int(val_str)
                    if 1 <= val <= 5:
                        responses.append(val)
                        break
                    print(f"{Color.RED}Nilai harus antara 1 sampai 5.{Color.RESET}")
                except ValueError:
                    print(f"{Color.RED}Harap masukkan angka bulat 1-5.{Color.RESET}")

        score = SUSCalculator.calculate_score(responses)
        grade, desc, col = SUSCalculator.get_grade(score)
        print(f"\n{Color.BOLD}HASIL PERHITUNGAN SUS PARTISIPAN {pid}:{Color.RESET}")
        print(f"Skor Akhir : {col}{Color.BOLD}{score} / 100{Color.RESET}")
        print(f"Predikat   : {col}{grade} ({desc}){Color.RESET}")

    else:
        print(f"{Color.WHITE}Selesai.{Color.RESET}")


if __name__ == "__main__":
    try:
        # Jika dijalankan non-interaktif di lingkungan CLI otomatis
        if not sys.stdin.isatty():
            pipeline = UsabilityAnalyticsPipeline()
            cohort = generate_sample_cohort("AutomatedCI", count=10, baseline_ux_quality=0.85)
            for s in cohort:
                pipeline.ingest_session(s)
            pipeline.generate_report()
        else:
            run_interactive_wizard()
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}Operasi dibatalkan oleh pengguna.{Color.RESET}")
        sys.exit(0)
