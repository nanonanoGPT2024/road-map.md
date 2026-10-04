# Bab 07 Module 01: Web Components & Template Deklaratif

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran**: Frontend & Mobile Architecture Track
* **Kategori**: 03-Frontend-and-Mobile
* **Topik Utama**: Web Components & Template Deklaratif
* **Tingkat Kerumitan**: Advanced / Production-Grade Architecture
* **Prasyarat Pengetahuan**: 
  * DOM Mutasi Lanjutan & Event Bubbling/Capturing
  * JavaScript ES6+ (Classes, Prototypal Inheritance, Proxy, WeakMap)
  * Asynchronous JavaScript & Microtask Timing
  * Browser Rendering Pipeline (Recalculate Style, Layout, Paint, Composite)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Mekanisme Enkapsulasi Shadow DOM**: Mengidentifikasi boundary antara Light DOM dan Shadow DOM, serta membedakan mode encapsulation (`open` vs `closed`) dan implementasi styling boundary via CSS Scoping (`:host`, `:host-context()`, `::slotted()`).
2. **Menguasai Siklus Hidup Custom Elements V1**: Mengorkestrasi microtask-safe state management menggunakan `connectedCallback`, `disconnectedCallback`, `adoptedCallback`, dan `attributeChangedCallback`.
3. **Mengoptimalkan Template Deklaratif & Shadow DOM**: Mengimplementasikan `<template>` dan `<slot>` deklaratif serta menyusun arsitektur Declarative Shadow DOM (DSD) untuk Server-Side Rendering (SSR) guna meniadakan Cumulative Layout Shift (CLS) dan Flash of Unstyled Content (FOUC).
4. **Menerapkan Pola Reaktivitas Kinerja Tinggi**: Mengintegrasikan `Adopted StyleSheets` (`CSSStyleSheet()`) untuk pembagian memori styling lintas ribuan node instance dan mengamankan integritas DOM menggunakan safe sanitization techniques.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari Abstraksi Framework ke Standar Runtime Native

Dalam dekade terakhir, ekosistem web didominasi oleh layer abstraksi berbasis Virtual DOM (V-DOM) seperti React, atau kompilasi komputasi reaktif seperti Svelte. Meskipun efektif, model-model ini memberlakukan **Framework Tax**:
1. Bundle payload JavaScript yang besar hanya untuk mengoperasikan runtime framework.
2. Fragmentasi ekosistem (komponen UI React tidak dapat secara langsung digunakan di Angular atau Vue tanpa wrapper).
3. Biaya Garbage Collection (GC) dan rekonsiliasi V-DOM yang membebani CPU thread utama.

```
+-----------------------------------------------------------------------+
| TRADITIONAL FRAMEWORK PARADIGM                                         |
| [JSX / Template] -> [Compiler] -> [V-DOM Tree] -> [Reconciliation Engine]
|                                                          | (Diffing)  |
|                                                          v            |
|                                                     [Browser DOM]     |
+-----------------------------------------------------------------------+
| WEB COMPONENTS (STANDARDS-BASED NATIVE RUNTIME)                       |
| [Declarative HTML/DSD] -------------------------------> [Browser DOM] |
| [Custom Elements API]  == Native Browser C++ Layer ==> [Shadow Tree]  |
+-----------------------------------------------------------------------+
```

Mental model Web Components adalah mengembalikan kedaulatan ke **Browser Engine (C++/Rust Native Runtime)**:
* **Custom Elements**: Memberdayakan developer untuk memperluas kosakata HTML vocabulary secara legal via `customElements.define()`.
* **Shadow DOM**: Dinding enkapsulasi sejati (*true boundary*). Tidak ada CSS leaky abstraction, tidak ada ID collision, tidak ada intervensi global query selector (`document.querySelector` tidak menembus batas shadow).
* **HTML Templates (`<template>` & `<slot>`)**: Parser browser meng-cache blueprint dokumen dalam kondisi inaktif (inert) tanpa eksekusi skrip atau network fetching, di-clone dengan alokasi memori mendekati nol via `cloneNode(true)`.
* **Declarative Shadow DOM (DSD)**: Menghubungkan jurang antara SSR dan enkapsulasi native tanpa hydration waterfall berbasis client JS.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Custom Element & Event Propagation Boundary

