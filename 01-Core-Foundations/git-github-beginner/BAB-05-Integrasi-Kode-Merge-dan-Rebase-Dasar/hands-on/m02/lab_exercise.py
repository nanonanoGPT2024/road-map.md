#!/usr/bin/env python3
"""
Lab Hands-on: Integrasi Kode Git (Fast-Forward, 3-Way Merge, & Git Rebase)
Kategori: 01-Core-Foundations | Topik: git-github-beginner
Bab 05: Modul 02 Deep Dive

Script ini memodelkan Directed Acyclic Graph (DAG) commit Git, pointer branch/HEAD,
dan algoritma rekonsiliasi state:
1. Deteksi Lowest Common Ancestor (LCA)
2. Fast-Forward Merge (pemindahan pointer linier)
3. 3-Way Merge (penggabungan delta dari basis bersama + merge commit berkepala ganda)
4. Rebase (pencopotan commit patch dan pengaplikasian ulang di atas basis target)
"""

import hashlib
import json
import time
from typing import Dict, List, Optional, Set, Tuple

# ANSI Color Codes untuk Visualisasi Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"


class Commit:
    """
    Representasi Git Commit Object.
    Menyimpan snapshot pohon file, referensi parent, metadata, dan SHA-1 hash.
    """
    def __init__(self, parents: List[str], tree: Dict[str, str], message: str):
        self.parents: List[str] = parents
        self.tree: Dict[str, str] = tree.copy()  # Snapshot file (path -> content)
        self.message: str = message
        self.timestamp: float = time.time()
        self.sha: str = self._calculate_hash()

    def _calculate_hash(self) -> str:
        payload = {
            "parents": sorted(self.parents),
            "tree": self.tree,
            "message": self.message,
            "timestamp": f"{self.timestamp:.4f}"
        }
        raw_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha1(raw_str.encode("utf-8")).hexdigest()[:8]

    def __repr__(self) -> str:
        p_str = ",".join(self.parents) if self.parents else "root"
        return f"Commit({self.sha} | Parents: [{p_str}] | Msg: '{self.message}')"


