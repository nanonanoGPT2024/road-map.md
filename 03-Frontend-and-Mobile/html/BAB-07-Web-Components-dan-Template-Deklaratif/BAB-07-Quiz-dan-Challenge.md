# BAB 07: Quiz, Challenge, & Knowledge Check
**Web Components & Template Deklaratif**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Inert DocumentFragment vs. Hidden DOM Tree**
   Jelaskan secara arsitektural mengapa elemen `<template>` dikategorikan sebagai *inert* oleh browser HTML parser! Bandingkan konsumsi memori, eksekusi resource (seperti tag `<img>` dengan `src` atau tag `<script>`), serta rendering pipeline antara elemen `<template>` dan elemen `<div>` dengan deklarasi style `display: none;`!

2. **Shadow Root Encapsulation & Security Fallacy**
   Apa perbedaan struktural dan runtime antara `attachShadow({ mode: 'open' })` dan `attachShadow({ mode: 'closed' })`? Berikan argumentasi teknis mengapa `mode: 'closed'` **tidak boleh** dianggap sebagai mekanisme keamanan (*security boundary*) terhadap manipulasi kode pihak ketiga (misalnya ekstensi browser atau dependensi XSS)!

3. **Keterbatasan dan Mekanisme Selektor `::slotted()`**
   Mengapa selektor `::slotted(selector)` hanya mampu menargetkan *top-level light DOM child* yang terdistribusi ke dalam slot dan tidak dapat menargetkan elemen turunan yang lebih dalam (*nested descendants*)? Jelaskan bagaimana mekanisme CSS specificity bekerja saat terjadi konflik antara rule pada Light DOM host dan rule `::slotted()` di dalam Shadow Root!

4. **Reflected Properties vs. HTML Attributes Synchronization**
   Pada spesifikasi *Custom Elements v1*, jelaskan relasi dan siklus hidup antara pemanggilan `attributeChangedCallback` dengan JavaScript property *getter/setter*! Mengapa sinkronisasi dua arah (*reflected attributes*) dapat memicu *infinite loop*, dan pola arsitektur apa yang digunakan untuk mencegah mutasi siklik tersebut?

5. **Declarative Shadow DOM (DSD) & Streaming Architecture**
   Bagaimana parser browser menangani tag `<template shadowrootmode="open">` saat memproses streaming HTML dari Server-Side Rendering (SSR)? Jelaskan bagaimana DSD mengeliminasi masalah *Flash of Unstyled Content* (FOUC) dibandingkan imperatif `attachShadow()` via JavaScript!

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Event Retargeting dan Batasan Boundary Disruption**
   Diberikan sebuah komponen `<x-user-card>` yang memiliki Shadow Root tertutup dan melempar *custom event*. Jelaskan konsep *Event Retargeting* dan bagaimana nilai dari `event.target` bertransformasi ketika sebuah event merambat keluar dari Shadow DOM menuju document root! Dalam kondisi apa pemanggilan `event.composedPath()` membocorkan informasi internal node Shadow DOM ke *event listener* eksternal?

2. **DOM Reconnection, Move Operations, dan Memory Leak Lifecycle**
   Saat sebuah node Custom Element dipindahkan dari satu kontainer ke kontainer lain dalam dokumen via `element.appendChild()`:
   - Bagaimana urutan eksekusi *lifecycle callbacks* yang terjadi (`disconnectedCallback` vs `connectedCallback` vs `adoptedCallback`)?
   - Bahaya arsitektural apa yang muncul jika pembersihan event listener global (`window.addEventListener`) atau pembatalan *Fetch/AbortController* dilakukan secara destruktif di `disconnectedCallback` tanpa membedakan skenario *DOM reparenting/reconnection*?

3. **Form-Associated Custom Elements (FACE) & ElementInternals**
   Bagaimana cara kerja antarmuka `ElementInternals` dalam mengintegrasikan Custom Element dengan elemen native `<form>`? Analisis skenario di mana sebuah custom element gagal berpartisipasi dalam event `submit` dan validasi native (`checkValidity()`, `reportValidity()`) saat didefinisikan tanpa flag `static formAssociated = true;`!

