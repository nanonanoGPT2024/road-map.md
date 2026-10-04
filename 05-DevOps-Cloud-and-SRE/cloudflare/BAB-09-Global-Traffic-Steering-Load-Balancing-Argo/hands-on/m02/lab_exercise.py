#!/usr/bin/env python3
"""
Lab Exercise: Cloudflare Global Traffic Steering, Load Balancing & Argo Smart Routing
BAB-09: Global Traffic Steering, Load Balancing, and Argo Simulation
Production Architecture Simulation - Interactive Terminal Environment
"""

import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# --- ANSI Terminal Color Palette ---
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
    BG_DARK = "\033[40m"
    ORANGE = "\033[38;5;208m"

class PoolStatus(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "CRITICAL"

class SteeringMode(Enum):
    GEO = "Geo-Steering"
    DYNAMIC_LATENCY = "Dynamic Latency Steering"
    FAILOVER = "Strict Failover (Priority)"
    PROXIMITY = "GPS Proximity Steering"

@dataclass
class OriginServer:
    server_id: str
    ip_address: str
    region: str
    weight: int = 1
    latency_ms: float = 25.0
    packet_loss_pct: float = 0.0
    active_connections: int = 0
    is_up: bool = True

@dataclass
class OriginPool:
    pool_id: str
    name: str
    region: str
    origins: List[OriginServer]
    minimum_origins: int = 1
    health_threshold: float = 0.5
    status: PoolStatus = PoolStatus.HEALTHY

    def get_healthy_origins(self) -> List[OriginServer]:
        return [o for o in self.origins if o.is_up and o.packet_loss_pct < 50.0]

    def update_health(self):
        healthy_count = len(self.get_healthy_origins())
        total = len(self.origins)
        ratio = healthy_count / total if total > 0 else 0.0

        if healthy_count >= self.minimum_origins and ratio >= 0.75:
            self.status = PoolStatus.HEALTHY
        elif healthy_count >= self.minimum_origins and ratio >= self.health_threshold:
            self.status = PoolStatus.DEGRADED
        else:
            self.status = PoolStatus.UNHEALTHY

@dataclass
class ArgoRouteMetrics:
    standard_bgp_latency: float
    argo_latency: float
    standard_packet_loss: float
    argo_packet_loss: float
    tiered_cache_hit: bool
    hop_reduction_pct: float

class CloudflareLoadBalancerSimulator:
    def __init__(self):
        self.steering_mode: SteeringMode = SteeringMode.GEO
        self.argo_enabled: bool = True
        self.session_affinity: bool = True
        self.affinity_sessions: Dict[str, str] = {}
        self.pools: Dict[str, OriginPool] = {}
        self._init_infrastructure()

    def _init_infrastructure(self):
        # Pool 1: APAC (Singapore / Tokyo)
        pool_apac = OriginPool(
            pool_id="pool-apac-prod",
            name="APAC Enterprise Origin",
            region="APAC",
            origins=[
                OriginServer("sin-01", "104.28.10.11", "Singapore (SIN)", weight=2, latency_ms=18.5),
                OriginServer("nrt-01", "104.28.10.12", "Tokyo (NRT)", weight=1, latency_ms=45.2),
            ],
            minimum_origins=1
        )

        # Pool 2: EU (Frankfurt / London)
        pool_eu = OriginPool(
            pool_id="pool-eu-prod",
            name="EMEA Core Origin",
            region="EMEA",
            origins=[
                OriginServer("fra-01", "104.28.20.11", "Frankfurt (FRA)", weight=2, latency_ms=22.4),
                OriginServer("lhr-01", "104.28.20.12", "London (LHR)", weight=1, latency_ms=28.1),
            ],
            minimum_origins=1
        )

        # Pool 3: North America (Ashburn / San Jose)
        pool_us = OriginPool(
            pool_id="pool-na-prod",
            name="US Backbone Origin",
            region="NAMER",
            origins=[
                OriginServer("iad-01", "104.28.30.11", "Ashburn (IAD)", weight=2, latency_ms=15.0),
                OriginServer("sjc-01", "104.28.30.12", "San Jose (SJC)", weight=2, latency_ms=38.6),
            ],
            minimum_origins=1
        )

        self.pools = {
            "APAC": pool_apac,
            "EMEA": pool_eu,
            "NAMER": pool_us
        }

    def print_banner(self):
        print(f"{Color.CYAN}{Color.BOLD}" + "="*78)
        print("  CLOUDFLARE EDGE PLATFORM: TRAFFIC STEERING & ARGO ROUTING LAB")
        print("  Architecture: Anycast Edge -> Load Balancing Pools -> Argo Tiered Backbone")
        print("="*78 + f"{Color.RESET}")

    def show_dashboard(self):
        print(f"\n{Color.WHITE}{Color.BOLD}=== GLOBAL LOAD BALANCER & POOL MONITOR ==={Color.RESET}")
        print(f"Steering Policy : {Color.YELLOW}{self.steering_mode.value}{Color.RESET} | "
              f"Argo Smart Routing: {Color.GREEN if self.argo_enabled else Color.RED}{'ENABLED' if self.argo_enabled else 'DISABLED'}{Color.RESET} | "
              f"Session Affinity: {Color.CYAN}{'ENABLED (Cookie: __cflb)' if self.session_affinity else 'DISABLED'}{Color.RESET}")
        print("-" * 78)

        for region, pool in self.pools.items():
            pool.update_health()
            status_color = Color.GREEN if pool.status == PoolStatus.HEALTHY else (Color.YELLOW if pool.status == PoolStatus.DEGRADED else Color.RED)
            print(f"[{status_color}{pool.status.value:<8}{Color.RESET}] {Color.BOLD}{pool.name}{Color.RESET} (ID: {pool.pool_id}) - Region: {pool.region}")

            for o in pool.origins:
                state_str = f"{Color.GREEN}ACTIVE{Color.RESET}" if o.is_up else f"{Color.RED}DOWN{Color.RESET}"
                loss_str = f"{Color.RED}{o.packet_loss_pct:.1f}%{Color.RESET}" if o.packet_loss_pct > 0 else f"{Color.DIM}0.0%{Color.RESET}"
                print(f"   ↳ [{state_str}] Server {o.server_id:<7} | IP: {o.ip_address:<14} | Loc: {o.region:<16} | Lat: {o.latency_ms:5.1f}ms | Loss: {loss_str} | Conn: {o.active_connections}")
        print("-" * 78)

    def route_request(self, client_ip: str, client_region: str, session_id: Optional[str] = None):
        print(f"\n{Color.CYAN}[Edge Request Dispatch]{Color.RESET} Client IP: {client_ip} | Geo-Region: {Color.BOLD}{client_region}{Color.RESET}")

        # 1. Session Affinity Check
        if self.session_affinity and session_id and session_id in self.affinity_sessions:
            bound_server = self.affinity_sessions[session_id]
            print(f"  {Color.MAGENTA}↳ [Session Affinity Hit]{Color.RESET} Found cookie session '{session_id}' -> Bound to {bound_server}")

        # 2. Select Pool according to Steering Mode
        target_pool = self._select_pool(client_region)
        print(f"  ↳ Selected Origin Pool: {Color.BOLD}{target_pool.name}{Color.RESET} (Status: {target_pool.status.value})")

        healthy_origins = target_pool.get_healthy_origins()
        if not healthy_origins:
            print(f"  {Color.RED}↳ [FAILOVER TRIGGERED]{Color.RESET} Target pool {target_pool.name} has no healthy origins!")
            fallback_pool = self._get_fallback_pool(target_pool.region)
            print(f"  {Color.YELLOW}↳ Diverting traffic to Fallback Pool: {fallback_pool.name}{Color.RESET}")
            target_pool = fallback_pool
            healthy_origins = target_pool.get_healthy_origins()

        if not healthy_origins:
            print(f"  {Color.RED}{Color.BOLD}↳ [530 / 502 Edge Error] Direct Origin Unreachable. All pools exhausted!{Color.RESET}")
            return

        # Weighted Round Robin Selection
        selected_origin = random.choices(healthy_origins, weights=[o.weight for o in healthy_origins], k=1)[0]
        selected_origin.active_connections += 1

        if self.session_affinity and session_id:
            self.affinity_sessions[session_id] = selected_origin.server_id

        # 3. Argo Smart Routing Simulation
        metrics = self._calculate_argo_metrics(client_region, selected_origin)

        print(f"  {Color.GREEN}✔ Dispatched to Origin:{Color.RESET} {selected_origin.server_id} ({selected_origin.region}) [{selected_origin.ip_address}]")
        self._print_latency_comparison(metrics)

    def _select_pool(self, client_region: str) -> OriginPool:
        if self.steering_mode == SteeringMode.GEO:
            return self.pools.get(client_region, self.pools["NAMER"])
        elif self.steering_mode == SteeringMode.DYNAMIC_LATENCY:
            best_pool = min(
                self.pools.values(),
                key=lambda p: min([o.latency_ms for o in p.origins if o.is_up] or [9999])
            )
            return best_pool
        elif self.steering_mode == SteeringMode.FAILOVER:
            # Priority order: NAMER -> EMEA -> APAC
            for key in ["NAMER", "EMEA", "APAC"]:
                p = self.pools[key]
                if len(p.get_healthy_origins()) >= p.minimum_origins:
                    return p
            return self.pools["NAMER"]
        else:
            return self.pools.get(client_region, self.pools["NAMER"])

    def _get_fallback_pool(self, failed_region: str) -> OriginPool:
        # Fallback hierarchy
        fallback_map = {
            "APAC": self.pools["NAMER"],
            "EMEA": self.pools["NAMER"],
            "NAMER": self.pools["EMEA"]
        }
        return fallback_map.get(failed_region, self.pools["NAMER"])

    def _calculate_argo_metrics(self, client_region: str, origin: OriginServer) -> ArgoRouteMetrics:
        base_latency = origin.latency_ms
        if client_region != origin.region:
            cross_continent_penalty = 120.0
            base_latency += cross_continent_penalty

        std_loss = origin.packet_loss_pct + (random.uniform(1.5, 4.0) if not self.argo_enabled else 0.0)

        if self.argo_enabled:
            # Argo avoids congested public transit nodes by 33% latency reduction on avg
            optimized_latency = base_latency * random.uniform(0.60, 0.72)
            argo_loss = 0.0
            hop_reduction = random.uniform(28.0, 45.0)
            tiered_hit = random.choice([True, False, True])
        else:
            optimized_latency = base_latency
            argo_loss = std_loss
            hop_reduction = 0.0
            tiered_hit = False

        return ArgoRouteMetrics(
            standard_bgp_latency=base_latency,
            argo_latency=optimized_latency,
            standard_packet_loss=std_loss,
            argo_packet_loss=argo_loss,
            tiered_cache_hit=tiered_hit,
            hop_reduction_pct=hop_reduction
        )

    def _print_latency_comparison(self, m: ArgoRouteMetrics):
        if self.argo_enabled:
            diff_ms = m.standard_bgp_latency - m.argo_latency
            gain_pct = (diff_ms / m.standard_bgp_latency) * 100
            print(f"    {Color.CYAN}┌─ Argo Smart Routing Optimization Report ─────────────┐{Color.RESET}")
            print(f"    │ Public BGP Transit Latency : {Color.RED}{m.standard_bgp_latency:6.1f} ms{Color.RESET} (Loss: {m.standard_packet_loss:.1f}%)    │")
            print(f"    │ Cloudflare Argo Backbone   : {Color.GREEN}{m.argo_latency:6.1f} ms{Color.RESET} (Loss: {m.argo_packet_loss:.1f}%)    │")
            print(f"    │ Latency Improvement        : {Color.GREEN}{Color.BOLD}-{diff_ms:5.1f} ms ({gain_pct:.1f}% faster){Color.RESET}     │")
            print(f"    │ Network Hops Bypassed      : {m.hop_reduction_pct:.1f}% public routing hops   │")
            print(f"    │ Tiered Cache Upper Tier    : {Color.GREEN+'HIT (Edge warm)' if m.tiered_cache_hit else Color.DIM+'MISS (Origin fetch)'}{Color.RESET}      │")
            print(f"    {Color.CYAN}└────────────────────────────────────────────────────────┘{Color.RESET}")
        else:
            print(f"    Transit Latency (Standard BGP): {m.standard_bgp_latency:.1f} ms | Packet Loss: {m.standard_packet_loss:.1f}%")

    def toggle_server_health(self, pool_key: str, server_id: str, is_up: bool, packet_loss: float = 0.0):
        if pool_key in self.pools:
            for s in self.pools[pool_key].origins:
                if s.server_id == server_id:
                    s.is_up = is_up
                    s.packet_loss_pct = packet_loss
                    self.pools[pool_key].update_health()
                    status_lbl = f"{Color.GREEN}UP{Color.RESET}" if is_up else f"{Color.RED}DOWN{Color.RESET}"
                    print(f"\n{Color.YELLOW}[Health Check Event]{Color.RESET} Origin {server_id} in {pool_key} set to {status_lbl} (Loss: {packet_loss}%)")
                    return
        print(f"{Color.RED}Origin server '{server_id}' not found in pool '{pool_key}'!{Color.RESET}")

    def run_automated_stress_benchmark(self):
        print(f"\n{Color.WHITE}{Color.BOLD}>>> RUNNING ARGO & GLOBAL LOAD BALANCING STRESS MATRIX <<<{Color.RESET}")
        clients = [
            ("203.0.113.45", "APAC", "sess-tokyo-01"),
            ("198.51.100.12", "EMEA", "sess-berlin-02"),
            ("192.0.2.89", "NAMER", "sess-ny-03"),
            ("185.220.101.5", "EMEA", "sess-london-04"),
            ("103.21.244.1", "APAC", "sess-singapore-05")
        ]

        print(f"{Color.DIM}Simulating 5 distributed client requests through edge nodes...{Color.RESET}")
        for ip, region, sess in clients:
            time.sleep(0.3)
            self.route_request(ip, region, sess)

        print(f"\n{Color.YELLOW}Simulating Outage: Taking down primary APAC node (sin-01)...{Color.RESET}")
        self.toggle_server_health("APAC", "sin-01", is_up=False, packet_loss=100.0)
        self.show_dashboard()

        print(f"{Color.DIM}Retrying APAC request under degraded pool conditions...{Color.RESET}")
        time.sleep(0.3)
        self.route_request("203.0.113.45", "APAC", "sess-tokyo-01")

def interactive_loop():
    lb = CloudflareLoadBalancerSimulator()
    lb.print_banner()

    menu = f"""
{Color.BOLD}INTERACTIVE LAB ACTIONS:{Color.RESET}
  1. Show Infrastructure Dashboard & Health Status
  2. Send Client Request (Test Traffic Steering)
  3. Toggle Argo Smart Routing (Currently: {'ON' if lb.argo_enabled else 'OFF'})
  4. Change Steering Policy (Geo / Latency / Failover)
  5. Simulate Origin Failure / Packet Loss Injection
  6. Run Full Traffic Matrix & Stress Test
  7. Reset Infrastructure to Healthy
  0. Exit Lab
"""

    while True:
        print(menu)
        try:
            choice = input(f"{Color.CYAN}cf-edge-cli>{Color.RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting lab.")
            break

        if choice == "1":
            lb.show_dashboard()
        elif choice == "2":
            regions = ["APAC", "EMEA", "NAMER"]
            print(f"Available client regions: {', '.join(regions)}")
            cr = input("Enter client region [default: APAC]: ").strip().upper() or "APAC"
            cip = input("Enter simulated Client IP [default: 198.51.100.77]: ").strip() or "198.51.100.77"
            sess = input("Enter Session Cookie ID (optional): ").strip() or None
            lb.route_request(cip, cr, sess)
        elif choice == "3":
            lb.argo_enabled = not lb.argo_enabled
            state = f"{Color.GREEN}ENABLED{Color.RESET}" if lb.argo_enabled else f"{Color.RED}DISABLED{Color.RESET}"
            print(f"\nArgo Smart Routing is now: {state}")
        elif choice == "4":
            print("\nSelect Steering Mode:")
            print("  1. Geo-Steering (Route by continent/country)")
            print("  2. Dynamic Latency Steering (Fastest origin by RTT)")
            print("  3. Strict Failover (Primary pool with backup order)")
            sm = input("Choose policy (1-3): ").strip()
            if sm == "1":
                lb.steering_mode = SteeringMode.GEO
            elif sm == "2":
                lb.steering_mode = SteeringMode.DYNAMIC_LATENCY
            elif sm == "3":
                lb.steering_mode = SteeringMode.FAILOVER
            print(f"Active Steering Mode updated to: {Color.BOLD}{lb.steering_mode.value}{Color.RESET}")
        elif choice == "5":
            lb.show_dashboard()
            pool_key = input("Enter Pool Key (APAC / EMEA / NAMER): ").strip().upper()
            srv_id = input("Enter Server ID (e.g. sin-01, fra-01, iad-01): ").strip().lower()
            action = input("Set state (1: Healthy, 2: 30% Degraded Loss, 3: Full Outage): ").strip()
            if action == "1":
                lb.toggle_server_health(pool_key, srv_id, is_up=True, packet_loss=0.0)
            elif action == "2":
                lb.toggle_server_health(pool_key, srv_id, is_up=True, packet_loss=30.0)
            elif action == "3":
                lb.toggle_server_health(pool_key, srv_id, is_up=False, packet_loss=100.0)
        elif choice == "6":
            lb.run_automated_stress_benchmark()
        elif choice == "7":
            lb._init_infrastructure()
            print(f"\n{Color.GREEN}All origin servers and routing states have been reset to factory defaults.{Color.RESET}")
            lb.show_dashboard()
        elif choice == "0":
            print(f"\n{Color.GREEN}Exiting Cloudflare Load Balancing & Argo Lab. Terimakasih!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Invalid selection. Choose an option between 0 and 7.{Color.RESET}")

if __name__ == "__main__":
    interactive_loop()
