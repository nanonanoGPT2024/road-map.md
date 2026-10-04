#!/usr/bin/env python3
"""
Lab Hands-on: Repository Security, Compliance, & Secrets Management (Deep Dive)
Category: 01-Core-Foundations | Chapter: 09 | Module: 02

This script simulates an enterprise Git Security Lifecycle:
1. Shannon Entropy & Regex Secret Detection Engine.
2. Pre-commit Hook Enforcer (Static Analysis & Secret Interception).
3. Mock Git Object Model (Blobs, Trees, DAG-based Commits).
4. Automated History Remediation (Simulating git-filter-repo / BFG DAG rewrites).
5. Cryptographic SHA-1 Commit Graph Recalculation & Compliance Auditing.
"""

import collections
import dataclasses
import hashlib
import json
import math
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

# --- ANSI Terminal Color Formatting ---
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"


@dataclasses.dataclass
class SecretFinding:
    rule_name: str
    line_number: int
    secret_preview: str
    entropy: float
    is_entropy_violation: bool


@dataclasses.dataclass
class GitCommit:
    commit_sha: str
    parent_sha: Optional[str]
    author: str
    timestamp: float
    message: str
    tree: Dict[str, str]  # Path -> File content (blob)


# ============================================================================
# 1. SECRET DETECTION & SHANNON ENTROPY ENGINE
# ============================================================================

KNOWN_PATTERNS = {
    "AWS Access Key ID": re.compile(r"\b(AKIA|ASIA|AROA)[A-Z0-9]{16}\b"),
    "GitHub Personal Access Token": re.compile(r"\bghp_[A-Za-z0-9_]{36}\b"),
    "Generic Private Key": re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    "High-Entropy API Key Candidate": re.compile(r'(?:api_key|token|secret)\s*[:=]\s*["\']([A-Za-z0-9_\-\.]{24,})["\']', re.IGNORECASE)
}


def calculate_shannon_entropy(data: str) -> float:
    """
    Computes Shannon Entropy: H(X) = -sum(P(x) * log2(P(x))).
    Higher entropy indicates random/pseudo-random cryptographic keys.
    """
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    frequencies = collections.Counter(data)
    for count in frequencies.values():
        p_x = count / length
        entropy -= p_x * math.log2(p_x)
    return round(entropy, 4)


def scan_file_content(filepath: str, content: str, entropy_threshold: float = 4.2) -> List[SecretFinding]:
    """
    Analyzes line-by-line file content using signature matching and entropy analysis.
    """
    findings = []
    lines = content.splitlines()

    for idx, line in enumerate(lines, start=1):
        # 1. Regex signature scan
        for rule_name, pattern in KNOWN_PATTERNS.items():
            matches = pattern.finditer(line)
            for match in matches:
                matched_str = match.group(0)
                entropy = calculate_shannon_entropy(matched_str)
                findings.append(SecretFinding(
                    rule_name=rule_name,
                    line_number=idx,
                    secret_preview=matched_str[:4] + "..." + matched_str[-4:] if len(matched_str) > 8 else "***",
                    entropy=entropy,
                    is_entropy_violation=entropy >= entropy_threshold
                ))

        # 2. General token-level entropy scan for suspicious assignments
        tokens = re.findall(r'[A-Za-z0-9+/=_\-]{20,}', line)
        for token in tokens:
            entropy = calculate_shannon_entropy(token)
            if entropy >= entropy_threshold:
                # Deduplicate if already caught by regex
                if not any(f.line_number == idx and f.secret_preview.startswith(token[:4]) for f in findings):
                    findings.append(SecretFinding(
                        rule_name="Unstructured High-Entropy Token",
                        line_number=idx,
                        secret_preview=token[:4] + "..." + token[-4:],
                        entropy=entropy,
                        is_entropy_violation=True
                    ))

    return findings


# ============================================================================
# 2. MOCK GIT ENGINE (DAG & SHA-1 RECALCULATION)
# ============================================================================

