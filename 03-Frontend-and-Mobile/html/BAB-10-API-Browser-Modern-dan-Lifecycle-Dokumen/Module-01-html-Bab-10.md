# BAB 10: API BROWSER MODERN & LIFECYCLE DOKUMEN

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** `03-Frontend-and-Mobile`
*   **Mata Pelajaran:** HTML & Web Runtime Engineering
*   **Bab:** 10 — Integrasi Platform Web Tingkat Lanjut
*   **Modul:** 01 — API Browser Modern & Lifecycle Dokumen
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Pemahaman mendalam tentang DOM Tree, Event Loop (Microtask/Macrotask), JavaScript Concurrency Model, Execution Context, dan Alur Parsing Dokumen HTML.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:

1.  Menganalisis dan membedah transisi state internal dokumen HTML dalam Web Hypertext Application Technology Working Group (WHATWG) dan W3C Page Lifecycle API specification (`loading`, `interactive`, `complete`, `passive`, `hidden`, `frozen`, `terminated`).
2.  Mengeliminasi Layout Thrashing dan *forced synchronous layout* dengan memanfaatkan asynchronous DOM observation via `IntersectionObserver`, `ResizeObserver`, dan `MutationObserver`.
3.  Merancang dan mengimplementasikan arsitektur pengiriman telemetri analitik web enterprise yang tangguh tanpa memblokir unmount/unload thread menggunakan `navigator.sendBeacon` dan Fetch API dengan flag `keepalive`.
4.  Mengelola retensi memori dan siklus hidup event listener secara deterministik dengan memanfaatkan antarmuka `AbortController` dan `AbortSignal`.
5.  Mengintegrasikan sistem pemantauan performa real-time dan isolasi thread latar belakang guna mencegah penurunan metrik Core Web Vitals (INP, LCP, CLS).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa web modern, halaman web bukan sekadar dokumen pasif yang diurai secara linier dari atas ke bawah, melainkan sebuah **state machine asinkron yang berjalan di atas sistem operasi multi-proses**.

```
[ Mental Model Konvensional ]
HTML Diterima -> Parse DOM -> Muat JS/CSS -> Selesai (Window Load) -> Pengguna Menutup Tab

[ Mental Model Modern Web Runtime Engine ]
Input Stream -> Tokenization -> Incremental DOM Parsing -> Layout Tree Construction
       │
       ├──> Lifecycle State Transitions (Passive <-> Hidden <-> Frozen)
       │
       └──> Autonomous Native Observers (Intersection / Resize / Mutation)
              └──> Offloading work from Main Thread Event Loop
```

Sebagai seorang engineer sistem frontend, Anda harus memandang browser (Chromium Blink, Gecko, WebKit) sebagai ekosistem komputasi dengan sumber daya terbatas (CPU cycle, GPU rasterization, memory bus). 

Pemanggilan API sinkron tradisional seperti `window.onscroll`, `window.onresize`, atau polling properti layout geometri (`element.getBoundingClientRect()`, `element.offsetHeight`) memaksa rendering engine melakukan siklus **Reflow-Repaint** di luar frame timing natural (60Hz/120Hz).

Mental model yang benar mengalihkan paradigma dari *polling-and-measure* ke *reactive-contract-subscription*. Kita mendelegasikan pemantauan geometri dan mutasi struktur langsung ke level engine internal browser menggunakan Observers API, mengisolasi pembacaan/penulisan ke dalam scheduled tasks, serta menghormati siklus hidup tab agar tidak menghabiskan baterai dan memori pengguna saat status halaman tidak aktif.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram arsitektur alur dokumen web modern yang mencakup transisi dari bootstrapping awal, observasi DOM non-blocking, hingga transisi status dokumen pada Page Lifecycle API:

