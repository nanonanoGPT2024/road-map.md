#!/usr/bin/env python3
"""
Cloudflare Advanced Production Architecture Simulator
BAB-05: DDoS Mitigation, Sliding Window Rate Limiting, & Bot Management Engine
"""

import collections
import dataclasses
import enum
import hashlib
import random
import sys
import time
from typing import Dict, List, Optional, Tuple


# ==============================================================================
# Terminal Color Palette (ANSI TrueColor & Standard 16-color Fallback)
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Cloudflare Brand & Status Colors
    CF_ORANGE = "\033[38;5;208m"
    CYAN = "\033[38;5;51m"
    BLUE = "\033[38;5;39m"
    GREEN = "\033[38;5;82m"
    YELLOW = "\033[38;5;220m"
    RED = "\033[38;5;196m"
    PURPLE = "\033[38;5;141m"
    GRAY = "\033[38;5;244m"
    BG_DARK = "\033[48;5;236m"


# ==============================================================================
# Domain Models & Enums
# ==============================================================================
class Action(enum.Enum):
    ALLOW = "ALLOW (200 OK)"
    BLOCK = "BLOCK (403 Forbidden)"
    CHALLENGE = "MANAGED CHALLENGE (Turnstile)"
    RATE_LIMIT = "RATE LIMITED (429 Too Many Requests)"
    DROP_L4 = "SYN-DROP (Layer 3/4 Gatekeeper)"


class BotCategory(enum.Enum):
    VERIFIED_GOOD = "Verified Good Bot"
    LIKELY_HUMAN = "Likely Human"
    SUSPICIOUS = "Suspicious Traffic"
    AUTOMATED = "Automated / Scraping Bot"
    MALICIOUS = "Malicious Bot / Threat Actor"


@dataclasses.dataclass
class HttpRequest:
    req_id: str
    client_ip: str
    method: str
    path: str
    user_agent: str
    ja3_fingerprint: str
    asn: int
    is_verified_bot: bool = False
    timestamp: float = dataclasses.field(default_factory=time.time)


@dataclasses.dataclass
class InspectionResult:
    action: Action
    stage: str
    bot_score: int
    category: BotCategory
    latency_ms: float
    details: str


# ==============================================================================
# Edge Pipeline Component 1: Layer 3/4 DDoS Mitigation (Unmetered Mitigation)
# ==============================================================================
class Layer4Gatekeeper:
    """Simulates Cloudflare Gatekeeper & dosd BGP Anycast scrubbing."""

    def __init__(self, syn_flood_threshold_per_sec: int = 15):
        self.threshold = syn_flood_threshold_per_sec
        self.ip_window: Dict[str, collections.deque] = collections.defaultdict(collections.deque)

    def inspect(self, req: HttpRequest) -> Tuple[bool, Optional[str]]:
        now = req.timestamp
        q = self.ip_window[req.client_ip]

        # Flush requests older than 1 second
        while q and now - q[0] > 1.0:
            q.popleft()

        q.append(now)

        if len(q) > self.threshold:
            return True, f"Volumetric SYN/UDP flood threshold exceeded ({len(q)} req/sec)"
        return False, None


# ==============================================================================
# Edge Pipeline Component 2: Sliding Window Rate Limiter
# ==============================================================================
class SlidingWindowRateLimiter:
    """Implements Sliding Window Log Rate Limiting per IP and URI scope."""

    def __init__(self, limit: int = 5, window_seconds: float = 5.0):
        self.limit = limit
        self.window_seconds = window_seconds
        # key -> deque of timestamps
        self.records: Dict[str, collections.deque] = collections.defaultdict(collections.deque)

    def check(self, key: str, timestamp: float) -> Tuple[bool, int, int]:
        now = timestamp
        q = self.records[key]

        while q and (now - q[0]) > self.window_seconds:
            q.popleft()

        current_count = len(q)
        if current_count >= self.limit:
            return False, current_count, self.limit

        q.append(now)
        return True, current_count + 1, self.limit