4. **Style Penetration: CSS Variables vs. `::part()` Interface Contract**
   Bandingkan strategi arsitektur isolasi gaya menggunakan *CSS Custom Properties* (*Inheritance Boundary*) versus *CSS Shadow Parts* (`::part()`). Kapan sebuah tim Design System harus mengekspos styling interface menggunakan `::part()` alih-alih menyediakan CSS Custom Properties, dan apa batasannya terhadap *combinator selectors* (seperti `::part(btn) span`)?

5. **Upgrade Timing, Custom Element Definition, dan `:defined` Pseudo-class**
   Analisis fenomena yang terjadi ketika HTML parser menemukan custom tag `<data-grid>` di DOM sebelum berkas JavaScript yang memanggil `customElements.define('data-grid', DataGrid)` selesai diunduh dan dieksekusi. Apa status node tersebut di memori (`HTMLUnknownElement` vs `HTMLElement`), dan bagaimana mitigasi visual rendering dilakukan menggunakan pseudo-class `:not(:defined)`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Rendering Degradasian & Garbage Collection Choke pada Virtualized Data-Grid
Sebuah aplikasi web *FinTech enterprise* memodernisasi tabel transaksi mereka menjadi Custom Element terisolasi bernama `<virtual-grid>`. Setiap baris transaksi di-render menggunakan `<grid-row>` yang masing-masing menginisialisasi Shadow Root secara imperatif via JavaScript:
```javascript
connectedCallback() {
  const shadow = this.attachShadow({ mode: 'open' });
  const template = document.getElementById('row-template');
  shadow.appendChild(template.content.cloneNode(true));
  // Inisialisasi event listener dan formatting internal
}
```
Ketika pengguna melakukan *fast scrolling* melewati 50.000 data menggunakan teknik virtual DOM windowing (memasang dan mencopot ratusan `<grid-row>` per detik), terjadi *frame drop* parah (jank) hingga 15 FPS dan konsumsi memori browser membengkak secara eksponensial hingga browser tab mengalami crash (*OOM - Out of Memory*).

* **Pertanyaan Diagnostik:**
  1. Identifikasi *bottleneck* fundamental pada lifecycle dan proses kloning template di atas saat instansiasi terjadi dalam frekuensi sangat tinggi!
  2. Mengapa pembuatan ribuan instance `ShadowRoot` secara dinamis menghasilkan overhead memori yang jauh lebih tinggi dibandingkan mutasi plain light DOM nodes?
  3. Rancang strategi refaktorisasi arsitektur komponen tersebut (melibatkan teknik *Constructable Stylesheets*, *DOM node recycling*, dan optimasi Shadow DOM) untuk menjaga konsumsi RAM stabil pada 60 FPS!

---

### Skenario B: Race Condition Lifecycle & Data Hydration pada Micro-Frontend Multi-Vendor
Sebuah portal e-commerce berbasis arsitektur *Micro-Frontend* memuat Custom Component `<checkout-button>` milik vendor eksternal. Di lingkungan produksi, muncul anomali kritis: sekitar 8% pengguna mengklik tombol tetapi tidak ada transaksi yang terproses, atau tombol menampilkan status *"Disabled"* secara permanen.

Investigasi menemukan kode vendor sebagai berikut:
```javascript
class CheckoutButton extends HTMLElement {
  static get observedAttributes() { return ['order-id', 'amount']; }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    this.render();
    this.setupPaymentGateway();
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue !== newValue) {
      this[name] = newValue;
      this.render(); // Re-render shadow DOM tree
    }
  }

  async setupPaymentGateway() {
    const res = await fetch(`/api/pay-init/${this.getAttribute('order-id')}`);
    this.token = await res.json();
    this.shadowRoot.querySelector('button').disabled = false;
  }

  render() {
    this.shadowRoot.innerHTML = `<button disabled>Bayar Sekarang</button>`;
  }
}
```
Aplikasi host memuat data pengguna secara asinkron dari GraphQL, lalu mengubah atribut `order-id` di DOM via JavaScript setelah komponen di-mount.

* **Pertanyaan Diagnostik:**
  1. Bedah secara mendalam *race condition* yang terjadi antara pemanggilan `attributeChangedCallback`, `connectedCallback`, dan `setupPaymentGateway()`!
  2. Apa dampak destruktif dari pemanggilan `this.shadowRoot.innerHTML = ...` di dalam `render()` terhadap *DOM references*, *active event listeners*, dan *network promise resolution*?
  3. Susun ulang implementasi kelas di atas agar sepenuhnya toleran terhadap *asynchronous property/attribute assignment*, mencegah *double-fetch*, dan tidak merusak integritas state button jika elemen dipindahkan di DOM!

