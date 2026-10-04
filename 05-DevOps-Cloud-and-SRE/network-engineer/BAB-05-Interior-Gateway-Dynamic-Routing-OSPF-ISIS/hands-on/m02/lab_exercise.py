#!/usr/bin/env python3
"""
Lab Exercise: Advanced Link-State Engineering (OSPFv2/v3 & IS-IS)
Simulasi Teknis:
  1. Dijkstra SPF & Loop-Free Alternate (LFA - RFC 5286) Fast Reroute (FRR)
  2. Dynamic Maintenance Mode: OSPF Max-Metric & IS-IS Overload Bit (OL-Bit)
  3. SPF Generation Throttling State Machine (Exponential Backoff)
"""

import sys
import heapq
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set

# ANSI Color Codes for terminal formatting
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


@dataclass(order=True)
class PriorityItem:
    cost: int
    node: str = field(compare=False)


class NetworkTopology:
    def __init__(self):
        # adjacency list: u -> list of (v, metric, interface_name)
        self.adj: Dict[str, List[Tuple[str, int, str]]] = {}
        # router flags: e.g. overload_bit or max_metric
        self.router_flags: Dict[str, Dict[str, bool]] = {}
        self.prefixes: Dict[str, List[str]] = {}

    def add_router(self, router_id: str, prefixes: Optional[List[str]] = None):
        if router_id not in self.adj:
            self.adj[router_id] = []
            self.router_flags[router_id] = {"overload": False, "max_metric": False}
            self.prefixes[router_id] = prefixes or []

    def add_link(self, u: str, v: str, cost: int, if_u: str, if_v: str, bidirectional: bool = True):
        self.add_router(u)
        self.add_router(v)
        self.adj[u].append((v, cost, if_u))
        if bidirectional:
            self.adj[v].append((u, cost, if_v))

    def set_overload_bit(self, router_id: str, active: bool = True):
        """Simulates IS-IS Overload (OL) bit or OSPF Stub Router Advertisement."""
        if router_id in self.router_flags:
            self.router_flags[router_id]["overload"] = active

    def dijkstra(self, source: str) -> Tuple[Dict[str, int], Dict[str, Optional[str]], Dict[str, str]]:
        """
        Calculates Shortest Path Tree from source.
        Returns:
            distances: node -> min_cost
            predecessors: node -> prev_node
            next_hops: node -> immediate outgoing interface & next hop
        """
        dist: Dict[str, int] = {node: float("inf") for node in self.adj} # type: ignore
        prev: Dict[str, Optional[str]] = {node: None for node in self.adj}
        next_hop: Dict[str, str] = {node: "" for node in self.adj}

        dist[source] = 0
        pq: List[PriorityItem] = [PriorityItem(0, source)]

        while pq:
            curr_item = heapq.heappop(pq)
            d, u = curr_item.cost, curr_item.node

            if d > dist[u]:
                continue

            for v, cost, iface in self.adj[u]:
                # If node u has overload/max_metric active and is NOT source, transit cost becomes effectively prohibitive (65535)
                effective_cost = cost
                if u != source and (self.router_flags[u]["overload"] or self.router_flags[u]["max_metric"]):
                    effective_cost = 65535

                new_cost = dist[u] + effective_cost
                if new_cost < dist[v]:
                    dist[v] = new_cost
                    prev[v] = u
                    # Determine next-hop from perspective of source
                    if u == source:
                        next_hop[v] = f"{iface} -> {v}"
                    else:
                        next_hop[v] = next_hop[u]
                    heapq.heappush(pq, PriorityItem(new_cost, v))

        return dist, prev, next_hop

    def compute_all_pairs_distances(self) -> Dict[str, Dict[str, int]]:
        all_dists: Dict[str, Dict[str, int]] = {}
        for node in self.adj:
            dists, _, _ = self.dijkstra(node)
            all_dists[node] = dists
        return all_dists

    def calculate_lfa_frr(self, source: str, destination: str) -> Dict[str, any]:
        """
        Evaluates RFC 5286 Loop-Free Alternate (LFA) conditions for primary next-hop failure:
        Basic Link-Protecting LFA:
            Distance(N, D) < Distance(S, D) + Distance(S, N)
        Downstream Path Condition:
            Distance(N, D) < Distance(S, D)
        """
        all_dists = self.compute_all_pairs_distances()
        d_sd = all_dists[source][destination]
        _, _, primary_next_hops = self.dijkstra(source)
        primary_nh_str = primary_next_hops[destination]

        # Extract primary neighbor
        neighbors = [v for v, _, _ in self.adj[source]]
        primary_neighbor = None
        for n in neighbors:
            if n in primary_nh_str:
                primary_neighbor = n
                break

        candidates = []
        for n in neighbors:
            if n == primary_neighbor:
                continue
            d_sn = all_dists[source][n]
            d_nd = all_dists[n][destination]

            # RFC 5286 Link-Protecting Inequality
            is_lfa = d_nd < (d_sd + d_sn)
            # Downstream path inequality (stricter, guarantees no loop even with uncoordinated failure)
            is_downstream = d_nd < d_sd

            candidates.append({
                "neighbor": n,
                "d_sn": d_sn,
                "d_nd": d_nd,
                "lfa_inequality": f"{d_nd} < {d_sd} + {d_sn} ({d_sd + d_sn})",
                "is_lfa": is_lfa,
                "is_downstream": is_downstream,
                "backup_cost": d_sn + d_nd
            })

        return {
            "source": source,
            "destination": destination,
            "primary_neighbor": primary_neighbor,
            "primary_cost": d_sd,
            "candidates": candidates
        }


