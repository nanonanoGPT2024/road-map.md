#!/usr/bin/env python3
"""
Lab Exercise: Fondasi Internet dan Arsitektur Peramban Web (BAB-01)
Simulasi Interaktif: Siklus Hidup Permintaan Web & Alur Rendering Peramban.
"""

import sys
import time

# Definisi Kode Warna ANSI
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
BG_GREEN = "\033[42m"
BG_MAGENTA = "\033[45m"


def print_header(title: str):
    print("\n" + "=" * 65)
    print(f"{BOLD}{CYAN}{title.center(65)}{RESET}")
    print("=" * 65)


def print_step(step_num: int, title: str, desc: str):
    print(f"\n{BOLD}{YELLOW}[Langkah {step_num}]{RESET} {BOLD}{WHITE}{title}{RESET}")
    print(f"{DIM}  -> {desc}{RESET}")
    time.sleep(0.3)


def simulate_dns(domain: str):
    print_header(f"FASE 1: RESOLUSI DNS UNTUK '{domain}'")
    cache_layers = [
        ("Periksa Cache Peramban (Browser DNS Cache)", False),
        ("Periksa Cache Sistem Operasi (OS hosts & resolver)", False),
        ("Periksa Cache Router Lokal", False),
        ("Kirim kueri ke ISP Recursive Resolver", True),
    ]

    for stage, found in cache_layers:
        time.sleep(0.2)
        if not found:
            print(f"  {RED}✕{RESET} {stage} ... {YELLOW}MISS (Tidak ditemukan){RESET}")
        else:
            print(f"  {GREEN}✓{RESET} {stage} ... {GREEN}Meneruskan kueri ke Name Servers{RESET}")

    dns_hierarchy = [
        ("Root Name Server ('.')", "Mengarahkan ke TLD .org / .com"),
        ("TLD Name Server ('.org' / '.com')", "Mengarahkan ke Authoritative Name Server"),
        ("Authoritative Name Server ('ns1.domain.com')", "Mengembalikan IP Address: 93.184.216.34"),
    ]

    for server, action in dns_hierarchy:
        time.sleep(0.3)
        print(f"    {CYAN}➜ {server}{RESET}: {action}")

    print(f"\n{GREEN}{BOLD}[SUKSES]{RESET} IP Ditemukan: {BOLD}93.184.216.34{RESET} (TTL: 300 detik)")


def simulate_tcp_tls():
    print_header("FASE 2: KONEKSI TCP (3-WAY HANDSHAKE) & TLS 1.3")
    
    tcp_steps = [
        ("Client", "Server", "SYN", "Sequence Number = 100", CYAN),
        ("Server", "Client", "SYN-ACK", "Acknowledge = 101, Sequence = 300", MAGENTA),
        ("Client", "Server", "ACK", "Acknowledge = 301 (Koneksi TCP ESTABLISHED)", GREEN),
    ]

    print(f"{BOLD}Pertukaran Paket TCP:{RESET}")
    for sender, receiver, flag, detail, color in tcp_steps:
        time.sleep(0.25)
        print(f"  [{color}{sender}{RESET}] ---> {BOLD}{flag:<8}{RESET} ---> [{color}{receiver}{RESET}] | {DIM}{detail}{RESET}")

    print(f"\n{BOLD}Negosiasi Enkripsi TLS 1.3:{RESET}")
    tls_steps = [
        ("Client", "ClientHello + Key Share + Cipher Suites"),
        ("Server", "ServerHello + Key Share + X.509 Certificate Verification"),
        ("Client", "Verifikasi Sertifikat CA & Menghasilkan Symmetric Session Key"),
        ("Both", "Koneksi Terenkripsi Aktif (HTTPS Siap)"),
    ]
    for actor, info in tls_steps:
        time.sleep(0.25)
        print(f"  {BLUE}🔒 [{actor}]{RESET} {info}")


