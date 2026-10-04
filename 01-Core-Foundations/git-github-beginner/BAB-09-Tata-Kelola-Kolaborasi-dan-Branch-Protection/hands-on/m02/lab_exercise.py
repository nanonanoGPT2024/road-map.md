#!/usr/bin/env python3
"""
Lab Hands-on: Tata Kelola Kolaborasi & Keamanan Repositori (Governance & Security)
Modul: 02 Deep Dive - Git & GitHub Security Engine Simulation
Deskripsi:
  Skrip ini memodelkan sistem verifikasi tata kelola repositori enterprise:
  1. Secret Scanner (Entropy calculation + Regex rules untuk deteksi kredensial bocor).
  2. CODEOWNERS Parser & Evaluator (Validasi file paths vs mandatory reviewers).
  3. Branch Protection Policy Enforcer (Pemberlakuan signed commits, reviews, dan CI checks).
  4. Cryptographic Tamper-evident Audit Ledger (Hash-chained audit log).
"""

import sys
import re
import math
import time
import hashlib
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field

# --- ANSI Terminal Color Codes ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"


def print_banner(text: str):
    line = "=" * 78
    print(f"\n{CLR_BOLD}{CLR_CYAN}{line}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}[GOVERNANCE ENGINE] {text}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{line}{CLR_RESET}")


# ==============================================================================
# 1. SECRET SCANNER ENGINE (Regex + Shannon Entropy Analysis)
# ==============================================================================
class SecretScanner:
    """Mendeteksi kredensial, token API, dan string ber-entropi tinggi pada diff file."""

    PATTERNS = {
        "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "GitHub Personal Token": re.compile(r"ghp_[a-zA-Z0-9]{36}"),
        "Generic Private Key": re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
        "Slack Webhook URL": re.compile(r"https://hooks\.slack\.com/services/T[a-zA-Z0-9_]+/B[a-zA-Z0-9_]+/[a-zA-Z0-9_]+"),
    }

    ENTROPY_THRESHOLD = 4.2  # Shannon entropy threshold untuk token acak hex/base64

    @staticmethod
    def calculate_entropy(data: str) -> float:
        """Menghitung Shannon Entropy dari sebuah string untuk deteksi password/token acak."""
        if not data:
            return 0.0
        entropy = 0.0
        length = len(data)
        freq = {}
        for char in data:
            freq[char] = freq.get(char, 0) + 1
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy

    def scan_diff(self, file_path: str, diff_content: str) -> List[Dict[str, str]]:
        """Memeriksa isi diff untuk mendeteksi potensi secret yang tertulis (leak)."""
        findings = []
        lines = diff_content.splitlines()

        for idx, line in enumerate(lines, 1):
            if not line.startswith("+"):
                continue  # Hanya periksa baris yang ditambahkan pada commit

            added_content = line[1:].strip()

            # 1. Pattern-based scan
            for leak_type, pattern in self.PATTERNS.items():
                if pattern.search(added_content):
                    findings.append({
                        "file": file_path,
                        "line": str(idx),
                        "type": leak_type,
                        "severity": "CRITICAL",
                        "snippet": added_content[:25] + "..." if len(added_content) > 25 else added_content
                    })

            # 2. Entropy-based high-randomness scan (contoh: API Secret tokens)
            tokens = re.findall(r'[a-zA-Z0-9_\-+=/]{20,}', added_content)
            for token in tokens:
                # Abaikan path direktori atau kata majemuk umum
                if "/" in token and not re.search(r'[A-Za-z0-9+/=]{20,}', token):
                    continue
                ent = self.calculate_entropy(token)
                if ent >= self.ENTROPY_THRESHOLD and not any(f["type"] == "Generic Private Key" for f in findings):
                    findings.append({
                        "file": file_path,
                        "line": str(idx),
                        "type": f"High Entropy String (H={ent:.2f})",
                        "severity": "WARNING",
                        "snippet": token[:16] + "..."
                    })

        return findings


