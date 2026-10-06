#!/usr/bin/env python3
"""
Lab Exercise M02: Kubernetes Packaging, GitOps, & Troubleshooting Engine
========================================================================
Bab 10: Packaging, GitOps, dan Troubleshooting Produksi

Simulasi interaktif menyeluruh untuk:
1. Helm Packaging & Value Overrides templating engine.
2. GitOps Reconciler loop (ArgoCD/Flux): State diff, drift detection, self-healing.
3. K8s Diagnostic & Troubleshooting triage:
   - CrashLoopBackOff & Exit Code analysis (137 OOMKilled vs 1 Runtime Error)
   - ImagePullBackOff & Registry secret diagnosis
   - Service Endpoint Mismatch (label selector disalignment)
   - Ephemeral Debug Container Injection (`kubectl debug`)
"""

import sys
import time
import json
import random
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

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
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{Color.CYAN}{Color.BOLD}{'=' * 76}{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}  >> {title.upper()} <<{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}{'=' * 76}{Color.RESET}\n")


def status_badge(status: str) -> str:
    mapping = {
        "HEALTHY": f"{Color.GREEN}{Color.BOLD}[✓ HEALTHY]{Color.RESET}",
        "SYNCED": f"{Color.GREEN}{Color.BOLD}[✓ SYNCED]{Color.RESET}",
        "OutOfSync": f"{Color.YELLOW}{Color.BOLD}[⚠ OUT_OF_SYNC]{Color.RESET}",
        "CrashLoopBackOff": f"{Color.RED}{Color.BOLD}[✖ CrashLoopBackOff]{Color.RESET}",
        "OOMKilled": f"{Color.RED}{Color.BOLD}[✖ OOMKilled (Exit 137)]{Color.RESET}",
        "ImagePullBackOff": f"{Color.RED}{Color.BOLD}[✖ ImagePullBackOff]{Color.RESET}",
        "PENDING": f"{Color.YELLOW}[⏳ PENDING]{Color.RESET}",
        "RUNNING": f"{Color.GREEN}[● RUNNING]{Color.RESET}",
    }
    return mapping.get(status, f"{Color.WHITE}[{status}]{Color.RESET}")


# --- Domain Data Structures ---
@dataclass
class PodSpec:
    name: str
    image: str
    cpu_limit: str
    memory_limit: str
    labels: Dict[str, str]
    status: str = "RUNNING"
    restart_count: int = 0
    exit_code: int = 0
    events: List[str] = field(default_factory=list)


@dataclass
class ServiceSpec:
    name: str
    port: int
    target_port: int
    selector: Dict[str, str]
    endpoints: List[str] = field(default_factory=list)


@dataclass
class GitOpsApplication:
    name: str
    repo_url: str
    target_revision: str
    path: str
    sync_policy: str  # Automated or Manual
    desired_replicas: int
    live_replicas: int
    sync_status: str = "SYNCED"
    health_status: str = "HEALTHY"


