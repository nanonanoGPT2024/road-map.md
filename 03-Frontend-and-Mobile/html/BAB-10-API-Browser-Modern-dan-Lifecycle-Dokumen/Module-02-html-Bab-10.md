# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Bab 10: API Browser Modern & Lifecycle Dokumen
### Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis dan Membedah Siklus Hidup Dokumen (Document Lifecycle API)**: Menguasai transisi status dokumen tingkat rendah (`loading`, `interactive`, `complete`) serta state engine WICG (*Active*, *Passive*, *Hidden*, *Frozen*, *Terminated*, *Discarded*) pada Chromium/WebKit.
2. **Mengeliminasi Degradasi Performa & Regresi Bfcache**: Merancang arsitektur aplikasi tanpa `unload` event listener yang merusak *Back-Forward Cache* (bfcache), mengoptimalkan parameter `persisted` pada `pageshow`/`pagehide`.
3. **Membangun Telemetri & Sinkronisasi State Nir-Gagal**: Mengimplementasikan *guaranteed data flushing* menggunakan `navigator.sendBeacon()` dan `fetch()` dengan flag `keepalive: true` saat dokumen memasuki state `hidden` atau `frozen`.
4. **Menerapkan Observer APIs Berkinerja Tinggi**: Mengintegrasikan `IntersectionObserver`, `ResizeObserver`, dan `MutationObserver` dalam arsitektur rendering tanpa memicu layout thrashing (*forced synchronous reflow*).
5. **Mengelola Resource Resilience Terdistribusi**: Mengontrol resource aktif (WebSocket, Web Workers, IndexedDB locks, audio contexts) secara otomatis saat tab mengalami suspend/thaw melalui Page Lifecycle API.

---

### 2. Prerequisite

Sebelum menempuh modul ini, engineer wajib memiliki pemahaman mendalam tentang:
- Arsitektur Event Loop (Task Queue, Microtask Queue, Animation Frame Callbacks).
- Dasar parsing HTML: Tokenizer, Tree Construction, DOM vs CSSOM vs Render Tree.
- Konsep networking modern: Keep-Alive HTTP/2-HTTP/3, HTTP Semantics, CORS.
- JavaScript Asinkron: Promises, Async/Await, AbortController, dan TypedArrays.

---

### 3. Concept & Internal Architecture

#### 3.1 Parser HTML dan Transisi `Document.readyState`

Pada level rendering engine (seperti Blink pada Chromium atau WebKit pada Safari), pemrosesan dokumen HTML dimulai dari streaming byte jaringan:

1. **Byte Stream Decoder**: Mengubah raw bytes menjadi stream of characters berdasarkan header `Content-Type` charset.
2. **Tokenizer**: State machine yang membaca characters dan memancarkan token: `DOCTYPE`, `StartTag`, `EndTag`, `Comment`, `Character`, `EndOfFile`.
3. **Tree Construction**: Memproses token secara sinkron untuk memvalidasi struktur bersarang dan membentuk node DOM.
4. **Pre-parse / Speculative Scanner**: Thread independen yang membaca sisa raw markup untuk mencari referensi eksternal (`<script src>`, `<link rel="stylesheet">`, `<img>`) guna mendispatch request jaringan sedini mungkin secara paralel saat thread utama diblokir oleh eksekusi skrip sinkron.

```
Byte Stream -> Tokenizer -> Tree Construction -> DOM Tree
      |                           |
      +---> Speculative Scanner --+ (Network Requests Pre-flight)
```

Perubahan status dokumen dipetakan melalui properti `document.readyState`:
- **`loading`**: Dokumen masih dalam proses parsing token. Node-node baru terus di-append ke DOM tree.
- **`interactive`**: Parser menyelesaikan seluruh token markup HTML (mencapai token `EndOfFile`), DOM tree telah terbentuk penuh. Seluruh tag `<script defer>` dieksekusi secara berurutan. Engine kemudian mendispatch event `DOMContentLoaded` pada objek `document`.
- **`complete`**: Seluruh resource yang dideklarasikan dalam dokumen (gambar, stylesheet, sub-frames, fonts) selesai di-download dan diproses. Engine kemudian mendispatch event `load` pada objek `window`.

#### 3.2 WICG Page Lifecycle State Machine

Aplikasi web modern berjalan di lingkungan multi-tab dengan alokasi memori dan CPU terbatas. Sistem operasi mobile dan desktop modern tidak lagi mempertahankan seluruh background tabs dalam status komputasi aktif. WICG menetapkan status formal lifecycle dokumen:

```
[ Active ] <====> [ Passive ]
    ^                   |
    |                   v
    +-----------> [ Hidden ]
                        |
                        v
                  [ Frozen ]
                   /      \
                  v        v
            [ Terminated ] [ Discarded ]
```

1. **Active**: Tab berada di latar depan (*foreground*), memiliki focus sistem input, dan sedang me-render frame.
2. **Passive**: Tab berada di latar depan tetapi kehilangan focus input (misalnya: devtools dibuka, dialog sistem aktif). Frame masih di-render.
3. **Hidden**: Tab sepenuhnya tidak terlihat oleh pengguna (background tab, window terminimalkan, atau layar terkunci). Terjadi saat event `visibilitychange` (`document.visibilityState === 'hidden'`) terpicu.
4. **Frozen**: CPU di-suspend oleh engine browser untuk menghemat konsumsi daya. Task queues dihentikan. Timer seperti `setInterval` atau `setTimeout` tidak dijalankan. Memory footprint dipertahankan di RAM.
5. **Terminated**: Dokumen di-unload dan memori dibersihkan dari RAM karena pengguna menutup tab atau bernavigasi keluar.
6. **Discarded**: Tab masih tampak pada tab strip browser, namun alokasi memori process dokumen telah direklamasi (di-kill) oleh operating system karena OOM (Out Of Memory). Ketika pengguna membuka tab kembali, browser memuat ulang URL secara penuh.

