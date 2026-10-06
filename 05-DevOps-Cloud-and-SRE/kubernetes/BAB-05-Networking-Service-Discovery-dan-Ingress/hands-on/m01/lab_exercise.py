#!/usr/bin/env python3
"""
Lab Exercise: Kubernetes Networking, Service Discovery, and Ingress Simulator
BAB-05: Networking, Service Discovery, dan Ingress
"""

import sys
import time
import random
import ipaddress
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ANSI Color codes for styled terminal output
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

@dataclass
class Pod:
    name: str
    namespace: str
    node: str
    ip: str
    labels: Dict[str, str]
    is_ready: bool = True

@dataclass
class Service:
    name: str
    namespace: str
    cluster_ip: str
    port: int
    target_port: int
    selector: Dict[str, str]

@dataclass
class IngressRule:
    host: str
    path: str
    service_name: str
    service_port: int

class KubeNetworkSimulator:
    def __init__(self):
        self.node_cidrs = {
            "node-worker-1": ipaddress.IPv4Network("10.244.1.0/24"),
            "node-worker-2": ipaddress.IPv4Network("10.244.2.0/24")
        }
        self.service_cidr = ipaddress.IPv4Network("10.96.0.0/12")
        self.cluster_domain = "cluster.local"
        self.cluster_dns_ip = "10.96.0.10"
        
        self.pods: Dict[str, Pod] = {}
        self.services: Dict[str, Service] = {}
        self.ingress_rules: List[IngressRule] = []
        self.rr_index: Dict[str, int] = {}
        
        self._bootstrap_cluster()

    def _bootstrap_cluster(self):
        # 1. Pod Deployment across Nodes
        self.pods["frontend-pod-a"] = Pod(
            name="frontend-pod-a",
            namespace="production",
            node="node-worker-1",
            ip="10.244.1.15",
            labels={"app": "frontend", "env": "prod"}
        )
        self.pods["frontend-pod-b"] = Pod(
            name="frontend-pod-b",
            namespace="production",
            node="node-worker-2",
            ip="10.244.2.22",
            labels={"app": "frontend", "env": "prod"}
        )
        self.pods["auth-pod-1"] = Pod(
            name="auth-pod-1",
            namespace="production",
            node="node-worker-1",
            ip="10.244.1.48",
            labels={"app": "auth-api", "env": "prod"}
        )
        self.pods["auth-pod-2"] = Pod(
            name="auth-pod-2",
            namespace="production",
            node="node-worker-2",
            ip="10.244.2.51",
            labels={"app": "auth-api", "env": "prod"}
        )
        self.pods["client-curl-pod"] = Pod(
            name="client-curl-pod",
            namespace="default",
            node="node-worker-1",
            ip="10.244.1.99",
            labels={"app": "toolbox"}
        )

        # 2. ClusterIP Services
        self.services["frontend-svc"] = Service(
            name="frontend-svc",
            namespace="production",
            cluster_ip="10.96.14.88",
            port=80,
            target_port=8080,
            selector={"app": "frontend"}
        )
        self.services["auth-svc"] = Service(
            name="auth-svc",
            namespace="production",
            cluster_ip="10.96.220.105",
            port=80,
            target_port=3000,
            selector={"app": "auth-api"}
        )

        # 3. Ingress Routing Rules
        self.ingress_rules.append(IngressRule(
            host="shop.example.com",
            path="/",
            service_name="frontend-svc",
            service_port=80
        ))
        self.ingress_rules.append(IngressRule(
            host="shop.example.com",
            path="/api/v1/auth",
            service_name="auth-svc",
            service_port=80
        ))

    def get_endpoints(self, service: Service) -> List[Pod]:
        endpoints = []
        for pod in self.pods.values():
            if pod.namespace != service.namespace:
                continue
            matched = all(pod.labels.get(k) == v for k, v in service.selector.items())
            if matched and pod.is_ready:
                endpoints.append(pod)
        return endpoints

    def resolve_dns(self, query: str, src_namespace: str) -> Optional[str]:
        print(f"\n{Style.CYAN}[CoreDNS Engine]{Style.RESET} Query received: '{query}' from ns: '{src_namespace}'")
        time.sleep(0.2)
        
        # Format normalizations: <svc>, <svc>.<ns>, <svc>.<ns>.svc, <svc>.<ns>.svc.<domain>
        tokens = query.strip(".").split(".")
        svc_name = tokens[0]
        
        target_ns = src_namespace
        if len(tokens) >= 2:
            target_ns = tokens[1]
            
        for svc in self.services.values():
            if svc.name == svc_name and svc.namespace == target_ns:
                fqdn = f"{svc.name}.{svc.namespace}.svc.{self.cluster_domain}"
                print(f"  {Style.GREEN}✓ DNS Match:{Style.RESET} {fqdn} -> A-record: {Style.BOLD}{svc.cluster_ip}{Style.RESET}")
                return svc.cluster_ip
                
        print(f"  {Style.RED}✗ NXDOMAIN:{Style.RESET} Domain name '{query}' not found in cluster DNS zone.")
        return None

    def kube_proxy_route(self, cluster_ip: str, port: int) -> Tuple[Optional[Pod], Optional[int]]:
        target_svc = None
        for svc in self.services.values():
            if svc.cluster_ip == cluster_ip and svc.port == port:
                target_svc = svc
                break
                
        if not target_svc:
            print(f"  {Style.RED}[kube-proxy]{Style.RESET} Connection refused! No service matches VIP {cluster_ip}:{port}")
            return None, None

        endpoints = self.get_endpoints(target_svc)
        if not endpoints:
            print(f"  {Style.RED}[kube-proxy]{Style.RESET} 503 No Endpoints Available for Service '{target_svc.name}'")
            return None, None

        # Round-robin packet dispatch (simulating IPVS / iptables statistic mode)
        curr_idx = self.rr_index.get(target_svc.name, 0)
        selected_pod = endpoints[curr_idx % len(endpoints)]
        self.rr_index[target_svc.name] = (curr_idx + 1) % len(endpoints)
        
        print(f"  {Style.MAGENTA}[kube-proxy iptables/IPVS]{Style.RESET} Packet dest: {cluster_ip}:{port}")
        print(f"  DNAT mapping -> {selected_pod.name} ({selected_pod.ip}:{target_svc.target_port}) on {selected_pod.node}")
        return selected_pod, target_svc.target_port

    def ingress_dispatch(self, host: str, path: str):
        print(f"\n{Style.YELLOW}[Ingress Controller NGINX/Envoy]{Style.RESET} Incoming HTTP Request")
        print(f"  Headers: Host={host} | Request-URI={path}")
        time.sleep(0.2)
        
        matched_rule = None
        # Longest prefix match
        sorted_rules = sorted(self.ingress_rules, key=lambda r: len(r.path), reverse=True)
        for rule in sorted_rules:
            if rule.host == host and path.startswith(rule.path):
                matched_rule = rule
                break
                
        if not matched_rule:
            print(f"  {Style.RED}404 Not Found:{Style.RESET} No matching ingress host/path route.")
            return
            
        print(f"  {Style.GREEN}✓ Matched Ingress Path:{Style.RESET} '{matched_rule.path}' -> Upstream Service: '{matched_rule.service_name}:{matched_rule.service_port}'")
        svc = self.services.get(matched_rule.service_name)
        if svc:
            pod, target_port = self.kube_proxy_route(svc.cluster_ip, svc.port)
            if pod:
                print(f"  {Style.GREEN}[HTTP 200 OK]{Style.RESET} Handled successfully by {pod.name} ({pod.ip})")

