#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Interaktif Shell Stream I/O, Redirection, & Pipe Architecture
BAB-02: Manajemen Shell, Stream I/O, dan Otomasi Bash
"""

import sys
import time
from typing import List, Dict, Tuple

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
    BG_DARK = "\033[48;5;236m"

def print_banner() -> None:
    print(f"{ANSI.CYAN}{ANSI.BOLD}{'=' * 75}{ANSI.RESET}")
    print(f"{ANSI.YELLOW}{ANSI.BOLD} [LAB INTERAKTIF] SIMULATOR STREAM I/O & BASH PIPELINE ARCHITECTURE{ANSI.RESET}")
    print(f"{ANSI.CYAN}{'=' * 75}{ANSI.RESET}")
    print(f"{ANSI.DIM}Simulasi visual standar file descriptor (FD 0, 1, 2) dan operator redirect.{ANSI.RESET}\n")

class StreamSimulator:
    def __init__(self):
        self.stdin_buffer: List[str] = []
        self.stdout_buffer: List[str] = []
        self.stderr_buffer: List[str] = []
        self.files: Dict[str, List[str]] = {
            "auth.log": [
                "Oct 10 10:00:01 srv sshd[1021]: Failed password for invalid user admin from 192.168.1.100 port 45123",
                "Oct 10 10:00:15 srv sshd[1022]: Accepted publickey for debian from 192.168.1.50 port 50214",
                "Oct 10 10:01:03 srv sshd[1025]: Failed password for root from 203.0.113.19 port 33120",
                "Oct 10 10:02:40 srv sshd[1030]: Invalid user postgres from 198.51.100.2 port 40192",
                "Oct 10 10:03:12 srv sshd[1033]: Accepted password for deploy from 10.0.0.12 port 52109"
            ]
        }

    def reset_streams(self) -> None:
        self.stdin_buffer.clear()
        self.stdout_buffer.clear()
        self.stderr_buffer.clear()

    def render_fd_table(self) -> None:
        print(f"\n{ANSI.BOLD}Current File Descriptor State:{ANSI.RESET}")
        print(f"┌──────┬────────┬───────────────────┬────────────────────────────────────────┐")
        print(f"│ {ANSI.BOLD}FD{ANSI.RESET}   │ {ANSI.BOLD}Name{ANSI.RESET}   │ {ANSI.BOLD}Target Buffer{ANSI.RESET}     │ {ANSI.BOLD}Item Count / Status{ANSI.RESET}                    │")
        print(f"├──────┼────────┼───────────────────┼────────────────────────────────────────┤")
        print(f"│ 0    │ stdin  │ STDIN_BUFFER      │ {len(self.stdin_buffer):<38} │")
        print(f"│ 1    │ stdout │ STDOUT_BUFFER     │ {len(self.stdout_buffer):<38} │")
        print(f"│ 2    │ stderr │ STDERR_BUFFER     │ {len(self.stderr_buffer):<38} │")
        print(f"└──────┴────────┴───────────────────┴────────────────────────────────────────┘")

    def demo_streams(self) -> None:
        self.reset_streams()
        print(f"\n{ANSI.MAGENTA}[DEMO 1] Standar File Descriptors: 0 (stdin), 1 (stdout), 2 (stderr){ANSI.RESET}")
        sample_logs = self.files["auth.log"]

        print(f"{ANSI.DIM}> Mensimulasikan proses membaca data dan memilah level stream...{ANSI.RESET}")
        time.sleep(0.3)

        for line in sample_logs:
            if "Failed" in line or "Invalid" in line:
                self.stderr_buffer.append(f"[ERR-2] {line}")
            else:
                self.stdout_buffer.append(f"[OUT-1] {line}")

        self.render_fd_table()

        print(f"\n{ANSI.GREEN}>>> STDOUT (FD 1 - Normal Output):{ANSI.RESET}")
        for item in self.stdout_buffer:
            print(f"  {ANSI.GREEN}✔ {item}{ANSI.RESET}")

        print(f"\n{ANSI.RED}>>> STDERR (FD 2 - Diagnostic/Error Output):{ANSI.RESET}")
        for item in self.stderr_buffer:
            print(f"  {ANSI.RED}✖ {item}{ANSI.RESET}")

    def demo_redirection(self) -> None:
        self.reset_streams()
        print(f"\n{ANSI.MAGENTA}[DEMO 2] Operator Redirection: >, >>, 2>, dan 2>&1{ANSI.RESET}")
        
        commands: List[Tuple[str, str]] = [
            ("echo 'System Initialized' > output.log", "Overwrite stdout ke output.log (FD 1 -> file)"),
            ("echo 'Worker node added' >> output.log", "Append stdout ke output.log"),
            ("cat /etc/shadow 2> error.log", "Redirect stderr ke error.log (FD 2 -> file)"),
            ("app_run > app.log 2>&1", "Gabungkan stderr ke channel stdout lalu simpan bersamaan"),
            ("grep 'Accepted' < auth.log", "Input redirection dari file ke stdin (FD 0 <- file)")
        ]

        for cmd, explanation in commands:
            print(f"\n{ANSI.BOLD}Perintah:{ANSI.RESET} {ANSI.CYAN}{cmd}{ANSI.RESET}")
            print(f"{ANSI.YELLOW}Mekanisme:{ANSI.RESET} {explanation}")
            time.sleep(0.2)

        # Simulasi 2>&1
        print(f"\n{ANSI.DIM}Simulasi eksekusi `app_run > app.log 2>&1`:{ANSI.RESET}")
        combined_file = []
        combined_file.append("[stdout] Starting microservice runtime v2.1")
        combined_file.append("[stderr] Warning: Insecure default credentials detected!")
        combined_file.append("[stdout] HTTP listener bound to 0.0.0.0:8080")

        print(f"{ANSI.BOLD}Isi dari app.log setelah merge 2>&1:{ANSI.RESET}")
        for entry in combined_file:
            color = ANSI.RED if "[stderr]" in entry else ANSI.GREEN
            print(f"  {color}{entry}{ANSI.RESET}")

    def demo_pipeline(self) -> None:
        print(f"\n{ANSI.MAGENTA}[DEMO 3] Visualisasi Pipeline Linier (|){ANSI.RESET}")
        raw_stream = self.files["auth.log"]
        print(f"{ANSI.BOLD}Command:{ANSI.RESET} {ANSI.CYAN}cat auth.log | grep 'Failed' | awk '{{print $11}}' | sort -u{ANSI.RESET}\n")

        print(f"1. {ANSI.BLUE}[cat auth.log]{ANSI.RESET} Output stream: {len(raw_stream)} baris log")
        filtered_grep = [line for line in raw_stream if "Failed" in line]
        print(f"   ↓ {ANSI.DIM}(Pipe menghubungkan stdout proses 1 ke stdin proses 2){ANSI.RESET}")
        
        print(f"2. {ANSI.BLUE}[grep 'Failed']{ANSI.RESET} Output stream: {len(filtered_grep)} baris yang cocok")
        for item in filtered_grep:
            print(f"      {ANSI.DIM}• {item}{ANSI.RESET}")

        print(f"   ↓ {ANSI.DIM}(Pipe meneruskan ke parser awk){ANSI.RESET}")
        extracted_ips = []
        for line in filtered_grep:
            parts = line.split()
            # Posisi IP berada di index ke-10 (indeks 0-based)
            for part in parts:
                if "." in part and part.replace(".", "").isdigit():
                    extracted_ips.append(part)
                    break
        print(f"3. {ANSI.BLUE}[awk '{{print $IP}}']{ANSI.RESET} Ekstraksi IP penyerang:")
        print(f"      IPs: {', '.join(extracted_ips)}")

        print(f"   ↓ {ANSI.DIM}(Pipe meneruskan ke sort deduplikasi){ANSI.RESET}")
        unique_ips = sorted(list(set(extracted_ips)))
        print(f"4. {ANSI.GREEN}[sort -u]{ANSI.RESET} Hasil akhir stdout pipeline:")
        for ip in unique_ips:
            print(f"      {ANSI.GREEN}{ANSI.BOLD}→ {ip}{ANSI.RESET}")

    def run_interactive_quiz(self) -> None:
        print(f"\n{ANSI.MAGENTA}[KUIS SINGKAT OPERATOR I/O]{ANSI.RESET}")
        questions = [
            {
                "q": "Operator mana yang me-redirect error stream (FD 2) tanpa menimpa stdout?",
                "choices": ["A. > file.txt", "B. 2> file.txt", "C. < file.txt", "D. &> file.txt"],
                "correct": "B"
            },
            {
                "q": "Apa arti '2>&1' dalam eksekusi shell bash?",
                "choices": [
                    "A. Mengirim background job nomor 1 dan 2",
                    "B. Menghapus stream stdout",
                    "C. Mengalihkan stream stderr (FD 2) ke target stdout (FD 1)",
                    "D. Menggandakan data input keyboard"
                ],
                "correct": "C"
            }
        ]

        score = 0
        for i, q in enumerate(questions, 1):
            print(f"\n{ANSI.BOLD}Soal {i}:{ANSI.RESET} {q['q']}")
            for ch in q["choices"]:
                print(f"  {ch}")
            ans = input(f"{ANSI.YELLOW}Pilihan Anda (A/B/C/D) [default: {q['correct']}]: {ANSI.RESET}").strip().upper()
            if not ans:
                ans = q['correct']
            if ans == q["correct"]:
                print(f"  {ANSI.GREEN}✓ Benar!{ANSI.RESET}")
                score += 1
            else:
                print(f"  {ANSI.RED}✗ Salah. Jawaban yang tepat: {q['correct']}{ANSI.RESET}")

        print(f"\n{ANSI.BOLD}Skor Kuis:{ANSI.RESET} {score}/{len(questions)}")

def main() -> None:
    print_banner()
    sim = StreamSimulator()

    while True:
        print(f"\n{ANSI.BOLD}Menu Simulasi Stream & Bash Automation:{ANSI.RESET}")
        print(f"  {ANSI.CYAN}1.{ANSI.RESET} Simulasi File Descriptors (FD 0, 1, 2)")
        print(f"  {ANSI.CYAN}2.{ANSI.RESET} Simulasi Operator Redirection (>, >>, 2>, 2>&1)")
        print(f"  {ANSI.CYAN}3.{ANSI.RESET} Simulasi Pipeline Pemrosesan Teks (|)")
        print(f"  {ANSI.CYAN}4.{ANSI.RESET} Jalankan Kuis Singkat I/O Redirection")
        print(f"  {ANSI.CYAN}5.{ANSI.RESET} Jalankan Semua Modul Otomatis (Demo Non-Interaktif)")
        print(f"  {ANSI.RED}0.{ANSI.RESET} Keluar")

        choice = input(f"\n{ANSI.YELLOW}Pilih opsi [1-5, 0]: {ANSI.RESET}").strip()

        if choice == "1":
            sim.demo_streams()
        elif choice == "2":
            sim.demo_redirection()
        elif choice == "3":
            sim.demo_pipeline()
        elif choice == "4":
            sim.run_interactive_quiz()
        elif choice == "5" or choice == "":
            print(f"\n{ANSI.YELLOW}Menjalankan demonstrasi komprehensif...{ANSI.RESET}")
            sim.demo_streams()
            sim.demo_redirection()
            sim.demo_pipeline()
            print(f"\n{ANSI.GREEN}Demonstrasi komprehensif selesai.{ANSI.RESET}")
            break
        elif choice == "0":
            print(f"\n{ANSI.GREEN}Terima kasih telah menggunakan lab simulator.{ANSI.RESET}")
            break
        else:
            print(f"{ANSI.RED}Pilihan tidak valid. Silakan coba lagi.{ANSI.RESET}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{ANSI.YELLOW}Sesi lab dihentikan oleh user.{ANSI.RESET}")
        sys.exit(0)
