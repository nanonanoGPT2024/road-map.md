#!/usr/bin/env python3
"""
Lab Hands-on: R Internal Architecture Deep Dive
Topic: Data Type System, Internal Memory Model (SEXP), Copy-on-Write (CoW), & Vectorization
Category: 02-Programming-Languages (R Internals)

This script simulates the internal runtime mechanics of GNU R:
1. SEXP (S-Expression) object header & memory representation.
2. Refcount-driven Copy-on-Write (CoW) semantics (NAMED / REFCNT).
3. ALTREP (Alternative Representation) zero-copy sequences.
4. SIMD/Vectorized C-level primitive loops vs interpreted scalar iterations.
"""

from __future__ import annotations
import sys
import time
import math
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union

# --- ANSI Terminal Formatting ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"

# --- R Internals Constants ---
# In 64-bit GNU R, a SEXPREC header typically costs ~40-48 bytes + payload pointers.
SEXPREC_HEADER_SIZE_BYTES = 48
ELEMENT_SIZE_MAP = {
    "LGLSXP": 4,   # Logical (int32 in C)
    "INTSXP": 4,   # Integer (int32 in C)
    "REALSXP": 8,  # Double precision float (float64)
    "STRSXP": 8,   # Pointer to CHARSXP cache
    "VECSXP": 8    # Generic vector / R list (array of pointers)
}


class SEXPType(Enum):
    """Core primitive types modeled directly from R's Rinternals.h."""
    NILSXP  = 0
    LGLSXP  = 10
    INTSXP  = 13
    REALSXP = 14
    STRSXP  = 16
    VECSXP  = 19


@dataclass
class SEXPHeader:
    """
    Simulates sxpinfo structure (32-bit bitfield in GNU R):
    - type: SEXPType
    - refcnt: Reference counter (R >= 3.1.0 uses REFCNT, prior used NAMED)
    - mark: Garbage Collection trace bit
    - gp: General purpose flags
    """
    type: SEXPType
    refcnt: int = 1
    mark: bool = False
    gp: int = 0


class RVector:
    """
    Emulates an R Vector object backed by continuous C-allocated memory.
    Simulates pointer mutation, tracking CoW behaviors and SEXP metadata.
    """
    _mem_address_seq: int = 0x7FFF00000000

    def __init__(self, sexptype: SEXPType, data: List[Any], name: str = "<anon>"):
        RVector._mem_address_seq += 0x1000
        self.address: int = RVector._mem_address_seq
        self.header = SEXPHeader(type=sexptype, refcnt=1)
        self.data: List[Any] = list(data)
        self.length: int = len(data)
        self.binding_symbol: str = name

    def duplicate(self) -> RVector:
        """Simulates Rf_duplicate() in R C-source (src/main/duplicate.c)."""
        RVector._mem_address_seq += 0x1000
        new_vec = RVector(self.header.type, self.data, self.binding_symbol)
        new_vec.address = RVector._mem_address_seq
        new_vec.header.refcnt = 1
        return new_vec

    @property
    def memory_footprint_bytes(self) -> int:
        elem_size = ELEMENT_SIZE_MAP.get(self.header.type.name, 8)
        return SEXPREC_HEADER_SIZE_BYTES + (self.length * elem_size)

    def write_item(self, index: int, value: Any) -> RVector:
        """
        Emulates R's mutation dispatch. If REFCNT > 1, the memory is duplicated
        before mutation to protect referential transparency (Copy-on-Write).
        """
        target = self
        if self.header.refcnt > 1:
            print(f"  {CLR_YELLOW}[CoW Triggered]{CLR_RESET} Refcount={self.header.refcnt} > 1. "
                  f"Duplicating SEXP at 0x{self.address:X}...")
            target = self.duplicate()
            self.header.refcnt -= 1
            print(f"  {CLR_GREEN}[Allocated]{CLR_RESET} Deep duplicate materialized at 0x{target.address:X}")

        target.data[index] = value
        return target

    def __repr__(self) -> str:
        preview = str(self.data[:4]) + ("..." if len(self.data) > 4 else "")
        return (f"<SEXP {self.header.type.name} at 0x{self.address:X} "
                f"len={self.length} refcnt={self.header.refcnt} payload={preview}>")


class ALTREPSequence:
    """
    Simulates R 3.5.0+ ALTREP (Alternative Representation) framework.
    Represents an integer sequence (e.g., 1:1e8) without materializing memory.
    """
    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end
        self.step = 1 if end >= start else -1
        self.length = abs(end - start) + 1

    @property
    def materialized_size_bytes(self) -> int:
        return SEXPREC_HEADER_SIZE_BYTES + (self.length * ELEMENT_SIZE_MAP["INTSXP"])

    @property
    def altrep_size_bytes(self) -> int:
        # ALTREP only stores start, end, step, and standard wrapper class pointers.
        return SEXPREC_HEADER_SIZE_BYTES + 24

    def __getitem__(self, idx: int) -> int:
        if 0 <= idx < self.length:
            return self.start + (idx * self.step)
        raise IndexError("ALTREP integer bounds exceeded")


# --- Lab Modules & Demonstration Execution ---

def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'=' * 78}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}::: {title} {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'=' * 78}{CLR_RESET}")


