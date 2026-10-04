#!/usr/bin/env python3
"""
Lab Hands-on: Array & Hashing Architecture (Deep Dive)
Bab: 01 - Modul 02: Internal Collision Resolution, Load Factors & Probing Metrics

Deskripsi:
Script ini membedah arsitektur internal hash table level rendah menggunakan
Open Addressing dengan Linear Probing dan mekanisme Tombstone Deletion.
Melakukan simulasi komputasi probe sequence length (PSL), deteksi clustering,
siklus resizing otomatis (rehashing), serta benchmarking performa terhadap dict bawaan.
"""

import sys
import time
import math
import random
from typing import Any, Optional, Tuple, List

# --- Terminal ANSI Color Formatting ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_GRAY = "\033[90m"


class LinearProbingHashMap:
    """
    Implementasi low-level Hash Table berbasis Open Addressing dengan Linear Probing.
    Menggunakan sentinel _TOMBSTONE untuk menangani soft-delete tanpa memutus probe chain.
    """

    # Sentinel singleton untuk menandai slot yang dihapus
    _TOMBSTONE = object()

    def __init__(self, initial_capacity: int = 8, load_factor_threshold: float = 0.65):
        # Kapasitas wajib berupa perpangkatan 2 untuk bitwise modulo: (cap - 1)
        self.capacity = self._next_power_of_two(max(8, initial_capacity))
        self.load_factor_threshold = load_factor_threshold
        
        self.slots: List[Optional[Tuple[Any, Any]]] = [None] * self.capacity
        self.size = 0          # Jumlah pasangan (key, value) aktif
        self.tombstones = 0    # Jumlah slot yang bertanda _TOMBSTONE
        
        # Metrik performa internal
        self.total_probes_recorded = 0
        self.resize_events = 0

    @staticmethod
    def _next_power_of_two(n: int) -> int:
        """Menghitung nilai perpangkatan dua terdekat yang >= n."""
        return 1 << (n - 1).bit_length()

    def _hash(self, key: Any) -> int:
        """
        Fungsi hash internal.
        Menggunakan bitwise AND mask sebagai pengganti modulo lambat (%)
        Kondisi: self.capacity harus selalu bernilai 2^k.
        """
        # Multiplikasi Fibonacci hashing untuk mendistribusikan entropi ke bit rendah
        h = hash(key)
        h ^= (h >> 20) ^ (h >> 12)
        h ^= (h >> 7) ^ (h >> 4)
        return h & (self.capacity - 1)

    def put(self, key: Any, value: Any) -> int:
        """
        Menyimpan pasangan (key, value).
        Mengembalikan jumlah probe yang dibutuhkan untuk operasi ini.
        Memicu dynamic resizing jika load factor melampaui ambang batas.
        """
        if (self.size + self.tombstones + 1) / self.capacity >= self.load_factor_threshold:
            self._resize(self.capacity * 2)

        idx = self._hash(key)
        probes = 0
        first_tombstone_idx = -1

        while True:
            probes += 1
            entry = self.slots[idx]

            if entry is None:
                # Slot kosong murni ditemukan
                target_idx = first_tombstone_idx if first_tombstone_idx != -1 else idx
                self.slots[target_idx] = (key, value)
                self.size += 1
                if first_tombstone_idx != -1:
                    self.tombstones -= 1
                self.total_probes_recorded += probes
                return probes

            elif entry is self._TOMBSTONE:
                # Slot mati; rekam kandidat pertama untuk reuse jika key tidak ditemukan di probe lanjutannya
                if first_tombstone_idx == -1:
                    first_tombstone_idx = idx

            elif entry[0] == key:
                # Update existing key
                self.slots[idx] = (key, value)
                self.total_probes_recorded += probes
                return probes

            # Linear Probing step
            idx = (idx + 1) & (self.capacity - 1)

    def get(self, key: Any) -> Tuple[Optional[Any], int]:
        """
        Mengambil nilai berdasarkan key.
        Mengembalikan tuple: (value, jumlah_probe). Jika tidak ditemukan: (None, probes).
        """
        idx = self._hash(key)
        probes = 0

        while True:
            probes += 1
            entry = self.slots[idx]

            if entry is None:
                # Terminal condition: slot None menandakan key dipastikan tidak ada
                return None, probes
            
            if entry is not self._TOMBSTONE and entry[0] == key:
                return entry[1], probes

            idx = (idx + 1) & (self.capacity - 1)
            
            # Pengaman bila traversal berputar penuh (semua slot berisi data/tombstone)
            if probes >= self.capacity:
                return None, probes

    def delete(self, key: Any) -> bool:
        """
        Menghapus key dengan meletakkan marker _TOMBSTONE.
        Mencegah pemutusan probe chain linear probing untuk item setelahnya.
        """
        idx = self._hash(key)
        probes = 0

        while True:
            probes += 1
            entry = self.slots[idx]

            if entry is None:
                return False

            if entry is not self._TOMBSTONE and entry[0] == key:
                self.slots[idx] = self._TOMBSTONE
                self.size -= 1
                self.tombstones += 1
                return True

            idx = (idx + 1) & (self.capacity - 1)
            if probes >= self.capacity:
                return False

    def _resize(self, new_capacity: int) -> None:
        """
        Rehashing seluruh elemen aktif ke dalam array buffer baru.
        Membersihkan semua tombstone dan merestrukturisasi panjang probe.
        """
        self.resize_events += 1
        old_slots = self.slots
        
        self.capacity = new_capacity
        self.slots = [None] * self.capacity
        self.size = 0
        self.tombstones = 0

        for entry in old_slots:
            if entry is not None and entry is not self._TOMBSTONE:
                self.put(entry[0], entry[1])

    def get_cluster_stats(self) -> dict:
        """
        Menganalisis fenomena Primary Clustering (rantai slot berturut-turut yang terisi).
        Metrik ini krusial dalam mendeteksi degradasi performa Open Addressing.
        """
        clusters = []
        current_len = 0
        
        for slot in self.slots:
            if slot is not None and slot is not self._TOMBSTONE:
                current_len += 1
            else:
                if current_len > 0:
                    clusters.append(current_len)
                    current_len = 0
        if current_len > 0:
            clusters.append(current_len)

        return {
            "total_clusters": len(clusters),
            "max_cluster": max(clusters) if clusters else 0,
            "avg_cluster": sum(clusters) / len(clusters) if clusters else 0.0,
            "load_factor": self.size / self.capacity
        }