```
[NETWORK INGESTION]
        │
        ▼ (Raw HTML Bytes)
[HTMLParser] ─────────────────────────────────────────────────────────────┐
        │                                                                 │
        ├─► [DOMContentLoaded Event] (DOM ready, async/defer scripts run) │
        │                                                                 │
        ▼                                                                 │
[Rendering Engine (Recalc Style -> Layout -> Paint -> Composite)]         │
        │                                                                 │
        ▼                                                                 │
[window.load Event] (Sub-resources / CSS / Images Loaded)                 │
        │                                                                 │
        ├─────────────────────────────────────────────────────────────────┘
        │
        ▼
╔══════════════════════════════════════════════════════════════════════════════════╗
║                          ACTIVE / RUNNING APPLICATION                            ║
║                                                                                  ║
║   ┌──────────────────────┐  ┌─────────────────────┐  ┌───────────────────────┐   ║
║   │ IntersectionObserver │  │   ResizeObserver    │  │   MutationObserver    │   ║
║   └──────────┬───────────┘  └──────────┬──────────┘  └──────────┬────────────┘   ║
║              │                         │                        │                ║
║              └─────────────────────────┼────────────────────────┘                ║
║                                        ▼                                         ║
║                          [Microtask Queue / Frame Queue]                         ║
║                                        │                                         ║
║                                        ▼                                         ║
║                               [Main Thread Event Loop]                           ║
╚══════════════════════════════════════════════════════════════════════════════════╝
        │
        │ (Tab switch / Minimize window / Backgrounded)
        ▼
┌──────────────────┐
│ visibilitychange │ ──► [document.visibilityState === 'hidden']
└─────────┬────────┘
          │
          │ (OS membebaskan resource / Browser membekukan tab)
          ▼
┌──────────────────┐
│    pagehide      │ ──► [PAGE FROZEN / BFCache]
└─────────┬────────┘
          │
          │ (User membunuh proses / tab ditutup permanen)
          ▼
┌──────────────────┐
│  TERMINATION     │ ──► [navigator.sendBeacon() / fetch(..., { keepalive: true })]
└──────────────────┘     (Last telemetry payload flush - NO SYNC XHR ALLOWED)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Parsing & Document Lifecycle Internals
*   **`document.readyState` Transitions:**
    *   `loading`: Browser masih mengurai dokumen HTML utama.
    *   `interactive`: Parser selesai membangun DOM tree. Sub-resource (gambar, stylesheet) mungkin masih berjalan. Skrip dengan atribut `defer` dieksekusi pada batas ini.
    *   `complete`: Semua sub-resource selesai diunduh. Event `window.load` ditembakkan.
*   **The Page Lifecycle API:**
    Didefinisikan oleh W3C untuk menstandarisasi status aplikasi web di platform modern:
    *   *Active*: Halaman memiliki fokus dan terlihat.
    *   *Passive*: Halaman terlihat tetapi tidak memiliki fokus (misalnya, layar split).
    *   *Hidden*: Halaman tidak terlihat sama sekali (berada di tab latar belakang, terminimalisasi). Event `visibilitychange` ditembakkan di sini.
    *   *Frozen*: Engine menangguhkan eksekusi CPU pada task queue/timer untuk menghemat daya. Memori tetap dipertahankan.
    *   *Discarded*: Tab ditutup dari memori oleh OS/Browser tanpa membunuh entri history navigation.
    *   *Terminated*: Konteks dokumen dibersihkan dan dibongkar secara permanen.

### 2. Browser Observer Engines
*   **`IntersectionObserver`:** Menggunakan komputasi bounding box terpadu di dalam pipeline compositor engine. Pengecekan intersection dihitung bersamaan dengan kalkulasi lifecycle rendering pipeline (sebelum *Paint* step), menghindari eksekusi berulang di JavaScript main thread.
*   **`ResizeObserver`:** Mendeteksi perubahan ukuran pada box model (Content Box, Border Box, Device Pixel Content Box). Engine menjalankan loop internal: jika perubahan ukuran memicu layout baru pada iterasi yang sama, engine membatasi iterasi untuk mencegah kondisi rekursif tak terbatas (*ResizeObserver loop completed with undelivered notifications*).
*   **`MutationObserver`:** Menggunakan *microtask queue*. Ketika mutasi DOM terjadi (`appendChild`, `removeAttribute`), node mutasi dicatat secara internal. Eksekusi callback ditunda sampai eksekusi sinkronik skrip saat ini tuntas, tepat sebelum giliran macrotask berikutnya atau render layout berikutnya.

### 3. Asynchronous Data Ingestion via `keepalive` & `sendBeacon`
Ketika tab berpindah ke status `hidden` atau `terminated`, main thread JavaScript dibatalkan segera.
*   Metode lama: Memanggil sinkronik `XMLHttpRequest` pada event `unload`. Ini memblokir thread proses UI browser dan sangat dilarang oleh spesifikasi modern.
*   Mekanisme Modern: `navigator.sendBeacon()` dan `fetch(url, { keepalive: true })` mendelegasikan array buffer atau payload transmisi ke level network stack browser secara langsung. Browser bertanggung jawab menyelesaikan koneksi HTTP POST di background out-of-process, lepas dari lifecycle thread dokumen yang sedang hancur.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Batasan Kritis Pipeline Rendering: Reflow vs Asynchronous Observation
Ketika kode JavaScript membaca properti layout (seperti `offsetWidth`, `scrollTop`, `getComputedStyle()`), browser engine terpaksa mengeksekusi *Forced Synchronous Layout (FSL)*. Jika properti ditulis lalu dibaca berulang-ulang di dalam satu frame loop, terjadi **Layout Thrashing**:

$$Latency_{frame} = \sum_{i=1}^{n} (T_{recalcStyle} + T_{reflow}) \gg 16.67\text{ ms}$$

```
[ Normal Frame Cycle ]
JS -> Style -> Layout -> Paint -> Composite

