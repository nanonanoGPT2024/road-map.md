#!/usr/bin/env python3
"""
Lab Exercise M01: Data Synchronization & Enterprise State Management Simulator
Topik: BAB-06 - Data Synchronization dan Enterprise State Management (React)

Fitur Simulasi:
1. Cache Engine & Stale-While-Revalidate (SWR / TanStack Query pattern)
2. Enterprise Global Store & State Slice (Zustand / Redux pattern)
3. Optimistic Updates & Automated Rollback on Mutation Failure
4. Middleware Pipeline & Action Dispatch Tracking
"""

import sys
import time
import json
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[40m"


def header(title: str) -> None:
    line = "=" * 65
    print(f"\n{CLR_CYAN}{CLR_BOLD}{line}")
    print(f" {title.center(63)} ")
    print(f"{line}{CLR_RESET}\n")


def log_event(category: str, message: str, color: str = CLR_GREEN) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{CLR_BOLD}[{timestamp}] [{category.upper()}]{CLR_RESET} {color}{message}{CLR_RESET}")


# ---------------------------------------------------------------------------
# 1. Query Client & Cache Store (TanStack Query / SWR Pattern)
# ---------------------------------------------------------------------------
@dataclass
class CacheEntry:
    key: str
    data: Any
    updated_at: float
    stale_time: float = 3.0  # Detik sebelum dianggap stale

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.updated_at) > self.stale_time


