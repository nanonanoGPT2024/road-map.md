#!/usr/bin/env python3
"""
Lab Hands-on: Sistem Interoperabilitas & C-Extensions Deep Dive
Bab 08 - Modul 02: Foreign Function Interface (FFI), Memory Alignment, & C-ABI Callbacks

Skrip mandiri ini membedah interoperabilitas biner tingkat rendah menggunakan ctypes:
1. Inspeksi Memori & Struct Alignment C-ABI (Padding, Offsets, Unpacking).
2. Pointer Manipulation & Direct Memory Mutation via Buffer Protocol.
3. C-Function Callbacks: Mengoper fungsi Python ke C Runtime (qsort).
4. Profiling Komparasi Overhead: Python Object Creation vs In-Place C Memory.
"""

import sys
import os
import time
import struct
import platform
import ctypes
from ctypes import (
    Structure, Union, POINTER, CFUNCTYPE,
    c_uint8, c_uint16, c_uint32, c_int, c_char, c_void_p, c_size_t,
    cast, byref, sizeof, addressof
)
import ctypes.util

# ============================================================================
# ANSI Formatting Constants
# ============================================================================
CLR_RST = "\033[0m"
CLR_BLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GRN = "\033[32m"
CLR_YLW = "\033[33m"
CLR_BLU = "\033[34m"
CLR_CYN = "\033[36m"
CLR_WHT = "\033[37m"

def print_banner(title: str):
    print(f"\n{CLR_CYN}{'=' * 78}{CLR_RST}")
    print(f"{CLR_BLD}{CLR_WHT}[LAB] {title.upper()}{CLR_RST}")
    print(f"{CLR_CYN}{'=' * 78}{CLR_RST}")

# ============================================================================
# MODUL 1: C-Struct Alignment, Bitfields, dan Padding Memory Layout
# ============================================================================
# C-ABI memberlakukan byte-alignment sesuai word size arsitektur hardware.
# Misal, field 32-bit biasanya disejajarkan ke offset kelipatan 4 byte.

class PacketFlags(Structure):
    """Mendefinisikan bitfield dalam 1 byte (8-bit hardware register layout)."""
    _fields_ = [
        ("is_encrypted", c_uint8, 1),
        ("is_compressed", c_uint8, 1),
        ("priority", c_uint8, 2),
        ("reserved", c_uint8, 4),
    ]

class PacketPayload(Union):
    """C-Union: Berbagi memori yang sama antara representasi raw bytes dan numeric."""
    _fields_ = [
        ("raw_bytes", c_char * 8),
        ("raw_ints", c_uint32 * 2),
    ]

class NetworkFrame(Structure):
    """
    C-Struct kompleks dengan padding alami compiler (Natural Alignment).
    Offset setiap anggota dipengaruhi oleh batas byte tipe data.
    """
    _fields_ = [
        ("magic_byte", c_uint8),       # 1 byte  (Offset 0)
        # Compiler menyisipkan 1 byte padding di sini agar uint16 berada di batas genap!
        ("packet_id", c_uint16),       # 2 byte  (Offset 2)
        ("payload_len", c_uint32),     # 4 byte  (Offset 4)
        ("flags", PacketFlags),        # 1 byte  (Offset 8)
        # Compiler menyisipkan 3 byte padding untuk menyelaraskan Union 4-byte/8-byte!
        ("payload", PacketPayload),    # 8 byte  (Offset 12 atau 16 tergantung arsitektur)
    ]

def demo_memory_alignment():
    print_banner("1. Layout Memori C-ABI, Padding & Struct Offset")
    
    frame = NetworkFrame()
    frame.magic_byte = 0xAA
    frame.packet_id = 0x1024
    frame.payload_len = 8
    frame.flags.is_encrypted = 1
    frame.flags.is_compressed = 0
    frame.flags.priority = 3
    frame.payload.raw_ints[0] = 0xDEADBEEF
    frame.payload.raw_ints[1] = 0xCAFEBABE

    addr = addressof(frame)
    size = sizeof(frame)

    print(f"{CLR_BLD}Base Address:{CLR_RST} 0x{addr:016X} | {CLR_BLD}Total Struct Size:{CLR_RST} {size} bytes\n")
    print(f"{'Field':<15} {'Type':<12} {'Offset':<8} {'Size':<6} {'Value'}")
    print(f"{'-'*55}")

    for field_name, field_type in frame._fields_:
        field_offset = getattr(NetworkFrame, field_name).offset
        field_size = sizeof(field_type)
        val = getattr(frame, field_name)
        if isinstance(val, PacketFlags):
            val_str = f"enc={val.is_encrypted}, prio={val.priority}"
        elif isinstance(val, PacketPayload):
            val_str = f"ints=[0x{val.raw_ints[0]:X}, 0x{val.raw_ints[1]:X}]"
        else:
            val_str = f"0x{val:X}" if isinstance(val, int) else str(val)
            
        print(f"{CLR_YLW}{field_name:<15}{CLR_RST} {field_type.__name__:<12} "
              f"+{field_offset:<7} {field_size:<6} {CLR_GRN}{val_str}{CLR_RST}")

    # Dump raw hex memory buffer
    raw_buffer = (c_uint8 * size).from_address(addr)
    hex_dump = " ".join(f"{b:02X}" for b in raw_buffer)
    print(f"\n{CLR_BLD}Raw Memory Hex Dump:{CLR_RST}\n[{hex_dump}]")

