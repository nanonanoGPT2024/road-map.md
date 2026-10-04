# Modul 01: Edge Compute Serverless: Cloudflare Workers & Pages

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengartikulasikan perbedaan arsitektural mendasar antara *V8 Isolates* dan *Container-based Serverless* (Docker/Kubernetes/AWS Lambda), terutama terkait *cold start*, alokasi memori, isolasi *runtime*, dan jejak *footprint* sistem.
- Mengembangkan, menguji secara lokal, dan mengotomatisasi *deployment* Cloudflare Workers menggunakan Wrangler CLI versi 3.x+ dengan arsitektur berbasis ES Modules.
- Mengimplementasikan manipulasi *payload* berbasis *streaming* berkinerja tinggi menggunakan Web Streams API (`ReadableStream`, `WritableStream`, `TransformStream`) untuk memitigasi latensi dan konsumsi memori edge.
- Melakukan transformasi struktur DOM secara *line-rate* tanpa *memory overhead* berbasis parsing pohon DOM penuh menggunakan *streaming API* `HTMLRewriter`.
- Merancang dan membangun alur CI/CD untuk aplikasi frontend modern dan *full-stack serverless* menggunakan Cloudflare Pages dan Pages Functions.
- Menyusun arsitektur *Edge Middleware* dan *Server-Side Rendering* (SSR) untuk manipulasi header, otentikasi JWT terdistribusi, A/B *testing*, serta orkestrasi *subrequest* multi-origin.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta harus menguasai:
- Pengetahuan mendalam tentang protokol HTTP/1.1, HTTP/2, dan HTTP/3 (siklus Request/Response, Header, Status Code, chunked transfer encoding).
- Pemahaman JavaScript modern (ECMAScript 2022+): `async/await`, `Promise`, ES Modules syntax (`export default`), Web API dasar (`fetch`, `Request`, `Response`, `Headers`).
- Konsep dasar jaringan komputer dan CDN: Edge nodes, Anycast routing, Point of Presence (PoP), caching tiers.
- Pengalaman menggunakan antarmuka baris perintah (CLI) dan Node.js/npm runtime ecosystem.

---

## 3. Concept
Komputasi serverless tradisional (seperti AWS Lambda, Google Cloud Functions) umumnya berjalan di atas arsitektur berbasis kontainer atau virtualisasi mikro (*microVM* seperti Firecracker). Setiap fungsi memerlukan alokasi sistem operasi mini, runtime language terisolasi (Node.js engine, Python interpreter), dan variabel lingkungan independen. Konsekuensinya adalah adanya *cold start* (100ms hingga beberapa detik) dan konsumsi memori minimal puluhan hingga ratusan megabyte per *instance*.

Cloudflare Workers merevolusi paradigma ini dengan memanfaatkan arsitektur **V8 Isolates**. V8 adalah JavaScript engine open-source milik Google yang mentenagai Google Chrome dan Node.js. Alih-alih menjalankan proses sistem operasi atau kontainer baru untuk setiap fungsi, Cloudflare menjalankan satu proses V8 besar pada ribuan server edge Anycast-nya. Di dalam satu proses tersebut, Cloudflare menciptakan ribuan lingkungan eksekusi terisolasi yang disebut **Isolates**. 

Isolates membatasi akses memori, mengeksekusi kode secara paralel, dan menegakkan batas keamanan secara *cryptographic-grade* dan *memory-safe* tanpa biaya *overhead* virtualisasi OS. Keuntungan revolusionernya adalah:
1. **Zero Cold Start**: Waktu inisialisasi Isolate berada di bawah 5 milidetik (sering kali < 1ms).
2. **Ultra-low Memory Footprint**: Sebuah Isolate dapat berukuran sekecil beberapa kilobyte memori.
3. **Global Proximity**: Kode dieksekusi secara instan di edge PoP Cloudflare yang paling dekat dengan klien (Anycast), bukan di region data center terpusat.

Di atas fondasi ini, Cloudflare Workers berfungsi sebagai programmable proxy dan komputasi edge berfitur lengkap, sementara Cloudflare Pages menyediakan platform hosting Git-integrated yang dioptimalkan untuk Single Page Applications (SPA), Static Site Generators (SSG), dan framework SSR edge modern.

