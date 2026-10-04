#!/usr/bin/env python3
"""
Lab Hands-on: Rust Deep Dive
Bab 08: Unsafe Rust & Foreign Function Interface (FFI)

Simulasi runtime memori tingkat rendah untuk mengeksplorasi konsep inti Unsafe Rust:
1. Raw Pointers (*const T, *mut T) dan validasi Undefined Behavior (UB).
2. Kalkulator Layout Memori Rust `#[repr(C)]` (Alignment, Size, Padding).
3. Marshalling FFI C-String, lifecycle boundary (`into_raw` vs `from_raw`), 
   dan pencegahan Use-After-Free / Double-Free.
"""

import sys
import ctypes
import struct
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# ANSI Color Codes untuk visualisasi terminal
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_CYAN   = "\033[36m"
CLR_MAG    = "\033[35m"


@dataclass
class AllocationMetadata:
    address: int
    size: int
    align: int
    is_freed: bool
    type_name: str


class UnsafeMemoryTracker:
    """
    Mensimulasikan AddressSanitizer/Miri sederhana untuk mendeteksi
    Undefined Behavior (UB) pada manipulasi raw pointer Rust.
    """
    def __init__(self):
        self._allocations: Dict[int, AllocationMetadata] = {}

    def allocate(self, size: int, align: int, type_name: str) -> int:
        # Mengalokasikan memory mentah menggunakan ctypes
        buf = (ctypes.c_uint8 * (size + align))()
        raw_addr = ctypes.addressof(buf)
        # Menghitung aligned address: (addr + align - 1) & ~(align - 1)
        aligned_addr = (raw_addr + align - 1) & ~(align - 1)
        
        # Simpan buffer ref agar tidak di-garbage collect oleh Python
        setattr(self, f"_buf_{aligned_addr}", buf)
        
        self._allocations[aligned_addr] = AllocationMetadata(
            address=aligned_addr,
            size=size,
            align=align,
            is_freed=False,
            type_name=type_name
        )
        return aligned_addr

    def write_u32(self, raw_ptr: int, value: int):
        self._validate_access(raw_ptr, size=4, required_align=4)
        ctypes.c_uint32.from_address(raw_ptr).value = value

    def read_u32(self, raw_ptr: int) -> int:
        self._validate_access(raw_ptr, size=4, required_align=4)
        return ctypes.c_uint32.from_address(raw_ptr).value

    def deallocate(self, raw_ptr: int):
        if raw_ptr not in self._allocations:
            raise RuntimeError(f"{CLR_RED}[UB: Bad Free] Alamat 0x{raw_ptr:08X} bukan heap pointer yang valid!{CLR_RESET}")
        
        meta = self._allocations[raw_ptr]
        if meta.is_freed:
            raise RuntimeError(f"{CLR_RED}[UB: Double Free] Alamat 0x{raw_ptr:08X} ({meta.type_name}) sudah pernah di-dealokasi!{CLR_RESET}")
        
        meta.is_freed = True

    def _validate_access(self, raw_ptr: int, size: int, required_align: int):
        # 1. Null pointer dereference
        if raw_ptr == 0:
            raise RuntimeError(f"{CLR_RED}[UB: Null Pointer Dereference] Mencoba dereference raw pointer 0x0!{CLR_RESET}")

        # 2. Misaligned access check
        if raw_ptr % required_align != 0:
            raise RuntimeError(f"{CLR_RED}[UB: Misaligned Read/Write] Pointer 0x{raw_ptr:08X} tidak ter-align pada {required_align}-byte boundary!{CLR_RESET}")

        # 3. Use-after-free check
        if raw_ptr in self._allocations:
            meta = self._allocations[raw_ptr]
            if meta.is_freed:
                raise RuntimeError(f"{CLR_RED}[UB: Use-After-Free] Mencoba mengakses alamat 0x{raw_ptr:08X} yang sudah di-drop/free!{CLR_RESET}")


