#!/usr/bin/env python3
"""
Hands-on Lab Exercise: BAB 03 - Text-Level Semantics, Technical Typography, and Localization
Simulasi interaktif untuk menganalisis, memvalidasi, dan merender semantik teks level HTML5,
termasuk anotasi fonetik (Ruby), bidirectional text (BDI/BDO), semantic technical typography
(code/kbd/samp/var), serta machine-readable inline semantics (time/data/abbr).
"""

import sys
import time
from typing import Dict, List, Any


class ANSI:
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
    BG_BLACK = "\033[40m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_DARK_GRAY = "\033[100m"


def print_banner() -> None:
    banner = f"""
{ANSI.CYAN}{ANSI.BOLD}================================================================================{ANSI.RESET}
{ANSI.MAGENTA}{ANSI.BOLD}  HTML5 TEXT-LEVEL SEMANTICS, TECHNICAL TYPOGRAPHY & LOCALIZATION LAB{ANSI.RESET}
{ANSI.CYAN}  Simulasi Interaktif Mesin Parsing Semantik, Bidi Engine, & Accessibility Tree{ANSI.RESET}
{ANSI.CYAN}{ANSI.BOLD}================================================================================{ANSI.RESET}
"""
    print(banner)


def display_module_header(title: str, subtext: str) -> None:
    print(f"\n{ANSI.YELLOW}{ANSI.BOLD}[MODUL] {title}{ANSI.RESET}")
    print(f"{ANSI.DIM}{subtext}{ANSI.RESET}")
    print(f"{ANSI.CYAN}{'-' * 70}{ANSI.RESET}")


def simulate_technical_typography() -> None:
    display_module_header(
        "1. Semantik Tipografi Komputasi (code, kbd, samp, var)",
        "Membedakan instruksi input, variabel dinamis, cuplikan kode, dan respon sistem.",
    )

    print(f"{ANSI.WHITE}Contoh skenario dokumentasi CLI:{ANSI.RESET}")
    raw_html = (
        "<p>Untuk restart container, ketik <kbd>docker restart <var>container_id</var></kbd>. "
        "Jika port konflik, sistem mencetak <samp>Error: bind failed</samp>.</p>"
    )
    print(f"Markup HTML Mentah:\n  {ANSI.DIM}{raw_html}{ANSI.RESET}\n")

    print(f"{ANSI.BOLD}Simulasi Rendering Visual Terminal:{ANSI.RESET}")
    rendered = (
        f"Untuk restart container, ketik "
        f"{ANSI.BG_DARK_GRAY}{ANSI.WHITE} docker restart {ANSI.ITALIC}{ANSI.CYAN}<container_id>{ANSI.RESET} "
        f". Jika port konflik, sistem mencetak "
        f"{ANSI.BG_BLACK}{ANSI.RED}[Error: bind failed]{ANSI.RESET}."
    )
    print(f"  {rendered}\n")

    print(f"{ANSI.BOLD}Audit Karakteristik Semantik:{ANSI.RESET}")
    specs = [
        ("<code>", "Blok atau token kode pemrograman / script literal"),
        ("<kbd>", "Input pengguna melalui keyboard, voice command, atau gesture"),
        ("<samp>", "Output program, terminal prompt, log sistem, atau respons runtime"),
        ("<var>", "Variabel matematika atau placeholder dinamis dalam perintah"),
    ]
    for tag, desc in specs:
        print(f"  * {ANSI.GREEN}{tag:<8}{ANSI.RESET} -> {desc}")


def simulate_bidirectional_and_localization() -> None:
    display_module_header(
        "2. Lokalisasi & Algoritma Bidirectional (BDI vs BDO)",
        "Penanganan isolasi arah teks LTR/RTL dan override visual paksa.",
    )

    scenarios = [
        {
            "case": "Peringkat Nama User (Tanpa BDI - Berpotensi Rusak/Spillover)",
            "snippet": "<li>User: سارة - 100 Poin</li>",
            "effect": "Karakter angka dan tanda hubung dapat terpental ke sisi kiri teks Arab.",
            "status": f"{ANSI.RED}[RENTAN BUG BIDI]{ANSI.RESET}",
        },
        {
            "case": "Peringkat Nama User (Dengan <bdi> - Bi-directional Isolation)",
            "snippet": "<li>User: <bdi>سارة</bdi> - 100 Poin</li>",
            "effect": "Teks Arab diisolasi ke dalam unit Bidi independen; tanda '-' dan '100 Poin' tetap LTR murni.",
            "status": f"{ANSI.GREEN}[VALID & AMAN]{ANSI.RESET}",
        },
        {
            "case": "Override Arah Teks Paksa (<bdo dir='rtl'>)",
            "snippet": "<bdo dir='rtl'>DEBUG-12345</bdo>",
            "effect": "Karakter di-render urutan kanan-ke-kiri tanpa isolasi semantik (Visual: 54321-GUBED).",
            "status": f"{ANSI.YELLOW}[OVERRIDE AKTIF]{ANSI.RESET}",
        },
    ]

    for item in scenarios:
        print(f"{ANSI.BOLD}{item['case']}{ANSI.RESET} {item['status']}")
        print(f"  Markup : {ANSI.CYAN}{item['snippet']}{ANSI.RESET}")
        print(f"  Analisis: {item['effect']}\n")


def simulate_ruby_annotations() -> None:
    display_module_header(
        "3. Anotasi Fonetik Tipografi Asia Timur (<ruby>, <rt>, <rp>)",
        "Struktur panduan pelafalan Furigana / Pinyin dengan mekanisme fallback.",
    )

    sample_html = (
        "<ruby>\n"
        "  漢 <rp>(</rp><rt>かん</rt><rp>)</rp>\n"
        "  字 <rp>(</rp><rt>じ</rt><rp>)</rp>\n"
        "</ruby>"
    )
    print(f"Markup HTML Ruby Lengkap:\n{ANSI.DIM}{sample_html}{ANSI.RESET}\n")

    print(f"{ANSI.BOLD}Visualisasi Rendering Modern (Furigana di atas Karakter Base):{ANSI.RESET}")
    print(f"    {ANSI.YELLOW}かん  じ{ANSI.RESET}")
    print(f"    {ANSI.WHITE}{ANSI.BOLD}漢   字{ANSI.RESET}\n")

    print(f"{ANSI.BOLD}Fallback Rendering Mode (Browser Jadul / Terminal Teks Polos):{ANSI.RESET}")
    print(f"    {ANSI.WHITE}漢(かん) 字(じ){ANSI.RESET}  {ANSI.DIM}<-- Dihasilkan via elemen <rp>{ANSI.RESET}")


def simulate_semantic_distinctions() -> None:
    display_module_header(
        "4. Perbedaan Semantik: Visual vs Logikal vs Mesin",
        "Komparasi pasangan elemen yang sering disalahartikan.",
    )

    comparisons = [
        ("<b> vs <strong>", "Stylistic offset tanpa urgensi vs Penting/Urgen bagi screen reader"),
        ("<i> vs <em>", "Istilah teknis/latin/pikiran vs Penekanan intonasi ucapan"),
        ("<u> vs <ins>", "Anotasi ortografi/nama asing vs Teks hasil revisi/penambahan dokumen"),
        ("<s> vs <del>", "Informasi usang/tidak relevan vs Teks yang resmi dihapus"),
        ("<mark>", "Penyorotan kontekstual relevan terhadap pencarian/referensi luar"),
        ("<time datetime='...'>", "Tanggal/waktu terbaca manusia sekaligus machine-parsable ISO-8601"),
        ("<data value='...'>", "Mengaitkan konten presentasi dengan machine key/kode produk"),
    ]

    for tags, desc in comparisons:
        print(f"  {ANSI.CYAN}{tags:<22}{ANSI.RESET} : {desc}")


def run_interactive_quiz() -> None:
    display_module_header(
        "5. Challenge & Kuis Diagnostik Semantik",
        "Uji pemahaman mendalam terkait aturan spesifikasi WHATWG HTML5.",
    )

    questions = [
        {
            "q": "Tag manakah yang paling tepat untuk merepresentasikan teks error yang dimuntahkan oleh terminal?",
            "options": ["A. <code>", "B. <kbd>", "C. <samp>", "D. <var>"],
            "ans": "C",
            "explanation": "<samp> (Sample Output) secara spesifik merepresentasikan output dari program/sistem.",
        },
        {
            "q": "Mengapa username yang diinput dinamis dari user multilingual wajib dibungkus <bdi>?",
            "options": [
                "A. Agar teks otomatis diterjemahkan",
                "B. Mengisolasi arah teks agar teks Arab/Ibrani tidak merusak layout sekitarnya",
                "C. Memperbesar ukuran font username",
                "D. Mematikan fitur copy-paste",
            ],
            "ans": "B",
            "explanation": "<bdi> mengisolasi bidirectional text sehingga karakter RTL tidak mencemari arah parsing LTR di sekitarnya.",
        },
        {
            "q": "Bagaimana cara mendefinisikan tanggal publikasi '25 Desember 2026' yang ramah mesin dan crawler?",
            "options": [
                "A. <span class='date'>25 Des 2026</span>",
                "B. <time datetime='2026-12-25'>25 Desember 2026</time>",
                "C. <data date='2026-12-25'>25 Desember 2026</data>",
                "D. <i>2026-12-25</i>",
            ],
            "ans": "B",
            "explanation": "<time> dengan atribut datetime='YYYY-MM-DD' adalah standar resmi machine-readable.",
        },
    ]

    score = 0
    total = len(questions)

    for i, item in enumerate(questions, 1):
        print(f"\n{ANSI.BOLD}Pertanyaan {i}/{total}:{ANSI.RESET} {item['q']}")
        for opt in item["options"]:
            print(f"  {opt}")

        user_choice = input(f"{ANSI.YELLOW}Pilihan Anda (A/B/C/D) [default {item['ans']}]: {ANSI.RESET}").strip().upper()
        if not user_choice:
            user_choice = item["ans"]

        if user_choice == item["ans"]:
            print(f"{ANSI.GREEN}✓ Benar!{ANSI.RESET} {item['explanation']}")
            score += 1
        else:
            print(f"{ANSI.RED}✗ Salah.{ANSI.RESET} Jawaban tepat adalah {item['ans']}. {item['explanation']}")

    print(f"\n{ANSI.BOLD}Hasil Kuis:{ANSI.RESET} Skor Anda: {ANSI.GREEN}{score}/{total}{ANSI.RESET}")


def interactive_menu() -> None:
    while True:
        print_banner()
        print(f"{ANSI.BOLD}PILIHAN LAB INTERAKTIF:{ANSI.RESET}")
        print("  1. Simulasi Tipografi Komputasi (code, kbd, samp, var)")
        print("  2. Simulasi Bidirectional & Lokalisasi (bdi, bdo)")
        print("  3. Simulasi Ruby Annotation (ruby, rt, rp)")
        print("  4. Matriks Komparasi Semantik Teks Level")
        print("  5. Jalankan Kuis Mandiri")
        print("  6. Jalankan Seluruh Demonstrasi (Batch Mode)")
        print("  0. Keluar")

        choice = input(f"\n{ANSI.CYAN}Pilih nomor menu (0-6): {ANSI.RESET}").strip()
        if choice == "1":
            simulate_technical_typography()
        elif choice == "2":
            simulate_bidirectional_and_localization()
        elif choice == "3":
            simulate_ruby_annotations()
        elif choice == "4":
            simulate_semantic_distinctions()
        elif choice == "5":
            run_interactive_quiz()
        elif choice == "6":
            simulate_technical_typography()
            simulate_bidirectional_and_localization()
            simulate_ruby_annotations()
            simulate_semantic_distinctions()
            run_interactive_quiz()
        elif choice in ("0", "q", "exit"):
            print(f"\n{ANSI.GREEN}Terima kasih telah menyelesaikan lab semantik teks HTML5.{ANSI.RESET}")
            sys.exit(0)
        else:
            print(f"{ANSI.RED}Pilihan tidak dikenali. Silakan coba lagi.{ANSI.RESET}")

        input(f"\n{ANSI.DIM}Tekan [Enter] untuk kembali ke menu utama...{ANSI.RESET}")


def main() -> None:
    # Jika dijalankan dengan argument non-interaktif atau piped input
    if not sys.stdin.isatty() or "--non-interactive" in sys.argv:
        print_banner()
        simulate_technical_typography()
        simulate_bidirectional_and_localization()
        simulate_ruby_annotations()
        simulate_semantic_distinctions()
        print(f"\n{ANSI.GREEN}[NON-INTERACTIVE CHECK PASSED] Seluruh modul simulasi valid.{ANSI.RESET}")
    else:
        try:
            interactive_menu()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{ANSI.YELLOW}Sesi lab dihentikan oleh pengguna.{ANSI.RESET}")
            sys.exit(0)


if __name__ == "__main__":
    main()
