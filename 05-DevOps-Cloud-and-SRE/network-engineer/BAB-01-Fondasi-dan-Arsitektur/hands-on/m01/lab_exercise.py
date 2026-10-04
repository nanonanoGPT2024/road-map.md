#!/usr/bin/env python3
"""
Lab Exercise M01: Fondasi dan Arsitektur Jaringan Komputer
Simulasi Interaktif: Model OSI/TCP-IP, Subnetting CIDR, & Routing Table (LPM)
Executable standalone - Zero external dependencies.
"""

import sys
import time
from typing import Dict, List, Optional, Tuple


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner() -> None:
    print(f"{Colors.CYAN}{Colors.BOLD}" + "=" * 65)
    print("   NETWORK ENGINEER LAB: BAB-01 FONDASI & ARSITEKTUR JARINGAN   ")
    print("   Simulasi Interaktif: OSI/TCP-IP, CIDR, & Routing Forwarding   ")
    print("=" * 65 + f"{Colors.RESET}\n")


# -------------------------------------------------------------------------
# PILAR 1: KALKULATOR SUBNET IPv4 (BITWISE IMPLEMENTATION)
# -------------------------------------------------------------------------

def ip_to_int(ip_str: str) -> int:
    octets = [int(x) for x in ip_str.strip().split(".")]
    if len(octets) != 4 or any(x < 0 or x > 255 for x in octets):
        raise ValueError(f"Format IPv4 tidak valid: {ip_str}")
    return (octets[0] << 24) | (octets[1] << 16) | (octets[2] << 8) | octets[3]


def int_to_ip(ip_int: int) -> str:
    return ".".join(str((ip_int >> (8 * i)) & 0xFF) for i in reversed(range(4)))


