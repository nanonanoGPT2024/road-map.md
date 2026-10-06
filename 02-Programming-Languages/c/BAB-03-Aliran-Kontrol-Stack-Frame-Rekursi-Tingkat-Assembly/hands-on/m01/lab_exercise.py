#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Aliran Kontrol, Stack Frame, & Rekursi Tingkat Assembly (x86-64)
BAB-03: Aliran-Kontrol-Stack-Frame-Rekursi-Tingkat-Assembly

Simulasi interaktif tingkat arsitektur komputer yang memodelkan perilaku
Call Stack, Register Pointer (RSP, RBP, RIP), Stack Frame Prologue/Epilogue,
serta mekanisme rekursi dan stack overflow.
"""

import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional

# ANSI Color Codes untuk visualisasi terminal
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[100m"

@dataclass
class StackSlot:
    address: int
    label: str
    content: str
    owner_func: str
    slot_type: str  # 'ret_addr', 'saved_rbp', 'local_var', 'param'

@dataclass
class StackFrame:
    func_name: str
    param_n: int
    frame_base: int  # RBP
    stack_top: int   # RSP
    ret_addr: int
    saved_rbp: int
    local_val: Optional[int] = None
    slots: List[StackSlot] = field(default_factory=list)

class X86StackSimulator:
    BASE_STACK_ADDR = 0x7FFFFFFFDE00
    SLOT_SIZE = 8  # 8 bytes per 64-bit slot

    def __init__(self):
        self.rsp = self.BASE_STACK_ADDR
        self.rbp = self.BASE_STACK_ADDR
        self.rip = 0x0000000000401140  # main entry
        self.memory: List[StackSlot] = []
        self.frames: List[StackFrame] = []
        self.call_history: List[str] = []

    def clear(self):
        self.rsp = self.BASE_STACK_ADDR
        self.rbp = self.BASE_STACK_ADDR
        self.rip = 0x0000000000401140
        self.memory.clear()
        self.frames.clear()
        self.call_history.clear()

    def print_header(self, title: str):
        border = "=" * 70
        print(f"\n{Colors.BOLD}{Colors.CYAN}{border}")
        print(f"  {title.center(66)}")
        print(f"{border}{Colors.RESET}\n")

    def print_registers(self):
        print(f"{Colors.BOLD}[REGISTERS]{Colors.RESET}")
        print(f"  RSP (Stack Pointer): {Colors.YELLOW}0x{self.rsp:016X}{Colors.RESET} (Tumbuh ke alamat rendah)")
        print(f"  RBP (Base Pointer) : {Colors.GREEN}0x{self.rbp:016X}{Colors.RESET} (Jangkar frame saat ini)")
        print(f"  RIP (Instr Pointer): {Colors.MAGENTA}0x{self.rip:016X}{Colors.RESET}")
        print("-" * 70)

    def print_stack_diagram(self):
        print(f"{Colors.BOLD}[MEMORI STACK REAL-TIME (Tinggi ke Rendah)]{Colors.RESET}")
        if not self.memory:
            print(f"  {Colors.DIM}[Stack kosong / Terinisialisasi di 0x{self.BASE_STACK_ADDR:016X}]{Colors.RESET}")
            return

        print(f"  {'ALAMAT':<18} | {'OFFSET':<10} | {'SLOT TYPE':<12} | {'KONTEN':<24} | {'POINTER'}")
        print("  " + "-" * 75)

        for slot in sorted(self.memory, key=lambda s: s.address, reverse=True):
            offset_str = f"+{slot.address - self.rsp:02d}B" if slot.address >= self.rsp else f"-{self.rsp - slot.address:02d}B"
            
            # Label pointer penunjuk
            ptr_label = []
            if slot.address == self.rsp:
                ptr_label.append(f"{Colors.YELLOW}<= RSP{Colors.RESET}")
            if slot.address == self.rbp:
                ptr_label.append(f"{Colors.GREEN}<= RBP{Colors.RESET}")
            ptr_str = " ".join(ptr_label)

            # Warna jenis slot
            if slot.slot_type == 'ret_addr':
                type_color = Colors.RED
            elif slot.slot_type == 'saved_rbp':
                type_color = Colors.GREEN
            elif slot.slot_type == 'local_var':
                type_color = Colors.CYAN
            else:
                type_color = Colors.WHITE

            print(f"  {Colors.DIM}0x{slot.address:016X}{Colors.RESET} | {offset_str:<10} | "
                  f"{type_color}{slot.slot_type:<12}{Colors.RESET} | "
                  f"{slot.content:<24} | {ptr_str}")

        print("  " + "-" * 75)

    def call_function(self, func_name: str, param: int, ret_addr: int):
        print(f"\n{Colors.BOLD}{Colors.BLUE}>>> EKSEKUSI: call {func_name}({param}){Colors.RESET}")
        print(f"    1. CPU push return address (0x{ret_addr:08X}) ke stack")
        self.rsp -= self.SLOT_SIZE
        ret_slot = StackSlot(
            address=self.rsp,
            label="Return Address",
            content=f"RET -> 0x{ret_addr:08X}",
            owner_func=func_name,
            slot_type="ret_addr"
        )
        self.memory.append(ret_slot)

        print(f"    2. Prologue: push rbp (Simpan RBP lama 0x{self.rbp:016X})")
        old_rbp = self.rbp
        self.rsp -= self.SLOT_SIZE
        saved_rbp_slot = StackSlot(
            address=self.rsp,
            label="Saved RBP",
            content=f"Saved RBP (0x{old_rbp:08X})",
            owner_func=func_name,
            slot_type="saved_rbp"
        )
        self.memory.append(saved_rbp_slot)

        print(f"    3. Prologue: mov rbp, rsp (Perbarui RBP ke frame baru)")
        self.rbp = self.rsp

        print(f"    4. Prologue: sub rsp, 16 (Alokasi ruang variabel lokal)")
        self.rsp -= self.SLOT_SIZE
        local_param_slot = StackSlot(
            address=self.rsp,
            label="Local n",
            content=f"int n = {param}",
            owner_func=func_name,
            slot_type="local_var"
        )
        self.memory.append(local_param_slot)

        frame = StackFrame(
            func_name=func_name,
            param_n=param,
            frame_base=self.rbp,
            stack_top=self.rsp,
            ret_addr=ret_addr,
            saved_rbp=old_rbp,
            local_val=param,
            slots=[ret_slot, saved_rbp_slot, local_param_slot]
        )
        self.frames.append(frame)
        self.call_history.append(f"{func_name}({param})")

    def return_function(self, return_val: int) -> int:
        if not self.frames:
            print(f"{Colors.RED}Kesalahan: Stack kosong!{Colors.RESET}")
            return return_val

        frame = self.frames[-1]
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}<<< EKSEKUSI: Epilogue & return dari {frame.func_name}({frame.param_n}){Colors.RESET}")
        print(f"    Nilai kembali dimuat ke register EAX/RAX = {Colors.BOLD}{return_val}{Colors.RESET}")
        print(f"    1. Epilogue: mov rsp, rbp (Dealokasi variabel lokal)")
        self.rsp = self.rbp

        # Hapus variabel lokal dari list memori
        self.memory = [s for s in self.memory if s.address >= self.rbp]

        print(f"    2. Epilogue: pop rbp (Pulihkan RBP ke pemanggil: 0x{frame.saved_rbp:016X})")
        self.rbp = frame.saved_rbp
        self.memory = [s for s in self.memory if s.address > self.rsp]
        self.rsp += self.SLOT_SIZE

        print(f"    3. Epilogue: ret (Pop return address 0x{frame.ret_addr:08X} ke RIP)")
        self.rip = frame.ret_addr
        self.memory = [s for s in self.memory if s.address > self.rsp]
        self.rsp += self.SLOT_SIZE

        self.frames.pop()
        return return_val


def interactive_factorial_simulation(sim: X86StackSimulator):
    sim.clear()
    sim.print_header("SIMULASI REKURSI FAKTORIAL: call stack & frame allocation")
    print("Contoh Kode C:")
    print(f"{Colors.CYAN}int factorial(int n) {{\n    if (n <= 1) return 1;\n    return n * factorial(n - 1);\n}}{Colors.RESET}\n")

    try:
        user_input = input("Masukkan nilai n untuk faktorial (disarankan 2 - 5): ").strip()
        n = int(user_input) if user_input else 3
        if n < 1 or n > 8:
            print(f"{Colors.YELLOW}Nilai dibatasi antara 1 - 8 untuk keterbacaan visual. Menggunakan n=3.{Colors.RESET}")
            n = 3
    except ValueError:
        n = 3

    print(f"\n{Colors.BOLD}Memulai eksekusi fungsi factorial({n})...{Colors.RESET}")
    time.sleep(0.5)

    # Fase 1: Panggilan rekursif (Winding / Growing Stack)
    print(f"\n{Colors.BOLD}{Colors.GREEN}=== FASE 1: WINDING (Stack Mengembang ke Bawah) ==={Colors.RESET}")
    current_ret = 0x401180  # Call site dari main
    for i in range(n, 0, -1):
        sim.call_function("factorial", i, current_ret)
        sim.print_registers()
        sim.print_stack_diagram()
        current_ret = 0x401168  # Call site rekursif di dalam factorial
        input(f"{Colors.DIM}[Tekan Enter untuk lanjut ke langkah berikutnya...]{Colors.RESET}")

    # Fase 2: Unwinding (Menyusutkan Stack & Evaluasi Nilai)
    print(f"\n{Colors.BOLD}{Colors.YELLOW}=== FASE 2: UNWINDING (Base Case Tercapai, Stack Diciutkan) ==={Colors.RESET}")
    print(f"Base case n=1 tercapai. Mengembalikan nilai 1 ke pemanggil.")
    
    accum = 1
    for step in range(1, n + 1):
        if step > 1:
            prev = accum
            accum = accum * step
            print(f"\n{Colors.BOLD}Perhitungan: RAX = {step} * {prev} = {accum}{Colors.RESET}")
        else:
            accum = 1
            print(f"\n{Colors.BOLD}Base case mengembalikan RAX = 1{Colors.RESET}")

        sim.return_function(accum)
        sim.print_registers()
        sim.print_stack_diagram()
        if sim.frames:
            input(f"{Colors.DIM}[Tekan Enter untuk lanjut unwinding...]{Colors.RESET}")

    print(f"\n{Colors.BOLD}{Colors.GREEN}Hasil Akhir: factorial({n}) = {accum}{Colors.RESET}")
    print(f"Stack telah pulih seimbang (RSP dan RBP kembali ke posisi awal di pemanggil).")


def simulate_stack_overflow_concept():
    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.RED}  SIMULASI TEKNIS: STACK OVERFLOW & GUARD PAGE EXHAUSTION  {Colors.RESET}")
    print("=" * 70)
    print("""
