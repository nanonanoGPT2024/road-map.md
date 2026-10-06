#!/usr/bin/env python3
"""
Lab Exercise: Data Persistence, Caching, & Event Streaming Engine Simulation
Chapter: BAB-08-Data-Persistence-Caching-Event-Streaming
Concepts:
  1. Relational Persistence & Connection Pool (database/sql semantics, ACID Tx)
  2. In-Memory Distributed Caching (Redis-like TTL, Cache-Aside, LRU Eviction)
  3. Partitioned Event Streaming (Kafka-like Log, Consumer Groups, Offset Commit)
  4. End-to-End Microservice Event-Driven Pipeline
"""

import sys
import time
import uuid
import threading
from typing import Dict, List, Optional, Tuple, Any
from collections import OrderedDict
from dataclasses import dataclass

# ANSI Terminal Color Palette
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
    BG_MAGENTA = "\033[45m"

def log_info(msg: str):
    print(f"  {Color.CYAN}ℹ [INFO]{Color.RESET} {msg}")

def log_success(msg: str):
    print(f"  {Color.GREEN}✔ [SUCCESS]{Color.RESET} {msg}")

def log_warn(msg: str):
    print(f"  {Color.YELLOW}⚠ [WARN]{Color.RESET} {msg}")

def log_error(msg: str):
    print(f"  {Color.RED}✖ [ERROR]{Color.RESET} {msg}")

def header(title: str):
    line = "━" * 68
    print(f"\n{Color.BOLD}{Color.MAGENTA}┏{line}┓{Color.RESET}")
    print(f"{Color.BOLD}{Color.MAGENTA}┃ {Color.WHITE}{title.center(66)} {Color.MAGENTA}┃{Color.RESET}")
    print(f"{Color.BOLD}{Color.MAGENTA}┗{line}┛{Color.RESET}\n")

# ============================================================================
# COMPONENT 1: RDBMS Connection Pool & ACID Transaction Manager (database/sql)
# ============================================================================

@dataclass
class Record:
    id: str
    username: str
    balance: float
    updated_at: float

class ConnectionPool:
    """Simulates Golang's database/sql DB connection pool mechanics."""
    def __init__(self, max_open: int = 5, max_idle: int = 2):
        self.max_open = max_open
        self.max_idle = max_idle
        self.active_conns = 0
        self.idle_conns = 0
        self.lock = threading.Lock()

    def acquire(self) -> int:
        with self.lock:
            if self.idle_conns > 0:
                self.idle_conns -= 1
                self.active_conns += 1
                return self.active_conns
            if self.active_conns < self.max_open:
                self.active_conns += 1
                return self.active_conns
            raise RuntimeError("Connection pool exhausted! MaxOpenConns reached.")

    def release(self):
        with self.lock:
            self.active_conns -= 1
            if self.idle_conns < self.max_idle:
                self.idle_conns += 1

class MockDatabase:
    """Simulates ACID Relational Database with Transaction Isolation."""
    def __init__(self, pool: ConnectionPool):
        self.pool = pool
        self.storage: Dict[str, Record] = {}
        self.lock = threading.Lock()

    def begin_tx(self) -> 'Transaction':
        conn_id = self.pool.acquire()
        return Transaction(self, conn_id)

class Transaction:
    def __init__(self, db: MockDatabase, conn_id: int):
        self.db = db
        self.conn_id = conn_id
        self.staging: Dict[str, Record] = {}
        self.is_active = True

    def query_user(self, user_id: str) -> Optional[Record]:
        if user_id in self.staging:
            return self.staging[user_id]
        with self.db.lock:
            return self.db.storage.get(user_id)

    def update_balance(self, user_id: str, new_balance: float):
        if not self.is_active:
            raise RuntimeError("Cannot execute query on inactive transaction!")
        curr = self.query_user(user_id)
        if not curr:
            raise ValueError(f"Record with ID '{user_id}' not found.")
        self.staging[user_id] = Record(
            id=curr.id,
            username=curr.username,
            balance=new_balance,
            updated_at=time.time()
        )

    def commit(self):
        if not self.is_active:
            raise RuntimeError("Transaction already finalized!")
        with self.db.lock:
            for k, v in self.staging.items():
                self.db.storage[k] = v
        self.is_active = False
        self.db.pool.release()

    def rollback(self):
        if not self.is_active:
            return
        self.staging.clear()
        self.is_active = False
        self.db.pool.release()

