#!/usr/bin/env python3
"""
Lab Exercise: Golang Production Hardening, Security, and SRE Practices Simulation
Bab 10 - Production Hardening, Security & SRE Practices

Modul simulasi interaktif Python 3 mandiri untuk memvisualisasikan arsitektur
keandalan (SRE) dan pengerasan keamanan (Security Hardening) pada backend microservice Go:
1. HTTP Server Timeout & Slowloris Attack Mitigation (net/http hardening)
2. Token Bucket Rate Limiting (golang.org/x/time/rate idiom)
3. Circuit Breaker Pattern & Kubernetes Probes (/livez, /readyz)
4. Graceful Shutdown & Context Cancellation Draining (os.Signal + context.WithTimeout)
5. Comprehensive SRE Chaos Test & Audit Matrix
"""

import sys
import time
import random
import threading
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional

# --- ANSI Color Palette ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_WHITE   = "\033[37m"
CLR_BG_DARK = "\033[40m"

def log_go(level: str, msg: str, **kwargs):
    """Format structured logging similar to Go slog package."""
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    lvl_color = CLR_WHITE
    if level == "INFO":
        lvl_color = CLR_GREEN
    elif level == "WARN":
        lvl_color = CLR_YELLOW
    elif level == "ERROR":
        lvl_color = CLR_RED
    elif level == "DEBUG":
        lvl_color = CLR_CYAN

    attrs = " ".join([f"{CLR_BLUE}{k}{CLR_RESET}={v}" for k, v in kwargs.items()])
    print(f"{CLR_WHITE}[{timestamp}]{CLR_RESET} {lvl_color}{level:<5}{CLR_RESET} {CLR_BOLD}{msg:<35}{CLR_RESET} {attrs}")

def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}================================================================================
  GOLANG SRE & PRODUCTION HARDENING SIMULATOR (BAB 10)
  Resilience Engineering, Security Hardening & Zero-Downtime Architecture
