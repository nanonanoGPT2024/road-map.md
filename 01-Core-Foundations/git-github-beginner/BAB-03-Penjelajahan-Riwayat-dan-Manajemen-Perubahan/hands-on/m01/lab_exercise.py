#!/usr/bin/env python3
"""
Lab Exercise: Penjelajahan Riwayat dan Manajemen Perubahan (Git Basics)
Modul 01 - Simulasi Interaktif Riwayat Commit, Navigasi HEAD, dan Diff Inspector.

Deskripsi:
Program mandiri (standalone) tanpa dependensi eksternal untuk mempelajari
dan memvisualisasikan bagaimana Git mengelola riwayat commit (DAG), inspeksi
perubahan (git diff & git show), serta navigasi state (HEAD & checkout).
"""

import sys
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Optional

# ANSI Color Codes untuk visualisasi terminal interaktif
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"
CLR_BG_DARK = "\033[40m"


class Commit:
    def __init__(self, message: str, author: str, parent_hash: Optional[str], files: Dict[str, str]):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.message = message
        self.author = author
        self.parent_hash = parent_hash
        self.files = files.copy()  # Snapshot berkas pada titik waktu commit
        
        # Kalkulasi hash SHA-1 realistis
        raw_content = f"{self.timestamp}|{message}|{author}|{parent_hash}|{files}"
        self.hash = hashlib.sha1(raw_content.encode("utf-8")).hexdigest()
        self.short_hash = self.hash[:7]


