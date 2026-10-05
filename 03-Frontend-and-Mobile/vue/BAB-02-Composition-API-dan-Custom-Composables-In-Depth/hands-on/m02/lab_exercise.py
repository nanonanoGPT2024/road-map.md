#!/usr/bin/env python3
"""
Lab Exercise: Vue 3 Composition API & Advanced Custom Composables Simulation
BAB-02: Composition-API-dan-Custom-Composables-In-Depth

Simulasi murni arsitektur reaktivitas runtime Vue 3 di terminal:
- Reactive Dependency Tracker (Ref, Computed, WatchEffect)
- EffectScope Lifecycle Management (Cleanup & Scope Disposal)
- Enterprise Production Composables:
    * useAsyncState (loading, data, error, retry mechanism)
    * usePagination (state slice, auto computed boundaries)
    * useEventStream (pub-sub bus via provide/inject pattern)
"""

import sys
import time
from typing import Callable, Any, List, Dict, Optional, Set

# --- ANSI Color Formatting Helper ---
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

def c_print(color: str, text: str, end: str = "\n"):
    print(f"{color}{text}{Color.RESET}", end=end)


# --- Core Reactivity Engine Simulation ---
class EffectScope:
    current_scope: Optional['EffectScope'] = None

    def __init__(self, detached: bool = False):
        self.detached = detached
        self.effects: Set[Callable[[], None]] = set()
        self.cleanups: List[Callable[[], None]] = []
        self.is_active = True
        self.parent: Optional['EffectScope'] = None

    def run(self, fn: Callable[[], Any]) -> Any:
        if not self.is_active:
            c_print(Color.YELLOW, "[EffectScope] Peringatan: Menjalankan fungsi pada scope yang sudah didispose!")
            return None
        prev_scope = EffectScope.current_scope
        EffectScope.current_scope = self
        try:
            return fn()
        finally:
            EffectScope.current_scope = prev_scope

    def stop(self):
        if not self.is_active:
            return
        self.is_active = False
        for cleanup in self.cleanups:
            cleanup()
        self.cleanups.clear()
        self.effects.clear()
        c_print(Color.RED, "  ⚡ [EffectScope.stop()] Seluruh listener dan watchers scope telah didestroy (No Memory Leak).")

    def record_cleanup(self, fn: Callable[[], None]):
        if self.is_active:
            self.cleanups.append(fn)


active_subscribers: List[Callable[[], None]] = []

class Ref:
    def __init__(self, initial_value: Any, name: str = "anonymous"):
        self._value = initial_value
        self.name = name
        self.subscribers: Set[Callable[[], None]] = set()

    @property
    def value(self) -> Any:
        # Dependency Tracking
        if active_subscribers:
            current_sub = active_subscribers[-1]
            self.subscribers.add(current_sub)
        return self._value

    @value.setter
    def value(self, new_val: Any):
        if self._value != new_val:
            old_val = self._value
            self._value = new_val
            self.trigger_subscribers(old_val, new_val)

    def trigger_subscribers(self, old_val: Any, new_val: Any):
        # Salin set subscriber untuk menghindari mutasi saat iterasi
        subs = list(self.subscribers)
        for sub in subs:
            sub()


class Computed(Ref):
    def __init__(self, getter: Callable[[], Any], name: str = "computed"):
        super().__init__(None, name=name)
        self.getter = getter
        self.dirty = True

        def effect():
            self.dirty = True
            self.trigger_subscribers(None, None)

        self._effect = effect
        self.update_cache()

    def update_cache(self):
        active_subscribers.append(self._effect)
        try:
            self._value = self.getter()
            self.dirty = False
        finally:
            active_subscribers.pop()

    @property
    def value(self) -> Any:
        if self.dirty:
            self.update_cache()
        if active_subscribers:
            self.subscribers.add(active_subscribers[-1])
        return self._value


