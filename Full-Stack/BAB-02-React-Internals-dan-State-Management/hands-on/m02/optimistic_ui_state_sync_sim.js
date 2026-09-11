/**
 * SIMULATOR: TANSTACK QUERY ENGINE, OPTIMISTIC UI MUTATIONS & ZUSTAND SELECTORS
 * Modul 02: State Management: Server State (TanStack Query) vs Client State (Zustand) & Optimistic UI
 *
 * Mendemonstrasikan:
 * 1. Siklus hidup Server State Cache (staleTime, deduplikasi request simultan).
 * 2. Mutasi Antarmuka Optimistis (Optimistic UI Update) dalam 0 milidetik.
 * 3. Mekanisme Automatic Rollback ke snapshot data lama saat terjadi kegagalan jaringan HTTP 500.
 * 4. Micro-Store Zustand dengan Atomic Selector (mencegah re-render tak perlu ala Context API).
 *
 * Jalankan: node optimistic_ui_state_sync_sim.js
 */

// =========================================================================
// BAGIAN 1: SIMULATOR TANSTACK QUERY CACHE ENGINE
// =========================================================================

class MockQueryClient {
  constructor() {
    this.cache = new Map(); // queryKeyString -> { data, updatedAt, staleTimeMs }
    this.inflightRequests = new Map(); // queryKeyString -> Promise (Deduplikasi)
    this.networkFetchCount = 0;
  }

  _serializeKey(keyArray) {
    return JSON.stringify(keyArray);
  }

  async fetchQuery(keyArray, fetcherFn, staleTimeMs = 2000) {
    const key = this._serializeKey(keyArray);
    const now = Date.now();

    // 1. Cek apakah ada data di cache yang MASIH FRESH (belum stale)
    if (this.cache.has(key)) {
      const cached = this.cache.get(key);
      const isStale = (now - cached.updatedAt) > cached.staleTimeMs;
      if (!isStale) {
        return { data: cached.data, source: 'CACHE_FRESH' };
      }
    }

    // 2. DEDUPLIKASI: Jika request untuk key yang sama sedang berjalan di jaringan,
    // jangan tembak dua kali! Gabungkan ke Promise yang sudah ada!
    if (this.inflightRequests.has(key)) {
      console.log(`  🛡️ [DEDUPLIKASI AKTIF] Request simultan untuk ${key} digabungkan ke koneksi yang sama!`);
      const sharedData = await this.inflightRequests.get(key);
      return { data: sharedData, source: 'SHARED_INFLIGHT' };
    }

    // 3. Tembak request ke server riil
    console.log(`  🌐 [NETWORK FETCH] Menghubungi API server untuk ${key}...`);
    this.networkFetchCount++;
    const fetchPromise = fetcherFn().finally(() => {
      this.inflightRequests.delete(key);
    });

    this.inflightRequests.set(key, fetchPromise);
    const serverData = await fetchPromise;

    // Simpan ke cache
    this.cache.set(key, {
      data: serverData,
      updatedAt: Date.now(),
      staleTimeMs
    });

    return { data: serverData, source: 'NETWORK_FRESH' };
  }

  getQueryData(keyArray) {
    const key = this._serializeKey(keyArray);
    const item = this.cache.get(key);
    return item ? JSON.parse(JSON.stringify(item.data)) : null; // Deep copy
  }

  setQueryData(keyArray, updaterFn) {
    const key = this._serializeKey(keyArray);
    const current = this.getQueryData(keyArray);
    const updated = typeof updaterFn === 'function' ? updaterFn(current) : updaterFn;
    this.cache.set(key, {
      data: updated,
      updatedAt: Date.now(),
      staleTimeMs: 2000
    });
    return updated;
  }
}

// =========================================================================
// BAGIAN 2: MESIN OPTIMISTIC UI MUTATION ENGINE
// =========================================================================

class OptimisticMutationEngine {
  constructor(queryClient) {
    this.client = queryClient;
  }

  async mutateToggleLike(postId, shouldFailNetwork = false) {
    const queryKey = ['post', postId];

    console.log(`\n▶️ [USER KLIK TOMBOL LIKE] Post #${postId}`);

    // LANGKAH 1: Ambil snapshot state lama (Backup)
    const previousPost = this.client.getQueryData(queryKey);
    console.log(`  1. Simpan Snapshot Cadangan : Likes = ${previousPost.likes}, isLiked = ${previousPost.isLiked}`);

    // LANGKAH 2: UPDATE OPTIMISTIS INSTAN DI MEMORI (0 MS!)
    const optimisticPost = this.client.setQueryData(queryKey, (old) => ({
      ...old,
      likes: old.isLiked ? old.likes - 1 : old.likes + 1,
      isLiked: !old.isLiked
    }));
    console.log(`  2. ⚡ [OPTIMISTIC UI UPDATE] Layar Berubah Instan! Likes = ${optimisticPost.likes}, isLiked = ${optimisticPost.isLiked} (Latensi 0ms)`);

    // LANGKAH 3: Kirim mutasi asinkron ke server
    console.log(`  3. Mengirim request PATCH ke backend server...`);
    try {
      await new Promise((resolve, reject) => {
        setTimeout(() => {
          if (shouldFailNetwork) {
            reject(new Error('HTTP 500: Database Connection Timeout pada Server!'));
          } else {
            resolve({ success: true });
          }
        }, 80);
      });

      console.log(`  4. ✅ [MUTASI SUKSES] Server mengonfirmasi status like untuk Post #${postId}. Selesai!`);
      return { success: true };

    } catch (err) {
      console.error(`  4. 🚨 [MUTASI GAGAL] Error: "${err.message}"`);
      console.log(`  5. 🔄 [AUTOMATIC ROLLBACK] Mengembalikan UI ke snapshot lama...`);
      // Kembalikan ke state awal yang disimpan di langkah 1
      this.client.setQueryData(queryKey, previousPost);
      const reverted = this.client.getQueryData(queryKey);
      console.log(`     UI Dipulihkan: Likes = ${reverted.likes}, isLiked = ${reverted.isLiked}`);
      return { success: false, error: err.message };
    }
  }
}

