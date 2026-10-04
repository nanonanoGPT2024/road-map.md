#!/usr/bin/env python3
"""
Lab: C# Metaprogramming Deep Dive - Reflection vs. Expression Trees vs. Roslyn Source Generators
Author: Lead System Programmer

Simulates the architectural evolution of metaprogramming in the .NET runtime:
1. Dynamic Runtime Reflection (System.Reflection - high dynamic dispatch overhead)
2. Cached Reflection / Compiled Expressions (System.Linq.Expressions - delegate emission)
3. Roslyn Source Generators (IIncrementalGenerator - zero-cost compile-time AST codegen)
"""

import time
import json
from typing import Dict, Any, List, Callable, Type


# ============================================================================
# ANSI Color Formatting Utilities
# ============================================================================
class ConsoleFormat:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    DIM = "\033[2m"


# ============================================================================
# Metadata Models (Simulating C# Attributes & Type System)
# ============================================================================
class JsonPropertyAttribute:
    """Simulates C# [JsonPropertyName(string name)]"""
    def __init__(self, property_name: str):
        self.property_name = property_name


class RangeAttribute:
    """Simulates C# [Range(int min, int max)]"""
    def __init__(self, min_val: int, max_val: int):
        self.min_val = min_val
        self.max_val = max_val


class UserPayload:
    """
    Target C# DTO:
    public class UserPayload {
        [JsonPropertyName("usr_id")] public int Id { get; set; }
        [JsonPropertyName("usr_name")] public string Username { get; set; }
        [JsonPropertyName("sec_level"), Range(1, 10)] public int SecurityLevel { get; set; }
    }
    """
    __metadata__ = {
        "id": [JsonPropertyAttribute("usr_id")],
        "username": [JsonPropertyAttribute("usr_name")],
        "security_level": [JsonPropertyAttribute("sec_level"), RangeAttribute(1, 10)]
    }

    def __init__(self, user_id: int, username: str, security_level: int):
        self.id = user_id
        self.username = username
        self.security_level = security_level


# ============================================================================
# Engine 1: Pure Dynamic Reflection (Simulates System.Reflection runtime scans)
# ============================================================================
class DynamicReflectionSerializer:
    """
    Performs full runtime type inspection and attribute discovery on every
    serialization invocation. High memory allocation and member resolution cost.
    """
    @staticmethod
    def serialize(obj: Any) -> str:
        cls = obj.__class__
        meta = getattr(cls, "__metadata__", {})
        payload = {}

        # Scan attributes and properties on each invocation
        for prop_name, attributes in meta.items():
            val = getattr(obj, prop_name)
            target_key = prop_name

            for attr in attributes:
                if isinstance(attr, JsonPropertyAttribute):
                    target_key = attr.property_name
                elif isinstance(attr, RangeAttribute):
                    if not (attr.min_val <= val <= attr.max_val):
                        raise ValueError(f"Property {prop_name} out of bounds")

            payload[target_key] = val

        return json.dumps(payload, separators=(',', ':'))


# ============================================================================
# Engine 2: Compiled/Cached Expression Tree (Simulates System.Linq.Expressions)
# ============================================================================
class CompiledDelegateSerializer:
    """
    Simulates LINQ Expression Trees: Introspects metadata once, compiles
    dynamic property accessors and validators into closure delegates, then
    caches the execution plan per Type.
    """
    _type_cache: Dict[Type, List[Callable[[Any, Dict[str, Any]], None]]] = {}

    @classmethod
    def _compile_type_pipeline(cls, target_cls: Type):
        meta = getattr(target_cls, "__metadata__", {})
        pipeline: List[Callable[[Any, Dict[str, Any]], None]] = []

        for prop_name, attributes in meta.items():
            out_key = prop_name
            validators = []

            for attr in attributes:
                if isinstance(attr, JsonPropertyAttribute):
                    out_key = attr.property_name
                elif isinstance(attr, RangeAttribute):
                    min_v, max_v = attr.min_val, attr.max_val
                    validators.append(
                        lambda v, p=prop_name, low=min_v, high=max_v: 
                        (low <= v <= high) or (_ for _ in ()).throw(ValueError(f"{p} out of bounds"))
                    )

            # Build optimized closure for member extraction and validation
            def build_writer(k: str, p: str, v_list: list):
                return lambda instance, out_dict: (
                    [v(getattr(instance, p)) for v in v_list],
                    out_dict.__setitem__(k, getattr(instance, p))
                )

            pipeline.append(build_writer(out_key, prop_name, validators))

        cls._type_cache[target_cls] = pipeline

    @classmethod
    def serialize(cls, obj: Any) -> str:
        target_cls = obj.__class__
        if target_cls not in cls._type_cache:
            cls._compile_type_pipeline(target_cls)

        payload: Dict[str, Any] = {}
        for writer in cls._type_cache[target_cls]:
            writer(obj, payload)

        return json.dumps(payload, separators=(',', ':'))


