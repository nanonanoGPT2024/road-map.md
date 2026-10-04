#!/usr/bin/env python3
"""
AWS Serverless Architecture & Event-Driven Systems Production Simulation Lab
Module: M02 Hands-On Lab Exercise
Topic: API Gateway -> EventBridge -> SQS/DLQ -> Lambda Worker -> DynamoDB + Streams
"""

import sys
import time
import uuid
import json
import random
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# ANSI Colors for Rich Terminal Output
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"
    BG_BLUE = "\033[44m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"


@dataclass
class EventEnvelope:
    id: str
    source: str
    detail_type: str
    time_epoch: float
    detail: Dict[str, Any]
    correlation_id: str
    retry_count: int = 0


@dataclass
class DynamoDBRecord:
    pk: str
    sk: str
    version: int
    payload: Dict[str, Any]
    ttl: int


class MockDynamoDB:
    def __init__(self):
        self.table: Dict[str, DynamoDBRecord] = {}
        self.stream_log: List[Dict[str, Any]] = []

    def put_item(self, pk: str, sk: str, payload: Dict[str, Any], expected_version: Optional[int] = None) -> bool:
        key = f"{pk}#{sk}"
        current = self.table.get(key)

        if expected_version is not None:
            if current and current.version != expected_version:
                return False  # ConditionalCheckFailedException

        new_version = (current.version + 1) if current else 1
        record = DynamoDBRecord(
            pk=pk,
            sk=sk,
            version=new_version,
            payload=payload,
            ttl=int(time.time()) + 86400
        )
        self.table[key] = record

        # DynamoDB Streams emission
        self.stream_log.append({
            "eventName": "MODIFY" if current else "INSERT",
            "keys": {"PK": pk, "SK": sk},
            "newImage": payload,
            "version": new_version
        })
        return True

    def get_item(self, pk: str, sk: str) -> Optional[DynamoDBRecord]:
        return self.table.get(f"{pk}#{sk}")


class DeadLetterQueue:
    def __init__(self, name: str):
        self.name = name
        self.messages: List[EventEnvelope] = []

    def enqueue(self, event: EventEnvelope, reason: str):
        event.detail["dlq_reason"] = reason
        self.messages.append(event)
        print(f"  {Color.BG_RED}{Color.BOLD} [DLQ] {Color.RESET} {Color.RED}Event routed to {self.name}: {event.id} | Reason: {reason}{Color.RESET}")


class SQSQueue:
    def __init__(self, name: str, max_retries: int = 3, dlq: Optional[DeadLetterQueue] = None):
        self.name = name
        self.max_retries = max_retries
        self.dlq = dlq
        self.queue: List[EventEnvelope] = []

    def send_message(self, event: EventEnvelope):
        self.queue.append(event)
        print(f"  {Color.CYAN}[SQS:{self.name}]{Color.RESET} Message enqueued: {Color.BOLD}{event.id}{Color.RESET}")

    def poll(self) -> Optional[EventEnvelope]:
        if self.queue:
            return self.queue.pop(0)
        return None


class EventBridgeBus:
    def __init__(self, name: str = "production-ecommerce-bus"):
        self.name = name
        self.subscribers: Dict[str, List[SQSQueue]] = {}

    def add_rule(self, detail_type_pattern: str, target_queue: SQSQueue):
        if detail_type_pattern not in self.subscribers:
            self.subscribers[detail_type_pattern] = []
        self.subscribers[detail_type_pattern].append(target_queue)

    def put_events(self, events: List[EventEnvelope]):
        for ev in events:
            print(f"  {Color.MAGENTA}[EventBridge:{self.name}]{Color.RESET} Ingested event {Color.YELLOW}'{ev.detail_type}'{Color.RESET} (Corr-ID: {ev.correlation_id[:8]})")
            matched = False
            for pattern, targets in self.subscribers.items():
                if pattern == "*" or pattern == ev.detail_type:
                    matched = True
                    for tgt in targets:
                        tgt.send_message(ev)
            if not matched:
                print(f"  {Color.GRAY}[EventBridge]{Color.RESET} No routing rule matched for {ev.detail_type}")


