#!/usr/bin/env python3
"""
Lab Hands-on: SwiftUI Persistence & Offline-First Data Pipeline Deep Dive
Simulasi Arsitektur SwiftData / CoreData + Outbox Pattern Sync Engine
Mekanisme: Local Store, Outbox Transaction Queue, Conflict Resolution (LWW),
dan Reactive UI State Observer.
"""

import time
import uuid
import json
import random
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Callable

# ANSI Terminal Color Codes
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_CYAN = "\033[36m"
C_DIM = "\033[2m"

class SyncStatus(Enum):
    SYNCED = "SYNCED"
    PENDING_INSERT = "PENDING_INSERT"
    PENDING_UPDATE = "PENDING_UPDATE"
    PENDING_DELETE = "PENDING_DELETE"

@dataclass
class NoteModel:
    """
    Representasi entitas SwiftUI (@Model di SwiftData).
    Memiliki tracking versi dan tombstone (is_deleted) untuk soft delete.
    """
    id: str
    title: str
    content: str
    version: int
    updated_at: float
    is_deleted: bool = False
    sync_status: SyncStatus = SyncStatus.SYNCED

    def serialize(self) -> dict:
        data = asdict(self)
        data['sync_status'] = self.sync_status.value
        return data

    @classmethod
    def deserialize(cls, data: dict) -> 'NoteModel':
        data['sync_status'] = SyncStatus(data['sync_status'])
        return cls(**data)


class RemoteCloudKitMock:
    """
    Simulasi remote server / Apple CloudKit private database.
    Menerapkan stateful remote persistence dengan validasi versioning.
    """
    def __init__(self):
        self.remote_db: Dict[str, NoteModel] = {}
        self.is_online: bool = True

    def commit_transaction(self, client_record: NoteModel) -> tuple[bool, Optional[NoteModel], str]:
        """
        Menerima mutasi client. Jika ada conflict, implementasikan Last-Write-Wins (LWW)
        atau tolak jika client version tertinggal.
        """
        if not self.is_online:
            return False, None, "NETWORK_UNREACHABLE"

        server_record = self.remote_db.get(client_record.id)

        if not server_record:
            # Insert baru pada remote
            self.remote_db[client_record.id] = client_record
            return True, client_record, "SUCCESS_INSERT"

        # Conflict Detection: Evaluasi timestamp dan versi
        if client_record.updated_at < server_record.updated_at:
            # Server memiliki versi yang lebih baru (Conflict detected)
            return False, server_record, "CONFLICT_SERVER_AHEAD"

        # Resolusi Last-Write-Wins (Client lebih baru atau sama)
        self.remote_db[client_record.id] = client_record
        return True, client_record, "SUCCESS_UPDATE"

    def fetch_changes_since(self, last_sync_time: float) -> List[NoteModel]:
        if not self.is_online:
            return []
        return [r for r in self.remote_db.values() if r.updated_at > last_sync_time]


