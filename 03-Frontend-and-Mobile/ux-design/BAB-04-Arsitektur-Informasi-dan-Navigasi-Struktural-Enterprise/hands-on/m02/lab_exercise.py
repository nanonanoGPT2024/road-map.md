#!/usr/bin/env python3
"""
Enterprise Information Architecture & Structural Navigation Engine
BAB-04: Arsitektur Informasi dan Navigasi Struktural Enterprise
Module 02 Hands-on Lab Exercise

Simulasi interaktif arsitektur informasi bertingkat (Taxonomy, Ontology, 
Breadcrumbs, Faceted Search, Cross-linking, dan RBAC Wayfinding).
"""

import sys
import json
import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field

# ==============================================================================
# ANSI Color Formatting & Terminal Helpers
# ==============================================================================
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # High-intensity Foreground
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    
    # Background
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def header(text: str) -> str:
    line = "=" * 70
    return f"{Colors.BRIGHT_BLUE}{line}\n{Colors.BOLD}{Colors.WHITE} {text.upper()}\n{Colors.BRIGHT_BLUE}{line}{Colors.RESET}"


def subheader(text: str) -> str:
    return f"\n{Colors.CYAN}{Colors.BOLD}--- {text} ---{Colors.RESET}"


def info_badge(tag: str, msg: str, color: str = Colors.GREEN) -> str:
    return f"{color}[{tag}]{Colors.RESET} {msg}"


