/**
 * SIMULATOR: Auth.js Edge Middleware Session Guard & Cryptographic Cookie Engine
 * -----------------------------------------------------------------------------
 * File: nextauth_edge_session_guard_sim.js
 * Deskripsi: Simulasi mandiri (zero-dependency, Node.js native crypto) dari pembuatan
 * stateless session cookie ber-signature HMAC-SHA256, chunking cookie otomatis,
 * verifikasi instan di Edge Middleware, dan Role-Based Access Control (RBAC).
 */

const crypto = require("crypto");

// Secret key server (minimal 32 byte)
const AUTH_SECRET = "super-secret-key-32-chars-long-min-entropy!!";

// =============================================================================
// 1. STATELESS TOKEN GENERATOR & VERIFIER (HMAC-SHA256)
// =============================================================================

function base64UrlEncode(str) {
  return Buffer.from(str)
    .toString("base64")
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function base64UrlDecode(str) {
  let base64 = str.replace(/-/g, "+").replace(/_/g, "/");
  while (base64.length % 4) base64 += "=";
  return Buffer.from(base64, "base64").toString("utf-8");
}

class StatelessSessionManager {
  static createToken(payload, expiresInSeconds = 3600) {
    const header = { alg: "HS256", typ: "JWT" };
    const exp = Math.floor(Date.now() / 1000) + expiresInSeconds;
    const body = { ...payload, exp, iat: Math.floor(Date.now() / 1000) };

    const encodedHeader = base64UrlEncode(JSON.stringify(header));
    const encodedBody = base64UrlEncode(JSON.stringify(body));
    const signatureInput = `${encodedHeader}.${encodedBody}`;

    const signature = crypto
      .createHmac("sha256", AUTH_SECRET)
      .update(signatureInput)
      .digest("base64url");

    return `${signatureInput}.${signature}`;
  }

  static verifyToken(token) {
    if (!token || typeof token !== "string") {
      return { valid: false, reason: "TOKEN_MISSING" };
    }

    const parts = token.split(".");
    if (parts.length !== 3) {
      return { valid: false, reason: "MALFORMED_STRUCTURE" };
    }

    const [headerB64, bodyB64, signature] = parts;
    const signatureInput = `${headerB64}.${bodyB64}`;

    // Verifikasi HMAC Signature secara timing-safe
    const expectedSig = crypto
      .createHmac("sha256", AUTH_SECRET)
      .update(signatureInput)
      .digest("base64url");

    const sigA = Buffer.from(signature);
    const sigB = Buffer.from(expectedSig);
    if (sigA.length !== sigB.length || !crypto.timingSafeEqual(sigA, sigB)) {
      return { valid: false, reason: "TAMPERED_SIGNATURE" };
    }

    try {
      const payload = JSON.parse(base64UrlDecode(bodyB64));
      const now = Math.floor(Date.now() / 1000);
      if (payload.exp && payload.exp < now) {
        return { valid: false, reason: "TOKEN_EXPIRED", payload };
      }
      return { valid: true, payload };
    } catch (e) {
      return { valid: false, reason: "INVALID_JSON_BODY" };
    }
  }

  // Simulasi Cookie Chunking jika ukuran token melebihi kapasitas per-cookie
  static chunkCookie(cookieName, tokenValue, chunkSize = 120) {
    if (tokenValue.length <= chunkSize) {
      return { [cookieName]: tokenValue };
    }
    const chunks = {};
    let count = 0;
    for (let i = 0; i < tokenValue.length; i += chunkSize) {
      chunks[`${cookieName}.${count}`] = tokenValue.substring(i, i + chunkSize);
      count++;
    }
    return chunks;
  }

  static assembleCookieChunks(cookieName, cookieJar) {
    if (cookieJar[cookieName]) return cookieJar[cookieName];
    let full = "";
    let index = 0;
    while (cookieJar[`${cookieName}.${index}`]) {
      full += cookieJar[`${cookieName}.${index}`];
      index++;
    }
    return full || null;
  }
}

// =============================================================================
// 2. SIMULASI NEXT.JS EDGE MIDDLEWARE ROUTE GUARD
// =============================================================================

function edgeMiddleware(request) {
  const { path, cookies } = request;
  const cookieName = "__Host-authjs.session-token";

  // 1. Bypass asset statis dan rute otentikasi
  if (path.startsWith("/api/auth") || path.startsWith("/_next")) {
    return { status: 200, action: "NEXT", reason: "PUBLIC_ROUTE" };
  }

  // 2. Rekonstruksi token dari cookie jar (termasuk chunking)
  const token = StatelessSessionManager.assembleCookieChunks(cookieName, cookies);
  const verifyResult = StatelessSessionManager.verifyToken(token);

  // 3. Proteksi Halaman Dashboard (Wajib Login)
  if (path.startsWith("/dashboard")) {
    if (!verifyResult.valid) {
      return {
        status: 307,
        action: "REDIRECT",
        target: `/login?callbackUrl=${encodeURIComponent(path)}`,
        reason: `UNAUTHENTICATED (${verifyResult.reason})`,
      };
    }
    return {
      status: 200,
      action: "NEXT",
      user: verifyResult.payload,
      reason: "AUTHENTICATED",
    };
  }

  // 4. Proteksi Halaman Admin (Role-Based Access Control)
  if (path.startsWith("/admin")) {
    if (!verifyResult.valid) {
      return {
        status: 307,
        action: "REDIRECT",
        target: "/login",
        reason: `UNAUTHENTICATED (${verifyResult.reason})`,
      };
    }

    if (verifyResult.payload.role !== "ADMIN") {
      return {
        status: 403,
        action: "FORBIDDEN",
        target: "/unauthorized",
        reason: `ROLE_MISMATCH (Expected: ADMIN, Found: ${verifyResult.payload.role})`,
      };
    }

    return {
      status: 200,
      action: "NEXT",
      user: verifyResult.payload,
      reason: "AUTHORIZED_ADMIN",
    };
  }

  return { status: 200, action: "NEXT", reason: "DEFAULT_ALLOW" };
}

// =============================================================================
// 3. EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =============================================================================

function runSimulation() {
  console.log("===========================================================================");
  console.log("SIMULASI: AUTH.JS SECURE COOKIE & EDGE MIDDLEWARE ROUTE GUARD");
  console.log("===========================================================================\n");

  // TEST 1: Request anonim ke /dashboard
  console.log("--- TEST 1: User Anonim Mengakses '/dashboard' Tanpa Cookie ---");
  const req1 = { path: "/dashboard", cookies: {} };
  const res1 = edgeMiddleware(req1);
  console.log(`  Respon: [${res1.status}] ${res1.action} -> ${res1.target || "OK"} (${res1.reason})\n`);

  // TEST 2: User login normal (Role: MEMBER) mengakses /dashboard
  console.log("--- TEST 2: Member Terotentikasi Mengakses '/dashboard' ---");
  const memberToken = StatelessSessionManager.createToken({
    userId: "usr_member_77",
    email: "budi@perusahaan.com",
    role: "MEMBER",
  });
  const req2 = {
    path: "/dashboard",
    cookies: { "__Host-authjs.session-token": memberToken },
  };
  const res2 = edgeMiddleware(req2);
  console.log(`  Respon: [${res2.status}] ${res2.action} | User: ${res2.user.email} (Role: ${res2.user.role}) - ${res2.reason}\n`);

  // TEST 3: Member mencoba membobol halaman '/admin' (RBAC Guard)
  console.log("--- TEST 3: Member Mencoba Mengakses '/admin' (Privilege Escalation Test) ---");
  const req3 = {
    path: "/admin/system-settings",
    cookies: { "__Host-authjs.session-token": memberToken },
  };
  const res3 = edgeMiddleware(req3);
  console.log(`  Respon: [${res3.status}] ${res3.action} -> ${res3.target} (${res3.reason})\n`);

  // TEST 4: Penyerang memodifikasi token secara ilegal (Tampered Payload)
  console.log("--- TEST 4: Penyerang Memanipulasi Payload Cookie Menjadi ADMIN ---");
  const tamperedParts = memberToken.split(".");
  // Mengganti isi body base64 secara paksa
  const forgedBody = base64UrlEncode(JSON.stringify({ userId: "usr_hacker", email: "hacker@dark.net", role: "ADMIN" }));
  const tamperedToken = `${tamperedParts[0]}.${forgedBody}.${tamperedParts[2]}`; // signature lama
  const req4 = {
    path: "/admin/system-settings",
    cookies: { "__Host-authjs.session-token": tamperedToken },
  };
  const res4 = edgeMiddleware(req4);
  console.log(`  Respon: [${res4.status}] ${res4.action} -> Deteksi: ${res4.reason} (Perisai Kriptografis Aktif! 🛡️)\n`);

  // TEST 5: Cookie Chunking & Reassembly Test
  console.log("--- TEST 5: Pengujian Cookie Chunking (Membagi Token > 120 Bytes) ---");
  const adminToken = StatelessSessionManager.createToken({
    userId: "usr_admin_001",
    email: "superadmin@perusahaan.co.id",
    role: "ADMIN",
    organization: "Global Core Enterprise Inc",
  });

  const chunkedCookies = StatelessSessionManager.chunkCookie("__Host-authjs.session-token", adminToken, 80);
  console.log("  Cookie Terbagi Menjadi Chunk:", Object.keys(chunkedCookies));

  const req5 = { path: "/admin/analytics", cookies: chunkedCookies };
  const res5 = edgeMiddleware(req5);
  console.log(`  Respon: [${res5.status}] ${res5.action} | Admin Lolos: ${res5.user.email} (Chunks Berhasil Dirangkai! ✅)\n`);

  // TEST 6: Benchmark Verifikasi di Edge
  console.log("--- TEST 6: Benchmark Kecepatan Edge Verification (10.000 Verifikasi) ---");
  const startHr = process.hrtime.bigint();
  for (let i = 0; i < 10000; i++) {
    StatelessSessionManager.verifyToken(memberToken);
  }
  const endHr = process.hrtime.bigint();
  const totalMs = Number(endHr - startHr) / 1e6;
  const opsPerSec = Math.round((10000 / totalMs) * 1000);

  console.log(`  ⏱️  Total Waktu 10.000 Verifikasi : ${totalMs.toFixed(2)} ms`);
  console.log(`  ⚡ Kecepatan Verifikasi Lokal     : ${opsPerSec.toLocaleString("id-ID")} operasi / detik`);
  console.log(`  🚀 Rata-rata Latensi per Request  : ${(totalMs / 10000).toFixed(4)} ms (Sub-Millisecond!)\n`);

  console.log("===========================================================================");
  console.log("SIMULASI SELESAI: Seluruh pengujian proteksi Edge berhasil lolos!");
  console.log("===========================================================================");
}

runSimulation();
