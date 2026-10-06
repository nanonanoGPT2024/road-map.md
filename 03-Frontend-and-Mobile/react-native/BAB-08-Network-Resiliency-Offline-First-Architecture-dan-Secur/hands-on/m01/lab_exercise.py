#!/usr/bin/env python3
"""
Lab Exercise M01: React Native Network Resiliency & Offline-First Architecture Simulator
Topik: BAB-08-Network-Resiliency-Offline-First-Architecture-dan-Security

Simulasi Teknis:
1. NetInfo State & Network Simulator (Online, Offline, Flaky)
2. Resilient HTTP Client dengan Exponential Backoff + Jitter
3. Outbox Pattern / Offline Mutation Sync Queue
4. Conflict Resolution Strategy (Client-Wins / Server-Wins / Timestamp-based)
5. Security Layer (SSL Certificate Pinning Simulation & Secure Storage Token Handling)
"""

import sys
import time
import random
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

# --- ANSI Terminal Styling ---
class Style:
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
    BG_DARK = "\033[40m"

def print_header(title: str):
    width = 72
    print(f"\n{Style.CYAN}{'=' * width}{Style.RESET}")
    print(f"{Style.BOLD}{Style.WHITE}  {title.center(width - 4)}{Style.RESET}")
    print(f"{Style.CYAN}{'=' * width}{Style.RESET}")

def print_step(step_num: int, description: str):
    print(f"\n{Style.BOLD}{Style.YELLOW}[STEP {step_num}]{Style.RESET} {Style.WHITE}{description}{Style.RESET}")

def log_info(msg: str):
    print(f"  {Style.BLUE}ℹ{Style.RESET} {msg}")

def log_success(msg: str):
    print(f"  {Style.GREEN}✔{Style.RESET} {Style.GREEN}{msg}{Style.RESET}")

def log_warn(msg: str):
    print(f"  {Style.YELLOW}⚠{Style.RESET} {Style.YELLOW}{msg}{Style.RESET}")

def log_error(msg: str):
    print(f"  {Style.RED}✖{Style.RESET} {Style.RED}{msg}{Style.RESET}")

