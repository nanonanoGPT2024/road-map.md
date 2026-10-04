#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Arsitektur Inti React Native (Old vs New Architecture)
BAB-01: Fondasi dan Arsitektur React Native

Simulasi teknis mencakup:
1. Old Architecture Bridge: Asynchronous JSON serialization bottleneck
2. New Architecture JSI (JavaScript Interface): Direct synchronous C++ host objects
3. Fabric Renderer: C++ Yoga Layout & Shadow Tree immutability
4. TurboModules: On-demand (lazy) loading vs Eager loading native modules
5. Threading Model: JS Thread, Shadow/Layout Thread, Native UI Thread
"""

import sys
import time
import json
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# ANSI Escape Codes untuk formatting terminal
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


def print_banner():
    banner = f"""
{CYAN}{BOLD}========================================================================{RESET}
{MAGENTA}{BOLD}   REACT NATIVE FOUNDATIONS & ARCHITECTURE SIMULATOR (BAB-01)          {RESET}
{CYAN}{BOLD}========================================================================{RESET}
{WHITE}Simulasi Interaktif: Bridge vs JSI, Fabric Engine, TurboModules & Threads{RESET}
"""
    print(banner)


def divider(title: str = ""):
    if title:
        print(f"\n{BLUE}{BOLD}[--- {title.upper()} ---]{RESET}")
    else:
        print(f"{DIM}{'-' * 70}{RESET}")


@dataclass
class BridgeMessage:
    module: str
    method: str
    args: List[Any]
    call_id: int


class BridgeSimulator:
    """
    Simulasi Arsitektur Lama (Old Architecture):
    - Menggunakan asynchronous JSON serialized bridge
    - Memiliki overhead serialization/deserialization
    - Rentan terhadap thread congestion (bottleneck)
    """
    def __init__(self):
        self.queue: List[str] = []
        self.call_counter = 0

    def invoke_native_call(self, module: str, method: str, args: List[Any]) -> Dict[str, Any]:
        self.call_counter += 1
        msg = BridgeMessage(module, method, args, self.call_counter)

        # 1. Serialization Overhead (JSON stringify di JS Thread)
        t_start = time.perf_counter()
        payload = json.dumps({"module": msg.module, "method": msg.method, "args": msg.args, "id": msg.call_id})
        time.sleep(0.0008 + random.uniform(0.0002, 0.0008)) # simulasi latency serialization JS

        # 2. Antrian Bridge (Asynchronous Queueing)
        self.queue.append(payload)
        queue_latency = 0.0012 + (len(self.queue) * 0.0003)
        time.sleep(queue_latency)

        # 3. Deserialization di Native Thread (C++/Java/Obj-C)
        parsed = json.loads(self.queue.pop(0))
        time.sleep(0.0005) # deserialization cost

        t_end = time.perf_counter()
        elapsed_ms = (t_end - t_start) * 1000

        return {
            "mode": "Bridge (JSON/Async)",
            "call_id": parsed["id"],
            "elapsed_ms": elapsed_ms,
            "payload_bytes": len(payload.encode('utf-8')),
            "synchronous": False
        }


class JSISimulator:
    """
    Simulasi Arsitektur Baru (New Architecture - JSI):
    - Menggunakan C++ Host Objects
    - Zero serialization overhead (Direct Memory Reference)
    - Synchronous execution capability & low memory footprint
    """
    def __init__(self):
        # Simulasi shared memory / C++ host object registry
        self.host_objects: Dict[str, Dict[str, Any]] = {
            "DeviceStorage": {"cache": {}},
            "HardwareSensor": {"sampling_rate": 60}
        }
        self.call_counter = 0

    def invoke_direct_call(self, module: str, method: str, args: List[Any]) -> Dict[str, Any]:
        self.call_counter += 1
        t_start = time.perf_counter()

        # Direct pointer access melalui C++ JSI binding (Zero JSON stringify)
        time.sleep(0.00008 + random.uniform(0.00002, 0.00006)) # C++ pointer dispatch overhead

        # Eksekusi instan pada host object
        if module not in self.host_objects:
            self.host_objects[module] = {}
        self.host_objects[module][method] = args

        t_end = time.perf_counter()
        elapsed_ms = (t_end - t_start) * 1000

        return {
            "mode": "JSI (C++ Direct Pointer)",
            "call_id": self.call_counter,
            "elapsed_ms": elapsed_ms,
            "payload_bytes": 0,  # Shared memory pointer
            "synchronous": True
        }


class FabricRendererSimulator:
    """
    Simulasi Fabric (Concurrent Rendering System):
    - Immutability pada Shadow Nodes
    - Integrasi mesin layout Yoga (C++ cross-platform Flexbox)
    - Thread-safe mount update langsung ke Native UI Host Views
    """
    def __init__(self):
        self.revision = 0

    def render_component_tree(self, node_count: int) -> Dict[str, Any]:
        self.revision += 1
        t_start = time.perf_counter()

        # Step 1: JS Virtual DOM Reconciliation (React 18 Concurrent Features)
        js_phase_time = node_count * 0.00005
        time.sleep(js_phase_time)

        # Step 2: C++ Shadow Tree Generation (Immutable Nodes)
        shadow_phase_time = node_count * 0.00003
        time.sleep(shadow_phase_time)

        # Step 3: Yoga Engine C++ Flexbox Layout Calculation
        yoga_calc_time = node_count * 0.00004
        time.sleep(yoga_calc_time)

        # Step 4: Mount Phase (Diffing & Native OS View Hierarchy Update)
        mount_time = node_count * 0.00002
        time.sleep(mount_time)

        t_end = time.perf_counter()
        total_ms = (t_end - t_start) * 1000

        return {
            "revision": self.revision,
            "nodes_rendered": node_count,
            "total_ms": total_ms,
            "phases_ms": {
                "js_reconcile": js_phase_time * 1000,
                "shadow_tree_cxx": shadow_phase_time * 1000,
                "yoga_flexbox": yoga_calc_time * 1000,
                "native_mount": mount_time * 1000
            }
        }


class TurboModuleSimulator:
    """
    Simulasi TurboModules:
    - Lazy Loading (diinisialisasi hanya saat method pertama kali dipanggil)
    - Dibandingkan dengan Bridge Eager Loading saat aplikasi bootstrap
    """
    def __init__(self):
        self.available_modules = [
            "CameraManager", "Biometrics", "BluetoothLE", 
            "FileSystemAccess", "GeolocationService", "SecureEnclave"
        ]
        self.eager_loaded: Dict[str, bool] = {}
        self.turbo_loaded: Dict[str, bool] = {}

    def simulate_app_startup_eager(self) -> float:
        """Old Architecture: Memuat SEMUA native module sekaligus di startup"""
        t_start = time.perf_counter()
        for mod in self.available_modules:
            time.sleep(0.015 + random.uniform(0.005, 0.010)) # biaya inisialisasi modul Java/Obj-C
            self.eager_loaded[mod] = True
        t_end = time.perf_counter()
        return (t_end - t_start) * 1000

    def simulate_app_startup_turbo(self) -> float:
        """New Architecture: Zero eagerly initialized modules di startup"""
        t_start = time.perf_counter()
        # TurboModules register JSI spec stubs secara instan (C++ table lookup)
        time.sleep(0.001)
        t_end = time.perf_counter()
        return (t_end - t_start) * 1000

    def invoke_turbo_module(self, name: str) -> Dict[str, Any]:
        t_start = time.perf_counter()
        is_first_load = name not in self.turbo_loaded

        if is_first_load:
            time.sleep(0.012) # On-demand JSI binding & native module creation
            self.turbo_loaded[name] = True
            cost_type = "Cold Init (First Call)"
        else:
            time.sleep(0.0001) # Cached JSI HostObject dispatch
            cost_type = "Hot Dispatch (Cached)"

        t_end = time.perf_counter()
        return {
            "module": name,
            "cost_type": cost_type,
            "elapsed_ms": (t_end - t_start) * 1000
        }


# ==============================================================================
# INTERAKTIF MENU & HANDLERS
# ==============================================================================

def run_bridge_vs_jsi_demo():
    divider("Simulasi 1: Bridge Serialization vs JSI Direct Execution")
    print(f"{WHITE}Membandingkan 50 batch komunikasi JS <-> Native (misal: scroll event/sensor data)...{RESET}\n")

    bridge = BridgeSimulator()
    jsi = JSISimulator()

    iterations = 50
    bridge_latencies = []
    jsi_latencies = []

    print(f"{BOLD}{'Iterasi':<8} | {'Bridge Latency':<18} | {'JSI Latency':<18} | {'Speedup':<12}{RESET}")
    print("-" * 65)

    for i in range(1, iterations + 1):
        payload = [f"data_point_{i}", random.randint(100, 999)]
        res_bridge = bridge.invoke_native_call("SensorTracker", "pushCoord", payload)
        res_jsi = jsi.invoke_direct_call("SensorTracker", "pushCoord", payload)

        bridge_latencies.append(res_bridge["elapsed_ms"])
        jsi_latencies.append(res_jsi["elapsed_ms"])

        if i <= 5 or i % 10 == 0:
            speedup = res_bridge["elapsed_ms"] / res_jsi["elapsed_ms"]
            print(f"Call #{i:<4} | {RED}{res_bridge['elapsed_ms']:>8.3f} ms (JSON){RESET} | "
                  f"{GREEN}{res_jsi['elapsed_ms']:>8.3f} ms (C++){RESET}  | "
                  f"{YELLOW}{speedup:>6.1f}x lebih cepat{RESET}")

    avg_bridge = sum(bridge_latencies) / len(bridge_latencies)
    avg_jsi = sum(jsi_latencies) / len(jsi_latencies)

    print("\n" + "=" * 65)
    print(f"{BOLD}HASIL RATA-RATA DARI {iterations} PANGGILAN:{RESET}")
    print(f" - Bridge Rata-rata : {RED}{BOLD}{avg_bridge:.4f} ms{RESET} (Serialized string bottleneck)")
    print(f" - JSI Rata-rata    : {GREEN}{BOLD}{avg_jsi:.4f} ms{RESET} (Zero-copy shared memory pointer)")
    print(f" - Peningkatan      : {CYAN}{BOLD}{avg_bridge / avg_jsi:.1f}x Performa Lebih Responsif{RESET}")
    print("=" * 65)


def run_fabric_renderer_demo():
    divider("Simulasi 2: Fabric Concurrent Renderer & Yoga Engine Layout")
    renderer = FabricRendererSimulator()

    test_sizes = [50, 200, 1000]
    print(f"{WHITE}Menguji proses render pohon UI (Reconcile -> C++ Shadow -> Yoga -> Native Mount):{RESET}\n")

    for size in test_sizes:
        res = renderer.render_component_tree(size)
        print(f"{CYAN}{BOLD}--- Rendering Tree dengan {size} Komponen (Revision #{res['revision']}) ---{RESET}")
        print(f"  • Total Frame Time     : {YELLOW}{res['total_ms']:.2f} ms{RESET} (Target 60 FPS: < 16.6 ms)")
        print(f"  • 1. React Reconcile   : {res['phases_ms']['js_reconcile']:.2f} ms")
        print(f"  • 2. Shadow Tree (C++) : {res['phases_ms']['shadow_tree_cxx']:.2f} ms")
        print(f"  • 3. Yoga Flexbox C++  : {res['phases_ms']['yoga_flexbox']:.2f} ms")
        print(f"  • 4. OS View Mount     : {res['phases_ms']['native_mount']:.2f} ms")

        if res['total_ms'] < 16.6:
            print(f"  Status: {GREEN}[MEMENUHI 60 FPS BUDGET]{RESET}\n")
        else:
            print(f"  Status: {RED}[FRAME DROP / JANK DETECTED]{RESET} (Perlu optimasi VirtualizedList)\n")


def run_turbomodules_demo():
    divider("Simulasi 3: TurboModules (Lazy Load) vs Eager Loading")
    turbo_sim = TurboModuleSimulator()

    print(f"{WHITE}1. Mengukur Waktu Startup Aplikasi (App Cold Launch):{RESET}")
    eager_time = turbo_sim.simulate_app_startup_eager()
    turbo_time = turbo_sim.simulate_app_startup_turbo()

    print(f"   - Old Arch (Eager Loading 6 Modules) : {RED}{BOLD}{eager_time:.2f} ms{RESET}")
    print(f"   - New Arch (TurboModules Lazy Spec)  : {GREEN}{BOLD}{turbo_time:.2f} ms{RESET}")
    print(f"   - Peningkatan Waktu Startup          : {YELLOW}{BOLD}{eager_time / turbo_time:.1f}x Lebih Cepat Booting{RESET}\n")

    print(f"{WHITE}2. Menguji Eksekusi On-Demand (Lazy Initialization):{RESET}")
    modules_to_call = ["CameraManager", "CameraManager", "Biometrics", "CameraManager"]

    for mod in modules_to_call:
        res = turbo_sim.invoke_turbo_module(mod)
        color = YELLOW if "Cold" in res["cost_type"] else GREEN
        print(f"   Invoke {CYAN}{res['module']:<18}{RESET} -> {color}{res['cost_type']:<24}{RESET} [{res['elapsed_ms']:.3f} ms]")


def run_thread_model_architecture_demo():
    divider("Simulasi 4: Model Tiga Thread React Native & Event Loop")
    print(f"""
{BOLD}React Native Threading Architecture:{RESET}
 {MAGENTA}[JS Thread]{RESET}        : Logika Bisnis, React State, Lifecycle, JS Bundle (Hermes VM)
       |
       v (JSI / C++ Host Objects)
 {CYAN}[Shadow Thread]{RESET}    : Yoga Layout Engine, C++ Shadow Tree, Pengukuran Flexbox
       |
       v (Direct Thread-Safe Mount)
 {GREEN}[Native UI Thread]{RESET} : Platform Views (Android ViewGroup / iOS UIView), Gestures & Paint
