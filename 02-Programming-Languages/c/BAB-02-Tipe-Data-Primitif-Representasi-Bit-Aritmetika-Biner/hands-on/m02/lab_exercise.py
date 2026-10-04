#!/usr/bin/env python3
"""
Lab Hands-on: C Primitive Data Types, Bit Representation, & Binary Arithmetic
Deep-dive engine simulating C-level fixed-width types, two's complement overflows,
IEEE-754 single-precision float dissection, and low-level endianness/bitfield packing.
"""

import struct
import sys
import math

# ==============================================================================
# ANSI Color Formatting Helper
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    DIM     = "\033[2m"


def header(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 78}")
    print(f" [*] {title}")
    print(f"{'=' * 78}{Color.RESET}")


def subheader(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.YELLOW}--- {title} ---{Color.RESET}")


# ==============================================================================
# 1. FIXED-WIDTH C INTEGER & ARITHMETIC EMULATOR
# ==============================================================================
class CInteger:
    """
    Simulates fixed-width integer behavior in C (signed & unsigned).
    Handles modular arithmetic, two's complement sign-extension, and overflows.
    """
    def __init__(self, bits: int, signed: bool, value: int = 0):
        self.bits = bits
        self.signed = signed
        self.mask = (1 << bits) - 1
        self.sign_bit = 1 << (bits - 1)
        self.min_val = -(1 << (bits - 1)) if signed else 0
        self.max_val = (1 << (bits - 1)) - 1 if signed else self.mask
        self.raw = 0
        self.set(value)

    def set(self, value: int) -> None:
        """Stores value truncated to fixed-width bitmask."""
        self.raw = value & self.mask

    @property
    def value(self) -> int:
        """Decodes raw bits into signed/unsigned integer interpretation."""
        if not self.signed:
            return self.raw
        # Two's complement conversion
        if self.raw & self.sign_bit:
            return self.raw - (1 << self.bits)
        return self.raw

    def add(self, other: int) -> tuple[int, bool]:
        """
        Performs binary addition with overflow detection.
        Returns: (resulting_value, overflow_flag)
        """
        prev = self.value
        raw_res = (self.raw + (other & self.mask)) & self.mask
        self.raw = raw_res
        curr = self.value
        
        # In C, signed overflow is technically undefined behavior (UB),
        # but x86/ARM hardware wraps according to two's complement rules.
        overflow = False
        if self.signed:
            # Overflow occurs if signs of operands match but differ from result
            a_neg = prev < 0
            b_neg = other < 0
            res_neg = curr < 0
            if (a_neg == b_neg) and (a_neg != res_neg):
                overflow = True
        else:
            # Unsigned overflow occurs on modular wrap-around
            if curr < prev:
                overflow = True
        return curr, overflow

    def to_binary(self) -> str:
        """Returns binary string representation formatted with nibble spaces."""
        raw_bin = f"{self.raw:0{self.bits}b}"
        nibbles = [raw_bin[max(i - 4, 0):i] for i in range(len(raw_bin), 0, -4)][::-1]
        return " ".join(nibbles)


def demo_integer_arithmetic():
    header("1. C INTEGER TYPES & TWO'S COMPLEMENT OVERFLOW SIMULATION")
    
    # Showcase uint8_t overflow
    u8 = CInteger(bits=8, signed=False, value=250)
    print(f"{Color.BOLD}Target Type: uint8_t [Range: 0 to 255]{Color.RESET}")
    print(f"Initial: {u8.value:4d} | Binary: {Color.GREEN}{u8.to_binary()}{Color.RESET}")
    for _ in range(7):
        val, ovf = u8.add(1)
        ovf_str = f"{Color.RED}[OVERFLOW/WRAP]{Color.RESET}" if ovf else ""
        print(f"  +1 ->  {val:4d} | Binary: {Color.GREEN}{u8.to_binary()}{Color.RESET} {ovf_str}")

    # Showcase int8_t overflow (Two's complement wrap: 127 + 1 -> -128)
    s8 = CInteger(bits=8, signed=True, value=125)
    print(f"\n{Color.BOLD}Target Type: int8_t [Range: -128 to 127]{Color.RESET}")
    print(f"Initial: {s8.value:4d} | Binary: {Color.MAGENTA}{s8.to_binary()}{Color.RESET}")
    for _ in range(5):
        val, ovf = s8.add(1)
        ovf_str = f"{Color.RED}[UB/HARDWARE WRAP]{Color.RESET}" if ovf else ""
        print(f"  +1 ->  {val:4d} | Binary: {Color.MAGENTA}{s8.to_binary()}{Color.RESET} {ovf_str}")


