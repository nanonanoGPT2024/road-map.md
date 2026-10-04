#!/usr/bin/env python3
"""
Lab Hands-on: PHP Internals Deep Dive
Topik: Functional Programming, Concurrency (Fibers) & Memory Management (Zval, COW, Cycle GC)
Kategori: 02-Programming-Languages / Bab 04 - Modul 02

Script ini mensimulasikan mekanisme internal Zend Engine (PHP 7/8):
1. Zval Memory Allocation & Copy-On-Write (COW) Semantics.
2. Concurrent Cooperative Multitasking via PHP 8.1 Fiber Simulation.
3. Concurrent Cyclic Garbage Collection menggunakan Bacon-Rajan Algorithm.
"""

from __future__ import annotations
import sys
import time
from typing import Any, Dict, List, Optional, Callable, Generator
from dataclasses import dataclass, field
from enum import Enum, auto

# ==============================================================================
# ANSI Color Formatting Helper
# ==============================================================================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def print_header(title: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*75}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN} [PHP ENGINE SIMULATION] {title.upper()}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*75}{Colors.RESET}")

def print_substep(tag: str, msg: str) -> None:
    print(f" {Colors.YELLOW}▸{Colors.RESET} {Colors.BOLD}{tag:<22}{Colors.RESET} : {msg}")


# ==============================================================================
# 1. ZEND MEMORY MANAGER: ZVAL & COPY-ON-WRITE (COW)
# ==============================================================================
class ZendType(Enum):
    IS_UNDEF = auto()
    IS_LONG = auto()
    IS_DOUBLE = auto()
    IS_STRING = auto()
    IS_ARRAY = auto()
    IS_OBJECT = auto()

class GCColor(Enum):
    BLACK = "BLACK"     # In use or freed
    WHITE = "WHITE"     # Candidate for garbage collection
    GREY = "GREY"       # Possible cycle member under examination
    PURPLE = "PURPLE"   # Suspected root of cycle

class ZendRefcounted:
    """Representasi struktur Zend zend_refcounted_h."""
    def __init__(self, value: Any, gc_type: ZendType):
        self.refcount: int = 1
        self.gc_color: GCColor = GCColor.BLACK
        self.value: Any = value
        self.type: ZendType = gc_type
        self.buffered: bool = False

@dataclass
class Zval:
    """Struktur Zval PHP 7/8 membungkus pointer ke zend_refcounted jika bertipe kompleks."""
    type: ZendType
    rc_obj: Optional[ZendRefcounted] = None
    scalar_value: Any = None

    @classmethod
    def create_string(cls, val: str) -> Zval:
        rc = ZendRefcounted(val, ZendType.IS_STRING)
        return cls(type=ZendType.IS_STRING, rc_obj=rc)

    @classmethod
    def create_array(cls, val: Dict[str, Zval]) -> Zval:
        rc = ZendRefcounted(val, ZendType.IS_ARRAY)
        return cls(type=ZendType.IS_ARRAY, rc_obj=rc)

    def addref(self) -> None:
        if self.rc_obj:
            self.rc_obj.refcount += 1

    def delref(self) -> int:
        if self.rc_obj:
            self.rc_obj.refcount -= 1
            return self.rc_obj.refcount
        return 0

    def write_array_key(self, key: str, value: Zval, gc_pool: ZendGC) -> None:
        """Simulasi Copy-On-Write (COW): Pisahkan buffer jika refcount > 1."""
        if not self.rc_obj or self.type != ZendType.IS_ARRAY:
            raise TypeError("Target bukan array yang dapat dimodifikasi.")

        if self.rc_obj.refcount > 1:
            print_substep("COW TRIGGERED", f"Refcount is {self.rc_obj.refcount}. Duplicating zend_array memory buffer.")
            self.rc_obj.refcount -= 1
            # Deep clone referensi array lokal
            cloned_elements: Dict[str, Zval] = {}
            for k, v in self.rc_obj.value.items():
                v.addref()
                cloned_elements[k] = v
            self.rc_obj = ZendRefcounted(cloned_elements, ZendType.IS_ARRAY)
            gc_pool.track(self.rc_obj)
        
        # Mutasi buffer array saat ini
        self.rc_obj.value[key] = value


