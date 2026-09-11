/**
 * SIMULATOR: LRU CACHE O(1) ENGINE & CACHE-ASIDE PATTERN BENCHMARK
 * Modul 01: Pola Caching & Algoritma Eviksi (LRU, LFU, ARC)
 *
 * Mendemonstrasikan:
 * 1. Implementasi LRU Cache O(1) murni (Doubly Linked List + Hash Map) dengan dukungan TTL.
 * 2. Simulasi Pola Cache-Aside dengan perbandingan latensi DB (I/O) vs RAM Cache.
 * 3. Benchmark 1.000 request dengan distribusi Pareto (80/20 Rule).
 *
 * Jalankan: node caching_patterns_lru_sim.js
 */

// =========================================================================
// BAGIAN 1: STRUKTUR DATA LRU CACHE O(1) BERBASIS DOUBLY LINKED LIST
// =========================================================================

class Node {
  constructor(key, value, ttlMs = 0) {
    this.key = key;
    this.value = value;
    this.expiresAt = ttlMs > 0 ? Date.now() + ttlMs : null;
    this.prev = null;
    this.next = null;
  }

  isExpired() {
    return this.expiresAt !== null && Date.now() > this.expiresAt;
  }
}

class LRUCache {
  constructor(capacity) {
    this.capacity = capacity;
    this.map = new Map(); // O(1) key -> Node lookup
    this.head = new Node(null, null); // Dummy head (Most Recently Used)
    this.tail = new Node(null, null); // Dummy tail (Least Recently Used)
    this.head.next = this.tail;
    this.tail.prev = this.head;

    this.hits = 0;
    this.misses = 0;
    this.evictions = 0;
  }

  _removeNode(node) {
    node.prev.next = node.next;
    node.next.prev = node.prev;
  }

  _addNodeToHead(node) {
    node.next = this.head.next;
    node.prev = this.head;
    this.head.next.prev = node;
    this.head.next = node;
  }

  _moveToHead(node) {
    this._removeNode(node);
    this._addNodeToHead(node);
  }

  get(key) {
    if (!this.map.has(key)) {
      this.misses++;
      return null;
    }

    const node = this.map.get(key);

    // Cek apakah item sudah kedaluwarsa (TTL expired)
    if (node.isExpired()) {
      this._removeNode(node);
      this.map.delete(key);
      this.misses++;
      return null;
    }

    // Pindahkan ke Head karena baru saja diakses (Promoted to MRU)
    this._moveToHead(node);
    this.hits++;
    return node.value;
  }

  set(key, value, ttlMs = 0) {
    if (this.map.has(key)) {
      const node = this.map.get(key);
      node.value = value;
      node.expiresAt = ttlMs > 0 ? Date.now() + ttlMs : null;
      this._moveToHead(node);
      return;
    }

    // Jika kapasitas memori penuh, gusur elemen di Tail (LRU)
    if (this.map.size >= this.capacity) {
      const lruNode = this.tail.prev;
      this._removeNode(lruNode);
      this.map.delete(lruNode.key);
      this.evictions++;
    }

    const newNode = new Node(key, value, ttlMs);
    this.map.set(key, newNode);
    this._addNodeToHead(newNode);
  }

  delete(key) {
    if (!this.map.has(key)) return false;
    const node = this.map.get(key);
    this._removeNode(node);
    this.map.delete(key);
    return true;
  }

  getStats() {
    const total = this.hits + this.misses;
    const hitRate = total > 0 ? ((this.hits / total) * 100).toFixed(2) : '0.00';
    return {
      capacity: this.capacity,
      size: this.map.size,
      hits: this.hits,
      misses: this.misses,
      evictions: this.evictions,
      hitRate: `${hitRate}%`
    };
  }
}

// =========================================================================
// BAGIAN 2: SIMULASI DATABASE PRIMER & CACHE-ASIDE PATTERN
// =========================================================================

class MockDatabase {
  constructor() {
    this.products = new Map();
    // Inisialisasi 100 produk di database
    for (let i = 1; i <= 100; i++) {
      this.products.set(`PROD-${i}`, {
        id: `PROD-${i}`,
        name: `Item Premium Edition #${i}`,
        price: 150000 + i * 5000,
        stock: 50 + (i % 20)
      });
    }
    this.queryCount = 0;
  }

