#!/usr/bin/env python3
"""
Lab Exercise: Next.js Data Mutation, Server Actions & Stateful Forms
Simulasi interaktif konsep fundamental Server Actions, useActionState,
useOptimistic, useFormStatus, dan Cache Revalidation (revalidatePath).
"""

import sys
import time
import copy
from typing import Dict, Any, List, Optional, Tuple

# ==============================================================================
# ANSI Color Codes untuk Terminal Styling
# ==============================================================================
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


def header(title: str) -> None:
    print(f"\n{CYAN}{BOLD}{'=' * 65}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 65}{RESET}")


def badge(label: str, bg: str = BG_BLUE) -> str:
    return f"{bg}{WHITE}{BOLD} {label} {RESET}"


# ==============================================================================
# 1. Mock Database & Data Cache Layer
# ==============================================================================
class Database:
    """Simulasi PostgreSQL/Prisma Database Store."""
    def __init__(self):
        self._items: List[Dict[str, Any]] = [
            {"id": "prod_1", "title": "Next.js Pro Guide", "price": 49.0, "stock": 10},
            {"id": "prod_2", "title": "React Server Component Handbook", "price": 35.0, "stock": 5},
            {"id": "prod_3", "title": "Fullstack TypeScript Mastery", "price": 59.0, "stock": 0},
        ]

    def find_all(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._items)

    def insert(self, title: str, price: float, stock: int) -> Dict[str, Any]:
        new_id = f"prod_{len(self._items) + 1}"
        record = {"id": new_id, "title": title, "price": price, "stock": stock}
        self._items.append(record)
        return record

    def update_stock(self, product_id: str, new_stock: int) -> Optional[Dict[str, Any]]:
        for item in self._items:
            if item["id"] == product_id:
                item["stock"] = new_stock
                return copy.deepcopy(item)
        return None


class ServerCache:
    """Simulasi Next.js Full Route Cache & Data Cache."""
    def __init__(self):
        self.tags: Dict[str, float] = {}
        self.paths: Dict[str, float] = {"/dashboard/products": time.time()}

    def revalidate_path(self, path: str) -> None:
        self.paths[path] = time.time()
        print(f"  {MAGENTA}[Next.js Cache]{RESET} revalidatePath('{path}') executed -> Cache invalidated.")

    def revalidate_tag(self, tag: str) -> None:
        self.tags[tag] = time.time()
        print(f"  {MAGENTA}[Next.js Cache]{RESET} revalidateTag('{tag}') executed -> Tag invalidated.")


# Instansiasi shared backend
db = Database()
cache = ServerCache()


# ==============================================================================
# 2. Schema Validation (Simulasi Zod)
# ==============================================================================
class ProductSchema:
    @staticmethod
    def validate(form_data: Dict[str, str]) -> Tuple[bool, Optional[Dict[str, Any]], Dict[str, str]]:
        errors: Dict[str, str] = {}
        title = form_data.get("title", "").strip()
        price_raw = form_data.get("price", "").strip()
        stock_raw = form_data.get("stock", "").strip()

        if not title or len(title) < 3:
            errors["title"] = "Title minimal harus 3 karakter."

        try:
            price = float(price_raw)
            if price <= 0:
                errors["price"] = "Price harus lebih besar dari 0."
        except ValueError:
            errors["price"] = "Price harus berupa angka desimal/integer valid."
            price = 0.0

        try:
            stock = int(stock_raw)
            if stock < 0:
                errors["stock"] = "Stock tidak boleh bernilai negatif."
        except ValueError:
            errors["stock"] = "Stock harus berupa bilangan bulat non-negatif."
            stock = 0

        if errors:
            return False, None, errors
        return True, {"title": title, "price": price, "stock": stock}, {}