# ==============================================================================
# 2. BACON-RAJAN CYCLE COLLECTOR (gc_collect_cycles)
# ==============================================================================
class ZendGC:
    """Simulasi Buffer Siklus PHP Garbage Collection (Bacon & Rajan Algorithm)."""
    def __init__(self, threshold: int = 10):
        self.roots: List[ZendRefcounted] = []
        self.threshold = threshold
        self.collected_cycles = 0

    def track(self, obj: ZendRefcounted) -> None:
        if obj not in self.roots:
            self.roots.append(obj)

    def possible_root(self, obj: ZendRefcounted) -> None:
        if obj.gc_color != GCColor.PURPLE:
            obj.gc_color = GCColor.PURPLE
            if not obj.buffered:
                obj.buffered = True
                self.roots.append(obj)

    def collect_cycles(self) -> int:
        """
        Algoritma 3-Fase Garbage Collection PHP:
        1. gc_mark_roots: Kurangi refcount sementara dan warnai GREY.
        2. gc_scan_roots: Pulihkan jika refcount > 0 (BLACK), jika 0 tetap WHITE.
        3. gc_collect_roots: Bebaskan objek dengan warna WHITE.
        """
        print_substep("GC INITIATED", f"Memulai gc_collect_cycles() pada {len(self.roots)} kandidat root...")
        
        # Tahap 1: Mark Grey (Trial Decrement)
        for root in self.roots:
            if root.gc_color == GCColor.PURPLE:
                self._mark_grey(root)
            else:
                root.buffered = False

        # Tahap 2: Scan Roots (Restore non-garbage to BLACK, garbage to WHITE)
        for root in self.roots:
            self._scan(root)

        # Tahap 3: Collect White Nodes
        freed = 0
        survivors = []
        for root in self.roots:
            root.buffered = False
            if root.gc_color == GCColor.WHITE:
                freed += 1
                root.value = None # Free payload
                root.refcount = 0
            else:
                survivors.append(root)

        self.roots = survivors
        self.collected_cycles += freed
        print_substep("GC FINISHED", f"Siklus terkumpul. Berhasil membebaskan {freed} struktur zend_refcounted.")
        return freed

    def _mark_grey(self, obj: ZendRefcounted) -> None:
        if obj.gc_color != GCColor.GREY:
            obj.gc_color = GCColor.GREY
            if obj.type == ZendType.IS_ARRAY and isinstance(obj.value, dict):
                for child_zval in obj.value.values():
                    if child_zval.rc_obj:
                        child_zval.rc_obj.refcount -= 1
                        self._mark_grey(child_zval.rc_obj)

    def _scan(self, obj: ZendRefcounted) -> None:
        if obj.gc_color == GCColor.GREY:
            if obj.refcount > 0:
                self._scan_black(obj)
            else:
                obj.gc_color = GCColor.WHITE
                if obj.type == ZendType.IS_ARRAY and isinstance(obj.value, dict):
                    for child_zval in obj.value.values():
                        if child_zval.rc_obj:
                            self._scan(child_zval.rc_obj)

    def _scan_black(self, obj: ZendRefcounted) -> None:
        obj.gc_color = GCColor.BLACK
        if obj.type == ZendType.IS_ARRAY and isinstance(obj.value, dict):
            for child_zval in obj.value.values():
                if child_zval.rc_obj:
                    child_zval.rc_obj.refcount += 1
                    if child_zval.rc_obj.gc_color != GCColor.BLACK:
                        self._scan_black(child_zval.rc_obj)


# ==============================================================================
# 3. CONCURRENCY: SIMULASI PHP 8.1 FIBER ENGINE
# ==============================================================================
class FiberState(Enum):
    INIT = auto()
    RUNNING = auto()
    SUSPENDED = auto()
    TERMINATED = auto()

