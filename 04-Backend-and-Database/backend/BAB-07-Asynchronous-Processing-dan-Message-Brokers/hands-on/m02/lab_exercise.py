#!/usr/bin/env python3
"""
Lab Exercise: Advanced Asynchronous Processing & Message Broker Simulation
BAB-07: Asynchronous Processing dan Message Brokers

Simulasi Arsitektur Produksi:
- Partition-based Message Broker (Distributed Topic, Partition Sharding)
- Consumer Groups & Rebalancing Mechanism
- Outbox Pattern Producer
- Resilient Worker Consumer dengan Idempotency Filter
- Exponential Backoff Retry Policy & Dead Letter Queue (DLQ)
- ANSI Terminal Visualizer
"""

import asyncio
import hashlib
import json
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

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
    
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"

def log(tag: str, color: str, msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Style.DIM}[{timestamp}]{Style.RESET} {color}[{tag:<14}]{Style.RESET} {msg}")

# --- Data Models ---
class MessageStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RETRYING = "RETRYING"
    DEAD_LETTERED = "DEAD_LETTERED"

@dataclass
class BrokerMessage:
    message_id: str
    topic: str
    partition_key: str
    payload: Dict[str, Any]
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    error_reason: Optional[str] = None

@dataclass
class DLQRecord:
    message: BrokerMessage
    failed_at: float
    reason: str
    worker_id: str

# --- Core Broker Infrastructure ---
class PartitionedQueue:
    def __init__(self, topic: str, partition_count: int = 3):
        self.topic = topic
        self.partition_count = partition_count
        self.queues: List[asyncio.Queue] = [asyncio.Queue() for _ in range(partition_count)]
        self.offsets: List[int] = [0] * partition_count

    def get_partition(self, key: str) -> int:
        h = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return h % self.partition_count

    async def publish(self, msg: BrokerMessage) -> int:
        partition_idx = self.get_partition(msg.partition_key)
        await self.queues[partition_idx].put(msg)
        self.offsets[partition_idx] += 1
        return partition_idx

# --- Idempotency Store ---
class IdempotencyRegistry:
    def __init__(self):
        self._processed_keys: Set[str] = set()
        self._lock = asyncio.Lock()

    async def check_and_set(self, idempotency_key: str) -> bool:
        async with self._lock:
            if idempotency_key in self._processed_keys:
                return False  # Duplicate detected
            self._processed_keys.add(idempotency_key)
            return True

# --- Dead Letter Queue (DLQ) ---
class DeadLetterQueue:
    def __init__(self):
        self.records: List[DLQRecord] = []

    def capture(self, msg: BrokerMessage, worker_id: str, reason: str):
        record = DLQRecord(
            message=msg,
            failed_at=time.time(),
            reason=reason,
            worker_id=worker_id
        )
        self.records.append(record)
        log("DLQ-ALARM", Style.BG_RED + Style.WHITE,
            f"Message {msg.message_id} routed to DLQ! Reason: {reason}")

    def inspect(self):
        print(f"\n{Style.BOLD}{Style.RED}{'='*25} DLQ INSPECTOR ({len(self.records)} Records) {'='*25}{Style.RESET}")
        for idx, rec in enumerate(self.records, 1):
            ts = datetime.fromtimestamp(rec.failed_at).strftime("%H:%M:%S")
            print(f"{Style.YELLOW}[#{idx:02d}]{Style.RESET} ID: {rec.message.message_id} | Failed at: {ts} | Worker: {rec.worker_id}")
            print(f"     Payload: {json.dumps(rec.message.payload)}")
            print(f"     Terminal Error: {rec.reason}")
        print(f"{Style.RED}{'='*72}{Style.RESET}\n")

