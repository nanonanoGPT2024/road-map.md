#!/usr/bin/env python3
"""
Kubernetes Control Plane Internal Architecture Simulation Lab
BAB-01: Arsitektur Internal dan Control Plane

Simulasi interaktif siklus hidup request Kubernetes:
1. kube-apiserver: Authentication, Authorization (RBAC), Admission Control
2. etcd: Raft KV Store dengan revisioning & watch events
3. kube-scheduler: Filtering (Predicates) & Scoring (Priorities)
4. kube-controller-manager: Reconciliation Loop (Desired vs Actual State)
5. kubelet: Node Pod Lifecycle & Heartbeats
"""

import sys
import time
import json
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# ANSI Color Codes for Terminal Output
class Color:
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
    BG_GREEN = "\033[42m"

def banner(title: str) -> None:
    line = "=" * 70
    print(f"\n{Color.CYAN}{line}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}{title.center(70)}{Color.RESET}")
    print(f"{Color.CYAN}{line}{Color.RESET}\n")

def log_component(component: str, color: str, message: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{Color.DIM}{timestamp}{Color.RESET}] {color}{Color.BOLD}[{component:^16}]{Color.RESET} {message}")

@dataclass
class ResourceRequirements:
    cpu_cores: float
    memory_mb: int

@dataclass
class PodSpec:
    name: str
    namespace: str
    image: str
    resources: ResourceRequirements
    node_name: Optional[str] = None
    status: str = "Pending"
    uid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

@dataclass
class Node:
    name: str
    total_cpu: float
    total_memory_mb: int
    used_cpu: float = 0.0
    used_memory_mb: int = 0
    ready: bool = True

    def fits(self, req: ResourceRequirements) -> bool:
        return (self.ready and 
                (self.total_cpu - self.used_cpu) >= req.cpu_cores and 
                (self.total_memory_mb - self.used_memory_mb) >= req.memory_mb)

    def allocate(self, req: ResourceRequirements) -> None:
        self.used_cpu += req.cpu_cores
        self.used_memory_mb += req.memory_mb

    def release(self, req: ResourceRequirements) -> None:
        self.used_cpu = max(0.0, self.used_cpu - req.cpu_cores)
        self.used_memory_mb = max(0, self.used_memory_mb - req.memory_mb)

class EtcdStore:
    """Simulasi etcd v3 (Distributed Key-Value Store dengan revisioning & watch)"""
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._revision: int = 1
        self._watchers: List[Any] = []

    def put(self, key: str, value: Any) -> int:
        self._revision += 1
        self._store[key] = value
        log_component("etcd", Color.MAGENTA, 
                      f"Raft Consensus Log Commit: key='{key}' (rev={self._revision})")
        return self._revision

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def list_prefix(self, prefix: str) -> Dict[str, Any]:
        return {k: v for k, v in self._store.items() if k.startswith(prefix)}

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            self._revision += 1
            log_component("etcd", Color.MAGENTA, 
                          f"Key Deleted: '{key}' (rev={self._revision})")
            return True
        return False

class KubeAPIServer:
    """Simulasi kube-apiserver: Gatekeeper & satu-satunya pintu ke etcd"""
    def __init__(self, etcd: EtcdStore):
        self.etcd = etcd

    def authenticate(self, token: str) -> str:
        if token == "admin-token-cluster":
            return "system:admin"
        if token == "kubelet-token-node01":
            return "system:node:worker-01"
        return "system:anonymous"

    def authorize(self, user: str, verb: str, resource: str) -> bool:
        if user == "system:admin":
            return True
        if user.startswith("system:node") and verb in ["get", "update", "patch"]:
            return True
        return False

    def admission_control_mutating(self, pod: PodSpec) -> None:
        # Defaulting namespace jika kosong
        if not pod.namespace:
            pod.namespace = "default"
            log_component("kube-apiserver", Color.BLUE, 
                          f"MutatingWebhook: set default namespace for Pod '{pod.name}'")

    def admission_control_validating(self, pod: PodSpec) -> bool:
        # Validasi batas resource minimal
        if pod.resources.cpu_cores <= 0 or pod.resources.memory_mb <= 0:
            log_component("kube-apiserver", Color.RED, 
                          f"ValidatingWebhook REJECTED: invalid resource requests for '{pod.name}'")
            return False
        log_component("kube-apiserver", Color.BLUE, 
                      f"ValidatingWebhook PASSED for Pod '{pod.name}'")
        return True

    def create_pod(self, token: str, pod: PodSpec) -> Optional[PodSpec]:
        log_component("kube-apiserver", Color.BLUE, 
                      f"Incoming HTTP POST /api/v1/namespaces/{pod.namespace}/pods")
        
        # 1. AuthN
        user = self.authenticate(token)
        log_component("kube-apiserver", Color.BLUE, f"AuthN: Authenticated as '{user}'")
        
        # 2. AuthZ (RBAC)
        if not self.authorize(user, "create", "pods"):
            log_component("kube-apiserver", Color.RED, f"AuthZ: User '{user}' FORBIDDEN to create pods")
            return None
        log_component("kube-apiserver", Color.BLUE, f"AuthZ: RBAC authorization granted")

        # 3. Admission Control
        self.admission_control_mutating(pod)
        if not self.admission_control_validating(pod):
            return None

        # 4. Persistence to etcd
        key = f"/registry/pods/{pod.namespace}/{pod.name}"
        self.etcd.put(key, pod)
        log_component("kube-apiserver", Color.BLUE, 
                      f"Pod '{pod.name}' persisted to etcd with status='{pod.status}'")
        return pod

    def bind_pod_to_node(self, pod: PodSpec, node_name: str) -> bool:
        pod.node_name = node_name
        key = f"/registry/pods/{pod.namespace}/{pod.name}"
        self.etcd.put(key, pod)
        log_component("kube-apiserver", Color.BLUE, 
                      f"Binding subresource updated: Pod '{pod.name}' bound to Node '{node_name}'")
        return True

