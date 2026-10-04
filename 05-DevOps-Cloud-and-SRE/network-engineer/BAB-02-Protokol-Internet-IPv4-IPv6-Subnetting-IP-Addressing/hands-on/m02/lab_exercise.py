#!/usr/bin/env python3
"""
Lab Exercise: BAB 02 - Protokol Internet (IPv4, IPv6, Subnetting & IP Addressing)
Modul: Network Engineering Advanced Production Architecture Simulator

Fitur Utama:
1. Enterprise IPv4 VLSM (Variable Length Subnet Masking) Engine dengan RFC 3021 /31 Subnet Support.
2. IPv6 Enterprise Hierarchy Planner (/48 -> /56 -> /64) & EUI-64 Link-Local Calculator.
3. Dual-Stack & NAT64/DNS64 Transition Simulator (RFC 6052 Well-Known Prefix 64:ff9b::/96).
4. Bitwise CIDR Inspector & Binary Subnet Mask Visualizer.
5. Automated Production Audit & Self-Test Verification Suite.
"""

import sys
import time
import math
import ipaddress
from typing import List, Dict, Tuple, Optional

# ANSI Color Codes
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
    banner = f"""{Color.CYAN}{Color.BOLD}
================================================================================
   ENTERPRISE NETWORK ARCHITECTURE SIMULATOR - BAB 02
   IPv4 / IPv6 Subnetting, VLSM, Dual-Stack & NAT64 Production Lab
================================================================================{Color.RESET}"""
    print(banner)


def to_binary_octet(ip_int: int, bits: int = 32) -> str:
    bin_str = bin(ip_int)[2:].zfill(bits)
    if bits == 32:
        return ".".join(bin_str[i:i+8] for i in range(0, 32, 8))
    elif bits == 128:
        return ":".join(bin_str[i:i+16] for i in range(0, 128, 16))
    return bin_str


class VLSMSubnetPlanner:
    """Simulasi Enterprise VLSM Subnetting untuk Datacenter Multi-Tier."""

    @staticmethod
    def calculate_vlsm(base_cidr: str, requirements: List[Dict[str, any]]) -> List[Dict[str, any]]:
        network = ipaddress.IPv4Network(base_cidr, strict=True)
        # Urutkan kebutuhan dari host terbanyak ke paling sedikit
        sorted_reqs = sorted(requirements, key=lambda r: r['hosts'], reverse=True)
        
        current_ip = int(network.network_address)
        allocated_subnets = []
        max_ip = int(network.broadcast_address)

        for req in sorted_reqs:
            name = req['name']
            hosts_needed = req['hosts']
            
            # RFC 3021: /31 link point-to-point (2 alamat, 2 host usable)
            if hosts_needed == 2 and req.get('allow_31', False):
                prefix_len = 31
                subnet_size = 2
                usable_hosts = 2
            else:
                # Memerlukan Network ID + Broadcast ID (+2)
                needed_ips = hosts_needed + 2
                prefix_len = 32 - math.ceil(math.log2(needed_ips))
                subnet_size = 2 ** (32 - prefix_len)
                usable_hosts = subnet_size - 2

            # Cek alignment boundary
            if current_ip % subnet_size != 0:
                current_ip += (subnet_size - (current_ip % subnet_size))

            if current_ip + subnet_size - 1 > max_ip:
                raise ValueError(f"Alokasi gagal: Ruang IP pada {base_cidr} tidak cukup untuk {name} ({hosts_needed} hosts)!")

            subnet = ipaddress.IPv4Network((current_ip, prefix_len))
            if prefix_len == 31:
                first_usable = subnet.network_address
                last_usable = subnet.broadcast_address
                broadcast_str = "N/A (RFC 3021 Point-to-Point)"
            else:
                first_usable = subnet.network_address + 1
                last_usable = subnet.broadcast_address - 1
                broadcast_str = str(subnet.broadcast_address)

            allocated_subnets.append({
                "name": name,
                "requested": hosts_needed,
                "allocated_hosts": usable_hosts,
                "prefix": f"/{prefix_len}",
                "network_cidr": str(subnet),
                "netmask": str(subnet.netmask),
                "first_usable": str(first_usable),
                "last_usable": str(last_usable),
                "broadcast": broadcast_str,
                "wastage_percent": round(((usable_hosts - hosts_needed) / usable_hosts) * 100, 1) if usable_hosts > 0 else 0
            })

            current_ip += subnet_size

        return allocated_subnets


