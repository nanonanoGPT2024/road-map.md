#!/usr/bin/env python3
"""
Lab Exercise: Micro-Frontend Architecture & Production Systems
Modul 01: Core Foundations, Shell Orchestration, Module Federation & Event Bus Simulation.

Simulasi teknis komprehensif arsitektur Micro-Frontend (MFE) tingkat lanjut:
1. Module Federation & Shared Dependency Resolution (SemVer Conflict Negotiation)
2. Host Shell Router & Dynamic Lifecycle Orchestrator (Mount/Unmount/Bootstrap)
3. Event-Driven Cross-MFE Communication (Typed EventBus & State Hydration)
4. Runtime Fault-Tolerance & Circuit Breaker (Resilient Fallback Handling)
"""

import sys
import time
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Callable, Any, Optional

# --- ANSI Color Utilities ---
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
    BG_RED = "\033[41m"

def c_print(color: str, text: str, bold: bool = False, end: str = "\n"):
    prefix = Color.BOLD if bold else ""
    print(f"{prefix}{color}{text}{Color.RESET}", end=end)


class MFEState(Enum):
    NOT_LOADED = "NOT_LOADED"
    FETCHING = "FETCHING"
    LOADED = "LOADED"
    BOOTSTRAPPED = "BOOTSTRAPPED"
    MOUNTED = "MOUNTED"
    UNMOUNTED = "UNMOUNTED"
    FAULTED = "FAULTED"


@dataclass
class SharedDependency:
    name: str
    required_version: str
    singleton: bool = True
    loaded_version: Optional[str] = None


@dataclass
class MicroFrontendManifest:
    name: str
    entry_url: str
    mount_route: str
    dependencies: Dict[str, str]  # dependency_name -> semver
    failure_rate: float = 0.0     # Probabilitas network/runtime failure (0.0 - 1.0)
    current_state: MFEState = MFEState.NOT_LOADED


class CrossMFEEventBus:
    """EventBus Global untuk komunikasi decoupled antar Micro-Frontends."""
    def __init__(self):
        self._listeners: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self._event_log: List[Dict[str, Any]] = []

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def publish(self, event_type: str, sender: str, payload: Dict[str, Any]):
        timestamp = time.strftime("%H:%M:%S")
        record = {
            "timestamp": timestamp,
            "event_type": event_type,
            "sender": sender,
            "payload": payload
        }
        self._event_log.append(record)
        c_print(Color.CYAN, f"  [EventBus] -> '{event_type}' disiarkan oleh <{sender}>: {json.dumps(payload)}")
        
        listeners = self._listeners.get(event_type, [])
        for cb in listeners:
            try:
                cb(record)
            except Exception as e:
                c_print(Color.RED, f"  [EventBus Error] Callback listener gagal: {e}")

    def get_history(self) -> List[Dict[str, Any]]:
        return self._event_log


class ModuleFederationResolver:
    """Manajer resolusi singleton dependency & negoisasi versi (Module Federation)."""
    def __init__(self):
        self.shared_scope: Dict[str, str] = {}  # lib -> resolved_version

    def register_or_resolve(self, mfe_name: str, dep: str, req_version: str) -> bool:
        if dep not in self.shared_scope:
            self.shared_scope[dep] = req_version
            c_print(Color.GREEN, f"    [ModuleFederation] {mfe_name} menginisialisasi shared '{dep}' @ v{req_version} (Singleton Scope)")
            return True
        else:
            resolved = self.shared_scope[dep]
            # Sederhana: bandingkan major version
            req_major = req_version.split(".")[0]
            res_major = resolved.split(".")[0]
            if req_major == res_major:
                c_print(Color.BLUE, f"    [ModuleFederation] {mfe_name} menggunakan shared '{dep}' @ v{resolved} (Kompatibel dengan v{req_version})")
                return True
            else:
                c_print(Color.YELLOW, f"    [ModuleFederation WARN] Ketidakcocokan versi major '{dep}': butuh v{req_version}, tersedia v{resolved}!")
                return False


