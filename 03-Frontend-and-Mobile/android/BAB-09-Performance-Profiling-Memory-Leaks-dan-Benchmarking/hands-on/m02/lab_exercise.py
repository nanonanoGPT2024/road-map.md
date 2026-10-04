#!/usr/bin/env python3
"""
Lab Hands-on: Android Performance Profiling, Memory Leaks & Benchmarking
Modul: Deep Dive Memory Leak Detection (LeakCanary Simulation) & Choreographer Jank Profiling

Deskripsi:
Script ini mensimulasikan lingkungan runtime Android untuk mendemonstrasikan:
1. Retained Context Memory Leaks: Perbedaan antara strong reference (static leak)
   dan weak reference pada lifecycle Activity.
2. Leak Detection Engine: Mengimplementasikan mekanisme LeakCanary menggunakan
   WeakReference dan trigger Garbage Collection terarah.
3. Choreographer VSYNC Benchmarking: Mengukur Frame Time, mendeteksi Jank Frames (>16.6ms),
   dan Frozen Frames (>700ms) berdasarkan metrik Android Vitals.
"""

import sys
import time
import gc
import weakref
import threading
import random
from collections import deque

# ANSI Color Codes untuk Visualisasi Profiling
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_GRAY = "\033[90m"


# =====================================================================
# 1. SIMULASI ANDROID ACTIVITY LIFECYCLE & MEMORY LEAK
# =====================================================================

class Activity:
    """Representasi Android Activity dengan alokasi heap simulasi."""
    def __init__(self, name: str, alloc_mb: int = 4):
        self.name = name
        self.is_destroyed = False
        # Simulasi alokasi Bitmap / View Hierarchy memory
        self.heap_allocation = bytearray(alloc_mb * 1024 * 1024)

    def on_destroy(self):
        """Dipanggil oleh Android OS saat konfigurasi berubah atau finish()."""
        self.is_destroyed = True


class SingletonListenerManager:
    """
    Simulasi static singleton (misal: LocationManager / NetworkMonitor)
    yang kerap menjadi sumber leak jika menyimpan context secara tidak tepat.
    """
    def __init__(self):
        self._leaky_listeners = []
        self._safe_listeners = []

    def register_leaky(self, listener):
        """Anti-pattern: Menyimpan Strong Reference ke Activity Context."""
        self._leaky_listeners.append(listener)

    def register_safe(self, listener):
        """Best-practice: Menyimpan WeakReference agar GC dapat mereklamasi."""
        self._safe_listeners.append(weakref.ref(listener))


class MockLeakCanary:
    """
    Simulasi LeakCanary: Mengawasi objek yang telah di-destroy.
    Jika objek masih bertahan setelah GC dipaksa berjalan, laporkan retain trace.
    """
    def __init__(self):
        self.watched_objects = []

    def watch(self, obj: Activity, description: str):
        # Menyimpan weak reference ke target untuk memverifikasi deallokasi
        tracker = weakref.ref(obj)
        self.watched_objects.append((tracker, description, obj.name))

    def evaluate_leaks(self):
        print(f"\n{CLR_BOLD}{CLR_BLUE}[LeakCanary Engine] Memicu GC & Menganalisis Retained Objects...{CLR_RESET}")
        # Simulasi Garbage Collection eksplisit seperti LeakCanary trigger
        gc.collect()
        time.sleep(0.1)

        detected_leaks = 0
        for tracker, desc, name in self.watched_objects:
            instance = tracker()
            if instance is not None and instance.is_destroyed:
                detected_leaks += 1
                heap_mb = len(instance.heap_allocation) / (1024 * 1024)
                print(f"{CLR_RED}✖ LEAK DETECTED: {name}{CLR_RESET}")
                print(f"  {CLR_GRAY}└─ Root Trace:{CLR_RESET} SingletonListenerManager._leaky_listeners")
                print(f"  {CLR_GRAY}└─ Retained Heap Size:{CLR_RESET} ~{heap_mb:.2f} MB")
                print(f"  {CLR_GRAY}└─ Penyebab:{CLR_RESET} {desc}\n")
            else:
                print(f"{CLR_GREEN}✔ NO LEAK: {name} berhasil dibersihkan dari Native/Dalvik Heap.{CLR_RESET}")
        
        return detected_leaks


# =====================================================================
# 2. CHOREOGRAPHER & JANK BENCHMARKING ENGINE
# =====================================================================

