#!/usr/bin/env python3
"""
Lab Exercise: Modul 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
Simulasi Komprehensif Arsitektur GitOps, Policy-as-Code, Supply Chain Security,
dan Progressive Delivery (Canary Rollout dengan Analisis Metrik & Auto-Rollback).
"""

import sys
import time
import random
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Tuple, Optional

# ANSI Color Codes
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


def header(title: str) -> None:
    border = "=" * 70
    print(f"\n{Color.CYAN}{Color.BOLD}{border}")
    print(f"  {title.center(66)}")
    print(f"{border}{Color.RESET}\n")


def subheader(title: str) -> None:
    print(f"\n{Color.YELLOW}{Color.BOLD}>>> {title}{Color.RESET}")


@dataclass
class ContainerArtifact:
    image: str
    tag: str
    digest: str
    signed_by: Optional[str]
    has_sbom: bool
    privileged_mode: bool
    cpu_limit: str
    memory_limit: str


class GatekeeperPolicyEngine:
    """Policy-as-Code Engine menggunakan rule set OPA/Gatekeeper."""
    
    @staticmethod
    def validate_admission(artifact: ContainerArtifact) -> Tuple[bool, List[str]]:
        violations = []
        
        # Rule 1: Must be cryptographically signed by authorized key (Supply Chain Security)
        if not artifact.signed_by or artifact.signed_by != "cosign@prod-ci.internal":
            violations.append("DENY: Image signature missing or invalid cryptographic attestation (Cosign/SLSA).")
            
        # Rule 2: Must include verified SBOM
        if not artifact.has_sbom:
            violations.append("DENY: Missing SPDX/CycloneDX Software Bill of Materials (SBOM).")
            
        # Rule 3: Must not run in privileged mode (Container Hardening)
        if artifact.privileged_mode:
            violations.append("DENY: Container securityContext.privileged must be false (PSP/PSS compliance).")
            
        # Rule 4: Resource limits must be declared
        if not artifact.cpu_limit or not artifact.memory_limit:
            violations.append("DENY: Quality of Service (QoS) violation - cpu/memory limits must be explicitly declared.")
            
        is_admitted = len(violations) == 0
        return is_admitted, violations


class GitOpsReconciliationController:
    """Operator yang memantau Desired State di Git vs Live State di Cluster."""
    
    def __init__(self, app_name: str):
        self.app_name = app_name
        self.desired_state: Dict[str, any] = {}
        self.live_state: Dict[str, any] = {}
        
    def sync_from_git(self, git_manifest: Dict[str, any]) -> None:
        self.desired_state = json.loads(json.dumps(git_manifest))
        print(f"{Color.BLUE}[GitOps Sync]{Color.RESET} Fetched commit {Color.BOLD}{self.desired_state.get('commit_hash')}{Color.RESET} from repository.")
        
    def get_live_state(self) -> Dict[str, any]:
        return self.live_state

    def simulate_manual_cluster_drift(self, modified_replicas: int) -> None:
        """Simulasi drift: seseorang menjalankan 'kubectl scale' langsung ke cluster."""
        print(f"{Color.RED}{Color.BOLD}[External Drift Event]{Color.RESET} Rogue engineer executed manual 'kubectl scale' to {modified_replicas} replicas!")
        self.live_state["replicas"] = modified_replicas

    def reconcile(self) -> bool:
        """Loop rekonsiliasi operator untuk mendeteksi drift dan auto-healing."""
        desired_hash = hashlib.sha256(json.dumps(self.desired_state, sort_keys=True).encode()).hexdigest()[:12]
        live_hash = hashlib.sha256(json.dumps(self.live_state, sort_keys=True).encode()).hexdigest()[:12]
        
        print(f"{Color.MAGENTA}[Operator Reconciliation Loop]{Color.RESET}")
        print(f"  Desired State Hash: {Color.GREEN}{desired_hash}{Color.RESET} | Live State Hash: {Color.YELLOW}{live_hash}{Color.RESET}")
        
        drift_detected = False
        for key in ["image", "replicas", "strategy"]:
            if self.desired_state.get(key) != self.live_state.get(key):
                print(f"  {Color.RED}Drift Detected on attribute '{key}': Desired={self.desired_state.get(key)}, Live={self.live_state.get(key)}{Color.RESET}")
                drift_detected = True
                
        if drift_detected:
            print(f"  {Color.YELLOW}[Auto-Healing Action]{Color.RESET} Forcing reconciliation... Applying Git declared state to Live cluster.")
            self.live_state = json.loads(json.dumps(self.desired_state))
            print(f"  {Color.GREEN}{Color.BOLD}[Synced & Healthy]{Color.RESET} Live state cluster sekarang 100% konsisten dengan Git.")
            return True
        else:
            print(f"  {Color.GREEN}[In Sync]{Color.RESET} Cluster state perfectly matches Git repository. No drift found.")
            return False


