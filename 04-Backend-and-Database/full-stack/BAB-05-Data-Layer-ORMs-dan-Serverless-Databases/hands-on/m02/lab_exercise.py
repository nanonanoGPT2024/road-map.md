#!/usr/bin/env python3
"""
BAB-05: Data Layer, ORMs, and Serverless Databases
Hands-on Lab Exercise: Production-Grade Resilient Data Architecture Simulation

Topics Covered:
1. Connection Pooling & Warm Pool Management (Serverless Scale-to-Zero vs Dedicated)
2. Read-Write Splitting (Primary Writer vs Read Replicas)
3. Optimistic Concurrency Control (Version-based Locking)
4. Cache-Aside Pattern with Edge Invalidation
5. Telemetry & ANSI Visualizer
"""

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    BG_BLUE = "\033[44m\033[97m"
    BG_GREEN = "\033[42m\033[97m"
    BG_RED = "\033[41m\033[97m"


class EngineMode(Enum):
    COLD_START = "COLD_START"
    WARM = "WARM"
    EXHAUSTED = "EXHAUSTED"


@dataclass
class DocumentRecord:
    id: str
    title: str
    content: str
    version: int
    updated_at: float


@dataclass
class QueryStats:
    total_reads: int = 0
    total_writes: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    optimistic_lock_conflicts: int = 0
    cold_starts: int = 0
    read_replica_queries: int = 0


class ConnectionPool:
    """Simulates a serverless connection proxy (e.g. Prisma Accelerate / AWS RDS Proxy)"""

    def __init__(self, pool_size: int = 5, cold_start_ms: int = 250):
        self.pool_size = pool_size
        self.cold_start_ms = cold_start_ms
        self._available_connections: int = pool_size
        self._is_cold: bool = True
        self._lock = asyncio.Lock()

    async def acquire(self) -> Tuple[str, EngineMode]:
        async with self._lock:
            mode = EngineMode.WARM
            if self._is_cold:
                await asyncio.sleep(self.cold_start_ms / 1000.0)
                self._is_cold = False
                mode = EngineMode.COLD_START

            if self._available_connections <= 0:
                return "CONN-EXHAUSTED", EngineMode.EXHAUSTED

            self._available_connections -= 1
            conn_id = f"conn-{uuid.uuid4().hex[:6]}"
            return conn_id, mode

    async def release(self, conn_id: str):
        async with self._lock:
            if self._available_connections < self.pool_size:
                self._available_connections += 1


class EdgeCacheStore:
    """Simulates distributed edge KV cache layer (e.g. Upstash Redis / Cloudflare KV)"""

    def __init__(self):
        self._cache: Dict[str, DocumentRecord] = {}

    def get(self, key: str) -> Optional[DocumentRecord]:
        return self._cache.get(key)

    def set(self, key: str, record: DocumentRecord):
        self._cache[key] = record

    def invalidate(self, key: str):
        self._cache.pop(key, None)