class GitRepositorySimulator:
    def __init__(self, repo_name: str = "belajar-git-riwayat"):
        self.repo_name = repo_name
        self.commits: Dict[str, Commit] = {}
        self.commit_history: List[str] = []  # List hash dari paling lama ke terbaru
        self.branches: Dict[str, str] = {"main": ""}
        self.current_branch: Optional[str] = "main"
        self.head_hash: Optional[str] = None
        self.working_directory: Dict[str, str] = {}
        self.staging_area: Dict[str, str] = {}
        
        # Inisialisasi basis data simulasi commit awal
        self._seed_initial_history()

    def _seed_initial_history(self):
        """Membuat beberapa commit realistis untuk latihan eksplorasi riwayat."""
        # Commit 1
        f1 = {"README.md": "# Proyek Portal Kampus\nDokumentasi sistem portal akademik.", "app.py": "print('Sistem v0.1-dev')"}
        c1 = Commit("feat: inisialisasi struktur proyek dan dokumentasi awal", "Siti Rahma <siti@kampus.ac.id>", None, f1)
        self.commits[c1.short_hash] = c1
        self.commit_history.append(c1.short_hash)

        # Commit 2
        f2 = f1.copy()
        f2["auth.py"] = "def login(user, pwd):\n    return user == 'admin'\n"
        f2["README.md"] += "\n- Modul autentikasi dasar ditambahkan."
        c2 = Commit("feat(auth): tambahkan modul login dasar", "Budi Santoso <budi@dev.id>", c1.short_hash, f2)
        self.commits[c2.short_hash] = c2
        self.commit_history.append(c2.short_hash)

        # Commit 3
        f3 = f2.copy()
        f3["auth.py"] = "def login(user, pwd):\n    # Bug fix: validasi string kosong\n    if not user or not pwd:\n        return False\n    return user == 'admin' and pwd == 'rahasia'\n"
        c3 = Commit("fix(auth): cegah login bypass dan verifikasi password", "Budi Santoso <budi@dev.id>", c2.short_hash, f3)
        self.commits[c3.short_hash] = c3
        self.commit_history.append(c3.short_hash)

        # Commit 4
        f4 = f3.copy()
        f4["database.py"] = "DB_URL = 'sqlite:///portal.db'\nprint('Database terkoneksi.')\n"
        f4["app.py"] = "import auth\nimport database\nprint('Portal Akademik Aktif')\n"
        c4 = Commit("feat(db): koneksi database sqlite dan integrasi server", "Andi Wijaya <andi@cloud.id>", c3.short_hash, f4)
        self.commits[c4.short_hash] = c4
        self.commit_history.append(c4.short_hash)

        # Set HEAD dan main branch
        self.branches["main"] = c4.short_hash
        self.head_hash = c4.short_hash
        self.working_directory = f4.copy()

    def log(self, oneline: bool = False, stat: bool = False):
        """Menampilkan riwayat commit serupa `git log`."""
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== RIWAYAT COMMIT (`git log`) ==={CLR_RESET}")
        if not self.commit_history:
            print(f"{CLR_YELLOW}Belum ada commit.{CLR_RESET}")
            return

        # Telusuri dari yang terbaru (reverse)
        for commit_hash in reversed(self.commit_history):
            c = self.commits[commit_hash]
            is_head = (commit_hash == self.head_hash)
            head_tag = f" {CLR_BOLD}{CLR_MAGENTA}(HEAD -> {self.current_branch if self.current_branch else 'detached'}){CLR_RESET}" if is_head else ""
            
            if oneline:
                print(f"{CLR_YELLOW}{c.short_hash}{CLR_RESET}{head_tag} {c.message} {CLR_DIM}({c.author.split()[0]}){CLR_RESET}")
            else:
                print(f"{CLR_YELLOW}commit {c.hash}{CLR_RESET}{head_tag}")
                print(f"Author: {c.author}")
                print(f"Date:   {c.timestamp}")
                print(f"\n    {CLR_BOLD}{c.message}{CLR_RESET}\n")
                if stat:
                    print(f"    {CLR_DIM}Snapshot files: {', '.join(c.files.keys())}{CLR_RESET}\n")

    def show(self, target_hash: str):
        """Menampilkan detail dan snapshot commit spesifik serupa `git show`."""
        target_hash = target_hash.strip()
        matching = [h for h in self.commits if h.startswith(target_hash)]
        if not matching:
            print(f"{CLR_RED}[ERROR] Commit '{target_hash}' tidak ditemukan.{CLR_RESET}")
            return

        c = self.commits[matching[0]]
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== DETAIL COMMIT (`git show {c.short_hash}`) ==={CLR_RESET}")
        print(f"{CLR_YELLOW}commit {c.hash}{CLR_RESET}")
        print(f"Author: {c.author}")
        print(f"Date:   {c.timestamp}")
        print(f"Parent: {c.parent_hash or 'None (Root Commit)'}")
        print(f"\n    {CLR_BOLD}{c.message}{CLR_RESET}\n")

        print(f"{CLR_BOLD}Daftar Berkas Terpantau:{CLR_RESET}")
        for filename, content in c.files.items():
            print(f"  {CLR_GREEN}* {filename}{CLR_RESET} ({len(content.splitlines())} baris)")
            for line in content.splitlines():
                print(f"    {CLR_DIM}| {line}{CLR_RESET}")
            print()

    def diff_commits(self, hash_a: str, hash_b: str):
        """Membandingkan perbedaan snapshot antara dua commit (`git diff commit1..commit2`)."""
        matching_a = [h for h in self.commits if h.startswith(hash_a)]
        matching_b = [h for h in self.commits if h.startswith(hash_b)]
        if not matching_a or not matching_b:
            print(f"{CLR_RED}[ERROR] Salah satu commit hash tidak valid.{CLR_RESET}")
            return

        c_a = self.commits[matching_a[0]]
        c_b = self.commits[matching_b[0]]

        print(f"\n{CLR_BOLD}{CLR_CYAN}=== PERBANDINGAN PERUBAHAN (`git diff {c_a.short_hash}..{c_b.short_hash}`) ==={CLR_RESET}")
        all_files = set(c_a.files.keys()).union(set(c_b.files.keys()))

        diff_count = 0
        for f in sorted(all_files):
            lines_a = c_a.files.get(f, "").splitlines()
            lines_b = c_b.files.get(f, "").splitlines()

            if lines_a != lines_b:
                diff_count += 1
                print(f"{CLR_BOLD}diff --git a/{f} b/{f}{CLR_RESET}")
                if f not in c_a.files:
                    print(f"{CLR_GREEN}--- berkas baru ditambahkan pada {c_b.short_hash} ---{CLR_RESET}")
                elif f not in c_b.files:
                    print(f"{CLR_RED}--- berkas dihapus pada {c_b.short_hash} ---{CLR_RESET}")
                
                # Sederhana line-by-line diff inspector
                set_a = set(lines_a)
                set_b = set(lines_b)
                for line in lines_a:
                    if line not in set_b:
                        print(f"{CLR_RED}- {line}{CLR_RESET}")
                for line in lines_b:
                    if line not in set_a:
                        print(f"{CLR_GREEN}+ {line}{CLR_RESET}")
                print()

        if diff_count == 0:
            print(f"{CLR_DIM}Tidak ada perbedaan konten berkas antara commit tersebut.{CLR_RESET}")

    def checkout(self, target: str):
        """Simulasi `git checkout` untuk berpindah HEAD antar commit atau branch."""
        target = target.strip()
        if target in self.branches:
            self.current_branch = target
            self.head_hash = self.branches[target]
            self.working_directory = self.commits[self.head_hash].files.copy()
            print(f"{CLR_GREEN}[SUKSES] Berpindah ke branch '{target}'. HEAD sekarang di {self.head_hash}.{CLR_RESET}")
            return

        matching = [h for h in self.commits if h.startswith(target)]
        if matching:
            chash = matching[0]
            self.current_branch = None  # Detached HEAD state
            self.head_hash = chash
            self.working_directory = self.commits[chash].files.copy()
            print(f"{CLR_YELLOW}[PERHATIAN] Memasuki state 'detached HEAD' pada commit {chash}.{CLR_RESET}")
            print(f"{CLR_DIM}Anda dapat menjelajahi riwayat lama tanpa mengubah riwayat branch utama.{CLR_RESET}")
            return

        print(f"{CLR_RED}[ERROR] Target branch atau commit '{target}' tidak ditemukan.{CLR_RESET}")

    def status(self):
        """Menampilkan status HEAD dan workspace saat ini."""
        branch_desc = f"branch {CLR_CYAN}{self.current_branch}{CLR_RESET}" if self.current_branch else f"{CLR_MAGENTA}HEAD detached at {self.head_hash}{CLR_RESET}"
        print(f"\n{CLR_BOLD}=== STATUS REPOSITORI ==={CLR_RESET}")
        print(f"Posisi: {branch_desc}")
        print(f"HEAD Commit : {CLR_YELLOW}{self.head_hash}{CLR_RESET} -> {self.commits[self.head_hash].message}")
        print(f"Berkas aktif di Working Directory:")
        for fn in self.working_directory:
            print(f"  - {fn}")


