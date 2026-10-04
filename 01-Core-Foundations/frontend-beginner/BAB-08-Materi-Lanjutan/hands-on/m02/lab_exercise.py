#!/usr/bin/env python3
"""
Lab Hands-on: JS Asynchronous Runtime, Web API, & REST Client Simulation
Modul: 01-Core-Foundations / 08 - JavaScript Asinkron, Web API & Integrasi REST
Deskripsi:
    Simulasi arsitektur Event Loop JavaScript tingkat rendah:
    1. Single-Threaded Call Stack (LIFO)
    2. Microtask Queue (Job Queue / Promise callbacks)
    3. Macrotask Queue (Task Queue / Timer, Network I/O)
    4. Mock Web API Engine untuk HTTP request RESTful asynchronous
"""

import time
import json
import collections
from typing import Callable, Any, Dict, List, Optional

# --- ANSI Formatting Constants ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_CYAN    = "\033[96m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_RED     = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_BLUE    = "\033[94m"
CLR_BG_DARK = "\033[100m"


class PromiseState:
    PENDING = "PENDING"
    FULFILLED = "FULFILLED"
    REJECTED = "REJECTED"


class Promise:
    """
    Abstraksi Promise JS yang mengelola status internal, value/reason,
    dan mendaftarkan callback ke Microtask Queue ketika state bertransisi.
    """
    def __init__(self, executor: Optional[Callable[['Callable', 'Callable'], None]] = None):
        self.state = PromiseState.PENDING
        self.value: Any = None
        self.reason: Any = None
        self._fulfill_callbacks: List[Callable] = []
        self._reject_callbacks: List[Callable] = []

        if executor:
            try:
                executor(self._resolve, self._reject)
            except Exception as e:
                self._reject(e)

    def _resolve(self, value: Any) -> None:
        if self.state != PromiseState.PENDING:
            return
        self.state = PromiseState.FULFILLED
        self.value = value
        for cb in self._fulfill_callbacks:
            JSRuntime.current().enqueue_microtask(lambda c=cb, v=value: c(v))
        self._fulfill_callbacks.clear()

    def _reject(self, reason: Any) -> None:
        if self.state != PromiseState.PENDING:
            return
        self.state = PromiseState.REJECTED
        self.reason = reason
        for cb in self._reject_callbacks:
            JSRuntime.current().enqueue_microtask(lambda c=cb, r=reason: c(r))
        self._reject_callbacks.clear()

    def then(self, on_fulfilled: Optional[Callable] = None, on_rejected: Optional[Callable] = None) -> 'Promise':
        """Meniru Promise.prototype.then() dengan chaining asinkron."""
        next_promise = Promise()

        def handle_fulfill(val):
            if on_fulfilled:
                try:
                    result = on_fulfilled(val)
                    if isinstance(result, Promise):
                        result.then(next_promise._resolve, next_promise._reject)
                    else:
                        next_promise._resolve(result)
                except Exception as ex:
                    next_promise._reject(ex)
            else:
                next_promise._resolve(val)

        def handle_reject(err):
            if on_rejected:
                try:
                    result = on_rejected(err)
                    next_promise._resolve(result)
                except Exception as ex:
                    next_promise._reject(ex)
            else:
                next_promise._reject(err)

        if self.state == PromiseState.FULFILLED:
            JSRuntime.current().enqueue_microtask(lambda: handle_fulfill(self.value))
        elif self.state == PromiseState.REJECTED:
            JSRuntime.current().enqueue_microtask(lambda: handle_reject(self.reason))
        else:
            self._fulfill_callbacks.append(handle_fulfill)
            self._reject_callbacks.append(handle_reject)

        return next_promise

    def catch(self, on_rejected: Callable) -> 'Promise':
        """Shorthand method untuk .then(None, on_rejected)."""
        return self.then(None, on_rejected)

    @staticmethod
    def resolve(value: Any) -> 'Promise':
        p = Promise()
        p._resolve(value)
        return p


