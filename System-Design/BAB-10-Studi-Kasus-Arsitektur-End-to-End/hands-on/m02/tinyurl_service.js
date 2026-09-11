/**
 * LAB SIMULATION: End-to-End TinyURL Service with KGS & Cache-Aside
 * 
 * Komponen:
 * 1. Base62 Converter Engine.
 * 2. Key Generation Service (KGS) - Pre-allocated non-colliding key pool.
 * 3. Database Store (NoSQL Key-Value simulation).
 * 4. In-Memory Redis Cache-Aside Layer.
 * 5. Asynchronous Click Analytics Counter.
 */

const BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

// 1. KEY GENERATION SERVICE (KGS)
class KeyGenerationService {
  constructor(poolSize = 100) {
    this.keyPool = [];
    this.currentSeed = 10000000; // Mulai dari ID 10 juta untuk memastikan 7 digit
    this.generatePool(poolSize);
  }

  idToBase62(num) {
    let str = "";
    while (num > 0) {
      str = BASE62[num % 62] + str;
      num = Math.floor(num / 62);
    }
    return str.padStart(7, "0");
  }

  generatePool(count) {
    for (let i = 0; i < count; i++) {
      this.currentSeed += Math.floor(Math.random() * 5) + 1; // Random increment untuk unguessable keys
      this.keyPool.push(this.idToBase62(this.currentSeed));
    }
  }

  getUniqueKey() {
    if (this.keyPool.length === 0) {
      this.generatePool(50); // Re-fill pool jika habis
    }
    return this.keyPool.shift(); // O(1) fetch dari RAM
  }
}

// 2. TINYURL CORE SERVICE
class TinyUrlService {
  constructor() {
    this.kgs = new KeyGenerationService(50);
    this.database = new Map(); // short_key -> { longUrl, createdAt, clicks }
    this.cache = new Map();    // Redis Cache-Aside: short_key -> longUrl
    this.stats = { totalRequests: 0, cacheHits: 0, cacheMisses: 0 };
  }

  // WRITE PATH: Buat URL Pendek
  shorten(longUrl, customAlias = null) {
    let shortKey;

    if (customAlias) {
      if (this.database.has(customAlias)) {
        throw new Error(`Conflict: Alias '${customAlias}' sudah digunakan!`);
      }
      shortKey = customAlias;
    } else {
      // Ambil key pre-generated dari KGS
      shortKey = this.kgs.getUniqueKey();
    }

    const record = {
      shortKey,
      longUrl,
      createdAt: new Date().toISOString(),
      clicks: 0
    };

    // Simpan ke Database
    this.database.set(shortKey, record);

    // Pre-warm Cache (Opsional tapi Best Practice)
    this.cache.set(shortKey, longUrl);

    return {
      shortUrl: `https://tiny.url/${shortKey}`,
      shortKey,
      longUrl
    };
  }

  // READ PATH: Redirect & Analitik (High QPS)
  redirect(shortKey) {
    this.stats.totalRequests += 1;

    // 1. Cek Redis Cache
    if (this.cache.has(shortKey)) {
      this.stats.cacheHits += 1;
      this.recordClickAsync(shortKey);
      return {
        statusCode: 302,
        location: this.cache.get(shortKey),
        source: "CACHE_HIT (0.2ms)"
      };
    }

    // 2. Cache Miss: Query Database
    this.stats.cacheMisses += 1;
    if (!this.database.has(shortKey)) {
      return { statusCode: 404, error: "Tautan tidak ditemukan!" };
    }

    const record = this.database.get(shortKey);
    // Simpan ke cache untuk request berikutnya
    this.cache.set(shortKey, record.longUrl);
    this.recordClickAsync(shortKey);

    return {
      statusCode: 302,
      location: record.longUrl,
      source: "DB_LOOKUP_AND_CACHED (8.5ms)"
    };
  }

  // Asynchronous Click Analytics (Fire-and-forget)
  recordClickAsync(shortKey) {
    setTimeout(() => {
      const record = this.database.get(shortKey);
      if (record) {
        record.clicks += 1;
      }
    }, 10);
  }
}

// ======================= PENGUJIAN SKENARIO =======================
const service = new TinyUrlService();

console.log("===================================================================");
console.log("🛠️  PENGUJIAN 1: PEMBUATAN URL PENDEK DENGAN KGS");
console.log("===================================================================\n");

const url1 = service.shorten("https://tokopedia.com/promo/flash-sale-gadget-september-2026?ref=ads");
console.log(`URL Asli: ${url1.longUrl}`);
console.log(`URL Pendek Diterbitkan: ${url1.shortUrl} (Key: ${url1.shortKey})\n`);

const url2 = service.shorten("https://github.com/torvalds/linux", "torvalds-repo");
console.log(`URL dengan Custom Alias: ${url2.shortUrl}\n`);

console.log("===================================================================");
console.log("🛠️  PENGUJIAN 2: READ PATH (CACHE HIT VS CACHE MISS)");
console.log("===================================================================\n");

// Simulasi evict cache untuk url1 agar menguji Cache Miss
service.cache.delete(url1.shortKey);

console.log("-> Kunjungan Pertama setelah Cache Eviction (Harus Cache Miss):");
console.log(service.redirect(url1.shortKey));

console.log("\n-> Kunjungan Kedua (Harus Cache Hit dari Redis):");
console.log(service.redirect(url1.shortKey));

console.log("\n-> Kunjungan Ketiga (Harus Cache Hit dari Redis):");
console.log(service.redirect(url1.shortKey));

// Tunggu sejenak agar background async analytics selesai dihitung
setTimeout(() => {
  console.log("\n===================================================================");
  console.log("📊 METRIK PERFORMA & ANALITIK");
  console.log("===================================================================");
  const cacheHitRatio = ((service.stats.cacheHits / service.stats.totalRequests) * 100).toFixed(1);
  console.log(`Total Redirect Requests: ${service.stats.totalRequests}`);
  console.log(`Cache Hits: ${service.stats.cacheHits} (${cacheHitRatio}%)`);
  console.log(`Cache Misses: ${service.stats.cacheMisses}`);
  console.log(`Total Klik Terdata pada '${url1.shortKey}': ${service.database.get(url1.shortKey).clicks} kali`);

  console.log("\n Kesimpulan:");
  console.log("1. KGS menerbitkan kunci 7 karakter unik tanpa resiko collision hashing.");
  console.log("2. Lapisan Redis Cache-Aside menyerap mayoritas trafik baca dengan respon sub-milidetik.");
  console.log("3. Analisis klik dicatat secara asinkron tanpa membebani latensi user redirect (HTTP 302).");
}, 100);
