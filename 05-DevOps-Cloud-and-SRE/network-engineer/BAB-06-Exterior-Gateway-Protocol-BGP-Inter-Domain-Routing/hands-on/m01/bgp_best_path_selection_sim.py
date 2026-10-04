#!/usr/bin/env python3
"""
BGP Best Path Selection Algorithm Simulator & RPKI ROV Engine
Standard: GEMINI.md - NETWORK-ENGINEER Track (Bab 06)
Author: Principal Cloud & SRE Curriculum Architect

Simulator ini mengimplementasikan algoritma deterministik BGP Best Path Selection
lengkap dengan 11-step tie-breaker breakdown dan validasi kriptografis RPKI ROA.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import List, Optional, Tuple
import ipaddress
import sys


class OriginCode(IntEnum):
    IGP = 0
    EGP = 1
    INCOMPLETE = 2

    def __str__(self):
        return self.name


class NeighborType(IntEnum):
    EBGP = 0
    IBGP = 1

    def __str__(self):
        return self.name


class RPKIStatus(Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class ROAEntry:
    prefix: ipaddress.IPv4Network
    authorized_asn: int
    max_length: int


@dataclass
class BGPRouteCandidate:
    path_id: str
    prefix: ipaddress.IPv4Network
    origin_asn: int
    next_hop: ipaddress.IPv4Address
    weight: int = 0
    local_pref: int = 100
    locally_originated: bool = False
    as_path: List[int] = field(default_factory=list)
    origin: OriginCode = OriginCode.IGP
    med: int = 0
    neighbor_type: NeighborType = NeighborType.EBGP
    igp_metric_to_next_hop: int = 10
    router_id: ipaddress.IPv4Address = ipaddress.IPv4Address("192.0.2.1")
    neighbor_ip: ipaddress.IPv4Address = ipaddress.IPv4Address("192.0.2.1")
    rpki_status: RPKIStatus = RPKIStatus.NOT_FOUND

    @property
    def as_path_length(self) -> int:
        return len(self.as_path)

    def __str__(self) -> str:
        return (
            f"[{self.path_id}] via {self.next_hop} | AS-Path: {self.as_path} | "
            f"LocPref: {self.local_pref} | Weight: {self.weight} | Origin: {self.origin} | "
            f"MED: {self.med} | Type: {self.neighbor_type} | IGP-Cost: {self.igp_metric_to_next_hop} | "
            f"RPKI: {self.rpki_status.value}"
        )


class RPKIValidator:
    def __init__(self, roa_table: List[ROAEntry]):
        self.roa_table = roa_table

    def validate(self, prefix: ipaddress.IPv4Network, origin_asn: int) -> RPKIStatus:
        matching_roas = [
            roa for roa in self.roa_table
            if prefix.subnet_of(roa.prefix)
        ]
        
        if not matching_roas:
            return RPKIStatus.NOT_FOUND

        for roa in matching_roas:
            if origin_asn == roa.authorized_asn and prefix.prefixlen <= roa.max_length:
                return RPKIStatus.VALID

        return RPKIStatus.INVALID


class BGPBestPathEngine:
    def __init__(self, reject_rpki_invalid: bool = True):
        self.reject_rpki_invalid = reject_rpki_invalid

    def evaluate(self, candidates: List[BGPRouteCandidate]) -> Tuple[Optional[BGPRouteCandidate], List[str]]:
        logs: List[str] = []
        logs.append(f"[*] Memulai evaluasi Best Path untuk {len(candidates)} kandidat rute...")

        current_pool = list(candidates)

        # 0. Pre-filter: RPKI Invalid Drop
        if self.reject_rpki_invalid:
            filtered = [r for r in current_pool if r.rpki_status != RPKIStatus.INVALID]
            dropped = [r for r in current_pool if r.rpki_status == RPKIStatus.INVALID]
            for d in dropped:
                logs.append(f"[-] [RPKI DROP] {d.path_id} dibuang karena status RPKI INVALID!")
            current_pool = filtered

        if not current_pool:
            logs.append("[!] Seluruh kandidat rute tereliminasi pada filter RPKI.")
            return None, logs

        if len(current_pool) == 1:
            return current_pool[0], logs

        # Step 1: Highest Weight (Cisco proprietary, local to router)
        max_weight = max(r.weight for r in current_pool)
        step_pool = [r for r in current_pool if r.weight == max_weight]
        if len(step_pool) < len(current_pool):
            eliminated = [r.path_id for r in current_pool if r.weight < max_weight]
            logs.append(f"[Step 1: Weight] Tertinggi: {max_weight}. Mengeliminasi: {eliminated}")
            current_pool = step_pool
        if len(current_pool) == 1:
            return current_pool[0], logs

        # Step 2: Highest Local Preference
        max_local_pref = max(r.local_pref for r in current_pool)
        step_pool = [r for r in current_pool if r.local_pref == max_local_pref]
        if len(step_pool) < len(current_pool):
            eliminated = [r.path_id for r in current_pool if r.local_pref < max_local_pref]
            logs.append(f"[Step 2: Local Pref] Tertinggi: {max_local_pref}. Mengeliminasi: {eliminated}")
            current_pool = step_pool
        if len(current_pool) == 1:
            return current_pool[0], logs

        # Step 3: Locally Originated (network/aggregate vs learned via BGP)
        has_local = any(r.locally_originated for r in current_pool)
        if has_local:
            step_pool = [r for r in current_pool if r.locally_originated]
            if len(step_pool) < len(current_pool):
                eliminated = [r.path_id for r in current_pool if not r.locally_originated]
                logs.append(f"[Step 3: Locally Originated] Mengeliminasi non-local: {eliminated}")
                current_pool = step_pool
            if len(current_pool) == 1:
                return current_pool[0], logs

        # Step 4: Shortest AS_PATH Length
        min_as_path = min(r.as_path_length for r in current_pool)
        step_pool = [r for r in current_pool if r.as_path_length == min_as_path]
        if len(step_pool) < len(current_pool):
            eliminated = [r.path_id for r in current_pool if r.as_path_length > min_as_path]
            logs.append(f"[Step 4: AS-Path] Terpendek ({min_as_path} hops). Mengeliminasi: {eliminated}")
            current_pool = step_pool
        if len(current_pool) == 1:
            return current_pool[0], logs

        # Step 5: Lowest Origin Code (IGP < EGP < INCOMPLETE)
        min_origin = min(r.origin for r in current_pool)
        step_pool = [r for r in current_pool if r.origin == min_origin]
        if len(step_pool) < len(current_pool):
            eliminated = [r.path_id for r in current_pool if r.origin > min_origin]
            logs.append(f"[Step 5: Origin Code] Terendah ({OriginCode(min_origin).name}). Mengeliminasi: {eliminated}")
            current_pool = step_pool
        if len(current_pool) == 1:
            return current_pool[0], logs

        # Step 6: Lowest MED (Multi-Exit Discriminator)
        min_med = min(r.med for r in current_pool)
        step_pool = [r for r in current_pool if r.med == min_med]
        if len(step_pool) < len(current_pool):
            eliminated = [r.path_id for r in current_pool if r.med > min_med]
            logs.append(f"[Step 6: MED] Terendah ({min_med}). Mengeliminasi: {eliminated}")
            current_pool = step_pool
        if len(current_pool) == 1:
            return current_pool[0], logs

        # Step 7: Neighbor Type (eBGP over iBGP)
        has_ebgp = any(r.neighbor_type == NeighborType.EBGP for r in current_pool)
        if has_ebgp:
            step_pool = [r for r in current_pool if r.neighbor_type == NeighborType.EBGP]
            if len(step_pool) < len(current_pool):
                eliminated = [r.path_id for r in current_pool if r.neighbor_type == NeighborType.IBGP]
                logs.append(f"[Step 7: Peer Type] Memilih eBGP. Mengeliminasi iBGP: {eliminated}")
                current_pool = step_pool
            if len(current_pool) == 1:
                return current_pool[0], logs

        # Step 8: Lowest IGP Metric to Next Hop
        min_igp = min(r.igp_metric_to_next_hop for r in current_pool)
        step_pool = [r for r in current_pool if r.igp_metric_to_next_hop == min_igp]
        if len(step_pool) < len(current_pool):
            eliminated = [r.path_id for r in current_pool if r.igp_metric_to_next_hop > min_igp]
            logs.append(f"[Step 8: IGP Metric] Terendah ({min_igp}). Mengeliminasi: {eliminated}")
            current_pool = step_pool
        if len(current_pool) == 1:
            return current_pool[0], logs

        # Step 9: Lowest BGP Router ID
        min_rid = min(r.router_id for r in current_pool)
        step_pool = [r for r in current_pool if r.router_id == min_rid]
        if len(step_pool) < len(current_pool):
            eliminated = [r.path_id for r in current_pool if r.router_id > min_rid]
            logs.append(f"[Step 9: Router ID] Terendah ({min_rid}). Mengeliminasi: {eliminated}")
            current_pool = step_pool
        if len(current_pool) == 1:
            return current_pool[0], logs

        # Step 10: Lowest Neighbor IP Address
        min_peer_ip = min(r.neighbor_ip for r in current_pool)
        step_pool = [r for r in current_pool if r.neighbor_ip == min_peer_ip]
        if len(step_pool) < len(current_pool):
            eliminated = [r.path_id for r in current_pool if r.neighbor_ip > min_peer_ip]
            logs.append(f"[Step 10: Peer IP] Terendah ({min_peer_ip}). Mengeliminasi: {eliminated}")
            current_pool = step_pool

        return current_pool[0], logs


def run_simulation():
    print("=" * 75)
    print(" BGP-4 Best Path Selection & RPKI Route Origin Validation Simulator")
    print(" Standard Kurikulum: GEMINI.md | Network Engineer Track")
    print("=" * 75)

    # 1. Inisialisasi Database ROA RPKI
    roa_database = [
        ROAEntry(prefix=ipaddress.IPv4Network("198.51.100.0/22"), authorized_asn=65001, max_length=24),
        ROAEntry(prefix=ipaddress.IPv4Network("203.0.113.0/24"), authorized_asn=65002, max_length=24),
    ]
    validator = R