---

## 4. Why
Mengapa arsitektur komputasi edge serverless berbasis Isolates krusial bagi infrastruktur SRE modern?

- **Pemberantasan Latensi RTT (Round Trip Time)**: Pada arsitektur komputasi terpusat (misal: AWS `us-east-1`), pengguna dari Asia Tenggara harus menempuh RTT fisik ~200-250ms hanya untuk autentikasi API atau SSR render. Dengan Cloudflare Workers, eksekusi dilakukan di Jakarta, Singapura, atau kota lokal lainnya dengan RTT < 10ms.
- **Efisiensi Finansial dan Skalabilitas Ekstrem**: Skalabilitas kontainer di Kubernetes membutuhkan *horizontal pod autoscaler* (HPA) yang membutuhkan hitungan menit untuk mendeteksi metrik CPU dan mem-provisioning node baru. Isolates dapat menangani lonjakan dari 0 hingga ratusan ribu request per detik secara instan tanpa proses *capacity planning* kluster.
- **Dekoupling Arsitektur Monolitik**: Workers memungkinkan implementasi pola arsitektur *Strangler Fig*. Edge worker dapat mencegat trafik ke monolit lama, melakukan dynamic routing ke microservices baru, memvalidasi otentikasi, atau memanipulasi response tanpa menyentuh kode aplikasi origin backend.
- **Zero Ingestion/DOM Latency via Streaming**: Dengan Web Streams dan `HTMLRewriter`, Workers dapat memproses dan memodifikasi body response berukuran gigabyte atau halaman HTML kompleks saat byte pertama mengalir dari origin ke klien (*line-rate processing*), tanpa harus memuat seluruh body ke memori server.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 V8 Isolates vs Containers: Deep Comparative Architecture
| Parameter Arsitektur | Traditional Container (Docker/K8s/Lambda) | Cloudflare Workers (V8 Isolates) |
| :--- | :--- | :--- |
| **Batas Isolasi (Isolation Boundary)** | Linux Namespaces, cgroups, seccomp, kernel boundary | V8 Isolate memory heap boundary, sandboxed pointers |
| **Inisialisasi (Cold Start)** | 100ms - 5000ms (Container launch, runtime init) | < 5ms (Inisialisasi konteks V8 di thread yang sudah ada) |
| **Overhead Memori Dasar** | ~30MB - 128MB+ per instance | ~1MB - 5MB runtime context footprint |
| **Kepadatan Multi-tenancy** | Ratusan container per physical host server | Puluhan ribu Isolates per physical host process |
| **Arsitektur Model Eksekusi** | 1 instance = 1 OS Process / MicroVM | Multi-tenant single-process, asynchronous event-loop |
| **Kompatibilitas Runtime** | Arbitrary OS binaries (C++, Go, Python, Java) | JavaScript, TypeScript, WebAssembly (Wasm) |

V8 Isolate memanfaatkan pointer sandbox: kode JavaScript yang berjalan di dalam Isolate tidak dapat mengakses pointer memori di luar heap yang dialokasikan untuk Isolate tersebut. Jika sebuah Isolate mengalami crash (misal: out of memory), hanya Isolate tersebut yang dihentikan; proses host Cloudflare dan Isolate lain di server yang sama tetap berjalan tanpa terpengaruh.

### 5.2 CPU Time vs Wall-Clock Time
Pembedaan krusial dalam Cloudflare Workers:
- **CPU Time**: Waktu aktual yang dihabiskan oleh CPU untuk mengeksekusi instruksi komputasi kode JS/Wasm Anda (parsing JSON, komputasi kriptografi, manipulasi array). Limit paket standard adalah 50ms CPU time (atau hingga ratusan ms pada Enterprise).
- **Wall-Clock Time**: Total durasi kalender dari awal request diterima hingga response selesai dikirim. Wall-clock time mencakup latensi jaringan I/O saat Worker menunggu subrequest `fetch()` dari origin database, cache lookup, atau API eksternal. Workers **tidak membatasi** Wall-Clock time secara ketat seperti CPU time; worker dapat menunggu operasi network I/O selama puluhan detik selama subrequest aktif dan CPU time tidak terlampaui.

