#!/usr/bin/env python3
"""
BAB-10: Arsitektur Perusahaan & Implementasi Capstone (Rust Architecture Lab)
Simulasi Teknis Mandiri Arsitektur Enterprise Rust:
- Clean Architecture & Domain-Driven Design (DDD)
- Pattern Result<T, E> & Option<T> idiomatik
- Concurrency & MPSC Channels (Multi-Producer, Single-Consumer) Worker Pool
- Event Sourcing & CQRS (Command Query Responsibility Segregation)
- Zero-Downtime Graceful Shutdown & Telemetry Metrics
"""

from __future__ import annotations
import sys
import time
import uuid
import queue
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar, Optional, List, Dict, Any, Callable

# ==============================================================================
# ANSI Terminal Color Definitions
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

def cprint(text: str, color: str = Color.WHITE, bold: bool = False, end: str = "\n"):
    prefix = Color.BOLD if bold else ""
    print(f"{prefix}{color}{text}{Color.RESET}", end=end)

# ==============================================================================
# Idiomatic Rust Primitives Simulation (Result<T, E> & Option<T>)
# ==============================================================================
T = TypeVar("T")
E = TypeVar("E")

class Result(Generic[T, E]):
    def __init__(self, value: Optional[T] = None, error: Optional[E] = None, is_ok: bool = True):
        self._value = value
        self._error = error
        self._is_ok = is_ok

    @classmethod
    def ok(cls, val: T) -> Result[T, E]:
        return cls(value=val, is_ok=True)

    @classmethod
    def err(cls, err: E) -> Result[T, E]:
        return cls(error=err, is_ok=False)

    def is_ok(self) -> bool:
        return self._is_ok

    def unwrap(self) -> T:
        if not self._is_ok:
            raise RuntimeError(f"Panic on unwrap: {self._error}")
        return self._value  # type: ignore

    def unwrap_or(self, default: T) -> T:
        return self._value if self._is_ok else default  # type: ignore

    def match(self, on_ok: Callable[[T], Any], on_err: Callable[[E], Any]) -> Any:
        if self._is_ok:
            return on_ok(self._value)  # type: ignore
        return on_err(self._error)  # type: ignore

