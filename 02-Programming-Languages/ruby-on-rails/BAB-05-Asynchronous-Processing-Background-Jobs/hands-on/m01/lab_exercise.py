#!/usr/bin/env python3
"""
Rails ActiveJob & Sidekiq Background Processing Simulation
==========================================================
BAB 05: Asynchronous Processing & Background Jobs
Simulates:
- ActiveJob abstraction layer & serialization
- Multi-queue priority execution (critical, default, low_priority)
- Worker thread pool & concurrency
- Retry logic with exponential backoff and jitter (retry_on)
- Dead Letter Queue / Dead Set (DLQ)
- Idempotency key protection
"""

import time
import uuid
import random
import threading
from queue import PriorityQueue, Empty
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ANSI Color Codes for Terminal Output
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"

@dataclass(order=True)
class EnqueuedJob:
    priority: int
    job_id: str = field(compare=False)
    job_class: str = field(compare=False)
    queue_name: str = field(compare=False)
    args: Dict[str, Any] = field(compare=False)
    retry_count: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)
    idempotency_key: Optional[str] = field(default=None, compare=False)
    scheduled_at: float = field(default=0.0, compare=False)

class IdempotencyStore:
    """Simulates Redis SETNX / distributed lock for idempotent job execution."""
    def __init__(self):
        self._keys: set = set()
        self._lock = threading.Lock()

    def acquire(self, key: Optional[str]) -> bool:
        if not key:
            return True
        with self._lock:
            if key in self._keys:
                return False
            self._keys.add(key)
            return True

class RailsBackgroundEngine:
    PRIORITY_MAP = {
        "critical": 1,
        "default": 5,
        "low_priority": 10
    }

    def __init__(self, concurrency: int = 3):
        self.concurrency = concurrency
        self.work_queue: PriorityQueue = PriorityQueue()
        self.dead_letter_queue: List[EnqueuedJob] = []
        self.idempotency_store = IdempotencyStore()
        self.workers: List[threading.Thread] = []
        self.running = False
        self._lock = threading.Lock()
        self.metrics = {"processed": 0, "retried": 0, "failed": 0, "skipped": 0}

    def start(self):
        self.running = True
        for i in range(self.concurrency):
            t = threading.Thread(target=self._worker_loop, args=(i + 1,), daemon=True)
            self.workers.append(t)
            t.start()
        print(f"{Color.CYAN}[Engine]{Color.RESET} Background Engine started with {Color.BOLD}{self.concurrency} worker threads{Color.RESET}.\n")

    def stop(self):
        self.running = False
        for t in self.workers:
            t.join(timeout=1.0)
        print(f"\n{Color.CYAN}[Engine]{Color.RESET} Background Engine stopped cleanly.")

    def enqueue(self, job_class: str, queue_name: str, args: Dict[str, Any],
                max_retries: int = 3, idempotency_key: Optional[str] = None):
        job_id = str(uuid.uuid4())[:8]
        prio = self.PRIORITY_MAP.get(queue_name, 5)
        job = EnqueuedJob(
            priority=prio,
            job_id=job_id,
            job_class=job_class,
            queue_name=queue_name,
            args=args,
            max_retries=max_retries,
            idempotency_key=idempotency_key,
            scheduled_at=time.time()
        )
        self.work_queue.put(job)
        print(f"{Color.GRAY}[Enqueued]{Color.RESET} Job {Color.BOLD}#{job_id}{Color.RESET} ({job_class}) -> queue:{Color.MAGENTA}{queue_name}{Color.RESET} [prio:{prio}]")

    def _worker_loop(self, worker_id: int):
        while self.running:
            try:
                job: EnqueuedJob = self.work_queue.get(timeout=0.5)
            except Empty:
                continue

            self._process_job(worker_id, job)
            self.work_queue.task_done()

    def _process_job(self, worker_id: int, job: EnqueuedJob):
        tag = f"{Color.BLUE}[Worker-{worker_id}]{Color.RESET}"
        
        # Idempotency verification
        if job.idempotency_key and not self.idempotency_store.acquire(job.idempotency_key):
            print(f"{tag} {Color.YELLOW}[IDEMPOTENT SKIP]{Color.RESET} Job #{job.job_id} already processed (Key: {job.idempotency_key})")
            with self._lock:
                self.metrics["skipped"] += 1
            return

        print(f"{tag} Running {Color.BOLD}{job.job_class}#{job.job_id}{Color.RESET} args={job.args} (Attempt {job.retry_count + 1}/{job.max_retries + 1})")
        time.sleep(0.3)  # Simulating task duration

        # Simulated failure scenario based on args
        should_fail = job.args.get("simulate_error", False)
        transient_failure = job.args.get("transient_until_attempt", 0)

        if should_fail or (job.retry_count + 1 < transient_failure):
            self._handle_failure(worker_id, job)
        else:
            with self._lock:
                self.metrics["processed"] += 1
            print(f"{tag} {Color.GREEN}✓ Completed{Color.RESET} {job.job_class}#{job.job_id}")

    def _handle_failure(self, worker_id: int, job: EnqueuedJob):
        tag = f"{Color.BLUE}[Worker-{worker_id}]{Color.RESET}"
        job.retry_count += 1

        if job.retry_count <= job.max_retries:
            # Exponential backoff simulation: wait = 2 ** retry + jitter
            backoff = (2 ** job.retry_count) * 0.1 + random.uniform(0.01, 0.05)
            print(f"{tag} {Color.YELLOW}⚠ Failed{Color.RESET} {job.job_class}#{job.job_id}. Retrying in {backoff:.2f}s (retry_on ActiveJob)")
            with self._lock:
                self.metrics["retried"] += 1
            time.sleep(backoff)
            self.work_queue.put(job)
        else:
            print(f"{tag} {Color.RED}✖ Dead Set / DLQ{Color.RESET} Job #{job.job_id} permanently failed after {job.max_retries} retries.")
            with self._lock:
                self.dead_letter_queue.append(job)
                self.metrics["failed"] += 1

    def print_dashboard(self):
        print(f"\n{Color.BOLD}{Color.CYAN}========== ENGINE DASHBOARD =========={Color.RESET}")
        print(f"Processed: {Color.GREEN}{self.metrics['processed']}{Color.RESET} | "
              f"Retries: {Color.YELLOW}{self.metrics['retried']}{Color.RESET} | "
              f"Failed (DLQ): {Color.RED}{self.metrics['failed']}{Color.RESET} | "
              f"Skipped: {Color.GRAY}{self.metrics['skipped']}{Color.RESET}")
        print(f"Dead Letter Queue Count: {Color.RED}{len(self.dead_letter_queue)}{Color.RESET}")
        for dlq_job in self.dead_letter_queue:
            print(f"  - [{dlq_job.job_id}] {dlq_job.job_class} (args={dlq_job.args})")
        print(f"{Color.BOLD}{Color.CYAN}======================================{Color.RESET}\n")

