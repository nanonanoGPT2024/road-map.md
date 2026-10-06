#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Kubernetes Networking, Service Discovery & Ingress Architecture
BAB-05: Networking, Service Discovery, dan Ingress
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"


class ServiceType(Enum):
    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"


@dataclass
class Pod:
    name: str
    namespace: str
    pod_ip: str
    node_name: str
    labels: Dict[str, str]
    is_ready: bool = True


@dataclass
class Service:
    name: str
    namespace: str
    service_type: ServiceType
    cluster_ip: str
    port: int
    target_port: int
    node_port: Optional[int] = None
    selector: Dict[str, str] = field(default_factory=dict)


@dataclass
class IngressPath:
    path: str
    service_name: str
    service_port: int


@dataclass
class IngressRule:
    host: str
    paths: List[IngressPath]


@dataclass
class NetworkPolicy:
    name: str
    namespace: str
    pod_selector: Dict[str, str]
    allowed_sources: List[str]


class KubernetesNetworkSimulator:
    def __init__(self):
        self.pods: Dict[str, Pod] = {}
        self.services: Dict[str, Service] = {}
        self.ingress_rules: List[IngressRule] = []
        self.network_policies: List[NetworkPolicy] = []
        self.dns_records: Dict[str, str] = {}
        self._bootstrap_cluster()

    def _bootstrap_cluster(self):
        # 1. Setup Pods across multi-node topology
        demo_pods = [
            Pod("auth-pod-1", "prod", "10.244.1.15", "worker-node-1", {"app": "auth", "tier": "backend"}),
            Pod("auth-pod-2", "prod", "10.244.2.22", "worker-node-2", {"app": "auth", "tier": "backend"}),
            Pod("web-pod-1", "prod", "10.244.1.33", "worker-node-1", {"app": "frontend", "tier": "web"}),
            Pod("web-pod-2", "prod", "10.244.2.44", "worker-node-2", {"app": "frontend", "tier": "web"}),
            Pod("payment-pod-1", "finance", "10.244.2.80", "worker-node-2", {"app": "payment", "tier": "secure"}),
        ]
        for p in demo_pods:
            self.pods[p.name] = p

        # 2. Setup Services & CoreDNS
        svc_web = Service(
            name="frontend-svc",
            namespace="prod",
            service_type=ServiceType.LOAD_BALANCER,
            cluster_ip="10.96.10.50",
            port=80,
            target_port=8080,
            node_port=30080,
            selector={"app": "frontend"},
        )
        svc_auth = Service(
            name="auth-svc",
            namespace="prod",
            service_type=ServiceType.CLUSTER_IP,
            cluster_ip="10.96.20.75",
            port=5000,
            target_port=5000,
            selector={"app": "auth"},
        )
        self.services[svc_web.name] = svc_web
        self.services[svc_auth.name] = svc_auth

        # CoreDNS records registration
        self.dns_records[f"frontend-svc.prod.svc.cluster.local"] = svc_web.cluster_ip
        self.dns_records[f"auth-svc.prod.svc.cluster.local"] = svc_auth.cluster_ip

        # 3. Setup Ingress Controller rules
        self.ingress_rules.append(
            IngressRule(
                host="api.company.com",
                paths=[
                    IngressPath(path="/", service_name="frontend-svc", service_port=80),
                    IngressPath(path="/auth", service_name="auth-svc", service_port=5000),
                ],
            )
        )

        # 4. Setup Network Policy (Deny cross-tier unapproved traffic)
        self.network_policies.append(
            NetworkPolicy(
                name="isolate-payment-tier",
                namespace="finance",
                pod_selector={"tier": "secure"},
                allowed_sources=["prod/app=auth"],
            )
        )

    def print_banner(self):
        print(f"{Color.CYAN}{'='*80}")
        print(f"  {Color.BOLD}{Color.GREEN}KUBERNETES NETWORKING & INGRESS LAB SIMULATOR (BAB-05){Color.RESET}")
        print(f"  {Color.YELLOW}Topologi: Pod-to-Pod CNI | Service IPVS/iptables | CoreDNS | Ingress Controller")
        print(f"{Color.CYAN}{'='*80}{Color.RESET}\n")

    def inspect_cluster(self):
        print(f"{Color.BOLD}{Color.WHITE}=== 1. Active Pod Endpoints (CNI Overlay Network) ==={Color.RESET}")
        for p in self.pods.values():
            status = f"{Color.GREEN}READY{Color.RESET}" if p.is_ready else f"{Color.RED}NOT_READY{Color.RESET}"
            print(f"  * [{p.namespace}] {p.name:<18} IP: {Color.CYAN}{p.pod_ip:<12}{Color.RESET} Node: {p.node_name:<14} [{status}] Labels: {p.labels}")

        print(f"\n{Color.BOLD}{Color.WHITE}=== 2. Services & Virtual IPs ==={Color.RESET}")
        for s in self.services.values():
            node_port_str = f"NodePort: {s.node_port}" if s.node_port else "NodePort: None"
            print(f"  * [{s.namespace}] {s.name:<18} Type: {s.service_type.value:<12} ClusterIP: {Color.MAGENTA}{s.cluster_ip:<12}{Color.RESET} Port: {s.port}->{s.target_port} ({node_port_str})")

        print(f"\n{Color.BOLD}{Color.WHITE}=== 3. CoreDNS Records ==={Color.RESET}")
        for fqdn, ip in self.dns_records.items():
            print(f"  * {fqdn:<38} -> {Color.MAGENTA}{ip}{Color.RESET}")

        print(f"\n{Color.BOLD}{Color.WHITE}=== 4. Ingress Rules (L7 HTTP Reverse Proxy) ==={Color.RESET}")
        for rule in self.ingress_rules:
            print(f"  * Host: {Color.YELLOW}{rule.host}{Color.RESET}")
            for p in rule.paths:
                print(f"      Path: {p.path:<10} Routing to: {p.service_name}:{p.service_port}")
        print()

    def simulate_dns_and_service_lookup(self, client_pod_name: str, target_fqdn: str):
        print(f"\n{Color.BOLD}[SIMULASI 1: Service Discovery & CoreDNS Packet Flow]{Color.RESET}")
        source_pod = self.pods.get(client_pod_name)
        if not source_pod:
            print(f"{Color.RED}Error: Pod {client_pod_name} tidak ditemukan.{Color.RESET}")
            return

        print(f"1. Pod [{Color.CYAN}{source_pod.name}{Color.RESET} ({source_pod.pod_ip})] memicu query DNS UDP:53 ke kube-dns: 10.96.0.10")
        time.sleep(0.3)
        if target_fqdn in self.dns_records:
            resolved_vip = self.dns_records[target_fqdn]
            print(f"   -> {Color.GREEN}DNS ANSWER:{Color.RESET} '{target_fqdn}' diresolusi ke ClusterIP {Color.MAGENTA}{resolved_vip}{Color.RESET}")
        else:
            print(f"   -> {Color.RED}DNS NXDOMAIN:{Color.RESET} Target {target_fqdn} gagal diresolusi.")
            return

        # Cari target service berdasarkan resolved VIP
        matched_svc = next((s for s in self.services.values() if s.cluster_ip == resolved_vip), None)
        if not matched_svc:
            print(f"   -> {Color.RED}ClusterIP tidak terikat pada Service apapun.{Color.RESET}")
            return

        print(f"2. Paket TCP SYN dikirim dari {source_pod.pod_ip} ke ClusterIP {matched_svc.cluster_ip}:{matched_svc.port}")
        print(f"   -> {Color.YELLOW}Kernel IPVS/iptables KUBE-SERVICES chain{Color.RESET}: Melakukan DNAT (Destination NAT)")
        
        # Load balancing ke endpoints pod yang matching
        endpoints = [p for p in self.pods.values() if all(p.labels.get(k) == v for k, v in matched_svc.selector.items()) and p.is_ready]
        if not endpoints:
            print(f"   -> {Color.RED}Error 503: Endpoint backend kosong! Service tidak memiliki Pod ready.{Color.RESET}")
            return

        selected_pod = endpoints[0]  # round-robin simulation
        print(f"   -> {Color.GREEN}DNAT Success:{Color.RESET} Virtual IP {matched_svc.cluster_ip}:{matched_svc.port} ditransformasi menjadi Endpoint {selected_pod.name} ({Color.CYAN}{selected_pod.pod_ip}:{matched_svc.target_port}{Color.RESET})")
        print(f"3. CNI Packet Routing: Paket dirutekan lintas node via overlay tunnel / VXLAN encapsulation dari {source_pod.node_name} ke {selected_pod.node_name}.")
        print(f"   {Color.BOLD}{Color.GREEN}✓ Koneksi Berhasil Terhubung (200 OK)!{Color.RESET}")

    def simulate_ingress_traffic(self, request_host: str, request_path: str):
        print(f"\n{Color.BOLD}[SIMULASI 2: Ingress L7 Path-based Routing]{Color.RESET}")
        print(f"Permintaan Masuk: HTTP GET http://{request_host}{request_path}")
        time.sleep(0.3)

        matched_rule = next((r for r in self.ingress_rules if r.host == request_host), None)
        if not matched_rule:
            print(f"{Color.RED}Ingress 404: Tidak ada host rule matching untuk '{request_host}'.{Color.RESET}")
            return

        # Sort matching longest prefix
        matched_path = None
        for p in sorted(matched_rule.paths, key=lambda x: len(x.path), reverse=True):
            if request_path.startswith(p.path):
                matched_path = p
                break

        if not matched_path:
            print(f"{Color.RED}Ingress 404: Path '{request_path}' tidak ditemukan di ingress rule.{Color.RESET}")
            return

        print(f"1. Ingress Controller (Nginx/Envoy Pod) menerima request pada external IP / LoadBalancer port 80/443.")
        print(f"2. Evaluasi Ingress Match: Host '{request_host}' + Path '{matched_path.path}'")
        print(f"   -> Mengarahkan ke internal Service: {Color.MAGENTA}{matched_path.service_name}:{matched_path.service_port}{Color.RESET}")
        
        target_svc = self.services.get(matched_path.service_name)
        if target_svc:
            endpoints = [p for p in self.pods.values() if all(p.labels.get(k) == v for k, v in target_svc.selector.items())]
            target_eps_str = ", ".join([f"{ep.name} ({ep.pod_ip})" for ep in endpoints])
            print(f"3. Upstream Endpoints aktif: [{target_eps_str}]")
            print(f"   {Color.BOLD}{Color.GREEN}✓ Ingress Proxy Berhasil Melewatkan Traffic L7 ke Target Service!{Color.RESET}")

    def simulate_network_policy_audit(self, src_pod_name: str, dst_pod_name: str) -> bool:
        print(f"\n{Color.BOLD}[SIMULASI 3: Evaluasi NetworkPolicy Security Guardrail]{Color.RESET}")
        src_pod = self.pods.get(src_pod_name)
        dst_pod = self.pods.get(dst_pod_name)

        if not src_pod or not dst_pod:
            print(f"{Color.RED}Pod pengirim atau penerima tidak ditemukan.{Color.RESET}")
            return False

        print(f"Traffic Attempt: [{src_pod.namespace}/{src_pod.name}] ({src_pod.pod_ip}) -> [{dst_pod.namespace}/{dst_pod.name}] ({dst_pod.pod_ip})")
        time.sleep(0.3)

        # Cek apakah dst_pod terisolasi oleh NetworkPolicy
        active_policies = [np for np in self.network_policies if np.namespace == dst_pod.namespace and all(dst_pod.labels.get(k) == v for k, v in np.pod_selector.items())]

        if not active_policies:
            print(f"   -> {Color.GREEN}DEFAULT ALLOW:{Color.RESET} Tidak ada NetworkPolicy aktif pada namespace '{dst_pod.namespace}'. Traffic diizinkan.")
            return True

        for policy in active_policies:
            print(f"   -> {Color.YELLOW}POLICY DETECTED:{Color.RESET} Pod tujuan dilindungi NetworkPolicy '{policy.name}'")
            # Evaluasi whitelist
            allowed = False
            for rule in policy.allowed_sources:
                req_ns, req_label = rule.split("/")
                lbl_k, lbl_v = req_label.split("=")
                if src_pod.namespace == req_ns and src_pod.labels.get(lbl_k) == lbl_v:
                    allowed = True
                    break

            if allowed:
                print(f"   {Color.BOLD}{Color.GREEN}✓ ACCESS GRANTED:{Color.RESET} Pod pengirim memenuhi kriteria selector whitelist.")
                return True
            else:
                print(f"   {Color.BOLD}{Color.RED}✗ ACCESS BLOCKED (Connection Timed Out):{Color.RESET} Paket di-drop oleh CNI eBPF/iptables filter.")
                return False


