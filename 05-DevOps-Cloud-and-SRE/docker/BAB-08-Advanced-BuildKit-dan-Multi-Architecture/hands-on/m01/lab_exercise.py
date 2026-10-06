#!/usr/bin/env python3
"""
Lab Exercise M01: Advanced BuildKit & Multi-Architecture Engine Simulator
BAB-08-Advanced-BuildKit-dan-Multi-Architecture
Mata Kuliah / Modul: Docker & Container Runtime Internals
"""

import sys
import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


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


class Arch(Enum):
    AMD64 = "linux/amd64"
    ARM64 = "linux/arm64"
    ARMV7 = "linux/arm/v7"
    RISCV64 = "linux/riscv64"


@dataclass
class LLBVertex:
    name: str
    command: str
    dependencies: List[str] = field(default_factory=list)
    mount_type: Optional[str] = None
    cache_hit: bool = False
    duration: float = 0.6
    sha256: str = ""

    def calculate_digest(self) -> str:
        raw = f"{self.name}:{self.command}:{self.mount_type}"
        self.sha256 = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return self.sha256


class BuildKitSimulator:
    def __init__(self):
        self.buildkit_version = "v0.13.1 (BuildX driver: docker-container)"
        self.cache_registry: Dict[str, str] = {}

    def banner(self):
        print(f"\n{Color.CYAN}{Color.BOLD}╔════════════════════════════════════════════════════════════════╗{Color.RESET}")
        print(f"{Color.CYAN}{Color.BOLD}║     DOCKER BUILDKIT & MULTI-ARCH ARCHITECTURE LAB (BAB-08)     ║{Color.RESET}")
        print(f"{Color.CYAN}{Color.BOLD}╚════════════════════════════════════════════════════════════════╝{Color.RESET}")
        print(f"{Color.DIM}Engine: BuildKit {self.buildkit_version}{Color.RESET}\n")

    def simulate_llb_dag(self):
        print(f"{Color.YELLOW}{Color.BOLD}[1/4] SIMULASI BUILDKIT LLB (LOW-LEVEL BUILDER) DAG SOLVER{Color.RESET}")
        print(f"{Color.DIM}Analisis graf asiklik terarah (DAG) dan eksekusi paralel independen...{Color.RESET}\n")

        vertices = [
            LLBVertex("base", "FROM golang:1.22-alpine AS base", []),
            LLBVertex("deps", "RUN --mount=type=cache,target=/go/pkg/mod go mod download", ["base"], mount_type="cache"),
            LLBVertex("lint", "RUN golangci-lint run", ["deps"], duration=0.8),
            LLBVertex("secret", "RUN --mount=type=secret,id=npm_token cat /run/secrets/npm_token", ["base"], mount_type="secret", duration=0.4),
            LLBVertex("compile", "RUN --mount=type=cache,target=/root/.cache/go-build go build -o app", ["deps"], mount_type="cache", duration=1.0),
            LLBVertex("runtime", "FROM alpine:3.19 AS runtime", []),
            LLBVertex("export", "COPY --from=compile /app /bin/app", ["compile", "runtime"], duration=0.5),
        ]

        for v in vertices:
            v.calculate_digest()

        print(f"{Color.BLUE}Generated LLB Graph Definitions (7 vertices):{Color.RESET}")
        for v in vertices:
            deps_str = f"<- [{', '.join(v.dependencies)}]" if v.dependencies else "(root)"
            mount_str = f" {Color.MAGENTA}[{v.mount_type.upper()} MOUNT]{Color.RESET}" if v.mount_type else ""
            print(f"  {Color.GREEN}sha256:{v.sha256}{Color.RESET} | {Color.BOLD}{v.name:<8}{Color.RESET} {deps_str:<22}{mount_str}")

        print(f"\n{Color.CYAN}Memulai eksekusi DAG paralel...{Color.RESET}")
        time.sleep(0.5)

        for v in vertices:
            sys.stdout.write(f"  ==> [{v.name}] {v.command[:50]}... ")
            sys.stdout.flush()
            time.sleep(v.duration * 0.5)
            if v.mount_type == "cache":
                status = f"{Color.GREEN}DONE (CACHE HIT){Color.RESET}"
            elif v.mount_type == "secret":
                status = f"{Color.MAGENTA}DONE (SECRET SAFE IN MEMFS){Color.RESET}"
            else:
                status = f"{Color.CYAN}DONE{Color.RESET}"
            print(status)

        print(f"{Color.GREEN}✓ LLB Pipeline berhasil dirangkai tanpa leaking layer secrets.{Color.RESET}\n")

    def simulate_secret_leak_vs_mount(self):
        print(f"{Color.YELLOW}{Color.BOLD}[2/4] AUDIT KEAMANAN: ARG/ENV VS BUILDKIT SECRET MOUNT{Color.RESET}")
        print(f"{Color.DIM}Membandingkan jejak histori citra antara ARG konvensional dan --mount=type=secret{Color.RESET}\n")

        dummy_token = "ghp_SuperSecretCredential998877665544"
        print(f"Token sensitif yang diuji: {Color.RED}{dummy_token}{Color.RESET}")

        print(f"\n{Color.RED}Skenario A: Konvensional (ARG & RUN export){Color.RESET}")
        print(f"  Dockerfile: ARG GITHUB_TOKEN; RUN echo export GITHUB_TOKEN=$GITHUB_TOKEN >> /root/.bashrc")
        print(f"  {Color.RED}[!] Status Layer Tarball: LEAKED IN IMAGE METADATA!{Color.RESET}")
        print(f"  Docker History: {Color.DIM}RUN /bin/sh -c echo export GITHUB_TOKEN={dummy_token[:8]}... (Size: 42B){Color.RESET}")

        print(f"\n{Color.GREEN}Skenario B: BuildKit Secret Mount (--mount=type=secret,id=my_secret){Color.RESET}")
        print(f"  Dockerfile: RUN --mount=type=secret,id=token cat /run/secrets/token | auth-cli")
        print(f"  {Color.GREEN}[✓] Status Layer Tarball: SECURE (Mounted via tmpfs in-memory during step){Color.RESET}")
        print(f"  Docker History: {Color.DIM}RUN --mount=type=secret... (Size: 0B / Zero Byte Diff){Color.RESET}")
        print()

    def simulate_multi_arch_matrix(self):
        print(f"{Color.YELLOW}{Color.BOLD}[3/4] MULTI-ARCHITECTURE BUILDX RUNNER MATRIX{Color.RESET}")
        print(f"{Color.DIM}Membangun citra ke multi-platform target (QEMU vs Native Node Builder)...{Color.RESET}\n")

        architectures = [
            (Arch.AMD64, "Native x86_64", 0.4, "x86_64 sysv"),
            (Arch.ARM64, "QEMU binfmt_misc (aarch64)", 0.9, "aarch64 aapcs-linux"),
            (Arch.ARMV7, "QEMU binfmt_misc (armhf)", 1.0, "armv7l eabihf"),
            (Arch.RISCV64, "Cross-Compiling via GOARCH=riscv64", 0.3, "riscv64"),
        ]

        built_manifests = []

        for arch, method, latency, abi in architectures:
            print(f"Building platform {Color.CYAN}{arch.value}{Color.RESET} via {method}:")
            steps = ["Fetching base rootfs", "Cross-compiling ELF binary", "Squashing layer digests"]
            for step in steps:
                sys.stdout.write(f"  [{arch.value}] {step}... ")
                sys.stdout.flush()
                time.sleep(latency * 0.25)
                print(f"{Color.GREEN}OK{Color.RESET}")

            digest = hashlib.sha256(f"image:{arch.value}:{abi}".encode()).hexdigest()
            built_manifests.append({
                "platform": {
                    "architecture": arch.value.split("/")[1],
                    "os": arch.value.split("/")[0],
                },
                "digest": f"sha256:{digest[:32]}",
                "size": 18450124 + len(arch.value) * 1024,
            })
            print(f"  Target ABI: {Color.BOLD}{abi}{Color.RESET} -> Digest: {Color.DIM}sha256:{digest[:16]}...{Color.RESET}\n")

        return built_manifests

    def simulate_oci_index_manifest(self, manifests: List[Dict]):
        print(f"{Color.YELLOW}{Color.BOLD}[4/4] PERAKITAN OCI IMAGE INDEX / DOCKER MANIFEST LIST{Color.RESET}")
        print(f"{Color.DIM}Menyatukan manifest platform individu menjadi 'Fat Manifest' OCI v1...{Color.RESET}\n")

        oci_index = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": manifests,
        }

        formatted_json = json.dumps(oci_index, indent=2)
        print(f"{Color.CYAN}{formatted_json}{Color.RESET}")

        index_digest = hashlib.sha256(formatted_json.encode()).hexdigest()
        print(f"\n{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} TAG PUBLISH SUCCESS {Color.RESET}")
        print(f"Repository Tag : {Color.BOLD}registry.local/infra/universal-service:latest{Color.RESET}")
        print(f"Fat Manifest ID: {Color.MAGENTA}sha256:{index_digest}{Color.RESET}")
        print(f"\nKetika user menarik tag 'latest':")
        print(f"  • Node Apple Silicon / AWS Graviton -> Docker otomatis routing ke {Color.CYAN}linux/arm64{Color.RESET}")
        print(f"  • Node Intel Xeon / AMD EPYC        -> Docker otomatis routing ke {Color.CYAN}linux/amd64{Color.RESET}")
        print(f"  • Edge IoT Gateway (Raspberry Pi)   -> Docker otomatis routing ke {Color.CYAN}linux/arm/v7{Color.RESET}\n")


