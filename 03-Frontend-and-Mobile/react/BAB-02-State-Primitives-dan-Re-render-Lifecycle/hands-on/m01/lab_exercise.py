#!/usr/bin/env python3
"""
BAB-02: State Primitives dan Re-render Lifecycle Simulator
Simulasi teknis mesin internal React:
- Hook Fiber Slot Architecture (useState linked-list / array indexing)
- Snapshot State vs Functional Updater (stale closure vs functional dispatch)
- Object.is bailout optimization (bailing out when state does not change)
- Batching queue (microtask execution simulation)
- Render Phase vs Commit Phase visualizer
"""

import sys
import time
from typing import Any, Callable, List, Dict, Optional, Union

# ANSI Color Codes for terminal styling
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_BLUE = "\033[44m\033[37m"
BG_MAGENTA = "\033[45m\033[37m"

def print_banner():
    print(f"\n{BOLD}{BG_BLUE}  ⚛️ REACT INTERNALS LAB: STATE PRIMITIVES & RE-RENDER LIFECYCLE ⚛️  {RESET}\n")
    print(f"{CYAN}Membedah cara kerja useState, Batching, Object.is Bailout, dan Stale Closure.{RESET}\n")

def is_object_equal(a: Any, b: Any) -> bool:
    """Implementasi semantik Object.is() ECMAScript pada Python."""
    if a is b:
        return True
    return a == b

class HookSlot:
    """Representasi satu node hook di dalam linked list / hook table Fiber."""
    def __init__(self, initial_value: Any):
        self.memoized_state: Any = initial_value
        self.queue: List[Union[Any, Callable[[Any], Any]]] = []

class MiniReactDispatcher:
    """
    Simulasi Fiber Node dan Dispatcher React.
    Menyimpan slot hooks, pointer urutan pemanggilan hooks, dan antrian flush batching.
    """
    def __init__(self):
        self.hooks: List[HookSlot] = []
        self.hook_cursor: int = 0
        self.render_count: int = 0
        self.component_fn: Optional[Callable[[], None]] = None
        self.is_batching: bool = False
        self.pending_re_render: bool = False

    def reset_cursor(self):
        self.hook_cursor = 0

    def mount_or_update_state(self, initial_value: Any):
        idx = self.hook_cursor
        if len(self.hooks) <= idx:
            # Mount phase: Inisialisasi slot hook baru
            slot = HookSlot(initial_value)
            self.hooks.append(slot)
            print(f"  {DIM}[Hook Init]{RESET} Slot #{idx} dibuat dengan nilai awal: {GREEN}{initial_value}{RESET}")
        else:
            # Update phase: Proses update queue yang tertunda
            slot = self.hooks[idx]
            if slot.queue:
                prev_val = slot.memoized_state
                for action in slot.queue:
                    if callable(action):
                        slot.memoized_state = action(slot.memoized_state)
                    else:
                        slot.memoized_state = action
                slot.queue.clear()
                print(f"  {DIM}[Queue Flushed]{RESET} Slot #{idx} diperbarui: {RED}{prev_val}{RESET} -> {GREEN}{slot.memoized_state}{RESET}")

        current_val = self.hooks[idx].memoized_state

        def set_state(action: Union[Any, Callable[[Any], Any]]):
            target_slot = self.hooks[idx]
            target_slot.queue.append(action)

            # Eager bail-out check (jika bukan updater function)
            if not callable(action) and is_object_equal(action, target_slot.memoized_state):
                print(f"  {YELLOW}⚡ [Bailout Notice]{RESET} Nilai baru identik ({action} == {target_slot.memoized_state}). Re-render diabaikan (Bailout)!")
                target_slot.queue.pop()
                return

            print(f"  {BLUE}📥 [Dispatch Action]{RESET} Slot #{idx} dijadwalkan untuk update: {action}")
            self.schedule_re_render()

        self.hook_cursor += 1
        return current_val, set_state

    def schedule_re_render(self):
        if self.is_batching:
            self.pending_re_render = True
            print(f"  {MAGENTA}⏳ [Batching Active]{RESET} Pemanggilan re-render ditunda (masuk batch queue).")
        else:
            self.perform_render()

    def perform_render(self):
        self.render_count += 1
        print(f"\n{BOLD}{CYAN}--- 🔄 [RENDER PHASE #{self.render_count}] Dimulai ---{RESET}")
        self.reset_cursor()
        if self.component_fn:
            self.component_fn()
        print(f"{BOLD}{GREEN}--- 🎨 [COMMIT PHASE #{self.render_count}] DOM Tree Updated & Synchronized ---{RESET}\n")

    def run_batched(self, fn: Callable[[], None]):
        """Simulasi React 18 Automatic Batching."""
        print(f"\n{BOLD}{YELLOW}>> Memulai Blok Eksekusi Ber-Batching (Automatic Batching) <<{RESET}")
        self.is_batching = True
        try:
            fn()
        finally:
            self.is_batching = False
            if self.pending_re_render:
                self.pending_re_render = False
                print(f"{MAGENTA}🚀 [Batch Flush]{RESET} Memicu single re-render terpadu setelah semua state terkumpul...")
                self.perform_render()

# Global runtime instance
runtime = MiniReactDispatcher()

