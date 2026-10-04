#!/usr/bin/env python3
"""
Lab Exercise M01: Repository Security, Compliance & Secrets Engine Simulator
Topik: BAB-09-Repository-Security-Compliance-dan-Secrets (Git & GitHub Foundations)

Simulasi mandiri untuk:
1. Secret Detection & Push Protection Engine (Regex scanning & Shannon Entropy)
2. Branch Protection & Compliance Rules Evaluation
3. Dependabot & Security Advisory Vulnerability Scan
4. Audit Trail & Incident Response Remediation Workflow
"""

import sys
import re
import math
import time
import json
from datetime import datetime
from typing import Dict, List, Tuple, Any

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"
CLR_BG_RED = "\033[41m"
CLR_BG_GREEN = "\033[42m"


def header(title: str) -> None:
    print(f"\n{CLR_CYAN}{'='*68}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_WHITE} [LAB] {title.upper()} {CLR_RESET}")
    print(f"{CLR_CYAN}{'='*68}{CLR_RESET}")


def subheader(title: str) -> None:
    print(f"\n{CLR_BLUE}{'-'*50}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_YELLOW}▸ {title}{CLR_RESET}")
    print(f"{CLR_BLUE}{'-'*50}{CLR_RESET}")


def calculate_entropy(data: str) -> float:
    """Menghitung Shannon entropy untuk mendeteksi high-entropy secrets/tokens."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    char_freq = {}
    for char in data:
        char_freq[char] = char_freq.get(char, 0) + 1
    for count in char_freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


# Known patterns for secret detection
SECRET_PATTERNS = {
    "GitHub Personal Access Token (classic)": r"\bghp_[A-Za-z0-9_]{36}\b",
    "GitHub Fine-grained PAT": r"\bgithub_pat_[A-Za-z0-9_]{82}\b",
    "AWS Access Key ID": r"\bAKIA[0-9A-Z]{16}\b",
    "AWS Secret Access Key": r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
    "Generic Private Key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "Slack Webhook URL": r"https://hooks\.slack\.com/services/T[0-9A-Z_]+/B[0-9A-Z_]+/[0-9A-Za-z]+",
    "JWT Bearer Token": r"\beyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b",
}


class SecretScanner:
    """Scanner commit diffs untuk mendeteksi credentials sebelum masuk ke remote repo."""

    def __init__(self):
        self.findings: List[Dict[str, Any]] = []

    def scan_diff(self, filename: str, content: str) -> List[Dict[str, Any]]:
        file_findings = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            # Check pattern regex
            for name, pattern in SECRET_PATTERNS.items():
                match = re.search(pattern, line)
                if match:
                    detected_val = match.group(0)
                    masked = detected_val[:6] + "..." + detected_val[-4:] if len(detected_val) > 10 else "***"
                    file_findings.append({
                        "file": filename,
                        "line": idx,
                        "type": name,
                        "severity": "CRITICAL",
                        "preview": masked,
                        "entropy": round(calculate_entropy(detected_val), 2),
                    })

            # Check generic high entropy on variable assignments
            assign_match = re.search(r'(?i)(?:api_key|token|password|secret)\s*=\s*["\']([^"\']{16,})["\']', line)
            if assign_match:
                token_val = assign_match.group(1)
                entropy = calculate_entropy(token_val)
                if entropy > 4.2:  # High entropy threshold
                    masked = token_val[:4] + "..." + token_val[-3:]
                    file_findings.append({
                        "file": filename,
                        "line": idx,
                        "type": "High Entropy Credential Assignment",
                        "severity": "HIGH",
                        "preview": masked,
                        "entropy": round(entropy, 2),
                    })

        self.findings.extend(file_findings)
        return file_findings


class ComplianceGuard:
    """Mengevaluasi kesesuaian branch protection rule & compliance checklist."""

    def __init__(self):
        self.rules = {
            "require_pull_request_reviews": True,
            "required_approving_review_count": 2,
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "require_signed_commits": True,
            "require_linear_history": True,
            "allow_force_pushes": False,
            "allow_deletions": False,
            "required_status_checks": ["build-and-test", "security-secret-scan", "license-compliance"],
        }

    def evaluate_pr(self, pr_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        violations = []

        if pr_data.get("approvals", 0) < self.rules["required_approving_review_count"]:
            violations.append(
                f"PR approvals kurang: {pr_data.get('approvals', 0)}/{self.rules['required_approving_review_count']}"
            )

        if not pr_data.get("codeowner_approved", False) and self.rules["require_code_owner_reviews"]:
            violations.append("Persetujuan dari CODEOWNERS belum terpenuhi.")

        if not pr_data.get("is_signed", False) and self.rules["require_signed_commits"]:
            violations.append("Commit belum ditandatangani GPG/SSH signature valid.")

        if not pr_data.get("linear_history", True) and self.rules["require_linear_history"]:
            violations.append("Terdapat merge commit yang merusak linear git history.")

        failed_checks = [
            chk for chk in self.rules["required_status_checks"]
            if chk not in pr_data.get("passed_checks", [])
        ]
        if failed_checks:
            violations.append(f"Status check wajib belum lolos: {', '.join(failed_checks)}")

        is_passed = len(violations) == 0
        return is_passed, violations


class DependabotSimulator:
    """Simulasi dependency vulnerability alerts dan automated security update."""

    MOCK_VULNS = [
        {"package": "requests", "current": "2.19.1", "fixed": "2.31.0", "cve": "CVE-2023-32681", "severity": "HIGH"},
        {"package": "pyyaml", "current": "5.3.1", "fixed": "5.4.0", "cve": "CVE-2020-14343", "severity": "CRITICAL"},
        {"package": "cryptography", "current": "3.3.1", "fixed": "41.0.6", "cve": "CVE-2023-49083", "severity": "MEDIUM"},
    ]

    def run_scan(self) -> List[Dict[str, str]]:
        return self.MOCK_VULNS


def run_interactive_simulation() -> None:
    header("BAB 09: Repository Security, Compliance & Secrets Engine")
    print(f"{CLR_WHITE}Memulai simulasi pertahanan berlapis repository Git & GitHub Enterprise...{CLR_RESET}\n")

    # 1. Secret Scanning & Push Protection
    subheader("Tahap 1: Secret Scanning & Push Protection (Pre-Receive Hook)")
    scanner = SecretScanner()

    mock_commit_files = {
        "src/config/database.py": """