[ Forced Synchronous Layout / Thrashing ]
JS -> Write Style -> Read Style (FORCED LAYOUT!) -> Write Style -> Read Style (FORCED LAYOUT!) ...
```

Observer API menyelesaikan problem struktural ini:
1.  **Intersection Observer** memindahkan beban evaluasi geometri ke fase post-layout, mendistribusikan notifikasi via microtasks atau frame queue.
2.  **Resize Observer** menghitung metrik dimensi secara deterministik di level frame rendering loop, mencegah FSL jika developer memodifikasi dimensi elemen di respons callback.
3.  **Mutation Observer** menggantikan pendekatan lama *Mutation Events* (yang bersifat sinkronik dan menimbulkan overhead $O(n^2)$ pada traversal pohon DOM dalam setiap manipulasi node).

### Lifecycle Termination: Mengapa `unload` dan `beforeunload` Berbahaya
Penggunaan event listener `window.addEventListener('unload', ...)` secara eksplisit mematikan fitur **Back-Forward Cache (BFCache)** di browser modern berbasis Blink dan WebKit. BFCache menyimpan *in-memory snapshot* dari seluruh eksekusi halaman web saat pengguna berpindah navigasi, memungkinkan rendering seketika (0 milidetik) saat tombol *Back* ditekan.

Jika terdapat handler `unload`, browser berasumsi halaman memiliki cleanup manual yang tidak kompatibel dengan pemulihan snapshot memori, mendegradasi metrik Core Web Vitals (khususnya Time to Interactive dan Largest Contentful Paint pada navigasi historis).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi clean slate yang mendemonstrasikan integrasi Native Browser Observers, Lifecycle Monitoring, dan Event Listener Abort Logic secara deterministik:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Arsitektur Browser Observers & Lifecycle</title>
  <style>
    .viewport-box {
      width: 100%;
      height: 250px;
      overflow-y: scroll;
      border: 2px solid #334155;
    }
    .spacer {
      height: 600px;
      background: repeating-linear-gradient(45deg, #f1f5f9, #f1f5f9 10px, #e2e8f0 10px, #e2e8f0 20px);
    }
    .target-box {
      padding: 16px;
      margin: 20px;
      background-color: #0284c7;
      color: #ffffff;
      border-radius: 8px;
      transition: background-color 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .target-box.intersecting {
      background-color: #16a34a;
    }
  </style>
</head>
<body>

  <h1>Browser Observer Engine Baseline</h1>
  <div class="viewport-box" id="scrollRoot">
    <div class="spacer">Scroll ke bawah untuk melihat target...</div>
    <div class="target-box" id="observedTarget">Target Pemantauan</div>
    <div class="spacer"></div>
  </div>

  <script>
    // Inisialisasi AbortController untuk manajemen memory & cleanup terpadu
    const globalLifecycleSignal = new AbortController();
    const { signal } = globalLifecycleSignal;

    // 1. INTERSECTION OBSERVER
    const intersectionCallback = (entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('intersecting');
          entry.target.textContent = `Elemen Terlihat! Ratio: ${(entry.intersectionRatio * 100).toFixed(1)}%`;
        } else {
          entry.target.classList.remove('intersecting');
          entry.target.textContent = 'Menunggu Visibility...';
        }
      });
    };

    const intersectionObserver = new IntersectionObserver(intersectionCallback, {
      root: document.getElementById('scrollRoot'),
      rootMargin: '0px',
      threshold: [0, 0.5, 1.0]
    });

    const targetElement = document.getElementById('observedTarget');
    intersectionObserver.observe(targetElement);

    // 2. RESIZE OBSERVER
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const inlineSize = entry.borderBoxSize?.[0]?.inlineSize ?? entry.contentRect.width;
        const blockSize = entry.borderBoxSize?.[0]?.blockSize ?? entry.contentRect.height;
        console.info(`[ResizeObserver] Target Dimensi Baru: ${inlineSize}x${blockSize}px`);
      }
    });

    resizeObserver.observe(targetElement);

    // 3. MUTATION OBSERVER
    const mutationObserver = new MutationObserver((mutationsList) => {
      for (const mutation of mutationsList) {
        if (mutation.type === 'childList') {
          console.info('[MutationObserver] Node anak berubah pada target.');
        } else if (mutation.type === 'attributes') {
          console.info(`[MutationObserver] Atribut ${mutation.attributeName} dimutasi.`);
        }
      }
    });

    mutationObserver.observe(targetElement, {
      attributes: true,
      attributeFilter: ['class'],
      childList: true,
      subtree: false
    });

    // 4. DOCUMENT LIFECYCLE MANAGEMENT DENGAN ABORTSIGNAL
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        console.warn('[Lifecycle] Dokumen masuk status HIDDEN. Mengirim heartbeat via sendBeacon...');
        const payload = JSON.stringify({ event: 'tab_hidden', timestamp: Date.now() });
        navigator.sendBeacon('/api/telemetry', payload);
      } else {
        console.info('[Lifecycle] Dokumen kembali ke status ACTIVE.');
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange, { signal });

    // Global cleanup handler (misal saat SPA route unmount)
    window.teardownApp = () => {
      globalLifecycleSignal.abort();
      intersectionObserver.disconnect();
      resizeObserver.disconnect();
      mutationObserver.disconnect();
      console.warn('[Cleanup] Seluruh Observer dan Listener berhasil didestruksi.');
    };
  </script>
</body>
</html>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 42–43 (`const globalLifecycleSignal = new AbortController(); const { signal } = globalLifecycleSignal;`):** Menginstansiasi abstraksi sinyal pembatalan event terpusat. Menggunakan `signal` pada penambahan event listener menjamin tidak adanya memory leak yang tertinggal saat konteks unmounted tanpa harus melakukan `removeEventListener` satu per satu.
*   **Baris 46–56 (`intersectionCallback = (entries, observer) => { ... }`):** Fungsi callback dieksekusi secara asinkronik setiap kali threshold yang ditentukan terlampaui. Iterator `entries` berisi objek snapshot `IntersectionObserverEntry` dengan parameter waktu, koordinat kalkulasi bounding rect, dan flag boolean `isIntersecting`.
*   **Baris 58–62 (`new IntersectionObserver(..., { root, rootMargin, threshold })`):** Mendefinisikan konfigurasi observer:
    *   `root`: Node kontainer overflow target. Jika `null`, default ke viewport peramban.
    *   `rootMargin`: Margin virtual di sekeliling root, memungkinkan eager pre-fetching sebelum elemen secara visual menabrak batas viewport.
    *   `threshold`: Array nilai persentase visibilitas `[0.0, 0.5, 1.0]` yang memicu penembakan callback engine.
*   **Baris 68–74 (`const resizeObserver = new ResizeObserver(...)`):** Membaca properti `borderBoxSize[0]` (struktur modern standar spesifikasi CSS Box Model) fallback ke `contentRect`. Pengecekan inlineSize/blockSize membaca ukuran logis elemen secara instan tanpa memicu reflow sinkronik.
*   **Baris 80–94 (`const mutationObserver = new MutationObserver(...)`):** Mengawasi mutasi arsitektur node target. Konfigurasi `attributeFilter: ['class']` membatasi pengawasan engine hanya pada mutasi class, secara drastis mengurangi noise observasi dan overhead parsing microtask.
*   **Baris 97–105 (`handleVisibilityChange`):** Menolak ketergantungan pada event usang `unload`. Menggunakan `document.visibilityState` untuk mendeteksi kapan pengguna meminimalisasi browser atau beralih tab, kemudian menembakkan telemetri menggunakan `navigator.sendBeacon()`.
*   **Baris 107 (`document.addEventListener('visibilitychange', ..., { signal })`):** Menghubungkan listener ke `AbortSignal`. Pemanggilan `abort()` nantinya akan secara instan menghapus keterikatan method ini dari memory event registry browser.
*   **Baris 110–116 (`window.teardownApp`):** Pola arsitektur enterprise untuk membersihkan memori (*disposal pattern*). Memanggil `disconnect()` pada setiap instance observer engine untuk melepas semua node pointer dari internal observation registry.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Production Scenario)

### Konteks Bisnis & Masalah
Sebuah platform media berita global berskala jutaan PV/hari (Page Views) mengalami degradasi parah pada metrik Core Web Vitals:
*   **Interaction to Next Paint (INP):** Berada di angka buruk 480ms (kategori *Poor*).
*   **Memory Footprint:** Aplikasi mengalami *crash* pada perangkat mobile entry-level (OOM / Out-of-Memory kills) setelah pengguna membaca 15–20 artikel via infinite scroll.
*   **Drop Telemetry Rate:** Kehilangan 35% data analitik durasi baca (*dwell time*) pengguna karena panggilan `fetch` standar dibatalkan peramban saat pengguna menutup tab secara mendadak.

### Akar Masalah Teknis
1.  **Layout Thrashing:** Infinite scroll menggunakan implementasi lama berbasis `window.addEventListener('scroll', ...)` yang memanggil `getBoundingClientRect()` pada 200 item DOM card sekaligus.
2.  **Observer & Memory Leak:** Pengembang membuat instance `IntersectionObserver` baru per satu elemen artikel tanpa pernah mengeksekusi `.unobserve()` atau `.disconnect()`, memicu retensi pointer pada DOM node yang sudah tidak terpakai.
3.  **Invalid Lifecycle Handling:** Menggunakan `window.addEventListener('beforeunload', ...)` yang memanggil sinkronik `fetch` atau perulangan `while(Date.now() < start + delay)` untuk menahan thread hingga data telemetri terkirim, merusak BFCache dan mematikan performa rendering.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur produksi di bawah ini mengimplementasikan:
1.  **Virtual Resource Lifecycle Manager:** Observer tunggal yang mengelola *Lazy Loading* dan unmounting resource interaktif.
2.  **Dwell-time Tracker Deterministic:** Menggunakan `IntersectionObserver` dan Page Lifecycle API.
3.  **Telemetry Ingestion System:** Memanfaatkan `keepalive` fetch dan fallback `sendBeacon` dengan struktur data yang aman terhadap kompresi JSON.

```javascript
/**
 * Production-Grade Resource & Lifecycle Observability Engine
 * Module: EnterpriseInfiniteStreamManager
 */