class JSRuntime:
    """
    Simulator Engine JavaScript tunggal: Call Stack, Web API Worker,
    Microtask Queue, dan Macrotask Queue.
    """
    _instance: Optional['JSRuntime'] = None

    def __init__(self):
        self.call_stack: List[str] = []
        self.microtask_queue: collections.deque = collections.deque()
        self.macrotask_queue: List[Dict[str, Any]] = []
        self.virtual_clock_ms: int = 0
        JSRuntime._instance = self

    @classmethod
    def current(cls) -> 'JSRuntime':
        if cls._instance is None:
            cls._instance = JSRuntime()
        return cls._instance

    def enqueue_microtask(self, task: Callable) -> None:
        self.microtask_queue.append(task)

    def enqueue_macrotask(self, name: str, task: Callable, delay_ms: int) -> None:
        scheduled_at = self.virtual_clock_ms + delay_ms
        self.macrotask_queue.append({
            "name": name,
            "fn": task,
            "trigger_time": scheduled_at
        })
        self.macrotask_queue.sort(key=lambda item: item["trigger_time"])

    def set_timeout(self, callback: Callable, delay_ms: int, tag: str = "setTimeout") -> None:
        """Simulasi Web API setTimeout."""
        print(f" {CLR_YELLOW}⚡ [WebAPI]{CLR_RESET} Mendaftarkan Timer '{tag}' ({delay_ms}ms)")
        self.enqueue_macrotask(f"TimerCallback::{tag}", callback, delay_ms)

    def fetch(self, url: str) -> Promise:
        """
        Simulasi Fetch API (Web API REST Client) mengembalikan objek Promise.
        Menghasilkan latensi jaringan dan deserialisasi response JSON.
        """
        promise = Promise()
        print(f" {CLR_BLUE}🌐 [WebAPI::Fetch]{CLR_RESET} Mengirim HTTP GET -> '{url}'")

        # Mock Database / Endpoints
        mock_db = {
            "/api/v1/users/42": {"id": 42, "name": "Budi Santoso", "role": "Frontend Dev", "status": 200},
            "/api/v1/users/42/repositories": [
                {"name": "vite-react-dashboard", "stars": 120},
                {"name": "micro-frontend-runtime", "stars": 450}
            ],
            "/api/v1/unstable-gateway": "HTTP 502 Bad Gateway"
        }

        # Simulasikan latensi transmisi jaringan (30ms - 80ms)
        latency = 60 if "repositories" in url else (30 if "users" in url else 90)

        def on_network_complete():
            if url in mock_db:
                payload = mock_db[url]
                if isinstance(payload, str) and "502" in payload:
                    print(f" {CLR_RED}✖ [Network]{CLR_RESET} Network Fail 502: {url}")
                    promise._reject(Exception(f"NetworkError: {payload}"))
                else:
                    response_obj = {
                        "status": 200,
                        "url": url,
                        "data": payload,
                        "json": lambda: payload
                    }
                    print(f" {CLR_GREEN}✔ [Network]{CLR_RESET} HTTP Response 200 dari {url}")
                    promise._resolve(response_obj)
            else:
                print(f" {CLR_RED}✖ [Network]{CLR_RESET} HTTP Response 404 dari {url}")
                promise._reject(Exception(f"NotFoundError: Endpoint {url} tidak ditemukan."))

        self.enqueue_macrotask(f"FetchI/O::{url}", on_network_complete, latency)
        return promise

    def run_event_loop(self) -> None:
        """
        Menjalankan loop eksekusi utama:
        1. Eksekusi Call Stack hingga kosong.
        2. Kuras tuntas Microtask Queue (Promises, queueMicrotask).
        3. Jalankan SATU Macrotask yang jatuh tempo, lalu kembali periksa microtask.
        """
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== MEMULAI EVENT LOOP JS ENGINE ==={CLR_RESET}\n")

        while self.microtask_queue or self.macrotask_queue:
            # Step 1: Kuras Microtask Queue (Run-to-completion)
            while self.microtask_queue:
                micro_fn = self.microtask_queue.popleft()
                self.call_stack.append("microtask_exec")
                print(f"  {CLR_MAGENTA}⚙ [Microtask Drain]{CLR_RESET} Mengeksekusi Promise handler...")
                micro_fn()
                self.call_stack.pop()

            # Step 2: Periksa Macrotask yang siap dieksekusi
            if self.macrotask_queue:
                # Cari task yang sudah jatuh tempo berdasarkan virtual clock
                ready_indices = [
                    i for i, t in enumerate(self.macrotask_queue) 
                    if t["trigger_time"] <= self.virtual_clock_ms
                ]

                if ready_indices:
                    task_info = self.macrotask_queue.pop(ready_indices[0])
                    print(f"\n{CLR_YELLOW}▶ [Macrotask Tick]{CLR_RESET} Menjalankan task: {task_info['name']} @ {self.virtual_clock_ms}ms")
                    self.call_stack.append(task_info['name'])
                    task_info['fn']()
                    self.call_stack.pop()
                else:
                    # Geser waktu virtual ke event macrotask berikutnya
                    next_task = self.macrotask_queue[0]
                    advance_delta = next_task["trigger_time"] - self.virtual_clock_ms
                    self.virtual_clock_ms = next_task["trigger_time"]
                    print(f"  {CLR_CYAN}⌛ [Virtual Clock]{CLR_RESET} Maju +{advance_delta}ms -> {self.virtual_clock_ms}ms")

        print(f"\n{CLR_BOLD}{CLR_CYAN}=== EVENT LOOP SELESAI (Stack & Queues Kosong) ==={CLR_RESET}\n")


