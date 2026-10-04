// database_sharding_router.js
// Simulator Arsitektur Database Sharding: Range vs Hash Sharding, Hotspot Detection, & Scatter-Gather

class ShardNode {
  constructor(id, name) {
    this.id = id;
    this.name = name;
    this.storage = [];
  }

  insert(record) {
    this.storage.push(record);
  }

  query(predicate) {
    return this.storage.filter(predicate);
  }
}

class ShardedDatabaseCluster {
  constructor(numShards = 3) {
    this.numShards = numShards;
    this.hashShards = Array.from({ length: numShards }, (_, i) => new ShardNode(i, `Hash-Shard-${i + 1}`));
    this.rangeShards = Array.from({ length: numShards }, (_, i) => new ShardNode(i, `Range-Shard-${i + 1}`));
  }

  // Sederhana string hash generator
  _hash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = (hash << 5) - hash + str.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash);
  }

  // 1. Ingestion menggunakan Range-Based Sharding
  insertRange(userId, record) {
    // Range: Shard 1 (1-100), Shard 2 (101-200), Shard 3 (201-300)
    let shardIndex = 0;
    if (userId > 100 && userId <= 200) shardIndex = 1;
    else if (userId > 200) shardIndex = 2;

    this.rangeShards[shardIndex].insert({ userId, ...record });
  }

  // 2. Ingestion menggunakan Hash-Based Sharding
  insertHash(userId, record) {
    const shardIndex = this._hash(userId.toString()) % this.numShards;
    this.hashShards[shardIndex].insert({ userId, ...record });
  }

  // Query Bertarget (Targeted Query): Membawa Sharding Key (Cepat!)
  queryTargeted(userId) {
    const startTime = Date.now();
    const shardIndex = this._hash(userId.toString()) % this.numShards;
    const targetShard = this.hashShards[shardIndex];

    const results = targetShard.query(r => r.userId === userId);
    return {
      type: "Targeted Single-Shard Query",
      searchedShards: [targetShard.name],
      resultsCount: results.length,
      latencyMs: Date.now() - startTime + 1 // ~1ms
    };
  }

  // Scatter-Gather Query: Tanpa Sharding Key (Mahal!)
  queryScatterGather(status) {
    const startTime = Date.now();
    const searchedShards = [];
    let aggregatedResults = [];

    // Kirim query ke SELURUH shard secara bersamaan (Scatter)
    this.hashShards.forEach(shard => {
      searchedShards.push(shard.name);
      const matches = shard.query(r => r.status === status);
      aggregatedResults = aggregatedResults.concat(matches); // Gather
    });

    return {
      type: "Scatter-Gather Multi-Shard Query",
      searchedShards,
      resultsCount: aggregatedResults.length,
      latencyMs: Date.now() - startTime + 15 // Menunggu seluruh shard selesai (~15ms)
    };
  }
}

function runDemo() {
  console.log("===================================================================");
  console.log("     SIMULATOR DATABASE SHARDING: RANGE vs HASH & SCATTER-GATHER   ");
  console.log("===================================================================\n");

  const cluster = new ShardedDatabaseCluster(3);

  // BAGIAN 1: Memasukkan 150 User Baru Berurutan (ID 201 s/d 350)
  console.log("--- 1. SIMULASI DETEKSI HOT SHARD PADA PENDAFTARAN USER BARU ---");
  console.log("Memasukkan 150 user baru berurutan (ID: 201 s/d 350)...");

  for (let id = 201; id <= 350; id++) {
    const userRecord = { name: `User_${id}`, status: id % 3 === 0 ? "VIP" : "REGULAR" };
    cluster.insertRange(id, userRecord);
    cluster.insertHash(id, userRecord);
  }

  console.log("\n[HASIL DISTRIBUSI PENYIMPANAN DATA]:");
  console.log("A. Range-Based Sharding (Rentan Hot Shard):");
  cluster.rangeShards.forEach(s => {
    console.log(` - ${s.name.padEnd(16, ' ')} : ${s.storage.length} baris data ${s.storage.length > 100 ? '(🔥 HOT SHARD OVERLOAD!)' : '(Sepi / Menganggur)'}`);
  });

  console.log("\nB. Hash-Based Sharding (Persebaran Merata):");
  cluster.hashShards.forEach(s => {
    console.log(` - ${s.name.padEnd(16, ' ')} : ${s.storage.length} baris data (✅ Seimbang Terdistribusi)`);
  });

  // BAGIAN 2: Komparasi Targeted Query vs Scatter-Gather
  console.log("\n===================================================================");
  console.log("--- 2. KOMPARASI TARGETED QUERY vs SCATTER-GATHER QUERY ---");
  console.log("===================================================================");

  // A. Query Bertarget (Ada User ID)
  console.log("A. Eksekusi: SELECT * FROM users WHERE user_id = 245;");
  const targeted = cluster.queryTargeted(245);
  console.log(` - Tipe Query      : ${targeted.type}`);
  console.log(` - Shard Diperiksa : [ ${targeted.searchedShards.join(', ')} ] (Hanya 1 Shard!)`);
  console.log(` - Latensi         : ~${targeted.latencyMs} ms`);

  // B. Query Tanpa Sharding Key (Mencari berdasarkan status)
  console.log("\nB. Eksekusi: SELECT * FROM users WHERE status = 'VIP';");
  const scatter = cluster.queryScatterGather("VIP");
  console.log(` - Tipe Query      : ${scatter.type}`);
  console.log(` - Shard Diperiksa : [ ${scatter.searchedShards.join(', ')} ] (SELURUH SHARD!)`);
  console.log(` - Total Ditemukan : ${scatter.resultsCount} data VIP`);
  console.log(` - Latensi         : ~${scatter.latencyMs} ms (Menunggu agregasi seluruh node)`);

  console.log("\n===================================================================");
  console.log(" [KESIMPULAN ARSITEKTURAL]:");
  console.log(" 1. Range Sharding menciptakan Hot Shard jika data bertambah berurutan.");
  console.log(" 2. Hash Sharding membagi beban data secara adil ke seluruh server.");
  console.log(" 3. Query tanpa Sharding Key (Scatter-Gather) membebani 100% server cluster.");
  console.log("===================================================================\n");
}

runDemo();
