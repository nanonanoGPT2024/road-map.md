#!/usr/bin/env python3
"""
Lab Exercise: Advanced Kubernetes Network Security, CNI, and NetworkPolicies Simulator
Bab 06: Network Security, CNI (Calico/Cilium), and NetworkPolicies
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    GRAY = "\033[90m"


class CNIPlugin(Enum):
    FLANNEL = "Flannel (Host-Gateway / VXLAN - No NetworkPolicy Engine)"
    CALICO = "Calico (IP-in-IP / BGP + Linux iptables/eBPF Policy Engine)"
    CILIUM = "Cilium (eBPF Datapath + Identity-Based L3/L4/L7 NetworkPolicy)"


class TrafficAction(Enum):
    ALLOW = "ALLOW"
    DROP = "DROP"


@dataclass
class Pod:
    name: str
    namespace: str
    ip: str
    labels: Dict[str, str]


@dataclass
class NetworkRule:
    policy_name: str
    direction: str  # "Ingress" or "Egress"
    target_selector: Dict[str, str]
    allowed_from_namespaces: List[str] = field(default_factory=list)
    allowed_from_pod_labels: List[Dict[str, str]] = field(default_factory=list)
    allowed_ports: List[int] = field(default_factory=list)
    allowed_l7_methods: List[str] = field(default_factory=list)  # Cilium L7 feature


class KubernetesNetworkSimulator:
    def __init__(self, cni: CNIPlugin = CNIPlugin.CILIUM):
        self.cni = cni
        self.pods: Dict[str, Pod] = {}
        self.policies: List[NetworkRule] = []
        self.default_deny_ingress: Set[str] = set()  # namespaces with default deny
        self._bootstrap_environment()

    def _bootstrap_environment(self):
        # Microservices topology: Frontend -> API Gateway -> Payment Backend -> Database
        self.pods = {
            "web-frontend": Pod("web-frontend", "prod", "10.244.1.10", {"app": "frontend", "tier": "public"}),
            "api-gateway": Pod("api-gateway", "prod", "10.244.1.11", {"app": "gateway", "tier": "ingress"}),
            "payment-svc": Pod("payment-svc", "finance", "10.244.2.20", {"app": "payment", "tier": "backend", "pci": "true"}),
            "db-postgres": Pod("db-postgres", "finance", "10.244.2.30", {"app": "database", "tier": "data"}),
            "rogue-pod": Pod("rogue-pod", "restricted", "10.244.9.99", {"app": "compromised", "tier": "untrusted"}),
            "monitoring-agent": Pod("monitoring-agent", "monitoring", "10.244.0.5", {"app": "prometheus", "role": "telemetry"}),
        }

        # Apply production-grade zero-trust policies
        self.default_deny_ingress.add("finance")

        # Policy 1: Only API Gateway can reach Payment Service on port 8443
        self.policies.append(
            NetworkRule(
                policy_name="allow-gateway-to-payment",
                direction="Ingress",
                target_selector={"app": "payment"},
                allowed_from_namespaces=["prod"],
                allowed_from_pod_labels=[{"app": "gateway"}],
                allowed_ports=[8443],
                allowed_l7_methods=["POST", "GET"],
            )
        )

        # Policy 2: Only Payment Service can access Database on port 5432
        self.policies.append(
            NetworkRule(
                policy_name="allow-payment-to-db",
                direction="Ingress",
                target_selector={"app": "database"},
                allowed_from_namespaces=["finance"],
                allowed_from_pod_labels=[{"app": "payment"}],
                allowed_ports=[5432],
                allowed_l7_methods=["ALL"],
            )
        )

        # Policy 3: Monitoring scrape allowed on port 9090
        self.policies.append(
            NetworkRule(
                policy_name="allow-monitoring-scrape",
                direction="Ingress",
                target_selector={"tier": "backend"},
                allowed_from_namespaces=["monitoring"],
                allowed_from_pod_labels=[{"app": "prometheus"}],
                allowed_ports=[9090],
                allowed_l7_methods=["GET"],
            )
        )

    def _matches_labels(self, labels: Dict[str, str], selector: Dict[str, str]) -> bool:
        return all(labels.get(k) == v for k, v in selector.items())

    def simulate_packet(
        self,
        src_name: str,
        dst_name: str,
        port: int,
        http_method: str = "GET",
    ) -> Tuple[TrafficAction, str, List[str]]:
        src = self.pods.get(src_name)
        dst = self.pods.get(dst_name)
        trace_logs: List[str] = []

        if not src or not dst:
            return TrafficAction.DROP, "Invalid source or destination pod", trace_logs

        trace_logs.append(
            f"Packet generation: [{src.namespace}/{src.name} ({src.ip})] -> [{dst.namespace}/{dst.name}:{port} ({dst.ip})]"
        )

        # CNI Level 1: Datapath Layer
        if self.cni == CNIPlugin.FLANNEL:
            trace_logs.append(f"[{self.cni.name}] VXLAN encap -> host routing without NetworkPolicy filters.")
            return TrafficAction.ALLOW, "CNI Flannel does NOT enforce NetworkPolicy. All traffic permitted!", trace_logs

        if self.cni == CNIPlugin.CALICO:
            trace_logs.append(f"[{self.cni.name}] Traversal through Linux iptables/calico veth pair & filter chains.")
        elif self.cni == CNIPlugin.CILIUM:
            trace_logs.append(f"[{self.cni.name}] BPF host-routing & tail-call execution via eBPF sockmap & socket LB.")

        # Check default isolation for target namespace
        is_isolated = dst.namespace in self.default_deny_ingress
        trace_logs.append(
            f"Namespace '{dst.namespace}' default ingress posture: {'ISOLATED (Default-Deny)' if is_isolated else 'NON-ISOLATED'}"
        )

        # Find applicable ingress policies
        applicable_policies = [p for p in self.policies if self._matches_labels(dst.labels, p.target_selector)]

        if not applicable_policies:
            if is_isolated:
                trace_logs.append("No whitelist policy matched destination pod. Default-Deny drop triggered.")
                return TrafficAction.DROP, "Default-Deny isolation active for namespace", trace_logs
            trace_logs.append("No policy selected destination pod. Traffic allowed by permissive default.")
            return TrafficAction.ALLOW, "Permissive ingress by default", trace_logs

        trace_logs.append(f"Evaluated {len(applicable_policies)} policy rules targeting '{dst.name}'")

        # Evaluate rules
        for pol in applicable_policies:
            trace_logs.append(f"-> Testing Rule '{pol.policy_name}' against packet attributes:")

            # 1. Check Namespace match
            if pol.allowed_from_namespaces and src.namespace not in pol.allowed_from_namespaces:
                trace_logs.append(f"   [MISMATCH] Source namespace '{src.namespace}' not in {pol.allowed_from_namespaces}")
                continue

            # 2. Check Pod Selector match
            pod_matched = False
            for selector in pol.allowed_from_pod_labels:
                if self._matches_labels(src.labels, selector):
                    pod_matched = True
                    break
            if not pod_matched and pol.allowed_from_pod_labels:
                trace_logs.append(f"   [MISMATCH] Source pod labels {src.labels} failed selector match.")
                continue

            # 3. Check Port match
            if pol.allowed_ports and port not in pol.allowed_ports:
                trace_logs.append(f"   [MISMATCH] Target port {port} not in allowed ports {pol.allowed_ports}")
                continue

            # 4. Check L7 Application inspection (Cilium capability)
            if self.cni == CNIPlugin.CILIUM and pol.allowed_l7_methods and "ALL" not in pol.allowed_l7_methods:
                if http_method not in pol.allowed_l7_methods:
                    trace_logs.append(
                        f"   [eBPF L7 REJECT] Method '{http_method}' rejected by Cilium L7 Envoy/eBPF filter. Expected: {pol.allowed_l7_methods}"
                    )
                    return TrafficAction.DROP, f"Cilium L7 HTTP Policy Violation: Method {http_method} blocked", trace_logs

            trace_logs.append(f"   [MATCH] Packet passed policy rule: '{pol.policy_name}'")
            return TrafficAction.ALLOW, f"Permitted by policy rule: {pol.policy_name}", trace_logs

        trace_logs.append("Packet failed all explicit allow policies.")
        return TrafficAction.DROP, "Blocked by NetworkPolicy Ingress Filter", trace_logs

    def display_topology(self):
        print(f"\n{Color.CYAN}{Color.BOLD}{'=' * 75}{Color.RESET}")
        print(f"{Color.YELLOW}{Color.BOLD}   KUBERNETES CLUSTER TOPOLOGY & POD INVENTORY   {Color.RESET}")
        print(f"{Color.CYAN}{'=' * 75}{Color.RESET}")
        print(f"{'POD NAME':<18} {'NAMESPACE':<12} {'POD IP':<15} {'LABELS'}")
        print("-" * 75)
        for p in self.pods.values():
            lbl_str = ", ".join(f"{k}={v}" for k, v in p.labels.items())
            print(f"{Color.WHITE}{p.name:<18}{Color.RESET} {Color.BLUE}{p.namespace:<12}{Color.RESET} {Color.MAGENTA}{p.ip:<15}{Color.RESET} {Color.GRAY}{lbl_str}{Color.RESET}")
        print(f"{Color.CYAN}{'=' * 75}{Color.RESET}\n")

    def run_security_audit(self):
        print(f"{Color.YELLOW}{Color.BOLD}[*] Executing Automated CNI & NetworkPolicy Matrix Audit...{Color.RESET}\n")
        scenarios = [
            ("web-frontend", "api-gateway", 80, "GET", "Public ingress traffic to API Gateway"),
            ("api-gateway", "payment-svc", 8443, "POST", "Authorized API Gateway payment settlement"),
            ("api-gateway", "payment-svc", 8443, "DELETE", "Unauthorized HTTP DELETE on payment service"),
            ("web-frontend", "payment-svc", 8443, "POST", "Direct bypass attempt: Frontend to Payment"),
            ("rogue-pod", "db-postgres", 5432, "GET", "Lateral movement attempt: Rogue pod to Database"),
            ("payment-svc", "db-postgres", 5432, "GET", "Standard Payment Service DB query"),
            ("monitoring-agent", "payment-svc", 9090, "GET", "Prometheus metric scraping"),
        ]

        for src, dst, port, method, desc in scenarios:
            action, reason, logs = self.simulate_packet(src, dst, port, method)
            status_badge = (
                f"{Color.BG_GREEN}{Color.WHITE} PASS (ALLOW) {Color.RESET}"
                if action == TrafficAction.ALLOW
                else f"{Color.BG_RED}{Color.WHITE} BLOCKED (DROP) {Color.RESET}"
            )
            print(f"{Color.BOLD}Scenario: {desc}{Color.RESET}")
            print(f"Flow: {Color.CYAN}{src}{Color.RESET} -> {Color.CYAN}{dst}:{port}{Color.RESET} [{Color.MAGENTA}{method}{Color.RESET}] => {status_badge}")
            print(f"Verdict: {Color.WHITE}{reason}{Color.RESET}")
            for l in logs:
                print(f"   {Color.GRAY}|_ {l}{Color.RESET}")
            print("-" * 75)
            time.sleep(0.05)


def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}===========================================================================
  KUBERNETES CNI & ZERO-TRUST NETWORKPOLICIES PRODUCTION SIMULATOR
  Bab 06: Advanced Network Security, Flannel/Calico/Cilium, & eBPF Filtering
==========================================================================={Color.RESET}"""
    print(banner)


