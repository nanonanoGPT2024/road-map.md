#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Ekosistem GitHub - Pull Requests dan Issues
BAB-08: Ekosistem GitHub Pull Requests dan Issues
Platform: Python 3 runnable mandiri dengan visualisasi ANSI Terminal
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# --- ANSI Terminal Color Codes ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"


class IssueState(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PRState(Enum):
    OPEN = "OPEN"
    MERGED = "MERGED"
    CLOSED = "CLOSED"


class MergeStrategy(Enum):
    MERGE_COMMIT = "Create a merge commit (--no-ff)"
    SQUASH_MERGE = "Squash and merge"
    REBASE_MERGE = "Rebase and merge"


@dataclass
class Review:
    reviewer: str
    status: str  # "APPROVED", "CHANGES_REQUESTED", "COMMENTED"
    comment: str


@dataclass
class Issue:
    id: int
    title: str
    description: str
    labels: List[str]
    assignee: str
    state: IssueState = IssueState.OPEN
    closed_by_pr: Optional[int] = None


@dataclass
class PullRequest:
    id: int
    title: str
    source_branch: str
    target_branch: str
    author: str
    description: str
    linked_issues: List[int] = field(default_factory=list)
    state: PRState = PRState.OPEN
    reviews: List[Review] = field(default_factory=list)
    merge_strategy: Optional[MergeStrategy] = None


class GitHubSimulator:
    def __init__(self, repo_name: str = "belajar-git/ekosistem-collab"):
        self.repo_name = repo_name
        self.issues: Dict[int, Issue] = {}
        self.pull_requests: Dict[int, PullRequest] = {}
        self.branches: List[str] = ["main"]
        self.current_branch = "main"
        self.issue_counter = 1
        self.pr_counter = 1

    def banner(self):
        print(f"{Color.CYAN}{Color.BOLD}" + "=" * 70)
        print(f"   GITHUB SIMULATOR: PULL REQUESTS & ISSUES WORKFLOW ENGINE")
        print(f"   Repository: {self.repo_name}")
        print("=" * 70 + f"{Color.RESET}\n")

    def print_status(self, message: str, level: str = "INFO"):
        tag_color = {
            "INFO": Color.BLUE,
            "SUCCESS": Color.GREEN,
            "WARNING": Color.YELLOW,
            "ERROR": Color.RED,
            "GIT": Color.MAGENTA,
        }.get(level, Color.WHITE)
        print(f"{tag_color}[{level}]{Color.RESET} {message}")

    def create_issue(self, title: str, description: str, labels: List[str], assignee: str) -> Issue:
        issue_id = self.issue_counter
        self.issue_counter += 1
        issue = Issue(id=issue_id, title=title, description=description, labels=labels, assignee=assignee)
        self.issues[issue_id] = issue
        self.print_status(
            f"Issue #{issue_id} dibuat: {Color.BOLD}'{title}'{Color.RESET} | Assignee: @{assignee} | Labels: {labels}",
            "SUCCESS"
        )
        return issue

    def checkout_branch(self, branch_name: str):
        if branch_name not in self.branches:
            self.branches.append(branch_name)
        self.current_branch = branch_name
        self.print_status(f"Beralih ke branch baru: {Color.YELLOW}{branch_name}{Color.RESET}", "GIT")

    def create_pull_request(self, title: str, source_branch: str, target_branch: str, author: str, description: str) -> PullRequest:
        pr_id = self.pr_counter
        self.pr_counter += 1

        # Deteksi auto-closing keyword GitHub (e.g. Closes #1, Fixes #1, Resolves #1)
        linked = []
        for word in description.split():
            clean_word = word.strip().rstrip(".,;:()")
            if clean_word.startswith("#") and clean_word[1:].isdigit():
                issue_num = int(clean_word[1:])
                if issue_num in self.issues:
                    linked.append(issue_num)

        pr = PullRequest(
            id=pr_id,
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            author=author,
            description=description,
            linked_issues=linked
        )
        self.pull_requests[pr_id] = pr
        self.print_status(
            f"Pull Request #{pr_id} dibuka: {Color.BOLD}'{title}'{Color.RESET} ({source_branch} -> {target_branch})",
            "SUCCESS"
        )
        if linked:
            self.print_status(f"  └─ Link Otomatis ke Issue: {', '.join(f'#{i}' for i in linked)}", "INFO")
        return pr

    def submit_review(self, pr_id: int, reviewer: str, status: str, comment: str):
        if pr_id not in self.pull_requests:
            self.print_status(f"PR #{pr_id} tidak ditemukan!", "ERROR")
            return
        pr = self.pull_requests[pr_id]
        review = Review(reviewer=reviewer, status=status, comment=comment)
        pr.reviews.append(review)
        status_color = Color.GREEN if status == "APPROVED" else Color.RED
        print(f"\n{Color.BOLD}--- Review Masuk untuk PR #{pr_id} ---{Color.RESET}")
        print(f"Reviewer : @{reviewer}")
        print(f"Keputusan: {status_color}{status}{Color.RESET}")
        print(f"Komentar : {Color.DIM}\"{comment}\"{Color.RESET}")

    def merge_pull_request(self, pr_id: int, strategy: MergeStrategy) -> bool:
        pr = self.pull_requests.get(pr_id)
        if not pr:
            self.print_status(f"PR #{pr_id} tidak ditemukan.", "ERROR")
            return False

        if pr.state != PRState.OPEN:
            self.print_status(f"PR #{pr_id} sudah dalam status {pr.state.value}!", "WARNING")
            return False

        # Validasi apakah ada approval
        has_approval = any(r.status == "APPROVED" for r in pr.reviews)
        if not has_approval:
            self.print_status(f"Gagal Merge: PR #{pr_id} belum memiliki review APPROVED.", "ERROR")
            return False

        pr.state = PRState.MERGED
        pr.merge_strategy = strategy
        self.print_status(
            f"PR #{pr_id} berhasil di-MERGE ke '{pr.target_branch}' menggunakan strategi '{strategy.value}'.",
            "SUCCESS"
        )

        # Proses penutupan issue otomatis
        for issue_id in pr.linked_issues:
            issue = self.issues.get(issue_id)
            if issue and issue.state == IssueState.OPEN:
                issue.state = IssueState.CLOSED
                issue.closed_by_pr = pr_id
                self.print_status(
                    f"  └─ Issue #{issue_id} ('{issue.title}') otomatis DITUTUP oleh PR #{pr_id}!",
                    "SUCCESS"
                )
        return True

    def display_board(self):
        print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} GITHUB REPOSITORY BOARD SUMMARY {Color.RESET}")
        print(f"{Color.CYAN}--- ISSUES ({len(self.issues)}) ---{Color.RESET}")
        for i_id, issue in self.issues.items():
            state_color = Color.GREEN if issue.state == IssueState.OPEN else Color.RED
            status_text = f"[{issue.state.value}]"
            labels_str = f"[{', '.join(issue.labels)}]" if issue.labels else ""
            closed_info = f" (Closed by PR #{issue.closed_by_pr})" if issue.closed_by_pr else ""
            print(f"  #{issue.id:02d} {state_color}{status_text:<8}{Color.RESET} {issue.title:<35} @{issue.assignee:<10} {Color.YELLOW}{labels_str}{Color.RESET}{closed_info}")

        print(f"\n{Color.CYAN}--- PULL REQUESTS ({len(self.pull_requests)}) ---{Color.RESET}")
        for p_id, pr in self.pull_requests.items():
            state_color = Color.MAGENTA if pr.state == PRState.MERGED else (Color.GREEN if pr.state == PRState.OPEN else Color.RED)
            strat = f"via {pr.merge_strategy.name}" if pr.merge_strategy else ""
            print(f"  #{pr.id:02d} {state_color}[{pr.state.value:<6}]{Color.RESET} {pr.title:<35} {pr.source_branch} -> {pr.target_branch} {strat}")
            for r in pr.reviews:
                rev_c = Color.GREEN if r.status == "APPROVED" else Color.RED
                print(f"      └─ Review by @{r.reviewer}: {rev_c}{r.status}{Color.RESET}")
        print("-" * 70 + "\n")


