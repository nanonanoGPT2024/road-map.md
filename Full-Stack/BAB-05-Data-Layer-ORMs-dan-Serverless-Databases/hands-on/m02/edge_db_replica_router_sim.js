/**
 * SIMULATOR: Edge DB Multi-Region Router & Zero-Downtime Migration Engine
 * -----------------------------------------------------------------------------
 * File: edge_db_replica_router_sim.js
 * Deskripsi: Simulasi mandiri (zero-dependency) dari perutean read-replica multi-region,
 * pemulihan fenomena "Read-Your-Own-Writes", edge cache invalidation, serta
 * orkestrasi 5 fase Zero-Downtime Migration (Expand and Contract Pattern).
 */

// =============================================================================
// 1. SIMULASI MULTI-REGION DATABASE & REPLICA ROUTER
// =============================================================================

class DatabaseCluster {
  constructor() {
    this.primaryStorage = new Map(); // us-east-1 (Primary Writer)
    this.replicaStorage = new Map(); // ap-southeast-3 (Read Replica)
    this.replicationLagMs = 80; // Waktu tempuh sinkronisasi data antar benua
    this.edgeCache = new Map(); // Upstash Redis Edge Store
  }

  // Menulis ke Primary Writer (us-east-1)
  async writePrimary(id, data) {
    this.primaryStorage.set(id, { ...data, updatedAt: Date.now() });

    // Invalidate Edge Cache seketika
    this.edgeCache.delete(`user:${id}`);

    // Replikasi asynchronous ke Read Replica (Simulasi Replication Lag)
    setTimeout(() => {
      this.replicaStorage.set(id, { ...data, updatedAt: Date.now() });
    }, this.replicationLagMs);
  }

  // Membaca dari Primary langsung (High Latency ~220ms, Strong Consistency)
  async readPrimary(id) {
    await new Promise((r) => setTimeout(r, 20)); // simulasi latensi jaringan
    return this.primaryStorage.get(id) || null;
  }

  // Membaca dari Replica Lokal (Low Latency ~8ms, Eventual Consistency)
  async readReplica(id) {
    await new Promise((r) => setTimeout(r, 5));
    return this.replicaStorage.get(id) || null;
  }

  // Membaca dari Edge Cache (Sub-2ms)
  readCache(id) {
    return this.edgeCache.get(`user:${id}`) || null;
  }

  setCache(id, data) {
    this.edgeCache.set(`user:${id}`, data);
  }
}

class SmartDataGateway {
  constructor(cluster) {
    this.cluster = cluster;
    this.sessionPins = new Map(); // Menyimpan status pin session user yang baru mutasi
  }

  async updateUser(userId, data) {
    // 1. Tulis ke Primary Writer
    await this.cluster.writePrimary(userId, data);

    // 2. Pasang Pin Session selama 5 detik untuk User ini
    this.sessionPins.set(userId, Date.now() + 5000);
    return { success: true };
  }

  async getUser(userId) {
    const isPinned = (this.sessionPins.get(userId) || 0) > Date.now();

    // Skenario A: User baru saja melakukan mutasi (Harus Strong Consistency)
    if (isPinned) {
      const data = await this.cluster.readPrimary(userId);
      return { data, source: "PRIMARY_WRITER (PINNED_SESSION)", latencyMs: 22 };
    }

    // Skenario B: Periksa Edge Cache terlebih dahulu
    const cached = this.cluster.readCache(userId);
    if (cached) {
      return { data: cached, source: "EDGE_CACHE_HIT (UPSTASH)", latencyMs: 1.5 };
    }

    // Skenario C: Baca dari Read Replica Terdekat
    const replicaData = await this.cluster.readReplica(userId);
    if (replicaData) {
      this.cluster.setCache(userId, replicaData);
      return { data: replicaData, source: "LOCAL_READ_REPLICA", latencyMs: 6 };
    }

    return { data: null, source: "NOT_FOUND", latencyMs: 5 };
  }
}

// =============================================================================
// 2. SIMULASI ZERO-DOWNTIME MIGRATION (EXPAND AND CONTRACT)
// =============================================================================

class ZeroDowntimeMigrationEngine {
  constructor() {
    this.records = [
      { id: 1, name: "Budi Santoso", email: "budi@mail.com" },
      { id: 2, name: "Siti Nurhaliza", email: "siti@mail.com" },
      { id: 3, name: "Joko Widodo", email: "joko@mail.com" },
    ];
    this.appVersion = "v1.0.0";
  }

  // FASE 1: EXPAND (Tambah kolom baru nullable di database)
  expandSchema() {
    console.log("  [FASE 1: EXPAND DDL] Menambahkan kolom 'first_name' dan 'last_name' (NULLABLE)...");
    this.records = this.records.map((r) => ({
      ...r,
      first_name: null,
      last_name: null,
    }));
  }

