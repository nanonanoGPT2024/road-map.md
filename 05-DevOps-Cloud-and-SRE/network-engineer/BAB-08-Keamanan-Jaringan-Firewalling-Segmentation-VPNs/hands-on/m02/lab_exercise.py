#!/usr/bin/env python3
"""
Enterprise Network Security Lab: Firewalling, Segmentation, and VPN Simulation
Chapter: BAB-08-Keamanan-Jaringan-Firewalling-Segmentation-VPNs
Module: M02 Advanced Lab Exercise

Simulates:
1. Stateful Packet Inspection (SPI) Engine with Conntrack Table.
2. Micro-segmentation & Zero Trust Network Architecture (ZTNA) Enforcement.
3. Site-to-Site IPsec & WireGuard Overlay Tunnel Status & Encryption Checks.
4. Interactive Packet Injection and Lateral Movement Intrusion Prevention.
"""

import sys
import time
import ipaddress
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


class Action(Enum):
    ALLOW = "ALLOW"
    DROP = "DROP"
    REJECT = "REJECT"


class Protocol(Enum):
    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"
    ESP = "ESP"


class ConnectionState(Enum):
    NEW = "NEW"
    ESTABLISHED = "ESTABLISHED"
    RELATED = "RELATED"
    INVALID = "INVALID"


@dataclass
class Packet:
    src_ip: str
    dst_ip: str
    protocol: Protocol
    src_port: int
    dst_port: int
    flags: List[str] = field(default_factory=list)
    payload_desc: str = ""


@dataclass
class FirewallRule:
    rule_id: int
    src_cidr: str
    dst_cidr: str
    protocol: Protocol
    dst_port: Optional[int]
    action: Action
    description: str


@dataclass
class VPNTunnel:
    name: str
    tunnel_type: str  # IPsec IKEv2 or WireGuard
    local_endpoint: str
    remote_endpoint: str
    cipher: str
    status: str
    tx_bytes: int
    rx_bytes: int
    last_handshake_sec_ago: int


class EnterpriseSecurityGateway:
    def __init__(self):
        # Network Segmentation definitions
        self.zones = {
            "WAN": ipaddress.ip_network("0.0.0.0/0"),
            "DMZ": ipaddress.ip_network("10.100.10.0/24"),
            "APP_TIER": ipaddress.ip_network("10.100.20.0/24"),
            "DB_TIER": ipaddress.ip_network("10.100.30.0/24"),
            "MGMT_OOB": ipaddress.ip_network("10.100.99.0/24"),
            "REMOTE_BRANCH": ipaddress.ip_network("172.16.1.0/24"),
        }

        # Conntrack table: (src_ip, dst_ip, proto, src_port, dst_port) -> state
        self.conntrack_table: Dict[Tuple[str, str, str, int, int], ConnectionState] = {}

        # Default rules
        self.rules: List[FirewallRule] = [
            FirewallRule(10, "0.0.0.0/0", "10.100.10.10/32", Protocol.TCP, 443, Action.ALLOW, "WAN -> DMZ Reverse Proxy HTTPS"),
            FirewallRule(20, "10.100.10.0/24", "10.100.20.0/24", Protocol.TCP, 8080, Action.ALLOW, "DMZ Proxy -> App API Microsegment"),
            FirewallRule(30, "10.100.20.0/24", "10.100.30.50/32", Protocol.TCP, 5432, Action.ALLOW, "App Tier -> Primary PostgreSQL DB"),
            FirewallRule(40, "10.100.99.10/32", "10.100.0.0/16", Protocol.TCP, 22, Action.ALLOW, "Bastion Jump Host -> Internal SSH"),
            FirewallRule(50, "172.16.1.0/24", "10.100.20.0/24", Protocol.TCP, 443, Action.ALLOW, "Branch Site VPN -> Internal Web API"),
            FirewallRule(999, "0.0.0.0/0", "0.0.0.0/0", Protocol.TCP, None, Action.DROP, "Default Deny Lateral & Unauthorized Traffic"),
        ]

        # Active VPN tunnels
        self.vpn_tunnels: List[VPNTunnel] = [
            VPNTunnel(
                name="S2S-DC-JKT-to-Branch-SBY",
                tunnel_type="IPsec IKEv2 / Route-Based VTI",
                local_endpoint="203.0.113.1",
                remote_endpoint="198.51.100.2",
                cipher="AES-GCM-256 / SHA384 / DH-Group21",
                status="UP / ESTABLISHED",
                tx_bytes=4829104,
                rx_bytes=8392110,
                last_handshake_sec_ago=14,
            ),
            VPNTunnel(
                name="WG-DevOps-Overlay-Mesh",
                tunnel_type="WireGuard Modern VPN",
                local_endpoint="203.0.113.5:51820",
                remote_endpoint="Cloud-Gateway:51820",
                cipher="ChaCha20-Poly1305 / Curve25519",
                status="ACTIVE / VERIFIED",
                tx_bytes=1920831,
                rx_bytes=1849102,
                last_handshake_sec_ago=3,
            ),
        ]

    def resolve_zone(self, ip_str: str) -> str:
        ip = ipaddress.ip_address(ip_str)
        for zone_name, net in self.zones.items():
            if zone_name == "WAN":
                continue
            if ip in net:
                return zone_name
        return "WAN"

    def inspect_packet(self, pkt: Packet) -> Tuple[Action, str, str]:
        src_zone = self.resolve_zone(pkt.src_ip)
        dst_zone = self.resolve_zone(pkt.dst_ip)
        conn_key = (pkt.src_ip, pkt.dst_ip, pkt.protocol.value, pkt.src_port, pkt.dst_port)
        reverse_key = (pkt.dst_ip, pkt.src_ip, pkt.protocol.value, pkt.dst_port, pkt.src_port)

        # 1. Stateful Conntrack check
        if reverse_key in self.conntrack_table:
            return Action.ALLOW, "ESTABLISHED / RELATED (Stateful Return Path)", f"{src_zone} -> {dst_zone}"

        # 2. Rule evaluation
        src_addr = ipaddress.ip_address(pkt.src_ip)
        dst_addr = ipaddress.ip_address(pkt.dst_ip)

        for rule in self.rules:
            src_match = src_addr in ipaddress.ip_network(rule.src_cidr)
            dst_match = dst_addr in ipaddress.ip_network(rule.dst_cidr)
            proto_match = (rule.protocol == pkt.protocol)
            port_match = (rule.dst_port is None or rule.dst_port == pkt.dst_port)

            if src_match and dst_match and proto_match and port_match:
                if rule.action == Action.ALLOW:
                    # Update conntrack
                    self.conntrack_table[conn_key] = ConnectionState.ESTABLISHED
                return rule.action, rule.description, f"{src_zone} -> {dst_zone}"

        return Action.DROP, "Implicit Global Default Drop", f"{src_zone} -> {dst_zone}"


