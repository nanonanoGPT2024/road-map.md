#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Inisialisasi, Konfigurasi, dan Siklus Objek Git
BAB-02: Inisialisasi, Konfigurasi, dan Siklus Objek Git
Modul 01 - Hands-on Lab Interaktif

Script ini mendemonstrasikan internal Git:
1. Inisialisasi struktur direktori .git (HEAD, objects, refs, config).
2. Mekanisme cascading konfigurasi Git (System vs Global vs Local).
3. Hashing konten objek Git mentah (Blob, Tree, Commit) dengan SHA-1 murni.
4. Inspeksi objek layaknya perintah internal `git cat-file -t` dan `git cat-file -p`.
"""

import sys
import hashlib
import zlib
import time
from typing import Dict, List, Optional, Tuple


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    BLUE = "\033[34m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"


class GitObject:
    def __init__(self, obj_type: str, content_bytes: bytes):
        self.obj_type = obj_type
        self.raw_content = content_bytes
        # Format header internal Git: "<type> <size>\0<content>"
        header = f"{obj_type} {len(content_bytes)}\0".encode("utf-8")
        self.store = header + content_bytes
        self.sha1 = hashlib.sha1(self.store).hexdigest()
        self.compressed = zlib.compress(self.store)


class GitDatabase:
    def __init__(self):
        self.objects: Dict[str, GitObject] = {}
        self.refs: Dict[str, str] = {}
        self.head: str = "ref: refs/heads/main"
        self.is_initialized: bool = False

    def init_repository(self) -> None:
        self.objects.clear()
        self.refs.clear()
        self.head = "ref: refs/heads/main"
        self.is_initialized = True

    def put_object(self, obj_type: str, content_bytes: bytes) -> str:
        obj = GitObject(obj_type, content_bytes)
        self.objects[obj.sha1] = obj
        return obj.sha1

    def get_object(self, sha1: str) -> Optional[GitObject]:
        return self.objects.get(sha1)


class ConfigManager:
    def __init__(self):
        self.system_config: Dict[str, str] = {
            "core.editor": "nano",
            "core.autocrlf": "input"
        }
        self.global_config: Dict[str, str] = {
            "user.name": "Developer Global",
            "user.email": "dev@global.internal",
            "init.defaultBranch": "main"
        }
        self.local_config: Dict[str, str] = {}

    def get(self, key: str) -> Tuple[Optional[str], str]:
        """Mencari nilai konfigurasi dengan urutan precedensi: Local -> Global -> System."""
        if key in self.local_config:
            return self.local_config[key], "local (.git/config)"
        if key in self.global_config:
            return self.global_config[key], "global (~/.gitconfig)"
        if key in self.system_config:
            return self.system_config[key], "system (/etc/gitconfig)"
        return None, "not set"

    def set_local(self, key: str, value: str) -> None:
        self.local_config[key] = value

    def set_global(self, key: str, value: str) -> None:
        self.global_config[key] = value


def print_banner():
    print(f"{ANSI.CYAN}{ANSI.BOLD}{'=' * 70}{ANSI.RESET}")
    print(f"{ANSI.GREEN}{ANSI.BOLD}  SIMULASI INTERAKTIF GIT: BAB-02 (STRUKTUR & SIKLUS OBJEK){ANSI.RESET}")
    print(f"{ANSI.YELLOW}  Laboratorium Pemahaman Tingkat Rendah Inisialisasi & Objek Git{ANSI.RESET}")
    print(f"{ANSI.CYAN}{ANSI.BOLD}{'=' * 70}{ANSI.RESET}\n")


def demo_git_init(db: GitDatabase):
    print(f"{ANSI.BOLD}[1] Simulasi `git init` & Bedah Arsitektur `.git`{ANSI.RESET}")
    db.init_repository()
    print(f"{ANSI.GREEN}Repository berhasil diinisialisasi! Direktori virtual `.git/` dibuat.{ANSI.RESET}")
    print(f"""
{ANSI.CYAN}.git/
├── HEAD                {ANSI.YELLOW}-> Berisi pointer aktif ('{db.head}'){ANSI.CYAN}
├── config              {ANSI.YELLOW}-> Berisi konfigurasi spesifik lokal repositori{ANSI.CYAN}
├── description         {ANSI.YELLOW}-> Digunakan untuk GitWeb (opsional){ANSI.CYAN}
├── hooks/              {ANSI.YELLOW}-> Direktori script otomasi client-side & server-side{ANSI.CYAN}
├── info/
│   └── exclude         {ANSI.YELLOW}-> Pola gitignore privat lokal per-repo{ANSI.CYAN}
├── objects/            {ANSI.YELLOW}-> Object Database (Content-Addressable Storage){ANSI.CYAN}
│   ├── info/
│   └── pack/           {ANSI.YELLOW}-> Berisi packfiles untuk kompresi delta{ANSI.CYAN}
└── refs/
    ├── heads/          {ANSI.YELLOW}-> Menyimpan SHA-1 branch lokal{ANSI.CYAN}
    └── tags/           {ANSI.YELLOW}-> Menyimpan SHA-1 release tags{ANSI.RESET}
