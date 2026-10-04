---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `stores/auth.ts`:
*   `export const useAuthStore = defineStore('auth', () => {`: Menggunakan *Setup Store*. Token `'auth'` adalah unique identifier internal yang digunakan Pinia untuk keying di master state map.
*   `const token = ref<string | null>(null)`: Deklarasi state eksplisit berbasis TypeScript generic.
*   `const isAuthenticated = computed(...)`: Getter yang secara reaktif melakukan tracking dependency terhadap `token` dan `session`.
*   `purgeSession()`: Action murni sinkron yang langsung mereset ref ke state awal tanpa mutator wrapper.
*   `return { ... }`: Setup store **wajib** me-return semua properti publik. Properti yang tidak di-return akan dianggap *private internal variable* yang tidak terekspos ke devtools maupun komponen.

### Analisis File `components/AuthStatus.vue`:
*   `const { session, isAuthenticated, isAdmin } = storeToRefs(authStore)`: Mencegah hilangnya reaktivitas saat destrukturisasi. `storeToRefs` menghasilkan `ToRef<T>` untuk setiap state/getter.
*   `const { purgeSession } = authStore`: Action tidak perlu dan tidak boleh dibungkus `storeToRefs`, karena action adalah referensi fungsi biasa yang context `this`-nya sudah di-bind oleh Pinia proxy.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Production Scenario)

### Skenario: Financial High-Frequency Order Execution System
Sebuah institusi pertukaran aset keuangan membutuhkan sistem Terminal Perdagangan (Trading Desk). Sistem ini menerima pembaruan data order book dan status eksekusi hingga ratusan transaksi per detik via WebSocket.

### Masalah Arsitektur:
1.  **State Desynchronization Across Tabs:** Trader membuka beberapa tab browser untuk melihat charting dan order list secara bersamaan. Jika pesanan dieksekusi di Tab A, status limit belanja di Tab B harus terupdate tanpa me-refresh jaringan.
2.  **Reactivity Bottleneck:** Ratusan mutasi data per detik membekukan UI (*event loop congestion*) jika seluruh array orderbook di-track secara deep reactive.
3.  **Audit Trail Requirement:** Setiap perubahan state harus memiliki transaction footprint yang dapat direkam dan di-rollback jika server membatalkan pesanan (Optimistic UI with Rollback).

### Solusi Teknis:
1.  Mengembangkan **Optimistic Execution Store** dengan struktur Map normalisasi.
2.  Menggunakan `shallowRef` untuk menampung order book bervolume tinggi guna mematikan overhead dynamic deep proxy.
3.  Menerapkan arsitektur **Pinia Plugin Custom** berbasis `BroadcastChannel` API untuk menyinkronkan snapshot transaksi antar tab browser secara peer-to-peer.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

### Arsitektur Direktori:
