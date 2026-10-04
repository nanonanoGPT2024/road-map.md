# Evaluasi Bab 06: Edge Compute Serverless: Cloudflare Workers & Pages

## 1. Basic Questions (5 Soal)

### Soal 1
Mengapa arsitektur V8 Isolates pada Cloudflare Workers mampu menghilangkan masalah *cold start* secara signifikan dibandingkan AWS Lambda berbasis Container Docker?
- A. Karena Cloudflare Workers mengalokasikan satu Virtual Machine (VM) khusus untuk setiap akun pengguna.
- B. Karena V8 Isolates tidak menjalankan kernel OS dan guest runtime terpisah, melainkan mengeksekusi kode di dalam thread proses V8 yang sudah berjalan sebelumnya.
- C. Karena Cloudflare Workers menyimpan seluruh status memori container di NVMe SSD edge server.
- D. Karena Cloudflare Workers hanya mengeksekusi kode statis yang sudah dikompilasi ke file binary Linux `.so`.

**Kunci Jawaban**: **B**
**Penjelasan Teknis**: Isolates memanfaatkan instance V8 engine yang telah berjalan aktif pada host edge. Menciptakan Isolate baru hanya mengalokasikan heap memori baru yang terisolasi sandboxing pointer tanpa mem-boot OS, namespace kernel, cgroups, atau runtime binary OS, memangkas waktu start dari ratusan milidetik menjadi <5 milidetik.

---

### Soal 2
Perintah CLI Wrangler manakah yang digunakan untuk menyalurkan (*stream*) log eksekusi, console output, dan error secara real-time dari production edge Worker ke terminal developer?
- A. `wrangler logs --follow`
- B. `wrangler monitor --production`
- C. `wrangler tail`
- D. `wrangler debug --remote`

**Kunci Jawaban**: **C**
**Penjelasan Teknis**: `npx wrangler tail` menginisialisasi sesi WebSocket aman ke sistem telemetri Cloudflare Workers untuk menangkap trace log `console.log()`, exception unhandled, dan status metadata request dari live traffic production.

---

### Soal 3
Bagaimana cara kerja parser `HTMLRewriter` dalam mentransformasi dokumen HTML di Cloudflare Workers?
- A. Mengunduh seluruh dokumen HTML ke memori RAM, membangun pohon DOM lengkap (seperti browser/JSDOM), memodifikasi node, lalu me-render ulang ke string.
- B. Mengonversi teks HTML menjadi format JSON AST (Abstract Syntax Tree), memodifikasi properti object, lalu mengompilasi balik ke HTML.
- C. Memproses stream byte HTML secara linier menggunakan streaming state machine berbasis Rust tanpa memuat seluruh dokumen ke dalam memori.
- D. Mengirimkan dokumen HTML ke backend microservice headless Chrome untuk di-render dan diambil snapshot DOM-nya.

**Kunci Jawaban**: **C**
**Penjelasan Teknis**: `HTMLRewriter` menggunakan library Rust *lol-html*. Parser ini memproses token HTML secara bertahap saat byte mengalir melalui stream network (*SAX-style streaming*), sehingga konsumsi memori konstan dan latensi pemrosesan mendekati nol terlepas dari ukuran dokumen HTML.

---

### Soal 4
Apa perbedaan mendasar antara alokasi **CPU Time** dan **Wall-Clock Time** di Cloudflare Workers?
- A. CPU time mengukur durasi siklus clock instruksi komputasi aktual pada prosesor, sedangkan Wall-Clock time mengukur total waktu fisik termasuk menunggu response network I/O.
- B. CPU time dibatasi hingga 15 menit, sedangkan Wall-Clock time dibatasi hingga 50 milidetik.
- C. CPU time hanya berlaku untuk Cloudflare Pages, sedangkan Wall-Clock time hanya berlaku untuk Workers KV.
- D. CPU time mencakup waktu transmisi network antar client dan server, sedangkan Wall-Clock time hanya mencakup waktu eksekusi kode internal JavaScript.

**Kunci Jawaban**: **A**
**Penjelasan Teknis**: Batas kuota standar (misal 50ms pada paket Standard) dievaluasi berdasarkan CPU Time (siklus komputasi aktif). Waktu tunggu network I/O dari subrequest `fetch()` origin dihitung ke dalam Wall-Clock time dan tidak mengurangi kuota CPU time.

---