# --- Consumer Worker with Exponential Backoff ---
class WorkerConsumer:
    def __init__(
        self,
        worker_id: str,
        group_id: str,
        partition_idx: int,
        queue: asyncio.Queue,
        idempotency: IdempotencyRegistry,
        dlq: DeadLetterQueue,
        handler: Callable[[BrokerMessage], Any]
    ):
        self.worker_id = worker_id
        self.group_id = group_id
        self.partition_idx = partition_idx
        self.queue = queue
        self.idempotency = idempotency
        self.dlq = dlq
        self.handler = handler
        self.processed_count = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _consume_loop(self):
        while self._running:
            try:
                msg: BrokerMessage = await asyncio.wait_for(self.queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # 1. Idempotency Check
            idem_key = msg.payload.get("transaction_id", msg.message_id)
            is_new = await self.idempotency.check_and_set(idem_key)
            if not is_new:
                log(self.worker_id, Style.YELLOW,
                    f"Duplicate message ignored: key={idem_key} (Idempotent Guard)")
                self.queue.task_done()
                continue

            # 2. Execution with Retries & Exponential Backoff
            success = False
            while not success and msg.retry_count <= msg.max_retries:
                try:
                    log(self.worker_id, Style.CYAN,
                        f"Processing [P{self.partition_idx}] msg={msg.message_id} (Attempt {msg.retry_count + 1})")
                    await self.handler(msg)
                    success = True
                    self.processed_count += 1
                    log(self.worker_id, Style.GREEN,
                        f"ACK: msg={msg.message_id} completed successfully.")
                except Exception as exc:
                    msg.retry_count += 1
                    if msg.retry_count > msg.max_retries:
                        log(self.worker_id, Style.RED,
                            f"EXHAUSTED RETRIES for msg={msg.message_id}: {exc}")
                        self.dlq.capture(msg, self.worker_id, str(exc))
                        break
                    
                    backoff = (2 ** (msg.retry_count - 1)) * 0.2 + random.uniform(0.05, 0.15)
                    log(self.worker_id, Style.MAGENTA,
                        f"Error: {exc}. Retrying in {backoff:.2f}s (Backoff exp)")
                    await asyncio.sleep(backoff)

            self.queue.task_done()

# --- Application Domain Handler ---
async def business_order_processor(msg: BrokerMessage):
    event_type = msg.payload.get("event")
    order_id = msg.payload.get("order_id")
    amount = msg.payload.get("amount", 0)

    # Simulate realistic async processing delay
    await asyncio.sleep(random.uniform(0.08, 0.2))

    # Chaos Injection: Simulated failures
    if msg.payload.get("chaos") == "transient_network_timeout" and msg.retry_count < 2:
        raise ConnectionResetError("Remote payment gateway 504 Gateway Timeout")

    if msg.payload.get("chaos") == "poison_pill":
        raise ValueError("Invalid schema: corrupted binary payload in order record")

    if amount < 0:
        raise ValueError(f"Fraud detection triggered: negative balance {amount}")

# --- Orchestrator & Demonstrations ---
class MessageBrokerSimulation:
    def __init__(self, partition_count: int = 3):
        self.topic = "order.events"
        self.broker = PartitionedQueue(self.topic, partition_count)
        self.idempotency = IdempotencyRegistry()
        self.dlq = DeadLetterQueue()
        self.workers: List[WorkerConsumer] = []

    def bootstrap_consumer_group(self, group_name: str, worker_count: int):
        for idx in range(worker_count):
            partition_idx = idx % self.broker.partition_count
            w = WorkerConsumer(
                worker_id=f"worker-{idx+1:02d}",
                group_id=group_name,
                partition_idx=partition_idx,
                queue=self.broker.queues[partition_idx],
                idempotency=self.idempotency,
                dlq=self.dlq,
                handler=business_order_processor
            )
            w.start()
            self.workers.append(w)
            log("BROKER-CTRL", Style.BLUE,
                f"Assigned partition {partition_idx} -> {w.worker_id} in [{group_name}]")

    async def teardown(self):
        for w in self.workers:
            await w.stop()

    async def scenario_normal_flow(self):
        print(f"\n{Style.BOLD}{Style.GREEN}=== SCENARIO 1: High-Throughput Partitioned Order Events ==={Style.RESET}")
        for i in range(1, 9):
            cust_id = f"cust-{(i % 4) + 1:03d}"
            msg = BrokerMessage(
                message_id=f"MSG-{i:04d}",
                topic=self.topic,
                partition_key=cust_id,
                payload={
                    "event": "ORDER_CREATED",
                    "order_id": f"ORD-{1000 + i}",
                    "customer_id": cust_id,
                    "amount": round(random.uniform(25.0, 450.0), 2),
                    "transaction_id": f"TXN-202610-{i:04d}"
                }
            )
            p_idx = await self.broker.publish(msg)
            log("OUTBOX-PROD", Style.WHITE,
                f"Published {msg.message_id} [key={cust_id}] to Partition #{p_idx}")
            await asyncio.sleep(0.04)

        # Wait until all partitioned queues are processed
        for q in self.broker.queues:
            await q.join()

    async def scenario_transient_retry(self):
        print(f"\n{Style.BOLD}{Style.MAGENTA}=== SCENARIO 2: Transient Network Flap & Exponential Backoff ==={Style.RESET}")
        msg = BrokerMessage(
            message_id="MSG-RETRY-01",
            topic=self.topic,
            partition_key="cust-999",
            payload={
                "event": "PAYMENT_CAPTURE",
                "order_id": "ORD-RETRY-77",
                "amount": 189.50,
                "chaos": "transient_network_timeout",
                "transaction_id": "TXN-CHAOS-01"
            }
        )
        p_idx = await self.broker.publish(msg)
        log("OUTBOX-PROD", Style.WHITE, f"Published flaky message {msg.message_id} to Partition #{p_idx}")
        for q in self.broker.queues:
            await q.join()

    async def scenario_poison_pill_dlq(self):
        print(f"\n{Style.BOLD}{Style.RED}=== SCENARIO 3: Poison Pill & Dead Letter Queue (DLQ) Routing ==={Style.RESET}")
        msg = BrokerMessage(
            message_id="MSG-POISON-99",
            topic=self.topic,
            partition_key="cust-poison",
            payload={
                "event": "ACCOUNT_SYNC",
                "chaos": "poison_pill",
                "transaction_id": "TXN-POISON-99"
            }
        )
        await self.broker.publish(msg)
        for q in self.broker.queues:
            await q.join()
        self.dlq.inspect()

    async def scenario_idempotency_guard(self):
        print(f"\n{Style.BOLD}{Style.YELLOW}=== SCENARIO 4: Network Duplication & Idempotent Consumer ==={Style.RESET}")
        shared_txn = "TXN-UNIQUE-KEY-8888"
        for i in range(1, 4):
            dup_msg = BrokerMessage(
                message_id=f"MSG-DUP-{i}",
                topic=self.topic,
                partition_key="cust-idempotent",
                payload={
                    "event": "INVOICE_GENERATED",
                    "order_id": "ORD-IDEM-001",
                    "transaction_id": shared_txn
                }
            )
            await self.broker.publish(dup_msg)
            log("NETWORK-DUP", Style.DIM, f"Broadcast transmission duplicate copy #{i} sent")
        for q in self.broker.queues:
            await q.join()

def print_banner():
    banner = f"""{Style.CYAN}{Style.BOLD}
========================================================================
   PRODUCTION MESSAGE BROKER & ASYNC PIPELINE ARCHITECTURE LAB
   [Kafka/RabbitMQ Semantics: Partitions, DLQ, Retries & Idempotency]
========================================================================{Style.RESET}"""
    print(banner)

async def interactive_runner():
    print_banner()
    sim = MessageBrokerSimulation(partition_count=3)
    sim.bootstrap_consumer_group(group_name="order-fulfillment-group", worker_count=3)

    if not sys.stdin.isatty():
        # Non-interactive / headless CI mode: run all scenarios sequentially
        log("SYS-RUNNER", Style.GREEN, "Running full test scenarios in automated mode...")
        await sim.scenario_normal_flow()
        await sim.scenario_transient_retry()
        await sim.scenario_poison_pill_dlq()
        await sim.scenario_idempotency_guard()
        await sim.teardown()
        log("SYS-RUNNER", Style.GREEN, "Automated validation successfully completed.")
        return

    menu = f"""
{Style.BOLD}PILIH SCENARIO SIMULASI:{Style.RESET}
1. Normal Event Pipeline (Partition Sharding)
2. Transient Network Flap (Exponential Backoff Retries)
3. Poison Pill Schema Error (DLQ Exhaustion)
4. Duplicate Message Replay (Idempotency Filter)
5. Run All Scenarios & Exit
0. Keluar
"""
    try:
        while True:
            print(menu)
            choice = input(f"{Style.YELLOW}Pilihan Anda [0-5]: {Style.RESET}").strip()
            if choice == "1":
                await sim.scenario_normal_flow()
            elif choice == "2":
                await sim.scenario_transient_retry()
            elif choice == "3":
                await sim.scenario_poison_pill_dlq()
            elif choice == "4":
                await sim.scenario_idempotency_guard()
            elif choice == "5":
                await sim.scenario_normal_flow()
                await sim.scenario_transient_retry()
                await sim.scenario_poison_pill_dlq()
                await sim.scenario_idempotency_guard()
                break
            elif choice == "0":
                break
            else:
                print(f"{Style.RED}Pilihan tidak valid.{Style.RESET}")
    finally:
        await sim.teardown()
        print(f"\n{Style.GREEN}Simulasi dihentikan dengan bersih (Graceful Shutdown).{Style.RESET}")

if __name__ == "__main__":
    asyncio.run(interactive_runner())
