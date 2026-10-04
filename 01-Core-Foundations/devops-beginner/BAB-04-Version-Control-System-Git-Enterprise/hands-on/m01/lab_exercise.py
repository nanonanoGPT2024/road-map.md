#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Fondasi Git Enterprise
Topik: Objek Git (Blob, Tree, Commit), 3 Status File, dan Branch Protection Workflow
BAB-04-Version-Control-System-Git-Enterprise
"""

import hashlib
import json
import os
import sys
import time

# --- ANSI Color Codes ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_BLUE = "\033[44m"


def clear_screen():
    print("\033[H\033[J", end="")


def header(title: str):
    print(f"\n{CLR_BG_BLUE}{CLR_WHITE}{CLR_BOLD}  === {title.upper()} ===  {CLR_RESET}\n")


def print_info(msg: str):
    print(f"{CLR_CYAN}[INFO]{CLR_RESET} {msg}")


def print_success(msg: str):
    print(f"{CLR_GREEN}[SUCCESS]{CLR_RESET} {msg}")


def print_warning(msg: str):
    print(f"{CLR_YELLOW}[WARNING]{CLR_RESET} {msg}")


def print_danger(msg: str):
    print(f"{CLR_RED}[DANGER]{CLR_RESET} {msg}")


def calculate_sha1(data_type: str, content: str) -> str:
    """Simulasi struktur hash Git: '<type> <size>\\0<content>'"""
    header_str = f"{data_type} {len(content.encode('utf-8'))}\0"
    store = header_str.encode("utf-8") + content.encode("utf-8")
    return hashlib.sha1(store).hexdigest()


class MiniGitEnterpriseSimulator:
    def __init__(self):
        self.working_directory = {}
        self.staging_area = {}
        self.object_store = {}  # sha -> {type, content}
        self.commits = []
        self.branches = {"main": None}
        self.current_branch = "main"
        self.branch_protection = {
            "main": {
                "require_pr": True,
                "required_reviews": 1,
                "block_force_push": True,
            }
        }

    def status(self):
        header("Git Status Monitor (3 Area Kerja)")
        print(f"Current Branch: {CLR_BOLD}{CLR_MAGENTA}{self.current_branch}{CLR_RESET}\n")

        all_files = sorted(set(list(self.working_directory.keys()) + list(self.staging_area.keys())))
        if not all_files:
            print(f"{CLR_YELLOW}Directory kosong. Tambahkan file untuk mulai bereksperimen.{CLR_RESET}")
            return

        print(f"{CLR_BOLD}{'FILE':<20} | {'WORKING DIR':<25} | {'STAGING AREA':<25} | {'STATUS'}{CLR_RESET}")
        print("-" * 85)

        for filename in all_files:
            wd_content = self.working_directory.get(filename)
            stage_content = self.staging_area.get(filename)

            wd_status = "Ada (Modified)" if wd_content else "Deleted"
            stage_status = "Staged" if stage_content else "Not Staged"

            if wd_content and not stage_content:
                flag = f"{CLR_RED}Untracked / Unstaged{CLR_RESET}"
            elif stage_content and stage_content != wd_content:
                flag = f"{CLR_YELLOW}Partially Staged{CLR_RESET}"
            elif stage_content and stage_content == wd_content:
                flag = f"{CLR_GREEN}Fully Staged (Ready){CLR_RESET}"
            else:
                flag = f"{CLR_RED}Inconsistent{CLR_RESET}"

            print(f"{filename:<20} | {wd_status:<25} | {stage_status:<25} | {flag}")
        print("-" * 85)

    def write_working_file(self, filename: str, content: str):
        self.working_directory[filename] = content
        print_success(f"File '{filename}' ditulis di Working Directory.")

    def stage_file(self, filename: str):
        if filename not in self.working_directory:
            print_danger(f"File '{filename}' tidak ditemukan di Working Directory.")
            return

        content = self.working_directory[filename]
        blob_sha = calculate_sha1("blob", content)
        self.object_store[blob_sha] = {"type": "blob", "content": content}
        self.staging_area[filename] = blob_sha

        print_success(f"File '{filename}' berhasil di-stage.")
        print_info(f"Git Blob Object tercipta: {CLR_CYAN}{blob_sha}{CLR_RESET}")

    def commit(self, message: str, author: str = "DevOps Engineer <devops@company.internal>"):
        if not self.staging_area:
            print_warning("Tidak ada perubahan di staging area untuk di-commit.")
            return

        # 1. Bangun Tree Object dari Staging Area
        tree_entries = []
        for fn, sha in sorted(self.staging_area.items()):
            tree_entries.append(f"100644 blob {sha} {fn}")
        tree_content = "\n".join(tree_entries)
        tree_sha = calculate_sha1("tree", tree_content)
        self.object_store[tree_sha] = {"type": "tree", "content": tree_content}

        # 2. Bangun Commit Object
        parent_sha = self.branches.get(self.current_branch)
        commit_payload = {
            "tree": tree_sha,
            "parent": parent_sha,
            "author": author,
            "timestamp": int(time.time()),
            "message": message,
        }
        commit_str = json.dumps(commit_payload, indent=2)
        commit_sha = calculate_sha1("commit", commit_str)
        self.object_store[commit_sha] = {"type": "commit", "content": commit_payload}

        # 3. Update Ref Branch
        self.branches[self.current_branch] = commit_sha
        self.commits.append(commit_sha)

        print_success(f"Commit berhasil dibuat: {CLR_BOLD}{commit_sha[:8]}{CLR_RESET} on [{self.current_branch}]")
        print_info(f"Tree SHA  : {tree_sha}")
        print_info(f"Commit SHA: {commit_sha}")
        print_info(f"Commit Log: \"{message}\"")

    def show_log(self):
        header(f"Git Commit History: [{self.current_branch}]")
        current_sha = self.branches.get(self.current_branch)
        if not current_sha:
            print_warning(f"Belum ada riwayat commit pada branch '{self.current_branch}'.")
            return

        while current_sha:
            obj = self.object_store.get(current_sha)
            if not obj or obj["type"] != "commit":
                break
            c_data = obj["content"]
            print(f"{CLR_YELLOW}commit {current_sha}{CLR_RESET}")
            print(f"Author: {c_data['author']}")
            print(f"Tree  : {c_data['tree']}")
            print(f"Date  : {time.ctime(c_data['timestamp'])}")
            print(f"\n    {CLR_BOLD}{c_data['message']}{CLR_RESET}\n")
            current_sha = c_data["parent"]

    def create_branch(self, branch_name: str):
        if branch_name in self.branches:
            print_warning(f"Branch '{branch_name}' sudah ada.")
            return
        self.branches[branch_name] = self.branches[self.current_branch]
        print_success(f"Branch baru '{branch_name}' dibuat merujuk ke {str(self.branches[branch_name])[:8]}.")

    def checkout(self, branch_name: str):
        if branch_name not in self.branches:
            print_danger(f"Branch '{branch_name}' tidak ditemukan.")
            return
        self.current_branch = branch_name
        print_success(f"Switched to branch '{branch_name}'.")

    def simulate_push_to_enterprise(self, target_branch: str = "main"):
        header("Enterprise Git Remote Push & Policy Enforcement")
        print_info(f"Mencoba melakukan direct push dari '{self.current_branch}' ke '{target_branch}'...")

        protection = self.branch_protection.get(target_branch)
        if protection and protection.get("require_pr") and self.current_branch != target_branch:
            print_danger("PUSH DITOLAK OLEH REMOTE SERVER (PRE-RECEIVE HOOK)!")
            print(f"{CLR_RED}Aturan Keamanan Enterprise:{CLR_RESET}")
            print(f" - Direct push ke '{target_branch}' dilarang keras.")
            print(" - Wajib membuat Pull Request (PR) dan mendapatkan minimal 1 approval reviewer.")
            print(f"\n{CLR_GREEN}Solusi Disarankan:{CLR_RESET}")
            print(f" 1. Push branch fitur Anda: git push origin {self.current_branch}")
            print(" 2. Buka PR via CLI: gh pr create --base main")
            return False

        if protection and self.current_branch == target_branch:
            print_danger("DIRECT COMMIT KE PROTECTED BRANCH TERDETEKSI!")
            print("Praktek DevOps Enterprise melarang commit langsung ke trunk/main.")
            return False

        print_success("Push berhasil diverifikasi oleh server.")
        return True


def interactive_cli():
    sim = MiniGitEnterpriseSimulator()
    clear_screen()
    print(f"{CLR_BOLD}{CLR_CYAN}================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}   LAB EXERCISE M01: SIMULASI INTERAKTIF GIT ENTERPRISE INTERNALS {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}================================================================={CLR_RESET}")
    print(f"Selamat datang di modul simulasi interaktif low-level Git objects & branching enterprise.\n")

    # Inisialisasi data awal
    sim.write_working_file("README.md", "# Enterprise Microservice\nArsitektur Cloud Native.")
    sim.write_working_file("service.py", "def app(): return 'OK'\n")

    while True:
        print(f"\n{CLR_BOLD}Menu Operasi Git:{CLR_RESET}")
        print(" [1] Lihat Status 3 Area Kerja (Working Dir, Staging, Repository)")
        print(" [2] Modifikasi File di Working Directory")
        print(" [3] Stage File (git add -> create blob object)")
        print(" [4] Commit Perubahan (git commit -> create tree & commit objects)")
        print(" [5] Lihat Riwayat Commit (git log)")
        print(" [6] Buat Branch Baru (git checkout -b <feature>)")
        print(" [7] Ganti Branch (git checkout <branch>)")
        print(" [8] Simulasi Direct Push ke Enterprise Protected Branch")
        print(" [9] Inspeksi Git Object Store (Hash Table / SHA-1 DB)")
        print(" [0] Keluar")

        pilihan = input(f"\n{CLR_YELLOW}Pilih opsi [0-9]: {CLR_RESET}").strip()

        if pilihan == "1":
            sim.status()
        elif pilihan == "2":
            fn = input("Masukkan nama file (misal: config.yaml): ").strip()
            content = input("Masukkan isi teks file: ")
            sim.write_working_file(fn, content)
        elif pilihan == "3":
            fn = input("Nama file yang ingin di-stage: ").strip()
            sim.stage_file(fn)
        elif pilihan == "4":
            msg = input("Pesan commit: ").strip()
            if msg:
                sim.commit(msg)
            else:
                print_warning("Pesan commit tidak boleh kosong.")
        elif pilihan == "5":
            sim.show_log()
        elif pilihan == "6":
            b_name = input("Nama branch baru (misal: feat/auth-service): ").strip()
            if b_name:
                sim.create_branch(b_name)
                sim.checkout(b_name)
        elif pilihan == "7":
            print(f"Daftar branch tersedia: {', '.join(sim.branches.keys())}")
            b_name = input("Nama branch tujuan: ").strip()
            sim.checkout(b_name)
        elif pilihan == "8":
            sim.simulate_push_to_enterprise("main")
        elif pilihan == "9":
            header("Git Object Database Dump (Content-Addressable Storage)")
            if not sim.object_store:
                print_warning("Object database masih kosong.")
            for sha, data in sim.object_store.items():
                print(f"{CLR_BLUE}[{data['type'].upper()}]{CLR_RESET} {CLR_BOLD}{sha}{CLR_RESET}")
                if data["type"] == "blob":
                    preview = data["content"].replace("\n", " ")[:40]
                    print(f"       Konten: \"{preview}...\"")
                elif data["type"] == "tree":
                    print(f"       Hierarki:\n{data['content']}")
                elif data["type"] == "commit":
                    print(f"       Pesan: {data['content']['message']} | Author: {data['content']['author']}")
        elif pilihan == "0":
            print(f"\n{CLR_GREEN}Terima kasih telah menyelesaikan modul latihan interaktif Git Enterprise.{CLR_RESET}\n")
            sys.exit(0)
        else:
            print_danger("Pilihan tidak valid. Silakan masukkan angka 0-9.")


if __name__ == "__main__":
    interactive_cli()
