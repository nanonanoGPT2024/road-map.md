#!/usr/bin/env python3
"""
Lab Exercise M01: Android Architecture & Data Layer Offline-First Simulation
Fokus: Room ORM (SQLite Engine), Single Source of Truth (SSOT), dan Sync Queue.
BAB-05: Data Layer, Offline-First Architecture & Room ORM Persistence
"""

import sys
import time
import sqlite3
import dataclasses
from typing import List, Optional, Dict, Any

# ANSI Color Escape Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_BLUE = "\033[94m"
CLR_GRAY = "\033[90m"

def log_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== [ {title.upper()} ] ==={CLR_RESET}")

def log_room(msg: str):
    print(f"  {CLR_MAGENTA}[Room SQLite ORM]{CLR_RESET} {msg}")

def log_remote(msg: str):
    print(f"  {CLR_BLUE}[Remote API/Ktor]{CLR_RESET} {msg}")

def log_repo(msg: str):
    print(f"  {CLR_YELLOW}[Repository SSOT]{CLR_RESET} {msg}")

def log_ui(msg: str):
    print(f"  {CLR_GREEN}[Compose UI State]{CLR_RESET} {msg}")

def log_error(msg: str):
    print(f"  {CLR_RED}[ERROR/OFFLINE]{CLR_RESET} {msg}")

@dataclasses.dataclass
class ArticleEntity:
    """Representasi @Entity(tableName = 'articles') di Android Room"""
    id: int
    title: str
    content: str
    author: str
    is_bookmarked: bool
    sync_status: str  # 'SYNCED', 'PENDING_UPDATE', 'PENDING_INSERT'
    updated_at: float

class ArticleDao:
    """Representasi @Dao interface yang mengeksekusi SQLite Query"""
    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn
        self._init_table()

    def _init_table(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author TEXT NOT NULL,
                    is_bookmarked INTEGER NOT NULL DEFAULT 0,
                    sync_status TEXT NOT NULL DEFAULT 'SYNCED',
                    updated_at REAL NOT NULL
                )
            """)

    def insert_or_replace_all(self, articles: List[ArticleEntity]):
        with self.conn:
            self.conn.executemany("""
                INSERT OR REPLACE INTO articles 
                (id, title, content, author, is_bookmarked, sync_status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                (a.id, a.title, a.content, a.author, 1 if a.is_bookmarked else 0, a.sync_status, a.updated_at)
                for a in articles
            ])

    def get_all(self) -> List[ArticleEntity]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, title, content, author, is_bookmarked, sync_status, updated_at FROM articles ORDER BY id ASC")
        rows = cursor.fetchall()
        return [
            ArticleEntity(
                id=r[0],
                title=r[1],
                content=r[2],
                author=r[3],
                is_bookmarked=bool(r[4]),
                sync_status=r[5],
                updated_at=r[6]
            ) for r in rows
        ]

    def update_bookmark(self, article_id: int, bookmarked: bool, status: str):
        with self.conn:
            self.conn.execute("""
                UPDATE articles 
                SET is_bookmarked = ?, sync_status = ?, updated_at = ?
                WHERE id = ?
            """, (1 if bookmarked else 0, status, time.time(), article_id))

    def get_pending_sync(self) -> List[ArticleEntity]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, title, content, author, is_bookmarked, sync_status, updated_at FROM articles WHERE sync_status != 'SYNCED'")
        rows = cursor.fetchall()
        return [
            ArticleEntity(
                id=r[0],
                title=r[1],
                content=r[2],
                author=r[3],
                is_bookmarked=bool(r[4]),
                sync_status=r[5],
                updated_at=r[6]
            ) for r in rows
        ]

class MockRemoteDataSource:
    """Simulasi Remote REST API Backend"""
    def __init__(self):
        self.is_online = True
        self.remote_articles: Dict[int, Dict[str, Any]] = {
            101: {"title": "Arsitektur Modern Android", "content": "MVI + Clean Architecture", "author": "Google Dev", "bookmarked": False},
            102: {"title": "Room ORM & Migrasi Schema", "content": "AutoMigration vs Manual Migration", "author": "Android Jetpack", "bookmarked": False},
            103: {"title": "Kotlin Coroutines & Flow", "content": "Cold Stream untuk Room InvalidationTracker", "author": "JetBrains", "bookmarked": True}
        }

    def fetch_articles(self) -> List[Dict[str, Any]]:
        if not self.is_online:
            raise ConnectionError("Host unreachable: Handshake failed (OFFLINE)")
        return [{"id": k, **v} for k, v in self.remote_articles.items()]

    def sync_mutation(self, article_id: int, is_bookmarked: bool) -> bool:
        if not self.is_online:
            raise ConnectionError("Gagal mengirim perubahan ke cloud: Device sedang Offline")
        if article_id in self.remote_articles:
            self.remote_articles[article_id]["bookmarked"] = is_bookmarked
            return True
        return False