Pada arsitektur sistem operasi modern (Linux/POSIX x86-64):
- Stack memiliki batas ukuran default (misal: 'ulimit -s' bernilai 8192 KB / 8 MB).
- Di bawah stack terpasang 'Guard Page' (halaman memori dengan proteksi PROT_NONE).
- Ketika rekursi tanpa base case berjalan, RSP terus dikurangi (sub rsp, X).
- Begitu RSP menyentuh Guard Page, MMU memicu Page Fault hardware.
- Kernel mendeteksi akses terlarang dan mengirim sinyal SIGSEGV (Segmentation Fault).
""")
    limit = 10
    print(f"{Colors.YELLOW}Mensimulasikan ledakan frame rekursi tak terbatas (infinite recursion)...{Colors.RESET}")
    for i in range(1, limit + 1):
        addr = 0x7FFFFFFFDE00 - (i * 0x1000)
        print(f"  Frame #{i:<3} | RSP = 0x{addr:016X} | Pushing frame [{i * 4096} bytes consumed]")
        time.sleep(0.08)

    print(f"\n{Colors.BOLD}{Colors.RED}[!] CRASH: RSP menyentuh 0x7FFFFF7FE000 (Guard Page Boundary)!{Colors.RESET}")
    print(f"{Colors.RED}[!] Hardware MMU -> Trap 14 (Page Fault Exception)")
    print(f"[!] Kernel Dispatcher -> Sinyal SIGSEGV dikirim ke proses.")
    print(f"[!] Segmentation fault (core dumped){Colors.RESET}\n")


def stack_frame_dissection_theory():
    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.CYAN}  BEDAH STRUKTUR STACK FRAME TINGKAT ASSEMBLY (x86-64 System V ABI)  {Colors.RESET}")
    print("=" * 70)
    print(f"""
