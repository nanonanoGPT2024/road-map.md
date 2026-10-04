#!/usr/bin/env python3
"""
Lab Exercise: Android Core Foundations & Architecture Simulator
BAB-01-Fondasi-dan-Arsitektur - Modul 01

Simulasi komprehensif konsep arsitektur Android:
1. Android OS Platform Architecture Stack (Kernel -> HAL -> ART -> Framework -> Apps)
2. Activity Lifecycle State Machine & Task/BackStack Manager
3. Looper, MessageQueue, dan Handler Event-Loop Concurrency Model
4. Android Process Priority & Low Memory Killer (LMK / OOM ADJ) Simulation
"""

import sys
import time
import os
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable


# ==============================================================================
# ANSI Color Palette for Terminal UI
# ==============================================================================
class Color:
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
    BG_GREEN = "\033[42m"
    BG_DARK = "\033[40m"


def header(title: str):
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {title} === {Color.RESET}\n")


def status_badge(label: str, color: str = Color.CYAN) -> str:
    return f"{color}{Color.BOLD}[{label}]{Color.RESET}"


# ==============================================================================
# 1. Android Platform Architecture Stack Visualizer
# ==============================================================================
def display_android_stack():
    header("ANDROID OS ARCHITECTURE STACK (LAYER-BY-LAYER)")
    stack_layers = [
        ("APPLICATIONS", Color.GREEN, [
            "Dialer, SMS, Camera, Settings, Custom User Apps (Kotlin/Java)"
        ]),
        ("JAVA API FRAMEWORK", Color.CYAN, [
            "ActivityManager, WindowManager, ContentProviders, ViewSystem, NotificationManager",
            "Package Manager, Telephony Manager, Resource Manager"
        ]),
        ("ANDROID RUNTIME (ART) & NATIVE C/C++ LIBRARIES", Color.YELLOW, [
            "ART: Ahead-of-Time (AOT) + Just-in-Time (JIT) Compiler, Compact Garbage Collector",
            "Native Libraries: WebKit, Media Framework, SQLite, OpenGL ES, FreeType, Bionic Libc"
        ]),
        ("HARDWARE ABSTRACTION LAYER (HAL)", Color.MAGENTA, [
            "HIDL / AIDL HAL Interfaces: Camera HAL, Audio HAL, Bluetooth HAL, Sensors HAL, Gralloc"
        ]),
        ("LINUX KERNEL", Color.RED, [
            "Kernel Drivers: Binder IPC Driver, Ashmem, Low Memory Killer Daemon (LMKD)",
            "Power Management (Wakelocks), Display Driver, USB Driver, Wi-Fi Drivers"
        ]),
    ]

    for title, col, details in stack_layers:
        border = "=" * 70
        print(f"{col}{Color.BOLD}+{border}+{Color.RESET}")
        print(f"{col}{Color.BOLD}| {title.center(68)} |{Color.RESET}")
        print(f"{col}+{'-' * 70}+{Color.RESET}")
        for d in details:
            print(f"{col}|  * {d:<65} |{Color.RESET}")
        print(f"{col}+{border}+{Color.RESET}\n")


# ==============================================================================
# 2. Activity Lifecycle State Machine & BackStack Simulation
# ==============================================================================
class ActivityState(Enum):
    NON_EXISTENT = auto()
    CREATED = auto()
    STARTED = auto()
    RESUMED = auto()
    PAUSED = auto()
    STOPPED = auto()
    DESTROYED = auto()


@dataclass
class ActivityRecord:
    name: str
    state: ActivityState = ActivityState.NON_EXISTENT
    saved_bundle: Dict[str, str] = field(default_factory=dict)

    def transition_to(self, new_state: ActivityState, reason: str = ""):
        old = self.state.name
        self.state = new_state
        print(f"  {status_badge(self.name, Color.YELLOW)} State: "
              f"{Color.DIM}{old}{Color.RESET} -> {Color.BOLD}{Color.GREEN}{new_state.name}{Color.RESET} "
              f"({Color.CYAN}{reason}{Color.RESET})")


