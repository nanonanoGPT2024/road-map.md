#!/usr/bin/env python3
"""
Kubernetes Production Architecture & Orchestration Simulator
BAB-04: Kubernetes Orchestration Lab Exercise
Simulates Control Plane, Worker Nodes, Deployments, HPA, and Self-Healing.
"""

import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# ANSI Color Codes for Terminal UI
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

class PodPhase(Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    FAILED = "Failed"
    TERMINATING = "Terminating"

@dataclass
class Pod:
    name: str
    app_label: str
    node_name: Optional[str]
    phase: PodPhase = PodPhase.PENDING
    ready: bool = False
    restarts: int = 0
    cpu_usage_m: int = 100  # millicores
    version: str = "v1.0.0"

@dataclass
class Node:
    name: str
    role: str
    status: str = "Ready"
    capacity_cpu: int = 4000  # 4000m
    capacity_mem_mi: int = 8192  # 8 GiB
    pods: Dict[str, Pod] = field(default_factory=dict)

    @property
    def allocatable_cpu(self) -> int:
        used = sum(p.cpu_usage_m for p in self.pods.values() if p.phase == PodPhase.RUNNING)
        return max(0, self.capacity_cpu - used)

class KubernetesClusterSimulator:
    def __init__(self):
        self.nodes: Dict[str, Node] = {
            "k8s-control-plane-01": Node(name="k8s-control-plane-01", role="control-plane"),
            "k8s-worker-node-01": Node(name="k8s-worker-node-01", role="worker"),
            "k8s-worker-node-02": Node(name="k8s-worker-node-02", role="worker"),
            "k8s-worker-node-03": Node(name="k8s-worker-node-03", role="worker"),
        }
        self.deployment_name = "payment-gateway-api"
        self.desired_replicas = 3
        self.current_version = "v1.0.0"
        self.pods: Dict[str, Pod] = {}
        self.hpa_target_cpu = 70  # target 70% threshold
        self.init_cluster()

    def init_cluster(self):
        """Bootstrap default deployment across worker nodes."""
        for i in range(1, self.desired_replicas + 1):
            pod_name = f"{self.deployment_name}-7b9f8d6c-{i:03d}"
            pod = Pod(name=pod_name, app_label=self.deployment_name, node_name=None, version=self.current_version)
            self._schedule_and_start_pod(pod)

    def _get_worker_nodes(self) -> List[Node]:
        return [n for n in self.nodes.values() if n.role == "worker" and n.status == "Ready"]

    def _schedule_and_start_pod(self, pod: Pod):
        workers = self._get_worker_nodes()
        if not workers:
            pod.phase = PodPhase.PENDING
            self.pods[pod.name] = pod
            return

        # LeastAllocated priority scheduling algorithm
        target_node = max(workers, key=lambda n: n.allocatable_cpu)
        pod.node_name = target_node.name
        pod.phase = PodPhase.RUNNING
        pod.ready = True
        pod.cpu_usage_m = random.randint(120, 250)
        target_node.pods[pod.name] = pod
        self.pods[pod.name] = pod

    def print_banner(self):
        print(f"\n{Color.CYAN}{'='*75}{Color.RESET}")
        print(f"{Color.BOLD}{Color.WHITE}   KUBERNETES PRODUCTION CLUSTER SIMULATOR v1.31-PROD{Color.RESET}")
        print(f"{Color.BLUE}   Orchestration, Self-Healing, Scheduling & Autoscaling Hands-On Lab{Color.RESET}")
        print(f"{Color.CYAN}{'='*75}{Color.RESET}\n")

    def display_status(self):
        print(f"{Color.BOLD}[1] CLUSTER NODES (Control Plane & Data Plane):{Color.RESET}")
        print(f"{'-'*75}")
        print(f"{'NODE NAME':<24} {'ROLE':<14} {'STATUS':<10} {'PODS':<8} {'CPU FREE':<12}")
        print(f"{'-'*75}")
        for node in self.nodes.values():
            status_color = Color.GREEN if node.status == "Ready" else Color.RED
            free_cpu_str = f"{node.allocatable_cpu}m / {node.capacity_cpu}m"
            print(f"{node.name:<24} {node.role:<14} {status_color}{node.status:<10}{Color.RESET} {len(node.pods):<8} {free_cpu_str:<12}")

        print(f"\n{Color.BOLD}[2] DEPLOYMENT: {self.deployment_name} ({self.current_version}){Color.RESET}")
        print(f"{'-'*75}")
        print(f"{'POD NAME':<34} {'READY':<8} {'STATUS':<12} {'RESTARTS':<10} {'NODE':<20}")
        print(f"{'-'*75}")
        for pod in self.pods.values():
            phase_color = Color.GREEN if pod.phase == PodPhase.RUNNING else (Color.YELLOW if pod.phase == PodPhase.PENDING else Color.RED)
            ready_str = "1/1" if pod.ready else "0/1"
            print(f"{pod.name:<34} {ready_str:<8} {phase_color}{pod.phase.value:<12}{Color.RESET} {pod.restarts:<10} {pod.node_name or 'unassigned':<20}")
        print(f"{'-'*75}\n")

    def rolling_update(self, new_version: str):
        print(f"\n{Color.YELLOW}[*] Triggering RollingUpdate: {self.current_version} -> {new_version}...{Color.RESET}")
        old_pods = list(self.pods.values())
        self.current_version = new_version

        # Step 1: MaxSurge: Create new pod before removing old pod
        for i in range(len(old_pods)):
            new_pod_name = f"{self.deployment_name}-8c0e1a2b-{i+1:03d}"
            print(f"{Color.CYAN}  -> [DeploymentController] Creating new ReplicaSet Pod: {new_pod_name} ({new_version}){Color.RESET}")
            new_pod = Pod(name=new_pod_name, app_label=self.deployment_name, node_name=None, version=new_version)
            self._schedule_and_start_pod(new_pod)
            time.sleep(0.5)

            # Step 2: Readiness probe passes, drain old pod
            old_pod = old_pods[i]
            print(f"{Color.MAGENTA}  -> [EndpointController] Removing old Pod {old_pod.name} from Service endpoints{Color.RESET}")
            if old_pod.node_name and old_pod.node_name in self.nodes:
                self.nodes[old_pod.node_name].pods.pop(old_pod.name, None)
            self.pods.pop(old_pod.name, None)
            time.sleep(0.3)

        print(f"{Color.GREEN}[✓] Rolling update complete! Zero-downtime achieved for {self.deployment_name}.{Color.RESET}\n")

    def simulate_traffic_and_hpa(self):
        print(f"\n{Color.YELLOW}[*] Injecting massive HTTP traffic spike (15,000 req/sec)...{Color.RESET}")
        avg_cpu = 0
        for pod in self.pods.values():
            if pod.phase == PodPhase.RUNNING:
                pod.cpu_usage_m = random.randint(750, 950)
                avg_cpu += pod.cpu_usage_m

        running_count = sum(1 for p in self.pods.values() if p.phase == PodPhase.RUNNING)
        avg_pct = int((avg_cpu / (running_count * 1000)) * 100) if running_count else 0
        print(f"{Color.RED}  [Metrics-Server] CPU utilization reached: {avg_pct}% (Threshold: {self.hpa_target_cpu}%){Color.RESET}")
        print(f"{Color.CYAN}  [HPA Controller] Scaling recommendation: DesiredReplicas = ceil({running_count} * ({avg_pct} / {self.hpa_target_cpu})) = 6{Color.RESET}")

        target_replicas = 6
        for i in range(len(self.pods) + 1, target_replicas + 1):
            new_name = f"{self.deployment_name}-scale-{i:03d}"
            pod = Pod(name=new_name, app_label=self.deployment_name, node_name=None, version=self.current_version)
            self._schedule_and_start_pod(pod)
            print(f"{Color.GREEN}  -> Pod {new_name} scheduled to {pod.node_name} and marked READY{Color.RESET}")
            time.sleep(0.4)

        self.desired_replicas = target_replicas
        print(f"{Color.GREEN}[✓] Horizontal Pod Autoscaler successfully scaled deployment to {self.desired_replicas} replicas!{Color.RESET}\n")

    def simulate_node_failure_and_eviction(self):
        worker = "k8s-worker-node-02"
        print(f"\n{Color.RED}[!] Simulating hardware kernel panic / network split on {worker}...{Color.RESET}")
        node = self.nodes[worker]
        node.status = "NotReady"
        affected_pods = list(node.pods.values())
        print(f"{Color.RED}  [NodeLifecycleController] Node {worker} missed heartbeats. Transitioned to NotReady.{Color.RESET}")
        print(f"{Color.YELLOW}  [PodEviction] Taint: node.kubernetes.io/unreachable applied. Evicting {len(affected_pods)} pods...{Color.RESET}")
        time.sleep(0.8)

        # Clear pods from failed node and reschedule
        node.pods.clear()
        for pod in affected_pods:
            print(f"{Color.CYAN}  -> Rescheduling evicted pod {pod.name} to healthy surviving workers...{Color.RESET}")
            self.pods.pop(pod.name, None)
            new_rescheduled_pod = Pod(name=f"{pod.name}-r", app_label=pod.app_label, node_name=None, version=pod.version)
            self._schedule_and_start_pod(new_rescheduled_pod)
            time.sleep(0.4)

        print(f"{Color.GREEN}[✓] Rescheduling complete. High Availability maintained across healthy nodes.{Color.RESET}\n")

    def simulate_liveness_probe_healing(self):
        print(f"\n{Color.YELLOW}[*] Inducing memory leak deadlock into random Pod container...{Color.RESET}")
        running_pods = [p for p in self.pods.values() if p.phase == PodPhase.RUNNING]
        if not running_pods:
            print(f"{Color.RED}No running pods available.{Color.RESET}")
            return

        victim = random.choice(running_pods)
        print(f"{Color.RED}  [ContainerRuntime] Pod {victim.name}: HTTP GET /healthz timeout (504 Gateway Timeout){Color.RESET}")
        victim.ready = False
        time.sleep(0.5)
        print(f"{Color.YELLOW}  [Kubelet] Liveness probe failed 3 consecutive times. Killing container.{Color.RESET}")
        time.sleep(0.5)
        victim.restarts += 1
        victim.ready = True
        victim.cpu_usage_m = 150
        print(f"{Color.GREEN}  [Kubelet] Container restarted successfully. Restart count: {victim.restarts}. Health: 200 OK.{Color.RESET}\n")

def main():
    cluster = KubernetesClusterSimulator()
    cluster.print_banner()

    while True:
        print(f"{Color.BOLD}--- Interactive Production Scenarios ---{Color.RESET}")
        print(f"1. View Cluster Architecture Topology & Pod Metrics")
        print(f"2. Execute Rolling Update Deployment (v1.0.0 -> v1.1.0-prod)")
        print(f"3. Trigger Traffic Spike & HPA Autoscaling Simulation")
        print(f"4. Chaos Engineering: Worker Node Outage & Pod Eviction")
        print(f"5. Trigger Deadlock & Test Kubelet Liveness Self-Healing")
        print(f"6. Exit Simulator")
        
        try:
            choice = input(f"\n{Color.BOLD}{Color.CYAN}Select scenario [1-6]: {Color.RESET}").strip()
            if choice == "1":
                cluster.display_status()
            elif choice == "2":
                cluster.rolling_update("v1.1.0-prod")
                cluster.display_status()
            elif choice == "3":
                cluster.simulate_traffic_and_hpa()
                cluster.display_status()
            elif choice == "4":
                cluster.simulate_node_failure_and_eviction()
                cluster.display_status()
            elif choice == "5":
                cluster.simulate_liveness_probe_healing()
                cluster.display_status()
            elif choice == "6" or choice.lower() in ("exit", "quit"):
                print(f"{Color.GREEN}Exiting Kubernetes Simulator. Keep on orchestrating!{Color.RESET}")
                sys.exit(0)
            else:
                print(f"{Color.RED}Invalid selection. Please choose options 1-6.{Color.RESET}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Simulation interrupted by user. Exiting.{Color.RESET}")
            break

if __name__ == "__main__":
    main()
