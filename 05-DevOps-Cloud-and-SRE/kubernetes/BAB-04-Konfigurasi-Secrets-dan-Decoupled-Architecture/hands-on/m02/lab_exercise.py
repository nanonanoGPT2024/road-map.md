#!/usr/bin/env python3
"""
Lab Exercise: Kubernetes Advanced Configuration, Secrets & Decoupled Architecture
Modul: BAB-04-Konfigurasi-Secrets-dan-Decoupled-Architecture
Topik: ConfigMap Immutability, KMS Envelope Secrets, Projected Volumes, & Hot-Reloading Patterns.
"""

import sys
import time
import base64
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ANSI Color Codes for Rich Terminal Display
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


def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}================================================================================{Color.RESET}
{Color.MAGENTA}{Color.BOLD}   KUBERNETES ADVANCED CONFIGURATION & SECRETS ARCHITECTURE SIMULATOR         {Color.RESET}
{Color.CYAN}{Color.BOLD}   BAB-04: Hands-on Lab Modul 02 - Decoupled Configuration & Runtime Sync      {Color.RESET}
{Color.CYAN}{Color.BOLD}================================================================================{Color.RESET}
"""
    print(banner)


@dataclass
class ConfigMap:
    name: str
    namespace: str
    data: Dict[str, str]
    immutable: bool = False
    resource_version: int = 1

    def compute_hash(self) -> str:
        serialized = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:10]


@dataclass
class Secret:
    name: str
    namespace: str
    type_: str
    data_b64: Dict[str, str]
    kms_encrypted: bool = True
    vault_path: Optional[str] = None

    def get_decoded(self, key: str) -> str:
        if key not in self.data_b64:
            raise KeyError(f"Key '{key}' not found in Secret {self.name}")
        raw = base64.b64decode(self.data_b64[key].encode()).decode("utf-8")
        return raw


@dataclass
class PodInstance:
    pod_id: str
    image: str
    env_vars: Dict[str, str] = field(default_factory=dict)
    mounted_volumes: Dict[str, Dict[str, str]] = field(default_factory=dict)
    config_hash: str = ""
    status: str = "Running"
    restarts: int = 0


class K8sClusterSimulation:
    def __init__(self):
        self.namespace = "production-core"
        self.config_maps: Dict[str, ConfigMap] = {}
        self.secrets: Dict[str, Secret] = {}
        self.pods: List[PodInstance] = []
        self._init_defaults()

    def _init_defaults(self):
        # 1. Immutable ConfigMap
        cm = ConfigMap(
            name="app-gateway-config",
            namespace=self.namespace,
            data={
                "gateway.timeout": "30s",
                "rate_limit.rps": "1500",
                "feature_flags.json": '{"enable_mesh": true, "tracing": "jaeger"}',
            },
            immutable=True,
            resource_version=1001,
        )
        self.config_maps[cm.name] = cm

        # 2. Production Secret (KMS Envelope Encrypted in etcd)
        db_pass = base64.b64encode(b"ProdSuperSecure_Token!9876").decode("utf-8")
        jwt_key = base64.b64encode(b"rsa-priv-4096-jwt-signature-key").decode("utf-8")
        sec = Secret(
            name="database-credentials",
            namespace=self.namespace,
            type_="Opaque",
            data_b64={"DB_PASSWORD": db_pass, "JWT_SIGNING_KEY": jwt_key},
            kms_encrypted=True,
            vault_path="secret/data/production/database",
        )
        self.secrets[sec.name] = sec

        # 3. Running Pod Replica Set
        h = cm.compute_hash()
        for i in range(1, 3):
            pod = PodInstance(
                pod_id=f"order-service-api-7d5f8c9b-{i}",
                image="registry.internal.net/apps/order-api:v2.4.1",
                env_vars={"POD_NAME": f"order-service-api-{i}", "ENV": "production"},
                mounted_volumes={
                    "/etc/config": cm.data.copy(),
                    "/etc/secrets": {"DB_PASSWORD": "***REDACTED***"},
                },
                config_hash=h,
            )
            self.pods.append(pod)

    def log_step(self, title: str):
        print(f"\n{Color.YELLOW}[PHASE] >> {Color.BOLD}{title}{Color.RESET}")

    def inspect_resources(self):
        self.log_step("1. In-Cluster Resource State Audit")
        print(f"Namespace: {Color.GREEN}{self.namespace}{Color.RESET}")
        print(f"\n{Color.CYAN}--- ConfigMaps: ---{Color.RESET}")
        for name, cm in self.config_maps.items():
            print(f"  * Name: {Color.BOLD}{name}{Color.RESET}")
            print(f"    - Immutable: {Color.GREEN if cm.immutable else Color.RED}{cm.immutable}{Color.RESET}")
            print(f"    - Hash: {cm.compute_hash()} (ResourceVersion: {cm.resource_version})")
            print(f"    - Keys: {list(cm.data.keys())}")

        print(f"\n{Color.CYAN}--- Secrets (Envelope Encryption & HashiCorp Vault Sync): ---{Color.RESET}")
        for name, sec in self.secrets.items():
            print(f"  * Name: {Color.BOLD}{name}{Color.RESET} (Type: {sec.type_})")
            print(f"    - KMS Envelope Encrypted in etcd: {Color.GREEN}{sec.kms_encrypted}{Color.RESET}")
            print(f"    - External Vault Backend: {Color.MAGENTA}{sec.vault_path}{Color.RESET}")
            print(f"    - Obfuscated Keys: {[k for k in sec.data_b64.keys()]}")

        print(f"\n{Color.CYAN}--- Pod Replica Pool: ---{Color.RESET}")
        for pod in self.pods:
            print(f"  * Pod: {Color.WHITE}{pod.pod_id}{Color.RESET} | Status: {Color.GREEN}{pod.status}{Color.RESET}")
            print(f"    - Mounted Volumes: {list(pod.mounted_volumes.keys())}")
            print(f"    - Config Tracking Hash: {Color.DIM}{pod.config_hash}{Color.RESET}")

    def test_immutability_protection(self):
        self.log_step("2. Demonstrating Kubernetes ConfigMap Immutability Protection")
        cm = self.config_maps["app-gateway-config"]
        print(f"Target ConfigMap: {cm.name} (immutable={cm.immutable})")
        print(f"{Color.DIM}Mencoba operasi PATCH field 'rate_limit.rps' ke '5000'...{Color.RESET}")
        time.sleep(0.6)

        if cm.immutable:
            print(f"{Color.RED}{Color.BOLD}[REJECTED by kube-apiserver]{Color.RESET}")
            print(
                f"{Color.RED}The ConfigMap \"{cm.name}\" is invalid: field is immutable when `immutable: true` is set.{Color.RESET}"
            )
            print(
                f"{Color.GREEN}INFO: Immutability memproteksi dari accidental drift dan meniadakan beban watch polling ke kube-apiserver.{Color.RESET}"
            )
        else:
            cm.data["rate_limit.rps"] = "5000"
            print(f"{Color.GREEN}Berhasil di-update.{Color.RESET}")

    def simulate_secret_decryption(self):
        self.log_step("3. Decoupled Secret Decryption & In-Memory Inspection")
        sec = self.secrets["database-credentials"]
        print(f"Reading Base64 Payload from Secret: {Color.BOLD}{sec.name}{Color.RESET}")
        for key, encoded in sec.data_b64.items():
            val = sec.get_decoded(key)
            masked = val[:3] + ("*" * (len(val) - 6)) + val[-3:] if len(val) > 6 else "***"
            print(f"  -> Key: {Color.YELLOW}{key:<18}{Color.RESET} [Raw b64: {encoded[:10]}...] -> Decoded Value: {Color.GREEN}{masked}{Color.RESET}")

    def simulate_hot_reload_stakater_pattern(self):
        self.log_step("4. Dynamic Configuration Evolution & Reloader Pattern Simulation")
        print(f"{Color.BLUE}Skenario: Memperbarui konfigurasi tanpa merusak immutability.{Color.RESET}")
        print("Pola Arsitektur: ConfigMap Versioning (app-gateway-config-v2) + Reloader Rolling Update Trigger.")
        time.sleep(0.8)

        new_cm = ConfigMap(
            name="app-gateway-config-v2",
            namespace=self.namespace,
            data={
                "gateway.timeout": "45s",
                "rate_limit.rps": "3500",
                "feature_flags.json": '{"enable_mesh": true, "tracing": "opentelemetry"}',
            },
            immutable=True,
            resource_version=1002,
        )
        self.config_maps[new_cm.name] = new_cm
        new_hash = new_cm.compute_hash()
        print(f"{Color.GREEN}[CREATED]{Color.RESET} ConfigMap '{new_cm.name}' with Hash: {new_hash}")

        print(f"\n{Color.YELLOW}[Reloader Controller]{Color.RESET} Terdeteksi perubahan annotation 'config.k8s.io/hash'!")
        print("Memulai Rolling Update terkontrol (Zero Downtime)...")

        for idx, pod in enumerate(self.pods):
            time.sleep(0.7)
            old_id = pod.pod_id
            new_id = f"order-service-api-88ce42af-{idx + 1}"
            print(f"  [Rolling Update] Terminating pod: {Color.RED}{old_id}{Color.RESET} -> Spawning: {Color.GREEN}{new_id}{Color.RESET}")
            pod.pod_id = new_id
            pod.config_hash = new_hash
            pod.mounted_volumes["/etc/config"] = new_cm.data.copy()
            pod.restarts += 1

        print(f"{Color.GREEN}{Color.BOLD}Zero-downtime rolling update sukses. Semua Pod sinkron dengan ConfigMap v2!{Color.RESET}")

    def verify_projected_volume_atomic_swap(self):
        self.log_step("5. Verifying Projected Volumes & Symlink Atomic Swapping")
        print("Kubernetes kubelet memperbarui mounted volumes via symlink swapping:")
        print(f"  /etc/config/..data_tmp -> /etc/config/..2026_10_05_timestamp")
        print(f"  atomic rename() -> /etc/config/..data")
        print(f"{Color.GREEN}[PASS]{Color.RESET} Inotify watchers menerima event IN_MODIFY tanpa proses restart pod jika aplikasi mendukung.")

    def run_all(self):
        print_banner()
        self.inspect_resources()
        self.test_immutability_protection()
        self.simulate_secret_decryption()
        self.simulate_hot_reload_stakater_pattern()
        self.verify_projected_volume_atomic_swap()
        print(f"\n{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} [SUCCESS] SELURUH TAHAP SIMULASI KUBERNETES CONFIG & SECRETS SELESAI DENGAN VALID {Color.RESET}\n")


def interactive_menu():
    sim = K8sClusterSimulation()
    while True:
        print_banner()
        print(f"{Color.BOLD}Menu Simulasi Interaktif:{Color.RESET}")
        print("  1. Audit Sumber Daya Cluster (ConfigMap, Secret, Pods)")
        print("  2. Uji Proteksi Immutability ConfigMap")
        print("  3. Uji Dekripsi Secret (KMS Envelope & Base64)")
        print("  4. Simulasi Pola Reloader (Hot-Reload / Rolling Deployment)")
        print("  5. Verifikasi Atomic Symlink Swap pada Projected Volumes")
        print("  6. Jalankan Seluruh Skenario Produksi (End-to-End Test)")
        print("  0. Keluar")
        choice = input(f"\n{Color.CYAN}Pilih opsi [0-6]: {Color.RESET}").strip()

        if choice == "1":
            sim.inspect_resources()
        elif choice == "2":
            sim.test_immutability_protection()
        elif choice == "3":
            sim.simulate_secret_decryption()
        elif choice == "4":
            sim.simulate_hot_reload_stakater_pattern()
        elif choice == "5":
            sim.verify_projected_volume_atomic_swap()
        elif choice == "6":
            sim.run_all()
        elif choice == "0":
            print(f"\n{Color.YELLOW}Sesi lab exercise diakhiri. Goodbye!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan coba lagi.{Color.RESET}")
        input(f"\n{Color.DIM}Tekan [Enter] untuk kembali ke menu...{Color.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--auto", "--demo", "-a"):
        sim = K8sClusterSimulation()
        sim.run_all()
    else:
        interactive_menu()
