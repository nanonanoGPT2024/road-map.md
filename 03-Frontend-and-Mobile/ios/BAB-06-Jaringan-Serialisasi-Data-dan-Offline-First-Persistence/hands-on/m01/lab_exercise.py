#!/usr/bin/env python3
"""
iOS Lab Exercise: BAB-06 - Jaringan, Serialisasi Data, dan Offline-First Persistence
Simulasi Teknis Konsep Arsitektur iOS:
  1. URLSession Architecture (Network Session, URLRequest, HTTPURLResponse, Cache Policies)
  2. Swift Codable Engine (JSONEncoder/Decoder, KeyDecodingStrategy snake_case <-> camelCase)
  3. Persistent Container (CoreData / SwiftData in-memory schema, CRUD, Dirty Tracker)
  4. Offline-First Sync Engine (Outbox Pattern, Network Reachability, Conflict Resolution)
"""

import sys
import json
import time
import uuid
import datetime
from typing import Dict, Any, List, Optional, Tuple

# ==============================================================================
# ANSI Color Codes & UI Helper
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    BG_BLUE = "\033[44m"

def print_header(title: str):
    print(f"\n{Color.CYAN}{'=' * 72}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}{title.center(72)}{Color.RESET}")
    print(f"{Color.CYAN}{'=' * 72}{Color.RESET}")

def print_step(step: str, desc: str):
    print(f"\n{Color.YELLOW}[STEP] {Color.BOLD}{step}{Color.RESET}: {desc}")

def print_success(msg: str):
    print(f" {Color.GREEN}✔ {msg}{Color.RESET}")

def print_info(label: str, msg: str):
    print(f"   {Color.CYAN}▸ {Color.BOLD}{label}:{Color.RESET} {msg}")

def print_warning(msg: str):
    print(f" {Color.YELLOW}⚠ {msg}{Color.RESET}")

def print_error(msg: str):
    print(f" {Color.RED}✖ {msg}{Color.RESET}")


# ==============================================================================
# 1. Swift Codable Simulator (Serialization Engine)
# ==============================================================================
class CodableSimulator:
    """
    Simulasi Swift `Codable` protocol dengan `JSONDecoder.KeyDecodingStrategy.convertFromSnakeCase`
    dan `JSONEncoder.KeyEncodingStrategy.convertToSnakeCase`.
    """
    @staticmethod
    def snake_to_camel(snake_str: str) -> str:
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

    @staticmethod
    def camel_to_snake(camel_str: str) -> str:
        res = []
        for char in camel_str:
            if char.isupper():
                res.append('_' + char.lower())
            else:
                res.append(char)
        return ''.join(res).lstrip('_')

    @classmethod
    def decode(cls, json_str: str, key_strategy: str = "convertFromSnakeCase") -> Dict[str, Any]:
        data = json.loads(json_str)
        if key_strategy == "convertFromSnakeCase":
            return {cls.snake_to_camel(k): v for k, v in data.items()}
        return data

    @classmethod
    def encode(cls, obj: Dict[str, Any], key_strategy: str = "convertToSnakeCase") -> str:
        if key_strategy == "convertToSnakeCase":
            transformed = {cls.camel_to_snake(k): v for k, v in obj.items()}
            return json.dumps(transformed, indent=2)
        return json.dumps(obj, indent=2)


# ==============================================================================
# 2. URLSession & Networking Simulator
# ==============================================================================
class CachePolicy:
    RELOAD_IGNORING_LOCAL_CACHE = "reloadIgnoringLocalCacheData"
    RETURN_CACHE_DATA_ELSE_LOAD = "returnCacheDataElseLoad"

class HTTPURLResponse:
    def __init__(self, status_code: int, headers: Dict[str, str]):
        self.status_code = status_code
        self.headers = headers

