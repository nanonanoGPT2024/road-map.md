# BAB 09: Quiz, Challenge, & Knowledge Check
**Strategi Pengujian End-to-End & Automasi CI/CD**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Isolasi Pengujian Server Components (RSC) vs Client Components (RCC)
Dalam arsitektur Next.js App Router, React Server Components (RSC) dieksekusi secara eksklusif di sisi server dan menghasilkan stream RSC Payload, sementara Client Components (RCC) dieksekusi di server (SSR) dan dihidrasi di browser. 
*Jelaskan bagaimana batas arsitektural ini memengaruhi strategi pengujian End-to-End (E2E) menggunakan Playwright/Cypress dibandingkan pengujian integrasi berbasis Component Testing (misal: Vitest/React Testing Library). Mengapa pengujian unit murni gagal memvalidasi interaksi native RSC seperti propagasi header dan eksekusi Server Action secara akurat?*

### Soal 1.2: Dampak Next.js Multi-Tier Caching terhadap Determinisme E2E
Next.js memiliki empat lapisan *caching* independen: Request Memoization, Data Cache, Full Route Cache, dan Router Cache (sisi klien). 
*Uraikan bagaimana Full Route Cache dan Data Cache dapat menyebabkan fenomena false-positive atau flakiness saat rangkaian pengujian E2E dijalankan secara berulang (back-to-back) pada environment staging/preview. Bagaimana konfigurasi build/runtime yang presisi untuk menonaktifkan atau mengisolasi cache tersebut tanpa merusak representasi perilaku sistem produksi?*

### Soal 1.3: Konkurensi, Workers, dan Sharding pada CI/CD
Ketika menjalankan pengujian E2E menggunakan Playwright di pipeline GitHub Actions, pengembang sering kali meningkatkan nilai `workers` untuk mempercepat eksekusi.
*Jelaskan perbedaan mendasar antara model konkurensi **Multithreading/Multi-worker lokal** (dalam satu host/container) dengan **Matrix Sharding** lintas multi-node runner di CI. Analisis potensi bottleneck I/O, CPU throttling, dan batasan shared resource (misal: port availability atau koneksi database lokal) yang muncul dari kedua pendekatan tersebut.*

### Soal 1.4: Node-Level Network Mocking vs Browser Interception
Dalam aplikasi Next.js, pemanggilan data eksternal terjadi di dua subsistem runtime: Node.js/Edge runtime (di dalam Server Components, Route Handlers, dan Server Actions) dan browser context (di dalam Client Components via `fetch` atau library client-side).
*Bandingkan mekanisme intersepsi jaringan menggunakan `page.route()` bawaan Playwright dengan library seperti Mock Service Worker (`msw/node`). Mengapa eksekusi `page.route()` saja tidak cukup untuk menguji alur Server Component yang mengambil data dari REST/GraphQL API pihak ketiga?*

### Soal 1.5: Siklus Otentikasi E2E: Direct UI Authentication vs Storage State Re-use
Melakukan login manual melalui UI interaktif di setiap *test file* merupakan anti-pattern yang memperlambat pipeline CI/CD secara signifikan.
*Jelaskan mekanisme kerja Playwright `storageState` dalam menyimpan dan menginjeksi Cookies serta LocalStorage untuk sesi pengujian Next.js (seperti NextAuth.js atau JWT berbasis HTTP-Only cookie). Bagaimana arsitektur setup global yang aman untuk menangani regenerasi token (refresh token) dan middleware redirect validation tanpa memicu degradasi performa pipeline?*

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Flaky Test Akibat App Router Hydration Race Condition
Sebuah skenario pengujian E2E memvalidasi pengalihan halaman setelah pengguna menekan tombol "Submit" pada Client Component yang membungkus Server Action. Pada pengujian lokal berbasis GUI (headed mode), pengujian 100% sukses. Namun, pada GitHub Actions headless runner (Linux 2-core), tombol sering kali diklik sebelum proses rehidrasi React selesai secara penuh (*partial hydration*), mengakibatkan `onClick` handler tidak terpanggil dan pengujian *timeout*.
*Bagaimana Anda mendiagnosis masalah ini pada level internal engine React/Next.js? Rancang strategi penulisan locator dan assertions di Playwright yang tahan terhadap hydration lag tanpa menggunakan arbitrary sleep/delay (`page.waitForTimeout`).*