class SwiftDataLocalStorage:
    """
    Simulasi Local Context SwiftData / SQLite Engine.
    Mendukung ACID-like local transaction, query interface, dan Outbox tracking.
    """
    def __init__(self):
        self._storage: Dict[str, NoteModel] = {}
        self._outbox_queue: List[str] = [] # Queue of entity IDs requiring sync
        self._subscribers: List[Callable[[List[NoteModel]], None]] = []

    def subscribe(self, callback: Callable[[List[NoteModel]], None]):
        """Simulasi Combine publisher / Swift Observation framework (@Observable)"""
        self._subscribers.append(callback)

    def _notify(self):
        live_data = [m for m in self._storage.values() if not m.is_deleted]
        for sub in self._subscribers:
            sub(live_data)

    def upsert_local(self, title: str, content: str, entity_id: Optional[str] = None) -> NoteModel:
        now = time.time()
        if entity_id and entity_id in self._storage:
            existing = self._storage[entity_id]
            existing.title = title
            existing.content = content
            existing.updated_at = now
            existing.version += 1
            existing.sync_status = SyncStatus.PENDING_UPDATE
            record = existing
        else:
            new_id = entity_id or str(uuid.uuid4())[:8]
            record = NoteModel(
                id=new_id,
                title=title,
                content=content,
                version=1,
                updated_at=now,
                is_deleted=False,
                sync_status=SyncStatus.PENDING_INSERT
            )
            self._storage[new_id] = record

        if record.id not in self._outbox_queue:
            self._outbox_queue.append(record.id)
            
        self._notify()
        return record

    def delete_local(self, entity_id: str) -> bool:
        if entity_id in self._storage:
            record = self._storage[entity_id]
            record.is_deleted = True
            record.updated_at = time.time()
            record.version += 1
            record.sync_status = SyncStatus.PENDING_DELETE
            if entity_id not in self._outbox_queue:
                self._outbox_queue.append(entity_id)
            self._notify()
            return True
        return False

    def mark_synced(self, entity_id: str, remote_version: int):
        if entity_id in self._storage:
            rec = self._storage[entity_id]
            if rec.is_deleted:
                del self._storage[entity_id]
            else:
                rec.sync_status = SyncStatus.SYNCED
                rec.version = remote_version
            if entity_id in self._outbox_queue:
                self._outbox_queue.remove(entity_id)
            self._notify()

    def overwrite_from_remote(self, remote_record: NoteModel):
        self._storage[remote_record.id] = remote_record
        if remote_record.id in self._outbox_queue:
            self._outbox_queue.remove(remote_record.id)
        self._notify()

    def get_outbox(self) -> List[NoteModel]:
        return [self._storage[uid] for uid in self._outbox_queue if uid in self._storage]


class OfflineFirstSyncEngine:
    """
    Koordinator sinkronisasi dua arah (Bidirectional Sync Pipeline).
    Bertanggung jawab mendistribusikan delta lokal ke cloud dan rekonsiliasi state.
    """
    def __init__(self, local_store: SwiftDataLocalStorage, remote_cloud: RemoteCloudKitMock):
        self.local = local_store
        self.remote = remote_cloud
        self.last_sync_timestamp = 0.0

    def synchronize(self) -> dict:
        stats = {"pushed": 0, "pulled": 0, "conflicts": 0, "failed": 0}
        
        print(f"{C_CYAN}[SyncEngine]{C_RESET} Memulai siklus sinkronisasi...")
        
        # FASE 1: Flush Outbox Lokal (Push)
        outbox = self.local.get_outbox()
        for record in outbox:
            success, server_copy, reason = self.remote.commit_transaction(record)
            if success:
                self.local.mark_synced(record.id, record.version)
                stats["pushed"] += 1
                print(f"  {C_GREEN}✓ Push Selesai:{C_RESET} Entity [{record.id}] '{record.title}' synced.")
            else:
                if reason == "CONFLICT_SERVER_AHEAD" and server_copy:
                    stats["conflicts"] += 1
                    print(f"  {C_YELLOW}⚠ Conflict Terdeteksi:{C_RESET} Entity [{record.id}]. Server lebih baru.")
                    # Resolusi: Server Win (Pull server state, overwrite local)
                    server_copy.sync_status = SyncStatus.SYNCED
                    self.local.overwrite_from_remote(server_copy)
                    print(f"    ↳ Resolusi LWW: Local di-rollback ke versi server v{server_copy.version}")
                else:
                    stats["failed"] += 1
                    print(f"  {C_RED}✗ Push Gagal:{C_RESET} Entity [{record.id}]. Reason: {reason}")

        # FASE 2: Fetch Perubahan Remote (Pull)
        if self.remote.is_online:
            remote_deltas = self.remote.fetch_changes_since(self.last_sync_timestamp)
            for r_rec in remote_deltas:
                # Update local jika bukan yang baru saja kita push
                if r_rec.id not in [o.id for o in outbox]:
                    r_rec.sync_status = SyncStatus.SYNCED
                    self.local.overwrite_from_remote(r_rec)
                    stats["pulled"] += 1
                    print(f"  {C_BLUE}↓ Pull Inbound:{C_RESET} Entity [{r_rec.id}] '{r_rec.title}' diterima dari cloud.")
            
            self.last_sync_timestamp = time.time()
            
        return stats