# ==============================================================================
# Enterprise Information Architecture Core Data Structures
# ==============================================================================
@dataclass
class TaxonomyNode:
    node_id: str
    label: str
    depth: int
    required_roles: Set[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    facets: Dict[str, str] = field(default_factory=dict)
    related_nodes: List[str] = field(default_factory=list)  # Polyhierarchical links / Ontology


class EnterpriseInformationArchitecture:
    """
    Core Enterprise IA Engine:
    - Hierarchical Taxonomy (Tree with depth validation)
    - Polyhierarchy & Associative Links (Cross-cutting ontology)
    - Role-Based Wayfinding & Access Filtering (RBAC)
    - Faceted Search & Retrieval Engine
    - Dynamic Breadcrumb Path Generation
    """

    def __init__(self):
        self.nodes: Dict[str, TaxonomyNode] = {}
        self.root_id: str = "root"
        self._build_enterprise_topology()

    def _build_enterprise_topology(self):
        # Level 0: Enterprise Root
        self.add_node(
            node_id="root",
            label="Enterprise Global Portal",
            depth=0,
            required_roles={"viewer", "analyst", "operator", "admin"},
            parent_id=None,
            facets={"domain": "global", "confidentiality": "public"}
        )

        # Level 1: Core Business Units
        self.add_node(
            node_id="fintech",
            label="Fintech & Treasury Core",
            depth=1,
            required_roles={"analyst", "admin"},
            parent_id="root",
            facets={"domain": "finance", "compliance": "pci-dss", "tier": "tier-1"}
        )
        self.add_node(
            node_id="ops",
            label="Operations & Logistics",
            depth=1,
            required_roles={"operator", "admin"},
            parent_id="root",
            facets={"domain": "supply-chain", "compliance": "iso-9001", "tier": "tier-2"}
        )
        self.add_node(
            node_id="security",
            label="Cybersecurity Governance",
            depth=1,
            required_roles={"admin"},
            parent_id="root",
            facets={"domain": "infosec", "compliance": "soc2", "tier": "tier-1"}
        )

        # Level 2: Sub-domains under Fintech
        self.add_node(
            node_id="settlements",
            label="Real-time Gross Settlements (RTGS)",
            depth=2,
            required_roles={"analyst", "admin"},
            parent_id="fintech",
            facets={"domain": "finance", "compliance": "pci-dss", "status": "active"},
            related_nodes=["audit_trails"]
        )
        self.add_node(
            node_id="forex",
            label="Forex Hedging & FX Liquidity",
            depth=2,
            required_roles={"analyst", "admin"},
            parent_id="fintech",
            facets={"domain": "finance", "compliance": "basel-iii", "status": "active"}
        )

        # Level 2: Sub-domains under Operations
        self.add_node(
            node_id="fleet",
            label="Fleet Tracking & Telematics",
            depth=2,
            required_roles={"operator", "admin"},
            parent_id="ops",
            facets={"domain": "supply-chain", "telemetry": "iot", "status": "active"}
        )
        self.add_node(
            node_id="warehousing",
            label="Automated Storage & Retrieval (ASRS)",
            depth=2,
            required_roles={"operator", "admin"},
            parent_id="ops",
            facets={"domain": "supply-chain", "telemetry": "rfid", "status": "active"}
        )

        # Level 2: Sub-domains under Cybersecurity
        self.add_node(
            node_id="audit_trails",
            label="Immutable Security Ledger & SIEM",
            depth=2,
            required_roles={"admin"},
            parent_id="security",
            facets={"domain": "infosec", "compliance": "soc2", "status": "restricted"},
            related_nodes=["settlements"]
        )
        self.add_node(
            node_id="identity_mgr",
            label="Zero-Trust IAM & Privilege Vault",
            depth=2,
            required_roles={"admin"},
            parent_id="security",
            facets={"domain": "infosec", "compliance": "zero-trust", "status": "restricted"}
        )

        # Level 3: Deep Technical Nodes
        self.add_node(
            node_id="rtgs_engine",
            label="Payment Orchestration Engine v4",
            depth=3,
            required_roles={"admin"},
            parent_id="settlements",
            facets={"domain": "finance", "latency": "ultra-low", "engine": "grpc"}
        )
        self.add_node(
            node_id="iot_gateway",
            label="Edge Broker MQTT Fleet Core",
            depth=3,
            required_roles={"operator", "admin"},
            parent_id="fleet",
            facets={"domain": "supply-chain", "latency": "standard", "engine": "mqtt"}
        )

    def add_node(
        self,
        node_id: str,
        label: str,
        depth: int,
        required_roles: Set[str],
        parent_id: Optional[str] = None,
        facets: Optional[Dict[str, str]] = None,
        related_nodes: Optional[List[str]] = None
    ):
        node = TaxonomyNode(
            node_id=node_id,
            label=label,
            depth=depth,
            required_roles=required_roles,
            metadata={"created_at": time.time()},
            children=[],
            parent_id=parent_id,
            facets=facets or {},
            related_nodes=related_nodes or []
        )
        self.nodes[node_id] = node
        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id].children.append(node_id)

    def resolve_breadcrumbs(self, current_node_id: str, user_role: str) -> List[Dict[str, str]]:
        """Menghasilkan jejak navigasi (breadcrumbs) berurutan dari root."""
        crumbs = []
        curr = current_node_id

        while curr is not None:
            if curr not in self.nodes:
                break
            node = self.nodes[curr]
            accessible = user_role in node.required_roles
            crumbs.insert(0, {
                "id": node.node_id,
                "label": node.label,
                "accessible": accessible,
                "depth": node.depth
            })
            curr = node.parent_id

        return crumbs

    def filter_tree_by_role(self, node_id: str, user_role: str) -> Optional[Dict[str, Any]]:
        """Wayfinding pruning: hanya menampilkan pohon yang diizinkan untuk role terkait."""
        node = self.nodes.get(node_id)
        if not node:
            return None

        # Evaluasi akses RBAC
        has_access = user_role in node.required_roles
        accessible_children = []

        for child_id in node.children:
            subtree = self.filter_tree_by_role(child_id, user_role)
            if subtree:
                accessible_children.append(subtree)

        # Tampilkan jika memiliki akses langsung atau merupakan kontainer anak yang diizinkan
        if has_access or accessible_children:
            return {
                "id": node.node_id,
                "label": node.label,
                "depth": node.depth,
                "has_direct_access": has_access,
                "children": accessible_children,
                "facets": node.facets,
                "related": node.related_nodes
            }
        return None

    def faceted_query(self, filters: Dict[str, str], user_role: str) -> List[TaxonomyNode]:
        """Pencarian multi-dimensi (Faceted Taxonomy Search) dengan filter aksesibilitas."""
        matched = []
        for node in self.nodes.values():
            if user_role not in node.required_roles:
                continue
            
            match = True
            for k, v in filters.items():
                if node.facets.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(node)
        return matched


