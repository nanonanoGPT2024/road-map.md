#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Fondasi Arsitektur Backend Lanjutan & Skalabilitas Sistem
Topik: BAB-10 - Arsitektur Skalabel, Rate Limiting, Consistent Hashing & Circuit Breaker
"""

import sys
import time
import hashlib
import random
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


class CircuitState(Enum):
    CLOSED = "CLOSED"        # Normal operation, traffic allowed
    OPEN = "OPEN"            # Failing, traffic short-circuited
    HALF_OPEN = "HALF_OPEN"  # Testing recovery with canary traffic


class ConsistentHashRing:
    """Implementasi Consistent Hashing Ring dengan Virtual Nodes."""

    def __init__(self, replicas: int = 3):
        self.replicas = replicas
        self.ring: Dict[int, str] = {}
        self.sorted_keys: List[int] = []

    def _hash(self, key: str) -> int:
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    def add_node(self, node: str) -> None:
        for i in range(self.replicas):
            vnode_key = f"{node}#vnode{i}"
            h = self._hash(vnode_key)
            self.ring[h] = node
        self.sorted_keys = sorted(self.ring.keys())

    def remove_node(self, node: str) -> None:
        for i in range(self.replicas):
            vnode_key = f"{node}#vnode{i}"
            h = self._hash(vnode_key)
            self.ring.pop(h, None)
        self.sorted_keys = sorted(self.ring.keys())

    def get_node(self, key: str) -> Optional[str]:
        if not self.ring:
            return None
        h = self._hash(key)
        for ring_key in self.sorted_keys:
            if h <= ring_key:
                return self.ring[ring_key]
        return self.ring[self.sorted_keys[0]]


class TokenBucketRateLimiter:
    """Implementasi Algoritma Rate Limiting: Token Bucket."""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.time()

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def allow_request(self, tokens: int = 1) -> Tuple[bool, float]:
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, self.tokens
        return False, self.tokens


class CircuitBreaker:
    """Implementasi Pola Ketahanan Sistem: Circuit Breaker Pattern."""

    def __init__(self, failure_threshold: int = 3, recovery_time: float = 3.0):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, target_func, *args, **kwargs) -> Tuple[bool, str]:
        now = time.time()

        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time > self.recovery_time:
                self.state = CircuitState.HALF_OPEN
            else:
                return False, f"Fast-fail: Sirkuit OPEN (Short-circuit, sisa timeout {self.recovery_time - (now - self.last_failure_time):.1f}s)"

        try:
            success, message = target_func(*args, **kwargs)
            if success:
                self._handle_success()
                return True, message
            else:
                self._handle_failure()
                return False, message
        except Exception as exc:
            self._handle_failure()
            return False, f"Exception tertangkap: {str(exc)}"

    def _handle_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def _handle_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN


def simulate_consistent_hashing():
    print(f"\n{Color.CYAN}{Color.BOLD}=== SIMULASI 1: CONSISTENT HASHING DENGAN VIRTUAL NODES ==={Color.RESET}")
    print("Mendistribusikan request partition key ke server nodes secara deterministik...")

    ring = ConsistentHashRing(replicas=3)
    nodes = ["server-node-alpha", "server-node-beta", "server-node-gamma"]
    for node in nodes:
        ring.add_node(node)

    keys = [f"session_token_usr_{1000 + i}" for i in range(10)]
    distribution: Dict[str, List[str]] = {n: [] for n in nodes}

    print(f"\n{Color.YELLOW}[Tahap 1] Pemetaan Awal (3 Nodes):{Color.RESET}")
    for k in keys:
        target = ring.get_node(k)
        distribution[target].append(k)
        print(f"  {Color.GRAY}Key:{Color.RESET} {k:<25} -> {Color.GREEN}{target}{Color.RESET}")

    print(f"\n{Color.YELLOW}[Tahap 2] Dynamic Scaling (Menambahkan node delta):{Color.RESET}")
    ring.add_node("server-node-delta")
    nodes.append("server-node-delta")

    reassigned = 0
    for k in keys:
        new_target = ring.get_node(k)
        prev_target = [n for n, items in distribution.items() if k in items][0]
        if new_target != prev_target:
            reassigned += 1
            print(f"  {Color.MAGENTA}Key Terpindah:{Color.RESET} {k} [{prev_target} => {Color.BOLD}{new_target}{Color.RESET}]")

    print(f"\n{Color.BOLD}Hasil Efisiensi Sharding:{Color.RESET} Hanya {reassigned}/{len(keys)} keys dipindahkan saat horizontal scaling!")


def simulate_rate_limiting():
    print(f"\n{Color.CYAN}{Color.BOLD}=== SIMULASI 2: TOKEN BUCKET RATE LIMITER ==={Color.RESET}")
    print("Konfigurasi: Kapasitas Bucket = 5 Token, Refill Rate = 2 Token/detik.")
    limiter = TokenBucketRateLimiter(capacity=5, refill_rate=2.0)

    print(f"\n{Color.YELLOW}Mengirim 8 request berturut-turut (Burst Traffic):{Color.RESET}")
    for req_id in range(1, 9):
        allowed, remaining = limiter.allow_request(1)
        if allowed:
            print(f"  Req #{req_id}: {Color.GREEN}[ACCEPTED]{Color.RESET} Sisa token: {remaining:.2f}")
        else:
            print(f"  Req #{req_id}: {Color.RED}[THROTTLED/429 Too Many Requests]{Color.RESET} Token habis ({remaining:.2f})")
        time.sleep(0.1)

    print(f"\n{Color.YELLOW}Menunggu 1.5 detik agar bucket terisi kembali (refill)...{Color.RESET}")
    time.sleep(1.5)

    print(f"{Color.YELLOW}Mengirim 2 request berikutnya setelah cooldown:{Color.RESET}")
    for req_id in range(9, 11):
        allowed, remaining = limiter.allow_request(1)
        status = f"{Color.GREEN}[ACCEPTED]{Color.RESET}" if allowed else f"{Color.RED}[THROTTLED]{Color.RESET}"
        print(f"  Req #{req_id}: {status} Sisa token: {remaining:.2f}")


def simulate_circuit_breaker():
    print(f"\n{Color.CYAN}{Color.BOLD}=== SIMULASI 3: CIRCUIT BREAKER STATE MACHINE ==={Color.RESET}")
    print("Ambang batas kegagalan: 3 kali berturut-turut | Timeout pemulihan: 2.0 detik")
    cb = CircuitBreaker(failure_threshold=3, recovery_time=2.0)

    is_flaky = True

    def downstream_service(req_id: int) -> Tuple[bool, str]:
        if is_flaky:
            return False, f"Downstream database timeout pada Request #{req_id}"
        return True, f"Response 200 OK dari upstream microservice #{req_id}"

    print(f"\n{Color.YELLOW}[Tahap 1] Mengirim request ke downstream bermasalah:{Color.RESET}")
    for i in range(1, 6):
        success, msg = cb.call(downstream_service, i)
        state_color = Color.GREEN if cb.state == CircuitState.CLOSED else Color.RED
        print(f"  Req #{i}: [{state_color}Status: {cb.state.value}{Color.RESET}] -> {msg}")
        time.sleep(0.2)

    print(f"\n{Color.YELLOW}[Tahap 2] Memperbaiki downstream service & menunggu cooldown timeout...{Color.RESET}")
    is_flaky = False
    print("  Sleeping 2.1 detik...")
    time.sleep(2.1)

    print(f"\n{Color.YELLOW}[Tahap 3] Mengirim request canary saat transisi pemulihan:{Color.RESET}")
    for i in range(6, 9):
        success, msg = cb.call(downstream_service, i)
        state_color = Color.GREEN if cb.state == CircuitState.CLOSED else Color.YELLOW
        print(f"  Req #{i}: [{state_color}Status: {cb.state.value}{Color.RESET}] -> {msg}")
        time.sleep(0.3)


def print_menu():
    print(f"\n{Color.BLUE}{'=' * 65}{Color.RESET}")
    print(f"{Color.BOLD}   LAB SIMULATOR ARSITEKTUR BACKEND LANJUTAN & SKALABILITAS   {Color.RESET}")
    print(f"{Color.BLUE}{'=' * 65}{Color.RESET}")
    print(f"  {Color.CYAN}1.{Color.RESET} Consistent Hashing & Ring Rebalancing")
    print(f"  {Color.CYAN}2.{Color.RESET} Token Bucket Rate Limiting")
    print(f"  {Color.CYAN}3.{Color.RESET} Circuit Breaker Pattern & Self-Healing")
    print(f"  {Color.CYAN}4.{Color.RESET} Jalankan Seluruh Pengujian / Automated Verification")
    print(f"  {Color.CYAN}0.{Color.RESET} Keluar")
    print(f"{Color.BLUE}{'-' * 65}{Color.RESET}")


def run_automated_tests() -> bool:
    print(f"\n{Color.BOLD}{Color.MAGENTA}=== MENJALANKAN AUTOMATED VERIFICATION SUITE ==={Color.RESET}")
    
    # 1. Test Consistent Hash Ring
    ring = ConsistentHashRing(replicas=5)
    ring.add_node("nodeA")
    ring.add_node("nodeB")
    assigned = ring.get_node("user_test_99")
    assert assigned in ["nodeA", "nodeB"], "Consistent hashing gagal menetapkan node valid"
    print(f"  [{Color.GREEN}PASS{Color.RESET}] ConsistentHashRing hashing deterministik terverifikasi.")

    # 2. Test Rate Limiter
    limiter = TokenBucketRateLimiter(capacity=2, refill_rate=1.0)
    assert limiter.allow_request(1)[0] is True
    assert limiter.allow_request(1)[0] is True
    assert limiter.allow_request(1)[0] is False, "Rate limiter seharusnya menolak request ke-3"
    print(f"  [{Color.GREEN}PASS{Color.RESET}] TokenBucketRateLimiter throttling terverifikasi.")

    # 3. Test Circuit Breaker
    cb = CircuitBreaker(failure_threshold=2, recovery_time=0.5)
    cb.call(lambda: (False, "err"))
    cb.call(lambda: (False, "err"))
    assert cb.state == CircuitState.OPEN, "Circuit breaker seharusnya beralih ke OPEN"
    time.sleep(0.6)
    cb.call(lambda: (True, "ok"))
    assert cb.state == CircuitState.CLOSED, "Circuit breaker seharusnya kembali CLOSED setelah sukses"
    print(f"  [{Color.GREEN}PASS{Color.RESET}] CircuitBreaker status transisi terverifikasi.")

    print(f"\n{Color.GREEN}{Color.BOLD}>>> SELURUH TES OTOMATIS BERHASIL (100% VALID) <<<{Color.RESET}\n")
    return True


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "-t", "test"):
        run_automated_tests()
        sys.exit(0)

    while True:
        print_menu()
        try:
            choice = input(f"{Color.BOLD}Pilih opsi [0-4]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Sesi lab dihentikan.{Color.RESET}")
            break

        if choice == "1":
            simulate_consistent_hashing()
        elif choice == "2":
            simulate_rate_limiting()
        elif choice == "3":
            simulate_circuit_breaker()
        elif choice == "4":
            simulate_consistent_hashing()
            simulate_rate_limiting()
            simulate_circuit_breaker()
            run_automated_tests()
        elif choice == "0":
            print(f"{Color.GREEN}Lab selesai. Sampai jumpa!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")


if __name__ == "__main__":
    main()