def show_header():
    print(f"\n{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} === KUBERNETES NETWORKING & SERVICE DISCOVERY LAB (BAB-05) === {Style.RESET}\n")

def menu_show_topology(sim: KubeNetworkSimulator):
    print(f"\n{Style.BOLD}--- [1] Cluster Topology & CNI IPAM Allocation ---{Style.RESET}")
    print(f"{Style.CYAN}Node PodCIDRs:{Style.RESET}")
    for node, cidr in sim.node_cidrs.items():
        print(f"  • {node:<15} : {cidr}")
    
    print(f"\n{Style.CYAN}Service Subnet (ClusterIP VIP pool):{Style.RESET} {sim.service_cidr}")
    print(f"{Style.CYAN}CoreDNS Resolver Address:{Style.RESET} {sim.cluster_dns_ip}")
    
    print(f"\n{Style.CYAN}Active Pods (veth interfaces bridged to CNI):{Style.RESET}")
    print(f"  {'POD NAME':<20} {'NAMESPACE':<12} {'NODE':<16} {'IP ADDRESS':<15} {'STATUS'}")
    print("  " + "-" * 72)
    for pod in sim.pods.values():
        status = f"{Style.GREEN}Ready{Style.RESET}" if pod.is_ready else f"{Style.RED}NotReady{Style.RESET}"
        print(f"  {pod.name:<20} {pod.namespace:<12} {pod.node:<16} {pod.ip:<15} {status}")
        
    print(f"\n{Style.CYAN}Kubernetes Services & Endpoints:{Style.RESET}")
    print(f"  {'SERVICE NAME':<16} {'CLUSTER-IP':<15} {'PORT':<8} {'TARGET':<8} {'ENDPOINTS'}")
    print("  " + "-" * 72)
    for svc in sim.services.values():
        eps = [f"{p.ip}:{svc.target_port}" for p in sim.get_endpoints(svc)]
        ep_str = ", ".join(eps) if eps else "<none>"
        print(f"  {svc.name:<16} {svc.cluster_ip:<15} {str(svc.port):<8} {str(svc.target_port):<8} {ep_str}")

