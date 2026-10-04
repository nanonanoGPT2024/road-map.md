#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif GitHub Actions & Otomasi CI/CD
BAB-10: Otomasi Dasar CI/CD (GitHub Actions)
Repository: git-github-beginner

Simulasi ini mendemonstrasikan bagaimana GitHub Actions merespons trigger (event),
mengalokasikan runner, mengeksekusi step secara berurutan, mengelola status check,
dan memblokir merge saat build gagal.
"""

import sys
import time
import random
from typing import List, Dict, Any

# ==========================================
# Konfigurasi Warna ANSI Terminal
# ==========================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"

def print_header(title: str):
    print(f"\n{Style.BOLD}{Style.CYAN}{'=' * 65}{Style.RESET}")
    print(f"{Style.BOLD}{Style.WHITE}  GITHUB ACTIONS SIMULATOR: {title.upper()}{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}{'=' * 65}{Style.RESET}\n")

def print_step(icon: str, step_name: str, runner: str = "ubuntu-latest"):
    print(f"{Style.BOLD}{Style.BLUE}[RUNNER: {runner}]{Style.RESET} {icon} {Style.WHITE}{step_name}...{Style.RESET}", end="", flush=True)

def print_success(detail: str = "Completed successfully"):
    print(f"\r  {Style.GREEN}✓ [PASS]{Style.RESET} {detail}")

def print_failure(detail: str = "Failed with exit code 1"):
    print(f"\r  {Style.RED}✗ [FAIL]{Style.RESET} {Style.BOLD}{detail}{Style.RESET}")

# ==========================================
# Komponen Simulasi Workflow
# ==========================================
SAMPLE_YAML = """name: Python CI/CD Pipeline

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install flake8 pytest

      - name: Lint with Flake8
        run: |
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

      - name: Run Unit Tests
        run: |
          pytest --maxfail=1 --disable-warnings -q

      - name: Upload Test Artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-${{ matrix.python-version }}
          path: pytest-report.xml
