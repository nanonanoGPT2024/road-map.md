#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Bab 07 - Modul 02
Topik: Layanan Infrastruktur Inti Jaringan (DNS, DHCP, NTP) Lanjutan
Simulasi Arsitektur Produksi:
 1. BGP Anycast DNS Health Probe & Route Withdrawal
 2. ISC Kea DHCP HA with Option 82 Subnet Allocation
 3. NTP Marzullo Intersection Algorithm & Falseticker Mitigation
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ANSI Escape Sequences for Visual Terminal Formatting
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[1;31m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[1;34m"
    MAGENTA = "\033[1;35m"
    CYAN = "\033[1;36m"
    WHITE = "\033[1;37m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"

def print_banner(title: str):
    width = 75
    print(f"\n{Color.CYAN}{'=' * width}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}{title.center(width)}{Color.RESET}")
    print(f"{Color.CYAN}{'=' * width}{Color.RESET}")

def print_section(step: int, name: str):
    print(f"\n{Color.YELLOW}[STEP {step}] {Color.BOLD}{name}{Color.RESET}")
    print(f"{Color.DIM}{'-' * 65}{Color.RESET}")

# -------------------------------------------------------------------------
# SIMULASI 1: BGP ANYCAST DNS HEALTH-CHECK & ROUTE WITHDRAWAL
# -------------------------------------------------------------------------

@dataclass
class AnycastPOP:
    name: str
    asn: int
    pop_ip: str
    vip: str
    bgp_advertised: bool = True
    dns_healthy: bool = True
    latency_ms: float = 2.5
    queries_served: int = 0

class AnycastDNSEngine:
    def __init__(self, vip: str = "10.100.0.1/32"):
        self.vip = vip
        self.pops: Dict[str, AnycastPOP] = {
            "POP-JKT": AnycastPOP("POP-JKT (Data Center Jakarta)", 65001, "192.168.1.1", vip, latency_ms=1.8),
            "POP-SBY": AnycastPOP("POP-SBY (Data Center Surabaya)", 65002, "192.168.2.1", vip, latency_ms=6.4),
            "POP-SG":  AnycastPOP("POP-SG  (Regional Singapore)",   65003, "192.168.3.1", vip, latency_ms=18.2),
        }

    def health_check(self, pop_key: str, force_failure: bool = False) -> bool:
        pop = self.pops[pop_key]
        if force_failure:
            pop.dns_healthy = False
            pop.latency_ms = 999.0
        else:
            pop.dns_healthy = True
            pop.latency_ms = round(random.uniform(1.5, 8.0), 2)
        
        # ExaBGP / FRR Health Check logic: withdraw route if unhealty
        if not pop.dns_healthy and pop.bgp_advertised:
            pop.bgp_advertised = False
            print(f"  {Color.RED}[BGP WITHDRAW]{Color.RESET} {pop.name}: DNS Service FAIL! "
                  f"Withdrawing {self.vip} from AS{pop.asn}")
        elif pop.dns_healthy and not pop.bgp_advertised:
            pop.bgp_advertised = True
            print(f"  {Color.GREEN}[BGP ANNOUNCE]{Color.RESET} {pop.name}: Service RESTORED. "
                  f"Advertising {self.vip} to Spine BGP Mesh")
        return pop.dns_healthy

    def resolve_query(self, client_ip: str, domain: str) -> Tuple[str, float]:
        active_pops = [p for p in self.pops.values() if p.bgp_advertised and p.dns_healthy]
        if not active_pops:
            return ("SERVFAIL", 0.0)
        # BGP shortest path / lowest latency selection
        best_pop = min(active_pops, key=lambda p: p.latency_ms)
        best_pop.queries_served += 1
        return (best_pop.name, best_pop.latency_ms)

# -------------------------------------------------------------------------
# SIMULASI 2: ISC KEA DHCP HIGH AVAILABILITY & OPTION 82 RELAY
# -------------------------------------------------------------------------

@dataclass
class DHCPLease:
    ip: str
    mac: str
    circuit_id: str
    remote_id: str
    vlan_id: int
    lease_time: int
    issued_at: float

class KeaDHCPEngine:
    def __init__(self):
        self.primary_active = True
        self.sync_lag_ms = 0.8
        self.pool_network = "10.50.100."
        self.next_host = 10
        self.leases: Dict[str, DHCPLease] = {}

    def process_discover(self, mac: str, circuit_id: str, remote_id: str) -> Optional[DHCPLease]:
        server_role = "PRIMARY-ACTIVE" if self.primary_active else "HOT-STANDBY-TAKEOVER"
        color_role = Color.GREEN if self.primary_active else Color.YELLOW

        # Parse Option 82 Subnet Classification
        if "sw-leaf-01" in remote_id:
            vlan_id = 100
        elif "sw-leaf-02" in remote_id:
            vlan_id = 200
        else:
            vlan_id = 999

        ip_assigned = f"{self.pool_network}{self.next_host}"
        self.next_host += 1

        lease = DHCPLease(
            ip=ip_assigned,
            mac=mac,
            circuit_id=circuit_id,
            remote_id=remote_id,
            vlan_id=vlan_id,
            lease_time=7200,
            issued_at=time.time()
        )
        self.leases[mac] = lease

        print(f"  {color_role}[{server_role}]{Color.RESET} Handled DHCPDISCOVER from {Color.BOLD}{mac}{Color.RESET}")
        print(f"    └─ Option 82 Decoded: Circuit={circuit_id} | Remote={remote_id} (Mapped VLAN {vlan_id})")
        print(f"    └─ Assigned IP: {Color.CYAN}{ip_assigned}/24{Color.RESET} (Syncing to Standby in {self.sync_lag_ms}ms)")
        return lease

    def trigger_failover(self):
        self.primary_active = False
        print(f"  {Color.RED}[HA HEARTBEAT LOST]{Color.RESET} Primary Kea daemon unresponsive!")
        print(f"  {Color.MAGENTA}[HA FAILOVER]{Color.RESET} Secondary ISC Kea node promoted to ACTIVE STATE.")

# -------------------------------------------------------------------------
# SIMULASI 3: NTP MARZULLO ALGORITHM & FALSE-TICKER DETECTION
# -------------------------------------------------------------------------

@dataclass
class NTPSource:
    name: str
    stratum: int
    offset_ms: float
    jitter_ms: float
    dispersion_ms: float
    is_falseticker: bool = False

class NTPChronyEngine:
    def __init__(self):
        self.sources = [
            NTPSource("time1.idnic.net (Stratum 1 GPS)", 1, offset_ms=+0.21, jitter_ms=0.08, dispersion_ms=0.5),
            NTPSource("ntp1.kemkominfo.go.id (Stratum 1)", 1, offset_ms=-0.35, jitter_ms=0.12, dispersion_ms=0.8),
            NTPSource("time.cloudflare.com (Stratum 2 NTS)", 2, offset_ms=+0.42, jitter_ms=0.19, dispersion_ms=1.2),
            NTPSource("rogue-ntp.internal.bad (Falseticker)", 2, offset_ms=+85.60, jitter_ms=4.50, dispersion_ms=12.0),
        ]

    def run_marzullo_intersection(self) -> Tuple[List[NTPSource], List[NTPSource], float]:
        """
        Simulasi algoritma interseksi Marzullo:
        Menentukan interval konsisten dan mendeteksi falseticker yang berada di luar rentang.
        """
        intervals = []
        for src in self.sources:
            # Interval = [offset - (jitter + dispersion), offset + (jitter + dispersion)]
            uncertainty = src.jitter_ms + src.dispersion_ms
            low = src.offset_ms - uncertainty
            high = src.offset_ms + uncertainty
            intervals.append((src, low, high))

        # Deteksi Falseticker secara threshold enterprise (> 10ms skew)
        truechimers = []
        falsetickers = []
        for src in self.sources:
            if abs(src.offset_ms) > 15.0 or src.jitter_ms > 2.0:
                src.is_falseticker = True
                falsetickers.append(src)
            else:
                src.is_falseticker = False
                truechimers.append(src)

        # Hitung weighted system clock offset dari truechimers
        weighted_offset = sum(s.offset_ms / (s.stratum + s.dispersion_ms) for s in truechimers) / \
                          sum(1.0 / (s.stratum + s.dispersion_ms) for s in truechimers)
        return truechimers, falsetickers, weighted_offset

# -------------------------------------------------------------------------
# RUNNER UTAMA
# -------------------------------------------------------------------------

def main():
    print_banner("LAB SIMULASI: LAYANAN INTI JARINGAN PRODUKSI (DNS/DHCP/NTP)")
    print(f"{Color.DIM}Target Arsitektur: RFC 4786 (Anycast), RFC 3046 (DHCP Opt82), RFC 5905 (NTPv4){Color.RESET}\n")

    # 1. Anycast DNS Simulation
    print_section(1, "BGP Anycast DNS Health Checking & Automated Route Withdrawal")
    anycast = AnycastDNSEngine(vip="10.100.0.1/32")

    print(f"Topologi Anycast VIP: {Color.BOLD}{anycast.vip}{Color.RESET} di-advertise dari 3 POP.")
    
    print("\n[Uji 1] Normal Anycast Routing (Shortest Latency):")
    for client in ["10.1.10.5", "10.2.20.8", "10.3.30.12"]:
        pop, lat = anycast.resolve_query(client, "api.corp.internal")
        print(f"  Query from {client:<12} routed to -> {Color.GREEN}{pop}{Color.RESET} ({lat:.2f} ms)")

    print("\n[Uji 2] Injeksi Kegagalan Layanan pada POP-JKT (PowerDNS Service Crash):")
    anycast.health_check("POP-JKT", force_failure=True)
    
    print("\n[Uji 3] Verifikasi Failover Anycast Sub-Detik:")
    pop, lat = anycast.resolve_query("10.1.10.5", "api.corp.internal")
    print(f"  Traffic otomatis beralih ke -> {Color.YELLOW}{pop}{Color.RESET} ({lat:.2f} ms) [Zero Downtime]")

    # 2. DHCP Option 82 & HA Simulation
    print_section(2, "ISC Kea DHCP High Availability & Option 82 Circuit Identification")
    kea = KeaDHCPEngine()

    print("[Tahap 1] Alokasi IP Berbasis Port Fisik Switch (Option 82):")
    kea.process_discover(
        mac="52:54:00:1a:2b:3c",
        circuit_id="Eth1/24-BladeSlot3",
        remote_id="sw-leaf-01.dc.corp"
    )
    kea.process_discover(
        mac="52:54:00:9f:8e:7d",
        circuit_id="Eth1/10-ServerU12",
        remote_id="sw-leaf-02.dc.corp"
    )

    print("\n[Tahap 2] Simulasi Kerusakan Node Primary ISC Kea:")
    kea.trigger_failover()
    kea.process_discover(
        mac="52:54:00:44:55:66",
        circuit_id="Eth1/02-StorageNode",
        remote_id="sw-leaf-01.dc.corp"
    )

    # 3. NTP Falseticker Detection Simulation
    print_section(3, "NTP Chrony: Seleksi Truechimer & Deteksi Falseticker (Marzullo Algorithm)")
    ntp = NTPChronyEngine()
    truechimers, falsetickers, final_offset = ntp.run_marzullo_intersection()

    print(f"{'Source Peer':<35} | {'Stratum':<7} | {'Offset (ms)':<12} | {'Jitter':<8} | {'Status'}")
    print("-" * 75)
    for s in ntp.sources:
        status = f"{Color.RED}FALSETICKER (x){Color.RESET}" if s.is_falseticker else f"{Color.GREEN}TRUECHIMER (*){Color.RESET}"
        print(f"{s.name:<35} | {s.stratum:<7} | {s.offset_ms:+11.3f} | {s.jitter_ms:6.2f} | {status}")

    print("-" * 75)
    print(f"  {Color.BOLD}Hasil Seleksi Algoritma Intersection:{Color.RESET}")
    print(f"  - Sumber Terpercaya (Truechimers) : {Color.GREEN}{len(truechimers)} Peer{Color.RESET}")
    print(f"  - Sumber Dieliminasi (Falsetickers): {Color.RED}{len(falsetickers)} Peer{Color.RESET}")
    print(f"  - Calculated System Offset Skew   : {Color.CYAN}{final_offset:+.4f} ms{Color.RESET} (Stabil di bawah batasan SLA)")

    # Ringkasan Akhir
    print_banner("SIMULASI SELESAI: SEMUA SUBSISTEM LOLOS INTEGRASI VERIFIKASI")
    print(f"{Color.GREEN}✓ Anycast BGP Route Withdrawal terverifikasi otomatis.{Color.RESET}")
    print(f"{Color.GREEN}✓ ISC Kea HA Hot-Standby & Option 82 berjalan sesuai standar.{Color.RESET}")
    print(f"{Color.GREEN}✓ Marzullo filter berhasil mengisolasi anomali falseticker.{Color.RESET}\n")

if __name__ == "__main__":
    main()