class ProgressiveCanaryRollout:
    """Canary progressive delivery controller dengan evaluasi prometheus metrik."""
    
    def __init__(self, app_name: str, stable_version: str, canary_version: str):
        self.app_name = app_name
        self.stable_version = stable_version
        self.canary_version = canary_version
        self.steps = [10, 25, 50, 80, 100]  # Persentase traffic canary
        self.sla_max_p99_latency_ms = 120.0
        self.sla_max_5xx_rate_pct = 1.0
        
    def simulate_metrics_sampler(self, traffic_weight: int, inject_defect: bool) -> Tuple[float, float]:
        """Simulasi Prometheus scraping p99 latency dan 5xx error rate."""
        if inject_defect and traffic_weight >= 25:
            # Simulasi regresi performa/bug memori pada versi canary
            p99_latency = random.uniform(160.0, 320.0)
            error_5xx_rate = random.uniform(3.5, 8.2)
        else:
            p99_latency = random.uniform(35.0, 75.0)
            error_5xx_rate = random.uniform(0.01, 0.25)
        return round(p99_latency, 2), round(error_5xx_rate, 2)

    def execute_rollout(self, inject_failure: bool = False) -> bool:
        subheader(f"Memulai Progressive Canary Rollout: {self.stable_version} -> {self.canary_version}")
        print(f"Target SLA: Latency p99 < {self.sla_max_p99_latency_ms}ms | 5xx Error Rate < {self.sla_max_5xx_rate_pct}%")
        
        for step in self.steps:
            stable_traffic = 100 - step
            print(f"\n{Color.CYAN}--- Shift Traffic: Stable={stable_traffic}%, Canary={step}% ---{Color.RESET}")
            
            # Sampling metrik sebanyak 3 iterasi
            breaches = 0
            for i in range(1, 4):
                time.sleep(0.3)
                p99, err_rate = self.simulate_metrics_sampler(step, inject_defect=inject_failure)
                
                status_color = Color.GREEN
                is_breach = p99 > self.sla_max_p99_latency_ms or err_rate > self.sla_max_5xx_rate_pct
                if is_breach:
                    status_color = Color.RED
                    breaches += 1
                    
                print(f"  [Probe #{i}] Canary Metric: p99={status_color}{p99}ms{Color.RESET}, 5xx_rate={status_color}{err_rate}%{Color.RESET}")
                
            if breaches >= 2:
                print(f"\n{Color.BG_RED}{Color.WHITE} [CRITICAL ALERT] SLA BREACH DETECTED IN CANARY METRICS! {Color.RESET}")
                print(f"{Color.RED}{Color.BOLD}>>> Membatalkan Rollout & Menjalankan Automated Instant Rollback ke {self.stable_version}...{Color.RESET}")
                time.sleep(0.4)
                print(f"{Color.GREEN}[Traffic Restored]{Color.RESET} 100% traffic dialihkan kembali ke versi stabil ({self.stable_version}).")
                print(f"{Color.YELLOW}[Post-Mortem Event]{Color.RESET} Canary deployment dipurge, telemetry alert dikirim ke channel SRE.")
                return False
                
            print(f"  {Color.GREEN}✔ Canary Step {step}% Lolos Verifikasi Metrik SLO.{Color.RESET}")
            
        print(f"\n{Color.BG_GREEN}{Color.WHITE} [ROLLOUT SUCCEEDED] Canary {self.canary_version} dipromosikan penuh ke 100% produksi! {Color.RESET}")
        return True