Diagram berikut mengilustrasikan transisi state dari Custom Element sejak instansiasi hingga pelepasan dari layout engine, beserta jalur propagasi event yang melewati batas Shadow Root.

```
                           LIFECYCLE STATE MACHINE
                           
     [ HTML Parser / document.createElement() ]
                         |
                         v
                +------------------+
                |   constructor()  | <--- Super(), attachShadow(),
                +------------------+      Inisialisasi Internal State
                         |
           +-------------+-------------+
           | Inserted into DOM         | Attributes altered
           v                           v
+-----------------------+     +-------------------------------+
|  connectedCallback()  |     |   attributeChangedCallback()  |
+-----------------------+     +-------------------------------+
           |                                   |
           +-----------------+-----------------+
                             |
                   Moved to new document
                             v
                  +--------------------+
                  |  adoptedCallback() |
                  +--------------------+
                             |
                   Removed from DOM
                             v
                +-------------------------+
                |  disconnectedCallback() | <--- Cleanup listeners,
                +-------------------------+      AbortControllers, timers
                             |
                             v
                        [ GC Engine ]
```

### Event Retargeting & Boundary Propagation

```
  LIGHT DOM (Document Root)
  +-------------------------------------------------------------------------+
  |  <main>                                                                 |
  |     |                                                                   |
  |     +--> <custom-card> (Host Element)                                   |
  |             |                                                           |
  |             | === SHADOW BOUNDARY ====================================  |
  |             |                                                           |
  |             +--> #shadow-root (open)                                    |
  |                     |                                                   |
  |                     +--> <div class="card-inner">                       |
  |                             |                                           |
  |                             +--> <button id="action-btn">Click</button> |
  +-------------------------------------------------------------------------+

EVENT DISPATCH PIPELINE:
User clicks <button id="action-btn">

Inside Shadow Root:
  event.target: <button id="action-btn">
  event.composedPath(): [<button>, <div.card-inner>, #shadow-root, <custom-card>, <main>, <body>, <html>, document, Window]

Crossing the Shadow Boundary to Document Root (Retargeting):
  event.composed: true   -> Event diperbolehkan melintasi boundary.
  event.composed: false  -> Event tertahan di dalam #shadow-root.
  
Outside Shadow Root (on <main> or document):
  event.target: <custom-card> (Retargeted! Detail internal disembunyikan)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi Shadow Root: `open` vs `closed`

Ketika memanggil `element.attachShadow({ mode: 'open' | 'closed' })`, layout engine browser mengalokasikan objek `ShadowRoot` yang ditautkan ke pointer elemen internal host.

| Parameter Mekanisme | `mode: 'open'` | `mode: 'closed'` |
| :--- | :--- | :--- |
| **Aksesibilitas JavaScript** | `element.shadowRoot` mengembalikan instance `ShadowRoot`. | `element.shadowRoot` selalu mengembalikan `null`. |
| **Akses via DevTools** | Terlihat dan dapat diinspeksi secara penuh. | Tetap terlihat di browser inspector, bukan merupakan mekanisme keamanan. |
| **Keamanan Kriptografis** | Nol. Akses langsung diizinkan. | Nol. Dapat ditembus jika `Element.prototype.attachShadow` di-*monkeypatch* sebelum script berjalan. |
| **Rekomendasi Arsitektur** | **Sangat Direkomendasikan**. Memudahkan testing, integrasi DOM pihak ketiga, dan interoperabilitas framework. | Hindari kecuali untuk implementasi internal browser (misal tag native `<video>`). |

### 2. Slotting & Transklusi: Arsitektur Pohon Ganda (Flattened Tree)

Komponen Web tidak memindahkan children Light DOM ke dalam Shadow DOM. Sebagai gantinya, layout engine membentuk **Flattened Tree**:

```
Light Tree:                  Shadow Tree:                 Flattened Tree (Rendering):
<custom-card>                #shadow-root                 <custom-card>
  <span slot="title">          <header>                     <header>
    Halo                         <slot name="title">          <span slot="title">Halo</span>
  </span>                      </header>                    </header>
