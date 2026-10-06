#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Konsep Fondasi Inti C (BAB 06)
Topik: Struct, Union, Enum, Memory Alignment & Padding Visualizer
Bahasa: Python 3 (Standalone Runnable Simulation)
"""

import sys
import struct
import math
from typing import List, Dict, Tuple, Any

# ANSI Escape Sequences untuk Pewarnaan Terminal
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
BG_CYAN = "\033[46m"
BG_GRAY = "\033[100m"

def print_header(title: str):
    width = 75
    print("\n" + CYAN + "=" * width + RESET)
    print(f"{BOLD}{WHITE}{title.center(width)}{RESET}")
    print(CYAN + "=" * width + RESET)

def print_section(title: str):
    print(f"\n{BOLD}{YELLOW}>>> [SUB-MODUL] {title}{RESET}")
    print(f"{DIM}{'-' * 60}{RESET}")

# -----------------------------------------------------------------------------
# 1. SIMULASI MEMORY ALIGNMENT & STRUCT PADDING
# -----------------------------------------------------------------------------
class StructSimulator:
    """
    Mensimulasikan ABI alignment standar sistem arsitektur x86_64 / ARM64.
    Aturan:
      - Tipe berukuran N byte harus dialokasikan pada alamat kelipatan N.
      - Total ukuran struct dibulatkan ke kelipatan dari alignment terbesar anggotanya.
    """
    TYPE_SIZES = {
        'char': 1,
        'uint8_t': 1,
        'int16_t': 2,
        'short': 2,
        'int': 4,
        'uint32_t': 4,
        'float': 4,
        'double': 8,
        'int64_t': 8,
        'pointer': 8
    }

    def __init__(self, name: str, members: List[Tuple[str, str]]):
        self.name = name
        self.members = members  # List of (type, name)
        self.layout: List[Dict[str, Any]] = []
        self.total_size = 0
        self.max_alignment = 1
        self.padding_bytes = 0
        self._calculate_layout()

    def _calculate_layout(self):
        current_offset = 0
        self.max_alignment = 1

        for type_str, field_name in self.members:
            size = self.TYPE_SIZES.get(type_str, 1)
            alignment = size
            self.max_alignment = max(self.max_alignment, alignment)

            # Hitung padding sebelum field jika offset belum aligned
            remainder = current_offset % alignment
            pad = 0 if remainder == 0 else (alignment - remainder)

            if pad > 0:
                self.layout.append({
                    'is_padding': True,
                    'type': f'padding',
                    'name': f'[pad {pad}B]',
                    'offset': current_offset,
                    'size': pad
                })
                current_offset += pad
                self.padding_bytes += pad

            self.layout.append({
                'is_padding': False,
                'type': type_str,
                'name': field_name,
                'offset': current_offset,
                'size': size
            })
            current_offset += size

        # Trailing padding untuk mencocokkan kelipatan alignment terbesar struct
        trailing_remainder = current_offset % self.max_alignment
        if trailing_remainder != 0:
            trailing_pad = self.max_alignment - trailing_remainder
            self.layout.append({
                'is_padding': True,
                'type': 'trailing_padding',
                'name': f'[tail pad {trailing_pad}B]',
                'offset': current_offset,
                'size': trailing_pad
            })
            current_offset += trailing_pad
            self.padding_bytes += trailing_pad

        self.total_size = current_offset

    def display(self):
        print(f"{BOLD}Struct Definition: {CYAN}{self.name}{RESET}")
        raw_size = sum(self.TYPE_SIZES.get(t, 1) for t, _ in self.members)
        print(f"Total Ukuran Nyata : {GREEN}{self.total_size} byte{RESET}")
        print(f"Ukuran Data Murni  : {WHITE}{raw_size} byte{RESET}")
        print(f"Total Padding Terbuang : {RED}{self.padding_bytes} byte{RESET}")
        print(f"Max Alignment      : {MAGENTA}{self.max_alignment} byte{RESET}\n")

        print(f"{'Offset':<8} | {'Field':<18} | {'Tipe':<12} | {'Ukuran':<8} | {'Visual Memori'}")
        print("-" * 75)

        for item in self.layout:
            offset_str = f"0x{item['offset']:04X} ({item['offset']:02d})"
            size_str = f"{item['size']} B"
            if item['is_padding']:
                field_col = f"{RED}{item['name']}{RESET}"
                type_col = f"{RED}PADDING{RESET}"
                vis = f"{BG_GRAY}{' X ' * item['size']}{RESET}"
            else:
                field_col = f"{GREEN}{item['name']}{RESET}"
                type_col = f"{CYAN}{item['type']}{RESET}"
                vis = f"{BG_BLUE}{' B ' * item['size']}{RESET}"
            print(f"{offset_str:<8} | {field_col:<27} | {type_col:<21} | {size_str:<8} | {vis}")

# -----------------------------------------------------------------------------
# 2. SIMULASI UNION MEMORY OVERLAP
# -----------------------------------------------------------------------------
class UnionSimulator:
    """
    Mensimulasikan union di C di mana semua anggota berbagi lokasi memori yang sama.
    """
    def __init__(self, name: str):
        self.name = name
        # Alokasi buffer memori mentah 8 byte
        self.buffer = bytearray(8)

    def write_uint32(self, val: int):
        packed = struct.pack('<I', val & 0xFFFFFFFF)
        self.buffer[0:4] = packed

    def write_float(self, val: float):
        packed = struct.pack('<f', val)
        self.buffer[0:4] = packed

    def write_double(self, val: float):
        packed = struct.pack('<d', val)
        self.buffer[0:8] = packed

    def inspect(self):
        val_u8_0 = self.buffer[0]
        val_u32 = struct.unpack('<I', self.buffer[0:4])[0]
        val_f32 = struct.unpack('<f', self.buffer[0:4])[0]
        val_u64 = struct.unpack('<Q', self.buffer[0:8])[0]
        val_f64 = struct.unpack('<d', self.buffer[0:8])[0]

        print(f"{BOLD}Union: {MAGENTA}{self.name}{RESET} (Alamat Basis Bersama: 0x7FFF0000)")
        print(f"{'Byte Index':<12}: " + " ".join([f"[{i}]" for i in range(8)]))
        print(f"{'Raw Bytes':<12}: " + " ".join([f"{b:02X}" for b in self.buffer]))
        print(f"{'ASCII View':<12}: " + " ".join([f" '{chr(b)}'" if 32 <= b <= 126 else " '.' " for b in self.buffer]))
        print("-" * 60)
        print(f"Interpretasi Sebagai:")
        print(f"  • uint8_t (byte[0]) : {GREEN}{val_u8_0}{RESET} (0x{val_u8_0:02X})")
        print(f"  • uint32_t (4 byte) : {CYAN}{val_u32}{RESET} (0x{val_u32:08X})")
        print(f"  • float    (4 byte) : {YELLOW}{val_f32:e}{RESET} (IEEE-754: {val_f32})")
        print(f"  • uint64_t (8 byte) : {WHITE}{val_u64}{RESET} (0x{val_u64:016X})")
        print(f"  • double   (8 byte) : {MAGENTA}{val_f64:e}{RESET}")

# -----------------------------------------------------------------------------
# 3. SIMULASI ENUM & BIT FLAGS
# -----------------------------------------------------------------------------
class EnumSimulator:
    """
    Mensimulasikan C Enum numerik dan Bitmask Flags pattern.
    """
    HTTP_STATUS = {
        "HTTP_OK": 200,
        "HTTP_CREATED": 201,
        "HTTP_BAD_REQUEST": 400,
        "HTTP_UNAUTHORIZED": 401,
        "HTTP_NOT_FOUND": 404,
        "HTTP_INTERNAL_ERROR": 500
    }

    FILE_PERMS = {
        "PERM_EXEC":  1 << 0,  # 0b001 = 1
        "PERM_WRITE": 1 << 1,  # 0b010 = 2
        "PERM_READ":  1 << 2,  # 0b100 = 4
    }

    @classmethod
    def display_enums(cls):
        print(f"{BOLD}1. Standar Enum (HTTP Status Code Mapping):{RESET}")
        for k, v in cls.HTTP_STATUS.items():
            print(f"   typedef enum {{ {CYAN}{k:<22}{RESET} = {GREEN}{v}{RESET} }} HttpStatus;")

        print(f"\n{BOLD}2. Bitmask Flag Pattern (Permissions):{RESET}")
        current_perm = cls.FILE_PERMS["PERM_READ"] | cls.FILE_PERMS["PERM_WRITE"]

        print(f"   Definisi Flag:")
        for name, bit in cls.FILE_PERMS.items():
            print(f"     {MAGENTA}{name:<12}{RESET} = (1 << {int(math.log2(bit))}) -> 0b{bit:03b} ({bit})")

        print(f"\n   Operasi Bitwise:")
        print(f"   uint8_t file_perm = PERM_READ | PERM_WRITE;  // Nilai: {current_perm} (0b{current_perm:03b})")
        for flag_name, flag_val in cls.FILE_PERMS.items():
            has_flag = (current_perm & flag_val) != 0
            status_str = f"{GREEN}AKTIF [✓]{RESET}" if has_flag else f"{RED}NONAKTIF [✗]{RESET}"
            print(f"     Pengecekan ({flag_name}): {status_str}")

# -----------------------------------------------------------------------------
# 4. RUNNER & INTERACTIVE DEMONSTRATION
# -----------------------------------------------------------------------------
def run_interactive_lab():
    print_header("LAB SIMULASI TEKNIS: C MEMORY MODEL & USER-DEFINED TYPES")
    print(f"{DIM}Modul Eksplorasi: Struct Padding, Union Memory Overlap, & Enum Bitflags{RESET}")

    # Skenario 1: Struct Unoptimized vs Optimized
    print_section("1. Struct Memory Alignment & Padding Analysis")
    print("Menganalisis perbedaan penataan urutan member pada efisiensi memori RAM.\n")

    unoptimized = StructSimulator("BadlyAlignedStruct", [
        ('char', 'status_code'),     # 1 byte
        ('double', 'sensor_reading'),# 8 byte (alignment 8 -> butuh 7B padding)
        ('int', 'packet_id'),        # 4 byte
        ('char', 'checksum'),        # 1 byte (trailing pad 3B agar kelipatan 8)
    ])
    unoptimized.display()

    print("\n" + "-" * 60)
    print(f"{BOLD}Optimasi Reordering Member Struct (Urutan Besar ke Kecil):{RESET}")
    optimized = StructSimulator("OptimizedStruct", [
        ('double', 'sensor_reading'),# 8 byte
        ('int', 'packet_id'),        # 4 byte
        ('char', 'status_code'),     # 1 byte
        ('char', 'checksum'),        # 1 byte
    ])
    optimized.display()

    savings = unoptimized.total_size - optimized.total_size
    percent = (savings / unoptimized.total_size) * 100
    print(f"\n{BOLD}{GREEN}HASIL OPTIMASI:{RESET} Penghematan Memori sebesar {savings} Byte ({percent:.1f}% lebih hemat)!")

    # Skenario 2: Union Overlap
    print_section("2. C Union Overlap & Type Punning Emulation")
    union_sim = UnionSimulator("HardwarePacketUnion")

    print("Kasus 2.1: Menulis nilai Integer Hexadecimal 0x41424344 ke dalam Union:")
    union_sim.write_uint32(0x41424344)
    union_sim.inspect()

    print("\nKasus 2.2: Menulis nilai Float 3.1415927 ke lokasi memori yang sama:")
    union_sim.write_float(3.1415927)
    union_sim.inspect()

    # Skenario 3: Enum & Bitwise Flags
    print_section("3. Enum Logic & Bitmask Flag System")
    EnumSimulator.display_enums()

    print("\n" + CYAN + "=" * 75 + RESET)
    print(f"{BOLD}{GREEN}Simulasi Lab Eksekusi C Selesai dengan Sukses (100% Valid Runnable).{RESET}")
    print(CYAN + "=" * 75 + RESET + "\n")

if __name__ == "__main__":
    run_interactive_lab()
