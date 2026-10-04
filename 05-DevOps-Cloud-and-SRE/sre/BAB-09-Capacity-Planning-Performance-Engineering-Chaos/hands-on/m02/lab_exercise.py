#!/usr/bin/env python3
"""
Lab Exercise M02: Production Capacity Planning, Performance Engineering & Chaos Simulation
Kurikulum: BAB-09-Capacity-Planning-Performance-Engineering-Chaos
Topik:
  - Sizing & Little's Law Capacity Sizing (L = λ * W)
  - Saturation Detection (Queueing Theory & M/M/c approximation)
  - Chaos Engineering Fault Injection (Network latency, pod kill, resource leak)
  - Resilience verification: Circuit Breaker & Adaptive Rate Limiting
"""

import sys
import time
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Definitions
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


@dataclass
class ServiceNode:
    node_id: str
    max_concurrency: int = 50
    active_requests: int = 0
    is_healthy: bool = True
    degraded_latency_ms: float = 0.0
    memory_leak_mb: float = 0.0

    def process_request(self, baseline_service_time_ms: float) -> tuple[bool, float]:
        if not self.is_healthy:
            return False, 0.0
        
        # Check node saturation
        if self.active_requests >= self.max_concurrency:
            return False, baseline_service_time_ms  # Rejected / Dropped (Overload)

        self.active_requests += 1
        # Calculate latency with degradation & jitter
        jitter = random.uniform(-2.0, 5.0)
        total_latency = max(1.0, baseline_service_time_ms + self.degraded_latency_ms + jitter)
        
        # Memory pressure penalty
        if self.memory_leak_mb > 500:
            total_latency *= 1.8

        self.active_requests -= 1
        return True, total_latency


class CircuitBreakerState:
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Failing, fast reject
    HALF_OPEN = "HALF_OPEN"# Trial testing recovery


class ResilienceCircuitBreaker:
    def __init__(self, failure_threshold: float = 0.35, recovery_time_s: float = 3.0):
        self.state = CircuitBreakerState.CLOSED
        self.failure_threshold = failure_threshold
        self.recovery_time_s = recovery_time_s
        self.last_state_change = time.time()
        self.recent_errors = 0
        self.recent_requests = 0

    def record_result(self, success: bool):
        self.recent_requests += 1
        if not success:
            self.recent_errors += 1

        error_rate = self.recent_errors / max(1, self.recent_requests)

        now = time.time()
        if self.state == CircuitBreakerState.CLOSED:
            if self.recent_requests >= 20 and error_rate >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.last_state_change = now
                self.recent_requests = 0
                self.recent_errors = 0
        elif self.state == CircuitBreakerState.OPEN:
            if now - self.last_state_change >= self.recovery_time_s:
                self.state = CircuitBreakerState.HALF_OPEN
                self.last_state_change = now
        elif self.state == CircuitBreakerState.HALF_OPEN:
            if success:
                self.state = CircuitBreakerState.CLOSED
                self.recent_requests = 0
                self.recent_errors = 0
            else:
                self.state = CircuitBreakerState.OPEN
                self.last_state_change = now

    def allow_request(self) -> bool:
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_state_change >= self.recovery_time_s:
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        return True


class ClusterArchitecture:
    def __init__(self, num_nodes: int = 4, node_capacity: int = 40):
        self.nodes: List[ServiceNode] = [
            ServiceNode(node_id=f"node-worker-{i+1:02d}", max_concurrency=node_capacity)
            for i in range(num_nodes)
        ]
        self.baseline_service_time_ms = 15.0
        self.circuit_breaker = ResilienceCircuitBreaker()
        self.enable_circuit_breaker = False

    def get_healthy_nodes(self) -> List[ServiceNode]:
        return [node for node in self.nodes if node.is_healthy]

    def dispatch_request(self) -> tuple[bool, float, str]:
        if self.enable_circuit_breaker and not self.circuit_breaker.allow_request():
            return False, 0.5, "CIRCUIT_OPEN_FAST_FAIL"

        healthy_nodes = self.get_healthy_nodes()
        if not healthy_nodes:
            if self.enable_circuit_breaker:
                self.circuit_breaker.record_result(False)
            return False, 0.0, "ALL_NODES_DEAD"

        # Least-connections load balancing
        target_node = min(healthy_nodes, key=lambda n: n.active_requests)
        success, latency = target_node.process_request(self.baseline_service_time_ms)

        if self.enable_circuit_breaker:
            self.circuit_breaker.record_result(success)

        status_msg = "SUCCESS" if success else "NODE_OVERLOAD_SHED"
        return success, latency, status_msg


