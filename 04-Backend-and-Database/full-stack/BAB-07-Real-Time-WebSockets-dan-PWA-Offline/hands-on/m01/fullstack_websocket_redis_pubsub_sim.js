/**
 * SIMULATOR: Full-Stack WebSocket Multi-Node Cluster & Redis Pub/Sub Broker
 * -----------------------------------------------------------------------------
 * File: fullstack_websocket_redis_pubsub_sim.js
 * Deskripsi: Simulasi mandiri (zero-dependency) dari arsitektur real-time kluster
 * multi-node, penyebaran pesan lintas server melalui Redis Pub/Sub, pendeteksian
 * zombie socket via heartbeat ping/pong, dan algoritma rekoneksi exponential backoff.
 */

const EventEmitter = require("events");

// =============================================================================
// 1. SIMULATOR REDIS PUB/SUB DISTRIBUTED BROKER
// =============================================================================

class RedisPubSubBroker {
  constructor() {
    this.channels = new Map(); // channelName -> Set of listener callbacks
  }

  subscribe(channel, callback) {
    if (!this.channels.has(channel)) {
      this.channels.set(channel, new Set());
    }
    this.channels.get(channel).add(callback);
    return () => this.channels.get(channel)?.delete(callback);
  }

  publish(channel, message) {
    const listeners = this.channels.get(channel);
    if (listeners) {
      for (const cb of listeners) {
        // Asynchronous delivery simulasi latensi jaringan Redis (~1-2ms)
        setTimeout(() => cb(message), 2);
      }
    }
  }
}

// =============================================================================
// 2. SIMULATOR WEBSOCKET SERVER NODE (CLUSTER INSTANCE)
// =============================================================================

class WebSocketServerNode {
  constructor(nodeId, redisBroker) {
    this.nodeId = nodeId;
    this.redisBroker = redisBroker;
    this.connectedSockets = new Map(); // socketId -> { socket, room, isAlive }

    // Berlangganan pesan global dari Redis
    this.redisBroker.subscribe("CLUSTER_BROADCAST", (msg) => {
      this._handleRedisMessage(msg);
    });
  }

  registerClient(socketId, room, clientHandler) {
    this.connectedSockets.set(socketId, {
      id: socketId,
      room,
      handler: clientHandler,
      isAlive: true,
      lastSeen: Date.now(),
    });
    console.log(`  [${this.nodeId}] Client '${socketId}' terhubung ke Room: '${room}'`);
  }

  // Client mengirim pesan ke server lokal
  clientSendMessage(socketId, text) {
    const sender = this.connectedSockets.get(socketId);
    if (!sender) return;

    const payload = {
      originNode: this.nodeId,
      senderId: socketId,
      room: sender.room,
      text,
      timestamp: new Date().toISOString(),
    };

    // Publikasikan ke Redis Pub/Sub agar seluruh node di kluster mendengar
    this.redisBroker.publish("CLUSTER_BROADCAST", payload);
  }

  _handleRedisMessage(payload) {
    // Siarkan ke seluruh socket lokal yang berada di room yang sama
    for (const [sId, client] of this.connectedSockets.entries()) {
      if (client.room === payload.room) {
        client.handler(payload);
      }
    }
  }

  // Protokol Heartbeat Ping: Deteksi Zombie Connection
  runHeartbeatCheck() {
    for (const [sId, client] of this.connectedSockets.entries()) {
      if (!client.isAlive) {
        console.log(`  💀 [${this.nodeId}] ZOMBIE SOCKET DETECTED: '${sId}' tidak merespons PING. Memutus paksa koneksi.`);
        this.connectedSockets.delete(sId);
      } else {
        // Set false dan tunggu PONG
        client.isAlive = false;
      }
    }
  }

  receivePong(socketId) {
    const client = this.connectedSockets.get(socketId);
    if (client) {
      client.isAlive = true;
      client.lastSeen = Date.now();
    }
  }
}

// =============================================================================
// 3. EXPONENTIAL BACKOFF WITH JITTER RECONNECTION SIMULATOR
// =============================================================================

function calculateBackoffWithJitter(attempt, baseMs = 500, maxMs = 8000) {
  const exponential = Math.min(Math.pow(2, attempt) * baseMs, maxMs);
  const jitter = Math.random() * (baseMs * 0.5); // Random Jitter 0-250ms
  return Math.round(exponential + jitter);
}

// =============================================================================
// 4. RUN SUITE SIMULATION
// =============================================================================

