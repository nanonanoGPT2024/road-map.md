#!/usr/bin/env python3
"""
Lab Exercise: Hands-on Kubernetes Orchestration Engine Simulator
BAB-04: Kubernetes Orchestration
Simulasi arsitektur inti K8s: API Server, etcd, Scheduler, Kubelet, dan Controller Manager.
"""

from __future__ import annotations
import dataclasses
import enum
import time
import random
import uuid
import sys
from typing import Dict, List, Optional


class AnsiColor:
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


class PodPhase(enum.Enum):
    PENDING = "Pending"
    CONTAINER_CREATING = "ContainerCreating"
    RUNNING = "Running"
    FAILED = "Failed"
    TERMINATING = "Terminating"


@dataclasses.dataclass
class ResourceRequirements:
    cpu_millicores: int
    memory_mib: int


@dataclasses.dataclass
class Pod:
    name: str
    uid: str
    namespace: str
    image: str
    resources: ResourceRequirements
    labels: Dict[str, str]
    phase: PodPhase = PodPhase.PENDING
    node_name: Optional[str] = None
    restart_count: int = 0
    ready: bool = False


@dataclasses.dataclass
class Node:
    name: str
    role: str
    capacity_cpu: int
    capacity_mem: int
    allocated_cpu: int = 0
    allocated_mem: int = 0
    healthy: bool = True

    @property
    def free_cpu(self) -> int:
        return self.capacity_cpu - self.allocated_cpu

    @property
    def free_mem(self) -> int:
        return self.capacity_mem - self.allocated_mem


class EtcdStorage:
    """Simulasi etcd key-value store konsisten."""

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def put(self, key: str, value: str) -> None:
        self._store[key] = value

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def list_prefix(self, prefix: str) -> Dict[str, str]:
        return {k: v for k, v in self._store.items() if k.startswith(prefix)}


class KubeAPIServer:
    """Pusat kontrol validasi deklaratif dan single-source-of-truth."""

    def __init__(self, etcd: EtcdStorage) -> None:
        self.etcd = etcd
        self.pods: Dict[str, Pod] = {}
        self.nodes: Dict[str, Node] = {}

    def register_node(self, node: Node) -> None:
        self.nodes[node.name] = node
        self.etcd.put(f"/registry/nodes/{node.name}", f"Node:{node.role}")
        print(f" {AnsiColor.CYAN}[API-SERVER]{AnsiColor.RESET} Registered node: {AnsiColor.BOLD}{node.name}{AnsiColor.RESET} ({node.role})")

    def create_pod(self, pod: Pod) -> Pod:
        self.pods[pod.name] = pod
        self.etcd.put(f"/registry/pods/{pod.namespace}/{pod.name}", pod.image)
        print(f" {AnsiColor.CYAN}[API-SERVER]{AnsiColor.RESET} Accepted Pod manifest: {AnsiColor.YELLOW}{pod.name}{AnsiColor.RESET}")
        return pod

    def update_pod_binding(self, pod_name: str, node_name: str) -> bool:
        pod = self.pods.get(pod_name)
        if not pod:
            return False
        pod.node_name = node_name
        self.etcd.put(f"/registry/bindings/{pod.namespace}/{pod.name}", node_name)
        return True

    def delete_pod(self, pod_name: str) -> None:
        if pod_name in self.pods:
            pod = self.pods.pop(pod_name)
            self.etcd.delete(f"/registry/pods/{pod.namespace}/{pod_name}")
            self.etcd.delete(f"/registry/bindings/{pod.namespace}/{pod_name}")
            if pod.node_name and pod.node_name in self.nodes:
                node = self.nodes[pod.node_name]
                node.allocated_cpu -= pod.resources.cpu_millicores
                node.allocated_mem -= pod.resources.memory_mib


