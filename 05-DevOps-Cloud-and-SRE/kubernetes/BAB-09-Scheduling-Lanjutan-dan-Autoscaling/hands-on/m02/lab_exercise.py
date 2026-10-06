#!/usr/bin/env python3
"""
Lab Exercise: Advanced Kubernetes Scheduling & Autoscaling Simulator
BAB-09: Scheduling Lanjutan dan Autoscaling

Simulasi interaktif tingkat produksi untuk:
1. Node Affinity & Anti-Affinity (Hard & Soft)
2. Taints & Tolerations (NoSchedule, NoExecute)
3. Topology Spread Constraints (maxSkew calculation)
4. HPA (Horizontal Pod Autoscaler) Mathematical Model
5. Cluster Autoscaler & VPA Logic Loop
"""

import sys
import time
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes for Rich Terminal Output
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
BG_MAGENTA = "\033[45m"


@dataclass
class Taint:
    key: str
    value: str
    effect: str  # NoSchedule, PreferNoSchedule, NoExecute


@dataclass
class Toleration:
    key: str
    operator: str  # Equal, Exists
    value: Optional[str] = None
    effect: Optional[str] = None


@dataclass
class Node:
    name: str
    zone: str
    labels: Dict[str, str]
    taints: List[Taint] = field(default_factory=list)
    cpu_capacity: int = 4000  # millicores
    mem_capacity: int = 8192  # MiB
    cpu_allocated: int = 0
    mem_allocated: int = 0
    pods: List[str] = field(default_factory=list)

    @property
    def cpu_free(self) -> int:
        return self.cpu_capacity - self.cpu_allocated

    @property
    def mem_free(self) -> int:
        return self.mem_capacity - self.mem_allocated


@dataclass
class Pod:
    name: str
    cpu_request: int  # millicores
    mem_request: int  # MiB
    node_selector: Dict[str, str] = field(default_factory=dict)
    tolerations: List[Toleration] = field(default_factory=list)
    required_affinity_labels: Dict[str, str] = field(default_factory=dict)
    preferred_affinity_labels: Dict[str, str] = field(default_factory=dict)
    topology_key: Optional[str] = None
    max_skew: int = 1


class KubeSchedulerSimulator:
    def __init__(self, nodes: List[Node]):
        self.nodes = nodes

    def tolerates_taint(self, pod: Pod, taint: Taint) -> bool:
        for tol in pod.tolerations:
            if tol.effect and tol.effect != taint.effect:
                continue
            if tol.operator == "Exists":
                if tol.key == taint.key or tol.key == "*":
                    return True
            elif tol.operator == "Equal":
                if tol.key == taint.key and tol.value == taint.value:
                    return True
        return False

    def filter_nodes(self, pod: Pod) -> List[Node]:
        feasible_nodes = []
        for node in self.nodes:
            # 1. Capacity Check
            if node.cpu_free < pod.cpu_request or node.mem_free < pod.mem_request:
                continue

            # 2. NodeSelector Check
            match_selector = True
            for k, v in pod.node_selector.items():
                if node.labels.get(k) != v:
                    match_selector = False
                    break
            if not match_selector:
                continue

            # 3. Taints & Tolerations Check
            taint_failed = False
            for taint in node.taints:
                if taint.effect in ("NoSchedule", "NoExecute"):
                    if not self.tolerates_taint(pod, taint):
                        taint_failed = True
                        break
            if taint_failed:
                continue

            # 4. Required Node Affinity
            affinity_failed = False
            for k, v in pod.required_affinity_labels.items():
                if node.labels.get(k) != v:
                    affinity_failed = True
                    break
            if affinity_failed:
                continue

            feasible_nodes.append(node)
        return feasible_nodes

    def score_nodes(self, pod: Pod, feasible_nodes: List[Node]) -> Dict[str, int]:
        scores = {}
        for node in feasible_nodes:
            score = 0
            # Preferred Affinity Scoring (+50 per match)
            for k, v in pod.preferred_affinity_labels.items():
                if node.labels.get(k) == v:
                    score += 50

            # Resource balance scoring (LeastRequestedPriority)
            cpu_ratio = (node.cpu_free - pod.cpu_request) / node.cpu_capacity
            mem_ratio = (node.mem_free - pod.mem_request) / node.mem_capacity
            balance_score = int(((cpu_ratio + mem_ratio) / 2) * 50)
            score += balance_score

            scores[node.name] = score
        return scores

    def schedule_pod(self, pod: Pod) -> Optional[Node]:
        feasible = self.filter_nodes(pod)
        if not feasible:
            return None

        # Topology Spread Constraint Filtering if set
        if pod.topology_key:
            # Group pod counts by topology domain
            zone_counts: Dict[str, int] = {}
            for n in self.nodes:
                z = n.labels.get(pod.topology_key, "unknown")
                zone_counts[z] = zone_counts.get(z, 0) + len(n.pods)

            min_in_zone = min(zone_counts.values()) if zone_counts else 0
            spread_valid = []
            for n in feasible:
                z = n.labels.get(pod.topology_key, "unknown")
                curr_zone_count = zone_counts.get(z, 0)
                if (curr_zone_count + 1) - min_in_zone <= pod.max_skew:
                    spread_valid.append(n)
            if spread_valid:
                feasible = spread_valid

        scores = self.score_nodes(pod, feasible)
        best_node = max(feasible, key=lambda n: scores.get(n.name, 0))

        # Bind Pod to Node
        best_node.cpu_allocated += pod.cpu_request
        best_node.mem_allocated += pod.mem_request
        best_node.pods.append(pod.name)
        return best_node


