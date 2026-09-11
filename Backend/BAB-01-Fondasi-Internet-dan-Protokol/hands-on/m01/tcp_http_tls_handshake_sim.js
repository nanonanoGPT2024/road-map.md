/**
 * Raw TCP 3-Way Handshake, DNS Resolution, & TLS 1.3 ECDHE Simulator
 * 
 * Mensimulasikan perjalanan paket jaringan end-to-end:
 * 1. Resolusi DNS Hierarki (Root -> TLD -> Authoritative).
 * 2. TCP 3-Way Handshake (SYN, SYN-ACK, ACK) dengan nomor sequence & acknowledgment.
 * 3. Kriptografi TLS 1.3 nyata: Pertukaran Kunci ECDHE (Elliptic Curve Diffie-Hellman)
 *    menggunakan kurva standar 'prime256v1' dan enkripsi simetris AES-256-GCM.
 * 4. Pengiriman data terenkripsi HTTP GET payload.
 * 5. TCP 4-Way Connection Teardown (FIN/ACK).
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

function log(layer, msg, color = ANSI.reset) {
  console.log(`${color}[${layer}] ${msg}${ANSI.reset}`);
}

// ================= 1. DNS RESOLVER SIMULATOR =================
class DNSResolver {
  static resolve(domain) {
    log("dns-client", `Memulai pencarian IP untuk domain '${domain}'...`, ANSI.cyan);
    log("dns-resolver", `1. Bertanya ke Root Server (.): "Siapa pengelola TLD .com?" -> Root mengarahkan ke TLD Server`, ANSI.cyan);
    log("dns-resolver", `2. Bertanya ke TLD Server (.com): "Siapa Authoritative Server bank.com?" -> Mengarahkan ke ns1.cloudflare.com`, ANSI.cyan);
    log("dns-resolver", `3. Bertanya ke Authoritative Nameserver (ns1.cloudflare.com): Query 'A api.bank.com'`, ANSI.cyan);

    const resolvedIP = "104.21.58.12";
    const ttlSeconds = 300;
    log("dns-client", `RESOLVED! ${domain} -> ${resolvedIP} (TTL: ${ttlSeconds}s, disimpan di cache lokal)`, ANSI.green);
    return resolvedIP;
  }
}

// ================= 2. TCP & TLS SIMULATION =================
class NetworkSimulator {
  static runFullHandshake() {
    console.log(`\n${ANSI.bold}=== TAHAP 1: TCP 3-WAY HANDSHAKE (LAYER 4) ===${ANSI.reset}`);

    // Nomor sequence acak awal
    let clientSeq = Math.floor(1000 + Math.random() * 8000);
    let serverSeq = Math.floor(50000 + Math.random() * 8000);

    // Langkah 1: Client -> Server: SYN
    log("client -> server", `TCP Packet: [SYN] Seq=${clientSeq}, Ack=0, Win=65535, MSS=1460`, ANSI.yellow);
    
    // Langkah 2: Server -> Client: SYN-ACK
    const expectedClientAck = clientSeq + 1;
    log("server -> client", `TCP Packet: [SYN, ACK] Seq=${serverSeq}, Ack=${expectedClientAck}, Win=65535`, ANSI.green);

    // Langkah 3: Client -> Server: ACK
    clientSeq = expectedClientAck;
    const expectedServerAck = serverSeq + 1;
    log("client -> server", `TCP Packet: [ACK] Seq=${clientSeq}, Ack=${expectedServerAck}`, ANSI.yellow);

    log("tcp-stack", `STATUS: TCP Connection ESTABLISHED! Saluran transport siap digunakan.`, ANSI.bold + ANSI.green);

    // ================= TAHAP 2: TLS 1.3 HANDSHAKE (1-RTT) =================
    console.log(`\n${ANSI.bold}=== TAHAP 2: TLS 1.3 CRYPTOGRAPHIC HANDSHAKE (ECDHE 1-RTT) ===${ANSI.reset}`);

    // Buat pasangan kunci kurva eliptis nyata (ECDH) pada Client
    const clientECDH = crypto.createECDH("prime256v1");
    const clientPublicKey = clientECDH.generateKeys();

    log("client -> server", `TLS Packet: ClientHello`, ANSI.cyan);
    log("client -> server", `-> Supported Ciphers: [TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256]`, ANSI.cyan);
    log("client -> server", `-> KeyShare Extension: Client ECDHE Public Key (${clientPublicKey.toString("hex").substring(0, 24)}...)`, ANSI.cyan);

    // Server menerima ClientHello, membangkitkan kunci ECDH miliknya
    const serverECDH = crypto.createECDH("prime256v1");
    const serverPublicKey = serverECDH.generateKeys();

    // Server menghitung Shared Secret
    const serverSharedSecret = serverECDH.computeSecret(clientPublicKey);
    log("server -> client", `TLS Packet: ServerHello`, ANSI.magenta);
    log("server -> client", `-> Selected Cipher: TLS_AES_256_GCM_SHA384`, ANSI.magenta);
    log("server -> client", `-> KeyShare Extension: Server ECDHE Public Key (${serverPublicKey.toString("hex").substring(0, 24)}...)`, ANSI.magenta);
    log("server -> client", `-> {EncryptedExtensions, Certificate: CN=api.bank.com, CertificateVerify, Finished}`, ANSI.magenta);

    // Client menghitung Shared Secret yang sama persis
    const clientSharedSecret = clientECDH.computeSecret(serverPublicKey);

    // Validasi bahwa matematika Diffie-Hellman kedua belah pihak identik tanpa pernah mengirimkan secret di jaringan!
    const secretsMatch = clientSharedSecret.equals(serverSharedSecret);
    log("crypto-engine", `Validasi Kriptografi ECDHE: Client Secret == Server Secret? ${secretsMatch ? ANSI.green + "TRUE (100% IDENTIK)" : ANSI.red + "FALSE"}${ANSI.reset}`);
    log("crypto-engine", `Derived Symmetric Session Key (SHA256 of secret): ${crypto.createHash("sha256").update(clientSharedSecret).digest("hex").substring(0, 32)}...`, ANSI.bold);
    log("tls-stack", `STATUS: TLS 1.3 Channel SECURE! Enkripsi end-to-end aktif hanya dalam 1 Round-Trip!`, ANSI.bold + ANSI.green);

    // ================= TAHAP 3: PENGIRIMAN DATA APLIKASI (HTTP OVER TLS) =================
    console.log(`\n${ANSI.bold}=== TAHAP 3: ENCRYPTED APPLICATION DATA TRANSMISSION ===${ANSI.reset}`);

    const symmetricKey = crypto.createHash("sha256").update(clientSharedSecret).digest();
    const iv = crypto.randomBytes(12); // 96-bit IV untuk AES-GCM

    const httpPayload = "GET /v1/account/balance HTTP/1.1\r\nHost: api.bank.com\r\nAuthorization: Bearer sec-token-98765\r\n\r\n";
    log("http-client", `Plaintext Request Asli:\n${httpPayload.trim()}`, ANSI.yellow);

    // Enkripsi payload menggunakan AES-256-GCM
    const cipher = crypto.createCipheriv("aes-256-gcm", symmetricKey, iv);
    let ciphertext = cipher.update(httpPayload, "utf8", "hex");
    ciphertext += cipher.final("hex");
    const authTag = cipher.getAuthTag();

    log("wire-sniff", `Data yang Lewat di Kabel Jaringan (Ciphertext Terenkripsi):`, ANSI.red);
    log("wire-sniff", `${ciphertext.substring(0, 60)}... [Tag: ${authTag.toString("hex")}] (Penyadap hanya melihat data acak!)`, ANSI.red);

    // Server mendekripsi payload
    const decipher = crypto.createDecipheriv("aes-256-gcm", symmetricKey, iv);
    decipher.setAuthTag(authTag);
    let decrypted = decipher.update(ciphertext, "hex", "utf8");
    decrypted += decipher.final("utf8");

    log("backend-server", `Server Berhasil Mendekripsi Payload:\n${decrypted.trim()}`, ANSI.green);
    log("backend-server", `Memproses request di Handler... Mengembalikan HTTP 200 OK: {"balance": 25000000}`, ANSI.green);

    // ================= TAHAP 4: TCP 4-WAY CONNECTION TEARDOWN =================
    console.log(`\n${ANSI.bold}=== TAHAP 4: TCP 4-WAY CONNECTION CLOSURE (TEARDOWN) ===${ANSI.reset}`);
    log("client -> server", `TCP Packet: [FIN, ACK] Client menutup sesi kirim`, ANSI.cyan);
    log("server -> client", `TCP Packet: [ACK] Server mengakui penutupan client`, ANSI.cyan);
    log("server -> client", `TCP Packet: [FIN, ACK] Server menutup sesi kirim miliknya`, ANSI.cyan);
    log("client -> server", `TCP Packet: [ACK] Client mengakui penutupan server -> TIME_WAIT (2MSL) -> CLOSED`, ANSI.cyan);
    log("tcp-stack", `STATUS: TCP Socket Ditutup Bersih (Graceful Teardown).`, ANSI.bold + ANSI.green);
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}   INTERNET PROTOCOL SIMULATOR: DNS, TCP HANDSHAKE, & TLS 1.3   ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);

// 1. Eksekusi Resolusi DNS
DNSResolver.resolve("api.bank.com");

// 2. Eksekusi TCP + TLS + HTTP
NetworkSimulator.runFullHandshake();

console.log(`\n${ANSI.bold}Seluruh siklus transmisi internet berhasil disimulasikan secara presisi!${ANSI.reset}`);
