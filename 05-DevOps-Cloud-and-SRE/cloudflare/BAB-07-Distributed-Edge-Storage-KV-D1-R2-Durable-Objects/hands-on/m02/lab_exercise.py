#!/usr/bin/env python3
"""
Lab Exercise: Cloudflare Distributed Edge Storage Architecture Simulator
BAB-07: Distributed Edge Storage (KV, D1, R2, Durable Objects)

Simulates production-grade interactions between Cloudflare's serverless edge primitives:
- Workers KV: Low-latency eventually consistent key-value cache across global PoPs
- Cloudflare D1: Distributed serverless relational database (SQLite at the edge)
- Cloudflare R2: S3-compatible zero-egress object storage with ETag generation
- Durable Objects (DO): Globally unique stateful coordination actors with strict serializability
"""

import sys
import time
import json
import random
import hashlib
import sqlite3
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# --- Terminal ANSI Color Constants ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[48;5;236m"

def banner() -> None:
    print(f"{Style.CYAN}{Style.BOLD}")
    print("=" * 78)
    print("   CLOUDFLARE DISTRIBUTED EDGE STORAGE SIMULATOR (BAB-07 ARCHITECTURE)   ")
    print("        [KV Cache] + [D1 Relational SQL] + [R2 Buckets] + [Durable Objects]     ")
    print("=" * 78 + f"{Style.RESET}")

# --- 1. Cloudflare Workers KV (Eventual Consistency & Multi-PoP Replication) ---
@dataclass
class KVEntry:
    value: str
    metadata: Dict[str, Any]
    version: int
    updated_at: float

