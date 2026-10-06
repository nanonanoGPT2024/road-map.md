#!/usr/bin/env python3
"""
Lab Exercise M01: IPv4/IPv6 Subnetting, Bitwise Operations, and LPM Router Simulator
Kurikulum: Network Engineering - BAB 02 (Protokol Internet IPv4/IPv6 & Subnetting)
"""

import sys
import ipaddress
import time
from typing import List, Tuple, Optional

# ANSI Color Codes for terminal formatting
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
BG_BLUE = "\033[44m"
WHITE = "\033[97m"

def print_banner() -> None:
    banner = f"""
{CYAN}{BOLD}================================================================================
          LAB M01: NETWORK ENGINEER IPV4/IPV6 & SUBNETTING SIMULATOR           
================================================================================{RESET}
{DIM}[Modul Fondasi Inti: Bitwise Subnetting, VLSM, IPv6 Prefixing, & LPM Engine]{RESET}
"""
    print(banner)

def to_binary_octets(ip_str: str) -> str:
    """Mengubah alamat IPv4 dotted-decimal menjadi representasi biner 8-bit berjarak titik."""
    octets = [int(x) for x in ip_str.split(".")]
    return ".".join(f"{octet:08b}" for octet in octets)

def analyze_ipv4_network(cidr_input: str) -> None:
    """Menganalisis subnet IPv4 secara mendalam dengan visualisasi biner."""
    print(f"\n{BOLD}{MAGENTA}[*] ANALISIS MENDALAM SUBNET IPV4: {cidr_input}{RESET}")
    print(f"{DIM}{'─' * 70}{RESET}")
    try:
        net = ipaddress.IPv4Network(cidr_input.strip(), strict=False)
    except ValueError as e:
        print(f"{RED}[!] Error input CIDR tidak valid: {e}{RESET}")
        return

    netmask = str(net.netmask)
    hostmask = str(net.hostmask)
    network_addr = str(net.network_address)
    broadcast_addr = str(net.broadcast_address)
    total_hosts = net.num_addresses
    usable_hosts = max(0, total_hosts - 2) if net.prefixlen < 31 else (2 if net.prefixlen == 31 else 1)

    first_usable = str(net.network_address + 1) if usable_hosts > 0 else "N/A"
    last_usable = str(net.broadcast_address - 1) if usable_hosts > 0 else "N/A"

    print(f"  {CYAN}Network Address    :{RESET} {network_addr}")
    print(f"  {CYAN}Subnet Mask        :{RESET} {netmask} (/{net.prefixlen})")
    print(f"  {CYAN}Wildcard Mask      :{RESET} {hostmask}")
    print(f"  {CYAN}Broadcast Address  :{RESET} {broadcast_addr}")
    print(f"  {CYAN}Usable Host Range  :{RESET} {first_usable} - {last_usable}")
    print(f"  {CYAN}Kapasitas Host     :{RESET} {usable_hosts:,} host valid (Total alamat: {total_hosts:,})")

    # Visualisasi Biner
    print(f"\n  {YELLOW}{BOLD}Visualisasi Bitwise & Partisi Mask:{RESET}")
    print(f"  IP Biner   : {GREEN}{to_binary_octets(network_addr)}{RESET}")
    print(f"  Mask Biner : {YELLOW}{to_binary_octets(netmask)}{RESET}")

    # Indikator Network vs Host bits
    mask_flat = "".join(f"{int(x):08b}" for x in netmask.split("."))
    split_idx = net.prefixlen
    bit_visual = (
        f"{GREEN}{mask_flat[:split_idx]} (Network bits){RESET} | "
        f"{RED}{mask_flat[split_idx:]} (Host bits){RESET}"
    )
    print(f"  Struktur   : {bit_visual}")