### Soal 2.2: Mitigasi Cache Poisoning pada `.next/cache` di GitHub Actions
Untuk menghemat waktu build, tim Anda mengonfigurasi cache GitHub Actions (`actions/cache`) untuk direktori `.next/cache`. Tiba-tiba, pengujian E2E pada Pull Request baru gagal karena halaman memuat versi HTML statis dari Pull Request sebelumnya yang telah di-*merge*, sementara skema database pengujian telah berubah.
*Bedah arsitektur internal dari `.next/cache` (termasuk folder `fetch-cache`, `webpack`, dan `swc`). Tentukan strategi penyusunan `cache-key` yang presisi berbasis hashing file dependensi, source code, dan commit SHA agar tidak terjadi race condition atau poisoned build artifacts lintas cabang (cross-branch).*

### Soal 2.3: Determinisme Server Actions Mutasi dengan `revalidatePath` / `revalidateTag`
Sebuah Server Action memproses mutasi database kemudian memicu `revalidatePath('/dashboard')`. Pada pengujian E2E, Playwright mengecek teks baru di halaman setelah klik tombol, namun teks yang terbaca sesekali masih menampilkan data lama (*stale data*).
*Jelaskan alur internal transmisi respon Server Action, invalidasi Full Route Cache di server, dan streaming RSC Payload pengganti ke router klien. Apa yang menyebabkan race condition ini terjadi di pipeline CI berkoneksi latensi tinggi, dan bagaimana menyusun assertion yang mengecek network lifecycle secara deterministik?*

### Soal 2.4: Debugging E2E Failure Menggunakan Playwright Trace Viewer & Chrome DevTools Protocol
Sebuah pengujian E2E gagal secara berkala hanya di lingkungan CI dengan galat `Target closed` atau `Navigation failed because page crashed!`. Server Next.js mencatat error SIGSEGV atau OOM (Out of Memory).
*Bagaimana metodologi Anda mengekstraksi dan memanfaatkan Playwright Trace, Memory Dumps, serta log stderr dari Node.js yang berjalan di container CI untuk menemukan akar penyebabnya? Parameter apa pada flags peluncuran Chromium (`chromiumSandbox`, `disable-dev-shm-usage`, `headless: 'new'`) yang krusial untuk kestabilan eksekusi di lingkungan containerized?*

### Soal 2.5: Isolasi Database Konkuren pada Pengujian E2E Paralel
Jika pipeline CI Anda menjalankan 4 Playwright worker paralel yang mengeksekusi mutasi entitas data yang sama (misal: menghapus atau mengubah `UserProfile`), akan terjadi collision data yang memicu kegagalan acak.
*Bandingkan tiga strategi isolasi data:*
1. *Database schema per-worker.*
2. *Dynamic tenant isolation via deterministic seed ID / factory-generated UUIDs.*
3. *Database transaction rollback per test run.*
*Mengapa strategi transaction rollback (umum di unit test) sangat sulit atau mustahil diimplementasikan pada pengujian E2E Next.js yang memanggil Server Action dan Route Handler secara nyata?*

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Durasi CI Pipeline pada Turborepo Monorepo Skala Enterprise
**Konteks Produksi:**
Sebuah monorepo enterprise mengelola 3 aplikasi Next.js (B2C Storefront, B2B Portal, Admin Console) yang saling terhubung dengan satu backend PostgreSQL terpusat. Suite pengujian E2E terdiri dari 600 tes Playwright. Saat ini, pipeline CI GitHub Actions memakan waktu 58 menit per commit. Developer mengalami bottleneck parah, merge queue menumpuk, dan biaya komputasi CI membengkak hingga puluhan ribu dolar per bulan.

```
[Commit Push] 
     │
     ▼
[Install + Lint + Typecheck: 8m] 
     │
     ▼
[Next.js Build: 12m] 
     │
     ▼
[Playwright E2E Sequential: 38m] ───► Total: ~58 Menit (Bottleneck!)
```

**Pertanyaan Diagnostik & Arsitektural:**
1. Rancang arsitektur pipeline CI/CD baru yang mengintegrasikan Turborepo Remote Caching, Matrix Sharding, dan dependency-based test execution.
2. Bagaimana Anda memisahkan dependensi build Next.js (apakah menguji terhadap local production build `next start`, standalone Docker container, atau deployment preview Vercel/Cloudflare) untuk mencapai eksekusi E2E di bawah 8 menit secara keseluruhan tanpa mengorbankan integritas tes?