#### 3.3 Back-Forward Cache (bfcache) Internals

*bfcache* adalah mekanisme optimasi snapshot in-memory lengkap dari sebuah halaman (termasuk heap JavaScript dan status DOM) saat pengguna bernavigasi ke halaman lain. Ketika pengguna mengklik tombol "Back" atau "Forward", halaman tidak di-download atau di-parse ulang; browser langsung me-restore heap secara instan (0ms rendering latency).

**Kondisi Pemblokir bfcache (Bfcache Eviction Triggers)**:
- Pendaftaran listener `window.addEventListener('unload', ...)`: Keberadaan listener ini secara instan mematikan kapabilitas bfcache di browser modern (Chromium, Firefox, Safari) karena browser berasumsi halaman memiliki logika terminasi non-idempotent.
- Koneksi terbuka yang tidak diputus: Objek `WebSocket`, `WebRTC`, atau active `IndexedDB` transaction yang tertahan.
- Penggunaan `Cache-Control: no-store` pada respon dokumen HTML utama (khususnya implementasi Chromium terdahulu, meski standar modern mulai melonggarkan jika tidak ada data sensitif).
- Lock aktif dari Web Locks API (`navigator.locks`) yang belum dilepas.

---

### 4. Why & What

| Fitur / API | Masalah yang Diselesaikan (Why) | Definisi & Karakteristik (What) |
| :--- | :--- | :--- |
| **Page Lifecycle API** | Background tabs menghabiskan baterai, memori, dan bandwidth; data hilang saat mobile OS menutup browser tiba-tiba. | Standar siklus hidup dokumen lintas platform yang mengekspos event deterministik (`visibilitychange`, `pagehide`, `pageshow`, `freeze`, `resume`). |
| **`visibilitychange`** | Menggantikan event `beforeunload` dan `unload` yang tidak andal pada mobile browser. | Event yang terpicu tepat saat dokumen berpindah status antara visible dan background. Momen paling aman untuk menyimpan state/sinkronisasi. |
| **`navigator.sendBeacon`** | Browser sering membatalkan asynchronous XHR/Fetch reguler saat dokumen di-unload/navigasi. | API pengiriman data HTTP POST asinkron berprioritas rendah yang dijamin selesai dikirim oleh browser engine tanpa menunda proses unload halaman. |
| **Speculation Rules API** | Latensi navigasi terasa lambat pada aplikasi multi-halaman enterprise. | JSON-based declarative API untuk melakukan pre-render atau pre-fetch dokumen HTML secara spekulatif berdasarkan probabilitas klik pengguna. |

---

### 5. How (Workflow Detail)

Alur penanganan lifecycle dokumen dari inisialisasi hingga terminasi:

```
[Network: Bytes Arrival]
           │
           ▼
[HTML Parsing & Tokenization]  ──► readyState: 'loading'
           │
           ▼
[DOM Parsing Selesai]          ──► readyState: 'interactive'
           │                   ──► Event: 'DOMContentLoaded'
           │                       (Execute defer scripts)
           ▼
[Subresources Loaded]          ──► readyState: 'complete'
(Images, CSS, Fonts)           ──► Event: 'load'
           │
           ▼
[User Switches Tab / Minimizes]
           │
           ▼
[Document Becomes Invisible]   ──► Event: 'visibilitychange' (hidden)
           │                       *Flush pending telemetry*
           │                       *Pause animations, media*
           │                       *Save state to localStorage/IndexedDB*
           ▼
[User Navigates Away]          ──► Event: 'pagehide'
                                   *Check event.persisted for bfcache*
                                   *Tear down WebSockets / Locks if persisted=false*
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Hotel dan Tamu
- **Active**: Tamu berada di dalam kamar, lampu menyala, pendingin udara bekerja, interaksi terjadi secara real-time.
- **Passive**: Tamu berada di kamar tetapi sedang menerima telepon interkom; perhatian terpecah, namun operasional kamar tetap berjalan normal.
- **Hidden**: Tamu keluar kamar untuk sarapan, mematikan lampu kamar, tetapi koper dan pakaian masih tertata rapi di dalam lemari.
- **Frozen (bfcache)**: Manajemen hotel menerapkan mode hibernasi: seluruh fasilitas kamar dinonaktifkan, inventaris dibekukan di tempat, biaya kamar dihentikan sementara.
- **Terminated/Discarded**: Tamu checkout permanen; kamar dibersihkan, koper dikeluarkan, memori kamar direset untuk tamu berikutnya.

#### Diagram Transisi State & Event Listener

```
                    ┌──────────────────────────────┐
                    │            ACTIVE            │
                    └──────────────┬───────────────┘
                                   │
               document.addEventListener('visibilitychange')
                        [document.hidden === true]
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │            HIDDEN            │
                    │ (Flush Telemetry via Beacon) │
                    └──────────────┬───────────────┘
                                   │
                    window.addEventListener('pagehide')
                                   │
                    ┌──────────────┴───────────────┐
       [event.persisted === true]     [event.persisted === false]
                    │                              │
                    ▼                              ▼
     ┌────────────────────────────┐  ┌────────────────────────────┐
     │       FROZEN (bfcache)     │  │         TERMINATED         │
     │  document.addEventListener │  │ (Koneksi jaringan diputus, │
     │         ('resume')         │  │   memori dibebaskan total) │
     └──────────────┬─────────────┘  └────────────────────────────┘
                    │
     window.addEventListener('pageshow')
       [event.persisted === true]
                    │
                    ▼
     ┌────────────────────────────┐
     │   RESTORED (Re-sync Data)  │
     └────────────────────────────┘
