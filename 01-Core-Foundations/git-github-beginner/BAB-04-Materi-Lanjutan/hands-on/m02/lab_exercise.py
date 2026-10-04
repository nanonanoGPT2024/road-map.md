#!/usr/bin/env python3
"""
Lab Hands-on: Percabangan Terisolasi (Branching Strategies & Mechanics)
Kategori: 01-Core-Foundations | Topik: git-github-beginner | Bab: 04

Simulasi mendalam engine pointer Git, Object Database (DAG), isolasi working tree,
serta algoritma rekonsiliasi percabangan (Fast-Forward & 3-Way Merge via LCA).
"""

import hashlib
import json
import sys
import time
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

# --- ANSI Formatting Constants ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_GRAY = "\033[90m"


class GitCommit:
    """
    Representasi immutable Commit Object dalam Git DAG.
    Setiap commit memiliki hash SHA-1 unik berdasarkan tree snapshot, parent, dan metadata.
    """

    def __init__(
        self,
        tree: Dict[str, str],
        parents: List[str],
        message: str,
        author: str = "Lead Developer <lead@internal.net>",
    ):
        self.tree: Dict[str, str] = tree.copy()  # Snapshot file (path -> content_hash)
        self.parents: List[str] = parents  # List SHA parent (bisa 0, 1, atau 2 untuk merge)
        self.message: str = message
        self.author: str = author
        self.timestamp: float = time.time()
        self.commit_hash: str = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """Menghitung SHA-1 hash deterministic dari payload commit."""
        payload = {
            "tree": sorted(self.tree.items()),
            "parents": self.parents,
            "message": self.message,
            "author": self.author,
            "timestamp": self.timestamp,
        }
        raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        header = f"commit {len(raw_bytes)}\0".encode("utf-8")
        return hashlib.sha1(header + raw_bytes).hexdigest()

    def short_hash(self) -> str:
        return self.commit_hash[:7]


