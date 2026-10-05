#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur State Management Produksi Skala Besar (Vue 3 / Pinia)
Modul: BAB-06 State Management Skala Besar - Modul 02

Fitur Simulasi Arsitektur:
1. Reactive Store Engine (State, Getters, Actions)
2. Plugin Pipeline (DevTools Logger, LocalStorage Persistence Adapter)
3. Action Subscriptions ($onAction hook dengan after/error lifecycle)
4. Optimistic UI Updates & Error Rollback Mechanism
5. Time-Travel Debugging (State Snapshots, Undo, Redo)
"""

import sys
import time
import copy
import json
from typing import Callable, Dict, Any, List, Optional

# --- ANSI Color Codes ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_BLUE = "\033[44m"


class ActionContext:
    def __init__(self, name: str, args: tuple, store: "PiniaStore"):
        self.name = name
        self.args = args
        self.store = store
        self._after_callbacks: List[Callable[[Any], None]] = []
        self._error_callbacks: List[Callable[[Exception], None]] = []

    def after(self, callback: Callable[[Any], None]):
        self._after_callbacks.append(callback)

    def on_error(self, callback: Callable[[Exception], None]):
        self._error_callbacks.append(callback)


class PiniaStore:
    def __init__(self, store_id: str, state_factory: Callable[[], Dict[str, Any]], getters: Dict[str, Callable], actions: Dict[str, Callable]):
        self.id = store_id
        self._state: Dict[str, Any] = state_factory()
        self._getters_def = getters
        self._actions_def = actions
        self._action_subscribers: List[Callable[[ActionContext], None]] = []
        self._history: List[Dict[str, Any]] = [copy.deepcopy(self._state)]
        self._history_index = 0

    @property
    def state(self) -> Dict[str, Any]:
        return self._state

    def get(self, getter_name: str) -> Any:
        if getter_name in self._getters_def:
            return self._getters_def[getter_name](self._state)
        raise KeyError(f"Getter '{getter_name}' tidak ditemukan pada store '{self.id}'")

    def patch(self, partial_or_mutator: Any):
        """Implementasi $patch modular Pinia"""
        self._record_history()
        if callable(partial_or_mutator):
            partial_or_mutator(self._state)
        elif isinstance(partial_or_mutator, dict):
            self._state.update(partial_or_mutator)
        self._record_history()

    def _record_history(self):
        # Truncate forward history if branching after undo
        if self._history_index < len(self._history) - 1:
            self._history = self._history[: self._history_index + 1]
        self._history.append(copy.deepcopy(self._state))
        self._history_index = len(self._history) - 1

    def subscribe_action(self, callback: Callable[[ActionContext], None]):
        """Implementasi store.$onAction hook"""
        self._action_subscribers.append(callback)

    def dispatch(self, action_name: str, *args, **kwargs) -> Any:
        if action_name not in self._actions_def:
            raise KeyError(f"Action '{action_name}' tidak terdaftar pada store '{self.id}'")

        ctx = ActionContext(action_name, args, self)
        for sub in self._action_subscribers:
            sub(ctx)

        try:
            fn = self._actions_def[action_name]
            result = fn(self, *args, **kwargs)
            for after_hook in ctx._after_callbacks:
                after_hook(result)
            return result
        except Exception as err:
            for err_hook in ctx._error_callbacks:
                err_hook(err)
            raise err

    def undo(self) -> bool:
        if self._history_index > 0:
            self._history_index -= 1
            self._state = copy.deepcopy(self._history[self._history_index])
            return True
        return False

    def redo(self) -> bool:
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._state = copy.deepcopy(self._history[self._history_index])
            return True
        return False


# --- Store Setup (E-Commerce Order & Inventory Module) ---

def initial_state() -> Dict[str, Any]:
    return {
        "items": [
            {"id": "sku-101", "name": "Vite Enterprise Guide", "price": 250000, "qty": 1},
            {"id": "sku-102", "name": "Pinia Architecture Blueprint", "price": 380000, "qty": 2},
        ],
        "applied_coupon": None,
        "is_syncing": False,
        "last_synced_at": None,
    }


def getter_total_count(state: Dict[str, Any]) -> int:
    return sum(item["qty"] for item in state["items"])


def getter_subtotal(state: Dict[str, Any]) -> int:
    return sum(item["price"] * item["qty"] for item in state["items"])


def getter_final_price(state: Dict[str, Any]) -> int:
    subtotal = getter_subtotal(state)
    if state["applied_coupon"] == "VUE3PROMO":
        return int(subtotal * 0.85)  # Diskon 15%
    return subtotal


# --- Store Actions with Optimistic UI & Network Simulation ---

def action_add_item_optimistic(store: PiniaStore, sku: str, name: str, price: int, qty: int = 1, simulate_fail: bool = False):
    print(f"{YELLOW}⚡ [Optimistic UI] Menambahkan item secara instan ke state lokal...{RESET}")
    backup_state = copy.deepcopy(store.state)

    # 1. Mutasi lokal instan (User tidak merasakan delay UI)
    existing = next((i for i in store.state["items"] if i["id"] == sku), None)
    if existing:
        existing["qty"] += qty
    else:
        store.state["items"].append({"id": sku, "name": name, "price": price, "qty": qty})
    store._record_history()
    store.state["is_syncing"] = True

    # 2. Simulasi Latensi Jaringan Asynchronous
    time.sleep(0.4)

    # 3. Validasi kegagalan server
    if simulate_fail:
        store.state.clear()
        store.state.update(backup_state)
        store.state["is_syncing"] = False
        raise RuntimeError(f"Server backend menolak SKU {sku} (Out of Stock / Concurrency Lock).")

    store.state["is_syncing"] = False
    store.state["last_synced_at"] = time.strftime("%H:%M:%S")
    return {"status": "SUCCESS", "sku": sku}


def action_apply_coupon(store: PiniaStore, code: str):
    valid_coupons = ["VUE3PROMO", "PINIAMASTER"]
    if code not in valid_coupons:
        raise ValueError(f"Kode kupon '{code}' tidak valid atau sudah kedaluwarsa.")
    store.patch({"applied_coupon": code})
    return {"code": code, "discount": "15%"}


def action_clear_cart(store: PiniaStore):
    store.patch({"items": [], "applied_coupon": None})


# --- Store Construction & Plugin Registration ---

def create_order_store() -> PiniaStore:
    store = PiniaStore(
        store_id="order-cart",
        state_factory=initial_state,
        getters={
            "total_count": getter_total_count,
            "subtotal": getter_subtotal,
            "final_price": getter_final_price,
        },
        actions={
            "addItemOptimistic": action_add_item_optimistic,
            "applyCoupon": action_apply_coupon,
            "clearCart": action_clear_cart,
        }
    )

    # Plugin 1: Pinia DevTools Action Audit Logger
    def devtools_logger_plugin(ctx: ActionContext):
        start_time = time.time()
        print(f"{MAGENTA}🔍 [DevTools Plugin] Action '$dispatch({ctx.name})' dipanggil.{RESET}")

        def on_success(res):
            duration = (time.time() - start_time) * 1000
            print(f"{GREEN}✔ [DevTools Plugin] Action '{ctx.name}' selesai dalam {duration:.1f}ms. Return: {res}{RESET}")

        def on_fail(err):
            print(f"{RED}✖ [DevTools Plugin] Action '{ctx.name}' GAGAL! Error: {err}{RESET}")

        ctx.after(on_success)
        ctx.on_error(on_fail)

    store.subscribe_action(devtools_logger_plugin)
    return store


# --- Interactive Terminal UI ---

def print_header():
    print(f"\n{BG_BLUE}{BOLD} === SIMULATOR STATE MANAGEMENT VUE 3 / PINIA (BAB-06) === {RESET}")
    print(f"{CYAN}Arsitektur Skala Besar: Reactive Stores, Optimistic UI, Plugins & Time-Travel{RESET}\n")


def display_dashboard(store: PiniaStore):
    print(f"{BOLD}--- [STATUS CURRENT STORE: {store.id}] ---{RESET}")
    print(f"Syncing State : {'Syncing...' if store.state['is_syncing'] else 'IDLE'}")
    print(f"Coupon Active : {store.state['applied_coupon'] or 'None'}")
    print(f"Last Synced   : {store.state['last_synced_at'] or 'Never'}")
    print(f"\n{BOLD}Daftar Item Keranjang:{RESET}")
    for it in store.state["items"]:
        print(f"  • [{it['id']}] {it['name']} x{it['qty']} @ Rp {it['price']:,}")

    subtotal = store.get("subtotal")
    final_price = store.get("final_price")
    total_count = store.get("total_count")

    print(f"\n{CYAN}Getters Computed:{RESET}")
    print(f"  - Total Item Qty : {total_count}")
    print(f"  - Subtotal       : Rp {subtotal:,}")
    print(f"  - Total Bayar    : {BOLD}Rp {final_price:,}{RESET}")
    print("-" * 50)


def interactive_loop():
    store = create_order_store()
    print_header()

    while True:
        display_dashboard(store)
        print(f"\n{BOLD}Pilih Skenario Interaktif:{RESET}")
        print("1. [Action Sukses] Tambah Item Baru (Optimistic UI -> Success)")
        print("2. [Action Gagal] Tambah Item dengan Simulasi Server Error (Rollback UI)")
        print("3. [Getter / Mutation] Terapkan Kupon Diskon (VUE3PROMO)")
        print("4. [Time-Travel] Undo State Sebelumnya")
        print("5. [Time-Travel] Redo State Berikutnya")
        print("6. [Reset] Kosongkan Keranjang ($patch)")
        print("0. Keluar")

        try:
            choice = input(f"\n{YELLOW}Pilihan Anda (0-6): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            sku = f"sku-{int(time.time()) % 1000}"
            try:
                store.dispatch("addItemOptimistic", sku, "Fullstack Vue 3 Mastery", 420000, 1, False)
            except Exception as e:
                print(f"{RED}Error ditangkap controller: {e}{RESET}")
        elif choice == "2":
            try:
                print(f"{YELLOW}Mencoba menambahkan item inventaris langka (Disimulasikan Gagal di Server)...{RESET}")
                store.dispatch("addItemOptimistic", "sku-999-rare", "Limited Edition GPU Merch", 9900000, 1, True)
            except Exception as e:
                print(f"{RED}UI Rollback Berhasil! State kembali aman: {e}{RESET}")
        elif choice == "3":
            try:
                store.dispatch("applyCoupon", "VUE3PROMO")
                print(f"{GREEN}Kupon 'VUE3PROMO' berhasil dipasang! (Diskon 15% dihitung otomatis oleh getter){RESET}")
            except Exception as e:
                print(f"{RED}Gagal: {e}{RESET}")
        elif choice == "4":
            if store.undo():
                print(f"{GREEN}State berhasil di-revert (Undo time-travel).{RESET}")
            else:
                print(f"{RED}Tidak ada riwayat untuk di-undo.{RESET}")
        elif choice == "5":
            if store.redo():
                print(f"{GREEN}State berhasil di-forward (Redo time-travel).{RESET}")
            else:
                print(f"{RED}Tidak ada riwayat untuk di-redo.{RESET}")
        elif choice == "6":
            store.dispatch("clearCart")
            print(f"{YELLOW}Keranjang telah dikosongkan.{RESET}")
        elif choice == "0":
            print(f"{GREEN}Simulasi selesai. Arsitektur state management berhasil divalidasi!{RESET}")
            break
        else:
            print(f"{RED}Opsi tidak dikenali! Silakan masukkan 0-6.{RESET}")
        time.sleep(0.3)


if __name__ == "__main__":
    interactive_loop()