class EnterpriseLifecycleTracker {
  #dwellStartTime = 0;
  #totalDwellTimeMs = 0;
  #isActive = false;
  #telemetryEndpoint;
  #abortController = new AbortController();

  constructor(telemetryEndpoint) {
    this.#telemetryEndpoint = telemetryEndpoint;
    this.#initLifecycleWatchers();
  }

  #initLifecycleWatchers() {
    const { signal } = this.#abortController;

    // Monitor Document Visibility State
    document.addEventListener(
      'visibilitychange',
      () => {
        if (document.visibilityState === 'hidden') {
          this.#pauseTimer();
          this.flushTelemetry(false);
        } else {
          this.#resumeTimer();
        }
      },
      { signal }
    );

    // Tangani freeze event khusus browser modern (BFCache freeze state)
    document.addEventListener(
      'freeze',
      () => {
        this.#pauseTimer();
        this.flushTelemetry(false);
      },
      { signal }
    );

    // Tangani Pagehide (terjadi sebelum dokumen dihancurkan / masuk BFCache)
    window.addEventListener(
      'pagehide',
      (event) => {
        this.#pauseTimer();
        // event.persisted menandakan halaman masuk ke BFCache
        this.flushTelemetry(true);
      },
      { signal }
    );

    this.#resumeTimer();
  }

  #resumeTimer() {
    if (!this.#isActive) {
      this.#dwellStartTime = performance.now();
      this.#isActive = true;
    }
  }

  #pauseTimer() {
    if (this.#isActive) {
      this.#totalDwellTimeMs += performance.now() - this.#dwellStartTime;
      this.#isActive = false;
    }
  }

  publicGetDwellTime() {
    if (this.#isActive) {
      return this.#totalDwellTimeMs + (performance.now() - this.#dwellStartTime);
    }
    return this.#totalDwellTimeMs;
  }

  /**
   * Mengirim data telemetri secara deterministik tanpa memblokir thread.
   * @param {boolean} isTerminating - Apakah halaman sedang dalam proses pembongkaran.
   */
  flushTelemetry(isTerminating = false) {
    const payload = JSON.stringify({
      url: window.location.href,
      dwellTimeMs: Math.round(this.publicGetDwellTime()),
      timestamp: Date.now(),
      isTerminating,
      clientPerf: {
        memory: performance.memory?.usedJSHeapSize ?? null,
      }
    });

    // 1. Upayakan navigator.sendBeacon terlebih dahulu untuk payload unload
    if (navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' });
      const success = navigator.sendBeacon(this.#telemetryEndpoint, blob);
      if (success) return;
    }

    // 2. Fallback menggunakan fetch dengan keepalive: true
    try {
      fetch(this.#telemetryEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true, // Crucial: Bertahan meski konteks halaman dihancurkan
        mode: 'cors',
      }).catch(() => {
        // Silent catch untuk mencegah unhandled rejection saat network shutdown
      });
    } catch (err) {
      console.error('[Telemetry] Network delivery failure:', err);
    }
  }

  destroy() {
    this.#abortController.abort();
    this.#pauseTimer();
  }
}

