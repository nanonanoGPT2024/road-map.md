#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Tipe Data Maju, Polimorfisme & Abstraksi Nol-Biaya (Rust)
BAB-02: Tipe Data Maju, Polimorfisme, dan Abstraksi Nol-Biaya

Modul ini mendemonstrasikan secara visual dan komparatif:
1. Tagged Union (Rust Enum dengan Data) & Memory Layout (Discriminant + Payload)
2. Static Dispatch (Monomorphization & Zero-Cost Abstraction)
3. Dynamic Dispatch (`dyn Trait`, Fat Pointer: Data Pointer + VTable Pointer)
4. Perbandingan Latensi & Profiling Eksekusi
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# ANSI Escape Sequences untuk Terminal Formatting
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_GRAY = "\033[100m"


def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN}>>> {title.center(67)} <<<{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}")


def print_section(name: str) -> None:
    print(f"\n{BOLD}{YELLOW}--- [ {name} ] ---{RESET}")


# ============================================================================
# 1. TAGGED UNION & MEMORY LAYOUT SIMULATION (Rust Enums)
# ============================================================================
class RustEnumVariant:
    """Simulasi varian Enum Rust dengan Tag/Discriminant dan Payload."""
    def __init__(self, discriminant: int, name: str, payload_size_bytes: int, payload_desc: str):
        self.discriminant = discriminant
        self.name = name
        self.payload_size = payload_size_bytes
        self.payload_desc = payload_desc

    def render_memory_layout(self, max_payload_size: int) -> str:
        tag_str = f"{BLUE}[ Tag/Disc: 0x{self.discriminant:02X} (1 Byte) ]{RESET}"
        payload_str = f"{GREEN}[ Payload: {self.payload_desc} ({self.payload_size} Bytes) ]{RESET}"
        padding = max_payload_size - self.payload_size
        padding_str = f"{BG_GRAY}[ Padding: {padding} Bytes ]{RESET}" if padding > 0 else ""
        return f"{tag_str} -> {payload_str} {padding_str}"


def demo_tagged_unions() -> None:
    print_section("Simulasi Tagged Union / Rust Enum Memory Layout")
    print("Rust `enum` bukan sekadar integer konvensional C, melainkan *Tagged Union*:")
    print("Total Size = Size(Discriminant) + Max(Size(Variants)) + Memory Alignment Padding.\n")

    variants = [
        RustEnumVariant(0, "Quit", 0, "() Empty unit tuple"),
        RustEnumVariant(1, "Move", 8, "{ x: i32, y: i32 }"),
        RustEnumVariant(2, "Write", 24, "String (ptr: 8, cap: 8, len: 8)"),
        RustEnumVariant(3, "ChangeColor", 3, "(u8, u8, u8) RGB"),
    ]

    max_payload = max(v.payload_size for v in variants)
    total_size = 1 + max_payload + (8 - ((1 + max_payload) % 8) if (1 + max_payload) % 8 != 0 else 0)

    print(f"Kalkulasi Layout Memori Struct Enum (Alignment 8 bytes):")
    print(f"  * Discriminant : 1 Byte (u8)")
    print(f"  * Max Payload  : {max_payload} Bytes (dari varian Write)")
    print(f"  * Total Size   : {total_size} Bytes (termasuk alignment)\n")

    for v in variants:
        print(f"Varian {BOLD}{v.name:<12}{RESET}: {v.render_memory_layout(max_payload)}")


# ============================================================================
# 2. STATIC DISPATCH (Monomorphization / Zero-Cost Abstraction)
# ============================================================================
class Circle:
    def __init__(self, radius: float):
        self.radius = radius

    def area(self) -> float:
        return 3.1415926535 * self.radius * self.radius


class Rectangle:
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def area(self) -> float:
        return self.width * self.height


# Simulasi Compiler Monomorphization (Generics menghasilkan dedicated function)
def print_area_circle_specialized(shape: Circle) -> float:
    """Specialized code hasil monomorphization: `print_area::<Circle>(c)`."""
    return shape.area()


def print_area_rectangle_specialized(shape: Rectangle) -> float:
    """Specialized code hasil monomorphization: `print_area::<Rectangle>(r)`."""
    return shape.area()


def demo_static_dispatch() -> None:
    print_section("Static Dispatch (Trait Bounds & Monomorphization)")
    print("Dalam Rust, generic function `fn print_area<T: Shape>(shape: T)` di-monomorphize")
    print("oleh kompilator menjadi salinan fungsi unik untuk masing-masing tipe konkret.")
    print(f"{GREEN}Keuntungan: Nol overhead vtable runtime, direct call, inline-friendly.{RESET}\n")

    circle = Circle(5.0)
    rect = Rectangle(4.0, 6.0)

    print(f"{BOLD}[Kompilasi Rust Generics]{RESET}")
    print(f"  `print_area::<Circle>`    -> Di-inline langsung ke direct CALL area: {print_area_circle_specialized(circle):.2f}")
    print(f"  `print_area::<Rectangle>` -> Di-inline langsung ke direct CALL area: {print_area_rectangle_specialized(rect):.2f}")


# ============================================================================
# 3. DYNAMIC DISPATCH (Trait Object & VTable / Fat Pointer)
# ============================================================================
class VTable:
    """Simulasi Virtual Method Table (VTable) milik Trait."""
    def __init__(self, trait_name: str, methods: Dict[str, Callable[[Any], Any]]):
        self.trait_name = trait_name
        self.methods = methods


