#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Data Structures & Memory Management Deep Dive
Topic: Python Runtime Memory Architecture, Optimization, and GC Semantics
Standard Library Only: sys, gc, weakref, time, tracemalloc
"""

import sys
import gc
import weakref
import time
import tracemalloc

# --- Terminal ANSI Styling ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_CYAN   = "\033[96m"

def print_header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")

def print_metric(label: str, value: str, note: str = "") -> None:
    note_str = f" ({CLR_YELLOW}{note}{CLR_RESET})" if note else ""
    print(f"  {CLR_BLUE}▶{CLR_RESET} {label:<35}: {CLR_BOLD}{value}{CLR_RESET}{note_str}")


# ============================================================================
# Modul 1: Memory Footprint Optimization (__slots__ vs __dict__)
# ============================================================================
class StandardEntity:
    """Representasi entitas berbasis dynamic __dict__ konvensional."""
    def __init__(self, entity_id: int, name: str, lat: float, lon: float):
        self.entity_id = entity_id
        self.name = name
        self.lat = lat
        self.lon = lon

class SlottedEntity:
    """
    Representasi entitas yang memanfaatkan __slots__.
    Mencegah alokasi PyDictObject per-instance dan mengalokasikan array C fixed-size.
    """
    __slots__ = ('entity_id', 'name', 'lat', 'lon')

    def __init__(self, entity_id: int, name: str, lat: float, lon: float):
        self.entity_id = entity_id
        self.name = name
        self.lat = lat
        self.lon = lon


def benchmark_slots_optimization(n_instances: int = 150_000):
    """
    Mengukur konsumsi memori aktual di heap CPython menggunakan tracemalloc
    antara dictionary-backed class vs slotted class.
    """
    print_header("1. Memory Footprint: __dict__ vs __slots__")
    
    # 1. Benchmark Standard Class
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    std_pool = [
        StandardEntity(i, f"Node-{i}", -6.2088 + (i * 0.0001), 106.8456 + (i * 0.0001))
        for i in range(n_instances)
    ]
    t1 = time.perf_counter()
    current_std, peak_std = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # 2. Benchmark Slotted Class
    del std_pool
    gc.collect()
    
    tracemalloc.start()
    t2 = time.perf_counter()
    slotted_pool = [
        SlottedEntity(i, f"Node-{i}", -6.2088 + (i * 0.0001), 106.8456 + (i * 0.0001))
        for i in range(n_instances)
    ]
    t3 = time.perf_counter()
    current_slotted, peak_slotted = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Evaluasi Hasil
    std_mb = peak_std / (1024 * 1024)
    slot_mb = peak_slotted / (1024 * 1024)
    saved_pct = ((peak_std - peak_slotted) / peak_std) * 100
    
    print_metric("Instance Count", f"{n_instances:,} objects")
    print_metric("Standard Class Peak Heap", f"{std_mb:.2f} MiB", f"{t1 - t0:.3f} sec")
    print_metric("Slotted Class Peak Heap", f"{slot_mb:.2f} MiB", f"{t3 - t2:.3f} sec")
    print_metric("Memory Reduction", f"{saved_pct:.2f}%", f"{CLR_GREEN}Optimization Direct Result{CLR_RESET}")

    del slotted_pool
    gc.collect()


# ============================================================================
# Modul 2: Circular References & CPython Generational GC Diagnostics
# ============================================================================
class CyclicNode:
    """Node yang sengaja dirancang untuk membangun circular reference."""
    def __init__(self, name: str):
        self.name = name
        self.neighbor = None

    def link(self, other: 'CyclicNode'):
        self.neighbor = other


def diagnose_cyclic_garbage():
    """
    Menganalisis Reference Counting failure pada cyclic graph
    dan membuktikan mekanisme pembersihan via Cyclic Garbage Collector (C-API PyGC_Head).
    """
    print_header("2. Reference Counting & Cyclic GC Diagnostics")

    # Matikan auto GC agar kita bisa membedah isolasi siklus referensi secara deterministik
    gc.disable()
    print(f"  {CLR_YELLOW}[!]{CLR_RESET} Cyclic Garbage Collector dinonaktifkan sementara.")

    # Alokasi siklus sirkular
    node_a = CyclicNode("Node-A")
    node_b = CyclicNode("Node-B")
    node_a.link(node_b)
    node_b.link(node_a)

    addr_a, addr_b = id(node_a), id(node_b)
    print_metric("Alamat node_a", hex(addr_a))
    print_metric("Alamat node_b", hex(addr_b))

    # Catatan: sys.getrefcount menambah 1 referensi internal temporer selama pemanggilan
    print_metric("Initial Refcount (node_a)", f"{sys.getrefcount(node_a) - 1}")
    print_metric("Initial Refcount (node_b)", f"{sys.getrefcount(node_b) - 1}")

    # Hapus pointer kuat dari scope lokal
    del node_a
    del node_b

    print(f"  {CLR_YELLOW}[!]{CLR_RESET} Reference lokal dihapus (del node_a, node_b).")
    print_metric("GC Thresholds (Gen0, Gen1, Gen2)", str(gc.get_threshold()))
    print_metric("GC Unreachable Tracked Before Run", str(gc.collect(0))) # collect Gen 0

    # Lakukan explicit Full Collection (Semua Generasi: 0, 1, 2)
    unreachable_count = gc.collect()
    print_metric("Explicit Full GC Run", f"Cleared {unreachable_count} unreachable cyclic objects")
    
    # Aktifkan kembali GC otomatis
    gc.enable()
    print(f"  {CLR_GREEN}[✓]{CLR_RESET} Cyclic Garbage Collector diaktifkan kembali.")


# ============================================================================
# Modul 3: In-Memory Cache Anti-Leak Menggunakan WeakValueDictionary
# ============================================================================
class HeavyDataPayload:
    """Objek dengan metadata besar yang disimulasikan."""
    def __init__(self, payload_id: str, size_bytes: int):
        self.payload_id = payload_id
        self.buffer = bytearray(size_bytes)

    def __repr__(self):
        return f"<HeavyPayload id={self.payload_id} size={len(self.buffer)}B>"


class ManagedWeakCache:
    """
    Cache thread-safe & zero-leak berbasis weak references.
    Objek akan otomatis tereviksi dari cache ketika referensi terakhir di luar cache mati.
    """
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()

    def set(self, key: str, payload: HeavyDataPayload) -> None:
        self._cache[key] = payload

    def get(self, key: str) -> HeavyDataPayload:
        return self._cache.get(key, None)

    def size(self) -> int:
        return len(self._cache)


def verify_weakref_cache():
    """Menguji auto-eviction semantics dari WeakValueDictionary."""
    print_header("3. Zero-Leak Memory Management via Weak References")

    cache = ManagedWeakCache()
    
    # Inisialisasi payload
    payload_1 = HeavyDataPayload("session-alpha", 1024 * 512) # 512 KiB
    payload_2 = HeavyDataPayload("session-beta",  1024 * 512) # 512 KiB

    cache.set("alpha", payload_1)
    cache.set("beta", payload_2)

    print_metric("Cache Size (Initial)", f"{cache.size()} items")
    print_metric("Lookup 'alpha'", str(cache.get("alpha")))
    
    # Simulasikan terminasi scope consumer payload_1
    print(f"\n  {CLR_YELLOW}[!]{CLR_RESET} Menghapus referensi eksternal dari payload_1...")
    del payload_1
    gc.collect()

    # Buktikan bahwa cache secara otomatis drop key tanpa eviction policy manual (LRU/TTL)
    print_metric("Cache Size (Post del payload_1)", f"{cache.size()} items")
    print_metric("Lookup 'alpha' (Harus None)", str(cache.get("alpha")))
    print_metric("Lookup 'beta' (Masih Hidup)", str(cache.get("beta")))

    # Hapus payload_2
    del payload_2
    gc.collect()
    print_metric("Cache Size (Post del payload_2)", f"{cache.size()} items", f"{CLR_GREEN}Fully clean{CLR_RESET}")


# ============================================================================
# Main Entry Point
# ============================================================================
def main():
    print(f"{CLR_BOLD}{CLR_GREEN}Starting Python Advanced Memory & Architecture Deep Dive...{CLR_RESET}")
    print(f"CPython Version : {sys.version.split()[0]} on {sys.platform}")
    print(f"Pointer Size    : {sys.maxsize.bit_length() + 1}-bit architecture")

    benchmark_slots_optimization(n_instances=100_000)
    diagnose_cyclic_garbage()
    verify_weakref_cache()

    print(f"\n{CLR_BOLD}{CLR_GREEN}[✓] Semua modul verifikasi memori selesai dieksekusi.{CLR_RESET}\n")

if __name__ == "__main__":
    main()