class MockRepository:
    def __init__(self, name: str):
        self.name = name
        self.commit_history: List[GitCommit] = []
        self.head: Optional[str] = None

    def calculate_commit_hash(self, parent_sha: Optional[str], tree: Dict[str, str], message: str, timestamp: float) -> str:
        """
        Simulates Git's SHA-1 hashing of tree objects, author metadata, and parent reference.
        """
        payload = {
            "parent": parent_sha or "0" * 40,
            "tree": tree,
            "message": message,
            "timestamp": timestamp
        }
        serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha1(serialized).hexdigest()

    def commit(self, author: str, message: str, files: Dict[str, str], bypass_hooks: bool = False) -> Optional[str]:
        """
        Creates a commit. Executes pre-commit hooks unless bypassed via --no-verify.
        """
        if not bypass_hooks:
            # Simulate Pre-Commit Git Hook
            if not self.run_pre_commit_hook(files):
                print(f"{RED}[HOOK REJECTED]{RESET} Commit blocked by Pre-commit Security Policy.")
                return None

        # Build commit object
        current_tree = {}
        if self.commit_history:
            current_tree = self.commit_history[-1].tree.copy()
        current_tree.update(files)

        now = time.time()
        sha = self.calculate_commit_hash(self.head, current_tree, message, now)
        commit = GitCommit(
            commit_sha=sha,
            parent_sha=self.head,
            author=author,
            timestamp=now,
            message=message,
            tree=current_tree
        )
        self.commit_history.append(commit)
        self.head = sha
        return sha

    def run_pre_commit_hook(self, staged_files: Dict[str, str]) -> bool:
        """
        Pre-commit validation interceptor: evaluates staged files before commit packaging.
        """
        violations = False
        for filepath, content in staged_files.items():
            findings = scan_file_content(filepath, content)
            if findings:
                violations = True
                print(f"{RED}[PRE-COMMIT BLOCK]{RESET} Secrets detected in {BOLD}{filepath}{RESET}:")
                for f in findings:
                    print(f"  -> Line {f.line_number}: {YELLOW}{f.rule_name}{RESET} "
                          f"(Entropy: {f.entropy:.2f}, Snippet: {f.secret_preview})")
        return not violations


# ============================================================================
# 3. HISTORY SCANNING & REMEDIATION (GIT-FILTER-REPO ENGINE)
# ============================================================================

def audit_full_repository_history(repo: MockRepository) -> Dict[str, List[SecretFinding]]:
    """
    Performs full git log -p traversal, scanning every commit object for secret exposures.
    """
    history_findings: Dict[str, List[SecretFinding]] = collections.defaultdict(list)
    for commit in repo.commit_history:
        for filepath, content in commit.tree.items():
            findings = scan_file_content(filepath, content)
            if findings:
                history_findings[commit.commit_sha].extend(findings)
    return history_findings


def execute_git_filter_repo(repo: MockRepository, patterns_to_redact: List[re.Pattern]) -> MockRepository:
    """
    Simulates `git-filter-repo` / BFG. Rewrites history by redacting matching secrets,
    then systematically recalculates child commits to maintain DAG cryptographic validity.
    """
    print(f"\n{CYAN}[REWRITING DAG]{RESET} Initializing BFG/git-filter-repo DAG reconstruction...")
    rewritten_repo = MockRepository(repo.name + "_sanitized")
    parent_map: Dict[str, str] = {}  # old_sha -> new_sha

    for commit in repo.commit_history:
        new_tree: Dict[str, str] = {}
        for filepath, content in commit.tree.items():
            sanitized_content = content
            for pat in patterns_to_redact:
                sanitized_content = pat.sub("*****[REDACTED_BY_SECOPS]*****", sanitized_content)
            new_tree[filepath] = sanitized_content

        # Resolve newly minted parent pointer
        new_parent = parent_map.get(commit.parent_sha) if commit.parent_sha else None
        new_sha = rewritten_repo.calculate_commit_hash(new_parent, new_tree, commit.message, commit.timestamp)

        rewritten_commit = GitCommit(
            commit_sha=new_sha,
            parent_sha=new_parent,
            author=commit.author,
            timestamp=commit.timestamp,
            message=commit.message,
            tree=new_tree
        )
        rewritten_repo.commit_history.append(rewritten_commit)
        parent_map[commit.commit_sha] = new_sha
        rewritten_repo.head = new_sha

        print(f"  Commit {YELLOW}{commit.commit_sha[:8]}{RESET} -> {GREEN}{new_sha[:8]}{RESET} "
              f"| Parent: {str(new_parent)[:8]} | Ref: {commit.message}")

    return rewritten_repo


# ============================================================================
# 4. EXECUTION PIPELINE & BENCHMARK LAB RUNNER
# ============================================================================

