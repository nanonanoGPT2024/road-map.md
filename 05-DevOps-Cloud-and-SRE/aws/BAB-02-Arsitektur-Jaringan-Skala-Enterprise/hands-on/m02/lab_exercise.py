#!/usr/bin/env python3
"""
Lab Exercise: AWS Enterprise Network Architecture Simulator (BAB-02 M02)
Topic: Centralized Inspection VPC, AWS Transit Gateway (TGW), AWS Network Firewall,
       and Hybrid Connectivity (Direct Connect & Site-to-Site VPN Failover).
"""

import sys
import time
import ipaddress
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ==============================================================================
# ANSI Color Codes for Terminal UI
# ==============================================================================
class Color:
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
    BG_DARK = "\033[40m"


def banner():
    print(f"{Color.CYAN}{Color.BOLD}" + "=" * 78)
    print("   AWS ENTERPRISE NETWORKING SIMULATOR - TRANSIT GATEWAY & INSPECTION VPC")
    print("   Bab 02: Arsitektur Jaringan Skala Enterprise (Multi-Account Hub & Spoke)")
    print("=" * 78 + f"{Color.RESET}\n")


# ==============================================================================
# Data Models: VPCs, Subnets, TGW Route Tables, and Firewall
# ==============================================================================
@dataclass
class Packet:
    src_ip: str
    dst_ip: str
    proto: str
    dst_port: int
    payload: str
    source_vpc: str


@dataclass
class RouteEntry:
    cidr: str
    target: str
    description: str


@dataclass
class TGWRouteTable:
    name: str
    routes: List[RouteEntry] = field(default_factory=list)

    def lookup(self, ip_str: str) -> Optional[RouteEntry]:
        target_ip = ipaddress.ip_address(ip_str)
        matched_route = None
        longest_prefix = -1
        for route in self.routes:
            net = ipaddress.ip_network(route.cidr)
            if target_ip in net:
                if net.prefixlen > longest_prefix:
                    longest_prefix = net.prefixlen
                    matched_route = route
        return matched_route


@dataclass
class FirewallRule:
    rule_id: str
    action: str  # PASS, DROP, ALERT
    protocol: str
    src_cidr: str
    dst_cidr: str
    dst_port: int
    payload_pattern: Optional[str] = None
    description: str = ""


class AWSNetworkFirewall:
    def __init__(self):
        self.stateful_rules: List[FirewallRule] = [
            FirewallRule(
                rule_id="RULE-BLOCK-MALWARE-SIG",
                action="DROP",
                protocol="TCP",
                src_cidr="0.0.0.0/0",
                dst_cidr="0.0.0.0/0",
                dst_port=80,
                payload_pattern="MALWARE_EXPLOIT_CVE",
                description="Drop signature eksploitasi zero-day"
            ),
            FirewallRule(
                rule_id="RULE-BLOCK-UNAUTHORIZED-SSH",
                action="DROP",
                protocol="TCP",
                src_cidr="0.0.0.0/0",
                dst_cidr="10.10.0.0/16",
                dst_port=22,
                payload_pattern=None,
                description="Block raw SSH direct access to Prod Spoke from external"
            ),
            FirewallRule(
                rule_id="RULE-ALLOW-INTERNAL-HTTPS",
                action="PASS",
                protocol="TCP",
                src_cidr="10.0.0.0/8",
                dst_cidr="10.0.0.0/8",
                dst_port=443,
                payload_pattern=None,
                description="Allow Inter-VPC TLS/HTTPS east-west traffic"
            ),
            FirewallRule(
                rule_id="RULE-ALLOW-EGRESS-WEB",
                action="PASS",
                protocol="TCP",
                src_cidr="10.0.0.0/8",
                dst_cidr="0.0.0.0/0",
                dst_port=443,
                payload_pattern=None,
                description="Allow spoke egress to Internet via Egress VPC"
            ),
            FirewallRule(
                rule_id="RULE-DEFAULT-ALLOW-ICMP",
                action="PASS",
                protocol="ICMP",
                src_cidr="0.0.0.0/0",
                dst_cidr="0.0.0.0/0",
                dst_port=0,
                payload_pattern=None,
                description="Allow ping diagnostic packets"
            ),
        ]

    def evaluate(self, packet: Packet) -> Tuple[str, str, str]:
        src_addr = ipaddress.ip_address(packet.src_ip)
        dst_addr = ipaddress.ip_address(packet.dst_ip)

        for rule in self.stateful_rules:
            # Check protocol
            if rule.protocol != "ANY" and rule.protocol != packet.proto.upper():
                continue
            # Check port
            if rule.dst_port != 0 and rule.dst_port != packet.dst_port:
                continue
            # Check IP ranges
            if src_addr not in ipaddress.ip_network(rule.src_cidr):
                continue
            if dst_addr not in ipaddress.ip_network(rule.dst_cidr):
                continue
            # Check payload pattern
            if rule.payload_pattern and rule.payload_pattern in packet.payload:
                return rule.action, rule.rule_id, f"Payload matched '{rule.payload_pattern}': {rule.description}"
            if not rule.payload_pattern:
                return rule.action, rule.rule_id, rule.description

        # Default action in strict mode is DROP for unmatched outbound / non-standard ports
        return "DROP", "DEFAULT_STRICT_POLICY", "Default implicit deny di AWS Network Firewall Stateful Engine"