# ============================================================================
# MODUL 2: C-Callback & Dynamically Linked libc Interoperability
# ============================================================================
# Mengikat Standard C Library (libc) dan meneruskan callback Python runtime 
# sebagai function pointer C yang dipanggil langsung oleh libc 'qsort'.

def resolve_libc():
    """Resolusi runtime C library lintas sistem operasi."""
    if sys.platform.startswith('win'):
        return ctypes.cdll.msvcrt
    lib_path = ctypes.util.find_library('c')
    if lib_path:
        return ctypes.CDLL(lib_path)
    # Fallback standar POSIX jika find_library mengembalikan None
    try:
        return ctypes.CDLL("libc.so.6")
    except OSError:
        return ctypes.CDLL(None)

def demo_c_callbacks():
    print_banner("2. C Dynamic Callbacks via Function Pointers (libc: qsort)")
    
    libc = resolve_libc()
    
    # Signature: int (*compare)(const void *, const void *)
    CMP_FUNC = CFUNCTYPE(c_int, POINTER(c_int), POINTER(c_int))
    
    callback_invocations = 0

    def py_descending_comparator(a_ptr, b_ptr):
        """Callback dieksekusi oleh thread stack C runtime selama qsort."""
        nonlocal callback_invocations
        callback_invocations += 1
        val_a = a_ptr.contents.value
        val_b = b_ptr.contents.value
        # Descending logic: > 0 jika val_b > val_a
        return (val_b > val_a) - (val_b < val_a)

    # Definisi prototipe C qsort:
    # void qsort(void *base, size_t nel, size_t width, int (*compar)(const void *, const void *))
    qsort = libc.qsort
    qsort.argtypes = [c_void_p, c_size_t, c_size_t, CMP_FUNC]
    qsort.restype = None

    dataset = [88, 12, 94, 3, 45, 67, 102, 1, 55, 33]
    arr_type = c_int * len(dataset)
    c_array = arr_type(*dataset)

    print(f"{CLR_BLD}Array Sebelum Diurutkan (C Memory):{CLR_RST} {list(c_array)}")
    
    # Bungkus Python function menjadi C-compatible Function Pointer
    c_comparator = CMP_FUNC(py_descending_comparator)
    
    qsort(
        cast(c_array, c_void_p),
        c_size_t(len(dataset)),
        c_size_t(sizeof(c_int)),
        c_comparator
    )
    
    print(f"{CLR_BLD}Array Sesudah Diurutkan (C qsort):{CLR_RST}   {CLR_GRN}{list(c_array)}{CLR_RST}")
    print(f"{CLR_BLD}Inter-ABI Context Switches (Callback calls):{CLR_RST} {CLR_YLW}{callback_invocations}{CLR_RST}")

# ============================================================================
# MODUL 3: Direct Pointer Mutation & Zero-Copy Byte Manipulation
# ============================================================================

