#!/usr/bin/env python3
"""
Lab Hands-on: Git Core Foundations - Bab 02
Inisialisasi, Konfigurasi, & Siklus Hidup Objek Git (Blob, Tree, Commit)

Script ini memodelkan 'Content-Addressable Storage Engine' internal Git:
1. Inisialisasi struktur direktori repositori (.minigit).
2. Mekanisme resolusi hierarki konfigurasi cascading (System -> Global -> Local).
3. Hashing kriptografis (SHA-1) dengan header tipe Git: [type] [size]\0[content].
4. Kompresi lossless zlib dan serialisasi objek ke disk.
5. Siklus hidup objek: Blob -> Tree -> Commit (Membangun Directed Acyclic Graph / DAG).
"""

import os
import sys
import zlib
import hashlib
import time
import shutil
from pathlib import Path

# ANSI Color Codes untuk visualisasi terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

class GitConfigHierarchy:
    """
    Simulasi hierarki konfigurasi Git: System, Global, dan Local.
    Menerapkan prinsip 'Most Specific Wins' (Local menimpa Global, Global menimpa System).
    """
    def __init__(self):
        self.system_config = {}
        self.global_config = {}
        self.local_config = {}

    def set_config(self, scope: str, key: str, value: str):
        if scope == 'system':
            self.system_config[key] = value
        elif scope == 'global':
            self.global_config[key] = value
        elif scope == 'local':
            self.local_config[key] = value
        else:
            raise ValueError(f"Scope tidak valid: {scope}")

    def get_effective_config(self, key: str) -> tuple:
        """Mengambil nilai konfigurasi efektif beserta sumber definisinya."""
        if key in self.local_config:
            return self.local_config[key], "local (.minigit/config)"
        if key in self.global_config:
            return self.global_config[key], "global (~/.minigitconfig)"
        if key in self.system_config:
            return self.system_config[key], "system (/etc/minigitconfig)"
        return None, "unset"


class MiniGitEngine:
    """
    Implementasi mesin low-level Git untuk manajemen siklus hidup objek.
    """
    def __init__(self, repo_path: str = "./sandbox_repo"):
        self.worktree = Path(repo_path).resolve()
        self.gitdir = self.worktree / ".minigit"
        self.objects_dir = self.gitdir / "objects"
        self.refs_dir = self.gitdir / "refs"
        self.config_manager = GitConfigHierarchy()

    def init_repo(self):
        """Membuat struktur internal repositori identik dengan 'git init'."""
        if self.gitdir.exists():
            shutil.rmtree(self.gitdir)

        (self.objects_dir / "info").mkdir(parents=True, exist_ok=True)
        (self.objects_dir / "pack").mkdir(parents=True, exist_ok=True)
        (self.refs_dir / "heads").mkdir(parents=True, exist_ok=True)
        (self.refs_dir / "tags").mkdir(parents=True, exist_ok=True)

        # Inisialisasi HEAD menunjuk ke branch default
        head_file = self.gitdir / "HEAD"
        head_file.write_text("ref: refs/heads/main\n")

        # Inisialisasi konfigurasi dasar lokal
        config_file = self.gitdir / "config"
        config_file.write_text("[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n")

    def _hash_and_store(self, obj_type: str, data: bytes) -> str:
        """
        Inti Content-Addressable Storage Git:
        1. Bungkus data dengan Git header: '<type> <size>\0'
        2. Hitung hash SHA-1 dari (header + data)
        3. Kompres menggunakan zlib (tingkat kompresi default)
        4. Tulis ke direktori .minigit/objects/xx/yyyy...
        """
        header = f"{obj_type} {len(data)}\0".encode('ascii')
        full_payload = header + data
        sha1_hash = hashlib.sha1(full_payload).hexdigest()

        # Sharding: 2 karakter pertama sebagai nama folder, 38 sisanya nama file
        dir_name = sha1_hash[:2]
        file_name = sha1_hash[2:]
        obj_folder = self.objects_dir / dir_name
        obj_folder.mkdir(exist_ok=True)

        obj_file = obj_folder / file_name
        if not obj_file.exists():
            compressed_data = zlib.compress(full_payload)
            obj_file.write_bytes(compressed_data)

        return sha1_hash

    def read_object(self, sha1_hash: str) -> tuple:
        """Membaca objek Git dari disk, dekompresi zlib, dan ekstrak tipe/konten."""
        dir_name = sha1_hash[:2]
        file_name = sha1_hash[2:]
        obj_file = self.objects_dir / dir_name / file_name

        if not obj_file.exists():
            raise FileNotFoundError(f"Objek Git {sha1_hash} tidak ditemukan di database.")

        raw_data = zlib.decompress(obj_file.read_bytes())
        null_idx = raw_data.find(b'\0')
        header = raw_data[:null_idx].decode('ascii')
        obj_type, size = header.split(' ')
        content = raw_data[null_idx + 1:]
        return obj_type, int(size), content

    def create_blob(self, content: bytes) -> str:
        """Menyimpan representasi file (Blob). Blob tidak menyimpan metadata nama file."""
        return self._hash_and_store("blob", content)

    def create_tree(self, entries: list) -> str:
        """
        Menyimpan direktori (Tree).
        Format biner Git Tree entry: [mode octal string] [filename]\0[20-byte binary SHA-1]
        """
        tree_payload = bytearray()
        # Entri harus diurutkan berdasarkan nama (persyaratan Git deterministik)
        sorted_entries = sorted(entries, key=lambda x: x['name'])

        for entry in sorted_entries:
            mode_str = f"{entry['mode']} {entry['name']}\0".encode('ascii')
            binary_sha = bytes.fromhex(entry['sha'])
            tree_payload.extend(mode_str)
            tree_payload.extend(binary_sha)

        return self._hash_and_store("tree", bytes(tree_payload))

    def create_commit(self, tree_sha: str, parent_sha: str, author_name: str, author_email: str, message: str) -> str:
        """
        Menyimpan snapshot riwayat (Commit).
        Menghubungkan Tree snapshot, parent hash, identitas author, timestamp, dan pesan log.
        """
        timestamp = int(time.time())
        timezone = "+0700"  # WIB
        commit_lines = [
            f"tree {tree_sha}",
        ]
        if parent_sha:
            commit_lines.append(f"parent {parent_sha}")

        author_entry = f"author {author_name} <{author_email}> {timestamp} {timezone}"
        committer_entry = f"committer {author_name} <{author_email}> {timestamp} {timezone}"
        commit_lines.append(author_entry)
        commit_lines.append(committer_entry)
        commit_lines.append("")
        commit_lines.append(message)
        commit_lines.append("")

        commit_payload = "\n".join(commit_lines).encode('utf-8')
        return self._hash_and_store("commit", commit_payload)


