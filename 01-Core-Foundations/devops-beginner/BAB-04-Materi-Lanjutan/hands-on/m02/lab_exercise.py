#!/usr/bin/env python3
"""
Lab Hands-on: Git Enterprise Internals & Governance Engine
Kategori: 01-Core-Foundations | Topik: devops-beginner
Bab 04: Version Control System Terapan: Git Enterprise - Modul 02 Deep Dive

Simulasi komprehensif Content-Addressable Storage (Object Database SHA-1:
Blob, Tree, Commit), DAG traversal (LCA / Lowest Common Ancestor),
Three-Way Merge Engine, dan Enterprise Pre-Receive Hook Engine (Branch Protection).
"""

import hashlib
import time
import sys
from typing import Dict, List, Optional, Set, Tuple

# ANSI Terminal Formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"

def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [LAB STEP] {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")

def print_success(msg: str):
    print(f"{CLR_GREEN}✔ [SUCCESS]{CLR_RESET} {msg}")

def print_error(msg: str):
    print(f"{CLR_RED}✖ [POLICY VIOLATION]{CLR_RESET} {msg}")

def print_info(msg: str):
    print(f"{CLR_BLUE}ℹ [INFO]{CLR_RESET} {msg}")

# --- Bagian 1: Git Object Model (Content-Addressable Storage) ---

class GitObject:
    """Basis representasi immutable object dalam Git."""
    def serialize(self) -> bytes:
        raise NotImplementedError

    @property
    def oid(self) -> str:
        """Menghitung SHA-1 Hash sesuai spesifikasi Git: <type> <size>\\0<data>."""
        raw_data = self.serialize()
        header = f"{self.type_name} {len(raw_data)}\0".encode('utf-8')
        return hashlib.sha1(header + raw_data).hexdigest()

class Blob(GitObject):
    type_name = "blob"
    def __init__(self, content: str):
        self.content = content.encode('utf-8')

    def serialize(self) -> bytes:
        return self.content

class Tree(GitObject):
    type_name = "tree"
    def __init__(self, entries: Dict[str, str]):
        # entries: {filename: blob_oid}
        self.entries = entries

    def serialize(self) -> bytes:
        # Format serialisasi sederhana: mode filename\0hash
        payload = bytearray()
        for filename in sorted(self.entries.keys()):
            oid_bytes = bytes.fromhex(self.entries[filename])
            payload.extend(f"100644 {filename}\0".encode('utf-8') + oid_bytes)
        return bytes(payload)

class Commit(GitObject):
    type_name = "commit"
    def __init__(self, tree_oid: str, parents: List[str], author: str, message: str, timestamp: Optional[float] = None):
        self.tree_oid = tree_oid
        self.parents = parents
        self.author = author
        self.message = message
        self.timestamp = timestamp or time.time()

    def serialize(self) -> bytes:
        lines = [f"tree {self.tree_oid}"]
        for p in self.parents:
            lines.append(f"parent {p}")
        lines.append(f"author {self.author} {int(self.timestamp)} +0700")
        lines.append("")
        lines.append(self.message)
        return "\n".join(lines).encode('utf-8')

# --- Bagian 2: Enterprise Policy Hook Engine ---

class EnterpriseHookEngine:
    """Simulasi Enterprise Server Pre-Receive Hook & Branch Protection."""
    PROTECTED_BRANCHES = {"main", "production"}
    MIN_COMMIT_MSG_LEN = 12

    @classmethod
    def validate_push(cls, target_branch: str, commit: Commit, is_direct_push: bool) -> Tuple[bool, str]:
        # Aturan 1: Branch Protection - Mencegah direct push ke branch utama
        if target_branch in cls.PROTECTED_BRANCHES and is_direct_push:
            return False, f"Direct push ke protected branch '{target_branch}' dilarang! Wajib via Pull Request."

        # Aturan 2: Conventional Commits / Format Pesan
        valid_prefixes = ("feat:", "fix:", "chore:", "refactor:", "docs:", "merge:")
        if not any(commit.message.startswith(prefix) for prefix in valid_prefixes):
            return False, f"Pesan commit harus mematuhi standard prefix: {valid_prefixes}"

        if len(commit.message.split('\n')[0]) < cls.MIN_COMMIT_MSG_LEN:
            return False, f"Pesan commit terlalu pendek (min {cls.MIN_COMMIT_MSG_LEN} karakter)."

        # Aturan 3: Validasi Author Identity
        if "@company.internal" not in commit.author:
            return False, f"Author '{commit.author}' tidak memiliki domain email resmi '@company.internal'."

        return True, "Validasi pre-receive lolos."

# --- Bagian 3: Git Repository & Merge Engine (DAG Operations) ---

class EnterpriseRepository:
    def __init__(self):
        self.object_db: Dict[str, GitObject] = {}
        self.refs: Dict[str, str] = {}  # branch_name -> commit_oid
        self.index: Dict[str, str] = {} # Staging area: filename -> blob_oid
        self.head: str = "main"

    def put_object(self, obj: GitObject) -> str:
        oid = obj.oid
        self.object_db[oid] = obj
        return oid

    def stage_file(self, filename: str, content: str):
        blob = Blob(content)
        oid = self.put_object(blob)
        self.index[filename] = oid

    def create_commit(self, message: str, author: str, direct_push: bool = False) -> Optional[str]:
        # Snapshot staging area menjadi Tree
        tree = Tree(dict(self.index))
        tree_oid = self.put_object(tree)

        parents = []
        if self.head in self.refs:
            parents.append(self.refs[self.head])

        commit = Commit(tree_oid, parents, author, message)
        
        # Eksekusi Enterprise Policy Hook
        allowed, reason = EnterpriseHookEngine.validate_push(self.head, commit, direct_push)
        if not allowed:
            print_error(f"Commit ditolak oleh server hook: {reason}")
            return None

        commit_oid = self.put_object(commit)
        self.refs[self.head] = commit_oid
        print_success(f"Commit tersimpan [{commit_oid[:7]}] pada branch '{self.head}': {message}")
        return commit_oid

    def create_branch(self, branch_name: str):
        if self.head not in self.refs:
            raise ValueError("Tidak dapat membuat branch dari HEAD yang tidak valid.")
        self.refs[branch_name] = self.refs[self.head]
        print_info(f"Branch '{branch_name}' dibuat mengarah ke [{self.refs[branch_name][:7]}].")

    def checkout(self, branch_name: str):
        if branch_name not in self.refs:
            raise ValueError(f"Branch '{branch_name}' tidak ditemukan.")
        self.head = branch_name
        # Update staging index dari commit target
        commit = self.object_db[self.refs[branch_name]]
        tree = self.object_db[commit.tree_oid]
        self.index = dict(tree.entries)
        print_info(f"Berpindah ke branch '{branch_name}' ({self.refs[branch_name][:7]})")

    def _find_lca(self, sha_a: str, sha_b: str) -> Optional[str]:
        """Mencari Lowest Common Ancestor (LCA) di DAG menggunakan BFS."""
        ancestors_a: Set[str] = set()
        queue = [sha_a]
        while queue:
            curr = queue.pop(0)
            ancestors_a.add(curr)
            curr_obj = self.object_db[curr]
            queue.extend(curr_obj.parents)

        queue = [sha_b]
        while queue:
            curr = queue.pop(0)
            if curr in ancestors_a:
                return curr
            curr_obj = self.object_db[curr]
            queue.extend(curr_obj.parents)
        return None

    def merge_branches(self, source_branch: str, author: str) -> bool:
        """Simulasi 3-Way Merge Engine dengan deteksi konflik."""
        target_branch = self.head
        head_sha = self.refs.get(target_branch)
        source_sha = self.refs.get(source_branch)

        print_info(f"Memulai integrasi merge: '{source_branch}' -> '{target_branch}'")
        
        # Fast-forward check
        lca_sha = self._find_lca(head_sha, source_sha)
        if lca_sha == head_sha:
            print_info("Fast-forward merge dimungkinkan, memperbarui pointer...")
            self.refs[target_branch] = source_sha
            print_success(f"Fast-forward selesai. '{target_branch}' sekarang di [{source_sha[:7]}].")
            return True

        # Three-way merge resolution
        base_commit: Commit = self.object_db[lca_sha]
        head_commit: Commit = self.object_db[head_sha]
        src_commit: Commit = self.object_db[source_sha]

        base_tree: Tree = self.object_db[base_commit.tree_oid]
        head_tree: Tree = self.object_db[head_commit.tree_oid]
        src_tree: Tree = self.object_db[src_commit.tree_oid]

        all_files = set(base_tree.entries) | set(head_tree.entries) | set(src_tree.entries)
        merged_entries = {}
        conflicts = []

        for f in all_files:
            b_oid = base_tree.entries.get(f)
            h_oid = head_tree.entries.get(f)
            s_oid = src_tree.entries.get(f)

            if h_oid == s_oid:
                # Keduanya identik
                if h_oid: merged_entries[f] = h_oid
            elif h_oid == b_oid:
                # Head tidak mengubah, ambil perubahan source
                if s_oid: merged_entries[f] = s_oid
            elif s_oid == b_oid:
                # Source tidak mengubah, ambil perubahan head
                if h_oid: merged_entries[f] = h_oid
            else:
                # Keduanya mengubah file secara independen dari base
                conflicts.append(f)

        if conflicts:
            print_error(f"Merge CONFLICT terdeteksi pada file: {conflicts}!")
            print_error("Merge dibatalkan secara otomatis (Safe State Restored).")
            return False

        # Tidak ada konflik, buat merge commit
        merge_tree = Tree(merged_entries)
        mtree_oid = self.put_object(merge_tree)
        merge_commit = Commit(
            tree_oid=mtree_oid,
            parents=[head_sha, source_sha],
            author=author,
            message=f"merge: integrasi branch '{source_branch}' ke '{target_branch}'"
        )
        merge_sha = self.put_object(merge_commit)
        self.refs[target_branch] = merge_sha
        self.index = dict(merged_entries)
        print_success(f"Merge commit berhasil diciptakan: [{merge_sha[:7]}] (Parents: {head_sha[:7]}, {source_sha[:7]})")
        return True

    def visualize_dag(self):
        """Merender struktur DAG Object Database secara visual di CLI."""
        print(f"\n{CLR_BOLD}{CLR_MAGENTA}--- REPRESENTASI DAG OBJECT REPOSITORY ---{CLR_RESET}")
        for ref_name, sha in self.refs.items():
            print(f"Ref: {CLR_YELLOW}{ref_name}{CLR_RESET} -> [{CLR_GREEN}{sha[:7]}{CLR_RESET}]")
        
        print("\nSilsilah Graph Node:")
        visited = set()
        queue = list(self.refs.values())
        while queue:
            curr_sha = queue.pop(0)
            if curr_sha in visited:
                continue
            visited.add(curr_sha)
            c: Commit = self.object_db[curr_sha]
            parents_str = ", ".join([p[:7] for p in c.parents]) or "ROOT"
            print(f"  * Commit [{CLR_GREEN}{curr_sha[:7]}{CLR_RESET}] Parents: [{CLR_BLUE}{parents_str}{CLR_RESET}] | {c.message.splitlines()[0]}")
            queue.extend(c.parents)

# --- Bagian 4: Skenario Eksekusi Lab ---

def run_simulation():
    repo = EnterpriseRepository()

    print_header("1. Inisialisasi Repository & Pengujian Direct Push Protection")
    repo.stage_file("app.py", "print('Initial v1.0.0')\n")
    repo.stage_file("security.json", '{"encryption": "AES-256"}\n')
    
    # Pelanggaran 1: Direct push ke protected branch 'main'
    print_info("Mencoba melakukan direct push ke protected branch 'main'...")
    fail_commit = repo.create_commit("feat: initial platform code", "alice@company.internal", direct_push=True)

    # Pelanggaran 2: Email domain tidak resmi
    print_info("Mencoba commit dengan email personal non-korporat...")
    fail_commit2 = repo.create_commit("feat: initial platform code", "hacker@gmail.com", direct_push=False)

    # Sukses inisialisasi root (simulasi bypass setup repo)
    print_info("Menyetel baseline repository via approved initialization pipeline...")
    root_blob = repo.put_object(Blob("print('Initial v1.0.0')\n"))
    root_tree = repo.put_object(Tree({"app.py": root_blob}))
    root_commit = repo.put_object(Commit(root_tree, [], "infra@company.internal", "chore: setup repo baseline"))
    repo.refs["main"] = root_commit
    repo.index["app.py"] = root_blob
    print_success(f"Baseline 'main' di-anchor pada: [{root_commit[:7]}]")

    print_header("2. Alur Fitur: Branching & Isolated Development")
    repo.create_branch("feature/user-auth")
    repo.checkout("feature/user-auth")
    
    # Feature dev update
    repo.stage_file("auth.py", "def login(): return True\n")
    repo.stage_file("app.py", "print('Initial v1.0.0')\nimport auth\n")
    repo.create_commit("feat: implement authentication logic", "bob@company.internal")

    print_header("3. Parallel Development pada Main Branch")
    repo.checkout("main")
    # Perubahan non-konflik pada file berbeda
    repo.stage_file("metrics.py", "METRICS_ENABLED = True\n")
    repo.create_commit("feat: tambahkan monitoring metrics", "charlie@company.internal")

    print_header("4. Three-Way Merge Engine (No-Conflict Scenario)")
    repo.merge_branches("feature/user-auth", author="infra@company.internal")

    print_header("5. Simulasi Deteksi Konflik Merge Konkuren")
    repo.create_branch("hotfix/quick-patch")
    repo.checkout("hotfix/quick-patch")
    repo.stage_file("app.py", "print('CRITICAL HOTFIX ACTIVE')\n")
    repo.create_commit("fix: emergency hotfix routing", "dave@company.internal")

    repo.checkout("main")
    repo.stage_file("app.py", "print('PRODUCTION REFACTOR V2')\n")
    repo.create_commit("refactor: app initialization refactor", "bob@company.internal")

    print_info("Mencoba merge branch hotfix yang mengubah file secara bentrok...")
    repo.merge_branches("hotfix/quick-patch", author="infra@company.internal")

    print_header("6. Validasi Topology & Directed Acyclic Graph (DAG)")
    repo.visualize_dag()

if __name__ == "__main__":
    run_simulation()
    print(f"\n{CLR_BOLD}{CLR_GREEN}Lab selesai dengan sukses: Seluruh mekanisme internal tervalidasi.{CLR_RESET}\n")