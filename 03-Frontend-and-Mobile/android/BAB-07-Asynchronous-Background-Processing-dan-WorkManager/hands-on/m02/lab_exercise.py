#!/usr/bin/env python3
"""
Lab Hands-on: Android Background Processing & WorkManager Deep Dive Simulation
Topic: 03-Frontend-and-Mobile / Chapter 07: Asynchronous Background Processing & WorkManager

Deskripsi:
Script ini memodelkan arsitektur internal Android Jetpack WorkManager secara detail,
mencakup:
1. WorkRequest State Machine (BLOCKED -> ENQUEUED -> RUNNING -> SUCCEEDED/FAILED/RETRY).
2. Constraints Engine (NetworkType, ChargingStatus) dengan Dynamic Triggering.
3. Chained WorkContinuation (beginWith([A, B]) -> then(C)).
4. Exponential/Linear Backoff Policy untuk retry mechanism.
5. Thread-safe Worker execution pool yang mensimulasikan ListenableWorker & Room DB state tracking.
"""

import sys
import time
import uuid
import threading
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional, Callable


# ==============================================================================
# ANSI Color Formatting Helper
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
    BG_DARK = "\033[40m"


def log_event(worker_name: str, state: str, msg: str, color: str = Color.WHITE) -> None:
    timestamp = time.strftime("%H:%M:%S")
    thread_name = threading.current_thread().name
    print(f"{Color.DIM}[{timestamp}]{Color.RESET} "
          f"{Color.BLUE}[{thread_name:^14}]{Color.RESET} "
          f"{color}[{state:^10}]{Color.RESET} "
          f"{Color.BOLD}{worker_name:<22}{Color.RESET}: {msg}")


# ==============================================================================
# Core WorkManager Enums and Data Models
# ==============================================================================
class WorkState(Enum):
    BLOCKED = auto()
    ENQUEUED = auto()
    RUNNING = auto()
    SUCCEEDED = auto()
    FAILED = auto()
    RETRY = auto()
    CANCELLED = auto()


class BackoffPolicy(Enum):
    LINEAR = auto()
    EXPONENTIAL = auto()


@dataclass
class Constraints:
    requires_network: bool = False
    requires_charging: bool = False

    def is_satisfied_by(self, device_state: 'DeviceState') -> bool:
        if self.requires_network and not device_state.network_connected:
            return False
        if self.requires_charging and not device_state.charging:
            return False
        return True


@dataclass
class DeviceState:
    network_connected: bool = False
    charging: bool = False


class Result:
    """Representasi Result dari ListenableWorker Android."""
    def __init__(self, status: str, output_data: Optional[Dict[str, Any]] = None):
        self.status = status
        self.output_data = output_data or {}

    @classmethod
    def success(cls, data: Optional[Dict[str, Any]] = None) -> 'Result':
        return cls("SUCCESS", data)

    @classmethod
    def retry(cls) -> 'Result':
        return cls("RETRY")

    @classmethod
    def failure(cls, data: Optional[Dict[str, Any]] = None) -> 'Result':
        return cls("FAILURE", data)


# ==============================================================================
# Worker Base Class
# ==============================================================================
class Worker:
    """Abstraksi ListenableWorker / CoroutineWorker di Jetpack WorkManager."""
    def __init__(self, work_id: str, input_data: Dict[str, Any]):
        self.id = work_id
        self.input_data = input_data

    def do_work(self) -> Result:
        raise NotImplementedError("do_work harus diimplementasikan oleh worker.")


# ==============================================================================
# WorkRequest and Builders
# ==============================================================================
class WorkRequest:
    """Representasi OneTimeWorkRequest dengan metadata dependensi, constraints, dan retry policy."""
    def __init__(
        self,
        worker_class: Callable[..., Worker],
        name: str,
        constraints: Optional[Constraints] = None,
        initial_input: Optional[Dict[str, Any]] = None,
        backoff_policy: BackoffPolicy = BackoffPolicy.EXPONENTIAL,
        initial_backoff_sec: float = 1.0,
        max_retries: int = 3
    ):
        self.id = str(uuid.uuid4())[:8]
        self.name = f"{name}-{self.id}"
        self.worker_class = worker_class
        self.constraints = constraints or Constraints()
        self.input_data = initial_input or {}
        self.output_data: Dict[str, Any] = {}
        self.state = WorkState.ENQUEUED
        self.run_attempt_count = 0
        self.backoff_policy = backoff_policy
        self.backoff_delay_sec = initial_backoff_sec
        self.max_retries = max_retries
        self.prerequisite_ids: Set[str] = set()
        self.next_eligible_time = 0.0


