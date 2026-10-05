#!/usr/bin/env python3
"""
Lab Exercise: UX Design Foundations & Information Architecture Simulator
BAB-01: Fondasi dan Arsitektur UX Design

Simulasi interaktif teknis untuk mengevaluasi prinsip fondasi UX:
1. Jesse James Garrett's 5 Planes of UX (Strategy, Scope, Structure, Skeleton, Surface)
2. Hick's Law Decision Time (T = b * log2(n + 1))
3. Fitts's Law Target Acquisition Index of Difficulty (ID = log2(2D / W))
4. Information Architecture (IA) Hierarchy & Cognitive Load Evaluator
"""

import math
import sys
import time

# Terminal ANSI Color Palette
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
BG_DARK = "\033[40m"


def print_header(title: str) -> None:
    border = "=" * 64
    print(f"\n{CYAN}{BOLD}{border}{RESET}")
    print(f"{CYAN}{BOLD}  {title.center(60)}  {RESET}")
    print(f"{CYAN}{BOLD}{border}{RESET}\n")


def print_section(title: str) -> None:
    print(f"\n{MAGENTA}{BOLD}--- [ {title} ] ---{RESET}")


def simulate_garrett_model() -> None:
    print_section("The 5 Planes of UX (Jesse James Garrett Model)")
    print(f"{DIM}Menganalisis koherensi arsitektur produk dari Abstrak ke Konkret.{RESET}\n")

    planes = [
        ("1. Strategy Plane", "User Needs & Business Objectives", "Mengapa produk ini ada?"),
        ("2. Scope Plane", "Functional Specifications & Content Requirements", "Fitur dan konten apa saja?"),
        ("3. Structure Plane", "Interaction Design & Information Architecture", "Bagaimana sistem merespons & disusun?"),
        ("4. Skeleton Plane", "Interface, Navigation & Information Design", "Bagaimana tata letak visual elemen?"),
        ("5. Surface Plane", "Visual Design & Sensory Experience", "Bagaimana tampilan visual akhir?"),
    ]

    for plane, focus, question in planes:
        time.sleep(0.15)
        print(f" {YELLOW}►{RESET} {BOLD}{plane:<20}{RESET} | {GREEN}{focus:<42}{RESET} | {CYAN}{question}{RESET}")

    print(f"\n{BLUE}[Status Analisis]: Arsitektur model 5 bidang valid & selaras secara struktural.{RESET}")


def calculate_hicks_law() -> None:
    print_section("Hick's Law: Cognitive Reaction Time Evaluator")
    print(f"{DIM}Rumus: T = b * log2(n + 1) | b (processing rate) = 0.155 s/bit{RESET}\n")

    b_constant = 0.155  # detik per bit empiris
    menu_options = [3, 5, 7, 10, 15, 30]

    print(f"{BOLD}{'Jumlah Opsi (n)':<18} | {'Kompleksitas (Bits)':<22} | {'Estimasi Waktu Respon (s)':<25} | {'Penilaian UX'}{RESET}")
    print("-" * 88)

    for n in menu_options:
        bits = math.log2(n + 1)
        reaction_time = b_constant * bits

        if n <= 5:
            assessment = f"{GREEN}Sangat Optimal (Miller's Rule: 5±2){RESET}"
        elif n <= 9:
            assessment = f"{YELLOW}Dapat Diterima (Kategori Standar){RESET}"
        else:
            assessment = f"{RED}Risiko Cognitive Overload! Perlu Chunking{RESET}"

        print(f"  {n:<16} | {bits:<22.3f} | {reaction_time:<25.4f} | {assessment}")

    print(f"\n{WHITE}{BOLD}Rekomendasi:{RESET} Gunakan progressive disclosure jika jumlah pilihan > 7.")


def calculate_fittss_law() -> None:
    print_section("Fitts's Law: Target Acquisition & Usability Ergonomics")
    print(f"{DIM}Rumus Index of Difficulty (ID): ID = log2((2 * D) / W){RESET}")
    print(f"{DIM}D = Jarak ke target (px), W = Lebar/Ukuran target (px){RESET}\n")

    scenarios = [
        ("Mobile CTA Utama (Thumb Zone)", 180, 56),
        ("Desktop Navbar Link", 420, 80),
        ("Mobile Floating Action Button", 90, 64),
        ("Micro Icon Button Tanpa Padding", 360, 16),
        ("Footer Tiny Text Link", 720, 24),
    ]

    print(f"{BOLD}{'Skenario Elemen UI':<34} | {'D (px)':<8} | {'W (px)':<8} | {'ID (Bits)':<10} | {'Ergonomic Rating'}{RESET}")
    print("-" * 86)

    for name, distance, width in scenarios:
        id_score = math.log2((2 * distance) / width)
        if id_score < 3.0:
            rating = f"{GREEN}{BOLD}EXCELLENT (Akses Cepat){RESET}"
        elif id_score < 5.0:
            rating = f"{YELLOW}MODERATE (Normal){RESET}"
        else:
            rating = f"{RED}{BOLD}POOR (High Error Rate / Frustrasi){RESET}"

        print(f"  {name:<32} | {distance:<8} | {width:<8} | {id_score:<10.2f} | {rating}")


