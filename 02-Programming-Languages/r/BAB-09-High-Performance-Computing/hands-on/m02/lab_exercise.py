#!/usr/bin/env python3
"""
Lab Hands-on: R Architecture Deep Dive - HPC, Profiling, & Rcpp Simulation
Category: 02-Programming-Languages | Topic: r | Chapter: 09

Simulates R's low-level execution characteristics:
1. SEXP (S-Expression) dynamic evaluation & Copy-on-Modify semantics overhead.
2. Comparative Benchmarking: Naive R Loop vs Vectorized R vs Rcpp (Compiled C++ Ext).
3. Rprof-style Statistical Call-Stack & Memory Profiler.
4. HPC Parallelization via Fork-Worker model (simulating parallel::mclapply).
"""

import sys
import time
import math
import random
import threading
from dataclasses import dataclass, field
from typing import List, Callable, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor

# --- ANSI Terminal Formatting ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_CYAN   = "\033[36m"
CLR_BG_DARK= "\033[48;5;236m"

# ==============================================================================
# 1. R CORE RUNTIME SIMULATION (SEXP & Copy-on-Modify)
# ==============================================================================

@dataclass
class SEXP:
    """
    Simulates R's SEXP (S-Expression) object structure.
    Tracks pointer reference counts and triggers Copy-on-Modify (CoM) duplicates.
    """
    type_tag: str
    data: List[float]
    ref_count: int = 1
    allocations_logged: int = 0

    def copy(self) -> 'SEXP':
        """Deep copy triggered when mutating an object with ref_count > 1."""
        self.allocations_logged += 1
        return SEXP(type_tag=self.type_tag, data=list(self.data), ref_count=1)

    def write_element(self, idx: int, value: float) -> 'SEXP':
        """Simulates R's duplicate() check before modifying vector elements."""
        target = self
        if self.ref_count > 1:
            target = self.copy()
            target.data[idx] = value
            return target
        self.data[idx] = value
        return self


# ==============================================================================
# 2. STATISTICAL PROFILER ENGINE (Simulating Rprof & Memory Tracing)
# ==============================================================================

class RprofSimulator:
    """
    Simulates R's `Rprof(interval = 0.001, memory.profiling = TRUE)`.
    Uses background sampling to monitor call stacks and memory allocations.
    """
    def __init__(self, sampling_interval_sec: float = 0.001):
        self.interval = sampling_interval_sec
        self.active_stack: List[str] = []
        self.samples: Dict[str, int] = {}
        self.memory_samples: Dict[str, int] = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def set_current_frame(self, frame_name: str):
        with self._lock:
            self.active_stack.append(frame_name)

    def pop_current_frame(self):
        with self._lock:
            if self.active_stack:
                self.active_stack.pop()

    def _sample_loop(self):
        while self._running:
            with self._lock:
                if self.active_stack:
                    current_fn = self.active_stack[-1]
                    self.samples[current_fn] = self.samples.get(current_fn, 0) + 1
            time.sleep(self.interval)

    def start(self):
        self.samples.clear()
        self._running = True
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()

    def print_summary(self):
        print(f"\n{CLR_BOLD}{CLR_CYAN}[Rprof Execution Profile Summary]{CLR_RESET}")
        print(f"{'Call / Function Node':<30} | {'Tick Samples':<12} | {'Estimated Self %':<15}")
        print("-" * 65)
        total_samples = sum(self.samples.values()) or 1
        for fn, ticks in sorted(self.samples.items(), key=lambda item: item[1], reverse=True):
            pct = (ticks / total_samples) * 100
            print(f"{fn:<30} | {ticks:<12} | {pct:>6.2f}%")


# ==============================================================================
# 3. COMPUTATIONAL WORKLOAD IMPLEMENTATIONS
# ==============================================================================

# Target workload: Calculate moving standard deviations over numeric vector
WINDOW_SIZE = 10

