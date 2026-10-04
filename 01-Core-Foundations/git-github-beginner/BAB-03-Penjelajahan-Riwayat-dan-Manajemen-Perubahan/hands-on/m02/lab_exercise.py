#!/usr/bin/env python3
"""
Lab Hands-on: Penjelajahan Riwayat & Manajemen Perubahan (Commits & Diffs)
Kategori: 01-Core-Foundations | Topik: git-github-beginner (Bab 03, Modul 02)

Script ini mengimplementasikan replika miniatur Git Object Database & Diff Engine.
Mendemonstrasikan secara mekanistis bagaimana:
1. Objek Git (Blob, Tree, Commit) di-hash via SHA-1 dengan formatting internal Git.
2. Riwayat commit membentuk Directed Acyclic Graph (DAG) berbasis pointer hash parent.
3. Algoritma diff menginspeksi delta perubahan baris per baris antar commit snapshot.
4. Git traversing engine merender graph visual log dan metadata patch commit.
"""

import hashlib
import time
import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ==============================================================================
# Terminal UI: ANSI Color Palettes
# ==============================================================================
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


# ==============================================================================
# Model Git Object: Blob, Tree, dan Commit
# ==============================================================================
@dataclass
class Blob:
    """Menyimpan konten mentah dari sebuah file (Git Blob Object)."""
    content: str

    def serialize(self) -> bytes:
        payload = self.content.encode("utf-8")
        header = f"blob {len(payload)}\0".encode("utf-8")
        return header + payload

    @property
    def hash(self) -> str:
        return hashlib.sha1(self.serialize()).hexdigest()


@dataclass
class Tree:
    """Menyimpan manifest direktori (nama file -> blob/tree SHA-1)."""
    entries: Dict[str, str] = field(default_factory=dict)  # filename -> blob_hash

    def serialize(self) -> bytes:
        # Format payload: <mode> <filename>\0<binary_sha1>
        body = b""
        for name in sorted(self.entries.keys()):
            sha_hex = self.entries[name]
            sha_bin = bytes.fromhex(sha_hex)
            body += f"100644 {name}\0".encode("utf-8") + sha_bin
        header = f"tree {len(body)}\0".encode("utf-8")
        return header + body

    @property
    def hash(self) -> str:
        return hashlib.sha1(self.serialize()).hexdigest()


@dataclass
class Commit:
    """Menyimpan snapshot root tree, pointer parents, author, dan message."""
    tree_hash: str
    parents: List[str]
    author: str
    timestamp: float
    message: str

    def serialize(self) -> bytes:
        lines = [f"tree {self.tree_hash}"]
        for p in self.parents:
            lines.append(f"parent {p}")
        lines.append(f"author {self.author} {int(self.timestamp)} +0000")
        lines.append(f"committer {self.author} {int(self.timestamp)} +0000")
        lines.append("")
        lines.append(self.message.strip())
        lines.append("")
        payload = "\n".join(lines).encode("utf-8")
        header = f"commit {len(payload)}\0".encode("utf-8")
        return header + payload

    @property
    def hash(self) -> str:
        return hashlib.sha1(self.serialize()).hexdigest()


