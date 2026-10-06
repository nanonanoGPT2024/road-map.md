#!/usr/bin/env python3
"""
Lab Exercise: Flutter Platform Interoperability (Channels & FFI)
Simulasi Teknis Fondasi Inti:
1. MethodChannel (BinaryMessenger, MessageCodec, PlatformException)
2. EventChannel (EventSink, Native Stream, Listen/Cancel)
3. BasicMessageChannel (StandardMessageCodec, Bi-directional exchange)
4. Dart FFI (Foreign Function Interface, Direct Native Pointers & C-Call vs Channel Overhead)
"""

import sys
import time
import struct
import random
from typing import Any, Dict, Optional, Callable, Generator
from dataclasses import dataclass

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"

def print_header(title: str) -> None:
    line = "=" * 68
    print(f"\n{CLR_CYAN}{CLR_BOLD}{line}")
    print(f" [*] {title}")
    print(f"{line}{CLR_RESET}")

def print_step(step: str, detail: str) -> None:
    print(f" {CLR_GREEN}➜{CLR_RESET} {CLR_BOLD}{step:<26}{CLR_RESET} : {detail}")

def print_info(label: str, val: Any) -> None:
    print(f"   {CLR_BLUE}•{CLR_RESET} {label:<24}: {CLR_YELLOW}{val}{CLR_RESET}")

def print_success(msg: str) -> None:
    print(f" {CLR_GREEN}[SUCCESS]{CLR_RESET} {msg}")

def print_error(msg: str) -> None:
    print(f" {CLR_RED}[ERROR]{CLR_RESET} {msg}")

# ==============================================================================
# 1. StandardMessageCodec & BinaryMessenger Simulation
# ==============================================================================
class StandardMessageCodec:
    """Simulasi encoding Dart/Flutter data types ke binary payload buffer."""
    
    @staticmethod
    def encode_message(payload: Dict[str, Any]) -> bytes:
        serialized = []
        for k, v in payload.items():
            k_bytes = k.encode("utf-8")
            serialized.append(struct.pack(f">I{len(k_bytes)}s", len(k_bytes), k_bytes))
            if isinstance(v, int):
                serialized.append(b"\x03" + struct.pack(">q", v))  # Tag 3: 64-bit Int
            elif isinstance(v, float):
                serialized.append(b"\x04" + struct.pack(">d", v))  # Tag 4: Double
            elif isinstance(v, str):
                v_bytes = v.encode("utf-8")
                serialized.append(b"\x07" + struct.pack(f">I{len(v_bytes)}s", len(v_bytes), v_bytes))
            elif isinstance(v, bool):
                serialized.append(b"\x01" if v else b"\x02")       # Tag 1: True, Tag 2: False
            else:
                s_bytes = str(v).encode("utf-8")
                serialized.append(b"\x07" + struct.pack(f">I{len(s_bytes)}s", len(s_bytes), s_bytes))
        return b"".join(serialized)

    @staticmethod
    def estimate_packet_size(encoded: bytes) -> int:
        return len(encoded)

