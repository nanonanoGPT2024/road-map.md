#!/usr/bin/env python3
"""
Lab Hands-on: Automated Canary Deployment & Automated Rollback Engine
Category: 01-Core-Foundations | Chapter 07: Continuous Delivery & Automated Deployment (CD)

Simulates an advanced Continuous Delivery (CD) progressive deployment pipeline:
- Traffic shifting router (0% -> 10% -> 50% -> 100%)
- Multi-instance service pool (Stable vs Canary)
- Real-time SLA/SLO evaluation (Error Rate threshold, Latency p95)
- Automated Rollback Engine upon metric deviation
"""

import time
import random
import hashlib
import sys
from dataclasses import dataclass
from typing import List, Dict, Tuple

# --- ANSI Terminal Formatting ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"


@dataclass
class ReleaseArtifact:
    """Represents an immutable deployable build artifact."""
    version: str
    git_sha: str
    has_defect: bool

    def verify_integrity(self) -> str:
        """Simulates checksum verification of the artifact binary."""
        payload = f"{self.version}-{self.git_sha}".encode()
        return hashlib.sha256(payload).hexdigest()[:12]


class ServiceInstance:
    """Simulates a microservice workload container/pod handling requests."""
    def __init__(self, instance_id: str, artifact: ReleaseArtifact):
        self.instance_id = instance_id
        self.artifact = artifact

    def process_request(self) -> Tuple[int, float]:
        """
        Simulates request execution:
        Returns: (HTTP status code, response time in ms)
        """
        if self.artifact.has_defect:
            # Latency degradation and elevated HTTP 5xx error rate
            latency = random.uniform(80.0, 320.0)
            status = 500 if random.random() < 0.28 else 200
        else:
            # Nominal production traffic profile
            latency = random.uniform(20.0, 65.0)
            status = 500 if random.random() < 0.01 else 200

        return status, latency


class LoadBalancerRouter:
    """Dynamic traffic router managing weighted traffic routing."""
    def __init__(self, stable_instances: List[ServiceInstance], canary_instances: List[ServiceInstance]):
        self.stable_pool = stable_instances
        self.canary_pool = canary_instances
        self.canary_weight = 0.0  # Percentage from 0.0 to 1.0

    def set_canary_weight(self, weight: float):
        self.canary_weight = max(0.0, min(1.0, weight))

    def route_request(self) -> Tuple[str, int, float]:
        """Routes a single request based on traffic split weights."""
        if self.canary_pool and random.random() < self.canary_weight:
            target = random.choice(self.canary_pool)
            target_env = "CANARY"
        else:
            target = random.choice(self.stable_pool)
            target_env = "STABLE"

        status, latency = target.process_request()
        return target_env, status, latency