class ChoreographerBenchmark:
    """
    Simulasi Android Choreographer untuk benchmarking frame rendering.
    Standar: 60 FPS -> Target VSYNC window: ~16.66 ms per frame.
    Jank Frame: > 16.66 ms.
    Frozen Frame: > 700 ms (Android Vitals Critical Alert).
    """
    TARGET_FRAME_TIME_MS = 16.66

    def __init__(self, frame_count: int = 60):
        self.frame_count = frame_count
        self.frame_durations = []

    def _simulate_ui_frame(self, simulate_heavy_ui: bool) -> float:
        start_time = time.perf_counter()
        
        # Operasi layouting & draw normal
        time.sleep(0.010)  # Baseline rendering: 10ms

        if simulate_heavy_ui:
            # Simulasi Main-Thread Block (misal: JSON parsing/DB query di UI thread)
            dice = random.random()
            if dice > 0.90:
                time.sleep(0.080)  # Moderate Jank: +80ms
            elif dice > 0.98:
                time.sleep(0.720)  # Frozen Frame: +720ms
            elif dice > 0.70:
                time.sleep(0.012)  # Minor frame drop: +12ms

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return elapsed_ms

    def run_benchmark(self, scenario_name: str, simulate_heavy_ui: bool):
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== Menjalankan Benchmark UI: {scenario_name} ==={CLR_RESET}")
        self.frame_durations.clear()

        jank_frames = 0
        frozen_frames = 0

        for frame_idx in range(1, self.frame_count + 1):
            frame_time = self._simulate_ui_frame(simulate_heavy_ui)
            self.frame_durations.append(frame_time)

            if frame_time > 700.0:
                frozen_frames += 1
                status = f"{CLR_RED}[FROZEN FRAME]{CLR_RESET}"
            elif frame_time > self.TARGET_FRAME_TIME_MS:
                jank_frames += 1
                status = f"{CLR_YELLOW}[JANK]{CLR_RESET}"
            else:
                status = f"{CLR_GREEN}[OK]{CLR_RESET}"

            if frame_idx % 15 == 0 or "OK" not in status:
                print(f"  Frame #{frame_idx:02d}: {frame_time:6.2f} ms {status}")

        self._print_metrics(jank_frames, frozen_frames)

    def _print_metrics(self, janks: int, frozen: int):
        total = len(self.frame_durations)
        avg_time = sum(self.frame_durations) / total
        sorted_times = sorted(self.frame_durations)
        p95 = sorted_times[int(total * 0.95)]
        p99 = sorted_times[int(total * 0.99)]
        jank_pct = (janks / total) * 100

        print(f"\n{CLR_BOLD}--- Laporan Metrik Performa (Android Vitals) ---{CLR_RESET}")
        print(f"  Total Frames Evaluated : {total}")
        print(f"  Rata-rata Frame Time   : {avg_time:.2f} ms (Target: <=16.66 ms)")
        print(f"  P95 Frame Time         : {p95:.2f} ms")
        print(f"  P99 Frame Time         : {p99:.2f} ms")
        
        color_jank = CLR_RED if jank_pct > 15 else (CLR_YELLOW if jank_pct > 5 else CLR_GREEN)
        print(f"  Jank Frame Rate        : {color_jank}{jank_pct:.1f}% ({janks}/{total}){CLR_RESET}")
        
        if frozen > 0:
            print(f"  {CLR_RED}CRITICAL: {frozen} Frozen Frame(s) terdeteksi! Risiko ANR (Application Not Responding).{CLR_RESET}")
        else:
            print(f"  {CLR_GREEN}Frozen Frames          : 0 (Aman dari risiko ANR dasar){CLR_RESET}")


# =====================================================================
# 3. RUNNER & DEMONSTRASI INTEGRASI
# =====================================================================

def main():
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}  ANDROID PERFORMANCE & MEMORY LEAK PROFILING LAB    {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================{CLR_RESET}")

    # --- BAGIAN 1: Simulasi Memory Leak (Dalvik/ART Heap Profiling) ---
    manager = SingletonListenerManager()
    canary = MockLeakCanary()

    print(f"\n{CLR_BOLD}[1] Memulai Skenario Alokasi Lifecycle Activity...{CLR_RESET}")
    
    # Activity A: Leaked melalui Strong Reference
    act_a = Activity("DetailProductActivity", alloc_mb=12)
    manager.register_leaky(act_a)
    canary.watch(act_a, "Activity di-destroy tapi singleton mempertahankan hard-reference.")
    
    # Activity B: Aman menggunakan Weak Reference
    act_b = Activity("UserSettingActivity", alloc_mb=8)
    manager.register_safe(act_b)
    canary.watch(act_b, "Activity di-destroy dan didaftarkan via WeakReference.")

    print(f"  -> {act_a.name} & {act_b.name} dialokasikan pada Heap.")
    print("  -> Menjalankan transisi Lifecycle: on_destroy()...")
    
    act_a.on_destroy()
    act_b.on_destroy()

    # Dereferensikan pointer lokal simulasi stack frame keluar
    del act_a
    del act_b

    # Evaluasi status leak
    canary.evaluate_leaks()

    # --- BAGIAN 2: Benchmarking Frame Rendering & Jank Profiling ---
    choreographer = ChoreographerBenchmark(frame_count=45)

    # Skenario A: Main Thread terbebani (Unoptimized)
    choreographer.run_benchmark("UI Thread Blocking (I/O & Heavy Calculation di Main Thread)", simulate_heavy_ui=True)

    # Skenario B: Optimized Background Offloading (Coroutines / RxJava Worker)
    choreographer.run_benchmark("Offloaded Architecture (Background Work Dispatcher)", simulate_heavy_ui=False)

    print(f"\n{CLR_BOLD}{CLR_GREEN}Lab Selesai. Semua parameter profil performa berhasil dievaluasi.{CLR_RESET}")


if __name__ == "__main__":
    main()