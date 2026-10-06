#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Observability, Cloud-Native Deployment & GraalVM Native Image
Topik: Java Cloud-Native Observability (Metrics, Traces, Health Probes) & GraalVM AOT Compilation

Simulasi teknis mandiri interaktif dengan output ANSI terminal berwarna.
"""

import time
import random
import uuid
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ANSI Color Codes & Formatting
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

BG_BLACK = "\033[40m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"


def header(text: str) -> None:
    print(f"\n{BOLD}{BG_BLUE}{WHITE}  === {text} ===  {RESET}\n")


def subheader(text: str) -> None:
    print(f"{BOLD}{CYAN}>>> {text}{RESET}")


def success(text: str) -> None:
    print(f"{GREEN}[SUCCESS]{RESET} {text}")


def info(text: str) -> None:
    print(f"{BLUE}[INFO]{RESET} {text}")


def warn(text: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {text}")


def error(text: str) -> None:
    print(f"{RED}[ERROR]{RESET} {text}")


# ----------------------------------------------------------------------
# 1. GRAALVM AOT VS HOTSPOT JVM RUNTIME BENCHMARK SIMULATION
# ----------------------------------------------------------------------
@dataclass
class RuntimeProfile:
    name: str
    startup_time_ms: float
    base_rss_mb: float
    throughput_rps: float
    jit_warmup_required: bool
    reflection_config_needed: bool


def simulate_graalvm_comparison():
    header("SIMULASI 1: GraalVM Native Image (AOT) vs OpenJDK HotSpot (JIT)")

    hotspot = RuntimeProfile(
        name="OpenJDK HotSpot 21 (C2 JIT Compiler)",
        startup_time_ms=1840.0,
        base_rss_mb=285.5,
        throughput_rps=48500.0,
        jit_warmup_required=True,
        reflection_config_needed=False
    )

    graalvm = RuntimeProfile(
        name="GraalVM Native Image (SubstrateVM AOT)",
        startup_time_ms=18.4,
        base_rss_mb=34.2,
        throughput_rps=46200.0,
        jit_warmup_required=False,
        reflection_config_needed=True
    )

    profiles = [hotspot, graalvm]

    for p in profiles:
        color = YELLOW if "HotSpot" in p.name else GREEN
        print(f"{BOLD}{color}[Target: {p.name}]{RESET}")
        print(f"  - Closed-World Assumption : {'ENABLED (Static Analysis)' if p.reflection_config_needed else 'DISABLED (Dynamic ClassLoading)'}")
        print(f"  - Need reflect-config.json: {p.reflection_config_needed}")
        print(f"  - Inisialisasi Bootstrapping...")

        # Visual progress simulation
        steps = 10
        delay = (p.startup_time_ms / 1000.0) / steps
        # Cap delay for responsive CLI demo
        capped_delay = min(delay, 0.08)

        sys.stdout.write("    Booting: [")
        for _ in range(steps):
            time.sleep(capped_delay)
            sys.stdout.write(f"{color}#{RESET}")
            sys.stdout.flush()
        sys.stdout.write(f"] Ready in {BOLD}{p.startup_time_ms:.1f} ms{RESET}!\n")

        print(f"  - Initial Resident Set Size (RSS Memory) : {BOLD}{p.base_rss_mb} MB{RESET}")
        print(f"  - Peak Throughput Capacity                : {p.throughput_rps:,.0f} req/s")
        print(f"  - Warm-up Penalty (JIT Tiered Compiles)   : {'Yes (~15,000 invocations)' if p.jit_warmup_required else 'Zero (Instant Peak)'}")
        print()

    # Comparison Table
    print(f"{BOLD}{MAGENTA}+---------------------------+-----------------------+-------------------------+{RESET}")
    print(f"{BOLD}{MAGENTA}| Metric Karakteristik      | OpenJDK HotSpot (JIT) | GraalVM Native (AOT)    |{RESET}")
    print(f"{BOLD}{MAGENTA}+---------------------------+-----------------------+-------------------------+{RESET}")
    print(f"| Startup Latency           | {RED}1,840.0 ms{RESET}            | {GREEN}18.4 ms (100x faster){RESET}   |")
    print(f"| Base Memory Footprint     | {RED}285.5 MB{RESET}              | {GREEN}34.2 MB (8.3x lighter){RESET}  |")
    print(f"| Peak Throughput (PGO)     | {GREEN}48,500 rps (Slightly +){RESET} | 46,200 rps              |")
    print(f"| Container Scale-to-Zero   | {RED}Tidak Cocok (Serverless){RESET}| {GREEN}Sangat Ideal (KNative){RESET}  |")
    print(f"| Reflection Handling       | {GREEN}Bebas & Dinamis{RESET}         | {YELLOW}Wajib reflect-config.json{RESET}|")
    print(f"{BOLD}{MAGENTA}+---------------------------+-----------------------+-------------------------+{RESET}")


# ----------------------------------------------------------------------
# 2. OPENTELEMETRY TRACE PROPAGATION SIMULATION (W3C TRACE CONTEXT)
# ----------------------------------------------------------------------
@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    duration_ms: float
    attributes: Dict[str, str] = field(default_factory=dict)
    status: str = "OK"


def simulate_opentelemetry_tracing():
    header("SIMULASI 2: OpenTelemetry Distributed Tracing (W3C TraceContext)")
    info("Membangun Distributed Trace untuk skenario: POST /api/v1/orders/checkout")

    trace_id = uuid.uuid4().hex
    root_span_id = uuid.uuid4().hex[:16]

    print(f"\n{BOLD}W3C Traceparent Header:{RESET}")
    print(f"  {CYAN}traceparent: 00-{trace_id}-{root_span_id}-01{RESET} (version-trace_id-parent_id-flags)\n")

    spans: List[Span] = []

    # 1. API Gateway Span
    s1 = Span(
        name="gateway.route_request",
        trace_id=trace_id,
        span_id=root_span_id,
        parent_span_id=None,
        duration_ms=4.2,
        attributes={"http.method": "POST", "http.route": "/api/v1/orders/checkout", "net.peer.ip": "192.168.1.12"}
    )
    spans.append(s1)

    # 2. Order Service (Spring Boot / Quarkus)
    order_span_id = uuid.uuid4().hex[:16]
    s2 = Span(
        name="order-service.create_order",
        trace_id=trace_id,
        span_id=order_span_id,
        parent_span_id=root_span_id,
        duration_ms=42.8,
        attributes={"app.business.order_id": "ORD-99821", "db.system": "postgresql"}
    )
    spans.append(s2)

    # 3. Payment Gateway RPC Call (gRPC Client)
    payment_span_id = uuid.uuid4().hex[:16]
    s3 = Span(
        name="payment-service.process_charge",
        trace_id=trace_id,
        span_id=payment_span_id,
        parent_span_id=order_span_id,
        duration_ms=88.5,
        attributes={"rpc.system": "grpc", "rpc.method": "ProcessPayment", "payment.provider": "MIDTRANS"}
    )
    spans.append(s3)

    # 4. Inventory Reservation Call
    inv_span_id = uuid.uuid4().hex[:16]
    s4 = Span(
        name="inventory-service.reserve_stock",
        trace_id=trace_id,
        span_id=inv_span_id,
        parent_span_id=order_span_id,
        duration_ms=16.3,
        attributes={"inventory.sku": "JAVA-GRAAL-BOOK", "inventory.quantity": "1"}
    )
    spans.append(s4)

    # Visualizing Waterfall Span Graph
    print(f"{BOLD}{WHITE}Trace ID: {trace_id} (Total Spans: {len(spans)}){RESET}")
    total_latency = s1.duration_ms + s2.duration_ms + s3.duration_ms + s4.duration_ms

    for idx, span in enumerate(spans):
        indent = "  " * (0 if span.parent_span_id is None else 1 if span.parent_span_id == root_span_id else 2)
        bar_len = max(2, int(span.duration_ms / 3))
        bar = f"{CYAN}{'█' * bar_len}{RESET}"

        print(f"{indent}{BOLD}span:{RESET} {YELLOW}{span.name:<32}{RESET} [{bar} {span.duration_ms:.1f}ms]")
        print(f"{indent}  ↳ span_id: {span.span_id} | parent: {span.parent_span_id or 'ROOT'}")
        attr_str = ", ".join([f"{k}={v}" for k, v in span.attributes.items()])
        print(f"{indent}  ↳ tags: {DIM}{attr_str}{RESET}")

    success(f"Distributed Tracing Span Waterfall selesai dirender! Estimasi end-to-end: {total_latency:.1f}ms")


# ----------------------------------------------------------------------
# 3. KUBERNETES CLOUD-NATIVE HEALTH PROBES (ACTUATOR / HEALTH)
# ----------------------------------------------------------------------
class HealthProbeSimulator:
    def __init__(self):
        self.is_started = False
        self.is_live = True
        self.is_ready = False
        self.database_connected = False
        self.cache_warm = False

    def simulate_lifecycle(self):
        header("SIMULASI 3: Kubernetes Probes (Startup, Liveness, Readiness)")
        info("Mensimulasikan transisi status Pod Java microservice di Kubernetes cluster...")

        # Phase 1: Startup Probe
        subheader("Fase 1: Kubelet mengecek StartupProbe (/q/health/started atau /actuator/health/startup)")
        for check in range(1, 4):
            time.sleep(0.05)
            if check < 3:
                warn(f"Probe #{check}: StartupProbe -> FAIL (503 Service Unavailable). Application context loading...")
            else:
                self.is_started = True
                self.database_connected = True
                success(f"Probe #{check}: StartupProbe -> PASS (200 OK). Bean creation & DB migration flyway selesai!")

        # Phase 2: Readiness Probe
        subheader("\nFase 2: Kubelet mengecek ReadinessProbe (/actuator/health/readiness)")
        info("Pod siap menerima traffic hanya jika readiness probe status UP.")
        for r_check in range(1, 3):
            time.sleep(0.05)
            if r_check == 1:
                warn(f"Readiness #{r_check}: FAIL (Cache warming in progress, DB connection pool warming)...")
            else:
                self.is_ready = True
                self.cache_warm = True
                success(f"Readiness #{r_check}: UP (200 OK). Traffic Service Endpoint diaktifkan!")

        # Phase 3: Liveness Probe Under Load / Deadlock Check
        subheader("\nFase 3: Kubelet mengecek LivenessProbe (/actuator/health/liveness)")
        info("Liveness membuktikan container process tidak mengalami unrecoverable deadlock.")
        if self.is_live:
            success("Liveness: UP (200 OK). Threads healthy, JVM GC Responsive, Virtual Threads available.")
        else:
            error("Liveness: DOWN (500 Internal Error). Kubelet me-restart Pod otomatis!")


# ----------------------------------------------------------------------
# 4. MICROMETER METRICS SCRAPE SIMULATION (/actuator/prometheus)
# ----------------------------------------------------------------------
def simulate_micrometer_prometheus():
    header("SIMULASI 4: Micrometer Prometheus Endpoint Scrape")
    info("Scraping format standar text Prometheus OpenMetrics dari aplikasi Java:")

    http_requests_count = random.randint(12400, 18500)
    jvm_gc_pause_seconds = random.uniform(0.012, 0.045)
    jvm_threads_live = random.randint(42, 68)
    jvm_memory_used_bytes = random.randint(48 * 1024 * 1024, 75 * 1024 * 1024)

    metrics_payload = f"""# HELP http_server_requests_seconds Duration of HTTP server requests
