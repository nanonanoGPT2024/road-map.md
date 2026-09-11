/**
 * SIMULATOR: OAUTH 2.0 PKCE FLOW, JWT ENGINE & ABAC POLICY VALIDATOR
 * Modul 01: Autentikasi Modern, JWT vs Session, OAuth 2.0 PKCE, & RBAC/ABAC
 *
 * Mendemonstrasikan:
 * 1. Pembangkitan Code Verifier & Code Challenge (SHA256 Base64URL).
 * 2. Pertukaran Kredensial OAuth 2.0 PKCE resmi vs Simulasi Serangan Intersepsi Man-in-the-Middle.
 * 3. Mesin Pembuatan & Verifikasi JWT Timing-Safe HMAC-SHA256.
 * 4. Mesin Otorisasi ABAC (Attribute-Based Access Control) multi-dimensi.
 *
 * Jalankan: node oauth2_pkce_auth_flow_sim.js
 */

const crypto = require('crypto');

function base64UrlEncode(buffer) {
  return buffer.toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

// =========================================================================
// BAGIAN 1: OAUTH 2.0 WITH PKCE (PROOF KEY FOR CODE EXCHANGE)
// =========================================================================

class PKCEHelper {
  static generateVerifier() {
    return base64UrlEncode(crypto.randomBytes(32));
  }

  static generateChallenge(verifier) {
    const hash = crypto.createHash('sha256').update(verifier).digest();
    return base64UrlEncode(hash);
  }
}

class MockOAuthAuthorizationServer {
  constructor() {
    this.authCodes = new Map(); // code -> { clientId, codeChallenge, userId, expiresAt }
    this.secretKey = 'super-secret-enterprise-jwt-signing-key-2026';
  }

  // Langkah 1: Client meminta auth code dengan code_challenge
  requestAuthCode(clientId, codeChallenge, userId) {
    const authCode = `authcode_${crypto.randomBytes(16).toString('hex')}`;
    this.authCodes.set(authCode, {
      clientId,
      codeChallenge,
      userId,
      expiresAt: Date.now() + 60000 // Berlaku 1 menit
    });
    return authCode;
  }

  // Langkah 2: Client menukarkan auth code + code_verifier asli
  exchangeCodeForTokens(authCode, codeVerifier, clientId) {
    const record = this.authCodes.get(authCode);
    if (!record) {
      throw new Error('Kode otorisasi tidak valid atau sudah kedaluwarsa!');
    }

    if (record.clientId !== clientId) {
      throw new Error('Client ID tidak cocok dengan peminta awal!');
    }

    // Hanguskan auth code segera setelah dipakai (One-time Use)
    this.authCodes.delete(authCode);

    // Verifikasi PKCE: SHA256(verifier) harus sama persis dengan challenge awal
    const calculatedChallenge = PKCEHelper.generateChallenge(codeVerifier);
    if (calculatedChallenge !== record.codeChallenge) {
      throw new Error('PKCE Verification GAGAL: Code Verifier tidak cocok dengan Challenge!');
    }

    // Terbitkan Access Token (JWT)
    const tokenPayload = {
      sub: record.userId,
      aud: 'https://api.enterprise.com',
      iss: 'https://auth.enterprise.com',
      role: record.userId === 'USR-99' ? 'DOCTOR' : 'PATIENT',
      department: 'CARDIOLOGY',
      exp: Math.floor(Date.now() / 1000) + 900 // 15 Menit
    };

    const accessToken = createJWT(tokenPayload, this.secretKey);
    const refreshToken = `ref_${crypto.randomBytes(24).toString('hex')}`;

    return {
      tokenType: 'Bearer',
      expiresIn: 900,
      accessToken,
      refreshToken
    };
  }
}

// =========================================================================
// BAGIAN 2: MESIN JWT (SIGNING & TIMING-SAFE VERIFICATION)
// =========================================================================

function createJWT(payload, secretKey) {
  const header = { alg: 'HS256', typ: 'JWT' };
  const encodedHeader = base64UrlEncode(Buffer.from(JSON.stringify(header)));
  const encodedPayload = base64UrlEncode(Buffer.from(JSON.stringify(payload)));
  const data = `${encodedHeader}.${encodedPayload}`;

  const signature = base64UrlEncode(
    crypto.createHmac('sha256', secretKey).update(data).digest()
  );

  return `${data}.${signature}`;
}

function verifyJWT(token, secretKey) {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('JWT struktur tidak valid');

  const [encodedHeader, encodedPayload, signature] = parts;
  const data = `${encodedHeader}.${encodedPayload}`;

  const expectedSignature = base64UrlEncode(
    crypto.createHmac('sha256', secretKey).update(data).digest()
  );

  // Timing safe compare untuk mencegah Side-Channel Timing Attacks
  const sigBuf = Buffer.from(signature);
  const expBuf = Buffer.from(expectedSignature);

  if (sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)) {
    throw new Error('JWT Signature Tidak Cocok! Token telah dimanipulasi!');
  }

  const payload = JSON.parse(Buffer.from(encodedPayload, 'base64').toString('utf-8'));
  if (payload.exp && Math.floor(Date.now() / 1000) > payload.exp) {
    throw new Error('JWT telah Expired!');
  }

  return payload;
}

