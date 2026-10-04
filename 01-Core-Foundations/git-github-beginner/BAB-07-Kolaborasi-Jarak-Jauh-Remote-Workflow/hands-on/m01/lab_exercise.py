#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Git Remote Workflow
Topik: BAB-07 Kolaborasi Jarak Jauh (Remote Workflow)
Konsep Inti: git remote, git fetch, git pull, git push, tracking branch, non-fast-forward detection.
"""

import sys
import time
from typing import List, Dict

# ANSI Color Codes untuk visualisasi terminal interaktif
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"
BG_BLUE = "\033[44m"


class Commit:
    def __init__(self, commit_id: str, message: str, author: str):
        self.commit_id = commit_id
        self.message = message
        self.author = author


class GitRemoteSimulator:
    def __init__(self):
        self.commit_counter = 1
        initial_commit = self._create_commit("Initial commit on main", "System")
        
        # Remote repository (origin)
        self.remote_url = "git@github.com:developer/belajar-git.git"
        self.remote_commits: List[Commit] = [initial_commit]
        
        # Local repository
        self.local_commits: List[Commit] = [initial_commit]
        self.cached_remote_commits: List[Commit] = [initial_commit]  # origin/main tracking ref
        self.remotes: Dict[str, str] = {"origin": self.remote_url}
        self.upstream_configured = True

    def _create_commit(self, message: str, author: str) -> Commit:
        cid = f"c{self.commit_counter:03d}f8"
        self.commit_counter += 1
        return Commit(cid, message, author)

    def print_banner(self):
        print(f"\n{BOLD}{CYAN}{'='*72}{RESET}")
        print(f"{BOLD}{BG_BLUE}  LAB EXERCISE M01: SIMULATOR REMOTE WORKFLOW (GIT & GITHUB)  {RESET}")
        print(f"{BOLD}{CYAN}{'='*72}{RESET}")
        print(f"{YELLOW}Pelajari cara kerja git remote, fetch, pull, push, dan sinkronisasi.{RESET}\n")

    def show_topology(self):
        print(f"\n{BOLD}{MAGENTA}--- STATUS REPOSITORI SAAT INI ---{RESET}")
        print(f"Remote URL: {CYAN}{self.remotes.get('origin', 'Belum diset')}{RESET}")
        
        local_ids = [c.commit_id for c in self.local_commits]
        remote_ids = [c.commit_id for c in self.remote_commits]
        cached_ids = [c.commit_id for c in self.cached_remote_commits]

        # Hitung ahead / behind
        ahead = [c for c in self.local_commits if c.commit_id not in remote_ids]
        behind = [c for c in self.remote_commits if c.commit_id not in local_ids]

        print(f"Tracking Branch: {GREEN}main -> origin/main{RESET}")
        if not ahead and not behind:
            print(f"Status: {GREEN}[Up-to-date]{RESET} Repositori lokal sinkron dengan GitHub.")
        else:
            status_str = []
            if ahead:
                status_str.append(f"{YELLOW}Ahead {len(ahead)} commit (perlu git push){RESET}")
            if behind:
                status_str.append(f"{RED}Behind {len(behind)} commit (perlu git pull / fetch){RESET}")
            print("Status: " + ", ".join(status_str))

        print(f"\n{BOLD}Daftar Commit di GitHub (origin/main):{RESET}")
        for c in self.remote_commits:
            print(f"  [{CYAN}{c.commit_id}{RESET}] {c.message} {BLUE}({c.author}){RESET}")

        print(f"\n{BOLD}Daftar Commit di Lokal (HEAD -> main):{RESET}")
        for c in self.local_commits:
            tag = ""
            if c.commit_id == self.local_commits[-1].commit_id:
                tag += f" {GREEN}(HEAD -> main){RESET}"
            if c.commit_id == self.cached_remote_commits[-1].commit_id:
                tag += f" {YELLOW}(origin/main){RESET}"
            print(f"  [{CYAN}{c.commit_id}{RESET}] {c.message}{tag}")
        print(f"{BOLD}{MAGENTA}{'-'*72}{RESET}\n")

    def local_commit(self):
        msg = input(f"{BOLD}Masukkan pesan commit lokal: {RESET}").strip()
        if not msg:
            msg = f"Perubahan fitur lokal #{len(self.local_commits)}"
        c = self._create_commit(msg, "Anda (Local)")
        self.local_commits.append(c)
        print(f"{GREEN}[OK]{RESET} Berhasil membuat commit lokal: [{c.commit_id}] {c.message}")

    def simulate_teammate_push(self):
        print(f"{YELLOW}[Simulasi]{RESET} Rekan setim (Rina) melakukan push commit ke remote GitHub...")
        time.sleep(0.5)
        c = self._create_commit("Update fitur auth oleh tim", "Rina (Remote Teammate)")
        self.remote_commits.append(c)
        print(f"{GREEN}[GitHub]{RESET} Commit baru mendarat di origin/main: [{c.commit_id}] {c.message}")
        print(f"{BLUE}[Catatan]{RESET} Lokal Anda belum tahu ada commit ini sebelum Anda melakukan 'git fetch'.")

    def git_fetch(self):
        print(f"{CYAN}$ git fetch origin{RESET}")
        time.sleep(0.4)
        new_on_remote = len(self.remote_commits) - len(self.cached_remote_commits)
        self.cached_remote_commits = list(self.remote_commits)
        if new_on_remote > 0:
            print(f"{GREEN}[Fetch Berhasil]{RESET} Memperbarui referensi 'origin/main' lokal ({new_on_remote} commit baru diunduh).")
            print(f"{YELLOW}Working tree lokal belum berubah. Gunakan 'git merge origin/main' atau 'git pull' untuk menerapkan.{RESET}")
        else:
            print(f"{GREEN}[Fetch Selesai]{RESET} Referensi origin/main sudah up-to-date.")

    def git_pull(self):
        print(f"{CYAN}$ git pull origin main{RESET}")
        time.sleep(0.5)
        local_ids = [c.commit_id for c in self.local_commits]
        remote_ids = [c.commit_id for c in self.remote_commits]

        missing_in_local = [c for c in self.remote_commits if c.commit_id not in local_ids]
        ahead_in_local = [c for c in self.local_commits if c.commit_id not in remote_ids]

        # Update cache origin/main
        self.cached_remote_commits = list(self.remote_commits)

        if not missing_in_local:
            print(f"{GREEN}Already up to date.{RESET}")
            return

        # Fast-Forward check
        if not ahead_in_local:
            self.local_commits.extend(missing_in_local)
            print(f"{GREEN}[Fast-forward Merge]{RESET} Cabang lokal langsung dimajukan.")
            print(f"Berhasil mengunduh dan menerapkan {len(missing_in_local)} commit ke cabang main lokal.")
        else:
            # 3-Way Merge Commit diperlukan
            merge_commit = self._create_commit("Merge remote-tracking branch 'origin/main'", "Anda (Merge)")
            self.local_commits.extend(missing_in_local)
            self.local_commits.append(merge_commit)
            print(f"{YELLOW}[Non-Fast-Forward Merge]{RESET} Terjadi divergensi!")
            print(f"Git membuat merge commit otomatis: [{merge_commit.commit_id}] {merge_commit.message}")

    def git_push(self):
        print(f"{CYAN}$ git push origin main{RESET}")
        time.sleep(0.5)
        local_ids = [c.commit_id for c in self.local_commits]
        remote_ids = [c.commit_id for c in self.remote_commits]

        # Cek apakah remote memiliki commit yang belum ada di lokal (Non-fast-forward rejection)
        missing_in_local = [c for c in self.remote_commits if c.commit_id not in local_ids]
        if missing_in_local:
            print(f"\n{BOLD}{RED}[PUSH REJECTED - NON-FAST-FORWARD]{RESET}")
            print(f"{RED}error: failed to push some refs to '{self.remote_url}'{RESET}")
            print(f"{YELLOW}hint: Updates were rejected because the remote contains work that you do{RESET}")
            print(f"{YELLOW}hint: not have locally. This is usually caused by another repository pushing{RESET}")
            print(f"{YELLOW}hint: to the same ref. You may want to first integrate the remote changes{RESET}")
            print(f"{YELLOW}hint: (e.g., 'git pull ...') before pushing again.{RESET}\n")
            return

        to_push = [c for c in self.local_commits if c.commit_id not in remote_ids]
        if not to_push:
            print(f"{GREEN}Everything up-to-date.{RESET}")
            return

        self.remote_commits = list(self.local_commits)
        self.cached_remote_commits = list(self.local_commits)
        print(f"{GREEN}[Push Berhasil]{RESET} {len(to_push)} commit terkirim ke GitHub (origin/main)!")


def interactive_menu():
    sim = GitRemoteSimulator()
    sim.print_banner()

    while True:
        print(f"{BOLD}PILIHAN AKSI GIT REMOTE:{RESET}")
        print(f"  {CYAN}1.{RESET} Tampilkan Status Topologi (Lokal vs origin/main)")
        print(f"  {CYAN}2.{RESET} Buat Commit Lokal ({BOLD}git commit{RESET})")
        print(f"  {CYAN}3.{RESET} Simulasi Teman Push ke Remote ({BOLD}Simulasi Konflik/Divergen{RESET})")
        print(f"  {CYAN}4.{RESET} Unduh metadata remote ({BOLD}git fetch origin{RESET})")
        print(f"  {CYAN}5.{RESET} Tarik & gabungkan perubahan ({BOLD}git pull origin main{RESET})")
        print(f"  {CYAN}6.{RESET} Kirim commit lokal ke remote ({BOLD}git push origin main{RESET})")
        print(f"  {CYAN}7.{RESET} Reset Simulasi Ulang")
        print(f"  {RED}0.{RESET} Keluar")

        choice = input(f"\n{BOLD}Pilih menu (0-7): {RESET}").strip()
        if choice == "1":
            sim.show_topology()
        elif choice == "2":
            sim.local_commit()
        elif choice == "3":
            sim.simulate_teammate_push()
        elif choice == "4":
            sim.git_fetch()
        elif choice == "5":
            sim.git_pull()
        elif choice == "6":
            sim.git_push()
        elif choice == "7":
            sim = GitRemoteSimulator()
            print(f"{GREEN}Simulasi telah direset ke kondisi awal.{RESET}")
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah mencoba simulasi Git Remote Workflow!{RESET}\n")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid, silakan masukkan angka 0-7.{RESET}")


if __name__ == "__main__":
    interactive_menu()