# TYPE http_server_requests_seconds summary
http_server_requests_seconds{{method="POST",uri="/api/v1/orders/checkout",status="200",quantile="0.5"}} 0.042
http_server_requests_seconds{{method="POST",uri="/api/v1/orders/checkout",status="200",quantile="0.95"}} 0.095
http_server_requests_seconds{{method="POST",uri="/api/v1/orders/checkout",status="200",quantile="0.99"}} 0.185
http_server_requests_seconds_count{{method="POST",uri="/api/v1/orders/checkout",status="200"}} {http_requests_count}

# HELP jvm_memory_used_bytes The amount of used memory
# TYPE jvm_memory_used_bytes gauge
jvm_memory_used_bytes{{area="heap",id="G1 Eden Space"}} {jvm_memory_used_bytes}
jvm_memory_used_bytes{{area="nonheap",id="Metaspace"}} 28410880

# HELP jvm_threads_live_threads The current number of live threads including daemon and non-daemon
# TYPE jvm_threads_live_threads gauge
jvm_threads_live_threads {jvm_threads_live}

# HELP jvm_gc_pause_seconds Time spent in GC pause
# TYPE jvm_gc_pause_seconds summary
jvm_gc_pause_seconds_count 14
jvm_gc_pause_seconds_sum {jvm_gc_pause_seconds:.4f}
"""
    print(f"{DIM}{metrics_payload}{RESET}")
    success(f"Scrape /actuator/prometheus berhasil diparsing oleh Prometheus Collector agent!")


# ----------------------------------------------------------------------
# 5. INTERACTIVE CLI RUNNER
# ----------------------------------------------------------------------
def show_menu():
    print(f"\n{BOLD}{CYAN}=== LAB EXERCISE: CLOUD NATIVE JAVA & OBSERVABILITY ==={RESET}")
    print(f"{WHITE}Pilih skenario laboratorium praktis yang ingin dieksekusi:{RESET}")
    print(f"  {BOLD}1.{RESET} Benchmark GraalVM Native Image vs OpenJDK HotSpot (AOT vs JIT)")
    print(f"  {BOLD}2.{RESET} Simulasi OpenTelemetry Distributed Tracing & W3C Span Flow")
    print(f"  {BOLD}3.{RESET} Simulasi Kubernetes Probes (Startup, Readiness, Liveness)")
    print(f"  {BOLD}4.{RESET} Simulasi Micrometer & Endpoint Prometheus Metrics Scraper")
    print(f"  {BOLD}5.{RESET} Jalankan SEMUA Skenario Sekaligus (Comprehensive Lab Audit)")
    print(f"  {BOLD}0.{RESET} Keluar")


def main():
    print(f"{BOLD}{GREEN}Laboratorium Observability & GraalVM Native Image Java Diinisialisasi.{RESET}")
    
    # Check if running in non-interactive environment (CI/batch)
    if not sys.stdin.isatty():
        info("Non-interactive terminal terdeteksi. Menjalankan seluruh skenario otomatis...")
        simulate_graalvm_comparison()
        simulate_opentelemetry_tracing()
        HealthProbeSimulator().simulate_lifecycle()
        simulate_micrometer_prometheus()
        success("Seluruh skenario laboratorium selesai dieksekusi dengan sukses!")
        return

    while True:
        show_menu()
        try:
            choice = input(f"\n{BOLD}{YELLOW}Masukkan nomor pilihan (0-5): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nProses dihentikan.")
            break

        if choice == "1":
            simulate_graalvm_comparison()
        elif choice == "2":
            simulate_opentelemetry_tracing()
        elif choice == "3":
            HealthProbeSimulator().simulate_lifecycle()
        elif choice == "4":
            simulate_micrometer_prometheus()
        elif choice == "5":
            simulate_graalvm_comparison()
            simulate_opentelemetry_tracing()
            HealthProbeSimulator().simulate_lifecycle()
            simulate_micrometer_prometheus()
            success("Seluruh modul laboratorium selesai dieksekusi!")
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menggunakan Lab Observability Java.{RESET}")
            break
        else:
            warn(f"Pilihan '{choice}' tidak valid. Silakan masukkan angka 0 sampai 5.")


if __name__ == "__main__":
    main()