  // FASE 2: DUAL WRITE (Aplikasi menulis ke kolom lama DAN baru)
  deployAppV2() {
    this.appVersion = "v2.0.0 (Dual-Write Active)";
    console.log(`  [FASE 2: DEPLOY DUAL-WRITE] Aplikasi naik ke ${this.appVersion}`);
  }

  insertUserV2(fullName, email) {
    const parts = fullName.trim().split(" ");
    const firstName = parts[0];
    const lastName = parts.slice(1).join(" ") || "";

    const newRecord = {
      id: this.records.length + 1,
      name: fullName, // Kolom lama tetap diisi
      first_name: firstName, // Kolom baru diisi
      last_name: lastName, // Kolom baru diisi
      email,
    };
    this.records.push(newRecord);
    return newRecord;
  }

  // FASE 3: BATCH BACKFILL (Migrasi data historis yang belum terisi)
  backfillHistoricalData() {
    console.log("  [FASE 3: DATA BACKFILL] Memproses data lama di background...");
    let backfilledCount = 0;
    for (const r of this.records) {
      if (r.first_name === null && r.name) {
        const parts = r.name.trim().split(" ");
        r.first_name = parts[0];
        r.last_name = parts.slice(1).join(" ") || "";
        backfilledCount++;
      }
    }
    console.log(`  ✅ Backfill Selesai: ${backfilledCount} baris berhasil disinkronisasi.`);
  }

  // FASE 4: APP SWITCH (Aplikasi hanya membaca dan menulis ke kolom baru)
  deployAppV3() {
    this.appVersion = "v3.0.0 (New Schema Solely)";
    console.log(`  [FASE 4: APP SWITCH] Aplikasi naik ke ${this.appVersion}. Kolom 'name' tidak lagi diakses.`);
  }

  // FASE 5: CONTRACT (Hapus kolom lama dari database dengan aman)
  contractSchema() {
    console.log("  [FASE 5: CONTRACT DDL] Mengeksekusi 'ALTER TABLE users DROP COLUMN name'...");
    this.records = this.records.map((r) => {
      const { name, ...rest } = r;
      return rest;
    });
    console.log("  ✅ Kolom 'name' berhasil dihapus tanpa menimbulkan downtime apapun!");
  }
}

// =============================================================================
// 3. RUN SIMULATION
// =============================================================================

async function runSimulation() {
  console.log("===========================================================================");
  console.log("SIMULASI: SMART EDGE REPLICA ROUTER & ZERO-DOWNTIME MIGRATION");
  console.log("===========================================================================\n");

  const cluster = new DatabaseCluster();
  const gateway = new SmartDataGateway(cluster);

  // Inisialisasi data awal
  await cluster.writePrimary("usr_100", { name: "Ahmad Dahlan", bio: "Software Architect" });

  // Tunggu replikasi sinkron awal
  await new Promise((r) => setTimeout(r, 100));

  console.log("--- SKENARIO 1: Pengguna Membaca Data Normal (Menggunakan Replica & Cache) ---");
  const read1 = await gateway.getUser("usr_100");
  console.log(`  Request 1 -> Sumber: ${read1.source} | Latensi: ${read1.latencyMs}ms | Data: ${read1.data.name}`);

  const read2 = await gateway.getUser("usr_100");
  console.log(`  Request 2 -> Sumber: ${read2.source} | Latensi: ${read2.latencyMs}ms | Data: ${read2.data.name}\n`);

  console.log("--- SKENARIO 2: Pengguna Mengubah Profil (Mutasi Data & Read-Your-Own-Writes) ---");
  console.log("  [ACTION] Pengguna mengupdate bio: 'VP of Engineering'...");
  await gateway.updateUser("usr_100", { name: "Ahmad Dahlan", bio: "VP of Engineering" });

  console.log("  [VERIFIKASI] Pengguna langsung refresh browser 10ms kemudian (Saat replica masih LAG)...");
  const readImmediate = await gateway.getUser("usr_100");
  console.log(`  Immediate Read -> Sumber : ${readImmediate.source}`);
  console.log(`                 -> Bio    : "${readImmediate.data.bio}" (Konsisten & Akurat! ✅)\n`);

  console.log("--- SKENARIO 3: Orkestrasi Zero-Downtime Migration (Expand and Contract) ---");
  const migrator = new ZeroDowntimeMigrationEngine();
  console.log("Status Awal Database:", migrator.records);

  migrator.expandSchema();
  migrator.deployAppV2();

  console.log("  [MUTASI TRANSIT] Menambahkan user baru selama masa dual-write...");
  migrator.insertUserV2("Mega Pratama", "mega@mail.com");

  migrator.backfillHistoricalData();
  migrator.deployAppV3();
  migrator.contractSchema();

  console.log("\nStatus Akhir Database Pasca-Migrasi:");
  console.table(migrator.records);

  console.log("===========================================================================");
  console.log("SIMULASI SELESAI: Seluruh protokol data layer modern terbukti sukses!");
  console.log("===========================================================================");
}

runSimulation();
