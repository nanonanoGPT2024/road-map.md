#!/usr/bin/env python3
"""
Lab Hands-on: Pull Request Workflows & Code Review Mechanics
Modul: 07 - Core Foundations (Git & GitHub Deep Dive)

Deskripsi:
Script ini memodelkan mesin siklus hidup Pull Request (PR) modern setingkat GitHub/GitLab.
Mencakup:
  1. DAG Commit Git, percabangan, dan identifikasi titik temu (Merge-Base).
  2. Komputasi delta file (Unified Diff) menggunakan modul `difflib`.
  3. Evaluasi Branch Protection Rules (Required Approvals, Stale Review Dismissal, CI Status Checks).
  4. Simulasi Code Review threads (Approval vs Changes Requested).
  5. Deteksi konflik penggabungan 3-arah (Three-Way Merge Conflict Detection).
  6. Eksekusi penggabungan (Squash & Merge vs 3-Way Merge Commit).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import difflib
import hashlib
import json
import sys
import time
from typing import Dict, List, Optional, Set, Tuple


# ============================================================================
# ANSI Terminal Styler
# ============================================================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


# ============================================================================
# Git Primitives (Commit, Tree, DAG)
# ============================================================================
@dataclass
class Commit:
    commit_id: str
    parents: List[str]
    message: str
    tree: Dict[str, str]  # Path file -> Konten file
    author: str
    timestamp: float = field(default_factory=time.time)


def hash_object(content: str) -> str:
    """Menghitung SHA-1 hash representatif dari konten git object."""
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:8]


class GitRepository:
    """Simulasi bare-bones object storage Git dan navigasi branch."""
    def __init__(self):
        self.commits: Dict[str, Commit] = {}
        self.branches: Dict[str, str] = {}  # branch_name -> commit_id

    def create_commit(self, parent_ids: List[str], message: str, tree: Dict[str, str], author: str) -> str:
        serialized = json.dumps(tree, sort_keys=True) + message + "".join(parent_ids)
        cid = hash_object(serialized)
        commit = Commit(commit_id=cid, parents=parent_ids, message=message, tree=tree.copy(), author=author)
        self.commits[cid] = commit
        return cid

    def find_merge_base(self, commit_a_id: str, commit_b_id: str) -> Optional[str]:
        """Menemukan common ancestor terakhir antara dua branch menggunakan BFS transversal."""
        def get_ancestors(start_id: str) -> Set[str]:
            visited = set()
            queue = [start_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                if current in self.commits:
                    queue.extend(self.commits[current].parents)
            return visited

        ancestors_a = get_ancestors(commit_a_id)
        queue = [commit_b_id]
        visited_b = set()

        while queue:
            current = queue.pop(0)
            if current in ancestors_a:
                return current
            if current in visited_b:
                continue
            visited_b.add(current)
            if current in self.commits:
                queue.extend(self.commits[current].parents)
        return None


# ============================================================================
# Pull Request & Review Domain Model
# ============================================================================
class ReviewState(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"


class CheckStatus(Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


@dataclass
class Review:
    reviewer: str
    state: ReviewState
    body: str
    submitted_at: float = field(default_factory=time.time)


@dataclass
class CIStatusCheck:
    context: str
    status: CheckStatus
    description: str


class PullRequest:
    """Model PR yang merepresentasikan State Machine GitHub PR."""
    def __init__(self, pr_id: int, title: str, base_branch: str, head_branch: str, author: str):
        self.pr_id = pr_id
        self.title = title
        self.base_branch = base_branch
        self.head_branch = head_branch
        self.author = author
        self.reviews: Dict[str, Review] = {}
        self.checks: Dict[str, CIStatusCheck] = {}
        self.is_closed: bool = False
        self.is_merged: bool = False

    def add_review(self, reviewer: str, state: ReviewState, body: str):
        self.reviews[reviewer] = Review(reviewer, state, body)

    def set_check(self, context: str, status: CheckStatus, desc: str):
        self.checks[context] = CIStatusCheck(context, status, desc)


# ============================================================================
# Branch Protection & Engine Logic
# ============================================================================
class BranchProtectionPolicy:
    """Menerapkan aturan guard rails sebelum merge diizinkan."""
    def __init__(self, required_approvals: int = 1, required_checks: List[str] = None):
        self.required_approvals = required_approvals
        self.required_checks = required_checks or []

    def evaluate(self, pr: PullRequest) -> Tuple[bool, List[str]]:
        violations = []

        # 1. Validasi Status Checks
        for req_check in self.required_checks:
            check = pr.checks.get(req_check)
            if not check:
                violations.append(f"Required status check '{req_check}' missing/not executed.")
            elif check.status != CheckStatus.SUCCESS:
                violations.append(f"Required status check '{req_check}' failed: {check.description}")

        # 2. Validasi Review Blockers (Changes Requested memiliki prioritas absolut)
        changes_requested = [r.reviewer for r in pr.reviews.values() if r.state == ReviewState.CHANGES_REQUESTED]
        if changes_requested:
            violations.append(f"Blocker: Changes requested by: {', '.join(changes_requested)}.")

        # 3. Validasi Approvals Count
        approvals = [r.reviewer for r in pr.reviews.values() if r.state == ReviewState.APPROVED]
        if len(approvals) < self.required_approvals:
            violations.append(
                f"Insufficient approvals: {len(approvals)}/{self.required_approvals} (Approved by: {approvals})"
            )

        can_merge = len(violations) == 0
        return can_merge, violations


# ============================================================================
# Diff & Merge Mechanics
# ============================================================================
def generate_diff(tree_base: Dict[str, str], tree_head: Dict[str, str]) -> str:
    """Menghitung patch unified diff antara dua state tree."""
    diff_output = []
    all_files = sorted(set(tree_base.keys()) | set(tree_head.keys()))

    for file_path in all_files:
        base_lines = tree_base.get(file_path, "").splitlines(keepends=True)
        head_lines = tree_head.get(file_path, "").splitlines(keepends=True)

        if base_lines != head_lines:
            diff = difflib.unified_diff(
                base_lines, head_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}"
            )
            for line in diff:
                if line.startswith('+') and not line.startswith('+++'):
                    diff_output.append(f"{Style.GREEN}{line.rstrip()}{Style.RESET}")
                elif line.startswith('-') and not line.startswith('---'):
                    diff_output.append(f"{Style.RED}{line.rstrip()}{Style.RESET}")
                elif line.startswith('@@'):
                    diff_output.append(f"{Style.CYAN}{line.rstrip()}{Style.RESET}")
                else:
                    diff_output.append(f"{Style.DIM}{line.rstrip()}{Style.RESET}")
    return "\n".join(diff_output)


def three_way_merge(base_tree: Dict[str, str],
                    target_tree: Dict[str, str],
                    incoming_tree: Dict[str, str]) -> Tuple[bool, Dict[str, str], List[str]]:
    """
    Melakukan 3-way reconciliation algoritmis.
    Mendeteksi bila modifikasi konkuren terjadi pada baris/file yang sama.
    """
    merged_tree = {}
    conflicts = []
    all_files = sorted(set(base_tree.keys()) | set(target_tree.keys()) | set(incoming_tree.keys()))

    for f in all_files:
        b = base_tree.get(f, "")
        t = target_tree.get(f, "")
        i = incoming_tree.get(f, "")

        if t == i:
            # Tidak ada perbedaan antar target dan incoming
            if t != "":
                merged_tree[f] = t
        elif t == b:
            # Target tidak menyentuh file, ambil perubahan incoming
            if i != "":
                merged_tree[f] = i
        elif i == b:
            # Incoming tidak menyentuh file, pertahankan target
            if t != "":
                merged_tree[f] = t
        else:
            # Kedua branch mengubah file yang sama relatif terhadap base
            if t != i:
                conflicts.append(f)
                # Tandai conflict marker di tree
                merged_tree[f] = f"<<<<<<< HEAD (Target)\n{t}\n=======\n{i}\n>>>>>>> INCOMING\n"
            else:
                merged_tree[f] = t

    return len(conflicts) == 0, merged_tree, conflicts


# ============================================================================
# Main Simulation Flow
# ============================================================================
def main():
    print(f"{Style.BOLD}{Style.CYAN}=== LAB: SIMULASI PR WORKFLOW & CODE REVIEW MECHANICS ==={Style.RESET}\n")

    repo = GitRepository()

    # 1. Baseline Initial Commit di branch `main`
    initial_tree = {
        "auth.py": "def authenticate(user, password):\n    # Basic mock check\n    return user == 'admin' and password == 'secret'\n",
        "config.json": '{\n  "version": "1.0.0",\n  "env": "production"\n}\n'
    }
    c_base = repo.create_commit([], "feat: Initial commit infrastructure", initial_tree, "devops@corp.internal")
    repo.branches["main"] = c_base
    print(f"[*] Repositori diinisialisasi. Branch '{Style.BOLD}main{Style.RESET}' at commit {c_base}")

    # 2. Developer membuat Feature Branch dan submit perubahan
    repo.branches["feature/jwt-auth"] = c_base
    print(f"[*] Percabangan '{Style.BOLD}feature/jwt-auth{Style.RESET}' dibuat dari {c_base}")

    feature_tree = initial_tree.copy()
    feature_tree["auth.py"] = (
        "import jwt\n"
        "def authenticate(token):\n"
        "    # Decode JWT Bearer token securely\n"
        "    return jwt.decode(token, 'SECRET_KEY_PROD', algorithms=['HS256'])\n"
    )
    c_feat = repo.create_commit([c_base], "feat(auth): Upgrade to JWT authentication protocol", feature_tree, "alice@corp.internal")
    repo.branches["feature/jwt-auth"] = c_feat
    print(f"[*] Developer (Alice) melakukan commit {c_feat} ke 'feature/jwt-auth'")

    # 3. Inisiasi PR
    pr = PullRequest(
        pr_id=142,
        title="Upgrade legacy authentication layer to JWT tokens",
        base_branch="main",
        head_branch="feature/jwt-auth",
        author="alice@corp.internal"
    )
    print(f"\n{Style.BOLD}{Style.YELLOW}>>> PR #{pr.pr_id} Dibuka: '{pr.title}' [{pr.head_branch} -> {pr.base_branch}]{Style.RESET}")

    # Visualisasi Diff
    print(f"\n{Style.BOLD}--- Unified Code Diff (Base vs Head) ---{Style.RESET}")
    merge_base = repo.find_merge_base(repo.branches[pr.base_branch], repo.branches[pr.head_branch])
    diff_text = generate_diff(repo.commits[merge_base].tree, repo.commits[pr.head_branch].tree)
    print(diff_text)

    # 4. Automasi Status Checks (CI Pipelines)
    print(f"\n{Style.BOLD}--- Menjalankan Automated CI Checks ---{Style.RESET}")
    pr.set_check("ci/unit-tests", CheckStatus.SUCCESS, "All 42 test suites passed successfully.")
    pr.set_check("ci/security-linter", CheckStatus.FAILURE, "Hardcoded secret detected: 'SECRET_KEY_PROD'")
    for ctx, chk in pr.checks.items():
        color = Style.GREEN if chk.status == CheckStatus.SUCCESS else Style.RED
        print(f"  [{color}{chk.status.value:<7}{Style.RESET}] {ctx}: {chk.description}")

    # 5. Peer Code Review Mechanics
    print(f"\n{Style.BOLD}--- Peer Code Review Evaluation ---{Style.RESET}")
    pr.add_review("bob_senior_dev", ReviewState.CHANGES_REQUESTED, "Hardcoded production key is forbidden! Inject via os.getenv().")
    print(f"  {Style.RED}[CHANGES_REQUESTED]{Style.RESET} bob_senior_dev: '{pr.reviews['bob_senior_dev'].body}'")

    # Evaluasi Guard-Rails (Protection Policy)
    policy = BranchProtectionPolicy(
        required_approvals=2,
        required_checks=["ci/unit-tests", "ci/security-linter"]
    )
    can_merge, violations = policy.evaluate(pr)
    print(f"\n{Style.BOLD}Evaluasi Branch Policy Status:{Style.RESET} Can Merge = {Style.RED if not can_merge else Style.GREEN}{can_merge}{Style.RESET}")
    for idx, v in enumerate(violations, 1):
        print(f"  {idx}. {Style.RED}{v}{Style.RESET}")

    # 6. Author melakukan Remediasi (Push Commit Baru ke Feature Branch)
    print(f"\n{Style.BOLD}--- Remediasi & Iterasi Review ---{Style.RESET}")
    print("[*] Alice memperbaiki security leak dan mem-push commit baru...")
    fixed_tree = feature_tree.copy()
    fixed_tree["auth.py"] = (
        "import os\n"
        "import jwt\n"
        "def authenticate(token):\n"
        "    # Decoupled secret key reading\n"
        "    secret = os.getenv('JWT_SECRET_KEY')\n"
        "    return jwt.decode(token, secret, algorithms=['HS256'])\n"
    )
    c_fixed = repo.create_commit([c_feat], "fix(security): Load secret from environment variables", fixed_tree, "alice@corp.internal")
    repo.branches["feature/jwt-auth"] = c_fixed
    print(f"[*] Feature branch dimutakhirkan ke commit {c_fixed}")

    # CI Rerun & Reviewer Approval
    pr.set_check("ci/security-linter", CheckStatus.SUCCESS, "Static secret audit clean.")
    pr.add_review("bob_senior_dev", ReviewState.APPROVED, "Fix verified. LGTM!")
    pr.add_review("carol_secops", ReviewState.APPROVED, "Security compliance sign-off granted.")
    print("  [CI RERUN] ci/security-linter: SUCCESS")
    print(f"  {Style.GREEN}[APPROVED]{Style.RESET} bob_senior_dev: '{pr.reviews['bob_senior_dev'].body}'")
    print(f"  {Style.GREEN}[APPROVED]{Style.RESET} carol_secops: '{pr.reviews['carol_secops'].body}'")

    can_merge, violations = policy.evaluate(pr)
    print(f"\n{Style.BOLD}Evaluasi Ulang Branch Policy Status:{Style.RESET} Can Merge = {Style.GREEN}{can_merge}{Style.RESET}")

    # 7. Merge Execution
    if can_merge:
        print(f"\n{Style.BOLD}--- Eksekusi Three-Way Merge Engine ---{Style.RESET}")
        base_commit = repo.commits[repo.branches[pr.base_branch]]
        incoming_commit = repo.commits[repo.branches[pr.head_branch]]
        ancestor_commit = repo.commits[merge_base]

        clean_merge, result_tree, conflicts = three_way_merge(
            ancestor_commit.tree,
            base_commit.tree,
            incoming_commit.tree
        )

        if clean_merge:
            merge_msg = f"Merge pull request #{pr.pr_id} from {pr.head_branch}\n\n* {pr.title}"
            merge_commit_id = repo.create_commit(
                parent_ids=[base_commit.commit_id, incoming_commit.commit_id],
                message=merge_msg,
                tree=result_tree,
                author="merge-bot@corp.internal"
            )
            repo.branches[pr.base_branch] = merge_commit_id
            pr.is_merged = True
            print(f"{Style.GREEN}{Style.BOLD}✔ PR Berhasil di-Merge!{Style.RESET}")
            print(f"  Merge Commit Hash : {Style.CYAN}{merge_commit_id}{Style.RESET}")
            print(f"  Parents            : {repo.commits[merge_commit_id].parents}")
            print(f"  Branch 'main' Pointer -> {merge_commit_id}")
            print(f"\n{Style.BOLD}Final Content in 'auth.py':{Style.RESET}")
            print(f"{Style.DIM}{result_tree['auth.py']}{Style.RESET}")
        else:
            print(f"{Style.RED}Merge Conflict Terdeteksi pada file: {conflicts}{Style.RESET}")


if __name__ == "__main__":
    main()