#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur State Management Skala Besar (Pinia / Vue)
Materi: BAB-06 State Management Skala Besar
Deskripsi:
  Simulasi teknis konsep fondasi reactive store, modular pinia store,
  getters, actions, batch mutation ($patch), subscriptions ($subscribe/$onAction),
  serta integrasi cross-store multi-modul enterprise.
"""

import sys
import time
import copy
from typing import Callable, Any, Dict, List, Optional


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def print_banner(title: str):
    print(f"\n{ANSI.BOLD}{ANSI.BG_BLUE}{' ' * 4}{title.upper()}{' ' * 4}{ANSI.RESET}\n")


def print_success(msg: str):
    print(f"{ANSI.GREEN}[OK]{ANSI.RESET} {msg}")


def print_info(msg: str):
    print(f"{ANSI.CYAN}[INFO]{ANSI.RESET} {msg}")


def print_warn(msg: str):
    print(f"{ANSI.YELLOW}[WARN]{ANSI.RESET} {msg}")


def print_event(scope: str, msg: str):
    print(f"{ANSI.MAGENTA}[{scope}]{ANSI.RESET} {msg}")


class PiniaStore:
    """Simulasi Store Pinia lengkap dengan State, Getters, Actions, Patch, & Plugins."""

    def __init__(self, store_id: str, state_factory: Callable[[], Dict[str, Any]], getters: Dict[str, Callable], actions: Dict[str, Callable]):
        self.store_id = store_id
        self._raw_state: Dict[str, Any] = state_factory()
        self._getters_def = getters
        self._actions_def = actions
        self._subscribers: List[Callable[[Dict[str, Any], Dict[str, Any]], None]] = []
        self._action_subscribers: List[Callable[[str, tuple, dict, str], None]] = []

    @property
    def state(self) -> Dict[str, Any]:
        return self._raw_state

    def get(self, key: str) -> Any:
        return self._raw_state.get(key)

    def compute(self, getter_name: str) -> Any:
        if getter_name in self._getters_def:
            return self._getters_def[getter_name](self)
        raise AttributeError(f"Getter '{getter_name}' tidak ditemukan pada store '{self.store_id}'.")

    def patch(self, partial_or_fn: Any) -> None:
        """Simulasi $patch Pinia untuk atomic batch mutation."""
        old_state = copy.deepcopy(self._raw_state)
        mutation_meta = {"type": "patch", "store_id": self.store_id}

        if callable(partial_or_fn):
            partial_or_fn(self._raw_state)
        elif isinstance(partial_or_fn, dict):
            for k, v in partial_or_fn.items():
                self._raw_state[k] = v
        else:
            raise TypeError("$patch menerima dict perubahan atau callback fungsi mutating.")

        # Notify mutation subscribers
        for sub in self._subscribers:
            sub(mutation_meta, copy.deepcopy(self._raw_state))

    def dispatch(self, action_name: str, *args, **kwargs) -> Any:
        """Simulasi eksekusi Action dengan hook lifecycle $onAction."""
        if action_name not in self._actions_def:
            raise AttributeError(f"Action '{action_name}' tidak dideklarasikan di store '{self.store_id}'.")

        # Lifecycle before action
        for sub in self._action_subscribers:
            sub(action_name, args, kwargs, "before")

        try:
            result = self._actions_def[action_name](self, *args, **kwargs)
            # Lifecycle after action
            for sub in self._action_subscribers:
                sub(action_name, args, kwargs, "after")
            return result
        except Exception as err:
            # Lifecycle error action
            for sub in self._action_subscribers:
                sub(action_name, args, kwargs, f"error: {str(err)}")
            raise err

    def subscribe(self, callback: Callable[[Dict[str, Any], Dict[str, Any]], None]):
        """Plugin subscriber untuk setiap perubahan state (e.g. LocalStorage sync)."""
        self._subscribers.append(callback)

    def on_action(self, callback: Callable[[str, tuple, dict, str], None]):
        """Plugin subscriber untuk audit log dispatch action."""
        self._action_subscribers.append(callback)


class PiniaRoot:
    """Root Registry untuk seluruh store aplikasi."""

    def __init__(self):
        self._stores: Dict[str, PiniaStore] = {}

    def register(self, store: PiniaStore):
        self._stores[store.store_id] = store

    def get_store(self, store_id: str) -> PiniaStore:
        if store_id not in self._stores:
            raise KeyError(f"Store '{store_id}' belum didaftarkan di root registry.")
        return self._stores[store_id]


# Inisialisasi Root Pinia
pinia = PiniaRoot()


# -------------------------------------------------------------
# Modul Store 1: Auth Store (Authentication & Role Perm)
# -------------------------------------------------------------
def auth_state():
    return {
        "user": None,
        "token": None,
        "role": "guest",
        "session_expires": None
    }


auth_getters = {
    "is_authenticated": lambda store: store.get("token") is not None,
    "user_display": lambda store: store.get("user") or "Tamu Anonim",
    "can_checkout": lambda store: store.get("token") is not None and store.get("role") in ["customer", "vip"]
}


def auth_action_login(store: PiniaStore, username: str, role: str = "customer"):
    print_event("AuthStore", f"Authenticating {ANSI.BOLD}{username}{ANSI.RESET} with role '{role}'...")
    token = f"jwt_{username}_session_{int(time.time())}"
    store.patch({
        "user": username,
        "token": token,
        "role": role,
        "session_expires": time.time() + 3600
    })
    return True


def auth_action_logout(store: PiniaStore):
    print_event("AuthStore", "Invalidating token and clearing user session...")
    store.patch(auth_state())
    return True


auth_actions = {
    "login": auth_action_login,
    "logout": auth_action_logout
}

auth_store = PiniaStore("auth", auth_state, auth_getters, auth_actions)
pinia.register(auth_store)


# -------------------------------------------------------------
# Modul Store 2: Cart Store (E-Commerce Multi-store Coordination)
# -------------------------------------------------------------
def cart_state():
    return {
        "items": [],
        "discount_code": None,
        "discount_percent": 0,
        "is_locked": False
    }


cart_getters = {
    "item_count": lambda store: sum(item["qty"] for item in store.get("items")),
    "subtotal": lambda store: sum(item["price"] * item["qty"] for item in store.get("items")),
    "total_price": lambda store: (
        sum(item["price"] * item["qty"] for item in store.get("items")) * (1 - store.get("discount_percent") / 100.0)
    ),
    "summary_breakdown": lambda store: {
        "count": store.compute("item_count"),
        "subtotal": store.compute("subtotal"),
        "total": store.compute("total_price")
    }
}


def cart_action_add_item(store: PiniaStore, product_name: str, price: float, qty: int = 1):
    def mutate(state):
        existing = next((i for i in state["items"] if i["name"] == product_name), None)
        if existing:
            existing["qty"] += qty
        else:
            state["items"].append({"name": product_name, "price": price, "qty": qty})

    store.patch(mutate)


def cart_action_apply_voucher(store: PiniaStore, code: str):
    vouchers = {
        "PINIA10": 10,
        "VUEPRO30": 30,
        "ENTERPRISE50": 50
    }
    if code in vouchers:
        store.patch({
            "discount_code": code,
            "discount_percent": vouchers[code]
        })
        print_success(f"Voucher {code} diaplikasikan: Diskon {vouchers[code]}%")
        return True
    else:
        raise ValueError(f"Kode voucher '{code}' tidak valid!")


def cart_action_checkout(store: PiniaStore):
    # Cross-Store dependency: Cart store reads Auth Store
    auth = pinia.get_store("auth")
    if not auth.compute("is_authenticated"):
        raise PermissionError("Checkout gagal: Pengguna wajib login terlebih dahulu!")

    if not auth.compute("can_checkout"):
        raise PermissionError(f"Akses ditolak: Role '{auth.get('role')}' tidak memiliki izin transaksi!")

    if store.compute("item_count") == 0:
        raise ValueError("Keranjang belanja kosong! Tidak dapat melakukan checkout.")

    total = store.compute("total_price")
    customer = auth.compute("user_display")
    print_event("CheckoutEngine", f"Processing transaction: Rp{total:,.2f} for user '{customer}'")

    # Atomic clear cart
    store.patch({"items": [], "discount_code": None, "discount_percent": 0})
    return {"order_id": f"ORD-{int(time.time())}", "total": total, "customer": customer}


cart_actions = {
    "add_item": cart_action_add_item,
    "apply_voucher": cart_action_apply_voucher,
    "checkout": cart_action_checkout
}

cart_store = PiniaStore("cart", cart_state, cart_getters, cart_actions)
pinia.register(cart_store)


# -------------------------------------------------------------
# Pinia Plugins: Audit Devtools Logger & Persistence Tracker
# -------------------------------------------------------------
def devtools_plugin(store: PiniaStore):
    def on_mutate(mutation, new_state):
        keys = list(new_state.keys())
        print(f"  {ANSI.DIM}[Devtools Mutation]{ANSI.RESET} Store '{mutation['store_id']}' updated state keys: {keys}")

    def on_act(name, args, kwargs, phase):
        status_color = ANSI.GREEN if phase == "after" else (ANSI.RED if "error" in phase else ANSI.YELLOW)
        print(f"  {ANSI.DIM}[Pinia $onAction]{ANSI.RESET} {store.store_id}.{name}() -> {status_color}{phase}{ANSI.RESET}")

    store.subscribe(on_mutate)
    store.on_action(on_act)


# Pasang Plugin ke semua store
devtools_plugin(auth_store)
devtools_plugin(cart_store)


# -------------------------------------------------------------
# Demo Skrip & Interactive Handler
# -------------------------------------------------------------
def run_automated_suite():
    print_banner("SIMULASI STATE MANAGEMENT SKALA BESAR (VUE 3 / PINIA)")

    print(f"{ANSI.BOLD}Langkah 1: Cek State Awal Auth & Cart{ANSI.RESET}")
    print_info(f"Auth Status: Authenticated? {auth_store.compute('is_authenticated')}")
    print_info(f"Cart Total Items: {cart_store.compute('item_count')}")

    print(f"\n{ANSI.BOLD}Langkah 2: Tambah Item ke Cart Store (Action + Patch){ANSI.RESET}")
    cart_store.dispatch("add_item", "Kursus Vue 3 Enterprise", 450000, 1)
    cart_store.dispatch("add_item", "Buku Pola Desain Pinia", 185000, 2)
    print_success(f"Items Count: {cart_store.compute('item_count')}")
    print_success(f"Subtotal: Rp{cart_store.compute('subtotal'):,.2f}")

    print(f"\n{ANSI.BOLD}Langkah 3: Coba Checkout Tanpa Login (Verifikasi Guards){ANSI.RESET}")
    try:
        cart_store.dispatch("checkout")
    except PermissionError as e:
        print_warn(f"Tertangkap Guard: {str(e)}")

    print(f"\n{ANSI.BOLD}Langkah 4: Login Pengguna via AuthStore (Dispatched Action){ANSI.RESET}")
    auth_store.dispatch("login", "developer_vue", "customer")
    print_success(f"Login sukses sebagai: {auth_store.compute('user_display')} ({auth_store.get('role')})")

    print(f"\n{ANSI.BOLD}Langkah 5: Terapkan Voucher Promo Diskon ($patch){ANSI.RESET}")
    cart_store.dispatch("apply_voucher", "VUEPRO30")
    print_info(f"Subtotal Sebelum Diskon : Rp{cart_store.compute('subtotal'):,.2f}")
    print_info(f"Total Setelah Diskon 30%: Rp{cart_store.compute('total_price'):,.2f}")

    print(f"\n{ANSI.BOLD}Langkah 6: Eksekusi Checkout Cross-Store Berhasil{ANSI.RESET}")
    invoice = cart_store.dispatch("checkout")
    print_success(f"Faktur Berhasil Terbit! ID: {invoice['order_id']}, Bayar: Rp{invoice['total']:,.2f}")
    print_info(f"Sisa Keranjang Belanja: {cart_store.compute('item_count')} item")

    print_banner("PENGUJIAN VALIDASI ARSITEKTUR SELESAI DENGAN SUKSES")


def interactive_mode():
    while True:
        print(f"\n{ANSI.BOLD}--- MENU INTERAKTIF STATE MANAGEMENT ---{ANSI.RESET}")
        print("1. Tampilkan Ringkasan State (Auth & Cart)")
        print("2. Tambah Item ke Cart")
        print("3. Terapkan Voucher Diskon")
        print("4. Login Pengguna")
        print("5. Logout Pengguna")
        print("6. Checkout Belanja (Cross-Store Action)")
        print("7. Jalankan Otomasi Pengujian Penuh")
        print("0. Keluar")

        choice = input(f"{ANSI.YELLOW}Pilih opsi [0-7]: {ANSI.RESET}").strip()

        if choice == "1":
            print(f"\n{ANSI.CYAN}=== STATE AUTH ==={ANSI.RESET}")
            print(f"User        : {auth_store.compute('user_display')}")
            print(f"Role        : {auth_store.get('role')}")
            print(f"Logged In   : {auth_store.compute('is_authenticated')}")
            print(f"\n{ANSI.CYAN}=== STATE CART ==={ANSI.RESET}")
            print(f"Item Count  : {cart_store.compute('item_count')}")
            print(f"Voucher     : {cart_store.get('discount_code')} ({cart_store.get('discount_percent')}%)")
            print(f"Subtotal    : Rp{cart_store.compute('subtotal'):,.2f}")
            print(f"Grand Total : Rp{cart_store.compute('total_price'):,.2f}")
        elif choice == "2":
            name = input("Nama barang: ").strip() or "Item Sampel"
            try:
                price = float(input("Harga satuan: ").strip() or "50000")
                qty = int(input("Kuantitas: ").strip() or "1")
                cart_store.dispatch("add_item", name, price, qty)
                print_success(f"Item {name} ditambahkan.")
            except ValueError:
                print_warn("Input angka tidak valid!")
        elif choice == "3":
            code = input("Masukkan kode voucher (e.g. PINIA10, VUEPRO30): ").strip()
            try:
                cart_store.dispatch("apply_voucher", code)
            except Exception as e:
                print_warn(str(e))
        elif choice == "4":
            uname = input("Username: ").strip() or "frontend_dev"
            role = input("Role (customer / vip / guest): ").strip() or "customer"
            auth_store.dispatch("login", uname, role)
        elif choice == "5":
            auth_store.dispatch("logout")
            print_success("User berhasil logout.")
        elif choice == "6":
            try:
                inv = cart_store.dispatch("checkout")
                print_success(f"Transaksi Selesai! ID: {inv['order_id']}")
            except Exception as e:
                print_warn(f"Gagal Checkout: {str(e)}")
        elif choice == "7":
            run_automated_suite()
        elif choice == "0":
            print("Keluar dari program.")
            break
        else:
            print_warn("Pilihan tidak valid.")


if __name__ == "__main__":
    # Jika dijalankan tanpa terminal interaktif (CI/pipe), jalankan test suite otomatis
    if not sys.stdin.isatty() or "--demo" in sys.argv:
        run_automated_suite()
    else:
        # Jalankan test suite sekali kemudian tawarkan opsi interaktif
        run_automated_suite()
        try:
            interactive_mode()
        except (KeyboardInterrupt, EOFError):
            print("\nSelesai.")