# ==============================================================================
# Edge Pipeline Component 3: Bot Management ML Engine (Score 1 - 99)
# ==============================================================================
class BotManagementEngine:
    """
    Simulates Cloudflare Bot Management heuristic & Machine Learning scoring.
    Score:
      1 - 29  : Definite Automated / Bot
      30 - 70 : Suspicious / Gray Area
      71 - 99 : Likely Human
    """

    KNOWN_GOOD_JA3 = {
        "b32309a26ce516a56669ac3b99b65762": "Modern Chrome / BoringSSL",
        "771b933a36ca7151a660a5e2f78306e7": "Firefox NSS",
        "2d235fcedc521109a25b306b3281a64f": "Apple Safari SecureTransport",
    }

    SUSPICIOUS_JA3 = {
        "c8c360c7b2a65d792e34749f7cf7d159": "Python requests / urllib",
        "9e9009a26ce516a56669ac3b99b65999": "Go-http-client / Custom Bot",
        "477b933a36ca7151a660a5e2f78306ee": "Headless Chrome / Puppeteer",
    }

    def evaluate(self, req: HttpRequest) -> Tuple[int, BotCategory, str]:
        # Rule 1: Verified Good Bots (Googlebot, Bingbot, etc. validated via reverse DNS/ASN)
        if req.is_verified_bot:
            return 99, BotCategory.VERIFIED_GOOD, "Verified Crawler (reverse-DNS verified)"

        score = 80
        signals = []

        # Heuristic 1: Suspicious User-Agents
        ua_lower = req.user_agent.lower()
        if any(tool in ua_lower for tool in ["curl", "python", "scrapy", "postman", "go-http"]):
            score -= 45
            signals.append("Automated HTTP Client UA")

        # Heuristic 2: JA3 Fingerprint analysis
        if req.ja3_fingerprint in self.SUSPICIOUS_JA3:
            score -= 30
            signals.append(f"Known Bot JA3 ({self.SUSPICIOUS_JA3[req.ja3_fingerprint]})")
        elif req.ja3_fingerprint in self.KNOWN_GOOD_JA3:
            score += 10
            signals.append("Legitimate Browser TLS Signature")

        # Heuristic 3: Path targeting sensitive endpoints
        if req.path in ["/login", "/api/v1/auth", "/wp-login.php", "/xmlrpc.php"]:
            score -= 10
            signals.append("Sensitive Endpoint Probe")

        # Heuristic 4: ASN Reputation
        if req.asn in [16509, 14061, 8075]:  # AWS, DigitalOcean, Microsoft Data Centers
            score -= 15
            signals.append(f"Hosting/DataCenter ASN ({req.asn})")

        # Clamp score between 1 and 99
        score = max(1, min(99, score))

        if score < 20:
            category = BotCategory.MALICIOUS
        elif score < 40:
            category = BotCategory.AUTOMATED
        elif score < 65:
            category = BotCategory.SUSPICIOUS
        else:
            category = BotCategory.LIKELY_HUMAN

        detail = " | ".join(signals) if signals else "Standard browser pattern"
        return score, category, detail


