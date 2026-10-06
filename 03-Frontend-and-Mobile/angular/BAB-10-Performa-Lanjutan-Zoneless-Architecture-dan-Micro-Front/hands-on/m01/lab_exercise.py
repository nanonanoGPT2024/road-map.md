#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Angular Zoneless Architecture & Micro-Frontend
Topik: BAB 10 - Performa Lanjutan, Zoneless Architecture, & Micro-Frontend
"""

import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

# --- ANSI Color Codes ---
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
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"

def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}================================================================================
  ANGULAR ADVANCED ENGINE: ZONELESS ARCHITECTURE & MICRO-FRONTEND SIMULATOR
  Bab 10: Performa Lanjutan, Zoneless (Signals) & Native Module Federation
================================================================================{Color.RESET}
"""
    print(banner)

# --- Sub-Sistem 1: Zone.js vs Zoneless Signal Reactive Scheduler ---

class ChangeDetectionMode(Enum):
    DEFAULT_ZONE = "ZoneJS_Default_TreeTraversal"
    ON_PUSH = "ZoneJS_OnPush"
    ZONELESS_SIGNAL = "Zoneless_SignalDriven"

@dataclass
class ComponentNode:
    id: str
    name: str
    mode: ChangeDetectionMode
    children: List['ComponentNode'] = field(default_factory=list)
    is_dirty: bool = False
    renders_count: int = 0
    signal_dependencies: Set[str] = field(default_factory=set)

    def mark_dirty(self):
        self.is_dirty = True

    def render(self):
        self.renders_count += 1
        self.is_dirty = False

class ZonelessScheduler:
    def __init__(self):
        self._dirty_nodes: Set[str] = set()
        self._microtask_scheduled = False

    def schedule_notify(self, node: ComponentNode):
        self._dirty_nodes.add(node.id)

    def flush(self, nodes_map: Dict[str, ComponentNode]) -> int:
        renders = 0
        for node_id in list(self._dirty_nodes):
            node = nodes_map.get(node_id)
            if node and node.is_dirty:
                node.render()
                renders += 1
        self._dirty_nodes.clear()
        return renders

def build_sample_tree(mode: ChangeDetectionMode) -> Dict[str, ComponentNode]:
    nodes = {
        "app": ComponentNode("app", "AppComponent (Root)", mode),
        "header": ComponentNode("header", "HeaderComponent", mode),
        "catalog": ComponentNode("catalog", "ProductCatalogComponent", mode),
        "item_a": ComponentNode("item_a", "ProductCardComponent (Item A)", mode),
        "item_b": ComponentNode("item_b", "ProductCardComponent (Item B)", mode),
        "cart_badge": ComponentNode("cart_badge", "CartBadgeComponent", mode),
    }
    nodes["app"].children = [nodes["header"], nodes["catalog"]]
    nodes["header"].children = [nodes["cart_badge"]]
    nodes["catalog"].children = [nodes["item_a"], nodes["item_b"]]
    
    # Wire signals dependency
    nodes["cart_badge"].signal_dependencies.add("cart_count")
    nodes["item_a"].signal_dependencies.add("item_a_qty")
    return nodes

def run_dirty_check_zone_default(root: ComponentNode) -> int:
    """Simulasi Zone.js Default: seluruh komponen dalam pohon diperiksa (Top-Down dirty check)."""
    checks = 1
    root.render()
    for child in root.children:
        checks += run_dirty_check_zone_default(child)
    return checks

def simulate_zoneless_vs_zone():
    print(f"\n{Color.YELLOW}{Color.BOLD}>>> [1] Simulasi: Zone.js Full Tree Check vs Zoneless Fine-Grained Signals{Color.RESET}")
    print(f"{Color.DIM}Event: User klik 'Add To Cart' pada Item A -> memicu update signal 'cart_count'.{Color.RESET}\n")

    # 1. Zone.js Default
    tree_zone = build_sample_tree(ChangeDetectionMode.DEFAULT_ZONE)
    start_t = time.perf_counter()
    zone_checks = run_dirty_check_zone_default(tree_zone["app"])
    dur_zone_ms = (time.perf_counter() - start_t) * 1000

    print(f"{Color.RED}[Legacy Zone.js Default]{Color.RESET}")
    print(f" - Mekanisme      : Intercept macro/microtask (Zone.run), cek dirty-checking top-down")
    print(f" - Komponen dicek : {Color.BOLD}{zone_checks} komponen{Color.RESET} (seluruh pohon app dicek ulang)")
    print(f" - Overheads      : Zone monkey-patching microtask/requestAnimationFrame, DOM traverse tinggi\n")

    # 2. Zoneless Signal Driven
    tree_zoneless = build_sample_tree(ChangeDetectionMode.ZONELESS_SIGNAL)
    scheduler = ZonelessScheduler()
    
    # Mutasi signal cart_count
    target = tree_zoneless["cart_badge"]
    target.mark_dirty()
    scheduler.schedule_notify(target)

    start_t = time.perf_counter()
    zoneless_renders = scheduler.flush(tree_zoneless)
    dur_zoneless_ms = (time.perf_counter() - start_t) * 1000

    print(f"{Color.GREEN}[Angular Zoneless + Signals (provideExperimentalZonelessChangeDetection)]{Color.RESET}")
    print(f" - Mekanisme      : Reactive dependency graph (Producer -> Consumer notification)")
    print(f" - Komponen dicek : {Color.BOLD}{zoneless_renders} komponen terpilih{Color.RESET} ({target.name})")
    print(f" - Keuntungan     : Zero Zone.js bundle cost (~13KB gzipped), no monkey-patching, instant rendering")
    reduction = ((zone_checks - zoneless_renders) / zone_checks) * 100
    print(f" - {Color.CYAN}Efisiensi Operasi CD: Turun {reduction:.1f}% check cycles!{Color.RESET}\n")

