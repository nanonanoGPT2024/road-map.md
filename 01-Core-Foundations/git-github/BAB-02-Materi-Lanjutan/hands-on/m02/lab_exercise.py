#!/usr/bin/env python3
"""
Lab Hands-on: Local Workflow & State Traversal (Git Under The Hood)
Category: 01-Core-Foundations | Chapter: 02 - Modul 02 Deep Dive

Deskripsi:
Script ini memodelkan arsitektur internal Git secara mendalam tanpa dependency eksternal.
Mencakup simulasi tiga area utama (Working Directory, Staging Area/Index, Object Store),
pembuatan objek SHA-1 (Blob, Tree, Commit), DAG (Directed Acyclic Graph) traversal,
dan time-travel (state checkout/rollback).
"""

import hashlib
import time
from typing import Dict, List, Optional, Tuple


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


class GitObject:
    """Basis representasi immutable object dalam Git Object Store."""
    def __init__(self, obj_type: str, content: bytes):
        self.obj_type = obj_type
        self.content = content
        # Format header Git canonical: "<type> <size>\0<content>"
        header = f"{obj_type} {len(content)}\0".encode("utf-8")
        self.raw_data = header + content
        self.sha1 = hashlib.sha1(self.raw_data).hexdigest()

    def __repr__(self) -> str:
        return f"<{self.obj_type.upper()} {self.sha1[:8]}>"