def run_interactive_simulation():
    sim = GitHubSimulator()
    sim.banner()

    print(f"{Color.BOLD}Skenario Hands-on:{Color.RESET}")
    print("Tim Anda menemukan bug pada sistem otentikasi. Anda akan mempraktikkan siklus:")
    print("1. Membuat Issue Bug")
    print("2. Membuat Feature/Fix Branch & Commit")
    print("3. Mengajukan Pull Request dengan kata kunci penutup otomatis")
    print("4. Melakukan Peer Code Review")
    print("5. Menjalankan Merge Strategy & Penutupan Issue Otomatis\n")

    time.sleep(1)

    # Langkah 1: Issue
    sim.print_status("Langkah 1: Membuat Issue pelaporan bug otentikasi...", "INFO")
    issue = sim.create_issue(
        title="Fix Null Pointer Exception saat login OAuth Google",
        description="Pengguna mengalami error 500 jika avatar URL bernilai null saat callback.",
        labels=["bug", "high-priority", "auth"],
        assignee="octocat-engineer"
    )
    time.sleep(0.8)

    # Langkah 2: Branching
    sim.print_status("\nLangkah 2: Engineer membuat branch baru dan push commit...", "INFO")
    feature_branch = "fix/issue-1-oauth-npe"
    sim.checkout_branch(feature_branch)
    sim.print_status("git commit -m 'fix: sanitize null avatar URL on oauth payload'", "GIT")
    sim.print_status(f"git push -u origin {feature_branch}", "GIT")
    time.sleep(0.8)

    # Langkah 3: Pull Request
    sim.print_status("\nLangkah 3: Membuka Pull Request terhubung...", "INFO")
    pr_desc = (
        "## Perubahan:\n"
        "- Menambahkan default fallback image jika profile.picture kosong.\n"
        "- Unit test verifikasi login callback.\n\n"
        "Closes #1"
    )
    pr = sim.create_pull_request(
        title="Fix(auth): handle null avatar URL gracefully in OAuth callback",
        source_branch=feature_branch,
        target_branch="main",
        author="octocat-engineer",
        description=pr_desc
    )
    time.sleep(0.8)

    # Langkah 4: Peer Review
    sim.print_status("\nLangkah 4: Melakukan Code Review oleh Tech Lead...", "INFO")
    sim.submit_review(
        pr_id=pr.id,
        reviewer="lead-maintainer",
        status="APPROVED",
        comment="LGTM! Penanganan fallback aman dan unit test mencakup edge cases."
    )
    time.sleep(0.8)

    # Langkah 5: Pilih Merge Strategy
    sim.print_status("\nLangkah 5: Memilih Strategi Merge...", "INFO")
    print(f"Opsi Strategi Merge di GitHub:")
    print(f"  1. {MergeStrategy.MERGE_COMMIT.value}")
    print(f"  2. {MergeStrategy.SQUASH_MERGE.value} (Rekomendasi untuk kebersihan branch main)")
    print(f"  3. {MergeStrategy.REBASE_MERGE.value}")

    # Otomatis memilih Squash & Merge untuk demonstrasi lab terbaik
    selected_strategy = MergeStrategy.SQUASH_MERGE
    sim.print_status(f"Strategi terpilih: {Color.BOLD}{selected_strategy.value}{Color.RESET}", "INFO")
    sim.merge_pull_request(pr.id, selected_strategy)
    time.sleep(0.8)

    # Ringkasan Akhir
    sim.display_board()
    print(f"{Color.GREEN}{Color.BOLD}✔ Simulasi Siklus Lengkap GitHub PR & Issues Selesai!{Color.RESET}\n")


if __name__ == "__main__":
    run_interactive_simulation()
