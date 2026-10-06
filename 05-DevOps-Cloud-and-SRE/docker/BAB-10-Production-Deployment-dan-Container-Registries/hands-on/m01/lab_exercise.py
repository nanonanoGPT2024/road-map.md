#!/usr/bin/env python3
"""
Laboratorium Simulasi Interaktif: Docker Production Deployment & Container Registries
BAB-10: Production Deployment dan Container Registries

Simulasi teknis mencakup:
1. Immutable Tagging & Content-Addressable Image Digests (SHA-256)
2. Registry Push/Pull & Layer Deduplication (Blob Store)
3. Container Security Vulnerability Gate (CVE Severity Matrix)
4. Zero-Downtime Blue/Green Deployment & Traffic Cutover
"""

import sys
import time
import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_BLUE = "\033[44m"


def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}================================================================================
  DOCKER PRODUCTION DEPLOYMENT & CONTAINER REGISTRY SIMULATOR
  Bab 10: Production Deployment dan Container Registries
================================================================================{CLR_RESET}
"""
    print(banner)


def status_msg(level: str, text: str):
    if level == "INFO":
        print(f"[{CLR_BLUE}INFO{CLR_RESET}] {text}")
    elif level == "SUCCESS":
        print(f"[{CLR_GREEN}SUCCESS{CLR_RESET}] {text}")
    elif level == "WARN":
        print(f"[{CLR_YELLOW}WARNING{CLR_RESET}] {text}")
    elif level == "FAIL":
        print(f"[{CLR_RED}FAILURE{CLR_RESET}] {text}")
    elif level == "STEP":
        print(f"\n{CLR_BOLD}{CLR_MAGENTA}>>> {text}{CLR_RESET}")


@dataclass
class ImageLayer:
    layer_id: str
    size_mb: int
    command: str
    digest: str = ""

    def __post_init__(self):
        if not self.digest:
            raw_hash = hashlib.sha256(f"{self.layer_id}:{self.command}".encode()).hexdigest()
            self.digest = f"sha256:{raw_hash[:16]}"


@dataclass
class ContainerImage:
    repository: str
    tag: str
    layers: List[ImageLayer]
    manifest_digest: str = ""

    def calculate_manifest(self) -> str:
        payload = f"{self.repository}:{self.tag}:" + ":".join([l.digest for l in self.layers])
        raw_hash = hashlib.sha256(payload.encode()).hexdigest()
        self.manifest_digest = f"sha256:{raw_hash}"
        return self.manifest_digest


class MockRegistry:
    def __init__(self, domain: str = "registry.internal.corp"):
        self.domain = domain
        self.blob_store: Dict[str, ImageLayer] = {}
        self.manifest_store: Dict[str, Dict[str, ContainerImage]] = {}  # repo -> tag -> Image

    def push_image(self, image: ContainerImage):
        status_msg("STEP", f"Memulai docker push ke {self.domain}/{image.repository}:{image.tag}")
        repo_manifests = self.manifest_store.setdefault(image.repository, {})

        for layer in image.layers:
            time.sleep(0.15)
            if layer.digest in self.blob_store:
                print(f"  Layer {CLR_YELLOW}{layer.digest[:12]}{CLR_RESET} -> {CLR_GREEN}Layer already exists (Deduplication Hit){CLR_RESET}")
            else:
                self.blob_store[layer.digest] = layer
                print(f"  Layer {CLR_CYAN}{layer.digest[:12]}{CLR_RESET} -> {CLR_WHITE}Pushed ({layer.size_mb} MB){CLR_RESET}")

        image.calculate_manifest()
        repo_manifests[image.tag] = image
        print(f"  Manifest Digest: {CLR_BOLD}{CLR_GREEN}{image.manifest_digest}{CLR_RESET}")
        status_msg("SUCCESS", f"Image berhasil terdaftar di remote registry: {self.domain}/{image.repository}:{image.tag}")


class SecurityScanner:
    @staticmethod
    def scan_image(image: ContainerImage) -> bool:
        status_msg("STEP", f"Menjalankan Static Vulnerability Scanner (Trivy/Clair Mode) pada {image.repository}:{image.tag}")
        time.sleep(0.3)
        vulnerabilities = [
            {"cve": "CVE-2024-21626", "severity": "HIGH", "pkg": "runc", "fixed": "1.1.12"},
            {"cve": "CVE-2023-44487", "severity": "MEDIUM", "pkg": "nghttp2", "fixed": "1.57.0"},
            {"cve": "CVE-2024-6387", "severity": "CRITICAL", "pkg": "openssh-server", "fixed": "9.8p1"},
        ]

        found_issues = []
        # Deteksi apakah image menggunakan package rentan secara acak
        random.seed(image.tag)
        sample_detected = random.sample(vulnerabilities, k=random.randint(0, 2))

        print(f"{CLR_BOLD}{'CVE ID':<18} {'SEVERITY':<12} {'PACKAGE':<18} {'FIXED VERSION'}{CLR_RESET}")
        print("-" * 65)

        blocked = False
        if not sample_detected:
            print(f"{CLR_GREEN}0 Vulnerabilities detected. Image bersih dan siap diproduksi.{CLR_RESET}")
            return True

        for issue in sample_detected:
            color = CLR_RED if issue["severity"] in ["CRITICAL", "HIGH"] else CLR_YELLOW
            print(f"{issue['cve']:<18} {color}{issue['severity']:<12}{CLR_RESET} {issue['pkg']:<18} {issue['fixed']}")
            if issue["severity"] in ["CRITICAL", "HIGH"]:
                blocked = True

        if blocked:
            status_msg("FAIL", "Deployment Gate DITOLAK: Ditemukan kerentanan CRITICAL/HIGH!")
            return False
        else:
            status_msg("WARN", "Hanya kerentanan berisiko rendah/sedang. Deployment diizinkan bersyarat.")
            return True


class BlueGreenDeployer:
    def __init__(self):
        self.active_slot = "BLUE"
        self.blue_version = "v1.2.0"
        self.green_version = "idle"
        self.traffic_weight_blue = 100
        self.traffic_weight_green = 0

    def show_topology(self):
        print("\n" + "=" * 60)
        print(f"{CLR_BOLD}STATUS TOPOLOGI PRODUKSI (Load Balancer & Reverse Proxy){CLR_RESET}")
        print("-" * 60)
        active_blue = f"{CLR_GREEN}[ACTIVE ({self.traffic_weight_blue}%)]" if self.active_slot == "BLUE" else f"{CLR_WHITE}[STANDBY ({self.traffic_weight_blue}%)]"
        active_green = f"{CLR_GREEN}[ACTIVE ({self.traffic_weight_green}%)]" if self.active_slot == "GREEN" else f"{CLR_WHITE}[STANDBY ({self.traffic_weight_green}%)]"

        print(f"Slot BLUE  : image: {self.blue_version:<15} {active_blue}{CLR_RESET}")
        print(f"Slot GREEN : image: {self.green_version:<15} {active_green}{CLR_RESET}")
        print("=" * 60 + "\n")

    def deploy_new_version(self, new_tag: str):
        target_slot = "GREEN" if self.active_slot == "BLUE" else "BLUE"
        status_msg("STEP", f"Memulai Blue/Green Deployment: Provisioning Slot [{target_slot}] dengan versi {new_tag}")

        if target_slot == "GREEN":
            self.green_version = new_tag
        else:
            self.blue_version = new_tag

        # Healthcheck Phase
        print("Memulai healthcheck container target...")
        for i in range(1, 4):
            time.sleep(0.2)
            print(f"  Probe HTTP GET /healthz (Attempt {i}/3) -> {CLR_GREEN}200 OK{CLR_RESET}")

        status_msg("SUCCESS", f"Target slot [{target_slot}] dinyatakan HEALTHY dan siap menerima trafik.")

        # Canary Traffic Shift
        status_msg("STEP", "Melakukan Cutover Trafik Bertahap pada Ingress Gateway...")
        shifts = [(90, 10), (50, 50), (10, 90), (0, 100)] if target_slot == "GREEN" else [(10, 90), (50, 50), (90, 10), (100, 0)]
        for b_w, g_w in shifts:
            time.sleep(0.15)
            self.traffic_weight_blue = b_w
            self.traffic_weight_green = g_w
            print(f"  Trafik Router: BLUE={b_w}% | GREEN={g_w}%")

        self.active_slot = target_slot
        status_msg("SUCCESS", f"Cutover 100% Selesai! Slot aktif saat ini adalah [{self.active_slot}].")
        self.show_topology()


def run_full_pipeline_simulation():
    registry = MockRegistry("registry-prod.internal.net")
    deployer = BlueGreenDeployer()

    # Step 1: Base image layer setup
    base_layers = [
        ImageLayer("layer-1", 45, "FROM alpine:3.20"),
        ImageLayer("layer-2", 15, "RUN apk add --no-cache ca-certificates"),
        ImageLayer("layer-3", 110, "COPY app-binary /usr/local/bin/app"),
    ]

    img_v1 = ContainerImage("payment-api", "v1.2.0", base_layers)
    registry.push_image(img_v1)
    deployer.show_topology()

    # Step 2: Next version with layer caching
    print(f"\n{CLR_BOLD}{CLR_CYAN}--- MEMBUAT REVISI BARU UNTUK PRODUCTION (v1.3.0) ---{CLR_RESET}")
    v2_layers = [
        base_layers[0],  # Cached
        base_layers[1],  # Cached
        ImageLayer("layer-4", 115, "COPY app-binary /usr/local/bin/app (patched v1.3.0)"),
    ]
    img_v2 = ContainerImage("payment-api", "v1.3.0-git-8f92a1d", v2_layers)
    registry.push_image(img_v2)

    # Step 3: Security Scan Gate
    passed = SecurityScanner.scan_image(img_v2)
    if not passed:
        status_msg("FAIL", "Pipeline Diberhentikan otomatis oleh CI/CD gate.")
        return

    # Step 4: Zero Downtime Deployment
    deployer.deploy_new_version(img_v2.tag)
    status_msg("SUCCESS", "Simulasi siklus penuh CI/CD Production & Registry selesai dengan sukses!")


def interactive_menu():
    print_banner()
    registry = MockRegistry()
    deployer = BlueGreenDeployer()

    base_layers = [
        ImageLayer("layer-alpine", 28, "FROM alpine:3.20"),
        ImageLayer("layer-deps", 35, "RUN apk add --no-cache nodejs"),
        ImageLayer("layer-code", 12, "COPY . /app"),
    ]

    while True:
        print(f"\n{CLR_BOLD}PILIHAN LAB INTERAKTIF:{CLR_RESET}")
        print("1. Periksa Topologi Cluster Produksi (Active/Passive Slot)")
        print("2. Simulasi Push Image ke Private Container Registry (Layer Deduplication)")
        print("3. Uji Security Vulnerability Gate (Static CVE Analysis)")
        print("4. Eksekusi Zero-Downtime Blue/Green Deployment")
        print("5. Jalankan Simulasi Otomatis Siklus Penuh (End-to-End CI/CD Pipeline)")
        print("0. Keluar dari Laboratorium")

        choice = input(f"\n{CLR_YELLOW}Pilih opsi [0-5]: {CLR_RESET}").strip()

        if choice == "1":
            deployer.show_topology()
        elif choice == "2":
            tag_name = input("Masukkan tag rilis baru (contoh: v2.0.1-prod): ").strip() or "v2.0.1"
            custom_layers = [
                base_layers[0],
                base_layers[1],
                ImageLayer(f"layer-{int(time.time())}", random.randint(10, 50), f"COPY ./dist /app (tag: {tag_name})"),
            ]
            img = ContainerImage("core-service", tag_name, custom_layers)
            registry.push_image(img)
        elif choice == "3":
            mock_img = ContainerImage("auth-gateway", "v1.0.4", base_layers)
            SecurityScanner.scan_image(mock_img)
        elif choice == "4":
            new_tag = input("Masukkan versi image baru untuk di-rollout: ").strip() or "v2.1.0-release"
            deployer.deploy_new_version(new_tag)
        elif choice == "5":
            run_full_pipeline_simulation()
        elif choice == "0":
            print(f"\n{CLR_GREEN}Menutup laboratorium. Sampai jumpa di modul berikutnya!{CLR_RESET}\n")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan coba lagi.{CLR_RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["--auto", "--test", "-y"]:
        print_banner()
        run_full_pipeline_simulation()
    else:
        # Jika dijalankan di lingkungan non-interactive / pipe, langsung jalankan auto demo
        if not sys.stdin.isatty():
            print_banner()
            run_full_pipeline_simulation()
        else:
            try:
                interactive_menu()
            except KeyboardInterrupt:
                print(f"\n\n{CLR_YELLOW}Operasi dibatalkan pengguna. Keluar.{CLR_RESET}")
                sys.exit(0)