### 5.3 Request and Response Streaming (Web Streams API)
Secara default, jika sebuah aplikasi melakukan `await response.text()` atau `await response.json()`, seluruh payload harus diunduh ke dalam memori RAM sebelum dieksekusi. Ini menciptakan:
1. Lonjakan memori (potensi *Worker Memory Exceeded limit* 128MB).
2. Time To First Byte (TTFB) yang buruk karena klien harus menunggu seluruh origin response selesai diproses.

Cloudflare Workers mendukung implementasi standar **Web Streams API**:
- `ReadableStream`: Sumber data sequential byte yang dapat dibaca secara chunk-by-chunk.
- `WritableStream`: Destinasi penulisan byte stream.
- `TransformStream`: Terdiri dari `ReadableStream` dan `WritableStream` yang terhubung secara internal. Data ditulis ke *writable side*, ditransformasikan oleh callback `transform()`, dan langsung tersedia untuk dibaca di *readable side*.

Dengan mem-pipe stream dari subrequest origin langsung ke client response (`response.body.pipeThrough(transformStream)`), Worker menerapkan mekanisme **backpressure**. Jika koneksi internet klien lambat, kecepatan pembacaan dari origin otomatis melambat, menjaga stabilitas konsumsi memori edge worker pada level minimum konstan (~beberapa KB).

### 5.4 Edge HTML Rewriting (`HTMLRewriter`)
`HTMLRewriter` adalah API bawaan Cloudflare Workers yang ditulis menggunakan Rust (*lol-html parser*) dan dikompilasi ke native engine Workers. Berbeda dengan parser DOM standar (seperti JSDOM atau Cheerio) yang mem-parsing seluruh teks HTML menjadi struktur tree object memory yang sangat mahal:
- `HTMLRewriter` bekerja secara streaming berbasis state-machine (SAX-like parser).
- Kode CSS selector dievaluasi secara linier seiring byte HTML mengalir melalui Worker.
- Memungkinkan injeksi skrip, penghapusan elemen, penggantian teks, atau mutasi atribut secara real-time tanpa parsing DOM lengkap.
- Latensi pemrosesan mendekati nol (*sub-millisecond streaming overhead*).

### 5.5 Cloudflare Pages & Pages Functions
Cloudflare Pages berevolusi dari platform hosting static assets menjadi platform full-stack compute:
- **Pages Core**: CDN storage terdistribusi untuk asset statis (HTML, CSS, JS bundle, assets) yang di-deploy via Git atau Direct Upload.
- **Pages Functions**: Eksekusi Workers berbasis konvensi direktori. File yang diletakkan pada folder `/functions` otomatis dikompilasi menjadi Cloudflare Workers.
- **File-based Routing**: File seperti `/functions/api/users/[id].js` secara otomatis memetakan HTTP request ke path `/api/users/:id`.
- **Middleware Support**: File `_middleware.js` di dalam direktori memproses request sebelum dialihkan ke subdirektori atau aset statis berikutnya.

---

## 6. How
Implementasi pengembangan ekosistem Workers dan Pages dilakukan melalui **Wrangler CLI**.

### Alur Kerja Wrangler CLI 3.x+
1. **Inisialisasi Project**:
   ```bash
   npm create cloudflare@latest edge-service -- --type=hello-world
   cd edge-service
   ```
2. **Struktur Konfigurasi (`wrangler.toml` atau `wrangler.jsonc`)**:
   Mendefinisikan nama worker, *compatibility date*, binding (KV, D1, R2, Environment Variables), dan konfigurasi routing.
3. **Pengujian Lokal (*Local Simulation*)**:
   Wrangler 3 menggunakan runtime open-source `workerd` (runtime aktual yang mentenagai Cloudflare Workers di production), bukan lingkungan emulasi mock Node.js.
   ```bash
   npx wrangler dev
   ```
4. **Secret Management**:
   Menyimpan secret (API Keys, private keys) secara terenkripsi di edge:
   ```bash
   npx wrangler secret put JWT_SECRET
   ```
