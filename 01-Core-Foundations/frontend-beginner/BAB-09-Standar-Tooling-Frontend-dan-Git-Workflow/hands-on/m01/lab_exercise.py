#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Standar Tooling Frontend dan Git Workflow
BAB 09: Standar Tooling Frontend & Git Workflow (frontend-beginner)

Modul Hands-on interaktif untuk memahami ekosistem tooling frontend modern:
1. Node/npm & Package Resolution
2. Linter (ESLint) & Formatter (Prettier) Rule Engine
3. Build Tool / Bundler (Vite / Rollup) Tree-shaking & Minification
4. Git Flow Lifecycle: Working Directory -> Staging Area -> Local Commit -> Branch & Merge
"""

import sys
import time
import os

# ANSI Color Codes untuk Terminal
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}========================================================================{RESET}
{MAGENTA}{BOLD}       SIMULATOR STANDAR TOOLING FRONTEND & GIT WORKFLOW (BAB 09)      {RESET}
{CYAN}{BOLD}========================================================================{RESET}
{DIM}Platform edukasi interaktif: Package Manager, Vite, Linter, & Git Workflow{RESET}
"""
    print(banner)


def progress_bar(task_name, duration=1.0, steps=20):
    """Menampilkan animasi loading bar sederhana."""
    print(f"{CYAN}➜ {task_name}...{RESET}")
    for i in range(steps + 1):
        percent = int((i / steps) * 100)
        bar = "█" * i + "░" * (steps - i)
        sys.stdout.write(f"\r  [{bar}] {percent}%")
        sys.stdout.flush()
        time.sleep(duration / steps)
    print(f" {GREEN}[SELESAI]{RESET}\n")


def simulate_package_manager():
    """Simulasi npm/pnpm dependency resolution dan package.json."""
    print(f"\n{BOLD}{BG_BLUE} [1] MODUL PACKAGE MANAGER (npm / pnpm / yarn) {RESET}\n")
    print(f"{YELLOW}Menganalisis file konfigurasi 'package.json'...{RESET}")

    sample_package_json = """{
  "name": "belajar-frontend-app",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "eslint src --ext .js,.jsx",
    "format": "prettier --write src/**/*.{js,css,html}"
  },
  "dependencies": {
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "eslint": "^8.57.0",
    "prettier": "^3.2.5",
    "vite": "^5.2.0"
  }
}"""
    print(f"{DIM}{sample_package_json}{RESET}\n")
    print(f"{CYAN}Pertanyaan Arsitektural:{RESET}")
    print("Mengapa 'vite' dan 'eslint' masuk ke 'devDependencies' sedangkan runtime dependency masuk ke 'dependencies'?")
    print(f"  {GREEN}Jawab:{RESET} devDependencies hanya dieksekusi saat pengembangan dan build pipeline,")
    print("  tidak diperlukan lagi oleh client browser saat bundle production dijalankan.\n")

    input(f"{DIM}Tekan [Enter] untuk menjalankan simulasi instalasi paket...{RESET}")
    progress_bar("Resolving dependency tree (lockfile validation)", duration=0.8)
    progress_bar("Fetching tarballs & linking node_modules/.bin", duration=1.0)
    print(f"{GREEN}✔ node_modules terisi! 142 paket terpasang tanpa kerentanan kritis.{RESET}\n")


