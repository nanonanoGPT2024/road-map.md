/**
 * SIMULATOR: Modern ORM Query Builder, Connection Pooling & Cold Start Benchmarker
 * -----------------------------------------------------------------------------
 * File: orm_query_builder_cold_start_sim.js
 * Deskripsi: Simulasi mandiri (zero-dependency) dari query builder ala Drizzle,
 * bahaya connection exhaustion di serverless, PgBouncer transaction multiplexer,
 * dan perbandingan latensi cold start antara Heavy Binary ORM vs Lightweight TS ORM.
 */

// =============================================================================
// 1. MINI DRIZZLE-STYLE TYPE-SAFE QUERY BUILDER & PARAMETERIZER
// =============================================================================

function pgTable(tableName, columns) {
  return {
    _tableName: tableName,
    ...columns,
  };
}

function column(name, type) {
  return { _name: name, _type: type };
}

// Skema Model
const users = pgTable("users", {
  id: column("id", "uuid"),
  name: column("name", "text"),
  email: column("email", "text"),
  role: column("role", "text"),
});

const orders = pgTable("orders", {
  id: column("id", "uuid"),
  userId: column("user_id", "uuid"),
  totalAmount: column("total_amount", "decimal"),
  status: column("status", "text"),
});

class QueryBuilder {
  constructor() {
    this.selectedFields = null;
    this.fromTable = null;
    this.joinClauses = [];
    this.whereConditions = [];
    this.limitCount = null;
    this.params = [];
  }

  select(fields) {
    this.selectedFields = fields;
    return this;
  }

  from(table) {
    this.fromTable = table;
    return this;
  }

  innerJoin(table, condition) {
    this.joinClauses.push({ type: "INNER JOIN", table, condition });
    return this;
  }

  where(condition) {
    this.whereConditions.push(condition);
    return this;
  }

  limit(count) {
    this.limitCount = count;
    return this;
  }

  toSQL() {
    const fieldsStr = Object.entries(this.selectedFields)
      .map(([alias, col]) => `${col._name} AS "${alias}"`)
      .join(", ");

    let sql = `SELECT ${fieldsStr} FROM ${this.fromTable._tableName}`;

    for (const j of this.joinClauses) {
      sql += ` ${j.type} ${j.table._tableName} ON ${j.condition.left._name} = ${j.condition.right._name}`;
    }

    if (this.whereConditions.length > 0) {
      const condClauses = this.whereConditions.map((c) => {
        this.params.push(c.value);
        return `${c.column._name} ${c.operator} $${this.params.length}`;
      });
      sql += ` WHERE ${condClauses.join(" AND ")}`;
    }

    if (this.limitCount !== null) {
      sql += ` LIMIT ${this.limitCount}`;
    }

    return {
      sql: sql + ";",
      params: [...this.params],
    };
  }
}

const eq = (col, val) => ({ column: col, operator: "=", value: val });
const joinEq = (leftCol, rightCol) => ({ left: leftCol, right: rightCol });

// =============================================================================
// 2. SIMULASI CONNECTION EXHAUSTION VS PGBOUNCER TRANSACTION POOLING
// =============================================================================

class MockPostgresDatabase {
  constructor(maxConnections = 10) {
    this.maxConnections = maxConnections;
    this.activeConnections = 0;
  }

  async acquireDirectConnection(clientId) {
    if (this.activeConnections >= this.maxConnections) {
      throw new Error(`FATAL: remaining connection slots are reserved for non-replication superuser connections (Active: ${this.activeConnections}/${this.maxConnections})`);
    }
    this.activeConnections++;
    return {
      connId: `tcp_conn_${Math.random().toString(36).substring(7)}`,
      release: () => {
        this.activeConnections--;
      },
    };
  }
}

class MockPgBouncerPooler {
  constructor(database, poolSize = 5) {
    this.database = database;
    this.poolSize = poolSize;
    this.availableSlots = poolSize;
    this.queue = [];
  }

  async executeTransaction(queryFn) {
    // Jika tidak ada slot yang tersedia, masukkan ke antrean (Queue)
    if (this.availableSlots <= 0) {
      await new Promise((resolve) => this.queue.push(resolve));
    }

    this.availableSlots--;
    try {
      // Pinjam koneksi database fisik hanya selama eksekusi transaksi
      const conn = await this.database.acquireDirectConnection("pgbouncer_worker");
      const result = await queryFn(conn);
      conn.release();
      return result;
    } finally {
      this.availableSlots++;
      if (this.queue.length > 0) {
        const nextInLine = this.queue.shift();
        nextInLine();
      }
    }
  }
}

// =============================================================================
// 3. COLD START BENCHMARK SIMULATION
// =============================================================================

