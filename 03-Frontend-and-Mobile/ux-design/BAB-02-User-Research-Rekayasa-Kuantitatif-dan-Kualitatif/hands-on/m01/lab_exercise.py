#!/usr/bin/env python3
"""
Lab Exercise M01: Quantitative & Qualitative UX Research Engine
BAB-02: User Research Rekayasa Kuantitatif dan Kualitatif

Modul ini mensimulasikan pemrosesan metrik riset UX secara komprehensif:
1. System Usability Scale (SUS) dengan curved percentile benchmarking (Sauro-Lewis).
2. Task Completion Rate dengan Wilson Score Confidence Interval 95%.
3. Time on Task (Geometric Mean & Log-Normal Statistics).
4. Qualitative Thematic Coding Engine & Code Co-occurrence Matrix.
"""

from __future__ import annotations
import math
import statistics
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


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


@dataclass
class SUSResponse:
    participant_id: str
    scores: List[int]  # 10 item skala Likert (1 - 5)

    def calculate_score(self) -> float:
        """
        Menghitung skor SUS standar (0 - 100):
        - Item ganjil (1, 3, 5, 7, 9): skor - 1
        - Item genap (2, 4, 6, 8, 10): 5 - skor
        - Total kontribusi dikalikan 2.5
        """
        if len(self.scores) != 10:
            raise ValueError("SUS membutuhkan tepat 10 pertanyaan Likert.")
        
        odd_sum = sum(score - 1 for score in self.scores[0::2])
        even_sum = sum(5 - score for score in self.scores[1::2])
        return (odd_sum + even_sum) * 2.5


@dataclass
class TaskMetric:
    participant_id: str
    task_id: str
    completed: bool
    duration_seconds: float
    seq_score: int  # Single Ease Question 1-7


class QuantitativeEngine:
    @staticmethod
    def sus_grade_and_percentile(score: float) -> Tuple[str, str, float]:
        """
        Sauro-Lewis Grade Scale & Percentile Rank
        Mengembalikan: (Grade, Adjective Rating, Estimated Percentile)
        """
        if score >= 84.1:
            return "A+", "Best Imaginable", 96.0
        elif score >= 80.3:
            return "A", "Excellent", 90.0
        elif score >= 74.0:
            return "B", "Good", 70.0
        elif score >= 68.0:
            return "C", "Average (Industry Benchmark)", 50.0
        elif score >= 51.7:
            return "D", "Poor / Marginal", 20.0
        else:
            return "F", "Unacceptable", 5.0

    @staticmethod
    def wilson_score_interval(successes: int, total: int, confidence: float = 1.96) -> Tuple[float, float, float]:
        """
        Menghitung Task Completion Rate menggunakan Wilson Score Interval untuk sample UX kecil.
        Confidence z=1.96 merepresentasikan interval kepercayaan 95%.
        """
        if total == 0:
            return 0.0, 0.0, 0.0
        
        p_hat = successes / total
        z = confidence
        z2 = z * z
        denominator = 1 + z2 / total
        center = (p_hat + z2 / (2 * total)) / denominator
        margin = (z * math.sqrt((p_hat * (1 - p_hat) + z2 / (4 * total)) / total)) / denominator
        
        ci_lower = max(0.0, center - margin)
        ci_upper = min(1.0, center + margin)
        return p_hat, ci_lower, ci_upper

    @staticmethod
    def geometric_mean(durations: List[float]) -> float:
        """
        Data waktu tugas selalu miring (skewed). Standar ISO 9241-11 & Sauro-Lewis merekomendasikan
        Geometric Mean atau median daripada rata-rata aritmatika biasa.
        """
        if not durations:
            return 0.0
        log_sum = sum(math.log(max(0.1, d)) for d in durations)
        return math.exp(log_sum / len(durations))


@dataclass
class QualitativeObservation:
    session_id: str
    quote: str
    codes: List[str]
    sentiment: str  # POSITIVE, NEGATIVE, NEUTRAL


class QualitativeMatrixEngine:
    def __init__(self):
        self.observations: List[QualitativeObservation] = []

    def add_observation(self, obs: QualitativeObservation) -> None:
        self.observations.append(obs)

    def generate_code_frequency(self) -> Dict[str, int]:
        freq: Dict[str, int] = {}
        for obs in self.observations:
            for code in obs.codes:
                freq[code] = freq.get(code, 0) + 1
        return dict(sorted(freq.items(), key=lambda item: item[1], reverse=True))

    def generate_co_occurrence(self) -> Dict[Tuple[str, str], int]:
        co_occur: Dict[Tuple[str, str], int] = {}
        for obs in self.observations:
            unique_codes = sorted(list(set(obs.codes)))
            for i in range(len(unique_codes)):
                for j in range(i + 1, len(unique_codes)):
                    pair = (unique_codes[i], unique_codes[j])
                    co_occur[pair] = co_occur.get(pair, 0) + 1
        return dict(sorted(co_occur.items(), key=lambda item: item[1], reverse=True))


