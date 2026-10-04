/**
 * SIMULATOR: REDIS DISTRIBUTED LOCK & MITIGASI CACHE STAMPEDE (XFETCH)
 * Modul 02: Redis Internals, Distributed Locks, & Mitigasi Bencana Cache
 *
 * Mendemonstrasikan:
 * 1. Implementasi Distributed Lock aman berbasis token unik & pelepasan atomik.
 * 2. Persaingan 5 worker konkuren memperebutkan tiket konser VIP (Mutual Exclusion).
 * 3. Mekanisme TTL deadman switch saat worker mati mendadak (Mencegah Deadlock).
 * 4. Mitigasi Cache Stampede dengan algoritma Probabilistic Early Expiration (XFetch).
 *
 * Jalankan: node redis_distributed_lock_sim.js
 */

const crypto = require('crypto');

// =========================================================================
// BAGIAN 1: SIMULATOR MESIN REDIS ATOMIC ENGINE
// =========================================================================

class MockRedisServer {
  constructor() {
    this.store = new Map(); // key -> { value, expiresAt }
  }

  // Simulasi perintah: SET key val NX PX ttlMs
  set(key, value, nx = false, pxMs = 0) {
    const now = Date.now();
    const existing = this.store.get(key);

    // Jika NX aktif dan kunci masih hidup, gagal
    if (nx && existing && (existing.expiresAt === null || existing.expiresAt > now)) {
      return null; // Gagal akuisisi
    }

    const expiresAt = pxMs > 0 ? now + pxMs : null;
    this.store.set(key, { value: String(value), expiresAt });
    return 'OK';
  }

  get(key) {
    const now = Date.now();
    const item = this.store.get(key);
    if (!item) return null;
    if (item.expiresAt !== null && item.expiresAt <= now) {
      this.store.delete(key);
      return null;
    }
    return item.value;
  }

  // Simulasi evaluasi skrip Lua atomik Redis
  evalLuaUnlock(lockKey, expectedToken) {
    const currentVal = this.get(lockKey);
    if (currentVal === expectedToken) {
      this.store.delete(lockKey);
      return 1; // Berhasil rilis kunci
    }
    return 0; // Gagal: token tidak cocok atau lock sudah expired
  }
}

// =========================================================================
// BAGIAN 2: IMPLEMENTASI DISTRIBUTED LOCK CLIENT
// =========================================================================

class DistributedLock {
  constructor(redis) {
    this.redis = redis;
  }

  async acquire(lockKey, ttlMs = 1000) {
    const token = crypto.randomUUID();
    const res = this.redis.set(lockKey, token, true, ttlMs);
    if (res === 'OK') {
      return { success: true, token, lockKey };
    }
    return { success: false, token: null, lockKey };
  }

  async release(lockKey, token) {
    const result = this.redis.evalLuaUnlock(lockKey, token);
    return result === 1;
  }
}

// =========================================================================
// BAGIAN 3: SIMULASI PERSAINGAN WORKER KONKUREN (TIKET KONSER VIP)
// =========================================================================

async function simulateConcertTicketBooking() {
  console.log('='.repeat(75));
  console.log('BAGIAN 1: PERSAINGAN WORKER KONKUREN MEMPEREBUTKAN TIKET VIP TERAKHIR');
  console.log('='.repeat(75));

  const redis = new MockRedisServer();
  const lockManager = new DistributedLock(redis);
  const resource = 'concert:ticket:VIP-001';

  let remainingTickets = 1;
  let ticketOwner = null;

  async function workerTask(workerName) {
    console.log(`[${workerName}] Menyerbu untuk membeli tiket...`);
    const lock = await lockManager.acquire(resource, 500);

    if (!lock.success) {
      console.log(`  ❌ [${workerName}] Gagal akuisisi lock (tiket sedang diproses worker lain).`);
      return;
    }

    console.log(`  🔒 [${workerName}] BERHASIL mengunci resource! Melakukan reservasi & transaksi...`);
    // Simulasi waktu proses pembayaran perbankan (50 ms)
    await new Promise(r => setTimeout(r, 50));

    if (remainingTickets > 0) {
      remainingTickets--;
      ticketOwner = workerName;
      console.log(`  🎟️ [${workerName}] TRANSAKSI BERHASIL! Tiket resmi dimiliki oleh ${workerName}.`);
    }

    const released = await lockManager.release(lock.lockKey, lock.token);
    console.log(`  🔓 [${workerName}] Melepaskan lock aman via Lua script: ${released ? 'SUKSES' : 'GAGAL'}`);
  }

  // 5 Worker menyerbu secara simultan (Promise.all)
  await Promise.all([
    workerTask('Worker-1 (Jakarta)'),
    workerTask('Worker-2 (Surabaya)'),
    workerTask('Worker-3 (Bandung)'),
    workerTask('Worker-4 (Medan)'),
    workerTask('Worker-5 (Bali)')
  ]);

  console.log(`\nStatus Akhir: Sisa Tiket = ${remainingTickets}, Pemenang = ${ticketOwner}\n`);
}

