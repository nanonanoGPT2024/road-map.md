---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Meninjau `src/composables/__tests__/useCheckoutEngine.spec.ts`:
*   **Baris 7-9 (`setActivePinia(createPinia())`):**
    *   Mekanisme: Membuat instance root Pinia baru secara in-memory dan menjadikannya active scope.
    *   Mengapa krusial: Jika diabaikan, state antar unit test akan tercemar (*cross-test pollution*). Item yang ditambahkan di Test A akan tetap berada di memori ketika Test B berjalan.
*   **Baris 10 (`vi.clearAllMocks()`):**
    *   Membersihkan tracking history call count, instances, dan invocation arguments dari mock functions. Menjamin integritas assertion `mockPaymentClient`.
*   **Baris 17 (`cart.addItem(...)`):**
    *   Menguji composable via interaksi state langsung (kontrak antar-modul), bukan mocking store. Ini memvalidasi interaksi reaktivitas riil antara `useCartStore` dan `useCheckoutEngine`.
*   **Baris 38 (`vi.fn().mockResolvedValue(...)`):**
    *   Mengganti external dependency (`paymentGatewayClient`) dengan sinonim mock yang mengembalikan Promise resolve. Pendekatan ini merupakan *Dependency Injection* murni tanpa memanipulasi network stack global.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise Multi-Currency Order Checkout Matrix
Sebuah platform B2B SaaS memproses transaksi ribuan enterprise user. Masalah yang sering terjadi di environment CI:
1.  **Vitest Network Race Conditions:** Developer melakukan `vi.spyOn(global, 'fetch')` secara manual di berbagai file. Ketika tests berjalan paralel via worker threads, mock fetch saling menimpa, menghasilkan HTTP 404/500 acak di CI runner.
2.  **Playwright Authentication Bottleneck:** E2E suite mengeksekusi login UI via form submission untuk 150 skenario test, mengakibatkan durasi pipeline melonjak hingga 45 menit dan memicu *rate limiting* pada identity provider (IdP).

### Solusi Arsitektur
1.  Standardisasi intersep jaringan level Vitest menggunakan **Mock Service Worker (MSW)**. MSW bekerja di level node runtime via interceptor internal undici/http, terisolasi per lifecycle process tanpa mengotori `globalThis.fetch`.
2.  Implementasi pola **Playwright Global Authentication Caching** via `storageState`, di mana sesi login dieksekusi satu kali di fase bootstrap CI, disimpan sebagai representasi file JSON terenkripsi, lalu diinjeksikan secara transparan ke seluruh instance `BrowserContext`.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

### 1. Vitest + MSW Component Testing

#### File: `src/mocks/handlers.ts`
