#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi PHP BAB-04
- Functional Programming (Pure functions, HOF, Currying, Pipelines)
- Concurrency Model (Fiber & Cooperative Multitasking Simulation)
- Zend Engine Memory Management (zval, Refcounting, Copy-on-Write, Cycle Collector)

Standalone runnable Python 3 script with ANSI terminal visuals.
"""

import sys
import time
from typing import Callable, Any, List, Dict, Optional

# ANSI Color Codes
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"

def print_header(title: str) -> None:
    print(f"\n{Style.BOLD}{Style.BG_BLUE} === [PHP ENGINE SIMULATOR] {title} === {Style.RESET}\n")

def print_step(step: str, detail: str) -> None:
    print(f"{Style.CYAN}[RUN]{Style.RESET} {Style.BOLD}{step}{Style.RESET} -> {detail}")

def print_success(msg: str) -> None:
    print(f"{Style.GREEN}[SUCCESS]{Style.RESET} {msg}")

def print_warn(msg: str) -> None:
    print(f"{Style.YELLOW}[WARN]{Style.RESET} {msg}")

def print_engine(msg: str) -> None:
    print(f"{Style.MAGENTA}[ZEND-VM]{Style.RESET} {msg}")


# ============================================================================
# 1. FUNCTIONAL PROGRAMMING EMULATION (PHP 7.4+ / 8.x Closures & Pipeline)
# ============================================================================

def compose(*funcs: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Menggabungkan fungsi dari kanan ke kiri: compose(f, g)(x) == f(g(x))"""
    def _composed(arg: Any) -> Any:
        res = arg
        for fn in reversed(funcs):
            res = fn(res)
        return res
    return _composed

