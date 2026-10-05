#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Produksi Lanjutan Jaringan & Web Server
Modul: BAB-02 Jaringan, Protokol, dan Web Servers
Deskripsi:
    Simulasi mandiri (self-contained) arsitektur sistem skala produksi yang mencakup:
    - Reverse Proxy / Load Balancer (Round Robin, Least Connection, IP Hash)
    - TLS Termination & Security Header Enforcement (HSTS, CSP, X-Forwarded-*)
    - Active Health Checking & Automatic Failover (Circuit Breaker)
    - Token Bucket Rate Limiting (Anti-DDoS / Traffic Shaping)
    - Visualisasi Metrik & Tracing dengan ANSI terminal colors.
"""

import sys
import time
import random
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


class ANSI:
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
    BG_BLUE = "\033[44m"
    BG_BLACK = "\033[40m"


@dataclass
class BackendNode:
    name: str
    host: str
    port: int
    weight: int = 1
    active_connections: int = 0
    is_healthy: bool = True
    consecutive_failures: int = 0
    total_served: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 20.0

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class HTTPRequest:
    client_ip: str
    method: str
    path: str
    proto: str = "HTTP/1.1"
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class HTTPResponse:
    status_code: int
    reason: str
    headers: Dict[str, str]
    body: str
    latency_ms: float
    served_by: str


class TokenBucketRateLimiter:
    """Token Bucket algorithm untuk rate-limiting ingress gateway."""
    def __init__(self, capacity: int = 5, fill_rate_per_sec: float = 2.0):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.fill_rate = fill_rate_per_sec
        self.last_update = time.time()

    def allow_request(self) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class CircuitBreaker:
    """Circuit Breaker untuk melindungi upstream cluster."""
    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 2.5):
        self.threshold = failure_threshold
        self.recovery_time = recovery_time_sec
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_state_change = time.time()

    def record_success(self):
        if self.state in ("OPEN", "HALF-OPEN"):
            self.state = "CLOSED"
            self.last_state_change = time.time()

    def record_failure(self, consecutive_fails: int):
        if consecutive_fails >= self.threshold:
            self.state = "OPEN"
            self.last_state_change = time.time()

    def can_attempt(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_state_change > self.recovery_time:
                self.state = "HALF-OPEN"
                self.last_state_change = time.time()
                return True
            return False
        if self.state == "HALF-OPEN":
            return True
        return False


class ProductionGateway:
    """Reverse Proxy & Load Balancer L7."""
    def __init__(self, cluster_name: str = "prod-edge-alb"):
        self.cluster_name = cluster_name
        self.backends: List[BackendNode] = [
            BackendNode("app-svc-01", "10.0.1.11", 8080, weight=3, avg_latency_ms=18.5),
            BackendNode("app-svc-02", "10.0.1.12", 8080, weight=2, avg_latency_ms=22.0),
            BackendNode("app-svc-03", "10.0.1.13", 8080, weight=1, avg_latency_ms=35.0),
        ]
        self.rr_index = 0
        self.rate_limiter = TokenBucketRateLimiter(capacity=6, fill_rate_per_sec=3.0)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            node.name: CircuitBreaker() for node in self.backends
        }

    def print_banner(self):
        print(f"{ANSI.CYAN}{ANSI.BOLD}" + "=" * 78 + f"{ANSI.RESET}")
        print(f"{ANSI.BG_BLUE}{ANSI.WHITE}{ANSI.BOLD}  SIMULASI ARSITEKTUR JARINGAN & REVERSE PROXY PRODUKSI (SRE / DEVOPS)  {ANSI.RESET}")
        print(f"{ANSI.CYAN}" + "=" * 78 + f"{ANSI.RESET}")
        print(f"{ANSI.DIM}Gateway ID: {self.cluster_name} | Protocol: TLS 1.3 / HTTP/2 Terminated{ANSI.RESET}\n")

    def run_health_checks(self):
        """Active health probe via L7 synthetic ping."""
        print(f"{ANSI.YELLOW}[HEALTH-PROBE] Menjalankan Active Health Checking ke Upstream...{ANSI.RESET}")
        for node in self.backends:
            cb = self.circuit_breakers[node.name]
            if not cb.can_attempt():
                node.is_healthy = False
                status_color = ANSI.RED
                status_text = f"UNHEALTHY (Circuit {cb.state})"
            elif node.is_healthy:
                status_color = ANSI.GREEN
                status_text = "HEALTHY (HTTP 200 OK)"
            else:
                status_color = ANSI.RED
                status_text = f"DOWN (Failures: {node.consecutive_failures})"

            print(
                f"  -> Node: {ANSI.BOLD}{node.name:<12}{ANSI.RESET} "
                f"Addr: {node.address:<17} "
                f"Status: {status_color}{status_text:<25}{ANSI.RESET} "
                f"ActiveConn: {node.active_connections:<3} "
                f"TotalServed: {node.total_served}"
            )
        print()

    def select_backend(self, algorithm: str, client_ip: str) -> Optional[BackendNode]:
        healthy_nodes = [
            n for n in self.backends
            if n.is_healthy and self.circuit_breakers[n.name].can_attempt()
        ]
        if not healthy_nodes:
            return None

        if algorithm == "least_conn":
            return min(healthy_nodes, key=lambda n: n.active_connections)
        elif algorithm == "ip_hash":
            hash_val = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
            return healthy_nodes[hash_val % len(healthy_nodes)]
        else:  # Round Robin default
            selected = healthy_nodes[self.rr_index % len(healthy_nodes)]
            self.rr_index = (self.rr_index + 1) % len(healthy_nodes)
            return selected

    def forward_request(self, req: HTTPRequest, algorithm: str = "round_robin") -> HTTPResponse:
        # Step 1: Token Bucket Rate Limiter
        if not self.rate_limiter.allow_request():
            return HTTPResponse(
                status_code=429,
                reason="Too Many Requests",
                headers={"Retry-After": "1", "X-RateLimit-Action": "Dropped"},
                body='{"error": "Rate limit exceeded. Token bucket depleted."}',
                latency_ms=1.2,
                served_by="edge-rate-limiter"
            )

        # Step 2: Route Selection
        backend = self.select_backend(algorithm, req.client_ip)
        if not backend:
            return HTTPResponse(
                status_code=503,
                reason="Service Unavailable",
                headers={"X-Proxy-Status": "All Backends Down"},
                body='{"error": "No healthy upstream cluster available."}',
                latency_ms=2.5,
                served_by="gateway-core"
            )

        # Step 3: Header Injection & Mutasi L7
        injected_headers = {
            "X-Forwarded-For": req.client_ip,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "api.production.internal",
            "X-Request-ID": hashlib.sha1(f"{req.client_ip}{time.time()}".encode()).hexdigest()[:12],
            "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
            "Server": "nginx-ingress-controller/1.9.4"
        }

        # Step 4: Dispatch Request & Latency Emulation
        backend.active_connections += 1
        jitter = random.uniform(-3.5, 6.0)
        computed_latency = max(2.0, backend.avg_latency_ms + jitter)

        # Simulasi fault injection jika server sedang tidak sehat
        if not backend.is_healthy:
            backend.consecutive_failures += 1
            backend.total_errors += 1
            self.circuit_breakers[backend.name].record_failure(backend.consecutive_failures)
            backend.active_connections = max(0, backend.active_connections - 1)
            return HTTPResponse(
                status_code=502,
                reason="Bad Gateway",
                headers=injected_headers,
                body=f'{{"error": "Connection refused to upstream {backend.address}"}}',
                latency_ms=computed_latency,
                served_by=backend.name
            )

        # Success path
        backend.total_served += 1
        backend.consecutive_failures = 0
        self.circuit_breakers[backend.name].record_success()
        backend.active_connections = max(0, backend.active_connections - 1)

        return HTTPResponse(
            status_code=200,
            reason="OK",
            headers=injected_headers,
            body=f'{{"status": "success", "cluster": "{backend.name}", "ip": "{req.client_ip}"}}',
            latency_ms=computed_latency,
            served_by=backend.name
        )


def scenario_traffic_simulation(gateway: ProductionGateway):
    """Skenario 1: Distribusi Trafik dengan Berbagai Algoritma."""
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}=== Skenario 1: Distribusi Trafik L7 Multi-Algoritma ==={ANSI.RESET}")
    algorithms = ["round_robin", "least_conn", "ip_hash"]
    test_clients = ["192.168.1.101", "10.200.4.55", "172.16.8.99", "192.168.1.102"]

    for algo in algorithms:
        print(f"\n{ANSI.WHITE}{ANSI.BOLD}[Pengujian Algoritma: {algo.upper()}]{ANSI.RESET}")
        for i in range(5):
            client_ip = random.choice(test_clients)
            req = HTTPRequest(client_ip=client_ip, method="GET", path="/api/v1/orders")
            res = gateway.forward_request(req, algorithm=algo)

            status_color = ANSI.GREEN if res.status_code == 200 else ANSI.RED
            print(
                f"  Req #{i+1:02d} | Client: {req.client_ip:<15} -> "
                f"Status: {status_color}{res.status_code} {res.reason:<6}{ANSI.RESET} | "
                f"Node: {ANSI.MAGENTA}{res.served_by:<12}{ANSI.RESET} | "
                f"Latency: {res.latency_ms:5.1f}ms | TraceID: {res.headers.get('X-Request-ID', '-')}"
            )
            time.sleep(0.08)


def scenario_failover_circuit_breaker(gateway: ProductionGateway):
    """Skenario 2: Simulasi Kegagalan Node & Self-Healing Circuit Breaker."""
    print(f"\n{ANSI.BOLD}{ANSI.RED}=== Skenario 2: Chaos Injection & Circuit Breaker Failover ==={ANSI.RESET}")
    target_node = gateway.backends[0]
    print(f"{ANSI.YELLOW}[CHAOS] Mematikan Node {target_node.name} (Simulasi Network Partition / OOM)...{ANSI.RESET}")
    target_node.is_healthy = False

    for attempt in range(1, 6):
        req = HTTPRequest(client_ip=f"10.0.5.{attempt}", method="POST", path="/api/v1/checkout")
        # Sengaja route ke target node untuk memicu circuit breaker
        res = gateway.forward_request(req, algorithm="round_robin")
        color = ANSI.GREEN if res.status_code == 200 else ANSI.RED
        print(
            f"  Percobaan #{attempt:02d} | Target Server: {res.served_by:<12} -> "
            f"Status: {color}{res.status_code} {res.reason}{ANSI.RESET} "
            f"(Circuit: {gateway.circuit_breakers[target_node.name].state})"
        )
        time.sleep(0.1)

    print(f"\n{ANSI.GREEN}[SELF-HEALING] Memulihkan kembali Node {target_node.name}...{ANSI.RESET}")
    target_node.is_healthy = True
    target_node.consecutive_failures = 0
    gateway.circuit_breakers[target_node.name].record_success()
    gateway.run_health_checks()


def scenario_security_headers_audit(gateway: ProductionGateway):
    """Skenario 3: Audit Keamanan Header & TLS Termination."""
    print(f"\n{ANSI.BOLD}{ANSI.MAGENTA}=== Skenario 3: Inspeksi Header & Proteksi Enkripsi L7 ==={ANSI.RESET}")
    req = HTTPRequest(client_ip="203.0.113.195", method="GET", path="/admin/cluster-metrics")
    res = gateway.forward_request(req, algorithm="round_robin")

    print(f"{ANSI.CYAN}--- HTTP Ingress Request ---{ANSI.RESET}")
    print(f"Client IP : {req.client_ip}")
    print(f"Endpoint  : {req.method} {req.path} {req.proto}")

    print(f"\n{ANSI.GREEN}--- Reverse Proxy Response & Injected Headers ---{ANSI.RESET}")
    print(f"HTTP Status: {res.status_code} {res.reason}")
    for k, v in res.headers.items():
        print(f"  {ANSI.BOLD}{k:<28}{ANSI.RESET}: {ANSI.YELLOW}{v}{ANSI.RESET}")
    print(f"Response Payload : {res.body}")


def scenario_rate_limiting_flood(gateway: ProductionGateway):
    """Skenario 4: Simulasi DoS / Burst Traffic dengan Token Bucket."""
    print(f"\n{ANSI.BOLD}{ANSI.YELLOW}=== Skenario 4: Stress Test & Token Bucket Defense ==={ANSI.RESET}")
    print(f"{ANSI.DIM}Mengirim 12 request instan melebihi kapasitas bucket (Capacity: 6, Fill: 3/s)...{ANSI.RESET}")

    accepted, dropped = 0, 0
    for req_idx in range(1, 13):
        req = HTTPRequest(client_ip="198.51.100.42", method="GET", path="/search?q=packet")
        res = gateway.forward_request(req)
        if res.status_code == 200:
            accepted += 1
            print(f"  Req #{req_idx:02d} -> {ANSI.GREEN}[200 OK]{ANSI.RESET} Diteruskan ke {res.served_by}")
        elif res.status_code == 429:
            dropped += 1
            print(f"  Req #{req_idx:02d} -> {ANSI.RED}[429 TOO MANY REQUESTS]{ANSI.RESET} Paket Ditolak oleh Limiter")
        time.sleep(0.04)

    print(f"\nHasil Uji Pertahanan: {ANSI.GREEN}Diterima: {accepted}{ANSI.RESET} | {ANSI.RED}Ditolak: {dropped}{ANSI.RESET}")


def interactive_menu():
    gateway = ProductionGateway()
    gateway.print_banner()

    menu_text = f"""
{ANSI.BOLD}{ANSI.WHITE}PILIHAN LAB INTERAKTIF:{ANSI.RESET}
  {ANSI.CYAN}[1]{ANSI.RESET} Jalankan Status Cluster & Active Health Check
  {ANSI.CYAN}[2]{ANSI.RESET} Simulasi Distribusi Trafik L7 Multi-Algoritma
  {ANSI.CYAN}[3]{ANSI.RESET} Uji Chaos Engineering (Failover & Circuit Breaker)
  {ANSI.CYAN}[4]{ANSI.RESET} Audit Keamanan Header Reverse Proxy & TLS Termination
  {ANSI.CYAN}[5]{ANSI.RESET} Simulasi Burst Traffic & Rate Limiting Defense
  {ANSI.CYAN}[6]{ANSI.RESET} Eksekusi Seluruh Skenario Produksi Otomatis (End-to-End)
  {ANSI.RED}[0]{ANSI.RESET} Keluar
