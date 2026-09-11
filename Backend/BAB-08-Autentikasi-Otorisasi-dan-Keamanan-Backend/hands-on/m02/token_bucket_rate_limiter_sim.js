/**
 * SIMULATOR: TOKEN BUCKET RATE LIMITER & AES-256-GCM DEFENSIVE ENCRYPTION
 * Modul 02: OWASP API Security Top 10, Rate Limiting, & Kriptografi Defensif
 *
 * Mendemonstrasikan:
 * 1. Algoritma Token Bucket murni dengan kalkulasi fraksional isi ulang otomatis.
 * 2. Penanganan burst request & penolakan status HTTP 429 Too Many Requests.
 * 3. Enkripsi Terotentikasi AES-256-GCM (AEAD) untuk perlindungan data sensitif PII.
 * 4. Uji coba manipulasi bit ciphertext dan pembuktian deteksi tamper oleh Auth Tag.
 *
 * Jalankan: node token_bucket_rate_limiter_sim.js
 */

const crypto = require('crypto');

// =========================================================================
// BAGIAN 1: IMPLEMENTASI TOKEN BUCKET RATE LIMITER
// =========================================================================

class TokenBucketRateLimiter {
  constructor(capacity, refillRatePerSec) {
    this.capacity = capacity; // Batas maksimum token di dalam ember (Burst Capacity)
    this.refillRate = refillRatePerSec; // Berapa token ditambahkan per detik
    this.tokens = capacity; // Mulai dengan ember penuh
    this.lastRefill = Date.now();
  }

  _refill() {
    const now = Date.now();
    const elapsedSeconds = (now - this.lastRefill) / 1000;
    // Tambahkan token sesuai waktu yang telah berlalu
    const tokensToAdd = elapsedSeconds * this.refillRate;
    this.tokens = Math.min(this.capacity, this.tokens + tokensToAdd);
    this.lastRefill = now;
  }

  tryConsume(tokensNeeded = 1) {
    this._refill();

    if (this.tokens >= tokensNeeded) {
      this.tokens -= tokensNeeded;
      return {
        allowed: true,
        remainingTokens: Number(this.tokens.toFixed(2)),
        statusCode: 200
      };
    }

    // Hitung estimasi waktu tunggu (Retry-After) dalam detik
    const tokensMissing = tokensNeeded - this.tokens;
    const retryAfterSeconds = Math.ceil(tokensMissing / this.refillRate);

    return {
      allowed: false,
      remainingTokens: Number(this.tokens.toFixed(2)),
      statusCode: 429,
      retryAfterSeconds
    };
  }
}

// =========================================================================
// BAGIAN 2: ENKRIPSI TEROTENTIKASI AES-256-GCM (AEAD)
// =========================================================================

class DefensiveCryptoEngine {
  constructor() {
    // Generate Master Key 256-bit (32 bytes)
    this.masterKey = crypto.randomBytes(32);
  }

  encrypt(plaintext) {
    // IV (Initialization Vector) acak 12-byte (96-bit) standar GCM
    const iv = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv('aes-256-gcm', this.masterKey, iv);

    let encrypted = cipher.update(plaintext, 'utf8', 'hex');
    encrypted += cipher.final('hex');

    // Ambil 16-byte Authentication Tag
    const authTag = cipher.getAuthTag();

    return {
      iv: iv.toString('hex'),
      authTag: authTag.toString('hex'),
      ciphertext: encrypted,
      storagePayload: `${iv.toString('hex')}:${authTag.toString('hex')}:${encrypted}`
    };
  }

  decrypt(storagePayload) {
    const [ivHex, authTagHex, ciphertextHex] = storagePayload.split(':');
    if (!ivHex || !authTagHex || !ciphertextHex) {
      throw new Error('Payload ciphertext rusak atau tidak lengkap!');
    }

    const iv = Buffer.from(ivHex, 'hex');
    const authTag = Buffer.from(authTagHex, 'hex');
    const decipher = crypto.createDecipheriv('aes-256-gcm', this.masterKey, iv);

    // Pasang Auth Tag sebelum memanggil final()
    decipher.setAuthTag(authTag);

    let decrypted = decipher.update(ciphertextHex, 'hex', 'utf8');
    decrypted += decipher.final('utf8'); // Melempar exception jika data pernah termodifikasi!

    return decrypted;
  }
}

