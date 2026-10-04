#!/usr/bin/env python3
"""
Lab Hands-on: Flutter Platform Interoperability Deep Dive
Chapter 08: Platform Channels vs. Dart FFI (Foreign Function Interface)

This lab simulates and benchmarks the architectural mechanics of Flutter's two
primary platform interoperability mechanisms:
 1. Platform Channels (BinaryMessenger, StandardMessageCodec serialization,
    and thread context-switching overhead across the platform bridge).
 2. Dart FFI (Direct C-memory pointers, zero-copy mutations, synchronous
    native execution via ctypes).
"""

import sys
import time
import struct
import ctypes
import threading
import queue
from typing import List, Tuple, Dict, Any

# --- Terminal ANSI Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"


# ============================================================================
# 1. PLATFORM CHANNEL SIMULATION (StandardMessageCodec + Thread Dispatch)
# ============================================================================

class BinaryMessenger:
    """
    Simulates Flutter Engine's BinaryMessenger.
    Handles message dispatch between Flutter UI Thread and Host Platform Thread
    over asynchronous thread queues.
    """
    def __init__(self):
        self._host_queue: queue.Queue = queue.Queue()
        self._reply_queue: queue.Queue = queue.Queue()
        self._running = True
        self._worker = threading.Thread(target=self._platform_event_loop, daemon=True)
        self._worker.start()

    def _platform_event_loop(self):
        """Simulates native Android Main Looper / iOS GCD dispatch queue."""
        while self._running:
            try:
                task = self._host_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            channel_name, binary_payload, reply_id = task
            # Native handler execution
            response_payload = self._handle_platform_call(channel_name, binary_payload)
            self._reply_queue.put((reply_id, response_payload))
            self._host_queue.task_done()

    def _handle_platform_call(self, channel: str, payload: bytes) -> bytes:
        """Native platform logic: Deserializes, processes, and re-encodes."""
        if channel == "com.flutter.vector/transform":
            # Unpack binary format: Count (I), then repeating triplets of floats (fff)
            count = struct.unpack_from("<I", payload, 0)[0]
            offset = 4
            result_floats = []
            scale_factor = 2.5

            for _ in range(count):
                x, y, z = struct.unpack_from("<fff", payload, offset)
                offset += 12
                # Vector scaling & norm offset
                result_floats.extend((x * scale_factor, y * scale_factor, z * scale_factor))

            # Re-serialize result back to platform bridge format
            fmt = f"<I{len(result_floats)}f"
            return struct.pack(fmt, count, *result_floats)
        return b""

    def send_and_await(self, channel: str, payload: bytes) -> bytes:
        """Asynchronously dispatches to native thread and awaits reply."""
        reply_id = time.time_ns()
        self._host_queue.put((channel, payload, reply_id))
        
        # Await reply (simulating Dart async Future resolution)
        while True:
            r_id, result = self._reply_queue.get()
            if r_id == reply_id:
                return result


class MethodChannel:
    """
    Simulates high-level Flutter MethodChannel wrapping binary encoding/decoding.
    """
    def __init__(self, name: str, messenger: BinaryMessenger):
        self.name = name
        self.messenger = messenger

    def invoke_method(self, method: str, vectors: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        # 1. Serialization (Dart isolate encodes to binary standard format)
        count = len(vectors)
        flat_coords = [coord for vec in vectors for coord in vec]
        wire_format = struct.pack(f"<I{len(flat_coords)}f", count, *flat_coords)

        # 2. Bridge crossing via BinaryMessenger
        response_bytes = self.messenger.send_and_await(self.name, wire_format)

        # 3. Deserialization (Engine decodes binary response back to Dart types)
        res_count = struct.unpack_from("<I", response_bytes, 0)[0]
        unpacked_floats = struct.unpack_from(f"<{res_count * 3}f", response_bytes, 4)

        result = []
        for i in range(0, len(unpacked_floats), 3):
            result.append((unpacked_floats[i], unpacked_floats[i+1], unpacked_floats[i+2]))
        return result


# ============================================================================
# 2. DART FFI SIMULATION (Foreign Function Interface / Direct Memory Pointer)
# ============================================================================

class NativeVector3(ctypes.Structure):
    """C-compatible struct mirroring memory layout of native C library."""
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float)
    ]


