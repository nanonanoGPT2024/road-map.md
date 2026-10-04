#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Git Local Workflow & State Traversal
Materi: BAB-02 Local Workflow & State Traversal (Git Foundation)

Fitur:
- Tiga Area Git: Working Directory, Staging Area (Index), Local Repository (HEAD)
- Empat Status File: Untracked, Unmodified, Modified, Staged
- Visualisasi status tabel berwarna ANSI
- CLI Interaktif & Mode Demonstrasi Otomatis
"""

import sys
import time
import hashlib
from typing import Dict, List, Optional


class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"


C = TerminalColor


class Commit:
    def __init__(self, commit_id: str, message: str, snapshot: Dict[str, str], parent: Optional[str] = None):
        self.commit_id = commit_id
        self.message = message
        self.snapshot = snapshot.copy()
        self.parent = parent
        self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")


class GitStateSimulator:
    def __init__(self):
        # 3 Trees Git
        self.working_directory: Dict[str, str] = {}
        self.staging_area: Dict[str, str] = {}
        self.commits: List[Commit] = []
        self.head: Optional[str] = None

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha1(content.encode("utf-8")).hexdigest()[:7]

    def modify_file(self, filename: str, content: str) -> None:
        """Menulis atau memperbarui file di Working Directory."""
        self.working_directory[filename] = content
        print(f"{C.CYAN}➜ [Working Directory]{C.RESET} File '{C.BOLD}{filename}{C.RESET}' dibuat/diubah.")

    def add(self, filename: str) -> bool:
        """Memindahkan file dari Working Directory ke Staging Area (Index)."""
        if filename not in self.working_directory:
            print(f"{C.RED}Error: File '{filename}' tidak ditemukan di Working Directory.{C.RESET}")
            return False

        self.staging_area[filename] = self.working_directory[filename]
        print(f"{C.GREEN}✔ [Staging Area]{C.RESET} '{filename}' berhasil di-stage (git add).")
        return True

    def commit(self, message: str) -> Optional[str]:
        """Membuat snapshot permanen dari Staging Area ke Local Repository (git commit)."""
        if not self.staging_area:
            print(f"{C.YELLOW}Peringatan: Tidak ada perubahan di Staging Area untuk di-commit.{C.RESET}")
            return None

        # Snapshot menggabungkan state HEAD terakhir + perubahan di staging
        base_snapshot = {}
        if self.head:
            latest_commit = next((c for c in self.commits if c.commit_id == self.head), None)
            if latest_commit:
                base_snapshot = latest_commit.snapshot.copy()

        base_snapshot.update(self.staging_area)

        # Hash commit dibuat dari snapshot + pesan + timestamp
        seed = f"{message}-{time.time()}-{sorted(base_snapshot.items())}"
        commit_id = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:7]

        new_commit = Commit(commit_id, message, base_snapshot, parent=self.head)
        self.commits.append(new_commit)
        self.head = commit_id

        # Bersihkan staging area setelah commit sukses
        self.staging_area.clear()

        print(f"{C.MAGENTA}★ [Commit Berhasil]{C.RESET} [{commit_id}] {message}")
        return commit_id

    def restore_staged(self, filename: str) -> bool:
        """Membatalkan staging (git restore --staged <file>)."""
        if filename in self.staging_area:
            del self.staging_area[filename]
            print(f"{C.YELLOW}⟲ [Unstage]{C.RESET} '{filename}' dikembalikan dari Staging Area.")
            return True
        print(f"{C.RED}Error: '{filename}' tidak ada dalam Staging Area.{C.RESET}")
        return False

    def get_file_state(self, filename: str) -> str:
        """Menentukan status file dalam lifecycle Git."""
        in_wd = filename in self.working_directory
        in_stage = filename in self.staging_area
        head_commit = next((c for c in self.commits if c.commit_id == self.head), None) if self.head else None
        in_head = filename in (head_commit.snapshot if head_commit else {})

        if not in_head and not in_stage and in_wd:
            return f"{C.RED}Untracked{C.RESET}"

        if in_stage:
            stage_content = self.staging_area[filename]
            head_content = head_commit.snapshot.get(filename) if head_commit else None
            wd_content = self.working_directory.get(filename)

            if stage_content != wd_content:
                return f"{C.YELLOW}Staged + Modified in WD{C.RESET}"
            elif stage_content != head_content:
                return f"{C.GREEN}Staged (Ready to Commit){C.RESET}"

        if in_head and in_wd:
            wd_content = self.working_directory[filename]
            head_content = head_commit.snapshot.get(filename) if head_commit else None
            if wd_content != head_content:
                return f"{C.RED}Modified (Unstaged){C.RESET}"
            return f"{C.WHITE}Unmodified (Committed){C.RESET}"

        return f"{C.DIM}Unknown{C.RESET}"

    def status(self) -> None:
        """Menampilkan visualisasi 3 Trees dan Git Status."""
        print(f"\n{C.BOLD}{'=' * 65}{C.RESET}")
        print(f"{C.BG_BLUE}{C.WHITE}{C.BOLD}            GIT STATUS & STATE TRAVERSAL MONITOR            {C.RESET}")
        print(f"{C.BOLD}{'=' * 65}{C.RESET}")

        head_info = f"{C.MAGENTA}{self.head}{C.RESET}" if self.head else f"{C.DIM}(Belum ada commit){C.RESET}"
        print(f"HEAD Pointer     : {head_info}")
        print(f"Total Commits    : {len(self.commits)}")
        print(f"{C.BOLD}{'-' * 65}{C.RESET}")

        all_files = sorted(list(set(
            list(self.working_directory.keys()) +
            list(self.staging_area.keys()) +
            (list(self.commits[-1].snapshot.keys()) if self.commits else [])
        )))

        if not all_files:
            print(f"{C.DIM}Workspace kosong. Buat file baru untuk memulai.{C.RESET}")
            return

        print(f"{C.BOLD}{'File':<18} | {'Working Dir':<14} | {'Staging (Index)':<14} | {'Status Git'}{C.RESET}")
        print(f"{'-' * 65}")

        for fname in all_files:
            wd_hash = self._hash_content(self.working_directory[fname]) if fname in self.working_directory else "-"
            st_hash = self._hash_content(self.staging_area[fname]) if fname in self.staging_area else "-"
            state_label = self.get_file_state(fname)
            print(f"{fname:<18} | {wd_hash:<14} | {st_hash:<14} | {state_label}")

        print(f"{C.BOLD}{'=' * 65}{C.RESET}\n")

    def log(self) -> None:
        """Menampilkan riwayat commit log."""
        print(f"\n{C.CYAN}{C.BOLD}--- GIT COMMIT HISTORY (LOG) ---{C.RESET}")
        if not self.commits:
            print(f"{C.DIM}(Tidak ada commit recorded){C.RESET}")
            return

        for commit in reversed(self.commits):
            is_head = " (HEAD -> main)" if commit.commit_id == self.head else ""
            print(f"{C.YELLOW}commit {commit.commit_id}{C.GREEN}{is_head}{C.RESET}")
            print(f"Date:   {commit.timestamp}")
            print(f"Parent: {commit.parent or 'initial'}")
            print(f"\n    {C.BOLD}{commit.message}{C.RESET}\n")
            print(f"    {C.DIM}Files: {list(commit.snapshot.keys())}{C.RESET}\n")


def run_interactive_simulation():
    sim = GitStateSimulator()
    print(f"{C.BOLD}{C.GREEN}Selamat datang di Hands-on Git Workflow Simulator!{C.RESET}")
    print(f"Ketik '{C.CYAN}help{C.RESET}' untuk melihat daftar perintah.")

    while True:
        try:
            cmd_input = input(f"{C.BOLD}git-sim > {C.RESET}").strip()
            if not cmd_input:
                continue

            parts = cmd_input.split(maxsplit=2)
            cmd = parts[0].lower()

            if cmd in ("exit", "quit"):
                print(f"{C.GREEN}Selesai. Terus eksplorasi fondasi Git!{C.RESET}")
                break

            elif cmd == "status":
                sim.status()

            elif cmd == "log":
                sim.log()

            elif cmd == "touch" or cmd == "modify":
                if len(parts) < 2:
                    print(f"{C.RED}Penggunaan: modify <filename> [konten]{C.RESET}")
                    continue
                fname = parts[1]
                content = parts[2] if len(parts) > 2 else "konten default " + str(time.time())
                sim.modify_file(fname, content)

            elif cmd == "add":
                if len(parts) < 2:
                    print(f"{C.RED}Penggunaan: add <filename>{C.RESET}")
                    continue
                sim.add(parts[1])

            elif cmd == "commit":
                if len(parts) < 2:
                    print(f"{C.RED}Penggunaan: commit <pesan commit>{C.RESET}")
                    continue
                msg = " ".join(parts[1:])
                sim.commit(msg)

            elif cmd == "unstage":
                if len(parts) < 2:
                    print(f"{C.RED}Penggunaan: unstage <filename>{C.RESET}")
                    continue
                sim.restore_staged(parts[1])

            elif cmd == "demo":
                run_automated_demo(sim)

            elif cmd == "help":
                print(f"\n{C.BOLD}Daftar Perintah:{C.RESET}")
                print("  modify <file> <text> : Tulis file ke Working Directory")
                print("  add <file>           : Pindahkan file ke Staging Area (git add)")
                print("  commit <pesan>       : Simpan snapshot ke Git Repo (git commit)")
                print("  unstage <file>       : Kembalikan file dari staging (restore --staged)")
                print("  status               : Cek status 3 trees dan status file")
                print("  log                  : Tampilkan histori commit")
                print("  demo                 : Jalankan skenario otomatis lengkap")
                print("  exit                 : Keluar dari program\n")

            else:
                print(f"{C.RED}Perintah '{cmd}' tidak dikenali. Ketik 'help' untuk panduan.{C.RESET}")

        except (KeyboardInterrupt, EOFError):
            print(f"\n{C.YELLOW}Sesi dihentikan.{C.RESET}")
            break


def run_automated_demo(sim: GitStateSimulator):
    print(f"\n{C.CYAN}{C.BOLD}=== MENJALANKAN DEMO STATE TRAVERSAL OTOMATIS ==={C.RESET}\n")

    print(f"{C.BOLD}[Langkah 1: Membuat File Baru (Untracked)]{C.RESET}")
    sim.modify_file("index.html", "<h1>Halo Dunia</h1>")
    sim.modify_file("style.css", "body { margin: 0; }")
    sim.status()
    time.sleep(1)

    print(f"{C.BOLD}[Langkah 2: Melakukan Staging (Untracked -> Staged)]{C.RESET}")
    sim.add("index.html")
    sim.status()
    time.sleep(1)

    print(f"{C.BOLD}[Langkah 3: Commit Perdana (Staged -> Committed)]{C.RESET}")
    sim.commit("feat: initial commit menambahkan index.html")
    sim.status()
    time.sleep(1)

    print(f"{C.BOLD}[Langkah 4: Modifikasi File Lama + Stage File Baru]{C.RESET}")
    sim.modify_file("index.html", "<h1>Halo Dunia - Versi 2</h1>")
    sim.add("style.css")
    sim.status()
    time.sleep(1)

    print(f"{C.BOLD}[Langkah 5: Commit Kedua]{C.RESET}")
    sim.add("index.html")
    sim.commit("feat: update index.html dan tambahkan styling css")
    sim.status()
    sim.log()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        simulator = GitStateSimulator()
        run_automated_demo(simulator)
    else:
        run_interactive_simulation()