class KubeScheduler:
    """Simulasi kube-scheduler: Filtering (Predicates) & Scoring (Priorities)"""
    def __init__(self, apiserver: KubeAPIServer, nodes: List[Node]):
        self.apiserver = apiserver
        self.nodes = nodes

    def schedule_pending_pods(self) -> None:
        pods_dict = self.apiserver.etcd.list_prefix("/registry/pods/")
        for key, pod in pods_dict.items():
            if isinstance(pod, PodSpec) and pod.node_name is None:
                log_component("kube-scheduler", Color.YELLOW, 
                              f"Scheduling pod '{pod.name}' (req: {pod.resources.cpu_cores} cores, {pod.resources.memory_mb} MB)...")
                
                # Phase 1: Filtering / Predicates
                feasible_nodes = []
                for n in self.nodes:
                    if n.fits(pod.resources):
                        feasible_nodes.append(n)
                        log_component("kube-scheduler", Color.YELLOW, 
                                      f"  Predicate NodeFitsResources: Node '{n.name}' -> PASSED")
                    else:
                        log_component("kube-scheduler", Color.YELLOW, 
                                      f"  Predicate NodeFitsResources: Node '{n.name}' -> REJECTED (Insufficient resources/offline)")

                if not feasible_nodes:
                    log_component("kube-scheduler", Color.RED, 
                                  f"FailedScheduling: Pod '{pod.name}' cannot be placed (0/{len(self.nodes)} nodes available)")
                    continue

                # Phase 2: Scoring / Priorities (LeastAllocatedPriority)
                best_node = None
                best_score = -1.0
                for n in feasible_nodes:
                    free_cpu = (n.total_cpu - n.used_cpu) / n.total_cpu
                    free_mem = (n.total_memory_mb - n.used_memory_mb) / n.total_memory_mb
                    score = (free_cpu + free_mem) * 50.0  # Skala 0-100
                    log_component("kube-scheduler", Color.YELLOW, 
                                  f"  Priority Scoring: Node '{n.name}' score = {score:.1f}/100")
                    if score > best_score:
                        best_score = score
                        best_node = n

                # Phase 3: Binding
                if best_node:
                    best_node.allocate(pod.resources)
                    self.apiserver.bind_pod_to_node(pod, best_node.name)
                    log_component("kube-scheduler", Color.GREEN, 
                                  f"Scheduled: Pod '{pod.name}' placed on '{best_node.name}' (Score: {best_score:.1f})")

