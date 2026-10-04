#!/usr/bin/env python3
"""
Lab Exercise: Simulasi GitHub Platform Engineering & Enterprise Governance
BAB-06: GitHub Platform Engineering dan Governance

Topik Simulasi:
1. Enterprise Repository Rulesets (Targeted Enforcement, Signed Commits, Linear History)
2. Secret Scanning Push Protection Gatekeeper
3. Automated CODEOWNERS & Branch Policy Validator
4. Compliance Audit Log Generator (SOC2 / ISO 27001 Audit Trail)
"""

import sys
import time
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[38;5;196m"
CLR_GREEN = "\033[38;5;46m"
CLR_YELLOW = "\033[38;5;226m"
CLR_BLUE = "\033[38;5;39m"
CLR_MAGENTA = "\033[38;5;201m"
CLR_CYAN = "\033[38;5;51m"
CLR_GRAY = "\033[38;5;244m"
BG_DARK = "\033[48;5;236m"


def header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}[GITHUB PLATFORM ENG & GOVERNANCE] >> {CLR_RESET}{CLR_BOLD}{title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}\n")


def print_step(step_num: int, label: str) -> None:
    print(f"{CLR_BOLD}{CLR_YELLOW}[STEP {step_num}]{CLR_RESET} {CLR_BOLD}{label}{CLR_RESET}")


def success(msg: str) -> None:
    print(f"  {CLR_GREEN}✔ [PASSED]{CLR_RESET} {msg}")


def failure(msg: str) -> None:
    print(f"  {CLR_RED}✖ [BLOCKED]{CLR_RESET} {msg}")


def audit_log(event_type: str, actor: str, repo: str, result: str, detail: str) -> None:
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    status_color = CLR_GREEN if result == "ALLOW" else CLR_RED
    print(f"  {CLR_GRAY}[AUDIT-LOG]{CLR_RESET} {timestamp} | {CLR_BOLD}{event_type:<18}{CLR_RESET} | Actor: {CLR_MAGENTA}@{actor:<10}{CLR_RESET} | Repo: {CLR_CYAN}{repo:<16}{CLR_RESET} | {status_color}{result:<6}{CLR_RESET} | {detail}")


@dataclass
class CommitPayload:
    commit_sha: str
    author: str
    message: str
    is_signed: bool
    is_linear: bool
    diff_content: str
    target_branch: str


@dataclass
class RulesetPolicy:
    name: str
    target_branches: List[str]
    require_signed_commits: bool = True
    require_linear_history: bool = True
    min_approvals: int = 2
    require_codeowners: bool = True
    block_force_push: bool = True
    bypass_actors: List[str] = field(default_factory=lambda: ["enterprise-admin", "breakglass-ci"])


