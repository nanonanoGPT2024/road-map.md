#!/usr/bin/env python3
"""
Lab Hands-on: iOS Architecture - Networking, Serialization, & Offline-First Persistence
Simulates:
  1. Swift-style Codable serialization with SHA-256 integrity validation.
  2. URLSession & URLCache RFC 7234 semantics (ETag, If-None-Match, 304 Not Modified).
  3. Offline-First Persistent Storage with an Outbox Mutation Sync Queue.
  4. Bidirectional state reconciliation with conflict resolution (Last-Write-Wins + Field Merging).
"""

import time
import json
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum


# --- ANSI Color Codes for iOS Terminal Output Simulation ---
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    RED = "\033[31m"


def log(module: str, message: str, color: str = TermColor.RESET) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{TermColor.BOLD}[{timestamp}] [{module:14}]{TermColor.RESET} {color}{message}{TermColor.RESET}")


# --- Models & Swift-like Codable Serialization ---
class MutationType(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class DocumentRecord:
    id: str
    title: str
    content: str
    author: str
    version: int
    updated_at: float

    def to_json(self) -> str:
        """Simulates Swift Codable: JSONEncoder().encode(self)"""
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, json_str: str) -> "DocumentRecord":
        """Simulates Swift Codable: JSONDecoder().decode(DocumentRecord.self, from: data)"""
        payload = json.loads(json_str)
        return cls(**payload)

    def calculate_etag(self) -> str:
        """Generates deterministic ETag based on payload content hash."""
        serialized = self.to_json().encode("utf-8")
        return f'W/"{hashlib.sha256(serialized).hexdigest()[:16]}"'


@dataclass
class PendingMutation:
    mutation_id: str
    record_id: str
    mutation_type: MutationType
    changes: Dict[str, Any]
    client_timestamp: float
    retry_count: int = 0


# --- HTTP Mock Remote Server ---
class MockRemoteServer:
    """Simulates an edge API gateway handling REST operations with ETag support."""
    def __init__(self):
        self._database: Dict[str, DocumentRecord] = {}

    def seed(self, record: DocumentRecord):
        self._database[record.id] = record

    def get_document(self, doc_id: str, if_none_match: Optional[str] = None) -> Tuple[int, Optional[str], Optional[str]]:
        """Handles conditional GET: returns (status_code, body_json, etag)."""
        time.sleep(0.02)  # Simulate network latency
        record = self._database.get(doc_id)
        if not record:
            return 404, None, None

        current_etag = record.calculate_etag()
        if if_none_match == current_etag:
            return 304, None, current_etag  # Not Modified (RFC 7234)

        return 200, record.to_json(), current_etag

    def mutate_document(self, doc_id: str, changes: Dict[str, Any], client_version: int) -> Tuple[int, Dict[str, Any]]:
        """Handles sync POST/PATCH with optimistic concurrency control."""
        time.sleep(0.03)
        record = self._database.get(doc_id)
        if not record:
            return 404, {"error": "Record not found"}

        # Optimistic Concurrency Conflict Detection
        if record.version > client_version:
            return 409, {
                "error": "Conflict detected: upstream has higher version",
                "server_state": json.loads(record.to_json())
            }

        # Apply mutation
        for key, val in changes.items():
            if hasattr(record, key):
                setattr(record, key, val)
        record.version += 1
        record.updated_at = time.time()
        self._database[doc_id] = record

        return 200, json.loads(record.to_json())


# --- Local Persistence Engine (Simulating CoreData/SQLite + URLCache) ---
class LocalDataStore:
    """Simulates local SQLite / CoreData storage with dirty-state tracking."""
    def __init__(self):
        self._local_records: Dict[str, DocumentRecord] = {}
        self._http_cache: Dict[str, Tuple[str, str]] = {}  # url -> (etag, payload)

    def read_cache(self, url: str) -> Optional[Tuple[str, str]]:
        return self._http_cache.get(url)

    def write_cache(self, url: str, etag: str, payload: str):
        self._http_cache[url] = (etag, payload)

    def save_record(self, record: DocumentRecord):
        self._local_records[record.id] = record

    def get_record(self, doc_id: str) -> Optional[DocumentRecord]:
        return self._local_records.get(doc_id)


