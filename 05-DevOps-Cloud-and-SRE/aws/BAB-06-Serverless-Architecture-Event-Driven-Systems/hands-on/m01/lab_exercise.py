#!/usr/bin/env python3
"""
AWS Serverless Architecture & Event-Driven Systems Lab Exercise
Simulasi teknis interaktif fondasi serverless:
1. EventBridge Event Bus & Routing Engine
2. SQS Queue & Dead Letter Queue (DLQ) with Exponential Retry
3. Lambda Execution Environment (Cold Start vs Warm Start, Concurrency Limits)
4. DynamoDB Idempotent State Store (Conditional Writes & De-duplication)
"""

import sys
import time
import uuid
import json
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# ANSI Color Codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def log(tag: str, msg: str, color: str = Colors.CYAN):
    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Colors.DIM}[{ts}]{Colors.RESET} {color}{Colors.BOLD}[{tag:<14}]{Colors.RESET} {msg}")

@dataclass
class EventEnvelope:
    source: str
    detail_type: str
    detail: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    retry_count: int = 0

@dataclass
class LambdaInstance:
    instance_id: str
    is_warm: bool = False
    busy_until: float = 0.0
    processed_count: int = 0

class DynamoDBStore:
    """Simulasi DynamoDB Table dengan Idempotency Key & Conditional Updates"""
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.items: Dict[str, Dict[str, Any]] = {}

    def put_idempotent(self, pk: str, data: Dict[str, Any], idempotency_token: str) -> bool:
        if pk in self.items:
            existing = self.items[pk]
            if existing.get("_idempotency_token") == idempotency_token:
                log("DYNAMODB", f"Idempotency match for key '{pk}'. Return cached record (No duplicate write).", Colors.YELLOW)
                return True
            else:
                log("DYNAMODB", f"Conflict/Duplicate key '{pk}' with different token!", Colors.RED)
                return False
        
        record = {**data, "_idempotency_token": idempotency_token, "_created_at": datetime.utcnow().isoformat()}
        self.items[pk] = record
        log("DYNAMODB", f"Conditional PutItem SUCCESS on '{self.table_name}' for PK={pk}", Colors.GREEN)
        return True

    def scan(self) -> Dict[str, Dict[str, Any]]:
        return self.items

class DeadLetterQueue:
    """Simulasi SQS Dead Letter Queue (DLQ)"""
    def __init__(self, name: str):
        self.name = name
        self.messages: List[Dict[str, Any]] = []

    def send(self, event: EventEnvelope, reason: str):
        record = {
            "message_id": str(uuid.uuid4()),
            "event": event,
            "failure_reason": reason,
            "moved_at": datetime.utcnow().isoformat()
        }
        self.messages.append(record)
        log("SQS-DLQ", f"Message {event.event_id[:8]} routing to DLQ '{self.name}'. Reason: {reason}", Colors.RED)

    def size(self) -> int:
        return len(self.messages)

class SQSQueue:
    """Simulasi SQS Standard Queue dengan Max Receive Count & DLQ Target"""
    def __init__(self, name: str, dlq: DeadLetterQueue, max_receive_count: int = 3):
        self.name = name
        self.dlq = dlq
        self.max_receive_count = max_receive_count
        self.buffer: List[EventEnvelope] = []

    def enqueue(self, event: EventEnvelope):
        self.buffer.append(event)
        log("SQS", f"Message enqueued into '{self.name}'. Queue depth: {len(self.buffer)}", Colors.CYAN)

    def dequeue(self) -> Optional[EventEnvelope]:
        if not self.buffer:
            return None
        return self.buffer.pop(0)