class ChaosEngine:
    @staticmethod
    def inject_latency_spike(nodes: List[ServiceNode], additional_ms: float = 120.0):
        target = random.choice([n for n in nodes if n.is_healthy])
        target.degraded_latency_ms += additional_ms
        return target.node_id

    @staticmethod
    def terminate_random_node(nodes: List[ServiceNode]) -> Optional[str]:
        healthy = [n for n in nodes if n.is_healthy]
        if not healthy:
            return None
        victim = random.choice(healthy)
        victim.is_healthy = False
        return victim.node_id

    @staticmethod
    def inject_memory_leak(nodes: List[ServiceNode], leak_mb: float = 650.0) -> str:
        target = random.choice(nodes)
        target.memory_leak_mb += leak_mb
        return target.node_id

    @staticmethod
    def heal_all_nodes(nodes: List[ServiceNode]):
        for node in nodes:
            node.is_healthy = True
            node.degraded_latency_ms = 0.0
            node.memory_leak_mb = 0.0


def calculate_percentiles(latencies: List[float]) -> Dict[str, float]:
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    return {
        "p50": sorted_lat[int(n * 0.50)],
        "p95": sorted_lat[min(n - 1, int(n * 0.95))],
        "p99": sorted_lat[min(n - 1, int(n * 0.99))],
        "max": sorted_lat[-1]
    }


def print_banner():
    print(f"{Color.CYAN}{'='*75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE} SRE ADVANCED LAB: CAPACITY PLANNING, PERFORMANCE & CHAOS SIMULATOR{Color.RESET}")
    print(f"{Color.CYAN}{'='*75}{Color.RESET}")
    print(f"{Color.MAGENTA}Domain:{Color.RESET} BAB-09 High-Scale Production Engineering")
    print(f"{Color.MAGENTA}Principles:{Color.RESET} Little's Law, Tail Latencies, Headroom, Simian Faults")
    print(f"{Color.CYAN}{'-'*75}{Color.RESET}")


def run_workload_simulation(cluster: ClusterArchitecture, target_rps: int, duration_seconds: int = 3):
    print(f"\n{Color.YELLOW}[*] Executing Load Test: {target_rps} RPS over {duration_seconds}s...{Color.RESET}")
    total_requests = target_rps * duration_seconds
    latencies: List[float] = []
    success_count = 0
    fail_count = 0
    reasons: Dict[str, int] = {}

    start_sim = time.time()
    for _ in range(total_requests):
        success, lat, reason = cluster.dispatch_request()
        if success:
            success_count += 1
            latencies.append(lat)
        else:
            fail_count += 1
            reasons[reason] = reasons.get(reason, 0) + 1

    pcts = calculate_percentiles(latencies)
    err_rate = (fail_count / total_requests) * 100.0

    # Display results
    print(f"\n{Color.BOLD}--- TELEMETRY & PERFORMANCE REPORT ---{Color.RESET}")
    print(f"Total Traffic   : {Color.WHITE}{total_requests} reqs{Color.RESET}")
    print(f"Successes       : {Color.GREEN}{success_count}{Color.RESET}")
    print(f"Failures        : {Color.RED if fail_count > 0 else Color.GREEN}{fail_count} ({err_rate:.2f}%){Color.RESET}")
    print(f"Latency P50     : {Color.CYAN}{pcts['p50']:.2f} ms{Color.RESET}")
    print(f"Latency P95     : {Color.YELLOW if pcts['p95'] > 50 else Color.GREEN}{pcts['p95']:.2f} ms{Color.RESET}")
    print(f"Latency P99     : {Color.RED if pcts['p99'] > 80 else Color.GREEN}{pcts['p99']:.2f} ms{Color.RESET}")
    print(f"Latency Max     : {pcts['max']:.2f} ms")

    if reasons:
        print(f"{Color.YELLOW}Failure Breakdown:{Color.RESET}")
        for r, cnt in reasons.items():
            print(f"  • {r}: {cnt} reqs")

    # SLO Verification (P99 < 60ms, Error Rate < 1%)
    slo_passed = pcts['p99'] <= 60.0 and err_rate <= 1.0
    status_str = f"{Color.BG_GREEN}{Color.WHITE} SLO MET {Color.RESET}" if slo_passed else f"{Color.BG_RED}{Color.WHITE} SLO BREACHED {Color.RESET}"
    print(f"SLO Target (P99<=60ms, Err<=1%): {status_str}\n")


def calculate_capacity_sizing(cluster: ClusterArchitecture):
    print(f"\n{Color.CYAN}{'='*50}{Color.RESET}")
    print(f"{Color.BOLD}CAPACITY PLANNING: LITTLE'S LAW & QUEUEING SIZING{Color.RESET}")
    print(f"{Color.CYAN}{'='*50}{Color.RESET}")
    healthy_nodes = cluster.get_healthy_nodes()
    total_concurrency = sum(n.max_concurrency for n in healthy_nodes)
    avg_service_time_sec = cluster.baseline_service_time_ms / 1000.0

    # Little's Law: L = λ * W => λ_max = L / W
    theoretical_max_rps = total_concurrency / avg_service_time_sec

    # Recommended safe utilization threshold: 70% (Knee of latency curve)
    safe_operational_rps = theoretical_max_rps * 0.70

    print(f"Active Nodes              : {len(healthy_nodes)} / {len(cluster.nodes)}")
    print(f"Max Concurrent Slots (L)  : {total_concurrency}")
    print(f"Baseline Service Time (W) : {cluster.baseline_service_time_ms:.1f} ms ({avg_service_time_sec:.4f} s)")
    print(f"Theoretical Max Throughput: {Color.YELLOW}{theoretical_max_rps:.0f} RPS{Color.RESET}")
    print(f"Target Safe SRE Operating Capacity (70%): {Color.GREEN}{safe_operational_rps:.0f} RPS{Color.RESET}")
    print(f"{Color.BLUE}Recommendation:{Color.RESET} Set autoscaler scale-up trigger at {safe_operational_rps:.0f} RPS.\n")


