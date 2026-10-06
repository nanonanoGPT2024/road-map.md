#!/usr/bin/env python3
"""
Lab Exercise: Hands-on Network Security, Stateful Firewall, Micro-segmentation & VPN Engine
BAB-08: Keamanan Jaringan (Firewalling, Segmentation, dan VPNs)
Platform: Python 3 Standard Library Simulation
"""

import sys
import time
import hmac
import hashlib
import ipaddress
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# --- ANSI Color Formatting ---
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
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


class Protocol(Enum):
    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"
    ESP = "ESP"  # IPsec Encapsulating Security Payload


class ConntrackState(Enum):
    NEW = "NEW"
    ESTABLISHED = "ESTABLISHED"
    RELATED = "RELATED"
    INVALID = "INVALID"


class SecurityZone(Enum):
    WAN = "WAN (Internet)"
    DMZ = "DMZ (Public Services)"
    CORP_LAN = "CORP_LAN (Internal Office)"
    SECURE_MGMT = "SECURE_MGMT (OOB / Bastion)"
    VPN_TUNNEL = "VPN_IPSEC (Branch Office)"


@dataclass
class Packet:
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: Protocol
    tcp_flags: str = ""  # SYN, ACK, FIN, RST
    payload: str = ""
    is_encrypted: bool = False
    vlan_id: int = 1

    def tuple_key(self) -> Tuple[str, str, int, int, str]:
        return (self.src_ip, self.dst_ip, self.src_port, self.dst_port, self.protocol.value)

    def reverse_tuple_key(self) -> Tuple[str, str, int, int, str]:
        return (self.dst_ip, self.src_ip, self.dst_port, self.src_port, self.protocol.value)


@dataclass
class FirewallRule:
    rule_id: int
    name: str
    src_zone: SecurityZone
    dst_zone: SecurityZone
    src_net: str
    dst_net: str
    dst_port: Optional[int]
    protocol: Protocol
    action: str  # ACCEPT / DROP / REJECT
    allow_states: List[ConntrackState] = field(default_factory=lambda: [ConntrackState.NEW, ConntrackState.ESTABLISHED])


@dataclass
class ConntrackEntry:
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: Protocol
    state: ConntrackState
    bytes_transferred: int = 0
    created_at: float = field(default_factory=time.time)