class QueryClient:
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}

    def get_query_data(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        return entry.data if entry else None

    def set_query_data(self, key: str, data: Any, stale_time: float = 3.0) -> None:
        self._cache[key] = CacheEntry(key=key, data=data, updated_at=time.time(), stale_time=stale_time)

    def invalidate_queries(self, key: str) -> None:
        if key in self._cache:
            # Paksa timestamp mundur agar langsung stale
            self._cache[key].updated_at = 0
            log_event("Cache", f"Cache key '{key}' invalidated!", CLR_YELLOW)

    def fetch_with_swr(self, key: str, fetcher: Callable[[], Any], stale_time: float = 3.0) -> Any:
        entry = self._cache.get(key)
        if entry is None:
            log_event("Query", f"MISS: Fetching fresh data for '{key}' from backend...", CLR_MAGENTA)
            fresh_data = fetcher()
            self.set_query_data(key, fresh_data, stale_time)
            return fresh_data

        if entry.is_stale:
            log_event("Query", f"STALE-HIT: Serving stale cache for '{key}', background refetching...", CLR_YELLOW)
            # Simulasi asynchronous background refetch
            background_data = fetcher()
            self.set_query_data(key, background_data, stale_time)
            log_event("Query", f"SYNC: Cache updated silently for '{key}'.", CLR_GREEN)
            return entry.data  # Kembalikan data lama terlebih dahulu (Stale-While-Revalidate)

        log_event("Query", f"FRESH-HIT: Cache key '{key}' masih segar. Hindari network call.", CLR_CYAN)
        return entry.data


# ---------------------------------------------------------------------------
# 2. Enterprise State Store (Zustand / Redux Slice Architecture)
# ---------------------------------------------------------------------------
class EnterpriseStore:
    def __init__(self, initial_state: Dict[str, Any]):
        self._state = dict(initial_state)
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._middlewares: List[Callable[[str, Any, Dict[str, Any]], None]] = []

    def get_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def add_middleware(self, middleware: Callable[[str, Any, Dict[str, Any]], None]) -> None:
        self._middlewares.append(middleware)

    def dispatch(self, action_type: str, payload: Any, reducer: Callable[[Dict[str, Any], Any], Dict[str, Any]]) -> None:
        prev_state = dict(self._state)
        for mw in self._middlewares:
            mw(action_type, payload, prev_state)

        next_state = reducer(prev_state, payload)
        self._state = next_state

        for subscriber in self._subscribers:
            subscriber(self._state)


# ---------------------------------------------------------------------------
# 3. Optimistic Update & Mutation Manager
# ---------------------------------------------------------------------------
class MutationManager:
    def __init__(self, store: EnterpriseStore, query_client: QueryClient):
        self.store = store
        self.query_client = query_client

    def mutate(
        self,
        mutation_name: str,
        payload: Any,
        optimistic_updater: Callable[[Dict[str, Any], Any], Dict[str, Any]],
        remote_executor: Callable[[Any], bool],
        query_key: str,
    ) -> bool:
        log_event("Mutation", f"Memulai optimistik mutasi: '{mutation_name}'", CLR_BLUE)
        snapshot = self.store.get_state()

        # 1. Terapkan update optimistik ke store secara instan
        self.store.dispatch(
            f"OPTIMISTIC_{mutation_name}",
            payload,
            lambda state, data: optimistic_updater(state, data),
        )
        log_event("UI", "UI ter-render instan berdasarkan optimistic state!", CLR_CYAN)

        # 2. Eksekusi server request
        log_event("Network", "Mengirim payload mutasi ke REST/GraphQL backend...", CLR_MAGENTA)
        success = remote_executor(payload)

        if success:
            log_event("Mutation", f"Mutasi '{mutation_name}' sukses di server!", CLR_GREEN)
            self.query_client.invalidate_queries(query_key)
            return True
        else:
            log_event("Error", f"Server gagal memproses mutasi! Memulai Automatic Rollback...", CLR_RED)
            # Rollback ke snapshot awal
            self.store.dispatch(
                f"ROLLBACK_{mutation_name}",
                snapshot,
                lambda _, prev: dict(prev),
            )
            log_event("UI", "Rollback selesai. State UI dipulihkan ke versi konsisten.", CLR_YELLOW)
            return False


# ---------------------------------------------------------------------------
# 4. Interactive Runner & Demo Suites
# ---------------------------------------------------------------------------
def simulate_swr_lifecycle(client: QueryClient) -> None:
    header("DEMO 1: SWR / TanStack Query Caching Lifecycle")

    fetch_counter = 0

    def mock_backend_fetch():
        nonlocal fetch_counter
        fetch_counter += 1
        return {"users": ["Alice", "Bob", "Charlie"], "version": fetch_counter}

    key = "users_list"
    print(f"{CLR_BOLD}Langkah 1: Initial Fetch (Cold Cache){CLR_RESET}")
    res1 = client.fetch_with_swr(key, mock_backend_fetch, stale_time=2.0)
    print(f"Hasil Data UI: {json.dumps(res1)}")

    print(f"\n{CLR_BOLD}Langkah 2: Fetch Ulang Cepat (< 2 detik, Cache Segar){CLR_RESET}")
    res2 = client.fetch_with_swr(key, mock_backend_fetch, stale_time=2.0)
    print(f"Hasil Data UI: {json.dumps(res2)}")

    print(f"\n{CLR_BOLD}Langkah 3: Tidur 2.5 detik agar cache STALE...{CLR_RESET}")
    time.sleep(2.5)

    print(f"{CLR_BOLD}Langkah 4: Fetch Setelah Stale (Stale-While-Revalidate){CLR_RESET}")
    res3 = client.fetch_with_swr(key, mock_backend_fetch, stale_time=2.0)
    print(f"Hasil Data Diterima UI: {json.dumps(res3)}")
    print(f"Data Terkini di Cache QueryClient: {json.dumps(client.get_query_data(key))}")


def simulate_optimistic_update(store: EnterpriseStore, client: QueryClient) -> None:
    header("DEMO 2: Optimistic Mutation & Automatic Rollback")
    mutation_mgr = MutationManager(store, client)

    def optimistic_add_todo(state: Dict[str, Any], new_item: str) -> Dict[str, Any]:
        todos = list(state.get("todos", []))
        todos.append(new_item)
        return {**state, "todos": todos}

    def failing_server_call(payload: Any) -> bool:
        time.sleep(0.6)
        # Simulasi network timeout / HTTP 500
        return False

    def successful_server_call(payload: Any) -> bool:
        time.sleep(0.6)
        # Simulasi HTTP 201 Created
        return True

    print(f"State Awal: {store.get_state()}")

    print(f"\n{CLR_BOLD}Skenario A: Mutasi Berhasil{CLR_RESET}")
    mutation_mgr.mutate(
        mutation_name="ADD_TODO_SUCCESS",
        payload="Belajar Zustand & Redux Toolkit",
        optimistic_updater=optimistic_add_todo,
        remote_executor=successful_server_call,
        query_key="todos",
    )
    print(f"State Akhir Skenario A: {store.get_state()}")

    print(f"\n{CLR_BOLD}Skenario B: Mutasi Gagal Server (500 Error / Rollback){CLR_RESET}")
    mutation_mgr.mutate(
        mutation_name="ADD_TODO_FAIL",
        payload="Item yang akan ditolak server",
        optimistic_updater=optimistic_add_todo,
        remote_executor=failing_server_call,
        query_key="todos",
    )
    print(f"State Akhir Skenario B (Tervalidasi Rollback): {store.get_state()}")


def main() -> None:
    header("BAB-06: Enterprise State & Data Synchronization Lab")
    print(f"{CLR_CYAN}Menginisialisasi Global Architecture Simulator...{CLR_RESET}")

    # Setup Store
    initial_state = {
        "todos": ["Persiapkan Arsitektur Monorepo", "Setup TanStack Query"],
        "user_session": {"username": "tech_lead", "role": "admin"},
    }
    store = EnterpriseStore(initial_state)

    # Logging Middleware (mirip redux-logger)
    def redux_logger(action: str, payload: Any, prev_state: Dict[str, Any]):
        print(f"  {CLR_BLUE}⚡ [Middleware: Action]{CLR_RESET} {action} | Payload: {payload}")

    store.add_middleware(redux_logger)
    client = QueryClient()

    # Pre-populate query cache
    client.set_query_data("todos", initial_state["todos"], stale_time=4.0)

    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Mode otomatis tanpa input prompt
        simulate_swr_lifecycle(client)
        simulate_optimistic_update(store, client)
        header("Simulasi Selesai dengan Sukses!")
        return

    while True:
        print("\n" + "=" * 50)
        print(f"{CLR_BOLD}MENU INTERAKTIF LAB PRAKTIKUM:{CLR_RESET}")
        print("1. Jalankan Simulasi Cache SWR (TanStack Query)")
        print("2. Jalankan Simulasi Optimistic Updates & Rollback")
        print("3. Tampilkan State Global Terkini (Zustand Store)")
        print("4. Jalankan Seluruh Skenario Otomatis (Full Run)")
        print("5. Keluar")
        print("=" * 50)

        choice = input(f"{CLR_YELLOW}Pilih opsi (1-5): {CLR_RESET}").strip()
        if choice == "1":
            simulate_swr_lifecycle(client)
        elif choice == "2":
            simulate_optimistic_update(store, client)
        elif choice == "3":
            header("State Store Global Saat Ini")
            print(json.dumps(store.get_state(), indent=2))
        elif choice == "4":
            simulate_swr_lifecycle(client)
            simulate_optimistic_update(store, client)
        elif choice == "5":
            print(f"\n{CLR_GREEN}Terima kasih! Sesi lab simulasi selesai.{CLR_RESET}\n")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid, silakan ulangi.{CLR_RESET}")


if __name__ == "__main__":
    main()
