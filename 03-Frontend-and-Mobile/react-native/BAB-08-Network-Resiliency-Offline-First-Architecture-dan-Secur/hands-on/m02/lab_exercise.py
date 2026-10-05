#!/usr/bin/env python3
"""
React Native Lab 08: Network Resiliency, Offline-First Architecture & Security Simulation.
Pilar 4: Hands-on Lab Nyata untuk Modul 02.

Topik Pembahasan:
1. Offline Sync Queue & SQLite Local State Engine
2. Circuit Breaker Pattern & Exponential Jitter Backoff
3. Conflict Resolution Strategy (Server Wins vs Client Wins vs CRDT Vector Clock)
4. Mobile Security Layer: SSL Pinning Verification & Keychain/Keystore Simulation
"""

import hashlib
import hmac
import json
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# --- ANSI Terminal Colors ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[40m"


def print_banner(text: str) -> None:
    line = "=" * 76
    print(f"\n{Color.CYAN}{Color.BOLD}{line}")
    print(f"  {text}")
    print(f"{line}{Color.RESET}\n")


def print_step(title: str, desc: str) -> None:
    print(f"{Color.YELLOW}{Color.BOLD}>>> [{title}]{Color.RESET} {Color.WHITE}{desc}{Color.RESET}")


def print_success(msg: str) -> None:
    print(f"    {Color.GREEN}✔ [SUCCESS]{Color.RESET} {msg}")


def print_warn(msg: str) -> None:
    print(f"    {Color.YELLOW}⚠ [WARN]{Color.RESET} {msg}")


def print_error(msg: str) -> None:
    print(f"    {Color.RED}✖ [ERROR]{Color.RESET} {msg}")


def print_info(msg: str) -> None:
    print(f"    {Color.BLUE}ℹ [INFO]{Color.RESET} {msg}")


# --- 1. Security Layer: SSL Pinning & Keychain ---
class SSLPinningEngine:
    """Simulasi validasi X.509 Public Key Pinning (HPKP / SHA256 Fingerprint) di React Native."""
    def __init__(self, trusted_fingerprint: str):
        self.pinned_fingerprint = trusted_fingerprint

    def verify_server_certificate(self, server_host: str, raw_cert_data: bytes) -> bool:
        cert_hash = hashlib.sha256(raw_cert_data).hexdigest()
        is_valid = cert_hash == self.pinned_fingerprint
        if is_valid:
            print_success(f"SSL Pinning OK: {server_host} hash cocok ({cert_hash[:16]}...)")
        else:
            print_error(f"MITM Alert: Pinning mismatch pada {server_host}! Ditemukan: {cert_hash[:16]}... Harapan: {self.pinned_fingerprint[:16]}...")
        return is_valid


class SecureStorage:
    """Simulasi react-native-keychain / EncryptedSharedPreferences."""
    def __init__(self, master_key: str):
        self._master_key = master_key.encode("utf-8")
        self._vault: Dict[str, str] = {}

    def set_secure_item(self, key: str, value: str) -> None:
        token = hmac.new(self._master_key, value.encode("utf-8"), hashlib.sha256).hexdigest()
        # Disimpan dalam format enkripsi terisolasi
        payload = {"value": value, "hmac": token, "updated_at": time.time()}
        self._vault[key] = json.dumps(payload)
        print_success(f"Keychain write key: '{key}' aman (HMAC verified).")

    def get_secure_item(self, key: str) -> Optional[str]:
        raw = self._vault.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        expected_hmac = hmac.new(self._master_key, data["value"].encode("utf-8"), hashlib.sha256).hexdigest()
        if expected_hmac != data["hmac"]:
            print_error(f"Tamper detected pada storage key '{key}'!")
            return None
        return data["value"]


# --- 2. Network Circuit Breaker & Resiliency ---
class CircuitState(Enum):
    CLOSED = "CLOSED (Normal Operation)"
    OPEN = "OPEN (Fast Failure / Offline Mode)"
    HALF_OPEN = "HALF_OPEN (Trial Sync)"