class StatefulFirewall:
    def __init__(self, default_policy: str = "DROP"):
        self.default_policy = default_policy
        self.rules: List[FirewallRule] = []
        self.conntrack_table: Dict[Tuple[str, str, int, int, str], ConntrackEntry] = {}
        self.blocked_attempts: int = 0
        self.passed_packets: int = 0

    def add_rule(self, rule: FirewallRule):
        self.rules.append(rule)

    def determine_zone(self, ip_str: str) -> SecurityZone:
        ip = ipaddress.ip_address(ip_str)
        if ip in ipaddress.ip_network("10.0.1.0/24"):
            return SecurityZone.DMZ
        elif ip in ipaddress.ip_network("10.0.10.0/24"):
            return SecurityZone.CORP_LAN
        elif ip in ipaddress.ip_network("10.0.99.0/24"):
            return SecurityZone.SECURE_MGMT
        elif ip in ipaddress.ip_network("192.168.50.0/24"):
            return SecurityZone.VPN_TUNNEL
        else:
            return SecurityZone.WAN

    def inspect_packet(self, pkt: Packet) -> Tuple[str, str, ConntrackState]:
        src_zone = self.determine_zone(pkt.src_ip)
        dst_zone = self.determine_zone(pkt.dst_ip)
        key = pkt.tuple_key()
        rev_key = pkt.reverse_tuple_key()

        # 1. State Tracking (Conntrack evaluation)
        state = ConntrackState.INVALID
        if pkt.protocol == Protocol.TCP:
            if "SYN" in pkt.tcp_flags and "ACK" not in pkt.tcp_flags:
                state = ConntrackState.NEW
            elif rev_key in self.conntrack_table or key in self.conntrack_table:
                state = ConntrackState.ESTABLISHED
            else:
                state = ConntrackState.INVALID
        else:
            if key in self.conntrack_table or rev_key in self.conntrack_table:
                state = ConntrackState.ESTABLISHED
            else:
                state = ConntrackState.NEW

        # Allow established reverse flow immediately (Stateful Bypass)
        if rev_key in self.conntrack_table and state == ConntrackState.ESTABLISHED:
            self.passed_packets += 1
            entry = self.conntrack_table[rev_key]
            entry.bytes_transferred += len(pkt.payload) + 40
            return "ACCEPT", f"Established state tracking match (Flow {rev_key[0]} <-> {rev_key[1]})", state

        # 2. Rule evaluation
        src_addr = ipaddress.ip_address(pkt.src_ip)
        dst_addr = ipaddress.ip_address(pkt.dst_ip)

        for rule in self.rules:
            if rule.src_zone != src_zone or rule.dst_zone != dst_zone:
                continue
            if src_addr not in ipaddress.ip_network(rule.src_net):
                continue
            if dst_addr not in ipaddress.ip_network(rule.dst_net):
                continue
            if rule.protocol != pkt.protocol:
                continue
            if rule.dst_port is not None and rule.dst_port != pkt.dst_port:
                continue
            if state not in rule.allow_states:
                continue

            if rule.action == "ACCEPT":
                self.passed_packets += 1
                if state == ConntrackState.NEW:
                    self.conntrack_table[key] = ConntrackEntry(
                        src_ip=pkt.src_ip,
                        dst_ip=pkt.dst_ip,
                        src_port=pkt.src_port,
                        dst_port=pkt.dst_port,
                        protocol=pkt.protocol,
                        state=ConntrackState.ESTABLISHED,
                        bytes_transferred=len(pkt.payload) + 40,
                    )
                return "ACCEPT", f"Matched Rule #{rule.rule_id} [{rule.name}]", state
            else:
                self.blocked_attempts += 1
                return "DROP", f"Explicit DROP by Rule #{rule.rule_id} [{rule.name}]", state

        # 3. Default Policy
        self.blocked_attempts += 1
        return self.default_policy, "Implicit Default Deny (Zero-Trust Security Barrier)", state


class VPNTunnelEngine:
    """Simulates IPsec / WireGuard cryptographic encapsulation and site-to-site transit"""

    def __init__(self, tunnel_name: str, preshared_key: str):
        self.tunnel_name = tunnel_name
        self.psk = preshared_key.encode("utf-8")
        self.seq_num = 1000

    def encapsulate(self, inner_pkt: Packet, gateway_src: str, gateway_dst: str) -> Tuple[Packet, str]:
        self.seq_num += 1
        payload_data = f"{inner_pkt.src_ip}:{inner_pkt.src_port}->{inner_pkt.dst_ip}:{inner_pkt.dst_port}|{inner_pkt.payload}"
        auth_tag = hmac.new(self.psk, f"{self.seq_num}:{payload_data}".encode(), hashlib.sha256).hexdigest()[:16]
        encrypted_blob = f"ESP_SEQ#{self.seq_num}::CIPHERTEXT[{hashlib.sha256(payload_data.encode()).hexdigest()[:24]}]::AUTH_TAG[{auth_tag}]"

        esp_packet = Packet(
            src_ip=gateway_src,
            dst_ip=gateway_dst,
            src_port=500,
            dst_port=500,
            protocol=Protocol.ESP,
            payload=encrypted_blob,
            is_encrypted=True,
            vlan_id=999,
        )
        return esp_packet, auth_tag

    def decapsulate_and_verify(self, esp_pkt: Packet, expected_tag: str) -> bool:
        if not esp_pkt.is_encrypted or "AUTH_TAG" not in esp_pkt.payload:
            return False
        return expected_tag in esp_pkt.payload


def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}================================================================================
       LAB EXERCISE: NEXT-GEN STATEFUL FIREWALL & VPN GATEWAY SIMULATOR
           BAB-08: Keamanan Jaringan, Segmentasi VLAN/DMZ, & IPsec/VPN
