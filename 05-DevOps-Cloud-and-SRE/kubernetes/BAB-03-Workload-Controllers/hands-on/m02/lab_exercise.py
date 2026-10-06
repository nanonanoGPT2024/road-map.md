#!/usr/bin/env python3
"""
Kubernetes Production Workload Controllers Simulator
BAB-03: Workload Controllers (Deployment, StatefulSet, DaemonSet, Job)

Lab Exercise Mandiri - Modul 02
Simulasi interaktif rekonsiliasi kontroler workload Kubernetes tingkat lanjut.
Standard Library Python 3 only (runnable tanpa pip install external).
"""

import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# ANSI Color Codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"

def print_header(title: str):
    width = 75
    print(f"\n{Color.CYAN}{'=' * width}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}  {title.center(width - 4)}{Color.RESET}")
    print(f"{Color.CYAN}{'=' * width}{Color.RESET}\n")

def print_event(source: str, message: str, level: str = "INFO"):
    color = Color.GREEN if level == "INFO" else (Color.YELLOW if level == "WARN" else Color.RED)
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{Color.DIM}{timestamp}{Color.RESET}] {color}[{level:4}]{Color.RESET} {Color.BOLD}[{source:15}]{Color.RESET} {message}")

class PodPhase(Enum):
    PENDING = "Pending"
    CONTAINER_CREATING = "ContainerCreating"
    RUNNING = "Running"
    TERMINATING = "Terminating"
    COMPLETED = "Completed"
    FAILED = "Failed"

@dataclass
class Pod:
    name: str
    namespace: str
    image: str
    phase: PodPhase = PodPhase.PENDING
    node: Optional[str] = None
    ip: Optional[str] = None
    ready: bool = False
    restarts: int = 0
    pvc: Optional[str] = None

class DeploymentSimulator:
    """Simulasi Deployment Controller dengan RollingUpdate Strategy (maxSurge=1, maxUnavailable=0)"""
    def __init__(self, name: str, replicas: int, image_v1: str):
        self.name = name
        self.replicas = replicas
        self.current_image = image_v1
        self.rs_v1 = [Pod(f"{name}-rs1-{i:03x}", "production", image_v1, PodPhase.RUNNING, f"worker-0{i+1}", f"10.244.1.{10+i}", True) for i in range(replicas)]
        self.rs_v2: List[Pod] = []

    def render_pods(self):
        print(f"\n{Color.BOLD}Status Pods Saat Ini (Deployment: {self.name}):{Color.RESET}")
        all_pods = self.rs_v1 + self.rs_v2
        print(f"{'NAME':<24} {'IMAGE':<15} {'NODE':<12} {'PHASE':<18} {'READY'}")
        print("-" * 75)
        for p in all_pods:
            phase_color = Color.GREEN if p.phase == PodPhase.RUNNING and p.ready else (Color.RED if p.phase == PodPhase.TERMINATING else Color.YELLOW)
            ready_str = f"{Color.GREEN}1/1{Color.RESET}" if p.ready else f"{Color.RED}0/1{Color.RESET}"
            print(f"{p.name:<24} {p.image:<15} {str(p.node):<12} {phase_color}{p.phase.value:<18}{Color.RESET} {ready_str}")
        print("-" * 75)

    def rolling_update(self, new_image: str):
        print_event("DeploymentCtrl", f"Memulai RollingUpdate dari {self.current_image} -> {new_image} (maxSurge=1, maxUnavailable=0)")
        step = 1
        
        while len(self.rs_v2) < self.replicas or len(self.rs_v1) > 0:
            print(f"\n{Color.BOLD}{Color.MAGENTA}--- Tahap {step} Rollout ---{Color.RESET}")
            
            # Step A: Scale up new ReplicaSet (Surge 1)
            if len(self.rs_v2) < self.replicas:
                idx = len(self.rs_v2)
                new_pod = Pod(f"{self.name}-rs2-{idx:03x}", "production", new_image, PodPhase.CONTAINER_CREATING, f"worker-0{(idx%3)+1}")
                self.rs_v2.append(new_pod)
                print_event("Kubelet", f"Scheduling & Creating Pod baru: {new_pod.name} ({new_image}) pada {new_pod.node}")
                self.render_pods()
                time.sleep(0.8)
                
                # Readiness probe passing
                new_pod.phase = PodPhase.RUNNING
                new_pod.ready = True
                new_pod.ip = f"10.244.2.{20+idx}"
                print_event("EndpointCtrl", f"ReadinessProbe PASS! Pod {new_pod.name} ditambahkan ke Endpoints Service.")
                self.render_pods()
                time.sleep(0.8)

            # Step B: Scale down old ReplicaSet
            if self.rs_v1:
                terminating_pod = self.rs_v1.pop()
                terminating_pod.phase = PodPhase.TERMINATING
                terminating_pod.ready = False
                print_event("EndpointCtrl", f"Pod {terminating_pod.name} dicabut dari Endpoints Service (SIGTERM dikirim).", "WARN")
                self.render_pods()
                time.sleep(0.8)
                print_event("Kubelet", f"Grace period 30s usai. Pod {terminating_pod.name} berhasil dihapus.")
                self.render_pods()
                time.sleep(0.6)

            step += 1

        self.current_image = new_image
        print_event("DeploymentCtrl", f"{Color.GREEN}Rollout berhasil! 100% traffic dialihkan ke versi {new_image} dengan zero downtime.{Color.RESET}")