class CanaryDeploymentOrchestrator:
    """
    Automated Continuous Delivery Pipeline Controller:
    Implements Progressive Canary Analysis (ACA) and Fast-Rollback strategies.
    """
    def __init__(self, max_error_rate: float = 0.05, max_p95_latency_ms: float = 120.0):
        self.max_error_rate = max_error_rate
        self.max_p95_latency_ms = max_p95_latency_ms

    def run_telemetry_probe(self, router: LoadBalancerRouter, sample_count: int = 100) -> Dict[str, Dict[str, float]]:
        """Collects telemetry over a discrete batch of real-time requests."""
        metrics = {
            "STABLE": {"requests": 0, "errors": 0, "latencies": []},
            "CANARY": {"requests": 0, "errors": 0, "latencies": []}
        }

        for _ in range(sample_count):
            env, status, latency = router.route_request()
            metrics[env]["requests"] += 1
            if status >= 500:
                metrics[env]["errors"] += 1
            metrics[env]["latencies"].append(latency)

        summary = {}
        for env, data in metrics.items():
            reqs = data["requests"]
            if reqs == 0:
                continue
            err_rate = data["errors"] / reqs
            sorted_lat = sorted(data["latencies"])
            p95_idx = int(0.95 * len(sorted_lat)) - 1
            p95_latency = sorted_lat[max(0, p95_idx)]
            summary[env] = {
                "requests": reqs,
                "error_rate": err_rate,
                "p95_latency": p95_latency,
                "avg_latency": sum(sorted_lat) / reqs
            }
        return summary

    def execute_deployment(self, stable_artifact: ReleaseArtifact, target_artifact: ReleaseArtifact) -> bool:
        """
        Executes progressive delivery across defined stages:
        [10% -> 25% -> 50% -> 100%]
        """
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== INITIATING AUTOMATED CD PIPELINE ==={CLR_RESET}")
        print(f"Target Artifact : {target_artifact.version} (SHA: {target_artifact.git_sha})")
        print(f"Checksum Valid  : {target_artifact.verify_integrity()}")
        print(f"SLA Thresholds  : Max Error Rate: {self.max_error_rate*100:.1f}%, Max P95 Latency: {self.max_p95_latency_ms}ms\n")

        # Provision node clusters
        stable_nodes = [ServiceInstance(f"stable-srv-{i+1}", stable_artifact) for i in range(3)]
        canary_nodes = [ServiceInstance(f"canary-srv-{i+1}", target_artifact) for i in range(2)]
        router = LoadBalancerRouter(stable_nodes, canary_nodes)

        stages = [0.10, 0.25, 0.50, 1.00]

        for stage_idx, weight in enumerate(stages, start=1):
            router.set_canary_weight(weight)
            print(f"{CLR_BLUE}[Stage {stage_idx}/{len(stages)}]{CLR_RESET} Shifting Traffic: {CLR_BOLD}{int(weight * 100)}% -> CANARY{CLR_RESET}")
            time.sleep(0.6)  # Simulate traffic propagation interval

            summary = self.run_telemetry_probe(router, sample_count=120)
            canary_stats = summary.get("CANARY")

            if not canary_stats:
                continue

            err_rate = canary_stats["error_rate"]
            p95_lat = canary_stats["p95_latency"]

            print(f"  └─ Telemetry: Requests={canary_stats['requests']} | "
                  f"Error Rate={err_rate*100:4.1f}% | P95 Latency={p95_lat:5.1f}ms")

            # Health Verification & Automated Canary Analysis (ACA)
            is_breached = (err_rate > self.max_error_rate) or (p95_lat > self.max_p95_latency_ms)

            if is_breached:
                print(f"{CLR_RED}{CLR_BOLD}  [ALERT] SLO Breach Detected on Canary!{CLR_RESET}")
                if err_rate > self.max_error_rate:
                    print(f"    - Error Rate: {err_rate*100:.2f}% (Limit: {self.max_error_rate*100:.2f}%)")
                if p95_lat > self.max_p95_latency_ms:
                    print(f"    - P95 Latency: {p95_lat:.2f}ms (Limit: {self.max_p95_latency_ms:.2f}ms)")
                
                self.trigger_rollback(router)
                return False

            print(f"  {CLR_GREEN}✔ Stage {stage_idx} Passed Automated Verification.{CLR_RESET}")

        print(f"\n{CLR_GREEN}{CLR_BOLD}★ DEPLOYMENT SUCCESSFUL: {target_artifact.version} Promoted to Full Production!{CLR_RESET}")
        return True

    def trigger_rollback(self, router: LoadBalancerRouter):
        """Immediately drains canary traffic and reverts cluster to stable baseline."""
        print(f"\n{CLR_YELLOW}{CLR_BOLD}>>> EXECUTING AUTOMATED FAST-ROLLBACK <<<{CLR_RESET}")
        router.set_canary_weight(0.0)
        print("1. Traffic split reset: CANARY -> 0%")
        print("2. Evicting Canary nodes from downstream service mesh...")
        router.canary_pool.clear()
        print("3. Rollback complete. Cluster restored to nominal baseline.")


def main():
    print(f"{CLR_BOLD}DevOps Hands-on: CD Pipeline & Automated Canary Analysis{CLR_RESET}")
    print("Standard Library Engine Initialized. Running Test Deployments...\n")

    pipeline = CanaryDeploymentOrchestrator(max_error_rate=0.06, max_p95_latency_ms=130.0)
    current_stable = ReleaseArtifact("v1.4.0", "9fa8c11", has_defect=False)

    # --- Scenario 1: Deploying a Healthy Patch (v1.4.1) ---
    healthy_candidate = ReleaseArtifact("v1.4.1", "a1e4d82", has_defect=False)
    res_healthy = pipeline.execute_deployment(current_stable, healthy_candidate)
    
    print("-" * 65)

    # --- Scenario 2: Deploying a Defective Patch (v1.5.0-rc) Triggering Rollback ---
    faulty_candidate = ReleaseArtifact("v1.5.0-rc", "f339bc0", has_defect=True)
    res_faulty = pipeline.execute_deployment(current_stable, faulty_candidate)

    print("\n" + "=" * 65)
    print(f"{CLR_BOLD}EXECUTION SUMMARY:{CLR_RESET}")
    print(f"Run 1 (Healthy Release v1.4.1)   : {'PROMOTED' if res_healthy else 'FAILED'}")
    print(f"Run 2 (Faulty Release v1.5.0-rc) : {'PROMOTED' if res_faulty else 'ROLLED BACK'}")
    print("=" * 65)

    if not res_faulty and res_healthy:
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()