#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Kubernetes Scheduling Lanjutan & Autoscaling (BAB-09)
Modul: m01 - Advanced Scheduling, Taints/Tolerations, Affinity, & HPA Simulation
"""

import math
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class Taint:
    key: str
    value: str
    effect: str  # NoSchedule, PreferNoSchedule, NoExecute


@dataclass
class Toleration:
    key: str
    operator: str  # Equal, Exists
    value: str = ""
    effect: str = ""

    def matches(self, taint: Taint) -> bool:
        if self.operator == "Exists":
            return (not self.key or self.key == taint.key) and (
                not self.effect or self.effect == taint.effect
            )
        elif self.operator == "Equal":
            return (
                self.key == taint.key
                and self.value == taint.value
                and (not self.effect or self.effect == taint.effect)
            )
        return False


@dataclass
class Node:
    name: str
    zone: str
    labels: Dict[str, str] = field(default_factory=dict)
    taints: List[Taint] = field(default_factory=list)
    cpu_capacity: int = 4000  # in millicores
    cpu_used: int = 0
    assigned_pods: List[str] = field(default_factory=list)


@dataclass
class Pod:
    name: str
    labels: Dict[str, str] = field(default_factory=dict)
    tolerations: List[Toleration] = field(default_factory=list)
    node_selector: Dict[str, str] = field(default_factory=dict)
    cpu_request: int = 500  # millicores


def header(title: str):
    line = "=" * 70
    print(f"\n{CYAN}{BOLD}{line}")
    print(f" [*] {title}")
    print(f"{line}{RESET}")


def subheader(title: str):
    print(f"\n{YELLOW}{BOLD}--- {title} ---{RESET}")


def simulate_scheduler_filtering_and_scoring(nodes: List[Node], pod: Pod) -> Optional[Node]:
    header(f"SCHEDULER FILTERING & SCORING: Pod '{pod.name}'")
    print(f"{BLUE}Pod Spec:{RESET} CPU Request={pod.cpu_request}m, NodeSelector={pod.node_selector}")
    print(f"Tolerations: {[t.key + '=' + t.value + ':' + t.effect for t in pod.tolerations]}")

    filtered_nodes: List[Node] = []

    subheader("Phase 1: Filtering (Predicates)")
    for node in nodes:
        reasons_failed = []

        # 1. Capacity Check
        if node.cpu_used + pod.cpu_request > node.cpu_capacity:
            reasons_failed.append(f"Insufficient CPU ({node.cpu_capacity - node.cpu_used}m free)")

        # 2. NodeSelector Check
        for k, v in pod.node_selector.items():
            if node.labels.get(k) != v:
                reasons_failed.append(f"NodeSelector mismatch ({k}={v})")

        # 3. Taint / Toleration Check
        for taint in node.taints:
            if taint.effect in ("NoSchedule", "NoExecute"):
                tolerated = any(tol.matches(taint) for tol in pod.tolerations)
                if not tolerated:
                    reasons_failed.append(f"Untolerated taint ({taint.key}={taint.value}:{taint.effect})")

        if not reasons_failed:
            print(f"  {GREEN}[PASS]{RESET} Node {BOLD}{node.name}{RESET} lolos tahap filtering.")
            filtered_nodes.append(node)
        else:
            print(f"  {RED}[FAIL]{RESET} Node {BOLD}{node.name}{RESET} dieliminasi: {', '.join(reasons_failed)}")

    if not filtered_nodes:
        print(f"\n{RED}{BOLD}[!] Scheduling Failed: Pod '{pod.name}' berstatus Pending (0/{len(nodes)} nodes available).{RESET}")
        return None

    subheader("Phase 2: Scoring (Priorities)")
    scores: Dict[str, int] = {}
    for node in filtered_nodes:
        # Score berdasarkan LeastRequestedPriority (makin banyak CPU kosong, makin tinggi skor)
        free_cpu = node.cpu_capacity - (node.cpu_used + pod.cpu_request)
        score = int((free_cpu / node.cpu_capacity) * 100)

        # Bonus skor jika ada label affinity (preferensi zone)
        if node.labels.get("topology.kubernetes.io/zone") == "ap-southeast-1a":
            score += 10
            print(f"  Node {node.name}: Zone bonus (+10)")

        scores[node.name] = score
        print(f"  {CYAN}Node {node.name}{RESET} -> Score: {BOLD}{score}/100{RESET} (Free CPU: {free_cpu}m)")

    # Select node with highest score
    selected_node_name = max(scores, key=scores.get)
    selected_node = next(n for n in filtered_nodes if n.name == selected_node_name)

    selected_node.cpu_used += pod.cpu_request
    selected_node.assigned_pods.append(pod.name)

    print(f"\n{GREEN}{BOLD}[OK] Pod '{pod.name}' berhasil dijadwalkan ke: {selected_node.name}{RESET}")
    return selected_node


def simulate_topology_spread(nodes: List[Node], max_skew: int = 1):
    header("SIMULASI: Pod Topology Spread Constraints")
    print(f"Konfigurasi: topologyKey='topology.kubernetes.io/zone', maxSkew={max_skew}")

    # Hitung jumlah pod per zone
    zone_counts: Dict[str, int] = {}
    for node in nodes:
        zone = node.zone
        zone_counts[zone] = zone_counts.get(zone, 0) + len(node.assigned_pods)

    for zone, count in zone_counts.items():
        print(f"  Zone {MAGENTA}{zone}{RESET}: {BOLD}{count} pods{RESET}")

    counts = list(zone_counts.values())
    if not counts:
        print("Belum ada pod yang dijadwalkan.")
        return

    min_count = min(counts)
    max_count = max(counts)
    actual_skew = max_count - min_count

    print(f"\nSkew Analysis: Max Pods ({max_count}) - Min Pods ({min_count}) = {BOLD}{actual_skew}{RESET}")
    if actual_skew <= max_skew:
        print(f"{GREEN}{BOLD}[PASSED] Distribusi pod seimbang memenuhi constraint maxSkew <= {max_skew}.{RESET}")
    else:
        print(f"{RED}{BOLD}[VIOLATION] Skew ({actual_skew}) melebihi batas toleransi maxSkew ({max_skew})!{RESET}")


def simulate_hpa(current_replicas: int, target_cpu_util: int, current_metrics: List[int]):
    header("SIMULASI: Horizontal Pod Autoscaler (HPA) Algorithm")
    print("Formula K8s: desiredReplicas = ceil[ currentReplicas * ( currentMetricValue / desiredMetricValue ) ]")
    print(f"Target CPU Utilization: {target_cpu_util}%\n")

    replicas = current_replicas
    min_replicas = 2
    max_replicas = 10

    for step, metric_val in enumerate(current_metrics, start=1):
        ratio = metric_val / target_cpu_util
        # HPA tolerance check default K8s adalah 10% (0.1)
        if abs(1.0 - ratio) <= 0.10:
            calc_replicas = replicas
            status = f"{YELLOW}Within 10% tolerance (No scale change){RESET}"
        else:
            calc_replicas = math.ceil(replicas * ratio)
            calc_replicas = max(min_replicas, min(calc_replicas, max_replicas))
            if calc_replicas > replicas:
                status = f"{GREEN}[SCALE-UP] +{calc_replicas - replicas} Pods{RESET}"
            elif calc_replicas < replicas:
                status = f"{RED}[SCALE-DOWN] -{replicas - calc_replicas} Pods{RESET}"
            else:
                status = f"{BLUE}Maintained at limits{RESET}"

        print(f"T+{step*15}s | Avg CPU: {metric_val:>3}% (Ratio: {ratio:.2f}) -> Replicas: {replicas} => {BOLD}{calc_replicas}{RESET} | {status}")
        replicas = calc_replicas
        time.sleep(0.15)


def build_default_cluster() -> List[Node]:
    return [
        Node(
            name="node-prod-01",
            zone="ap-southeast-1a",
            labels={"topology.kubernetes.io/zone": "ap-southeast-1a", "node-role": "worker", "tier": "general"},
            taints=[],
            cpu_capacity=4000,
            cpu_used=1000
        ),
        Node(
            name="node-prod-02",
            zone="ap-southeast-1b",
            labels={"topology.kubernetes.io/zone": "ap-southeast-1b", "node-role": "worker", "tier": "general"},
            taints=[],
            cpu_capacity=4000,
            cpu_used=2800
        ),
        Node(
            name="node-gpu-dedicated",
            zone="ap-southeast-1a",
            labels={"topology.kubernetes.io/zone": "ap-southeast-1a", "node-role": "gpu", "tier": "specialized"},
            taints=[Taint(key="dedicated", value="gpu", effect="NoSchedule")],
            cpu_capacity=8000,
            cpu_used=500
        )
    ]


def run_full_demo():
    print(f"\n{BOLD}{CYAN}=== MEMULAI DEMO OTOMATIS: KUBERNETES ADVANCED SCHEDULING & AUTOSCALING ==={RESET}\n")
    nodes = build_default_cluster()

    # Skenario 1: Pod Biasa (Harus masuk node-prod-01 karena skor free CPU lebih tinggi dibanding node-prod-02)
    pod_web = Pod(
        name="frontend-web-1",
        labels={"app": "frontend"},
        node_selector={"node-role": "worker"},
        cpu_request=800
    )
    simulate_scheduler_filtering_and_scoring(nodes, pod_web)

    # Skenario 2: Pod GPU dengan Toleration (Harus bisa lolos ke node-gpu-dedicated)
    pod_ai = Pod(
        name="ai-inference-worker",
        labels={"app": "ai-worker"},
        tolerations=[Toleration(key="dedicated", operator="Equal", value="gpu", effect="NoSchedule")],
        node_selector={"node-role": "gpu"},
        cpu_request=2000
    )
    simulate_scheduler_filtering_and_scoring(nodes, pod_ai)

    # Skenario 3: Pod yang ditolak oleh Taint (Pending)
    pod_unprivileged = Pod(
        name="batch-worker-untrusted",
        labels={"app": "batch"},
        node_selector={"node-role": "gpu"},  # Ingin node GPU tapi tidak punya tolerasi
        cpu_request=500
    )
    simulate_scheduler_filtering_and_scoring(nodes, pod_unprivileged)

    # Skenario 4: Evaluasi Topology Spread
    simulate_topology_spread(nodes, max_skew=1)

    # Skenario 5: HPA Simulasi
    sample_metrics = [50, 68, 85, 92, 110, 75, 45, 25]
    simulate_hpa(current_replicas=2, target_cpu_util=60, current_metrics=sample_metrics)

    print(f"\n{GREEN}{BOLD}[DONE] Seluruh demonstrasi lab berhasil dieksekusi.{RESET}\n")


def interactive_menu():
    nodes = build_default_cluster()
    while True:
        header("INTERACTIVE LAB: KUBERNETES ADVANCED SCHEDULING")
        print("1. Jadwalkan Pod Standar (Worker Tier)")
        print("2. Jadwalkan AI/ML Pod (Dengan GPU Toleration)")
        print("3. Jadwalkan Pod Mismatch Taint (Simulasi Pod Pending)")
        print("4. Cek Status Node & Topology Spread Analysis")
        print("5. Jalankan Simulasi HPA Autoscaling Loop")
        print("6. Jalankan Demo Otomatis Komprehensif")
        print("0. Keluar")

        try:
            choice = input(f"\n{BOLD}Pilih opsi [0-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            p = Pod(name=f"web-{int(time.time())%1000}", node_selector={"node-role": "worker"}, cpu_request=600)
            simulate_scheduler_filtering_and_scoring(nodes, p)
        elif choice == "2":
            p = Pod(
                name=f"ai-task-{int(time.time())%1000}",
                tolerations=[Toleration(key="dedicated", operator="Equal", value="gpu", effect="NoSchedule")],
                node_selector={"node-role": "gpu"},
                cpu_request=1500
            )
            simulate_scheduler_filtering_and_scoring(nodes, p)
        elif choice == "3":
            p = Pod(name="unwanted-pod", node_selector={"node-role": "gpu"}, cpu_request=500)
            simulate_scheduler_filtering_and_scoring(nodes, p)
        elif choice == "4":
            header("CLUSTER NODE OVERVIEW")
            for n in nodes:
                print(f"Node: {BOLD}{n.name:<18}{RESET} Zone: {n.zone:<16} CPU: {n.cpu_used}/{n.cpu_capacity}m | Pods: {n.assigned_pods}")
            simulate_topology_spread(nodes, max_skew=1)
        elif choice == "5":
            simulate_hpa(current_replicas=3, target_cpu_util=50, current_metrics=[52, 75, 95, 120, 80, 40, 20])
        elif choice == "6":
            run_full_demo()
        elif choice == "0":
            print(f"{CYAN}Sampai jumpa! Lab selesai.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "--run", "-d"):
        run_full_demo()
    elif not sys.stdin.isatty():
        # Fallback untuk lingkungan headless/non-interactive test runner
        run_full_demo()
    else:
        interactive_menu()
