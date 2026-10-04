# BAB 10: Quiz, Challenge, & Knowledge Check
**Observabilitas, Resiliensi, & Deployment Berskala Besar**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **OpenTelemetry & W3C Trace Context Propagation**  
   Bagaimana Next.js memfasilitasi propagasi *trace context* (berdasarkan standar W3C `traceparent` dan `tracestate`) dari panggilan browser sisi klien, melewati Next.js App Router (baik Edge Runtime maupun Node.js Server Components), hingga ke *downstream microservices*? Jelaskan fungsi `instrumentation.ts` dan batasan *context loss* yang mungkin terjadi jika pengembang menggunakan pemanggilan HTTP kustom di luar `fetch` bawaan.

2. **Core Web Vitals & Real User Monitoring (RUM)**  
   Bedakan mekanisme pengukuran performa sintetis (*Lighthouse/Lab data*) dengan *Field Data* (RUM) menggunakan fungsi `reportWebVitals` pada Next.js App Router. Bagaimana Anda mengekstrak metrik *Interaction to Next Paint* (INP) dan *Cumulative Layout Shift* (CLS) dari sesi pengguna riil dan menghubungkannya dengan metrik server-side seperti *Time to First Byte* (TTFB) untuk mendeteksi degradasi performa pada tingkat infrastruktur?

3. **Mekanisme Bundling `output: 'standalone'`**  
   Jelaskan secara teknis bagaimana Next.js mengompilasi aplikasi saat opsi `output: 'standalone'` diaktifkan di `next.config.js`. Analisis bagaimana Next.js menggunakan pelacakan ketergantungan statis (melalui `@vercel/nft`) untuk men-tree-shake direktori `node_modules`, dan sebutkan dependensi atau berkas apa saja yang sering luput (*asset missing*) sehingga harus ditangani secara eksplisit pada Dockerfile multi-stage.

4. **Resiliensi Rendering: Partial Prerendering (PPR) vs Dynamic Streaming Fallback**  
   Dari sudut pandang ketersediaan sistem (*high availability*), bagaimana kombinasi React Suspense Streaming (`loading.tsx`) dan Partial Prerendering melindungi sistem dari kegagalan total (*cascading failure*) ketika layanan pihak ketiga (*upstream dependency*) mengalami degradasi latensi tinggi (>5000ms)?

5. **Karakteristik Siklus Hidup Runtime: Serverless/Edge vs Containerized Node.js (Long-running)**  
   Bandingkan manajemen *connection pool* (misalnya koneksi database PostgreSQL atau Redis) dan risiko *memory leak* antara arsitektur deployment Next.js berbasis Serverless/Edge Functions versus Long-running Pods (Docker di Kubernetes). Mengapa pola *singleton instance* pada koneksi basis data dapat menjadi *anti-pattern* fatal pada lingkungan serverless namun menjadi kewajiban pada kontainer?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **AsyncLocalStorage dan Konteks Hilang pada Server Components**  
   Next.js mengandalkan `AsyncLocalStorage` dari Node.js untuk melacak konteks *request*, *headers*, dan *cookies* di dalam Server Components. Dalam skenario apa pembuatan thread baru (*Worker threads*), pemanggilan asynchronous yang tidak di-*await* secara tepat, atau pustaka eksternal pihak ketiga dapat memutus (*context stripping*) rantai pelacakan OpenTelemetry? Bagaimana cara merekonstruksi konteks tersebut?

