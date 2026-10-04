#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Inti & Arsitektur Cloudflare
BAB-01: Fondasi dan Arsitektur Cloudflare

Fitur Simulasi:
1. Anycast vs Unicast BGP Routing Engine
2. Reverse Proxy Lifecycle (Client -> Edge PoP -> WAF -> Cache -> Origin)
3. Edge Caching States (MISS, HIT, BYPASS, EXPIRED)
4. WAF & DDoS Threat Mitigation Layer
"""

import sys
import time
import random
import hashlib
from typing import Dict, Any, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
ORANGE = "\033[38;5;208m"
BG_BLUE = "\033[44m"
BG_ORANGE = "\033[48;5;208m"


def header(title: str):
    print(f"\n{ORANGE}{BOLD}{'=' * 65}{RESET}")
    print(f"{ORANGE}{BOLD} [CLOUDFLARE SIMULATOR] {WHITE}{title}{RESET}")
    print(f"{ORANGE}{BOLD}{'=' * 65}{RESET}\n")


def log_step(component: str, msg: str, status: str = "INFO", delay: float = 0.04):
    color_map = {
        "INFO": CYAN,
        "PASS": GREEN,
        "WARN": YELLOW,
        "BLOCK": RED,
        "ORIGIN": MAGENTA,
        "CACHE": ORANGE,
    }
    col = color_map.get(status, WHITE)
    timestamp = time.strftime("%H:%M:%S")
    print(f"{DIM}[{timestamp}]{RESET} {col}[{component:<12}]{RESET} {msg}")
    if delay > 0:
        time.sleep(delay)


class AnycastNetwork:
    """Simulasi Anycast Routing BGP Global Edge Network."""

    POPS = {
        "CGK": {"name": "Jakarta (CGK)", "lat": -6.12, "lon": 106.65},
        "SIN": {"name": "Singapore (SIN)", "lat": 1.36, "lon": 103.99},
        "NRT": {"name": "Tokyo (NRT)", "lat": 35.77, "lon": 140.39},
        "FRA": {"name": "Frankfurt (FRA)", "lat": 50.03, "lon": 8.57},
        "SFO": {"name": "San Francisco (SFO)", "lat": 37.62, "lon": -122.37},
    }

    UNICAST_ORIGIN = {"name": "Origin Server (Ashburn / IAD)", "lat": 39.04, "lon": -77.48}

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        # Perhitungan euclidean sederhana untuk jarak geografis & latensi simulasi
        return ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5

    def route_request(self, client_location: str, client_coords: tuple) -> Dict[str, Any]:
        c_lat, c_lon = client_coords

        # Cari Edge PoP terdekat (Anycast routing metric)
        closest_pop = None
        min_dist = float("inf")
        for code, data in self.POPS.items():
            dist = self.calculate_distance(c_lat, c_lon, data["lat"], data["lon"])
            if dist < min_dist:
                min_dist = dist
                closest_pop = (code, data)

        # Hitung latensi ke Anycast Edge vs Unicast Origin langsung
        anycast_latency_ms = round(max(3.0, min_dist * 1.8 + random.uniform(1.0, 4.0)), 1)

        origin_dist = self.calculate_distance(
            c_lat, c_lon, self.UNICAST_ORIGIN["lat"], self.UNICAST_ORIGIN["lon"]
        )
        unicast_latency_ms = round(max(15.0, origin_dist * 2.2 + random.uniform(5.0, 15.0)), 1)

        return {
            "client": client_location,
            "pop_code": closest_pop[0],
            "pop_name": closest_pop[1]["name"],
            "anycast_latency_ms": anycast_latency_ms,
            "unicast_origin": self.UNICAST_ORIGIN["name"],
            "unicast_latency_ms": unicast_latency_ms,
        }


class EdgeCache:
    """Simulasi L1 Edge Cache pada Cloudflare Edge PoP."""

    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        if url in self.store:
            entry = self.store[url]
            if time.time() < entry["expires_at"]:
                return entry["data"]
            else:
                del self.store[url]
        return None

    def put(self, url: str, data: Dict[str, Any], ttl_seconds: int = 10):
        self.store[url] = {
            "data": data,
            "expires_at": time.time() + ttl_seconds,
            "cached_at": time.time(),
        }

    def purge(self):
        self.store.clear()


class WAFEngine:
    """Simulasi Web Application Firewall & Inspeksi Layer 7."""

    BAD_PATTERNS = ["UNION SELECT", "<script>", "drop table", "/etc/passwd", "../"]
    BOT_USER_AGENTS = ["sqlmap", "nikto", "masscan", "curl-bot-attack"]

    @classmethod
    def inspect(cls, uri: str, headers: Dict[str, str], ip: str) -> Dict[str, Any]:
        # 1. User-Agent Check
        ua = headers.get("User-Agent", "").lower()
        for bot in cls.BOT_USER_AGENTS:
            if bot in ua:
                return {
                    "action": "BLOCK",
                    "rule": "100010_BAD_BOT",
                    "reason": f"Known malicious User-Agent: {ua}",
                }

        # 2. URI / Query SQLi & LFI Check
        for pat in cls.BAD_PATTERNS:
            if pat.lower() in uri.lower():
                return {
                    "action": "BLOCK",
                    "rule": "100020_SQLI_LFI_DETECTED",
                    "reason": f"Malicious pattern identified: '{pat}'",
                }

        # 3. Geo / IP Rate limiting check simulasi
        if ip.startswith("198.51.100."):
            return {
                "action": "CHALLENGE",
                "rule": "100030_MANAGED_CHALLENGE",
                "reason": "Suspicious Autonomous System Number (ASN threat score 85)",
            }

        return {"action": "ALLOW", "rule": "DEFAULT_ALLOW", "reason": "Passed all rule checks"}


class CloudflareEdgeSimulator:
    """Reverse Proxy & Orchestrator Simulasi Fondasi Cloudflare."""

    def __init__(self):
        self.network = AnycastNetwork()
        self.waf = WAFEngine()
        self.cache = EdgeCache()
        self.origin_hits = 0
        self.edge_hits = 0
        self.total_requests = 0

    def process_request(
        self,
        client_name: str,
        coords: tuple,
        method: str,
        uri: str,
        headers: Dict[str, str],
        client_ip: str,
        is_proxied: bool = True,
    ):
        self.total_requests += 1
        print(f"\n{BOLD}--> Request: {CYAN}{method} {uri}{RESET} dari {YELLOW}{client_name}{RESET} ({client_ip})")

        # 1. DNS & Routing
        if not is_proxied:
            log_step("DNS", "Status DNS: Grey Cloud (DNS Only). Bypass Edge!", "WARN")
            log_step("ROUTING", f"Request langsung dialihkan ke Unicast Origin di Ashburn (IAD)...", "ORIGIN")
            time.sleep(0.08)
            log_step("ORIGIN", "Response diterima langsung dari Origin (Latensi tinggi, No Protection).", "ORIGIN")
            return

        routing = self.network.route_request(client_name, coords)
        log_step("DNS", "Status DNS: Orange Cloud (Proxied via Cloudflare Anycast IP: 104.16.123.96)", "INFO")
        log_step(
            "ANYCAST",
            f"BGP Anycast mengarahkan request ke PoP terdekat: {GREEN}{routing['pop_name']}{RESET} (RTT: {routing['anycast_latency_ms']} ms vs Origin Unicast: {routing['unicast_latency_ms']} ms)",
            "PASS",
        )

        # 2. WAF & DDoS Inspection
        log_step("WAF-L7", "Menjalankan deep packet & header inspection...", "INFO")
        waf_res = self.waf.inspect(uri, headers, client_ip)

        if waf_res["action"] == "BLOCK":
            log_step("WAF-L7", f"{RED}BLOCKED! Rule ID: {waf_res['rule']} - {waf_res['reason']}{RESET}", "BLOCK")
            print(f"    {BG_ORANGE}{WHITE}{BOLD} [HTTP 403 Forbidden - Cloudflare Security Block] {RESET}")
            return
        elif waf_res["action"] == "CHALLENGE":
            log_step("CHALLENGE", f"{YELLOW}Managed Challenge (Turnstile Captcha Triggered) - {waf_res['reason']}{RESET}", "WARN")
            log_step("TURNSTILE", "Token challenge valid via interactive browser check. Melanjutkan...", "PASS")

        log_step("WAF-L7", "WAF Inspection Clear. Request diizinkan.", "PASS")

        # 3. Edge Cache Evaluation
        cached_data = self.cache.get(uri)
        if cached_data and method == "GET":
            self.edge_hits += 1
            log_step("CACHE", f"{GREEN}CF-Cache-Status: HIT{RESET} (Konten disajikan dari Edge RAM L1 Cache)", "CACHE")
            log_step("RESPONSE", f"HTTP 200 OK | cf-ray: {hashlib.md5(str(time.time()).encode()).hexdigest()[:16]}-{routing['pop_code']}", "PASS")
            print(f"    Payload: {cached_data['payload']} (Size: {cached_data['size']})")
            return

        # 4. Origin Fetch on Cache MISS / BYPASS
        self.origin_hits += 1
        cache_status = "BYPASS" if method != "GET" else "MISS"
        log_step("CACHE", f"{YELLOW}CF-Cache-Status: {cache_status}{RESET} -> Mengirim origin request ke Backend...", "WARN")
        log_step("TLS/TCP", "Membuat TLS 1.3 Keep-Alive tunnel ke Origin Server (Ashburn IAD)...", "ORIGIN")
        
        # Origin processing simulation
        time.sleep(0.06)
        origin_payload = {
            "payload": f"Content-for-[{uri}]",
            "size": "42 KB",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        log_step("ORIGIN", "Origin merespon dengan header 'Cache-Control: public, max-age=10'", "ORIGIN")

        if method == "GET":
            self.cache.put(uri, origin_payload, ttl_seconds=8)
            log_step("CACHE", "Menyimpan respon ke Edge Storage L1 untuk request selanjutnya.", "CACHE")

        cf_ray = f"{hashlib.md5((uri + str(time.time())).encode()).hexdigest()[:16]}-{routing['pop_code']}"
        log_step("RESPONSE", f"HTTP 200 OK | cf-ray: {cf_ray} | Server: cloudflare", "PASS")
        print(f"    Payload: {origin_payload['payload']} (Size: {origin_payload['size']})")


def run_interactive_demo():
    sim = CloudflareEdgeSimulator()

    client_presets = {
        "1": ("Client Jakarta (ID)", (-6.20, 106.81), "180.252.12.4"),
        "2": ("Client Singapore (SG)", (1.35, 103.81), "118.200.45.10"),
        "3": ("Client Frankfurt (DE)", (50.11, 8.68), "194.12.44.8"),
        "4": ("Client Attacker (Bad Bot)", (-6.21, 106.84), "198.51.100.99"),
    }

    while True:
        header("SIMULASI LABORATORIUM CLOUDFLARE EDGE & ARSITEKTUR")
        print(f"{BOLD}Pilih skenario simulasi:{RESET}")
        print(f"  {CYAN}1.{RESET} Anycast Routing Demo (Klien Jakarta -> Auto-route PoP CGK)")
        print(f"  {CYAN}2.{RESET} Cache Flow Lifecycle (MISS -> HIT -> Expiration)")
        print(f"  {CYAN}3.{RESET} WAF Security Mitigation (Simulasi SQLi & Malicious Bot)")
        print(f"  {CYAN}4.{RESET} Proxied (Orange Cloud) vs Direct Origin (Grey Cloud)")
        print(f"  {CYAN}5.{RESET} Jalankan Audit Metrik & Statistik Cache")
        print(f"  {CYAN}6.{RESET} Keluar (Exit)")

        choice = input(f"\n{BOLD}{YELLOW}Masukkan pilihan (1-6): {RESET}").strip()

        if choice == "1":
            print(f"\n{BOLD}--- Pengujian Anycast Global Edge Network ---{RESET}")
            for name, coords, ip in client_presets.values():
                sim.process_request(
                    client_name=name,
                    coords=coords,
                    method="GET",
                    uri="/static/logo.svg",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64)"},
                    client_ip=ip,
                    is_proxied=True,
                )

        elif choice == "2":
            print(f"\n{BOLD}--- Siklus Hidup Edge Cache (MISS vs HIT) ---{RESET}")
            c_name, c_coords, c_ip = client_presets["1"]
            print(f"\n{BLUE}[Tahap 1]{RESET} Request pertama untuk asset CSS:")
            sim.process_request(c_name, c_coords, "GET", "/assets/app.min.css", {"User-Agent": "Mozilla/5.0"}, c_ip)

            print(f"\n{BLUE}[Tahap 2]{RESET} Request kedua untuk asset yang sama (sebelum TTL habis):")
            sim.process_request(c_name, c_coords, "GET", "/assets/app.min.css", {"User-Agent": "Mozilla/5.0"}, c_ip)

        elif choice == "3":
            print(f"\n{BOLD}--- Simulasi WAF & Threat Intelligence ---{RESET}")
            # Request normal
            sim.process_request("Legit User", (-6.20, 106.81), "GET", "/index.html", {"User-Agent": "Mozilla/5.0"}, "103.21.244.2")
            # SQL Injection attack
            sim.process_request("Hacker Node", (50.11, 8.68), "GET", "/api/users?id=1%20UNION%20SELECT%20password%20FROM%20users", {"User-Agent": "Mozilla/5.0"}, "198.51.100.22")
            # Automated bot scraper attack
            sim.process_request("Bad Bot Scanner", (37.77, -122.41), "GET", "/admin/login", {"User-Agent": "sqlmap/1.6#stable"}, "198.51.100.99")

        elif choice == "4":
            print(f"\n{BOLD}--- Orange Cloud (Proxied) vs Grey Cloud (Bypass) ---{RESET}")
            c_name, c_coords, c_ip = client_presets["1"]
            print(f"\n{ORANGE}[Mode: Orange Cloud (CDN + WAF Enabled)]{RESET}")
            sim.process_request(c_name, c_coords, "GET", "/home", {"User-Agent": "Mozilla/5.0"}, c_ip, is_proxied=True)

            print(f"\n{WHITE}[Mode: Grey Cloud (Direct Origin DNS)]{RESET}")
            sim.process_request(c_name, c_coords, "GET", "/home", {"User-Agent": "Mozilla/5.0"}, c_ip, is_proxied=False)

        elif choice == "5":
            header("STATISTIK TRAFFIC CLOUDFLARE EDGE")
            print(f"Total Permintaan Diterima : {sim.total_requests}")
            print(f"Edge Cache Hits           : {GREEN}{sim.edge_hits}{RESET}")
            print(f"Origin Requests (Misses)  : {YELLOW}{sim.origin_hits}{RESET}")
            ratio = (sim.edge_hits / max(1, sim.edge_hits + sim.origin_hits)) * 100
            print(f"Cache Hit Ratio (Bandwidth Save) : {CYAN}{ratio:.1f}%{RESET}")
            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")

        elif choice == "6":
            print(f"\n{GREEN}Simulasi selesai. Fondasi arsitektur Cloudflare berhasil dipelajari!{RESET}\n")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")


if __name__ == "__main__":
    try:
        run_interactive_demo()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Program dihentikan oleh user.{RESET}")
        sys.exit(0)