def main():
    sim = KubernetesNetworkSimulator()
    sim.print_banner()

    while True:
        print(f"\n{Color.BOLD}{Color.CYAN}--- PILIHAN MENU LAB SIMULASI INTERAKTIF ---{Color.RESET}")
        print("1. Tampilkan Topologi Cluster (Pods, Services, CoreDNS, Ingress)")
        print("2. Uji Alur Service Discovery (CoreDNS -> Virtual IP -> DNAT -> Pod Endpoint)")
        print("3. Uji Alur L7 Ingress Routing (Host & Path Matching)")
        print("4. Uji Isolasi Keamanan (NetworkPolicy Ingress Filtering)")
        print("5. Eksekusi Seluruh Skenario Otomatis (Demo Lengkap)")
        print("0. Keluar")

        try:
            choice = input(f"\n{Color.BOLD}Pilih nomor skenario [0-5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Sesi lab diakhiri.{Color.RESET}")
            break

        if choice == "1":
            sim.inspect_cluster()
        elif choice == "2":
            sim.simulate_dns_and_service_lookup("web-pod-1", "auth-svc.prod.svc.cluster.local")
        elif choice == "3":
            print("\nMemilih request: host='api.company.com', path='/auth'")
            sim.simulate_ingress_traffic("api.company.com", "/auth")
        elif choice == "4":
            print("\nUji 4a: Web Pod (prod) -> Payment Pod (finance) [Seharusnya Ditolak]")
            sim.simulate_network_policy_audit("web-pod-1", "payment-pod-1")
            print("\nUji 4b: Auth Pod (prod) -> Payment Pod (finance) [Seharusnya Diizinkan]")
            sim.simulate_network_policy_audit("auth-pod-1", "payment-pod-1")
        elif choice == "5":
            print(f"\n{Color.BG_BLUE}{Color.WHITE} >>> MENJALANKAN SELURUH SKENARIO DEMO ARSITEKTUR PRODUKSI <<< {Color.RESET}\n")
            sim.inspect_cluster()
            sim.simulate_dns_and_service_lookup("web-pod-1", "auth-svc.prod.svc.cluster.local")
            sim.simulate_ingress_traffic("api.company.com", "/auth")
            sim.simulate_network_policy_audit("web-pod-1", "payment-pod-1")
            sim.simulate_network_policy_audit("auth-pod-1", "payment-pod-1")
            print(f"\n{Color.BG_GREEN}{Color.WHITE} Seluruh demonstrasi lab selesai dengan sukses! {Color.RESET}")
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih telah menggunakan K8s Networking Simulator.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}")


if __name__ == "__main__":
    main()