# ==============================================================================
# 2. CODEOWNERS ENGINE
# ==============================================================================
class CodeOwnersEngine:
    """Mengelola pemetaan path direktori ke tim penanggung jawab kode."""

    def __init__(self, raw_rules: str):
        self.rules: List[tuple] = []
        self._parse_rules(raw_rules)

    def _parse_rules(self, raw_rules: str):
        for line in raw_rules.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            pattern = parts[0]
            owners = parts[1:]
            # Konversi pattern wildcard sederhana ke Regex
            regex_str = "^" + pattern.replace(".", r"\.").replace("*", ".*") + "$"
            self.rules.append((re.compile(regex_str), owners))

    def evaluate_required_owners(self, modified_files: List[str]) -> Set[str]:
        """Menentukan daftar pemilik kode (owners) yang wajib mereview perubahan."""
        required = set()
        for f in modified_files:
            # Rule terakhir yang match memiliki prioritas tertinggi (spesifikasi CODEOWNERS)
            matched_owners = None
            for pattern_re, owners in self.rules:
                if pattern_re.search(f):
                    matched_owners = owners
            if matched_owners:
                required.update(matched_owners)
        return required


# ==============================================================================
# 3. BRANCH PROTECTION & AUDIT TRAIL
# ==============================================================================
@dataclass
class CommitMetadata:
    commit_id: str
    author: str
    is_signed_gpg: bool
    modified_files: List[str]
    diff_payload: Dict[str, str]  # file_path -> diff


@dataclass
class PullRequest:
    pr_id: int
    title: str
    target_branch: str
    commits: List[CommitMetadata]
    approvals: List[str] = field(default_factory=list)
    status_checks: Dict[str, str] = field(default_factory=dict)  # check_name -> PASSED/FAILED


class AuditLedger:
    """Hash-chained ledger untuk mencatat riwayat keamanan repositori yang anti-manipulasi."""

    def __init__(self):
        self.chain: List[Dict] = []
        self.prev_hash = "0" * 64

    def record_event(self, action: str, details: Dict):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        block_content = f"{self.prev_hash}|{action}|{timestamp}|{details}"
        block_hash = hashlib.sha256(block_content.encode("utf-8")).hexdigest()
        entry = {
            "index": len(self.chain) + 1,
            "timestamp": timestamp,
            "action": action,
            "details": details,
            "prev_hash": self.prev_hash,
            "block_hash": block_hash
        }
        self.chain.append(entry)
        self.prev_hash = block_hash

    def verify_integrity(self) -> bool:
        """Memvalidasi integritas kriptografis seluruh rantai audit log."""
        expected_prev = "0" * 64
        for entry in self.chain:
            if entry["prev_hash"] != expected_prev:
                return False
            payload = f"{entry['prev_hash']}|{entry['action']}|{entry['timestamp']}|{entry['details']}"
            if hashlib.sha256(payload.encode("utf-8")).hexdigest() != entry["block_hash"]:
                return False
            expected_prev = entry["block_hash"]
        return True