# --- Sub-Sistem 2: @defer (Deferrable Views) Lifecycle Simulation ---

class DeferState(Enum):
    PLACEHOLDER = "Placeholder (Static HTML)"
    LOADING = "Loading (Chunk Downloading...)"
    RESOLVED = "Resolved (Component Rendered)"
    ERROR = "Error / Fallback"

@dataclass
class DeferrableBlock:
    name: str
    trigger: str
    prefetch_trigger: str
    chunk_size_kb: float
    state: DeferState = DeferState.PLACEHOLDER
    is_prefetched: bool = False

    def simulate_trigger(self, event: str):
        print(f"  [Event Emitted] '{event}' diterima oleh block '{self.name}'")
        if not self.is_prefetched and "prefetch" in event:
            print(f"  {Color.BLUE}-> Memulai download background chunk ({self.chunk_size_kb} KB)...{Color.RESET}")
            time.sleep(0.3)
            self.is_prefetched = True
            print(f"  {Color.GREEN}-> Chunk berhasil di-prefetch dan disimpan di cache browser!{Color.RESET}")
            return

        if "trigger" in event:
            if not self.is_prefetched:
                self.state = DeferState.LOADING
                print(f"  {Color.YELLOW}-> State: {self.state.value} (Mengunduh chunk on-the-fly)...{Color.RESET}")
                time.sleep(0.4)
            else:
                print(f"  {Color.CYAN}-> Chunk sudah tersedia di cache, swap DOM instan!{Color.RESET}")
            self.state = DeferState.RESOLVED
            print(f"  {Color.GREEN}{Color.BOLD}-> State Akhir: {self.state.value}{Color.RESET}")

def simulate_deferrable_views():
    print(f"\n{Color.YELLOW}{Color.BOLD}>>> [2] Simulasi: @defer Deferrable Views Lifecycle Optimization{Color.RESET}")
    print(f"{Color.DIM}Template: @defer (on viewport; prefetch on idle) {{ <heavy-chart /> }} @placeholder {{ ... }} @loading {{ ... }}{Color.RESET}\n")

    block = DeferrableBlock(
        name="AnalyticsChartComponent",
        trigger="on viewport (scroll to section)",
        prefetch_trigger="on idle (browser idle callback)",
        chunk_size_kb=142.5
    )

    print(f"Status Awal: {Color.MAGENTA}{block.state.value}{Color.RESET}")
    print("Skenario: Idle browser mendeteksi CPU nganggur -> prefetch chunk.")
    block.simulate_trigger("idle prefetch")
    
    print("\nSkenario: User melakukan scroll dan komponen masuk ke viewport window.")
    block.simulate_trigger("viewport trigger")
    print(f"\n{Color.GREEN}Hasil: TBT (Total Blocking Time) berkurang drastis karena bundle dipartisi.{Color.RESET}\n")

# --- Sub-Sistem 3: Micro-Frontend Native Module Federation Container ---

@dataclass
class SharedPackage:
    name: str
    required_version: str
    loaded_version: Optional[str] = None
    is_singleton: bool = True

@dataclass
class RemoteManifest:
    remote_name: str
    exposed_module: str
    bundle_url: str
    shared_deps: Dict[str, str]

