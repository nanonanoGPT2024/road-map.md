#!/usr/bin/env python3
"""
Lab Exercise M01: SwiftUI Offline-First Data Pipeline Simulation
Topik: Persistensi SwiftData / CoreData, Outbox Mutation Queue, Conflict Resolution, & Network Synchronization.

Simulasi teknis independen yang memodelkan arsitektur Offline-First pada aplikasi SwiftUI modern:
1. Local ModelContext & SQLite Cache Store (SwiftData Equivalent)
2. Outbox Mutation Queue Pattern (Pending Offline Operations)
3. Remote API Mock & Two-Way Sync Engine
4. Conflict Resolution Strategy (Server-Wins vs Client-Wins / Timestamp Merge)
"""

import sys
import time
import json
import uuid
import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# ANSI Color formatting
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"

@dataclass
class ExpenseItem:
    id: str
    title: str
    amount: float
    category: str
    updated_at: float
    version: int = 1
    is_deleted: bool = False

@dataclass
class MutationRecord:
    mutation_id: str
    item_id: str
    action: str  # 'CREATE', 'UPDATE', 'DELETE'
    payload: dict
    timestamp: float

class SwiftDataSimulator:
    """Simulasi in-memory ModelContext SwiftData / CoreData"""
    def __init__(self):
        self.storage: Dict[str, ExpenseItem] = {}
        self.mutation_queue: List[MutationRecord] = []
        self.undo_stack: List[str] = []

    def insert(self, title: str, amount: float, category: str) -> ExpenseItem:
        item_id = str(uuid.uuid4())[:8]
        now = time.time()
        item = ExpenseItem(
            id=item_id,
            title=title,
            amount=amount,
            category=category,
            updated_at=now,
            version=1
        )
        self.storage[item_id] = item
        # Enqueue Outbox mutation
        mutation = MutationRecord(
            mutation_id=str(uuid.uuid4())[:6],
            item_id=item_id,
            action="CREATE",
            payload=asdict(item),
            timestamp=now
        )
        self.mutation_queue.append(mutation)
        return item

    def update(self, item_id: str, new_title: Optional[str] = None, new_amount: Optional[float] = None) -> Optional[ExpenseItem]:
        item = self.storage.get(item_id)
        if not item or item.is_deleted:
            return None
        if new_title is not None:
            item.title = new_title
        if new_amount is not None:
            item.amount = new_amount
        item.updated_at = time.time()
        item.version += 1

        mutation = MutationRecord(
            mutation_id=str(uuid.uuid4())[:6],
            item_id=item_id,
            action="UPDATE",
            payload=asdict(item),
            timestamp=item.updated_at
        )
        self.mutation_queue.append(mutation)
        return item

    def delete(self, item_id: str) -> bool:
        item = self.storage.get(item_id)
        if not item or item.is_deleted:
            return False
        item.is_deleted = True
        item.updated_at = time.time()
        item.version += 1

        mutation = MutationRecord(
            mutation_id=str(uuid.uuid4())[:6],
            item_id=item_id,
            action="DELETE",
            payload={"id": item_id},
            timestamp=item.updated_at
        )
        self.mutation_queue.append(mutation)
        return True

    def fetch_active(self) -> List[ExpenseItem]:
        return [item for item in self.storage.values() if not item.is_deleted]

class RemoteServerMock:
    """Simulasi Remote Cloud Backend (CloudKit / REST / GraphQL)"""
    def __init__(self):
        self.records: Dict[str, dict] = {}

    def apply_mutation(self, mutation: MutationRecord, strategy: str = "LAST_WRITE_WINS") -> dict:
        item_id = mutation.item_id
        server_item = self.records.get(item_id)

        if mutation.action == "CREATE":
            if server_item:
                return {"status": "CONFLICT", "reason": "Item already exists on remote"}
            self.records[item_id] = mutation.payload
            return {"status": "SUCCESS", "version": mutation.payload["version"]}

        elif mutation.action == "UPDATE":
            if not server_item:
                # Upstream missing, create it
                self.records[item_id] = mutation.payload
                return {"status": "SUCCESS", "version": mutation.payload["version"]}
            
            # Check for conflict
            if server_item.get("version", 1) >= mutation.payload["version"]:
                if strategy == "CLIENT_WINS":
                    self.records[item_id] = mutation.payload
                    return {"status": "RESOLVED_CLIENT", "version": mutation.payload["version"]}
                else: # SERVER_WINS / LWW by timestamp
                    if server_item.get("updated_at", 0) > mutation.timestamp:
                        return {"status": "REJECTED_SERVER_NEWER", "remote_data": server_item}
                    else:
                        self.records[item_id] = mutation.payload
                        return {"status": "RESOLVED_LWW", "version": mutation.payload["version"]}
            else:
                self.records[item_id] = mutation.payload
                return {"status": "SUCCESS", "version": mutation.payload["version"]}

        elif mutation.action == "DELETE":
            if item_id in self.records:
                del self.records[item_id]
            return {"status": "SUCCESS"}

        return {"status": "UNKNOWN_ACTION"}