class IPv6ArchitecturePlanner:
    """Simulasi Enterprise IPv6 Prefix Delegation, Subnetting, dan EUI-64."""

    @staticmethod
    def mac_to_eui64(mac_str: str, prefix_str: str = "fe80::/64") -> str:
        """Konversi MAC address IEEE 802 ke IPv6 Modified EUI-64 Identifier."""
        clean_mac = mac_str.replace(":", "").replace("-", "").replace(".", "").lower()
        if len(clean_mac) != 12:
            raise ValueError(f"Format MAC Address tidak valid: {mac_str}")

        # Sisipkan FFFE di tengah (setelah 3 oktet)
        eui64_hex = clean_mac[:6] + "fffe" + clean_mac[6:]
        
        # Balik Universal/Local (U/L) bit (bit ke-7 dari octet ke-1)
        first_byte = int(eui64_hex[:2], 16)
        modified_byte = first_byte ^ 0x02
        eui64_modified = f"{modified_byte:02x}" + eui64_hex[2:]

        # Interface identifier 64-bit integer
        iid_int = int(eui64_modified, 16)
        prefix_net = ipaddress.IPv6Network(prefix_str, strict=False)
        if prefix_net.prefixlen != 64:
            raise ValueError(f"SLAAC / EUI-64 mensyaratkan prefix /64 (diberikan /{prefix_net.prefixlen})")

        prefix_int = int(prefix_net.network_address)
        combined_ip_int = prefix_int | iid_int
        return str(ipaddress.IPv6Address(combined_ip_int))

    @staticmethod
    def generate_enterprise_subnets(global_prefix: str, subnets: List[str]) -> List[Dict[str, str]]:
        parent = ipaddress.IPv6Network(global_prefix, strict=False)
        allocations = []
        for idx, sname in enumerate(subnets):
            # Mengambil sub-prefix /64 dari blok enterprise
            vlan_subnet = list(parent.subnets(new_prefix=64))[idx]
            allocations.append({
                "segment": sname,
                "prefix": str(vlan_subnet),
                "gateway": str(vlan_subnet.network_address + 1),
                "slaac_range": f"{vlan_subnet.network_address + 2} - {vlan_subnet.network_address + 0xfffe}",
                "type": "Global Unicast (2000::/3 GUA)"
            })
        return allocations


class DualStackNAT64Engine:
    """Simulasi Transisi IPv6-ke-IPv4 menggunakan Stateful NAT64 & DNS64 (RFC 6052)."""

    WELL_KNOWN_PREFIX = "64:ff9b::/96"

    @classmethod
    def synthesize_ipv6_from_ipv4(cls, ipv4_str: str, prefix_str: str = WELL_KNOWN_PREFIX) -> str:
        ipv4_addr = ipaddress.IPv4Address(ipv4_str)
        nat64_net = ipaddress.IPv6Network(prefix_str)
        if nat64_net.prefixlen != 96:
            raise ValueError("Simulasi ini mensyaratkan NAT64 prefix /96 sesuai RFC 6052!")
        
        # 96-bit prefix + 32-bit IPv4 alamat
        prefix_int = int(nat64_net.network_address)
        ipv4_int = int(ipv4_addr)
        synthesized_int = prefix_int | ipv4_int
        return str(ipaddress.IPv6Address(synthesized_int))

    @classmethod
    def extract_ipv4_from_nat64(cls, ipv6_str: str, prefix_str: str = WELL_KNOWN_PREFIX) -> str:
        ipv6_addr = ipaddress.IPv6Address(ipv6_str)
        nat64_net = ipaddress.IPv6Network(prefix_str)
        if ipv6_addr not in nat64_net:
            raise ValueError(f"{ipv6_str} bukan bagian dari NAT64 prefix {prefix_str}!")
        
        mask32 = 0xFFFFFFFF
        extracted_int = int(ipv6_addr) & mask32
        return str(ipaddress.IPv4Address(extracted_int))


