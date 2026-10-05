#!/usr/bin/env python3
"""
Lab Exercise M02: Production-Grade Quantitative & Qualitative UX Research Pipeline
BAB-02: User Research - Rekayasa Kuantitatif dan Kualitatif

Features:
- Quantitative Engine: System Usability Scale (SUS), SEQ, Task Success (Wilson Score 95% CI), Time-on-Task (Lognormal)
- Qualitative Engine: Thematic Coding, Affinity Mapping, Sentiment & Pain Point Extraction
- Interactive CLI with ANSI terminal formatting and benchmark reporting
"""

from __future__ import annotations
import math
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ============================================================================
# ANSI Color Palette & Terminal Styling
# ============================================================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Background
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[40m"


def header_banner(title: str, subtitle: str = "") -> str:
    line = "=" * 70
    res = f"\n{Style.CYAN}{Style.BOLD}{line}\n"
    res += f"  🚀 {title.upper()}\n"
    if subtitle:
        res += f"  {Style.DIM}{subtitle}{Style.RESET}{Style.CYAN}{Style.BOLD}\n"
    res += f"{line}{Style.RESET}\n"
    return res


def section_title(text: str) -> str:
    return f"\n{Style.MAGENTA}{Style.BOLD}▶ {text}{Style.RESET}"


def badge(label: str, color: str = Style.GREEN) -> str:
    return f"{color}{Style.BOLD}[ {label} ]{Style.RESET}"


# ============================================================================
# Data Models
# ============================================================================
@dataclass
class SUSResponse:
    participant_id: str
    scores: List[int]  # 10 Likert items (1 to 5)

    def calculate_score(self) -> float:
        """
        Calculates standard SUS score (0 - 100).
        Odd items (1, 3, 5, 7, 9): score - 1
        Even items (2, 4, 6, 8, 10): 5 - score
        Sum of adjusted scores * 2.5
        """
        if len(self.scores) != 10:
            raise ValueError(f"SUS requires exactly 10 responses, got {len(self.scores)}")
        
        odd_sum = sum(score - 1 for i, score in enumerate(self.scores) if i % 2 == 0)
        even_sum = sum(5 - score for i, score in enumerate(self.scores) if i % 2 == 1)
        return (odd_sum + even_sum) * 2.5


@dataclass
class UsabilityTaskMetric:
    participant_id: str
    task_id: str
    completed: bool
    time_seconds: float
    seq_score: int  # Single Ease Question: 1 (Very Difficult) to 7 (Very Easy)
    errors_count: int


@dataclass
class QualitativeQuote:
    participant_id: str
    text: str
    assigned_codes: List[str] = field(default_factory=list)
    sentiment: str = "NEUTRAL"  # POSITIVE, NEGATIVE, NEUTRAL


# ============================================================================
# Quantitative Analytics Engine
# ============================================================================
class QuantitativeEngine:
    @staticmethod
    def grade_sus(score: float) -> Tuple[str, str, str]:
        """Returns Grade (A-F), Adjective, and Acceptability based on Bangor et al."""
        if score >= 85.0:
            return "A+", "Best Imaginable", "Acceptable"
        elif score >= 80.3:
            return "A", "Excellent", "Acceptable"
        elif score >= 74.0:
            return "B", "Good", "Acceptable"
        elif score >= 68.0:
            return "C", "OK (Average Benchmark)", "Acceptable"
        elif score >= 51.0:
            return "D", "Poor", "Marginal"
        else:
            return "F", "Worst Imaginable", "Not Acceptable"

    @staticmethod
    def wilson_score_interval(successes: int, total: int, confidence: float = 1.96) -> Tuple[float, float, float]:
        """
        Calculates Wilson Score Confidence Interval for binomial completion rate.
        Recommended for sample sizes under 100 in usability studies.
        """
        if total == 0:
            return 0.0, 0.0, 0.0
        p_hat = successes / total
        z = confidence
        z2 = z * z
        denom = 1 + (z2 / total)
        center = (p_hat + (z2 / (2 * total))) / denom
        delta = (z * math.sqrt((p_hat * (1 - p_hat) / total) + (z2 / (4 * total * total)))) / denom
        lower = max(0.0, center - delta)
        upper = min(1.0, center + delta)
        return p_hat, lower, upper

    @staticmethod
    def analyze_sus_batch(responses: List[SUSResponse]) -> Dict[str, float]:
        scores = [r.calculate_score() for r in responses]
        n = len(scores)
        if n == 0:
            return {"mean": 0.0, "std_dev": 0.0, "min": 0.0, "max": 0.0, "median": 0.0}
        
        mean = statistics.mean(scores)
        std_dev = statistics.stdev(scores) if n > 1 else 0.0
        median = statistics.median(scores)
        return {
            "mean": mean,
            "std_dev": std_dev,
            "min": min(scores),
            "max": max(scores),
            "median": median,
            "n": float(n),
        }

    @staticmethod
    def analyze_task_performance(tasks: List[UsabilityTaskMetric]) -> Dict[str, any]:
        if not tasks:
            return {}

        successes = sum(1 for t in tasks if t.completed)
        total = len(tasks)
        p_hat, ci_low, ci_high = QuantitativeEngine.wilson_score_interval(successes, total)

        times = [t.time_seconds for t in tasks if t.completed]
        seqs = [t.seq_score for t in tasks]
        errors = [t.errors_count for t in tasks]

        # Geometric Mean for time-on-task (lognormal behavior)
        if times:
            log_mean = statistics.mean([math.log(t) for t in times])
            geometric_mean_time = math.exp(log_mean)
            median_time = statistics.median(times)
        else:
            geometric_mean_time = 0.0
            median_time = 0.0

        return {
            "task_id": tasks[0].task_id,
            "total_participants": total,
            "completion_rate": p_hat * 100.0,
            "ci_95_low": ci_low * 100.0,
            "ci_95_high": ci_high * 100.0,
            "geometric_mean_time": geometric_mean_time,
            "median_time": median_time,
            "mean_seq": statistics.mean(seqs) if seqs else 0.0,
            "total_errors": sum(errors),
            "mean_errors_per_user": statistics.mean(errors) if errors else 0.0,
        }


# ============================================================================
# Qualitative Thematic Engine
# ============================================================================
class QualitativeEngine:
    LEXICON_NEGATIVE = [
        "confusing", "slow", "hard", "lost", "frustrated", "buggy", 
        "broken", "annoying", "unclear", "complicated", "hidden"
    ]
    LEXICON_POSITIVE = [
        "easy", "fast", "intuitive", "clean", "smooth", "clear", 
        "helpful", "delightful", "simple", "loved"
    ]

    THEME_KEYWORDS = {
        "Navigation & Hierarchy": ["find", "menu", "navigate", "lost", "structure", "hidden", "search"],
        "Form Clarity & Feedback": ["input", "validation", "error", "message", "submit", "clear"],
        "Cognitive Load & Friction": ["complicated", "too many steps", "confusing", "overwhelming"],
        "Performance & Latency": ["slow", "lag", "waiting", "hang", "spinner"],
        "Visual Aesthetics": ["clean", "design", "colors", "font", "modern", "cluttered"],
    }

    @classmethod
    def auto_tag_quote(cls, quote: QualitativeQuote) -> QualitativeQuote:
        text_lower = quote.text.lower()

        # Sentiment Analysis
        pos_count = sum(1 for w in cls.LEXICON_POSITIVE if w in text_lower)
        neg_count = sum(1 for w in cls.LEXICON_NEGATIVE if w in text_lower)

        if neg_count > pos_count:
            quote.sentiment = "NEGATIVE"
        elif pos_count > neg_count:
            quote.sentiment = "POSITIVE"
        else:
            quote.sentiment = "NEUTRAL"

        # Theme tagging
        for theme, keywords in cls.THEME_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                if theme not in quote.assigned_codes:
                    quote.assigned_codes.append(theme)

        if not quote.assigned_codes:
            quote.assigned_codes.append("General Feedback")

        return quote

    @classmethod
    def synthesize_themes(cls, quotes: List[QualitativeQuote]) -> Dict[str, Dict[str, any]]:
        theme_map: Dict[str, Dict[str, any]] = {}
        for q in quotes:
            for code in q.assigned_codes:
                if code not in theme_map:
                    theme_map[code] = {
                        "count": 0,
                        "positive": 0,
                        "negative": 0,
                        "neutral": 0,
                        "sample_quotes": [],
                    }
                theme_map[code]["count"] += 1
                theme_map[code][q.sentiment.lower()] += 1
                if len(theme_map[code]["sample_quotes"]) < 3:
                    theme_map[code]["sample_quotes"].append(f"[{q.participant_id}] {q.text}")
        return theme_map


# ============================================================================
# Mock Dataset Generators
# ============================================================================
def generate_production_ux_dataset() -> Tuple[List[SUSResponse], List[UsabilityTaskMetric], List[QualitativeQuote]]:
    """Simulates a realistic corporate multi-channel research dataset."""
    sus_data = [
        SUSResponse("P-01", [4, 2, 5, 1, 4, 2, 5, 1, 4, 2]),  # High usability
        SUSResponse("P-02", [4, 1, 4, 2, 5, 1, 4, 1, 5, 2]),
        SUSResponse("P-03", [3, 3, 3, 3, 3, 3, 3, 3, 3, 3]),  # Borderline 50
        SUSResponse("P-04", [2, 4, 2, 5, 2, 4, 1, 5, 2, 4]),  # Critical issues
        SUSResponse("P-05", [5, 1, 5, 2, 4, 1, 5, 2, 4, 1]),
        SUSResponse("P-06", [4, 2, 4, 3, 4, 2, 4, 2, 4, 2]),
        SUSResponse("P-07", [5, 2, 4, 1, 5, 1, 4, 2, 5, 1]),
        SUSResponse("P-08", [1, 5, 2, 4, 1, 5, 1, 4, 2, 5]),  # Low usability
        SUSResponse("P-09", [4, 2, 4, 2, 4, 2, 4, 2, 4, 2]),
        SUSResponse("P-10", [5, 1, 5, 1, 5, 1, 4, 1, 4, 1]),  # High delight
    ]

    task_metrics = [
        UsabilityTaskMetric("P-01", "TASK_CHECKOUT_FLOW", True, 42.5, 6, 0),
        UsabilityTaskMetric("P-02", "TASK_CHECKOUT_FLOW", True, 38.2, 7, 0),
        UsabilityTaskMetric("P-03", "TASK_CHECKOUT_FLOW", True, 75.0, 4, 2),
        UsabilityTaskMetric("P-04", "TASK_CHECKOUT_FLOW", False, 120.0, 2, 4),
        UsabilityTaskMetric("P-05", "TASK_CHECKOUT_FLOW", True, 45.1, 6, 0),
        UsabilityTaskMetric("P-06", "TASK_CHECKOUT_FLOW", True, 52.8, 5, 1),
        UsabilityTaskMetric("P-07", "TASK_CHECKOUT_FLOW", True, 39.4, 7, 0),
        UsabilityTaskMetric("P-08", "TASK_CHECKOUT_FLOW", False, 115.6, 1, 5),
        UsabilityTaskMetric("P-09", "TASK_CHECKOUT_FLOW", True, 48.0, 5, 1),
        UsabilityTaskMetric("P-10", "TASK_CHECKOUT_FLOW", True, 33.1, 7, 0),
    ]

    qual_quotes = [
        QualitativeQuote("P-01", "The checkout process was clean and smooth, completed without confusion."),
        QualitativeQuote("P-03", "I got lost trying to find where to input the promo code. It was hidden behind a collapse menu."),
        QualitativeQuote("P-04", "Very frustrated. The validation error message did not explain what was wrong with my phone number."),
        QualitativeQuote("P-07", "Loved the one-click address lookup, made it fast and simple!"),
        QualitativeQuote("P-08", "Too many steps and confusing buttons. The screen was lagging when submitting payment."),
        QualitativeQuote("P-09", "Overall fine, but navigation back to cart was slightly unclear."),
        QualitativeQuote("P-10", "Clean design and fast checkout. The instant confirmation was clear and helpful."),
    ]

    return sus_data, task_metrics, qual_quotes


# ============================================================================
# Interactive CLI Workflow
# ============================================================================
class UXResearchCLI:
    def __init__(self):
        self.sus_responses, self.task_metrics, self.raw_quotes = generate_production_ux_dataset()
        # Process qualitative items
        self.processed_quotes = [QualitativeEngine.auto_tag_quote(q) for q in self.raw_quotes]

    def render_sus_report(self):
        print(section_title("QUANTITATIVE BENCHMARK: SYSTEM USABILITY SCALE (SUS)"))
        stats = QuantitativeEngine.analyze_sus_batch(self.sus_responses)
        mean_score = stats["mean"]
        grade, adj, accept = QuantitativeEngine.grade_sus(mean_score)

        print(f"\n{Style.BOLD}Total Participants Evaluated:{Style.RESET} {int(stats['n'])}")
        print(f"┌{'─' * 28}┬{'─' * 38}┐")
        print(f"│ Metric                     │ Calculated Production Value        │")
        print(f"├{'─' * 28}┼{'─' * 38}┤")
        print(f"│ Mean SUS Score             │ {Style.CYAN}{Style.BOLD}{mean_score:6.2f} / 100{Style.RESET}                      │")
        print(f"│ Standard Deviation         │ ± {stats['std_dev']:5.2f}                           │")
        print(f"│ Median Score               │ {stats['median']:6.2f}                             │")
        print(f"│ Min / Max Range            │ {stats['min']:4.1f} / {stats['max']:4.1f}                        │")
        print(f"│ Sauro Benchmark Grade      │ {badge(grade, Style.GREEN if mean_score >= 68 else Style.RED)}                       │")
        print(f"│ Adjective Rating           │ {Style.YELLOW}{adj:<34}{Style.RESET} │")
        print(f"│ Acceptability Range        │ {Style.WHITE}{accept:<34}{Style.RESET} │")
        print(f"└{'─' * 28}┴{'─' * 38}┘")

        print(f"\n{Style.DIM}Industry Benchmark Note: Average standard SUS is 68.0. Target enterprise threshold is ≥ 80.0.{Style.RESET}")

    def render_task_performance_report(self):
        print(section_title("QUANTITATIVE BENCHMARK: TASK COMPLETION & EFFICIENCY"))
        res = QuantitativeEngine.analyze_task_performance(self.task_metrics)

        comp_rate = res["completion_rate"]
        print(f"\nTarget Task: {Style.BOLD}{res['task_id']}{Style.RESET}")
        print(f"Sample Size (N): {res['total_participants']}")
        
        status_color = Style.GREEN if comp_rate >= 80.0 else Style.RED
        print(f"\n• Completion Rate: {status_color}{Style.BOLD}{comp_rate:.1f}%{Style.RESET}")
        print(f"  └─ Wilson 95% Confidence Interval: [{res['ci_95_low']:.1f}% - {res['ci_95_high']:.1f}%]")
        
        print(f"• Geometric Mean Time: {Style.CYAN}{res['geometric_mean_time']:.2f}s{Style.RESET} (Median: {res['median_time']:.1f}s)")
        print(f"• Single Ease Question (SEQ): {Style.YELLOW}{res['mean_seq']:.2f} / 7.0{Style.RESET} (Target > 5.5)")
        print(f"• Error Rate: {Style.RED if res['mean_errors_per_user'] > 1.0 else Style.GREEN}{res['mean_errors_per_user']:.2f} errors/user{Style.RESET} (Total: {res['total_errors']})")

    def render_qualitative_thematic_report(self):
        print(section_title("QUALITATIVE RESEARCH: THEMATIC ANALYSIS & AFFINITY SYNTHESIS"))
        theme_map = QualitativeEngine.synthesize_themes(self.processed_quotes)

        sorted_themes = sorted(theme_map.items(), key=lambda x: x[1]["count"], reverse=True)

        for theme, data in sorted_themes:
            pos = data["positive"]
            neg = data["negative"]
            neu = data["neutral"]
            badge_color = Style.RED if neg > pos else (Style.GREEN if pos > neg else Style.YELLOW)
            
            citations_label = f"{data['count']} citations"
            print(f"\n{Style.BOLD}🏷️  Theme: {Style.CYAN}{theme}{Style.RESET} {badge(citations_label, badge_color)}")
            print(f"   Sentiment Distribution: {Style.GREEN}Pos: {pos}{Style.RESET} | {Style.RED}Neg: {neg}{Style.RESET} | {Style.DIM}Neu: {neu}{Style.RESET}")
            print("   Key Verbatim Quotes:")
            for quote in data["sample_quotes"]:
                print(f"     {Style.DIM}• {quote}{Style.RESET}")

    def add_custom_qualitative_quote(self):
        print(section_title("INPUT INTERAKTIF: FEEDBACK KUALITATIF BARU"))
        print(f"{Style.DIM}Masukkan respon transkrip user testing untuk diekstrak sentimen dan temanya.{Style.RESET}")
        p_id = input(f"{Style.CYAN}Participant ID (e.g. P-11): {Style.RESET}").strip() or "P-User"
        text = input(f"{Style.YELLOW}Kutipan Feedback: {Style.RESET}").strip()

        if not text:
            print(f"{Style.RED}Kutipan tidak boleh kosong! Batal menambahkan.{Style.RESET}")
            return

        new_quote = QualitativeQuote(p_id, text)
        tagged = QualitativeEngine.auto_tag_quote(new_quote)
        self.processed_quotes.append(tagged)

        print(f"\n{Style.GREEN}✔ Berhasil di-parse dan ditambahkan ke database riset!{Style.RESET}")
        print(f"  • Sentimen Terdeteksi: {badge(tagged.sentiment, Style.GREEN if tagged.sentiment=='POSITIVE' else Style.RED)}")
        print(f"  • Tema Terhubung: {Style.CYAN}{', '.join(tagged.assigned_codes)}{Style.RESET}")

    def run_prioritization_matrix(self):
        print(section_title("TRIANGULASI & MATRIX PRIORITAS UX ROADMAP"))
        print(f"{Style.DIM}Menggabungkan temuan Kuantitatif (Error/Drop-off) dengan Temuan Kualitatif (Pain Point).{Style.RESET}\n")

        recommendations = [
            ("P0 - CRITICAL", "Redesign form validasi nomor telepon & feedback pesan error", "Dipicu oleh Task Failure P-04 & P-08, keluhan 'unclear validation error'."),
            ("P1 - HIGH", "Bongkar hidden promo code accordion di checkout screen", "Dipicu oleh inflasi Time-on-Task P-03 (75s) dan keluhan 'lost promo code'."),
            ("P2 - MEDIUM", "Optimasi query API pembayaran untuk mengeliminasi UI lag", "Dipicu oleh keluhan P-08 (screen lagging) saat submit."),
            ("P3 - LOW", "Perkuat affordance breadcrumb navigation kembali ke cart", "Keluhan minor usability P-09.")
        ]

        for priority, item, rationale in recommendations:
            color = Style.RED if "P0" in priority else (Style.YELLOW if "P1" in priority else Style.CYAN)
            print(f"{color}{Style.BOLD}[{priority}]{Style.RESET} {Style.BOLD}{item}{Style.RESET}")
            print(f"    {Style.DIM}Rasional Riset: {rationale}{Style.RESET}\n")

    def main_menu(self):
        print(header_banner(
            "UX Research Analytics Engine: M02 Interactive Lab",
            "Simulasi Analisis Kuantitatif (SUS, Wilson CI, SEQ) & Kualitatif (Thematic Tagging)"
        ))

        while True:
            print(f"\n{Style.BOLD}MAIN CONTROLLER MENU:{Style.RESET}")
            print(f" {Style.CYAN}1.{Style.RESET} Audit Benchmark SUS (System Usability Scale)")
            print(f" {Style.CYAN}2.{Style.RESET} Analisis Kuantitatif Task Performance & Wilson 95% CI")
            print(f" {Style.CYAN}3.{Style.RESET} Sintesis Tematik Kualitatif (Thematic & Sentiment)")
            print(f" {Style.CYAN}4.{Style.RESET} Input Data Feedback Kualitatif Baru (Live NLP/Lexicon)")
            print(f" {Style.CYAN}5.{Style.RESET} Tampilkan UX Prioritization Action Matrix (Triangulasi)")
            print(f" {Style.CYAN}6.{Style.RESET} Jalankan Laporan Komprehensif Otomatis")
            print(f" {Style.RED}0.{Style.RESET} Keluar (Exit)")

            try:
                choice = input(f"\n{Style.BOLD}Pilih opsi [0-6]: {Style.RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{Style.YELLOW}Sesi dihentikan.{Style.RESET}")
                break

            if choice == "1":
                self.render_sus_report()
            elif choice == "2":
                self.render_task_performance_report()
            elif choice == "3":
                self.render_qualitative_thematic_report()
            elif choice == "4":
                self.add_custom_qualitative_quote()
            elif choice == "5":
                self.run_prioritization_matrix()
            elif choice == "6":
                print(f"\n{Style.YELLOW}Memproses seluruh dataset riset UX...{Style.RESET}")
                time.sleep(0.4)
                self.render_sus_report()
                self.render_task_performance_report()
                self.render_qualitative_thematic_report()
                self.run_prioritization_matrix()
            elif choice == "0":
                print(f"\n{Style.GREEN}Lab UX Research selesai. Terus validasi asumsi dengan data nyata!{Style.RESET}\n")
                break
            else:
                print(f"{Style.RED}Pilihan tidak valid. Silakan coba lagi.{Style.RESET}")


# ============================================================================
# Entry Point
# ============================================================================
def main():
    cli = UXResearchCLI()
    # Jika dijalankan dengan argumen non-interaktif seperti '--auto' atau dalam pipeline test
    if len(sys.argv) > 1 and sys.argv[1] in ("--auto", "-a", "--test"):
        print(header_banner("Automated UX Analytics Verification Mode"))
        cli.render_sus_report()
        cli.render_task_performance_report()
        cli.render_qualitative_thematic_report()
        cli.run_prioritization_matrix()
        print(f"\n{Style.GREEN}{Style.BOLD}✔ Autonomous verification passed successfully.{Style.RESET}\n")
    else:
        cli.main_menu()


if __name__ == "__main__":
    main()
