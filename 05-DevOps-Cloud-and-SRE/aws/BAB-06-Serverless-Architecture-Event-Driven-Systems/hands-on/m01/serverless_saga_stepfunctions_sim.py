#!/usr/bin/env python3
"""
Serverless Saga Pattern & Event-Driven Engine Simulator
Modul 01: AWS Serverless Architecture & Distributed Systems

Skrip ini mensimulasikan distributed saga orchestration (AWS Step Functions)
lengkap dengan EventBridge routing, SQS Dead-Letter Queue (DLQ), retry exponential backoff
dengan jitter, serta compensating transactions saat terjadi kegagalan sistem terdistribusi.

Dependensi: Python standard library murni (tanpa external pip packages).
Kompatibel: Python 3.9+
"""

import json
import time
import random
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# Konfigurasi Logging Terstruktur Bergaya AWS CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [TraceID: %(trace_id)s] %(message)s'
)

# Adapter Logger untuk menyuntikkan trace_id secara otomatis
class TraceLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        kwargs['extra'] = {'trace_id': self.extra.get('trace_id', 'ROOT-NONE')}
        return msg, kwargs

base_logger = logging.getLogger("AWS-Serverless-Engine")

# --- DATA MODELS ---

@dataclass
class EventEnvelope:
    id: str
    source: str
    detail_type: str
    detail: Dict[str, Any]
    account: str = "123456789012"
    region: str = "us-east-1"
    time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2)

@dataclass
class SQSMessage:
    message_id: str
    body: str
    receipt_handle: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    receive_count: int = 0

# --- SIMULASI KOMPONEN SERVERLESS AWS ---

class SimulatedSQSQueue:
    """Simulasi antrean Amazon SQS lengkap dengan DLQ dan Visibility Timeout"""
    def __init__(self, name: str, visibility_timeout: int = 5, max_receive_count: int = 3, dlq: Optional['SimulatedSQSQueue'] = None):
        self.name = name
        self.visibility_timeout = visibility_timeout
        self.max_receive_count = max_receive_count
        self.dlq = dlq
        self.messages: List[SQSMessage] = []
        self.in_flight: Dict[str, float] = {} # receipt_handle -> visibility expiration timestamp

    def send_message(self, body: Dict[str, Any]) -> str:
        msg_id = str(uuid.uuid4())
        msg = SQSMessage(
            message_id=msg_id,
            body=json.dumps(body),
            receipt_handle=str(uuid.uuid4())
        )
        self.messages.append(msg)
        return msg_id

    def receive_messages(self, max_number: int = 1) -> List[SQSMessage]:
        now = time.time()
        # Bersihkan pesan in-flight yang melewati visibility timeout
        expired_handles = [h for h, exp in self.in_flight.items() if now > exp]
        for h in expired_handles:
            del self.in_flight[h]

        visible_msgs = []
        for msg in self.messages:
            if msg.receipt_handle not in self.in_flight:
                msg.receive_count += 1
                if self.dlq and msg.receive_count > self.max_receive_count:
                    # Alihkan ke Dead-Letter Queue
                    self.dlq.send_message(json.loads(msg.body))
                    self.messages.remove(msg)
                    continue

                self.in_flight[msg.receipt_handle] = now + self.visibility_timeout
                visible_msgs.append(msg)
                if len(visible_msgs) >= max_number:
                    break
        return visible_msgs

    def delete_message(self, receipt_handle: str):
        if receipt_handle in self.in_flight:
            del self.in_flight[receipt_handle]
        self.messages = [m for m in self.messages if m.receipt_handle != receipt_handle]


class SimulatedEventBridge:
    """Simulasi Amazon EventBridge Bus dengan Content-Based Filtering Rules"""
    def __init__(self, name: str = "default"):
        self.name = name
        self.rules: List[Dict[str, Any]] = []

    def add_rule(self, name: str, pattern: Dict[str, Any], target_callback):
        self.rules.append({
            "name": name,
            "pattern": pattern,
            "target": target_callback
        })

    def put_events(self, event: EventEnvelope, logger: TraceLoggerAdapter):
        logger.info(f"[EventBridge] Menerima event '{event.detail_type}' dari source '{event.source}'")
        for rule in self.rules:
            if self._matches_pattern(event, rule["pattern"]):
                logger.info(f"[EventBridge] Rule '{rule['name']}' MATCH! Meneruskan ke target.")
                rule["target"](event)

    def _matches_pattern(self, event: EventEnvelope, pattern: Dict[str, Any]) -> bool:
        # Evaluasi sederhana berbasis key match
        for k, v in pattern.items():
            if k == "source" and event.source not in v:
                return False
            if k == "detail-type" and event.detail_type not in v:
                return False
        return True