================================================================================{CLR_RESET}
"""
    print(banner)

# ==============================================================================
# 1. HTTP TIMEOUT HARDENING & SLOWLORIS DEFENSE (net/http)
# ==============================================================================
@dataclass
class HTTPServerConfig:
    read_header_timeout: float = 2.0  # Go: http.Server.ReadHeaderTimeout
    read_timeout: float = 5.0         # Go: http.Server.ReadTimeout
    write_timeout: float = 10.0       # Go: http.Server.WriteTimeout
    idle_timeout: float = 30.0        # Go: http.Server.IdleTimeout
    max_header_bytes: int = 1 << 20   # 1 MB default

def simulate_slowloris_mitigation():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}--- [1] SIMULASI: HTTP Server Timeout & Slowloris Defense ---{CLR_RESET}")
    print(f"{CLR_YELLOW}Konsep Go:{CLR_RESET} Mengabaikan `ReadHeaderTimeout` membuka celah Slowloris attack di mana")
    print("penyerang mengirim byte header HTTP secara sangat lambat untuk menghabiskan file descriptor.\n")

    cfg = HTTPServerConfig(read_header_timeout=1.5, write_timeout=3.0)
    log_go("INFO", "server_configured", read_header_timeout=f"{cfg.read_header_timeout}s", write_timeout=f"{cfg.write_timeout}s")

    scenarios = [
        {"client": "Valid-Microservice-Req", "send_delay": 0.3, "headers": "Complete"},
        {"client": "Slowloris-Attacker-Node", "send_delay": 2.5, "headers": "Partial (Slow drip)"},
        {"client": "Batch-Worker-Upload", "send_delay": 0.8, "headers": "Complete"}
    ]

    for req in scenarios:
        client = req["client"]
        delay = req["send_delay"]
        print(f"\n{CLR_CYAN}--> Menghubungkan client [{client}] (Delay header: {delay}s)...{CLR_RESET}")
        time.sleep(0.4)

        if delay > cfg.read_header_timeout:
            log_go("WARN", "read_header_timeout_exceeded", client=client, elapsed=f"{delay}s", threshold=f"{cfg.read_header_timeout}s")
            print(f"{CLR_RED}[BLOCKED]{CLR_RESET} Koneksi diputus seketika: {CLR_YELLOW}net/http: TLS handshake / header read deadline exceeded (408 Request Timeout){CLR_RESET}")
        else:
            log_go("INFO", "http_request_accepted", client=client, elapsed=f"{delay}s", status="200 OK")
            print(f"{CLR_GREEN}[SUCCESS]{CLR_RESET} Permintaan diproses oleh goroutine worker.")

# ==============================================================================
# 2. TOKEN BUCKET RATE LIMITING (golang.org/x/time/rate)
# ==============================================================================
class TokenBucketLimiter:
    """Simulasi rate.NewLimiter(rate.Limit(r), b) di Go"""
    def __init__(self, refill_rate: float, burst_capacity: int):
        self.rate = refill_rate          # token per detik
        self.capacity = burst_capacity   # burst max
        self.tokens = float(burst_capacity)
        self.last_update = time.time()
        self.lock = threading.Lock()

    def allow(self) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.last_update = now

            # Isi ulang token sesuai waktu yang berlalu
            self.tokens = min(self.capacity, self.tokens + (elapsed * self.rate))

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False

def simulate_rate_limiter():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}--- [2] SIMULASI: Token Bucket Rate Limiter (golang.org/x/time/rate) ---{CLR_RESET}")
    print(f"{CLR_YELLOW}Konsep Go:{CLR_RESET} Perlindungan DoS & noisy-neighbor menggunakan algoritma Token Bucket")
    print("dengan parameter `r` (refill rate/sec) dan `b` (burst capacity).\n")

    limiter = TokenBucketLimiter(refill_rate=3.0, burst_capacity=5)
    log_go("INFO", "rate_limiter_initialized", refill_rate="3 req/sec", burst_capacity="5 tokens")

    total_requests = 12
    accepted = 0
    rejected = 0

    print(f"{CLR_CYAN}Menjalankan lonjakan (burst) 12 request berturut-turut:{CLR_RESET}")
    for i in range(1, total_requests + 1):
        time.sleep(0.18)  # request datang sangat rapat
        if limiter.allow():
            accepted += 1
            log_go("INFO", "request_allowed", req_id=f"req-{i:02d}", tokens_left=f"{limiter.tokens:.1f}")
        else:
            rejected += 1
            log_go("ERROR", "rate_limit_exceeded", req_id=f"req-{i:02d}", status="429 Too Many Requests")

    print(f"\n{CLR_BOLD}Hasil Simulasi Rate Limiting:{CLR_RESET}")
    print(f"Total: {total_requests} | {CLR_GREEN}Diterima: {accepted}{CLR_RESET} | {CLR_RED}Ditolak (429): {rejected}{CLR_RESET}")
    print(f"{CLR_BLUE}Kompensasi Otomatis:{CLR_RESET} 5 token pertama diloloskan instan (Burst), sisanya dibatasi 3 req/detik.")

# ==============================================================================
# 3. CIRCUIT BREAKER & KUBERNETES PROBES (/livez, /readyz)
# ==============================================================================
class CircuitState(Enum):
    CLOSED = "CLOSED (Normal Operation)"
    OPEN = "OPEN (Fast Failing / Tripped)"
    HALF_OPEN = "HALF-OPEN (Canary Probing)"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 2.0):
        self.state = CircuitState.CLOSED
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0

    def record_result(self, success: bool):
        now = time.time()
        if success:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                log_go("INFO", "circuit_breaker_recovered", state=self.state.value)
        else:
            self.failure_count += 1
            self.last_failure_time = now
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                log_go("WARN", "circuit_breaker_tripped", failures=self.failure_count, state=self.state.value)

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if (time.time() - self.last_failure_time) > self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                log_go("INFO", "circuit_breaker_probing", state=self.state.value)
                return True
            return False
        return True  # HALF_OPEN allows single canary probe

def simulate_circuit_breaker_probes():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}--- [3] SIMULASI: Circuit Breaker & Health Probes (/livez & /readyz) ---{CLR_RESET}")
    print(f"{CLR_YELLOW}Konsep Go:{CLR_RESET} Pola circuit breaker mencegah cascading failure ke upstream database.")
    print("K8s /livez menandakan runtime hidup, /readyz menandakan siap menerima traffic.\n")

    cb = CircuitBreaker(failure_threshold=3, reset_timeout=1.5)

    # 1. Healthy state
    log_go("INFO", "probe_check", endpoint="/livez", status="200 OK (Process Alive)")
    log_go("INFO", "probe_check", endpoint="/readyz", status="200 OK (Ready for Traffic)")

    print(f"\n{CLR_CYAN}Simulasi gangguan konektivitas database downstream...{CLR_RESET}")
    for cycle in range(1, 6):
        time.sleep(0.3)
        if not cb.can_execute():
            print(f"[{CLR_RED}FAIL FAST{CLR_RESET}] Circuit OPEN -> Menolak request tanpa membebani database!")
            log_go("WARN", "probe_check", endpoint="/readyz", status="503 Service Unavailable (Circuit OPEN)")
            continue

        # Simulasikan kegagalan database
        success = False
        cb.record_result(success)
        log_go("ERROR", "db_query_failed", attempt=cycle, error="connection timeout: 5432")

    print(f"\n{CLR_YELLOW}Menunggu masa pemulihan ({cb.reset_timeout}s) untuk transisi HALF-OPEN...{CLR_RESET}")
    time.sleep(cb.reset_timeout + 0.2)

    if cb.can_execute():
        print(f"[{CLR_GREEN}CANARY CHECK{CLR_RESET}] Mencoba 1 probe sehat ke database...")
        cb.record_result(True)
        log_go("INFO", "probe_check", endpoint="/readyz", status="200 OK (Traffic Restored)")

# ==============================================================================
# 4. GRACEFUL SHUTDOWN & IN-FLIGHT DRAINING (sync.WaitGroup + context)
# ==============================================================================
def simulate_graceful_shutdown():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}--- [4] SIMULASI: Graceful Shutdown & Context Drain ---{CLR_RESET}")
    print(f"{CLR_YELLOW}Konsep Go:{CLR_RESET} Menangkap sinyal OS (SIGINT/SIGTERM), menghentikan listener baru,")
    print("lalu memberikan waktu grace period (misal 5 detik) untuk menyelesaikan request aktif.\n")

    in_flight_tasks = ["payment-trx-901", "report-gen-104", "webhook-dispatch-42"]
    log_go("INFO", "server_running", active_goroutines=len(in_flight_tasks))
    for t in in_flight_tasks:
        print(f"  * Menjalankan goroutine: {CLR_CYAN}{t}{CLR_RESET}")

    time.sleep(0.5)
    print(f"\n{CLR_RED}{CLR_BOLD}[!] Menerima Sinyal OS: SIGTERM (Kubernetes Pod Deletion / Rolling Upgrade){CLR_RESET}")
    log_go("WARN", "signal_received", signal="SIGTERM", action="initiating_graceful_shutdown")

    grace_period = 3.0
    log_go("INFO", "context_deadline_set", timeout=f"{grace_period}s", helper="http.Server.Shutdown(ctx)")

    # Draining tasks
    for idx, task in enumerate(in_flight_tasks, 1):
        drain_time = 0.5 * idx
        time.sleep(drain_time)
        print(f"{CLR_GREEN}✔ Selesai:{CLR_RESET} {task} diselesaikan dalam {drain_time}s")

    log_go("INFO", "shutdown_complete", exit_code=0, message="All connections drained cleanly without dropped packets.")

# ==============================================================================
# 5. COMPREHENSIVE SRE CHAOS AUDIT MATRIX
# ==============================================================================
def run_chaos_audit_matrix():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}--- [5] COMPREHENSIVE SRE CHAOS & SECURITY AUDIT MATRIX ---{CLR_RESET}")
    audit_items = [
        ("TLS Configuration", "MinVersion: tls.VersionTLS13, Modern Ciphers Only", "PASS", CLR_GREEN),
        ("Slowloris Hardening", "ReadHeaderTimeout: 2s explicitly configured", "PASS", CLR_GREEN),
        ("Memory Allocations", "Buffer reuse via sync.Pool to minimize GC pauses", "PASS", CLR_GREEN),
        ("Panic Recovery", "Global Recovery Middleware with Structured Traceback", "PASS", CLR_GREEN),
        ("Secret Management", "Zero plain-text credentials in logs / memory wiping", "PASS", CLR_GREEN),
        ("Kubernetes Liveness", "Endpoint /livez decoupled from external downstream", "PASS", CLR_GREEN),
        ("Zero Downtime", "Graceful shutdown drains HTTP & gRPC connections", "PASS", CLR_GREEN),
    ]

    print(f"{'ITEM AUDIT':<25} | {'PARAMETER IMPLEMENTASI GOLANG':<45} | {'STATUS':<8}")
    print("-" * 84)
    for name, desc, status, clr in audit_items:
        time.sleep(0.15)
        print(f"{name:<25} | {desc:<45} | {clr}{CLR_BOLD}{status:<8}{CLR_RESET}")
    print("-" * 84)
    print(f"{CLR_GREEN}{CLR_BOLD}Audit Selesai: 7/7 Standar Production Hardening Terpenuhi (100% Reliability Target).{CLR_RESET}")

# ==============================================================================
# INTERACTIVE CLI INTERFACE
# ==============================================================================
def display_menu():
    print(f"\n{CLR_WHITE}{CLR_BOLD}Pilih Modul Simulasi SRE & Hardening:{CLR_RESET}")
    print(f"  {CLR_CYAN}[1]{CLR_RESET} HTTP Timeout & Slowloris Attack Defense")
    print(f"  {CLR_CYAN}[2]{CLR_RESET} Token Bucket Rate Limiting (golang.org/x/time/rate)")
    print(f"  {CLR_CYAN}[3]{CLR_RESET} Circuit Breaker & Health Probes (/livez & /readyz)")
    print(f"  {CLR_CYAN}[4]{CLR_RESET} Graceful Shutdown & Goroutine In-Flight Draining")
    print(f"  {CLR_CYAN}[5]{CLR_RESET} Jalankan Comprehensive SRE Audit Matrix")
    print(f"  {CLR_CYAN}[6]{CLR_RESET} Jalankan SEMUA Modul Berurutan (Automated Run)")
    print(f"  {CLR_CYAN}[0]{CLR_RESET} Keluar (Exit)")

def main():
    print_banner()

    # Jika argumen CLI diberikan (misal --auto atau non-interaktif), jalankan semua
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "--auto", "-a"):
        simulate_slowloris_mitigation()
        simulate_rate_limiter()
        simulate_circuit_breaker_probes()
        simulate_graceful_shutdown()
        run_chaos_audit_matrix()
        print(f"\n{CLR_GREEN}{CLR_BOLD}Seluruh simulasi selesai dengan sukses.{CLR_RESET}")
        return

    while True:
        display_menu()
        try:
            choice = input(f"\n{CLR_YELLOW}Masukkan pilihan [0-6]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{CLR_RED}Sesi dihentikan oleh user.{CLR_RESET}")
            break

        if choice == "1":
            simulate_slowloris_mitigation()
        elif choice == "2":
            simulate_rate_limiter()
        elif choice == "3":
            simulate_circuit_breaker_probes()
        elif choice == "4":
            simulate_graceful_shutdown()
        elif choice == "5":
            run_chaos_audit_matrix()
        elif choice == "6":
            simulate_slowloris_mitigation()
            simulate_rate_limiter()
            simulate_circuit_breaker_probes()
            simulate_graceful_shutdown()
            run_chaos_audit_matrix()
        elif choice == "0":
            print(f"{CLR_GREEN}Sampai jumpa! Menutup simulasi SRE.{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan coba lagi.{CLR_RESET}")

if __name__ == "__main__":
    main()
