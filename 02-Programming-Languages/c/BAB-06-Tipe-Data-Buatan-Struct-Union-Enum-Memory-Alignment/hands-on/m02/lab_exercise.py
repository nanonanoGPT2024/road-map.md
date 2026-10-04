#!/usr/bin/env python3
"""
Lab Hands-on: C Memory Layout Engine (Struct, Union, Enum, & Alignment)
Modul: 02 - Deep Dive Tipe Data Buatan & Alignment Memory Architecture.

Script ini mensimulasikan dan menganalisis mekanisme internal C runtime:
1. Perhitungan Padding & Memory Alignment (Natural Alignment vs Packed).
2. Optimasi Layout Struct (Menghemat cache line & footprint RAM).
3. Type Punning & Memory Overlapping via C-Union (IEEE-754 Float Inspection).
4. Enum & Bitmask Memory Footprint.
5. Visualizer Hex Dump memori biner C runtime secara real-time.
"""

import ctypes
import sys

# ANSI Colors untuk representasi CLI interaktif
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_BG_PAD  = "\033[41m\033[37m" # Red background for padding bytes
CLR_BG_DATA = "\033[42m\033[30m" # Green background for valid data bytes


# ============================================================================
# 1. STRUCT DEFINITIONS & ALIGNMENT ANOMALIES
# ============================================================================

class BadStruct(ctypes.Structure):
    """
    Representasi struct C tanpa optimasi layout:
    struct BadStruct {
        char   a;      // 1 byte
        // padding 3 bytes
        int    b;      // 4 bytes
        char   c;      // 1 byte
        // padding 7 bytes
        double d;      // 8 bytes
    };
    """
    _fields_ = [
        ("a", ctypes.c_char),
        ("b", ctypes.c_int32),
        ("c", ctypes.c_char),
        ("d", ctypes.c_double),
    ]


class OptimizedStruct(ctypes.Structure):
    """
    Representasi struct C setelah re-ordering field berbobot terbesar dahulu:
    struct OptimizedStruct {
        double d;      // 8 bytes
        int    b;      // 4 bytes
        char   a;      // 1 byte
        char   c;      // 1 byte
        // padding 2 bytes untuk memenuhi kelipatan 8 bytes (alignment double)
    };
    """
    _fields_ = [
        ("d", ctypes.c_double),
        ("b", ctypes.c_int32),
        ("a", ctypes.c_char),
        ("c", ctypes.c_char),
    ]


class PackedStruct(ctypes.Structure):
    """
    Representasi struct C dengan direktif compiler:
    #pragma pack(push, 1) atau __attribute__((packed))
    Zero padding, mengorbankan siklus fetch CPU (unaligned memory access).
    """
    _pack_ = 1
    _fields_ = [
        ("a", ctypes.c_char),
        ("b", ctypes.c_int32),
        ("c", ctypes.c_char),
        ("d", ctypes.c_double),
    ]


# ============================================================================
# 2. UNION & TYPE PUNNING (Low-level Float Inspection)
# ============================================================================

class FloatIntUnion(ctypes.Union):
    """
    Representasi C-Union untuk membaca representasi bit raw IEEE-754:
    union FloatIntUnion {
        float f;
        uint32_t u;
        uint8_t bytes[4];
    };
    Semua member berbagi alamat basis (offset 0) yang sama di RAM.
    """
    _fields_ = [
        ("f", ctypes.c_float),
        ("u", ctypes.c_uint32),
        ("bytes", ctypes.c_uint8 * 4),
    ]


# ============================================================================
# 3. ENUM / BITMASK SIMULATION
# ============================================================================

class PosixPermissions:
    """Simulasi enum C POSIX file permissions berbasis bitmask."""
    PROT_NONE  = 0x0
    PROT_READ  = 0x1  # 001
    PROT_WRITE = 0x2  # 010
    PROT_EXEC  = 0x4  # 100


# ============================================================================
# 4. UTILITY FUNCTIONS (Analysis & Hex Dump Engine)
# ============================================================================