# ==============================================================================
# WorkManager Engine (Simulasi SQLite + GreedyScheduler + WorkContinuations)
# ==============================================================================
class WorkManagerEngine:
    def __init__(self):
        self._work_store: Dict[str, WorkRequest] = {}
        self._lock = threading.RLock()
        self._device_state = DeviceState(network_connected=False, charging=False)
        self._is_active = True
        self._worker_threads: List[threading.Thread] = []

        # Background Scheduler Thread (simulasi GreedyScheduler Android)
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="GreedySched",
            daemon=True
        )
        self._scheduler_thread.start()

    def set_device_network(self, available: bool) -> None:
        with self._lock:
            self._device_state.network_connected = available
            status = "CONNECTED" if available else "DISCONNECTED"
            log_event("ConstraintTracker", "TRIGGER", f"Jaringan Device: {status}", Color.MAGENTA)

    def set_device_charging(self, charging: bool) -> None:
        with self._lock:
            self._device_state.charging = charging
            status = "PLUGGED_IN" if charging else "ON_BATTERY"
            log_event("ConstraintTracker", "TRIGGER", f"Status Daya: {status}", Color.MAGENTA)

    def enqueue(self, requests: List[WorkRequest]) -> None:
        with self._lock:
            for req in requests:
                if req.prerequisite_ids:
                    # Cek jika dependencies belum selesai, set ke BLOCKED
                    all_met = all(
                        self._work_store[pid].state == WorkState.SUCCEEDED
                        for pid in req.prerequisite_ids
                    )
                    req.state = WorkState.ENQUEUED if all_met else WorkState.BLOCKED
                self._work_store[req.id] = req
                log_event(req.name, req.state.name, f"Dimasukkan ke Room DB. ID={req.id}", Color.CYAN)

    def _scheduler_loop(self) -> None:
        while self._is_active:
            now = time.time()
            schedulable_work: List[WorkRequest] = []

            with self._lock:
                # 1. Update State BLOCKED -> ENQUEUED jika prerequisite selesai
                for req in self._work_store.values():
                    if req.state == WorkState.BLOCKED:
                        all_prereqs_finished = all(
                            pid in self._work_store and self._work_store[pid].state == WorkState.SUCCEEDED
                            for pid in req.prerequisite_ids
                        )
                        failed_prereq = any(
                            pid in self._work_store and self._work_store[pid].state == WorkState.FAILED
                            for pid in req.prerequisite_ids
                        )
                        if failed_prereq:
                            req.state = WorkState.FAILED
                            log_event(req.name, "FAILED", "Dependency gagal dieksekusi. Dibatalkan.", Color.RED)
                        elif all_prereqs_finished:
                            # Merge parent output data into child input data
                            for pid in req.prerequisite_ids:
                                req.input_data.update(self._work_store[pid].output_data)
                            req.state = WorkState.ENQUEUED
                            log_event(req.name, "UNBLOCKED", "Semua dependensi terpenuhi -> ENQUEUED", Color.YELLOW)

                # 2. Cari pekerjaan ENQUEUED yang memenuhi syarat waktu & constraints
                for req in self._work_store.values():
                    if req.state == WorkState.ENQUEUED and now >= req.next_eligible_time:
                        if req.constraints.is_satisfied_by(self._device_state):
                            req.state = WorkState.RUNNING
                            schedulable_work.append(req)

            # Eksekusi task yang lolos seleksi di thread pool
            for req in schedulable_work:
                t = threading.Thread(
                    target=self._execute_worker,
                    args=(req,),
                    name=f"WorkerPool-{req.id}"
                )
                self._worker_threads.append(t)
                t.start()

            time.sleep(0.1)

    def _execute_worker(self, req: WorkRequest) -> None:
        log_event(req.name, "RUNNING", f"Attempt #{req.run_attempt_count + 1} dimulai", Color.YELLOW)
        worker_instance = req.worker_class(req.id, req.input_data)
        
        try:
            result = worker_instance.do_work()
        except Exception as e:
            result = Result.failure({"error": str(e)})

        with self._lock:
            if result.status == "SUCCESS":
                req.state = WorkState.SUCCEEDED
                req.output_data = result.output_data
                log_event(req.name, "SUCCEEDED", f"Selesai! Output payload: {req.output_data}", Color.GREEN)

            elif result.status == "RETRY":
                req.run_attempt_count += 1
                if req.run_attempt_count >= req.max_retries:
                    req.state = WorkState.FAILED
                    log_event(req.name, "FAILED", f"Max retry ({req.max_retries}) terlampaui!", Color.RED)
                else:
                    req.state = WorkState.ENQUEUED
                    # Menghitung Backoff Delay
                    if req.backoff_policy == BackoffPolicy.EXPONENTIAL:
                        delay = req.backoff_delay_sec * (2 ** (req.run_attempt_count - 1))
                    else:
                        delay = req.backoff_delay_sec * req.run_attempt_count
                    req.next_eligible_time = time.time() + delay
                    log_event(
                        req.name, "RETRY",
                        f"Dijadwalkan ulang dalam {delay:.2f}s (Policy={req.backoff_policy.name})",
                        Color.MAGENTA
                    )

            elif result.status == "FAILURE":
                req.state = WorkState.FAILED
                log_event(req.name, "FAILED", f"Eksekusi gagal. Data={result.output_data}", Color.RED)

    def is_all_completed(self) -> bool:
        with self._lock:
            terminal_states = {WorkState.SUCCEEDED, WorkState.FAILED, WorkState.CANCELLED}
            return all(req.state in terminal_states for req in self._work_store.values())

    def shutdown(self) -> None:
        self._is_active = False
        for t in self._worker_threads:
            if t.is_alive():
                t.join(timeout=1.0)
        if self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=1.0)


