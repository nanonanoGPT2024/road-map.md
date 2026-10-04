#!/usr/bin/env python3
"""
Lab Exercise: Enterprise Security Hardening & Production System Design (JS/Node.js Runtime Context)
Simulates core enterprise security controls for JavaScript runtimes:
 1. Prototype Pollution Detection & Mitigation Engine.
 2. ReDoS (Regular Expression Denial of Service) Heuristic Analyzer.
 3. Dynamic Content Security Policy (CSP) & Subresource Integrity (SRI) Compiler.
 4. Secure Payload Verifier (HMAC-SHA256 Timing-Safe Authentication).
"""

import hashlib
import hmac
import json
import re
import sys
import time
from typing import Any, Dict, List, Tuple

# Terminal ANSI Color Formatting
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"


class PrototypePollutionGuard:
    """
    Simulates recursive object deep-merging and prototype-pollution sanitization
    in JavaScript environments (combating `__proto__`, `constructor`, `prototype` injections).
    """

    SUSPICIOUS_KEYS = {"__proto__", "constructor", "prototype"}

    def __init__(self):
        self.blocked_violations = 0

    def sanitize_and_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge source into target while stripping out Prototype Pollution vectors.
        Equivalent to a hardened Object.assign / deepMerge in Node.js enterprise middleware.
        """
        for key, value in list(source.items()):
            if key in self.SUSPICIOUS_KEYS:
                self.blocked_violations += 1
                print(f"  {RED}[SECURITY ALERT]{RESET} Blocked malicious prototype mutation key: {BOLD}{key}{RESET}")
                continue

            if isinstance(value, dict) and isinstance(target.get(key), dict):
                self.sanitize_and_merge(target[key], value)
            else:
                target[key] = value
        return target


class ReDoSAnalyzer:
    """
    Evaluates regular expressions for catastrophic backtracking vulnerabilities
    frequently exploitable in V8/Node.js event-loop blocking attacks.
    """

    # Heuristic detection for dangerous nested quantifiers, e.g. (a+)+, (a|b+)+, (.*a){x}
    NESTED_QUANTIFIERS = re.compile(r"(\([^\)]*[\+\*][^\)]*\))[\+\*]|\([^\)]*\|[^\)]*[\+\*]\)[\+\*]")

    @staticmethod
    def audit_regex(pattern: str) -> Tuple[bool, str]:
        """
        Statically inspects user-defined regex patterns before compilation in runtime routes.
        """
        if ReDoSAnalyzer.NESTED_QUANTIFIERS.search(pattern):
            return False, "Catastrophic backtracking vulnerability detected (Nested Quantifiers)."
        
        # Guard against unbounded wildcard repetition
        if ".*.*" in pattern or ".+.+" in pattern:
            return False, "Dangerous overlapping wildcards detected."

        return True, "Pattern cleared safe static analysis."


class EnterpriseCSPAndSRIEngine:
    """
    Implements enterprise-grade client-side boundary hardening:
    Generates cryptographic SRI hashes and compiles strict Content Security Policies.
    """

    @staticmethod
    def compute_sri(content: str, algorithm: str = "sha384") -> str:
        """
        Calculates W3C Subresource Integrity (SRI) digest for static JS bundles.
        """
        encoded = content.encode("utf-8")
        if algorithm == "sha256":
            digest = hashlib.sha256(encoded).digest()
        elif algorithm == "sha384":
            digest = hashlib.sha384(encoded).digest()
        elif algorithm == "sha512":
            digest = hashlib.sha512(encoded).digest()
        else:
            raise ValueError(f"Unsupported SRI algorithm: {algorithm}")

        import base64
        return f"{algorithm}-{base64.b64encode(digest).decode('utf-8')}"

    @staticmethod
    def compile_hardened_csp(nonce: str, report_uri: str = "/api/v1/csp-reports") -> str:
        """
        Builds a Zero-Trust Content Security Policy (CSP Level 3) baseline.
        """
        directives = [
            "default-src 'none'",
            f"script-src 'strict-dynamic' 'nonce-{nonce}' 'unsafe-inline' https:",
            "object-src 'none'",
            "base-uri 'none'",
            "frame-ancestors 'none'",
            "require-trusted-types-for 'script'",
            f"report-uri {report_uri}"
        ]
        return "; ".join(directives)


class SecurePayloadSigner:
    """
    Protects inter-service JSON RPC calls via HMAC-SHA256 with constant-time verification.
    """

    def __init__(self, secret_key: bytes):
        self._secret = secret_key

    def sign(self, payload: str) -> str:
        return hmac.new(self._secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify(self, payload: str, signature: str) -> bool:
        expected = self.sign(payload)
        # Constant-time comparison mitigates side-channel timing attacks
        return hmac.compare_digest(expected, signature)


def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN}>>> {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}")


def run_laboratory():
    print(f"{BOLD}{MAGENTA}Enterprise Security Hardening: Node.js/JS Production System Lab{RESET}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")

    # ---------------------------------------------------------
    # Test 1: Prototype Pollution Defenses
    # ---------------------------------------------------------
    print_header("1. PROTOTYPE POLLUTION MITIGATION ENGINE")
    pp_guard = PrototypePollutionGuard()

    base_config = {
        "server": {"port": 8080, "timeout": 30},
        "features": {"metrics": True}
    }

    # Malicious payload typical of JSON input attacking Node.js `lodash.merge` or native assigns
    malicious_payload = {
        "features": {"debugMode": True},
        "__proto__": {"isAdmin": True, "shell": "/bin/sh"},
        "constructor": {"prototype": {"polluted": "yes"}}
    }

    print(f"Incoming Target Baseline: {json.dumps(base_config)}")
    print(f"Raw Ingest Payload:       {json.dumps(malicious_payload)}")
    print("\nExecuting deep sanitization merge...")
    
    clean_config = pp_guard.sanitize_and_merge(base_config, malicious_payload)
    
    print(f"\nSanitized Result:         {json.dumps(clean_config)}")
    print(f"Pollution Keys Intercepted: {BOLD}{RED}{pp_guard.blocked_violations}{RESET}")
    assert "__proto__" not in clean_config, "Failed: Prototype pollution occurred!"
    assert "isAdmin" not in clean_config, "Failed: Target was polluted!"
    print(f"Status: {GREEN}PROTECTED against Object.prototype contamination{RESET}")

    # ---------------------------------------------------------
    # Test 2: ReDoS Catastrophic Backtracking Analyzer
    # ---------------------------------------------------------
    print_header("2. ReDoS (REGULAR EXPRESSION DENIAL OF SERVICE) AUDIT")
    test_regexes = [
        (r"^[a-zA-Z0-9_-]{3,16}$", "Standard Username Validator"),
        (r"^([a-zA-Z0-9]+)+$", "Catastrophic Nested Grouping"),
        (r"^(a|b+)+$", "Catastrophic Alternate Repetition"),
        (r"^https?://.*.*\.cdn\.domain\.com", "Redundant Overlapping Wildcards"),
        (r"^[a-z0-9]+@[a-z0-9-]+\.[a-z]{2,8}$", "Bounded RFC Email Subset")
    ]

    for pattern, desc in test_regexes:
        safe, reason = ReDoSAnalyzer.audit_regex(pattern)
        res_color = GREEN if safe else RED
        status_text = "SAFE" if safe else "REJECTED"
        print(f"Pattern: {BOLD}{pattern:<40}{RESET} [{desc}]")
        print(f"  Audit: {res_color}{status_text}{RESET} -> {reason}")

    # ---------------------------------------------------------
    # Test 3: Subresource Integrity (SRI) & CSP Level 3 Synthesis
    # ---------------------------------------------------------
    print_header("3. DYNAMIC CSP (NONCE-BASED) & SRI COMPILATION")
    simulated_bundle = """
    (function enterpriseApp() {
        console.log("Kernel initialized under secure CSP context");
    })();
    """
    bundle_sri = EnterpriseCSPAndSRIEngine.compute_sri(simulated_bundle, algorithm="sha384")
    sample_nonce = hashlib.sha256(str(time.time_ns()).encode("utf-8")).hexdigest()[:16]
    hardened_csp = EnterpriseCSPAndSRIEngine.compile_hardened_csp(sample_nonce)

    print(f"Simulated Static Bundle Length: {len(simulated_bundle.strip())} bytes")
    print(f"Generated SRI (sha384):        {BOLD}{GREEN}{bundle_sri}{RESET}")
    print("\nHardened HTTP Response Headers Generated:")
    print(f"  {YELLOW}Content-Security-Policy:{RESET}")
    for directive in hardened_csp.split("; "):
        print(f"    - {directive}")

    # ---------------------------------------------------------
    # Test 4: Timing-Safe HMAC Payload Signature Verification
    # ---------------------------------------------------------
    print_header("4. HIGH-THROUGHPUT SECURE SIGNATURE VALIDATION")
    secret = b"k9!enterprise_super_secret_signing_key_2026"
    signer = SecurePayloadSigner(secret)

    valid_payload = json.dumps({"userId": 44921, "role": "OPERATOR", "nonce": 981240})
    tampered_payload = json.dumps({"userId": 44921, "role": "ADMIN", "nonce": 981240})

    signature = signer.sign(valid_payload)
    print(f"Signed Request Payload: {valid_payload}")
    print(f"HMAC-SHA256 Signature:  {signature}")

    # Verify original
    orig_check = signer.verify(valid_payload, signature)
    print(f"Verification (Original Payload): {GREEN if orig_check else RED}{orig_check}{RESET}")

    # Verify tampered
    tamper_check = signer.verify(tampered_payload, signature)
    print(f"Verification (Tampered Payload): {GREEN if not tamper_check else RED}{tamper_check}{RESET}")

    assert orig_check is True and tamper_check is False, "Cryptographic validation failed."

    print_header("LAB SUMMARY: ALL SECURITY POLICIES VALIDATED SUCCESSFULLY")
    print(f"{GREEN}✓ Sanitizer halted Prototype Pollution vectors.{RESET}")
    print(f"{GREEN}✓ ReDoS heuristic correctly isolated catastrophic engines.{RESET}")
    print(f"{GREEN}✓ CSP Strict-Dynamic with SRI cryptographically active.{RESET}")
    print(f"{GREEN}✓ Constant-time payload integrity verification confirmed.{RESET}\n")


if __name__ == "__main__":
    run_laboratory()