def menu_coredns(sim: KubeNetworkSimulator):
    print(f"\n{Style.BOLD}--- [2] Interactive CoreDNS Service Discovery ---{Style.RESET}")
    print("Contoh FQDN:")
    print("  1. frontend-svc")
    print("  2. auth-svc.production")
    print("  3. auth-svc.production.svc.cluster.local")
    print("  4. payment-svc.default (non-existent)")
    
    default_queries = [
        ("frontend-svc", "production"),
        ("auth-svc.production", "default"),
        ("auth-svc.production.svc.cluster.local", "default"),
        ("unknown-svc", "default")
    ]
    for q, ns in default_queries:
        sim.resolve_dns(q, ns)

def menu_service_load_balancing(sim: KubeNetworkSimulator):
    print(f"\n{Style.BOLD}--- [3] kube-proxy Load Balancing Simulation (Round-Robin) ---{Style.RESET}")
    svc = sim.services["frontend-svc"]
    print(f"Mengirim 4 request berturut-turut ke ClusterIP {svc.cluster_ip}:{svc.port}...")
    for i in range(1, 5):
        print(f"\nRequest #{i}:")
        sim.kube_proxy_route(svc.cluster_ip, svc.port)
        time.sleep(0.15)

def menu_ingress_routing(sim: KubeNetworkSimulator):
    print(f"\n{Style.BOLD}--- [4] Ingress Layer 7 Path-Based Routing ---{Style.RESET}")
    requests = [
        ("shop.example.com", "/"),
        ("shop.example.com", "/catalog/items"),
        ("shop.example.com", "/api/v1/auth/login"),
        ("shop.example.com", "/api/v1/payment"),
        ("evil-domain.com", "/")
    ]
    for host, path in requests:
        sim.ingress_dispatch(host, path)

def run_automated_suite(sim: KubeNetworkSimulator):
    print(f"\n{Style.BOLD}--- [5] Menjalankan Automated Verification Suite ---{Style.RESET}")
    # Check 1: DNS
    print("Test 1: Validasi CoreDNS A-Record frontend-svc...")
    ip = sim.resolve_dns("frontend-svc.production.svc.cluster.local", "default")
    assert ip == "10.96.14.88", "DNS resolution failed!"
    print(f"  {Style.GREEN}[PASS]{Style.RESET} DNS test berhasil.\n")

    # Check 2: Endpoints
    print("Test 2: Validasi Endpoint Discovery...")
    eps = sim.get_endpoints(sim.services["frontend-svc"])
    assert len(eps) == 2, "Endpoint mismatch!"
    print(f"  {Style.GREEN}[PASS]{Style.RESET} 2 Ready Pods terdeteksi.\n")

    # Check 3: kube-proxy routing
    print("Test 3: Validasi Load Balancing kube-proxy...")
    p1, _ = sim.kube_proxy_route("10.96.14.88", 80)
    p2, _ = sim.kube_proxy_route("10.96.14.88", 80)
    assert p1.name != p2.name, "Load balancer round-robin failure!"
    print(f"  {Style.GREEN}[PASS]{Style.RESET} Round-robin traffic distribution valid.\n")

    print(f"{Style.BOLD}{Style.GREEN}✓ Semua 3 Verification Tests Berhasil (100% PASS)!{Style.RESET}")

def main():
    sim = KubeNetworkSimulator()
    show_header()

    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        menu_show_topology(sim)
        menu_coredns(sim)
        menu_service_load_balancing(sim)
        menu_ingress_routing(sim)
        run_automated_suite(sim)
        return

    while True:
        print(f"\n{Style.BOLD}PILIH MENU SIMULASI:{Style.RESET}")
        print("  [1] Tampilkan Topologi Cluster, CNI IPAM & Endpoints")
        print("  [2] Simulasi CoreDNS Name Resolution (SRV & A-Record)")
        print("  [3] Simulasi kube-proxy Load Balancing (ClusterIP VIP)")
        print("  [4] Simulasi Ingress Layer-7 (Host & Path Routing)")
        print("  [5] Jalankan Automated Verification Test Suite")
        print("  [6] Keluar")
        
        try:
            choice = input(f"\n{Style.YELLOW}Pilihan Anda (1-6) [default: 5]: {Style.RESET}").strip()
            if not choice:
                choice = "5"
                
            if choice == "1":
                menu_show_topology(sim)
            elif choice == "2":
                menu_coredns(sim)
            elif choice == "3":
                menu_service_load_balancing(sim)
            elif choice == "4":
                menu_ingress_routing(sim)
            elif choice == "5":
                run_automated_suite(sim)
            elif choice == "6" or choice.lower() == "q":
                print(f"\n{Style.CYAN}Sesi lab simulasi selesai.{Style.RESET}")
                break
            else:
                print(f"{Style.RED}Pilihan tidak valid! Masukkan angka 1 sampai 6.{Style.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Style.CYAN}Program dihentikan oleh user.{Style.RESET}")
            break

if __name__ == "__main__":
    main()