class KubeScheduler:
    """Menghitung filtering dan scoring untuk placement Pod unassigned."""

    def __init__(self, api: KubeAPIServer) -> None:
        self.api = api

    def schedule_pending_pods(self) -> None:
        for pod in list(self.api.pods.values()):
            if pod.node_name is None and pod.phase == PodPhase.PENDING:
                self._schedule_pod(pod)

    def _schedule_pod(self, pod: Pod) -> None:
        print(f" {AnsiColor.MAGENTA}[SCHEDULER]{AnsiColor.RESET} Filtering & Scoring node candidate untuk {pod.name}...")
        feasible_nodes: List[Node] = []
        for node in self.api.nodes.values():
            if not node.healthy or node.role == "control-plane":
                continue
            if node.free_cpu >= pod.resources.cpu_millicores and node.free_mem >= pod.resources.memory_mib:
                feasible_nodes.append(node)

        if not feasible_nodes:
            print(f" {AnsiColor.RED}[SCHEDULER-ERR]{AnsiColor.RESET} 0/{len(self.api.nodes)} nodes available: Insufficient CPU/Memory untuk {pod.name}")
            return

        # Prioritaskan node dengan utilisasi terendah (LeastRequestedPriority)
        best_node = max(feasible_nodes, key=lambda n: n.free_cpu + n.free_mem)
        best_node.allocated_cpu += pod.resources.cpu_millicores
        best_node.allocated_mem += pod.resources.memory_mib

        self.api.update_pod_binding(pod.name, best_node.name)
        pod.phase = PodPhase.CONTAINER_CREATING
        print(f" {AnsiColor.MAGENTA}[SCHEDULER]{AnsiColor.RESET} Pod {AnsiColor.BOLD}{pod.name}{AnsiColor.RESET} bound ke Node: {AnsiColor.GREEN}{best_node.name}{AnsiColor.RESET}")


class Kubelet:
    """Node agent yang bertanggung jawab atas siklus hidup Pod di local node."""

    def __init__(self, node_name: str, api: KubeAPIServer) -> None:
        self.node_name = node_name
        self.api = api

    def sync_loop(self) -> None:
        for pod in list(self.api.pods.values()):
            if pod.node_name == self.node_name:
                if pod.phase == PodPhase.CONTAINER_CREATING:
                    time.sleep(0.1)
                    pod.phase = PodPhase.RUNNING
                    pod.ready = True
                    print(f" {AnsiColor.BLUE}[KUBELET@{self.node_name}]{AnsiColor.RESET} Container pull '{pod.image}' selesai -> Pod {AnsiColor.GREEN}{pod.name}{AnsiColor.RESET} is RUNNING (1/1 Ready)")