class GovernancePolicyEnforcer:
    """Menguji kepatuhan Branch Protection Rules sebelum merge diizinkan."""

    def __init__(self, codeowners: CodeOwnersEngine, scanner: SecretScanner, ledger: AuditLedger):
        self.codeowners = codeowners
        self.scanner = scanner
        self.ledger = ledger

        # Kebijakan branch protection untuk target branch 'main'
        self.min_approvals = 2
        self.require_signed_commits = True
        self.required_checks = ["ci/security-lint", "ci/unit-tests"]

    def enforce_pr(self, pr: PullRequest) -> bool:
        print(f"\n{CLR_BOLD}[EVALUASI PR #{pr.pr_id}: '{pr.title}' -> branch '{pr.target_branch}']{CLR_RESET}")
        all_passed = True
        blocking_reasons = []

        # 1. Audit Security Scanning terhadap semua perubahan diff
        print(f"[*] Menjalankan Automated Secret Scanning...")
        has_critical_secrets = False
        all_files_changed = set()

        for commit in pr.commits:
            all_files_changed.update(commit.modified_files)
            for fpath, diff in commit.diff_payload.items():
                findings = self.scanner.scan_diff(fpath, diff)
                for finding in findings:
                    severity_color = CLR_RED if finding['severity'] == 'CRITICAL' else CLR_YELLOW
                    print(f"    {severity_color}[! {finding['severity']}] {finding['file']}:{finding['line']} - "
                          f"{finding['type']} (Snippet: '{finding['snippet']}'){CLR_RESET}")
                    if finding['severity'] == "CRITICAL":
                        has_critical_secrets = True

        if has_critical_secrets:
            blocking_reasons.append("Terdapat secret/kredensial ter-ekspos pada diff commit!")
            all_passed = False
        else:
            print(f"    {CLR_GREEN}[PASS] Tidak ada secret kritis yang terdeteksi.{CLR_RESET}")

        # 2. Verifikasi GPG Signed Commits
        print(f"[*] Memeriksa GPG Signature Commits...")
        unsigned_commits = [c.commit_id for c in pr.commits if not c.is_signed_gpg]
        if self.require_signed_commits and unsigned_commits:
            blocking_reasons.append(f"Commit tanpa tanda tangan GPG valid: {', '.join(unsigned_commits)}")
            print(f"    {CLR_RED}[FAIL] Kebijakan Signed Commits dilanggar. Commit tidak terverifikasi.{CLR_RESET}")
            all_passed = False
        else:
            print(f"    {CLR_GREEN}[PASS] Semua commit ({len(pr.commits)}) terverifikasi dengan GPG.{CLR_RESET}")

        # 3. Validasi Review CODEOWNERS
        print(f"[*] Mengevaluasi Hak Akses & Persetujuan CODEOWNERS...")
        required_owners = self.codeowners.evaluate_required_owners(list(all_files_changed))
        print(f"    - Berkas yang diubah: {', '.join(all_files_changed)}")
        print(f"    - Mandatory Reviewers (CODEOWNERS): {', '.join(required_owners) if required_owners else 'None'}")

        missing_owner_reviews = [owner for owner in required_owners if owner not in pr.approvals]
        if missing_owner_reviews:
            blocking_reasons.append(f"Kurang persetujuan dari CODEOWNERS: {', '.join(missing_owner_reviews)}")
            print(f"    {CLR_RED}[FAIL] Review CODEOWNERS belum terpenuhi.{CLR_RESET}")
            all_passed = False
        else:
            print(f"    {CLR_GREEN}[PASS] Persetujuan CODEOWNERS telah dipenuhi.{CLR_RESET}")

        # 4. Validasi Kuorum Approvals Minimum
        if len(pr.approvals) < self.min_approvals:
            blocking_reasons.append(f"Total approval saat ini ({len(pr.approvals)}) kurang dari kuorum ({self.min_approvals})")
            print(f"    {CLR_RED}[FAIL] Kuorum approval belum cukup.{CLR_RESET}")
            all_passed = False
        else:
            print(f"    {CLR_GREEN}[PASS] Kuorum approval tercapai ({len(pr.approvals)}/{self.min_approvals}).{CLR_RESET}")

        # 5. Validasi Status Checks (CI/CD Pipeline)
        print(f"[*] Memeriksa Status Checks (CI)...")
        for check in self.required_checks:
            status = pr.status_checks.get(check, "MISSING")
            if status != "PASSED":
                blocking_reasons.append(f"Status check '{check}' berstatus: {status}")
                print(f"    {CLR_RED}[FAIL] Required check '{check}' = {status}{CLR_RESET}")
                all_passed = False
            else:
                print(f"    {CLR_GREEN}[PASS] Required check '{check}' = PASSED{CLR_RESET}")

        # Keputusan Akhir & Perekaman Ledger
        status_action = "PR_MERGED" if all_passed else "PR_BLOCKED"
        self.ledger.record_event(
            action=status_action,
            details={
                "pr_id": pr.pr_id,
                "target": pr.target_branch,
                "reasons": blocking_reasons if not all_passed else ["All branch policies satisfied."]
            }
        )

        if all_passed:
            print(f"\n{CLR_BOLD}{CLR_GREEN}>>> HASIL: MERGE DISETUJUI. Branch protection rules terpenuhi.{CLR_RESET}")
        else:
            print(f"\n{CLR_BOLD}{CLR_RED}>>> HASIL: MERGE DITOLAK. Pelanggaran kebijakan terdeteksi:{CLR_RESET}")
            for r in blocking_reasons:
                print(f"    {CLR_RED}- {r}{CLR_RESET}")

        return all_passed


