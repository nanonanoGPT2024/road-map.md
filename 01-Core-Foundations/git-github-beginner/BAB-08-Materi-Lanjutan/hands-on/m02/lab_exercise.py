#!/usr/bin/env python3
"""
Lab Hands-on: Ekosistem GitHub - Pull Requests, Issues, & Project Governance Engine.
Simulasi teknis arsitektur GitHub: Branch Protection Rules, CODEOWNERS Evaluation,
Issue Lifecycle Automation (Closes/Fixes), dan Pull Request Merge Gatekeeper.
"""

from dataclasses import dataclass, field
from enum import Enum
import fnmatch
import hashlib
import re
import sys
import time
from typing import Dict, List, Optional, Set

# Terminal ANSI Styling
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"


class IssueState(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ReviewState(Enum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"


class MergeMethod(Enum):
    MERGE_COMMIT = "MERGE_COMMIT"
    SQUASH = "SQUASH"
    REBASE = "REBASE"


@dataclass
class Issue:
    id: int
    title: str
    author: str
    state: IssueState = IssueState.OPEN
    closed_by_pr: Optional[int] = None


@dataclass
class CodeOwnerRule:
    pattern: str
    owners: Set[str]


@dataclass
class Review:
    reviewer: str
    state: ReviewState
    timestamp: float = field(default_factory=time.time)


@dataclass
class PullRequest:
    id: int
    title: str
    description: str
    author: str
    base_branch: str
    head_branch: str
    changed_files: List[str]
    reviews: Dict[str, Review] = field(default_factory=dict)
    ci_checks_passed: bool = False
    merged: bool = False
    merge_commit_sha: Optional[str] = None


class BranchProtectionPolicy:
    """Mendefinisikan aturan tata kelola (governance) repositori pada branch sensitif."""

    def __init__(
        self,
        required_approvals: int = 2,
        require_codeowner_review: bool = True,
        require_ci_pass: bool = True,
        enforce_linear_history: bool = True,
    ):
        self.required_approvals = required_approvals
        self.require_codeowner_review = require_codeowner_review
        self.require_ci_pass = require_ci_pass
        self.enforce_linear_history = enforce_linear_history


class GovernanceEngine:
    """Mesin evaluasi kepatuhan tata kelola branch, issue parsing, dan merge verification."""

    def __init__(self):
        self.issues: Dict[int, Issue] = {}
        self.pull_requests: Dict[int, PullRequest] = {}
        self.codeowners: List[CodeOwnerRule] = []
        self.branch_policies: Dict[str, BranchProtectionPolicy] = {}
        self.issue_close_regex = re.compile(
            r"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+#(\d+)",
            re.IGNORECASE,
        )

    def load_codeowners(self, codeowners_content: str) -> None:
        """Mem-parsing sintaks standard file CODEOWNERS."""
        self.codeowners.clear()
        for line in codeowners_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            pattern = parts[0]
            owners = set(parts[1:])
            self.codeowners.append(CodeOwnerRule(pattern=pattern, owners=owners))

    def resolve_codeowners(self, file_path: str) -> Set[str]:
        """Menentukan pemilik kode berdasarkan precedence urutan terbawah file CODEOWNERS."""
        matched_owners: Set[str] = set()
        for rule in self.codeowners:
            # Menggunakan fnmatch untuk memetakan path globbing
            if fnmatch.fnmatch(file_path, rule.pattern) or fnmatch.fnmatch(
                file_path, f"*/{rule.pattern}"
            ):
                matched_owners = rule.owners
        return matched_owners

    def get_pr_required_codeowners(self, pr: PullRequest) -> Set[str]:
        """Mengumpulkan semua CODEOWNERS yang wajib mereview berdasarkan daftar modifikasi file."""
        required = set()
        for file in pr.changed_files:
            owners = self.resolve_codeowners(file)
            required.update(owners)
        return required

    def evaluate_merge_eligibility(
        self, pr_id: int
    ) -> (bool, List[str]):
        """Memverifikasi pemenuhan seluruh policy protection rules."""
        pr = self.pull_requests.get(pr_id)
        if not pr:
            return False, ["PR tidak ditemukan."]

        policy = self.branch_policies.get(pr.base_branch)
        if not policy:
            return True, ["Tidak ada branch protection policy."]

        violations = []

        # 1. CI Status Checks
        if policy.require_ci_pass and not pr.ci_checks_passed:
            violations.append("CI/CD pipeline status check belum sukses/lulus.")

        # 2. Review Counts & Changes Requested
        approved_reviews = [
            r for r in pr.reviews.values() if r.state == ReviewState.APPROVED
        ]
        blocking_reviews = [
            r
            for r in pr.reviews.values()
            if r.state == ReviewState.CHANGES_REQUESTED
        ]

        if blocking_reviews:
            blockers = ", ".join(r.reviewer for r in blocking_reviews)
            violations.append(f"Perubahan diminta oleh: {blockers}")

        if len(approved_reviews) < policy.required_approvals:
            violations.append(
                f"Kurang persetujuan: Butuh {policy.required_approvals}, "
                f"baru menerima {len(approved_reviews)}."
            )

        # 3. CODEOWNERS Review Requirement
        if policy.require_codeowner_review:
            required_codeowners = self.get_pr_required_codeowners(pr)
            approvers = {
                r.reviewer
                for r in pr.reviews.values()
                if r.state == ReviewState.APPROVED
            }
            missing_owners = required_codeowners - approvers
            if missing_owners:
                violations.append(
                    f"Belum disetujui CODEOWNERS yang bersangkutan: {', '.join(missing_owners)}"
                )

        return len(violations) == 0, violations

    def merge_pull_request(
        self, pr_id: int, merger: str, method: MergeMethod
    ) -> bool:
        """Mengeksekusi merge secara atomik dan menutup issue terkait otomatis via commit regex."""
        pr = self.pull_requests.get(pr_id)
        if not pr or pr.merged:
            print(f"{RED}[FAIL] PR #{pr_id} tidak valid atau sudah dimerge.{RESET}")
            return False

        eligible, violations = self.evaluate_merge_eligibility(pr_id)
        if not eligible:
            print(f"{RED}[REJECTED] PR #{pr_id} ditolak oleh Governance Engine:{RESET}")
            for v in violations:
                print(f"  {YELLOW}• {v}{RESET}")
            return False

        # Generate mock Git SHA
        payload = f"{pr.base_branch}:{pr.head_branch}:{time.time()}:{merger}"
        pr.merge_commit_sha = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]
        pr.merged = True

        print(
            f"{GREEN}[MERGED] PR #{pr.id} berhasil digabungkan via {method.value} "
            f"oleh {merger} (Commit: {pr.merge_commit_sha}){RESET}"
        )

        # Linked Issue Automation Resolution
        full_text = f"{pr.title}\n{pr.description}"
        linked_issues = self.issue_close_regex.findall(full_text)
        for issue_id_str in linked_issues:
            issue_id = int(issue_id_str)
            if issue_id in self.issues:
                issue = self.issues[issue_id]
                issue.state = IssueState.CLOSED
                issue.closed_by_pr = pr.id
                print(
                    f"  {MAGENTA}↳ Issue #{issue.id} ('{issue.title}') otomatis DITUTUP via PR #{pr.id}{RESET}"
                )

        return True


def run_governance_lab():
    print(f"{BOLD}{CYAN}=== LAB: GITHUB GOVERNANCE, PULL REQUESTS & ISSUES ENGINE ==={RESET}\n")
    engine = GovernanceEngine()

    # 1. Konfigurasi Branch Protection
    print(f"{BOLD}1. Menetapkan Branch Protection Policy untuk 'main'...{RESET}")
    engine.branch_policies["main"] = BranchProtectionPolicy(
        required_approvals=2,
        require_codeowner_review=True,
        require_ci_pass=True,
    )
    print("   Aturan aktif: Min 2 Approval, CODEOWNERS Wajib, CI Success Wajib.\n")

    # 2. Parsing File CODEOWNERS
    raw_codeowners = """
    # Security and Core infrastructure
    auth/*       @sec-team @alice
    database/*   @db-lead
    *            @core-team
    """
    print(f"{BOLD}2. Mem-parsing Dokumen CODEOWNERS:{RESET}")
    engine.load_codeowners(raw_codeowners)
    for rule in engine.codeowners:
        print(f"   Pattern: {rule.pattern:<12} Owners: {rule.owners}")
    print()

    # 3. Pembuatan Issue Tracker
    print(f"{BOLD}3. Registrasi Masalah (Issues):{RESET}")
    engine.issues[42] = Issue(id=42, title="CVE-2023: Vulnerability in auth tokens", author="david")
    print(f"   Issue #{engine.issues[42].id} dibuat: '{engine.issues[42].title}' [Status: {engine.issues[42].state.value}]\n")

    # 4. Pembuatan Pull Request yang menargetkan penyelesaian issue
    print(f"{BOLD}4. Mengajukan Pull Request #101...{RESET}")
    pr = PullRequest(
        id=101,
        title="Refactor token validation logic",
        description="Pembersihan celah keamanan otentikasi token. Fixes #42",
        author="bob",
        base_branch="main",
        head_branch="patch-auth-fix",
        changed_files=["auth/token_verifier.py", "auth/jwt.py"],
    )
    engine.pull_requests[pr.id] = pr
    required_owners = engine.get_pr_required_codeowners(pr)
    print(f"   PR #{pr.id} diajukan dari '{pr.head_branch}' -> '{pr.base_branch}'")
    print(f"   File terikat: {pr.changed_files}")
    print(f"   CODEOWNERS yang wajib mereview: {required_owners}\n")

    # 5. Uji Coba Penggabungan Prematur (Tanpa CI dan Review)
    print(f"{BOLD}5. Evaluasi Pertama: Upaya Merge Tanpa Review/CI...{RESET}")
    engine.merge_pull_request(pr.id, merger="charlie", method=MergeMethod.SQUASH)
    print()

    # 6. Pemenuhan Tahap CI dan Review Parsial
    print(f"{BOLD}6. Eksekusi Test Runner & Non-CodeOwner Review...{RESET}")
    pr.ci_checks_passed = True
    print(f"   {GREEN}✓ CI/CD Pipeline Build: SUCCESSFUL{RESET}")

    pr.reviews["charlie"] = Review(reviewer="charlie", state=ReviewState.APPROVED)
    print(f"   Review diserahkan: charlie -> {ReviewState.APPROVED.value}")

    print("   Upaya merge ulang:")
    engine.merge_pull_request(pr.id, merger="charlie", method=MergeMethod.SQUASH)
    print()

    # 7. Pemenuhan CodeOwner Approval
    print(f"{BOLD}7. Meminta Persetujuan CODEOWNER (@alice)...{RESET}")
    pr.reviews["@alice"] = Review(reviewer="@alice", state=ReviewState.APPROVED)
    print(f"   Review diserahkan: @alice -> {ReviewState.APPROVED.value}")

    print("   Evaluasi kelayakan akhir dan eksekusi Merge:")
    success = engine.merge_pull_request(pr.id, merger="bob", method=MergeMethod.SQUASH)
    print()

    # 8. Post-condition Verification
    print(f"{BOLD}8. Verifikasi Status Akhir Repositori:{RESET}")
    print(f"   PR #{pr.id} Merged: {pr.merged} (Commit SHA: {pr.merge_commit_sha})")
    print(f"   Issue #42 State: {engine.issues[42].state.value} (Closed by PR #{engine.issues[42].closed_by_pr})")
    print(f"\n{BOLD}{GREEN}=== SIMULASI GOVERNANCE WORKFLOW SELESAI DENGAN SUKSES ==={RESET}")


if __name__ == "__main__":
    run_governance_lab()