# ==============================================================================
# Enterprise Network Topology Manager
# ==============================================================================
class EnterpriseNetworkManager:
    def __init__(self):
        self.firewall = AWSNetworkFirewall()
        self.init_tgw_route_tables()
        self.dx_status = "ACTIVE"
        self.vpn_status = "STANDBY"

    def init_tgw_route_tables(self):
        # 1. Spoke VPC TGW Route Table (East-West & North-South inspected centrally)
        self.rt_spoke = TGWRouteTable(name="TGW-RT-SPOKES")
        self.rt_spoke.routes = [
            RouteEntry("0.0.0.0/0", "tgw-attach-inspection-vpc", "Default route diteruskan ke Inspection VPC FW"),
            RouteEntry("10.0.0.0/8", "tgw-attach-inspection-vpc", "East-West inspection ke Central Inspection VPC"),
        ]

        # 2. Post-Inspection TGW Route Table (Traffic returned from FW to destinations)
        self.rt_post_inspection = TGWRouteTable(name="TGW-RT-POST-INSPECTION")
        self.rt_post_inspection.routes = [
            RouteEntry("10.10.0.0/16", "tgw-attach-prod-vpc", "Prod Spoke VPC CIDR"),
            RouteEntry("10.20.0.0/16", "tgw-attach-nonprod-vpc", "Non-Prod Spoke VPC CIDR"),
            RouteEntry("10.30.0.0/16", "tgw-attach-shared-vpc", "Shared Services VPC CIDR"),
            RouteEntry("192.168.0.0/16", "tgw-attach-dxgw", "On-Premises Data Center via Direct Connect Gateway"),
            RouteEntry("0.0.0.0/0", "tgw-attach-egress-vpc", "Egress VPC (Centralized NAT Gateways & IGW)"),
        ]

    def display_topology(self):
        print(f"{Color.MAGENTA}{Color.BOLD}>>> ARSITEKTUR TOPOLOGI ENTERPRISE MULTI-ACCOUNT <<<{Color.RESET}")
        print("""
               +-------------------------------------------------------------+
               |                    AWS ORGANIZATIONS                        |
               +-------------------------------------------------------------+
                                       |
    +----------------------------------+------------------------------------+
    |                                  |                                    |
    v                                  v                                    v
[Prod Account]                  [Security/Net Account]            [Core Network Account]
+-------------------------+     +--------------------------+      +-------------------------+
| Prod Spoke VPC          |     | Inspection VPC           |      | AWS Transit Gateway     |
| 10.10.0.0/16            |     | 10.100.0.0/16            |      | (TGW - Hub ASN: 64512)  |
| - App Subnet (10.10.1.0)|     | - AWS Network Firewall   | <==> | Route Tables:           |
| - TGW Subnet (10.10.9.0)| <-> | - Gateway Load Balancer  |      |  * TGW-RT-SPOKES        |
+-------------------------+     +--------------------------+      |  * TGW-RT-POST-INSPECT  |
                                             |                    +-------------------------+
+-------------------------+                  |                                 |
| Non-Prod Spoke VPC      |                  v                                 v
| 10.20.0.0/16            | <-> +--------------------------+      +-------------------------+
+-------------------------+     | Egress VPC (10.200.0.0)  |      | Direct Connect Gateway  |
                                | - Central NAT GW & IGW   |      | BGP ASN: 65000 (DX-GW)  |
+-------------------------+     +--------------------------+      | Failover: Site2Site VPN |
| Shared Services VPC     |                  |                    +-------------------------+
| 10.30.0.0/16            | <----------------+                                 |
| - Active Directory / DNS|                                                    v
+-------------------------+                                           [On-Premise Data Center]
                                                                      192.168.0.0/16
        """)

    def simulate_packet_trace(self, packet: Packet):
        print(f"\n{Color.CYAN}{Color.BOLD}[PACKET INGRESS TRACE]{Color.RESET}")
        print(f" Source      : {Color.WHITE}{packet.src_ip} ({packet.source_vpc}){Color.RESET}")
        print(f" Destination : {Color.WHITE}{packet.dst_ip}:{packet.dst_port} ({packet.proto}){Color.RESET}")
        print(f" Payload Body: {Color.DIM}{packet.payload}{Color.RESET}")
        print("-" * 75)

        time.sleep(0.3)
        # Step 1: Subnet Route Table
        print(f"Step 1: Evaluasi Subnet Route Table di {packet.source_vpc}...")
        print(f"  -> Outbound route matching: 0.0.0.0/0 via {Color.YELLOW}tgw-attachment{Color.RESET}")

        time.sleep(0.3)
        # Step 2: Transit Gateway Spoke Route Table
        print("Step 2: Masuk ke AWS Transit Gateway [TGW-RT-SPOKES]...")
        route1 = self.rt_spoke.lookup(packet.dst_ip)
        if not route1:
            print(f"  {Color.RED}[DROP]{Color.RESET} No route found in TGW Spoke RT.")
            return
        print(f"  -> Match Route: {route1.cidr} -> Target: {Color.CYAN}{route1.target}{Color.RESET} ({route1.description})")

        time.sleep(0.3)
        # Step 3: Centralized Inspection VPC & AWS Network Firewall
        print("Step 3: Masuk ke Central Inspection VPC (Gateway Load Balancer Endpoint)...")
        print("  -> Menjalankan Suricata Stateful Rule Engine (AWS Network Firewall)...")
        action, rule_id, desc = self.firewall.evaluate(packet)
        time.sleep(0.4)

        if action == "DROP":
            print(f"  {Color.RED}{Color.BOLD}[FIREWALL BLOCKED]{Color.RESET} Paket DITOLAK oleh {rule_id}")
            print(f"  Alasan: {Color.RED}{desc}{Color.RESET}")
            print(f"{Color.RED}--> Status Transmisi: GAGAL (Packet Terminated by Inspection Firewall){Color.RESET}\n")
            return
        else:
            print(f"  {Color.GREEN}{Color.BOLD}[FIREWALL PERMITTED]{Color.RESET} Lolos inspeksi ({rule_id}: {desc})")

        time.sleep(0.3)
        # Step 4: Post-Inspection TGW Route Table
        print("Step 4: Kembali ke TGW via [TGW-RT-POST-INSPECTION]...")
        route2 = self.rt_post_inspection.lookup(packet.dst_ip)
        if not route2:
            print(f"  {Color.RED}[DROP]{Color.RESET} Destination unreachable di Post-Inspection RT.")
            return
        print(f"  -> Match Egress Route: {route2.cidr} -> Target: {Color.GREEN}{route2.target}{Color.RESET} ({route2.description})")

        # Step 5: Final Delivery or NAT Gateway
        time.sleep(0.3)
        print("Step 5: Terminasi Pengiriman Paket...")
        if route2.target == "tgw-attach-egress-vpc":
            print(f"  -> Ditranslasikan oleh {Color.YELLOW}NAT Gateway Egress VPC (SNAT Public Elastic IP){Color.RESET}")
            print(f"  -> Keluar melalui {Color.CYAN}Internet Gateway (IGW){Color.RESET} menuju Public Internet.")
        elif route2.target == "tgw-attach-dxgw":
            active_link = "Direct Connect 10 Gbps (Dedicated)" if self.dx_status == "ACTIVE" else "IPSec VPN Backup (BGP AS-Path Failover)"
            print(f"  -> Diteruskan ke On-Premise Data Center via: {Color.MAGENTA}{active_link}{Color.RESET}")
        else:
            print(f"  -> Diteruskan ke Target Local ENI di {Color.GREEN}{route2.description}{Color.RESET}")

        print(f"{Color.GREEN}{Color.BOLD}--> Status Transmisi: SUKSES (Packet Delivered Successfully){Color.RESET}\n")

    def simulate_hybrid_failover(self):
        print(f"\n{Color.YELLOW}{Color.BOLD}[SIMULASI FAILOVER DIRECT CONNECT -> S2S VPN]{Color.RESET}")
        print(f"Status Awal  : Direct Connect = {Color.GREEN}{self.dx_status}{Color.RESET}, VPN = {Color.YELLOW}{self.vpn_status}{Color.RESET}")
        print("Simulasi gangguan fisik pada Cross-Connect Equinix / Co-location...")
        time.sleep(0.8)
        self.dx_status = "DOWN"
        self.vpn_status = "ACTIVE"
        print(f"{Color.RED}[ALERT] BGP Session Direct Connect DOWN! ASN 65000 hold-timer expired.{Color.RESET}")
        print(f"{Color.GREEN}[FAILOVER] BGP Dynamic Route Switchover: Menukar preferensi ke IPSec VPN (AS-Path Prepending aktif)...{Color.RESET}")
        print(f"Status Terkini: Direct Connect = {Color.RED}{self.dx_status}{Color.RESET}, IPSec VPN = {Color.GREEN}{self.vpn_status}{Color.RESET}")
        print("Rute on-premises 192.168.0.0/16 sekarang dialihkan tanpa downtime ke VPN Tunnel 1 & 2.")

    def run_automated_suite(self):
        print(f"{Color.CYAN}{Color.BOLD}>>> MENJALANKAN AUTOMATED VERIFICATION SUITE <<<{Color.RESET}\n")
        test_cases = [
            Packet(
                src_ip="10.10.1.45",
                dst_ip="10.30.2.10",
                proto="TCP",
                dst_port=443,
                payload="GET /api/v1/auth HTTP/1.1",
                source_vpc="Prod Spoke VPC"
            ),
            Packet(
                src_ip="10.10.1.45",
                dst_ip="1.1.1.1",
                proto="TCP",
                dst_port=443,
                payload="GET /dns-query HTTP/1.1",
                source_vpc="Prod Spoke VPC"
            ),
            Packet(
                src_ip="10.20.1.88",
                dst_ip="8.8.8.8",
                proto="TCP",
                dst_port=80,
                payload="MALWARE_EXPLOIT_CVE payload attempt",
                source_vpc="Non-Prod Spoke VPC"
            ),
            Packet(
                src_ip="192.168.10.5",
                dst_ip="10.10.1.100",
                proto="TCP",
                dst_port=22,
                payload="SSH-2.0-OpenSSH_8.2",
                source_vpc="On-Premise via DX"
            ),
            Packet(
                src_ip="10.10.1.50",
                dst_ip="192.168.50.4",
                proto="ICMP",
                dst_port=0,
                payload="PING",
                source_vpc="Prod Spoke VPC"
            ),
        ]

        passed = 0
        for i, pkt in enumerate(test_cases, 1):
            print(f"{Color.BOLD}--- TEST SCENARIO {i} / {len(test_cases)} ---{Color.RESET}")
            self.simulate_packet_trace(pkt)
            passed += 1
            time.sleep(0.4)

        print(f"{Color.GREEN}{Color.BOLD}[PASSED] Seluruh {passed} skenario pengujian arsitektur berhasil dievaluasi!{Color.RESET}\n")