// =========================================================================
// BAGIAN 3: ZUSTAND ATOMIC SELECTOR SIMULATOR
// =========================================================================

class MockZustandStore {
  constructor(initialState) {
    this.state = initialState;
    this.subscribers = [];
  }

  getState() {
    return this.state;
  }

  setState(partialState) {
    this.state = { ...this.state, ...partialState };
    // Beritahu subscriber yang nilainya berubah
    this.subscribers.forEach(sub => sub(this.state));
  }

  // Hook selector atomik (Hanya re-render jika slice data yang dipilih berubah)
  subscribeSelector(selectorFn, componentName) {
    let currentSlice = selectorFn(this.state);
    this.subscribers.push((newState) => {
      const nextSlice = selectorFn(newState);
      if (currentSlice !== nextSlice) {
        console.log(`  📢 [ZUSTAND RE-RENDER] Komponen '${componentName}' me-render ulang karena datanya berubah: [${nextSlice}]`);
        currentSlice = nextSlice;
      } else {
        console.log(`  💤 [SKIPPED] Komponen '${componentName}' TIDAK perlu re-render (Data tidak berubah).`);
      }
    });
  }
}

// =========================================================================
// BAGIAN 4: EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =========================================================================

async function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: SERVER STATE, OPTIMISTIC UI ROLLBACK, & ZUSTAND SELECTORS');
  console.log('='.repeat(75));

  const queryClient = new MockQueryClient();

  // Seeding post awal di server state cache
  queryClient.setQueryData(['post', 101], { id: 101, title: 'Tutorial React Modern 2026', likes: 42, isLiked: false });

  // 1. Pengujian Deduplikasi Request Simultan TanStack Query
  console.log('A. Uji Deduplikasi Request Simultan (3 Komponen Meminta Data yang Sama):');
  const mockFetcher = async () => {
    await new Promise(r => setTimeout(r, 40));
    return { userId: 'USR-88', name: 'Budi Santoso', tier: 'PRO' };
  };

  await Promise.all([
    queryClient.fetchQuery(['user', 'profile'], mockFetcher),
    queryClient.fetchQuery(['user', 'profile'], mockFetcher),
    queryClient.fetchQuery(['user', 'profile'], mockFetcher)
  ]);
  console.log(`  Total Panggilan Jaringan Riil: ${queryClient.networkFetchCount} kali (3 request digabung jadi 1!)\n`);

  // 2. Pengujian Optimistic UI (Kasus Sukses)
  console.log('-'.repeat(75));
  console.log('B. Pengujian Optimistic UI Update (Skenario Sukses):');
  console.log('-'.repeat(75));
  const mutationEngine = new OptimisticMutationEngine(queryClient);
  await mutationEngine.mutateToggleLike(101, false);

  // 3. Pengujian Optimistic UI (Kasus Gagal & Rollback)
  console.log('\n' + '-'.repeat(75));
  console.log('C. Pengujian Optimistic UI Update (Skenario Kegagalan Jaringan & Rollback):');
  console.log('-'.repeat(75));
  await mutationEngine.mutateToggleLike(101, true);

  // 4. Pengujian Zustand Atomic Selector vs Context API
  console.log('\n' + '-'.repeat(75));
  console.log('D. Pengujian Zustand Atomic Selector (Pencegahan Re-render Berlebih):');
  console.log('-'.repeat(75));

  const store = new MockZustandStore({ theme: 'dark', userBalance: 50000 });

  // Komponen A hanya tertarik pada theme
  store.subscribeSelector(s => s.theme, 'ThemeToggleComponent');
  // Komponen B hanya tertarik pada userBalance
  store.subscribeSelector(s => s.userBalance, 'BalanceDisplayComponent');

  console.log('Memperbarui Theme dari "dark" ke "light":');
  store.setState({ theme: 'light' });

  console.log('\nMemperbarui Saldo User dari 50000 ke 75000:');
  store.setState({ userBalance: 75000 });

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: Seluruh pilar state management full-stack teruji sempurna!');
  console.log('='.repeat(75));
}

main();