# =====================================================================
# SIMULASI & BENCHMARK SUITE
# =====================================================================

def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}[LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")


def run_collision_and_tombstone_demo():
    print_header("Fase 1: Mekanisme Linear Probing & Tombstone Deletion")
    
    # Inisialisasi kapasitas kecil untuk mendemonstrasikan probing visual
    ht = LinearProbingHashMap(initial_capacity=8, load_factor_threshold=0.75)
    
    keys = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
    print(f"{CLR_YELLOW}-> Memasukkan data awal (Kapasitas: {ht.capacity})...{CLR_RESET}")
    
    for k in keys:
        probes = ht.put(k, f"val_{k}")
        idx = ht._hash(k)
        print(f"  Put Key: {k:<8} | Hash Slot Ideal: {idx:2d} | Total Probes Terpakai: {probes}")

    print(f"\n{CLR_YELLOW}-> Menghapus 'Beta' (Mekanisme Soft-Delete / Tombstone)...{CLR_RESET}")
    ht.delete("Beta")
    
    # Tampilkan state internal buffer
    print(f"  Slot Allocation:")
    for i, s in enumerate(ht.slots):
        if s is None:
            state = f"{CLR_GRAY}[EMPTY]{CLR_RESET}"
        elif s is LinearProbingHashMap._TOMBSTONE:
            state = f"{CLR_RED}[TOMBSTONE]{CLR_RESET}"
        else:
            state = f"{CLR_GREEN}[KEY: {s[0]}]{CLR_RESET}"
        print(f"    Bucket [{i:02d}]: {state}")

    print(f"\n{CLR_YELLOW}-> Memverifikasi Probe Chain saat mencari 'Gamma' melompati Tombstone...{CLR_RESET}")
    val, p_count = ht.get("Gamma")
    print(f"  Lookup 'Gamma' -> Nilai: '{val}' | Probes dilewati: {p_count} {CLR_GREEN}(Lolos melewati slot yang dihapus){CLR_RESET}")


def run_clustering_and_resize_analysis():
    print_header("Fase 2: Analisis Primary Clustering & Amortized Resizing")
    
    ht = LinearProbingHashMap(initial_capacity=16, load_factor_threshold=0.60)
    data_points = 250
    print(f"Menyuntikkan {data_points} random keys ke LinearProbingHashMap...")

    checkpoints = [10, 50, 100, 175, 250]
    
    for i in range(1, data_points + 1):
        key = f"metric_key_{i}_{random.randint(1000, 9999)}"
        ht.put(key, i)
        
        if i in checkpoints:
            stats = ht.get_cluster_stats()
            print(f"[{CLR_BOLD}N = {i:3d}{CLR_RESET}] "
                  f"Kapasitas: {ht.capacity:4d} | "
                  f"Load Factor: {stats['load_factor']:.3f} | "
                  f"Max Cluster: {stats['max_cluster']:2d} | "
                  f"Avg Cluster: {stats['avg_cluster']:.2f} | "
                  f"Resize Terjadi: {ht.resize_events} kali")


def run_performance_benchmark():
    print_header("Fase 3: Benchmark Komparatif vs Python Native Dict")
    
    n_operations = 50_000
    test_keys = [f"uuid_benchmark_{i}_{random.random()}" for i in range(n_operations)]
    query_keys = random.sample(test_keys, 20_000)
    
    # 1. Custom Linear Probing Map
    custom_map = LinearProbingHashMap(initial_capacity=1024, load_factor_threshold=0.65)
    
    t0 = time.perf_counter()
    for k in test_keys:
        custom_map.put(k, 1)
    custom_insert_time = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    total_custom_probes = 0
    for qk in query_keys:
        _, p = custom_map.get(qk)
        total_custom_probes += p
    custom_lookup_time = time.perf_counter() - t0
    avg_probes = total_custom_probes / len(query_keys)

    # 2. Native Built-in Dict (Highly Optimized C-Python Implementation)
    native_dict = {}
    
    t0 = time.perf_counter()
    for k in test_keys:
        native_dict[k] = 1
    native_insert_time = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    for qk in query_keys:
        _ = native_dict.get(qk)
    native_lookup_time = time.perf_counter() - t0

    # Output Metrik
    print(f"{'Metrik':<30} | {'Custom Linear Probing':<20} | {'Python Native (Dict)':<20}")
    print("-" * 75)
    print(f"{'Waktu Insert (' + str(n_operations) + ' item)':<30} | {custom_insert_time * 1000:>17.2f} ms | {native_insert_time * 1000:>17.2f} ms")
    print(f"{'Waktu Lookup (20,000 item)':<30} | {custom_lookup_time * 1000:>17.2f} ms | {native_lookup_time * 1000:>17.2f} ms")
    print(f"{'Final Capacity / Size':<30} | {custom_map.capacity:>9d} / {custom_map.size:<7d} | {'Dynamic (C-level)':>20}")
    print(f"{'Rata-rata Probes / Lookup':<30} | {avg_probes:>20.2f} | {'1.00 (O(1) optimal)':>20}")
    
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}[Kesimpulan Arsitektur]:{CLR_RESET}")
    print(f"1. Linear Probing menjaga spatial locality (cache-friendly) karena array berurutan.")
    print(f"2. Kelemahan utamanya adalah {CLR_YELLOW}Primary Clustering{CLR_RESET}, terlihat dari probe lookup rata-rata ({avg_probes:.2f} probes).")
    print(f"3. Resizing eksponensial (2^n) menekan load factor di bawah 0.65 guna menjaga lookup tetap amortized O(1).")


if __name__ == "__main__":
    # Jalankan keseluruhan lab
    random.seed(42)  # Deterministic pseudo-random seed untuk konsistensi benchmark
    run_collision_and_tombstone_demo()
    run_clustering_and_resize_analysis()
    run_performance_benchmark()
    print(f"\n{CLR_GREEN}{CLR_BOLD}Semua modul evaluasi selesai dijalankan dengan sukses.{CLR_RESET}\n")