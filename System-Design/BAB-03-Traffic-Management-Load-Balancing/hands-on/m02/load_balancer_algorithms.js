// load_balancer_algorithms.js
// Implementasi & Komparasi 4 Algoritma Load Balancing Terdistribusi

const crypto = require('crypto');

// ==========================================
// 1. ALGORITMA ROUND ROBIN
// ==========================================
class RoundRobinBalancer {
  constructor(servers) {
    this.servers = servers;
    this.currentIndex = 0;
  }

  getNextServer() {
    const server = this.servers[this.currentIndex];
    this.currentIndex = (this.currentIndex + 1) % this.servers.length;
    return server;
  }
}

// ==========================================
// 2. ALGORITMA WEIGHTED ROUND ROBIN
// ==========================================
class WeightedRoundRobinBalancer {
  constructor(serverWeights) {
    // serverWeights: [{ name: 'Server A', weight: 3 }, { name: 'Server B', weight: 1 }]
    this.pool = [];
    serverWeights.forEach(s => {
      for (let i = 0; i < s.weight; i++) {
        this.pool.push(s.name);
      }
    });
    this.currentIndex = 0;
  }

  getNextServer() {
    const server = this.pool[this.currentIndex];
    this.currentIndex = (this.currentIndex + 1) % this.pool.length;
    return server;
  }
}

// ==========================================
// 3. ALGORITMA LEAST CONNECTIONS
// ==========================================
class LeastConnectionsBalancer {
  constructor(serverNames) {
    this.servers = serverNames.map(name => ({ name, activeConnections: 0 }));
  }

  getNextServer() {
    // Cari server dengan koneksi aktif paling sedikit
    let leastServer = this.servers[0];
    for (const s of this.servers) {
      if (s.activeConnections < leastServer.activeConnections) {
        leastServer = s;
      }
    }
    leastServer.activeConnections++;
    return leastServer;
  }

  releaseConnection(server) {
    if (server.activeConnections > 0) {
      server.activeConnections--;
    }
  }
}

// ==========================================
// 4. ALGORITMA CONSISTENT HASHING (WITH VIRTUAL NODES)
// ==========================================
class ConsistentHashRing {
  constructor(servers, virtualNodesCount = 100) {
    this.virtualNodesCount = virtualNodesCount;
    this.ring = new Map(); // hashValue -> serverName
    this.sortedKeys = [];

    servers.forEach(server => this.addServer(server));
  }

  hash(key) {
    const md5 = crypto.createHash('md5').update(key).digest('hex');
    return parseInt(md5.substring(0, 8), 16); // 32-bit integer
  }

  addServer(server) {
    for (let i = 0; i < this.virtualNodesCount; i++) {
      const vNodeKey = `${server}#vn${i}`;
      const hashVal = this.hash(vNodeKey);
      this.ring.set(hashVal, server);
      this.sortedKeys.push(hashVal);
    }
    this.sortedKeys.sort((a, b) => a - b);
  }

  removeServer(server) {
    for (let i = 0; i < this.virtualNodesCount; i++) {
      const vNodeKey = `${server}#vn${i}`;
      const hashVal = this.hash(vNodeKey);
      this.ring.delete(hashVal);
    }
    this.sortedKeys = Array.from(this.ring.keys()).sort((a, b) => a - b);
  }

  getServer(requestKey) {
    if (this.sortedKeys.length === 0) return null;
    const requestHash = this.hash(requestKey);

    // Cari node pertama di cincin yang hash-nya >= requestHash (searah jarum jam)
    for (const key of this.sortedKeys) {
      if (key >= requestHash) {
        return this.ring.get(key);
      }
    }
    // Jika melewati ujung cincin, balik ke node pertama (wrap around 0)
    return this.ring.get(this.sortedKeys[0]);
  }
}

// ==========================================
// DEMO DAN EVALUASI HASIL
// ==========================================
function main() {
  console.log("===================================================================");
  console.log("       SIMULATOR & KOMPARASI 4 ALGORITMA LOAD BALANCING            ");
  console.log("===================================================================\n");

  // 1. Uji Round Robin
  console.log("--- 1. ROUND ROBIN (3 Server Identik: A, B, C) ---");
  const rr = new RoundRobinBalancer(['Server A', 'Server B', 'Server C']);
  const rrResults = {};
  for (let i = 1; i <= 9; i++) {
    const s = rr.getNextServer();
    rrResults[s] = (rrResults[s] || 0) + 1;
  }
  console.table(rrResults);

  // 2. Uji Weighted Round Robin
  console.log("\n--- 2. WEIGHTED ROUND ROBIN (Server A Bobot 3 vs Server B Bobot 1) ---");
  const wrr = new WeightedRoundRobinBalancer([
    { name: 'Server A (Besar)', weight: 3 },
    { name: 'Server B (Kecil)', weight: 1 }
  ]);
  const wrrResults = {};
  for (let i = 1; i <= 8; i++) {
    const s = wrr.getNextServer();
    wrrResults[s] = (wrrResults[s] || 0) + 1;
  }
  console.table(wrrResults);

  // 3. Uji Least Connections
  console.log("\n--- 3. LEAST CONNECTIONS (Server A sedang sibuk, Server B idle) ---");
  const lc = new LeastConnectionsBalancer(['Server A', 'Server B', 'Server C']);
  // Simulasikan Server A dan B sedang memegang koneksi
  lc.servers[0].activeConnections = 5; // Server A punya 5 koneksi
  lc.servers[1].activeConnections = 2; // Server B punya 2 koneksi
  lc.servers[2].activeConnections = 0; // Server C punya 0 koneksi

  console.log("Koneksi awal:", lc.servers.map(s => `${s.name}: ${s.activeConnections}`).join(", "));
  const chosenServer = lc.getNextServer();
  console.log(`-> Request baru otomatis diarahkan ke: ${chosenServer.name} (Koneksi aktif terkecil)`);

  // 4. Uji Consistent Hashing
  console.log("\n--- 4. CONSISTENT HASHING RING (Dengan 100 Virtual Nodes) ---");
  const servers = ['Server-Alpha', 'Server-Beta', 'Server-Gamma'];
  const chRing = new ConsistentHashRing(servers, 100);

  const testUsers = ['user_101', 'user_202', 'user_303', 'user_404', 'user_505'];
  console.log("Pemetaan Awal User ID ke Server:");
  const initialMapping = {};
  testUsers.forEach(u => {
    initialMapping[u] = chRing.getServer(u);
    console.log(` - ${u} -> ${initialMapping[u]}`);
  });

  console.log("\n⚡ [PERISTIWA]: Server-Beta mendadak CRASH dan dicabut dari cincin!");
  chRing.removeServer('Server-Beta');

  console.log("Pemetaan Ulang Setelah Server-Beta Dicabut:");
  let displacedCount = 0;
  testUsers.forEach(u => {
    const newServer = chRing.getServer(u);
    const wasOnBeta = initialMapping[u] === 'Server-Beta';
    const changed = initialMapping[u] !== newServer;
    if (changed) displacedCount++;
    console.log(` - ${u} -> ${newServer} ${changed ? (wasOnBeta ? '(✅ Direlokasi dari server mati)' : '(❌ Pindah Tidak Perlu)') : '(✅ Tetap di server lama)'}`);
  });

  console.log(`\nTotal user yang berpindah server: ${displacedCount}/${testUsers.length}`);
  console.log("Hanya user yang tadinya berada di Server-Beta yang berpindah! User lain tetap di server aslinya.");
  console.log("===================================================================\n");
}

main();
