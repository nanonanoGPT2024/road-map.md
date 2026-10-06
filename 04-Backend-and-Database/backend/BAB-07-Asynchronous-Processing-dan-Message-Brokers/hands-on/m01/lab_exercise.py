#!/usr/bin/env python3
"""
BAB-07: Asynchronous Processing & Message Brokers
Hands-on Lab Exercise: In-Memory Message Broker & Event-Driven Worker Simulation

Fitur & Konsep Inti yang Disimulasikan:
1. Topic Exchange & Message Partitioning (Hash-based partition routing)
2. Consumer Groups, Offset Tracking & Consumer Lag
3. At-least-once Delivery, Explicit Ack / Nack Protocol
4. Retry Mechanism dengan Exponential Backoff & Dead Letter Queue (DLQ)
5. Idempotent Processing (Deduplication Cache di sisi Consumer)
6. Output ANSI Colorized Terminal & Interactive CLI
"""

import sys
import time
import uuid
import random
import hashlib
import threading
from queue import Queue, Empty
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# --- ANSI Color Codes ---
class Colors:
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
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"


@dataclass
class Message:
    topic: str
    key: str
    payload: dict
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    partition: int = 0
    offset: int = 0
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    error_reason: Optional[str] = None


class DeadLetterQueue:
    """Menyimpan pesan-pesan racun (poison pills) yang gagal diproses melampaui ambang batas retry."""
    def __init__(self):
        self._lock = threading.Lock()
        self.messages: List[Message] = []

    def push(self, msg: Message, reason: str):
        with self._lock:
            msg.error_reason = reason
            self.messages.append(msg)
            print(f"{Colors.BG_RED}{Colors.WHITE}[DLQ ROUTED]{Colors.RESET} Message "
                  f"{Colors.YELLOW}#{msg.id}{Colors.RESET} (Key={msg.key}) dipindahkan ke DLQ! Alasan: {reason}")

    def count(self) -> int:
        with self._lock:
            return len(self.messages)

    def drain(self) -> List[Message]:
        with self._lock:
            msgs = list(self.messages)
            self.messages.clear()
            return msgs


class Partition:
    """Partisi log logikal yang merekam pesan secara append-only dan terurut."""
    def __init__(self, partition_id: int):
        self.partition_id = partition_id
        self._lock = threading.Lock()
        self._log: List[Message] = []
        self._queue: Queue = Queue()

    def append(self, msg: Message) -> int:
        with self._lock:
            offset = len(self._log)
            msg.partition = self.partition_id
            msg.offset = offset
            self._log.append(msg)
            self._queue.put(msg)
            return offset

    def fetch(self, timeout: float = 0.5) -> Optional[Message]:
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def size(self) -> int:
        with self._lock:
            return len(self._log)

    def pending_count(self) -> int:
        return self._queue.qsize()


class Broker:
    """Message Broker in-memory dengan dukungan multi-partition dan consumer groups."""
    def __init__(self, num_partitions: int = 3):
        self.num_partitions = num_partitions
        self.partitions: Dict[int, Partition] = {
            i: Partition(i) for i in range(num_partitions)
        }
        self.dlq = DeadLetterQueue()
        self.consumer_offsets: Dict[str, Dict[int, int]] = {}
        self._lock = threading.Lock()

    def _hash_key(self, key: str) -> int:
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        return int(digest, 16) % self.num_partitions

    def publish(self, topic: str, key: str, payload: dict, max_retries: int = 3) -> Message:
        part_id = self._hash_key(key)
        msg = Message(topic=topic, key=key, payload=payload, max_retries=max_retries)
        offset = self.partitions[part_id].append(msg)
        print(f"{Colors.GREEN}[PRODUCER -> BROKER]{Colors.RESET} Topic: {Colors.CYAN}{topic}{Colors.RESET} | "
              f"Key: {Colors.MAGENTA}{key}{Colors.RESET} -> Partition: {Colors.BOLD}{part_id}{Colors.RESET} | "
              f"Offset: {Colors.BOLD}{offset}{Colors.RESET} | MsgID: {msg.id}")
        return msg

    def requeue_or_dlq(self, msg: Message, reason: str):
        if msg.retry_count < msg.max_retries:
            msg.retry_count += 1
            backoff_sec = 0.2 * (2 ** (msg.retry_count - 1))
            print(f"{Colors.YELLOW}[RETRY SCHEDULER]{Colors.RESET} Msg #{msg.id} retry {msg.retry_count}/{msg.max_retries} "
                  f"dalam {backoff_sec:.2f}s (Error: {reason})")
            time.sleep(backoff_sec)
            self.partitions[msg.partition].append(msg)
        else:
            self.dlq.push(msg, reason)

    def commit_offset(self, group_id: str, partition_id: int, offset: int):
        with self._lock:
            if group_id not in self.consumer_offsets:
                self.consumer_offsets[group_id] = {}
            self.consumer_offsets[group_id][partition_id] = offset + 1


