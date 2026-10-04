#!/usr/bin/env python3
"""
Ruby Architecture & Foundation Simulator (BAB-01: Fondasi dan Arsitektur)
Hands-on Lab Exercise: Memahami Anatomi Ruby, Model Objek, Method Lookup,
YARV Bytecode Engine, dan ObjectSpace Memory Slot (RVALUE).
"""

import sys
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# --- ANSI Terminal Color Palette ---
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
BG_RED = "\033[41m"
BG_BLUE = "\033[44m"


def banner(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{WHITE}{title.center(65)}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")


def print_step(step: str, desc: str) -> None:
    print(f"{BOLD}{YELLOW}[{step}]{RESET} {WHITE}{desc}{RESET}")


# ==============================================================================
# 1. MODEL OBJEK RUBY: "Everything is an Object" & Ancestors Chain
# ==============================================================================
class RubyModule:
    def __init__(self, name: str):
        self.name = name
        self.methods: Dict[str, Any] = {}

    def define_method(self, name: str, impl: Any) -> None:
        self.methods[name] = impl


class RubyClass(RubyModule):
    def __init__(self, name: str, superclass: Optional["RubyClass"] = None):
        super().__init__(name)
        self.superclass: Optional["RubyClass"] = superclass
        self.included_modules: List[RubyModule] = []

    def include_module(self, mod: RubyModule) -> None:
        self.included_modules.insert(0, mod)

    def ancestors(self) -> List[RubyModule]:
        chain: List[RubyModule] = [self]
        for mod in self.included_modules:
            chain.append(mod)
        if self.superclass:
            chain.extend(self.superclass.ancestors())
        return chain


class RubyObject:
    def __init__(self, ruby_class: RubyClass, value: Any = None):
        self.ruby_class = ruby_class
        self.value = value
        self.singleton_methods: Dict[str, Any] = {}
        self.object_id = id(self)

    def define_singleton_method(self, name: str, impl: Any) -> None:
        self.singleton_methods[name] = impl

    def send(self, method_name: str, *args: Any) -> Any:
        print(f"  {CYAN}--> Menjalankan Dynamic Dispatch: #{method_name}{RESET}")
        # 1. Cek Singleton Class (Metaclass/Eigenclass)
        if method_name in self.singleton_methods:
            print(f"      {GREEN}[FOUND]{RESET} di {BOLD}Singleton Class (#<Class:{self.ruby_class.name}>){RESET}")
            return self.singleton_methods[method_name](self, *args)

        # 2. Telusuri Ancestors Chain
        for ancestor in self.ruby_class.ancestors():
            print(f"      {DIM}Mencari di {ancestor.name}...{RESET}")
            if method_name in ancestor.methods:
                print(f"      {GREEN}[FOUND]{RESET} Terdefinisi pada {BOLD}{ancestor.name}{RESET}")
                return ancestor.methods[method_name](self, *args)

        # 3. Method Missing fallback
        print(f"      {RED}[NOT FOUND]{RESET} Memicu fallback ke `method_missing`...")
        for ancestor in self.ruby_class.ancestors():
            if "method_missing" in ancestor.methods:
                return ancestor.methods["method_missing"](self, method_name, *args)

        raise AttributeError(f"undefined method `{method_name}' for {self.ruby_class.name}")


# ==============================================================================
# 2. YARV (Yet Another Ruby VM) Bytecode Engine Simulator
# ==============================================================================
@dataclass
class Instruction:
    op: str
    arg: Optional[Any] = None


class YARVVirtualMachine:
    def __init__(self):
        self.stack: List[Any] = []
        self.local_table: Dict[str, Any] = {}

    def dump_stack(self) -> None:
        items = " | ".join([f"{BOLD}{YELLOW}{v}{RESET}" for v in self.stack])
        print(f"    {MAGENTA}[VM Stack ({len(self.stack)})]:{RESET} [ {items if self.stack else '(empty)'} ]")

    def execute(self, iseq: List[Instruction]) -> Any:
        print_step("YARV", "Mulai mengeksekusi Instruction Sequence (ISEQ)")
        for idx, ins in enumerate(iseq):
            time.sleep(0.15)
            print(f"  {BLUE}00{idx:02d} {ins.op:<20}{RESET} {DIM}(arg={ins.arg}){RESET}")
            if ins.op == "putobject":
                self.stack.append(ins.arg)
            elif ins.op == "setlocal":
                val = self.stack.pop()
                self.local_table[ins.arg] = val
            elif ins.op == "getlocal":
                self.stack.append(self.local_table.get(ins.arg))
            elif ins.op == "opt_plus":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a + b)
            elif ins.op == "opt_mult":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)
            elif ins.op == "opt_send_without_block":
                method_name = ins.arg
                if method_name == "puts":
                    val = self.stack.pop()
                    print(f"    {BG_BLUE}{WHITE} [Ruby stdout]: {val} {RESET}")
                    self.stack.append(None)
            elif ins.op == "leave":
                break
            self.dump_stack()

        return self.stack.pop() if self.stack else None


