#!/usr/bin/env python3
"""
Lab Exercise: Anatomi dan Filosofi Version Control (Git Core Foundations)
Simulasi Interaktif Tiga Pohon Git, Content-Addressable Storage (SHA-1), & Snapshot Model.
"""

import hashlib
import time
import sys
import os
from typing import Dict, List, Optional


# ANSI Color Codes untuk Terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"


def clear_screen():
    print("\033[H\033[J", end="")


def header(title: str):
    print(f"\n{Color.BG_BLUE}{Color.BOLD} === {title} === {Color.RESET}\n")


def sha1_hash(content: str) -> str:
    """Menghitung hash SHA-1 seperti cara Git mengidentifikasi objek blob."""
    header_str = f"blob {len(content.encode('utf-8'))}\0"
    store = header_str + content
    return hashlib.sha1(store.encode("utf-8")).hexdigest()


class Commit:
    def __init__(self, tree: Dict[str, str], message: str, parent: Optional[str] = None):
        self.tree = tree.copy()  # Snapshot seluruh workspace (bukan diff)
        self.message = message
        self.parent = parent
        self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.id = self._generate_id()

    def _generate_id(self) -> str:
        raw_payload = f"{sorted(self.tree.items())}|{self.message}|{self.parent}|{self.timestamp}"
        return hashlib.sha1(raw_payload.encode("utf-8")).hexdigest()[:8]