def print_banner():
    print(f"{Color.CYAN}{Color.BOLD}" + "=" * 78)
    print("  NETSEC LAB: NEXT-GEN FIREWALL, MICRO-SEGMENTATION & VPN SIMULATOR")
    print("  Enterprise Production Architecture Testing Terminal")
    print("=" * 78 + f"{Color.RESET}\n")


def display_zones(gw: EnterpriseSecurityGateway):
    print(f"{Color.YELLOW}{Color.BOLD}>>> ACTIVE NETWORK SECURITY ZONES (Segmentation Matrix):{Color.RESET}")
    for zone, cidr in gw.zones.items():
        print(f"  {Color.BOLD}[{zone:14}]{Color.RESET} Subnet: {Color.CYAN}{str(cidr):18}{Color.RESET}")
    print()


def display_vpn_status(gw: EnterpriseSecurityGateway):
    print(f"{Color.GREEN}{Color.BOLD}>>> ENTERPRISE VPN OVERLAYS & TUNNELS:{Color.RESET}")
    for vpn in gw.vpn_tunnels:
        print(f"  {Color.BOLD}Tunnel:{Color.RESET} {vpn.name}")
        print(f"    Type: {vpn.tunnel_type}")
        print(f"    Endpoints: {vpn.local_endpoint} <---> {vpn.remote_endpoint}")
        print(f"    Cipher Suite: {Color.MAGENTA}{vpn.cipher}{Color.RESET}")
        print(f"    Tunnel State: {Color.GREEN}{vpn.status}{Color.RESET}")
        print(f"    Telemetry: TX={vpn.tx_bytes} bytes, RX={vpn.rx_bytes} bytes, Keepalive: {vpn.last_handshake_sec_ago}s ago\n")


def display_firewall_rules(gw: EnterpriseSecurityGateway):
    print(f"{Color.BLUE}{Color.BOLD}>>> ACTIVE ACL POLICY TABLE (L4/L7 Stateful Filter):{Color.RESET}")
    print(f"  {'ID':<5} {'Source CIDR':<19} {'Dest CIDR':<19} {'Proto':<6} {'Port':<6} {'Action':<8} {'Policy Name'}")
    print("  " + "-" * 74)
    for r in gw.rules:
        act_col = Color.GREEN if r.action == Action.ALLOW else Color.RED
        port_str = str(r.dst_port) if r.dst_port else "ANY"
        print(f"  {r.rule_id:<5} {r.src_cidr:<19} {r.dst_cidr:<19} {r.protocol.value:<6} {port_str:<6} {act_col}{r.action.value:<8}{Color.RESET} {r.description}")
    print()