class LambdaService:
    """Simulasi AWS Lambda dengan Cold/Warm Start Lifecycle, Concurrency Limit, dan Timeout"""
    def __init__(self, function_name: str, max_concurrency: int = 3, cold_start_ms: int = 150):
        self.function_name = function_name
        self.max_concurrency = max_concurrency
        self.cold_start_ms = cold_start_ms
        self.instances: List[LambdaInstance] = []

    def _acquire_instance(self) -> LambdaInstance:
        now = time.time()
        # Cari warm and idle instance
        for inst in self.instances:
            if inst.busy_until <= now:
                inst.is_warm = True
                return inst
        
        # Buat instance baru jika limit konkurrensi belum tercapai
        if len(self.instances) < self.max_concurrency:
            new_id = f"inst-{len(self.instances)+1:02d}"
            new_inst = LambdaInstance(instance_id=new_id, is_warm=False)
            self.instances.append(new_inst)
            return new_inst

        # Concurrency limit reached -> Throttling
        raise RuntimeError("429 TooManyRequestsException: Lambda Function Throttled (Concurrency Limit Reached)")

    def invoke(self, event: EventEnvelope, db: DynamoDBStore, fail_rate: float = 0.0) -> bool:
        try:
            inst = self._acquire_instance()
        except RuntimeError as e:
            log("LAMBDA", str(e), Colors.RED)
            return False

        now = time.time()
        if not inst.is_warm:
            log("LAMBDA", f"[{inst.instance_id}] COLD START init ({self.cold_start_ms}ms overhead)...", Colors.YELLOW)
            time.sleep(self.cold_start_ms / 1000.0)
            inst.is_warm = True
        else:
            log("LAMBDA", f"[{inst.instance_id}] WARM START invocation reused container.", Colors.GREEN)

        # Simulasi eksekusi function runtime
        exec_duration = random.uniform(0.04, 0.08)
        inst.busy_until = now + exec_duration
        time.sleep(exec_duration)
        inst.processed_count += 1

        # Simulasi flakiness / exception
        if random.random() < fail_rate:
            log("LAMBDA", f"[{inst.instance_id}] Process error: Unhandled Exception in Business Logic!", Colors.RED)
            return False

        order_id = event.detail.get("order_id", f"ord-{event.event_id[:6]}")
        token = event.detail.get("idempotency_token", event.event_id)
        
        db.put_idempotent(order_id, event.detail, token)
        log("LAMBDA", f"[{inst.instance_id}] Handler completed successfully. RequestId: {event.event_id[:8]}", Colors.GREEN)
        return True

class EventBridgeRouter:
    """Simulasi Amazon EventBridge Custom Event Bus & Rule Evaluation Engine"""
    def __init__(self, bus_name: str = "production-event-bus"):
        self.bus_name = bus_name
        self.rules: List[Dict[str, Any]] = []

    def add_rule(self, name: str, source: str, detail_type: str, target_queue: SQSQueue):
        self.rules.append({
            "name": name,
            "source": source,
            "detail_type": detail_type,
            "target": target_queue
        })
        log("EVENTBRIDGE", f"Rule attached: '{name}' matches [source={source}, type={detail_type}]", Colors.BLUE)

    def put_events(self, events: List[EventEnvelope]) -> int:
        routed_count = 0
        for ev in events:
            matched = False
            for rule in self.rules:
                if rule["source"] == ev.source and rule["detail_type"] == ev.detail_type:
                    log("EVENTBRIDGE", f"Event {ev.event_id[:8]} MATCHED rule '{rule['name']}' -> Routing to SQS", Colors.CYAN)
                    rule["target"].enqueue(ev)
                    matched = True
                    routed_count += 1
            if not matched:
                log("EVENTBRIDGE", f"Event {ev.event_id[:8]} DROPPED (No matching Event Pattern).", Colors.DIM)
        return routed_count