class MiniGitEngine:
    """
    Engine Git mandiri yang mengelola Commit DAG, Refs (Branch), dan State File.
    """
    def __init__(self):
        self.commits: Dict[str, Commit] = {}
        self.branches: Dict[str, str] = {}  # Nama branch -> commit SHA
        self.head_branch: str = "main"
        self.working_tree: Dict[str, str] = {}

    def commit(self, message: str, file_updates: Dict[str, str]) -> str:
        """Merekam snapshot baru ke branch aktif."""
        self.working_tree.update(file_updates)
        parent_sha = self.branches.get(self.head_branch)
        parents = [parent_sha] if parent_sha else []

        new_commit = Commit(parents=parents, tree=self.working_tree, message=message)
        self.commits[new_commit.sha] = new_commit
        self.branches[self.head_branch] = new_commit.sha
        return new_commit.sha

    def create_branch(self, branch_name: str, start_point: Optional[str] = None):
        """Membuat referensi branch baru."""
        target_sha = start_point if start_point else self.branches[self.head_branch]
        self.branches[branch_name] = target_sha

    def checkout(self, branch_name: str):
        """Berpindah branch aktif dan merestorasi status working directory."""
        if branch_name not in self.branches:
            raise ValueError(f"Branch '{branch_name}' tidak ditemukan.")
        self.head_branch = branch_name
        current_sha = self.branches[branch_name]
        self.working_tree = self.commits[current_sha].tree.copy()

    def find_lca(self, sha1: str, sha2: str) -> Optional[str]:
        """
        Mencari Lowest Common Ancestor (LCA) menggunakan penelusuran Breadth-First Search (BFS).
        Kritikal untuk 3-Way Merge dan Rebase.
        """
        ancestors_1: Set[str] = set()
        queue = [sha1]
        while queue:
            curr = queue.pop(0)
            ancestors_1.add(curr)
            for p in self.commits[curr].parents:
                if p not in ancestors_1:
                    queue.append(p)

        # Temukan ancestor pertama dari sha2 yang ada di set sha1
        queue = [sha2]
        visited_2: Set[str] = set()
        while queue:
            curr = queue.pop(0)
            if curr in ancestors_1:
                return curr
            visited_2.add(curr)
            for p in self.commits[curr].parents:
                if p not in visited_2:
                    queue.append(p)
        return None

    def merge_fast_forward(self, target_branch: str) -> bool:
        """
        Mencoba Fast-Forward Merge.
        Jika HEAD adalah ancestor dari target_branch, pointer HEAD cukup digeser maju.
        """
        curr_sha = self.branches[self.head_branch]
        target_sha = self.branches[target_branch]
        lca = self.find_lca(curr_sha, target_sha)

        if lca == curr_sha:
            # Tidak ada deviasi di branch saat ini; pointer dapat dimajukan langsung
            self.branches[self.head_branch] = target_sha
            self.working_tree = self.commits[target_sha].tree.copy()
            return True
        return False

    def merge_three_way(self, target_branch: str) -> str:
        """
        Eksekusi 3-Way Merge:
        1. Identifikasi Basis Bersama (LCA)
        2. Hitung Delta (LCA -> HEAD) dan (LCA -> Target)
        3. Rekonsiliasi konflik (Auto-resolve jika file terpisah)
        4. Buat Merge Commit dengan 2 parents
        """
        curr_sha = self.branches[self.head_branch]
        target_sha = self.branches[target_branch]
        lca_sha = self.find_lca(curr_sha, target_sha)

        if not lca_sha:
            raise RuntimeError("Akar sejarah cabang terpisah total (Unrelated histories).")

        base_tree = self.commits[lca_sha].tree
        ours_tree = self.commits[curr_sha].tree
        theirs_tree = self.commits[target_sha].tree

        all_files = set(base_tree.keys()) | set(ours_tree.keys()) | set(theirs_tree.keys())
        merged_tree: Dict[str, str] = {}

        for file_path in all_files:
            val_base = base_tree.get(file_path)
            val_ours = ours_tree.get(file_path)
            val_theirs = theirs_tree.get(file_path)

            if val_ours == val_theirs:
                if val_ours is not None:
                    merged_tree[file_path] = val_ours
            elif val_ours == val_base:
                # 'Ours' tidak diubah, adopsi perubahan 'theirs'
                if val_theirs is not None:
                    merged_tree[file_path] = val_theirs
            elif val_theirs == val_base:
                # 'Theirs' tidak diubah, pertahankan perubahan 'ours'
                if val_ours is not None:
                    merged_tree[file_path] = val_ours
            else:
                # Kedua sisi mengubah file yang sama dari basis -> Merge Conflict!
                merged_tree[file_path] = (
                    f"<<<<<<< HEAD ({self.head_branch})\n"
                    f"{val_ours}\n"
                    f"=======\n"
                    f"{val_theirs}\n"
                    f">>>>>>> {target_branch}"
                )

        # Buat commit penggabungan (Merge Commit)
        msg = f"Merge branch '{target_branch}' into {self.head_branch}"
        merge_commit = Commit(parents=[curr_sha, target_sha], tree=merged_tree, message=msg)
        self.commits[merge_commit.sha] = merge_commit
        self.branches[self.head_branch] = merge_commit.sha
        self.working_tree = merged_tree.copy()
        return merge_commit.sha

    def rebase(self, upstream_branch: str):
        """
        Eksekusi Rebase:
        1. Cari titik temu (LCA)
        2. Kumpulkan commit unik pada branch aktif sejak LCA
        3. Pindahkan HEAD pointer ke puncak upstream
        4. Replay setiap commit dengan parent baru (menghasilkan SHA baru)
        """
        curr_sha = self.branches[self.head_branch]
        upstream_sha = self.branches[upstream_branch]
        lca = self.find_lca(curr_sha, upstream_sha)

        # Kumpulkan commit linier dari LCA ke branch saat ini
        commits_to_replay: List[Commit] = []
        node = curr_sha
        while node != lca:
            c = self.commits[node]
            commits_to_replay.append(c)
            node = c.parents[0] if c.parents else None

        commits_to_replay.reverse()

        # Mulai replay di atas upstream_sha
        current_base = upstream_sha
        for patch_commit in commits_to_replay:
            # Ambil delta dari commit asli terhadap parent aslinya
            orig_parent_tree = self.commits[patch_commit.parents[0]].tree if patch_commit.parents else {}
            new_tree = self.commits[current_base].tree.copy()

            for k, v in patch_commit.tree.items():
                if orig_parent_tree.get(k) != v:
                    new_tree[k] = v

            # Cetak commit baru dengan parent baru (sejarah ditulis ulang)
            rebased_commit = Commit(
                parents=[current_base],
                tree=new_tree,
                message=f"{patch_commit.message} (rebased)"
            )
            self.commits[rebased_commit.sha] = rebased_commit
            current_base = rebased_commit.sha

        # Arahkan pointer branch saat ini ke commit hasil replay terakhir
        self.branches[self.head_branch] = current_base
        self.working_tree = self.commits[current_base].tree.copy()

    def print_log(self):
        """Menampilkan visualisasi ringkas rantai commit dan pointer."""
        print(f"\n{CLR_BOLD}--- REPOSITORY TOPOLOGY LOG ---{CLR_RESET}")
        for branch, sha in self.branches.items():
            head_tag = f" {CLR_YELLOW}(HEAD -> {branch}){CLR_RESET}" if branch == self.head_branch else ""
            print(f"Branch '{CLR_CYAN}{branch}{CLR_RESET}' points to [{CLR_GREEN}{sha}{CLR_RESET}]{head_tag}")

        print(f"\n{CLR_BOLD}Daftar Seluruh Node Commit DAG:{CLR_RESET}")
        for sha, c in self.commits.items():
            p_str = ", ".join(c.parents) if c.parents else "None"
            print(f" * [{CLR_GREEN}{sha}{CLR_RESET}] Parents: [{p_str:^17}] | Msg: {c.message}")
        print("--------------------------------------------------------------------------------\n")


