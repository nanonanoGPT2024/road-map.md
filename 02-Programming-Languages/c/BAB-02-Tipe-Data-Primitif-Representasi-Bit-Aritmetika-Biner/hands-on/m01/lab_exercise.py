#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Representasi Bit, Two's Complement, & Aritmetika Biner C
Bab 02: Tipe Data Primitif, Representasi Bit, & Aritmetika Biner

Simulasi mandiri untuk memvisualisasikan bagaimana representasi memori level rendah
bekerja pada arsitektur sistem (signed/unsigned integer wrap-around, IEEE-754 floating point,
serta operasi bitwise dan endianness).
"""

import sys
import struct

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_BLUE = "\033[44m"
BG_DARK = "\033[100m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{WHITE} >>> {title.upper()} <<<{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


def format_bits(val: int, bits: int = 8, group: int = 4) -> str:
    """Format biner dengan pengelompokan per nibble dan pewarnaan bit tanda (MSB)."""
    mask = (1 << bits) - 1
    raw_bin = bin(val & mask)[2:].zfill(bits)
    # Group first on raw characters
    chunks = [raw_bin[max(0, i - group):i] for i in range(len(raw_bin), 0, -group)][::-1]
    # Highlight MSB on the first chunk
    first_chunk = f"{RED}{chunks[0][0]}{RESET}" + chunks[0][1:]
    return " ".join([first_chunk] + chunks[1:])


def demo_twos_complement_and_overflow() -> None:
    header("1. Representasi Two's Complement & Integer Wrap-Around (8-bit)")
    print(f"{YELLOW}Dalam C, tipe 'int8_t' (signed char) berkisar dari -128 hingga 127.{RESET}")
    print(f"Sedangkan 'uint8_t' (unsigned char) berkisar dari 0 hingga 255.\n")

    test_values = [0, 1, 42, 127, 128, -1, -42, -128]
    print(f"{BOLD}{'Nilai Desimal':<15} {'Signed (8-bit)':<18} {'Unsigned':<12} {'Representasi Biner (MSB Merah)':<30}{RESET}")
    print("-" * 75)

    for val in test_values:
        # Konversi ke 8-bit two's complement
        signed_8 = struct.unpack("b", struct.pack("B", val & 0xFF))[0]
        unsigned_8 = val & 0xFF
        b_str = format_bits(unsigned_8, 8)
        print(f"{val:<15} {signed_8:<18} {unsigned_8:<12} {b_str:<30}")

    print(f"\n{BOLD}{MAGENTA}[SIMULASI OVERFLOW INT8]{RESET}")
    x = 126
    for step in range(5):
        raw = (x + step) & 0xFF
        signed_val = struct.unpack("b", struct.pack("B", raw))[0]
        status = f"{RED}(OVERFLOW TERJADI!){RESET}" if signed_val < 0 else f"{GREEN}(Normal){RESET}"
        print(f"Step {step+1}: 126 + {step} = {x + step:<4} -> Raw: 0x{raw:02X} | Bits: {format_bits(raw, 8)} | int8_t: {signed_val:<4} {status}")


def demo_bitwise_operations() -> None:
    header("2. Operasi Bitwise Inti C (&, |, ^, ~, <<, >>)")
    a = 0b00111100  # 60
    b = 0b00001101  # 13

    print(f"Nilai A: {a:<4} (0x{a:02X}) -> {format_bits(a, 8)}")
    print(f"Nilai B: {b:<4} (0x{b:02X}) -> {format_bits(b, 8)}\n")

    ops = [
        ("A & B (AND)", a & b),
        ("A | B (OR)", a | b),
        ("A ^ B (XOR)", a ^ b),
        ("~A    (NOT / Invert 8-bit)", (~a) & 0xFF),
        ("A << 2 (Left Shift)", (a << 2) & 0xFF),
        ("A >> 2 (Right Shift)", (a >> 2) & 0xFF),
    ]

    for label, res in ops:
        print(f"{BOLD}{CYAN}{label:<28}{RESET} : 0x{res:02X} ({res:>3}) | Biner: {format_bits(res, 8)}")


def demo_bitmask_flags() -> None:
    header("3. Simulasi Bitmasking & Flag Status Hardware (Registers)")
    print(f"{YELLOW}Pola umum driver perangkat keras dalam bahasa C untuk manipulasi register.{RESET}\n")

    FLAG_READ    = 1 << 0  # 0001 (0x01)
    FLAG_WRITE   = 1 << 1  # 0010 (0x02)
    FLAG_EXECUTE = 1 << 2  # 0100 (0x04)
    FLAG_LOCKED  = 1 << 3  # 1000 (0x08)

    permission_reg = 0
    print(f"Register Inisial: 0x{permission_reg:02X} [{format_bits(permission_reg, 8)}]")

    # Set READ dan WRITE
    permission_reg |= (FLAG_READ | FLAG_WRITE)
    print(f"{GREEN}+ Set READ & WRITE:{RESET} 0x{permission_reg:02X} [{format_bits(permission_reg, 8)}]")

    # Cek izin EXECUTE
    has_exec = (permission_reg & FLAG_EXECUTE) != 0
    print(f"{BLUE}? Cek FLAG_EXECUTE:{RESET} {'AKTIF' if has_exec else 'TIDAK AKTIF'}")

    # Toggle EXECUTE
    permission_reg ^= FLAG_EXECUTE
    print(f"{YELLOW}^ Toggle EXECUTE:{RESET}   0x{permission_reg:02X} [{format_bits(permission_reg, 8)}]")

    # Clear WRITE
    permission_reg &= ~FLAG_WRITE
    print(f"{RED}- Clear WRITE:{RESET}      0x{permission_reg:02X} [{format_bits(permission_reg, 8)}]")


def demo_ieee754_float() -> None:
    header("4. Representasi IEEE-754 Single Precision Floating Point (32-bit)")
    test_floats = [0.0, 1.0, -1.0, 3.1415927, -42.5, 0.1]

    for val in test_floats:
        # Pack float sebagai 4 byte IEEE-754 (big endian untuk urutan bit standar)
        packed = struct.pack(">f", val)
        int_bits = struct.unpack(">I", packed)[0]
        bit_str = bin(int_bits)[2:].zfill(32)

        sign = bit_str[0]
        exponent = bit_str[1:9]
        mantissa = bit_str[9:]

        sign_val = -1 if sign == '1' else 1
        exp_int = int(exponent, 2)
        biased_exp = exp_int - 127

        print(f"\n{BOLD}Float: {val}{RESET} (Hex: 0x{int_bits:08X})")
        print(f"Raw 32-bit : {sign} {exponent} {mantissa}")
        print(f"Breakdown  : Sign={RED}{sign}{RESET} ({'+' if sign=='0' else '-'}) | "
              f"Exp={YELLOW}{exponent}{RESET} (raw={exp_int}, bias 127 -> {biased_exp}) | "
              f"Mantissa={GREEN}{mantissa[:8]}...{RESET}")


def demo_endianness() -> None:
    header("5. Endianness Memori: Little-Endian vs Big-Endian")
    val32 = 0xA1B2C3D4
    print(f"Integer 32-bit: {BOLD}0x{val32:08X}{RESET}\n")

    le_bytes = struct.pack("<I", val32)
    be_bytes = struct.pack(">I", val32)

    print(f"{CYAN}Little-Endian (x86_64 / ARM default):{RESET}")
    print(" Alamat Rendah -> Alamat Tinggi")
    for i, b in enumerate(le_bytes):
        print(f"  [Byte {i}] @ 0x{i:02X}: {GREEN}0x{b:02X}{RESET} ({format_bits(b, 8)})")

    print(f"\n{MAGENTA}Big-Endian (Network Byte Order):{RESET}")
    print(" Alamat Rendah -> Alamat Tinggi")
    for i, b in enumerate(be_bytes):
        print(f"  [Byte {i}] @ 0x{i:02X}: {YELLOW}0x{b:02X}{RESET} ({format_bits(b, 8)})")


def interactive_menu() -> None:
    """Menu interaktif jika dijalankan dalam terminal TTY langsung."""
    while True:
        print(f"\n{BOLD}{BG_BLUE} === SIMULATOR TIPE DATA & BIT ARITMETIKA C (BAB-02) === {RESET}")
        print(f"{WHITE}1.{RESET} Two's Complement & Integer Wrap-around")
        print(f"{WHITE}2.{RESET} Operasi Bitwise Dasar")
        print(f"{WHITE}3.{RESET} Bitmasking & Flag Status Register")
        print(f"{WHITE}4.{RESET} IEEE-754 Single Precision Float (32-bit)")
        print(f"{WHITE}5.{RESET} Inspeksi Endianness Memori")
        print(f"{WHITE}6.{RESET} Jalankan Seluruh Demonstrasi (Batch Mode)")
        print(f"{WHITE}0.{RESET} Keluar")
        
        choice = input(f"\n{BOLD}Pilih opsi [0-6]: {RESET}").strip()
        if choice == "1":
            demo_twos_complement_and_overflow()
        elif choice == "2":
            demo_bitwise_operations()
        elif choice == "3":
            demo_bitmask_flags()
        elif choice == "4":
            demo_ieee754_float()
        elif choice == "5":
            demo_endianness()
        elif choice == "6":
            run_all_demos()
        elif choice == "0":
            print(f"{GREEN}Selesai. Eksplorasi bit tuntas!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")


def run_all_demos() -> None:
    demo_twos_complement_and_overflow()
    demo_bitwise_operations()
    demo_bitmask_flags()
    demo_ieee754_float()
    demo_endianness()


def main() -> None:
    # Jika dijalankan secara non-interaktif atau dengan argumen, jalankan batch mode
    if len(sys.argv) > 1 or not sys.stdin.isatty():
        run_all_demos()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