def print_banner(step_num: int, title: str):
    print(f"\n{Colors.CYAN}{'=' * 75}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.YELLOW}[LANGKAH {step_num}] {title}{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 75}{Colors.RESET}")

def main():
    repo = MiniGitEngine(repo_path="./lab_git_internals")
    
    # --- LANGKAH 1: Inisialisasi Repositori ---
    print_banner(1, "Inisialisasi Repositori Git Internal (.minigit)")
    repo.init_repo()
    print(f"{Colors.GREEN}✔ Struktur skeleton repositori berhasil dibuat di:{Colors.RESET} {repo.gitdir}")
    for root, dirs, files in os.walk(repo.gitdir):
        level = root.replace(str(repo.gitdir), '').count(os.sep)
        indent = ' ' * 4 * level
        folder = os.path.basename(root)
        print(f"{indent}{Colors.BLUE}📁 {folder}/{Colors.RESET}")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            print(f"{subindent}{Colors.DIM}📄 {f}{Colors.RESET}")

    # --- LANGKAH 2: Simulasi Hierarki Konfigurasi ---
    print_banner(2, "Evaluasi Cascading Git Configuration (System vs Global vs Local)")
    # Set nilai konfigurasi di tingkat yang berbeda
    repo.config_manager.set_config('system', 'user.name', 'System Admin')
    repo.config_manager.set_config('system', 'user.email', 'root@system.local')
    
    repo.config_manager.set_config('global', 'user.name', 'Aditya Global')
    repo.config_manager.set_config('global', 'user.email', 'aditya@developer.com')
    
    # Local menimpa email, tetapi name mewarisi global jika tidak di-set
    repo.config_manager.set_config('local', 'user.email', 'aditya.project@enterprise.com')

    for key in ['user.name', 'user.email', 'core.editor']:
        val, source = repo.config_manager.get_effective_config(key)
        print(f"Resolusi Key {Colors.BOLD}'{key}'{Colors.RESET}:")
        print(f"  └─ Nilai Terpilih : {Colors.GREEN}{val}{Colors.RESET}")
        print(f"  └─ Sumber Hierarki: {Colors.YELLOW}{source}{Colors.RESET}")

    author_name, _ = repo.config_manager.get_effective_config('user.name')
    author_email, _ = repo.config_manager.get_effective_config('user.email')

    # --- LANGKAH 3: Siklus Hidup Objek - Pembuatan Blob & Deduplikasi Konten ---
    print_banner(3, "Pembuatan Objek Blob & Content-Addressability")
    file1_content = b"print('Halo Dunia! Ini adalah arsitektur internal Git.')\n"
    file2_identical = b"print('Halo Dunia! Ini adalah arsitektur internal Git.')\n"
    file3_different = b"version = '2.0.0'\n"

    blob1_sha = repo.create_blob(file1_content)
    blob2_sha = repo.create_blob(file2_identical)
    blob3_sha = repo.create_blob(file3_different)

    print(f"File 1 Hash : {Colors.CYAN}{blob1_sha}{Colors.RESET}")
    print(f"File 2 Hash : {Colors.CYAN}{blob2_sha}{Colors.RESET} (Konten identik dengan File 1)")
    print(f"File 3 Hash : {Colors.CYAN}{blob3_sha}{Colors.RESET} (Konten berbeda)")

    assert blob1_sha == blob2_sha, "Algoritma Content Addressable gagal mendeteksi kesamaan konten!"
    print(f"{Colors.GREEN}✔ DEDUPLIKASI BERHASIL:{Colors.RESET} File identik merujuk ke satu objek fisik yang sama.")

    # Bukti penyimpanan fisik dan inspeksi dekompresi
    obj_type, size, content = repo.read_object(blob1_sha)
    print(f"\n{Colors.BOLD}Inspeksi Fisik Objek Database:{Colors.RESET}")
    print(f"  • Path Disimpan : .minigit/objects/{blob1_sha[:2]}/{blob1_sha[2:]}")
    print(f"  • Tipe Header   : {Colors.YELLOW}{obj_type}{Colors.RESET}")
    print(f"  • Ukuran Konten : {size} bytes")
    print(f"  • Data Mentah   : {content.decode('utf-8').strip()}")

    # --- LANGKAH 4: Siklus Hidup Objek - Struktur Direktori (Tree) ---
    print_banner(4, "Pembuatan Objek Tree (Struktur Direktori)")
    tree_entries = [
        {"mode": "100644", "name": "main.py", "sha": blob1_sha},
        {"mode": "100644", "name": "version.py", "sha": blob3_sha}
    ]
    tree_sha = repo.create_tree(tree_entries)
    print(f"Tree Root SHA-1: {Colors.CYAN}{tree_sha}{Colors.RESET}")
    
    t_type, t_size, t_content = repo.read_object(tree_sha)
    print(f"Tree Objek terdaftar ({t_size} bytes biner).")
    print(f"{Colors.BOLD}Entri Hirarki File dalam Tree:{Colors.RESET}")
    for entry in tree_entries:
        print(f"  [Mode: {entry['mode']}] ─── {entry['name']} ───> Blob SHA: {entry['sha']}")

    # --- LANGKAH 5: Siklus Hidup Objek - Snapshot Commit & Graph Linkage ---
    print_banner(5, "Pembuatan Objek Commit & DAG Linkage")
    # Commit Pertama (Root Commit)
    commit1_sha = repo.create_commit(
        tree_sha=tree_sha,
        parent_sha=None,
        author_name=author_name,
        author_email=author_email,
        message="feat: commit inisial arsitektur engine"
    )
    print(f"Commit 1 (Root)  : {Colors.GREEN}{commit1_sha}{Colors.RESET}")

    # Simulasi modifikasi: Menambahkan file baru dan membuat Commit Kedua
    blob4_sha = repo.create_blob(b"# Dokumentasi Internal Git Engine\n")
    tree2_entries = tree_entries + [{"mode": "100644", "name": "README.md", "sha": blob4_sha}]
    tree2_sha = repo.create_tree(tree2_entries)

    # Commit Kedua mengaitkan parent ke Commit 1
    commit2_sha = repo.create_commit(
        tree_sha=tree2_sha,
        parent_sha=commit1_sha,
        author_name=author_name,
        author_email=author_email,
        message="docs: tambahkan dokumentasi awal README"
    )
    print(f"Commit 2 (Anak)  : {Colors.GREEN}{commit2_sha}{Colors.RESET}")

    # Membaca Payload Commit 2
    c_type, c_size, c_payload = repo.read_object(commit2_sha)
    print(f"\n{Colors.BOLD}Isi Mentah Objek Commit 2:{Colors.RESET}")
    print(f"{Colors.DIM}{c_payload.decode('utf-8')}{Colors.RESET}")

    # --- LANGKAH 6: Visualisasi DAG (Directed Acyclic Graph) ---
    print_banner(6, "Topologi Graf Objek Git (DAG Repository Representation)")
    dag_visualization = f"""
    [Commit 2: {commit2_sha[:7]}] 
          │
          ├─► [Parent Link] ──► [Commit 1: {commit1_sha[:7]}] (Root)
          │                            │
          │                            └─► [Tree: {tree_sha[:7]}]
          │                                      ├─► main.py    ({blob1_sha[:7]})
          │                                      └─► version.py ({blob3_sha[:7]})
          │
          └─► [Tree: {tree2_sha[:7]}]
                    ├─► main.py    ({blob1_sha[:7]}) [Reused Object - Zero Cost Copy]
                    ├─► version.py ({blob3_sha[:7]}) [Reused Object - Zero Cost Copy]
                    └─► README.md  ({blob4_sha[:7]}) [New Blob]
    """
    print(f"{Colors.CYAN}{dag_visualization}{Colors.RESET}")
    print(f"{Colors.GREEN}{Colors.BOLD}Lab Eksekusi Berhasil Selesai! Arsitektur penyimpanan Git terverifikasi.{Colors.RESET}\n")

if __name__ == "__main__":
    main()