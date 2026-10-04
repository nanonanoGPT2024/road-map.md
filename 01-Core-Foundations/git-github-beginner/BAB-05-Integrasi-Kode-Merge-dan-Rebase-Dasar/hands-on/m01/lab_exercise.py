#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Git Merge vs Git Rebase Dasar
BAB-05: Integrasi Kode - Merge dan Rebase Dasar (git-github-beginner)

Simulator terminal mandiri tanpa ketergantungan library eksternal.
Memvisualisasikan tree commit, pergerakan HEAD branch, fast-forward merge,
3-way recursive merge, simulasi merge conflict, serta rebase linear history.
"""

import sys
import time
from typing import List, Dict, Optional


class AnsiColor:
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
    BG_RED = "\033[41m"


class Commit:
    def __init__(self, commit_id: str, message: str, parents: Optional[List[str]] = None):
        self.commit_id = commit_id
        self.message = message
        self.parents = parents if parents is not None else []

    def __repr__(self):
        return f"Commit({self.commit_id}: {self.message})"


class GitGraphSimulator:
    def __init__(self):
        self.reset_repository()

    def reset_repository(self):
        """Mengatur ulang kondisi awal repository tiruan."""
        self.commits: Dict[str, Commit] = {
            "c1": Commit("c1", "Initial project commit", []),
            "c2": Commit("c2", "Add base configuration & README", ["c1"]),
        }
        self.branches: Dict[str, str] = {
            "main": "c2",
            "feature": "c2"
        }
        self.active_branch: str = "main"
        self.counter: int = 3

    def print_header(self, title: str):
        print(f"\n{AnsiColor.CYAN}{'=' * 65}{AnsiColor.RESET}")
        print(f"{AnsiColor.BOLD}{AnsiColor.WHITE} [SIMULATOR] {title} {AnsiColor.RESET}")
        print(f"{AnsiColor.CYAN}{'=' * 65}{AnsiColor.RESET}")

    def show_graph(self):
        """Menampilkan representasi visual commit tree di terminal."""
        print(f"\n{AnsiColor.YELLOW}--- Status Branch & Pohon Komit Saat Ini ---{AnsiColor.RESET}")
        for branch, commit_id in self.branches.items():
            is_active = (branch == self.active_branch)
            marker = f"{AnsiColor.GREEN}* (HEAD){AnsiColor.RESET}" if is_active else " "
            print(f"  Branch {AnsiColor.BOLD}{branch:10}{AnsiColor.RESET} -> Commit: {AnsiColor.CYAN}{commit_id}{AnsiColor.RESET} {marker}")

        print(f"\n{AnsiColor.DIM}Daftar Node Commit Terdaftar:{AnsiColor.RESET}")
        for cid, obj in self.commits.items():
            parent_str = ", ".join(obj.parents) if obj.parents else "None"
            print(f"  [{AnsiColor.BOLD}{cid}{AnsiColor.RESET}] {obj.message} (Parents: {parent_str})")
        print()

    def create_commit(self, branch: str, message: str) -> str:
        cid = f"c{self.counter}"
        self.counter += 1
        parent = self.branches[branch]
        self.commits[cid] = Commit(cid, message, [parent])
        self.branches[branch] = cid
        return cid

    def demo_fast_forward_merge(self):
        """
        Skenario 1: Fast-Forward Merge.
        main tidak bergerak, feature maju 2 commit.
        Ketika main melakukan merge feature, pointer main tinggal loncat maju.
        """
        self.reset_repository()
        self.print_header("Skenario 1: Fast-Forward (FF) Merge")
        print(f"{AnsiColor.WHITE}Skenario:{AnsiColor.RESET} Branch 'feature' dibuat dari 'main'.")
        print("Branch 'feature' menambahkan 2 commit baru, sementara 'main' tidak bergerak sama sekali.")

        c3 = self.create_commit("feature", "feat: create auth middleware")
        c4 = self.create_commit("feature", "feat: implement login JWT token")

        print(f"{AnsiColor.GREEN}+ Ditambahkan commit di feature:{AnsiColor.RESET} {c3}, {c4}")
        self.show_graph()

        input(f"{AnsiColor.DIM}Tekan [Enter] untuk menjalankan: git checkout main && git merge feature ...{AnsiColor.RESET}")

        print(f"\n{AnsiColor.BOLD}Eksekusi Perintah:{AnsiColor.RESET}")
        print(f"$ git checkout main")
        print(f"$ git merge feature")
        time.sleep(0.6)

        # Lakukan Fast Forward
        self.branches["main"] = self.branches["feature"]
        print(f"\n{AnsiColor.BG_GREEN}{AnsiColor.BOLD} HASIL FAST-FORWARD {AnsiColor.RESET}")
        print(f"Tidak ada commit merge baru yang dibuat! Pointer 'main' langsung loncat ke {self.branches['feature']}.")
        self.show_graph()

    def demo_three_way_merge(self):
        """
        Skenario 2: 3-Way (Recursive/Ort) Merge.
        main dan feature sama-sama memiliki commit baru yang divergen.
        Git membuat satu 'Merge Commit' baru dengan 2 parents.
        """
        self.reset_repository()
        self.print_header("Skenario 2: 3-Way Merge (Divergent History)")
        print(f"{AnsiColor.WHITE}Skenario:{AnsiColor.RESET} Sejarah telah divergen (bercabang).")
        print("- Di 'main': ada perbaikan hotfix dari anggota tim lain.")
        print("- Di 'feature': ada implementasi fitur dashboard.")

        c3 = self.create_commit("feature", "feat: add user analytics dashboard")
        c4 = self.create_commit("main", "fix: security patch on session validation")

        print(f"{AnsiColor.GREEN}+ Commit divergen dibuat:{AnsiColor.RESET}")
        print(f"  feature -> {c3}")
        print(f"  main    -> {c4}")
        self.show_graph()

        input(f"{AnsiColor.DIM}Tekan [Enter] untuk menjalankan: git merge feature (dari branch main)...{AnsiColor.RESET}")

        print(f"\n{AnsiColor.BOLD}Eksekusi Perintah:{AnsiColor.RESET}")
        print(f"$ git merge feature")
        time.sleep(0.6)

        # Buat merge commit dengan 2 parents
        merge_cid = f"c{self.counter}"
        self.counter += 1
        self.commits[merge_cid] = Commit(
            merge_cid,
            "Merge branch 'feature' into main",
            [self.branches["main"], self.branches["feature"]]
        )
        self.branches["main"] = merge_cid

        print(f"\n{AnsiColor.BG_BLUE}{AnsiColor.BOLD} HASIL 3-WAY MERGE {AnsiColor.RESET}")
        print(f"Merge commit otomatis dibuat: {AnsiColor.CYAN}{merge_cid}{AnsiColor.RESET}")
        print("Commit ini memiliki 2 orang tua (parents), mempertahankan riwayat percabangan asli.")
        self.show_graph()

    def demo_merge_conflict(self):
        """
        Skenario 3: Simulasi Konflik Merge & Penyelesaian Manual.
        """
        self.print_header("Skenario 3: Simulasi Merge Conflict & Resolusi")
        print("Kedua branch mengubah baris yang SAMA pada file 'settings.json':")
        print(f"  Branch main    -> {AnsiColor.RED}\"MAX_CONCURRENT_USERS\": 500{AnsiColor.RESET}")
        print(f"  Branch feature -> {AnsiColor.GREEN}\"MAX_CONCURRENT_USERS\": 1000{AnsiColor.RESET}")

        print(f"\n{AnsiColor.YELLOW}Tampilan file saat terjadi CONFLICT:{AnsiColor.RESET}")
        conflict_marker = f"""<<<<<<< HEAD (main)