/**
 * High-Performance Flyweight Intersection Pool
 * Mengelola ribuan target DOM hanya dengan SATU instance observer internal.
 */
class FlyweightIntersectionPool {
  #observer;
  #callbacks = new WeakMap();

  constructor(options = {}) {
    const config = {
      root: null,
      rootMargin: '100px 0px', // Pre-load konten sebelum masuk viewport sejauh 100px
      threshold: 0.1,
      ...options,
    };

    this.#observer = new IntersectionObserver((entries) => {
      for (let i = 0; i < entries.length; i++) {
        const entry = entries[i];
        const registeredAction = this.#callbacks.get(entry.target);
        if (registeredAction) {
          registeredAction(entry);
        }
      }
    }, config);
  }

  observe(element, callback) {
    if (!(element instanceof Element)) {
      throw new TypeError('Target harus merupakan instance dari DOM Element');
    }
    this.#callbacks.set(element, callback);
    this.#observer.observe(element);
  }

  unobserve(element) {
    this.#callbacks.delete(element);
    this.#observer.unobserve(element);
  }

  disconnect() {
    this.#observer.disconnect();
  }
}

// ==========================================
// Integrasi Eksekusi Pada Lingkungan Runtime
// ==========================================

const telemetryEngine = new EnterpriseLifecycleTracker('/v2/telemetry/dwell');
const sharedIntersectionObserver = new FlyweightIntersectionPool();