def run_simulation():
    print(f"{Color.BOLD}{Color.GREEN}Starting ActiveJob / Background Processing Simulator{Color.RESET}")
    print("Concepts: Priority Queues, Workers, Exponential Backoff, Idempotency, DLQ\n")

    engine = RailsBackgroundEngine(concurrency=3)
    engine.start()

    # 1. Normal Standard Job
    engine.enqueue(
        job_class="WelcomeEmailJob",
        queue_name="default",
        args={"user_id": 101, "email": "dev@example.com"}
    )

    # 2. Critical High-Priority Job
    engine.enqueue(
        job_class="ProcessPaymentJob",
        queue_name="critical",
        args={"order_id": 9999, "amount": 150.00}
    )

    # 3. Idempotent Duplicate Jobs (simulating duplicate webhook / deliver_later spam)
    token = "txn_secret_payload_abc"
    engine.enqueue(
        job_class="StripeWebhookJob",
        queue_name="critical",
        args={"event": "charge.succeeded"},
        idempotency_key=token
    )
    engine.enqueue(
        job_class="StripeWebhookJob",
        queue_name="critical",
        args={"event": "charge.succeeded"},
        idempotency_key=token
    )

    # 4. Job that recovers after retries (transient network failure)
    engine.enqueue(
        job_class="FetchThirdPartyDataJob",
        queue_name="default",
        args={"service": "weather_api", "transient_until_attempt": 2},
        max_retries=3
    )

    # 5. Job that fails permanently and enters DLQ
    engine.enqueue(
        job_class="SyncLegacyAccountingJob",
        queue_name="low_priority",
        args={"batch_id": "batch_88", "simulate_error": True},
        max_retries=2
    )

    # Let the worker threads consume jobs
    time.sleep(3.5)
    engine.print_dashboard()
    engine.stop()

if __name__ == "__main__":
    run_simulation()
