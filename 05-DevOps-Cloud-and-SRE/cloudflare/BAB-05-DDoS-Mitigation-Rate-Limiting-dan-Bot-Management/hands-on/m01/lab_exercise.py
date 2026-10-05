#!/usr/bin/env python3
"""
Lab Exercise: Cloudflare DDoS Mitigation, Rate Limiting, & Bot Management Simulation
BAB-05: Cloudflare Security Core Architecture
Language: Python 3 (Standard Library Only)
"""

import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# --- ANSI Terminal Color Palette ---
class Colors:
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
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


class ActionType(Enum):
    ALLOW = "ALLOW (200 OK)"
    JS_CHALLENGE = "JS_CHALLENGE (Managed)"
    RATE_LIMITED = "RATE_LIMITED (429 Too Many Requests)"
    DROP_DDOS = "DROP_DDOS (Edge Drop / 403 Forbidden)"


@dataclass
class ClientRequest:
    ip: str
    user_agent: str
    path: str
    has_valid_ja3: bool
    solves_pow_challenge: bool
    is_known_search_engine: bool
    request_rate: float  # req/sec


@dataclass
class RateLimiterBucket:
    capacity: float = 10.0
    tokens: float = 10.0
    refill_rate: float = 2.0  # tokens per second
    last_update: float = field(default_factory=time.time)
    penalty_until: float = 0.0

    def consume(self, cost: float = 1.0) -> bool:
        now = time.time()
        if now < self.penalty_until:
            return False

        # Refill tokens based on elapsed time
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_update = now

        if self.tokens >= cost:
            self.tokens -= cost
            return True
        else:
            # Trigger temporary penalty box (Cloudflare 60s cooldown style)
            self.penalty_until = now + 3.0
            return False


class CloudflareEdgeSimulator:
    def __init__(self):
        self.rate_limiters: Dict[str, RateLimiterBucket] = {}
        self.ddos_threshold_rps = 15.0
        self.known_good_crawlers = ["Googlebot/2.1", "bingbot/2.0"]
        self.total_processed = 0
        self.stats = {
            ActionType.ALLOW: 0,
            ActionType.JS_CHALLENGE: 0,
            ActionType.RATE_LIMITED: 0,
            ActionType.DROP_DDOS: 0,
        }

    def compute_bot_score(self, req: ClientRequest) -> int:
        """
        Calculates Cloudflare Bot Score (1 - 99):
        1 - 29: Likely Automated / Malicious Bot
        30 - 79: Likely Semi-Automated / Unknown
        80 - 99: Verified Human / Legitimate Crawler
        """
        if req.is_known_search_engine and req.user_agent in self.known_good_crawlers:
            return 99

        score = 50
        if req.has_valid_ja3:
            score += 25
        else:
            score -= 30

        if "python-requests" in req.user_agent.lower() or "curl" in req.user_agent.lower():
            score -= 35

        if req.request_rate > 8.0:
            score -= 20

        return max(1, min(99, score))

    def evaluate_request(self, req: ClientRequest) -> Tuple[ActionType, int, str]:
        self.total_processed += 1
        bot_score = self.compute_bot_score(req)

        # 1. DDoS Mitigation Layer (Volumetric Edge Defense)
        if req.request_rate >= self.ddos_threshold_rps:
            action = ActionType.DROP_DDOS
            reason = f"Volumetric attack detected ({req.request_rate:.1f} rps >= {self.ddos_threshold_rps} rps threshold)"
            self.stats[action] += 1
            return action, bot_score, reason

        # 2. Bot Management Layer
        if bot_score < 30:
            if not req.solves_pow_challenge:
                action = ActionType.DROP_DDOS
                reason = f"Bot Score {bot_score} failed or refused Managed Challenge"
                self.stats[action] += 1
                return action, bot_score, reason
            else:
                action = ActionType.JS_CHALLENGE
                reason = f"Bot Score {bot_score} solved challenge; granted temporary edge pass"
                self.stats[action] += 1
                return action, bot_score, reason

        # 3. Rate Limiting Engine (Token Bucket with Penalty Window)
        if req.ip not in self.rate_limiters:
            self.rate_limiters[req.ip] = RateLimiterBucket()

        bucket = self.rate_limiters[req.ip]
        if not bucket.consume(1.0):
            action = ActionType.RATE_LIMITED
            penalty_remaining = max(0.0, bucket.penalty_until - time.time())
            reason = f"Exceeded burst limit (Tokens: {bucket.tokens:.1f}/{bucket.capacity}, Penalty Box: {penalty_remaining:.1f}s)"
            self.stats[action] += 1
            return action, bot_score, reason

        # 4. Clean Traffic Allowed
        action = ActionType.ALLOW
        reason = f"Valid request pass (Bot Score: {bot_score}, Tokens: {bucket.tokens:.1f})"
        self.stats[action] += 1
        return action, bot_score, reason