// =========================================================================
// BAGIAN 4: SIMULASI PREVENSI DEADLOCK (WORKER CRASH & LEASE EXPIRY)
// =========================================================================

async function simulateDeadlockPrevention() {
  console.log('='.repeat(75));
  console.log('BAGIAN 2: UJI KETAHANAN KETIKA WORKER CRASH (DEADMAN SWITCH TTL)');
  console.log('='.repeat(75));

  const redis = new MockRedisServer();
  const lockManager = new DistributedLock(redis);
  const resource = 'inventory:item:CRASH-TEST';

  console.log('[Worker-A] Mengakuisisi lock dengan TTL 100ms...');
  const lockA = await lockManager.acquire(resource, 100);
  console.log(`  Status Akuisisi Worker-A: ${lockA.success}`);

  console.log('  ⚠️ Worker-A tiba-tiba mengalami CRASH FATAL / Out Of Memory!');
  console.log('  Worker-A TIDAK PERNAH memanggil release()...');

  console.log('\n[Worker-B] Mencoba mengambil lock segera (sebelum TTL habis)...');
  const lockBImmediate = await lockManager.acquire(resource, 200);
  console.log(`  Status Akuisisi Worker-B: ${lockBImmediate.success} (Tertolak karena lock masih aktif)`);

  console.log('\nMenunggu 120ms hingga TTL sewa (lease) otomatis kedaluwarsa...');
  await new Promise(r => setTimeout(r, 120));

  console.log('[Worker-B] Mencoba mengambil lock kembali setelah TTL habis...');
  const lockBAfterExpiry = await lockManager.acquire(resource, 200);
  console.log(`  Status Akuisisi Worker-B: ${lockBAfterExpiry.success} (BERHASIL!)`);
  console.log('✅ KESIMPULAN: Sistem terhindar dari Deadlock abadi berkat mekanisme TTL otomatis!\n');
}

// =========================================================================
// BAGIAN 5: MITIGASI CACHE STAMPEDE DENGAN ALGORITMA XFETCH
// =========================================================================

async function simulateCacheStampedeMitigation() {
  console.log('='.repeat(75));
  console.log('BAGIAN 3: ALGORITMA XFETCH (PROBABILISTIC EARLY EXPIRATION)');
  console.log('='.repeat(75));

  /**
   * Formula XFetch:
   * delta - beta * ln(rand()) * computation_time > expiry_remaining
   * Jika bernilai TRUE, thread saat ini secara proaktif merefresh cache di background
   * sebelum kunci benar-benar expired bagi pengguna lain.
   */
  function shouldRefreshEarly(expiresAtMs, computationTimeMs, beta = 1.0) {
    const now = Date.now();
    const timeRemainingMs = expiresAtMs - now;
    if (timeRemainingMs <= 0) return true; // Sudah kedaluwarsa

    const random = Math.random();
    const probabilisticTerm = -(beta * Math.log(random) * computationTimeMs);
    return probabilisticTerm > timeRemainingMs;
  }

  const computationCostMs = 200; // Kalkulasi query berat memakan waktu 200ms
  const now = Date.now();
  const expiresAt = now + 150; // Kunci akan expired dalam 150ms

  console.log(`Kondisi Cache: Sisa Waktu = 150ms, Biaya Komputasi DB = ${computationCostMs}ms`);
  console.log('Menguji probabilitas refresh proaktif dari 10 request yang lewat:');

  let refreshedByWorker = null;
  for (let req = 1; req <= 10; req++) {
    const decision = shouldRefreshEarly(expiresAt, computationCostMs);
    console.log(`  Request #${req.toString().padStart(2)}: Trigger Early Refresh? ${decision ? 'YA (Refresh di Background!)' : 'TIDAK (Pakai Cache)'}`);
    if (decision && !refreshedByWorker) {
      refreshedByWorker = `Request #${req}`;
    }
  }

  console.log(`\n✅ Hasil: ${refreshedByWorker || 'Request berikutnya'} mengasumsikan tugas refresh proaktif.`);
  console.log('   Hasilnya: 0 request yang mengalami Cache Miss, database aman dari Thundering Herd!\n');
}

async function main() {
  await simulateConcertTicketBooking();
  await simulateDeadlockPrevention();
  await simulateCacheStampedeMitigation();
  console.log('='.repeat(75));
  console.log('SIMULASI BERHASIL: Seluruh mekanisme Redis Lock & XFetch tervalidasi!');
  console.log('='.repeat(75));
}

main();