def simulate_http_exchange(path: str):
    print_header(f"FASE 3: PERMINTAAN & RESPONS HTTP/2 (GET {path})")
    
    print(f"{BOLD}{GREEN}>>> HTTP Request dikirim:{RESET}")
    request_headers = [
        f"GET {path} HTTP/2",
        "Host: example.org",
        "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept: text/html,application/xhtml+xml",
        "Accept-Encoding: gzip, deflate, br",
    ]
    for h in request_headers:
        print(f"  {DIM}{h}{RESET}")

    time.sleep(0.4)
    print(f"\n{BOLD}{CYAN}<<< HTTP Response diterima:{RESET}")
    response_headers = [
        "HTTP/2 200 OK",
        "Content-Type: text/html; charset=UTF-8",
        "Content-Length: 1256",
        "Cache-Control: max-age=600",
        "Strict-Transport-Security: max-age=31536000",
    ]
    for h in response_headers:
        print(f"  {DIM}{h}{RESET}")

    print(f"\n{YELLOW}[Body Payload Tiba]{RESET} 1.2 KB HTML Chunk pertama diterima oleh thread network.")


def simulate_browser_engine():
    print_header("FASE 4: PIPELINE RENDERING PERAMBAN (CRITICAL RENDERING PATH)")

    stages = [
        (
            1,
            "HTML Parsing & Konstruksi DOM Tree",
            "Byte stream dikonversi menjadi token, lalu dibentuk node-node DOM.",
            "Node: Document -> html -> body -> [header, main, footer]",
            BLUE,
        ),
        (
            2,
            "CSS Parsing & Konstruksi CSSOM Tree",
            "Membaca stylesheet internal & eksternal untuk menghitung spesifisitas gaya.",
            "Rules: h1 { color: #1e88e5 }, body { margin: 0; font-family: sans-serif }",
            MAGENTA,
        ),
        (
            3,
            "Pembentukan Render Tree",
            "Menggabungkan DOM dan CSSOM. Elemen dengan 'display: none' dibuang.",
            "Render Objects siap dikalkulasi koordinat geometrinya.",
            CYAN,
        ),
        (
            4,
            "Layout / Reflow (Kalkulasi Geometri)",
            "Menghitung ukuran pasti (lebar, tinggi) dan posisi (x, y) setiap elemen viewport.",
            "Viewport: 1920x1080 | Elemen <main> berada di x: 120, y: 80, w: 1680, h: 900",
            YELLOW,
        ),
        (
            5,
            "Paint / Rasterization",
            "Mengubah node render tree menjadi piksel nyata pada layer grafis bitmap.",
            "Menggambar warna latar, teks, border, bayangan (box-shadow).",
            GREEN,
        ),
        (
            6,
            "Compositing (GPU Acceleration)",
            "Menyatukan layer-layer grafis terpisah ke frame buffer layar pengguna.",
            "Peramban memanfaatkan hardware acceleration untuk performa 60 FPS.",
            WHITE,
        ),
    ]

    for step_num, title, desc, detail, color in stages:
        print_step(step_num, title, desc)
        print(f"    {color}⚙ Detail Engine:{RESET} {detail}")
        time.sleep(0.35)


