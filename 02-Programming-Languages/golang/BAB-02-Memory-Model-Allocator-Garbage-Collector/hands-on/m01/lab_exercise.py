#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Go Memory Model, Allocator & Garbage Collector
Topik: BAB-02 Memory Model, Allocator (TCMalloc/mcache/mcentral/mheap), & Tricolor GC
"""

import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set

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
BG_GREEN = "\033[42m"
BG_MAGENTA = "\033[45m"


class ColorState(Enum):
    WHITE = auto()  # Unvisited / candidate for collection
    GREY = auto()   # Discovered, children not yet scanned
    BLACK = auto()  # Retained, live object with children scanned


@dataclass
class HeapObject:
    id: str
    size_bytes: int
    color: ColorState = ColorState.WHITE
    references: List["HeapObject"] = field(default_factory=list)
    escaped: bool = False
    origin: str = "stack"

    def __repr__(self) -> str:
        return f"Object({self.id}, {self.size_bytes}B, {self.color.name})"


@dataclass
class Span:
    class_id: int
    obj_size: int
    total_slots: int
    free_slots: int

    def allocate(self) -> bool:
        if self.free_slots > 0:
            self.free_slots -= 1
            return True
        return False

    def release(self) -> None:
        if self.free_slots < self.total_slots:
            self.free_slots += 1


class GoMemorySimulator:
    def __init__(self) -> None:
        # Size classes standard Go: (class_id, object_size, num_slots_per_span)
        self.size_classes: Dict[int, int] = {
            1: 8,
            2: 16,
            3: 32,
            4: 48,
            5: 64,
            6: 80,
            7: 96,
            8: 112,
            9: 128,
            10: 256,
        }
        # mcentral pool simulates spans per size class
        self.mcentral_spans: Dict[int, List[Span]] = {
            cid: [Span(cid, sz, 64, 64)] for cid, sz in self.size_classes.items()
        }
        # mcache per P (Processor)
        self.mcache: Dict[int, Optional[Span]] = {cid: None for cid in self.size_classes}
        # Heap objects tracked for GC
        self.heap_objects: Dict[str, HeapObject] = {}
        self.root_pointers: Set[str] = set()

    def print_banner(self) -> None:
        print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
        print(f"{BOLD}{BG_BLUE}{WHITE}  SIMULATOR: GOLANG MEMORY MODEL, ALLOCATOR & TRICOLOR GC  {RESET}")
        print(f"{BOLD}{CYAN}======================================================================{RESET}")
        print(f"{DIM}Materi: Stack vs Heap, Escape Analysis, mcache/mcentral/mheap, Tricolor Mark-Sweep{RESET}\n")

    def escape_analysis_demo(self) -> None:
        print(f"{BOLD}{YELLOW}[1] SIMULASI ESCAPE ANALYSIS (Stack vs Heap Allocation){RESET}")
        print(f"{DIM}Aturan Go Compiler: Objek yang tidak direferensikan ke luar fungsi dialokasikan di Stack.{RESET}")
        print(f"{DIM}Jika pointer lolos ke heap/return/interface, runtime memindahkan ke Heap (escapes to heap).{RESET}\n")

        scenarios = [
            ("func computeSquare(x int) int { result := x * x; return result }", False, "Variabel primitif bernilai, tetap di Stack"),
            ("func createLocal() *User { u := User{ID: 1}; return &u }", True, "&u direturn ke luar fungsi -> Escapes to Heap"),
            ("func logMessage(msg interface{}) { fmt.Println(msg) }", True, "Tipe dilempar ke interface{} -> Escapes to Heap (type assertion overhead)"),
            ("func bufferWork() []byte { buf := make([]byte, 64); return buf[0:2] }", True, "Slice backing array lolos scope fungsi -> Escapes to Heap"),
            ("func smallBuffer() { buf := make([]byte, 32); _ = buf }", False, "Ukuran kecil konstan & tidak kabur -> Stack allocation (zero-GC cost)"),
        ]

        for idx, (code, escapes, reason) in enumerate(scenarios, 1):
            time.sleep(0.3)
            status_badge = f"{BG_MAGENTA}{WHITE} HEAP {RESET}" if escapes else f"{BG_GREEN}{WHITE} STACK {RESET}"
            color_text = RED if escapes else GREEN
            print(f"  {BOLD}Kasus #{idx}:{RESET}")
            print(f"    Code   : {CYAN}{code}{RESET}")
            print(f"    Lokasi : {status_badge} {color_text}({reason}){RESET}\n")

    def _find_size_class(self, size_bytes: int) -> int:
        for cid, max_sz in sorted(self.size_classes.items(), key=lambda x: x[1]):
            if size_bytes <= max_sz:
                return cid
        return 10  # fallback to largest or large allocation

    def allocate_memory(self, obj_id: str, size_bytes: int, is_root: bool = False) -> HeapObject:
        cid = self._find_size_class(size_bytes)
        obj_sz = self.size_classes[cid]

        # Cek mcache lokal P
        span = self.mcache.get(cid)
        if span is None or span.free_slots == 0:
            # Ambil span dari mcentral (butuh lock)
            mcentral_pool = self.mcentral_spans[cid]
            if not mcentral_pool or mcentral_pool[-1].free_slots == 0:
                # Alokasi span baru dari mheap
                new_span = Span(cid, obj_sz, 64, 64)
                mcentral_pool.append(new_span)
            span = mcentral_pool[-1]
            self.mcache[cid] = span
            source = f"{YELLOW}mcentral -> mcache{RESET}"
        else:
            source = f"{GREEN}mcache (lock-free!){RESET}"

        span.allocate()
        obj = HeapObject(id=obj_id, size_bytes=size_bytes, color=ColorState.WHITE, escaped=True, origin="heap")
        self.heap_objects[obj_id] = obj
        if is_root:
            self.root_pointers.add(obj_id)

        print(f"  Alloc [{obj_id:8s}] {size_bytes:3d}B -> SizeClass #{cid:02d} ({obj_sz:3d}B span slot) via {source}")
        return obj

    def allocator_pipeline_demo(self) -> None:
        print(f"\n{BOLD}{YELLOW}[2] SIMULASI GO RUNTIME ALLOCATOR (TCMalloc Derivative){RESET}")
        print(f"{DIM}Hirarki Alokasi: Tiny Allocator (<16B) -> mcache (per-P, lockless) -> mcentral (locked) -> mheap (page-level){RESET}\n")

        self.allocate_memory("node_A", 12, is_root=True)
        self.allocate_memory("node_B", 40)
        self.allocate_memory("node_C", 90)
        self.allocate_memory("node_D", 8, is_root=True)
        self.allocate_memory("node_E", 200)

        # Sambungkan relasi objek (object graph)
        self.heap_objects["node_A"].references.append(self.heap_objects["node_B"])
        self.heap_objects["node_B"].references.append(self.heap_objects["node_C"])
        # node_E dibiarkan orphan (unreachable garbage)

        print(f"\n  {BOLD}Topologi Objek di Heap:{RESET}")
        print(f"    Root: {GREEN}node_A{RESET} -> {CYAN}node_B{RESET} -> {CYAN}node_C{RESET}")
        print(f"    Root: {GREEN}node_D{RESET} (mandiri)")
        print(f"    Orphan: {RED}node_E{RESET} (unreachable / siap disapu GC)\n")

    def tricolor_gc_cycle(self) -> None:
        print(f"{BOLD}{YELLOW}[3] SIMULASI TRICOLOR MARK-SWEEP GC DENGAN WRITE-BARRIER{RESET}")
        print(f"{DIM}Fase: 1. Sweep Termination -> 2. Concurrent Mark (Roots to Grey) -> 3. Mark Termination -> 4. Concurrent Sweep{RESET}\n")

        # Inisialisasi: Semua objek awal berwarna WHITE
        for obj in self.heap_objects.values():
            obj.color = ColorState.WHITE

        print(f"  {BOLD}Langkah 1: Inisialisasi (Semua Objek = WHITE){RESET}")
        for obj in self.heap_objects.values():
            print(f"    [WHITE] {obj.id} ({obj.size_bytes}B)")
        time.sleep(0.4)

        # Langkah 2: Scan Roots -> Masukkan ke GREY set
        grey_set: List[HeapObject] = []
        print(f"\n  {BOLD}Langkah 2: Root Scanning (Stack, Globals, Registers){RESET}")
        for root_id in self.root_pointers:
            root_obj = self.heap_objects[root_id]
            root_obj.color = ColorState.GREY
            grey_set.append(root_obj)
            print(f"    {MAGENTA}Root terdeteksi:{RESET} {root_obj.id} diubah menjadi {MAGENTA}GREY{RESET}")
        time.sleep(0.4)

        # Langkah 3: Concurrent Mark Loop (Pewarnaan berulang)
        print(f"\n  {BOLD}Langkah 3: Proses Marking Loop (Tricolor Invariant){RESET}")
        step = 1
        while grey_set:
            curr = grey_set.pop(0)
            print(f"    Iterasi {step}: Memproses {MAGENTA}[GREY] {curr.id}{RESET}...")
            time.sleep(0.3)

            for child in curr.references:
                if child.color == ColorState.WHITE:
                    child.color = ColorState.GREY
                    grey_set.append(child)
                    print(f"      -> Menemukan referensi anak {child.id}: WHITE -> {MAGENTA}GREY{RESET}")

            curr.color = ColorState.BLACK
            print(f"      -> Objek {curr.id} selesai dipindai: GREY -> {BOLD}{GREEN}BLACK{RESET}")
            step += 1
            time.sleep(0.2)

        # Tampilkan status warna akhir
        print(f"\n  {BOLD}Hasil Akhir Pewarnaan Tri-Color:{RESET}")
        for obj_id, obj in self.heap_objects.items():
            if obj.color == ColorState.BLACK:
                color_badge = f"{BG_GREEN}{WHITE} BLACK (LIVE) {RESET}"
            elif obj.color == ColorState.WHITE:
                color_badge = f"{RED}{BOLD} WHITE (GARBAGE) {RESET}"
            else:
                color_badge = f"{MAGENTA} GREY {RESET}"
            print(f"    Object {obj_id:8s}: {color_badge}")

        # Langkah 4: Sweep Phase (Sapuan Memori Mati)
        print(f"\n  {BOLD}Langkah 4: Concurrent Sweep (Membersihkan White Objects){RESET}")
        time.sleep(0.4)
        survivors = {}
        reclaimed_bytes = 0

        for obj_id, obj in self.heap_objects.items():
            if obj.color == ColorState.WHITE:
                reclaimed_bytes += obj.size_bytes
                cid = self._find_size_class(obj.size_bytes)
                span = self.mcache.get(cid)
                if span:
                    span.release()
                print(f"    {RED}[DEALLOCATED]{RESET} {obj_id} ({obj.size_bytes}B dibebaskan kembali ke span)")
            else:
                survivors[obj_id] = obj

        self.heap_objects = survivors
        print(f"\n  {BOLD}{GREEN}GC Selesai!{RESET} Memori dibebaskan: {BOLD}{reclaimed_bytes} bytes{RESET}")
        print(f"  Objek hidup tersisa di Heap: {[k for k in self.heap_objects.keys()]}\n")

    def run_all(self) -> None:
        self.print_banner()
        self.escape_analysis_demo()
        self.allocator_pipeline_demo()
        self.tricolor_gc_cycle()
        print(f"{BOLD}{GREEN}Seluruh demonstrasi simulasi siklus memori Go berhasil diselesaikan!{RESET}\n")


def main() -> None:
    simulator = GoMemorySimulator()
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        simulator.run_all()
        return

    while True:
        simulator.print_banner()
        print(f"{BOLD}Pilih Modul Simulasi:{RESET}")
        print(f"  {CYAN}1.{RESET} Escape Analysis (Stack vs Heap Allocation)")
        print(f"  {CYAN}2.{RESET} Memory Allocator (mcache, mcentral, span classes)")
        print(f"  {CYAN}3.{RESET} Tricolor Mark-Sweep Garbage Collection & Sweep")
        print(f"  {CYAN}4.{RESET} Jalankan Seluruh Simulasi Sekaligus")
        print(f"  {CYAN}5.{RESET} Keluar")

        try:
            choice = input(f"\n{BOLD}Masukkan pilihan (1-5): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            simulator.escape_analysis_demo()
        elif choice == "2":
            simulator.allocator_pipeline_demo()
        elif choice == "3":
            if not simulator.heap_objects:
                print(f"{YELLOW}Menyiapkan alokasi objek dummy terlebih dahulu...{RESET}")
                simulator.allocator_pipeline_demo()
            simulator.tricolor_gc_cycle()
        elif choice == "4":
            simulator.run_all()
        elif choice == "5":
            print(f"{GREEN}Terima kasih! Belajar Go Memory Model selesai.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")

        try:
            input(f"\n{DIM}Tekan Enter untuk melanjutkan...{RESET}")
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    main()