def main():
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{BOLD}{MAGENTA} LAB EXERCISE: REPOSITORY SECURITY, SECRETS MANAGEMENT & DAG REWRITE {RESET}")
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}\n")

    repo = MockRepository("production-microservice")

    # Phase 1: Baseline Clean Commit
    print(f"{BOLD}[PHASE 1: LEGITIMATE DEVELOPMENT WORKFLOW]{RESET}")
    app_py = "import os\n\ndef run():\n    return 'System Online'\n"
    c1 = repo.commit("alice@infra.local", "feat: initial service scaffold", {"src/app.py": app_py})
    print(f"{GREEN}[SUCCESS]{RESET} Commit generated: {c1}\n")

    # Phase 2: Inadvertent Secret Addition with Pre-Commit Interception
    print(f"{BOLD}[PHASE 2: PRE-COMMIT HOOK DEFENSE EVALUATION]{RESET}")
    compromised_config = (
        "# Configuration File\n"
        "AWS_REGION = 'us-east-1'\n"
        "AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'\n"  # Known AWS regex target
        "GH_TOKEN = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'\n"  # GitHub PAT
        "HIGH_ENTROPY_KEY = 'x9u#L2_mZ!99a1qP82d001Nzm'\n"  # Entropy Target
    )

    print("Attempting to commit files containing plain-text keys...")
    c2_attempt = repo.commit("bob@dev.local", "feat: added external cloud provider client", {"config/cloud.py": compromised_config})
    assert c2_attempt is None, "Hook should have blocked this commit!"
    print(f"{CYAN}[VERIFIED]{RESET} Pre-commit hook successfully protected upstream branches.\n")

    # Phase 3: Rogue Bypass (--no-verify simulation)
    print(f"{BOLD}[PHASE 3: SIMULATING HOOK BYPASS (--no-verify)]{RESET}")
    print("Developer bypassed hook using `git commit --no-verify`...")
    c2 = repo.commit("bob@dev.local", "feat: added external cloud provider client", {"config/cloud.py": compromised_config}, bypass_hooks=True)
    print(f"{RED}[LEAK PERSISTED]{RESET} Secret introduced into history: {c2}")

    # Phase 4: Downstream development continues
    c3 = repo.commit("charlie@dev.local", "fix: optimize latency in network handler", {"src/utils.py": "def ping(): return True\n"}, bypass_hooks=True)
    print(f"Subsequent commit created on top: {c3}\n")

    # Phase 5: Repository Security Audit & Compliance Assessment
    print(f"{BOLD}[PHASE 4: SECRETS AUDIT TRAVERSAL ON FULL GIT DAG]{RESET}")
    findings_map = audit_full_repository_history(repo)
    print(f"Total infected commits found: {RED}{len(findings_map)}{RESET}")
    for sha, findings in findings_map.items():
        print(f" Commit {YELLOW}{sha[:10]}{RESET}:")
        for f in findings:
            print(f"   - Rule: {BOLD}{f.rule_name}{RESET} | Line: {f.line_number} | "
                  f"Entropy: {f.entropy} | Preview: {f.secret_preview}")

    # Phase 6: Automated Incident Remediation (Filter-Repo Emulation)
    print(f"\n{BOLD}[PHASE 5: AUTOMATED DAG REWRITE & INCIDENT REMEDIATION]{RESET}")
    patterns_to_strip = list(KNOWN_PATTERNS.values())
    sanitized_repo = execute_git_filter_repo(repo, patterns_to_strip)

    # Phase 7: Post-Remediation Verification
    print(f"\n{BOLD}[PHASE 6: POST-REMEDIATION AUDIT VERIFICATION]{RESET}")
    new_findings = audit_full_repository_history(sanitized_repo)
    if not new_findings:
        print(f"{GREEN}[AUDIT PASSED]{RESET} Sanitized DAG contains 0 secret findings across all historical commits.")
    else:
        print(f"{RED}[AUDIT FAILED]{RESET} Secrets remain in history!")

    # Check Hash Divergence Proof
    print(f"\n{BOLD}[CRYPTOGRAPHIC INTEGRITY PROOF]{RESET}")
    print(f"Original HEAD SHA  : {RED}{repo.head}{RESET}")
    print(f"Remediated HEAD SHA: {GREEN}{sanitized_repo.head}{RESET}")
    assert repo.head != sanitized_repo.head, "DAG rewrite must alter historical and tip hashes."
    print("SHA mutation verifies commit tree authenticity and non-repudiation guarantees.")
    print(f"\n{GREEN}{BOLD}Lab exercise executed successfully.{RESET}")


if __name__ == "__main__":
    main()