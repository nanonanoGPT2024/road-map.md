/**
 * SIMULATOR: Service Worker Cache Engine & Offline-First Background Sync Queue
 * -----------------------------------------------------------------------------
 * File: service_worker_offline_sync_sim.js
 * Deskripsi: Simulasi mandiri (zero-dependency) dari proxy jaringan Service Worker,
 * strategi caching (Cache-First, Network-First, Stale-While-Revalidate),
 * antrean mutasi IndexedDB saat offline, dan pemulihan otomatis via Background Sync.
 */

// =============================================================================
// 1. SIMULATOR BROWSER CACHE STORAGE API
// =============================================================================

class MockCacheStorage {
  constructor() {
    this.storage = new Map();
  }

  async open(cacheName) {
    if (!this.storage.has(cacheName)) {
      this.storage.set(cacheName, new Map());
    }
    const bucket = this.storage.get(cacheName);
    return {
      match: async (url) => bucket.get(url) || null,
      put: async (url, response) => bucket.set(url, { ...response, cachedAt: Date.now() }),
      delete: async (url) => bucket.delete(url),
      keys: async () => Array.from(bucket.keys()),
    };
  }
}

// =============================================================================
// 2. SIMULATOR OFFLINE-FIRST INDEXEDDB OUTBOX QUEUE
// =============================================================================

class MockIndexedDBOutbox {
  constructor() {
    this.queue = [];
  }

  addMutation(action) {
    const entry = {
      id: `mut_${Date.now()}_${Math.random().toString(36).substring(7)}`,
      ...action,
      queuedAt: new Date().toISOString(),
    };
    this.queue.push(entry);
    return entry;
  }

  getPending() {
    return [...this.queue];
  }

  remove(id) {
    this.queue = this.queue.filter((m) => m.id !== id);
  }

  clear() {
    this.queue = [];
  }
}

// =============================================================================
// 3. SERVICE WORKER PROGRAMMABLE PROXY ENGINE
// =============================================================================

class ServiceWorkerProxy {
  constructor(caches, outbox) {
    this.caches = caches;
    this.outbox = outbox;
    this.isOnline = true; // Status jaringan global
    this.serverDatabase = {
      notes: [
        { id: 1, title: "Catatan Pembuka", author: "Budi" },
      ],
    };
  }

  // Intersepsi Request (Event 'fetch')
  async handleFetch(url, options = {}) {
    const method = options.method || "GET";

    // 1. Strategi Cache-First (Untuk Aset Statis Ber-hash)
    if (url.startsWith("/static/")) {
      const cache = await this.caches.open("static-v1");
      const cached = await cache.match(url);
      if (cached) {
        return { status: 200, source: "CACHE_HIT (0.2ms)", data: cached.body };
      }

      // Jika miss, ambil dari jaringan
      if (!this.isOnline) throw new Error("Offline: Aset tidak tersedia di cache");
      const networkData = `// Content of ${url}`;
      await cache.put(url, { body: networkData });
      return { status: 200, source: "NETWORK_FETCH_THEN_CACHED", data: networkData };
    }

    // 2. Strategi Network-First (Untuk Data Profil Pengguna)
    if (url === "/api/profile") {
      const cache = await this.caches.open("profile-v1");
      if (this.isOnline) {
        const freshData = { name: "Budi Santoso", status: "Online", updated: Date.now() };
        await cache.put(url, { body: freshData });
        return { status: 200, source: "NETWORK_FRESH", data: freshData };
      } else {
        // Fallback ke Cache saat Offline
        const cached = await cache.match(url);
        if (cached) {
          return { status: 200, source: "CACHE_FALLBACK (OFFLINE)", data: cached.body };
        }
        throw new Error("Offline: Profil tidak tersedia di cache lokal");
      }
    }

    // 3. Strategi Stale-While-Revalidate (Untuk Feed Catatan)
    if (url === "/api/notes" && method === "GET") {
      const cache = await this.caches.open("notes-v1");
      const cached = await cache.match(url);

      // Revalidate di background jika online
      if (this.isOnline) {
        const freshNotes = [...this.serverDatabase.notes];
        await cache.put(url, { body: freshNotes });
      }

      if (cached) {
        return { status: 200, source: "CACHE_STALE_INSTANT", data: cached.body };
      }

      return { status: 200, source: "NETWORK_FRESH_FIRST_LOAD", data: this.serverDatabase.notes };
    }

    // 4. Mutasi POST saat Offline (Ditampung di IndexedDB Outbox)
    if (url === "/api/notes" && method === "POST") {
      const payload = options.body;

      if (!this.isOnline) {
        // Simpan ke antrean IndexedDB
        const queued = this.outbox.addMutation({ endpoint: url, payload });
        return {
          status: 202,
          source: "INDEXED_DB_OUTBOX (OFFLINE QUEUED)",
          data: { ...payload, id: `temp_${Date.now()}`, isOptimistic: true },
        };
      }

      // Jika online, langsung simpan ke database server
      const newNote = { id: this.serverDatabase.notes.length + 1, ...payload };
      this.serverDatabase.notes.push(newNote);
      return { status: 201, source: "SERVER_SAVED_DIRECT", data: newNote };
    }

    return { status: 404, source: "NOT_FOUND" };
  }