# ============================================================================
# Engine 3: Roslyn Source Generator Simulation (Compile-Time Code Synthesis)
# ============================================================================
class RoslynGeneratorSimulator:
    """
    Simulates C# 9+ Roslyn Source Generators (IIncrementalGenerator):
    Inspects syntax and symbols at compilation, directly synthesizes unrolled
    assembly/IL-level routines. Zero runtime reflection, zero cache lookup overhead.
    """
    _synthesized_methods: Dict[Type, Callable[[Any], str]] = {}

    @classmethod
    def synthesize_code_ahead_of_time(cls, target_cls: Type):
        """
        Emulates Roslyn's SourceProductionContext.AddSource:
        Generates direct string template assembly avoiding dynamic inspection.
        """
        meta = getattr(target_cls, "__metadata__", {})
        code_lines = [
            f"def __generated_serializer(obj):",
            f"    # Direct unrolled access synthesized ahead-of-time"
        ]

        # Generate unrolled validation logic
        for prop_name, attributes in meta.items():
            for attr in attributes:
                if isinstance(attr, RangeAttribute):
                    code_lines.append(
                        f"    if not ({attr.min_val} <= obj.{prop_name} <= {attr.max_val}): "
                        f"raise ValueError('Out of range: {prop_name}')"
                    )

        # Generate zero-overhead direct JSON construction
        fmt_parts = []
        val_parts = []
        for prop_name, attributes in meta.items():
            key = prop_name
            for attr in attributes:
                if isinstance(attr, JsonPropertyAttribute):
                    key = attr.property_name
            fmt_parts.append(f'"{key}":%s')
            # Handle string formatting vs numeric formatting
            val_parts.append(f'(f\'"{{obj.{prop_name}}}\"' if isinstance(obj.{prop_name}, str) else str(obj.{prop_name}))')

        json_pattern = "{" + ",".join(fmt_parts) + "}"
        tuple_expr = "(" + ",".join(val_parts) + ",)"
        code_lines.append(f"    return '{json_pattern}' % {tuple_expr}")

        source_code = "\n".join(code_lines)
        local_scope: Dict[str, Any] = {}
        exec(source_code, {}, local_scope)
        cls._synthesized_methods[target_cls] = local_scope["__generated_serializer"]
        return source_code

    @classmethod
    def serialize(cls, obj: Any) -> str:
        # Direct static method call without any reflection/attribute query
        return cls._synthesized_methods[obj.__class__](obj)


# ============================================================================
# Benchmark Runner & Diagnostic Report
# ============================================================================
def run_benchmark():
    iterations = 50_000
    sample = UserPayload(101, "dev_architect", 5)

    print(f"{ConsoleFormat.BOLD}{ConsoleFormat.CYAN}"
          f"========================================================================\n"
          f" C# METAPROGRAMMING & ROSLYN SOURCE GENERATION BENCHMARK\n"
          f"========================================================================{ConsoleFormat.RESET}")

    # Step 1: Synthesize Roslyn Artifacts Ahead-Of-Time
    print(f"{ConsoleFormat.YELLOW}[Compilation Phase]{ConsoleFormat.RESET} Emitting Source Generated Code...")
    generated_code = RoslynGeneratorSimulator.synthesize_code_ahead_of_time(UserPayload)
    print(f"{ConsoleFormat.DIM}{generated_code}{ConsoleFormat.RESET}\n")

    # Step 2: Validate Output Parity Across All 3 Engines
    ref_out = DynamicReflectionSerializer.serialize(sample)
    del_out = CompiledDelegateSerializer.serialize(sample)
    gen_out = RoslynGeneratorSimulator.serialize(sample)

    assert ref_out == del_out == gen_out, (
        f"Data Parity Failure:\nRef: {ref_out}\nDel: {del_out}\nGen: {gen_out}"
    )
    print(f"{ConsoleFormat.GREEN}✔ Verification Passed:{ConsoleFormat.RESET} All engines produce bit-identical output:")
    print(f"  Result: {ConsoleFormat.BOLD}{gen_out}{ConsoleFormat.RESET}\n")

    # Step 3: Performance Profiling
    engines = [
        ("Dynamic Reflection (System.Reflection)", DynamicReflectionSerializer.serialize),
        ("Compiled Expressions (Expression<Func>)", CompiledDelegateSerializer.serialize),
        ("Roslyn Source Generator (AOT Synthesized)", RoslynGeneratorSimulator.serialize)
    ]

    timings = {}
    print(f"{ConsoleFormat.CYAN}[Execution Phase]{ConsoleFormat.RESET} Benchmarking {iterations:,} iterations per engine...")

    for name, serializer in engines:
        # Warmup
        for _ in range(500):
            serializer(sample)

        start = time.perf_counter_ns()
        for _ in range(iterations):
            serializer(sample)
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        timings[name] = elapsed_ms
        ops_per_sec = (iterations / elapsed_ms) * 1000
        print(f"  • {name:<42}: {elapsed_ms:>8.2f} ms ({ops_per_sec:,.0f} ops/sec)")

    # Step 4: Summary Analysis
    baseline = timings["Dynamic Reflection (System.Reflection)"]
    print(f"\n{ConsoleFormat.BOLD}Performance Summary & Speedup Relative to Runtime Reflection:{ConsoleFormat.RESET}")
    print("-" * 72)
    for name, elapsed in timings.items():
        ratio = baseline / elapsed
        color = ConsoleFormat.RED if ratio <= 1.0 else (ConsoleFormat.YELLOW if ratio < 3.0 else ConsoleFormat.GREEN)
        print(f"  {name:<42} | {color}{ratio:>6.2f}x speedup{ConsoleFormat.RESET}")
    print("-" * 72)

    print(f"\n{ConsoleFormat.MAGENTA}[Architectural Takeaway]{ConsoleFormat.RESET}")
    print("1. Reflection incurs heavy runtime costs via property table and custom attribute scans.")
    print("2. Expression compilation shifts resolution to warmup, trading startup time for execution speed.")
    print("3. Roslyn Source Generators eliminate both costs completely by shifting all metaprogramming")
    print("   to compile-time, delivering native zero-overhead code execution (ideal for AOT & mobile).")


