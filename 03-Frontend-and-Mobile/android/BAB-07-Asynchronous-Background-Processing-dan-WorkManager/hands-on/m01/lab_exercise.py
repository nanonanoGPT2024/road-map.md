#!/usr/bin/env python3
"""
Lab Exercise M01: Asynchronous Background Processing & WorkManager Fundamentals
Simulasi arsitektur background processing Android:
- Threading, Looper, MessageQueue, Handler vs Dispatchers.IO
- WorkManager Core: Worker, Constraints, BackoffPolicy, WorkContinuation (Chaining)
"""

import enum
import queue
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

# --- ANSI Terminal Color Palette ---
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
    BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 65}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.WHITE} [ANDROID ARCH] {title.upper()}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 65}{Colors.RESET}")


def log_step(tag: str, msg: str, color: str = Colors.WHITE) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{Colors.DIM}[{timestamp}]{Colors.RESET} {Colors.BOLD}[{tag}]{Colors.RESET} {color}{msg}{Colors.RESET}")


# =====================================================================
# BAGIAN 1: SIMULASI MAIN THREAD, LOOPER, & COROUTINE DISPATCHER (IO)
# =====================================================================

@dataclass
class Message:
    what: int
    callback: Optional[Callable[[], None]] = None
    data: str = ""


class MessageQueue:
    def __init__(self):
        self._q = queue.Queue()

    def enqueue(self, msg: Message):
        self._q.put(msg)

    def next(self, timeout=0.1) -> Optional[Message]:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None


class Looper:
    def __init__(self, name: str):
        self.name = name
        self.mq = MessageQueue()
        self.is_running = True

    def loop(self):
        while self.is_running:
            msg = self.mq.next(timeout=0.05)
            if msg:
                if msg.callback:
                    msg.callback()
                self.mq._q.task_done()


def demo_main_thread_and_io_dispatcher():
    header("Simulasi Main Thread Looper vs Dispatchers.IO")
    log_step("UI_THREAD", "Main Looper running. Frame budget: 16.6ms (60 FPS)...", Colors.GREEN)

    main_looper = Looper("MainThread")
    main_thread = threading.Thread(target=main_looper.loop, daemon=True)
    main_thread.start()

    print(f"\n{Colors.YELLOW}Skenario A: Menjalankan heavy blocking operation langsung di Main Thread (Anti-Pattern){Colors.RESET}")
    log_step("UI_THREAD", "Trigger blocking network call 1.5 detik langsung di Main Looper...", Colors.RED)

    blocked_done = threading.Event()
    def bad_task():
        time.sleep(1.2)
        log_step("UI_THREAD", "Selesai bad task! Tapi UI macet 1200ms -> ANR / Skipped 72 frames!", Colors.RED)
        blocked_done.set()

    main_looper.mq.enqueue(Message(what=1, callback=bad_task))
    blocked_done.wait()

    print(f"\n{Colors.GREEN}Skenario B: Offloading ke Background Thread / Dispatchers.IO dengan Callback UI{Colors.RESET}")
    io_done = threading.Event()

    def safe_io_task():
        log_step("DISPATCHER_IO", "Mulai fetch data dari REST API di thread pool latar belakang...", Colors.CYAN)
        time.sleep(0.8)
        data = "JSON_RESPONSE_USER_PROFILE_200_OK"
        log_step("DISPATCHER_IO", f"Data didapatkan: {data}. Posting update ke Main Thread Handler...", Colors.CYAN)

        def ui_update():
            log_step("UI_THREAD", f"Handler menerima hasil: Memperbarui TextView UI dengan data '{data}'!", Colors.GREEN)
            io_done.set()

        main_looper.mq.enqueue(Message(what=2, callback=ui_update))

    threading.Thread(target=safe_io_task, daemon=True).start()
    io_done.wait()

    main_looper.is_running = False
    main_thread.join(timeout=0.2)
    log_step("SUMMARY", "Looper & IO Offload simulation selesai dengan sukses.\n", Colors.MAGENTA)


# =====================================================================
# BAGIAN 2: SIMULASI WORKMANAGER ENGINE (CONSTRAINTS, RETRY, CHAINING)
# =====================================================================

class NetworkType(enum.Enum):
    NOT_REQUIRED = 1
    CONNECTED = 2
    UNMETERED = 3


class WorkState(enum.Enum):
    ENQUEUED = "ENQUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRY = "RETRY"
    CANCELLED = "CANCELLED"


class BackoffPolicy(enum.Enum):
    LINEAR = "LINEAR"
    EXPONENTIAL = "EXPONENTIAL"


@dataclass
class Constraints:
    required_network_type: NetworkType = NetworkType.NOT_REQUIRED
    requires_charging: bool = False
    requires_battery_not_low: bool = False

    def is_satisfied(self, net: NetworkType, charging: bool, battery_level: int) -> bool:
        if self.required_network_type == NetworkType.CONNECTED and net == NetworkType.NOT_REQUIRED:
            return False
        if self.required_network_type == NetworkType.UNMETERED and net != NetworkType.UNMETERED:
            return False
        if self.requires_charging and not charging:
            return False
        if self.requires_battery_not_low and battery_level < 20:
            return False
        return True


