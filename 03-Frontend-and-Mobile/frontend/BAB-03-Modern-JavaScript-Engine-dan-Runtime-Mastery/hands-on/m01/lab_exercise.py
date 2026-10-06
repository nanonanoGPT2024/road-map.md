#!/usr/bin/env python3
"""
Lab Exercise: JavaScript Engine & Runtime Internals Simulator (V8 & Event Loop)
BAB-03: Modern JavaScript Engine dan Runtime Mastery
-------------------------------------------------------------------------------
Simulasi teknis interaktif Python 3 mandiri untuk:
 1. Pipeline V8: Parser -> Ignition (Bytecode) -> TurboFan (JIT Speculation & Deopt)
 2. Object Shapes & Hidden Classes (Maps) + Inline Caching (Monomorphic vs Polymorphic)
 3. V8 Generational Garbage Collection: Scavenger (Semi-Space) & Mark-Sweep
 4. ECMAScript Event Loop: Call Stack, Microtasks (Promise/queueMicrotask), Macrotasks (Timer/IO)
"""

import sys
import time
import dataclasses
from collections import deque
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Tuple


# ==============================================================================
# Terminal ANSI Formatting Helpers
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright Foreground
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"

    # Backgrounds
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[100m"


def banner(title: str) -> None:
    line = "═" * 70
    print(f"\n{Color.BRIGHT_CYAN}{line}")
    print(f"  {Color.BOLD}{title.center(66)}{Color.RESET}{Color.BRIGHT_CYAN}")
    print(f"{line}{Color.RESET}\n")


def section_header(title: str) -> None:
    print(f"\n{Color.BRIGHT_YELLOW}┌── [ {Color.BOLD}{title}{Color.RESET}{Color.BRIGHT_YELLOW} ]" + "─" * (64 - len(title)) + f"{Color.RESET}")


# ==============================================================================
# Bagian 1: Simulasi Hidden Classes (Maps) & Inline Caching (IC)
# ==============================================================================
class MapTransition:
    """Representasi V8 Hidden Class (Shape/Map) transitions"""
    def __init__(self, map_id: str, property_added: Optional[str] = None, offset: int = 0):
        self.map_id = map_id
        self.property_added = property_added
        self.offset = offset
        self.transitions: Dict[str, "MapTransition"] = {}

    def get_or_create_transition(self, prop: str, counter: List[int]) -> "MapTransition":
        if prop not in self.transitions:
            counter[0] += 1
            new_map_id = f"Map_{counter[0]:02d}"
            next_offset = self.offset + 1
            self.transitions[prop] = MapTransition(new_map_id, prop, next_offset)
        return self.transitions[prop]


class V8Object:
    """Objek JS dengan pointer ke V8 Map & Storage Slot terindeks"""
    def __init__(self, name: str, root_map: MapTransition, map_counter: List[int]):
        self.name = name
        self.current_map = root_map
        self.properties: Dict[str, Any] = {}
        self.map_counter = map_counter

    def set_property(self, prop: str, val: Any) -> Tuple[str, str]:
        old_map_id = self.current_map.map_id
        if prop not in self.properties:
            self.current_map = self.current_map.get_or_create_transition(prop, self.map_counter)
        self.properties[prop] = val
        return old_map_id, self.current_map.map_id


class InlineCacheState(Enum):
    UNINITIALIZED = auto()
    MONOMORPHIC = auto()
    POLYMORPHIC = auto()
    MEGAMORPHIC = auto()


class InlineCacheSite:
    """Feedback Vector slot untuk IC property access"""
    def __init__(self, property_name: str):
        self.property_name = property_name
        self.state = InlineCacheState.UNINITIALIZED
        self.recorded_maps: Dict[str, int] = {}  # map_id -> slot_offset

    def access(self, obj: V8Object) -> Any:
        map_id = obj.current_map.map_id
        val = obj.properties.get(self.property_name, None)

        if self.state == InlineCacheState.UNINITIALIZED:
            self.state = InlineCacheState.MONOMORPHIC
            self.recorded_maps[map_id] = obj.current_map.offset
            print(f"    {Color.CYAN}IC [load .{self.property_name}]: {Color.YELLOW}UNINITIALIZED -> MONOMORPHIC {Color.RESET}(Map: {map_id})")
        elif self.state == InlineCacheState.MONOMORPHIC:
            if map_id in self.recorded_maps:
                print(f"    {Color.GREEN}IC [load .{self.property_name}]: FAST PATH MONOMORPHIC HIT! {Color.RESET}(Map: {map_id})")
            else:
                self.recorded_maps[map_id] = obj.current_map.offset
                self.state = InlineCacheState.POLYMORPHIC
                print(f"    {Color.YELLOW}IC [load .{self.property_name}]: POLYMORPHIC TRANSITION {Color.RESET}(Maps registered: {list(self.recorded_maps.keys())})")
        elif self.state == InlineCacheState.POLYMORPHIC:
            if map_id in self.recorded_maps:
                print(f"    {Color.GREEN}IC [load .{self.property_name}]: POLYMORPHIC HIT {Color.RESET}(Map: {map_id} in {len(self.recorded_maps)} cached variants)")
            else:
                self.recorded_maps[map_id] = obj.current_map.offset
                if len(self.recorded_maps) > 4:
                    self.state = InlineCacheState.MEGAMORPHIC
                    print(f"    {Color.RED}{Color.BOLD}IC [load .{self.property_name}]: MEGAMORPHIC DE-OPTIMIZATION! {Color.RESET}(Too many maps: {len(self.recorded_maps)}. Falling back to dictionary lookup)")
                else:
                    print(f"    {Color.YELLOW}IC [load .{self.property_name}]: POLYMORPHIC MISS -> Added {map_id}{Color.RESET}")
        elif self.state == InlineCacheState.MEGAMORPHIC:
            print(f"    {Color.RED}IC [load .{self.property_name}]: SLOW PATH MEGAMORPHIC DICTIONARY SEARCH! {Color.RESET}(Map: {map_id})")

        return val


def run_v8_hidden_classes_demo():
    section_header("1. V8 HIDDEN CLASSES & INLINE CACHING (IC) ENGINE")
    print(f"{Color.DIM}Melihat bagaimana susunan inisialisasi properti mengubah Shape/Map objek,{Color.RESET}")
    print(f"{Color.DIM}serta dampaknya terhadap optimasi Inline Cache (Monomorphic -> Polymorphic -> Megamorphic).{Color.RESET}\n")

    map_counter = [0]
    root_map = MapTransition("Map_00 (Root)")

    # Objek A: urutan { x, y }
    obj_a = V8Object("point_A", root_map, map_counter)
    old_m, new_m = obj_a.set_property("x", 10)
    print(f"  {Color.BOLD}{obj_a.name}.x = 10{Color.RESET}    -> Transition: {Color.BLUE}{old_m}{Color.RESET} ──(+x)──> {Color.GREEN}{new_m}{Color.RESET}")
    old_m, new_m = obj_a.set_property("y", 20)
    print(f"  {Color.BOLD}{obj_a.name}.y = 20{Color.RESET}    -> Transition: {Color.BLUE}{old_m}{Color.RESET} ──(+y)──> {Color.GREEN}{new_m}{Color.RESET}")

    # Objek B: urutan yang sama { x, y } -> Reusing existing Shape
    obj_b = V8Object("point_B", root_map, map_counter)
    old_m, new_m = obj_b.set_property("x", 100)
    print(f"\n  {Color.BOLD}{obj_b.name}.x = 100{Color.RESET}   -> Transition: {Color.BLUE}{old_m}{Color.RESET} ──(+x)──> {Color.GREEN}{new_m} (Shared!){Color.RESET}")
    old_m, new_m = obj_b.set_property("y", 200)
    print(f"  {Color.BOLD}{obj_b.name}.y = 200{Color.RESET}   -> Transition: {Color.BLUE}{old_m}{Color.RESET} ──(+y)──> {Color.GREEN}{new_m} (Shared!){Color.RESET}")

    # Objek C: urutan terbalik { y, x } -> Cabang shape baru! (Bentuk polymorphism)
    obj_c = V8Object("point_C", root_map, map_counter)
    old_m, new_m = obj_c.set_property("y", 5)
    print(f"\n  {Color.BOLD}{obj_c.name}.y = 5{Color.RESET}     -> Transition: {Color.BLUE}{old_m}{Color.RESET} ──(+y)──> {Color.MAGENTA}{new_m} (Branch!){Color.RESET}")
    old_m, new_m = obj_c.set_property("x", 15)
    print(f"  {Color.BOLD}{obj_c.name}.x = 15{Color.RESET}    -> Transition: {Color.BLUE}{old_m}{Color.RESET} ──(+x)──> {Color.MAGENTA}{new_m} (Branch!){Color.RESET}")

    print(f"\n{Color.BRIGHT_CYAN}── Pengujian Call Site getX(obj) dengan Inline Caching ──{Color.RESET}")
    ic_site = InlineCacheSite("x")

    print(f"\n1. Panggilan 1 dengan point_A ({obj_a.current_map.map_id}):")
    ic_site.access(obj_a)

    print(f"2. Panggilan 2 dengan point_A ({obj_a.current_map.map_id}):")
    ic_site.access(obj_a)

    print(f"3. Panggilan 3 dengan point_B ({obj_b.current_map.map_id} - shape identik):")
    ic_site.access(obj_b)

    print(f"4. Panggilan 4 dengan point_C ({obj_c.current_map.map_id} - shape berbeda):")
    ic_site.access(obj_c)

    # Triggering Megamorphism
    print(f"\n5. Membuat 4 shape acak untuk memicu Megamorphism:")
    for i in range(1, 5):
        dummy = V8Object(f"shape_dummy_{i}", root_map, map_counter)
        dummy.set_property(f"rnd_prop_{i}", i)
        dummy.set_property("x", i * 10)
        ic_site.access(dummy)


# ==============================================================================
# Bagian 2: Simulasi V8 Generational Garbage Collector (Scavenger & Mark-Sweep)
# ==============================================================================
@dataclasses.dataclass
class HeapChunk:
    id: int
    label: str
    alive: bool
    age: int = 0  # siklus Scavenge bertahan


class V8GarbageCollector:
    """Simulasi Generational Memory Management V8:
       New Space (Semi-Space: From-Space & To-Space) + Old Space
    """
    def __init__(self, new_space_capacity: int = 4):
        self.from_space: List[HeapChunk] = []
        self.to_space: List[HeapChunk] = []
        self.old_space: List[HeapChunk] = []
        self.new_space_capacity = new_space_capacity
        self.id_seq = 1

    def allocate(self, label: str) -> HeapChunk:
        chunk = HeapChunk(id=self.id_seq, label=label, alive=True, age=0)
        self.id_seq += 1
        self.from_space.append(chunk)
        print(f"  {Color.GREEN}[Alloc]{Color.RESET} '{chunk.label}' (id={chunk.id}) dialokasikan di {Color.CYAN}NewSpace:FromSpace{Color.RESET}")
        return chunk

    def scavenge(self):
        """Cheney's Copying Algorithm (Minor GC)"""
        print(f"\n  {Color.BG_BLUE}{Color.WHITE} ── TRIGGER MINOR GC (SCAVENGER / SEMI-SPACE COPY) ── {Color.RESET}")
        survivors_to_space = []
        promoted_to_old = []

        for chunk in self.from_space:
            if not chunk.alive:
                print(f"    {Color.RED}[Dead Object] {chunk.label} diabaikan (dilepas dari memori){Color.RESET}")
                continue

            chunk.age += 1
            if chunk.age >= 2:
                # Promosi ke Old Space (Objek bertahan lama)
                self.old_space.append(chunk)
                promoted_to_old.append(chunk)
                print(f"    {Color.BRIGHT_MAGENTA}[Promotion] {chunk.label} (age={chunk.age}) dipromosikan ke OLD SPACE!{Color.RESET}")
            else:
                # Salin ke To-Space
                survivors_to_space.append(chunk)
                print(f"    {Color.GREEN}[Evacuate] {chunk.label} disalin ke To-Space (age={chunk.age}){Color.RESET}")

        # Swap From-Space & To-Space
        self.to_space = survivors_to_space
        self.from_space = self.to_space
        self.to_space = []
        print(f"  {Color.BLUE}Swap Selesai: From-Space sekarang berisi {len(self.from_space)} objek.{Color.RESET}")

    def major_gc(self):
        """Mark-Sweep-Compact di Old Space"""
        print(f"\n  {Color.BG_MAGENTA}{Color.WHITE} ── TRIGGER MAJOR GC (MARK-SWEEP-COMPACT) ── {Color.RESET}")
        print(f"    {Color.YELLOW}[Marking] Menelusuri Root Pointer objek aktif di Old Space...{Color.RESET}")
        survivors = []
        swept = 0
        for chunk in self.old_space:
            if chunk.alive:
                survivors.append(chunk)
                print(f"    {Color.GREEN}[Marked Alive] {chunk.label} (id={chunk.id}){Color.RESET}")
            else:
                swept += 1
                print(f"    {Color.RED}[Sweep] Membebaskan slot memori '{chunk.label}'{Color.RESET}")

        self.old_space = survivors
        print(f"    {Color.CYAN}[Compact] Menata ulang kontinuitas memori Old Space ({len(survivors)} objek tersisa, {swept} disapu).{Color.RESET}")


def run_v8_gc_demo():
    section_header("2. V8 MEMORY MANAGEMENT & GENERATIONAL GC")
    print(f"{Color.DIM}Simulasi Cheney's Algorithm (Minor GC / Scavenger) & Mark-Sweep (Major GC).{Color.RESET}\n")

    gc = V8GarbageCollector()

    # Siklus 1: Alokasi objek jangka pendek dan jangka panjang
    c1 = gc.allocate("DOMNode_temp")
    c2 = gc.allocate("GlobalState_auth")
    c3 = gc.allocate("ClosureCache_scoped")

    # c1 segera kehilangan referensi (garbage)
    print(f"\n  {Color.YELLOW}Dereferencing {c1.label} (c1 = null)...{Color.RESET}")
    c1.alive = False

    # Jalankan Scavenge 1
    gc.scavenge()

    # Siklus 2: Alokasi baru + Scavenge kedua untuk memicu promosi
    print(f"\n  {Color.YELLOW}Alokasi batch kedua & dereferencing {c3.label}...{Color.RESET}")
    c4 = gc.allocate("RenderTree_cache")
    c3.alive = False

    gc.scavenge()

    # Sekarang c2 harusnya sudah dipromosikan ke Old Space
    print(f"\n  {Color.YELLOW}Dereferencing {c2.label} di Old Space (c2 = null)...{Color.RESET}")
    c2.alive = False

    # Jalankan Major GC
    gc.major_gc()


# ==============================================================================
# Bagian 3: Simulasi ECMAScript Event Loop (Stack, Microtask, Macrotask)
# ==============================================================================
class TaskType(Enum):
    SYNC = auto()
    MICROTASK = auto()   # Promise.then, queueMicrotask, MutationObserver
    MACROTASK = auto()   # setTimeout, setInterval, setImmediate, I/O
    ANIMATION = auto()   # requestAnimationFrame (UI Render Step)


@dataclasses.dataclass
class ScheduledTask:
    name: str
    task_type: TaskType
    payload: str
    delay_ms: int = 0
    spawn_time: float = dataclasses.field(default_factory=time.time)


class EventLoopRuntime:
    """Simulator detail ECMAScript Single-Threaded Runtime"""
    def __init__(self):
        self.call_stack: List[str] = []
        self.microtask_queue: deque[ScheduledTask] = deque()
        self.macrotask_queue: deque[ScheduledTask] = deque()
        self.render_callbacks: List[ScheduledTask] = []
        self.tick_count = 0

    def push_stack(self, frame_name: str) -> None:
        self.call_stack.append(frame_name)
        print(f"  {Color.BRIGHT_BLUE}[STACK PUSH]{Color.RESET} ──> {frame_name} | Stack: {self.call_stack}")

    def pop_stack(self) -> None:
        if self.call_stack:
            popped = self.call_stack.pop()
            print(f"  {Color.BLUE}[STACK POP ]{Color.RESET} <── {popped} | Stack: {self.call_stack}")

    def queue_microtask(self, name: str, payload: str):
        task = ScheduledTask(name, TaskType.MICROTASK, payload)
        self.microtask_queue.append(task)
        print(f"    {Color.BRIGHT_CYAN}[+Microtask Enqueued]{Color.RESET} {name} ('{payload}')")

    def queue_macrotask(self, name: str, payload: str):
        task = ScheduledTask(name, TaskType.MACROTASK, payload)
        self.macrotask_queue.append(task)
        print(f"    {Color.BRIGHT_YELLOW}[+Macrotask Enqueued]{Color.RESET} {name} ('{payload}')")

    def run_event_loop_step(self):
        self.tick_count += 1
        print(f"\n{Color.BG_DARK}{Color.WHITE} ─── EVENT LOOP TICK #{self.tick_count} ─── {Color.RESET}")

        # 1. Jalankan SATU Macrotask tertua jika stack kosong
        if self.macrotask_queue:
            current_macro = self.macrotask_queue.popleft()
            print(f"  {Color.YELLOW}[Macrotask Dispatch]{Color.RESET} Menjalankan: {Color.BOLD}{current_macro.name}{Color.RESET}")
            self.push_stack(f"Execute({current_macro.name})")
            print(f"    {Color.WHITE}> Output: {current_macro.payload}{Color.RESET}")
            self.pop_stack()
        else:
            print(f"  {Color.DIM}(Tidak ada Macrotask yang menunggu){Color.RESET}")

        # 2. Flush SELURUH Microtask Queue hingga benar-benar habis (Starvation danger!)
        if self.microtask_queue:
            print(f"  {Color.CYAN}[Microtask Checkpoint]{Color.RESET} Menguras Microtask queue ({len(self.microtask_queue)} antrean)...")
            drain_count = 0
            while self.microtask_queue:
                drain_count += 1
                micro = self.microtask_queue.popleft()
                self.push_stack(f"Microtask({micro.name})")
                print(f"    {Color.BRIGHT_CYAN}★ Microtask #{drain_count}:{Color.RESET} {micro.name} -> {micro.payload}")
                self.pop_stack()
        else:
            print(f"  {Color.DIM}(Microtask Queue kosong){Color.RESET}")

        # 3. Render Step (Hanya berjalan berkala jika frame render diizinkan)
        if self.tick_count % 2 == 0:
            print(f"  {Color.MAGENTA}[Render Pipeline]{Color.RESET} Style Calc -> Layout -> Paint -> GPU Composite (60 FPS tick)")


def run_event_loop_demo():
    section_header("3. ECMASCRIPT EVENT LOOP, MICROTASKS & MACROTASKS")
    print(f"{Color.DIM}Simulasi deterministik eksekusi Script Sinkron, Promise (.then), dan Timer (setTimeout).{Color.RESET}\n")

    runtime = EventLoopRuntime()

    print(f"{Color.BOLD}Simulasi snippet JavaScript berikut:{Color.RESET}")
    js_code = """
    console.log('1. Synchronous Main script start');
    setTimeout(() => {
        console.log('2. Timeout 1 Macrotask');
        queueMicrotask(() => console.log('3. Microtask spawned inside Timeout 1'));
    }, 0);
    Promise.resolve().then(() => {
        console.log('4. Microtask Promise.then 1');
    }).then(() => {
        console.log('5. Microtask Promise.then 2 (Chained)');
    });
    console.log('6. Synchronous Main script end');
    """
    for l in js_code.strip().split("\n"):
        print(f"  {Color.DIM}{l}{Color.RESET}")
    print()

    # Eksekusi Script Sinkron Utama
    runtime.push_stack("main()")
    print(f"  {Color.WHITE}> Output: 1. Synchronous Main script start{Color.RESET}")

    # setTimeout dipanggil -> WebAPI mendaftarkan timer -> Macrotask queue
    runtime.queue_macrotask("setTimeout_cb1", "2. Timeout 1 Macrotask")

    # Promise.resolve() dipanggil -> Microtask queue
    runtime.queue_microtask("Promise.then_1", "4. Microtask Promise.then 1")

    print(f"  {Color.WHITE}> Output: 6. Synchronous Main script end{Color.RESET}")
    runtime.pop_stack()

    # Begitu Main script stack kosong, Microtask Checkpoint langsung dijalankan!
    print(f"\n{Color.BOLD}{Color.YELLOW}Main script selesai! Stack kosong -> Engine menjalankan Microtask Checkpoint seketika:{Color.RESET}")
    while runtime.microtask_queue:
        micro = runtime.microtask_queue.popleft()
        runtime.push_stack(f"Microtask({micro.name})")
        print(f"    {Color.BRIGHT_CYAN}★ Resolving:{Color.RESET} {micro.payload}")
        if micro.name == "Promise.then_1":
            # Chained microtask
            runtime.queue_microtask("Promise.then_2", "5. Microtask Promise.then 2 (Chained)")
        runtime.pop_stack()

    # Masuk ke siklus Event Loop reguler untuk Macrotasks
    print(f"\n{Color.BOLD}{Color.YELLOW}Memulai Perputaran Event Loop untuk Macrotask yang tersisa:{Color.RESET}")
    runtime.run_event_loop_step()

    # Simulasi microtask yang ditambahkan oleh setTimeout_cb1
    runtime.queue_microtask("nested_microtask", "3. Microtask spawned inside Timeout 1")
    runtime.run_event_loop_step()


# ==============================================================================
# Menu Interaktif & Runner
# ==============================================================================
def main():
    banner("MODERN JAVASCRIPT ENGINE & RUNTIME SIMULATOR (V8 / ECMASCRIPT)")
    print(f"{Color.BOLD}Pilih modul praktikum yang ingin dijalankan:{Color.RESET}")
    print(f"  [{Color.CYAN}1{Color.RESET}] Simulasi V8 Hidden Classes, Shapes & Inline Caching (IC)")
    print(f"  [{Color.CYAN}2{Color.RESET}] Simulasi V8 Generational Memory GC (Scavenger Semi-space & Mark-Sweep)")
    print(f"  [{Color.CYAN}3{Color.RESET}] Simulasi ECMAScript Event Loop (Stack, Microtask vs Macrotask)")
    print(f"  [{Color.CYAN}4{Color.RESET}] Jalankan Seluruh Rangkaian Lab Sekaligus")
    print(f"  [{Color.CYAN}0{Color.RESET}] Keluar")

    # Jika dijalankan non-interaktif atau dengan argumen CLI
    choice = "4"
    if len(sys.argv) > 1:
        choice = sys.argv[1].strip()
    else:
        try:
            user_input = input(f"\n{Color.BRIGHT_GREEN}Masukkan pilihan (0-4) [default: 4]: {Color.RESET}").strip()
            if user_input:
                choice = user_input
        except (EOFError, KeyboardInterrupt):
            print("\nNon-interactive session detected. Menjalankan modul default [4].")
            choice = "4"

    if choice == "1":
        run_v8_hidden_classes_demo()
    elif choice == "2":
        run_v8_gc_demo()
    elif choice == "3":
        run_event_loop_demo()
    elif choice == "4":
        run_v8_hidden_classes_demo()
        run_v8_gc_demo()
        run_event_loop_demo()
    elif choice == "0":
        print(f"\n{Color.YELLOW}Sesi lab diakhiri.{Color.RESET}")
        return
    else:
        print(f"{Color.RED}Pilihan tidak valid, menjalankan full suite.{Color.RESET}")
        run_v8_hidden_classes_demo()
        run_v8_gc_demo()
        run_event_loop_demo()

    print(f"\n{Color.BRIGHT_GREEN}✔ Lab Exercise selesai dieksekusi dengan sukses tanpa error.{Color.RESET}\n")


if __name__ == "__main__":
    main()