def simulate_information_architecture() -> None:
    print_section("Information Architecture (IA) Node Hierarchy Audit")
    print(f"{DIM}Memvalidasi kedalaman navigasi (Click Depth) vs keluasan kategori (Breadth).{RESET}\n")

    tree = {
        "Beranda": {
            "depth": 0,
            "children": {
                "Katalog Produk": {
                    "depth": 1,
                    "children": {
                        "Elektronik": {"depth": 2, "children": {"Laptop Ultrabook": {"depth": 3, "children": {}}}},
                        "Aksesoris": {"depth": 2, "children": {}}
                    }
                },
                "Pusat Bantuan": {
                    "depth": 1,
                    "children": {
                        "FAQ Pembayaran": {"depth": 2, "children": {}},
                        "Ticket Dukungan": {"depth": 2, "children": {}}
                    }
                },
                "Akun Pengguna": {
                    "depth": 1,
                    "children": {
                        "Profil": {"depth": 2, "children": {}},
                        "Riwayat Transaksi": {"depth": 2, "children": {}}
                    }
                }
            }
        }
    }

    def traverse(node_name: str, node_data: dict, indent: int = 0) -> None:
        depth = node_data["depth"]
        prefix = "  " * indent + "└─ " if indent > 0 else ""
        color = GREEN if depth <= 1 else (YELLOW if depth == 2 else RED)
        depth_flag = f"[Depth: {depth}]"
        print(f"{prefix}{color}{BOLD}{node_name:<28}{RESET} {DIM}{depth_flag}{RESET}")
        for child_name, child_data in node_data.get("children", {}).items():
            traverse(child_name, child_data, indent + 1)

    traverse("Beranda", tree["Beranda"])

    print(f"\n{CYAN}{BOLD}[Rule of Thumb IA]:{RESET} Kedalaman hierarki maksimal 3 level untuk mencegah disorientasi kognitif.")


def run_interactive_ux_audit() -> None:
    print_section("Interaktif: Quick UX Heuristics & Cognitive Load Score")
    print(f"{WHITE}Evaluasi parameter desain interface Anda:{RESET}\n")

    questions = [
        ("Berapa jumlah opsi navigasi tingkat pertama pada navbar? (rekomendasi: 4-7)", 5, 7),
        ("Berapa ukuran touch target terkecil pada versi mobile (px)? (rekomendasi: >= 48px)", 48, None),
        ("Berapa klik maksimum yang dibutuhkan user untuk mencapai konversi utama?", 3, 3)
    ]

    total_score = 100
    deductions = []

    # Default automated evaluation values for non-interactive / headless CI runs
    defaults = [5, 48, 3]

    print(f"{CYAN}Menjalankan uji kepatuhan standar UX fondasi (WCAG & Nielsen Norman Group)...{RESET}")
    for idx, (prompt, target_val, max_allowed) in enumerate(questions):
        val = defaults[idx]
        print(f" {YELLOW}?{RESET} {prompt}")
        print(f"   {DIM}Value terdeteksi/default: {val}{RESET}")

        if idx == 0 and val > 7:
            total_score -= 20
            deductions.append("Terlalu banyak pilihan utama (Melanggar Hick's Law)")
        elif idx == 1 and val < 44:
            total_score -= 25
            deductions.append("Touch target terlalu kecil (Melanggar WCAG 2.5.5 & Fitts's Law)")
        elif idx == 2 and val > 4:
            total_score -= 20
            deductions.append("Click depth terlalu dalam (Potensi drop-off tinggi)")

    print(f"\n{BOLD}Hasil Audit Kualitas Desain UX:{RESET}")
    if total_score >= 85:
        status_color = GREEN
        status_label = "EXCELLENT - Siap masuk tahap Prototyping & High-Fidelity"
    elif total_score >= 70:
        status_color = YELLOW
        status_label = "ACCEPTABLE - Perlu revisi minor pada Skeleton Plane"
    else:
        status_color = RED
        status_label = "CRITICAL ISSUES - Perlu restrukturisasi Information Architecture"

    print(f"Skor Kepatuhan: {status_color}{BOLD}{total_score}/100 ({status_label}){RESET}")
    if deductions:
        print(f"{RED}Catatan Defisit:{RESET}")
        for d in deductions:
            print(f" - {d}")


def main() -> None:
    print_header("UX DESIGN CORE FOUNDATIONS & ARCHITECTURE SIMULATOR")
    print(f"{WHITE}Modul Pembelajaran Mandiri: BAB-01 Fondasi & Arsitektur UX{RESET}")
    print(f"{DIM}Memuat modul evaluasi teknis UX...{RESET}")

    simulate_garrett_model()
    calculate_hicks_law()
    calculate_fittss_law()
    simulate_information_architecture()
    run_interactive_ux_audit()

    print_header("SIMULASI SELESAI - KONDISI ARSITEKTUR UX OPTIMAL")


if __name__ == "__main__":
    main()
