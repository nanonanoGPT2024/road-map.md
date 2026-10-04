#!/usr/bin/env python3
"""
Lab: Rekayasa Software Defensif, Hardening, & Undefined Behavior (C Runtime Emulation)
Lead Systems Engineering Module: Memory Sanitizers, Stack Canaries, and Safe Arithmetic.

Script ini memodelkan mekanisme proteksi tingkat rendah (low-level mitigation):
1. AddressSanitizer (ASan) Shadow Memory: Redzones, Poisoning, Use-After-Free, OOB.
2. Stack Smashing Protector (-fstack-protector-strong): Random Canary Validation.
3. Strict Overflow Checking: Deteksi Undefined Behavior pada Signed Integer Overflow.
"""

import sys
import struct
import secrets
from typing import Dict, Optional, Tuple

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_RED   = "\033[1;31m"
CLR_GREEN = "\033[1;32m"
CLR_YELLOW= "\033[1;33m"
CLR_CYAN  = "\033[1;36m"
CLR_MAGENTA = "\033[1;35m"
CLR_GRAY  = "\033[0;90m"
CLR_WHITE = "\033[1;37m"

def log_header(title: str) -> None:
    print(f"\n{CLR_CYAN}{'='*75}{CLR_RESET}")
    print(f"{CLR_WHITE}[+] {title}{CLR_RESET}")
    print(f"{CLR_CYAN}{'='*75}{CLR_RESET}")

def log_alert(level: str, msg: str) -> None:
    badge = {
        "INFO": f"{CLR_CYAN}[INFO]{CLR_RESET}",
        "WARN": f"{CLR_YELLOW}[WARN]{CLR_RESET}",
        "FATAL": f"{CLR_RED}[FATAL / UB]{CLR_RESET}",
        "HARDENED": f"{CLR_GREEN}[MITIGATION]{CLR_RESET}",
    }.get(level, "[*]")
    print(f"  {badge} {msg}")


# ==============================================================================
# MODUL 1: SAFE INTEGER ARITHMETIC ENGINE (C99/C11 DEFENSIVE ENGINEERING)
# ==============================================================================
class DefensiveArithmetic:
    """
    Mensimulasikan perbedaan Signed Integer Overflow (Undefined Behavior di C)
    dan hardened arithmetic check (seperti GCC/Clang __builtin_add_overflow).
    """
    INT32_MAX = 0x7FFFFFFF
    INT32_MIN = -0x80000000

    @staticmethod
    def c_unsafe_add(a: int, b: int) -> Tuple[int, bool]:
        """
        Di C, signed overflow adalah Undefined Behavior (UB). Kompiler sering kali
        mengoptimasi 'a + b < a' menjadi 'false' karena mengasumsikan overflow mustahil.
        """
        raw = a + b
        # Simulasi wrapping 32-bit hardware register
        wrapped = ((raw + 0x80000000) % 0x100000000) - 0x80000000
        # Compiler UB assumption: Compiler berasumsi tidak ada overflow,
        # sehingga logic security check bisa dihapus oleh optimasi -O2/-O3!
        ub_triggered = (raw > DefensiveArithmetic.INT32_MAX) or (raw < DefensiveArithmetic.INT32_MIN)
        return wrapped, ub_triggered

    @staticmethod
    def hardened_add(a: int, b: int) -> Tuple[Optional[int], bool]:
        """
        Pattern defensif sesuai CERT-C: INT32-C.
        Memverifikasi batas sebelum operasi hardware dilakukan.
        """
        if (b > 0 and a > (DefensiveArithmetic.INT32_MAX - b)) or \
           (b < 0 and a < (DefensiveArithmetic.INT32_MIN - b)):
            return None, False  # Overflow dicegah secara deterministik
        return a + b, True