class GitRepositoryEngine:
    """
    Simulasi subsistem internal Git yang mengelola:
    - Object Store (Content-addressable storage untuk commit & blob)
    - Reference Pointers (.git/refs/heads/*)
    - HEAD pointer (simbolik atau detached)
    - Index/Staging Area & Working Directory isolation
    """

    def __init__(self):
        self.objects: Dict[str, GitCommit] = {}  # Object DB: hash -> GitCommit
        self.blob_store: Dict[str, str] = {}    # Blob DB: content_hash -> content
        self.branches: Dict[str, str] = {}      # References: branch_name -> commit_hash
        self.head: str = "main"                 # HEAD pointer: menunjuk ke nama branch aktif
        self.is_detached: bool = False          # Status apakah HEAD dalam detached mode
        self.index: Dict[str, str] = {}         # Staging area: path -> content_hash
        self.working_tree: Dict[str, str] = {}  # File fisik di working directory

        # Inisialisasi branch default
        self.branches["main"] = ""

    def _hash_object(self, content: str) -> str:
        """Menyimpan data file ke blob store dan mengembalikan hash SHA-1."""
        raw_bytes = content.encode("utf-8")
        content_hash = hashlib.sha1(f"blob {len(raw_bytes)}\0{content}".encode("utf-8")).hexdigest()
        self.blob_store[content_hash] = content
        return content_hash

    def write_file(self, path: str, content: str) -> None:
        """Membuat atau memperbarui file pada working directory."""
        self.working_tree[path] = content

    def stage_file(self, path: str) -> None:
        """Menjalankan ekuivalen 'git add <path>'."""
        if path not in self.working_tree:
            raise FileNotFoundError(f"File {path} tidak ditemukan di working tree.")
        content = self.working_tree[path]
        blob_hash = self._hash_object(content)
        self.index[path] = blob_hash

    def commit(self, message: str) -> str:
        """
        Menjalankan 'git commit -m <message>'.
        Membentuk snapshot dari Index, mengaitkannya ke parent HEAD saat ini,
        dan memajukan pointer branch aktif (O(1) operation).
        """
        if not self.index:
            raise ValueError("Nothing to commit (staging index is empty).")

        parent_hashes = []
        current_commit_hash = self._resolve_head()
        if current_commit_hash:
            parent_hashes.append(current_commit_hash)

        new_commit = GitCommit(tree=self.index, parents=parent_hashes, message=message)
        self.objects[new_commit.commit_hash] = new_commit

        # Update pointer
        if self.is_detached:
            self.head = new_commit.commit_hash
        else:
            self.branches[self.head] = new_commit.commit_hash

        return new_commit.commit_hash

    def _resolve_head(self) -> str:
        """Menyelesaikan pointer HEAD ke SHA-1 commit spesifik."""
        if self.is_detached:
            return self.head
        return self.branches.get(self.head, "")

    def create_branch(self, branch_name: str) -> None:
        """
        Menjalankan 'git branch <name>'.
        Hanya membuat pointer referensi baru ke commit yang sedang ditunjuk HEAD.
        Biaya komputasi O(1).
        """
        current_hash = self._resolve_head()
        if not current_hash:
            raise ValueError("Tidak dapat membuat branch dari kondisi repository kosong.")
        if branch_name in self.branches:
            raise ValueError(f"Branch '{branch_name}' sudah ada.")

        self.branches[branch_name] = current_hash
        print(f"{CLR_GREEN}[REF CREATED]{CLR_RESET} Pointer refs/heads/{branch_name} -> {current_hash[:7]}")

    def switch_branch(self, branch_name: str) -> None:
        """
        Menjalankan 'git switch <name>'.
        Mengalihkan HEAD, lalu memulihkan Staging Area dan Working Directory
        sesuai commit snapshot dari branch target (mengisolasi workspace).
        """
        if branch_name not in self.branches:
            raise ValueError(f"Branch '{branch_name}' tidak ditemukan.")

        target_commit_hash = self.branches[branch_name]
        self.head = branch_name
        self.is_detached = False

        # Pulihkan lingkungan dari target snapshot
        self._checkout_tree(target_commit_hash)
        print(f"{CLR_CYAN}[SWITCH]{CLR_RESET} Switched to branch '{branch_name}' @ {target_commit_hash[:7]}")

    def _checkout_tree(self, commit_hash: str) -> None:
        """Sinkronisasi Index & Working Tree dengan snapshot commit target."""
        commit_obj = self.objects[commit_hash]
        self.index = commit_obj.tree.copy()
        self.working_tree.clear()
        for path, blob_hash in self.index.items():
            self.working_tree[path] = self.blob_store[blob_hash]

    def find_lowest_common_ancestor(self, hash_a: str, hash_b: str) -> Optional[str]:
        """
        Menemukan Lowest Common Ancestor (LCA) menggunakan BFS traversal.
        Krusial untuk mendeteksi apakah merge bisa Fast-Forward atau membutuhkan 3-Way Merge.
        """
        if hash_a == hash_b:
            return hash_a

        # Kumpulkan semua ancestor dari hash_a
        ancestors_a: Set[str] = set()
        queue: deque = deque([hash_a])
        while queue:
            curr = queue.popleft()
            if curr in ancestors_a or not curr:
                continue
            ancestors_a.add(curr)
            if curr in self.objects:
                for parent in self.objects[curr].parents:
                    queue.append(parent)

        # BFS dari hash_b untuk menemukan node pertama yang beririsan dengan ancestor hash_a
        queue = deque([hash_b])
        visited_b: Set[str] = set()
        while queue:
            curr = queue.popleft()
            if curr in visited_b or not curr:
                continue
            visited_b.add(curr)
            if curr in ancestors_a:
                return curr  # Titik temu terdekat (LCA)
            if curr in self.objects:
                for parent in self.objects[curr].parents:
                    queue.append(parent)

        return None

    def merge(self, source_branch: str) -> None:
        """
        Menjalankan 'git merge <source_branch>'.
        Mendeteksi secara mekanis:
        1. Already up-to-date
        2. Fast-Forward Merge (memajukan pointer)
        3. True 3-Way Merge (membuat merge commit dengan 2 parent)
        """
        if self.is_detached:
            raise ValueError("Tidak dapat melakukan merge pada detached HEAD.")

        current_branch = self.head
        head_commit_hash = self.branches[current_branch]
        source_commit_hash = self.branches.get(source_branch, "")

        if not source_commit_hash:
            raise ValueError(f"Source branch '{source_branch}' tidak valid.")

        if head_commit_hash == source_commit_hash:
            print(f"{CLR_YELLOW}[MERGE NOOP]{CLR_RESET} Already up to date.")
            return

        lca_hash = self.find_lowest_common_ancestor(head_commit_hash, source_commit_hash)

        # Kasus 1: Fast-Forward
        # Jika LCA adalah head saat ini, head cukup 'didorong' maju ke source commit
        if lca_hash == head_commit_hash:
            print(f"{CLR_YELLOW}[MERGE FAST-FORWARD]{CLR_RESET} Updating {head_commit_hash[:7]}..{source_commit_hash[:7]}")
            self.branches[current_branch] = source_commit_hash
            self._checkout_tree(source_commit_hash)
            return

        # Kasus 2: 3-Way Merge
        print(f"{CLR_MAGENTA}[MERGE 3-WAY]{CLR_RESET} LCA terdeteksi pada {lca_hash[:7]}. Menganalisis diff 3 arah...")
        lca_tree = self.objects[lca_hash].tree if lca_hash else {}
        head_tree = self.objects[head_commit_hash].tree
        source_tree = self.objects[source_commit_hash].tree

        all_files = set(lca_tree.keys()) | set(head_tree.keys()) | set(source_tree.keys())
        merged_tree: Dict[str, str] = {}

        for path in all_files:
            base_blob = lca_tree.get(path)
            head_blob = head_tree.get(path)
            src_blob = source_tree.get(path)

            if head_blob == src_blob:
                # Keduanya setuju (atau sama-sama tidak diubah)
                if head_blob:
                    merged_tree[path] = head_blob
            elif base_blob == head_blob:
                # Modifikasi hanya ada di source branch
                if src_blob:
                    merged_tree[path] = src_blob
            elif base_blob == src_blob:
                # Modifikasi hanya ada di current head branch
                if head_blob:
                    merged_tree[path] = head_blob
            else:
                # Konflik dua arah terdeteksi
                raise RuntimeError(
                    f"{CLR_RED}[CONFLICT]{CLR_RESET} Konflik terjadi pada berkas '{path}'! "
                    f"Head: {head_blob[:7] if head_blob else 'DELETED'}, "
                    f"Source: {src_blob[:7] if src_blob else 'DELETED'}."
                )

        # Buat Merge Commit dengan 2 parents
        self.index = merged_tree.copy()
        merge_msg = f"Merge branch '{source_branch}' into {current_branch}"
        merge_commit = GitCommit(
            tree=self.index,
            parents=[head_commit_hash, source_commit_hash],
            message=merge_msg,
        )
        self.objects[merge_commit.commit_hash] = merge_commit
        self.branches[current_branch] = merge_commit.commit_hash
        self._checkout_tree(merge_commit.commit_hash)
        print(f"{CLR_GREEN}[MERGE SUCCESS]{CLR_RESET} Created merge commit {merge_commit.short_hash()} with parents [{head_commit_hash[:7]}, {source_commit_hash[:7]}]")

    def print_dag_graph(self) -> None:
        """Visualisasi Commit DAG dan posisi pointer referensi saat ini."""
        print(f"\n{CLR_BOLD}=== VISUALISASI COMMIT DAG & POINTERS ==={CLR_RESET}")
        for c_hash, commit in reversed(list(self.objects.items())):
            parents_str = ", ".join([p[:7] for p in commit.parents]) if commit.parents else "ROOT"
            
            # Label pointer yang merujuk commit ini
            labels = []
            for b_name, b_hash in self.branches.items():
                if b_hash == c_hash:
                    if not self.is_detached and self.head == b_name:
                        labels.append(f"{CLR_GREEN}{CLR_BOLD}HEAD -> {b_name}{CLR_RESET}")
                    else:
                        labels.append(f"{CLR_CYAN}{b_name}{CLR_RESET}")
            if self.is_detached and self.head == c_hash:
                labels.append(f"{CLR_RED}{CLR_BOLD}HEAD (detached){CLR_RESET}")

            pointer_tag = f" ({', '.join(labels)})" if labels else ""
            print(f"[*] Commit: {CLR_YELLOW}{commit.short_hash()}{CLR_RESET} [Parents: {parents_str}]{pointer_tag}")
            print(f"    Message: {commit.message}")
            files_preview = [f"{k}" for k in commit.tree.keys()]
            print(f"    Snapshot: {CLR_GRAY}{files_preview}{CLR_RESET}")
        print("=" * 45 + "\n")