class TaskBackStack:
    def __init__(self, task_name: str = "MainActivityTask"):
        self.task_name = task_name
        self.stack: List[ActivityRecord] = []

    def current_top(self) -> Optional[ActivityRecord]:
        return self.stack[-1] if self.stack else None

    def start_activity(self, name: str):
        print(f"\n{status_badge('INTENT', Color.MAGENTA)} Launching Activity: {Color.BOLD}{name}{Color.RESET}")
        curr = self.current_top()
        if curr and curr.state == ActivityState.RESUMED:
            curr.transition_to(ActivityState.PAUSED, "onPause: relinquishing foreground window")

        new_act = ActivityRecord(name=name)
        new_act.transition_to(ActivityState.CREATED, "onCreate: inflating layout, init ViewModel")
        new_act.transition_to(ActivityState.STARTED, "onStart: UI becoming visible to user")
        new_act.transition_to(ActivityState.RESUMED, "onResume: active window, receiving user input")

        if curr and curr.state == ActivityState.PAUSED:
            curr.transition_to(ActivityState.STOPPED, "onStop: window completely covered / hidden")

        self.stack.append(new_act)

    def press_back(self):
        if not self.stack:
            print(f"  {status_badge('BACK_STACK', Color.RED)} Back stack is empty!")
            return

        top = self.stack.pop()
        print(f"\n{status_badge('BACK_PRESSED', Color.YELLOW)} Popping: {Color.BOLD}{top.name}{Color.RESET}")
        top.transition_to(ActivityState.PAUSED, "onPause: losing focus")
        top.transition_to(ActivityState.STOPPED, "onStop: view hidden")
        top.transition_to(ActivityState.DESTROYED, "onDestroy: finished/popped from backstack")

        resumed = self.current_top()
        if resumed:
            print(f"  {status_badge('NAVIGATE_RETURN', Color.GREEN)} Returning to previous Activity: {resumed.name}")
            if resumed.state == ActivityState.STOPPED:
                resumed.transition_to(ActivityState.STARTED, "onRestart -> onStart: restoring visibility")
            resumed.transition_to(ActivityState.RESUMED, "onResume: regaining foreground input focus")
        else:
            print(f"  {status_badge('TASK_FINISHED', Color.RED)} Root activity destroyed. Task stack exited.")

    def simulate_config_change(self):
        curr = self.current_top()
        if not curr:
            print("  No activity to rotate!")
            return
        print(f"\n{status_badge('ORIENTATION_CHANGE', Color.CYAN)} Screen Rotation on {curr.name} (Configuration Change)")
        curr.saved_bundle["edit_text_cache"] = "Simulated Form Data @ timestamp " + str(int(time.time()))
        print(f"  {status_badge(curr.name, Color.YELLOW)} onSaveInstanceState: Bundled {curr.saved_bundle}")

        curr.transition_to(ActivityState.PAUSED, "onPause")
        curr.transition_to(ActivityState.STOPPED, "onStop")
        curr.transition_to(ActivityState.DESTROYED, "onDestroy (recreation teardown)")

        # Rebirth
        curr.transition_to(ActivityState.CREATED, f"onCreate(savedInstanceState={curr.saved_bundle})")
        curr.transition_to(ActivityState.STARTED, "onStart")
        print(f"  {status_badge(curr.name, Color.YELLOW)} onRestoreInstanceState: Restored state successfully!")
        curr.transition_to(ActivityState.RESUMED, "onResume")

    def print_stack(self):
        print(f"\n{Color.BOLD}Current BackStack State [{self.task_name}]:{Color.RESET}")
        if not self.stack:
            print("  [ <Empty Stack> ]")
            return
        for idx, act in enumerate(reversed(self.stack)):
            marker = "--> (TOP/RESUMED)" if idx == 0 else "    (INACTIVE)   "
            print(f"  {marker} [{len(self.stack)-1-idx}] {act.name:<18} | State: {act.state.name}")


# ==============================================================================
# 3. Looper, MessageQueue, and Handler Simulation
# ==============================================================================
@dataclass
class Message:
    what: int
    data: str
    target_handler_name: str
    uptime_millis: float


class MessageQueue:
    def __init__(self):
        self.messages: List[Message] = []

    def enqueue(self, msg: Message):
        self.messages.append(msg)
        self.messages.sort(key=lambda m: m.uptime_millis)

    def next(self) -> Optional[Message]:
        if not self.messages:
            return None
        return self.messages.pop(0)


class Looper:
    def __init__(self, thread_name: str):
        self.thread_name = thread_name
        self.queue = MessageQueue()
        self.running = True

    def loop_step(self, handler_dispatch_callback: Callable[[Message], None]):
        msg = self.queue.next()
        if msg:
            handler_dispatch_callback(msg)
            return True
        return False


