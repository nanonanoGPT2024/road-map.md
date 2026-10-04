#!/usr/bin/env python3
"""
Lab Exercise: Module 02 - Network Engineer Bab 01
Simulasi Teknis Mandiri:
1. VXLAN Packet Encapsulation & PMTUD Black Hole Diagnostic
2. Linux Kernel Conntrack Table Exhaustion & SoftIRQ Pressure Simulator
3. TCP MSS Clamping & Jumbo Frame Optimization Engine
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[1;31m"
CLR_GREEN = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_BLUE = "\033[1;34m"
CLR_MAGENTA = "\033[1;35m"
CLR_CYAN = "\033[1;36m"
CLR_BG_RED = "\033[41;1;37m"
CLR_BG_GREEN = "\033[42;1;30m"
CLR_BG_BLUE = "\033[44;1;37m"


def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}================================================================================
  NETWORK ARCHITECTURE SIMULATION ENGINE: BAB-01 MODUL-02
  Kernel Datapath, EVPN-VXLAN Overhead, & Conntrack Resilience Lab
================================================================================{CLR_RESET}
"""
    print(banner)


@dataclass
class Packet:
    packet_id: int
    src_ip: str
    dst_ip: str
    payload_size: int
    df_bit: bool = True  # Don't Fragment bit
    inner_protocol: str = "TCP"
    vni: int = 1000


@dataclass
class VxlanTunnelConfig:
    underlay_mtu: int = 1500
    outer_eth_header: int = 14
    outer_ip_header: int = 20
    outer_udp_header: int = 8
    vxlan_header: int = 8
    mss_clamping: bool = False
    clamped_mss_target: int = 1410

    @property
    def total_overhead(self) -> int:
        return (
            self.outer_eth_header
            + self.outer_ip_header
            + self.outer_udp_header
            + self.vxlan_header
        )

    @property
    def max_inner_payload_safe(self) -> int:
        # 1500 (Underlay) - 50 (Overhead) - 20 (Inner IP) - 20 (Inner TCP) = 1410 bytes
        return self.underlay_mtu - self.total_overhead - 40


def simulate_vxlan_pmtud_scenario():
    print(f"\n{CLR_BLUE}{CLR_BOLD}[SCENARIO 1] EVPN-VXLAN Encapsulation & PMTUD Black Hole Audit{CLR_RESET}")
    print(f"{CLR_YELLOW}Mengevaluasi datapath enkapsulasi L2 over L3 saat payload melintasi Underlay Fabric...{CLR_RESET}\n")

    configs = [
        ("Default Underlay (Standard 1500 MTU, No MSS Clamping)", VxlanTunnelConfig(underlay_mtu=1500, mss_clamping=False)),
        ("Remediasi A: Jumbo Frames Active (9000 MTU Fabric)", VxlanTunnelConfig(underlay_mtu=9000, mss_clamping=False)),
        ("Remediasi B: iptables TCP MSS Clamping (1410 bytes)", VxlanTunnelConfig(underlay_mtu=1500, mss_clamping=True, clamped_mss_target=1410)),
    ]

    test_payloads = [64, 512, 1400, 1460, 4096]

    for title, cfg in configs:
        print(f"{CLR_BOLD}--> Testing Topology:{CLR_RESET} {CLR_CYAN}{title}{CLR_RESET}")
        print(f"    Overhead: {cfg.total_overhead} bytes | Underlay MTU: {cfg.underlay_mtu} | Safe TCP Payload: {cfg.max_inner_payload_safe}B")
        
        dropped = 0
        transmitted = 0

        for idx, payload in enumerate(test_payloads, start=1):
            inner_frame_len = payload + 40  # IP (20) + TCP (20)
            total_wire_len = inner_frame_len + cfg.total_overhead

            # If MSS clamping is enabled on SYN, clamp the payload
            actual_payload = min(payload, cfg.clamped_mss_target) if cfg.mss_clamping else payload
            actual_wire_len = actual_payload + 40 + cfg.total_overhead

            status = ""
            if actual_wire_len > cfg.underlay_mtu:
                status = f"{CLR_BG_RED} DROPPED (PMTUD Black Hole) {CLR_RESET} Exceeds Underlay MTU ({actual_wire_len} > {cfg.underlay_mtu})"
                dropped += 1
            else:
                if cfg.mss_clamping and payload > cfg.clamped_mss_target:
                    status = f"{CLR_GREEN} FORWARDED (Clamped {payload}B -> {actual_payload}B) {CLR_RESET} Wire: {actual_wire_len}B"
                else:
                    status = f"{CLR_GREEN} FORWARDED {CLR_RESET} Wire: {actual_wire_len}B"
                transmitted += 1

            print(f"    Packet #{idx:02d} [Payload={payload:4d}B]: {status}")
            time.sleep(0.04)

        success_rate = (transmitted / len(test_payloads)) * 100
        color = CLR_GREEN if success_rate == 100 else (CLR_YELLOW if success_rate > 50 else CLR_RED)
        print(f"    {CLR_BOLD}Throughput Efficiency:{CLR_RESET} {color}{success_rate:.1f}% Packet Delivery{CLR_RESET}\n")


@dataclass
class ConntrackEntry:
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    state: str
    ttl: int