# ==============================================================================
# 2. IEEE-754 SINGLE PRECISION (32-BIT FLOAT) DECOMPOSER
# ==============================================================================
def dissect_float32(value: float) -> None:
    """
    Deconstructs a Python float as an IEEE-754 32-bit single-precision float (C float).
    Displays Sign (1b), Exponent (8b), and Fraction/Mantissa (23b).
    """
    # Pack into raw IEEE-754 bytes, then re-read as uint32
    packed = struct.pack(">f", value)
    uint_rep = struct.unpack(">I", packed)[0]

    sign_bit = (uint_rep >> 31) & 0x1
    exp_bits = (uint_rep >> 23) & 0xFF
    mantissa_bits = uint_rep & 0x7FFFFF

    sign_str = f"{sign_bit:01b}"
    exp_str = f"{exp_bits:08b}"
    mant_str = f"{mantissa_bits:023b}"

    # IEEE-754 Exponent Bias = 127
    bias = 127
    actual_exp = exp_bits - bias

    # Calculate decoded mantissa value
    if exp_bits == 0:
        category = "Subnormal (Denormalized)"
        implied_mantissa = 0.0
        significand = mantissa_bits / (1 << 23)
        calculated_val = ((-1) ** sign_bit) * (2 ** (-126)) * significand
    elif exp_bits == 0xFF:
        category = "Special (NaN or Infinity)"
        calculated_val = float('nan') if mantissa_bits != 0 else (float('-inf') if sign_bit else float('inf'))
    else:
        category = "Normalized"
        implied_mantissa = 1.0
        significand = implied_mantissa + (mantissa_bits / (1 << 23))
        calculated_val = ((-1) ** sign_bit) * (2 ** actual_exp) * significand

    print(f"\nDissecting C `float`: {Color.BOLD}{value}{Color.RESET} (Type Category: {category})")
    print(f" Raw Hex       : 0x{uint_rep:08X}")
    print(f" Bit Breakdown : [{Color.RED}{sign_str}{Color.RESET}] "
          f"[{Color.GREEN}{exp_str}{Color.RESET}] "
          f"[{Color.CYAN}{mant_str}{Color.RESET}]")
    print(f"                 S(1)     Exp(8)          Mantissa(23)")
    print(f" Sign          : {sign_bit} ({'-' if sign_bit else '+'})")
    print(f" Exponent Bits : {exp_bits} (Biased), Unbiased = {exp_bits} - {bias} = {actual_exp}")
    print(f" Mantissa Bits : 0x{mantissa_bits:06X} -> Significand = {significand:.8f}")
    print(f" Decoded Reval : {calculated_val:.8e}")


def demo_ieee754():
    header("2. IEEE-754 FLOATING POINT BIT-LEVEL DECOMPOSITION (float32)")
    test_floats = [12.375, -0.15625, 0.0, -1.0, 1e-40]
    for tf in test_floats:
        dissect_float32(tf)


