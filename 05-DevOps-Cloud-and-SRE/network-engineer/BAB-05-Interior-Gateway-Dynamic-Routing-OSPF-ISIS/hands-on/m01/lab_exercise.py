#!/usr/bin/env python3
"""
Lab Exercise: Interior Gateway Dynamic Routing (OSPF & IS-IS Core Concepts)
BAB-05: Network Engineer Foundation Lab

Simulasi interaktif Link-State Routing Protocol:
- Pembentukan OSPF Adjacency & State Machine (Down -> 2-Way -> ExStart -> Full)
- Komputasi Jalur Terpendek Dijkstra (Shortest Path First - SPF)
- Flooding Link State Advertisements (LSA Type 1 & 2)
- Konvergensi Dinamis saat Link Failure & Cost Metric Update
"""

import sys
import time
import heapq
from typing import Dict, List, Tuple, Set, Optional

# ANSI Color Escape Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_BLUE = "\033[44m"


class Link:
    def __init__(self, neighbor_id: str, cost: int, subnet: str, status: str = "UP"):
        self.neighbor_id = neighbor_id
        self.cost = cost
        self.subnet = subnet
        self.status = status


class Router:
    def __init__(self, router_id: str, name: str, area: int = 0, priority: int = 1):
        self.router_id = router_id
        self.name = name
        self.area = area
        self.priority = priority
        self.links: Dict[str, Link] = {}
        self.lsdb: Dict[str, Dict[str, int]] = {}
        self.neighbor_states: Dict[str, str] = {}
        self.routing_table: Dict[str, Tuple[int, str, str]] = {}  # dest: (cost, next_hop, outgoing_if)

    def add_link(self, neighbor_id: str, cost: int, subnet: str):
        self.links[neighbor_id] = Link(neighbor_id, cost, subnet)
        self.neighbor_states[neighbor_id] = "DOWN"

    def form_adjacency(self, neighbor_id: str, delay: float = 0.05):
        states = ["DOWN", "INIT", "2-WAY", "EXSTART", "EXCHANGE", "LOADING", "FULL"]
        print(f"{CLR_CYAN}[OSPF NEIGHBOR]{CLR_RESET} Initializing handshake: {CLR_BOLD}{self.name} <---> {neighbor_id}{CLR_RESET}")
        for s in states:
            self.neighbor_states[neighbor_id] = s
            color = CLR_YELLOW if s != "FULL" else CLR_GREEN
            print(f"  --> State: {color}{s:<8}{CLR_RESET} (Router-ID: {self.router_id}, Neighbor: {neighbor_id})")
            if delay > 0:
                time.sleep(delay)
        print(f"{CLR_GREEN}[ADJACENCY UP]{CLR_RESET} Adjacency FULL tercapai antara {self.name} dan {neighbor_id}!\n")


