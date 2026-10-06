#!/usr/bin/env python3
"""
Lab Exercise: Layer 3 Routing Fundamentals, Static Routing & FHRP Simulation
Module: BAB-04-Layer-3-Routing-Fundamentals-Static-Routing-FHRP / M01
Description:
    Simulasi interaktif konsep fundamental Layer 3 routing:
    - Longest Prefix Match (LPM) & Routing Table Lookup
    - Administrative Distance (AD) & Metric Comparison
    - Floating Static Route Failover
    - First Hop Redundancy Protocol (FHRP / VRRP / HSRP) State Machine & Virtual Gateway Failover
"""

import sys
import time
import ipaddress
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

# ANSI Terminal Color Constants
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"


class RouteType(Enum):
    CONNECTED = "C (Connected)"
    STATIC = "S (Static)"
    FLOATING_STATIC = "S* (Floating Static)"
    DEFAULT = "S* (Default Route)"


@dataclass
class RouteEntry:
    destination: ipaddress.IPv4Network
    next_hop: Optional[ipaddress.IPv4Address]
    interface: str
    admin_distance: int
    metric: int
    route_type: RouteType
    is_active: bool = True

    def matches(self, ip: ipaddress.IPv4Address) -> bool:
        return self.is_active and (ip in self.destination)


class VRRPState(Enum):
    INITIALIZE = "INITIALIZE"
    MASTER = "MASTER (Active Gateway)"
    BACKUP = "BACKUP (Standby Gateway)"


@dataclass
class VRRPNode:
    name: str
    ip: ipaddress.IPv4Address
    priority: int
    preempt: bool
    state: VRRPState = VRRPState.INITIALIZE
    is_alive: bool = True


class Router:
    def __init__(self, name: str):
        self.name = name
        self.routing_table: List[RouteEntry] = []

    def add_route(self, route: RouteEntry) -> None:
        self.routing_table.append(route)

    def longest_prefix_match(self, dest_ip: ipaddress.IPv4Address) -> Optional[Tuple[RouteEntry, List[RouteEntry]]]:
        """
        Melakukan evaluasi LPM (Longest Prefix Match):
        1. Cari seluruh rute aktif yang subnet-nya melingkupi dest_ip.
        2. Pilih kandidat dengan prefix length terpanjang (/32 > /24 > /16 > /0).
        3. Jika prefix length sama, pilih Administrative Distance terkecil.
        4. Jika AD sama, pilih metric terkecil.
        """
        matching_routes = [r for r in self.routing_table if r.matches(dest_ip)]
        if not matching_routes:
            return None

        # Sort: descending prefixlen, ascending AD, ascending metric
        sorted_candidates = sorted(
            matching_routes,
            key=lambda r: (r.destination.prefixlen, -r.admin_distance, -r.metric),
            reverse=True
        )
        return sorted_candidates[0], matching_routes


