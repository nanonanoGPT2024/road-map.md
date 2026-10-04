#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Data Structures & Specialized Paradigms
Chapter 10, Module 02: Segment Trees with Lazy Propagation vs. Dual-BIT Range Engines

Implements and benchmarks:
1. Segment Tree with Lazy Propagation (O(log N) Range Add, O(log N) Range Sum).
2. Dual Binary Indexed Tree (Fenwick) for Range Add & Range Query (O(log N) operations).
3. Naive reference engine for ground-truth fuzzing & verification.
"""

import sys
import time
import random

# ANSI Terminal Styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"


class SegmentTreeLazy:
    """
    Segment Tree with Lazy Propagation supporting:
    - Range Add Updates
    - Range Sum Queries
    Space Complexity: O(4N)
    Time Complexity: O(log N) per update/query
    """

    def __init__(self, data: list):
        self.n = len(data)
        self.tree = [0] * (4 * self.n)
        self.lazy = [0] * (4 * self.n)
        if self.n > 0:
            self._build(data, 1, 0, self.n - 1)

    def _build(self, data: list, node: int, start: int, end: int):
        if start == end:
            self.tree[node] = data[start]
            return
        mid = (start + end) // 2
        left_node = 2 * node
        right_node = 2 * node + 1
        self._build(data, left_node, start, mid)
        self._build(data, right_node, mid + 1, end)
        self.tree[node] = self.tree[left_node] + self.tree[right_node]

    def _push_down(self, node: int, start: int, end: int):
        """Propagate pending deferred modifications to children nodes."""
        if self.lazy[node] != 0:
            lazy_val = self.lazy[node]
            mid = (start + end) // 2
            left_node = 2 * node
            right_node = 2 * node + 1

            # Update children tree aggregations
            self.tree[left_node] += lazy_val * (mid - start + 1)
            self.tree[right_node] += lazy_val * (end - mid)

            # Cascade lazy state
            self.lazy[left_node] += lazy_val
            self.lazy[right_node] += lazy_val

            # Clear current node lazy state
            self.lazy[node] = 0

    def update_range(self, ql: int, qr: int, val: int, node: int = 1, start: int = 0, end: int = -1):
        if end == -1:
            end = self.n - 1
        if ql <= start and end <= qr:
            self.tree[node] += val * (end - start + 1)
            self.lazy[node] += val
            return

        self._push_down(node, start, end)
        mid = (start + end) // 2
        left_node = 2 * node
        right_node = 2 * node + 1

        if ql <= mid:
            self.update_range(ql, qr, val, left_node, start, mid)
        if qr > mid:
            self.update_range(ql, qr, val, right_node, mid + 1, end)

        self.tree[node] = self.tree[left_node] + self.tree[right_node]

    def query_range(self, ql: int, qr: int, node: int = 1, start: int = 0, end: int = -1) -> int:
        if end == -1:
            end = self.n - 1
        if ql <= start and end <= qr:
            return self.tree[node]

        self._push_down(node, start, end)
        mid = (start + end) // 2
        total = 0
        left_node = 2 * node
        right_node = 2 * node + 1

        if ql <= mid:
            total += self.query_range(ql, qr, left_node, start, mid)
        if qr > mid:
            total += self.query_range(ql, qr, right_node, mid + 1, end)

        return total


class DualFenwickTree:
    """
    Point update / Prefix sum BIT combined mathematically to support:
    - O(log N) Range Add Updates
    - O(log N) Range Sum Queries
    Based on the identity:
    Sum(A[1..p]) = p * Sum(B1[1..p]) - Sum(B2[1..p])
    """

    def __init__(self, size: int):
        self.n = size
        self.bit1 = [0] * (self.n + 2)
        self.bit2 = [0] * (self.n + 2)

    def _add(self, bit: list, idx: int, val: int):
        while idx <= self.n:
            bit[idx] += val
            idx += idx & (-idx)

    def _query(self, bit: list, idx: int) -> int:
        res = 0
        while idx > 0:
            res += bit[idx]
            idx -= idx & (-idx)
        return res

    def update_range(self, l: int, r: int, val: int):
        # 1-based indexing adaptation
        l += 1
        r += 1
        self._add(self.bit1, l, val)
        self._add(self.bit1, r + 1, -val)
        self._add(self.bit2, l, val * (l - 1))
        self._add(self.bit2, r + 1, -val * r)

    def _prefix_sum(self, idx: int) -> int:
        return self._query(self.bit1, idx) * idx - self._query(self.bit2, idx)

    def query_range(self, l: int, r: int) -> int:
        # 1-based indexing adaptation
        l += 1
        r += 1
        return self._prefix_sum(r) - self._prefix_sum(l - 1)


class NaiveReference:
    """Brute-force baseline engine for fuzz verification."""

    def __init__(self, data: list):
        self.data = list(data)

    def update_range(self, l: int, r: int, val: int):
        for i in range(l, r + 1):
            self.data[i] += val

    def query_range(self, l: int, r: int) -> int:
        return sum(self.data[l:r + 1])


def run_correctness_suite(iterations: int = 5000, array_size: int = 128):
    print(f"{C_BOLD}{C_CYAN}[PHASE 1] Correctness & Differential Fuzzing Suite{C_RESET}")
    print(f"Target Array Size : {array_size}")
    print(f"Operations Count   : {iterations} randomized queries/mutations")

    initial_data = [random.randint(-100, 100) for _ in range(array_size)]
    seg_tree = SegmentTreeLazy(initial_data)
    naive = NaiveReference(initial_data)
    bit = DualFenwickTree(array_size)

    # Initialize Dual Fenwick Tree with initial elements
    for i, val in enumerate(initial_data):
        bit.update_range(i, i, val)

    mismatches = 0
    for op_id in range(iterations):
        op_type = random.choice(["UPDATE", "QUERY"])
        l = random.randint(0, array_size - 1)
        r = random.randint(l, array_size - 1)

        if op_type == "UPDATE":
            val = random.randint(-50, 50)
            naive.update_range(l, r, val)
            seg_tree.update_range(l, r, val)
            bit.update_range(l, r, val)
        else:
            ans_naive = naive.query_range(l, r)
            ans_seg = seg_tree.query_range(l, r)
            ans_bit = bit.query_range(l, r)

            if not (ans_naive == ans_seg == ans_bit):
                mismatches += 1
                print(f"{C_RED}[FAIL] Op {op_id}: Range [{l}, {r}] | Naive: {ans_naive}, SegTree: {ans_seg}, BIT: {ans_bit}{C_RESET}")
                break

    if mismatches == 0:
        print(f"{C_GREEN}[PASS] Complete state parity verified across Naive, Segment Tree, and Dual BIT.{C_RESET}\n")
    else:
        print(f"{C_RED}[ABORT] State corruption detected.{C_RESET}\n")
        sys.exit(1)


def run_benchmark_suite(array_size: int = 50000, ops_count: int = 100000):
    print(f"{C_BOLD}{C_CYAN}[PHASE 2] High-Throughput Performance Profiling{C_RESET}")
    print(f"Dataset Size      : {array_size:,} nodes")
    print(f"Total Operations  : {ops_count:,} interleaved transactions")

    # Generate synthetic operations beforehand to decouple RNG latency
    ops = []
    for _ in range(ops_count):
        t = 0 if random.random() < 0.5 else 1  # 0: Query, 1: Update
        l = random.randint(0, array_size - 1)
        r = random.randint(l, array_size - 1)
        v = random.randint(1, 100) if t == 1 else 0
        ops.append((t, l, r, v))

    # Benchmark: Segment Tree
    base_data = [0] * array_size
    seg_tree = SegmentTreeLazy(base_data)

    t0 = time.perf_counter()
    seg_checksum = 0
    for t, l, r, v in ops:
        if t == 1:
            seg_tree.update_range(l, r, v)
        else:
            seg_checksum += seg_tree.query_range(l, r)
    seg_time = time.perf_counter() - t0

    # Benchmark: Dual Fenwick Tree
    bit = DualFenwickTree(array_size)
    t0 = time.perf_counter()
    bit_checksum = 0
    for t, l, r, v in ops:
        if t == 1:
            bit.update_range(l, r, v)
        else:
            bit_checksum += bit.query_range(l, r)
    bit_time = time.perf_counter() - t0

    # Integrity verification via checksum comparison
    assert seg_checksum == bit_checksum, "Checksum mismatch between engines!"

    # Metrics computation
    seg_ops_sec = ops_count / seg_time
    bit_ops_sec = ops_count / bit_time
    speedup = seg_time / bit_time if bit_time > 0 else 0

    print(f"\n{C_BOLD}{'Engine Architecture':<28} | {'Execution Time':<15} | {'Throughput (Ops/sec)':<20}{C_RESET}")
    print("-" * 70)
    print(f"{C_YELLOW}{'Segment Tree (Lazy)':<28}{C_RESET} | {seg_time:>13.4f}s | {seg_ops_sec:>18.2f} ops/s")
    print(f"{C_MAGENTA}{'Dual Fenwick Tree':<28}{C_RESET} | {bit_time:>13.4f}s | {bit_ops_sec:>18.2f} ops/s")
    print("-" * 70)

    print(f"Checksum Integrity  : {C_GREEN}VALID (Σ = {seg_checksum}){C_RESET}")
    print(f"Fenwick vs SegTree  : {C_GREEN}{speedup:.2f}x speedup observed{C_RESET} due to lower cache misses and recursion-free design.")


if __name__ == "__main__":
    print(f"{C_BOLD}{'=' * 70}{C_RESET}")
    print(f"{C_BOLD} ADVANCED DATA STRUCTURES: RANGE QUERY & MUTATION ENGINES {C_RESET}")
    print(f"{C_BOLD}{'=' * 70}{C_RESET}\n")

    random.seed(42)  # Deterministic test runs
    run_correctness_suite(iterations=10000, array_size=256)
    run_benchmark_suite(array_size=50000, ops_count=100000)

    print(f"\n{C_BOLD}{C_GREEN}Lab execution finished successfully.{C_RESET}")