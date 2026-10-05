#!/usr/bin/env python3
"""
AWS Distributed Databases & Caching Layer - Interactive Hands-on Lab
Simulates Amazon DynamoDB partitioning, DAX/ElastiCache caching strategies,
and Eventual vs Strong Consistency replication lag.
"""

import sys
import time
import random
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List
from enum import Enum

# ANSI Terminal Color Codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Colors.RESET}"

# --- Data Models & Storage Engines ---

@dataclass
class Record:
    partition_key: str
    payload: str
    version: int = 1
    timestamp: float = field(default_factory=time.time)

class ReadConsistency(Enum):
    EVENTUAL = "EVENTUALLY_CONSISTENT"
    STRONG = "STRONGLY_CONSISTENT"

class DynamoDBStorageNode:
    """Simulates an AWS DynamoDB physical storage partition."""
    def __init__(self, partition_id: int):
        self.partition_id = partition_id
        self.primary_store: Dict[str, Record] = {}
        self.replica_stores: List[Dict[str, Record]] = [{}, {}]  # 2 storage replicas in 3 AZs
        self.replication_lag_ms: float = 25.0

    def put_item(self, key: str, payload: str) -> Record:
        current_version = self.primary_store[key].version + 1 if key in self.primary_store else 1
        record = Record(partition_key=key, payload=payload, version=current_version)
        self.primary_store[key] = record
        
        # Async replication to replicas (simulated lag)
        for replica in self.replica_stores:
            if random.random() > 0.3:  # 70% immediate, 30% lagged
                replica[key] = record
        return record

    def sync_replicas(self):
        """Catch-up replication for eventual consistency."""
        for key, record in self.primary_store.items():
            for replica in self.replica_stores:
                replica[key] = record

    def get_item(self, key: str, consistency: ReadConsistency) -> Tuple[Optional[Record], float]:
        start = time.perf_counter()
        if consistency == ReadConsistency.STRONG:
            # Reads from primary / quorum
            time.sleep(0.012)  # ~12ms network roundtrip
            record = self.primary_store.get(key)
        else:
            # Reads from random replica (may be stale)
            time.sleep(0.005)  # ~5ms single-replica read
            chosen_replica = random.choice(self.replica_stores)
            record = chosen_replica.get(key) or self.primary_store.get(key)
        latency_ms = (time.perf_counter() - start) * 1000
        return record, latency_ms

class DynamoDBCluster:
    """Manages consistent hashing and partition allocation."""
    def __init__(self, num_partitions: int = 4):
        self.num_partitions = num_partitions
        self.partitions = [DynamoDBStorageNode(i) for i in range(num_partitions)]

    def _hash_key(self, partition_key: str) -> int:
        md5_digest = hashlib.md5(partition_key.encode('utf-8')).hexdigest()
        return int(md5_digest, 16) % self.num_partitions

    def get_partition(self, partition_key: str) -> DynamoDBStorageNode:
        idx = self._hash_key(partition_key)
        return self.partitions[idx]

    def put(self, key: str, value: str) -> Tuple[Record, int]:
        partition = self.get_partition(key)
        rec = partition.put_item(key, value)
        return rec, partition.partition_id

    def get(self, key: str, consistency: ReadConsistency) -> Tuple[Optional[Record], int, float]:
        partition = self.get_partition(key)
        rec, latency = partition.get_item(key, consistency)
        return rec, partition.partition_id, latency

# --- In-Memory Caching Layer (ElastiCache / DAX Simulation) ---

class CacheStrategy(Enum):
    CACHE_ASIDE = "Cache-Aside (Lazy Loading)"
    WRITE_THROUGH = "Write-Through"

class CacheLayer:
    """Simulates Redis / Memcached / DAX in-memory caching."""
    def __init__(self, ttl_seconds: float = 5.0):
        self.cache: Dict[str, Tuple[str, float]] = {}
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Tuple[Optional[str], float]:
        start = time.perf_counter()
        time.sleep(0.0008)  # ~0.8ms sub-millisecond in-memory lookup
        now = time.time()
        
        if key in self.cache:
            val, expiry = self.cache[key]
            if now < expiry:
                self.hits += 1
                return val, (time.perf_counter() - start) * 1000
            else:
                del self.cache[key]
                
        self.misses += 1
        return None, (time.perf_counter() - start) * 1000

    def set(self, key: str, value: str):
        self.cache[key] = (value, time.time() + self.ttl)

    def invalidate(self, key: str):
        self.cache.pop(key, None)

    def clear(self):
        self.cache.clear()
        self.hits = 0
        self.misses = 0