---

### Skenario B: Race Condition dan Mocking Kegagalan Pembayaran Pihak Ketiga
**Konteks Produksi:**
Aplikasi Next.js App Router Anda menangani checkout pesanan. Alurnya melibatkan Server Action yang memvalidasi stok di database internal, membuat *Payment Intent* ke gateway eksternal (Stripe API), dan menunggu webhook asinkronus Stripe untuk mengubah status order menjadi `PAID`, sebelum browser dialihkan ke halaman `/order/success/[id]`. 

Di CI, pengujian E2E untuk skenario "Pembayaran Berhasil" gagal sebesar 20% secara sporadis. Ketika diinvestigasi, halaman dialihkan terlalu cepat sebelum webhook mock berhasil memutasi state database, sehingga pengguna melihat halaman `/order/pending` alih-alih `/order/success`.

**Pertanyaan Diagnostik & Arsitektural:**
1. Di mana letak kegagalan arsitektur pengujian tersebut (apakah pada mock orchestration, lifecycle event coordination, atau database assertion)?
2. Rancang pola implementasi deterministik menggunakan custom Playwright fixtures dan webhook injection endpoint/mock server yang menjamin eliminasi 100% race condition ini tanpa bergantung pada loop polling manual berbasis interval.

---

### Skenario C: Architectural Trade-Off: Preview Deployment Testing vs Ephemeral Containers
**Konteks Produksi:**
Perusahaan Anda sedang merancang ulang strategi CI/CD untuk aplikasi e-commerce core berbasis Next.js dengan trafik jutaan RPS. Tim QA mengusulkan agar seluruh pengujian E2E (1.200 skenario) dieksekusi langsung terhadap URL **Vercel Preview Deployment** yang otomatis terbuat di setiap PR. Tim Platform & Security menolak usulan tersebut dan menuntut pengujian dijalankan pada **Ephemeral Self-Hosted Runner** berbasis Kubernetes/Docker Compose di infrastruktur privat.

**Pertanyaan Diagnostik & Arsitektural:**
Analisis trade-off mendalam dari kedua pendekatan tersebut ditinjau dari parameter:
*   *Security & Compliance* (eksposur database staging dan credentials).
*   *Rate Limiting & Cost* (Vercel edge middleware invocation, database read/write throughput).
*   *Cold Start & Performance Variability* (dampak multi-tenant serverless execution terhadap determinisme tes).
Rekomendasikan arsitektur final *hybrid* yang paling optimal untuk skala enterprise ini beserta justifikasi rasionalnya.

---

## 4. Chapter Challenge

### Tantangan Praktis: Merancang Pipeline E2E Enterprise dengan Playwright Sharding, Otentikasi Terisolasi, dan Ephemeral Database untuk Next.js App Router

#### Problem Statement
Anda ditunjuk sebagai Principal Engineer untuk membangun pipeline pengujian E2E zero-flakiness dari awal (*from scratch*) untuk aplikasi Next.js 14/15 App Router. Pipeline ini harus mampu memvalidasi alur kritis mutasi data (Server Actions) dan visual interface, memiliki waktu eksekusi super-cepat di CI, menggunakan database terisolasi, serta mengeliminasi autentikasi redundan melalui penyimpanan state global.

#### Requirements
1. **Playwright Architecture Setup:**
   * Konfigurasi `playwright.config.ts` yang mendukung multi-project: `setup` (untuk global authentication), `desktop-chrome`, dan `mobile-safari`.
   * Implementasikan mekanisme `storageState` di mana autentikasi dijalankan sekali di fase setup worker, dan session token diinjeksikan secara instan ke worker pengujian transaksi tanpa membuka form login berulang kali.
2. **Ephemeral Database Strategy:**
   * Siapkan konfigurasi `docker-compose.test.yml` yang menyalakan PostgreSQL khusus pengujian.
   * Buat script automasi lifecycle database yang mengeksekusi migrasi skema (misal: Prisma/Drizzle) dan *seeding baseline data* sebelum pengujian dimulai.