def pure_r_naive_loop(raw_data: List[float], profiler: RprofSimulator) -> List[float]:
    """
    Simulates base R interpreter overhead:
    - SEXP re-allocation via append/copy-on-modify inside a for-loop.
    - Repeated dynamic method lookup / boxing.
    """
    profiler.set_current_frame("pure_r_naive_loop")
    
    # Simulating R vector with shared reference
    vec_sexp = SEXP(type_tag="REALSXP", data=list(raw_data), ref_count=2)
    n = len(raw_data)
    result = SEXP(type_tag="REALSXP", data=[], ref_count=2)

    for i in range(n - WINDOW_SIZE + 1):
        window = []
        for j in range(WINDOW_SIZE):
            # Dynamic lookup simulation overhead
            val = vec_sexp.data[i + j]
            window.append(val)
            # Intentional slight cpu spin simulating AST eval overhead
            _ = math.sqrt(val * val)
        
        # Calculate standard deviation
        mean = sum(window) / WINDOW_SIZE
        variance = sum((x - mean) ** 2 for x in window) / (WINDOW_SIZE - 1)
        std_dev = math.sqrt(variance)

        # Trigger SEXP copy-on-modify behavior: dynamically growing vectors in R loops
        result = result.copy()
        result.data.append(std_dev)

    profiler.pop_current_frame()
    return result.data


def r_vectorized_approach(raw_data: List[float], profiler: RprofSimulator) -> List[float]:
    """
    Simulates R's vectorized idioms (C-internal dispatch, pre-allocated memory buffers).
    """
    profiler.set_current_frame("r_vectorized_approach")
    n = len(raw_data)
    out_len = n - WINDOW_SIZE + 1
    
    # Pre-allocated contiguous buffer (zero resizing)
    out = [0.0] * out_len
    
    # Cumulative sums to compute sliding window statistics (C-level vector operations)
    cumsum = [0.0] * (n + 1)
    cumsum_sq = [0.0] * (n + 1)
    
    for i in range(n):
        cumsum[i + 1] = cumsum[i] + raw_data[i]
        cumsum_sq[i + 1] = cumsum_sq[i] + raw_data[i] * raw_data[i]
        
    k = WINDOW_SIZE
    inv_k_minus_1 = 1.0 / (k - 1)
    
    for i in range(out_len):
        sum_w = cumsum[i + k] - cumsum[i]
        sum_sq_w = cumsum_sq[i + k] - cumsum_sq[i]
        variance = (sum_sq_w - (sum_w * sum_w) / k) * inv_k_minus_1
        out[i] = math.sqrt(max(0.0, variance))

    profiler.pop_current_frame()
    return out


def rcpp_compiled_kernel(raw_data: List[float], profiler: RprofSimulator) -> List[float]:
    """
    Simulates Rcpp / C++ inline extension:
    - Direct pointer traversal (zero boxing/unboxing).
    - Single-pass Welford's algorithm for numerical stability.
    - Zero garbage collection pressure.
    """
    profiler.set_current_frame("rcpp_compiled_kernel")
    n = len(raw_data)
    out_len = n - WINDOW_SIZE + 1
    out = [0.0] * out_len

    # Direct loop emulation bypassing all interpreter abstractions
    for i in range(out_len):
        m = 0.0
        s = 0.0
        for j in range(WINDOW_SIZE):
            x = raw_data[i + j]
            old_m = m
            m += (x - m) / (j + 1)
            s += (x - old_m) * (x - m)
        out[i] = math.sqrt(s / (WINDOW_SIZE - 1))

    profiler.pop_current_frame()
    return out


# ==============================================================================
# 4. HPC MULTI-CORE WORKER ENGINE (Simulating parallel::mclapply)
# ==============================================================================

def mclapply_simulation(
    chunks: List[List[float]], 
    worker_kernel: Callable[[List[float], RprofSimulator], List[float]], 
    cores: int
) -> List[float]:
    """
    Simulates R's `parallel::mclapply(chunks, FUN, mc.cores=cores)`.
    Distributes sub-arrays to isolated threads/processes.
    """
    dummy_prof = RprofSimulator()
    results = []
    
    with ThreadPoolExecutor(max_workers=cores) as executor:
        futures = [executor.submit(worker_kernel, chunk, dummy_prof) for chunk in chunks]
        for f in futures:
            results.extend(f.result())
            
    return results