if __name__ == "__main__":
    run_benchmark()
README.md
# hands-on-c-sharp

Lab Hands-on Berbasis Code-First: C#

Kumpulan lab praktis implementasi konsep-konsep C# (.NET) modern berbasis kode langsung dan runnable.

---

## Daftar Modul Lab

| No | Modul | Topik Utama | Script Lab |
|---|---|---|---|
| 01 | [Modul 01 - Memory Management](./01-memory-management/) | Span, Memory, ArrayPool, dan Unsafe Code | `01_span_memory_sim.py` |
| 02 | [Modul 02 - Async Internals](./02-async-internals/) | State Machine `async`/`await` & SynchronizationContext | `02_async_state_machine.py` |
| 03 | [Modul 03 - Concurrency](./03-concurrency/) | Threading, Channels, Dataflow & Lock-Free Synchronization | `03_channels_pipeline.py` |
| 04 | [Modul 04 - LINQ Internals](./04-linq-internals/) | Deferred Execution & Expression Tree Compiler | `04_linq_internals.py` |
| 05 | [Modul 05 - Modern Language Features](./05-modern-features/) | Pattern Matching, Records & Immutability | `05_pattern_matching_records.py` |
| 06 | [Modul 06 - Metaprogramming](./06-metaprogramming/) | Reflection vs Expression Trees vs Roslyn Source Generators | `06_metaprogramming_roslyn.py` |
| 07 | [Modul 07 - ASP.NET Core Internals](./07-aspnet-internals/) | Middleware Pipeline & Dependency Injection Engine | `07_aspnet_internals.py` |
| 08 | [Modul 08 - Performance & Native AOT](./08-performance-aot/) | Object Pooling, SIMD/Vectorization & Native AOT Profiling | `08_performance_aot.py` |

---

## Cara Menjalankan Lab

Seluruh script dirancang mandiri (*self-contained*) dan hanya membutuhkan **Python 3.8+** (standard library saja, tanpa dependensi pihak ketiga).

```bash
# Jalankan modul tertentu
python3 01-memory-management/01_span_memory_sim.py
python3 02-async-internals/02_async_state_machine.py
python3 03-concurrency/03_channels_pipeline.py
python3 04-linq-internals/04_linq_internals.py
python3 05-modern-features/05_pattern_matching_records.py
python3 06-metaprogramming/06_metaprogramming_roslyn.py
python3 07-aspnet-internals/07_aspnet_internals.py
python3 08-performance-aot/08_performance_aot.py
```
01-memory-management/01_span_memory_sim.py

    bench_data = b"POST /api/v1/telemetry HTTP/1.1\r\nX-Batch-Id: 98765\r\nContent-Length: 1024\r\n\r\nPayloadData"
    iterations = 20_000

    print(f"\n{BOLD}{CYAN}=== BENCHMARK: STRING SUBSTRING VS SLICED SPAN ({iterations} ITERATIONS) ==={RESET}")

    # Traditional Substring (Allocating)
    t0 = time.perf_counter()
    str_data = bench_data.decode("utf-8")
    for _ in range(iterations):
        # Emulate repeated headers parsing with substrings
        idx = str_data.find("\r\n\r\n")
        header_part = str_data[:idx]
        body_part = str_data[idx + 4:]
        _ = header_part.split("\r\n")
    dur_substr = time.perf_counter() - t0

    # Zero-Allocation Span Parser
    parser = ZeroAllocHttpParser()
    t0 = time.perf_counter()
    for _ in range(iterations):
        span = Span(bench_data)
        _ = parser.parse_request(span)
    dur_span = time.perf_counter() - t0

    print(f"Traditional Substring Allocations : {dur_substr * 1000:8.2f} ms")
    print(f"Span<T> Zero-Allocation Slices    : {dur_span * 1000:8.2f} ms")
    speedup = dur_substr / dur_span if dur_span > 0 else 1.0
    print(f"{GREEN}Efficiency Gain / Speedup Ratio   : {speedup:8.2f}x faster{RESET}")

    print(f"\n{BOLD}{CYAN}=== ALL LAB SCENARIOS COMPLETED SUCCESSFULLY ==={RESET}\n")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Lab: C# Memory Management Deep Dive
