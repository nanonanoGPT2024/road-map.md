#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Zero-Copy Buffer Processing & Array-String Idiom (C)
BAB-05: Array, String Idiom, Zero-Copy Buffer Processing

Simulasi interaktif konsep memori level rendah C:
1. Flat Contiguous Memory Buffer & Pointer Offset Arithmetic
2. Null-Terminated String Idiom & In-Place Tokenization (mirip strtok/strsep)
3. Zero-Copy Slicing dengan memoryview vs Copy Allocations
4. Network Protocol Framing Parsing tanpa memcpy
"""

import sys
import time
from typing import List, Tuple, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_DARK = "\033[48;5;236m"
CLR_BG_HIGHLIGHT = "\033[48;5;240m"


class SimulatedMemoryBuffer:
    """
    Simulasi blok memori kontigu (seperti byte array char buffer[N] di C).
    Mendukung pointer arithmetic konseptual dan zero-copy slicing via memoryview.
    """
    def __init__(self, size: int, base_address: int = 0x7FFF0000):
        self.size = size
        self.base_address = base_address
        self._raw_data = bytearray(size)
        self._view = memoryview(self._raw_data)

    def write_bytes(self, offset: int, data: bytes) -> int:
        if offset + len(data) > self.size:
            raise ValueError("Buffer overflow: data melebihi kapasitas alokasi buffer!")
        self._raw_data[offset:offset + len(data)] = data
        return len(data)

    def get_slice_view(self, offset: int, length: int) -> memoryview:
        """Zero-copy slice menggunakan Python memoryview (tanpa duplikasi heap)."""
        if offset + length > self.size:
            raise IndexError("Pointer dereference out of bounds!")
        return self._view[offset:offset + length]

    def hex_dump(self, offset: int = 0, length: Optional[int] = None, pointers: Optional[dict] = None) -> str:
        """Menghasilkan representasi hex dump & ASCII visual dengan penanda pointer."""
        if length is None:
            length = self.size
        end = min(offset + length, self.size)
        lines = []

        header = f"{CLR_BOLD}{CLR_CYAN}{'Address':<12} {'Hex Bytes (Offset 0x00 - 0x0F)':<49} {'ASCII View':<16}{CLR_RESET}"
        lines.append(header)
        lines.append("-" * 80)

        for row_start in range(offset, end, 16):
            row_end = min(row_start + 16, end)
            addr_str = f"0x{self.base_address + row_start:08X}"

            # Hex values
            hex_parts = []
            for i in range(row_start, row_start + 16):
                if i < row_end:
                    b = self._raw_data[i]
                    if b == 0:
                        hex_parts.append(f"{CLR_RED}{b:02X}{CLR_RESET}")
                    elif 32 <= b <= 126:
                        hex_parts.append(f"{CLR_GREEN}{b:02X}{CLR_RESET}")
                    else:
                        hex_parts.append(f"{CLR_YELLOW}{b:02X}{CLR_RESET}")
                else:
                    hex_parts.append("  ")
            hex_str = " ".join(hex_parts)

            # ASCII values
            ascii_parts = []
            for i in range(row_start, row_end):
                b = self._raw_data[i]
                if b == 0:
                    ascii_parts.append(f"{CLR_RED}\\0{CLR_RESET}")
                elif 32 <= b <= 126:
                    ascii_parts.append(f"{CLR_WHITE}{chr(b)}{CLR_RESET}")
                else:
                    ascii_parts.append(f"{CLR_MAGENTA}.{CLR_RESET}")
            ascii_str = "".join(ascii_parts)

            lines.append(f"{CLR_BLUE}{addr_str}{CLR_RESET}  {hex_str}  |{ascii_str}|")

            # Check if any pointer points to this row
            if pointers:
                ptr_line = [" "] * 12 + [" "] * 2
                has_ptr = False
                for i in range(row_start, row_start + 16):
                    matched = [name for name, ptr_pos in pointers.items() if ptr_pos == i]
                    if matched:
                        has_ptr = True
                        ptr_label = "^" + matched[0]
                        ptr_line.extend([f"{CLR_YELLOW}{ptr_label[:2]:<2}{CLR_RESET}", " "])
                    else:
                        ptr_line.extend(["  ", " "])
                if has_ptr:
                    lines.append("".join(ptr_line))

        return "\n".join(lines)


def demo_string_idiom_strtok():
    """
    Simulasi pola C String: In-Place Delimiter Replacement (strtok / strsep idiom).
    Mengubah delimiter menjadi null-byte '\\0' tanpa alokasi string baru.
    """
    print(f"\n{CLR_BOLD}{CLR_YELLOW}=== [1] C String Idiom & In-Place Tokenizer (Zero-Copy) ==={CLR_RESET}")
    print(f"{CLR_CYAN}Konsep: String di C adalah array char yang diakhiri null-byte (\\0).")
    print(f"Tokenisasi efisien (strtok) mengganti delimiter dengan '\\0' langsung di buffer.{CLR_RESET}\n")

    buf = SimulatedMemoryBuffer(size=48)
    initial_text = b"POST /api/v1/orders HTTP/1.1\r\nHost: server"
    buf.write_bytes(0, initial_text)

    print(f"{CLR_BOLD}Keadaan Memori Awal (Sebelum Tokenisasi):{CLR_RESET}")
    print(buf.hex_dump(0, 48))

    print(f"\n{CLR_MAGENTA}Melakukan In-Place Parsing memisahkan HTTP Method, URI, dan Version...{CLR_RESET}")
    
    # In-place search and replace delimiter with 0 (null-terminator)
    tokens: List[Tuple[str, int, int]] = []
    ptr = 0
    token_start = 0
    length = len(initial_text)

    while ptr < length:
        b = buf._raw_data[ptr]
        if b in (ord(' '), ord('\r'), ord('\n')):
            # Ganti delimiter dengan null-terminator
            buf._raw_data[ptr] = 0
            if ptr > token_start:
                tok_len = ptr - token_start
                # Zero-copy view
                tok_bytes = bytes(buf.get_slice_view(token_start, tok_len))
                tokens.append((tok_bytes.decode('ascii', errors='replace'), token_start, tok_len))
            token_start = ptr + 1
        ptr += 1

    if token_start < length:
        tok_len = length - token_start
        tok_bytes = bytes(buf.get_slice_view(token_start, tok_len))
        tokens.append((tok_bytes.decode('ascii', errors='replace'), token_start, tok_len))

    print(f"\n{CLR_BOLD}Keadaan Memori Sesudah Delimiter Diganti Null-Terminator (\\0):{CLR_RESET}")
    print(buf.hex_dump(0, 48))

    print(f"\n{CLR_GREEN}{CLR_BOLD}Hasil Zero-Copy Pointers:{CLR_RESET}")
    for idx, (val, off, tlen) in enumerate(tokens):
        abs_addr = hex(buf.base_address + off)
        print(f"  Token [{idx}]: {CLR_BOLD}'{val}'{CLR_RESET} -> Buffer Offset: {off}, Addr: {abs_addr}, Len: {tlen}B")


def demo_zerocopy_protocol_framing():
    """
    Simulasi Network Packet Framing Header + Payload Parsing.
    Header: [2B Magic: 0xCAFE] [1B PacketType] [1B Flags] [4B PayloadLength] [Payload bytes...]
    """
    print(f"\n{CLR_BOLD}{CLR_YELLOW}=== [2] Network Frame Parser: Zero-Copy Slice vs Memcpy Copy ==={CLR_RESET}")
    print(f"{CLR_CYAN}Konsep: Membaca struct header dan payload tanpa menyalin (zero-copy slicing).{CLR_RESET}\n")

    buf = SimulatedMemoryBuffer(size=64)
    # Magic=0xCAFE, Type=0x01 (ORDER_PAYLOAD), Flags=0x00, Length=16 bytes
    header = bytes([0xCA, 0xFE, 0x01, 0x00, 0x00, 0x00, 0x00, 0x10])
    payload = b"PAYLOAD_TX_98741"  # 16 bytes
    buf.write_bytes(0, header)
    buf.write_bytes(len(header), payload)

    print(buf.hex_dump(0, 32, pointers={"HD": 0, "PL": 8}))

    # Parsing struct secara zero-copy
    magic = (buf._raw_data[0] << 8) | buf._raw_data[1]
    pkt_type = buf._raw_data[2]
    payload_len = int.from_bytes(buf._raw_data[4:8], byteorder="big")

    print(f"\n{CLR_BOLD}Header Analysis:{CLR_RESET}")
    print(f"  Magic Number   : {CLR_GREEN}0x{magic:04X}{CLR_RESET} (Valid: {magic == 0xCAFE})")
    print(f"  Packet Type    : {CLR_GREEN}0x{pkt_type:02X}{CLR_RESET}")
    print(f"  Payload Length : {CLR_GREEN}{payload_len} bytes{CLR_RESET}")

    # Zero-copy view vs Memcpy
    zero_copy_view = buf.get_slice_view(8, payload_len)
    deep_copy_buffer = bytes(buf._raw_data[8:8 + payload_len])

    print(f"\n{CLR_BOLD}Verifikasi Mutasi In-Place Buffer Induk:{CLR_RESET}")
    print(f"  Zero-copy View sebelum mutasi: {bytes(zero_copy_view)}")
    print(f"  Memcpy Buffer sebelum mutasi : {deep_copy_buffer}")

    # Modifikasi buffer induk di offset payload
    print(f"\n{CLR_RED}>> Mengubah karakter pertama payload pada induk memori ('P' -> 'X')...{CLR_RESET}")
    buf._raw_data[8] = ord('X')

    print(f"  Zero-copy View sesudah mutasi: {CLR_GREEN}{bytes(zero_copy_view)}{CLR_RESET} (Ikut berubah otomatis!)")
    print(f"  Memcpy Buffer sesudah mutasi : {CLR_YELLOW}{deep_copy_buffer}{CLR_RESET} (Statis/Ketinggalan, makan 2x RAM)")


def benchmark_zerocopy_vs_memcpy():
    """
    Benchmark perbandingan performa:
    Operasi Slicing Tradisional (Copy Allocation) vs Zero-Copy memoryview.
    """
    print(f"\n{CLR_BOLD}{CLR_YELLOW}=== [3] Benchmark Kinerja: Slicing Buffer 10 MB x 50.000 Iterasi ==={CLR_RESET}")
    print(f"{CLR_CYAN}Mengukur perbedaan latensi CPU dan overhead alokasi memori heap.{CLR_RESET}\n")

    size_mb = 10
    total_bytes = size_mb * 1024 * 1024
    test_buffer = bytearray(total_bytes)
    test_view = memoryview(test_buffer)
    iterations = 50000

    print(f"Mengalokasikan buffer pengujian sebesar {size_mb} MB...")

    # 1. Standard Copy Slicing
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = test_buffer[1024:1024 + 4096]  # Mengalokasikan objek bytes baru setiap iterasi
    t_copy = time.perf_counter() - t0

    # 2. Zero-Copy View Slicing
    t1 = time.perf_counter()
    for _ in range(iterations):
        _ = test_view[1024:1024 + 4096]    # Hanya pointer window offset, 0 alokasi data
    t_zerocopy = time.perf_counter() - t1

    speedup = t_copy / t_zerocopy if t_zerocopy > 0 else float("inf")

    print(f"  1. Copy Slicing (memcpy equivalent) : {CLR_RED}{t_copy:.5f} detik{CLR_RESET}")
    print(f"  2. Zero-Copy (pointer/memoryview)  : {CLR_GREEN}{t_zerocopy:.5f} detik{CLR_RESET}")
    print(f"  --> Akselerasi Efisiensi            : {CLR_BOLD}{CLR_CYAN}{speedup:.2f}x Lebih Cepat{CLR_RESET}")


def interactive_menu():
    """Menu CLI interaktif untuk menjelajahi konsep zero-copy buffer."""
    banner = f"""{CLR_BOLD}{CLR_CYAN}