5. **Deployment**:
   Mempublikasikan kode secara global ke seluruh edge PoP Cloudflare dalam hitungan detik:
   ```bash
   npx wrangler deploy
   ```

---

## 7. Analogy
Bayangkan Anda ingin menyewakan ruang kerja untuk 1.000 pekerja mandiri:

- **Arsitektur Container (Docker/K8s)**:
  Anda membangun 1.000 rumah petak terpisah. Setiap rumah memiliki pondasi sendiri, instalasi pipa ledeng sendiri, genset listrik sendiri, dan sistem pendingin udara sendiri. Butuh waktu lama untuk menyalakan genset setiap rumah (*cold start*), dan lahan yang dibutuhkan luar biasa luas (*high memory footprint*).
  
- **Arsitektur V8 Isolates (Cloudflare Workers)**:
  Anda membangun sebuah gedung pencakar langit modern terintegrasi dengan satu sistem AC sentral, satu sistem plumbing, dan sistem keamanan bersama. Setiap pekerja mendapatkan meja kerja pribadi dengan sekat kedap suara dan kunci biometrik (*Isolate*). Membuat ruang kerja baru hanya butuh waktu 1 detik untuk membersihkan meja (*0ms cold start*), dan Anda dapat menampung puluhan ribu pekerja di dalam satu gedung efisien tanpa saling mengganggu.

---

## 8. Diagram (ASCII)

### Diagram 1: Arsitektur Eksekusi V8 Isolates vs Containers

```
================= CONTAINER ARCHITECTURE (AWS LAMBDA / DOCKER) =================
+------------------------------------------------------------------------------+
| Host OS (Linux Kernel)                                                       |
|  +---------------------------+  +---------------------------+                |
|  | Container Runtime (Docker)|  | Container Runtime (Docker)|                |
|  | +-----------------------+ |  | +-----------------------+ |                |
|  | | Guest OS / MicroVM    | |  | | Guest OS / MicroVM    | |                |
|  | | Node.js Runtime       | |  | | Node.js Runtime       | |                |
|  | | App Code (Heap 50MB+) | |  | | App Code (Heap 50MB+) | |                |
|  | +-----------------------+ |  | +-----------------------+ |                |
|  +---------------------------+  +---------------------------+                |
|  Cold Start: 200ms - 2000ms     Memory Overhead: Masif                      |
+------------------------------------------------------------------------------+

================== CLOUDFLARE WORKERS V8 ISOLATE ARCHITECTURE ==================
+------------------------------------------------------------------------------+
| Host OS (Linux Kernel optimized for Edge)                                    |
|  +-------------------------------------------------------------------------+ |
|  | Single V8 Process (Cloudflare workerd Engine)                           | |
|  |                                                                         | |
|  |  +--------------------+  +--------------------+  +--------------------+ | |
|  |  | V8 Isolate #001    |  | V8 Isolate #002    |  | V8 Isolate #N      | | |
|  |  | (Tenant A: Worker) |  | (Tenant B: Worker) |  | (Tenant C: Worker) | | |
|  |  | Heap: ~2MB         |  | Heap: ~1.5MB       |  | Heap: ~3MB         | | |
|  |  +--------------------+  +--------------------+  +--------------------+ | |
|  +-------------------------------------------------------------------------+ |
|  Cold Start: < 5ms              Memory Overhead: Sangat Ringan (< 5MB)      |
+------------------------------------------------------------------------------+
```

### Diagram 2: Pipeline Streaming Response dan HTMLRewriter

```
Client (Browser)             Cloudflare Edge Worker                 Origin Server
      |                                |                                  |
      | 1. HTTP GET /product/123       |                                  |
      |------------------------------->| 2. fetch(originRequest)          |
      |                                |--------------------------------->|
      |                                |                                  |
      |                                | 3. HTTP 200 OK (Stream Body)     |
      |                                |<---------------------------------|
      |                                |                                  |
      |                                | [TransformStream / HTMLRewriter] |
      |                                | - Byte chunk diterima di edge    |
      |                                | - Parser mencocokkan selector    |
      | 4. HTTP 200 OK (Stream Chunk)  | - Modifikasi DOM on-the-fly      |
      |<-------------------------------| - Byte diteruskan ke client      |
      | 5. Stream Chunk N...           |                                  |
      |<-------------------------------|                                  |
      | 6. EOF (Stream Completed)      |                                  |
      |<-------------------------------|                                  |
```