# ==============================================================================
# 3. Server Actions Layer ('use server')
# ==============================================================================
def create_product_action(prev_state: Dict[str, Any], form_data: Dict[str, str]) -> Dict[str, Any]:
    """
    Simulasi Server Action signature:
    async function createProductAction(prevState: ActionState, formData: FormData)
    """
    print(f"\n{BLUE}[Server Action]{RESET} Eksekusi dipanggil di Node.js/Edge Server Environment...")
    time.sleep(0.4)

    is_valid, parsed_data, errors = ProductSchema.validate(form_data)
    if not is_valid:
        print(f"  {RED}[Zod Validation]{RESET} Validasi gagal: {errors}")
        return {
            "status": "error",
            "message": "Validasi input gagal.",
            "fieldErrors": errors,
            "data": None
        }

    # Simulasi mutasi database
    assert parsed_data is not None
    record = db.insert(parsed_data["title"], parsed_data["price"], parsed_data["stock"])
    print(f"  {GREEN}[DB Mutation]{RESET} Record disimpan: ID={record['id']} | Title='{record['title']}'")

    # Invalidate Cache
    cache.revalidate_path("/dashboard/products")
    cache.revalidate_tag("products-collection")

    return {
        "status": "success",
        "message": f"Produk '{record['title']}' berhasil dibuat!",
        "fieldErrors": {},
        "data": record
    }


def update_stock_action(product_id: str, new_stock: int, should_fail: bool = False) -> Dict[str, Any]:
    """Server Action untuk update stok dengan kemungkinan server error (untuk uji coba rollback)."""
    time.sleep(0.5)
    if should_fail:
        return {"status": "error", "message": "Database transaction timeout (Simulated Error)."}
    
    updated = db.update_stock(product_id, new_stock)
    if updated:
        cache.revalidate_path("/dashboard/products")
        return {"status": "success", "data": updated}
    return {"status": "error", "message": "Produk tidak ditemukan."}


# ==============================================================================
# 4. Client Components & Hooks Simulation (useActionState, useOptimistic, useFormStatus)
# ==============================================================================
class FormStatusHook:
    """Simulasi Hook React DOM: const { pending } = useFormStatus();"""
    def __init__(self):
        self.pending: bool = False

    def set_pending(self, state: bool):
        self.pending = state


class OptimisticUI:
    """
    Simulasi Hook React 19:
    const [optimisticState, setOptimistic] = useOptimistic(state, updateFn)
    """
    def __init__(self, current_products: List[Dict[str, Any]]):
        self.actual_state = current_products
        self.optimistic_state = copy.deepcopy(current_products)

    def apply_optimistic_update(self, product_id: str, optimistic_stock: int) -> None:
        self.optimistic_state = copy.deepcopy(self.actual_state)
        for item in self.optimistic_state:
            if item["id"] == product_id:
                item["stock"] = optimistic_stock
                item["_is_optimistic"] = True
                break

    def rollback(self) -> None:
        self.optimistic_state = copy.deepcopy(self.actual_state)

    def commit(self, updated_record: Dict[str, Any]) -> None:
        for idx, item in enumerate(self.actual_state):
            if item["id"] == updated_record["id"]:
                self.actual_state[idx] = copy.deepcopy(updated_record)
                break
        self.optimistic_state = copy.deepcopy(self.actual_state)