class OfflineFirstPipeline:
    def __init__(self):
        self.local = SwiftDataSimulator()
        self.remote = RemoteServerMock()
        self.is_online = False
        self.conflict_resolution_strategy = "LAST_WRITE_WINS"

    def toggle_network(self):
        self.is_online = not self.is_online
        status_text = f"{Style.GREEN}ONLINE (Wi-Fi/5G Connected){Style.RESET}" if self.is_online else f"{Style.RED}OFFLINE (Airplane Mode){Style.RESET}"
        print(f"\n{Style.BOLD}[Network Monitor]{Style.RESET} Status switched to: {status_text}")

    def sync(self):
        print(f"\n{Style.CYAN}{Style.BOLD}--- [Data Pipeline Sync Triggered] ---{Style.RESET}")
        if not self.is_online:
            print(f"{Style.YELLOW}[Pipeline Warmer] Network is OFFLINE. Sync aborted. Mutations buffered in Outbox: {len(self.local.mutation_queue)}{Style.RESET}")
            return

        if not self.local.mutation_queue:
            print(f"{Style.GREEN}[Sync Engine] Local cache is cleanly in sync with Remote. Zero pending mutations.{Style.RESET}")
            return

        print(f"{Style.CYAN}[Sync Engine] Flushing {len(self.local.mutation_queue)} queued mutations to Remote...{Style.RESET}")
        processed_queue: List[MutationRecord] = []

        for mutation in self.local.mutation_queue:
            res = self.remote.apply_mutation(mutation, self.conflict_resolution_strategy)
            status = res.get("status")
            if status in ["SUCCESS", "RESOLVED_CLIENT", "RESOLVED_LWW"]:
                print(f"  {Style.GREEN}✓ Push mutation {mutation.mutation_id} ({mutation.action}) -> Remote ACK [{status}]{Style.RESET}")
                processed_queue.append(mutation)
            elif status == "REJECTED_SERVER_NEWER":
                remote_data = res.get("remote_data", {})
                print(f"  {Style.MAGENTA}⚡ Conflict on {mutation.item_id}: Remote has newer timestamp/version!{Style.RESET}")
                print(f"    Overwriting local ModelContext with remote authoritative state...")
                # Reconcile local ModelContext
                local_item = self.local.storage.get(mutation.item_id)
                if local_item:
                    local_item.title = remote_data.get("title", local_item.title)
                    local_item.amount = remote_data.get("amount", local_item.amount)
                    local_item.version = remote_data.get("version", local_item.version)
                    local_item.updated_at = remote_data.get("updated_at", local_item.updated_at)
                processed_queue.append(mutation)
            else:
                print(f"  {Style.RED}✗ Mutation {mutation.mutation_id} failed: {res}{Style.RESET}")

        # Remove successfully processed mutations
        for m in processed_queue:
            self.local.mutation_queue.remove(m)

        print(f"{Style.GREEN}{Style.BOLD}Sync phase complete. Remaining queue depth: {len(self.local.mutation_queue)}{Style.RESET}")

def render_dashboard(pipeline: OfflineFirstPipeline):
    print(f"\n{Style.BOLD}==================================================================={Style.RESET}")
    net_badge = f"{Style.BG_GREEN} ONLINE {Style.RESET}" if pipeline.is_online else f"{Style.RED}{Style.BOLD}[OFFLINE]{Style.RESET}"
    print(f"{Style.BOLD}SWIFTUI OFFLINE-FIRST PERSISTENCE SIMULATOR{Style.RESET} | Network: {net_badge}")
    print(f"Outbox Mutation Queue Size: {Style.YELLOW}{len(pipeline.local.mutation_queue)}{Style.RESET} | Conflict Policy: {Style.CYAN}{pipeline.conflict_resolution_strategy}{Style.RESET}")
    print(f"{Style.BOLD}-------------------------------------------------------------------{Style.RESET}")
    
    # Local State
    active_items = pipeline.local.fetch_active()
    print(f"{Style.BOLD}Local SwiftData Store ({len(active_items)} active items):{Style.RESET}")
    if not active_items:
        print("  (Empty local ModelContext)")
    else:
        for it in active_items:
            t_str = datetime.datetime.fromtimestamp(it.updated_at).strftime('%H:%M:%S')
            print(f"  [{it.id}] {it.title:<18} | ${it.amount:>7.2f} | Cat: {it.category:<10} | v{it.version} | @{t_str}")

    # Remote Backend State
    print(f"\n{Style.BOLD}Remote CloudKit/REST Store ({len(pipeline.remote.records)} records):{Style.RESET}")
    if not pipeline.remote.records:
        print("  (Empty remote database)")
    else:
        for r_id, r in pipeline.remote.records.items():
            t_str = datetime.datetime.fromtimestamp(r['updated_at']).strftime('%H:%M:%S')
            print(f"  [{r_id}] {r['title']:<18} | ${r['amount']:>7.2f} | v{r.get('version', 1)} | @{t_str}")
    print(f"{Style.BOLD}==================================================================={Style.RESET}")