def render_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
================================================================================
       CLOUDFLARE EDGE ENGINE SIMULATOR: DDOS, RATE LIMITING & BOT MGMT
                     Hands-on Lab Exercise - Module 01
================================================================================{Colors.RESET}"""
    print(banner)


def render_action_tag(action: ActionType) -> str:
    if action == ActionType.ALLOW:
        return f"{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} {action.value} {Colors.RESET}"
    elif action == ActionType.JS_CHALLENGE:
        return f"{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD} {action.value} {Colors.RESET}"
    elif action == ActionType.RATE_LIMITED:
        return f"{Colors.YELLOW}{Colors.BOLD} {action.value} {Colors.RESET}"
    else:
        return f"{Colors.BG_RED}{Colors.WHITE}{Colors.BOLD} {action.value} {Colors.RESET}"


def run_single_simulation(engine: CloudflareEdgeSimulator, req: ClientRequest, label: str):
    print(f"\n{Colors.BOLD}--> Simulating Scenario: {Colors.WHITE}{label}{Colors.RESET}")
    print(f"    {Colors.DIM}Client IP:{Colors.RESET} {req.ip} | {Colors.DIM}UA:{Colors.RESET} {req.user_agent}")
    print(f"    {Colors.DIM}Rate:{Colors.RESET} {req.request_rate:.1f} req/s | {Colors.DIM}JA3:{Colors.RESET} {req.has_valid_ja3} | {Colors.DIM}Crawler:{Colors.RESET} {req.is_known_search_engine}")

    action, bot_score, reason = engine.evaluate_request(req)
    tag = render_action_tag(action)

    print(f"    {Colors.BOLD}Edge Decision:{Colors.RESET} {tag}")
    print(f"    {Colors.BOLD}Bot Score:{Colors.RESET} {Colors.MAGENTA}{bot_score}/99{Colors.RESET} | {Colors.DIM}Details:{Colors.RESET} {reason}")


def run_ddos_burst_simulation(engine: CloudflareEdgeSimulator):
    print(f"\n{Colors.RED}{Colors.BOLD}[*] Launching Distributed HTTP Flood Simulation (50 rapid requests)...{Colors.RESET}")
    botnet_ips = [f"198.51.100.{i}" for i in range(1, 11)]

    for idx in range(1, 26):
        ip = random.choice(botnet_ips)
        is_flood = idx > 5
        req = ClientRequest(
            ip=ip,
            user_agent="Mirai/Botnet-Agent-X" if is_flood else "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            path="/api/v1/checkout",
            has_valid_ja3=not is_flood,
            solves_pow_challenge=False,
            is_known_search_engine=False,
            request_rate=25.0 if is_flood else 3.0,
        )
        action, score, reason = engine.evaluate_request(req)
        status_symbol = f"{Colors.RED}BLOCKED{Colors.RESET}" if action == ActionType.DROP_DDOS else f"{Colors.GREEN}PASSED{Colors.RESET}"
        print(f"  Req #{idx:02d} | IP: {ip:<15} | Rate: {req.request_rate:4.1f} rps | Score: {score:02d} | Decision: {status_symbol} ({reason})")
        time.sleep(0.04)


def run_rate_limit_demo(engine: CloudflareEdgeSimulator):
    print(f"\n{Colors.YELLOW}{Colors.BOLD}[*] Testing Token Bucket Rate Limiting for IP: 203.0.113.88{Colors.RESET}")
    ip = "203.0.113.88"
    for req_num in range(1, 16):
        req = ClientRequest(
            ip=ip,
            user_agent="Mozilla/5.0 Chrome/120.0 Safari/537.36",
            path="/api/search",
            has_valid_ja3=True,
            solves_pow_challenge=True,
            is_known_search_engine=False,
            request_rate=5.0,
        )
        action, score, reason = engine.evaluate_request(req)
        color = Colors.GREEN if action == ActionType.ALLOW else Colors.YELLOW
        print(f"  Request #{req_num:02d}: {color}{action.name:<12}{Colors.RESET} - {reason}")
        time.sleep(0.08)


def display_dashboard(engine: CloudflareEdgeSimulator):
    print(f"\n{Colors.CYAN}{Colors.BOLD}====================== CLOUDFLARE EDGE TELEMETRY DASHBOARD ======================{Colors.RESET}")
    print(f"Total Requests Evaluated: {Colors.BOLD}{engine.total_processed}{Colors.RESET}")
    print("--------------------------------------------------------------------------------")
    for action, count in engine.stats.items():
        pct = (count / engine.total_processed * 100) if engine.total_processed > 0 else 0
        bar = "#" * int(pct / 4)
        print(f"  {action.name:<16}: {count:4d} ({pct:5.1f}%) | {Colors.BLUE}{bar}{Colors.RESET}")
    print(f"{Colors.CYAN}================================================================================{Colors.RESET}\n")


def interactive_menu():
    engine = CloudflareEdgeSimulator()
    render_banner()

    scenarios = [
        ("Legitimate Human Browser", ClientRequest("198.51.100.12", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "/index.html", True, True, False, 1.2)),
        ("Googlebot Crawler (Verified)", ClientRequest("66.249.66.1", "Googlebot/2.1", "/robots.txt", True, True, True, 2.0)),
        ("Automated Python Scraper", ClientRequest("192.0.2.45", "python-requests/2.31.0", "/pricing-data", False, False, False, 4.5)),
        ("Headless Browser / Managed Challenge", ClientRequest("192.0.2.99", "Puppeteer/Chrome", "/login", False, True, False, 3.0)),
    ]

    while True:
        print(f"{Colors.BOLD}PILIH MENU SIMULASI:{Colors.RESET}")
        print("  1. Uji Profiling Request Tunggal (Human vs Crawler vs Scraper)")
        print("  2. Simulasi Serangan Volumetric DDoS Flood (L7 Mitigation)")
        print("  3. Simulasi Token Bucket Rate Limiting & Cooldown Box")
        print("  4. Tampilkan Ringkasan Telemetri Edge WAF")
        print("  5. Jalankan Semua Skenario Berurutan (Automated Demo)")
        print("  0. Keluar")

        choice = input(f"\n{Colors.CYAN}Masukkan pilihan (0-5): {Colors.RESET}").strip()

        if choice == "1":
            for label, sample_req in scenarios:
                run_single_simulation(engine, sample_req, label)
            print()
        elif choice == "2":
            run_ddos_burst_simulation(engine)
        elif choice == "3":
            run_rate_limit_demo(engine)
        elif choice == "4":
            display_dashboard(engine)
        elif choice == "5":
            for label, sample_req in scenarios:
                run_single_simulation(engine, sample_req, label)
            run_rate_limit_demo(engine)
            run_ddos_burst_simulation(engine)
            display_dashboard(engine)
        elif choice == "0":
            print(f"{Colors.GREEN}Selesai. Simulasi Cloudflare Edge ditutup.{Colors.RESET}")
            sys.exit(0)
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan ulangi.{Colors.RESET}\n")


if __name__ == "__main__":
    interactive_menu()
