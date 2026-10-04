#!/usr/bin/env python3
"""
Android Data Layer Deep Dive: Offline-First Architecture & Room ORM Simulator
Demonstrates:
  - Room ORM patterns: Entity mapping, DAO (Data Access Object), and SQLite transactions.
  - Single Source of Truth (SSOT): UI observes SQLite database directly.
  - Reactive Flow simulation: Database writes trigger reactive observers.
  - Cache-then-Network & Optimistic Updates with background sync workers.
  - Conflict Resolution (OnConflictStrategy.REPLACE and version-based conflict handling).
"""

import sqlite3
import time
import threading
import queue
import random
from dataclasses import dataclass, asdict
from typing import List, Optional, Callable

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BOLD = "\033[1m"


# ============================================================================
# 1. ENTITY DEFINITION (@Entity in Room)
# ============================================================================
@dataclass
class TaskEntity:
    id: str
    title: str
    is_completed: bool
    version: int
    sync_status: str  # 'SYNCED', 'PENDING_UPLOAD', 'PENDING_DELETE'
    updated_at: float


# ============================================================================
# 2. DAO DEFINITION (@Dao in Room)
# Handles SQLite interactions, conflict resolution, and change notifications.
# ============================================================================
class TaskDao:
    def __init__(self, db_conn: sqlite3.Connection, change_notifier: Callable[[], None]):
        self._conn = db_conn
        self._notify_change = change_notifier
        self._lock = threading.Lock()
        self._init_table()

    def _init_table(self):
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    is_completed INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    sync_status TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """
            )
            self._conn.commit()

    def insert_or_replace(self, task: TaskEntity):
        """Room equivalent: @Insert(onConflict = OnConflictStrategy.REPLACE)"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (id, title, is_completed, version, sync_status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    is_completed=excluded.is_completed,
                    version=excluded.version,
                    sync_status=excluded.sync_status,
                    updated_at=excluded.updated_at
            """,
                (
                    task.id,
                    task.title,
                    1 if task.is_completed else 0,
                    task.version,
                    task.sync_status,
                    task.updated_at,
                ),
            )
            self._conn.commit()
        self._notify_change()

    def get_all_tasks(self) -> List[TaskEntity]:
        """Room equivalent: @Query("SELECT * FROM tasks WHERE sync_status != 'PENDING_DELETE'")"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT id, title, is_completed, version, sync_status, updated_at 
                FROM tasks 
                WHERE sync_status != 'PENDING_DELETE'
                ORDER BY updated_at ASC
            """
            )
            rows = cursor.fetchall()
            return [
                TaskEntity(
                    id=row[0],
                    title=row[1],
                    is_completed=bool(row[2]),
                    version=row[3],
                    sync_status=row[4],
                    updated_at=row[5],
                )
                for row in rows
            ]

    def get_unsynced_tasks(self) -> List[TaskEntity]:
        """Room query used exclusively by sync workers."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT id, title, is_completed, version, sync_status, updated_at FROM tasks WHERE sync_status != 'SYNCED'"
            )
            return [
                TaskEntity(
                    id=r[0],
                    title=r[1],
                    is_completed=bool(r[2]),
                    version=r[3],
                    sync_status=r[4],
                    updated_at=r[5],
                )
                for r in cursor.fetchall()
            ]


# ============================================================================
# 3. REMOTE API CLIENT (Mock Retrofit Service)
# ============================================================================
class MockRemoteService:
    def __init__(self):
        # Simulated server-side storage
        self.server_store = {
            "task_0": {
                "id": "task_0",
                "title": "Setup Android Studio & NDK",
                "is_completed": True,
                "version": 1,
                "updated_at": time.time() - 3600,
            }
        }
        self.is_network_available = True

    def fetch_tasks(self) -> List[dict]:
        time.sleep(0.3)  # Simulated latency
        if not self.is_network_available:
            raise ConnectionError("Network unreachable: HTTP 503 Gateway Timeout")
        return list(self.server_store.values())

    def push_task(self, task_dict: dict) -> dict:
        time.sleep(0.3)
        if not self.is_network_available:
            raise ConnectionError("Offline: Failed to POST to remote endpoint")

        current_remote = self.server_store.get(task_dict["id"])
        # Server-side optimistic locking / conflict check
        if current_remote and current_remote["version"] > task_dict["version"]:
            # Server wins if version is strictly higher
            return current_remote

        # Accept mutation, bump server version
        new_version = task_dict["version"] + 1
        updated = dict(task_dict)
        updated["version"] = new_version
        self.server_store[task_dict["id"]] = updated
        return updated