def watch(source: Ref, callback: Callable[[Any, Any], None], immediate: bool = False):
    prev_val = source.value

    def watcher_effect():
        nonlocal prev_val
        curr = source.value
        callback(curr, prev_val)
        prev_val = curr

    source.subscribers.add(watcher_effect)

    if EffectScope.current_scope and EffectScope.current_scope.is_active:
        scope = EffectScope.current_scope
        scope.record_cleanup(lambda: source.subscribers.discard(watcher_effect))

    if immediate:
        callback(source.value, None)


# --- Advanced Custom Composables ---

def use_async_state(fetcher: Callable[[], Any], default_val: Any = None):
    """Custom Composable: Meniru useAsyncState dari VueUse dengan auto retry & status."""
    data = Ref(default_val, name="async_data")
    is_loading = Ref(False, name="is_loading")
    error = Ref(None, name="error")

    def execute(retry_count: int = 1):
        is_loading.value = True
        error.value = None
        attempt = 0
        while attempt <= retry_count:
            try:
                attempt += 1
                c_print(Color.CYAN, f"  🔄 [useAsyncState] Mengambil data (Percobaan #{attempt})...")
                result = fetcher()
                data.value = result
                is_loading.value = False
                c_print(Color.GREEN, f"  ✅ [useAsyncState] Berhasil resolve: {result}")
                return
            except Exception as err:
                c_print(Color.YELLOW, f"  ⚠️ [useAsyncState] Gagal percobaan #{attempt}: {err}")
                if attempt > retry_count:
                    error.value = str(err)
                    is_loading.value = False
                    c_print(Color.RED, f"  ❌ [useAsyncState] Fetch gagal definitif: {err}")

    return {"data": data, "isLoading": is_loading, "error": error, "execute": execute}