class NetworkSimulator:
    def __init__(self):
        self.r1 = Router("R1-EdgeGateway")
        self.r2 = Router("R2-BackupGateway")
        self._init_topology()

        # VRRP / FHRP Configuration for LAN 192.168.10.0/24
        self.virtual_ip = ipaddress.IPv4Address("192.168.10.1")
        self.virtual_mac = "00:00:5E:00:01:0A"
        self.vrrp_r1 = VRRPNode(
            name="R1-EdgeGateway",
            ip=ipaddress.IPv4Address("192.168.10.2"),
            priority=110,
            preempt=True,
            state=VRRPState.MASTER
        )
        self.vrrp_r2 = VRRPNode(
            name="R2-BackupGateway",
            ip=ipaddress.IPv4Address("192.168.10.3"),
            priority=100,
            preempt=True,
            state=VRRPState.BACKUP
        )

    def _init_topology(self) -> None:
        # R1 Routing Table
        self.r1.add_route(RouteEntry(
            destination=ipaddress.IPv4Network("192.168.10.0/24"),
            next_hop=None,
            interface="GigabitEthernet0/0 (LAN)",
            admin_distance=0,
            metric=0,
            route_type=RouteType.CONNECTED
        ))
        self.r1.add_route(RouteEntry(
            destination=ipaddress.IPv4Network("10.0.12.0/30"),
            next_hop=None,
            interface="GigabitEthernet0/1 (ISP1-Primary)",
            admin_distance=0,
            metric=0,
            route_type=RouteType.CONNECTED
        ))
        # Specific Branch Route
        self.r1.add_route(RouteEntry(
            destination=ipaddress.IPv4Network("172.16.50.0/24"),
            next_hop=ipaddress.IPv4Address("10.0.12.2"),
            interface="GigabitEthernet0/1 (ISP1-Primary)",
            admin_distance=1,
            metric=0,
            route_type=RouteType.STATIC
        ))
        # Default Route via Primary ISP (AD = 1)
        self.r1.add_route(RouteEntry(
            destination=ipaddress.IPv4Network("0.0.0.0/0"),
            next_hop=ipaddress.IPv4Address("10.0.12.2"),
            interface="GigabitEthernet0/1 (ISP1-Primary)",
            admin_distance=1,
            metric=10,
            route_type=RouteType.DEFAULT
        ))
        # Floating Static Default Route via Backup ISP Link (AD = 10)
        self.r1.add_route(RouteEntry(
            destination=ipaddress.IPv4Network("0.0.0.0/0"),
            next_hop=ipaddress.IPv4Address("10.0.22.2"),
            interface="GigabitEthernet0/2 (ISP2-Backup)",
            admin_distance=10,
            metric=20,
            route_type=RouteType.FLOATING_STATIC
        ))

    def display_banner(self) -> None:
        print(f"{CYAN}{'=' * 75}{RESET}")
        print(f"{BOLD}{GREEN}  L3 ROUTING FUNDAMENTALS & FHRP LAB SIMULATOR (PYTHON 3 CLI){RESET}")
        print(f"{WHITE}  Topologi: LAN (192.168.10.0/24) -> R1 (Master) / R2 (Backup) -> WAN{RESET}")
        print(f"{CYAN}{'=' * 75}{RESET}\n")

    def show_routing_table(self, router: Router) -> None:
        print(f"\n{BOLD}{MAGENTA}=== Routing Table: {router.name} ==={RESET}")
        print(f"{'Destination Subnet':<20} {'Next-Hop':<16} {'Interface':<24} {'AD/Metric':<12} {'Status':<10}")
        print("-" * 85)
        for r in router.routing_table:
            status = f"{GREEN}ACTIVE{RESET}" if r.is_active else f"{RED}INACTIVE{RESET}"
            nh = str(r.next_hop) if r.next_hop else "Directly Connected"
            ad_m = f"[{r.admin_distance}/{r.metric}]"
            print(f"{str(r.destination):<20} {nh:<16} {r.interface:<24} {ad_m:<12} {status}")
        print("-" * 85)

    def simulate_lpm(self, ip_str: str) -> None:
        try:
            target_ip = ipaddress.IPv4Address(ip_str)
        except ValueError:
            print(f"{RED}[ERROR] Format IP Address '{ip_str}' tidak valid!{RESET}")
            return

        print(f"\n{YELLOW}[*] Menjalankan Routing Lookup untuk Target: {BOLD}{target_ip}{RESET} pada {self.r1.name}...")
        result = self.r1.longest_prefix_match(target_ip)

        if not result:
            print(f"{RED}[DROP] Packet Terbuang! Network Unreachable (No Route to Host).{RESET}")
            return

        best_route, all_matches = result
        print(f"{BLUE}[INFO] Rute yang cocok (Candidates):{RESET}")
        for match in all_matches:
            marker = f"{GREEN}--> [SELECTED LPM]{RESET}" if match is best_route else "    [SHADOWED]"
            print(f" {marker} Prefix: {str(match.destination):<18} Type: {match.route_type.value} AD/Metric: [{match.admin_distance}/{match.metric}] via {match.interface}")

        print(f"\n{GREEN}[FORWARD] Hasil Keputusan Forwarding Layer 3:{RESET}")
        print(f"  • Selected Prefix Length : /{best_route.destination.prefixlen} (Longest Prefix Match)")
        print(f"  • Egress Interface       : {BOLD}{best_route.interface}{RESET}")
        print(f"  • Next-Hop Address       : {best_route.next_hop if best_route.next_hop else 'ARP directly on link'}")
        print(f"  • Route Classification   : {best_route.route_type.value}")

    def toggle_primary_wan_link(self) -> None:
        primary_routes = [r for r in self.r1.routing_table if "ISP1-Primary" in r.interface or (r.next_hop and str(r.next_hop) == "10.0.12.2")]
        current_state = primary_routes[0].is_active if primary_routes else True
        new_state = not current_state

        for r in primary_routes:
            r.is_active = new_state

        state_str = f"{GREEN}UP (RESTORED){RESET}" if new_state else f"{RED}DOWN (FAILED){RESET}"
        print(f"\n{YELLOW}[!] WAN Primary Link ISP1 diubah statusnya menjadi: {state_str}")
        print(f"[*] Mengevaluasi Floating Static Route otomatis...")

        time.sleep(0.5)
        # Check current default route
        dummy_ip = ipaddress.IPv4Address("8.8.8.8")
        result = self.r1.longest_prefix_match(dummy_ip)
        if result:
            best_route, _ = result
            print(f"{GREEN}[FAILOVER RESULT] Default Route sekarang diarahkan ke:{RESET}")
            print(f"  • Interface : {BOLD}{best_route.interface}{RESET}")
            print(f"  • Next-Hop  : {best_route.next_hop}")
            print(f"  • AD/Metric : [{best_route.admin_distance}/{best_route.metric}] ({best_route.route_type.value})")
        else:
            print(f"{RED}[FAILOVER RESULT] Tidak ada default route yang aktif!{RESET}")

    def show_fhrp_status(self) -> None:
        print(f"\n{BOLD}{CYAN}=== FHRP / VRRP Group 10 Status ==={RESET}")
        print(f"Virtual IP (Default Gateway Host) : {BOLD}{GREEN}{self.virtual_ip}{RESET}")
        print(f"Virtual MAC                       : {BOLD}{self.virtual_mac}{RESET}")
        print("-" * 75)
        print(f"{'Node Name':<18} {'Physical IP':<16} {'Priority':<10} {'Preempt':<10} {'State':<20} {'Health':<8}")
        print("-" * 75)
        for node in [self.vrrp_r1, self.vrrp_r2]:
            health = f"{GREEN}ALIVE{RESET}" if node.is_alive else f"{RED}DEAD{RESET}"
            state_color = GREEN if node.state == VRRPState.MASTER else YELLOW
            print(f"{node.name:<18} {str(node.ip):<16} {node.priority:<10} {str(node.preempt):<10} {state_color}{node.state.value:<20}{RESET} {health}")
        print("-" * 75)

    def trigger_fhrp_election(self) -> None:
        """Kalkulasi VRRP State Machine berdasarkan Priority dan Health"""
        print(f"\n{YELLOW}[*] Menjalankan VRRP Heartbeat / Election cycle...{RESET}")
        time.sleep(0.4)

        if self.vrrp_r1.is_alive and self.vrrp_r2.is_alive:
            if self.vrrp_r1.priority >= self.vrrp_r2.priority:
                self.vrrp_r1.state = VRRPState.MASTER
                self.vrrp_r2.state = VRRPState.BACKUP
            else:
                self.vrrp_r1.state = VRRPState.BACKUP
                self.vrrp_r2.state = VRRPState.MASTER
        elif self.vrrp_r1.is_alive and not self.vrrp_r2.is_alive:
            self.vrrp_r1.state = VRRPState.MASTER
            self.vrrp_r2.state = VRRPState.INITIALIZE
        elif not self.vrrp_r1.is_alive and self.vrrp_r2.is_alive:
            self.vrrp_r1.state = VRRPState.INITIALIZE
            self.vrrp_r2.state = VRRPState.MASTER
        else:
            self.vrrp_r1.state = VRRPState.INITIALIZE
            self.vrrp_r2.state = VRRPState.INITIALIZE

        active_gw = None
        if self.vrrp_r1.state == VRRPState.MASTER:
            active_gw = self.vrrp_r1
        elif self.vrrp_r2.state == VRRPState.MASTER:
            active_gw = self.vrrp_r2

        if active_gw:
            print(f"{GREEN}[SUCCESS] VRRP Master Gateway aktif adalah: {BOLD}{active_gw.name} (IP: {active_gw.ip}){RESET}")
            print(f"          Menghandle ARP request untuk Virtual IP {self.virtual_ip} -> {self.virtual_mac}")
        else:
            print(f"{RED}[CRITICAL] Seluruh Gateway MATI! Host LAN kehilangan koneksi keluar.{RESET}")

    def toggle_r1_fhrp_node(self) -> None:
        self.vrrp_r1.is_alive = not self.vrrp_r1.is_alive
        status = f"{GREEN}ONLINE{RESET}" if self.vrrp_r1.is_alive else f"{RED}OFFLINE / CRASHED{RESET}"
        print(f"\n{YELLOW}[!] Status Node {self.vrrp_r1.name} diubah menjadi: {status}")
        self.trigger_fhrp_election()

    def run_automated_selftest(self) -> bool:
        print(f"\n{BOLD}{MAGENTA}=== MENJALANKAN AUTOMATED VERIFICATION TEST SUITE ==={RESET}")
        tests_passed = 0
        total_tests = 4

        # Test 1: LPM specific subnet vs default route
        print(f"[{YELLOW}TEST 1{RESET}] Verifikasi Longest Prefix Match (LPM)... ", end="")
        res_specific = self.r1.longest_prefix_match(ipaddress.IPv4Address("172.16.50.45"))
        if res_specific and res_specific[0].destination.prefixlen == 24:
            print(f"{GREEN}PASSED (/24 dipilih sebelum /0){RESET}")
            tests_passed += 1
        else:
            print(f"{RED}FAILED{RESET}")

        # Test 2: Default route selection
        print(f"[{YELLOW}TEST 2{RESET}] Verifikasi Default Route (0.0.0.0/0)... ", end="")
        res_default = self.r1.longest_prefix_match(ipaddress.IPv4Address("8.8.4.4"))
        if res_default and res_default[0].destination.prefixlen == 0 and res_default[0].admin_distance == 1:
            print(f"{GREEN}PASSED (Primary Static AD=1 aktif){RESET}")
            tests_passed += 1
        else:
            print(f"{RED}FAILED{RESET}")

        # Test 3: Floating static failover logic
        print(f"[{YELLOW}TEST 3{RESET}] Verifikasi Floating Static Route Failover... ", end="")
        for r in self.r1.routing_table:
            if "ISP1-Primary" in r.interface:
                r.is_active = False
        res_failover = self.r1.longest_prefix_match(ipaddress.IPv4Address("8.8.4.4"))
        if res_failover and res_failover[0].admin_distance == 10:
            print(f"{GREEN}PASSED (Backup Static AD=10 otomatis menggantikan){RESET}")
            tests_passed += 1
        else:
            print(f"{RED}FAILED{RESET}")
        # Restore state
        for r in self.r1.routing_table:
            r.is_active = True

        # Test 4: FHRP Master Failover
        print(f"[{YELLOW}TEST 4{RESET}] Verifikasi VRRP Gateway Failover... ", end="")
        self.vrrp_r1.is_alive = False
        self.trigger_fhrp_election()
        if self.vrrp_r2.state == VRRPState.MASTER:
            print(f"{GREEN}PASSED (R2 naik jadi MASTER saat R1 down){RESET}")
            tests_passed += 1
        else:
            print(f"{RED}FAILED{RESET}")
        # Restore R1
        self.vrrp_r1.is_alive = True
        self.trigger_fhrp_election()

        print("-" * 60)
        print(f"Hasil: {GREEN}{tests_passed}/{total_tests} Test Cases Berhasil!{RESET}\n")
        return tests_passed == total_tests


