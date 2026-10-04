#!/usr/bin/env python3
"""
k8s_resilience_pdb_sim.py
Kubernetes Resilience Engine: Pod Disruption Budget (PDB), Eviction & Resource Sizing Simulator.

Author: Principal Cloud & SRE Curriculum Architect
Standard: GEMINI SRE Production Quality
"""

import sys
import time
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class Container:
    name: str
    req_cpu_m: int
    limit_cpu_m: int
    req_mem_mb: int
    limit_mem_mb: int
    allocated_mem_mb: int = 0
    cfs_throttled: bool = False


@dataclass
class Pod:
    name: str
    namespace: str
    labels: Dict[str, str]
    node_name: str
    containers: List[Container]
    status: str = "Pending"  # Pending, Running, Terminating, Evicted, OOMKilled
    ready: bool = False
    priority: int = 0
    qos_class: str = ""
    grace_period_sec: int = 30
    pre_stop_sec: int = 0

    def compute_qos(self):
        req_cpu = sum(c.req_cpu_m for c in self.containers)
        lim_cpu = sum(c.limit_cpu_m for c in self.containers)
        req_mem = sum(c.req_mem_mb for c in self.containers)
        lim_mem = sum(c.limit_mem_mb for c in self.containers)

        if req_cpu == lim_cpu and req_mem == lim_mem and req_cpu > 0 and req_mem > 0:
            self.qos_class = "Guaranteed"
        elif req_cpu > 0 or req_mem > 0:
            self.qos_class = "Burstable"
        else:
            self.qos_class = "BestEffort"


@dataclass
class Node:
    name: str
    capacity_cpu_m: int
    capacity_mem_mb: int
    taints: List[str] = field(default_factory=list)
    cordoned: bool = False
    pods: Dict[str, Pod] = field(default_factory=dict)

    def available_cpu(self) -> int:
        used = sum(sum(c.req_cpu_m for c in p.containers) for p in self.pods.values() if p.status == "Running")
        return self.capacity_cpu_m - used

    def available_mem(self) -> int:
        used = sum(sum(c.req_mem_mb for c in p.containers) for p in self.pods.values() if p.status == "Running")
        return self.capacity_mem_mb - used


@dataclass
class PDB:
    name: str
    namespace: str
    match_labels: Dict[str, str]
    min_available: Optional[int] = None
    max_unavailable: Optional[int] = None