class DistributedOrderSaga:
    """
    Simulasi AWS Step Functions State Machine
    Pola: SAGA Pattern dengan Forward Tasks dan Compensating Actions
    """
    def __init__(self, event_bus: SimulatedEventBridge, dlq: SimulatedSQSQueue, trace_id: str):
        self.event_bus = event_bus
        self.dlq = dlq
        self.trace_id = trace_id
        self.logger = TraceLoggerAdapter(base_logger, {'trace_id': trace_id})
        
        # State ledger untuk pelacakan transaksi kompensasi
        self.compensation_stack: List[str] = []

    def execute(self, payload: Dict[str, Any]):
        self.logger.info(">>> MEMULAI DISTRIBUTED SAGA WORKFLOW EXECUTION <<<")
        self.logger.info(f"Input Order Payload: {json.dumps(payload)}")

        try:
            # Step 1: Reserve Inventory
            self._step_reserve_inventory(payload)

            # Step 2: Process Payment (Simulasi titik potensi kegagalan)
            self._step_process_payment_with_retry(payload)

            # Step 3: Confirm Order & Publish Event
            self._step_confirm_order(payload)

            self.logger.info(">>> SAGA EXECUTION SELESAI: STATUS SUCCESS <<<")
            self.event_bus.put_events(EventEnvelope(
                id=str(uuid.uuid4()),
                source="order.saga",
                detail_type="OrderCompleted",
                detail={"order_id": payload["order_id"], "status": "CONFIRMED"}
            ), self.logger)

        except Exception as err:
            self.logger.error(f"[SAGA FAILURE DETECTED] Alasan: {str(err)}. Memulai Kompensasi Rollback!")
            self._rollback_compensations(payload)
            
            # Publikasikan status kegagalan ke EventBridge
            self.event_bus.put_events(EventEnvelope(
                id=str(uuid.uuid4()),
                source="order.saga",
                detail_type="OrderFailed",
                detail={"order_id": payload["order_id"], "error": str(err)}
            ), self.logger)

            # Masukkan payload bermasalah ke DLQ untuk analisis offline
            self.dlq.send_message({"payload": payload, "error": str(err), "trace_id": self.trace_id})
            self.logger.info(f"[DLQ] Payload diisolasi ke {self.dlq.name} untuk post-mortem analysis.")

    def _step_reserve_inventory(self, payload: Dict[str, Any]):
        self.logger.info("[Task: ReserveInventory] Menghubungi Inventory Service...")
        time.sleep(0.1) # Simulasi network latency
        # Daftarkan tindakan kompensasi jika langkah berikutnya gagal
        self.compensation_stack.append("COMPENSATE_INVENTORY")
        self.logger.info(f"[Inventory] Berhasil mengunci {payload['quantity']} item untuk SKU {payload['sku']}.")

    def _step_process_payment_with_retry(self, payload: Dict[str, Any]):
        """Simulasi Task dengan konfigurasi Retry: Exponential Backoff & Jitter"""
        max_attempts = 3
        base_delay = 0.2
        backoff_rate = 2.0

        for attempt in range(1, max_attempts + 1):
            self.logger.info(f"[Task: ProcessPayment] Eksekusi (Percobaan {attempt}/{max_attempts})...")
            try:
                # Simulasi deterministic failure untuk pengujian
                if payload.get("simulate_payment_failure", False):
                    if attempt < 3 and payload.get("failure_type") == "TRANSIENT_NETWORK":
                        raise ConnectionResetError("503 Service Unavailable: Bank Gateway Busy")
                    else:
                        raise ValueError("402 Payment Declined: Saldo Rekening Tidak Mencukupi")

                # Jika sukses
                self.logger.info(f"[Payment] Pembayaran senilai Rp {payload['amount']:,} berhasil diverifikasi.")
                self.compensation_stack.append("COMPENSATE_PAYMENT")
                return

            except ConnectionResetError as transient_err:
                self.logger.warning(f"[Payment] Transient error tertangkap: {transient_err}")
                if attempt == max_attempts:
                    raise
                # Kalkulasi Full Jitter Backoff
                delay = random.uniform(0, base_delay * (backoff_rate ** (attempt - 1)))
                self.logger.info(f"[Retry Engine] Menunggu {delay:.3f} detik sebelum mencoba kembali...")
                time.sleep(delay)

            except ValueError as fatal_err:
                # Non-transient error: hentikan retry langsung
                self.logger.error(f"[Payment] Fatal Error (Non-retryable): {fatal_err}")
                raise

    def _step_confirm_order(self, payload: Dict[str, Any]):
        self.logger.info("[Task: ConfirmOrder] Mengupdate status order menjadi 'CONFIRMED' di database.")
        time.sleep(0.05)

    def _rollback_compensations(self, payload: Dict[str, Any]):
        """Mengeksekusi stack kompensasi secara terbalik (LIFO)"""
        self.logger.warning("--- MEMULAI SAGA COMPENSATING TRANSACTIONS ---")
        while self.compensation_stack:
            action = self.compensation_stack.pop()
            if action == "COMPENSATE_PAYMENT":
                self.logger.info(f"[Compensation: Payment] Menjalankan API Refund dana Rp {payload['amount']:,}...")
                time.sleep(0.05)
            elif action == "COMPENSATE_INVENTORY":
                self.logger.info(f"[Compensation: Inventory] Melepaskan reservasi {payload['quantity']} item SKU {payload['sku']}...")
                time.sleep(0.05)
        self.logger.warning("--- SELURUH TRANSAKSI KOMPENSASI SELESAI DIEKSEKUSI ---")