# --- Data Structures & Enums ---
class NetworkState(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    FLAKY = "FLAKY (High Packet Loss)"

class MutationAction(Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

@dataclass
class MutationTask:
    task_id: str
    action: MutationAction
    entity_id: str
    payload: Dict[str, Any]
    client_timestamp: float
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class ServerRecord:
    id: str
    title: str
    version: int
    updated_at: float

# --- Security Layer: SSL Pinning & Secure Store Simulator ---
class SecurityGateway:
    # Expected SHA-256 fingerprint for api.example.com
    EXPECTED_PIN = hashlib.sha256(b"TRUSTED_ROOT_CA_CERT_REACT_NATIVE_2026").hexdigest()

    @staticmethod
    def verify_ssl_pin(provided_cert_bytes: bytes) -> bool:
        calculated_hash = hashlib.sha256(provided_cert_bytes).hexdigest()
        return calculated_hash == SecurityGateway.EXPECTED_PIN

    @staticmethod
    def encrypt_secure_token(token: str, secret_key: str) -> str:
        # Simple simulated encrypted token representation
        digest = hashlib.sha256((token + secret_key).encode()).hexdigest()[:24]
        return f"enc_sec_{digest}"

# --- Network & HTTP Layer Simulator ---
class ResilientHttpClient:
    def __init__(self):
        self.network_state = NetworkState.ONLINE
        self.base_delay = 0.4
        self.valid_cert = b"TRUSTED_ROOT_CA_CERT_REACT_NATIVE_2026"
        self.untrusted_cert = b"ROGUE_MITM_PROXY_CERT_UNTRUSTED"

    def set_network_state(self, state: NetworkState):
        self.network_state = state
        color = Style.GREEN if state == NetworkState.ONLINE else (Style.RED if state == NetworkState.OFFLINE else Style.YELLOW)
        log_info(f"NetInfo: Status jaringan berubah menjadi: {color}{state.value}{Style.RESET}")

    def execute_request(self, method: str, endpoint: str, data: Dict[str, Any], cert_bytes: bytes) -> Dict[str, Any]:
        # 1. SSL Pinning Verification
        if not SecurityGateway.verify_ssl_pin(cert_bytes):
            raise ConnectionRefusedError("SSL_PIN_MISMATCH: Potensi Serangan MITM detected! Request digagalkan.")

        # 2. Network Check
        if self.network_state == NetworkState.OFFLINE:
            raise ConnectionError("NETWORK_UNAVAILABLE: Perangkat sedang offline.")

        if self.network_state == NetworkState.FLAKY:
            # 60% failure rate
            if random.random() < 0.6:
                raise TimeoutError("NETWORK_TIMEOUT: Socket read timeout pada koneksi tidak stabil.")

        time.sleep(0.1)  # Simulating round-trip latency
        return {"status": 200, "message": "OK", "data": data}

    def execute_with_backoff(self, task: MutationTask, cert_bytes: bytes) -> bool:
        """Menggunakan Exponential Backoff dengan Jitter"""
        attempt = 0
        while attempt <= task.max_retries:
            try:
                log_info(f"Mengirim mutasi {task.task_id} (Percobaan {attempt + 1}/{task.max_retries + 1})...")
                self.execute_request("POST", "/sync/mutation", task.payload, cert_bytes)
                log_success(f"Mutasi {task.task_id} berhasil disinkronisasi ke server!")
                return True
            except (ConnectionError, TimeoutError) as e:
                attempt += 1
                if attempt > task.max_retries:
                    log_error(f"Mutasi {task.task_id} gagal setelah {task.max_retries + 1} kali percobaan: {e}")
                    return False
                
                # Backoff Formula: base_delay * (2 ^ attempt) + uniform random jitter
                backoff_time = self.base_delay * (2 ** (attempt - 1)) + random.uniform(0.05, 0.15)
                log_warn(f"Gagal ({e}). Menunggu exponential backoff: {backoff_time:.2f}s...")
                time.sleep(backoff_time)
            except ConnectionRefusedError as sec_err:
                log_error(f"Fatal Security Error: {sec_err}")
                return False
        return False

# --- Offline Outbox Queue & Conflict Resolver ---
class OutboxQueueManager:
    def __init__(self, client: ResilientHttpClient):
        self.queue: List[MutationTask] = []
        self.client = client
        self.local_cache: Dict[str, Dict[str, Any]] = {}
        self.server_db: Dict[str, ServerRecord] = {
            "item_101": ServerRecord(id="item_101", title="Belanja Bahan Mingguan", version=1, updated_at=time.time() - 3600)
        }

    def enqueue_mutation(self, action: MutationAction, entity_id: str, payload: Dict[str, Any]):
        task_id = f"mut_{int(time.time() * 1000)}_{random.randint(100, 999)}"
        task = MutationTask(
            task_id=task_id,
            action=action,
            entity_id=entity_id,
            payload=payload,
            client_timestamp=time.time()
        )
        self.queue.append(task)
        # Optimistic UI Update pada Local Cache
        self.local_cache[entity_id] = {
            "data": payload,
            "_syncStatus": "PENDING_OUTBOX",
            "_updatedAt": task.client_timestamp
        }
        log_warn(f"[Optimistic UI] Mutasi {task.action.value} untuk '{entity_id}' disimpan di Outbox Queue.")
        log_info(f"Local Store terupdate secara optimis: {self.local_cache[entity_id]['data']}")

    def process_queue(self, cert_bytes: bytes):
        if not self.queue:
            log_info("Outbox Queue kosong. Tidak ada data yang tertunda.")
            return

        print(f"\n{Style.MAGENTA}--- Memproses Outbox Queue ({len(self.queue)} antrean) ---{Style.RESET}")
        unprocessed: List[MutationTask] = []

        while self.queue:
            task = self.queue.pop(0)
            success = self.client.execute_with_backoff(task, cert_bytes)

            if success:
                # Resolve & update server DB
                self.resolve_and_commit(task)
                if task.entity_id in self.local_cache:
                    self.local_cache[task.entity_id]["_syncStatus"] = "SYNCED"
            else:
                task.retry_count += 1
                unprocessed.append(task)

        self.queue = unprocessed
        log_info(f"Selesai proses antrean. Sisa antrean tertunda: {len(self.queue)}")

    def resolve_and_commit(self, task: MutationTask):
        """Conflict Resolution: Last-Write-Wins (LWW) berdasar Timestamp & Versioning"""
        server_rec = self.server_db.get(task.entity_id)
        if not server_rec:
            # New record
            self.server_db[task.entity_id] = ServerRecord(
                id=task.entity_id,
                title=task.payload.get("title", "Untitled"),
                version=1,
                updated_at=task.client_timestamp
            )
            log_success(f"[Server Sync] Entity baru '{task.entity_id}' berhasil dicatat (v1).")
        else:
            if task.client_timestamp > server_rec.updated_at:
                # Client LWW Wins
                old_title = server_rec.title
                server_rec.title = task.payload.get("title", server_rec.title)
                server_rec.version += 1
                server_rec.updated_at = task.client_timestamp
                log_success(f"[Conflict Resolved: LWW] Update '{task.entity_id}': '{old_title}' -> '{server_rec.title}' (v{server_rec.version}).")
            else:
                log_warn(f"[Conflict Rejected] Mutasi {task.task_id} kedaluwarsa dibanding data Server. Server wins.")

# --- Interactive Main Runner ---
def run_interactive_simulation():
    client = ResilientHttpClient()
    outbox = OutboxQueueManager(client)

    print_header("REACT NATIVE NETWORK RESILIENCY & OFFLINE-FIRST SIMULATOR")
    print(f"{Style.DIM}Modul Laboratorium: Arsitektur Resiliensi Jaringan, Outbox Queue, & Security{Style.RESET}")

    # Step 1: Security Handshake & SSL Pinning Validation
    print_step(1, "SSL Pinning Validation & Secure Storage Simulation")
    log_info("Menguji SSL Pinning dengan Certificate Pin yang valid...")
    try:
        res = client.execute_request("GET", "/api/v1/ping", {"check": "ssl"}, client.valid_cert)
        log_success(f"SSL Pin Valid: Connection Accepted -> {res}")
    except ConnectionRefusedError as e:
        log_error(f"Gagal SSL: {e}")

    log_info("Menguji serangan MITM dengan Rogue Certificate...")
    try:
        client.execute_request("GET", "/api/v1/ping", {"check": "ssl"}, client.untrusted_cert)
    except ConnectionRefusedError as e:
        log_success(f"Security Alert Berfungsi: {e}")

    token = "usr_jwt_mobile_session_key_99812"
    sec_token = SecurityGateway.encrypt_secure_token(token, "AES256_REACT_NATIVE_KEY")
    log_info(f"Simulasi Expo SecureStore / react-native-keychain:")
    log_info(f"Raw Token: {token} -> Stored Encrypted: {Style.CYAN}{sec_token}{Style.RESET}")

    # Step 2: Optimistic Mutation saat Kondisi OFFLINE
    print_step(2, "Offline Outbox Queue & Optimistic UI Update")
    client.set_network_state(NetworkState.OFFLINE)
    
    log_info("User membuat perubahan data saat mode pesawat (Offline)...")
    outbox.enqueue_mutation(
        action=MutationAction.UPDATE,
        entity_id="item_101",
        payload={"title": "Belanja Bahan Mingguan (Updated: Tambah Beras & Telur)"}
    )
    outbox.enqueue_mutation(
        action=MutationAction.CREATE,
        entity_id="item_102",
        payload={"title": "Beli Kabel USB-C Tipe Thunderbolt 4"}
    )

    log_info("Mencoba melakukan sinkronisasi otomatis saat masih OFFLINE...")
    outbox.process_queue(client.valid_cert)

    # Step 3: Network Pemulihan Flaky & Exponential Backoff + Jitter
    print_step(3, "Pemulihan Jaringan Menjadi FLAKY (Intermittent) & Sync Retry")
    client.set_network_state(NetworkState.FLAKY)
    log_info("Memicu background sync listener...")
    outbox.process_queue(client.valid_cert)

    # Step 4: Network Sempurna ONLINE & Final Queue Drain
    print_step(4, "Jaringan Kembali ONLINE Penuh & Verifikasi Status Konsistensi Data")
    client.set_network_state(NetworkState.ONLINE)
    outbox.process_queue(client.valid_cert)

    # Verifikasi Final State
    print_header("HASIL AKHIR SINKRONISASI OFFLINE-FIRST")
    print(f"\n{Style.BOLD}Status Local Cache:{Style.RESET}")
    for k, v in outbox.local_cache.items():
        status_color = Style.GREEN if v["_syncStatus"] == "SYNCED" else Style.YELLOW
        print(f"  • [{k}] Status: {status_color}{v['_syncStatus']}{Style.RESET} | Data: {v['data']}")

    print(f"\n{Style.BOLD}Status Database Server:{Style.RESET}")
    for k, rec in outbox.server_db.items():
        print(f"  • [{k}] Title: {Style.CYAN}{rec.title}{Style.RESET} (Version: {rec.version}, Timestamp: {rec.updated_at:.2f})")

    log_success("Seluruh simulasi siklus Offline-First dan Resiliensi Jaringan selesai dengan sukses 100%!")

if __name__ == "__main__":
    run_interactive_simulation()