// Penggunaan pada infinite stream card
document.querySelectorAll('.news-article-card').forEach((cardElement) => {
  sharedIntersectionObserver.observe(cardElement, (entry) => {
    if (entry.isIntersecting) {
      // Lazy-load sub-elemen internal atau load media HD
      const mediaTarget = entry.target.querySelector('img[data-src]');
      if (mediaTarget) {
        mediaTarget.src = mediaTarget.getAttribute('data-src');
        mediaTarget.removeAttribute('data-src');
      }
      // Hentikan observasi jika hanya butuh perlakuan satu kali (one-off)
      sharedIntersectionObserver.unobserve(entry.target);
    }
  });
});
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Metrik | Event Listener Scroll Tradisional (`scroll`) | Native Observers (`IntersectionObserver`) | Web Workers dengan Komputasi Offload |
| :--- | :--- | :--- | :--- |
| **Beban Eksekusi Main Thread** | **Tinggi (Kritis):** Terpanggil setiap frame tick (16ms pada 60Hz, 8ms pada 120Hz). Menimbulkan frame drop jika tidak di-*throttle*. | **Sangat Rendah:** Perhitungan kalkulasi bounding rect didelegasikan ke Compositor Engine C++. | **Nol pada Main Thread:** Dijalankan sepenuhnya di thread terpisah (namun tidak memiliki akses langsung ke DOM). |
| **Risiko Layout Thrashing** | **Sangat Tinggi:** Akses tak terkontrol terhadap `el.getBoundingClientRect()` memicu synchronous reflow. | **Nol:** Hasil kalkulasi posisi merupakan *read-only projection* yang disediakan internal oleh browser. | **Nol:** Worker tidak memiliki konteks layout geometri dokumen. |
| **Presisi Waktu Callback** | Real-time sinkronik terhadap event tick thread. | Asinkronik (dijalankan pasca-layout, pra-paint pada task queue khusus). | Ditentukan oleh latensi *serialization/deserialization* antrian pesan IPC (`postMessage`). |
| **Kompatibilitas Memori** | Membutuhkan cleanup referensi manual via `removeEventListener`. Risiko memory leak tinggi jika closure menangkap variabel luar. | Instance dapat direndang ulang via `WeakMap`. Biaya instansiasi rendah jika menggunakan pola Flyweight (Shared instance). | Membutuhkan alokasi thread OS tersendiri. Alokasi awal berat (~beberapa MB per worker thread). |
| **Dukungan Runtime Legacy** | Universal (IE5+). | Modern Browsers (Chrome 51+, Safari 12.1+, Firefox 55+). Polyfill memakan CPU. | Modern Browsers (IE10+). Tidak kompatibel jika DOM interop dibutuhkan secara konstan. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Intersection Observer Zero-Size Target Anomaly
*   **Kasus:** Elemen target memiliki ukuran awal $0 \times 0$ piksel (misalnya, gambar dinamis tanpa atribut `width` dan `height` eksplisit sebelum dimuat, atau kontainer dengan `display: inline`).
*   **Akar Masalah:** Jika dimensi width dan height target bernilai 0, threshold komputasi intersection ratio menjadi undefined atau bernilai `0`. Callback mungkin tidak pernah terpicu untuk threshold $> 0$, atau sebaliknya terpicu berulang secara tidak wajar saat layout stabil.
*   **Mitigasi:** Pastikan elemen reservasi layout memiliki dimensi ruang minimum via CSS sebelum render: `min-height: 1px; min-width: 1px; aspect-ratio: 16/9;`.

