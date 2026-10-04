#!/usr/bin/env python3
"""
Lab Hands-on: Aliran Kontrol, Stack Frame, & Rekursi Tingkat Assembly (C Architecture Deep Dive)
Kategori: 02-Programming-Languages / C - Bab 03

Skrip ini memodelkan eksekusi panggilan fungsi C tingkat rendah sesuai konvensi x86-64 System V AMD64 ABI:
- Alokasi memori Stack (tumbuh ke bawah: alamat tinggi -> alamat rendah)
- Register: RSP (Stack Pointer), RBP (Base/Frame Pointer), RAX (Return Register), RDI (Arg 1)
- Siklus Prologue (push rbp, mov rbp rsp, sub rsp N), Call, Epilogue (mov rsp rbp, pop rbp, ret)
- Rekursi, deteksi Stack Overflow, serta visualisasi layout frame memori mentah.
"""

import sys
import time
from typing import Dict, List, Optional, Tuple

# ANSI Colors
CLR_RST = "\033[0m"
CLR_RED = "\033[91m"
CLR_GRN = "\033[92m"
CLR_YEL = "\033[93m"
CLR_BLU = "\033[94m"
CLR_MAG = "\033[95m"
CLR_CYN = "\033[96m"
CLR_WHT = "\033[97m"
CLR_GRY = "\033[90m"
CLR_BOLD = "\033[1m"