# ==============================================================================
# WorkContinuation Helper (Fluent API Android style)
# ==============================================================================
class WorkContinuation:
    def __init__(self, engine: WorkManagerEngine, initial_requests: List[WorkRequest]):
        self.engine = engine
        self.current_layer = initial_requests
        self.all_requests = list(initial_requests)

    def then(self, next_requests: List[WorkRequest]) -> 'WorkContinuation':
        for n_req in next_requests:
            for p_req in self.current_layer:
                n_req.prerequisite_ids.add(p_req.id)
            self.all_requests.append(n_req)
        self.current_layer = next_requests
        return self

    def enqueue(self) -> None:
        self.engine.enqueue(self.all_requests)


# ==============================================================================
# Concrete Domain Workers (Studi Kasus: Pemrosesan Gambar & Sync Background)
# ==============================================================================
class ImageCompressWorker(Worker):
    def do_work(self) -> Result:
        raw_size = self.input_data.get("image_size_kb", 5000)
        log_event(f"CompressWorker-{self.id}", "EXEC", f"Mengompresi gambar dari {raw_size}KB...", Color.WHITE)
        time.sleep(0.4)  # Simulasi latency CPU
        compressed_size = int(raw_size * 0.25)
        return Result.success({
            "compressed_size_kb": compressed_size,
            "compression_ratio": "75%"
        })


class WatermarkWorker(Worker):
    def do_work(self) -> Result:
        log_event(f"WatermarkWorker-{self.id}", "EXEC", "Menerapkan watermark hak cipta ke memori bitmap...", Color.WHITE)
        time.sleep(0.3)
        return Result.success({"watermarked": True, "stamp": "@AndroidJetpack"})