```

Aturan Transklusi:
* Konten slot tetap hidup dalam Light DOM. Selector CSS global (`span { color: red; }`) tetap mempengaruhi konten yang dislotkan.
* Konten fallback di dalam `<slot>Fallback Data</slot>` hanya di-render jika tidak ada node yang cocok yang dipetakan ke slot tersebut.

### 3. CSS Scoping Engine: `:host`, `::slotted`, dan Inherited Properties

* **`:host`**: Menargetkan elemen Custom Element itu sendiri dari dalam Shadow CSS.
* **`:host([disabled])`**: Menargetkan host hanya ketika atribut `disabled` ada.
* **`:host-context(.dark-theme)`**: Mengaktifkan styling bersyarat jika ancestor di Light DOM memenuhi kriteria selector (berguna untuk Theming).
* **`::slotted(selector)`**: Menargetkan elemen terdistribusi dari Light DOM. **Pembatasan kritis**: Selector `::slotted()` hanya dapat menargetkan elemen turunan langsung (*compound selector* tidak diperbolehkan, misal `::slotted(div .child)` tidak valid; hanya `::slotted(div)`).
* **CSS Custom Properties**: CSS Variables menembus Shadow Boundary secara bebas. Variabel yang didefinisikan pada `:root` atau host akan diwariskan ke seluruh kedalaman sub-tree Shadow DOM.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Custom Elements Registry & Konstruksi Kelas
Pendaftaran komponen menggunakan `CustomElementRegistry` (`window.customElements`). Aturan spesifikasi W3C/WHATWG mewajibkan:
1. **Valid Custom Element Name**: Wajib mengandung karakter strip/hyphen (`-`) untuk membedakannya dari tag standar HTML masa kini dan masa depan (misal `<app-drawer>`, bukan `<appdrawer>`). Karakter awal harus berupa huruf alfabet ASCII.
2. **Prototype Chaining**: Kelas wajib mewarisi `HTMLElement` (Autonomous Custom Elements) atau subclass spesifik seperti `HTMLButtonElement` (Customized Built-in Elements).

```javascript
class MetricDisplay extends HTMLElement {
  // Wajib static getter untuk attribute-observation pipeline
  static get observedAttributes() {
    return ['value', 'unit', 'status'];
  }

  constructor() {
    super(); // Wajib dipanggil pertama kali untuk menginisialisasi prototype chain
    // Inisialisasi state murni internal di sini.
    // DILARANG: Memeriksa atribut atau memanipulasi children di constructor.
  }
}
customElements.define('metric-display', MetricDisplay);
```

### Declarative Shadow DOM (DSD)
Sebelum standardisasi DSD, Server-Side Rendering (SSR) untuk Web Components mengalami kegagalan struktural. Server mengirim HTML kustom, tetapi shadow tree tidak ada sampai JavaScript di-parse, dikompilasi, dan dieksekusi di client, menyebabkan pergeseran layout drastis (CLS).

DSD memecahkan masalah ini secara deklaratif via tag `<template shadowrootmode="open">`:

```html
<enterprise-alert type="critical">
  <template shadowrootmode="open">
    <style>
      :host { display: block; border-left: 4px solid red; }
    </style>
    <div class="alert-box">
      <slot></slot>
    </div>
  </template>
  <p>Basis data produksi mengalami koneksi putus!</p>
