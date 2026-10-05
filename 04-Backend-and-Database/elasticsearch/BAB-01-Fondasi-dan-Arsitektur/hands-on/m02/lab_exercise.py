#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Arsitektur Produksi Tingkat Lanjut Elasticsearch
BAB-01: Fondasi dan Arsitektur Elasticsearch

Fitur Simulasi:
- Node Roles: Dedicated Master, Data Hot, Data Warm, Data Cold, Coordinating, Ingest.
- Ingestion Flow: Coordinating -> Ingest Pipeline -> Hash Routing (Murmur3-like) -> Primary -> Replicas.
- Cluster Health & Quorum: Split-Brain protection, Voting Configuration, State Transitions (GREEN, YELLOW, RED).
- Allocation Awareness: Rack/Zone Distribution & Failover Auto-Promotion.
- Visualisasi: ANSI Terminal Colors & Interactive Diagnostic CLI.
"""

from __future__ import annotations
import sys
import time
import hashlib
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# ANSI Color Palette
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"


def header(text: str) -> None:
    line = "═" * 76
    print(f"\n{Color.CYAN}{Color.BOLD}{line}")
    print(f"  {text}")
    print(f"{line}{Color.RESET}")


def subheader(text: str) -> None:
    print(f"\n{Color.YELLOW}{Color.BOLD}▶ {text}{Color.RESET}")


def success(text: str) -> None:
    print(f"{Color.GREEN}✔ {text}{Color.RESET}")


def warning(text: str) -> None:
    print(f"{Color.YELLOW}⚠ {text}{Color.RESET}")


def error(text: str) -> None:
    print(f"{Color.RED}✖ {text}{Color.RESET}")


def info(text: str) -> None:
    print(f"{Color.BLUE}ℹ {text}{Color.RESET}")


# ==============================================================================
# Cluster Architecture & Domain Models
# ==============================================================================
class ClusterStatus(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class NodeRole(Enum):
    MASTER = "master"
    DATA_HOT = "data_hot"
    DATA_WARM = "data_warm"
    DATA_COLD = "data_cold"
    INGEST = "ingest"
    COORDINATING = "coordinating"


@dataclass
class Shard:
    shard_id: int
    index_name: str
    is_primary: bool
    node_id: Optional[str] = None
    unassigned: bool = False
    doc_count: int = 0


@dataclass
class Node:
    node_id: str
    name: str
    roles: List[NodeRole]
    rack: str
    zone: str
    ip: str
    is_alive: bool = True
    shards: List[Shard] = field(default_factory=list)

    @property
    def role_str(self) -> str:
        return ",".join(r.value for r in self.roles)


@dataclass
class IndexMetadata:
    name: str
    primary_shards: int
    replica_factor: int
    routing_key: str = "_id"


# ==============================================================================
# Simulation Engine
# ==============================================================================
class ElasticsearchClusterSimulator:
    def __init__(self, cluster_name: str = "es-prod-enterprise"):
        self.cluster_name = cluster_name
        self.nodes: Dict[str, Node] = {}
        self.indices: Dict[str, IndexMetadata] = {}
        self.all_shards: List[Shard] = []
        self.cluster_state_version = 1
        self._bootstrap_cluster()

    def _bootstrap_cluster(self) -> None:
        """Membangun topologi cluster production HA multi-zone."""
        specs = [
            ("node-m01", "es-master-01", [NodeRole.MASTER], "rack-a1", "ap-southeast-3a", "10.0.1.11"),
            ("node-m02", "es-master-02", [NodeRole.MASTER], "rack-b1", "ap-southeast-3b", "10.0.1.12"),
            ("node-m03", "es-master-03", [NodeRole.MASTER], "rack-c1", "ap-southeast-3c", "10.0.1.13"),
            ("node-c01", "es-coord-01", [NodeRole.COORDINATING, NodeRole.INGEST], "rack-a2", "ap-southeast-3a", "10.0.2.21"),
            ("node-c02", "es-coord-02", [NodeRole.COORDINATING, NodeRole.INGEST], "rack-b2", "ap-southeast-3b", "10.0.2.22"),
            ("node-dh01", "es-data-hot-01", [NodeRole.DATA_HOT], "rack-a3", "ap-southeast-3a", "10.0.3.31"),
            ("node-dh02", "es-data-hot-02", [NodeRole.DATA_HOT], "rack-b3", "ap-southeast-3b", "10.0.3.32"),
            ("node-dh03", "es-data-hot-03", [NodeRole.DATA_HOT], "rack-c3", "ap-southeast-3c", "10.0.3.33"),
            ("node-dw01", "es-data-warm-01", [NodeRole.DATA_WARM], "rack-a4", "ap-southeast-3a", "10.0.4.41"),
            ("node-dw02", "es-data-warm-02", [NodeRole.DATA_WARM], "rack-b4", "ap-southeast-3b", "10.0.4.42"),
        ]

        for nid, name, roles, rack, zone, ip in specs:
            self.nodes[nid] = Node(nid, name, roles, rack, zone, ip)

        # Buat index default: logs-payment-prod (3 Primaries, 1 Replica = 6 shards total)
        self.create_index("logs-payment-prod", primary_shards=3, replica_factor=1)

    def create_index(self, name: str, primary_shards: int = 3, replica_factor: int = 1) -> None:
        idx = IndexMetadata(name=name, primary_shards=primary_shards, replica_factor=replica_factor)
        self.indices[name] = idx

        hot_nodes = [n for n in self.nodes.values() if NodeRole.DATA_HOT in n.roles and n.is_alive]
        if not hot_nodes:
            raise RuntimeError("Tidak ada hot data node tersedia untuk alokasi shard!")

        for p_id in range(primary_shards):
            # Primary Shard
            primary_node = hot_nodes[p_id % len(hot_nodes)]
            p_shard = Shard(shard_id=p_id, index_name=name, is_primary=True, node_id=primary_node.node_id)
            primary_node.shards.append(p_shard)
            self.all_shards.append(p_shard)

            # Replica Shard (Pastikan tidak berada di node & rack yang sama jika memungkinkan - Allocation Awareness)
            for r in range(replica_factor):
                candidates = [
                    n for n in hot_nodes
                    if n.node_id != primary_node.node_id and n.rack != primary_node.rack
                ]
                if not candidates:
                    candidates = [n for n in hot_nodes if n.node_id != primary_node.node_id]

                target_node = candidates[r % len(candidates)] if candidates else None
                if target_node:
                    r_shard = Shard(shard_id=p_id, index_name=name, is_primary=False, node_id=target_node.node_id)
                    target_node.shards.append(r_shard)
                else:
                    r_shard = Shard(shard_id=p_id, index_name=name, is_primary=False, node_id=None, unassigned=True)
                self.all_shards.append(r_shard)

        self.cluster_state_version += 1

    def calculate_health(self) -> Tuple[ClusterStatus, str]:
        total_primaries = [s for s in self.all_shards if s.is_primary]
        total_replicas = [s for s in self.all_shards if not s.is_primary]

        unassigned_primaries = [s for s in total_primaries if s.unassigned or not self._is_node_online(s.node_id)]
        unassigned_replicas = [s for s in total_replicas if s.unassigned or not self._is_node_online(s.node_id)]

        if unassigned_primaries:
            return ClusterStatus.RED, f"{len(unassigned_primaries)} Primary Shards unassigned/offline!"
        if unassigned_replicas:
            return ClusterStatus.YELLOW, f"{len(unassigned_replicas)} Replica Shards unassigned (Data tetap aman, redundansi berkurang)."
        return ClusterStatus.GREEN, "Semua primary dan replica shards aktif & terdistribusi normal."

    def _is_node_online(self, node_id: Optional[str]) -> bool:
        if not node_id or node_id not in self.nodes:
            return False
        return self.nodes[node_id].is_alive

    def get_master_quorum_status(self) -> Dict[str, object]:
        masters = [n for n in self.nodes.values() if NodeRole.MASTER in n.roles]
        alive_masters = [n for n in masters if n.is_alive]
        total_masters = len(masters)
        required_quorum = (total_masters // 2) + 1
        has_quorum = len(alive_masters) >= required_quorum
        return {
            "total_master_eligible": total_masters,
            "alive_masters": len(alive_masters),
            "required_quorum": required_quorum,
            "has_quorum": has_quorum,
            "elected_master": alive_masters[0].name if alive_masters else None
        }

    def simulate_ingest_pipeline(self, raw_doc: dict) -> Tuple[dict, List[str]]:
        """Simulasi eksekusi Ingest Node Processor: timestamp, geoip, lowercase."""
        steps = []
        doc = raw_doc.copy()
        steps.append("Ingest Node menerima payload mentah (HTTP REST API /_bulk)")

        # Processor 1: Set Ingest Timestamp
        doc["@timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        steps.append("Processor [set]: Menyisipkan metadata `@timestamp` UTC ISO-8601")

        # Processor 2: Lowercase email & action
        if "action" in doc:
            doc["action"] = str(doc["action"]).lower()
            steps.append("Processor [lowercase]: Normalisasi teks field `action`")

        # Processor 3: GeoIP Enrichment Simulasi
        ip = doc.get("client_ip", "103.20.18.5")
        doc["geo"] = {"country": "ID", "city": "Jakarta", "asn": "AS23947"}
        steps.append(f"Processor [geoip]: Resolusi IP {ip} -> Lat/Lon + Country [ID/Jakarta]")

        return doc, steps

    def route_document(self, index_name: str, doc_id: str) -> Tuple[int, str, List[str]]:
        """
        Rumus Elasticsearch Core Routing:
        shard = hash(_routing) % number_of_primary_shards
        """
        idx = self.indices[index_name]
        # Gunakan representasi hash deterministic (MD5 int mod N)
        hash_val = int(hashlib.md5(doc_id.encode("utf-8")).hexdigest(), 16)
        target_shard_id = hash_val % idx.primary_shards

        # Temukan primary node untuk shard tersebut
        primary_shard = next(
            s for s in self.all_shards
            if s.index_name == index_name and s.shard_id == target_shard_id and s.is_primary
        )
        p_node = self.nodes[primary_shard.node_id] if primary_shard.node_id else None

        # Temukan replica nodes
        replica_shards = [
            s for s in self.all_shards
            if s.index_name == index_name and s.shard_id == target_shard_id and not s.is_primary
        ]
        r_nodes = [self.nodes[r.node_id].name for r in replica_shards if r.node_id and self.nodes[r.node_id].is_alive]

        # Naikkan doc count
        primary_shard.doc_count += 1
        for r in replica_shards:
            r.doc_count += 1

        return target_shard_id, (p_node.name if p_node else "UNASSIGNED"), r_nodes

    def simulate_node_crash(self, node_id: str) -> List[str]:
        events = []
        if node_id not in self.nodes:
            events.append(f"Node {node_id} tidak ditemukan.")
            return events

        target_node = self.nodes[node_id]
        if not target_node.is_alive:
            events.append(f"Node {target_node.name} sudah dalam keadaan mati.")
            return events

        target_node.is_alive = False
        events.append(f"Node '{target_node.name}' ({target_node.ip}) TERPUTUS dari cluster!")

        # Shard promotion logic
        for shard in self.all_shards:
            if shard.node_id == node_id:
                if shard.is_primary:
                    events.append(f"Primary Shard [{shard.index_name}][{shard.shard_id}] pada {target_node.name} OFFLINE!")
                    # Cari replica yang hidup untuk dipromosikan
                    replicas = [
                        s for s in self.all_shards
                        if s.index_name == shard.index_name
                        and s.shard_id == shard.shard_id
                        and not s.is_primary
                        and self._is_node_online(s.node_id)
                    ]
                    if replicas:
                        promoted = replicas[0]
                        promoted.is_primary = True
                        shard.is_primary = False
                        shard.unassigned = True
                        shard.node_id = None
                        new_host = self.nodes[promoted.node_id].name
                        events.append(f"AUTO-PROMOTION: Replica Shard di node {new_host} dipromosikan menjadi PRIMARY!")
                    else:
                        shard.unassigned = True
                        shard.node_id = None
                        events.append(f"KRITIKAL: Tidak ada replica hidup! Shard [{shard.index_name}][{shard.shard_id}] UNASSIGNED!")
                else:
                    shard.unassigned = True
                    shard.node_id = None
                    events.append(f"Replica Shard [{shard.index_name}][{shard.shard_id}] hilang. Status degradasi.")

        self.cluster_state_version += 1
        return events

    def recover_node(self, node_id: str) -> List[str]:
        events = []
        if node_id not in self.nodes:
            events.append(f"Node {node_id} tidak dikenal.")
            return events

        node = self.nodes[node_id]
        if node.is_alive:
            events.append(f"Node {node.name} sudah online.")
            return events

        node.is_alive = True
        events.append(f"Node '{node.name}' berhasil pulih dan bergabung kembali via transport ping.")

        # Re-assign unassigned replicas back to node
        for shard in self.all_shards:
            if shard.unassigned and not shard.is_primary:
                shard.unassigned = False
                shard.node_id = node.node_id
                events.append(f"Shard Allocation Manager: Replica [{shard.index_name}][{shard.shard_id}] dialokasikan kembali ke {node.name}.")

        self.cluster_state_version += 1
        return events


# ==============================================================================
# UI & Interactive Display Views
# ==============================================================================
class ClusterDashboard:
    def __init__(self, cluster: ElasticsearchClusterSimulator):
        self.cluster = cluster

    def render_overview(self) -> None:
        health_status, reason = self.cluster.calculate_health()
        q_status = self.cluster.get_master_quorum_status()

        color_map = {
            ClusterStatus.GREEN: Color.GREEN,
            ClusterStatus.YELLOW: Color.YELLOW,
            ClusterStatus.RED: Color.RED,
        }
        st_color = color_map[health_status]

        header("ES ENTERPRISE CLUSTER DASHBOARD (PRODUCTION TOPOLOGY)")
        print(f" Cluster Name : {Color.BOLD}{self.cluster.cluster_name}{Color.RESET}")
        print(f" State Version: v{self.cluster.cluster_state_version} | Status: {st_color}{Color.BOLD}[{health_status.value}]{Color.RESET} - {reason}")
        print(f" Quorum Status: {'PASS' if q_status['has_quorum'] else 'FAIL'} (Master Aktif: {q_status['alive_masters']}/{q_status['total_master_eligible']} | Minimal: {q_status['required_quorum']})")
        print(f" Elected Master: {Color.MAGENTA}{q_status['elected_master'] or 'NONE (NO QUORUM)'}{Color.RESET}")

        print(f"\n{Color.BOLD}{'NODE ID':<12} {'NAME':<18} {'IP ADDR':<14} {'ZONE/RACK':<20} {'ROLES':<20} {'STATE':<10}{Color.RESET}")
        print("─" * 96)
        for n in self.cluster.nodes.values():
            state_str = f"{Color.GREEN}ONLINE{Color.RESET}" if n.is_alive else f"{Color.RED}OFFLINE{Color.RESET}"
            rack_zone = f"{n.zone}/{n.rack}"
            print(f"{n.node_id:<12} {n.name:<18} {n.ip:<14} {rack_zone:<20} {n.role_str:<20} {state_str:<10}")

    def render_shard_allocation(self, index_name: str = "logs-payment-prod") -> None:
        subheader(f"Tabel Alokasi Shard Index: `{index_name}` (Shard Routing & HA Placement)")
        print(f"{Color.BOLD}{'SHARD #':<10} {'TIPE':<12} {'NODE PENAMPUNG':<20} {'DOCS':<8} {'STATUS':<12}{Color.RESET}")
        print("─" * 65)

        shards = [s for s in self.cluster.all_shards if s.index_name == index_name]
        shards.sort(key=lambda x: (x.shard_id, not x.is_primary))

        for s in shards:
            stype = f"{Color.CYAN}PRIMARY{Color.RESET}" if s.is_primary else f"{Color.WHITE}REPLICA{Color.RESET}"
            if s.unassigned:
                host_node = f"{Color.RED}UNASSIGNED{Color.RESET}"
                status = f"{Color.RED}UNASSIGNED{Color.RESET}"
            else:
                node = self.cluster.nodes.get(s.node_id or "")
                host_node = node.name if (node and node.is_alive) else f"{Color.RED}DEAD HOST{Color.RESET}"
                status = f"{Color.GREEN}STARTED{Color.RESET}" if (node and node.is_alive) else f"{Color.RED}OFFLINE{Color.RESET}"

            print(f"[{s.shard_id}]       {stype:<21} {host_node:<29} {s.doc_count:<8} {status:<12}")

    def run_interactive(self) -> None:
        while True:
            self.render_overview()
            self.render_shard_allocation()

            print(f"\n{Color.CYAN}{Color.BOLD}PILASAN SIMULASI ARSITEKTUR:{Color.RESET}")
            print(" [1] Simulasi Dokumen Masuk (Ingest Node Pipeline -> Hash Routing -> Shard Primary/Replica)")
            print(" [2] Simulasi Network Partition / Failover (Matikan Data Hot Node)")
            print(" [3] Simulasi Split-Brain / Quorum Stress (Matikan Master Nodes)")
            print(" [4] Pemulihan Node (Node Recovery & Shard Re-allocation)")
            print(" [5] Jalankan Diagnostic Benchmark Otomatis")
            print(" [0] Keluar dari Lab")

            try:
                choice = input(f"\n{Color.YELLOW}Pilih skenario [0-5]: {Color.RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{Color.CYAN}Lab dihentikan.{Color.RESET}")
                break

            if choice == "0":
                print(f"{Color.GREEN}Terima kasih telah menjalankan simulasi arsitektur Elasticsearch!{Color.RESET}")
                break
            elif choice == "1":
                self.interactive_ingest()
            elif choice == "2":
                self.interactive_data_node_crash()
            elif choice == "3":
                self.interactive_master_quorum_test()
            elif choice == "4":
                self.interactive_recover_node()
            elif choice == "5":
                self.run_automated_benchmark()
            else:
                warning("Pilihan tidak valid, silakan masukkan nomor 0 sampai 5.")

            input(f"\n{Color.DIM}Tekan [ENTER] untuk melanjutkan...{Color.RESET}")

    def interactive_ingest(self) -> None:
        subheader("Simulasi Ingestion Workflow (End-to-End)")
        doc_id = f"tx_{random.randint(100000, 999999)}"
        raw_payload = {
            "order_id": doc_id,
            "user_id": f"usr_{random.randint(1, 500)}",
            "amount": round(random.uniform(50000, 2500000), 2),
            "currency": "IDR",
            "action": "CHECKOUT_COMPLETED",
            "client_ip": "103.20.18.5"
        }

        print(f"\n1. Coordinating Node menerima HTTP POST dari gateway:")
        print(f"{Color.DIM}{json.dumps(raw_payload, indent=2)}{Color.RESET}")

        # Ingest pipeline
        enriched, steps = self.cluster.simulate_ingest_pipeline(raw_payload)
        print("\n2. Ingest Node Pre-processing Engine:")
        for st in steps:
            print(f"   {Color.GREEN}→{Color.RESET} {st}")

        # Routing calculation
        shard_id, primary_node, replicas = self.cluster.route_document("logs-payment-prod", doc_id)
        print(f"\n3. Shard Hash Routing: hash('{doc_id}') % 3 = {Color.BOLD}Shard [{shard_id}]{Color.RESET}")
        print(f"   - Tulis Lokal ke Primary Shard di : {Color.GREEN}{primary_node}{Color.RESET}")
        print(f"   - Replikasi Sync/Async ke Replicas: {Color.CYAN}{', '.join(replicas) if replicas else 'Tidak ada'}{Color.RESET}")
        success(f"Dokumen [{doc_id}] berhasil di-index dengan aman (In-Memory Translog + Segment Memory Buffer)!")

    def interactive_data_node_crash(self) -> None:
        subheader("Simulasi Crash pada Data Node (Failover & Shard Auto-Promotion)")
        hot_nodes = [n for n in self.cluster.nodes.values() if NodeRole.DATA_HOT in n.roles and n.is_alive]
        if not hot_nodes:
            warning("Semua Hot Data Node sudah offline!")
            return

        target = hot_nodes[0]
        confirm = input(f"Matikan Data Node {Color.RED}{target.name}{Color.RESET} ({target.ip})? (y/N): ").strip().lower()
        if confirm == 'y':
            logs = self.cluster.simulate_node_crash(target.node_id)
            for log in logs:
                print(f"  {Color.YELLOW}»{Color.RESET} {log}")
            success("Simulasi crash dieksekusi. Perhatikan perubahan state shard di dashboard.")

    def interactive_master_quorum_test(self) -> None:
        subheader("Simulasi Voting Configuration & Split-Brain Quorum Protection")
        masters = [n for n in self.cluster.nodes.values() if NodeRole.MASTER in n.roles]
        alive = [n for n in masters if n.is_alive]

        print(f"Status Master Nodes Saat Ini ({len(alive)}/{len(masters)} Online):")
        for m in masters:
            st = f"{Color.GREEN}ONLINE{Color.RESET}" if m.is_alive else f"{Color.RED}OFFLINE{Color.RESET}"
            print(f" - {m.name} ({m.ip}) -> {st}")

        if len(alive) <= 1:
            warning("Master node tersisa tinggal 1! Mematikan lagi akan membuat cluster unresponsive total.")

        target = alive[0] if alive else None
        if not target:
            warning("Semua master node sudah offline! Quorum hilang.")
            return

        confirm = input(f"Matikan master node {Color.RED}{target.name}{Color.RESET}? (y/N): ").strip().lower()
        if confirm == 'y':
            target.is_alive = False
            self.cluster.cluster_state_version += 1
            warning(f"Master {target.name} dimatikan.")
            q = self.cluster.get_master_quorum_status()
            if q["has_quorum"]:
                success(f"QUORUM AMAN: Masih ada {q['alive_masters']} node aktif (Min. Quorum: {q['required_quorum']}). Baru terpilih: {q['elected_master']}")
            else:
                error(f"QUORUM HILANG! Master aktif {q['alive_masters']} < {q['required_quorum']}. Cluster menolak semua update cluster state untuk mencegah Split-Brain!")

    def interactive_recover_node(self) -> None:
        subheader("Pemulihan Node (Node Recovery)")
        dead_nodes = [n for n in self.cluster.nodes.values() if not n.is_alive]
        if not dead_nodes:
            info("Semua node dalam cluster saat ini berstatus sehat (ONLINE). Tidak ada yang perlu dipulihkan.")
            return

        print("Node yang sedang offline:")
        for idx, n in enumerate(dead_nodes, 1):
            print(f" [{idx}] {n.name} ({n.node_id}) - Roles: {n.role_str}")

        choice = input("Pilih nomor node yang ingin dihidupkan kembali (atau 'all'): ").strip().lower()
        if choice == "all":
            for n in dead_nodes:
                logs = self.cluster.recover_node(n.node_id)
                for l in logs:
                    print(f"  {Color.GREEN}»{Color.RESET} {l}")
        else:
            try:
                sel = int(choice) - 1
                if 0 <= sel < len(dead_nodes):
                    logs = self.cluster.recover_node(dead_nodes[sel].node_id)
                    for l in logs:
                        print(f"  {Color.GREEN}»{Color.RESET} {l}")
                else:
                    warning("Pilihan di luar rentang.")
            except ValueError:
                warning("Input tidak valid.")

    def run_automated_benchmark(self) -> None:
        subheader("Jalankan Diagnostic Benchmark & Architectural Health Check")
        print("Memulai pengujian integritas arsitektur Elasticsearch...")
        time.sleep(0.5)

        # Check 1: Quorum
        q = self.cluster.get_master_quorum_status()
        if q["has_quorum"]:
            success(f"[PASS] Master Quorum Check: {q['alive_masters']}/{q['total_master_eligible']} eligible nodes (Required: {q['required_quorum']})")
        else:
            error(f"[FAIL] Master Quorum Check: Cluster kekurangan quorum!")

        # Check 2: Shard Health
        health, reason = self.cluster.calculate_health()
        if health == ClusterStatus.GREEN:
            success(f"[PASS] Shard Distribution Check: Status GREEN ({reason})")
        elif health == ClusterStatus.YELLOW:
            warning(f"[WARN] Shard Distribution Check: Status YELLOW ({reason})")
        else:
            error(f"[FAIL] Shard Distribution Check: Status RED ({reason})")

        # Check 3: Ingestion Simulation
        try:
            for i in range(5):
                d_id = f"bench_doc_{i}"
                self.cluster.route_document("logs-payment-prod", d_id)
            success(f"[PASS] Bulk Ingest Routing: 5 dokumen berhasil dirutekan secara proporsional ke primary shards.")
        except Exception as e:
            error(f"[FAIL] Ingest Simulation error: {e}")

        # Check 4: Allocation Awareness
        print("\nMemeriksa aturan Zone/Rack Allocation Awareness...")
        violations = 0
        for shard_id in range(3):
            assigned = [
                s for s in self.cluster.all_shards
                if s.index_name == "logs-payment-prod" and s.shard_id == shard_id and not s.unassigned
            ]
            racks = [self.cluster.nodes[s.node_id].rack for s in assigned if s.node_id]
            if len(racks) != len(set(racks)):
                violations += 1

        if violations == 0:
            success("[PASS] Allocation Awareness: Tidak ada primary dan replica dari shard yang sama berada di satu rack.")
        else:
            warning(f"[WARN] Allocation Awareness: Terdeteksi {violations} shard berbagi rack yang sama!")

        info("Benchmark selesai.")


# ==============================================================================
# Main Entry Point
# ==============================================================================
def main():
    cluster = ElasticsearchClusterSimulator()
    dashboard = ClusterDashboard(cluster)

    if "--non-interactive" in sys.argv or "--benchmark" in sys.argv:
        dashboard.render_overview()
        dashboard.render_shard_allocation()
        dashboard.run_automated_benchmark()
        return

    dashboard.run_interactive()


if __name__ == "__main__":
    main()
