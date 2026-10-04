#!/usr/bin/env python3
"""
Lab Exercise: Cloudflare Edge Architecture & Ingress Pipeline Simulation
Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Cloudflare

Simulasi mandiri (Zero-Dependency) alur request L4 (eBPF/Unimog) -> L7 (Pingora)
-> Wirefilter WAF -> Tiered Cache -> Cloudflare Tunnel -> Origin.
"""

import sys
import time
import random
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ==========================================
# ANSI Color Codes & Formatting
# ==========================================
class Colors:
    HEADER    = '\033[95m'
    BLUE      = '\033[94m'
    CYAN      = '\033[96m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    RED       = '\033[91m'
    MAGENTA   = '\033[35m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM       = '\033[2m'
    RESET     = '\033[0m'

# ==========================================
# Data Models
# ==========================================
@dataclass
class HttpRequest:
    req_id: str
    client_ip: str
    country: str
    method: str
    uri: str
    headers: Dict[str, str]
    body: str = ""
    is_syn_flood: bool = False
    is_tor_or_vpn: bool = False

@dataclass
class EdgeTrace:
    ray_id: str
    edge_pop: str
    upper_pop: str
    l4_decision: str = "PASS"
    tls_version: str = "TLS 1.3"
    waf_action: str = "ALLOW"
    cache_status: str = "DYNAMIC"
    origin_tunnel_status: str = "CONNECTED"
    http_status: int = 200
    latency_ms: float = 0.0
    details: List[str] = field(default_factory=list)

# ==========================================
# Simulation Subsystems
# ==========================================
class L4UnimogGatebot:
    """Simulasi Ingress L4: eBPF/XDP fast path & Gatebot volumetric DDoS mitigation."""
    def __init__(self, pps_threshold: int = 1000):
        self.pps_threshold = pps_threshold

    def inspect(self, req: HttpRequest, trace: EdgeTrace) -> bool:
        trace.details.append(f"{Colors.CYAN}[L4:Unimog/XDP]{Colors.RESET} Ingress packet processed via stateless BGP Anycast")
        if req.is_syn_flood:
            trace.l4_decision = "DROP"
            trace.http_status = 444  # Connection dropped at L4
            trace.details.append(f"{Colors.RED}[L4:Gatebot]{Colors.RESET} Volumetric SYN flood signature detected! Dropped at XDP driver layer in sub-microsecond.")
            return False
        trace.details.append(f"{Colors.GREEN}[L4:Unimog]{Colors.RESET} Clean flow, passed to Pingora worker threads via IP-in-IP encapsulation")
        return True

class L7PingoraEngine:
    """Simulasi L7 Reverse Proxy Engine (Rust/Pingora): TLS Termination & HTTP parse."""
    def __init__(self, min_tls_version: str = "TLS 1.2"):
        self.min_tls_version = min_tls_version

    def process_tls(self, req: HttpRequest, trace: EdgeTrace) -> bool:
        client_tls = req.headers.get("X-Client-TLS-Version", "TLS 1.3")
        trace.tls_version = client_tls
        if client_tls < self.min_tls_version:
            trace.http_status = 400
            trace.details.append(f"{Colors.RED}[L7:Pingora]{Colors.RESET} TLS Handshake Failure: Client version ({client_tls}) below minimum allowed ({self.min_tls_version})")
            return False
        alpn = req.headers.get("X-ALPN", "h2")
        trace.details.append(f"{Colors.GREEN}[L7:Pingora]{Colors.RESET} TLS 1.3 Handshake terminated (ALPN={alpn}, 0-RTT Session Reused)")
        return True

class WirefilterWAF:
    """Simulasi WAF Ruleset Engine dengan sintaks wirefilter-like expression."""
    def __init__(self):
        self.rules = [
            {
                "id": "10001",
                "name": "Block VPN/Tor on Checkout",
                "expr": 'req.is_tor_or_vpn and req.uri.startswith("/checkout")',
                "action": "BLOCK",
                "status": 403
            },
            {
                "id": "10002",
                "name": "Challenge High-Risk Country on Admin",
                "expr": 'req.uri.startswith("/admin") and req.country in ["RU", "KP"]',
                "action": "MANAGED_CHALLENGE",
                "status": 401
            },
            {
                "id": "10003",
                "name": "SQLi & Directory Traversal Protection",
                "expr": "'..' in req.uri or 'UNION SELECT' in req.body.upper() or '<SCRIPT>' in req.body.upper()",
                "action": "BLOCK",
                "status": 403
            }
        ]

    def evaluate(self, req: HttpRequest, trace: EdgeTrace) -> bool:
        for rule in self.rules:
            # Evaluasi ekspresi logika WAF sederhana
            matched = False
            if rule["id"] == "10001" and (req.is_tor_or_vpn and req.uri.startswith("/checkout")):
                matched = True
            elif rule["id"] == "10002" and (req.uri.startswith("/admin") and req.country in ["RU", "KP"]):
                matched = True
            elif rule["id"] == "10003" and (".." in req.uri or "UNION SELECT" in req.body.upper() or "<SCRIPT>" in req.body.upper()):
                matched = True

            if matched:
                trace.waf_action = rule["action"]
                trace.http_status = rule["status"]
                trace.details.append(f"{Colors.YELLOW}[WAF:Wirefilter]{Colors.RESET} Rule #{rule['id']} ({rule['name']}) matched! Action: {Colors.RED}{rule['action']}{Colors.RESET}")
                return False

        trace.details.append(f"{Colors.GREEN}[WAF:Wirefilter]{Colors.RESET} All security rules passed safely")
        return True

class TieredCacheEngine:
    """Simulasi Cache Tiered: Edge POP (CGK) -> Upper-Tier POP (SIN) -> Origin."""
    def __init__(self):
        # Cache internal memory simulasi NVMe storage
        self.edge_cache: Dict[str, bytes] = {}
        self.upper_cache: Dict[str, bytes] = {
            "/assets/app.js": b"console.log('Production Bundle v2.4');",
            "/assets/logo.svg": b"<svg>Cloudflare Enterprise</svg>"
        }

    def check(self, req: HttpRequest, trace: EdgeTrace) -> Tuple[bool, Optional[bytes]]:
        if req.method != "GET":
            trace.cache_status = "BYPASS"
            trace.details.append(f"{Colors.BLUE}[Cache:L7]{Colors.RESET} Method {req.method} bypasses cache (status: {trace.cache_status})")
            return False, None

        if "Authorization" in req.headers or "session_id" in req.headers.get("Cookie", ""):
            trace.cache_status = "BYPASS"
            trace.details.append(f"{Colors.BLUE}[Cache:L7]{Colors.RESET} Auth/Cookie header detected -> Cache BYPASS enforced")
            return False, None

        # Check Edge POP Cache (Jakarta / CGK)
        if req.uri in self.edge_cache:
            trace.cache_status = "HIT"
            trace.details.append(f"{Colors.GREEN}[Cache:Edge POP/{trace.edge_pop}]{Colors.RESET} Status: HIT (Served directly from edge NVMe memory)")
            return True, self.edge_cache[req.uri]

        trace.details.append(f"{Colors.YELLOW}[Cache:Edge POP/{trace.edge_pop}]{Colors.RESET} Status: MISS -> Forwarding query to Upper-Tier POP ({trace.upper_pop})")

        # Check Upper-Tier POP Cache (Singapore / SIN)
        if req.uri in self.upper_cache:
            trace.cache_status = "UPPER_HIT"
            # Populate back to Edge
            self.edge_cache[req.uri] = self.upper_cache[req.uri]
            trace.details.append(f"{Colors.GREEN}[Cache:Upper Tier/{trace.upper_pop}]{Colors.RESET} Status: HIT -> Backfilled into {trace.edge_pop} cache")
            return True, self.upper_cache[req.uri]

        trace.cache_status = "MISS"
        trace.details.append(f"{Colors.MAGENTA}[Cache:Upper Tier/{trace.upper_pop}]{Colors.RESET} Status: MISS -> Must forward request to Enterprise Origin")
        return False, None

class CloudflareTunnelOrigin:
    """Simulasi Zero-Trust Cloudflare Tunnel (cloudflared) & SSL Handshake Origin."""
    def __init__(self, ssl_mode: str = "Full (Strict)"):
        self.ssl_mode = ssl_mode
        self.origin_healthy = True
        self.origin_cert_valid = True

    def fetch(self, req: HttpRequest, trace: EdgeTrace) -> int:
        trace.details.append(f"{Colors.CYAN}[Zero-Trust Tunnel]{Colors.RESET} Routing request through outbound-only cloudflared daemon")

        # Simulasi validasi SSL Mode Full (Strict)
        if self.ssl_mode == "Full (Strict)" and not self.origin_cert_valid:
            trace.http_status = 526
            trace.origin_tunnel_status = "SSL_ERROR"
            trace.details.append(f"{Colors.RED}[Origin:SSL]{Colors.RESET} Error 526: Invalid SSL Certificate (Origin cert is self-signed/expired in Full Strict mode)")
            return 526

        if not self.origin_healthy:
            trace.http_status = 521
            trace.origin_tunnel_status = "DOWN"
            trace.details.append(f"{Colors.RED}[Origin:Gateway]{Colors.RESET} Error 521: Web Server Is Down (Tunnel agent unable to reach TCP 127.0.0.1:8080)")
            return 521

        trace.http_status = 200
        trace.origin_tunnel_status = "CONNECTED"
        trace.details.append(f"{Colors.GREEN}[Origin:App]{Colors.RESET} Origin responded 200 OK via Argo Smart Routing backbone")
        return 200

# ==========================================
# Orchestrator / Pipeline Simulator
# ==========================================
class CloudflarePipelineSimulator:
    def __init__(self):
        self.l4 = L4UnimogGatebot()
        self.l7 = L7PingoraEngine(min_tls_version="TLS 1.2")
        self.waf = WirefilterWAF()
        self.cache = TieredCacheEngine()
        self.tunnel = CloudflareTunnelOrigin(ssl_mode="Full (Strict)")

    def generate_cf_ray(self, pop: str) -> str:
        unique_part = hashlib.md5(f"{time.time()}-{random.random()}".encode()).hexdigest()[:16]
        return f"{unique_part}-{pop}"

    def process(self, req: HttpRequest) -> EdgeTrace:
        start_time = time.perf_counter()
        edge_pop = "CGK"   # Jakarta Soekarno-Hatta Edge POP
        upper_pop = "SIN"  # Singapore Upper-Tier Regional POP
        ray_id = self.generate_cf_ray(edge_pop)

        trace = EdgeTrace(ray_id=ray_id, edge_pop=edge_pop, upper_pop=upper_pop)
        trace.details.append(f"{Colors.BOLD}{Colors.HEADER}=== INCOMING REQUEST: {req.method} {req.uri} (Client IP: {req.client_ip}, Geo: {req.country}) ==={Colors.RESET}")
        trace.details.append(f"{Colors.DIM}Assigned CF-Ray ID: {ray_id}{Colors.RESET}")

        # Step 1: L4 Inspection
        if not self.l4.inspect(req, trace):
            trace.latency_ms = (time.perf_counter() - start_time) * 1000 + 0.12
            return trace

        # Step 2: L7 Pingora & TLS Termination
        if not self.l7.process_tls(req, trace):
            trace.latency_ms = (time.perf_counter() - start_time) * 1000 + 1.45
            return trace

        # Step 3: WAF Ruleset Engine
        if not self.waf.evaluate(req, trace):
            trace.latency_ms = (time.perf_counter() - start_time) * 1000 + 2.10
            return trace

        # Step 4: Tiered Cache Subsystem
        cached_hit, data = self.cache.check(req, trace)
        if cached_hit:
            trace.http_status = 200
            trace.latency_ms = (time.perf_counter() - start_time) * 1000 + 3.85
            return trace

        # Step 5: Origin via Cloudflare Tunnel
        self.tunnel.fetch(req, trace)
        trace.latency_ms = (time.perf_counter() - start_time) * 1000 + 24.60
        return trace

# ==========================================
# Visual Test Runner & Scenarios
# ==========================================
def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
================================================================================
   CLOUDFLARE EDGE ARCHITECTURE & PIPELINE SIMULATOR (PYTHON 3 RUNNABLE)
   Modul 02: L4/XDP, Pingora L7, WAF, Tiered Cache, Zero-Trust Tunnel
================================================================================{Colors.RESET}"""
    print(banner)

def display_trace_summary(trace: EdgeTrace):
    status_color = Colors.GREEN if trace.http_status == 200 else (Colors.YELLOW if trace.http_status in (401, 403) else Colors.RED)
    print("\n" + "\n".join(trace.details))
    print(f"\n{Colors.BOLD}--- Execution Telemetry Trace ---{Colors.RESET}")
    print(f"  * {Colors.BOLD}CF-Ray ID       :{Colors.RESET} {trace.ray_id}")
    print(f"  * {Colors.BOLD}Final HTTP Status:{Colors.RESET} {status_color}{trace.http_status}{Colors.RESET}")
    print(f"  * {Colors.BOLD}L4 Engine Action :{Colors.RESET} {trace.l4_decision}")
    print(f"  * {Colors.BOLD}WAF Filter Action:{Colors.RESET} {trace.waf_action}")
    print(f"  * {Colors.BOLD}CF-Cache-Status  :{Colors.RESET} {trace.cache_status}")
    print(f"  * {Colors.BOLD}Origin Tunnel    :{Colors.RESET} {trace.origin_tunnel_status}")
    print(f"  * {Colors.BOLD}Total Latency    :{Colors.RESET} {Colors.CYAN}{trace.latency_ms:.2f} ms{Colors.RESET}")
    print(f"{Colors.DIM}{'-' * 80}{Colors.RESET}\n")

def run_all_scenarios():
    print_banner()
    sim = CloudflarePipelineSimulator()

    scenarios = [
        (
            "SKENARIO 1: Volumetric DDoS SYN Flood Attack ke Anycast IP",
            HttpRequest(
                req_id="SCEN-01",
                client_ip="198.51.100.44",
                country="US",
                method="GET",
                uri="/",
                headers={},
                is_syn_flood=True
            ),
            lambda s: None
        ),
        (
            "SKENARIO 2: Anonymous Tor/VPN User mencoba Checkout Payment",
            HttpRequest(
                req_id="SCEN-02",
                client_ip="185.220.101.5",
                country="DE",
                method="POST",
                uri="/checkout/pay",
                headers={"X-Client-TLS-Version": "TLS 1.3", "Content-Type": "application/json"},
                body='{"order_id": "9921", "amount": 500000}',
                is_tor_or_vpn=True
            ),
            lambda s: None
        ),
        (
            "SKENARIO 3: Static Asset Request (Tiered Cache Miss di Edge -> Hit di Upper-Tier Singapore)",
            HttpRequest(
                req_id="SCEN-03",
                client_ip="103.28.12.89",
                country="ID",
                method="GET",
                uri="/assets/app.js",
                headers={"X-Client-TLS-Version": "TLS 1.3", "Accept": "*/*"}
            ),
            lambda s: None
        ),
        (
            "SKENARIO 4: Dynamic API Request via Zero-Trust Tunnel ke Origin Privat (200 OK)",
            HttpRequest(
                req_id="SCEN-04",
                client_ip="114.124.200.15",
                country="ID",
                method="POST",
                uri="/api/v1/user/profile",
                headers={"X-Client-TLS-Version": "TLS 1.3", "Authorization": "Bearer token_xyz123"},
                body='{"action": "update_name", "value": "DevOps Engineer"}'
            ),
            lambda s: None
        ),
        (
            "SKENARIO 5: Origin Misconfiguration (Error 526: Invalid SSL Certificate pada Full Strict)",
            HttpRequest(
                req_id="SCEN-05",
                client_ip="203.0.113.8",
                country="SG",
                method="GET",
                uri="/internal/status",
                headers={"X-Client-TLS-Version": "TLS 1.3"}
            ),
            lambda s: setattr(s.tunnel, 'origin_cert_valid', False)
        )
    ]

    for title, req, setup_fn in scenarios:
        print(f"{Colors.BOLD}{Colors.UNDERLINE}>>> MENJALANKAN {title} <<<{Colors.RESET}")
        setup_fn(sim)
        trace = sim.process(req)
        display_trace_summary(trace)
        # Reset tunnel state back
        sim.tunnel.origin_cert_valid = True
        sim.tunnel.origin_healthy = True
        time.sleep(0.05)

    print(f"{Colors.GREEN}{Colors.BOLD}[OK] Seluruh 5 skenario simulasi arsitektur Cloudflare berhasil dieksekusi!{Colors.RESET}")
    print(f"{Colors.DIM}Untuk pengujian manual dengan parameter khusus, jalankan script ini langsung menggunakan Python 3.{Colors.RESET}\n")

if __name__ == "__main__":
    run_all_scenarios()
