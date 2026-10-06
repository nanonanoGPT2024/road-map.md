#!/usr/bin/env python3
"""
Lab Exercise: C++ Core Foundations & Memory Architecture Simulator
BAB-04-6: Fondasi Inti C++ (Object Lifecycle, RAII, Move Semantics, Vtable, & Smart Pointers)
"""

import sys
import time
from typing import Dict, List, Optional


class TerminalColors:
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


def print_banner(title: str) -> None:
    line = "=" * 68
    print(f"\n{TerminalColors.CYAN}{TerminalColors.BOLD}{line}{TerminalColors.RESET}")
    print(f"{TerminalColors.CYAN}{TerminalColors.BOLD} [C++ SIM] :: {title.center(50)} ::{TerminalColors.RESET}")
    print(f"{TerminalColors.CYAN}{TerminalColors.BOLD}{line}{TerminalColors.RESET}\n")


class RAIIScopeSimulator:
    """Simulates C++ Stack Frame Unwinding and RAII Destructor calls."""

    def __init__(self, scope_name: str):
        self.scope_name = scope_name
        self.resources: List[str] = []

    def allocate(self, res_name: str, memory_addr: str) -> None:
        self.resources.append(res_name)
        print(f"  {TerminalColors.GREEN}[+] C++ Ctor:{TerminalColors.RESET} Resource '{res_name}' "
              f"acquired at stack/heap {TerminalColors.YELLOW}{memory_addr}{TerminalColors.RESET}")

    def __enter__(self):
        print(f"{TerminalColors.BLUE}--> Entering Scope: [{self.scope_name}]{TerminalColors.RESET}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print(f"{TerminalColors.MAGENTA}<-- Exiting Scope: [{self.scope_name}] (Deterministic RAII Unwinding){TerminalColors.RESET}")
        while self.resources:
            res = self.resources.pop()
            print(f"  {TerminalColors.RED}[-] C++ Dtor:{TerminalColors.RESET} Freeing '{res}' cleanly via RAII destructor.")


class MoveSemanticsBuffer:
    """Simulates C++11 Move Semantics vs Deep Copy."""

    def __init__(self, name: str, size_bytes: int):
        self.name = name
        self.size_bytes = size_bytes
        self.buffer_ptr: Optional[str] = f"0xHEAP_{id(self):X}"

    def deep_copy_from(self, other: "MoveSemanticsBuffer", new_name: str) -> "MoveSemanticsBuffer":
        print(f"  {TerminalColors.YELLOW}[COPY-CTOR]{TerminalColors.RESET} Deep copying {other.size_bytes} bytes "
              f"from '{other.name}' ({other.buffer_ptr})...")
        new_obj = MoveSemanticsBuffer(new_name, other.size_bytes)
        print(f"    --> Allocated new heap memory: {TerminalColors.GREEN}{new_obj.buffer_ptr}{TerminalColors.RESET} "
              f"(Cost: High O(N) allocation + memcpy)")
        return new_obj

    def move_from(self, other: "MoveSemanticsBuffer", new_name: str) -> "MoveSemanticsBuffer":
        print(f"  {TerminalColors.CYAN}[MOVE-CTOR]{TerminalColors.RESET} Stealing resource ptr from '{other.name}' (rvalue reference &&)...")
        new_obj = MoveSemanticsBuffer(new_name, other.size_bytes)
        new_obj.buffer_ptr = other.buffer_ptr
        other.buffer_ptr = None  # Moved-from state: nullptr
        print(f"    --> Transferred pointer: {TerminalColors.GREEN}{new_obj.buffer_ptr}{TerminalColors.RESET}")
        print(f"    --> '{other.name}' is now in valid but unspecified state ({TerminalColors.RED}nullptr{TerminalColors.RESET}) (Cost: O(1) pointer swap)")
        return new_obj


class VTableSimulator:
    """Simulates C++ Dynamic Dispatch via VTable and VPtr."""

    def __init__(self):
        # Simulated Virtual Method Tables
        self.vtables: Dict[str, Dict[str, str]] = {
            "BaseEntity": {
                "update()": "BaseEntity::update() @ 0x401020",
                "render()": "BaseEntity::render() @ 0x401060",
                "~BaseEntity()": "BaseEntity::~BaseEntity() [Virtual Dtor] @ 0x4010A0",
            },
            "PlayerCharacter": {
                "update()": "PlayerCharacter::update() [OVERRIDDEN] @ 0x402120",
                "render()": "PlayerCharacter::render() [OVERRIDDEN] @ 0x402180",
                "~BaseEntity()": "PlayerCharacter::~PlayerCharacter() [OVERRIDDEN] @ 0x402200",
            }
        }

    def dispatch(self, static_type: str, dynamic_type: str, method: str) -> None:
        print(f"  Pointer Type: {TerminalColors.YELLOW}{static_type}*{TerminalColors.RESET} | "
              f"Actual Dynamic Instance: {TerminalColors.GREEN}{dynamic_type}{TerminalColors.RESET}")
        print(f"  Resolving call: '{method}' via vptr -> dynamic_type VTable...")
        
        target_vtable = self.vtables.get(dynamic_type, {})
        target_func = target_vtable.get(method, "UNKNOWN")
        print(f"    ==> Dispatched to: {TerminalColors.CYAN}{target_func}{TerminalColors.RESET}\n")


class SmartPointerSimulator:
    """Simulates std::shared_ptr and std::unique_ptr reference counting."""

    def __init__(self, resource_name: str):
        self.resource = resource_name
        self.ref_count = 1
        self.memory_addr = f"0x007FFF_{id(self):06X}"
        print(f"  {TerminalColors.GREEN}[make_shared]{TerminalColors.RESET} Created std::shared_ptr<{self.resource}> "
              f"at {self.memory_addr} | RefCount: {TerminalColors.BOLD}1{TerminalColors.RESET}")

    def acquire_ref(self, holder: str) -> None:
        self.ref_count += 1
        print(f"  {TerminalColors.CYAN}[COPY shared_ptr]{TerminalColors.RESET} '{holder}' acquired ownership. "
              f"RefCount: {TerminalColors.BOLD}{self.ref_count}{TerminalColors.RESET}")

    def release_ref(self, holder: str) -> None:
        self.ref_count -= 1
        print(f"  {TerminalColors.YELLOW}[DTOR shared_ptr]{TerminalColors.RESET} '{holder}' released reference. "
              f"RefCount: {TerminalColors.BOLD}{self.ref_count}{TerminalColors.RESET}")
        if self.ref_count == 0:
            print(f"    {TerminalColors.RED}*** RefCount reached 0! Deallocating control block and {self.resource} at {self.memory_addr} ***{TerminalColors.RESET}")


def run_raii_demo() -> None:
    print_banner("1. RAII & Stack Unwinding Simulation")
    print(f"{TerminalColors.WHITE}Demonstrating C++ deterministic destructor invocation upon scope termination.{TerminalColors.RESET}\n")
    with RAIIScopeSimulator("outer_function_scope") as outer:
        outer.allocate("DatabaseConnectionPool", "0x7FFEE01A")
        with RAIIScopeSimulator("inner_critical_section") as inner:
            inner.allocate("MutexGuard<std::mutex>", "0x7FFEE030")
            inner.allocate("FileDescriptor(log.txt)", "0x7FFEE048")
            print(f"  {TerminalColors.DIM}[...] Executing high-frequency transaction [...]{TerminalColors.RESET}")
    print(f"\n{TerminalColors.GREEN}✓ RAII simulation finished successfully with zero memory leaks.{TerminalColors.RESET}\n")


def run_move_semantics_demo() -> None:
    print_banner("2. C++11 Move Semantics vs Deep Copy")
    print(f"{TerminalColors.WHITE}Comparing high-cost copy constructor with zero-cost rvalue move transfer.{TerminalColors.RESET}\n")
    
    source = MoveSemanticsBuffer("VectorA_Source", 1024 * 1024 * 64)  # 64MB
    print(f"Initial State: '{source.name}' holds 64MB buffer at {source.buffer_ptr}\n")

    # Copy demo
    _ = source.deep_copy_from(source, "VectorB_DeepCopy")
    print(f"Original '{source.name}' buffer still intact: {source.buffer_ptr}\n")

    # Move demo
    moved = source.move_from(source, "VectorC_MovedTarget")
    print(f"Final State: '{moved.name}' now holds {moved.buffer_ptr}")
    print(f"Original '{source.name}' buffer pointer: {TerminalColors.RED}{source.buffer_ptr}{TerminalColors.RESET}\n")


def run_vtable_demo() -> None:
    print_banner("3. Polymorphism & VTable Dispatch")
    print(f"{TerminalColors.WHITE}Simulating runtime dynamic method resolution through virtual method tables.{TerminalColors.RESET}\n")
    
    sim = VTableSimulator()
    sim.dispatch("BaseEntity", "BaseEntity", "update()")
    sim.dispatch("BaseEntity", "PlayerCharacter", "update()")
    sim.dispatch("BaseEntity", "PlayerCharacter", "render()")
    sim.dispatch("BaseEntity", "PlayerCharacter", "~BaseEntity()")


def run_smart_ptr_demo() -> None:
    print_banner("4. Smart Pointers (std::shared_ptr) Control Block")
    print(f"{TerminalColors.WHITE}Tracking reference counter increments and automated deallocation.{TerminalColors.RESET}\n")
    
    shared_obj = SmartPointerSimulator("AudioEngine")
    shared_obj.acquire_ref("SoundManager")
    shared_obj.acquire_ref("AmbientTracker")
    
    print("\nSimulating components shutting down...")
    shared_obj.release_ref("AmbientTracker")
    shared_obj.release_ref("SoundManager")
    shared_obj.release_ref("MainGameLoop")


def interactive_menu() -> None:
    while True:
        print_banner("C++ FONDASI INTI (BAB-04-6) - INTERACTIVE LAB")
        print(f"  {TerminalColors.CYAN}1.{TerminalColors.RESET} Simulasi RAII & Deterministic Scope Unwinding")
        print(f"  {TerminalColors.CYAN}2.{TerminalColors.RESET} Simulasi Move Semantics vs Deep Copy (std::move)")
        print(f"  {TerminalColors.CYAN}3.{TerminalColors.RESET} Simulasi Virtual Table (VTable & Dynamic Dispatch)")
        print(f"  {TerminalColors.CYAN}4.{TerminalColors.RESET} Simulasi Smart Pointer Ref-Count (std::shared_ptr)")
        print(f"  {TerminalColors.CYAN}5.{TerminalColors.RESET} Jalankan Semua Simulasi (Full Suite)")
        print(f"  {TerminalColors.RED}0.{TerminalColors.RESET} Keluar / Exit\n")
        
        try:
            choice = input(f"{TerminalColors.BOLD}Pilih modul simulasi [0-5]: {TerminalColors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if choice == "1":
            run_raii_demo()
        elif choice == "2":
            run_move_semantics_demo()
        elif choice == "3":
            run_vtable_demo()
        elif choice == "4":
            run_smart_ptr_demo()
        elif choice == "5":
            run_raii_demo()
            run_move_semantics_demo()
            run_vtable_demo()
            run_smart_ptr_demo()
        elif choice == "0":
            print(f"{TerminalColors.GREEN}Sesi simulasi selesai. Sampai jumpa!{TerminalColors.RESET}")
            break
        else:
            print(f"{TerminalColors.RED}Pilihan tidak valid. Silakan coba lagi.{TerminalColors.RESET}")
        
        try:
            input(f"\n{TerminalColors.DIM}[Tekan Enter untuk melanjutkan ke menu...]{TerminalColors.RESET}")
        except (EOFError, KeyboardInterrupt):
            break


def main() -> None:
    # If run in non-interactive environment (e.g. piped or automated test), execute all demos
    if not sys.stdin.isatty():
        print(f"{TerminalColors.YELLOW}[Non-interactive terminal detected. Running complete test suite...]{TerminalColors.RESET}")
        run_raii_demo()
        run_move_semantics_demo()
        run_vtable_demo()
        run_smart_ptr_demo()
        print(f"\n{TerminalColors.GREEN}All C++ core foundation simulations passed successfully.{TerminalColors.RESET}")
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