# ==============================================================================
# Interactive Terminal Simulation Dashboard
# ==============================================================================
class SimulationRunner:
    def __init__(self):
        self.ia = EnterpriseInformationArchitecture()
        self.current_role = "viewer"
        self.current_location = "root"

    def print_banner(self):
        print(header("Enterprise Information Architecture (IA) Simulation Suite"))
        print(f"{Colors.DIM}Standard ISO/IEC 23950 & Rosenfeld-Morville Enterprise IA Reference Model{Colors.RESET}")
        print(f"{Colors.YELLOW}Peran Pengguna Saat Ini: {Colors.BOLD}{self.current_role.upper()}{Colors.RESET}")
        print(f"{Colors.CYAN}Lokasi Simpul Navigasi: {Colors.BOLD}{self.ia.nodes[self.current_location].label}{Colors.RESET}\n")

    def display_breadcrumbs(self):
        crumbs = self.ia.resolve_breadcrumbs(self.current_location, self.current_role)
        trail = []
        for crumb in crumbs:
            if crumb["accessible"]:
                trail.append(f"{Colors.BRIGHT_GREEN}{crumb['label']}{Colors.RESET}")
            else:
                trail.append(f"{Colors.RED}[LOCKED: {crumb['label']}]{Colors.RESET}")
        
        breadcrumb_str = f" {Colors.WHITE}> {Colors.RESET}".join(trail)
        print(f"{Colors.BOLD}Navigational Breadcrumbs:{Colors.RESET} {breadcrumb_str}")

    def render_tree(self, subtree: Dict[str, Any], indent: str = "", is_last: bool = True):
        marker = "└── " if is_last else "├── "
        direct = subtree["has_direct_access"]
        
        if direct:
            status_symbol = f"{Colors.GREEN}●{Colors.RESET}"
            title = f"{Colors.WHITE}{Colors.BOLD}{subtree['label']}{Colors.RESET}"
        else:
            status_symbol = f"{Colors.RED}○ [Restricted Parent]{Colors.RESET}"
            title = f"{Colors.DIM}{subtree['label']}{Colors.RESET}"

        facet_desc = f" {Colors.DIM}({subtree['facets']}){Colors.RESET}" if subtree['facets'] else ""
        print(f"{indent}{marker}{status_symbol} [{subtree['id']}] {title}{facet_desc}")

        next_indent = indent + ("    " if is_last else "│   ")
        children = subtree["children"]
        for i, child in enumerate(children):
            self.render_tree(child, next_indent, is_last=(i == len(children) - 1))

    def switch_role(self, role: str):
        valid_roles = ["viewer", "analyst", "operator", "admin"]
        if role.lower() in valid_roles:
            self.current_role = role.lower()
            print(info_badge("AUTH", f"Konteks keamanan diganti ke: {self.current_role.upper()}", Colors.BRIGHT_GREEN))
            # Fallback jika posisi saat ini tidak lagi accessible
            curr_node = self.ia.nodes.get(self.current_location)
            if curr_node and self.current_role not in curr_node.required_roles:
                print(info_badge("GUARD", f"Akses ke '{curr_node.label}' dicabut. Memindahkan ke 'root'.", Colors.YELLOW))
                self.current_location = "root"
        else:
            print(info_badge("ERROR", f"Role '{role}' tidak valid. Pilihan: {valid_roles}", Colors.RED))

    def navigate_to(self, node_id: str):
        if node_id not in self.ia.nodes:
            print(info_badge("FAIL", f"Node '{node_id}' tidak ditemukan dalam taksonomi.", Colors.RED))
            return

        target_node = self.ia.nodes[node_id]
        if self.current_role not in target_node.required_roles:
            print(info_badge("ACCESS_DENIED", f"Role '{self.current_role}' dilarang mengakses '{target_node.label}'.", Colors.RED))
            print(f"{Colors.DIM}Dibutuhkan salah satu role: {list(target_node.required_roles)}{Colors.RESET}")
            return

        self.current_location = node_id
        print(info_badge("NAVIGATE", f"Berpindah ke: {target_node.label} [Depth: {target_node.depth}]", Colors.BRIGHT_BLUE))

    def run_faceted_search_demo(self):
        print(subheader("Simulasi Faceted Search (Multi-kriteria)"))
        print("Mencari simpul dengan kriteria: domain='finance'")
        results = self.ia.faceted_query({"domain": "finance"}, self.current_role)
        print(f"Hasil ditemukan untuk role {self.current_role.upper()} ({len(results)} item):")
        for node in results:
            print(f"  - {Colors.BRIGHT_CYAN}{node.label}{Colors.RESET} ({node.node_id}) | Facets: {node.facets}")

        print("\nMencari simpul dengan kriteria: compliance='soc2'")
        results_soc2 = self.ia.faceted_query({"compliance": "soc2"}, self.current_role)
        print(f"Hasil ditemukan untuk role {self.current_role.upper()} ({len(results_soc2)} item):")
        for node in results_soc2:
            print(f"  - {Colors.BRIGHT_YELLOW}{node.label}{Colors.RESET} ({node.node_id}) | Facets: {node.facets}")

    def inspect_current_node(self):
        node = self.ia.nodes[self.current_location]
        print(subheader(f"Detail Simpul: {node.label}"))
        print(f"{Colors.BOLD}ID:{Colors.RESET} {node.node_id}")
        print(f"{Colors.BOLD}Level Taksonomi (Depth):{Colors.RESET} {node.depth}")
        print(f"{Colors.BOLD}Parent Node:{Colors.RESET} {node.parent_id or 'None (Root Enterprise)'}")
        print(f"{Colors.BOLD}Sub-kategori Terdaftar ({len(node.children)}):{Colors.RESET} {node.children}")
        print(f"{Colors.BOLD}Facet & Taksonomi Metadata:{Colors.RESET} {json.dumps(node.facets, indent=2)}")
        
        if node.related_nodes:
            print(f"{Colors.BOLD}Ontologi & Polyhierarchical Links (Cross-cutting):{Colors.RESET}")
            for rel in node.related_nodes:
                rel_node = self.ia.nodes.get(rel)
                label = rel_node.label if rel_node else rel
                print(f"  -> Hubungan Asosiatif: {Colors.MAGENTA}{label}{Colors.RESET} (ID: {rel})")

    def run_full_diagnostic(self):
        print(subheader("Diagnostik Arsitektur Informasi & Integritas Navigasi"))
        total_nodes = len(self.ia.nodes)
        max_depth = max(n.depth for n in self.ia.nodes.values())
        poly_links = sum(len(n.related_nodes) for n in self.ia.nodes.values())

        print(f"1. Total Entitas Taksonomi       : {Colors.BOLD}{total_nodes}{Colors.RESET}")
        print(f"2. Kedalaman Maksimum (Max Depth): {Colors.BOLD}{max_depth}{Colors.RESET} (Optimal UX Enterprise <= 4)")
        print(f"3. Relasi Asosiatif / Polyarchy : {Colors.BOLD}{poly_links}{Colors.RESET}")
        
        # Deteksi orphan nodes
        orphans = [nid for nid, n in self.ia.nodes.items() if n.parent_id is None and nid != self.ia.root_id]
        if orphans:
            print(info_badge("WARN", f"Ditemukan orphan nodes: {orphans}", Colors.RED))
        else:
            print(info_badge("PASS", "Integritas Struktural: Pohon taksonomi terhubung sempurna.", Colors.GREEN))

        # Deteksi Cognitive Load Depth
        if max_depth > 5:
            print(info_badge("WARN", "Kedalaman melebihi standar Miller's Law / cognitive limit.", Colors.YELLOW))
        else:
            print(info_badge("PASS", "Depth memenuhi standar Navigasi Struktural Enterprise.", Colors.GREEN))