""")


def demo_git_config(cfg: ConfigManager):
    print(f"\n{ANSI.BOLD}[2] Simulasi Cascading Hirarki Konfigurasi `git config`{ANSI.RESET}")
    keys_to_check = ["user.name", "user.email", "core.editor", "init.defaultBranch"]
    
    print(f"{ANSI.YELLOW}Kondisi Awal Konfigurasi:{ANSI.RESET}")
    for k in keys_to_check:
        val, scope = cfg.get(k)
        print(f"  - {ANSI.BOLD}{k:<18}{ANSI.RESET}: {val} {ANSI.MAGENTA}(asal: {scope}){ANSI.RESET}")

    print(f"\n{ANSI.BLUE}Eksekusi simulasi: `git config --local user.name 'Developer Project X'`{ANSI.RESET}")
    print(f"{ANSI.BLUE}Eksekusi simulasi: `git config --local user.email 'projx@company.internal'`{ANSI.RESET}")
    cfg.set_local("user.name", "Developer Project X")
    cfg.set_local("user.email", "projx@company.internal")

    print(f"\n{ANSI.GREEN}Hasil Evaluasi Precedensi (Local menimpa Global & System):{ANSI.RESET}")
    for k in keys_to_check:
        val, scope = cfg.get(k)
        print(f"  - {ANSI.BOLD}{k:<18}{ANSI.RESET}: {ANSI.BOLD}{val}{ANSI.RESET} {ANSI.GREEN}(asal: {scope}){ANSI.RESET}")


def demo_git_lifecycle(db: GitDatabase):
    print(f"\n{ANSI.BOLD}[3] Simulasi Siklus Objek Git: Blob -> Tree -> Commit{ANSI.RESET}")
    if not db.is_initialized:
        print(f"{ANSI.RED}Repositori belum diinisialisasi! Menjalankan inisialisasi otomatis...{ANSI.RESET}")
        db.init_repository()

    # Tahap 1: Blob Object
    filename1 = "README.md"
    content1 = "# Dokumentasi Proyek\nInisialisasi repositori Git dan siklus objek.\n"
    blob_sha1 = db.put_object("blob", content1.encode("utf-8"))
    print(f"\n{ANSI.CYAN}--- Langkah A: Membuat Blob (File Content) ---{ANSI.RESET}")
    print(f"File: {ANSI.BOLD}{filename1}{ANSI.RESET}")
    print(f"Header: 'blob {len(content1.encode('utf-8'))}\\0'")
    print(f"SHA-1 Hash: {ANSI.GREEN}{blob_sha1}{ANSI.RESET}")
    print(f"Lokasi Penyimpanan: .git/objects/{blob_sha1[:2]}/{blob_sha1[2:]}")

    # Tahap 2: Tree Object
    print(f"\n{ANSI.CYAN}--- Langkah B: Membuat Tree (Directory Listing Snapshot) ---{ANSI.RESET}")
    # Tree format: "<mode> <filename>\0<20-byte-binary-sha1>"
    mode = "100644"
    tree_entry = f"{mode} {filename1}\0".encode("utf-8") + bytes.fromhex(blob_sha1)
    tree_sha1 = db.put_object("tree", tree_entry)
    print(f"Tree Snapshot Root: SHA-1 -> {ANSI.GREEN}{tree_sha1}{ANSI.RESET}")
    print(f"Entri: {mode} blob {blob_sha1}    {filename1}")

    # Tahap 3: Commit Object
    print(f"\n{ANSI.CYAN}--- Langkah C: Membuat Commit (Metadata & Pointer Snapshot) ---{ANSI.RESET}")
    timestamp = int(time.time())
    timezone = "+0700"
    author_line = f"Developer Project X <projx@company.internal> {timestamp} {timezone}"
    commit_payload = (
        f"tree {tree_sha1}\n"
        f"author {author_line}\n"
        f"committer {author_line}\n\n"
        f"feat: inisialisasi repositori dan modul pengenalan\n"
    )
    commit_sha1 = db.put_object("commit", commit_payload.encode("utf-8"))
    db.refs["refs/heads/main"] = commit_sha1
    print(f"Commit SHA-1: {ANSI.GREEN}{commit_sha1}{ANSI.RESET}")
    print(f"Branch `main` diperbarui ke commit ini ({ANSI.YELLOW}refs/heads/main -> {commit_sha1[:7]}{ANSI.RESET})")


def inspect_cat_file(db: GitDatabase):
    print(f"\n{ANSI.BOLD}[4] Simulasi `git cat-file` (Inspeksi Objek Tingkat Rendah){ANSI.RESET}")
    if not db.objects:
        print(f"{ANSI.RED}Database objek kosong. Jalankan simulasi siklus objek terlebih dahulu.{ANSI.RESET}")
        return

    print(f"Daftar SHA-1 yang tersimpan di .git/objects:")
    for sha, obj in db.objects.items():
        print(f" - {ANSI.YELLOW}{sha}{ANSI.RESET} [{ANSI.CYAN}{obj.obj_type:<6}{ANSI.RESET}] ({len(obj.raw_content)} bytes)")

    user_sha = input(f"\n{ANSI.BOLD}Masukkan SHA-1 objek (atau ketik 'all' untuk semua): {ANSI.RESET}").strip()
    target_shas = list(db.objects.keys()) if user_sha.lower() == "all" else [user_sha]

    for sha in target_shas:
        obj = db.get_object(sha)
        if not obj:
            print(f"{ANSI.RED}Error: Objek dengan SHA-1 '{sha}' tidak ditemukan.{ANSI.RESET}")
            continue

        print(f"\n{ANSI.BOLD}=== Inspeksi Hash: {sha} ==={ANSI.RESET}")
        print(f"$ git cat-file -t {sha[:7]}")
        print(f"Tipe Objek: {ANSI.GREEN}{obj.obj_type}{ANSI.RESET}")
        print(f"$ git cat-file -s {sha[:7]}")
        print(f"Ukuran Konten: {len(obj.raw_content)} bytes")
        print(f"$ git cat-file -p {sha[:7]}")
        print(f"{ANSI.YELLOW}--- Payload Terdekompresi ---{ANSI.RESET}")
        if obj.obj_type == "tree":
            print(f"[Raw binary tree data holding blob pointers: {obj.raw_content.hex()[:60]}...]")
        else:
            print(obj.raw_content.decode("utf-8", errors="replace").rstrip())
        print(f"{ANSI.YELLOW}-----------------------------{ANSI.RESET}")


def main_menu():
    db = GitDatabase()
    cfg = ConfigManager()

    while True:
        print_banner()
        print(f"Pilih skenario hands-on:")
        print(f" 1. Eksekusi `git init` & Struktur Internal `.git`")
        print(f" 2. Uji Precedensi `git config` (System -> Global -> Local)")
        print(f" 3. Siklus Objek Git (Blob -> Tree -> Commit)")
        print(f" 4. Inspeksi Objek Menggunakan `git cat-file` (-t, -p, -s)")
        print(f" 5. Jalankan Seluruh Skenario Otomatis (Demo Lengkap)")
        print(f" 0. Keluar")
        print()

        choice = input(f"{ANSI.BOLD}Masukkan pilihan [0-5]: {ANSI.RESET}").strip()

        if choice == "1":
            demo_git_init(db)
        elif choice == "2":
            demo_git_config(cfg)
        elif choice == "3":
            demo_git_lifecycle(db)
        elif choice == "4":
            inspect_cat_file(db)
        elif choice == "5":
            demo_git_init(db)
            demo_git_config(cfg)
            demo_git_lifecycle(db)
            print(f"\n{ANSI.GREEN}{ANSI.BOLD}Verifikasi Otomatis Siklus Objek Berhasil!{ANSI.RESET}")
        elif choice == "0":
            print(f"\n{ANSI.GREEN}Terima kasih telah mempelajari fondasi internal Git!{ANSI.RESET}")
            sys.exit(0)
        else:
            print(f"{ANSI.RED}Pilihan tidak valid, silakan coba lagi.{ANSI.RESET}")

        input(f"\n{ANSI.CYAN}Tekan [Enter] untuk kembali ke menu utama...{ANSI.RESET}")
        print("\n" * 2)


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{ANSI.YELLOW}Program dihentikan oleh user. Sampai jumpa!{ANSI.RESET}")
        sys.exit(0)
