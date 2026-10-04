#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Git Object Database & Plumbing vs Porcelain
BAB-01: Arsitektur Inti Plumbing vs Porcelain

Skrip ini mendemonstrasikan implementasi internal objek Git murni (in-memory & direct hashing):
1. Perhitungan header dan SHA-1 object (blob, tree, commit)
2. Kompresi dan dekompresi zlib
3. Dekonstruksi perintah Porcelain (git add, git commit) menjadi Plumbing
   (hash-object, write-tree, commit-tree, update-ref)
"""

import hashlib
import zlib
import time
import sys
from typing import Dict, Tuple, Optional, List


# ANSI Terminal Colors
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    DIM = "\033[2m"


class MockGitRepository:
    def __init__(self):
        # Key: 40-char SHA1 hex digest -> Value: compressed zlib bytes
        self.objects: Dict[str, bytes] = {}
        # Key: ref path (e.g. 'refs/heads/main') -> Value: commit SHA1
        self.refs: Dict[str, str] = {}
        self.head: str = "ref: refs/heads/main"
        # Staging area / Index: path -> SHA1
        self.index: Dict[str, str] = {}

    # =========================================================================
    # PLUMBING COMMANDS
    # =========================================================================

    def hash_object(self, obj_type: str, content_bytes: bytes, write: bool = True) -> str:
        """Plumbing: git hash-object -w -t <type>"""
        header = f"{obj_type} {len(content_bytes)}\0".encode("utf-8")
        store = header + content_bytes
        sha1 = hashlib.sha1(store).hexdigest()

        if write:
            compressed = zlib.compress(store)
            self.objects[sha1] = compressed
        return sha1

    def cat_file(self, sha1: str, mode: str = "-p") -> Tuple[str, str]:
        """Plumbing: git cat-file -t / -p <hash>"""
        if sha1 not in self.objects:
            raise KeyError(f"fatal: Not a valid object name {sha1}")

        raw = zlib.decompress(self.objects[sha1])
        null_idx = raw.find(b"\0")
        header = raw[:null_idx].decode("utf-8")
        obj_type, size_str = header.split(" ")
        body = raw[null_idx + 1:]

        if mode == "-t":
            return obj_type, f"type: {obj_type}, size: {size_str} bytes"
        return obj_type, body.decode("utf-8", errors="replace")

    def write_tree(self) -> str:
        """Plumbing: git write-tree dari current index/staging area"""
        if not self.index:
            raise ValueError("Staging area (index) kosong!")

        # Format binary tree entry: [mode] [name]\0[binary SHA-1 20-bytes]
        # Untuk tujuan simulasi & inspeksi, kita serialisasikan tree format teks kanonik:
        tree_entries = []
        for path in sorted(self.index.keys()):
            blob_hash = self.index[path]
            tree_entries.append(f"100644 blob {blob_hash}\t{path}")

        tree_content = "\n".join(tree_entries) + "\n"
        tree_bytes = tree_content.encode("utf-8")
        return self.hash_object("tree", tree_bytes, write=True)

    def commit_tree(
        self,
        tree_sha: str,
        parent_sha: Optional[str],
        message: str,
        author: str = "Developer <dev@domain.local>"
    ) -> str:
        """Plumbing: git commit-tree <tree-hash> -p <parent-hash> -m <msg>"""
        timestamp = int(time.time())
        timezone = "+0700"

        lines = [f"tree {tree_sha}"]
        if parent_sha:
            lines.append(f"parent {parent_sha}")
        lines.append(f"author {author} {timestamp} {timezone}")
        lines.append(f"committer {author} {timestamp} {timezone}")
        lines.append("")
        lines.append(message)
        lines.append("")

        commit_bytes = "\n".join(lines).encode("utf-8")
        return self.hash_object("commit", commit_bytes, write=True)

    def update_ref(self, ref_name: str, new_sha: str):
        """Plumbing: git update-ref <ref> <newvalue>"""
        self.refs[ref_name] = new_sha

    # =========================================================================
    # PORCELAIN COMMANDS
    # =========================================================================

    def porcelain_add(self, filename: str, content: str):
        """Porcelain: git add <file>"""
        print(f"{Color.CYAN}→ [PORCELAIN] git add {filename}{Color.RESET}")
        content_bytes = content.encode("utf-8")
        blob_sha = self.hash_object("blob", content_bytes, write=True)
        self.index[filename] = blob_sha
        print(f"  {Color.DIM}↳ Under the hood: git hash-object -w -> {blob_sha[:12]}{Color.RESET}")
        print(f"  {Color.DIM}↳ Under the hood: git update-index --add --cacheinfo 100644 {blob_sha[:8]} {filename}{Color.RESET}")

    def porcelain_commit(self, message: str) -> str:
        """Porcelain: git commit -m <message>"""
        print(f"{Color.GREEN}→ [PORCELAIN] git commit -m \"{message}\"{Color.RESET}")
        
        # 1. Plumbing: write-tree
        tree_sha = self.write_tree()
        print(f"  {Color.DIM}↳ (Plumbing 1) git write-tree               => tree {tree_sha[:12]}{Color.RESET}")

        # 2. Get current parent commit from HEAD
        parent_sha = None
        target_ref = "refs/heads/main"
        if self.head.startswith("ref: "):
            target_ref = self.head.split("ref: ")[1]
            parent_sha = self.refs.get(target_ref)

        # 3. Plumbing: commit-tree
        commit_sha = self.commit_tree(tree_sha, parent_sha, message)
        parent_display = parent_sha[:12] if parent_sha else "(root-commit)"
        print(f"  {Color.DIM}↳ (Plumbing 2) git commit-tree -p {parent_display} => commit {commit_sha[:12]}{Color.RESET}")

        # 4. Plumbing: update-ref
        self.update_ref(target_ref, commit_sha)
        print(f"  {Color.DIM}↳ (Plumbing 3) git update-ref {target_ref} => {commit_sha[:12]}{Color.RESET}")

        return commit_sha


def print_banner():
    banner = f"""
{Color.BOLD}{Color.BLUE}======================================================================
  SIMULASI ARSITEKTUR GIT: PLUMBING VS PORCELAIN & CONTENT-ADDRESSABLE
  Bab 01 - Dasar Internal Git & Git Object Database (Blob, Tree, Commit)
