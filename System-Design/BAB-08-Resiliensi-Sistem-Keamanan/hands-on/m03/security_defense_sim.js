/**
 * LAB SIMULATION: Cryptographic Token Verification, Tampering Defense, & L7 DDoS Shield
 * 
 * Menggunakan modul bawaan 'crypto' Node.js murni (Zero External Dependencies).
 * 
 * Skenario:
 * 1. Menerbitkan JWT yang sah untuk user reguler.
 * 2. Mencoba memalsukan (tamper) token untuk menjadi "admin" -> Verifikasi tanda tangan GAGAL!
 * 3. Menguji token yang kedaluwarsa (Expired Token Defense).
 * 4. Simulasi L7 HTTP Flood Shield (WAF IP Throttling).
 */

const crypto = require("crypto");

// 1. JWT ENGINE DARI NOL (BUILT-IN CRYPTO)
class SimpleJwtEngine {
  constructor(secretKey) {
    this.secretKey = secretKey;
  }

  base64UrlEncode(str) {
    return Buffer.from(str)
      .toString("base64")
      .replace(/=/g, "")
      .replace(/\+/g, "-")
      .replace(/\//g, "_");
  }

  base64UrlDecode(str) {
    str = str.replace(/-/g, "+").replace(/_/g, "/");
    while (str.length % 4) str += "=";
    return Buffer.from(str, "base64").toString("utf8");
  }

  createToken(payload, expiresInSec = 300) {
    const header = { alg: "HS256", typ: "JWT" };
    const now = Math.floor(Date.now() / 1000);
    const enrichedPayload = { ...payload, iat: now, exp: now + expiresInSec };

    const encodedHeader = this.base64UrlEncode(JSON.stringify(header));
    const encodedPayload = this.base64UrlEncode(JSON.stringify(enrichedPayload));

    const signature = crypto
      .createHmac("sha256", this.secretKey)
      .update(`${encodedHeader}.${encodedPayload}`)
      .digest("base64")
      .replace(/=/g, "")
      .replace(/\+/g, "-")
      .replace(/\//g, "_");

    return `${encodedHeader}.${encodedPayload}.${signature}`;
  }

  verifyToken(token) {
    const parts = token.split(".");
    if (parts.length !== 3) {
      return { valid: false, error: "Invalid token format (Must have 3 parts)" };
    }

    const [headerB64, payloadB64, signature] = parts;

    // Verifikasi Tanda Tangan Kriptografis
    const expectedSignature = crypto
      .createHmac("sha256", this.secretKey)
      .update(`${headerB64}.${payloadB64}`)
      .digest("base64")
      .replace(/=/g, "")
      .replace(/\+/g, "-")
      .replace(/\//g, "_");

    if (signature !== expectedSignature) {
      return { valid: false, error: "🚨 SIGNATURE FORGERY DETECTED! Data telah dimanipulasi!" };
    }

    // Verifikasi Expire Time
    const payload = JSON.parse(this.base64UrlDecode(payloadB64));
    const now = Math.floor(Date.now() / 1000);
    if (payload.exp && payload.exp < now) {
      return { valid: false, error: "⌛ TOKEN EXPIRED! Harap lakukan refresh token." };
    }

    return { valid: true, payload };
  }
}

// 2. LAYER 7 DDOS & BRUTE FORCE SHIELD
class L7WafShield {
  constructor(thresholdPerSec = 5) {
    this.thresholdPerSec = thresholdPerSec;
    this.ipTracker = new Map(); // ip -> { count, windowStart }
    this.blacklist = new Set();
  }

  inspectRequest(ip) {
    if (this.blacklist.has(ip)) {
      return { allowed: false, reason: "403 Forbidden: IP ini telah di-blacklist permanen oleh WAF!" };
    }

    const now = Date.now();
    const record = this.ipTracker.get(ip) || { count: 0, windowStart: now };

    if (now - record.windowStart > 1000) {
      record.count = 1;
      record.windowStart = now;
    } else {
      record.count += 1;
    }
    this.ipTracker.set(ip, record);

    if (record.count > this.thresholdPerSec) {
      this.blacklist.add(ip);
      return { allowed: false, reason: `🚨 429 / 403: Serangan L7 HTTP Flood terdeteksi dari ${ip} (${record.count} req/s). IP DIBLOKIR!` };
    }

    return { allowed: true };
  }
}

// ======================= PENGUJIAN =======================
console.log("===================================================================");
console.log("🛠️  PENGUJIAN 1: PEMBUATAN TOKEN SAH VS UPAYA PEMALSUAN DATA (TAMPERING)");
console.log("===================================================================\n");

const jwt = new SimpleJwtEngine("super-secret-enterprise-key-2026");

// Token Asli untuk user biasa
const legitimateToken = jwt.createToken({ userId: 101, username: "budi", role: "user" }, 60);
console.log("1. Token Sah Diterbitkan untuk Budi (Role: 'user'):");
console.log(legitimateToken);

const verifyLegit = jwt.verifyToken(legitimateToken);
console.log(`-> Hasil Verifikasi: Valid = ${verifyLegit.valid}, Role = "${verifyLegit.payload.role}"\n`);

// Upaya Hacker: Merubah role 'user' menjadi 'admin' di payload Base64
console.log("2. Simulasi Serangan: Attacker mengubah payload Base64 menjadi Role 'admin'...");
const parts = legitimateToken.split(".");
const decodedPayload = JSON.parse(jwt.base64UrlDecode(parts[1]));
decodedPayload.role = "admin"; // Manipulasi payload
decodedPayload.username = "hacked_admin";

const tamperedPayloadB64 = jwt.base64UrlEncode(JSON.stringify(decodedPayload));
const tamperedToken = `${parts[0]}.${tamperedPayloadB64}.${parts[2]}`; // Gabung dengan signature lama

console.log("Token Palsu yang dikirim Attacker:");
console.log(tamperedToken);

const verifyTampered = jwt.verifyToken(tamperedToken);
console.log(`-> Hasil Verifikasi Gateway: ${verifyTampered.error}\n`);


console.log("===================================================================");
console.log("🛠️  PENGUJIAN 2: PERLINDUNGAN TERHADAP L7 HTTP FLOOD (WAF SHIELD)");
console.log("===================================================================\n");

const waf = new L7WafShield(4); // Maksimal 4 request per detik dari 1 IP
const attackerIp = "198.51.100.77";

console.log(`Attacker (${attackerIp}) melancarkan serangan HTTP GET Flood ke /login:`);
for (let req = 1; req <= 6; req++) {
  const result = waf.inspectRequest(attackerIp);
  if (result.allowed) {
    console.log(`Req #${req}: ✅ Diteruskan ke Backend`);
  } else {
    console.log(`Req #${req}: ${result.reason}`);
  }
}

console.log("\n Kesimpulan:");
console.log("1. Tanda tangan kriptografis (HMAC SHA-256) menjamin integritas token (Tamper-Proof).");
console.log("2. Upaya eskalasi hak akses (privilege escalation) ditolak seketika oleh Gateway.");
console.log("3. WAF Layer 7 mampu mendeteksi HTTP Flood dan mem-blacklist IP penyerang secara otomatis.");