def lab_01_sexp_and_cow():
    """Demonstrates R's internal SEXP header and Copy-on-Write semantics."""
    print_header("LAB 01: SEXP Metadata & Copy-On-Write (CoW) Mechanics")

    # Step 1: Initialize an integer vector
    print(f"{CLR_BOLD}1. Allocating SEXP x <- c(10L, 20L, 30L){CLR_RESET}")
    x = RVector(SEXPType.INTSXP, [10, 20, 30], name="x")
    print(f"  Symbol 'x': {x}")
    print(f"  Memory allocated: {x.memory_footprint_bytes} bytes")

    # Step 2: Shallow binding assignment (y <- x)
    print(f"\n{CLR_BOLD}2. Binding Assignment y <- x (Shared Pointer){CLR_RESET}")
    y = x
    x.header.refcnt += 1
    print(f"  Symbol 'x': {x}")
    print(f"  Symbol 'y': {y}")
    print(f"  Pointers match: {CLR_GREEN}{x.address == y.address}{CLR_RESET} (Shared buffer)")

    # Step 3: Modifying y triggers duplicate() because refcnt > 1
    print(f"\n{CLR_BOLD}3. Mutating y[1] <- 999L (Write Operation){CLR_RESET}")
    y = y.write_item(0, 999)
    print(f"  Symbol 'x': {x}")
    print(f"  Symbol 'y': {y}")
    print(f"  Pointers match: {CLR_RED}{x.address == y.address}{CLR_RESET} (Decoupled via CoW)")


def lab_02_altrep_memory_optimization():
    """Demonstrates memory footprint difference between Materialized SEXP vs ALTREP."""
    print_header("LAB 02: ALTREP (Alternative Representation) Memory Efficiency")

    seq_size = 50_000_000
    print(f"Evaluating Sequence: 1:{seq_size:,}")

    altrep = ALTREPSequence(1, seq_size)
    mat_mb = altrep.materialized_size_bytes / (1024 * 1024)
    altrep_kb = altrep.altrep_size_bytes / 1024

    print(f"  Materialized INTSXP footprint : {CLR_RED}{mat_mb:,.2f} MB{CLR_RESET}")
    print(f"  ALTREP Compact Integer Vector : {CLR_GREEN}{altrep_kb:,.2f} KB{CLR_RESET}")
    print(f"  Memory Savings                : {CLR_BOLD}{(1 - (altrep.altrep_size_bytes / altrep.materialized_size_bytes)) * 100:.6f}%{CLR_RESET}")

    # Random access verification without heap allocation
    test_indices = [0, seq_size // 2, seq_size - 1]
    print("\nSimulating ALTREP Element Extraction (O(1) Arithmetic):")
    for idx in test_indices:
        val = altrep[idx]
        print(f"  Index [{idx:,}] => Value: {val:,}")


def lab_03_vectorization_engine():
    """
    Simulates performance differences between scalar interpreted loops (eval loop in R)
    versus C-level vectorized operations executing over continuous SEXP buffers.
    """
    print_header("LAB 03: Vectorization Benchmark (C-Level SIMD vs Interpreted Loop)")

    n_elements = 1_000_000
    print(f"Dataset Size: {n_elements:,} REALSXP elements (double precision)")
    data = [math.sin(i) * 10.0 for i in range(n_elements)]

    # 1. Simulating interpreted scalar loop (Evaluator overhead per element)
    # In R, a 'for' loop hits the evaluator context, environment lookups, and type checks.
    print(f"\n{CLR_YELLOW}[Running Simulation 1]{CLR_RESET} Interpreted Scalar Loop...")
    start_scalar = time.perf_counter()
    scalar_result = [0.0] * n_elements
    for i in range(n_elements):
        # Simulated R evaluator overhead: typecheck + dispatch
        val = data[i]
        if val > 0:
            scalar_result[i] = val * 2.5
        else:
            scalar_result[i] = 0.0
    time_scalar = time.perf_counter() - start_scalar

    # 2. Simulating C-level vectorized call (SIMD/Unrolled batch loop inside R kernel)
    print(f"{CLR_GREEN}[Running Simulation 2]{CLR_RESET} C-Vectorized Primitive Engine (Contiguous Array)...")
    start_vec = time.perf_counter()
    # Emulates native C: vector loop without AST traversal overhead
    vec_result = [x * 2.5 if x > 0 else 0.0 for x in data]
    time_vec = time.perf_counter() - start_vec

    speedup = time_scalar / time_vec if time_vec > 0 else float("inf")

    print("\n--- Benchmark Telemetry ---")
    print(f"  Interpreted Scalar Loop Time : {CLR_RED}{time_scalar * 1000:.2f} ms{CLR_RESET}")
    print(f"  Vectorized Kernel Time       : {CLR_GREEN}{time_vec * 1000:.2f} ms{CLR_RESET}")
    print(f"  Effective Vectorized Speedup : {CLR_BOLD}{CLR_CYAN}{speedup:.2f}x faster{CLR_RESET}")
    print(f"  Vector Integrity Check       : {'PASS' if scalar_result[:5] == vec_result[:5] else 'FAIL'}")


def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}R Internals Runtime Simulator: Data Types, Memory & Vectorization{CLR_RESET}")
    print(f"Platform Emulation: Standard GNU R 4.x SEXP Architecture on x86_64")
    
    lab_01_sexp_and_cow()
    lab_02_altrep_memory_optimization()
    lab_03_vectorization_engine()
    
    print(f"\n{CLR_GREEN}{CLR_BOLD}All Hands-on Lab Demonstrations Completed Successfully.{CLR_RESET}\n")


if __name__ == "__main__":
    main()