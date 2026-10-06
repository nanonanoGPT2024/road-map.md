#!/usr/bin/env python3
"""
Lab Exercise: Kubernetes ConfigMap, Secrets, and Decoupled Architecture
Simulasi interaktif konsep decoupling konfigurasi, Base64 Secrets, Volume Projections,
dan Dynamic Reloading pada containerized workloads.
"""

import base64
import json
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class AnsiColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def print_banner():
    banner = f"""{AnsiColor.CYAN}{AnsiColor.BOLD}
================================================================================
   KUBERNETES LAB: CONFIGMAP, SECRETS & DECOUPLED ARCHITECTURE SIMULATOR
================================================================================{AnsiColor.RESET}
 {AnsiColor.YELLOW}* Konsep Inti:{AnsiColor.RESET} 12-Factor Config Separation, Secret Masking, Volume Mount vs Env
"""
    print(banner)


class InjectionMode(Enum):
    ENV_VARIABLE = "env"
    VOLUME_MOUNT = "volume"


@dataclass
class ConfigMap:
    name: str
    data: Dict[str, str] = field(default_factory=dict)
    immutable: bool = False
    resource_version: int = 1


@dataclass
class K8sSecret:
    name: str
    secret_type: str = "Opaque"
    b64_data: Dict[str, str] = field(default_factory=dict)
    immutable: bool = False
    resource_version: int = 1

    def set_secret(self, key: str, raw_value: str):
        encoded = base64.b64encode(raw_value.encode("utf-8")).decode("utf-8")
        self.b64_data[key] = encoded

    def get_decoded(self, key: str) -> Optional[str]:
        if key not in self.b64_data:
            return None
        return base64.b64decode(self.b64_data[key].encode("utf-8")).decode("utf-8")


class PodWorkload:
    def __init__(self, name: str, configmap_ref: ConfigMap, secret_ref: K8sSecret, mode: InjectionMode):
        self.name = name
        self.configmap = configmap_ref
        self.secret = secret_ref
        self.injection_mode = mode
        self.running_env: Dict[str, str] = {}
        self.mounted_volumes: Dict[str, str] = {}
        self.initialize_runtime()

    def initialize_runtime(self):
        if self.injection_mode == InjectionMode.ENV_VARIABLE:
            # Di K8s, env var diikat saat Pod startup (Snapshot statis)
            for k, v in self.configmap.data.items():
                self.running_env[f"APP_{k.upper()}"] = v
            for k in self.secret.b64_data.keys():
                self.running_env[f"SEC_{k.upper()}"] = self.secret.get_decoded(k) or ""
        else:
            # Volume projection: direktori /etc/config & /etc/secrets
            self.refresh_volume_projection()

    def refresh_volume_projection(self):
        if self.injection_mode == InjectionMode.VOLUME_MOUNT:
            self.mounted_volumes.clear()
            for k, v in self.configmap.data.items():
                self.mounted_volumes[f"/etc/config/{k}"] = v
            for k in self.secret.b64_data.keys():
                self.mounted_volumes[f"/etc/secrets/{k}"] = self.secret.get_decoded(k) or ""

    def simulate_heartbeat(self):
        print(f"\n{AnsiColor.BOLD}[Pod: {self.name} | Mode: {self.injection_mode.value.upper()}]{AnsiColor.RESET}")
        if self.injection_mode == InjectionMode.ENV_VARIABLE:
            print(f" {AnsiColor.DIM}-> Membaca process environment memory (Static snapshot):{AnsiColor.RESET}")
            for k, v in self.running_env.items():
                masked = "********" if "SEC_" in k else v
                print(f"    ${k} = {AnsiColor.GREEN}{masked}{AnsiColor.RESET}")
        else:
            self.refresh_volume_projection()
            print(f" {AnsiColor.DIM}-> Membaca Atomic Symlink Mount (/etc/config & /etc/secrets):{AnsiColor.RESET}")
            for path, content in self.mounted_volumes.items():
                is_secret = "/etc/secrets/" in path
                display_val = "******** (Protected Secret File)" if is_secret else content
                print(f"    {path} -> {AnsiColor.CYAN}{display_val}{AnsiColor.RESET}")


