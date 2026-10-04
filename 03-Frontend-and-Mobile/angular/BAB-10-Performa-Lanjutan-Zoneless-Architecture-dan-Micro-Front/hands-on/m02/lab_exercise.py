#!/usr/bin/env python3
"""
Lab Hands-on: Angular Deep Dive
Bab 10: Performa Lanjutan, Zoneless Architecture, & Micro-Frontends (Module Federation)
Deskripsi:
  Skrip simulasi komprehensif yang memodelkan:
  1. Zone.js vs Zoneless Reactive Change Detection (Fine-grained Signals Engine).
  2. Overhead benchmark antara Global CD (Top-Down) vs Targeted Zoneless Scheduling.
  3. Micro-Frontend (MFE) Runtime Orchestrator: Dynamic Module Federation & Inter-App Event Bus.
"""

import time
import random
from typing import Dict, List, Set, Callable, Any, Optional
from dataclasses import dataclass, field
from collections import deque

# --- ANSI Terminal Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_BLUE = "\033[94m"

# ==============================================================================
# SECTION 1: REACTIVE PRIMITIVES (Fine-Grained Signals Engine)
# ==============================================================================

class SignalContext:
    """Melacak dependency context aktif saat evaluasi reactive effect / computed."""
    active_consumer: Optional[Callable] = None


class Signal:
    """Implementasi reaktif Angular Signal (Producer)."""
    def __init__(self, initial_value: Any, name: str = "Signal"):
        self._value = initial_value
        self.name = name
        self._subscribers: Set[Callable] = set()

    def get(self) -> Any:
        if SignalContext.active_consumer is not None:
            self._subscribers.add(SignalContext.active_consumer)
        return self._value

    def set(self, new_value: Any) -> None:
        if self._value != new_value:
            self._value = new_value
            self._notify()

    def update(self, updater: Callable[[Any], Any]) -> None:
        self.set(updater(self._value))

    def _notify(self) -> None:
        # Notifikasi fine-grained consumer secara spesifik
        for subscriber in list(self._subscribers):
            subscriber()

    def __repr__(self):
        return f"Signal({self.name}={self._value})"


# ==============================================================================
# SECTION 2: COMPONENT TREE & CHANGE DETECTION (Zone.js vs Zoneless)
# ==============================================================================

class Component:
    """Representasi Component Node dalam Hierarki Virtual DOM Angular."""
    def __init__(self, name: str, parent: Optional['Component'] = None):
        self.name = name
        self.parent = parent
        self.children: List['Component'] = []
        self.check_count = 0
        self.is_dirty = False
        self.signals: Dict[str, Signal] = {}
        if parent:
            parent.children.append(self)

    def attach_signal(self, name: str, signal: Signal):
        self.signals[name] = signal
        # Daftarkan component renderer sebagai consumer dari signal
        def consumer():
            self.mark_dirty_zoneless()
        
        SignalContext.active_consumer = consumer
        signal.get()  # Registrasi subscription
        SignalContext.active_consumer = None

    def render(self) -> None:
        """Simulasi kalkulasi view binding / template rendering."""
        self.check_count += 1
        self.is_dirty = False

    def mark_dirty_zoneless(self) -> None:
        """Zoneless: Menandai node spesifik dan mengantri render tanpa global pass."""
        self.is_dirty = True
        ZonelessScheduler.schedule(self)


class ZoneJSSimulator:
    """
    Simulasi Zone.js:
    Setiap async macrotask/microtask (XHR, setTimeout, event listener)
    memicu pemeriksaan pohon komponen dari akar ke daun (Top-Down Dirty Checking).
    """
    @staticmethod
    def run_event(root: Component, trigger_node: Component, mutator: Callable) -> int:
        # 1. Eksekusi mutasi state
        mutator()
        
        # 2. Zone.js onTurnDone: Lakukan pengecekan menyeluruh (Full Tree Walk)
        checks = 0
        queue = deque([root])
        while queue:
            node = queue.popleft()
            node.render()
            checks += 1
            for child in node.children:
                queue.append(child)
        return checks


class ZonelessScheduler:
    """
    Simulasi Angular Zoneless:
    Tidak ada Zone.js monkey-patching. Komponen yang kotor (via Signal/markForCheck)
    menjadwalkan diri ke microtask queue, merender hanya node yang terpengaruh.
    """
    _queue: Set[Component] = set()

    @classmethod
    def schedule(cls, component: Component) -> None:
        cls._queue.add(component)

    @classmethod
    def flush(cls) -> int:
        checks = 0
        while cls._queue:
            component = cls._queue.pop()
            component.render()
            checks += 1
        return checks