class AssemblyStackMachine:
    """
    Simulator Stack Machine x86-64 yang memodelkan perilaku call stack,
    instruksi kendali aliran (call, ret, jle, jmp), dan activation records.
    """

    WORD_SIZE = 8  # 64-bit architecture (8 byte per quadword)
    STACK_BASE = 0x7FFF_FFFF_E000
    STACK_LIMIT = 0x7FFF_FFFF_C000  # Stack size limit ~8 KB (mencegah overflow tak terbatas)

    def __init__(self):
        # Register Hardware x86-64
        self.rsp: int = self.STACK_BASE  # Stack Pointer (points to top of stack)
        self.rbp: int = self.STACK_BASE  # Base/Frame Pointer
        self.rax: int = 0                # Return Accumulator
        self.rdi: int = 0                # 1st Function Argument (System V ABI)
        self.rip: int = 0x0040_0000      # Instruction Pointer

        # Memori virtual linear: Address (int) -> Data Word (int / pointer / str)
        self.memory: Dict[int, int] = {}
        self.symbol_table: Dict[int, str] = {
            0x0040_1000: "main",
            0x0040_1050: "factorial",
            0x0040_1080: "factorial.base_case",
            0x0040_10A0: "factorial.epilogue",
        }
        self.call_history: List[str] = []
        self.max_stack_depth = 0

    def push(self, value: int, label: str = "") -> None:
        """Instruksi PUSH: Mengurangi RSP sebesar 8 byte dan menulis nilai ke stack."""
        self.rsp -= self.WORD_SIZE
        if self.rsp <= self.STACK_LIMIT:
            raise RecursionError(
                f"{CLR_RED}[SIGSEGV] Stack Overflow Exception! RSP ({hex(self.rsp)}) < Guard Page ({hex(self.STACK_LIMIT)}){CLR_RST}"
            )
        self.memory[self.rsp] = value
        depth = (self.STACK_BASE - self.rsp) // self.WORD_SIZE
        if depth > self.max_stack_depth:
            self.max_stack_depth = depth

    def pop(self) -> int:
        """Instruksi POP: Membaca nilai dari [RSP] lalu menambah RSP sebesar 8 byte."""
        if self.rsp >= self.STACK_BASE:
            raise IndexError("Stack Underflow: Mencoba POP melebihi STACK_BASE!")
        val = self.memory.get(self.rsp, 0)
        self.rsp += self.WORD_SIZE
        return val

    def print_registers(self) -> None:
        """Menampilkan status register utama."""
        print(
            f"  {CLR_GRY}REGISTERS: {CLR_RST}"
            f"RSP={CLR_CYN}{hex(self.rsp)}{CLR_RST} | "
            f"RBP={CLR_MAG}{hex(self.rbp)}{CLR_RST} | "
            f"RAX={CLR_GRN}{self.rax}{CLR_RST} | "
            f"RDI={CLR_YEL}{self.rdi}{CLR_RST} | "
            f"RIP={CLR_BLU}{hex(self.rip)}{CLR_RST}"
        )

    def print_stack_layout(self, title: str = "STACK SNAPSHOT") -> None:
        """
        Visualisasi grafis struktur Call Stack Memory (dari STACK_BASE ke RSP).
        Menyoroti frame pointer (RBP), stack pointer (RSP), dan isi quadword.
        """
        print(f"\n{CLR_BOLD}--- {title} (Tumbuh: 0x7FFF_FFFF_E000 -> Bawah) ---{CLR_RST}")
        print(f"{'Address':<18} | {'Value (Hex / Dec)':<22} | {'Marker & Semantic Context'}")
        print("-" * 75)

        if self.rsp == self.STACK_BASE:
            print(f"  {CLR_GRY}[Stack Kosong - RSP == STACK_BASE]{CLR_RST}")
            return

        # Render dari alamat tinggi (STACK_BASE - 8) turun ke alamat rendah (RSP)
        addr = self.STACK_BASE - self.WORD_SIZE
        while addr >= self.rsp:
            val = self.memory.get(addr, 0)
            markers = []

            if addr == self.rbp:
                markers.append(f"{CLR_MAG}[RBP -> Saved Frame Pointer]{CLR_RST}")
            if addr == self.rsp:
                markers.append(f"{CLR_CYN}[RSP -> Stack Top]{CLR_RST}")

            # Interpretasi semantik word
            context = ""
            if val in self.symbol_table:
                context = f"RetAddr to <{self.symbol_table[val]}>"
            elif addr > self.rbp:
                context = "Parent Frame Caller Data"
            elif addr == self.rbp:
                context = f"Saved RBP (points to {hex(val)})"
            elif addr == self.rbp - 8:
                context = f"Local Var (n = {val})"
            else:
                context = f"Stack Data: {val}"

            val_str = f"{hex(val):<12} ({val})"
            marker_str = " ".join(markers)
            row_color = CLR_WHT
            if addr == self.rsp:
                row_color = CLR_CYN
            elif addr == self.rbp:
                row_color = CLR_MAG

            print(f"{row_color}{hex(addr):<18}{CLR_RST} | {val_str:<22} | {marker_str} {CLR_GRY}{context}{CLR_RST}")
            addr -= self.WORD_SIZE
        print("-" * 75)

    def simulate_c_factorial(self, n: int) -> int:
        """
        Simulasi eksekusi fungsi C Rekursif pada tingkat kode mesin:
        
        uint64_t factorial(uint64_t n) {
            // Prologue
            //   push rbp
            //   mov  rbp, rsp
            //   sub  rsp, 16
            //   mov  [rbp - 8], rdi
            if (n <= 1) return 1;
            return n * factorial(n - 1);
            // Epilogue
            //   mov  rsp, rbp
            //   pop  rbp
            //   ret
        }
        """
        print(f"\n{CLR_BLU}{CLR_BOLD}>>> MEMULAI EKSEKUSI: factorial({n}) <<<{CLR_RST}")
        self.rdi = n
        self.rip = 0x0040_1000  # Entry point main

        # Main memanggil factorial: `call 0x0040_1050`
        ret_addr_main = 0x0040_1020
        self.push(ret_addr_main, "Return address to main")
        self.rip = 0x0040_1050

        # Eksekusi fungsi rekursif
        result = self._asm_factorial_procedure()
        self.rax = result

        # Return ke main
        popped_ret = self.pop()
        assert popped_ret == ret_addr_main
        self.rip = ret_addr_main

        print(f"\n{CLR_GRN}{CLR_BOLD}>>> EKSEKUSI SELESAI. RAX (Hasil Akhir) = {self.rax} <<<{CLR_RST}")
        return self.rax

    def _asm_factorial_procedure(self) -> int:
        """Simulasi instruksi mikro assembly di dalam body factorial()."""
        # ==================== PROLOGUE ====================
        # 1. Simpan RBP pemanggil
        self.push(self.rbp, "Saved RBP")
        # 2. RBP baru menunjuk ke stack top saat ini
        self.rbp = self.rsp
        # 3. Alokasikan 16 byte stack space untuk local variables (alignment ABI 16-byte)
        self.rsp -= 16
        # 4. Simpan parameter register (RDI) ke stack local variable: [RBP - 8]
        current_n = self.rdi
        self.memory[self.rbp - 8] = current_n

        indent = "  " * ((self.STACK_BASE - self.rbp) // 32)
        print(f"{indent}{CLR_CYN}[CALL]{CLR_RST} factorial(n={current_n}) | RBP={hex(self.rbp)} RSP={hex(self.rsp)}")

        # ==================== BASE CASE CHECK ====================
        # cmp qword ptr [rbp - 8], 1
        # jle .base_case
        if current_n <= 1:
            print(f"{indent}{CLR_GRN}[BASE CASE DIKUNJUNGI]{CLR_RST} n={current_n} -> Return 1")
            self.rax = 1
        else:
            # ==================== RECURSIVE STEP ====================
            # mov rdi, [rbp - 8]
            # dec rdi
            next_arg = current_n - 1
            self.rdi = next_arg

            # call factorial (Push Return Address)
            simulated_ret_addr = 0x0040_1068
            self.push(simulated_ret_addr, f"RetAddr for n={current_n}")
            self.rip = 0x0040_1050

            # Rekursi Assembly
            child_result = self._asm_factorial_procedure()

            # Setelah RET: POP return address
            popped_ret = self.pop()
            self.rip = popped_ret

            # Restore nilai n lokal dari [RBP - 8] dan kalikan dengan RAX
            saved_n = self.memory[self.rbp - 8]
            self.rax = saved_n * child_result
            print(f"{indent}{CLR_YEL}[UNWIND]{CLR_RST} Returning: {saved_n} * {child_result} = {self.rax}")

        # ==================== EPILOGUE ====================
        # mov rsp, rbp   (Deallokasi local variables)
        self.rsp = self.rbp
        # pop rbp       (Restore base pointer milik pemanggil)
        self.rbp = self.pop()
        # ret           (Kembali ke caller)

        return self.rax


def run_benchmark_and_overflow_demo():
    print(f"{CLR_BOLD}{'=' * 75}{CLR_RST}")
    print(f"{CLR_BOLD}{CLR_CYN}LAB SISTEM KOMPUTER & C: CALL STACK, ACTIVATION RECORD & REKURSI{CLR_RST}")
    print(f"{CLR_BOLD}{'=' * 75}{CLR_RST}")

    emulator = AssemblyStackMachine()

    # 1. Jalankan factorial(4) dengan pelacakan stack frame penuh
    factorial_input = 4
    result = emulator.simulate_c_factorial(factorial_input)

    # 2. Tampilkan kondisi stack setelah eksekusi normal
    emulator.print_stack_layout(f"STACK FRAME STATE POST factorial({factorial_input})")
    print(f"Max Stack Depth Tercapai : {emulator.max_stack_depth * 8} bytes ({emulator.max_stack_depth} quadwords)")

    # 3. Snapshot di tengah kedalaman rekursi
    print(f"\n{CLR_BOLD}[DEMO INSPEKSI STRUKTUR MEMORI FRAME AKTIF]{CLR_RST}")
    inspect_sim = AssemblyStackMachine()
    inspect_sim.push(0x0040_1020)  # main ret
    inspect_sim.push(inspect_sim.rbp)  # frame 0 rbp
    inspect_sim.rbp = inspect_sim.rsp
    inspect_sim.rsp -= 16
    inspect_sim.memory[inspect_sim.rbp - 8] = 3  # n = 3

    # Frame berikutnya (n = 2)
    inspect_sim.push(0x0040_1068)  # ret addr
    inspect_sim.push(inspect_sim.rbp)  # saved rbp frame 0
    inspect_sim.rbp = inspect_sim.rsp
    inspect_sim.rsp -= 16
    inspect_sim.memory[inspect_sim.rbp - 8] = 2  # n = 2
    inspect_sim.print_stack_layout("SNAPSHOT: CALL STACK MULTI-FRAME (Recursion Depth = 2)")

    # 4. Simulasi Eksperimen Stack Overflow (Guard Page Violation)
    print(f"\n{CLR_BOLD}[SIMULASI BATAS FISIK: STACK OVERFLOW RECURSION]{CLR_RST}")
    overflow_sim = AssemblyStackMachine()
    overflow_limit_n = 2000
    print(f"Menjalankan rekursi tak terkendali n={overflow_limit_n} (Limit buffer = 8KB)...")
    try:
        # Loop sengaja memicu penurunan RSP melewati STACK_LIMIT
        for i in range(1, overflow_limit_n):
            overflow_sim.push(i, f"dummy frame data {i}")
            if i % 250 == 0:
                print(f"  Frame Level {i:<4} | RSP: {hex(overflow_sim.rsp)}")
    except RecursionError as e:
        print(str(e))
        print(f"{CLR_GRN}[SUCCESS] Emulator berhasil mencegat Stack Buffer Boundary Breach!{CLR_RST}")


if __name__ == "__main__":
    run_benchmark_and_overflow_demo()
    sys.exit(0)