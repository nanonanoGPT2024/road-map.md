#!/usr/bin/env python3
"""
Lab Hands-on: Resolusi Konflik (Merge Conflict Resolution & State Recovery)
Modul 02 Deep Dive - Git & GitHub Foundations

Deskripsi:
Script ini memodelkan algoritma 'Three-Way Merge' Git, deteksi hunk conflict,
injeksi conflict markers (<<<<<<<, =======, >>>>>>>), serta simulasi State
Recovery Engine ('git merge --abort', stage tracking, dan state rollback).
"""

import sys
import copy
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"


class RepoState(Enum):
    CLEAN = "CLEAN"
    MERGING_CONFLICT = "MERGING (CONFLICT)"
    MERGING_RESOLVED = "MERGING (ALL RESOLVED)"


@dataclass
class Commit:
    commit_id: str
    message: str
    tree: Dict[str, List[str]]  # filename -> lines of content
    parent_ids: List[str] = field(default_factory=list)


class ThreeWayMergeEngine:
    """
    Mengimplementasikan logika Three-Way Merge (Base vs Ours vs Theirs).
    Mendeteksi hunk yang termodifikasi secara independen atau bentrok serentak.
    """

    @staticmethod
    def merge_content(
        base: List[str],
        ours: List[str],
        theirs: List[str],
        branch_ours: str = "HEAD",
        branch_theirs: str = "feature"
    ) -> Tuple[List[str], bool]:
        """
        Melakukan rekonsiliasi baris demi baris berbasis Common Ancestor (Base).
        Mengembalikan (merged_lines, has_conflicts).
        """
        merged: List[str] = []
        has_conflict = False
        max_len = max(len(base), len(ours), len(theirs))

        i = 0
        while i < max_len:
            b_line = base[i] if i < len(base) else None
            o_line = ours[i] if i < len(ours) else None
            t_line = theirs[i] if i < len(theirs) else None

            # Skenario 1: Tidak ada perubahan atau kedua cabang mengubah ke hal yang sama persis
            if o_line == t_line:
                if o_line is not None:
                    merged.append(o_line)
            # Skenario 2: Hanya Ours yang mengubah baris
            elif b_line == t_line and o_line != b_line:
                if o_line is not None:
                    merged.append(o_line)
            # Skenario 3: Hanya Theirs yang mengubah baris
            elif b_line == o_line and t_line != b_line:
                if t_line is not None:
                    merged.append(t_line)
            # Skenario 4: Keduanya mengubah baris ke nilai berbeda -> CONFLICT!
            else:
                has_conflict = True
                merged.append(f"<<<<<<< {branch_ours}")
                if o_line is not None:
                    merged.append(o_line)
                merged.append("=======")
                if t_line is not None:
                    merged.append(t_line)
                merged.append(f">>>>>>> {branch_theirs}")

            i += 1

        return merged, has_conflict