# ==============================================================================
# 5. LAB BENCHMARK HARNESS & VERIFICATION
# ==============================================================================

def run_benchmarks():
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}   LAB: HIGH-PERFORMANCE COMPUTING, PROFILING & RCPP INTERFACE        {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    
    # Generate reproducible synthetic time-series dataset
    random.seed(42)
    DATASET_SIZE = 8_000
    print(f"{CLR_YELLOW}[*] Initializing synthetic input signal: {DATASET_SIZE:,} elements...{CLR_RESET}")
    synthetic_signal = [random.gauss(100.0, 15.0) for _ in range(DATASET_SIZE)]

    profiler = RprofSimulator(sampling_interval_sec=0.0005)
    profiler.start()

    benchmark_registry = [
        ("1. Pure R Naive Loop (CoM Overhead)", pure_r_naive_loop),
        ("2. R Vectorized (Prefix Sums/BLAS)", r_vectorized_approach),
        ("3. Rcpp C++ Engine (Zero-Copy Pointers)", rcpp_compiled_kernel),
    ]

    execution_metrics: List[Tuple[str, float, float, int]] = []
    baseline_output = None

    for label, fn in benchmark_registry:
        print(f"\n{CLR_CYAN}[>] Executing: {label}...{CLR_RESET}")
        
        t_start = time.perf_counter_ns()
        result = fn(synthetic_signal, profiler)
        t_elapsed_ms = (time.perf_counter_ns() - t_start) / 1_000_000.0

        if baseline_output is None:
            baseline_output = result
        else:
            # Verify numerical fidelity against naive implementation
            max_delta = max(abs(a - b) for a, b in zip(baseline_output[:100], result[:100]))
            assert max_delta < 1e-6, f"Validation failure! Delta: {max_delta}"

        execution_metrics.append((label, t_elapsed_ms, 0.0, len(result)))

    profiler.stop()

    # --- 4. Parallel HPC Evaluation ---
    print(f"\n{CLR_CYAN}[>] Executing: 4. HPC Simulation (parallel::mclapply 4-Cores)...{CLR_RESET}")
    chunk_size = len(synthetic_signal) // 4
    signal_chunks = [synthetic_signal[i:i + chunk_size] for i in range(0, len(synthetic_signal), chunk_size)]
    
    t_start = time.perf_counter_ns()
    parallel_res = mclapply_simulation(signal_chunks, rcpp_compiled_kernel, cores=4)
    t_parallel_ms = (time.perf_counter_ns() - t_start) / 1_000_000.0
    execution_metrics.append(("4. Rcpp + parallel::mclapply (4 cores)", t_parallel_ms, 0.0, len(parallel_res)))

    # --- Print Benchmark Report ---
    baseline_ms = execution_metrics[0][1]
    print(f"\n{CLR_BOLD}{CLR_GREEN}======================= PERFORMANCE BENCHMARK MATRIX ======================={CLR_RESET}")
    print(f"{'Strategy / Implementation':<42} | {'Wall Time':<12} | {'Speedup Factor':<15}")
    print("-" * 75)

    for label, duration_ms, _, count in execution_metrics:
        speedup = baseline_ms / duration_ms if duration_ms > 0 else float('inf')
        color = CLR_GREEN if speedup > 2.0 else (CLR_YELLOW if speedup >= 1.0 else CLR_RED)
        print(f"{label:<42} | {duration_ms:>8.2f} ms | {color}{speedup:>13.2f}x{CLR_RESET}")
    print("-" * 75)

    # Output profiler statistical breakdown
    profiler.print_summary()

    print(f"\n{CLR_BOLD}{CLR_GREEN}[✔] HPC & Profiling simulation completed successfully.{CLR_RESET}\n")

if __name__ == "__main__":
    run_benchmarks()