# ==============================================================================
# Main Interactive Loop
# ==============================================================================
def main():
    sim = SimulationRunner()
    
    # Auto-demonstrasi awal
    sim.print_banner()
    sim.display_breadcrumbs()
    print(subheader("Hierarki Taksonomi Sesuai Hak Akses Pengguna"))
    tree_data = sim.ia.filter_tree_by_role("root", sim.current_role)
    if tree_data:
        sim.render_tree(tree_data)

    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}PILIHAN PERINTAH SIMULASI INTERAKTIF:{Colors.RESET}")
    print(" 1. Ubah Role Pengguna    : role <viewer|analyst|operator|admin>")
    print(" 2. Navigasi ke Simpul    : nav <node_id> (misal: nav settlements)")
    print(" 3. Inspeksi Simpul Aktif : inspect")
    print(" 4. Faceted Search Demo   : search")
    print(" 5. Tampilkan Seluruh IA  : tree")
    print(" 6. Validasi Diagnostik   : diag")
    print(" 7. Keluar                : exit / quit")
    print("=" * 70)

    # Interactive Prompt
    if not sys.stdin.isatty():
        # Non-interactive / headless fallback mode (e.g. CI/CD or piped run)
        print(info_badge("SYSTEM", "Mode Headless / Automated Execution Terdeteksi.", Colors.CYAN))
        print("\n--- Uji Navigasi Role Admin ---")
        sim.switch_role("admin")
        sim.navigate_to("rtgs_engine")
        sim.display_breadcrumbs()
        sim.inspect_current_node()
        print("\n--- Eksekusi Faceted Query ---")
        sim.run_faceted_search_demo()
        print("\n--- Eksekusi Diagnostik Akhir ---")
        sim.run_full_diagnostic()
        print(info_badge("SUCCESS", "Simulasi Arsitektur Informasi Selesai 100%.", Colors.BRIGHT_GREEN))
        return

    while True:
        try:
            prompt = f"\n{Colors.BRIGHT_CYAN}[IA-Engine ({sim.current_role}) @ {sim.current_location}]> {Colors.RESET}"
            user_input = input(prompt).strip()
            if not user_input:
                continue

            parts = user_input.split()
            cmd = parts[0].lower()

            if cmd in ("exit", "quit", "q"):
                print(f"{Colors.GREEN}Sesi simulasi ditutup. Sampai jumpa!{Colors.RESET}")
                break
            elif cmd == "role" and len(parts) > 1:
                sim.switch_role(parts[1])
            elif cmd == "nav" and len(parts) > 1:
                sim.navigate_to(parts[1])
                sim.display_breadcrumbs()
            elif cmd == "inspect":
                sim.inspect_current_node()
            elif cmd == "search":
                sim.run_faceted_search_demo()
            elif cmd == "tree":
                tree_data = sim.ia.filter_tree_by_role("root", sim.current_role)
                if tree_data:
                    sim.render_tree(tree_data)
                else:
                    print(info_badge("EMPTY", "Tidak ada simpul yang dapat diakses.", Colors.RED))
            elif cmd == "diag":
                sim.run_full_diagnostic()
            else:
                print(info_badge("HELP", "Perintah tidak dikenali. Ketik 'tree', 'role <name>', 'nav <id>', 'inspect', 'search', 'diag', atau 'exit'.", Colors.YELLOW))
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.GREEN}Sesi simulasi dihentikan.{Colors.RESET}")
            break


if __name__ == "__main__":
    main()
