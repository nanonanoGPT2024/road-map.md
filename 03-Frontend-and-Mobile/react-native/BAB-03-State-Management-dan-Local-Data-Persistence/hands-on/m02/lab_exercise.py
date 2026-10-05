#!/usr/bin/env python3
"""
Lab Exercise: React Native Advanced State Management & Local Data Persistence Simulator
Bab 03: State Management (Zustand / Redux Architecture) & Local Persistence (MMKV + SQLite/WatermelonDB Sync)

Simulasi interaktif arsitektur offline-first, sinkronisasi storage instan (MMKV JSI bindings),
serta mutation queue dengan conflict resolution (Last-Write-Wins).
"""

import sys
import time
import json
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

# --- ANSI Terminal Styling ---
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
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"

def print_banner():
    print(f"\n{CYAN}{BOLD}{'='*75}{RESET}")
    print(f"{CYAN}{BOLD}  REACT NATIVE PRODUCTION STATE & PERSISTENCE ARCHITECTURE LAB{RESET}")
    print(f"{BLUE}  Simulation: Zustand Store + JSI MMKV Fast Cache + SQLite Offline Queue{RESET}")
    print(f"{CYAN}{BOLD}{'='*75}{RESET}\n")

# --- Model & Data Contracts ---

@dataclass
class MutationRecord:
    id: str
    action: str
    payload: Dict[str, Any]
    client_timestamp: float
    status: str  # PENDING, SYNCED, CONFLICT

@dataclass
class Product:
    id: str
    name: str
    price: float
    stock: int
    updated_at: float