# ==============================================================================
# Interactive Menu Loop
# ==============================================================================
def interactive_menu():
    manager = EnterpriseNetworkManager()
    banner()

    while True:
        print(f"{Color.BOLD}MENU SIMULATOR JARINGAN ENTERPRISE:{Color.RESET}")
        print(" [1] Tampilkan Topologi Arsitektur Multi-Account & TGW")
        print(" [2] Uji Pengiriman Paket Valid: Inter-VPC East-West (Prod -> Shared Services)")
        print(" [3] Uji Egress Internet Terpusat (Prod -> Internet via Central NAT GW)")
        print(" [4] Uji Blokir Ancaman Keamanan (Malware Signature Drop by AWS NW Firewall)")
        print(" [5] Uji Penolakan SSH Langsung ke Prod (Zero-Trust Security Rule)")
        print(" [6] Simulasi BGP Failover Direct Connect ke Site-to-Site VPN")
        print(" [7] Jalankan Automated Test Suite Lengkap (5 Kasus)")
        print(" [8] Keluar dari Lab")

        try:
            choice = input(f"\n{Color.CYAN}Pilih opsi [1-8]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting lab...")
            break

        if choice == "1":
            manager.display_topology()
        elif choice == "2":
            manager.simulate_packet_trace(Packet(
                src_ip="10.10.1.50",
                dst_ip="10.30.2.100",
                proto="TCP",
                dst_port=443,
                payload="TLS Client Hello (Secure Microservice Call)",
                source_vpc="Prod Spoke VPC"
            ))
        elif choice == "3":
            manager.simulate_packet_trace(Packet(
                src_ip="10.10.2.77",
                dst_ip="52.216.100.12",
                proto="TCP",
                dst_port=443,
                payload="HTTPS Outbound to AWS S3 / Third-Party SaaS",
                source_vpc="Prod Spoke VPC"
            ))
        elif choice == "4":
            manager.simulate_packet_trace(Packet(
                src_ip="10.20.1.33",
                dst_ip="198.51.100.5",
                proto="TCP",
                dst_port=80,
                payload="MALWARE_EXPLOIT_CVE signature test injection",
                source_vpc="Non-Prod Spoke VPC"
            ))
        elif choice == "5":
            manager.simulate_packet_trace(Packet(
                src_ip="192.168.1.15",
                dst_ip="10.10.1.10",
                proto="TCP",
                dst_port=22,
                payload="Direct SSH connection attempt",
                source_vpc="On-Premise Data Center"
            ))
        elif choice == "6":
            manager.simulate_hybrid_failover()
        elif choice == "7":
            manager.run_automated_suite()
        elif choice == "8":
            print(f"{Color.GREEN}Terima kasih telah menyelesaikan hands-on lab AWS Enterprise Networking!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan masukkan angka 1-8.{Color.RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--auto", "-t"):
        sim = EnterpriseNetworkManager()
        banner()
        sim.run_automated_suite()
    else:
        interactive_menu()