class StatefulSetSimulator:
    """Simulasi StatefulSet Controller (Ordered Ready, Stable Network ID & Dedicated PVC)"""
    def __init__(self, name: str, replicas: int):
        self.name = name
        self.replicas = replicas
        self.pods: List[Pod] = []

    def scale_up(self):
        print_event("StatefulSetCtrl", f"Scaling StatefulSet '{self.name}' secara deterministik (Ordered: 0 -> {self.replicas-1})...")
        for i in range(len(self.pods), self.replicas):
            pod_name = f"{self.name}-{i}"
            pvc_name = f"data-{self.name}-{i}"
            print_event("PV-Controller", f"Provisioning persistent volume claim '{pvc_name}' (ReadWriteOnce - 10Gi)")
            time.sleep(0.5)
            
            pod = Pod(name=pod_name, namespace="production", image="postgres:15-alpine", phase=PodPhase.CONTAINER_CREATING, node=f"db-node-0{(i%2)+1}", pvc=pvc_name)
            self.pods.append(pod)
            print_event("Kubelet", f"Attaching Volume {pvc_name} ke {pod_name}...")
            time.sleep(0.6)
            
            pod.phase = PodPhase.RUNNING
            pod.ready = True
            pod.ip = f"10.244.3.{50+i}"
            print_event("StatefulSetCtrl", f"Pod '{pod_name}' Ready! Stateful network identity: {pod_name}.db-headless.production.svc.cluster.local")
            time.sleep(0.5)

    def simulate_pod_recovery(self, pod_index: int):
        if pod_index >= len(self.pods):
            print(f"{Color.RED}Index pod tidak valid!{Color.RESET}")
            return
        failed_pod = self.pods[pod_index]
        print_event("NodeManager", f"Node hardware fault terdeteksi pada node {failed_pod.node}! Pod {failed_pod.name} dievakuasi.", "CRIT")
        failed_pod.phase = PodPhase.FAILED
        failed_pod.ready = False
        time.sleep(0.8)
        
        print_event("StatefulSetCtrl", f"Membuat ulang pod dengan identitas dan PVC yang sama: {failed_pod.name}...")
        time.sleep(0.7)
        failed_pod.phase = PodPhase.RUNNING
        failed_pod.ready = True
        failed_pod.node = "db-node-03-spare"
        failed_pod.restarts += 1
        print_event("PV-Controller", f"Volume '{failed_pod.pvc}' berhasil di-reattach ke {failed_pod.name} pada {failed_pod.node}.")
        print_event("StatefulSetCtrl", f"{Color.GREEN}Pod {failed_pod.name} pulih sempurna dengan data persisten utuh!{Color.RESET}")

    def render(self):
        print(f"\n{Color.BOLD}Topology StatefulSet ({self.name}):{Color.RESET}")
        print(f"{'ORDINAL POD':<18} {'PVC ATTACHED':<18} {'NODE':<16} {'STATUS'}")
        print("-" * 75)
        for p in self.pods:
            status = f"{Color.GREEN}Running (Ready){Color.RESET}" if p.ready else f"{Color.RED}{p.phase.value}{Color.RESET}"
            print(f"{p.name:<18} {str(p.pvc):<18} {str(p.node):<16} {status}")
        print("-" * 75)

