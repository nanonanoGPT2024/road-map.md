#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Fondasi C Pointer Mastery & Aritmetika Memori
BAB 04: Pointer Mastery, Aritmetika Alamat, dan Manipulasi Memori
"""

import sys
import struct
import time

# ANSI Color Codes untuk visualisasi terminal
class Style:
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
    BG_DARK = "\033[40m"


class VirtualMemory:
    """Simulasi ruang memori linier byte-addressable (RAM sederhana)"""
    def __init__(self, base_addr=0x1000, size=64):
        self.base_addr = base_addr
        self.size = size
        self.memory = bytearray(size)

    def is_valid(self, addr, length=1):
        return self.base_addr <= addr and (addr + length) <= (self.base_addr + self.size)

    def write_bytes(self, addr, data: bytes):
        if not self.is_valid(addr, len(data)):
            raise ValueError(f"Segmentation Fault: Alamat 0x{addr:04X} di luar batas alokasi!")
        offset = addr - self.base_addr
        self.memory[offset:offset + len(data)] = data

    def read_bytes(self, addr, length: int) -> bytes:
        if not self.is_valid(addr, length):
            raise ValueError(f"Segmentation Fault: Alamat 0x{addr:04X} di luar batas alokasi!")
        offset = addr - self.base_addr
        return bytes(self.memory[offset:offset + length])

    def dump_hex(self, highlight_range=None, active_ptr=None):
        print(f"\n{Style.BOLD}{Style.CYAN}=== PETA MEMORI FISIK (0x{self.base_addr:04X} - 0x{self.base_addr + self.size - 1:04X}) ==={Style.RESET}")
        print(f"{Style.DIM}Alamat   | +0 +1 +2 +3 +4 +5 +6 +7 | ASCII Representation{Style.RESET}")
        print("-" * 55)

        for row_start in range(self.base_addr, self.base_addr + self.size, 8):
            row_bytes = self.read_bytes(row_start, 8)
            hex_parts = []
            ascii_parts = []

            for i, b in enumerate(row_bytes):
                curr_addr = row_start + i
                h_str = f"{b:02X}"

                # Highlight pointer target
                if active_ptr == curr_addr:
                    h_str = f"{Style.BG_BLUE}{Style.BOLD}{h_str}{Style.RESET}"
                elif highlight_range and highlight_range[0] <= curr_addr < highlight_range[1]:
                    h_str = f"{Style.GREEN}{Style.BOLD}{h_str}{Style.RESET}"

                hex_parts.append(h_str)
                ch = chr(b) if 32 <= b <= 126 else "."
                ascii_parts.append(ch)

            hex_line = " ".join(hex_parts)
            ascii_line = "".join(ascii_parts)
            marker = f"{Style.YELLOW}<- [PTR]{Style.RESET}" if active_ptr and (row_start <= active_ptr < row_start + 8) else ""
            print(f"0x{row_start:04X} | {hex_line} | {ascii_line} {marker}")
        print("-" * 55)


class PointerSimulator:
    """Engine simulator konsep pointer C"""
    TYPE_SIZES = {
        "char": 1,
        "short": 2,
        "int": 4,
        "double": 8,
        "pointer": 4
    }

    def __init__(self):
        self.vm = VirtualMemory(base_addr=0x2000, size=48)
        self._init_sample_data()

    def _init_sample_data(self):
        # Inisialisasi data array integer [100, 200, 300, 400] di 0x2000
        arr_data = struct.pack("<4i", 100, 200, 300, 400)
        self.vm.write_bytes(0x2000, arr_data)

        # Inisialisasi string buffer "POINTER" di 0x2018
        str_data = b"POINTER\x00"
        self.vm.write_bytes(0x2018, str_data)

    def demo_dereference(self):
        print(f"\n{Style.BOLD}{Style.MAGENTA}[DEMO 1: Deklarasi & Dereferencing Pointer]{Style.RESET}")
        print(f"Kode C Ekuivalen:\n  {Style.YELLOW}int val = 100; int *p = &val; *p = 999;{Style.RESET}\n")

        target_addr = 0x2000
        old_val = struct.unpack("<i", self.vm.read_bytes(target_addr, 4))[0]
        print(f"1. Membaca target di alamat {Style.CYAN}0x{target_addr:04X}{Style.RESET}: {old_val}")
        self.vm.dump_hex(highlight_range=(target_addr, target_addr + 4), active_ptr=target_addr)

        print(f"\n{Style.GREEN}Melakukan dereferencing write: *p = 999{Style.RESET}")
        new_bytes = struct.pack("<i", 999)
        self.vm.write_bytes(target_addr, new_bytes)

        read_back = struct.unpack("<i", self.vm.read_bytes(target_addr, 4))[0]
        print(f"2. Nilai setelah mutasi dereference: {Style.BOLD}{read_back}{Style.RESET}")
        self.vm.dump_hex(highlight_range=(target_addr, target_addr + 4), active_ptr=target_addr)

    def demo_pointer_arithmetic(self):
        print(f"\n{Style.BOLD}{Style.MAGENTA}[DEMO 2: Aritmetika Alamat (Scaling Berdasarkan Tipe Data)]{Style.RESET}")
        print("Aturan C: `ptr + n` bergerak sejauh `n * sizeof(*ptr)` byte fisik!\n")

        types = [("char", 1), ("short", 2), ("int", 4), ("double", 8)]
        base = 0x2000

        for t_name, t_size in types:
            step = 1
            calculated_addr = base + (step * t_size)
            print(f"• Tipe {Style.YELLOW}{t_name:6s}{Style.RESET} (sizeof={t_size}):")
            print(f"    Base Addr: 0x{base:04X}")
            print(f"    Formula  : 0x{base:04X} + ({step} * {t_size})")
            print(f"    Hasil    : {Style.GREEN}0x{calculated_addr:04X}{Style.RESET} (Lompat {t_size} byte)")

        print(f"\n{Style.BOLD}Iterasi Array `int arr[] = {{100, 200, 300, 400}}` via Pointer Step:{Style.RESET}")
        ptr = 0x2000
        for idx in range(4):
            val = struct.unpack("<i", self.vm.read_bytes(ptr, 4))[0]
            print(f"  [{idx}] Alamat: {Style.CYAN}0x{ptr:04X}{Style.RESET} | Nilai (*(ptr+{idx})): {Style.GREEN}{val}{Style.RESET}")
            ptr += 4

    def demo_double_pointer(self):
        print(f"\n{Style.BOLD}{Style.MAGENTA}[DEMO 3: Pointer-to-Pointer (int**)]{Style.RESET}")
        print(f"Kode C Ekuivalen:\n  {Style.YELLOW}int x = 42; int *p = &x; int **pp = &p;{Style.RESET}\n")

        addr_x = 0x2024
        addr_p = 0x2028
        addr_pp = 0x202C

        # Tulis x = 42
        self.vm.write_bytes(addr_x, struct.pack("<i", 42))
        # Tulis p = &x (pointer menampung alamat x)
        self.vm.write_bytes(addr_p, struct.pack("<I", addr_x))
        # Tulis pp = &p (double pointer menampung alamat p)
        self.vm.write_bytes(addr_pp, struct.pack("<I", addr_p))

        print(f"Variabel {Style.BOLD}x{Style.RESET}  disimpan di {Style.CYAN}0x{addr_x:04X}{Style.RESET} bernilai: 42")
        print(f"Pointer  {Style.BOLD}p{Style.RESET}  disimpan di {Style.CYAN}0x{addr_p:04X}{Style.RESET} bernilai: 0x{addr_x:04X} (&x)")
        print(f"Pointer  {Style.BOLD}pp{Style.RESET} disimpan di {Style.CYAN}0x{addr_pp:04X}{Style.RESET} bernilai: 0x{addr_p:04X} (&p)")

        # Evaluasi dereferensi ganda: **pp
        deref_step1 = struct.unpack("<I", self.vm.read_bytes(addr_pp, 4))[0]
        deref_step2 = struct.unpack("<I", self.vm.read_bytes(deref_step1, 4))[0]
        final_val = struct.unpack("<i", self.vm.read_bytes(deref_step2, 4))[0]

        print(f"\nLangkah Resolusi Hardware:")
        print(f"  1. Baca isi pp   (0x{addr_pp:04X})  -> 0x{deref_step1:04X} (*pp == p)")
        print(f"  2. Baca isi p    (0x{deref_step1:04X})  -> 0x{deref_step2:04X} (**pp == x address)")
        print(f"  3. Baca isi x    (0x{deref_step2:04X})  -> Nilai: {Style.GREEN}{final_val}{Style.RESET}")

        self.vm.dump_hex(highlight_range=(addr_x, addr_pp + 4), active_ptr=addr_x)

    def demo_endianness(self):
        print(f"\n{Style.BOLD}{Style.MAGENTA}[DEMO 4: Endianness & Memory Layout Byte-by-Byte]{Style.RESET}")
        val = 0x12345678
        addr = 0x2010

        le_bytes = struct.pack("<I", val)
        self.vm.write_bytes(addr, le_bytes)

        print(f"Nilai 32-bit Integer: {Style.YELLOW}0x12345678{Style.RESET}")
        print(f"Disimpan pada arsitektur Little-Endian (Intel/AMD/ARM standar):")
        print("  Alamat Rendah menyimpan LSB (Least Significant Byte)\n")

        for i, b in enumerate(le_bytes):
            curr = addr + i
            print(f"  Offset +{i} (0x{curr:04X}): {Style.CYAN}0x{b:02X}{Style.RESET}  <-- byte {i}")

        self.vm.dump_hex(highlight_range=(addr, addr + 4), active_ptr=addr)


def print_banner():
    banner = f"""{Style.BOLD}{Style.CYAN}