def print_banner():
    banner = f"""{CLR_CYAN}{CLR_BOLD}
========================================================================
 LAB SIMULATOR: PENJELAJAHAN RIWAYAT & MANAJEMEN PERUBAHAN GIT (BAB-03)
 Interaktif: Eksplorasi Log, Tree Commit, Git Show, dan Inspeksi Diff
========================================================================{CLR_RESET}
"""
    print(banner)


def show_menu():
    print(f"""{CLR_BOLD}PILIHAN PERINTAH GIT:{CLR_RESET}
 {CLR_GREEN}1{CLR_RESET}. `git log`               : Tampilkan riwayat commit lengkap
 {CLR_GREEN}2{CLR_RESET}. `git log --oneline`     : Tampilkan riwayat commit ringkas 1 baris
 {CLR_GREEN}3{CLR_RESET}. `git log --stat`        : Tampilkan riwayat commit disertai berkas terdampak
 {CLR_GREEN}4{CLR_RESET}. `git show <hash>`       : Inspeksi detail 1 commit dan konten berkasnya
 {CLR_GREEN}5{CLR_RESET}. `git diff <c1>..<c2>`   : Bandingkan perbedaan dua titik commit
 {CLR_GREEN}6{CLR_RESET}. `git checkout <target>` : Pindah HEAD ke commit tertentu (Time-travel/Detached)
 {CLR_GREEN}7{CLR_RESET}. `git status`            : Periksa posisi HEAD dan berkas aktif saat ini
 {CLR_GREEN}8{CLR_RESET}. Auto-Demo Eksplorasi    : Jalankan simulasi panduan skenario belajar
 {CLR_RED}0{CLR_RESET}. Keluar
""")