class DaemonSetSimulator:
    """Simulasi DaemonSet Controller (1 Pod per Eligible Node)"""
    def __init__(self, name: str, nodes: List[str]):
        self.name = name
        self.nodes = list(nodes)
        self.pods: Dict[str, Pod] = {}
        self.reconcile()

    def reconcile(self):
        for node in self.nodes:
            if node not in self.pods:
                pod_name = f"{self.name}-{random.randint(1000, 9999)}"
                p = Pod(name=pod_name, namespace="kube-system", image="prom/node-exporter:v1.6.0", phase=PodPhase.RUNNING, node=node, ready=True)
                self.pods[node] = p
                print_event("DaemonSetCtrl", f"Menugaskan daemon pod '{pod_name}' ke node baru: {node}")

    def add_node(self, new_node: str):
        print_event("NodeCtrl", f"Node baru bergabung ke cluster: {new_node}")
        self.nodes.append(new_node)
        time.sleep(0.5)
        self.reconcile()

    def drain_node(self, node_to_remove: str):
        if node_to_remove in self.pods:
            print_event("NodeCtrl", f"Draining & Cordoning node: {node_to_remove}", "WARN")
            del self.pods[node_to_remove]
            self.nodes.remove(node_to_remove)
            time.sleep(0.5)
            print_event("DaemonSetCtrl", f"Daemon pod pada node {node_to_remove} dibersihkan.")

    def render(self):
        print(f"\n{Color.BOLD}Topology DaemonSet ({self.name}):{Color.RESET}")
        print(f"{'NODE NAME':<20} {'DAEMON POD':<25} {'STATUS'}")
        print("-" * 75)
        for node, pod in self.pods.items():
            print(f"{node:<20} {pod.name:<25} {Color.GREEN}Healthy (Node Metrics Monitored){Color.RESET}")
        print("-" * 75)

class JobSimulator:
    """Simulasi Kubernetes Job Controller (completions=3, parallelism=2, backoffLimit=2)"""
    def __init__(self, name: str, completions: int = 3, parallelism: int = 2):
        self.name = name
        self.completions = completions
        self.parallelism = parallelism

    def execute(self):
        print_event("JobController", f"Memulai Batch Job '{self.name}' (Target: {self.completions} completions, Parallelism: {self.parallelism})")
        completed = 0
        iteration = 1
        
        while completed < self.completions:
            batch_count = min(self.parallelism, self.completions - completed)
            print(f"\n{Color.BLUE}>> Menjalankan worker batch ke-{iteration} ({batch_count} pod paralel)...{Color.RESET}")
            
            workers = []
            for b in range(batch_count):
                worker_name = f"{self.name}-batch-{iteration}-{b}"
                workers.append(worker_name)
                print_event("Kubelet", f"Worker pod '{worker_name}' mulai menjalankan komputasi analitik...")
            
            time.sleep(1.0)
            
            for w in workers:
                # Simulasi retry jika ada fault acak kecil
                if random.random() < 0.2:
                    print_event("Kubelet", f"Worker '{w}' OOMKilled! Restarting pod sesuai backoffLimit...", "WARN")
                    time.sleep(0.5)
                print_event("JobController", f"Worker '{w}' exit code 0: Succeeded.")
                completed += 1
            
            iteration += 1

        print_event("JobController", f"{Color.GREEN}Job '{self.name}' SELESAI ({completed}/{self.completions} task pods sukses). Controller marks Job as Complete.{Color.RESET}")