def calculate_vlsm(base_cidr: str, subnets_demand: List[Tuple[str, int]]) -> None:
    """Melakukan alokasi Variable Length Subnet Masking (VLSM) terurut efisien."""
    print(f"\n{BOLD}{MAGENTA}[*] PERHITUNGAN VLSM UNTUK BASE BLOCK: {base_cidr}{RESET}")
    print(f"{DIM}{'─' * 70}{RESET}")
    try:
        base_net = ipaddress.IPv4Network(base_cidr.strip(), strict=True)
    except ValueError as e:
        print(f"{RED}[!] Base network tidak valid atau bukan network boundary: {e}{RESET}")
        return

    # Sort berdasarkan kebutuhan host terbesar (best practice VLSM)
    sorted_demands = sorted(subnets_demand, key=lambda x: x[1], reverse=True)
    current_addr = int(base_net.network_address)
    base_end = int(base_net.broadcast_address)

    print(f"{'Departemen/Nama':<18} | {'Kebutuhan':<10} | {'Subnet Dialokasikan':<20} | {'Rentang Usable':<32} | {'Sisa Host'}")
    print(f"{'─'*18}─┼─{'─'*10}─┼─{'─'*20}─┼─{'─'*32}─┼─{'─'*10}")

    for name, req_hosts in sorted_demands:
        # Hitung bit host yang dibutuhkan: 2^h - 2 >= req_hosts
        host_bits = 0
        while (2 ** host_bits - 2) < req_hosts:
            host_bits += 1
        prefix_len = 32 - host_bits
        allocated_size = 2 ** host_bits

        if current_addr + allocated_size - 1 > base_end:
            print(f"{RED}{name:<18} | {req_hosts:<10} | ALOKASI GAGAL (Kapasitas Base Block Habis!){RESET}")
            continue

        alloc_net = ipaddress.IPv4Network((current_addr, prefix_len), strict=False)
        first_h = alloc_net.network_address + 1
        last_h = alloc_net.broadcast_address - 1
        waste = (alloc_net.num_addresses - 2) - req_hosts

        print(
            f"{BLUE}{name:<18}{RESET} | "
            f"{req_hosts:<10} | "
            f"{GREEN}{str(alloc_net):<20}{RESET} | "
            f"{first_h} - {last_h} | "
            f"{YELLOW}{waste}{RESET}"
        )
        current_addr += allocated_size

def analyze_ipv6_address(ipv6_input: str) -> None:
    """Menganalisis alamat IPv6, ekspansi hextet, dan identifikasi tipe scoping."""
    print(f"\n{BOLD}{MAGENTA}[*] ANALISIS PROTOKOL INTERNET IPV6: {ipv6_input}{RESET}")
    print(f"{DIM}{'─' * 70}{RESET}")
    try:
        ip6 = ipaddress.IPv6Interface(ipv6_input.strip())
    except ValueError as e:
        print(f"{RED}[!] Alamat IPv6 tidak valid: {e}{RESET}")
        return

    net6 = ip6.network
    full_expanded = ip6.ip.exploded
    compressed = ip6.ip.compressed

    # Identifikasi scope/type
    scope_type = "Unknown"
    if ip6.ip.is_loopback:
        scope_type = "Loopback (::1/128)"
    elif ip6.ip.is_link_local:
        scope_type = "Link-Local Unicast (fe80::/10) - Non-routable diluar L2 domain"
    elif ip6.ip.is_site_local:
        scope_type = "Site-Local (Deprecated)"
    elif ip6.ip.is_private:
        scope_type = "Unique Local Address (ULA fc00::/7 / fd00::/8) - Private IPv6"
    elif ip6.ip.is_multicast:
        scope_type = "Multicast Address (ff00::/8)"
    elif ip6.ip.is_global:
        scope_type = "Global Unicast Address (GUA 2000::/3) - Public Internet Routable"

    print(f"  {CYAN}Compressed Notation   :{RESET} {compressed}")
    print(f"  {CYAN}Full Exploded (128bit):{RESET} {full_expanded}")
    print(f"  {CYAN}Prefix Length         :{RESET} /{ip6.network.prefixlen}")
    print(f"  {CYAN}Network ID (Prefix)   :{RESET} {net6.network_address}")
    print(f"  {CYAN}Tipe / Address Scope  :{RESET} {GREEN}{BOLD}{scope_type}{RESET}")

    # Visualisasi pembagian Global Routing Prefix, Subnet ID, dan Interface Identifier
    hextets = full_expanded.split(":")
    print(f"\n  {YELLOW}Anatomi Arsitektur /64 Standar:{RESET}")
    print(f"  [Global Routing Prefix: {hextets[0]}:{hextets[1]}:{hextets[2]}] "
          f"[Subnet ID: {hextets[3]}] "
          f"[Interface ID: {':'.join(hextets[4:])}]")