class ReprCLayoutEngine:
    """
    Menghitung field offsets, padding, total size, dan struct alignment
    sesuai standar C-ABI standard (System V AMD64 ABI) yang diemulasikan oleh Rust `#[repr(C)]`.
    """
    RUST_PRIMITIVES: Dict[str, Tuple[int, int, str]] = {
        # type_name: (size, alignment, struct_format_char)
        "bool": (1, 1, "?"),
        "u8":   (1, 1, "B"),
        "i8":   (1, 1, "b"),
        "u16":  (2, 2, "H"),
        "i16":  (2, 2, "h"),
        "u32":  (4, 4, "I"),
        "i32":  (4, 4, "i"),
        "u64":  (8, 8, "Q"),
        "i64":  (8, 8, "q"),
        "usize":(8, 8, "Q"), # simulasi 64-bit target
        "*const c_char": (8, 8, "Q"),
    }

    @classmethod
    def calculate_layout(cls, fields: List[Tuple[str, str]]) -> Dict:
        """
        Menghitung memori layout untuk field: [(nama_field, tipe_rust), ...]
        """
        current_offset = 0
        struct_alignment = 1
        field_offsets = []

        for name, rust_type in fields:
            if rust_type not in cls.RUST_PRIMITIVES:
                raise ValueError(f"Tipe tidak dikenali: {rust_type}")
            
            size, align, _ = cls.RUST_PRIMITIVES[rust_type]
            struct_alignment = max(struct_alignment, align)

            # Hitung padding yang dibutuhkan untuk align field saat ini
            padding = (align - (current_offset % align)) % align
            current_offset += padding
            field_offsets.append((name, rust_type, current_offset, size, padding))
            current_offset += size

        # Padding akhir agar ukuran total struct habis dibagi struct_alignment
        tail_padding = (struct_alignment - (current_offset % struct_alignment)) % struct_alignment
        total_size = current_offset + tail_padding

        return {
            "fields": field_offsets,
            "struct_alignment": struct_alignment,
            "total_size": total_size,
            "tail_padding": tail_padding
        }


class FFICStringSimulator:
    """
    Mensimulasikan lifecycle std::ffi::CString dan transmisi raw pointer `*const c_char`
    menyeberang FFI boundaries.
    """
    def __init__(self, text: str):
        self.raw_bytes = text.encode('utf-8') + b'\x00' # Tambah null terminator
        self.length = len(self.raw_bytes)
        self.buffer = (ctypes.c_char * self.length)(*self.raw_bytes)
        self.ptr = ctypes.addressof(self.buffer)
        self.is_owned = True

    def into_raw(self) -> int:
        """
        Rust: `CString::into_raw(self) -> *mut c_char`
        Melepas kepemilikan Rust; pointer tidak akan di-drop otomatis oleh scope.
        """
        self.is_owned = False
        return self.ptr

    @classmethod
    def from_raw(cls, ptr: int, original_instance: 'FFICStringSimulator') -> 'FFICStringSimulator':
        """
        Rust: `unsafe { CString::from_raw(ptr) }`
        Mengambil alih kembali kepemilikan pointer dari C library untuk dibersihkan.
        """
        if original_instance.ptr != ptr:
            raise ValueError(f"Pointer tidak cocok: 0x{ptr:08X}")
        original_instance.is_owned = True
        return original_instance


# -------------------------------------------------------------------------
# Simulasi Foreign Function (C runtime mock)
# -------------------------------------------------------------------------
def foreign_c_strlen(c_str_ptr: int) -> int:
    """
    Simulasi fungsi C: size_t strlen(const char *s);
    Membaca memori byte per byte hingga menemukan byte 0x00 (Null Terminator).
    """
    count = 0
    while True:
        byte = ctypes.c_uint8.from_address(c_str_ptr + count).value
        if byte == 0:
            break
        count += 1
    return count


def print_banner(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_YELLOW}>>> {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 75}{CLR_RESET}")