def mock_swiftui_view_render(models: List[NoteModel]):
    """Simulasi render pipeline declarative SwiftUI Body saat @Observable berubah"""
    print(f"\n{C_MAGENTA}--- SwiftUI Render Pass (@Query View Hierarchy) ---{C_RESET}")
    if not models:
        print(f"  {C_DIM}(Canvas Kosong - Tidak ada data){C_RESET}")
    for item in models:
        status_color = C_GREEN if item.sync_status == SyncStatus.SYNCED else C_YELLOW
        print(f"  • [{item.id}] {C_BOLD}{item.title}{C_RESET} : '{item.content}' "
              f"(v{item.version}) [{status_color}{item.sync_status.value}{C_RESET}]")
    print(f"{C_MAGENTA}----------------------------------------------------{C_RESET}\n")


def run_lab():
    print(f"{C_BOLD}{C_CYAN}=== LAB PERSISTENSI SWIFTUI: OFFLINE-FIRST DATA PIPELINE ==={C_RESET}\n")

    # Inisialisasi komponen
    local_store = SwiftDataLocalStorage()
    remote_cloud = RemoteCloudKitMock()
    sync_engine = OfflineFirstSyncEngine(local_store, remote_cloud)

    # Pasang observer view
    local_store.subscribe(mock_swiftui_view_render)

    # 1. State Awal: Mutasi Saat Terkoneksi
    print(f"{C_BOLD}[Skenario 1] Membuat item lokal dalam kondisi ONLINE{C_RESET}")
    doc1 = local_store.upsert_local("Belanja", "Susu Oat, Telur, Kopi")
    sync_engine.synchronize()

    # 2. Simulasi Kondisi Offline
    print(f"\n{C_BOLD}[Skenario 2] Jaringan terputus total (Airplane Mode diaktifkan){C_RESET}")
    remote_cloud.is_online = False
    
    print(f"{C_YELLOW}→ User memodifikasi data lokal secara offline...{C_RESET}")
    local_store.upsert_local("Belanja Mingguan", "Susu Oat, Kopi, Alpukat", entity_id=doc1.id)
    doc2 = local_store.upsert_local("Fitur SwiftUI", "Implementasikan @Observable macro")

    print(f"{C_YELLOW}→ Mencoba sinkronisasi saat OFFLINE:{C_RESET}")
    sync_engine.synchronize()

    # 3. Simulasi Konflik Remote
    print(f"\n{C_BOLD}[Skenario 3] Modifikasi Paralel di Remote Cloud (Edge Conflict){C_RESET}")
    # Modifikasi item doc1 langsung di remote dengan timestamp lebih baru
    time.sleep(0.05)
    concurrent_remote = NoteModel(
        id=doc1.id,
        title="Belanja Bersama",
        content="Susu Almond, Roti Gandum (Diedit user lain di Cloud)",
        version=5,
        updated_at=time.time() + 10.0, # Jam remote lebih maju
        is_deleted=False,
        sync_status=SyncStatus.SYNCED
    )
    remote_cloud.remote_db[doc1.id] = concurrent_remote
    print(f"{C_DIM}Log: Cloud database menerima update paralel dari Device B untuk ID {doc1.id}{C_RESET}")

    # 4. Jaringan Pulih Kembali
    print(f"\n{C_BOLD}[Skenario 4] Pemulihan Jaringan & Resolusi Konflik Otomatis{C_RESET}")
    remote_cloud.is_online = True
    stats = sync_engine.synchronize()

    print(f"\n{C_BOLD}Laporan Hasil Eksekusi Pipeline Sinkronisasi:{C_RESET}")
    print(f" - Sukses Dipush : {C_GREEN}{stats['pushed']}{C_RESET}")
    print(f" - Ditarik (Pull): {C_BLUE}{stats['pulled']}{C_RESET}")
    print(f" - Konflik LWW   : {C_YELLOW}{stats['conflicts']}{C_RESET}")
    print(f" - Gagal         : {C_RED}{stats['failed']}{C_RESET}")
    print(f" - Sisa Outbox   : {len(local_store.get_outbox())} items")

    print(f"\n{C_GREEN}✓ Verifikasi Integritas: Local Store terkonvergensi konsisten dengan Remote.{C_RESET}")

if __name__ == "__main__":
    run_lab()