class ServerlessLabSimulator:
    """Koordinator Simulator Event-Driven Serverless Architecture"""
    def __init__(self):
        self.dlq = DeadLetterQueue("orders-order-processing-dlq")
        self.queue = SQSQueue("orders-processing-queue", dlq=self.dlq, max_receive_count=3)
        self.bus = EventBridgeRouter("ecommerce-events")
        self.lambda_fn = LambdaService("OrderProcessorFunction", max_concurrency=2, cold_start_ms=120)
        self.dynamodb = DynamoDBStore("OrdersTable")

        # Setup standard rules
        self.bus.add_rule(
            name="RouteOrderCreated",
            source="ecommerce.checkout",
            detail_type="OrderPlaced",
            target_queue=self.queue
        )

    def process_queue_batch(self, simulated_failure_rate: float = 0.0):
        print(f"\n{Colors.BOLD}{'='*25} PROCESSING SQS BATCH WITH LAMBDA {'='*25}{Colors.RESET}")
        processed = 0
        while True:
            event = self.queue.dequeue()
            if not event:
                break
            
            processed += 1
            event.retry_count += 1
            log("SQS", f"Delivering event {event.event_id[:8]} (Attempt {event.retry_count}/{self.queue.max_receive_count})", Colors.CYAN)
            
            success = self.lambda_fn.invoke(event, self.dynamodb, fail_rate=simulated_failure_rate)
            if not success:
                if event.retry_count >= self.queue.max_receive_count:
                    self.dlq.send(event, reason="Exceeded MaxReceiveCount (3 failures)")
                else:
                    backoff = 0.05 * (2 ** (event.retry_count - 1))
                    log("SQS", f"Transient failure. Backing off {backoff:.2f}s and re-enqueuing...", Colors.YELLOW)
                    time.sleep(backoff)
                    self.queue.enqueue(event)

        if processed == 0:
            log("RUNNER", "Queue is currently empty.", Colors.DIM)
        else:
            log("RUNNER", f"Batch run complete. {processed} message invocations evaluated.", Colors.GREEN)

    def display_status(self):
        print(f"\n{Colors.BOLD}{Colors.HEADER}=== AWS SERVERLESS ARCHITECTURE COMPONENT STATUS ==={Colors.RESET}")
        print(f"{Colors.BOLD}1. EventBridge Bus:{Colors.RESET}   {self.bus.bus_name} (Active Rules: {len(self.bus.rules)})")
        print(f"{Colors.BOLD}2. SQS Primary Queue:{Colors.RESET} {self.queue.name} | Backlog Depth: {Colors.CYAN}{len(self.queue.buffer)}{Colors.RESET}")
        print(f"{Colors.BOLD}3. SQS DLQ:{Colors.RESET}           {self.dlq.name} | Poison Messages: {Colors.RED}{self.dlq.size()}{Colors.RESET}")
        print(f"{Colors.BOLD}4. Lambda Workers:{Colors.RESET}    {self.lambda_fn.function_name} | Pool Size: {len(self.lambda_fn.instances)}/{self.lambda_fn.max_concurrency}")
        for inst in self.lambda_fn.instances:
            print(f"   -> [{inst.instance_id}] Warm={inst.is_warm} Invocations={inst.processed_count}")
        print(f"{Colors.BOLD}5. DynamoDB Table:{Colors.RESET}    {self.dynamodb.table_name} | Stored Items: {Colors.GREEN}{len(self.dynamodb.items)}{Colors.RESET}")
        for pk, item in self.dynamodb.items.items():
            print(f"   -> PK: {pk:<12} Amount: ${item.get('amount', 0):<6} Item: {item.get('item', 'N/A')}")
        print(f"{Colors.BOLD}{'='*53}{Colors.RESET}\n")