class OfflineFirstRepository:
    """Implementasi Single Source of Truth (SSOT) via Room DAO"""
    def __init__(self, dao: ArticleDao, remote: MockRemoteDataSource):
        self.dao = dao
        self.remote = remote

    def get_articles_stream(self, force_refresh: bool = False):
        """
        Simulasi Kotlin Flow:
        1. Selalu emit data lokal dari Room lebih dulu (instant UI response).
        2. Jika online/refresh, fetch remote dan simpan ke Room (SSOT update).
        3. Emit ulang data dari Room setelah terupdate.
        """
        log_repo("Membaca data saat ini dari Room Local Storage (Cache First)...")
        cached = self.dao.get_all()
        yield cached

        if force_refresh:
            log_repo("Memulai NetworkBoundResource refresh dari Remote Backend...")
            try:
                log_remote("Mengirim GET /api/v1/articles ...")
                remote_data = self.remote.fetch_articles()
                log_remote(f"Berhasil fetch {len(remote_data)} artikel dari server cloud.")
                
                # Transform DTO -> Room Entity
                entities = [
                    ArticleEntity(
                        id=item["id"],
                        title=item["title"],
                        content=item["content"],
                        author=item["author"],
                        is_bookmarked=item["bookmarked"],
                        sync_status="SYNCED",
                        updated_at=time.time()
                    ) for item in remote_data
                ]
                log_room("Upserting payload jaringan ke tabel SQLite Room...")
                self.dao.insert_or_replace_all(entities)
                
                # Emit update terbaru dari Room
                updated_cache = self.dao.get_all()
                yield updated_cache
            except ConnectionError as e:
                log_error(f"Network error ditangkap: {e}")
                log_repo("Fall-back transparan: Melayani data dari Room Database tanpa crashing UI.")

    def toggle_bookmark(self, article_id: int, target_state: bool):
        """Optimistic UI update: simpan ke Room dulu, catat status sync"""
        log_repo(f"Melakukan Optimistic Local Mutation pada ID={article_id} (Bookmark={target_state})...")
        self.dao.update_bookmark(article_id, target_state, status="PENDING_UPDATE")
        log_room("Room SQLite diperbarui dengan sync_status='PENDING_UPDATE'.")

        # Coba sinkronisasi langsung jika online
        if self.remote.is_online:
            try:
                log_remote(f"Mengirim PATCH /api/v1/articles/{article_id}...")
                success = self.remote.sync_mutation(article_id, target_state)
                if success:
                    self.dao.update_bookmark(article_id, target_state, status="SYNCED")
                    log_room("Status sinkronisasi Room diubah menjadi 'SYNCED'.")
            except ConnectionError:
                log_error("Gagal sync ke server. Perubahan tetap disimpan di SQLite Room sebagai PENDING_UPDATE.")
        else:
            log_error("Perangkat Offline: Perubahan dimasukkan ke antrean lokal Room (Pending WorkManager).")

    def run_sync_worker(self):
        """Simulasi Android WorkManager periodic/one-time sync worker"""
        log_repo("WorkManager memulai background sync worker...")
        pending = self.dao.get_pending_sync()
        if not pending:
            log_repo("Tidak ada perubahan tertunda di Room Database. Status konsisten.")
            return

        log_repo(f"Ditemukan {len(pending)} item dengan status PENDING_SYNC.")
        if not self.remote.is_online:
            log_error("Sinkronisasi WorkManager ditunda: Jaringan masih belum tersedia (NetworkType.CONNECTED belum terpenuhi).")
            return

        for item in pending:
            try:
                log_remote(f"Pushing offline mutation: ID {item.id} -> Bookmark={item.is_bookmarked}")
                self.remote.sync_mutation(item.id, item.is_bookmarked)
                self.dao.update_bookmark(item.id, item.is_bookmarked, status="SYNCED")
                log_room(f"ID {item.id} berhasil tersinkronisasi dan berstatus 'SYNCED'.")
            except ConnectionError as err:
                log_error(f"Gagal menyinkronkan ID {item.id}: {err}")

def print_ui_table(articles: List[ArticleEntity]):
    if not articles:
        log_ui(f"{CLR_GRAY}(Layar Kosong / Cache Belum Ada Data){CLR_RESET}")
        return
    print(f"\n  {CLR_BOLD}{'ID':<6} {'STATUS SYNC':<16} {'BOOKMARK':<10} {'JUDUL ARTIKEL':<32} {'AUTHOR'}{CLR_RESET}")
    print("  " + "-" * 75)
    for a in articles:
        bm_icon = f"{CLR_GREEN}★ YES{CLR_RESET}" if a.is_bookmarked else f"{CLR_GRAY}☆ NO {CLR_RESET}"
        status_color = CLR_GREEN if a.sync_status == "SYNCED" else CLR_YELLOW
        status_str = f"{status_color}{a.sync_status:<16}{CLR_RESET}"
        print(f"  {a.id:<6} {status_str} {bm_icon:<19} {a.title[:30]:<32} {a.author}")
    print()