2. **Diagnostik Event Loop Lag dan CPU Saturation pada SSR**  
   Sebuah kluster Next.js di Kubernetes mengalami peningkatan drastis pada metrik *Event Loop Lag* (>100ms) di bawah beban 5.000 RPS, meskipun konsumsi memori pod masih stabil di bawah 40%. Jelaskan langkah diagnostik sistematis untuk mengidentifikasi apakah akar masalahnya berada pada:
   - Serialisasi JSON berukuran masif pada RSC payload.
   - Operasi kriptografi/hashing sinkron di Middleware.
   - Regular Expression Denial of Service (ReDoS) pada penanganan *rewrites*/*redirects*.

3. **Inkonsistensi State pada Multi-Region Deployment & Custom Cache Handler**  
   Saat men-deploy Next.js secara *multi-region* (misalnya: Frankfurt dan Jakarta) menggunakan `cacheHandler` kustom berbasis Redis, jelaskan skenario *race condition* yang memicu fenomena *split-brain* atau *stale cache drift* ketika pemanggilan `revalidateTag()` dieksekusi di Region A tetapi dibaca secara bersamaan di Region B. Bagaimana strategi implementasi *distributed invalidation queue* mengatasi masalah ini?

4. **Debugging V8 Heap Exhaustion (OOMKilled) pada Standalone Docker**  
   Sebuah kontainer Next.js terus mengalami *crash* berkala akibat `Exit Code 137 (OOMKilled)`. Saat diuji secara lokal, penggunaan RAM terlihat normal. Jelaskan metodologi pembuatan *heap snapshot* saat *runtime* produksi tanpa mematikan pod, bagaimana membaca alokasi memori retained pada *closures* Server Action, dan peran alokasi memori internal *buffer* Next.js saat menangani respons streaming yang lambat dikonsumsi klien (*slow consumers* / *backpressure failure*).

5. **Implementasi Resiliensi: Timeout & Circuit Breaker pada Next Data Layer**  
   Rancang arsitektur interseptor data fetching di Next.js menggunakan pola *Circuit Breaker* (misalnya via opossum/cockatiel) dan *Exponential Backoff with Jitter*. Jelaskan bagaimana interseptor ini harus berinteraksi dengan mekanisme internal Next.js `fetch` (yang memiliki subsistem `next: { revalidate, tags }`) agar ketika sirkuit berada pada status `OPEN`, Next.js tetap menyajikan data *stale-while-revalidate* dari cache alih-alih melempar Unhandled Promise Rejection ke pengguna.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Black Friday Cascading Collapse
Platform e-commerce yang berjalan di atas kluster Kubernetes (20 Pod Next.js, autoscaling HPA maks 100 Pod) mengalami *total outage* 10 menit setelah kampanye diskon diluncurkan. 
- **Gejala:** Metrik CPU melonjak ke 100%, HPA memicu *scale-out* agresif ke 100 Pod. Namun, penambahan Pod justru mempercepat kegagalan: Pod baru membutuhkan waktu 45 detik untuk lolos `readinessProbe` dan segera *crash* dengan status `OOMKilled`. 
- **Log Indikasi:** Ribuan log `undici: Client Connection Timeout` bercampur dengan `FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`. Upstream inventory API dilaporkan mengalami degradasi (respons melambat dari 50ms ke 4500ms).

*Pertanyaan Diagnostik & Mitigasi:*
1. Mengapa lonjakan latensi pada upstream service memicu konsumsi memori eksponensial pada instance Next.js hingga memicu OOMKilled, alih-alih hanya membuat respons menjadi lambat?
2. Bagaimana konfigurasi Next.js Standalone, Node.js HTTP/Undici agent, dan Kubernetes Probes (`liveness`, `readiness`, `startup`) harus dimodifikasi untuk memutus rantai kegagalan kaskade (*cascading failure*) ini secara instan di level *network* dan *runtime*?

---

### Skenario B: Cache Poisoning & Stale Asset Hash pada Blue-Green Deployment
Sebuah perusahaan fintech menerapkan strategi deployment *Blue-Green* di depan Cloudflare CDN. Ketika traffic dialihkan dari Blue (versi `v1.2.0`) ke Green (versi `v1.3.0`):
- **Gejala:** 5% pengguna mengalami antarmuka yang hancur total (*white-screen of death*). Konsol browser mereka menunjukkan error: `Loading chunk failed: _next/static/chunks/app/dashboard/[hash].js (404 Not Found)`. 
- **Temuan Forensik:** Pengguna yang mengalami galat menerima dokumen HTML dari versi Green (`v1.3.0`), tetapi URL chunk JavaScript statis yang dimuat oleh dokumen tersebut dialihkan ke CDN/origin yang masih melayani versi Blue (`v1.2.0`), atau sebaliknya. File hash JavaScript `v1.3.0` belum tereplikasi ke seluruh CDN Edge PoP saat traffic di-cutover.

*Pertanyaan Diagnostik & Mitigasi:*
1. Analisis titik kegagalan arsitektural yang menyebabkan disinkronisasi antara Next.js HTML response dan berkas immutable statis (`/_next/static/*`) saat proses cutover traffic.
2. Rancang arsitektur pipeline CI/CD dan strategi hosting aset statis (misalnya menggunakan AWS S3/GCS bucket dengan `assetPrefix`) yang sepenuhnya mengisolasi aset versi lama dan versi baru, sehingga menjamin *zero-downtime* dan eliminasi total error `ChunkLoadError` selama proses *phased rollout*.

---

### Skenario C: Kebocoran Data Multi-Tenant pada Middleware & Logging Trace
Sistem SaaS multi-tenant dengan ribuan pelanggan korporat melaporkan insiden kepatuhan keamanan (*compliance breach*):
- **Gejala:** Administrator Perusahaan X menemukan log aktivitas dan data transaksi terenkripsi milik Perusahaan Y muncul di dasbor pemantauan Datadog/Grafana mereka.
- **Investigasi:** Tim menggunakan custom OpenTelemetry span processor dan logging global pada Next.js `middleware.ts` untuk merekam data header otentikasi (`x-tenant-id`), serta menaruh *user session payload* ke dalam *global object* untuk mempermudah injeksi metadata ke log di dalam Server Actions dan Route Handlers.

*Pertanyaan Diagnostik & Mitigasi:*
1. Tunjukkan letak kerentanan arsitektural pada penanganan *shared memory/state* di dalam V8 runtime Next.js (terutama Middleware Edge/Node.js) yang menyebabkan metadata tenant tercampur antar *concurrent requests*.
2. Rancang arsitektur observabilitas (Logging, Tracing, dan Metrik) yang *thread-safe* dan mengisolasi konteks tenant secara kedap menggunakan `AsyncLocalStorage` serta *redaction pipeline* otomatis untuk memblokir PII (*Personally Identifiable Information*) sebelum diekspor ke collector pihak ketiga.

---

## 4. Chapter Challenge

**Tantangan Praktis: Enterprise Resilience & Observability Harness**

### Deskripsi Masalah
Perusahaan Anda memiliki aplikasi Next.js (App Router) dengan beban transaksi tinggi yang sering mengalami *downtime* parsial karena backend microservices yang tidak stabil, ketiadaan visibilitas *distributed trace*, dan kontainerisasi yang tidak efisien (ukuran image >1.5GB dengan alokasi memori tidak terkontrol).

### Spesifikasi Kebutuhan

1. **OpenTelemetry Full-Stack Instrumentation:**
   - Implementasikan file `instrumentation.ts` yang menginisiasi OpenTelemetry SDK (Node.js & Edge Runtime).
   - Buat *custom span* manual di dalam Server Action kompleks yang mencatat *event*, atribut status bisnis (misal: `order.id`, `tenant.id`), serta menangkap error secara otomatis dengan status `SpanStatusCode.ERROR`.
   - Konfigurasikan OTLP Trace Exporter untuk mengirim span via protokol gRPC/HTTP ke OpenTelemetry Collector.

2. **Resilient Data Access Layer (Circuit Breaker & Fallback):**
   - Bangun sebuah utilitas pembungkus `resilientFetch()` yang mengimplementasikan:
     - Pola *Circuit Breaker* (Status: `CLOSED`, `OPEN`, `HALF-OPEN`).
     - Strict execution timeout (misal: 2500ms) menggunakan `AbortController`.
     - *Graceful Fallback*: Jika sirkuit `OPEN` atau terjadi timeout, fungsi otomatis mengembalikan data dari persistent stale cache (misal: Redis lokal atau mock fallback data) tanpa melempar *crash* ke UI layer.

3. **Production-Ready Enterprise Dockerfile:**
   - Buat multi-stage Dockerfile berbasis alpine/distroless untuk `output: 'standalone'`.
   - Wajib mengimplementasikan pengguna non-root (`nextjs:nodejs`, UID/GID 1001).
   - Terapkan alokasi memori V8 yang ketat via flag `--max-old-space-size` yang disinkronkan dengan limit Kubernetes cgroup.
   - Sediakan skrip penanganan sinyal OS (`SIGTERM` dan `SIGINT`) untuk *graceful shutdown*, memastikan koneksi database dan in-flight request diselesaikan dalam *grace period* 30 detik.

4. **Health Check Probes Route Handler:**
   - Buat route `/api/healthz/liveness` (mengecek kesiapan runtime Node.js).
   - Buat route `/api/healthz/readiness` (melakukan evaluasi konektivitas upstream: database, cache, dan memory threshold usage <90%).

### Batasan (Constraints)
- Ukuran final Docker image tidak boleh melebihi **180 MB**.
- Tidak boleh menggunakan pustaka observabilitas yang membungkus (monkey-patch) global scope secara destruktif tanpa kompatibilitas ESM.
- Semua implementasi TypeScript harus menggunakan *strict mode* tanpa ada penggunaan tipe `any`.

### Expected Output
- Repositori/arsip berkas yang berisi:
  - `instrumentation.ts`
  - `lib/resilience/resilient-fetch.ts`
  - `app/api/healthz/readiness/route.ts`
  - `app/api/healthz/liveness/route.ts`
  - `Dockerfile` & `.dockerignore`
  - Ringkasan arsitektur dalam format Markdown (`OBSERVABILITY_ARCHITECTURE.md`) yang menjelaskan alur propagasi trace dari ingress hingga backend service.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal propagasi *trace context* W3C pada Next.js Server Components, Server Actions, Route Handlers, dan Edge Middleware.
- [ ] Batasan runtime V8 dalam eksekusi I/O intensif dan dampaknya terhadap Node.js Event Loop Lag pada komputasi SSR.
- [ ] Perbedaan fundamental arsitektur *lifecycle* kontainer standalone vs platform *serverless* terkelola (Vercel/Cloudflare).
- [ ] Pola resiliensi microservices: Circuit Breaker, Bulkhead, Retry with Jitter, dan Deadline/Timeout Propagation.
- [ ] Siklus invalidasi cache terdistribusi (`revalidateTag`, `revalidatePath`) dan penanganannya pada deployment multi-instance/multi-region.
- [ ] Mengapa variabel lingkungan *build-time* vs *runtime* harus dipisahkan secara ketat dalam arsitektur Docker immutable.

### Saya tidak perlu menghafal:
- [ ] Spesifikasi byte-level dari payload protokol OTLP/gRPC (cukup pahami konfigurasi exporter dan struktur atribut span).
- [ ] Sintaks baris per baris konfigurasi internal webpack/turbopack Next.js (fokus pada abstraksi `next.config.js`).
- [ ] Perhitungan matematika eksak kurva desil pada histogram metrik RUM (cukup pahami representasi p75, p95, dan p99).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan mengaktifkan OpenTelemetry via `instrumentation.ts` untuk melacak latensi Server Components hingga ke database query.
- [ ] Menganalisis *Heap Memory Dump* dan *CPU Profile* dari instance Next.js produksi untuk melacak memory leak dan CPU bottleneck.
- [ ] Menulis Dockerfile multi-stage berstandar industri dengan optimasi ukuran image, non-root user privilege, dan implementasi OS signal trapping.
- [ ] Merancang dan mengeksekusi strategi deployment *zero-downtime* (Canary/Blue-Green) dengan pemisahan aset statis ke Object Storage (CDN Offloading).
- [ ] Mengimplementasikan *Graceful Degradation* pada aplikasi berskala besar sehingga kegagalan satu komponen backend tidak merusak seluruh halaman web.