class URLSessionSimulator:
    """
    Simulasi iOS `URLSession` dengan konfigurasi Cache, Latency, dan Network Reachability.
    """
    def __init__(self):
        self.cache: Dict[str, Tuple[str, float]] = {}  # url -> (payload, timestamp)
        self.is_connected = True
        self.remote_db: Dict[str, Dict[str, Any]] = {}

    def set_reachability(self, online: bool):
        self.is_connected = online
        status = f"{Color.GREEN}ONLINE (Wi-Fi/Cellular){Color.RESET}" if online else f"{Color.RED}OFFLINE (Airplane Mode / No Connection){Color.RESET}"
        print(f"   [NWPathMonitor] Network Status Changed: {status}")

    def data_task(self, url: str, method: str = "GET", body: Optional[str] = None,
                  cache_policy: str = CachePolicy.RETURN_CACHE_DATA_ELSE_LOAD) -> Tuple[Optional[str], Optional[HTTPURLResponse], Optional[str]]:
        """
        Simulasi async data task: (Data?, URLResponse?, Error?)
        """
        now = time.time()
        
        # Check Cache Policy First
        if method == "GET" and cache_policy == CachePolicy.RETURN_CACHE_DATA_ELSE_LOAD:
            if url in self.cache:
                cached_data, cached_time = self.cache[url]
                print_info("URLCache", f"HIT (Local disk/memory cache, age: {now - cached_time:.2f}s)")
                return cached_data, HTTPURLResponse(200, {"X-Cache": "HIT"}), None

        # Network Check
        if not self.is_connected:
            return None, None, "The Internet connection appears to be offline. (NSURLErrorNotConnectedToInternet -1009)"

        # Simulated Remote Server Execution
        time.sleep(0.05)  # simulate roundtrip
        if method == "GET":
            payload = json.dumps(list(self.remote_db.values()))
            self.cache[url] = (payload, now)
            return payload, HTTPURLResponse(200, {"X-Cache": "MISS"}), None
        
        elif method == "POST":
            if body:
                record = json.loads(body)
                rec_id = record.get("id", str(uuid.uuid4()))
                self.remote_db[rec_id] = record
                self.cache.pop(url, None)  # Invalidate cache
                return json.dumps({"status": "created", "id": rec_id}), HTTPURLResponse(201, {}), None

        return None, HTTPURLResponse(400, {}), "Bad Request"


# ==============================================================================
# 3. Persistent Store Simulator (SwiftData / CoreData Model Context)
# ==============================================================================
class LocalEntity:
    def __init__(self, entity_id: str, title: str, content: str, updated_at: float, sync_state: str = "synced"):
        self.id = entity_id
        self.title = title
        self.content = content
        self.updated_at = updated_at
        self.sync_state = sync_state  # "synced", "pending_insert", "pending_update"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "updatedAt": self.updated_at,
            "syncState": self.sync_state
        }

class ModelContextSimulator:
    """
    Simulasi SwiftData `ModelContext` / CoreData `NSManagedObjectContext`
    dengan tracking dirty state dan pending change outbox.
    """
    def __init__(self):
        self.entities: Dict[str, LocalEntity] = {}

    def insert(self, title: str, content: str) -> LocalEntity:
        entity_id = str(uuid.uuid4())[:8]
        entity = LocalEntity(entity_id, title, content, time.time(), sync_state="pending_insert")
        self.entities[entity_id] = entity
        return entity

    def update(self, entity_id: str, new_title: str, new_content: str):
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            entity.title = new_title
            entity.content = new_content
            entity.updated_at = time.time()
            if entity.sync_state != "pending_insert":
                entity.sync_state = "pending_update"

    def fetch_all(self) -> List[LocalEntity]:
        return list(self.entities.values())

    def fetch_dirty(self) -> List[LocalEntity]:
        return [e for e in self.entities.values() if e.sync_state in ("pending_insert", "pending_update")]

    def mark_synced(self, entity_id: str):
        if entity_id in self.entities:
            self.entities[entity_id].sync_state = "synced"


# ==============================================================================
# 4. Offline-First Sync Engine (Outbox Pattern & Conflict Resolution)
# ==============================================================================
class OfflineSyncEngine:
    def __init__(self, context: ModelContextSimulator, session: URLSessionSimulator, api_endpoint: str):
        self.context = context
        self.session = session
        self.api_endpoint = api_endpoint

    def synchronize(self):
        print_step("SYNCHRONIZE", "Menjalankan Outbox Pattern & Conflict Resolution")
        dirty_records = self.context.fetch_dirty()
        
        if not dirty_records:
            print_info("SyncEngine", "Tidak ada perubahan lokal (Outbox kosong).")
            return

        print_info("Outbox Queue", f"Ditemukan {len(dirty_records)} item tertunda yang perlu disinkronkan.")

        for item in dirty_records:
            # Gunakan Codable Simulator untuk mengonversi model lokal ke JSON API (snake_case)
            local_dict = {
                "id": item.id,
                "title": item.title,
                "content": item.content,
                "clientTimestamp": item.updated_at
            }
            json_payload = CodableSimulator.encode(local_dict, key_strategy="convertToSnakeCase")

            print(f"   {Color.MAGENTA}↑ Mengunggah {item.id} ({item.sync_state})...{Color.RESET}")
            data, resp, err = self.session.data_task(
                url=self.api_endpoint,
                method="POST",
                body=json_payload
            )

            if err:
                print_error(f"Gagal mengunggah item {item.id}: {err}")
                print_warning(f"Item {item.id} tetap berada dalam Outbox lokal.")
            elif resp and resp.status_code in (200, 201):
                self.context.mark_synced(item.id)
                print_success(f"Item {item.id} berhasil disinkronkan ke server backend. State -> 'synced'")