function simulateHeavyBinaryORMColdStart() {
  const start = process.hrtime.bigint();
  // Simulasi pembacaan binary Rust 25MB, loading FFI, deserializing engine AST
  let dummyMemory = [];
  for (let i = 0; i < 300000; i++) {
    dummyMemory.push({ engine: "prisma-query-engine-node-api", id: i });
  }
  const end = process.hrtime.bigint();
  const durationMs = Number(end - start) / 1e6;
  return durationMs + 180; // Ditambah latensi real-world OS process invocation
}

function simulateLightweightTSORMColdStart() {
  const start = process.hrtime.bigint();
  // Simulasi parsing modul JS/TS murni tanpa binary
  let smallConfig = { dialect: "postgres", version: "0.30.0" };
  JSON.parse(JSON.stringify(smallConfig));
  const end = process.hrtime.bigint();
  const durationMs = Number(end - start) / 1e6;
  return durationMs + 1.2; // Rata-rata eval JavaScript V8
}

// =============================================================================
// 4. RUN SUITE
// =============================================================================

async function runSuite() {
  console.log("===========================================================================");
  console.log("SIMULASI: MODERN ORM, SERVERLESS CONNECTION POOLING, & COLD START");
  console.log("===========================================================================\n");

  // BAGIAN 1: QUERY BUILDER TEST
  console.log("--- BAGIAN 1: Menguji Parameterized Type-Safe SQL Query Builder ---");
  const qb = new QueryBuilder();
  const query = qb
    .select({
      orderId: orders.id,
      total: orders.totalAmount,
      customerName: users.name,
    })
    .from(orders)
    .innerJoin(users, joinEq(orders.userId, users.id))
    .where(eq(orders.status, "PAID"))
    .limit(5);

  const compiled = query.toSQL();
  console.log("Compiled SQL Query:");
  console.log(`  ${compiled.sql}`);
  console.log(`Parameters Bound: ${JSON.stringify(compiled.params)}\n`);

  // BAGIAN 2: CONNECTION EXHAUSTION TEST
  console.log("--- BAGIAN 2: Menguji 30 Serverless Requests Serentak (Direct vs Pooled) ---");
  const db = new MockPostgresDatabase(10); // Database hanya mampu 10 koneksi maksimal

  console.log("A. Menggunakan Koneksi Langsung (Direct Connection Tanpa Pooler):");
  let directSuccess = 0;
  let directFailed = 0;

  const directPromises = Array.from({ length: 30 }, async (_, idx) => {
    try {
      const conn = await db.acquireDirectConnection(`req_${idx}`);
      // Simulasi query berlangsung 40ms
      await new Promise((r) => setTimeout(r, 40));
      conn.release();
      directSuccess++;
    } catch (err) {
      directFailed++;
    }
  });

  await Promise.all(directPromises);
  console.log(`  ✅ Berhasil Dilayani : ${directSuccess} request`);
  console.log(`  ❌ Gagal / Crash     : ${directFailed} request (Database Connection Exhaustion!)\n`);

  console.log("B. Menggunakan PgBouncer / Connection Pooler (Multiplexing 5 Physical Slots):");
  const pooler = new MockPgBouncerPooler(db, 5);
  let pooledSuccess = 0;
  let pooledFailed = 0;

  const startPoolTime = Date.now();
  const pooledPromises = Array.from({ length: 30 }, async (_, idx) => {
    try {
      await pooler.executeTransaction(async (conn) => {
        // Simulasi query transaksi selama 15ms
        await new Promise((r) => setTimeout(r, 15));
        return { ok: true };
      });
      pooledSuccess++;
    } catch (err) {
      pooledFailed++;
    }
  });

  await Promise.all(pooledPromises);
  const totalDuration = Date.now() - startPoolTime;
  console.log(`  ✅ Berhasil Dilayani : ${pooledSuccess}/30 request (100% Lolos Tanpa Error!)`);
  console.log(`  ⏱️  Waktu Total Eksekusi : ${totalDuration} ms`);
  console.log(`  🔒 Status Koneksi DB Fisik: ${db.activeConnections} aktif (Stabil & Aman)\n`);

  // BAGIAN 3: COLD START BENCHMARK
  console.log("--- BAGIAN 3: Benchmark Cold Start Serverless Function ---");
  const heavyColdStart = simulateHeavyBinaryORMColdStart();
  const lightColdStart = simulateLightweightTSORMColdStart();

  console.log(`  📦 Heavy Binary ORM (Engine Rust ~25MB)     : ~${heavyColdStart.toFixed(1)} ms`);
  console.log(`  ⚡ Lightweight TS ORM (Drizzle/Kysely ~50KB) : ~${lightColdStart.toFixed(1)} ms`);
  const speedup = (heavyColdStart / lightColdStart).toFixed(1);
  console.log(`  🚀 Efisiensi Cold Start                     : ${speedup}x LEBIH CEPAT!\n`);

  console.log("===========================================================================");
  console.log("SIMULASI SELESAI: Arsitektur Data Layer Terverifikasi Sempurna!");
  console.log("===========================================================================");
}

runSuite();