Simulating: Span<T>, Memory<T>, ArrayPool<T>, and Unsafe Buffer Pointers.
This script demonstrates zero-allocation slicing, heap vs stack-only semantics,
and array rent/return lifecycles without third-party dependencies.
"""

import sys
import time
from typing import Optional, List, Dict, Tuple

# Terminal ANSI color codes for structured output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"

class Span:
    """
    Simulates C# ref struct Span<T>.
    Key Characteristics:
    - Stack-only semantics (by convention/design in this simulation).
    - Holds an interior pointer/reference to a contiguous sequence of memory.
    - Slicing produces a new Span over the SAME underlying memory buffer without allocations.
    """
    def __init__(self, buffer: bytearray, start: int = 0, length: Optional[int] = None):
        if not isinstance(buffer, (bytearray, bytes, memoryview)):
            raise TypeError("Underlying buffer must be a contiguous byte-like sequence.")
        
        self._buffer = buffer
        self._start = start
        self._length = len(buffer) - start if length is None else length

        if self._start < 0 or self._length < 0 or (self._start + self._length) > len(buffer):
            raise IndexError("Span range exceeds underlying buffer bounds.")

    @property
    def length(self) -> int:
        return self._length

    def slice(self, start: int, length: Optional[int] = None) -> 'Span':
        """Zero-allocation sub-view calculation (O(1))."""
        new_len = self._length - start if length is None else length
        if start < 0 or new_len < 0 or (start + new_len) > self._length:
            raise IndexError("Slice extends beyond current Span bounds.")
        return Span(self._buffer, self._start + start, new_len)

    def to_bytes(self) -> bytes:
        return bytes(self._buffer[self._start : self._start + self._length])

    def __getitem__(self, idx: int) -> int:
        if idx < 0 or idx >= self._length:
            raise IndexError("Index out of Span range.")
        return self._buffer[self._start + idx]

    def __setitem__(self, idx: int, value: int):
        if idx < 0 or idx >= self._length:
            raise IndexError("Index out of Span range.")
        self._buffer[self._start + idx] = value

    def __repr__(self) -> str:
        return f"<Span offset={self._start} len={self._length} data={bytes(self._buffer[self._start:self._start+min(16, self._length)])}>"


class MemoryOwner:
    """Simulates C# IMemoryOwner<T> returned from an ArrayPool or native allocator."""
    def __init__(self, buffer: bytearray, pool: 'ArrayPool'):
        self._buffer = buffer
        self._pool = pool
        self._is_disposed = False

    @property
    def memory(self) -> 'Memory':
        if self._is_disposed:
            raise RuntimeError("Cannot access Memory on a disposed MemoryOwner.")
        return Memory(self._buffer)

    def dispose(self):
        """Returns the rented buffer back to the pool."""
        if not self._is_disposed:
            self._pool.return_buffer(self._buffer)
            self._is_disposed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()


class Memory:
    """
    Simulates C# Memory<T>.
    Unlike Span, Memory can survive on the managed heap, be passed across async/await boundaries,
    and be stored in class fields.
    """
    def __init__(self, buffer: bytearray, start: int = 0, length: Optional[int] = None):
        self._buffer = buffer
        self._start = start
        self._length = len(buffer) - start if length is None else length

    @property
    def span(self) -> Span:
        """Converts heap-allocated memory representation into a high-performance stack-like Span."""
        return Span(self._buffer, self._start, self._length)

    def slice(self, start: int, length: Optional[int] = None) -> 'Memory':
        new_len = self._length - start if length is None else length
        if start < 0 or new_len < 0 or (start + new_len) > self._length:
            raise IndexError("Slice extends beyond Memory bounds.")
        return Memory(self._buffer, self._start + start, new_len)