class FatPointer:
    """Simulasi Fat Pointer `&dyn Trait` berukuran 16 byte (2 x 64-bit pointers)."""
    def __init__(self, data_ptr: Any, vtable_ptr: VTable):
        self.data_ptr = data_ptr        # Pointer 1: Alamat objek konkret di memory
        self.vtable_ptr = vtable_ptr    # Pointer 2: Alamat VTable berisi fungsi trait

    def invoke(self, method_name: str) -> Any:
        # Simulasi indirect call via vtable pointer dereferencing
        method = self.vtable_ptr.methods.get(method_name)
        if not method:
            raise AttributeError(f"Method {method_name} tidak ditemukan di VTable")
        return method(self.data_ptr)


def demo_dynamic_dispatch() -> None:
    print_section("Dynamic Dispatch (`&dyn Trait` / Fat Pointer)")
    print("Jika koleksi heterogeneous diperlukan (`Vec<Box<dyn Shape>>`), Rust memakai Fat Pointer:")
    print(f"  1. {MAGENTA}Data Pointer (8 Bytes){RESET}   -> Alamat instans konkret di heap/stack.")
    print(f"  2. {MAGENTA}VTable Pointer (8 Bytes){RESET} -> Alamat tabel pointer fungsi runtime.\n")

    # Inisialisasi VTable terpisah
    circle_vtable = VTable("Shape", {"area": lambda obj: obj.area()})
    rect_vtable = VTable("Shape", {"area": lambda obj: obj.area()})

    shapes: List[Tuple[str, FatPointer]] = [
        ("Circle FatPtr", FatPointer(Circle(3.0), circle_vtable)),
        ("Rect FatPtr", FatPointer(Rectangle(2.0, 5.0), rect_vtable)),
    ]

    for label, fat_ptr in shapes:
        result = fat_ptr.invoke("area")
        print(f"{BOLD}{label:<15}{RESET} -> [Data: 0x{id(fat_ptr.data_ptr):X} | VTable: 0x{id(fat_ptr.vtable_ptr):X}] -> Area: {result:.2f}")


# ============================================================================
# 4. BENCHMARK SIMULASI OVERHEAD PANGGILAN
# ============================================================================
def demo_benchmark() -> None:
    print_section("Simulasi Komparasi Kinerja: Static vs Dynamic Dispatch")
    iterations = 2_000_000
    circle = Circle(2.5)
    vtable = VTable("Shape", {"area": lambda obj: obj.area()})
    fat_ptr = FatPointer(circle, vtable)

    print(f"Menjalankan simulasi loop {iterations:,} iterasi...")

    # Benchmark Static Dispatch (Direct Call)
    start_time = time.perf_counter()
    sum_static = 0.0
    for _ in range(iterations):
        sum_static += circle.area()
    dur_static = time.perf_counter() - start_time

    # Benchmark Dynamic Dispatch (Indirect Call)
    start_time = time.perf_counter()
    sum_dyn = 0.0
    for _ in range(iterations):
        sum_dyn += fat_ptr.invoke("area")
    dur_dyn = time.perf_counter() - start_time

    print(f"\n{BOLD}Hasil Profiling Sederhana:{RESET}")
    print(f"  * Static Dispatch  (Direct)   : {dur_static:.4f} detik (1.00x - Baseline)")
    ratio = dur_dyn / dur_static if dur_static > 0 else 1.0
    print(f"  * Dynamic Dispatch (Indirect) : {dur_dyn:.4f} detik ({ratio:.2f}x Overhead)")
    print(f"{YELLOW}Catatan: Pada Rust kode mesin native, static dispatch dapat di-inlining penuh{RESET}")
    print(f"{YELLOW}menjadi register arithmetic (0 ns runtime dispatch cost).{RESET}")


# ============================================================================
# 5. INTERACTIVE CLI RUNNER
# ============================================================================
def main() -> None:
    print_header("RUST BAB-02: TIPE DATA MAJU & ZERO-COST ABSTRACTION")
    print(f"{GREEN}Lab interaktif siap menjalankan modul eksplorasi konsep.{RESET}")

    demos = [
        ("1", "Simulasi Memory Layout Tagged Union (Rust Enum)", demo_tagged_unions),
        ("2", "Simulasi Static Dispatch & Monomorphization", demo_static_dispatch),
        ("3", "Simulasi Dynamic Dispatch & Fat Pointer (dyn Trait)", demo_dynamic_dispatch),
        ("4", "Benchmarking Overhead Pemanggilan Metode", demo_benchmark),
    ]

    # Jalankan seluruh modul secara sekuensial jika flag --all atau interaktif
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        while True:
            print("\nPilihan Demonstrasi:")
            for key, desc, _ in demos:
                print(f"  [{BOLD}{key}{RESET}] {desc}")
            print(f"  [{BOLD}A{RESET}] Jalankan Semua")
            print(f"  [{BOLD}Q{RESET}] Keluar")

            choice = input(f"\n{BOLD}Pilih opsi (1-4/A/Q): {RESET}").strip().upper()
            if choice == "Q":
                print(f"{GREEN}Selesai. Selamat belajar Rust!{RESET}")
                break
            elif choice == "A":
                for _, _, fn in demos:
                    fn()
            else:
                matched = False
                for key, _, fn in demos:
                    if choice == key:
                        fn()
                        matched = True
                        break
                if not matched:
                    print(f"{RED}Pilihan tidak valid.{RESET}")
    else:
        # Default: Eksekusi komprehensif semua demo
        for _, _, fn in demos:
            fn()
        print(f"\n{BOLD}{GREEN}Semua modul demonstrasi berhasil dieksekusi dengan sukses!{RESET}\n")


if __name__ == "__main__":
    main()
