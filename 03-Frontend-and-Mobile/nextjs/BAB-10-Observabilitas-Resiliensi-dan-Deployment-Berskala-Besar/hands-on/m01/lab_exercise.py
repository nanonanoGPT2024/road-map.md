#!/usr/bin/env python3
"""
Lab Exercise: Next.js Observabilitas, Resiliensi, dan Deployment Berskala Besar
Simulasi Teknis Mandiri:
1. OpenTelemetry Tracing & Instrumentation Hook (instrumentation.ts)
2. Circuit Breaker & Resilient Fallback Pattern
3. Health Check Endpoints (/api/healthz, /api/readyz)
4. Canary Deployment & Traffic Splitting Engine
"""

import sys
import time
import random
import uuid
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
BG_BLUE = "\033[44m"
BG_DARK = "\033[40m"

def print_header(title: str) -> None:
    print(f"\n{BG_BLUE}{WHITE}{BOLD} === {title.upper()} === {RESET}\n")

def print_metric(label: str, value: Any, color: str = CYAN) -> None:
    print(f"  {BOLD}• {label:<28}:{RESET} {color}{value}{RESET}")

class OpenTelemetrySimulator:
    """Simulasi OpenTelemetry Distributed Tracing pada Next.js instrumentation.ts"""
    
    def __init__(self, service_name: str = "nextjs-storefront-prod"):
        self.service_name = service_name
        self.active_trace_id: Optional[str] = None

    def start_trace(self, operation_name: str) -> str:
        self.active_trace_id = uuid.uuid4().hex[:16]
        span_id = uuid.uuid4().hex[:8]
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        print(f"{MAGENTA}[OTel Trace Started]{RESET} {BOLD}{operation_name}{RESET}")
        print(f"  TraceID: {YELLOW}{self.active_trace_id}{RESET} | SpanID: {CYAN}{span_id}{RESET} | Timestamp: {timestamp}")
        return span_id

    def record_span(self, parent_span: str, span_name: str, duration_ms: float, status: str = "OK") -> None:
        span_id = uuid.uuid4().hex[:8]
        status_color = GREEN if status == "OK" else RED
        print(f"  └── [Span] {BOLD}{span_name:<24}{RESET} Parent:{parent_span} ID:{span_id} Latency:{duration_ms:5.1f}ms Status:{status_color}{status}{RESET}")

class CircuitBreaker:
    """
    Simulasi Circuit Breaker Pattern untuk Dependensi Mikroservis / Downstream API
    States: CLOSED (Normal), OPEN (Failing/Tripped), HALF-OPEN (Testing Recovery)
    """
    def __init__(self, failure_threshold: int = 3, recovery_time: float = 4.0):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, downstream_func, *args, **kwargs) -> Dict[str, Any]:
        current_time = time.time()

        # Cek transisi OPEN -> HALF-OPEN
        if self.state == "OPEN":
            if current_time - self.last_failure_time > self.recovery_time:
                self.state = "HALF-OPEN"
                print(f"    {YELLOW}⚡ Circuit Breaker State Transition -> HALF-OPEN (Testing probe){RESET}")
            else:
                remaining = self.recovery_time - (current_time - self.last_failure_time)
                print(f"    {RED}⛔ Circuit is OPEN! Request short-circuited. Cooldown remaining: {remaining:.1f}s{RESET}")
                return {"status": 503, "data": None, "fallback": True, "source": "Edge-Cache-Fallback"}

        try:
            result = downstream_func(*args, **kwargs)
            # Jika sukses saat HALF-OPEN, reset ke CLOSED
            if self.state == "HALF-OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                print(f"    {GREEN}✔ Service recovered! Circuit Breaker reset -> CLOSED{RESET}")
            return {"status": 200, "data": result, "fallback": False, "source": "Downstream-API"}
        except Exception as exc:
            self.failure_count += 1
            self.last_failure_time = current_time
            print(f"    {RED}✘ Request Failed ({exc}). Fail count: {self.failure_count}/{self.failure_threshold}{RESET}")
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                print(f"    {RED}{BOLD}🚨 Threshold reached! Tripping Circuit Breaker -> OPEN{RESET}")
            
            return {"status": 500, "data": None, "fallback": True, "source": "Static-Stale-SWR-Fallback"}

class DeploymentHealthMonitor:
    """Simulasi Liveness & Readiness Probes Kubernetes/Container Deployment"""
    
    def __init__(self):
        self.db_connected = True
        self.redis_connected = True
        self.is_draining = False

    def liveness_probe(self) -> Dict[str, Any]:
        """/api/healthz - Cek apakah proses node masih running"""
        return {"status": "UP", "code": 200, "uptime_seconds": 3600}

    def readiness_probe(self) -> Dict[str, Any]:
        """/api/readyz - Cek apakah instance siap menerima traffic dari load balancer"""
        ready = self.db_connected and self.redis_connected and not self.is_draining
        return {
            "status": "READY" if ready else "OUT_OF_SERVICE",
            "code": 200 if ready else 503,
            "checks": {
                "database": "UP" if self.db_connected else "DOWN",
                "redis_cache": "UP" if self.redis_connected else "DOWN",
                "traffic_drain": "ACTIVE" if self.is_draining else "INACTIVE"
            }
        }