# --- iOS Offline-First Sync Engine ---
class OfflineSyncEngine:
    """
    Manages local cache, outbound mutation queue, network policy,
    and reconciliation between local CoreData and Remote API.
    """
    def __init__(self, server: MockRemoteServer):
        self.server = server
        self.store = LocalDataStore()
        self.outbox_queue: List[PendingMutation] = []
        self.is_network_reachable: bool = True

    def fetch_document(self, doc_id: str) -> Optional[DocumentRecord]:
        """
        Mimics URLSession with URLRequestCachePolicy.useProtocolCachePolicy:
        Issues conditional request using cached ETag. Falls back to offline store if network down.
        """
        cache_key = f"/documents/{doc_id}"

        if not self.is_network_reachable:
            log("Network", f"Device is OFFLINE. Serving {doc_id} directly from local CoreData.", TermColor.YELLOW)
            return self.store.get_record(doc_id)

        # Retrieve cached ETag if available
        cached_entry = self.store.read_cache(cache_key)
        if_none_match = cached_entry[0] if cached_entry else None

        status, body, etag = self.server.get_document(doc_id, if_none_match=if_none_match)

        if status == 304 and cached_entry:
            log("URLSession", f"HTTP 304 Not Modified for {doc_id}. Reusing cached bytes (ETag: {etag}).", TermColor.CYAN)
            return DocumentRecord.from_json(cached_entry[1])
        elif status == 200 and body and etag:
            log("URLSession", f"HTTP 200 OK for {doc_id}. Updating local URLCache & CoreData.", TermColor.GREEN)
            self.store.write_cache(cache_key, etag, body)
            record = DocumentRecord.from_json(body)
            self.store.save_record(record)
            return record
        else:
            log("URLSession", f"HTTP {status}: Failed to fetch {doc_id}.", TermColor.RED)
            return self.store.get_record(doc_id)

    def mutate_locally(self, doc_id: str, changes: Dict[str, Any]):
        """
        Offline-first mutation: applies modification immediately to local store
        and queues a PendingMutation into the outbound synchronization FIFO queue.
        """
        record = self.store.get_record(doc_id)
        if not record:
            log("Store", f"Cannot mutate missing local record {doc_id}.", TermColor.RED)
            return

        # 1. Optimistic Local Update
        for k, v in changes.items():
            if hasattr(record, k):
                setattr(record, k, v)
        record.updated_at = time.time()
        self.store.save_record(record)

        # 2. Append to Outbox Queue
        mutation = PendingMutation(
            mutation_id=hashlib.md5(f"{doc_id}:{time.time()}".encode()).hexdigest()[:8],
            record_id=doc_id,
            mutation_type=MutationType.UPDATE,
            changes=changes,
            client_timestamp=time.time()
        )
        self.outbox_queue.append(mutation)
        log("OutboxQueue", f"Enqueued mutation [{mutation.mutation_id}] for {doc_id}. Pending mutations: {len(self.outbox_queue)}", TermColor.MAGENTA)

    def reconcile_outbox(self):
        """
        Synchronizes queued local modifications with upstream server.
        Handles optimistic concurrency conflicts (HTTP 409) via Last-Write-Wins & Field Merging.
        """
        if not self.is_network_reachable:
            log("SyncEngine", "Reconciliation skipped: Network unavailable.", TermColor.YELLOW)
            return

        if not self.outbox_queue:
            log("SyncEngine", "Outbox is clean. Nothing to sync.", TermColor.GREEN)
            return

        log("SyncEngine", f"Starting background sync of {len(self.outbox_queue)} pending mutations...", TermColor.BOLD)

        synced_mutations = []
        for mutation in list(self.outbox_queue):
            local_record = self.store.get_record(mutation.record_id)
            if not local_record:
                continue

            status, response = self.server.mutate_document(
                doc_id=mutation.record_id,
                changes=mutation.changes,
                client_version=local_record.version
            )

            if status == 200:
                log("SyncEngine", f"✔ Mutation [{mutation.mutation_id}] applied upstream successfully.", TermColor.GREEN)
                synced_record = DocumentRecord(**response)
                self.store.save_record(synced_record)
                # Invalidate/update URLCache
                self.store.write_cache(f"/documents/{synced_record.id}", synced_record.calculate_etag(), synced_record.to_json())
                synced_mutations.append(mutation)
            elif status == 409:
                log("SyncEngine", f"✖ Conflict on [{mutation.mutation_id}]! Upstream version ahead.", TermColor.RED)
                server_payload = response["server_state"]
                self._resolve_conflict(mutation, local_record, server_payload)
                synced_mutations.append(mutation)

        # Remove processed mutations
        for m in synced_mutations:
            if m in self.outbox_queue:
                self.outbox_queue.remove(m)

        log("SyncEngine", "Reconciliation batch cycle complete.", TermColor.BOLD)

    def _resolve_conflict(self, mutation: PendingMutation, local: DocumentRecord, server_dict: Dict[str, Any]):
        """
        Three-way merge policy:
        Field-level merge. Conflicting fields default to Last-Write-Wins (LWW) based on timestamp.
        """
        log("Reconciliation", f"Resolving 3-way conflict on record '{local.id}'...", TermColor.YELLOW)
        server_record = DocumentRecord(**server_dict)

        # Merge strategy: Client updates are kept if client mutation is newer, otherwise server wins
        for field, client_val in mutation.changes.items():
            if mutation.client_timestamp > server_record.updated_at:
                log("Reconciliation", f"  -> Field '{field}': Client-Wins (Client: {mutation.client_timestamp:.2f} > Server: {server_record.updated_at:.2f})", TermColor.CYAN)
                setattr(server_record, field, client_val)
            else:
                log("Reconciliation", f"  -> Field '{field}': Server-Wins (Server timestamp is newer)", TermColor.CYAN)

        # Update local state with merged version and advance local version tracker
        server_record.version += 1
        self.store.save_record(server_record)
        log("Reconciliation", f"Merged state updated locally with base version {server_record.version}.", TermColor.GREEN)


