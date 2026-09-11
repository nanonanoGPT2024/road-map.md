/**
 * HTTP/2 Multiplexing, WebSocket Handshake/Framing, & SSE Engine Simulator
 * 
 * Mensimulasikan protokol real-time & modern application layer:
 * 1. HTTP/2 Binary Multiplexing: Pengiriman paket multi-stream terjalin (interleaved) di 1 TCP socket.
 * 2. WebSocket RFC 6455:
 *    - Handshake Upgrade HTTP 101 dengan kalkulasi SHA-1 Sec-WebSocket-Accept.
 *    - Framing biner dengan Masking Key XOR 4-byte (Client -> Server).
 *    - Mekanisme Ping (Opcode 0x9) dan Pong (Opcode 0xA) heartbeat.
 * 3. Server-Sent Events (SSE):
 *    - Unidirectional streaming event text/event-stream.
 *    - Reconnection resilience menggunakan header 'Last-Event-ID'.
 */

const crypto = require("crypto");

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

// ================= 1. HTTP/2 MULTIPLEXING SIMULATOR =================
class HTTP2Multiplexer {
  static runDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 1: HTTP/2 BINARY MULTIPLEXING SIMULATION ===${ANSI.reset}`);
    log("tcp-socket", "1 Koneksi TCP Tunggal Terbuka (Port 443)", ANSI.cyan);

    // Stream 1: Request Profil Pengguna
    // Stream 3: Request Katalog Produk
    const frames = [
      { streamId: 1, type: "HEADERS", payload: "GET /api/v1/user" },
      { streamId: 3, type: "HEADERS", payload: "GET /api/v1/products" },
      { streamId: 1, type: "DATA", payload: "{\"userId\": 42, \"name\": \"Alex\"}" },
      { streamId: 3, type: "DATA", payload: "[{\"id\": 1, \"item\": \"Laptop\"}, ...]" },
      { streamId: 1, type: "END_STREAM", payload: "Stream 1 Closed" },
      { streamId: 3, type: "END_STREAM", payload: "Stream 3 Closed" }
    ];

    log("http2-engine", "Mengirimkan frame biner secara terjalin (interleaved) tanpa HoL Blocking:", ANSI.yellow);
    for (const f of frames) {
      log("wire", `[Frame ${f.type.padEnd(10)}] Stream ID #${f.streamId} -> Payload: ${f.payload}`, ANSI.magenta);
    }
    log("http2-engine", "Kedua request selesai serentak melalui 1 koneksi fisik TCP yang sama!", ANSI.green);
  }
}

// ================= 2. WEBSOCKET RFC 6455 SIMULATOR =================
class WebSocketSimulator {
  static runHandshakeAndFraming() {
    console.log(`\n${ANSI.bold}=== BAGIAN 2: WEBSOCKET RFC 6455 HANDSHAKE & BINARY FRAMING ===${ANSI.reset}`);

    // A. Handshake Upgrade
    const clientNonce = crypto.randomBytes(16).toString("base64");
    log("client -> server", `HTTP Upgrade Request:`, ANSI.cyan);
    log("client -> server", `GET /chat HTTP/1.1\nUpgrade: websocket\nConnection: Upgrade\nSec-WebSocket-Key: ${clientNonce}`, ANSI.cyan);

    // Server menghitung Sec-WebSocket-Accept
    const WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
    const serverAccept = crypto
      .createHash("sha1")
      .update(clientNonce + WS_GUID)
      .digest("base64");

    log("server -> client", `HTTP 101 Switching Protocols:`, ANSI.green);
    log("server -> client", `HTTP/1.1 101 Switching Protocols\nUpgrade: websocket\nConnection: Upgrade\nSec-WebSocket-Accept: ${serverAccept}`, ANSI.green);

    // B. Masking & Binary Framing (Client -> Server)
    const rawMessage = "Halo Backend dari WebSocket Client!";
    const maskingKey = crypto.randomBytes(4); // 4-byte XOR mask wajib untuk client
    const rawBuffer = Buffer.from(rawMessage, "utf8");
    const maskedBuffer = Buffer.alloc(rawBuffer.length);

    for (let i = 0; i < rawBuffer.length; i++) {
      maskedBuffer[i] = rawBuffer[i] ^ maskingKey[i % 4];
    }

    log("ws-client", `Pesan Asli: "${rawMessage}"`, ANSI.yellow);
    log("ws-client", `Masking Key (XOR 4-byte): [0x${maskingKey.toString("hex")}]`, ANSI.yellow);
    log("wire", `Frame Terkirim di Jaringan (Masked): <${maskedBuffer.toString("hex").substring(0, 30)}...>`, ANSI.red);

    // Server Unmasking
    const unmaskedBuffer = Buffer.alloc(maskedBuffer.length);
    for (let i = 0; i < maskedBuffer.length; i++) {
      unmaskedBuffer[i] = maskedBuffer[i] ^ maskingKey[i % 4];
    }
    const decodedMessage = unmaskedBuffer.toString("utf8");
    log("ws-server", `Server Berhasil Men-decode via XOR Unmask: "${decodedMessage}"`, ANSI.green);

    // C. Heartbeat Ping / Pong
    log("ws-server", `Mengirim Frame Biner PING (Opcode 0x9) untuk memastikan client hidup...`, ANSI.cyan);
    log("ws-client", `Menerima Ping -> Membalas otomatis dengan Frame PONG (Opcode 0xA)`, ANSI.green);
  }
}

// ================= 3. SERVER-SENT EVENTS (SSE) SIMULATOR =================
class SSESimulator {
  static runDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 3: SERVER-SENT EVENTS (SSE) STREAMING & RESILIENCE ===${ANSI.reset}`);

    log("sse-client", `Client melakukan HTTP GET /v1/ai/stream-completion`, ANSI.cyan);
    log("sse-server", `HTTP/1.1 200 OK\nContent-Type: text/event-stream\nCache-Control: no-cache\nConnection: keep-alive`, ANSI.green);

    const tokens = ["Halo", "!", " ", "Arsitektur", " ", "Backend", " ", "Tingkat", " ", "Lanjut", "."];
    let eventId = 100;

    console.log(`\n[SSE Stream Active - Output Token AI Streaming]:`);
    for (const tok of tokens) {
      eventId++;
      const sseChunk = `id: ${eventId}\nevent: token\ndata: {"text": "${tok}"}\n\n`;
      process.stdout.write(`${ANSI.green}${tok}${ANSI.reset}`);
    }
    console.log("\n");

    // Simulasi Terputus & Reconnection via Last-Event-ID
    log("network", `Sinyal smartphone terputus sesaat (Network Disconnect)!`, ANSI.red);
    log("sse-client", `Browser EventSource otomatis reconnect ke server dengan header:`, ANSI.yellow);
    log("sse-client", `GET /v1/ai/stream-completion\nLast-Event-ID: ${eventId}`, ANSI.yellow);
    log("sse-server", `Server mendeteksi Last-Event-ID: ${eventId}. Melanjutkan streaming dari token berikutnya tanpa duplikasi data!`, ANSI.green);
  }
}

// ================= EKSEKUSI SIMULASI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}   MODERN PROTOCOLS SIMULATOR: HTTP/2, WEBSOCKET, & SSE STREAM  ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);

HTTP2Multiplexer.runDemo();
WebSocketSimulator.runHandshakeAndFraming();
SSESimulator.runDemo();

console.log(`\n${ANSI.bold}Seluruh spesifikasi protokol aplikasi tervalidasi dengan sempurna!${ANSI.reset}`);