class Handler:
    def __init__(self, name: str, looper: Looper):
        self.name = name
        self.looper = looper

    def send_message(self, what: int, payload: str, delay_ms: float = 0.0):
        target_time = time.time() * 1000 + delay_ms
        msg = Message(what=what, data=payload, target_handler_name=self.name, uptime_millis=target_time)
        print(f"  {status_badge('HANDLER_POST', Color.BLUE)} {self.name} posted msg(what={what}, data='{payload}') delay={delay_ms}ms")
        self.looper.queue.enqueue(msg)

    def handle_message(self, msg: Message):
        print(f"  {status_badge('DISPATCH', Color.GREEN)} Thread: [{self.looper.thread_name}] "
              f"-> {self.name}.handleMessage(what={msg.what}, data='{msg.data}')")


def simulate_handler_looper():
    header("ANDROID UI THREAD EVENT LOOP (LOOPER, HANDLER, MESSAGE QUEUE)")
    print("Inisialisasi MainThread (UI Thread) Looper & Handler...")
    main_looper = Looper("main_ui_thread")
    ui_handler = Handler("ViewRootHandler", main_looper)
    bg_worker_handler = Handler("WorkerResultHandler", main_looper)

    print("\nMensimulasikan pengiriman pesan dari background thread ke UI thread:")
    ui_handler.send_message(what=101, payload="CLICK_EVENT_BUTTON_SUBMIT")
    bg_worker_handler.send_message(what=200, payload="HTTP_RESPONSE_JSON_PARSED", delay_ms=50)
    ui_handler.send_message(what=102, payload="REPAINT_SURFACE_FRAME")

    print(f"\n{Color.BOLD}Looper.loop() processing MessageQueue sequentially:{Color.RESET}")
    while True:
        processed = main_looper.loop_step(lambda msg: (
            ui_handler.handle_message(msg) if msg.target_handler_name == ui_handler.name
            else bg_worker_handler.handle_message(msg)
        ))
        if not processed:
            break
    print(f"{Color.GREEN}Semua pesan dalam MessageQueue telah selesai diproses tanpa blocking UI Thread.{Color.RESET}")


# ==============================================================================
# 4. Android Process Priority & Low Memory Killer (LMK) Simulation
# ==============================================================================
@dataclass
class AndroidProcess:
    pid: int
    name: str
    oom_adj: int  # -1000 to 1000 (lower means higher priority)
    category: str
    ram_mb: int


def simulate_lmk_memory_trim():
    header("ANDROID LOW MEMORY KILLER (LMKD) & OOM_SCORE_ADJ SIMULATION")
    processes = [
        AndroidProcess(pid=1012, name="system_server", oom_adj=-1000, category="SYSTEM_PERSISTENT", ram_mb=450),
        AndroidProcess(pid=2150, name="com.android.launcher", oom_adj=0, category="FOREGROUND_APP", ram_mb=180),
        AndroidProcess(pid=3340, name="com.spotify.music:player", oom_adj=200, category="PERCEPTIBLE_SERVICE", ram_mb=210),
        AndroidProcess(pid=4512, name="com.whatsapp", oom_adj=700, category="PREVIOUS_RECENT_APP", ram_mb=290),
        AndroidProcess(pid=5981, name="com.tokopedia.app", oom_adj=900, category="CACHED_BACKGROUND_EMPTY", ram_mb=320),
        AndroidProcess(pid=6104, name="com.game.racing3d", oom_adj=950, category="CACHED_BACKGROUND_APP", ram_mb=580),
    ]

    print(f"{'PID':<6} | {'PROCESS NAME':<26} | {'CATEGORY':<22} | {'OOM_ADJ':<8} | {'RAM (MB)':<8}")
    print("-" * 78)
    for p in processes:
        col = Color.GREEN if p.oom_adj <= 0 else (Color.YELLOW if p.oom_adj < 800 else Color.RED)
        print(f"{p.pid:<6} | {p.name:<26} | {p.category:<22} | {col}{p.oom_adj:<8}{Color.RESET} | {p.ram_mb} MB")

    print(f"\n{status_badge('SYS_EVENT', Color.RED)} Skenario: Device mengalami TEKANAN RAM KRITIS (RAM Free < 300 MB)")
    print(f"{Color.YELLOW}LMKD (Low Memory Killer Daemon) mengorbankan proses dengan oom_adj tertinggi lebih dahulu:{Color.RESET}\n")

    reclaimed_ram = 0
    target_to_free = 800
    for p in sorted(processes, key=lambda x: x.oom_adj, reverse=True):
        if p.oom_adj < 0:
            print(f"  {status_badge('PROTECTED', Color.GREEN)} {p.name} (oom_adj={p.oom_adj}) dilindungi oleh OS.")
            continue

        print(f"  {status_badge('SIGKILL_SENT', Color.RED)} LMK membunuh PID {p.pid} ({p.name}) | oom_adj={p.oom_adj} | Bebaskan {p.ram_mb} MB")
        reclaimed_ram += p.ram_mb
        if reclaimed_ram >= target_to_free:
            print(f"\n{Color.GREEN}{Color.BOLD}Target RAM pulih (+{reclaimed_ram} MB). System kembali normal.{Color.RESET}")
            break