# ==============================================================================
# 5. Interactive Scenarios & Demos
# ==============================================================================
def demo_create_product_form():
    header("SKENARIO 1: Stateful Form (useActionState & Zod Validation)")
    print(f"{DIM}Simulasi Client Component memanggil Server Action dengan useActionState.{RESET}\n")

    form_status = FormStatusHook()
    state: Dict[str, Any] = {"status": "idle", "message": "", "fieldErrors": {}}

    print(f"Status Form Awal: {badge('IDLE', BG_BLUE)} Pending={form_status.pending}")

    title_input = input(f"{YELLOW}Masukkan Judul Produk (min 3 huruf, contoh: 'Docker Deep Dive'): {RESET}").strip()
    price_input = input(f"{YELLOW}Masukkan Harga (angka desimal/float, contoh: '45.50'): {RESET}").strip()
    stock_input = input(f"{YELLOW}Masukkan Stok Awal (integer non-negatif, contoh: '15'): {RESET}").strip()

    payload = {"title": title_input, "price": price_input, "stock": stock_input}

    # Client triggers form submission
    form_status.set_pending(True)
    print(f"\n{YELLOW}[Form Event]{RESET} Tombol Submit diklik -> {badge('useFormStatus: pending=True', BG_BLUE)}")
    print(f"{DIM}Tombol 'Submit' otomatis berstatus disabled di Client UI.{RESET}")

    # Invoke Server Action
    action_result = create_product_action(state, payload)
    state = action_result
    form_status.set_pending(False)

    print(f"\n{YELLOW}[Form State Updated]{RESET} {badge('useFormStatus: pending=False', BG_GREEN)}")
    if state["status"] == "success":
        print(f"{GREEN}{BOLD}✓ SUKSES:{RESET} {state['message']}")
        print(f"  Data Tersimpan: {state['data']}")
    else:
        print(f"{RED}{BOLD}✗ GAGAL:{RESET} {state['message']}")
        for field, err in state["fieldErrors"].items():
            print(f"  - {RED}{field}:{RESET} {err}")


def demo_optimistic_update():
    header("SKENARIO 2: Optimistic UI (useOptimistic & Error Rollback)")
    products = db.find_all()
    optimistic_hook = OptimisticUI(products)

    target_id = "prod_1"
    initial_stock = [p for p in products if p["id"] == target_id][0]["stock"]
    print(f"Produk Terpilih: {BOLD}Next.js Pro Guide{RESET} (ID: {target_id})")
    print(f"Stok Aktual Saat Ini: {BOLD}{initial_stock}{RESET}\n")

    print(f"{CYAN}Pilih mode simulasi:{RESET}")
    print("  1. Mutasi Sukses (Optimistic update diverifikasi server)")
    print("  2. Mutasi Gagal / Network Drop (Optimistic update di-rollback)")
    choice = input(f"{YELLOW}Pilihan (1/2): {RESET}").strip()
    simulate_failure = (choice == "2")

    new_stock = initial_stock + 5
    print(f"\n{BOLD}1. [Client Action]{RESET} Pengguna menambah stok +5 menjadi {new_stock}...")
    
    # Apply optimistic update instantly
    optimistic_hook.apply_optimistic_update(target_id, new_stock)
    print(f"   {GREEN}>> UI Render Instan (useOptimistic):{RESET} Tampilan berubah menjadi {BOLD}{new_stock}{RESET} {badge('OPTIMISTIC (0ms latency)', BG_GREEN)}")
    print(f"   {DIM}Pengguna merasakan respon sekejap tanpa menunggu round-trip server.{RESET}")

    # Network roundtrip to Server Action
    print(f"\n{BOLD}2. [Server Communication]{RESET} Mengirim request mutasi ke backend...")
    result = update_stock_action(target_id, new_stock, should_fail=simulate_failure)

    if result["status"] == "success":
        optimistic_hook.commit(result["data"])
        print(f"   {GREEN}>> [Server Ack]{RESET} Mutasi berhasil dikonfirmasi server.")
        print(f"   State Final Terkonsolidasi: Stok = {BOLD}{result['data']['stock']}{RESET}")
    else:
        print(f"   {RED}>> [Server Rejected]{RESET} Server mengembalikan error: {result['message']}")
        print(f"   {YELLOW}>> [Rollback Triggered]{RESET} Hook useOptimistic membatalkan prediksi!")
        optimistic_hook.rollback()
        print(f"   State Kembali ke Aktual: Stok = {BOLD}{initial_stock}{RESET} {badge('REVERTED', BG_RED)}")