class ConsumerWorker:
    """Worker node yang menyimulasikan pemrosesan pesan, failure injection, dan deduplikasi idempoten."""
    def __init__(self, worker_id: str, group_id: str, broker: Broker, assigned_partition: int):
        self.worker_id = worker_id
        self.group_id = group_id
        self.broker = broker
        self.assigned_partition = assigned_partition
        self.is_running = False
        self.processed_keys: Set[str] = set()
        self._thread: Optional[threading.Thread] = None
        self.stats = {"processed": 0, "failed": 0, "duplicates": 0}

    def start(self):
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run_loop(self):
        partition = self.broker.partitions[self.assigned_partition]
        while self.is_running:
            msg = partition.fetch(timeout=0.3)
            if not msg:
                continue

            # Simulasi Idempotent check (deduplikasi berdasarkan idempotency key payload)
            idem_key = msg.payload.get("idempotency_key", msg.id)
            if idem_key in self.processed_keys and msg.retry_count == 0:
                print(f"{Colors.BLUE}[IDEMPOTENT SKIP]{Colors.RESET} {self.worker_id}: Pesan #{msg.id} "
                      f"(Key={idem_key}) sudah pernah diproses. Instant ACK!")
                self.stats["duplicates"] += 1
                self.broker.commit_offset(self.group_id, self.assigned_partition, msg.offset)
                continue

            # Simulasi Failure Injection
            force_fail = msg.payload.get("simulate_fail", False)
            flaky = msg.payload.get("flaky", False)
            should_fail = force_fail or (flaky and random.random() < 0.6 and msg.retry_count < 2)

            time.sleep(random.uniform(0.05, 0.15))  # Waktu kerja simulasi

            if should_fail:
                self.stats["failed"] += 1
                err_msg = "Database Timeout Error" if flaky else "Unrecoverable Schema Error"
                print(f"{Colors.RED}[WORKER NACK]{Colors.RESET} {self.worker_id} (Part {self.assigned_partition}): "
                      f"Gagal memproses #{msg.id}! Alasan: {err_msg}")
                self.broker.requeue_or_dlq(msg, err_msg)
            else:
                self.stats["processed"] += 1
                self.processed_keys.add(idem_key)
                self.broker.commit_offset(self.group_id, self.assigned_partition, msg.offset)
                print(f"{Colors.GREEN}[WORKER ACK]{Colors.RESET} {self.worker_id} (Part {self.assigned_partition}): "
                      f"Sukses proses Msg #{msg.id} [{msg.topic}] Action: {msg.payload.get('action')} | "
                      f"Offset Committed: {msg.offset}")


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}================================================================================
   LAB SIMULASI MESSAGE BROKER & ASYNC PROCESSING (BAB-07)
   Topics: Partitioning, Consumer Groups, Ack/Nack, DLQ, & Idempotency