@dataclass
class DeviceSystemState:
    network: NetworkType = NetworkType.CONNECTED
    charging: bool = False
    battery_level: int = 85


class ListenableWorkerResult(enum.Enum):
    SUCCESS = "Result.success()"
    FAILURE = "Result.failure()"
    RETRY = "Result.retry()"


class BaseWorker:
    def __init__(self, name: str):
        self.name = name

    def do_work(self, input_data: dict) -> tuple[ListenableWorkerResult, dict]:
        raise NotImplementedError


@dataclass
class WorkRequest:
    id: str
    worker_class: type[BaseWorker]
    tag: str
    constraints: Constraints = field(default_factory=Constraints)
    backoff_policy: BackoffPolicy = BackoffPolicy.EXPONENTIAL
    backoff_delay_sec: float = 1.0
    run_attempt_count: int = 0
    state: WorkState = WorkState.ENQUEUED
    input_data: dict = field(default_factory=dict)
    output_data: dict = field(default_factory=dict)


class WorkManagerEngine:
    def __init__(self, system_state: DeviceSystemState):
        self.system_state = system_state
        self.work_queue: List[WorkRequest] = []

    def enqueue(self, request: WorkRequest):
        log_step("WORKMANAGER", f"Request '{request.tag}' [{request.id[:6]}] dimasukkan ke Room Database (State: {request.state.value})", Colors.CYAN)
        self.work_queue.append(request)

    def run_worker_now(self, request: WorkRequest) -> bool:
        if not request.constraints.is_satisfied(
            self.system_state.network,
            self.system_state.charging,
            self.system_state.battery_level
        ):
            log_step("WORKMANAGER", f"Constraints belum terpenuhi untuk '{request.tag}'. Menunggu trigger OS...", Colors.YELLOW)
            return False

        request.state = WorkState.RUNNING
        log_step("WORKER_EXEC", f"Instantiating Worker: {request.worker_class.__name__} (Attempt #{request.run_attempt_count + 1})", Colors.BOLD)

        worker_instance = request.worker_class(request.tag)
        result, output = worker_instance.do_work(request.input_data)
        request.output_data = output

        if result == ListenableWorkerResult.SUCCESS:
            request.state = WorkState.SUCCEEDED
            log_step("WORKER_EXEC", f"Worker '{request.tag}' SUCCEEDED with output: {output}", Colors.GREEN)
            return True
        elif result == ListenableWorkerResult.RETRY:
            request.run_attempt_count += 1
            request.state = WorkState.RETRY
            if request.backoff_policy == BackoffPolicy.EXPONENTIAL:
                delay = request.backoff_delay_sec * (2 ** (request.run_attempt_count - 1))
            else:
                delay = request.backoff_delay_sec * request.run_attempt_count
            log_step("WORKER_EXEC", f"Worker '{request.tag}' RETRY diminta. Backoff {request.backoff_policy.value} menunggu {delay:.1f} detik...", Colors.YELLOW)
            time.sleep(min(delay, 2.0))
            return self.run_worker_now(request)
        else:
            request.state = WorkState.FAILED
            log_step("WORKER_EXEC", f"Worker '{request.tag}' FAILED permanen.", Colors.RED)
            return False


# Concrete Worker Implementations
class ImageFilterWorker(BaseWorker):
    def do_work(self, input_data: dict) -> tuple[ListenableWorkerResult, dict]:
        img = input_data.get("image_uri", "raw_photo.jpg")
        log_step(self.name, f"Mengaplikasikan filter Vignette & Sepia ke {img}...", Colors.WHITE)
        time.sleep(0.4)
        return ListenableWorkerResult.SUCCESS, {"filtered_uri": "filtered_" + img}


class ImageCompressWorker(BaseWorker):
    def do_work(self, input_data: dict) -> tuple[ListenableWorkerResult, dict]:
        img = input_data.get("filtered_uri", "filtered_photo.jpg")
        log_step(self.name, f"Kompresi WebP lossy 80% pada {img}...", Colors.WHITE)
        time.sleep(0.3)
        return ListenableWorkerResult.SUCCESS, {"compressed_uri": "compressed_" + img, "bytes": 240500}


class CloudUploadWorker(BaseWorker):
    def __init__(self, name: str):
        super().__init__(name)
        self.fail_once = True

    def do_work(self, input_data: dict) -> tuple[ListenableWorkerResult, dict]:
        target = input_data.get("compressed_uri", "unknown.webp")
        log_step(self.name, f"Mengunggah {target} ke S3 / Firebase Storage...", Colors.WHITE)
        time.sleep(0.5)

        # Simulasi network glitch di attempt 0
        if self.fail_once:
            self.fail_once = False
            log_step(self.name, "Network Socket Timeout (504 Gateway Timeout). Meminta Retry.", Colors.RED)
            return ListenableWorkerResult.RETRY, {}

        log_step(self.name, "Upload selesai 100%! Server return HTTP 201 Created.", Colors.GREEN)
        return ListenableWorkerResult.SUCCESS, {"remote_url": "https://storage.cloud.android/images/uuid_123.webp"}