def simulate_user_application() -> None:
    """
    Simulasi naskah JavaScript:
    Sinkronus -> Macrotask (setTimeout) -> Microtask (Promise) -> REST Waterfall Fetch.
    """
    runtime = JSRuntime.current()

    print(f"{CLR_BOLD}[1. Main Script Execution Started]{CLR_RESET}")

    # Synchronous Log
    print(" Console.log: 'Langkah Awal - Inisialisasi Script'")

    # Macrotask: setTimeout 50ms
    runtime.set_timeout(lambda: print(f" {CLR_YELLOW}⚡ Callback Timer (50ms) selesai dijalankan.{CLR_RESET}"), 50, tag="LogTimer")

    # Microtask Langsung via Promise.resolve()
    Promise.resolve("DATA_PROMISE_SEGERA").then(
        lambda data: print(f" {CLR_MAGENTA}⚙ Immediate Microtask 1: Resolved '{data}'{CLR_RESET}")
    ).then(
        lambda _: print(f" {CLR_MAGENTA}⚙ Chained Microtask 2: Eksekusi berantai selesai.{CLR_RESET}")
    )

    # REST Fetch Orchestration: Mengambil user -> Mengambil repositori secara berantai (Waterfall Pattern)
    print(" Inisiasi Pipeline Fetch REST...")
    (
        runtime.fetch("/api/v1/users/42")
        .then(lambda res: res["json"]())
        .then(lambda user_data: handle_user_profile(user_data, runtime))
        .catch(lambda err: print(f" {CLR_RED}✖ Error Handling di Catch Pipeline: {err}{CLR_RESET}"))
    )

    # Trigger skenario error integrasi Web API
    runtime.fetch("/api/v1/unstable-gateway").catch(
        lambda err: print(f" {CLR_RED}🛡️ Penanganan Graceful Fallback Gateway: {err}{CLR_RESET}")
    )

    # Synchronous Log Penutup
    print(" Console.log: 'Langkah Akhir Script Sinkron Selesai'")
    print(f"{CLR_BOLD}[Main Script Finished - Call Stack Kembali Kosong]{CLR_RESET}")


def handle_user_profile(user: Dict[str, Any], runtime: JSRuntime) -> Promise:
    """Helper callback yang memicu HTTP request kedua setelah request pertama tuntas."""
    print(f" {CLR_GREEN}★ Profile Diterima:{CLR_RESET} {user['name']} ({user['role']})")
    endpoint_repos = f"/api/v1/users/{user['id']}/repositories"
    
    return runtime.fetch(endpoint_repos).then(
        lambda res: handle_repositories(res["json"]())
    )


def handle_repositories(repos: List[Dict[str, Any]]) -> None:
    """Handler penutup untuk data repositori."""
    print(f" {CLR_GREEN}★ Repository Terload:{CLR_RESET}")
    for r in repos:
        print(f"   • {r['name']} ({r['stars']} ⭐)")


if __name__ == "__main__":
    # Eksekusi script instruksional langsung
    simulate_user_application()
    # Mulai pemrosesan asynchronous runtime
    JSRuntime.current().run_event_loop()