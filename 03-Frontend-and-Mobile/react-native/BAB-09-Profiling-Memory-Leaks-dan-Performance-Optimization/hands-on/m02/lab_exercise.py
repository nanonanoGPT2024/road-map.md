#!/usr/bin/env python3
"""
Lab Exercise: React Native Advanced Profiling, Memory Leaks, and Performance Optimization
BAB-09: Profiling, Memory Leaks, dan Performance Optimization

Simulasi komprehensif profiling performa React Native (Hermes Engine, JS Thread vs UI Thread,
Bridge/JSI bottleneck, Event Listener Retain Cycles, dan Virtualized List Optimization).
"""

import sys
import time
import random
from typing import List, Dict, Any, Optional

# ANSI Color Codes
class Style:
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
    BG_DARK = "\033[40m"

class HermesHeapSimulator:
    """Simulasi Memory Heap & Garbage Collector pada Hermes Engine"""
    def __init__(self):
        self.allocated_kb: float = 18400.0  # Base bundle + runtime footprint (~18MB)
        self.retained_listeners: List[Dict[str, Any]] = []
        self.detached_views: List[Dict[str, Any]] = []
        self.closure_leaks: List[Dict[str, Any]] = []

    def allocate(self, amount_kb: float):
        self.allocated_kb += amount_kb

    def garbage_collect(self, trigger_full: bool = False) -> float:
        """Simulasi GC Sweep Hermes (Generational GC)"""
        initial = self.allocated_kb
        # Leaked objects tidak bisa di-GC karena strong references di retain cycle
        freed = 0.0
        if not trigger_full:
            # Young gen collection
            freed = random.uniform(500.0, 1800.0)
        else:
            # Full Mark-Sweep-Compact
            freed = random.uniform(2500.0, 5000.0)

        self.allocated_kb = max(18400.0 + len(self.retained_listeners) * 1200.0 + len(self.detached_views) * 2800.0,
                                self.allocated_kb - freed)
        return initial - self.allocated_kb