========================================================================
   SIMULASI TEKNIS C: ZERO-COPY BUFFER PROCESSING & STRING IDIOM
              BAB-05 Hands-on Laboratory Exercise
========================================================================{CLR_RESET}"""
    print(banner)

    while True:
        print(f"\n{CLR_BOLD}Pilih Modul Simulasi:{CLR_RESET}")
        print(f"  {CLR_GREEN}[1]{CLR_RESET} Simulasi C String Idiom & In-Place Tokenizer (\\0 replacement)")
        print(f"  {CLR_GREEN}[2]{CLR_RESET} Simulasi Network Protocol Header-Payload Zero-Copy Parser")
        print(f"  {CLR_GREEN}[3]{CLR_RESET} Benchmark Performa Zero-Copy vs Memory Copy Slicing")
        print(f"  {CLR_GREEN}[4]{CLR_RESET} Jalankan Seluruh Rangkaian Lab Sekaligus")
        print(f"  {CLR_RED}[q]{CLR_RESET} Keluar")

        try:
            choice = input(f"\n{CLR_BOLD}Masukkan pilihan (1/2/3/4/q): {CLR_RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{CLR_YELLOW}Selesai.{CLR_RESET}")
            break

        if choice == '1':
            demo_string_idiom_strtok()
        elif choice == '2':
            demo_zerocopy_protocol_framing()
        elif choice == '3':
            benchmark_zerocopy_vs_memcpy()
        elif choice == '4':
            demo_string_idiom_strtok()
            demo_zerocopy_protocol_framing()
            benchmark_zerocopy_vs_memcpy()
            print(f"\n{CLR_BOLD}{CLR_GREEN}Seluruh demonstrasi berhasil dijalankan!{CLR_RESET}")
            break
        elif choice in ('q', 'exit', 'quit'):
            print(f"\n{CLR_GREEN}Terima kasih telah menjalankan simulasi zero-copy buffer.{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid, silakan coba lagi.{CLR_RESET}")


if __name__ == "__main__":
    # Jika dijalankan secara non-interaktif (piped atau CI), jalankan opsi 4 secara otomatis
    if not sys.stdin.isatty():
        demo_string_idiom_strtok()
        demo_zerocopy_protocol_framing()
        benchmark_zerocopy_vs_memcpy()
    else:
        interactive_menu()
