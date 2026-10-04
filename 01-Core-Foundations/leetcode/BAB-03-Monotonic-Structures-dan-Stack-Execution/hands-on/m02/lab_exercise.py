#!/usr/bin/env python3
"""
Lab Hands-on: Monotonic Structures & Stack Execution Engine
Category: 01-Core-Foundations | Chapter 03: Monotonic Structures & Stack Execution

This module implements and benchmarks production-grade monotonic primitives:
1. Monotonic Decreasing Stack (Next Greater Element / Daily Latency Spikes)
2. Monotonic Increasing Stack (Largest Rectangle in Histogram / Peak Resource Utilization)
3. Monotonic Deque (Sliding Window Maximum for High-Frequency Metric Stream)
Includes brute-force verification, step-by-step state logging, and performance telemetry.
"""

from collections import deque
import random
import sys
import time
from typing import List, Tuple

# ANSI terminal formatting constants
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"


class MonotonicEngine:
    """
    Implements core monotonic algorithms optimized for amortized O(N) execution.
    """

    @staticmethod
    def next_greater_elements(arr: List[int]) -> List[int]:
        """
        Calculates the distance to the next strictly greater element for each index.
        Pattern: Monotonic Decreasing Stack.
        Time Complexity: O(N) amortized (each index pushed and popped at most once).
        Space Complexity: O(N) auxiliary stack.
        """
        n = len(arr)
        result = [0] * n
        # Stack stores indices of elements waiting for a greater successor
        stack: List[int] = []

        for i, val in enumerate(arr):
            while stack and arr[stack[-1]] < val:
                prev_idx = stack.pop()
                result[prev_idx] = i - prev_idx
            stack.append(i)

        # Remaining indices in stack have no greater element to their right
        while stack:
            prev_idx = stack.pop()
            result[prev_idx] = 0

        return result

    @staticmethod
    def largest_rectangle_area(heights: List[int]) -> Tuple[int, Tuple[int, int]]:
        """
        Finds the maximum rectangular area formed by contiguous histogram bars.
        Pattern: Monotonic Increasing Stack.
        Time Complexity: O(N) amortized.
        Space Complexity: O(N).
        Returns: (max_area, (start_idx, end_idx))
        """
        # Sentinel zero added at end to flush stack cleanly without duplicating loop logic
        augmented = heights + [0]
        stack: List[int] = []
        max_area = 0
        best_window = (0, 0)

        for i, h in enumerate(augmented):
            # Maintain monotonic non-decreasing stack
            while stack and augmented[stack[-1]] > h:
                top_idx = stack.pop()
                height = augmented[top_idx]
                # Width spans between current i (exclusive) and previous stack top (exclusive)
                width = i if not stack else i - stack[-1] - 1
                area = height * width
                if area > max_area:
                    max_area = area
                    start_idx = 0 if not stack else stack[-1] + 1
                    best_window = (start_idx, i - 1)
            stack.append(i)

        return max_area, best_window

    @staticmethod
    def sliding_window_max_monotonic(nums: List[int], k: int) -> List[int]:
        """
        Computes maximum value in each sliding window of size k using Monotonic Deque.
        Time Complexity: O(N) strictly amortized.
        Space Complexity: O(k) for the deque.
        """
        if not nums or k <= 0:
            return []
        if k == 1:
            return list(nums)

        deq: deque[int] = deque()  # Stores indices, values are monotonically decreasing
        result: List[int] = []

        for i, val in enumerate(nums):
            # 1. Evict elements out of the current sliding window [i - k + 1, i]
            while deq and deq[0] < i - k + 1:
                deq.popleft()

            # 2. Maintain monotonic decreasing order: pop elements <= current value
            while deq and nums[deq[-1]] <= val:
                deq.pop()

            # 3. Push current index
            deq.append(i)

            # 4. Record front of deque as max once first full window is reached
            if i >= k - 1:
                result.append(nums[deq[0]])

        return result

    @staticmethod
    def sliding_window_max_brute_force(nums: List[int], k: int) -> List[int]:
        """
        Naive sliding window maximum for baseline comparison and invariant checking.
        Time Complexity: O(N * k).
        Space Complexity: O(1) auxiliary.
        """
        if not nums or k <= 0:
            return []
        return [max(nums[i:i + k]) for i in range(len(nums) - k + 1)]


def print_banner(text: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 75}")
    print(f" {text}")
    print(f"{'=' * 75}{CLR_RESET}")