def render_vlsm_table(subnets: List[Dict[str, any]]):
    print(f"\n{Color.YELLOW}{Color.BOLD}>>> HASIL ALOKASI VLSM ENTERPRISE DATACENTER <<<{Color.RESET}")
    header = f"{'Segment':<18} | {'Req':<5} | {'Alloc':<6} | {'Subnet CIDR':<18} | {'Range Usable':<31} | {'Wastage'}"
    print(Color.CYAN + "-" * len(header) + Color.RESET)
    print(Color.BOLD + header + Color.RESET)
    print(Color.CYAN + "-" * len(header) + Color.RESET)
    
    for sub in subnets:
        usable_range = f"{sub['first_usable']} - {sub['last_usable']}"
        waste_color = Color.GREEN if sub['wastage_percent'] < 30 else (Color.YELLOW if sub['wastage_percent'] < 60 else Color.RED)
        print(f"{Color.WHITE}{sub['name']:<18}{Color.RESET} | "
              f"{sub['requested']:<5} | "
              f"{sub['allocated_hosts']:<6} | "
              f"{Color.GREEN}{sub['network_cidr']:<18}{Color.RESET} | "
              f"{usable_range:<31} | "
              f"{waste_color}{sub['wastage_percent']:>5.1f}%{Color.RESET}")
    print(Color.CYAN + "-" * len(header) + Color.RESET)


def render_cidr_inspector(ip_cidr: str):
    try:
        net = ipaddress.IPv4Network(ip_cidr, strict=False)
    except Exception as e:
        print(f"{Color.RED}[ERROR] Format IPv4 CIDR tidak valid: {e}{Color.RESET}")
        return

    netmask_int = int(net.netmask)
    wildcard_int = int(net.hostmask)
    network_int = int(net.network_address)
    broadcast_int = int(net.broadcast_address)
    
    print(f"\n{Color.MAGENTA}{Color.BOLD}>>> BITWISE CIDR & MASK INSPECTOR ({ip_cidr}) <<<{Color.RESET}")
    print(f"Network Address : {Color.GREEN}{net.network_address}{Color.RESET} ({to_binary_octet(network_int)})")
    print(f"Subnet Mask     : {Color.GREEN}{net.netmask}{Color.RESET} ({to_binary_octet(netmask_int)})")
    print(f"Wildcard Mask   : {Color.YELLOW}{net.hostmask}{Color.RESET} ({to_binary_octet(wildcard_int)})")
    print(f"Broadcast IP    : {Color.RED}{net.broadcast_address}{Color.RESET} ({to_binary_octet(broadcast_int)})")
    print(f"Total Addresses : {net.num_addresses:,} alamat")
    usable = net.num_addresses - 2 if net.prefixlen < 31 else (net.num_addresses if net.prefixlen == 31 else 1)
    print(f"Usable Hosts    : {Color.CYAN}{usable:,} hosts{Color.RESET} (Prefix /{net.prefixlen})")