### Soal 5
Pada Cloudflare Pages Functions, konvensi penamaan file manakah yang secara otomatis menangani parameter rute dinamis (dynamic route parameter) untuk endpoint seperti `/users/:id`?
- A. `/functions/users/{id}.js`
- B. `/functions/users/:id.js`
- C. `/functions/users/[id].js`
- D. `/functions/users/*id.js`

**Kunci Jawaban**: **C**
**Penjelasan Teknis**: Cloudflare Pages Functions menggunakan format bracket berbasis sistem file `[param].js` untuk rute dinamis tunggal, dan `[[param]].js` atau `[...param].js` untuk catch-all routes.

---

## 2. Intermediate Questions (5 Soal)

### Soal 6
Sebuah Worker perlu mengirimkan log analitik ke backend logging pihak ketiga setelah merespons HTTP request ke client. Anda ingin memastikan operasi pengiriman log tidak menambah latensi TTFB yang dialami oleh client. API Workers apa yang wajib digunakan?
- A. `process.nextTick()`
- B. `ctx.waitUntil()`
- C. `setTimeout(fn, 0)`
- D. `navigator.sendBeacon()`

**Kunci Jawaban**: **B**
**Penjelasan Teknis**: Method `ctx.waitUntil(promise)` menginstruksikan runtime V8 Isolate untuk tetap membiarkan event loop Isolate aktif mengeksekusi asynchronous background task (seperti logging fetch) bahkan setelah objek `Response` selesai dikirimkan ke client, menjaga TTFB client tetap optimal.

---

### Soal 7
Apa implikasi arsitektural dari penggunaan `await response.text()` pada respons origin berukuran 100MB di dalam sebuah Cloudflare Worker dengan paket memori standar 128MB?
- A. Runtime otomatis memecah teks tersebut ke penyimpanan Cloudflare KV tanpa error.
- B. Isolate berisiko mengalami crash akibat *Worker Memory Exceeded limit* (Error 1101), dan streaming transfer encoding terputus.
- C. Runtime membatasi parsing teks secara otomatis menjadi 512KB pertama dan membuang sisanya secara diam-diam.
- D. Request dialihkan otomatis ke kontainer AWS Lambda fallback.

**Kunci Jawaban**: **B**
**Penjelasan Teknis**: Membaca seluruh response 100MB ke memori string V8 via `await response.text()` membutuhkan alokasi heap yang masif. Hal ini menyebabkan heap exhaustion melebihi limit memori Isolate (128MB), memicu pembatalan eksekusi Isolate oleh host runtime. Pola yang benar adalah menggunakan Web Streams API (`ReadableStream` / `TransformStream`).

---

### Soal 8
Anda mengimplementasikan `HTMLRewriter` untuk mengubah konten sebuah tag HTML. Mengapa manipulasi tag menggunakan selector `htmlRewriter.on('p', ...)` jauh lebih aman dari serangan Cross-Site Scripting (XSS) jika dibandingkan dengan regex string replacement sederhana `body.replace(/<p>(.*?)<\/p>/, ...)`?
- A. Karena `HTMLRewriter` secara otomatis mengenkripsi seluruh string HTML menggunakan AES-GCM 256.
- B. Karena `HTMLRewriter` melakukan parsing struktur konteks HTML secara semantik dan method seperti `element.setInnerContent(text, { html: false })` melakukan escaping karakter berbahaya secara default.
- C. Karena `HTMLRewriter` hanya dapat dijalankan pada browser client, bukan di server edge.
- D. Karena `HTMLRewriter` memblokir semua request yang mengandung payload skrip JavaScript.

**Kunci Jawaban**: **B**
**Penjelasan Teknis**: Pendekatan regex tidak memahami sintaks hierarkis HTML (rentan terhadap malformed input, attribute injection, bypass quote). `HTMLRewriter` mengenali konteks element/attribute dan menyediakan opsi sanitasi native (`{ html: false }`) yang secara otomatis mengubah karakter berbahaya (`<`, `>`, `&`, `"`) menjadi HTML entities.

---