def run_interactive_lab():
    repo = GitRepositorySimulator()
    print_banner()
    print(f"{CLR_WHITE}Selamat datang di Lab Mandiri. Repositori simulasi telah dimuat dengan 4 riwayat commit.{CLR_RESET}\n")

    # Jika berjalan di lingkungan non-interaktif atau batch test
    if not sys.stdin.isatty():
        print(f"{CLR_YELLOW}[INFO] Mode non-interaktif terdeteksi. Menjalankan auto-demo terpadu...{CLR_RESET}")
        run_guided_demo(repo)
        return

    while True:
        show_menu()
        try:
            choice = input(f"{CLR_BOLD}Ketik pilihan (0-8): {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            repo.log(oneline=False)
        elif choice == "2":
            repo.log(oneline=True)
        elif choice == "3":
            repo.log(stat=True)
        elif choice == "4":
            chash = input(f"Masukkan 7 karakter short-hash commit (misal {repo.commit_history[0]}): ").strip()
            repo.show(chash)
        elif choice == "5":
            c1 = input(f"Masukkan hash commit awal  (misal {repo.commit_history[0]}): ").strip()
            c2 = input(f"Masukkan hash commit akhir (misal {repo.commit_history[-1]}): ").strip()
            repo.diff_commits(c1, c2)
        elif choice == "6":
            target = input(f"Masukkan hash commit tujuan atau 'main': ").strip()
            repo.checkout(target)
        elif choice == "7":
            repo.status()
        elif choice == "8":
            run_guided_demo(repo)
        elif choice == "0":
            print(f"{CLR_GREEN}Terima kasih telah berlatih penjelajahan riwayat Git!{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid, silakan ulangi.{CLR_RESET}")
        
        print("\n" + "-" * 65 + "\n")


def run_guided_demo(repo: GitRepositorySimulator):
    """Menjalankan skenario terpandu untuk demonstrasi instan pemahaman konsep BAB-03."""
    print(f"\n{CLR_BOLD}{CLR_YELLOW}=== [DEMO TERPANDU]: LANGKAH 1 - ANALISIS RIWAYAT DENGAN GIT LOG ==={CLR_RESET}")
    repo.log(oneline=True)

    print(f"\n{CLR_BOLD}{CLR_YELLOW}=== [DEMO TERPANDU]: LANGKAH 2 - INSPEKSI KONTEN DENGAN GIT SHOW ==={CLR_RESET}")
    first_commit = repo.commit_history[0]
    repo.show(first_commit)

    print(f"\n{CLR_BOLD}{CLR_YELLOW}=== [DEMO TERPANDU]: LANGKAH 3 - MEMBANDINGKAN EVOLUSI KODE DENGAN GIT DIFF ==={CLR_RESET}")
    c_auth = repo.commit_history[1]
    c_fix = repo.commit_history[2]
    repo.diff_commits(c_auth, c_fix)

    print(f"\n{CLR_BOLD}{CLR_YELLOW}=== [DEMO TERPANDU]: LANGKAH 4 - TIME TRAVEL / DETACHED HEAD STATE ==={CLR_RESET}")
    print(f"{CLR_WHITE}Mencoba checkout ke titik commit awal {first_commit}:{CLR_RESET}")
    repo.checkout(first_commit)
    repo.status()

    print(f"\n{CLR_WHITE}Kembali ke branch utama 'main':{CLR_RESET}")
    repo.checkout("main")
    repo.status()
    print(f"\n{CLR_GREEN}{CLR_BOLD}[SUKSES] Skenario demo selesai dengan validasi penuh.{CLR_RESET}")


if __name__ == "__main__":
    run_interactive_lab()
