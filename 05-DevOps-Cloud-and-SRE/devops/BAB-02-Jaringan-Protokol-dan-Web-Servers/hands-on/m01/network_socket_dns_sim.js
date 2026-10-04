/**
 * Hands-on M01: DNS Resolution, TCP 3-Way Handshake, & TLS Certificate Validator Simulator
 * Mengilustrasikan konsep:
 * 1. DNS Cache Hierarchy dengan TTL Expiration
 * 2. Simulasi TCP Three-Way Handshake (SYN -> SYN-ACK -> ACK)
 * 3. Validasi Sertifikat SSL/TLS & SNI (Server Name Indication)
 *
 * Jalankan: node network_socket_dns_sim.js
 */

const crypto = require('crypto');

const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m'
};

// ==========================================
// 1. DNS CACHE & RESOLVER SIMULATOR
// ==========================================
class SimulatedDnsResolver {
  constructor() {
    this.cache = new Map();
    // Basis data Authoritative Nameserver upstream
    this.authoritativeDb = {
      'api.ecommerce.com': { ip: '104.21.55.2', ttlSec: 2 },
      'db.internal.vpc': { ip: '10.0.1.100', ttlSec: 10 },
      'cdn.assets.io': { ip: '151.101.65.140', ttlSec: 5 }
    };
  }

  async resolve(hostname) {
    const now = Date.now();

    // 1. Cek cache lokal
    if (this.cache.has(hostname)) {
      const entry = this.cache.get(hostname);
      if (now < entry.expiresAt) {
        console.log(`  ${colors.green}[DNS CACHE HIT]${colors.reset} ${hostname} -> ${entry.ip} (Sisa TTL: ${Math.round((entry.expiresAt - now) / 1000)}s)`);
        return entry.ip;
      }
      console.log(`  ${colors.yellow}[DNS CACHE EXPIRED]${colors.reset} TTL untuk ${hostname} telah kedaluwarsa.`);
    }

    // 2. Query ke Authoritative Nameserver
    console.log(`  ${colors.cyan}[DNS RECURSIVE QUERY]${colors.reset} Bertanya ke Authoritative Nameserver untuk: ${hostname}...`);
    await new Promise(r => setTimeout(r, 150)); // Latency query 150ms

    const record = this.authoritativeDb[hostname];
    if (!record) {
      throw new Error(`NXDOMAIN: Domain "${hostname}" tidak ditemukan di DNS records.`);
    }

    // Simpan di cache
    this.cache.set(hostname, {
      ip: record.ip,
      expiresAt: now + (record.ttlSec * 1000)
    });

    console.log(`  ${colors.green}[DNS RESOLVED]${colors.reset} ${hostname} -> ${record.ip} (Cached with TTL: ${record.ttlSec}s)`);
    return record.ip;
  }
}

// ==========================================
// 2. TCP 3-WAY HANDSHAKE SIMULATOR
// ==========================================
class SimulatedTcpStack {
  static async establishConnection(targetIp, port) {
    console.log(`\n${colors.bold}${colors.magenta}=== MEMULAI TCP 3-WAY HANDSHAKE ke ${targetIp}:${port} ===${colors.reset}`);
    const rttOneWayMs = 25;

    // Step 1: SYN (Client -> Server)
    const clientSeq = Math.floor(Math.random() * 100000);
    console.log(`  [STEP 1] Client --- SYN (seq=${clientSeq}) ---> Server:${port}`);
    await new Promise(r => setTimeout(r, rttOneWayMs));

    // Step 2: SYN-ACK (Server -> Client)
    const serverSeq = Math.floor(Math.random() * 200000);
    const serverAck = clientSeq + 1;
    console.log(`  [STEP 2] Client <--- SYN-ACK (seq=${serverSeq}, ack=${serverAck}) --- Server:${port}`);
    await new Promise(r => setTimeout(r, rttOneWayMs));

    // Step 3: ACK (Client -> Server)
    const clientAck = serverSeq + 1;
    console.log(`  [STEP 3] Client --- ACK (ack=${clientAck}) ---> Server:${port}`);
    await new Promise(r => setTimeout(r, rttOneWayMs));

    console.log(`${colors.green}[TCP CONNECTED] Koneksi 2-arah terbuka penuh (Total Handshake Latency: ${rttOneWayMs * 3}ms)${colors.reset}\n`);
    return {
      connected: true,
      socketId: `sock_${clientSeq}_${serverSeq}`
    };
  }
}

