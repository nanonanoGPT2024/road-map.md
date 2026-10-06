#!/usr/bin/env python3
"""
Interactive Technical Simulation: C++ Core Foundations (BAB 08 - BAB 10)
Topics: Pointers, Memory Addresses, RAII, Smart Pointers, VTable/Polymorphism, and Move Semantics.
"""

import sys
import time

# ANSI Terminal Colors
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


def print_header(title: str):
    print("\n" + "=" * 65)
    print(f"{BOLD}{BG_BLUE}{WHITE}  {title}  {RESET}")
    print("=" * 65)


def print_step(step_num: int, description: str):
    print(f"\n{BOLD}{CYAN}[Step {step_num}]{RESET} {YELLOW}{description}{RESET}")


def simulate_pointers_and_memory():
    print_header("SIMULASI 1: Pointer, Memory Addressing & Dereference")
    print(f"{WHITE}Mensimulasikan cara kerja pointer mentah (raw pointer) dan stack memory.{RESET}")

    val_a = 42
    addr_a = "0x7ffd9a32c014"
    ptr_p = addr_a

    print_step(1, "Alokasi variabel lokal di Stack")
    print(f"  int a = {val_a};")
    print(f"  Address of a (&a) : {GREEN}{addr_a}{RESET}")
    print(f"  Value of a        : {MAGENTA}{val_a}{RESET}")

    print_step(2, "Inisialisasi Raw Pointer")
    print("  int* p = &a;")
    print(f"  Pointer p holds   : {GREEN}{ptr_p}{RESET}")
    print(f"  Dereference (*p)  : {MAGENTA}{val_a}{RESET}")

    print_step(3, "Mutasi nilai via Pointer Dereferencing")
    print("  *p = 99;")
    val_a = 99
    print(f"  New value of a    : {BOLD}{GREEN}{val_a}{RESET} (ikut berubah via alias memori)")

    print_step(4, "Bahaya Null Pointer Dereference")
    print("  int* null_ptr = nullptr;")
    null_ptr = None
    print(f"  null_ptr address  : {RED}0x0 (nullptr){RESET}")
    try:
        if null_ptr is None:
            raise RuntimeError("Segmentation fault (SIGSEGV): Dereferencing nullptr!")
    except RuntimeError as err:
        print(f"  {RED}[TRAPPED]{RESET} {err}")


class SimulatedResource:
    def __init__(self, resource_id: int):
        self.resource_id = resource_id
        print(f"  {GREEN}[+] Resource #{self.resource_id} allocated on Heap (new).{RESET}")

    def __del__(self):
        print(f"  {RED}[-] Resource #{self.resource_id} deallocated (delete/destructor).{RESET}")


class UniquePtrSimulation:
    def __init__(self, resource: SimulatedResource):
        self._res = resource

    def release(self):
        res = self._res
        self._res = None
        return res

    def reset(self, new_res=None):
        if self._res is not None:
            del self._res
        self._res = new_res

    def is_valid(self):
        return self._res is not None


def simulate_raii_and_smart_pointers():
    print_header("SIMULASI 2: RAII & Smart Pointers (std::unique_ptr)")
    print(f"{WHITE}Mensimulasikan Resource Acquisition Is Initialization (RAII).{RESET}")

    print_step(1, "Entering Scope A (Membuat std::unique_ptr<Resource>)")
    uptr = UniquePtrSimulation(SimulatedResource(101))
    print(f"  unique_ptr owns resource? {GREEN}{uptr.is_valid()}{RESET}")

    print_step(2, "Transfer Kepemilikan (Move Semantics: std::move)")
    print("  auto uptr2 = std::move(uptr);")
    moved_res = uptr.release()
    uptr2 = UniquePtrSimulation(moved_res)

    print(f"  uptr (original) owns resource? {RED}{uptr.is_valid()}{RESET} (Moved-from / null)")
    print(f"  uptr2 (target) owns resource?   {GREEN}{uptr2.is_valid()}{RESET} (Active owner)")

    print_step(3, "Exiting Scope (Destruksi Otomatis RAII)")
    print("  Leaving scope block...")
    uptr2.reset()


def simulate_vtable_polymorphism():
    print_header("SIMULASI 3: Virtual Table (vtable) & Dynamic Dispatch")
    print(f"{WHITE}Mensimulasikan bagaimana compiler C++ memetakan virtual function call.{RESET}")

    vtable_base = {
        "speak": "Base::speak (offset +0x00)",
        "identify": "Base::identify (offset +0x08)"
    }

    vtable_derived = {
        "speak": "Derived::speak [OVERRIDDEN] (offset +0x00)",
        "identify": "Base::identify [INHERITED] (offset +0x08)"
    }

    print_step(1, "VTable Base Class Structure")
    for fn, slot in vtable_base.items():
        print(f"  [vptr -> Base]    slot '{fn}': {CYAN}{slot}{RESET}")

    print_step(2, "VTable Derived Class Structure (Override)")
    for fn, slot in vtable_derived.items():
        print(f"  [vptr -> Derived] slot '{fn}': {GREEN}{slot}{RESET}")

    print_step(3, "Dynamic Dispatch via Base Pointer")
    print("  Base* b = new Derived();")
    print("  b->speak(); // Melakukan dereferensi vptr -> vtable[0]")
    invoked = vtable_derived["speak"]
    print(f"  Resolved function: {BOLD}{GREEN}{invoked}{RESET}")


def run_interactive_menu():
    while True:
        print_header("C++ FOUNDATION LAB SIMULATOR (CLI)")
        print(f"{YELLOW}1.{RESET} Simulasi Pointer & Memory Stack/Heap")
        print(f"{YELLOW}2.{RESET} Simulasi RAII & std::unique_ptr Move Semantics")
        print(f"{YELLOW}3.{RESET} Simulasi Virtual Table (vtable) Polymorphism")
        print(f"{YELLOW}4.{RESET} Jalankan Seluruh Simulasi Otomatis (Full Run)")
        print(f"{YELLOW}5.{RESET} Keluar (Exit)")
        print("-" * 65)

        try:
            choice = input(f"{BOLD}Pilih menu (1-5): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{CYAN}Program selesai.{RESET}")
            break

        if choice == "1":
            simulate_pointers_and_memory()
        elif choice == "2":
            simulate_raii_and_smart_pointers()
        elif choice == "3":
            simulate_vtable_polymorphism()
        elif choice == "4":
            simulate_pointers_and_memory()
            simulate_raii_and_smart_pointers()
            simulate_vtable_polymorphism()
            print(f"\n{BOLD}{GREEN}[SUCCESS] Seluruh modul fondasi C++ berhasil disimulasikan.{RESET}\n")
        elif choice == "5":
            print(f"{GREEN}Menutup simulator. Sampai jumpa!{RESET}")
            break
        else:
            print(f"{RED}[!] Pilihan tidak valid. Silakan masukkan angka 1 - 5.{RESET}")

        time.sleep(0.3)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        simulate_pointers_and_memory()
        simulate_raii_and_smart_pointers()
        simulate_vtable_polymorphism()
        print(f"\n{BOLD}{GREEN}[AUTO-TEST PASSED] Syntax and execution 100% OK.{RESET}\n")
    else:
        run_interactive_menu()