# ==============================================================================
# MODUL 2: SHADOW MEMORY & HEAP SANITIZER (ASan SIMULATION)
# ==============================================================================
class ShadowMemoryAllocator:
    """
    Simulasi AddressSanitizer (ASan).
    Tiap blok heap dipisahkan oleh Redzone (Poisoned Memory).
    Ketika memori di-free, blok diubah menjadi Quarantined/Dead zone untuk UAF.
    """
    REDZONE_SIZE = 16
    TAG_VALID = 0x00
    TAG_REDZONE = 0xFA
    TAG_FREED = 0xFD

    def __init__(self, memory_pool_size: int = 1024):
        self.pool_size = memory_pool_size
        self.memory = bytearray(memory_pool_size)
        self.shadow_map: Dict[int, int] = {i: self.TAG_REDZONE for i in range(memory_pool_size)}
        self.allocations: Dict[int, int] = {}  # ptr -> size
        self.free_offset = self.REDZONE_SIZE

    def malloc(self, size: int) -> int:
        req_size = size + (8 - (size % 8)) if size % 8 != 0 else size
        ptr = self.free_offset
        limit = ptr + req_size + self.REDZONE_SIZE

        if limit > self.pool_size:
            raise MemoryError("Virtual Heap Exhausted")

        # Set memory valid
        for i in range(ptr, ptr + size):
            self.shadow_map[i] = self.TAG_VALID

        # Sisa alignment dan right redzone dipoison
        for i in range(ptr + size, limit):
            self.shadow_map[i] = self.TAG_REDZONE

        self.allocations[ptr] = size
        self.free_offset = limit
        return ptr

    def free(self, ptr: int) -> None:
        if ptr not in self.allocations:
            if ptr in self.shadow_map and self.shadow_map[ptr] == self.TAG_FREED:
                log_alert("FATAL", f"Double Free terdeteksi pada pointer 0x{ptr:08X}!")
                return
            log_alert("FATAL", f"Invalid Free / Pointer tak terdaftar: 0x{ptr:08X}")
            return

        size = self.allocations.pop(ptr)
        # Karantina blok dan poison dengan TAG_FREED
        for i in range(ptr, ptr + size):
            self.shadow_map[i] = self.TAG_FREED
        log_alert("HARDENED", f"Blok 0x{ptr:08X} ({size} bytes) masuk karantina (Use-After-Free trap dipasang).")

    def write(self, ptr: int, offset: int, data: bytes) -> bool:
        target_addr = ptr + offset
        for idx in range(target_addr, target_addr + len(data)):
            tag = self.shadow_map.get(idx, self.TAG_REDZONE)
            if tag == self.TAG_REDZONE:
                log_alert("FATAL", f"ASan Violation: Heap Buffer Overflow (Out-of-Bounds write) pada 0x{idx:08X}!")
                return False
            elif tag == self.TAG_FREED:
                log_alert("FATAL", f"ASan Violation: Use-After-Free (Write pada poisoned byte 0x{idx:08X})!")
                return False

        self.memory[target_addr : target_addr + len(data)] = data
        return True


# ==============================================================================
# MODUL 3: STACK FRAME HARDENING (-fstack-protector-strong)
# ==============================================================================
class HardenedStackFrame:
    """
    Simulasi stack frame x86_64 dengan random Stack Canary.
    Buffer -> Canary Guard -> Saved Frame Pointer -> Return Address.
    """
    def __init__(self, buffer_size: int, func_name: str):
        self.func_name = func_name
        self.buffer_size = buffer_size
        self.stack_canary = secrets.token_bytes(8)
        self.saved_rip = 0x00007FFF5FC0FFEE.to_bytes(8, byteorder='little')
        
        # Inisialisasi frame: [BUFFER] + [CANARY] + [SAVED_RIP]
        self.raw_stack = bytearray(buffer_size + 8 + 8)
        # Pasang canary di akhir buffer lokal
        self.canary_offset = buffer_size
        self.rip_offset = buffer_size + 8
        self.raw_stack[self.canary_offset : self.canary_offset + 8] = self.stack_canary
        self.raw_stack[self.rip_offset : self.rip_offset + 8] = self.saved_rip

    def unsafe_strcpy(self, input_payload: bytes) -> None:
        """Mensimulasikan fungsi strcpy() rentan tanpa boundary checking"""
        log_alert("INFO", f"Eksekusi fungsi {self.func_name}() | Menerima payload {len(input_payload)} byte.")
        limit = min(len(input_payload), len(self.raw_stack))
        self.raw_stack[0:limit] = input_payload[0:limit]

    def epilogue_and_return(self) -> bool:
        """
        Prologue/Epilogue Compiler check: __stack_chk_fail jika canary rusak.
        """
        current_canary = self.raw_stack[self.canary_offset : self.canary_offset + 8]
        if current_canary != self.stack_canary:
            log_alert("FATAL", f"*** STACK SMASHING DETECTED *** in '{self.func_name}()'")
            log_alert("FATAL", f"Canary rusak! Nilai awal: {self.stack_canary.hex()} | Nilai saat ini: {current_canary.hex()}")
            log_alert("HARDENED", "Sinyal SIGABRT dipicu. Eksekusi program dihentikan seketika untuk mencegah hijack RIP.")
            return False
        
        rip = int.from_bytes(self.raw_stack[self.rip_offset : self.rip_offset + 8], byteorder='little')
        log_alert("INFO", f"Canary Intak [{current_canary.hex()}]. Return Address valid: 0x{rip:016X}. Return sukses.")
        return True