# ==============================================================================
# Cloudflare Edge Core: Pipeline Orchestrator
# ==============================================================================
class CloudflareEdgeSimulator:
    def __init__(self):
        self.l4_gatekeeper = Layer4Gatekeeper(syn_flood_threshold_per_sec=10)
        self.rate_limiter = SlidingWindowRateLimiter(limit=6, window_seconds=5.0)
        self.bot_engine = BotManagementEngine()

        self.stats = collections.defaultdict(int)
        self.total_latency_ms = 0.0

    def process(self, req: HttpRequest) -> InspectionResult:
        start_time = time.perf_counter()

        # Step 1: Layer 3/4 Gatekeeper (Unmetered DDoS Mitigation)
        l4_drop, l4_msg = self.l4_gatekeeper.inspect(req)
        if l4_drop:
            latency = (time.perf_counter() - start_time) * 1000 + random.uniform(0.1, 0.4)
            self.stats[Action.DROP_L4] += 1
            return InspectionResult(
                action=Action.DROP_L4,
                stage="Layer 3/4 Gatekeeper",
                bot_score=1,
                category=BotCategory.MALICIOUS,
                latency_ms=latency,
                details=l4_msg or "Drop at edge",
            )

        # Step 2: Bot Management ML Evaluation
        bot_score, bot_category, bot_details = self.bot_engine.evaluate(req)

        # Step 3: WAF Mitigation Rules based on Bot Score
        if bot_category == BotCategory.MALICIOUS:
            latency = (time.perf_counter() - start_time) * 1000 + random.uniform(0.3, 0.8)
            self.stats[Action.BLOCK] += 1
            return InspectionResult(
                action=Action.BLOCK,
                stage="Bot Management (Score < 20)",
                bot_score=bot_score,
                category=bot_category,
                latency_ms=latency,
                details=f"Threat blocked. Score={bot_score} ({bot_details})",
            )

        if bot_category in (BotCategory.AUTOMATED, BotCategory.SUSPICIOUS):
            latency = (time.perf_counter() - start_time) * 1000 + random.uniform(0.5, 1.2)
            self.stats[Action.CHALLENGE] += 1
            return InspectionResult(
                action=Action.CHALLENGE,
                stage="WAF Managed Challenge",
                bot_score=bot_score,
                category=bot_category,
                latency_ms=latency,
                details=f"Turnstile triggered. Score={bot_score} ({bot_details})",
            )

        # Step 4: Sliding Window Rate Limiting (Sensitive paths like /login or API)
        rate_key = f"{req.client_ip}:{req.path}"
        passed, current, limit = self.rate_limiter.check(rate_key, req.timestamp)
        if not passed:
            latency = (time.perf_counter() - start_time) * 1000 + random.uniform(0.2, 0.6)
            self.stats[Action.RATE_LIMIT] += 1
            return InspectionResult(
                action=Action.RATE_LIMIT,
                stage="Rate Limiting Ruleset",
                bot_score=bot_score,
                category=bot_category,
                latency_ms=latency,
                details=f"Rate exceeded: {current}/{limit} req per 5s on {req.path}",
            )

        # Step 5: Allowed through Edge to Origin / Edge Cache
        latency = (time.perf_counter() - start_time) * 1000 + random.uniform(0.4, 1.5)
        self.stats[Action.ALLOW] += 1
        return InspectionResult(
            action=Action.ALLOW,
            stage="Origin Proxy / Cache",
            bot_score=bot_score,
            category=bot_category,
            latency_ms=latency,
            details=f"Score={bot_score} | {bot_details}",
        )


# ==============================================================================
# UI Formatting & Interactive Terminal Dashboard
# ==============================================================================
def format_action(action: Action) -> str:
    if action == Action.ALLOW:
        return f"{Color.GREEN}{Color.BOLD}✓ {action.value}{Color.RESET}"
    elif action == Action.BLOCK:
        return f"{Color.RED}{Color.BOLD}✗ {action.value}{Color.RESET}"
    elif action == Action.CHALLENGE:
        return f"{Color.YELLOW}{Color.BOLD}⚡ {action.value}{Color.RESET}"
    elif action == Action.RATE_LIMIT:
        return f"{Color.PURPLE}{Color.BOLD}⏱ {action.value}{Color.RESET}"
    elif action == Action.DROP_L4:
        return f"{Color.RED}{Color.BOLD}⛔ {action.value}{Color.RESET}"
    return str(action.value)


def print_banner():
    banner = f"""
{Color.CF_ORANGE}{Color.BOLD}╔══════════════════════════════════════════════════════════════════════════════════╗
║               CLOUDFLARE EDGE ARCHITECTURE INTERACTIVE SIMULATOR                 ║
║   BAB-05: DDoS Mitigation, Sliding Window Rate Limiting, & Bot Management Engine ║
╚══════════════════════════════════════════════════════════════════════════════════╝{Color.RESET}
"""
    print(banner)


def render_result_row(req: HttpRequest, res: InspectionResult):
    print(f"{Color.CYAN}┌─ REQ #{req.req_id} [{req.method} {req.path}]{Color.RESET}")
    print(f"│  {Color.GRAY}Client IP:{Color.RESET} {req.client_ip:<15}  {Color.GRAY}ASN:{Color.RESET} AS{req.asn:<6}  {Color.GRAY}JA3:{Color.RESET} {req.ja3_fingerprint[:12]}...")
    print(f"│  {Color.GRAY}User-Agent:{Color.RESET} {req.user_agent[:60]}")
    print(f"│  {Color.BOLD}Decision:{Color.RESET}  {format_action(res.action)}")
    print(f"│  {Color.BOLD}Pipeline:{Color.RESET}  {Color.BLUE}{res.stage}{Color.RESET} | {Color.YELLOW}Bot Score: {res.bot_score}/99{Color.RESET} ({res.category.value})")
    print(f"│  {Color.BOLD}Details:{Color.RESET}   {res.details}")
    print(f"│  {Color.GRAY}Latency:{Color.RESET}   {res.latency_ms:.2f} ms")
    print(f"{Color.CYAN}└─────────────────────────────────────────────────────────────────────────────────{Color.RESET}")