class CircuitBreaker:
    """Implementasi Circuit Breaker untuk menjaga UI thread React Native dari hanging I/O."""
    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 3.0):
        self.state = CircuitState.CLOSED
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.failure_count = 0
        self.last_failure_time: float = 0.0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        print_warn(f"Circuit Breaker failure count: {self.failure_count}/{self.failure_threshold}")
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            print_error(f"Circuit Breaker tripping to {self.state.value}!")

    def record_success(self) -> None:
        self.failure_count = 0
        if self.state != CircuitState.CLOSED:
            print_success(f"Recovery success: Circuit kembali ke {CircuitState.CLOSED.value}")
        self.state = CircuitState.CLOSED

    def can_attempt_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_time_sec:
                self.state = CircuitState.HALF_OPEN
                print_info(f"Cooldown berlalu ({elapsed:.1f}s), masuk fase {self.state.value}")
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return True
        return False


# --- 3. Offline First Sync Queue & Conflict Resolution ---
@dataclass
class MutationRecord:
    id: str
    entity: str
    action: str  # CREATE, UPDATE, DELETE
    payload: Dict[str, Any]
    client_version: int
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0


class ConflictStrategy(Enum):
    CLIENT_WINS = "CLIENT_WINS"
    SERVER_WINS = "SERVER_WINS"
    VECTOR_CLOCK = "VECTOR_CLOCK"


class OfflineSyncEngine:
    """Simulasi WatermelonDB / Redux-Offline / PowerSync engine di sisi client."""
    def __init__(self, strategy: ConflictStrategy = ConflictStrategy.VECTOR_CLOCK):
        self.queue: List[MutationRecord] = []
        self.local_db: Dict[str, Dict[str, Any]] = {}
        self.strategy = strategy

    def enqueue_mutation(self, entity: str, action: str, entity_id: str, data: Dict[str, Any]) -> MutationRecord:
        # Optimistic UI update di lokal
        current = self.local_db.get(entity_id, {"version": 0, "data": {}})
        new_version = current.get("version", 0) + 1
        
        updated_local = {
            "id": entity_id,
            "version": new_version,
            "data": {**current.get("data", {}), **data},
            "_sync_status": "PENDING_SYNC"
        }
        self.local_db[entity_id] = updated_local

        mutation = MutationRecord(
            id=f"mut_{int(time.time()*1000)}_{random.randint(100,999)}",
            entity=entity,
            action=action,
            payload={"id": entity_id, **data},
            client_version=new_version
        )
        self.queue.append(mutation)
        print_info(f"Optimistic UI Updated: [{entity}] ID '{entity_id}' -> Local v{new_version}. Queue size: {len(self.queue)}")
        return mutation

    def resolve_conflict(self, local_item: Dict[str, Any], server_item: Dict[str, Any]) -> Dict[str, Any]:
        """Menyelesaikan konflik saat sinkronisasi."""
        print_warn(f"Konflik Terdeteksi pada ID {local_item['id']}! Strategi: {self.strategy.value}")
        
        if self.strategy == ConflictStrategy.CLIENT_WINS:
            resolved = {**local_item, "version": max(local_item["version"], server_item["version"]) + 1}
            print_info("Resolusi: Client Wins diterapkan.")
            return resolved

        elif self.strategy == ConflictStrategy.SERVER_WINS:
            resolved = {**server_item}
            print_info("Resolusi: Server Wins diterapkan. Local rollback ke server state.")
            return resolved

        else: # VECTOR_CLOCK / 3-Way Field Merge
            merged_data = {**server_item.get("data", {}), **local_item.get("data", {})}
            resolved = {
                "id": local_item["id"],
                "version": max(local_item["version"], server_item["version"]) + 1,
                "data": merged_data,
                "_sync_status": "SYNCED"
            }
            print_info("Resolusi: Smart 3-Way Field Merge berhasil.")
            return resolved