// =========================================================================
// BAGIAN 3: MESIN OTORISASI ABAC (ATTRIBUTE-BASED ACCESS CONTROL)
// =========================================================================

class ABACPolicyEngine {
  /**
   * Kebijakan: Dokter boleh melihat rekam medis jika berasal dari departemen
   * yang sama DAN jam akses berada di jam dinas (08:00 - 18:00).
   */
  static evaluateAccess(subject, resource, action, environment) {
    // 1. Super Admin selalu diizinkan
    if (subject.role === 'SUPER_ADMIN') return { allowed: true, reason: 'Super Admin Override' };

    // 2. Pasien hanya boleh membaca rekam medis milik dirinya sendiri
    if (subject.role === 'PATIENT') {
      if (action === 'READ' && resource.patientId === subject.userId) {
        return { allowed: true, reason: 'Pasien mengakses berkas pribadinya' };
      }
      return { allowed: false, reason: 'Pasien dilarang melihat data pasien lain' };
    }

    // 3. Dokter mengakses rekam medis
    if (subject.role === 'DOCTOR') {
      // Evaluasi atribut departemen
      if (subject.department !== resource.department) {
        return { allowed: false, reason: `Departemen dokter (${subject.department}) tidak cocok dengan berkas (${resource.department})` };
      }
      // Evaluasi atribut lingkungan (Jam Kerja)
      if (environment.hourOfDay < 8 || environment.hourOfDay > 18) {
        return { allowed: false, reason: `Akses ditolak di luar jam operasional rumah sakit (${environment.hourOfDay}:00)` };
      }
      return { allowed: true, reason: 'Dokter berhak membaca berkas spesialisasi pada jam dinas' };
    }

    return { allowed: false, reason: 'Peran tidak dikenali' };
  }
}

// =========================================================================
// BAGIAN 4: EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =========================================================================

