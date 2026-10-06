#!/usr/bin/env python3
"""
Lab Exercise: Production Container Deployment & Registry Management Simulator
Topik: BAB 10 - Production Deployment & Container Registries (Modul 02)
Target Platform: Python 3.8+ (Zero External Dependencies)
"""

import sys
import time
import json
import hashlib
import random
from typing import Dict, List, Optional
from dataclasses import dataclass, field

# ==============================================================================
# Terminal ANSI Color Palette
# ==============================================================================
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
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"


def header(text: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} [LAB] {text.center(67)} {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")


def step_banner(step_num: int, title: str) -> None:
    print(f"\n{Color.BOLD}{Color.YELLOW}[STEP {step_num}] {title}{Color.RESET}")
    print(f"{Color.DIM}{'-' * 60}{Color.RESET}")


def log_info(msg: str) -> None:
    print(f"{Color.BLUE}ℹ  INFO:{Color.RESET} {msg}")


def log_success(msg: str) -> None:
    print(f"{Color.GREEN}✔  SUCCESS:{Color.RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"{Color.YELLOW}⚠  WARN:{Color.RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"{Color.RED}✖  ERROR:{Color.RESET} {msg}")


# ==============================================================================
# Domain Models
# ==============================================================================
@dataclass
class Vulnerability:
    cve_id: str
    package: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    description: str


@dataclass
class ContainerImage:
    repository: str
    tag: str
    architecture: str
    layers: List[str]
    digest: str = ""
    is_signed: bool = False
    signature_hash: str = ""
    vulnerabilities: List[Vulnerability] = field(default_factory=list)

    def calculate_digest(self) -> str:
        combined = f"{self.repository}:{self.tag}:{self.architecture}:" + ":".join(self.layers)
        self.digest = "sha256:" + hashlib.sha256(combined.encode()).hexdigest()
        return self.digest


@dataclass
class ManifestList:
    repository: str
    tag: str
    manifests: Dict[str, str] = field(default_factory=dict)  # arch -> digest


# ==============================================================================
# Simulation Engine
# ==============================================================================
class ProductionRegistrySimulator:
    def __init__(self, registry_domain: str = "registry.internal.enterprise.io:5000"):
        self.domain = registry_domain
        self.catalog: Dict[str, Dict[str, ContainerImage]] = {}  # repo -> {tag: image}
        self.manifest_lists: Dict[str, Dict[str, ManifestList]] = {}  # repo -> {tag: manifest_list}
        self.authenticated_users = {"admin": "Secr3tToken#2026", "ci-builder": "CI_Deploy_Key_998"}
        self.session_token: Optional[str] = None

    def authenticate(self, username: str, token: str) -> bool:
        log_info(f"Authenticating against {self.domain}/v2/_catalog...")
        time.sleep(0.3)
        if self.authenticated_users.get(username) == token:
            self.session_token = f"jwt-session-{hashlib.md5(username.encode()).hexdigest()[:8]}"
            log_success(f"Authenticated as '{username}'. Token: {self.session_token}")
            return True
        log_error("Registry authentication failed: Invalid credentials.")
        return False

    def push_image(self, image: ContainerImage) -> bool:
        if not self.session_token:
            log_error("Push rejected: 401 Unauthorized. Login required.")
            return False

        image.calculate_digest()
        repo = f"{self.domain}/{image.repository}"
        
        log_info(f"Pushing image {repo}:{image.tag} ({image.architecture})")
        for idx, layer in enumerate(image.layers, start=1):
            time.sleep(0.15)
            layer_hash = hashlib.sha256(layer.encode()).hexdigest()[:12]
            print(f"  {Color.DIM}Layer {idx}/{len(image.layers)} [{layer_hash}] -> Pushed{Color.RESET}")

        if repo not in self.catalog:
            self.catalog[repo] = {}
        self.catalog[repo][image.tag] = image
        
        log_success(f"Pushed: {repo}:{image.tag}")
        print(f"  {Color.MAGENTA}Digest: {image.digest}{Color.RESET}")
        return True

    def create_multiarch_manifest(self, repo_name: str, tag: str, arch_images: List[ContainerImage]) -> bool:
        repo = f"{self.domain}/{repo_name}"
        log_info(f"Creating multi-architecture manifest list for {repo}:{tag}...")
        time.sleep(0.3)
        
        m_list = ManifestList(repository=repo, tag=tag)
        for img in arch_images:
            if not img.digest:
                img.calculate_digest()
            m_list.manifests[img.architecture] = img.digest
            print(f"  {Color.CYAN}+ Target Arch: {img.architecture:<8} -> {img.digest[:24]}...{Color.RESET}")

        if repo not in self.manifest_lists:
            self.manifest_lists[repo] = {}
        self.manifest_lists[repo][tag] = m_list
        log_success(f"Manifest list published: {repo}:{tag}")
        return True


class SecurityVulnerabilityScanner:
    SEVERITY_WEIGHTS = {"LOW": 1, "MEDIUM": 3, "HIGH": 7, "CRITICAL": 15}

    @staticmethod
    def scan(image: ContainerImage, fail_threshold: str = "HIGH") -> bool:
        log_info(f"Scanning image {image.repository}:{image.tag} with Security Policy Gate...")
        time.sleep(0.4)
        print(f"  Target Digest: {image.digest[:30]}...")

        if not image.vulnerabilities:
            log_success("No CVE vulnerabilities found in image layers! Image clean.")
            return True

        print(f"\n  {Color.BOLD}{'CVE ID':<16} {'PACKAGE':<15} {'SEVERITY':<12} {'SUMMARY'}{Color.RESET}")
        print(f"  {'-' * 65}")

        max_weight = 0
        threshold_weight = SecurityVulnerabilityScanner.SEVERITY_WEIGHTS.get(fail_threshold, 7)

        for v in image.vulnerabilities:
            w = SecurityVulnerabilityScanner.SEVERITY_WEIGHTS.get(v.severity, 0)
            if w > max_weight:
                max_weight = w
            
            color = Color.WHITE
            if v.severity == "CRITICAL":
                color = Color.RED
            elif v.severity == "HIGH":
                color = Color.YELLOW
            elif v.severity == "MEDIUM":
                color = Color.CYAN

            print(f"  {v.cve_id:<16} {v.package:<15} {color}{v.severity:<12}{Color.RESET} {v.description[:30]}")

        print(f"  {'-' * 65}")
        if max_weight >= threshold_weight:
            log_error(f"Image gate check FAILED! Found vulnerabilities at or above '{fail_threshold}'.")
            return False

        log_success("Security gate PASSED. Vulnerabilities within acceptable enterprise threshold.")
        return True


class OrchestrationDeploymentManager:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.blue_nodes: List[Dict[str, str]] = []
        self.green_nodes: List[Dict[str, str]] = []
        self.active_pool: str = "blue"
        self.traffic_ratio: Dict[str, int] = {"blue": 100, "green": 0}

    def provision_initial_blue(self, image_ref: str, instances: int = 3) -> None:
        log_info(f"Provisioning initial BLUE cluster for '{self.service_name}' ({instances} pods)...")
        self.blue_nodes.clear()
        for i in range(1, instances + 1):
            pod = {
                "id": f"pod-{self.service_name}-blue-{i:02d}",
                "image": image_ref,
                "status": "Running",
                "health": "200 OK",
            }
            self.blue_nodes.append(pod)
            time.sleep(0.1)
            print(f"  {Color.BLUE}✔ Node ready: {pod['id']} running {image_ref}{Color.RESET}")
        self.active_pool = "blue"
        self.traffic_ratio = {"blue": 100, "green": 0}
        log_success("BLUE cluster actively serving 100% production traffic.")

    def run_blue_green_deployment(self, new_image_ref: str) -> bool:
        header(f"Blue/Green Zero-Downtime Deployment: {self.service_name}")
        log_info(f"Target Version to deploy: {Color.BOLD}{new_image_ref}{Color.RESET}")

        target_pool = "green" if self.active_pool == "blue" else "blue"
        current_pool = self.active_pool

        # 1. Provision target pool
        log_info(f"Phase 1: Spin up staging cluster [{target_pool.upper()}] with {new_image_ref}")
        staging_nodes: List[Dict[str, str]] = []
        for i in range(1, len(self.blue_nodes) + 1):
            time.sleep(0.2)
            pod = {
                "id": f"pod-{self.service_name}-{target_pool}-{i:02d}",
                "image": new_image_ref,
                "status": "Running",
                "health": "200 OK",
            }
            staging_nodes.append(pod)
            print(f"  {Color.GREEN}➜ Provisioned {pod['id']} (Warmup state){Color.RESET}")

        if target_pool == "green":
            self.green_nodes = staging_nodes
        else:
            self.blue_nodes = staging_nodes

        # 2. Synthetic Health Check probes
        log_info("Phase 2: Executing deep synthetic health checks (/healthz & /ready)...")
        time.sleep(0.3)
        for pod in staging_nodes:
            latency = random.randint(12, 45)
            print(f"  Probe {pod['id']}: HTTP GET /healthz -> {Color.GREEN}Status 200{Color.RESET} ({latency}ms)")
        log_success("100% synthetic probes succeeded. Staging cluster is fully healthy.")

        # 3. Traffic Shifting
        log_info("Phase 3: Shifting load balancer ingress rules...")
        for pct in [10, 25, 50, 100]:
            time.sleep(0.25)
            if target_pool == "green":
                self.traffic_ratio = {"blue": 100 - pct, "green": pct}
            else:
                self.traffic_ratio = {"green": 100 - pct, "blue": pct}
            
            bar_len = 30
            green_bars = int(bar_len * (self.traffic_ratio["green"] / 100))
            blue_bars = bar_len - green_bars
            bar_visual = f"{Color.BG_BLUE}{' ' * blue_bars}{Color.BG_GREEN}{' ' * green_bars}{Color.RESET}"
            print(f"  LoadBalancer: {bar_visual} | Blue: {self.traffic_ratio['blue']}% | Green: {self.traffic_ratio['green']}%")

        self.active_pool = target_pool
        log_success(f"Deployment cutover complete! Active pool: {self.active_pool.upper()}")

        # 4. Drain & Idle old cluster
        log_info(f"Phase 4: Draining connection pool on previous [{current_pool.upper()}] nodes...")
        time.sleep(0.2)
        log_success(f"Cluster [{current_pool.upper()}] drained and placed in standby state for quick rollback.")
        return True

    def canary_traffic_shift_with_rollback(self, canary_image: str, simulate_fault: bool = True) -> bool:
        header(f"Canary Release Strategy: {self.service_name}")
        log_info(f"Canary Target Image: {canary_image}")
        log_info("Injecting 1 Canary Instance (10% Traffic Weight)...")
        time.sleep(0.3)

        canary_pod = {
            "id": f"pod-{self.service_name}-canary-01",
            "image": canary_image,
            "status": "Running",
        }
        print(f"  {Color.MAGENTA}★ Canary Pod started: {canary_pod['id']}{Color.RESET}")

        log_info("Monitoring telemetry metrics (Error Rate & P99 Latency)...")
        for second in range(1, 4):
            time.sleep(0.3)
            if simulate_fault and second == 2:
                log_error("Telemetry Alert: HTTP 500 error rate spiked to 14.8%! (SLO threshold: < 1.0%)")
                log_warn("Triggering automated Canary Circuit Breaker Rollback...")
                time.sleep(0.2)
                print(f"  {Color.RED}✖ Traffic instantly redirected back to stable pool (100%){Color.RESET}")
                print(f"  {Color.RED}✖ Terminating unhealthy pod {canary_pod['id']}{Color.RESET}")
                log_success("Rollback finalized. Zero production degradation sustained.")
                return False
            else:
                print(f"  Metric T+{second}s: 0.02% 5xx errors | P99: 38ms (Healthy)")

        log_success("Canary stage stable. Ready for automated progression.")
        return True


# ==============================================================================
# Interactive Guided Runner
# ==============================================================================
def run_interactive_simulation() -> None:
    header("ENTERPRISE DOCKER PRODUCTION DEPLOYMENT LAB (BAB 10)")
    print(f"{Color.BOLD}Skenario:{Color.RESET} Mensimulasikan pipeline deployment enterprise lengkap:")
    print(" 1. Private Enterprise Registry Authentication & Layer Push")
    print(" 2. Multi-Architecture Manifest Building (amd64 / arm64)")
    print(" 3. Container Vulnerability Scanning & Compliance Gate")
    print(" 4. Blue/Green Zero-Downtime Deployment & Canary Rollback")
    print(f"{Color.DIM}{'=' * 75}{Color.RESET}\n")

    registry = ProductionRegistrySimulator()
    deployer = OrchestrationDeploymentManager("payment-gateway")

    # Step 1: Authentication & Layer Push
    step_banner(1, "Secure Registry Authentication & Push")
    auth_ok = registry.authenticate("ci-builder", "CI_Deploy_Key_998")
    if not auth_ok:
        sys.exit(1)

    app_v1 = ContainerImage(
        repository="fintech/payment-gateway",
        tag="v1.2.0-amd64",
        architecture="amd64",
        layers=["layer-base-alpine:3.19", "layer-runtime-python:3.12", "layer-app-code:1.2.0"],
    )
    registry.push_image(app_v1)

    app_v1_arm = ContainerImage(
        repository="fintech/payment-gateway",
        tag="v1.2.0-arm64",
        architecture="arm64",
        layers=["layer-base-alpine:3.19", "layer-runtime-python:3.12-arm", "layer-app-code:1.2.0"],
    )
    registry.push_image(app_v1_arm)

    # Step 2: Multi-Architecture Manifest
    step_banner(2, "Multi-Arch Manifest List Creation")
    registry.create_multiarch_manifest("fintech/payment-gateway", "v1.2.0", [app_v1, app_v1_arm])

    # Step 3: Security Gate & Scanning
    step_banner(3, "Image Vulnerability Gate Check")
    app_v1.vulnerabilities = [
        Vulnerability("CVE-2024-21626", "runc", "LOW", "Internal file descriptor leak handling"),
        Vulnerability("CVE-2024-24576", "libssl", "MEDIUM", "Command execution edge case bypass"),
    ]
    scan_passed = SecurityVulnerabilityScanner.scan(app_v1, fail_threshold="HIGH")
    if not scan_passed:
        log_error("Pipeline halted due to security violation.")
        sys.exit(1)

    # Step 4: Baseline Deployment
    step_banner(4, "Baseline Cluster Initialization")
    deployer.provision_initial_blue("registry.internal.enterprise.io:5000/fintech/payment-gateway:v1.2.0", instances=3)

    # Step 5: Blue/Green Deployment to v1.3.0
    step_banner(5, "Execute Blue/Green Zero-Downtime Rollout")
    deployer.run_blue_green_deployment("registry.internal.enterprise.io:5000/fintech/payment-gateway:v1.3.0")

    # Step 6: Canary Release with Automated Rollback Demo
    step_banner(6, "Canary Deployment with Automated Health Failure Rollback")
    deployer.canary_traffic_shift_with_rollback(
        canary_image="registry.internal.enterprise.io:5000/fintech/payment-gateway:v2.0.0-unstable",
        simulate_fault=True,
    )

    header("PRODUCTION LAB COMPLETED SUCCESSFULLY")
    print(f"{Color.GREEN}{Color.BOLD}Seluruh verifikasi arsitektur produksi kontainer telah selesai.{Color.RESET}")
    print("Semua pilar: Registry, Multi-Arch, Image Security, Zero-Downtime, dan Rollback tervalidasi.\n")


if __name__ == "__main__":
    try:
        run_interactive_simulation()
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}[!] Lab simulation stopped by user.{Color.RESET}")
        sys.exit(0)