class DartFFIEngine:
    """
    Simulates Dart FFI using direct ctypes pointers.
    Allows zero-copy synchronous manipulation of native heap allocations.
    """
    @staticmethod
    def transform_in_place(ptr: ctypes.POINTER(NativeVector3), count: int, scale: float):
        """Direct native memory transformation without serialization or thread hop."""
        for i in range(count):
            vec = ptr[i]
            vec.x *= scale
            vec.y *= scale
            vec.z *= scale


# ============================================================================
# 3. BENCHMARK & COMPARATIVE EVALUATION
# ============================================================================

def run_platform_interop_lab():
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} FLUTTER ARCHITECTURE LAB: PLATFORM CHANNELS vs. DART FFI DEEP DIVE  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}\n")

    DATA_SIZES = [1000, 10000, 50000]
    SCALE_FACTOR = 2.5
    messenger = BinaryMessenger()
    method_channel = MethodChannel("com.flutter.vector/transform", messenger)

    print(f"{CLR_BOLD}Benchmark Scenario:{CLR_RESET} Transforming 3D Vector Arrays (Scale x2.5)")
    print(f"Comparing Serialization/Bridge IPC vs. Direct Pointer Native Access.\n")

    for size in DATA_SIZES:
        print(f"{CLR_YELLOW}----------------------------------------------------------------------{CLR_RESET}")
        print(f"Processing Batch Size: {CLR_BOLD}{size:,} Vector3 entries{CLR_RESET}")
        print(f"{CLR_YELLOW}----------------------------------------------------------------------{CLR_RESET}")

        # Seed test data
        test_vectors = [(float(i), float(i + 1), float(i + 2)) for i in range(size)]

        # --- A. MethodChannel Evaluation ---
        t0 = time.perf_counter()
        channel_result = method_channel.invoke_method("transform", test_vectors)
        t_channel = (time.perf_counter() - t0) * 1000.0  # ms

        # Payload size telemetry
        # 4 bytes count + size * 3 * 4 bytes floats
        raw_wire_size_kb = (4 + size * 12) / 1024.0

        # --- B. Dart FFI Evaluation ---
        # Allocate native contiguous block using ctypes
        NativeVectorArray = NativeVector3 * size
        native_buffer = NativeVectorArray()
        for idx, (x, y, z) in enumerate(test_vectors):
            native_buffer[idx].x = x
            native_buffer[idx].y = y
            native_buffer[idx].z = z

        raw_pointer = ctypes.cast(native_buffer, ctypes.POINTER(NativeVector3))

        t0 = time.perf_counter()
        DartFFIEngine.transform_in_place(raw_pointer, size, SCALE_FACTOR)
        t_ffi = (time.perf_counter() - t0) * 1000.0  # ms

        # Verification: Validate equivalence of both computations
        sample_channel = channel_result[0]
        sample_ffi = (raw_pointer[0].x, raw_pointer[0].y, raw_pointer[0].z)
        assert abs(sample_channel[0] - sample_ffi[0]) < 1e-4, "Data mismatch between Channel and FFI!"

        # Speedup Calculation
        speedup = (t_channel / t_ffi) if t_ffi > 0 else 0

        # Output Telemetry
        print(f"  [Platform Channel] Execution Time: {CLR_RED}{t_channel:8.3f} ms{CLR_RESET} | Wire Copy: {raw_wire_size_kb:8.1f} KB")
        print(f"  [Dart FFI Engine ] Execution Time: {CLR_GREEN}{t_ffi:8.3f} ms{CLR_RESET} | Zero-Copy Ptr (In-Place)")
        print(f"  {CLR_BOLD}Performance Delta:{CLR_RESET} FFI is {CLR_MAGENTA}{CLR_BOLD}{speedup:5.1f}x faster{CLR_RESET} than MethodChannel\n")

    # Stop background thread
    messenger._running = False

    # Architectural Summary
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD} ARCHITECTURAL SUMMARY & SELECTION CRITERIA{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print("""
1. Platform Channels (MethodChannel/BasicMessageChannel):
   - Overhead : Requires binary serialization (StandardMessageCodec) and asynchronous
                thread queue hops across Dart UI thread and Platform Host thread.
   - Use Cases: Battery status, GPS, camera controls, native UI integrations,
                standard system APIs where call frequency is low (< 60Hz).

2. Dart FFI (Foreign Function Interface):
   - Overhead : Synchronous direct memory pointer dereferencing with ZERO wire
                serialization overhead. Runs directly on the calling isolate.
   - Use Cases: Real-time audio DSP, game engines, SQLite, image/video manipulation,
                heavy cryptography, computer vision (OpenCV).
""")


if __name__ == "__main__":
    run_platform_interop_lab()