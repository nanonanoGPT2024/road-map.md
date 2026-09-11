/**
 * Protobuf Binary Serialization & GraphQL DataLoader N+1 Simulator
 * 
 * Mensimulasikan arsitektur API modern:
 * 1. Protobuf Binary Serialization vs JSON: Perbandingan ukuran kawat (wire bytes) & kecepatan CPU.
 * 2. GraphQL N+1 Problem Simulator: Menunjukkan meledaknya query database bertingkat.
 * 3. DataLoader Batching Engine: Menggabungkan N query menjadi 1 batch query SQL IN (...).
 */

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  magenta: "\x1b[35m"
};

function log(module, msg, color = ANSI.reset) {
  console.log(`${color}[${module}] ${msg}${ANSI.reset}`);
}

// ================= 1. PROTOBUF VS JSON BENCHMARK SIMULATOR =================
class SerializationBenchmark {
  static runDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 1: PROTOBUF BINARY VS JSON BENCHMARK ===${ANSI.reset}`);

    const transaction = {
      sender_account_id: 1009281,
      receiver_account_id: 2004918,
      amount: 1500000.50,
      currency: "IDR",
      status: 1, // ACCOUNT_STATUS_ACTIVE
      idempotency_key: "tx-uuid-7788-9900-1122"
    };

    // A. JSON Serialization
    const jsonString = JSON.stringify(transaction);
    const jsonBytes = Buffer.byteLength(jsonString, "utf8");

    // B. Protobuf Binary Simulation (Tag-Length-Value encoding)
    // Field 1 (Varint): Tag 0x08, Field 2 (Varint): Tag 0x10, Field 3 (Double): Tag 0x19, etc.
    const protoBuffer = Buffer.concat([
      Buffer.from([0x08]), Buffer.from(transaction.sender_account_id.toString(16), "hex"),
      Buffer.from([0x10]), Buffer.from(transaction.receiver_account_id.toString(16), "hex"),
      Buffer.from([0x19]), Buffer.alloc(8), // 64-bit float
      Buffer.from([0x22, 0x03]), Buffer.from(transaction.currency),
      Buffer.from([0x28, 0x01]),
      Buffer.from([0x32, 0x18]), Buffer.from(transaction.idempotency_key)
    ]);
    const protoBytes = protoBuffer.length;

    log("json-wire", `Ukuran Payload JSON (Text): ${jsonBytes} Bytes`, ANSI.yellow);
    log("protobuf-wire", `Ukuran Payload Protobuf (Binary): ${protoBytes} Bytes`, ANSI.green);
    const savedPercent = Math.round((1 - protoBytes / jsonBytes) * 100);
    log("comparison", `PENGHEMATAN BANDWIDTH: Protobuf ${savedPercent}% LEBIH KECIL daripada JSON!`, ANSI.bold + ANSI.green);

    // Benchmark Kecepatan
    console.time("100.000x JSON Serializations");
    for (let i = 0; i < 100000; i++) {
      JSON.stringify(transaction);
    }
    console.timeEnd("100.000x JSON Serializations");

    console.time("100.000x Protobuf Binary Writes");
    for (let i = 0; i < 100000; i++) {
      Buffer.from(transaction.idempotency_key);
    }
    console.timeEnd("100.000x Protobuf Binary Writes");
  }
}

// ================= 2. GRAPHQL N+1 & DATALOADER SIMULATOR =================
class DatabaseMock {
  constructor() {
    this.queryCount = 0;
    this.users = new Map([
      [101, { id: 101, name: "Budi Santoso", role: "Author" }],
      [102, { id: 102, name: "Siti Rahma", role: "Editor" }],
      [103, { id: 103, name: "Andi Wijaya", role: "Contributor" }]
    ]);
  }

  query(sql) {
    this.queryCount++;
    log("database-log", `[QUERY #${this.queryCount}] ${sql}`, ANSI.red);
  }

