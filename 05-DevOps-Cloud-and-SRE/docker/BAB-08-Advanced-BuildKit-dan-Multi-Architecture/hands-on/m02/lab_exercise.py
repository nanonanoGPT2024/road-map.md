#!/usr/bin/env python3
"""
Lab Exercise: BAB-08 - Advanced BuildKit & Multi-Architecture Engine
Simulasi Interaktif Arsitektur Produksi Docker BuildKit, Mounts Cache/Secret,
dan Multi-Arch Manifest List Synthesis.
"""

import sys
import time
import json
import random
import argparse
from typing import Dict, List, Any

# ANSI Terminal Styling
class TermColor:
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
    BG_MAGENTA = "\033[45m"

def print_banner():
    banner = f"""
{TermColor.CYAN}{TermColor.BOLD}================================================================================
  DOCKER BUILDKIT & MULTI-ARCH PRODUCTION SIMULATOR (BAB-08)
  LLB Solver | Cache Mounts | Secret Ingestion | OCI Multi-Arch Index
================================================================================{TermColor.RESET}
"""
    print(banner)

def log_info(msg: str):
    print(f"{TermColor.BLUE}[INFO]{TermColor.RESET} {msg}")

def log_success(msg: str):
    print(f"{TermColor.GREEN}[SUCCESS]{TermColor.RESET} {msg}")

def log_buildkit(step: str, detail: str, cached: bool = False):
    tag = f"{TermColor.YELLOW}=> [CACHED]{TermColor.RESET}" if cached else f"{TermColor.CYAN}=>{TermColor.RESET}"
    print(f"{tag} {TermColor.BOLD}{step:<35}{TermColor.RESET} | {TermColor.DIM}{detail}{TermColor.RESET}")

def render_progress_bar(label: str, duration: float = 1.0, steps: int = 25):
    for i in range(steps + 1):
        percent = int((i / steps) * 100)
        filled = "=" * i
        spaces = " " * (steps - i)
        sys.stdout.write(f"\r  {TermColor.MAGENTA}{label}{TermColor.RESET} [{filled}>{spaces}] {percent}%")
        sys.stdout.flush()
        time.sleep(duration / steps)
    print()