def simulate_lint_and_format():
    """Simulasi ESLint static analysis dan Prettier automated formatting."""
    print(f"\n{BOLD}{BG_BLUE} [2] MODUL CODE QUALITY (ESLint & Prettier) {RESET}\n")

    dirty_code = """// src/main.js (KODE BELUM SESUAI STANDAR)
var username = "Budi" ;
let count=10
function calculateTotal(price,qty){
return price*qty
}
console.log( calculateTotal( 15000, 2 ) )
"""
    print(f"{RED}[KODE SEBELUM LINTING & FORMATTING]:{RESET}")
    print(f"{DIM}{dirty_code}{RESET}")

    print(f"{YELLOW}Menjalankan: npx eslint src/main.js{RESET}")
    time.sleep(0.5)
    print(f"{RED}✖ 2 Masalah Ditemukan (ESLint Rule Violation):{RESET}")
    print(f"  {RED}1:1{RESET}  error  'var' dilarang, gunakan 'const' atau 'let'        {DIM}no-var{RESET}")
    print(f"  {YELLOW}1:5{RESET}  warn   Variabel 'username' dideklarasikan tapi tidak dipakai {DIM}no-unused-vars{RESET}\n")

    print(f"{YELLOW}Menjalankan: npx prettier --write src/main.js{RESET}")
    time.sleep(0.5)
    print(f"{GREEN}✔ Semicolon diselaraskan, whitespace dirapikan, single quotes diterapkan.{RESET}\n")

    clean_code = """// src/main.js (HASIL PERBAIKAN)
const count = 10;

function calculateTotal(price, qty) {
  return price * qty;
}

console.log(calculateTotal(15000, 2));
"""
    print(f"{GREEN}[KODE SETELAH AUTO-FIX & PRETTIER]:{RESET}")
    print(f"{BOLD}{clean_code}{RESET}")


def simulate_vite_build():
    """Simulasi Vite development server (HMR) dan Rollup production bundler."""
    print(f"\n{BOLD}{BG_BLUE} [3] MODUL BUNDLER & DEV SERVER (Vite) {RESET}\n")
    print(f"{CYAN}Vite memanfaatkan Native ES Modules (ESM) pada mode development:{RESET}")
    print("Tidak perlu me-re-bundle seluruh aplikasi setiap kali ada perubahan file (HMR sub-millisecond).\n")

    print(f"{YELLOW}$ npm run build{RESET}")
    progress_bar("Vite v5.2.0 building for production", duration=0.7)
    progress_bar("Transforming modules with esbuild & rollup", duration=1.0)

    print(f"{GREEN}✔ Build selesai dalam 184ms! Direktori 'dist/' terbentuk:{RESET}")
    print(f"  {DIM}dist/index.html{RESET}                   {CYAN}0.45 kB{RESET}")
    print(f"  {DIM}dist/assets/index-a39f1c8b.css{RESET}    {CYAN}1.12 kB{RESET} │ gzip: 0.54 kB")
    print(f"  {DIM}dist/assets/index-8fe7d110.js{RESET}     {CYAN}4.89 kB{RESET} │ gzip: 2.10 kB\n")


def simulate_git_workflow():
    """Simulasi tahapan lifecycle Git: branch, staging, commit, dan PR review."""
    print(f"\n{BOLD}{BG_BLUE} [4] MODUL GIT WORKFLOW & COLLABORATION {RESET}\n")

    git_state = {
        "branch": "main",
        "working_tree": ["index.html", "src/styles.css"],
        "staging_area": [],
        "commits": ["init: initial commit"]
    }

    print(f"{CYAN}Status awal repository:{RESET}")
    print(f"  Current Branch : {BOLD}{git_state['branch']}{RESET}")
    print(f"  Working Tree   : {RED}{', '.join(git_state['working_tree'])} (untracked / modified){RESET}")
    print(f"  Staging Area   : {DIM}(kosong){RESET}\n")

    print(f"{YELLOW}Langkah 1: Membuat feature branch baru{RESET}")
    branch_name = "feat/navbar-responsive"
    git_state["branch"] = branch_name
    print(f"  $ git checkout -b {branch_name}")
    print(f"  {GREEN}✔ Switched to a new branch '{branch_name}'{RESET}\n")

    print(f"{YELLOW}Langkah 2: Memindahkan file ke Staging Area{RESET}")
    print(f"  $ git add src/styles.css")
    git_state["staging_area"].append("src/styles.css")
    git_state["working_tree"].remove("src/styles.css")
    print(f"  Staging (Changes to be committed) : {GREEN}{', '.join(git_state['staging_area'])}{RESET}")
    print(f"  Untracked (Working directory)      : {RED}{', '.join(git_state['working_tree'])}{RESET}\n")

    print(f"{YELLOW}Langkah 3: Melakukan Commit dengan Conventional Commits format{RESET}")
    commit_msg = "feat(navbar): tambahkan styling navigasi responsif mobile"
    print(f'  $ git commit -m "{commit_msg}"')
    git_state["commits"].append(commit_msg)
    git_state["staging_area"].clear()
    print(f"  {GREEN}✔ [feat/navbar-responsive 4b89f1a] {commit_msg}{RESET}")
    print("  1 file changed, 45 insertions(+)\n")

    print(f"{YELLOW}Langkah 4: Push ke Remote & Buat Pull Request (PR){RESET}")
    print(f"  $ git push -u origin {branch_name}")
    progress_bar("Pushing commit objects to origin", duration=0.8)
    print(f"  {GREEN}✔ Remote branch created: origin/{branch_name}{RESET}")
    print(f"  {CYAN}Pull Request #12 dibuka:{RESET} '{commit_msg}' [CI Checks: ESLint PASSED, Build PASSED]\n")


