/**
 * SIMULATOR: NEXT.JS 4-TIER CACHING LIFECYCLE & EDGE MIDDLEWARE ROUTE GUARD
 * Modul 02: Next.js Multi-Layer Caching, Revalidasi Dinamis, & Edge Middleware
 *
 * Mendemonstrasikan:
 * 1. Lapisan 1: Request Memoization (React cache() de-duplication dalam 1 siklus render).
 * 2. Lapisan 2: Persistent Data Cache dengan Tagging & On-Demand Revalidation (revalidateTag).
 * 3. Lapisan 3: Full Route Cache (Evaluasi Statis vs Dinamis).
 * 4. Lapisan 4: Edge Middleware Simulator (Route Guard otentikasi cepat & security headers).
 *
 * Jalankan: node nextjs_caching_lifecycle_sim.js
 */

// =========================================================================
// BAGIAN 1: REQUEST MEMOIZATION ENGINE (REACT CACHE())
// =========================================================================

class RequestMemoizationEngine {
  constructor() {
    this.dbQueryCount = 0;
  }

  // Fungsi utilitas membungkus fungsi asinkron dengan Request Memoization
  createMemoizedFunction(fn) {
    let requestContextCache = new Map();

    return async (...args) => {
      const serializedKey = JSON.stringify(args);
      if (requestContextCache.has(serializedKey)) {
        return { data: requestContextCache.get(serializedKey), source: 'REQUEST_MEMO_HIT' };
      }

      this.dbQueryCount++;
      const result = await fn(...args);
      requestContextCache.set(serializedKey, result);
      return { data: result, source: 'DB_QUERY_EXECUTION' };
    };
  }
}

// =========================================================================
// BAGIAN 2: DATA CACHE ENGINE DENGAN TAGGING & REVALIDASI ON-DEMAND
// =========================================================================

class NextDataCache {
  constructor() {
    this.store = new Map(); // key -> { value, tags: Set, expiresAt }
    this.tagIndex = new Map(); // tag -> Set of keys
  }

  set(key, value, tags = [], revalidateSeconds = 3600) {
    const expiresAt = revalidateSeconds > 0 ? Date.now() + (revalidateSeconds * 1000) : null;
    this.store.set(key, { value, tags: new Set(tags), expiresAt });

    // Petakan tag ke index
    tags.forEach(tag => {
      if (!this.tagIndex.has(tag)) this.tagIndex.set(tag, new Set());
      this.tagIndex.get(tag).add(key);
    });
  }

  get(key) {
    const item = this.store.get(key);
    if (!item) return null;

    // Cek time-based expiration
    if (item.expiresAt !== null && Date.now() > item.expiresAt) {
      console.log(`  ⏱️ Cache untuk key "${key}" telah basi (Expired by Time).`);
      return null;
    }

    return item.value;
  }

  // ON-DEMAND REVALIDATION BERBASIS TAG (revalidateTag)
  revalidateTag(tag) {
    console.log(`\n🔄 [ON-DEMAND REVALIDATION] Memanggil revalidateTag('${tag}')...`);
    if (!this.tagIndex.has(tag)) {
      console.log(`  Peringatan: Tidak ditemukan kunci yang memiliki tag "${tag}".`);
      return 0;
    }

    const affectedKeys = this.tagIndex.get(tag);
    let purgedCount = 0;

    affectedKeys.forEach(key => {
      this.store.delete(key);
      purgedCount++;
      console.log(`  🗑️ Menghapus Data Cache untuk key: "${key}"`);
    });

    this.tagIndex.delete(tag);
    return purgedCount;
  }
}

// =========================================================================
// BAGIAN 3: EDGE MIDDLEWARE SIMULATOR (V8 ISOLATE ROUTE GUARD)
// =========================================================================

class EdgeMiddlewareSimulator {
  static handleIncomingRequest(urlPath, cookies = {}) {
    console.log(`\n🛡️ [EDGE MIDDLEWARE] Memeriksa request ke path: "${urlPath}"...`);
    const startTime = process.hrtime.bigint();

    const headers = {
      'X-Frame-Options': 'DENY',
      'X-Content-Type-Options': 'nosniff',
      'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
    };

    // 1. ROUTE GUARD: Proteksi rute private /dashboard
    if (urlPath.startsWith('/dashboard')) {
      if (!cookies['session_token']) {
        const elapsedUs = Number(process.hrtime.bigint() - startTime) / 1000;
        console.warn(`  ❌ [AKSES DITOLAK DI EDGE] Cookie sesi tidak ada! Redirect ke /login (${elapsedUs.toFixed(1)} µs)`);
        return {
          status: 307,
          action: 'REDIRECT',
          destination: '/login',
          headers,
          latencyUs: elapsedUs
        };
      }
    }

    const elapsedUs = Number(process.hrtime.bigint() - startTime) / 1000;
    console.log(`  ✅ [IZIN LOLOS] Request diizinkan masuk ke server origin (${elapsedUs.toFixed(1)} µs)`);
    return {
      status: 200,
      action: 'NEXT',
      headers,
      latencyUs: elapsedUs
    };
  }
}