class KubernetesResilienceSimulator:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.pdbs: Dict[str, PDB] = {}
        self.all_pods: Dict[str, Pod] = {}

    def add_node(self, name: str, cpu_cores: int, memory_gb: int, taints: List[str] = None):
        self.nodes[name] = Node(
            name=name,
            capacity_cpu_m=cpu_cores * 1000,
            capacity_mem_mb=memory_gb * 1024,
            taints=taints or []
        )
        print(f"[CLUSTER] Node ditambahkan: {name} (CPU: {cpu_cores} cores, Mem: {memory_gb} GB)")

    def add_pdb(self, name: str, namespace: str, match_labels: Dict[str, str],
                min_available: Optional[int] = None, max_unavailable: Optional[int] = None):
        self.pdbs[name] = PDB(name, namespace, match_labels, min_available, max_unavailable)
        print(f"[PDB REGISTER] PDB: {name} (minAvailable={min_available}, maxUnavailable={max_unavailable})")

    def schedule_pod(self, pod: Pod) -> bool:
        pod.compute_qos()
        for node in self.nodes.values():
            if node.cordoned:
                continue

            # Check Taints
            if node.taints:
                # Simulasi sederhana: Pod belum punya toleration lengkap
                continue

            req_cpu = sum(c.req_cpu_m for c in pod.containers)
            req_mem = sum(c.req_mem_mb for c in pod.containers)

            if node.available_cpu() >= req_cpu and node.available_mem() >= req_mem:
                pod.node_name = node.name
                pod.status = "Running"
                pod.ready = True
                node.pods[pod.name] = pod
                self.all_pods[pod.name] = pod
                print(f"[SCHEDULER] Pod {pod.name} ({pod.qos_class}) dijadwalkan pada {node.name}")
                return True

        print(f"[SCHEDULER ERROR] Pod {pod.name} gagal dijadwalkan (Insufficient resources / Tainted)!")
        pod.status = "Pending"
        self.all_pods[pod.name] = pod
        return False

    def validate_pdb(self, pod: Pod) -> Tuple[bool, str]:
        for pdb in self.pdbs.values():
            if pdb.namespace != pod.namespace:
                continue

            # Cek match labels
            matches = all(pod.labels.get(k) == v for k, v in pdb.match_labels.items())
            if not matches:
                continue

            # Hitung pod yang cocok dengan label PDB di seluruh klaster
            matching_pods = [p for p in self.all_pods.values()
                             if p.namespace == pdb.namespace and
                             all(p.labels.get(k) == v for k, v in pdb.match_labels.items())]

            total_replicas = len(matching_pods)
            ready_pods = sum(1 for p in matching_pods if p.ready and p.status == "Running")

            if pdb.min_available is not None:
                if (ready_pods - 1) < pdb.min_available:
                    return False, f"PDB '{pdb.name}' violation: Butuh minimal {pdb.min_available} Ready, saat ini {ready_pods}."

            if pdb.max_unavailable is not None:
                current_unavailable = total_replicas - ready_pods
                if (current_unavailable + 1) > pdb.max_unavailable:
                    return False, f"PDB '{pdb.name}' violation: Max unavailable {pdb.max_unavailable}, melampaui batas."

        return True, "Allowed"

    def drain_node(self, node_name: str, force: bool = False):
        print(f"\n================ STARTING DRAIN: {node_name} ================")
        if node_name not in self.nodes:
            print(f"[ERROR] Node {node_name} tidak ditemukan.")
            return

        node = self.nodes[node_name]
        node.cordoned = True
        print(f"[CORDON] Node {node_name} ditandai Unschedulable.")

        pods_to_evict = list(node.pods.values())
        failed_evictions = []

        for pod in pods_to_evict:
            allowed, reason = self.validate_pdb(pod)
            if not allowed and not force:
                print(f"[EVICTION REJECTED] Pod {pod.name} DITOLAK oleh API Server. Alasan: {reason}")
                failed_evictions.append(pod)
                continue

            print(f"[EVICTING] Menjalankan eviction untuk Pod: {pod.name}...")
            # Simulasi graceful eviction lifecycle
            if pod.pre_stop_sec > 0:
                print(f"  -> [preStop] Menjalankan preStop hook (sleep {pod.pre_stop_sec}s)...")
                time.sleep(0.2)  # Skala simulasi cepat

            print(f"  -> [SIGTERM] Mengirim sinyal SIGTERM. Menunggu proses selesai...")
            time.sleep(0.1)

            pod.ready = False
            pod.status = "Evicted"
            del node.pods[pod.name]
            print(f"[EVICTED SUCCESS] Pod {pod.name} berhasil digusur dari {node_name}.")

        if failed_evictions:
            print(f"\n[DRAIN FAILED] Node {node_name} TIDAK DAPAT di-drain tuntas karena batasan PDB.")
            print(f"Pod yang tertahan: {[p.name for p in failed_evictions]}")
        else:
            print(f"\n[DRAIN SUCCESS] Seluruh pod pada {node_name} berhasil dievakuasi secara graceful.")

    def simulate_oom_kill(self, pod_name: str, memory_spike_mb: int):
        print(f"\n[SIMULASI MEMORY PRESSURE] Memicu lonjakan memori pada {pod_name}...")
        if pod_name not in self.all_pods:
            print(f"[ERROR] Pod {pod_name} tidak ditemukan.")
            return

        pod = self.all_pods[pod_name]
        for c in pod.containers:
            c.allocated_mem_mb += memory_spike_mb
            print(f"Container '{c.name}': Alokasi = {c.allocated_mem_mb}MiB, Limit = {c.limit_mem_mb}MiB")
            if c.allocated_mem_mb > c.limit_mem_mb:
                print(f"[KERNEL ALERT] cgroup memory threshold exceeded! Invoking OOM Killer...")
                print(f"[OOMKilled] Container '{c.name}' dimatikan paksa (Exit Code 137 / SIGKILL).")
                pod.status = "OOMKilled"
                pod.ready = False
                return

        print(f"[STABLE] Alokasi memori container masih di dalam batas toleransi.")


def run_demo():
    sim = KubernetesResilienceSimulator()

    # 1. Inisialisasi Node Klaster
    sim.add_node("worker-01", cpu_cores=4, memory_gb=8)
    sim.add_node("worker-02", cpu_cores=4, memory_gb=8)

    # 2. Definisikan PDB (Minimal 2 Ready dari total 3 pod)
    sim.add_pdb("payment-pdb", namespace="production",
                match_labels={"app": "payment-api"}, min_available=2)

    # 3. Deploy 3 Pod Payment API
    for i in range(1, 4):
        p = Pod(
            name=f"payment-api-{i}",
            namespace="production",
            labels={"app": "payment-api", "version": "v1"},
            node_name="",
            containers=[
                Container(name="app", req_cpu_m=500, limit_cpu_m=500, req_mem_mb=512, limit_mem_mb=512)
            ],
            pre_stop_sec=5
        )
        sim.schedule_pod(p)

    # 4. Uji Skenario Drain: Mencoba drain worker-01 yang menampung pod
    target_node = "worker-01"
    print(f"\nStatus Pod di {target_node}: {[p.name for p in sim.nodes[target_node].pods.values()]}")
    
    # Jalankan Drain
    sim.drain_node(target_node)

    # 5. Simulasi OOMKilled
    surviving_pod = [p for p in sim.all_pods.values() if p.status == "Running"][0]
    sim.simulate_oom_kill(surviving_pod.name, memory_spike_mb=600)


if __name__ == "__main__":
    run_demo()