def run_self_verification(repo: OfflineFirstRepository, remote: MockRemoteDataSource, dao: ArticleDao):
    log_header("Menjalankan Test Suite Verifikasi Mandiri")
    
    # Test 1: Cold start fetch
    remote.is_online = True
    list(repo.get_articles_stream(force_refresh=True))
    cached = dao.get_all()
    assert len(cached) == 3, f"Expected 3 articles, got {len(cached)}"
    print(f"  [{CLR_GREEN}PASS{CLR_RESET}] Cold Start Cache Population: 3 entities inserted.")

    # Test 2: Offline mutation
    remote.is_online = False
    repo.toggle_bookmark(101, True)
    article_101 = next(a for a in dao.get_all() if a.id == 101)
    assert article_101.is_bookmarked is True, "Optimistic update bookmark must be True"
    assert article_101.sync_status == "PENDING_UPDATE", "Status must be PENDING_UPDATE when offline"
    print(f"  [{CLR_GREEN}PASS{CLR_RESET}] Offline Optimistic Update: Room persists mutation with PENDING status.")

    # Test 3: WorkManager reconnect sync
    remote.is_online = True
    repo.run_sync_worker()
    article_101_synced = next(a for a in dao.get_all() if a.id == 101)
    assert article_101_synced.sync_status == "SYNCED", "Status must become SYNCED after worker run"
    assert remote.remote_articles[101]["bookmarked"] is True, "Remote backend must reflect synced bookmark state"
    print(f"  [{CLR_GREEN}PASS{CLR_RESET}] WorkManager Reconciliation: Remote state is reconciliated successfully.")
    
    print(f"\n{CLR_GREEN}{CLR_BOLD}Semua tes arsitektur Offline-First & Room ORM lulus 100%!{CLR_RESET}\n")

def main():
    # Setup In-Memory SQLite sebagai representasi Room SQLite Database
    sqlite_conn = sqlite3.connect(":memory:")
    dao = ArticleDao(sqlite_conn)
    remote = MockRemoteDataSource()
    repo = OfflineFirstRepository(dao, remote)

    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}  LAB SIMULASI: ANDROID OFFLINE-FIRST ARCHITECTURE & ROOM PERSISTENCE  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"Konsep Inti: Single Source of Truth (SSOT), Invalidation Tracker, Offline Queue\n")

    # Muat data pertama kali
    for articles in repo.get_articles_stream(force_refresh=True):
        print_ui_table(articles)

    while True:
        print(f"{CLR_BOLD}Menu Interaktif Arsitektur Data Layer:{CLR_RESET}")
        print("  1. Toggle Status Jaringan (Online / Offline)")
        print("  2. Refresh Data (NetworkBoundResource flow)")
        print("  3. Ubah Bookmark Artikel (Optimistic UI Update)")
        print("  4. Jalankan Background Sync (Simulasi Android WorkManager)")
        print("  5. Tampilkan Raw Tabel SQLite Room")
        print("  6. Jalankan Verifikasi Mandiri (Automated Assertion)")
        print("  0. Keluar")

        curr_net = f"{CLR_GREEN}ONLINE{CLR_RESET}" if remote.is_online else f"{CLR_RED}OFFLINE{CLR_RESET}"
        print(f"  Status Jaringan Saat Ini: {curr_net}")
        
        try:
            choice = input(f"{CLR_YELLOW}Pilih opsi [0-6]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            remote.is_online = not remote.is_online
            state_str = "ONLINE (WiFi/LTE Aktif)" if remote.is_online else "OFFLINE (Airplane Mode Aktif)"
            log_header(f"Status Jaringan Berubah: {state_str}")
        elif choice == "2":
            log_header("Memicu Refresh Swipe-to-Refresh")
            for articles in repo.get_articles_stream(force_refresh=True):
                print_ui_table(articles)
        elif choice == "3":
            log_header("Ubah Status Bookmark Artikel")
            try:
                art_id = int(input("  Masukkan ID Artikel (contoh 101, 102, 103): ").strip())
                curr_articles = {a.id: a for a in dao.get_all()}
                if art_id not in curr_articles:
                    print(f"  {CLR_RED}ID {art_id} tidak ditemukan di Room database.{CLR_RESET}")
                    continue
                new_state = not curr_articles[art_id].is_bookmarked
                repo.toggle_bookmark(art_id, new_state)
                print_ui_table(dao.get_all())
            except ValueError:
                print(f"  {CLR_RED}Input ID tidak valid.{CLR_RESET}")
        elif choice == "4":
            log_header("Trigger WorkManager Sync Worker")
            repo.run_sync_worker()
            print_ui_table(dao.get_all())
        elif choice == "5":
            log_header("Inspeksi Fisik Tabel Room SQLite")
            rows = dao.get_all()
            for r in rows:
                print(f"  {r}")
            print()
        elif choice == "6":
            run_self_verification(repo, remote, dao)
        elif choice == "0":
            print(f"{CLR_GREEN}Selesai. Keluar dari lab simulasi.{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Opsi tidak valid.{CLR_RESET}")

if __name__ == "__main__":
    main()