---

## 9. Simple Example
Sebuah Worker sederhana yang bertindak sebagai Edge Middleware untuk memeriksa header otentikasi kustom dan memanipulasi header respons:

```javascript
export default {
  async fetch(request, env, ctx) {
    // Edge Middleware Check: Autentikasi API Key sederhana
    const apiKey = request.headers.get("x-edge-api-key");
    if (!apiKey || apiKey !== env.EXPECTED_API_KEY) {
      return new Response(JSON.stringify({ error: "Unauthorized access at edge" }), {
        status: 401,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Capture waktu eksekusi
    const startTime = Date.now();

    // Meneruskan request ke origin server
    const response = await fetch(request);

    // Kloning response header untuk dimutasi (Response headers bawaan bersifat read-only)
    const newHeaders = new Headers(response.headers);
    newHeaders.set("X-Edge-Processed-By", "Cloudflare-Worker-V8");
    newHeaders.set("X-Edge-Latency-MS", (Date.now() - startTime).toString());

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders
    });
  }
};
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

Berikut adalah konfigurasi production Worker dengan `wrangler.toml` dan skrip middleware kompleks yang mengimplementasikan geo-routing, response streaming transformation, dan injeksi elemen via `HTMLRewriter`.

### Konfigurasi: `wrangler.toml`
```toml
name = "edge-proxy-suite"
main = "src/index.js"
compatibility_date = "2024-04-01"
compatibility_flags = ["nodejs_compat"]

[vars]
ENVIRONMENT = "production"
BACKEND_ORIGIN = "https://origin.internal.enterprise.com"

