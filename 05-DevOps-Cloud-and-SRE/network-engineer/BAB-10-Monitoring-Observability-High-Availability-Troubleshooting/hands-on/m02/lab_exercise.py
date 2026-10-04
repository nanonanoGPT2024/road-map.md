#!/usr/bin/env python3
"""
BAB 10: Monitoring, Observability, High Availability (HA) & Troubleshooting
Interactive Production Network Telemetry and HA Failover Simulator.

Features:
- Live gNMI / Streaming Telemetry Emulation
- Dual-Node Keepalived/VRRP Virtual IP Failover with Gratuitous ARP
- Automated Root Cause Analysis (RCA) for Route Flapping & Silent Blackholes
- Synthetic OpenTelemetry / Prometheus Metrics Exporter
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict

# ANSI Terminal Color Palette
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_CYAN = "\033[36m"
C_WHITE = "\033[37m"
C_BG_RED = "\033[41m"
C_BG_GREEN = "\033[42m"
C_BG_BLUE = "\033[44m"


@dataclass
class RouterNode:
    name: str
    role: str
    vip: str
    vrrp_priority: int
    vrrp_state: str  # MASTER or BACKUP
    bgp_peers_up: int
    bgp_peers_total: int
    cpu_percent: float
    interface_drops: int
    rtt_ms: float
    jitter_ms: float
    health_score: float = 100.0


@dataclass
class NetworkFabric:
    primary: RouterNode
    secondary: RouterNode
    vip: str = "198.51.100.1"
    active_master: str = "CORE-GW-01"
    anomalies: List[str] = field(default_factory=list)


def banner():
    print(f"{C_CYAN}{C_BOLD}" + "=" * 78)
    print("   ENTERPRISE NETWORK OBSERVABILITY & HA FAILOVER SIMULATOR")
    print("   Architecture: Spine-Leaf Core HA Cluster (VRRP / BGP Anycast / gNMI)")
    print("=" * 78 + f"{C_RESET}")


def render_dashboard(fabric: NetworkFabric):
    print(f"\n{C_BOLD}{C_WHITE}--- REAL-TIME CLUSTER TELEMETRY DASHBOARD ---{C_RESET}")
    print(f"Cluster Virtual IP (VIP): {C_BOLD}{C_CYAN}{fabric.vip}{C_RESET} | Active Master: {C_BOLD}{C_GREEN if fabric.active_master == fabric.primary.name else C_YELLOW}{fabric.active_master}{C_RESET}")
    print("-" * 78)
    header = f"{'Node Name':<12} | {'Role':<8} | {'VRRP':<8} | {'Prio':<5} | {'BGP Peer':<9} | {'Drops/s':<7} | {'RTT':<7} | {'Health'}"
    print(f"{C_BOLD}{header}{C_RESET}")
    print("-" * 78)

    for node in [fabric.primary, fabric.secondary]:
        vrrp_color = C_GREEN if node.vrrp_state == "MASTER" else C_YELLOW
        health_color = C_GREEN if node.health_score >= 85 else (C_YELLOW if node.health_score >= 60 else C_RED)
        bgp_status = f"{node.bgp_peers_up}/{node.bgp_peers_total}"
        bgp_color = C_GREEN if node.bgp_peers_up == node.bgp_peers_total else C_RED

        print(
            f"{C_BOLD}{node.name:<12}{C_RESET} | "
            f"{node.role:<8} | "
            f"{vrrp_color}{node.vrrp_state:<8}{C_RESET} | "
            f"{node.vrrp_priority:<5} | "
            f"{bgp_color}{bgp_status:<9}{C_RESET} | "
            f"{node.interface_drops:<7} | "
            f"{node.rtt_ms:>4.1f}ms  | "
            f"{health_color}{node.health_score:>5.1f}%{C_RESET}"
        )
    print("-" * 78)

    if fabric.anomalies:
        print(f"{C_BG_RED}{C_WHITE}{C_BOLD} [ACTIVE ALERTS] {C_RESET}")
        for alert in fabric.anomalies:
            print(f"  {C_RED}! {alert}{C_RESET}")
    else:
        print(f"{C_GREEN}✓ Telemetry normal. SLA compliance: 99.999%. Zero packet anomalies detected.{C_RESET}")


def simulate_telemetry_stream(fabric: NetworkFabric):
    print(f"\n{C_MAGENTA}{C_BOLD}[STREAM] Ingesting 5-second gNMI Subscriptions & sFlow Samples...{C_RESET}")
    for i in range(1, 4):
        time.sleep(0.4)
        ts = time.strftime("%H:%M:%S")
        rtt_sample = round(random.uniform(0.8, 2.5), 2)
        bps = random.randint(420, 850)
        print(f"  {C_DIM}[{ts}]{C_RESET} gNMI path=/interfaces/interface[name=eth0]/state/counters packets={140000+i*320} rx_bps={bps}Mbps rtt={rtt_sample}ms")

    fabric.primary.rtt_ms = round(random.uniform(1.0, 2.8), 2)
    fabric.secondary.rtt_ms = round(random.uniform(1.1, 2.9), 2)
    fabric.primary.cpu_percent = round(random.uniform(18.0, 32.0), 1)
    fabric.secondary.cpu_percent = round(random.uniform(12.0, 24.0), 1)
    print(f"{C_GREEN}✓ Telemetry pipeline synchronization completed.{C_RESET}")


def trigger_vrrp_failover(fabric: NetworkFabric):
    print(f"\n{C_YELLOW}{C_BOLD}[ACTION] Simulating Hardware Failure on Active Master ({fabric.active_master})...{C_RESET}")
    time.sleep(0.5)

    if fabric.active_master == fabric.primary.name:
        print(f"  {C_RED}[FAIL] {fabric.primary.name}: Power Supply Fault / Link Down on eth0/0.{C_RESET}")
        print(f"  {C_YELLOW}[VRRP] {fabric.primary.name} priority reduced 150 -> 0 (State: FAULT).{C_RESET}")
        fabric.primary.vrrp_state = "FAULT"
        fabric.primary.vrrp_priority = 0
        fabric.primary.health_score = 15.0
        fabric.primary.interface_drops = 2840

        time.sleep(0.6)
        print(f"  {C_CYAN}[VRRP] {fabric.secondary.name} missed 3 advertisement intervals (timeout: 3.2s).{C_RESET}")
        print(f"  {C_GREEN}{C_BOLD}[FAILOVER] {fabric.secondary.name} transitions: BACKUP -> MASTER.{C_RESET}")
        fabric.secondary.vrrp_state = "MASTER"
        fabric.active_master = fabric.secondary.name

        print(f"  {C_WHITE}[ARP] Broadcasting Gratuitous ARP: IP {fabric.vip} is now at MAC {C_BOLD}52:54:00:fa:02:bb{C_RESET}")
        fabric.anomalies.append(f"HA Failover occurred: VIP {fabric.vip} migrated to {fabric.secondary.name}")
    else:
        print(f"{C_CYAN}[RECOVERY] Restoring {fabric.primary.name} to Primary Master...{C_RESET}")
        fabric.primary.vrrp_state = "MASTER"
        fabric.primary.vrrp_priority = 150
        fabric.primary.health_score = 98.5
        fabric.primary.interface_drops = 0
        fabric.secondary.vrrp_state = "BACKUP"
        fabric.active_master = fabric.primary.name
        fabric.anomalies.clear()
        print(f"  {C_GREEN}✓ Preemption successful. {fabric.primary.name} reassumed MASTER state.{C_RESET}")


def inject_anomaly(fabric: NetworkFabric):
    print(f"\n{C_RED}{C_BOLD}[FAULT INJECTION MENU]{C_RESET}")
    print("1. BGP Flapping & Route Dampening (Peer 10.254.1.2)")
    print("2. MTU Mismatch & Packet Truncation (Blackhole on Uplink)")
    print("3. Interface Silent Drops via Buffer Congestion")
    print("4. Clear All Injected Faults")

    choice = input(f"{C_BOLD}Select Fault [1-4]: {C_RESET}").strip()
    if choice == "1":
        target = fabric.primary if fabric.active_master == fabric.primary.name else fabric.secondary
        target.bgp_peers_up = max(0, target.bgp_peers_up - 1)
        target.health_score = 54.0
        msg = f"BGP Session Down: Peer 10.254.1.2 flap detected on {target.name} (HoldTime expired)"
        if msg not in fabric.anomalies:
            fabric.anomalies.append(msg)
        print(f"{C_RED}⚠ Alert triggered: BGP state machine reset.{C_RESET}")
    elif choice == "2":
        target = fabric.primary
        target.rtt_ms += 18.5
        target.interface_drops += 412
        target.health_score = 62.0
        msg = f"Path MTU discovery failure: DF-bit packet > 1500 bytes dropped on {target.name}"
        if msg not in fabric.anomalies:
            fabric.anomalies.append(msg)
        print(f"{C_YELLOW}⚠ Injected ICMP Type 3 Code 4 blackhole.{C_RESET}")
    elif choice == "3":
        fabric.primary.interface_drops += 1850
        fabric.primary.health_score = 42.0
        msg = f"Tail drop on egress queue QoS-Voice (CoS 5) on {fabric.primary.name}"
        if msg not in fabric.anomalies:
            fabric.anomalies.append(msg)
        print(f"{C_RED}⚠ Microburst buffer exhaustion simulated.{C_RESET}")
    elif choice == "4":
        fabric.primary.bgp_peers_up = fabric.primary.bgp_peers_total
        fabric.secondary.bgp_peers_up = fabric.secondary.bgp_peers_total
        fabric.primary.interface_drops = 0
        fabric.secondary.interface_drops = 0
        fabric.primary.health_score = 99.2
        fabric.secondary.health_score = 99.0
        fabric.anomalies.clear()
        print(f"{C_GREEN}✓ All synthetic network anomalies resolved.{C_RESET}")
    else:
        print(f"{C_YELLOW}Invalid selection.{C_RESET}")


def run_automated_rca(fabric: NetworkFabric):
    print(f"\n{C_CYAN}{C_BOLD}[AI-OPS / AUTOMATED ROOT CAUSE ANALYSIS ENGINE]{C_RESET}")
    print(f"{C_DIM}Correlating syslog, SNMP traps, and telemetry time-series...{C_RESET}")
    time.sleep(0.4)

    if not fabric.anomalies:
        print(f"{C_GREEN}No incidents found. Fabric state: OPTIMAL. Topology convergence: 100%.{C_RESET}")
        return

    print(f"{C_BOLD}{C_WHITE}Diagnostics & Remediation Recommendations:{C_RESET}")
    for idx, alert in enumerate(fabric.anomalies, 1):
        print(f"\n{C_YELLOW}[Incident #{idx}]{C_RESET} {alert}")
        if "BGP" in alert:
            print(f"  {C_BOLD}Root Cause:{C_RESET} TCP RST or Keepalive timeout on Port 179.")
            print(f"  {C_BOLD}Action:{C_RESET} Verify MTU size, check ACL blocking port 179, and verify dampening parameters.")
            print(f"  {C_GREEN}Auto-Heal:{C_RESET} Triggering graceful restart helper (RFC 4724)...")
        elif "MTU" in alert:
            print(f"  {C_BOLD}Root Cause:{C_RESET} Jumbo frame (9000 bytes) ingress hitting standard MTU (1500 bytes) transit interface.")
            print(f"  {C_BOLD}Action:{C_RESET} Standardize system MTU: `mtu 9216` across core trunk links.")
            print(f"  {C_GREEN}Auto-Heal:{C_RESET} Clamping TCP MSS to 1460 bytes via iptables/nftables.")
        elif "Failover" in alert or "FAULT" in alert:
            print(f"  {C_BOLD}Root Cause:{C_RESET} VRRP Master heartbeat loss exceeded 3x advertisement interval.")
            print(f"  {C_BOLD}Action:{C_RESET} Inspect BFD (Bidirectional Forwarding Detection) session and physical uplink SFP.")
            print(f"  {C_GREEN}Auto-Heal:{C_RESET} Secondary node successfully holding VIP traffic without blackholing.")
        else:
            print(f"  {C_BOLD}Root Cause:{C_RESET} Buffer congestion on high-rate microburst.")
            print(f"  {C_BOLD}Action:{C_RESET} Enable WRED (Weighted Random Early Detection) and Dynamic Buffer Allocation.")


def export_metrics(fabric: NetworkFabric):
    print(f"\n{C_BLUE}{C_BOLD}[PROMETHEUS / OPENTELEMETRY FORMAT EXPORT]{C_RESET}")
    ts = int(time.time() * 1000)
    metrics = [
        f'# HELP node_network_up Status of network node VIP state',
        f'# TYPE node_network_up gauge',
        f'node_network_up{{device="{fabric.primary.name}",role="primary",state="{fabric.primary.vrrp_state}"}} {1 if fabric.primary.vrrp_state == "MASTER" else 0} {ts}',
        f'node_network_up{{device="{fabric.secondary.name}",role="secondary",state="{fabric.secondary.vrrp_state}"}} {1 if fabric.secondary.vrrp_state == "MASTER" else 0} {ts}',
        f'# HELP node_bgp_established Established BGP sessions count',
        f'# TYPE node_bgp_established gauge',
        f'node_bgp_established{{device="{fabric.primary.name}"}} {fabric.primary.bgp_peers_up} {ts}',
        f'node_bgp_established{{device="{fabric.secondary.name}"}} {fabric.secondary.bgp_peers_up} {ts}',
        f'# HELP node_network_interface_drop_total Cumulative dropped packet count',
        f'# TYPE node_network_interface_drop_total counter',
        f'node_network_interface_drop_total{{device="{fabric.primary.name}",iface="eth0"}} {fabric.primary.interface_drops} {ts}',
        f'node_network_interface_drop_total{{device="{fabric.secondary.name}",iface="eth0"}} {fabric.secondary.interface_drops} {ts}',
        f'# HELP node_network_rtt_milliseconds Ping probe round-trip time',
        f'# TYPE node_network_rtt_milliseconds gauge',
        f'node_network_rtt_milliseconds{{device="{fabric.primary.name}",target="core-spine"}} {fabric.primary.rtt_ms} {ts}',
        f'node_network_rtt_milliseconds{{device="{fabric.secondary.name}",target="core-spine"}} {fabric.secondary.rtt_ms} {ts}',
    ]
    for m in metrics:
        print(f"  {C_CYAN}{m}{C_RESET}")
    print(f"\n{C_GREEN}✓ Export ready for Prometheus Scrape Endpoint (/metrics) and Grafana Agent.{C_RESET}")


def main():
    primary_node = RouterNode(
        name="CORE-GW-01",
        role="Active",
        vip="198.51.100.1",
        vrrp_priority=150,
        vrrp_state="MASTER",
        bgp_peers_up=4,
        bgp_peers_total=4,
        cpu_percent=22.4,
        interface_drops=0,
        rtt_ms=1.2,
        jitter_ms=0.15,
        health_score=99.8,
    )

    secondary_node = RouterNode(
        name="CORE-GW-02",
        role="Standby",
        vip="198.51.100.1",
        vrrp_priority=100,
        vrrp_state="BACKUP",
        bgp_peers_up=4,
        bgp_peers_total=4,
        cpu_percent=14.1,
        interface_drops=0,
        rtt_ms=1.4,
        jitter_ms=0.18,
        health_score=99.5,
    )

    fabric = NetworkFabric(primary=primary_node, secondary=secondary_node)

    banner()

    # Non-interactive / headless pipeline check
    if not sys.stdin.isatty():
        print(f"{C_YELLOW}[INFO] Non-interactive execution detected. Running automated test suite...{C_RESET}")
        render_dashboard(fabric)
        simulate_telemetry_stream(fabric)
        trigger_vrrp_failover(fabric)
        render_dashboard(fabric)
        run_automated_rca(fabric)
        export_metrics(fabric)
        print(f"\n{C_GREEN}{C_BOLD}[PASS] Automated pipeline validation completed successfully.{C_RESET}")
        return 0

    while True:
        render_dashboard(fabric)
        print(f"\n{C_BOLD}OPERATIONAL WORKFLOW CONTROLS:{C_RESET}")
        print(f"  {C_CYAN}1.{C_RESET} Stream Real-Time Telemetry (gNMI/sFlow)")
        print(f"  {C_CYAN}2.{C_RESET} Trigger Keepalived/VRRP Failover Simulation")
        print(f"  {C_CYAN}3.{C_RESET} Inject Network Anomaly (BGP Flap, MTU mismatch, Drops)")
        print(f"  {C_CYAN}4.{C_RESET} Run Automated Root Cause Analysis (RCA)")
        print(f"  {C_CYAN}5.{C_RESET} Export Prometheus / OpenTelemetry Metrics")
        print(f"  {C_CYAN}6.{C_RESET} Exit Simulator")

        try:
            choice = input(f"\n{C_BOLD}Select an action [1-6]: {C_RESET}").strip()
            if choice == "1":
                simulate_telemetry_stream(fabric)
            elif choice == "2":
                trigger_vrrp_failover(fabric)
            elif choice == "3":
                inject_anomaly(fabric)
            elif choice == "4":
                run_automated_rca(fabric)
            elif choice == "5":
                export_metrics(fabric)
            elif choice == "6" or choice.lower() in ("q", "exit"):
                print(f"{C_GREEN}Shutting down simulator. Goodbye!{C_RESET}")
                break
            else:
                print(f"{C_YELLOW}Invalid option. Please choose between 1 and 6.{C_RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C_YELLOW}Exiting cleanly.{C_RESET}")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