def run_laboratory():
    header("DEVOPS BAB 01 MODUL 02: HANDS-ON ADVANCED ARCHITECTURE LAB")
    print(f"{Color.DIM}Lingkungan Simulasi: GitOps Reconciliation + OPA Policy Engine + Progressive Canary{Color.RESET}\n")

    # =========================================================================
    # STEP 1: Supply Chain Security & Admission Controller Policy
    # =========================================================================
    subheader("Tahap 1: Verifikasi Supply Chain Cryptographic & OPA Admission Control")
    
    good_artifact = ContainerArtifact(
        image="registry.internal/payment-service",
        tag="v2.4.0",
        digest="sha256:d8a57e3f94c1204859a11bc19e5",
        signed_by="cosign@prod-ci.internal",
        has_sbom=True,
        privileged_mode=False,
        cpu_limit="500m",
        memory_limit="512Mi"
    )
    
    bad_artifact = ContainerArtifact(
        image="registry.internal/payment-service",
        tag="v2.5.0-dev",
        digest="sha256:49fa10b98c39247ad",
        signed_by=None,  # Unsigned image!
        has_sbom=False,  # Missing SBOM!
        privileged_mode=True, # Insecure privilege escalation!
        cpu_limit="",
        memory_limit=""
    )
    
    print(f"Menguji Artefak A ({good_artifact.tag}) terhadap Gatekeeper OPA Policy:")
    admitted, violations = GatekeeperPolicyEngine.validate_admission(good_artifact)
    if admitted:
        print(f"  {Color.GREEN}✔ PASSED: Image lolos verifikasi tanda tangan digital Cosign & policy security hardening.{Color.RESET}")
    else:
        print(f"  {Color.RED}✖ REJECTED: {violations}{Color.RESET}")
        
    print(f"\nMenguji Artefak B ({bad_artifact.tag} - Unsigned & Privileged):")
    admitted, violations = GatekeeperPolicyEngine.validate_admission(bad_artifact)
    if admitted:
        print(f"  {Color.GREEN}✔ PASSED{Color.RESET}")
    else:
        print(f"  {Color.RED}{Color.BOLD}✖ REJECTED BY ADMISSION WEBHOOK:{Color.RESET}")
        for v in violations:
            print(f"    - {Color.RED}{v}{Color.RESET}")

    # =========================================================================
    # STEP 2: GitOps Controller Reconciliation & Drift Self-Healing
    # =========================================================================
    subheader("Tahap 2: GitOps Reconciler - Drift Detection & Autonomous Self-Healing")
    
    gitops = GitOpsReconciliationController(app_name="payment-service")
    git_manifest = {
        "app": "payment-service",
        "image": "registry.internal/payment-service:v2.4.0",
        "replicas": 6,
        "strategy": "Canary",
        "commit_hash": "a79fc21"
    }
    
    gitops.sync_from_git(git_manifest)
    # Inisialisasi live state sama dengan desired
    gitops.live_state = json.loads(json.dumps(git_manifest))
    
    print(f"\n[Status Awal Cluster]")
    gitops.reconcile()
    
    print("\n[Simulasi Human Error / Direct Infrastructure Tampering]")
    gitops.simulate_manual_cluster_drift(modified_replicas=2)
    
    print("\n[Eksekusi Siklus Rekonsiliasi Otomatis]")
    gitops.reconcile()

    # =========================================================================
    # STEP 3: Progressive Delivery - Canary Rollout (Happy Path & Failure Injected)
    # =========================================================================
    subheader("Tahap 3: Progressive Delivery - Argo Rollout Canary Simulation")
    
    print(f"{Color.BOLD}Skenario A: Rollout Canary Rilis v2.4.0 (Normal / Sehat){Color.RESET}")
    canary_normal = ProgressiveCanaryRollout("payment-service", "v2.3.9", "v2.4.0")
    success = canary_normal.execute_rollout(inject_failure=False)
    
    print(f"\n{Color.BOLD}Skenario B: Rollout Canary Rilis v2.5.0 (Regresi Memori / Latensi Tinggi){Color.RESET}")
    canary_faulty = ProgressiveCanaryRollout("payment-service", "v2.4.0", "v2.5.0")
    success_faulty = canary_faulty.execute_rollout(inject_failure=True)
    
    # =========================================================================
    # RINGKASAN AKHIR
    # =========================================================================
    header("HASIL EVALUASI LAB MODUL 02")
    print(f"{Color.GREEN}✔ Supply Chain Attestation :{Color.RESET} Gatekeeper berhasil memblokir artefak tidak tepercaya.")
    print(f"{Color.GREEN}✔ GitOps Reconciliation    :{Color.RESET} Operator berhasil mendeteksi cluster drift dan melakukan self-heal.")
    print(f"{Color.GREEN}✔ Progressive Delivery     :{Color.RESET} Automated Rollback berhasil melindungi pengguna dari regresi performa.")
    print(f"\n{Color.CYAN}{Color.BOLD}Simulasi arsitektur DevOps produksi selesai dengan status SUCCESS.{Color.RESET}\n")


if __name__ == "__main__":
    run_laboratory()
