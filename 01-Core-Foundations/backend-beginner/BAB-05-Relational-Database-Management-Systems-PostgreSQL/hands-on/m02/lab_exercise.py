#!/usr/bin/env python3
"""
Lab: Deep Dive Relational Database Internals (PostgreSQL MVCC & VACUUM Simulator)
Bab: 05 - Relational Database Management Systems (PostgreSQL) - Modul 02

Tujuan Pembelajaran:
1. Memahami arsitektur Multi-Version Concurrency Control (MVCC) PostgreSQL.
2. Mensimulasikan struktur Heap Tuple dengan metadata xmin dan xmax.
3. Mengimplementasikan aturan visibilitas snapshot (HeapTupleSatisfiesMVCC).
4. Mensimulasikan fenomena bloat (dead tuples) akibat operasi UPDATE/DELETE.
5. Membangun mekanisme VACUUM worker untuk membersihkan dead tuples secara efisien.
"""

from dataclasses import dataclass
from enum import Enum
import sys
import time
from typing import Any, Dict, List, Optional, Set


# ANSI terminal color codes untuk visualisasi engine
class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    GRAY = "\033[90m"


class TxStatus(Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass
class TupleRecord:
    """
    Representasi dari physical tuple di storage page (heap) PostgreSQL.
    - xmin: ID transaksi yang melakukan INSERT (membuat tuple).
    - xmax: ID transaksi yang melakukan DELETE atau UPDATE (mematikan tuple). 0 jika aktif.
    """
    row_id: int
    data: Dict[str, Any]
    xmin: int
    xmax: int = 0


@dataclass
class Snapshot:
    """
    Representasi Snapshot PostgreSQL:
    - xmin: Transaksi tertua yang masih aktif saat snapshot dibuat.
    - xmax: Transaksi pertama yang belum di-assign (setara dengan latest_tx + 1).
    - active_txs: Set transaksi yang sedang aktif pada saat snapshot diambil.
    """
    xmin: int
    xmax: int
    active_txs: Set[int]


class PostgresStorageEngine:
    """
    Simulasi Storage Engine PostgreSQL dengan dukungan MVCC dan VACUUM.
    """

    def __init__(self):
        self.next_tx_id = 100
        self.tx_status_log: Dict[int, TxStatus] = {}
        self.heap_table: List[TupleRecord] = []
        self.active_tx_pool: Set[int] = set()

    def begin_transaction(self) -> int:
        """Memulai transaksi baru dan mengalokasikan XID unik."""
        tx_id = self.next_tx_id
        self.next_tx_id += 1
        self.tx_status_log[tx_id] = TxStatus.IN_PROGRESS
        self.active_tx_pool.add(tx_id)
        return tx_id

    def commit(self, tx_id: int):
        """Menyelesaikan transaksi secara permanen (Commit Log / pg_xact)."""
        if tx_id in self.active_tx_pool:
            self.active_tx_pool.remove(tx_id)
            self.tx_status_log[tx_id] = TxStatus.COMMITTED

    def abort(self, tx_id: int):
        """Membatalkan transaksi (Rollback)."""
        if tx_id in self.active_tx_pool:
            self.active_tx_pool.remove(tx_id)
            self.tx_status_log[tx_id] = TxStatus.ABORTED

    def get_snapshot(self, current_tx: int) -> Snapshot:
        """Membuat point-in-time isolation snapshot untuk MVCC SELECT."""
        xmin = min(self.active_tx_pool) if self.active_tx_pool else self.next_tx_id
        xmax = self.next_tx_id
        active = set(self.active_tx_pool)
        return Snapshot(xmin=xmin, xmax=xmax, active_txs=active)

    def insert(self, tx_id: int, row_id: int, data: Dict[str, Any]):
        """Menulis heap tuple baru dengan metadata xmin = tx_id."""
        record = TupleRecord(row_id=row_id, data=data, xmin=tx_id, xmax=0)
        self.heap_table.append(record)

    def delete(self, tx_id: int, row_id: int) -> bool:
        """
        Dalam Postgres, DELETE tidak langsung menghapus bytes fisik.
        Tuple lama ditandai dengan xmax = tx_id.
        """
        snapshot = self.get_snapshot(tx_id)
        for record in self.heap_table:
            if record.row_id == row_id and self._is_visible(record, snapshot, tx_id):
                record.xmax = tx_id
                return True
        return False

    def update(self, tx_id: int, row_id: int, new_data: Dict[str, Any]) -> bool:
        """
        Postgres melakukan UPDATE sebagai DELETE + INSERT:
        1. Set xmax pada record lama dengan tx_id sekarang.
        2. Insert versi tuple baru dengan xmin = tx_id sekarang dan xmax = 0.
        """
        if self.delete(tx_id, row_id):
            self.insert(tx_id, row_id, new_data)
            return True
        return False

    def _is_visible(self, record: TupleRecord, snapshot: Snapshot, current_tx: int) -> bool:
        """
        Implementasi Aturan Visibilitas Tuple PostgreSQL (HeapTupleSatisfiesMVCC):
        1. Cek xmin (apakah creator committed dan terlihat oleh snapshot).
        2. Cek xmax (jika ada deleter/updater, apakah deletion-nya sudah visible).
        """
        # Skenario 1: Tuple dibuat oleh transaksi yang sama yang sedang berjalan
        if record.xmin == current_tx:
            # Jika dihapus oleh transaksi sendiri, maka tidak visible
            return record.xmax != current_tx

        # Cek status pembuat tuple (xmin)
        xmin_status = self.tx_status_log.get(record.xmin, TxStatus.ABORTED)
        if xmin_status != TxStatus.COMMITTED:
            return False  # Belum commit atau di-abort

        # Jika xmin dimulai setelah snapshot diambil, atau sedang aktif saat snapshot diambil
        if record.xmin >= snapshot.xmax or record.xmin in snapshot.active_txs:
            return False

        # Skenario 2: Tuple belum pernah dihapus/diupdate (xmax == 0)
        if record.xmax == 0:
            return True

        # Skenario 3: Tuple sedang/sudah di-update atau di-delete
        if record.xmax == current_tx:
            return False  # Dihapus oleh transaksi aktif ini sendiri

        xmax_status = self.tx_status_log.get(record.xmax, TxStatus.ABORTED)
        if xmax_status != TxStatus.COMMITTED:
            return True  # Deleter abort atau masih in-progress, tuple masih valid

        # Deleter sudah commit: Cek apakah deletion terlihat oleh snapshot ini
        if record.xmax >= snapshot.xmax or record.xmax in snapshot.active_txs:
            return True  # Dihapus *setelah* snapshot ini dibuat -> masih terlihat

        return False  # Dihapus *sebelum* snapshot ini dibuat -> tidak terlihat

    def select(self, tx_id: int) -> List[Dict[str, Any]]:
        """Membaca data menggunakan isolation snapshot."""
        snapshot = self.get_snapshot(tx_id)
        results = []
        for record in self.heap_table:
            if self._is_visible(record, snapshot, tx_id):
                results.append(record.data)
        return results

    def vacuum(self) -> Dict[str, int]:
        """
        Simulasi Engine VACUUM PostgreSQL:
        Membersihkan Dead Tuples (tuple yang xmax-nya sudah COMMITTED
        dan lebih lama daripada transaksi terlama yang sedang berjalan).
        """
        oldest_active_tx = min(self.active_tx_pool) if self.active_tx_pool else self.next_tx_id
        surviving_tuples: List[TupleRecord] = []
        dead_count = 0

        for record in self.heap_table:
            is_dead = False
            if record.xmax != 0:
                xmax_status = self.tx_status_log.get(record.xmax, TxStatus.ABORTED)
                # Dead tuple: Dihapus oleh transaksi yang COMMITTED dan lebih tua dari semua active tx
                if xmax_status == TxStatus.COMMITTED and record.xmax < oldest_active_tx:
                    is_dead = True
                # Dead tuple: Dibuat oleh transaksi yang kena ABORT / ROLLBACK
                elif self.tx_status_log.get(record.xmin) == TxStatus.ABORTED:
                    is_dead = True

            if is_dead:
                dead_count += 1
            else:
                surviving_tuples.append(record)

        self.heap_table = surviving_tuples
        return {
            "reclaimed_tuples": dead_count,
            "remaining_tuples": len(self.heap_table),
        }

    def print_heap_state(self, label: str):
        """Mencetak snapshot fisik dari isi heap table."""
        print(f"\n{TerminalColor.BOLD}{TerminalColor.CYAN}--- Physical Heap Storage: {label} ---{TerminalColor.RESET}")
        print(f"{'Index':<6} | {'RowID':<6} | {'xmin':<6} | {'xmax':<6} | {'Data Payload':<25}")
        print("-" * 60)
        for idx, rec in enumerate(self.heap_table):
            xmax_str = str(rec.xmax) if rec.xmax != 0 else "-"
            # Highlight dead tuples
            color = TerminalColor.RESET
            if rec.xmax != 0 and self.tx_status_log.get(rec.xmax) == TxStatus.COMMITTED:
                color = TerminalColor.GRAY
            print(f"{color}{idx:<6} | {rec.row_id:<6} | {rec.xmin:<6} | {xmax_str:<6} | {str(rec.data):<25}{TerminalColor.RESET}")
        print("-" * 60)


def execute_lab_simulation():
    engine = PostgresStorageEngine()

    print(f"{TerminalColor.BOLD}{TerminalColor.MAGENTA}============================================================{TerminalColor.RESET}")
    print(f"{TerminalColor.BOLD}{TerminalColor.MAGENTA}  POSTGRESQL INTERNALS: MVCC & VACUUM SIMULATION WORKBENCH  {TerminalColor.RESET}")
    print(f"{TerminalColor.BOLD}{TerminalColor.MAGENTA}============================================================{TerminalColor.RESET}")

    # Langkah 1: Populasi Data Awal (Transaki Awal Tx 100)
    tx_init = engine.begin_transaction()
    print(f"\n{TerminalColor.GREEN}[Tx {tx_init}] BEGIN & INSERT (2 Akun Bank){TerminalColor.RESET}")
    engine.insert(tx_init, row_id=1, data={"user": "Alice", "balance": 1000})
    engine.insert(tx_init, row_id=2, data={"user": "Bob", "balance": 500})
    engine.commit(tx_init)
    print(f"{TerminalColor.GREEN}[Tx {tx_init}] COMMIT{TerminalColor.RESET}")

    engine.print_heap_state("Setelah Inisialisasi Data")

    # Langkah 2: Simulasi Concurrency (Tx 101 membaca, Tx 102 melakukan transfer)
    tx_reader = engine.begin_transaction()
    print(f"{TerminalColor.BLUE}[Tx {tx_reader}] (Reader) BEGIN - Snapshot Diambil{TerminalColor.RESET}")

    tx_writer = engine.begin_transaction()
    print(f"{TerminalColor.YELLOW}[Tx {tx_writer}] (Writer) BEGIN - Update Alice balance -> 900{TerminalColor.RESET}")
    engine.update(tx_writer, row_id=1, new_data={"user": "Alice", "balance": 900})

    # Reader membaca saat writer belum commit
    reader_view_1 = engine.select(tx_reader)
    print(f"{TerminalColor.BLUE}[Tx {tx_reader}] SELECT hasil saat Tx {tx_writer} in-flight: {reader_view_1}{TerminalColor.RESET}")

    # Writer melakukan commit
    print(f"{TerminalColor.YELLOW}[Tx {tx_writer}] COMMIT{TerminalColor.RESET}")
    engine.commit(tx_writer)

    # Reader membaca lagi setelah writer commit (Repeatable Read snapshot consistency test)
    reader_view_2 = engine.select(tx_reader)
    print(f"{TerminalColor.BLUE}[Tx {tx_reader}] SELECT ulang (Snapshot Isolation): {reader_view_2}{TerminalColor.RESET}")

    # Transaksi baru dimulai setelah Tx 102 commit
    tx_new = engine.begin_transaction()
    new_view = engine.select(tx_new)
    print(f"{TerminalColor.GREEN}[Tx {tx_new}] (New Transaction) SELECT hasil: {new_view}{TerminalColor.RESET}")
    engine.commit(tx_new)

    engine.commit(tx_reader)
    print(f"{TerminalColor.BLUE}[Tx {tx_reader}] COMMIT (Selesai membaca){TerminalColor.RESET}")

    # Langkah 3: Mensimulasikan Bloat Akumulasi Dead Tuples
    print(f"\n{TerminalColor.YELLOW}Simulasi Update Beruntun untuk Memicu Table Bloat...{TerminalColor.RESET}")
    for i in range(3):
        tx_loop = engine.begin_transaction()
        engine.update(tx_loop, row_id=1, new_data={"user": "Alice", "balance": 900 - (i + 1) * 50})
        engine.commit(tx_loop)

    engine.print_heap_state("Kondisi Heap Terkena Table Bloat")

    # Langkah 4: Menjalankan VACUUM Engine
    print(f"\n{TerminalColor.BOLD}{TerminalColor.MAGENTA}[VACUUM WORKER] Menjalankan Garbage Collection Dead Tuples...{TerminalColor.RESET}")
    metrics = engine.vacuum()
    print(f"{TerminalColor.GREEN}VACUUM Selesai: {metrics['reclaimed_tuples']} dead tuples dihapus fisik, {metrics['remaining_tuples']} tuple aktif dipertahankan.{TerminalColor.RESET}")

    engine.print_heap_state("Heap Setelah Pembersihan VACUUM")


if __name__ == "__main__":
    execute_lab_simulation()
