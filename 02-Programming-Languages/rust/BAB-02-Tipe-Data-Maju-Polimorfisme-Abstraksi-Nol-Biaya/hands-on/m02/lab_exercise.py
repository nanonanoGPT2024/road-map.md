#!/usr/bin/env python3
"""
Lab Hands-on: Rust - Tipe Data Maju, Polimorfisme, & Abstraksi Nol-Biaya
Modul: 02 Deep Dive: Sistem Tipe Rust & Performa Runtime

Script ini merekayasa balik (reverse-engineer) dan mensimulasikan mekanisme internal
kompiler rustc:
1. Aljabar Tipe Data: Layout memori Tagged Union (Enums dengan Payload & Niche Optimization).
2. Polimorfisme: Static Dispatch (Monomorphization) vs Dynamic Dispatch (Trait Objects / Fat Pointer & VTable).
3. Abstraksi Nol-Biaya: Perbandingan biaya eksekusi antara functional iterator pipelines
   dan imperative loops.
"""

import sys
import time
import math
from dataclasses import dataclass
from typing import Callable, Any, Dict, List, Tuple

# ANSI Color Codes untuk visualisasi terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"

# ==============================================================================
# BAGIAN 1: SIMULASI MEMORY LAYOUT TAGGED UNION (RUST ENUM DENGAN DATA)
# ==============================================================================
class RustTypeLayout:
    """Menganalisis dan menghitung representasi byte internal Rust Enums."""

    @staticmethod
    def align_to(offset: int, align: int) -> int:
        """Rust Compiler alignment padding rule: (offset + align - 1) & !(align - 1)."""
        return (offset + align - 1) & ~(align - 1)

    @classmethod
    def calculate_enum_layout(cls, variants: Dict[str, List[Tuple[str, int, int]]]) -> Dict[str, Any]:
        """
        Menghitung ukuran memory Rust enum (Tag/Discriminant + Largest Variant + Padding).
        Setiap field adalah tuple: (NamaField, UkuranByte, AligmentByte).
        """
        discriminant_size = 1  # Standard u8 tag untuk varian < 256
        discriminant_align = 1
        
        max_variant_size = 0
        max_align = discriminant_align

        variant_layouts = {}
        for name, fields in variants.items():
            current_offset = 0
            variant_max_align = 1
            for _, f_size, f_align in fields:
                current_offset = cls.align_to(current_offset, f_align)
                current_offset += f_size
                variant_max_align = max(variant_max_align, f_align)
            
            # Align seluruh struct varian
            current_offset = cls.align_to(current_offset, variant_max_align)
            variant_layouts[name] = {
                "payload_size": current_offset,
                "alignment": variant_max_align
            }
            max_variant_size = max(max_variant_size, current_offset)
            max_align = max(max_align, variant_max_align)

        # Total layout: Discriminant + Padding payload + Payload + Padding enum
        payload_offset = cls.align_to(discriminant_size, max_align)
        total_size = cls.align_to(payload_offset + max_variant_size, max_align)

        return {
            "discriminant_bytes": discriminant_size,
            "max_variant_bytes": max_variant_size,
            "overall_alignment": max_align,
            "total_size_bytes": total_size,
            "variants": variant_layouts
        }

# ==============================================================================
# BAGIAN 2: POLIMORFISME - MONOMORPHIZATION VS TRAIT OBJECTS (FAT POINTER)
# ==============================================================================

class VTable:
    """Simulasi struktur VTable internal Rust: drop_in_place, size, align, method pointers."""
    def __init__(self, type_name: str, methods: Dict[str, Callable]):
        self.type_name = type_name
        self.methods = methods
        self.size = 8  # Asumsi 64-bit platform
        self.align = 8

class FatPointer:
    """Simulasi `*mut dyn Trait` (Fat Pointer: Data Pointer + VTable Pointer)."""
    def __init__(self, data_instance: Any, vtable: VTable):
        self.data_ptr = data_instance
        self.vtable_ptr = vtable

    def invoke(self, method_name: str, *args, **kwargs):
        """Dynamic dispatch: dereferencing VTable function pointer pada runtime."""
        fn = self.vtable_ptr.methods.get(method_name)
        if not fn:
            raise AttributeError(f"Method '{method_name}' tidak ditemukan di VTable!")
        return fn(self.data_ptr, *args, **kwargs)