# --- Interactive Lab Demonstrations ---

def demo_partitioning(db: DynamoDBCluster):
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== LAB 1: DynamoDB Consistent Hashing & Partition Key Distribution ==={Colors.RESET}")
    print("Menganalisis bagaimana Partition Key (PK) didistribusikan ke storage nodes fisik via MD5 hash ring.\n")
    
    sample_keys = [
        "user#1001", "order#9021", "session#abc89", "user#1002",
        "device#iot-99", "payment#tx-44", "order#9022", "user#1003",
        "tenant#org-alpha", "analytics#click-1"
    ]
    
    distribution: Dict[int, List[str]] = {i: [] for i in range(db.num_partitions)}
    
    print(f"{'Partition Key':<20} | {'MD5 Hash (Hex Prefix)':<22} | {'Target Partition':<18}")
    print("-" * 65)
    
    for key in sample_keys:
        hash_val = hashlib.md5(key.encode('utf-8')).hexdigest()
        p_node = db.get_partition(key)
        distribution[p_node.partition_id].append(key)
        rec, p_id = db.put(key, f"Data for {key}")
        print(f"{colorize(key, Colors.CYAN):<30} | {hash_val[:16]}... | {colorize(f'Partition #{p_id}', Colors.GREEN)}")
    
    print(f"\n{Colors.BOLD}Ringkasan Distribusi Beban (Sharding Balance):{Colors.RESET}")
    for p_id, keys in distribution.items():
        bar = "█" * (len(keys) * 4)
        print(f"  Node #{p_id}: {bar:<16} ({len(keys)} items) -> {keys}")
    print(f"\n{Colors.YELLOW}Insight Arsitektur AWS:{Colors.RESET} Kunci partisi dengan kardinalitas tinggi mencegah 'Hot Partitions'.")

def demo_caching_strategies(db: DynamoDBCluster, cache: CacheLayer):
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== LAB 2: Caching Strategies (Cache-Aside vs Write-Through) ==={Colors.RESET}")
    print("Membandingkan performa latensi antara Cache Hit (ElastiCache/DAX) vs Cache Miss (DynamoDB Read).\n")
    
    key = "product#catalog-item-404"
    initial_val = "SuperCloud SSD 2TB - Rp 2.500.000"
    db.put(key, initial_val)
    cache.clear()

    # Skenario 1: Cache-Aside Read Flow
    print(f"{Colors.BOLD}[1] Pola Cache-Aside (Lazy Loading):{Colors.RESET}")
    
    # Request 1: Cache Miss
    print("  -> Request 1: Read key...")
    cached_val, c_lat = cache.get(key)
    if cached_val is None:
        print(f"     [{colorize('CACHE MISS', Colors.RED)}] Latensi Cache: {c_lat:.2f}ms. Mengambil data dari DynamoDB...")
        rec, p_id, db_lat = db.get(key, ReadConsistency.EVENTUAL)
        cache.set(key, rec.payload)
        total_lat = c_lat + db_lat
        print(f"     [{colorize('DB READ SUCCESS', Colors.GREEN)}] Latensi DynamoDB: {db_lat:.2f}ms | Total Roundtrip: {total_lat:.2f}ms")
    
    # Request 2: Cache Hit
    print("\n  -> Request 2: Read key yang sama...")
    cached_val, c_lat = cache.get(key)
    if cached_val:
        print(f"     [{colorize('CACHE HIT', Colors.GREEN)}] Latensi DAX/ElastiCache: {c_lat:.2f}ms (Sub-millisecond)")
        print(f"     Data didapatkan langsung dari Memory: \"{cached_val}\"")
        speedup = (db_lat / c_lat) if c_lat > 0 else 100.0
        print(f"     {colorize(f'Akselerasi Kecepatan: ~{speedup:.1f}x lebih cepat!', Colors.YELLOW)}")

    # Skenario 2: Cache Invalidation / Stale Data Problem
    print(f"\n{Colors.BOLD}[2] Masalah Stale Data & Cache Invalidation:{Colors.RESET}")
    new_val = "SuperCloud SSD 2TB - Rp 2.100.000 (Flash Sale)"
    print(f"  -> Memperbarui data langsung di Database ke: \"{new_val}\"...")
    db.put(key, new_val)
    
    stale_val, _ = cache.get(key)
    print(f"  -> Read dari Cache tanpa Invalidation:")
    print(f"     Data Cache (STALE) : \"{colorize(stale_val, Colors.RED)}\"")
    rec, _, _ = db.get(key, ReadConsistency.STRONG)
    print(f"     Data DB Asli (REAL): \"{colorize(rec.payload, Colors.GREEN)}\"")
    
    print("  -> Menjalankan Invalidation (`cache.invalidate(key)`)...")
    cache.invalidate(key)
    val, _ = cache.get(key)
    print(f"     Status Cache setelah invalidasi: {colorize('PURGED / NONE', Colors.YELLOW)}")