class ModuleFederationHost:
    def __init__(self, host_name: str):
        self.host_name = host_name
        self.shared_scope: Dict[str, SharedPackage] = {
            "@angular/core": SharedPackage("@angular/core", "^18.0.0", "18.2.0", is_singleton=True),
            "@angular/common": SharedPackage("@angular/common", "^18.0.0", "18.2.0", is_singleton=True),
            "rxjs": SharedPackage("rxjs", "^7.8.0", "7.8.1", is_singleton=True),
        }
        self.mounted_remotes: Dict[str, RemoteManifest] = {}

    def negotiate_dependencies(self, remote: RemoteManifest) -> bool:
        print(f"  {Color.CYAN}[Federation Share Scope Handshake]{Color.RESET} Remote: '{remote.remote_name}'")
        for pkg_name, req_ver in remote.shared_deps.items():
            if pkg_name in self.shared_scope:
                host_pkg = self.shared_scope[pkg_name]
                print(f"    - Dep: {pkg_name} | Dibutuhkan: {req_ver} | Disediakan Host: {host_pkg.loaded_version}")
                if host_pkg.is_singleton:
                    print(f"      {Color.GREEN}✓ Singleton reuse: Remote akan memakai instance memori host.{Color.RESET}")
            else:
                print(f"    - Dep: {pkg_name} | {Color.YELLOW}! Tidak ada di host scope, remote mengunduh fallback bundle.{Color.RESET}")
        return True

    def load_remote_entry(self, remote: RemoteManifest):
        print(f"\nMemuat Remote Entry: {Color.BOLD}{remote.remote_name}{Color.RESET} dari {remote.bundle_url}...")
        time.sleep(0.2)
        if self.negotiate_dependencies(remote):
            self.mounted_remotes[remote.remote_name] = remote
            print(f"{Color.GREEN}{Color.BOLD}✓ Remote '{remote.remote_name}' mounted berhasil pada route '/{remote.remote_name}'!{Color.RESET}")

def simulate_micro_frontends():
    print(f"\n{Color.YELLOW}{Color.BOLD}>>> [3] Simulasi: Micro-Frontend Module Federation & Runtime Resolution{Color.RESET}")
    print(f"{Color.DIM}Arsitektur: Shell (Host) memuat remote micro-apps secara independen tanpa duplicate shared libraries.{Color.RESET}\n")

    host = ModuleFederationHost("AngularShellHost")

    remote_checkout = RemoteManifest(
        remote_name="mfe_checkout",
        exposed_module="./CheckoutModule",
        bundle_url="https://cdn.corp.internal/mfe/checkout/remoteEntry.json",
        shared_deps={
            "@angular/core": "^18.0.0",
            "@angular/common": "^18.0.0",
            "rxjs": "^7.8.0"
        }
    )

    remote_payment = RemoteManifest(
        remote_name="mfe_payment_gateway",
        exposed_module="./PaymentWidget",
        bundle_url="https://cdn.corp.internal/mfe/payment/remoteEntry.json",
        shared_deps={
            "@angular/core": "^18.0.0",
            "stripe-js": "^3.0.0"
        }
    )

    host.load_remote_entry(remote_checkout)
    host.load_remote_entry(remote_payment)

    print(f"\n{Color.CYAN}Total Micro-Frontends Aktif di Shell Host: {len(host.mounted_remotes)}{Color.RESET}")
    for k, v in host.mounted_remotes.items():
        print(f" - [{k}] Exposing: {v.exposed_module}")

# --- Interactive Terminal Loop ---

def show_menu():
    print(f"""
{Color.BOLD}PILIH DEMO SIMULASI INTERAKTIF:{Color.RESET}
  {Color.CYAN}[1]{Color.RESET} Benchmark: Zone.js Full CD vs Angular Zoneless (Signals)
  {Color.CYAN}[2]{Color.RESET} Simulasi: Deferrable Views (@defer, @placeholder, @loading)
  {Color.CYAN}[3]{Color.RESET} Simulasi: Micro-Frontend Native Federation & Shared Scopes
  {Color.CYAN}[4]{Color.RESET} Jalankan Seluruh Pengujian Sekaligus
  {Color.RED}[0]{Color.RESET} Keluar
""")

def interactive_session():
    print_banner()
    while True:
        show_menu()
        try:
            choice = input(f"{Color.BOLD}Masukkan pilihan (0-4): {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSesi selesai.")
            break

        if choice == "1":
            simulate_zoneless_vs_zone()
        elif choice == "2":
            simulate_deferrable_views()
        elif choice == "3":
            simulate_micro_frontends()
        elif choice == "4":
            simulate_zoneless_vs_zone()
            simulate_deferrable_views()
            simulate_micro_frontends()
        elif choice == "0":
            print(f"\n{Color.GREEN}Terima kasih! Lab Zoneless & Micro-Frontend selesai.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}")

if __name__ == "__main__":
    interactive_session()
