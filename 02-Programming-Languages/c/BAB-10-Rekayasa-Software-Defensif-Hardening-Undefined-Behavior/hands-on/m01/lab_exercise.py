#!/usr/bin/env python3
"""
Lab Exercise: Rekayasa Software Defensif, Hardening, dan Mitigasi Undefined Behavior (C)
Simulator Interaktif Konsep Low-Level:
 1. Buffer Overflow & Stack Canary Simulation
 2. Integer Overflow / Signed Wrap Detection
 3. Use-After-Free (UAF) & Memory Poisoning (0xDEADBEEF)
 4. Compiler UB Exploitation & Optimization Hazards
 5. Hardening Suite (ASLR, NX, RELRO, Stack Canary Verification)
"""

import sys
import time
import struct
import random

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_RED = "\033[1;31m"
CLR_GREEN = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_BLUE = "\033[1;34m"
CLR_MAGENTA = "\033[1;35m"
CLR_CYAN = "\033[1;36m"
CLR_WHITE = "\033[1;37m"
CLR_BG_RED = "\033[41m\033[1;37m"
CLR_BG_GREEN = "\033[42m\033[1;37m"
CLR_DIM = "\033[2m"


def print_banner():
    banner = f"""{CLR_CYAN}
╔═══════════════════════════════════════════════════════════════════════════╗
║   LAB SIMULASI DEFENSIVE C & HARDENING (BAB 10: UNDEFINED BEHAVIOR)      ║
║   Memory Safety, Sanitizer Internals, and Exploit Mitigations             ║
╚═══════════════════════════════════════════════════════════════════════════╝{CLR_RESET}"""
    print(banner)


def section_header(title: str):
    print(f"\n{CLR_MAGENTA}═══ [MODUL: {title}] ═══{CLR_RESET}\n")


def simulate_stack_canary():
    section_header("1. Buffer Overflow & Stack Canary Hardening")
    print(f"{CLR_WHITE}Skenario:{CLR_RESET} Fungsi vulnerable dengan buffer lokal 16 byte.")
    print(f"Layout Stack Frame (x86_64 visualizer):")
    print(f" [Local Buffer (16B)] | [Canary (8B)] | [Saved RBP (8B)] | [Saved RIP (8B)]\n")

    canary_val = 0x59A2F180DEADBEEF
    saved_rbp = 0x7FFE_EBAD_1100
    saved_rip = 0x0040_1337_0000

    print(f"{CLR_BLUE}[INIT]{CLR_RESET} Generated Random Canary: {CLR_YELLOW}{hex(canary_val)}{CLR_RESET}")
    user_payload = input(f"{CLR_CYAN}Ketik string input untuk buffer (default 'A'*24): {CLR_RESET}").strip()
    if not user_payload:
        user_payload = "A" * 24

    payload_bytes = user_payload.encode("utf-8")
    buffer_capacity = 16
    written_len = len(payload_bytes)

    print(f"\n{CLR_WHITE}Menulis {written_len} bytes ke buffer 16 bytes...{CLR_RESET}")
    time.sleep(0.4)

    # Memory state representation
    corrupted_canary = canary_val
    if written_len > buffer_capacity:
        overflow_len = written_len - buffer_capacity
        overflow_bytes = payload_bytes[buffer_capacity:buffer_capacity + 8]
        # Pad with 0s if shorter than 8
        overflow_bytes = overflow_bytes.ljust(8, b"\x00")
        corrupted_canary = struct.unpack("<Q", overflow_bytes)[0]

    print(f"\nMemory Inspection:")
    print(f" -> Buffer (0..15)     : {CLR_GREEN}{payload_bytes[:16]!r}{CLR_RESET}")
    
    if corrupted_canary != canary_val:
        print(f" -> Canary Value       : {CLR_BG_RED} 0x{corrupted_canary:016X} (CORRUPTED!) {CLR_RESET}")
        print(f" -> Expected Canary    : {CLR_GREEN}0x{canary_val:016X}{CLR_RESET}")
        print(f"\n{CLR_RED}[!] STACK SMASHING DETECTED! *** stack smashing detected ***: terminated{CLR_RESET}")
        print(f"{CLR_YELLOW}[DEFENSIF] __stack_chk_fail() dipicu sebelum Saved RIP dieksekusi. Exploit RCE digagalkan!{CLR_RESET}")
    else:
        print(f" -> Canary Value       : {CLR_BG_GREEN} 0x{canary_val:016X} (INTACT) {CLR_RESET}")
        print(f" -> Saved RBP          : 0x{saved_rbp:016X}")
        print(f" -> Saved RIP          : 0x{saved_rip:016X}")
        print(f"{CLR_GREEN}[+] Tidak ada deteksi overflow pada Canary. Fungsi kembali dengan aman.{CLR_RESET}")