```

---

### 7. Implementation: Simple & Practical Example

#### 7.1 Simple Example: Safe Lifecycle Hook Registration

Implementasi pendaftaran lifecycle hook yang benar tanpa mematikan bfcache:

```javascript
/**
 * @file safe-lifecycle.js
 * Pendaftaran dasar state observer tanpa menyentuh event 'unload'.
 */

// Tangani perubahan visibilitas
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    console.log('[Lifecycle] Document is now hidden. Pausing background tasks.');
  } else {
    console.log('[Lifecycle] Document is now visible. Resuming rendering.');
  }
});

// Tangani navigasi keluar dengan verifikasi bfcache
window.addEventListener('pagehide', (event) => {
  if (event.persisted) {
    console.log('[Lifecycle] Page is entering bfcache. Keep connection teardown minimal.');
  } else {
    console.log('[Lifecycle] Page is terminating completely. Cleanup all resources.');
  }
});

// Tangani restore dari bfcache
window.addEventListener('pageshow', (event) => {
  if (event.persisted) {
    console.log('[Lifecycle] Restored from bfcache! Re-validating dynamic data via fetch.');
  }
});
```

#### 7.2 Practical Example: Enterprise Session State & Telemetry Orchestrator

Arsitektur produksi untuk mengelola state synchronization, flushing telemetri, penanganan koneksi WebSocket, dan proteksi bfcache:

```typescript
/**
 * @file EnterpriseLifecycleOrchestrator.ts
 * Solusi tangguh untuk sinkronisasi state dan telemetri lifecycle enterprise.
 */

interface TelemetryPayload {
  sessionId: string;
  eventType: string;
  timestamp: number;
  payload: Record<string, unknown>;
}

export class EnterpriseLifecycleOrchestrator {
  private sessionId: string;
  private beaconUrl: string;
  private telemetryQueue: TelemetryPayload[] = [];
  private socket: WebSocket | null = null;
  private isFrozen: boolean = false;

  constructor(sessionId: string, beaconUrl: string, wsUrl: string) {
    this.sessionId = sessionId;
    this.beaconUrl = beaconUrl;
    this.initWebSocket(wsUrl);
    this.registerLifecycleHooks();
  }

  private initWebSocket(wsUrl: string): void {
    this.socket = new WebSocket(wsUrl);
    this.socket.onopen = () => console.log('[Socket] Connected');
    this.socket.onerror = (err) => console.error('[Socket] Error:', err);
  }

  public enqueueEvent(eventType: string, payload: Record<string, unknown>): void {
    this.telemetryQueue.push({
      sessionId: this.sessionId,
      eventType,
      timestamp: Date.now(),
      payload
    });

    if (this.telemetryQueue.length >= 20) {
      this.flushTelemetry();
    }
  }

  /**
   * Menjamin payload telemetri terkirim meskipun tab ditutup seketika.
   */
  public flushTelemetry(): void {
    if (this.telemetryQueue.length === 0) return;

    const dataToSend = JSON.stringify(this.telemetryQueue);
    this.telemetryQueue = [];

    // Prioritas 1: Gunakan sendBeacon
    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const blob = new Blob([dataToSend], { type: 'application/json; charset=UTF-8' });
      const success = navigator.sendBeacon(this.beaconUrl, blob);
      if (success) return;
    }

    // Prioritas 2: Fallback ke fetch dengan keepalive
    try {
      fetch(this.beaconUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: dataToSend,
        keepalive: true, // Mempertahankan koneksi socket HTTP tetap hidup meski tab di-unload
      }).catch((err) => {
        console.error('[Telemetry] Fallback fetch failed:', err);
      });
    } catch (err) {
      console.error('[Telemetry] Failed to dispatch via fetch keepalive:', err);
    }
  }

  private registerLifecycleHooks(): void {
    // 1. Visibility Change: Penyelamat data utama pada platform mobile
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        this.enqueueEvent('PAGE_HIDDEN', { memoryUsage: (performance as any)?.memory?.usedJSHeapSize });
        this.flushTelemetry();
        // Kurangi komputasi: beritahu backend tab ini pasif
      } else {
        this.enqueueEvent('PAGE_VISIBLE', {});
      }
    });

    // 2. Pagehide: Persiapan masuk bfcache atau terminasi total
    window.addEventListener('pagehide', (event: PageTransitionEvent) => {
      this.enqueueEvent('PAGE_HIDE', { persisted: event.persisted });
      this.flushTelemetry();

      if (event.persisted) {
        // Tab akan masuk ke BFCache: TUTUP WebSocket agar tidak membatalkan eligibilitas BFCache
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
          this.socket.close(1000, 'Entering bfcache');
          this.socket = null;
        }
      } else {
        // Tab ditutup permanen
        if (this.socket) {
          this.socket.close(1000, 'Page terminating');
          this.socket = null;
        }
      }
    });

    // 3. Pageshow: Rekonstruksi state jika dipulihkan dari bfcache
    window.addEventListener('pageshow', (event: PageTransitionEvent) => {
      if (event.persisted) {
        console.warn('[Lifecycle] Page restored from BFCache. Reconnecting infrastructure...');
        this.enqueueEvent('BFCACHE_RESTORED', {});
        // Rekoneksi WebSocket yang ditutup pada 'pagehide'
        if (!this.socket || this.socket.readyState === WebSocket.CLOSED) {
          this.initWebSocket('wss://telemetry.enterprise.internal/stream');
        }
      }
    });

    // 4. Freeze & Resume (Chromium Lifecycle API Standard)
    document.addEventListener('freeze', () => {
      this.isFrozen = true;
      this.enqueueEvent('PAGE_FROZEN', {});
      this.flushTelemetry();
    });

    document.addEventListener('resume', () => {
      this.isFrozen = false;
      this.enqueueEvent('PAGE_RESUMED', {});
    });
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Terminal Perdagangan Finansial High-Frequency (Forex & Saham)

