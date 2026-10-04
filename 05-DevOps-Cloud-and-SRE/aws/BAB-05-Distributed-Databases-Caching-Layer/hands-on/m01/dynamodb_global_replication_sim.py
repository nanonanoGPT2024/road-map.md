#!/usr/bin/env python3
"""
DynamoDB Global Tables & Multi-Region Caching Layer Simulator
Curriculum: GEMINI.md - Distributed Databases & Caching Layer (Bab 05)

Skrip ini mensimulasikan secara mandiri (standalone, tanpa dependensi eksternal):
1. Arsitektur Multi-Region Active-Active Replication (DynamoDB Global Tables).
2. Mekanisme Resolusi Konflik Konkuren menggunakan Last-Writer-Wins (LWW).
3. Change Data Capture (CDC) via DynamoDB Streams.
4. Regional Cache Invalidation pada In-Memory Cache Layer (ElastiCache Simulator).
"""

import time
import json
import threading
from typing import Dict, Any, Optional

# ANSI Color codes untuk visualisasi log terminal
COLOR_RESET = "\033[0m"
COLOR_PRIMARY = "\033[1;34m"   # Blue
COLOR_SECONDARY = "\033[1;32m" # Green
COLOR_WARNING = "\033[1;33m"   # Yellow
COLOR_ALERT = "\033[1;31m"     # Red
COLOR_CYAN = "\033[1;36m"      # Cyan


class InMemoryCache:
    """Simulasi ElastiCache / Redis Layer lokal pada sebuah Region."""
    def __init__(self, region_name: str, default_ttl_sec: float = 2.0):
        self.region_name = region_name
        self.default_ttl_sec = default_ttl_sec
        self.store: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            entry = self.store.get(key)
            if not entry:
                return None
            if time.time() > entry["expires_at"]:
                del self.store[key]
                return None
            return entry["val"]

    def set(self, key: str, val: Any):
        with self.lock:
            self.store[key] = {
                "val": val,
                "expires_at": time.time() + self.default_ttl_sec
            }

    def invalidate(self, key: str):
        with self.lock:
            if key in self.store:
                del self.store[key]
                print(f"{COLOR_WARNING}[CACHE-INVALIDATE] ({self.region_name}) Cache evicted for key: {key}{COLOR_RESET}")


class DynamoDBStreamRecord:
    """Mempresentasikan payload CDC DynamoDB Stream event."""
    def __init__(self, event_name: str, keys: dict, old_image: dict, new_image: dict):
        self.event_id = f"stream-evt-{time.time_ns()}"
        self.event_name = event_name # INSERT, MODIFY, REMOVE
        self.keys = keys
        self.old_image = old_image
        self.new_image = new_image