================================================================================{Colors.RESET}
"""
    print(banner)


def display_dashboard(broker: Broker, workers: List[ConsumerWorker]):
    group_name = workers[0].group_id if workers else "order-processing-group"
    print(f"\n{Colors.BOLD}{Colors.WHITE}=== STATUS BROKER & PARTITIONS ==={Colors.RESET}")
    for p_id, partition in broker.partitions.items():
        total = partition.size()
        pending = partition.pending_count()
        committed = broker.consumer_offsets.get(group_name, {}).get(p_id, 0)
        lag = max(0, total - committed)
        print(f" Partisi [{Colors.YELLOW}{p_id}{Colors.RESET}]: Total Log: {total:3d} | "
              f"Committed Offset: {committed:3d} | Pending Queue: {pending:3d} | "
              f"Consumer Lag: {Colors.RED if lag > 0 else Colors.GREEN}{lag}{Colors.RESET}")

    dlq_count = broker.dlq.count()
    dlq_color = Colors.RED if dlq_count > 0 else Colors.GREEN
    print(f" Dead Letter Queue (DLQ): {dlq_color}{Colors.BOLD}{dlq_count} pesan{Colors.RESET}")

    print(f"\n{Colors.BOLD}{Colors.WHITE}=== METRIK WORKER (CONSUMER GROUP: {group_name}) ==={Colors.RESET}")
    for w in workers:
        st = w.stats
        print(f" [{Colors.CYAN}{w.worker_id}{Colors.RESET}] Assg: Part-{w.assigned_partition} | "
              f"Sukses (ACK): {Colors.GREEN}{st['processed']}{Colors.RESET} | "
              f"Gagal (NACK): {Colors.RED}{st['failed']}{Colors.RESET} | "
              f"Deduplikasi: {Colors.BLUE}{st['duplicates']}{Colors.RESET}")
    print("-" * 80)


def run_interactive():
    print_banner()
    broker = Broker(num_partitions=3)
    group_name = "order-processing-group"

    # Inisialisasi 3 Consumer Worker (1 Worker per Partisi)
    workers = [
        ConsumerWorker(f"Worker-{i}", group_name, broker, assigned_partition=i)
        for i in range(broker.num_partitions)
    ]
    for w in workers:
        w.start()

    print(f"{Colors.GREEN}✓ Cluster broker siap dengan 3 Partisi dan 3 Consumer Workers aktif.{Colors.RESET}")

    try:
        while True:
            print(f"\n{Colors.BOLD}PILIHAN AKSI SIMULASI:{Colors.RESET}")
            print(f" {Colors.CYAN}[1]{Colors.RESET} Kirim Single Event (Normal: Order Placed)")
            print(f" {Colors.CYAN}[2]{Colors.RESET} Kirim Flaky Event (Akan memicu Auto-Retry lalu Sukses)")
            print(f" {Colors.CYAN}[3]{Colors.RESET} Kirim Poison Pill Event (Pasti Gagal -> Masuk DLQ)")
            print(f" {Colors.CYAN}[4]{Colors.RESET} Kirim Duplikat Event (Uji Idempotent Consumer)")
            print(f" {Colors.CYAN}[5]{Colors.RESET} Kirim Batch 12 Acak (High-Throughput Simulation)")
            print(f" {Colors.CYAN}[6]{Colors.RESET} Tampilkan Dashboard Partisi, Lag & Offset")
            print(f" {Colors.CYAN}[7]{Colors.RESET} Inspeksi & Drain/Replay Isi DLQ")
            print(f" {Colors.RED}[0]{Colors.RESET} Keluar")

            choice = input(f"\n{Colors.YELLOW}Masukkan pilihan (0-7): {Colors.RESET}").strip()

            if choice == "1":
                oid = f"ORD-{random.randint(1000, 9999)}"
                broker.publish("orders", key=oid, payload={"action": "CREATE_ORDER", "amount": 150000})
                time.sleep(0.4)

            elif choice == "2":
                oid = f"ORD-FLAKY-{random.randint(100, 999)}"
                print(f"{Colors.MAGENTA}>> Mempublikasikan pesan dengan transient network issue...{Colors.RESET}")
                broker.publish("payments", key=oid, payload={"action": "PROCESS_PAYMENT", "flaky": True})
                time.sleep(1.2)

            elif choice == "3":
                oid = f"ORD-POISON-{random.randint(100, 999)}"
                print(f"{Colors.RED}>> Mempublikasikan Poison Pill (unrecoverable error)...{Colors.RESET}")
                broker.publish("orders", key=oid, payload={"action": "CORRUPTED_EVENT", "simulate_fail": True}, max_retries=2)
                time.sleep(1.5)

            elif choice == "4":
                fixed_idemp = "IDEMP-KEY-99999"
                print(f"{Colors.BLUE}>> Mengirim pesan pertama dengan idempotency key {fixed_idemp}...{Colors.RESET}")
                broker.publish("inventory", key="ITEM-42", payload={"action": "RESERVE_STOCK", "idempotency_key": fixed_idemp})
                time.sleep(0.4)
                print(f"{Colors.BLUE}>> Mengirim pesan duplikat persis dengan key {fixed_idemp}...{Colors.RESET}")
                broker.publish("inventory", key="ITEM-42", payload={"action": "RESERVE_STOCK", "idempotency_key": fixed_idemp})
                time.sleep(0.4)

            elif choice == "5":
                print(f"{Colors.CYAN}>> Mengirim 12 event acak ke broker secara beruntun...{Colors.RESET}")
                for i in range(12):
                    cust_id = f"USER-{random.randint(1, 5)}"
                    is_flaky = (i % 4 == 0)
                    broker.publish("events", key=cust_id, payload={
                        "action": f"STEP_{i+1}",
                        "timestamp": time.time(),
                        "flaky": is_flaky
                    })
                    time.sleep(0.05)
                time.sleep(1.5)

            elif choice == "6":
                display_dashboard(broker, workers)

            elif choice == "7":
                count = broker.dlq.count()
                print(f"\n{Colors.BOLD}=== INSPEKSI DEAD LETTER QUEUE (Total: {count}) ==={Colors.RESET}")
                if count == 0:
                    print(f"{Colors.GREEN}DLQ Bersih! Tidak ada pesan bermasalah.{Colors.RESET}")
                else:
                    dlq_items = broker.dlq.drain()
                    for idx, item in enumerate(dlq_items, 1):
                        print(f" {idx}. ID: {Colors.YELLOW}{item.id}{Colors.RESET} | "
                              f"Key: {item.key} | Partisi Asal: {item.partition} | "
                              f"Retries: {item.retry_count}/{item.max_retries} | "
                              f"Error: {Colors.RED}{item.error_reason}{Colors.RESET}")
                    replay = input(f"\n{Colors.YELLOW}Replay pesan-pesan ini kembali ke broker? (y/N): {Colors.RESET}").lower()
                    if replay == "y":
                        print(f"{Colors.GREEN}>> Replaying {len(dlq_items)} pesan dengan flag simulate_fail=False...{Colors.RESET}")
                        for item in dlq_items:
                            item.payload["simulate_fail"] = False
                            item.payload["flaky"] = False
                            item.retry_count = 0
                            broker.publish(item.topic, item.key, item.payload)
                        time.sleep(0.8)

            elif choice == "0":
                print(f"\n{Colors.YELLOW}Menghentikan semua consumer worker threads...{Colors.RESET}")
                for w in workers:
                    w.stop()
                print(f"{Colors.GREEN}Selesai. Terima kasih telah mengikuti simulasi BAB-07!{Colors.RESET}\n")
                break
            else:
                print(f"{Colors.RED}Pilihan tidak valid. Silakan pilih 0-7.{Colors.RESET}")

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}\nInterupsi diterima. Menghentikan simulasi...{Colors.RESET}")
        for w in workers:
            w.stop()
        sys.exit(0)


if __name__ == "__main__":
    # Jika dijalankan secara non-interaktif / batch mode (--automated / CI)
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--automated", "--demo"):
        print_banner()
        print(f"{Colors.YELLOW}[AUTOMATED MODE] Menjalankan test run mandiri...{Colors.RESET}")
        test_broker = Broker(num_partitions=3)
        t_workers = [ConsumerWorker(f"Worker-{i}", "test-grp", test_broker, i) for i in range(3)]
        for tw in t_workers:
            tw.start()

        # Uji kirim variasi pesan
        test_broker.publish("orders", "CUST-1", {"action": "PAY", "simulate_fail": False})
        test_broker.publish("orders", "CUST-2", {"action": "FAIL_POISON", "simulate_fail": True, "max_retries": 1})
        time.sleep(1.0)
        display_dashboard(test_broker, t_workers)
        for tw in t_workers:
            tw.stop()
        print(f"{Colors.GREEN}✓ Automated run sukses.{Colors.RESET}")
    else:
        run_interactive()