class GitVirtualRepository:
    """
    Simulasi Working Directory, Staging Area (Index), HEAD pointer,
    dan MERGE_HEAD state tracking.
    """

    def __init__(self):
        self.commits: Dict[str, Commit] = {}
        self.branches: Dict[str, str] = {}  # branch_name -> commit_id
        self.current_branch: str = "main"
        self.head_commit_id: Optional[str] = None
        self.state: RepoState = RepoState.CLEAN

        # Snapshot untuk State Recovery saat Merge Conflict
        self.pre_merge_tree: Dict[str, List[str]] = {}
        self.working_directory: Dict[str, List[str]] = {}
        self.index: Dict[str, List[str]] = {}
        self.merge_head: Optional[str] = None

    def commit(self, message: str, files: Dict[str, List[str]]) -> str:
        """Membuat commit baru pada active branch."""
        cid = f"c{len(self.commits) + 1:03d}"
        parents = [self.head_commit_id] if self.head_commit_id else []
        new_commit = Commit(commit_id=cid, message=message, tree=copy.deepcopy(files), parent_ids=parents)

        self.commits[cid] = new_commit
        self.branches[self.current_branch] = cid
        self.head_commit_id = cid
        self.working_directory = copy.deepcopy(files)
        self.index = copy.deepcopy(files)
        return cid

    def branch(self, branch_name: str):
        """Membuat branch pointer baru dari HEAD saat ini."""
        self.branches[branch_name] = self.head_commit_id

    def checkout(self, branch_name: str):
        """Berpindah branch dan merefresh working directory."""
        if branch_name not in self.branches:
            raise ValueError(f"Cabang {branch_name} tidak ditemukan.")
        self.current_branch = branch_name
        self.head_commit_id = self.branches[branch_name]
        self.working_directory = copy.deepcopy(self.commits[self.head_commit_id].tree)
        self.index = copy.deepcopy(self.working_directory)

    def merge(self, target_branch: str) -> bool:
        """
        Mengeksekusi merge dari target_branch ke current_branch.
        Mengembalikan True jika fast-forward / clean merge, False jika conflict.
        """
        target_cid = self.branches.get(target_branch)
        if not target_cid:
            raise ValueError(f"Cabang target '{target_branch}' tidak valid.")

        ours_cid = self.head_commit_id
        base_cid = self._find_merge_base(ours_cid, target_cid)

        # Simpan snapshot working directory untuk State Recovery (git merge --abort)
        self.pre_merge_tree = copy.deepcopy(self.working_directory)
        self.merge_head = target_cid

        base_tree = self.commits[base_cid].tree if base_cid else {}
        ours_tree = self.commits[ours_cid].tree
        theirs_tree = self.commits[target_cid].tree

        all_files = set(ours_tree.keys()).union(theirs_tree.keys()).union(base_tree.keys())
        any_conflict = False

        print(f"{ANSI.CYAN}--> Menjalankan 3-Way Merge:{ANSI.RESET}")
        print(f"    Base Ancestor : {ANSI.BOLD}{base_cid}{ANSI.RESET}")
        print(f"    Ours (HEAD)   : {ANSI.BOLD}{self.current_branch} ({ours_cid}){ANSI.RESET}")
        print(f"    Theirs        : {ANSI.BOLD}{target_branch} ({target_cid}){ANSI.RESET}\n")

        merged_workspace = {}
        for filename in all_files:
            b_lines = base_tree.get(filename, [])
            o_lines = ours_tree.get(filename, [])
            t_lines = theirs_tree.get(filename, [])

            merged_lines, conflict = ThreeWayMergeEngine.merge_content(
                b_lines, o_lines, t_lines, branch_ours=self.current_branch, branch_theirs=target_branch
            )
            merged_workspace[filename] = merged_lines
            if conflict:
                any_conflict = True

        self.working_directory = merged_workspace

        if any_conflict:
            self.state = RepoState.MERGING_CONFLICT
            return False
        else:
            self.state = RepoState.CLEAN
            self.index = copy.deepcopy(merged_workspace)
            cid = self.commit(f"Merge branch '{target_branch}' into {self.current_branch}", merged_workspace)
            self.commits[cid].parent_ids = [ours_cid, target_cid]
            self.merge_head = None
            return True

    def abort_merge(self):
        """Memulihkan working tree dan index ke posisi sebelum merge."""
        if self.state not in (RepoState.MERGING_CONFLICT, RepoState.MERGING_RESOLVED):
            print(f"{ANSI.RED}Tidak ada proses merge yang sedang berjalan.{ANSI.RESET}")
            return

        print(f"{ANSI.YELLOW}[State Recovery] Mengembalikan Working Directory ke snapshot HEAD...{ANSI.RESET}")
        self.working_directory = copy.deepcopy(self.pre_merge_tree)
        self.index = copy.deepcopy(self.pre_merge_tree)
        self.merge_head = None
        self.state = RepoState.CLEAN
        print(f"{ANSI.GREEN}[State Recovery] git merge --abort BERHASIL. Status kembali CLEAN.{ANSI.RESET}\n")

    def resolve_manual(self, filename: str, resolved_content: List[str]):
        """Menyimulasikan editing manual developer untuk membuang conflict markers."""
        if filename not in self.working_directory:
            raise KeyError(f"File {filename} tidak ada di working directory.")
        self.working_directory[filename] = resolved_content
        # Staging file yang sudah di-resolve (git add)
        self.index[filename] = copy.deepcopy(resolved_content)

        # Cek apakah seluruh conflict markers sudah hilang di semua file
        unresolved = False
        for lines in self.index.values():
            if any("<<<<<<<" in line for line in lines):
                unresolved = True
                break

        if not unresolved:
            self.state = RepoState.MERGING_RESOLVED

    def complete_merge_commit(self, message: str) -> str:
        """Menyelesaikan merge commit setelah resolusi konflik diselesaikan."""
        if self.state != RepoState.MERGING_RESOLVED:
            raise RuntimeError("Tidak dapat commit: Masih ada konflik atau belum di-stage.")

        cid = f"c{len(self.commits) + 1:03d}"
        parents = [self.head_commit_id, self.merge_head]
        new_commit = Commit(commit_id=cid, message=message, tree=copy.deepcopy(self.index), parent_ids=parents)
        self.commits[cid] = new_commit
        self.branches[self.current_branch] = cid
        self.head_commit_id = cid
        self.state = RepoState.CLEAN
        self.merge_head = None
        return cid

    def _find_merge_base(self, cid_a: str, cid_b: str) -> Optional[str]:
        """Menemukan common ancestor terdalam via Breadth-First Search traversal."""
        ancestors_a = set()
        queue = [cid_a]
        while queue:
            curr = queue.pop(0)
            if curr:
                ancestors_a.add(curr)
                queue.extend(self.commits[curr].parent_ids)

        queue = [cid_b]
        while queue:
            curr = queue.pop(0)
            if curr in ancestors_a:
                return curr
            if curr:
                queue.extend(self.commits[curr].parent_ids)
        return None