class GovernanceEngine:
    def __init__(self, policy: RulesetPolicy):
        self.policy = policy
        self.secret_patterns = {
            "GitHub Personal Access Token": r"ghp_[0-9a-zA-Z]{36}",
            "AWS Access Key ID": r"(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
            "Generic Private Key": r"-----BEGIN (RSA|EC|OPENSSH|PGP) PRIVATE KEY-----",
            "Slack Webhook URL": r"https://hooks\.slack\.com/services/T[0-9a-zA-Z]+/B[0-9a-zA-Z]+/[0-9a-zA-Z]+"
        }

    def check_push_protection(self, diff: str) -> List[str]:
        findings = []
        for name, pattern in self.secret_patterns.items():
            if re.search(pattern, diff):
                findings.append(name)
        return findings

    def evaluate_ruleset(self, commit: CommitPayload, approvers: List[str], codeowner_approved: bool) -> bool:
        repo_name = "infra-core/mesh-gateway"
        print(f"\n{CLR_BOLD}Mengevaluasi Repository Ruleset: {CLR_MAGENTA}{self.policy.name}{CLR_RESET}")
        print(f"Target Branch: {CLR_CYAN}{commit.target_branch}{CLR_RESET} | Actor: {CLR_MAGENTA}@{commit.author}{CLR_RESET}")

        if commit.target_branch not in self.policy.target_branches:
            success(f"Branch '{commit.target_branch}' tidak diproteksi ruleset enterprise.")
            return True

        is_bypass = commit.author in self.policy.bypass_actors
        if is_bypass:
            print(f"  {CLR_YELLOW}⚡ Actor @{commit.author} memiliki hak BYPASS enterprise ruleset.{CLR_RESET}")

        all_passed = True

        # 1. Secret Scanning Push Protection
        leaks = self.check_push_protection(commit.diff_content)
        if leaks:
            all_passed = False
            for leak in leaks:
                failure(f"Push Protection terpicu: Terdeteksi {CLR_BOLD}{leak}{CLR_RESET} pada commit diff!")
            audit_log("PUSH_PROTECTION", commit.author, repo_name, "DENY", f"Secret leak detected: {','.join(leaks)}")
            return False  # Push protection is non-bypassable even for admins
        else:
            success("Secret Scanning Push Protection: Bersih dari credential publik/privat.")

        # 2. Signed Commit Verification
        if self.policy.require_signed_commits:
            if commit.is_signed:
                success("GPG/S/MIME Signature terverifikasi valid (Cryptographic provenance OK).")
            else:
                if not is_bypass:
                    all_passed = False
                    failure("Commit tidak ditandatangani GPG/SSH signature (Enforce Signed Commits).")
                else:
                    success("Commit unsigned diizinkan via enterprise bypass list.")

        # 3. Linear History
        if self.policy.require_linear_history:
            if commit.is_linear:
                success("Linear git history dipertahankan (Tidak ada merge commits kotor).")
            else:
                if not is_bypass:
                    all_passed = False
                    failure("Terdeteksi merge commit non-linear! Kebijakan rebase/squash diwajibkan.")
                else:
                    success("Non-linear commit diizinkan via bypass.")

        # 4. Review Approvals
        if len(approvers) >= self.policy.min_approvals:
            success(f"Peer approvals mencukupi: {len(approvers)}/{self.policy.min_approvals} (Approved by: {', '.join(approvers)}).")
        else:
            if not is_bypass:
                all_passed = False
                failure(f"Peer approvals kurang! Ditemukan: {len(approvers)}, Dibutuhkan minimal: {self.policy.min_approvals}.")
            else:
                success("Peer review minimum di-bypass oleh privileged actor.")

        # 5. CODEOWNERS Review
        if self.policy.require_codeowners:
            if codeowner_approved:
                success("Approval dari Tim CODEOWNERS (@sec-platform-core) terverifikasi.")
            else:
                if not is_bypass:
                    all_passed = False
                    failure("Wajib approval dari anggota @sec-platform-core sesuai file CODEOWNERS.")
                else:
                    success("CODEOWNERS approval di-bypass.")

        action = "ALLOW" if all_passed else "DENY"
        audit_log("BRANCH_RULESET", commit.author, repo_name, action, f"Commit {commit.commit_sha[:8]} target: {commit.target_branch}")
        return all_passed