class CircuitBreaker:
    """Pola Circuit Breaker untuk isolasi kegagalan remote MFE."""
    def __init__(self, failure_threshold: int = 2, recovery_timeout: float = 3.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_counts: Dict[str, int] = {}
        self.tripped_time: Dict[str, float] = {}

    def record_success(self, mfe_name: str):
        self.failure_counts[mfe_name] = 0
        if mfe_name in self.tripped_time:
            del self.tripped_time[mfe_name]

    def record_failure(self, mfe_name: str):
        self.failure_counts[mfe_name] = self.failure_counts.get(mfe_name, 0) + 1
        if self.failure_counts[mfe_name] >= self.failure_threshold:
            self.tripped_time[mfe_name] = time.time()
            c_print(Color.RED, f"    [CircuitBreaker] ⚠️ Remote <{mfe_name}> TRIPPED! Sirkuit terbuka, fallback UI diaktifkan.", bold=True)

    def is_open(self, mfe_name: str) -> bool:
        if mfe_name in self.tripped_time:
            elapsed = time.time() - self.tripped_time[mfe_name]
            if elapsed > self.recovery_timeout:
                c_print(Color.YELLOW, f"    [CircuitBreaker] Remote <{mfe_name}> memasuki mode HALF-OPEN. Mencoba rekonsiliasi...")
                return False
            return True
        return False


class MicroFrontendHostShell:
    """Host Shell yang bertanggung jawab terhadap routing, lifecycle, dan isolasi MFE."""
    def __init__(self):
        self.registry: Dict[str, MicroFrontendManifest] = {}
        self.route_map: Dict[str, str] = {}  # route -> mfe_name
        self.active_mfe: Optional[str] = None
        self.event_bus = CrossMFEEventBus()
        self.federation = ModuleFederationResolver()
        self.circuit_breaker = CircuitBreaker()
        self._setup_event_listeners()

    def _setup_event_listeners(self):
        # Listener contoh untuk audit global shell
        self.event_bus.subscribe("AUTH_TOKEN_UPDATED", self._on_auth_changed)
        self.event_bus.subscribe("CART_ITEM_ADDED", self._on_cart_updated)

    def _on_auth_changed(self, event: Dict[str, Any]):
        user = event["payload"].get("username", "Anonymous")
        c_print(Color.MAGENTA, f"  [Shell Core] Session sinkron: User aktif saat ini adalah '{user}'")

    def _on_cart_updated(self, event: Dict[str, Any]):
        count = event["payload"].get("total_items", 0)
        c_print(Color.MAGENTA, f"  [Shell Header/Navbar Badge] Indikator Keranjang diperbarui: {count} item")

    def register_mfe(self, manifest: MicroFrontendManifest):
        self.registry[manifest.name] = manifest
        self.route_map[manifest.mount_route] = manifest.name
        c_print(Color.WHITE, f"[Host Shell] MFE Terdaftar: <{manifest.name}> di route '{manifest.mount_route}'")

    def navigate(self, target_route: str):
        c_print(Color.WHITE, f"\n=== [Host Shell Router] Navigasi ke: '{target_route}' ===", bold=True)
        target_mfe_name = self.route_map.get(target_route)

        if not target_mfe_name:
            c_print(Color.YELLOW, f"  [Host Shell] 404 Route Not Found! Render Fallback 404 Page.")
            self._unmount_active()
            return

        if target_mfe_name == self.active_mfe:
            c_print(Color.DIM, f"  [Host Shell] Micro-Frontend <{target_mfe_name}> sudah mounted di route ini.")
            return

        # 1. Unmount MFE yang sedang aktif
        self._unmount_active()

        # 2. Periksa Circuit Breaker
        if self.circuit_breaker.is_open(target_mfe_name):
            c_print(Color.RED, f"  [Host Shell] Remote <{target_mfe_name}> tidak sehat. Menampilkan Fallback Error Boundary!")
            return

        # 3. Mount MFE baru
        manifest = self.registry[target_mfe_name]
        self._mount_mfe(manifest)

    def _unmount_active(self):
        if self.active_mfe:
            old_manifest = self.registry[self.active_mfe]
            old_manifest.current_state = MFEState.UNMOUNTED
            c_print(Color.YELLOW, f"  [Host Shell] Unmounting <{self.active_mfe}>... Cleanup DOM, unbind listeners.")
            self.active_mfe = None

    def _mount_mfe(self, manifest: MicroFrontendManifest):
        c_print(Color.CYAN, f"  [Host Shell] Memuat Remote Container: {manifest.entry_url}")
        manifest.current_state = MFEState.FETCHING
        time.sleep(0.3)

        # Simulasi network instability / failure
        if random.random() < manifest.failure_rate:
            c_print(Color.RED, f"  [Host Shell ERROR] Gagal mengunduh bundle container <{manifest.name}>!")
            manifest.current_state = MFEState.FAULTED
            self.circuit_breaker.record_failure(manifest.name)
            c_print(Color.YELLOW, f"  [Host Shell] Render Fallback UI mikro untuk <{manifest.name}>.")
            return

        self.circuit_breaker.record_success(manifest.name)
        manifest.current_state = MFEState.LOADED

        # Resolve Shared Dependencies (Webpack Module Federation style)
        c_print(Color.DIM, f"  [Host Shell] Menjalankan Module Federation Dependency Negotiation...")
        for dep, ver in manifest.dependencies.items():
            self.federation.register_or_resolve(manifest.name, dep, ver)

        # Bootstrap & Mount
        manifest.current_state = MFEState.BOOTSTRAPPED
        c_print(Color.DIM, f"  [Host Shell] Bootstrapping <{manifest.name}>...")
        manifest.current_state = MFEState.MOUNTED
        self.active_mfe = manifest.name
        c_print(Color.GREEN, f"  [Host Shell SUCCESS] Remote <{manifest.name}> berhasil di-mount pada DOM container!", bold=True)


def run_interactive_simulation():
    """Loop simulasi interaktif dengan terminal UI."""
    shell = MicroFrontendHostShell()

    # Inisialisasi Katalog Micro-Frontend Production
    shell.register_mfe(MicroFrontendManifest(
        name="Catalog-MFE",
        entry_url="https://cdn.production.app/remotes/catalog/remoteEntry.js",
        mount_route="/catalog",
        dependencies={"react": "18.2.0", "lodash": "4.17.21"},
        failure_rate=0.0
    ))
    shell.register_mfe(MicroFrontendManifest(
        name="Cart-Checkout-MFE",
        entry_url="https://cdn.production.app/remotes/checkout/remoteEntry.js",
        mount_route="/checkout",
        dependencies={"react": "18.2.0", "axios": "1.6.0"},
        failure_rate=0.4  # Disimulasikan sesekali mengalami network glitch
    ))
    shell.register_mfe(MicroFrontendManifest(
        name="Account-Profile-MFE",
        entry_url="https://cdn.production.app/remotes/account/remoteEntry.js",
        mount_route="/account",
        dependencies={"react": "19.0.0-rc", "zustand": "4.4.1"}, # Beda major version react
        failure_rate=0.1
    ))

    cart_state = {"items_count": 0}

    while True:
        print("\n" + "=" * 65)
        c_print(Color.BG_BLUE + Color.WHITE, " MICRO-FRONTEND ARCHITECTURE LAB (INTERACTIVE CONSOLE) ", bold=True)
        print("=" * 65)
        print(f" Status Host Shell: Active MFE = [{shell.active_mfe or 'None'}]")
        print(" Pilihan Aksi:")
        print("   1. Navigasi ke '/catalog' (Katalog Produk)")
        print("   2. Navigasi ke '/checkout' (Keranjang & Pembayaran)")
        print("   3. Navigasi ke '/account' (Profil & Autentikasi Pengguna)")
        print("   4. Publish Event: Autentikasi User (AUTH_TOKEN_UPDATED)")
        print("   5. Publish Event: Tambah Barang ke Keranjang (CART_ITEM_ADDED)")
        print("   6. Inspeksi State Registry & Shared Scopes")
        print("   7. Keluar / Exit")
        print("-" * 65)

        choice = input("Pilih menu (1-7): ").strip()

        if choice == "1":
            shell.navigate("/catalog")
        elif choice == "2":
            shell.navigate("/checkout")
        elif choice == "3":
            shell.navigate("/account")
        elif choice == "4":
            uname = input("Masukkan nama pengguna baru (default: Sarah Connor): ").strip() or "Sarah Connor"
            token = f"jwt_mock_{random.randint(1000, 9999)}"
            shell.event_bus.publish("AUTH_TOKEN_UPDATED", "Auth-Identity-Service", {"username": uname, "token": token})
        elif choice == "5":
            cart_state["items_count"] += 1
            item_name = random.choice(["Mechanical Keyboard", "UltraWide Monitor", "Ergonomic Chair", "Noise-Cancelling Headset"])
            shell.event_bus.publish("CART_ITEM_ADDED", shell.active_mfe or "Global-Shortcut", {
                "item": item_name,
                "price": random.randint(50, 400),
                "total_items": cart_state["items_count"]
            })
        elif choice == "6":
            print("\n--- [REGISTRY & SHARED SCOPES INSPECTION] ---")
            for name, manifest in shell.registry.items():
                print(f" * Remote: {name:<20} | Status: {manifest.current_state.value:<12} | Route: {manifest.mount_route}")
            print("\n Shared Scope (Singleton Instances):")
            print(json.dumps(shell.federation.shared_scope, indent=2))
        elif choice == "7":
            c_print(Color.GREEN, "Menutup simulasi Micro-Frontend. Selesai.")
            break
        else:
            c_print(Color.RED, "Pilihan tidak valid, silakan coba lagi.")


if __name__ == "__main__":
    try:
        run_interactive_simulation()
    except (KeyboardInterrupt, EOFError):
        print("\n\nSimulasi dihentikan.")
        sys.exit(0)