def run_interactive():
    lab = ServerlessLabSimulator()
    print(f"{Colors.BOLD}{Colors.GREEN}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║     AWS SERVERLESS ARCHITECTURE & EVENT-DRIVEN LAB SIMULATOR      ║")
    print("║          EventBridge + SQS + Lambda + DLQ + DynamoDB              ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")

    options = {
        "1": "Publish Valid Event (ecommerce.checkout / OrderPlaced)",
        "2": "Publish Unmatched Event (ecommerce.payment / PaymentAuthorized)",
        "3": "Simulate High Concurrency Batch (Cold Starts & Concurrency Limit)",
        "4": "Process Queue (Normal execution / No failures)",
        "5": "Process Queue with Injected Lambda Errors (Observe Retries & DLQ)",
        "6": "Simulate Idempotency Re-execution (Re-send identical Token)",
        "7": "Inspect Architectural State (DynamoDB, SQS, DLQ, Containers)",
        "8": "Exit Lab"
    }

    auto_token = str(uuid.uuid4())

    while True:
        print(f"{Colors.BOLD}Available Lab Scenarios:{Colors.RESET}")
        for k, v in options.items():
            print(f"  [{Colors.CYAN}{k}{Colors.RESET}] {v}")
        
        try:
            choice = input(f"\n{Colors.BOLD}Select scenario (1-8): {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if choice == "1":
            order_id = f"ORD-{random.randint(1000, 9999)}"
            ev = EventEnvelope(
                source="ecommerce.checkout",
                detail_type="OrderPlaced",
                detail={"order_id": order_id, "item": "Cloud Architecture Handbook", "amount": 49.99}
            )
            log("CLIENT", f"Dispatching Event {ev.event_id[:8]} to EventBridge...", Colors.BLUE)
            lab.bus.put_events([ev])

        elif choice == "2":
            ev = EventEnvelope(
                source="ecommerce.payment",
                detail_type="PaymentAuthorized",
                detail={"txn_id": "TX-9921", "amount": 49.99}
            )
            log("CLIENT", f"Dispatching Event with unconfigured rule pattern...", Colors.BLUE)
            lab.bus.put_events([ev])

        elif choice == "3":
            print(f"\n{Colors.YELLOW}Triggering 5 rapid orders to exceed Lambda concurrency limit (max=2)...{Colors.RESET}")
            batch = []
            for i in range(5):
                batch.append(EventEnvelope(
                    source="ecommerce.checkout",
                    detail_type="OrderPlaced",
                    detail={"order_id": f"ORD-BURST-{i+1}", "item": "AWS Serverless Key", "amount": 10.0}
                ))
            lab.bus.put_events(batch)
            lab.process_queue_batch(simulated_failure_rate=0.0)

        elif choice == "4":
            lab.process_queue_batch(simulated_failure_rate=0.0)

        elif choice == "5":
            print(f"\n{Colors.RED}Simulating high lambda failure rate (75% error) to trigger DLQ eviction...{Colors.RESET}")
            # Ensure at least 1 message in queue
            ev = EventEnvelope(
                source="ecommerce.checkout",
                detail_type="OrderPlaced",
                detail={"order_id": f"ORD-FAIL-{random.randint(100, 999)}", "item": "Faulty Microservice Component", "amount": 120.0}
            )
            lab.bus.put_events([ev])
            lab.process_queue_batch(simulated_failure_rate=0.85)

        elif choice == "6":
            print(f"\n{Colors.YELLOW}Testing DynamoDB Idempotency Token De-duplication...{Colors.RESET}")
            ev1 = EventEnvelope(
                source="ecommerce.checkout",
                detail_type="OrderPlaced",
                detail={"order_id": "ORD-IDEMPOTENT-001", "item": "Sub-Second Provisioning", "amount": 19.99, "idempotency_token": auto_token}
            )
            ev2 = EventEnvelope(
                source="ecommerce.checkout",
                detail_type="OrderPlaced",
                detail={"order_id": "ORD-IDEMPOTENT-001", "item": "Sub-Second Provisioning (Duplicate)", "amount": 19.99, "idempotency_token": auto_token}
            )
            lab.bus.put_events([ev1, ev2])
            lab.process_queue_batch(simulated_failure_rate=0.0)

        elif choice == "7":
            lab.display_status()

        elif choice == "8":
            print(f"{Colors.GREEN}Serverless Architecture Lab concluded.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Invalid option, please choose 1-8.{Colors.RESET}")

if __name__ == "__main__":
    run_interactive()