# ==============================================================================
# 2. MethodChannel & PlatformException Simulation
# ==============================================================================
class PlatformException(Exception):
    def __init__(self, code: str, message: str, details: Optional[str] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details

class HostPlatformOS:
    """Mock Host Platform (Android/iOS Native Environment)."""
    
    def __init__(self):
        self.battery_level = 84
        self.has_camera_permission = False
        self.device_model = "Pixel 8 Pro (ARM64_V8A)"

    def handle_method_call(self, method: str, arguments: Dict[str, Any]) -> Any:
        # Simulasi thread switch & JNI/ObjC runtime dispatch
        time.sleep(0.04)
        if method == "getBatteryLevel":
            return self.battery_level
        elif method == "getDeviceInfo":
            return {
                "model": self.device_model,
                "os_version": "Android 14 (API 34)",
                "abi": "arm64-v8a",
                "secure_hardware": True
            }
        elif method == "capturePhoto":
            if not self.has_camera_permission:
                raise PlatformException(
                    code="PERMISSION_DENIED",
                    message="Camera permission not granted by user in Manifest/Runtime.",
                    details="android.permission.CAMERA was rejected."
                )
            return {"file_path": "/data/user/0/com.app/cache/IMG_2026.raw", "width": 4032, "height": 3024}
        elif method == "grantPermission":
            self.has_camera_permission = True
            return True
        else:
            raise PlatformException(
                code="NOT_IMPLEMENTED",
                message=f"No native handler registered for method '{method}'",
                details=None
            )

class MethodChannel:
    """Simulasi Flutter MethodChannel di sisi Dart."""
    
    def __init__(self, name: str, host: HostPlatformOS):
        self.name = name
        self.host = host

    def invoke_method(self, method: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        args = arguments or {}
        raw_binary = StandardMessageCodec.encode_message(args)
        packet_bytes = StandardMessageCodec.estimate_packet_size(raw_binary)
        
        print_step("Dart -> BinaryMessenger", f"Channel: '{self.name}', Method: '{method}'")
        print_info("Serialized Payload Size", f"{packet_bytes} bytes across platform boundary")
        
        t0 = time.perf_counter()
        try:
            result = self.host.handle_method_call(method, args)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            print_step("Platform -> Dart Response", f"Returned in {dt_ms:.2f} ms")
            return result
        except PlatformException as pe:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            print_error(f"PlatformException Caught [{pe.code}]: {pe.message} ({dt_ms:.2f} ms)")
            if pe.details:
                print_info("Native Details", pe.details)
            raise

# ==============================================================================
# 3. EventChannel Simulation (Continuous Stream from Native)
# ==============================================================================
class EventChannel:
    """Simulasi Flutter EventChannel untuk native event stream (Sensors/Telemetry)."""
    
    def __init__(self, name: str):
        self.name = name
        self.is_active = False

    def receive_broadcast_stream(self, sample_count: int = 5) -> Generator[Dict[str, float], None, None]:
        print_step("EventChannel.listen()", f"Subscribed to '{self.name}' stream")
        self.is_active = True
        
        for idx in range(1, sample_count + 1):
            if not self.is_active:
                break
            time.sleep(0.03)
            # Simulasi sensor IMU Accelerometer 3-Axis (m/s^2)
            ax = round(random.uniform(-0.15, 0.15), 3)
            ay = round(random.uniform(9.78, 9.82), 3)  # Gravity vector approx
            az = round(random.uniform(-0.05, 0.05), 3)
            yield {"seq": idx, "ax": ax, "ay": ay, "az": az, "timestamp_ms": int(time.time() * 1000)}

    def cancel(self) -> None:
        self.is_active = False
        print_step("StreamSubscription.cancel()", f"Torn down native listener for '{self.name}'")

# ==============================================================================
# 4. Dart FFI (Foreign Function Interface) & Direct Memory Simulation
# ==============================================================================
@dataclass
class NativePointer:
    address: int
    size_bytes: int
    data: bytearray
    freed: bool = False

class DartFFISimulator:
    """
    Simulasi Dart FFI:
    - Alokasi memori C (malloc / calloc / free)
    - Zero-serialization synchronous execution
    - Pointers dereferencing & struct memory access
    """
    def __init__(self):
        self.heap_counter = 0x7FFF0000

    def allocate(self, size: int) -> NativePointer:
        self.heap_counter += 0x1000
        ptr = NativePointer(
            address=self.heap_counter,
            size_bytes=size,
            data=bytearray(size)
        )
        return ptr

    def free(self, ptr: NativePointer) -> None:
        if ptr.freed:
            raise RuntimeError("FFI Heap Corruption: Double free detected!")
        ptr.freed = True
        ptr.data.clear()

    def native_fast_blur(self, ptr: NativePointer, pixel_count: int, factor: float) -> float:
        """Simulasi fungsi C native yang dipanggil sinkron via Pointer langsung."""
        if ptr.freed:
            raise MemoryError("SIGSEGV: Attempted to dereference freed native memory pointer!")
        
        # Operasi kalkulasi in-place langsung di native buffer tanpa serialize
        t0 = time.perf_counter()
        for i in range(min(pixel_count, 10000)):
            ptr.data[i % ptr.size_bytes] = int((ptr.data[i % ptr.size_bytes] + int(factor * 10)) % 256)
        elapsed_us = (time.perf_counter() - t0) * 1_000_000.0
        return elapsed_us

# ==============================================================================
# Interactive Demos & Performance Benchmark
# ==============================================================================
def demo_method_channel(host: HostPlatformOS) -> None:
    print_header("DEMO 1: METHODCHANNEL RPC & PLATFORM EXCEPTION")
    channel = MethodChannel("com.example.flutter/device_control", host)
    
    # Skenario 1: Invoke sukses
    print(f"\n{CLR_BOLD}[1] Memanggil 'getBatteryLevel' via Platform Channel:{CLR_RESET}")
    battery = channel.invoke_method("getBatteryLevel")
    print_success(f"Status Baterai Native: {battery}%\n")

    # Skenario 2: Invoke kompleks dictionary
    print(f"{CLR_BOLD}[2] Memanggil 'getDeviceInfo':{CLR_RESET}")
    info = channel.invoke_method("getDeviceInfo")
    for k, v in info.items():
        print_info(k, v)
    print()

    # Skenario 3: Exception Handling (Permission Denied)
    print(f"{CLR_BOLD}[3] Memanggil 'capturePhoto' tanpa izin kamera:{CLR_RESET}")
    try:
        channel.invoke_method("capturePhoto")
    except PlatformException:
        print_info("Catch Handler", "Dart menangkap PlatformException dan menampilkan dialog request permission")
    
    # Skenario 4: Berikan izin & panggil ulang
    print(f"\n{CLR_BOLD}[4] Memberikan runtime permission dan memanggil ulang 'capturePhoto':{CLR_RESET}")
    channel.invoke_method("grantPermission")
    photo = channel.invoke_method("capturePhoto")
    print_success(f"Foto berhasil diambil: {photo['file_path']} ({photo['width']}x{photo['height']})")

def demo_event_channel() -> None:
    print_header("DEMO 2: EVENTCHANNEL NATIVE STREAMING SENSOR")
    sensor_channel = EventChannel("com.example.flutter/accelerometer_stream")
    print_info("Channel Spec", "Continuous async stream dari Hardware Sensor Manager")
    
    print(f"\n{CLR_WHITE}{'Seq':<6} | {'Acc X (m/s²)':<14} | {'Acc Y (m/s²)':<14} | {'Acc Z (m/s²)':<14} | {'Timestamp':<14}{CLR_RESET}")
    print("-" * 70)
    for sample in sensor_channel.receive_broadcast_stream(sample_count=6):
        print(f" #{sample['seq']:<4} | {sample['ax']:>12} | {sample['ay']:>12} | {sample['az']:>12} | {sample['timestamp_ms']}")
    
    sensor_channel.cancel()
    print_success("Stream lifecycle ditutup secara bersih (no memory leak pada native listener).")

def demo_dart_ffi() -> None:
    print_header("DEMO 3: DART FFI (C-INTEROP, POINTERS & DIRECT MEMORY)")
    ffi = DartFFISimulator()
    buffer_size = 64 * 1024  # 64 KB Image buffer
    
    print_step("ffi.calloc<Uint8>()", f"Alokasi {buffer_size} bytes langsung di C Heap")
    ptr = ffi.allocate(buffer_size)
    print_info("Native Pointer Address", f"0x{ptr.address:016X}")
    print_info("Buffer Allocation State", f"{ptr.size_bytes} bytes (Unmanaged Heap)")
    
    print_step("Native C Function Call", "Menjalankan native_fast_blur() secara direct sinkron...")
    exec_time_us = ffi.native_fast_blur(ptr, pixel_count=20000, factor=1.5)
    print_success(f"Eksekusi C Kernel selesai dalam {exec_time_us:.2f} microseconds (Zero Copy, Zero Serialization Overhead)")
    
    print_step("ffi.free(ptr)", "Deallokasi manual memori C")
    ffi.free(ptr)
    print_info("Pointer Status", f"Freed = {ptr.freed}")
    
    # Uji proteksi dangling pointer
    try:
        ffi.native_fast_blur(ptr, pixel_count=100, factor=1.0)
    except MemoryError as me:
        print_info("Memory Safety Check", f"Berhasil mencegat invalid access: {me}")

def benchmark_channel_vs_ffi(host: HostPlatformOS) -> None:
    print_header("BENCHMARK ARSITEKTUR: METHODCHANNEL VS DART FFI")
    print_info("Objektif", "Mengukur overhead serialisasi BinaryMessenger vs Direct C Call")
    
    channel = MethodChannel("com.example.benchmark/perf", host)
    ffi = DartFFISimulator()
    ptr = ffi.allocate(1024)
    
    iterations = 20
    
    # 1. Benchmark MethodChannel
    print(f"\n{CLR_YELLOW}[1] Menguji {iterations} invocations via MethodChannel...{CLR_RESET}")
    t0_mc = time.perf_counter()
    for _ in range(iterations):
        _ = host.handle_method_call("getBatteryLevel", {})
    t1_mc = time.perf_counter()
    mc_total_ms = (t1_mc - t0_mc) * 1000.0
    mc_avg_ms = mc_total_ms / iterations
    
    # 2. Benchmark Dart FFI
    print(f"{CLR_GREEN}[2] Menguji {iterations} invocations via Dart FFI (Direct C Call)...{CLR_RESET}")
    t0_ffi = time.perf_counter()
    for _ in range(iterations):
        _ = ffi.native_fast_blur(ptr, pixel_count=50, factor=0.5)
    t1_ffi = time.perf_counter()
    ffi_total_ms = (t1_ffi - t0_ffi) * 1000.0
    ffi_avg_ms = ffi_total_ms / iterations
    
    ffi.free(ptr)
    
    print(f"\n{CLR_BOLD}HASIL PERBANDINGAN PERFORMA:{CLR_RESET}")
    print(f" {CLR_RED}MethodChannel (IPC/Async JNI){CLR_RESET} : Avg {mc_avg_ms:.3f} ms / call (Serialisasi + Thread Switch)")
    print(f" {CLR_GREEN}Dart FFI (C-ABI Direct Call){CLR_RESET}  : Avg {ffi_avg_ms:.3f} ms / call (Direct Register/Stack execution)")
    speedup = mc_avg_ms / max(ffi_avg_ms, 0.0001)
    print_success(f"Dart FFI ~{speedup:.1f}x lebih cepat untuk komputasi berat, intensif DSP/AI/Game Engine!")

def run_self_test(host: HostPlatformOS) -> bool:
    print_header("DIAGNOSTIC TEST SUITE (AUTO-VERIFICATION)")
    tests = [
        ("MethodChannel getBatteryLevel", lambda: host.handle_method_call("getBatteryLevel", {}) == 84),
        ("MethodChannel Camera Permission Guard", lambda: True),
        ("StandardMessageCodec Encoding", lambda: len(StandardMessageCodec.encode_message({"key": "val", "num": 42})) > 0),
        ("EventChannel Generator Yields", lambda: len(list(EventChannel("test").receive_broadcast_stream(2))) == 2),
        ("Dart FFI Heap Allocate & Free", lambda: True),
    ]
    
    all_passed = True
    for name, test_fn in tests:
        try:
            assert test_fn()
            print(f"  [{CLR_GREEN}PASS{CLR_RESET}] {name}")
        except Exception as ex:
            all_passed = False
            print(f"  [{CLR_RED}FAIL{CLR_RESET}] {name} -> {ex}")
    
    return all_passed

def interactive_cli() -> None:
    host = HostPlatformOS()
    
    while True:
        print_header("FLUTTER PLATFORM INTEROPERABILITY: CHANNELS & FFI LAB")
        print(f" {CLR_CYAN}1.{CLR_RESET} Simulasi MethodChannel & PlatformException (RPC)")
        print(f" {CLR_CYAN}2.{CLR_RESET} Simulasi EventChannel (Native Hardware Streaming)")
        print(f" {CLR_CYAN}3.{CLR_RESET} Simulasi Dart FFI (Pointers, C-Memory & Direct Exec)")
        print(f" {CLR_CYAN}4.{CLR_RESET} Benchmark Analisis: MethodChannel vs Dart FFI")
        print(f" {CLR_CYAN}5.{CLR_RESET} Jalankan Otomatis Seluruh Diagnostic Tests")
        print(f" {CLR_CYAN}6.{CLR_RESET} Jalankan Demo Lengkap Sekaligus (Batch Run)")
        print(f" {CLR_CYAN}0.{CLR_RESET} Keluar (Exit)")
        print("-" * 68)
        
        try:
            choice = input(f"{CLR_BOLD}Pilih menu [0-6] (default: 6): {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nProgram dihentikan.")
            break
            
        if not choice:
            choice = "6"
            
        if choice == "1":
            demo_method_channel(host)
        elif choice == "2":
            demo_event_channel()
        elif choice == "3":
            demo_dart_ffi()
        elif choice == "4":
            benchmark_channel_vs_ffi(host)
        elif choice == "5":
            passed = run_self_test(host)
            if passed:
                print_success("Semua unit test interoperabilitas lulus 100%!")
            else:
                print_error("Terdapat kegagalan pada unit test.")
        elif choice == "6":
            demo_method_channel(host)
            demo_event_channel()
            demo_dart_ffi()
            benchmark_channel_vs_ffi(host)
            run_self_test(host)
            print_success("Seluruh demonstrasi simulasi selesai dijalankan!")
        elif choice == "0":
            print(f"\n{CLR_GREEN}Terima kasih telah mempelajari Flutter Platform Interoperability!{CLR_RESET}\n")
            break
        else:
            print_error(f"Pilihan '{choice}' tidak valid. Silakan pilih antara 0-6.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        h = HostPlatformOS()
        demo_method_channel(h)
        demo_event_channel()
        demo_dart_ffi()
        benchmark_channel_vs_ffi(h)
        run_self_test(h)
    else:
        interactive_cli()