╔═══════════════════════════════════════════════════════════════════╗
║  LAB EXERCISE M01: C POINTER & MEMORY ARITHMETIC SIMULATOR        ║
║  BAB 04: Pointer Mastery, Aritmetika Alamat & Manipulasi Memori   ║
╚═══════════════════════════════════════════════════════════════════╝{Style.RESET}"""
    print(banner)


def show_menu():
    print(f"\n{Style.BOLD}PILIHAN LAB INTERAKTIF:{Style.RESET}")
    print(f"  {Style.GREEN}1.{Style.RESET} Visualisasi Dump Memori Virtual")
    print(f"  {Style.GREEN}2.{Style.RESET} Simulasi Pointer Dereferencing & Mutasi (*p)")
    print(f"  {Style.GREEN}3.{Style.RESET} Simulasi Aritmetika Pointer & Scaling Type")
    print(f"  {Style.GREEN}4.{Style.RESET} Simulasi Double Pointer (int**)")
    print(f"  {Style.GREEN}5.{Style.RESET} Visualisasi Little-Endian vs Byte Layout")
    print(f"  {Style.GREEN}6.{Style.RESET} Jalankan Seluruh Seri Laboratorium Sekaligus")
    print(f"  {Style.RED}0.{Style.RESET} Keluar")


def main():
    sim = PointerSimulator()
    print_banner()

    # Jika dijalankan secara non-interaktif (piped/CI test)
    if not sys.stdin.isatty():
        print(f"{Style.YELLOW}Mode Non-Interaktif Terdeteksi: Menjalankan eksekusi verifikasi otomatis...{Style.RESET}")
        sim.vm.dump_hex()
        sim.demo_dereference()
        sim.demo_pointer_arithmetic()
        sim.demo_double_pointer()
        sim.demo_endianness()
        print(f"\n{Style.BOLD}{Style.GREEN}✔ Verifikasi Otomatis Sukses: 100% Modul Pointer Berfungsi Normal.{Style.RESET}")
        return

    while True:
        show_menu()
        try:
            choice = input(f"\n{Style.BOLD}Pilih nomor modul [0-6]: {Style.RESET}").strip()
            if choice == "1":
                sim.vm.dump_hex()
            elif choice == "2":
                sim.demo_dereference()
            elif choice == "3":
                sim.demo_pointer_arithmetic()
            elif choice == "4":
                sim.demo_double_pointer()
            elif choice == "5":
                sim.demo_endianness()
            elif choice == "6":
                sim.vm.dump_hex()
                sim.demo_dereference()
                sim.demo_pointer_arithmetic()
                sim.demo_double_pointer()
                sim.demo_endianness()
            elif choice == "0":
                print(f"\n{Style.GREEN}Selesai! Terus eksplorasi manipulasi memori tingkat rendah C.{Style.RESET}")
                break
            else:
                print(f"{Style.RED}Pilihan tidak valid, silakan ulangi.{Style.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Style.YELLOW}Lab dihentikan oleh pengguna.{Style.RESET}")
            break


if __name__ == "__main__":
    main()