def main():
    header("SIMULASI PLATFORM ENGINEERING & ENTERPRISE GOVERNANCE")
    print(f"{CLR_BOLD}Selamat datang di Hands-on Lab Modul 01: GitHub Governance Framework.{CLR_RESET}")
    print("Lab ini mendemonstrasikan evaluasi desentralisasi vs sentralisasi kebijakan repository enterprise.")
    time.sleep(0.5)

    policy = RulesetPolicy(
        name="Enterprise-Zero-Trust-Baseline",
        target_branches=["main", "release/*"],
        require_signed_commits=True,
        require_linear_history=True,
        min_approvals=2,
        require_codeowners=True,
        block_force_push=True,
        bypass_actors=["enterprise-admin", "breakglass-ci"]
    )

    engine = GovernanceEngine(policy)

    # Skenario 1: Regular Developer Push dengan Hardcoded Secret
    print_step(1, "Skenario Push Protection (Karyawan tidak sengaja menyertakan PAT)")
    bad_commit = CommitPayload(
        commit_sha="a8f102c98d7b3e1f00a5e12845c110294821a",
        author="junior-dev",
        message="feat: sambungkan connector gateway",
        is_signed=True,
        is_linear=True,
        diff_content="""
+ const GITHUB_TOKEN = "ghp_ABCD1234567890abcdefghijklmnopqrstuv";
+ function fetchRepo() { return fetch('/api', { headers: { Authorization: GITHUB_TOKEN } }); }
        """,
        target_branch="main"
    )
    result1 = engine.evaluate_ruleset(bad_commit, approvers=["peer-dev1", "peer-dev2"], codeowner_approved=True)
    print(f"Status Deployment: {CLR_RED if not result1 else CLR_GREEN}{'REJECTED BY PLATFORM GATE' if not result1 else 'APPROVED'}{CLR_RESET}\n")
    time.sleep(1)

    # Skenario 2: Unsigned Commits dan Review Kurang
    print_step(2, "Skenario Governance Bypass Failure (Unsigned & Missing CODEOWNERS)")
    unsigned_commit = CommitPayload(
        commit_sha="7b12d5912c019a84f33198de71624510924ab",
        author="contractor-ext",
        message="fix: patch typo di README dan config",
        is_signed=False,
        is_linear=True,
        diff_content="+ # Updating documentation anchor point",
        target_branch="main"
    )
    result2 = engine.evaluate_ruleset(unsigned_commit, approvers=["peer-dev1"], codeowner_approved=False)
    print(f"Status Deployment: {CLR_RED if not result2 else CLR_GREEN}{'REJECTED BY PLATFORM GATE' if not result2 else 'APPROVED'}{CLR_RESET}\n")
    time.sleep(1)

    # Skenario 3: Compliance Approved Release
    print_step(3, "Skenario Golden Path Deployment (Semua Governance Check Lolos)")
    golden_commit = CommitPayload(
        commit_sha="f2098bc192837401928301928301928301928",
        author="senior-platform-eng",
        message="feat(ingress): implement mutual TLS verification",
        is_signed=True,
        is_linear=True,
        diff_content="""
+ spec:
+   tls:
+     mode: STRICT
+     clientCertificateValidation: MANDATORY
        """,
        target_branch="main"
    )
    result3 = engine.evaluate_ruleset(golden_commit, approvers=["tech-lead", "principal-eng"], codeowner_approved=True)
    print(f"Status Deployment: {CLR_RED if not result3 else CLR_GREEN}{'REJECTED' if not result3 else 'APPROVED FOR PRODUCTION MERGE'}{CLR_RESET}\n")
    time.sleep(1)

    # Skenario 4: Breakglass Emergency Hotfix (Admin Bypass)
    print_step(4, "Skenario Emergency Breakglass (Incident Response Bypass)")
    breakglass_commit = CommitPayload(
        commit_sha="d999120938401928301928301928301928301",
        author="enterprise-admin",
        message="hotfix(cve-critical): mitigate zero-day buffer overflow",
        is_signed=False,
        is_linear=False,
        diff_content="+ // emergency hotfix applied directly under INCIDENT-4091",
        target_branch="main"
    )
    result4 = engine.evaluate_ruleset(breakglass_commit, approvers=[], codeowner_approved=False)
    print(f"Status Deployment: {CLR_RED if not result4 else CLR_GREEN}{'REJECTED' if not result4 else 'BYPASS ALLOWED - AUDIT TRAIL RECORDED'}{CLR_RESET}\n")

    # Kesimpulan Platform Engineering
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}Ringkasan Platform Governance Scorecard:{CLR_RESET}")
    print(f"  • Enterprise Ruleset: Enforced on all 'main' and 'release/*' branches.")
    print(f"  • Zero-Secret Policy: 100% pre-receive push validation.")
    print(f"  • Cryptographic Chain-of-Custody: Enforced GPG/SSH signatures.")
    print(f"  • Audit Log Compliance: Fully compliant with SOC2 CC6.8 & ISO/IEC 27001 A.8.28.")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{CLR_YELLOW}Simulasi dihentikan oleh pengguna.{CLR_RESET}")
        sys.exit(0)