def print_banner(text: str):
    print(f"\n{ANSI.BOLD}{ANSI.MAGENTA}{'=' * 65}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.MAGENTA}  {text}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.MAGENTA}{'=' * 65}{ANSI.RESET}\n")


def display_file(filename: str, lines: List[str]):
    print(f"{ANSI.BOLD}--- {filename} ---{ANSI.RESET}")
    for idx, line in enumerate(lines, 1):
        if line.startswith("<<<<<<<") or line.startswith(">>>>>>>"):
            print(f"{ANSI.BG_RED}{ANSI.BOLD}{idx:2d} | {line}{ANSI.RESET}")
        elif line.startswith("======="):
            print(f"{ANSI.YELLOW}{idx:2d} | {line}{ANSI.RESET}")
        else:
            print(f"{idx:2d} | {line}")
    print()


def main():
    repo = GitVirtualRepository()

    print_banner("SIMULASI LAB: MERGE CONFLICT RESOLUTION & STATE RECOVERY")

    # 1. SETUP BASE COMMIT
    print(f"{ANSI.BOLD}[Langkah 1] Membuat Base Ancestor Commit (c001){ANSI.RESET}")
    initial_config = [
        "app_env: production",
        "database_pool: 10",
        "cache_ttl_seconds: 3600",
        "log_level: info"
    ]
    c1 = repo.commit("Init base config", {"config.yaml": initial_config})
    print(f"Commit {c1} dibuat di branch 'main'.")

    # 2. FEATURE BRANCH DIVERGENCE
    print(f"\n{ANSI.BOLD}[Langkah 2] Membuat Branch 'feature/performance-tuning' & Modifikasi{ANSI.RESET}")
    repo.branch("feature/performance-tuning")
    repo.checkout("feature/performance-tuning")
    feature_config = [
        "app_env: production",
        "database_pool: 50",       # Berubah: pool dinaikkan
        "cache_ttl_seconds: 7200", # Berubah: cache diperpanjang
        "log_level: info"
    ]
    c2 = repo.commit("Tune pool size to 50 & cache to 7200", {"config.yaml": feature_config})
    print(f"Commit {c2} dibuat di branch 'feature/performance-tuning'.")

    # 3. MAIN BRANCH DIVERGENCE (CONFLICT SETUP)
    print(f"\n{ANSI.BOLD}[Langkah 3] Pindah ke 'main' & Lakukan Hotfix yang Bertabrakan{ANSI.RESET}")
    repo.checkout("main")
    main_config = [
        "app_env: production",
        "database_pool: 20",       # Berubah ke nilai beda: pool diubah ke 20
        "cache_ttl_seconds: 3600", # Tetap sama seperti base
        "log_level: debug"         # Berubah: log diubah ke debug
    ]
    c3 = repo.commit("Hotfix main: db_pool=20 & debug logs", {"config.yaml": main_config})
    print(f"Commit {c3} dibuat di branch 'main'.")

    # 4. MERGE DENGAN HASIL CONFLICT
    print(f"\n{ANSI.BOLD}[Langkah 4] Merge 'feature/performance-tuning' ke 'main'{ANSI.RESET}")
    merge_success = repo.merge("feature/performance-tuning")

    if not merge_success:
        print(f"{ANSI.RED}{ANSI.BOLD}[CONFLICT DETECTED!]{ANSI.RESET}")
        print(f"Status Repositori: {ANSI.YELLOW}{repo.state.value}{ANSI.RESET}\n")
        display_file("config.yaml", repo.working_directory["config.yaml"])

    # 5. DEMO STATE RECOVERY: MERGE --ABORT
    print(f"{ANSI.BOLD}[Langkah 5] Simulasi State Recovery #1: 'git merge --abort'{ANSI.RESET}")
    print("Skenario: Developer belum siap merge, ingin memulihkan state awal.")
    repo.abort_merge()
    print("Kondisi file setelah di-abort (harus kembali ke kondisi commit c003):")
    display_file("config.yaml", repo.working_directory["config.yaml"])

    # 6. TRIGGER MERGE LAGI DAN RESOLVE MANUAL
    print(f"{ANSI.BOLD}[Langkah 6] Eksekusi Ulang Merge & Simulasi Resolusi Manual{ANSI.RESET}")
    repo.merge("feature/performance-tuning")
    print(f"State saat ini: {ANSI.YELLOW}{repo.state.value}{ANSI.RESET}")

    # Developer merekonsiliasi: ambil pool=50 dari feature, cache=7200 dari feature, log=debug dari main
    resolved_lines = [
        "app_env: production",
        "database_pool: 50",       # Resolusi: Memilih dari feature
        "cache_ttl_seconds: 7200", # Otomatis terpilih dari feature (non-conflicting)
        "log_level: debug"         # Otomatis terpilih dari main (non-conflicting)
    ]
    print(f"{ANSI.CYAN}[Resolusi] Developer mengedit file, menghapus marker, dan melakukan 'git add'...{ANSI.RESET}")
    repo.resolve_manual("config.yaml", resolved_lines)
    print(f"Status Repositori: {ANSI.GREEN}{repo.state.value}{ANSI.RESET}\n")

    # 7. COMMIT FINAL RESOLUSI
    print(f"{ANSI.BOLD}[Langkah 7] Finalisasi Resolusi dengan Merge Commit{ANSI.RESET}")
    final_cid = repo.complete_merge_commit("Merge branch 'feature/performance-tuning' into main [Resolved Conflicts]")
    print(f"{ANSI.GREEN}[BERHASIL] Merge commit tercipta: {final_cid}{ANSI.RESET}")
    print(f"Parent commits: {repo.commits[final_cid].parent_ids}")
    print(f"State Repositori Akhir: {ANSI.GREEN}{repo.state.value}{ANSI.RESET}\n")

    print(f"{ANSI.BOLD}Isi config.yaml final:{ANSI.RESET}")
    display_file("config.yaml", repo.working_directory["config.yaml"])


if __name__ == "__main__":
    main()