# ==============================================================================
# Main Interactive CLI Controller
# ==============================================================================
def main_interactive_menu():
    task_stack = TaskBackStack("E-Commerce-Task")

    while True:
        print("\n" + "=" * 65)
        print(f"{Color.CYAN}{Color.BOLD}   ANDROID CORE FOUNDATIONS & ARCHITECTURE LAB (BAB-01){Color.RESET}")
        print("=" * 65)
        print(f" {Color.WHITE}1.{Color.RESET} Tampilkan Arsitektur Android OS (Layer Visualizer)")
        print(f" {Color.WHITE}2.{Color.RESET} Simulasi Activity Lifecycle & Task BackStack")
        print(f" {Color.WHITE}3.{Color.RESET} Simulasi Configuration Change (Screen Rotation & State Bundle)")
        print(f" {Color.WHITE}4.{Color.RESET} Simulasi UI Thread Looper, MessageQueue, & Handler")
        print(f" {Color.WHITE}5.{Color.RESET} Simulasi Low Memory Killer (LMK) & OOM Score Adj")
        print(f" {Color.WHITE}6.{Color.RESET} Jalankan Automated Full Lifecycle Walkthrough")
        print(f" {Color.WHITE}0.{Color.RESET} Keluar (Exit)")
        print("-" * 65)

        try:
            choice = input(f"{Color.BOLD}Pilih opsi simulasi [0-6]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            display_android_stack()
        elif choice == "2":
            header("ACTIVITY TASK & BACKSTACK SIMULATOR")
            task_stack.print_stack()
            print("\nSub-menu:")
            print("  [a] Push HomeActivity")
            print("  [b] Push ProductListActivity")
            print("  [c] Push ProductDetailActivity")
            print("  [p] Press Back Button")
            sub = input("  Aksi [a/b/c/p]: ").strip().lower()
            if sub == "a":
                task_stack.start_activity("HomeActivity")
            elif sub == "b":
                task_stack.start_activity("ProductListActivity")
            elif sub == "c":
                task_stack.start_activity("ProductDetailActivity")
            elif sub == "p":
                task_stack.press_back()
            task_stack.print_stack()
        elif choice == "3":
            if not task_stack.current_top():
                task_stack.start_activity("CheckoutActivity")
            task_stack.simulate_config_change()
            task_stack.print_stack()
        elif choice == "4":
            simulate_handler_looper()
        elif choice == "5":
            simulate_lmk_memory_trim()
        elif choice == "6":
            header("AUTOMATED COMPLETE ARCHITECTURE WALKTHROUGH")
            display_android_stack()
            auto_stack = TaskBackStack("DemoTask")
            auto_stack.start_activity("SplashActivity")
            auto_stack.start_activity("DashboardActivity")
            auto_stack.start_activity("ProfileActivity")
            auto_stack.print_stack()
            auto_stack.simulate_config_change()
            auto_stack.press_back()
            auto_stack.press_back()
            auto_stack.press_back()
            simulate_handler_looper()
            simulate_lmk_memory_trim()
        elif choice == "0":
            print(f"\n{Color.GREEN}Simulasi selesai. Lab exercise siap digunakan.{Color.RESET}")
            sys.exit(0)
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan coba lagi.{Color.RESET}")


if __name__ == "__main__":
    main_interactive_menu()
