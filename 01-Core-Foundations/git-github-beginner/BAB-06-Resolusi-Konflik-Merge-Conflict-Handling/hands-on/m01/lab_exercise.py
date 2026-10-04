#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Resolusi Konflik Git (Merge Conflict Handling)
BAB-06: Resolusi Konflik (Merge Conflict Handling) - git-github-beginner

Simulasi mandiri untuk memahami anatomi marker konflik Git, alur deteksi,
pemilihan strategi resolusi (ours vs theirs vs manual merge), staging, hingga commit penyelesaian.
"""

import sys
import time

# --- ANSI Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_RED = "\033[41m"
CLR_BG_GREEN = "\033[42m"


def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}======================================================================
  GIT HANDS-ON LAB: SIMULATOR MERGE CONFLICT RESOLUTION
  BAB-06: Resolusi Konflik & Manajemen Percabangan
======================================================================{CLR_RESET}
    """
    print(banner)


def print_step(step_num: int, title: str):
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[LANGKAH {step_num}] {title}{CLR_RESET}")
    print(f"{CLR_DIM}{'-' * 60}{CLR_RESET}")


def show_conflict_file(content_conflict: str):
    print(f"\n{CLR_BOLD}File: {CLR_CYAN}server_config.py{CLR_RESET}")
    print(f"{CLR_DIM}------------------------------------------------------------{CLR_RESET}")
    for line in content_conflict.splitlines():
        if line.startswith("<<<<<<<"):
            print(f"{CLR_RED}{CLR_BOLD}{line}  <-- Penanda awal branch target (HEAD / main){CLR_RESET}")
        elif line.startswith("======="):
            print(f"{CLR_YELLOW}{CLR_BOLD}{line}  <-- Pembatas kedua versi perubahan{CLR_RESET}")
        elif line.startswith(">>>>>>>"):
            print(f"{CLR_BLUE}{CLR_BOLD}{line}  <-- Penanda akhir branch sumber (feature/api-v2){CLR_RESET}")
        elif "PORT = 8080" in line or "AUTH_PROVIDER = 'oauth2'" in line:
            print(f"  {CLR_GREEN}+ {line}{CLR_RESET}")
        elif "PORT = 9000" in line or "AUTH_PROVIDER = 'jwt_token'" in line:
            print(f"  {CLR_MAGENTA}* {line}{CLR_RESET}")
        else:
            print(f"    {line}")
    print(f"{CLR_DIM}------------------------------------------------------------{CLR_RESET}")