class ArrayPool:
    """
    Simulates C# System.Buffers.ArrayPool<T>.Shared.
    Reduces GC Gen 0/1/2 pressure by reusing allocated byte arrays across workers.
    """
    def __init__(self):
        # Power-of-two bucket tiers (e.g., 256, 512, 1024, 2048, 4096...)
        self._buckets: Dict[int, List[bytearray]] = {}
        self.total_allocations = 0
        self.rents = 0
        self.returns = 0

    def _get_bucket_size(self, min_size: int) -> int:
        size = 256
        while size < min_size:
            size <<= 1
        return size

    def rent(self, min_length: int) -> bytearray:
        """Rents a buffer from the bucket or allocates if empty."""
        bucket_size = self._get_bucket_size(min_length)
        self.rents += 1
        
        if bucket_size in self._buckets and self._buckets[bucket_size]:
            return self._buckets[bucket_size].pop()
        
        # Cold path: allocate new buffer
        self.total_allocations += 1
        return bytearray(bucket_size)

    def return_buffer(self, buffer: bytearray, clear_array: bool = True):
        """Returns the rented buffer to its corresponding bucket."""
        self.returns += 1
        capacity = len(buffer)
        
        if clear_array:
            for i in range(capacity):
                buffer[i] = 0
                
        if capacity not in self._buckets:
            self._buckets[capacity] = []
        self._buckets[capacity].append(buffer)


class ZeroAllocHttpParser:
    """
    Demonstrates zero-copy HTTP header parsing using Span<T> slicing.
    Avoids string.Split() or substring allocations, mirroring ASP.NET Core Kestrel parser.
    """
    CRLF = b"\r\n"
    COLON = ord(":")

    def parse_request(self, raw_request_span: Span) -> Tuple[Span, Span, List[Tuple[Span, Span]]]:
        """
        Parses Method, Path, and Headers completely within the initial Span buffer.
        """
        headers = []
        offset = 0

        # Read Request Line: METHOD PATH PROTOCOL\r\n
        line_end = self._find_crlf(raw_request_span, offset)
        if line_end == -1:
            raise ValueError("Malformed request line.")
        
        req_line_span = raw_request_span.slice(offset, line_end - offset)
        offset = line_end + 2

        # Parse Method and Path
        first_space = self._find_byte(req_line_span, 0, ord(" "))
        method_span = req_line_span.slice(0, first_space)
        second_space = self._find_byte(req_line_span, first_space + 1, ord(" "))
        path_span = req_line_span.slice(first_space + 1, second_space - (first_space + 1))

        # Parse Headers
        while offset < raw_request_span.length:
            line_end = self._find_crlf(raw_request_span, offset)
            if line_end == -1:
                break
            
            line_len = line_end - offset
            if line_len == 0:
                # Empty line indicating end of headers
                break
            
            header_span = raw_request_span.slice(offset, line_len)
            colon_idx = self._find_byte(header_span, 0, self.COLON)
            if colon_idx != -1:
                key_span = header_span.slice(0, colon_idx)
                # Trim leading space from value if present
                val_start = colon_idx + 1
                if val_start < header_span.length and header_span[val_start] == ord(" "):
                    val_start += 1
                val_span = header_span.slice(val_start, header_span.length - val_start)
                headers.append((key_span, val_span))

            offset = line_end + 2

        return method_span, path_span, headers

    def _find_crlf(self, span: Span, start: int) -> int:
        for i in range(start, span.length - 1):
            if span[i] == 13 and span[i + 1] == 10: # \r and \n
                return i
        return -1

    def _find_byte(self, span: Span, start: int, target: int) -> int:
        for i in range(start, span.length):
            if span[i] == target:
                return i
        return -1