### Soal 9
Manakah pernyataan yang **BENAR** mengenai cakupan isolasi memori antar request pada Cloudflare Workers?
- A. Setiap incoming request dijamin selalu menjalankan instance Isolate baru yang fresh dari awal.
- B. Dua request yang masuk secara paralel dari klien berbeda dapat berbagi memori heap lokal Isolate yang sama di thread yang sama tanpa ada batasan keamanan.
- C. Sebuah Isolate dapat digunakan kembali (*reused*) untuk menangani request-request berikutnya pada PoP yang sama, namun variabel state in-memory global tidak dapat diandalkan untuk konsistensi data terdistribusi.
- D. Seluruh data yang disimpan pada variabel global secara otomatis disinkronkan ke seluruh 300+ PoP di seluruh dunia.

**Kunci Jawaban**: **C**
**Penjelasan Teknis**: Runtime Cloudflare dapat me-reuse Isolate yang sama untuk request berikutnya guna mengoptimalkan efisiensi (*warm reuse*). Oleh karena itu, variabel global mungkin mempertahankan nilai sebelumnya pada request berikutnya di server yang sama, namun karena Workers berjalan di ratusan node Anycast secara terdistribusi, state global in-memory tidak terjamin sinkron antar server/PoP.

---

### Soal 10
Berapa batas default *subrequests* (panggilan `fetch()` sekunder ke internet/origin) yang diizinkan dalam penanganan satu kali *incoming request* pada Cloudflare Workers standard?
- A. 10 subrequest
- B. 50 subrequest
- C. 500 subrequest
- D. Tidak terbatas

**Kunci Jawaban**: **B**
**Penjelasan Teknis**: Cloudflare Workers memberlakukan batas keamanan maksimal 50 subrequests per single client incoming HTTP request untuk mencegah infinite loop fetch, amplifikasi DDoS internal, dan eksploitasi resource exhaustion di edge server.

---

## 3. Scenario-Based Questions (3 Kasus Nyata)

### Kasus 1: Flash Sale E-Commerce & Edge Queue Token Bucket
**Skenario**: 
Sebuah platform tiket konser online mengalami lonjakan trafik dari 1.000 RPS menjadi 150.000 RPS dalam 3 detik saat penjualan tiket dibuka. Database origin MySQL di backend langsung crash karena kehabisan koneksi (pool exhaustion). Tim SRE diinstruksikan membangun Edge Middleware di Cloudflare Workers untuk membatasi traffic yang menyentuh origin maksimum 2.000 RPS, dan mengalihkan sisa antrean pengunjung ke ruang tunggu virtual (*Virtual Waiting Room*) yang menyajikan halaman statis informatif beserta estimasi antrean berbasis token JWT.

**Tugas Evaluasi SRE**:
1. Rancang arsitektur alur kerja Worker di layer Edge untuk mencegat request sebelum mencapai origin.
2. Jelaskan bagaimana Anda memverifikasi token antrean pengguna tanpa membebani database origin.
3. Bagaimana mekanisme mitigasi agar Worker tidak melampaui limit *subrequest* atau memori saat memvalidasi puluhan ribu request per detik?

**Jawaban dan Analisis Solusi**:
1. **Arsitektur Edge Interceptor**:
   - Request pertama masuk ke Worker di Anycast Edge PoP.
   - Worker memeriksa keberadaan cookie terenkripsi/ditandatangani: `queue_token`.
   - Jika pengguna belum memiliki token atau token belum gilirannya, Worker mengembalikan HTTP 200 berisi halaman HTML antrean virtual murni dari Edge Cache/Workers KV tanpa pernah mem-proxy request ke backend origin.
2. **Validasi Token Kriptografis Tanpa Database**:
   - Token diterbitkan menggunakan format JWT / HMAC-SHA256 yang ditandatangani menggunakan secret key yang disimpan di `env.SECRET_HMAC_KEY`.
   - Payload token berisi: `{ queue_number: 14500, issued_at: 1714000000 }`.
   - Menggunakan Web Crypto API native (`crypto.subtle.verify`), Worker memvalidasi integritas signature token di edge dalam waktu < 0.5ms CPU time tanpa external call.
   - Batas antrean aktif yang diizinkan saat ini (*current served window*, misal: nomor 1-5.000) disimpan pada Cloudflare KV atau edge memory rate limiter. Jika `queue_number <= current_served_window`, request diizinkan lanjut ke origin via `fetch()`.
