#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi NoSQL & NewSQL
BAB 05: Basis Data NoSQL dan NewSQL

Modul ini mengimplementasikan simulasi interaktif dari 4 model basis data modern:
1. Document Store (MongoDB-style query engine & indexing)
2. Key-Value Store (Redis-style TTL caching & atomic operations)
3. Wide-Column Store (Cassandra-style Consistent Hashing & partition key routing)
4. NewSQL Consensus Engine (Raft leader lease & 2-Phase Commit distributed transaction)
"""

import sys
import time
import json
import hashlib
from typing import Dict, Any, List, Optional

# ANSI Color Codes untuk visualisasi terminal interaktif
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
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"


# ==============================================================================
# 1. DOCUMENT STORE SIMULATOR (MongoDB Style)
# ==============================================================================
class DocumentStore:
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.indexes: Dict[str, Dict[Any, List[str]]] = {}

    def create_index(self, field: str) -> None:
        self.indexes[field] = {}
        for doc_id, doc in self.documents.items():
            val = doc.get(field)
            if val is not None:
                self.indexes[field].setdefault(val, []).append(doc_id)

    def insert(self, doc: Dict[str, Any]) -> str:
        doc_id = doc.get("_id") or hashlib.md5(f"{time.time()}_{len(self.documents)}".encode()).hexdigest()[:10]
        doc["_id"] = doc_id
        self.documents[doc_id] = doc

        # Update secondary indexes
        for field, index_map in self.indexes.items():
            val = doc.get(field)
            if val is not None:
                index_map.setdefault(val, []).append(doc_id)
        return doc_id

    def find(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Optimization: Cek apakah query memanfaatkan index
        for field, target_val in query.items():
            if field in self.indexes and isinstance(target_val, (str, int, float, bool)):
                doc_ids = self.indexes[field].get(target_val, [])
                results = []
                for did in doc_ids:
                    doc = self.documents[did]
                    if self._matches(doc, query):
                        results.append(doc)
                return results

        # Full table/collection scan jika tanpa index
        return [doc for doc in self.documents.values() if self._matches(doc, query)]

    def _matches(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for k, v in query.items():
            if isinstance(v, dict):
                # Operator query: $gt, $lt, $in
                doc_val = doc.get(k)
                if doc_val is None:
                    return False
                if "$gt" in v and not (doc_val > v["$gt"]):
                    return False
                if "$lt" in v and not (doc_val < v["$lt"]):
                    return False
                if "$in" in v and doc_val not in v["$in"]:
                    return False
            else:
                if doc.get(k) != v:
                    return False
        return True


# ==============================================================================
# 2. KEY-VALUE STORE SIMULATOR (Redis Style with TTL & LRU)
# ==============================================================================
class KeyValueStore:
    def __init__(self, capacity: int = 5):
        self.capacity = capacity
        self.store: Dict[str, Any] = {}
        self.expires_at: Dict[str, float] = {}
        self.access_order: List[str] = []

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        if key in self.store:
            self.access_order.remove(key)
        elif len(self.store) >= self.capacity:
            # LRU Eviction jika memori penuh
            evicted = self.access_order.pop(0)
            del self.store[evicted]
            self.expires_at.pop(evicted, None)

        self.store[key] = value
        self.access_order.append(key)

        if ttl_seconds is not None:
            self.expires_at[key] = time.time() + ttl_seconds
        else:
            self.expires_at.pop(key, None)

    def get(self, key: str) -> Optional[Any]:
        # Cek TTL expiration
        if key in self.expires_at and time.time() > self.expires_at[key]:
            del self.store[key]
            del self.expires_at[key]
            if key in self.access_order:
                self.access_order.remove(key)
            return None

        if key in self.store:
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.store[key]
        return None

    def dump_keys(self) -> Dict[str, Any]:
        valid_keys = {}
        now = time.time()
        for k in list(self.store.keys()):
            if k in self.expires_at and now > self.expires_at[k]:
                continue
            ttl_left = max(0.0, round(self.expires_at[k] - now, 1)) if k in self.expires_at else "persistent"
            valid_keys[k] = {"value": self.store[k], "ttl": ttl_left}
        return valid_keys


# ==============================================================================
# 3. WIDE-COLUMN STORE SIMULATOR (Cassandra Style Consistent Hashing)
# ==============================================================================
class CassandraRing:
    def __init__(self, nodes: List[str]):
        self.nodes = sorted(nodes)
        self.ring: List[tuple] = []
        for node in nodes:
            # Generate virtual hash token (0 - 360 derajat)
            h = int(hashlib.sha256(node.encode()).hexdigest(), 16) % 360
            self.ring.append((h, node))
        self.ring.sort(key=lambda x: x[0])
        self.storage: Dict[str, Dict[str, Dict[str, Any]]] = {node: {} for node in nodes}

    def _get_node_for_key(self, partition_key: str) -> str:
        h = int(hashlib.sha256(partition_key.encode()).hexdigest(), 16) % 360
        for token, node in self.ring:
            if h <= token:
                return node
        # Wrap around ring
        return self.ring[0][1]

    def write_row(self, partition_key: str, cluster_key: str, columns: Dict[str, Any]) -> str:
        target_node = self._get_node_for_key(partition_key)
        node_db = self.storage[target_node]
        if partition_key not in node_db:
            node_db[partition_key] = {}
        node_db[partition_key][cluster_key] = {
            "columns": columns,
            "timestamp": time.time_ns()
        }
        return target_node


# ==============================================================================
# 4. NewSQL DISTRIBUTED TRANSACTION SIMULATOR (2-Phase Commit / 2PC)
# ==============================================================================
class DistributedNewSQLShard:
    def __init__(self, shard_id: str):
        self.shard_id = shard_id
        self.data: Dict[str, int] = {}
        self.prepared_tx: Dict[str, tuple] = {}

    def prepare(self, tx_id: str, key: str, delta: int) -> bool:
        current_val = self.data.get(key, 0)
        if current_val + delta < 0:
            return False  # Abort jika saldo tidak mencukupi
        self.prepared_tx[tx_id] = (key, delta)
        return True

    def commit(self, tx_id: str) -> None:
        if tx_id in self.prepared_tx:
            key, delta = self.prepared_tx.pop(tx_id)
            self.data[key] = self.data.get(key, 0) + delta

    def rollback(self, tx_id: str) -> None:
        self.prepared_tx.pop(tx_id, None)


class Coordinator2PC:
    def __init__(self, shards: Dict[str, DistributedNewSQLShard]):
        self.shards = shards

    def execute_transfer(self, tx_id: str, from_shard: str, from_acc: str, to_shard: str, to_acc: str, amount: int) -> bool:
        # Phase 1: Prepare
        p1 = self.shards[from_shard].prepare(tx_id, from_acc, -amount)
        p2 = self.shards[to_shard].prepare(tx_id, to_acc, amount)

        # Phase 2: Decision
        if p1 and p2:
            self.shards[from_shard].commit(tx_id)
            self.shards[to_shard].commit(tx_id)
            return True
        else:
            self.shards[from_shard].rollback(tx_id)
            self.shards[to_shard].rollback(tx_id)
            return False


# ==============================================================================
# TERMINAL UI & INTERACTIVE TEST RUNNER
# ==============================================================================
def banner() -> None:
    print(f"\n{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} === NO SQL & NEWSQL ARCHITECTURE LAB EXERCISE === {Style.RESET}\n")

def demo_document_store() -> None:
    print(f"{Style.CYAN}{Style.BOLD}▶ DEMO 1: Document Store (MongoDB Style JSON Document & Query){Style.RESET}")
    doc_db = DocumentStore("users_catalog")
    doc_db.create_index("role")

    users = [
        {"_id": "u101", "name": "Budi", "role": "admin", "score": 95, "tags": ["db", "backend"]},
        {"_id": "u102", "name": "Siti", "role": "engineer", "score": 88, "tags": ["python", "nosql"]},
        {"_id": "u103", "name": "Agus", "role": "engineer", "score": 72, "tags": ["junior"]},
        {"_id": "u104", "name": "Dewi", "role": "lead", "score": 98, "tags": ["cloud", "newsql"]}
    ]
    for u in users:
        doc_db.insert(u)

    print(f"  {Style.GREEN}✓{Style.RESET} 4 Dokumen berhasil disimpan dengan index pada field '{Style.BOLD}role{Style.RESET}'.")

    # Indexed query
    res_index = doc_db.find({"role": "engineer"})
    print(f"  {Style.YELLOW}[Indexed Query]{Style.RESET} find({{role: 'engineer'}}): {len(res_index)} dokumen ditemukan:")
    for r in res_index:
        print(f"    - ID: {r['_id']} | Nama: {r['name']} | Score: {r['score']}")

    # Range Operator query
    res_range = doc_db.find({"score": {"$gt": 85}})
    print(f"  {Style.YELLOW}[Range Query]{Style.RESET} find({{score: {{$gt: 85}}}}): {len(res_range)} dokumen ditemukan:")
    for r in res_range:
        print(f"    - ID: {r['_id']} | Nama: {r['name']} | Score: {r['score']}")
    print()

def demo_key_value_store() -> None:
    print(f"{Style.CYAN}{Style.BOLD}▶ DEMO 2: Key-Value Store (Redis Style Cache TTL & LRU Eviction){Style.RESET}")
    kv = KeyValueStore(capacity=3)
    print("  Menginisialisasi Cache Store dengan kapasitas buffer LRU = 3 item...")

    kv.set("session:1", {"user": "Alice"}, ttl_seconds=1.5)
    kv.set("session:2", {"user": "Bob"})
    kv.set("session:3", {"user": "Charlie"})
    print(f"  {Style.GREEN}✓{Style.RESET} Set 3 keys. State saat ini:")
    for k, v in kv.dump_keys().items():
        print(f"    - {k} -> {v['value']} (TTL: {v['ttl']}s)")

    print(f"  {Style.MAGENTA}[LRU Test]{Style.RESET} Memasukkan 'session:4' (akan meng-evict session terlama: session:1)...")
    kv.set("session:4", {"user": "Diana"})
    print("  State setelah LRU eviction:")
    for k, v in kv.dump_keys().items():
        print(f"    - {k} -> {v['value']}")

    print(f"  {Style.MAGENTA}[TTL Test]{Style.RESET} Menunggu 1.6 detik untuk menguji automatic TTL expiration...")
    kv.set("temp_token", "SECRET_XYZ", ttl_seconds=1.0)
    time.sleep(1.2)
    val = kv.get("temp_token")
    status = f"{Style.RED}EXPIRED (None){Style.RESET}" if val is None else f"{Style.GREEN}{val}{Style.RESET}"
    print(f"  Lookup 'temp_token' setelah 1.2s -> {status}")
    print()

def demo_wide_column() -> None:
    print(f"{Style.CYAN}{Style.BOLD}▶ DEMO 3: Wide-Column Store (Cassandra Consistent Hashing Ring){Style.RESET}")
    nodes = ["Node-Alpha", "Node-Beta", "Node-Gamma", "Node-Delta"]
    cluster = CassandraRing(nodes)
    print("  Cassandra Ring Topology (Tokens):")
    for token, node in cluster.ring:
        print(f"    - Token Hash {token:3d}° -> Host [{node}]")

    orders = [
        ("cust_JKT_01", "order_1001", {"total": 500000, "status": "PAID"}),
        ("cust_BDG_99", "order_1002", {"total": 125000, "status": "PENDING"}),
        ("cust_SBY_42", "order_1003", {"total": 890000, "status": "SHIPPED"}),
        ("cust_JKT_01", "order_1004", {"total": 45000, "status": "DELIVERED"})
    ]

    print("\n  Melakukan distributed write berdasarkan partition key:")
    for p_key, c_key, cols in orders:
        routed_node = cluster.write_row(p_key, c_key, cols)
        print(f"    - Partition '{p_key}' -> Routed to {Style.BOLD}{routed_node}{Style.RESET}")
    print()

def demo_newsql_transaction() -> None:
    print(f"{Style.CYAN}{Style.BOLD}▶ DEMO 4: NewSQL ACID Distributed 2-Phase Commit (2PC){Style.RESET}")
    shard_a = DistributedNewSQLShard("Shard-Jakarta")
    shard_b = DistributedNewSQLShard("Shard-Singapore")
    coordinator = Coordinator2PC({"shard_jkt": shard_a, "shard_sg": shard_b})

    # Inisialisasi Saldo Awal
    shard_a.data["acc_101"] = 1_000_000
    shard_b.data["acc_202"] = 500_000
    print(f"  Kondisi Saldo Awal: acc_101 (JKT)=Rp{shard_a.data['acc_101']:,} | acc_202 (SG)=Rp{shard_b.data['acc_202']:,}")

    # Transaksi 1: Sukses
    tx1 = "TX-9001"
    print(f"\n  {Style.YELLOW}Mengeksekusi {tx1}:{Style.RESET} Transfer Rp300,000 dari acc_101 ke acc_202")
    success = coordinator.execute_transfer(tx1, "shard_jkt", "acc_101", "shard_sg", "acc_202", 300_000)
    print(f"  Hasil Transaksi: {Style.GREEN}COMMITTED (SUCCESS){Style.RESET}" if success else f"{Style.RED}ABORTED{Style.RESET}")
    print(f"  Saldo Terkini: acc_101 (JKT)=Rp{shard_a.data['acc_101']:,} | acc_202 (SG)=Rp{shard_b.data['acc_202']:,}")

    # Transaksi 2: Gagal (Saldo tidak cukup) -> Rollback atomik
    tx2 = "TX-9002"
    print(f"\n  {Style.YELLOW}Mengeksekusi {tx2}:{Style.RESET} Transfer Rp1,500,000 (Overdraft) dari acc_101 ke acc_202")
    success = coordinator.execute_transfer(tx2, "shard_jkt", "acc_101", "shard_sg", "acc_202", 1_500_000)
    print(f"  Hasil Transaksi: {Style.GREEN}COMMITTED{Style.RESET}" if success else f"{Style.RED}ABORTED & AUTOMATIC ROLLBACK (Insufficient Funds){Style.RESET}")
    print(f"  Saldo Konsisten: acc_101 (JKT)=Rp{shard_a.data['acc_101']:,} | acc_202 (SG)=Rp{shard_b.data['acc_202']:,}")
    print()

def main() -> None:
    banner()
    demo_document_store()
    demo_key_value_store()
    demo_wide_column()
    demo_newsql_transaction()
    print(f"{Style.BG_GREEN}{Style.WHITE}{Style.BOLD} [LAB SIMULATION COMPLETED SUCCESSFULLY] {Style.RESET}\n")

if __name__ == "__main__":
    main()