# Implementasi Tipe Konkret
class EngineV8:
    def __init__(self, horse_power: int):
        self.hp = horse_power

    def power_output(self) -> int:
        return self.hp * 10

class MotorElectric:
    def __init__(self, kilowatts: int):
        self.kw = kilowatts

    def power_output(self) -> int:
        return int(self.kw * 13.41)

# VTables terisolasi untuk trait `Drivable`
VTABLE_ENGINE_V8 = VTable("EngineV8", {"power_output": EngineV8.power_output})
VTABLE_MOTOR_ELECTRIC = VTable("MotorElectric", {"power_output": MotorElectric.power_output})

# Static Dispatch (Simulasi rustc specialized generic monomorphization)
def static_drive_v8(engine: EngineV8) -> int:
    return engine.power_output()

def static_drive_electric(motor: MotorElectric) -> int:
    return motor.power_output()

# Dynamic Dispatch (Simulasi rustc Box<dyn Trait> / &dyn Trait call)
def dynamic_drive(fat_ptr: FatPointer) -> int:
    return fat_ptr.invoke("power_output")

# ==============================================================================
# BAGIAN 3: ZERO-COST ABSTRACTION PIPELINE BENCHMARK
# ==============================================================================

class RustZeroCostSimulator:
    """
    Mensimulasikan overhead rustc iterator functional combinator
    vs dynamic trait-object boxed abstraction pipeline.
    """
    @staticmethod
    def imperative_sum(data: List[int]) -> int:
        """Model loop tingkat mesin (asumsi LLVM vectorized ASM)."""
        acc = 0
        for x in data:
            if x % 2 != 0:
                acc += (x * 3) + 7
        return acc

    @staticmethod
    def zero_cost_iterator_simulation(data: List[int]) -> int:
        """
        Model Rust Iterator Chain: data.iter().filter(...).map(...).sum().
        Dalam Rust, LLVM melakukan loop unrolling & auto-vectorization menjadi identik
        dengan imperative loop tanpa alokasi intermediate.
        """
        # Simulasi generator tanpa alokasi memori heap baru
        return sum(((x * 3) + 7) for x in data if x % 2 != 0)

    @staticmethod
    def dynamic_boxing_simulation(data: List[int]) -> int:
        """
        Model runtime dynamic dispatch (seperti Box<dyn Fn(i32) -> bool>).
        Menyebabkan pointer-chasing dan dynamic call overhead.
        """
        class BoxedPred:
            def check(self, val: int) -> bool: return val % 2 != 0
        
        class BoxedTrans:
            def apply(self, val: int) -> int: return (val * 3) + 7

        p = BoxedPred()
        t = BoxedTrans()
        
        acc = 0
        for x in data:
            if p.check(x):
                acc += t.apply(x)
        return acc

# ==============================================================================
# DRIVER & VISUALISASI HASIL LAB
# ==============================================================================

def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}[LAB STEP] {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*70}{CLR_RESET}")