# ============================================================================
# COMPONENT 2: Distributed In-Memory Cache (Redis TTL & LRU Eviction)
# ============================================================================

class LRUCache:
    """Simulates Redis Cache with Capacity Eviction (LRU) and Expiration (TTL)."""
    def __init__(self, capacity: int = 3):
        self.capacity = capacity
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key not in self.cache:
                return None
            val, expiry = self.cache[key]
            if time.time() > expiry:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return val

    def set(self, key: str, value: Any, ttl_seconds: float = 2.0):
        with self.lock:
            now = time.time()
            if key in self.cache:
                self.cache.move_to_end(key)
            elif len(self.cache) >= self.capacity:
                evicted_key, _ = self.cache.popitem(last=False)
                log_warn(f"Cache Eviction: Max capacity reached. Evicted key '{evicted_key}'.")
            self.cache[key] = (value, now + ttl_seconds)

    def invalidate(self, key: str):
        with self.lock:
            if key in self.cache:
                del self.cache[key]

# ============================================================================
# COMPONENT 3: Event Streaming Engine (Kafka-like Partitioned Broker)
# ============================================================================

@dataclass
class Message:
    offset: int
    key: str
    payload: Dict[str, Any]
    timestamp: float

class Partition:
    def __init__(self, partition_id: int):
        self.id = partition_id
        self.log: List[Message] = []
        self.lock = threading.Lock()

    def append(self, key: str, payload: Dict[str, Any]) -> int:
        with self.lock:
            offset = len(self.log)
            msg = Message(offset=offset, key=key, payload=payload, timestamp=time.time())
            self.log.append(msg)
            return offset

class MessageBroker:
    def __init__(self, topic: str, partition_count: int = 2):
        self.topic = topic
        self.partitions = [Partition(i) for i in range(partition_count)]
        self.consumer_offsets: Dict[str, Dict[int, int]] = {}

    def _get_partition(self, key: str) -> Partition:
        idx = hash(key) % len(self.partitions)
        return self.partitions[idx]

    def produce(self, key: str, payload: Dict[str, Any]) -> Tuple[int, int]:
        partition = self._get_partition(key)
        offset = partition.append(key, payload)
        return partition.id, offset

    def consume(self, group_id: str) -> List[Tuple[int, Message]]:
        messages = []
        if group_id not in self.consumer_offsets:
            self.consumer_offsets[group_id] = {p.id: 0 for p in self.partitions}

        group_map = self.consumer_offsets[group_id]
        for p in self.partitions:
            committed = group_map.get(p.id, 0)
            with p.lock:
                for msg in p.log[committed:]:
                    messages.append((p.id, msg))
                    group_map[p.id] = msg.offset + 1
        return messages

# ============================================================================
# INTERACTIVE DEMO SCENARIOS
# ============================================================================

def demo_database_transactions():
    header("1. RDBMS CONNECTION POOL & ACID TRANSACTION SIMULATION")
    pool = ConnectionPool(max_open=2, max_idle=1)
    db = MockDatabase(pool)
    user_id = "usr_golang_01"

    # Pre-populate record
    db.storage[user_id] = Record(id=user_id, username="alice_crypto", balance=1000.0, updated_at=time.time())
    log_info(f"Initialized Database Record: ID={user_id}, Balance=1000.00 USD")

    log_info("Executing Transaction 1: Transfer with successful Commit...")
    tx1 = db.begin_tx()
    log_info(f"Connection acquired (Active Conns: {pool.active_conns}, Idle: {pool.idle_conns})")
    tx1.update_balance(user_id, 1500.0)
    tx1.commit()
    log_success(f"Tx1 Committed. Database Balance: {db.storage[user_id].balance} USD")

    log_info("Executing Transaction 2: Transfer with failure and Rollback...")
    tx2 = db.begin_tx()
    try:
        tx2.update_balance(user_id, 9999.0)
        log_warn("Simulating unhandled business violation (Zero Balance constraint)...")
        raise ArithmeticError("Credit check failed!")
    except Exception as e:
        log_error(f"Error caught: {e}. Executing Tx.Rollback()...")
        tx2.rollback()

    log_success(f"Tx2 Rolled Back. Balance safely intact: {db.storage[user_id].balance} USD")
    log_info(f"Pool status after operations: Active={pool.active_conns}, Idle={pool.idle_conns}")