def test_packet_flow(gw: EnterpriseSecurityGateway, pkt: Packet):
    action, reason, zone_path = gw.inspect_packet(pkt)
    status_color = Color.GREEN if action == Action.ALLOW else Color.RED
    icon = "[PASSED]" if action == Action.ALLOW else "[BLOCKED]"

    print(f"  {Color.BOLD}Packet Flow:{Color.RESET} {pkt.src_ip}:{pkt.src_port} -> {pkt.dst_ip}:{pkt.dst_port} [{pkt.protocol.value}]")
    print(f"    Zone Path: {Color.CYAN}{zone_path}{Color.RESET} | Payload: {pkt.payload_desc}")
    print(f"    Result: {status_color}{Color.BOLD}{icon} {action.value}{Color.RESET} ({reason})")
    print("  " + "." * 72)


def run_automated_suite(gw: EnterpriseSecurityGateway):
    print(f"{Color.MAGENTA}{Color.BOLD}>>> RUNNING AUTOMATED COMPLIANCE & PENETRATION SUITE...{Color.RESET}\n")

    test_vectors = [
        Packet("198.51.100.55", "10.100.10.10", Protocol.TCP, 51042, 443, ["SYN"], "Legitimate Public User -> Reverse Proxy HTTPS"),
        Packet("10.100.10.10", "10.100.20.15", Protocol.TCP, 38102, 8080, ["SYN"], "DMZ Reverse Proxy -> Internal App API"),
        Packet("10.100.20.15", "10.100.30.50", Protocol.TCP, 41200, 5432, ["SYN"], "App Tier -> Database Tier PostgreSQL"),
        Packet("10.100.10.10", "10.100.30.50", Protocol.TCP, 49120, 5432, ["SYN"], "ATTACK: Compromised DMZ Proxy trying Direct DB Access"),
        Packet("10.100.20.15", "10.100.20.16", Protocol.TCP, 42100, 445, ["SYN"], "ATTACK: Lateral Movement via SMB between App instances"),
        Packet("172.16.1.100", "10.100.20.15", Protocol.TCP, 55210, 443, ["SYN"], "Branch Office via S2S IPsec -> Internal Web App"),
        Packet("198.51.100.99", "10.100.30.50", Protocol.TCP, 61001, 22, ["SYN"], "ATTACK: External Port 22 SSH Scan directly to Database"),
        Packet("10.100.99.10", "10.100.30.50", Protocol.TCP, 50112, 22, ["SYN"], "Admin OOB Bastion -> Database Server SSH Maintenance"),
    ]

    for p in test_vectors:
        test_packet_flow(gw, p)
        time.sleep(0.05)

    print(f"\n{Color.GREEN}{Color.BOLD}✓ All test vectors evaluated against Zero Trust Network Security policies.{Color.RESET}\n")


def interactive_menu(gw: EnterpriseSecurityGateway):
    while True:
        print(f"{Color.CYAN}--- MAIN MENU ---{Color.RESET}")
        print("  1. View Active Security Zones & Topology")
        print("  2. View Firewall SPI Ruleset & Policies")
        print("  3. View Site-to-Site VPN & Overlay Tunnel Status")
        print("  4. Run Automated Zero-Trust & Micro-segmentation Audit")
        print("  5. Inject Custom Packet (Simulate Attack or Flow)")
        print("  6. View Conntrack State Table")
        print("  0. Exit")

        try:
            choice = input(f"\n{Color.YELLOW}Pilih opsi [0-6]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        print()
        if choice == "1":
            display_zones(gw)
        elif choice == "2":
            display_firewall_rules(gw)
        elif choice == "3":
            display_vpn_status(gw)
        elif choice == "4":
            run_automated_suite(gw)
        elif choice == "5":
            try:
                src = input("  Source IP (e.g. 10.100.10.10): ").strip()
                dst = input("  Destination IP (e.g. 10.100.30.50): ").strip()
                port = int(input("  Destination Port (e.g. 5432): ").strip())
                desc = input("  Description / Payload: ").strip() or "Custom Injected Packet"
                pkt = Packet(src, dst, Protocol.TCP, random.randint(30000, 65000), port, ["SYN"], desc)
                print()
                test_packet_flow(gw, pkt)
                print()
            except Exception as e:
                print(f"{Color.RED}Input error: {e}{Color.RESET}\n")
        elif choice == "6":
            print(f"{Color.BLUE}{Color.BOLD}>>> CURRENT STATEFUL CONNTRACK TABLE:{Color.RESET}")
            if not gw.conntrack_table:
                print("  (Table is currently empty. Run test traffic first.)\n")
            else:
                for k, v in gw.conntrack_table.items():
                    print(f"  {k[0]}:{k[3]} -> {k[1]}:{k[4]} [{k[2]}] State: {Color.GREEN}{v.value}{Color.RESET}")
                print()
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih! Sesi lab keamanan jaringan selesai.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Masukkan angka 0-6.{Color.RESET}\n")


def main():
    print_banner()
    gw = EnterpriseSecurityGateway()

    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        display_zones(gw)
        display_firewall_rules(gw)
        display_vpn_status(gw)
        run_automated_suite(gw)
    else:
        # Default interactive with initial baseline display
        display_zones(gw)
        display_vpn_status(gw)
        interactive_menu(gw)


if __name__ == "__main__":
    main()