def analyze_struct_layout(struct_cls, title):
    """
    Menganalisis offset setiap field, padding tersembunyi (holes),
    dan total footprint memory struct.
    """
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== Layout Analisis: {title} ==={CLR_RESET}")
    total_size = ctypes.sizeof(struct_cls)
    align_req = ctypes.alignment(struct_cls)
    print(f"Total Size: {CLR_YELLOW}{total_size} bytes{CLR_RESET} | Alignment Boundary: {CLR_YELLOW}{align_req} bytes{CLR_RESET}")
    print(f"{'Field':<10} {'Type':<15} {'Offset':<8} {'Size':<6} {'Padding Before':<15}")
    print("-" * 60)

    last_offset_end = 0
    total_padding = 0

    for name, c_type in struct_cls._fields_:
        field_attr = getattr(struct_cls, name)
        offset = field_attr.offset
        size = field_attr.size
        padding_before = offset - last_offset_end

        if padding_before > 0:
            print(f"{CLR_RED}{'[PAD]':<10} {'padding hole':<15} {last_offset_end:<8} {padding_before:<6} {'(CPU Aligner)':<15}{CLR_RESET}")
            total_padding += padding_before

        print(f"{CLR_GREEN}{name:<10}{CLR_RESET} {c_type.__name__:<15} {offset:<8} {size:<6} {0:<15}")
        last_offset_end = offset + size

    tail_padding = total_size - last_offset_end
    if tail_padding > 0:
        print(f"{CLR_RED}{'[TAIL PAD]':<10} {'tail padding':<15} {last_offset_end:<8} {tail_padding:<6} {'(Tail Boundary)':<15}{CLR_RESET}")
        total_padding += tail_padding

    waste_pct = (total_padding / total_size) * 100
    print(f"Memory Waste (Padding Overhead): {CLR_MAGENTA}{waste_pct:.2f}% ({total_padding} bytes){CLR_RESET}\n")


def hex_dump_memory(raw_bytes, label):
    """Mencetak representasi heksadesimal byte-level raw memory."""
    print(f"{CLR_BOLD}Memory Byte Map [{label}]:{CLR_RESET}")
    hex_str = " ".join(f"{b:02X}" for b in raw_bytes)
    ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in raw_bytes)
    print(f"  Offset HEX : {CLR_BLUE}{hex_str}{CLR_RESET}")
    print(f"  ASCII Map  : {ascii_str}")


# ============================================================================
# 5. LAB DEMONSTRATION WORKFLOW
# ============================================================================

def run_alignment_lab():
    # 1. Struct Alignment & Padding Comparison
    analyze_struct_layout(BadStruct, "BadStruct (Unordered)")
    analyze_struct_layout(OptimizedStruct, "OptimizedStruct (Ordered by size)")
    analyze_struct_layout(PackedStruct, "PackedStruct (#pragma pack(1))")

    # Inisialisasi nilai instance
    bad_inst = BadStruct(a=b'A', b=0x12345678, c=b'Z', d=12345.6789)
    raw_bad = bytes(bad_inst)
    hex_dump_memory(raw_bad, "BadStruct Instance Byte Dump")

    # 2. C-Union Demonstration: IEEE-754 Float Bit Breakdown
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== C-Union: Memory Overlapping & Type Punning ==={CLR_RESET}")
    u = FloatIntUnion()
    u.f = -13.625  # Nilai floating point tertentu

    print(f"Assign Float Value : {CLR_YELLOW}{u.f}{CLR_RESET}")
    print(f"Shared Memory Size : {ctypes.sizeof(FloatIntUnion)} bytes (Maksimum size member)")
    print(f"Interpretasi Integer Raw Hex : {CLR_GREEN}0x{u.u:08X}{CLR_RESET}")
    print(f"Interpretasi Binary Bits     : {CLR_MAGENTA}{u.u:032b}{CLR_RESET}")

    # IEEE-754 single precision breakdown: 1 bit sign, 8 bit exponent, 23 bit mantissa
    sign = (u.u >> 31) & 0x1
    exp = (u.u >> 23) & 0xFF
    mantissa = u.u & 0x7FFFFF

    print(f"  ├─ Sign Bit (1 bit)       : {sign} ({'Negatif' if sign else 'Positif'})")
    print(f"  ├─ Biased Exponent (8 bit): {exp} (Actual: {exp - 127})")
    print(f"  └─ Mantissa Bits (23 bit) : 0x{mantissa:06X}")

    raw_union = bytes(u)
    hex_dump_memory(raw_union, "FloatIntUnion Instance Raw Buffer")

    # 3. Enum & Bitmask Execution
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== Enum & Bitmask Hardware Flags ==={CLR_RESET}")
    user_perms = PosixPermissions.PROT_READ | PosixPermissions.PROT_EXEC
    print(f"Permission Bitmask : {CLR_YELLOW}0x{user_perms:02X} (Binary: {user_perms:04b}){CLR_RESET}")
    print(f"  ├─ PROT_READ  Active? : {'YES' if user_perms & PosixPermissions.PROT_READ else 'NO'}")
    print(f"  ├─ PROT_WRITE Active? : {'YES' if user_perms & PosixPermissions.PROT_WRITE else 'NO'}")
    print(f"  └─ PROT_EXEC  Active? : {'YES' if user_perms & PosixPermissions.PROT_EXEC else 'NO'}")


if __name__ == "__main__":
    print(f"{CLR_BOLD}{CLR_GREEN}Mengeksekusi Lab: C Struct, Union, & Memory Alignment Deep Dive{CLR_RESET}")
    print(f"Target CPU Architecture: {sys.byteorder.upper()}-ENDIAN Platform\n")
    run_alignment_lab()
    print(f"\n{CLR_BOLD}{CLR_GREEN}Lab selesai dieksekusi dengan sukses.{CLR_RESET}")