### 2. ResizeObserver Infinite Recursion Exception
*   **Kasus:** Browser melempar error di console: `ResizeObserver loop completed with undelivered notifications`.
*   **Akar Masalah:** Terjadi ketika mutasi di dalam callback `ResizeObserver` memicu perubahan ukuran elemen lain yang sedang diobservasi atau elemen target itu sendiri pada frame render yang sama. Engine menghentikan notifikasi lanjutan untuk mencegah browser crash dalam siklus loop tak berujung.
*   **Mitigasi:** Tunda eksekusi modifikasi style yang memicu layout pass baru ke frame siklus berikutnya menggunakan `requestAnimationFrame`:
```javascript
const safeResizeObserver = new ResizeObserver((entries) => {
  requestAnimationFrame(() => {
    for (const entry of entries) {
      // Modifikasi style aman dieksekusi di sini
      entry.target.style.width = `${Math.floor(entry.contentRect.width)}px`;
    }
  });
});
```

### 3. Batasan Payload `navigator.sendBeacon`
*   **Kasus:** `sendBeacon()` mengembalikan status boolean `false`, dan data telemetri gagal terkirim secara diam-diam.
*   **Akar Masalah:** Spesifikasi browser membatasi ukuran antrian buffer data beacon yang belum terkirim (biasanya akumulasi maksimal 64 KB per konteks proses peramban). Mengirim data analitik masif pada akhir sesi akan otomatis menolak transmisi data.
*   **Mitigasi:** Batasi payload beacon hanya untuk metrik ID penting dan data esensial. Jika melebihi 64 KB, gunakan kompresi string atau pangkas array data sebelum transmit.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan Event `unload` untuk Menyimpan State
*   **Anti-pattern:**
    ```javascript
    // BURUK: Mematikan BFCache seketika pada browser modern
    window.addEventListener('unload', () => {
      localStorage.setItem('session_data', JSON.stringify(sessionData));
    });
    ```