""")

    print(f"{WHITE}Mensimulasikan flow sentuhan layar pengguna (Touch Event):{RESET}")
    time.sleep(0.3)
    print(f"  1. {GREEN}[Native UI Thread]{RESET} Menangkap event 'onPress' pada tombol...")
    time.sleep(0.3)
    print(f"  2. {CYAN}[Shadow Thread]{RESET}    Memvalidasi batas koordinat view (hit-test)...")
    time.sleep(0.3)
    print(f"  3. {MAGENTA}[JS Thread]{RESET}        Mengeksekusi handler onClick, setState({{ count: count + 1 }})...")
    time.sleep(0.3)
    print(f"  4. {CYAN}[Shadow Thread]{RESET}    Yoga C++ menghitung ulang ukuran dan batas box model baru...")
    time.sleep(0.3)
    print(f"  5. {GREEN}[Native UI Thread]{RESET} Memperbarui teks pada elemen TextView / UILabel bawaan OS.")
    print(f"\n{GREEN}{BOLD}Pipeline selesai tanpa hambatan serialisasi string JSON!{RESET}")


def main_menu():
    while True:
        print_banner()
        print(f"{BOLD}PILIH SIMULASI FONDASI REACT NATIVE:{RESET}")
        print(f"  {CYAN}1.{RESET} Perbandingan Performa The Bridge vs JSI (Serialization vs C++ Pointer)")
        print(f"  {CYAN}2.{RESET} Simulasi Fabric Renderer & Mesin Layout Yoga C++")
        print(f"  {CYAN}3.{RESET} Simulasi TurboModules: Startup Time & Lazy Loading")
        print(f"  {CYAN}4.{RESET} Analisis Model 3 Thread (JS, Shadow, Native UI)")
        print(f"  {CYAN}5.{RESET} Jalankan Seluruh Rangkaian Simulasi Lengkap")
        print(f"  {CYAN}0.{RESET} Keluar (Exit)")
        print("-" * 70)

        choice = input(f"{YELLOW}Masukkan pilihan (0-5) [default 5]: {RESET}").strip()
        if not choice:
            choice = "5"

        if choice == "1":
            run_bridge_vs_jsi_demo()
        elif choice == "2":
            run_fabric_renderer_demo()
        elif choice == "3":
            run_turbomodules_demo()
        elif choice == "4":
            run_thread_model_architecture_demo()
        elif choice == "5":
            run_bridge_vs_jsi_demo()
            run_fabric_renderer_demo()
            run_turbomodules_demo()
            run_thread_model_architecture_demo()
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih! Lab Fondasi Arsitektur React Native selesai.{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")

        input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")


if __name__ == "__main__":
    try:
        # Jika dijalankan non-interaktif (piped input/CI), jalankan mode otomatis opsi 5
        if not sys.stdin.isatty():
            print_banner()
            run_bridge_vs_jsi_demo()
            run_fabric_renderer_demo()
            run_turbomodules_demo()
            run_thread_model_architecture_demo()
            print(f"\n{GREEN}Automated run completed successfully.{RESET}")
        else:
            main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Simulasi dihentikan oleh user.{RESET}")
        sys.exit(0)