def main() -> None:
    print(f"{CLR_BOLD}LAB: MEKANIKA DAN STRATEGI PERCABANGAN GIT TERISOLASI{CLR_RESET}\n")
    repo = GitRepositoryEngine()

    # 1. Root commit pada branch main
    print(f"{CLR_BOLD}[1] Inisialisasi Berkas Inti pada 'main'{CLR_RESET}")
    repo.write_file("kernel.py", "def boot(): return 'v1.0.0'")
    repo.stage_file("kernel.py")
    c1 = repo.commit("Initial commit: kernel foundation")
    print(f"Commit root berhasil: {c1[:7]}")

    # 2. Percabangan Feature (Fitur Baru)
    print(f"\n{CLR_BOLD}[2] Membuat Branch 'feature/auth' & Isolasi State{CLR_RESET}")
    repo.create_branch("feature/auth")
    repo.switch_branch("feature/auth")

    # Modifikasi di branch feature
    repo.write_file("auth.py", "class AuthManager: pass")
    repo.stage_file("auth.py")
    repo.commit("feat: implement basic auth manager")

    # Verifikasi isolasi working tree
    print(f"File di working tree saat di 'feature/auth': {list(repo.working_tree.keys())}")
    
    print(f"\n{CLR_BOLD}[3] Beralih kembali ke 'main' (Demonstrasi Isolasi){CLR_RESET}")
    repo.switch_branch("main")
    print(f"File di working tree saat di 'main': {list(repo.working_tree.keys())} -> (auth.py tidak terlihat!)")

    # 3. Fast-Forward Simulation
    print(f"\n{CLR_BOLD}[4] Simulasi Fast-Forward Merge{CLR_RESET}")
    # Karena 'main' tidak memiliki commit baru sejak dicabangkan, main cukup dimajukan ke 'feature/auth'
    repo.merge("feature/auth")
    repo.print_dag_graph()

    # 4. Divergensi Cabang (Mempersiapkan True 3-Way Merge)
    print(f"{CLR_BOLD}[5] Membangun Kondisi Divergen (Diverged History){CLR_RESET}")
    repo.create_branch("feature/telemetry")
    repo.switch_branch("feature/telemetry")
    repo.write_file("telemetry.py", "def collect_metrics(): return {}")
    repo.stage_file("telemetry.py")
    repo.commit("feat: add telemetry metrics exporter")

    # Kembali ke main lalu menambahkan hotfix/fitur lain secara paralel
    repo.switch_branch("main")
    repo.write_file("license.md", "# MIT License Copyright 2026")
    repo.stage_file("license.md")
    repo.commit("docs: add license file to project")

    # 5. True 3-Way Merge
    print(f"{CLR_BOLD}[6] Melakukan 3-Way Merge 'feature/telemetry' ke 'main'{CLR_RESET}")
    repo.merge("feature/telemetry")
    repo.print_dag_graph()

    # 6. Demonstrasi Detached HEAD
    print(f"{CLR_BOLD}[7] Mekanika Detached HEAD (Eksplorasi Snapshot Historis){CLR_RESET}")
    repo.is_detached = True
    repo.head = c1  # Lompat langsung ke commit awal
    repo._checkout_tree(c1)
    print(f"{CLR_RED}[DETACHED]{CLR_RESET} HEAD menunjuk langsung ke raw commit {c1[:7]}")
    print(f"Working tree snapshot saat ini: {list(repo.working_tree.keys())}")
    repo.print_dag_graph()


if __name__ == "__main__":
    main()