def demo_cache_inspection():
    header("SKENARIO 3: Next.js Cache & Revalidation State")
    print(f"{BOLD}Data Terkini di Database (Server Source of Truth):{RESET}")
    items = db.find_all()
    for item in items:
        status_tag = f"{GREEN}[In Stock]{RESET}" if item["stock"] > 0 else f"{RED}[Out of Stock]{RESET}"
        print(f"  • {item['id']:<8} | {item['title']:<35} | ${item['price']:<6.2f} | Stok: {item['stock']:<3} {status_tag}")

    print(f"\n{BOLD}Metadata Riwayat Invalidation Cache:{RESET}")
    for p, ts in cache.paths.items():
        print(f"  Path: {CYAN}{p:<25}{RESET} -> Invalidate Epoch: {ts}")
    for t, ts in cache.tags.items():
        print(f"  Tag:  {MAGENTA}{t:<25}{RESET} -> Invalidate Epoch: {ts}")


def run_automated_self_test():
    header("PENGUJIAN OTOMATIS (Automated Suite Validation)")
    print(f"{DIM}Menjalankan uji sintaks, logika validasi Zod, dan mutasi data...{RESET}\n")

    # Test 1: Validation fail
    val_ok, _, errs = ProductSchema.validate({"title": "ab", "price": "-10", "stock": "-1"})
    assert not val_ok, "Test 1 Gagal: Seharusnya validasi error"
    assert "title" in errs and "price" in errs and "stock" in errs
    print(f"[{GREEN}PASS{RESET}] Test 1: Validasi form Zod menangkap kesalahan input dengan benar.")

    # Test 2: Valid payload creation
    res = create_product_action({}, {"title": "Nuxt to Next Migration", "price": "42.0", "stock": "8"})
    assert res["status"] == "success", "Test 2 Gagal: Seharusnya pembuatan produk sukses"
    assert res["data"]["title"] == "Nuxt to Next Migration"
    print(f"[{GREEN}PASS{RESET}] Test 2: Server Action 'create_product_action' berhasil menyimpan data baru.")

    # Test 3: Optimistic rollback logic
    opt = OptimisticUI([{"id": "p_test", "title": "Test", "price": 10.0, "stock": 5}])
    opt.apply_optimistic_update("p_test", 100)
    assert opt.optimistic_state[0]["stock"] == 100
    opt.rollback()
    assert opt.optimistic_state[0]["stock"] == 5
    print(f"[{GREEN}PASS{RESET}] Test 3: useOptimistic state update dan rollback berjalan deterministik.")

    print(f"\n{BG_GREEN}{WHITE}{BOLD} SEMUA TEST SUITE LOLOS 100% (Sintaks & Logika Valid) {RESET}\n")


# ==============================================================================
# 6. Main Interactive CLI Menu Loop
# ==============================================================================
def main():
    if "--test" in sys.argv or "--non-interactive" in sys.argv:
        run_automated_self_test()
        sys.exit(0)

    while True:
        header("LAB SIMULATOR: NEXT.JS DATA MUTATION & STATEFUL FORMS")
        print(f"{BOLD}Pilih Modul Pembelajaran:{RESET}")
        print(f"  {CYAN}1.{RESET} Simulasi Form Stateful (Server Action + Zod + useActionState)")
        print(f"  {CYAN}2.{RESET} Simulasi Optimistic UI Update & Auto-Rollback (useOptimistic)")
        print(f"  {CYAN}3.{RESET} Inspeksi Database & Cache Revalidation Logs (revalidatePath)")
        print(f"  {CYAN}4.{RESET} Jalankan Automated Self-Test")
        print(f"  {CYAN}5.{RESET} Keluar (Exit)")
        
        choice = input(f"\n{YELLOW}Pilihan Anda [1-5]: {RESET}").strip()
        
        if choice == "1":
            demo_create_product_form()
        elif choice == "2":
            demo_optimistic_update()
        elif choice == "3":
            demo_cache_inspection()
        elif choice == "4":
            run_automated_self_test()
        elif choice == "5" or choice.lower() == "q":
            print(f"\n{GREEN}Terima kasih! Sesi hands-on selesai.{RESET}\n")
            break
        else:
            print(f"\n{RED}Pilihan tidak valid. Silakan masukkan angka 1 - 5.{RESET}")

        input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu utama...{RESET}")


if __name__ == "__main__":
    main()
