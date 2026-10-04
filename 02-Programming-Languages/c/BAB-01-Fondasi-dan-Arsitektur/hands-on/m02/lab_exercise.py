#!/usr/bin/env python3
"""
Lab Hands-on: Arsitektur Kompilasi, Linking, & Memory Layout (C Low-Level Deep Dive)
Kategori: 02-Programming-Languages / c / Bab 01 - Modul 02

Script ini mensimulasikan siklus hidup program C secara komprehensif:
1. Tahap Object File Generation (.o) dengan Segmentasi (.text, .data, .bss) & Symbol Table.
2. Linker Engine: Symbol Resolution, Collision Detection, & Address Relocation (R_X86_64).
3. Runtime Process Memory Layout: Alokasi VMA (Virtual Memory Address), Heap growth,
   serta Stack Frame dynamics (prologue/epilogue, stack-heap collision check).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import sys
import time

# --- ANSI Color Codes untuk visualisasi CLI ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_MAGENTA= "\033[35m"
CLR_CYAN   = "\033[36m"
CLR_GRAY   = "\033[90m"


class SymbolBinding(Enum):
    LOCAL = "LOCAL"
    GLOBAL = "GLOBAL"
    WEAK = "WEAK"


class SymbolType(Enum):
    NOTYPE = "NOTYPE"
    OBJECT = "OBJECT"   # Variabel
    FUNC = "FUNC"       # Fungsi


class RelocType(Enum):
    R_X86_64_64 = "R_X86_64_64"       # Absolute 64-bit address relocation
    R_X86_64_PC32 = "R_X86_64_PC32"   # PC-relative 32-bit relocation


@dataclass
class Symbol:
    name: str
    sym_type: SymbolType
    binding: SymbolBinding
    section: str       # '.text', '.data', '.bss', atau '*UND*' (Undefined)
    value: int         # Offset di dalam section atau 0 jika undefined
    size: int = 0
    resolved_addr: Optional[int] = None


@dataclass
class RelocationEntry:
    offset: int          # Offset instruksi/data yang butuh patching
    symbol_name: str     # Symbol yang direferensikan
    reloc_type: RelocType
    addend: int = 0      # Nilai koreksi penyesuaian (biasanya -4 untuk PC-relative call)


@dataclass
class ObjectFile:
    name: str
    text_sec: bytearray = field(default_factory=bytearray)
    data_sec: bytearray = field(default_factory=bytearray)
    bss_size: int = 0
    symbols: Dict[str, Symbol] = field(default_factory=dict)
    relocations: Dict[str, List[RelocationEntry]] = field(default_factory=dict)

    def add_symbol(self, sym: Symbol):
        self.symbols[sym.name] = sym

    def add_reloc(self, section: str, reloc: RelocationEntry):
        if section not in self.relocations:
            self.relocations[section] = []
        self.relocations[section].append(reloc)


class Linker:
    """
    Simulasi Static Linker: Menggabungkan Translation Units (.o),
    Menyelesaikan cross-reference symbol (Resolution), dan menghitung Relocation patch.
    """
    BASE_TEXT_VMA = 0x00400000  # Standar VMA Linux x86_64 non-PIE
    PAGE_SIZE     = 0x1000      # 4KB Alignment

    def __init__(self):
        self.objects: List[ObjectFile] = []
        self.global_symtab: Dict[str, Symbol] = {}
        
        # Segment Tergabung
        self.merged_text = bytearray()
        self.merged_data = bytearray()
        self.total_bss_size = 0

        # Memory Map Section
        self.sec_vma: Dict[str, int] = {}

    def add_object(self, obj: ObjectFile):
        self.objects.append(obj)

    def align_to(self, address: int, alignment: int) -> int:
        return (address + alignment - 1) & ~(alignment - 1)

    def resolve_symbols(self):
        """Pass 1 Linker: Memvalidasi simbol, cek duplikasi & eksistensi eksternal."""
        print(f"\n{CLR_BOLD}[LINKER PASS 1: SYMBOL RESOLUTION]{CLR_RESET}")
        for obj in self.objects:
            for name, sym in obj.symbols.items():
                if sym.section != "*UND*":
                    if sym.binding == SymbolBinding.GLOBAL:
                        if name in self.global_symtab and self.global_symtab[name].section != "*UND*":
                            raise RuntimeError(f"Linker Error: Duplicate strong symbol definition -> '{name}' "
                                               f"di {obj.name} dan definisi sebelumnya!")
                        self.global_symtab[name] = sym
                        print(f"  {CLR_GREEN}✓ Exported Strong Symbol:{CLR_RESET} {name:20} dari {obj.name}")

        # Validasi apakah ada undefined symbol yang belum terselesaikan
        for obj in self.objects:
            for name, sym in obj.symbols.items():
                if sym.section == "*UND*":
                    if name not in self.global_symtab:
                        raise RuntimeError(f"Linker Error: Undefined reference to symbol -> '{name}' di {obj.name}")
                    print(f"  {CLR_CYAN}⇄ Resolved Reference:{CLR_RESET}    {name:20} ({obj.name} -> defined elsewhere)")

    def layout_and_relocate(self):
        """Pass 2 Linker: Menggabungkan section, menetapkan VMA, dan kalkulasi relocation."""
        print(f"\n{CLR_BOLD}[LINKER PASS 2: SECTION MERGING & RELOCATION]{CLR_RESET}")
        
        # 1. Tata letak VMA untuk .text (Executable)
        text_vma = self.BASE_TEXT_VMA
        self.sec_vma['.text'] = text_vma
        
        obj_text_offsets = {}
        for obj in self.objects:
            obj_text_offsets[obj.name] = len(self.merged_text)
            # Update symbol offset lokal ke address global
            for sym in obj.symbols.values():
                if sym.section == '.text':
                    sym.resolved_addr = text_vma + obj_text_offsets[obj.name] + sym.value
            self.merged_text.extend(obj.text_sec)

        # 2. Tata letak VMA untuk .data (Read/Write) - Diberi page alignment
        data_vma = self.align_to(text_vma + len(self.merged_text), self.PAGE_SIZE)
        self.sec_vma['.data'] = data_vma
        
        obj_data_offsets = {}
        for obj in self.objects:
            obj_data_offsets[obj.name] = len(self.merged_data)
            for sym in obj.symbols.values():
                if sym.section == '.data':
                    sym.resolved_addr = data_vma + obj_data_offsets[obj.name] + sym.value
            self.merged_data.extend(obj.data_sec)

        # 3. Tata letak VMA untuk .bss (Zero Initialized)
        bss_vma = data_vma + len(self.merged_data)
        self.sec_vma['.bss'] = bss_vma
        current_bss_offset = 0
        for obj in self.objects:
            for sym in obj.symbols.values():
                if sym.section == '.bss':
                    sym.resolved_addr = bss_vma + current_bss_offset + sym.value
            current_bss_offset += obj.bss_size
        self.total_bss_size = current_bss_offset

        # 4. Patching Relokasi
        for obj in self.objects:
            if '.text' in obj.relocations:
                for reloc in obj.relocations['.text']:
                    target_sym = self.global_symtab[reloc.symbol_name]
                    call_site_vma = text_vma + obj_text_offsets[obj.name] + reloc.offset
                    
                    if reloc.reloc_type == RelocType.R_X86_64_PC32:
                        # Formula: Target - (CallSite + 4)
                        pc_relative_offset = target_sym.resolved_addr - (call_site_vma + 4)
                        print(f"  {CLR_YELLOW}⚡ Patching Reloc:{CLR_RESET} {reloc.reloc_type.value} pada VMA 0x{call_site_vma:08X} "
                              f"-> Simbol: '{reloc.symbol_name}' (VMA: 0x{target_sym.resolved_addr:08X}), Delta: {pc_relative_offset}")
                    elif reloc.reloc_type == RelocType.R_X86_64_64:
                        print(f"  {CLR_YELLOW}⚡ Patching Reloc:{CLR_RESET} {reloc.reloc_type.value} pada VMA 0x{call_site_vma:08X} "
                              f"-> Simbol: '{reloc.symbol_name}' (Absolute VMA: 0x{target_sym.resolved_addr:08X})")


class ProcessMemorySimulator:
    """
    Simulasi Runtime Layout Memori C:
    Text, Data, BSS, Heap (tumbuh ke atas), Stack (tumbuh ke bawah).
    """
    STACK_TOP = 0x7FFFFFFFF000  # Canonical User-space Stack Top (x86-64)

    def __init__(self, linker: Linker):
        self.linker = linker
        self.heap_start = self.linker.sec_vma['.bss'] + self.linker.total_bss_size
        self.brk = self.heap_start  # Program Break
        self.rsp = self.STACK_TOP   # Stack Pointer
        self.call_stack: List[str] = []

    def malloc(self, size: int) -> int:
        """Simulasi brk() heap allocation."""
        aligned_size = (size + 7) & ~7  # 8-byte word alignment
        allocated_addr = self.brk
        self.brk += aligned_size
        if self.brk >= self.rsp:
            raise MemoryError(f"{CLR_RED}CRITICAL: OOM / Heap-Stack Collision detected!{CLR_RESET}")
        return allocated_addr

    def push_stack_frame(self, func_name: str, frame_size: int):
        """Simulasi Function Call Prologue: push %rbp; mov %rsp, %rbp; sub $size, %rsp."""
        aligned_frame = (frame_size + 15) & ~15  # x86_64 ABI 16-byte stack alignment
        self.rsp -= aligned_frame
        self.call_stack.append(func_name)
        if self.rsp <= self.brk:
            raise RecursionError(f"{CLR_RED}CRITICAL: Stack Overflow! Collision with Heap.{CLR_RESET}")

    def pop_stack_frame(self):
        """Simulasi Function Epilogue: leave; ret."""
        if self.call_stack:
            func_name = self.call_stack.pop()
            return func_name
        return None

    def dump_memory_map(self):
        print(f"\n{CLR_BOLD}{'='*75}{CLR_RESET}")
        print(f"{CLR_BOLD}             PROCESS VIRTUAL ADDRESS SPACE LAYOUT (x86-64)             {CLR_RESET}")
        print(f"{CLR_BOLD}{'='*75}{CLR_RESET}")
        print(f"{CLR_MAGENTA}[0x7FFFFFFFFFFF]  High Memory (Kernel Space - Restricted){CLR_RESET}")
        print(f"       |")
        print(f"       v   {CLR_RED}STACK SEGMENT (Grows Downward ↓){CLR_RESET}")
        print(f"  [0x{self.rsp:012X}] RSP (Current Stack Pointer) -> Active Frames: {self.call_stack}")
        print(f"       |")
        print(f"       :   {CLR_GRAY}(Unallocated Virtual Memory Gap){CLR_RESET}")
        print(f"       |")
        print(f"  [0x{self.brk:012X}] Program Break (brk) -> Heap End")
        print(f"       ^   {CLR_YELLOW}HEAP SEGMENT (Grows Upward ↑){CLR_RESET}")
        print(f"  [0x{self.heap_start:012X}] Heap Base (End of .bss)")
        print(f"  [0x{self.linker.sec_vma['.bss']:012X}] .bss Segment  (Size: {self.linker.total_bss_size} bytes - Zero Initted)")
        print(f"  [0x{self.linker.sec_vma['.data']:012X}] .data Segment (Size: {len(self.linker.merged_data)} bytes - Initialized RW)")
        print(f"  [0x{self.linker.sec_vma['.text']:012X}] .text Segment (Size: {len(self.linker.merged_text)} bytes - Code RX)")
        print(f"       |")
        print(f"{CLR_MAGENTA}[0x000000000000]  Null Pointer Trap Page & Reserved Areas{CLR_RESET}")
        print(f"{CLR_BOLD}{'='*75}{CLR_RESET}\n")


def build_simulation_units() -> List[ObjectFile]:
    """
    Membuat 2 translation unit tiruan:
    1. math_engine.c:
       int g_multiplier = 42;          // .data
       int g_calc_counter;             // .bss
       int compute(int x);             // .text
    2. main.c:
       extern int g_multiplier;        // *UND*
       extern int compute(int x);      // *UND*
       int main();                     // .text
    """
    # --- math_engine.o ---
    math_obj = ObjectFile(name="math_engine.o")
    math_obj.text_sec = bytearray(b"\x55\x48\x89\xE5\x89\x7D\xFC\xB8\x00\x00\x00\x00\x5D\xC3")  # 14 bytes code
    math_obj.data_sec = bytearray(b"\x2A\x00\x00\x00")  # int 42 (4 bytes)
    math_obj.bss_size = 4                                # int g_calc_counter (4 bytes uninit)

    math_obj.add_symbol(Symbol("compute", SymbolType.FUNC, SymbolBinding.GLOBAL, ".text", 0x00, size=14))
    math_obj.add_symbol(Symbol("g_multiplier", SymbolType.OBJECT, SymbolBinding.GLOBAL, ".data", 0x00, size=4))
    math_obj.add_symbol(Symbol("g_calc_counter", SymbolType.OBJECT, SymbolBinding.GLOBAL, ".bss", 0x00, size=4))

    # --- main.o ---
    main_obj = ObjectFile(name="main.o")
    # Code main: call compute() -> butuh relokasi PC32 di offset 0x08
    main_obj.text_sec = bytearray(b"\x55\x48\x89\xE5\xBF\x05\x00\x00\xE8\x00\x00\x00\x00\x5D\xC3") # 15 bytes
    main_obj.data_sec = bytearray()
    main_obj.bss_size = 0

    main_obj.add_symbol(Symbol("main", SymbolType.FUNC, SymbolBinding.GLOBAL, ".text", 0x00, size=15))
    main_obj.add_symbol(Symbol("compute", SymbolType.FUNC, SymbolBinding.GLOBAL, "*UND*", 0x00))
    main_obj.add_symbol(Symbol("g_multiplier", SymbolType.OBJECT, SymbolBinding.GLOBAL, "*UND*", 0x00))

    # Catat relokasi pemanggilan fungsi 'compute'
    main_obj.add_reloc(".text", RelocationEntry(offset=0x09, symbol_name="compute", reloc_type=RelocType.R_X86_64_PC32, addend=-4))

    return [math_obj, main_obj]


def main():
    print(f"{CLR_BOLD}{CLR_CYAN}=== C COMPILATION PIPELINE, LINKING & MEMORY LAYOUT LAB ==={CLR_RESET}")
    print(f"Memulai pipeline simulasi objek ELF64...\n")
    time.sleep(0.3)

    # 1. Konstruksi Object Files
    obj_files = build_simulation_units()
    for obj in obj_files:
        print(f"{CLR_BOLD}Unit Kompilasi Dihasilkan: {obj.name}{CLR_RESET}")
        for s_name, sym in obj.symbols.items():
            print(f"  [SYM] {s_name:18} | Bind: {sym.binding.value:6} | Sec: {sym.section:6} | Value: 0x{sym.value:04X}")
        for sec, relocs in obj.relocations.items():
            for r in relocs:
                print(f"  [REL] Sec: {sec} | Offset: 0x{r.offset:02X} | Type: {r.reloc_type.value} -> Sym: {r.symbol_name}")

    # 2. Linker: Symbol Resolution & Address Relocation
    linker = Linker()
    for obj in obj_files:
        linker.add_object(obj)

    linker.resolve_symbols()
    linker.layout_and_relocate()

    # 3. Simulasi Runtime Virtual Memory
    vm_sim = ProcessMemorySimulator(linker)
    print(f"\n{CLR_BOLD}[MEMULAI SIMULASI RUNTIME PROSES]{CLR_RESET}")
    vm_sim.dump_memory_map()

    # Simulasi eksekusi dan dinamika Stack & Heap
    print(f"{CLR_CYAN}--> Eksekusi Memasuki '_start' -> main(){CLR_RESET}")
    vm_sim.push_stack_frame("main", frame_size=32)
    
    print(f"{CLR_CYAN}--> main() memanggil malloc(64) untuk buffer heap...{CLR_RESET}")
    ptr1 = vm_sim.malloc(64)
    print(f"    Alokasi Heap Berhasil di VMA: {CLR_GREEN}0x{ptr1:08X}{CLR_RESET}")

    print(f"{CLR_CYAN}--> main() memanggil compute(5)... Stack frame compute dialokasikan.{CLR_RESET}")
    vm_sim.push_stack_frame("compute", frame_size=48)
    
    print(f"{CLR_CYAN}--> compute() memanggil malloc(128)...{CLR_RESET}")
    ptr2 = vm_sim.malloc(128)
    print(f"    Alokasi Heap Berhasil di VMA: {CLR_GREEN}0x{ptr2:08X}{CLR_RESET}")

    vm_sim.dump_memory_map()

    print(f"{CLR_CYAN}--> compute() selesai, stack unwinding (epilogue)...{CLR_RESET}")
    popped = vm_sim.pop_stack_frame()
    print(f"    Frame '{popped}' didestruksi. RSP naik kembali.")

    vm_sim.dump_memory_map()
    print(f"{CLR_GREEN}{CLR_BOLD}[LAB SELESAI] Arsitektur Kompilasi, Linking, & Memory Layout Berhasil Dimodelkan.{CLR_RESET}")


if __name__ == "__main__":
    main()