class Fiber:
    """Implementasi kooperatif non-preemptive PHP 8.1 Fiber Engine."""
    _current_fiber: Optional[Fiber] = None

    def __init__(self, target: Callable[..., Generator[Any, Any, Any]]):
        self.target_func = target
        self.generator: Optional[Generator[Any, Any, Any]] = None
        self.state: FiberState = FiberState.INIT
        self.return_value: Any = None

    @classmethod
    def getCurrent(cls) -> Optional[Fiber]:
        return cls._current_fiber

    @classmethod
    def suspend(cls, value: Any = None) -> Any:
        fiber = cls.getCurrent()
        if not fiber or fiber.state != FiberState.RUNNING:
            raise RuntimeError("Fiber::suspend() hanya bisa dipanggil dari dalam Fiber yang aktif.")
        fiber.state = FiberState.SUSPENDED
        return value

    def start(self, *args: Any, **kwargs: Any) -> Any:
        if self.state != FiberState.INIT:
            raise RuntimeError("Fiber sudah pernah dijalankan.")
        self.generator = self.target_func(*args, **kwargs)
        return self._resume_internal(None)

    def resume(self, value: Any = None) -> Any:
        if self.state != FiberState.SUSPENDED:
            raise RuntimeError("Hanya Fiber dengan state SUSPENDED yang dapat di-resume.")
        return self._resume_internal(value)

    def _resume_internal(self, val_to_send: Any) -> Any:
        prev = Fiber._current_fiber
        Fiber._current_fiber = self
        self.state = FiberState.RUNNING
        try:
            yielded = self.generator.send(val_to_send) if self.generator else None
            if self.state == FiberState.RUNNING:
                self.state = FiberState.SUSPENDED
            return yielded
        except StopIteration as stop:
            self.state = FiberState.TERMINATED
            self.return_value = stop.value
            return None
        finally:
            Fiber._current_fiber = prev

    def isTerminated(self) -> bool:
        return self.state == FiberState.TERMINATED


# ==============================================================================
# 4. FUNCTIONAL UTILITIES (MAP, FILTER, CURRY/COMPOSE)
# ==============================================================================
def array_map_fp(fn: Callable[[Any], Any], items: List[Any]) -> List[Any]:
    """Pure functional mapping."""
    return [fn(x) for x in items]

def array_filter_fp(predicate: Callable[[Any], bool], items: List[Any]) -> List[Any]:
    """Pure functional filtering."""
    return [x for x in items if predicate(x)]