  // Trigger Event 'sync' (Background Sync saat internet kembali aktif)
  async processBackgroundSync() {
    console.log("  [SYNC EVENT] Memulai Background Sync untuk antrean tertunda...");
    const pending = this.outbox.getPending();
    if (pending.length === 0) {
      console.log("  Tidak ada antrean tertunda.");
      return;
    }

    for (const item of pending) {
      console.log(`  🔄 Mengirimkan mutasi tertunda ID: ${item.id} -> ${item.endpoint}...`);
      const newNote = { id: this.serverDatabase.notes.length + 1, ...item.payload };
      this.serverDatabase.notes.push(newNote);
      this.outbox.remove(item.id);
    }

    console.log("  ✅ Seluruh antrean IndexedDB berhasil disinkronkan ke server!");
    console.log("  🔔 [SIMULASI WEB PUSH] Notifikasi: 'Semua catatan offline berhasil disinkronkan ke cloud!'");
  }
}

// =============================================================================
// 4. RUN SUITE
// =============================================================================

async function runSuite() {
  console.log("===========================================================================");
  console.log("SIMULASI: SERVICE WORKER CACHING & OFFLINE-FIRST BACKGROUND SYNC");
  console.log("===========================================================================\n");

  const caches = new MockCacheStorage();
  const outbox = new MockIndexedDBOutbox();
  const sw = new ServiceWorkerProxy(caches, outbox);

  // SKENARIO 1: STRATEGI CACHING SAAT KONEKSI NORMAL
  console.log("--- SKENARIO 1: Strategi Caching Normal (Online) ---");
  // A. Cache-First (Asset statis)
  const asset1 = await sw.handleFetch("/static/bundle-a8f9d.js");
  console.log(`  Aset Statis (Panggilan 1) -> Sumber: ${asset1.source}`);
  const asset2 = await sw.handleFetch("/static/bundle-a8f9d.js");
  console.log(`  Aset Statis (Panggilan 2) -> Sumber: ${asset2.source}`);

  // B. Network-First
  const prof1 = await sw.handleFetch("/api/profile");
  console.log(`  Profil Data (Panggilan 1) -> Sumber: ${prof1.source} | Nama: ${prof1.data.name}`);

  // C. Stale-While-Revalidate
  const notes1 = await sw.handleFetch("/api/notes");
  console.log(`  Daftar Feed (Panggilan 1) -> Sumber: ${notes1.source} | Jumlah: ${notes1.data.length}\n`);

  // SKENARIO 2: PENGGUNA MEMASUKI KONDISI OFFLINE (KONEKSI TERPUTUS)
  console.log("--- SKENARIO 2: Internet Terputus (Airplane Mode / No Connection) ---");
  sw.isOnline = false;
  console.log("  📶 Status Jaringan: OFFLINE ❌");

  // A. Membaca profil yang sudah pernah di-cache
  const profOffline = await sw.handleFetch("/api/profile");
  console.log(`  Baca Profil Saat Offline   -> Sumber: ${profOffline.source} | Data: ${profOffline.data.name}`);

  // B. Menulis data baru saat offline (Offline Mutation)
  console.log("  [ACTION] Pengguna membuat Catatan 1 saat offline...");
  const mut1 = await sw.handleFetch("/api/notes", {
    method: "POST",
    body: { title: "Ide Fitur AI di Kereta Bawah Tanah", author: "Budi" },
  });
  console.log(`  Status Simpan: ${mut1.source} | Optimistic ID: ${mut1.data.id}`);

  console.log("  [ACTION] Pengguna membuat Catatan 2 saat offline...");
  const mut2 = await sw.handleFetch("/api/notes", {
    method: "POST",
    body: { title: "Daftar Belanja Akhir Pekan", author: "Budi" },
  });
  console.log(`  Status Simpan: ${mut2.source} | Optimistic ID: ${mut2.data.id}`);
  console.log(`  Total Item di IndexedDB Outbox: ${outbox.getPending().length} item tertunda.\n`);

  // SKENARIO 3: KONEKSI PULIH & BACKGROUND SYNC BERJALAN
  console.log("--- SKENARIO 3: Sinyal Internet Kembali Pulih (Online) ---");
  sw.isOnline = true;
  console.log("  📶 Status Jaringan: ONLINE ✅");

  // Browser memicu event 'sync'
  await sw.processBackgroundSync();

  // Verifikasi isi database server akhir
  console.log("\nStatus Akhir Catatan di Server Database:");
  console.table(sw.serverDatabase.notes);

  console.log("===========================================================================");
  console.log("SIMULASI SELESAI: Arsitektur PWA & Offline-First Terbukti Tangguh!");
  console.log("===========================================================================");
}

runSuite();
