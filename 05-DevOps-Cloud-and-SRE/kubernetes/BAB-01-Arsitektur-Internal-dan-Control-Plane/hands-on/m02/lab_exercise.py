#!/usr/bin/env python3
"""
Kubernetes Control Plane Internal Architecture Simulation (BAB-01)
Hands-on Lab Exercise: High-Availability & Request Lifecycle Simulator
"""

import sys
import time
import random
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

# ==========================================
# Terminal ANSI Formatting & Color Palette
# ==========================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    # Background accents
    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"

def log_event(component: str, color: str, message: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{Style.DIM}[{timestamp}]{Style.RESET} {color}{Style.BOLD}[{component:^15}]{Style.RESET} {message}")

# ==========================================
# Data Models
# ==========================================
@dataclass
class ResourceRequirements:
    cpu_millicores: int
    memory_mb: int

@dataclass
class PodSpec:
    name: str
    namespace: str
    resources: ResourceRequirements
    node_name: Optional[str] = None
    tolerations: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    status: str = "Pending"  # Pending, Scheduled, Running, Evicted

@dataclass
class Node:
    name: str
    allocatable_cpu: int
    allocatable_memory: int
    used_cpu: int = 0
    used_memory: int = 0
    taints: List[str] = field(default_factory=list)
    healthy: bool = True
    last_heartbeat: float = field(default_factory=time.time)

# ==========================================
# Component: etcd (v3 Key-Value Store)
# ==========================================
class EtcdCluster:
    def __init__(self, members: int = 3):
        self.members = members
        self.term = 1
        self.revision = 0
        self.db: Dict[str, str] = {}
        self.leader = "etcd-01"
        self.quorum_active = True

    def put(self, key: str, value: Any) -> Tuple[bool, str]:
        if not self.quorum_active:
            return False, "etcd Raft consensus error: Quorum lost (no leader elected)"
        self.revision += 1
        self.db[key] = json.dumps(value)
        return True, f"Revision {self.revision} committed to Raft log"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        val = self.db.get(key)
        return json.loads(val) if val else None

    def list_prefix(self, prefix: str) -> Dict[str, Any]:
        return {k: json.loads(v) for k, v in self.db.items() if k.startswith(prefix)}

# ==========================================
# Component: Kube-API-Server
# ==========================================
class KubeApiServer:
    def __init__(self, etcd: EtcdCluster):
        self.etcd = etcd
        self.admission_plugins = ["DefaultStorageClass", "MutatingAdmissionWebhook", "ValidatingAdmissionWebhook"]

    def handle_request(self, token: str, action: str, resource: str, payload: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        log_event("API-SERVER", Style.CYAN, f"Incoming REST request: {action} /api/v1/{resource}")
        
        # 1. Authentication
        if not token.startswith("Bearer k8s-admin-token"):
            log_event("API-SERVER", Style.RED, "Authentication failed: Invalid credentials / mTLS client cert rejected.")
            return False, "401 Unauthorized", None
        log_event("API-SERVER", Style.CYAN, "-> Step 1: Authentication successful (TLS Client Subject validated).")

        # 2. Authorization (RBAC)
        if action == "POST" and payload.get("namespace") == "kube-system" and "admin" not in token:
            log_event("API-SERVER", Style.RED, "RBAC Forbidden: User cannot write to 'kube-system' namespace.")
            return False, "403 Forbidden by ClusterRoleBinding", None
        log_event("API-SERVER", Style.CYAN, "-> Step 2: RBAC Authorization passed (User has verbs [create, get, watch]).")

        # 3. Mutating Admission Webhook
        if "labels" not in payload:
            payload["labels"] = {}
        payload["labels"]["app.kubernetes.io/managed-by"] = "k8s-control-plane"
        log_event("API-SERVER", Style.CYAN, "-> Step 3: Mutating Webhook injected standard tracking labels.")

        # 4. Validating Admission Webhook
        res = payload.get("resources", {})
        if res.get("cpu_millicores", 0) > 4000 or res.get("memory_mb", 0) > 8192:
            log_event("API-SERVER", Style.RED, "Validation Error: Requested resources exceed LimitRange ceiling.")
            return False, "422 Unprocessable Entity: ResourceLimitExceeded", None
        log_event("API-SERVER", Style.CYAN, "-> Step 4: Validating Webhook approved schema and resource bounds.")

        # 5. Commit to etcd
        key = f"/registry/pods/{payload.get('namespace', 'default')}/{payload.get('name')}"
        ok, msg = self.etcd.put(key, payload)
        if not ok:
            log_event("API-SERVER", Style.RED, f"Storage failure: {msg}")
            return False, f"500 Internal Storage Error: {msg}", None

        log_event("API-SERVER", Style.GREEN, f"-> Step 5: Resource written to etcd at {key} (Revision: {self.etcd.revision})")
        return True, "201 Created", payload

# ==========================================
# Component: Kube-Scheduler
# ==========================================
class KubeScheduler:
    def __init__(self, api_server: KubeApiServer, nodes: List[Node]):
        self.api_server = api_server
        self.nodes = nodes

    def schedule_pending_pod(self, pod: PodSpec) -> bool:
        log_event("SCHEDULER", Style.YELLOW, f"Evaluating schedule pipeline for Pod: '{pod.name}' (Namespace: {pod.namespace})")
        
        # Phase 1: Filtering (Predicates)
        feasible_nodes: List[Node] = []
        for n in self.nodes:
            if not n.healthy:
                log_event("SCHEDULER", Style.DIM, f"  [Filter] Node {n.name} discarded: NodeNotReady")
                continue
            
            # Resource Check
            cpu_avail = n.allocatable_cpu - n.used_cpu
            mem_avail = n.allocatable_memory - n.used_memory
            if cpu_avail < pod.resources.cpu_millicores or mem_avail < pod.resources.memory_mb:
                log_event("SCHEDULER", Style.DIM, f"  [Filter] Node {n.name} discarded: Insufficient CPU/Memory")
                continue
                
            # Taints & Tolerations Check
            tolerated = True
            for taint in n.taints:
                if taint not in pod.tolerations:
                    tolerated = False
                    log_event("SCHEDULER", Style.DIM, f"  [Filter] Node {n.name} discarded: Untolerated taint '{taint}'")
                    break
            if tolerated:
                feasible_nodes.append(n)

        if not feasible_nodes:
            log_event("SCHEDULER", Style.RED, f"Scheduling Failed: No available nodes satisfy Pod predicates (0/{len(self.nodes)} nodes match).")
            return False

        # Phase 2: Scoring (Priorities - LeastAllocatedPriority)
        scored_nodes: List[Tuple[Node, float]] = []
        for n in feasible_nodes:
            free_cpu_ratio = (n.allocatable_cpu - n.used_cpu) / n.allocatable_cpu
            free_mem_ratio = (n.allocatable_memory - n.used_memory) / n.allocatable_memory
            score = (free_cpu_ratio + free_mem_ratio) * 50.0  # Scale to 100
            scored_nodes.append((n, score))
            log_event("SCHEDULER", Style.YELLOW, f"  [Scoring] Node {n.name} score: {score:.2f}/100")

        # Pick node with highest score
        best_node, highest_score = max(scored_nodes, key=lambda item: item[1])
        log_event("SCHEDULER", Style.GREEN, f"Binding chosen node '{best_node.name}' (Score: {highest_score:.2f}) -> Pod '{pod.name}'")

        # Phase 3: Binding (Update state)
        best_node.used_cpu += pod.resources.cpu_millicores
        best_node.used_memory += pod.resources.memory_mb
        pod.node_name = best_node.name
        pod.status = "Running"
        
        # Persist binding to etcd via API server
        key = f"/registry/pods/{pod.namespace}/{pod.name}"
        self.api_server.etcd.put(key, {
            "name": pod.name,
            "namespace": pod.namespace,
            "node_name": pod.node_name,
            "status": pod.status,
            "resources": {
                "cpu_millicores": pod.resources.cpu_millicores,
                "memory_mb": pod.resources.memory_mb
            }
        })
        return True

# ==========================================
# Component: Kube-Controller-Manager
# ==========================================
class KubeControllerManager:
    def __init__(self, api_server: KubeApiServer, scheduler: KubeScheduler, nodes: List[Node]):
        self.api_server = api_server
        self.scheduler = scheduler
        self.nodes = nodes

    def run_reconciliation_cycle(self) -> None:
        log_event("CONTROLLER-MGR", Style.MAGENTA, "Reconciliation Loop: Checking active Node Leases & Pod Health...")
        
        # Node Lifecycle Controller
        now = time.time()
        for node in self.nodes:
            if node.healthy and (now - node.last_heartbeat > 40.0):
                node.healthy = False
                log_event("CONTROLLER-MGR", Style.RED, f"Node Lifecycle Alarm: Heartbeat lost for '{node.name}'. Marking NodeNotReady.")
                self.evict_pods_from_node(node.name)

    def evict_pods_from_node(self, failed_node: str) -> None:
        log_event("CONTROLLER-MGR", Style.YELLOW, f"Eviction routine initiated for orphaned workloads on '{failed_node}'.")
        all_pods = self.api_server.etcd.list_prefix("/registry/pods/")
        for key, p_data in all_pods.items():
            if p_data.get("node_name") == failed_node and p_data.get("status") == "Running":
                log_event("CONTROLLER-MGR", Style.MAGENTA, f"Evicting Pod '{p_data['name']}' -> Triggering rescheduling.")
                # Reset pod state
                res_dict = p_data.get("resources", {})
                pod = PodSpec(
                    name=p_data["name"],
                    namespace=p_data["namespace"],
                    resources=ResourceRequirements(res_dict.get("cpu_millicores", 250), res_dict.get("memory_mb", 512)),
                    status="Pending"
                )
                self.scheduler.schedule_pending_pod(pod)

# ==========================================
# Interactive Simulator Harness
# ==========================================
class KubernetesSimulationCluster:
    def __init__(self):
        self.etcd = EtcdCluster(members=3)
        self.api_server = KubeApiServer(self.etcd)
        self.nodes = [
            Node("worker-alpha", allocatable_cpu=4000, allocatable_memory=8192),
            Node("worker-bravo", allocatable_cpu=4000, allocatable_memory=8192),
            Node("worker-gpu-tainted", allocatable_cpu=8000, allocatable_memory=16384, taints=["dedicated=gpu:NoSchedule"])
        ]
        self.scheduler = KubeScheduler(self.api_server, self.nodes)
        self.controller_mgr = KubeControllerManager(self.api_server, self.scheduler, self.nodes)

    def print_banner(self) -> None:
        print(f"{Style.CYAN}{Style.BOLD}" + "=" * 78)
        print("   KUBERNETES CONTROL PLANE ARCHITECTURE INTERACTIVE SIMULATOR (BAB-01)")
        print("   Hands-On Production-Grade Internals & Raft Consensus Diagnostic Tool")
        print("=" * 78 + f"{Style.RESET}\n")

    def show_cluster_status(self) -> None:
        print(f"\n{Style.BOLD}--- [ CONTROL PLANE & NODE TOPOLOGY STATUS ] ---{Style.RESET}")
        raft_status = f"{Style.GREEN}Healthy (Quorum 3/3){Style.RESET}" if self.etcd.quorum_active else f"{Style.RED}DEGRADED (Quorum Lost){Style.RESET}"
        print(f" etcd Cluster:     Leader={self.etcd.leader} | Term={self.etcd.term} | Rev={self.etcd.revision} | State={raft_status}")
        print(f" API Server:       Mutating/Validating Admission Plugins Active")
        print(f" Controller-Mgr:   NodeLifecycleController, ReplicaSetController Active\n")
        
        print(f"{Style.UNDERLINE}{'Node Name':<22} {'State':<12} {'CPU Used/Total':<18} {'Mem Used/Total':<18} {'Taints'}{Style.RESET}")
        for n in self.nodes:
            state_str = f"{Style.GREEN}Ready{Style.RESET}" if n.healthy else f"{Style.RED}NotReady{Style.RESET}"
            cpu_str = f"{n.used_cpu}/{n.allocatable_cpu}m"
            mem_str = f"{n.used_memory}/{n.allocatable_memory}Mi"
            taints_str = ",".join(n.taints) if n.taints else "-"
            print(f"{n.name:<22} {state_str:<21} {cpu_str:<18} {mem_str:<18} {taints_str}")
        print()

    def simulate_workload_submission(self) -> None:
        print(f"\n{Style.BOLD}>>> Skenario 1: Deployment Request Lifecycle (API -> Admission -> etcd -> Scheduler){Style.RESET}")
        pod_name = f"web-api-{random.randint(1000, 9999)}"
        token = "Bearer k8s-admin-token-production-sec-99"
        
        payload = {
            "name": pod_name,
            "namespace": "production",
            "resources": {
                "cpu_millicores": 1000,
                "memory_mb": 2048
            }
        }
        
        # 1. API Server Lifecycle
        success, code, res = self.api_server.handle_request(token, "POST", "pods", payload)
        if not success:
            print(f"{Style.RED}Submisi ditolak oleh API Server: {code}{Style.RESET}")
            return

        # 2. Scheduling Phase
        pod_spec = PodSpec(
            name=payload["name"],
            namespace=payload["namespace"],
            resources=ResourceRequirements(payload["resources"]["cpu_millicores"], payload["resources"]["memory_mb"])
        )
        scheduled = self.scheduler.schedule_pending_pod(pod_spec)
        if scheduled:
            print(f"{Style.GREEN}{Style.BOLD}Pod '{pod_name}' sukses dijadwalkan pada node '{pod_spec.node_name}'!{Style.RESET}\n")
        else:
            print(f"{Style.RED}Pod '{pod_name}' gagal dijadwalkan.{Style.RESET}\n")

    def simulate_node_failure_scenario(self) -> None:
        print(f"\n{Style.BOLD}>>> Skenario 2: Simulasi Node Outage & Eviction oleh Controller Manager{Style.RESET}")
        target_node = self.nodes[0]
        print(f"{Style.YELLOW}Mematikan worker node '{target_node.name}' (Kubelet network partition)...{Style.RESET}")
        target_node.last_heartbeat = time.time() - 60.0  # Expire heartbeat
        self.controller_mgr.run_reconciliation_cycle()
        print(f"{Style.GREEN}Siklus rekonsiliasi pemulihan otomatis selesai.{Style.RESET}\n")

    def simulate_etcd_partition(self) -> None:
        print(f"\n{Style.BOLD}>>> Skenario 3: Simulasi Split-Brain & Hilang Quorum etcd Raft{Style.RESET}")
        self.etcd.quorum_active = not self.etcd.quorum_active
        if not self.etcd.quorum_active:
            print(f"{Style.RED}{Style.BOLD}[ALARM] Partisi jaringan memutus 2 dari 3 node etcd. Quorum hilang!{Style.RESET}")
            print(f"{Style.YELLOW}Mencoba submit Pod saat Raft tidak memiliki kuorum:{Style.RESET}")
            self.simulate_workload_submission()
        else:
            print(f"{Style.GREEN}[PULIH] Koneksi jaringan etcd pulih. Quorum etcd tercapai kembali.{Style.RESET}")

    def run_menu(self) -> None:
        self.print_banner()
        while True:
            self.show_cluster_status()
            print(f"{Style.BOLD}Menu Eksperimen Arsitektur Kubernetes:{Style.RESET}")
            print("  1. Submit Pod Baru (Tracer Lifecycle: Auth -> Admission -> etcd -> Scheduler)")
            print("  2. Simulasi Kematian Node & Self-Healing Eviction (Controller Manager)")
            print("  3. Toggle Kegagalan Kuorum etcd (Simulasi Raft Consensus Failure)")
            print("  4. Pulihkan Semua Node ke Status Sehat")
            print("  5. Keluar")
            
            try:
                choice = input(f"\n{Style.CYAN}Pilih opsi [1-5]: {Style.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{Style.YELLOW}Sesi interaktif diakhiri.{Style.RESET}")
                break

            if choice == "1":
                self.simulate_workload_submission()
            elif choice == "2":
                self.simulate_node_failure_scenario()
            elif choice == "3":
                self.simulate_etcd_partition()
            elif choice == "4":
                for n in self.nodes:
                    n.healthy = True
                    n.last_heartbeat = time.time()
                self.etcd.quorum_active = True
                print(f"{Style.GREEN}Seluruh node dan etcd dikembalikan ke status prima.{Style.RESET}")
            elif choice == "5":
                print(f"{Style.GREEN}Keluar dari simulator. Selesai.{Style.RESET}")
                break
            else:
                print(f"{Style.RED}Pilihan tidak valid. Silakan pilih 1-5.{Style.RESET}")
            
            # Non-interactive fallback safeguard
            if not sys.stdin.isatty():
                print(f"{Style.DIM}Non-interactive stream detected. Skenario otomatis selesai.{Style.RESET}")
                break

if __name__ == "__main__":
    cluster_sim = KubernetesSimulationCluster()
    # Jika dijalankan dengan argument non-interactive / test
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        cluster_sim.simulate_workload_submission()
        cluster_sim.simulate_node_failure_scenario()
        cluster_sim.simulate_etcd_partition()
        cluster_sim.simulate_etcd_partition()
        print(f"{Style.GREEN}Mode non-interaktif test berhasil dijalankan tanpa error!{Style.RESET}")
    else:
        cluster_sim.run_menu()
