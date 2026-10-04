#!/usr/bin/env python3
"""
Laboratorium Hands-on: Asynchronous Processing & Background Jobs (ActiveJob / Sidekiq Deep Dive)
Topik: Ruby on Rails Architectural Concepts in Python 3

Simulasi mendalam arsitektur pemrosesan latar belakang (background worker) bergaya Rails:
- Implementasi ApplicationJob dengan declarative retry & queue routing.
- Redis-like In-Memory Queue Store dengan multi-level priority (critical, default, low).
- Scheduler Daemon untuk delayed jobs dan exponential backoff retry via Min-Heap.
- Dead Letter Queue (DLQ) untuk job yang kehabisan batas percobaan.
- Multi-threaded Worker Pool yang mengonsumsi antrean secara konkuren.
"""

import heapq
import json
import math
import os
import random
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

# --- ANSI Terminal Color Palette ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_GRAY    = "\033[90m"

def log_event(source: str, color: str, message: str) -> None:
    """Mencetak log terstruktur dengan timestamp mikrodetik dan tag berwarna."""
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{CLR_GRAY}[{now}]{CLR_RESET} {color}{CLR_BOLD}[{source:<14}]{CLR_RESET} {message}")


@dataclass(order=True)
class ScheduledItem:
    """Item pembungkus untuk Min-Heap scheduler berdasarkan run_at timestamp."""
    run_at: float
    payload: Any = field(compare=False)


@dataclass
class JobInvocation:
    """Struktur serialisasi data job yang kompatibel dengan format ActiveJob / Sidekiq."""
    job_id: str
    job_class: str
    queue_name: str
    args: list
    kwargs: dict
    executions: int = 0
    max_retries: int = 3
    retry_delay_base: float = 1.0
    scheduled_at: float = 0.0
    error_message: Optional[str] = None


class ActiveJobRegistry:
    """Registry global pemetaan nama kelas job ke implementasi runnable."""
    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, job_cls: type) -> type:
        cls._registry[job_cls.__name__] = job_cls
        return job_cls

    @classmethod
    def get(cls, class_name: str) -> Optional[type]:
        return cls._registry.get(class_name)


class RedisBrokerMock:
    """
    Simulasi in-memory Redis backing store:
    - Lists per queue (LPUSH / RPOP).
    - Sorted Sets (ZSET) disimulasikan dengan heapq untuk delayed retry.
    - Hashes untuk Dead Letter Queue (DLQ).
    """
    def __init__(self):
        self._queues: Dict[str, List[JobInvocation]] = {
            "critical": [],
            "default": [],
            "low": []
        }
        self._scheduled_heap: List[ScheduledItem] = []
        self._dead_letter_queue: List[JobInvocation] = []
        self._lock = threading.RLock()
        self._notify = threading.Condition(self._lock)

    def enqueue(self, job: JobInvocation) -> None:
        """Enqueue instan ke priority queue yang ditentukan (mirip LPUSH)."""
        with self._notify:
            if job.queue_name not in self._queues:
                self._queues[job.queue_name] = []
            self._queues[job.queue_name].append(job)
            self._notify.notify()

    def schedule(self, job: JobInvocation, run_at: float) -> None:
        """Menjadwalkan job ke masa depan (mirip ZADD key timestamp member)."""
        with self._notify:
            job.scheduled_at = run_at
            heapq.heappush(self._scheduled_heap, ScheduledItem(run_at=run_at, payload=job))
            self._notify.notify()

    def promote_scheduled_jobs(self) -> int:
        """Memeriksa job yang sudah jatuh tempo dan memindahkannya ke antrean aktif."""
        now = time.time()
        promoted = 0
        with self._notify:
            while self._scheduled_heap and self._scheduled_heap[0].run_at <= now:
                item = heapq.heappop(self._scheduled_heap)
                job: JobInvocation = item.payload
                self._queues[job.queue_name].append(job)
                promoted += 1
            if promoted > 0:
                self._notify.notify_all()
        return promoted

    def fetch_next(self, queue_priorities: List[str], timeout: float = 0.5) -> Optional[JobInvocation]:
        """Strict-priority fetching: mengecek antrean secara berurutan sesuai bobot."""
        with self._notify:
            end_time = time.time() + timeout
            while time.time() < end_time:
                for q in queue_priorities:
                    queue_list = self._queues.get(q, [])
                    if queue_list:
                        return queue_list.pop(0)  # FIFO fetch
                remaining = end_time - time.time()
                if remaining > 0:
                    self._notify.wait(timeout=min(0.1, remaining))
            return None

    def push_to_dlq(self, job: JobInvocation) -> None:
        """Menyimpan job yang gagal permanen ke Dead Letter Queue (Morgue)."""
        with self._lock:
            self._dead_letter_queue.append(job)

    def dlq_count(self) -> int:
        with self._lock:
            return len(self._dead_letter_queue)