3. **CI/CD Pipeline Implementation (GitHub Actions):**
   * Buat workflow `.github/workflows/e2e.yml`.
   * Terapkan strategi **Matrix Sharding** (minimal 4 shards paralel).
   * Implementasikan caching yang tepat untuk dependensi npm/pnpm dan `.next/cache`.
   * Gabungkan (*merge*) seluruh laporan Playwright HTML dari keempat shards menjadi satu artifact dashboard terpadu di akhir job menggunakan `merge-reports`.
4. **Deterministic Server Action Testing:**
   * Tulis satu test spec (`e2e/order-mutation.spec.ts`) yang menguji form mutasi Server Action dengan validasi input, status mutasi pending (loading state), dan visualisasi data yang ter-*revalidate*. Pastikan tidak ada polling atau arbitrary sleep.

#### Constraints
* **Runtime Target:** Node.js 20 LTS, Next.js 14+ (App Router).
* **Test Framework:** Playwright Test versi terbaru.
* **Execution Time:** Maksimal durasi per-shard di CI adalah 3 menit.
* **Strict Flakiness Policy:** Retries diizinkan maksimal 1 kali di CI (`retries: 1`), dan 0 kali di lokal. Pengujian harus lulus 100% pada 10x eksekusi berturut-turut di pipeline.

#### Expected Output
1. File `playwright.config.ts` lengkap dan modular.
2. File pipeline `.github/workflows/e2e.yml` berstandar produksi yang mengimplementasikan steps build, cache, background services, matrix sharding, dan artifact merging.
3. File test spec `order-mutation.spec.ts` yang mendemonstrasikan penanganan Server Action dan deterministic assertions.
4. Diagram alur Markdown atau penjelasan arsitektural tentang bagaimana state autentikasi dan database lifecycle dikelola lintas worker shard.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur siklus hidup rendering Next.js App Router (RSC Payload, Streaming, Hydration) dan titik-titik kritis kegagalan pada pengujian E2E.
- [ ] Perbedaan fungsionalitas antara `page.route()` (Playwright) dan `MSW` (Mock Service Worker) dalam mencegat request yang berasal dari server runtime vs browser runtime.
- [ ] Mekanisme kerja 4 layer cache Next.js (Request Memoization, Data Cache, Full Route Cache, Router Cache) dan cara mengendalikannya dalam environment pengujian.
- [ ] Konsep Matrix Sharding pada CI/CD runners dan trade-off konsumsi resource I/O, database concurrency, serta network bottleneck.
- [ ] Cara kerja Playwright auth session caching (`storageState`) dan bahaya leakage security jika token disimpan secara tidak aman di CI artifacts.
- [ ] Perilaku Server Actions saat dipanggil secara konkuren di headless mode dan bagaimana assertion deterministik dibuat tanpa arbitrary delay (`waitForTimeout`).
- [ ] Metodologi debugging berbasis Playwright Trace Viewer, Network HAR logs, dan video recording untuk troubleshooting headless CI failures.

### Saya tidak perlu menghafal:
- [ ] Seluruh parameter konfigurasi CLI flags dari Playwright atau GitHub Actions syntax secara detail di luar kepala (cukup memahami struktur deklaratif dan fungsinya).
- [ ] Implementasi internal binary engine Chromium/WebKit driver saat mem-parsing Web Platform APIs.
- [ ] Konfigurasi internal compiler Rust pada Next.js SWC/Turbopack untuk code transformation.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi `playwright.config.ts` dengan multi-project dependencies, webServer startup hooks, custom reporters, dan dynamic workers.
- [ ] Menulis pipeline CI/CD GitHub Actions multi-stage yang mencakup dependency caching, Next.js incremental build caching, dynamic container services, dan multi-node matrix sharding.
- [ ] Menggabungkan laporan pengujian terdistribusi (HTML report artifacts) dari multi-shards menggunakan tool Playwright Merge Reports.
- [ ] Mendesain custom fixtures di Playwright untuk mengisolasi state, mocking third-party network APIs di tingkat Node.js, dan seeding database dinamis.
- [ ] Mengidentifikasi, mengisolasi, dan memusnahkan *flaky tests* yang diakibatkan oleh race condition hidrasi React atau mutasi basis data asinkron.
- [ ] Membangun workflow pengujian berbasis ephemeral environment di mana database dan container Next.js dihidupkan serta dihancurkan secara otomatis per test execution run.