---

### Skenario C: CSS Penetration Fiasco & SSR Hydration Mismatch pada Global Design System
Sebuah organisasi memigrasikan Design System internal mereka ke Web Components dengan SSR berbasis *Declarative Shadow DOM (DSD)*. Komponen form input didefinisikan sebagai:
```html
<ds-input>
  <template shadowrootmode="open">
    <style>
      .input-wrapper { display: flex; border: 1px solid var(--theme-border, #ccc); }
      input { flex: 1; outline: none; }
    </style>
    <div class="input-wrapper">
      <slot name="prefix"></slot>
      <input type="text" id="native-input" />
    </div>
  </template>
</ds-input>
```
Saat diimplementasikan pada aplikasi consumer yang menggunakan Dark Mode, terjadi insiden:
- Muncul *FOUC (Flash of Unstyled Content)* sesaat sebelum script client-side dieksekusi, di mana beberapa halaman merender input tanpa CSS DSD.
- Tema Dark Mode (`--theme-border: #333;`) yang di-inject di level `:root` Light DOM berhasil tembus, namun custom CSS class yang di-override dari Light DOM (`<ds-input class="border-red">`) gagal diaplikasikan ke `.input-wrapper` di dalam Shadow Root.
- Saat client hydration script (`customElements.define`) berjalan, DOM tree me-refresh dan teks yang telah diketik pengguna di `#native-input` tiba-tiba hilang.

* **Pertanyaan Diagnostik:**
  1. Analisis mengapa Light DOM classes (`.border-red`) tidak bisa memengaruhi `.input-wrapper`, dan bagaimana arsitektur komponen seharusnya dirancang menggunakan `:host` atau pseudo-class `:host-context()` untuk mengizinkan styling kontekstual!
  2. Mengapa teks input pengguna terhapus saat script client-side terinisialisasi? Indikasikan kesalahan umum pada imperatif hydration Web Components yang menimpa DSD!
  3. Bagaimana arsitektur *Constructable Stylesheets* (`adoptedStyleSheets`) diterapkan agar dapat berbagi ribuan baris styling Design Tokens secara hemat memori (*zero redundant parsing*) antara ratusan instance Web Component yang dirender via SSR?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Form-Associated Accessible Autocomplete Component (Design System Primitive)

#### Problem Statement
Anda ditugaskan oleh Core Architecture Team untuk membangun *native UI primitive* mandiri: `<enterprise-combobox>`. Komponen ini harus berfungsi layaknya `<select>` native yang memiliki fitur filter autocomplete, namun mampu bekerja secara *cross-framework* (dapat dipakai di React, Vue, Svelte, atau Vanilla JS) tanpa bergantung pada framework runtime pihak ketiga.

#### Requirements
1. **Shadow Encapsulation & Declarative SSR**:
   - Mendukung rendering SSR via *Declarative Shadow DOM* (`<template shadowrootmode="open">`).
   - Mencegah kebocoran styling internal keluar, namun menyediakan integrasi CSS Design System melalui *CSS Variables* dan `::part(input)`, `::part(dropdown)`, serta `::part(option)`.

2. **Form-Associated Custom Element (FACE)**:
   - Harus mengimplementasikan `static formAssociated = true;`.
   - Menggunakan `ElementInternals` untuk mengikat nilai (`setFormValue`), mendukung validasi native (`form.reportValidity()`), dan merespons lifecycle form native:
     - Reset form (`formResetCallback`).
     - Disable state (`formDisabledCallback`).
     - Restore state saat navigasi *bfcache* (`formStateRestoreCallback`).

3. **Accessibility (ARIA 1.2 Combobox Pattern)**:
   - Komponen harus sepenuhnya accessible menggunakan keyboard (`ArrowUp`, `ArrowDown`, `Enter`, `Escape`, `Home`, `End`).
   - Wajib menangani sinkronisasi atribut ARIA secara internal: `role="combobox"`, `aria-autocomplete="list"`, `aria-expanded="true|false"`, `aria-activedescendant`, dan `role="listbox"`.

4. **Slotting & Content Projection**:
   - Mendukung light-DOM `<option>` projection melalui `<slot>` default atau kustom data binding via JavaScript array.