def demo_direct_pointer_mutation():
    print_banner("3. Zero-Copy Pointer Cast & Direct Buffer Mutation")

    # Inisialisasi buffer memory biner menggunakan ctypes
    buffer_len = 16
    raw_buffer = (c_uint8 * buffer_len)(*([0x00] * buffer_len))
    buf_addr = addressof(raw_buffer)
    
    print(f"Alokasi Virtual Memory: {CLR_BLD}0x{buf_addr:016X}{CLR_RST} ({buffer_len} bytes)")
    print(f"Kondisi Awal: {' '.join(f'{b:02X}' for b in raw_buffer)}")

    # Injeksi data 32-bit integer tepat di tengah buffer (offset 4) menggunakan pointer cast
    target_offset = 4
    ptr_to_offset = cast(buf_addr + target_offset, POINTER(c_uint32))
    
    # Mutasi langsung pada memori mentah tanpa membuat salinan (Zero-Copy)
    ptr_to_offset.contents.value = 0xAABBCCDD

    # Injeksi string C tepat di offset 10
    string_offset = 10
    char_ptr = cast(buf_addr + string_offset, POINTER(c_char * 5))
    char_ptr.contents.value = b"KERN"

    print(f"\n{CLR_GRN}[+] Melakukan dereferensi pointer ke offset 4 (uint32) dan 10 (c_char[5])...{CLR_RST}")
    print(f"Kondisi Akhir: {CLR_YLW}{' '.join(f'{b:02X}' for b in raw_buffer)}{CLR_RST}")
    
    # Validasi interpretasi endianness hardware
    val_at_offset = ptr_to_offset.contents.value
    print(f"Nilai uint32 yang terbaca dari pointer: 0x{val_at_offset:08X} "
          f"({sys.byteorder.upper()}-ENDIAN representation)")

# ============================================================================
# MODUL 4: Benchmark: Python Abstraction vs Ctypes In-Place Buffer
# ============================================================================

def benchmark_memory_operations():
    print_banner("4. Benchmark: Python Dynamic Object vs C contiguous Buffer")
    
    ELEMENTS = 200_000
    print(f"Memproses transformasi XOR terhadap {CLR_BLD}{ELEMENTS:,}{CLR_RST} elemen...")

    # --- Uji 1: Pendekatan Python List Standar ---
    py_list = [i & 0xFF for i in range(ELEMENTS)]
    t0 = time.perf_counter()
    for idx in range(ELEMENTS):
        py_list[idx] = (py_list[idx] ^ 0xAA) + 1
    t1 = time.perf_counter()
    duration_py = (t1 - t0) * 1000

    # --- Uji 2: Pendekatan C-Array Buffer In-Place via ctypes ---
    CArrayType = c_uint8 * ELEMENTS
    c_buffer = CArrayType(*[i & 0xFF for i in range(ELEMENTS)])
    
    # Memaksimalkan efisiensi: pointer mentah tanpa overhead bounds checking tingkat tinggi
    t2 = time.perf_counter()
    buf_ptr = cast(c_buffer, POINTER(c_uint8))
    for idx in range(ELEMENTS):
        # Mutasi memori langsung
        buf_ptr[idx] = (buf_ptr[idx] ^ 0xAA) + 1
    t3 = time.perf_counter()
    duration_c = (t3 - t2) * 1000

    print(f"1. Standard Python List (Object Dispatch) : {CLR_RED}{duration_py:8.2f} ms{CLR_RST}")
    print(f"2. Ctypes Direct Contiguous Memory Pointer: {CLR_GRN}{duration_c:8.2f} ms{CLR_RST}")
    
    delta = duration_py - duration_c
    speedup = duration_py / duration_c if duration_c > 0 else float('inf')
    
    print(f"\n{CLR_BLD}Analisis Karakteristik:{CLR_RST}")
    print(f"- Ctypes menghindari PyObject metadata overhead per-elemen (hanya contiguous bytes).")
    print(f"- Walaupun iterasi loop tetap di CPython interpreter, manipulasi pointer C")
    print(f"  mengurangi beban alokasi dynamic garbage collector.")
    print(f"- Rasio Performa: {CLR_CYN}{speedup:.2f}x{CLR_RST}")

# ============================================================================
# Main Execution Entry Point
# ============================================================================
if __name__ == "__main__":
    print(f"{CLR_BLD}Python C-Extension & System Interoperability Diagnostic{CLR_RST}")
    print(f"Platform: {platform.platform()} | ABI Architecture: {platform.architecture()[0]}")
    
    try:
        demo_memory_alignment()
        demo_c_callbacks()
        demo_direct_pointer_mutation()
        benchmark_memory_operations()
        
        print(f"\n{CLR_GRN}{CLR_BLD}[OK] Seluruh modul verifikasi C-Extensions berhasil dieksekusi.{CLR_RST}\n")
    except Exception as e:
        print(f"\n{CLR_RED}[FATAL ERROR] Kegagalan interoperabilitas C: {e}{CLR_RST}", file=sys.stderr)
        sys.exit(1)