def run_automated_production_tests():
    """Test suite otomatis untuk verifikasi integritas arsitektur jaringan."""
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} RUNNING AUTOMATED AUDIT & SELF-TEST SUITE {Color.RESET}\n")
    
    # 1. Test VLSM
    print(f"[*] Testing Enterprise VLSM Planner (10.100.0.0/16)...", end=" ")
    reqs = [
        {"name": "K8s-Worker-Pool", "hosts": 1200},
        {"name": "Database-Cluster", "hosts": 250},
        {"name": "DMZ-Ingress", "hosts": 60},
        {"name": "P2P-Core-Border", "hosts": 2, "allow_31": True}
    ]
    subnets = VLSMSubnetPlanner.calculate_vlsm("10.100.0.0/16", reqs)
    assert len(subnets) == 4, "Jumlah subnet VLSM harus 4!"
    assert subnets[0]['network_cidr'] == "10.100.0.0/21", "K8s pool harus /21 (2048 IPs)"
    assert subnets[3]['prefix'] == "/31", "P2P Core Border harus dialokasikan /31 (RFC 3021)"
    print(f"{Color.GREEN}[PASSED]{Color.RESET}")

    # 2. Test IPv6 EUI-64
    print(f"[*] Testing EUI-64 Generation & U/L Bit Inversion...", end=" ")
    mac_sample = "00:1a:2b:3c:4d:5e"
    eui64 = IPv6ArchitecturePlanner.mac_to_eui64(mac_sample, "fe80::/64")
    # 00 -> 02 (U/L bit flipped), FFFE inserted -> fe80::21a:2bff:fe3c:4d5e
    assert eui64.lower() == "fe80::21a:2bff:fe3c:4d5e", f"EUI-64 generation salah: {eui64}"
    print(f"{Color.GREEN}[PASSED]{Color.RESET}")

    # 3. Test NAT64 / DNS64 Synthesis
    print(f"[*] Testing NAT64 IPv4 Synthesis & Extraction (RFC 6052)...", end=" ")
    v4_target = "198.51.100.42"
    nat64_v6 = DualStackNAT64Engine.synthesize_ipv6_from_ipv4(v4_target)
    assert nat64_v6 == "64:ff9b::c633:642a", f"NAT64 synthesis gagal: {nat64_v6}"
    recovered_v4 = DualStackNAT64Engine.extract_ipv4_from_nat64(nat64_v6)
    assert recovered_v4 == v4_target, f"NAT64 reverse extraction gagal: {recovered_v4}"
    print(f"{Color.GREEN}[PASSED]{Color.RESET}")

    # 4. Overlap & Boundary Verification
    print(f"[*] Testing Subnet Non-Overlap Invariants...", end=" ")
    nets = [ipaddress.IPv4Network(s['network_cidr']) for s in subnets]
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            assert not nets[i].overlaps(nets[j]), f"Deteksi tabrakan subnet antara {nets[i]} dan {nets[j]}!"
    print(f"{Color.GREEN}[PASSED]{Color.RESET}")

    print(f"\n{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} ALL PRODUCTION TESTS PASSED SUCCESSFULLY! {Color.RESET}\n")