def simulate_integer_overflow():
    section_header("2. Integer Overflow & Signed Wrap Undefined Behavior")
    print(f"{CLR_WHITE}Di C Standard (C99/C11/C23 §6.5): Signed Integer Overflow adalah UNDEFINED BEHAVIOR.{CLR_RESET}")
    print(f"Kompiler (GCC/Clang -O2/-O3) berhak menganggap `x + 1 > x` selalu TRUE dan menghapus boundary check!\n")

    INT32_MAX = 2147483647
    INT32_MIN = -2147483648

    print(f"Status: INT32_MAX = {CLR_YELLOW}{INT32_MAX}{CLR_RESET}")
    user_add = input(f"{CLR_CYAN}Masukkan nilai integer positif untuk ditambahkan ke INT32_MAX (default 1): {CLR_RESET}").strip()
    try:
        delta = int(user_add) if user_add else 1
    except ValueError:
        delta = 1

    # C naive simulation (simulate 32-bit hardware wrap)
    naive_result = struct.unpack("<i", struct.pack("<I", (INT32_MAX + delta) & 0xFFFFFFFF))[0]
    
    print(f"\n{CLR_WHITE}[Eksperimen Hardware & Kompiler]:{CLR_RESET}")
    print(f"Operasi: {INT32_MAX} + {delta}")
    print(f"Hasil Naive Wrap (Two's Complement 32-bit): {CLR_RED}{naive_result}{CLR_RESET}")

    # Defensive check implementation
    print(f"\n{CLR_WHITE}[Defensive Precondition Check (Safe Math Pattern)]:{CLR_RESET}")
    print(f"Code: `if (a > INT_MAX - b) {{ /* handle error */ }}`")
    
    if delta > (INT32_MAX - INT32_MAX):  # if delta > 0 when adding to INT32_MAX
        print(f"{CLR_GREEN}[SAFEGUARD TRIGGERED]{CLR_RESET} Overflow terdeteksi sebelum eksekusi:")
        print(f" -> Kondisi: delta ({delta}) > (INT32_MAX - {INT32_MAX})")
        print(f" -> Tindakan: Tolak alokasi / return EOVERFLOW / abort.")
    else:
        print(f"{CLR_GREEN}[OK]{CLR_RESET} Operasi aman dalam rentang 32-bit.")

    print(f"\n{CLR_YELLOW}[Catatan Hardening]: Gunakan compiler flag `-fsanitize=signed-integer-overflow` dan `-fwrapv` jika wrap didefinisikan secara eksplisit.{CLR_RESET}")