**Konteks Masalah**:
Sebuah platform broker enterprise mengalami komplain kritis dari trader institusi:
1. Terjadi data desinkronisasi portofolio saat trader membuka puluhan tab dan berpindah-pindah.
2. Ketika trader meminimalkan browser, konsumsi memori browser membengkak hingga browser crash (OOM Discard).
3. Saat berpindah halaman lalu menekan tombol "Back", terminal melakukan re-rendering penuh selama 4.2 detik alih-alih instan, mengakibatkan hilangnya momentum order.
4. Laporan audit transaksi sering hilang (dropped telemetry) ketika trader menutup laptop secara tiba-tiba.

**Penyebab Arsitektural**:
1. Aplikasi memasang `window.addEventListener('unload', ...)` untuk mematikan auth session token. Ini **secara total menganulir bfcache**.
2. WebSocket dibiarkan terus melakukan update DOM tree internal secara masif meskipun status `document.visibilityState === 'hidden'`, memicu *recalculate style* dan memory bloat di background.
3. Telemetri menggunakan asynchronous `axios.post` tanpa `keepalive: true` saat penutupan dokumen, sehingga browser memutus koneksi TCP sebelum payload terkirim.

**Solusi Arsitektural Terapan**:
1. Menghapus seluruh listener `unload` dan `beforeunload` (kecuali `beforeunload` saat formulir order memiliki status "dirty/unsubmitted").
2. Memodifikasi lifecycle handler:
   - Saat `visibilitychange` menjadi `hidden`: WebSocket dialihkan ke mode throttle (*heartbeat only*, menghentikan pemrosesan orderbook visual). Telemetri di-flush menggunakan `navigator.sendBeacon`.
   - Pada `pagehide`: Menghentikan koneksi WebSocket dengan kode 1000 agar halaman menjadi *eligible* masuk ke bfcache.
   - Pada `pageshow`: Jika `event.persisted === true`, lakukan *fast delta-sync* melalui REST API untuk mengambil transaksi yang terlewat selama tab berada di cache, lalu nyalakan kembali WebSocket.

**Hasil Metrik Produksi**:
- Waktu transisi tombol Back/Forward berkurang dari **4200ms** menjadi **18ms** (99.5% improvement via bfcache).
- Zero Telemetry Loss tercapai pada event terminasi tak terduga.
- Penghematan konsumsi RAM background tab rata-rata sebesar 68%.

---

### 9. Trade-offs

| Pendekatan | Latency Impact | Memory Overhead | Reliability | Development Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **`navigator.sendBeacon`** | Sangat Rendah (Asynchronous & di-queue oleh OS browser). | Minimal (Queue buffer diatur engine, max 64KB). | Sangat Tinggi (Dijamin browser dikirim out-of-process). | Rendah. Payload hanya support string/Blob. |
| **`fetch()` + `keepalive`** | Rendah (Koneksi TCP tetap hidup). | Sedang (Mempertahankan buffer header & state fetch). | Tinggi (Dukungan custom HTTP headers & auth token). | Sedang (Perlu handling quota error `RequestInit.keepalive`). |
| **Bfcache Enabled** | Sangat Rendah (0-50ms instant page loads). | Tinggi (Heap JavaScript, DOM, CSSOM tetap berada di RAM). | Tinggi (Jika state restore ditangani secara tepat). | Sangat Tinggi (Wajib mengisolasi persistent connections). |
| **Aggressive Unload Cleanup** | Tinggi (Memaksa network parsing ulang saat re-visit). | Rendah (RAM langsung dibersihkan seketika). | Rendah (Rawan memicu unhandled rejection saat tab kill). | Rendah. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Menggunakan Event `unload`
* **Gejala**: Navigasi tombol back terasa lambat, metriks LCP melonjak, audit Lighthouse memperingatkan `Deprecation: unload event listener found`.
* **Root Cause**: Engine browser menonaktifkan optimasi bfcache jika ada listener `unload`.
* **Solusi**: Pindahkan seluruh logika cleanup ke `pagehide` dan `visibilitychange`.

```javascript
// BURUK: Merusak bfcache
window.addEventListener('unload', () => {
  cleanup();
});

// BAIK: Mempertahankan bfcache
window.addEventListener('pagehide', (event) => {
  cleanup();
  if (event.persisted) {
    // Persiapan freeze
  }
});
```

#### 2. Layout Thrashing dalam Observer Callbacks
* **Gejala**: FPS anjlok (jank), interaksi drop frame ketika elemen di-observe.
* **Root Cause**: Membaca geometri DOM (`element.offsetHeight`, `getBoundingClientRect()`) segera setelah mengubah style di dalam callback `ResizeObserver` atau `MutationObserver`.
* **Solusi**: Pisahkan tahap pembacaan (read) dan penulisan (write), atau gunakan payload ukuran native yang diberikan oleh observer (`entry.contentRect` / `entry.borderBoxSize`).