# ==============================================================================
# PIPELINE DEMONSTRASI & PENGUJIAN DEFENSIVE SOFTWARE
# ==============================================================================
def main():
    print(f"{CLR_MAGENTA}RUNTIME HARDENING & UNDEFINED BEHAVIOR LAB ENGINE{CLR_RESET}")
    print(f"{CLR_GRAY}Model Simulasi Sistem: Linux x86_64 Kernel ABI & Defensive Toolchain{CLR_RESET}")

    # --------------------------------------------------------------------------
    # SCENARIO 1: Signed Integer Overflow vs Safe Hardened Arithmetic
    # --------------------------------------------------------------------------
    log_header("SKENARIO 1: Signed Integer Overflow (Undefined Behavior) vs Defensive Math")
    val_a = DefensiveArithmetic.INT32_MAX
    val_b = 100

    print(f"  Konfigurasi Input: a = {val_a} (0x7FFFFFFF / INT32_MAX), b = {val_b}")
    
    # 1.1 Unsafe execution (C standard UB)
    wrapped_res, is_ub = DefensiveArithmetic.c_unsafe_add(val_a, val_b)
    log_alert("WARN", f"Unsafe C add: Result = {wrapped_res} (Wraparound ke negatif).")
    if is_ub:
        log_alert("FATAL", "Undefined Behavior (UB) aktif! Pengujian optimasi -O3 dapat menghapus batasan validasi.")

    # 1.2 Hardened execution
    safe_res, ok = DefensiveArithmetic.hardened_add(val_a, val_b)
    if not ok:
        log_alert("HARDENED", "Operasi dibatalkan sebelum CPU arithmetic trap. Return status: ERANGE/EOVERFLOW.")
    else:
        log_alert("INFO", f"Hasil aman didapatkan: {safe_res}")

    # --------------------------------------------------------------------------
    # SCENARIO 2: Stack Smashing Protection (-fstack-protector-strong)
    # --------------------------------------------------------------------------
    log_header("SKENARIO 2: Stack Smashing Protection & Canary Validation")
    
    # Kasus A: Normal Stack Write (Aman)
    print(f"{CLR_WHITE}[Kasus A: Buffer Normal Safe Write]{CLR_RESET}")
    frame_safe = HardenedStackFrame(buffer_size=16, func_name="process_user_token")
    frame_safe.unsafe_strcpy(b"AUTH_OK_12345")
    frame_safe.epilogue_and_return()

    # Kasus B: Buffer Overflow menyerang Canary & RIP
    print(f"\n{CLR_WHITE}[Kasus B: Malicious Overflow Melebihi Batas Buffer (Attack Exploit)]{CLR_RESET}")
    frame_exploit = HardenedStackFrame(buffer_size=16, func_name="vulnerable_auth_handler")
    # Payload: 16 bytes buffer filler + 8 bytes canary overwrite + 8 bytes hijacker RIP
    malicious_payload = b"A" * 16 + b"\xDE\xAD\xBE\xEF\xCA\xFE\xBA\xBE" + struct.pack("<Q", 0x00001337C0DED00D)
    frame_exploit.unsafe_strcpy(malicious_payload)
    frame_exploit.epilogue_and_return()

    # --------------------------------------------------------------------------
    # SCENARIO 3: AddressSanitizer (ASan) Memory Redzones & Use-After-Free
    # --------------------------------------------------------------------------
    log_header("SKENARIO 3: Heap Redzones & Use-After-Free (UAF) Sanitizer")
    heap = ShadowMemoryAllocator(memory_pool_size=256)

    # 3.1 Alokasi memori
    ptr1 = heap.malloc(size=24)
    log_alert("INFO", f"Allocated 24 bytes pada 0x{ptr1:08X} (Dikelilingi Redzone poisoned bytes).")

    # 3.2 Out-of-Bounds Write
    print(f"\n{CLR_WHITE}[Uji OOB: Menulis melebihi 24 byte yang dialokasikan]{CLR_RESET}")
    oob_data = b"X" * 32
    success = heap.write(ptr1, offset=0, data=oob_data)
    if not success:
        log_alert("HARDENED", "Write diblokir oleh ASan Shadow Memory boundary checker!")

    # 3.3 Free dan UAF detection
    print(f"\n{CLR_WHITE}[Uji UAF: Membaca/Menulis pointer setelah free()]{CLR_RESET}")
    heap.free(ptr1)
    
    # Mencoba menulis setelah di-free
    log_alert("INFO", "Mencoba menulis ke pointer lama yang telah dilepas (dangling pointer)...")
    uaf_success = heap.write(ptr1, offset=0, data=b"EXPLOIT_WRITE")
    if not uaf_success:
        log_alert("HARDENED", "UAF ditolak seketika! Eksploitasi Memory Corruption berhasil digagalkan.")

    # 3.4 Double Free detection
    print(f"\n{CLR_WHITE}[Uji Double-Free: Memanggil free() kedua kali pada pointer yang sama]{CLR_RESET}")
    heap.free(ptr1)

    print(f"\n{CLR_GREEN}[+] Semua simulasi hardening defensif berhasil dieksekusi.{CLR_RESET}\n")

if __name__ == "__main__":
    main()