class GitEngine:
    """
    Mesin simulasi Git yang mengimplementasikan state transitions:
    Working Directory -> Staging Area (Index) -> Commit Object Graph.
    """

    def __init__(self):
        # Database object internal Git: {sha1: GitObject}
        self.object_store: Dict[str, GitObject] = {}
        # Working Directory (Simulasi File System lokal): {filepath: content}
        self.working_dir: Dict[str, str] = {}
        # Index / Staging Area: {filepath: blob_sha1}
        self.index: Dict[str, str] = {}
        # Referensi Branch: {branch_name: commit_sha1}
        self.branches: Dict[str, str] = {"main": ""}
        # HEAD: Penunjuk posisi saat ini (Branch name atau Detached Commit SHA-1)
        self.head: str = "main"

    def write_working_file(self, filepath: str, content: str) -> None:
        """Menulis atau memodifikasi file di Working Directory."""
        self.working_dir[filepath] = content

    def remove_working_file(self, filepath: str) -> None:
        """Menghapus file di Working Directory."""
        if filepath in self.working_dir:
            del self.working_dir[filepath]

    def add(self, filepath: str) -> str:
        """
        Simulasi 'git add':
        1. Membaca file dari Working Directory.
        2. Membuat Blob Object dengan hashing SHA-1.
        3. Menyimpan Blob di Object Store.
        4. Memetakan file path ke Blob SHA-1 di Staging Area (Index).
        """
        if filepath not in self.working_dir:
            raise FileNotFoundError(f"File {filepath} tidak ditemukan di working tree.")

        content_bytes = self.working_dir[filepath].encode("utf-8")
        blob = GitObject("blob", content_bytes)
        self.object_store[blob.sha1] = blob
        self.index[filepath] = blob.sha1
        return blob.sha1

    def commit(self, message: str, author: str = "Engineer <eng@system.local>") -> str:
        """
        Simulasi 'git commit':
        1. Mengompilasi Index saat ini menjadi Tree Object.
        2. Membuat Commit Object yang mereferensikan Tree dan Parent Commit.
        3. Memajukan pointer HEAD/Branch ke commit baru.
        """
        if not self.index:
            raise ValueError("Staging area (Index) kosong! Tidak ada yang bisa di-commit.")

        # 1. Bangun Tree Object dari Index entries
        tree_lines = []
        for path in sorted(self.index.keys()):
            blob_sha = self.index[path]
            tree_lines.append(f"100644 blob {blob_sha}\t{path}")
        tree_payload = "\n".join(tree_lines).encode("utf-8")
        tree = GitObject("tree", tree_payload)
        self.object_store[tree.sha1] = tree

        # 2. Ambil parent commit SHA dari HEAD
        parent_sha = self.get_head_commit()

        # 3. Bentuk format metadata Commit Object
        timestamp = int(time.time())
        commit_lines = [f"tree {tree.sha1}"]
        if parent_sha:
            commit_lines.append(f"parent {parent_sha}")
        commit_lines.append(f"author {author} {timestamp} +0000")
        commit_lines.append(f"committer {author} {timestamp} +0000")
        commit_lines.append("")
        commit_lines.append(message)

        commit_payload = "\n".join(commit_lines).encode("utf-8")
        commit_obj = GitObject("commit", commit_payload)
        self.object_store[commit_obj.sha1] = commit_obj

        # 4. Perbarui Branch / HEAD
        if self.head in self.branches:
            self.branches[self.head] = commit_obj.sha1
        else:
            self.head = commit_obj.sha1  # Detached HEAD state

        return commit_obj.sha1

    def get_head_commit(self) -> Optional[str]:
        """Mengambil Commit SHA saat ini yang ditunjuk oleh HEAD."""
        if self.head in self.branches:
            return self.branches[self.head] if self.branches[self.head] else None
        return self.head if self.head else None

    def status(self) -> Dict[str, List[str]]:
        """
        Simulasi 'git status':
        Membandingkan state Working Dir vs Index, dan Index vs HEAD Commit Tree.
        """
        head_commit_sha = self.get_head_commit()
        head_tree_index: Dict[str, str] = {}

        if head_commit_sha:
            commit_obj = self.object_store[head_commit_sha]
            lines = commit_obj.content.decode("utf-8").split("\n")
            tree_sha = lines[0].split()[1]
            tree_obj = self.object_store[tree_sha]
            for entry in tree_obj.content.decode("utf-8").split("\n"):
                if entry.strip():
                    parts = entry.split()
                    blob_sha = parts[2]
                    path = entry.split("\t")[1]
                    head_tree_index[path] = blob_sha

        # 1. Changes to be committed (Index vs HEAD)
        staged = []
        for path, blob_sha in self.index.items():
            if path not in head_tree_index:
                staged.append(f"new file: {path}")
            elif head_tree_index[path] != blob_sha:
                staged.append(f"modified: {path}")

        # 2. Changes not staged for commit (Working Tree vs Index)
        unstaged = []
        for path, blob_sha in self.index.items():
            if path not in self.working_dir:
                unstaged.append(f"deleted:  {path}")
            else:
                curr_content = self.working_dir[path].encode("utf-8")
                curr_blob = GitObject("blob", curr_content)
                if curr_blob.sha1 != blob_sha:
                    unstaged.append(f"modified: {path}")

        # 3. Untracked files (Working Tree vs Index)
        untracked = [p for p in self.working_dir if p not in self.index]

        return {"staged": staged, "unstaged": unstaged, "untracked": untracked}

    def checkout(self, target_commit_sha: str) -> None:
        """
        Simulasi 'git checkout <sha>' (State Traversal):
        Mengembalikan file di Working Directory dan Index ke snapshot pada target commit.
        """
        if target_commit_sha not in self.object_store:
            raise KeyError(f"Commit {target_commit_sha} tidak ada di database.")

        commit_obj = self.object_store[target_commit_sha]
        if commit_obj.obj_type != "commit":
            raise ValueError(f"Object {target_commit_sha} bukan merupakan commit.")

        # Ambil Tree
        lines = commit_obj.content.decode("utf-8").split("\n")
        tree_sha = lines[0].split()[1]
        tree_obj = self.object_store[tree_sha]

        # Reset Staging & Working Dir ke snapshot state commit
        self.index.clear()
        self.working_dir.clear()

        for entry in tree_obj.content.decode("utf-8").split("\n"):
            if not entry.strip():
                continue
            parts = entry.split()
            blob_sha = parts[2]
            path = entry.split("\t")[1]
            blob_obj = self.object_store[blob_sha]

            self.index[path] = blob_sha
            self.working_dir[path] = blob_obj.content.decode("utf-8")

        # Pindahkan HEAD (detached HEAD mode)
        self.head = target_commit_sha

    def log(self) -> List[Tuple[str, str, str]]:
        """
        DAG Traversal: Menelusuri rantai commit ke belakang via parent commit pointer.
        """
        history = []
        curr_sha = self.get_head_commit()

        while curr_sha:
            commit_obj = self.object_store[curr_sha]
            lines = commit_obj.content.decode("utf-8").split("\n")
            parent_sha = None
            message = ""
            for idx, line in enumerate(lines):
                if line.startswith("parent "):
                    parent_sha = line.split()[1]
                elif line == "":
                    message = "\n".join(lines[idx + 1:]).strip()
                    break

            history.append((curr_sha, message, parent_sha or "root"))
            curr_sha = parent_sha

        return history


def print_status_box(repo: GitEngine) -> None:
    """Utility visualisasi state workspace saat ini."""
    stat = repo.status()
    head = repo.get_head_commit()
    head_str = head[:8] if head else "(empty)"
    print(f"\n{ANSI.BOLD}--- GIT STATE [HEAD @ {head_str}] ---{ANSI.RESET}")

    if stat["staged"]:
        print(f"{ANSI.GREEN}Changes to be committed:{ANSI.RESET}")
        for s in stat["staged"]:
            print(f"  {ANSI.GREEN}+ {s}{ANSI.RESET}")
    if stat["unstaged"]:
        print(f"{ANSI.YELLOW}Changes not staged for commit:{ANSI.RESET}")
        for u in stat["unstaged"]:
            print(f"  {ANSI.YELLOW}* {u}{ANSI.RESET}")
    if stat["untracked"]:
        print(f"{ANSI.RED}Untracked files:{ANSI.RESET}")
        for ut in stat["untracked"]:
            print(f"  {ANSI.RED}? {ut}{ANSI.RESET}")
    if not (stat["staged"] or stat["unstaged"] or stat["untracked"]):
        print(f"{ANSI.CYAN}Working tree clean. Nothing to commit.{ANSI.RESET}")