Diagram Standar Layout Stack Frame:

     Alamat Memori Tinggi (High Address)
     +-----------------------------------+
     | Parameter ke-7, ke-8 (jika > 6)   |  [RBP + 16, RBP + 24 ...]
     +-----------------------------------+
     | Return Address (RIP Pemanggil)    |  [RBP + 8]  <-- Di-push otomatis oleh 'call'
     +-----------------------------------+
     | Saved Frame Pointer (RBP Lama)    |  [RBP]      <-- Di-push oleh 'push rbp'
     +-----------------------------------+  <== RBP sekarang menunjuk ke sini
     | Variabel Lokal 1                  |  [RBP - 4 / -8]
     | Variabel Lokal 2 / Array / Struct |  [RBP - 16 ...]
     +-----------------------------------+
     | Ruang Callee-saved (RBX, R12-R15) |  [RSP]      <-- RSP menunjuk batas bawah
     +-----------------------------------+
     | Red Zone (128-byte scratchpad)    |  [RSP - 128] (Khusus leaf function x86-64)
     +-----------------------------------+
     Alamat Memori Rendah (Low Address)

Instruksi Prologue Standar:
    push    rbp              ; Simpan base pointer pemanggil
    mov     rbp, rsp         ; Jadikan stack pointer saat ini sebagai basis frame
    sub     rsp, 16          ; Alokasikan ruang memori lokal