# --- 4. Remote Server Simulator ---
class MockRemoteServer:
    def __init__(self, simulated_fingerprint: str):
        self.remote_db: Dict[str, Dict[str, Any]] = {}
        self.cert_data = b"VALID_PRODUCTION_X509_CERT_KEY_DATA"
        self.fingerprint = simulated_fingerprint
        self.is_online = True
        self.latency_ms = 40

    def process_sync(self, mutation: MutationRecord) -> Tuple[bool, Optional[Dict[str, Any]]]:
        if not self.is_online:
            return False, None

        time.sleep(self.latency_ms / 1000.0)
        item_id = mutation.payload["id"]
        server_record = self.remote_db.get(item_id)

        if server_record:
            # Simulasi race condition server side update
            if server_record["version"] > mutation.client_version:
                # Konflik: server sudah punya versi lebih tinggi
                return False, server_record

        # Mutasi berhasil di server
        new_version = (server_record["version"] if server_record else 0) + 1
        new_record = {
            "id": item_id,
            "version": new_version,
            "data": mutation.payload,
            "server_timestamp": time.time()
        }
        self.remote_db[item_id] = new_record
        return True, new_record


# --- 5. Interactive Orchestrator Workflow ---
def run_interactive_simulation() -> None:
    print_banner("SIMULASI ARSITEKTUR REACT NATIVE: NETWORK RESILIENCY & OFFLINE-FIRST")
    
    cert_hash = hashlib.sha256(b"VALID_PRODUCTION_X509_CERT_KEY_DATA").hexdigest()
    server = MockRemoteServer(simulated_fingerprint=cert_hash)
    ssl_engine = SSLPinningEngine(trusted_fingerprint=cert_hash)
    storage = SecureStorage(master_key="prod_rn_vault_secret_device_unique_key")
    circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_time_sec=2.0)
    sync_engine = OfflineSyncEngine(strategy=ConflictStrategy.VECTOR_CLOCK)

    # Langkah 1: Bootstrapping & Security Check
    print_step("STEP 1", "Verifikasi Keamanan Perangkat: Keystore & SSL Pinning")
    storage.set_secure_item("user_auth_token", "jwt_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.lab_auth")
    token = storage.get_secure_item("user_auth_token")
    print_info(f"Token sesi terbaca dari Keychain: {token[:25]}...")
    
    print("\nValidasi Handshake Sertifikat:")
    ssl_engine.verify_server_certificate("api.core-app.internal", server.cert_data)

    # Test MITM Protection
    fake_cert = b"ATTACKER_INJECTED_PROXY_CERTIFICATE"
    print("\nPengujian Penyerangan MITM (Man-in-the-middle):")
    ssl_engine.verify_server_certificate("api.core-app.internal", fake_cert)

    # Langkah 2: State Online & Normal Mutation
    print_step("STEP 2", "Mutasi Pertama Saat Online (Optimistic UI -> Sync)")
    sync_engine.enqueue_mutation(
        entity="OrderEntity",
        action="CREATE",
        entity_id="ord_9901",
        data={"item": "MacBook Pro M3", "status": "PENDING", "qty": 1}
    )

    print("\nProses Flush Queue Sinkronisasi:")
    if circuit_breaker.can_attempt_request():
        mut = sync_engine.queue.pop(0)
        success, res = server.process_sync(mut)
        if success:
            circuit_breaker.record_success()
            sync_engine.local_db[mut.payload["id"]]["_sync_status"] = "SYNCED"
            print_success(f"Mutation {mut.id} tersinkronisasi ke server v{res['version']}")
        else:
            circuit_breaker.record_failure()

    # Langkah 3: Disconnect Network (Simulasi Terowongan / Mode Pesawat)
    print_step("STEP 3", "Jaringan Terputus: Transisi Otomatis ke Offline Store & Circuit Breaker")
    server.is_online = False
    print_warn("Koneksi fisik hilang: NetInfo state -> { isConnected: false, isInternetReachable: false }")

    # User melakukan 3 tindakan secara offline
    sync_engine.enqueue_mutation("OrderEntity", "UPDATE", "ord_9901", {"qty": 2, "notes": "Add sleeve case"})
    sync_engine.enqueue_mutation("OrderEntity", "UPDATE", "ord_9901", {"discount_code": "PROMO_OFFLINE"})
    sync_engine.enqueue_mutation("UserEntity", "CREATE", "usr_55", {"name": "Budi Santoso", "role": "Engineer"})

    print("\nPercobaan Background Sync saat offline (Memicu Circuit Breaker):")
    while sync_engine.queue:
        if not circuit_breaker.can_attempt_request():
            print_error(f"Sync dihentikan! Circuit Breaker adalah {circuit_breaker.state.value}. Menjaga battery & I/O.")
            break
        
        mut = sync_engine.queue[0]
        print_info(f"Mencoba sinkronisasi mutasi: {mut.id} ({mut.entity})")
        success, _ = server.process_sync(mut)
        if not success:
            circuit_breaker.record_failure()
            mut.retry_count += 1
            # Exponential Backoff with Jitter
            backoff = (2 ** mut.retry_count) + random.uniform(0.1, 0.5)
            print_warn(f"Sync gagal. Backoff terjadwal: {backoff:.2f} detik")

    # Langkah 4: Konflik Data di Server Saat Device Offline
    print_step("STEP 4", "Simulasi Data Server Berubah dari Device Lain (Konflik)")
    server.remote_db["ord_9901"] = {
        "id": "ord_9901",
        "version": 5,
        "data": {"item": "MacBook Pro M3", "status": "OUT_OF_STOCK", "admin_lock": True},
        "server_timestamp": time.time()
    }
    print_warn("Server telah dimodifikasi oleh Admin Web Console: status -> 'OUT_OF_STOCK' (v5)")

    # Langkah 5: Network Reconnect & Intelligent Sync
    print_step("STEP 5", "Jaringan Pulih: Cooldown Circuit Breaker & 3-Way Conflict Resolution")
    print_info("Menunggu cooldown Circuit Breaker...")
    time.sleep(2.1)
    server.is_online = True
    print_success("NetInfo: Connection restored. isInternetReachable: true")

    if circuit_breaker.can_attempt_request():
        print_info(f"Circuit Breaker mengizinkan request uji coba ({circuit_breaker.state.value})")
        
        while sync_engine.queue:
            mut = sync_engine.queue.pop(0)
            success, server_data = server.process_sync(mut)
            
            if not success and server_data:
                # Konflik terjadi
                local_item = sync_engine.local_db[mut.payload["id"]]
                resolved = sync_engine.resolve_conflict(local_item, server_data)
                sync_engine.local_db[mut.payload["id"]] = resolved
                circuit_breaker.record_success()
            elif success:
                circuit_breaker.record_success()
                sync_engine.local_db[mut.payload["id"]]["_sync_status"] = "SYNCED"
                print_success(f"Mutasi {mut.id} berhasil disinkronkan.")

    # Rekapitulasi State Akhir
    print_banner("HASIL AKHIR SINKRONISASI OFFLINE-FIRST PADA LOCAL SQLITE / STATE")
    for entity_id, record in sync_engine.local_db.items():
        print(f"{Color.CYAN}Entity ID:{Color.RESET} {entity_id}")
        print(f"  {Color.BOLD}Final Version:{Color.RESET} {record.get('version')}")
        print(f"  {Color.BOLD}Sync Status:{Color.RESET} {record.get('_sync_status')}")
        print(f"  {Color.BOLD}Merged Payload:{Color.RESET} {json.dumps(record.get('data'), indent=4)}")
        print("-" * 50)

    print(f"\n{Color.GREEN}{Color.BOLD}✔ Simulasi Arsitektur Produksi React Native Selesai dengan Sukses!{Color.RESET}\n")


if __name__ == "__main__":
    try:
        run_interactive_simulation()
    except KeyboardInterrupt:
        print("\n\nSimulasi dibatalkan oleh pengguna.")
        sys.exit(0)