def demo_caching_patterns():
    header("2. HIGH-PERFORMANCE CACHING (CACHE-ASIDE & LRU EVICTION)")
    cache = LRUCache(capacity=2)
    db_records = {
        "p:101": "MacBook Pro M3 Max",
        "p:102": "Sony WH-1000XM5",
        "p:103": "LG UltraFine 5K"
    }

    def get_product(prod_id: str) -> str:
        # Cache-Aside logic
        cached = cache.get(prod_id)
        if cached:
            log_success(f"{Color.GREEN}[CACHE HIT]{Color.RESET} Key='{prod_id}' => {cached}")
            return cached
        log_warn(f"{Color.YELLOW}[CACHE MISS]{Color.RESET} Key='{prod_id}'. Fetching from Database...")
        time.sleep(0.05) # Simulate DB latency
        data = db_records.get(prod_id, "Unknown Product")
        cache.set(prod_id, data, ttl_seconds=1.5)
        log_info(f"Stored '{prod_id}' into cache with TTL=1.5s")
        return data

    log_info("Accessing p:101 (First query - Database fetch):")
    get_product("p:101")

    log_info("\nAccessing p:101 again (Immediate subsequent query):")
    get_product("p:101")

    log_info("\nPopulating p:102 and p:103 to trigger LRU eviction (Capacity=2):")
    get_product("p:102")
    get_product("p:103")

    log_info("\nRe-querying p:101 (Should miss due to LRU eviction):")
    get_product("p:101")

    log_info("\nTesting TTL Expiration: Waiting 1.6 seconds...")
    time.sleep(1.6)
    log_info("Querying p:101 after TTL expiration:")
    get_product("p:101")

def demo_event_streaming():
    header("3. PARTITIONED EVENT STREAMING (KAFKA ARCHITECTURE)")
    broker = MessageBroker(topic="orders.completed", partition_count=2)
    group_id = "inventory_service"

    orders = [
        ("cust_01", {"order_id": "ORD-101", "amount": 120.5}),
        ("cust_02", {"order_id": "ORD-102", "amount": 45.0}),
        ("cust_01", {"order_id": "ORD-103", "amount": 310.0}),
        ("cust_03", {"order_id": "ORD-104", "amount": 890.0}),
    ]

    log_info(f"Publishing {len(orders)} events to topic '{broker.topic}' across 2 partitions...")
    for key, payload in orders:
        pid, off = broker.produce(key, payload)
        print(f"  {Color.BLUE}⚡ [PRODUCER]{Color.RESET} Key='{key}' -> Partition #{pid} at Offset #{off} | Event={payload['order_id']}")

    log_info(f"\nConsumer Group '{group_id}' reading uncommitted messages...")
    messages = broker.consume(group_id)
    for pid, msg in messages:
        print(f"  {Color.MAGENTA}✔ [CONSUMER GROUP: {group_id}]{Color.RESET} Partition #{pid} [Offset={msg.offset}] Processed {msg.payload['order_id']}")

    log_info("\nConsumer Group polling again (Checking offset persistence):")
    empty_check = broker.consume(group_id)
    if not empty_check:
        log_success("All offsets committed. No new pending messages (At-least-once delivery guaranteed).")

