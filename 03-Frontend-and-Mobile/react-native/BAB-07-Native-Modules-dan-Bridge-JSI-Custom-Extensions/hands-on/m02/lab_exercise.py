#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Arsitektur React Native Native Modules, Legacy Bridge vs. JSI & TurboModules
Materi: BAB-07 Native Modules dan Bridge JSI Custom Extensions

Skrip ini mensimulasikan perbandingan performa mendalam dan mekanisme internal antara:
1. Legacy Asynchronous Serialized Bridge (JSON over thread boundary)
2. New Architecture: JSI (JavaScript Interface) HostObject & TurboModules (Direct C++ Memory Call)
"""

import sys
import time
import json
import random
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

# ================= ANSI Color Codes =================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM = '\033[2m'
    RESET = '\033[0m'

@dataclass
class BridgeMessage:
    module: str
    method: str
    args_json: str
    callback_id: int
    payload_bytes: int
    queue_time_ns: int = 0

@dataclass
class JSIRuntimeContext:
    total_memory_heap_kb: int = 65536
    cxx_host_objects: Dict[str, Any] = field(default_factory=dict)
    active_turbomodules: Dict[str, bool] = field(default_factory=dict)

# ================= SIMULATOR 1: LEGACY BRIDGE =================
class LegacyBridgeSimulator:
    """
    Mensimulasikan antrean Bridge lama:
    - Serialisasi JSON di JS Thread
    - Enqueue ke message queue
    - Thread context switch (JS -> Native Shadow/UI Thread)
    - Deserialisasi JSON di Native Thread
    - Eksekusi native
    - Serialisasi respons & postMessage balik ke JS Thread
    """
    def __init__(self, thread_switch_latency_ms: float = 2.5):
        self.latency_ms = thread_switch_latency_ms
        self.message_queue: List[BridgeMessage] = []
        self.serialized_traffic_bytes = 0

    def send_invoke(self, module: str, method: str, args: List[Any], cb_id: int) -> BridgeMessage:
        t0 = time.perf_counter_ns()
        # 1. JSON Stringify overhead (JS Thread)
        args_json = json.dumps(args)
        payload_size = len(args_json.encode('utf-8'))
        self.serialized_traffic_bytes += payload_size

        msg = BridgeMessage(
            module=module,
            method=method,
            args_json=args_json,
            callback_id=cb_id,
            payload_bytes=payload_size,
            queue_time_ns=t0
        )
        self.message_queue.append(msg)
        return msg

    def process_batch(self) -> List[Dict[str, Any]]:
        results = []
        # Mensimulasikan batching frame 16ms
        while self.message_queue:
            msg = self.message_queue.pop(0)
            # Simulated serialization + bridge hop latency
            simulated_delay = (self.latency_ms / 1000.0) + (msg.payload_bytes / 20_000_000.0)
            time.sleep(simulated_delay)

            # Native parsing
            parsed_args = json.loads(msg.args_json)
            # Dummy native execution (e.g. cryptography / image transform)
            res_val = f"ACK_{msg.module}::{msg.method}({len(parsed_args)}_items)"
            
            # Simulated response serialization
            res_json = json.dumps({"cb": msg.callback_id, "result": res_val})
            self.serialized_traffic_bytes += len(res_json.encode('utf-8'))

            results.append({"status": "OK", "data": res_val, "bytes": msg.payload_bytes})
        return results

# ================= SIMULATOR 2: JSI & TURBOMODULES =================
class JSIHostObjectSimulator:
    """
    Mensimulasikan direct invocation melalui JSI:
    - Tidak ada serialisasi JSON
    - C++ HostObject expose pointer langsung ke JavaScript Runtime
    - Synchronous execution atau zero-copy TypedArray reference
    - Lazy loading TurboModule registry
    """
    def __init__(self, runtime: JSIRuntimeContext):
        self.runtime = runtime
        self.zero_copy_ops = 0

    def resolve_turbomodule(self, module_name: str) -> bool:
        """TurboModule lazy initialization check"""
        if module_name not in self.runtime.active_turbomodules:
            # Lazy load module only when invoked
            self.runtime.active_turbomodules[module_name] = True
            time.sleep(0.001) # Small 1ms one-time initialization
            return False # Was not already loaded
        return True # Already cached in C++ registry

    def direct_cxx_call(self, module: str, method: str, raw_data_ref: Any) -> Any:
        self.resolve_turbomodule(module)
        
        # JSI memproses objek C++ HostObject tanpa JSON marshalling
        # Direct synchronous evaluation
        t_start = time.perf_counter_ns()
        
        # Zero-copy memory view simulation
        self.zero_copy_ops += 1
        if isinstance(raw_data_ref, list):
            data_len = len(raw_data_ref)
        elif isinstance(raw_data_ref, bytes):
            data_len = len(raw_data_ref)
        else:
            data_len = 1

        # Nanosecond direct pointer access simulation
        time.sleep(0.00005) # ~50 microseconds native C++ call
        t_end = time.perf_counter_ns()

        return {
            "result": f"JSI_PTR_SUCCESS({module}::{method})",
            "items_processed": data_len,
            "latency_us": (t_end - t_start) / 1000.0
        }

# ================= VISUALIZATION & BENCHMARK =================
def run_benchmark(iterations: int = 15, payload_items: int = 1000):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.HEADER}  REACT NATIVE BENCHMARK: LEGACY BRIDGE vs JSI TURBOMODULE{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.YELLOW}Parameter Skenario:{Colors.RESET}")
    print(f"  • Jumlah Pemanggilan : {Colors.BOLD}{iterations}{Colors.RESET} frame calls")
    print(f"  • Ukuran Payload     : {Colors.BOLD}{payload_items}{Colors.RESET} elemen per payload")
    print(f"{Colors.CYAN}{'-'*70}{Colors.RESET}\n")

    sample_payload = [{"id": i, "token": f"sec_tok_{random.randint(1000, 9999)}", "active": True} for i in range(payload_items)]

    # --- 1. LEGACY BRIDGE EXECUTION ---
    print(f"{Colors.BOLD}{Colors.RED}[1/2] Mensimulasikan Arsitektur Legacy Bridge (Asynchronous Batched)...{Colors.RESET}")
    legacy_bridge = LegacyBridgeSimulator(thread_switch_latency_ms=3.0)
    
    t_bridge_start = time.perf_counter()
    for i in range(iterations):
        legacy_bridge.send_invoke(
            module="CryptoModule",
            method="verifyKeysBatch",
            args=[sample_payload],
            cb_id=100 + i
        )
    bridge_results = legacy_bridge.process_batch()
    t_bridge_end = time.perf_counter()
    total_bridge_time = (t_bridge_end - t_bridge_start) * 1000.0

    print(f"  -> Selesai diproses: {len(bridge_results)} batch invokes.")
    print(f"  -> Total Traffic Bridge JSON: {Colors.BOLD}{legacy_bridge.serialized_traffic_bytes / 1024:.2f} KB{Colors.RESET}")
    print(f"  -> Total Elapsed Time: {Colors.RED}{Colors.BOLD}{total_bridge_time:.2f} ms{Colors.RESET}\n")

    # --- 2. JSI TURBOMODULES EXECUTION ---
    print(f"{Colors.BOLD}{Colors.GREEN}[2/2] Mensimulasikan Arsitektur JSI + TurboModules (HostObject Direct C++)...{Colors.RESET}")
    runtime_ctx = JSIRuntimeContext()
    jsi_sim = JSIHostObjectSimulator(runtime_ctx)

    t_jsi_start = time.perf_counter()
    jsi_results = []
    for _ in range(iterations):
        res = jsi_sim.direct_cxx_call(
            module="CryptoModuleTurbo",
            method="verifyKeysBatchSynchronous",
            raw_data_ref=sample_payload
        )
        jsi_results.append(res)
    t_jsi_end = time.perf_counter()
    total_jsi_time = (t_jsi_end - t_jsi_start) * 1000.0

    print(f"  -> Selesai diproses: {len(jsi_results)} direct synchronous C++ invocations.")
    print(f"  -> Zero-copy Memory Operations: {Colors.BOLD}{jsi_sim.zero_copy_ops}{Colors.RESET} ops")
    print(f"  -> Total Elapsed Time: {Colors.GREEN}{Colors.BOLD}{total_jsi_time:.2f} ms{Colors.RESET}\n")

    # --- PERBANDINGAN METRIK ---
    speedup = total_bridge_time / (total_jsi_time if total_jsi_time > 0 else 0.001)
    
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.HEADER}                  HASIL ANALISIS ARSITEKTUR                  {Colors.RESET}")
    print(f"{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"  Performa Relatif    : {Colors.BOLD}{Colors.GREEN}{speedup:.1f}x LEBIH CEPAT{Colors.RESET} menggunakan JSI / TurboModules")
    print(f"  Overhead Serialisasi: {Colors.RED}Legacy = {legacy_bridge.serialized_traffic_bytes/1024:.1f} KB JSON{Colors.RESET} vs {Colors.GREEN}JSI = 0 KB (Zero-Copy Ptr){Colors.RESET}")
    print(f"  Karakteristik Thread: {Colors.RED}Legacy = Thread Hops (Async Queue){Colors.RESET} vs {Colors.GREEN}JSI = Synchronous Direct Access{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*70}{Colors.RESET}\n")


def interactive_cli():
    print(f"{Colors.BOLD}{Colors.GREEN}Lab Hands-on M02 React Native Architecture Simulator Dimulai.{Colors.RESET}")
    while True:
        print(f"\n{Colors.BOLD}PILIHAN LAB & DEMO ARSITEKTUR:{Colors.RESET}")
        print(" [1] Jalankan Benchmark Otomatis (Bridge vs JSI)")
        print(" [2] Uji Stres Ukuran Payload Ekstrem (Simulasi Frame Drops)")
        print(" [3] Inspeksi Komparasi Konsep & Kode C++ vs Java/Obj-C")
        print(" [4] Keluar")
        
        try:
            choice = input(f"\n{Colors.CYAN}Masukkan pilihan [1-4] (default: 1): {Colors.RESET}").strip()
            if not choice:
                choice = "1"

            if choice == "1":
                run_benchmark(iterations=12, payload_items=800)
            elif choice == "2":
                print(f"\n{Colors.YELLOW}Menguji 50 payload besar (5.000 objek/call) ke Bridge...{Colors.RESET}")
                run_benchmark(iterations=5, payload_items=5000)
            elif choice == "3":
                print(f"\n{Colors.BOLD}{Colors.CYAN}--- ARCHITECTURAL COMPARISON CHEATSHEET ---{Colors.RESET}")
                print(f"{Colors.BOLD}1. Legacy NativeModule (Java/Obj-C):{Colors.RESET}")
                print("   @ReactMethod public void doHeavyTask(ReadableArray arr, Callback cb)")
                print("   • Harus melewati serialize/deserialize JSON di queue thread.")
                print(f"\n{Colors.BOLD}2. Modern JSI TurboModule (C++ HostObject):{Colors.RESET}")
                print("   jsi::Value get(jsi::Runtime& rt, const jsi::PropNameID& name) override")
                print("   • Pointer diekspos langsung ke global scope JavaScript runtime.")
                print("   • Zero-copy memory access, eliminasi lag UI 60/120 FPS.")
                print(f"{Colors.CYAN}---------------------------------------------{Colors.RESET}")
            elif choice == "4" or choice.lower() in ("exit", "quit", "q"):
                print(f"{Colors.GREEN}Selesai. Terima kasih telah menggunakan simulator arsitektur JSI!{Colors.RESET}")
                break
            else:
                print(f"{Colors.RED}Pilihan tidak valid. Silakan pilih 1, 2, 3, atau 4.{Colors.RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Keluar dari program.{Colors.RESET}")
            break

if __name__ == "__main__":
    # If run in non-interactive / automated pipe mode
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_benchmark(iterations=5, payload_items=500)
    else:
        # Jalankan benchmark satu siklus lalu masuk ke menu interaktif jika terminal TTY
        run_benchmark(iterations=8, payload_items=400)
        if sys.stdin.isatty():
            interactive_cli()