class ApplicationJob:
    """
    Kelas dasar ActiveJob: menyediakan DSL perform_later, retry_on, dan queue_as.
    """
    queue_name: str = "default"
    max_retries: int = 2
    retry_delay_base: float = 0.5

    @classmethod
    def set(cls, queue: Optional[str] = None, wait: float = 0.0):
        return JobConfigurator(cls, queue=queue, wait=wait)

    @classmethod
    def perform_later(cls, *args, **kwargs) -> JobInvocation:
        return cls.set().perform_later(*args, **kwargs)

    def perform(self, *args, **kwargs):
        raise NotImplementedError("Subclass wajib mengimplementasikan method perform()")


class JobConfigurator:
    """Helper untuk mendukung syntax chaining Rails: MyJob.set(wait: 2.seconds).perform_later()"""
    def __init__(self, job_cls: type, queue: Optional[str] = None, wait: float = 0.0):
        self.job_cls = job_cls
        self.queue = queue or job_cls.queue_name
        self.wait = wait

    def perform_later(self, *args, **kwargs) -> JobInvocation:
        invocation = JobInvocation(
            job_id=str(uuid.uuid4())[:8],
            job_class=self.job_cls.__name__,
            queue_name=self.queue,
            args=list(args),
            kwargs=kwargs,
            executions=0,
            max_retries=self.job_cls.max_retries,
            retry_delay_base=self.job_cls.retry_delay_base
        )
        if self.wait > 0:
            run_at = time.time() + self.wait
            GLOBAL_BROKER.schedule(invocation, run_at)
            log_event("DISPATCHER", CLR_CYAN,
                      f"Enqueued {self.job_cls.__name__} ({invocation.job_id}) to [{self.queue}] scheduled in {self.wait:.1f}s")
        else:
            GLOBAL_BROKER.enqueue(invocation)
            log_event("DISPATCHER", CLR_CYAN,
                      f"Enqueued {self.job_cls.__name__} ({invocation.job_id}) directly to [{self.queue}]")
        return invocation


GLOBAL_BROKER = RedisBrokerMock()


# --- Domain Jobs Implementation ---

@ActiveJobRegistry.register
class ProcessPaymentJob(ApplicationJob):
    queue_name = "critical"
    max_retries = 3
    retry_delay_base = 0.4

    def perform(self, account_id: str, amount: float):
        # Mensimulasikan kegagalan jaringan acak (network glitch)
        log_event("EXEC-PAYMENT", CLR_BLUE, f"Processing ${amount:.2f} for account: {account_id}")
        if random.random() < 0.65:
            raise ConnectionResetError("Remote Payment Gateway Timeout (504)")
        return f"Payment of ${amount:.2f} settled successfully."


@ActiveJobRegistry.register
class SendWelcomeEmailJob(ApplicationJob):
    queue_name = "default"
    max_retries = 2
    retry_delay_base = 0.2

    def perform(self, user_email: str):
        log_event("EXEC-MAILER", CLR_BLUE, f"Dispatching welcome SMTP packet to {user_email}")
        time.sleep(0.1)  # Simulasi I/O
        return f"Welcome email delivered to {user_email}."


@ActiveJobRegistry.register
class GenerateMonthlyReportJob(ApplicationJob):
    queue_name = "low"
    max_retries = 1
    retry_delay_base = 0.3

    def perform(self, tenant_id: str, month: str):
        log_event("EXEC-REPORT", CLR_BLUE, f"Aggregating data points for tenant: {tenant_id}, month: {month}")
        time.sleep(0.15)  # Simulasi komputasi intensif
        return f"Report generated for {tenant_id}."


# --- Worker Pool & Scheduler Engine ---

class BackgroundScheduler(threading.Thread):
    """Daemon thread yang memantau scheduled set & mempromosikan job saat 'run_at' tercapai."""
    def __init__(self, broker: RedisBrokerMock, poll_interval: float = 0.05):
        super().__init__(daemon=True, name="Scheduler-Daemon")
        self.broker = broker
        self.poll_interval = poll_interval
        self._running = True

    def run(self):
        while self._running:
            promoted = self.broker.promote_scheduled_jobs()
            if promoted > 0:
                log_event("SCHEDULER", CLR_MAGENTA, f"Promoted {promoted} delayed job(s) into active queue.")
            time.sleep(self.poll_interval)

    def stop(self):
        self._running = False


