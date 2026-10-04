# BAB 07: Quiz, Challenge, & Knowledge Check
**Bab 07: Arsitektur Frontend Enterprise (Micro-frontends, Module Federation, & Monorepo Systems)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Komposisi Micro-frontend (Build-time vs Runtime Composition):**  
   Bandingkan arsitektur integrasi micro-frontend berbasis *build-time* (misalnya via npm packages internal) versus *runtime* (misalnya via Webpack 5 Module Federation atau dynamic Web Components). Analisis trade-off keduanya ditinjau dari aspek *deployment decoupling*, *bundle size duplication*, *blast radius* saat terjadi breaking change, serta performa Core Web Vitals (terutama LCP dan CLS).

2. **Mekanisme Shared Scope pada Webpack Module Federation:**  
   Bagaimana cara kerja internal `shared` scope pada Module Federation saat menentukan pemuatan dependensi (misalnya `react` dan `react-dom`)? Jelaskan peran inisialisasi asynchronous (`import('bootstrap')` chunk) dan bagaimana mekanisme *negotiation version* bekerja saat Host dan Remote mendeklarasikan semver yang berbeda.

3. **Isolasi Styling dan Kontaminasi Global CSS:**  
   Pada arsitektur runtime micro-frontend di mana berbagai aplikasi independen dirender dalam satu DOM tree bersama, bagaimana Anda mencegah terjadinya *style leakage*? Bandingkan kelebihan dan batasan teknis antara pendekatan Shadow DOM (Web Components), CSS Modules / Scoped CSS, CSS-in-JS dengan custom hash prefixing, dan Tailwind CSS namespace prefixing.

4. **Monorepo Dependency Hoisting dan Phantom Dependencies:**  
   Jelaskan fenomena *phantom dependencies* dan *doppelgängers* pada package manager berbasis flat node_modules (seperti npm/Yarn v1) dalam konteks Monorepo. Mengapa isolasi berbasis symlink/hardlink (seperti pada pnpm) atau plug'n'play (PnP) menjadi standar industri untuk menjaga integritas dependensi antar-workspace?