def print_cluster_topology(cluster: ClusterArchitecture):
    print(f"\n{Color.BOLD}--- CURRENT CLUSTER TOPOLOGY ---{Color.RESET}")
    for n in cluster.nodes:
        health_icon = f"{Color.GREEN}HEALTHY{Color.RESET}" if n.is_healthy else f"{Color.RED}OFFLINE/DEAD{Color.RESET}"
        degrade_info = f" (+{n.degraded_latency_ms}ms)" if n.degraded_latency_ms > 0 else ""
        leak_info = f" [MemLeak: {n.memory_leak_mb}MB]" if n.memory_leak_mb > 0 else ""
        print(f"  • {n.node_id:<16}: State={health_icon:<18} Cap={n.max_concurrency}{degrade_info}{leak_info}")
    cb_status = f"{Color.GREEN}ENABLED ({cluster.circuit_breaker.state}){Color.RESET}" if cluster.enable_circuit_breaker else f"{Color.WHITE}DISABLED{Color.RESET}"
    print(f"  • Circuit Breaker : {cb_status}\n")


def interactive_menu():
    cluster = ClusterArchitecture(num_nodes=4, node_capacity=30)
    print_banner()

    while True:
        print_cluster_topology(cluster)
        print(f"{Color.BOLD}Select Production Engineering Action:{Color.RESET}")
        print(f" {Color.CYAN}1.{Color.RESET} Run Baseline Workload Benchmark (e.g. 500 RPS)")
        print(f" {Color.CYAN}2.{Color.RESET} Run Stress/Saturation Workload (e.g. 2500 RPS)")
        print(f" {Color.CYAN}3.{Color.RESET} Calculate Capacity & Headroom via Little's Law")
        print(f" {Color.CYAN}4.{Color.RESET} [Chaos] Inject Latency Spike (+180ms to random node)")
        print(f" {Color.CYAN}5.{Color.RESET} [Chaos] Terminate Random Pod (Pod Crash Simulation)")
        print(f" {Color.CYAN}6.{Color.RESET} [Chaos] Inject Memory Leak (Resource Exhaustion)")
        print(f" {Color.CYAN}7.{Color.RESET} Toggle Circuit Breaker & Load Shedding")
        print(f" {Color.CYAN}8.{Color.RESET} Self-Heal Cluster (Restore all nodes to baseline)")
        print(f" {Color.CYAN}9.{Color.RESET} Exit Lab")

        choice = input(f"\n{Color.BOLD}Input choice (1-9): {Color.RESET}").strip()

        if choice == "1":
            run_workload_simulation(cluster, target_rps=600, duration_seconds=2)
        elif choice == "2":
            run_workload_simulation(cluster, target_rps=2600, duration_seconds=2)
        elif choice == "3":
            calculate_capacity_sizing(cluster)
        elif choice == "4":
            node_id = ChaosEngine.inject_latency_spike(cluster.nodes, additional_ms=180.0)
            print(f"{Color.RED}[!] Chaos Applied: Injected +180ms network delay into {node_id}{Color.RESET}")
        elif choice == "5":
            killed = ChaosEngine.terminate_random_node(cluster.nodes)
            if killed:
                print(f"{Color.RED}[!] Chaos Applied: SIGKILL sent to {killed}{Color.RESET}")
            else:
                print(f"{Color.YELLOW}[!] All nodes are already offline!{Color.RESET}")
        elif choice == "6":
            leaked = ChaosEngine.inject_memory_leak(cluster.nodes, leak_mb=700.0)
            print(f"{Color.RED}[!] Chaos Applied: Simulated memory leak (+700MB) on {leaked}{Color.RESET}")
        elif choice == "7":
            cluster.enable_circuit_breaker = not cluster.enable_circuit_breaker
            status = "ENABLED" if cluster.enable_circuit_breaker else "DISABLED"
            print(f"{Color.GREEN}[*] Resilience Circuit Breaker is now {status}.{Color.RESET}")
        elif choice == "8":
            ChaosEngine.heal_all_nodes(cluster.nodes)
            cluster.circuit_breaker.state = CircuitBreakerState.CLOSED
            print(f"{Color.GREEN}[✓] Orchestrator Self-Healing Complete: All pods recreated & healthy.{Color.RESET}")
        elif choice == "9":
            print(f"{Color.GREEN}Terminating SRE Chaos & Capacity Lab. Stay resilient!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Invalid option selected.{Color.RESET}")


if __name__ == "__main__":
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}[*] Lab interrupted by user. Exiting...{Color.RESET}")
        sys.exit(0)
