// redis_cluster_sim.js
// Simulator Sharding Redis Cluster: 16.384 Hash Slots, CRC16 Hashing, & Hash Tags Grouping

// 1. Implementasi Algoritma CRC16 Standar (Polinomial 0x1021) yang digunakan Redis Cluster
function crc16(str) {
  let crc = 0;
  for (let i = 0; i < str.length; i++) {
    crc = ((crc << 8) ^ crc16Table[((crc >> 8) ^ str.charCodeAt(i)) & 0xFF]) & 0xFFFF;
  }
  return crc;
}

// Precomputed CRC16 Table
const crc16Table = new Uint16Array(256);
for (let i = 0; i < 256; i++) {
  let curr = i << 8;
  for (let j = 0; j < 8; j++) {
    curr = ((curr & 0x8000) !== 0) ? ((curr << 1) ^ 0x1021) : (curr << 1);
  }
  crc16Table[i] = curr & 0xFFFF;
}

// Ekstrak string di dalam Hash Tag {...} jika ada
function getEffectiveKeyForHash(key) {
  const openBracket = key.indexOf('{');
  if (openBracket !== -1) {
    const closeBracket = key.indexOf('}', openBracket + 1);
    if (closeBracket !== -1 && closeBracket > openBracket + 1) {
      return key.substring(openBracket + 1, closeBracket);
    }
  }
  return key; // Tanpa hash tag, hash seluruh string
}

function getSlot(key) {
  const effectiveKey = getEffectiveKeyForHash(key);
  return crc16(effectiveKey) % 16384;
}

// 2. Simulasi Cluster dengan 3 Master Node (Membagi 16.384 Slots)
class RedisClusterSimulator {
  constructor() {
    this.nodes = [
      { name: "Master-Node-1 (Port 7000)", slotRange: [0, 5460], keys: [] },
      { name: "Master-Node-2 (Port 7001)", slotRange: [5461, 10922], keys: [] },
      { name: "Master-Node-3 (Port 7002)", slotRange: [10923, 16383], keys: [] }
    ];
  }

  set(key, value) {
    const slot = getSlot(key);
    const targetNode = this.nodes.find(n => slot >= n.slotRange[0] && slot <= n.slotRange[1]);
    targetNode.keys.push({ key, slot, value });
    return { node: targetNode.name, slot };
  }

  printDistribution() {
    console.log("┌──────────────────────────┬──────────────────────┬─────────────────┐");
    console.log("│ Nama Master Node         │ Rentang Hash Slots   │ Total Kunci     │");
    console.log("├──────────────────────────┼──────────────────────┼─────────────────┤");
    this.nodes.forEach(n => {
      console.log(`│ ${n.name.padEnd(24, ' ')} │ ${`${n.slotRange[0]} - ${n.slotRange[1]}`.padEnd(20, ' ')} │ ${n.keys.length.toString().padEnd(15, ' ')} │`);
    });
    console.log("└──────────────────────────┴──────────────────────┴─────────────────┘");
  }
}

function runDemo() {
  console.log("===================================================================");
  console.log(" SIMULATOR REDIS CLUSTER: 16.384 HASH SLOTS & HASH TAGS GROUPING   ");
  console.log("===================================================================\n");

  const cluster = new RedisClusterSimulator();

  // BAGIAN 1: Kunci Biasa Tanpa Hash Tag (Tersebar Acak di Berbagai Node)
  console.log("--- BAGIAN 1: KUNCI BIASA (TERSEBAR ACAK DI 3 MASTER) ---");
  const randomKeys = ["user:101:profile", "user:101:orders", "user:101:cart", "product:999", "session:abc"];
  randomKeys.forEach(k => {
    const res = cluster.set(k, "data_sample");
    console.log(` Kunci: "${k.padEnd(20, ' ')}" -> CRC16 Slot: ${res.slot.toString().padStart(5, ' ')} -> Disimpan di: ${res.node}`);
  });

  console.log("\nDistribusi Node Sementara:");
  cluster.printDistribution();

  // BAGIAN 2: Kunci Dengan Hash Tag {...} (Wajib Mendarat di 1 Node Fisik yang Sama!)
  console.log("\n--- BAGIAN 2: KUNCI DENGAN HASH TAGS {...} (CO-LOCATED MULTI-KEY) ---");
  console.log("Seluruh data milik user:202 diberi tag '{user:202}' agar bisa diakses dalam 1 transaksi:");

  const taggedKeys = [
    "{user:202}:profile",
    "{user:202}:orders",
    "{user:202}:cart",
    "{user:202}:preferences"
  ];

  taggedKeys.forEach(k => {
    const res = cluster.set(k, "user_data");
    console.log(` Kunci: "${k.padEnd(24, ' ')}" -> Slot: ${res.slot.toString().padStart(5, ' ')} -> Disimpan di: ${res.node}`);
  });

  console.log("\n===================================================================");
  console.log(" [KESIMPULAN ARSITEKTUR REDIS CLUSTER]:");
  console.log(" 1. Pada Bagian 1, data user:101 terpecah ke node berbeda (Gagal jika MGET).");
  console.log(" 2. Pada Bagian 2, Hash Tag '{user:202}' memaksa seluruh 4 kunci memiliki");
  console.log("    slot yang PERSIS SAMA (Bebas Cross-Slot Error, Transaksi Multi-Key Aman!).");
  console.log("===================================================================\n");
}

runDemo();
