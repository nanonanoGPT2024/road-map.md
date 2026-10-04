#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi & Arsitektur .NET / C#
Materi: BAB-01 - Fondasi dan Arsitektur .NET Runtime (CLR, CTS, CLI, JIT, GC)

Script simulasi mandiri untuk memvisualisasikan cara kerja:
1. Pipeline Kompilasi: C# Source -> Roslyn -> CIL (MSIL) -> JIT -> Native Code
2. Memory Model: Stack vs Managed Heap, Value Types vs Reference Types, Boxing/Unboxing
3. Generational Garbage Collector (.NET Generational GC: Gen 0, Gen 1, Gen 2, LOH)
"""

import sys
import time
from typing import Any, Dict, List, Optional


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Foreground colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    # Backgrounds
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_GRAY = "\033[100m"


def print_banner(title: str) -> None:
    border = "=" * 68
    print(f"\n{ANSI.CYAN}{ANSI.BOLD}{border}")
    print(f" {title.center(66)}")
    print(f"{border}{ANSI.RESET}\n")


def print_step(step_num: int, title: str) -> None:
    print(f"{ANSI.YELLOW}{ANSI.BOLD}[Tahap {step_num}]{ANSI.RESET} {ANSI.WHITE}{ANSI.BOLD}{title}{ANSI.RESET}")


def pause(seconds: float = 0.6) -> None:
    time.sleep(seconds)


class JITSimulator:
    """Simulasi Roslyn Compiler dan CLR JIT (Tiered Compilation: Tier 0 vs Tier 1)."""

    def __init__(self) -> None:
        self.call_counts: Dict[str, int] = {}
        self.compiled_tier: Dict[str, str] = {}

    def compile_source_to_cil(self, method_name: str, csharp_code: str) -> List[str]:
        print(f"\n{ANSI.MAGENTA}[Roslyn Frontend]{ANSI.RESET} Mengompilasi C# source ke CIL bytecode...")
        pause(0.4)
        print(f"{ANSI.DIM}C# Code:\n{csharp_code.strip()}{ANSI.RESET}\n")
        pause(0.5)

        il_code = [
            f".method public static int32 {method_name}(int32 a, int32 b) cil managed",
            "{",
            "    .maxstack 2",
            "    ldarg.0      // Muat argumen a ke evaluation stack",
            "    ldarg.1      // Muat argumen b ke evaluation stack",
            "    add          // Operasi penambahan IL",
            "    ret          // Return hasil ke caller",
            "}"
        ]
        print(f"{ANSI.GREEN}[Roslyn Output - CIL / MSIL Assembly]{ANSI.RESET}")
        for line in il_code:
            print(f"  {ANSI.DIM}{line}{ANSI.RESET}")
        return il_code

    def invoke_method(self, method_name: str, a: int, b: int) -> int:
        count = self.call_counts.get(method_name, 0) + 1
        self.call_counts[method_name] = count

        if count == 1:
            self.compiled_tier[method_name] = "Tier 0 (Quick JIT - Min Optimization)"
            print(f"{ANSI.YELLOW}-> Pemanggilan pertama (Count: {count}): JIT Mengompilasi via {self.compiled_tier[method_name]}{ANSI.RESET}")
            print(f"   {ANSI.DIM}Status: Menghasilkan kode native cepat agar startup time instan.{ANSI.RESET}")
        elif count >= 3 and "Tier 1" not in self.compiled_tier[method_name]:
            self.compiled_tier[method_name] = "Tier 1 (Dynamic PGO / Optimized JIT)"
            print(f"{ANSI.GREEN}-> Hot Method Detected (Count: {count})! Tiered Compilation memicu Re-JIT: {self.compiled_tier[method_name]}{ANSI.RESET}")
            print(f"   {ANSI.DIM}Status: Loop unrolling, inlining, register allocation optimal.{ANSI.RESET}")
        else:
            print(f"-> Pemanggilan method '{method_name}' (Count: {count}) dieksekusi langsung via native cache [{self.compiled_tier[method_name]}]")

        return a + b


class MemoryModelSimulator:
    """Simulasi Stack vs Managed Heap, Value Types vs Reference Types, Boxing/Unboxing."""

    def __init__(self) -> None:
        self.stack: List[Dict[str, Any]] = []
        self.heap: Dict[int, Dict[str, Any]] = {}
        self.next_heap_address = 0x1000

    def push_value_type(self, name: str, val_type: str, value: Any) -> None:
        frame_entry = {
            "name": name,
            "category": "ValueType (CTS struct/primitive)",
            "type": val_type,
            "raw_value": value,
            "location": "Stack Frame"
        }
        self.stack.append(frame_entry)
        print(f"{ANSI.GREEN}[Stack Alloc]{ANSI.RESET} Variabel '{name}' ({val_type}) dialokasikan langsung di Stack: value={value}")

    def push_reference_type(self, name: str, class_name: str, payload: Dict[str, Any]) -> int:
        addr = self.next_heap_address
        self.next_heap_address += 0x64

        heap_object = {
            "address": hex(addr),
            "type": class_name,
            "sync_block_index": 0,
            "type_handle": f"MT_{class_name}",
            "fields": payload,
            "generation": 0,
            "marked": True
        }
        self.heap[addr] = heap_object

        stack_ref = {
            "name": name,
            "category": "ReferenceType Pointer",
            "type": f"Ref to {class_name}",
            "raw_value": hex(addr),
            "location": "Stack Frame"
        }
        self.stack.append(stack_ref)
        print(f"{ANSI.BLUE}[Heap Alloc]{ANSI.RESET} Objek '{class_name}' dialokasikan di Managed Heap ({hex(addr)}) dengan TypeHandle & SyncBlockIndex.")
        print(f"             Pointer 64-bit disimpan di Stack: {name} -> {hex(addr)}")
        return addr

    def box_value(self, val_name: str, target_name: str) -> Optional[int]:
        # Cari value di stack
        val_entry = next((item for item in reversed(self.stack) if item["name"] == val_name), None)
        if not val_entry:
            print(f"{ANSI.RED}Variabel '{val_name}' tidak ditemukan di stack!{ANSI.RESET}")
            return None

        addr = self.next_heap_address
        self.next_heap_address += 0x64
        self.heap[addr] = {
            "address": hex(addr),
            "type": f"System.Object (Boxed {val_entry['type']})",
            "sync_block_index": 0,
            "type_handle": f"MT_Boxed_{val_entry['type']}",
            "fields": {"boxed_value": val_entry["raw_value"]},
            "generation": 0,
            "marked": True
        }

        self.stack.append({
            "name": target_name,
            "category": "Boxed Object Reference",
            "type": "System.Object",
            "raw_value": hex(addr),
            "location": "Stack Frame"
        })
        print(f"{ANSI.YELLOW}[Boxing Warning!]{ANSI.RESET} Menyalin nilai value-type '{val_name}' ({val_entry['raw_value']}) ke alokasi baru di Managed Heap ({hex(addr)}).")
        print(f"                   Menimbulkan memory overhead (MethodTable + SyncBlock + Heap Payload).")
        return addr

    def unbox_value(self, boxed_ref_name: str, target_val_name: str, expected_type: str) -> None:
        ref_entry = next((item for item in reversed(self.stack) if item["name"] == boxed_ref_name), None)
        if not ref_entry:
            print(f"{ANSI.RED}Reference '{boxed_ref_name}' tidak ditemukan di stack!{ANSI.RESET}")
            return

        addr = int(ref_entry["raw_value"], 16)
        heap_obj = self.heap.get(addr)
        if not heap_obj:
            print(f"{ANSI.RED}NullReferenceException: Heap kosong pada {hex(addr)}{ANSI.RESET}")
            return

        unboxed_val = heap_obj["fields"]["boxed_value"]
        self.stack.append({
            "name": target_val_name,
            "category": f"Unboxed ValueType ({expected_type})",
            "type": expected_type,
            "raw_value": unboxed_val,
            "location": "Stack Frame"
        })
        print(f"{ANSI.CYAN}[Unboxing]{ANSI.RESET} Mengekstrak nilai mentah dari heap {hex(addr)} kembali ke Stack: {target_val_name} = {unboxed_val}")

    def display_memory(self) -> None:
        print(f"\n{ANSI.BOLD}--- STATUS MEMORI SAAT INI ---{ANSI.RESET}")
        print(f"{ANSI.WHITE}{ANSI.BG_GRAY} [STACK (Fast, LIFO, Thread-Local)] {ANSI.RESET}")
        if not self.stack:
            print(f"  {ANSI.DIM}(Stack Kosong){ANSI.RESET}")
        for item in reversed(self.stack):
            print(f"  | {item['name']:<12} | {item['type']:<22} | Value: {str(item['raw_value']):<10} | {item['category']}")

        print(f"\n{ANSI.WHITE}{ANSI.BG_BLUE} [MANAGED HEAP (Garbage Collected)] {ANSI.RESET}")
        if not self.heap:
            print(f"  {ANSI.DIM}(Heap Kosong){ANSI.RESET}")
        for addr, obj in self.heap.items():
            fields_str = ", ".join(f"{k}: {v}" for k, v in obj["fields"].items())
            print(f"  @ {hex(addr)} [Gen {obj['generation']}] {obj['type']} -> Fields: {{{fields_str}}}")
        print("-" * 50)


class GarbageCollectorSimulator:
    """Simulasi .NET Generational Garbage Collector (Gen 0, Gen 1, Gen 2, Mark-Sweep-Compact)."""

    def __init__(self, memory: MemoryModelSimulator) -> None:
        self.memory = memory
        self.collection_counts = {0: 0, 1: 0, 2: 0}

    def collect(self, generation: int = 0) -> None:
        self.collection_counts[generation] += 1
        print(f"\n{ANSI.RED}{ANSI.BOLD}[GC Triggered]{ANSI.RESET} Menjalankan Garbage Collection untuk Gen {generation} (Run #{self.collection_counts[generation]})...")
        pause(0.5)

        # 1. Mark phase: Cari roots dari stack
        live_addresses = set()
        for item in self.memory.stack:
            val = str(item["raw_value"])
            if val.startswith("0x"):
                try:
                    live_addresses.add(int(val, 16))
                except ValueError:
                    pass

        print(f"{ANSI.YELLOW}[Phase 1: Mark]{ANSI.RESET} Memeriksa root references dari Stack & Static roots...")
        print(f"               Live Addresses terdeteksi: {[hex(a) for a in live_addresses]}")
        pause(0.4)

        # 2. Sweep & Compact / Promote phase
        survivors = []
        dead_objects = []

        for addr, obj in list(self.memory.heap.items()):
            if obj["generation"] <= generation:
                if addr in live_addresses:
                    # Promosi generasi objek jika bertahan dari sweep (max Gen 2)
                    old_gen = obj["generation"]
                    obj["generation"] = min(2, old_gen + 1)
                    survivors.append((addr, obj["type"], old_gen, obj["generation"]))
                else:
                    dead_objects.append((addr, obj["type"], obj["generation"]))
                    del self.memory.heap[addr]

        print(f"{ANSI.RED}[Phase 2: Sweep]{ANSI.RESET} Membersihkan {len(dead_objects)} objek mati/unreachable dari heap:")
        for addr, otype, gen in dead_objects:
            print(f"  {ANSI.RED}X{ANSI.RESET} Dihapus: {hex(addr)} ({otype}) di Gen {gen}")

        print(f"{ANSI.GREEN}[Phase 3: Compact & Promotion]{ANSI.RESET} Memadatkan sisa objek dan menaikkan generasi:")
        for addr, otype, old_g, new_g in survivors:
            print(f"  {ANSI.GREEN}* {hex(addr)}{ANSI.RESET} ({otype}): Gen {old_g} -> Gen {new_g}")


def run_compilation_demo() -> None:
    print_banner("1. Pipeline Eksekusi .NET: C# -> CIL -> JIT Compiler")
    jit = JITSimulator()
    sample_code = """public static int Add(int a, int b) {
    return a + b;
}"""
    jit.compile_source_to_cil("Add", sample_code)

    print_step(1, "Simulasi Pemanggilan Method Berulang Kali untuk Mengamati Tiered Compilation")
    for i in range(1, 4):
        pause(0.4)
        result = jit.invoke_method("Add", 10 * i, 5 * i)
        print(f"   Hasil eksekusi: Add({10*i}, {5*i}) = {result}")


def run_memory_demo() -> None:
    print_banner("2. Memory Model: Stack vs Heap & Boxing/Unboxing")
    mem = MemoryModelSimulator()

    print_step(1, "Alokasi Value Types di Stack Frame")
    mem.push_value_type("x", "System.Int32", 42)
    mem.push_value_type("isActive", "System.Boolean", True)
    mem.display_memory()
    pause(0.6)

    print_step(2, "Alokasi Reference Types di Managed Heap")
    mem.push_reference_type("user1", "OrderCustomer", {"id": 101, "name": "Budi Santoso"})
    mem.display_memory()
    pause(0.6)

    print_step(3, "Boxing: Mengonversi System.Int32 ke System.Object")
    mem.box_value("x", "boxedObj")
    mem.display_memory()
    pause(0.6)

    print_step(4, "Unboxing: Mengonversi kembali ke int primitive di Stack")
    mem.unbox_value("boxedObj", "unboxedX", "System.Int32")
    mem.display_memory()


def run_gc_demo() -> None:
    print_banner("3. .NET Generational Garbage Collector (Gen 0, 1, 2)")
    mem = MemoryModelSimulator()
    gc = GarbageCollectorSimulator(mem)

    print_step(1, "Membuat Objek di Heap (Sebagian Rooted, Sebagian Temporary)")
    mem.push_reference_type("activeSession", "SessionData", {"user": "Alice", "token": "XYZ987"})
    
    # Objek temporer tanpa reference kuat di stack (simulasi out-of-scope variable)
    addr_temp1 = mem.push_reference_type("tempBuffer1", "ByteStream", {"size": 4096})
    addr_temp2 = mem.push_reference_type("tempBuffer2", "XmlNodeCache", {"count": 15})

    print(f"\n{ANSI.YELLOW}[Simulasi Keluar Scope]{ANSI.RESET} Variabel lokal tempBuffer1 & tempBuffer2 dibuang dari Stack Frame...")
    mem.stack = [item for item in mem.stack if item["name"] not in ("tempBuffer1", "tempBuffer2")]
    mem.display_memory()
    pause(0.6)

    print_step(2, "Memicu GC Gen 0")
    gc.collect(generation=0)
    mem.display_memory()
    pause(0.6)

    print_step(3, "Alokasi Objek Baru Lagi dan Memicu Gen 1 Collection")
    mem.push_reference_type("reportCache", "MonthlyReport", {"year": 2026, "month": 10})
    gc.collect(generation=1)
    mem.display_memory()


def main_interactive_menu() -> None:
    while True:
        print_banner("INTERACTIVE LAB: FONDASI & ARSITEKTUR .NET (C#)")
        print(f"{ANSI.BOLD}Pilih simulasi konsep runtime yang ingin dijalankan:{ANSI.RESET}")
        print(f"  {ANSI.CYAN}[1]{ANSI.RESET} Pipeline Kompilasi C# & JIT Tiered Compilation (Tier 0 & Tier 1)")
        print(f"  {ANSI.CYAN}[2]{ANSI.RESET} Memory Model: Stack vs Heap & Biaya Boxing/Unboxing")
        print(f"  {ANSI.CYAN}[3]{ANSI.RESET} Generational Garbage Collector (Gen 0, Gen 1, Mark-Sweep)")
        print(f"  {ANSI.CYAN}[4]{ANSI.RESET} Jalankan SEMUA Modul Secara Terpadu (Full Walkthrough)")
        print(f"  {ANSI.CYAN}[5]{ANSI.RESET} Keluar (Exit)")
        print(f"{ANSI.DIM}{'-' * 68}{ANSI.RESET}")

        try:
            choice = input(f"{ANSI.YELLOW}Masukkan pilihan (1-5): {ANSI.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSelesai.")
            break

        if choice == "1":
            run_compilation_demo()
        elif choice == "2":
            run_memory_demo()
        elif choice == "3":
            run_gc_demo()
        elif choice == "4":
            run_compilation_demo()
            pause(1.0)
            run_memory_demo()
            pause(1.0)
            run_gc_demo()
        elif choice == "5":
            print(f"\n{ANSI.GREEN}Terima kasih telah mempelajari fondasi arsitektur .NET runtime!{ANSI.RESET}\n")
            break
        else:
            print(f"{ANSI.RED}Pilihan tidak valid. Silakan masukkan angka 1-5.{ANSI.RESET}")
        
        try:
            input(f"\n{ANSI.DIM}Tekan [Enter] untuk kembali ke menu utama...{ANSI.RESET}")
        except (KeyboardInterrupt, EOFError):
            break


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Mode non-interaktif untuk CI/automated test run
        run_compilation_demo()
        run_memory_demo()
        run_gc_demo()
    else:
        main_interactive_menu()