Instruksi Epilogue Standar:
    leave                    ; Ekuivalen dengan: mov rsp, rbp; pop rbp
    ret                      ; Pop return address dari stack dan lompat ke RIP tersebut
""")


def run_interactive_quiz():
    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.YELLOW}  KUIS INTERAKTIF: PEMAHAMAN STACK FRAME & ASSEMBLY  {Colors.RESET}")
    print("=" * 70)

    questions = [
        {
            "q": "Instruksi assembly mana yang secara otomatis mengurangi RSP sebesar 8 byte dan menyimpan RIP?",
            "options": ["A. jmp label", "B. call function", "C. mov [rsp], rip", "D. ret"],
            "ans": "B",
            "explain": "'call' melakukan push alamat instruksi berikutnya (RIP) ke stack dan lompat ke target."
        },
        {
            "q": "Di mana letak Saved RBP relatif terhadap RBP saat ini di dalam fungsi callee?",
            "options": ["A. Tepat di alamat [RBP]", "B. Di alamat [RBP + 8]", "C. Di alamat [RBP - 8]", "D. Di [RSP + 128]"],
            "ans": "A",
            "explain": "Setelah 'push rbp' lalu 'mov rbp, rsp', alamat yang ditunjuk RBP adalah lokasi simpan RBP lama."
        },
        {
            "q": "Instruksi tunggal x86-64 'leave' merupakan singkatan operasi dari:",
            "options": ["A. pop rbp; ret", "B. mov rsp, rbp; pop rbp", "C. sub rsp, 16; ret", "D. push rbp; mov rbp, rsp"],
            "ans": "B",
            "explain": "'leave' menyetel kembali RSP ke RBP (membersihkan variabel lokal) kemudian melakukan pop RBP."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"\n{Colors.BOLD}Soal {idx}: {item['q']}{Colors.RESET}")
        for opt in item["options"]:
            print(f"  {opt}")
        user_ans = input(f"{Colors.CYAN}Jawaban Anda (A/B/C/D): {Colors.RESET}").strip().upper()
        if user_ans == item["ans"]:
            print(f"{Colors.GREEN}✓ Benar! {item['explain']}{Colors.RESET}")
            score += 1
        else:
            print(f"{Colors.RED}✗ Salah. Jawaban benar adalah {item['ans']}. {item['explain']}{Colors.RESET}")

    print(f"\n{Colors.BOLD}Skor Kuis Anda: {score} / {len(questions)}{Colors.RESET}")


def main():
    sim = X86StackSimulator()
    while True:
        sim.print_header("SIMULATOR ARSITEKTUR: STACK FRAME & REKURSI ASSEMBLY")
        print("Menu Pilihan Simulasi:")
        print("  1. Visualisasi Interaktif Rekursi Faktorial (Winding & Unwinding Frame)")
        print("  2. Teori & Diagram Bedah Stack Frame (Prologue, Epilogue, ABI)")
        print("  3. Simulasi Teknis Stack Overflow & Guard Page Fault")
        print("  4. Uji Pemahaman: Kuis Interaktif Assembly & Stack")
        print("  5. Keluar")
        print("-" * 70)

        choice = input(f"{Colors.CYAN}Pilih opsi (1-5): {Colors.RESET}").strip()
        if choice == "1":
            interactive_factorial_simulation(sim)
        elif choice == "2":
            stack_frame_dissection_theory()
        elif choice == "3":
            simulate_stack_overflow_concept()
        elif choice == "4":
            run_interactive_quiz()
        elif choice == "5":
            print(f"\n{Colors.GREEN}Simulasi selesai. Memori simulator dibersihkan.{Colors.RESET}")
            sys.exit(0)
        else:
            print(f"{Colors.YELLOW}Pilihan tidak valid. Silakan pilih 1-5.{Colors.RESET}")

        input(f"\n{Colors.DIM}[Tekan Enter untuk kembali ke Menu Utama]{Colors.RESET}")


if __name__ == "__main__":
    main()