# =====================================================================
# SCENARIOS DEMONSTRATION
# =====================================================================

def demo_constraints_and_lifecycle():
    header("WorkManager: Constraints Verification & Execution Lifecycle")
    state = DeviceSystemState(network=NetworkType.NOT_REQUIRED, charging=False, battery_level=12)
    engine = WorkManagerEngine(state)

    req = WorkRequest(
        id="wr-001",
        worker_class=ImageFilterWorker,
        tag="PreprocessImageWorker",
        constraints=Constraints(
            required_network_type=NetworkType.CONNECTED,
            requires_battery_not_low=True
        ),
        input_data={"image_uri": "camera_capture_001.jpg"}
    )

    engine.enqueue(req)
    log_step("SYSTEM", f"Kondisi awal perangkat: Network={state.network.name}, Battery={state.battery_level}%", Colors.DIM)
    log_step("OS_EVENT", "Mencoba eksekusi saat kondisi baterai lemah & offline...", Colors.YELLOW)
    engine.run_worker_now(req)

    print(f"\n{Colors.CYAN}--> Simulasi Event OS: Pengguna menyambungkan Wi-Fi dan mengisi daya baterai...{Colors.RESET}")
    time.sleep(0.5)
    state.network = NetworkType.CONNECTED
    state.battery_level = 65
    state.charging = True
    log_step("SYSTEM", f"Kondisi perangkat sekarang: Network={state.network.name}, Battery={state.battery_level}%, Charging=True", Colors.GREEN)

    log_step("OS_EVENT", "WorkManager JobScheduler / WorkDatabase mendeteksi trigger constraints satisfied!", Colors.GREEN)
    engine.run_worker_now(req)


def demo_chaining_and_continuation():
    header("WorkManager: WorkContinuation Pipeline (Filter -> Compress -> Upload)")
    state = DeviceSystemState(network=NetworkType.CONNECTED, charging=True, battery_level=90)
    engine = WorkManagerEngine(state)

    pipeline_input = {"image_uri": "profile_avatar.raw"}
    print(f"{Colors.BOLD}Pipeline: [ImageFilterWorker] -> [ImageCompressWorker] -> [CloudUploadWorker]{Colors.RESET}\n")

    filter_req = WorkRequest("w1", ImageFilterWorker, "Stage1_Filter", input_data=pipeline_input)
    engine.run_worker_now(filter_req)

    compress_req = WorkRequest("w2", ImageCompressWorker, "Stage2_Compress", input_data=filter_req.output_data)
    engine.run_worker_now(compress_req)

    upload_req = WorkRequest(
        "w3", CloudUploadWorker, "Stage3_Upload",
        constraints=Constraints(required_network_type=NetworkType.CONNECTED),
        input_data=compress_req.output_data
    )
    engine.run_worker_now(upload_req)

    print(f"\n{Colors.BOLD}{Colors.GREEN}=== WorkContinuation Chain Selesai! Final Result URL: {upload_req.output_data.get('remote_url')} ==={Colors.RESET}")


def interactive_menu():
    system_state = DeviceSystemState()
    while True:
        header("Android Background Processing & WorkManager Lab")
        print(f" {Colors.BOLD}1.{Colors.RESET} Demo Looper, MessageQueue & Dispatchers.IO Thread Offloading")
        print(f" {Colors.BOLD}2.{Colors.RESET} Demo WorkManager Constraints & Trigger Lifecycle")
        print(f" {Colors.BOLD}3.{Colors.RESET} Demo WorkManager Sequential Chaining (Filter -> Compress -> Upload)")
        print(f" {Colors.BOLD}4.{Colors.RESET} Jalankan Seluruh Skenario Otomatis (Full Verification)")
        print(f" {Colors.BOLD}0.{Colors.RESET} Keluar")
        print(f"{Colors.CYAN}{'-' * 65}{Colors.RESET}")

        try:
            choice = input(f"{Colors.BOLD}Pilih opsi [0-4]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            demo_main_thread_and_io_dispatcher()
        elif choice == "2":
            demo_constraints_and_lifecycle()
        elif choice == "3":
            demo_chaining_and_continuation()
        elif choice == "4":
            demo_main_thread_and_io_dispatcher()
            demo_constraints_and_lifecycle()
            demo_chaining_and_continuation()
        elif choice == "0":
            print(f"{Colors.GREEN}Lab selesai. Sampai jumpa!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan coba lagi.{Colors.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        demo_main_thread_and_io_dispatcher()
        demo_constraints_and_lifecycle()
        demo_chaining_and_continuation()
    else:
        interactive_menu()