async function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: OAUTH 2.0 PKCE, JWT SECURITY & ABAC POLICY ENGINE');
  console.log('='.repeat(75));

  const authServer = new MockOAuthAuthorizationServer();
  const clientId = 'my-mobile-health-app';

  // 1. Pembangkitan Kunci PKCE di Perangkat Mobile
  console.log('1. Klien Mobile Menyiapkan Kriptografi PKCE:');
  const codeVerifier = PKCEHelper.generateVerifier();
  const codeChallenge = PKCEHelper.generateChallenge(codeVerifier);
  console.log(`  - Code Verifier (Rahasia di Mobile) : ${codeVerifier}`);
  console.log(`  - Code Challenge (SHA256 Base64URL) : ${codeChallenge}`);

  // 2. Meminta Kode Otorisasi
  console.log('\n2. Meminta Kode Otorisasi ke Auth Server...');
  const authCode = authServer.requestAuthCode(clientId, codeChallenge, 'USR-99');
  console.log(`  - Kode Otorisasi Diterbitkan : ${authCode}`);

  // 3. Serangan Intersepsi Man-In-The-Middle (Attacker mencuri auth code dari URL)
  console.log('\n3. Simulasi Serangan: Peretas Mencuri Auth Code dari URL Redirect:');
  try {
    const fakeVerifier = PKCEHelper.generateVerifier(); // Peretas tidak punya verifier asli
    console.log(`  Peretas mencoba menukarkan authCode dengan Verifier Palsu: ${fakeVerifier}`);
    authServer.exchangeCodeForTokens(authCode, fakeVerifier, clientId);
  } catch (err) {
    console.log(`  🛡️ [SERANGAN DITANGKIS] Server menolak pertukaran: ${err.message}`);
  }

  // 4. Pertukaran Sah oleh Pemilik Asli
  console.log('\n4. Klien Sah Menukarkan Auth Code dengan Code Verifier Asli:');
  // Karena auth code hangus setelah dipakai (bahkan saat gagal), generate baru untuk klien sah
  const validAuthCode = authServer.requestAuthCode(clientId, codeChallenge, 'USR-99');
  const tokenResponse = authServer.exchangeCodeForTokens(validAuthCode, codeVerifier, clientId);
  console.log(`  ✅ [PERTUKARAN SUKSES] Diterbitkan Token JWT:`);
  console.log(`     Access Token : ${tokenResponse.accessToken.substring(0, 45)}...`);
  console.log(`     Refresh Token: ${tokenResponse.refreshToken}`);

  // 5. Verifikasi Integritas JWT & Uji Tampering
  console.log('\n5. Verifikasi Signature JWT & Deteksi Pemalsuan Data:');
  const verifiedUser = verifyJWT(tokenResponse.accessToken, authServer.secretKey);
  console.log(`  - Payload Terverifikasi : User=${verifiedUser.sub}, Role=${verifiedUser.role}, Dept=${verifiedUser.department}`);

  // Coba modifikasi role menjadi SUPER_ADMIN
  console.log('  Mencoba memanipulasi payload token menjadi SUPER_ADMIN tanpa private key...');
  const tamperedToken = tokenResponse.accessToken.replace('.eyJ', '.eyF');
  try {
    verifyJWT(tamperedToken, authServer.secretKey);
  } catch (err) {
    console.log(`  🛡️ [TAMPERING DETECTED] ${err.message}`);
  }

  // 6. Pengujian Otorisasi Berbasis Atribut (ABAC)
  console.log('\n6. Evaluasi Kebijakan Otorisasi ABAC:');
  const medicalRecord = { id: 'REC-101', patientId: 'USR-88', department: 'CARDIOLOGY' };

  // Kasus A: Dokter mengakses pada pukul 14:00 (Jam Kerja)
  const eval1 = ABACPolicyEngine.evaluateAccess(
    { userId: verifiedUser.sub, role: verifiedUser.role, department: verifiedUser.department },
    medicalRecord,
    'READ',
    { hourOfDay: 14 }
  );
  console.log(`  Kasus A (Dokter Jam 14:00): ${eval1.allowed ? '✅ IZINKAN' : '❌ TOLAK'} (${eval1.reason})`);

  // Kasus B: Dokter mengakses pada pukul 23:00 (Luar Jam Kerja)
  const eval2 = ABACPolicyEngine.evaluateAccess(
    { userId: verifiedUser.sub, role: verifiedUser.role, department: verifiedUser.department },
    medicalRecord,
    'READ',
    { hourOfDay: 23 }
  );
  console.log(`  Kasus B (Dokter Jam 23:00): ${eval2.allowed ? '✅ IZINKAN' : '❌ TOLAK'} (${eval2.reason})`);

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: OAuth 2.0 PKCE, JWT & ABAC Engine berjalan sempurna!');
  console.log('='.repeat(75));
}

main();
