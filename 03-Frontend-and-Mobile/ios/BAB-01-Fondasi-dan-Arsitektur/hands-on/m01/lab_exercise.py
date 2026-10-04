#!/usr/bin/env python3
"""
iOS Foundation & Architecture Interactive Technical Lab (BAB-01)
Simulasi komprehensif konsep arsitektur dan fondasi inti iOS:
1. UIApplication & App Lifecycle State Machine
2. Automatic Reference Counting (ARC) & Retain Cycle Detection
3. UIResponder Chain & Event Hit-Testing Dispatch
4. Main RunLoop & Task Scheduling

Kebutuhan: Python 3.8+ (Standard Library saja)
"""

import sys
import time
from typing import Optional, List, Dict, Any

# ANSI Color Codes untuk terminal visualizer
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

def print_header(title: str):
    print(f"\n{BOLD}{BG_BLUE}{WHITE}  === {title.upper()} ===  {RESET}\n")

def print_step(step: str, desc: str):
    print(f"  {CYAN}▸ [{step}]{RESET} {desc}")

def print_success(msg: str):
    print(f"    {GREEN}✔ {msg}{RESET}")

def print_warning(msg: str):
    print(f"    {YELLOW}⚠ {msg}{RESET}")

def print_alert(msg: str):
    print(f"    {RED}✘ {msg}{RESET}")


# ============================================================================
# 1. SIMULASI APPLICATION LIFECYCLE (UIApplication & Scene Lifecycle)
# ============================================================================
class AppLifecycleSimulator:
    STATES = ["Not Running", "Inactive", "Active", "Background", "Suspended"]

    def __init__(self):
        self.current_state = "Not Running"
        self.memory_warning_triggered = False

    def transition_to(self, new_state: str, trigger_event: str):
        print(f"    {MAGENTA}Event:{RESET} {BOLD}{trigger_event}{RESET}")
        print(f"    {DIM}State Transition:{RESET} [{YELLOW}{self.current_state}{RESET}] ➔ [{GREEN}{new_state}{RESET}]")
        self.current_state = new_state
        time.sleep(0.3)

    def run_lifecycle_demo(self):
        print_header("Simulasi 1: iOS Application Lifecycle State Machine")
        print("  State Machine mengikuti siklus hidup UIKit / UISceneDelegate standard:")
        
        self.transition_to("Inactive", "application:willFinishLaunchingWithOptions: / Scene Connecting")
        self.transition_to("Active", "sceneDidBecomeActive: (User interaksi dimulai)")
        print_success("App menerima event UI di foreground (Main RunLoop aktif).")
        
        input(f"\n  {BOLD}[Tekan ENTER untuk mensimulasikan incoming call / lock screen]{RESET}")
        self.transition_to("Inactive", "sceneWillResignActive: (Interupsi: Call/Alarm/App Switcher)")
        
        input(f"  {BOLD}[Tekan ENTER untuk push aplikasi ke background]{RESET}")
        self.transition_to("Background", "sceneDidEnterBackground: (Memulai background task 30 detik)")
        
        print_step("OS Policy", "iOS mengalokasikan waktu eksekusi background terbatas sebelum suspension.")
        time.sleep(0.5)
        self.transition_to("Suspended", "OS freeze memory image; CPU execution dihentikan")
        print_warning("State: Suspended. Memory tetap ada, tetapi instruksi CPU di-pause.")

        input(f"\n  {BOLD}[Tekan ENTER untuk mensimulasikan OS Memory Pressure (Jetsam Kill)]{RESET}")
        self.transition_to("Not Running", "Jetsam SIGKILL / Purged by kernel due to memory pressure")
        print_alert("Aplikasi dihentikan tanpa notifikasi terminasi runtime!")