```javascript
// BURUK: Memaksa Layout Thrashing
const ro = new ResizeObserver((entries) => {
  for (const entry of entries) {
    // Membaca offsetHeight langsung dari DOM saat mutating
    if (entry.target.offsetHeight > 500) {
      entry.target.classList.add('large'); // Write
    }
  }
});

// BAIK: Gunakan box sizing yang telah dihitung oleh engine
const roClean = new ResizeObserver((entries) => {
  for (const entry of entries) {
    const height = entry.borderBoxSize?.[0]?.blockSize ?? entry.contentRect.height;
    if (height > 500) {
      requestAnimationFrame(() => {
        entry.target.classList.add('large');
      });
    }
  }
});
```

#### 3. Quota Exceeded pada `fetch()` with `keepalive`
* **Gejala**: `TypeError: Failed to fetch` saat mengirim payload di `visibilitychange`.
* **Root Cause**: Browser membatasi total data inflight untuk `keepalive` (standar Chromium/WebKit membatasi hingga 64 KB total concurrently across all keepalive requests).
* **Solusi**: Gumpalkan payload menjadi batasan payload kecil (<30 KB) atau prioritaskan single-flight aggregated JSON payload.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Hapus Seluruh Listener `unload`**: Audit dependency third-party (analytics, monitoring) untuk memastikan tidak ada script yang menginjeksi `window.onunload`.
2. [ ] **Validasi Bfcache di DevTools**: Buka Chrome DevTools -> Application -> Background Services -> Back/forward cache -> Jalankan test run untuk verifikasi *Eligible*.
3. [ ] **Gunakan `visibilitychange` sebagai Titik Telemetri Utama**: Jangan pernah mengandalkan event `beforeunload` pada iOS/Android browser.
4. [ ] **Putus Persistent Handles pada `pagehide`**: Putus koneksi Web Locks, WebSocket, dan hentikan IndexedDB manual transactions jika `event.persisted === true`.
5. [ ] **Re-sync Data pada `pageshow`**: Selalu periksa `event.persisted`; jika `true`, lakukan invalidasi query data (misal: panggil cache invalidation TanStack Query atau RTK Query).
6. [ ] **Throttle Background Computing**: Jika `document.visibilityState === 'hidden'`, hentikan request animasi non-kritis dan turunkan interval polling telemetry.
7. [ ] **Batas Ukuran Payload Beacon**: Pastikan payload `navigator.sendBeacon` atau `fetch keepalive` berada di bawah ambang batas aman (maksimum 60 KB).

---

### 12. Hands-on Practice

Struktur direktori praktikum yang harus dibangun:
```
hands-on/m02/
├── index.html
├── server.js
└── src/
    └── orchestrator.js
```

#### Langkah 1: Siapkan Server Ingestion Mock (`server.js`)
Buat script backend Node.js untuk menangani data beacon dan logging bfcache lifecycle:

```javascript
// hands-on/m02/server.js
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3000;

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/api/telemetry') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      console.log('\x1b[32m%s\x1b[0m', `[Server Telemetry Received] at ${new Date().toISOString()}`);
      console.log(JSON.parse(body));
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ACK' }));
    });
    return;
  }

  // Static File Serving
  let filePath = req.url === '/' ? '/index.html' : req.url;
  const absPath = path.join(__dirname, filePath);
  
  if (fs.existsSync(absPath)) {
    const ext = path.extname(absPath);
    let contentType = 'text/html';
    if (ext === '.js') contentType = 'application/javascript';

    res.writeHead(200, { 'Content-Type': contentType });
    fs.createReadStream(absPath).pipe(res);
  } else {
    res.writeHead(404);
    res.end('Not Found');
  }
});

server.listen(PORT, () => {
  console.log(`Enterprise Lab Server running at http://localhost:${PORT}`);
});
```

#### Langkah 2: Buat Modul Orchestrator Client (`src/orchestrator.js`)

```javascript
// hands-on/m02/src/orchestrator.js
export class ResilientLifecycleClient {
  constructor(endpoint) {
    this.endpoint = endpoint;
    this.metricsBuffer = [];
    this.init();
  }

  init() {
    console.log(`[Engine] Initial ReadyState: ${document.readyState}`);

    document.addEventListener('readystatechange', () => {
      console.log(`[Engine] ReadyState Transition: ${document.readyState}`);
      this.record('READY_STATE_CHANGE', { state: document.readyState });
    });

    document.addEventListener('DOMContentLoaded', () => {
      console.log('[Engine] Event DOMContentLoaded fired');
      this.record('DOM_CONTENT_LOADED', {});
    });

    window.addEventListener('load', () => {
      console.log('[Engine] Event load fired');
      this.record('WINDOW_LOADED', {});
    });

    document.addEventListener('visibilitychange', () => {
      console.log(`[Engine] Visibility State: ${document.visibilityState}`);
      this.record('VISIBILITY_CHANGE', { state: document.visibilityState });
      if (document.visibilityState === 'hidden') {
        this.flush();
      }
    });

    window.addEventListener('pagehide', (e) => {
      console.log(`[Engine] Pagehide fired! Persisted (BFCache): ${e.persisted}`);
      this.record('PAGE_HIDE', { persisted: e.persisted });
      this.flush();
    });

    window.addEventListener('pageshow', (e) => {
      console.log(`[Engine] Pageshow fired! Restored from BFCache: ${e.persisted}`);
      this.record('PAGE_SHOW', { persisted: e.persisted });
    });
  }

