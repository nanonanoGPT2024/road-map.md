#!/usr/bin/env python3
"""
Lab Exercise: React Native Native Modules, Legacy Bridge vs JSI / TurboModules
Simulasi interaktif arsitektur komunikasi JavaScript <-> Native pada React Native.
"""

import sys
import time
import json
import random
from typing import Any, Dict, List, Optional

# ANSI Color Codes
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


class LegacyBridgeSimulator:
    """
    Simulasi Arsitektur Lama (Old Architecture):
    - Thread JS dan Native terpisah secara asinkron.
    - Semua data harus di-serialize menjadi JSON string.
    - Data di-enqueue ke MessageQueue (batched).
    - Latensi tinggi untuk transmisi data kontinu/besar.
    """

    def __init__(self) -> None:
        self.bridge_queue: List[Dict[str, Any]] = []
        self.native_storage: Dict[str, Any] = {
            "authToken": "eyJh...secure_token",
            "theme": "dark",
            "counter": 42
        }

    def serialize_payload(self, data: Any) -> str:
        return json.dumps(data)

    def deserialize_payload(self, raw_json: str) -> Any:
        return json.loads(raw_json)

    def dispatch_call_async(self, module: str, method: str, args: List[Any]) -> Dict[str, Any]:
        """Mengirim pesan dari JS ke Native melalui Bridge."""
        # 1. JS Thread: Serialisasi
        t0 = time.perf_counter()
        serialized = self.serialize_payload({"module": module, "method": method, "args": args})
        payload_size_bytes = len(serialized.encode("utf-8"))

        # 2. Bridge Queue
        call_packet = {
            "call_id": random.randint(1000, 9999),
            "payload": serialized,
            "timestamp": time.time()
        }
        self.bridge_queue.append(call_packet)

        # 3. Native Thread: Dequeue & Deserialisasi
        queued_item = self.bridge_queue.pop(0)
        unpacked = self.deserialize_payload(queued_item["payload"])

        # 4. Native Execution (Simulasi)
        result = None
        if unpacked["method"] == "getItem":
            key = unpacked["args"][0]
            result = self.native_storage.get(key, None)
        elif unpacked["method"] == "setItem":
            key, val = unpacked["args"][0], unpacked["args"][1]
            self.native_storage[key] = val
            result = True
        elif unpacked["method"] == "computeHash":
            data = unpacked["args"][0]
            result = f"hash_{hash(str(data)) & 0xFFFFFFFF:08x}"

        # 5. Return via Callback Queue (Serialization lagi)
        response_json = self.serialize_payload({"result": result, "status": "ok"})
        native_response = self.deserialize_payload(response_json)
        t1 = time.perf_counter()

        elapsed_us = (t1 - t0) * 1_000_000
        return {
            "result": native_response["result"],
            "payload_size_bytes": payload_size_bytes,
            "elapsed_us": elapsed_us
        }


class JSIHostObjectSimulator:
    """
    Simulasi Arsitektur Baru (New Architecture / JSI & TurboModules):
    - JavaScript runtime (Hermes/V8) memiliki pointer C++ langsung ke HostObject.
    - Zero JSON serialization (Direct Memory / Reference Passing).
    - Mendukung synchronous call langsung di JS thread atau thread native terpisah.
    """

    def __init__(self) -> None:
        self._cpp_host_memory: Dict[str, Any] = {
            "authToken": "eyJh...secure_token",
            "theme": "dark",
            "counter": 42
        }

    def direct_invoke(self, method: str, *args: Any) -> Dict[str, Any]:
        """Eksekusi sinkron langsung melalui JSI C++ HostObject."""
        t0 = time.perf_counter()

        # Tidak ada konversi string JSON, referensi objek langsung diakses
        result = None
        if method == "getItem":
            key = args[0]
            result = self._cpp_host_memory.get(key, None)
        elif method == "setItem":
            key, val = args[0], args[1]
            self._cpp_host_memory[key] = val
            result = True
        elif method == "computeHash":
            data = args[0]
            result = f"hash_{hash(str(data)) & 0xFFFFFFFF:08x}"

        t1 = time.perf_counter()
        elapsed_us = (t1 - t0) * 1_000_000

        return {
            "result": result,
            "payload_size_bytes": sys.getsizeof(args),
            "elapsed_us": elapsed_us
        }