class KubeControllerManager:
    """Simulasi Controller Manager: Reconciliation Loop (Desired State vs Actual State)"""
    def __init__(self, apiserver: KubeAPIServer):
        self.apiserver = apiserver

    def reconcile_deployment(self, name: str, desired_replicas: int, template_resources: ResourceRequirements) -> None:
        log_component("kube-controller", Color.CYAN, 
                      f"Reconciliation Loop triggered for Deployment '{name}' (Target Replicas={desired_replicas})")
        
        prefix = f"/registry/pods/default/{name}-"
        existing_pods = [
            v for k, v in self.apiserver.etcd.list_prefix(prefix).items() 
            if isinstance(v, PodSpec) and v.status != "Terminated"
        ]
        
        current_count = len(existing_pods)
        log_component("kube-controller", Color.CYAN, 
                      f"State check: Desired={desired_replicas} vs Actual={current_count}")

        if current_count < desired_replicas:
            diff = desired_replicas - current_count
            log_component("kube-controller", Color.CYAN, f"Reconciling: Scaling UP (+{diff} pods)")
            for i in range(diff):
                pod_name = f"{name}-{uuid.uuid4().hex[:6]}"
                new_pod = PodSpec(
                    name=pod_name,
                    namespace="default",
                    image="nginx:1.25-alpine",
                    resources=template_resources
                )
                self.apiserver.create_pod("admin-token-cluster", new_pod)
        elif current_count > desired_replicas:
            diff = current_count - desired_replicas
            log_component("kube-controller", Color.CYAN, f"Reconciling: Scaling DOWN (-{diff} pods)")
            for i in range(diff):
                victim_pod = existing_pods[i]
                victim_pod.status = "Terminated"
                self.apiserver.etcd.delete(f"/registry/pods/{victim_pod.namespace}/{victim_pod.name}")
        else:
            log_component("kube-controller", Color.GREEN, 
                          f"Reconciliation Clean: Cluster matches desired state.")

class Kubelet:
    """Simulasi Kubelet (Node Agent): Watch pods bound to this node, invoke CRI, sync status"""
    def __init__(self, node: Node, apiserver: KubeAPIServer):
        self.node = node
        self.apiserver = apiserver

    def sync_pods(self) -> None:
        pods_dict = self.apiserver.etcd.list_prefix("/registry/pods/")
        for key, pod in pods_dict.items():
            if isinstance(pod, PodSpec) and pod.node_name == self.node.name and pod.status == "Pending":
                log_component(f"kubelet({self.node.name})", Color.WHITE, 
                              f"Detected assigned pod '{pod.name}'. Calling Container Runtime Interface (CRI)...")
                # Simulasi pull image & start container
                time.sleep(0.3)
                pod.status = "Running"
                self.apiserver.etcd.put(key, pod)
                log_component(f"kubelet({self.node.name})", Color.GREEN, 
                              f"Container started. Status updated to 'Running' (IP: 10.244.1.{hash(pod.name)%250})")

class KubernetesClusterLab:
    def __init__(self):
        self.etcd = EtcdStore()
        self.apiserver = KubeAPIServer(self.etcd)
        self.nodes = [
            Node(name="worker-node-01", total_cpu=4.0, total_memory_mb=8192),
            Node(name="worker-node-02", total_cpu=2.0, total_memory_mb=4096),
        ]
        self.scheduler = KubeScheduler(self.apiserver, self.nodes)
        self.controller = KubeControllerManager(self.apiserver)
        self.kubelets = [Kubelet(n, self.apiserver) for n in self.nodes]

    def display_cluster_state(self) -> None:
        banner("CLUSTER PHYSICAL & LOGICAL STATE DUMP")
        print(f"{Color.BOLD}NODES STATUS:{Color.RESET}")
        for n in self.nodes:
            ready_str = f"{Color.GREEN}Ready{Color.RESET}" if n.ready else f"{Color.RED}NotReady{Color.RESET}"
            cpu_pct = (n.used_cpu / n.total_cpu) * 100
            mem_pct = (n.used_memory_mb / n.total_memory_mb) * 100
            print(f"  • {Color.WHITE}{n.name:<18}{Color.RESET} | Status: {ready_str:<17} | "
                  f"CPU: {n.used_cpu:3.1f}/{n.total_cpu:.1f} cores ({cpu_pct:4.1f}%) | "
                  f"RAM: {n.used_memory_mb:4d}/{n.total_memory_mb:4d} MB ({mem_pct:4.1f}%)")

        print(f"\n{Color.BOLD}ETCD REGISTERED PODS (/registry/pods):{Color.RESET}")
        pods_dict = self.etcd.list_prefix("/registry/pods/")
        if not pods_dict:
            print(f"  {Color.DIM}(No active pods found in etcd storage){Color.RESET}")
        else:
            for k, pod in pods_dict.items():
                if isinstance(pod, PodSpec):
                    st_col = Color.GREEN if pod.status == "Running" else Color.YELLOW
                    node_disp = pod.node_name if pod.node_name else f"{Color.RED}<Unassigned>{Color.RESET}"
                    print(f"  • Pod: {Color.CYAN}{pod.name:<24}{Color.RESET} | "
                          f"Node: {node_disp:<20} | Status: {st_col}{pod.status:<10}{Color.RESET} | "
                          f"Req: {pod.resources.cpu_cores} CPU, {pod.resources.memory_mb} MB")

    def run_e2e_deployment_pipeline(self) -> None:
        banner("TRACE SIKLUS HIDUP REQUEST: DEPLOYMENT NGINX (3 REPLICAS)")
        print(f"{Color.WHITE}Langkah 1: Controller Manager mendeteksi spec deployment dan membuat Pods{Color.RESET}")
        self.controller.reconcile_deployment(
            name="web-frontend", 
            desired_replicas=3, 
            template_resources=ResourceRequirements(cpu_cores=1.0, memory_mb=1024)
        )
        time.sleep(0.5)

        print(f"\n{Color.WHITE}Langkah 2: Scheduler memilih node optimal untuk setiap pending pod{Color.RESET}")
        self.scheduler.schedule_pending_pods()
        time.sleep(0.5)

        print(f"\n{Color.WHITE}Langkah 3: Kubelet pada masing-masing worker node mengeksekusi container{Color.RESET}")
        for k in self.kubelets:
            k.sync_pods()
        time.sleep(0.5)

        self.display_cluster_state()

    def simulate_node_failure(self) -> None:
        banner("SIMULASI FAULT TOLERANCE & SELF-HEALING CONTROL PLANE")
        target_node = self.nodes[0]
        log_component("simulation", Color.RED, f"CRITICAL: Hardware failure pada '{target_node.name}'!")
        target_node.ready = False

        # Evict pods dari node yang mati
        pods_dict = self.etcd.list_prefix("/registry/pods/")
        evicted_count = 0
        for k, pod in list(pods_dict.items()):
            if isinstance(pod, PodSpec) and pod.node_name == target_node.name:
                log_component("kube-controller", Color.RED, 
                              f"NodeController: Node '{target_node.name}' NotReady. Evicting Pod '{pod.name}'")
                self.etcd.delete(k)
                evicted_count += 1

        print(f"\n{Color.WHITE}Controller Manager melakukan Self-Healing (Reconcile Loop):{Color.RESET}")
        self.controller.reconcile_deployment(
            name="web-frontend", 
            desired_replicas=3, 
            template_resources=ResourceRequirements(cpu_cores=1.0, memory_mb=1024)
        )
        
        print(f"\n{Color.WHITE}Scheduler menjadwalkan ulang pod pengganti:{Color.RESET}")
        self.scheduler.schedule_pending_pods()

        print(f"\n{Color.WHITE}Kubelet node yang sehat menjalankan pod baru:{Color.RESET}")
        for k in self.kubelets:
            k.sync_pods()

        self.display_cluster_state()

