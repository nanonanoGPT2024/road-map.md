#!/usr/bin/env python3
"""
Hands-on Lab M01: Simulasi Interaktif Pull Request Workflows & Code Review
Topik: BAB-07-Pull-Request-Workflows-dan-Code-Review

Deskripsi:
Program mandiri (standalone) yang mensimulasikan alur kerja Pull Request (PR) modern:
1. Pembuatan feature branch & commit
2. Pembuatan Pull Request (PR) dengan template deskripsi
3. Eksekusi Automated CI Checks (Lint, Test, Security audit)
4. Simulasi Code Review (Reviewers, comments, Request Changes, Approval)
5. Branch Protection Rules enforcement (Required approvals, Passing CI)
6. Strategi Merge (Squash & Merge, Rebase & Merge, Merge Commit)
7. Housekeeping (Branch deletion)
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BG_DARK = "\033[40m"


class ReviewStatus(Enum):
    PENDING = "PENDING"
    COMMENTED = "COMMENTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED = "APPROVED"


class MergeStrategy(Enum):
    MERGE_COMMIT = "Create a Merge Commit (--no-ff)"
    SQUASH = "Squash and Merge (--squash)"
    REBASE = "Rebase and Merge (--rebase)"


@dataclass
class Commit:
    sha: str
    message: str
    author: str
    files_changed: List[str]


@dataclass
class ReviewComment:
    reviewer: str
    file_name: str
    line_number: int
    comment: str
    resolved: bool = False


@dataclass
class PullRequest:
    id: int
    title: str
    description: str
    author: str
    source_branch: str
    target_branch: str
    commits: List[Commit] = field(default_factory=list)
    comments: List[ReviewComment] = field(default_factory=list)
    reviews: Dict[str, ReviewStatus] = field(default_factory=dict)
    ci_status: Dict[str, bool] = field(default_factory=dict)
    is_merged: bool = False
    merge_commit_sha: Optional[str] = None


class GitSimEngine:
    def __init__(self):
        self.branches = {
            "main": [
                Commit("a1b2c3d", "feat: initial project setup", "Alice", ["README.md", "app.py"])
            ]
        }
        self.current_branch = "main"
        self.pull_requests: List[PullRequest] = []
        self.protection_rules = {
            "require_ci_pass": True,
            "min_approvals": 1,
            "no_direct_push_to_main": True,
        }

    def print_header(self, text: str):
        print(f"\n{Color.BOLD}{Color.CYAN}{'='*60}{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN}▶ {text.upper()}{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN}{'='*60}{Color.RESET}")

    def print_success(self, text: str):
        print(f"{Color.GREEN}✔ {text}{Color.RESET}")

    def print_warning(self, text: str):
        print(f"{Color.YELLOW}⚠ {text}{Color.RESET}")

    def print_error(self, text: str):
        print(f"{Color.RED}✖ {text}{Color.RESET}")

    def print_info(self, text: str):
        print(f"{Color.BLUE}ℹ {text}{Color.RESET}")

    def run_step_1_create_branch_and_commits(self) -> str:
        self.print_header("Langkah 1: Membuat Feature Branch & Commit")
        branch_name = "feature/jwt-authentication"
        self.branches[branch_name] = list(self.branches["main"])
        self.current_branch = branch_name

        self.print_info(f"Berpindah ke branch baru: {Color.BOLD}{branch_name}{Color.RESET}")

        c1 = Commit(
            sha="f47a901",
            message="feat(auth): implement token generator and verifier",
            author="DevBudi",
            files_changed=["auth/jwt_service.py", "requirements.txt"]
        )
        c2 = Commit(
            sha="8b12e44",
            message="test(auth): add unit test suite for jwt auth",
            author="DevBudi",
            files_changed=["tests/test_jwt_service.py"]
        )
        self.branches[branch_name].extend([c1, c2])

        for c in [c1, c2]:
            print(f"  {Color.MAGENTA}[{c.sha}]{Color.RESET} {c.message} {Color.DIM}({c.author}){Color.RESET}")
            print(f"      Modified: {', '.join(c.files_changed)}")

        self.print_success("2 commit berhasil dibuat di branch feature.")
        return branch_name

    def run_step_2_open_pull_request(self, branch_name: str) -> PullRequest:
        self.print_header("Langkah 2: Membuka Pull Request (PR) ke 'main'")
        
        pr = PullRequest(
            id=101,
            title="feat(auth): implement JWT Authentication and Token Middleware",
            description=(
                "### Ringkasan Perubahan\n"
                "- Menambahkan modul JWT token generation & verification\n"
                "- Menambahkan middleware untuk memvalidasi token authorization header\n"
                "- Menambahkan 12 unit tests dengan coverage 94%"
            ),
            author="DevBudi",
            source_branch=branch_name,
            target_branch="main",
            commits=self.branches[branch_name][1:],  # Only feature commits
            ci_status={"lint": False, "unit-tests": False, "security-scan": False}
        )
        self.pull_requests.append(pr)

        print(f"{Color.BOLD}Pull Request #{pr.id}: {pr.title}{Color.RESET}")
        print(f"Author : {Color.CYAN}{pr.author}{Color.RESET}")
        print(f"Alur   : {Color.YELLOW}{pr.source_branch}{Color.RESET} ➔ {Color.GREEN}{pr.target_branch}{Color.RESET}")
        print(f"\n{Color.DIM}--- Deskripsi PR ---{Color.RESET}")
        for line in pr.description.split("\n"):
            print(f"  {line}")
        print(f"{Color.DIM}--------------------{Color.RESET}")

        self.print_success(f"PR #{pr.id} berhasil dibuka dan siap direview!")
        return pr

    def run_step_3_continuous_integration(self, pr: PullRequest):
        self.print_header("Langkah 3: Menjalankan CI Pipeline (Automated Checks)")
        checks = [
            ("Linter (Flake8 / Ruff)", "lint"),
            ("Unit & Integration Tests (pytest)", "unit-tests"),
            ("Dependency & Secret Scanner (Trufflehog/Bandit)", "security-scan"),
        ]

        for name, key in checks:
            print(f"  ⏳ Menjalankan {name}...", end="", flush=True)
            time.sleep(0.3)
            pr.ci_status[key] = True
            print(f" {Color.GREEN}[PASSED]{Color.RESET}")

        self.print_success("Seluruh status check CI berstatus HIJAU (Semua lolos).")

    def run_step_4_code_review_round_1(self, pr: PullRequest):
        self.print_header("Langkah 4: Code Review - Putaran 1 (Reviewer: SeniorDevSiti)")

        comment = ReviewComment(
            reviewer="SeniorDevSiti",
            file_name="auth/jwt_service.py",
            line_number=42,
            comment="Perhatian: Secret key di-hardcode ke string default fallback. Wajib gunakan environment variable!"
        )
        pr.comments.append(comment)
        pr.reviews["SeniorDevSiti"] = ReviewStatus.CHANGES_REQUESTED

        print(f"{Color.BOLD}Reviewer:{Color.RESET} {Color.YELLOW}SeniorDevSiti{Color.RESET}")
        print(f"  File : {Color.CYAN}{comment.file_name}:{comment.line_number}{Color.RESET}")
        print(f"  Catatan : {Color.RED}\"{comment.comment}\"{Color.RESET}")
        print(f"\nStatus Review: {Color.RED}{ReviewStatus.CHANGES_REQUESTED.value}{Color.RESET}")
        self.print_warning("PR diblokir dari merge karena 'Changes Requested'.")

    def run_step_5_author_iteration(self, pr: PullRequest):
        self.print_header("Langkah 5: Penulis Mengirim Perbaikan (Iteration Commit)")
        self.print_info("DevBudi membaca review dan memperbaiki penanganan env variable.")

        fix_commit = Commit(
            sha="33c990a",
            message="fix(auth): read secret key strictly from os.getenv and raise on missing",
            author="DevBudi",
            files_changed=["auth/jwt_service.py"]
        )
        self.branches[pr.source_branch].append(fix_commit)
        pr.commits.append(fix_commit)

        # Resolve comment
        for c in pr.comments:
            c.resolved = True

        print(f"  {Color.MAGENTA}[{fix_commit.sha}]{Color.RESET} {fix_commit.message}")
        self.print_success("Comment inline ditandai sebagai 'Resolved'.")

    def run_step_6_code_review_round_2(self, pr: PullRequest):
        self.print_header("Langkah 6: Re-review & Approval")
        self.print_info("SeniorDevSiti memeriksa kembali commit perbaikan.")
        
        pr.reviews["SeniorDevSiti"] = ReviewStatus.APPROVED
        print(f"Status Review SeniorDevSiti: {Color.GREEN}{ReviewStatus.APPROVED.value} ✔{Color.RESET}")
        print("Komentar: \"Implementasi rapi dan aman. LGTM (Looks Good To Me)!\"")
        self.print_success("Syarat approval minimum terpenuhi.")

    def run_step_7_branch_protection_audit(self, pr: PullRequest) -> bool:
        self.print_header("Langkah 7: Audit Branch Protection Rules 'main'")
        
        all_passed = True
        
        # Check CI
        ci_ok = all(pr.ci_status.values())
        print(f"  1. Required Status Checks (CI) : ", end="")
        if ci_ok:
            print(f"{Color.GREEN}PASSED (3/3){Color.RESET}")
        else:
            print(f"{Color.RED}FAILED{Color.RESET}")
            all_passed = False

        # Check Approvals
        approvals = sum(1 for status in pr.reviews.values() if status == ReviewStatus.APPROVED)
        print(f"  2. Required Pull Request Reviews : ", end="")
        if approvals >= self.protection_rules["min_approvals"]:
            print(f"{Color.GREEN}PASSED ({approvals} approval){Color.RESET}")
        else:
            print(f"{Color.RED}FAILED ({approvals}/{self.protection_rules['min_approvals']}){Color.RESET}")
            all_passed = False

        # Check Unresolved Conversations
        unresolved = [c for c in pr.comments if not c.resolved]
        print(f"  3. Conversations Resolved       : ", end="")
        if not unresolved:
            print(f"{Color.GREEN}PASSED (All threads resolved){Color.RESET}")
        else:
            print(f"{Color.RED}FAILED ({len(unresolved)} open discussions){Color.RESET}")
            all_passed = False

        if all_passed:
            self.print_success("Branch protection rules terpenuhi! Tombol 'Merge' aktif.")
        else:
            self.print_error("Merge diblokir oleh GitHub branch protection!")
        return all_passed

    def run_step_8_merge_and_cleanup(self, pr: PullRequest):
        self.print_header("Langkah 8: Memilih Strategi Merge & Membersihkan Branch")
        print("Pilih strategi merge yang disimulasikan:")
        strategies = [
            MergeStrategy.SQUASH,
            MergeStrategy.MERGE_COMMIT,
            MergeStrategy.REBASE,
        ]
        for idx, strat in enumerate(strategies, 1):
            print(f"  {idx}. {strat.name} ➔ {strat.value}")

        selected_strat = MergeStrategy.SQUASH
        print(f"\n{Color.CYAN}Menggunakan strategi rekomendasi: {Color.BOLD}{selected_strat.name}{Color.RESET}")
        print(f"{Color.DIM}Dampaknya: Menggabungkan 3 commit feature menjadi 1 commit rapi di branch 'main'.{Color.RESET}")

        # Simulate Squash & Merge
        squash_commit = Commit(
            sha="99e01ff",
            message=f"feat(auth): implement JWT Authentication and Token Middleware (#{pr.id})",
            author="DevBudi",
            files_changed=["auth/jwt_service.py", "requirements.txt", "tests/test_jwt_service.py"]
        )
        self.branches["main"].append(squash_commit)
        pr.is_merged = True
        pr.merge_commit_sha = squash_commit.sha

        self.print_success(f"PR #{pr.id} berhasil di-merge ke 'main' dengan commit [{squash_commit.sha}]!")

        # Housekeeping: Delete feature branch
        print(f"\n{Color.DIM}Housekeeping:{Color.RESET}")
        del self.branches[pr.source_branch]
        self.print_success(f"Branch remote '{pr.source_branch}' berhasil dihapus.")

    def print_final_git_log(self):
        self.print_header("Ringkasan Riwayat Git Log di Branch 'main'")
        for c in reversed(self.branches["main"]):
            print(f"{Color.YELLOW}commit {c.sha}{Color.RESET}")
            print(f"Author: {c.author}")
            print(f"    {c.message}\n")
        self.print_success("Lab exercise selesai dengan sempurna!")


def main():
    print(f"{Color.BOLD}{Color.MAGENTA}=== SIMULASI WORKFLOW PULL REQUEST & CODE REVIEW ==={Color.RESET}")
    print(f"{Color.DIM}Git & GitHub Foundations Lab - Bab 07{Color.RESET}\n")

    sim = GitSimEngine()
    branch = sim.run_step_1_create_branch_and_commits()
    pr = sim.run_step_2_open_pull_request(branch)
    sim.run_step_3_continuous_integration(pr)
    sim.run_step_4_code_review_round_1(pr)
    sim.run_step_5_author_iteration(pr)
    sim.run_step_6_code_review_round_2(pr)
    ready = sim.run_step_7_branch_protection_audit(pr)

    if ready:
        sim.run_step_8_merge_and_cleanup(pr)
        sim.print_final_git_log()
    else:
        sim.print_error("Simulasi gagal melewati branch protection rule.")


if __name__ == "__main__":
    main()