# ==============================================================================
# SECTION 3: MICRO-FRONTEND (MFE) FEDERATION & EVENT BUS
# ==============================================================================

@dataclass
class FederatedManifest:
    app_name: str
    remote_entry: str
    exposed_modules: List[str]
    loaded: bool = False


class CrossMfeEventBus:
    """Event Bus Global terisolasi untuk komunikasi asinkron antar MFE."""
    def __init__(self):
        self._listeners: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(handler)

    def dispatch(self, event_type: str, payload: Dict[str, Any]) -> None:
        if event_type in self._listeners:
            for listener in self._listeners[event_type]:
                listener(payload)


class HostApplication:
    """Host Shell (Shell MFE) yang memuat Remote MFE secara dinamis."""
    def __init__(self, bus: CrossMfeEventBus):
        self.bus = bus
        self.remotes: Dict[str, FederatedManifest] = {}

    def register_remote(self, manifest: FederatedManifest) -> None:
        self.remotes[manifest.app_name] = manifest
        print(f"{CLR_BLUE}[Host-Shell]{CLR_RESET} Manifest didaftarkan: {CLR_BOLD}{manifest.app_name}{CLR_RESET} ({manifest.remote_entry})")

    def load_remote_module(self, app_name: str, module_name: str) -> bool:
        if app_name not in self.remotes:
            print(f"{CLR_RED}[Error]{CLR_RESET} MFE {app_name} tidak ditemukan.")
            return False
        remote = self.remotes[app_name]
        if module_name not in remote.exposed_modules:
            print(f"{CLR_RED}[Error]{CLR_RESET} Modul {module_name} tidak diekspos oleh {app_name}.")
            return False
        
        # Simulasi lazy network fetch script & initialize container
        time.sleep(0.03)
        remote.loaded = True
        print(f"{CLR_GREEN}✔ [Dynamic Remote Load]{CLR_RESET} Berhasil memuat container '{app_name}/{module_name}'")
        return True


# ==============================================================================
# SECTION 4: BENCHMARK & LAB RUNNER
# ==============================================================================

def build_component_tree() -> tuple[Component, List[Component]]:
    """Membangun hierarki komponen Angular yang dalam (Depth: 4, Nodes: 15)."""
    root = Component("AppRoot")
    
    # Header branch
    header = Component("AppHeader", parent=root)
    Component("UserBadge", parent=header)
    Component("NavMenu", parent=header)
    
    # Main Body branch
    main = Component("AppMain", parent=root)
    sidebar = Component("SideBar", parent=main)
    Component("FilterList", parent=sidebar)
    
    content = Component("ContentArea", parent=main)
    grid = Component("ProductGrid", parent=content)
    
    # Daun pohon komponen
    leaf_nodes = []
    for i in range(1, 9):
        card = Component(f"CardItem_{i}", parent=grid)
        leaf_nodes.append(card)
        
    all_nodes = [root, header, main, sidebar, content, grid] + leaf_nodes
    return root, all_nodes


