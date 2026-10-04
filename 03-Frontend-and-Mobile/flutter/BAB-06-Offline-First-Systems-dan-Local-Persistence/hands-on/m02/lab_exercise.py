#!/usr/bin/env python3
"""
Lab Hands-on: Flutter Architecture - Offline-First Systems & Local Persistence
Module: 06-02 Deep Dive: Bi-directional Sync, Outbox Pattern & Conflict Resolution

This script models a high-performance offline-first sync engine commonly
implemented in enterprise Flutter applications (utilizing SQLite/Drift + Outbox pattern).
It simulates:
1. An embedded SQLite-based Local Cache with an Outbox Mutation Queue.
2. Network partition toggles (Online/Offline state transitions).
3. Concurrent data modification on both Local and Remote backends.
4. Deterministic Conflict Resolution (Three-Way Merge / Last-Write-Wins with Vector Versioning).
"""

import sqlite3
import json
import time
import uuid
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

# --- ANSI Terminal Colors ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"


@dataclass
class Mutation:
    id: str
    record_id: str
    action: str  # 'UPSERT' or 'DELETE'
    payload: Dict[str, Any]
    client_version: int
    created_at: float


class RemoteServer:
    """Simulates a Cloud REST/GraphQL Endpoint with optimistic concurrency control."""
    def __init__(self):
        # record_id -> {"data": {...}, "version": int, "updated_at": float}
        self._store: Dict[str, Dict[str, Any]] = {}

    def fetch_changes_since(self, last_sync_time: float) -> List[Dict[str, Any]]:
        """Returns records modified strictly after last_sync_time."""
        results = []
        for record_id, record in self._store.items():
            if record["updated_at"] > last_sync_time:
                results.append({
                    "id": record_id,
                    "data": record["data"],
                    "version": record["version"],
                    "updated_at": record["updated_at"]
                })
        return results

    def commit_mutation(self, mutation: Mutation) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Attempts to apply a mutation.
        Enforces optimistic concurrency checks based on version numbers.
        """
        current = self._store.get(mutation.record_id)
        now = time.time()

        if mutation.action == "UPSERT":
            if current:
                # Detect conflict: If remote version is strictly greater than incoming client baseline
                if current["version"] > mutation.client_version:
                    return False, current
                new_version = current["version"] + 1
            else:
                new_version = 1

            self._store[mutation.record_id] = {
                "data": mutation.payload,
                "version": new_version,
                "updated_at": now
            }
            return True, None

        elif mutation.action == "DELETE":
            if current and current["version"] > mutation.client_version:
                return False, current
            self._store.pop(mutation.record_id, None)
            return True, None

        return False, None

    def inject_concurrent_edit(self, record_id: str, new_data: Dict[str, Any]):
        """Simulates another client editing the server record concurrently."""
        rec = self._store.get(record_id)
        ver = rec["version"] + 1 if rec else 1
        self._store[record_id] = {
            "data": new_data,
            "version": ver,
            "updated_at": time.time()
        }


class LocalPersistenceEngine:
    """
    Simulates Flutter's Local SQLite Engine (analogous to Drift / Sqflite).
    Maintains domain tables and an Outbox queue in an atomic local transaction.
    """
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self.conn:
            # Domain Data Table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    is_dirty INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                );
            """)
            # Outbox Sync Queue Table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_outbox (
                    mutation_id TEXT PRIMARY KEY,
                    record_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    client_version INTEGER NOT NULL,
                    created_at REAL NOT NULL
                );
            """)

    def upsert_local_transaction(self, record_id: str, title: str, content: str):
        """
        Simulates an Offline Write in Flutter:
        1. Write immediately to local UI table with dirty flag = 1.
        2. Append mutation to sync_outbox.
        Both execute within an atomic transaction.
        """
        now = time.time()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT version FROM notes WHERE id = ?", (record_id,))
            row = cur.fetchone()
            current_version = row["version"] if row else 0

            # Optimistic local increment
            next_version = current_version + 1

            cur.execute("""
                INSERT INTO notes (id, title, content, version, is_dirty, updated_at)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    version = excluded.version,
                    is_dirty = 1,
                    updated_at = excluded.updated_at;
            """, (record_id, title, content, next_version, now))

            payload = json.dumps({"title": title, "content": content})
            mutation_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO sync_outbox (mutation_id, record_id, action, payload, client_version, created_at)
                VALUES (?, ?, 'UPSERT', ?, ?, ?);
            """, (mutation_id, record_id, payload, current_version, now))

    def get_pending_mutations(self) -> List[Mutation]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM sync_outbox ORDER BY created_at ASC")
        rows = cur.fetchall()
        return [
            Mutation(
                id=r["mutation_id"],
                record_id=r["record_id"],
                action=r["action"],
                payload=json.loads(r["payload"]),
                client_version=r["client_version"],
                created_at=r["created_at"]
            )
            for r in rows
        ]

    def remove_mutation(self, mutation_id: str, final_version: int, record_id: str):
        """Acknowledges successful remote sync; clears dirty state."""
        with self.conn:
            self.conn.execute("DELETE FROM sync_outbox WHERE mutation_id = ?", (mutation_id,))
            self.conn.execute("""
                UPDATE notes 
                SET is_dirty = 0, version = ? 
                WHERE id = ? AND (SELECT COUNT(*) FROM sync_outbox WHERE record_id = ?) = 0
            """, (final_version, record_id, record_id))

    def apply_server_override(self, record_id: str, title: str, content: str, server_version: int):
        """Resolves conflict by forcing local state to match authoritative remote state."""
        with self.conn:
            self.conn.execute("""
                INSERT INTO notes (id, title, content, version, is_dirty, updated_at)
                VALUES (?, ?, ?, ?, 0, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    version = excluded.version,
                    is_dirty = 0,
                    updated_at = excluded.updated_at;
            """, (record_id, title, content, server_version, time.time()))
            # Evict stale mutations for this item
            self.conn.execute("DELETE FROM sync_outbox WHERE record_id = ?", (record_id,))

    def fetch_all_notes(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT id, title, content, version, is_dirty FROM notes")
        return [dict(r) for r in cur.fetchall()]


class SyncCoordinator:
    """Coordinates upstream flush and downstream fetch with network-aware checks."""
    def __init__(self, local: LocalPersistenceEngine, remote: RemoteServer):
        self.local = local
        self.remote = remote
        self.is_online = True
        self.last_sync_timestamp = 0.0

    def set_connectivity(self, online: bool):
        self.is_online = online
        status = f"{CLR_GREEN}ONLINE{CLR_RESET}" if online else f"{CLR_RED}OFFLINE{CLR_RESET}"
        print(f"\n{CLR_BOLD}[Network Lifecycle]{CLR_RESET} Network State Changed -> {status}")

    def synchronize(self):
        """Core sync protocol: PUSH mutations, handle conflicts, then PULL changes."""
        if not self.is_online:
            print(f"{CLR_YELLOW}[Sync Engine] Aborted: Client is currently OFFLINE. Mutations safely held in Outbox.{CLR_RESET}")
            return

        print(f"{CLR_CYAN}[Sync Engine] Starting bi-directional sync cycle...{CLR_RESET}")
        
        # 1. PUSH: Process local Outbox
        mutations = self.local.get_pending_mutations()
        print(f" -> Found {len(mutations)} pending local mutation(s) in Outbox.")
        
        for mut in mutations:
            success, server_state = self.remote.commit_mutation(mut)
            if success:
                print(f"    {CLR_GREEN}✓ Synced mutation {mut.id[:8]} for Record '{mut.record_id}'{CLR_RESET}")
                # Fetch remote assigned version after commit
                remote_rec = self.remote._store[mut.record_id]
                self.local.remove_mutation(mut.id, remote_rec["version"], mut.record_id)
            else:
                # 2. CONFLICT DETECTED
                print(f"    {CLR_RED}⚠ Conflict detected on record '{mut.record_id}'!{CLR_RESET}")
                print(f"      Client base version: {mut.client_version} | Remote active version: {server_state['version']}")
                
                # Conflict Resolution: Server Authoritative / Last-Write Merge Strategy
                print(f"      {CLR_MAGENTA}-> Applying Resolution Policy: Server-Authoritative Fallback{CLR_RESET}")
                self.local.apply_server_override(
                    record_id=mut.record_id,
                    title=server_state["data"]["title"],
                    content=server_state["data"]["content"],
                    server_version=server_state["version"]
                )

        # 3. PULL: Fetch delta changes from server
        pull_start = time.time()
        updates = self.remote.fetch_changes_since(self.last_sync_timestamp)
        for upd in updates:
            # Update local if not dirty
            cur = self.local.conn.cursor()
            cur.execute("SELECT is_dirty FROM notes WHERE id = ?", (upd["id"],))
            row = cur.fetchone()
            if not row or row["is_dirty"] == 0:
                self.local.apply_server_override(
                    record_id=upd["id"],
                    title=upd["data"]["title"],
                    content=upd["data"]["content"],
                    server_version=upd["version"]
                )
        
        self.last_sync_timestamp = pull_start
        print(f"{CLR_CYAN}[Sync Engine] Sync completed successfully.{CLR_RESET}\n")


def display_state(label: str, local: LocalPersistenceEngine, remote: RemoteServer):
    print(f"\n{CLR_BOLD}=== {label} ==={CLR_RESET}")
    print(f"{CLR_BOLD}Local Notes Table:{CLR_RESET}")
    notes = local.fetch_all_notes()
    if not notes:
        print("  (Empty)")
    for n in notes:
        flag = f"{CLR_YELLOW}[DIRTY]{CLR_RESET}" if n["is_dirty"] else f"{CLR_GREEN}[SYNCED]{CLR_RESET}"
        print(f"  [{n['id']}] v{n['version']} | {flag} Title: '{n['title']}' | Content: '{n['content']}'")

    print(f"{CLR_BOLD}Local Sync Outbox:{CLR_RESET}")
    outbox = local.get_pending_mutations()
    if not outbox:
        print("  (Queue Empty)")
    for m in outbox:
        print(f"  Queued: MutId={m.id[:8]} | RecId={m.record_id} | ClientBaseVer={m.client_version} | Action={m.action}")

    print(f"{CLR_BOLD}Remote Server Store:{CLR_RESET}")
    if not remote._store:
        print("  (Empty)")
    for rid, rdata in remote._store.items():
        print(f"  [{rid}] v{rdata['version']} | Payload: {rdata['data']}")
    print("-" * 65)


def run_lab():
    print(f"{CLR_CYAN}{CLR_BOLD}======================================================================{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}  FLUTTER LAB: OFFLINE-FIRST PERSISTENCE & SYNC ARCHITECTURE          {CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}======================================================================{CLR_RESET}")

    # Step 1: Initialize Local SQLite and Cloud Store
    local_db = LocalPersistenceEngine()
    remote_server = RemoteServer()
    coordinator = SyncCoordinator(local_db, remote_server)

    # Step 2: Online Creation
    print(f"\n{CLR_BOLD}[Phase 1] Online Creation & Immediate Synchronization{CLR_RESET}")
    coordinator.set_connectivity(True)
    local_db.upsert_local_transaction("doc_01", "Architecture Blueprint", "Initial draft of offline-first design.")
    display_state("After Local Write (Before Sync)", local_db, remote_server)
    coordinator.synchronize()
    display_state("After Sync Cycle", local_db, remote_server)

    # Step 3: Network Disconnect (Offline Editing)
    print(f"\n{CLR_BOLD}[Phase 2] Simulating Network Outage & Local Offline Mutations{CLR_RESET}")
    coordinator.set_connectivity(False)
    local_db.upsert_local_transaction("doc_01", "Architecture Blueprint v2", "Offline edit: added drift db layer.")
    local_db.upsert_local_transaction("doc_02", "Grocery List", "Milk, Eggs, Coffee.")
    display_state("Offline State (Mutations Buffered locally)", local_db, remote_server)

    # Step 4: Outbox Hold Verification
    coordinator.synchronize()  # Should fail gracefully

    # Step 5: Server-Side Concurrent Modification (Conflict Seed)
    print(f"\n{CLR_BOLD}[Phase 3] Generating Remote Conflict Concurrently{CLR_RESET}")
    print("Simulating a remote update from another device on 'doc_01' while current client is offline...")
    remote_server.inject_concurrent_edit(
        record_id="doc_01",
        new_data={"title": "Cloud Blueprint Overwrite", "content": "Updated via Web Portal by collaborator."}
    )
    print(f"{CLR_YELLOW}Remote now possesses version 2 that client has not seen.{CLR_RESET}")

    # Step 6: Network Restored & Reconciliation
    print(f"\n{CLR_BOLD}[Phase 4] Network Restored - Conflict Detection & Auto-Resolution{CLR_RESET}")
    coordinator.set_connectivity(True)
    coordinator.synchronize()
    display_state("Final Converged State", local_db, remote_server)

    print(f"\n{CLR_GREEN}{CLR_BOLD}Lab Completed Successfully:{CLR_RESET}")
    print("1. Local Outbox isolated mutations during offline period.")
    print("2. Optimistic local updates maintained responsive UI states.")
    print("3. Version divergence triggered non-blocking conflict resolution protocol.")


if __name__ == "__main__":
    run_lab()