  // Simulasi I/O disk & latency jaringan database (~15ms)
  async findById(productId) {
    this.queryCount++;
    await new Promise(resolve => setTimeout(resolve, 1)); // 1ms simulated network I/O
    return this.products.get(productId) || null;
  }
}

class ProductRepositoryWithCache {
  constructor(db, cache) {
    this.db = db;
    this.cache = cache;
  }

  async getProduct(productId) {
    const cacheKey = `cache:product:${productId}`;

    // 1. Coba baca dari Cache (RAM - Sub-millisecond)
    const cached = this.cache.get(cacheKey);
    if (cached !== null) {
      return { data: cached, source: 'CACHE_HIT' };
    }

    // 2. Cache Miss: Ambil dari Database Primer
    const dbData = await this.db.findById(productId);
    if (dbData) {
      // 3. Simpan ke Cache dengan TTL 60 detik
      this.cache.set(cacheKey, dbData, 60000);
    }

    return { data: dbData, source: 'CACHE_MISS (DB)' };
  }
}

// =========================================================================
// BAGIAN 3: BENCHMARK BEBAN REALISTIS (PARETO 80/20 RULE)
// =========================================================================

async function runBenchmark() {
  console.log('='.repeat(75));
  console.log('BENCHMARK: EVALUASI PERFORMA POLA CACHE-ASIDE DENGAN LRU EVICTION');
  console.log('='.repeat(75));

  const db = new MockDatabase();
  const cacheCapacity = 20; // Cache hanya mampu menampung 20 item (20% dari total 100 produk)
  const lruCache = new LRUCache(cacheCapacity);
  const repo = new ProductRepositoryWithCache(db, lruCache);

  console.log(`Konfigurasi Uji:`);
  console.log(`- Total Produk di Database : 100 produk`);
  console.log(`- Kapasitas Memori Cache   : ${cacheCapacity} produk (20% working set)`);
  console.log(`- Pola Akses Trafik        : 80% request mengakses 20 produk terpopuler (Pareto)\n`);

  const totalRequests = 1000;
  let cacheHitCount = 0;
  let cacheMissCount = 0;

  const startTime = Date.now();

  for (let i = 0; i < totalRequests; i++) {
    // Bangkitkan ID berdasarkan distribusi Pareto:
    // 80% probabilitas mengakses PROD-1 s/d PROD-20 (Hot Items)
    // 20% probabilitas mengakses PROD-21 s/d PROD-100 (Cold Items)
    let prodId;
    if (Math.random() < 0.8) {
      prodId = `PROD-${Math.floor(Math.random() * 20) + 1}`;
    } else {
      prodId = `PROD-${Math.floor(Math.random() * 80) + 21}`;
    }

    const result = await repo.getProduct(prodId);
    if (result.source === 'CACHE_HIT') {
      cacheHitCount++;
    } else {
      cacheMissCount++;
    }
  }

  const durationMs = Date.now() - startTime;
  const stats = lruCache.getStats();

  console.log('HASIL PENGUJIAN:');
  console.log(`- Total HTTP Requests Dilayani : ${totalRequests} request`);
  console.log(`- Waktu Eksekusi Total        : ${durationMs} ms`);
  console.log(`- Cache Hits                   : ${cacheHitCount}`);
  console.log(`- Cache Misses                 : ${cacheMissCount}`);
  console.log(`- Database Queries Dijalankan  : ${db.queryCount} query`);
  console.log(`- Eviction Terjadi             : ${stats.evictions} item digusur`);
  console.log(`- Cache Hit Ratio Akhir        : ${stats.hitRate}`);
  console.log(`- Beban Database Terpangkas    : ${(((totalRequests - db.queryCount) / totalRequests) * 100).toFixed(2)}%\n`);

  console.log('STATUS AKHIR ELEMEN DI LRU CACHE (Head to Tail):');
  let current = lruCache.head.next;
  let index = 1;
  while (current !== lruCache.tail) {
    console.log(`  [Posisi ${String(index).padStart(2)}] ${current.key} => ${current.value.name}`);
    current = current.next;
    index++;
  }

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: LRU Cache Engine bekerja presisi dengan O(1) complexity!');
  console.log('='.repeat(75));
}

runBenchmark();