class OSPFNetworkSimulator:
    def __init__(self):
        self.routers: Dict[str, Router] = {}
        self._init_topology()

    def _init_topology(self):
        # Inisialisasi 4 Router dalam OSPF Area 0
        r1 = Router("1.1.1.1", "R1-Core-JKT", area=0, priority=100)
        r2 = Router("2.2.2.2", "R2-Agg-SBY", area=0, priority=50)
        r3 = Router("3.3.3.3", "R3-Agg-BDG", area=0, priority=50)
        r4 = Router("4.4.4.4", "R4-Edge-DPS", area=0, priority=10)

        self.routers = {
            "R1": r1,
            "R2": r2,
            "R3": r3,
            "R4": r4
        }

        # Interkoneksi Link dengan OSPF Cost (Ref Bandwidth 100Gbps)
        # R1 <-> R2 (10Gbps Link -> Cost 10)
        r1.add_link("R2", 10, "10.0.12.0/30")
        r2.add_link("R1", 10, "10.0.12.0/30")

        # R1 <-> R3 (1Gbps Link -> Cost 100)
        r1.add_link("R3", 100, "10.0.13.0/30")
        r3.add_link("R1", 100, "10.0.13.0/30")

        # R2 <-> R4 (10Gbps Link -> Cost 10)
        r2.add_link("R4", 10, "10.0.24.0/30")
        r4.add_link("R2", 10, "10.0.24.0/30")

        # R3 <-> R4 (10Gbps Link -> Cost 10)
        r3.add_link("R4", 10, "10.0.34.0/30")
        r4.add_link("R3", 10, "10.0.34.0/30")

        # R2 <-> R3 (10Gbps Link -> Cost 15)
        r2.add_link("R3", 15, "10.0.23.0/30")
        r3.add_link("R2", 15, "10.0.23.0/30")

    def display_topology(self):
        print(f"\n{CLR_BG_BLUE}{CLR_WHITE}{CLR_BOLD} === TOPOLOGI LAB OSPF AREA 0 === {CLR_RESET}")
        print(f"{CLR_BOLD}{'Router':<12} {'Router-ID':<12} {'Neighbor':<12} {'Cost Metric':<12} {'Subnet':<16} {'Status'}{CLR_RESET}")
        print("-" * 72)
        for r_name, router in self.routers.items():
            for n_name, link in router.links.items():
                st_color = CLR_GREEN if link.status == "UP" else CLR_RED
                print(f"{r_name:<12} {router.router_id:<12} {n_name:<12} {link.cost:<12} {link.subnet:<16} {st_color}{link.status}{CLR_RESET}")
        print("-" * 72)

    def run_all_adjacencies(self, delay: float = 0.02):
        print(f"\n{CLR_MAGENTA}{CLR_BOLD}=== SIMULASI OSPF FINITE STATE MACHINE (FSM) ==={CLR_RESET}")
        processed = set()
        for r_name, router in self.routers.items():
            for n_name in router.links:
                pair = tuple(sorted([r_name, n_name]))
                if pair not in processed:
                    router.form_adjacency(n_name, delay=delay)
                    self.routers[n_name].neighbor_states[r_name] = "FULL"
                    processed.add(pair)

    def compute_spf_dijkstra(self, source: str) -> Dict[str, Tuple[int, List[str]]]:
        """
        Algoritma Dijkstra Shortest Path First (SPF) untuk Link-State Protocol
        Returns: {destination: (total_cost, [path_nodes])}
        """
        if source not in self.routers:
            print(f"{CLR_RED}Error: Router {source} tidak ditemukan!{CLR_RESET}")
            return {}

        distances: Dict[str, int] = {r: float("inf") for r in self.routers}
        paths: Dict[str, List[str]] = {r: [] for r in self.routers}
        distances[source] = 0
        paths[source] = [source]

        pq: List[Tuple[int, str]] = [(0, source)]
        visited: Set[str] = set()

        print(f"\n{CLR_CYAN}{CLR_BOLD}[SPF CALCULATION]{CLR_RESET} Menjalankan Dijkstra SPF dari Root Node: {CLR_BOLD}{source}{CLR_RESET}")

        step = 1
        while pq:
            curr_dist, curr_node = heapq.heappop(pq)

            if curr_node in visited:
                continue
            visited.add(curr_node)

            print(f"  Langkah {step}: Mengevaluasi node {CLR_BOLD}{curr_node}{CLR_RESET} (Akumulasi Cost: {curr_dist})")
            step += 1

            for neighbor, link in self.routers[curr_node].links.items():
                if link.status != "UP":
                    continue
                new_cost = curr_dist + link.cost
                if new_cost < distances[neighbor]:
                    distances[neighbor] = new_cost
                    paths[neighbor] = paths[curr_node] + [neighbor]
                    heapq.heappush(pq, (new_cost, neighbor))
                    print(f"    -> Relax edge ({curr_node} -> {neighbor}): New lowest cost = {CLR_GREEN}{new_cost}{CLR_RESET}")

        return {r: (distances[r], paths[r]) for r in self.routers}

    def update_routing_table(self, source: str):
        spf_result = self.compute_spf_dijkstra(source)
        r = self.routers[source]
        r.routing_table.clear()

        for dest, (cost, path) in spf_result.items():
            if dest == source or cost == float("inf"):
                continue
            next_hop = path[1] if len(path) > 1 else dest
            link = r.links.get(next_hop)
            out_if = f"Gi0/{next_hop}"
            r.routing_table[dest] = (cost, next_hop, out_if)

        print(f"\n{CLR_GREEN}{CLR_BOLD}=== ROUTING TABLE (RIB) HASIL SPF UNTUK {source} ==={CLR_RESET}")
        print(f"{CLR_BOLD}{'Destination':<14} {'Protocol':<10} {'Metric (Cost)':<16} {'Next-Hop':<12} {'Path'}{CLR_RESET}")
        print("-" * 65)
        for dest, (cost, next_hop, _) in r.routing_table.items():
            path_str = " -> ".join(spf_result[dest][1])
            print(f"{dest:<14} {'OSPF (O)':<10} {cost:<16} {next_hop:<12} {CLR_CYAN}{path_str}{CLR_RESET}")
        print("-" * 65)

    def trigger_link_failure(self, r1_name: str, r2_name: str):
        print(f"\n{CLR_RED}{CLR_BOLD}[EVENT - LINK FAILURE]{CLR_RESET} Memutus link antara {r1_name} dan {r2_name}...")
        if r2_name in self.routers[r1_name].links:
            self.routers[r1_name].links[r2_name].status = "DOWN"
        if r1_name in self.routers[r2_name].links:
            self.routers[r2_name].links[r1_name].status = "DOWN"

        print(f"{CLR_YELLOW}[LSA FLOODING]{CLR_RESET} Mengirimkan LSA Type 1 Update ke seluruh area...")
        time.sleep(0.05)
        print(f"{CLR_GREEN}[SPF TRIGGER]{CLR_RESET} Menjalankan rekalkulasi SPF pasca kegagalan link!\n")
        self.update_routing_table("R1")

    def restore_link(self, r1_name: str, r2_name: str):
        print(f"\n{CLR_GREEN}{CLR_BOLD}[EVENT - LINK RESTORE]{CLR_RESET} Mengembalikan link antara {r1_name} dan {r2_name} ke UP...")
        if r2_name in self.routers[r1_name].links:
            self.routers[r1_name].links[r2_name].status = "UP"
        if r1_name in self.routers[r2_name].links:
            self.routers[r2_name].links[r1_name].status = "UP"
        self.update_routing_table("R1")