class GitCoreSimulation:
    def __init__(self):
        # 1. Working Directory: Berkas aktual yang sedang diedit
        self.working_directory: Dict[str, str] = {
            "README.md": "# Project Demo Git\nInisiasi proyek belajar fondasi VCS.",
            "main.py": "print('Halo Dunia!')\n"
        }
        # 2. Staging Area (Index): Penampung berkas yang dipersiapkan untuk snapshot
        self.staging_area: Dict[str, str] = {}
        # 3. Repository (Commit History / Objects)
        self.commits: Dict[str, Commit] = {}
        self.head: Optional[str] = None

    def status(self):
        header("GIT STATUS: THE THREE TREES INSPECTION")
        print(f"{Color.BOLD}1. HEAD State:{Color.RESET} {Color.CYAN}{self.head if self.head else 'Initial (Belum ada commit)'}{Color.RESET}")

        last_commit_tree = self.commits[self.head].tree if self.head else {}

        # Cek perubahan di Staging Area vs Last Commit
        staged_changes = []
        for path, content in self.staging_area.items():
            if path not in last_commit_tree or last_commit_tree[path] != content:
                staged_changes.append(path)

        # Cek perubahan di Working Tree vs Staging Area
        unstaged_changes = []
        untracked_files = []
        for path, content in self.working_directory.items():
            if path not in self.staging_area and path not in last_commit_tree:
                untracked_files.append(path)
            elif path in self.staging_area and self.staging_area[path] != content:
                unstaged_changes.append(path)
            elif path not in self.staging_area and path in last_commit_tree and last_commit_tree[path] != content:
                unstaged_changes.append(path)

        print(f"\n{Color.BOLD}Perubahan yang siap di-commit (Staged Area):{Color.RESET}")
        if staged_changes:
            for f in staged_changes:
                blob_hash = sha1_hash(self.staging_area[f])[:7]
                print(f"  {Color.GREEN}siap commit:   {f:<15} [blob hash: {blob_hash}]{Color.RESET}")
        else:
            print(f"  {Color.YELLOW}(kosong, tidak ada file di staging area){Color.RESET}")

        print(f"\n{Color.BOLD}Perubahan di luar Staging Area (Working Directory):{Color.RESET}")
        if unstaged_changes:
            for f in unstaged_changes:
                print(f"  {Color.RED}termodifikasi: {f}{Color.RESET}")
        elif not untracked_files:
            print(f"  {Color.GREEN}working tree bersih (clean working tree){Color.RESET}")

        if untracked_files:
            print(f"\n{Color.BOLD}File Belum Dilacak (Untracked Files):{Color.RESET}")
            for f in untracked_files:
                print(f"  {Color.MAGENTA}untracked:     {f}{Color.RESET}")

    def add(self, filename: str):
        if filename == ".":
            for f, content in self.working_directory.items():
                self.staging_area[f] = content
            print(f"{Color.GREEN}✓ Seluruh file di working directory ditambahkan ke Staging Area (git add .){Color.RESET}")
        elif filename in self.working_directory:
            self.staging_area[filename] = self.working_directory[filename]
            blob_hash = sha1_hash(self.working_directory[filename])
            print(f"{Color.GREEN}✓ File '{filename}' masuk ke Staging Area.{Color.RESET}")
            print(f"  → Objek Blob terbuat dengan SHA-1: {Color.CYAN}{blob_hash}{Color.RESET}")
        else:
            print(f"{Color.RED}✗ Error: File '{filename}' tidak ditemukan di Working Directory.{Color.RESET}")

    def commit(self, message: str):
        if not self.staging_area:
            print(f"{Color.RED}✗ Tidak ada perubahan di Staging Area untuk di-commit! Lakukan 'git add' terlebih dahulu.{Color.RESET}")
            return

        new_commit = Commit(tree=self.staging_area, message=message, parent=self.head)
        self.commits[new_commit.id] = new_commit
        self.head = new_commit.id
        print(f"\n{Color.BG_GREEN}{Color.BOLD} [SUCCESS] Commit Terbentuk! {Color.RESET}")
        print(f"  Commit ID   : {Color.YELLOW}{new_commit.id}{Color.RESET}")
        print(f"  Pesan       : {new_commit.message}")
        print(f"  Parent Hash : {new_commit.parent or 'None (Root Commit)'}")
        print(f"  Waktu       : {new_commit.timestamp}")
        print(f"  Snapshot    : {len(new_commit.tree)} berkas direkam dalam tree object.")

    def log(self):
        header("GIT LOG: RIWAYAT SNAPSHOT (DAG CHAIN)")
        curr = self.head
        if not curr:
            print(f"{Color.YELLOW}Belum ada commit di repositori ini.{Color.RESET}")
            return

        while curr:
            c = self.commits[curr]
            parent_info = f"-> Parent: {c.parent}" if c.parent else "-> (Initial Root Commit)"
            print(f"{Color.YELLOW}commit {c.id}{Color.RESET} {Color.CYAN}(HEAD){Color.RESET}" if curr == self.head else f"{Color.YELLOW}commit {c.id}{Color.RESET}")
            print(f"Date:   {c.timestamp}")
            print(f"Tree:   {parent_info}")
            print(f"Files:  {list(c.tree.keys())}")
            print(f"\n    {Color.BOLD}{c.message}{Color.RESET}\n" + "-" * 50)
            curr = c.parent

    def inspect_diff_vs_snapshot(self):
        header("FILOSOFI: DELTA/DIFF-BASED (VCS LAMA) VS SNAPSHOT-BASED (GIT)")
        print(f"""
{Color.BOLD}1. Sistem Tradisional (CVS/SVN - Delta-based):{Color.RESET}
   Menyimpan perubahan per file sebagai baris diff berurutan (delta).
   File A: [Base] ----> [Δ1] ----> [Δ2] ----> [Δ3]
   Kelemahan: Menghitung status file pada commit lama butuh rekonstruksi seluruh rantai delta.

{Color.BOLD}2. Git (Snapshot-based Stream of Snapshots):{Color.RESET}
   Setiap commit adalah 'mini-filesystem'. Jika file tidak berubah, Git membuat link pointer
   ke blob yang sama (Content-Addressable Storage via SHA-1 Hash).
   Commit 1: [A1]   [B1]   [C1]
   Commit 2: [A1*]  [B2]   [C1*]  (* pointer ke hash identik, tanpa duplikasi data)

{Color.GREEN}Keuntungan Git:{Color.RESET}
 - Operasi lokal instan (rekonstruksi state commit berkecepatan O(1)).
 - Integritas kriptografis mutlak: jika isi berubah 1 spasi, hash SHA-1 berubah.
""")

    def edit_file(self, filename: str, content: str):
        self.working_directory[filename] = content
        print(f"{Color.GREEN}✓ File '{filename}' diperbarui di Working Directory.{Color.RESET}")