def run_interactive_simulation():
    pipeline = OfflineFirstPipeline()
    
    # Pre-populate sample offline state
    print(f"{Style.CYAN}Menginisialisasi pipeline SwiftUI Offline-First...{Style.RESET}")
    it1 = pipeline.local.insert("Server Subscription", 45.0, "Infrastructure")
    it2 = pipeline.local.insert("MacBook Keyboard", 129.99, "Hardware")

    while True:
        render_dashboard(pipeline)
        print(f"\n{Style.BOLD}Pilihan Menu Praktikum:{Style.RESET}")
        print("1. Tambah Data Baru (Simulasi UI Form @Environment(\\ModelContext))")
        print("2. Ubah Data Lokal (Update Pending Mutation)")
        print("3. Hapus Data Lokal (Tombstone Deletion)")
        print("4. Toggle Status Jaringan (Online / Offline)")
        print("5. Jalankan Background Synchronization Pipeline")
        print("6. Simulasikan Remote Conflict (Perubahan mendahului dari server)")
        print("7. Ganti Strategi Resolusi Konflik (LWW / Client-Wins)")
        print("0. Keluar dari Lab")

        try:
            choice = input(f"\n{Style.CYAN}Pilih opsi [0-7]: {Style.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            title = input("Nama pengeluaran/item: ").strip() or "Untitled Item"
            try:
                amount_str = input("Nominal/Harga ($): ").strip()
                amount = float(amount_str) if amount_str else 10.0
            except ValueError:
                amount = 10.0
            cat = input("Kategori (Work/Personal/Food): ").strip() or "General"
            item = pipeline.local.insert(title, amount, cat)
            print(f"{Style.GREEN}✓ Disimpan ke SwiftData ModelContext! ID: {item.id} (Outbox enqueued){Style.RESET}")

        elif choice == "2":
            items = pipeline.local.fetch_active()
            if not items:
                print(f"{Style.RED}Tidak ada item lokal untuk diubah.{Style.RESET}")
                continue
            item_id = input(f"Masukkan ID item ({', '.join([i.id for i in items])}): ").strip()
            new_title = input("Nama baru (kosongkan jika tidak ubah): ").strip()
            new_amt_str = input("Nominal baru (kosongkan jika tidak ubah): ").strip()
            new_amt = float(new_amt_str) if new_amt_str else None
            updated = pipeline.local.update(item_id, new_title or None, new_amt)
            if updated:
                print(f"{Style.GREEN}✓ Item {item_id} diperbarui lokal ke v{updated.version}!{Style.RESET}")
            else:
                print(f"{Style.RED}Item tidak ditemukan!{Style.RESET}")

        elif choice == "3":
            items = pipeline.local.fetch_active()
            if not items:
                print(f"{Style.RED}Tidak ada item lokal untuk dihapus.{Style.RESET}")
                continue
            item_id = input(f"Masukkan ID item yang ingin dihapus: ").strip()
            if pipeline.local.delete(item_id):
                print(f"{Style.YELLOW}✓ Item {item_id} ditandai dihapus (Tombstoned). Mutation DELETE antre di Outbox.{Style.RESET}")
            else:
                print(f"{Style.RED}Item tidak ditemukan!{Style.RESET}")

        elif choice == "4":
            pipeline.toggle_network()

        elif choice == "5":
            pipeline.sync()

        elif choice == "6":
            # Simulate upstream server mutation ahead of local
            items = pipeline.local.fetch_active()
            if not items:
                print(f"{Style.RED}Silakan tambahkan data lokal terlebih dahulu.{Style.RESET}")
                continue
            target = items[0]
            # Create higher version on remote directly
            pipeline.remote.records[target.id] = {
                "id": target.id,
                "title": f"[Remote Modified] {target.title}",
                "amount": target.amount + 50.0,
                "category": target.category,
                "version": target.version + 2,
                "updated_at": time.time() + 10.0,
                "is_deleted": False
            }
            print(f"{Style.MAGENTA}⚡ Server backend diubah secara eksternal (v{target.version + 2}) dengan timestamp lebih baru!{Style.RESET}")
            print(f"Jalankan opsi 5 (Sync) untuk melihat bagaimana pipeline menangani conflict resolution.")

        elif choice == "7":
            if pipeline.conflict_resolution_strategy == "LAST_WRITE_WINS":
                pipeline.conflict_resolution_strategy = "CLIENT_WINS"
            else:
                pipeline.conflict_resolution_strategy = "LAST_WRITE_WINS"
            print(f"{Style.CYAN}Strategi resolusi konflik diubah menjadi: {pipeline.conflict_resolution_strategy}{Style.RESET}")

        elif choice == "0":
            print(f"{Style.GREEN}Praktikum Lab M01 Selesai. Terima kasih!{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Masukkan angka 0-7.{Style.RESET}")

if __name__ == "__main__":
    run_interactive_simulation()