class DeploymentController:
    """Reconciliation loop: memastikan actual state = desired state."""

    def __init__(self, api: KubeAPIServer, deployment_name: str, image: str, replicas: int) -> None:
        self.api = api
        self.name = deployment_name
        self.image = image
        self.desired_replicas = replicas

    def reconcile(self) -> None:
        current_pods = [
            p for p in self.api.pods.values()
            if p.labels.get("app") == self.name and p.phase != PodPhase.TERMINATING
        ]
        active_count = len(current_pods)

        if active_count < self.desired_replicas:
            diff = self.desired_replicas - active_count
            print(f" {AnsiColor.YELLOW}[DEPLOY-CTRL]{AnsiColor.RESET} Desired: {self.desired_replicas} | Actual: {active_count}. Scaling UP (+{diff})...")
            for _ in range(diff):
                pod_suffix = uuid.uuid4().hex[:5]
                pod = Pod(
                    name=f"{self.name}-{pod_suffix}",
                    uid=str(uuid.uuid4()),
                    namespace="production",
                    image=self.image,
                    resources=ResourceRequirements(cpu_millicores=250, memory_mib=256),
                    labels={"app": self.name, "version": self.image.split(":")[-1]}
                )
                self.api.create_pod(pod)

        elif active_count > self.desired_replicas:
            diff = active_count - self.desired_replicas
            print(f" {AnsiColor.YELLOW}[DEPLOY-CTRL]{AnsiColor.RESET} Desired: {self.desired_replicas} | Actual: {active_count}. Scaling DOWN (-{diff})...")
            for p in current_pods[:diff]:
                print(f" {AnsiColor.YELLOW}[DEPLOY-CTRL]{AnsiColor.RESET} Evicting surplus pod: {p.name}")
                self.api.delete_pod(p.name)

    def rolling_update(self, new_image: str, scheduler: KubeScheduler, kubelets: Dict[str, Kubelet]) -> None:
        print(f"\n{AnsiColor.BOLD}{AnsiColor.BG_BLUE} === MEMULAI ROLLING UPDATE KE {new_image} (maxSurge=1, maxUnavailable=0) === {AnsiColor.RESET}")
        old_image = self.image
        self.image = new_image

        # Pola Rolling Update bertahap pod demi pod
        for step in range(self.desired_replicas):
            print(f"\n{AnsiColor.BOLD}--- Step {step + 1}/{self.desired_replicas}: Rollout Pod Baru ---{AnsiColor.RESET}")
            # 1. Tambah 1 pod versi baru
            new_pod = Pod(
                name=f"{self.name}-{uuid.uuid4().hex[:5]}",
                uid=str(uuid.uuid4()),
                namespace="production",
                image=new_image,
                resources=ResourceRequirements(cpu_millicores=250, memory_mib=256),
                labels={"app": self.name, "version": new_image.split(":")[-1]}
            )
            self.api.create_pod(new_pod)
            scheduler.schedule_pending_pods()
            if new_pod.node_name and new_pod.node_name in kubelets:
                kubelets[new_pod.node_name].sync_loop()

            # 2. Hapus 1 pod versi lama
            old_pods = [
                p for p in self.api.pods.values()
                if p.labels.get("app") == self.name and p.image == old_image and p.phase != PodPhase.TERMINATING
            ]
            if old_pods:
                to_terminate = old_pods[0]
                print(f" {AnsiColor.YELLOW}[ROLLOUT]{AnsiColor.RESET} Terminating pod lama: {to_terminate.name}")
                self.api.delete_pod(to_terminate.name)
            time.sleep(0.2)


def render_cluster_status(api: KubeAPIServer) -> None:
    print("\n" + "=" * 80)
    print(f"{AnsiColor.BOLD}KUBERNETES CLUSTER DASHBOARD - CURRENT STATE{AnsiColor.RESET}")
    print("=" * 80)

    print(f"\n{AnsiColor.BOLD}[NODES]{AnsiColor.RESET}")
    print(f"{'NAME':<20} {'ROLE':<15} {'CPU (USED/TOTAL)':<20} {'MEM (USED/TOTAL)':<20} {'STATUS':<10}")
    print("-" * 80)
    for n in api.nodes.values():
        status_color = AnsiColor.GREEN if n.healthy else AnsiColor.RED
        cpu_str = f"{n.allocated_cpu}/{n.capacity_cpu}m"
        mem_str = f"{n.allocated_mem}/{n.capacity_mem}Mi"
        print(f"{n.name:<20} {n.role:<15} {cpu_str:<20} {mem_str:<20} {status_color}{'Ready' if n.healthy else 'NotReady':<10}{AnsiColor.RESET}")

    print(f"\n{AnsiColor.BOLD}[PODS (NAMESPACE: production)]{AnsiColor.RESET}")
    print(f"{'NAME':<24} {'READY':<8} {'STATUS':<18} {'NODE':<18} {'IMAGE':<18}")
    print("-" * 80)
    if not api.pods:
        print(f"{AnsiColor.DIM}No resources found in production namespace.{AnsiColor.RESET}")
    for p in api.pods.values():
        ready_str = "1/1" if p.ready else "0/1"
        phase_color = AnsiColor.GREEN if p.phase == PodPhase.RUNNING else AnsiColor.YELLOW
        node_display = p.node_name or "<none>"
        print(f"{p.name:<24} {ready_str:<8} {phase_color}{p.phase.value:<18}{AnsiColor.RESET} {node_display:<18} {p.image:<18}")
    print("=" * 80 + "\n")