def run_automated_suite():
    print_header("AUTOMATED PRODUCTION CONTROLLER VERIFICATION SUITE")
    
    # 1. Deployment
    print(f"\n{Color.BG_BLUE}{Color.WHITE} [TEST 1] DEPLOYMENT ZERO-DOWNTIME ROLLING UPDATE {Color.RESET}")
    dep = DeploymentSimulator("payment-service", 3, "payment:v1.0.0")
    dep.render_pods()
    dep.rolling_update("payment:v2.0.0")
    
    # 2. StatefulSet
    print(f"\n{Color.BG_BLUE}{Color.WHITE} [TEST 2] STATEFULSET ORDERED ROLLOUT & RECOVERY {Color.RESET}")
    sts = StatefulSetSimulator("redis-cluster", 3)
    sts.scale_up()
    sts.render()
    sts.simulate_pod_recovery(1)
    sts.render()

    # 3. DaemonSet
    print(f"\n{Color.BG_BLUE}{Color.WHITE} [TEST 3] DAEMONSET AUTO-SCHEDULING ON NODE TOPOLOGY {Color.RESET}")
    ds = DaemonSetSimulator("fluentbit-logger", ["k8s-node-01", "k8s-node-02", "k8s-node-03"])
    ds.render()
    ds.add_node("k8s-node-04-gpu")
    ds.render()

    # 4. Job
    print(f"\n{Color.BG_BLUE}{Color.WHITE} [TEST 4] BATCH JOB PARALLEL RECONCILIATION {Color.RESET}")
    job = JobSimulator("db-migration-etl", completions=4, parallelism=2)
    job.execute()

    print(f"\n{Color.BG_GREEN}{Color.WHITE} SELURUH CONTROLLER RECONCILIATION LOOP BERHASIL DIUJI! {Color.RESET}\n")

def interactive_menu():
    dep = DeploymentSimulator("cart-api", 3, "cart-api:1.0.0")
    sts = StatefulSetSimulator("mongo-replica", 3)
    sts.scale_up()
    ds = DaemonSetSimulator("node-agent", ["worker-alpha", "worker-beta"])

    while True:
        print_header("KUBERNETES WORKLOAD CONTROLLERS LAB INTERAKTIF")
        print(f"{Color.CYAN}1.{Color.RESET} Jalankan Deployment Rolling Update (Zero-Downtime Rollout)")
        print(f"{Color.CYAN}2.{Color.RESET} Jalankan StatefulSet Self-Healing & Stable Identity Test")
        print(f"{Color.CYAN}3.{Color.RESET} Tambah Node Baru untuk Menguji DaemonSet Auto-Injection")
        print(f"{Color.CYAN}4.{Color.RESET} Eksekusi Batch Job dengan Parallelism & Retry")
        print(f"{Color.CYAN}5.{Color.RESET} Jalankan Full Automated Verification Suite")
        print(f"{Color.CYAN}6.{Color.RESET} Keluar (Exit)")
        
        choice = input(f"\n{Color.BOLD}Pilih skenario simulasi (1-6): {Color.RESET}").strip()
        
        if choice == "1":
            version = input("Masukkan versi image baru (contoh: cart-api:2.1.0): ").strip() or "cart-api:2.0.0"
            dep.rolling_update(version)
        elif choice == "2":
            sts.render()
            sts.simulate_pod_recovery(0)
            sts.render()
        elif choice == "3":
            new_node = f"worker-edge-{random.randint(10, 99)}"
            ds.add_node(new_node)
            ds.render()
        elif choice == "4":
            j = JobSimulator(f"data-aggregator-{random.randint(100, 999)}", completions=3, parallelism=2)
            j.execute()
        elif choice == "5":
            run_automated_suite()
        elif choice == "6" or choice.lower() == "q":
            print(f"\n{Color.GREEN}Terima kasih! Lab Workload Controllers selesai.{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}")

if __name__ == "__main__":
    # Jika dipanggil dengan argumen --auto atau non-interaktif
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_automated_suite()
    else:
        try:
            interactive_menu()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Color.YELLOW}Simulasi dihentikan oleh user.{Color.RESET}\n")
            sys.exit(0)