</enterprise-alert>
```

Browser HTML parser secara otomatis mengonversi tag template tersebut menjadi instance `#shadow-root` sebelum paint pertama terjadi, tanpa membutuhkan dependensi script client satu byte pun.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental dari komponen `AppBadge` yang mendemonstrasikan integrasi `<template>`, `attachShadow`, attribute observation, dan lifecycle events.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Fundamental Web Component</title>
</head>
<body>

  <!-- Inactive Declarative Template -->
  <template id="app-badge-template">
    <style>
      :host {
        display: inline-flex;
        align-items: center;
        font-family: system-ui, -apple-system, sans-serif;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 9999px;
        padding: 0.25rem 0.75rem;
        line-height: 1;
        transition: background-color 0.2s ease, color 0.2s ease;
      }
      :host([variant="info"]) {
        background-color: #e0f2fe;
        color: #0369a1;
      }
      :host([variant="success"]) {
        background-color: #dcfce7;
        color: #15803d;
      }
      :host([variant="danger"]) {
        background-color: #fee2e2;
        color: #b91c1c;
      }
      .dot {
        width: 0.5rem;
        height: 0.5rem;
        border-radius: 50%;
        background-color: currentColor;
        margin-right: 0.375rem;
      }
    </style>
    <span class="dot" aria-hidden="true"></span>
    <slot>Status Default</slot>
  </template>

  <!-- Penggunaan Komponen -->
  <app-badge variant="success">Berjalan Normal</app-badge>
  <app-badge variant="danger">Server Down</app-badge>

  <script>
    class AppBadge extends HTMLElement {
      static get observedAttributes() {
        return ['variant'];
      }

      constructor() {
        super();
        const template = document.getElementById('app-badge-template');
        const shadowRoot = this.attachShadow({ mode: 'open' });
        shadowRoot.appendChild(template.content.cloneNode(true));
      }

      connectedCallback() {
        if (!this.hasAttribute('variant')) {
          this.setAttribute('variant', 'info');
        }
      }

      attributeChangedCallback(name, oldValue, newValue) {
        if (oldValue !== newValue && name === 'variant') {
          // Logika update khusus jika diperlukan
          this.#renderAccessibility(newValue);
        }
      }

      #renderAccessibility(variant) {
        this.setAttribute('role', 'status');
        this.setAttribute('aria-label', `Status: ${variant}`);
      }
    }

    customElements.define('app-badge', AppBadge);
  </script>
</body>
</html>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Menganalisis implementasi pada **Seksi 07**:

* **Baris 10–39 (`<template id="app-badge-template">`)**: Konten di dalam template ini bersifat *inert*. Browser memvalidasi sintaks HTML di dalamnya, tetapi file gambar tidak di-load, skrip tidak berjalan, dan CSS tidak bocor ke luar dokumen.
* **Baris 12–20 (`:host`)**: Mendeklarasikan struktur display CSS untuk node `app-badge`. Ini mengeliminasi perilaku default Custom Element yang bertipe `display: inline` tanpa layout properties.
* **Baris 21–32 (`:host([variant="..."])`)**: Selector bersyarat berdasarkan keberadaan atribut di Light DOM. Mengubah skema warna internal Shadow DOM tanpa memaparkan class internal ke user.
* **Baris 40 (`<slot>Status Default</slot>`)**: Titik proyeksi konten transklusi. Teks "Berjalan Normal" diproyeksikan ke sini. Jika slot kosong, teks "Status Default" muncul secara native.
* **Baris 49 (`static get observedAttributes()`)**: Mengembalikan array string atribut yang didaftarkan ke rendering engine. Perubahan pada atribut selain yang ada di array ini tidak akan memicu trigger callback C++ browser.
* **Baris 53 (`super()`)**: Mengesahkan prototype chain kelas. Harus dipanggil sebelum mengakses keyword `this`.
* **Baris 55 (`this.attachShadow({ mode: 'open' })`)**: Menginisialisasi context Shadow DOM baru untuk host instance dan mengikatnya ke reference internal.
* **Baris 56 (`template.content.cloneNode(true)`)**: Melakukan kloning *deep memory* dari `DocumentFragment` template. Operasi ini jauh lebih efisien dibanding parsing string menggunakan `innerHTML`.
* **Baris 59–63 (`connectedCallback()`)**: Invokasi siklus hidup saat node terikat pada document DOM tree aktif. Di sini operasi manipulasi atribut awal diterapkan secara aman.
* **Baris 65–70 (`attributeChangedCallback(...)`)**: Dipanggil secara asinkron atau sinkron saat atribut yang diobservasi berubah melalui JS (`setAttribute`) atau parsing HTML parser.
* **Baris 78 (`customElements.define('app-badge', AppBadge)`)**: Mendaftarkan custom tag ke registry dokumen browser. Mulai dari titik ini, setiap kali tag `<app-badge>` ditemukan di parser, kelas `AppBadge` akan diinstansiasi.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Production Scenario)