def print_banner() -> None:
    print(f"{Colors.HEADER}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}   REACT NATIVE ARCHITECTURE LAB: BRIDGE vs JSI TURBOMODULES{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.YELLOW}Topik: Deep Dive Native Modules, C++ HostObject, dan Message Queue{Colors.RESET}\n")


def demo_trace_bridge(bridge: LegacyBridgeSimulator) -> None:
    print(f"\n{Colors.BOLD}{Colors.BLUE}[TRACE 1] Alur Komunikasi Melalui Legacy Bridge (Asynchronous JSON){Colors.RESET}")
    print(f"{Colors.CYAN}1. JS Thread:{Colors.RESET} NativeModules.StorageModule.getItem('authToken') dipanggil.")
    print(f"{Colors.CYAN}2. Serialisasi:{Colors.RESET} Parameter dikonversi ke format JSON string.")
    
    t0 = time.perf_counter()
    res = bridge.dispatch_call_async("StorageModule", "getItem", ["authToken"])
    t1 = time.perf_counter()

    print(f"{Colors.CYAN}3. Message Queue:{Colors.RESET} Payload ditambahkan ke batch queue (Buffer C++ bridge).")
    print(f"{Colors.CYAN}4. Native Thread:{Colors.RESET} Java/Obj-C thread parse JSON, baca memori, lalu serialize response.")
    print(f"{Colors.CYAN}5. Callback Dispatch:{Colors.RESET} Hasil dikirim kembali ke JavaScript context via batched bridge.")
    print(f"{Colors.GREEN}✔ Hasil diterima JS:{Colors.RESET} {res['result']}")
    print(f"{Colors.YELLOW}ℹ Payload size:{Colors.RESET} {res['payload_size_bytes']} bytes")
    print(f"{Colors.YELLOW}ℹ Waktu round-trip bridge:{Colors.RESET} {res['elapsed_us']:.2f} µs\n")


def demo_trace_jsi(jsi: JSIHostObjectSimulator) -> None:
    print(f"\n{Colors.BOLD}{Colors.BLUE}[TRACE 2] Alur Komunikasi Melalui JSI / TurboModules (Direct C++ HostObject){Colors.RESET}")
    print(f"{Colors.CYAN}1. JS Thread:{Colors.RESET} global.__storageHostObject.getItem('authToken') dipanggil.")
    print(f"{Colors.CYAN}2. Direct C++ Binding:{Colors.RESET} Hermes memanggil jsi::HostObject::get() secara langsung.")
    print(f"{Colors.CYAN}3. Zero-Copy Exec:{Colors.RESET} Memory buffer dibaca tanpa JSON serialization.")
    
    res = jsi.direct_invoke("getItem", "authToken")

    print(f"{Colors.GREEN}✔ Nilai langsung dikembalikan synchronously ke JS CallStack!{Colors.RESET}")
    print(f"{Colors.GREEN}✔ Hasil:{Colors.RESET} {res['result']}")
    print(f"{Colors.YELLOW}ℹ Memory overhead args:{Colors.RESET} {res['payload_size_bytes']} bytes")
    print(f"{Colors.YELLOW}ℹ Waktu eksekusi JSI:{Colors.RESET} {res['elapsed_us']:.2f} µs\n")


def benchmark_comparison(bridge: LegacyBridgeSimulator, jsi: JSIHostObjectSimulator, iterations: int = 5000) -> None:
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== BENCHMARK: {iterations:,} ITERASI PEMANGGILAN NATIVE ==={Colors.RESET}")
    test_data = {"user": "developer_alpha", "roles": ["admin", "mobile_lead"], "active": True}

    # 1. Benchmark Bridge
    print(f"{Colors.CYAN}Menjalankan uji Legacy Bridge...{Colors.RESET}")
    t0 = time.perf_counter()
    total_bridge_bytes = 0
    for _ in range(iterations):
        res = bridge.dispatch_call_async("NativeUtility", "computeHash", [test_data])
        total_bridge_bytes += res["payload_size_bytes"]
    t_bridge = time.perf_counter() - t0

    # 2. Benchmark JSI
    print(f"{Colors.CYAN}Menjalankan uji JSI Direct HostObject...{Colors.RESET}")
    t0 = time.perf_counter()
    total_jsi_bytes = 0
    for _ in range(iterations):
        res = jsi.direct_invoke("computeHash", test_data)
        total_jsi_bytes += res["payload_size_bytes"]
    t_jsi = time.perf_counter() - t0

    # Output Summary
    print(f"\n{Colors.BOLD}--- HASIL PERBANDINGAN PERFORMA ---{Colors.RESET}")
    print(f"Legacy Bridge Total Time : {Colors.RED}{t_bridge * 1000:.2f} ms{Colors.RESET} ({t_bridge/iterations*1_000_000:.2f} µs/call)")
    print(f"JSI HostObject Total Time: {Colors.GREEN}{t_jsi * 1000:.2f} ms{Colors.RESET} ({t_jsi/iterations*1_000_000:.2f} µs/call)")
    
    speedup = t_bridge / t_jsi if t_jsi > 0 else 1.0
    print(f"{Colors.BOLD}{Colors.GREEN}Akselerasi JSI : {speedup:.2f}x LEBIH CEPAT{Colors.RESET}")
    print(f"JSON Bridge Serialized Overhead : {total_bridge_bytes / 1024:.2f} KB transfer data")
    print(f"JSI Memory Overhead             : Minimal (Direct pointer reference)\n")