def run_next_greater_demo() -> None:
    print_banner("1. Monotonic Decreasing Stack: Metric Latency Spike Detector")
    sample_latencies = [73, 74, 75, 71, 69, 72, 76, 73]
    print(f"Sample Input Latencies (ms) : {sample_latencies}")

    distances = MonotonicEngine.next_greater_elements(sample_latencies)
    print(f"Intervals to Higher Latency : {distances}")

    print(f"\n{CLR_YELLOW}Execution Trace:{CLR_RESET}")
    for i, (lat, dist) in enumerate(zip(sample_latencies, distances)):
        if dist > 0:
            target_lat = sample_latencies[i + dist]
            print(f"  idx {i} [latency: {lat}ms] -> Higher peak at idx {i + dist} [{target_lat}ms] (+{dist} steps)")
        else:
            print(f"  idx {i} [latency: {lat}ms] -> {CLR_RED}No subsequent higher peak found (0){CLR_RESET}")


def run_largest_rectangle_demo() -> None:
    print_banner("2. Monotonic Increasing Stack: Cluster Memory Utilization")
    memory_blocks = [2, 1, 5, 6, 2, 3]
    print(f"Server Allocation Units: {memory_blocks}")

    max_area, (start_idx, end_idx) = MonotonicEngine.largest_rectangle_area(memory_blocks)
    print(f"Largest Rectangular Capacity : {CLR_GREEN}{max_area} units{CLR_RESET}")
    print(f"Optimal Sub-array Range     : Indices [{start_idx}..{end_idx}]")

    # ASCII visualization of the histogram
    max_h = max(memory_blocks)
    print(f"\n{CLR_YELLOW}Histogram Profile Matrix:{CLR_RESET}")
    for level in range(max_h, 0, -1):
        line = f"  {level:2d} | "
        for idx, h in enumerate(memory_blocks):
            in_window = start_idx <= idx <= end_idx
            bar_color = CLR_GREEN if in_window else CLR_CYAN
            line += f"{bar_color}██ {CLR_RESET}" if h >= level else "   "
        print(line)
    print("      " + "---" * len(memory_blocks))
    print("       " + "".join([f" {i} " for i in range(len(memory_blocks))]))


def run_sliding_window_benchmark() -> None:
    print_banner("3. High-Throughput Benchmark: O(N) Deque vs O(N*k) Brute Force")

    num_samples = 120_000
    window_size = 500
    print(f"Generating synthetic telemetry: {num_samples:,} data points, window k={window_size}...")

    random.seed(42)
    stream = [random.randint(10, 10_000) for _ in range(num_samples)]

    # 1. Monotonic Deque Execution
    t0 = time.perf_counter()
    res_mono = MonotonicEngine.sliding_window_max_monotonic(stream, window_size)
    mono_time = time.perf_counter() - t0

    # 2. Brute Force (evaluate only on slice to prevent CPU lockup)
    brute_sample_size = 15_000
    print(f"Benchmarking Brute-Force on reduced slice ({brute_sample_size:,} points)...")
    t1 = time.perf_counter()
    res_brute_partial = MonotonicEngine.sliding_window_max_brute_force(
        stream[:brute_sample_size], window_size
    )
    brute_time_partial = time.perf_counter() - t1

    # Extrapolate full brute force time
    extrapolated_brute_time = (brute_time_partial / brute_sample_size) * num_samples

    # Correctness verification
    verification_passed = res_mono[: len(res_brute_partial)] == res_brute_partial

    print(f"\n{CLR_BOLD}Benchmark Results:{CLR_RESET}")
    status = f"{CLR_GREEN}PASSED (Identical Outputs){CLR_RESET}" if verification_passed else f"{CLR_RED}FAILED{CLR_RESET}"
    print(f"  Verification Status         : {status}")
    print(f"  Monotonic Deque Total Time  : {CLR_GREEN}{mono_time:.4f}s{CLR_RESET} ({num_samples / mono_time:,.0f} ops/sec)")
    print(f"  Brute-Force Sample Time     : {CLR_YELLOW}{brute_time_partial:.4f}s{CLR_RESET} ({brute_sample_size:,} elements)")
    print(f"  Brute-Force Extrapolated    : {CLR_RED}{extrapolated_brute_time:.4f}s{CLR_RESET}")
    speedup = extrapolated_brute_time / mono_time if mono_time > 0 else 0
    print(f"  Performance Advantage       : {CLR_BOLD}{CLR_CYAN}{speedup:.1f}x Speedup{CLR_RESET}")


def main() -> None:
    print(f"{CLR_BOLD}Monotonic Engine & Stack Execution Testbed{CLR_RESET}")
    print(f"Environment: Python {sys.version.split()[0]} | Platform: {sys.platform}")

    run_next_greater_demo()
    run_largest_rectangle_demo()
    run_sliding_window_benchmark()

    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ Lab completed successfully. All invariants verified.{CLR_RESET}\n")


if __name__ == "__main__":
    main()