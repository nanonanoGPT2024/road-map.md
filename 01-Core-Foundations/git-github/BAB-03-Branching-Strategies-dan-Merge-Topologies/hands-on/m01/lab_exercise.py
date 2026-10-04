#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Branching Strategies & Merge Topologies
BAB-03: Branching Strategies dan Merge Topologies
Modul 01: Fondasi Branching, Merge Topologies, dan Strategi Rilis

File ini adalah skrip interaktif mandiri (runnable) yang mensimulasikan
topologi commit Git (DAG - Directed Acyclic Graph) untuk berbagai operasi merge:
1. Fast-Forward Merge
2. 3-Way Merge (True Merge / --no-ff)
3. Squash Merge
4. Git Rebase (Linear History)
5. Studi Kasus Workflow: Git Flow vs GitHub Flow vs Trunk-Based Development
"""

import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"


@dataclass
class CommitNode:
    commit_id: str
    message: str
    branch: str
    parents: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class GitTopologySimulator:
    def __init__(self):
        self.commits: Dict[str, CommitNode] = {}
        self.branches: Dict[str, str] = {}  # branch_name -> commit_id
        self.head_branch: str = "main"
        self._init_repository()

    def _init_repository(self):
        """Inisialisasi repo dengan commit awal pada branch main."""
        self.commits.clear()
        self.branches.clear()
        c0 = CommitNode(
            commit_id="a1b2c01",
            message="Initial commit: Project setup & README",
            branch="main",
            parents=[]
        )
        c1 = CommitNode(
            commit_id="a1b2c02",
            message="feat: core routing engine",
            branch="main",
            parents=["a1b2c01"]
        )
        self.commits[c0.commit_id] = c0
        self.commits[c1.commit_id] = c1
        self.branches["main"] = c1.commit_id
        self.head_branch = "main"

    def banner(self, title: str):
        print(f"\n{BOLD}{CYAN}{'=' * 72}{RESET}")
        print(f"{BOLD}{WHITE}{title.center(72)}{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 72}{RESET}\n")

    def print_status(self, action_name: str, explanation: str):
        print(f"{BG_BLUE}{WHITE}{BOLD} ACTION {RESET} {BOLD}{YELLOW}{action_name}{RESET}")
        print(f"{DIM}Penjelasan:{RESET} {WHITE}{explanation}{RESET}\n")

    def render_dag(self):
        """Render commit log visual dengan representasi topologi."""
        print(f"{BOLD}{MAGENTA}--- Visualisasi Topological Commit Graph ---{RESET}")
        sorted_commits = sorted(self.commits.values(), key=lambda c: c.timestamp)
        
        for commit in sorted_commits:
            parents_str = f"<- [{', '.join(commit.parents)}]" if commit.parents else "(root)"
            branch_tag = f" {BOLD}{GREEN}({commit.branch}){RESET}" if commit.branch else ""
            
            # Deteksi merge commit (memiliki >= 2 parent)
            if len(commit.parents) > 1:
                prefix = f"{BOLD}{YELLOW}* [MERGE COMMIT]{RESET}"
            elif commit.branch == "main":
                prefix = f"{BOLD}{BLUE}* [main]{RESET}"
            else:
                prefix = f"{BOLD}{CYAN}* [{commit.branch}]{RESET}"

            print(f" {prefix} {BOLD}{commit.commit_id}{RESET} {parents_str}{branch_tag}")
            print(f"   |-- {WHITE}{commit.message}{RESET}")
        
        print(f"{BOLD}{MAGENTA}{'-' * 46}{RESET}\n")

    def simulate_fast_forward(self):
        self.banner("SIMULASI 1: FAST-FORWARD MERGE")
        self._init_repository()
        
        self.print_status(
            "git checkout -b feature/auth",
            "Membuat branch baru dari ujung main (HEAD). Tidak ada divergensi."
        )
        c_feat1 = CommitNode(
            commit_id="f01a001",
            message="feat(auth): login controller & jwt token",
            branch="feature/auth",
            parents=["a1b2c02"],
            timestamp=time.time() + 1
        )
        self.commits[c_feat1.commit_id] = c_feat1
        self.branches["feature/auth"] = c_feat1.commit_id
        self.render_dag()

        self.print_status(
            "git checkout main && git merge feature/auth (Fast-Forward)",
            "Karena main tidak bergerak sejak branch dibuat, pointer main hanya 'maju' (fast-forward) "
            "menunjuk ke commit feature. Tidak ada merge commit baru yang tercipta."
        )
        # Fast-Forward: pointer main langsung diperbarui ke commit feature
        self.branches["main"] = self.branches["feature/auth"]
        self.commits[c_feat1.commit_id].branch = "main (merged FF)"
        self.render_dag()
        print(f"{GREEN}[INFO]{RESET} Karakteristik Fast-Forward: Linear, rapi, tanpa merge bubble.\n")

    def simulate_three_way_merge(self):
        self.banner("SIMULASI 2: 3-WAY MERGE (RECURSIVE / ORT - NON-FAST-FORWARD)")
        self._init_repository()

        # Branch feature dibuat
        c_feat1 = CommitNode(
            commit_id="f02a001",
            message="feat(payment): integrate stripe webhook",
            branch="feature/payment",
            parents=["a1b2c02"],
            timestamp=time.time() + 1
        )
        self.commits[c_feat1.commit_id] = c_feat1
        self.branches["feature/payment"] = c_feat1.commit_id

        # Branch main juga mendapat commit baru (divergensi terjadi)
        c_main_hotfix = CommitNode(
            commit_id="m02a003",
            message="hotfix: sanitize query parameter injection",
            branch="main",
            parents=["a1b2c02"],
            timestamp=time.time() + 2
        )
        self.commits[c_main_hotfix.commit_id] = c_main_hotfix
        self.branches["main"] = c_main_hotfix.commit_id

        self.print_status(
            "Divergensi Terdeteksi!",
            "main telah maju dengan commit m02a003, sementara feature memiliki f02a001. "
            "Fast-forward mustahil dilakukan tanpa rebase."
        )
        self.render_dag()

        # Eksekusi 3-Way Merge
        merge_commit = CommitNode(
            commit_id="m02merge",
            message="Merge branch 'feature/payment' into main",
            branch="main",
            parents=["m02a003", "f02a001"],
            timestamp=time.time() + 3
        )
        self.commits[merge_commit.commit_id] = merge_commit
        self.branches["main"] = merge_commit.commit_id

        self.print_status(
            "git merge feature/payment (3-Way Merge)",
            "Git mencari Common Ancestor (a1b2c02), lalu membandingkan HEAD main (m02a003) "
            "dan feature HEAD (f02a001). Hasilnya adalah Merge Commit baru dengan 2 parents!"
        )
        self.render_dag()
        print(f"{GREEN}[INFO]{RESET} Karakteristik 3-Way: Mempertahankan riwayat historis asli & konteks cabang.\n")

    def simulate_squash_merge(self):
        self.banner("SIMULASI 3: SQUASH MERGE")
        self._init_repository()

        # Tambahkan serangkaian commit kecil (WIP) di feature
        c1 = CommitNode("sq01", "wip: add form ui", "feature/cart", ["a1b2c02"], time.time() + 1)
        c2 = CommitNode("sq02", "fix typo in button class", "feature/cart", ["sq01"], time.time() + 2)
        c3 = CommitNode("sq03", "feat: finalize checkout validation", "feature/cart", ["sq02"], time.time() + 3)
        for c in (c1, c2, c3):
            self.commits[c.commit_id] = c
        self.branches["feature/cart"] = c3.commit_id

        self.print_status(
            "feature/cart Memiliki 3 Commit Kecil/Bising",
            "Commit sq01, sq02, dan sq03 merekam proses pengerjaan bertahap yang tidak perlu mengotori history main."
        )
        self.render_dag()

        # Squash merge
        squash_commit = CommitNode(
            commit_id="sq_final",
            message="feat(cart): complete shopping cart and checkout form (#42)",
            branch="main",
            parents=["a1b2c02"],
            timestamp=time.time() + 4
        )
        self.commits[squash_commit.commit_id] = squash_commit
        self.branches["main"] = squash_commit.commit_id

        self.print_status(
            "git merge --squash feature/cart && git commit",
            "Semua perubahan dari sq01, sq02, sq03 digabungkan menjadi SATU commit tunggal di main. "
            "Induknya hanya satu (a1b2c02), bukan merge commit 2 parent."
        )
        self.render_dag()
        print(f"{GREEN}[INFO]{RESET} Karakteristik Squash: Git log main sangat bersih, commit atomic per PR.\n")

    def simulate_rebase(self):
        self.banner("SIMULASI 4: GIT REBASE (LINEARIZATION)")
        self._init_repository()

        # Feature dibuat dari a1b2c02
        c_feat = CommitNode("rb_feat1", "feat(export): pdf exporter", "feature/export", ["a1b2c02"], time.time() + 1)
        self.commits[c_feat.commit_id] = c_feat
        self.branches["feature/export"] = c_feat.commit_id

        # Main bergerak maju
        c_main2 = CommitNode("m_new01", "refactor: database connection pool", "main", ["a1b2c02"], time.time() + 2)
        self.commits[c_main2.commit_id] = c_main2
        self.branches["main"] = c_main2.commit_id

        self.print_status(
            "Kondisi Sebelum Rebase (Diverged)",
            "feature/export bertumpu pada commit lama (a1b2c02). Main sudah melompat ke m_new01."
        )
        self.render_dag()

        # Rebase: replay commit feature di atas HEAD main
        c_feat_replayed = CommitNode(
            "rb_feat1'",
            "feat(export): pdf exporter (replayed)",
            "feature/export",
            ["m_new01"],
            time.time() + 3
        )
        del self.commits["rb_feat1"]
        self.commits[c_feat_replayed.commit_id] = c_feat_replayed
        self.branches["feature/export"] = c_feat_replayed.commit_id

        self.print_status(
            "git checkout feature/export && git rebase main",
            "Git mencabut commit rb_feat1, lalu memainkannya kembali (replay) di atas m_new01. "
            "Dihasilkan commit baru rb_feat1' dengan hash berbeda, menciptakan garis linear!"
        )
        self.render_dag()
        print(f"{RED}[GOLDEN RULE OF REBASE]{RESET}: Jangan pernah me-rebase branch publik yang dipakai bersama!\n")

    def display_workflow_comparison(self):
        self.banner("KOMPARASI BRANCHING STRATEGY DI INDUSTRI")
        table = f"""
{BOLD}{'Strategi':<18} | {'Karakteristik Kunci':<28} | {'Kelebihan':<22} | {'Kelemahan':<20}{RESET}
{'-'*98}
{CYAN}{'Git Flow':<18}{RESET} | main, develop, release, hotfix | Sangat terkontrol, stabil  | Rilis lambat, merge hell
{GREEN}{'GitHub Flow':<18}{RESET} | main + short-lived branch + PR | Sederhana, cocok utk CI/CD | Butuh automasi testing
{MAGENTA}{'Trunk-Based':<18}{RESET} | 1 trunk, commit langsung/short | Fast cycle, zero drift     | Wajib Feature Flags
{'-'*98}
        """
        print(table)


def run_interactive_menu():
    sim = GitTopologySimulator()
    while True:
        print(f"\n{BOLD}{YELLOW}=== LAB SIMULATOR: BRANCHING STRATEGIES & MERGE TOPOLOGIES ==={RESET}")
        print("1. Simulasi Fast-Forward Merge")
        print("2. Simulasi 3-Way Merge (True Merge / --no-ff)")
        print("3. Simulasi Squash Merge")
        print("4. Simulasi Git Rebase (Linearization)")
        print("5. Jalankan Semua Simulasi Secara Sekuensial")
        print("6. Tabel Komparasi Workflow Industri (Git Flow / GitHub Flow / Trunk-Based)")
        print("0. Keluar")
        
        try:
            choice = input(f"{BOLD}{WHITE}Pilih opsi [0-6]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            sim.simulate_fast_forward()
        elif choice == "2":
            sim.simulate_three_way_merge()
        elif choice == "3":
            sim.simulate_squash_merge()
        elif choice == "4":
            sim.simulate_rebase()
        elif choice == "5":
            sim.simulate_fast_forward()
            sim.simulate_three_way_merge()
            sim.simulate_squash_merge()
            sim.simulate_rebase()
            sim.display_workflow_comparison()
        elif choice == "6":
            sim.display_workflow_comparison()
        elif choice == "0":
            print(f"{GREEN}Lab selesai. Selamat mempraktikkan branching topology!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 0-6.{RESET}")


if __name__ == "__main__":
    # Jika dijalankan dengan argument non-interaktif seperti '--auto' atau 'test'
    if len(sys.argv) > 1 and sys.argv[1] in ("--auto", "-a", "test"):
        sim = GitTopologySimulator()
        sim.simulate_fast_forward()
        sim.simulate_three_way_merge()
        sim.simulate_squash_merge()
        sim.simulate_rebase()
        sim.display_workflow_comparison()
    else:
        run_interactive_menu()