def run_lab():
    tracker = UnsafeMemoryTracker()

    # =========================================================================
    # Modul 1: Raw Pointer & Unsafe Dereferencing Simulation
    # =========================================================================
    print_banner("1. Unsafe Rust: Raw Pointer Dereference & UB Detection")
    print(f"{CLR_BLUE}[Info]{CLR_RESET} Mengalokasikan heap buffer untuk tipe `u32` (Size=4, Align=4)...")
    
    ptr_val = tracker.allocate(size=4, align=4, type_name="u32")
    print(f"{CLR_GREEN}[Alloc]{CLR_RESET} Raw pointer dialokasikan pada: {CLR_BOLD}0x{ptr_val:08X}{CLR_RESET}")

    print(f"{CLR_BLUE}[Action]{CLR_RESET} Menulis data integer 42 ke raw pointer via unsafe write...")
    tracker.write_u32(ptr_val, 42)
    read_val = tracker.read_u32(ptr_val)
    print(f"{CLR_GREEN}[Dereference]{CLR_RESET} Nilai terbaca dari unsafe block: {CLR_BOLD}{read_val}{CLR_RESET}")

    print(f"{CLR_BLUE}[Action]{CLR_RESET} Menjalankan manual deallocate (`std::alloc::dealloc` / `Drop`)...")
    tracker.deallocate(ptr_val)
    print(f"{CLR_GREEN}[Dealloc]{CLR_RESET} Memori 0x{ptr_val:08X} ditandai sebagai freed.")

    # Simulasi Use-After-Free
    print(f"\n{CLR_YELLOW}[Simulasi UB 1: Use-After-Free]{CLR_RESET}")
    try:
        print(f"Mencoba membaca dari 0x{ptr_val:08X} setelah di-free...")
        tracker.read_u32(ptr_val)
    except RuntimeError as err:
        print(f"{CLR_BOLD}Tangki Deteksi UB:{CLR_RESET} {err}")

    # Simulasi Double Free
    print(f"\n{CLR_YELLOW}[Simulasi UB 2: Double Free]{CLR_RESET}")
    try:
        print(f"Mencoba men-dealokasi ulang 0x{ptr_val:08X}...")
        tracker.deallocate(ptr_val)
    except RuntimeError as err:
        print(f"{CLR_BOLD}Tangki Deteksi UB:{CLR_RESET} {err}")

    # Simulasi Misaligned Pointer Access
    print(f"\n{CLR_YELLOW}[Simulasi UB 3: Misaligned Pointer Dereference]{CLR_RESET}")
    misaligned_ptr = ptr_val + 1  # Offset ganjil untuk u32 (memerlukan kelipatan 4)
    try:
        print(f"Mencoba dereference pointer ganjil 0x{misaligned_ptr:08X} untuk 32-bit read...")
        tracker.read_u32(misaligned_ptr)
    except RuntimeError as err:
        print(f"{CLR_BOLD}Tangki Deteksi UB:{CLR_RESET} {err}")

    # =========================================================================
    # Modul 2: Rust #[repr(C)] Struct Memory Layout
    # =========================================================================
    print_banner("2. Memory Layout: Rust #[repr(C)] ABI Padding & Alignment")
    
    struct_def = [
        ("id", "u8"),             # 1 byte, align 1
        ("flags", "u32"),         # 4 byte, align 4 -> butuh 3 byte padding sebelumnya
        ("is_active", "bool"),    # 1 byte, align 1
        ("payload_ptr", "*const c_char") # 8 byte, align 8 -> butuh 7 byte padding sebelumnya
    ]

    print(f"{CLR_BLUE}[Definisi Struct]{CLR_RESET}")
    print("  #[repr(C)]")
    print("  struct SensorPacket {")
    for fname, ftype in struct_def:
        print(f"      {fname}: {ftype},")
    print("  }\n")

    layout = ReprCLayoutEngine.calculate_layout(struct_def)
    
    print(f"{CLR_BOLD}{'FIELD':<15} | {'TIPE':<15} | {'OFFSET':<8} | {'SIZE':<6} | {'PADDING SEBELUM':<15}{CLR_RESET}")
    print("-" * 75)
    for name, rust_type, offset, size, pad in layout["fields"]:
        pad_str = f"+{pad} bytes" if pad > 0 else "0 bytes"
        print(f"{name:<15} | {rust_type:<15} | 0x{offset:04X}   | {size}B    | {pad_str:<15}")

    print("-" * 75)
    print(f"Total Structural Alignment : {layout['struct_alignment']} bytes")
    print(f"Tail Padding               : {layout['tail_padding']} bytes")
    print(f"{CLR_BOLD}Total Struct Memory Size   : {layout['total_size']} bytes{CLR_RESET}")

    # =========================================================================
    # Modul 3: FFI CString Ownership & Cross-Boundary Call
    # =========================================================================
    print_banner("3. FFI Boundaries: CString Marshalling & Ownership Transfer")
    
    rust_text = "Rust FFI Pipeline"
    print(f"{CLR_BLUE}[Rust Space]{CLR_RESET} Menginisialisasi CString: \"{rust_text}\"")
    cstring = FFICStringSimulator(rust_text)
    
    # 1. Rust menyerahkan pointer ke C
    c_ptr = cstring.into_raw()
    print(f"{CLR_YELLOW}[Transisi]{CLR_RESET} CString::into_raw() -> Raw Pointer: {CLR_BOLD}0x{c_ptr:08X}{CLR_RESET}")
    print(f"             Status Rust Owner: {cstring.is_owned} (Mencegah deallocation di Rust scope)")

    # 2. Foreign C Function beroperasi pada raw pointer
    print(f"{CLR_BLUE}[Foreign C Space]{CLR_RESET} Memanggil `extern \"C\" fn foreign_c_strlen(ptr)`...")
    calculated_len = foreign_c_strlen(c_ptr)
    print(f"{CLR_GREEN}[C Result]{CLR_RESET} Ukuran string dihitung oleh runtime C: {CLR_BOLD}{calculated_len}{CLR_RESET} bytes")

    # 3. Rust mengambil kembali ownership pointer untuk membersihkannya
    print(f"{CLR_YELLOW}[Transisi]{CLR_RESET} unsafe {{ CString::from_raw(ptr) }} -> Merebut kembali hak kepemilikan...")
    reclaimed = FFICStringSimulator.from_raw(c_ptr, cstring)
    print(f"             Status Rust Owner: {reclaimed.is_owned}")
    print(f"{CLR_GREEN}[Drop Check]{CLR_RESET} String aman di-drop oleh Rust allocator tanpa leak!")


if __name__ == "__main__":
    run_lab()
    print(f"\n{CLR_GREEN}{CLR_BOLD}=== Lab Hands-on Unsafe Rust & FFI Berhasil Selesai ==={CLR_RESET}\n")
    sys.exit(0)