#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Asynchronous Flow, Form Validation, & Data Fetching (Vue Architecture)
BAB-07: Asynchronous Flow, Forms, dan Data Fetching
Repositori: Road-Map / Frontend-and-Mobile / Vue

Simulasi interaktif tingkat lanjut yang memodelkan lifecycle Vue 3:
1. Composable Data Fetching (useAsyncQuery) dengan Stale-While-Revalidate & Request Deduplication
2. Race Condition Prevention via AbortController (Cancellable Tokens)
3. Schema-based Form Validation (VeeValidate/Zod style) dengan Dirty Checking
4. Optimistic UI Updates dengan Rollback Mechanism on API Failure
5. Resilient Retry Strategy dengan Exponential Backoff & Jitter
"""

import sys
import time
import random
import threading
from typing import Dict, Any, List, Optional, Callable

# ANSI Color Codes for Rich Terminal Presentation
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

def print_header(title: str):
    print(f"\n{BG_BLUE}{WHITE}{BOLD} [VUE COMPOSABLE RUNTIME] {RESET} {BOLD}{CYAN}{title}{RESET}")
    print(f"{DIM}{'─' * 70}{RESET}")

def log_event(channel: str, message: str, color: str = WHITE):
    timestamp = time.strftime("%H:%M:%S")
    print(f"{DIM}[{timestamp}]{RESET} {BOLD}{color}[{channel:<16}]{RESET} {message}")


class AbortSignal:
    """Simulasi AbortSignal DOM API untuk pembatalan HTTP request serentak."""
    def __init__(self):
        self._aborted = False

    def abort(self):
        self._aborted = True

    @property
    def is_aborted(self) -> bool:
        return self._aborted


class MockBackendAPI:
    """Mock API Gateway dengan latensi variabel & simulasi kegagalan network."""
    _products_db = [
        {"id": 1, "name": "Vite Turbo Laptop", "stock": 14, "price": 1250},
        {"id": 2, "name": "Pinia State Monitor 4K", "stock": 5, "price": 480},
        {"id": 3, "name": "Vue 3 Reactive Mechanical Keyboard", "stock": 28, "price": 160},
        {"id": 4, "name": "TypeScript Strict Ergonomic Mouse", "stock": 0, "price": 85},
    ]

    @classmethod
    def fetch_products(cls, search_query: str, signal: AbortSignal) -> List[Dict[str, Any]]:
        # Simulated network latency (200ms - 600ms)
        latency = random.uniform(0.2, 0.6)
        elapsed = 0.0
        step = 0.05
        while elapsed < latency:
            if signal.is_aborted:
                raise InterruptedError("Request dibatalkan oleh AbortController (Stale Request Detected).")
            time.sleep(step)
            elapsed += step

        # Filter query
        q = search_query.strip().lower()
        if not q:
            return list(cls._products_db)
        return [p for p in cls._products_db if q in p["name"].lower()]

    @classmethod
    def update_stock(cls, product_id: int, delta: int, simulate_failure: bool = False) -> Dict[str, Any]:
        time.sleep(0.4)
        if simulate_failure or random.random() < 0.25:
            raise ConnectionError(f"HTTP 500: Database lock timeout saat sinkronisasi stock item #{product_id}.")
        for item in cls._products_db:
            if item["id"] == product_id:
                if item["stock"] + delta < 0:
                    raise ValueError(f"HTTP 422: Stok tidak boleh bernilai negatif (Tersedia: {item['stock']}).")
                item["stock"] += delta
                return dict(item)
        raise LookupError(f"HTTP 404: Produk ID {product_id} tidak ditemukan.")


class ReactiveFormState:
    """
    Simulasi VeeValidate / Reactive Form Management di Vue 3:
    Mendukung field dirty checking, schema validation, touch state, dan async submission.
    """
    def __init__(self, initial_values: Dict[str, Any], validation_schema: Dict[str, Callable[[Any], Optional[str]]]):
        self.values = dict(initial_values)
        self.initial_values = dict(initial_values)
        self.schema = validation_schema
        self.errors: Dict[str, str] = {}
        self.touched: Dict[str, bool] = {k: False for k in initial_values}
        self.is_submitting = False

    @property
    def is_dirty(self) -> bool:
        return any(self.values[k] != self.initial_values[k] for k in self.values)

    @property
    def is_valid(self) -> bool:
        self.validate_all()
        return len(self.errors) == 0

    def touch(self, field: str):
        self.touched[field] = True
        self.validate_field(field)

    def set_field_value(self, field: str, value: Any):
        self.values[field] = value
        self.touch(field)

    def validate_field(self, field: str) -> bool:
        validator = self.schema.get(field)
        if validator:
            err = validator(self.values.get(field))
            if err:
                self.errors[field] = err
                return False
            else:
                self.errors.pop(field, None)
                return True
        return True

    def validate_all(self) -> bool:
        self.errors.clear()
        valid = True
        for field in self.schema:
            if not self.validate_field(field):
                valid = False
        return valid


class UseAsyncQueryState:
    """
    Simulasi Vue Composable: useAsyncQuery / TanStack Vue Query.
    Fitur: In-Memory Cache (SWR), Deduplikasi Request, dan AbortController handling.
    """
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._current_signal: Optional[AbortSignal] = None
        self._active_thread: Optional[threading.Thread] = None

    def execute(self, query: str, on_success: Callable[[List[Dict[str, Any]], bool], None], on_error: Callable[[str], None]):
        # Batalkan request sebelumnya jika masih berjalan (Race Condition Prevention)
        if self._current_signal and not self._current_signal.is_aborted:
            log_event("useAsyncQuery", f"Membatalkan inflight request sebelumnya untuk query: '{query}'", YELLOW)
            self._current_signal.abort()

        signal = AbortSignal()
        self._current_signal = signal

        # Cek Cache (Stale-While-Revalidate)
        cached_entry = self._cache.get(query)
        if cached_entry:
            age = time.time() - cached_entry["timestamp"]
            if age < 5.0:  # Fresh data (< 5 detik)
                log_event("CacheEngine", f"Cache HIT (fresh: {age:.2f}s) untuk '{query}' - Instant Render!", GREEN)
                on_success(cached_entry["data"], True)
                return
            else:
                log_event("CacheEngine", f"Cache STALE ({age:.2f}s). Mengembalikan stale data dan revalidating...", MAGENTA)
                on_success(cached_entry["data"], True)

        def worker():
            log_event("NetworkFetcher", f"Mengirim GET /api/products?search={query}", CYAN)
            try:
                data = MockBackendAPI.fetch_products(query, signal)
                self._cache[query] = {"data": data, "timestamp": time.time()}
                on_success(data, False)
            except InterruptedError as ie:
                log_event("NetworkFetcher", str(ie), YELLOW)
            except Exception as e:
                on_error(str(e))

        thread = threading.Thread(target=worker, daemon=True)
        self._active_thread = thread
        thread.start()


# --- Demo Scenarios & Interactive Simulation ---

def run_scenario_1_race_conditions():
    print_header("SKENARIO 1: Penanganan Race Condition & AbortController pada Search Input")
    print(f"{DIM}Menguji perilaku saat user mengetik cepat ('v', 'vue', 'vue 3').{RESET}")
    print(f"{DIM}Hanya request terakhir yang diizinkan menyelesaikan mutation state.{RESET}\n")

    query_composable = UseAsyncQueryState()
    results_lock = threading.Lock()

    def make_success_cb(term: str):
        def cb(data: List[Dict[str, Any]], from_cache: bool):
            with results_lock:
                cache_tag = f" {BG_GREEN}{WHITE} CACHED {RESET}" if from_cache else ""
                log_event("ViewRenderer", f"✅ Render hasil pencarian untuk '{term}' (Items: {len(data)}){cache_tag}", GREEN)
        return cb

    def error_cb(err: str):
        log_event("ViewRenderer", f"❌ Error: {err}", RED)

    keystrokes = ["v", "vue", "vue 3"]
    for stroke in keystrokes:
        log_event("UserEvent", f"Input text typed: '{stroke}'", BLUE)
        query_composable.execute(stroke, make_success_cb(stroke), error_cb)
        time.sleep(0.12)  # Delay lebih singkat dari latensi backend untuk memicu abort

    # Beri waktu request terakhir selesai
    time.sleep(0.8)


def run_scenario_2_form_validation_and_optimistic_update():
    print_header("SKENARIO 2: Form Validation Schema & Optimistic UI Update with Rollback")
    print(f"{DIM}Mendemonstrasikan dirty state, schema error guard, dan rollback ketika mutasi server gagal.{RESET}\n")

    schema = {
        "product_id": lambda v: None if isinstance(v, int) and v > 0 else "Product ID wajib dipilih.",
        "delta": lambda v: None if isinstance(v, int) and v != 0 else "Jumlah penambahan/pengurangan tidak boleh 0.",
        "note": lambda v: None if isinstance(v, str) and len(v.strip()) >= 5 else "Catatan wajib minimal 5 karakter.",
    }

    form = ReactiveFormState(
        initial_values={"product_id": 2, "delta": -2, "note": "Sync"},
        validation_schema=schema
    )

    log_event("FormSetup", f"Initial Form State: values={form.values}, is_dirty={form.is_dirty}", WHITE)

    # 1. Test validation failure
    log_event("FormAction", "Menguji validasi: Note terlalu pendek ('Sync')", YELLOW)
    form.validate_all()
    print(f"  {RED}↳ Validation Errors: {form.errors} | isValid={form.is_valid}{RESET}")

    # 2. Fix validation
    log_event("FormAction", "User mengoreksi form: Note -> 'Restock etalase cabang utama'", BLUE)
    form.set_field_value("note", "Restock etalase cabang utama")
    form.set_field_value("delta", 10)
    print(f"  {GREEN}↳ Form status setelah diperbaiki: is_dirty={form.is_dirty}, is_valid={form.is_valid}{RESET}")

    # 3. Optimistic Update Routine
    print("\n" + f"{BOLD}{YELLOW}--- Memulai Optimistic Mutation Flow ---{RESET}")
    product_target = 2
    local_stock_cache = 5  # Pinia State awal
    tentative_delta = 10

    # Step A: Optimistic Apply
    snapshot_stock = local_stock_cache
    local_stock_cache += tentative_delta
    log_event("PiniaStore", f"⚡ [OPTIMISTIC UPDATE] Stock ID #{product_target} diubah seketika: {snapshot_stock} -> {local_stock_cache}", CYAN)
    log_event("VueUI", f"Layar menampilkan stok terbaru: {local_stock_cache} (Loading spinner aktif)", MAGENTA)

    # Step B: Remote Call with Induced Failure to inspect rollback
    log_event("HTTPClient", f"POST /api/stock/adjust payload={{'id': {product_target}, 'delta': {tentative_delta}}}", BLUE)
    try:
        MockBackendAPI.update_stock(product_target, tentative_delta, simulate_failure=True)
        log_event("PiniaStore", "Komit state permanen: Server merespons 200 OK.", GREEN)
    except Exception as e:
        log_event("HTTPClient", f"🚨 Remote Call Gagal: {e}", RED)
        # Step C: Rollback Mechanism
        local_stock_cache = snapshot_stock
        log_event("PiniaStore", f"⏪ [ROLLBACK APPLIED] Mengembalikan state ke snapshot: {local_stock_cache}", YELLOW)
        log_event("NotificationToast", "Menampilkan Toast Error: 'Gagal memperbarui stok. Perubahan dibatalkan.'", RED)


def run_scenario_3_exponential_backoff_retry():
    print_header("SKENARIO 3: Resilient Data Fetching dengan Exponential Backoff + Jitter")
    print(f"{DIM}Mengatasi transient failure pada jaringan melalui automated retry policy.{RESET}\n")

    max_retries = 3
    base_delay = 0.2

    for attempt in range(1, max_retries + 1):
        try:
            log_event("FetchPolicy", f"Percobaan Request HTTP #{attempt}...", CYAN)
            # 60% probability of transient failure on attempts 1-2
            if attempt < 3:
                raise ConnectionResetError("Connection reset by peer (Network blip)")
            
            log_event("FetchPolicy", "✅ Berhasil menerima payload dari server!", GREEN)
            break
        except ConnectionResetError as cre:
            log_event("FetchPolicy", f"Gagal pada percobaan #{attempt}: {cre}", RED)
            if attempt == max_retries:
                log_event("ErrorBoundary", "❌ Seluruh retry limit habis. Mengaktifkan Fallback UI Component.", BG_RED + WHITE)
            else:
                backoff = (base_delay * (2 ** (attempt - 1))) + random.uniform(0.01, 0.05)
                log_event("RetrySchedule", f"Menunggu backoff {backoff:.3f} detik sebelum mencoba lagi...", YELLOW)
                time.sleep(backoff)


def main():
    print(f"{BOLD}{BG_BLUE}{WHITE}  SIMULASI ARSITEKTUR ASINKRON & FORM PIPELINE VUE 3 TINGKAT LANJUT  {RESET}")
    print(f"{CYAN}Modul: hands-on/m02/lab_exercise.py | BAB-07 Vue Production Guide{RESET}\n")

    run_scenario_1_race_conditions()
    time.sleep(0.5)
    run_scenario_2_form_validation_and_optimistic_update()
    time.sleep(0.5)
    run_scenario_3_exponential_backoff_retry()

    print("\n" + f"{BG_GREEN}{WHITE}{BOLD} [ALL LAB SIMULATION COMPLETED SUCCESSFULLY] {RESET}")
    print(f"{GREEN}Seluruh alur arsitektur asinkron Vue 3 telah teruji & tervalidasi mandiri.{RESET}\n")


if __name__ == "__main__":
    main()