#### Constraints
- **Zero Third-Party Dependencies**: Dilarang menggunakan runtime styling (seperti Tailwind runtime, Lit, Fast, Stencil). Wajib *pure Vanilla Web APIs*.
- **No InnerHTML Destructive Rewrites**: Dilarang me-render ulang shadow root via `innerHTML = ...` setelah fase inisialisasi awal untuk mencegah hancurnya memory references.
- **Constructable Stylesheets**: Wajib menggunakan `adoptedStyleSheets` pada shadow root jika didukung oleh browser runtime, dengan fallback yang aman.

#### Expected Output
1. **Class Implementation (`EnterpriseCombobox`)**: Implementasi lengkap kelas JavaScript yang mewarisi `HTMLElement`.
2. **HTML Markup Demonstration**:
   - Contoh representasi HTML Declarative Shadow DOM (SSR-ready).
   - Penggunaan komponen di dalam tag `<form action="/submit">` native dengan verifikasi bahwa data berhasil dikirimkan via FormData standar.
3. **Verification Snippet**: Skrip pengujian end-to-end sederhana (menggunakan JavaScript) yang memvalidasi bahwa event `formdata`, `checkValidity()`, dan mutasi atribut dinamis bekerja secara akurat.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan siklus hidup parsing antara elemen native HTML parser, inert `<template>`, dan instansiasi elemen Custom Element.
- [ ] Arsitektur Shadow DOM: Perbedaan fundamental antara Light DOM, Shadow Tree, Document Fragment, dan Slot Projection.
- [ ] Spesifikasi *Event Retargeting*: Bagaimana event merambat melewati batasan shadow boundary (`composed: true/false`, `bubbles: true/false`), dan cara membaca `composedPath()`.
- [ ] Konsep *Form-Associated Custom Elements* (FACE) dan integrasi `ElementInternals` untuk validasi, form association, dan aksesibilitas ARIA.
- [ ] Mekanisme rendering SSR dengan *Declarative Shadow DOM* (DSD) menggunakan atribut `shadowrootmode`.
- [ ] Mekanisme styling isolasi: Scoped CSS, selektor `:host`, `:host()`, `:host-context()`, `::slotted()`, `::part()`, dan Constructable Stylesheets (`CSSStyleSheet()` + `adoptedStyleSheets`).
- [ ] Keterbatasan dan implikasi keamanan antara `attachShadow({ mode: 'open' })` vs `mode: 'closed'`.
- [ ] Lifecycle standard Custom Elements: `connectedCallback`, `disconnectedCallback`, `adoptedCallback`, `attributeChangedCallback`, serta deklarasi `observedAttributes`.

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap vendor prefix kuno untuk Shadow DOM non-standar (misalnya `::-webkit-validation-bubble` atau Shadow DOM v0 API seperti `<content>` tag).
- [ ] Hex code warna atau spesifikasi visual dari komponen UI library pihak ketiga (misalnya Material UI/Bootstrap web components).
- [ ] Seluruh nomor kode error spesifik DOMException secara numerik saat Custom Element registration gagal (cukup pahami penyebab logisnya seperti nama tag tanpa tanda hubung).

### Saya harus bisa melakukan:
- [ ] Menulis dan mendaftarkan Custom Element otonom yang valid sesuai spesifikasi W3C (menggunakan *kebab-case* dan menangani *re-entrancy*).
- [ ] Membangun komponen UI terisolasi dengan Shadow DOM yang memanfaatkan template kloning secara efisien tanpa menyebabkan memory leak.
- [ ] Menyediakan *CSS theming interface* yang bersih pada Web Components menggunakan kombinasi *CSS Custom Properties* dan *CSS Parts*.
- [ ] Menghubungkan Custom Element ke native HTML Form menggunakan API `ElementInternals` sehingga elemen dapat divalidasi dan di-submit tanpa hidden `<input>` hack.
- [ ] Mengimplementasikan *Declarative Shadow DOM* untuk rendering server-side (SSR) yang bebas dari *Flash of Unstyled Content* (FOUC).
- [ ] Melakukan debugging dan profilisasi performa Web Components untuk mendeteksi detached DOM nodes, listener leaks di `disconnectedCallback`, dan blocking CPU tasks akibat rendering loop.