# ==============================================================================
# Git Internal Engine Simulation
# ==============================================================================
class MiniGitVCS:
    """Engine pengelola Object Database, Working Tree, Index, dan Diff calculation."""
    def __init__(self):
        self.object_db: Dict[str, bytes] = {}
        self.refs: Dict[str, str] = {}  # refs/heads/main -> commit_hash
        self.head: Optional[str] = "refs/heads/main"
        self.index: Dict[str, str] = {}  # Staging Area: path -> content

    def stage_file(self, path: str, content: str) -> None:
        """Memasukkan perubahan file ke staging area."""
        self.index[path] = content

    def commit(self, message: str, author: str = "Lead Dev <lead@sys.internal>") -> str:
        """
        Membuat commit dari staging area:
        1. Buat Blob untuk tiap file dan simpan ke Object DB.
        2. Buat Tree yang merujuk pada hash Blob.
        3. Buat Commit yang merujuk pada Tree dan parent HEAD saat ini.
        4. Geser pointer HEAD ke commit baru.
        """
        tree_entries: Dict[str, str] = {}
        for path, content in self.index.items():
            blob = Blob(content)
            sha = blob.hash
            self.object_db[sha] = blob.serialize()
            tree_entries[path] = sha

        tree = Tree(entries=tree_entries)
        tree_sha = tree.hash
        self.object_db[tree_sha] = tree.serialize()

        parent_hash = self.refs.get(self.head)
        parents = [parent_hash] if parent_hash else []

        commit_obj = Commit(
            tree_hash=tree_sha,
            parents=parents,
            author=author,
            timestamp=time.time(),
            message=message
        )
        commit_sha = commit_obj.hash
        self.object_db[commit_sha] = commit_obj.serialize()

        # Update ref
        self.refs[self.head] = commit_sha
        return commit_sha

    def _deserialize_commit(self, sha: str) -> Commit:
        raw = self.object_db[sha]
        header_end = raw.find(b"\0")
        payload = raw[header_end + 1:].decode("utf-8")
        
        parts = payload.split("\n\n", 1)
        meta_lines = parts[0].split("\n")
        message = parts[1].strip() if len(parts) > 1 else ""

        tree_sha = ""
        parents = []
        author = ""
        ts = 0.0

        for line in meta_lines:
            if line.startswith("tree "):
                tree_sha = line.split(" ", 1)[1]
            elif line.startswith("parent "):
                parents.append(line.split(" ", 1)[1])
            elif line.startswith("author "):
                author_data = line[7:]
                author = author_data.rsplit(" ", 2)[0]
                ts = float(author_data.rsplit(" ", 2)[1])

        return Commit(tree_sha, parents, author, ts, message)

    def _deserialize_tree(self, sha: str) -> Tree:
        raw = self.object_db[sha]
        header_end = raw.find(b"\0")
        payload = raw[header_end + 1:]
        
        entries = {}
        idx = 0
        while idx < len(payload):
            space_pos = payload.find(b" ", idx)
            null_pos = payload.find(b"\0", space_pos)
            filename = payload[space_pos + 1:null_pos].decode("utf-8")
            sha_bin = payload[null_pos + 1:null_pos + 21]
            sha_hex = sha_bin.hex()
            entries[filename] = sha_hex
            idx = null_pos + 21
        return Tree(entries)

    def _get_blob_content(self, sha: str) -> str:
        raw = self.object_db[sha]
        header_end = raw.find(b"\0")
        return raw[header_end + 1:].decode("utf-8")

    def diff_trees(self, tree_sha_a: Optional[str], tree_sha_b: str) -> List[str]:
        """
        Menghasilkan delta diff baris per baris (Unified Diff standard) 
        antara dua snapshot tree.
        """
        entries_a = self._deserialize_tree(tree_sha_a).entries if tree_sha_a else {}
        entries_b = self._deserialize_tree(tree_sha_b).entries if tree_sha_b else {}
        
        all_files = sorted(set(entries_a.keys()) | set(entries_b.keys()))
        diff_output = []

        for filename in all_files:
            sha_a = entries_a.get(filename)
            sha_b = entries_b.get(filename)

            if sha_a == sha_b:
                continue

            content_a = self._get_blob_content(sha_a).splitlines(keepends=True) if sha_a else []
            content_b = self._get_blob_content(sha_b).splitlines(keepends=True) if sha_b else []

            label_a = f"a/{filename}" if sha_a else "/dev/null"
            label_b = f"b/{filename}" if sha_b else "/dev/null"

            delta = difflib.unified_diff(
                content_a,
                content_b,
                fromfile=label_a,
                tofile=label_b,
                n=3
            )
            diff_output.extend(list(delta))

        return diff_output

    def render_log(self) -> None:
        """Menampilkan riwayat commit graph (mirip `git log --graph --oneline`)."""
        print(f"\n{ANSI.BOLD}{ANSI.YELLOW}=== GIT LOG HISTORY (DAG GRAPH TRAVERSAL) ==={ANSI.RESET}")
        curr = self.refs.get(self.head)
        
        while curr:
            commit_obj = self._deserialize_commit(curr)
            short_sha = curr[:7]
            timestr = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(commit_obj.timestamp))
            
            # Format visual log
            print(f"{ANSI.MAGENTA}*{ANSI.RESET} {ANSI.CYAN}{short_sha}{ANSI.RESET} "
                  f"- {ANSI.BOLD}{commit_obj.message}{ANSI.RESET} "
                  f"{ANSI.GRAY}({commit_obj.author} | {timestr}){ANSI.RESET}")

            if commit_obj.parents:
                print(f"{ANSI.MAGENTA}|{ANSI.RESET}")
                curr = commit_obj.parents[0]
            else:
                curr = None
        print(f"{ANSI.GRAY}* (Initial Commit End){ANSI.RESET}\n")

    def show_commit(self, commit_sha: str) -> None:
        """Menampilkan detail commit beserta unified diff (mirip `git show <hash>`)."""
        commit_obj = self._deserialize_commit(commit_sha)
        parent_sha = commit_obj.parents[0] if commit_obj.parents else None
        parent_tree = self._deserialize_commit(parent_sha).tree_hash if parent_sha else None

        print(f"{ANSI.BOLD}{ANSI.BLUE}commit {commit_sha}{ANSI.RESET}")
        if parent_sha:
            print(f"Parent:  {parent_sha}")
        print(f"Author:  {commit_obj.author}")
        print(f"Tree:    {commit_obj.tree_hash}")
        print(f"\n    {commit_obj.message}\n")

        diff = self.diff_trees(parent_tree, commit_obj.tree_hash)
        for line in diff:
            if line.startswith("+++") or line.startswith("---"):
                print(f"{ANSI.BOLD}{line.rstrip()}{ANSI.RESET}")
            elif line.startswith("+"):
                print(f"{ANSI.GREEN}{line.rstrip()}{ANSI.RESET}")
            elif line.startswith("-"):
                print(f"{ANSI.RED}{line.rstrip()}{ANSI.RESET}")
            elif line.startswith("@@"):
                print(f"{ANSI.CYAN}{line.rstrip()}{ANSI.RESET}")
            else:
                print(line.rstrip())
        print()