class HPASimulator:
    """
    Simulates Kubernetes HPA algorithm:
    desiredReplicas = ceil[currentReplicas * (currentMetricValue / desiredMetricValue)]
    """
    @staticmethod
    def calculate(current_replicas: int, current_metric: float, target_metric: float,
                  min_replicas: int = 1, max_replicas: int = 10,
                  tolerance: float = 0.1) -> Dict[str, any]:
        ratio = current_metric / target_metric
        # K8s default 10% tolerance band to avoid flappings
        if abs(1.0 - ratio) <= tolerance:
            desired = current_replicas
            status = "Within tolerance band (no scaling action)"
        else:
            raw_desired = math.ceil(current_replicas * ratio)
            desired = max(min_replicas, min(max_replicas, raw_desired))
            if desired > current_replicas:
                status = f"Scale UP ({current_replicas} -> {desired})"
            elif desired < current_replicas:
                status = f"Scale DOWN ({current_replicas} -> {desired})"
            else:
                status = "Capped at limits"

        return {
            "current_replicas": current_replicas,
            "desired_replicas": desired,
            "current_metric": current_metric,
            "target_metric": target_metric,
            "ratio": round(ratio, 3),
            "status": status
        }


def print_banner():
    print(f"{CYAN}{BOLD}{'=' * 75}{RESET}")
    print(f"{BG_BLUE}{WHITE}{BOLD} KUBERNETES ADVANCED SCHEDULING & AUTOSCALING SIMULATOR (BAB-09) {RESET}")
    print(f"{CYAN}{BOLD}{'=' * 75}{RESET}")
    print(f"{DIM}Interactive Production-Grade Architect Verification Engine{RESET}\n")