5. **Cross-Micro-frontend Communication Boundary:**  
   Mengapa berbagi state global terpusat (seperti satu shared Redux store global) di seluruh micro-frontend dianggap sebagai *anti-pattern* yang merusak prinsip arsitektur micro-frontend? Jelaskan pola komunikasi alternatif yang decoupled (misalnya *custom event bus via Window*, *broadcast channel API*, atau *reactive props injection via shell container*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Resolusi Version Mismatch dan Singleton Traps:**  
   Sebuah Host Application mengonfigurasi Module Federation dengan `shared: { react: { singleton: true, strictVersion: true, requiredVersion: "^18.2.0" } }`. Sebuah Remote Application di-deploy secara independen dengan `react: "18.3.1"`.  
   *Pertanyaan:* Apa respons runtime dan build engine terhadap konfigurasi ini? Jika `strictVersion` dimatikan (`false`), bagaimana fallback behavior dari Module Federation Container Interface, dan potensi runtime exception apa yang bisa muncul pada reconciliation engine React?

2. **Orkestrasi Routing Antar-Aplikasi:**  
   Jelaskan implementasi arsitektur sinkronisasi routing antara Shell Application (Host) dan sub-aplikasi (Remote) yang menggunakan React Router. Mengapa Remote tidak boleh menggunakan `BrowserRouter` secara langsung dan harus mengimplementasikan `MemoryRouter` dengan integrasi ke history Host? Jelaskan mekanisme *deep-linking* dan pencegahan *infinite navigation loop*.

3. **Memory Leaks pada Lifecycle Dynamic Mounting & Unmounting:**  
   Saat sebuah Micro-frontend di-unmount dari Shell untuk digantikan oleh Micro-frontend lain, sumber daya apa saja yang rentan tertinggal dan menyebabkan memory leak? Berikan prosedur diagnostik internal untuk membersihkan:
   - Dynamic `<script>` dan `<style>` tags yang diinjeksikan runtime.
   - Global event listeners pada `window` atau `document`.
   - Dangling instances dari Observer API (IntersectionObserver, MutationObserver).
   - Singleton timer atau long-polling sockets.

4. **Determinisme Cache dan Task Graph Execution pada Monorepo:**  
   Bagaimana engine seperti Turborepo atau Nx menghitung *hash fingerprint* untuk menentukan *cache hit* vs *cache miss* pada task execution (`build`, `test`, `lint`)? Faktor input apa saja yang diikutsertakan dalam kalkulasi hash (file globs, env vars, upstream dependency graph), dan bagaimana cara mencegah terjadinya *cache poisoning* pada Remote Caching CI/CD?

5. **Resiliency & Chunk Load Error Recovery:**  
   Saat Remote Micro-frontend di-deploy versi baru ke CDN, hash dari remote entry atau asynchronous chunk lama akan terhapus. Klien yang masih membuka Shell lama akan mengalami error `ChunkLoadError: Loading chunk [X] failed`. Rancang strategi arsitektur penanganan error ini yang mencakup: Dynamic remote retry mechanism, service worker cache busting, fallback circuit breaker UI, dan silent auto-reload strategy.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bencana Rolling Deployment dan Split-Brain Runtime pada Platform E-Commerce
Platform e-commerce skala enterprise membagi frontend menjadi 3 Micro-frontend via Module Federation: Shell (Header/Auth), Catalog MFE, dan Checkout MFE.  
Saat event flash sale, tim Catalog melakukan *hotfix deployment* ke CDN. Segera setelah deployment, customer support menerima ribuan komplain: pengguna yang sedang berada di flow Checkout tiba-tiba mengalami *blank screen* dengan error `TypeError: Cannot read properties of undefined (reading 'createContext')` atau infinite loader saat menekan tombol "Bayar".  
Tim DevOps melaporkan CDN cache hit ratio turun drastis dan server remote entry terbebani spike traffic.

*Pertanyaan Diagnostik & Solusi:*
1. Mengapa error `createContext` muncul pasca deployment Catalog MFE, padahal tim Checkout tidak melakukan rilis kode sama sekali? Analisis dependency negotiation React pada runtime.
2. Identifikasi kegagalan arsitektur pada konfigurasi caching CDN untuk file `remoteEntry.js` versus chunk hashing assets (`[name].[contenthash].js`).
3. Rancang arsitektur deployment zero-downtime untuk Module Federation yang mengisolasi kegagalan ini di masa depan tanpa harus memaksa deployment serentak (*lockstep deployment*).

### Skenario B: Race Condition Otentikasi dan Deadlock Komunikasi Antar-MFE
Sebuah aplikasi perbankan enterprise memuat 4 micro-frontend dalam satu dashboard: Portfolio, Transfers, Credit Cards, dan Notifications. Masing-masing MFE membutuhkan JWT token valid.  
Token memiliki masa berlaku 5 menit dengan mekanisme Refresh Token. Saat token kedaluwarsa, keempat MFE secara bersamaan mendeteksi status HTTP 401 dan masing-masing menembak endpoint `/api/auth/refresh` secara simultan.  
Sistem backend mengimplementasikan *Refresh Token Rotation* (token lama langsung di-revoke saat refresh pertama berhasil). Akibatnya, request dari MFE pertama berhasil, tetapi 3 request dari MFE lainnya ditolak oleh backend (403 Forbidden - Token Reused Detected), memicu Shell men-trigger logout paksa bagi pengguna di tengah transaksi transfer dana.

*Pertanyaan Diagnostik & Solusi:*
1. Identifikasi *single point of failure* pada kepemilikan state otentikasi di arsitektur distributed frontend tersebut.
2. Rancang pola *Concurrency Control* dan *Token Synchronization Mechanism* di Shell Application menggunakan *Single-flight / Promise-memoization pattern* atau *BroadcastChannel API* agar refresh token hanya dieksekusi satu kali untuk seluruh MFE.
3. Rancang fallback flow jika refresh token benar-benar invalid tanpa menyebabkan cascade crash di seluruh MFE yang sedang aktif.

### Skenario C: Monorepo Scale Collapse pada CI Pipeline
Sebuah startup unicorn memiliki monorepo frontend dengan 45 aplikasi dan 120 shared packages menggunakan Yarn v1 dan Lerna.  
Waktu build CI melonjak dari 8 menit menjadi 58 menit. Sering terjadi insiden di mana commit pada library UI core memicu testing dan build ke seluruh 45 aplikasi, menyebabkan antrean CI macet.  
Selain itu, developer sering mendapati bug misterius: aplikasi berhasil di-build di lokal developer, tetapi gagal di-build di environment CI (`Module not found` atau versi package yang berbeda).

*Pertanyaan Diagnostik & Solusi:*
1. Analisis akar penyebab teknis dari inkonsistensi build antara mesin lokal dan CI pada arsitektur monorepo tersebut (fokus pada *phantom dependencies* dan non-deterministic hoisting).
2. Tentukan blueprint migrasi arsitektur monorepo: Tools apa yang harus diadopsi (misal: pnpm workspaces + Turborepo/Nx) dan bagaimana mekanisme *Affected Graph Analysis* memangkas waktu eksekusi CI secara drastis?
3. Rancang strategi pembagian shared packages (core, utils, UI components) agar tidak menciptakan dependency graph sirkular (*circular dependency*) yang melumpuhkan kemampuan caching build.

---

## 4. Chapter Challenge

**Tantangan Praktis: Membangun Resilient Micro-Frontend Engine dengan Dynamic Module Federation, Event-Driven Cross-App State, dan Fault Tolerance**

### Deskripsi Masalah:
Sebuah platform SaaS enterprise memerlukan sistem Host (Shell) yang mampu memuat Remote Application secara dinamis pada saat runtime berdasarkan izin hak akses pengguna (*Role-Based Dynamic Remotes*). Shell harus tahan banting (*fault-tolerant*): jika Remote gagal dimuat atau crash di runtime, Shell dan Remote lain tidak boleh terpengaruh, serta harus menampilkan fallback UI yang informatif dengan tombol pemulihan (*retry mounting*).

### Requirements:
1. **Host (Shell) Application:**
   - Menggunakan dynamic script loader untuk memuat `remoteEntry.js` dari URL yang diberikan via konfigurasi JSON runtime (bukan hardcoded di file `webpack.config.js`).
   - Menyediakan `RemoteBoundary` tingkat enterprise yang menangkap error loading chunk jaringan dan error rendering runtime React (Error Boundary).
   - Mengimplementasikan Micro-frontend Health Check & Circuit Breaker: jika remote gagal di-load 3 kali berturut-turut, tandai sebagai *degraded* dan tampilkan maintenance state lokal tanpa blocking navigasi aplikasi lain.

2. **Decoupled Cross-MFE Event Bus:**
   - Buat implementasi Event Bus berbasis `CustomEvent` yang di-namespace (misal: `app:auth:changed`, `app:notification:push`) yang bertindak sebagai mediator komunikasi antar MFE.
   - Implementasikan *Contract Typing* (TypeScript) yang ketat untuk payload event agar komunikasi antar tim memiliki skema yang terikat.

3. **Remote Application (Analytics Dashboard):**
   - Berjalan sebagai independent micro-frontend.
   - Mengonsumsi data user dari Host melalui dynamic props atau custom event contract.
   - Menggunakan isolasi CSS yang ketat (misal Tailwind dengan custom class prefix `mfe-analytics-` atau CSS Modules).

### Constraints:
- Host dan Remote harus berbagi instance `react` dan `react-dom` yang sama (Singleton). Tidak boleh ada duplikasi React di memori browser.
- Dilarang keras menggunakan global shared store (seperti Redux/Zustand global di window).
- Harus menangani edge case: Remote dimuat saat kondisi koneksi *offline* atau *slow 3G* dengan visual progress indicator tanpa Layout Shift (CLS score < 0.1).

### Expected Output:
- Konfigurasi Webpack/Vite (Module Federation Plugin) untuk Host dan Remote.
- Kode implementasi dynamic loading utility (`loadComponent(scope, module, url)`).
- Komponen `MicroFrontendErrorBoundary` dengan retry policy.
- Typed Custom Event Bus utility.
- Dokumentasi arsitektur singkat yang menjelaskan skema alur komunikasi dan isolasi dependensi.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara arsitektur Monolitik Frontend, Micro-frontends (Build-time vs Runtime), dan Multi-Zone/Multi-Page Apps.
- [ ] Mekanisme kerja Webpack 5 Module Federation Container Interface (`get()`, `init()`, dan `sharedScope`).
- [ ] Dampak konfigurasi `singleton`, `strictVersion`, dan `requiredVersion` terhadap bundle size dan runtime stability.
- [ ] Mengapa isolasi state dan loose coupling adalah syarat wajib dalam menjaga independensi siklus rilis micro-frontend.
- [ ] Cara kerja dependency graph, hashing, dan remote caching pada sistem Monorepo modern (pnpm, Turborepo, Nx).
- [ ] Anatomi kebocoran memori (memory leak) dan tabrakan style (CSS collision) dalam runtime multi-aplikasi satu DOM tree.

### Saya tidak perlu menghafal:
- [ ] Seluruh syntax opsi konfigurasi webpack compiler hook tingkat rendah.
- [ ] Konfigurasi internal detail plugin Babel untuk Module Federation.
- [ ] Implementasi algoritma topological sort yang dieksekusi internal oleh task runner monorepo.
- [ ] Format biner exact dari file pnpm-lock.yaml.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan mengoptimalkan Module Federation Host & Remote pada enterprise build setup.
- [ ] Mengintegrasikan dynamic remote loader berbasis runtime URL resolution yang aman dari failure.
- [ ] Melakukan debugging dan root-cause analysis terhadap error `Shared module is not available for eager consumption` atau version mismatch React.
- [ ] Mengatur monorepo workspace enterprise dengan pnpm dan Turborepo/Nx untuk eksekusi task pipeline berkecepatan tinggi dengan remote cache.
- [ ] Mengimplementasikan boundary isolasi CSS dan Error Boundary resilien untuk mencegah cascading failure pada Shell Application.
- [ ] Merancang kontrak komunikasi antar-MFE yang type-safe tanpa menciptakan dependensi langsung (*zero coupling*).