def main():
    print(f"{BOLD}{CYAN}=== C# MEMORY MANAGEMENT, SPAN<T> & ARRAYPOOL SIMULATOR ==={RESET}\n")

    # 1. ArrayPool Rentals and Lifecycle
    pool = ArrayPool()
    print(f"{BOLD}[1] ArrayPool<byte>.Shared Simulation{RESET}")
    print(f"Renting buffers across multiple worker tasks...")

    rented_buffers = []
    for req_size in [128, 500, 1024, 250, 900]:
        buf = pool.rent(req_size)
        rented_buffers.append(buf)
        print(f"  Rented request={req_size:4d} bytes -> Allocated bucket={len(buf):4d} bytes")

    print(f"{YELLOW}Metrics before return:{RESET} Total Allocations: {pool.total_allocations}, Active Rents: {pool.rents}")
    
    # Return all buffers to pool
    for buf in rented_buffers:
        pool.return_buffer(buf)

    print(f"Returned {len(rented_buffers)} buffers back to the ArrayPool.")
    print(f"{GREEN}Metrics after return:{RESET} Total Allocations: {pool.total_allocations}, Returns Processed: {pool.returns}")

    # Re-renting should cause ZERO new allocations
    print(f"Re-renting 3 buffers...")
    for req_size in [200, 450, 1000]:
        _ = pool.rent(req_size)
    print(f"{GREEN}Zero-Alloc Verification:{RESET} Total Heap Allocations remained at: {pool.total_allocations}\n")

    # 2. Zero-Copy String Parsing via Span Slices
    print(f"{BOLD}[2] High-Performance Zero-Allocation HTTP Parser (Span Slicing){RESET}")
    raw_payload = (
        b"GET /api/v1/orders/88349 HTTP/1.1\r\n"
        b"Host: internal.service.local\r\n"
        b"User-Agent: KestrelSimulation/1.0\r\n"
        b"Accept: application/json\r\n"
        b"X-Trace-Id: 4bf92f3577b34da6a3ce929d0e0e4736\r\n"
        b"\r\n"
    )

    # Wrap raw bytes in a bytearray memory buffer
    shared_buffer = bytearray(raw_payload)
    master_span = Span(shared_buffer)
    parser = ZeroAllocHttpParser()

    method, path, headers = parser.parse_request(master_span)

    print(f"  HTTP Method : {GREEN}{method.to_bytes().decode()}{RESET} (Offset: {method._start}, Len: {method.length})")
    print(f"  HTTP Path   : {GREEN}{path.to_bytes().decode()}{RESET} (Offset: {path._start}, Len: {path.length})")
    print(f"  Parsed Headers without allocating new string objects:")
    for k, v in headers:
        print(f"    - {k.to_bytes().decode():<15} => {v.to_bytes().decode()}")

    # 3. Memory Mutation Verification (Slices point to the exact same memory)
    print(f"\n{BOLD}[3] Memory Mutation & In-Place Pointer Updating{RESET}")
    print("Modifying Path directly in memory via unsafe Span slice...")
    
    # In-place overwrite /orders/88349 to /orders/99999
    # Target '88349' inside the path span
    id_start_in_path = 16  # len('/api/v1/orders/')
    for i in range(5):
        path[id_start_in_path + i] = ord("9")

    print(f"  Updated Path Slice : {MAGENTA}{path.to_bytes().decode()}{RESET}")
    print(f"  Underlying Buffer  : {master_span.to_bytes()[:38].decode()} ...")

    # 4. Performance Benchmark: Substring vs. Span Slicing07-aspnet-internals/07_aspnet_internals.py
#!/usr/bin/env python3
"""
Lab: ASP.NET Core Internals - Middleware Pipeline & Dependency Injection Engine
Topic: C# (.NET) Internals Simulation
Features:
- ServiceCollection & ServiceProvider supporting Transient, Scoped, and Singleton lifetimes.
- Scope-isolated resolution container (ServiceScope).
- Standard ASP.NET Core Middleware Pipeline chaining (RequestDelegate -> Func<HttpContext, Func<Task>, Task>).
- Mock HTTP context processing through a realistic middleware chain (ExceptionHandling, Auth, Routing, Endpoint).
"""

import time
import uuid
from enum import Enum, auto
from typing import Dict, Any, Callable, List, Optional, Type


# --- Color Codes for Terminal Output ---
class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


# ==============================================================================
# SECTION 1: Dependency Injection Subsystem (Microsoft.Extensions.DependencyInjection)
# ==============================================================================

class ServiceLifetime(Enum):
    SINGLETON = auto()
    SCOPED = auto()
    TRANSIENT = auto()


class ServiceDescriptor:
    def __init__(self, service_type: Type, implementation_type: Type, lifetime: ServiceLifetime):
        self.service_type = service_type
        self.implementation_type = implementation_type
        self.lifetime = lifetime


class IServiceProvider:
    def get_service(self, service_type: Type) -> Any:
        raise NotImplementedError()


class IServiceScope:
    def __init__(self, service_provider: IServiceProvider):
        self.service_provider = service_provider

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class ServiceProvider(IServiceProvider):
    def __init__(self, descriptors: Dict[Type, ServiceDescriptor], parent_root: Optional['ServiceProvider'] = None):
        self.descriptors = descriptors
        self.parent_root = parent_root or self
        # Singleton instances are managed at root
        self.singletons: Dict[Type, Any] = {} if parent_root is None else parent_root.singletons
        # Scoped instances are isolated to this provider instance
        self.scoped_instances: Dict[Type, Any] = {}

    def get_service(self, service_type: Type) -> Any:
        descriptor = self.descriptors.get(service_type)
        if not descriptor:
            raise KeyError(f"No service registered for type {service_type.__name__}")

        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type not in self.singletons:
                self.singletons[service_type] = self._instantiate(descriptor.implementation_type)
            return self.singletons[service_type]

        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            if service_type not in self.scoped_instances:
                self.scoped_instances[service_type] = self._instantiate(descriptor.implementation_type)
            return self.scoped_instances[service_type]

        elif descriptor.lifetime == ServiceLifetime.TRANSIENT:
            return self._instantiate(descriptor.implementation_type)

        raise ValueError("Invalid service lifetime configuration.")

    def _instantiate(self, impl_type: Type) -> Any:
        # Reflect constructor parameters and resolve recursively from current container
        import inspect
        sig = inspect.signature(impl_type.__init__)
        params = sig.parameters
        args = {}
        for name, param in params.items():
            if name == "self":
                continue
            if param.annotation != inspect.Parameter.empty:
                args[name] = self.get_service(param.annotation)
            else:
                raise ValueError(f"Unannotated dependency '{name}' in {impl_type.__name__}")
        return impl_type(**args)

    def create_scope(self) -> 'ServiceScope':
        child_provider = ServiceProvider(self.descriptors, parent_root=self.parent_root)
        return ServiceScope(child_provider)