# Bindings untuk Secret didefinisikan via CLI: npx wrangler secret put EDGE_SIGNING_KEY
```

### Kode Implementasi: `src/index.js`
```javascript
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Geolocation & Security Middleware
    const country = request.cf?.country || "XX";
    const clientIP = request.headers.get("cf-connecting-ip") || "unknown";

    if (["RU", "KP"].includes(country) && url.pathname.startsWith("/admin")) {
      return new Response("Forbidden: Restricted Geo Region", { status: 403 });
    }

    // 2. Routing Logic ke Origin
    const targetUrl = new URL(env.BACKEND_ORIGIN);
    targetUrl.pathname = url.pathname;
    targetUrl.search = url.search;

    const proxyRequest = new Request(targetUrl.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.body,
      redirect: "manual"
    });

    // Tambahkan tracing header ke origin
    proxyRequest.headers.set("X-Forwarded-For", clientIP);
    proxyRequest.headers.set("X-Edge-Country", country);

    // 3. Subrequest ke Origin
    const originResponse = await fetch(proxyRequest);

    // 4. Edge HTMLRewriting jika content-type adalah text/html
    const contentType = originResponse.headers.get("content-type") || "";
    if (contentType.includes("text/html")) {
      const rewriter = new HTMLRewriter()
        .on("head", {
          element(element) {
            element.append(
              `<meta name="x-edge-worker" content="cf-v8-isolate" />
               <meta name="x-client-country" content="${country}" />`,
              { html: true }
            );
          }
        })
        .on("div#geo-banner", {
          element(element) {
            element.setInnerContent(
              `Selamat datang pengunjung dari ${country}! Pengiriman lokal tersedia.`,
              { html: false }
            );
          }
        });

      // Streaming transformasi langsung ke client
      const transformedStream = rewriter.transform(originResponse);
      return new Response(transformedStream.body, {
        status: originResponse.status,
        headers: originResponse.headers
      });
    }

    // 5. Streaming Response untuk Asset / Data non-HTML menggunakan TransformStream
    const { readable, writable } = new TransformStream({
      transform(chunk, controller) {
        // Pass-through chunk tanpa buffer
        controller.enqueue(chunk);
      }
    });

    originResponse.body.pipeTo(writable).catch((err) => {
      console.error("Stream pipe failed:", err);
    });

    const responseHeaders = new Headers(originResponse.headers);
    responseHeaders.set("X-Edge-Proxy", "Active");

    return new Response(readable, {
      status: originResponse.status,
      headers: responseHeaders
    });
  }
};
```

---

## 11. Real World Example
Sebuah platform E-Commerce multinasional menghadapi kendala arsitektur cache: Halaman detail produk (PDP) di-cache secara statis di CDN origin untuk menahan beban jutaan request per detik. Namun, kebutuhan bisnis menuntut agar:
1. Tombol keranjang belanja harus menampilkan jumlah item aktual pengguna.
2. Nama user yang login harus muncul di navbar.
3. Harga mata uang harus dinamis berdasarkan IP negara asal pengunjung.

**Solusi Konvensional**: 
Mematikan cache CDN pada halaman HTML (mengakibatkan database overload di backend) ATAU melakukan client-side fetch (AJAX) setelah halaman render (menyebabkan layout shift dan latency tinggi).

**Solusi Edge Cloudflare Workers dengan `HTMLRewriter`**:
1. CDN tetap meng-cache halaman PDP HTML dasar secara statis di Edge Cache (Cache Hit ratio > 95%).
2. Ketika request masuk, Worker membaca JWT dari cookie browser pengguna.
3. Worker mengambil body HTML dari cache edge secara lokal via `fetch(cacheKey)`.
4. Menggunakan `HTMLRewriter`, Worker menginjeksi state cart dan nama profil dari cookie langsung ke dalam placeholder markup HTML:
   ```javascript
   new HTMLRewriter()
     .on("span#user-cart-count", {
       element(el) { el.setInnerContent(parsedCartCount); }
     })
     .on("span#user-name-display", {
       element(el) { el.setInnerContent(escapeHtml(userName)); }
     })
     .transform(cachedResponse);
   ```
5. Hasilnya dikirim ke browser secara streaming. 

**Hasil**: Browser menerima halaman yang sepenuhnya terpersonalisasi (seperti SSR penuh) pada byte pertama dengan TTFB di bawah 30ms, tanpa pernah membebani database origin backend.

---

## 12. Trade-offs

| Keuntungan (Pros) | Keterbatasan / Kerugian (Cons) |
| :--- | :--- |
| **0ms Cold Start**: Eksekusi instan tanpa siklus booting VM/container. | **Tidak Ada Dukungan Native Binary**: Tidak dapat mengeksekusi binary Linux arbitrary atau library native C/C++ tanpa porting ke WebAssembly. |
| **Global Deployment**: Kode langsung terdistribusi ke >300 PoP global. | **Limit Eksekusi CPU**: CPU time dibatasi ketat (default 50ms untuk Worker non-enterprise). Operasi CPU-heavy berat (video transcoding, model training) dilarang. |
| **Kinerja Memori**: Model streaming mengonsumsi memori minimal (<5MB). | **Batasan Memori Absolut**: Memori Isolate dibatasi hingga 128MB (Standard) / 256MB+ (Enterprise), tidak cocok untuk parsing in-memory dataset raksasa. |
| **Zero Ingestion Latency**: `HTMLRewriter` mentransformasi data tanpa buffer penuh. | **Keterbatasan Ekosistem Node.js**: Meski ada `nodejs_compat`, API yang bergantung pada OS filesystem (`fs`), child processes (`child_process`), dan native bindings tidak didukung. |

---

## 13. When To Use
- **Edge Routing & Dynamic Reverse Proxying**: Membagi lalu lintas antar backend origin yang berbeda berdasarkan path, cookie, atau header.
- **Header Security & Token Validation**: Memvalidasi JWT, menandatangani URL (HMAC), atau menambahkan header keamanan (CSP, HSTS) sebelum request menyentuh origin.
- **Edge Personalization**: Mengubah konten HTML statis yang di-cache menggunakan `HTMLRewriter` berdasarkan geolokasi, device type, atau A/B test variants.
- **API Gateways**: Melakukan request aggregation (menggabungkan data dari 2 REST endpoint origin menjadi satu response JSON ringkas untuk mobile app).
- **Edge Server-Side Rendering (SSR)**: Merender frontend modern (Remix, Next.js, SvelteKit, Astro) langsung di edge server terdekat dengan pengguna.

---

## 14. When NOT To Use
- **Komputasi Berat Jangka Panjang (*Long-running Batch Jobs*)**: Proses rendering 3D, transcoding video, atau eksekusi algoritma machine learning yang membutuhkan menit hingga jam komputasi CPU murni.
- **Aplikasi Monolitik Legacy Berbasis Node.js OS Access**: Aplikasi yang membutuhkan direct access ke sistem file lokal OS (`/tmp` disk writes besar), Unix domain sockets, atau binding native binary `*.node`.
- **Koneksi Database Relasional Legacy Tanpa Pooling**: Aplikasi yang membuka ribuan koneksi langsung (TCP raw connection) ke Postgres/MySQL tanpa koneksi proxy edge-ready (seperti Prisma Accelerate, Cloudflare Hyperdrive, atau Supabase Connection Pooler).

---

## 15. Common Mistakes
- **Buffering Body saat Streaming Lebih Efisien**: Menggunakan `await response.text()` lalu melakukan `text.replace()`, alih-alih menggunakan `HTMLRewriter` atau `TransformStream`. Ini memicu *memory limit exhaustion* pada file besar dan merusak TTFB.
- **Menyimpan State di Global Variable**: Mendeklarasikan `let requestCount = 0;` di luar handler `fetch()`. Di lingkungan V8 Isolates terdistribusi, Isolate dapat dibuat, dihancurkan, atau dijalankan di PoP berbeda kapan saja. State global tidak dijamin sinkron atau persisten.
- **Mengabaikan Subrequest Limits**: Worker memiliki batas maksimal 50 subrequest (panggilan `fetch()` eksternal) per single incoming request. Menjalankan query fetch berulang dalam loop besar akan melempar *Error 1042: Subrequest limit exceeded*.
- **Mencampuradukkan CPU Time dan Wall-Clock Time**: Panik ketika melihat latency request 1.500ms, mengira melanggar CPU time limit 50ms. Padahal latensi tersebut adalah Wall-Clock time menunggu respons backend origin.

---

## 16. Best Practices
- **Manfaatkan `ctx.waitUntil()`**: Jika Worker perlu melakukan audit logging, pengiriman analytics, atau pelaporan metrik ke service eksternal, gunakan `ctx.waitUntil(promise)`. Worker akan segera mengirimkan HTTP response ke klien tanpa menunggu background task selesai, sehingga mengeliminasi latensi logging bagi pengguna.
- **Gunakan Single-Pass HTML Rewriting**: Jangan merangkai multiple instance `HTMLRewriter` secara bersarang jika satu instance dapat menangani semua CSS selector yang dibutuhkan.
- **Definisikan `compatibility_date` Secara Eksplisit**: Selalu kunci tanggal kompatibilitas di `wrangler.toml` (contoh: `compatibility_date = "2024-04-01"`) agar pembaruan runtime internal Cloudflare tidak merusak fungsi yang sudah berjalan di production.
- **Validasi Fail-Open vs Fail-Closed**: Ketika Worker middleware Anda memvalidasi authorization atau rate-limiting, putuskan arsitekturnya: jika external check timeout, apakah request diizinkan lewat (*fail-open*) atau diblokir total (*fail-closed*) demi postur keamanan.

---

## 17. Troubleshooting

| Gejala Masalah / Error Code | Root Cause (Akar Masalah) | Langkah Remediasi SRE / Dev |
| :--- | :--- | :--- |
| **Error 1101: Worker Threw Exception** | Eksepsi JavaScript unhandled di kode Worker Anda (misal: `TypeError: Cannot read property of undefined`). | Jalankan `npx wrangler tail` untuk streaming real-time production console error logs. Bungkus entrypoint fetch dengan blok `try...catch` defensif. |
| **Error 1027: Worker Exceeded CPU Time Limit** | Komputasi kode JavaScript Worker melebihi jatah CPU (50ms). Sering disebabkan oleh regex ReDoS (catastrophic backtracking) atau JSON parsing payload raksasa. | Optimalkan ekspresi Regular Expression. Hindari parsing array besar secara sinkron. Pindahkan pemrosesan ke background queue atau tingkatkan limit via Workers Paid. |
| **Error 1015: You are being rate limited** | Cloudflare Edge rate limiting bawaan terpicu akibat terlalu banyak subrequest ke target endpoint yang sama dalam durasi singkat. | Gunakan Cloudflare KV / Cache API untuk men-cache respons subrequest di edge, kurangi ketergantungan fetch berulang. |
| **Stream Prematurely Closed / Body already read** | Mencoba membaca body respons (`response.text()`) dua kali, atau response stream ditutup sebelum client selesai membaca. | Gunakan `response.clone()` jika payload perlu dibaca untuk logging dan diteruskan ke client, atau gunakan `TransformStream`. |

---

## 18. Exercise
**Instruksi**: Buatlah Cloudflare Worker yang memanipulasi header keamanan pada setiap response yang datang dari origin backend publik, dan inject script Google Analytics dummy di tag `<head>` menggunakan `HTMLRewriter`.

1. Inisialisasi worker baru dengan nama `security-proxy`:
   ```bash
   npm create cloudflare@latest security-proxy -- --type=hello-world
   ```
2. Modifikasi file `src/index.js` untuk:
   - Mengambil request dari backend `https://httpbin.org/html`.
   - Menggunakan `HTMLRewriter` untuk menambahkan `<meta name="security-scan" content="passed" />` ke dalam tag `<head>`.
   - Menghapus header `Server` yang diekspos oleh origin.
   - Menambahkan header keamanan:
     - `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
     - `X-Content-Type-Options: nosniff`
     - `X-Frame-Options: DENY`
3. Jalankan secara lokal menggunakan `npx wrangler dev` dan uji menggunakan command `curl -I http://localhost:8787` untuk memvalidasi header, serta periksa output HTML via browser.