# ==============================================================================
# Lab Scenario Execution
# ==============================================================================
def main():
    repo = MiniGitVCS()
    print(f"{ANSI.BOLD}{ANSI.GREEN}>>> Memulai Lab Deep Dive: Commits & Diffs Engine <<<{ANSI.RESET}")

    # Step 1: Snapshot Pertama (Initial Commit)
    print(f"\n{ANSI.BOLD}[1] Staging & Commit 1: Fondasi Modul Kernel{ANSI.RESET}")
    repo.stage_file("main.py", (
        "# Kernel Core Module\n"
        "def initialize_system():\n"
        "    print('Starting secure subsystem...')\n"
        "    return True\n"
    ))
    repo.stage_file("README.md", "# Security Kernel\nVersi dasar sistem.\n")
    c1 = repo.commit("feat: initial kernel implementation and readme")
    print(f"Commit Terbentuk: {ANSI.CYAN}{c1}{ANSI.RESET}")

    time.sleep(1.0)

    # Step 2: Snapshot Kedua (Modifikasi file & Penambahan Fitur)
    print(f"\n{ANSI.BOLD}[2] Staging & Commit 2: Update Logika Main & Tambah Config{ANSI.RESET}")
    repo.stage_file("main.py", (
        "# Kernel Core Module\n"
        "import sys\n\n"
        "def initialize_system():\n"
        "    print('Starting secure subsystem v2.0...')\n"
        "    # Added telemetry check\n"
        "    return verify_integrity()\n\n"
        "def verify_integrity():\n"
        "    return True\n"
    ))
    repo.stage_file("config.json", '{\n  "mode": "production",\n  "telemetry": true\n}\n')
    c2 = repo.commit("refactor: enhance startup handshake and add telemetry config")
    print(f"Commit Terbentuk: {ANSI.CYAN}{c2}{ANSI.RESET}")

    time.sleep(1.0)

    # Step 3: Snapshot Ketiga (Bug Fix)
    print(f"\n{ANSI.BOLD}[3] Staging & Commit 3: Fix Telemetry Boolean{ANSI.RESET}")
    repo.stage_file("config.json", '{\n  "mode": "production",\n  "telemetry": false\n}\n')
    c3 = repo.commit("fix: disable telemetry default in production config")
    print(f"Commit Terbentuk: {ANSI.CYAN}{c3}{ANSI.RESET}")

    # Visualisasi Riwayat Commit (Graph Log)
    repo.render_log()

    # Eksekusi Git Show pada Commit 2 (Melihat Delta Diff)
    print(f"{ANSI.BOLD}{ANSI.YELLOW}=== DEMO 1: INSPEKSI COMMIT (git show {c2[:7]}) ==={ANSI.RESET}")
    repo.show_commit(c2)

    # Eksekusi Arbitrary Diff antar dua titik riwayat (c1..c3)
    print(f"{ANSI.BOLD}{ANSI.YELLOW}=== DEMO 2: ARBITRARY DIFF RANGE (git diff {c1[:7]}..{c3[:7]}) ==={ANSI.RESET}")
    commit_1_tree = repo._deserialize_commit(c1).tree_hash
    commit_3_tree = repo._deserialize_commit(c3).tree_hash
    range_diff = repo.diff_trees(commit_1_tree, commit_3_tree)
    
    for line in range_diff:
        if line.startswith("+++") or line.startswith("---"):
            print(f"{ANSI.BOLD}{line.rstrip()}{ANSI.RESET}")
        elif line.startswith("+"):
            print(f"{ANSI.GREEN}{line.rstrip()}{ANSI.RESET}")
        elif line.startswith("-"):
            print(f"{ANSI.RED}{line.rstrip()}{ANSI.RESET}")
        elif line.startswith("@@"):
            print(f"{ANSI.CYAN}{line.rstrip()}{ANSI.RESET}")
        else:
            print(line.rstrip())

    print(f"\n{ANSI.BOLD}{ANSI.GREEN}>>> Lab Selesai: Seluruh struktur commit DAG dan diff engine terverifikasi. <<<{ANSI.RESET}")


if __name__ == "__main__":
    main()