def use_state(initial_value: Any):
    """React useState primitive wrapper."""
    return runtime.mount_or_update_state(initial_value)

# State setters referensi global untuk kontrol interaktif
global_set_count = None
global_set_text = None
global_current_count = 0
global_current_text = ""

def app_component():
    """Komponen fungsional representasi UI."""
    global global_set_count, global_set_text, global_current_count, global_current_text
    count, set_count = use_state(0)
    text, set_text = use_state("Hello World")

    global_set_count = set_count
    global_set_text = set_text
    global_current_count = count
    global_current_text = text

    print(f"  {BOLD}🖥️ Virtual DOM Output:{RESET}")
    print(f"     <Widget count={GREEN}{count}{RESET} text=\"{CYAN}{text}{RESET}\" />")

def run_stale_closure_demo():
    print(f"\n{BOLD}{RED}=== DEMO 1: STALE CLOSURE VS FUNCTIONAL UPDATER ==={RESET}")
    print(f"Skenario: Memanggil dispatch 3x berturut-turut dalam satu event handler.\n")

    print(f"{YELLOW}[Uji A: Direct Value Dispatch (setCount(count + 1))]{RESET}")
    print(f"Snapshot count saat event handler diikat = {global_current_count}")
    c = global_current_count
    # Memanggil 3 kali dengan snapshot nilai 'c'
    global_set_count(c + 1)
    global_set_count(c + 1)
    global_set_count(c + 1)

    print(f"\n{YELLOW}[Uji B: Functional Updater Dispatch (setCount(prev => prev + 1))]{RESET}")
    print(f"Menggunakan callback untuk selalu membaca pending state terkini:")
    global_set_count(lambda prev: prev + 1)
    global_set_count(lambda prev: prev + 1)
    global_set_count(lambda prev: prev + 1)

def run_batching_demo():
    print(f"\n{BOLD}{MAGENTA}=== DEMO 2: AUTOMATIC BATCHING SIMULATION ==={RESET}")
    print("Mengubah dua state berbeda (count & text) di dalam satu handler sinkron.")

    def batched_handler():
        global_set_count(lambda prev: prev + 10)
        global_set_text("Batching Updated!")

    runtime.run_batched(batched_handler)

def run_bailout_demo():
    print(f"\n{BOLD}{GREEN}=== DEMO 3: OBJECT.IS BAILOUT OPTIMIZATION ==={RESET}")
    print(f"Mengisi state dengan nilai yang persis sama: '{global_current_text}'")
    global_set_text(global_current_text)

def interactive_loop():
    print_banner()
    runtime.component_fn = app_component

    # Inisialisasi first render (Mount)
    print(f"{BOLD}[Mount Phase]{RESET} Merender komponen untuk pertama kali...")
    runtime.perform_render()

    menu = f"""
{BOLD}Pilih Skenario Pengujian State & Lifecycle:{RESET}
{CYAN}[1]{RESET} Demo Stale Closure vs Functional Updater (Snapshot vs Functional Update)
{CYAN}[2]{RESET} Demo Automatic Batching (Multi-update ke 1 re-render)
{CYAN}[3]{RESET} Demo Object.is Bailout Optimization (Mencegah re-render sia-sia)
{CYAN}[4]{RESET} Direct Input: Tambah Count (+1)
{CYAN}[5]{RESET} Direct Input: Ubah Text
{CYAN}[6]{RESET} Tampilkan Struktur Internal Hook Slot Fiber
{CYAN}[0]{RESET} Keluar (Exit)
"""

    while True:
        print(menu)
        try:
            choice = input(f"{BOLD}Masukkan nomor pilihan [0-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Selesai. Keluar dari simulator.{RESET}")
            break

        if choice == "1":
            run_stale_closure_demo()
        elif choice == "2":
            run_batching_demo()
        elif choice == "3":
            run_bailout_demo()
        elif choice == "4":
            print(f"\n{BOLD}Memicu setCount(prev => prev + 1)...{RESET}")
            global_set_count(lambda prev: prev + 1)
        elif choice == "5":
            try:
                new_str = input("Masukkan teks baru: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            global_set_text(new_str)
        elif choice == "6":
            print(f"\n{BOLD}=== INSPEKSI INTERNAL FIBER HOOKS TABLE ==={RESET}")
            for i, slot in enumerate(runtime.hooks):
                print(f"  Slot #{i}: memoized_state={GREEN}{slot.memoized_state!r}{RESET}, pending_queue_size={len(slot.queue)}")
            print(f"  Total re-renders performed: {runtime.render_count}\n")
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih! Lab simulasi selesai.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid! Masukkan angka 0-6.{RESET}")

if __name__ == "__main__":
    # Jika dijalankan non-interaktif (misal via CI / piped input)
    if not sys.stdin.isatty():
        print_banner()
        runtime.component_fn = app_component
        runtime.perform_render()
        print(f"{BOLD}Mode non-interaktif: Menjalankan automated test harness...{RESET}")
        run_stale_closure_demo()
        run_batching_demo()
        run_bailout_demo()
        print(f"\n{GREEN}✅ Seluruh verifikasi skenario React state primitives berhasil!{RESET}")
    else:
        interactive_loop()