# ==============================================================================
# Main Interactive Simulation
# ==============================================================================
def run_simulation():
    print_header("LAB SIMULATOR: iOS NETWORKING & OFFLINE-FIRST PERSISTENCE")
    print(f"{Color.DIM}Simulasi arsitektur Swift URLSession, Codable, SwiftData/CoreData, dan Outbox Sync.{Color.RESET}\n")

    context = ModelContextSimulator()
    session = URLSessionSimulator()
    api_endpoint = "https://api.apple-dev.internal/v1/notes"
    sync_engine = OfflineSyncEngine(context, session, api_endpoint)

    # --------------------------------------------------------------------------
    # Demo 1: Swift Codable Engine
    # --------------------------------------------------------------------------
    print_step("1. SWIFT CODABLE", "Serialisasi & Deserialisasi Model Swift")
    api_json_sample = '{"note_id": "ios-101", "author_name": "Steve Woz", "is_pinned": true}'
    print_info("Incoming JSON (snake_case)", api_json_sample)
    
    decoded = CodableSimulator.decode(api_json_sample, "convertFromSnakeCase")
    print_success("Decoded ke Swift Struct (camelCase properties):")
    for k, v in decoded.items():
        print(f"      • {Color.BOLD}{k}{Color.RESET}: {v}")

    re_encoded = CodableSimulator.encode(decoded, "convertToSnakeCase")
    print_success("Re-encoded ke JSON Network Payload (snake_case strategy):")
    print(f"{Color.DIM}{re_encoded}{Color.RESET}")

    # --------------------------------------------------------------------------
    # Demo 2: Local Persistence saat Offline (Airplane Mode)
    # --------------------------------------------------------------------------
    print_step("2. OFFLINE OPERATION", "Aplikasi Berjalan dalam Keadaan Offline (CoreData/SwiftData)")
    session.set_reachability(False)

    print("\n   Pengguna membuat 2 catatan baru di iPhone saat tidak ada sinyal:")
    note1 = context.insert("Arsitektur URLSession", "Gunakan ephemeral untuk guest session, background session untuk download besar.")
    note2 = context.insert("SwiftData Predicates", "#Predicate Macro menjamin type-safety pada saat compile-time.")
    print_success(f"Disimpan ke ModelContext lokal: [{note1.id}] '{note1.title}' (State: {note1.sync_state})")
    print_success(f"Disimpan ke ModelContext lokal: [{note2.id}] '{note2.title}' (State: {note2.sync_state})")

    # Mencoba sync saat offline
    print("\n   Mencoba trigger sinkronisasi otomatis saat offline:")
    sync_engine.synchronize()

    # --------------------------------------------------------------------------
    # Demo 3: Transisi Online & Outbox Execution
    # --------------------------------------------------------------------------
    print_step("3. ONLINE RECOVERY", "Koneksi Tersambung Kembali & Eksekusi Antrean Outbox")
    session.set_reachability(True)
    sync_engine.synchronize()

    # --------------------------------------------------------------------------
    # Demo 4: URLCache Policy Test
    # --------------------------------------------------------------------------
    print_step("4. URLCACHE TEST", "Pengujian Cache Policy (ReturnCacheDataElseLoad)")
    print("   Request 1: Mengambil catatan dari API...")
    data1, resp1, _ = session.data_task(api_endpoint, "GET")
    print_success(f"Status: {resp1.status_code if resp1 else 'ERR'}, Cache Header: {resp1.headers.get('X-Cache') if resp1 else '-'}")

    print("\n   Request 2: Mengambil catatan kembali (harus Cache HIT):")
    data2, resp2, _ = session.data_task(api_endpoint, "GET")
    print_success(f"Status: {resp2.status_code if resp2 else 'ERR'}, Cache Header: {resp2.headers.get('X-Cache') if resp2 else '-'}")

    # --------------------------------------------------------------------------
    # Rangkuman Keadaan Akhir
    # --------------------------------------------------------------------------
    print_step("5. VERIFIKASI AKHIR", "Pemeriksaan Konsistensi Data Lokal vs Server")
    all_local = context.fetch_all()
    print_info("Jumlah Entitas Lokal", str(len(all_local)))
    print_info("Jumlah Entitas Server", str(len(session.remote_db)))
    
    all_synced = all(e.sync_state == "synced" for e in all_local)
    if all_synced and len(all_local) == len(session.remote_db):
        print_success("STATUS SISTEM: 100% KONSISTEN (All local records synced to remote DB)")
    else:
        print_warning("STATUS SISTEM: Terdapat inkonsistensi data.")

    print_header("SIMULASI LAB SELESAI DENGAN SUKSES")

if __name__ == "__main__":
    try:
        run_simulation()
    except KeyboardInterrupt:
        print("\n\nSimulasi dibatalkan oleh pengguna.")
        sys.exit(0)