# ==============================================================================
# 3. BITFIELD PACKING & ENDIANNESS ENGINE
# ==============================================================================
def pack_rgb565(r: int, g: int, b: int) -> int:
    """
    Packs 8-bit RGB components into a single 16-bit RGB565 integer.
    Bit Layout: RRRRRGGG GGGBBBBB
    """
    r5 = (r >> 3) & 0x1F  # 5 bits
    g6 = (g >> 2) & 0x3F  # 6 bits
    b5 = (b >> 3) & 0x1F  # 5 bits
    return (r5 << 11) | (g6 << 5) | b5


def unpack_rgb565(packed: int) -> tuple[int, int, int]:
    """Unpacks a 16-bit RGB565 value back to standard 8-bit components."""
    r5 = (packed >> 11) & 0x1F
    g6 = (packed >> 5) & 0x3F
    b5 = packed & 0x1F

    # Scale back to 8-bit [0-255]
    r = (r5 * 255) // 31
    g = (g6 * 255) // 63
    b = (b5 * 255) // 31
    return r, g, b


def demo_bitfields_and_endianness():
    header("3. LOW-LEVEL BITFIELD PACKING (RGB565) & ENDIANNESS")
    
    # 1. Bitfield packing demo
    orig_r, orig_g, orig_b = 220, 140, 75
    packed = pack_rgb565(orig_r, orig_g, orig_b)
    unpacked_r, unpacked_g, unpacked_b = unpack_rgb565(packed)

    print(f"Original 24-bit RGB : R={orig_r}, G={orig_g}, B={orig_b}")
    print(f"Packed 16-bit RGB565: 0x{packed:04X} | Binary: {packed:016b}")
    print(f"Unpacked Reconstructed: R={unpacked_r}, G={unpacked_g}, B={unpacked_b}")
    print(f"{Color.DIM}(Precision loss occurs due to 8-bit -> 5/6-bit truncation){Color.RESET}")

    # 2. Endianness transformation
    subheader("Endianness Memory Inspection (uint32_t = 0xA1B2C3D4)")
    val32 = 0xA1B2C3D4

    # Pack in Little Endian (x86_64, ARM default)
    le_bytes = struct.pack("<I", val32)
    # Pack in Big Endian (Network Byte Order)
    be_bytes = struct.pack(">I", val32)

    def format_bytes(byte_data: bytes) -> str:
        return " ".join(f"[{Color.GREEN}0x{b:02X}{Color.RESET}]" for b in byte_data)

    print(f"Memory Layout - Little-Endian (<I): {format_bytes(le_bytes)} (LSB at lowest addr)")
    print(f"Memory Layout - Big-Endian    (>I): {format_bytes(be_bytes)} (MSB at lowest addr)")

    # Bitwise manual byte-swap implementation (C-style ntohl / htonl)
    swapped = (
        ((val32 & 0x000000FF) << 24) |
        ((val32 & 0x0000FF00) << 8)  |
        ((val32 & 0x00FF0000) >> 8)  |
        ((val32 & 0xFF000000) >> 24)
    )
    print(f"Manual Bitwise Swap (__builtin_bswap32): 0x{val32:08X} -> {Color.BOLD}0x{swapped:08X}{Color.RESET}")
    assert swapped == struct.unpack(">I", le_bytes)[0], "Endian swap validation failed!"
    print(f"{Color.GREEN}✔ Endianness transformation validated successfully.{Color.RESET}")


# ==============================================================================
# ENTRY POINT
# ==============================================================================
def main():
    print(f"{Color.BOLD}{Color.WHITE}C FOUNDATIONS: PRIMITIVE TYPES, BIT REPRESENTATION & BINARY ARITHMETIC{Color.RESET}")
    print(f"System Architecture Word Size : {struct.calcsize('P') * 8}-bit")
    print(f"Native Byte Order             : {sys.byteorder.upper()}-ENDIAN")

    demo_integer_arithmetic()
    demo_ieee754()
    demo_bitfields_and_endianness()

    print(f"\n{Color.BOLD}{Color.GREEN}=== Lab Execution Finished Successfully ==={Color.RESET}\n")


if __name__ == "__main__":
    main()