def use_pagination(items_ref: Ref, page_size: int = 3):
    """Custom Composable: Navigasi slice reaktif & boundary check."""
    current_page = Ref(1, name="current_page")
    total_pages = Computed(lambda: max(1, (len(items_ref.value) + page_size - 1) // page_size), name="total_pages")

    def paginated_slice():
        start = (current_page.value - 1) * page_size
        end = start + page_size
        return items_ref.value[start:end]

    paginated_data = Computed(paginated_slice, name="paginated_data")

    def next_page():
        if current_page.value < total_pages.value:
            current_page.value += 1
            c_print(Color.BLUE, f"  ⏩ [usePagination] Halaman naik: {current_page.value}/{total_pages.value}")
        else:
            c_print(Color.YELLOW, "  ⚠️ [usePagination] Sudah mencapai halaman terakhir!")

    def prev_page():
        if current_page.value > 1:
            current_page.value -= 1
            c_print(Color.BLUE, f"  ⏪ [usePagination] Halaman turun: {current_page.value}/{total_pages.value}")
        else:
            c_print(Color.YELLOW, "  ⚠️ [usePagination] Sudah di halaman pertama!")

    return {
        "currentPage": current_page,
        "totalPages": total_pages,
        "paginatedData": paginated_data,
        "nextPage": next_page,
        "prevPage": prev_page
    }


# --- Interactive Scenarios ---

def scenario_reactive_core():
    c_print(Color.MAGENTA + Color.BOLD, "\n=== SKENARIO 1: Primitive Ref, Computed & Auto-tracking ===")
    counter = Ref(10, name="counter")
    double = Computed(lambda: counter.value * 2, name="double_counter")

    def on_change(curr, old):
        c_print(Color.CYAN, f"  🔔 [Watch] Counter berubah dari {old} -> {curr}")

    watch(counter, on_change)

    c_print(Color.WHITE, f"State Awal: counter={counter.value}, double={double.value}")
    c_print(Color.WHITE, "Melakukan mutasi: counter.value = 25")
    counter.value = 25
    c_print(Color.WHITE, f"State Baru: counter={counter.value}, double={double.value} (Otomatis dievaluasi ulang)")


def scenario_effect_scope_cleanup():
    c_print(Color.MAGENTA + Color.BOLD, "\n=== SKENARIO 2: EffectScope & Memory Leak Prevention ===")
    scope = EffectScope()
    global_source = Ref("Initial Event", name="global_stream")

    c_print(Color.CYAN, "-> Menjalankan sub-modul di dalam EffectScope...")
    scope.run(lambda: watch(
        global_source,
        lambda curr, old: c_print(Color.GREEN, f"  [Scope Listener Aktif] Mendapat sinyal: '{curr}'")
    ))

    c_print(Color.WHITE, "Pemicu 1 (Scope Aktif):")
    global_source.value = "Koneksi Websocket Terhubung"

    c_print(Color.YELLOW, "-> Memanggil scope.stop() (Unmount komponen)...")
    scope.stop()

    c_print(Color.WHITE, "Pemicu 2 (Setelah Scope Diberhentikan):")
    global_source.value = "Paket Data Baru Tiba"
    c_print(Color.WHITE, "Hasil: Tidak ada listener yang terpanggil karena EffectScope telah membersihkan watcher.")


def scenario_full_composables():
    c_print(Color.MAGENTA + Color.BOLD, "\n=== SKENARIO 3: useAsyncState & usePagination Pipeline ===")
    mock_db = ["Auth Guard", "Microfrontend Loader", "Telemetry Bus", "Pinia Store", "Vue Router Guard", "I18n Engine", "Vite SSR"]

    # Inisialisasi useAsyncState
    async_comp = use_async_state(lambda: mock_db, default_val=[])
    async_comp["execute"]()

    # Reaktifkan hasil async ke composable paginasi
    pager = use_pagination(async_comp["data"], page_size=3)

    c_print(Color.WHITE, f"Total Data: {len(async_comp['data'].value)} | Total Halaman: {pager['totalPages'].value}")
    c_print(Color.GREEN, f"Halaman {pager['currentPage'].value}: {pager['paginatedData'].value}")

    pager["nextPage"]()
    c_print(Color.GREEN, f"Halaman {pager['currentPage'].value}: {pager['paginatedData'].value}")

    pager["nextPage"]()
    c_print(Color.GREEN, f"Halaman {pager['currentPage'].value}: {pager['paginatedData'].value}")

    pager["nextPage"]()  # Harus memicu batas maksimal


def interactive_menu():
    banner = f"""
{Color.CYAN}{Color.BOLD}╔══════════════════════════════════════════════════════════════════════════╗
║     VUE 3 COMPOSITION API & CUSTOM COMPOSABLES IN-DEPTH SIMULATOR       ║
║     (BAB-02 Architecture Lab: Pure Python Reactivity Runtime Engine)     ║
╚══════════════════════════════════════════════════════════════════════════╝{Color.RESET}
    """
    print(banner)

    while True:
        print(f"\n{Color.BOLD}PILIH MENU SIMULASI INTERAKTIF:{Color.RESET}")
        print("  [1] Reaktivitas Fundamental: Ref, Computed, & Dependency Tracking")
        print("  [2] EffectScope: Lifecycle Management & Mencegah Memory Leak")
        print("  [3] Custom Composables Pipeline: useAsyncState & usePagination")
        print("  [4] Jalankan Semua Skenario Berurutan (Automated Test)")
        print("  [5] Keluar")

        try:
            choice = input(f"\n{Color.YELLOW}Masukkan pilihan (1-5): {Color.RESET}").strip()
            if choice == "1":
                scenario_reactive_core()
            elif choice == "2":
                scenario_effect_scope_cleanup()
            elif choice == "3":
                scenario_full_composables()
            elif choice == "4":
                scenario_reactive_core()
                time.sleep(0.4)
                scenario_effect_scope_cleanup()
                time.sleep(0.4)
                scenario_full_composables()
            elif choice in ("5", "exit", "quit", "q"):
                c_print(Color.CYAN, "Sampai jumpa! Lab Composition API selesai.")
                break
            else:
                c_print(Color.RED, "Pilihan tidak valid. Silakan masukkan angka 1 hingga 5.")
        except (KeyboardInterrupt, EOFError):
            print("\n")
            c_print(Color.YELLOW, "Sesi interaktif dihentikan.")
            break


if __name__ == "__main__":
    interactive_menu()