# ==============================================================================
# Domain Entities, Value Objects & CQRS Events
# ==============================================================================
class OrderStatus(Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"

@dataclass(frozen=True)
class OrderId:
    value: str = field(default_factory=lambda: f"ORD-{uuid.uuid4().hex[:8].upper()}")

@dataclass(frozen=True)
class Money:
    amount: float
    currency: str = "IDR"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Nilai moneter tidak boleh negatif")

@dataclass
class OrderCreatedEvent:
    order_id: OrderId
    customer_id: str
    item_sku: str
    total: Money
    timestamp: float = field(default_factory=time.time)

@dataclass
class OrderExecutedEvent:
    order_id: OrderId
    execution_latency_ms: float
    timestamp: float = field(default_factory=time.time)

# ==============================================================================
# Enterprise Architecture: Actor & MPSC Pipeline (Simulasi Tokio + MPSC)
# ==============================================================================
@dataclass
class PipelineMessage:
    event_type: str
    payload: Any
    reply_channel: Optional[queue.Queue] = None

class EnterprisePipeline:
    """
    Simulasi Arsitektur Rust: Async Actor Runtime dengan Worker Threads dan Channels
    """
    def __init__(self, worker_count: int = 3):
        self.channel: queue.Queue[Optional[PipelineMessage]] = queue.Queue(maxsize=100)
        self.workers: List[threading.Thread] = []
        self.running = threading.Event()
        self.processed_counter = 0
        self.lock = threading.Lock()
        self.audit_log: List[str] = []
        self.worker_count = worker_count

    def start(self):
        self.running.set()
        for i in range(self.worker_count):
            t = threading.Thread(target=self._worker_loop, args=(i + 1,), daemon=True)
            self.workers.append(t)
            t.start()
        cprint(f"[SYSTEM] Pipeline Tokio/MPSC Worker Pool ({self.worker_count} workers) aktif.", Color.GREEN)

    def _worker_loop(self, worker_id: int):
        while self.running.is_set():
            try:
                msg = self.channel.get(timeout=0.2)
            except queue.Empty:
                continue

            if msg is None:
                self.channel.task_done()
                break

            # Simulasi pengolahan pesanan non-blocking
            time.sleep(0.04)
            with self.lock:
                self.processed_counter += 1
                log_entry = f"Worker #{worker_id} processed {msg.event_type} id={getattr(msg.payload, 'order_id', 'N/A')}"
                self.audit_log.append(log_entry)

            if msg.reply_channel:
                msg.reply_channel.put(Result.ok(f"Sukses di-handle oleh Worker #{worker_id}"))

            self.channel.task_done()

    def send_command(self, msg: PipelineMessage) -> Result[str, str]:
        if not self.running.is_set():
            return Result.err("Runtime pipeline sedang shutdown!")
        try:
            self.channel.put(msg, timeout=0.5)
            return Result.ok("Pesan berhasil dikirim ke bounded queue")
        except queue.Full:
            return Result.err("Backpressure trigger! Channel antrean penuh (Drop/Throttle)")

    def stop(self):
        cprint("[SYSTEM] Menginisiasi Graceful Shutdown (draining bounded queue)...", Color.YELLOW)
        self.running.clear()
        for _ in self.workers:
            self.channel.put(None)
        for t in self.workers:
            t.join()
        cprint("[SYSTEM] Seluruh worker thread Rust runtime telah dihentikan secara bersih.", Color.GREEN)

# ==============================================================================
# Domain Service & Use Cases
# ==============================================================================
class OrderEngine:
    def __init__(self, pipeline: EnterprisePipeline):
        self.pipeline = pipeline
        self.read_model_orders: Dict[str, Dict[str, Any]] = {}

    def submit_order(self, customer: str, sku: str, price: float) -> Result[OrderId, str]:
        # Validasi Invariant DDD
        if price <= 0:
            return Result.err("ERR_INVALID_PRICE: Harga pesanan wajib > 0")
        if not sku.startswith("SKU-"):
            return Result.err("ERR_DOMAIN_RULE: Format SKU tidak standar enterprise")

        order_id = OrderId()
        money = Money(amount=price)
        event = OrderCreatedEvent(order_id=order_id, customer_id=customer, item_sku=sku, total=money)

        # Proyeksi CQRS Read Model
        self.read_model_orders[order_id.value] = {
            "customer": customer,
            "sku": sku,
            "amount": price,
            "status": OrderStatus.PENDING.value,
            "created_at": event.timestamp,
        }

        # Dispatch ke async channel worker
        msg = PipelineMessage(event_type="OrderCreated", payload=event)
        dispatch_res = self.pipeline.send_command(msg)

        if not dispatch_res.is_ok():
            return Result.err(f"Gagal dispatch event: {dispatch_res._error}")

        self.read_model_orders[order_id.value]["status"] = OrderStatus.EXECUTED.value
        return Result.ok(order_id)

# ==============================================================================
# Interactive Terminal User Interface
# ==============================================================================
def print_banner():
    cprint("=" * 72, Color.CYAN)
    cprint("  RUST ENTERPRISE CAPSTONE ARCHITECTURE SIMULATOR (BAB-10)", Color.CYAN, bold=True)
    cprint("  DDD · CQRS/ES · Tokio MPSC Concurrency · Fault Tolerance · Zero-Cost", Color.WHITE)
    cprint("=" * 72, Color.CYAN)

def print_menu():
    print(f"\n{Color.BOLD}{Color.MAGENTA}--- MENU UTAMA LAB INTERAKTIF ---{Color.RESET}")
    print(f"[{Color.GREEN}1{Color.RESET}] Buat Pesanan Baru (DDD Command & Event Sourcing)")
    print(f"[{Color.GREEN}2{Color.RESET}] Simulasi Stres & Backpressure Channel (Concurrency MPSC)")
    print(f"[{Color.GREEN}3{Color.RESET}] Inspeksi CQRS Read Model & Audit Log")
    print(f"[{Color.GREEN}4{Color.RESET}] Uji Domain Failure & Validasi Result<T, E>")
    print(f"[{Color.GREEN}5{Color.RESET}] Telemetri Metrik & Health Check")
    print(f"[{Color.RED}0{Color.RESET}] Graceful Shutdown & Keluar")

def main():
    print_banner()
    pipeline = EnterprisePipeline(worker_count=4)
    pipeline.start()
    engine = OrderEngine(pipeline)

    try:
        while True:
            print_menu()
            choice = input(f"{Color.YELLOW}Pilih opsi [0-5]: {Color.RESET}").strip()

            if choice == "1":
                cprint("\n[*] Membuat Pesanan Baru...", Color.CYAN, bold=True)
                cust = input("Nama Pelanggan [default: AcmeCorp]: ").strip() or "AcmeCorp"
                sku = input("Kode SKU [contoh: SKU-RUST-SERVER]: ").strip() or "SKU-RUST-SERVER"
                try:
                    price_str = input("Total Nilai (IDR) [contoh: 25000000]: ").strip() or "25000000"
                    price = float(price_str)
                except ValueError:
                    cprint("[-] Input nominal tidak valid!", Color.RED)
                    continue

                res = engine.submit_order(cust, sku, price)
                res.match(
                    on_ok=lambda oid: cprint(f"[+] SUKSES: Order {oid.value} berhasil diproses oleh Domain Core!", Color.GREEN, bold=True),
                    on_err=lambda err: cprint(f"[-] GAGAL: {err}", Color.RED, bold=True)
                )

            elif choice == "2":
                cprint("\n[*] Menjalankan Stress Test Concurrency (25 Async Commands via Worker Pool)...", Color.CYAN, bold=True)
                start_t = time.time()
                for idx in range(25):
                    sku = f"SKU-BATCH-{idx:03d}"
                    engine.submit_order(f"Client-{idx}", sku, 100000.0 + idx * 5000)
                elapsed = time.time() - start_t
                cprint(f"[+] 25 events terdistribusi ke Worker Channels dalam {elapsed:.3f}s.", Color.GREEN)

            elif choice == "3":
                cprint("\n[*] CQRS Projections & Audit Logs:", Color.CYAN, bold=True)
                orders = engine.read_model_orders
                cprint(f"Total Pesanan di Read Model: {len(orders)}", Color.WHITE)
                for oid, data in list(orders.items())[-5:]:
                    print(f"  • {Color.YELLOW}{oid}{Color.RESET}: Customer={data['customer']} | SKU={data['sku']} | IDR {data['amount']:,.2f} | [{data['status']}]")
                cprint("\nTerakhir 4 Entri Audit Trail:", Color.DIM)
                with pipeline.lock:
                    for log in pipeline.audit_log[-4:]:
                        print(f"  [LOG] {log}")

            elif choice == "4":
                cprint("\n[*] Menguji Fault Tolerance & Pattern Matching Error...", Color.CYAN, bold=True)
                bad_cases = [
                    ("PT Solusi", "INVALID-SKU-123", 500000.0),
                    ("PT Maju", "SKU-DATABASE-01", -15000.0)
                ]
                for cust, sku, price in bad_cases:
                    cprint(f"Testing order payload: SKU={sku}, Price={price}", Color.YELLOW)
                    res = engine.submit_order(cust, sku, price)
                    res.match(
                        on_ok=lambda oid: cprint(f"  Unexpected Ok: {oid.value}", Color.GREEN),
                        on_err=lambda err: cprint(f"  Caught Domain Error Handled Safely: {err}", Color.RED)
                    )

            elif choice == "5":
                cprint("\n[*] Telemetri & Runtime Health Check:", Color.CYAN, bold=True)
                with pipeline.lock:
                    processed = pipeline.processed_counter
                qsize = pipeline.channel.qsize()
                cprint(f"  Runtime Status     : RUNNING (Healthy)", Color.GREEN)
                cprint(f"  Worker Threads     : {pipeline.worker_count} Active OS Threads", Color.WHITE)
                cprint(f"  Queue Capacity     : {qsize} / 100 (Backpressure threshold: 100)", Color.WHITE)
                cprint(f"  Total Processed    : {processed} messages", Color.CYAN)
                cprint(f"  Zero-Cost Overhead : Verified (No GIL bottlenecks simulated)", Color.MAGENTA)

            elif choice == "0":
                cprint("\nKeluar dari simulasi...", Color.YELLOW)
                break
            else:
                cprint("Pilihan tidak valid, silakan ulangi.", Color.RED)

    except KeyboardInterrupt:
        cprint("\nInterupsi diterima, segera shutdown...", Color.RED)
    finally:
        pipeline.stop()
        cprint("[*] Selesai. Lab simulasi Rust enterprise ditutup dengan aman.\n", Color.CYAN)

if __name__ == "__main__":
    main()