def run_interactive_quiz():
    """Kuis pemahaman cepat untuk memvalidasi pemahaman materi."""
    print(f"\n{BOLD}{BG_GREEN} [EVALUASI MANDIRI CEPAT] {RESET}\n")
    questions = [
        {
            "q": "Apa peran file 'package-lock.json' dalam proyek Node.js?",
            "options": [
                "1. Mengunci file kode agar tidak bisa diedit orang lain",
                "2. Menjamin versi pasti dependency yang diinstal identik di semua komputer tim",
                "3. Menggantikan peran Git dalam mencatat riwayat versi"
            ],
            "answer": "2"
        },
        {
            "q": "Perintah git mana yang memindahkan perubahan dari Staging Area ke commit history lokal?",
            "options": [
                "1. git add .",
                "2. git push origin main",
                "3. git commit -m 'pesan'"
            ],
            "answer": "3"
        }
    ]

    score = 0
    for idx, item in enumerate(questions, start=1):
        print(f"{BOLD}Pertanyaan {idx}: {item['q']}{RESET}")
        for opt in item["options"]:
            print(f"  {opt}")
        choice = input(f"{CYAN}Pilih jawaban Anda (1/2/3): {RESET}").strip()
        if choice == item["answer"]:
            print(f"{GREEN}✔ Jawaban Tepat!{RESET}\n")
            score += 1
        else:
            print(f"{RED}✘ Jawaban belum tepat. Pilihan yang benar adalah nomor {item['answer']}.{RESET}\n")

    print(f"{BOLD}Skor Evaluasi:{RESET} {score}/{len(questions)} berhasil dijawab dengan benar.")


def main():
    """Fungsi utama orchestrator simulator."""
    print_banner()
    while True:
        print(f"{BOLD}PILIHAN LAB EXERCISE:{RESET}")
        print("  1. Simulasi Package Manager (package.json & lockfile)")
        print("  2. Simulasi Linter & Formatter (ESLint & Prettier)")
        print("  3. Simulasi Modern Bundler (Vite)")
        print("  4. Simulasi Git Workflow (Branch, Stage, Commit, PR)")
        print("  5. Jalankan Seluruh Skenario (Pipeline Penuh)")
        print("  6. Kuis Evaluasi Konsep")
        print("  0. Keluar")

        choice = input(f"\n{CYAN}Masukkan nomor modul [0-6]: {RESET}").strip()

        if choice == "1":
            simulate_package_manager()
        elif choice == "2":
            simulate_lint_and_format()
        elif choice == "3":
            simulate_vite_build()
        elif choice == "4":
            simulate_git_workflow()
        elif choice == "5":
            simulate_package_manager()
            simulate_lint_and_format()
            simulate_vite_build()
            simulate_git_workflow()
            run_interactive_quiz()
        elif choice == "6":
            run_interactive_quiz()
        elif choice == "0":
            print(f"\n{GREEN}Lab selesai. Selamat belajar frontend engineering modern!{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}\n")

        input(f"{DIM}Tekan [Enter] untuk kembali ke menu utama...{RESET}")
        print("\n" + "-" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Program dihentikan oleh pengguna.{RESET}\n")
        sys.exit(0)