# --- Simulation Components ---
class ClusterSimulator:
    def __init__(self):
        self.namespace = "production-ecommerce"
        self.gitops_app = GitOpsApplication(
            name="checkout-service-app",
            repo_url="git@github.com:enterprise/gitops-manifests.git",
            target_revision="commit-sha-9f82d1",
            path="clusters/production/checkout-service",
            sync_policy="Automated (Self-Heal: ON)",
            desired_replicas=3,
            live_replicas=3,
        )
        self.pods: Dict[str, PodSpec] = {
            "checkout-pod-1": PodSpec(
                name="checkout-pod-1",
                image="registry.internal/apps/checkout:v2.4.1",
                cpu_limit="500m",
                memory_limit="256Mi",
                labels={"app": "checkout", "tier": "backend", "version": "v2.4.1"},
            ),
            "checkout-pod-2": PodSpec(
                name="checkout-pod-2",
                image="registry.internal/apps/checkout:v2.4.1",
                cpu_limit="500m",
                memory_limit="256Mi",
                labels={"app": "checkout", "tier": "backend", "version": "v2.4.1"},
            ),
            "checkout-pod-3": PodSpec(
                name="checkout-pod-3",
                image="registry.internal/apps/checkout:v2.4.1",
                cpu_limit="500m",
                memory_limit="256Mi",
                labels={"app": "checkout", "tier": "backend", "version": "v2.4.1"},
            ),
        }
        self.service = ServiceSpec(
            name="checkout-svc",
            port=80,
            target_port=8080,
            selector={"app": "checkout", "tier": "backend"},
            endpoints=["10.244.1.14:8080", "10.244.2.22:8080", "10.244.3.09:8080"],
        )

    def print_overview(self) -> None:
        header(f"Cluster State: Namespace [{self.namespace}]")
        print(f"{Color.BOLD}GitOps Application (ArgoCD / Flux CDR):{Color.RESET}")
        print(f"  App Name       : {self.gitops_app.name}")
        print(f"  Git Source     : {self.gitops_app.repo_url} @ {self.gitops_app.target_revision}")
        print(f"  Sync Status    : {status_badge(self.gitops_app.sync_status)}")
        print(f"  Health Status  : {status_badge(self.gitops_app.health_status)}")
        print(f"  Sync Policy    : {Color.CYAN}{self.gitops_app.sync_policy}{Color.RESET}\n")

        print(f"{Color.BOLD}Workload Pods:{Color.RESET}")
        print(f"{'Pod Name':<20} {'Image Tag':<30} {'Restarts':<10} {'Status'}")
        print("-" * 76)
        for pod in self.pods.values():
            print(f"{pod.name:<20} {pod.image:<30} {pod.restart_count:<10} {status_badge(pod.status)}")

        print(f"\n{Color.BOLD}Service & Endpoints Routing:{Color.RESET}")
        print(f"  Service Name   : {self.service.name} (Port: {self.service.port} -> {self.service.target_port})")
        print(f"  Selector       : {json.dumps(self.service.selector)}")
        print(f"  Active EP List : {Color.GREEN if self.service.endpoints else Color.RED}{self.service.endpoints or 'No endpoints matched!'}{Color.RESET}\n")

    # Module 1: Helm & Kustomize Packaging
    def run_packaging_demo(self) -> None:
        header("Module 1: Helm Packaging & Value Overrides Engine")
        print(f"{Color.YELLOW}Simulating Helm Chart Template Resolution...{Color.RESET}")
        chart_yaml = """apiVersion: v2
name: checkout-microservice
version: 1.2.0
appVersion: "2.4.1"
dependencies:
  - name: common-auth-helper
    version: "^0.4.0"
    repository: "https://charts.internal.corp"
"""
        values_yaml = """replicaCount: 3
image:
  repository: registry.internal/apps/checkout
  tag: v2.4.1
  pullPolicy: IfNotPresent
resources:
  limits:
    cpu: 500m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 64Mi
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 75
"""
        print(f"\n{Color.BLUE}--- [Chart.yaml Definition] ---{Color.RESET}")
        print(chart_yaml.strip())
        print(f"\n{Color.BLUE}--- [values.yaml Defaults] ---{Color.RESET}")
        print(values_yaml.strip())

        print(f"\n{Color.MAGENTA}Executing: `helm template checkout ./chart -f values-prod.yaml --set replicaCount=5`{Color.RESET}")
        for i in range(3):
            time.sleep(0.3)
            print(f"  {Color.DIM}Parsing AST template [templates/deployment.yaml] ... ({i+1}/3){Color.RESET}")

        print(f"\n{Color.GREEN}✓ Rendered Kubernetes Manifest with Custom Overrides:{Color.RESET}")
        rendered_snippet = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout-checkout-microservice
  labels:
    app.kubernetes.io/name: checkout-microservice
    app.kubernetes.io/instance: checkout
spec:
  replicas: 5  # <-- Overridden from CLI --set
  selector:
    matchLabels:
      app: checkout
      tier: backend
  template:
    spec:
      containers:
        - name: checkout
          image: "registry.internal/apps/checkout:v2.4.1"
          resources:
            limits:
              memory: 256Mi
