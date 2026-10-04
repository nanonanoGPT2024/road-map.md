#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi dan Arsitektur Java (JVM Internal & Execution Pipeline)
Topik: JDK vs JRE vs JVM, ClassLoader Subsystem, Runtime Data Areas, & Execution Engine.
"""

import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# ANSI Color Codes untuk Terminal
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
BG_MAGENTA = "\033[45m"


def header(title: str):
    width = 72
    print(f"\n{BOLD}{BG_BLUE}{WHITE}{' ' + title + ' ':=^{width}}{RESET}\n")


def subheader(title: str):
    print(f"{BOLD}{CYAN}=== {title} ==={RESET}")


def info(msg: str):
    print(f"{BLUE}[INFO]{RESET} {msg}")


def success(msg: str):
    print(f"{GREEN}[SUCCESS]{RESET} {msg}")


def warn(msg: str):
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def jvm_log(component: str, msg: str):
    print(f"{MAGENTA}[JVM::{component}]{RESET} {msg}")


@dataclass
class StackFrame:
    method_name: str
    local_variables: Dict[str, Any] = field(default_factory=dict)
    operand_stack: List[Any] = field(default_factory=list)


@dataclass
class JavaObject:
    obj_id: int
    class_name: str
    fields: Dict[str, Any]
    marked: bool = False
    age: int = 0


class JVMSimulator:
    def __init__(self):
        # Memory Areas
        self.method_area: Dict[str, Dict[str, Any]] = {}
        self.eden_space: List[JavaObject] = []
        self.survivor_space: List[JavaObject] = []
        self.tenured_space: List[JavaObject] = []
        self.call_stack: List[StackFrame] = []
        self.pc_register: int = 0
        self.object_counter: int = 1000

        # JIT Compiler Hotspot Counter
        self.method_invocation_counters: Dict[str, int] = {}
        self.jit_compiled_cache: Dict[str, str] = {}

    # --- Phase 1: Compilation (javac) ---
    def simulate_javac(self, source_code_file: str, class_name: str) -> str:
        header("FASE 1: KOMPILASI SOURCE CODE (javac)")
        info(f"Membaca file source: {YELLOW}{source_code_file}{RESET}")
        time.sleep(0.3)
        info("Parser memeriksa sintaksis dan lexical analysis...")
        time.sleep(0.3)
        bytecode_file = f"{class_name}.class"
        success(f"Kompilasi berhasil! Dihasilkan Java Bytecode portable: {GREEN}{bytecode_file}{RESET}")
        print(f"{DIM}Magic Number Bytecode: 0xCAFEBABE{RESET}")
        return bytecode_file

    # --- Phase 2: Class Loading Subsystem ---
    def class_loader_subsystem(self, class_name: str):
        header("FASE 2: CLASSLOADER SUBSYSTEM (Loading, Linking, Initialization)")
        
        # 1. Loading
        subheader("1. Loading (Delegation Hierarchy)")
        loaders = [
            ("Bootstrap ClassLoader", "rt.jar / java.base (core classes)"),
            ("Platform/Extension ClassLoader", "ext libraries / platform modules"),
            ("Application/System ClassLoader", "classpath aplikasi Anda")
        ]
        for loader_name, scope in loaders:
            jvm_log("ClassLoader", f"Delegasi pengecekan ke {BOLD}{loader_name}{RESET} -> {scope}")
            time.sleep(0.25)
        success(f"Class '{class_name}' ditemukan dan dimuat oleh Application ClassLoader.")

        # 2. Linking
        subheader("2. Linking (Verification, Preparation, Resolution)")
        jvm_log("Verification", "Memverifikasi integritas bytecode dan batas keamanan JVM...")
        time.sleep(0.2)
        jvm_log("Preparation", "Mengalokasikan memori untuk static variables dan nilai default (0/null)...")
        time.sleep(0.2)
        jvm_log("Resolution", "Mengubah symbolic references di Constant Pool menjadi direct memory references...")
        time.sleep(0.2)
        success("Tahap Linking selesai tanpa security constraint violation.")

        # 3. Initialization
        subheader("3. Initialization (<clinit>)")
        jvm_log("Initialization", f"Mengeksekusi blok static dan inisialisasi nilai variabel static class {class_name}...")
        self.method_area[class_name] = {
            "constant_pool": ["#1 Methodref", "#2 Fieldref", "#3 String 'Java Architecture Lab'"],
            "static_fields": {"APP_VERSION": "1.0-LTS"},
            "methods": ["main([Ljava/lang/String;)V", "calculateScore(II)I"]
        }
        success(f"Metadata kelas {class_name} tersimpan di Method Area (Metaspace).\n")

    # --- Phase 3: Runtime Execution & Stack/Heap Management ---
    def execute_frame(self, method_name: str, args: Dict[str, Any]):
        frame = StackFrame(method_name=method_name, local_variables=args.copy())
        self.call_stack.append(frame)
        self.pc_register = 0
        self.method_invocation_counters[method_name] = self.method_invocation_counters.get(method_name, 0) + 1
        
        jvm_log("StackEngine", f"PUSH frame baru: {BOLD}{method_name}(){RESET} ke Thread JVM Stack.")
        self.print_stack_state()

        # Simulasi JIT Profiling
        invocations = self.method_invocation_counters[method_name]
        if invocations >= 3 and method_name not in self.jit_compiled_cache:
            warn(f"Metode '{method_name}' terdeteksi sebagai HOT METHOD (Hits: {invocations})!")
            jvm_log("JIT/C2 Compiler", f"Mengompilasi bytecode '{method_name}' langsung ke Native Machine Code (x86_64).")
            self.jit_compiled_cache[method_name] = "NATIVE_ASM_X86_OPT"

        # Alokasi Object ke Heap jika metode main
        if method_name == "main":
            self.allocate_object("UserSession", {"userId": 101, "role": "STUDENT"})
            self.allocate_object("TempCache", {"tempToken": "xyz-999"})
            
            # Panggil sub-metode
            info("Mengeksekusi invokasi metode calculateScore()...")
            self.execute_frame("calculateScore", {"a": 85, "b": 15})
            
            # Dereference TempCache untuk mensimulasikan objek eligible GC
            info("Dereferensi 'TempCache' (objek menjadi unreachable / eligible for GC)...")
            for obj in self.eden_space:
                if obj.class_name == "TempCache":
                    obj.marked = False

        elif method_name == "calculateScore":
            # Simulasi operand stack bytecode
            jvm_log("ExecutionEngine", "iload_1 (load a=85 ke operand stack)")
            frame.operand_stack.append(frame.local_variables["a"])
            self.pc_register += 1

            jvm_log("ExecutionEngine", "iload_2 (load b=15 ke operand stack)")
            frame.operand_stack.append(frame.local_variables["b"])
            self.pc_register += 1

            jvm_log("ExecutionEngine", "iadd (menjumlahkan 2 nilai teratas stack)")
            v2 = frame.operand_stack.pop()
            v1 = frame.operand_stack.pop()
            res = v1 + v2
            frame.operand_stack.append(res)
            self.pc_register += 1

            jvm_log("ExecutionEngine", f"ireturn hasil: {GREEN}{res}{RESET}")
            time.sleep(0.3)

        # Pop stack frame
        popped = self.call_stack.pop()
        jvm_log("StackEngine", f"POP frame {BOLD}{popped.method_name}(){RESET} selesai.")

    def allocate_object(self, class_name: str, fields: Dict[str, Any]):
        self.object_counter += 1
        new_obj = JavaObject(obj_id=self.object_counter, class_name=class_name, fields=fields, marked=True)
        self.eden_space.append(new_obj)
        jvm_log("HeapManager", f"Objek baru {BOLD}{class_name}@{hex(new_obj.obj_id)}{RESET} dialokasikan di {CYAN}Heap (Young Gen -> Eden Space){RESET}.")

    # --- Phase 4: Garbage Collection Simulation ---
    def trigger_minor_gc(self):
        header("FASE 4: GARBAGE COLLECTION SIMULASI (Minor GC / Young Generation)")
        info("Kondisi: Eden Space penuh. Memulai Stop-The-World (STW) pause mikro...")
        time.sleep(0.3)
        
        survivors = []
        garbage = []
        for obj in self.eden_space:
            if obj.marked:
                obj.age += 1
                survivors.append(obj)
            else:
                garbage.append(obj)

        for g in garbage:
            print(f"{RED}[GC-SWEEP]{RESET} Memusnahkan objek mati {g.class_name}@{hex(g.obj_id)}")
        
        for s in survivors:
            if s.age >= 2:
                self.tenured_space.append(s)
                success(f"Objek berumur {s.age} dipromosikan ke Tenured (Old Gen): {s.class_name}@{hex(s.obj_id)}")
            else:
                self.survivor_space.append(s)
                print(f"{GREEN}[GC-COPY]{RESET} Memindahkan survivor ke S0/S1: {s.class_name}@{hex(s.obj_id)} (Age: {s.age})")

        self.eden_space.clear()
        success("Minor GC selesai. Memori Eden Space kembali bersih.")

    # --- Visual State Reporter ---
    def print_stack_state(self):
        print(f"\n{BOLD}{YELLOW}--- Status JVM Thread Stack ---{RESET}")
        if not self.call_stack:
            print(f"{DIM}(Stack Kosong){RESET}")
            return
        for idx, f in enumerate(reversed(self.call_stack)):
            print(f"  [{idx}] Method: {BOLD}{f.method_name}{RESET}")
            print(f"      Locals: {f.local_variables}")
            print(f"      Operand Stack: {f.operand_stack}")
        print(f"{YELLOW}------------------------------{RESET}\n")

    def print_memory_dashboard(self):
        header("DASHBOARD ARSITEKTUR RUNTIME JVM")
        print(f"{BOLD}1. Method Area (Metaspace):{RESET}")
        for k, v in self.method_area.items():
            print(f"   - Class: {CYAN}{k}{RESET} | Statics: {v['static_fields']} | Methods: {v['methods']}")

        print(f"\n{BOLD}2. Heap Memory Breakdown:{RESET}")
        print(f"   * {BOLD}Young Gen - Eden Space:{RESET} {[f'{o.class_name}@{hex(o.obj_id)}' for o in self.eden_space] or '(Kosong)'}")
        print(f"   * {BOLD}Young Gen - Survivor (S0/S1):{RESET} {[f'{o.class_name}@{hex(o.obj_id)}(age={o.age})' for o in self.survivor_space] or '(Kosong)'}")
        print(f"   * {BOLD}Old Gen - Tenured Space:{RESET} {[f'{o.class_name}@{hex(o.obj_id)}' for o in self.tenured_space] or '(Kosong)'}")

        print(f"\n{BOLD}3. JIT Execution Status:{RESET}")
        for meth, hits in self.method_invocation_counters.items():
            status = f"{GREEN}NATIVE (JIT Compiled){RESET}" if meth in self.jit_compiled_cache else f"{YELLOW}INTERPRETER{RESET}"
            print(f"   - {meth}(): {hits} invocations -> [{status}]")
        print()


def interactive_menu():
    jvm = JVMSimulator()
    class_name = "ApplicationMain"
    source_file = f"{class_name}.java"

    while True:
        print(f"\n{BOLD}{WHITE}Simulasi Hands-on: Fondasi & Arsitektur Java{RESET}")
        print("1. Jalankan Siklus Kompilasi Lengkap (javac & ClassLoader)")
        print("2. Eksekusi Bytecode di Stack & Alokasi Objek di Heap")
        print("3. Uji Coba HotSpot JIT Optimization (Looping Invocation)")
        print("4. Picu Garbage Collector (Minor GC & Promotion)")
        print("5. Tampilkan Dashboard Runtime Memory JVM")
        print("6. Keluar")
        
        choice = input(f"\n{CYAN}Pilih opsi [1-6]: {RESET}").strip()
        if choice == "1":
            jvm.simulate_javac(source_file, class_name)
            jvm.class_loader_subsystem(class_name)
        elif choice == "2":
            header("FASE 3: EKSEKUSI RUNTIME DI JVM STACK & HEAP")
            jvm.execute_frame("main", {"args": ["--mode=production"]})
        elif choice == "3":
            header("SIMULASI JIT HOTSPOT COMPILATION")
            info("Memanggil 'calculateScore()' berulang kali untuk mencapai threshold JIT...")
            for i in range(4):
                jvm.execute_frame("calculateScore", {"a": 10 * i, "b": 20})
            success("Profiling Hotspot JIT telah tercapai.")
        elif choice == "4":
            jvm.trigger_minor_gc()
        elif choice == "5":
            jvm.print_memory_dashboard()
        elif choice == "6":
            print(f"\n{GREEN}Terima kasih telah mempelajari fondasi arsitektur Java.{RESET}\n")
            sys.exit(0)
        else:
            warn("Pilihan tidak valid, silakan ulangi.")


if __name__ == "__main__":
    interactive_menu()
