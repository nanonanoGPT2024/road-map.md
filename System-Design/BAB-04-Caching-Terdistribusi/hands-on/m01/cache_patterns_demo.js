// cache_patterns_demo.js
// Simulator & Komparasi 3 Pola Akses Caching: Cache-Aside, Write-Through, dan Write-Behind

// 1. Simulasi Storage Database (Disk IO / Network: ~60ms)
class MockDatabase {
  constructor() {
    this.store = new Map([
      ["prod-1", { id: "prod-1", name: "Keyboard Mechanical", price: 80 }],
      ["prod-2", { id: "prod-2", name: "Gaming Mouse", price: 40 }]
    ]);
  }

  async read(key) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(this.store.has(key) ? { ...this.store.get(key) } : null);
      }, 60);
    });
  }

  async write(key, value) {
    return new Promise((resolve) => {
      setTimeout(() => {
        this.store.set(key, { ...value });
        resolve(true);
      }, 60);
    });
  }
}

// 2. Simulasi Storage Memory Cache (RAM: ~2ms)
class MockCache {
  constructor() {
    this.store = new Map();
  }

  async get(key) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(this.store.has(key) ? { ...this.store.get(key) } : null);
      }, 2);
    });
  }

  async set(key, value) {
    return new Promise((resolve) => {
      setTimeout(() => {
        this.store.set(key, { ...value });
        resolve(true);
      }, 2);
    });
  }

  async delete(key) {
    return new Promise((resolve) => {
      setTimeout(() => {
        this.store.delete(key);
        resolve(true);
      }, 2);
    });
  }
}

// ===================================================================
// A. IMPLEMENTASI CACHE-ASIDE (LAZY LOADING)
// ===================================================================
class CacheAsideService {
  constructor(db, cache) {
    this.db = db;
    this.cache = cache;
  }

  async getProduct(id) {
    const start = Date.now();
    // 1. Cek Cache
    const cached = await this.cache.get(id);
    if (cached) {
      return { data: cached, latencyMs: Date.now() - start, source: "Cache HIT (RAM)" };
    }

    // 2. Cache Miss: Ambil dari DB
    const dbData = await this.db.read(id);
    if (dbData) {
      // 3. Simpan ke Cache
      await this.cache.set(id, dbData);
    }
    return { data: dbData, latencyMs: Date.now() - start, source: "Cache MISS -> DB Fetch" };
  }

  // Pola Penulisan Aman: Tulis ke DB dulu, lalu Delete Cache
  async updateProduct(id, newProduct) {
    const start = Date.now();
    await this.db.write(id, newProduct);
    await this.cache.delete(id); // Invalidate cache
    return { latencyMs: Date.now() - start, action: "Write DB & Delete Cache" };
  }
}

// ===================================================================
// B. IMPLEMENTASI WRITE-THROUGH
// ===================================================================
class WriteThroughService {
  constructor(db, cache) {
    this.db = db;
    this.cache = cache;
  }

  async updateProduct(id, newProduct) {
    const start = Date.now();
    // Tulis ke Cache dan DB secara sinkron berurutan
    await this.cache.set(id, newProduct);
    await this.db.write(id, newProduct);
    return { latencyMs: Date.now() - start, action: "Synchronous Write (Cache + DB)" };
  }
}

// ===================================================================
// C. IMPLEMENTASI WRITE-BEHIND (WRITE-BACK ASYNCHRONOUS BATCH)
// ===================================================================
class WriteBehindService {
  constructor(db, cache) {
    this.db = db;
    this.cache = cache;
    this.writeQueue = [];
    this.isFlushing = false;

    // Background worker setiap 200ms melakukan batch flush ke DB
    setInterval(() => this.flushQueueToDatabase(), 200);
  }

  async updateProduct(id, newProduct) {
    const start = Date.now();
    // 1. Tulis ke Cache seketika
    await this.cache.set(id, newProduct);
    // 2. Masukkan ke antrean asinkron
    this.writeQueue.push({ id, data: newProduct });
    // Langsung return ke client!
    return { latencyMs: Date.now() - start, action: "Instant Write to Cache (Queued for DB)" };
  }

  async flushQueueToDatabase() {
    if (this.writeQueue.length === 0 || this.isFlushing) return;
    this.isFlushing = true;
    const batch = [...this.writeQueue];
    this.writeQueue = [];

    console.log(`\n  🔄 [BACKGROUND FLUSH]: Menulis ${batch.length} item secara asinkron ke database...`);
    for (const item of batch) {
      await this.db.write(item.id, item.data);
    }
    console.log(`  ✅ [FLUSH SELESAI]: Database tersinkronisasi.`);
    this.isFlushing = false;
  }
}

async function runDemo() {
  console.log("===================================================================");
  console.log("    SIMULATOR & KOMPARASI POLA CACHING TERDISTRIBUSI               ");
  console.log("===================================================================\n");

  const db = new MockDatabase();
  const cache = new MockCache();

  // 1. UJI CACHE-ASIDE
  console.log("--- 1. UJI POLA CACHE-ASIDE (LAZY LOADING) ---");
  const asideService = new CacheAsideService(db, cache);

  const req1 = await asideService.getProduct("prod-1");
  console.log(`Request 1: Latensi = ${req1.latencyMs} ms | Status = ${req1.source}`);

  const req2 = await asideService.getProduct("prod-1");
  console.log(`Request 2: Latensi = ${req2.latencyMs} ms | Status = ${req2.source}`);

  console.log("\nAdmin mengupdate harga produk #prod-1...");
  const updateAside = await asideService.updateProduct("prod-1", { id: "prod-1", name: "Keyboard Mechanical", price: 95 });
  console.log(`Update Selesai dlm ${updateAside.latencyMs} ms (${updateAside.action})`);

  const req3 = await asideService.getProduct("prod-1");
  console.log(`Request 3 (Pasca Update): Latensi = ${req3.latencyMs} ms | Status = ${req3.source} | Harga Baru = $${req3.data.price}`);

  // 2. UJI WRITE-THROUGH
  console.log("\n--- 2. UJI POLA WRITE-THROUGH (SINKRON) ---");
  const writeThroughService = new WriteThroughService(db, cache);
  const wtRes = await writeThroughService.updateProduct("prod-2", { id: "prod-2", name: "Gaming Mouse RGB", price: 50 });
  console.log(`Write-Through Selesai dlm ${wtRes.latencyMs} ms | Wajib menunggu DB selesai (~62ms).`);

  // 3. UJI WRITE-BEHIND
  console.log("\n--- 3. UJI POLA WRITE-BEHIND (ASINKRON) ---");
  const writeBehindService = new WriteBehindService(db, cache);
  const wbRes = await writeBehindService.updateProduct("prod-2", { id: "prod-2", name: "Gaming Mouse Wireless", price: 65 });
  console.log(`Write-Behind Selesai dlm ${wbRes.latencyMs} ms! (Instan kembali ke user, DB antre di background).`);

  // Tunggu agar interval flush asinkron selesai sebelum script berakhir
  await new Promise(r => setTimeout(r, 400));

  console.log("\n===================================================================");
  console.log(" [KESIMPULAN ANALISIS CACHING]:");
  console.log(" 1. Cache-Aside: Read kedua 30x lebih cepat (2ms vs 62ms).");
  console.log(" 2. Write-Through: Aman konsisten, namun penulisan lambat (62ms).");
  console.log(" 3. Write-Behind: Penulisan secepat kilat (2ms), namun ada buffer window ke DB.");
  console.log("===================================================================\n");
  process.exit(0);
}

runDemo();