"""
        print(rendered_snippet)

    # Module 2: GitOps Reconciliation Loop
    def run_gitops_reconciler_demo(self) -> None:
        header("Module 2: GitOps Controller Reconciliation (ArgoCD/Flux)")
        print("GitOps state machine tracks Desired State (Git Repo) vs Live State (K8s API).")
        print(f"{Color.CYAN}Step 1: Normal State Checking...{Color.RESET}")
        print(f"  Git Commit Desired Replicas: {self.gitops_app.desired_replicas}")
        print(f"  Live K8s Current Replicas  : {self.gitops_app.live_replicas}")
        print(f"  Status: {status_badge('SYNCED')} {status_badge('HEALTHY')}\n")

        print(f"{Color.YELLOW}Step 2: Simulating Configuration Drift (Manual kubectl edit on Cluster){Color.RESET}")
        print(f"  Admin ran: `kubectl scale deployment/checkout-service --replicas=1` out-of-band!")
        self.gitops_app.live_replicas = 1
        self.gitops_app.sync_status = "OutOfSync"
        print(f"  Live K8s Current Replicas  : {self.gitops_app.live_replicas}")
        print(f"  Drift Detected! Diff: Desired (3) != Live (1)")
        print(f"  Status: {status_badge(self.gitops_app.sync_status)}\n")

        print(f"{Color.MAGENTA}Step 3: GitOps Controller Loop Triggered (Self-Healing Enabled)...{Color.RESET}")
        print("  Reconciliation loop calculating three-way merge patch...")
        time.sleep(0.4)
        print("  Applying git declarative source to restore desired state...")
        time.sleep(0.4)
        self.gitops_app.live_replicas = 3
        self.gitops_app.sync_status = "SYNCED"
        print(f"{Color.GREEN}✓ Self-Healing completed! Cluster converged to Git commit {self.gitops_app.target_revision}{Color.RESET}")
        print(f"  Live Replicas Restored: {self.gitops_app.live_replicas}")
        print(f"  Status: {status_badge(self.gitops_app.sync_status)}")

    # Module 3: Troubleshooting Scenarios
    def run_troubleshoot_scenario(self, issue_type: str) -> None:
        header(f"Module 3: SRE Triage Matrix - {issue_type}")

        if issue_type == "OOMKilled":
            pod = self.pods["checkout-pod-2"]
            pod.status = "OOMKilled"
            pod.exit_code = 137
            pod.restart_count += 5
            pod.events = [
                "Pod sandbox created successfully",
                "Container checkout started",
                "OOMKilling process 10423 (java): Memory cgroup out of memory: Killed process",
            ]
            print(f"{Color.RED}Alert Fired: Pod {pod.name} terminated abruptly!{Color.RESET}")
            print(f"Executing diagnosis command: `kubectl describe pod {pod.name}`\n")
            print(f"  Status        : {status_badge(pod.status)}")
            print(f"  Last State    : Terminated with ExitCode={pod.exit_code} (128 + SIGKILL 9)")
            print(f"  Reason        : OOMKilled (Memory limit exceeded: {pod.memory_limit})")
            print(f"  Events Log    :")
            for ev in pod.events:
                print(f"    - {Color.YELLOW}{ev}{Color.RESET}")

            print(f"\n{Color.CYAN}[SRE Remediation Action]{Color.RESET}")
            print("1. Cek memory leak profile atau heap dump JVM.")
            print("2. Update Helm `values.yaml` resources.limits.memory dari 256Mi -> 1Gi.")
            print("3. Commit perubahan ke Git repo agar GitOps merekonsiliasi rolling update.")

            # Apply Fix
            pod.memory_limit = "1Gi"
            pod.status = "RUNNING"
            pod.exit_code = 0
            print(f"\n{Color.GREEN}✓ Patch Applied: memory limit dinaikkan ke 1Gi. Pod pulih kembali!{Color.RESET}")

        elif issue_type == "ServiceMismatch":
            print(f"{Color.RED}Incident: Service {self.service.name} mengembalikan HTTP 503 Bad Gateway!{Color.RESET}")
            print(f"Investigasi Endpoints: `kubectl get endpoints {self.service.name}`")
            # Break selector
            self.service.selector = {"app": "checkout-typo", "tier": "backend"}
            self.service.endpoints = []
            print(f"  Current Endpoints: {Color.RED}<none>{Color.RESET}")
            print(f"  Diagnosa Selector Service: {self.service.selector}")
            print(f"  Label Pod Sebenarnya    : {self.pods['checkout-pod-1'].labels}\n")

            print(f"{Color.YELLOW}Root Cause Analisis: Selector 'app=checkout-typo' tidak cocok dengan label pod 'app=checkout'.{Color.RESET}")
            print("Memperbaiki manifest service selector via Git PR...")
            time.sleep(0.4)
            self.service.selector = {"app": "checkout", "tier": "backend"}
            self.service.endpoints = ["10.244.1.14:8080", "10.244.2.22:8080", "10.244.3.09:8080"]
            print(f"{Color.GREEN}✓ Service Selector diperbaiki! Endpoints terisi kembali: {self.service.endpoints}{Color.RESET}")

        elif issue_type == "ImagePullBackOff":
            pod = self.pods["checkout-pod-3"]
            pod.status = "ImagePullBackOff"
            pod.image = "registry.internal/apps/checkout:v999.0-nonexistent"
            pod.events = [
                "Pulling image registry.internal/apps/checkout:v999.0-nonexistent",
                "Failed to pull image: rpc error: code = NotFound desc = failed to pull and unpack image: tag not found",
                "Error: ErrImagePull",
                "Back-off pulling image",
            ]
            print(f"{Color.RED}Alert Fired: Pod {pod.name} gagal pull container image!{Color.RESET}")
            print(f"  Status     : {status_badge(pod.status)}")
            print(f"  Target Image: {pod.image}")
            print(f"  Events Log :")
            for ev in pod.events:
                print(f"    - {Color.YELLOW}{ev}{Color.RESET}")

            print(f"\n{Color.CYAN}[SRE Remediation Action]{Color.RESET}")
            print("1. Verifikasi registry creds secret `imagePullSecrets`.")
            print("2. Koreksi tag container ke tag valid di artifact repository: `v2.4.1`.")
            pod.image = "registry.internal/apps/checkout:v2.4.1"
            pod.status = "RUNNING"
            print(f"\n{Color.GREEN}✓ Tag dikoreksi ke v2.4.1. Pod successfully running!{Color.RESET}")

        elif issue_type == "EphemeralDebug":
            print(f"{Color.CYAN}Teknik Ephemeral Container Debugging: `kubectl debug`{Color.RESET}")
            target_pod = "checkout-pod-1"
            print(f"Target Pod: {target_pod} (Distroless / Non-root image tanpa bash/curl)")
            print(f"Command: `kubectl debug -it {target_pod} --image=nicolaka/netshoot --target=checkout --share-processes`")
            time.sleep(0.3)
            print(f"\n{Color.GREEN}[Connected to Ephemeral Debug Shell]{Color.RESET}")
            print("  netshoot:/# ss -tulpn")
            print("  Netid  State   Recv-Q  Send-Q   Local Address:Port   Peer Address:Port")
            print("  tcp    LISTEN  0       128            0.0.0.0:8080       0.0.0.0:*      users:((\"java\",pid=1,fd=4))")
            print("  netshoot:/# curl -s localhost:8080/actuator/health")
            print('  {"status":"UP","components":{"db":{"status":"UP"},"diskSpace":{"status":"UP"}}}')
            print(f"\n{Color.GREEN}✓ Root cause diverifikasi tanpa restart atau modifikasi pod produksi!{Color.RESET}")

    def run_automated_suite(self) -> None:
        header("Running Full Automated Kubernetes Bab 10 Validation Suite")
        self.print_overview()
        self.run_packaging_demo()
        self.run_gitops_reconciler_demo()
        self.run_troubleshoot_scenario("OOMKilled")
        self.run_troubleshoot_scenario("ServiceMismatch")
        self.run_troubleshoot_scenario("ImagePullBackOff")
        self.run_troubleshoot_scenario("EphemeralDebug")
        self.print_overview()
        print(f"\n{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} >> SELURUH SIMULASI PRODUKSI BAB 10 SELESAI DENGAN SUKSES [STATUS: PASSED] << {Color.RESET}\n")


def print_menu() -> None:
    print(f"\n{Color.BOLD}=== Kubernetes Lab Menu (Bab 10: Packaging, GitOps, & Troubleshooting) ==={Color.RESET}")
    print("  [1] Tampilkan Status Kluster & Topologi Pods")
    print("  [2] Simulasi Helm Packaging & Value Overrides Engine")
    print("  [3] Simulasi GitOps Controller Drift & Self-Healing Loop")
    print("  [4] Triage SRE: Troubleshooting OOMKilled (Exit 137)")
    print("  [5] Triage SRE: Troubleshooting Service Endpoint Mismatch")
    print("  [6] Triage SRE: Troubleshooting ImagePullBackOff")
    print("  [7] Triage SRE: Injeksi Ephemeral Container Debug (`kubectl debug`)")
    print("  [8] Jalankan Seluruh Validasi Otomatis (Full Production Suite)")
    print("  [0] Keluar")
    print(f"{Color.CYAN}{'-' * 74}{Color.RESET}")


def interactive_session() -> None:
    cluster = ClusterSimulator()
    
    # If run in non-interactive pipeline or with arguments, run full suite
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "auto", "test"):
        cluster.run_automated_suite()
        return

    # Check if standard input is a TTY
    if not sys.stdin.isatty():
        print(f"{Color.YELLOW}Standard input non-TTY terdeteksi. Menjalankan skrip dalam mode otomatis...{Color.RESET}")
        cluster.run_automated_suite()
        return

    while True:
        try:
            print_menu()
            choice = input(f"{Color.BOLD}Pilih nomor skenario [0-8]: {Color.RESET}").strip()
            if choice == "1":
                cluster.print_overview()
            elif choice == "2":
                cluster.run_packaging_demo()
            elif choice == "3":
                cluster.run_gitops_reconciler_demo()
            elif choice == "4":
                cluster.run_troubleshoot_scenario("OOMKilled")
            elif choice == "5":
                cluster.run_troubleshoot_scenario("ServiceMismatch")
            elif choice == "6":
                cluster.run_troubleshoot_scenario("ImagePullBackOff")
            elif choice == "7":
                cluster.run_troubleshoot_scenario("EphemeralDebug")
            elif choice == "8":
                cluster.run_automated_suite()
            elif choice in ("0", "q", "exit"):
                print(f"\n{Color.GREEN}Terima kasih! Sesi simulasi Kubernetes ditutup.{Color.RESET}")
                break
            else:
                print(f"{Color.RED}Pilihan tidak valid! Masukkan angka antara 0 - 8.{Color.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Color.YELLOW}Sesi dihentikan pengguna. Keluar...{Color.RESET}")
            break


if __name__ == "__main__":
    interactive_session()
