#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi CSS3 Box Model & Critical Rendering Pipeline
Modul 01 - Frontend Beginner (BAB 03)

Simulator interaktif berbasis terminal dengan warna ANSI untuk memahami:
1. Box Model (content-box vs border-box) & kalkulasi dimensi fisik elemen
2. Browser Rendering Pipeline (DOM -> CSSOM -> Render Tree -> Layout -> Paint -> Composite)
3. Margin Collapse & trigger Reflow vs Repaint
"""

import sys
import time

# Konstanta Kode Warna ANSI
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
BG_YELLOW = "\033[43m"
BG_GREEN = "\033[42m"
BG_MAGENTA = "\033[45m"


def clear_screen():
    print("\033[2J\033[H", end="")


def print_header(title):
    print(f"\n{BOLD}{CYAN}{'=' * 68}{RESET}")
    print(f"{BOLD}{YELLOW}  {title.center(64)}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 68}{RESET}\n")


def simulate_box_model():
    print_header("SIMULASI CSS BOX MODEL: CONTENT-BOX VS BORDER-BOX")

    print(f"{WHITE}Masukkan properti CSS untuk elemen hipotesis:{RESET}")
    try:
        width = int(input(f"{CYAN}  Lebar dasar (width dlm px)    [default 300]: {RESET}") or 300)
        padding = int(input(f"{CYAN}  Padding seragam (px)          [default 20]:  {RESET}") or 20)
        border = int(input(f"{CYAN}  Border tebal (px)             [default 5]:   {RESET}") or 5)
        margin = int(input(f"{CYAN}  Margin luar (px)              [default 15]:  {RESET}") or 15)
    except ValueError:
        print(f"{RED}Input harus berupa bilangan bulat! Menggunakan nilai default.{RESET}")
        width, padding, border, margin = 300, 20, 5, 15

    # Perhitungan content-box
    cb_content_w = width
    cb_total_rendered_w = width + (2 * padding) + (2 * border)
    cb_total_space_w = cb_total_rendered_w + (2 * margin)

    # Perhitungan border-box
    bb_total_rendered_w = width
    bb_content_w = max(0, width - (2 * padding) - (2 * border))
    bb_total_space_w = bb_total_rendered_w + (2 * margin)

    print(f"\n{BOLD}{MAGENTA}[1] box-sizing: content-box (W3C Standard Classic){RESET}")
    print(f"  * Content Area Width : {GREEN}{cb_content_w}px{RESET}")
    print(f"  * Padding (Kiri+Kanan): {YELLOW}+{2 * padding}px{RESET}")
    print(f"  * Border (Kiri+Kanan) : {BLUE}+{2 * border}px{RESET}")
    print(f"  {BOLD}-> Lebar Visual Tampak: {RED}{cb_total_rendered_w}px{RESET} (Lebar membesar melebihi nilai width!)")
    print(f"  * Total Occupied Space: {WHITE}{cb_total_space_w}px{RESET} (termasuk margin kiri/kanan)")

    print(f"\n{BOLD}{GREEN}[2] box-sizing: border-box (Modern Standard Layout){RESET}")
    print(f"  * Ditetapkan CSS width: {GREEN}{width}px{RESET}")
    print(f"  * Padding (Kiri+Kanan): {YELLOW}-{2 * padding}px{RESET} (ditelan ke dalam)")
    print(f"  * Border (Kiri+Kanan) : {BLUE}-{2 * border}px{RESET} (ditelan ke dalam)")
    print(f"  * Sisa Ruang Konten   : {CYAN}{bb_content_w}px{RESET}")
    print(f"  {BOLD}-> Lebar Visual Tampak: {GREEN}{bb_total_rendered_w}px{RESET} (Tepat sesuai deklarasi width!)")
    print(f"  * Total Occupied Space: {WHITE}{bb_total_space_w}px{RESET} (termasuk margin kiri/kanan)")

    print(f"\n{BOLD}{YELLOW}Diagram Visual Tingkat Lapisan Box Model:{RESET}")
    print(f"  {BG_YELLOW}{WHITE} [MARGIN: {margin}px] {RESET}")
    print(f"    {BG_BLUE}{WHITE} [BORDER: {border}px] {RESET}")
    print(f"      {BG_GREEN}{WHITE} [PADDING: {padding}px] {RESET}")
    print(f"        {BG_MAGENTA}{WHITE} [CONTENT: {cb_content_w}px (cb) | {bb_content_w}px (bb)] {RESET}")


def simulate_rendering_pipeline():
    print_header("SIMULATOR CRITICAL RENDERING PIPELINE BROWSER")

    properties = [
        {"name": "width: 500px", "type": "Layout/Reflow", "cost": "MAHAL (Reflow -> Repaint -> Composite)"},
        {"name": "margin-left: 20px", "type": "Layout/Reflow", "cost": "MAHAL (Reflow -> Repaint -> Composite)"},
        {"name": "background-color: #f00", "type": "Paint/Repaint", "cost": "SEDANG (Repaint -> Composite)"},
        {"name": "color: #333", "type": "Paint/Repaint", "cost": "SEDANG (Repaint -> Composite)"},
        {"name": "transform: translateX(20px)", "type": "Composite Only", "cost": "SANGAT CEPAT (GPU Composite)"},
        {"name": "opacity: 0.8", "type": "Composite Only", "cost": "SANGAT CEPAT (GPU Composite)"}
    ]

    print(f"{WHITE}Pilih modifikasi CSS DOM untuk melihat tahapan rendering pipeline:{RESET}")
    for idx, prop in enumerate(properties, 1):
        print(f"  [{idx}] {CYAN}{prop['name']}{RESET}")

    choice = input(f"\nPilih nomor [1-{len(properties)}]: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(properties)):
        print(f"{RED}Pilihan tidak valid.{RESET}")
        return

    selected = properties[int(choice) - 1]
    print(f"\n{BOLD}Menganalisis Trigger Perubahan Properti:{RESET} {YELLOW}{selected['name']}{RESET}")
    print(f"Kategori Efek: {BOLD}{selected['type']}{RESET} | Biaya Performa: {selected['cost']}\n")

    steps = [
        ("1. Parsing HTML -> DOM Tree", "Mengurai tag HTML menjadi node Document Object Model", CYAN),
        ("2. Parsing CSS -> CSSOM Tree", "Mengurai stylesheet menjadi CSS Object Model", BLUE),
        ("3. Rekonstruksi Render Tree", "Menggabungkan DOM yang tampak dengan aturan CSSOM", MAGENTA),
        ("4. Layout (Reflow)", "Menghitung geometri presisi: koordinat X/Y, lebar & tinggi elemen", RED),
        ("5. Paint (Rasterize)", "Mengisi piksel ke layer: teks, warna, border, box-shadow", YELLOW),
        ("6. Composite Layers", "Menggabungkan layer independen ke GPU framebuffer layar", GREEN),
    ]

    for step, desc, color in steps:
        time.sleep(0.3)
        if selected["type"] == "Composite Only" and ("Layout" in step or "Paint" in step):
            print(f"  {DIM}[SKIPPED] {step} - (Dilewati, hemat siklus CPU!){RESET}")
        elif selected["type"] == "Paint/Repaint" and "Layout" in step:
            print(f"  {DIM}[SKIPPED] {step} - (Geometri tidak bergeser, Reflow di-bypass){RESET}")
        else:
            print(f"  {BOLD}{color}[ACTIVE]  {step}{RESET} -> {desc}")

    print(f"\n{BOLD}{GREEN}[ANALISIS PERFORMA]:{RESET}")
    if selected["type"] == "Composite Only":
        print(f"  {GREEN}Status: 60 FPS Smooth! Menggunakan GPU layer tanpa triggering reflow.{RESET}")
    elif selected["type"] == "Paint/Repaint":
        print(f"  {YELLOW}Status: Cukup Baik. Hindari perulangan dalam event onScroll / requestAnimationFrame.{RESET}")
    else:
        print(f"  {RED}Status: Waspada Jank! Memaksa CPU menghitung ulang seluruh geometri tata letak.{RESET}")


def simulate_margin_collapse():
    print_header("STUDI KASUS: MARGIN COLLAPSE DALAM NORMAL FLOW")
    print(f"{WHITE}Dua elemen block vertikal berada bertumpukan secara default:{RESET}")
    print(f"  Elemen Atas:   {CYAN}margin-bottom: 30px{RESET}")
    print(f"  Elemen Bawah:  {CYAN}margin-top: 20px{RESET}\n")

    print(f"{BOLD}Pertanyaan: Berapa jarak spasi nyata antar kedua elemen tersebut?{RESET}")
    print(f"  A) 50px (30px + 20px dijumlahkan)")
    print(f"  B) 30px (Margin runtuh/collapse mengambil nilai terbesar)")
    print(f"  C) 10px (Selisih margin)")

    ans = input(f"\nJawaban Anda [A/B/C]: ").strip().upper()
    if ans == "B":
        print(f"\n{BOLD}{GREEN}BENAR! Jarak sesungguhnya adalah 30px.{RESET}")
    else:
        print(f"\n{BOLD}{RED}KURANG TEPAT. Jawaban yang benar adalah B (30px).{RESET}")

    print(f"\n{YELLOW}Penjelasan Aturan W3C Margin Collapsing:{RESET}")
    print("  1. Margin vertikal (top & bottom) antar elemen block bersaudara di dalam normal flow")
    print("     akan saling melebur (collapse), bukan bertumpuk penjumlahan.")
    print("  2. Nilai jarak yang diambil adalah nilai margin TERBESAR (max(30, 20) = 30px).")
    print("  3. Margin horizontal (left & right) TIDAK PERNAH mengalami collapse.")
    print("  4. Flexbox item dan Grid item TIDAK mengalami margin collapse.")


def run_quiz():
    print_header("KUIS REFLEKSI FONDASI CSS3 & BOX MODEL")
    questions = [
        {
            "q": "Apa nilai properti box-sizing default pada seluruh elemen HTML menurut spesifikasi W3C?",
            "opt": ["A. border-box", "B. content-box", "C. margin-box", "D. padding-box"],
            "ans": "B",
            "exp": "Default browser adalah 'content-box', sehingga padding dan border memperbesar dimensi elemen."
        },
        {
            "q": "Manakah properti CSS berikut yang HANYA memicu tahap Composite tanpa Reflow maupun Repaint?",
            "opt": ["A. width", "B. top", "C. transform", "D. border-color"],
            "ans": "C",
            "exp": "Properti 'transform' dan 'opacity' dapat diproses langsung oleh GPU layer (Composite-only)."
        },
        {
            "q": "Bagaimana reset CSS universal modern yang paling direkomendasikan untuk box model?",
            "opt": [
                "A. * { box-sizing: content-box; }",
                "B. html { box-sizing: border-box; } *, *::before, *::after { box-sizing: inherit; }",
                "C. body { margin: 0; padding: 0; }",
                "D. * { margin: 0 !important; }"
            ],
            "ans": "B",
            "exp": "Pola inheritance border-box memudahkan integrasi komponen pihak ketiga yang membutuhkan custom sizing."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"\n{BOLD}{WHITE}Soal {idx}: {item['q']}{RESET}")
        for opt in item["opt"]:
            print(f"  {opt}")
        user_ans = input(f"{CYAN}Pilihan Anda [A/B/C/D]: {RESET}").strip().upper()
        if user_ans == item["ans"]:
            print(f"{GREEN}Benar!{RESET} {item['exp']}")
            score += 1
        else:
            print(f"{RED}Salah! Pilihan tepat adalah {item['ans']}.{RESET} {item['exp']}")

    print(f"\n{BOLD}{CYAN}Skor Akhir Kuis: {score}/{len(questions)}{RESET}")


def main_menu():
    while True:
        clear_screen()
        print(f"{BOLD}{BLUE}===================================================================={RESET}")
        print(f"{BOLD}{WHITE}    SIMULATOR FONDASI CSS3: BOX MODEL & RENDERING ENGINE          {RESET}")
        print(f"{BOLD}{BLUE}===================================================================={RESET}")
        print(f"  {CYAN}[1]{RESET} Simulasi Kalkulator Box Model (content-box vs border-box)")
        print(f"  {CYAN}[2]{RESET} Simulasi Critical Rendering Pipeline (Reflow vs Repaint vs Composite)")
        print(f"  {CYAN}[3]{RESET} Demonstrasi Aturan Margin Collapse")
        print(f"  {CYAN}[4]{RESET} Uji Pemahaman Mandiri (Kuis Interaktif)")
        print(f"  {CYAN}[5]{RESET} Keluar")
        print(f"{BOLD}{BLUE}--------------------------------------------------------------------{RESET}")

        pilihan = input(f"{YELLOW}Pilih modul simulasi [1-5]: {RESET}").strip()
        if pilihan == "1":
            simulate_box_model()
        elif pilihan == "2":
            simulate_rendering_pipeline()
        elif pilihan == "3":
            simulate_margin_collapse()
        elif pilihan == "4":
            run_quiz()
        elif pilihan == "5":
            print(f"\n{GREEN}Terima kasih! Terus tingkatkan pemahaman fondasi Web Architecture & CSS3!{RESET}\n")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid! Tekan Enter untuk coba lagi.{RESET}")

        input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu utama...{RESET}")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Program dihentikan pengguna. Sampai jumpa!{RESET}\n")
        sys.exit(0)