def simulate_use_after_free():
    section_header("3. Use-After-Free (UAF) & Memory Poisoning")
    print(f"{CLR_WHITE}Mekanisme alokasi heap simulasi dengan tracking pointer dan sanitasi free().{CLR_RESET}\n")

    heap_chunks = {}
    
    def alloc_chunk(chunk_id: int, content: str):
        heap_chunks[chunk_id] = {
            "status": "ALLOCATED",
            "address": 0x5555_0010 + (chunk_id * 0x40),
            "payload": content.encode("utf-8")
        }
        return heap_chunks[chunk_id]

    chunk = alloc_chunk(1, "AUTH_TOKEN_SECRET_9999")
    print(f"{CLR_GREEN}[MALLOC]{CLR_RESET} Allocated chunk at {hex(chunk['address'])}: {chunk['payload']!r}")

    # Free with and without poisoning
    use_hardening = input(f"{CLR_CYAN}Aktifkan pointer zeroing & memory poisoning? [y/N]: {CLR_RESET}").strip().lower() == 'y'

    print(f"\n{CLR_YELLOW}[FREE]{CLR_RESET} Melakukan free(ptr)...")
    if use_hardening:
        chunk["status"] = "FREED_POISONED"
        chunk["payload"] = b"\xDE\xAD\xBE\xEF" * (len(chunk["payload"]) // 4 + 1)
        ptr = None
        print(f"{CLR_GREEN}[HARDENED FREE]{CLR_RESET} Memory di-poison dengan 0xDEADBEEF dan pointer di-set ke NULL.")
    else:
        chunk["status"] = "FREED_DANGLING"
        ptr = chunk["address"]
        print(f"{CLR_RED}[INSECURE FREE]{CLR_RESET} Memory ditandai freed di allocator, tetapi pointer tetap menyimpan {hex(ptr)} (Dangling)!")

    time.sleep(0.3)
    print(f"\n{CLR_WHITE}[SIMULASI DEREFERENCE SETELAH FREE]{CLR_RESET}")
    if ptr is None:
        print(f"{CLR_GREEN}[PASS]{CLR_RESET} Mencoba dereference `*ptr` -> NULL Pointer Exception seketika (Segfault terprediksi, aman dari manipulasi attacker).")
    else:
        print(f"{CLR_BG_RED} [CRITICAL VULN] {CLR_RESET} Dangling pointer {hex(ptr)} dibaca:")
        print(f" -> Raw Memory: {chunk['payload']!r}")
        print(f" -> Attacker dapat menyuntikkan struct vtable baru pada alokasi berikutnya dan membajak kontrol alur (Control Flow Hijack)!")


def simulate_hardening_audit():
    section_header("4. Binary Hardening & Mitigations Audit Check")
    print(f"{CLR_WHITE}Menganalisis binary target flags (ASLR, Stack Canary, RELRO, NX bit):{CLR_RESET}\n")

    mitigations = [
        ("Stack Canary (-fstack-protector-strong)", True, "Melindungi overwrite return address pada stack frame."),
        ("NX / W^X (No-Execute Stack)", True, "Menandai halaman memori stack & heap sebagai non-executable."),
        ("PIE / Full ASLR (-fPIE -pie)", True, "Merandomisasi address space code, stack, mmap, dan heap."),
        ("Full RELRO (-Wl,-z,relro,-z,now)", True, "GOT (Global Offset Table) dijadikan read-only pasca-linking dinamis."),
        ("Fortify Source (-D_FORTIFY_SOURCE=3)", True, "Mengganti fungsi string berbahaya dengan bounded wrappers."),
        ("Control Flow Integrity (-fsanitize=cfi)", False, "Memvalidasi target indirect call/jump."),
    ]

    for name, status, desc in mitigations:
        status_badge = f"{CLR_BG_GREEN} ENABLED  {CLR_RESET}" if status else f"{CLR_BG_RED} DISABLED {CLR_RESET}"
        print(f" {status_badge} {CLR_WHITE}{name:<40}{CLR_RESET}")
        print(f"             {CLR_DIM}-> {desc}{CLR_RESET}")
        time.sleep(0.15)


def run_full_suite():
    print_banner()
    simulate_stack_canary()
    simulate_integer_overflow()
    simulate_use_after_free()
    simulate_hardening_audit()
    print(f"\n{CLR_GREEN}═══════════════════════════════════════════════════════════════════════════{CLR_RESET}")
    print(f"{CLR_CYAN}[SELESAI] Seluruh simulasi rekayasa defensif dan mitigasi UB berhasil dijalankan.{CLR_RESET}\n")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        # Non-interactive automated run
        print_banner()
        print(f"{CLR_YELLOW}[AUTO-DEMO MODE]{CLR_RESET}")
        section_header("1. Buffer Overflow & Stack Canary Hardening")
        canary = 0x59A2F180DEADBEEF
        print(f"Initial Canary: 0x{canary:016X}")
        print(f"Payload 24 bytes over 16B buffer -> Canary smashed!")
        print(f"{CLR_RED}[!] *** stack smashing detected ***: terminated{CLR_RESET}")

        section_header("2. Integer Overflow")
        print(f"INT32_MAX + 1 = {CLR_RED}-2147483648{CLR_RESET} (Signed wrap UB)")
        print(f"{CLR_GREEN}[DEFENSIVE]{CLR_RESET} Detected via precondition `delta > INT_MAX - base`")

        section_header("3. Use-After-Free")
        print(f"Pointers zeroed out upon free: {CLR_GREEN}SAFE (Immediate deterministic crash if used){CLR_RESET}")

        simulate_hardening_audit()
        return

    try:
        run_full_suite()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{CLR_YELLOW}\n[Interrupted] Keluar dari simulasi.{CLR_RESET}")


if __name__ == "__main__":
    main()
