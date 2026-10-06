#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Komprehensif Arsitektur Full-Stack & Browser Internals
BAB-01: Arsitektur Full-Stack dan Browser Internals

Modul ini mensimulasikan lifecycle request end-to-end dari:
1. Client Navigation & Browser Internals:
   - DNS Resolution (Local Cache, ISP Recursive, Root/TLD/Authoritative)
   - TCP 3-Way Handshake + TLS 1.3 Key Exchange
   - HTTP/2 Stream Multiplexing & Request Transmission
   - Critical Rendering Path (CRP): HTML Parsing, DOM/CSSOM Construction, Layout, Paint, GPU Compositing
2. Edge & Production Infrastructure:
   - Anycast CDN Edge Caching (Hit/Miss, TTL, Stale-While-Revalidate)
   - Layer 7 Reverse Proxy & Web Application Firewall (WAF)
   - Application Gateway & Layer 4/7 Load Balancer
   - Distributed Cache Layer (Redis Cache-Aside Pattern)
   - Database Cluster (Primary Read-Write & Read Replicas)
"""

import os
import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# ANSI Color Formatting & Terminal Helpers
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright Foreground
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Backgrounds
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_DARK = "\033[40m"


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_banner() -> None:
    print(f"{Color.CYAN}{Color.BOLD}╔══════════════════════════════════════════════════════════════════════════════╗{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}║         ENTERPRISE FULL-STACK & BROWSER INTERNALS SIMULATION LAB           ║{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}║         Bab 01: Arsitektur Produksi & Critical Rendering Path (CRP)         ║{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}╚══════════════════════════════════════════════════════════════════════════════╝{Color.RESET}")
    print()


def log_step(phase: str, msg: str, latency_ms: float = 0.0) -> None:
    time_str = f"{Color.BRIGHT_BLACK}[+{latency_ms:6.2f}ms]{Color.RESET}" if latency_ms > 0 else f"{Color.BRIGHT_BLACK}[       ]{Color.RESET}"
    badge = f"{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} {phase:<12} {Color.RESET}"
    print(f" {badge} {time_str} {msg}")
    time.sleep(0.04)


def log_substep(label: str, detail: str, color: str = Color.WHITE) -> None:
    print(f"    {Color.BRIGHT_BLACK}├─{Color.RESET} {Color.BOLD}{label:<18}{Color.RESET}: {color}{detail}{Color.RESET}")
    time.sleep(0.02)


def log_success(msg: str) -> None:
    print(f"    {Color.BRIGHT_GREEN}✔{Color.RESET} {Color.GREEN}{msg}{Color.RESET}")


def log_warning(msg: str) -> None:
    print(f"    {Color.BRIGHT_YELLOW}⚠{Color.RESET} {Color.YELLOW}{msg}{Color.RESET}")


def log_info(msg: str) -> None:
    print(f"    {Color.BRIGHT_CYAN}ℹ{Color.RESET} {Color.CYAN}{msg}{Color.RESET}")


# ==============================================================================
# Domain Models & Enums
# ==============================================================================
class CacheStatus(Enum):
    HIT = "HIT"
    MISS = "MISS"
    STALE = "STALE"


@dataclass
class HttpRequest:
    method: str
    url: str
    host: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    stream_id: int = 1


@dataclass
class HttpResponse:
    status_code: int
    status_text: str
    headers: Dict[str, str]
    body: str
    ttfb_ms: float
    total_latency_ms: float
    cache_status: CacheStatus


# ==============================================================================
# Simulation Engine: Browser Internals & Network Stack
# ==============================================================================
class BrowserNetworkEngine:
    def __init__(self):
        self.local_dns_cache = {"api.tokopedpedia.id": "104.26.12.88"}
        self.tls_session_resumed = False

    def resolve_dns(self, host: str) -> Tuple[str, float]:
        log_step("DNS RESOLVE", f"Resolving domain name: {Color.BOLD}{host}{Color.RESET}")
        t0 = time.time()

        if host in self.local_dns_cache:
            latency = 1.2
            log_substep("Cache Lookup", "Found in browser local DNS cache (TTL: 280s)", Color.GREEN)
            log_substep("Resolved IP", self.local_dns_cache[host], Color.BRIGHT_CYAN)
            return self.local_dns_cache[host], latency

        # Hierarchical DNS lookup simulation
        log_substep("Browser Cache", "MISS", Color.YELLOW)
        log_substep("OS Resolver", "Querying local hosts file & system daemon...", Color.WHITE)
        log_substep("Recursive DNS", "1.1.1.1 (Cloudflare / ISP Resolver)", Color.WHITE)
        log_substep("Root Nameserver", "Querying a.root-servers.net for TLD '.id'", Color.WHITE)
        log_substep("TLD Server", "PANDI TLD NS answered with Authoritative NS ns1.cloudflare.com", Color.WHITE)
        resolved_ip = f"104.26.{random.randint(10, 50)}.{random.randint(2, 250)}"
        self.local_dns_cache[host] = resolved_ip
        latency = round(random.uniform(25.0, 48.0), 2)
        log_substep("Authoritative A", f"{host} -> {resolved_ip}", Color.BRIGHT_GREEN)
        return resolved_ip, latency

    def establish_connection(self, ip: str, port: int = 443) -> float:
        log_step("TCP/TLS HAND", f"Establishing secure transport to {ip}:{port}")
        # TCP 3-Way Handshake
        t_tcp = round(random.uniform(12.0, 20.0), 2)
        log_substep("TCP SYN", f"Client -> SYN seq={random.randint(1000, 9999)} to {ip}:{port}", Color.WHITE)
        log_substep("TCP SYN-ACK", "Server -> SYN-ACK ack=seq+1", Color.WHITE)
        log_substep("TCP ACK", "Client -> ACK -> TCP Connection ESTABLISHED", Color.GREEN)

        # TLS 1.3 Key Exchange (1-RTT)
        t_tls = round(random.uniform(18.0, 32.0), 2)
        log_substep("TLS ClientHello", "Supported Versions: TLS 1.3, Ciphers: TLS_AES_256_GCM_SHA384", Color.WHITE)
        log_substep("Key Share", "ECDH curve: X25519, KeyShare Exchange", Color.WHITE)
        log_substep("TLS ServerHello", "ServerHello + EncryptedExtensions + Certificate + Finished", Color.WHITE)
        log_substep("Security", "ALPN Negotiated Protocol: h2 (HTTP/2)", Color.BRIGHT_CYAN)
        log_substep("Cipher State", "Traffic keys derived. Symmetric encryption activated.", Color.BRIGHT_GREEN)

        return t_tcp + t_tls

    def send_http2_frame(self, req: HttpRequest) -> float:
        log_step("HTTP/2 STREAM", f"Multiplexing stream ID {req.stream_id} over single TCP connection")
        latency = round(random.uniform(3.5, 7.5), 2)
        log_substep("FRAME HEADERS", f"{req.method} {req.url} (HPACK Compressed: 68 bytes)", Color.CYAN)
        log_substep("Pseudo Headers", f":authority={req.host}, :method={req.method}, :path={req.url}", Color.WHITE)
        if req.body:
            log_substep("FRAME DATA", f"Payload size: {len(req.body)} bytes (END_STREAM flag)", Color.WHITE)
        return latency


# ==============================================================================
# Simulation Engine: Backend & Edge Architecture
# ==============================================================================
class BackendProductionCluster:
    def __init__(self):
        self.edge_cdn_cache: Dict[str, Tuple[str, float]] = {
            "/api/v1/catalog/featured": ("""{"items": [{"id": 1, "name": "Cloud Native Architecture Book", "price": 450000}, {"id": 2, "name": "Mechanical Keyboard", "price": 1200000}]}""", time.time())
        }
        self.redis_cache: Dict[str, str] = {
            "user:profile:1001": """{"id": 1001, "name": "Budi Santoso", "tier": "Enterprise VIP", "balance": 7500000}"""
        }
        self.database_primary = {
            "users": {1001: {"name": "Budi Santoso", "tier": "Enterprise VIP", "balance": 7500000}},
            "orders": []
        }
        self.upstream_servers = ["10.0.1.101 (svc-app-01)", "10.0.1.102 (svc-app-02)", "10.0.1.103 (svc-app-03)"]
        self.lb_counter = 0

    def process_request(self, req: HttpRequest) -> HttpResponse:
        total_latency = 0.0

        # Layer 1: Edge CDN Caching
        log_step("EDGE CDN", f"Anycast PoP CGK-01 checking Edge Cache for {req.url}")
        if req.method == "GET" and req.url in self.edge_cdn_cache:
            content, cached_at = self.edge_cdn_cache[req.url]
            edge_lat = round(random.uniform(4.0, 9.0), 2)
            total_latency += edge_lat
            log_substep("CDN Cache", "HIT (Status: HIT, Age: 42s, Cloudflare CF-Cache-Status: HIT)", Color.BRIGHT_GREEN)
            log_substep("Edge Response", "Directly serving from Singapore/Jakarta Edge PoP", Color.GREEN)
            return HttpResponse(
                status_code=200,
                status_text="OK",
                headers={"X-Cache": "HIT", "CF-Cache-Status": "HIT", "Content-Type": "application/json"},
                body=content,
                ttfb_ms=edge_lat,
                total_latency_ms=total_latency,
                cache_status=CacheStatus.HIT
            )

        edge_lat = round(random.uniform(5.0, 10.0), 2)
        total_latency += edge_lat
        log_substep("CDN Cache", "MISS -> Routing to Origin Gateway", Color.YELLOW)

        # Layer 2: WAF & API Gateway / Reverse Proxy
        waf_lat = round(random.uniform(3.0, 6.0), 2)
        total_latency += waf_lat
        log_step("GATEWAY / WAF", "NGINX Ingress Controller & ModSecurity WAF Inspection", waf_lat)
        log_substep("WAF Rule Check", "SQLi: Clean | XSS: Clean | Rate-Limit Token Bucket: OK", Color.GREEN)
        log_substep("mTLS Handshake", "Internal Service Mesh (Envoy/Istio Sidecar) verification", Color.WHITE)

        # Layer 3: Layer 7 Load Balancer
        lb_server = self.upstream_servers[self.lb_counter % len(self.upstream_servers)]
        self.lb_counter += 1
        log_step("LOAD BALANCER", f"Algorithm: Smooth Weighted Round-Robin -> Node: {lb_server}")

        # Layer 4: Application Server & Redis Cache
        app_lat = round(random.uniform(8.0, 15.0), 2)
        total_latency += app_lat
        log_step("MICROSERVICE", f"Running Golang/Node.js Business Logic on {lb_server}", app_lat)

        cache_key = f"cache:{req.url}"
        if req.url in self.redis_cache:
            redis_lat = round(random.uniform(1.2, 2.5), 2)
            total_latency += redis_lat
            log_substep("Redis Cluster", f"CACHE HIT for key '{cache_key}' in RAM (0.8ms)", Color.BRIGHT_GREEN)
            resp_body = self.redis_cache[req.url]
        else:
            log_substep("Redis Cluster", f"CACHE MISS for key '{cache_key}'", Color.YELLOW)
            # Layer 5: PostgreSQL Primary/Replica Query
            db_lat = round(random.uniform(14.0, 30.0), 2)
            total_latency += db_lat
            if req.method == "GET":
                log_step("DB REPLICA", "Routing Read Query to PostgreSQL Replica #2 (pgpool-II)", db_lat)
                log_substep("SQL Execution", "SELECT id, name, sku, price, stock FROM inventory WHERE is_active=true LIMIT 20;", Color.WHITE)
                log_substep("Query Planner", "Index Scan using idx_inventory_active on inventory (cost=0.29..8.31)", Color.CYAN)
            else:
                log_step("DB PRIMARY", "Routing Write/Transaction to PostgreSQL Primary (WAL Enabled)", db_lat)
                log_substep("ACID Tx", "BEGIN; UPDATE accounts SET balance = balance - 50000; COMMIT;", Color.BRIGHT_YELLOW)
                log_substep("WAL Replication", "Streaming WAL to 2 Synchronous Standby Nodes", Color.WHITE)

            resp_body = f"""{{"status": "success", "data": {{"entity": "{req.url}", "timestamp": {int(time.time())}, "cluster_node": "{lb_server}"}}}}"""
            self.redis_cache[req.url] = resp_body
            log_substep("Cache Population", "Populated key into Redis with TTL 300s", Color.GREEN)

        ttfb = total_latency
        return HttpResponse(
            status_code=200,
            status_text="OK",
            headers={"X-Cache": "MISS", "Server": "k8s-ingress-nginx", "Content-Type": "application/json"},
            body=resp_body,
            ttfb_ms=ttfb,
            total_latency_ms=total_latency + round(random.uniform(4.0, 8.0), 2),
            cache_status=CacheStatus.MISS
        )


# ==============================================================================
# Simulation Engine: Critical Rendering Path (CRP) in Browser
# ==============================================================================
class CriticalRenderingPathEngine:
    @staticmethod
    def execute_crp_pipeline() -> None:
        print()
        print(f"{Color.BG_MAGENTA}{Color.WHITE}{Color.BOLD} === BROWSER INTERNALS: CRITICAL RENDERING PATH (CRP) === {Color.RESET}")
        time.sleep(0.05)

        # 1. Parsing & DOM Construction
        t_dom = round(random.uniform(8.0, 16.0), 2)
        log_step("CRP: DOM TREE", "Byte Stream -> Tokenization -> Node Hierarchy -> DOM Tree", t_dom)
        log_substep("Tokens", "<!DOCTYPE html>, <html>, <head>, <script defer>, <body>, <main>", Color.WHITE)
        log_substep("Preload Scanner", "Speculative parser detected styles.css, app.js, hero.webp", Color.BRIGHT_CYAN)

        # 2. CSSOM Construction
        t_cssom = round(random.uniform(6.0, 12.0), 2)
        log_step("CRP: CSSOM", "Parsing CSS rules & Computing Cascading Specificity", t_cssom)
        log_substep("Render-Blocking", "CSS is render-blocking: Execution paused until CSSOM is ready", Color.YELLOW)
        log_substep("Computed Styles", "Resolved 420 selectors, CSS Variables, and Flexbox properties", Color.WHITE)

        # 3. Render Tree
        t_rt = round(random.uniform(3.0, 6.0), 2)
        log_step("CRP: RENDER", "Merging DOM + CSSOM into Render Tree", t_rt)
        log_substep("Filtering", "Nodes with `display: none` and `<head>` excluded from Render Tree", Color.WHITE)
        log_substep("Pseudo-elements", "::before and ::after rendered elements injected", Color.WHITE)

        # 4. Layout (Reflow)
        t_layout = round(random.uniform(9.0, 18.0), 2)
        log_step("CRP: LAYOUT", "Calculating geometric coordinates (x, y, width, height) of every box", t_layout)
        log_substep("Box Model", "Evaluating Viewport (1920x1080) -> Calculating relative percentages", Color.WHITE)
        log_substep("Reflow Warning", "Frequent DOM mutations here trigger layout thrashing!", Color.BRIGHT_YELLOW)

        # 5. Paint (Rasterization)
        t_paint = round(random.uniform(7.0, 14.0), 2)
        log_step("CRP: PAINT", "Converting layout boxes into actual screen pixels (Rasterization)", t_paint)
        log_substep("Display List", "Generating draw commands: drawRect, drawText, drawImage", Color.WHITE)
        log_substep("Layer Split", "Promoted sticky navbar and animated modal to dedicated GPU layers", Color.BRIGHT_CYAN)

        # 6. Composite (GPU)
        t_comp = round(random.uniform(2.5, 5.0), 2)
        log_step("CRP: COMPOSITE", "GPU Compositor draws textures to screen frame buffer (60/120 FPS)", t_comp)
        log_substep("Hardware Accel", "Direct-3D / Metal / OpenGL raster pipeline complete", Color.BRIGHT_GREEN)
        log_substep("V-Sync Signal", "Frame rendered successfully within 16.6ms frame budget", Color.GREEN)


# ==============================================================================
# Interactive Simulation Controller
# ==============================================================================
class SimulationCLI:
    def __init__(self):
        self.network = BrowserNetworkEngine()
        self.cluster = BackendProductionCluster()

    def run_full_trace(self, url_path: str = "/api/v1/catalog/featured", method: str = "GET") -> None:
        host = "api.tokopedpedia.id"
        print(f"\n{Color.BOLD}{Color.YELLOW}>>> MEMULAI TRACE KOMPLET: {method} https://{host}{url_path}{Color.RESET}\n")

        t_start = time.time()
        # 1. DNS
        ip, dns_lat = self.network.resolve_dns(host)
        # 2. TCP + TLS
        conn_lat = self.network.establish_connection(ip, 443)
        # 3. HTTP/2 Transmission
        req = HttpRequest(method=method, url=url_path, host=host, stream_id=random.choice([1, 3, 5]))
        h2_lat = self.network.send_http2_frame(req)
        # 4. Backend Edge & Origin Execution
        resp = self.cluster.process_request(req)
        # 5. Critical Rendering Path (if rendering web document or SPA)
        CriticalRenderingPathEngine.execute_crp_pipeline()

        total_elapsed = dns_lat + conn_lat + h2_lat + resp.total_latency_ms
        print()
        print(f"{Color.GREEN}{Color.BOLD}╔══════════════════════════════════════════════════════════════════════════════╗{Color.RESET}")
        print(f"{Color.GREEN}{Color.BOLD}║                        SUMMARY METRICS & WATERFALL                           ║{Color.RESET}")
        print(f"{Color.GREEN}{Color.BOLD}╚══════════════════════════════════════════════════════════════════════════════╝{Color.RESET}")
        print(f"  • {Color.BOLD}DNS Resolution Latency{Color.RESET}   : {dns_lat:6.2f} ms")
        print(f"  • {Color.BOLD}TCP 3-Way + TLS 1.3{Color.RESET}       : {conn_lat:6.2f} ms")
        print(f"  • {Color.BOLD}Time to First Byte (TTFB){Color.RESET} : {resp.ttfb_ms:6.2f} ms")
        print(f"  • {Color.BOLD}Cache Status{Color.RESET}               : {Color.BRIGHT_GREEN if resp.cache_status == CacheStatus.HIT else Color.BRIGHT_YELLOW}{resp.cache_status.value}{Color.RESET}")
        print(f"  • {Color.BOLD}HTTP Status Code{Color.RESET}           : {Color.GREEN}{resp.status_code} {resp.status_text}{Color.RESET}")
        print(f"  • {Color.BOLD}Total End-to-End Latency{Color.RESET}   : {Color.BRIGHT_CYAN}{total_elapsed:6.2f} ms{Color.RESET}")
        print()

    def display_menu(self) -> None:
        print_banner()
        print(f"{Color.BOLD}PILIHAN SKENARIO SIMULASI:{Color.RESET}")
        print(f"  {Color.CYAN}[1]{Color.RESET} Simulasi Skenario 1: {Color.BOLD}CDN Cache Hit{Color.RESET} (Ultra Fast Edge Delivery)")
        print(f"  {Color.CYAN}[2]{Color.RESET} Simulasi Skenario 2: {Color.BOLD}CDN Cache Miss -> Redis Cache Hit{Color.RESET}")
        print(f"  {Color.CYAN}[3]{Color.RESET} Simulasi Skenario 3: {Color.BOLD}Full Miss -> PostgreSQL Primary/Replica Deep Query{Color.RESET}")
        print(f"  {Color.CYAN}[4]{Color.RESET} Simulasi Skenario 4: {Color.BOLD}Browser CRP Bottleneck{Color.RESET} (Reflow & Paint Analysis)")
        print(f"  {Color.CYAN}[5]{Color.RESET} Jalankan {Color.BOLD}Automated Benchmarking Suite{Color.RESET} (Semua Skenario)")
        print(f"  {Color.RED}[q]{Color.RESET} Keluar (Exit)")
        print()

    def run_interactive(self) -> None:
        while True:
            self.display_menu()
            choice = input(f"{Color.YELLOW}{Color.BOLD}Pilih opsi (1-5 / q): {Color.RESET}").strip()
            if choice.lower() == "q":
                print(f"\n{Color.GREEN}Terima kasih! Lab simulasi selesai.{Color.RESET}")
                break
            elif choice == "1":
                self.run_full_trace("/api/v1/catalog/featured", "GET")
            elif choice == "2":
                self.run_full_trace("/api/v1/user/profile/1001", "GET")
            elif choice == "3":
                self.run_full_trace(f"/api/v1/orders/checkout/{random.randint(5000, 9999)}", "POST")
            elif choice == "4":
                CriticalRenderingPathEngine.execute_crp_pipeline()
            elif choice == "5":
                print(f"\n{Color.MAGENTA}{Color.BOLD}=== MENJALANKAN BENCHMARK AUTOMATISASI 3 SKENARIO ==={Color.RESET}\n")
                self.run_full_trace("/api/v1/catalog/featured", "GET")
                self.run_full_trace("/api/v1/user/profile/1001", "GET")
                self.run_full_trace("/api/v1/inventory/search?q=database", "GET")
                break
            else:
                print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")
                time.sleep(1)


# ==============================================================================
# Main Execution Entrypoint
# ==============================================================================
if __name__ == "__main__":
    cli = SimulationCLI()
    # If run in non-interactive / CI / piped mode, run automated benchmark suite directly
    if not sys.stdin.isatty() or len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        print(f"{Color.CYAN}Mode Non-Interaktif / CI terdeteksi. Menjalankan skenario otomatis...{Color.RESET}")
        cli.run_full_trace("/api/v1/catalog/featured", "GET")
        cli.run_full_trace("/api/v1/user/profile/1001", "GET")
        cli.run_full_trace("/api/v1/orders/create", "POST")
        print(f"\n{Color.BRIGHT_GREEN}Simulasi valid 100% dan berhasil diselesaikan.{Color.RESET}")
    else:
        cli.run_interactive()