def render_header() -> None:
    print(f"\n{ANSI.BG_BLUE}{ANSI.WHITE}{ANSI.BOLD} ========================================================================= {ANSI.RESET}")
    print(f"{ANSI.BG_BLUE}{ANSI.WHITE}{ANSI.BOLD}   UX RESEARCH LAB: REKAYASA KUANTITATIF & KUALITATIF (BAB-02 M01)        {ANSI.RESET}")
    print(f"{ANSI.BG_BLUE}{ANSI.WHITE}{ANSI.BOLD} ========================================================================= {ANSI.RESET}\n")


def run_simulation() -> None:
    render_header()

    # 1. Dataset SUS (12 Partisipan Tes Usabilitas)
    raw_sus_data = [
        ("P01", [4, 2, 5, 1, 4, 2, 5, 2, 4, 1]),
        ("P02", [5, 1, 4, 2, 4, 1, 5, 1, 5, 2]),
        ("P03", [3, 3, 3, 3, 4, 2, 3, 2, 4, 3]),
        ("P04", [4, 1, 4, 2, 5, 1, 4, 2, 5, 1]),
        ("P05", [2, 4, 3, 4, 2, 5, 2, 4, 3, 5]),
        ("P06", [5, 1, 5, 1, 5, 2, 5, 1, 5, 1]),
        ("P07", [4, 2, 4, 3, 4, 2, 4, 2, 3, 2]),
        ("P08", [3, 4, 2, 4, 3, 4, 2, 5, 2, 4]),
        ("P09", [5, 2, 5, 1, 4, 1, 5, 2, 4, 2]),
        ("P10", [4, 1, 5, 2, 4, 2, 4, 1, 5, 2]),
        ("P11", [4, 2, 4, 2, 3, 2, 4, 3, 4, 2]),
        ("P12", [5, 1, 5, 1, 4, 2, 5, 1, 5, 1]),
    ]

    sus_responses = [SUSResponse(pid, scores) for pid, scores in raw_sus_data]
    sus_scores = [resp.calculate_score() for resp in sus_responses]
    mean_sus = statistics.mean(sus_scores)
    median_sus = statistics.median(sus_scores)
    std_sus = statistics.stdev(sus_scores)
    grade, adj, percentile = QuantitativeEngine.sus_grade_and_percentile(mean_sus)

    print(f"{ANSI.CYAN}{ANSI.BOLD}[1] ANALISIS SYSTEM USABILITY SCALE (SUS){ANSI.RESET}")
    print(f"    Jumlah Sampel (N)      : {len(sus_responses)} partisipan")
    print(f"    Rata-rata Skor SUS     : {ANSI.BOLD}{mean_sus:.2f}{ANSI.RESET} / 100")
    print(f"    Median Skor SUS        : {median_sus:.2f}")
    print(f"    Standar Deviasi        : {std_sus:.2f}")
    print(f"    Sauro-Lewis Grade      : {ANSI.GREEN}{ANSI.BOLD}{grade}{ANSI.RESET}")
    print(f"    Adjective Rating       : {ANSI.YELLOW}{adj}{ANSI.RESET}")
    print(f"    Percentile Rank        : {ANSI.MAGENTA}{percentile:.1f}%{ANSI.RESET}")
    
    # Visual Bar SUS
    bar_length = int(mean_sus / 2.5)
    bar_str = "█" * bar_length + "░" * (40 - bar_length)
    print(f"    Benchmark Visual       : [{ANSI.GREEN}{bar_str}{ANSI.RESET}] ({mean_sus:.1f}/100)\n")

    # 2. Analisis Task Performance (Completion Rate & Time on Task)
    task_records = [
        TaskMetric("P01", "T01-Checkout", True, 45.2, 6),
        TaskMetric("P02", "T01-Checkout", True, 38.0, 7),
        TaskMetric("P03", "T01-Checkout", True, 62.5, 5),
        TaskMetric("P04", "T01-Checkout", True, 41.1, 7),
        TaskMetric("P05", "T01-Checkout", False, 120.0, 2),
        TaskMetric("P06", "T01-Checkout", True, 33.4, 7),
        TaskMetric("P07", "T01-Checkout", True, 52.8, 5),
        TaskMetric("P08", "T01-Checkout", False, 110.0, 2),
        TaskMetric("P09", "T01-Checkout", True, 39.5, 6),
        TaskMetric("P10", "T01-Checkout", True, 44.0, 6),
        TaskMetric("P11", "T01-Checkout", True, 58.1, 5),
        TaskMetric("P12", "T01-Checkout", True, 35.6, 7),
    ]

    total_tasks = len(task_records)
    successful_tasks = sum(1 for t in task_records if t.completed)
    p_hat, ci_low, ci_high = QuantitativeEngine.wilson_score_interval(successful_tasks, total_tasks)
    
    successful_durations = [t.duration_seconds for t in task_records if t.completed]
    geom_mean_duration = QuantitativeEngine.geometric_mean(successful_durations)
    arithmetic_mean = statistics.mean(successful_durations)
    avg_seq = statistics.mean(t.seq_score for t in task_records)

    print(f"{ANSI.CYAN}{ANSI.BOLD}[2] ANALISIS EFISIENSI & EFEKTIVITAS TUGAS (T01-Checkout){ANSI.RESET}")
    print(f"    Tingkat Keberhasilan   : {ANSI.BOLD}{p_hat * 100:.1f}%{ANSI.RESET} ({successful_tasks}/{total_tasks})")
    print(f"    Wilson Score CI (95%)  : {ANSI.YELLOW}[{ci_low * 100:.1f}% s/d {ci_high * 100:.1f}%]{ANSI.RESET}")
    print(f"    Waktu Tugas (Mean Geo) : {ANSI.BOLD}{geom_mean_duration:.1f} detik{ANSI.RESET} (Anti-bias skew)")
    print(f"    Waktu Tugas (Mean Arit): {arithmetic_mean:.1f} detik")
    print(f"    Single Ease Question   : {ANSI.BOLD}{avg_seq:.2f}{ANSI.RESET} / 7.0 (Threshold > 5.5 = Mudah)\n")

    # 3. Kualitatif: Thematic Coding & Matrix Engine
    qual_engine = QualitativeMatrixEngine()
    qual_engine.add_observation(QualitativeObservation("S01", "Saya bingung tombol bayar tertutup banner promosi", ["UI_OBSTRUCTION", "CHECKOUT_FLOW"], "NEGATIVE"))
    qual_engine.add_observation(QualitativeObservation("S02", "Proses verifikasi OTP sangat cepat dan mulus", ["OTP_AUTH", "PERFORMANCE"], "POSITIVE"))
    qual_engine.add_observation(QualitativeObservation("S03", "Form alamat terlalu panjang dan tidak ada auto-fill", ["FORM_COMPLEXITY", "CHECKOUT_FLOW"], "NEGATIVE"))
    qual_engine.add_observation(QualitativeObservation("S04", "Saya tidak melihat opsi pengiriman instan", ["DISCOVERABILITY", "LOGISTICS"], "NEGATIVE"))
    qual_engine.add_observation(QualitativeObservation("S05", "Voucher otomatis terpasang saat pembayaran, sangat membantu", ["PROMO_SYSTEM", "CHECKOUT_FLOW"], "POSITIVE"))
    qual_engine.add_observation(QualitativeObservation("S06", "Validasi form error baru muncul setelah tombol submit ditekan", ["FORM_COMPLEXITY", "ERROR_PREVENTION"], "NEGATIVE"))
    qual_engine.add_observation(QualitativeObservation("S07", "Font teks ketentuan pembayaran terlalu kecil dan kontrasnya rendah", ["ACCESSIBILITY", "CHECKOUT_FLOW"], "NEGATIVE"))

    print(f"{ANSI.CYAN}{ANSI.BOLD}[3] ANALISIS KUALITATIF: THEMATIC CODING & PAIR CO-OCCURRENCE{ANSI.RESET}")
    code_freq = qual_engine.generate_code_frequency()
    print(f"    {ANSI.WHITE}{ANSI.BOLD}Distribusi Frekuensi Kode Temuan:{ANSI.RESET}")
    for code, count in code_freq.items():
        bar = "▓" * (count * 3)
        print(f"      • {code:<18} : {ANSI.MAGENTA}{count:2d}{ANSI.RESET} | {bar}")

    co_occur = qual_engine.generate_co_occurrence()
    print(f"\n    {ANSI.WHITE}{ANSI.BOLD}Matriks Ko-okurensi Kode (Pola Titik Temu Isu):{ANSI.RESET}")
    for (c1, c2), count in list(co_occur.items())[:4]:
        print(f"      • [{c1}] <---> [{c2}] : {ANSI.YELLOW}{count} korelasi sesi{ANSI.RESET}")

    # Rekomendasi Sintesis UX
    print(f"\n{ANSI.BG_MAGENTA}{ANSI.WHITE}{ANSI.BOLD} --- KESIMPULAN REKAYASA RISET UX --- {ANSI.RESET}")
    print(f"1. SUS {mean_sus:.1f} berada pada rentang {grade} ({adj}). Sistem dinilai layak secara industri.")
    print(f"2. Titik friksi terbesar terpusat pada tema {ANSI.RED}'CHECKOUT_FLOW'{ANSI.RESET} yang berkorelasi kuat dengan 'FORM_COMPLEXITY'.")
    print(f"3. Rekomendasi mitigasi: Implementasikan inline-validation dan address auto-fill untuk memangkas waktu tugas ke bawah 40 detik.")
    print(f"{ANSI.GREEN}Simulasi UX Research Engine selesai dieksekusi dengan sukses.{ANSI.RESET}\n")


if __name__ == "__main__":
    run_simulation()