def interactive_menu():
    sim = BuildKitSimulator()
    sim.banner()

    options = {
        "1": ("Simulasi LLB DAG Solver & Concurrent Pipeline", sim.simulate_llb_dag),
        "2": ("Audit Keamanan: BuildKit Secret Mount vs ARG", sim.simulate_secret_leak_vs_mount),
        "3": ("Multi-Arch BuildX Matrix & Manifest Assembly", None),
        "4": ("Jalankan Seluruh Pipeline End-to-End", None),
        "q": ("Keluar", sys.exit),
    }

    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print(f"{Color.BOLD}Menjalankan mode otomatis (--auto)...{Color.RESET}\n")
        sim.simulate_llb_dag()
        sim.simulate_secret_leak_vs_mount()
        manifests = sim.simulate_multi_arch_matrix()
        sim.simulate_oci_index_manifest(manifests)
        return

    while True:
        print(f"{Color.BOLD}Menu Simulasi Interaktif BuildKit & Multi-Arch:{Color.RESET}")
        for key, (label, _) in options.items():
            print(f"  [{Color.CYAN}{key}{Color.RESET}] {label}")
        
        choice = input(f"\nPilih opsi [1-4, q] (default: 4): ").strip().lower()
        if not choice:
            choice = "4"

        print()
        if choice == "1":
            sim.simulate_llb_dag()
        elif choice == "2":
            sim.simulate_secret_leak_vs_mount()
        elif choice == "3":
            manifests = sim.simulate_multi_arch_matrix()
            sim.simulate_oci_index_manifest(manifests)
        elif choice == "4":
            sim.simulate_llb_dag()
            sim.simulate_secret_leak_vs_mount()
            manifests = sim.simulate_multi_arch_matrix()
            sim.simulate_oci_index_manifest(manifests)
            break
        elif choice == "q":
            print("Keluar dari lab simulation.")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, coba lagi.{Color.RESET}\n")


if __name__ == "__main__":
    interactive_menu()
