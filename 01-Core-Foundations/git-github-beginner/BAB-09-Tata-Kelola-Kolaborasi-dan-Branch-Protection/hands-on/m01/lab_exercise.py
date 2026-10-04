#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Tata Kelola Kolaborasi & Branch Protection (BAB-09)
Modul: git-github-beginner - BAB-09-Tata-Kelola-Kolaborasi-dan-Branch-Protection

Deskripsi:
Simulasi interaktif alur tata kelola kolaborasi tim pada Git & GitHub:
- Proteksi branch utama (main)
- Blokir direct push ke branch terproteksi
- Mekanisme Pull Request (PR) & CODEOWNERS approval
- Gating CI/Status checks (Unit tests & Linting)
- Enforce linear history & strategi merge (Squash / Rebase)
"""

import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes
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

def color(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"

@dataclass
class BranchProtectionPolicy:
    branch_name: str = "main"
    allow_direct_push: bool = False
    require_pull_request: bool = True
    required_approvals: int = 1
    require_codeowners_review: bool = True
    require_status_checks: bool = True
    require_linear_history: bool = True
    enforce_for_administrators: bool = True

@dataclass
class PullRequest:
    id: int
    title: str
    source_branch: str
    target_branch: str
    author: str
    touched_files: List[str]
    approvals: List[str] = field(default_factory=list)
    ci_status: Dict[str, str] = field(default_factory=lambda: {
        "linter": "PENDING",
        "unit-tests": "PENDING",
        "security-scan": "PENDING"
    })
    is_merged: bool = False
    merge_strategy: Optional[str] = None

class GovernanceSimulator:
    def __init__(self):
        self.policy = BranchProtectionPolicy()
        self.codeowners: Dict[str, List[str]] = {
            "src/core/": ["@lead-dev", "@tech-lead"],
            "docs/": ["@tech-writer"],
            "infra/": ["@devops-lead"],
            "*": ["@core-team"]
        }
        self.current_user = "junior-developer"
        self.pull_requests: List[PullRequest] = []
        self.next_pr_id = 101

    def print_banner(self):
        print(color("=" * 72, BLUE))
        print(color("   SIMULASI TATA KELOLA KOLABORASI & BRANCH PROTECTION (BAB-09)   ", BOLD + CYAN))
        print(color("=" * 72, BLUE))
        print(f"Pengguna aktif: {color(self.current_user, YELLOW)} | Branch target: {color(self.policy.branch_name, GREEN)}")
        print()

    def display_policy(self):
        print(color("\n--- KONFIGURASI BRANCH PROTECTION RULE [main] ---", BOLD + MAGENTA))
        print(f" 1. Allow Direct Push               : {color('DENIED', RED) if not self.policy.allow_direct_push else color('ALLOWED', GREEN)}")
        print(f" 2. Require Pull Request            : {color('YES', GREEN) if self.policy.require_pull_request else color('NO', RED)}")
        print(f" 3. Required Approvals Min          : {color(str(self.policy.required_approvals), YELLOW)} review(s)")
        print(f" 4. Require CODEOWNERS Review       : {color('YES', GREEN) if self.policy.require_codeowners_review else color('NO', RED)}")
        print(f" 5. Require Status Checks Passing   : {color('YES', GREEN) if self.policy.require_status_checks else color('NO', RED)}")
        print(f" 6. Enforce Linear History          : {color('YES', GREEN) if self.policy.require_linear_history else color('NO', RED)}")
        print(f" 7. Enforce for Administrators      : {color('YES', GREEN) if self.policy.enforce_for_administrators else color('NO', RED)}")
        print(color("-" * 50, DIM))
        print(color("CODEOWNERS Mappings:", BOLD))
        for path_pattern, owners in self.codeowners.items():
            print(f"   {path_pattern:<15} -> {', '.join(owners)}")
        print()

    def simulate_direct_push(self):
        print(color("\n[ACTION] Mencoba 'git push origin main' secara langsung...", BOLD + YELLOW))
        time.sleep(0.4)
        if not self.policy.allow_direct_push:
            print(color("remote: Resolving deltas: 100% (3/3), done.", DIM))
            print(color("remote: error: GH006: Protected branch update failed for refs/heads/main.", RED + BOLD))
            print(color("remote: error: At least 1 approving review is required by policy.", RED))
            print(color("remote: error: Changes must be made through a pull request.", RED))
            print(color("To github.com:org/super-project.git", DIM))
            print(color(" ! [remote rejected] main -> main (protected branch hook declined)", RED + BOLD))
            print(color("FAILED: Direct push diblokir oleh GitHub Branch Protection Hook!\n", RED))
        else:
            print(color("PERINGATAN: Direct push diizinkan karena proteksi dinonaktifkan.", YELLOW))
            print(color("OK: Commit berhasil didorong langsung ke main (Risiko tinggi!).\n", GREEN))

    def create_pull_request(self) -> PullRequest:
        print(color("\n[ACTION] Membuat Feature Branch & Membuka Pull Request...", BOLD + CYAN))
        branch_name = f"feat/login-oauth-{len(self.pull_requests) + 1}"
        title = "feat(auth): implementasi login GitHub OAuth2"
        files = ["src/core/auth.py", "docs/auth-guide.md"]

        pr = PullRequest(
            id=self.next_pr_id,
            title=title,
            source_branch=branch_name,
            target_branch="main",
            author=self.current_user,
            touched_files=files
        )
        self.next_pr_id += 1
        self.pull_requests.append(pr)

        print(f"-> Branch dibuat: {color(branch_name, GREEN)}")
        print(f"-> Files diubah : {', '.join(files)}")
        print(f"-> PR #{pr.id} dibuka: '{color(pr.title, WHITE)}'")
        
        # Determine required codeowners
        required_owners = set()
        for f in files:
            for pattern, owners in self.codeowners.items():
                if pattern.rstrip("/") in f or pattern == "*":
                    required_owners.update(owners)
        print(f"-> CODEOWNERS terdeteksi otomatis: {color(', '.join(sorted(required_owners)), YELLOW)}")
        print(color("SUCCESS: PR siap diproses untuk governance check.\n", GREEN))
        return pr

    def run_ci_checks(self, pr: PullRequest):
        print(color(f"\n[ACTION] Menjalankan Automated Status Checks untuk PR #{pr.id}...", BOLD + CYAN))
        checks = ["linter", "unit-tests", "security-scan"]
        for c in checks:
            time.sleep(0.3)
            pr.ci_status[c] = "SUCCESS"
            print(f"   [CI Gating] Check: {c:<15} ... {color('PASSED (0 errors)', GREEN)}")
        print(color("All required status checks have succeeded!\n", GREEN + BOLD))

    def add_reviews(self, pr: PullRequest):
        print(color(f"\n[ACTION] Meminta review rekan tim & CODEOWNERS untuk PR #{pr.id}...", BOLD + CYAN))
        reviewers = ["@lead-dev", "@tech-lead"]
        for reviewer in reviewers:
            if reviewer not in pr.approvals:
                pr.approvals.append(reviewer)
                print(f"   Review masuk dari {color(reviewer, YELLOW)}: {color('APPROVED (LGTM!)', GREEN)}")
        print(f"Total persetujuan saat ini: {color(str(len(pr.approvals)), GREEN)} review.\n")

    def attempt_merge(self, pr: PullRequest):
        print(color(f"\n[ACTION] Mengevaluasi aturan penggabungan (Merge Gate) untuk PR #{pr.id}...", BOLD + MAGENTA))
        time.sleep(0.3)
        failures = []

        # 1. PR Requirement
        if self.policy.require_pull_request and not pr:
            failures.append("Perubahan harus melalui Pull Request.")

        # 2. Approvals
        if len(pr.approvals) < self.policy.required_approvals:
            failures.append(f"Kurang approval: butuh minimal {self.policy.required_approvals}, baru didapat {len(pr.approvals)}.")

        # 3. CODEOWNERS Review
        if self.policy.require_codeowners_review:
            has_codeowner = any(r in ["@lead-dev", "@tech-lead"] for r in pr.approvals)
            if not has_codeowner:
                failures.append("Wajib mendapatkan approval dari CODEOWNERS untuk folder src/core/.")

        # 4. CI Status Checks
        if self.policy.require_status_checks:
            failed_ci = [k for k, v in pr.ci_status.items() if v != "SUCCESS"]
            if failed_ci:
                failures.append(f"Status checks belum lolos: {', '.join(failed_ci)}")

        if failures:
            print(color("MERGE DIBLOKIR! Aturan Branch Protection tidak terpenuhi:", RED + BOLD))
            for f in failures:
                print(f"  {color('[X]', RED)} {f}")
            print(color("Solusi: Selesaikan status check atau minta review dari pemilik kode terkait.\n", YELLOW))
            return False

        # Pilih strategi merge
        strategy = "Squash and Merge"
        pr.is_merged = True
        pr.merge_strategy = strategy
        print(color(f"SEMUA GATE TERPENUHI: {strategy} berhasil dijalankan!", GREEN + BOLD))
        print(f"Branch {color(pr.source_branch, CYAN)} berhasil digabungkan ke {color('main', GREEN)}.")
        print(color("History tetap bersih dan linear (Linear History Enforced).\n", DIM + WHITE))
        return True

    def run_automated_audit(self):
        print(color("\n=== AUDIT TATA KELOLA OTOMATIS (GOVERNANCE AUDIT) ===", BOLD + YELLOW))
        pr = self.create_pull_request()
        
        print(color("[FASE 1] Verifikasi Kegagalan Penggabungan Prematur:", BOLD))
        self.attempt_merge(pr)

        print(color("[FASE 2] Menjalankan Pipeline CI:", BOLD))
        self.run_ci_checks(pr)

        print(color("[FASE 3] Verifikasi Kegagalan Karena Kurang Review:", BOLD))
        self.attempt_merge(pr)

        print(color("[FASE 4] Menambahkan Review CODEOWNERS:", BOLD))
        self.add_reviews(pr)

        print(color("[FASE 5] Final Merge Gate Check:", BOLD))
        success = self.attempt_merge(pr)
        
        if success:
            print(color("HASIL AUDIT: SISTEM TATA KELOLA BERJALAN 100% SESUAI STANDAR!", BOLD + GREEN))
        print()

    def run(self):
        self.print_banner()
        while True:
            print(color("MENU UTAMA:", BOLD))
            print("1. Tampilkan Konfigurasi Branch Protection & CODEOWNERS")
            print("2. Simulasi Direct Push ke 'main' (Uji Blokir Proteksi)")
            print("3. Buat Feature Branch & Buka Pull Request (PR)")
            print("4. Jalankan Status Checks / CI Gating pada PR Terakhir")
            print("5. Tambahkan Review & Approval dari CODEOWNERS")
            print("6. Eksekusi Penggabungan PR (Merge Evaluation)")
            print("7. Jalankan Skenario Audit Lengkap Otomatis")
            print("8. Keluar")
            
            choice = input(color("\nPilih menu (1-8): ", BOLD + CYAN)).strip()

            if choice == "1":
                self.display_policy()
            elif choice == "2":
                self.simulate_direct_push()
            elif choice == "3":
                self.create_pull_request()
            elif choice == "4":
                if not self.pull_requests:
                    print(color("Belum ada PR yang dibuka. Pilih menu 3 terlebih dahulu!\n", YELLOW))
                else:
                    self.run_ci_checks(self.pull_requests[-1])
            elif choice == "5":
                if not self.pull_requests:
                    print(color("Belum ada PR yang dibuka. Pilih menu 3 terlebih dahulu!\n", YELLOW))
                else:
                    self.add_reviews(self.pull_requests[-1])
            elif choice == "6":
                if not self.pull_requests:
                    print(color("Belum ada PR yang dibuka. Pilih menu 3 terlebih dahulu!\n", YELLOW))
                else:
                    self.attempt_merge(self.pull_requests[-1])
            elif choice == "7":
                self.run_automated_audit()
            elif choice == "8" or choice.lower() in ["exit", "q"]:
                print(color("Keluar dari simulasi. Sesi lab selesai.", GREEN))
                break
            else:
                print(color("Pilihan tidak valid, silakan coba lagi.\n", RED))

if __name__ == "__main__":
    sim = GovernanceSimulator()
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        sim.print_banner()
        sim.display_policy()
        sim.simulate_direct_push()
        sim.run_automated_audit()
    else:
        try:
            sim.run()
        except (KeyboardInterrupt, EOFError):
            print(color("\nSimulasi dihentikan.", YELLOW))