"MAX_CONCURRENT_USERS": 500
=======
"MAX_CONCURRENT_USERS": 1000
>>>>>>> feature"""
        print(f"{AnsiColor.DIM}{conflict_marker}{AnsiColor.RESET}\n")

        print("Pilihan resolusi Anda:")
        print("  1. Gunakan versi main (500)")
        print("  2. Gunakan versi feature (1000)")
        print("  3. Kompromi manual arsitektur tim (misal: 750)")

        choice = input(f"{AnsiColor.BOLD}Pilih nomor resolusi (1/2/3): {AnsiColor.RESET}").strip()
        if choice == "1":
            resolved_val = "500 (diambil dari main)"
        elif choice == "2":
            resolved_val = "1000 (diambil dari feature)"
        else:
            resolved_val = "750 (hasil mufakat teknis)"

        print(f"\n{AnsiColor.GREEN}[RESOLVED]{AnsiColor.RESET} Nilai akhir yang di-stage: {resolved_val}")
        print(f"$ git add settings.json")
        print(f"$ git commit -m \"fix: resolve merge conflict on MAX_CONCURRENT_USERS config\"")
        print(f"{AnsiColor.CYAN}Konflik berhasil diselesaikan dengan aman!{AnsiColor.RESET}\n")

    def demo_rebase(self):
        """
        Skenario 4: Git Rebase Dasar.
        Mengubah basis commit feature agar diletakkan di ujung commit main terbaru,
        menghasilkan riwayat commit yang lurus (linear).
        """
        self.reset_repository()
        self.print_header("Skenario 4: Git Rebase (Linear History)")
        print(f"{AnsiColor.WHITE}Skenario:{AnsiColor.RESET} Membuat commit di 'feature' dan 'main'.")

        c3 = self.create_commit("feature", "feat: create billing stripe checkout")
        c4 = self.create_commit("main", "chore: upgrade node runtime v20")

        self.show_graph()

        print(f"Sebelum rebase, 'feature' ({c3}) berakar pada 'c2'.")
        print(f"Sementara 'main' sudah melangkah maju ke '{c4}'.")
        input(f"{AnsiColor.DIM}Tekan [Enter] untuk menjalankan: git checkout feature && git rebase main ...{AnsiColor.RESET}")

        print(f"\n{AnsiColor.BOLD}Eksekusi Perintah:{AnsiColor.RESET}")
        print(f"$ git checkout feature")
        print(f"$ git rebase main")
        time.sleep(0.6)

        # Proses rebase: commit c3 di-replay di atas c4 menjadi c3'
        rebased_cid = f"c{self.counter}'"
        self.counter += 1
        self.commits[rebased_cid] = Commit(
            rebased_cid,
            "feat: create billing stripe checkout (replayed on main)",
            [self.branches["main"]]
        )
        self.branches["feature"] = rebased_cid

        print(f"\n{AnsiColor.BG_GREEN}{AnsiColor.BOLD} HASIL GIT REBASE {AnsiColor.RESET}")
        print("Commit feature dicabut, lalu diputar ulang (replayed) di atas commit 'main' terkini.")
        print(f"Riwayat sekarang sepenuhnya LINEAR tanpa ada merge commit baru!")
        self.show_graph()


def main_menu():
    sim = GitGraphSimulator()
    while True:
        print(f"\n{AnsiColor.BOLD}{AnsiColor.BLUE}======================================================{AnsiColor.RESET}")
        print(f"{AnsiColor.BOLD}  LAB INTERAKTIF: INTEGRASI KODE (MERGE & REBASE DASAR){AnsiColor.RESET}")
        print(f"{AnsiColor.BOLD}{AnsiColor.BLUE}======================================================{AnsiColor.RESET}")
        print("  1. Simulasi Fast-Forward Merge")
        print("  2. Simulasi 3-Way Merge (Recursive)")
        print("  3. Simulasi & Latihan Menyelesaikan Merge Conflict")
        print("  4. Simulasi Git Rebase Dasar (Linear History)")
        print("  5. Jalankan Semua Modul Bertahap")
        print("  0. Keluar dari Lab")
        print(f"{AnsiColor.DIM}------------------------------------------------------{AnsiColor.RESET}")

        pilihan = input(f"{AnsiColor.CYAN}Pilih menu [0-5]: {AnsiColor.RESET}").strip()

        if pilihan == "1":
            sim.demo_fast_forward_merge()
        elif pilihan == "2":
            sim.demo_three_way_merge()
        elif pilihan == "3":
            sim.demo_merge_conflict()
        elif pilihan == "4":
            sim.demo_rebase()
        elif pilihan == "5":
            sim.demo_fast_forward_merge()
            sim.demo_three_way_merge()
            sim.demo_merge_conflict()
            sim.demo_rebase()
            print(f"\n{AnsiColor.GREEN}{AnsiColor.BOLD}Semua simulasi fondasi integrasi kode telah selesai dijalankan!{AnsiColor.RESET}")
        elif pilihan == "0":
            print(f"\n{AnsiColor.YELLOW}Terima kasih telah berlatih di Lab Git Integrasi Kode! Sampai jumpa.{AnsiColor.RESET}")
            sys.exit(0)
        else:
            print(f"{AnsiColor.RED}Pilihan tidak valid, silakan coba lagi.{AnsiColor.RESET}")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{AnsiColor.YELLOW}Eksekusi dihentikan oleh pengguna.{AnsiColor.RESET}")
        sys.exit(0)
