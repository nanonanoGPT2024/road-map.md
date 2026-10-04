#!/usr/bin/env python3
"""
Lab Exercise M02: Advanced Layer 3 Routing & FHRP (HSRP/VRRP) Architecture Simulation
Topic: BAB-04 - Layer 3 Routing Fundamentals, Static Routing, and First Hop Redundancy Protocols

Features:
- Longest Prefix Match (LPM) routing engine implementation using ipaddress
- Floating static routing with Administrative Distance (AD) and metric-based failover
- VRRP / HSRP state machine (Active/Standby, Priority, Preemption, Virtual IP/MAC)
- Uplink interface tracking & automatic priority decrement
- Interactive CLI with ANSI terminal coloring and step-by-step diagnostic verification
"""

import ipaddress
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# ANSI Terminal Color Palettes
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
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

def banner(title: str) -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === [ {title} ] === {Color.RESET}\n")

def info(msg: str) -> None:
    print(f"{Color.CYAN}[INFO]{Color.RESET} {msg}")

def success(msg: str) -> None:
    print(f"{Color.GREEN}[OK]{Color.RESET} {msg}")

def warn(msg: str) -> None:
    print(f"{Color.YELLOW}[WARN]{Color.RESET} {msg}")

def alert(msg: str) -> None:
    print(f"{Color.RED}[ALERT]{Color.RESET} {msg}")

class FHRPState(Enum):
    INITIAL = "INITIAL"
    STANDBY = "STANDBY"
    ACTIVE = "ACTIVE"

@dataclass
class StaticRoute:
    prefix: ipaddress.IPv4Network
    next_hop: ipaddress.IPv4Address
    interface_name: str
    admin_distance: int = 1  # Standard static route AD
    metric: int = 0
    description: str = ""

@dataclass
class Interface:
    name: str
    ip_addr: ipaddress.IPv4Interface
    is_up: bool = True
    speed_mbps: int = 1000

@dataclass
class FHRPConfig:
    group_id: int
    virtual_ip: ipaddress.IPv4Address
    virtual_mac: str
    priority: int
    configured_priority: int
    preempt: bool
    state: FHRPState
    track_interface: str
    track_decrement: int = 20

class Router:
    def __init__(self, hostname: str, loopback: str):
        self.hostname = hostname
        self.loopback = ipaddress.IPv4Address(loopback)
        self.interfaces: Dict[str, Interface] = {}
        self.routing_table: List[StaticRoute] = []
        self.fhrp_instances: Dict[int, FHRPConfig] = {}

    def add_interface(self, name: str, cidr: str) -> None:
        self.interfaces[name] = Interface(name=name, ip_addr=ipaddress.IPv4Interface(cidr))

    def add_static_route(self, prefix_cidr: str, next_hop: str, interface: str, ad: int = 1, metric: int = 0, desc: str = "") -> None:
        route = StaticRoute(
            prefix=ipaddress.IPv4Network(prefix_cidr),
            next_hop=ipaddress.IPv4Address(next_hop),
            interface_name=interface,
            admin_distance=ad,
            metric=metric,
            description=desc
        )
        self.routing_table.append(route)

    def configure_fhrp(self, group_id: int, vip: str, vmac: str, priority: int, preempt: bool, track_iface: str, decrement: int = 20) -> None:
        self.fhrp_instances[group_id] = FHRPConfig(
            group_id=group_id,
            virtual_ip=ipaddress.IPv4Address(vip),
            virtual_mac=vmac,
            priority=priority,
            configured_priority=priority,
            preempt=preempt,
            state=FHRPState.STANDBY,
            track_interface=track_iface,
            track_decrement=decrement
        )

    def evaluate_fhrp_tracking(self, group_id: int) -> None:
        if group_id not in self.fhrp_instances:
            return
        cfg = self.fhrp_instances[group_id]
        tracked = self.interfaces.get(cfg.track_interface)
        if tracked and not tracked.is_up:
            cfg.priority = max(1, cfg.configured_priority - cfg.track_decrement)
        else:
            cfg.priority = cfg.configured_priority

    def lookup_lpm(self, dest_ip: ipaddress.IPv4Address) -> Optional[StaticRoute]:
        """Performs Longest Prefix Match (LPM) with Administrative Distance tie-breaking."""
        candidates = []
        for route in self.routing_table:
            # Check interface status
            iface = self.interfaces.get(route.interface_name)
            if not iface or not iface.is_up:
                continue
            if dest_ip in route.prefix:
                candidates.append(route)

        if not candidates:
            return None

        # Sort criteria: 
        # 1. Prefix length descending (LPM)
        # 2. Administrative Distance ascending (AD lower is better)
        # 3. Metric ascending
        candidates.sort(key=lambda r: (-r.prefix.prefixlen, r.admin_distance, r.metric))
        return candidates[0]

