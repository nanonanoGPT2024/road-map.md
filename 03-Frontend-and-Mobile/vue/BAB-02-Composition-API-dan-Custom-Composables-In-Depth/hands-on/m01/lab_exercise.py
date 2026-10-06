#!/usr/bin/env python3
"""
Lab Exercise: Vue 3 Composition API & Custom Composables Simulator
Simulasi teknis independen prinsip reaktivitas Vue 3 (track, trigger, ref, reactive, computed, watch, composables)
dalam terminal interaktif dengan ANSI coloring.
"""

import sys
import time
from typing import Callable, Any, Set, List, Dict, Optional

# --- ANSI Color Codes ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_MAGENTA = "\033[35m"
CLR_RED = "\033[31m"
CLR_BLUE = "\033[34m"
CLR_BG_DARK = "\033[48;5;236m"


def header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== {title} ==={CLR_RESET}")


def info(msg: str) -> None:
    print(f"  {CLR_CYAN}[INFO]{CLR_RESET} {msg}")


def success(msg: str) -> None:
    print(f"  {CLR_GREEN}[SUCCESS]{CLR_RESET} {msg}")


def trigger_log(msg: str) -> None:
    print(f"  {CLR_MAGENTA}[TRIGGER]{CLR_RESET} {msg}")


def track_log(msg: str) -> None:
    print(f"  {CLR_YELLOW}[TRACK]{CLR_RESET} {msg}")


# --- Core Reactivity Engine (Vue 3 Effect & Dependency Tracking) ---
active_effect: Optional[Callable[[], None]] = None


class Dep:
    """Dependency bucket menyimpan effects yang bergantung pada target/property tertentu."""
    def __init__(self, name: str = "dep"):
        self.name = name
        self.subscribers: Set[Callable[[], None]] = set()

    def depend(self) -> None:
        global active_effect
        if active_effect and active_effect not in self.subscribers:
            self.subscribers.add(active_effect)
            track_log(f"Effect didaftarkan ke Dep({self.name}). Total sub: {len(self.subscribers)}")

    def notify(self) -> None:
        if not self.subscribers:
            return
        trigger_log(f"Dep({self.name}) memicu {len(self.subscribers)} subscriber effect(s)...")
        # Buat snapshot set untuk mencegah infinite loop saat effect berjalan
        effects_to_run = list(self.subscribers)
        for effect in effects_to_run:
            effect()


def watch_effect(fn: Callable[[], None]) -> Callable[[], None]:
    """Menjalankan efek segera dan melacak dependensi yang diakses selama eksekusi."""
    global active_effect

    def runner():
        global active_effect
        prev_effect = active_effect
        active_effect = runner
        try:
            fn()
        finally:
            active_effect = prev_effect

    runner()
    return runner


# --- Vue 3 Primitives: ref, reactive, computed, watch ---
class Ref:
    """Implementasi ref() Vue 3 dengan pembungkus .value"""
    def __init__(self, initial_value: Any, name: str = "anonymous_ref"):
        self._value = initial_value
        self.name = name
        self._dep = Dep(name=f"ref:{name}")

    @property
    def value(self) -> Any:
        self._dep.depend()
        return self._value

    @value.setter
    def value(self, new_val: Any) -> None:
        if new_val != self._value:
            old_val = self._value
            self._value = new_val
            info(f"Ref({self.name}) nilai berubah: {CLR_YELLOW}{old_val}{CLR_RESET} -> {CLR_GREEN}{new_val}{CLR_RESET}")
            self._dep.notify()


def ref(val: Any, name: str = "ref") -> Ref:
    return Ref(val, name=name)


class ReactiveProxy:
    """Simulasi Proxy reactive() pada object kamus/dictionary di Python."""
    def __init__(self, target: Dict[str, Any], name: str = "state"):
        self._target = target
        self._name = name
        self._deps: Dict[str, Dep] = {k: Dep(f"{name}.{k}") for k in target.keys()}

    def get(self, key: str) -> Any:
        if key not in self._deps:
            self._deps[key] = Dep(f"{self._name}.{key}")
        self._deps[key].depend()
        return self._target.get(key)

    def set(self, key: str, value: Any) -> None:
        old_val = self._target.get(key)
        if old_val != value:
            self._target[key] = value
            if key not in self._deps:
                self._deps[key] = Dep(f"{self._name}.{key}")
            info(f"Reactive({self._name}.{key}) mutated: {CLR_YELLOW}{old_val}{CLR_RESET} -> {CLR_GREEN}{value}{CLR_RESET}")
            self._deps[key].notify()


def reactive(target: Dict[str, Any], name: str = "state") -> ReactiveProxy:
    return ReactiveProxy(target, name=name)