---

## 19. Challenge
**Deskripsi Skenario**: 
Sebuah portal berita ingin menerapkan strategi A/B testing multi-origin murni di edge tanpa redirect URL (menjaga URL tetap `example.com/breaking-news`).
- Pengguna yang memiliki cookie `bucket=B` dialihkan ke Origin B (`https://origin-b.service.internal`).
- Pengguna tanpa cookie dialokasikan secara deterministik (50% traffic distribution) ke Origin A atau Origin B.
- Nilai penentuan bucket harus disimpan ke dalam cookie `Set-Cookie: bucket=<val>; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax`.
- Worker harus memantau waktu respons origin (latency tracking). Jika salah satu origin mengalami response code 5xx atau latency > 2000ms, Worker harus melakukan fallback transparan ke origin cadangan tanpa menampilkan halaman error ke pengunjung.
- Body response HTML dari variant manapun harus di-stream dan disuntikkan badge debug di bagian bawah halaman (`<div id="edge-debug">Variant: B | Latency: 42ms</div>`).

**Target Evaluasi**: Kode harus bebas dari memory buffering (gunakan streaming `HTMLRewriter`), menangani error handling multi-layer, dan menjamin zero-downtime origin failover di edge.

---

## 20. Summary
- **Arsitektur V8 Isolates** menyingkirkan lapisan berat virtualisasi OS dan kontainer, menghasilkan *cold start* mendekati nol (<5ms) dan konsumsi memori terendah per instance, memposisikan komputasi tepat di edge jalur Anycast jaringan Cloudflare.
- **Wrangler CLI** bersama runtime `workerd` menyediakan siklus *inner-loop* development yang presisi antara lingkungan local simulation dan eksekusi cloud global.
- **Web Streams API** memfasilitasi arsitektur backpressure-aware pipeline, memungkinkan data diteruskan chunk-by-chunk tanpa latensi buffer.
- **`HTMLRewriter`** memberikan solusi streaming DOM parsing yang sangat efisien (*zero full-DOM parsing overhead*), memungkinkan personalisasi konten dinamis pada edge cache.
- **Cloudflare Pages & Functions** menggabungkan kemudahan deployment asset frontend dengan kekuatan komputasi serverless edge berbasis file routing.
- **Edge Middleware** mengabstraksi fungsionalitas transversal sistem—seperti security validation, geo-routing, header injection, dan origin proxying—sebelum request menyentuh infrastruktur core backend.