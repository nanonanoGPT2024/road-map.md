#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Network Security, CNI, dan Kubernetes NetworkPolicy
BAB-06: Network-Security-CNI-dan-NetworkPolicies
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


@dataclass
class Pod:
    name: str
    namespace: str
    ip: str
    labels: Dict[str, str]


@dataclass
class NetworkRule:
    direction: str  # "Ingress" or "Egress"
    allowed_from_labels: Optional[Dict[str, str]] = None
    allowed_from_namespaces: Optional[List[str]] = None
    allowed_ports: Optional[List[int]] = None
    action: str = "ALLOW"


@dataclass
class NetworkPolicy:
    name: str
    namespace: str
    pod_selector: Dict[str, str]  # Pod targets
    policy_types: List[str]  # ["Ingress"], ["Egress"], or both
    ingress_rules: List[NetworkRule] = field(default_factory=list)
    egress_rules: List[NetworkRule] = field(default_factory=list)


class CNIProviderEngine:
    """Simulasi CNI Data Plane (Calico IPIP/iptables & Cilium eBPF map logic)."""

    def __init__(self, mode: str = "cilium-ebpf"):
        self.mode = mode

    def inspect_packet_datapath(self, src: Pod, dst: Pod, port: int) -> str:
        if self.mode == "cilium-ebpf":
            return (
                f"{CYAN}[eBPF BPF_MAP_POLICY]{RESET} Hook: tc/sockops egress "
                f"({src.ip} -> {dst.ip}:{port}) - zero-copy kernel fastpath"
            )
        else:
            return (
                f"{MAGENTA}[IPIP/IPTABLES]{RESET} KUBE-POD-ROUTER -> "
                f"filter chain FORWARD ({src.ip} -> {dst.ip}:{port})"
            )


class KubernetesNetworkSimulation:
    def __init__(self):
        self.cni = CNIProviderEngine(mode="cilium-ebpf")
        self.pods: Dict[str, Pod] = {}
        self.policies: List[NetworkPolicy] = []
        self._seed_cluster()

    def _seed_cluster(self):
        # Setup sample cluster pods across namespaces
        self.pods["frontend-pod"] = Pod(
            name="frontend-app-7d94bc-x8k1",
            namespace="production",
            ip="10.244.1.15",
            labels={"app": "frontend", "tier": "web", "env": "prod"},
        )
        self.pods["backend-pod"] = Pod(
            name="backend-api-5c78f9-nm3q",
            namespace="production",
            ip="10.244.2.42",
            labels={"app": "backend", "tier": "api", "env": "prod"},
        )
        self.pods["database-pod"] = Pod(
            name="postgres-db-0",
            namespace="production",
            ip="10.244.2.99",
            labels={"app": "database", "tier": "storage", "env": "prod"},
        )
        self.pods["rogue-attacker"] = Pod(
            name="compromised-pod-xyz",
            namespace="dev",
            ip="10.244.3.77",
            labels={"app": "untrusted", "tier": "scratch"},
        )

    def print_header(self, text: str):
        print(f"\n{BOLD}{BG_BLUE}{WHITE} === {text} === {RESET}\n")

    def display_cluster_state(self):
        self.print_header("KUBERNETES POD INVENTORY & CNI ADDRESSING")
        print(f"{'POD NAME':<32} {'NAMESPACE':<12} {'POD IP':<15} {'LABELS'}")
        print("-" * 80)
        for key, pod in self.pods.items():
            lbl_str = ", ".join(f"{k}={v}" for k, v in pod.labels.items())
            print(f"{GREEN}{pod.name:<32}{RESET} {pod.namespace:<12} {pod.ip:<15} {lbl_str}")

        print(f"\n{BOLD}Active CNI Plugin Engine:{RESET} {CYAN}{self.cni.mode.upper()}{RESET}")
        print(f"{BOLD}Installed NetworkPolicies:{RESET} {len(self.policies)} active rule(s)")
        for pol in self.policies:
            print(f"  * Policy: {YELLOW}{pol.name}{RESET} (ns: {pol.namespace}, target: {pol.pod_selector})")

    def apply_default_deny(self):
        """Menerapkan Default-Deny Ingress pada namespace production."""
        pol = NetworkPolicy(
            name="default-deny-ingress-prod",
            namespace="production",
            pod_selector={},  # Seleksi semua pod di namespace production
            policy_types=["Ingress"],
            ingress_rules=[],  # Kosong = isolate completely
        )
        self.policies.append(pol)
        print(f"\n{GREEN}[+] NetworkPolicy '{pol.name}' diaplikasikan!{RESET}")
        print(f"    {YELLOW}Efek:{RESET} Namespace 'production' beralih ke Zero-Trust Default-Deny Ingress.")

    def apply_backend_allowlist(self):
        """Mengizinkan akses hanya dari frontend ke backend port 8080."""
        rule = NetworkRule(
            direction="Ingress",
            allowed_from_labels={"app": "frontend"},
            allowed_ports=[8080],
            action="ALLOW",
        )
        pol = NetworkPolicy(
            name="allow-fe-to-be",
            namespace="production",
            pod_selector={"app": "backend"},
            policy_types=["Ingress"],
            ingress_rules=[rule],
        )
        self.policies.append(pol)
        print(f"\n{GREEN}[+] NetworkPolicy '{pol.name}' diaplikasikan!{RESET}")
        print(f"    {YELLOW}Efek:{RESET} Pod app=backend hanya menerima Ingress dari app=frontend di port 8080.")

    def evaluate_traffic(self, src: Pod, dst: Pod, port: int) -> bool:
        # Cek apakah destinasi terisolasi oleh NetworkPolicy Ingress
        applicable_policies = [
            p for p in self.policies
            if p.namespace == dst.namespace
            and (not p.pod_selector or all(dst.labels.get(k) == v for k, v in p.pod_selector.items()))
            and "Ingress" in p.policy_types
        ]

        if not applicable_policies:
            # Standar Kubernetes CNI default: Default-Allow jika tanpa policy
            return True

        # Jika ada policy isolasi, default menjadi DENY kecuali ada rule yang cocok (Whitelist model)
        allowed = False
        for pol in applicable_policies:
            for rule in pol.ingress_rules:
                port_match = (not rule.allowed_ports) or (port in rule.allowed_ports)
                label_match = True
                if rule.allowed_from_labels:
                    label_match = all(src.labels.get(k) == v for k, v in rule.allowed_from_labels.items())
                
                ns_match = True
                if rule.allowed_from_namespaces:
                    ns_match = src.namespace in rule.allowed_from_namespaces

                if port_match and label_match and ns_match:
                    allowed = True
                    break

        return allowed

    def simulate_packet(self, src_key: str, dst_key: str, port: int):
        src = self.pods[src_key]
        dst = self.pods[dst_key]

        print(f"\n{BOLD}[SEND PACKET]{RESET} {src.name} ({src.ip}) -> {dst.name} ({dst.ip}:{port})")
        print(f"  {self.cni.inspect_packet_datapath(src, dst, port)}")
        time.sleep(0.3)

        allowed = self.evaluate_traffic(src, dst, port)
        if allowed:
            print(f"  {GREEN}[ALLOWED - TCP ACK]{RESET} Paket diterima oleh kernel socket di {dst.ip}:{port}")
        else:
            print(f"  {RED}[BLOCKED - DROP]{RESET} Paket didrop oleh CNI NetworkPolicy enforcer (Host Filter/eBPF)")

    def run_automated_suite(self):
        self.print_header("PENGUJIAN SKENARIO OTOMATIS: NETWORK POLICIES & CNI")

        print(f"{BOLD}--- Skenario 1: Default Cluster State (Flat Network, Default-Allow) ---{RESET}")
        self.simulate_packet("frontend-pod", "backend-pod", 8080)
        self.simulate_packet("rogue-attacker", "database-pod", 5432)

        print(f"\n{BOLD}--- Skenario 2: Menerapkan Default-Deny di Namespace Production ---{RESET}")
        self.apply_default_deny()
        self.simulate_packet("frontend-pod", "backend-pod", 8080)
        self.simulate_packet("rogue-attacker", "database-pod", 5432)

        print(f"\n{BOLD}--- Skenario 3: Menerapkan Micro-segmentation Whitelist Rule ---{RESET}")
        self.apply_backend_allowlist()
        self.simulate_packet("frontend-pod", "backend-pod", 8080)
        self.simulate_packet("frontend-pod", "backend-pod", 9090)  # Port salah
        self.simulate_packet("rogue-attacker", "backend-pod", 8080)  # Label salah

        print(f"\n{BOLD}{GREEN}=== Seluruh Skenario Lab Selesai Terverifikasi! ==={RESET}\n")