def pipe(*funcs: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Pipeline transformation: pipe(f, g)(x) == g(f(x)) mirip operator |>"""
    def _piped(arg: Any) -> Any:
        res = arg
        for fn in funcs:
            res = fn(res)
        return res
    return _piped

def curry_binary(fn: Callable[[Any, Any], Any]) -> Callable[[Any], Callable[[Any], Any]]:
    """Currying untuk fungsi 2-argumen"""
    return lambda a: lambda b: fn(a, b)


def run_functional_demo():
    print_header("1. FUNCTIONAL PROGRAMMING & PIPELINE TRANSFORMATION")
    
    dataset = [
        {"id": 1, "username": "alice_dev", "role": "admin", "score": 95},
        {"id": 2, "username": "bob_tester", "role": "user", "score": 62},
        {"id": 3, "username": "charlie_php", "role": "admin", "score": 88},
        {"id": 4, "username": "david_intern", "role": "user", "score": 45},
        {"id": 5, "username": "eve_lead", "role": "admin", "score": 98},
    ]

    print_step("Input Records", f"{len(dataset)} entitas pengguna dimuat.")
    
    # Pure Filter & Mapping
    filter_admin = lambda users: [u for u in users if u["role"] == "admin"]
    add_bonus = lambda users: [{**u, "score": u["score"] + 5} for u in users]
    format_output = lambda users: [f"{u['username'].upper()} ({u['score']} pts)" for u in users]

    # Pipeline Composition
    pipeline_fn = pipe(filter_admin, add_bonus, format_output)
    
    print_step("Executing Pure Pipeline", "filter_admin |> add_bonus(+5) |> format_output")
    result = pipeline_fn(dataset)

    for item in result:
        print_success(f"Output Item: {item}")
        
    # Currying Demo
    multiply = lambda a, b: a * b
    curried_mul = curry_binary(multiply)
    triple = curried_mul(3)
    
    print_step("Currying Demo", f"triple(15) = {triple(15)}")


# ============================================================================
# 2. CONCURRENCY & FIBER / COOPERATIVE SCHEDULING (PHP 8.1+ Fiber)
# ============================================================================

class FiberState:
    SUSPENDED = "SUSPENDED"
    RUNNING = "RUNNING"
    TERMINATED = "TERMINATED"

class SimulatedFiber:
    def __init__(self, name: str, generator_fn):
        self.name = name
        self.gen = generator_fn
        self.state = FiberState.SUSPENDED
        self.return_val = None

    def resume(self, val=None):
        self.state = FiberState.RUNNING
        try:
            yielded = self.gen.send(val)
            self.state = FiberState.SUSPENDED
            return yielded
        except StopIteration as e:
            self.state = FiberState.TERMINATED
            self.return_val = e.value
            return None

class FiberScheduler:
    """Cooperative Event Loop Scheduler meniru amphp / revolt / swoole scheduler."""
    def __init__(self):
        self.tasks: List[SimulatedFiber] = []

    def spawn(self, name: str, gen):
        fiber = SimulatedFiber(name, gen)
        self.tasks.append(fiber)
        return fiber

    def run(self):
        print_engine("Event Loop Started. Round-robin Fiber execution.")
        step_round = 1
        while any(f.state != FiberState.TERMINATED for f in self.tasks):
            print(f"{Style.YELLOW}--- Loop Cycle #{step_round} ---{Style.RESET}")
            for fiber in list(self.tasks):
                if fiber.state != FiberState.TERMINATED:
                    print_step(f"Resume Fiber '{fiber.name}'", f"State: {fiber.state}")
                    res = fiber.resume()
                    if res:
                        print(f"      {Style.BLUE}↳ Fiber Yielded Message: '{res}'{Style.RESET}")
                    if fiber.state == FiberState.TERMINATED:
                        print_success(f"Fiber '{fiber.name}' TERMINATED. Result: {fiber.return_val}")
            step_round += 1
            time.sleep(0.05)
        print_engine("All Fibers completed. Event Loop idle shutdown.")


def fiber_worker_io(worker_id: int, total_steps: int):
    """Simulasi generator asynchronous I/O mirip Fiber PHP"""
    for i in range(1, total_steps + 1):
        yield f"Worker-{worker_id} waiting on non-blocking socket chunk {i}/{total_steps}"
    return f"Worker-{worker_id} I/O Complete"


def run_concurrency_demo():
    print_header("2. CONCURRENCY: PHP 8.1 FIBER COOPERATIVE EVENT LOOP")
    scheduler = FiberScheduler()

    f1 = scheduler.spawn("HTTP_Fetcher", fiber_worker_io(101, 3))
    f2 = scheduler.spawn("DB_Query_Pool", fiber_worker_io(202, 2))
    f3 = scheduler.spawn("Cache_Warmup", fiber_worker_io(303, 4))

    scheduler.run()


# ============================================================================
# 3. ZEND ENGINE MEMORY MANAGEMENT (zval, Refcount, COW & Cyclic GC)
# ============================================================================

class ZVal:
    """Simulasi struktur zval pada Zend Engine C Core"""
    _id_counter = 1000

    def __init__(self, val_type: str, value: Any):
        ZVal._id_counter += 1
        self.ref_id = ZVal._id_counter
        self.val_type = val_type
        self.value = value
        self.refcount = 1
        self.is_ref = False
        self.gc_color = "BLACK"  # Untuk Cycle Collector: BLACK, GREY, WHITE, PURPLE

    def __repr__(self):
        return f"<zval#{self.ref_id} type={self.val_type} refcount={self.refcount} is_ref={int(self.is_ref)} val={self.value}>"

class ZendSymbolTable:
    """Tabel simbol scope variabel PHP ($a, $b, dll)"""
    def __init__(self):
        self.symbols: Dict[str, ZVal] = {}
        self.gc_root_buffer: List[ZVal] = []

    def assign(self, var_name: str, zval_obj: ZVal):
        """$var_name = $other; (Refcount increment)"""
        if var_name in self.symbols:
            self.unset(var_name)
        self.symbols[var_name] = zval_obj
        zval_obj.refcount += 1
        print_engine(f"Assign '${var_name}' -> refcount={zval_obj.refcount}")

    def create_variable(self, var_name: str, val_type: str, value: Any) -> ZVal:
        """$var_name = value;"""
        if var_name in self.symbols:
            self.unset(var_name)
        new_zval = ZVal(val_type, value)
        self.symbols[var_name] = new_zval
        print_engine(f"Allocated '${var_name}': {new_zval}")
        return new_zval

    def modify_cow(self, var_name: str, new_value: Any):
        """Simulasi Copy-on-Write (COW): Duplikasi memory jika refcount > 1"""
        target = self.symbols.get(var_name)
        if not target:
            raise KeyError(f"Undefined variable ${var_name}")
        
        if target.refcount > 1 and not target.is_ref:
            print_warn(f"COW Triggered on '${var_name}'! Refcount was {target.refcount}. Splitting zval...")
            target.refcount -= 1
            cloned = ZVal(target.val_type, new_value)
            self.symbols[var_name] = cloned
            print_engine(f"Detached memory block: old={target}, new={cloned}")
        else:
            target.value = new_value
            print_engine(f"In-place write on '${var_name}': {target}")

    def unset(self, var_name: str):
        """unset($var_name); decrement refcount, deallocate if 0"""
        target = self.symbols.pop(var_name, None)
        if target:
            target.refcount -= 1
            print_engine(f"Unset '${var_name}': Refcount decremented to {target.refcount}")
            if target.refcount <= 0:
                print_success(f"ZEND MEMORY FREE: Memory block #{target.ref_id} freed instantly.")
            else:
                # Kandidat cyclic garbage jika bertipe struktur (array/object)
                if target.val_type in ("array", "object"):
                    target.gc_color = "PURPLE"
                    if target not in self.gc_root_buffer:
                        self.gc_root_buffer.append(target)
                        print_warn(f"Possible cyclic root added to GC Buffer: zval#{target.ref_id}")

    def run_cycle_collector(self):
        """Simulasi Concurrent Cycle Collector (Zend GC Mark & Sweep)"""
        print_engine(f"Running Zend Garbage Collection (Roots in buffer: {len(self.gc_root_buffer)})")
        if not self.gc_root_buffer:
            print_success("GC Buffer is clean. Zero cycle leaks detected.")
            return

        # Mark Grey
        collected = []
        for root in list(self.gc_root_buffer):
            # Cek jika referensi masih hidup di tabel simbol
            still_referenced = any(s == root for s in self.symbols.values())
            if not still_referenced:
                collected.append(root)
                self.gc_root_buffer.remove(root)
                print_success(f"Garbage Collector reclaimed circular zombie zval#{root.ref_id} (Freed leaked block)")

        print_engine(f"GC Finished. Total cyclic buffers reclaimed: {len(collected)}")


def run_memory_demo():
    print_header("3. ZEND ENGINE MEMORY MANAGEMENT (zval & COW & GC)")
    sym = ZendSymbolTable()

    print_step("Step 1: Inisialisasi variabel string", "$a = 'Hello World'")
    z_a = sym.create_variable("a", "string", "Hello World")

    print_step("Step 2: Assign by value (COW Sharing)", "$b = $a")
    sym.assign("b", z_a)

    print_step("Step 3: Modifikasi $b (Triggering Copy-On-Write)", "$b .= ' Mutated!'")
    sym.modify_cow("b", "Hello World Mutated!")

    print_step("Step 4: Observasi status kedua zval", "Cek pemisahan memory block")
    print(f"      $a -> {sym.symbols['a']}")
    print(f"      $b -> {sym.symbols['b']}")

    print_step("Step 5: Simulasi Circular Reference", "Object/Array me-referensikan dirinya sendiri")
    z_circ = sym.create_variable("node", "array", {"name": "RootNode", "child": None})
    z_circ.value["child"] = z_circ  # Circular self reference
    print_engine(f"Self-reference linked. Simulated cycle created.")

    print_step("Step 6: Unset pointer luar", "unset($node) tapi referensi internal masih menahan refcount")
    sym.unset("node")

    print_step("Step 7: Panggil Zend GC Cycle Collector", "gc_collect_cycles()")
    sym.run_cycle_collector()


# ============================================================================
# INTERACTIVE CLI DISPATCHER
# ============================================================================

def show_menu():
    print(f"\n{Style.BOLD}{Style.CYAN}--- PILIHAN MODUL SIMULASI BAB-04 ---{Style.RESET}")
    print("1. Functional Programming & Pipeline Transformations")
    print("2. Concurrency: Fiber & Event Loop Cooperative Multitasking")
    print("3. Zend Engine Memory Management (zval, COW, Cyclic GC)")
    print("4. Jalankan Seluruh Modul (1 - 3)")
    print("5. Keluar")

def main():
    print(f"{Style.BOLD}{Style.BG_MAGENTA} PHP 8.x ADVANCED CONCEPTS ENGINE EMULATOR {Style.RESET}")
    print("Simulasi Teknis: Functional Programming, Concurrency, & Memory Management\n")

    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        run_functional_demo()
        run_concurrency_demo()
        run_memory_demo()
        print_success("Seluruh simulasi fondasi BAB-04 selesai dieksekusi dengan sukses!\n")
        return

    # Default non-blocking / automated run of all modules for verification or interactive
    if not sys.stdin.isatty():
        run_functional_demo()
        run_concurrency_demo()
        run_memory_demo()
        print_success("Mode batch/CI terdeteksi. Selesai dijalankan 100% tanpa error.")
        return

    while True:
        show_menu()
        try:
            choice = input(f"{Style.BOLD}Pilih opsi [1-5]: {Style.RESET}").strip()
            if choice == "1":
                run_functional_demo()
            elif choice == "2":
                run_concurrency_demo()
            elif choice == "3":
                run_memory_demo()
            elif choice == "4":
                run_functional_demo()
                run_concurrency_demo()
                run_memory_demo()
            elif choice == "5" or choice == "q":
                print(f"{Style.GREEN}Sampai jumpa! Lab selesai.{Style.RESET}")
                break
            else:
                print_warn("Opsi tidak valid. Silakan pilih 1-5.")
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi.")
            break

if __name__ == "__main__":
    main()