def main():
    print(f"{CLR_BOLD}{CLR_YELLOW}=== SIMULASI DEEP DIVE: SISTEM TIPE & ABSTRAKSI RUST ==={CLR_RESET}")
    
    # -------------------------------------------------------------------------
    # SKENARIO 1: Analisis Layout Memori Rust Enum
    # -------------------------------------------------------------------------
    print_header("1. Layout Memori Rust Tagged Union (Enums Ber-payload)")
    
    # Model Rust Enum:
    # enum NetworkEvent {
    #     Quit,                               // 0 payload
    #     Move { x: i32, y: i32 },            // 8 bytes (i32: 4, align: 4)
    #     Write(String),                      // 24 bytes (ptr: 8, cap: 8, len: 8, align: 8)
    #     SetColor(u8, u8, u8),               // 3 bytes (u8: 1, align: 1)
    # }
    enum_def = {
        "Quit": [],
        "Move": [("x", 4, 4), ("y", 4, 4)],
        "Write": [("ptr", 8, 8), ("cap", 8, 8), ("len", 8, 8)],
        "SetColor": [("r", 1, 1), ("g", 1, 1), ("b", 1, 1)]
    }
    
    layout = RustTypeLayout.calculate_enum_layout(enum_def)
    print(f"Struktur Enum: {CLR_BOLD}NetworkEvent{CLR_RESET}")
    print(f" - Discriminant Tag : {layout['discriminant_bytes']} byte(s)")
    print(f" - Max Alignment    : {layout['overall_alignment']} bytes")
    print(f" - Largest Payload  : {layout['max_variant_bytes']} bytes (Varian: 'Write')")
    print(f" - {CLR_YELLOW}Total Size (RAM) : {layout['total_size_bytes']} bytes{CLR_RESET} (Termasuk alignment padding)")
    print(f"\nRincian Varian:")
    for v_name, v_meta in layout["variants"].items():
        print(f"   * {v_name:<10} => Payload: {v_meta['payload_size']:>2} bytes | Align: {v_meta['alignment']} byte(s)")

    # -------------------------------------------------------------------------
    # SKENARIO 2: Benchmark Static vs Dynamic Dispatch
    # -------------------------------------------------------------------------
    print_header("2. Polimorfisme: Static Dispatch vs Dynamic Fat Pointer VTable")
    
    engine = EngineV8(horse_power=450)
    fat_engine = FatPointer(engine, VTABLE_ENGINE_V8)
    
    iterations = 1_000_000
    print(f"Benchmarking invoke call sebanyak {iterations:,} iterasi...")

    # Benchmark Static Dispatch
    t0 = time.perf_counter()
    res_static = 0
    for _ in range(iterations):
        res_static += static_drive_v8(engine)
    t_static = time.perf_counter() - t0

    # Benchmark Dynamic Dispatch
    t0 = time.perf_counter()
    res_dynamic = 0
    for _ in range(iterations):
        res_dynamic += dynamic_drive(fat_engine)
    t_dynamic = time.perf_counter() - t0

    print(f" - Static Dispatch  : {t_static:.6f} detik | Nilai: {res_static}")
    print(f" - Dynamic Dispatch : {t_dynamic:.6f} detik | Nilai: {res_dynamic}")
    overhead = ((t_dynamic - t_static) / t_static) * 100
    print(f" => {CLR_RED}Dynamic dispatch overhead: +{overhead:.2f}%{CLR_RESET}")
    print(f"    (Dihasilkan oleh indirect VTable pointer lookup dan inhibisi inlining)")

    # -------------------------------------------------------------------------
    # SKENARIO 3: Abstraksi Nol-Biaya vs Dynamic Boxing
    # -------------------------------------------------------------------------
    print_header("3. Validasi 'Zero-Cost Abstractions' Iterator")
    
    data_sample = list(range(200_000))
    print(f"Memproses {len(data_sample):,} elemen integer...")

    t0 = time.perf_counter()
    ans_imp = RustZeroCostSimulator.imperative_sum(data_sample)
    t_imp = time.perf_counter() - t0

    t0 = time.perf_counter()
    ans_iter = RustZeroCostSimulator.zero_cost_iterator_simulation(data_sample)
    t_iter = time.perf_counter() - t0

    t0 = time.perf_counter()
    ans_dyn = RustZeroCostSimulator.dynamic_boxing_simulation(data_sample)
    t_dyn = time.perf_counter() - t0

    assert ans_imp == ans_iter == ans_dyn, "Perhitungan matematis tidak konsisten!"

    print(f" [1] Hand-Rolled Loop     : {t_imp:.6f} detik (Baseline Machine Loop)")
    print(f" [2] Generator Pipeline   : {t_iter:.6f} detik (Rust Iterator Analogue)")
    print(f" [3] Dynamic Boxed Calls  : {t_dyn:.6f} detik (Object Indirect Calls)")
    
    perf_penalty = (t_dyn / t_iter)
    print(f"\n{CLR_BOLD}{CLR_GREEN}[KESIMPULAN LAB]{CLR_RESET}")
    print(f"Abstraksi fungsional tanpa alokasi per-elemen mendekati performa baseline imperatif.")
    print(f"Metode ter-abstraksi dynamic/boxed lebih lambat {CLR_RED}{perf_penalty:.2f}x{CLR_RESET} dibanding pipeline.")
    print(f"{CLR_BLUE}Kompiler rustc melangkah lebih jauh: menghapus generator state machine sepenuhnya")
    print(f"dan memancarkan Vectorized Assembly register langsung (Zero-Cost Abstraction sejati).{CLR_RESET}")

if __name__ == "__main__":
    main()