class CloudflareWorkersKV:
    """Simulates distributed Workers KV with global PoP eventual propagation."""
    POPS = ["SIN (Singapore)", "NRT (Tokyo)", "LHR (London)", "SFO (San Francisco)", "FRA (Frankfurt)"]

    def __init__(self, namespace: str = "PROD_SESSION_CACHE"):
        self.namespace = namespace
        self.primary_store: Dict[str, KVEntry] = {}
        self.pop_caches: Dict[str, Dict[str, KVEntry]] = {pop: {} for pop in self.POPS}
        self.lock = threading.Lock()

    def put(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        with self.lock:
            version = 1
            if key in self.primary_store:
                version = self.primary_store[key].version + 1
            entry = KVEntry(value=value, metadata=metadata or {}, version=version, updated_at=time.time())
            self.primary_store[key] = entry
            # Immediate write to primary region, asynchronous sync to other PoPs
            origin_pop = self.POPS[0]
            self.pop_caches[origin_pop][key] = entry
            print(f"{Style.GREEN}[KV:PUT]{Style.RESET} Namespace={self.namespace} Key='{key}' Version=v{version} synced to origin {origin_pop}")

    def propagate_to_edges(self, key: str) -> None:
        """Simulates background global propagation delay across Cloudflare Anycast PoPs."""
        with self.lock:
            if key not in self.primary_store:
                print(f"{Style.RED}[KV:ERROR] Key '{key}' not found in primary store.{Style.RESET}")
                return
            entry = self.primary_store[key]
            for pop in self.POPS[1:]:
                # Simulate realistic edge sync latency (10ms - 80ms)
                latency = random.uniform(12.0, 75.0)
                self.pop_caches[pop][key] = entry
                print(f"  └─► {Style.CYAN}Replicated to PoP {pop:<22}{Style.RESET} | Propagation Latency: {latency:.2f}ms")

    def get_at_pop(self, pop: str, key: str) -> Optional[str]:
        with self.lock:
            cache = self.pop_caches.get(pop, {})
            if key in cache:
                print(f"{Style.GREEN}[KV:HIT]{Style.RESET} PoP={pop} Key='{key}' -> Value='{cache[key].value}' (v{cache[key].version})")
                return cache[key].value
            print(f"{Style.YELLOW}[KV:MISS]{Style.RESET} PoP={pop} Key='{key}' (Not yet propagated or expired)")
            return None


# --- 2. Cloudflare D1 (Serverless Distributed Relational SQLite) ---
class CloudflareD1Database:
    """Simulates Cloudflare D1 with read replication and primary write leader."""
    def __init__(self, db_name: str = "production-ecommerce-d1"):
        self.db_name = db_name
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    customer_email TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            self.conn.commit()

    def execute_write(self, order_id: str, email: str, sku: str, amount_cents: int) -> bool:
        """Primary region write coordinator."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO orders (id, customer_email, sku, amount_cents, status) VALUES (?, ?, ?, ?, ?)",
                (order_id, email, sku, amount_cents, "CONFIRMED")
            )
            self.conn.commit()
            print(f"{Style.MAGENTA}[D1:WRITE_PRIMARY]{Style.RESET} Executed SQL INSERT on primary coordinator: OrderID={order_id}")
            return True

    def query_read_replica(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Simulates read query executed on nearby Edge Read Replica."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT id, customer_email, sku, amount_cents, status, created_at FROM orders ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": r[0],
                    "customer_email": r[1],
                    "sku": r[2],
                    "amount_cents": r[3],
                    "status": r[4],
                    "created_at": r[5]
                })
            print(f"{Style.CYAN}[D1:READ_REPLICA]{Style.RESET} Fetched {len(results)} rows via edge replica (Query Latency: ~4.1ms)")
            return results


# --- 3. Cloudflare R2 (S3-Compatible Object Storage) ---
@dataclass
class R2Object:
    key: str
    content_bytes: bytes
    content_type: str
    etag: str
    size: int
    created_at: float

class CloudflareR2Storage:
    """Simulates Cloudflare R2 bucket with zero egress fees and automated ETag hashing."""
    def __init__(self, bucket_name: str = "prod-media-assets"):
        self.bucket_name = bucket_name
        self.objects: Dict[str, R2Object] = {}
        self.lock = threading.Lock()

    def put_object(self, key: str, payload: str, content_type: str = "application/json") -> R2Object:
        with self.lock:
            data = payload.encode("utf-8")
            etag = hashlib.md5(data).hexdigest()
            obj = R2Object(
                key=key,
                content_bytes=data,
                content_type=content_type,
                etag=etag,
                size=len(data),
                created_at=time.time()
            )
            self.objects[key] = obj
            print(f"{Style.BLUE}[R2:PUT_OBJECT]{Style.RESET} Bucket='{self.bucket_name}' Key='{key}' ETag={etag} Size={obj.size} bytes (Zero-Egress)")
            return obj

    def get_object(self, key: str) -> Optional[R2Object]:
        with self.lock:
            obj = self.objects.get(key)
            if obj:
                print(f"{Style.GREEN}[R2:GET_OBJECT]{Style.RESET} 200 OK | Key='{key}' ETag={obj.etag} Type={obj.content_type}")
                return obj
            print(f"{Style.RED}[R2:404_NOT_FOUND]{Style.RESET} Object '{key}' does not exist in bucket '{self.bucket_name}'")
            return None


# --- 4. Cloudflare Durable Objects (DO) - Strongly Consistent Actor ---
class InventoryDurableObject:
    """
    Simulates a Cloudflare Durable Object instance coordinating real-time stock
    with single-threaded execution guarantees and atomic state mutation.
    """
    def __init__(self, object_id: str, initial_stock: int = 10):
        self.object_id = object_id
        self.stock = initial_stock
        self.lock = threading.Lock()
        self.txn_counter = 0

    def reserve_stock(self, client_id: str, quantity: int) -> bool:
        """Atomic reservation executed strictly inside DO single-threaded boundary."""
        with self.lock:
            self.txn_counter += 1
            time.sleep(0.01) # Simulated microsecond transaction lock
            if self.stock >= quantity:
                self.stock -= quantity
                print(f"{Style.GREEN}[DO:TXN #{self.txn_counter:03d}]{Style.RESET} ActorID={self.object_id} RESERVED {quantity} units for {client_id}. Remaining Stock: {self.stock}")
                return True
            else:
                print(f"{Style.RED}[DO:TXN #{self.txn_counter:03d}]{Style.RESET} ActorID={self.object_id} REJECTED {quantity} units for {client_id}. Out of stock! (Current: {self.stock})")
                return False


# --- Simulation Orchestration Engine ---
class CloudflareEdgeOrchestrator:
    def __init__(self):
        self.kv = CloudflareWorkersKV()
        self.d1 = CloudflareD1Database()
        self.r2 = CloudflareR2Storage()
        self.durable_objects: Dict[str, InventoryDurableObject] = {}

    def get_or_create_do(self, sku: str) -> InventoryDurableObject:
        if sku not in self.durable_objects:
            # Deterministic ID based on SKU
            do_id = f"do-sku-{sku}-{hashlib.sha256(sku.encode()).hexdigest()[:8]}"
            self.durable_objects[sku] = InventoryDurableObject(object_id=do_id, initial_stock=5)
        return self.durable_objects[sku]

    def process_edge_checkout(self, order_id: str, email: str, sku: str, quantity: int, price_cents: int) -> None:
        """
        Demonstrates complete multi-primitive Cloudflare edge architecture pipeline:
        1. Durable Object: Coordinate concurrent race-free inventory check.
        2. D1: Persist transactional relational order record.
        3. R2: Archive immutable invoice artifact without egress fees.
        4. KV: Cache user session token and fast order state globally.
        """
        print(f"\n{Style.BOLD}{Style.WHITE}>>> Processing Edge Checkout Pipeline: Order {order_id} <<<{Style.RESET}")
        
        # Step 1: Durable Object Atomic Check
        do_actor = self.get_or_create_do(sku)
        success = do_actor.reserve_stock(client_id=email, quantity=quantity)
        if not success:
            print(f"{Style.RED}[PIPELINE:FAILED] Transaction aborted at Durable Object level.{Style.RESET}")
            return

        # Step 2: D1 SQL Transaction
        self.d1.execute_write(order_id=order_id, email=email, sku=sku, amount_cents=price_cents)

        # Step 3: R2 Invoice Storage
        invoice_payload = json.dumps({
            "order_id": order_id,
            "customer": email,
            "sku": sku,
            "qty": quantity,
            "total_cents": price_cents,
            "timestamp": time.time()
        }, indent=2)
        r2_key = f"invoices/2026/10/{order_id}.json"
        self.r2.put_object(key=r2_key, payload=invoice_payload)

        # Step 4: Workers KV Edge Session Update
        kv_key = f"user_last_order:{email}"
        self.kv.put(key=kv_key, value=order_id, metadata={"sku": sku, "status": "CONFIRMED"})
        print(f"{Style.YELLOW}Triggering asynchronous KV edge replication across Anycast PoPs...{Style.RESET}")
        self.kv.propagate_to_edges(kv_key)
        
        print(f"{Style.GREEN}{Style.BOLD}✓ Order {order_id} successfully finalized across edge storage primitives!{Style.RESET}\n")


def interactive_menu(orch: CloudflareEdgeOrchestrator) -> None:
    while True:
        print(f"\n{Style.BOLD}=== Cloudflare Edge Storage Control Panel ==={Style.RESET}")
        print(f"[{Style.CYAN}1{Style.RESET}] Test Workers KV (Put, Get, Global PoP Eventual Propagation)")
        print(f"[{Style.CYAN}2{Style.RESET}] Test Cloudflare D1 (Write Transaction & Read Replica Query)")
        print(f"[{Style.CYAN}3{Style.RESET}] Test Cloudflare R2 (Upload Payload & Inspect Zero-Egress Metadata)")
        print(f"[{Style.CYAN}4{Style.RESET}] Test Durable Objects (Concurrent Race Condition Simulation)")
        print(f"[{Style.CYAN}5{Style.RESET}] Run Full E2E Production Architecture Workflow")
        print(f"[{Style.CYAN}6{Style.RESET}] Exit Simulator")
        
        try:
            choice = input(f"{Style.BOLD}Select an option (1-6): {Style.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            key = input("Enter KV Key (e.g. config:feature_flag): ").strip() or "config:feature_flag"
            val = input("Enter KV Value (e.g. true): ").strip() or "true"
            orch.kv.put(key, val)
            print("Testing read at Origin PoP:")
            orch.kv.get_at_pop(orch.kv.POPS[0], key)
            print("Propagating globally across Anycast PoPs:")
            orch.kv.propagate_to_edges(key)
            print("Testing read at Tokyo (NRT) PoP:")
            orch.kv.get_at_pop("NRT (Tokyo)", key)

        elif choice == "2":
            order_id = f"ord-{random.randint(1000, 9999)}"
            email = "devops-engineer@enterprise.io"
            sku = "SKU-CLOUDFLARE-PRO"
            amount = 29900
            print(f"Executing D1 Write for Order {order_id}...")
            orch.d1.execute_write(order_id, email, sku, amount)
            print("\nExecuting D1 Read Replica Query:")
            rows = orch.d1.query_read_replica(limit=5)
            for r in rows:
                print(f"  • {r['id']} | {r['customer_email']} | SKU: {r['sku']} | Amount: ${r['amount_cents']/100:.2f} | Status: {r['status']}")

        elif choice == "3":
            file_key = input("Enter R2 Object Key (e.g. assets/app.wasm): ").strip() or "assets/app.wasm"
            content = input("Enter Object Body: ").strip() or '{"version": "2.4.1", "status": "deployed"}'
            orch.r2.put_object(file_key, content)
            print("\nRetrieving Object from R2:")
            orch.r2.get_object(file_key)

        elif choice == "4":
            print(f"\n{Style.YELLOW}Simulating 8 concurrent requests competing for 5 inventory items via Durable Object Actor...{Style.RESET}")
            sku = "LIMITED-EDITION-WAF-TSHIRT"
            actor = orch.get_or_create_do(sku)
            threads = []
            for i in range(8):
                t = threading.Thread(
                    target=actor.reserve_stock,
                    args=(f"user_thread_{i+1}@cloudflare.com", 1)
                )
                threads.append(t)
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            print(f"{Style.GREEN}Durable Object coordination completed with zero overselling.{Style.RESET}")

        elif choice == "5":
            order_id = f"E2E-{random.randint(10000, 99999)}"
            orch.process_edge_checkout(
                order_id=order_id,
                email="alice@cloud-architect.org",
                sku="ENTERPRISE-EDGE-BUNDLE",
                quantity=2,
                price_cents=99900
            )

        elif choice == "6":
            print(f"{Style.GREEN}Shutting down simulator. Happy Edge Computing!{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Invalid selection. Please choose 1-6.{Style.RESET}")

def main():
    banner()
    orchestrator = CloudflareEdgeOrchestrator()
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print(f"{Style.YELLOW}Running automated verification suite...{Style.RESET}")
        orchestrator.process_edge_checkout("AUTO-101", "bot@test.com", "SKU-AUTO", 1, 4900)
        sys.exit(0)
    interactive_menu(orchestrator)

if __name__ == "__main__":
    main()