class EnterpriseNetworkLab:
    def __init__(self):
        self.routers: Dict[str, Router] = {}
        self._bootstrap_topology()

    def _bootstrap_topology(self) -> None:
        # Router 1 (Edge Primary Core)
        r1 = Router("R1-EDGE-PRIMARY", "10.255.0.1")
        r1.add_interface("Gi0/0", "192.168.1.2/24")    # LAN Gateway IP
        r1.add_interface("Gi0/1", "198.51.100.2/30")   # WAN Primary (Direct to ISP1)
        r1.add_interface("Gi0/2", "10.0.12.1/30")      # Inter-Core Link to R2
        # Default route via Primary ISP (AD=1)
        r1.add_static_route("0.0.0.0/0", "198.51.100.1", "Gi0/1", ad=1, metric=10, desc="Primary WAN via ISP-1")
        # Floating backup via R2 (AD=10)
        r1.add_static_route("0.0.0.0/0", "10.0.12.2", "Gi0/2", ad=10, metric=50, desc="Inter-core backup default route")
        # FHRP Group 10 (HSRP/VRRP) with tracking Gi0/1
        r1.configure_fhrp(group_id=10, vip="192.168.1.1", vmac="00:00:5E:00:01:0A", priority=110, preempt=True, track_iface="Gi0/1", decrement=30)
        r1.fhrp_instances[10].state = FHRPState.ACTIVE
        self.routers["R1"] = r1

        # Router 2 (Edge Secondary Core)
        r2 = Router("R2-EDGE-SECONDARY", "10.255.0.2")
        r2.add_interface("Gi0/0", "192.168.1.3/24")    # LAN Gateway IP
        r2.add_interface("Gi0/1", "203.0.113.2/30")    # WAN Secondary (Direct to ISP2)
        r2.add_interface("Gi0/2", "10.0.12.2/30")      # Inter-Core Link to R1
        # Default route via Secondary ISP (AD=1)
        r2.add_static_route("0.0.0.0/0", "203.0.113.1", "Gi0/1", ad=1, metric=20, desc="Secondary WAN via ISP-2")
        # Floating backup via R1 (AD=10)
        r2.add_static_route("0.0.0.0/0", "10.0.12.1", "Gi0/2", ad=10, metric=50, desc="Inter-core backup default route")
        # FHRP Group 10 (HSRP/VRRP) with tracking Gi0/1
        r2.configure_fhrp(group_id=10, vip="192.168.1.1", vmac="00:00:5E:00:01:0A", priority=95, preempt=True, track_iface="Gi0/1", decrement=20)
        r2.fhrp_instances[10].state = FHRPState.STANDBY
        self.routers["R2"] = r2

    def sync_fhrp_election(self) -> None:
        """Simulate periodic FHRP advertisement & preemption election."""
        r1_cfg = self.routers["R1"].fhrp_instances[10]
        r2_cfg = self.routers["R2"].fhrp_instances[10]

        self.routers["R1"].evaluate_fhrp_tracking(10)
        self.routers["R2"].evaluate_fhrp_tracking(10)

        r1_alive = self.routers["R1"].interfaces["Gi0/0"].is_up
        r2_alive = self.routers["R2"].interfaces["Gi0/0"].is_up

        if not r1_alive and not r2_alive:
            r1_cfg.state = FHRPState.INITIAL
            r2_cfg.state = FHRPState.INITIAL
            return

        if not r1_alive:
            r1_cfg.state = FHRPState.INITIAL
            r2_cfg.state = FHRPState.ACTIVE
            return

        if not r2_alive:
            r2_cfg.state = FHRPState.INITIAL
            r1_cfg.state = FHRPState.ACTIVE
            return

        # Both LAN interfaces alive: Compare priority
        if r1_cfg.priority > r2_cfg.priority:
            if r1_cfg.preempt or r2_cfg.state != FHRPState.ACTIVE:
                r1_cfg.state = FHRPState.ACTIVE
                r2_cfg.state = FHRPState.STANDBY
        elif r2_cfg.priority > r1_cfg.priority:
            if r2_cfg.preempt or r1_cfg.state != FHRPState.ACTIVE:
                r2_cfg.state = FHRPState.ACTIVE
                r1_cfg.state = FHRPState.STANDBY
        else:
            # IP tie breaker (R2 .3 > R1 .2)
            if r2_cfg.preempt:
                r2_cfg.state = FHRPState.ACTIVE
                r1_cfg.state = FHRPState.STANDBY

    def display_topology(self) -> None:
        banner("NETWORK TOPOLOGY & INTERFACE STATUS")
        for key in ["R1", "R2"]:
            r = self.routers[key]
            print(f"{Color.BOLD}Node: {r.hostname} (Loopback: {r.loopback}){Color.RESET}")
            print(f"{'Interface':<12} {'IP Address/Subnet':<22} {'Status':<10} {'Speed':<10}")
            print("-" * 56)
            for name, iface in r.interfaces.items():
                status_color = Color.GREEN if iface.is_up else Color.RED
                status_str = f"{status_color}{'UP' if iface.is_up else 'DOWN'}{Color.RESET}"
                print(f"{name:<12} {str(iface.ip_addr):<22} {status_str:<19} {iface.speed_mbps} Mbps")
            print()

    def display_fhrp_status(self) -> None:
        self.sync_fhrp_election()
        banner("FHRP (HSRP / VRRP) CLUSTER STATUS - GROUP 10")
        print(f"{'Node':<16} {'Role':<12} {'Virtual IP':<16} {'Virtual MAC':<20} {'Priority (Cfg/Eff)':<20} {'Preempt':<8} {'Tracked Uplink'}")
        print("-" * 105)
        for key in ["R1", "R2"]:
            r = self.routers[key]
            cfg = r.fhrp_instances[10]
            role_color = Color.GREEN if cfg.state == FHRPState.ACTIVE else (Color.YELLOW if cfg.state == FHRPState.STANDBY else Color.RED)
            role_str = f"{role_color}{cfg.state.value}{Color.RESET}"
            prio_str = f"{cfg.configured_priority} / {cfg.priority}"
            track_status = "UP" if r.interfaces[cfg.track_interface].is_up else "DOWN (-{})".format(cfg.track_decrement)
            print(f"{r.hostname:<16} {role_str:<21} {str(cfg.virtual_ip):<16} {cfg.virtual_mac:<20} {prio_str:<20} {str(cfg.preempt):<8} {cfg.track_interface} [{track_status}]")
        print()

    def display_routing_table(self) -> None:
        banner("L3 FORWARDING INFORMATION BASE (FIB) / STATIC ROUTES")
        for key in ["R1", "R2"]:
            r = self.routers[key]
            print(f"{Color.BOLD}Routing Table for {r.hostname}:{Color.RESET}")
            print(f"{'Prefix':<18} {'Next Hop':<16} {'Interface':<12} {'AD/Metric':<12} {'Active?':<10} {'Description'}")
            print("-" * 88)
            for rt in r.routing_table:
                iface = r.interfaces.get(rt.interface_name)
                is_active = iface.is_up if iface else False
                active_str = f"{Color.GREEN}ACTIVE{Color.RESET}" if is_active else f"{Color.RED}INACTIVE{Color.RESET}"
                ad_metric = f"[{rt.admin_distance}/{rt.metric}]"
                print(f"{str(rt.prefix):<18} {str(rt.next_hop):<16} {rt.interface_name:<12} {ad_metric:<12} {active_str:<19} {rt.description}")
            print()

    def simulate_packet_trace(self, destination: str) -> None:
        self.sync_fhrp_election()
        banner(f"TRACEROUTE SIMULATION: CLIENT (192.168.1.100) -> {destination}")
        dest_ip = ipaddress.IPv4Address(destination)
        
        # Step 1: Client sends to Gateway (Virtual IP 192.168.1.1)
        active_gw = None
        for key in ["R1", "R2"]:
            if self.routers[key].fhrp_instances[10].state == FHRPState.ACTIVE:
                active_gw = self.routers[key]
                break

        print(f"{Color.CYAN}[Client: 192.168.1.100]{Color.RESET}")
        print(f"  |--> Resolving ARP for Default Gateway VIP 192.168.1.1...")
        time.sleep(0.3)

        if not active_gw:
            alert("DROP: No active FHRP gateway responding to ARP! Gateway Unreachable.")
            return

        vip_cfg = active_gw.fhrp_instances[10]
        print(f"  |--> [ARP Reply] 192.168.1.1 is at {vip_cfg.virtual_mac} (Handled by {Color.BOLD}{active_gw.hostname}{Color.RESET})")
        print(f"  |--> Packet forwarded to Ingress Interface Gi0/0 ({active_gw.interfaces['Gi0/0'].ip_addr.ip})")
        time.sleep(0.3)

        # Step 2: Ingress Router Routing Table Lookup
        route = active_gw.lookup_lpm(dest_ip)
        if not route:
            alert(f"DROP: {active_gw.hostname} has no valid route to destination {destination} (LPM lookup failed)!")
            return

        print(f"  |--> {active_gw.hostname} FIB Lookup: Matched Route {Color.BOLD}{route.prefix}{Color.RESET}")
        print(f"       AD: {route.admin_distance}, Metric: {route.metric}, Next-Hop: {route.next_hop}, Out-Interface: {route.interface_name}")
        time.sleep(0.3)

        # Step 3: Handle Inter-Core Transit if route points to peer router
        if route.interface_name == "Gi0/2":
            peer_key = "R2" if active_gw == self.routers["R1"] else "R1"
            peer = self.routers[peer_key]
            print(f"  |--> Transit hop via Inter-Core Trunk Gi0/2 to {peer.hostname} ({route.next_hop})...")
            peer_route = peer.lookup_lpm(dest_ip)
            if not peer_route:
                alert(f"DROP: {peer.hostname} received packet but failed secondary route lookup!")
                return
            print(f"  |--> {peer.hostname} Egress via {peer_route.interface_name} to ISP Gateway {peer_route.next_hop} ({peer_route.description})")
            success(f"SUCCESS: Packet successfully routed to WAN via {peer.hostname} [{peer_route.interface_name}]")
        else:
            success(f"SUCCESS: Packet forwarded to WAN directly via {active_gw.hostname} [{route.interface_name} -> {route.next_hop}]")

    def toggle_interface(self, router_name: str, iface_name: str, state: bool) -> None:
        if router_name not in self.routers:
            alert(f"Router {router_name} not found.")
            return
        r = self.routers[router_name]
        if iface_name not in r.interfaces:
            alert(f"Interface {iface_name} not found on {router_name}.")
            return
        r.interfaces[iface_name].is_up = state
        state_label = "UP" if state else "DOWN"
        warn(f"EVENT: Interface {router_name} {iface_name} changed state to {state_label}")
        self.sync_fhrp_election()

    def run_automated_chaos_test(self) -> None:
        banner("STARTING AUTOMATED PRODUCTION RESILIENCY & FAILOVER TEST")
        info("Initial State: Baseline operational validation")
        self.display_fhrp_status()
        self.simulate_packet_trace("8.8.8.8")
        time.sleep(1.0)

        banner("CHAOS EVENT 1: Primary WAN Link Failure on R1 (Gi0/1 DOWN)")
        self.toggle_interface("R1", "Gi0/1", False)
        info("Evaluating Tracked Interface & FHRP Priority recalculation...")
        self.display_fhrp_status()
        self.display_routing_table()
        info("Verifying failover path via floating static route / active secondary gateway...")
        self.simulate_packet_trace("8.8.8.8")
        time.sleep(1.0)

        banner("CHAOS EVENT 2: Complete Primary Node Disruption (R1 LAN Gi0/0 DOWN)")
        self.toggle_interface("R1", "Gi0/0", False)
        self.display_fhrp_status()
        self.simulate_packet_trace("8.8.8.8")
        time.sleep(1.0)

        banner("RECOVERY EVENT: Restoring R1 Interfaces (Preemption & Primary Route Convergence)")
        self.toggle_interface("R1", "Gi0/0", True)
        self.toggle_interface("R1", "Gi0/1", True)
        self.display_fhrp_status()
        self.simulate_packet_trace("8.8.8.8")
        success("Test complete: All convergence states verified successfully.")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main_cli():
    lab = EnterpriseNetworkLab()
    while True:
        print(f"\n{Color.BOLD}{Color.WHITE}================================================================{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN}  ADVANCED LAYER 3 ROUTING & FHRP HIGH-AVAILABILITY LAB (M02)  {Color.RESET}")
        print(f"{Color.BOLD}{Color.WHITE}================================================================{Color.RESET}")
        print(f" [1] View Network Topology & Interface Matrix")
        print(f" [2] Inspect Routing Tables (FIB / Floating Static Routes)")
        print(f" [3] View FHRP (HSRP/VRRP) State & Virtual Gateway Tracking")
        print(f" [4] Simulate L3 Traffic Flow (Traceroute client to WAN 8.8.8.8)")
        print(f" [5] Inject WAN Link Failure (Down R1 Gi0/1 - Primary ISP)")
        print(f" [6] Inject Core Node LAN Failure (Down R1 Gi0/0)")
        print(f" [7] Restore All Interfaces (Simulate Full Recovery & Preempt)")
        print(f" [8] Run Automated Chaos Engineering & Resiliency Test Suite")
        print(f" [0] Exit Simulator")
        print(f"{Color.BOLD}----------------------------------------------------------------{Color.RESET}")
        
        try:
            choice = input(f"{Color.YELLOW}Select an option [0-8]: {Color.RESET}").strip()
            if choice == "1":
                lab.display_topology()
            elif choice == "2":
                lab.display_routing_table()
            elif choice == "3":
                lab.display_fhrp_status()
            elif choice == "4":
                dest = input("Enter destination IPv4 [default: 8.8.8.8]: ").strip() or "8.8.8.8"
                lab.simulate_packet_trace(dest)
            elif choice == "5":
                lab.toggle_interface("R1", "Gi0/1", False)
            elif choice == "6":
                lab.toggle_interface("R1", "Gi0/0", False)
            elif choice == "7":
                lab.toggle_interface("R1", "Gi0/0", True)
                lab.toggle_interface("R1", "Gi0/1", True)
                lab.toggle_interface("R2", "Gi0/0", True)
                lab.toggle_interface("R2", "Gi0/1", True)
                success("All router interfaces restored to UP state.")
            elif choice == "8":
                lab.run_automated_chaos_test()
            elif choice == "0":
                print(f"\n{Color.GREEN}Terminating simulator session. Keep routing resilient!{Color.RESET}\n")
                sys.exit(0)
            else:
                warn("Invalid selection. Please choose options 0-8.")
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Color.YELLOW}Session interrupted by user. Exiting.{Color.RESET}")
            sys.exit(0)

if __name__ == "__main__":
    # If run in non-interactive environment (e.g. CI or automated runner), run automated test
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        lab = EnterpriseNetworkLab()
        lab.run_automated_chaos_test()
    else:
        main_cli()