class RegionalDynamoDBReplica:
    """Mempresentasikan satu replica tabel DynamoDB pada satu Region tertentu."""
    def __init__(self, region_name: str):
        self.region_name = region_name
        self.table_data: Dict[str, Dict[str, Any]] = {}
        self.cache = InMemoryCache(region_name)
        self.stream_subscribers = []
        self.lock = threading.Lock()

    def register_stream_subscriber(self, callback):
        self.stream_subscribers.append(callback)

    def _emit_stream_record(self, event_name: str, keys: dict, old_image: dict, new_image: dict):
        record = DynamoDBStreamRecord(event_name, keys, old_image, new_image)
        for sub in self.stream_subscribers:
            # Replikasi berjalan asinkronus (disimulasikan dengan worker thread)
            threading.Thread(target=sub, args=(self.region_name, record), daemon=True).start()

    def read_item(self, partition_key: str) -> Optional[Dict[str, Any]]:
        # 1. Cek Cache (Cache-Aside Strategy)
        cached_val = self.cache.get(partition_key)
        if cached_val is not None:
            print(f"{COLOR_CYAN}[CACHE-HIT] ({self.region_name}) Item '{partition_key}' fetched from Memory Cache.{COLOR_RESET}")
            return cached_val

        # 2. Cache Miss - Baca dari persistent storage
        with self.lock:
            item = self.table_data.get(partition_key)
            if item:
                print(f"{COLOR_WARNING}[CACHE-MISS] ({self.region_name}) Item '{partition_key}' fetched from Disk Storage.{COLOR_RESET}")
                # Update Cache
                self.cache.set(partition_key, item)
            else:
                print(f"[STORAGE-EMPTY] ({self.region_name}) Item '{partition_key}' not found.")
            return item

    def write_item_local(self, partition_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Eksekusi penulisan langsung dari client lokal ke region ini."""
        with self.lock:
            now_ts = time.time()
            old_image = self.table_data.get(partition_key, {}).copy()
            
            # Tambahkan metadata internal resolusi konflik LWW
            new_image = payload.copy()
            new_image["_pk"] = partition_key
            new_image["_last_updated_at"] = now_ts
            new_image["_origin_region"] = self.region_name

            self.table_data[partition_key] = new_image
            
            # Invalidate cache lokal segera setelah write berhasil (Cache Consistency)
            self.cache.invalidate(partition_key)

            print(f"{COLOR_PRIMARY}[LOCAL-WRITE] ({self.region_name}) Write Key='{partition_key}' | Payload={payload} | TS={now_ts:.6f}{COLOR_RESET}")
            
            # Pancarkan CDC Stream
            event_type = "MODIFY" if old_image else "INSERT"
            self._emit_stream_record(event_type, {"_pk": partition_key}, old_image, new_image)
            return new_image

    def apply_replicated_write(self, remote_region: str, record: DynamoDBStreamRecord):
        """Menerima dan menyelesaikan penulisan replikasi asinkronus dari region lain."""
        # Simulasi network propagation delay antar-benua (50ms - 150ms)
        time.sleep(0.08)

        pk = record.keys["_pk"]
        incoming_item = record.new_image
        incoming_ts = incoming_item["_last_updated_at"]

        with self.lock:
            current_item = self.table_data.get(pk)

            if current_item:
                current_ts = current_item.get("_last_updated_at", 0.0)
                # Evaluasi Mekanisme Last-Writer-Wins (LWW)
                if incoming_ts > current_ts:
                    print(f"{COLOR_SECONDARY}[REPLICATION-ACCEPT] ({self.region_name}) <-- Applied update from {remote_region} for Key='{pk}' (LWW Won: incoming {incoming_ts:.6f} > current {current_ts:.6f}){COLOR_RESET}")
                    self.table_data[pk] = incoming_item
                    self.cache.invalidate(pk)
                else:
                    print(f"{COLOR_ALERT}[REPLICATION-DISCARD] ({self.region_name}) <-- Dropped update from {remote_region} for Key='{pk}' (LWW Lost: incoming {incoming_ts:.6f} <= current {current_ts:.6f}){COLOR_RESET}")
            else:
                # Belum ada item, simpan langsung
                print(f"{COLOR_SECONDARY}[REPLICATION-NEW] ({self.region_name}) <-- Inserted new record from {remote_region} for Key='{pk}'{COLOR_RESET}")
                self.table_data[pk] = incoming_item
                self.cache.invalidate(pk)


class GlobalTableMesh:
    """Menghubungkan multiple regional replicas ke dalam topologi Global Table."""
    def __init__(self):
        self.replicas: Dict[str, RegionalDynamoDBReplica] = {}

    def add_region(self, region_name: str) -> RegionalDynamoDBReplica:
        replica = RegionalDynamoDBReplica(region_name)
        replica.register_stream_subscriber(self._route_stream_event)
        self.replicas[region_name] = replica
        return replica

    def _route_stream_event(self, source_region: str, record: DynamoDBStreamRecord):
        """Router jaringan AWS Global Infrastructure mensimulasikan broadcast stream."""
        for target_region, target_replica in self.replicas.items():
            if target_region != source_region:
                target_replica.apply_replicated_write(source_region, record)


def execute_simulation():
    print("=" * 80)
    print("  SIMULASI ARSITEKTUR DYNAMODB GLOBAL TABLES & DISTRIBUTED CACHING LAYER")
    print("=" * 80)

    mesh = GlobalTableMesh()
    region_us = mesh.add_region("us-east-1")
    region_eu = mesh.add_region("eu-west-1")

    item_id = "PRODUCT#SKU-7721"

    print("\n--- SKENARIO 1: Basic Write di Region US dan Replikasi ke EU ---")
    region_us.write_item_local(item_id, {"title": "Mechanical Keyboard", "stock": 100, "price": 120.0})
    time.sleep(0.3) # Tunggu async replication selesai

    print("\n--- SKENARIO 2: Verifikasi Cache Miss lalu Cache Hit di Region EU ---")
    print("[1st Read] Harusnya Cache Miss dan ambil dari persistent storage:")
    data_eu_1 = region_eu.read_item(item_id)
    print(f"Hasil: {data_eu_1.get('title')} | Stock: {data_eu_1.get('stock')}")

    print("\n[2nd Read] Harusnya Cache Hit langsung dari in-memory cache:")
    data_eu_2 = region_eu.read_item(item_id)
    print(f"Hasil: {data_eu_2.get('title')} | Stock: {data_eu_2.get('stock')}")

    print("\n--- SKENARIO 3: Concurrent Active-Active Write (Konflik Last-Writer-Wins) ---")
    print("Skenario: Region US dan Region EU melakukan penulisan ke SKU yang sama nyaris bersamaan.\n")

    def write_us():
        region_us.write_item_local(item_id, {"title": "Mechanical Keyboard v2 (US Update)", "stock": 85, "price": 115.0})

    def write_eu():
        # Tambahkan jeda mikroskopis 10ms untuk mensimulasikan event yang tiba belakangan
        time.sleep(0.01)
        region_eu.write_item_local(item_id, {"title": "Mechanical Keyboard Pro (EU Update)", "stock": 42, "price": 130.0})

    t1 = threading.Thread(target=write_us)
    t2 = threading.Thread(target=write_eu)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    # Beri waktu propagasi jaringan cross-region selesai
    time.sleep(0.4)

    print("\n--- SKENARIO 4: Evaluasi Status Akhir (Konvergensi Konsistensi Global) ---")
    final_us = region_us.table_data.get(item_id)
    final_eu = region_eu.table_data.get(item_id)

    print(f"State di us-east-1: Title='{final_us['title']}' | Stock={final_us['stock']} | Origin={final_us['_origin_region']}")
    print(f"State di eu-west-1: Title='{final_eu['title']}' | Stock={final_eu['stock']} | Origin={final_eu['_origin_region']}")

    if final_us == final_eu:
        print(f"\n{COLOR_PRIMARY}[SUCCESS] Global Convergence Tercapai! Kedua region identik berkat LWW.{COLOR_RESET}")
    else:
        print(f"\n{COLOR_ALERT}[FAILED] Data State Inkonsisten (Split-Brain Terdeteksi).{COLOR_RESET}")

    print("\n" + "=" * 80)
    print("  SIMULASI SELESAI")
    print("=" * 80)


if __name__ == "__main__":
    execute_simulation()

---