def pipe(*fns: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Functional composition pipeline ($pipeline = pipe(fn1, fn2, fn3))."""
    def composed(initial: Any) -> Any:
        result = initial
        for fn in fns:
            result = fn(result)
        return result
    return composed


# ==============================================================================
# LAB DEMONSTRATION SUITE
# ==============================================================================
def run_lab():
    gc = ZendGC()

    # --------------------------------------------------------------------------
    # Demo 1: Zval Reference Counting & Copy-on-Write (COW)
    # --------------------------------------------------------------------------
    print_header("1. Zval Reference Counting & Copy-on-Write (COW)")
    
    # PHP: $varA = ["worker" => "core_0", "status" => "active"];
    zval_worker = Zval.create_string("core_0")
    zval_status = Zval.create_string("active")
    varA = Zval.create_array({"worker": zval_worker, "status": zval_status})
    gc.track(varA.rc_obj)
    
    print_substep("ALLOCATE $varA", f"Array dialokasikan. Array Refcount: {varA.rc_obj.refcount}")
    
    # PHP: $varB = $varA; (Implicit pass-by-ref via copy reference)
    varB = varA
    varB.addref()
    print_substep("ASSIGN $varB = $varA", f"Assignment selesai tanpa cloning. Array Refcount: {varA.rc_obj.refcount}")
    
    # PHP: $varB["worker"] = "worker_isolated"; (Pemicu mutasi / COW)
    new_payload = Zval.create_string("worker_isolated")
    print_substep("MUTATING $varB", "Memodifikasi index array pada $varB...")
    varB.write_array_key("worker", new_payload, gc)

    print_substep("COW VERIFIED", f"$varA refcount: {varA.rc_obj.refcount}, $varB refcount: {varB.rc_obj.refcount}")
    print_substep("DATA SEPARATION", f"$varA['worker'] = '{varA.rc_obj.value['worker'].rc_obj.value}' | $varB['worker'] = '{varB.rc_obj.value['worker'].rc_obj.value}'")


    # --------------------------------------------------------------------------
    # Demo 2: Cyclic Memory Leak & Bacon-Rajan Cycle Collector
    # --------------------------------------------------------------------------
    print_header("2. Circular Reference & Zend Cycle Garbage Collection")
    
    # PHP: $nodeA = []; $nodeB = []; $nodeA['next'] = &$nodeB; $nodeB['prev'] = &$nodeA;
    nodeA = Zval.create_array({})
    nodeB = Zval.create_array({})
    gc.track(nodeA.rc_obj)
    gc.track(nodeB.rc_obj)

    nodeA.rc_obj.value["next"] = nodeB
    nodeB.addref()
    nodeB.rc_obj.value["prev"] = nodeA
    nodeA.addref()

    print_substep("CYCLE CREATED", f"nodeA refcount: {nodeA.rc_obj.refcount}, nodeB refcount: {nodeB.rc_obj.refcount}")

    # PHP: unset($nodeA, $nodeB);
    print_substep("UNSET VARIABLES", "Melakukan unset() pointer lokal. Menandai calon root siklus...")
    ref_a = nodeA.rc_obj
    ref_b = nodeB.rc_obj
    nodeA.delref()
    nodeB.delref()
    gc.possible_root(ref_a)
    gc.possible_root(ref_b)

    print_substep("LEAK STATUS", f"Sebelum GC: NodeA RC={ref_a.refcount}, NodeB RC={ref_b.refcount} (Terjebak di Memory)")
    freed = gc.collect_cycles()
    print_substep("CYCLE RESULT", f"Objek yang dibebaskan: {freed}. NodeA RC={ref_a.refcount}, NodeB RC={ref_b.refcount}")


    # --------------------------------------------------------------------------
    # Demo 3: Asynchronous Fiber Event-Loop & FP Pipeline
    # --------------------------------------------------------------------------
    print_header("3. PHP 8.1 Fiber Concurrency & Functional Data Pipeline")

    tasks_dataset = [
        {"id": 101, "payload": "raw_telemetry_a", "weight": 42},
        {"id": 102, "payload": "raw_telemetry_b", "weight": 18},
        {"id": 103, "payload": "raw_telemetry_c", "weight": 75},
        {"id": 104, "payload": "raw_telemetry_d", "weight": 9},
    ]

    # Functional Pipeline: Transform -> Filter -> Enrich
    cleanse = lambda item: {**item, "payload": item["payload"].upper()}
    filter_heavy = lambda item: item["weight"] > 15
    enrich = lambda item: {**item, "checksum": hex(hash(item["payload"]) & 0xFFFFFFFF)}

    process_pipeline = pipe(cleanse, enrich)

    # Coroutine worker yang merepresentasikan Fiber PHP
    def task_coroutine(worker_id: str, work_item: dict):
        print(f"   {Colors.BLUE}[Fiber-{worker_id}]{Colors.RESET} Dimulai. Memproses Task ID: {work_item['id']}")
        # Simulasi Non-blocking I/O (Fiber::suspend())
        Fiber.suspend(f"YIELD_IO_WAIT_TASK_{work_item['id']}")
        
        # Menjalankan pemrosesan functional
        transformed = process_pipeline(work_item)
        print(f"   {Colors.GREEN}[Fiber-{worker_id}]{Colors.RESET} Selesai dihitung: Checksum {transformed['checksum']}")
        return transformed

    # Persiapkan Fiber
    filtered_data = array_filter_fp(filter_heavy, tasks_dataset)
    fiber_pool: List[Fiber] = [
        Fiber(lambda w=idx, d=item: task_coroutine(f"Worker-{w}", d))
        for idx, item in enumerate(filtered_data)
    ]

    print_substep("FIBERS SCHEDULED", f"{len(fiber_pool)} fibers siap dieksekusi secara kooperatif.")

    # Event Loop Scheduler
    scheduler_tick = 0
    results: List[Any] = []
    
    start_time = time.perf_counter()
    while fiber_pool:
        scheduler_tick += 1
        current = fiber_pool.pop(0)
        
        if current.state == FiberState.INIT:
            susp_signal = current.start()
            print_substep(f"TICK #{scheduler_tick}", f"Fiber ditangguhkan (Yielded: {susp_signal})")
            fiber_pool.append(current) # Kembalikan ke antrian loop
        elif current.state == FiberState.SUSPENDED:
            # Mengalirkan kembali siklus CPU setelah simulasi I/O
            current.resume()
            if current.isTerminated():
                results.append(current.return_value)
                print_substep(f"TICK #{scheduler_tick}", f"Fiber TERMINATED -> Return: {current.return_value['id']}")
            else:
                fiber_pool.append(current)

    elapsed = (time.perf_counter() - start_time) * 1000
    print_substep("CONCURRENCY COMPLETED", f"Total ticks: {scheduler_tick} dalam {elapsed:.3f}ms")
    print(f"\n{Colors.BOLD}{Colors.GREEN}✔ Hands-on Lab Modul Selesai: Arsitektur Memori dan Konkurensi PHP Terverifikasi!{Colors.RESET}\n")

if __name__ == "__main__":
    run_lab()