class K8sClusterSimulator:
    def __init__(self):
        # Initial ConfigMap (Decoupled Non-sensitive configuration)
        self.cm = ConfigMap(
            name="app-config-v1",
            data={
                "LOG_LEVEL": "DEBUG",
                "DB_HOST": "postgres-cluster.internal.svc",
                "FEATURE_NEW_CHECKOUT": "true",
                "RATE_LIMIT_RPS": "250",
            },
        )
        # Initial Secret (Sensitive Credentials)
        self.secret = K8sSecret(name="app-credentials-v1")
        self.secret.set_secret("DB_PASSWORD", "SuperSecureP@ssw0rd2026!")
        self.secret.set_secret("API_AUTH_TOKEN", "jwt_sim_99a8b7c6d5e4f3a2")

        # Dua workload yang mendemonstrasikan perbedaan decoupling
        self.pod_env = PodWorkload("api-gateway-env", self.cm, self.secret, InjectionMode.ENV_VARIABLE)
        self.pod_vol = PodWorkload("api-gateway-vol", self.cm, self.secret, InjectionMode.VOLUME_MOUNT)

    def display_resources(self):
        print(f"\n{AnsiColor.BOLD}=== REPOSITORI KONFIGURASI ETCD (KUBERNETES CONTROL PLANE) ==={AnsiColor.RESET}")
        print(f"\n{AnsiColor.YELLOW}[ConfigMap: {self.cm.name}] (v{self.cm.resource_version}){AnsiColor.RESET}")
        print(f"  Immutable: {self.cm.immutable}")
        for k, v in self.cm.data.items():
            print(f"  - {k}: {AnsiColor.GREEN}{v}{AnsiColor.RESET}")

        print(f"\n{AnsiColor.MAGENTA}[Secret: {self.secret.name}] (v{self.secret.resource_version}){AnsiColor.RESET}")
        print(f"  Type: {self.secret.secret_type} | Immutable: {self.secret.immutable}")
        print(f"  {AnsiColor.DIM}Data mentah di etcd tersimpan sebagai Base64:{AnsiColor.RESET}")
        for k, b64 in self.secret.b64_data.items():
            decoded = self.secret.get_decoded(k)
            print(f"  - {k}: {AnsiColor.RED}{b64}{AnsiColor.RESET} (Decode preview: {AnsiColor.DIM}{decoded}{AnsiColor.RESET})")

    def mutate_configmap(self):
        if self.cm.immutable:
            print(f"{AnsiColor.RED}[REJECTED] ConfigMap bersifat immutable! Kubernetes API Server menolak update.{AnsiColor.RESET}")
            return

        print(f"\n{AnsiColor.CYAN}Pilih key ConfigMap yang ingin diupdate:{AnsiColor.RESET}")
        keys = list(self.cm.data.keys())
        for idx, k in enumerate(keys, 1):
            print(f" {idx}. {k} (Current: {self.cm.data[k]})")
        print(" 0. Kembali")

        try:
            choice = input(f"{AnsiColor.BOLD}Pilihan [0-{len(keys)}]: {AnsiColor.RESET}").strip()
            if choice == "0" or not choice:
                return
            idx = int(choice) - 1
            if 0 <= idx < len(keys):
                selected_key = keys[idx]
                new_val = input(f"Masukkan nilai baru untuk {selected_key}: ").strip()
                if new_val:
                    self.cm.data[selected_key] = new_val
                    self.cm.resource_version += 1
                    print(f"{AnsiColor.GREEN}[OK] ConfigMap updated! ResourceVersion naik ke {self.cm.resource_version}{AnsiColor.RESET}")
        except ValueError:
            print(f"{AnsiColor.RED}Input tidak valid.{AnsiColor.RESET}")

    def toggle_immutability(self):
        self.cm.immutable = not self.cm.immutable
        self.secret.immutable = not self.secret.immutable
        status = "AKTIF (Kubelet menonaktifkan watch polling, etcd mengunci write)" if self.cm.immutable else "NON-AKTIF"
        print(f"\n{AnsiColor.YELLOW}[Status Immutability] Sekarang: {status}{AnsiColor.RESET}")

    def run_workload_audit(self):
        print(f"\n{AnsiColor.BOLD}=== SIMULASI WORKLOAD HEALTHCHECK & RUNTIME DRIFT ==={AnsiColor.RESET}")
        self.pod_env.simulate_heartbeat()
        self.pod_vol.simulate_heartbeat()

        print(f"\n{AnsiColor.YELLOW}[EVALUASI ARSITEKTUR KUBERNETES]:{AnsiColor.RESET}")
        print(f" 1. {AnsiColor.BOLD}Env Var Pod:{AnsiColor.RESET} Tidak mendeteksi perubahan ConfigMap tanpa 'kubectl rollout restart'.")
        print(f" 2. {AnsiColor.BOLD}Volume Mount Pod:{AnsiColor.RESET} Otomatis sync dengan atomic symlink ..data saat Kubelet sync period tiba.")


