#!/usr/bin/env python3
"""
Interactive Lab Exercise: BAB 02 - User Research & Problem Discovery
Simulation & Analysis Tool for Qualitative Research Synthesis,
Affinity Mapping, JTBD Formulation, and Problem Statement Scoping.
"""

import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict

# ANSI Color Codes for Terminal Styling
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
class InterviewNote:
    id: int
    participant: str
    quote: str
    category: str  # Say, Do, Think, Feel
    friction_level: int  # 1 (Low) - 5 (Critical)


@dataclass
class JTBDStatement:
    when: str
    want_to: str
    so_that: str


@dataclass
class ResearchCluster:
    theme: str
    notes: List[InterviewNote] = field(default_factory=list)
    impact_score: float = 0.0
    urgency_score: float = 0.0


SAMPLE_NOTES = [
    InterviewNote(
        id=1,
        participant="Participant P01 (SME Owner)",
        quote="Saya bingung harus klik ke mana setelah upload invoice, tidak ada konfirmasi sukses.",
        category="Say",
        friction_level=4,
    ),
    InterviewNote(
        id=2,
        participant="Participant P02 (Staff Finance)",
        quote="Sering bolak-balik buka spreadsheet manual untuk memvalidasi nomor rekening vendor.",
        category="Do",
        friction_level=5,
    ),
    InterviewNote(
        id=3,
        participant="Participant P01 (SME Owner)",
        quote="Takut kalau transaksi salah kirim dan uang perusahaan hilang tanpa jejak audit.",
        category="Feel",
        friction_level=5,
    ),
    InterviewNote(
        id=4,
        participant="Participant P03 (Freelancer)",
        quote="Saya merasa proses rekonsiliasi akhir bulan memakan waktu weekend keluarga saya.",
        category="Think",
        friction_level=4,
    ),
    InterviewNote(
        id=5,
        participant="Participant P02 (Staff Finance)",
        quote="Menghabiskan 3 jam hanya untuk download rekapan bank satu per satu.",
        category="Do",
        friction_level=4,
    ),
]


def print_header(title: str):
    print(f"\n{BOLD}{BG_BLUE}{WHITE}  === {title} ===  {RESET}\n")


def display_empathy_map(notes: List[InterviewNote]):
    print_header("EMPATHY MAP MATRIX (SAY - DO - THINK - FEEL)")
    quadrants = {"Say": [], "Do": [], "Think": [], "Feel": []}
    for n in notes:
        quadrants[n.category].append(n)

    for quad, items in quadrants.items():
        color = CYAN if quad in ["Say", "Do"] else MAGENTA
        print(f"{BOLD}{color}[ {quad.upper()} ]{RESET} ({len(items)} observasi)")
        for item in items:
            severity = f"{RED}{'★' * item.friction_level}{DIM}{'★' * (5 - item.friction_level)}{RESET}"
            print(f"  • {BOLD}{item.participant}{RESET}: \"{item.quote}\" | Friction: {severity}")
        print()


def run_affinity_clustering(notes: List[InterviewNote]) -> Dict[str, ResearchCluster]:
    print_header("AFFINITY DIAGRAMMING & THEMATIC CLUSTERING")
    print(f"{DIM}Mengelompokkan data kualitatif mentah menjadi tema temuan inti...{RESET}\n")

    clusters = {
        "Feedback & Transparency Friction": ResearchCluster(
            theme="Feedback & Transparency Friction",
            impact_score=4.2,
            urgency_score=4.0,
        ),
        "Manual Repetitive Workflow": ResearchCluster(
            theme="Manual Repetitive Workflow",
            impact_score=4.8,
            urgency_score=4.6,
        ),
        "Psychological Anxiety & Trust": ResearchCluster(
            theme="Psychological Anxiety & Trust",
            impact_score=4.5,
            urgency_score=4.2,
        ),
    }

    # Grouping logic
    for n in notes:
        if n.id == 1:
            clusters["Feedback & Transparency Friction"].notes.append(n)
        elif n.id in [2, 5]:
            clusters["Manual Repetitive Workflow"].notes.append(n)
        elif n.id in [3, 4]:
            clusters["Psychological Anxiety & Trust"].notes.append(n)

    for theme, cluster in clusters.items():
        print(f"{BOLD}{YELLOW}Cluster Theme: {theme}{RESET}")
        print(f"  {CYAN}Priority Index:{RESET} Impact={cluster.impact_score}/5.0 | Urgency={cluster.urgency_score}/5.0")
        print(f"  Jumlah Bukti Lapangan: {len(cluster.notes)} kutipan:")
        for n in cluster.notes:
            print(f"    - [{n.category}] \"{n.quote}\" ({n.participant})")
        print()

    return clusters


def synthesize_jtbd() -> JTBDStatement:
    print_header("JOBS TO BE DONE (JTBD) FRAMEWORK")
    jtbd = JTBDStatement(
        when="Ketika mengelola pembukuan akhir bulan dan rekonsiliasi multi-vendor",
        want_to="Mengotomatisasi verifikasi akun vendor dan validasi invoice sekali klik",
        so_that="Saya terbebas dari kesalahan audit manual dan dapat pulang tepat waktu tanpa kecemasan operasional",
    )
    print(f"{BOLD}{GREEN}Core Job Formulation:{RESET}")
    print(f"  {BOLD}WHEN{RESET}    : {CYAN}{jtbd.when}{RESET}")
    print(f"  {BOLD}WANT TO{RESET} : {YELLOW}{jtbd.want_to}{RESET}")
    print(f"  {BOLD}SO THAT{RESET} : {GREEN}{jtbd.so_that}{RESET}\n")
    return jtbd