class SpfThrottlingEngine:
    """Simulates OSPF/IS-IS Exponential Backoff SPF Throttling."""
    def __init__(self, init_delay_ms: int = 50, hold_time_ms: int = 200, max_wait_ms: int = 5000):
        self.init_delay = init_delay_ms
        self.hold_time = hold_time_ms
        self.max_wait = max_wait_ms
        self.current_hold = hold_time_ms
        self.state = "QUIET" # QUIET, HOLDING, MAX_HOLD
        self.last_event_time = 0.0

    def trigger_topology_change(self, event_name: str) -> Tuple[int, str]:
        """Returns (delay_applied_ms, new_state_summary)"""
        if self.state == "QUIET":
            delay = self.init_delay
            self.state = "HOLDING"
            self.current_hold = self.hold_time
            msg = f"First event [{event_name}]: Schedule SPF immediately with init-delay ({delay}ms). Enter HOLDING."
            return delay, msg
        elif self.state == "HOLDING":
            delay = self.current_hold
            self.current_hold = min(self.current_hold * 2, self.max_wait)
            if self.current_hold >= self.max_wait:
                self.state = "MAX_HOLD"
            msg = f"Subsequent flap [{event_name}]: Throttling applied. Delay {delay}ms, next hold doubled to {self.current_hold}ms."
            return delay, msg
        else: # MAX_HOLD
            delay = self.max_wait
            msg = f"Rapid instability [{event_name}]: Max throttling reached! Clamped to max-wait ({delay}ms)."
            return delay, msg

    def reset_timer(self):
        self.state = "QUIET"
        self.current_hold = self.hold_time


def print_banner():
    banner = f"""
{CYAN}{BOLD}================================================================================
   ENTERPRISE CORE LINK-STATE ROUTING LAB: OSPFv2/v3 & IS-IS ENGINE
   Module 02: Advanced SPF, LFA Fast-Reroute & Maintenance Isolation
================================================================================{RESET}"""
    print(banner)


def display_topology(topo: NetworkTopology):
    print(f"\n{BOLD}{YELLOW}[+] Active Backbone Topology & Link Weights:{RESET}")
    visited = set()
    for u in sorted(topo.adj.keys()):
        for v, cost, iface in topo.adj[u]:
            link_id = tuple(sorted([u, v]))
            if link_id not in visited:
                visited.add(link_id)
                flag_u = f"{RED}[OL/MaxMetric]{RESET}" if topo.router_flags[u]["overload"] else ""
                flag_v = f"{RED}[OL/MaxMetric]{RESET}" if topo.router_flags[v]["overload"] else ""
                print(f"  {CYAN}{u:4s}{RESET} {flag_u} <──({iface}, metric: {cost:2d})──> {CYAN}{v:4s}{RESET} {flag_v}")


def run_routing_table_audit(topo: NetworkTopology, source: str):
    print(f"\n{BOLD}{BLUE}[*] Routing Information Base (RIB) Computed for Root Node: {source}{RESET}")
    print(f"{'Destination':<14} | {'Total Metric':<12} | {'Next-Hop / Egress':<25} | {'Path Detail'}")
    print("-" * 75)

    dist, prev, next_hop = topo.dijkstra(source)
    for target in sorted(topo.adj.keys()):
        if target == source:
            continue
        # reconstruct path
        curr = target
        path = []
        while curr is not None:
            path.append(curr)
            curr = prev[curr]
        path.reverse()
        path_str = " -> ".join(path)

        cost_str = f"{dist[target]}" if dist[target] < 60000 else f"{dist[target]} (TRANSIT BLOCKED)"
        print(f"{target:<14} | {cost_str:<12} | {next_hop[target]:<25} | {path_str}")


