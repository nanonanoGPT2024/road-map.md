#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Asynchronous, Concurrency & Networking di Flutter/Dart
Topik: Event Loop (Microtask vs Event Queue), Streams, Isolate Actor Model, & HTTP Interceptor
"""

import asyncio
import collections
import dataclasses
import json
import random
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{CYAN} [LAB] {title.center(57)} {RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")


def log_step(component: str, msg: str, color: str = GREEN) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{BOLD}[{timestamp}] [{color}{component}{RESET}]{BOLD}:{RESET} {msg}")


# ==============================================================================
# 1. SIMULASI DART EVENT LOOP: Microtask Queue vs Event Queue
# ==============================================================================
class DartEventLoopSimulator:
    """
    Mensimulasikan prioritas eksekusi Dart Event Loop:
    Semua Microtask dieksekusi sampai tuntas sebelum Event berikutnya diambil dari Event Queue.
    """
    def __init__(self) -> None:
        self.microtask_queue: collections.deque = collections.deque()
        self.event_queue: collections.deque = collections.deque()

    def schedule_microtask(self, name: str, action: Callable[[], None]) -> None:
        self.microtask_queue.append((name, action))
        log_step("Scheduler", f"Dischedulkan ke {MAGENTA}Microtask Queue{RESET}: {name}", MAGENTA)

    def schedule_event(self, name: str, action: Callable[[], None]) -> None:
        self.event_queue.append((name, action))
        log_step("Scheduler", f"Dischedulkan ke {YELLOW}Event Queue (Timer/Future){RESET}: {name}", YELLOW)

    def run(self) -> None:
        log_step("EventLoop", "Memulai siklus Dart Event Loop...", CYAN)
        cycle = 1
        while self.microtask_queue or self.event_queue:
            # Drain microtask queue first
            while self.microtask_queue:
                name, action = self.microtask_queue.popleft()
                log_step("EventLoop", f"Eksekusi Microtask (High-Priority): {BOLD}{name}{RESET}", MAGENTA)
                action()

            # Execute single event from event queue
            if self.event_queue:
                name, action = self.event_queue.popleft()
                log_step("EventLoop", f"[Cycle {cycle}] Eksekusi Event Queue Item: {BOLD}{name}{RESET}", YELLOW)
                action()
                cycle += 1

        log_step("EventLoop", f"{GREEN}Event Loop kosong (Idle / UI Frame Ready).{RESET}", GREEN)


# ==============================================================================
# 2. SIMULASI REACTIVE STREAM CONTROLLER (Dart Stream API)
# ==============================================================================
class StreamSubscription:
    def __init__(self, cancel_callback: Callable[[], None]) -> None:
        self._cancel_callback = cancel_callback
        self.is_active = True

    def cancel(self) -> None:
        if self.is_active:
            self._cancel_callback()
            self.is_active = False
            log_step("StreamSubscription", "Subscription dibatalkan (Clean-up memory).", RED)


class StreamController:
    """
    Simulasi StreamController<T> Dart untuk reactive async data pipelines.
    """
    def __init__(self) -> None:
        self._listeners: List[Callable[[Any], None]] = []
        self._is_closed = False

    def listen(self, on_data: Callable[[Any], None]) -> StreamSubscription:
        self._listeners.append(on_data)

        def _cancel() -> None:
            if on_data in self._listeners:
                self._listeners.remove(on_data)

        return StreamSubscription(_cancel)

    def add(self, event: Any) -> None:
        if self._is_closed:
            raise RuntimeError("Cannot add event to a closed stream!")
        log_step("StreamController", f"Sink.add -> Emitting event: {CYAN}{event}{RESET}", BLUE)
        for listener in list(self._listeners):
            listener(event)

    def close(self) -> None:
        self._is_closed = True
        log_step("StreamController", "Stream ditutup (Done signal emitted).", BLUE)


# ==============================================================================
# 3. SIMULASI ISOLATE: Worker Background Thread dengan Port Messaging
# ==============================================================================
class IsolateWorker:
    """
    Dart Isolate tidak berbagi memori (Shared-nothing memory model).
    Komunikasi dilakukan melalui SendPort / ReceivePort message passing.
    """
    def __init__(self) -> None:
        self.inbox: collections.deque = collections.deque()
        self.outbox: collections.deque = collections.deque()

    def _worker_entrypoint(self) -> None:
        log_step("IsolateThread", "Isolate baru spawning dengan heap memori terpisah...", MAGENTA)
        while True:
            if self.inbox:
                payload = self.inbox.popleft()
                if payload == "TERMINATE":
                    log_step("IsolateThread", "Isolate menerima sinyal terminate, shutting down.", MAGENTA)
                    break
                log_step("IsolateThread", f"Menghitung komputasi berat (Fibonacci n={payload})...", MAGENTA)
                # Heavy computation simulation
                result = self._fib(payload)
                self.outbox.append((payload, result))
            time.sleep(0.05)

    def _fib(self, n: int) -> int:
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    def run_isolate_task(self, n: int) -> None:
        t = threading.Thread(target=self._worker_entrypoint, daemon=True)
        t.start()
        log_step("MainIsolate", f"Mengirim pesan ke Isolate SendPort: compute(fib, {n})", CYAN)
        self.inbox.append(n)

        # Main isolate remains non-blocking and monitors progress
        log_step("MainIsolate", "Main thread bebas me-render UI (60/120 FPS tanpa jank)...", GREEN)
        for _ in range(3):
            time.sleep(0.1)
            log_step("UI-Engine", "Tick vsync frame render normal: Frame drawn OK.", CYAN)

        while not self.outbox:
            time.sleep(0.05)

        num, res = self.outbox.popleft()
        log_step("MainIsolate", f"Menerima hasil dari ReceivePort: Fib({num}) = {res}", GREEN)
        self.inbox.append("TERMINATE")
        t.join(timeout=1.0)


# ==============================================================================
# 4. SIMULASI NETWORK LAYER: Interceptors, Retries & JSON DTO Serialization
# ==============================================================================
@dataclasses.dataclass
class UserDTO:
    user_id: int
    name: str
    role: str
    token: str

    @classmethod
    def from_json(cls, raw: Dict[str, Any]) -> "UserDTO":
        return cls(
            user_id=raw["id"],
            name=raw["name"],
            role=raw["role"],
            token=raw.get("token", "anonymous-token"),
        )


class DioStyleHttpClient:
    """
    Simulasi HTTP Client canggih (seperti package dio di Flutter)
    dilengkapi Interceptor (onRequest, onResponse, onError) dan Retry mechanism.
    """
    def __init__(self, max_retries: int = 2) -> None:
        self.max_retries = max_retries

    async def _interceptor_on_request(self, endpoint: str, headers: Dict[str, str]) -> Dict[str, str]:
        log_step("Interceptor", f"Adding Auth Bearer Token ke request {endpoint}", BLUE)
        headers["Authorization"] = "Bearer dart_jwt_secure_token_xyz"
        headers["Content-Type"] = "application/json"
        return headers

    async def _interceptor_on_response(self, status: int, data: Dict[str, Any]) -> Dict[str, Any]:
        log_step("Interceptor", f"Status {status}: Auto-logging & unwrapping response envelope", BLUE)
        return data.get("data", data)

    async def get_user_profile(self, user_id: int) -> UserDTO:
        headers: Dict[str, str] = {}
        headers = await self._interceptor_on_request(f"/api/v1/users/{user_id}", headers)

        attempts = 0
        while attempts <= self.max_retries:
            attempts += 1
            log_step("HttpClient", f"GET /api/v1/users/{user_id} (Percobaan #{attempts})...", YELLOW)
            await asyncio.sleep(0.2)  # Simulates network I/O latency

            # Simulasi transien network glitch di percobaan pertama
            if attempts == 1:
                log_step("HttpClient", f"{RED}SocketException: Connection timeout. Melakukan exponential retry...{RESET}", RED)
                await asyncio.sleep(0.3)
                continue

            # Sukses di percobaan berikutnya
            raw_response = {
                "status": 200,
                "data": {
                    "id": user_id,
                    "name": "Nusantara Flutter Dev",
                    "role": "Lead Mobile Architect",
                    "token": headers["Authorization"],
                },
            }
            unwrapped = await self._interceptor_on_response(200, raw_response)
            user_dto = UserDTO.from_json(unwrapped)
            log_step("Deserializer", f"JSON di-parse ke Model Data Class: {user_dto}", GREEN)
            return user_dto

        raise ConnectionError("Gagal menghubungi remote API setelah retry berulang.")


# ==============================================================================
# 5. DEMO RUNNER & INTERACTIVE MENU
# ==============================================================================
def demo_event_loop() -> None:
    header("DEMO 1: Dart Event Loop Architecture")
    simulator = DartEventLoopSimulator()

    # Jadwalkan interleave event queue dan microtask queue
    simulator.schedule_event("Timer.periodic Tick (Event Queue)", lambda: print(f"   -> {YELLOW}[Action]{RESET} Timer rendering update."))
    simulator.schedule_microtask("scheduleMicrotask 1 (Internal Sync)", lambda: print(f"   -> {MAGENTA}[Action]{RESET} Microtask state normalization."))
    simulator.schedule_event("Future.delayed (Event Queue)", lambda: print(f"   -> {YELLOW}[Action]{RESET} Future HTTP callback processed."))
    simulator.schedule_microtask("scheduleMicrotask 2 (Mutation Observer)", lambda: print(f"   -> {MAGENTA}[Action]{RESET} Layout bounds recalculated."))

    simulator.run()


def demo_streams() -> None:
    header("DEMO 2: Dart Reactive StreamController Pipeline")
    controller = StreamController()

    # Subscriber 1: UI Widget listener
    sub1 = controller.listen(lambda event: print(f"   -> {GREEN}[UI StateNotifier]{RESET} Menerima nilai live: {event}"))

    # Subscriber 2: Analytics Logger
    sub2 = controller.listen(lambda event: print(f"   -> {BLUE}[AnalyticsLogger]{RESET} Telemetry event sent: {event}"))

    # Emit data
    events = ["State.Initial", "State.Loading", "State.Success(data: 42)"]
    for evt in events:
        controller.add(evt)
        time.sleep(0.1)

    sub2.cancel()
    log_step("StreamDemo", "Mengirimkan event lagi setelah Analytics unsubscribed...", YELLOW)
    controller.add("State.Refreshing")
    controller.close()


def demo_isolate() -> None:
    header("DEMO 3: Dart Isolate Multi-Thread Concurrency")
    isolate = IsolateWorker()
    isolate.run_isolate_task(35)


def demo_network_layer() -> None:
    header("DEMO 4: HTTP Client Interceptor & Retry Logic")
    client = DioStyleHttpClient(max_retries=2)

    async def _async_runner() -> None:
        user = await client.get_user_profile(user_id=101)
        print(f"\n{BOLD}{GREEN}✓ Berhasil Mengambil Profil Pengguna:{RESET}")
        print(f"  • ID   : {user.user_id}")
        print(f"  • Name : {user.name}")
        print(f"  • Role : {user.role}")
        print(f"  • Token: {user.token}")

    asyncio.run(_async_runner())


def run_all() -> None:
    demo_event_loop()
    demo_streams()
    demo_isolate()
    demo_network_layer()
    print(f"\n{BOLD}{GREEN}=== Seluruh Demonstrasi Fondasi Async/Network Flutter Berhasil Dijalankan ==={RESET}\n")


def main() -> None:
    while True:
        print(f"\n{BOLD}{CYAN}=== LAB FLUTTER BAB-05: ASYNCHRONOUS & CONCURRENCY SIMULATOR ==={RESET}")
        print("1. Simulasi Dart Event Loop (Microtask vs Event Queue)")
        print("2. Simulasi StreamController & Reactive Streams")
        print("3. Simulasi Dart Isolate & Actor Concurrency Model")
        print("4. Simulasi HTTP Client (Interceptor, Retry, JSON DTO)")
        print("5. Jalankan Semua Simulasi Secara Berurutan (Full Test)")
        print("0. Keluar")
        
        choice = input(f"\n{BOLD}Pilih menu (0-5): {RESET}").strip()
        if choice == "1":
            demo_event_loop()
        elif choice == "2":
            demo_streams()
        elif choice == "3":
            demo_isolate()
        elif choice == "4":
            demo_network_layer()
        elif choice == "5":
            run_all()
        elif choice == "0" or choice.lower() == "exit":
            print(f"{GREEN}Selesai. Selamat belajar arsitektur async Flutter!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan ulangi.{RESET}")


if __name__ == "__main__":
    # Jika dijalankan tanpa terminal interaktif, jalankan full suite
    if not sys.stdin.isatty():
        run_all()
    else:
        main()
