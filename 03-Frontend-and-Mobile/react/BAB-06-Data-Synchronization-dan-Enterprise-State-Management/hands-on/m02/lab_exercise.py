#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Enterprise State Management & Data Synchronization di React
Topik: BAB-06 Data Synchronization dan Enterprise State Management
Fitur Simulasi:
  - TanStack Query Engine (Stale-While-Revalidate, GC, Query Invalidation)
  - Zustand / Redux Enterprise Store (Action Dispatching, Middleware, Subscriptions)
  - Optimistic Updates dengan Automatic Rollback pada Server Failure
  - Offline Action Sync Queue (Simulasi IndexedDB Sync Worker)
"""

import sys
import time
import json
import random
from typing import Dict, Any, List, Callable, Optional

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
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"

def banner():
    print(f"{Color.CYAN}{Color.BOLD}{'='*75}")
    print("  🚀 SIMULASI PRODUKSI: REACT ENTERPRISE STATE & DATA SYNCHRONIZATION")
    print(f"  Modul 02: TanStack Query + Zustand Store + Optimistic Rollback Queue")
    print(f"{'='*75}{Color.RESET}\n")

# --- Model & Server Mock ---
class MockServer:
    def __init__(self):
        self.db = {
            "products": [
                {"id": 1, "name": "Enterprise Cloud Suite", "stock": 45, "price": 1200},
                {"id": 2, "name": "Real-time Telemetry Agent", "stock": 18, "price": 450},
                {"id": 3, "name": "Edge Compute Gateway", "stock": 5, "price": 890}
            ]
        }
        self.latency_sec = 0.6
        self.failure_rate = 0.0  # Controlled failure

    def fetch_products(self) -> List[Dict[str, Any]]:
        time.sleep(self.latency_sec)
        if random.random() < self.failure_rate:
            raise RuntimeError("500 Internal Server Error: Database deadlock detected!")
        return json.loads(json.dumps(self.db["products"]))

    def update_stock(self, product_id: int, new_stock: int) -> Dict[str, Any]:
        time.sleep(self.latency_sec)
        if random.random() < self.failure_rate:
            raise RuntimeError(f"500 Server Mutation Error: Gagal mengupdate produk {product_id}!")
        for item in self.db["products"]:
            if item["id"] == product_id:
                item["stock"] = new_stock
                return dict(item)
        raise ValueError("Product not found")

# --- Client Cache: TanStack Query Simulation ---
class QueryCacheEntry:
    def __init__(self, key: str, data: Any, stale_time: float = 3.0):
        self.key = key
        self.data = data
        self.updated_at = time.time()
        self.stale_time = stale_time

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.updated_at) > self.stale_time

class QueryClient:
    def __init__(self, server: MockServer):
        self.server = server
        self.cache: Dict[str, QueryCacheEntry] = {}
        self.listeners: List[Callable[[str, Any], None]] = []

    def subscribe(self, callback: Callable[[str, Any], None]):
        self.listeners.append(callback)

    def _notify(self, key: str, data: Any):
        for cb in self.listeners:
            cb(key, data)

    def fetch_query(self, key: str, force_refetch: bool = False) -> Any:
        entry = self.cache.get(key)
        if entry and not entry.is_stale and not force_refetch:
            print(f"{Color.GREEN}  ⚡ [QueryCache HIT] key='{key}' (Fresh, age: {time.time()-entry.updated_at:.2f}s){Color.RESET}")
            return entry.data

        if entry and entry.is_stale and not force_refetch:
            print(f"{Color.YELLOW}  ⚠️  [SWR Triggered] key='{key}' stale! Mengembalikan stale data sambil background revalidating...{Color.RESET}")
            self._revalidate_in_background(key)
            return entry.data

        print(f"{Color.BLUE}  🌐 [QueryCache MISS/REFETCH] Mengunduh data segar dari remote server...{Color.RESET}")
        data = self.server.fetch_products()
        self.cache[key] = QueryCacheEntry(key, data)
        self._notify(key, data)
        return data

    def _revalidate_in_background(self, key: str):
        print(f"{Color.DIM}     ↳ [Background Worker] Fetching fresh data...{Color.RESET}")
        try:
            fresh_data = self.server.fetch_products()
            self.cache[key] = QueryCacheEntry(key, fresh_data)
            print(f"{Color.GREEN}     ↳ [Background Worker] Cache diperbarui! UI tersinkronisasi.{Color.RESET}")
            self._notify(key, fresh_data)
        except Exception as e:
            print(f"{Color.RED}     ↳ [Background Worker] Revalidation gagal: {e}{Color.RESET}")

    def invalidate_queries(self, key: str):
        print(f"{Color.MAGENTA}  🔄 [Cache Invalidation] Query key='{key}' ditandai STALE/INVALID!{Color.RESET}")
        if key in self.cache:
            self.cache[key].updated_at = 0  # Force stale

    def set_query_data(self, key: str, new_data: Any):
        self.cache[key] = QueryCacheEntry(key, new_data)
        self._notify(key, new_data)

# --- Global Enterprise Store: Zustand / Redux Simulation ---
class EnterpriseStore:
    def __init__(self):
        self.state = {
            "user": {"name": "Senior Cloud Architect", "role": "admin"},
            "cart": [],
            "network_status": "online",
            "optimistic_snapshots": []
        }
        self.middlewares = [self._logger_middleware]

    def _logger_middleware(self, action_type: str, payload: Any, prev_state: Dict[str, Any]):
        print(f"{Color.CYAN}  📦 [Zustand Dispatch] Action: {Color.BOLD}{action_type}{Color.RESET}")
        print(f"{Color.DIM}     Payload: {payload}{Color.RESET}")

    def dispatch(self, action_type: str, payload: Any = None):
        prev = json.loads(json.dumps(self.state))
        for mw in self.middlewares:
            mw(action_type, payload, prev)

        if action_type == "SET_NETWORK_STATUS":
            self.state["network_status"] = payload
        elif action_type == "ADD_TO_CART":
            self.state["cart"].append(payload)
        elif action_type == "CLEAR_CART":
            self.state["cart"] = []

# --- Optimistic Mutation Controller with Rollback & Offline Queue ---
class OptimisticMutationManager:
    def __init__(self, query_client: QueryClient, store: EnterpriseStore, server: MockServer):
        self.query_client = query_client
        self.store = store
        self.server = server
        self.offline_queue: List[Dict[str, Any]] = []

    def mutate_stock_optimistic(self, product_id: int, new_stock: int):
        cache_key = "products"
        current_data = self.query_client.cache.get(cache_key)
        snapshot = json.loads(json.dumps(current_data.data)) if current_data else []

        print(f"\n{Color.YELLOW}=== 1. PRE-MUTATION SNAPSHOT ==={Color.RESET}")
        print(f"  Menyimpan snapshot cache untuk proteksi rollback jika server gagal...")

        # Optimistic UI Update
        optimistic_data = []
        for p in snapshot:
            item = dict(p)
            if item["id"] == product_id:
                item["stock"] = new_stock
            optimistic_data.append(item)

        print(f"{Color.GREEN}=== 2. APPLYING OPTIMISTIC UPDATE ==={Color.RESET}")
        print(f"  UI langsung diperbarui seketika (Zero Latency perception untuk user).")
        self.query_client.set_query_data(cache_key, optimistic_data)

        # Check network status
        if self.store.state["network_status"] == "offline":
            print(f"{Color.YELLOW}  📴 [OFFLINE MODE] Koneksi offline! Mutation dimasukkan ke Offline Sync Queue.{Color.RESET}")
            self.offline_queue.append({"product_id": product_id, "new_stock": new_stock})
            return

        # Execute remote call
        print(f"{Color.BLUE}=== 3. NETWORK SYNC TO SERVER ==={Color.RESET}")
        try:
            self.server.update_stock(product_id, new_stock)
            print(f"{Color.GREEN}  ✅ Server konfirmasi 200 OK! Mutasi permanen.{Color.RESET}")
            self.query_client.invalidate_queries(cache_key)
        except Exception as e:
            print(f"{Color.BG_RED}{Color.WHITE} ❌ SERVER REJECTED MUTATION! {Color.RESET} {Color.RED}{e}{Color.RESET}")
            print(f"{Color.YELLOW}=== 4. TRIGGERING AUTOMATIC ROLLBACK ==={Color.RESET}")
            print(f"  Mengembalikan state UI ke snapshot awal sebelum mutasi...")
            self.query_client.set_query_data(cache_key, snapshot)
            print(f"{Color.GREEN}  🛡️ Cache & UI berhasil di-rollback ke konsistensi server!{Color.RESET}")

    def flush_offline_queue(self):
        if not self.offline_queue:
            print(f"{Color.DIM}  Queue kosong. Tidak ada mutasi offline tertunda.{Color.RESET}")
            return

        print(f"{Color.CYAN}  🔄 Menguras {len(self.offline_queue)} mutasi dari Offline Sync Queue...{Color.RESET}")
        queue_copy = list(self.offline_queue)
        self.offline_queue.clear()
        for task in queue_copy:
            print(f"     ↳ Syncing product_id={task['product_id']} -> stock={task['new_stock']}")
            try:
                self.server.update_stock(task["product_id"], task["new_stock"])
                print(f"{Color.GREEN}       ✅ Berhasil disinkronisasi ke server!{Color.RESET}")
            except Exception as e:
                print(f"{Color.RED}       ❌ Gagal sync: {e}{Color.RESET}")
        self.query_client.invalidate_queries("products")

# --- Interactive CLI Interface ---
def render_product_table(products: List[Dict[str, Any]]):
    print(f"\n{Color.BOLD}{'ID':<4} | {'Product Name':<30} | {'Stock':<8} | {'Price ($)':<10}{Color.RESET}")
    print("-" * 60)
    for p in products:
        stock_color = Color.RED if p['stock'] <= 5 else Color.GREEN
        print(f"{p['id']:<4} | {p['name']:<30} | {stock_color}{p['stock']:<8}{Color.RESET} | {p['price']:<10}")
    print("-" * 60)

def main():
    banner()
    server = MockServer()
    query_client = QueryClient(server)
    store = EnterpriseStore()
    mutation_mgr = OptimisticMutationManager(query_client, store, server)

    while True:
        print(f"\n{Color.BOLD}--- PANEL KENDALI ARSITEKTUR STATE REACT ---{Color.RESET}")
        net_color = Color.GREEN if store.state['network_status'] == 'online' else Color.RED
        print(f"Koneksi: {net_color}{store.state['network_status'].upper()}{Color.RESET} | Server Failure Rate: {Color.MAGENTA}{server.failure_rate * 100:.0f}%{Color.RESET} | Offline Queue: {len(mutation_mgr.offline_queue)}")
        print("1. [TanStack Query] Fetch / Revalidate Products (Check SWR & Cache)")
        print("2. [Optimistic Mutation] Ubah Stock Produk (Zero-Latency Simulation)")
        print("3. [Simulasi Gangguan] Toggle Server Error Failure Rate (0% <-> 100%)")
        print("4. [Network Resilience] Toggle Online / Offline Status")
        print("5. [Offline Sync] Flush Offline Action Queue ke Server")
        print("6. [Cache Inspect] Lihat Isi Raw Cache & Metadata TanStack Query")
        print("7. Keluar")

        choice = input(f"\n{Color.CYAN}Pilih opsi (1-7): {Color.RESET}").strip()

        if choice == "1":
            print(f"\n{Color.BOLD}--- EXECUTE USEQUERY('products') ---{Color.RESET}")
            try:
                data = query_client.fetch_query("products")
                render_product_table(data)
            except Exception as e:
                print(f"{Color.RED}Error saat fetching: {e}{Color.RESET}")

        elif choice == "2":
            cache_entry = query_client.cache.get("products")
            if not cache_entry:
                print(f"{Color.YELLOW}Harap jalankan opsi 1 (Fetch) terlebih dahulu agar cache terisi.{Color.RESET}")
                continue
            render_product_table(cache_entry.data)
            try:
                pid = int(input(f"{Color.CYAN}Masukkan Product ID yang ingin diubah stock-nya: {Color.RESET}"))
                new_stk = int(input(f"{Color.CYAN}Masukkan jumlah Stock baru: {Color.RESET}"))
                mutation_mgr.mutate_stock_optimistic(pid, new_stk)
                print("\nKeadaan Data di UI setelah siklus mutasi:")
                render_product_table(query_client.cache["products"].data)
            except ValueError:
                print(f"{Color.RED}Input angka tidak valid!{Color.RESET}")

        elif choice == "3":
            server.failure_rate = 1.0 if server.failure_rate == 0.0 else 0.0
            status_text = "100% (SETIAP REQUEST GAGAL)" if server.failure_rate == 1.0 else "0% (SEMUA REQUEST SUKSES)"
            print(f"{Color.MAGENTA}  ⚙️ Server Failure Rate diubah menjadi: {Color.BOLD}{status_text}{Color.RESET}")

        elif choice == "4":
            current_net = store.state["network_status"]
            new_net = "offline" if current_net == "online" else "online"
            store.dispatch("SET_NETWORK_STATUS", new_net)
            print(f"{Color.YELLOW}  📶 Status Jaringan berubah menjadi: {new_net.upper()}{Color.RESET}")

        elif choice == "5":
            mutation_mgr.flush_offline_queue()

        elif choice == "6":
            print(f"\n{Color.BOLD}--- INSPEKSI METADATA QUERY CACHE ---{Color.RESET}")
            for k, entry in query_client.cache.items():
                age = time.time() - entry.updated_at
                stale_badge = f"{Color.RED}[STALE]{Color.RESET}" if entry.is_stale else f"{Color.GREEN}[FRESH]{Color.RESET}"
                print(f"Key: {Color.BOLD}{k}{Color.RESET} | Status: {stale_badge} | Age: {age:.2f}s | StaleTime: {entry.stale_time}s")
                print(f"Raw Items Count: {len(entry.data)}")

        elif choice == "7":
            print(f"{Color.GREEN}Terima kasih telah menggunakan lab simulasi state architecture! Goodbye.{Color.RESET}")
            sys.exit(0)
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}")

if __name__ == "__main__":
    main()
