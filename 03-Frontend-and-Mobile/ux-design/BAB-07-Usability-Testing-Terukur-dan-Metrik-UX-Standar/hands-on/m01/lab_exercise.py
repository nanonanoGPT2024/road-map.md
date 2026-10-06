#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Usability Testing & Perhitungan Metrik UX Terukur
BAB 07 - Usability Testing Terukur dan Metrik UX Standar

Skrip ini mensimulasikan sesi Usability Testing kuantitatif dengan menghitung:
1. Completion Rate / Task Success Rate (TSR)
2. Time on Task (ToT) beserta standar deviasi
3. Error Rate per task
4. System Usability Scale (SUS) dengan formula konversi standar Brooke (1996)
5. Single Ease Question (SEQ) pasca-task
"""

import math
import sys
from typing import Dict, List, Optional


class TerminalColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"


C = TerminalColors


class SUSMetricCalculator:
    """Kalkulator System Usability Scale (SUS) 10-Item Standar."""

    QUESTIONS = [
        "1. Saya rasa saya akan sering menggunakan sistem ini.",
        "2. Saya merasa sistem ini terlalu rumit padahal tidak perlu.",
        "3. Saya rasa sistem ini mudah untuk digunakan.",
        "4. Saya membutuhkan bantuan teknisi untuk dapat menggunakan sistem ini.",
        "5. Saya merasa fungsi dalam sistem ini terintegrasi dengan baik.",
        "6. Saya rasa ada terlalu banyak inkonsistensi pada sistem ini.",
        "7. Saya membayangkan orang lain dapat belajar menggunakan sistem ini dengan cepat.",
        "8. Saya merasa sistem ini sangat janggal atau membingungkan untuk digunakan.",
        "9. Saya merasa sangat percaya diri saat menggunakan sistem ini.",
        "10. Saya harus mempelajari banyak hal terlebih dahulu sebelum dapat mengoperasikannya.",
    ]

    @staticmethod
    def calculate_score(responses: List[int]) -> float:
        """Menghitung skor SUS (0 - 100) berdasarkan formula John Brooke (1996).

        - Item bernomor ganjil (1, 3, 5, 7, 9): skor - 1
        - Item bernomor genap (2, 4, 6, 8, 10): 5 - skor
        - Total skor dikalikan 2.5
        """
        if len(responses) != 10:
            raise ValueError("Evaluasi SUS wajib memiliki tepat 10 respons.")

        converted_sum = 0
        for i, val in enumerate(responses):
            if not (1 <= val <= 5):
                raise ValueError(f"Nilai respons harus berada pada skala 1-5, diterima: {val}")
            if i % 2 == 0:  # Item ganjil (0-indexed: 0, 2, 4, 6, 8)
                converted_sum += val - 1
            else:  # Item genap (0-indexed: 1, 3, 5, 7, 9)
                converted_sum += 5 - val

        return round(converted_sum * 2.5, 2)

    @staticmethod
    def get_adjective_rating(sus_score: float) -> str:
        """Kualifikasi interpretasi skor SUS (Bangor et al., 2009)."""
        if sus_score >= 85.0:
            return f"{C.GREEN}Excellent / Grade A+ (Acceptable){C.RESET}"
        elif sus_score >= 80.0:
            return f"{C.GREEN}Good / Grade A (Acceptable){C.RESET}"
        elif sus_score >= 68.0:
            return f"{C.CYAN}OK / Grade C (Industry Average / Marginal High){C.RESET}"
        elif sus_score >= 51.0:
            return f"{C.YELLOW}Poor / Grade D (Marginal Low - Needs Improvement){C.RESET}"
        else:
            return f"{C.RED}Awful / Grade F (Not Acceptable - Critical Redesign Required){C.RESET}"


class TaskSessionTracker:
    """Pelacak metrik kinerja task kuantitatif (Time, Success, Errors, SEQ)."""

    def __init__(self, task_id: str, task_name: str):
        self.task_id = task_id
        self.task_name = task_name
        self.records: List[Dict] = []

    def add_participant_result(
        self,
        participant_id: str,
        completed: bool,
        duration_seconds: float,
        error_count: int,
        seq_score: int,
    ):
        if not (1 <= seq_score <= 7):
            raise ValueError("SEQ harus dalam rentang 1 (Sangat Sulit) hingga 7 (Sangat Mudah).")
        self.records.append(
            {
                "participant_id": participant_id,
                "completed": completed,
                "duration_seconds": duration_seconds,
                "error_count": error_count,
                "seq_score": seq_score,
            }
        )

    def compute_metrics(self) -> Dict:
        total = len(self.records)
        if total == 0:
            return {}

        success_count = sum(1 for r in self.records if r["completed"])
        success_rate = (success_count / total) * 100.0

        durations = [r["duration_seconds"] for r in self.records]
        avg_time = sum(durations) / total
        variance = sum((t - avg_time) ** 2 for t in durations) / (total if total == 1 else total - 1)
        std_time = math.sqrt(variance)

        total_errors = sum(r["error_count"] for r in self.records)
        avg_errors = total_errors / total

        seq_scores = [r["seq_score"] for r in self.records]
        avg_seq = sum(seq_scores) / total

        return {
            "total_participants": total,
            "success_rate": round(success_rate, 2),
            "mean_time_seconds": round(avg_time, 2),
            "std_time_seconds": round(std_time, 2),
            "total_errors": total_errors,
            "mean_errors": round(avg_errors, 2),
            "mean_seq": round(avg_seq, 2),
        }


def print_banner():
    print(f"\n{C.CYAN}{C.BOLD}{'=' * 75}{C.RESET}")
    print(f"{C.BG_BLUE}{C.BOLD}   UX RESEARCH LAB: USABILITY TESTING & QUANTITATIVE METRICS ENGINE   {C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'=' * 75}{C.RESET}")
    print(f"{C.DIM}Fondasi Metrik ISO 9241-11: Efektivitas, Efisiensi, & Kepuasan Pengguna{C.RESET}\n")


def run_benchmark_simulation():
    """Menjalankan skenario data Usability Testing benchmark industri (5 partisipan)."""
    print(f"{C.YELLOW}{C.BOLD}[1/2] Mensimulasikan Skenario Task: 'Pemesanan Tiket Express'{C.RESET}")

    task = TaskSessionTracker("T01", "Pemesanan Tiket Express")

    # Data simulasi 5 user Usability Testing
    sample_data = [
        ("User_01", True, 42.5, 0, 6),
        ("User_02", True, 58.0, 1, 5),
        ("User_03", False, 120.0, 3, 2),
        ("User_04", True, 49.2, 0, 7),
        ("User_05", True, 65.4, 2, 5),
    ]

    for p_id, comp, dur, err, seq in sample_data:
        task.add_participant_result(p_id, comp, dur, err, seq)
        status_color = C.GREEN if comp else C.RED
        status_text = "SUCCESS" if comp else "FAILED "
        print(
            f"  -> {C.BOLD}{p_id}{C.RESET} | Status: {status_color}{status_text}{C.RESET} | "
            f"Waktu: {dur:>5.1f}s | Errors: {err} | SEQ: {seq}/7"
        )

    metrics = task.compute_metrics()
    print(f"\n{C.CYAN}{C.BOLD}--- Ringkasan Metrik Task (T01) ---{C.RESET}")
    print(f"  • Task Completion Rate : {C.BOLD}{metrics['success_rate']}%{C.RESET} (Target standar >= 78%)")
    print(f"  • Mean Time on Task    : {metrics['mean_time_seconds']}s (± {metrics['std_time_seconds']}s)")
    print(f"  • Rata-rata Error/User : {metrics['mean_errors']} kesalahan")
    print(f"  • Rata-rata SEQ (1-7)  : {metrics['mean_seq']} / 7.0 (Benchmark kemudahan >= 5.5)\n")

    print(f"{C.YELLOW}{C.BOLD}[2/2] Evaluasi Kuesioner System Usability Scale (SUS){C.RESET}")
    # Respons 10 item kuesioner dari partisipan terpilih (skala 1-5)
    sample_sus_responses = {
        "User_01": [4, 1, 5, 2, 4, 1, 5, 1, 4, 2],
        "User_02": [4, 2, 4, 2, 4, 2, 4, 2, 4, 2],
        "User_04": [5, 1, 5, 1, 5, 1, 5, 1, 5, 1],
        "User_05": [3, 3, 3, 2, 4, 3, 3, 2, 3, 2],
    }

    sus_scores = []
    for user, answers in sample_sus_responses.items():
        score = SUSMetricCalculator.calculate_score(answers)
        sus_scores.append(score)
        rating_text = SUSMetricCalculator.get_adjective_rating(score)
        print(f"  • {user} SUS Score: {C.BOLD}{score:>5.1f}{C.RESET} -> {rating_text}")

    avg_sus = round(sum(sus_scores) / len(sus_scores), 2)
    print(f"\n{C.MAGENTA}{C.BOLD}==================================================================={C.RESET}")
    print(f"{C.BOLD}SKOR SUS KESELURUHAN (RATA-RATA): {C.CYAN}{avg_sus}{C.RESET} / 100")
    print(f"Kategori Adjektif: {SUSMetricCalculator.get_adjective_rating(avg_sus)}")
    print(f"Standar Benchmark Global: Rata-rata SUS industri perangkat lunak adalah 68.0")
    if avg_sus >= 68.0:
        print(f"{C.GREEN}{C.BOLD}[PASS] Usability memenuhi ambang batas kelayakan produk rilis!{C.RESET}")
    else:
        print(f"{C.RED}{C.BOLD}[ACTION REQUIRED] Skor di bawah 68.0, lakukan audit heuristik & revisi alur!{C.RESET}")
    print(f"{C.MAGENTA}{C.BOLD}==================================================================={C.RESET}\n")


def interactive_sus_calculator():
    """Mode interaktif untuk menghitung skor SUS secara mandiri."""
    print(f"\n{C.GREEN}{C.BOLD}>>> MODE INPUT INTERAKTIF KUESIONER SUS (10 Pertanyaan) <<<{C.RESET}")
    print(f"{C.DIM}Masukkan nilai skala Likert 1 (Sangat Tidak Setuju) s.d. 5 (Sangat Setuju):{C.RESET}\n")

    answers = []
    for q in SUSMetricCalculator.QUESTIONS:
        while True:
            try:
                raw_input = input(f"{C.BOLD}{q}{C.RESET}\nSkor (1-5): ").strip()
                val = int(raw_input)
                if 1 <= val <= 5:
                    answers.append(val)
                    break
                else:
                    print(f"{C.RED}Error: Nilai harus berupa bilangan bulat antara 1 dan 5!{C.RESET}")
            except (ValueError, EOFError):
                print(f"{C.RED}Input tidak valid. Menggunakan nilai default 3.{C.RESET}")
                answers.append(3)
                break

    score = SUSMetricCalculator.calculate_score(answers)
    print(f"\n{C.CYAN}{C.BOLD}--- Hasil Perhitungan SUS Interaktif ---{C.RESET}")
    print(f"Skor Akhir: {C.BOLD}{score}{C.RESET} / 100")
    print(f"Kategori  : {SUSMetricCalculator.get_adjective_rating(score)}\n")


def main():
    print_banner()

    # Jika dijalankan dengan argumen non-interaktif atau default
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_sus_calculator()
    else:
        run_benchmark_simulation()
        print(
            f"{C.DIM}Tips: Jalankan 'python3 hands-on/m01/lab_exercise.py --interactive' "
            f"untuk menginput skor kuesioner Anda sendiri.{C.RESET}\n"
        )


if __name__ == "__main__":
    main()