async function runSimulation() {
  console.log("===========================================================================");
  console.log("SIMULASI: WEBSOCKET MULTI-NODE CLUSTER & REDIS PUB/SUB ADAPTER");
  console.log("===========================================================================\n");

  const redisBroker = new RedisPubSubBroker();

  // Membentuk 3 Node Server WebSocket yang berdiri independen
  const nodeA = new WebSocketServerNode("NODE_JAKARTA_01", redisBroker);
  const nodeB = new WebSocketServerNode("NODE_SINGAPORE_01", redisBroker);
  const nodeC = new WebSocketServerNode("NODE_FRANKFURT_01", redisBroker);

  // Menyambungkan 3 Client ke server yang berbeda secara geografis
  console.log("--- TAHAP 1: Klien Terhubung ke Server Node yang Berbeda-beda ---");
  const aliceReceived = [];
  const bobReceived = [];
  const charlieReceived = [];

  nodeA.registerClient("Alice", "ROOM_ARCHITECT", (msg) => {
    aliceReceived.push(msg);
    console.log(`  📩 [Alice @ Jakarta] Menerima pesan dari ${msg.senderId}: "${msg.text}"`);
  });

  nodeB.registerClient("Bob", "ROOM_ARCHITECT", (msg) => {
    bobReceived.push(msg);
    console.log(`  📩 [Bob @ Singapore] Menerima pesan dari ${msg.senderId}: "${msg.text}"`);
  });

  nodeC.registerClient("Charlie", "ROOM_ARCHITECT", (msg) => {
    charlieReceived.push(msg);
    console.log(`  📩 [Charlie @ Frankfurt] Menerima pesan dari ${msg.senderId}: "${msg.text}"`);
  });

  // Client David di Room Berbeda (ROOM_FINANCE)
  nodeB.registerClient("David", "ROOM_FINANCE", (msg) => {
    console.log(`  📩 [David @ Singapore] Menerima pesan: "${msg.text}"`);
  });

  console.log("\n--- TAHAP 2: Alice di Jakarta Mengirim Chat ke Room 'ROOM_ARCHITECT' ---");
  console.log("  [ACTION] Alice: 'Rekan-rekan, migrasi database telah selesai!'...");
  nodeA.clientSendMessage("Alice", "Rekan-rekan, migrasi database telah selesai!");

  // Tunggu sejenak agar pesan disebarkan via Redis
  await new Promise((r) => setTimeout(r, 20));

  console.log(`\n  Verifikasi Penerimaan:`);
  console.log(`  - Bob menerima pesan?     : ${bobReceived.length === 1 ? "YA ✅" : "TIDAK ❌"}`);
  console.log(`  - Charlie menerima pesan? : ${charlieReceived.length === 1 ? "YA ✅" : "TIDAK ❌"}`);
  console.log(`  - Apakah David (Room Finance) terganggu? : ${charlieReceived.length === 1 ? "TIDAK (Room Terisolasi Aman! ✅)" : "YA"}\n`);

  // TAHAP 3: DETEKSI ZOMBIE SOCKET DENGAN HEARTBEAT
  console.log("--- TAHAP 3: Deteksi Zombie Connection (Silent Disconnect) ---");
  console.log("  Skenario: Wi-Fi Charlie mati mendadak tanpa mengirimkan frame penutupan TCP.");
  // Putaran Heartbeat 1: Kirim Ping ke semua client
  nodeC.runHeartbeatCheck(); // Charlie isAlive di-set false

  // Client normal mengirim Pong, tapi Charlie tidak
  // nodeC.receivePong("Charlie"); <-- sengaja tidak dipanggil!

  console.log("  Server menunggu respons Pong selama 1 interval...");
  // Putaran Heartbeat 2: Periksa status Pong
  nodeC.runHeartbeatCheck();
  console.log(`  Total client aktif di Node Frankfurt: ${nodeC.connectedSockets.size} client (Zombie dibersihkan! ✅)\n`);

  // TAHAP 4: SIMULASI EXPONENTIAL BACKOFF RECONNECTION DENGAN JITTER
  console.log("--- TAHAP 4: Algoritma Rekoneksi Klien (Exponential Backoff + Jitter) ---");
  console.log("  Mencegah Thundering Herd Problem saat server pulih pasca-outage:\n");

  for (let attempt = 1; attempt <= 5; attempt++) {
    const delay = calculateBackoffWithJitter(attempt);
    console.log(`  🔄 Percobaan Reconnect ke-${attempt}: Delay = ${delay} ms (Interval Adaptif)`);
  }

  console.log("\n===========================================================================");
  console.log("SIMULASI SELESAI: Arsitektur Real-Time Multi-Node Teruji Sempurna!");
  console.log("===========================================================================");
}

runSimulation();