================================================================================{Color.RESET}
"""
    print(banner)


def display_topology():
    print(f"{Color.YELLOW}{Color.BOLD}[+] SEGMENTASI ZONA KEAMANAN (SECURITY TOPOLOGY):{Color.RESET}")
    print(f"  {Color.MAGENTA}ZONA WAN (Internet){Color.RESET}         : 0.0.0.0/0 (Untrusted External)")
    print(f"  {Color.BLUE}ZONA DMZ (Public Servers){Color.RESET}    : 10.0.1.0/24 (VLAN 10 - Web/DNS reverse-proxy)")
    print(f"  {Color.GREEN}ZONA CORP_LAN (Internal){Color.RESET}    : 10.0.10.0/24 (VLAN 20 - Workstations, ERP)")
    print(f"  {Color.RED}ZONA SECURE_MGMT (OOB){Color.RESET}     : 10.0.99.0/24 (VLAN 99 - Bastion Host & Core Routers)")
    print(f"  {Color.CYAN}ZONA VPN_TUNNEL (Remote){Color.RESET}    : 192.168.50.0/24 (Site-to-Site Encrypted Overlay)\n")


def build_firewall_rules(fw: StatefulFirewall):
    rules = [
        FirewallRule(10, "Allow WAN to DMZ HTTPS Web", SecurityZone.WAN, SecurityZone.DMZ, "0.0.0.0/0", "10.0.1.100/32", 443, Protocol.TCP, "ACCEPT"),
        FirewallRule(20, "Allow WAN to DMZ DNS", SecurityZone.WAN, SecurityZone.DMZ, "0.0.0.0/0", "10.0.1.53/32", 53, Protocol.UDP, "ACCEPT"),
        FirewallRule(30, "Allow CORP_LAN Outbound Web to WAN", SecurityZone.CORP_LAN, SecurityZone.WAN, "10.0.10.0/24", "0.0.0.0/0", 443, Protocol.TCP, "ACCEPT"),
        FirewallRule(40, "Allow Remote Branch VPN to CORP ERP", SecurityZone.VPN_TUNNEL, SecurityZone.CORP_LAN, "192.168.50.0/24", "10.0.10.50/32", 8443, Protocol.TCP, "ACCEPT"),
        FirewallRule(50, "Allow Bastion Admin SSH to Core", SecurityZone.SECURE_MGMT, SecurityZone.CORP_LAN, "10.0.99.10/32", "10.0.10.0/24", 22, Protocol.TCP, "ACCEPT"),
        FirewallRule(90, "Block DMZ to CORP_LAN Lateral Movement", SecurityZone.DMZ, SecurityZone.CORP_LAN, "10.0.1.0/24", "10.0.10.0/24", None, Protocol.TCP, "DROP"),
        FirewallRule(100, "Allow Site-to-Site IPsec ESP Gateway Transit", SecurityZone.WAN, SecurityZone.WAN, "203.0.113.10/32", "198.51.100.1/32", 500, Protocol.ESP, "ACCEPT"),
    ]
    for r in rules:
        fw.add_rule(r)


def simulate_packet_trace(fw: StatefulFirewall, pkt: Packet, description: str):
    print(f"{Color.BOLD}--- Scenario: {description} ---{Color.RESET}")
    print(f"  {Color.DIM}Packet Ingress:{Color.RESET} {pkt.src_ip}:{pkt.src_port} -> {pkt.dst_ip}:{pkt.dst_port} "
          f"[{pkt.protocol.value} {pkt.tcp_flags}] VLAN:{pkt.vlan_id}")

    src_z = fw.determine_zone(pkt.src_ip).name
    dst_z = fw.determine_zone(pkt.dst_ip).name
    print(f"  {Color.DIM}Zone Routing:{Color.RESET} {Color.BLUE}{src_z}{Color.RESET} ==> {Color.MAGENTA}{dst_z}{Color.RESET}")

    action, reason, state = fw.inspect_packet(pkt)
    if action == "ACCEPT":
        status_tag = f"{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} ACCEPT {Color.RESET}"
    else:
        status_tag = f"{Color.BG_RED}{Color.WHITE}{Color.BOLD} DROP   {Color.RESET}"

    print(f"  Firewall Verdict : {status_tag} {Color.BOLD}(State: {state.value}){Color.RESET}")
    print(f"  Decision Reason  : {Color.DIM}{reason}{Color.RESET}\n")


def run_comprehensive_simulation():
    fw = StatefulFirewall(default_policy="DROP")
    build_firewall_rules(fw)
    vpn = VPNTunnelEngine("BranchOffice-to-HQ", "SuperSecretPreSharedKey2026!@#")

    test_scenarios = [
        (
            Packet("203.0.113.88", "10.0.1.100", 52140, 443, Protocol.TCP, "SYN", "GET /login.html"),
            "Client Eksternal Publik mengakses Web Server HTTPS di DMZ (Legitimate)"
        ),
        (
            Packet("10.0.1.100", "203.0.113.88", 443, 52140, Protocol.TCP, "SYN-ACK", "Handshake ACK"),
            "Return Traffic dari DMZ kembali ke Client Internet (Stateful ESTABLISHED Verification)"
        ),
        (
            Packet("10.0.1.100", "10.0.10.50", 41230, 3306, Protocol.TCP, "SYN", "Lateral Probe to MySQL"),
            "Kompromi DMZ: Hacker mencoba Lateral Movement dari Web Server ke Database Internal LAN"
        ),
        (
            Packet("10.0.10.15", "1.1.1.1", 49152, 443, Protocol.TCP, "SYN", "HTTPS Request to Cloud"),
            "Karyawan Corporate LAN browsing HTTPS ke Cloud/Internet (Allowed Outbound)"
        ),
        (
            Packet("198.51.100.5", "10.0.99.10", 38910, 22, Protocol.TCP, "SYN", "Brute Force SSH to Bastion"),
            "Penyerang Luar (Internet) mencoba membobol port SSH Bastion Management OOB"
        ),
        (
            Packet("10.0.99.10", "10.0.10.2", 50123, 22, Protocol.TCP, "SYN", "Admin Configuration Push"),
            "Senior Sysadmin dari Bastion Management mengonfigurasi Server Internal (Authorized SSH)"
        ),
        (
            Packet("10.0.10.99", "10.0.1.100", 61000, 443, Protocol.TCP, "ACK", "Out of state ACK Injection"),
            "Serangan TCP Out-of-State / ACK Scanning tanpa inisiasi SYN sebelumnya"
        ),
    ]

    print(f"{Color.YELLOW}{Color.BOLD}[1] MENJALANKAN SIMULASI INSPEKSI PAKET STATEFUL:{Color.RESET}\n")
    for pkt, desc in test_scenarios:
        simulate_packet_trace(fw, pkt, desc)
        time.sleep(0.05)

    print(f"{Color.YELLOW}{Color.BOLD}[2] SIMULASI ENKRIPSI & TRANSMISI TUNNEL IPsec/VPN:{Color.RESET}\n")
    inner_packet = Packet("192.168.50.12", "10.0.10.50", 54321, 8443, Protocol.TCP, "SYN", "POST /api/v1/payroll")
    print(f"  {Color.CYAN}Inner Payload (Cleartext sebelum enkripsi):{Color.RESET}")
    print(f"    Payload: {inner_packet.payload} | Route: {inner_packet.src_ip} -> {inner_packet.dst_ip}\n")

    gw_src = "203.0.113.10"
    gw_dst = "198.51.100.1"
    esp_pkt, auth_tag = vpn.encapsulate(inner_packet, gw_src, gw_dst)

    print(f"  {Color.MAGENTA}Tunnel Encapsulation (ESP Header applied):{Color.RESET}")
    print(f"    Outer Header: {esp_pkt.src_ip} -> {esp_pkt.dst_ip} Protocol:{esp_pkt.protocol.value}")
    print(f"    Encrypted Body: {esp_pkt.payload}")
    print(f"    HMAC Integrity Tag: {Color.GREEN}{auth_tag}{Color.RESET}\n")

    print(f"  {Color.BLUE}Pemeriksaan Firewall WAN untuk ESP Transit:{Color.RESET}")
    action, reason, state = fw.inspect_packet(esp_pkt)
    print(f"    Verdict: {action} ({reason})\n")

    print(f"  {Color.GREEN}Penerima IPsec Gateway HQ Decapsulation & Integrity Check:{Color.RESET}")
    valid = vpn.decapsulate_and_verify(esp_pkt, auth_tag)
    print(f"    Integrity Hash Validated: {Color.GREEN}{valid}{Color.RESET} (Paket aman dan utuh)")

    # Test delivery of inner packet inside corporate LAN
    action_inner, reason_inner, state_inner = fw.inspect_packet(inner_packet)
    print(f"    Inner Packet Routing ke ERP: {Color.GREEN}{action_inner}{Color.RESET} - {reason_inner}\n")

    print(f"{Color.CYAN}{Color.BOLD}================================================================================{Color.RESET}")
    print(f"{Color.BOLD}STATISTIK KEAMANAN DAN STATE TRACKING TABLE (CONNTRACK):{Color.RESET}")
    print(f"  Total Paket Lolos (ACCEPTED)   : {Color.GREEN}{fw.passed_packets}{Color.RESET}")
    print(f"  Total Ancaman Ditolak (DROPPED): {Color.RED}{fw.blocked_attempts}{Color.RESET}")
    print(f"  Active Stateful Connections    : {len(fw.conntrack_table)}")
    print("--------------------------------------------------------------------------------")
    print(f"{'SRC IP':<16} {'DST IP':<16} {'PROTO':<6} {'STATE':<12} {'BYTES TRANSFERRED'}")
    print("--------------------------------------------------------------------------------")
    for key, item in fw.conntrack_table.items():
        print(f"{item.src_ip:<16} {item.dst_ip:<16} {item.protocol.value:<6} {item.state.value:<12} {item.bytes_transferred} bytes")
    print("--------------------------------------------------------------------------------\n")


def interactive_mode():
    fw = StatefulFirewall(default_policy="DROP")
    build_firewall_rules(fw)

    print(f"{Color.GREEN}{Color.BOLD}>>> Masuk ke Mode Uji Coba Paket Mandiri (Interactive CLI) <<<{Color.RESET}")
    print("Format input: <src_ip> <dst_ip> <dst_port> <protocol> <flags>")
    print("Contoh: 10.0.10.15 10.0.1.100 443 TCP SYN")
    print("Ketik 'exit' atau tekan Ctrl+C untuk selesai.\n")

    while True:
        try:
            user_input = input(f"{Color.BOLD}Lab-Sec-CLI>{Color.RESET} ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Menutup sesi lab interaktif.")
                break

            parts = user_input.split()
            if len(parts) < 4:
                print(f"{Color.RED}Error: Argumen kurang! Format: <src_ip> <dst_ip> <dst_port> <protocol> [flags]{Color.RESET}")
                continue

            src, dst, port_str, proto_str = parts[0], parts[1], parts[2], parts[3].upper()
            flags = parts[4] if len(parts) > 4 else "SYN"

            proto = Protocol.TCP if proto_str == "TCP" else (Protocol.UDP if proto_str == "UDP" else Protocol.ICMP)
            test_pkt = Packet(
                src_ip=src,
                dst_ip=dst,
                src_port=49152,
                dst_port=int(port_str),
                protocol=proto,
                tcp_flags=flags,
                payload="Interactive test payload"
            )
            simulate_packet_trace(fw, test_pkt, "Uji Coba Manual User")
        except KeyboardInterrupt:
            print("\nSesi dihentikan.")
            break
        except Exception as e:
            print(f"{Color.RED}Error memproses paket: {e}{Color.RESET}")


def main():
    print_banner()
    display_topology()
    run_comprehensive_simulation()

    if "--interactive" in sys.argv or "-i" in sys.argv:
        interactive_mode()
    else:
        print(f"{Color.YELLOW}Petunjuk:{Color.RESET} Jalankan dengan flag {Color.BOLD}--interactive{Color.RESET} untuk menguji paket custom secara bebas.")


if __name__ == "__main__":
    main()