### Masalah: Real-Time Telemetry Data-Grid Micro-Frontend
Pada platform enterprise monitoring infrastruktur, tim dashboard harus menampilkan matriks status lebih dari 10.000 kontainer Kubernetes secara serentak. 

**Bottleneck Arsitektural Sebelumnya:**
1. Menggunakan komponen berbasis React/Vue di dalam loop rendering memakan memori JS heap hingga >400 MB karena overhead Virtual DOM wrapper, fiber tree tracking, dan closure listeners.
2. Injecting `<style>` tag berulang kali di setiap item tabel memicu *Recalculate Style* berulang (Thrashing) yang membuat Frame Rate drop drastis di bawah 20 FPS saat update stream WebSocket 60Hz masuk.
3. CSS bertabrakan antar widget yang dibuat oleh tim platform berbeda (nama class global saling menimpa).

**Solusi Desain Arsitektur Baru:**
Membangun elemen kustom `telemetry-meter` mandiri menggunakan Web Components native murni dengan:
* **Constructable StyleSheets (`adoptedStyleSheets`)**: Satu single instance CSS yang di-cache di memori GPU/C++ styling engine, dibagikan ke 10.000 Shadow Roots secara serentak (zero memory redundancy).
* **AbortController Lifecycle Disposer**: Mencegah kebocoran memori dari WebSocket/DOM listeners saat elemen di-*virtualize* atau di-unmount.
* **Bypass V-DOM Direct Mutasi**: Memperbarui status internal elemen langsung via Shadow DOM mutation pipeline saat pesan biner tiba, menjaga performa tetap stabil di 60 FPS pada memori heap <30 MB.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Di bawah ini adalah kode produksi untuk custom element `TelemetryMeter` yang mengimplementasikan **Constructable StyleSheets**, manajemen lifecycle anti-leak memori (`AbortController`), serta enkapsulasi performa tinggi.

