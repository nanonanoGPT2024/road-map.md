#!/usr/bin/env python3
"""
Lab Exercise: Advanced Resilient Kubernetes Production Architecture Simulation
Curriculum: BAB-07-Container-Orchestration-Resilient-Kubernetes (Modul 02 Hands-on)
Focus: Self-healing, HPA scaling, Pod Disruption Budgets, Rolling Updates, SLI/SLO & Error Budget.
"""

import sys
import time
import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

# ANSI Color Codes
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
    BG_DARK = "\033[40m"

class PodPhase(Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    CRASH_LOOP = "CrashLoopBackOff"
    TERMINATING = "Terminating"
    FAILED = "Failed"

@dataclass
class Pod:
    name: str
    version: str
    node: str
    phase: PodPhase = PodPhase.PENDING
    ready: bool = False
    restarts: int = 0
    cpu_usage_m: int = 100  # millicores
    mem_usage_mb: int = 128
    liveness_failures: int = 0
    readiness_failures: int = 0

@dataclass
class Node:
    name: str
    zone: str
    cordoned: bool = False
    ready: bool = True
    cpu_capacity_m: int = 4000
    mem_capacity_mb: int = 8192

class SREClusterSimulator:
    def __init__(self):
        self.nodes: Dict[str, Node] = {
            "worker-zone-a-01": Node(name="worker-zone-a-01", zone="ap-southeast-1a"),
            "worker-zone-b-01": Node(name="worker-zone-b-01", zone="ap-southeast-1b"),
            "worker-zone-c-01": Node(name="worker-zone-c-01", zone="ap-southeast-1c"),
        }
        self.app_version = "v1.24.0"
        self.desired_replicas = 3
        self.min_replicas = 3
        self.max_replicas = 10
        self.target_cpu_utilization = 75  # 75%
        self.cpu_request_m = 250
        self.max_surge = 1
        self.max_unavailable = 0
        self.min_available_pdb = 2

        self.pods: List[Pod] = []
        self._init_workload()

        # SRE Observability State
        self.total_requests = 100000
        self.failed_requests = 15
        self.slo_target = 0.999  # 99.9% Availability (Three 9s)
        self.error_budget_window_total = 100000 * (1 - self.slo_target)  # 100 errors allowed

    def _init_workload(self):
        self.pods.clear()
        node_keys = list(self.nodes.keys())
        for i in range(self.desired_replicas):
            node_name = node_keys[i % len(node_keys)]
            pod = Pod(
                name=f"payment-service-{self.app_version.replace('.', '')}-{random.randint(1000, 9999)}",
                version=self.app_version,
                node=node_name,
                phase=PodPhase.RUNNING,
                ready=True,
                cpu_usage_m=120,
            )
            self.pods.append(pod)

    def print_banner(self):
        print(f"{Color.CYAN}{Color.BOLD}{'=' * 78}")
        print("  SRE PRODUCTION PLATFORM: KUBERNETES RESILIENCE & CHAOS SIMULATOR")
        print(f"  Domain: BAB-07 Container Orchestration Resilient Architecture")
        print(f"{'=' * 78}{Color.RESET}\n")

    def print_cluster_status(self):
        print(f"\n{Color.BOLD}{Color.WHITE}--- [TOPOLOGY & NODE POOLS] ---{Color.RESET}")
        for n in self.nodes.values():
            status_str = f"{Color.GREEN}Ready{Color.RESET}" if n.ready else f"{Color.RED}NotReady{Color.RESET}"
            sched_str = f"{Color.YELLOW}[SchedulingDisabled]{Color.RESET}" if n.cordoned else f"{Color.CYAN}[Schedulable]{Color.RESET}"
            pods_on_node = sum(1 for p in self.pods if p.node == n.name and p.phase == PodPhase.RUNNING)
            print(f"  • Node: {Color.BOLD}{n.name:<18}{Color.RESET} Zone: {n.zone:<15} Status: {status_str} {sched_str} Pods: {pods_on_node}")

        print(f"\n{Color.BOLD}{Color.WHITE}--- [WORKLOAD: payment-service (Deployment)] ---{Color.RESET}")
        print(f"  Version: {Color.MAGENTA}{self.app_version}{Color.RESET} | Target Replicas: {self.desired_replicas} (Min: {self.min_replicas}, Max: {self.max_replicas})")
        print(f"  PDB minAvailable: {self.min_available_pdb} | MaxSurge: {self.max_surge} | MaxUnavailable: {self.max_unavailable}")
        
        print(f"\n  {'NAME':<36} {'VERSION':<10} {'STATUS':<20} {'READY':<8} {'NODE':<20} {'CPU(m)':<8}")
        print(f"  {'-' * 105}")
        for p in self.pods:
            color = Color.GREEN if p.phase == PodPhase.RUNNING and p.ready else (Color.YELLOW if p.phase == PodPhase.PENDING else Color.RED)
            ready_str = f"{Color.GREEN}True{Color.RESET}" if p.ready else f"{Color.RED}False{Color.RESET}"
            status_str = f"{color}{p.phase.value}{Color.RESET}"
            print(f"  {p.name:<36} {p.version:<10} {status_str:<29} {ready_str:<17} {p.node:<20} {p.cpu_usage_m:<8}")

        self.print_sli_metrics()

    def print_sli_metrics(self):
        availability = (self.total_requests - self.failed_requests) / self.total_requests
        budget_spent = self.failed_requests
        budget_remaining = max(0.0, self.error_budget_window_total - budget_spent)
        burn_rate = (self.failed_requests / self.error_budget_window_total) * 100

        print(f"\n{Color.BOLD}{Color.WHITE}--- [SRE OBSERVABILITY: SLI / SLO & ERROR BUDGET] ---{Color.RESET}")
        print(f"  Target SLO (Availability) : {Color.BOLD}{self.slo_target * 100:.2f}%{Color.RESET}")
        sli_color = Color.GREEN if availability >= self.slo_target else Color.RED
        print(f"  Current SLI               : {sli_color}{Color.BOLD}{availability * 100:.4f}%{Color.RESET}")
        print(f"  Error Budget Pool (Total) : {self.error_budget_window_total:.1f} errors per 100k requests")
        
        budget_color = Color.GREEN if budget_remaining > 20 else (Color.YELLOW if budget_remaining > 0 else Color.RED)
        print(f"  Error Budget Remaining    : {budget_color}{Color.BOLD}{budget_remaining:.1f} ({100 - burn_rate:.1f}% left){Color.RESET}")
        print(f"  Error Budget Burn Rate    : {Color.RED if burn_rate > 80 else Color.CYAN}{burn_rate:.1f}% consumed{Color.RESET}")

    def simulate_hpa_autoscale(self):
        print(f"\n{Color.YELLOW}{Color.BOLD}[SCALING EVENT] Simulating incoming flash-crowd traffic spike...{Color.RESET}")
        time.sleep(0.5)
        # Spike CPU across current pods
        for p in self.pods:
            if p.phase == PodPhase.RUNNING:
                p.cpu_usage_m = random.randint(350, 480)  # > 250m threshold (140-190% load)

        avg_cpu = sum(p.cpu_usage_m for p in self.pods) / len(self.pods)
        avg_utilization = (avg_cpu / self.cpu_request_m) * 100

        print(f"  Current avg CPU utilization: {Color.RED}{avg_utilization:.1f}%{Color.RESET} (Threshold: {self.target_cpu_utilization}%)")
        target_replicas = min(self.max_replicas, math.ceil(len(self.pods) * (avg_utilization / self.target_cpu_utilization)))
        
        print(f"  {Color.CYAN}HPA Controller Recommendation:{Color.RESET} Scale from {len(self.pods)} to {target_replicas} pods.")
        available_nodes = [n.name for n in self.nodes.values() if n.ready and not n.cordoned]

        if not available_nodes:
            print(f"  {Color.RED}Scale-up blocked! No schedulable nodes available.{Color.RESET}")
            return

        for i in range(len(self.pods), target_replicas):
            assigned_node = random.choice(available_nodes)
            new_pod = Pod(
                name=f"payment-service-{self.app_version.replace('.', '')}-{random.randint(1000, 9999)}",
                version=self.app_version,
                node=assigned_node,
                phase=PodPhase.RUNNING,
                ready=True,
                cpu_usage_m=110
            )
            self.pods.append(new_pod)
            print(f"  {Color.GREEN}✔ Scheduled pod {new_pod.name} -> {assigned_node}{Color.RESET}")

        self.desired_replicas = target_replicas
        # Normalize CPU after load distribution
        for p in self.pods:
            p.cpu_usage_m = int(avg_cpu * 3 / len(self.pods))
        print(f"{Color.GREEN}{Color.BOLD}[SUCCESS] Workload scaled successfully. Load normalized.{Color.RESET}")

    def simulate_rolling_update(self):
        new_version = "v1.25.0"
        print(f"\n{Color.CYAN}{Color.BOLD}[DEPLOYMENT] Starting zero-downtime rolling update ({self.app_version} -> {new_version})...{Color.RESET}")
        print(f"  Strategy: MaxSurge={self.max_surge}, MaxUnavailable={self.max_unavailable}")
        
        available_nodes = [n.name for n in self.nodes.values() if n.ready and not n.cordoned]
        old_pods = [p for p in self.pods if p.version == self.app_version]
        
        step = 1
        while old_pods:
            print(f"\n  --- Step {step}: Provisioning Surge Canary Pod ---")
            assigned_node = random.choice(available_nodes)
            canary_pod = Pod(
                name=f"payment-service-{new_version.replace('.', '')}-{random.randint(1000, 9999)}",
                version=new_version,
                node=assigned_node,
                phase=PodPhase.PENDING,
                ready=False
            )
            self.pods.append(canary_pod)
            print(f"  1. Created pod {canary_pod.name} (Pending)")
            time.sleep(0.4)

            # Probe checks
            print(f"  2. Executing Startup and Readiness probes...")
            canary_pod.phase = PodPhase.RUNNING
            canary_pod.ready = True
            print(f"     {Color.GREEN}Readiness probe passed (200 OK HTTP /healthz){Color.RESET}")

            # Decommission one old pod
            victim = old_pods.pop(0)
            print(f"  3. Terminating old revision pod {victim.name} (PreStop Hook + SIGTERM)...")
            victim.phase = PodPhase.TERMINATING
            victim.ready = False
            time.sleep(0.3)
            self.pods.remove(victim)
            print(f"     {Color.YELLOW}Old pod gracefully removed from Service Endpoints.{Color.RESET}")
            step += 1

        self.app_version = new_version
        print(f"\n{Color.GREEN}{Color.BOLD}[DEPLOYMENT COMPLETE] 100% traffic serving on {self.app_version} with zero dropped requests.{Color.RESET}")

    def simulate_chaos_node_drain(self):
        active_nodes = [n for n in self.nodes.values() if n.ready and not n.cordoned]
        if len(active_nodes) <= 1:
            print(f"{Color.RED}[BLOCKED] Cannot drain node: minimum survivable cluster topology reached!{Color.RESET}")
            return

        target_node = random.choice(active_nodes)
        print(f"\n{Color.MAGENTA}{Color.BOLD}[CHAOS / MAINTENANCE] Draining node: {target_node.name}...{Color.RESET}")
        
        # 1. Cordon
        target_node.cordoned = True
        print(f"  1. Cordoning node {target_node.name} (Marked Unschedulable)")

        # 2. Check PDB
        pods_to_evict = [p for p in self.pods if p.node == target_node.name]
        remaining_ready = sum(1 for p in self.pods if p.ready and p.node != target_node.name)
        
        print(f"  2. Validating PodDisruptionBudget (minAvailable={self.min_available_pdb})...")
        print(f"     Surviving Ready Pods: {remaining_ready}")
        
        if remaining_ready < self.min_available_pdb:
            print(f"     {Color.RED}Eviction rejected by APIServer! PDB violation would breach availability.{Color.RESET}")
            target_node.cordoned = False
            return

        print(f"     {Color.GREEN}PDB check passed. Proceeding with eviction.{Color.RESET}")
        surviving_nodes = [n.name for n in self.nodes.values() if n.name != target_node.name and n.ready and not n.cordoned]

        for p in pods_to_evict:
            dest_node = random.choice(surviving_nodes)
            print(f"  3. Evicting {p.name} -> Rescheduled to {dest_node}")
            p.node = dest_node
            p.phase = PodPhase.RUNNING
            p.ready = True

        print(f"{Color.GREEN}{Color.BOLD}[DRAIN SUCCESSFUL] Node {target_node.name} is safe for OS patching or retirement.{Color.RESET}")

    def simulate_pod_crash_and_probes(self):
        if not self.pods:
            return
        victim = random.choice(self.pods)
        print(f"\n{Color.RED}{Color.BOLD}[CHAOS INJECTION] Injecting memory leak & deadlock to pod {victim.name}...{Color.RESET}")
        
        victim.readiness_failures = 3
        victim.ready = False
        print(f"  1. Readiness Probe Failed: HTTP 500 internal state corrupted.")
        print(f"     {Color.YELLOW}Kube-proxy action: Pod removed from endpoints controller.{Color.RESET}")
        
        # SRE error budget impact
        synthetic_failed_reqs = random.randint(15, 35)
        self.failed_requests += synthetic_failed_reqs
        print(f"     {Color.RED}Transient errors leaked before cutoff: {synthetic_failed_reqs} requests failed.{Color.RESET}")
        
        victim.liveness_failures = 3
        print(f"  2. Liveness Probe Failed 3 consecutive times.")
        print(f"     {Color.RED}Kubelet action: Killing container via SIGKILL and restarting...{Color.RESET}")
        victim.restarts += 1
        victim.phase = PodPhase.RUNNING
        victim.ready = True
        victim.readiness_failures = 0
        victim.liveness_failures = 0
        print(f"  3. {Color.GREEN}Container restarted (RestartCount={victim.restarts}). Health probes recovered.{Color.RESET}")

    def interactive_menu(self):
        while True:
            self.print_banner()
            self.print_cluster_status()
            print(f"\n{Color.BOLD}SRE Control Operations:{Color.RESET}")
            print("  [1] Trigger Traffic Spike (Test HPA Horizontal Autoscaler)")
            print("  [2] Execute Zero-Downtime Rolling Update (MaxSurge / Canary)")
            print("  [3] Chaos Engineering: Drain Worker Node (PDB Guardrail)")
            print("  [4] Chaos Engineering: Inject Probe Failure / OOM (Self-Healing)")
            print("  [5] Recover / Uncordon All Nodes")
            print("  [6] Run Automated SRE Resilience Verification Suite")
            print("  [0] Exit Lab")
            
            try:
                choice = input(f"\n{Color.BOLD}{Color.CYAN}Select operation (0-6): {Color.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting SRE Lab...")
                break

            if choice == "1":
                self.simulate_hpa_autoscale()
            elif choice == "2":
                self.simulate_rolling_update()
            elif choice == "3":
                self.simulate_chaos_node_drain()
            elif choice == "4":
                self.simulate_pod_crash_and_probes()
            elif choice == "5":
                for n in self.nodes.values():
                    n.cordoned = False
                    n.ready = True
                print(f"{Color.GREEN}All nodes uncordoned and schedulable.{Color.RESET}")
            elif choice == "6":
                self.run_automated_verification()
            elif choice == "0":
                print(f"\n{Color.GREEN}SRE Lab Session closed cleanly.{Color.RESET}")
                break
            else:
                print(f"{Color.RED}Invalid option selected.{Color.RESET}")

            input(f"\n{Color.WHITE}Press [Enter] to continue...{Color.RESET}")

    def run_automated_verification(self):
        print(f"\n{Color.CYAN}{Color.BOLD}=== RUNNING AUTOMATED SRE RESILIENCE TEST SUITE ==={Color.RESET}")
        tests = [
            ("HPA Auto-scaling Test", self.simulate_hpa_autoscale),
            ("Zero-Downtime Rolling Update", self.simulate_rolling_update),
            ("PDB Guardrail on Node Drain", self.simulate_chaos_node_drain),
            ("Kubelet Probe Self-Healing", self.simulate_pod_crash_and_probes),
        ]
        
        passed = 0
        for name, test_fn in tests:
            print(f"\n{Color.BOLD}>> Executing: {name}...{Color.RESET}")
            try:
                test_fn()
                print(f"{Color.GREEN}✔ PASS: {name}{Color.RESET}")
                passed += 1
            except Exception as e:
                print(f"{Color.RED}✘ FAIL: {name} - Error: {e}{Color.RESET}")

        print(f"\n{Color.BOLD}Resilience Score: {passed}/{len(tests)} Tests Passed{Color.RESET}")
        availability = (self.total_requests - self.failed_requests) / self.total_requests
        if availability >= self.slo_target:
            print(f"{Color.GREEN}{Color.BOLD}SLO STATUS: HEALTHY ({availability * 100:.4f}% >= {self.slo_target * 100:.2f}%){Color.RESET}")
        else:
            print(f"{Color.RED}{Color.BOLD}SLO STATUS: BREACHED ({availability * 100:.4f}% < {self.slo_target * 100:.2f}%){Color.RESET}")

if __name__ == "__main__":
    simulator = SREClusterSimulator()
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        simulator.run_automated_verification()
    else:
        simulator.interactive_menu()