def interactive_cli():
    lab = KubernetesClusterLab()
    while True:
        banner("KUBERNETES CONTROL PLANE ARCHITECTURE LAB (BAB-01)")
        print(f"{Color.BOLD}PILIH SKENARIO PRAKTIKUM INTERAKTIF:{Color.RESET}")
        print("  1. Dump State Cluster (etcd, Nodes, Pods)")
        print("  2. Jalankan Trace Siklus Hidup Deploy Pod/Deployment End-to-End")
        print("  3. Uji Coba RBAC & Admission Control (Unauthorized & Invalid Pod)")
        print("  4. Simulasi Node Failure & Self-Healing Reconciliation Loop")
        print("  5. Keluar (Exit)")
        print()

        try:
            choice = input(f"{Color.CYAN}Masukkan nomor pilihan [1-5]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting lab...")
            break

        if choice == "1":
            lab.display_cluster_state()
        elif choice == "2":
            lab.run_e2e_deployment_pipeline()
        elif choice == "3":
            banner("UJI COBA ADMISSION CONTROLLER & RBAC SECURITY GATEWAY")
            # Kasus 1: Token Palsu
            invalid_pod = PodSpec("hacker-pod", "default", "evil:latest", ResourceRequirements(0.5, 256))
            log_component("Client", Color.WHITE, "Mencoba membuat pod dengan token ilegal...")
            lab.apiserver.create_pod("fake-token-123", invalid_pod)

            # Kasus 2: Resource invalid
            bad_resource_pod = PodSpec("greedy-pod", "default", "busybox", ResourceRequirements(-1.0, 0))
            log_component("Client", Color.WHITE, "Mencoba membuat pod dengan resource invalid (negatif)...")
            lab.apiserver.create_pod("admin-token-cluster", bad_resource_pod)
        elif choice == "4":
            lab.simulate_node_failure()
        elif choice == "5":
            print(f"\n{Color.GREEN}Lab selesai. Praktikum pemahaman arsitektur internal Kubernetes tuntas!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 1-5.{Color.RESET}")
        
        input(f"\n{Color.DIM}Tekan [Enter] untuk kembali ke menu...{Color.RESET}")

if __name__ == "__main__":
    # Jika dijalankan tanpa terminal interaktif (CI/test mode), jalankan simulasi otomatis
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        lab = KubernetesClusterLab()
        lab.run_e2e_deployment_pipeline()
        lab.simulate_node_failure()
    else:
        interactive_cli()