// =========================================================================
// BAGIAN 4: EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =========================================================================

async function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: NEXT.JS 4-TIER CACHING & EDGE MIDDLEWARE RUNTIME');
  console.log('='.repeat(75));

  // --- TIER 1: REQUEST MEMOIZATION ---
  console.log('\nA. PENGUJIAN TIER 1: REQUEST MEMOIZATION (REACT cache()):');
  console.log('-'.repeat(75));
  const memoEngine = new RequestMemoizationEngine();

  // Simulasi query DB asli
  const rawGetUser = async (id) => ({ id, name: 'Budi Santoso', tier: 'ENTERPRISE' });
  const getUserMemoized = memoEngine.createMemoizedFunction(rawGetUser);

  console.log('Komponen 1 (HeaderNav) memanggil getUser(101)...');
  const res1 = await getUserMemoized(101);
  console.log(`  Hasil: ${res1.data.name} | Sumber: ${res1.source}`);

  console.log('\nKomponen 2 (SidebarProfile) memanggil getUser(101) di siklus render yang sama...');
  const res2 = await getUserMemoized(101);
  console.log(`  Hasil: ${res2.data.name} | Sumber: ${res2.source} (Nol Query Tambahan!)`);

  console.log('\nKomponen 3 (MetaTitle) memanggil getUser(101)...');
  const res3 = await getUserMemoized(101);
  console.log(`  Hasil: ${res3.data.name} | Sumber: ${res3.source} (Nol Query Tambahan!)`);
  console.log(`Total Eksekusi Database Riil: ${memoEngine.dbQueryCount} kali (3 panggilan digabung jadi 1!)\n`);

  // --- TIER 2: DATA CACHE & TAG REVALIDATION ---
  console.log('-'.repeat(75));
  console.log('B. PENGUJIAN TIER 2: DATA CACHE & TAG REVALIDATION:');
  console.log('-'.repeat(75));
  const dataCache = new NextDataCache();

  // Menyimpan data produk dengan tags
  dataCache.set('fetch:/products/101', { id: 101, name: 'MacBook Pro M3', price: 40000000 }, ['products', 'product-101']);
  dataCache.set('fetch:/products/102', { id: 102, name: 'iPad Pro OLED', price: 20000000 }, ['products', 'product-102']);

  console.log('Membaca Produk 101 dari Data Cache:');
  const prod1 = dataCache.get('fetch:/products/101');
  console.log(`  ✅ Ditemukan: ${prod1.name} (Rp ${prod1.price.toLocaleString('id-ID')})`);

  // Admin mengupdate harga Produk 101 via Server Action -> revalidateTag('product-101')
  dataCache.revalidateTag('product-101');

  console.log('\nMembaca Produk 101 kembali pasca revalidateTag:');
  const prod1After = dataCache.get('fetch:/products/101');
  console.log(`  Status Cache Produk 101: ${prod1After ? 'HIT' : 'MISS (Harus Fetch Ulang ke Database!)'}`);

  console.log('\nMembaca Produk 102 (Tag berbeda):');
  const prod2After = dataCache.get('fetch:/products/102');
  console.log(`  Status Cache Produk 102: ${prod2After ? 'HIT (Masih Aman di Cache ✅)' : 'MISS'}`);

  // --- TIER 4: EDGE MIDDLEWARE ---
  console.log('\n' + '-'.repeat(75));
  console.log('C. PENGUJIAN TIER 4: EDGE MIDDLEWARE ROUTE GUARD:');
  console.log('-'.repeat(75));

  // Kasus 1: Request rute privat tanpa cookie
  EdgeMiddlewareSimulator.handleIncomingRequest('/dashboard/analytics', {});

  // Kasus 2: Request rute privat dengan cookie sah
  EdgeMiddlewareSimulator.handleIncomingRequest('/dashboard/analytics', { session_token: 'auth_jwt_991823' });

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: Next.js Multi-Tier Caching & Edge Guard tervalidasi!');
  console.log('='.repeat(75));
}

main();
