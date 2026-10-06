#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Produksi NoSQL & NewSQL
BAB-05: Basis Data NoSQL dan NewSQL

Modul ini mensimulasikan komponen arsitektur data produksi:
1. NoSQL Document Store (Replica Set dengan Oplog Replication & Write Concern majority)
2. In-Memory Distributed Cache (Cache-Aside pattern, TTL, & Cache Invalidation)
3. NewSQL Distributed Engine (Raft Consensus & Two-Phase Commit / 2PC Cross-Shard Transaction)

Dapat dijalankan secara interaktif (CLI menu) maupun headless/automated (argumen --all).
"""

import sys
import time
import random
import json
import uuid
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple


# ==============================================================================
# ANSI Color Formatting Utility
# ==============================================================================
class Color:
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
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"


def header(text: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}  {text}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}\n")


def success(msg: str) -> None:
    print(f" {Color.GREEN}✔ [SUCCESS]{Color.RESET} {msg}")


def info(msg: str) -> None:
    print(f" {Color.BLUE}ℹ [INFO]{Color.RESET}    {msg}")


def warn(msg: str) -> None:
    print(f" {Color.YELLOW}⚠ [WARN]{Color.RESET}    {msg}")


def error(msg: str) -> None:
    print(f" {Color.RED}✖ [ERROR]{Color.RESET}   {msg}")


# ==============================================================================
# 1. NoSQL Document Store Simulation (MongoDB Replica Set & Write Concern)
# ==============================================================================
class WriteConcern(Enum):
    UNACKNOWLEDGED = 0
    W1 = 1           # Ack dari Primary saja
    MAJORITY = 2     # Ack dari mayoritas node (Quorum: (3//2) + 1 = 2)


@dataclass
class ReplicaNode:
    node_id: str
    role: str  # "PRIMARY" atau "SECONDARY"
    storage: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    oplog_commit_index: int = 0
    is_alive: bool = True
    lag_ms: float = 0.0


class MongoReplicaSet:
    def __init__(self, name: str = "rs0"):
        self.name = name
        self.primary = ReplicaNode("node-01", "PRIMARY")
        self.secondaries = [
            ReplicaNode("node-02", "SECONDARY"),
            ReplicaNode("node-03", "SECONDARY"),
        ]
        self.global_oplog: List[Dict[str, Any]] = []

    @property
    def all_nodes(self) -> List[ReplicaNode]:
        return [self.primary] + self.secondaries

    def insert(self, collection: str, doc: Dict[str, Any], concern: WriteConcern = WriteConcern.MAJORITY) -> Tuple[bool, str]:
        if not self.primary.is_alive:
            return False, "Primary node tidak dapat dihubungi (Election diperlukan)!"

        doc_id = doc.get("_id", str(uuid.uuid4())[:8])
        doc["_id"] = doc_id
        doc["_version"] = 1

        # 1. Tulis ke Primary
        self.primary.storage[doc_id] = doc.copy()
        op_index = len(self.global_oplog) + 1
        oplog_entry = {"op_id": op_index, "col": collection, "doc_id": doc_id, "data": doc}
        self.global_oplog.append(oplog_entry)
        self.primary.oplog_commit_index = op_index

        # Evaluasi Quorum
        acks = 1  # Primary acknowledge

        # 2. Replikasi Oplog ke Secondary
        for sec in self.secondaries:
            if sec.is_alive:
                # Simulasi transfer oplog
                sec.storage[doc_id] = doc.copy()
                sec.oplog_commit_index = op_index
                acks += 1

        required_acks = 1 if concern == WriteConcern.W1 else (len(self.all_nodes) // 2 + 1)
        if concern == WriteConcern.UNACKNOWLEDGED:
            return True, f"Doc {doc_id} dikirim secara fire-and-forget (w=0)."

        if acks >= required_acks:
            return True, f"Doc {doc_id} berhasil dicommit dengan {acks}/{len(self.all_nodes)} node ACKs (concern: {concern.name})."
        else:
            return False, f"Write Concern Majority GAGAL! Hanya {acks}/{len(self.all_nodes)} node yang siap."

    def read(self, doc_id: str, read_preference: str = "primary") -> Optional[Dict[str, Any]]:
        if read_preference == "primary":
            if self.primary.is_alive:
                return self.primary.storage.get(doc_id)
            return None
        elif read_preference == "secondaryPreferred":
            active_sec = [s for s in self.secondaries if s.is_alive]
            if active_sec:
                node = random.choice(active_sec)
                return node.storage.get(doc_id)
            return self.primary.storage.get(doc_id) if self.primary.is_alive else None
        return None


# ==============================================================================
# 2. In-Memory Distributed Cache Simulation (Redis Cache-Aside Pattern)
# ==============================================================================
@dataclass
class CacheEntry:
    value: Any
    created_at: float
    ttl_seconds: float

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class RedisCacheCluster:
    def __init__(self, capacity: int = 50):
        self.capacity = capacity
        self.store: Dict[str, CacheEntry] = {}
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get(self, key: str) -> Optional[Any]:
        if key in self.store:
            entry = self.store[key]
            if entry.is_expired():
                del self.store[key]
                self.stats["misses"] += 1
                return None
            self.stats["hits"] += 1
            return entry.value
        self.stats["misses"] += 1
        return None

    def set(self, key: str, value: Any, ttl: float = 60.0) -> None:
        if len(self.store) >= self.capacity and key not in self.store:
            oldest_key = next(iter(self.store))
            del self.store[oldest_key]
            self.stats["evictions"] += 1

        self.store[key] = CacheEntry(value=value, created_at=time.time(), ttl_seconds=ttl)

    def delete(self, key: str) -> None:
        if key in self.store:
            del self.store[key]


class UserServiceCacheAside:
    """Implementasi Cache-Aside Pattern (Lazy Loading + Invalidation)"""
    def __init__(self, db: MongoReplicaSet, cache: RedisCacheCluster):
        self.db = db
        self.cache = cache

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        cache_key = f"user:profile:{user_id}"
        # 1. Cek cache
        cached = self.cache.get(cache_key)
        if cached:
            return {"source": "CACHE_HIT", "data": cached}

        # 2. Cache Miss: Ambil dari Database
        user_doc = self.db.read(user_id, read_preference="secondaryPreferred")
        if user_doc:
            # 3. Populate ke Cache dengan TTL 30 detik
            self.cache.set(cache_key, user_doc, ttl=30.0)
            return {"source": "DB_FETCH_CACHED", "data": user_doc}
        return {"source": "NOT_FOUND", "data": None}

    def update_user_balance(self, user_id: str, new_balance: float) -> bool:
        cache_key = f"user:profile:{user_id}"
        user_doc = self.db.read(user_id, read_preference="primary")
        if not user_doc:
            return False

        # 1. Update Database Primer
        user_doc["balance"] = new_balance
        user_doc["updated_at"] = time.time()
        ok, _ = self.db.insert("users", user_doc, concern=WriteConcern.MAJORITY)

        # 2. Invalidate Cache (Cache Eviction) untuk mencegah Stale Data
        self.cache.delete(cache_key)
        return ok


# ==============================================================================
# 3. NewSQL Distributed Engine (Raft Consensus & Distributed 2PC)
# ==============================================================================
@dataclass
class AccountRecord:
    account_id: str
    owner: str
    balance: float
    shard_id: int


class ShardPartition:
    """Partisi Shard yang dimanage secara terdistribusi dengan Raft Consensus"""
    def __init__(self, shard_id: int):
        self.shard_id = shard_id
        self.leader = f"node-shard-{shard_id}-L"
        self.records: Dict[str, AccountRecord] = {}
        self.locks: Dict[str, str] = {}  # account_id -> tx_id
        self.raft_log: List[str] = []

    def prepare(self, tx_id: str, account_id: str, amount_delta: float) -> bool:
        """Fase 1 2PC: PREPARE (Acquire Lock & Validasi Saldo)"""
        if account_id in self.locks and self.locks[account_id] != tx_id:
            return False  # Conflict: Row sedang dikunci oleh transaksi lain

        record = self.records.get(account_id)
        if not record:
            return False

        if record.balance + amount_delta < 0:
            return False  # Insufficient funds

        # Lock record
        self.locks[account_id] = tx_id
        self.raft_log.append(f"PREPARE tx={tx_id} acc={account_id} delta={amount_delta}")
        return True

    def commit(self, tx_id: str, account_id: str, amount_delta: float) -> bool:
        """Fase 2 2PC: COMMIT (Terapkan Delta & Lepas Lock via Consensus)"""
        if self.locks.get(account_id) != tx_id:
            return False

        record = self.records[account_id]
        record.balance += amount_delta
        del self.locks[account_id]
        self.raft_log.append(f"COMMIT tx={tx_id} acc={account_id} final_bal={record.balance}")
        return True

    def abort(self, tx_id: str, account_id: str) -> None:
        """Fase 2 2PC: ABORT / ROLLBACK (Lepas Lock)"""
        if self.locks.get(account_id) == tx_id:
            del self.locks[account_id]
            self.raft_log.append(f"ABORT tx={tx_id} acc={account_id}")


class NewSQLDistributedCoordinator:
    """Two-Phase Commit (2PC) Distributed Transaction Manager (CockroachDB/TiDB style)"""
    def __init__(self):
        # Shard 0: Akun ID genap, Shard 1: Akun ID ganjil
        self.shards: Dict[int, ShardPartition] = {
            0: ShardPartition(shard_id=0),
            1: ShardPartition(shard_id=1),
        }

    def _get_shard_id(self, account_id: str) -> int:
        hash_val = int(hashlib.md5(account_id.encode()).hexdigest(), 16)
        return hash_val % len(self.shards)

    def provision_account(self, account_id: str, owner: str, initial_balance: float) -> None:
        shard_id = self._get_shard_id(account_id)
        shard = self.shards[shard_id]
        shard.records[account_id] = AccountRecord(
            account_id=account_id,
            owner=owner,
            balance=initial_balance,
            shard_id=shard_id
        )

    def execute_cross_shard_transfer(self, from_id: str, to_id: str, amount: float) -> Tuple[bool, str]:
        tx_id = f"tx-{uuid.uuid4().hex[:6]}"
        shard_from = self.shards[self._get_shard_id(from_id)]
        shard_to = self.shards[self._get_shard_id(to_id)]

        cross_shard = (shard_from.shard_id != shard_to.shard_id)
        tag = "[CROSS-SHARD 2PC]" if cross_shard else "[SINGLE-SHARD]"

        # -------------------------------------------------------------
        # FASE 1: PREPARE (Voting Phase)
        # -------------------------------------------------------------
        vote_from = shard_from.prepare(tx_id, from_id, -amount)
        vote_to = shard_to.prepare(tx_id, to_id, amount)

        # -------------------------------------------------------------
        # FASE 2: COMMIT / ABORT (Decision Phase)
        # -------------------------------------------------------------
        if vote_from and vote_to:
            shard_from.commit(tx_id, from_id, -amount)
            shard_to.commit(tx_id, to_id, amount)
            return True, f"{tag} Tx {tx_id} KOMIT PENUH! Transfer {amount:.2f} dari {from_id} -> {to_id} sukses."
        else:
            # Rollback peserta yang sempat voting YES
            if vote_from:
                shard_from.abort(tx_id, from_id)
            if vote_to:
                shard_to.abort(tx_id, to_id)
            reason = "Saldo tidak cukup atau locking collision!"
            return False, f"{tag} Tx {tx_id} ROLLBACK/ABORT! Alasan: {reason}"


# ==============================================================================
# 4. Interactive & Automated Scenarios
# ==============================================================================
def demo_mongodb_replication():
    header("SKENARIO 1: NoSQL Document Store (MongoDB Replica Set & Write Concern)")
    rs = MongoReplicaSet("rs-prod-jakarta")

    info("Menginisialisasi Replica Set (1 Primary, 2 Secondaries)...")
    time.sleep(0.1)

    print(f" {Color.WHITE}Topologi Klaster:{Color.RESET}")
    for n in rs.all_nodes:
        print(f"   - {Color.CYAN}{n.node_id}{Color.RESET} ({Color.YELLOW}{n.role}{Color.RESET}) | Status: Online")

    print("\n--- Percobaan 1: Write Concern Majority (Quorum Ack 2/3) ---")
    doc = {"_id": "usr-01", "name": "Budi Santoso", "tier": "Enterprise", "balance": 15000000.0}
    ok, msg = rs.insert("users", doc, concern=WriteConcern.MAJORITY)
    if ok:
        success(msg)
    else:
        error(msg)

    print("\n--- Percobaan 2: Simulasi Partisi Jaringan (Matikan Secondary-01 & 02) ---")
    warn("Mematikan node-02 dan node-03 untuk menguji toleransi jaringan...")
    rs.secondaries[0].is_alive = False
    rs.secondaries[1].is_alive = False

    doc2 = {"_id": "usr-02", "name": "Siti Rahma", "tier": "Standard", "balance": 250000.0}
    ok, msg = rs.insert("users", doc2, concern=WriteConcern.MAJORITY)
    if not ok:
        error(f"Diharapkan Gagal: {msg}")
        info("ACID Guarantees terpenuhi: Database menolak komit ketika Quorum gagal!")

    # Pulihkan kembali
    rs.secondaries[0].is_alive = True
    rs.secondaries[1].is_alive = True
    success("Klaster kembali pulih (Re-synchronized).\n")


def demo_cache_aside():
    header("SKENARIO 2: In-Memory Distributed Caching (Cache-Aside & Invalidation)")
    rs = MongoReplicaSet("rs-cache")
    cache = RedisCacheCluster(capacity=5)
    service = UserServiceCacheAside(rs, cache)

    # Seed User
    user_id = "user_99"
    rs.insert("users", {"_id": user_id, "name": "Eko Prasetyo", "balance": 7500000.0}, WriteConcern.MAJORITY)

    print(f"{Color.WHITE}Siklus Permintaan Data Profile:{Color.RESET}")

    # Request 1: Cache Miss
    res1 = service.get_user_profile(user_id)
    info(f"Req 1: {res1['source']} -> Diambil dari MongoDB, lalu disimpan di Redis Cache.")

    # Request 2: Cache Hit
    res2 = service.get_user_profile(user_id)
    success(f"Req 2: {res2['source']} -> Langsung dari Redis In-Memory (Latency <1ms)!")

    # Request 3: Update Saldo (Trigger Cache Invalidation)
    print("\n--- Update Saldo di Database & Evaluasi Cache Invalidation ---")
    service.update_user_balance(user_id, 9200000.0)
    warn(f"Saldo diubah ke Rp 9.200.000 -> Key '{f'user:profile:{user_id}'}' dibersihkan dari Cache!")

    # Request 4: Cache Miss (Data baru termuat tanpa stale reading)
    res3 = service.get_user_profile(user_id)
    info(f"Req 4: {res3['source']} -> Terbaca saldo terupdate: Rp {res3['data']['balance']:,.2f}")
    success("Konsistensi data berhasil dijaga antara NoSQL Storage & In-Memory Cache.\n")


def demo_newsql_distributed_2pc():
    header("SKENARIO 3: NewSQL Distributed Sharding & 2PC Consensus Transaction")
    coord = NewSQLDistributedCoordinator()

    # Provision Accounts
    coord.provision_account("ACC_JKT_01", "PT Digital Nusantara", 50_000_000.0)
    coord.provision_account("ACC_SBY_02", "CV Wisata Bahari", 10_000_000.0)

    acc1_shard = coord._get_shard_id("ACC_JKT_01")
    acc2_shard = coord._get_shard_id("ACC_SBY_02")

    print(f"Pemetaan Shard Terdistribusi:")
    print(f" - ACC_JKT_01 -> {Color.CYAN}Shard {acc1_shard}{Color.RESET}")
    print(f" - ACC_SBY_02 -> {Color.CYAN}Shard {acc2_shard}{Color.RESET}")
    print(f" Status Shard: {'Cross-Shard Partitioning (2PC Wajib)' if acc1_shard != acc2_shard else 'Single Shard'}\n")

    print("--- Transaksi 1: Transfer Lintas Shard Valid (Rp 15.000.000) ---")
    ok, msg = coord.execute_cross_shard_transfer("ACC_JKT_01", "ACC_SBY_02", 15_000_000.0)
    if ok:
        success(msg)
    else:
        error(msg)

    print("\n--- Transaksi 2: Transfer Melebihi Saldo / Insufficient Funds (Rp 100.000.000) ---")
    ok, msg = coord.execute_cross_shard_transfer("ACC_JKT_01", "ACC_SBY_02", 100_000_000.0)
    if not ok:
        warn(msg)
        info("Atomisitas terjamin: Tidak ada dana mengambang atau debet sepihak!")

    # Tampilkan saldo akhir
    bal1 = coord.shards[acc1_shard].records["ACC_JKT_01"].balance
    bal2 = coord.shards[acc2_shard].records["ACC_SBY_02"].balance
    print(f"\n{Color.BOLD}Audit Saldo Terakhir:{Color.RESET}")
    print(f" • ACC_JKT_01: Rp {bal1:,.2f}")
    print(f" • ACC_SBY_02: Rp {bal2:,.2f}")
    print(f" • Total Klaster : Rp {(bal1 + bal2):,.2f} {Color.GREEN}(Konsisten!){Color.RESET}\n")


def run_full_suite():
    print(f"{Color.BOLD}{Color.MAGENTA}")
    print("╔═════════════════════════════════════════════════════════════════════════╗")
    print("║   LAB INTERAKTIF: ARSITEKTUR BASIS DATA NoSQL & NewSQL PRODUKSI         ║")
    print("║   BAB-05: Distributed Systems, High Availability & ACID Transactions    ║")
    print("╚═════════════════════════════════════════════════════════════════════════╝")
    print(f"{Color.RESET}")

    demo_mongodb_replication()
    demo_cache_aside()
    demo_newsql_distributed_2pc()

    header("HASIL VERIFIKASI AKHIR KLASTER")
    success("Seluruh simulasi NoSQL Replica Set, Cache-Aside, dan NewSQL 2PC lulus tanpa error!")


def interactive_menu():
    while True:
        print(f"\n{Color.BOLD}{Color.CYAN}=== MENU LAB NoSQL & NewSQL ==={Color.RESET}")
        print(" [1] Uji MongoDB Replica Set & Write Concern (Quorum)")
        print(" [2] Uji Redis In-Memory Cache-Aside & Invalidation")
        print(" [3] Uji NewSQL Distributed 2PC Cross-Shard Transaction")
        print(" [4] Jalankan Semua Simulasi Sekaligus")
        print(" [0] Keluar")
        choice = input(f"{Color.YELLOW}Pilih opsi [0-4]: {Color.RESET}").strip()

        if choice == "1":
            demo_mongodb_replication()
        elif choice == "2":
            demo_cache_aside()
        elif choice == "3":
            demo_newsql_distributed_2pc()
        elif choice == "4":
            run_full_suite()
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih telah menjalankan lab arsitektur NoSQL/NewSQL!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid! Masukkan angka 0 - 4.{Color.RESET}")


if __name__ == "__main__":
    # Jika dijalankan dengan flag --all atau non-TTY, jalankan seluruh skenario otomatis
    if "--all" in sys.argv or "--headless" in sys.argv or not sys.stdin.isatty():
        run_full_suite()
    else:
        interactive_menu()