class WorkerThread(threading.Thread):
    """Worker konkruen yang mengonsumsi antrean dan menerapkan retry backoff."""
    def __init__(self, worker_id: int, broker: RedisBrokerMock, queues: List[str]):
        super().__init__(daemon=True, name=f"Worker-{worker_id}")
        self.worker_id = worker_id
        self.broker = broker
        self.queues = queues
        self._running = True

    def run(self):
        while self._running:
            job = self.broker.fetch_next(self.queues, timeout=0.2)
            if not job:
                continue
            self._execute_job(job)

    def _execute_job(self, job: JobInvocation):
        job.executions += 1
        worker_tag = f"Worker-{self.worker_id}"
        log_event(worker_tag, CLR_YELLOW,
                  f"Starting {job.job_class} [ID: {job.job_id}] (Attempt {job.executions}/{job.max_retries + 1})")

        job_cls = ActiveJobRegistry.get(job.job_class)
        if not job_cls:
            log_event(worker_tag, CLR_RED, f"Unregistered Job class: {job.job_class}. Routing to DLQ.")
            job.error_message = "ClassNotFound"
            self.broker.push_to_dlq(job)
            return

        instance = job_cls()
        try:
            result = instance.perform(*job.args, **job.kwargs)
            log_event(worker_tag, CLR_GREEN, f"Completed {job.job_class} [ID: {job.job_id}] -> {result}")
        except Exception as exc:
            job.error_message = str(exc)
            if job.executions <= job.max_retries:
                # Rails-like Exponential Backoff dengan Jitter: delay = base * (2 ^ executions) + rand(jitter)
                jitter = random.uniform(0.05, 0.2)
                delay = (job.retry_delay_base * math.pow(2, job.executions - 1)) + jitter
                log_event(worker_tag, CLR_RED,
                          f"Failed {job.job_class} [ID: {job.job_id}] with '{exc}'. Retrying in {delay:.2f}s...")
                self.broker.schedule(job, time.time() + delay)
            else:
                log_event(worker_tag, CLR_RED,
                          f"Exhausted retries for {job.job_class} [ID: {job.job_id}]. Moving to Dead Letter Queue (DLQ)!")
                self.broker.push_to_dlq(job)

    def stop(self):
        self._running = False


# --- Lab Execution Scenario ---

def main():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== RUBY ON RAILS DEEP DIVE: ACTIVEJOB & SIDEKIQ ARCHITECTURE ==={CLR_RESET}")
    print(f"{CLR_GRAY}Simulasi: Strict Priority Queues, Idempotent Worker Retries, & Scheduled Engine{CLR_RESET}\n")

    # Inisialisasi engine
    queues_priority = ["critical", "default", "low"]
    scheduler = BackgroundScheduler(GLOBAL_BROKER)
    scheduler.start()

    workers = [WorkerThread(i + 1, GLOBAL_BROKER, queues_priority) for i in range(3)]
    for w in workers:
        w.start()

    log_event("CLUSTER", CLR_GREEN, f"Spawned 3 Workers listening to priority: {queues_priority}")

    # Skenario 1: Antrean instan dengan berbagai prioritas
    log_event("SIMULATION", CLR_BOLD, "--- Tahap 1: Enqueue batch job instan ---")
    SendWelcomeEmailJob.perform_later("alice@example.com")
    SendWelcomeEmailJob.perform_later("bob@example.com")
    GenerateMonthlyReportJob.perform_later("tenant-uuid-404", "2026-03")

    # Skenario 2: Job terjadwal (delayed execution via `set(wait: ...)`)
    log_event("SIMULATION", CLR_BOLD, "--- Tahap 2: Enqueue scheduled / delayed jobs ---")
    SendWelcomeEmailJob.set(wait=1.2).perform_later("delayed_charlie@example.com")

    # Skenario 3: Job kritis dengan potensi kegagalan tinggi (menguji retry backoff & DLQ)
    log_event("SIMULATION", CLR_BOLD, "--- Tahap 3: Enqueue high-failure critical jobs (Retry test) ---")
    ProcessPaymentJob.perform_later("acc_9921", 149.99)
    ProcessPaymentJob.perform_later("acc_3301", 999.00)

    # Biarkan worker pool dan scheduler memproses aliran transaksi
    time.sleep(4.5)

    # Shutdown sistem secara gracefully
    log_event("CLUSTER", CLR_YELLOW, "Stopping workers and collecting final metrics...")
    scheduler.stop()
    for w in workers:
        w.stop()

    dlq_count = GLOBAL_BROKER.dlq_count()
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== METRIK PEMROSESAN AKHIR ==={CLR_RESET}")
    print(f"Total Job Masuk Dead Letter Queue (DLQ) : {CLR_RED if dlq_count > 0 else CLR_GREEN}{dlq_count}{CLR_RESET}")
    if dlq_count > 0:
        for dead_job in GLOBAL_BROKER._dead_letter_queue:
            print(f"  {CLR_RED}✖{CLR_RESET} [ID: {dead_job.job_id}] {dead_job.job_class} -> Alasan: {dead_job.error_message}")
    print(f"{CLR_GREEN}✓ Seluruh worker thread dan scheduler berhasil ditutup dengan bersih.{CLR_RESET}\n")

if __name__ == "__main__":
    main()