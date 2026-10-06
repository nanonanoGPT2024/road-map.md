#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Arsitektur Backend Tingkat Lanjut & Skalabilitas Sistem
BAB-10: Arsitektur Backend Lanjutan dan Skalabilitas Sistem

Topik yang disimulasikan:
1. Rate Limiting (Token Bucket Algorithm)
2. Circuit Breaker Pattern (Closed -> Open -> Half-Open)
3. Consistent Hashing (Sharding & Load Balancing)
4. Cache-Aside Pattern dengan Invalidation Strategy
"""

import hashlib
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ANSI Escape Sequences untuk Pewarnaan Terminal
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_RED = "\033[41m"


def header(text: str) -> None:
    print(f"\n{BOLD}{BG_BLUE}{WHITE} === {text} === {RESET}\n")


def log_info(msg: str) -> None:
    print(f"{CYAN}[INFO]{RESET} {msg}")


def log_success(msg: str) -> None:
    print(f"{GREEN}[SUCCESS]{RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"{RED}[ERROR]{RESET} {msg}")


# ==============================================================================
# 1. TOKEN BUCKET RATE LIMITER
# ==============================================================================
class TokenBucketRateLimiter:
    """Implementasi algoritma Token Bucket per Client IP/ID."""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = float(capacity)
        self.refill_rate = refill_rate  # tokens per second
        self.tokens: Dict[str, float] = defaultdict(lambda: float(capacity))
        self.last_refill: Dict[str, float] = defaultdict(time.time)

    def _refill(self, client_id: str) -> None:
        now = time.time()
        elapsed = now - self.last_refill[client_id]
        new_tokens = elapsed * self.refill_rate
        self.tokens[client_id] = min(self.capacity, self.tokens[client_id] + new_tokens)
        self.last_refill[client_id] = now

    def allow_request(self, client_id: str, cost: float = 1.0) -> Tuple[bool, float]:
        self._refill(client_id)
        if self.tokens[client_id] >= cost:
            self.tokens[client_id] -= cost
            return True, self.tokens[client_id]
        return False, self.tokens[client_id]


# ==============================================================================
# 2. CIRCUIT BREAKER
# ==============================================================================
class CircuitState(Enum):
    CLOSED = "CLOSED"        # Normal: Lalu lintas diteruskan ke upstream
    OPEN = "OPEN"            # Degradasi: Memblokir request cepat (fast-fail)
    HALF_OPEN = "HALF_OPEN"  # Pemulihan: Menguji coba trafik terbatas


class CircuitBreaker:
    """Circuit Breaker untuk melindungi sistem hilir dari cascading failure."""

    def __init__(self, failure_threshold: int = 3, recovery_time: float = 4.0):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time: Optional[float] = None
        self.success_count_in_half_open = 0

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.success_count_in_half_open += 1
            if self.success_count_in_half_open >= 2:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count_in_half_open = 0
                log_success("Circuit Breaker beralih kembali ke status [CLOSED]. Layanan sehat!")
        else:
            self.failure_count = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            log_error("Probe request gagal pada HALF_OPEN! Sirkuit kembali [OPEN].")
        elif self.failure_count >= self.failure_threshold and self.state == CircuitState.CLOSED:
            self.state = CircuitState.OPEN
            log_warn(f"Ambang batas kegagalan tercapai ({self.failure_count}). Sirkuit beralih ke [OPEN]!")

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time >= self.recovery_time):
                self.state = CircuitState.HALF_OPEN
                self.success_count_in_half_open = 0
                log_info("Recovery time habis. Sirkuit beralih ke [HALF_OPEN] untuk pengujian.")
                return True
            return False
        return True  # HALF_OPEN allows testing


# ==============================================================================
# 3. CONSISTENT HASHING
# ==============================================================================
class ConsistentHashRing:
    """Ring Consistent Hashing dengan Virtual Nodes untuk distribusi beban merata."""

    def __init__(self, replicas: int = 3):
        self.replicas = replicas
        self.ring: Dict[int, str] = {}
        self.sorted_keys: List[int] = []

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % (2**32)

    def add_node(self, node: str) -> None:
        for i in range(self.replicas):
            virtual_key = f"{node}#vnode{i}"
            h = self._hash(virtual_key)
            self.ring[h] = node
            self.sorted_keys.append(h)
        self.sorted_keys.sort()
        log_info(f"Node Database '{node}' ditambahkan ke Hash Ring ({self.replicas} virtual nodes).")

    def remove_node(self, node: str) -> None:
        for i in range(self.replicas):
            virtual_key = f"{node}#vnode{i}"
            h = self._hash(virtual_key)
            if h in self.ring:
                del self.ring[h]
                self.sorted_keys.remove(h)
        log_warn(f"Node Database '{node}' dilepas dari Hash Ring.")

    def get_node(self, key: str) -> Optional[str]:
        if not self.ring:
            return None
        h = self._hash(key)
        for ring_key in self.sorted_keys:
            if h <= ring_key:
                return self.ring[ring_key]
        return self.ring[self.sorted_keys[0]]


# ==============================================================================
# 4. DISTRIBUTED CACHE-ASIDE SIMULATOR
# ==============================================================================
class CacheAsideStore:
    """Simulasi Cache-Aside Pattern dengan TTL dan Invalidation."""

    def __init__(self):
        self.cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expiry)
        self.database: Dict[str, Any] = {
            "user:101": {"id": 101, "name": "Budi Rahardjo", "role": "Architect"},
            "user:102": {"id": 102, "name": "Siti Nurhaliza", "role": "Principal Engineer"},
            "user:103": {"id": 103, "name": "Ahmad Dani", "role": "SRE Lead"},
        }

    def get(self, key: str, ttl: float = 3.0) -> Tuple[Any, str]:
        now = time.time()
        if key in self.cache:
            val, expiry = self.cache[key]
            if now < expiry:
                return val, "CACHE_HIT"
            else:
                del self.cache[key]

        # Cache Miss: Ambil dari DB lalu isi cache
        if key in self.database:
            val = self.database[key]
            self.cache[key] = (val, now + ttl)
            return val, "CACHE_MISS"
        return None, "NOT_FOUND"

    def write_update(self, key: str, new_data: Any) -> None:
        self.database[key] = new_data
        if key in self.cache:
            del self.cache[key]
            log_warn(f"Cache Invalidation dilakukan untuk key '{key}'.")


# ==============================================================================
# INTERACTIVE SIMULATION RUNNER
# ==============================================================================
def demo_rate_limiter() -> None:
    header("1. SIMULASI RATE LIMITER (TOKEN BUCKET)")
    limiter = TokenBucketRateLimiter(capacity=4, refill_rate=1.5)
    client = "client-api-gateway"
    print(f"{DIM}Kapasitas: 4 token | Refill Rate: 1.5 token/detik{RESET}")

    for i in range(1, 9):
        allowed, remaining = limiter.allow_request(client)
        if allowed:
            log_success(f"Request #{i:02d} [DITERIMA] - Sisa Token: {remaining:.2f}")
        else:
            log_error(f"Request #{i:02d} [DITOLAK - 429 Too Many Requests] - Sisa Token: {remaining:.2f}")
        time.sleep(0.3)


def demo_circuit_breaker() -> None:
    header("2. SIMULASI RESILIENSI: CIRCUIT BREAKER PATTERN")
    cb = CircuitBreaker(failure_threshold=3, recovery_time=2.0)

    # 1. Kirim beberapa request gagal
    for i in range(1, 5):
        if cb.can_execute():
            log_info(f"Mengirim RPC request #{i} ke microservice pembayaran (State: {cb.state.value})...")
            cb.record_failure()
        else:
            log_error(f"Request #{i} [FAIL-FAST] Diblokir oleh Circuit Breaker (State: {cb.state.value})!")
        time.sleep(0.4)

    log_warn("Menunggu waktu pemulihan (recovery time 2 detik)...")
    time.sleep(2.2)

    # 2. Transisi ke Half-Open dan Pemulihan
    for i in range(5, 8):
        if cb.can_execute():
            log_info(f"Mengirim probe request #{i} (State: {cb.state.value})...")
            cb.record_success()
        else:
            log_error(f"Request #{i} diblokir!")
        time.sleep(0.3)


def demo_consistent_hashing() -> None:
    header("3. SIMULASI SHARDING DATA: CONSISTENT HASH RING")
    ring = ConsistentHashRing(replicas=3)
    nodes = ["shard-us-east", "shard-eu-west", "shard-ap-southeast"]

    for n in nodes:
        ring.add_node(n)

    sample_keys = [f"session_{idx}" for idx in range(1001, 1009)]
    distribution: Dict[str, List[str]] = defaultdict(list)

    print(f"\n{BOLD}Pemetaan Kunci Sesi ke Partisi/Shard:{RESET}")
    for k in sample_keys:
        target = ring.get_node(k)
        if target:
            distribution[target].append(k)
            print(f"  {CYAN}{k}{RESET} -> {GREEN}{target}{RESET}")

    # Simulasi kegagalan node (scale-down)
    print(f"\n{YELLOW}>> Simulasi Node 'shard-eu-west' mengalami failover / dekomisioning...{RESET}")
    ring.remove_node("shard-eu-west")

    print(f"\n{BOLD}Pemetaan Ulang Pasca-Failover:{RESET}")
    for k in sample_keys[:4]:
        new_target = ring.get_node(k)
        print(f"  {CYAN}{k}{RESET} sekarang terarah ke -> {MAGENTA}{new_target}{RESET}")


def demo_cache_aside() -> None:
    header("4. SIMULASI STRATEGI CACHE-ASIDE & INVALIDATION")
    store = CacheAsideStore()
    target_key = "user:101"

    print(f"{DIM}Mengakses data '{target_key}' pertama kali (Cold Cache)...{RESET}")
    data, status = store.get(target_key, ttl=1.5)
    log_info(f"Status: {YELLOW}{status}{RESET} -> Mengambil dari DB: {data}")

    print(f"\n{DIM}Mengakses data '{target_key}' kedua kali (Hot Cache)...{RESET}")
    data, status = store.get(target_key, ttl=1.5)
    log_success(f"Status: {GREEN}{status}{RESET} -> Respons ultra-cepat dari In-Memory Cache: {data}")

    print(f"\n{DIM}Memperbarui data profil di Master DB...{RESET}")
    store.write_update(target_key, {"id": 101, "name": "Budi Rahardjo", "role": "VP of Architecture"})

    print(f"\n{DIM}Mengakses kembali pasca-invalidation...{RESET}")
    data, status = store.get(target_key, ttl=1.5)
    log_info(f"Status: {YELLOW}{status}{RESET} -> Data baru dimuat ulang ke Cache: {data}")


def main_menu() -> None:
    while True:
        print("\n" + "=" * 65)
        print(f"{BOLD}{MAGENTA}LAB ARSITEKTUR BACKEND LANJUTAN & SKALABILITAS SISTEM (M02){RESET}")
        print("=" * 65)
        print(f"{CYAN}1.{RESET} Jalankan Simulasi Token Bucket Rate Limiter")
        print(f"{CYAN}2.{RESET} Jalankan Simulasi Circuit Breaker Pattern")
        print(f"{CYAN}3.{RESET} Jalankan Simulasi Consistent Hashing & Sharding")
        print(f"{CYAN}4.{RESET} Jalankan Simulasi Cache-Aside & Invalidation")
        print(f"{CYAN}5.{RESET} Jalankan Seluruh Skenario Produksi (End-to-End Test)")
        print(f"{RED}0.{RESET} Keluar")
        print("-" * 65)

        try:
            choice = input(f"{BOLD}Pilih skenario simulasi [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Simulasi dihentikan.{RESET}")
            break

        if choice == "1":
            demo_rate_limiter()
        elif choice == "2":
            demo_circuit_breaker()
        elif choice == "3":
            demo_consistent_hashing()
        elif choice == "4":
            demo_cache_aside()
        elif choice == "5":
            demo_rate_limiter()
            demo_circuit_breaker()
            demo_consistent_hashing()
            demo_cache_aside()
            log_success("Seluruh skenario arsitektur berhasil dijalankan!")
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah menjalankan lab arsitektur backend lanjutan.{RESET}")
            break
        else:
            log_error("Pilihan tidak valid, silakan masukkan angka antara 0 hingga 5.")


if __name__ == "__main__":
    # Jika dijalankan secara non-interaktif (piped/CI), jalankan mode otomatis
    if not sys.stdin.isatty():
        demo_rate_limiter()
        demo_circuit_breaker()
        demo_consistent_hashing()
        demo_cache_aside()
        log_success("Eksekusi batch headless selesai dengan sukses.")
    else:
        main_menu()