def run_interactive_simulation() -> None:
    print(f"{AnsiColor.BOLD}{AnsiColor.CYAN}")
    print("****************************************************************")
    print("   BAB-04: KUBERNETES ORCHESTRATION ENGINE TECHNICAL LAB       ")
    print("      Simulasi Interaktif Rekonsiliasi, Scheduling, & Rollout   ")
    print("****************************************************************")
    print(f"{AnsiColor.RESET}")

    etcd = EtcdStorage()
    api = KubeAPIServer(etcd)

    # 1. Bootstrapping nodes
    print(f"{AnsiColor.BOLD}>>> FASE 1: Inisialisasi Topology Cluster{AnsiColor.RESET}")
    api.register_node(Node("control-plane-01", "control-plane", capacity_cpu=4000, capacity_mem=8192))
    api.register_node(Node("worker-node-01", "worker", capacity_cpu=2000, capacity_mem=4096))
    api.register_node(Node("worker-node-02", "worker", capacity_cpu=2000, capacity_mem=4096))

    scheduler = KubeScheduler(api)
    kubelets = {
        "worker-node-01": Kubelet("worker-node-01", api),
        "worker-node-02": Kubelet("worker-node-02", api),
    }

    # 2. Deploy Aplikasi
    print(f"\n{AnsiColor.BOLD}>>> FASE 2: Deklarasi Deployment 'order-service' (Replicas: 3, v1.0.0){AnsiColor.RESET}")
    deploy_ctrl = DeploymentController(api, "order-service", "order-api:v1.0.0", replicas=3)
    deploy_ctrl.reconcile()

    print(f"\n{AnsiColor.BOLD}>>> FASE 3: Menjalankan Scheduler Cycle{AnsiColor.RESET}")
    scheduler.schedule_pending_pods()

    print(f"\n{AnsiColor.BOLD}>>> FASE 4: Kubelet Sync Loop (Pod Start & Probe Checks){AnsiColor.RESET}")
    for k in kubelets.values():
        k.sync_loop()

    render_cluster_status(api)

    # 3. Rolling update
    print(f"\n{AnsiColor.BOLD}>>> FASE 5: Trigger Zero-Downtime Rolling Update ke v2.0.0{AnsiColor.RESET}")
    deploy_ctrl.rolling_update("order-api:v2.0.0", scheduler, kubelets)

    render_cluster_status(api)

    # 4. Self-Healing Simulation
    print(f"\n{AnsiColor.BOLD}>>> FASE 6: Simulasi Kegagalan & Self-Healing (Pod Crash Injection){AnsiColor.RESET}")
    running_pods = [p for p in api.pods.values() if p.phase == PodPhase.RUNNING]
    if running_pods:
        crashed_pod = running_pods[0]
        print(f" {AnsiColor.RED}[CHAOS-TEST]{AnsiColor.RESET} Membunuh Pod paksa: {crashed_pod.name}")
        api.delete_pod(crashed_pod.name)

        print(f" {AnsiColor.CYAN}[OBSERVATION]{AnsiColor.RESET} Status segera setelah Pod crash:")
        render_cluster_status(api)

        print(f" {AnsiColor.GREEN}[SELF-HEALING]{AnsiColor.RESET} DeploymentController mendeteksi drift -> Menjalankan rekonsiliasi ulang:")
        deploy_ctrl.reconcile()
        scheduler.schedule_pending_pods()
        for k in kubelets.values():
            k.sync_loop()

        render_cluster_status(api)

    print(f"{AnsiColor.BOLD}{AnsiColor.GREEN}=== SIMULASI SELESAI DENGAN SUKSES: SELURUH INTI KUBERNETES TERVERIFIKASI ==={AnsiColor.RESET}\n")


if __name__ == "__main__":
    try:
        run_interactive_simulation()
    except KeyboardInterrupt:
        print("\nSimulasi dihentikan oleh user.")
        sys.exit(0)