def interactive_menu():
    sim = GitCoreSimulation()

    while True:
        print(f"\n{Color.CYAN}{Color.BOLD}===================================================={Color.RESET}")
        print(f"{Color.CYAN}{Color.BOLD}   LAB ANATOMI & FILOSOFI VERSION CONTROL (GIT)    {Color.RESET}")
        print(f"{Color.CYAN}{Color.BOLD}===================================================={Color.RESET}")
        print("1. [Status] Periksa 3 Pohon Git (Working Dir, Index, Repository)")
        print("2. [Edit] Modifikasi Berkas di Working Directory")
        print("3. [Add] Pindahkan Berkas ke Staging Area (git add)")
        print("4. [Commit] Buat Snapshot Permanen (git commit -m)")
        print("5. [Log] Tampilkan Rantai Pohon Commit (git log)")
        print("6. [Teori] Anatomi Hash SHA-1 & Delta vs Snapshot")
        print("7. [Uji Mandiri] Kuis Pemahaman Konsep Anatomi Git")
        print("0. Keluar dari Lab")

        choice = input(f"\n{Color.BOLD}Pilih menu (0-7): {Color.RESET}").strip()

        if choice == "1":
            sim.status()
        elif choice == "2":
            print("\nDaftar berkas saat ini di Working Directory:")
            for f in sim.working_directory.keys():
                print(f" - {f}")
            fname = input("Masukkan nama file yang ingin diedit/dibuat: ").strip()
            if not fname:
                continue
            print(f"Ketikkan teks baru untuk '{fname}':")
            val = input("> ")
            sim.edit_file(fname, val)
        elif choice == "3":
            sim.status()
            target = input("\nKetik nama file yang ingin di-stage (atau '.' untuk semua): ").strip()
            if target:
                sim.add(target)
        elif choice == "4":
            msg = input("Masukkan pesan commit: ").strip()
            if msg:
                sim.commit(msg)
            else:
                print(f"{Color.RED}Pesan commit tidak boleh kosong.{Color.RESET}")
        elif choice == "5":
            sim.log()
        elif choice == "6":
            sim.inspect_diff_vs_snapshot()
            sample_text = "Hello Git Internal"
            print(f"Demo SHA-1 hashing Git Blob:")
            print(f"Raw Content : '{sample_text}'")
            print(f"Git Blob Hash: {Color.CYAN}{sha1_hash(sample_text)}{Color.RESET}")
        elif choice == "7":
            run_quiz()
        elif choice == "0":
            print(f"\n{Color.GREEN}Terima kasih telah berlatih di Lab Fondasi Git! Sampai jumpa di modul berikutnya.{Color.RESET}\n")
            sys.exit(0)
        else:
            print(f"{Color.RED}Pilihan tidak valid.{Color.RESET}")


def run_quiz():
    header("KUIS REFLEKSI FONDASI ANATOMI & FILOSOFI GIT")
    questions = [
        {
            "q": "Apa perbedaan utama model penyimpanan Git dibanding VCS generasi lama seperti SVN?",
            "options": [
                "A. Git menyimpan daftar selisih baris (delta-based) secara berurutan",
                "B. Git menyimpan snapshot menyeluruh dari status proyek pada setiap commit",
                "C. Git mengunci file di server utama sebelum pengguna bisa mengedit",
                "D. Git menghapus file lama saat file baru dibuat"
            ],
            "ans": "B",
            "explain": "Git memperlakukan data sebagai serangkaian 'stream of snapshots', bukan tumpukan rekaman delta."
        },
        {
            "q": "Di mana file berada setelah perintah 'git add filename' dieksekusi?",
            "options": [
                "A. Working Tree",
                "B. Remote Server GitHub",
                "C. Staging Area (Index)",
                "D. Trash Bin"
            ],
            "ans": "C",
            "explain": "git add memindahkan file dari Working Tree ke Staging Area (Index) sebelum diikat menjadi snapshot commit."
        },
        {
            "q": "Mengapa Git menggunakan fungsi kriptografi SHA-1 untuk mengidentifikasi objek?",
            "options": [
                "A. Untuk mengompres berkas menjadi file zip",
                "B. Untuk mengunci file agar tidak bisa dibaca oleh sistem operasi",
                "C. Menjamin integritas data (Content-Addressable Storage); perubahan 1 bit akan mengubah hash",
                "D. Agar file dapat dikirim melalui protokol Bluetooth"
            ],
            "ans": "C",
            "explain": "SHA-1 menjadikan objek Git bersifat content-addressable: integritas mutlak di mana hash mencerminkan isi presisi objek."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"\n{Color.BOLD}Soal {idx}: {item['q']}{Color.RESET}")
        for opt in item["options"]:
            print(f"  {opt}")
        user_ans = input("Jawaban Anda (A/B/C/D): ").strip().upper()
        if user_ans == item["ans"]:
            print(f"{Color.GREEN}✓ Benar! {item['explain']}{Color.RESET}")
            score += 1
        else:
            print(f"{Color.RED}✗ Salah. Jawaban yang tepat: {item['ans']}. {item['explain']}{Color.RESET}")

    print(f"\n{Color.BOLD}Skor Akhir Kuis: {score}/{len(questions)}{Color.RESET}")
    if score == len(questions):
        print(f"{Color.GREEN}Sempurna! Anda memahami anatomi dan filosofi internal Git secara komprehensif.{Color.RESET}")
    else:
        print(f"{Color.YELLOW}Silakan tinjau kembali penjelasan di Menu 6 untuk memperkuat pemahaman.{Color.RESET}")


if __name__ == "__main__":
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print(f"\n\n{Color.YELLOW}Sesi lab dihentikan oleh pengguna.{Color.RESET}")
        sys.exit(0)