class Computed:
    """Implementasi computed() dengan dirty checking & lazy evaluation."""
    def __init__(self, getter: Callable[[], Any], name: str = "computed"):
        self.getter = getter
        self.name = name
        self._value: Any = None
        self._dirty = True
        self._dep = Dep(f"computed:{name}")

        def on_dep_change():
            if not self._dirty:
                self._dirty = True
                trigger_log(f"Computed({self.name}) di-flag DIRTY oleh dep")
                self._dep.notify()

        self._scheduler = on_dep_change

    @property
    def value(self) -> Any:
        self._dep.depend()
        if self._dirty:
            info(f"Computed({self.name}) menghitung ulang nilai (evaluasi getter)...")
            global active_effect
            prev_effect = active_effect
            active_effect = self._scheduler
            try:
                self._value = self.getter()
            finally:
                active_effect = prev_effect
            self._dirty = False
        else:
            info(f"Computed({self.name}) mengambil nilai dari CACHE")
        return self._value


def computed(getter: Callable[[], Any], name: str = "computed") -> Computed:
    return Computed(getter, name=name)


def watch(source: Callable[[], Any], callback: Callable[[Any, Any], None], immediate: bool = False) -> None:
    """Implementasi watch(source, cb) Vue 3."""
    old_value: Any = None
    is_initial = True

    def job():
        nonlocal old_value, is_initial
        new_value = source()
        if is_initial:
            is_initial = False
            old_value = new_value
            if immediate:
                callback(new_value, None)
            return

        if new_value != old_value:
            prev = old_value
            old_value = new_value
            callback(new_value, prev)

    watch_effect(job)


# --- Custom Composables (Pola Composition API Vue 3) ---
def use_counter(initial_value: int = 0, step: int = 1):
    """Custom Composable: useCounter encapsulating state dan actions."""
    count = ref(initial_value, name="counter_count")
    double_count = computed(lambda: count.value * 2, name="double_count")

    def increment():
        count.value += step

    def decrement():
        count.value -= step

    def reset():
        count.value = initial_value

    return {
        "count": count,
        "double_count": double_count,
        "increment": increment,
        "decrement": decrement,
        "reset": reset,
    }


def use_toggle(initial_state: bool = False):
    """Custom Composable: useToggle untuk mengelola boolean switch."""
    state = ref(initial_state, name="toggle_state")

    def toggle():
        state.value = not state.value

    return {"state": state, "toggle": toggle}


# --- Interactive Demos ---
def demo_ref_and_reactive():
    header("1. DEMO: Ref vs Reactive")
    info("Membuat ref('Vue 3') dan reactive state...")
    app_title = ref("Vue 3 Composition API", name="title")
    user = reactive({"name": "Budi", "role": "Frontend Dev"}, name="user")

    print(f"\n{CLR_BOLD}Setup watchEffect (simulasi render template):{CLR_RESET}")
    render_count = 0

    def mock_render():
        nonlocal render_count
        render_count += 1
        print(f"  {CLR_CYAN}[DOM RENDER #{render_count}]{CLR_RESET} App: {app_title.value} | User: {user.get('name')} ({user.get('role')})")

    watch_effect(mock_render)

    time.sleep(0.3)
    print(f"\n{CLR_BOLD}Mutasi 1: Update app_title.value{CLR_RESET}")
    app_title.value = "Vue 3 Mastery: Composition In-Depth"

    time.sleep(0.3)
    print(f"\n{CLR_BOLD}Mutasi 2: Update user.set('role'){CLR_RESET}")
    user.set("role", "Vue Core Architect")


def demo_computed_and_caching():
    header("2. DEMO: Computed & Lazy Caching Evaluation")
    price = ref(10000, name="price")
    quantity = ref(3, name="qty")

    total = computed(lambda: price.value * quantity.value, name="total_price")

    print(f"\n{CLR_BOLD}Membaca total.value pertama kali:{CLR_RESET}")
    print(f"  Nilai Total: Rp{total.value:,}")

    print(f"\n{CLR_BOLD}Membaca total.value kedua kali (harus dari cache, tidak hitung ulang):{CLR_RESET}")
    print(f"  Nilai Total: Rp{total.value:,}")

    print(f"\n{CLR_BOLD}Mengubah quantity.value = 5 (memicu dirty flag):{CLR_RESET}")
    quantity.value = 5

    print(f"\n{CLR_BOLD}Membaca total.value setelah dirty:{CLR_RESET}")
    print(f"  Nilai Total Baru: Rp{total.value:,}")