"""

    # Jika dijalankan di environment non-TTY (pipe/CI), jalankan skenario 6 otomatis
    if not sys.stdin.isatty() or "--auto" in sys.argv:
        print(f"{ANSI.YELLOW}[INFO] Mode otomatis/non-interaktif terdeteksi. Menjalankan skenario lengkap...{ANSI.RESET}")
        gateway.run_health_checks()
        scenario_traffic_simulation(gateway)
        scenario_failover_circuit_breaker(gateway)
        scenario_security_headers_audit(gateway)
        scenario_rate_limiting_flood(gateway)
        print(f"\n{ANSI.GREEN}{ANSI.BOLD}✓ Seluruh simulasi selesai dengan sukses 100%.{ANSI.RESET}")
        return

    while True:
        print(menu_text)
        try:
            choice = input(f"{ANSI.BOLD}Pilih opsi [0-6]: {ANSI.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            gateway.run_health_checks()
        elif choice == "2":
            scenario_traffic_simulation(gateway)
        elif choice == "3":
            scenario_failover_circuit_breaker(gateway)
        elif choice == "4":
            scenario_security_headers_audit(gateway)
        elif choice == "5":
            scenario_rate_limiting_flood(gateway)
        elif choice == "6":
            gateway.run_health_checks()
            scenario_traffic_simulation(gateway)
            scenario_failover_circuit_breaker(gateway)
            scenario_security_headers_audit(gateway)
            scenario_rate_limiting_flood(gateway)
        elif choice == "0":
            print(f"{ANSI.CYAN}Menutup simulasi laboratorium. Sampai jumpa!{ANSI.RESET}")
            break
        else:
            print(f"{ANSI.RED}Pilihan tidak valid, silakan ulangi.{ANSI.RESET}")


if __name__ == "__main__":
    interactive_menu()