def render_metrics_summary(stats: Dict[Action, int]):
    total = sum(stats.values()) or 1
    print(f"\n{Color.CF_ORANGE}{Color.BOLD}=== EDGE METRICS SUMMARY ==={Color.RESET}")
    print(f"Total Requests Processed: {Color.BOLD}{sum(stats.values())}{Color.RESET}\n")

    for act in Action:
        count = stats[act]
        pct = (count / total) * 100
        bar = "█" * int(pct / 4)
        print(f"  {act.name:<12} : {count:>4} reqs ({pct:>5.1f}%) {Color.CYAN}{bar}{Color.RESET}")
    print()


# ==============================================================================
# Attack & Traffic Scenarios
# ==============================================================================
def scenario_human_browsing(edge: CloudflareEdgeSimulator):
    print(f"\n{Color.GREEN}{Color.BOLD}► [SCENARIO 1] Legitimate Human User (E-Commerce Browsing){Color.RESET}")
    ip = "203.0.113.45"
    ja3 = "b32309a26ce516a56669ac3b99b65762"
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

    paths = ["/", "/products", "/products/item-492", "/cart", "/checkout"]
    for i, path in enumerate(paths, 1):
        req = HttpRequest(
            req_id=f"HUM-{i:03d}",
            client_ip=ip,
            method="GET",
            path=path,
            user_agent=ua,
            ja3_fingerprint=ja3,
            asn=7713,  # Telkom Indonesia
            timestamp=time.time(),
        )
        res = edge.process(req)
        render_result_row(req, res)
        time.sleep(0.15)


def scenario_rate_limiting_burst(edge: CloudflareEdgeSimulator):
    print(f"\n{Color.PURPLE}{Color.BOLD}► [SCENARIO 2] API Burst & Sliding Window Rate Limiting Violation{Color.RESET}")
    print(f"{Color.GRAY}Configured Limit: 6 requests per 5-second window on /api/v1/auth{Color.RESET}")
    ip = "198.51.100.88"
    ja3 = "771b933a36ca7151a660a5e2f78306e7"
    ua = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"

    t_base = time.time()
    for i in range(1, 10):
        req = HttpRequest(
            req_id=f"BURST-{i:03d}",
            client_ip=ip,
            method="POST",
            path="/api/v1/auth",
            user_agent=ua,
            ja3_fingerprint=ja3,
            asn=13335,  # Cloudflare ASN (legit client ASN)
            timestamp=t_base + (i * 0.2),  # Fast burst
        )
        res = edge.process(req)
        render_result_row(req, res)
        time.sleep(0.08)


def scenario_credential_stuffing_botnet(edge: CloudflareEdgeSimulator):
    print(f"\n{Color.YELLOW}{Color.BOLD}► [SCENARIO 3] Distributed Credential Stuffing & Scraping Botnet{Color.RESET}")
    bot_ja3s = [
        "c8c360c7b2a65d792e34749f7cf7d159",
        "9e9009a26ce516a56669ac3b99b65999",
        "477b933a36ca7151a660a5e2f78306ee",
    ]
    bot_uas = [
        "python-requests/2.31.0",
        "Go-http-client/1.1",
        "Mozilla/5.0 (HeadlessChrome/119.0.0.0)",
        "Scrapy/2.11.0 (+https://scrapy.org)",
    ]

    for i in range(1, 7):
        ip = f"185.220.101.{10 + i}"
        req = HttpRequest(
            req_id=f"BOT-{i:03d}",
            client_ip=ip,
            method="POST",
            path="/login",
            user_agent=random.choice(bot_uas),
            ja3_fingerprint=random.choice(bot_ja3s),
            asn=14061,  # DigitalOcean Cloud Datacenter
            timestamp=time.time(),
        )
        res = edge.process(req)
        render_result_row(req, res)
        time.sleep(0.12)


