#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Branching & Isolasi Alur Kerja Git
BAB-04: Percabangan Terisolasi (Branching Basics)

Modul ini mendemonstrasikan secara visual dan interaktif bagaimana Git memperlakukan
branch sebagai pointer ringan (lightweight movable pointer) ke commit tertentu,
serta bagaimana perpindahan HEAD (git switch/checkout) mengisolasi perubahan.
"""

import sys
import uuid
import datetime

# ANSI Color Codes untuk visualisasi terminal interaktif
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
BG_MAGENTA = "\033[45m"


class Commit:
    def __init__(self, message: str, parent_id: str = None, author: str = "Developer"):
        self.commit_id = uuid.uuid4().hex[:7]
        self.message = message
        self.parent_id = parent_id
        self.author = author
        self.timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    def __repr__(self):
        return f"Commit({self.commit_id}, '{self.message}')"


class GitBranchSimulator:
    def __init__(self):
        self.commits = {}
        self.branches = {}
        self.current_branch = "main"
        self._initialize_repo()

    def _initialize_repo(self):
        # Inisialisasi initial commit pada main
        init_commit = Commit("Initial commit: setup struktur proyek")
        self.commits[init_commit.commit_id] = init_commit
        self.branches["main"] = init_commit.commit_id
        self.current_branch = "main"

    def active_commit_id(self) -> str:
        return self.branches.get(self.current_branch)

    def commit(self, message: str) -> Commit:
        if not message.strip():
            raise ValueError("Pesan commit tidak boleh kosong!")
        parent_id = self.active_commit_id()
        new_commit = Commit(message=message.strip(), parent_id=parent_id)
        self.commits[new_commit.commit_id] = new_commit
        self.branches[self.current_branch] = new_commit.commit_id
        return new_commit

    def create_branch(self, branch_name: str) -> bool:
        branch_name = branch_name.strip()
        if not branch_name:
            raise ValueError("Nama branch tidak boleh kosong!")
        if branch_name in self.branches:
            raise ValueError(f"Branch '{branch_name}' sudah ada!")
        # Branch baru menunjuk ke commit yang sama dengan commit aktif saat ini
        self.branches[branch_name] = self.active_commit_id()
        return True

    def switch_branch(self, branch_name: str) -> bool:
        branch_name = branch_name.strip()
        if branch_name not in self.branches:
            raise ValueError(f"Branch '{branch_name}' tidak ditemukan!")
        if branch_name == self.current_branch:
            raise ValueError(f"Anda sudah berada di branch '{branch_name}'!")
        self.current_branch = branch_name
        return True

    def delete_branch(self, branch_name: str) -> bool:
        branch_name = branch_name.strip()
        if branch_name == self.current_branch:
            raise ValueError(f"Tidak dapat menghapus branch aktif '{branch_name}'. Pindah ke branch lain dulu!")
        if branch_name not in self.branches:
            raise ValueError(f"Branch '{branch_name}' tidak ditemukan!")
        if branch_name == "main":
            raise ValueError("Branch 'main' adalah branch utama dan tidak diizinkan untuk dihapus!")
        del self.branches[branch_name]
        return True

    def merge_fast_forward(self, source_branch: str) -> str:
        source_branch = source_branch.strip()
        if source_branch not in self.branches:
            raise ValueError(f"Branch target '{source_branch}' tidak ditemukan!")
        if source_branch == self.current_branch:
            raise ValueError("Tidak bisa menggabungkan branch ke dirinya sendiri!")

        target_commit_id = self.branches[source_branch]
        current_commit_id = self.branches[self.current_branch]

        # Cek apakah target commit adalah downstream dari current commit (Fast-Forward check sederhana)
        curr = target_commit_id
        path_to_current = False
        while curr:
            if curr == current_commit_id:
                path_to_current = True
                break
            commit_obj = self.commits.get(curr)
            curr = commit_obj.parent_id if commit_obj else None

        if path_to_current:
            self.branches[self.current_branch] = target_commit_id
            return f"Fast-forward merge sukses: '{self.current_branch}' kini menunjuk ke {target_commit_id}."
        else:
            # 3-Way Merge simulation
            merge_commit = Commit(
                message=f"Merge branch '{source_branch}' into '{self.current_branch}'",
                parent_id=current_commit_id,
            )
            self.commits[merge_commit.commit_id] = merge_commit
            self.branches[self.current_branch] = merge_commit.commit_id
            return f"3-Way Merge dibuat: Commit {merge_commit.commit_id} menyatukan riwayat."

    def display_status(self):
        print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
        print(f"{BOLD}{YELLOW} STATUS REPOSITORI & TOPOLOGI POINTER GIT {RESET}")
        print(f"{CYAN}{'='*65}{RESET}")
        print(f" Branch Aktif (HEAD) -> {BG_BLUE}{WHITE} {self.current_branch} {RESET}")
        print(f" Commit Aktif        -> {YELLOW}{self.active_commit_id()}{RESET}")
        print(f"{CYAN}{'-'*65}{RESET}")

        print(f"\n{BOLD}Daftar Branch & Target Pointer:{RESET}")
        for b_name, c_id in self.branches.items():
            c_info = self.commits.get(c_id)
            is_head = f"{GREEN}{BOLD}* (HEAD){RESET}" if b_name == self.current_branch else "        "
            print(f" {is_head} {BOLD}{CYAN}{b_name:<16}{RESET} -> [{YELLOW}{c_id}{RESET}] \"{c_info.message}\"")

        print(f"\n{BOLD}Riwayat Linear Commit Grafis:{RESET}")
        for c_id, commit in reversed(list(self.commits.items())):
            branches_pointing = [b for b, cid in self.branches.items() if cid == c_id]
            branch_tags = ""
            if branches_pointing:
                tags = []
                for b in branches_pointing:
                    if b == self.current_branch:
                        tags.append(f"{BG_BLUE}{WHITE}HEAD -> {b}{RESET}")
                    else:
                        tags.append(f"{GREEN}{b}{RESET}")
                branch_tags = f" ({', '.join(tags)})"

            parent_str = f"parent: {commit.parent_id}" if commit.parent_id else "root commit"
            print(f"  {YELLOW}* {c_id}{RESET}{branch_tags} - {WHITE}{commit.message}{RESET} {DIM}({commit.timestamp}, {parent_str}){RESET}")
        print(f"{CYAN}{'='*65}{RESET}\n")


def print_banner():
    banner = f"""
{BOLD}{MAGENTA}=================================================================
  SIMULATOR PERCABANGAN TERISOLASI GIT (BRANCHING BASICS)
  Modul M01: Memahami Pointer Branch, HEAD, dan Alur Fitur