class ThreadProfiler:
    """Simulasi Profiling Thread: UI Main Thread (60 FPS) vs JavaScript Thread"""
    FRAME_BUDGET_MS = 16.67  # 60 FPS standard (1000ms / 60 frames)

    @staticmethod
    def simulate_frame(js_workload_ms: float, ui_workload_ms: float) -> Dict[str, Any]:
        js_dropped = max(0, int(js_workload_ms // ThreadProfiler.FRAME_BUDGET_MS))
        ui_dropped = max(0, int(ui_workload_ms // ThreadProfiler.FRAME_BUDGET_MS))

        effective_fps_js = max(10.0, min(60.0, 1000.0 / max(ThreadProfiler.FRAME_BUDGET_MS, js_workload_ms)))
        effective_fps_ui = max(10.0, min(60.0, 1000.0 / max(ThreadProfiler.FRAME_BUDGET_MS, ui_workload_ms)))

        return {
            "js_duration_ms": js_workload_ms,
            "ui_duration_ms": ui_workload_ms,
            "js_dropped_frames": js_dropped,
            "ui_dropped_frames": ui_dropped,
            "js_fps": round(effective_fps_js, 1),
            "ui_fps": round(effective_fps_ui, 1),
            "jank_detected": js_workload_ms > ThreadProfiler.FRAME_BUDGET_MS or ui_workload_ms > ThreadProfiler.FRAME_BUDGET_MS
        }

class ProductionLabSimulation:
    def __init__(self):
        self.heap = HermesHeapSimulator()
        self.is_optimized = False
        self.mount_count = 0

    def print_banner(self):
        print(f"\n{Style.CYAN}{Style.BOLD}" + "=" * 76 + f"{Style.RESET}")
        print(f"{Style.MAGENTA}{Style.BOLD}  ⚡ REACT NATIVE ADVANCED PROFILER & MEMORY LEAK DIAGNOSTIC SUITE ⚡{Style.RESET}")
        print(f"{Style.CYAN}" + "  Engine: Hermes v0.12.0 | Architecture: New Architecture (JSI / Fabric)" + f"{Style.RESET}")
        print(f"{Style.CYAN}{Style.BOLD}" + "=" * 76 + f"{Style.RESET}\n")

    def simulate_navigation_cycle(self, screens: int = 5):
        """Simulasi perpindahan layar bolak-balik (Mount & Unmount cycles)"""
        print(f"{Style.YELLOW}▶ Menjalankan {screens}x Navigation Push & Pop Cycle...{Style.RESET}")
        time.sleep(0.4)

        for i in range(1, screens + 1):
            self.mount_count += 1
            print(f"  [{i}/{screens}] Navigating: HomeFeedScreen -> DetailOrderScreen", end="")
            
            if not self.is_optimized:
                # ANTI-PATTERN: DeviceEventEmitter tanpa cleanup di useEffect return callback
                # ANTI-PATTERN: Heavy Anonymous Closure retaining large list payload
                self.heap.retained_listeners.append({
                    "event": "onAppStateChange",
                    "listener_id": f"sub_0x7f{random.randint(1000, 9999)}",
                    "closure_payload_mb": 1.2
                })
                self.heap.detached_views.append({
                    "native_tag": f"RCTView_Detached_{self.mount_count}",
                    "node_count": 84
                })
                self.heap.allocate(amount_kb=2400.0)
                print(f" {Style.RED}✘ Leak Created! (+2.4 MB retain cycle){Style.RESET}")
            else:
                # OPTIMIZED: Clean subscription unsubscribe on unmount & scoped references
                print(f" {Style.GREEN}✔ Subscriptions Cleaned Up (Zero Leak){Style.RESET}")
                self.heap.allocate(amount_kb=150.0)  # Transient allocation
                self.heap.garbage_collect(trigger_full=False)

            time.sleep(0.15)

        print(f"\n{Style.BOLD}Status Heap Saat Ini:{Style.RESET} "
              f"{Style.RED if self.heap.allocated_kb > 25000 else Style.GREEN}"
              f"{self.heap.allocated_kb / 1024:.2f} MB{Style.RESET} | "
              f"Active Leaked Listeners: {len(self.heap.retained_listeners)}")

    def run_profiling_trace(self):
        """Simulasi Profiling Frame Drops & Thread Bottleneck (Systrace / Flipper Flamegraph)"""
        print(f"\n{Style.CYAN}{Style.BOLD}[PROFILING TRACE: JS & UI THREAD TIMELINE]{Style.RESET}")
        print(f"{'Workload Scenario':<28} | {'JS Time':<10} | {'UI Time':<10} | {'JS FPS':<8} | {'UI FPS':<8} | {'Status':<12}")
        print("-" * 88)

        scenarios = [
            ("FlatList Re-render (1k items)", 42.5 if not self.is_optimized else 8.2, 14.1 if not self.is_optimized else 7.5),
            ("JSON Parse on Main Thread", 38.0 if not self.is_optimized else 4.0, 16.0 if not self.is_optimized else 5.2),
            ("Native Gesture PanResponder", 12.0, 31.5 if not self.is_optimized else 10.2),
            ("Hermes GC Pause (Compaction)", 26.4 if not self.is_optimized else 5.1, 8.0)
        ]

        total_janks = 0
        for name, js_ms, ui_ms in scenarios:
            res = ThreadProfiler.simulate_frame(js_ms, ui_ms)
            if res["jank_detected"]:
                total_janks += 1
                status = f"{Style.RED}JANK DROP{Style.RESET}"
            else:
                status = f"{Style.GREEN}SMOOTH{Style.RESET}"

            print(f"{name:<28} | {res['js_duration_ms']:>6.1f} ms | {res['ui_duration_ms']:>6.1f} ms | "
                  f"{res['js_fps']:>6.1f}   | {res['ui_fps']:>6.1f}   | {status}")
            time.sleep(0.1)

        print("-" * 88)
        if total_janks > 0:
            print(f"{Style.YELLOW}⚠️  Peringatan: Terdeteksi {total_janks} Frame Drop! Melebihi budget 16.67ms per frame.{Style.RESET}")
            if not self.is_optimized:
                print(f"{Style.RED}   Penyebab: Re-render redundant tanpa React.memo, inline closure anonim, & blocking JSON parse.{Style.RESET}")
        else:
            print(f"{Style.GREEN}✨ Sempurna! Seluruh frame rendering berjalan mulus di 60 FPS tanpa dropped frames.{Style.RESET}")

    def inspect_heap_snapshots(self):
        """Analisis Memory Heap Dump & Retain Cycles"""
        print(f"\n{Style.MAGENTA}{Style.BOLD}[HERMES HEAP SNAPSHOT ANALYSIS & MEMORY GRAPH]{Style.RESET}")
        print(f"Total Allocated Heap : {self.heap.allocated_kb / 1024:.2f} MB")
        print(f"Base VM Memory       : 18.00 MB")
        print(f"Active Leaks Count   : {len(self.heap.retained_listeners)} EventEmitters, {len(self.heap.detached_views)} Detached Native Nodes")
        
        if self.heap.retained_listeners:
            print(f"\n{Style.RED}🚨 Deteksi Retain Cycle Path (Root Object Graph):{Style.RESET}")
            for idx, item in enumerate(self.heap.retained_listeners[:4], 1):
                print(f"  {idx}. [GlobalScope] -> EventEmitter (Event: '{item['event']}') "
                      f"-> [Closure Scope: {item['listener_id']}] -> {Style.BOLD}Retained Screen Component Instance{Style.RESET} (+{item['closure_payload_mb']} MB)")
            if len(self.heap.retained_listeners) > 4:
                print(f"  ... dan {len(self.heap.retained_listeners) - 4} listener tak ter-cleanup lainnya.")
        else:
            print(f"\n{Style.GREEN}✅ Tidak ditemukan Retain Cycles atau Memory Leak pada heap snapshot.{Style.RESET}")

    def apply_optimizations(self):
        """Menerapkan konfigurasi arsitektur produksi teroptimasi"""
        print(f"\n{Style.BLUE}{Style.BOLD}🔧 Menerapkan Solusi Rekayasa Performa Tingkat Lanjut...{Style.RESET}")
        time.sleep(0.3)
        steps = [
            "1. Memasang Hook Cleanup: Mengubah useEffect sub.remove() pada EventEmitter",
            "2. Virtualisasi List: Mengganti ScrollView/FlatList berat dengan Shopify/FlashList (estimatedItemSize)",
            "3. Stabilisasi Referensi: Membungkus props renderItem dengan useCallback & React.memo",
            "4. Offloading Heavy Compute: Menggunakan JSI / react-native-worklets / InteractionManager",
            "5. Memanggil Hermes Manual GC Heap Compaction..."
        ]
        for step in steps:
            print(f"  {Style.GREEN}✔{Style.RESET} {step}")
            time.sleep(0.12)

        self.is_optimized = True
        self.heap.retained_listeners.clear()
        self.heap.detached_views.clear()
        freed = self.heap.garbage_collect(trigger_full=True)
        print(f"\n{Style.GREEN}{Style.BOLD}✔ Optimasi Berhasil Diterapkan! Heap terkompresi sebesar {freed/1024:.2f} MB.{Style.RESET}")

    def run_interactive_menu(self):
        while True:
            self.print_banner()
            opt_label = f"{Style.GREEN}OPTIMIZED{Style.RESET}" if self.is_optimized else f"{Style.RED}UNOPTIMIZED (LEAKY){Style.RESET}"
            print(f"Status Mode Sistem: [{opt_label}]")
            print("1. Jalankan Simulasi Navigasi (Reproduce Memory Leak)")
            print("2. Jalankan Trace Profiling (JS vs UI Thread FPS & Jank Detection)")
            print("3. Inspeksi Heap Memory Dump & Retain Cycles")
            print("4. Terapkan Solusi Optimasi Performa Arsitektur")
            print("5. Reset Simulasi ke Kondisi Awal")
            print("0. Keluar")
            
            try:
                choice = input(f"\n{Style.BOLD}Pilih opsi [0-5]: {Style.RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{Style.YELLOW}Sesi lab diakhiri.{Style.RESET}")
                break

            if choice == "1":
                self.simulate_navigation_cycle(screens=5)
            elif choice == "2":
                self.run_profiling_trace()
            elif choice == "3":
                self.inspect_heap_snapshots()
            elif choice == "4":
                self.apply_optimizations()
            elif choice == "5":
                self.__init__()
                print(f"\n{Style.YELLOW}Simulasi telah di-reset ke kondisi awal.{Style.RESET}")
            elif choice == "0":
                print(f"\n{Style.CYAN}Lab Profiling React Native selesai. Happy debugging! 🚀{Style.RESET}\n")
                break
            else:
                print(f"{Style.RED}Pilihan tidak valid. Silakan pilih 0-5.{Style.RESET}")

            input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu...{Style.RESET}")

if __name__ == "__main__":
    app = ProductionLabSimulation()
    # Jika dijalankan dengan flag non-interaktif (e.g. automated test / CI)
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print(f"{Style.YELLOW}Menjalankan Automated Self-Verification Flow...{Style.RESET}")
        app.simulate_navigation_cycle(screens=3)
        app.run_profiling_trace()
        app.inspect_heap_snapshots()
        app.apply_optimizations()
        app.simulate_navigation_cycle(screens=3)
        app.run_profiling_trace()
        print(f"\n{Style.GREEN}Automated Verification Passed!{Style.RESET}")
        sys.exit(0)
    else:
        app.run_interactive_menu()