def display_threads_architecture() -> None:
    print(f"\n{Colors.BOLD}{Colors.YELLOW}=== ARSITEKTUR THREAD REACT NATIVE ==={Colors.RESET}")
    print(f"""
  {Colors.CYAN}[ JS Thread (Hermes Engine) ]{Colors.RESET}
            │
            ├── (Legacy) ──> [ JSON Stringify ] ──> [ MessageQueue ] ──> [ Native Bridge ] ──> (UI/Native Thread)
            │
            └── (JSI) ─────> [ jsi::Runtime ] ───> [ C++ HostObject Direct Invocation ] ────> (Instant Sync/Async)
    """)
    print(f"{Colors.BOLD}1. JS Thread:{Colors.RESET} Menjalankan kode bundle JavaScript & business logic React.")
    print(f"{Colors.BOLD}2. Shadow Thread:{Colors.RESET} Menghitung layout flexbox melalui Yoga engine (C++).")
    print(f"{Colors.BOLD}3. UI/Main Thread:{Colors.RESET} Menggambar native views (Android Views / iOS UIViews).")
    print(f"{Colors.BOLD}4. TurboModules:{Colors.RESET} Inisialisasi on-demand, hanya saat module pertama kali dibutuhkan.\n")


def interactive_menu() -> None:
    bridge = LegacyBridgeSimulator()
    jsi = JSIHostObjectSimulator()

    while True:
        print_banner()
        print(f"{Colors.BOLD}PILIHAN LAB INTERAKTIF:{Colors.RESET}")
        print("1. Trace Call: Legacy Bridge (JSON Serialization & Async Queue)")
        print("2. Trace Call: JSI / TurboModules (Direct C++ HostObject)")
        print("3. Benchmark: 5.000 Call Bridge vs JSI")
        print("4. Diagram Arsitektur Threading")
        print("5. Jalankan Semua Uji (Automated Test Run)")
        print("6. Keluar")

        try:
            choice = input(f"\n{Colors.BOLD}Masukkan pilihan (1-6): {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            demo_trace_bridge(bridge)
        elif choice == "2":
            demo_trace_jsi(jsi)
        elif choice == "3":
            benchmark_comparison(bridge, jsi, iterations=5000)
        elif choice == "4":
            display_threads_architecture()
        elif choice == "5":
            demo_trace_bridge(bridge)
            demo_trace_jsi(jsi)
            display_threads_architecture()
            benchmark_comparison(bridge, jsi, iterations=5000)
        elif choice == "6":
            print(f"{Colors.GREEN}Sesi lab selesai. Terima kasih.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan masukkan angka 1-6.{Colors.RESET}")

        if not sys.stdin.isatty():
            # Jika dijalankan secara non-interaktif, otomatis selesai setelah 1 pass
            break

        input(f"{Colors.UNDERLINE}Tekan [Enter] untuk melanjutkan...{Colors.RESET}")


def main() -> None:
    # Jika dieksekusi tanpa terminal interaktif, jalankan automated suite
    if not sys.stdin.isatty() or len(sys.argv) > 1 and sys.argv[1] == "--auto":
        bridge = LegacyBridgeSimulator()
        jsi = JSIHostObjectSimulator()
        print_banner()
        demo_trace_bridge(bridge)
        demo_trace_jsi(jsi)
        display_threads_architecture()
        benchmark_comparison(bridge, jsi, iterations=2000)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