def benchmark_zone_vs_zoneless():
    print(f"\n{CLR_CYAN}{'='*75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}LAB: PERFORMANCE BENCHMARK - ZONE.JS vs ZONELESS ARCHITECTURE{CLR_RESET}")
    print(f"{CLR_CYAN}{'='*75}{CLR_RESET}\n")

    root, all_nodes = build_component_tree()
    target_node = all_nodes[-1]  # Komponen daun terdalam (CardItem_8)
    
    # Siapkan Signal pada target node
    item_price = Signal(100, name="CardPrice")
    target_node.attach_signal("price", item_price)

    iterations = 500
    
    # --- 1. SIMULASI ZONE.JS ---
    print(f"{CLR_YELLOW}>>> Menjalankan {iterations} Async Events via Traditional Zone.js (Global Walk)...{CLR_RESET}")
    for node in all_nodes:
        node.check_count = 0

    zone_total_checks = 0
    t0 = time.perf_counter()
    for i in range(iterations):
        def mutator():
            item_price._value = 100 + i
        checks = ZoneJSSimulator.run_event(root, target_node, mutator)
        zone_total_checks += checks
    t_zone = time.perf_counter() - t0

    print(f"    Total Siklus CD (Zone.js)  : {CLR_BOLD}{zone_total_checks:,} checks{CLR_RESET}")
    print(f"    Waktu Eksekusi (Zone.js)   : {CLR_BOLD}{t_zone*1000:.2f} ms{CLR_RESET}")

    # --- 2. SIMULASI ZONELESS ARCHITECTURE ---
    print(f"\n{CLR_GREEN}>>> Menjalankan {iterations} Async Events via Zoneless Engine (Targeted Signal Flush)...{CLR_RESET}")
    for node in all_nodes:
        node.check_count = 0

    zoneless_total_checks = 0
    t0 = time.perf_counter()
    for i in range(iterations):
        # Mutasi signal memicu mark_dirty_zoneless secara spesifik via dependency
        item_price.set(200 + i)
        checks = ZonelessScheduler.flush()
        zoneless_total_checks += checks
    t_zoneless = time.perf_counter() - t0

    print(f"    Total Siklus CD (Zoneless) : {CLR_BOLD}{zoneless_total_checks:,} checks{CLR_RESET}")
    print(f"    Waktu Eksekusi (Zoneless)  : {CLR_BOLD}{t_zoneless*1000:.2f} ms{CLR_RESET}")

    # --- ANALISIS PERFORMA ---
    reduction = ((zone_total_checks - zoneless_total_checks) / zone_total_checks) * 100
    speedup = t_zone / t_zoneless if t_zoneless > 0 else 1.0

    print(f"\n{CLR_MAGENTA}{'-'*75}{CLR_RESET}")
    print(f"{CLR_BOLD}HASIL OPTIMASI ZONELESS:{CLR_RESET}")
    print(f"  • Reduksi Siklus Pengecekan : {CLR_BOLD}{CLR_GREEN}{reduction:.2f}% pengurangan DOM dirty-check{CLR_RESET}")
    print(f"  • Percepatan Eksekusi (Speedup): {CLR_BOLD}{CLR_GREEN}{speedup:.2f}x lebih cepat{CLR_RESET}")
    print(f"  • Penjelasan: Zone.js memeriksa {len(all_nodes)} node/event. Zoneless memeriksa 1 node/event.")
    print(f"{CLR_MAGENTA}{'-'*75}{CLR_RESET}\n")


def simulate_micro_frontends():
    print(f"{CLR_CYAN}{'='*75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}LAB: MICRO-FRONTENDS (MFE) FEDERATED MODULE LOADER & EVENT BUS{CLR_RESET}")
    print(f"{CLR_CYAN}{'='*75}{CLR_RESET}\n")

    event_bus = CrossMfeEventBus()
    host = HostApplication(bus=event_bus)

    # 1. Pendaftaran Remote Manifests (Module Federation)
    host.register_remote(FederatedManifest(
        app_name="OrderRemote",
        remote_entry="http://cdn.enterprise.internal/mfe/order/remoteEntry.js",
        exposed_modules=["OrderHistoryComponent", "CheckoutWidget"]
    ))
    host.register_remote(FederatedManifest(
        app_name="InventoryRemote",
        remote_entry="http://cdn.enterprise.internal/mfe/inventory/remoteEntry.js",
        exposed_modules=["StockTrackerComponent"]
    ))

    # 2. Inter-App Communication Listener Setup
    def on_order_created(payload: Dict[str, Any]):
        print(f"{CLR_YELLOW}[InventoryRemote Listener]{CLR_RESET} Menerima event '{CLR_BOLD}ORDER_PLACED{CLR_RESET}':")
        print(f"  --> Memperbarui reservasi stok untuk SKU: {payload.get('sku')} sejumlah {payload.get('qty')} unit.")

    event_bus.subscribe("ORDER_PLACED", on_order_created)

    # 3. Dynamic Module Federation Loading
    print()
    host.load_remote_module("OrderRemote", "CheckoutWidget")
    host.load_remote_module("InventoryRemote", "StockTrackerComponent")

    # 4. Dispatch Event lintas MFE boundaries
    print(f"\n{CLR_BLUE}[Host Shell Action]{CLR_RESET} Menembakkan event checkout pembayaran:")
    payload = {"order_id": "ORD-99824", "sku": "NG-CHIP-V18", "qty": 4, "total": 1250000}
    event_bus.dispatch("ORDER_PLACED", payload)

    print(f"\n{CLR_GREEN}✔ Simulasi Modul Micro-Frontend selesai dan terintegrasi aman.{CLR_RESET}\n")


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    benchmark_zone_vs_zoneless()
    simulate_micro_frontends()
    print(f"{CLR_BOLD}{CLR_GREEN}Lab Deep Dive Bab 10 (Zoneless & MFE) Selesai dengan Sukses.{CLR_RESET}")