# --- Layer 1: Simulated MMKV Storage (Synchronous JSI Engine) ---
class MMKVEngine:
    """
    Simulasi react-native-mmkv (C++ JSI Direct Memory Access).
    Operasi bersifat synchronous, thread-safe, dan efisiensi I/O tinggi.
    """
    def __init__(self, storage_id: str = "app_secure_mmkv"):
        self.storage_id = storage_id
        self._raw_memory: Dict[str, str] = {}
        self.read_count = 0
        self.write_count = 0

    def set_string(self, key: str, value: str):
        self._raw_memory[key] = value
        self.write_count += 1

    def get_string(self, key: str) -> Optional[str]:
        self.read_count += 1
        return self._raw_memory.get(key)

    def set_json(self, key: str, data: Any):
        self.set_string(key, json.dumps(data))

    def get_json(self, key: str) -> Optional[Any]:
        val = self.get_string(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return None

    def dump_keys(self) -> List[str]:
        return list(self._raw_memory.keys())

# --- Layer 2: Simulated Local SQLite / WatermelonDB Layer ---
class SQLiteLocalDB:
    """
    Simulasi SQLite / WatermelonDB relational local database
    untuk caching tabel besar dan tracking status sinkronisasi offline.
    """
    def __init__(self):
        self.products: Dict[str, Product] = {}
        self.mutation_queue: List[MutationRecord] = []

    def upsert_product(self, product: Product):
        self.products[product.id] = product

    def get_all_products(self) -> List[Product]:
        return list(self.products.values())

    def enqueue_mutation(self, action: str, payload: Dict[str, Any]) -> MutationRecord:
        record = MutationRecord(
            id=str(uuid.uuid4())[:8],
            action=action,
            payload=payload,
            client_timestamp=time.time(),
            status="PENDING"
        )
        self.mutation_queue.append(record)
        return record

    def get_pending_mutations(self) -> List[MutationRecord]:
        return [m for m in self.mutation_queue if m.status == "PENDING"]

    def mark_mutation_resolved(self, mutation_id: str, new_status: str):
        for m in self.mutation_queue:
            if m.id == mutation_id:
                m.status = new_status
                break

# --- Layer 3: Centralized Reactive Store (Zustand Architecture) ---
class ReactZustandStore:
    """
    Simulasi Reactive State Store dengan selector, middleware logging,
    dan synchronous write-through cache ke MMKV.
    """
    def __init__(self, mmkv: MMKVEngine, sqlite_db: SQLiteLocalDB):
        self.mmkv = mmkv
        self.sqlite = sqlite_db
        self.state: Dict[str, Any] = {
            "cart": {},             # {product_id: quantity}
            "is_online": True,
            "user_session": None,
            "last_synced_at": 0.0
        }
        self.subscribers = []
        self._hydrate_from_persistence()

    def _hydrate_from_persistence(self):
        saved_cart = self.mmkv.get_json("persist:cart_slice")
        if saved_cart:
            self.state["cart"] = saved_cart
        session = self.mmkv.get_json("persist:user_session")
        if session:
            self.state["user_session"] = session

    def subscribe(self, callback):
        self.subscribers.append(callback)

    def _notify(self, slice_name: str):
        for sub in self.subscribers:
            sub(slice_name, self.state)

    # --- Actions ---
    def set_online_status(self, is_online: bool):
        self.state["is_online"] = is_online
        self._notify("network")

    def login(self, username: str, role: str = "Engineer"):
        session_data = {"user": username, "role": role, "token": f"jwt_{uuid.uuid4().hex[:12]}"}
        self.state["user_session"] = session_data
        # Synchronous write to MMKV
        self.mmkv.set_json("persist:user_session", session_data)
        self._notify("auth")

    def logout(self):
        self.state["user_session"] = None
        self.mmkv.set_string("persist:user_session", "")
        self._notify("auth")

    def add_to_cart_optimistic(self, product_id: str, quantity: int = 1):
        """
        Optimistic Update:
        1. Langsung perbarui in-memory React state untuk 60FPS UI response
        2. Tulis langsung ke MMKV (0 latency)
        3. Enqueue mutation ke SQLite jika offline / dispatch remote request jika online
        """
        current_qty = self.state["cart"].get(product_id, 0)
        new_qty = current_qty + quantity
        self.state["cart"][product_id] = new_qty
        
        # Persist to MMKV immediately
        self.mmkv.set_json("persist:cart_slice", self.state["cart"])
        self._notify("cart")

        # Catat mutasi untuk offline sync
        mut_record = self.sqlite.enqueue_mutation(
            action="UPDATE_CART_ITEM",
            payload={"product_id": product_id, "quantity": new_qty}
        )

        return mut_record

    def clear_cart(self):
        self.state["cart"] = {}
        self.mmkv.set_json("persist:cart_slice", {})
        self._notify("cart")

# --- Layer 4: Cloud Sync Engine & Conflict Resolver ---
class SyncEngine:
    def __init__(self, store: ReactZustandStore, sqlite_db: SQLiteLocalDB):
        self.store = store
        self.sqlite = sqlite_db
        # Remote mock backend state
        self.server_cart_state: Dict[str, Any] = {}
        self.server_version = 100

    def trigger_background_sync(self):
        print(f"\n{YELLOW}[SyncEngine] Memulai sinkronisasi offline mutation queue...{RESET}")
        time.sleep(0.3)
        pending = self.sqlite.get_pending_mutations()

        if not self.store.state["is_online"]:
            print(f"{RED}[SyncEngine] ABORT: Perangkat offline. {len(pending)} mutasi ditunda.{RESET}")
            return

        if not pending:
            print(f"{GREEN}[SyncEngine] Tidak ada mutasi tertunda. State sudah tersinkronisasi.{RESET}")
            return

        print(f"{CYAN}[SyncEngine] Memproses {len(pending)} mutasi...{RESET}")
        for mutation in pending:
            # Resolusi konflik LWW (Last-Write-Wins)
            p_id = mutation.payload.get("product_id")
            p_qty = mutation.payload.get("quantity")
            
            # Simulasi network roundtrip
            print(f"  {DIM}--> Mengirim {mutation.action} (ID: {mutation.id}) ke Cloud API...{RESET}")
            self.server_cart_state[p_id] = p_qty
            self.sqlite.mark_mutation_resolved(mutation.id, "SYNCED")
            print(f"  {GREEN}✓ Mutasi {mutation.id} berhasil diakui (ACK) oleh server.{RESET}")

        self.store.state["last_synced_at"] = time.time()
        print(f"{GREEN}{BOLD}[SyncEngine] Sinkronisasi Sukses! Semua transaksi lokal telah commit.{RESET}")

# --- UI Renderer & CLI Interface ---
def render_dashboard(store: ReactZustandStore, sqlite_db: SQLiteLocalDB, mmkv: MMKVEngine):
    session = store.state["user_session"]
    network_color = BG_GREEN if store.state["is_online"] else BG_RED
    network_text = " ONLINE " if store.state["is_online"] else " OFFLINE "

    print(f"\n{BOLD}------------------------------- SISTEM STATUS -------------------------------{RESET}")
    print(f" Network Status : {network_color}{BOLD}{network_text}{RESET} | MMKV Reads: {mmkv.read_count} Writes: {mmkv.write_count}")
    print(f" User Session   : {GREEN + session['user'] + ' (' + session['role'] + ')' if session else RED + 'Guest (Not Logged In)'}{RESET}")
    
    # Cart details
    cart = store.state["cart"]
    cart_summary = ", ".join([f"{pid} x{qty}" for pid, qty in cart.items()]) if cart else "Kosong"
    print(f" Active Cart    : {CYAN}{cart_summary}{RESET}")

    # Pending Mutations
    pending = sqlite_db.get_pending_mutations()
    pend_color = YELLOW if pending else GREEN
    print(f" Offline Queue  : {pend_color}{len(pending)} mutasi pending{RESET}")
    print(f"{BOLD}-----------------------------------------------------------------------------{RESET}")

def interactive_loop():
    # Setup seed data
    mmkv = MMKVEngine()
    sqlite_db = SQLiteLocalDB()
    
    # Populate catalogue in SQLite
    products = [
        Product(id="PROD-01", name="React Native Book", price=35.0, stock=20, updated_at=time.time()),
        Product(id="PROD-02", name="JSI Architecture Course", price=79.0, stock=100, updated_at=time.time()),
        Product(id="PROD-03", name="Wireless Mechanical Key", price=120.0, stock=15, updated_at=time.time())
    ]
    for p in products:
        sqlite_db.upsert_product(p)

    store = ReactZustandStore(mmkv, sqlite_db)
    sync_engine = SyncEngine(store, sqlite_db)

    # Auto-login default developer
    store.login("MobileArchitect", role="Lead Mobile Engineer")

    while True:
        render_dashboard(store, sqlite_db, mmkv)
        print(f"\n{BOLD}Menu Eksperimen Arsitektur:{RESET}")
        print(f"  {CYAN}1.{RESET} Tambah item ke Keranjang (Optimistic UI Update + MMKV write)")
        print(f"  {CYAN}2.{RESET} Toggle Network State (Online <--> Offline)")
        print(f"  {CYAN}3.{RESET} Jalankan Sinkronisasi Background (SyncEngine)")
        print(f"  {CYAN}4.{RESET} Inspeksi Raw Binary/JSON Cache di MMKV Storage")
        print(f"  {CYAN}5.{RESET} Kosongkan Keranjang (Reset State & Cache)")
        print(f"  {CYAN}6.{RESET} Jalankan Automated Stress Test (100 Mutasi Cepat)")
        print(f"  {RED}0.{RESET} Keluar (Exit)")

        try:
            choice = input(f"\n{BOLD}Pilih opsi [0-6]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Program dihentikan oleh user.{RESET}")
            break

        if choice == "1":
            print(f"\nPilih produk yang ingin ditambahkan:")
            for idx, p in enumerate(sqlite_db.get_all_products(), start=1):
                print(f"  {idx}. {p.id} - {p.name} (${p.price})")
            p_choice = input("Pilih nomor produk (1-3): ").strip()
            item_map = {"1": "PROD-01", "2": "PROD-02", "3": "PROD-03"}
            selected_id = item_map.get(p_choice, "PROD-01")
            
            mut = store.add_to_cart_optimistic(selected_id, quantity=1)
            print(f"{GREEN}✓ State diperbarui secara optimistik! Mutasi terdaftar: [{mut.id}]{RESET}")

        elif choice == "2":
            new_status = not store.state["is_online"]
            store.set_online_status(new_status)
            status_label = "ONLINE" if new_status else "OFFLINE"
            print(f"{YELLOW}Jaringan diubah menjadi: {BOLD}{status_label}{RESET}")

        elif choice == "3":
            sync_engine.trigger_background_sync()

        elif choice == "4":
            print(f"\n{MAGENTA}{BOLD}=== ISI PERSISTENSI MMKV (Synchronous Raw Storage) ==={RESET}")
            keys = mmkv.dump_keys()
            for k in keys:
                print(f"  {BOLD}Key:{RESET} {CYAN}{k}{RESET}")
                print(f"  {BOLD}Value:{RESET} {mmkv.get_string(k)}")
            print(f"{MAGENTA}{'='*50}{RESET}")

        elif choice == "5":
            store.clear_cart()
            print(f"{YELLOW}Keranjang telah di-reset dan MMKV diperbarui.{RESET}")

        elif choice == "6":
            print(f"\n{BLUE}{BOLD}[Benchmark] Memulai Stress Test Optimistic State + MMKV...{RESET}")
            start_time = time.time()
            store.set_online_status(False)
            for i in range(100):
                pid = f"PROD-0{((i % 3) + 1)}"
                store.add_to_cart_optimistic(pid, quantity=1)
            duration = (time.time() - start_time) * 1000
            print(f"{GREEN}✓ Berhasil mengeksekusi 100 mutasi offline dalam {duration:.2f} ms!{RESET}")
            print(f"{GREEN}✓ Rata-rata persistensi MMKV: {duration / 100:.3f} ms per update (C++ JSI Equivalent).{RESET}")

        elif choice == "0":
            print(f"\n{CYAN}Menutup simulasi lab. Sampai jumpa di produksi!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")

if __name__ == "__main__":
    print_banner()
    interactive_loop()