class CanaryTrafficRouter:
    """Simulasi Traffic Splitting Canary Deployment (e.g. Istio / Cloudflare Worker / AWS ALB)"""
    
    def __init__(self, canary_weight_percent: int = 15):
        self.canary_weight = canary_weight_percent
        self.stable_version = "v14.2.1-stable"
        self.canary_version = "v15.0.0-rc2"

    def route_request(self, user_id: str) -> Dict[str, str]:
        # Hash user_id untuk konsistensi sticky-session
        deterministic_hash = hash(user_id) % 100
        if deterministic_hash < self.canary_weight:
            return {"version": self.canary_version, "cluster": "canary-pool", "bucket": "experimental"}
        return {"version": self.stable_version, "cluster": "stable-pool", "bucket": "baseline"}

def simulate_flaky_payment_gateway(fail_probability: float = 0.7) -> Dict[str, str]:
    """Mocking downstream flaky payment service"""
    if random.random() < fail_probability:
        raise ConnectionResetError("Remote host upstream timeout (504 GATEWAY_TIMEOUT)")
    return {"transaction_id": f"txn_{random.randint(10000, 99999)}", "status": "APPROVED"}

def interactive_dashboard():
    otel = OpenTelemetrySimulator()
    cb = CircuitBreaker(failure_threshold=2, recovery_time=3.0)
    health = DeploymentHealthMonitor()
    router = CanaryTrafficRouter(canary_weight_percent=25)

    print(f"{BOLD}{CYAN}========================================================================={RESET}")
    print(f"{BOLD}{GREEN} NEXT.JS PRODUCTION OBSERVABILITY & RESILIENCE SIMULATOR{RESET}")
    print(f"{BOLD}{WHITE} BAB 10: Observabilitas, Resiliensi, dan Deployment Berskala Besar{RESET}")
    print(f"{BOLD}{CYAN}========================================================================={RESET}")

    # 1. Distributed Tracing Simulation
    print_header("1. OpenTelemetry Distributed Tracing (instrumentation.ts)")
    root_span = otel.start_trace("GET /api/checkout/process")
    time.sleep(0.05)
    otel.record_span(root_span, "nextjs.middleware", 12.4, "OK")
    otel.record_span(root_span, "auth.verify-jwt", 18.2, "OK")
    otel.record_span(root_span, "render.rsc-payload", 45.8, "OK")
    otel.record_span(root_span, "db.query.products", 32.1, "OK")
    otel.record_span(root_span, "downstream.payment-gateway", 125.6, "OK")

    # 2. Resiliensi & Circuit Breaker Simulation
    print_header("2. Circuit Breaker & Graceful Fallback Simulation")
    print(f"{DIM}Memicu 6 request berturut-turut ke downstream yang tidak stabil:{RESET}")
    
    for req_idx in range(1, 7):
        print(f"\n  [Request #{req_idx}] Memanggil External Payment Provider...")
        res = cb.call(simulate_flaky_payment_gateway, fail_probability=0.75)
        if res["fallback"]:
            print(f"    {YELLOW}↳ Response Disajikan via [{res['source']}] Status: {res['status']}{RESET}")
        else:
            print(f"    {GREEN}↳ Sukses dari [{res['source']}]: {res['data']}{RESET}")
        time.sleep(0.3)

    # 3. Liveness and Readiness Probe
    print_header("3. Container Orchestration Health Probes")
    print("• Skenario 1: Kondisi Sehat (Baseline)")
    ready_baseline = health.readiness_probe()
    live_baseline = health.liveness_probe()
    print_metric("Liveness (/api/healthz)", f"{live_baseline['status']} ({live_baseline['code']})", GREEN)
    print_metric("Readiness (/api/readyz)", f"{ready_baseline['status']} ({ready_baseline['code']})", GREEN)

    print("\n• Skenario 2: Simulasi Gangguan Redis & Graceful Draining")
    health.redis_connected = False
    health.is_draining = True
    ready_degraded = health.readiness_probe()
    print_metric("Redis Cache Status", ready_degraded['checks']['redis_cache'], RED)
    print_metric("Traffic Draining", ready_degraded['checks']['traffic_drain'], YELLOW)
    print_metric("Readiness (/api/readyz)", f"{ready_degraded['status']} ({ready_degraded['code']})", RED)
    print(f"  {DIM}Kube-Proxy/Ingress akan otomatis mencabut pod ini dari routing pool!{RESET}")

    # 4. Canary Deployment Traffic Splitting
    print_header("4. Canary Deployment Traffic Distribution (25% Weight)")
    sample_users = [f"usr_{100 + i}" for i in range(12)]
    counts = {"stable-pool": 0, "canary-pool": 0}
    
    print(f"  {'USER ID':<14} | {'CLUSTER':<16} | {'TARGET VERSION':<18} | {'ROUTING'}")
    print(f"  {'-'*14}-+-{'-'*16}-+-{'-'*18}-+-{'-'*12}")
    for u in sample_users:
        route = router.route_request(u)
        counts[route['cluster']] += 1
        tag_color = MAGENTA if route['cluster'] == "canary-pool" else BLUE
        print(f"  {u:<14} | {tag_color}{route['cluster']:<16}{RESET} | {BOLD}{route['version']:<18}{RESET} | {route['bucket']}")

    print(f"\n  {BOLD}Ringkasan Distribusi Traffic:{RESET}")
    print_metric("Stable Pool (v14.2)", f"{counts['stable-pool']} users ({counts['stable-pool']/len(sample_users)*100:.1f}%)", BLUE)
    print_metric("Canary Pool (v15.0)", f"{counts['canary-pool']} users ({counts['canary-pool']/len(sample_users)*100:.1f}%)", MAGENTA)

    print(f"\n{BOLD}{GREEN}✔ Simulasi Bab 10 Observabilitas & Resiliensi Berhasil Dijalankan!{RESET}\n")

if __name__ == "__main__":
    interactive_dashboard()