class ServerlessOrderSagaSimulator:
    def __init__(self):
        self.dynamodb = MockDynamoDB()
        self.order_dlq = DeadLetterQueue("Order-Failed-DLQ")
        self.payment_queue = SQSQueue("PaymentProcessingQueue", max_retries=2, dlq=self.order_dlq)
        self.inventory_queue = SQSQueue("InventoryReservationQueue", max_retries=2, dlq=self.order_dlq)
        self.notification_queue = SQSQueue("CustomerNotificationQueue", max_retries=3, dlq=self.order_dlq)
        
        self.bus = EventBridgeBus("production-core-eventbus")
        self._setup_eventbridge_rules()

        # Idempotency token storage
        self.idempotency_cache: Dict[str, Dict[str, Any]] = {}

    def _setup_eventbridge_rules(self):
        self.bus.add_rule("OrderPlaced", self.payment_queue)
        self.bus.add_rule("PaymentProcessed", self.inventory_queue)
        self.bus.add_rule("OrderCompleted", self.notification_queue)

    def api_gateway_ingress(self, payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        """Simulates API Gateway HTTP POST /orders with Idempotency & Schema Validation."""
        print(f"\n{Color.BG_BLUE}{Color.BOLD} API GATEWAY INGRESS {Color.RESET} HTTP POST /v1/orders (Idempotency-Key: {idempotency_key[:8]}...)")

        # 1. Idempotency Check
        if idempotency_key in self.idempotency_cache:
            cached_resp = self.idempotency_cache[idempotency_key]
            print(f"  {Color.YELLOW}[API-GW 200 CACHED]{Color.RESET} Returning cached response for idempotency key.")
            return cached_resp

        # 2. Validation
        required = ["customer_id", "items", "amount"]
        for field_name in required:
            if field_name not in payload:
                resp = {"statusCode": 400, "error": f"Missing required field: {field_name}"}
                print(f"  {Color.RED}[API-GW 400 Bad Request]{Color.RESET} {resp['error']}")
                return resp

        # 3. Create Event
        order_id = f"ord-{uuid.uuid4().hex[:8]}"
        correlation_id = str(uuid.uuid4())
        
        event = EventEnvelope(
            id=str(uuid.uuid4()),
            source="com.retail.orderservice",
            detail_type="OrderPlaced",
            time_epoch=time.time(),
            detail={
                "order_id": order_id,
                "customer_id": payload["customer_id"],
                "items": payload["items"],
                "amount": payload["amount"],
                "status": "PENDING"
            },
            correlation_id=correlation_id
        )

        # Write initial order to DynamoDB
        self.dynamodb.put_item(
            pk=f"ORDER#{order_id}",
            sk="METADATA",
            payload={"status": "INITIALIZED", "amount": payload["amount"]}
        )

        # Ingest into EventBridge
        self.bus.put_events([event])

        response = {
            "statusCode": 202,
            "order_id": order_id,
            "status": "ACCEPTED",
            "correlation_id": correlation_id,
            "message": "Order accepted for asynchronous processing."
        }
        self.idempotency_cache[idempotency_key] = response
        return response

    def lambda_payment_worker(self, event: EventEnvelope, simulate_chaos: bool = False):
        """Simulates Payment Lambda consumer."""
        print(f"\n  {Color.BOLD}{Color.BLUE}[Lambda: PaymentProcessor]{Color.RESET} Invoked for Order: {event.detail['order_id']}")
        time.sleep(0.1)

        if simulate_chaos and random.random() < 0.6:
            event.retry_count += 1
            if event.retry_count >= self.payment_queue.max_retries:
                print(f"  {Color.RED}[Lambda: PaymentProcessor]{Color.RESET} Max retries ({self.payment_queue.max_retries}) exceeded! Payment Gateway Timeout.")
                self.order_dlq.enqueue(event, "PAYMENT_GATEWAY_UNAVAILABLE_EXHAUSTED_RETRIES")
                return
            else:
                print(f"  {Color.YELLOW}[Lambda: PaymentProcessor]{Color.RESET} Transient failure. Re-queuing (Retry {event.retry_count}/{self.payment_queue.max_retries})...")
                self.payment_queue.send_message(event)
                return

        # Payment success
        print(f"  {Color.GREEN}[Lambda: PaymentProcessor]{Color.RESET} Payment of ${event.detail['amount']} approved.")
        self.dynamodb.put_item(
            pk=f"ORDER#{event.detail['order_id']}",
            sk="PAYMENT",
            payload={"status": "PAID", "transaction_ref": f"txn_{uuid.uuid4().hex[:6]}"}
        )

        # Emit next event
        next_event = EventEnvelope(
            id=str(uuid.uuid4()),
            source="com.retail.paymentservice",
            detail_type="PaymentProcessed",
            time_epoch=time.time(),
            detail=event.detail,
            correlation_id=event.correlation_id
        )
        self.bus.put_events([next_event])

    def lambda_inventory_worker(self, event: EventEnvelope, out_of_stock: bool = False):
        """Simulates Inventory Reservation Worker."""
        print(f"\n  {Color.BOLD}{Color.MAGENTA}[Lambda: InventoryWorker]{Color.RESET} Checking stock for Order: {event.detail['order_id']}")
        time.sleep(0.1)

        if out_of_stock:
            print(f"  {Color.RED}[Lambda: InventoryWorker]{Color.RESET} Stock depletion detected! Triggering compensating transaction.")
            self.order_dlq.enqueue(event, "INSUFFICIENT_STOCK_COMPENSATING_REFUND")
            self.dynamodb.put_item(
                pk=f"ORDER#{event.detail['order_id']}",
                sk="METADATA",
                payload={"status": "FAILED_CANCELLED", "reason": "OUT_OF_STOCK"}
            )
            return

        print(f"  {Color.GREEN}[Lambda: InventoryWorker]{Color.RESET} Items reserved successfully in warehouse.")
        self.dynamodb.put_item(
            pk=f"ORDER#{event.detail['order_id']}",
            sk="METADATA",
            payload={"status": "CONFIRMED_RESERVED"}
        )

        completed_event = EventEnvelope(
            id=str(uuid.uuid4()),
            source="com.retail.inventoryservice",
            detail_type="OrderCompleted",
            time_epoch=time.time(),
            detail=event.detail,
            correlation_id=event.correlation_id
        )
        self.bus.put_events([completed_event])

    def lambda_notification_worker(self, event: EventEnvelope):
        """Simulates SES/SNS Push Notification Worker."""
        print(f"\n  {Color.BOLD}{Color.GREEN}[Lambda: NotificationService]{Color.RESET} Dispatching receipt email to customer {event.detail['customer_id']}...")
        time.sleep(0.05)
        print(f"  {Color.GREEN}[SES Dispatched]{Color.RESET} Order {event.detail['order_id']} is confirmed.")

    def run_drain_cycle(self, simulate_payment_chaos: bool = False, simulate_inventory_failure: bool = False):
        """Drains SQS queues until processing completes."""
        print(f"\n{Color.GRAY}--- SQS Event Loop Polling Started ---{Color.RESET}")
        cycles = 0
        while cycles < 10:
            cycles += 1
            acted = False

            # Drain payment queue
            msg = self.payment_queue.poll()
            if msg:
                acted = True
                self.lambda_payment_worker(msg, simulate_chaos=simulate_payment_chaos)

            # Drain inventory queue
            msg = self.inventory_queue.poll()
            if msg:
                acted = True
                self.lambda_inventory_worker(msg, out_of_stock=simulate_inventory_failure)

            # Drain notification queue
            msg = self.notification_queue.poll()
            if msg:
                acted = True
                self.lambda_notification_worker(msg)

            if not acted:
                break
        print(f"{Color.GRAY}--- SQS Event Loop Polling Settled ({cycles} cycles) ---{Color.RESET}")


def render_dashboard(sim: ServerlessOrderSagaSimulator):
    print(f"\n{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}       AWS SERVERLESS ARCHITECTURE RESILIENCE DASHBOARD{Color.RESET}")
    print(f"{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"  {Color.BOLD}DynamoDB Table State Records:{Color.RESET} {len(sim.dynamodb.table)}")
    for k, v in sim.dynamodb.table.items():
        print(f"    - {Color.YELLOW}{k}{Color.RESET} (Version: {v.version}) -> {json.dumps(v.payload)}")
    
    print(f"\n  {Color.BOLD}DynamoDB Stream CDC Log (CDC stream count):{Color.RESET} {len(sim.dynamodb.stream_log)}")
    print(f"  {Color.BOLD}Dead Letter Queue (DLQ) Discards:{Color.RESET} {len(sim.order_dlq.messages)}")
    for dlq_item in sim.order_dlq.messages:
        print(f"    - {Color.RED}DLQ Event ID: {dlq_item.id} | Type: {dlq_item.detail_type} | Reason: {dlq_item.detail.get('dlq_reason')}{Color.RESET}")
    print(f"{Color.CYAN}{'=' * 75}{Color.RESET}\n")


def print_banner():
    banner = f"""{Color.BOLD}{Color.YELLOW}
  ======================================================================
     AWS ADVANCED SERVERLESS & EVENT-DRIVEN ENTERPRISE ARCHITECTURE
          Lab Simulation: API Gateway + EventBridge + SQS + Lambda
  ======================================================================{Color.RESET}
    """
    print(banner)


def main():
    print_banner()
    sim = ServerlessOrderSagaSimulator()

    while True:
        print(f"{Color.BOLD}Select Simulation Scenario:{Color.RESET}")
        print(f"  {Color.GREEN}[1]{Color.RESET} Standard Happy Path (Order Placement -> SQS -> Payment -> Inventory -> Notification)")
        print(f"  {Color.YELLOW}[2]{Color.RESET} Idempotent Replay Protection Test (Duplicate API Gateway Request)")
        print(f"  {Color.RED}[3]{Color.RESET} Payment Chaos & DLQ Fallback (Transient Network Faults -> Retry -> Poison Message to DLQ)")
        print(f"  {Color.MAGENTA}[4]{Color.RESET} Inventory Depletion Compensating Action (Out-of-Stock Fallback)")
        print(f"  {Color.CYAN}[5]{Color.RESET} View Real-time DynamoDB & DLQ Architecture Metrics")
        print(f"  {Color.GRAY}[0] Exit Lab{Color.RESET}")

        try:
            choice = input(f"\n{Color.BOLD}Enter scenario [0-5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)

        if choice == "1":
            req_key = f"idem-key-{uuid.uuid4().hex[:6]}"
            order_data = {"customer_id": "cust-8821", "items": ["cloud-architect-handbook"], "amount": 99.50}
            resp = sim.api_gateway_ingress(order_data, req_key)
            sim.run_drain_cycle()
            render_dashboard(sim)

        elif choice == "2":
            fixed_key = "idempotency-token-enterprise-999"
            order_data = {"customer_id": "cust-enterprise-vip", "items": ["aws-solution-pro-cert"], "amount": 300.00}
            print(f"\n{Color.BOLD}--> Request 1 (First attempt):{Color.RESET}")
            resp1 = sim.api_gateway_ingress(order_data, fixed_key)
            sim.run_drain_cycle()

            print(f"\n{Color.BOLD}--> Request 2 (Duplicate immediate replay):{Color.RESET}")
            resp2 = sim.api_gateway_ingress(order_data, fixed_key)
            render_dashboard(sim)

        elif choice == "3":
            print(f"\n{Color.YELLOW}[Scenario 3] Simulating high packet loss on payment processor...{Color.RESET}")
            req_key = f"idem-key-chaos-{uuid.uuid4().hex[:6]}"
            order_data = {"customer_id": "cust-unlucky", "items": ["serverless-gpu-rig"], "amount": 1450.00}
            sim.api_gateway_ingress(order_data, req_key)
            sim.run_drain_cycle(simulate_payment_chaos=True)
            render_dashboard(sim)

        elif choice == "4":
            print(f"\n{Color.MAGENTA}[Scenario 4] Simulating warehouse inventory depletion...{Color.RESET}")
            req_key = f"idem-key-oos-{uuid.uuid4().hex[:6]}"
            order_data = {"customer_id": "cust-oos", "items": ["limited-edition-keycap"], "amount": 45.00}
            sim.api_gateway_ingress(order_data, req_key)
            sim.run_drain_cycle(simulate_inventory_failure=True)
            render_dashboard(sim)

        elif choice == "5":
            render_dashboard(sim)

        elif choice == "0":
            print(f"\n{Color.GREEN}Lab completed successfully. Serverless simulation closed.{Color.RESET}")
            sys.exit(0)
        else:
            print(f"{Color.RED}Invalid selection. Please choose 0 through 5.{Color.RESET}")


if __name__ == "__main__":
    main()