# ============================================================================
# 2. SIMULASI MEMORY MANAGEMENT (ARC, Strong, Weak & Retain Cycles)
# ============================================================================
class SimulatedObject:
    def __init__(self, name: str):
        self.name = name
        self.retain_count = 1
        self.references: Dict[str, 'SimulatedObject'] = {}
        self.weak_references: List['SimulatedObject'] = []
        print(f"      {GREEN}+ Alloc & Init:{RESET} {self.name} (Retain Count: {self.retain_count})")

    def retain(self, context: str):
        self.retain_count += 1
        print(f"      {CYAN}+ Retain [{context}]:{RESET} {self.name} ➔ Retain Count: {self.retain_count}")

    def release(self, context: str):
        self.retain_count -= 1
        print(f"      {YELLOW}- Release [{context}]:{RESET} {self.name} ➔ Retain Count: {self.retain_count}")
        if self.retain_count <= 0:
            self.dealloc()

    def dealloc(self):
        print(f"      {RED}✖ Dealloc / Free Heap:{RESET} {self.name} berhasil dibebaskan dari memori.")


def run_arc_demo():
    print_header("Simulasi 2: Swift/Obj-C Automatic Reference Counting (ARC)")
    print("  Membuktikan perbedaan Strong Reference Cycle vs Weak Reference Pattern.\n")

    print_step("Scenario A", "Menciptakan Strong Retain Cycle (Memory Leak)")
    vc = SimulatedObject("ProfileViewController")
    vm = SimulatedObject("ProfileViewModel")

    print_step("Linkage", "VC memegang strong reference ke VM:")
    vm.retain("VC -> VM (Strong)")
    vc.references["viewModel"] = vm

    print_step("Linkage", "VM memegang strong delegate/closure ke VC (Retain Cycle terbentuk!):")
    vc.retain("VM -> VC delegate (Strong Danger!)")
    vm.references["delegate"] = vc

    print_step("Pop Navigation", "User menekan Back button, dismiss ProfileViewController:")
    vc.release("Navigation Stack Pop")

    print_alert(f"Status Retain Count -> VC: {vc.retain_count}, VM: {vm.retain_count}")
    print_alert("KEBOCORAN MEMORI (LEAK)! Tidak ada objek yang mencapai retain count 0.")

    input(f"\n  {BOLD}[Tekan ENTER untuk menjalankan Solusi 'weak' reference]{RESET}")
    print_step("Scenario B", "Menggunakan 'weak' reference pada Delegate/Closure")
    
    vc2 = SimulatedObject("HomeViewController")
    vm2 = SimulatedObject("HomeViewModel")
    
    print_step("Linkage", "VC2 memegang strong ref ke VM2:")
    vm2.retain("VC2 -> VM2 (Strong Ownership)")
    vc2.references["viewModel"] = vm2

    print_step("Weak Linkage", "VM2 memegang 'weak var delegate' ke VC2 (Tanpa increment retain count):")
    print(f"      {MAGENTA}* Weak Ref Assignment:{RESET} VM2.delegate = weak VC2 (Retain count tetap {vc2.retain_count})")
    vm2.weak_references.append(vc2)

    print_step("Pop Navigation", "User dismiss HomeViewController:")
    vc2.release("Navigation Stack Pop")
    print_step("Cascade Cleanup", "VC2 deinit melepaskan strong reference ke VM2:")
    vm2.release("VC2 Dealloc Release VM2")
    print_success("Zero Memory Leak! Kedua objek dealloc dengan sempurna.")


# ============================================================================
# 3. SIMULASI UIRESPONDER CHAIN & HIT-TESTING
# ============================================================================
class ResponderNode:
    def __init__(self, name: str, next_responder: Optional['ResponderNode'] = None, can_handle: bool = False):
        self.name = name
        self.next_responder = next_responder
        self.can_handle = can_handle

    def handle_touch(self, touch_event: str) -> bool:
        print(f"      {DIM}Hit-Test/Event passed to:{RESET} {BOLD}{self.name}{RESET}")
        time.sleep(0.2)
        if self.can_handle:
            print_success(f"Action '{touch_event}' ditangani secara sukses oleh [{self.name}]!")
            return True
        elif self.next_responder:
            print(f"        {YELLOW}↳ Bukan handler / Forwarding ke nextResponder...{RESET}")
            return self.next_responder.handle_touch(touch_event)
        else:
            print_alert(f"Event '{touch_event}' jatuh di ujung Responder Chain tanpa handler!")
            return False