def print_step(title: str):
    print(f"\n{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}>>> {title} <<<{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")


def run_lab():
    repo = MiniGitEngine()

    # --- SKENARIO 1: INISIALISASI & COMMIT DASAR ---
    print_step("LANGKAH 1: Inisialisasi Repository & Baseline Commit")
    c1 = repo.commit("Initial commit: setup project structure", {"README.md": "# Mini Engine Docs\nVersion 1.0"})
    c2 = repo.commit("Feat: add auth scaffolding", {"auth.py": "def login(): pass"})
    print(f"Commit awal dibuat: {c1} -> {c2}")
    repo.print_log()

    # --- SKENARIO 2: FAST-FORWARD MERGE ---
    print_step("LANGKAH 2: Simulasi Fast-Forward Merge")
    print("Membuat feature branch 'feature/login-jwt' dari 'main'.")
    repo.create_branch("feature/login-jwt")
    repo.checkout("feature/login-jwt")

    c3 = repo.commit("Feat: implement jwt encode/decode", {"auth.py": "def login(): return 'jwt_token'"})
    print(f"Commit pada 'feature/login-jwt': [{c3}]")
    print("Kondisi: 'main' tidak memiliki commit baru setelah percabangan.")

    repo.checkout("main")
    print(f"Sebelum Merge: 'main' menunjuk ke [{repo.branches['main']}]")
    success_ff = repo.merge_fast_forward("feature/login-jwt")
    if success_ff:
        print(f"{CLR_GREEN}[FAST-FORWARD BERHASIL]{CLR_RESET} Pointer 'main' dimajukan langsung ke [{repo.branches['main']}].")
        print("Tidak ada Merge Commit baru yang di-generate karena rantai linear sempurna.")
    repo.print_log()

    # --- SKENARIO 3: DIVERGENSI & 3-WAY MERGE ---
    print_step("LANGKAH 3: Simulasi 3-Way Merge (Divergent History)")
    print("Menciptakan divergensi: 'main' dan 'feature/payment' sama-sama bertambah commit.")
    repo.create_branch("feature/payment")

    # Main commit perubahan pada modul database
    c_main = repo.commit("Chore: setup database connector", {"db.py": "def get_conn(): return 'conn'"})
    print(f"Branch 'main' membuat commit baru: [{c_main}]")

    # Pindah ke feature/payment dan commit modul payment
    repo.checkout("feature/payment")
    c_pay = repo.commit("Feat: integrate stripe client", {"payment.py": "def process(): return True"})
    print(f"Branch 'feature/payment' membuat commit baru: [{c_pay}]")

    print("\nMelakukan checkout ke 'main' dan mengeksekusi 3-Way Merge...")
    repo.checkout("main")
    merge_sha = repo.merge_three_way("feature/payment")
    print(f"{CLR_GREEN}[3-WAY MERGE BERHASIL]{CLR_RESET} Dibuat Merge Commit baru: [{CLR_BOLD}{merge_sha}{CLR_RESET}]")
    print(f"Parent Merge Commit: {repo.commits[merge_sha].parents} (Menyatukan 2 cabang)")
    print(f"State File Hasil Integrasi: {list(repo.working_tree.keys())}")
    repo.print_log()

    # --- SKENARIO 4: GIT REBASE (LINEARISASI HISTORY) ---
    print_step("LANGKAH 4: Simulasi Git Rebase (Rewrite History)")
    print("Membuat branch 'feature/metrics' dari commit divergen sebelumnya...")
    repo.create_branch("feature/metrics", start_point=c_main)
    repo.checkout("feature/metrics")

    c_m1 = repo.commit("Feat: add prometheus exporter", {"metrics.py": "export_count = 0"})
    c_m2 = repo.commit("Feat: record http latency", {"metrics.py": "export_count = 0\nlatency = 12"})
    print(f"Feature metrics memiliki 2 commit lokal: [{c_m1}] dan [{c_m2}] berbasis [{c_main}].")

    print(f"Target upstream rebase adalah 'main' yang saat ini berada di [{repo.branches['main']}].")
    print("Mengeksekusi REBASE: Memetik (cherry-pick) commit feature/metrics ke atas 'main'...")
    repo.rebase("main")

    new_head_sha = repo.branches["feature/metrics"]
    print(f"{CLR_GREEN}[REBASE SELESAI]{CLR_RESET}")
    print(f"Branch 'feature/metrics' kini bertengger langsung di atas 'main'.")
    print(f"SHA commit telah ditulis ulang (diverifikasi hash baru): [{new_head_sha}]")
    print(f"Parent dari puncak rebased commit: {repo.commits[new_head_sha].parents}")
    repo.print_log()

    print_step("RINGKASAN TEKNIS LAB")
    print(f"1. {CLR_YELLOW}Fast-Forward{CLR_RESET}: LCA(HEAD, Target) == HEAD. Perubahan murni linier, memajukan pointer.")
    print(f"2. {CLR_YELLOW}3-Way Merge{CLR_RESET} : LCA berada di belakang keduanya. Terbentuk commit baru dengan 2 parents.")
    print(f"3. {CLR_YELLOW}Git Rebase{CLR_RESET}  : Mencabut commit dari fork-point (LCA) dan mengaplikasikan ulang")
    print("                    di ujung branch target. Menghasilkan SHA baru dan riwayat bersih linier.")


if __name__ == "__main__":
    run_lab()