```javascript
/**
 * @fileoverview TelemetryMeter - Enterprise-grade Custom Element
 * Menggunakan Constructable StyleSheets dan Resource Cleanup Otomatis.
 */

// 1. Inisialisasi Constructable StyleSheet di level modul (Shared Memory)
const telemetrySheet = new CSSStyleSheet();
telemetrySheet.replaceSync(`
  :host {
    display: grid;
    grid-template-columns: 120px 1fr 60px;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background-color: var(--meter-bg, #1e293b);
    color: var(--meter-text, #f8fafc);
    border-radius: 4px;
    font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
    font-size: 12px;
    contain: content; /* Isolasi layout, style, dan paint */
  }

  :host([data-status="critical"]) {
    --meter-accent: #ef4444;
    background-color: #450a0a;
  }

  :host([data-status="warning"]) {
    --meter-accent: #f59e0b;
  }

  :host([data-status="healthy"]) {
    --meter-accent: #10b981;
  }

  .label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .track {
    background: #334155;
    border-radius: 9999px;
    height: 8px;
    overflow: hidden;
    position: relative;
  }

  .fill {
    height: 100%;
    background-color: var(--meter-accent, #38bdf8);
    width: 0%;
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .value {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
`);

export class TelemetryMeter extends HTMLElement {
  static get observedAttributes() {
    return ['metric-name', 'value', 'max', 'warning-threshold', 'critical-threshold'];
  }

  // Private state field encapsulation
  #shadow;
  #abortController = null;
  #elements = {};

  constructor() {
    super();

    // Attach open shadow root
    this.#shadow = this.attachShadow({ mode: 'open' });

    // Terapkan Shared StyleSheet (Zero-copy memory)
    this.#shadow.adoptedStyleSheets = [telemetrySheet];

    // Bangun struktur DOM sekali saja
    this.#shadow.innerHTML = `
      <span class="label" id="lbl"></span>
      <div class="track" role="progressbar" aria-valuemin="0" aria-valuemax="100" id="prog">
        <div class="fill" id="bar"></div>
      </div>
      <span class="value" id="val">0%</span>
    `;

    // Cache node references untuk menghindari querySelector berkali-kali
    this.#elements = {
      label: this.#shadow.getElementById('lbl'),
      fill: this.#shadow.getElementById('bar'),
      value: this.#shadow.getElementById('val'),
      progress: this.#shadow.getElementById('prog'),
    };
  }

  connectedCallback() {
    this.#abortController = new AbortController();
    const { signal } = this.#abortController;

    // Pasang listener internal dengan abort signal
    this.addEventListener('click', this.#handleElementClick.bind(this), { signal });

    this.#render();
  }

  disconnectedCallback() {
    // Batalkan seluruh event listener dan asynchronous workers
    if (this.#abortController) {
      this.#abortController.abort();
      this.#abortController = null;
    }
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue) return;
    this.#render();
  }

  #calculatePercentage(val, max) {
    if (max <= 0) return 0;
    return Math.min(Math.max((val / max) * 100, 0), 100);
  }

  #render() {
    // Ambil data dari attributes dengan sanitasi tipe data numerik
    const metricName = this.getAttribute('metric-name') || 'Unknown';
    const value = parseFloat(this.getAttribute('value') || '0');
    const max = parseFloat(this.getAttribute('max') || '100');
    const warning = parseFloat(this.getAttribute('warning-threshold') || '70');
    const critical = parseFloat(this.getAttribute('critical-threshold') || '90');

    const percentage = this.#calculatePercentage(value, max);

    // Tentukan status
    let status = 'healthy';
    if (percentage >= critical) {
      status = 'critical';
    } else if (percentage >= warning) {
      status = 'warning';
    }

    // Refleksikan status ke atribut host untuk styling scoped
    this.dataset.status = status;

    // Mutasi node secara terarah
    this.#elements.label.textContent = metricName;
    this.#elements.label.title = metricName;
    
    this.#elements.fill.style.width = `${percentage}%`;
    this.#elements.value.textContent = `${percentage.toFixed(0)}%`;

    // Update atribut aksesibilitas ARIA
    this.#elements.progress.setAttribute('aria-valuenow', percentage.toFixed(0));
    this.#elements.progress.setAttribute('aria-label', metricName);
  }

  #handleElementClick() {
    // Dispatch custom event melintasi batas shadow DOM
    this.dispatchEvent(
      new CustomEvent('metric-select', {
        bubbles: true,
        composed: true, // Memungkinkan event menembus batas Shadow DOM
        detail: {
          metricName: this.getAttribute('metric-name'),
          value: parseFloat(this.getAttribute('value') || '0'),
          status: this.dataset.status,
        },
      })
    );
  }
}

// Mendaftarkan komponen secara aman
if (!customElements.get('telemetry-meter')) {
  customElements.define('telemetry-meter', TelemetryMeter);
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

Analisis arsitektural komparatif antara implementasi Web Components Native, React Component (V-DOM), dan standard CSS Modules/Emulated Scoping:

| Dimensi Arsitektural | Web Components Native (DSD + Custom Elements) | Framework Komponen (e.g., React Component) | CSS Modules / Emulated Scoped CSS |
| :--- | :--- | :--- | :--- |
| **Enkapsulasi CSS** | **Keras (Hard Engine Boundary)**: Isolasi mutlak via Shadow DOM. Style di luar mustahil bocor masuk tanpa variable explicit. | **Lemah (Emulated)**: Menggunakan prefix hashing (`.btn_a8f9`). Rentan bentrok jika selector global menggunakan tag selector. | **Trik Sintaks**: Hanya prefixing string. Tetap berbagi namespace CSS global runtime. |
| **Footprint Memori per 10k Elemen** | **Sangat Ringan**: Menggunakan `CSSStyleSheet` bersama. Node instances dialokasikan langsung di native memory browser. | **Berat**: Memerlukan V-DOM tracking tree, closure listener di memori JS, fiber reconciler overhead. | **Tergantung Runtime JS**: Sering menduplikasi tag style jika tidak diproses melalui bundler modern. |
| **SEO & SSR Interoperabilitas** | **Tinggi via Declarative Shadow DOM (DSD)**. Parsed native oleh browser tanpa hydration lock. | **Tinggi via Framework SSR Engine**, namun memerlukan JavaScript hydration hydration phase yang besar. | **Sangat Baik**: Menghasilkan HTML/CSS konvensional tanpa dependensi runtime. |
| **Integrasi Antar-Ekosistem** | **Universal**: Berjalan mulus di Angular, Vue, React, Svelte, atau Vanilla JS tanpa wrapper layer. | **Terkunci Ekosistem**: Memerlukan ekosistem React wrapper khusus untuk berjalan di runtime lain. | **Universal**: Hanya konvensi penamaan CSS stylesheet biasa. |
| **Kompleksitas Data Passing** | **Terbatas pada String/Primitive** via HTML Attributes, memerlukan JS property binding untuk object/array kompleks. | **Sangat Ekspresif**: Mendukung passing function, nested objects, dan dynamic symbols secara native via Props. | **Tidak Relevan**: Hanya menangani layer representasi stylesheet visual. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Custom Elements Constructor Restrictions Trap
Spesifikasi W3C melarang keras eksekusi beberapa operasi di dalam `constructor()` Custom Element:
* **Larangan**: Memeriksa children, membaca atribut (`this.getAttribute()`), atau menambahkan atribut (`this.setAttribute()`).
* **Penyebab**: Elemen belum sepenuhnya dikonstruksi oleh C++ engine HTML parser. Mengakses atribut di constructor akan memicu error: `DOMException: Failed to construct 'CustomElement': The result must not have attributes`.
* **Solusi**: Tunda seluruh inisialisasi state atribut ke dalam `connectedCallback()`.

### 2. Form Association Failure
Custom Element tidak dapat mengirimkan nilai (value) ke tag `<form>` secara otomatis jika diperlakukan sebagai input biasa.
* **Solusi**: Gunakan **Form-Associated Custom Elements API**:
```javascript
class CustomInput extends HTMLElement {
  static formAssociated = true;

  constructor() {
    super();
    this._internals = this.attachInternals(); // Menautkan form lifecycle
  }

  setValue(val) {
    this._internals.setFormValue(val); // Nilai ini akan di-submit bersama form
  }
}
```

### 3. FOUC (Flash of Unstyled Content) saat Client-Side Hydration
Jika custom elements diregistrasikan via skrip asinkron (`async`/`defer`), browser akan me-render tag HTML yang belum dikenal (`HTMLUnknownElement`) sebelum JavaScript dieksekusi.
* **Solusi CSS**: Gunakan pseudo-class `:defined` di level dokumen global:
```css
/* Sembunyikan elemen sebelum definisinya diregistrasi oleh JS engine */
telemetry-meter:not(:defined) {
  display: block;
  min-height: 40px;
  background-color: #1e293b;
  opacity: 0;
}
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Menyuntikkan `<style>` Tag Menggunakan `innerHTML` Berulang Kali
```javascript
// BURUK (Memory Leak & Layout Engine Thrashing):
connectedCallback() {
  this.shadowRoot.innerHTML = `
    <style>
      .btn { color: red; } /* Browser mem-parse ulang stylesheet string ini untuk setiap instance elemen! */
    </style>
    <button class="btn">Click</button>
  `;
}
```
```javascript
// BENAR (Constructable StyleSheets):
const sharedSheet = new CSSStyleSheet();
sharedSheet.replaceSync(`.btn { color: red; }`);

class MyButton extends HTMLElement {
  constructor() {
    super();
    const root = this.attachShadow({ mode: 'open' });
    root.adoptedStyleSheets = [sharedSheet]; // Dialokasikan satu kali, di-share ke N instances!
    root.innerHTML = `<button class="btn">Click</button>`;
  }
}
```

### Anti-Pattern 2: Melupakan Event Unbinding (Memory Leak Saat Virtual DOM Meng-unmount)
```javascript
// BURUK:
connectedCallback() {
  window.addEventListener('resize', this.onResize); // Listener ini akan hidup selamanya di memori
}
```
```javascript
// BENAR: Menggunakan AbortController Pattern
#abortCtrl;

connectedCallback() {
  this.#abortCtrl = new AbortController();
  window.addEventListener('resize', this.onResize, { 
    signal: this.#abortCtrl.signal 
  });
}

disconnectedCallback() {
  this.#abortCtrl.abort(); // Secara otomatis mencabut seluruh listener yang terhubung ke signal
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Atribut vs Properti (Dual-Binding)**:
   * **Attributes**: Berfungsi untuk konfigurasi deklaratif, SSR, dan tipe data string/primitif.
   * **Properties**: Berfungsi untuk tipe data kompleks (objek, array, fungsi) di JavaScript runtime.
   * Hubungkan keduanya: Ketika atribut diubah, perbarui properti yang sesuai. Saat properti diubah, refleksikan kembali ke atribut (kecuali data berukuran besar untuk menghindari overhead serialization).

```javascript
get value() {
  return parseFloat(this.getAttribute('value') || '0');
}
set value(val) {
  this.setAttribute('value', String(val));
}
```

2. **Styling Hooks Menggunakan CSS Variables**: Selalu buat kontrak publik interface styling menggunakan CSS Custom Properties. Jangan paksa developer luar menembus shadow root menggunakan implementasi kotor.
```css
/* Kontrak Variabel Publik Elemen */
:host {
  background-color: var(--my-component-bg, #ffffff);
  padding: var(--my-component-padding, 1rem);
}
```

3. **Event Design: Composed & Bubbling**: Hanya pasang opsi `composed: true` pada Custom Event jika event tersebut memang didesain secara publik untuk didengarkan oleh elemen Light DOM di luar hierarki komponen.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. `contain: content` dan `content-visibility: auto`
Untuk komponen berat yang sering muncul di dalam list panjang (misal telemetry, feeds, chat logs), terapkan isolasi layout engine browser di level CSS host:

```css
:host {
  display: block;
  /* Menginstruksikan browser bahwa subtree elemen ini independen dari layout luar */
  contain: layout style paint;
  /* Lewati proses painting dan layout jika elemen berada di luar viewport */
  content-visibility: auto;
  contain-intrinsic-size: 0 48px; /* Estimasi tinggi saat virtualized */
}
```

### 2. Batching DOM Updates Menggunakan Microtask Queue
Hindari re-rendering bertubi-tubi saat beberapa atribut berubah sekaligus dalam satu siklus CPU tick yang sama:

```javascript
#isPendingUpdate = false;

attributeChangedCallback() {
  if (this.#isPendingUpdate) return;
  this.#isPendingUpdate = true;
  
  // Mengelompokkan mutasi DOM ke microtask queue berikutnya
  queueMicrotask(() => {
    this.#render();
    this.#isPendingUpdate = false;
  });
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Sanitasi Ketat saat Menangani Input Pengguna ke Dalam Shadow DOM
Bahaya XSS (Cross-Site Scripting) pada Web Components setara dengan DOM konvensional. Menggunakan `this.shadowRoot.innerHTML = this.getAttribute('text')` adalah celah fatal.

```javascript
// KEAMANAN TINGKAT TINGGI: Gunakan Sanitizer API jika tersedia, atau perlakuan textContent murni
#safeRender(userInput) {
  // JANGAN: this.#container.innerHTML = userInput;
  
  // GUNAKAN DOM Parser Aman atau textContent:
  this.#