def run_lfa_simulation(topo: NetworkTopology, source: str, destination: str):
    print(f"\n{BOLD}{MAGENTA}[*] RFC 5286 Loop-Free Alternate (LFA) Computation ({source} -> {destination}):{RESET}")
    res = topo.calculate_lfa_frr(source, destination)
    print(f"  Primary Shortest Path Next-Hop : {GREEN}{res['primary_neighbor']}{RESET} (End-to-End Cost: {res['primary_cost']})")
    print(f"\n  {'Neighbor':<10} | {'D(N,D)':<8} | {'D(S,D)+D(S,N)':<15} | {'LFA Status':<18} | {'Downstream?'}")
    print("  " + "-" * 70)

    for c in res["candidates"]:
        status = f"{GREEN}PASS (LFA Valid){RESET}" if c["is_lfa"] else f"{RED}FAIL (Loop Risk){RESET}"
        downstream = f"{GREEN}YES{RESET}" if c["is_downstream"] else f"{YELLOW}NO{RESET}"
        print(f"  {c['neighbor']:<10} | {c['d_nd']:<8} | {c['lfa_inequality']:<15} | {status:<27} | {downstream}")


def run_spf_throttling_demo():
    print(f"\n{BOLD}{YELLOW}[*] SPF & LSA Throttling Simulation (Hold-down & Exponential Backoff):{RESET}")
    engine = SpfThrottlingEngine(init_delay_ms=50, hold_time_ms=200, max_wait_ms=5000)

    flaps = [
        "Core Link Gi0/1 Down",
        "Rapid Flap 1 (Link flapping)",
        "Rapid Flap 2 (Unstable optic)",
        "Rapid Flap 3 (BGP peering bounce)",
        "Stabilized Link Up"
    ]

    for i, event in enumerate(flaps, 1):
        delay, log = engine.trigger_topology_change(event)
        color = GREEN if i == 1 else (YELLOW if i < 4 else RED)
        print(f"  Event {i}: {color}{log}{RESET}")


def main():
    print_banner()

    # Step 1: Initialize Backbone Mesh Topology
    # R1 (Ingress Core) - R2 (Spine A) - R3 (Spine B) - R4 (Core Transit) - R5 (Egress Gateway)
    topo = NetworkTopology()
    topo.add_link("R1", "R2", cost=10, if_u="Gi0/1", if_v="Gi0/1")
    topo.add_link("R1", "R3", cost=15, if_u="Gi0/2", if_v="Gi0/1")
    topo.add_link("R2", "R4", cost=10, if_u="Gi0/2", if_v="Gi0/1")
    topo.add_link("R3", "R4", cost=10, if_u="Gi0/2", if_v="Gi0/2")
    topo.add_link("R4", "R5", cost=5,  if_u="Gi0/3", if_v="Gi0/1")
    topo.add_link("R2", "R3", cost=5,  if_u="Gi0/3", if_v="Gi0/3")

    display_topology(topo)

    # Step 2: Normal Baseline SPF & RIB
    print(f"\n{BOLD}{WHITE}--- STAGE 1: Baseline Steady-State Convergence ---{RESET}")
    run_routing_table_audit(topo, source="R1")

    # Step 3: Fast Reroute LFA Evaluation for R1 -> R5
    print(f"\n{BOLD}{WHITE}--- STAGE 2: Pre-computed Loop-Free Alternate (LFA FRR) ---{RESET}")
    run_lfa_simulation(topo, source="R1", destination="R5")

    # Step 4: Maintenance Mode - IS-IS Overload Bit / OSPF Stub Router on R2
    print(f"\n{BOLD}{WHITE}--- STAGE 3: Zero-Downtime Maintenance Drain (Overload Bit on R2) ---{RESET}")
    print(f"{YELLOW}[!] Activating IS-IS Overload Bit (OL-Bit) / OSPF Max-Metric on Router R2...{RESET}")
    topo.set_overload_bit("R2", active=True)
    display_topology(topo)
    run_routing_table_audit(topo, source="R1")

    # Step 5: Throttling State Machine Demonstration
    print(f"\n{BOLD}{WHITE}--- STAGE 4: Micro-Loop Suppression & SPF Throttling Engine ---{RESET}")
    run_spf_throttling_demo()

    print(f"\n{GREEN}{BOLD}[✔] Lab Exercise Simulation Completed Successfully.{RESET}\n")


if __name__ == "__main__":
    main()