# ==============================================================================
# MAIN SIMULASI HANDS-ON
# ==============================================================================
def main():
    print_banner("SIMULASI KEAMANAN & TATA KELOLA REPOSITORI (ENTERPRISE LAB)")

    # 1. Definisi Konfigurasi CODEOWNERS
    codeowners_config = """
    # Security-critical configurations
    /security/*          @secops-lead @appsec-team
    /infra/terraform/*   @infra-devops
    *.py                 @backend-core
    """
    codeowners = CodeOwnersEngine(codeowners_config)
    scanner = SecretScanner()
    ledger = AuditLedger()
    governance = GovernancePolicyEnforcer(codeowners, scanner, ledger)

    # --------------------------------------------------------------------------
    # SKENARIO 1: Pull Request Melanggar Keamanan (Secret leak + Unsigned commit)
    # --------------------------------------------------------------------------
    bad_commit = CommitMetadata(
        commit_id="a1b2c3d",
        author="alice@developer.local",
        is_signed_gpg=False,  # Unsigned commit
        modified_files=["infra/terraform/main.tf", "security/auth.py"],
        diff_payload={
            "infra/terraform/main.tf": "+ provider \"aws\" {\n+   access_key = \"AKIAIOSFODNN7EXAMPLE\"\n+ }",
            "security/auth.py": "+ API_SIGN_KEY = \"4f9a7c3b2e1d0f8a7e6b5c4d3e2f1a0b\" # high entropy internal token"
        }
    )

    bad_pr = PullRequest(
        pr_id=101,
        title="feat: Migrasi AWS Provider dan Helper Auth",
        target_branch="main",
        commits=[bad_commit],
        approvals=["@junior-dev"],  # Kurang & bukan CODEOWNER
        status_checks={"ci/security-lint": "PASSED", "ci/unit-tests": "PASSED"}
    )

    governance.enforce_pr(bad_pr)

    # --------------------------------------------------------------------------
    # SKENARIO 2: Pull Request Patuh Kebijakan (Compliant PR)
    # --------------------------------------------------------------------------
    clean_commit_1 = CommitMetadata(
        commit_id="e5f6g7h",
        author="alice@developer.local",
        is_signed_gpg=True,
        modified_files=["infra/terraform/main.tf"],
        diff_payload={
            "infra/terraform/main.tf": "+ provider \"aws\" {\n+   # Menggunakan AWS IAM Role OIDC\n+ }"
        }
    )

    clean_commit_2 = CommitMetadata(
        commit_id="j8k9l0m",
        author="bob@developer.local",
        is_signed_gpg=True,
        modified_files=["security/auth.py"],
        diff_payload={
            "security/auth.py": "+ def get_signature():\n+     return os.environ.get('SECRET_TOKEN')"
        }
    )

    good_pr = PullRequest(
        pr_id=102,
        title="fix: Implementasi IAM Role OIDC & Secure Env Storage",
        target_branch="main",
        commits=[clean_commit_1, clean_commit_2],
        approvals=["@secops-lead", "@infra-devops", "@backend-core"],
        status_checks={"ci/security-lint": "PASSED", "ci/unit-tests": "PASSED"}
    )

    governance.enforce_pr(good_pr)

    # --------------------------------------------------------------------------
    # SKENARIO 3: Audit Ledger Integrity Check
    # --------------------------------------------------------------------------
    print_banner("VERIFIKASI INTEGRITAS KRIPTOGRAFIS AUDIT LOG")
    print(f"Total entri dalam log rantai audit: {len(ledger.chain)}")
    for entry in ledger.chain:
        print(f"[{entry['index']}] {entry['timestamp']} | Event: {CLR_BOLD}{entry['action']}{CLR_RESET} | "
              f"Hash: {entry['block_hash'][:16]}... | Prev: {entry['prev_hash'][:16]}...")

    is_valid = ledger.verify_integrity()
    if is_valid:
        print(f"\n{CLR_GREEN}[PASS] Seluruh rantai blok audit log TERVERIFIKASI valid dan bebas manipulasi.{CLR_RESET}")
    else:
        print(f"\n{CLR_RED}[CRITICAL] Audit log tidak valid atau mengalami pembongkaran data!{CLR_RESET}")


if __name__ == "__main__":
    main()