def interactive_menu():
    print_banner()
    
    while True:
        print(f"\n{Color.BOLD}--- MAIN MENU LAB BAB 02 ---{Color.RESET}")
        print(f"1. {Color.CYAN}Simulasi Datacenter VLSM Subnetting (IPv4){Color.RESET}")
        print(f"2. {Color.CYAN}Enterprise IPv6 Architecture & EUI-64 Calculator{Color.RESET}")
        print(f"3. {Color.CYAN}Dual-Stack & Stateful NAT64 Packet Synthesizer{Color.RESET}")
        print(f"4. {Color.CYAN}Bitwise CIDR Subnet & Wildcard Inspector{Color.RESET}")
        print(f"5. {Color.GREEN}Jalankan Automated Production Audit Suite{Color.RESET}")
        print(f"0. {Color.RED}Keluar (Exit){Color.RESET}")

        choice = input(f"\n{Color.YELLOW}Pilih opsi [0-5]: {Color.RESET}").strip()

        if choice == "1":
            print(f"\n{Color.CYAN}[Demo VLSM Multi-Tier Enterprise]{Color.RESET}")
            base_cidr = input("Masukkan Base Supernet (Default: 172.16.0.0/19): ").strip()
            if not base_cidr:
                base_cidr = "172.16.0.0/19"
            
            print(f"Mengalokasikan tier: Core K8s (1500 hosts), App Pool (600 hosts), DB Cluster (120 hosts), P2P WAN (/31)...")
            demo_reqs = [
                {"name": "K8s-Nodes-VLAN10", "hosts": 1500},
                {"name": "App-Service-VLAN20", "hosts": 600},
                {"name": "DB-Tier-VLAN30", "hosts": 120},
                {"name": "P2P-Router-Interlink", "hosts": 2, "allow_31": True}
            ]
            try:
                results = VLSMSubnetPlanner.calculate_vlsm(base_cidr, demo_reqs)
                render_vlsm_table(results)
            except Exception as e:
                print(f"{Color.RED}[ERROR] Gagal menghitung VLSM: {e}{Color.RESET}")

        elif choice == "2":
            print(f"\n{Color.CYAN}[Demo IPv6 Prefix Planning & EUI-64]{Color.RESET}")
            global_prefix = input("Masukkan Global Prefix Enterprise (Default: 2001:db8:acad::/48): ").strip()
            if not global_prefix:
                global_prefix = "2001:db8:acad::/48"
            
            subnets = ["HQ-DataCenter-VLAN10", "HQ-Office-Users-VLAN20", "HQ-DMZ-VLAN30"]
            plan = IPv6ArchitecturePlanner.generate_enterprise_subnets(global_prefix, subnets)
            print(f"\n{Color.YELLOW}Hasil Delegasi /64 Prefix per VLAN:{Color.RESET}")
            for p in plan:
                print(f"- {Color.BOLD}{p['segment']}{Color.RESET}: Prefix: {Color.GREEN}{p['prefix']}{Color.RESET} | Default GW: {p['gateway']}")
            
            mac = input(f"\nMasukkan MAC Address host untuk konversi EUI-64 (Default: 00:50:56:a1:b2:c3): ").strip()
            if not mac:
                mac = "00:50:56:a1:b2:c3"
            eui64 = IPv6ArchitecturePlanner.mac_to_eui64(mac, plan[0]['prefix'])
            print(f"{Color.GREEN}[EUI-64 Generated Address]{Color.RESET}: {Color.BOLD}{eui64}{Color.RESET}")

        elif choice == "3":
            print(f"\n{Color.CYAN}[Demo NAT64/DNS64 IPv4-Embedded Synthesis (RFC 6052)]{Color.RESET}")
            ipv4_target = input("Masukkan Target IPv4 Server (Default: 93.184.216.34 - example.com): ").strip()
            if not ipv4_target:
                ipv4_target = "93.184.216.34"
            
            synthesized_v6 = DualStackNAT64Engine.synthesize_ipv6_from_ipv4(ipv4_target)
            print(f"\n[1] IPv4 Destination Address   : {Color.CYAN}{ipv4_target}{Color.RESET}")
            print(f"[2] NAT64 Well-Known Prefix    : {Color.YELLOW}64:ff9b::/96{Color.RESET}")
            print(f"[3] Synthesized IPv6 Address   : {Color.GREEN}{Color.BOLD}{synthesized_v6}{Color.RESET}")
            
            reversed_v4 = DualStackNAT64Engine.extract_ipv4_from_nat64(synthesized_v6)
            print(f"[4] Reverse Extracted IPv4     : {Color.WHITE}{reversed_v4}{Color.RESET} (Integritas Terverifikasi)")

        elif choice == "4":
            cidr = input("\nMasukkan CIDR notation (contoh: 192.168.10.0/26): ").strip()
            if not cidr:
                cidr = "192.168.10.0/26"
            render_cidr_inspector(cidr)

        elif choice == "5":
            run_automated_production_tests()

        elif choice == "0":
            print(f"{Color.GREEN}Selesai. Selamat belajar network engineering!{Color.RESET}")
            sys.exit(0)

        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--auto", "-t"):
        print_banner()
        run_automated_production_tests()
        sys.exit(0)
    
    # Jalankan interaktif
    try:
        interactive_menu()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Color.YELLOW}[*] Keluar dari simulator.{Color.RESET}")
        sys.exit(0)
