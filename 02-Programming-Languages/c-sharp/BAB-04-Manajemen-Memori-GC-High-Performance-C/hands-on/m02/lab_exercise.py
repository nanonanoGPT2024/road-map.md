#!/usr/bin/env python3
"""
Lab Hands-on: C# Memory Management, CLR Generational Garbage Collection & High-Performance Buffers
Modul: 04 - Deep Dive: Manajemen Memori, GC & High-Performance C#

Skrip ini mensimulasikan mekanisme internal Common Language Runtime (CLR) .NET:
1. Generational GC (Gen 0, Gen 1, Gen 2, dan Large Object Heap / LOH >= 85,000 bytes).
2. Mekanisme Mark, Sweep, dan Survival Promotion antar generasi.
3. Simulasi optimasi 'System.Buffers.ArrayPool<T>' vs alokasi naive untuk eliminasi GC pressure.
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes untuk visualisasi terminal
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RESET = "\033[0m"

LOH_THRESHOLD_BYTES = 85_000  # Standar CLR .NET: Objek >= 85KB masuk LOH
GEN0_CAPACITY_BYTES = 256_000 # Ambang batas pemicu Gen 0 GC
GEN1_CAPACITY_BYTES = 512_000 # Ambang batas pemicu Gen 1 GC

@dataclass
class ClrObject:
    """Merepresentasikan entitas objek di managed heap CLR."""
    obj_id: int
    name: str
    size_bytes: int
    generation: int = 0
    is_pinned: bool = False
    is_loh: bool = False
    is_reachable: bool = True  # Status referensi dari root tree

class ClrGarbageCollector:
    """
    Simulasi CLR Generational Garbage Collector (Workstation / Concurrent style).
    Mengimplementasikan:
    - Gen 0 (Ephemeral allocations)
    - Gen 1 (Buffer penstabil)
    - Gen 2 (Long-lived heap)
    - Large Object Heap (LOH - Langsung ke Gen 2, tanpa kompaksi reguler)
    """

    def __init__(self):
        self.objects: Dict[int, ClrObject] = {}
        self.next_id = 1
        
        # Metrik GC Counter (.NET equivalent: GC.CollectionCount(gen))
        self.gc_count = {0: 0, 1: 0, 2: 0}
        self.bytes_allocated = 0
        self.total_pause_time_ms = 0.0

    def allocate(self, name: str, size_bytes: int, is_pinned: bool = False) -> ClrObject:
        """Alokasi memori ke Managed Heap sesuai spesifikasi ukuran objek."""
        is_loh = size_bytes >= LOH_THRESHOLD_BYTES
        target_gen = 2 if is_loh else 0

        obj = ClrObject(
            obj_id=self.next_id,
            name=name,
            size_bytes=size_bytes,
            generation=target_gen,
            is_pinned=is_pinned,
            is_loh=is_loh,
            is_reachable=True
        )
        self.next_id += 1
        self.objects[obj.obj_id] = obj
        self.bytes_allocated += size_bytes

        # Cek apakah budget alokasi Gen 0 memicu GC
        gen0_size = sum(o.size_bytes for o in self.objects.values() if o.generation == 0 and not o.is_loh)
        if gen0_size >= GEN0_CAPACITY_BYTES:
            self._trigger_gc(generation=0)

        return obj

    def _trigger_gc(self, generation: int):
        """Menjalankan proses Mark, Sweep, dan Compact/Promote."""
        start_time = time.perf_counter()
        self.gc_count[generation] += 1
        
        # Simulasi eskalasi GC: Jika Gen 1 penuh, eskalasi ke Gen 2 (Full GC)
        gen1_size = sum(o.size_bytes for o in self.objects.values() if o.generation == 1)
        if generation == 0 and gen1_size >= GEN1_CAPACITY_BYTES:
            generation = 1

        print(f"  {CLR_YELLOW}[GC TRIGGER]{CLR_RESET} Executing GC Gen {generation}... "
              f"(Allocated: {self.get_heap_size_kb():.2f} KB)")

        dead_ids = []
        promoted_count = 0
        freed_bytes = 0

        # Mark & Sweep phase
        for obj_id, obj in list(self.objects.items()):
            if obj.generation <= generation or (generation == 2 and obj.is_loh):
                if not obj.is_reachable:
                    dead_ids.append(obj_id)
                    freed_bytes += obj.size_bytes
                else:
                    # Promosi Generasi (Survivors climb from Gen 0 -> 1 -> 2)
                    if not obj.is_loh:
                        if obj.generation < 2:
                            obj.generation += 1
                            promoted_count += 1

        # Reklamasi memori (Sweep)
        for obj_id in dead_ids:
            del self.objects[obj_id]

        duration_ms = (time.perf_counter() - start_time) * 1000 + (generation + 1) * 0.45
        self.total_pause_time_ms += duration_ms

        print(f"  {CLR_DIM}└─ [Sweep Completed] Freed: {freed_bytes / 1024:.2f} KB | "
              f"Promoted: {promoted_count} objs | Pause: {duration_ms:.2f}ms{CLR_RESET}")

    def collect_explicit(self, generation: int = 2):
        """Simulasi GC.Collect(generation) eksplisit."""
        self._trigger_gc(generation=generation)

    def get_heap_size_kb(self) -> float:
        return sum(o.size_bytes for o in self.objects.values()) / 1024.0

    def print_heap_layout(self):
        """Visualisasi status segment memori CLR."""
        gen0 = [o for o in self.objects.values() if o.generation == 0 and not o.is_loh]
        gen1 = [o for o in self.objects.values() if o.generation == 1]
        gen2 = [o for o in self.objects.values() if o.generation == 2 and not o.is_loh]
        loh = [o for o in self.objects.values() if o.is_loh]

        print(f"\n{CLR_BOLD}=== MANAGED HEAP STATUS SNAPSHOT ==={CLR_RESET}")
        print(f"  Gen 0 (Ephemeral) : {len(gen0):3d} objs | {sum(o.size_bytes for o in gen0)/1024:7.2f} KB")
        print(f"  Gen 1 (Intermediate: {len(gen1):3d} objs | {sum(o.size_bytes for o in gen1)/1024:7.2f} KB")
        print(f"  Gen 2 (Long-Lived) : {len(gen2):3d} objs | {sum(o.size_bytes for o in gen2)/1024:7.2f} KB")
        print(f"  LOH   (>= 85,000 B): {len(loh):3d} objs | {sum(o.size_bytes for o in loh)/1024:7.2f} KB")
        print(f"  GC Collections     : Gen0={self.gc_count[0]}, Gen1={self.gc_count[1]}, Gen2={self.gc_count[2]}")
        print(f"  Total GC Pause Time: {self.total_pause_time_ms:.2f} ms")
        print("=" * 40 + "\n")


class ArrayPoolSimulator:
    """
    Simulasi System.Buffers.ArrayPool<byte>.Shared dari .NET Core/Modern .NET.
    Mencegah alokasi berulang pada Small/Large Object Heap dengan daur ulang array.
    """
    def __init__(self, gc: ClrGarbageCollector):
        self.gc = gc
        # Buckets pool: size -> list of free buffers
        self.pool: Dict[int, List[ClrObject]] = {}
        self.rents = 0
        self.returns = 0

    def rent(self, min_size: int) -> ClrObject:
        """Meminjam buffer dari pool atau mengalokasikan baru jika pool kosong."""
        self.rents += 1
        # Pembulatan ukuran ke kelipatan power-of-two bucket
        bucket_size = 1024
        while bucket_size < min_size:
            bucket_size *= 2

        if bucket_size in self.pool and len(self.pool[bucket_size]) > 0:
            buffer = self.pool[bucket_size].pop()
            buffer.is_reachable = True
            return buffer
        
        # Jika belum ada di pool, alokasikan baru
        return self.gc.allocate(f"PooledBuffer-{bucket_size}B", bucket_size)

    def return_buffer(self, buffer: ClrObject):
        """Mengembalikan buffer ke pool agar tidak dikoleksi oleh GC."""
        self.returns += 1
        buffer.is_reachable = True  # Tetap reachable di dalam pool
        if buffer.size_bytes not in self.pool:
            self.pool[buffer.size_bytes] = []
        self.pool[buffer.size_bytes].append(buffer)


def run_benchmark():
    print(f"{CLR_CYAN}{CLR_BOLD}LAB HANDS-ON: C# MEMORY MANAGEMENT & HIGH-PERFORMANCE GC{CLR_RESET}")
    print(f"Menguji CLR Generational Allocator, Promotion, LOH, dan ArrayPool Optimization.\n")

    # =========================================================================
    # SKENARIO 1: Simulasi Siklus Hidup Objek & Promosi Generasi (Gen 0 -> Gen 2)
    # =========================================================================
    print(f"{CLR_BOLD}--- SKENARIO 1: Generational Allocation & LOH Direct Placement ---{CLR_RESET}")
    gc = ClrGarbageCollector()

    print("[Step 1] Mengalokasikan Transient Short-lived Objects (Gen 0)...")
    transient_refs = []
    for i in range(10):
        # Setiap objek berukuran 32 KB (Masuk Gen 0)
        obj = gc.allocate(f"HttpRequestContext_{i}", 32_000)
        if i % 2 == 0:
            transient_refs.append(obj)  # Separuh objek bertahan (survivor)
        else:
            obj.is_reachable = False    # Separuh langsung menjadi garbage (out of scope)

    print(f"[Step 2] Mengalokasikan Objek Besar (>= 85,000 bytes) untuk LOH...")
    loh_blob = gc.allocate("LargeImagePayload", 120_000)
    print(f"  Allocated '{loh_blob.name}' ({loh_blob.size_bytes} Bytes) -> Assigned directly to Gen {loh_blob.generation} (LOH={loh_blob.is_loh})")

    gc.print_heap_layout()

    print("[Step 3] Memicu beban alokasi masif untuk menekan Gen 0...")
    for i in range(12):
        # Memicu pemenuhan budget Gen 0 berulang kali
        o = gc.allocate(f"TempWorker_{i}", 28_000)
        o.is_reachable = False  # Segera mati

    print(f"[Step 4] Melepas sisa referensi root transient...")
    for o in transient_refs:
        o.is_reachable = False
    transient_refs.clear()

    print("[Step 5] Memanggil manual Full GC: GC.Collect()...")
    gc.collect_explicit(generation=2)
    gc.print_heap_layout()

    # =========================================================================
    # SKENARIO 2: Benchmark Pola Naive vs High-Performance ArrayPool<T>
    # =========================================================================
    print(f"\n{CLR_BOLD}--- SKENARIO 2: Benchmark High-Perf Pattern (ArrayPool<T> vs Naive New) ---{CLR_RESET}")
    iterations = 25
    buffer_request_size = 90_000  # Objek berukuran LOH untuk melihat dampak drastis

    # 1. Naive Allocations
    print(f"{CLR_RED}[Test A] Naive Pattern: 'new byte[90000]' di setiap request loop...{CLR_RESET}")
    naive_gc = ClrGarbageCollector()
    t0 = time.perf_counter()
    for i in range(iterations):
        buf = naive_gc.allocate(f"NaiveBuffer_{i}", buffer_request_size)
        # Simulasi pemrosesan I/O stream singkat
        buf.is_reachable = False # Out of scope di akhir fungsi/loop
    naive_time = (time.perf_counter() - t0) * 1000

    print(f"  Naive finished in: {naive_time:.2f}ms | GC Collections: {naive_gc.gc_count}")
    print(f"  Total Heap Pause Time: {naive_gc.total_pause_time_ms:.2f}ms")

    # 2. Optimized with ArrayPool
    print(f"\n{CLR_GREEN}[Test B] High-Performance: 'ArrayPool<byte>.Shared.Rent(90000)'...{CLR_RESET}")
    pool_gc = ClrGarbageCollector()
    pool = ArrayPoolSimulator(pool_gc)
    t0 = time.perf_counter()
    for i in range(iterations):
        # Rent buffer
        rented_buf = pool.rent(buffer_request_size)
        # Simulasi proses data...
        # Return buffer kembali ke pool
        pool.return_buffer(rented_buf)
    pool_time = (time.perf_counter() - t0) * 1000

    print(f"  ArrayPool finished in: {pool_time:.2f}ms | GC Collections: {pool_gc.gc_count}")
    print(f"  Total Heap Pause Time: {pool_gc.total_pause_time_ms:.2f}ms")

    # =========================================================================
    # HASIL AKHIR & INSIGHT TEKNIS
    # =========================================================================
    print(f"\n{CLR_BOLD}=== HASIL & KESIMPULAN TEKNIKAL HIGH-PERFORMANCE C# ==={CLR_RESET}")
    saved_collections = sum(naive_gc.gc_count.values()) - sum(pool_gc.gc_count.values())
    print(f"1. {CLR_GREEN}Pengurangan GC Pauses:{CLR_RESET} ArrayPool memangkas {saved_collections} siklus GC.")
    print(f"2. {CLR_GREEN}LOH Fragmentation:{CLR_RESET} Alokasi berulang >= 85KB pada Naive memicu degradasi Gen 2/LOH.")
    print(f"3. {CLR_GREEN}Zero-Allocation Principle:{CLR_RESET} Pemanfaatan buffer reuse (ArrayPool / Memory<T> / Span<T>)")
    print(f"   menjaga kestabilan latency tail (P99) pada server berbeban tinggi (Kestrel / ASP.NET Core).")

if __name__ == "__main__":
    run_benchmark()