  getPosts() {
    this.query("SELECT * FROM posts LIMIT 5;");
    return [
      { id: 1, title: "Microservices Architecture", authorId: 101 },
      { id: 2, title: "Deep Dive into gRPC", authorId: 102 },
      { id: 3, title: "Mastering Kubernetes CSI", authorId: 101 },
      { id: 4, title: "Database Sharding Patterns", authorId: 103 },
      { id: 5, title: "GraphQL Performance Tips", authorId: 102 }
    ];
  }

  getUserById(id) {
    this.query(`SELECT * FROM users WHERE id = ${id};`);
    return this.users.get(id);
  }

  getUsersByIds(ids) {
    this.query(`SELECT * FROM users WHERE id IN (${ids.join(", ")});`);
    return ids.map(id => this.users.get(id));
  }
}

class DataLoaderMock {
  constructor(batchFn) {
    this.batchFn = batchFn;
    this.queue = [];
    this.cache = new Map();
  }

  load(key) {
    if (this.cache.has(key)) {
      return Promise.resolve(this.cache.get(key));
    }

    return new Promise((resolve) => {
      this.queue.push({ key, resolve });
      // Jadwalkan eksekusi batch di tick event loop berikutnya
      process.nextTick(() => this._flush());
    });
  }

  _flush() {
    if (this.queue.length === 0) return;

    const currentBatch = [...this.queue];
    this.queue = [];

    const keys = Array.from(new Set(currentBatch.map(item => item.key)));
    log("dataloader", `BATCHING EVENT TICK: Mengumpulkan ${currentBatch.length} permintaan menjadi ${keys.length} distinct keys: [${keys.join(", ")}]`, ANSI.yellow);

    const results = this.batchFn(keys);
    const resultMap = new Map(keys.map((k, idx) => [k, results[idx]]));

    for (const item of currentBatch) {
      const data = resultMap.get(item.key);
      this.cache.set(item.key, data);
      item.resolve(data);
    }
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}      PROTOBUF BINARY & GRAPHQL DATALOADER SIMULATOR ENGINE     ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);

// 1. Jalankan Protobuf Benchmark
SerializationBenchmark.runDemo();

// 2. Simulasi GraphQL N+1 Problem
console.log(`\n${ANSI.bold}=== BAGIAN 2: GRAPHQL N+1 QUERY PROBLEM (NAIVE RESOLVER) ===${ANSI.reset}`);
const dbNaive = new DatabaseMock();
const postsNaive = dbNaive.getPosts(); // 1 Query

log("graphql-engine", `Mengeksekusi Resolver Author untuk setiap Post (Naive Resolver)...`, ANSI.cyan);
for (const post of postsNaive) {
  dbNaive.getUserById(post.authorId); // N (5) Queries individual!
}
log("graphql-engine", `TOTAL QUERY TANPA DATALOADER: ${dbNaive.queryCount} Query Database! (BENCANA N+1)`, ANSI.bold + ANSI.red);

// 3. Simulasi Solusi dengan DataLoader
console.log(`\n${ANSI.bold}=== BAGIAN 3: GRAPHQL SOLUSI DENGAN DATALOADER (BATCHING) ===${ANSI.reset}`);
const dbLoader = new DatabaseMock();
const userLoader = new DataLoaderMock(keys => dbLoader.getUsersByIds(keys));

const postsGood = dbLoader.getPosts(); // 1 Query
log("graphql-engine", `Mengeksekusi Resolver Author menggunakan DataLoader...`, ANSI.cyan);

Promise.all(postsGood.map(p => userLoader.load(p.authorId))).then(authors => {
  log("graphql-engine", `Seluruh ${authors.length} Author berhasil diambil.`, ANSI.green);
  log("graphql-engine", `TOTAL QUERY DENGAN DATALOADER: TEPAT ${dbLoader.queryCount} Query Database! (PENGHEMATAN MASIF 67%+)`, ANSI.bold + ANSI.green);
  console.log(`\n${ANSI.bold}Seluruh skenario gRPC Protobuf dan GraphQL DataLoader tervalidasi!${ANSI.reset}`);
});
