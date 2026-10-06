#!/usr/bin/env python3
"""
Lab Exercise: Kubernetes Packaging, GitOps Reconciliation & Troubleshooting Simulation
BAB-10: Packaging, GitOps, dan Troubleshooting
"""

import sys
import time
import random
from typing import Dict, List, Any, Optional

# ANSI Color Palette
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def log_info(msg: str) -> None:
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")

def log_success(msg: str) -> None:
    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} {msg}")

def log_warn(msg: str) -> None:
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")

def log_error(msg: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")

def log_step(title: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}===> {title}{Colors.RESET}")


# Module 1: Helm Chart Packaging & Template Engine Simulation
class HelmChartSimulator:
    def __init__(self, chart_name: str, version: str):
        self.chart_name = chart_name
        self.version = version
        self.default_values: Dict[str, Any] = {
            "replicaCount": 2,
            "image": {"repository": "nginx", "tag": "1.25.1", "pullPolicy": "IfNotPresent"},
            "resources": {"limits": {"cpu": "200m", "memory": "256Mi"}, "requests": {"cpu": "100m", "memory": "128Mi"}},
            "service": {"type": "ClusterIP", "port": 80}
        }

    def render_manifest(self, custom_values: Optional[Dict[str, Any]] = None) -> str:
        values = self.default_values.copy()
        if custom_values:
            values.update(custom_values)
            if "image" in custom_values:
                values["image"] = {**self.default_values["image"], **custom_values["image"]}

        manifest = f"""---
# Source: {self.chart_name}/templates/deployment.yaml (Helm v{self.version})
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {self.chart_name}-web
  labels:
    app.kubernetes.io/name: {self.chart_name}
    app.kubernetes.io/version: "{values['image']['tag']}"
spec:
  replicas: {values['replicaCount']}
  selector:
    matchLabels:
      app: {self.chart_name}
  template:
    metadata:
      labels:
        app: {self.chart_name}
    spec:
      containers:
      - name: app
        image: "{values['image']['repository']}:{values['image']['tag']}"
        imagePullPolicy: {values['image']['pullPolicy']}
        resources:
          limits:
            cpu: {values['resources']['limits']['cpu']}
            memory: {values['resources']['limits']['memory']}
"""
        return manifest


# Module 2: GitOps Controller & Drift Detection Engine (ArgoCD / Flux Model)
class GitOpsReconciler:
    def __init__(self):
        self.git_revision = "a1b2c3d"
        self.desired_state: Dict[str, Any] = {
            "replicas": 3,
            "image": "app-backend:v1.2.0",
            "cpu_limit": "250m"
        }
        self.live_state: Dict[str, Any] = {
            "replicas": 3,
            "image": "app-backend:v1.2.0",
            "cpu_limit": "250m"
        }

    def inject_drift(self) -> None:
        log_warn("Simulasi Manual kubectl edit/patch oleh Operator di Cluster (Out-of-Band Change)!")
        self.live_state["replicas"] = 1
        self.live_state["image"] = "app-backend:debug-hotfix"

    def detect_drift(self) -> List[str]:
        drifts = []
        for key, desired_val in self.desired_state.items():
            live_val = self.live_state.get(key)
            if desired_val != live_val:
                drifts.append(f"Field '{key}': Desired='{desired_val}' != Live='{live_val}'")
        return drifts

    def reconcile(self, auto_sync: bool = True) -> None:
        log_step("GitOps Controller Loop: Sync State Check")
        drifts = self.detect_drift()
        if not drifts:
            log_success(f"Cluster State: InSync (SyncStatus: Synced, HealthStatus: Healthy)")
            return

        log_error(f"Cluster State: OutOfSync! Terdeteksi {len(drifts)} perubahan tak sah:")
        for drift in drifts:
            print(f"  {Colors.RED}✗ {drift}{Colors.RESET}")

        if auto_sync:
            log_info("Memulai Self-Healing / Auto-Sync ke Single Source of Truth (Git)...")
            time.sleep(0.5)
            self.live_state = self.desired_state.copy()
            log_success("Rekonsiliasi Sukses: Live cluster state dipulihkan sesuai Git repo!")


# Module 3: Kubernetes Troubleshooting & RCA Engine
class PodDiagnosticEngine:
    ISSUES = [
        {
            "pod": "payment-api-79df4b876-xk29j",
            "status": "CrashLoopBackOff",
            "exit_code": 1,
            "event": "Back-off restarting failed container",
            "logs": "FATAL: Connection to Redis at redis:6379 refused. Authentication required.",
            "rca": "Kesalahan ConfigMap/Secret: Password Redis tidak diinjeksikan ke ENV variabel.",
            "remedy": "Periksa Secret redis-creds dan pastikan envFrom pada Deployment mereferensikan SecretKeyRef yang valid."
        },
        {
            "pod": "order-processor-5d6789b7-pl81q",
            "status": "OOMKilled",
            "exit_code": 137,
            "event": "Container app exceeded memory limit (256Mi), terminated by cgroup OOM killer",
            "logs": "java.lang.OutOfMemoryError: Java heap space",
            "rca": "Memory limit terlalu rendah atau terdapat memory leak pada Java JVM heap allocation.",
            "remedy": "Tingkatkan resources.limits.memory ke 512Mi / 1Gi dan konfigurasikan JVM flag -XX:MaxRAMPercentage."
        },
        {
            "pod": "auth-service-86b998cf64-wm29z",
            "status": "ImagePullBackOff",
            "exit_code": 0,
            "event": "Failed to pull image registry.internal.corp/auth:v2.1.0: unauthorized: access token required",
            "logs": "<tidak ada log kontainer>",
            "rca": "Autentikasi Container Registry gagal atau imagePullSecrets tidak disertakan pada ServiceAccount/Pod.",
            "remedy": "Buat Secret docker-registry dan lampirkan imagePullSecrets pada spec Pod."
        }
    ]

    def run_troubleshooting_lab(self) -> None:
        log_step("Kubernetes Cluster Troubleshooting & RCA Diagnostic")
        print(f"{Colors.BOLD}{'POD NAME':<35} {'STATUS':<20} {'EXIT CODE':<10}{Colors.RESET}")
        print("-" * 65)
        for issue in self.ISSUES:
            color = Colors.RED if issue["status"] != "Running" else Colors.GREEN
            print(f"{issue['pod']:<35} {color}{issue['status']:<20}{Colors.RESET} {issue['exit_code']:<10}")

        print("\n" + "=" * 65)
        for i, issue in enumerate(self.ISSUES, 1):
            print(f"\n{Colors.YELLOW}[Investigasi Insiden #{i}] Pod: {issue['pod']}{Colors.RESET}")
            print(f"  • Event K8s  : {issue['event']}")
            print(f"  • Log Output : {Colors.DIM}{issue['logs']}{Colors.RESET}")
            print(f"  • {Colors.BOLD}Root Cause Analysis (RCA):{Colors.RESET} {issue['rca']}")
            print(f"  • {Colors.GREEN}Rekomendasi Perbaikan (Remedy):{Colors.RESET} {issue['remedy']}")


def main() -> None:
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("=======================================================================")
    print("   LAB SIMULASI KUBERNETES: PACKAGING, GITOPS & TROUBLESHOOTING       ")
    print("   BAB 10: Hands-on Lab Interaktif                                    ")
    print("=======================================================================")
    print(f"{Colors.RESET}")

    # Bagian 1: Helm Packaging
    log_step("BAGIAN 1: Helm Template Rendering Simulation")
    helm = HelmChartSimulator(chart_name="ecommerce-core", version="1.0.0")
    custom_overrides = {
        "replicaCount": 4,
        "image": {"tag": "2.4.0-prod"}
    }
    rendered = helm.render_manifest(custom_overrides)
    print(f"{Colors.DIM}{rendered}{Colors.RESET}")
    log_success("Helm chart manifest berhasil dirender dengan values override.")

    # Bagian 2: GitOps Engine
    log_step("BAGIAN 2: GitOps Continuous Delivery & Drift Self-Healing")
    gitops = GitOpsReconciler()
    gitops.reconcile()
    
    print("\n[Simulasi] Menyuntikkan konfigurasi drift pada cluster...")
    gitops.inject_drift()
    gitops.reconcile(auto_sync=True)

    # Bagian 3: Troubleshooting Engine
    log_step("BAGIAN 3: Diagnostic Engine untuk Troubleshooting Pod Bermasalah")
    diagnostic = PodDiagnosticEngine()
    diagnostic.run_troubleshooting_lab()

    print(f"\n{Colors.BOLD}{Colors.GREEN}=======================================================================")
    print("   LAB SELESAI: Seluruh simulasi BAB-10 berhasil dieksekusi tanpa error!")
    print(f"======================================================================={Colors.RESET}\n")

if __name__ == "__main__":
    main()