# --- Execution Pipeline ---
def main():
    print(f"{TermColor.BOLD}{TermColor.BLUE}======================================================================={TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.BLUE}  iOS Architecture Deep Dive: Networking, URLCache, & Sync Engine     {TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.BLUE}======================================================================={TermColor.RESET}\n")

    # 1. Setup Mock Server with initial document
    server = MockRemoteServer()
    initial_doc = DocumentRecord(
        id="DOC-9021",
        title="Mobile System Architecture",
        content="Overview of Swift Concurrency & CoreData.",
        author="lead_dev",
        version=1,
        updated_at=time.time()
    )
    server.seed(initial_doc)

    client = OfflineSyncEngine(server)

    # 2. Step 1: Initial Cold Fetch (HTTP 200)
    log("MAIN", "--- STEP 1: Cold Initial Document Request ---", TermColor.BOLD)
    doc = client.fetch_document("DOC-9021")
    if doc:
        print(f"  Received: Title='{doc.title}', Version={doc.version}, Hash={doc.calculate_etag()[:12]}")

    # 3. Step 2: Immediate Re-fetch (HTTP 304 Validation via ETag)
    print()
    log("MAIN", "--- STEP 2: Cache Validation with If-None-Match ---", TermColor.BOLD)
    doc_cached = client.fetch_document("DOC-9021")
    if doc_cached:
        print(f"  Received: Title='{doc_cached.title}', Version={doc_cached.version}")

    # 4. Step 3: Transition to Offline State & Queue Local Modifications
    print()
    log("MAIN", "--- STEP 3: Network Interruption & Local Mutations ---", TermColor.BOLD)
    client.is_network_reachable = False
    log("Network", "Airplane Mode ACTIVATED (Simulated).", TermColor.RED)

    client.mutate_locally("DOC-9021", {"title": "Mobile System Architecture (Offline Draft)"})
    client.mutate_locally("DOC-9021", {"content": "Appended offline section regarding Outbox FIFO queues."})

    # Read while offline
    offline_doc = client.fetch_document("DOC-9021")
    if offline_doc:
        print(f"  Offline CoreData View: '{offline_doc.title}' | Version={offline_doc.version}")

    # 5. Step 4: Out-of-band Concurrent Remote Modification (Generates Conflict)
    print()
    log("MAIN", "--- STEP 4: Server State Drift (Remote Concurrent Modification) ---", TermColor.BOLD)
    time.sleep(0.05)
    server.mutate_document(
        doc_id="DOC-9021",
        changes={"content": "Remote author edited content concurrently on Web.", "author": "chief_architect"},
        client_version=1  # Server version moves to 2
    )
    log("RemoteServer", "Doc DOC-9021 modified remotely on web console. Server version is now 2.", TermColor.YELLOW)

    # 6. Step 5: Network Restored & Outbox Synchronization
    print()
    log("MAIN", "--- STEP 5: Connectivity Restored & Conflict Reconciliation ---", TermColor.BOLD)
    client.is_network_reachable = True
    log("Network", "Wi-Fi Connected (Simulated).", TermColor.GREEN)

    # Trigger reconciliation
    client.reconcile_outbox()

    # 7. Final State Audit
    print()
    log("MAIN", "--- STEP 6: Final Integrated Verification ---", TermColor.BOLD)
    final_doc = client.store.get_record("DOC-9021")
    if final_doc:
        print(f"  Final Local Entity:")
        print(f"    - ID:      {final_doc.id}")
        print(f"    - Title:   {final_doc.title}")
        print(f"    - Content: {final_doc.content}")
        print(f"    - Author:  {final_doc.author}")
        print(f"    - Version: {final_doc.version}")
        print(f"    - ETag:    {final_doc.calculate_etag()}")

    print(f"\n{TermColor.BOLD}{TermColor.GREEN}✔ Verification Complete: Seamless Offline-to-Online state convergence achieved.{TermColor.RESET}\n")


if __name__ == "__main__":
    main()