def lpm_routing_lookup(routing_table: List[Tuple[str, str, str]], target_ip: str) -> None:
    """Simulasi Router Forwarding Engine: Longest Prefix Match (LPM)."""
    print(f"\n{BOLD}{MAGENTA}[*] ENGINE ROUTING TABLE SIMULATOR: LONGEST PREFIX MATCH{RESET}")
    print(f"{DIM}{'─' * 70}{RESET}")
    print(f"Lookup Target Destination IP: {YELLOW}{BOLD}{target_ip}{RESET}")

    try:
        dest_addr = ipaddress.ip_address(target_ip.strip())
    except ValueError as e:
        print(f"{RED}[!] Target IP tidak valid: {e}{RESET}")
        return

    best_match = None
    longest_prefix = -1
    matching_routes = []

    print(f"\n{'Prefix Terdaftar':<22} | {'Prefixlen':<10} | {'Next-Hop':<15} | {'Interface':<10} | {'Status Match'}")
    print(f"{'─'*22}─┼─{'─'*10}─┼─{'─'*15}─┼─{'─'*10}─┼─{'─'*12}")

    for route_str, nexthop, iface in routing_table:
        route_net = ipaddress.ip_network(route_str)
        is_match = dest_addr in route_net

        status = f"{GREEN}MATCH{RESET}" if is_match else f"{DIM}MISMATCH{RESET}"
        print(f"{route_str:<22} | /{route_net.prefixlen:<9} | {nexthop:<15} | {iface:<10} | {status}")

        if is_match:
            matching_routes.append((route_net, nexthop, iface))
            if route_net.prefixlen > longest_prefix:
                longest_prefix = route_net.prefixlen
                best_match = (route_net, nexthop, iface)

    print(f"{DIM}{'─' * 70}{RESET}")
    if best_match:
        matched_net, nhop, iface = best_match
        print(f"{GREEN}{BOLD}[V] FORWARDING DECISION TERPILIH (LPM):{RESET}")
        print(f"    Rute Terpilih   : {CYAN}{matched_net}{RESET} (Prefix terpanjang: /{longest_prefix})")
        print(f"    Egress Next-Hop : {YELLOW}{nhop}{RESET}")
        print(f"    Out Interface   : {BLUE}{iface}{RESET}")
    else:
        print(f"{RED}[!] Packet Dropped: No route to host (No default gateway configured).{RESET}")

def run_automated_demo() -> None:
    """Menjalankan seluruh skenario demonstrasi secara komprehensif tanpa user input."""
    print(f"\n{BG_BLUE}{WHITE}{BOLD} >>> MENJALANKAN DEMO OTOMATIS SUITE NETWORK-ENGINEER <<< {RESET}\n")

    # Skenario 1: Subnetting IPv4
    analyze_ipv4_network("192.168.10.65/26")
    time.sleep(0.3)

    # Skenario 2: VLSM Planning
    demands = [
        ("Engineering-VLAN", 58),
        ("Finance-VLAN", 26),
        ("VoIP-Phone", 12),
        ("P2P-Router-Link", 2)
    ]
    calculate_vlsm("172.16.0.0/23", demands)
    time.sleep(0.3)

    # Skenario 3: IPv6 Address Classification
    analyze_ipv6_address("2001:0db8:85a3:0000:0000:8a2e:0370:7334/64")
    analyze_ipv6_address("fe80::1ff:fe00:3a60/64")
    time.sleep(0.3)

    # Skenario 4: LPM Forwarding
    rib = [
        ("0.0.0.0/0", "198.51.100.1", "eth0"),
        ("10.0.0.0/8", "10.254.0.1", "eth1"),
        ("10.50.0.0/16", "10.254.50.1", "eth2"),
        ("10.50.4.0/22", "10.254.50.4", "eth3"),
        ("10.50.4.0/24", "10.254.50.254", "eth4"),
    ]
    lpm_routing_lookup(rib, "10.50.4.77")
    lpm_routing_lookup(rib, "8.8.8.8")
    print(f"\n{GREEN}{BOLD}[SUCCESS] Seluruh modul simulasi jaringan dieksekusi dengan sempurna.{RESET}\n")

