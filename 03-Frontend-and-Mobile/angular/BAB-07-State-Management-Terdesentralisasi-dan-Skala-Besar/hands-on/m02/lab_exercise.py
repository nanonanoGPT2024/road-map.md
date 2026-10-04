#!/usr/bin/env python3
"""
Lab Hands-on: Decentralized & Large-Scale State Management (Angular Pattern)
Bab: 07 - Modul 02 Deep Dive

Simulasi arsitektur state management skala besar terdesentralisasi
yang terinspirasi oleh NgRx Feature Stores, ComponentStore, dan Signals.
Memodelkan dynamic slice registration, memoized selectors, reactive action
dispatchers, side-effects, dan optimistic updates dengan rollback engine.
"""

import copy
import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# --- ANSI Terminal Colors ---
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"

def log_info(module: str, msg: str):
    print(f"{TermColor.CYAN}[INFO]{TermColor.RESET} {TermColor.BOLD}[{module}]{TermColor.RESET} {msg}")

def log_success(module: str, msg: str):
    print(f"{TermColor.GREEN}[SUCCESS]{TermColor.RESET} {TermColor.BOLD}[{module}]{TermColor.RESET} {msg}")

def log_warn(module: str, msg: str):
    print(f"{TermColor.YELLOW}[WARN]{TermColor.RESET} {TermColor.BOLD}[{module}]{TermColor.RESET} {msg}")

def log_error(module: str, msg: str):
    print(f"{TermColor.RED}[ERROR]{TermColor.RESET} {TermColor.BOLD}[{module}]{TermColor.RESET} {msg}")

def log_state(module: str, state_dict: dict):
    payload = json.dumps(state_dict, indent=2)
    print(f"{TermColor.MAGENTA}[STATE DUMP] {module}:{TermColor.RESET}\n{payload}")

# --- Data Structures Core ---
@dataclass
class Action:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    origin: str = "GLOBAL"

class MemoizedSelector:
    """
    Meniru createSelector di NgRx: Menghitung hasil komputasi turunan
    hanya ketika slice state input mengalami mutasi referensial.
    """
    def __init__(self, projection_fn: Callable[[Dict[str, Any]], Any]):
        self._projection_fn = projection_fn
        self._last_state_hash: Optional[str] = None
        self._last_result: Any = None
        self.cache_hits = 0
        self.cache_misses = 0

    def _compute_hash(self, state: Dict[str, Any]) -> str:
        serialized = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

    def select(self, state: Dict[str, Any]) -> Any:
        current_hash = self._compute_hash(state)
        if current_hash == self._last_state_hash:
            self.cache_hits += 1
            return self._last_result

        self.cache_misses += 1
        self._last_state_hash = current_hash
        self._last_result = self._projection_fn(state)
        return self._last_result