def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}======================================================================
  NETWORK ENGINEER SIMULATOR: BAB-05 INTERIOR GATEWAY (OSPF & IS-IS)
  Hands-on Lab Exercise: Link-State Routing & SPF Convergence
======================================================================{CLR_RESET}
    """
    print(banner)


def run_interactive():
    sim = OSPFNetworkSimulator()
    print_banner()

    # Otomatis inisialisasi state awal
    sim.display_topology()
    sim.run_all_adjacencies(delay=0.01)
    sim.update_routing_table("R1")

    # Jika non-interactive shell (piped / CI test)
    if not sys.stdin.isatty():
        print(f"{CLR_YELLOW}[NON-INTERACTIVE]{CLR_RESET} Menjalankan skenario uji otomatis...")
        sim.trigger_link_failure("R1", "R2")
        sim.restore_link("R1", "R2")
        print(f"{CLR_GREEN}[SUKSES]{CLR_RESET} Skenario otomatis selesai.")
        return

    while True:
        print(f"\n{CLR_BOLD}Menu Pilihan Lab:{CLR_RESET}")
        print("  1. Tampilkan Topologi & Status Link Saat Ini")
        print("  2. Hitung Ulang SPF Dijkstra dari Router R1")
        print("  3. Simulasi Link Failure (R1 <-> R2 Down)")
        print("  4. Simulasi Pemulihan Link (R1 <-> R2 Up)")
        print("  5. Hitung SPF dari Router Lain (R2/R3/R4)")
        print("  6. Keluar dari Lab")

        try:
            choice = input(f"{CLR_CYAN}Pilih opsi (1-6): {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            sim.display_topology()
        elif choice == "2":
            sim.update_routing_table("R1")
        elif choice == "3":
            sim.trigger_link_failure("R1", "R2")
        elif choice == "4":
            sim.restore_link("R1", "R2")
        elif choice == "5":
            r_target = input("Masukkan nama router root (R1/R2/R3/R4): ").strip().upper()
            if r_target in sim.routers:
                sim.update_routing_table(r_target)
            else:
                print(f"{CLR_RED}Nama router tidak valid!{CLR_RESET}")
        elif choice == "6":
            print(f"{CLR_GREEN}Lab selesai. Selamat belajar!{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid, silakan coba lagi.{CLR_RESET}")


if __name__ == "__main__":
    run_interactive()