class CloudSyncWorker(Worker):
    """Worker yang membutuhkan network dan menguji mekanisme Transient Error / Retry."""
    _attempts = 0

    def do_work(self) -> Result:
        CloudSyncWorker._attempts += 1
        log_event(f"CloudSync-{self.id}", "EXEC", f"Mengunggah payload ke remote S3/GCS...", Color.WHITE)
        time.sleep(0.3)

        # Simulasi Transient Network Flake pada attempt pertama
        if CloudSyncWorker._attempts == 1:
            log_event(f"CloudSync-{self.id}", "WARN", "503 Service Temporarily Unavailable. Triggering Retry...", Color.RED)
            return Result.retry()

        return Result.success({
            "upload_url": "https://storage.googleapis.com/android-lab/output.jpg",
            "bytes_sent": self.input_data.get("compressed_size_kb", 0) * 1024
        })


# ==============================================================================
# Interactive Simulation Scenario
# ==============================================================================
def main():
    print(f"\n{Color.BOLD}{Color.CYAN}====================================================================")
    print("      DEEP DIVE: JETPACK WORKMANAGER ENGINE & CONSTRAINTS SIMULATION")
    print(f"===================================================================={Color.RESET}\n")

    engine = WorkManagerEngine()

    try:
        # 1. Definisikan Pipeline Menggunakan WorkContinuation (beginWith -> then)
        compress_req = WorkRequest(
            worker_class=ImageCompressWorker,
            name="CompressTask",
            initial_input={"image_size_kb": 4096}
        )

        watermark_req = WorkRequest(
            worker_class=WatermarkWorker,
            name="WatermarkTask"
        )

        # Upload membutuhkan Jaringan & Baterai Charging
        upload_req = WorkRequest(
            worker_class=CloudSyncWorker,
            name="UploadTask",
            constraints=Constraints(requires_network=True, requires_charging=True),
            backoff_policy=BackoffPolicy.EXPONENTIAL,
            initial_backoff_sec=0.5,
            max_retries=3
        )

        print(f"{Color.BOLD}Skenario Pipeline:{Color.RESET}")
        print("  1. Paralel: [CompressTask, WatermarkTask]")
        print("  2. Chained: -> UploadTask (Constraints: Network=True, Charging=True)\n")

        continuation = WorkContinuation(engine, [compress_req, watermark_req]).then([upload_req])
        continuation.enqueue()

        # Biarkan kompresi dan watermark berjalan (tanpa constraint)
        time.sleep(1.0)

        # Cek status UploadTask (harus masih tertahan karena constraint)
        print(f"\n{Color.BOLD}{Color.YELLOW}--> SIMULASI KONDISI PERANGKAT: UploadTask tertahan oleh batasan hardware...{Color.RESET}")
        time.sleep(0.8)

        # 2. Nyalakan Charger
        print(f"\n{Color.BOLD}{Color.MAGENTA}--> AKSI EVENT: Hubungkan Charger ke Device{Color.RESET}")
        engine.set_device_charging(True)
        time.sleep(0.8)

        # 3. Nyalakan Network (Memenuhi semua constraint UploadTask)
        print(f"\n{Color.BOLD}{Color.MAGENTA}--> AKSI EVENT: Hubungkan Jaringan WiFi ke Device{Color.RESET}")
        engine.set_device_network(True)

        # Tunggu sampai semua task selesai (termasuk penanganan Retry pada UploadTask)
        max_wait = 10.0
        start_t = time.time()
        while not engine.is_all_completed() and (time.time() - start_t) < max_wait:
            time.sleep(0.2)

        print(f"\n{Color.BOLD}{Color.GREEN}====================================================================")
        print("                 HASIL AKHIR WORKMANAGER EXECUTION")
        print(f"===================================================================={Color.RESET}")
        for req_id, req in engine._work_store.items():
            status_color = Color.GREEN if req.state == WorkState.SUCCEEDED else Color.RED
            print(f"• Work: {Color.BOLD}{req.name:<25}{Color.RESET} "
                  f"State: {status_color}{req.state.name:<10}{Color.RESET} "
                  f"Attempts: {req.run_attempt_count} "
                  f"Payload: {req.output_data}")

    finally:
        engine.shutdown()
        print(f"\n{Color.DIM}Engine shutdown clean. Thread pool release completed.{Color.RESET}\n")


if __name__ == "__main__":
    main()