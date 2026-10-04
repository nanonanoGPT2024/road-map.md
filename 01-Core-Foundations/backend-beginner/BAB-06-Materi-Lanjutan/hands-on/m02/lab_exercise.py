#!/usr/bin/env python3
"""
Lab Hands-on: Bab 06 - Data Access Patterns & Manajemen Koneksi (Deep Dive)
Modul 02: Thread-Safe Database Connection Pool Engine & Lifecycle Management

Script ini mensimulasikan mekanisme internal Connection Pool pada backend server:
1. Pool Initialization & Lazy Resource Allocation.
2. Thread-Safe Borrow & Release cycle menggunakan Semaphore dan Queue.
3. Connection Health Check & Auto-Eviction (TTL & Stale Ping).
4. Backpressure handling saat traffic spike (Timeout & Pool Exhaustion).
5. Context Manager idiom untuk mencegah Connection Leak.
"""

import time
import random
import threading
import queue
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

# ANSI Color formatting untuk output terminal terstruktur
class TermColor:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"


@dataclass
class ConnectionConfig:
    host: str = "cluster-db-primary.internal"
    port: int = 5432
    max_lifetime_sec: float = 4.0  # Max TTL sebelum connection dianggap stale


class MockDBConnection:
    """
    Representasi koneksi TCP/Socket ke database engine.
    Memiliki lifecycle internal: created, active, idle, dan expired/closed.
    """
    def __init__(self, conn_id: int, config: ConnectionConfig):
        self.conn_id = conn_id
        self.config = config
        self.created_at = time.time()
        self.last_used_at = self.created_at
        self.is_connected = True
        self._simulate_handshake()

    def _simulate_handshake(self) -> None:
        # Simulasi TCP 3-Way Handshake + SSL + Auth overhead
        time.sleep(0.08)

    def ping(self) -> bool:
        """Memeriksa apakah koneksi fisik masih responsif."""
        if not self.is_connected:
            return False
        # Evaluasi TTL connection
        age = time.time() - self.created_at
        return age < self.config.max_lifetime_sec

    def execute(self, query: str, execution_time: float) -> str:
        """Simulasi eksekusi payload SQL over network."""
        if not self.is_connected:
            raise ConnectionError(f"Conn #{self.conn_id} disconnected!")
        time.sleep(execution_time)
        self.last_used_at = time.time()
        return f"OK [Result of '{query}']"

    def terminate(self) -> None:
        self.is_connected = False


class ConnectionPoolExhausted(Exception):
    """Dilempar ketika waktu tunggu connection melampaui timeout batas toleransi."""
    pass


class DatabaseConnectionPool:
    """
    Enterprise-grade Thread-Safe Connection Pool.
    Menerapkan model Object Pool dengan boundary control dan proactive eviction.
    """
    def __init__(self, min_size: int, max_size: int, acquire_timeout: float):
        self.min_size = min_size
        self.max_size = max_size
        self.acquire_timeout = acquire_timeout
        self.config = ConnectionConfig()

        self._pool: queue.Queue[MockDBConnection] = queue.Queue(maxsize=max_size)
        self._lock = threading.Lock()
        self._current_total = 0
        self._conn_id_counter = 0

        # Metrik operasional
        self.stats_acquired = 0
        self.stats_timeouts = 0
        self.stats_recreated = 0

        self._initialize_warm_pool()

    def _create_new_connection(self) -> MockDBConnection:
        with self._lock:
            self._conn_id_counter += 1
            self._current_total += 1
            cid = self._conn_id_counter
        return MockDBConnection(cid, self.config)

    def _initialize_warm_pool(self) -> None:
        """Warm-up pool: Menyiapkan koneksi minimum di awal."""
        print(f"{TermColor.CYAN}[POOL INIT] Melakukan warming up {self.min_size} koneksi awal...{TermColor.RESET}")
        for _ in range(self.min_size):
            conn = self._create_new_connection()
            self._pool.put(conn)

    def acquire(self) -> MockDBConnection:
        """
        Mengambil koneksi idle dari pool. Jika kosong dan kapasitas masih ada,
        buat koneksi baru. Jika kapasitas penuh, tunggu hingga acquire_timeout.
        """
        start_time = time.time()

        # Strategi 1: Coba ambil instance yang idle tanpa blocking
        try:
            conn = self._pool.get_nowait()
            return self._validate_and_recycle(conn)
        except queue.Empty:
            pass

        # Strategi 2: Jika pool kosong, coba alokasikan slot baru secara on-demand
        with self._lock:
            if self._current_total < self.max_size:
                conn = self._create_new_connection()
                self.stats_acquired += 1
                return conn

        # Strategi 3: Pool fully saturated, thread masuk waiting state (blocking queue)
        remaining_timeout = self.acquire_timeout - (time.time() - start_time)
        if remaining_timeout <= 0:
            self.stats_timeouts += 1
            raise ConnectionPoolExhausted(f"Timeout {self.acquire_timeout}s tercapai: Pool jenuh!")

        try:
            conn = self._pool.get(timeout=remaining_timeout)
            return self._validate_and_recycle(conn)
        except queue.Empty:
            self.stats_timeouts += 1
            raise ConnectionPoolExhausted(f"Timeout {self.acquire_timeout}s tercapai: Antrean gagal dipenuhi!")

    def _validate_and_recycle(self, conn: MockDBConnection) -> MockDBConnection:
        """Pemeriksaan kesehatan koneksi sebelum diserahkan ke consumer."""
        if not conn.ping():
            # Koneksi kadaluarsa/rusak, hancurkan dan gantikan yang segar
            conn.terminate()
            self.stats_recreated += 1
            print(f"{TermColor.YELLOW}[EVICT] Conn #{conn.conn_id} stale/expired. Reconnecting...{TermColor.RESET}")
            with self._lock:
                self._current_total -= 1
            conn = self._create_new_connection()

        self.stats_acquired += 1
        return conn

    def release(self, conn: MockDBConnection) -> None:
        """Mengembalikan koneksi ke pool agar reusable."""
        if conn.is_connected:
            try:
                self._pool.put_nowait(conn)
            except queue.Full:
                # Surplus koneksi jika konfigurasi dinamis berubah, buang koneksi
                conn.terminate()
                with self._lock:
                    self._current_total -= 1
        else:
            with self._lock:
                self._current_total -= 1

    @contextmanager
    def connection(self):
        """Pattern Context Manager: Menjamin determinisme rilis koneksi (Resource Safety)."""
        conn = self.acquire()
        try:
            yield conn
        finally:
            self.release(conn)

    def print_status(self) -> None:
        with self._lock:
            idle = self._pool.qsize()
            active = self._current_total - idle
            print(f"{TermColor.MAGENTA}[METRIC] Total: {self._current_total}/{self.max_size} | "
                  f"Active: {active} | Idle: {idle}{TermColor.RESET}")