3. **Pemberantasan Subrequest Limit & Memory Exhaustion**:
   - Verifikasi kriptografi dilakukan murni in-memory menggunakan Web Crypto API (0 subrequest).
   - Pengambilan konfigurasi *current served window* memanfaatkan integrasi edge caching atau cache header `Cache-Control: s-maxage=5` sehingga Worker hanya mengambil data baru tiap 5 detik sekali, bukan per request.
   - Halaman Waiting Room disajikan secara streaming via `HTMLRewriter` untuk menginjeksi nomor antrean, menjaga memori heap Worker tetap stabil di bawah 2MB.

---

### Kasus 2: Micro-Frontend Edge Stitching
**Skenario**: 
Aplikasi enterprise modern dibangun menggunakan arsitektur micro-frontend:
- Fragment Navigasi & Header disediakan oleh Tim Navigasi: `https://nav.enterprise.internal/fragment`
- Fragment Konten Utama disediakan oleh Tim Core: `https://core.enterprise.internal/fragment`
- Fragment Rekomendasi AI disediakan oleh Tim Data: `https://ai.enterprise.internal/fragment`

Jika integrasi dilakukan di sisi client (browser fetching 3 endpoint berbeda), terjadi network waterfalling dan rendering flicker yang memperburuk metrik Core Web Vitals (LCP & CLS). Anda ditugaskan membangun **Edge Stitcher** di Cloudflare Workers yang menggabungkan ketiga fragment tersebut menjadi satu dokumen HTML tunggal sebelum dikirimkan ke browser.

**Tugas Evaluasi SRE**:
1. Tuliskan arsitektur eksekusi *asynchronous* untuk mengambil ketiga origin fragment secara paralel.
2. Jelaskan penanganan kegagalan (*fault tolerance*) jika fragment AI mengalami timeout (>500ms) atau HTTP 500, agar halaman web utama tetap dapat ditampilkan ke pengguna tanpa fragment AI tersebut.
3. Bagaimana mekanisme streaming HTML diterapkan agar browser dapat mulai mem-parse header navigasi sebelum rekomendasi AI selesai dihitung?

**Jawaban dan Analisis Solusi**:
1. **Parallel Asynchronous Fetching**:
   - Worker menggunakan `Promise.allSettled()` untuk mengeksekusi subrequest ke ketiga origin secara konkuren, bukan sequential `await`.
   ```javascript
   const navPromise = fetch("https://nav.enterprise.internal/fragment");
   const corePromise = fetch("https://core.enterprise.internal/fragment");
   const aiPromise = fetch("https://ai.enterprise.internal/fragment", {
     signal: AbortSignal.timeout(500) // Timeout strict 500ms
   });
   ```
2. **Fault Tolerance & Graceful Degradation**:
   - Dengan `Promise.allSettled()`, status setiap fragment diperiksa secara independen.
   - Jika fragment AI rejected (timeout) atau menghasilkan response `!response.ok`, fallback UI berupa skeleton layout kosong atau elemen tersembunyi disuntikkan, sehingga error pada fragment AI tidak mematikan halaman utama (Core & Nav).
3. **Edge Stitching via Streaming Pipeline**:
   - Worker mengambil *shell template* dasar (HTML envelope).
   - Gunakan `HTMLRewriter` dengan binding selector:
     - `rewriter.on("div#nav-slot", { async element(el) { el.replace(await navResponse.text(), {html: true}); } })`
     - `rewriter.on("div#core-slot", { async element(el) { el.replace(await coreResponse.text(), {html: true}); } })`
     - `rewriter.on("div#ai-slot", { async element(el) { el.replace(aiContentSafe, {html: true}); } })`
   - Respon di-stream langsung ke client, sehingga byte header navigasi tiba di browser terlebih dahulu sementara AI fragment di-resolve di background edge.

---

### Kasus 3: Canary Deployments & Zero-Downtime Origin Migration
**Skenario**: 
Organisasi Anda sedang memigrasikan backend dari Data Center on-premise lama (`origin-legacy.company.com`) ke infrastruktur AWS EKS baru (`origin-k8s.company.com`). Tim DevOps ingin melakukan migrasi berbasis Canary Routing bertahap:
- 90% trafik tetap diarahkan ke origin lama.
- 10% trafik dialihkan ke AWS EKS baru.
- Pengguna yang masuk ke kelompok 10% (Canary) harus konsisten (*sticky*) berada di kelompok Canary pada request-request berikutnya.
- Jika origin AWS EKS menghasilkan response error (HTTP 502/503/504), Worker harus secara transparan mengulang (*retry*) request tersebut ke origin lama dalam durasi < 150ms tanpa disadari oleh client.