class ServiceScope(IServiceScope):
    def __init__(self, scoped_provider: ServiceProvider):
        super().__init__(scoped_provider)


class ServiceCollection:
    def __init__(self):
        self.descriptors: Dict[Type, ServiceDescriptor] = {}

    def add_singleton(self, service_type: Type, implementation_type: Type):
        self.descriptors[service_type] = ServiceDescriptor(service_type, implementation_type, ServiceLifetime.SINGLETON)

    def add_scoped(self, service_type: Type, implementation_type: Type):
        self.descriptors[service_type] = ServiceDescriptor(service_type, implementation_type, ServiceLifetime.SCOPED)

    def add_transient(self, service_type: Type, implementation_type: Type):
        self.descriptors[service_type] = ServiceDescriptor(service_type, implementation_type, ServiceLifetime.TRANSIENT)

    def build_service_provider(self) -> ServiceProvider:
        return ServiceProvider(self.descriptors)


# ==============================================================================
# SECTION 2: ASP.NET Core HttpContext & Pipeline Engine
# ==============================================================================

class HttpRequest:
    def __init__(self, path: str, method: str = "GET", headers: Optional[Dict[str, str]] = None):
        self.path = path
        self.method = method
        self.headers = headers or {}


class HttpResponse:
    def __init__(self):
        self.status_code = 200
        self.body: str = ""
        self.headers: Dict[str, str] = {}


class HttpContext:
    def __init__(self, request: HttpRequest, service_provider: IServiceProvider):
        self.request = request
        self.response = HttpResponse()
        self.request_services = service_provider  # Current Scoped Container
        self.items: Dict[str, Any] = {}
        self.trace_identifier = str(uuid.uuid4())[:8]


# Type definitions matching C# RequestDelegate: Func<HttpContext, Task>
RequestDelegate = Callable[[HttpContext], None]
# Type definitions matching Middleware: Func<RequestDelegate, RequestDelegate>
MiddlewareComponent = Callable[[RequestDelegate], RequestDelegate]


class ApplicationBuilder:
    def __init__(self, service_provider: IServiceProvider):
        self.service_provider = service_provider
        self._components: List[MiddlewareComponent] = []

    def use(self, middleware: Callable[[HttpContext, Callable[[], None]], None]) -> 'ApplicationBuilder':
        """Registers a middleware lambda similar to app.Use(async (context, next) => { ... })"""
        def component(next_delegate: RequestDelegate) -> RequestDelegate:
            def handler(context: HttpContext):
                middleware(context, lambda: next_delegate(context))
            return handler
        self._components.append(component)
        return self

    def build(self) -> RequestDelegate:
        """Chains middlewares in reverse order (Onion Architecture)."""
        # Terminal default 404 handler
        delegate: RequestDelegate = lambda ctx: setattr(ctx.response, 'status_code', 404)
        for component in reversed(self._components):
            delegate = component(delegate)
        return delegate


# ==============================================================================
# SECTION 3: Business Services & Simulated ASP.NET Core Application
# ==============================================================================

class IMetricsTracker:
    def record(self, action: str): pass

class MetricsTracker(IMetricsTracker):
    """Singleton Service: Survives entire application lifecycle."""
    def __init__(self):
        self.instance_id = str(uuid.uuid4())[:4]
        self.hits = 0

    def record(self, action: str):
        self.hits += 1


class IDbContext:
    def execute_query(self, sql: str) -> str: pass

class DbContext(IDbContext):
    """Scoped Service: One instance per HTTP Request pipeline."""
    def __init__(self):
        self.connection_id = str(uuid.uuid4())[:6]

    def execute_query(self, sql: str) -> str:
        return f"[DBConn:{self.connection_id}] Executed '{sql}'"


class IOrderService:
    def process_order(self, order_id: str) -> str: pass