def worker_task(worker_id: int, pool: DatabaseConnectionPool, query_duration: float):
    """Simulasi consumer worker API request yang butuh database access."""
    tag = f"Worker-{worker_id:02d}"
    print(f"{TermColor.BLUE}[{tag}] Mencoba meminjam koneksi...{TermColor.RESET}")

    start_wait = time.time()
    try:
        # Context manager menjamin conn.release() selalu dieksekusi walau error
        with pool.connection() as conn:
            wait_time = time.time() - start_wait
            print(f"{TermColor.GREEN}[{tag}] Berhasil pinjam Conn #{conn.conn_id} (Antre: {wait_time:.3f}s){TermColor.RESET}")
            
            # Simulasi eksekusi I/O ke DB
            result = conn.execute(f"SELECT * FROM users WHERE id = {worker_id}", query_duration)
            print(f"{TermColor.BOLD}[{tag}] Query Berhasil: {result}{TermColor.RESET}")

    except ConnectionPoolExhausted as ex:
        print(f"{TermColor.RED}[{tag}] GAGAL: {ex}{TermColor.RESET}")


def main():
    print(f"{TermColor.BOLD}=== SIMULASI ADVANCED DATA ACCESS & CONNECTION MANAGEMENT ==={TermColor.RESET}")
    print("Skenario: 10 Concurrent Request bersaing memperebutkan max 4 Connection Slots.")
    print("Pool Timeout: 0.8s | Max Lifetime: 4.0s (Auto-Eviction Demo)\n")

    # Inisialisasi pool terbatas: Min 2, Max 4, Timeout 0.8s
    pool = DatabaseConnectionPool(min_size=2, max_size=4, acquire_timeout=0.8)
    pool.print_status()
    print("-" * 75)

    workers = []
    # Jalankan burst 10 concurrent workers
    for wid in range(1, 11):
        # Durasi query acak antara 0.2 hingga 0.6 detik
        dur = random.uniform(0.25, 0.60)
        t = threading.Thread(target=worker_task, args=(wid, pool, dur))
        workers.append(t)

    for t in workers:
        t.start()
        time.sleep(0.04)  # Small realistic staggered incoming arrival

    # Tunggu seluruh worker batch 1 selesai
    for t in workers:
        t.join()

    print("-" * 75)
    print(f"{TermColor.CYAN}[STAGE 2] Mensimulasikan Sleep untuk menguji TTL Connection Eviction...{TermColor.RESET}")
    time.sleep(4.2)  # Menunggu melampaui ConnectionConfig.max_lifetime_sec (4.0 detik)

    print(f"{TermColor.CYAN}[STAGE 2] Mengirim query baru pada koneksi yang sudah stale...{TermColor.RESET}")
    stale_test_worker = threading.Thread(target=worker_task, args=(99, pool, 0.1))
    stale_test_worker.start()
    stale_test_worker.join()

    print("\n" + "=" * 75)
    print(f"{TermColor.BOLD}RINGKASAN METRIK PERFORMA POOL:{TermColor.RESET}")
    print(f"Total Operasi Pinjam Sukses  : {pool.stats_acquired}")
    print(f"Total Requests Ditolak/Timeout : {pool.stats_timeouts}")
    print(f"Total Stale Reconnect (Evicted): {pool.stats_recreated}")
    pool.print_status()
    print("=" * 75)


if __name__ == "__main__":
    main()