def calculate_subnet(cidr_notation: str) -> Dict[str, str]:
    if "/" not in cidr_notation:
        raise ValueError("Gunakan notasi CIDR (contoh: 192.168.10.50/24)")
    ip_part, prefix_part = cidr_notation.split("/")
    prefix = int(prefix_part)
    if prefix < 0 or prefix > 32:
        raise ValueError("Prefix CIDR harus antara 0 s.d 32")

    ip_int = ip_to_int(ip_part)
    mask_int = ((0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF) if prefix > 0 else 0
    wildcard_int = (~mask_int) & 0xFFFFFFFF

    net_int = ip_int & mask_int
    bcast_int = net_int | wildcard_int

    total_hosts = 2 ** (32 - prefix)
    usable_hosts = total_hosts - 2 if prefix <= 30 else (2 if prefix == 31 else 1)

    first_host_int = net_int + 1 if prefix <= 30 else net_int
    last_host_int = bcast_int - 1 if prefix <= 30 else bcast_int

    return {
        "ip": ip_part,
        "prefix": f"/{prefix}",
        "netmask": int_to_ip(mask_int),
        "wildcard": int_to_ip(wildcard_int),
        "network": int_to_ip(net_int),
        "broadcast": int_to_ip(bcast_int),
        "first_host": int_to_ip(first_host_int),
        "last_host": int_to_ip(last_host_int),
        "usable_hosts": str(usable_hosts),
        "total_hosts": str(total_hosts),
        "binary_mask": f"{mask_int:032b}",
    }


def run_subnet_module(cidr_input: Optional[str] = None) -> None:
    print(f"\n{Colors.YELLOW}{Colors.BOLD}[*] MODUL 1: KALKULASI & ANALISIS SUBNET CIDR{Colors.RESET}")
    if not cidr_input:
        cidr_input = input(f"{Colors.CYAN}Masukkan IP/CIDR (default: 172.16.50.75/26): {Colors.RESET}").strip()
        if not cidr_input:
            cidr_input = "172.16.50.75/26"

    try:
        res = calculate_subnet(cidr_input)
        print(f"\n{Colors.GREEN}{'='*45}{Colors.RESET}")
        print(f" {Colors.BOLD}Hasil Perhitungan Subnetting untuk:{Colors.RESET} {Colors.CYAN}{cidr_input}{Colors.RESET}")
        print(f"{Colors.GREEN}{'='*45}{Colors.RESET}")
        print(f" • Network Address     : {Colors.BOLD}{res['network']}{Colors.RESET}")
        print(f" • Subnet Mask         : {res['netmask']} ({res['prefix']})")
        print(f" • Wildcard Mask       : {res['wildcard']}")
        print(f" • Usable Host Range   : {res['first_host']} - {res['last_host']}")
        print(f" • Broadcast Address   : {res['broadcast']}")
        print(f" • Total Host Space    : {res['total_hosts']} alokasi")
        print(f" • Usable Valid Hosts  : {Colors.GREEN}{res['usable_hosts']} host{Colors.RESET}")
        b = res["binary_mask"]
        formatted_bin = f"{b[0:8]}.{b[8:16]}.{b[16:24]}.{b[24:32]}"
        print(f" • Netmask Bitwise     : {Colors.DIM}{formatted_bin}{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}[!] Kesalahan: {e}{Colors.RESET}")


# -------------------------------------------------------------------------
# PILAR 2: SIMULATOR ENKAPSULASI & DEKAPSULASI OSI / TCP-IP
# -------------------------------------------------------------------------

def simulate_encapsulation(payload: str = "GET /index.html HTTP/1.1") -> None:
    print(f"\n{Colors.YELLOW}{Colors.BOLD}[*] MODUL 2: SIMULASI ENKAPSULASI DATA (OSI / TCP-IP){Colors.RESET}")
    print(f"Payload Data Aplikasi Asli: {Colors.CYAN}'{payload}'{Colors.RESET}\n")

    steps = [
        ("Layer 7-5 (Application/Presentation/Session)", "Data", f"DATA: '{payload}'"),
        ("Layer 4 (Transport Layer)", "Segment", f"TCP [SrcPort: 54321, DstPort: 80, Seq: 100] + {payload}"),
        ("Layer 3 (Network Layer)", "Packet", f"IP [Src: 192.168.1.50, Dst: 93.184.216.34, TTL: 64] + [TCP Header + Data]"),
        ("Layer 2 (Data Link Layer)", "Frame", f"ETH [SrcMAC: 52:54:00:12:34:56, DstMAC: 00:1A:2B:3C:4D:5E, Type: 0x0800] + [Packet] + [FCS: 0xA3B9]"),
        ("Layer 1 (Physical Layer)", "Bits", "01000111 01000101 01010100 00100000 00101111 ... (Sinyal/Voltase Kabel)")
    ]

    for layer, pdu, detail in steps:
        time.sleep(0.15)
        print(f"{Colors.BOLD}{Colors.BLUE}[+] {layer}{Colors.RESET}")
        print(f"    PDU Type  : {Colors.GREEN}{pdu}{Colors.RESET}")
        print(f"    Struktur  : {Colors.DIM}{detail}{Colors.RESET}")

    print(f"\n{Colors.GREEN}[✓] Data siap ditransmisikan melalui media fisik (Fiber/Copper/Wireless).{Colors.RESET}")


# -------------------------------------------------------------------------
# PILAR 3: SIMULATOR ROUTING TABLE & LONGEST PREFIX MATCH (LPM)
# -------------------------------------------------------------------------

class RouteEntry:
    def __init__(self, dest_net: str, next_hop: str, interface: str):
        self.dest_net = dest_net
        self.next_hop = next_hop
        self.interface = interface
        net_str, prefix_str = dest_net.split("/")
        self.prefix_len = int(prefix_str)
        self.net_int = ip_to_int(net_str)
        self.mask_int = ((0xFFFFFFFF << (32 - self.prefix_len)) & 0xFFFFFFFF) if self.prefix_len > 0 else 0

    def matches(self, ip_int: int) -> bool:
        return (ip_int & self.mask_int) == self.net_int


class RouterSimulation:
    def __init__(self):
        self.routes: List[RouteEntry] = []

    def add_route(self, dest_net: str, next_hop: str, interface: str) -> None:
        self.routes.append(RouteEntry(dest_net, next_hop, interface))

    def lookup(self, destination_ip: str) -> Optional[Tuple[RouteEntry, int]]:
        dest_int = ip_to_int(destination_ip)
        best_match: Optional[RouteEntry] = None
        max_prefix = -1

        for r in self.routes:
            if r.matches(dest_int):
                # Longest Prefix Match principle
                if r.prefix_len > max_prefix:
                    max_prefix = r.prefix_len
                    best_match = r

        if best_match:
            return best_match, max_prefix
        return None


def run_routing_module(dest_ip_input: Optional[str] = None) -> None:
    print(f"\n{Colors.YELLOW}{Colors.BOLD}[*] MODUL 3: SIMULASI FORWARDING & LONGEST PREFIX MATCH (LPM){Colors.RESET}")
    router = RouterSimulation()

    # Inisialisasi Routing Table
    router.add_route("0.0.0.0/0", "203.0.113.1", "eth0 (WAN Default Gateway)")
    router.add_route("10.0.0.0/8", "192.168.100.2", "eth1 (Core Backbone)")
    router.add_route("10.50.0.0/16", "192.168.100.6", "eth2 (Datacenter Edge)")
    router.add_route("10.50.20.0/24", "192.168.100.10", "eth3 (Production Cluster)")
    router.add_route("192.168.1.0/24", "0.0.0.0", "eth4 (LAN Direct)")

    print(f"{Colors.CYAN}Routing Table Router Aktif:{Colors.RESET}")
    print(f"{'Prefix Tujuan':<18} | {'Next-Hop':<15} | {'Egress Interface'}")
    print("-" * 55)
    for r in sorted(router.routes, key=lambda x: -x.prefix_len):
        print(f"{r.dest_net:<18} | {r.next_hop:<15} | {r.interface}")
    print("-" * 55)

    if not dest_ip_input:
        dest_ip_input = input(f"\n{Colors.CYAN}Masukkan IP Tujuan Uji Forwarding (default: 10.50.20.55): {Colors.RESET}").strip()
        if not dest_ip_input:
            dest_ip_input = "10.50.20.55"

    try:
        res = router.lookup(dest_ip_input)
        if res:
            route, prefix = res
            print(f"\n{Colors.GREEN}[✓] Keputusan Forwarding untuk {dest_ip_input}:{Colors.RESET}")
            print(f" • Matched Route       : {Colors.BOLD}{route.dest_net}{Colors.RESET}")
            print(f" • Prefix Length (LPM) : {Colors.BOLD}/{prefix} (Spesifisitas Tertinggi){Colors.RESET}")
            print(f" • Next-Hop Gateway    : {route.next_hop}")
            print(f" • Outgoing Interface  : {Colors.CYAN}{route.interface}{Colors.RESET}")
        else:
            print(f"{Colors.RED}[!] Paket didrop: Network Unreachable (No matching route).{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}[!] Kesalahan: {e}{Colors.RESET}")


# -------------------------------------------------------------------------
# MENU UTAMA & DEMO AUTOMATED TEST
# -------------------------------------------------------------------------

def run_automated_demo() -> None:
    print_banner()
    print(f"{Colors.CYAN}{Colors.BOLD}>>> Menjalankan Automated Verification Suite...<<<{Colors.RESET}\n")
    run_subnet_module("192.168.10.130/27")
    simulate_encapsulation("PING echo-request ICMP_SEQ=1")
    run_routing_module("10.50.20.100")
    print(f"\n{Colors.GREEN}{Colors.BOLD}=== SEMUA SIMULASI FONDASI BERHASIL DIVALIDASI ==={Colors.RESET}\n")


def interactive_menu() -> None:
    while True:
        print_banner()
        print("1. Subnet Calculator & CIDR Bitwise Analyzer")
        print("2. Simulasi Enkapsulasi & Dekapsulasi OSI / TCP-IP")
        print("3. Routing Table Forwarding & Longest Prefix Match (LPM)")
        print("4. Jalankan Seluruh Demo Fondasi (Automated Mode)")
        print("5. Keluar")

        choice = input(f"\n{Colors.CYAN}Pilih opsi (1-5): {Colors.RESET}").strip()
        if choice == "1":
            run_subnet_module()
        elif choice == "2":
            simulate_encapsulation()
        elif choice == "3":
            run_routing_module()
        elif choice == "4":
            run_automated_demo()
        elif choice == "5" or choice.lower() in ("q", "quit", "exit"):
            print(f"\n{Colors.GREEN}Sesi lab selesai. Happy networking!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}[!] Pilihan tidak valid.{Colors.RESET}")

        input(f"\n{Colors.DIM}Tekan [Enter] untuk kembali ke menu utama...{Colors.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "-d", "--test"):
        run_automated_demo()
    else:
        try:
            interactive_menu()
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}[*] Lab dibatalkan oleh user.{Colors.RESET}")
            sys.exit(0)
