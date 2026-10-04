#!/usr/bin/env python3
"""
Lab Hands-on: Java Concurrency & Multithreading Mendalam (Deep Dive)
Simulasi Internal JVM: Memory Model (JMM), CAS (Atomic Operations), 
ReentrantLock, Monitor Object Pattern, dan Bounded ThreadPoolExecutor.
"""

import time
import threading
from collections import deque
import random
import sys

# ANSI Escape Colors untuk output terminal terstruktur
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_CYAN = "\033[36m"
CLR_MAGENTA = "\033[35m"


class SimulatedAtomicInteger:
    """
    Simulasi java.util.concurrent.atomic.AtomicInteger.
    Memodelkan instruksi CPU Compare-And-Swap (CAS) seperti cmpxchg pada arsitektur x86.
    """
    def __init__(self, initial_value: int = 0):
        self._value = initial_value
        self._lock = threading.Lock()  # Mengemulasikan hardware-level bus/cache lock

    def get(self) -> int:
        with self._lock:
            return self._value

    def compare_and_set(self, expect: int, update: int) -> bool:
        """Hardware CAS abstraction: atomik update jika nilai memori sama dengan ekspektasi."""
        with self._lock:
            if self._value == expect:
                self._value = update
                return True
            return False

    def increment_and_get(self) -> int:
        """Lock-free retry loop (CAS spin-loop idiomatik Java)."""
        while True:
            current = self.get()
            next_val = current + 1
            if self.compare_and_set(current, next_val):
                return next_val

    def add_and_get(self, delta: int) -> int:
        while True:
            current = self.get()
            next_val = current + delta
            if self.compare_and_set(current, next_val):
                return next_val


class JavaCountDownLatch:
    """
    Simulasi java.util.concurrent.CountDownLatch.
    Sinkronisasi primitif berbasis AbstractQueuedSynchronizer (AQS).
    """
    def __init__(self, count: int):
        self.count = count
        self._condition = threading.Condition()

    def count_down(self):
        with self._condition:
            if self.count > 0:
                self.count -= 1
                if self.count == 0