def run_quiz():
    print_header("KUIS INTERAKTIF FONDASI INTERNET & BROWSER")
    questions = [
        {
            "q": "Protokol apa yang bertugas menerjemahkan nama domain (seperti google.com) menjadi alamat IP?",
            "options": ["A. HTTP", "B. DNS", "C. TCP", "D. ARP"],
            "ans": "B",
            "expl": "DNS (Domain Name System) bertindak seperti buku telepon internet.",
        },
        {
            "q": "Pada proses 3-Way Handshake TCP, paket kedua yang dikirim server adalah?",
            "options": ["A. SYN", "B. ACK", "C. SYN-ACK", "D. FIN"],
            "ans": "C",
            "expl": "Server merespons paket SYN dari klien dengan SYN-ACK.",
        },
        {
            "q": "Apakah elemen HTML dengan gaya 'display: none' akan masuk ke dalam Render Tree?",
            "options": ["A. Ya, selalu", "B. Tidak, elemen tersebut dilewati", "C. Hanya jika ada JavaScript", "D. Ya, tapi transparan"],
            "ans": "B",
            "expl": "Render Tree hanya memuat elemen yang terlihat secara visual di layar.",
        },
        {
            "q": "Tahap Critical Rendering Path yang menghitung posisi (x, y) dan ukuran elemen disebut?",
            "options": ["A. Painting", "B. Parsing", "C. Layout / Reflow", "D. Compositing"],
            "ans": "C",
            "expl": "Layout (Reflow) mengukur geometri fisik setiap elemen di dalam viewport.",
        },
    ]

    score = 0
    for idx, item in enumerate(questions, start=1):
        print(f"\n{BOLD}{YELLOW}Pertanyaan {idx}:{RESET} {item['q']}")
        for opt in item["options"]:
            print(f"  {CYAN}{opt}{RESET}")
        
        user_choice = input(f"{BOLD}Jawaban Anda (A/B/C/D): {RESET}").strip().upper()
        if user_choice == item["ans"]:
            print(f"{GREEN}✓ Benar!{RESET} {item['expl']}")
            score += 1
        else:
            print(f"{RED}✕ Salah.{RESET} Jawaban yang benar: {BOLD}{item['ans']}{RESET}. {item['expl']}")

    print(f"\n{BOLD}Skor Akhir Anda:{RESET} {score}/{len(questions)}")
    if score == len(questions):
        print(f"{GREEN}{BOLD}Luar biasa! Pemahaman fondasi arsitektur peramban Anda sangat solid.{RESET}")
    else:
        print(f"{YELLOW}Bagus! Terus pelajari materi untuk menguasai konsep secara menyeluruh.{RESET}")


def main_menu():
    while True:
        print_header("SIMULATOR FONDASI INTERNET & ARSITEKTUR PERAMBAN (BAB-01)")
        print(f"{BOLD}Pilih mode simulasi:{RESET}")
        print(f"  {CYAN}1.{RESET} Simulasi Lengkap End-to-End (DNS -> TCP/TLS -> HTTP -> Rendering)")
        print(f"  {CYAN}2.{RESET} Simulasi Resolusi DNS Saja")
        print(f"  {CYAN}3.{RESET} Simulasi Handshake TCP & Enkripsi TLS")
        print(f"  {CYAN}4.{RESET} Simulasi Alur Kerja Rendering Engine (DOM/CSSOM/Layout/Paint)")
        print(f"  {CYAN}5.{RESET} Uji Pemahaman Mandiri (Kuis Interaktif)")
        print(f"  {CYAN}0.{RESET} Keluar")
        
        try:
            choice = input(f"\n{BOLD}Masukkan pilihan (0-5): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSampai jumpa!")
            break

        if choice == "1":
            domain = input(f"{BOLD}Masukkan domain target (default: developer.mozilla.org): {RESET}").strip()
            if not domain:
                domain = "developer.mozilla.org"
            simulate_dns(domain)
            simulate_tcp_tls()
            simulate_http_exchange("/")
            simulate_browser_engine()
            print(f"\n{GREEN}{BOLD}Halaman web berhasil dimuat dan dirender di layar pengguna!{RESET}")
        elif choice == "2":
            domain = input(f"{BOLD}Masukkan domain target (default: example.com): {RESET}").strip()
            if not domain:
                domain = "example.com"
            simulate_dns(domain)
        elif choice == "3":
            simulate_tcp_tls()
        elif choice == "4":
            simulate_browser_engine()
        elif choice == "5":
            run_quiz()
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menggunakan simulator BAB-01. Selamat belajar!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")
            
        try:
            input(f"\n{DIM}[Tekan Enter untuk kembali ke menu utama]{RESET}")
        except (KeyboardInterrupt, EOFError):
            break


if __name__ == "__main__":
    main_menu()