class ConntrackTable:
    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self.entries: Dict[str, ConntrackEntry] = {}
        self.drop_count: int = 0
        self.syn_flood_detected: bool = False

    def insert(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int, state: str = "SYN_RECV") -> bool:
        flow_key = f"{src_ip}:{src_port}->{dst_ip}:{dst_port}"
        if len(self.entries) >= self.max_entries:
            self.drop_count += 1
            return False
        self.entries[flow_key] = ConntrackEntry(src_ip, dst_ip, src_port, dst_port, "TCP", state, ttl=30)
        return True

    def evict_expired(self):
        to_del = [k for k, v in self.entries.items() if v.ttl <= 0]
        for k in to_del:
            del self.entries[k]


def simulate_conntrack_table_exhaustion():
    print(f"\n{CLR_BLUE}{CLR_BOLD}[SCENARIO 2] Linux Kernel Netfilter Conntrack Table & SoftIRQ Stress{CLR_RESET}")
    print(f"{CLR_YELLOW}Simulasi lonjakan koneksi mikroburst dan mitigasi sysctl tuning...{CLR_RESET}\n")

    table_capacity = 250
    ct_table = ConntrackTable(max_entries=table_capacity)

    print(f"[*] Kernel Parameters Initial: {CLR_BOLD}net.netfilter.nf_conntrack_max = {table_capacity}{CLR_RESET}")
    print("[*] Mengirim 350 paket inisiasi koneksi (TCP SYN Flood / Microburst)...")

    for i in range(1, 351):
        src_ip = f"10.0.{random.randint(1, 20)}.{random.randint(1, 254)}"
        src_port = random.randint(1024, 65535)
        dst_ip = "192.168.100.10"
        dst_port = 80
        success = ct_table.insert(src_ip, dst_ip, src_port, dst_port)
        
        if not success and not ct_table.syn_flood_detected:
            ct_table.syn_flood_detected = True
            print(f"    {CLR_RED}[ALERT] Conntrack Table Full! (Entries: {len(ct_table.entries)}/{table_capacity}){CLR_RESET}")
            print(f"    {CLR_RED}[KERNEL] nf_conntrack: table full, dropping packet! SoftIRQ spiked.{CLR_RESET}")

    utilization = (len(ct_table.entries) / table_capacity) * 100
    print(f"\n{CLR_BOLD}Hasil Uji Beban:{CLR_RESET}")
    print(f"  - Total Terdaftar : {CLR_YELLOW}{len(ct_table.entries)}{CLR_RESET} flows")
    print(f"  - Total Dropped   : {CLR_RED}{ct_table.drop_count}{CLR_RESET} packets")
    print(f"  - Utilisasi Hash  : {CLR_RED if utilization >= 100 else CLR_GREEN}{utilization:.1f}%{CLR_RESET}")

    print(f"\n{CLR_GREEN}{CLR_BOLD}[MITIGASI KERNEL TUNING DITERAPKAN]{CLR_RESET}")
    print("  1. sysctl -w net.netfilter.nf_conntrack_max=262144")
    print("  2. sysctl -w net.ipv4.tcp_syncookies=1")
    print("  3. sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=600")
    print("  4. iptables -t raw -A PREROUTING -p tcp --dport 80 -j NOTRACK  (Stateless Bypass)")

    tuned_table = ConntrackTable(max_entries=2000)
    for i in range(1, 351):
        src_ip = f"10.0.{random.randint(1, 20)}.{random.randint(1, 254)}"
        src_port = random.randint(1024, 65535)
        tuned_table.insert(src_ip, dst_ip, src_port, dst_port)

    print(f"  -> Uji Ulang Pasca-Tuning: Dropped = {CLR_GREEN}{tuned_table.drop_count}{CLR_RESET}, Entries = {CLR_GREEN}{len(tuned_table.entries)}{CLR_RESET} flows ({CLR_GREEN}100% Zero-Drop{CLR_RESET})\n")


def simulate_l2_overlay_fdb():
    print(f"{CLR_BLUE}{CLR_BOLD}[SCENARIO 3] Linux Bridge & VXLAN Forwarding Database (FDB) Inspection{CLR_RESET}")
    print(f"{CLR_YELLOW}Pemetaan Inner MAC Address ke Outer Remote VTEP IP (RFC 7348)...{CLR_RESET}\n")

    fdb_records = [
        {"mac": "52:54:00:12:34:56", "vni": 1000, "vtep_dst": "172.16.0.2", "state": "permanent", "interface": "vxlan-vni1000"},
        {"mac": "52:54:00:98:76:54", "vni": 1000, "vtep_dst": "172.16.0.3", "state": "reachable", "interface": "vxlan-vni1000"},
        {"mac": "00:00:00:00:00:00", "vni": 1000, "vtep_dst": "239.1.1.1",   "state": "static",    "interface": "all (BUM/Multicast)"},
    ]

    header = f"{'INNER MAC ADDR':^20} | {'VNI':^8} | {'REMOTE VTEP IP':^16} | {'PORT/IFACE':^18} | {'STATUS':^10}"
    print(f"{CLR_BOLD}{header}{CLR_RESET}")
    print("-" * len(header))

    for rec in fdb_records:
        row = f"{rec['mac']:^20} | {rec['vni']:^8} | {rec['vtep_dst']:^16} | {rec['interface']:^18} | {CLR_GREEN}{rec['state']:^10}{CLR_RESET}"
        print(row)
    print("\n" + "=" * 80)


def main():
    print_banner()
    simulate_vxlan_pmtud_scenario()
    simulate_conntrack_table_exhaustion()
    simulate_l2_overlay_fdb()
    print(f"{CLR_BG_GREEN}{CLR_BOLD}  LAB SIMULATION COMPLETE - SELURUH TEST SUITE SELESAI DENGAN STATUS PASS  {CLR_RESET}\n")


if __name__ == "__main__":
    main()