class ServerlessDataCluster:
    """Simulates distributed database cluster with Primary Writer & Read-Replicas"""

    def __init__(self, replica_count: int = 2):
        self.primary_store: Dict[str, DocumentRecord] = {}
        self.replicas: List[Dict[str, DocumentRecord]] = [{} for _ in range(replica_count)]
        self.edge_cache = EdgeCacheStore()
        self.proxy_pool = ConnectionPool(pool_size=4, cold_start_ms=180)
        self.stats = QueryStats()
        self._mutation_lock = asyncio.Lock()

    async def write_transaction(self, record_id: str, title: str, content: str, expected_version: int) -> bool:
        """Optimistic Concurrency Control write operation with replication & cache invalidation"""
        conn_id, mode = await self.proxy_pool.acquire()
        if mode == EngineMode.EXHAUSTED:
            print(f"  {ANSI.RED}[POOL FAILURE]{ANSI.RESET} Connection pool exhausted during write!")
            return False
        if mode == EngineMode.COLD_START:
            self.stats.cold_starts += 1

        try:
            self.stats.total_writes += 1
            await asyncio.sleep(0.04)  # Network / IO latency simulation

            async with self._mutation_lock:
                current_doc = self.primary_store.get(record_id)
                curr_version = current_doc.version if current_doc else 0

                # Optimistic Lock Validation
                if curr_version != expected_version:
                    self.stats.optimistic_lock_conflicts += 1
                    print(
                        f"  {ANSI.YELLOW}[OCC CONFLICT]{ANSI.RESET} Record {record_id} version mismatch! "
                        f"(Expected: {expected_version}, Found: {curr_version})"
                    )
                    return False

                new_record = DocumentRecord(
                    id=record_id,
                    title=title,
                    content=content,
                    version=curr_version + 1,
                    updated_at=time.time(),
                )
                self.primary_store[record_id] = new_record

                # Invalidate Edge Cache
                self.edge_cache.invalidate(record_id)

                # Asynchronous Replica Propagation
                asyncio.create_task(self._replicate_to_followers(record_id, new_record))
                return True
        finally:
            await self.proxy_pool.release(conn_id)

    async def _replicate_to_followers(self, record_id: str, record: DocumentRecord):
        await asyncio.sleep(0.02)  # Replication lag simulation
        for replica in self.replicas:
            replica[record_id] = record

    async def read_query(self, record_id: str) -> Optional[DocumentRecord]:
        """Read-Aside: Cache -> Replica Pool -> Cache Refill"""
        self.stats.total_reads += 1

        # 1. Edge Cache Probe
        cached = self.edge_cache.get(record_id)
        if cached:
            self.stats.cache_hits += 1
            return cached

        self.stats.cache_misses += 1

        # 2. Read from Replicas (Load Balanced)
        conn_id, mode = await self.proxy_pool.acquire()
        if mode == EngineMode.COLD_START:
            self.stats.cold_starts += 1

        try:
            await asyncio.sleep(0.03)  # Database Read IO
            self.stats.read_replica_queries += 1
            replica_target = random.choice(self.replicas)
            doc = replica_target.get(record_id) or self.primary_store.get(record_id)

            if doc:
                self.edge_cache.set(record_id, doc)
            return doc
        finally:
            await self.proxy_pool.release(conn_id)


def print_banner():
    print(f"\n{ANSI.BG_BLUE}  LAB EXERCISE: ADVANCED SERVERLESS DATA LAYER ARCHITECTURE  {ANSI.RESET}")
    print(f"{ANSI.CYAN}========================================================================{ANSI.RESET}")
    print("Simulating ORM Transactions, Optimistic Locking, Connection Pooling & Edge Caching")
    print(f"{ANSI.CYAN}========================================================================{ANSI.RESET}\n")


def print_dashboard(cluster: ServerlessDataCluster):
    s = cluster.stats
    hit_rate = (s.cache_hits / s.total_reads * 100) if s.total_reads > 0 else 0.0

    print(f"\n{ANSI.BOLD}--- Live Data Telemetry Dashboard ---{ANSI.RESET}")
    print(f"Total Reads:               {ANSI.CYAN}{s.total_reads}{ANSI.RESET}")
    print(f"Total Writes:              {ANSI.MAGENTA}{s.total_writes}{ANSI.RESET}")
    print(f"Cache Hit Rate:            {ANSI.GREEN if hit_rate > 50 else ANSI.YELLOW}{hit_rate:.1f}%{ANSI.RESET} ({s.cache_hits} hits / {s.cache_misses} misses)")
    print(f"Replica Read Dispatches:   {ANSI.BLUE}{s.read_replica_queries}{ANSI.RESET}")
    print(f"Serverless Cold Starts:    {ANSI.YELLOW}{s.cold_starts}{ANSI.RESET}")
    print(f"OCC Conflicts Detected:    {ANSI.RED}{s.optimistic_lock_conflicts}{ANSI.RESET}")
    print(f"Primary Store Size:        {ANSI.BOLD}{len(cluster.primary_store)} records{ANSI.RESET}")
    print("--------------------------------------\n")