def demo_consistency_race(db: DynamoDBCluster):
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== LAB 3: Eventual vs Strongly Consistent Reads (Replication Lag) ==={Colors.RESET}")
    print("Simulasi replication lag lintas Availability Zone (AZ) dan konsumsi RCU (Read Capacity Units).\n")
    
    item_key = "wallet#acc-8821"
    db.put(item_key, "Saldo: Rp 10.000.000")
    
    print(f"1. Transaksi: Transfer keluar Rp 5.000.000.")
    print("   Menulis saldo baru ke DynamoDB Primary Leader Replica...")
    db.put(item_key, "Saldo: Rp 5.000.000")
    
    print("\n2. Melakukan 10 concurrent reads cepat menggunakan:")
    print(f"   A) {colorize('Eventually Consistent Reads', Colors.CYAN)} (1/2 RCU cost)")
    print(f"   B) {colorize('Strongly Consistent Reads', Colors.GREEN)}   (1 RCU full cost)\n")
    
    eventual_stale_count = 0
    strong_correct_count = 0
    
    print(f"{'Req #':<6} | {'Eventual Read Result':<30} | {'Strong Read Result':<30}")
    print("-" * 72)
    
    for i in range(1, 11):
        rec_ev, _, lat_ev = db.get(item_key, ReadConsistency.EVENTUAL)
        rec_st, _, lat_st = db.get(item_key, ReadConsistency.STRONG)
        
        is_stale = rec_ev.payload != "Saldo: Rp 5.000.000"
        if is_stale:
            eventual_stale_count += 1
            ev_str = colorize(f"{rec_ev.payload} (STALE!)", Colors.RED)
        else:
            ev_str = colorize(rec_ev.payload, Colors.CYAN)
            
        strong_correct_count += 1
        st_str = colorize(f"{rec_st.payload} (FRESH)", Colors.GREEN)
        
        print(f"{i:<6} | {ev_str:<39} | {st_str:<39}")
        time.sleep(0.01)
        
    db.get_partition(item_key).sync_replicas()
    
    print(f"\n{Colors.BOLD}Hasil Uji Replikasi:{Colors.RESET}")
    print(f"  - Eventual Stale Reads : {colorize(str(eventual_stale_count), Colors.RED)} dari 10 request (Replication Lag)")
    print(f"  - Strong Consistent    : {colorize(str(strong_correct_count), Colors.GREEN)} dari 10 request selalu up-to-date")
    print(f"{Colors.YELLOW}Analisis Cost-Tradeoff AWS:{Colors.RESET} Eventual Consistency menghemat 50% biaya RCU, cocok untuk use case non-financial.")