def interactive_cli() -> None:
    """Antarmuka menu interaktif terminal."""
    print_banner()
    while True:
        print(f"\n{BOLD}PILIHAN MODUL LAB:{RESET}")
        print(f"  {CYAN}1.{RESET} IPv4 Subnet Analyzer & Bitwise Breakdown")
        print(f"  {CYAN}2.{RESET} VLSM (Variable Length Subnet Mask) Generator")
        print(f"  {CYAN}3.{RESET} IPv6 Address Analyzer & Scoping")
        print(f"  {CYAN}4.{RESET} Router FIB/RIB Longest Prefix Match (LPM) Tester")
        print(f"  {CYAN}5.{RESET} Jalankan Automated Full Lab Demo")
        print(f"  {CYAN}0.{RESET} Keluar")

        try:
            choice = input(f"\n{YELLOW}Pilih opsi [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{RED}Sesi dibatalkan.{RESET}")
            break

        if choice == "1":
            cidr = input(f"Masukkan IPv4 CIDR (misal: 10.20.30.0/24): ").strip() or "192.168.1.0/24"
            analyze_ipv4_network(cidr)
        elif choice == "2":
            base = input(f"Masukkan Base Network (misal: 192.168.0.0/24): ").strip() or "192.168.0.0/24"
            print("Masukkan kebutuhan subnet (contoh: LabA=50, LabB=20, Link=2)")
            raw_req = input("Subnet requirements: ").strip() or "Prod=60, Dev=25, WAN=2"
            demands = []
            for item in raw_req.split(","):
                if "=" in item:
                    k, v = item.split("=", 1)
                    if v.strip().isdigit():
                        demands.append((k.strip(), int(v.strip())))
            if demands:
                calculate_vlsm(base, demands)
            else:
                print(f"{RED}[!] Format kebutuhan tidak valid.{RESET}")
        elif choice == "3":
            ip6_in = input(f"Masukkan IPv6 Interface (misal: 2001:db8:abcd::1/64): ").strip() or "2001:db8:acad::1/64"
            analyze_ipv6_address(ip6_in)
        elif choice == "4":
            target = input(f"Masukkan Target IP untuk lookup LPM (misal: 10.50.4.15): ").strip() or "10.50.4.15"
            default_rib = [
                ("0.0.0.0/0", "192.0.2.1", "wan0"),
                ("10.0.0.0/8", "172.16.1.1", "core0"),
                ("10.50.0.0/16", "172.16.2.1", "dist0"),
                ("10.50.4.0/24", "172.16.3.1", "access0"),
            ]
            lpm_routing_lookup(default_rib, target)
        elif choice == "5":
            run_automated_demo()
        elif choice == "0":
            print(f"{GREEN}Lab selesai. Sampai jumpa di materi jaringan berikutnya!{RESET}")
            break
        else:
            print(f"{RED}[!] Pilihan tidak dikenali.{RESET}")

if __name__ == "__main__":
    # Jika dijalankan dengan argument --demo atau non-interactive TTY, jalankan demo
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "-d", "auto", "test"):
        print_banner()
        run_automated_demo()
    elif not sys.stdin.isatty():
        print_banner()
        run_automated_demo()
    else:
        interactive_cli()