def scenario_volumetric_ddos(edge: CloudflareEdgeSimulator):
    print(f"\n{Color.RED}{Color.BOLD}► [SCENARIO 4] Layer 3/4 Volumetric SYN/HTTP Flood (Gatekeeper Trigger){Color.RESET}")
    attacker_ip = "45.155.205.23"
    t_now = time.time()

    print(f"{Color.GRAY}Flooding 15 packets in <1s window from {attacker_ip}...{Color.RESET}")
    for i in range(1, 16):
        req = HttpRequest(
            req_id=f"DDOS-{i:03d}",
            client_ip=attacker_ip,
            method="GET",
            path="/",
            user_agent="Wget/1.21.3",
            ja3_fingerprint="c8c360c7b2a65d792e34749f7cf7d159",
            asn=9009,
            timestamp=t_now + (i * 0.02),
        )
        res = edge.process(req)
        if res.action == Action.DROP_L4:
            print(f" {Color.RED}⚡ {res.action.value} -> Packet {i} dropped at anycast edge.{Color.RESET}")
        else:
            print(f" {Color.YELLOW}• Packet {i} inspected: {res.action.name}{Color.RESET}")
        time.sleep(0.02)


def scenario_verified_search_crawler(edge: CloudflareEdgeSimulator):
    print(f"\n{Color.CYAN}{Color.BOLD}► [SCENARIO 5] Verified Search Engine Crawler (Googlebot rDNS Passed){Color.RESET}")
    req = HttpRequest(
        req_id=f"CRAWL-001",
        client_ip="66.249.66.1",
        method="GET",
        path="/sitemap.xml",
        user_agent="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        ja3_fingerprint="2d235fcedc521109a25b306b3281a64f",
        asn=15169,  # Google LLC
        is_verified_bot=True,
        timestamp=time.time(),
    )
    res = edge.process(req)
    render_result_row(req, res)


# ==============================================================================
# Interactive CLI Menu
# ==============================================================================
def interactive_menu(edge: CloudflareEdgeSimulator):
    while True:
        print(f"\n{Color.BOLD}Select Simulation Mode:{Color.RESET}")
        print(f"  {Color.GREEN}1{Color.RESET}) Run Complete End-to-End Suite (Scenarios 1-5)")
        print(f"  {Color.GREEN}2{Color.RESET}) Test Human User Traffic")
        print(f"  {Color.GREEN}3{Color.RESET}) Test Sliding Window Rate Limiting (Burst)")
        print(f"  {Color.GREEN}4{Color.RESET}) Test Bot Management & Managed Challenge")
        print(f"  {Color.GREEN}5{Color.RESET}) Test Volumetric Layer 3/4 Flood (Gatekeeper)")
        print(f"  {Color.GREEN}6{Color.RESET}) Test Verified Search Engine Crawler")
        print(f"  {Color.GREEN}7{Color.RESET}) View Edge Metrics Summary")
        print(f"  {Color.RED}0{Color.RESET}) Exit Lab")

        choice = input(f"\n{Color.CF_ORANGE}Enter option [0-7]: {Color.RESET}").strip()

        if choice == "1":
            scenario_human_browsing(edge)
            scenario_rate_limiting_burst(edge)
            scenario_credential_stuffing_botnet(edge)
            scenario_volumetric_ddos(edge)
            scenario_verified_search_crawler(edge)
            render_metrics_summary(edge.stats)
        elif choice == "2":
            scenario_human_browsing(edge)
        elif choice == "3":
            scenario_rate_limiting_burst(edge)
        elif choice == "4":
            scenario_credential_stuffing_botnet(edge)
        elif choice == "5":
            scenario_volumetric_ddos(edge)
        elif choice == "6":
            scenario_verified_search_crawler(edge)
        elif choice == "7":
            render_metrics_summary(edge.stats)
        elif choice in ("0", "q", "exit"):
            print(f"\n{Color.CYAN}Exiting Cloudflare Edge Simulator. Keep your edge secure!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Invalid option selected.{Color.RESET}")


def main():
    print_banner()
    edge = CloudflareEdgeSimulator()

    # If running non-interactively or with '--auto' flag
    if "--auto" in sys.argv or not sys.stdin.isatty():
        print(f"{Color.YELLOW}Running in non-interactive batch verification mode...{Color.RESET}\n")
        scenario_human_browsing(edge)
        scenario_rate_limiting_burst(edge)
        scenario_credential_stuffing_botnet(edge)
        scenario_volumetric_ddos(edge)
        scenario_verified_search_crawler(edge)
        render_metrics_summary(edge.stats)
    else:
        interactive_menu(edge)


if __name__ == "__main__":
    main()