# ==============================================================================
# 3. RUBY MEMORY MANAGEMENT: RVALUE Slots & Mark-and-Sweep GC Simulator
# ==============================================================================
@dataclass
class RValueSlot:
    slot_id: int
    data_type: str
    marked: bool = False
    payload: Any = None
    flags: str = "T_OBJECT"


class RubyObjectSpace:
    def __init__(self, total_slots: int = 8):
        self.slots: List[RValueSlot] = [
            RValueSlot(slot_id=i, data_type="FREE") for i in range(total_slots)
        ]
        self.roots: List[int] = []

    def allocate(self, data_type: str, payload: Any) -> int:
        for slot in self.slots:
            if slot.data_type == "FREE":
                slot.data_type = data_type
                slot.payload = payload
                slot.marked = False
                slot.flags = f"T_{data_type.upper()}"
                return slot.slot_id
        raise MemoryError("Ruby Heap Full! Perlu Garbage Collection.")

    def add_root(self, slot_id: int) -> None:
        if slot_id not in self.roots:
            self.roots.append(slot_id)

    def remove_root(self, slot_id: int) -> None:
        if slot_id in self.roots:
            self.roots.remove(slot_id)

    def display_heap(self, stage: str) -> None:
        print(f"\n  {BOLD}{WHITE}Status Ruby Heap ({stage}):{RESET}")
        print(f"  {'-' * 60}")
        for s in self.slots:
            status = f"{GREEN}[LIVE]{RESET}" if s.marked else (f"{RED}[DEAD]{RESET}" if s.data_type != "FREE" else f"{DIM}[FREE]{RESET}")
            root_info = f"{YELLOW}(ROOT STACK){RESET}" if s.slot_id in self.roots else ""
            print(f"  Slot #{s.slot_id:02d}: Type={s.data_type:<8} Mark={s.marked} | {status} {root_info} payload={s.payload}")
        print(f"  {'-' * 60}\n")

    def run_garbage_collection(self) -> None:
        print_step("GC-MARK", "Menelusuri objek yang terhubung dari Root (Stack / Global Table)")
        for root_id in self.roots:
            self.slots[root_id].marked = True
            print(f"    {GREEN}* Menandai Slot #{root_id:02d} sebagai LIVE (Marked=True){RESET}")
        self.display_heap("Fase Mark Selesai")

        time.sleep(0.2)
        print_step("GC-SWEEP", "Menyapu slot yang tidak memiliki Mark dan mengembalikannya ke Freelist")
        reclaimed = 0
        for slot in self.slots:
            if slot.data_type != "FREE" and not slot.marked:
                print(f"    {RED}x Membersihkan Slot #{slot.slot_id:02d} ({slot.payload}) -> FREE{RESET}")
                slot.data_type = "FREE"
                slot.payload = None
                slot.flags = "T_NONE"
                reclaimed += 1
            else:
                slot.marked = False  # Reset mark untuk siklus berikutnya
        print(f"    {BOLD}{GREEN}GC Berhasil: {reclaimed} slot RVALUE berhasil direklamasi.{RESET}")
        self.display_heap("Fase Sweep Selesai")


# ==============================================================================
# 4. INTERACTIVE DEMO SCENARIOS
# ==============================================================================
def demo_object_model() -> None:
    banner("1. DEMO: RUBY OBJECT MODEL & METHOD LOOKUP")
    print("Membangun Hirarki Kelas Ruby Standar:")
    print("  BasicObject -> Object -> Kernel (Module) -> Numeric -> Integer\n")

    basic_obj = RubyClass("BasicObject")
    ruby_obj = RubyClass("Object", superclass=basic_obj)
    kernel_mod = RubyModule("Kernel")
    ruby_obj.include_module(kernel_mod)

    numeric_cls = RubyClass("Numeric", superclass=ruby_obj)
    integer_cls = RubyClass("Integer", superclass=numeric_cls)

    # Definisi method pada tingkatan berbeda
    kernel_mod.define_method("puts", lambda self, msg: f"[Kernel#puts]: {msg}")
    numeric_cls.define_method("zero?", lambda self: self.value == 0)
    integer_cls.define_method("even?", lambda self: (self.value % 2) == 0)

    # Fallback method missing di BasicObject
    basic_obj.define_method("method_missing", lambda self, m_name, *args: f"[NoMethodError] `{m_name}` tidak ada!")

    num = RubyObject(integer_cls, value=42)
    print(f"{BOLD}Objek Terbuat:{RESET} Instance of {integer_cls.name} (value={num.value}, object_id={num.object_id})")
    print(f"{BOLD}Ancestors Chain:{RESET} {[m.name for m in integer_cls.ancestors()]}\n")

    print_step("TEST 1", "Panggil method `even?` (Didefinisikan di Integer)")
    res1 = num.send("even?")
    print(f"  Hasil: {BOLD}{GREEN}{res1}{RESET}\n")

    print_step("TEST 2", "Panggil method `zero?` (Didefinisikan di superclass Numeric)")
    res2 = num.send("zero?")
    print(f"  Hasil: {BOLD}{GREEN}{res2}{RESET}\n")

    print_step("TEST 3", "Definisikan Singleton Method khusus untuk objek `num` (Eigenclass)")
    num.define_singleton_method("spesial_ruby", lambda self: "Nilai rahasia 42!")
    res3 = num.send("spesial_ruby")
    print(f"  Hasil: {BOLD}{GREEN}{res3}{RESET}\n")

    print_step("TEST 4", "Panggil method yang tidak terdefinisi (`terbang`)")
    res4 = num.send("terbang")
    print(f"  Hasil: {BOLD}{RED}{res4}{RESET}\n")