def formulate_problem_statement(cluster: ResearchCluster, jtbd: JTBDStatement):
    print_header("POINT OF VIEW (POV) PROBLEM STATEMENT")
    user = "Finance Team & SME Business Owners"
    need = "sistem rekonsiliasi cerdas dengan audit trail real-time dan otomasi batching"
    insight = "kecemasan terbesar bukan pada kecepatan software, melainkan ketakutan kehilangan uang akibat eror input data manual tanpa safety net"

    print(f"{BOLD}User Persona :{RESET} {WHITE}{user}{RESET}")
    print(f"{BOLD}User Need    :{RESET} {CYAN}{need}{RESET}")
    print(f"{BOLD}Key Insight  :{RESET} {YELLOW}{insight}{RESET}\n")

    print(f"{BOLD}{GREEN}Final POV Statement:{RESET}")
    print(f'"{BOLD}{WHITE}{user}{RESET} membutuhkan {BOLD}{CYAN}{need}{RESET} karena {BOLD}{YELLOW}{insight}{RESET}."\n')


def interactive_prioritization_matrix():
    print_header("PRIORITIZATION MATRIX (OPPORTUNITY SCORING)")
    opportunities = [
        {"feature": "Otomasi Rekonsiliasi Bank API", "impact": 9, "effort": 6},
        {"feature": "Banner Notifikasi Status Upload Real-time", "impact": 6, "effort": 2},
        {"feature": "Audit Trail Log & Rollback Transaksi", "impact": 8, "effort": 5},
        {"feature": "Custom Theme Dark Mode Dashboard", "impact": 3, "effort": 4},
    ]

    print(f"{BOLD}{'Inisiatif Desain Solusi':<40} | {'Impact (1-10)':<13} | {'Effort (1-10)':<13} | {'Kuadran Rekomendasi'}{RESET}")
    print("-" * 95)
    for opp in opportunities:
        imp, eff = opp["impact"], opp["effort"]
        if imp >= 7 and eff <= 6:
            quadrant = f"{GREEN}{BOLD}QUICK WIN / HIGH VALUE{RESET}"
        elif imp >= 7 and eff > 6:
            quadrant = f"{YELLOW}STRATEGIC / BIG BET{RESET}"
        elif imp < 7 and eff <= 4:
            quadrant = f"{CYAN}LOW HANGING FRUIT{RESET}"
        else:
            quadrant = f"{RED}DE-PRIORITIZE / DROP{RESET}"

        print(f"{opp['feature']:<40} | {imp:<13} | {eff:<13} | {quadrant}")
    print()


def show_menu():
    print(f"{BOLD}{CYAN}=== MENU SIMULASI USER RESEARCH & PROBLEM DISCOVERY ==={RESET}")
    print(f"1. Tampilkan Empathy Map Matrix (Say / Do / Think / Feel)")
    print(f"2. Jalankan Affinity Diagramming & Thematic Clustering")
    print(f"3. Rumuskan Jobs To Be Done (JTBD) Statement")
    print(f"4. Sintesis Point of View (POV) & Problem Statement")
    print(f"5. Evaluasi Prioritization Matrix (Impact vs Effort)")
    print(f"6. Jalankan Seluruh Pipeline Riset (End-to-End Walkthrough)")
    print(f"0. Keluar")
    print("-" * 55)


def run_all():
    display_empathy_map(SAMPLE_NOTES)
    clusters = run_affinity_clustering(SAMPLE_NOTES)
    jtbd = synthesize_jtbd()
    formulate_problem_statement(clusters["Manual Repetitive Workflow"], jtbd)
    interactive_prioritization_matrix()
    print(f"{BOLD}{GREEN}✓ Pipeline riset dan sintesis problem discovery berhasil dieksekusi.{RESET}\n")


def main():
    # If launched non-interactively or with argument '--demo' or '--all'
    if not sys.stdin.isatty() or "--demo" in sys.argv or "--all" in sys.argv:
        print(f"{BOLD}{MAGENTA}[Mode Non-Interaktif / Otomatis Terdeteksi]{RESET}")
        run_all()
        return

    while True:
        show_menu()
        try:
            choice = input(f"{BOLD}Pilih opsi [0-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            display_empathy_map(SAMPLE_NOTES)
        elif choice == "2":
            run_affinity_clustering(SAMPLE_NOTES)
        elif choice == "3":
            synthesize_jtbd()
        elif choice == "4":
            clusters = run_affinity_clustering(SAMPLE_NOTES)
            jtbd = synthesize_jtbd()
            formulate_problem_statement(clusters["Manual Repetitive Workflow"], jtbd)
        elif choice == "5":
            interactive_prioritization_matrix()
        elif choice == "6":
            run_all()
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menggunakan User Research Lab Simulator.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}\n")


if __name__ == "__main__":
    main()