class BuildKitSimulator:
    def __init__(self, mode_interactive: bool = True):
        self.interactive = mode_interactive
        self.cache_store = {
            "go_mod_cache": True,
            "apt_cache": True,
            "npm_cache": False
        }
        self.secrets = {
            "github_token": "ghp_secureProductionToken9872134",
            "aws_creds": "[profile prod]\naws_access_key_id=AKIAIOSFODNN7"
        }

    def simulate_cache_and_secret_mounts(self):
        print(f"\n{TermColor.BOLD}{TermColor.YELLOW}--- [SKENARIO 1] BuildKit Advanced Mounts (Secret & Cache) ---{TermColor.RESET}")
        print("Menganalisis instruksi Dockerfile dengan BuildKit syntax modern:")
        print(f"{TermColor.DIM}#syntax=docker/dockerfile:1.4")
        print("RUN --mount=type=cache,target=/root/.cache/go-build,id=go_cache \\")
        print("    --mount=type=cache,target=/go/pkg/mod,id=go_mod \\")
        print("    --mount=type=secret,id=gh_token,target=/run/secrets/gh_token,required=true \\")
        print(f"    go build -v -o /out/api ./cmd/api{TermColor.RESET}\n")

        log_info("1. Menginisialisasi BuildKit Worker & LLB Solver (Low-Level Builder DAG)...")
        time.sleep(0.3)
        log_buildkit("Resolve base image", "docker.io/library/golang:1.22-alpine", cached=True)
        log_buildkit("Mount temporary secret", "Mounting fd secret to /run/secrets/gh_token (in-memory ramfs)")
        
        # Verify secret is not written to layers
        print(f"  {TermColor.GREEN}✓ Secret terisolasi di RAM: TIDAK bocor ke layer filesystem metadata!{TermColor.RESET}")
        
        time.sleep(0.4)
        cached_mod = self.cache_store["go_mod_cache"]
        log_buildkit("Mount persistent cache", "/go/pkg/mod (id=go_mod, mode=0755)", cached=cached_mod)
        if cached_mod:
            log_success("Cache hit! 45 dependencies ter-resolve seketika dari cache host.")
        else:
            render_progress_bar("Downloading Go dependencies", 0.8)
            self.cache_store["go_mod_cache"] = True

        render_progress_bar("Compiling Go binary", 0.6)
        log_buildkit("Output stage compilation", "Binary target: /out/api (ELF 64-bit LSB)", cached=False)
        log_success("Skenario 1 Selesai: Image terkompilasi aman tanpa jejak kredensial pada layer history.\n")

    def simulate_multi_arch_manifest(self):
        print(f"\n{TermColor.BOLD}{TermColor.YELLOW}--- [SKENARIO 2] Multi-Architecture Buildx & OCI Manifest List ---{TermColor.RESET}")
        platforms = ["linux/amd64", "linux/arm64", "linux/arm/v7"]
        print(f"Target platform: {', '.join(platforms)}")
        print("Menjalankan solver paralel menggunakan Docker Buildx driver 'docker-container'...")
        
        manifest_entries = []
        for plat in platforms:
            print(f"\n{TermColor.BOLD}>>> Worker Pipeline untuk platform [{plat}]:{TermColor.RESET}")
            is_qemu = ("arm" in plat)
            builder_type = "QEMU user-static emulation" if is_qemu else "Native host execution"
            print(f"  Executor : {TermColor.CYAN}{builder_type}{TermColor.RESET}")
            
            render_progress_bar(f"Building {plat}", 0.7 if is_qemu else 0.4)
            digest = f"sha256:{random.getrandbits(256):064x}"
            size_mb = round(random.uniform(42.0, 48.5), 2)
            manifest_entries.append({
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": digest,
                "size": int(size_mb * 1024 * 1024),
                "platform": {
                    "architecture": plat.split("/")[1],
                    "os": "linux",
                    "variant": plat.split("/")[2] if len(plat.split("/")) > 2 else None
                }
            })
            log_buildkit(f"Export layer {plat}", f"Digest: {digest[:19]}... ({size_mb} MB)")

        print(f"\n{TermColor.BOLD}Membangun OCI Image Index (Multi-Arch Manifest List):{TermColor.RESET}")
        time.sleep(0.5)
        index_manifest = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": manifest_entries
        }
        print(f"{TermColor.DIM}{json.dumps(index_manifest, indent=2)}{TermColor.RESET}")
        log_success("Multi-arch index berhasil di-push ke registry simulasi!")

    def simulate_registry_cache_exporter(self):
        print(f"\n{TermColor.BOLD}{TermColor.YELLOW}--- [SKENARIO 3] Remote Registry Cache (cache-to / cache-from) ---{TermColor.RESET}")
        print("Sintaks CI/CD Enterprise:")
        print(f"{TermColor.DIM}docker buildx build \\")
        print("  --cache-to type=registry,ref=registry.internal.net/cache:app-v2,mode=max \\")
        print("  --cache-from type=registry,ref=registry.internal.net/cache:app-v2 \\")
        print(f"  --push -t registry.internal.net/prod/app:2.5.0 .{TermColor.RESET}\n")

        render_progress_bar("Importing remote metadata cache", 0.5)
        log_buildkit("Check manifest cache", "Checking SHA hash of LLB stages against remote index")
        
        stages = [
            ("Stage 0 (base-deps)", True, "0.1s"),
            ("Stage 1 (build-frontend)", True, "0.2s"),
            ("Stage 2 (compile-backend)", False, "4.8s (Code changed in /pkg/router)"),
            ("Stage 3 (final-runtime)", False, "0.4s (Copying fresh binary)")
        ]

        for stage, is_cached, timing in stages:
            log_buildkit(stage, f"Execution time: {timing}", cached=is_cached)
            time.sleep(0.25)

        print(f"\n{TermColor.CYAN}Mengunggah intermediate layers dan metadata cache (mode=max)...{TermColor.RESET}")
        render_progress_bar("Exporting cache layers to remote", 0.6)
        log_success("Remote cache sink tersinkronisasi. Build pipeline berikutnya menghemat 78% durasi.")

    def run_full_diagnostic(self):
        print(f"\n{TermColor.BOLD}{TermColor.CYAN}>>> Menjalankan Audit Kesiapan BuildKit & Platform Host <<<{TermColor.RESET}")
        checks = [
            ("Docker BuildKit Daemon State", "ENABLED (DOCKER_BUILDKIT=1)"),
            ("Buildx Instance Driver", "docker-container (multi-node active)"),
            ("QEMU Binfmt Emulation Support", "aarch64, arm, riscv64, ppc64le [OK]"),
            ("Cache Mount Isolation", "Private inode namespace verify [PASSED]"),
            ("Secret RAMFS Zero-Persistence", "Checked /proc/self/mountinfo [VERIFIED]")
        ]
        for name, res in checks:
            time.sleep(0.2)
            print(f"  [✓] {name:<35}: {TermColor.GREEN}{res}{TermColor.RESET}")
        print()

    def interactive_menu(self):
        while True:
            print(f"\n{TermColor.BOLD}PILIHAN LAB INTERAKTIF (BAB-08):{TermColor.RESET}")
            print("  1. Simulasi Advanced BuildKit Mounts (Cache & Secret Isolation)")
            print("  2. Simulasi Multi-Architecture Buildx & OCI Manifest Matrix")
            print("  3. Simulasi Remote Registry Cache (cache-to / cache-from mode=max)")
            print("  4. Audit Kesiapan BuildKit Host & Platform Drivers")
            print("  5. Jalankan Semua Modul (End-to-End Test)")
            print("  0. Keluar")
            
            try:
                choice = input(f"\n{TermColor.CYAN}Pilih menu [0-5]: {TermColor.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSelesai.")
                break

            if choice == "1":
                self.simulate_cache_and_secret_mounts()
            elif choice == "2":
                self.simulate_multi_arch_manifest()
            elif choice == "3":
                self.simulate_registry_cache_exporter()
            elif choice == "4":
                self.run_full_diagnostic()
            elif choice == "5":
                self.simulate_cache_and_secret_mounts()
                self.simulate_multi_arch_manifest()
                self.simulate_registry_cache_exporter()
                self.run_full_diagnostic()
            elif choice == "0":
                print(f"{TermColor.GREEN}Terima kasih telah menyelesaikan Lab BuildKit & Multi-Arch.{TermColor.RESET}")
                break
            else:
                print(f"{TermColor.RED}Pilihan tidak valid. Silakan coba lagi.{TermColor.RESET}")

def main():
    parser = argparse.ArgumentParser(description="BuildKit & Multi-Arch Production Simulation Lab")
    parser.add_argument("--auto", action="store_true", help="Jalankan seluruh simulasi secara otomatis tanpa interaksi")
    args = parser.parse_args()

    print_banner()
    sim = BuildKitSimulator(mode_interactive=not args.auto)

    # If running non-interactively or in automated test mode
    if args.auto or not sys.stdin.isatty():
        log_info("Mode otomatis / Non-TTY terdeteksi. Menjalankan skenario secara berurutan...")
        sim.simulate_cache_and_secret_mounts()
        sim.simulate_multi_arch_manifest()
        sim.simulate_registry_cache_exporter()
        sim.run_full_diagnostic()
        log_success("Semua simulasi BAB-08 berhasil diselesaikan 100%!")
    else:
        sim.interactive_menu()

if __name__ == "__main__":
    main()