# --- RUNNER HANDS-ON DEMO ---

def simulate_email_notification_service(event: EventEnvelope):
    trace_id = event.detail.get("order_id", "N/A")
    log = TraceLoggerAdapter(base_logger, {'trace_id': trace_id})
    log.info(f"[Notification Worker] Mengirimkan email konfirmasi ke customer untuk Order {event.detail.get('order_id')}")

def simulate_audit_service(event: EventEnvelope):
    trace_id = event.detail.get("order_id", "N/A")
    log = TraceLoggerAdapter(base_logger, {'trace_id': trace_id})
    log.info(f"[Audit Worker] Merekam audit log immutable untuk Event {event.detail_type}")

def main():
    print("=" * 80)
    print(" AWS SERVERLESS & EVENT-DRIVEN DISTRIBUTED ARCHITECTURE SIMULATION ")
    print(" Modul: 05-DevOps-Cloud-and-SRE / Bab 06: Serverless Architecture")
    print("=" * 80)

    # 1. Inisialisasi Infrastruktur Serverless
    event_bus = SimulatedEventBridge(name="corporate-main-bus")
    dlq = SimulatedSQSQueue(name="order-saga-poison-pill-dlq")

    # 2. Daftarkan Rules EventBridge (Fan-out Subscribers)
    event_bus.add_rule(
        name="Rule-Send-Confirmation-Email",
        pattern={"source": ["order.saga"], "detail-type": ["OrderCompleted"]},
        target_callback=simulate_email_notification_service
    )
    event_bus.add_rule(
        name="Rule-Audit-Logging",
        pattern={"source": ["order.saga"], "detail-type": ["OrderCompleted", "OrderFailed"]},
        target_callback=simulate_audit_service
    )

    # =========================================================================
    # KASUS 1: Transaksi Normal (Happy Path)
    # =========================================================================
    print("\n" + "-" * 80)
    print("SKENARIO 1: PEMESANAN NORMAL (HAPPY PATH - ALL SERVICES HEALTHY)")
    print("-" * 80)
    trace_1 = f"trace-req-{uuid.uuid4().hex[:8]}"
    order_payload_success = {
        "order_id": "ORD-2026-001",
        "customer_id": "CUST-8891",
        "sku": "MACBOOK-M3-PRO",
        "quantity": 1,
        "amount": 32000000,
        "simulate_payment_failure": False
    }
    saga_1 = DistributedOrderSaga(event_bus, dlq, trace_id=trace_1)
    saga_1.execute(order_payload_success)

    # =========================================================================
    # KASUS 2: Transient Network Failure (Auto-recovered via Exponential Backoff)
    # =========================================================================
    print("\n" + "-" * 80)
    print("SKENARIO 2: TRANSIENT FAILURE (RECOVERED BY EXPONENTIAL BACKOFF RETRY)")
    print("-" * 80)
    trace_2 = f"trace-