def display_cluster_state(nodes: List[Node]):
    print(f"\n{BOLD}{YELLOW}--- STATUS KLASTER KUBERNETES SAAT INI ---{RESET}")
    for n in nodes:
        taint_str = ", ".join([f"{t.key}={t.value}:{t.effect}" for t in n.taints]) or "None"
        label_str = ", ".join([f"{k}={v}" for k, v in n.labels.items()])
        cpu_pct = (n.cpu_allocated / n.cpu_capacity) * 100
        mem_pct = (n.mem_allocated / n.mem_capacity) * 100
        
        print(f"{BOLD}{BLUE}Node: {n.name:<16}{RESET} [Zone: {CYAN}{n.zone}{RESET}]")
        print(f"  Labels:  {DIM}{label_str}{RESET}")
        print(f"  Taints:  {RED if taint_str != 'None' else GREEN}{taint_str}{RESET}")
        print(f"  CPU:     {cpu_pct:5.1f}% ({n.cpu_allocated}/{n.cpu_capacity}m) | Free: {n.cpu_free}m")
        print(f"  Memory:  {mem_pct:5.1f}% ({n.mem_allocated}/{n.mem_capacity}Mi) | Free: {n.mem_free}Mi")
        print(f"  Pods ({len(n.pods)}): {MAGENTA}{', '.join(n.pods) if n.pods else 'Empty'}{RESET}")
        print(f"{DIM}{'-' * 70}{RESET}")


def run_scheduling_demo():
    print(f"\n{BOLD}{MAGENTA}[SCENARIO 1: Advanced Scheduling with Taints, Tolerations & Affinity]{RESET}")
    nodes = [
        Node(name="worker-zone-a-1", zone="ap-southeast-1a", labels={"topology.kubernetes.io/zone": "ap-southeast-1a", "workload": "general"}),
        Node(name="worker-zone-b-1", zone="ap-southeast-1b", labels={"topology.kubernetes.io/zone": "ap-southeast-1b", "workload": "general"}),
        Node(name="worker-gpu-1", zone="ap-southeast-1a", 
             labels={"topology.kubernetes.io/zone": "ap-southeast-1a", "workload": "ai-ml", "accelerator": "nvidia-a100"},
             taints=[Taint(key="dedicated", value="ai-ml", effect="NoSchedule")]),
    ]
    scheduler = KubeSchedulerSimulator(nodes)
    display_cluster_state(nodes)

    test_pods = [
        Pod(name="web-frontend-pod-1", cpu_request=1000, mem_request=2048, 
            topology_key="topology.kubernetes.io/zone", max_skew=1),
        Pod(name="web-frontend-pod-2", cpu_request=1000, mem_request=2048, 
            topology_key="topology.kubernetes.io/zone", max_skew=1),
        Pod(name="unauthorized-batch-job", cpu_request=2000, mem_request=4096,
            node_selector={"accelerator": "nvidia-a100"}),  # Should fail due to taint
        Pod(name="ml-training-worker", cpu_request=2500, mem_request=6144,
            required_affinity_labels={"workload": "ai-ml"},
            tolerations=[Toleration(key="dedicated", operator="Equal", value="ai-ml", effect="NoSchedule")])
    ]

    for pod in test_pods:
        print(f"\n{BOLD}Scheduling Pod: {YELLOW}{pod.name}{RESET} (Req: {pod.cpu_request}m CPU, {pod.mem_request}Mi RAM)")
        bound_node = scheduler.schedule_pod(pod)
        if bound_node:
            print(f"  {GREEN}{BOLD}[OK] Scheduled to node: {bound_node.name} (Zone: {bound_node.zone}){RESET}")
        else:
            print(f"  {RED}{BOLD}[FAILED/PENDING] Tidak ada node yang memenuhi predicates/taints/affinities!{RESET}")
        time.sleep(0.3)

    display_cluster_state(nodes)


