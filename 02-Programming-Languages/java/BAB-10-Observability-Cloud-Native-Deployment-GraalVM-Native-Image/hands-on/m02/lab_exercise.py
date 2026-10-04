#!/usr/bin/env python3
"""
Lab Hands-on: Observability, Cloud-Native Deployment & GraalVM Native Image
Deep Dive Simulation: HotSpot JVM vs. GraalVM AOT Substrate VM Execution Profiling,
Kubernetes Probe Lifecycles, and Distributed Tracing Simulation.

Standard Library Only: sys, time, random, uuid, dataclasses, typing
"""

import sys
import time
import random
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# --- ANSI Terminal Aesthetics ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[48;5;236m"


@dataclass
class Span:
    """Represents an OpenTelemetry-compatible tracing span."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time_ns: int
    end_time_ns: int = 0
    attributes: Dict[str, str] = field(default_factory=dict)

    def finish(self):
        self.end_time_ns = time.perf_counter_ns()

    @property
    def duration_ms(self) -> float:
        return (self.end_time_ns - self.start_time_ns) / 1_000_000.0


class ObservabilityTracer:
    """Simulates a lightweight distributed tracing engine (OpenTelemetry/Micrometer)."""
    def __init__(self):
        self.spans: List[Span] = []

    def start_trace(self, operation: str) -> Span:
        trace_id = uuid.uuid4().hex
        span = Span(
            trace_id=trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=None,
            operation_name=operation,
            start_time_ns=time.perf_counter_ns()
        )
        self.spans.append(span)
        return span

    def start_span(self, operation: str, parent: Span) -> Span:
        span = Span(
            trace_id=parent.trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=parent.span_id,
            operation_name=operation,
            start_time_ns=time.perf_counter_ns()
        )
        self.spans.append(span)
        return span


class RuntimeEngine:
    """Base class for Java execution model simulation."""
    def __init__(self, name: str):
        self.name = name
        self.rss_memory_mb: float = 0.0
        self.startup_time_ms: float = 0.0
        self.is_ready: bool = False
        self.is_alive: bool = True
        self.invocations: int = 0

    def boot(self):
        raise NotImplementedError

    def handle_request(self, tracer: ObservabilityTracer, root_span: Span) -> float:
        raise NotImplementedError


class HotSpotJVM(RuntimeEngine):
    """
    Simulates standard OpenJDK HotSpot JVM:
    - Dynamic bytecode loading, Metaspace allocation, Tiered Compilation (C1/C2 JIT).
    - Requires warmup cycles before achieving peak execution efficiency.
    - Higher initial RSS memory baseline.
    """
    def __init__(self):
        super().__init__("HotSpot JVM (OpenJDK 21)")
        self.jit_compiled_tier4 = False

    def boot(self):
        # Hotspot startup involves class verification, Metaspace init, and runtime bytecode interpreter setup
        t0 = time.perf_counter()
        time.sleep(0.120)  # Simulates JVM boot and framework context initialization
        self.rss_memory_mb = 185.0  # Base footprint with Metaspace and dynamic linkers
        self.startup_time_ms = (time.perf_counter() - t0) * 1000.0
        self.is_ready = True

    def handle_request(self, tracer: ObservabilityTracer, root_span: Span) -> float:
        self.invocations += 1
        span = tracer.start_span("HotSpot_Dispatch", root_span)

        # Warmup profile: First 10 invocations use Interpreter/C1 JIT (slow), then C2 optimizes
        if self.invocations <= 5:
            execution_latency_ms = random.uniform(18.0, 32.0)
            compilation_stage = "Bytecode Interpreter (Tier 0)"
            self.rss_memory_mb += 1.2  # Dynamic class loading overhead
        elif self.invocations <= 12:
            execution_latency_ms = random.uniform(8.0, 15.0)
            compilation_stage = "C1 Client Compiler (Tier 3)"
            self.rss_memory_mb += 0.8
        else:
            if not self.jit_compiled_tier4:
                self.jit_compiled_tier4 = True
            execution_latency_ms = random.uniform(1.2, 3.1)
            compilation_stage = "C2 Server Compiler (Tier 4 Peak)"

        # Introduce occasional Safepoint/Stop-the-World Minor GC simulation
        if self.invocations % 8 == 0:
            execution_latency_ms += random.uniform(4.0, 7.0)
            compilation_stage += " [G1GC Safepoint Pause]"
            self.rss_memory_mb -= 2.5

        time.sleep(execution_latency_ms / 1000.0)
        span.attributes["runtime.tier"] = compilation_stage
        span.attributes["runtime.rss_mb"] = f"{self.rss_memory_mb:.1f}"
        span.finish()
        return execution_latency_ms


class GraalVMNativeImage(RuntimeEngine):
    """
    Simulates GraalVM Native Image (Substrate VM):
    - Ahead-Of-Time (AOT) closed-world static analysis.
    - Zero dynamic bytecode interpretation; pre-compiled native machine code.
    - Sub-millisecond initialization, immediate peak throughput, low fixed RSS footprint.
    """
    def __init__(self):
        super().__init__("GraalVM Native Image (SubstrateVM)")

    def boot(self):
        # AOT native binary directly mapped to ELF/Mach-O memory pages
        t0 = time.perf_counter()
        time.sleep(0.005)  # Immediate execution startup
        self.rss_memory_mb = 28.5  # Lean native memory footprint
        self.startup_time_ms = (time.perf_counter() - t0) * 1000.0
        self.is_ready = True

    def handle_request(self, tracer: ObservabilityTracer, root_span: Span) -> float:
        self.invocations += 1
        span = tracer.start_span("GraalVM_AOT_Dispatch", root_span)

        # Immediate peak performance: No JIT warmup stages, no bytecode loading
        execution_latency_ms = random.uniform(1.1, 2.9)
        execution_stage = "AOT Native Assembly (Pre-Compiled)"

        # Serial/Epsilon GC or compact GC footprint without huge metaspace
        if self.invocations % 10 == 0:
            self.rss_memory_mb += 0.1  # Highly predictable heap growth

        time.sleep(execution_latency_ms / 1000.0)
        span.attributes["runtime.tier"] = execution_stage
        span.attributes["runtime.rss_mb"] = f"{self.rss_memory_mb:.1f}"
        span.finish()
        return execution_latency_ms


def simulate_k8s_probes(runtime: RuntimeEngine):
    """Evaluates Kubernetes Readiness and Liveness probe transitions."""
    print(f"  {CLR_CYAN}├── [K8s Probes]{CLR_RESET} Evaluating container lifecycle status...")
    # Liveness probe
    liveness_status = f"{CLR_GREEN}HTTP 200 OK{CLR_RESET}" if runtime.is_alive else f"{CLR_RED}HTTP 500 FAIL{CLR_RESET}"
    # Readiness probe
    readiness_status = f"{CLR_GREEN}HTTP 200 OK (Traffic Allowed){CLR_RESET}" if runtime.is_ready else f"{CLR_YELLOW}HTTP 503 DOWN{CLR_RESET}"

    print(f"  {CLR_CYAN}│   ├── /health/liveness  -> {liveness_status}")
    print(f"  {CLR_CYAN}│   └── /health/readiness -> {readiness_status}")


def execute_workload_simulation(runtime: RuntimeEngine, rounds: int = 15):
    """Executes requests across the lifecycle to observe warmup and memory patterns."""
    tracer = ObservabilityTracer()
    latencies = []

    print(f"\n{CLR_BOLD}{CLR_BLUE}=== Initializing Node: {runtime.name} ==={CLR_RESET}")
    runtime.boot()
    print(f"  {CLR_GREEN}✔ Process Boot Complete:{CLR_RESET} Startup Latency: "
          f"{CLR_BOLD}{runtime.startup_time_ms:.2f} ms{CLR_RESET} | Initial RSS: {runtime.rss_memory_mb:.1f} MB")

    simulate_k8s_probes(runtime)

    print(f"  {CLR_YELLOW}⚡ Ingesting Workload ({rounds} Requests) across OpenTelemetry Trace Context...{CLR_RESET}")

    for idx in range(1, rounds + 1):
        root_span = tracer.start_trace(f"HTTP_GET /api/v1/compute/order-{idx}")
        lat = runtime.handle_request(tracer, root_span)
        root_span.finish()
        latencies.append(lat)

        child_span = tracer.spans[-1]
        tier_info = child_span.attributes.get("runtime.tier", "Unknown")
        rss_info = child_span.attributes.get("runtime.rss_mb", f"{runtime.rss_memory_mb:.1f}")

        # Highlight Warmup (Hotspot) vs Flatline (GraalVM)
        latency_color = CLR_RED if lat > 15.0 else (CLR_YELLOW if lat > 5.0 else CLR_GREEN)
        print(f"  [{idx:02d}] TraceID: {root_span.trace_id[:8]}.. | "
              f"Latency: {latency_color}{lat:5.2f} ms{CLR_RESET} | "
              f"RSS: {rss_info} MB | "
              f"Execution: {CLR_MAGENTA}{tier_info}{CLR_RESET}")

    p99 = sorted(latencies)[int(len(latencies) * 0.95)]
    avg = sum(latencies) / len(latencies)
    print(f"  {CLR_CYAN}└─ Telemetry Metrics: Avg Latency: {avg:.2f} ms | P95: {p99:.2f} ms | Peak RSS: {runtime.rss_memory_mb:.1f} MB{CLR_RESET}")
    return {
        "name": runtime.name,
        "startup": runtime.startup_time_ms,
        "rss_peak": runtime.rss_memory_mb,
        "latencies": latencies,
        "avg": avg,
        "p95": p99
    }


def print_comparison_dashboard(jvm_data: dict, graal_data: dict):
    """Outputs a side-by-side analytical assessment report."""
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}" + "=" * 80 + CLR_RESET)
    print(f"{CLR_BOLD}{CLR_MAGENTA}   CLOUD-NATIVE ARCHITECTURAL TELEMETRY COMPARISON DASHBOARD{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}" + "=" * 80 + CLR_RESET)
    
    header = f"{'Metric / Observation Dimension':<35} | {'HotSpot JVM':<20} | {'GraalVM Native Image':<20}"
    print(CLR_BOLD + header + CLR_RESET)
    print("-" * 80)

    print(f"{'Container Startup Time':<35} | {jvm_data['startup']:<17.2f} ms | {graal_data['startup']:<17.2f} ms")
    print(f"{'Memory Footprint (RSS Peak)':<35} | {jvm_data['rss_peak']:<17.1f} MB | {graal_data['rss_peak']:<17.1f} MB")
    print(f"{'Average Request Latency':<35} | {jvm_data['avg']:<17.2f} ms | {graal_data['avg']:<17.2f} ms")
    print(f"{'P95 Latency (Tail SLa)':<35} | {jvm_data['p95']:<17.2f} ms | {graal_data['p95']:<17.2f} ms")
    print(f"{'Warmup Penalty (Cold Start)':<35} | {CLR_RED}{'High (JIT C1/C2)':<20}{CLR_RESET} | {CLR_GREEN}{'None (AOT Native)':<20}{CLR_RESET}")
    print(f"{'K8s Scaling Appropriateness':<35} | {'Long-running monoliths' :<20} | {'Scale-to-Zero Serverless' :<20}")
    print("-" * 80)
    
    startup_ratio = jvm_data['startup'] / max(graal_data['startup'], 0.001)
    memory_ratio = jvm_data['rss_peak'] / max(graal_data['rss_peak'], 0.001)
    print(f"{CLR_BOLD}Technical Conclusion:{CLR_RESET}")
    print(f" • GraalVM achieved {CLR_GREEN}{startup_ratio:.1f}x faster boot{CLR_RESET} and "
          f"{CLR_GREEN}{memory_ratio:.1f}x lower memory footprint{CLR_RESET}.")
    print(f" • HotSpot JVM guarantees high steady-state optimization through dynamic profile-guided runtime feedback,")
    print(f"   whereas GraalVM Native Image optimizes for horizontal cloud scaling, ephemeral pods, and instant readiness.")
    print(CLR_BOLD + CLR_MAGENTA + "=" * 80 + CLR_RESET + "\n")


def main():
    """Main execution entry point."""
    print(f"{CLR_BOLD}{CLR_CYAN}Starting Lab: Observability & Cloud-Native Runtime Analysis{CLR_RESET}")
    print(f"Simulating Cloud-Native runtime dynamics, MicroProfile health, and OpenTelemetry instrumentation.\n")

    # 1. Profile HotSpot JVM
    hotspot = HotSpotJVM()
    jvm_metrics = execute_workload_simulation(hotspot, rounds=16)

    # 2. Profile GraalVM Native Image
    graal = GraalVMNativeImage()
    graal_metrics = execute_workload_simulation(graal, rounds=16)

    # 3. Output Comparative Telemetry Summary
    print_comparison_dashboard(jvm_metrics, graal_metrics)


if __name__ == "__main__":
    main()