*   **Solusi:**
    ```javascript
    // BENAR: Menggunakan event pagehide / visibilitychange
    window.addEventListener('pagehide', (event) => {
      localStorage.setItem('session_data', JSON.stringify(sessionData));
    });
    ```

### 2. Membocorkan Referensi Target pada `MutationObserver`
*   **Anti-pattern:**
    ```javascript
    // BURUK: Target dihapus dari DOM, namun observer tetap memegang subtree
    const observer = new MutationObserver(callback);
    observer.observe(document.getElementById('temp-widget'), { childList: true, subtree: true });
    // Kemudian: document.getElementById('temp-widget').remove();
    // Instance observer dan node memory TIDAK DAPAT di-garbage collect!
    ```
*   **Solusi:**
    Lakukan `.disconnect()` atau `.takeRecords()` secara eksplisit sebelum melepas referensi node, atau gunakan binding `AbortSignal` jika target dihapus dari antarmuka:
    ```javascript
    observer.disconnect();
    targetElement.remove();
    ```

### 3. Instansiasi Observer Masif di Dalam Loop
*   **Anti-pattern:**
    ```javascript
    // BURUK: 1000 instance observer untuk 1000 node
    document.querySelectorAll('.item').forEach(el => {
      const io = new IntersectionObserver(handleIntersect);
      io.observe(el);
    });
    ```
*   **Solusi:**
    Gunakan satu shared instance (*Flyweight Pattern*) untuk mengawasi ribuan node secara serentak:
    ```javascript
    // BENAR: 1 instance observer melayani 1000 node
    const sharedIo = new IntersectionObserver(handleIntersect);
    document.querySelectorAll('.item').forEach(el => sharedIo.observe(el));
    ```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan CSS Content-Visibility untuk Offscreen Rendering:**
    Kombinasikan `IntersectionObserver` modern dengan properti performa tingkat lanjut engine CSS:
    ```css
    .offscreen-section {
      content-visibility: auto;
      contain-intrinsic-size: 0 500px; /* Estimasi tinggi layout elemen sebelum dirender */
    }
    ```
    Browser akan melompati proses perhitungan layout dan paint secara otomatis untuk elemen di luar viewport tanpa butuh intervensi baris kode JavaScript yang rumit.
2.  **Deterministik Cleanup via AbortSignal Registry:**
    Saat membangun komponen aplikasi berskala besar, integrasikan seluruh listener siklus hidup dokumen ke sinyal komponen induk (*Parent Controller*), sehingga ketika komponen dihancurkan, seluruh stream browser API dihentikan seketika.
3.  **Prioritaskan `fetch(url, { keepalive: true })` Dibanding Sinkronik XHR:**
    Standardisasikan pipeline data out-of-document menggunakan `keepalive: true` yang mendukung payload fleksibel, CORS headers kustom, dan HTTP/2 / HTTP/3 multiplexing.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Benchmark: Polling Scroll Event vs Flyweight IntersectionObserver
Memantau 500 elemen DOM card pada halaman infinite scroll berkecepatan 120 FPS:

```
[ Pendekatan Tradisional (Scroll Event Listener + getBoundingClientRect) ]
Frame