def demo_full_pipeline():
    header("4. INTEGRATED ARCHITECTURE: DB TX + CACHE + EVENT BUS")
    pool = ConnectionPool(max_open=5, max_idle=2)
    db = MockDatabase(pool)
    cache = LRUCache(capacity=5)
    broker = MessageBroker(topic="payment.settled", partition_count=2)

    user_id = "user_vip_99"
    db.storage[user_id] = Record(id=user_id, username="satya_nadella", balance=50000.0, updated_at=time.time())
    cache.set(user_id, db.storage[user_id], ttl_seconds=10.0)

    log_info(f"Initial State: User {user_id} Cached with Balance 50,000 USD")

    # Step 1: Execute Transaction
    log_info("\nStep 1: Processing Debit Transaction (-15,000 USD) in DB...")
    tx = db.begin_tx()
    current = tx.query_user(user_id)
    tx.update_balance(user_id, current.balance - 15000.0)
    tx.commit()
    log_success("DB Transaction Committed!")

    # Step 2: Cache Invalidation (Write-Through/Invalidation Pattern)
    log_info("Step 2: Invalidating stale cache entry...")
    cache.invalidate(user_id)
    log_success(f"Cache key '{user_id}' purged.")

    # Step 3: Produce Audit Event
    log_info("Step 3: Publishing PaymentSettledEvent to Message Broker...")
    p_id, offset = broker.produce(user_id, {
        "event_id": str(uuid.uuid4())[:8],
        "user_id": user_id,
        "amount_debited": 15000.0,
        "status": "SETTLED"
    })
    log_success(f"Event published to Partition {p_id} @ Offset {offset}")

    # Step 4: Downstream Consumer processing
    log_info("Step 4: Audit & Notification Service Consuming Event...")
    consumed = broker.consume("audit_workers")
    for pid, msg in consumed:
        log_info(f"Worker received: {msg.payload}")

    # Step 5: Read back data (Cache-Aside repopulation)
    log_info("Step 5: Client requests user profile (Triggering Cache-Aside miss + reload)...")
    if not cache.get(user_id):
        log_warn("Cache miss! Querying DB...")
        fresh_data = db.storage[user_id]
        cache.set(user_id, fresh_data, ttl_seconds=5.0)
        log_success(f"Fresh Balance Loaded & Cached: {fresh_data.balance} USD")

def interactive_menu():
    while True:
        print(f"\n{Color.BOLD}{Color.WHITE}======================================================{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN} BAB-08: GOLANG PERSISTENCE, CACHE & STREAMING LAB {Color.RESET}")
        print(f"{Color.BOLD}{Color.WHITE}======================================================{Color.RESET}")
        print("  1. Run Database Pool & ACID Transaction Simulation")
        print("  2. Run Cache-Aside & LRU/TTL Cache Simulation")
        print("  3. Run Distributed Message Broker / Event Stream")
        print("  4. Run Full Integrated Microservice Pipeline")
        print("  5. Run All Demonstrations Sequentially")
        print("  6. Exit")
        print(f"{Color.WHITE}------------------------------------------------------{Color.RESET}")

        try:
            choice = input(f"{Color.YELLOW}Pilih opsi [1-6]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if choice == "1":
            demo_database_transactions()
        elif choice == "2":
            demo_caching_patterns()
        elif choice == "3":
            demo_event_streaming()
        elif choice == "4":
            demo_full_pipeline()
        elif choice == "5":
            demo_database_transactions()
            demo_caching_patterns()
            demo_event_streaming()
            demo_full_pipeline()
        elif choice == "6" or choice.lower() == "q":
            log_info("Exiting lab simulation. Selamat belajar!")
            break
        else:
            log_error("Pilihan tidak valid, silakan coba lagi.")

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "--run"):
        demo_database_transactions()
        demo_caching_patterns()
        demo_event_streaming()
        demo_full_pipeline()
        return

    # Check if running in non-interactive environment (CI / pipe)
    if not sys.stdin.isatty():
        demo_database_transactions()
        demo_caching_patterns()
        demo_event_streaming()
        demo_full_pipeline()
        return

    interactive_menu()

if __name__ == "__main__":
    main()