  record(event, data) {
    this.metricsBuffer.push({
      event,
      data,
      timestamp: performance.now(),
      epoch: Date.now()
    });
  }

  flush() {
    if (this.metricsBuffer.length === 0) return;

    const payload = JSON.stringify(this.metricsBuffer);
    this.metricsBuffer = [];

    if (navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' });
      const sent = navigator.sendBeacon(this.endpoint, blob);
      if (sent) {
        console.log('[Telemetry] Dispatched via sendBeacon');
        return;
      }
    }

    fetch(this.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
      keepalive: true
    }).then(() => {
      console.log('[Telemetry] Dispatched via Fetch keepalive');
    }).catch(err => {
      console.error('[Telemetry] Fallback Failed', err);
    });
  }
}
```

#### Langkah 3: Implementasi Dokumen Antarmuka (`index.html`)

```html
<!DOCTYPE html>
<!-- hands-on/m02/index.html -->
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Enterprise Document Lifecycle Testing Harness</title>
  <style>
    body { font-family: monospace; padding: 2rem; background: #0f172a; color: #f8fafc; }
    .card { background: #1e293b; padding: 1.5rem; border-radius: 8px; border: 1px solid #334155; }
    .btn { background: #3b82f6; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; }
    .btn:hover { background: #2563eb; }
    #log { margin-top: 1rem; height: 200px; overflow-y: scroll; background: #020617; padding: 1rem; }
  </style>
  <script type="module">
    import { ResilientLifecycleClient } from './src/orchestrator.js';
    window.client = new ResilientLifecycleClient('/api/telemetry');
  </script>
</head>
<body>
  <div class="card">
    <h1>Document Lifecycle Deep Dive Lab</h1>
    <p>Buka DevTools Console & Server Terminal untuk mengamati observasi event.</p>
    <button class="btn" onclick="triggerAction()">Simulasi Mutasi State & Log</button>
    <a href="https://example.com" class="btn" style="text-decoration:none; display:inline-block;">Buka Eksternal Link (Uji BFCache)</a>
    <div id="log"></div>
  </div>

  <script>
    function triggerAction() {
      const msg = `Custom action at ${new Date().toLocaleTimeString()}`;
      window.client.record('USER_ACTION', { action: 'BUTTON_CLICK' });
      const logEl = document.getElementById('log');
      logEl.innerHTML += `<div>${msg}</div>`;
    }
  </script>
</body>
</html>
```

#### Langkah 4: Menjalankan dan Menguji
1. Jalankan server: `node server.js`.
2. Buka browser Chromium di `http://localhost:3000`.
3. Buka tab baru, lalu kembali ke tab lama. Periksa console log server: payload `VISIBILITY_CHANGE: hidden` dikirim secara instan.
4. Klik tautan eksternal, kemudian klik tombol "Back". Amati apakah event `pageshow` melaporkan `persisted: true`.

---

### 13. Exercise

#### Level Easy
1. **Identifikasi Status**: Modifikasi `index.html` untuk menampilkan badge visual di pojok kanan atas yang merefleksikan perubahan `document.visibilityState` (`VISIBLE` warna hijau, `HIDDEN` warna merah).
2. **Kriteria Selesai**: Badge terupdate seketika saat window diminimalkan atau tab dipindah tanpa menyebabkan error di console.

#### Level Medium
1. **IntersectionObserver Auto-Pause**: Buat implementasi HTML custom element `<monitored-video>` yang memutar video HTML5 hanya jika rasio perjumpaan viewport (intersection ratio) minimal `0.75` (75%), dan otomatis mem-pause pemutaran jika dokumen masuk ke state `visibilitychange === 'hidden'`.
2. **Kriteria Selesai**: Resource audio/video tidak boleh memproses frame atau decoding audio sama sekali saat tab berada di background.

#### Level Hard
1. **Distributed Mutex Lock Manager**: Bangun mekanisme koordinasi multi-tab menggunakan Web Locks API (`navigator.locks`) dan BroadcastChannel. Jika tab utama (leader) di-freeze oleh browser OS atau dimasukkan ke dalam bfcache, kepemimpinan (leader lock) harus secara instan dialihkan ke tab cadangan (replica) dalam durasi < 150ms tanpa race condition.
2. **Kriteria Selesai**: Tidak terjadi deadlock saat tab leader dihentikan secara paksa via Chrome Task Manager (`SIGKILL`).

---

### 14. Challenge

**Skenario**: Arsitektur Kolaboratif Real-Time Canvas dengan Suspensi Multi-Tenant.

Anda adalah Principal Frontend Engineer pada platform desain kolaboratif enterprise (seperti Figma). Pengguna sering membuka puluhan tab proyek berskala gigabyte.
- **Tantangan**:
  1. Saat dokumen berada di background (`hidden`) lebih dari 60 detik, alokasi memori WebGL Canvas dan OffscreenCanvas harus didereferensikan tanpa menghapus riwayat Undo/Redo di IndexedDB.
  2. Ketika pengguna kembali ke tab (`pageshow` atau `visibilitychange: visible`), aplikasi harus merekonstruksi grafis kanvas dari snapshot IndexedDB tanpa blocking Main Thread lebih dari 50ms (INP safe).
  3. Dokumen harus 100% *eligible* untuk Chromium bfcache. Navigasi bolak-balik antara dashboard dan workspace canvas tidak boleh memicu rendering ulang dari network.
  4. Rancang dokumen arsitektur dan modular code skeleton yang menangani: State Snapshotting, Worker Freezing, Resource Rehydration, dan Unload Prevention.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Soal)
1. **Kapan tepatnya event `DOMContentLoaded` dipancarkan oleh browser engine?**
   - A. Setelah seluruh CSS, gambar, dan subframes selesai dimuat.
   - B. Tepat saat token markup HTML selesai di-parse dan deferred scripts telah dieksekusi, tanpa menunggu gambar/stylesheet selesai dimuat.
   - C. Sebelum eksekusi tag `<script>` sinkron dimulai.
   - D. Hanya saat aplikasi dipulihkan dari Back-Forward cache.
   *Jawaban*: B.

2. **Properti `document.readyState` bernilai `'interactive'` menandakan apa?**
   - A. Dokumen sedang mengunduh payload HTML.
   - B. File HTML selesai di-parse menjadi DOM Tree, namun resource eksternal masih dapat berjalan.
   - C. Browser telah mengeksekusi event `window.onload`.
   - D. Halaman siap masuk ke mode bfcache.
   *Jawaban*: B.

3. **Event manakah yang paling andal untuk menyimpan status aplikasi pada browser modern di perangkat mobile?**
   - A. `unload`
   - B. `beforeunload`
   - C. `visibilitychange`
   - D. `destroy`
   *Jawaban*: C.

4. **Berapakah limitasi buffer data standar untuk API `navigator.sendBeacon()` di mayoritas engine browser?**
   - A. Tidak terbatas
   - B. 64 Kilobytes
   - C. 10 Megabytes
   - D. 2 Megabytes
   *Jawaban*: B.

5. **Apa indikasi utama bahwa sebuah halaman web dipulihkan dari bfcache saat event `pageshow` terpanggil?**
   - A. `document.referrer` bernilai string kosong.
   - B. `event.persisted === true`
   - C. `performance.navigation.type === 2`
   - D. `document.readyState === 'loading'`
   *Jawaban*: B.

#### Intermediate Level (5 Soal)
6. **Mengapa menempatkan listener kosong `window.addEventListener('unload', () => {})` dianggap anti-pattern kritis di arsitektur web modern?**
   - A. Memicu memory leak pada garbage collection V8.
   - B. Mencegah browser engine menyertakan dokumen tersebut ke dalam Back-Forward Cache (bfcache).
   - C. Menyebabkan request synchronous XHR gagal secara otomatis.
   - D. Menunda event `DOMContentLoaded` sebanyak 500ms.
   *Jawaban*: B.

7. **Bagaimana urutan transisi siklus hidup yang benar saat pengguna berpindah dari Tab A ke Tab B di window yang sama?**
   - A. Tab A `pagehide` -> Tab A `visibilitychange` (hidden) -> Tab B `visibilitychange` (visible).
   - B. Tab A `visibilitychange` (hidden) -> Tab A `freeze` -> Tab B `visibilitychange` (visible).
   - C. Tab A `visibilitychange` (hidden) -> Tab B `visibilitychange` (visible) -> Tab A `freeze`.
   - D. Tab A `beforeunload` -> Tab B `load`.
   *Jawaban*: C.

8. **Apa perbedaan teknis mendasar antara `fetch()` dengan flag `{ keepalive: true }` dan `navigator.sendBeacon()`?**
   - A. `sendBeacon` hanya mendukung GET, sedangkan `fetch` mendukung POST.
   - B. `fetch` dengan `keepalive` memungkinkan kustomisasi HTTP methods, headers, dan CORS mode; sedangkan `sendBeacon` terbatas pada HTTP POST dengan batasan header tertentu.
   - C. `sendBeacon` memblokir rendering UI thread saat unload, sedangkan `fetch` tidak.
   - D. Tidak ada perbedaan; keduanya menggunakan C++ class binding yang sama tanpa batasan kuota.
   *Jawaban*: B.

9. **Jika sebuah dokumen memiliki koneksi WebSocket aktif yang sedang mendengarkan pesan, apa yang terjadi pada eligibilitas bfcache Chromium saat pengguna berpindah halaman?**
   - A. Browser membiarkan koneksi tetap tersambung di background tanpa batas waktu.
   - B. Browser langsung membuang halaman dari bfcache (*eviction*) kecuali koneksi ditutup secara eksplisit sebelum atau saat event `pagehide`.
   - C. Browser secara otomatis meng-hibernate koneksi TCP WebSocket dan melanjutkannya saat `pageshow`.
   - D. Engine membatalkan navigasi pengguna dan memunculkan error modal.
   *Jawaban*: B.

10. **Kapan `ResizeObserver` memicu error `"ResizeObserver loop completed with undelivered notifications"`?**
    - A. Ketika memori browser habis (OOM).
    - B. Ketika modifikasi layout di dalam callback ResizeObserver memicu perubahan ukuran elemen lain yang posisinya lebih dalam/luar secara berulang dalam frame rendering siklus yang sama.
    - C. Ketika elemen yang di-observe memiliki properti `display: none`.
    - D. Ketika callback membutuhkan durasi eksekusi lebih dari 16.6ms.
    *Jawaban*: B.

#### Scenario-based Production Questions (3 Soal)

11. **Skenario 1**: Aplikasi Single Page Application (SPA) Enterprise berbasis e-Commerce melaporkan bahwa 15% transaksi checkout pembayaran ganda (double-charge) terjadi ketika pengguna di mobile menekan tombol "Back" lalu mengklik tombol "Bayar" lagi. Setelah diteliti, halaman checkout ter-restore secara instan dari bfcache dengan tombol bayar yang masih aktif.
    *Pertanyaan*: Apa perbaikan arsitektural yang paling tepat pada event lifecycle untuk menyelesaikan masalah ini?
    - A. Tambahkan `window.addEventListener('unload', () => location.reload())` untuk mematikan bfcache secara permanen.
    - B. Pada listener `pageshow`, periksa properti `event.persisted`. Jika bernilai `true`, lakukan verifikasi status pesanan secara asinkron ke server; jika pesanan telah terproses, lakukan navigasi paksa (`location.replace`) ke halaman tanda terima sukses atau render state *paid*.
    - C. Gunakan `beforeunload` untuk menampilkan native dialog browser meminta pengguna tidak menekan tombol back.
    - D. Simpan status di `sessionStorage` dan hapus total token otentikasi saat `pagehide`.
    *Jawaban*: B. *Alasan*: Mematikan bfcache menurunkan metrik performa secara signifikan. Solusi yang benar adalah memvalidasi status idempotensi transaksi pada `pageshow` jika `event.persisted` bernilai true.

12. **Skenario 2**: Sistem telemetri analitik enterprise mencatat bahwa data durasi waktu tinggal di halaman (*Time Spent on Page*) pada perangkat iOS Safari selalu bernilai jauh lebih kecil daripada durasi nyata ketika pengguna menutup Safari dengan menggeser app switcher ke atas (force close).
    *Pertanyaan*: Di mana letak kegagalan implementasi penangkapan metrik lifecycle tersebut?
    - A. Analitik menghitung kalkulasi durasi pada event `beforeunload`, yang sama sekali tidak dipancarkan oleh OS iOS saat aplikasi di-kill atau di-minimize via home gesture.
    - B. iOS Safari memblokir semua request jaringan yang dibuat menggunakan `navigator.sendBeacon`.
    - C. Browser Safari memerlukan sertifikat SSL custom agar event `pagehide` berfungsi.
    - D. Perhitungan durasi seharusnya dilakukan di dalam Web Worker menggunakan `Atomics.wait()`.
    *Jawaban*: A. *Alasan*: iOS Safari dan mobile Chromium secara rutin mematikan proses web view di background tanpa memicu event `beforeunload` atau `unload`. Perhitungan dan penyimpanan delta waktu harus selalu dikaitkan pada event `visibilitychange`.

13. **Skenario 3**: Sebuah aplikasi analitik monitoring server memantau ratusan log server secara streaming. Aplikasi mengeluhkan pemakaian memori yang melonjak dari 100MB menjadi 2GB setelah tab dibiarkan terminimalkan selama 4 jam di background.
    *Pertanyaan*: Mengapa garbage collection engine V8 tidak membersihkan memori tersebut dan bagaimana strategi perbaikan siklus hidupnya?
    - A. V8 dimatikan saat tab terminimalkan sehingga garbage collection tidak pernah dijalankan sama sekali.
    - B. Event listener WebSocket/Stream tetap menerima data dan melakukan manipulasi array in-memory atau membuat DOM nodes baru di memory pool tanpa memedulikan status visibilitas dokumen. Perbaikannya: Dengarkan `visibilitychange`, hentikan konsumsi stream atau buffer pesan ke IndexedDB lokal saat dokumen berstatus `hidden`.
    - C. Browser otomatis mengalokasikan virtual memory swap saat dokumen terminimalkan.
    - D. Engine CSSOM menahan seluruh tree mutation sampai dokumen dibuka kembali.
    *Jawaban*: B. *Alasan*: Saat hidden, skrip JavaScript tetap dapat berjalan (meski timer di-throttle). Jika koneksi data stream terus memompa data ke dalam array JavaScript tanpa dibersihkan, V8 Heap akan membesar hingga batas OOM. Solusinya adalah memutus atau men-throttle data stream saat `document.visibilityState === 'hidden'`.

---

### 16. Summary

1. **State Machine Parsing Dokumen**: Alur pembacaan HTML parser bertransformasi secara linier dari `loading` -> `interactive` (`DOMContentLoaded`) -> `complete` (`load`). Intervensi arsitektur harus memprioritaskan pembebasan thread utama sebelum fase `interactive`.
2. **Kematian Event `unload`**: Event `unload` adalah anti-pattern usang yang menghancurkan arsitektur *Back-Forward Cache (bfcache)*. Seluruh logika cleanup modern harus berpusat secara mutlak pada kombinasi event `visibilitychange` dan `pagehide`.
3. **Determinisme State Transisi**:
   - `visibilitychange`: Titik teraman untuk menyimpan state, menulis ke penyimpanan lokal (IndexedDB/CacheStorage), dan mengirim analitik via `navigator.sendBeacon` atau `fetch(url, { keepalive: true })`.
   - `pagehide`: Gerbang evaluasi status persistensi (`event.persisted`) guna memutus koneksi persisten (WebSocket, Web Locks) agar halaman siap disimpan di memori snapshot bfcache.
   - `pageshow`: Titik rekonstruksi infrastruktur dinamis dan validasi integritas data pasca-hibernasi.
4. **Optimasi Resource Resiliency**: Tab modern bersifat fana (*ephemeral*). Browser OS memiliki hak penuh untuk melakukan transisi status dari *Active* ke *Passive*, *Hidden*, *Frozen*, hingga *Discarded*. Perangkat lunak enterprise kelas produksi harus didesain dengan asumsi tab dapat dihentikan kapan saja tanpa notifikasi terminal langsung. Telemetri harus dikirim secara inkremental, dan state aplikasi harus selalu dapat dipulihkan secara instan dari level storage lokal.