import os
DB_HOST = "prod-db.internal.net"
# ghp_39CharactersFakeClassicTokenExample12345
GITHUB_API_KEY = "ghp_AbCdEf1234567890GhIjKlMnOpQrStUvWxYz"
AWS_KEY = "AKIA1234567890ABCDEF"
aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
""",
        "src/auth/jwt_helper.py": """
import jwt
SECRET_HMAC = "k9$2mZ#99xLaq!11vN0048s91aA8bC" # High entropy secret
ALGO = "HS256"
""",
        "deploy/scripts/deploy.sh": """
#!/bin/bash
echo "Deploying to production cluster..."
SLACK_NOTIFY="https://hooks.slack.com/services/T00000000/B00000000/XXXXX1234567890abcdef"
"""
    }

    print(f"{CLR_WHITE}Menganalisis staging diff commit sebelum 'git push' ke remote repository...{CLR_RESET}")
    time.sleep(0.3)

    total_findings = []
    for fname, code in mock_commit_files.items():
        res = scanner.scan_diff(fname, code)
        if res:
            total_findings.extend(res)

    for item in total_findings:
        sev_color = CLR_RED if item["severity"] == "CRITICAL" else CLR_YELLOW
        print(f" {sev_color}[{item['severity']}]{CLR_RESET} {CLR_BOLD}{item['file']}:{item['line']}{CLR_RESET}")
        print(f"    ├─ Vulnerability: {CLR_MAGENTA}{item['type']}{CLR_RESET}")
        print(f"    ├─ Masked Value:  {item['preview']}")
        print(f"    └─ Entropy Score: {item['entropy']} bits/byte")

    print(f"\n{CLR_BG_RED}{CLR_WHITE}{CLR_BOLD} [PUSH PROTECTION BLOCKED] {CLR_RESET}")
    print(f"{CLR_RED}Remote memblokir push karena terdeteksi {len(total_findings)} secret potensial.{CLR_RESET}")
    print(f"{CLR_YELLOW}Saran Mitigasi: Gunakan 'git rm --cached', 'git filter-repo', atau rotasi kredensial.{CLR_RESET}")

    # 2. Branch Protection & Compliance Evaluation
    subheader("Tahap 2: Evaluasi Branch Protection Ruleset & Compliance")
    guard = ComplianceGuard()

    test_pr = {
        "title": "Fix: Perbaikan sistem pembayaran dan upgrade dependensi",
        "branch": "feature/payments-v2",
        "target_branch": "main",
        "approvals": 1,              # Rule butuh 2
        "codeowner_approved": False, # Butuh True
        "is_signed": True,           # Commit signed with GPG
        "linear_history": True,
        "passed_checks": ["build-and-test", "security-secret-scan"], # Kurang 'license-compliance'
    }

    print(f"Memvalidasi PR #{CLR_CYAN}142{CLR_RESET} menuju branch {CLR_BOLD}'main'{CLR_RESET}...")
    is_ok, violations = guard.evaluate_pr(test_pr)

    if not is_ok:
        print(f"\n{CLR_RED}✖ STATUS PR: MERGE RESTRICTED (Kebijakan Compliance Dilanggar){CLR_RESET}")
        for v in violations:
            print(f"  {CLR_RED}✗ {v}{CLR_RESET}")
    else:
        print(f"\n{CLR_GREEN}✔ STATUS PR: COMPLIANT & READY TO MERGE{CLR_RESET}")

    # 3. Dependabot & Security Advisory Scan
    subheader("Tahap 3: Dependabot Security Advisory & Software Bill of Materials (SBOM)")
    dep_scanner = DependabotSimulator()
    vulns = dep_scanner.run_scan()

    print(f"{'Package':<15} {'Current':<10} {'Fixed in':<10} {'CVE Alert':<16} {'Severity'}")
    print(f"{'-'*65}")
    for v in vulns:
        s_color = CLR_RED if v['severity'] == 'CRITICAL' else (CLR_YELLOW if v['severity'] == 'HIGH' else CLR_BLUE)
        print(f"{v['package']:<15} {v['current']:<10} {v['fixed']:<10} {v['cve']:<16} {s_color}{v['severity']}{CLR_RESET}")

    print(f"\n{CLR_GREEN}Automated Pull Requests tersedia dari Dependabot untuk remediating dependensi di atas.{CLR_RESET}")

    # 4. Interactive Remediation & Audit Trail Summary
    subheader("Tahap 4: Security Audit Trail & Incident Summary")
    audit_event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": "developer-audit-bot",
        "repo": "enterprise-core-service",
        "action": "git_push.rejected",
        "reasons": [f["type"] for f in total_findings],
        "compliance_violations_count": len(violations),
        "open_vulnerabilities": len(vulns),
        "status": "INCIDENT_OPEN_TRIAGED"
    }

    print(f"{CLR_WHITE}Audit Log Payload (JSON Formatted):{CLR_RESET}")
    print(f"{CLR_CYAN}{json.dumps(audit_event, indent=2)}{CLR_RESET}")

    print(f"\n{CLR_BG_GREEN}{CLR_WHITE}{CLR_BOLD} [LAB SELESAI] {CLR_RESET}")
    print(f"{CLR_GREEN}Semua modul fondasi security compliance BAB-09 berhasil disimulasikan secara sukses.{CLR_RESET}\n")


if __name__ == "__main__":
    try:
        run_interactive_simulation()
    except KeyboardInterrupt:
        print(f"\n{CLR_YELLOW}Simulasi dihentikan pengguna.{CLR_RESET}")
        sys.exit(0)