======================================================================{Color.RESET}
"""
    print(banner)


def inspect_object(repo: MockGitRepository, sha: str, title: str):
    obj_type, payload = repo.cat_file(sha, mode="-p")
    comp_size = len(repo.objects[sha])
    print(f"\n{Color.YELLOW}[INSPEKSI: {title}]{Color.RESET}")
    print(f"  {Color.BOLD}SHA-1 Hash  :{Color.RESET} {sha}")
    print(f"  {Color.BOLD}Tipe Objek  :{Color.RESET} {obj_type}")
    print(f"  {Color.BOLD}Ukuran Zlib :{Color.RESET} {comp_size} bytes terkompresi")
    print(f"  {Color.BOLD}Payload Isi :{Color.RESET}")
    for line in payload.strip().split("\n"):
        print(f"    {Color.CYAN}|{Color.RESET} {line}")


def run_interactive_lab():
    print_banner()
    repo = MockGitRepository()

    print(f"{Color.BOLD}{Color.MAGENTA}LANGKAH 1: Plumbing Manual (git hash-object){Color.RESET}")
    sample_text = "print('Hello Git Internals!')\n"
    print(f"Membuat blob mentah dari string: {repr(sample_text)}")
    manual_blob_sha = repo.hash_object("blob", sample_text.encode("utf-8"), write=True)
    print(f"Hasil hash: {Color.GREEN}{manual_blob_sha}{Color.RESET}")
    inspect_object(repo, manual_blob_sha, "Plumbing Blob Object")

    print(f"\n{Color.BOLD}{Color.MAGENTA}LANGKAH 2: Porcelain Workflow (git add & git commit - Commit #1){Color.RESET}")
    repo.porcelain_add("app.py", sample_text)
    repo.porcelain_add("README.md", "# Panduan Proyek\nBelajar plumbing vs porcelain.")
    commit1_sha = repo.porcelain_commit("feat: inisialisasi aplikasi dasar")
    
    inspect_object(repo, commit1_sha, "Commit Objek #1")

    # Ambil tree sha dari commit 1
    _, commit_body = repo.cat_file(commit1_sha, "-p")
    tree1_sha = commit_body.split("\n")[0].split(" ")[1]
    inspect_object(repo, tree1_sha, "Tree Objek Milik Commit #1")

    print(f"\n{Color.BOLD}{Color.MAGENTA}LANGKAH 3: Modifikasi File (Commit #2 Berantai){Color.RESET}")
    updated_text = "print('Hello Git Internals!')\nprint('Menambahkan fitur logging.')\n"
    repo.porcelain_add("app.py", updated_text)
    commit2_sha = repo.porcelain_commit("feat(app): tambahkan baris logging")

    inspect_object(repo, commit2_sha, "Commit Objek #2 (Perhatikan Parent Hash)")

    print(f"\n{Color.BOLD}{Color.MAGENTA}LANGKAH 4: Status References & HEAD Pointer{Color.RESET}")
    print(f"  {Color.BOLD}HEAD File Points To :{Color.RESET} {repo.head}")
    ref_main = repo.refs["refs/heads/main"]
    print(f"  {Color.BOLD}refs/heads/main      :{Color.RESET} {ref_main} (Sama dengan Commit #2: {ref_main == commit2_sha})")

    print(f"\n{Color.BOLD}{Color.GREEN}✔ Selesai! Semua simulasi plumbing & porcelain berhasil diverifikasi.{Color.RESET}\n")


if __name__ == "__main__":
    run_interactive_lab()
