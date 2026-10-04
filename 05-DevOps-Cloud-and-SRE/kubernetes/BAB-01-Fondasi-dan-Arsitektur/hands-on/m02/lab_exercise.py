#!/usr/bin/env python3
"""
Lab Exercise: Modul 02 - Kubernetes Enterprise Architecture Deep Dive
Simulasi Teknis Siklus Hidup Request kube-apiserver, etcd Raft Quorum, dan Scheduling Framework.
"""

import sys
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ANSI Colors & Formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"
BG_DARK = "\033[40m"
BG_BLUE = "\033[44m"


def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}================================================================================
          KUBERNETES CONTROL PLANE & REQUEST LIFECYCLE SIMULATOR
           Module 02: Deep Dive Arsitektur Produksi & Scheduling Engine
================================================================================{CLR_RESET}"""
    print(banner)


def log_phase(phase: str, desc: str):
    print(f"\n{CLR_BLUE}{CLR_BOLD}>>> [FASE: {phase.upper()}]{CLR_RESET} {CLR_WHITE}{desc}{CLR_RESET}")


def log_step(component: str, message: str, status: str = "INFO"):
    color = CLR_WHITE
    symbol = "•"
    if status == "SUCCESS":
        color = CLR_GREEN
        symbol = "✔"
    elif status == "WARNING":
        color = CLR_YELLOW
        symbol = "⚠"
    elif status == "FAILED":
        color = CLR_RED
        symbol = "✖"
    elif status == "MUTATE":
        color = CLR_MAGENTA
        symbol = "✎"

    print(f"  {color}[{component}] {symbol} {message}{CLR_RESET}")


@dataclass
class UserIdentity:
    username: str
    groups: List[str]
    token: str


@dataclass
class ContainerSpec:
    name: str
    image: str
    cpu_request: int  # in millicores
    mem_request: int  # in MiB
    privileged: bool = False
    run_as_non_root: bool = True


@dataclass
class PodSpec:
    name: str
    namespace: str
    containers: List[ContainerSpec]
    node_selector: Dict[str, str] = field(default_factory=dict)
    tolerations: List[str] = field(default_factory=list)
    annotations: Dict[str, str] = field(default_factory=dict)
    assigned_node: Optional[str] = None


@dataclass
class Node:
    name: str
    cpu_capacity: int  # millicores
    mem_capacity: int  # MiB
    cpu_used: int
    mem_used: int
    labels: Dict[str, str]
    taints: List[str]


class MockEtcdCluster:
    def __init__(self, node_count: int = 3):
        self.node_count = node_count
        self.quorum_threshold = (node_count // 2) + 1
        self.revision = 1000
        self.kv_store: Dict[str, str] = {}
        self.wal_log: List[str] = []

    def commit(self, key: str, value: str) -> Tuple[bool, int, str]:
        # Simulasi Raft consensus check
        active_nodes = self.node_count  # Anggap semua node sehat pada baseline
        if active_nodes >= self.quorum_threshold:
            self.revision += 1
            self.kv_store[key] = value
            self.wal_log.append(f"REV:{self.revision} PUT {key}")
            return True, self.revision, f"Quorum tercapai ({active_nodes}/{self.node_count} nodes ACK)"
        return False, self.revision, f"Split-brain! Quorum tidak terpenuhi (< {self.quorum_threshold})"


class KubeApiServer:
    def __init__(self, etcd: MockEtcdCluster):
        self.etcd = etcd
        self.token_db = {
            "token-admin-123": UserIdentity("cluster-admin", ["system:masters"], "token-admin-123"),
            "token-dev-456": UserIdentity("developer-alice", ["developers"], "token-dev-456"),
            "token-ci-789": UserIdentity("service-ci", ["system:serviceaccounts:ci"], "token-ci-789"),
        }
        self.rbac_roles = {
            "developers": {"resources": ["pods", "services"], "namespaces": ["default", "dev"], "verbs": ["create", "get", "list"]},
            "system:masters": {"resources": ["*"], "namespaces": ["*"], "verbs": ["*"]},
        }

    def authenticate(self, token: str) -> Optional[UserIdentity]:
        time.sleep(0.05)
        return self.token_db.get(token)

    def authorize(self, user: UserIdentity, verb: str, resource: str, namespace: str) -> bool:
        time.sleep(0.05)
        for group in user.groups:
            perms = self.rbac_roles.get(group)
            if not perms:
                continue
            if "*" in perms["resources"] or resource in perms["resources"]:
                if "*" in perms["namespaces"] or namespace in perms["namespaces"]:
                    if "*" in perms["verbs"] or verb in perms["verbs"]:
                        return True
        return False

    def mutate(self, pod: PodSpec) -> List[str]:
        mutations = []
        # Mutating Webhook 1: Inject default resource limits jika kosong / terlalu rendah
        for c in pod.containers:
            if c.cpu_request == 0:
                c.cpu_request = 100
                mutations.append(f"DefaultLimits: CPU request diatur default 100m pada kontainer '{c.name}'")
            if c.mem_request == 0:
                c.mem_request = 128
                mutations.append(f"DefaultLimits: Memory request diatur default 128Mi pada kontainer '{c.name}'")

        # Mutating Webhook 2: Sidecar Injection jika ada anotasi mesh
        if pod.annotations.get("sidecar.istio.io/inject") == "true":
            sidecar = ContainerSpec(
                name="istio-proxy",
                image="docker.io/istio/proxyv2:1.20.0",
                cpu_request=50,
                mem_request=64,
                run_as_non_root=True
            )
            pod.containers.append(sidecar)
            mutations.append("IstioInjector: Sidecar proxy 'istio-proxy' berhasil diinjeksi")

        return mutations

    def validate_schema(self, pod: PodSpec) -> Tuple[bool, str]:
        if not pod.name or len(pod.name) > 63:
            return False, "Pod name kosong atau melebihi 63 karakter RFC 1123"
        for c in pod.containers:
            if not c.image:
                return False, f"Image kontainer '{c.name}' tidak didefinisikan"
        return True, "Schema OpenAPI v3 valid"

    def validate_admission(self, pod: PodSpec) -> Tuple[bool, List[str]]:
        violations = []
        # Policy: Pod Security Standards (Restricted)
        for c in pod.containers:
            if c.privileged:
                violations.append(f"PSS Violation: Kontainer '{c.name}' meminta hak istimewa (privileged=true)")
            if not c.run_as_non_root:
                violations.append(f"PSS Violation: Kontainer '{c.name}' diizinkan berjalan sebagai root")

        if violations:
            return False, violations
        return True, ["Pod Security Standards (Baseline & Restricted) lolos"]

    def process_request(self, token: str, verb: str, resource: str, pod: PodSpec) -> Tuple[bool, str, Optional[int]]:
        log_phase("1. Authentication (Authn)", "Verifikasi kredensial bearer token X.509 / OIDC")
        user = self.authenticate(token)
        if not user:
            log_step("kube-apiserver", "401 Unauthorized: Bearer Token tidak valid atau kedaluwarsa", "FAILED")
            return False, "401 Unauthorized", None
        log_step("kube-apiserver", f"Identitas subjek terverifikasi: User='{user.username}', Groups={user.groups}", "SUCCESS")

        log_phase("2. Authorization (Authz)", "Evaluasi Rule-Based Access Control (RBAC)")
        if not self.authorize(user, verb, resource, pod.namespace):
            log_step("kube-apiserver", f"403 Forbidden: User '{user.username}' tidak memiliki izin '{verb}' pada resource '{resource}' di namespace '{pod.namespace}'", "FAILED")
            return False, "403 Forbidden", None
        log_step("kube-apiserver", f"RBAC Check Passed: Subject diizinkan melakukan verb='{verb}' pada namespace='{pod.namespace}'", "SUCCESS")

        log_phase("3. Mutating Admission Webhooks", "Modifikasi deklarasi objek sebelum validasi ketat")
        mutations = self.mutate(pod)
        for m in mutations:
            log_step("MutatingAdmission", m, "MUTATE")
        if not mutations:
            log_step("MutatingAdmission", "Tidak ada mutasi yang diperlukan pada objek Pod", "INFO")

        log_phase("4. Schema Validation", "Validasi format JSON/YAML terhadap skema OpenAPI v3")
        valid, msg = self.validate_schema(pod)
        if not valid:
            log_step("SchemaValidator", f"400 Bad Request: {msg}", "FAILED")
            return False, msg, None
        log_step("SchemaValidator", msg, "SUCCESS")

        log_phase("5. Validating Admission Webhooks", "Enforcement kepatuhan kebijakan enterprise (OPA/Gatekeeper / Kyverno / PSS)")
        valid_adm, msgs = self.validate_admission(pod)
        if not valid_adm:
            for v in msgs:
                log_step("ValidatingAdmission", f"Deny Enforcement: {v}", "FAILED")
            return False, "Validating Admission Denied", None
        for v in msgs:
            log_step("ValidatingAdmission", v, "SUCCESS")

        log_phase("6. etcd Raft Storage Layer", "Persistensi linearizable object ke distributed key-value store via Raft")
        key = f"/registry/pods/{pod.namespace}/{pod.name}"
        val = json.dumps({"name": pod.name, "containers": [c.name for c in pod.containers]})
        success, rev, status_desc = self.etcd.commit(key, val)
        if success:
            log_step("etcd-raft", f"Fsync WAL sukses. Revision: {rev} -> {status_desc}", "SUCCESS")
            log_step("etcd-raft", f"Tersimpan di: {key}", "INFO")
            return True, "Created", rev
        else:
            log_step("etcd-raft", f"500 Internal Error: {status_desc}", "FAILED")
            return False, status_desc, None


class KubeScheduler:
    def __init__(self, nodes: List[Node]):
        self.nodes = nodes

    def schedule(self, pod: PodSpec) -> Optional[str]:
        log_phase("Scheduling Pipeline", f"Menempatkan Pod '{pod.name}' ke node optimal")
        log_step("PriorityQueue", f"Pod '{pod.name}' masuk ke ActiveQ", "INFO")

        # Hitung total kebutuhan resource Pod
        tot_cpu = sum(c.cpu_request for c in pod.containers)
        tot_mem = sum(c.mem_request for c in pod.containers)
        log_step("ResourceProfile", f"Total Request: CPU={tot_cpu}m, Memory={tot_mem}MiB across {len(pod.containers)} container(s)", "INFO")

        # 1. Filter Phase (Predicates)
        eligible_nodes: List[Node] = []
        for node in self.nodes:
            # Check Taints & Tolerations
            if node.taints:
                unhandled_taints = [t for t in node.taints if t not in pod.tolerations]
                if unhandled_taints:
                    log_step("FilterPlugin", f"Node '{node.name}' gugur: Taint {unhandled_taints} tidak ditoleransi", "WARNING")
                    continue

            # Check Node Affinity / Node Selector
            if pod.node_selector:
                matched = all(node.labels.get(k) == v for k, v in pod.node_selector.items())
                if not matched:
                    log_step("FilterPlugin", f"Node '{node.name}' gugur: Label node tidak cocok dengan selector {pod.node_selector}", "WARNING")
                    continue

            # Check Resource Capacity (NodeResourcesFit)
            avail_cpu = node.cpu_capacity - node.cpu_used
            avail_mem = node.mem_capacity - node.mem_used
            if avail_cpu < tot_cpu or avail_mem < tot_mem:
                log_step("FilterPlugin", f"Node '{node.name}' gugur: Resource tidak cukup (Sisa CPU:{avail_cpu}m, Mem:{avail_mem}MiB)", "WARNING")
                continue

            log_step("FilterPlugin", f"Node '{node.name}' lolos fase Filter", "SUCCESS")
            eligible_nodes.append(node)

        if not eligible_nodes:
            log_step("kube-scheduler", f"Scheduling FAILED: 0/{len(self.nodes)} node memenuhi syarat (Pod dialihkan ke UnschedulableQ)", "FAILED")
            return None

        # 2. Score Phase (Priorities)
        log_step("ScorePlugin", f"Menghitung skor distribusi beban untuk {len(eligible_nodes)} node yang lolos", "INFO")
        scored_nodes: List[Tuple[Node, float]] = []
        for node in eligible_nodes:
            # Formula NodeResourcesBalancedAllocation: mendekati 50-50 ratio balance
            cpu_ratio = (node.cpu_used + tot_cpu) / node.cpu_capacity
            mem_ratio = (node.mem_used + tot_mem) / node.mem_capacity
            score = 100.0 - (abs(cpu_ratio - mem_ratio) * 100.0)
            scored_nodes.append((node, score))
            log_step("ScorePlugin", f"Node '{node.name}' -> Score: {score:.2f}/100.0 (Proj CPU: {cpu_ratio*100:.1f}%, Mem: {mem_ratio*100:.1f}%)", "INFO")

        # Ambil skor tertinggi
        scored_nodes.sort(key=lambda x: x[1], reverse=True)
        winner_node, win_score = scored_nodes[0]

        # 3. Reserve & Bind Phase
        log_step("ReservePlugin", f"Alokasi resource terkunci pada '{winner_node.name}' (Score: {win_score:.2f})", "SUCCESS")
        winner_node.cpu_used += tot_cpu
        winner_node.mem_used += tot_mem
        pod.assigned_node = winner_node.name
        log_step("BindPlugin", f"Pod '{pod.name}' berhasil di-bind secara asinkron ke node '{winner_node.name}'", "SUCCESS")

        return winner_node.name


def run_simulation():
    print_banner()

    etcd = MockEtcdCluster(node_count=3)
    apiserver = KubeApiServer(etcd)

    nodes = [
        Node(name="worker-node-01", cpu_capacity=4000, mem_capacity=8192, cpu_used=1200, mem_used=3000,
             labels={"topology.kubernetes.io/zone": "ap-southeast-1a", "tier": "frontend"}, taints=[]),
        Node(name="worker-node-02", cpu_capacity=4000, mem_capacity=8192, cpu_used=3500, mem_used=7200,
             labels={"topology.kubernetes.io/zone": "ap-southeast-1b", "tier": "backend"}, taints=[]),
        Node(name="worker-node-gpu-01", cpu_capacity=16000, mem_capacity=65536, cpu_used=2000, mem_used=8000,
             labels={"topology.kubernetes.io/zone": "ap-southeast-1a", "accelerator": "nvidia-a100"},
             taints=["sku=gpu:NoSchedule"]),
    ]
    scheduler = KubeScheduler(nodes)

    print(f"\n{CLR_YELLOW}{CLR_BOLD}--- SKENARIO 1: Enterprise Microservice Pod Deployment (Sukses Penuh) ---{CLR_RESET}")
    pod1 = PodSpec(
        name="payment-service-v2",
        namespace="default",
        containers=[
            ContainerSpec(name="app-server", image="internal-reg.corp.com/payment:v2.1", cpu_request=500, mem_request=1024, privileged=False, run_as_non_root=True)
        ],
        annotations={"sidecar.istio.io/inject": "true"},
        node_selector={"topology.kubernetes.io/zone": "ap-southeast-1a"}
    )
    ok, status, rev = apiserver.process_request("token-dev-456", "create", "pods", pod1)
    if ok:
        assigned = scheduler.schedule(pod1)
        print(f"\n{CLR_GREEN}{CLR_BOLD}>>> STATUS AKHIR SKENARIO 1: BERHASIL - Pod berjalan di {assigned} (Revision {rev}){CLR_RESET}")

    time.sleep(0.1)

    print(f"\n{CLR_YELLOW}{CLR_BOLD}--- SKENARIO 2: Pelanggaran Keamanan PSS / OPA Gatekeeper (Validating Webhook Rejection) ---{CLR_RESET}")
    pod2 = PodSpec(
        name="crypto-miner-rogue",
        namespace="default",
        containers=[
            ContainerSpec(name="miner", image="docker.io/untrusted/miner:latest", cpu_request=2000, mem_request=4096, privileged=True, run_as_non_root=False)
        ]
    )
    ok, status, _ = apiserver.process_request("token-dev-456", "create", "pods", pod2)
    if not ok:
        print(f"\n{CLR_RED}{CLR_BOLD}>>> STATUS AKHIR SKENARIO 2: DITOLAK API-SERVER ({status}) - Mencegah eskalasi privilese container{CLR_RESET}")

    time.sleep(0.1)

    print(f"\n{CLR_YELLOW}{CLR_BOLD}--- SKENARIO 3: Pelanggaran Akses RBAC (Authorization Failure) ---{CLR_RESET}")
    pod3 = PodSpec(
        name="backdoor-pod",
        namespace="kube-system",
        containers=[
            ContainerSpec(name="sniffer", image="alpine:3.18", cpu_request=100, mem_request=64)
        ]
    )
    ok, status, _ = apiserver.process_request("token-dev-456", "create", "pods", pod3)
    if not ok:
        print(f"\n{CLR_RED}{CLR_BOLD}>>> STATUS AKHIR SKENARIO 3: DITOLAK RBAC ({status}) - Pengguna biasa dilarang memanipulasi kube-system{CLR_RESET}")

    time.sleep(0.1)

    print(f"\n{CLR_YELLOW}{CLR_BOLD}--- SKENARIO 4: Pod Gagal Terjadwal (Resource Exhaustion / Taints Mismatch) ---{CLR_RESET}")
    pod4 = PodSpec(
        name="monolith-analytics-heavy",
        namespace="default",
        containers=[
            ContainerSpec(name="spark-worker", image="internal-reg.corp.com/spark:3.5", cpu_request=3500, mem_request=6000)
        ],
        node_selector={"topology.kubernetes.io/zone": "ap-southeast-1a"}
    )
    ok, status, rev = apiserver.process_request("token-admin-123", "create", "pods", pod4)
    if ok:
        assigned = scheduler.schedule(pod4)
        if not assigned:
            print(f"\n{CLR_YELLOW}{CLR_BOLD}>>> STATUS AKHIR SKENARIO 4: PENDING (Unschedulable) - Tidak ada node memenuhi filter resource & taints{CLR_RESET}")

    print(f"\n{CLR_CYAN}{CLR_BOLD}================================================================================")
    print(f"                      SIMULASI MODUL 02 SELESAI")
    print(f"================================================================================{CLR_RESET}")


if __name__ == "__main__":
    run_simulation()