// ==========================================
// 3. TLS CERTIFICATE & SNI VALIDATOR
// ==========================================
class TlsCertificateValidator {
  static validate(hostname, certInfo) {
    console.log(`\n${colors.cyan}[TLS VALIDATOR] Memeriksa Sertifikat SSL/TLS untuk SNI: "${hostname}"...${colors.reset}`);
    const now = new Date();

    // 1. Cek masa kedaluwarsa
    if (now > certInfo.validTo) {
      return {
        valid: false,
        error: `Sertifikat kedaluwarsa pada ${certInfo.validTo.toISOString()}!`
      };
    }

    // 2. Cek kecocokan Subject Alternative Name (SAN)
    const matchesDomain = certInfo.sans.some(san => {
      if (san.startsWith('*.')) {
        const rootDomain = san.replace('*.', '');
        return hostname.endsWith(rootDomain);
      }
      return san === hostname;
    });

    if (!matchesDomain) {
      return {
        valid: false,
        error: `Hostname mismatch! Sertifikat diterbitkan untuk [${certInfo.sans.join(', ')}] tetapi diakses via "${hostname}".`
      };
    }

    return {
      valid: true,
      protocol: 'TLS 1.3',
      cipherSuite: 'TLS_AES_256_GCM_SHA384',
      issuer: certInfo.issuer,
      daysRemaining: Math.round((certInfo.validTo - now) / (1000 * 60 * 60 * 24))
    };
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS NETWORK LAB: DNS, TCP, & TLS SIMULATOR ===${colors.reset}\n`);

  const dns = new SimulatedDnsResolver();

  // 1. Uji Coba DNS Resolution & TTL Caching
  console.log('--- 1. UJI COBA RESOLUSI DNS & TTL ---');
  const ip1 = await dns.resolve('api.ecommerce.com');
  console.log(`Hasil IP: ${ip1}`);

  // Query kedua (harus cache hit)
  const ip2 = await dns.resolve('api.ecommerce.com');
  console.log(`Hasil IP: ${ip2}`);

  // 2. Uji Coba TCP 3-Way Handshake
  console.log('\n--- 2. UJI COBA TCP 3-WAY HANDSHAKE ---');
  const tcpSession = await SimulatedTcpStack.establishConnection(ip1, 443);

  // 3. Uji Coba TLS Certificate Validation
  console.log('--- 3. UJI COBA VALIDASI SERTIFIKAT TLS 1.3 ---');
  const validCert = {
    issuer: "Let's Encrypt Authority X3",
    sans: ['*.ecommerce.com', 'ecommerce.com'],
    validFrom: new Date(Date.now() - 30 * 24 * 3600 * 1000),
    validTo: new Date(Date.now() + 60 * 24 * 3600 * 1000) // Masih berlaku 60 hari
  };

  const check1 = TlsCertificateValidator.validate('api.ecommerce.com', validCert);
  if (check1.valid) {
    console.log(`${colors.green}[TLS STATUS OK]${colors.reset} Enkripsi Aktif (${check1.protocol}) - Sisa Masa Berlaku: ${check1.daysRemaining} hari.`);
  }

  // Uji coba sertifikat expired
  const expiredCert = {
    issuer: "DigiCert Global Root",
    sans: ['api.ecommerce.com'],
    validTo: new Date(Date.now() - 5 * 24 * 3600 * 1000) // Kedaluwarsa 5 hari lalu
  };
  const check2 = TlsCertificateValidator.validate('api.ecommerce.com', expiredCert);
  if (!check2.valid) {
    console.log(`${colors.red}[TLS BLOCKED] Kegagalan Sertifikat:${colors.reset} ${check2.error}`);
  }

  // Uji coba domain mismatch
  const mismatchCert = {
    issuer: "Cloudflare Inc",
    sans: ['another-site.org'],
    validTo: new Date(Date.now() + 90 * 24 * 3600 * 1000)
  };
  const check3 = TlsCertificateValidator.validate('api.ecommerce.com', mismatchCert);
  if (!check3.valid) {
    console.log(`${colors.red}[TLS BLOCKED] Hostname Mismatch:${colors.reset} ${check3.error}`);
  }

  console.log(`\n${colors.bold}${colors.green}=== SEMUA PENGUJIAN JARINGAN (DNS, TCP, TLS) SELESAI SUKSES ===${colors.reset}`);
}

runLab();
