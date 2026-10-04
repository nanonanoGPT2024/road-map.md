// realtime_comparison.js
// Simulator Komparasi Real-time: Long Polling vs Server-Sent Events (SSE) vs WebSocket Full-Duplex

const http = require('http');

// ===================================================================
// 1. SIMULATOR LONG POLLING SERVER
// ===================================================================
// Server menahan koneksi client hingga event terjadi atau timeout
class LongPollingSimulator {
  constructor() {
    this.waitingClients = [];
  }

  handleClientPoll(res) {
    // Tahan request client di array antrean
    this.waitingClients.push(res);
  }

  broadcastEvent(message) {
    const count = this.waitingClients.length;
    while (this.waitingClients.length > 0) {
      const client = this.waitingClients.pop();
      client.writeHead(200, { 'Content-Type': 'application/json' });
      client.end(JSON.stringify({ event: message, timestamp: Date.now() }));
    }
    return count;
  }
}

// ===================================================================
// 2. SIMULATOR SERVER-SENT EVENTS (SSE)
// ===================================================================
// Server membuka 1 koneksi streaming HTTP persisten satu arah
class SSESimulator {
  constructor() {
    this.activeStreams = new Set();
  }

  handleClientConnection(res) {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    });
    res.write(`: SSE Connected\n\n`);
    this.activeStreams.add(res);
  }

  broadcastEvent(message) {
    const payload = `data: ${JSON.stringify({ event: message, timestamp: Date.now() })}\n\n`;
    this.activeStreams.forEach(res => res.write(payload));
    return this.activeStreams.size;
  }
}

// ===================================================================
// 3. SIMULATOR WEBSOCKET FULL-DUPLEX (Dua Arah)
// ===================================================================
class WebSocketSimulator {
  constructor() {
    this.connectedSockets = new Set();
  }

  connectSocket(socketId) {
    const socket = {
      id: socketId,
      overheadPerMessageBytes: 2, // Frame header biner murni ~2 bytes
      send: (data) => `[Socket ${socketId}] Received Frame: ${JSON.stringify(data)}`
    };
    this.connectedSockets.add(socket);
    return socket;
  }

  broadcast(message) {
    let sentCount = 0;
    this.connectedSockets.forEach(s => {
      s.send(message);
      sentCount++;
    });
    return sentCount;
  }
}

// ===================================================================
// RUN COMPARISON DEMO
// ===================================================================
async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function runDemo() {
  console.log("===================================================================");
  console.log("       SIMULATOR & KOMPARASI 3 PARADIGMA KOMUNIKASI REAL-TIME       ");
  console.log("===================================================================\n");

  // 1. DEMO LONG POLLING
  console.log("--- 1. UJI MEKANISME LONG POLLING ---");
  const lp = new LongPollingSimulator();
  console.log(" Client A dan Client B mengirim HTTP GET /poll (Koneksi tertahan di server)...");
  
  // Simulasi 2 mock client responses
  const mockClientA = { writeHead: () => {}, end: (d) => console.log(`   -> Client A menerima: ${d}`) };
  const mockClientB = { writeHead: () => {}, end: (d) => console.log(`   -> Client B menerima: ${d}`) };
  lp.handleClientPoll(mockClientA);
  lp.handleClientPoll(mockClientB);

  await sleep(300);
  console.log(" ⚡ Event Terjadi di Server: 'Gol dicetak oleh Tim Merah!'");
  lp.broadcastEvent("Gol dicetak oleh Tim Merah!");
  console.log(" ⚠️ [Kelemahan Long Polling]: Kedua koneksi HTTP langsung TERTUTUP.");
  console.log("    Client A & B terpaksa mengirimkan koneksi HTTP baru (overhead 1KB lagi).\n");

  // 2. DEMO SERVER-SENT EVENTS (SSE)
  console.log("--- 2. UJI MEKANISME SERVER-SENT EVENTS (SSE) ---");
  const sse = new SSESimulator();
  console.log(" Client A dan Client B membuka 1 koneksi streaming persisten (text/event-stream)...");

  const sseMockClientA = { writeHead: () => {}, write: (d) => console.log(`   -> Client A Stream: ${d.trim()}`) };
  const sseMockClientB = { writeHead: () => {}, write: (d) => console.log(`   -> Client B Stream: ${d.trim()}`) };
  sse.handleClientConnection(sseMockClientA);
  sse.handleClientConnection(sseMockClientB);

  await sleep(300);
  console.log(" ⚡ Event 1 Terjadi: 'Kartu Kuning Nomor 7'");
  sse.broadcastEvent("Kartu Kuning Nomor 7");

  await sleep(200);
  console.log(" ⚡ Event 2 Terjadi: 'Peluit Babak 1 Selesai'");
  sse.broadcastEvent("Peluit Babak 1 Selesai");
  console.log(" ✅ [Keunggulan SSE]: Koneksi HTTP tetap TERBUKA kontinu tanpa perlu rekoneksi!\n");

  // 3. DEMO WEBSOCKET FULL-DUPLEX
  console.log("--- 3. UJI MEKANISME WEBSOCKET FULL-DUPLEX ---");
  const wsCluster = new WebSocketSimulator();
  const socket1 = wsCluster.connectSocket("user_andi");
  const socket2 = wsCluster.connectSocket("user_budi");
  console.log(" 1x HTTP Upgrade Handshake sukses -> Koneksi TCP Socket murni terbentuk.");

  console.log(" Client Andi mengirim pesan chat: 'Halo Budi!' (Client -> Server)");
  console.log(" Server menyiarkan frame biner ke seluruh soket (Server -> Client)...");
  wsCluster.broadcast({ from: "user_andi", text: "Halo Budi!" });
  console.log(` ✅ [Keunggulan WebSocket]: Dua arah simultan, overhead per pesan HANYA ${socket1.overheadPerMessageBytes} Bytes!`);

  console.log("\n===================================================================");
  console.log("                       TABEL RANGKUMAN                             ");
  console.log("===================================================================");
  console.log(" 1. Long Polling : Siklus buka-tutup koneksi berulang (Boros bandwidth).");
  console.log(" 2. SSE          : Satu arah server-ke-client, native HTTP/2, auto-reconnect.");
  console.log(" 3. WebSocket    : Dua arah full-duplex, latensi terendah, frame biner padat.");
  console.log("===================================================================\n");
}

runDemo();