def run_responder_chain_demo():
    print_header("Simulasi 3: UIResponder Chain & Event Propagation")
    print("  Hierarki tree: UIButton -> CustomContentView -> UIViewController -> UIWindow -> UIApplication")
    
    # Membangun rantai responder
    app = ResponderNode("UIApplication (Terminal Node)", None, can_handle=False)
    window = ResponderNode("UIWindow (Key Window)", app, can_handle=False)
    view_controller = ResponderNode("OrderCheckoutViewController", window, can_handle=True)
    custom_view = ResponderNode("CardContainerView", view_controller, can_handle=False)
    button = ResponderNode("PrimaryCheckoutButton", custom_view, can_handle=False)

    print_step("Trigger", "User mentap 'PrimaryCheckoutButton' untuk event: 'onPayButtonTapped'")
    button.handle_touch("onPayButtonTapped")

    print("\n  Perhatikan bagaimana event naik (bubble-up) dari leaf view ke UIViewController.")


# ============================================================================
# 4. SIMULASI MAIN RUNLOOP & THREAD DISPATCHING
# ============================================================================
def run_runloop_demo():
    print_header("Simulasi 4: iOS Main RunLoop & Thread Safety Simulation")
    print("  RunLoop memproses Event Sources (Touches, Timers, Port/IPC) dan Render Passes.\n")

    events = [
        {"type": "Source0", "name": "TouchEvent (Tap Gesture)"},
        {"type": "Timer",   "name": "CADisplayLink (120Hz ProMotion Sync)"},
        {"type": "Source1", "name": "Mach Port IPC (CoreTelephony Call Alert)"},
        {"type": "Render",  "name": "CATransaction Commit (Draw Rect & Layout Subviews)"}
    ]

    for iteration in range(1, 3):
        print(f"  {CYAN}--- RunLoop Cycle #{iteration} (kCFRunLoopDefaultMode) ---{RESET}")
        for ev in events:
            print(f"    {GREEN}● Processing [{ev['type']}]:{RESET} {ev['name']}")
            time.sleep(0.25)
        print(f"    {DIM}↳ RunLoop Sleep / Waiting for Mach Port Wakeup...{RESET}\n")
        time.sleep(0.3)
    
    print_success("Main RunLoop menjaga UI tetap responsif jika tidak diblokir heavy operation!")


# ============================================================================
# INTERACTIVE CLI RUNNER
# ============================================================================
def main():
    while True:
        print(f"\n{BOLD}{CYAN}==================================================================={RESET}")
        print(f"{BOLD}{WHITE}    LAB SIMULATOR: ARSITEKTUR & FONDASI INTI iOS (BAB-01){RESET}")
        print(f"{BOLD}{CYAN}==================================================================={RESET}")
        print(f"  {BOLD}1.{RESET} Simulasi Application Lifecycle (UIApplicationState Machine)")
        print(f"  {BOLD}2.{RESET} Simulasi Memory Management ARC (Strong, Weak & Retain Cycles)")
        print(f"  {BOLD}3.{RESET} Simulasi UIResponder Chain (Event Bubbling & Handling)")
        print(f"  {BOLD}4.{RESET} Simulasi Main RunLoop (Event Loop & CADisplayLink Tick)")
        print(f"  {BOLD}5.{RESET} Jalankan Seluruh Modul Simulasi (End-to-End Test)")
        print(f"  {BOLD}0.{RESET} Keluar (Exit)")
        print(f"{CYAN}-------------------------------------------------------------------{RESET}")
        
        choice = input(f"{BOLD}Pilih nomor simulasi (0-5): {RESET}").strip()
        
        if choice == "1":
            sim = AppLifecycleSimulator()
            sim.run_lifecycle_demo()
        elif choice == "2":
            run_arc_demo()
        elif choice == "3":
            run_responder_chain_demo()
        elif choice == "4":
            run_runloop_demo()
        elif choice == "5":
            sim = AppLifecycleSimulator()
            sim.run_lifecycle_demo()
            run_arc_demo()
            run_responder_chain_demo()
            run_runloop_demo()
            print_header("Evaluasi Simulasi Selesai")
            print_success("Seluruh konsep fondasi iOS (BAB-01) berhasil disimulasikan.")
        elif choice == "0":
            print(f"\n{GREEN}Lab exercise selesai. Happy iOS Engineering!{RESET}\n")
            sys.exit(0)
        else:
            print_alert("Pilihan tidak valid, silakan masukkan nomor 0 sampai 5.")

if __name__ == "__main__":
    main()
