#!/usr/bin/env python3
"""
Simulasi Lab: Pola Caching (Cache-Aside / Lazy Loading) Terdistribusi
Mensimulasikan interaksi antara Application, Caching Layer (Mock Redis), dan Database Utama (Mock RDS).
"""

import time
import json
import threading
from collections import OrderedDict
import random

# ==========================================
# 1. Mock Caching Layer (Simulasi Redis LRU)
# ==========================================
class MockRedisCache:
    def __init__(self, capacity=5):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        with self.lock:
            if key in self.cache:
                # Pindahkan ke paling akhir (paling sering digunakan / MRU)
                self.cache.move_to_end(key)
                self.hits += 1
                print(f"[\033[92mCACHE HIT\033[0m] Data ditemukan di Cache untuk key: '{key}'")
                return self.cache[key]
            else:
                self.misses += 1
                print(f"[\033[91mCACHE MISS\033[0m] Data TIDAK ditemukan di Cache untuk key: '{key}'")
                return None

    def set(self, key, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                # Buang item paling awal (paling jarang digunakan / LRU)
                evicted = self.cache.popitem(last=False)
                print(f"[\033[93mCACHE EVICTION\033[0m] Kapasitas penuh. Menghapus key: '{evicted[0]}'")
            print(f"[\033[94mCACHE WRITE\033[0m] Menyimpan data ke Cache untuk key: '{key}'")

    def get_stats(self):
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return f"Hits: {self.hits}, Misses: {self.misses}, Hit Rate: {hit_rate:.2f}%"


# ==========================================
# 2. Mock Database Layer (Simulasi Amazon RDS)
# ==========================================
class MockDatabase:
    def __init__(self):
        # Simulasi data di Database
        self.data = {
            "product_1": {"id": 1, "name": "Laptop Pro 15", "price": 1500, "stock": 42},
            "product_2": {"id": 2, "name": "Wireless Mouse", "price": 50, "stock": 105},
            "product_3": {"id": 3, "name": "Mechanical Keyboard", "price": 120, "stock": 30},
            "product_4": {"id": 4, "name": "4K Monitor", "price": 400, "stock": 15},
            "product_5": {"id": 5, "name": "USB-C Hub", "price": 35, "stock": 200},
            "product_6": {"id": 6, "name": "Noise Cancelling Headphones", "price": 250, "stock": 60},
            "product_7": {"id": 7, "name": "Webcam 1080p", "price": 80, "stock": 85},
        }

    def fetch_data(self, key):
        print(f"[\033[95mDB QUERY\033[0m] Mengambil data dari Database lambat untuk key: '{key}'...")
        # Simulasi Network dan Disk Latency dari Database Relasional
        time.sleep(random.uniform(1.0, 2.0))
        
        if key in self.data:
            print(f"[\033[95mDB RESULT\033[0m] Data '{key}' ditemukan di Database.")
            return json.dumps(self.data[key])
        else:
            print(f"[\033[91mDB ERROR\033[0m] Data '{key}' tidak ditemukan di Database.")
            return None


# ==========================================
# 3. Application Logic Layer
# ==========================================
class Application:
    def __init__(self, db, cache):
        self.db = db
        self.cache = cache

    def get_product(self, product_id):
        key = f"product_{product_id}"
        print(f"\n--- Meminta data produk: {key} ---")
        
        start_time = time.time()
        
        # Implementasi Pola Cache-Aside (Lazy Loading)
        # Langkah 1: Cek Cache terlebih dahulu
        data = self.cache.get(key)
        
        if data is None:
            # Langkah 2: Jika Cache Miss, ambil dari Database
            data = self.db.fetch_data(key)
            
            if data is not None:
                # Langkah 3: Simpan ke Cache untuk permintaan selanjutnya
                self.cache.set(key, data)
        
        elapsed = time.time() - start_time
        
        if data:
            print(f"[\033[96mAPP SUCCESS\033[0m] Data diterima dalam {elapsed:.4f} detik.")
        else:
            print(f"[\033[91mAPP ERROR\033[0m] Produk tidak ditemukan.")
            
        return data


# ==========================================
# 4. Main Execution (Simulasi Traffic)
# ==========================================
def run_simulation():
    print("\033[1m=== Memulai Simulasi Distributed Caching Layer (Cache-Aside) ===\033[0m\n")
    
    db = MockDatabase()
    # Cache berkapasitas 3 item untuk memicu Cache Eviction
    cache = MockRedisCache(capacity=3) 
    app = Application(db, cache)
    
    # Skenario 1: Cache Miss (Data belum ada di cache)
    print("\033[1m>> SKENARIO 1: Permintaan pertama (Cache Miss)\033[0m")
    app.get_product(1)
    
    # Skenario 2: Cache Hit (Data sudah ada di cache)
    print("\n\033[1m>> SKENARIO 2: Permintaan kedua untuk data yang sama (Cache Hit)\033[0m")
    app.get_product(1)
    
    # Skenario 3: Mengisi cache hingga penuh dan memicu Eviction
    print("\n\033[1m>> SKENARIO 3: Memenuhi kapasitas Cache & memicu LRU Eviction\033[0m")
    app.get_product(2) # Cache isi: [1, 2]
    app.get_product(3) # Cache isi: [1, 2, 3] -> Penuh
    app.get_product(4) # Cache isi: [2, 3, 4] -> Eviction terjadi pada key 'product_1'
    
    # Skenario 4: Kembali meminta data yang sudah di-evict
    print("\n\033[1m>> SKENARIO 4: Meminta data yang sudah dihapus dari Cache\033[0m")
    app.get_product(1) # Cache isi: [3, 4, 1] -> Cache Miss lagi untuk product_1
    
    # Skenario 5: Lonjakan Traffic (Loop)
    print("\n\033[1m>> SKENARIO 5: Simulasi lonjakan trafik untuk Hot Items\033[0m")
    hot_items = [2, 4, 2, 2, 4, 99] # 99 adalah produk tidak valid
    for item in hot_items:
        app.get_product(item)
        time.sleep(0.5)
        
    print("\n\033[1m=== Ringkasan Performa Cache ===\033[0m")
    print(cache.get_stats())
    print("\033[1m================================\033[0m\n")

if __name__ == "__main__":
    run_simulation()