================================================================={RESET}
{DIM}Konsep Kunci:
1. Branch hanyalah pointer (referensi) 40-byte ke SHA-1/SHA-256 commit.
2. HEAD menunjukkan branch mana yang sedang aktif saat ini di working directory.
3. Membuat commit baru hanya memajukan branch aktif saat ini.{RESET}
"""
    print(banner)


def print_menu():
    print(f"{BOLD}PILIHAN OPERASI GIT:{RESET}")
    print(f"  {GREEN}1.{RESET} Lihat Status & Visualisasi Pohon Commit (`git status / log`)")
    print(f"  {GREEN}2.{RESET} Buat Commit Baru di Branch Aktif (`git commit -m`)")
    print(f"  {GREEN}3.{RESET} Buat Branch Baru (`git branch <nama>`)")
    print(f"  {GREEN}4.{RESET} Pindah ke Branch Lain (`git switch <nama>`)")
    print(f"  {GREEN}5.{RESET} Buat & Langsung Pindah ke Branch Baru (`git switch -c <nama>`)")
    print(f"  {GREEN}6.{RESET} Gabungkan Branch ke Branch Aktif (`git merge <nama>`)")
    print(f"  {GREEN}7.{RESET} Hapus Branch (`git branch -d <nama>`)")
    print(f"  {GREEN}8.{RESET} Jalankan Skenario Pembelajaran Terpandu (Feature Isolation Demo)")
    print(f"  {RED}9.{RESET} Keluar")


def run_scenario_demo(sim: GitBranchSimulator):
    print(f"\n{BOLD}{YELLOW}>>> MEMULAI SKENARIO TERPANDU: ISOLASI FITUR & FAST-FORWARD MERGE <<<{RESET}")
    print(f"{DIM}Skenario ini mensimulasikan pembuatan branch 'feature/login', bekerja di sana,")
    print(f"dan membuktikan bahwa branch 'main' tetap aman dari perubahan belum selesai.{RESET}\n")

    input(f"{CYAN}[Tekan ENTER untuk membuat branch 'feature/login' dan beralih ke sana...]{RESET}")
    sim.create_branch("feature/login")
    sim.switch_branch("feature/login")
    sim.display_status()

    input(f"{CYAN}[Tekan ENTER untuk membuat commit fitur baru di 'feature/login'...]{RESET}")
    sim.commit("feat: tambah komponen form login")
    sim.commit("feat: validasi otentikasi JWT")
    sim.display_status()

    input(f"{CYAN}[Tekan ENTER untuk kembali ke 'main' dan buktikan isolasi commit...]{RESET}")
    sim.switch_branch("main")
    sim.display_status()
    print(f"{BOLD}{GREEN}Perhatikan:{RESET} Branch 'main' masih berada pada commit awal! Perubahan fitur terisolasi sempurna.")

    input(f"{CYAN}[Tekan ENTER untuk melakukan Fast-Forward Merge dari 'feature/login' ke 'main'...]{RESET}")
    res = sim.merge_fast_forward("feature/login")
    print(f"{BOLD}{GREEN}{res}{RESET}")
    sim.display_status()

    input(f"{CYAN}[Tekan ENTER untuk membersihkan branch 'feature/login' yang sudah selesai...]{RESET}")
    sim.delete_branch("feature/login")
    sim.display_status()
    print(f"{BOLD}{GREEN}Skenario berhasil diselesaikan! Fitur telah terintegrasi dan repo kembali bersih.{RESET}\n")


def main():
    sim = GitBranchSimulator()
    print_banner()

    while True:
        print_menu()
        try:
            choice = input(f"{BOLD}{CYAN}Masukkan pilihan (1-9): {RESET}").strip()
            if choice == "1":
                sim.display_status()
            elif choice == "2":
                msg = input(f"{YELLOW}Pesan commit (misal: 'feat: header navigasi'): {RESET}")
                if msg:
                    c = sim.commit(msg)
                    print(f"{GREEN}✓ Commit berhasil dibuat [{c.commit_id}] pada branch '{sim.current_branch}'.{RESET}")
                    sim.display_status()
            elif choice == "3":
                bname = input(f"{YELLOW}Nama branch baru (misal: 'feature/auth'): {RESET}")
                if bname:
                    sim.create_branch(bname)
                    print(f"{GREEN}✓ Branch '{bname}' berhasil dibuat menunjuk ke [{sim.active_commit_id()}].{RESET}")
                    sim.display_status()
            elif choice == "4":
                bname = input(f"{YELLOW}Nama branch tujuan (misal: 'main'): {RESET}")
                if bname:
                    sim.switch_branch(bname)
                    print(f"{GREEN}✓ Berhasil berpindah ke branch '{bname}'. HEAD sekarang menunjuk ke {bname}.{RESET}")
                    sim.display_status()
            elif choice == "5":
                bname = input(f"{YELLOW}Nama branch baru yang akan dibuat & diaktifkan: {RESET}")
                if bname:
                    sim.create_branch(bname)
                    sim.switch_branch(bname)
                    print(f"{GREEN}✓ Branch '{bname}' dibuat dan langsung aktif (HEAD -> {bname}).{RESET}")
                    sim.display_status()
            elif choice == "6":
                bname = input(f"{YELLOW}Nama branch yang ingin digabung ke '{sim.current_branch}': {RESET}")
                if bname:
                    res = sim.merge_fast_forward(bname)
                    print(f"{GREEN}✓ {res}{RESET}")
                    sim.display_status()
            elif choice == "7":
                bname = input(f"{YELLOW}Nama branch yang ingin dihapus: {RESET}")
                if bname:
                    sim.delete_branch(bname)
                    print(f"{GREEN}✓ Branch '{bname}' berhasil dihapus.{RESET}")
                    sim.display_status()
            elif choice == "8":
                run_scenario_demo(sim)
            elif choice == "9":
                print(f"{CYAN}Terima kasih telah menggunakan simulator Git Branching Basics. Selamat belajar!{RESET}")
                sys.exit(0)
            else:
                print(f"{RED}Pilihan tidak valid. Silakan masukkan angka 1-9.{RESET}\n")
        except ValueError as err:
            print(f"{RED}Error: {err}{RESET}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{CYAN}Program dihentikan oleh pengguna.{RESET}")
            sys.exit(0)


if __name__ == "__main__":
    main()