**Tugas Evaluasi SRE**:
Jelaskan alur implementasi Worker untuk memecahkan kebutuhan di atas mencakup penentuan bobot (*weighting*), persistensi sesi (*session stickiness*), dan *automatic retry fallback*.

**Jawaban dan Analisis Solusi**:
1. **Stickiness & Weighted Routing**:
   - Worker membaca cookie `canary_bucket` dari request.
   - Jika cookie tidak ada, hitung nilai deterministik (misal: generate random integer 1-100 atau hashing IP client + Salt).
   - Jika nilai <= 10, tetapkan target origin ke AWS EKS (`origin-k8s`) dan buat header response `Set-Cookie: canary_bucket=canary; Path=/; HttpOnly; Max-Age=2592000`.
   - Jika nilai > 10, arahkan ke origin legacy.
2. **Request Execution & Fallback State Machine**:
   - Jika target adalah Canary (`origin-k8s`), kirim subrequest dengan batas timeout ketat menggunakan `AbortSignal.timeout(1000)`.
   - Lakukan evaluasi response:
   ```javascript
   let targetOrigin = isCanary ? ORIGIN_AWS : ORIGIN_LEGACY;
   let response;
   try {
     response = await fetch(buildRequest(targetOrigin, request));
     // Deteksi 5xx error pada Canary origin
     if (isCanary && [502, 503, 504].includes(response.status)) {
       throw new Error(`Canary origin failure: ${response.status}`);
     }
   } catch (err) {
     if (isCanary) {
       // Automatic transparent fallback ke origin legacy
       response = await fetch(buildRequest(ORIGIN_LEGACY, request));
       // Injeksi header indikasi fallback untuk monitoring SRE
       response = new Response(response.body, response);
       response.headers.set("X-Edge-Fallback", "true");
     } else {
       throw err;
     }
   }
   ```
3. **Observabilitas**:
   - Kirimkan telemetri status fallback ke analytics engine via `ctx.waitUntil()` untuk memperingatkan tim SRE jika rasio error pada Canary melebihi batas SLO.

---

## 4. Practical Chapter Challenge: Dynamic Edge Reverse Proxy with Real-time Transformations

### Spesifikasi Teknis Tantangan:
Anda diminta membangun sebuah proyek enterprise Cloudflare Worker terpadu yang bertindak sebagai **Reverse Proxy & Edge Gateway** lengkap dengan ketentuan arsitektur berikut:

1. **Routing Multi-Backend & Path Rewriting**:
   - Path `/api/*` diteruskan ke backend API mock: `https://dummyjson.com/` (dengan menghapus prefix `/api`).
   - Path `/docs/*` diteruskan ke static documentation origin: `https://httpbin.org/html`.
   - Path root `/` dialihkan secara default ke documentation origin.
2. **Edge Security Middleware**:
   - Mencegat request yang memiliki query parameter `?debug=true`. Jika parameter tersebut ada, Worker harus memeriksa header `X-Debug-Secret`. Jika header tidak cocok dengan environment secret `DEBUG_TOKEN`, blokir dengan HTTP 403 Forbidden JSON response.
3. **HTML Transformation Engine via `HTMLRewriter`**:
   - Untuk semua response HTML yang berasal dari `/docs/*`, gunakan `HTMLRewriter` untuk:
     - Mengubah isi tag `<title>` menjadi `Enterprise Edge Portal - Managed by Cloudflare Workers`.
     - Menyuntikkan banner navigasi darurat di awal tag `<body>`:
       `<div style="background: red; color: white; padding: 10px; text-align: center;">PRODUCTION EDGE GATEWAY ACTIVE</div>`.
     - Menghapus semua elemen `<h1>` dari origin dan menggantinya dengan element `<h2>Enterprise Distributed Edge System</h2>`.
4. **Resilient Streaming with Custom Telemetry Headers**:
   - Terapkan Web Streams API pipeline (`TransformStream`) untuk response payload JSON pada rute API.
   - Tambahkan header performa pada setiap response yang keluar ke pengguna:
     - `X-Edge-Origin-Time`: Waktu tunggu I/O ke origin (dalam ms).
     - `X-Edge-Region`: PoP data center Cloudflare tempat request diproses (didapat dari `request.cf.colo`).
     - `X-Edge-Security`: Status verifikasi middleware (`PASSED`).

---