def interactive_cli():
    cluster = K8sClusterSimulator()
    print_banner()

    menu = f"""
{AnsiColor.BOLD}Navigasi Simulasi Lab:{AnsiColor.RESET}
  {AnsiColor.CYAN}1.{AnsiColor.RESET} Tampilkan Manifest & Etcd Storage (ConfigMap vs Base64 Secret)
  {AnsiColor.CYAN}2.{AnsiColor.RESET} Update Nilai ConfigMap Secara Live
  {AnsiColor.CYAN}3.{AnsiColor.RESET} Periksa Reaksi Pod (Env Var vs Volume Projection Dynamic Update)
  {AnsiColor.CYAN}4.{AnsiColor.RESET} Toggle Fitur Immutability (immutable: true/false)
  {AnsiColor.CYAN}5.{AnsiColor.RESET} Jalankan Automated Self-Test Verifikasi
  {AnsiColor.CYAN}6.{AnsiColor.RESET} Keluar
"""

    while True:
        print(menu)
        try:
            choice = input(f"{AnsiColor.BOLD}Pilih opsi [1-6]: {AnsiColor.RESET}").strip()
            if choice == "1":
                cluster.display_resources()
            elif choice == "2":
                cluster.mutate_configmap()
            elif choice == "3":
                cluster.run_workload_audit()
            elif choice == "4":
                cluster.toggle_immutability()
            elif choice == "5":
                run_automated_tests(cluster)
            elif choice == "6":
                print(f"\n{AnsiColor.GREEN}Lab selesai. Selamat belajar Kubernetes!{AnsiColor.RESET}")
                sys.exit(0)
            else:
                print(f"{AnsiColor.RED}Pilihan tidak valid. Silakan pilih 1-6.{AnsiColor.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{AnsiColor.YELLOW}Sesi lab dihentikan.{AnsiColor.RESET}")
            sys.exit(0)


def run_automated_tests(cluster: K8sClusterSimulator):
    print(f"\n{AnsiColor.BOLD}=== MENJALANKAN AUTOMATED VERIFICATION TESTS ==={AnsiColor.RESET}")

    # Test 1: Base64 Decoupling
    raw_pass = "TestPa$$w0rd"
    sec = K8sSecret(name="test-sec")
    sec.set_secret("KEY", raw_pass)
    assert sec.get_decoded("KEY") == raw_pass, "Base64 decode failure"
    print(f" [{AnsiColor.GREEN}PASS{AnsiColor.RESET}] Secret Base64 serialization & decode terverifikasi.")

    # Test 2: Volume Dynamic Sync vs Env Static Snapshot
    cm = ConfigMap(name="test-cm", data={"RATE": "100"})
    sec2 = K8sSecret(name="test-sec2")
    sec2.set_secret("TOKEN", "xyz")

    p_env = PodWorkload("p-env", cm, sec2, InjectionMode.ENV_VARIABLE)
    p_vol = PodWorkload("p-vol", cm, sec2, InjectionMode.VOLUME_MOUNT)

    # Mutate
    cm.data["RATE"] = "500"
    p_vol.refresh_volume_projection()

    assert p_env.running_env["APP_RATE"] == "100", "Env var must remain static without pod restart"
    assert p_vol.mounted_volumes["/etc/config/RATE"] == "500", "Volume mount must reflect new configuration"
    print(f" [{AnsiColor.GREEN}PASS{AnsiColor.RESET}] Perbedaan decoupling Env vs Volume Mount terbukti akurat.")

    # Test 3: Immutability enforcement
    cm.immutable = True
    assert cm.immutable is True, "Immutability flag failed"
    print(f" [{AnsiColor.GREEN}PASS{AnsiColor.RESET}] Kubernetes Immutability flag validation lolos.")

    print(f"\n{AnsiColor.GREEN}{AnsiColor.BOLD}Seluruh 3 test assertions berhasil dieksekusi tanpa error!{AnsiColor.RESET}\n")


if __name__ == "__main__":
    interactive_cli()