def demo_yarv_engine() -> None:
    banner("2. DEMO: YARV (YET ANOTHER RUBY VM) BYTECODE ENGINE")
    print("Simulasi kompilasi potongan kode Ruby berikut ke YARV Bytecode:")
    print(f"{CYAN}  a = 10{RESET}")
    print(f"{CYAN}  b = 5{RESET}")
    print(f"{CYAN}  total = (a + b) * 2{RESET}")
    print(f"{CYAN}  puts total{RESET}\n")

    iseq = [
        Instruction("putobject", 10),
        Instruction("setlocal", "a"),
        Instruction("putobject", 5),
        Instruction("setlocal", "b"),
        Instruction("getlocal", "a"),
        Instruction("getlocal", "b"),
        Instruction("opt_plus"),
        Instruction("putobject", 2),
        Instruction("opt_mult"),
        Instruction("setlocal", "total"),
        Instruction("getlocal", "total"),
        Instruction("opt_send_without_block", "puts"),
        Instruction("leave"),
    ]

    vm = YARVVirtualMachine()
    vm.execute(iseq)
    print(f"\n{BOLD}{GREEN}Eksekusi Bytecode Selesai dengan State Local Table:{RESET} {vm.local_table}")


def demo_garbage_collector() -> None:
    banner("3. DEMO: RUBY OBJECTSPACE & MARK-SWEEP GC")
    print("Ruby mengalokasikan slot memori RVALUE tetap (40 bytes per slot).")
    print("Mari simulasikan alokasi heap dan pembersihan objek yatim (unreachable).\n")

    obj_space = RubyObjectSpace(total_slots=6)

    s0 = obj_space.allocate("STRING", "UserSession: Active")
    s1 = obj_space.allocate("ARRAY", [1, 2, 3])
    s2 = obj_space.allocate("HASH", {"role": "admin"})
    s3 = obj_space.allocate("STRING", "TempCache: To be deleted")
    s4 = obj_space.allocate("OBJECT", "TemporaryCalcResult")

    # s0 dan s2 masih dirujuk oleh stack lokal/root
    obj_space.add_root(s0)
    obj_space.add_root(s2)

    obj_space.display_heap("Inisialisasi Alokasi Objek")

    print_step("SIMULASI", "Menjalankan GC Cycle karena alokasi memori mendekati batas ambang.")
    obj_space.run_garbage_collection()


def interactive_menu() -> None:
    while True:
        banner("LAB SIMULATOR ARSITEKTUR RUBY (BAB-01)")
        print(f"  {BOLD}Pilih Modul Praktikum:{RESET}")
        print(f"  {CYAN}1.{RESET} Eksplorasi Object Model & Dynamic Dispatch (Ancestors Chain)")
        print(f"  {CYAN}2.{RESET} Eksplorasi YARV Bytecode & Stack Virtual Machine")
        print(f"  {CYAN}3.{RESET} Eksplorasi ObjectSpace, RVALUE Slots & Garbage Collector")
        print(f"  {CYAN}4.{RESET} Jalankan Seluruh Simulasi Otomatis")
        print(f"  {RED}0.{RESET} Keluar\n")

        try:
            choice = input(f"{BOLD}{WHITE}Masukkan pilihan (0-4): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            demo_object_model()
        elif choice == "2":
            demo_yarv_engine()
        elif choice == "3":
            demo_garbage_collector()
        elif choice == "4":
            demo_object_model()
            demo_yarv_engine()
            demo_garbage_collector()
            break
        elif choice == "0":
            print(f"\n{GREEN}Sesi praktikum selesai.{RESET}\n")
            break
        else:
            print(f"\n{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")

        try:
            input(f"\n{DIM}Tekan [Enter] untuk melanjutkan...{RESET}")
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        demo_object_model()
        demo_yarv_engine()
        demo_garbage_collector()
    else:
        # Jika dijalankan di terminal non-interaktif, jalankan mode auto
        if not sys.stdin.isatty():
            demo_object_model()
            demo_yarv_engine()
            demo_garbage_collector()
        else:
            interactive_menu()
