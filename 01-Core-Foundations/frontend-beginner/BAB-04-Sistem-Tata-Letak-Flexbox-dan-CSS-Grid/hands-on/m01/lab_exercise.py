#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Flexbox & CSS Grid Terminal
BAB 04: Sistem Tata Letak Modern (Flexbox & CSS Grid)
Frontend Beginner Curriculum - Core Foundations

Simulator visual interaktif untuk memahami perilaku tata letak:
1. Flexbox (Sistem 1 Dimensi: Main Axis vs Cross Axis)
2. CSS Grid (Sistem 2 Dimensi: Baris, Kolom, Area, dan Gap)
"""

import sys
import time

# --- ANSI Color Codes ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Foreground Colors
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
RED = "\033[31m"
WHITE = "\033[37m"

# Background Colors for visual boxes
BG_CONTAINER = "\033[48;5;236m"
BG_ITEM1 = "\033[48;5;31m\033[97m"
BG_ITEM2 = "\033[48;5;35m\033[97m"
BG_ITEM3 = "\033[48;5;166m\033[97m"
BG_ITEM4 = "\033[48;5;128m\033[97m"


def clear_screen():
    print("\033[2J\033[H", end="")


def print_banner():
    print(f"{CYAN}{BOLD}{'=' * 68}{RESET}")
    print(f"{CYAN}{BOLD}   LAB VIRTUAL: SIMULATOR TATA LETAK FLEXBOX & CSS GRID{RESET}")
    print(f"{BLUE}      BAB 04 - Core Foundations Frontend Beginner{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 68}{RESET}\n")


def simulate_flexbox():
    print(f"\n{YELLOW}{BOLD}[MODUL 1: FLEXBOX 1D LAYOUT ENGINE]{RESET}")
    print(f"{DIM}Flexbox bekerja pada satu sumbu (1 Dimensi): Main Axis & Cross Axis.{RESET}\n")

    directions = ["row", "row-reverse", "column"]
    justifies = ["flex-start", "center", "flex-end", "space-between", "space-around"]

    print(f"{WHITE}Pilih {BOLD}flex-direction{RESET}:{WHITE}")
    for idx, d in enumerate(directions, 1):
        print(f"  {idx}. {d}")
    dir_choice = input(f"{CYAN}Pilihan (1-3, default 1): {RESET}").strip()
    direction = directions[int(dir_choice) - 1] if dir_choice in ["1", "2", "3"] else "row"

    print(f"\nPilih {BOLD}justify-content{RESET} (Alignment sepanjang Main Axis):")
    for idx, j in enumerate(justifies, 1):
        print(f"  {idx}. {j}")
    jc_choice = input(f"{CYAN}Pilihan (1-5, default 1): {RESET}").strip()
    justify = justifies[int(jc_choice) - 1] if jc_choice in ["1", "2", "3", "4", "5"] else "flex-start"

    items = ["[ 1 ]", "[ 2 ]", "[ 3 ]"]
    if direction == "row-reverse":
        items = list(reversed(items))

    container_width = 46
    total_items_len = sum(len(it) for it in items)
    remaining_space = container_width - total_items_len

    rendered_line = ""
    if justify == "flex-start":
        rendered_line = " ".join(items) + (" " * (container_width - len(" ".join(items))))
    elif justify == "center":
        left_pad = remaining_space // 2
        right_pad = remaining_space - left_pad
        rendered_line = (" " * left_pad) + "".join(items) + (" " * right_pad)
    elif justify == "flex-end":
        rendered_line = (" " * remaining_space) + "".join(items)
    elif justify == "space-between":
        gap = remaining_space // (len(items) - 1)
        rendered_line = items[0] + (" " * gap) + items[1] + (" " * (remaining_space - gap)) + items[2]
    elif justify == "space-around":
        unit = remaining_space // (len(items) * 2)
        pad = " " * unit
        rendered_line = pad + items[0] + (pad * 2) + items[1] + (pad * 2) + items[2] + pad

    print(f"\n{GREEN}{BOLD}CSS Declaration Applied:{RESET}")
    print(f"{MAGENTA}.flex-container {{{RESET}")
    print(f"  display: flex;")
    print(f"  flex-direction: {CYAN}{direction}{RESET};")
    print(f"  justify-content: {CYAN}{justify}{RESET};")
    print(f"{MAGENTA}}}{RESET}\n")

    print(f"{WHITE}Visualisasi Container (Lebar: 48 char):{RESET}")
    print(f"{BLUE}+" + ("-" * 48) + f"+{RESET}")
    if direction in ["row", "row-reverse"]:
        print(f"{BLUE}|{RESET} {BG_CONTAINER}{rendered_line}{RESET} {BLUE}|{RESET}")
    else:
        # column rendering
        for it in items:
            pad = " " * (container_width - len(it))
            print(f"{BLUE}|{RESET} {BG_CONTAINER}{it}{pad}{RESET} {BLUE}|{RESET}")
    print(f"{BLUE}+" + ("-" * 48) + f"+{RESET}")
    print(f"{DIM}Main Axis: {'Horizontal (X)' if 'row' in direction else 'Vertical (Y)'} | Cross Axis: {'Vertical (Y)' if 'row' in direction else 'Horizontal (X)'}{RESET}\n")


def simulate_grid():
    print(f"\n{YELLOW}{BOLD}[MODUL 2: CSS GRID 2D LAYOUT ENGINE]{RESET}")
    print(f"{DIM}CSS Grid mengatur tata letak 2 Dimensi (Baris & Kolom sekaligus).{RESET}\n")

    print("Contoh studi kasus: Dashboard Card Grid 3 Kolom")
    print(f"{WHITE}Pilih konfigurasi gap:{RESET}")
    print("  1. gap: 0px (Rapat tanpa jeda)")
    print("  2. gap: 12px (Standar moderat)")
    print("  3. gap: 24px (Spacious layout)")
    gap_choice = input(f"{CYAN}Pilihan gap (1-3, default 2): {RESET}").strip()

    gap_str = "0px" if gap_choice == "1" else ("24px" if gap_choice == "3" else "12px")
    spacer = "" if gap_choice == "1" else ("  " if gap_choice == "2" else "    ")

    print(f"\n{GREEN}{BOLD}CSS Declaration Applied:{RESET}")
    print(f"{MAGENTA}.dashboard-grid {{{RESET}")
    print(f"  display: grid;")
    print(f"  grid-template-columns: {CYAN}repeat(3, 1fr){RESET};")
    print(f"  grid-template-rows: {CYAN}auto auto{RESET};")
    print(f"  gap: {CYAN}{gap_str}{RESET};")
    print(f"{MAGENTA}}}{RESET}\n")

    print(f"{WHITE}Visualisasi CSS Grid Matrix (2 Baris x 3 Kolom):{RESET}")
    row1 = [f"{BG_ITEM1} Card 1 {RESET}", f"{BG_ITEM2} Card 2 {RESET}", f"{BG_ITEM3} Card 3 {RESET}"]
    row2 = [f"{BG_ITEM4} Card 4 {RESET}", f"{BG_ITEM1} Card 5 {RESET}", f"{BG_ITEM2} Card 6 {RESET}"]

    print(spacer.join(row1))
    if gap_choice != "1":
        print(f"{DIM}  ... [grid-row-gap: {gap_str}] ...{RESET}")
    print(spacer.join(row2))
    print(f"\n{DIM}Karakteristik Grid: Penempatan item presisi berbasis sel dan track (fr unit).{RESET}\n")


def run_comparative_matrix():
    print(f"\n{YELLOW}{BOLD}[MODUL 3: KOMPARASI ATURAN PENGGUNAAN (FLEXBOX vs GRID)]{RESET}")
    table = [
        ("Dimensi Layout", "1 Dimensi (Baris ATAU Kolom)", "2 Dimensi (Baris DAN Kolom)"),
        ("Filosofi", "Content-First (Ukuran konten memandu layout)", "Layout-First (Grid memandu ukuran konten)"),
        ("Kasus Terbaik", "Navigasi, Form input group, Tombol sejajar", "Halaman Web utuh, Photo Gallery, Dashboard"),
        ("Sumbu Kontrol", "Main Axis vs Cross Axis", "Grid Line, Track, Grid Template Areas"),
    ]

    header_fmt = f"{BOLD}{WHITE}{'Aspek':<18} | {'Flexbox':<32} | {'CSS Grid':<35}{RESET}"
    sep = "-" * 90
    print(sep)
    print(header_fmt)
    print(sep)
    for aspect, flex_desc, grid_desc in table:
        print(f"{CYAN}{aspect:<18}{RESET} | {GREEN}{flex_desc:<32}{RESET} | {MAGENTA}{grid_desc:<35}{RESET}")
    print(sep + "\n")


def main():
    while True:
        clear_screen()
        print_banner()
        print(f"{WHITE}Pilih menu simulasi yang ingin Anda uji:{RESET}")
        print(f"  {CYAN}1.{RESET} Eksplorasi Flexbox (Direction & Justify-Content)")
        print(f"  {CYAN}2.{RESET} Eksplorasi CSS Grid (repeat(), fr, dan gap)")
        print(f"  {CYAN}3.{RESET} Matriks Komparasi Kapan Pakai Flexbox vs Grid")
        print(f"  {CYAN}4.{RESET} Jalankan Semua Demonstrasi Sekaligus")
        print(f"  {RED}5.{RESET} Keluar")

        choice = input(f"\n{YELLOW}Ketik nomor pilihan (1-5): {RESET}").strip()

        if choice == "1":
            simulate_flexbox()
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        elif choice == "2":
            simulate_grid()
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        elif choice == "3":
            run_comparative_matrix()
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        elif choice == "4":
            simulate_flexbox()
            simulate_grid()
            run_comparative_matrix()
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")
        elif choice == "5" or choice.lower() in ["exit", "q", "quit"]:
            print(f"\n{GREEN}Terima kasih telah bereksperimen dengan lab Flexbox & CSS Grid!{RESET}\n")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")
            time.sleep(1)


if __name__ == "__main__":
    main()