def print_menu() -> None:
    print(f"\n{BOLD}PILIHAN SIMULASI INTERAKTIF:{RESET}")
    print(f"  {CYAN}1.{RESET} Tampilkan Tabel Routing R1 (RIB / Routing Information Base)")
    print(f"  {CYAN}2.{RESET} Simulasi Packet Forwarding & Longest Prefix Match (LPM)")
    print(f"  {CYAN}3.{RESET} Toggle WAN Primary Link (Uji Floating Static Route Failover)")
    print(f"  {CYAN}4.{RESET} Tampilkan Status FHRP / VRRP (Virtual Gateway Redundancy)")
    print(f"  {CYAN}5.{RESET} Toggle Primary Router R1 Power (Uji FHRP Gateway Failover)")
    print(f"  {CYAN}6.{RESET} Jalankan Automated Self-Test Suite")
    print(f"  {RED}0.{RESET} Keluar (Exit)")


def main() -> None:
    sim = NetworkSimulator()
    sim.display_banner()

    # Jika dipanggil tanpa TTY / non-interaktif, jalankan self-test otomatis
    if not sys.stdin.isatty():
        print(f"{YELLOW}[Mode Non-Interaktif terdeteksi] Menjalankan automated test suite...{RESET}")
        success = sim.run_automated_selftest()
        sys.exit(0 if success else 1)

    while True:
        print_menu()
        try:
            choice = input(f"\n{BOLD}Pilih opsi [0-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Simulasi dihentikan.{RESET}")
            break

        if choice == "1":
            sim.show_routing_table(sim.r1)
        elif choice == "2":
            ip_input = input(f"{YELLOW}Masukkan Destination IP untuk diuji (contoh: 172.16.50.25 atau 1.1.1.1): {RESET}").strip()
            if ip_input:
                sim.simulate_lpm(ip_input)
        elif choice == "3":
            sim.toggle_primary_wan_link()
        elif choice == "4":
            sim.show_fhrp_status()
        elif choice == "5":
            sim.toggle_r1_fhrp_node()
        elif choice == "6":
            sim.run_automated_selftest()
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menggunakan L3 Routing Simulator.{RESET}")
            break
        else:
            print(f"{RED}[!] Opsi tidak dikenali. Silakan masukkan angka 0-6.{RESET}")


if __name__ == "__main__":
    main()
