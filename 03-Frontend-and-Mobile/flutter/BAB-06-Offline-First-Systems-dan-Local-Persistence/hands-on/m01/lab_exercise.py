#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Offline-First Architecture & Local Persistence Simulation
Modul: BAB-06 Offline-First Systems dan Local Persistence (Flutter Concepts in Python)
"""

import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class AnsiColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


class SyncStatus(Enum):
    SYNCED = "SYNCED"
    PENDING = "PENDING"
    SYNCING = "SYNCING"
    FAILED = "FAILED"


class ConflictResolutionStrategy(Enum):
    CLIENT_WINS = "CLIENT_WINS"
    SERVER_WINS = "SERVER_WINS"
    LAST_WRITE_WINS = "LAST_WRITE_WINS"


@dataclass
class DocumentRecord:
    id: str
    title: str
    content: str
    version: int
    updated_at: float
    sync_status: SyncStatus = SyncStatus.SYNCED

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "version": self.version,
            "updated_at": self.updated_at,
            "sync_status": self.sync_status.value,
        }


@dataclass
class OutboxMutation:
    mutation_id: str
    entity_id: str
    operation: str  # INSERT, UPDATE, DELETE
    payload: dict
    version: int
    created_at: float
    retry_count: int = 0
    status: SyncStatus = SyncStatus.PENDING


class RemoteServerMock:
    """Simulates a remote backend API and database."""

    def __init__(self):
        self.remote_db: Dict[str, DocumentRecord] = {}

    def fetch_all(self) -> Dict[str, DocumentRecord]:
        return self.remote_db.copy()

    def process_mutation(
        self,
        mutation: OutboxMutation,
        strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LAST_WRITE_WINS,
    ) -> tuple[bool, Optional[DocumentRecord], str]:
        entity_id = mutation.entity_id
        incoming_data = mutation.payload

        if mutation.operation in ("INSERT", "UPDATE"):
            if entity_id in self.remote_db:
                server_record = self.remote_db[entity_id]
                # Conflict detected if server has newer or different version
                if server_record.version > mutation.version:
                    if strategy == ConflictResolutionStrategy.SERVER_WINS:
                        return (
                            False,
                            server_record,
                            f"Conflict: Rejected. Server version ({server_record.version}) wins.",
                        )
                    elif strategy == ConflictResolutionStrategy.CLIENT_WINS:
                        new_version = server_record.version + 1
                        resolved_record = DocumentRecord(
                            id=entity_id,
                            title=incoming_data["title"],
                            content=incoming_data["content"],
                            version=new_version,
                            updated_at=time.time(),
                            sync_status=SyncStatus.SYNCED,
                        )
                        self.remote_db[entity_id] = resolved_record
                        return True, resolved_record, "Conflict: Resolved via Client-Wins."
                    else:  # LAST_WRITE_WINS
                        if incoming_data.get("updated_at", 0) >= server_record.updated_at:
                            new_version = server_record.version + 1
                            resolved_record = DocumentRecord(
                                id=entity_id,
                                title=incoming_data["title"],
                                content=incoming_data["content"],
                                version=new_version,
                                updated_at=incoming_data.get("updated_at", time.time()),
                                sync_status=SyncStatus.SYNCED,
                            )
                            self.remote_db[entity_id] = resolved_record
                            return True, resolved_record, "Conflict: Resolved via Last-Write-Wins (Client was newer)."
                        else:
                            return (
                                False,
                                server_record,
                                f"Conflict: Rejected via Last-Write-Wins (Server timestamp was newer).",
                            )

            # Normal insert or linear update
            curr_ver = self.remote_db[entity_id].version if entity_id in self.remote_db else 0
            persisted = DocumentRecord(
                id=entity_id,
                title=incoming_data["title"],
                content=incoming_data["content"],
                version=curr_ver + 1,
                updated_at=incoming_data.get("updated_at", time.time()),
                sync_status=SyncStatus.SYNCED,
            )
            self.remote_db[entity_id] = persisted
            return True, persisted, "Successfully synced."

        elif mutation.operation == "DELETE":
            if entity_id in self.remote_db:
                del self.remote_db[entity_id]
            return True, None, "Successfully deleted on server."

        return False, None, "Unsupported operation."


class OfflineFirstRepository:
    """Simulates Flutter local persistence (Hive/Isar/Sqflite) and Outbox sync engine."""

    def __init__(self, remote_server: RemoteServerMock):
        self.local_cache: Dict[str, DocumentRecord] = {}
        self.outbox_queue: List[OutboxMutation] = []
        self.remote_server = remote_server
        self.is_online: bool = True
        self.resolution_strategy = ConflictResolutionStrategy.LAST_WRITE_WINS

    def save_item(self, title: str, content: str, item_id: Optional[str] = None) -> DocumentRecord:
        now = time.time()
        if item_id and item_id in self.local_cache:
            existing = self.local_cache[item_id]
            updated_record = DocumentRecord(
                id=item_id,
                title=title,
                content=content,
                version=existing.version,
                updated_at=now,
                sync_status=SyncStatus.PENDING,
            )
            operation = "UPDATE"
        else:
            new_id = item_id or str(uuid.uuid4())[:8]
            updated_record = DocumentRecord(
                id=new_id,
                title=title,
                content=content,
                version=0,
                updated_at=now,
                sync_status=SyncStatus.PENDING,
            )
            operation = "INSERT"

        # 1. Optimistic Local Persistence (Write immediately to local disk/cache)
        self.local_cache[updated_record.id] = updated_record

        # 2. Append to Outbox Queue
        mutation = OutboxMutation(
            mutation_id=str(uuid.uuid4())[:8],
            entity_id=updated_record.id,
            operation=operation,
            payload={
                "title": updated_record.title,
                "content": updated_record.content,
                "updated_at": updated_record.updated_at,
            },
            version=updated_record.version,
            created_at=now,
        )
        self.outbox_queue.append(mutation)
        return updated_record

    def synchronize(self) -> List[str]:
        logs: List[str] = []
        if not self.is_online:
            logs.append(f"{AnsiColor.YELLOW}Sync skipped: Device is offline.{AnsiColor.RESET}")
            return logs

        logs.append(f"{AnsiColor.CYAN}Sync engine active: Processing Outbox Queue...{AnsiColor.RESET}")
        remaining_queue: List[OutboxMutation] = []

        for mutation in self.outbox_queue:
            mutation.status = SyncStatus.SYNCING
            success, server_record, message = self.remote_server.process_mutation(
                mutation, self.resolution_strategy
            )

            if success:
                logs.append(
                    f"  {AnsiColor.GREEN}✓ Mutation [{mutation.mutation_id}] on entity [{mutation.entity_id}] -> {message}{AnsiColor.RESET}"
                )
                if server_record and server_record.id in self.local_cache:
                    # Update local cache with canonical server record
                    self.local_cache[server_record.id] = server_record
            else:
                mutation.retry_count += 1
                if server_record:
                    # Server rejected with newer state -> reconcile local cache
                    logs.append(
                        f"  {AnsiColor.RED}✗ Mutation [{mutation.mutation_id}] rejected -> {message}. Reconciling with server snapshot...{AnsiColor.RESET}"
                    )
                    self.local_cache[server_record.id] = server_record
                else:
                    mutation.status = SyncStatus.FAILED
                    remaining_queue.append(mutation)
                    logs.append(
                        f"  {AnsiColor.RED}✗ Mutation [{mutation.mutation_id}] failed. Retries: {mutation.retry_count}{AnsiColor.RESET}"
                    )

        self.outbox_queue = remaining_queue

        # 3. Pull delta updates from server to local cache (Two-way sync)
        server_state = self.remote_server.fetch_all()
        for s_id, s_record in server_state.items():
            if s_id not in self.local_cache:
                self.local_cache[s_id] = s_record
                logs.append(
                    f"  {AnsiColor.BLUE}↓ Pulled downstream entity [{s_id}] (v{s_record.version}) from remote server.{AnsiColor.RESET}"
                )

        return logs


def display_dashboard(repo: OfflineFirstRepository, server: RemoteServerMock):
    status_color = AnsiColor.GREEN if repo.is_online else AnsiColor.RED
    status_text = "ONLINE" if repo.is_online else "OFFLINE"

    print("\n" + "=" * 70)
    print(
        f"{AnsiColor.BOLD}{AnsiColor.CYAN}--- FLUTTER OFFLINE-FIRST ARCHITECTURE SIMULATOR ---{AnsiColor.RESET}"
    )
    print(
        f"Connectivity: {status_color}{status_text}{AnsiColor.RESET} | Conflict Policy: {AnsiColor.MAGENTA}{repo.resolution_strategy.value}{AnsiColor.RESET}"
    )
    print("=" * 70)

    print(f"\n{AnsiColor.BOLD}[1] Local Storage (Isar/Hive Cache) [{len(repo.local_cache)} records]:{AnsiColor.RESET}")
    if not repo.local_cache:
        print(f"  {AnsiColor.GRAY}(Local storage is empty){AnsiColor.RESET}")
    for item in repo.local_cache.values():
        stat_color = AnsiColor.GREEN if item.sync_status == SyncStatus.SYNCED else AnsiColor.YELLOW
        print(
            f"  • ID: {AnsiColor.BOLD}{item.id}{AnsiColor.RESET} | Ver: {item.version} | "
            f"Title: {item.title:<18} | Status: {stat_color}{item.sync_status.value}{AnsiColor.RESET}"
        )

    print(f"\n{AnsiColor.BOLD}[2] Outbox Queue (Mutations waiting to sync) [{len(repo.outbox_queue)} items]:{AnsiColor.RESET}")
    if not repo.outbox_queue:
        print(f"  {AnsiColor.GRAY}(Outbox queue is empty - All clean){AnsiColor.RESET}")
    for mut in repo.outbox_queue:
        print(
            f"  • Queue ID: {mut.mutation_id} | Op: {mut.operation} | Target ID: {mut.entity_id} | "
            f"Retries: {mut.retry_count} | Status: {mut.status.value}"
        )

    print(f"\n{AnsiColor.BOLD}[3] Remote Cloud Database [{len(server.remote_db)} records]:{AnsiColor.RESET}")
    if not server.remote_db:
        print(f"  {AnsiColor.GRAY}(Remote database is empty){AnsiColor.RESET}")
    for r_item in server.remote_db.values():
        print(
            f"  • ID: {AnsiColor.BOLD}{r_item.id}{AnsiColor.RESET} | Ver: {r_item.version} | "
            f"Title: {r_item.title:<18} | Content: {r_item.content[:25]}"
        )
    print("=" * 70)


def run_automated_suite(repo: OfflineFirstRepository, server: RemoteServerMock):
    print(f"\n{AnsiColor.BOLD}{AnsiColor.CYAN}>>> RUNNING AUTOMATED OFFLINE-FIRST VERIFICATION TEST SUITE <<<{AnsiColor.RESET}\n")

    # Step 1: Online creation
    print(f"{AnsiColor.YELLOW}Test 1: Create note while ONLINE and synchronize...{AnsiColor.RESET}")
    repo.is_online = True
    note1 = repo.save_item("Catatan Kuliah", "Algoritma Pemrograman")
    assert note1.id in repo.local_cache, "Failed: Note not in local cache"
    assert len(repo.outbox_queue) == 1, "Failed: Outbox queue must hold 1 mutation"
    logs = repo.synchronize()
    for log in logs:
        print(log)
    assert len(repo.outbox_queue) == 0, "Failed: Outbox should be drained after sync"
    assert note1.id in server.remote_db, "Failed: Note not present on remote server"
    print(f"{AnsiColor.GREEN}✓ Test 1 Passed!{AnsiColor.RESET}\n")

    # Step 2: Offline mutation
    print(f"{AnsiColor.YELLOW}Test 2: Go OFFLINE, mutate note, verify outbox persistence...{AnsiColor.RESET}")
    repo.is_online = False
    repo.save_item("Catatan Kuliah (Revisi Offline)", "Ditambahkan Bab Binary Tree", item_id=note1.id)
    assert repo.local_cache[note1.id].title == "Catatan Kuliah (Revisi Offline)"
    assert repo.local_cache[note1.id].sync_status == SyncStatus.PENDING
    assert len(repo.outbox_queue) == 1
    logs = repo.synchronize()
    for log in logs:
        print(log)
    assert len(repo.outbox_queue) == 1, "Failed: Outbox must remain intact when offline"
    print(f"{AnsiColor.GREEN}✓ Test 2 Passed!{AnsiColor.RESET}\n")

    # Step 3: Concurrent Server Edit (Conflict scenario)
    print(f"{AnsiColor.YELLOW}Test 3: Simulate concurrent cloud update while client is offline...{AnsiColor.RESET}")
    server_curr = server.remote_db[note1.id]
    server.remote_db[note1.id] = DocumentRecord(
        id=note1.id,
        title="Catatan Kuliah (Server Edit)",
        content="Disunting oleh kolaborator web",
        version=server_curr.version + 1,
        updated_at=time.time() + 10,
        sync_status=SyncStatus.SYNCED,
    )

    # Step 4: Reconnect and Reconcile
    print(f"{AnsiColor.YELLOW}Test 4: Reconnect ONLINE and run conflict resolution...{AnsiColor.RESET}")
    repo.is_online = True
    repo.resolution_strategy = ConflictResolutionStrategy.SERVER_WINS
    logs = repo.synchronize()
    for log in logs:
        print(log)
    assert repo.local_cache[note1.id].title == "Catatan Kuliah (Server Edit)"
    assert repo.local_cache[note1.id].version >= 2
    print(f"{AnsiColor.GREEN}✓ Test 4 Passed! Local store reconciled with canonical server state.{AnsiColor.RESET}\n")

    print(f"{AnsiColor.BOLD}{AnsiColor.GREEN}>>> ALL VERIFICATION SUITE CHECKS PASSED SUCCESSFULLY! <<<{AnsiColor.RESET}")


def interactive_cli():
    server = RemoteServerMock()
    repo = OfflineFirstRepository(server)

    # Pre-populate initial dataset
    initial = repo.save_item("Daftar Belanja", "Kopi, Susu, Gandum")
    repo.synchronize()

    while True:
        display_dashboard(repo, server)
        print(f"\n{AnsiColor.BOLD}Command Menu:{AnsiColor.RESET}")
        print("  1. Simpan/Ubah Data Lokal (Optimistic UI Write)")
        print("  2. Toggle Status Jaringan (Online <-> Offline)")
        print("  3. Picu Sinkronisasi Manual (Flush Outbox & Pull Remote Delta)")
        print("  4. Buat Konflik di Server (Simulasi Server Drift)")
        print("  5. Ganti Strategi Resolusi Konflik")
        print("  6. Jalankan Automated Verification Test Suite")
        print("  0. Keluar")

        try:
            choice = input(f"\n{AnsiColor.BOLD}Pilih opsi [0-6]: {AnsiColor.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "0":
            print("Keluar dari simulasi.")
            break
        elif choice == "1":
            print(f"\n{AnsiColor.CYAN}--- Tulis Dokumen ke Penyimpanan Lokal ---{AnsiColor.RESET}")
            existing_id = input("Masukkan ID dokumen jika ingin update (atau Enter untuk dokumen baru): ").strip()
            item_id = existing_id if existing_id else None
            title = input("Judul Dokumen : ").strip() or "Untitled Document"
            content = input("Isi Konten    : ").strip() or "No content"
            saved = repo.save_item(title=title, content=content, item_id=item_id)
            print(f"{AnsiColor.GREEN}✓ Disimpan di lokal (ID: {saved.id}). Masuk antrian outbox.{AnsiColor.RESET}")
        elif choice == "2":
            repo.is_online = not repo.is_online
            state_str = "ONLINE" if repo.is_online else "OFFLINE"
            print(f"{AnsiColor.MAGENTA}Status jaringan sekarang: {state_str}{AnsiColor.RESET}")
        elif choice == "3":
            logs = repo.synchronize()
            print("\nLog Sinkronisasi:")
            for log in logs:
                print(log)
        elif choice == "4":
            if not server.remote_db:
                print(f"{AnsiColor.RED}Server masih kosong. Buat data dan lakukan sinkronisasi terlebih dahulu.{AnsiColor.RESET}")
            else:
                target_id = list(server.remote_db.keys())[0]
                rec = server.remote_db[target_id]
                rec.title += " [Cloud Diverged]"
                rec.version += 2
                rec.updated_at = time.time() + 50
                print(f"{AnsiColor.YELLOW}Server entity [{target_id}] dimodifikasi sepihak di cloud (Version: {rec.version}).{AnsiColor.RESET}")
        elif choice == "5":
            print("\nPilih Strategi Resolusi Konflik:")
            print("  1. LAST_WRITE_WINS")
            print("  2. SERVER_WINS")
            print("  3. CLIENT_WINS")
            sub_choice = input("Pilihan [1-3]: ").strip()
            if sub_choice == "1":
                repo.resolution_strategy = ConflictResolutionStrategy.LAST_WRITE_WINS
            elif sub_choice == "2":
                repo.resolution_strategy = ConflictResolutionStrategy.SERVER_WINS
            elif sub_choice == "3":
                repo.resolution_strategy = ConflictResolutionStrategy.CLIENT_WINS
            print(f"{AnsiColor.GREEN}Strategi aktif: {repo.resolution_strategy.value}{AnsiColor.RESET}")
        elif choice == "6":
            run_automated_suite(repo, server)
            input(f"\n{AnsiColor.GRAY}Tekan Enter untuk kembali ke dashboard...{AnsiColor.RESET}")
        else:
            print(f"{AnsiColor.RED}Pilihan tidak valid.{AnsiColor.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_server = RemoteServerMock()
        test_repo = OfflineFirstRepository(test_server)
        run_automated_suite(test_repo, test_server)
    else:
        interactive_cli()