def demo_full_stress_test(db: DynamoDBCluster, cache: CacheLayer):
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== LAB 4: High-Throughput Traffic & Cache Hit-Ratio Simulation ==={Colors.RESET}")
    print("Mensimulasikan 50 traffic request e-commerce untuk mengukur Hit Ratio dan Total Latency Savings.\n")
    
    catalog_keys = [f"item#{i}" for i in range(1, 11)]
    for k in catalog_keys:
        db.put(k, f"Specs for {k}")
    cache.clear()
    
    total_db_time = 0.0
    total_cache_time = 0.0
    requests = 50
    
    # 80/20 Zipfian-like distribution (Top 2 items get 70% of traffic)
    weights = [0.45, 0.25, 0.05, 0.05, 0.04, 0.04, 0.04, 0.04, 0.05, 0.04]
    
    print(f"Menjalankan {requests} requests ke caching tier...")
    for i in range(requests):
        chosen_key = random.choices(catalog_keys, weights=weights, k=1)[0]
        val, c_lat = cache.get(chosen_key)
        total_cache_time += c_lat
        
        if val is None:
            rec, _, d_lat = db.get(chosen_key, ReadConsistency.EVENTUAL)
            cache.set(chosen_key, rec.payload)
            total_db_time += d_lat
        else:
            pass  # Served purely from cache
            
    hit_ratio = (cache.hits / requests) * 100.0
    combined_latency = total_cache_time + total_db_time
    hypothetical_no_cache_latency = requests * 8.5  # Average 8.5ms per direct DB read
    saved_time = hypothetical_no_cache_latency - combined_latency
    
    print(f"\n{Colors.BOLD}Laporan Metrik Kinerja (CloudWatch Metrics):{Colors.RESET}")
    print(f"  • Total Requests     : {requests}")
    print(f"  • Cache Hits         : {colorize(str(cache.hits), Colors.GREEN)}")
    print(f"  • Cache Misses       : {colorize(str(cache.misses), Colors.RED)}")
    print(f"  • Cache Hit Ratio    : {colorize(f'{hit_ratio:.1f}%', Colors.BOLD + Colors.CYAN)}")
    print(f"  • Waktu Latensi Riil : {combined_latency:.2f} ms")
    print(f"  • Waktu Tanpa Cache  : {hypothetical_no_cache_latency:.2f} ms")
    print(f"  • Latency Overhead Cut: {colorize(f'{saved_time:.2f} ms ({saved_time/hypothetical_no_cache_latency*100:.1f}%)', Colors.GREEN)}")

def main_menu():
    db = DynamoDBCluster(num_partitions=4)
    cache = CacheLayer(ttl_seconds=10.0)
    
    while True:
        print(f"\n{Colors.BOLD}{Colors.BLUE}===================================================================={Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN} AWS CLOUD LAB: Distributed Databases & Caching Layer (BAB-05){Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}===================================================================={Colors.RESET}")
        print("Pilih modul simulasi praktikum:")
        print(" [1] DynamoDB Consistent Hashing & Partition Key Distribution")
        print(" [2] Caching Strategies (Cache-Aside, Write-Through & Invalidation)")
        print(" [3] Eventual vs Strongly Consistent Reads (Replication Lag & RCU)")
        print(" [4] High-Throughput Stress Test & Cache Hit Ratio Metrics")
        print(" [5] Jalankan Seluruh Demonstrasi (Automated Full Tour)")
        print(" [0] Keluar")
        print(f"{Colors.BLUE}--------------------------------------------------------------------{Colors.RESET}")
        
        choice = input(f"{Colors.BOLD}Masukkan pilihan [0-5]: {Colors.RESET}").strip()
        
        if choice == "1":
            demo_partitioning(db)
        elif choice == "2":
            demo_caching_strategies(db, cache)
        elif choice == "3":
            demo_consistency_race(db)
        elif choice == "4":
            demo_full_stress_test(db, cache)
        elif choice == "5":
            demo_partitioning(db)
            demo_caching_strategies(db, cache)
            demo_consistency_race(db)
            demo_full_stress_test(db, cache)
        elif choice in ("0", "exit", "quit"):
            print(f"\n{Colors.GREEN}Selesai. Selamat mempelajari arsitektur database terdistribusi AWS!{Colors.RESET}\n")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan coba lagi.{Colors.RESET}")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Program dihentikan oleh user. Sampai jumpa!{Colors.RESET}")
        sys.exit(0)