def interactive_menu():
    sim = KubernetesNetworkSimulation()
    while True:
        sim.print_header("KUBERNETES NETWORK SECURITY INTERACTIVE LAB")
        print("1. Tampilkan State Pod & CNI Topology")
        print("2. Terapkan Default-Deny Ingress (Zero-Trust)")
        print("3. Terapkan Whitelist Policy (Frontend -> Backend:8080)")
        print("4. Kirim Probe Paket Kustom")
        print("5. Jalankan Automated Verification Suite")
        print("6. Ubah CNI Data Plane Engine (Calico iptables vs Cilium eBPF)")
        print("0. Keluar")
        
        choice = input(f"\n{BOLD}Pilih opsi [0-6]: {RESET}").strip()
        if choice == "1":
            sim.display_cluster_state()
        elif choice == "2":
            sim.apply_default_deny()
        elif choice == "3":
            sim.apply_backend_allowlist()
        elif choice == "4":
            print("\nPilih Source Pod:")
            keys = list(sim.pods.keys())
            for i, k in enumerate(keys):
                print(f"  {i+1}. {k}")
            try:
                s_idx = int(input("Pilih nomor Source: ")) - 1
                d_idx = int(input("Pilih nomor Destination: ")) - 1
                port = int(input("Port tujuan (cth: 8080, 5432): "))
                sim.simulate_packet(keys[s_idx], keys[d_idx], port)
            except (ValueError, IndexError):
                print(f"{RED}Input tidak valid.{RESET}")
        elif choice == "5":
            sim.run_automated_suite()
        elif choice == "6":
            sim.cni.mode = "calico-iptables" if sim.cni.mode == "cilium-ebpf" else "cilium-ebpf"
            print(f"\n{YELLOW}CNI Engine dialihkan ke: {sim.cni.mode}{RESET}")
        elif choice == "0":
            print(f"\n{GREEN}Lab selesai. Terima kasih.{RESET}")
            break
        else:
            print(f"{RED}Opsi tidak dikenal.{RESET}")

        input(f"\n{CYAN}Tekan [Enter] untuk melanjutkan...{RESET}")


if __name__ == "__main__":
    # Jika dipanggil dengan flag non-interaktif atau argumen automated
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--auto", "-a"):
        sim = KubernetesNetworkSimulation()
        sim.run_automated_suite()
    else:
        interactive_menu()