class OrderService(IOrderService):
    """Transient Service: New instance resolved on each request for injection."""
    def __init__(self, db: IDbContext, metrics: IMetricsTracker):
        self.db = db
        self.metrics = metrics
        self.instance_id = str(uuid.uuid4())[:4]

    def process_order(self, order_id: str) -> str:
        self.metrics.record("order_processed")
        db_res = self.db.execute_query(f"INSERT INTO Orders VALUES ('{order_id}')")
        return f"[OrderSvc:{self.instance_id}] Success -> {db_res}"


# ==============================================================================
# SECTION 4: Pipeline Execution Simulation
# ==============================================================================

def run_lab():
    print(f"{Color.CYAN}{Color.BOLD}======================================================================{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD} LAB: ASP.NET CORE INTERNALS (MIDDLEWARE PIPELINE & DI ENGINE)        {Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}======================================================================{Color.RESET}\n")

    # 1. Setup DI Container
    services = ServiceCollection()
    services.add_singleton(IMetricsTracker, MetricsTracker)
    services.add_scoped(IDbContext, DbContext)
    services.add_transient(IOrderService, OrderService)
    root_provider = services.build_service_provider()

    # 2. Build Pipeline
    app = ApplicationBuilder(root_provider)

    # Middleware A: Global Exception Handler
    def error_handling_middleware(ctx: HttpContext, next_mw: Callable[[], None]):
        try:
            next_mw()
        except Exception as ex:
            ctx.response.status_code = 500
            ctx.response.body = f"GlobalExceptionHandler caught error: {str(ex)}"
            print(f"  {Color.RED}[Middleware: ExceptionHandler]{Color.RESET} Caught unhandled exception: {ex}")
    app.use(error_handling_middleware)

    # Middleware B: Request Diagnostics / Logging
    def diagnostics_middleware(ctx: HttpContext, next_mw: Callable[[], None]):
        start = time.perf_counter_ns()
        print(f"  {Color.YELLOW}[Middleware: Diagnostics IN]{Color.RESET} Request: {ctx.request.method} {ctx.request.path} (TraceID: {ctx.trace_identifier})")
        next_mw()
        elapsed = (time.perf_counter_ns() - start) / 1000.0
        print(f"  {Color.YELLOW}[Middleware: Diagnostics OUT]{Color.RESET} Status: {ctx.response.status_code} ({elapsed:.1f} µs)")
    app.use(diagnostics_middleware)

    # Middleware C: Routing & Endpoint Dispatcher
    def endpoint_routing_middleware(ctx: HttpContext, next_mw: Callable[[], None]):
        if ctx.request.path == "/checkout":
            # Resolve Scoped & Transient services from RequestServices
            order_svc: IOrderService = ctx.request_services.get_service(IOrderService)
            db: IDbContext = ctx.request_services.get_service(IDbContext)
            
            # Execute business logic
            result = order_svc.process_order("ORD-9021")
            ctx.response.status_code = 200
            ctx.response.body = f"Result: {result} | DirectScopedDBCheck: {db.connection_id}"
        elif ctx.request.path == "/fail":
            raise RuntimeError("Simulation of database crash in downstream execution!")
        else:
            next_mw()  # Continue to terminal middleware
    app.use(endpoint_routing_middleware)

    pipeline = app.build()

    # 3. Simulate Inbound HTTP Requests
    test_requests = [
        HttpRequest("/checkout", "POST"),
        HttpRequest("/checkout", "POST"),
        HttpRequest("/fail", "GET"),
        HttpRequest("/missing-endpoint", "GET")
    ]

    for req_idx, req in enumerate(test_requests, 1):
        print(f"\n{Color.BOLD}---> Dispatching Inbound HTTP Request #{req_idx} [{req.method} {req.path}] <---{Color.RESET}")
        
        # ASP.NET Core creates a scoped ServiceProvider per request
        with root_provider.create_scope() as scope:
            context = HttpContext(req, scope.service_provider)
            pipeline(context)
            
            # Print execution response
            status_color = Color.GREEN if context.response.status_code == 200 else Color.RED
            print(f"  {Color.MAGENTA}[Response Received]{Color.RESET} Status: {status_color}{context.response.status_code}{Color.RESET}")
            print(f"  {Color.MAGENTA}[Response Body]{Color.RESET}     {context.response.body or '(empty)'}")

    # Inspect Singleton State at Root Provider
    metrics: MetricsTracker = root_provider.get_service(IMetricsTracker)
    print(f"\n{Color.CYAN}{Color.BOLD}======================================================================{Color.RESET}")
    print(f"{Color.CYAN}DI Lifetime Verification Summary:{Color.RESET}")
    print(f" - Singleton MetricsTracker ID : {metrics.instance_id} (Processed Hits: {metrics.hits})")
    print(f" - Scoped DbContext             : Dynamic unique instance generated per request scope.")
    print(f" - Transient OrderService       : Distinct instance generated per DI activation.")
    print(f"{Color.CYAN}{Color.BOLD}======================================================================{Color.RESET}\n")


if __name__ == "__main__":
    run_lab()