def main():
    print_banner()

    active_cni = CNIPlugin.CILIUM
    sim = KubernetesNetworkSimulator(cni=active_cni)
    sim.display_topology()

    print(f"Current Active CNI Engine: {Color.GREEN}{Color.BOLD}{active_cni.value}{Color.RESET}\n")

    # If non-interactive execution (e.g. piped or automated tests)
    if not sys.stdin.isatty() or len(sys.argv) > 1 and sys.argv[1] in ("--auto", "-a", "--test"):
        print(f"{Color.YELLOW}[INFO] Non-interactive execution mode detected. Running full security matrix.{Color.RESET}")
        sim.run_security_audit()
        print(f"\n{Color.GREEN}{Color.BOLD}[+] All simulations and audits completed successfully.{Color.RESET}")
        return

    # Interactive CLI Mode
    while True:
        print(f"\n{Color.BOLD}Interactive Control Menu:{Color.RESET}")
        print("  1. Run Complete Zero-Trust Security Audit Matrix")
        print("  2. Inject Custom Microservice Packet Trace")
        print("  3. Switch CNI Engine (Flannel / Calico / Cilium)")
        print("  4. View Pod Inventory & Applied NetworkPolicies")
        print("  5. Exit")

        try:
            choice = input(f"\n{Color.CYAN}Select option [1-5]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting simulator.")
            break

        if choice == "1":
            sim.run_security_audit()
        elif choice == "2":
            print(f"\nAvailable pods: {list(sim.pods.keys())}")
            src = input(f"Source Pod name [{list(sim.pods.keys())[0]}]: ").strip() or "web-frontend"
            dst = input(f"Destination Pod name [{list(sim.pods.keys())[2]}]: ").strip() or "payment-svc"
            port_str = input("Target Port [8443]: ").strip() or "8443"
            method = input("HTTP Method (GET/POST/DELETE) [GET]: ").strip().upper() or "GET"

            try:
                port = int(port_str)
            except ValueError:
                port = 8443

            action, reason, logs = sim.simulate_packet(src, dst, port, method)
            status = f"{Color.GREEN}PERMITTED (ALLOW){Color.RESET}" if action == TrafficAction.ALLOW else f"{Color.RED}DENIED (DROP){Color.RESET}"
            print(f"\n{Color.BOLD}Packet Simulation Result: {status}")
            print(f"Verdict: {reason}{Color.RESET}")
            print(f"\n{Color.YELLOW}Kernel/eBPF Datapath Logs:{Color.RESET}")
            for l in logs:
                print(f"  {Color.GRAY}> {l}{Color.RESET}")
        elif choice == "3":
            print("\nSelect CNI Plugin:")
            print("  1. Flannel (No policy engine)")
            print("  2. Calico (iptables / IPVS / eBPF)")
            print("  3. Cilium (Native eBPF + L7 inspection)")
            cni_choice = input("Choice [1-3]: ").strip()
            if cni_choice == "1":
                sim.cni = CNIPlugin.FLANNEL
            elif cni_choice == "2":
                sim.cni = CNIPlugin.CALICO
            elif cni_choice == "3":
                sim.cni = CNIPlugin.CILIUM
            print(f"{Color.GREEN}[+] CNI switched to: {sim.cni.value}{Color.RESET}")
        elif choice == "4":
            sim.display_topology()
            print(f"{Color.YELLOW}Active Network Policies:{Color.RESET}")
            for pol in sim.policies:
                print(f"  * {Color.WHITE}{pol.policy_name}{Color.RESET} (Ingress to {pol.target_selector})")
                print(f"    From Namespaces: {pol.allowed_from_namespaces}, Ports: {pol.allowed_ports}, L7: {pol.allowed_l7_methods}")
        elif choice == "5":
            print("Exiting simulator.")
            break
        else:
            print(f"{Color.RED}Invalid option selected.{Color.RESET}")


if __name__ == "__main__":
    main()