"""

def display_workflow_yaml():
    print_header("Workflow YAML Definition (.github/workflows/ci.yml)")
    lines = SAMPLE_YAML.strip().split("\n")
    for i, line in enumerate(lines, 1):
        if line.startswith("name:") or line.startswith("on:") or line.startswith("jobs:"):
            print(f"{Style.YELLOW}{i:2d} | {Style.BOLD}{line}{Style.RESET}")
        elif "uses:" in line or "run:" in line:
            print(f"{Style.CYAN}{i:2d} | {line}{Style.RESET}")
        elif "matrix:" in line:
            print(f"{Style.MAGENTA}{i:2d} | {line}{Style.RESET}")
        else:
            print(f"{Style.DIM}{i:2d} |{Style.RESET} {line}")
    print(f"\n{Style.DIM}File di atas ditempatkan di: .github/workflows/ci.yml{Style.RESET}\n")

def simulate_pipeline(fail_at: str = None, python_ver: str = "3.11") -> bool:
    print_header(f"Simulasi Workflow Job (Python {python_ver})")
    steps = [
        ("actions/checkout@v4", "Memeriksa dan mengunduh commit git tree (SHA: 4fa9b12)"),
        ("actions/setup-python@v5", f"Mengonfigurasi environment Python {python_ver} + pip cache"),
        ("pip install", "Menginstal dependencies (flake8, pytest, requests)"),
        ("flake8 linter", "Menganalisis sintaks dan PEP8 static code analysis"),
        ("pytest runner", "Menjalankan 14 unit tests pada modul aplikasi"),
        ("actions/upload-artifact@v4", f"Mengompresi dan mengunggah log test-report-{python_ver}.xml")
    ]

    start_time = time.time()
    for name, desc in steps:
        time.sleep(0.35)
        print_step("⚙️ ", f"{name} - {desc}")
        time.sleep(0.45)

        if fail_at and fail_at.lower() in name.lower():
            if "flake8" in fail_at.lower():
                print_failure(f"{name} Error: SyntaxError pada app/main.py baris 42 (IndentationError)")
            elif "pytest" in fail_at.lower():
                print_failure(f"{name} Error: AssertionError pada test_auth.py: test_login_token_expiry FAILED")
            else:
                print_failure(f"{name} Error: Command returned non-zero exit status")
            print(f"\n{Style.BG_RED}{Style.WHITE} [WORKFLOW TERMINATED] Status Check: FAILED {Style.RESET}")
            print(f"{Style.RED}Pull Request merge status: BLOCKED oleh GitHub Branch Protection Rule.{Style.RESET}\n")
            return False

        print_success(f"{name} sukses dalam {(random.uniform(0.8, 2.4)):.2f}s")

    elapsed = time.time() - start_time
    print(f"\n{Style.BG_GREEN}{Style.WHITE} [WORKFLOW COMPLETED] Status Check: ALL CHECKS PASSED ({elapsed:.2f}s) {Style.RESET}")
    print(f"{Style.GREEN}Commit berstatus 'Green' ✓ - Siap untuk Auto-Merge ke branch main.{Style.RESET}\n")
    return True

def simulate_matrix_build():
    print_header("Simulasi GitHub Actions Matrix Build")
    print(f"{Style.YELLOW}Matrix Strategy mentrigger 3 job paralel pada runner yang berbeda:{Style.RESET}\n")
    versions = ["3.10", "3.11", "3.12"]
    results = {}

    for ver in versions:
        print(f"{Style.BOLD}--- Memulai Matrix Job: [Python {ver} on ubuntu-latest] ---{Style.RESET}")
        time.sleep(0.3)
        res = simulate_pipeline(fail_at=None, python_ver=ver)
        results[ver] = res

    print(f"{Style.BOLD}Ringkasan Matriks Pengujian:{Style.RESET}")
    for ver, passed in results.items():
        status = f"{Style.GREEN}✓ PASSED{Style.RESET}" if passed else f"{Style.RED}✗ FAILED{Style.RESET}"
        print(f"  • Runner Python {ver}: {status}")
    print(f"\n{Style.CYAN}Matriks memastikan dependensi kode kompatibel lintas versi Python!{Style.RESET}\n")

def interactive_quiz():
    print_header("Kuis Evaluasi Pemahaman CI/CD GitHub Actions")
    questions = [
        {
            "q": "Direktori manakah tempat file konfigurasi GitHub Actions wajib diletakkan?",
            "opt": ["A. .git/workflows/", "B. .github/workflows/", "C. .github/actions/", "D. config/ci/"],
            "ans": "B",
            "expl": "File workflow wajib berekstensi .yml atau .yaml dan berada di subfolder '.github/workflows/'."
        },
        {
            "q": "Keyword apa yang digunakan untuk menentukan trigger (seperti push atau pull_request)?",
            "opt": ["A. trigger:", "B. when:", "C. on:", "D. events:"],
            "ans": "C",
            "expl": "Keyword 'on:' mendefinisikan event apa yang memicu eksekusi workflow."
        },
        {
            "q": "Apa kegunaan dari 'actions/checkout@v4' pada awal workflow?",
            "opt": [
                "A. Membayar tagihan cloud GitHub",
                "B. Mengunduh source code repositori ke lingkungan runner",
                "C. Melakukan commit perubahan otomatis",
                "D. Memeriksa lisensi open-source"
            ],
            "ans": "B",
            "expl": "Runner bermula dalam kondisi kosong (clean VM/container). actions/checkout mengkloning repo agar file project dapat diakses runner."
        },
        {
            "q": "Jika salah satu step bernilai gagal (exit code != 0), apa default behavior GitHub Actions?",
            "opt": [
                "A. Tetap lanjut ke step berikutnya",
                "B. Mengulang step tersebut 10 kali",
                "C. Menghentikan eksekusi step berikutnya dan menandai job sebagai FAILED",
                "D. Menghapus repositori"
            ],
            "ans": "C",
            "expl": "Secara default, GitHub Actions menggunakan 'fail-fast' sehingga step berikutnya dibatalkan kecuali diberi klausul 'if: always()'."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"{Style.BOLD}{Style.YELLOW}Pertanyaan {idx}/{len(questions)}:{Style.RESET} {item['q']}")
        for opt in item["opt"]:
            print(f"  {opt}")
        user_choice = input(f"{Style.CYAN}Pilihan Anda (A/B/C/D): {Style.RESET}").strip().upper()
        if user_choice == item["ans"]:
            print(f"{Style.GREEN}✓ Benar!{Style.RESET} {item['expl']}\n")
            score += 1
        else:
            print(f"{Style.RED}✗ Salah.{Style.RESET} Jawaban benar adalah {item['ans']}. {item['expl']}\n")

    print(f"{Style.BOLD}Skor Akhir: {score} / {len(questions)}{Style.RESET}")
    if score == len(questions):
        print(f"{Style.GREEN}Luar biasa! Pemahaman fondasi GitHub Actions Anda sempurna.{Style.RESET}\n")
    else:
        print(f"{Style.YELLOW}Tetap semangat! Pelajari kembali struktur workflow dan lifecycle runner.{Style.RESET}\n")

def main():
    while True:
        print(f"\n{Style.BOLD}{Style.MAGENTA}=== LAB EXERCISE: OTOMASI CI/CD GITHUB ACTIONS (BAB 10) ==={Style.RESET}")
        print("1. Tampilkan Blueprint Workflow YAML (.github/workflows/ci.yml)")
        print("2. Jalankan Simulasi Workflow CI Normal (Semua Step Lolos/Green)")
        print("3. Jalankan Simulasi Broken Build (Gagal di Linting / Syntax Error)")
        print("4. Jalankan Simulasi Broken Build (Gagal di Unit Testing / Pytest)")
        print("5. Jalankan Simulasi Matrix Multi-Version Build (Python 3.10, 3.11, 3.12)")
        print("6. Kuis Pemahaman Teori & Praktik CI/CD")
        print("0. Keluar dari Lab")

        choice = input(f"\n{Style.CYAN}Pilih menu [0-6]: {Style.RESET}").strip()

        if choice == "1":
            display_workflow_yaml()
        elif choice == "2":
            simulate_pipeline()
        elif choice == "3":
            simulate_pipeline(fail_at="flake8")
        elif choice == "4":
            simulate_pipeline(fail_at="pytest")
        elif choice == "5":
            simulate_matrix_build()
        elif choice == "6":
            interactive_quiz()
        elif choice == "0":
            print(f"\n{Style.GREEN}Lab exercise selesai. Terus berlatih otomasi repositori Anda!{Style.RESET}\n")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan masukkan angka 0-6.{Style.RESET}")

if __name__ == "__main__":
    main()