def demo_watch_lifecycle():
    header("3. DEMO: Explicit Watcher (Old vs New Value)")
    query = ref("", name="search_query")

    def on_query_change(new_val, old_val):
        print(f"  {CLR_GREEN}[WATCH HANDLER]{CLR_RESET} Search query berubah dari '{old_val}' ke '{new_val}'! Melakukan query API simulasi...")

    watch(lambda: query.value, on_query_change, immediate=False)

    for word in ["Vue", "Composition", "Composable"]:
        time.sleep(0.2)
        print(f"\n{CLR_BOLD}Input user mengetik '{word}':{CLR_RESET}")
        query.value = word


def demo_custom_composable():
    header("4. DEMO: Custom Composable (useCounter & useToggle)")
    counter = use_counter(initial_value=5, step=2)
    toggle = use_toggle(initial_state=False)

    print(f"Status Awal Counter: count={counter['count'].value}, double={counter['double_count'].value}")
    print(f"Status Awal Toggle: {toggle['state'].value}")

    print(f"\n{CLR_BOLD}Aksi Composable:{CLR_RESET}")
    counter["increment"]()
    print(f"Setelah increment(): count={counter['count'].value}, double={counter['double_count'].value}")

    toggle["toggle"]()
    print(f"Setelah toggle(): state={toggle['state'].value}")

    counter["decrement"]()
    print(f"Setelah decrement(): count={counter['count'].value}, double={counter['double_count'].value}")

    counter["reset"]()
    print(f"Setelah reset(): count={counter['count'].value}, double={counter['double_count'].value}")


def run_automated_tests() -> bool:
    header("AUTOMATED VERIFICATION SUITE")
    all_passed = True

    # Test 1: Ref reactivity
    test_ref = ref(10, name="t_ref")
    observed = []
    watch_effect(lambda: observed.append(test_ref.value))
    test_ref.value = 20
    test_ref.value = 30
    if observed == [10, 20, 30]:
        success("Test Ref Reactivity & Effect Tracking: PASSED")
    else:
        print(f"{CLR_RED}[FAIL]{CLR_RESET} Expected [10, 20, 30], got {observed}")
        all_passed = False

    # Test 2: Computed caching
    calc_runs = 0
    base_val = ref(5, name="base")

    def compute_fn():
        nonlocal calc_runs
        calc_runs += 1
        return base_val.value * 10

    comp = computed(compute_fn, name="c_test")
    _ = comp.value
    _ = comp.value  # should be cached
    if calc_runs == 1 and comp.value == 50:
        base_val.value = 7
        _ = comp.value  # recompute
        if calc_runs == 2 and comp.value == 70:
            success("Test Computed Caching & Dirty Evaluation: PASSED")
        else:
            print(f"{CLR_RED}[FAIL]{CLR_RESET} Computed failed after update: runs={calc_runs}")
            all_passed = False
    else:
        print(f"{CLR_RED}[FAIL]{CLR_RESET} Computed caching failed: runs={calc_runs}")
        all_passed = False

    # Test 3: Custom Composable
    c = use_counter(0, 5)
    c["increment"]()
    c["increment"]()
    if c["count"].value == 10 and c["double_count"].value == 20:
        success("Test Custom Composable useCounter: PASSED")
    else:
        print(f"{CLR_RED}[FAIL]{CLR_RESET} Composable unexpected state")
        all_passed = False

    return all_passed


def interactive_menu():
    while True:
        print(f"\n{CLR_BOLD}{CLR_CYAN}╔═══════════════════════════════════════════════════════════════╗{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_CYAN}║     VUE 3 COMPOSITION API & COMPOSABLES SIMULATOR LAB         ║{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_CYAN}╚═══════════════════════════════════════════════════════════════╝{CLR_RESET}")
        print("  1. Demo: Ref vs Reactive (Dependency Tracking)")
        print("  2. Demo: Computed Property & Dirty-Flag Caching")
        print("  3. Demo: Watcher (oldValue vs newValue triggers)")
        print("  4. Demo: Custom Composable (useCounter & useToggle)")
        print("  5. Jalankan Semua Demo Berurutan")
        print("  6. Jalankan Unit Test Reaktivitas Otomatis")
        print("  0. Keluar")

        try:
            choice = input(f"\n{CLR_BOLD}Pilih opsi [0-6]: {CLR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            demo_ref_and_reactive()
        elif choice == "2":
            demo_computed_and_caching()
        elif choice == "3":
            demo_watch_lifecycle()
        elif choice == "4":
            demo_custom_composable()
        elif choice == "5":
            demo_ref_and_reactive()
            demo_computed_and_caching()
            demo_watch_lifecycle()
            demo_custom_composable()
        elif choice == "6":
            run_automated_tests()
        elif choice == "0":
            print(f"{CLR_GREEN}Sampai jumpa di lab Vue 3 berikutnya!{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid, silakan ulangi.{CLR_RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        ok = run_automated_tests()
        sys.exit(0 if ok else 1)
    interactive_menu()
