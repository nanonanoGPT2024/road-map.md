#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Manajemen Memori & Garbage Collection .NET (CLR)
Modul: BAB-04-Manajemen-Memori-GC-High-Performance-C#
Topik:
  1. Generational GC (Gen 0, Gen 1, Gen 2, dan Large Object Heap / LOH)
  2. Alokasi Ephemeral & Mekanisme Promosi Generasi (Compaction & Sweep)
  3. Span<T> Zero-Allocation Memory Slicing vs Heap Copying
  4. ArrayPool<T> Buffer Recycling vs Garbage Pressure
  5. Siklus Hidup IDisposable & Finalizer Queue
"""

import sys
import time
import random
from typing import List, Dict, Optional

# ANSI Color Codes
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
BG_MAGENTA = "\033[45m"

class SimulatedObject:
    def __init__(self, name: str, size_bytes: int, is_root_referenced: bool = True):
        self.name = name
        self.size_bytes = size_bytes
        self.is_root_referenced = is_root_referenced
        self.generation = 0
        self.address = hex(id(self))
        self.has_finalizer = False
        self.is_disposed = False

class DotNetMemorySimulator:
    LOH_THRESHOLD = 85000  # 85,000 bytes CLR Large Object Heap threshold
    GEN0_BUDGET = 256000   # 256 KB
    GEN1_BUDGET = 512000   # 512 KB
    
    def __init__(self):
        self.gen0: List[SimulatedObject] = []
        self.gen1: List[SimulatedObject] = []
        self.gen2: List[SimulatedObject] = []
        self.loh: List[SimulatedObject] = []
        self.finalizer_queue: List[SimulatedObject] = []
        self.pool: Dict[int, List[bytearray]] = {}
        self.collection_counts = {0: 0, 1: 0, 2: 0}
        self.total_allocated_bytes = 0

    def allocate(self, name: str, size_bytes: int, root_referenced: bool = True, with_finalizer: bool = False) -> SimulatedObject:
        obj = SimulatedObject(name, size_bytes, root_referenced)
        obj.has_finalizer = with_finalizer
        self.total_allocated_bytes += size_bytes

        if with_finalizer:
            self.finalizer_queue.append(obj)

        if size_bytes >= self.LOH_THRESHOLD:
            obj.generation = -1 # Menandai LOH
            self.loh.append(obj)
            print(f"{YELLOW}[LOH Alloc]{RESET} '{name}' ({size_bytes:,} bytes) langsung ditempatkan di {MAGENTA}Large Object Heap{RESET}.")
        else:
            self.gen0.append(obj)
            print(f"{GREEN}[Gen 0 Alloc]{RESET} '{name}' ({size_bytes:,} bytes) dialokasikan di {CYAN}Generation 0{RESET}.")
            
            # Periksa apakah Gen 0 melebihi anggaran
            gen0_size = sum(o.size_bytes for o in self.gen0)
            if gen0_size >= self.GEN0_BUDGET:
                print(f"{RED}[Trigger]{RESET} Gen 0 melampaui kapasitas ({gen0_size:,} / {self.GEN0_BUDGET:,} bytes). Memicu GC otomatis...")
                self.collect(generation=0)

        return obj

    def collect(self, generation: int = 0):
        print(f"\n{BOLD}{RED}=== Memulai Garbage Collection: Gen {generation} ==={RESET}")
        start_time = time.perf_counter()
        self.collection_counts[generation] += 1

        # Gen 0 Collection
        survivors_gen0: List[SimulatedObject] = []
        collected_gen0_bytes = 0
        for obj in self.gen0:
            if obj.is_root_referenced:
                obj.generation = 1
                survivors_gen0.append(obj)
            else:
                collected_gen0_bytes += obj.size_bytes
                if obj.has_finalizer and not obj.is_disposed:
                    print(f"  {YELLOW}↳ Object '{obj.name}' masuk ke Freachable Queue untuk eksekusi Finalizer (~Destructor){RESET}")

        self.gen0 = []
        self.gen1.extend(survivors_gen0)
        print(f"  {CYAN}Gen 0 Sweep & Compact:{RESET} Membersihkan {collected_gen0_bytes:,} bytes dead objects.")
        print(f"  {GREEN}Promosi:{RESET} {len(survivors_gen0)} objek Gen 0 dipromosikan ke {YELLOW}Gen 1{RESET}.")

        # Jika triggered Gen 1 atau Gen 1 melebihi budget
        gen1_size = sum(o.size_bytes for o in self.gen1)
        if generation >= 1 or gen1_size >= self.GEN1_BUDGET:
            survivors_gen1: List[SimulatedObject] = []
            collected_gen1_bytes = 0
            for obj in self.gen1:
                if obj.is_root_referenced:
                    obj.generation = 2
                    survivors_gen1.append(obj)
                else:
                    collected_gen1_bytes += obj.size_bytes
            self.gen1 = []
            self.gen2.extend(survivors_gen1)
            print(f"  {YELLOW}Gen 1 Sweep:{RESET} Membersihkan {collected_gen1_bytes:,} bytes.")
            print(f"  {GREEN}Promosi:{RESET} {len(survivors_gen1)} objek Gen 1 dipromosikan ke {RED}Gen 2 (Tenured){RESET}.")

        # Full GC (Gen 2 + LOH)
        if generation >= 2:
            survivors_gen2 = [o for o in self.gen2 if o.is_root_referenced]
            collected_gen2_bytes = sum(o.size_bytes for o in self.gen2 if not o.is_root_referenced)
            self.gen2 = survivors_gen2

            # LOH Sweep (Tanpa Compaction standar di .NET lama)
            survivors_loh = [o for o in self.loh if o.is_root_referenced]
            collected_loh_bytes = sum(o.size_bytes for o in self.loh if not o.is_root_referenced)
            self.loh = survivors_loh
            print(f"  {RED}Full GC Sweep (Gen 2 & LOH):{RESET} Bebaskan Gen 2: {collected_gen2_bytes:,} bytes, LOH: {collected_loh_bytes:,} bytes (LOH rentan fragmentasi).")

        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"{BOLD}GC Selesai dalam {elapsed:.3f} ms (Stop-the-World pause dipersingkat).{RESET}\n")

    def display_heap_status(self):
        print(f"\n{BOLD}{BG_BLUE}{WHITE} ===== STATUS MEMORI CLR .NET ===== {RESET}")
        gen0_bytes = sum(o.size_bytes for o in self.gen0)
        gen1_bytes = sum(o.size_bytes for o in self.gen1)
        gen2_bytes = sum(o.size_bytes for o in self.gen2)
        loh_bytes = sum(o.size_bytes for o in self.loh)

        print(f"{CYAN}Generation 0 (Nursery/Fresh):{RESET} {len(self.gen0)} objek | {gen0_bytes:,} / {self.GEN0_BUDGET:,} bytes")
        self._print_objects(self.gen0)

        print(f"{YELLOW}Generation 1 (Buffer/Aging):{RESET}  {len(self.gen1)} objek | {gen1_bytes:,} / {self.GEN1_BUDGET:,} bytes")
        self._print_objects(self.gen1)

        print(f"{RED}Generation 2 (Long-Lived):{RESET}    {len(self.gen2)} objek | {gen2_bytes:,} bytes")
        self._print_objects(self.gen2)

        print(f"{MAGENTA}Large Object Heap (>= 85KB):{RESET} {len(self.loh)} objek | {loh_bytes:,} bytes")
        self._print_objects(self.loh)

        print(f"{BOLD}Statistik GC:{RESET} Gen0={self.collection_counts[0]}, Gen1={self.collection_counts[1]}, Gen2={self.collection_counts[2]}")
        print(f"{DIM}Total Alokasi Kumulatif: {self.total_allocated_bytes:,} bytes{RESET}")
        print(f"{BG_BLUE}{WHITE} =================================== {RESET}\n")

    def _print_objects(self, obj_list: List[SimulatedObject]):
        if not obj_list:
            print(f"   {DIM}(kosong){RESET}")
            return
        for o in obj_list:
            status = f"{GREEN}Root Alive{RESET}" if o.is_root_referenced else f"{RED}Unreachable (Eligible GC){RESET}"
            fin = f" | {YELLOW}[Finalizer]{RESET}" if o.has_finalizer else ""
            print(f"   • [{o.address}] {o.name:<18} : {o.size_bytes:>7,} B | {status}{fin}")

    # Simulasi ArrayPool<T>
    def rent_buffer(self, size: int) -> bytearray:
        bucket = self.pool.setdefault(size, [])
        if bucket:
            buf = bucket.pop()
            print(f"{GREEN}[ArrayPool.Shared.Rent]{RESET} Menggunakan kembali buffer {size:,} bytes dari pool (0 alokasi GC).")
            return buf
        print(f"{YELLOW}[ArrayPool.Shared.Rent]{RESET} Pool kosong. Mengalokasikan array baru {size:,} bytes.")
        return bytearray(size)

    def return_buffer(self, buf: bytearray):
        size = len(buf)
        self.pool.setdefault(size, []).append(buf)
        print(f"{CYAN}[ArrayPool.Shared.Return]{RESET} Buffer {size:,} bytes dikembalikan ke pool untuk reuse.")


def demo_span_vs_heap():
    print(f"\n{BOLD}{BG_MAGENTA}{WHITE} --- SIMULASI: Span<T> (Stack Slicing) vs Substring/Heap Copy --- {RESET}")
    print("Skenario: Memotong string/byte-buffer 1,000,000 kali.")
    raw_payload = b"HEADER:TYPE=ORDER;ID=99884433;CUSTOMER=ALPHA_CORP;CHECKSUM=FA82;BODY=DATA_PAYLOAD_CONTENT"
    
    # 1. Metode Klasik (Heap Allocation Subarray)
    t0 = time.perf_counter()
    heap_allocations = 0
    total_bytes = 0
    for _ in range(50000):
        # Slicing bytearray/bytes konvensional di Python menduplikasi memori (identik string.Substring / byte[] di C#)
        chunk = raw_payload[20:45]
        heap_allocations += 1
        total_bytes += len(chunk)
    t1 = time.perf_counter()
    time_heap = (t1 - t0) * 1000

    # 2. Metode Zero-Allocation (memoryview / Span<T> di C#)
    t2 = time.perf_counter()
    mem_view = memoryview(raw_payload)
    for _ in range(50000):
        # memoryview menyediakan zero-copy slice (mengemulasi ReadOnlySpan<byte>)
        span_slice = mem_view[20:45]
    t3 = time.perf_counter()
    time_span = (t3 - t2) * 1000

    print(f"{RED}[Metode Klasik Substring / Heap Copy]:{RESET}")
    print(f"  • Waktu Eksekusi    : {time_heap:.2f} ms")
    print(f"  • Memori Baru Heap : {total_bytes:,} bytes dialokasikan (Beban bagi GC)")

    print(f"{GREEN}[Metode Ref Struct / Span<T> Zero-Allocation]:{RESET}")
    print(f"  • Waktu Eksekusi    : {time_span:.2f} ms")
    print(f"  • Memori Baru Heap : 0 bytes (Zero GC pressure, bekerja langsung di contiguous memory/stack)")
    speedup = time_heap / time_span if time_span > 0 else 1.0
    print(f"{BOLD}Efisiensi Performa: {speedup:.1f}x lebih cepat tanpa GC overhead!{RESET}\n")


def interactive_cli():
    sim = DotNetMemorySimulator()
    
    # Pre-populate heap untuk gambaran awal
    sim.allocate("AppConfiguration", 12000, root_referenced=True)
    sim.allocate("TempRequestBuffer1", 90000, root_referenced=False) # Masuk LOH
    sim.allocate("UserSessionToken", 8000, root_referenced=True)
    sim.allocate("ShortLivedDBSnapshot", 180000, root_referenced=False) # Gen 0
    
    while True:
        print(f"{BOLD}{CYAN}=== MENU SIMULATOR MANAJEMEN MEMORI C# .NET ==={RESET}")
        print("1. Tampilkan Status Generasi Heap (Gen 0, Gen 1, Gen 2, LOH)")
        print("2. Alokasikan Objek Baru (Gen 0 atau LOH)")
        print("3. Ubah Referensi Objek (Simulasikan Scope Keluar / Dereferensi)")
        print("4. Picu Garbage Collection Manual (GC.Collect)")
        print("5. Benchmark: Span<T> (Zero-Copy) vs Alokasi Heap Konvensional")
        print("6. Simulasi ArrayPool<T> (Renting & Returning)")
        print("7. Alokasikan Objek dengan IDisposable & Finalizer (~Destructor)")
        print("0. Keluar")
        
        choice = input(f"{BOLD}Pilih opsi [0-7]: {RESET}").strip()
        
        if choice == "1":
            sim.display_heap_status()
            
        elif choice == "2":
            name = input("Nama Objek (e.g., OrderDto, ImageBitmap): ").strip() or "SampleObject"
            try:
                size = int(input("Ukuran dalam Bytes (LOH >= 85,000 B, contoh 45000 atau 120000): "))
            except ValueError:
                print(f"{RED}Ukuran harus berupa bilangan bulat integer.{RESET}")
                continue
            sim.allocate(name, size, root_referenced=True)
            
        elif choice == "3":
            all_objs = sim.gen0 + sim.gen1 + sim.gen2 + sim.loh
            if not all_objs:
                print(f"{YELLOW}Tidak ada objek di heap.{RESET}")
                continue
            print(f"\nDaftar objek aktif:")
            for idx, obj in enumerate(all_objs):
                ref_str = f"{GREEN}Rooted{RESET}" if obj.is_root_referenced else f"{RED}Unreachable{RESET}"
                print(f" {idx+1}. {obj.name} ({obj.size_bytes:,} B) - Gen {obj.generation if obj.generation != -1 else 'LOH'} [{ref_str}]")
            
            sel = input(f"Pilih nomor objek untuk di-dereferensikan (hilangkan root ref): ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(all_objs):
                target = all_objs[int(sel)-1]
                target.is_root_referenced = False
                print(f"{YELLOW}Referensi root ke '{target.name}' telah diputus (eligible for GC sweep).{RESET}")
            else:
                print(f"{RED}Pilihan tidak valid.{RESET}")
                
        elif choice == "4":
            gen_in = input("Target Generasi [0 = Ephemeral, 1 = Mid, 2 = Full GC (termasuk LOH)]: ").strip()
            if gen_in in ["0", "1", "2"]:
                sim.collect(generation=int(gen_in))
            else:
                print(f"{RED}Generasi harus 0, 1, atau 2.{RESET}")
                
        elif choice == "5":
            demo_span_vs_heap()
            
        elif choice == "6":
            print(f"\n{BOLD}--- Simulasi ArrayPool<byte>.Shared ---{RESET}")
            buf1 = sim.rent_buffer(64000)
            print("Operasi I/O socket sedang memproses paket network...")
            time.sleep(0.3)
            sim.return_buffer(buf1)
            print("Peminjaman kedua untuk koneksi baru...")
            buf2 = sim.rent_buffer(64000)
            sim.return_buffer(buf2)
            print(f"{GREEN}Keuntungan: Heap tidak dipenuhi oleh alokasi array transient berulang.{RESET}\n")
            
        elif choice == "7":
            name = input("Nama Unmanaged Resource (e.g., SafeFileHandle, SocketNative): ").strip() or "NativeResourceWrapper"
            obj = sim.allocate(name, 35000, root_referenced=True, with_finalizer=True)
            print(f"{YELLOW}Objek terdaftar di Finalization Queue.{RESET}")
            ans = input("Panggil Dispose() sebelum dereference? (y/n): ").strip().lower()
            if ans == 'y':
                obj.is_disposed = True
                print(f"{GREEN}Dispose() dipanggil! GC.SuppressFinalize(this) mengecualikan objek dari Freachable Queue.{RESET}")
            else:
                print(f"{RED}Dispose() TIDAK dipanggil. Finalizer thread akan terpaksa memprosesnya saat GC sweep!{RESET}")
            obj.is_root_referenced = False
            
        elif choice == "0":
            print(f"{BOLD}Simulasi selesai. Memahami manajemen memori .NET membuat kode C# bebas latency dan hemat RAM!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak dikenali.{RESET}")

if __name__ == "__main__":
    interactive_cli()