def run_lab():
    print(f"{ANSI.BOLD}{ANSI.MAGENTA}=== LAB: LOCAL WORKFLOW & STATE TRAVERSAL SIMULATION ==={ANSI.RESET}\n")
    repo = GitEngine()

    # Step 1: Inisialisasi file awal di Working Directory
    print(f"{ANSI.CYAN}[STEP 1] Membuat file lokal di Working Directory...{ANSI.RESET}")
    repo.write_working_file("kernel.py", "def boot(): return 'v1.0.0'")
    repo.write_working_file("README.md", "# Core System Architecture")
    print_status_box(repo)

    # Step 2: Melakukan staging (git add)
    print(f"\n{ANSI.CYAN}[STEP 2] Staging file ke Index (git add)...{ANSI.RESET}")
    blob1 = repo.add("kernel.py")
    blob2 = repo.add("README.md")
    print(f"  Created Blob kernel.py -> {ANSI.MAGENTA}{blob1}{ANSI.RESET}")
    print(f"  Created Blob README.md -> {ANSI.MAGENTA}{blob2}{ANSI.RESET}")
    print_status_box(repo)

    # Step 3: Membuat Commit Pertama
    print(f"\n{ANSI.CYAN}[STEP 3] Membuat commit snapshot pertama...{ANSI.RESET}")
    c1 = repo.commit("feat: initial kernel implementation v1.0.0")
    print(f"  {ANSI.GREEN}Commit 1 created: {c1}{ANSI.RESET}")
    print_status_box(repo)

    # Step 4: Perubahan Berantai (Commit Kedua)
    print(f"\n{ANSI.CYAN}[STEP 4] Mutasi file: update kernel.py & tambah driver.py...{ANSI.RESET}")
    repo.write_working_file("kernel.py", "def boot(): return 'v1.1.0-hotfix'")
    repo.write_working_file("driver.py", "def init_hardware(): pass")
    print_status_box(repo)

    print(f"\n{ANSI.CYAN}[STEP 5] Menambahkan mutasi dan commit kedua...{ANSI.RESET}")
    repo.add("kernel.py")
    repo.add("driver.py")
    c2 = repo.commit("fix: kernel patch hotfix and new driver stub")
    print(f"  {ANSI.GREEN}Commit 2 created: {c2}{ANSI.RESET}")
    print_status_box(repo)

    # Step 6: Log Traversal (DAG History)
    print(f"\n{ANSI.BOLD}{ANSI.BLUE}[STEP 6] Menelusuri Commit DAG History (git log):{ANSI.RESET}")
    for sha, msg, parent in repo.log():
        print(f"  * {ANSI.YELLOW}{sha[:8]}{ANSI.RESET} [parent: {parent[:8]}] - {msg}")

    # Step 7: State Traversal (Checkout Time Travel ke Commit Pertama)
    print(f"\n{ANSI.BOLD}{ANSI.RED}[STEP 7] State Traversal: Checkout ke Snapshot Pertama ({c1[:8]})...{ANSI.RESET}")
    print("  Mengeksekusi: git checkout", c1[:8])
    repo.checkout(c1)

    print(f"\n{ANSI.CYAN}[VERIFIKASI RESTORASI FILE]{ANSI.RESET}")
    print(f"  Daftar file di Working Directory:")
    for path, content in repo.working_dir.items():
        print(f"    - {ANSI.BOLD}{path}{ANSI.RESET} -> content: {repr(content)}")

    print(f"\n{ANSI.CYAN}[VERIFIKASI OBJECT STORE INTERNALS]{ANSI.RESET}")
    print(f"  Total objek tersimpan dalam .git/objects: {ANSI.BOLD}{len(repo.object_store)}{ANSI.RESET}")
    for sha, obj in repo.object_store.items():
        print(f"    SHA-1: {sha[:10]}... | Type: {obj.obj_type.ljust(6)} | Byte Size: {len(obj.content)}")

    print(f"\n{ANSI.BOLD}{ANSI.GREEN}=== LAB BERHASIL: Konsep 3-Tier State & Traversal Teruji ==={ANSI.RESET}")


if __name__ == "__main__":
    run_lab()