# --- Feature Store Pattern (ComponentStore / Slice Pattern) ---
class FeatureStore:
    """
    Memodelkan isolated domain slice dalam arsitektur state terdesentralisasi.
    Mendukung patchState atomik, history tracking, dan optimistic rollback.
    """
    def __init__(self, slice_name: str, initial_state: Dict[str, Any]):
        self.slice_name = slice_name
        self._state: Dict[str, Any] = copy.deepcopy(initial_state)
        self._history: List[Dict[str, Any]] = [copy.deepcopy(initial_state)]
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.RLock()

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def patch_state(self, partial_or_fn: Any, reason: str = "PATCH") -> None:
        """Atomic state update (mirip ComponentStore.patchState/updater)."""
        with self._lock:
            old_state = copy.deepcopy(self._state)
            if callable(partial_or_fn):
                new_state = partial_or_fn(copy.deepcopy(self._state))
            elif isinstance(partial_or_fn, dict):
                new_state = copy.deepcopy(self._state)
                new_state.update(partial_or_fn)
            else:
                raise ValueError("patch_state hanya menerima dict atau updater function.")

            self._state = new_state
            self._history.append(copy.deepcopy(new_state))
            log_info(f"Store:{self.slice_name}", f"State ditransformasikan [{reason}]")
            self._notify_subscribers()

    def rollback(self, steps: int = 1) -> bool:
        """Optimistic rollback jika downstream effect gagal."""
        with self._lock:
            if len(self._history) <= steps:
                log_warn(f"Store:{self.slice_name}", "Riwayat state tidak cukup untuk rollback.")
                return False
            for _ in range(steps):
                self._history.pop()
            self._state = copy.deepcopy(self._history[-1])
            log_warn(f"Store:{self.slice_name}", f"State di-rollback ke snapshot sebelumnya.")
            self._notify_subscribers()
            return True

    def subscribe(self, subscriber: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._subscribers.append(subscriber)

    def _notify_subscribers(self) -> None:
        current_state = copy.deepcopy(self._state)
        for sub in self._subscribers:
            try:
                sub(current_state)
            except Exception as e:
                log_error(f"Store:{self.slice_name}", f"Kesalahan listener: {str(e)}")

# --- Root Store Coordinator (Decentralized Manager) ---
class DecentralizedStoreRegistry:
    """
    Root State Registry yang mengizinkan isolated feature modules
    meregistrasikan domain store mereka secara modular/lazy-loaded.
    """
    def __init__(self):
        self._stores: Dict[str, FeatureStore] = {}
        self._effects: Dict[str, List[Callable[[Action], Optional[Action]]]] = {}
        self._action_pipeline: List[Action] = []
        self._lock = threading.Lock()

    def register_feature(self, store: FeatureStore) -> None:
        with self._lock:
            if store.slice_name in self._stores:
                raise ValueError(f"Slice '{store.slice_name}' sudah terdaftar!")
            self._stores[store.slice_name] = store
            log_success("StoreRegistry", f"Dynamic Feature Slice '{store.slice_name}' berhasil dimuat.")

    def get_feature(self, slice_name: str) -> FeatureStore:
        with self._lock:
            if slice_name not in self._stores:
                raise KeyError(f"Feature Slice '{slice_name}' tidak ditemukan.")
            return self._stores[slice_name]

    def register_effect(self, action_type: str, effect_fn: Callable[[Action], Optional[Action]]) -> None:
        """Mirip NgRx Effects: Mendengarkan action spesifik dan memicu side-effect."""
        with self._lock:
            if action_type not in self._effects:
                self._effects[action_type] = []
            self._effects[action_type].append(effect_fn)

    def dispatch(self, action: Action) -> None:
        with self._lock:
            self._action_pipeline.append(action)
            log_info("Dispatcher", f"Action: {TermColor.BOLD}{action.type}{TermColor.RESET} dari [{action.origin}]")

        # Jalankan asynchronous effects terdaftar
        if action.type in self._effects:
            for effect in self._effects[action.type]:
                threading.Thread(target=self._run_effect_worker, args=(effect, action)).start()

    def _run_effect_worker(self, effect_fn: Callable[[Action], Optional[Action]], triggering_action: Action) -> None:
        try:
            result_action = effect_fn(triggering_action)
            if result_action:
                self.dispatch(result_action)
        except Exception as err:
            log_error("EffectEngine", f"Gagal menjalankan effect untuk {triggering_action.type}: {str(err)}")

# --- Domain Projections (Selectors) ---
def select_cart_total(cart_state: Dict[str, Any]) -> float:
    time.sleep(0.005)  # Simulasi kalkulasi berat (misal tax, currency exchange)
    items = cart_state.get("items", [])
    total = sum(i["price"] * i["qty"] for i in items)
    discount = cart_state.get("discount_rate", 0.0)
    return total * (1.0 - discount)

def select_inventory_deficits(inv_state: Dict[str, Any]) -> List[str]:
    stock = inv_state.get("stock", {})
    return [sku for sku, qty in stock.items() if qty < 3]

# --- Main Hands-on Lab Simulation ---
def main():
    print(f"\n{TermColor.BOLD}{TermColor.BLUE}======================================================================{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.BLUE}  LAB: DECENTRALIZED STATE MANAGEMENT (ANGULAR ARCHITECTURE PATTERN)  {TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.BLUE}======================================================================{TermColor.RESET}\n")

    registry = DecentralizedStoreRegistry()

    # 1. Modular Slice Initialization (Micro-frontend / Feature Stores)
    log_info("Setup", "Inisialisasi Feature Stores mandiri...")

    cart_store = FeatureStore("CartSlice", {
        "items": [
            {"sku": "SKU-ANGULAR-BOOK", "price": 45.0, "qty": 1},
            {"sku": "SKU-TS-MUG", "price": 15.0, "qty": 2}
        ],
        "discount_rate": 0.10,
        "is_checking_out": False
    })

    inventory_store = FeatureStore("InventorySlice", {
        "stock": {
            "SKU-ANGULAR-BOOK": 12,
            "SKU-TS-MUG": 2,
            "SKU-RXJS-STICKER": 50
        },
        "reserved": {}
    })

    registry.register_feature(cart_store)
    registry.register_feature(inventory_store)

    # 2. Selectors Memoization Demonstration
    log_info("Selectors", "Inisialisasi Memoized Selectors...")
    cart_selector = MemoizedSelector(select_cart_total)
    inventory_selector = MemoizedSelector(select_inventory_deficits)

    # Kalkulasi Pertama (Miss)
    total_1 = cart_selector.select(cart_store.get_state())
    log_info("CartSelector", f"Total Belanja: ${total_1:.2f} (Hits: {cart_selector.cache_hits}, Misses: {cart_selector.cache_misses})")

    # Kalkulasi Kedua tanpa perubahan state (Hit)
    total_2 = cart_selector.select(cart_store.get_state())
    log_info("CartSelector", f"Evaluasi ulang tanpa mutasi: ${total_2:.2f} (Hits: {cart_selector.cache_hits}, Misses: {cart_selector.cache_misses})")

    # 3. Efek & Optimistic Updates dengan Rollback Simulation
    # Skenario Checkout:
    # 1. Set is_checking_out = True di Cart
    # 2. Kurangi stok di Inventory (Side Effect)
    # 3. Bila stok tidak mencukupi, rollback perubahan cart dan batalkan checkout.

    def checkout_effect(action: Action) -> Optional[Action]:
        sku = action.payload.get("sku")
        qty = action.payload.get("qty", 1)

        log_info("EffectEngine", f"Side-effect menvalidasi stok backend untuk {sku} x{qty}...")
        time.sleep(0.1)  # Simulasi latency I/O HTTP

        inv = registry.get_feature("InventorySlice")
        cart = registry.get_feature("CartSlice")
        inv_state = inv.get_state()
        available = inv_state["stock"].get(sku, 0)

        if available >= qty:
            # Sukses: Commit state pemotongan
            def updater(s):
                s["stock"][sku] -= qty
                s["reserved"][sku] = s["reserved"].get(sku, 0) + qty
                return s
            inv.patch_state(updater, reason=f"Stock Reserved for {sku}")
            return Action(type="[Checkout] SUCCESS", payload={"sku": sku, "qty": qty}, origin="CheckoutEffect")
        else:
            # Gagal: Rollback status cart
            log_error("EffectEngine", f"Stok tidak memadai untuk {sku}! Stok tersisa: {available}, diminta: {qty}")
            cart.rollback(steps=1)
            return Action(type="[Checkout] FAILED", payload={"sku": sku, "reason": "OUT_OF_STOCK"}, origin="CheckoutEffect")

    registry.register_effect("[Cart] INITIATE_CHECKOUT", checkout_effect)

    # 4. Skenario Transaksi Sukses
    print(f"\n{TermColor.BOLD}--- SKENARIO 1: Mutasi Normal & Transaksi Valid ---{TermColor.RESET}")
    # Tambah item
    def add_item_updater(s):
        s["items"].append({"sku": "SKU-RXJS-STICKER", "price": 5.0, "qty": 4})
        return s

    cart_store.patch_state(add_item_updater, reason="Add Stickers")
    new_total = cart_selector.select(cart_store.get_state())
    log_info("CartSelector", f"Total Baru (Cache Missed): ${new_total:.2f} (Hits: {cart_selector.cache_hits}, Misses: {cart_selector.cache_misses})")

    # Trigger Checkout untuk item dengan stok cukup (Sticker)
    cart_store.patch_state({"is_checking_out": True}, reason="Optimistic Locking Cart")
    registry.dispatch(Action(
        type="[Cart] INITIATE_CHECKOUT",
        payload={"sku": "SKU-RXJS-STICKER", "qty": 10},
        origin="CartComponent"
    ))

    time.sleep(0.2)  # Menunggu thread side-effect selesai

    # 5. Skenario Transaksi Gagal & Optimistic Rollback
    print(f"\n{TermColor.BOLD}--- SKENARIO 2: Kegagalan Transaksi & Optimistic Rollback ---{TermColor.RESET}")
    # Simpan snapshot sebelum checkout bermasalah
    log_info("CartComponent", "Pengguna mencoba checkout produk dengan stok kurang (SKU-TS-MUG)...")
    cart_store.patch_state({"is_checking_out": True}, reason="Optimistic Locking Cart (Overdraft Attempt)")

    registry.dispatch(Action(
        type="[Cart] INITIATE_CHECKOUT",
        payload={"sku": "SKU-TS-MUG", "qty": 10},  # Stok cuma ada 2
        origin="CartComponent"
    ))

    time.sleep(0.2)  # Menunggu thread side-effect memproses dan trigger rollback

    # 6. Evaluasi Akhir State & Selector Audit
    print(f"\n{TermColor.BOLD}--- AUDIT STATE TERDESENTRALISASI AKHIR ---{TermColor.RESET}")
    log_state("CartSlice Final State", cart_store.get_state())
    log_state("InventorySlice Final State", inventory_store.get_state())

    deficits = inventory_selector.select(inventory_store.get_state())
    log_warn("InventorySelector", f"Item dengan stok kritis (< 3): {deficits}")

    print(f"\n{TermColor.BOLD}Statistik Selector Memoization:{TermColor.RESET}")
    print(f" - Cart Selector Total Hits   : {cart_selector.cache_hits}")
    print(f" - Cart Selector Total Misses : {cart_selector.cache_misses}")
    print(f" - Inventory Selector Misses  : {inventory_selector.cache_misses}")

    log_success("System", "Lab Validasi Decentralized Store Selesai secara Deterministik.\n")

if __name__ == "__main__":
    main()