def main():
    print_banner()

    print(f"{CLR_BOLD}Skenario:{CLR_RESET}")
    print("Anda berada di branch 'main'. Anda menjalankan perintah:")
    print(f"  {CLR_CYAN}$ git merge feature/api-v2{CLR_RESET}")
    print(f"\n{CLR_RED}Auto-merging server_config.py{CLR_RESET}")
    print(f"{CLR_RED}{CLR_BOLD}CONFLICT (content): Merge conflict in server_config.py{CLR_RESET}")
    print(f"{CLR_YELLOW}Automatic merge failed; fix conflicts and then commit the result.{CLR_RESET}")

    conflict_data = """import os

# Konfigurasi Server Utama
APP_NAME = "E-Commerce Gateway"
DEBUG = False

<<<<<<< HEAD (Branch: main)
PORT = 8080
AUTH_PROVIDER = "oauth2"
TIMEOUT_SECONDS = 30
=======
PORT = 9000
AUTH_PROVIDER = "jwt_token"
TIMEOUT_SECONDS = 45
>>>>>>> feature/api-v2

DATABASE_URL = os.getenv("DB_URL", "sqlite:///prod.db")
"""

    resolved_content = ""

    # Langkah 1: Pemeriksaan Status & Marker
    print_step(1, "Inspeksi Status dan Anatomi Marker Konflik")
    print("Melihat status git saat ini:")
    print(f"  {CLR_CYAN}$ git status{CLR_RESET}")
    print(f"  On branch {CLR_GREEN}main{CLR_RESET}")
    print(f"  You have unmerged paths.")
    print(f"    (fix conflicts and run 'git commit')")
    print(f"    (use 'git merge --abort' to abort the merge)")
    print(f"  Unmerged paths:")
    print(f"    {CLR_RED}both modified:   server_config.py{CLR_RESET}")

    show_conflict_file(conflict_data)

    # Langkah 2: Pilihan Strategi Resolusi
    print_step(2, "Menentukan Strategi Resolusi Konflik")
    print("Pilih opsi resolusi di bawah ini:")
    print(f"  {CLR_CYAN}[1]{CLR_RESET} Pertahankan Versi HEAD (main)       -> PORT=8080, AUTH='oauth2', TIMEOUT=30")
    print(f"  {CLR_CYAN}[2]{CLR_RESET} Terima Versi Feature (incoming)      -> PORT=9000, AUTH='jwt_token', TIMEOUT=45")
    print(f"  {CLR_CYAN}[3]{CLR_RESET} Manual Merge / Rekonsiliasi Ideal    -> PORT=9000, AUTH='oauth2' + 'jwt_token', TIMEOUT=45")
    print(f"  {CLR_CYAN}[4]{CLR_RESET} Batalkan Merge (git merge --abort)")

    choice = ""
    try:
        choice = input(f"\n{CLR_YELLOW}Pilih opsi (1/2/3/4) [default: 3]: {CLR_RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "3"

    if not choice:
        choice = "3"

    if choice == "1":
        print(f"\n{CLR_GREEN}[OK] Menerapkan strategi: Accept Current Change (ours / HEAD){CLR_RESET}")
        resolved_block = """PORT = 8080
AUTH_PROVIDER = "oauth2"
TIMEOUT_SECONDS = 30"""
    elif choice == "2":
        print(f"\n{CLR_GREEN}[OK] Menerapkan strategi: Accept Incoming Change (theirs / feature){CLR_RESET}")
        resolved_block = """PORT = 9000
AUTH_PROVIDER = "jwt_token"
TIMEOUT_SECONDS = 45"""
    elif choice == "4":
        print(f"\n{CLR_RED}[ABORT] Menjalankan: git merge --abort{CLR_RESET}")
        print("Working tree dikembalikan ke kondisi sebelum perintah merge dijalankan.")
        print(f"{CLR_GREEN}Status: Bersih (HEAD detached / main normal). Selesai.{CLR_RESET}")
        return
    else:
        print(f"\n{CLR_GREEN}[OK] Menerapkan strategi: Manual Merge & Best-of-both-worlds{CLR_RESET}")
        resolved_block = """# Rekonsiliasi: Menggunakan port modern dan dual authentication
PORT = 9000
AUTH_PROVIDER = "oauth2,jwt_token"
TIMEOUT_SECONDS = 45"""

    resolved_content = f"""import os

# Konfigurasi Server Utama
APP_NAME = "E-Commerce Gateway"
DEBUG = False

{resolved_block}

DATABASE_URL = os.getenv("DB_URL", "sqlite:///prod.db")
"""

    # Langkah 3: Verifikasi File Setelah Resolusi
    print_step(3, "Verifikasi File Tanpa Marker Konflik")
    print(f"File {CLR_CYAN}server_config.py{CLR_RESET} berhasil diedit. Semua marker (<<<, ===, >>>) telah dibersihkan:")
    print(f"{CLR_DIM}------------------------------------------------------------{CLR_RESET}")
    for line in resolved_content.splitlines():
        if "PORT" in line or "AUTH_PROVIDER" in line or "TIMEOUT" in line:
            print(f"  {CLR_GREEN}{line}{CLR_RESET}")
        else:
            print(f"    {line}")
    print(f"{CLR_DIM}------------------------------------------------------------{CLR_RESET}")

    # Langkah 4: Staging (Mark as Resolved)
    print_step(4, "Menandai Konflik Terselesaikan (git add)")
    print("Dalam Git, menandai bahwa konflik sudah terselesaikan dilakukan dengan 'git add':")
    print(f"  {CLR_CYAN}$ git add server_config.py{CLR_RESET}")
    time.sleep(0.3)
    print(f"  {CLR_CYAN}$ git status{CLR_RESET}")
    print(f"  On branch {CLR_GREEN}main{CLR_RESET}")
    print("  All conflicts fixed but you are still merging.")
    print("    (use 'git commit' to conclude merge)")
    print("  Changes to be committed:")
    print(f"    {CLR_GREEN}modified:   server_config.py{CLR_RESET}")

    # Langkah 5: Finalisasi dengan Merge Commit
    print_step(5, "Membuat Merge Commit Penutup")
    commit_msg = 'Merge branch "feature/api-v2" into main (Resolved config conflicts)'
    print(f"Menjalankan perintah:")
    print(f"  {CLR_CYAN}$ git commit -m '{commit_msg}'{CLR_RESET}")
    time.sleep(0.3)
    print(f"  {CLR_GREEN}[main a81e9f2] {commit_msg}{CLR_RESET}")

    # Ringkasan Filosofis
    print_step(6, "Ringkasan Pembelajaran Kunci (Takeaway)")
    summary_points = [
        ("Marker <<<<<<< HEAD", "Menunjukkan baris kode lokal/target sebelum garis =======."),
        ("Marker >>>>>>> branch", "Menunjukkan baris kode dari branch yang sedang digabungkan."),
        ("Penghapusan Marker Wajib", "Jangan pernah men-commit file yang masih memuat marker <<<<, ====, >>>>."),
        ("Penyelesaian = git add", "Perintah 'git add <file>' memberi tahu Git bahwa benturan isi file sudah tuntas."),
        ("git merge --abort", "Gunakan opsi ini jika ragu dan ingin membatalkan proses merge kembali ke titik awal."),
    ]
    for key, desc in summary_points:
        print(f"  * {CLR_BOLD}{key:<25}{CLR_RESET}: {desc}")

    print(f"\n{CLR_GREEN}{CLR_BOLD}[SUKSES] Simulasi resolusi konflik Git selesai dengan sempurna!{CLR_RESET}\n")


if __name__ == "__main__":
    main()