async def run_scenario_1_crud_and_cache(cluster: ServerlessDataCluster):
    print(f"{ANSI.BOLD}Scenario 1: Cold Start + Read-Aside + Cache Invalidation Lifecycle{ANSI.RESET}")
    doc_id = "doc-alpha"

    print(f"  [1] Creating record '{doc_id}' on Primary Writer (Cold Start expected)...")
    ok = await cluster.write_transaction(doc_id, "System Architecture", "v1 Initial Draft", expected_version=0)
    print(f"      Result: {ANSI.GREEN if ok else ANSI.RED}{'SUCCESS' if ok else 'FAILED'}{ANSI.RESET}")

    print(f"  [2] Read request #1 for '{doc_id}' (Cache Miss -> DB Replica -> Seed Cache)...")
    res1 = await cluster.read_query(doc_id)
    print(f"      Loaded: {res1.title} [v{res1.version}]")

    print(f"  [3] Read request #2 for '{doc_id}' (Edge Cache Hit)...")
    res2 = await cluster.read_query(doc_id)
    print(f"      Loaded from Cache: {res2.title} [v{res2.version}]")

    print(f"  [4] Updating record '{doc_id}' with version=1 (Will invalidate Edge Cache)...")
    ok = await cluster.write_transaction(doc_id, "System Architecture", "v2 Revised Schema", expected_version=1)
    print(f"      Update Result: {ANSI.GREEN if ok else ANSI.RED}{'SUCCESS' if ok else 'FAILED'}{ANSI.RESET}")

    print(f"  [5] Read request #3 for '{doc_id}' (Post-invalidation Cache Miss)...")
    res3 = await cluster.read_query(doc_id)
    print(f"      Refreshed from Replica: {res3.title} [v{res3.version}] - Content: {res3.content}")


async def run_scenario_2_concurrent_optimistic_locking(cluster: ServerlessDataCluster):
    print(f"\n{ANSI.BOLD}Scenario 2: Concurrent Mutation & Optimistic Concurrency Control (OCC){ANSI.RESET}")
    doc_id = "doc-finance-ledger"
    await cluster.write_transaction(doc_id, "Ledger Balance", "Balance: $1000", expected_version=0)

    print(f"  Simulating 3 simultaneous microservices trying to update '{doc_id}' from version 1...")

    async def worker_update(worker_name: str, new_val: str):
        # All workers saw version 1 initially
        print(f"    Worker [{worker_name}] attempting update with expected_version=1...")
        success = await cluster.write_transaction(doc_id, "Ledger Balance", new_val, expected_version=1)
        if success:
            print(f"    Worker [{worker_name}] {ANSI.GREEN}COMMITTED CHANGE{ANSI.RESET} ({new_val})")
        else:
            print(f"    Worker [{worker_name}] {ANSI.RED}ROLLED BACK (OCC Conflict){ANSI.RESET}")

    tasks = [
        worker_update("Payroll-Service", "Balance: $850"),
        worker_update("Subscription-Billing", "Balance: $920"),
        worker_update("Refund-Processor", "Balance: $1100"),
    ]
    await asyncio.gather(*tasks)


async def run_scenario_3_stress_burst(cluster: ServerlessDataCluster):
    print(f"\n{ANSI.BOLD}Scenario 3: Serverless Traffic Burst (Connection Pool Under Load){ANSI.RESET}")
    target_ids = ["doc-alpha", "doc-finance-ledger"]

    async def burst_reader(i: int):
        target = random.choice(target_ids)
        await cluster.read_query(target)

    print(f"  Firing 25 asynchronous read requests across connection pool...")
    start_t = time.perf_counter()
    await asyncio.gather(*(burst_reader(i) for i in range(25)))
    elapsed = time.perf_counter() - start_t
    print(f"  {ANSI.GREEN}Burst complete in {elapsed * 1000:.2f} ms!{ANSI.RESET}")


async def main():
    print_banner()
    cluster = ServerlessDataCluster(replica_count=3)

    print(f"{ANSI.CYAN}>>> Executing Phase 1: Core Data Lifecycle & Cache Operations <<<{ANSI.RESET}")
    await run_scenario_1_crud_and_cache(cluster)

    print(f"\n{ANSI.CYAN}>>> Executing Phase 2: High Concurrency Conflict Resolution <<<{ANSI.RESET}")
    await run_scenario_2_concurrent_optimistic_locking(cluster)

    print(f"\n{ANSI.CYAN}>>> Executing Phase 3: Traffic Spike Stress Test <<<{ANSI.RESET}")
    await run_scenario_3_stress_burst(cluster)

    print_dashboard(cluster)
    print(f"{ANSI.BG_GREEN} ALL ARCHITECTURAL SIMULATION TESTS COMPLETED SUCCESSFULLY! {ANSI.RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