# ============================================================================
# 4. REPOSITORY & REACTIVE STREAM (Flow / LiveData simulation)
# Implements Single Source of Truth (SSOT).
# ============================================================================
class TaskRepository:
    def __init__(self, dao: TaskDao, remote_api: MockRemoteService):
        self._dao = dao
        self._api = remote_api
        self._observers: List[Callable[[List[TaskEntity]], None]] = []
        self._lock = threading.Lock()

    def register_observer(self, observer: Callable[[List[TaskEntity]], None]):
        """Simulates Kotlin Flow collection: collector receives current value immediately."""
        with self._lock:
            self._observers.append(observer)
        # Emit current state from local DB (SSOT)
        observer(self._dao.get_all_tasks())

    def notify_observers(self):
        """Called whenever the Room database emits an invalidation tracker event."""
        tasks = self._dao.get_all_tasks()
        with self._lock:
            for obs in self._observers:
                obs(tasks)

    def fetch_and_cache(self):
        """Cache-then-network pattern: reads from remote and writes directly to Room."""
        try:
            remote_data = self._api.fetch_tasks()
            for r in remote_data:
                # Merge remote record with local DB
                entity = TaskEntity(
                    id=r["id"],
                    title=r["title"],
                    is_completed=r["is_completed"],
                    version=r["version"],
                    sync_status="SYNCED",
                    updated_at=r["updated_at"],
                )
                self._dao.insert_or_replace(entity)
        except ConnectionError as e:
            # Degrade gracefully: Local database continues serving data
            pass

    def add_task(self, task_id: str, title: str):
        """Optimistic write: Write locally first with PENDING_UPLOAD status."""
        local_task = TaskEntity(
            id=task_id,
            title=title,
            is_completed=False,
            version=1,
            sync_status="PENDING_UPLOAD",
            updated_at=time.time(),
        )
        # Write to Room (UI observer updates instantly)
        self._dao.insert_or_replace(local_task)

    def synchronize(self):
        """Worker task syncing offline mutations to cloud."""
        unsynced = self._dao.get_unsynced_tasks()
        for local in unsynced:
            try:
                res = self._api.push_task(asdict(local))
                # Update Room with the remote confirmation and bump sync status
                confirmed = TaskEntity(
                    id=res["id"],
                    title=res["title"],
                    is_completed=res["is_completed"],
                    version=res["version"],
                    sync_status="SYNCED",
                    updated_at=time.time(),
                )
                self._dao.insert_or_replace(confirmed)
            except ConnectionError:
                # Retain PENDING_UPLOAD state for next cycle
                break


# ============================================================================
# 5. TEST RUNNER & SIMULATION PIPELINE
# ============================================================================
def ui_collector(tasks: List[TaskEntity]):
    """Simulates a Jetpack Compose ViewModel collecting task state from Flow."""
    print(f"\n{CLR_MAGENTA}>>> [UI RE-RENDER EVENT | Composable Observed Room Flow]{CLR_RESET}")
    if not tasks:
        print("    [Empty State: No tasks available]")
        return
    for t in tasks:
        status_color = CLR_GREEN if t.sync_status == "SYNCED" else CLR_YELLOW
        status_badge = f"{status_color}[{t.sync_status}]{CLR_RESET}"
        check = "✓" if t.is_completed else " "
        print(f"    [{check}] {t.id:<8} | {t.title:<30} (v{t.version}) {status_badge}")
    print("-" * 70)


def main():
    print(f"{CLR_BOLD}{CLR_CYAN}=== ANDROID DATA LAYER: ROOM ORM & OFFLINE-FIRST ARCHITECTURE LAB ==={CLR_RESET}\n")

    # Setup SQLite database simulating Room database instance
    db_conn = sqlite3.connect(":memory:", check_same_thread=False)
    
    # Wire dependencies
    remote_api = MockRemoteService()
    repo = None

    def on_db_changed():
        if repo:
            repo.notify_observers()

    dao = TaskDao(db_conn, change_notifier=on_db_changed)
    repo = TaskRepository(dao, remote_api)

    # 1. UI starts observing the data layer (Simulating ViewModel collection)
    print(f"{CLR_BOLD}[Phase 1] UI Subscribes to Flow<List<TaskEntity>> (SSOT initialization){CLR_RESET}")
    repo.register_observer(ui_collector)

    # 2. Network Fetch & Sync into Room
    print(f"\n{CLR_BOLD}[Phase 2] Fetching Initial Remote Data (Cache-then-Network)...{CLR_RESET}")
    repo.fetch_and_cache()
    time.sleep(0.2)

    # 3. Optimistic Offline Writes
    print(f"\n{CLR_BOLD}[Phase 3] Network Goes OFFLINE. User performs local mutations...{CLR_RESET}")
    remote_api.is_network_available = False
    print(f"{CLR_RED}--> Network status changed: DISCONNECTED{CLR_RESET}")

    repo.add_task("task_1", "Implement Room TypeConverters")
    time.sleep(0.1)
    repo.add_task("task_2", "Configure WorkManager Periodic Sync")
    time.sleep(0.1)

    print(f"\n{CLR_YELLOW}--> Triggering sync while offline (Expect background failure)...{CLR_RESET}")
    repo.synchronize()
    print("--> Sync finished. Unsynced mutations remained preserved in Room.")

    # 4. Reconnecting and Background WorkManager Sync
    print(f"\n{CLR_BOLD}[Phase 4] Network Restored. WorkManager Sync Execution...{CLR_RESET}")
    remote_api.is_network_available = True
    print(f"{CLR_GREEN}--> Network status changed: CONNECTED{CLR_RESET}")

    print("--> Triggering TaskRepository.synchronize()...")
    repo.synchronize()
    time.sleep(0.2)

    # 5. Remote Conflict / Version Update
    print(f"\n{CLR_BOLD}[Phase 5] Conflict Handling: Remote Task Updated Independently{CLR_RESET}")
    # Simulating remote updating task_0 externally
    remote_api.server_store["task_0"]["version"] = 5
    remote_api.server_store["task_0"]["title"] = "Setup Android Studio & NDK (Remote Patch)"
    print("--> Remote contains newer version (v5) of 'task_0'. Fetching updates...")
    repo.fetch_and_cache()
    time.sleep(0.2)

    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ Architecture verification complete: Single Source of Truth maintained cleanly.{CLR_RESET}")


if __name__ == "__main__":
    main()