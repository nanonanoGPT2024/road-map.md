#!/usr/bin/env python3
"""
Lab: GitHub Platform Engineering & Enterprise Governance Engine
Focus: Policy-as-Code Ruleset Engine, Webhook Cryptographic Verification (HMAC-SHA256),
       and OIDC Federated Identity Claim Evaluator.
"""

import sys
import json
import hmac
import hashlib
import time
import base64
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple

# ANSI Terminal Styler
class Style:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    GREEN   = "\033[92m"
    RED     = "\033[91m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    GRAY    = "\033[90m"

@dataclass
class PolicyEvaluationResult:
    rule_name: str
    passed: bool
    severity: str  # BLOCKER, HIGH, MEDIUM, LOW
    message: str
    execution_time_ms: float

@dataclass
class PullRequestContext:
    pr_id: int
    repository: str
    target_branch: str
    author: str
    is_draft: bool
    commits_signed: bool
    linear_history: bool
    codeowner_approvals: List[str]
    required_codeowners: List[str]
    sast_vulnerabilities_count: int
    oidc_claims: Dict[str, Any]

class WebhookSecurityService:
    """Simulates GitHub Enterprise Webhook cryptographic validation (HMAC-SHA256)."""
    
    @staticmethod
    def sign_payload(secret: str, payload_bytes: bytes) -> str:
        """Generates the X-Hub-Signature-256 header value."""
        mac = hmac.new(secret.encode('utf-8'), msg=payload_bytes, digestmod=hashlib.sha256)
        return f"sha256={mac.hexdigest()}"

    @staticmethod
    def verify_signature(secret: str, payload_bytes: bytes, signature_header: str) -> bool:
        """Constant-time cryptographic validation to prevent timing attacks."""
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected_sig = WebhookSecurityService.sign_payload(secret, payload_bytes)
        return hmac.compare_digest(expected_sig, signature_header)

class PlatformGovernanceEngine:
    """
    Evaluates enterprise branch protection rules, OIDC federated identity claims,
    and Policy-as-Code standards for deployment authorization.
    """

    def __init__(self, target_environment: str = "production"):
        self.target_environment = target_environment
        self.audit_log: List[Dict[str, Any]] = []

    def verify_oidc_claims(self, claims: Dict[str, Any], repository: str) -> Tuple[bool, str]:
        """
        Validates GitHub Actions OIDC Token claims against Enterprise IAM policies.
        Prevents credential leakage by strictly matching 'sub' and 'aud' claims.
        """
        expected_iss = "https://token.actions.githubusercontent.com"
        expected_aud = "sts.amazonaws.com"
        expected_sub_prefix = f"repo:{repository}:"

        if claims.get("iss") != expected_iss:
            return False, f"Invalid Issuer: expected {expected_iss}, got {claims.get('iss')}"
        
        if claims.get("aud") != expected_aud:
            return False, f"Invalid Audience: expected {expected_aud}, got {claims.get('aud')}"
        
        sub = claims.get("sub", "")
        if not sub.startswith(expected_sub_prefix):
            return False, f"Subject claim violation: {sub} does not belong to {expected_sub_prefix}"

        # Production deployments strictly require releases or protected main tags
        if self.target_environment == "production":
            environment_claim = claims.get("environment")
            if environment_claim != "production":
                return False, f"OIDC environment claim mismatch: expected 'production', got '{environment_claim}'"

        return True, "OIDC Claims validated successfully for cloud federation."

    def evaluate_ruleset(self, ctx: PullRequestContext) -> List[PolicyEvaluationResult]:
        """Runs the test suite of Policy-as-Code branch rulesets."""
        results = []

        # Rule 1: Signed Commits Enforcement
        t0 = time.perf_counter()
        passed = ctx.commits_signed
        results.append(PolicyEvaluationResult(
            rule_name="GPG/SSH Commit Signing Enforcement",
            passed=passed,
            severity="BLOCKER",
            message="All commits in PR must have valid cryptographic signatures." if not passed else "Signatures verified.",
            execution_time_ms=(time.perf_counter() - t0) * 1000
        ))

        # Rule 2: Strict CODEOWNERS Enforcement
        t0 = time.perf_counter()
        missing_approvers = [req for req in ctx.required_codeowners if req not in ctx.codeowner_approvals]
        passed = len(missing_approvers) == 0
        results.append(PolicyEvaluationResult(
            rule_name="Enterprise CODEOWNERS Quorum",
            passed=passed,
            severity="BLOCKER",
            message=f"Missing required approvals from: {missing_approvers}" if not passed else "CODEOWNERS quorum satisfied.",
            execution_time_ms=(time.perf_counter() - t0) * 1000
        ))

        # Rule 3: Linear History Enforcement (No merge bubbles)
        t0 = time.perf_counter()
        passed = ctx.linear_history
        results.append(PolicyEvaluationResult(
            rule_name="Linear History (Rebase/Squash Required)",
            passed=passed,
            severity="HIGH",
            message="Merge commits detected. Target branch mandates fast-forward rebase/squash." if not passed else "Linear history intact.",
            execution_time_ms=(time.perf_counter() - t0) * 1000
        ))

        # Rule 4: Zero-Tolerance SAST Security Gate
        t0 = time.perf_counter()
        passed = ctx.sast_vulnerabilities_count == 0
        results.append(PolicyEvaluationResult(
            rule_name="Static Application Security Testing (SAST) Gate",
            passed=passed,
            severity="BLOCKER",
            message=f"Blocking: Detected {ctx.sast_vulnerabilities_count} unresolved vulnerabilities." if not passed else "Zero critical/high vulnerabilities.",
            execution_time_ms=(time.perf_counter() - t0) * 1000
        ))

        # Rule 5: OIDC Identity Federation Compliance
        t0 = time.perf_counter()
        oidc_ok, oidc_msg = self.verify_oidc_claims(ctx.oidc_claims, ctx.repository)
        results.append(PolicyEvaluationResult(
            rule_name="GitHub OIDC IAM Federation Assurance",
            passed=oidc_ok,
            severity="BLOCKER",
            message=oidc_msg,
            execution_time_ms=(time.perf_counter() - t0) * 1000
        ))

        return results

    def process_pull_request(self, raw_payload: bytes, signature: str, secret: str, ctx: PullRequestContext) -> bool:
        """Core orchestration pipeline: Verifies Ingress Auth -> Evaluates Governance -> Dispatches Decision."""
        print(f"\n{Style.BOLD}{Style.BLUE}=== Processing PR #{ctx.pr_id} on [{ctx.repository}] -> target: '{ctx.target_branch}' ==={Style.RESET}")

        # Step 1: Ingress Webhook Verification
        print(f"{Style.CYAN}[1/3] Cryptographic Webhook Ingress Verification...{Style.RESET}")
        valid_signature = WebhookSecurityService.verify_signature(secret, raw_payload, signature)
        if not valid_signature:
            print(f"  {Style.RED}✖ FAIL:{Style.RESET} Ingress HMAC-SHA256 signature verification failed. Request dropped.")
            return False
        print(f"  {Style.GREEN}✔ PASS:{Style.RESET} Signature matches. Payload authenticity confirmed via constant-time HMAC.")

        # Step 2: Policy-as-Code Governance Checks
        print(f"{Style.CYAN}[2/3] Executing Enterprise Rulesets & Governance Pipeline...{Style.RESET}")
        results = self.evaluate_ruleset(ctx)
        
        all_passed = True
        for res in results:
            badge = f"{Style.GREEN}✔ PASS{Style.RESET}" if res.passed else f"{Style.RED}✖ FAIL [{res.severity}]{Style.RESET}"
            print(f"  [{badge}] {Style.BOLD}{res.rule_name}{Style.RESET} ({res.execution_time_ms:.3f}ms)")
            print(f"         {Style.GRAY}↳ {res.message}{Style.RESET}")
            if not res.passed and res.severity == "BLOCKER":
                all_passed = False

        # Step 3: Deployment Gate Authorization
        print(f"{Style.CYAN}[3/3] Deployment Gate Verdict...{Style.RESET}")
        if all_passed:
            print(f"  {Style.BOLD}{Style.GREEN}>>> GATE STATUS: AUTHORIZED FOR MERGE & DEPLOYMENT <<<{Style.RESET}")
        else:
            print(f"  {Style.BOLD}{Style.RED}>>> GATE STATUS: REJECTED (Compliance Violations Present) <<<{Style.RESET}")

        # Record structured audit log
        self.audit_log.append({
            "pr_id": ctx.pr_id,
            "repo": ctx.repository,
            "timestamp": time.time(),
            "decision": "AUTHORIZED" if all_passed else "REJECTED",
            "evaluations": len(results)
        })

        return all_passed

def run_simulation():
    webhook_secret = "ghp_super_secret_enterprise_token_987654321"
    engine = PlatformGovernanceEngine(target_environment="production")

    print(f"{Style.BOLD}{Style.MAGENTA}======================================================================{Style.RESET}")
    print(f"{Style.BOLD}{Style.MAGENTA}  GitHub Platform Engineering Lab: Rulesets, OIDC & Governance Engine  {Style.RESET}")
    print(f"{Style.BOLD}{Style.MAGENTA}======================================================================{Style.RESET}")

    # =========================================================================
    # SCENARIO 1: Non-Compliant PR (Unsigned commits, missing CODEOWNER, OIDC mismatch)
    # =========================================================================
    payload_bad = json.dumps({"action": "opened", "number": 101, "sender": "junior-dev"}).encode('utf-8')
    sig_bad = WebhookSecurityService.sign_payload(webhook_secret, payload_bad)

    bad_ctx = PullRequestContext(
        pr_id=101,
        repository="enterprise-bank/payment-core",
        target_branch="main",
        author="junior-dev",
        is_draft=False,
        commits_signed=False,          # Violation
        linear_history=True,
        codeowner_approvals=["lead-frontend"],
        required_codeowners=["sec-lead", "principal-infra"], # Violation
        sast_vulnerabilities_count=2,  # Violation
        oidc_claims={
            "iss": "https://token.actions.githubusercontent.com",
            "aud": "sts.amazonaws.com",
            "sub": "repo:enterprise-bank/payment-core:ref:refs/heads/feature-patch",
            "environment": "staging"    # Violation: PR targets production
        }
    )
    engine.process_pull_request(payload_bad, sig_bad, webhook_secret, bad_ctx)

    # =========================================================================
    # SCENARIO 2: Cryptographic Tampering Attack Simulation
    # =========================================================================
    print(f"\n{Style.BOLD}{Style.YELLOW}--- Simulating Man-in-the-Middle Webhook Tampering ---{Style.RESET}")
    tampered_payload = json.dumps({"action": "synchronize", "number": 102, "malicious_injection": True}).encode('utf-8')
    invalid_signature = "sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    
    dummy_ctx = PullRequestContext(
        pr_id=102, repository="enterprise-bank/payment-core", target_branch="main",
        author="attacker", is_draft=False, commits_signed=True, linear_history=True,
        codeowner_approvals=["sec-lead"], required_codeowners=["sec-lead"],
        sast_vulnerabilities_count=0, oidc_claims={}
    )
    engine.process_pull_request(tampered_payload, invalid_signature, webhook_secret, dummy_ctx)

    # =========================================================================
    # SCENARIO 3: Fully Compliant Enterprise Pull Request
    # =========================================================================
    payload_good = json.dumps({"action": "synchronize", "number": 103, "sender": "sr-platform-eng"}).encode('utf-8')
    sig_good = WebhookSecurityService.sign_payload(webhook_secret, payload_good)

    good_ctx = PullRequestContext(
        pr_id=103,
        repository="enterprise-bank/payment-core",
        target_branch="main",
        author="sr-platform-eng",
        is_draft=False,
        commits_signed=True,
        linear_history=True,
        codeowner_approvals=["sec-lead", "principal-infra"],
        required_codeowners=["sec-lead", "principal-infra"],
        sast_vulnerabilities_count=0,
        oidc_claims={
            "iss": "https://token.actions.githubusercontent.com",
            "aud": "sts.amazonaws.com",
            "sub": "repo:enterprise-bank/payment-core:environment:production",
            "environment": "production"
        }
    )
    engine.process_pull_request(payload_good, sig_good, webhook_secret, good_ctx)

    # =========================================================================
    # AUDIT LOG SUMMARY
    # =========================================================================
    print(f"\n{Style.BOLD}{Style.MAGENTA}=== Enterprise Audit Trail Report ==={Style.RESET}")
    print(json.dumps(engine.audit_log, indent=2))

if __name__ == "__main__":
    run_simulation()
    sys.exit(0)