// =========================================================================
// BAGIAN 3: EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =========================================================================

async function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: TOKEN BUCKET RATE LIMITER & AES-256-GCM CIPHER ENGINE');
  console.log('='.repeat(75));

  // --- BAGIAN A: PENGUJIAN TOKEN BUCKET ---
  console.log('A. Pengujian Token Bucket Rate Limiter (Kapasitas = 5, Refill = 2 token/detik):');
  const limiter = new TokenBucketRateLimiter(5, 2);

  console.log('\nMengirim 8 Request Serentak (Burst Traffic):');
  for (let i = 1; i <= 8; i++) {
    const res = limiter.tryConsume(1);
    if (res.allowed) {
      console.log(`  [Req #${i}] HTTP ${res.statusCode} OK | Token Sisa: ${res.remainingTokens}`);
    } else {
      console.log(`  [Req #${i}] HTTP ${res.statusCode} TOO MANY REQUESTS | Kuota Habis! Coba lagi dalam ${res.retryAfterSeconds} detik.`);
    }
  }

  console.log('\nMenunggu 1.5 detik agar ember terisi ulang (1.5s x 2 token/s = +3 token)...');
  await new Promise(r => setTimeout(r, 1500));

  console.log('\nMengirim 3 Request Tambahan Pasca Isi Ulang:');
  for (let i = 9; i <= 11; i++) {
    const res = limiter.tryConsume(1);
    console.log(`  [Req #${i}] HTTP ${res.statusCode} ${res.allowed ? 'OK' : 'DENIED'} | Token Sisa: ${res.remainingTokens}`);
  }

  // --- BAGIAN B: PENGUJIAN ENKRIPSI AES-256-GCM ---
  console.log('\n' + '-'.repeat(75));
  console.log('B. Pengujian Enkripsi Data-at-Rest AES-256-GCM (AEAD):');
  console.log('-'.repeat(75));

  const cryptoEngine = new DefensiveCryptoEngine();
  const sensitivePII = JSON.stringify({
    patientId: 'PT-884192',
    name: 'Budi Santoso',
    creditCard: '4532-8812-9901-4452',
    medicalDiagnosis: 'Hipertensi Stadium 2 & Riwayat Penyakit Jantung Koroner'
  });

  console.log('1. Plaintext Data Sensitif Asli:');
  console.log(`   ${sensitivePII}`);

  console.log('\n2. Melakukan Enkripsi AES-256-GCM...');
  const encryptedResult = cryptoEngine.encrypt(sensitivePII);
  console.log(`   - IV (96-bit)   : ${encryptedResult.iv}`);
  console.log(`   - Auth Tag (16B): ${encryptedResult.authTag}`);
  console.log(`   - Ciphertext    : ${encryptedResult.ciphertext.substring(0, 60)}...`);
  console.log(`   - Stored in DB  : ${encryptedResult.storagePayload.substring(0, 70)}...`);

  console.log('\n3. Melakukan Dekripsi Sah (Authorized Read):');
  const decryptedText = cryptoEngine.decrypt(encryptedResult.storagePayload);
  console.log(`   ✅ Hasil Dekripsi: ${decryptedText}`);

  console.log('\n4. Simulasi Serangan: Peretas Memanipulasi 1 Karakter Ciphertext di Database!');
  // Ganti 1 karakter hex di tengah ciphertext
  const tamperedPayload = encryptedResult.storagePayload.slice(0, -5) + 'a1b2c';
  console.log(`   Payload termanipulasi: ${tamperedPayload.substring(0, 70)}...`);

  try {
    cryptoEngine.decrypt(tamperedPayload);
    console.log('   ❌ ERROR FATAL: Data termodifikasi berhasil didekripsi!');
  } catch (err) {
    console.log(`   🛡️ [PENYUSUPAN DIGAGALKAN] Auth Tag menolak data yang tidak otentik!`);
    console.log(`      Pesan Error Sistem: "${err.message}"`);
  }

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: Rate Limiter & Kriptografi Defensif teruji sempurna!');
  console.log('='.repeat(75));
}

main();
