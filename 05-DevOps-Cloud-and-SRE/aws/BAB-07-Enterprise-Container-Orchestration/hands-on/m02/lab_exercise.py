#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Arsitektur Enterprise Container Orchestration (AWS ECS & EKS)
BAB-07: Enterprise Container Orchestration
Platform: Python 3 runnable mandiri tanpa dependensi eksternal.
"""

import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# --- ANSI Terminal Color Palette ---
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
    BG_DARK = "\033[40m"


def header(text: str):
    print(f"\n{Color.BOLD}{Color.BG_BLUE}{Color.WHITE} === {text} === {Color.RESET}\n")


def status_badge(status: str, ok: bool = True):
    badge = f"{Color.GREEN}[✓ {status}]{Color.RESET}" if ok else f"{Color.RED}[✗ {status}]{Color.RESET}"
    return badge


# --- Domain Data Models ---

class DeploymentStrategy(Enum):
    ROLLING_UPDATE = "RollingUpdate"
    BLUE_GREEN_CANARY = "BlueGreenCanary"


@dataclass
class ContainerTask:
    task_id: str
    version: str
    target_group: str  # blue or green
    traffic_weight: int
    health_status: str
    cpu_utilization: float
    memory_mb: int


@dataclass
class KarpenterNode:
    node_id: str
    instance_type: str
    capacity_type: str  # spot or on-demand
    zone: str
    allocated_cpu_m: int
    allocated_mem_mi: int
    pods_running: int


# --- Simulation Engines ---

class ECSEnterpriseClusterSimulator:
    """Simulasi ECS Fargate Cluster dengan Blue/Green CodeDeploy, Target Tracking & Circuit Breaker."""

    def __init__(self, cluster_name: str = "prod-core-ecs"):
        self.cluster_name = cluster_name
        self.current_version = "v1.4.2"
        self.desired_tasks = 4
        self.tasks: List[ContainerTask] = [
            ContainerTask(f"task-{i:03d}", self.current_version, "tg-blue", 100, "HEALTHY", 24.5, 512)
            for i in range(1, self.desired_tasks + 1)
        ]
        self.service_connect_healthy = True

    def display_topology(self):
        print(f"{Color.CYAN}Cluster:{Color.RESET} {Color.BOLD}{self.cluster_name}{Color.RESET} (AWS Fargate Serverless)")
        print(f"{Color.CYAN}Service Connect Proxy:{Color.RESET} Envoy Sidecar Active (mTLS strict mode)")
        print(f"{Color.CYAN}Active Desired Count:{Color.RESET} {self.desired_tasks} tasks\n")
        print(f"{Color.BOLD}{'TASK ID':<12} {'VERSION':<10} {'TARGET GROUP':<14} {'WEIGHT':<8} {'HEALTH':<12} {'CPU%':<8} {'MEM(MB)'}{Color.RESET}")
        print("-" * 75)
        for t in self.tasks:
            h_color = Color.GREEN if t.health_status == "HEALTHY" else Color.RED
            print(f"{t.task_id:<12} {t.version:<10} {t.target_group:<14} {t.traffic_weight:<8} {h_color}{t.health_status:<12}{Color.RESET} {t.cpu_utilization:<8.1f} {t.memory_mb}")
        print("-" * 75)

    def trigger_blue_green_canary(self, new_version: str = "v1.5.0"):
        header(f"CodeDeploy Blue/Green Canary Deployment: {self.current_version} -> {new_version}")
        print(f"{Color.YELLOW}[PHASE 1]{Color.RESET} Provisioning Green Target Group Tasks (Fargate Provisioning)...")
        time.sleep(1)

        green_tasks = [
            ContainerTask(f"task-{i:03d}-new", new_version, "tg-green", 0, "INITIALIZING", 12.0, 512)
            for i in range(5, 5 + self.desired_tasks)
        ]
        for gt in green_tasks:
            print(f"  -> Spawned {gt.task_id} on private subnet az-{random.choice(['1a', '1b', '1c'])}... {Color.GREEN}READY{Color.RESET}")
            gt.health_status = "HEALTHY"

        print(f"\n{Color.YELLOW}[PHASE 2]{Color.RESET} ALB Listener Rule Shift: Canary 10% Traffic ke tg-green (Hold 3 detik)")
        time.sleep(1)
        print(f"  {status_badge('Canary Shifted')} ALB Route: 90% -> tg-blue | 10% -> tg-green")
        print(f"  {Color.CYAN}Evaluating CloudWatch Rollback Alarms (5xx Rate, Latency P99, Task CrashCount)...{Color.RESET}")
        
        # Simulasi synthetic check
        synthetic_error_rate = 0.01
        print(f"  -> Synthetic Traffic Error Rate: {Color.GREEN}{synthetic_error_rate}%{Color.RESET} (Threshold: < 1.0%)")
        time.sleep(1)

        print(f"\n{Color.YELLOW}[PHASE 3]{Color.RESET} Shift 100% Traffic ke tg-green & Drain tg-blue Tasks")
        time.sleep(1)
        for gt in green_tasks:
            gt.traffic_weight = 100
        self.tasks = green_tasks
        self.current_version = new_version
        print(f"  {status_badge('Cutover Complete')} All traffic routed to target group {Color.GREEN}tg-green{Color.RESET}!")
        print(f"  -> De-registering tg-blue legacy tasks (deregistration_delay: 30s)... Done.")


class EKSKarpenterAutoscalerSimulator:
    """Simulasi EKS Autoscaling menggunakan Karpenter (Just-in-Time Node Provisioning)."""

    def __init__(self):
        self.nodes: List[KarpenterNode] = [
            KarpenterNode("ip-10-0-12-44.ec2", "c6i.xlarge", "spot", "ap-southeast-1a", 2400, 4800, 18),
            KarpenterNode("ip-10-0-28-19.ec2", "c6i.xlarge", "spot", "ap-southeast-1b", 2100, 4100, 15),
        ]

    def display_karpenter_state(self):
        header("EKS Karpenter NodePool Controller State")
        print(f"{Color.BOLD}{'NODE NAME':<22} {'INSTANCE TYPE':<14} {'CAPACITY':<10} {'ZONE':<16} {'CPU (m)':<10} {'MEM (Mi)':<10} {'PODS'}{Color.RESET}")
        print("-" * 90)
        for n in self.nodes:
            cap_color = Color.MAGENTA if n.capacity_type == "spot" else Color.CYAN
            print(f"{n.node_id:<22} {n.instance_type:<14} {cap_color}{n.capacity_type:<10}{Color.RESET} {n.zone:<16} {n.allocated_cpu_m:<10} {n.allocated_mem_mi:<10} {n.pods_running}")
        print("-" * 90)

    def simulate_traffic_burst(self, incoming_pods: int = 25):
        header(f"Traffic Burst Alert: +{incoming_pods} Pods Pending Scheduling")
        print(f"{Color.YELLOW}[Karpenter Event]{Color.RESET} Detecting unschedulable pods due to InsufficientCPU in existing NodePool...")
        time.sleep(1)
        
        # Bin-packing calculation
        print(f"  -> Bin-packing solver executing: selecting optimal instance types based on NodePool limits & pricing...")
        provisioned_instance = "c6i.2xlarge"
        selected_zone = "ap-southeast-1c"
        print(f"  -> Selected optimal Spot candidate: {Color.BOLD}{provisioned_instance}{Color.RESET} on {selected_zone} (Cost saving: 72% vs On-Demand)")
        
        new_node = KarpenterNode(
            f"ip-10-0-{random.randint(30, 90)}-{random.randint(10, 99)}.ec2",
            provisioned_instance,
            "spot",
            selected_zone,
            incoming_pods * 250,
            incoming_pods * 512,
            incoming_pods
        )
        time.sleep(1)
        print(f"  -> Launching EC2 instance via fleet API (EC2 Fleet instantaneous launch)...")
        print(f"  -> Node initialized and joined EKS cluster via AWS IAM IRSA & aws-auth... {Color.GREEN}READY{Color.RESET}")
        self.nodes.append(new_node)
        print(f"\n{status_badge('Autoscale Success')} All {incoming_pods} pods scheduled without cluster-autoscaler cooling delay.")


class ServiceMeshCircuitBreaker:
    """Simulasi Envoy Service Connect / App Mesh Circuit Breaker & Outlier Detection."""

    def run_simulation(self):
        header("Service Connect: Envoy Sidecar Circuit Breaker Simulation")
        print("Simulasi downstream call dari Service-Order ke Service-Payment...")
        print("Threshold Circuit Breaker: Max Consecutive 5xx Errors = 3 | Outlier Ejection = 30s\n")
        
        consecutive_failures = 0
        circuit_open = False

        for req_id in range(1, 11):
            time.sleep(0.4)
            if circuit_open:
                print(f"Request #{req_id:02d}: {Color.RED}[CIRCUIT OPEN - SHORT CIRCUITED]{Color.RESET} Request ditolak langsung oleh sidecar Envoy lokal (Fast-Fail)")
                continue

            # Injeksi failure pada request 4, 5, 6
            if 4 <= req_id <= 6:
                consecutive_failures += 1
                print(f"Request #{req_id:02d}: {Color.YELLOW}[503 Service Unavailable]{Color.RESET} Backend payment timeout. Consecutive errors: {consecutive_failures}")
                if consecutive_failures >= 3:
                    circuit_open = True
                    print(f"  {Color.RED}{Color.BOLD}>>> OUTLIER DETECTION TRIGGERED! Ejecting faulty payment instance from pool <<<{Color.RESET}")
            else:
                print(f"Request #{req_id:02d}: {Color.GREEN}[200 OK]{Color.RESET} Latency: {random.randint(18, 45)}ms | Envoy mTLS Handshake Verified")


# --- Main Interactive Menu Loop ---

def main():
    ecs_sim = ECSEnterpriseClusterSimulator()
    eks_sim = EKSKarpenterAutoscalerSimulator()
    mesh_sim = ServiceMeshCircuitBreaker()

    while True:
        print(f"\n{Color.BOLD}{Color.WHITE}===================================================================={Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN} AWS ENTERPRISE CONTAINER ORCHESTRATION LAB CONSOLE (BAB-07) {Color.RESET}")
        print(f"{Color.BOLD}{Color.WHITE}===================================================================={Color.RESET}")
        print(f" {Color.YELLOW}1.{Color.RESET} Tampilkan Topologi & Status Cluster ECS Fargate")
        print(f" {Color.YELLOW}2.{Color.RESET} Jalankan ECS Blue/Green Canary Deployment (CodeDeploy Engine)")
        print(f" {Color.YELLOW}3.{Color.RESET} Tampilkan State NodePool & Node EKS Karpenter")
        print(f" {Color.YELLOW}4.{Color.RESET} Simulasikan Lonjakan Beban Pod & JIT Karpenter Spot Provisioning")
        print(f" {Color.YELLOW}5.{Color.RESET} Simulasikan Service Connect Circuit Breaking & Outlier Detection")
        print(f" {Color.YELLOW}6.{Color.RESET} Jalankan Audit Checklist Arsitektur Produksi (Semua Komponen)")
        print(f" {Color.YELLOW}7.{Color.RESET} Keluar (Exit)")
        print(f"{Color.BOLD}{Color.WHITE}===================================================================={Color.RESET}")
        
        choice = input(f"{Color.BOLD}Pilih opsi menu (1-7): {Color.RESET}").strip()

        if choice == "1":
            ecs_sim.display_topology()
        elif choice == "2":
            ecs_sim.trigger_blue_green_canary("v1.5.0-enterprise")
            ecs_sim.display_topology()
        elif choice == "3":
            eks_sim.display_karpenter_state()
        elif choice == "4":
            eks_sim.simulate_traffic_burst(30)
            eks_sim.display_karpenter_state()
        elif choice == "5":
            mesh_sim.run_simulation()
        elif choice == "6":
            header("Audit Kesiapan Arsitektur Container Produksi AWS")
            checklist = [
                ("Multi-AZ Task & Node Distribution (min 3 AZs)", True),
                ("Fargate Task IAM Roles terpisah dari Task Execution Roles", True),
                ("EKS Pod Identity / IRSA (Zero long-lived IAM keys)", True),
                ("Container Insights & CloudWatch Metric Filters Terpasang", True),
                ("VPC Endpoints (PrivateLink) untuk ECR, S3, CloudWatch, SecretsManager", True),
                ("Karpenter Node Expiration & Spot Interruption Graceful Handling", True),
            ]
            for item, ok in checklist:
                print(f"  {status_badge('PASS' if ok else 'FAIL', ok)} {item}")
            print(f"\n{Color.GREEN}{Color.BOLD}Status Skor Audit: 100% PRODUCTION READY{Color.RESET}")
        elif choice == "7":
            print(f"\n{Color.GREEN}Terima kasih telah menyelesaikan simulasi lab BAB-07!{Color.RESET}\n")
            sys.exit(0)
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 1-7.{Color.RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}Sesi lab dihentikan oleh pengguna.{Color.RESET}")
        sys.exit(0)