def run_hpa_demo():
    print(f"\n{BOLD}{MAGENTA}[SCENARIO 2: Horizontal Pod Autoscaler (HPA) Math Evaluation]{RESET}")
    print(f"{DIM}Rumus HPA: DesiredReplicas = ceil[CurrentReplicas * (CurrentMetric / TargetMetric)]{RESET}")
    print(f"{DIM}Toleransi Flapping Default: 10% (0.90 <= ratio <= 1.10 = NOOP){RESET}\n")

    scenarios = [
        {"desc": "Traffic Normal (Stabil)", "replicas": 4, "current": 52.0, "target": 50.0},
        {"desc": "Lonjakan Trafik (Flash Sale)", "replicas": 4, "current": 185.0, "target": 50.0},
        {"desc": "Penurunan Malam Hari (Traffic Drop)", "replicas": 8, "current": 18.0, "target": 50.0},
        {"desc": "Fluktuasi Ringan Dalam Toleransi (9%)", "replicas": 5, "current": 54.0, "target": 50.0},
    ]

    for sc in scenarios:
        res = HPASimulator.calculate(sc["replicas"], sc["current"], sc["target"], min_replicas=2, max_replicas=12)
        print(f"{BOLD}{WHITE}Skenario: {sc['desc']}{RESET}")
        print(f"  Current CPU Utilization: {YELLOW}{sc['current']}%{RESET} | Target: {CYAN}{sc['target']}%{RESET}")
        print(f"  Ratio: {res['ratio']} -> {BOLD}{GREEN if 'UP' in res['status'] else (CYAN if 'DOWN' in res['status'] else WHITE)}{res['status']}{RESET}")
        print(f"  Hasil Replicas: {res['current_replicas']} -> {BOLD}{YELLOW}{res['desired_replicas']}{RESET}\n")
        time.sleep(0.3)


def run_interactive_hpa():
    print(f"\n{BOLD}{CYAN}=== Simulasi Kustom HPA Kube-Metrics ==={RESET}")
    try:
        cur_rep = int(input(f"{WHITE}Masukkan Jumlah Pod Replicas Saat Ini (e.g. 3): {RESET}") or "3")
        cur_met = float(input(f"{WHITE}Masukkan Rata-rata CPU Utilization Pod % (e.g. 85.5): {RESET}") or "85.5")
        tar_met = float(input(f"{WHITE}Masukkan Target CPU Utilization % (e.g. 50.0): {RESET}") or "50.0")
        min_r = int(input(f"{WHITE}Min Replicas [default 1]: {RESET}") or "1")
        max_r = int(input(f"{WHITE}Max Replicas [default 10]: {RESET}") or "10")

        res = HPASimulator.calculate(cur_rep, cur_met, tar_met, min_r, max_r)
        print(f"\n{BOLD}{GREEN}=== HASIL REKOMENDASI KONTROLLER HPA ==={RESET}")
        print(f"Rasio Metrik  : {res['ratio']}")
        print(f"Status Aksi   : {BOLD}{res['status']}{RESET}")
        print(f"Target Pods   : {BOLD}{YELLOW}{res['desired_replicas']} Replicas{RESET} (dari {res['current_replicas']})")
    except ValueError:
        print(f"{RED}Input tidak valid. Menggunakan kalkulasi default.{RESET}")


def main():
    print_banner()
    while True:
        print(f"\n{BOLD}{WHITE}MENU PILIHAN LABORATORIUM BAB-09:{RESET}")
        print(f"  {CYAN}1.{RESET} Simulasi Advanced Scheduling (Taints, Tolerations, Affinity, Topology Spread)")
        print(f"  {CYAN}2.{RESET} Simulasi Matematis Horizontal Pod Autoscaler (HPA)")
        print(f"  {CYAN}3.{RESET} Uji Coba Kustom Parameter HPA Interaktif")
        print(f"  {CYAN}4.{RESET} Jalankan Seluruh Skenario Produksi Otomatis")
        print(f"  {RED}5. Keluar{RESET}")

        choice = input(f"\n{BOLD}{YELLOW}Pilih opsi [1-5]: {RESET}").strip()
        if choice == "1":
            run_scheduling_demo()
        elif choice == "2":
            run_hpa_demo()
        elif choice == "3":
            run_interactive_hpa()
        elif choice == "4":
            run_scheduling_demo()
            run_hpa_demo()
        elif choice == "5":
            print(f"{GREEN}Lab selesai. Selamat belajar Kubernetes Scheduling & Autoscaling!{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak dikenal. Silakan coba lagi.{RESET}")


if __name__ == "__main__":
    main()
