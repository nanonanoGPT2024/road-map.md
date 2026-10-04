# BAB 07: Web Components dan Template Deklaratif
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Menguasai implementasi siklus hidup tingkat lanjut Custom Elements (`connectedCallback`, `disconnectedCallback`, `attributeChangedCallback`, `adoptedCallback`) dengan penanganan microtask dan pembatalan operasi asinkron via `AbortController`.
- Mengimplementasikan **Declarative Shadow DOM (DSD)** untuk rendering sisi server (*Server-Side Rendering* / SSR) guna mengeliminasi *Flash of Unstyled Content* (FOUC) dan meningkatkan skor *Core Web Vitals* (LCP/CLS).
- Membangun **Form-Associated Custom Elements (FACE)** memanfaatkan API `ElementInternals` standar W3C untuk validasi form bawaan browser, penanganan status form (`validity`, `validationMessage`), dan integrasi semantik form tanpa ketergantungan framework.
- Merancang sistem styling terisolasi dan modular menggunakan *Constructable Stylesheets*, CSS Shadow Parts (`::part`), CSS Variables, dan slot projection tingkat lanjut.
- Menganalisis dan memitigasi kebocoran memori (*memory leak*), siklus hidup referensi DOM yang terputus, serta degradasi performa pada pohon Shadow DOM berukuran masif di lingkungan multi-framework enterprise.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta harus menguasai:
- **JavaScript Modern (ESNext)**: ES Modules, ES Classes (`extends`, `super`, `#privateField`), `AbortController`/`AbortSignal`, `WeakMap`, Microtask Queue (`queueMicrotask`), dan `MutationObserver`.
- **Dasar Web Components**: Penggunaan `customElements.define()`, `attachShadow({ mode: 'open' })`, dan elemen HTML native `<template>` serta `<slot>`.
- **Browser Rendering Pipeline**: Siklus Parse HTML, CSSOM Construction, Render Tree, Layout, Paint, dan Composite.
- **HTTP & Server-Side Basics**: Pemahaman dasar SSR/hydration menggunakan runtime Node.js, Deno, atau Bun.

---

### 3. Concept & Internal Architecture

Implementasi Web Components tingkat lanjut menuntut pemahaman mendalam tentang bagaimana engine browser (Blink, WebKit, Gecko) memproses elemen kustom dalam siklus parser, layout tree, dan garbage collector.

```
+---------------------------------------------------------------------------------------+
|                                    DOCUMENT (HOST)                                    |
|                                                                                       |
|  <enterprise-input name="user_id" required>                                          |
|    |                                                                                  |
|    |-- [Light DOM] ---------------------------------------------+                     |
|    |   <span slot="helper">Format: UUIDv4</span>                |                     |
|    +------------------------------------------------------------+                     |
|    |                                                                                  |
|    |-- [ElementInternals] ---> Terhubung ke <form> Parent (Validity, FormData)        |
|    |                                                                                  |
|    |-- [Shadow Root] (#shadow-root (open))                                            |
|        |-- AdoptedStyleSheet: [CSSStyleSheet instance] (Zero Memory Duplication)      |
|        |                                                                              |
|        |-- <div class="field-container">                                              |
|        |     <label for="native-input"><slot name="label"></slot></label>             |
|        |     <input id="native-input" part="native-input" />                          |
|        |     <slot name="helper"></slot> <--- Diproyeksikan dari Light DOM            |
|        |   </div>                                                                     |
+--------+------------------------------------------------------------------------------+
```

#### A. Custom Element Reaction Stack & Microtask Timing
Browser mengeksekusi callback Custom Elements melalui *Reaction Stack* khusus. Ketika sebuah atribut diubah via JavaScript (`element.setAttribute()`), browser segera menempatkan pemanggilan `attributeChangedCallback` ke dalam reaction queue elemen tersebut. Namun, parsing DOM awal oleh browser dapat memicu pemanggilan `attributeChangedCallback` **sebelum** `connectedCallback` selesai atau bahkan sebelum *child nodes* selesai di-parse. Arsitektur produksi harus menggunakan `queueMicrotask()` atau pengecekan `#isMounted` untuk menghindari manipulasi DOM sebelum pohon parser stabil.

#### B. Declarative Shadow DOM (DSD) Architecture
Pada arsitektur SSR konvensional, browser harus mengunduh JavaScript, mengeksekusi `customElements.define()`, dan memanggil `attachShadow()` sebelum Shadow DOM terbentuk. Ini memicu FOUC (*Flash of Unstyled Content*). DSD mengatasi ini dengan memperkenalkan atribut `shadowrootmode="open"` pada tag `<template>` langsung di dalam payload HTML:

```html
<enterprise-card>
  <template shadowrootmode="open">
    <style>:host { display: block; border: 1px solid #ccc; }</style>
    <div class="content"><slot></slot></div>
  </template>
  <p>Data ter-render langsung saat HTML di-parse oleh browser.</p>
</enterprise-card>
```
Saat parser HTML membaca `<template shadowrootmode="open">`, parser internal browser langsung menginstansiasi `ShadowRoot` dan memindahkannya ke host elemen tanpa memerlukan intervensi JavaScript client.

#### C. Form-Associated Custom Elements (FACE) & ElementInternals
Sebelum spesifikasi FACE, input custom tidak dapat berpartisipasi langsung dalam form native `<form>`. Elemen harus membuat elemen `<input type="hidden">` dummy di Light DOM. Dengan menyetel properti statis `static formAssociated = true`, komponen mendapatkan akses ke antarmuka `ElementInternals` via `this.attachInternals()`. Ini memberikan:
- Integrasi otomatis dengan form submission (`internals.setFormValue()`).
- Integrasi Constraint Validation API (`internals.setValidity()`, `internals.checkValidity()`).
- State pseudo-classes native seperti `:valid`, `:invalid`, `:disabled`.
- Semantik aksesibilitas via Accessibility Object Model (AOM) tanpa mengotori markup atribut ARIA.

#### D. Constructable Stylesheets
Menggunakan tag `<style>` di dalam setiap Shadow Root menduplikasi parsing CSS dan konsumsi memori untuk setiap instansiasi komponen. `Constructable Stylesheets` memungkinkan satu instance `CSSStyleSheet` dibuat, di-parse sekali, dan dibagikan ke ribuan Shadow Root via array `shadowRoot.adoptedStyleSheets`:

$$\text{Memory Overhead}_{\text{Native <style>}} = N \times \text{Size}(\text{CSS Text})$$
$$\text{Memory Overhead}_{\text{Constructable}} = \text{Size}(\text{CSS Object}) + (N \times \text{Pointer Size})$$

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan di Skala Enterprise | Apa Fungsinya |
| :--- | :--- | :--- |
| **Form-Associated Custom Elements** | Menghilangkan peretasan *hidden input* yang rapuh dan memungkinkan Web Components berperilaku persis seperti `<input>` native. | Menyediakan jembatan native antara lifecycle form HTML5 dengan Custom Elements melalui objek `ElementInternals`. |
| **Declarative Shadow DOM** | Mengeliminasi FOUC, meningkatkan Core Web Vitals (LCP/CLS), dan mendukung SEO-friendly SSR. | Memungkinkan server mengalirkan Shadow DOM dalam bentuk markup HTML murni tanpa ketergantungan JavaScript untuk render pertama. |
| **Constructable Stylesheets** | Mencegah bottleneck memori ketika puluhan ribu komponen identik (misal: baris data grid) dirender. | Mengizinkan pembagian objek CSS terkompilasi tunggal di berbagai Shadow Root secara reaktif. |
| **`AbortController` Lifecycle** | Mencegah memory leak yang diakibatkan oleh event listener global (`window`, `document`) yang tidak terlepas. | Menyediakan mekanisme pembatalan deterministik untuk semua event listener komponen dalam satu pemanggilan `abort()`. |

---

### 5. How (Workflow Detail)

Alur kerja berikut mendemonstrasikan inisialisasi komponen kelas enterprise, mulai dari pemrosesan SSR (DSD), hidrasi client, manajemen state, hingga pembersihan memori (*cleanup*):

```
[SERVER]
   |
   |-- 1. Serialisasi Komponen: Generate <component><template shadowrootmode="open">...
   v
[NETWORK: HTTP Response Streaming]
   |
   v
[BROWSER ENGINE (HTML Parser)]
   |
   |-- 2. Parsing DSD -> Shadow Root langsung terbentuk & CSS diterapkan (Tanpa FOUC)
   |-- 3. Download & Parse JavaScript Bundle
   |-- 4. customElements.define('my-element', MyElement) dieksekusi
   v
[CUSTOM ELEMENT LIFECYCLE]
   |
   |-- 5. constructor() -> attachInternals(), hubungkan Adopted Stylesheet
   |-- 6. connectedCallback() -> Inisialisasi AbortController, attach Event Listener global
   |-- 7. attributeChangedCallback() -> Eksekusi validasi & pantulkan (reflect) ke property
   |-- 8. ElementInternals.setFormValue() -> Sinkronkan state input ke parent <form>
   v
[DOM DETACHMENT / CLEANUP]
   |
   |-- 9. Elemen dihapus dari DOM -> disconnectedCallback() dipanggil
   |-- 10. AbortController.abort() dipanggil -> Semua listener otomatis hancur (Zero Leak)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kedutaan Besar Berdaulat (Sovereign Embassy)
Bayangkan sebuah halaman web seperti sebuah negara berdaulat (*Host Document*). Web Component konvensional seperti gedung perusahaan lokal; ia tunduk sepenuhnya pada peraturan lokal (CSS global dapat merusak tampilannya, script global dapat mengacak-acak isinya). 

Shadow DOM dengan Form-Associated Element berfungsi seperti **Kedutaan Besar**:
1. **Shadow Root**: Wilayah teritorial tertutup di dalam kedutaan. Aturan hukum (CSS) host tidak dapat menembus temboknya secara sewenang-wenang.
2. **Slots**: Pintu gerbang konsuler tempat dokumen atau delegasi dari negara tuan rumah (*Light DOM*) diizinkan masuk dan ditampilkan di ruangan tertentu (*Slot Projection*).
3. **ElementInternals (Diplomat Resmi)**: Satu-satunya jalur komunikasi resmi antara kedutaan dengan kementerian luar negeri tuan rumah (*Parent `<form>`*). Diplomat mengabarkan apakah kedutaan menyetujui perjanjian (*form validity*) atau membawa berkas resmi (*form data*).

```
Document Context (CSS Global / Script Host)
 +--------------------------------------------------------------------+
 | Host CSS: `div { color: red; }` (TIDAK tembus ke dalam Kedutaan)  |
 |                                                                    |
 |   <custom-embassy>                                                 |
 |     #shadow-root (open)                                            |
 |     +=================== BOUNDARY TEMBOK =======================+  |
 |     |  Constructable StyleSheet: `div { color: blue; }`         |  |
 |     |                                                           |  |
 |     |  <div class="office">                                     |  |
 |     |    <slot name="visitor">                                  |  |
 |     |  </div>        ^                                          |  |
 |     +================|==========================================+  |
 |                      | (Diproyeksikan)                             |
 |       <span slot="visitor">Tamu dari Host</span>                   |
 |                                                                    |
 +--------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Declarative Shadow DOM dengan Hydration Check

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>DSD Minimalis</title>
</head>
<body>
  <!-- Server-rendered Custom Element -->
  <simple-card>
    <template shadowrootmode="open">
      <style>
        :host { display: block; padding: 1rem; border: 1px solid #ddd; border-radius: 8px; font-family: sans-serif; }
        .title { font-weight: bold; color: #2c3e50; }
      </style>
      <div class="title">Kartu Profil (DSD)</div>
      <slot></slot>
    </template>
    <p>Ini adalah konten yang dialirkan dari server melalui Light DOM.</p>
  </simple-card>

  <script>
    class SimpleCard extends HTMLElement {
      constructor() {
        super();
        // Cek apakah shadowRoot sudah di-instansiasi via DSD
        if (!this.shadowRoot) {
          // Fallback untuk browser lawas / client-side rendering murni
          this.attachShadow({ mode: 'open' });
          this.shadowRoot.innerHTML = `
            <style>:host { display: block; border: 1px solid #ddd; }</style>
            <div>Fallback Client Render</div>
            <slot></slot>
          `;
        }
      }

      connectedCallback() {
        console.log('SimpleCard terhidrasi di client.');
      }
    }
    customElements.define('simple-card', SimpleCard);
  </script>
</body>
</html>
```

#### B. Practical Enterprise Example: Production-Ready Form-Associated Input

Implementasi komponen `<enterprise-text-field>` lengkap dengan `ElementInternals`, validasi terintegrasi, CSS Constructable Stylesheets, pembatalan event via `AbortController`, dan reflection attribute-property.

```javascript
// enterprise-text-field.js

// 1. Shared Constructable Stylesheet untuk efisiensi memori
const sheet = new CSSStyleSheet();
sheet.replaceSync(`
  :host {
    display: inline-block;
    font-family: system-ui, -apple-system, sans-serif;
    margin-bottom: 1rem;
    --primary-color: #2563eb;
    --error-color: #dc2626;
    --border-color: #d1d5db;
  }
  :host([disabled]) {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
  }
  .field-wrapper {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  label {
    font-size: 0.875rem;
    font-weight: 600;
    color: #374151;
  }
  input {
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    font-size: 1rem;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  input:focus {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
  }
  :host(:invalid) input {
    border-color: var(--error-color);
  }
  .error-msg {
    font-size: 0.75rem;
    color: var(--error-color);
    min-height: 1rem;
  }
`);

export class EnterpriseTextField extends HTMLElement {
  // Wajib untuk FACE (Form-Associated Custom Elements)
  static formAssociated = true;

  static get observedAttributes() {
    return ['value', 'label', 'placeholder', 'required', 'disabled', 'type'];
  }

  #internals;
  #inputElement;
  #errorElement;
  #abortController;

  constructor() {
    super();
    // 2. Attach Internals untuk integrasi Form
    this.#internals = this.attachInternals();

    // 3. Dukungan Hydration DSD: periksa shadowRoot yang sudah ada
    let root = this.shadowRoot;
    if (!root) {
      root = this.attachShadow({ mode: 'open' });
      root.innerHTML = `
        <div class="field-wrapper">
          <label id="input-label"></label>
          <input id="inner-input" part="input" />
          <span class="error-msg" id="error-display" aria-live="polite"></span>
        </div>
      `;
    }

    // Terapkan Adopted Stylesheet
    root.adoptedStyleSheets = [sheet];

    this.#inputElement = root.getElementById('inner-input');
    this.#errorElement = root.getElementById('error-display');
  }

  // Lifecycle: Tersambung ke DOM
  connectedCallback() {
    this.#abortController = new AbortController();
    const { signal } = this.#abortController;

    // Delegate ID relasi ARIA
    this.shadowRoot.getElementById('input-label').setAttribute('for', 'inner-input');

    // Event Listener Input terisolasi dengan AbortSignal
    this.#inputElement.addEventListener(
      'input',
      (e) => this.#handleInput(e),
      { signal }
    );

    this.#inputElement.addEventListener(
      'blur',
      () => this.#validate(),
      { signal }
    );

    this.#syncInitialProperties();
    this.#validate();
  }

  // Lifecycle: Terlepas dari DOM (Pembersihan Memori Total)
  disconnectedCallback() {
    if (this.#abortController) {
      this.#abortController.abort();
      this.#abortController = null;
    }
  }

  // Lifecycle: Mutasi Atribut
  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue) return;

    switch (name) {
      case 'value':
        this.value = newValue;
        break;
      case 'label':
        this.shadowRoot.getElementById('input-label').textContent = newValue || '';
        break;
      case 'placeholder':
        this.#inputElement.placeholder = newValue || '';
        break;
      case 'required':
        this.#inputElement.required = this.hasAttribute('required');
        this.#validate();
        break;
      case 'disabled':
        this.#inputElement.disabled = this.hasAttribute('disabled');
        break;
      case 'type':
        this.#inputElement.type = newValue || 'text';
        break;
    }
  }

  // Getters & Setters untuk JavaScript Property Reflection
  get value() {
    return this.#inputElement.value;
  }

  set value(val) {
    const stringVal = String(val ?? '');
    this.#inputElement.value = stringVal;
    this.#internals.setFormValue(stringVal);
    this.#validate();
  }

  get name() { return this.getAttribute('name'); }
  get type() { return this.getAttribute('type') || 'text'; }
  get form() { return this.#internals.form; }
  get validity() { return this.#internals.validity; }
  get validationMessage() { return this.#internals.validationMessage; }
  get willValidate() { return this.#internals.willValidate; }

  checkValidity() { return this.#internals.checkValidity(); }
  reportValidity() { return this.#internals.reportValidity(); }

  // Form Reset Callback native FACE
  formResetCallback() {
    this.value = this.getAttribute('value') || '';
    this.#validate();
  }

  // Form Disabled Callback native FACE
  formDisabledCallback(disabled) {
    this.#inputElement.disabled = disabled;
    if (disabled) {
      this.setAttribute('disabled', '');
    } else {
      this.removeAttribute('disabled');
    }
  }

  // Private Handlers
  #handleInput(event) {
    const val = event.target.value;
    this.#internals.setFormValue(val);
    
    // Dispatch Custom Event standar bubbled & composed
    this.dispatchEvent(new CustomEvent('enterprise-change', {
      detail: { value: val },
      bubbles: true,
      composed: true
    }));

    this.#validate();
  }

  #validate() {
    // Sinkronkan validitas native inner-input ke ElementInternals
    const isValid = this.#inputElement.checkValidity();

    if (!isValid) {
      this.#internals.setValidity(
        this.#inputElement.validity,
        this.#inputElement.validationMessage,
        this.#inputElement
      );
      this.#errorElement.textContent = this.#inputElement.validationMessage;
    } else {
      this.#internals.setValidity({});
      this.#errorElement.textContent = '';
    }
  }

  #syncInitialProperties() {
    if (this.hasAttribute('value')) {
      this.value = this.getAttribute('value');
    }
    if (this.hasAttribute('label')) {
      this.shadowRoot.getElementById('input-label').textContent = this.getAttribute('label');
    }
    if (this.hasAttribute('placeholder')) {
      this.#inputElement.placeholder = this.getAttribute('placeholder');
    }
  }
}

// Registrasi Elemen
if (!customElements.get('enterprise-text-field')) {
  customElements.define('enterprise-text-field', EnterpriseTextField);
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Unified Design System di Multi-Brand FinTech
Sebuah konglomerat finansial menaungi empat anak perusahaan dengan stack yang berbeda-beda:
- Entitas A: Menggunakan Next.js (React)
- Entitas B: Menggunakan Nuxt (Vue 3)
- Entitas C: Menggunakan Angular Enterprise
- Entitas D: Portal Agen menggunakan Vanilla HTML/Legacy jQuery

#### Masalah:
Tim mendesain form verifikasi identitas (KYC) yang melibatkan aturan validasi form regulasi ketat (AML/KYC), masking nomor kartu kredit, enkripsi input data sensitif di level client, dan pencegahan inspect DOM inject. Duplikasi komponen form di masing-masing framework menyebabkan inkonsistensi perilaku validasi dan pembengkakan biaya pemeliharaan (*maintenance cost*). Selain itu, Next.js dan Nuxt mengalami isu SSR FOUC yang parah ketika Web Components dihidrasi.

#### Solusi Arsitektur:
1. **Pustaka Inti Komponen Web Components Standar (Zero-Dependency)**: Dibangun menggunakan Custom Elements native + Form-Associated API (`ElementInternals`).
2. **Eliminasi FOUC dengan Declarative Shadow DOM**: Engine SSR (Node.js engine di Next.js dan Nuxt) dikonfigurasi untuk merender tag `<template shadowrootmode="open">` secara langsung. Browser menampilkan styling input dan struktur form sebelum runtime React atau Vue aktif.
3. **Kompatibilitas Form Cross-Framework**: Komponen form-associated dapat diletakkan di dalam tag `<form>` standar. `Formik`, `React Hook Form`, `VeeValidate`, maupun submit form native HTML membaca komponen seperti input biasa tanpa membutuhkan wrapper komponen khusus.

```
                           +----------------------------------------+
                           |  Central Web Components Design System  |
                           |    - ElementInternals (FACE API)       |
                           |    - Constructable Stylesheets         |
                           |    - Declarative Shadow DOM (SSR)      |
                           +----------------------------------------+
                                        |
        +-------------------------------+-------------------------------+
        |                               |                               |
        v                               v                               v
+-------------------+           +-------------------+           +-------------------+
| Next.js App (SSR) |           | Nuxt 3 App (SSR)  |           | Legacy jQuery App |
|   <ds-input />    |           |   <ds-input />    |           |   <ds-input />    |
|   (Direct Form)   |           |   (Direct Form)   |           |   (Direct Form)   |
+-------------------+           +-------------------+           +-------------------+
        |                               |                               |
        +-------------------------------+-------------------------------+
                                        v
                    Native HTML5 Form Payload Submission (Standard)
```

#### Hasil:
- Pengurangan duplikasi kode komponen UI hingga **73%**.
- First Contentful Paint (FCP) pada halaman onboarding KYC membaik dari **2.4 detik** menjadi **0.8 detik** berkat DSD.
- Mengeliminasi 100% bug inkonsistensi validasi form antar platform.

---

### 9. Trade-offs

| Pendekatan / Aspek | Keuntungan (*Pros*) | Kerugian / Biaya (*Cons & Latency*) |
| :--- | :--- | :--- |
| **Shadow DOM (Open)** | Enkapsulasi CSS absolut; tidak ada CSS clash; arsitektur modular terjamin. | Querying DOM dari luar menjadi lebih kompleks; CSS tooling umum (seperti Tailwind Utility murni) sulit menembus batas shadow tanpa `::part` atau CSS Variables. |
| **Declarative Shadow DOM (DSD)** | Eliminasi total FOUC; performa LCP/CLS unggul pada SSR. | Ukuran payload transfer HTML meningkat secara signifikan karena duplikasi markup template pada SSR jika tidak dioptimalkan. |
| **Constructable Stylesheets** | Penggunaan memori minimal (shared instance); update style runtime sangat cepat (C++ engine level). | Membutuhkan polyfill pada runtime browser non-modern lama; tidak dapat memuat file CSS eksternal via `@import` secara sinkron tanpa latency. |
| **ElementInternals (FACE)** | Validasi form standar browser; tidak butuh wrapper atau hidden input hack. | Memerlukan implementasi getter/setter manual untuk setiap properti HTMLInputElement standar (`validity`, `checkValidity`, dll). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Akses Child Nodes atau Parent di dalam `constructor()`
*Penyebab:* Menurut spesifikasi W3C, ketika `constructor()` dieksekusi, atribut dan *children* elemen belum tersedia di DOM tree.
```javascript
// SALAH
class BadComponent extends HTMLElement {
  constructor() {
    super();
    // DOMException: The element to be created already has children!
    this.innerHTML = `<div>Broken</div>`; 
    console.log(this.getAttribute('data-id')); // Mengembalikan null
  }
}

// BENAR
class GoodComponent extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }
  connectedCallback() {
    // Akses atribut atau modifikasi DOM aman di sini
    console.log(this.getAttribute('data-id'));
  }
}
```

#### Kesalahan 2: Memory Leak dari Event Listener Global
*Penyebab:* Menambahkan listener ke `window` atau `document` tanpa menghapusnya di `disconnectedCallback()`.
```javascript
// SALAH
connectedCallback() {
  window.addEventListener('resize', this.handleResize);
}

// BENAR: Menggunakan AbortController
#abortController;
connectedCallback() {
  this.#abortController = new AbortController();
  window.addEventListener('resize', this.handleResize, { 
    signal: this.#abortController.signal 
  });
}
disconnectedCallback() {
  this.#abortController.abort(); // Membersihkan semua listener secara instan
}
```

#### Kesalahan 3: Dual-Attachment Shadow Root pada Hydration DSD
*Penyebab:* Memanggil `this.attachShadow({ mode: 'open' })` secara membabi buta padahal DSD sudah membentuk `shadowRoot`.
```javascript
// SALAH: Crash dengan error "DOMException: Shadow root cannot be created on a host which already hosts a shadow tree."
constructor() {
  super();
  this.attachShadow({ mode: 'open' });
}

// BENAR: Pola Defensive DSD Hydration
constructor() {
  super();
  if (!this.shadowRoot) {
    this.attachShadow({ mode: 'open' });
  }
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan `formAssociated = true`**: Selalu gunakan `ElementInternals` untuk komponen form kustom.
- [ ] **Defensive DSD Initialization**: Selalu periksa keberadaan `this.shadowRoot` di `constructor()` sebelum memanggil `attachShadow()`.
- [ ] **Constructable Stylesheet Sharing**: Jangan pernah mendefinisikan string `<style>` berulang di dalam innerHTML jika komponen dirender berulang (>100 kali). Gunakan `adoptedStyleSheets`.
- [ ] **Lifecycle Unsubscription via `AbortController`**: Pasang sinyal `signal` pada semua event listener yang tidak terikat langsung ke host elemen atau internal shadow root.
- [ ] **Prop-to-Attribute Reflection**: Pastikan setter memanggil `setAttribute()` dan getter membaca `getAttribute()` hanya untuk tipe data primitif (string, boolean, number) guna menjaga reaktivitas inspektur devtools.
- [ ] **Ekspos Styling Hook Terkendali**: Gunakan atribut `part="name"` pada elemen internal kritis agar developer konsumen dapat mengubah styling menggunakan pseudo-element `::part()`.
- [ ] **Pastikan Aksesibilitas (AOM)**: Hubungkan label ke form controls menggunakan internal ID atau properti ARIA `this.#internals.ariaLabel`.

---

### 12. Hands-on Practice

Buatlah implementasi lengkap komponen Switch Toggle Form-Associated di direktori proyek lokal Anda:

#### File: `hands-on/m02/enterprise-toggle.js`
```javascript
const toggleSheet = new CSSStyleSheet();
toggleSheet.replaceSync(`
  :host {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    user-select: none;
    font-family: inherit;
  }
  :host([disabled]) {
    cursor: not-allowed;
    opacity: 0.6;
  }
  .switch {
    position: relative;
    width: 44px;
    height: 24px;
    background-color: #e5e7eb;
    border-radius: 9999px;
    transition: background-color 0.2s ease-in-out;
  }
  :host([checked]) .switch {
    background-color: #10b981;
  }
  .thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 20px;
    height: 20px;
    background-color: white;
    border-radius: 50%;
    transition: transform 0.2s ease-in-out;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  }
  :host([checked]) .thumb {
    transform: translateX(20px);
  }
  :host(:focus-visible) .switch {
    box-shadow: 0 0 0 2px #3b82f6;
  }
`);

export class EnterpriseToggle extends HTMLElement {
  static formAssociated = true;
  static get observedAttributes() { return ['checked', 'disabled', 'value']; }

  #internals;
  #abortController;

  constructor() {
    super();
    this.#internals = this.attachInternals();
    this.#internals.role = 'switch';

    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' });
      this.shadowRoot.innerHTML = `
        <div class="switch" part="track">
          <div class="thumb" part="thumb"></div>
        </div>
        <slot></slot>
      `;
    }
    this.shadowRoot.adoptedStyleSheets = [toggleSheet];
  }

  connectedCallback() {
    this.#abortController = new AbortController();
    const { signal } = this.#abortController;

    if (!this.hasAttribute('tabindex')) {
      this.setAttribute('tabindex', '0');
    }

    this.addEventListener('click', this.#toggle.bind(this), { signal });
    this.addEventListener('keydown', (e) => {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        this.#toggle();
      }
    }, { signal });

    this.#syncState();
  }

  disconnectedCallback() {
    this.#abortController?.abort();
  }

  attributeChangedCallback(name) {
    if (name === 'checked' || name === 'disabled') {
      this.#syncState();
    }
  }

  get checked() { return this.hasAttribute('checked'); }
  set checked(val) {
    if (Boolean(val)) {
      this.setAttribute('checked', '');
    } else {
      this.removeAttribute('checked');
    }
  }

  get disabled() { return this.hasAttribute('disabled'); }
  set disabled(val) {
    if (Boolean(val)) {
      this.setAttribute('disabled', '');
      this.setAttribute('tabindex', '-1');
    } else {
      this.removeAttribute('disabled');
      this.setAttribute('tabindex', '0');
    }
  }

  get value() { return this.getAttribute('value') || 'on'; }
  set value(val) { this.setAttribute('value', val); }

  #toggle() {
    if (this.disabled) return;
    this.checked = !this.checked;
    this.dispatchEvent(new Event('change', { bubbles: true }));
  }

  #syncState() {
    this.#internals.ariaChecked = this.checked ? 'true' : 'false';
    this.#internals.ariaDisabled = this.disabled ? 'true' : 'false';
    this.#internals.setFormValue(this.checked ? this.value : null);
  }

  formResetCallback() {
    this.checked = this.hasAttribute('defaultchecked');
  }
}

customElements.define('enterprise-toggle', EnterpriseToggle);
```

#### File: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Hands-on Web Components Production</title>
</head>
<body style="font-family: sans-serif; padding: 2rem;">
  <h2>Uji Coba Form Integration</h2>
  
  <form id="test-form">
    <enterprise-toggle name="subscribe_newsletter" value="yes" checked>
      Terima Newsletter Mingguan
    </enterprise-toggle>
    <br><br>
    <button type="submit">Submit Form</button>
    <button type="reset">Reset Form</button>
  </form>

  <div id="output" style="margin-top: 1rem; background: #f3f4f6; padding: 1rem; font-family: monospace;"></div>

  <script type="module">
    import './enterprise-toggle.js';

    const form = document.getElementById('test-form');
    const output = document.getElementById('output');

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const formData = new FormData(form);
      const entries = Object.fromEntries(formData.entries());
      output.textContent = 'FormData Output: ' + JSON.stringify(entries, null, 2);
    });

    form.addEventListener('reset', () => {
      output.textContent = 'Form direset ke kondisi awal.';
    });
  </script>
</body>
</html>
```

---

### 13. Exercise

#### Level Easy
1. Modifikasi komponen `EnterpriseToggle` di hands-on agar menerima atribut `size="small" | "medium" | "large"` dan implementasikan perubahannya via CSS Custom Properties.

#### Level Medium
1. Buat Custom Element `<password-field>` berbasis `EnterpriseTextField` yang memiliki tombol enkapsulasi internal Shadow DOM untuk *toggle visibility* (show/hide password).
2. Terapkan validasi native regex minimal: 8 karakter, 1 huruf besar, 1 angka menggunakan `internals.setValidity()`. Tampilkan pesan error saat input ditinggalkan (*blur*).

#### Level Hard
1. Buat Custom Element `<data-grid>` yang merender 10.000 data baris (simulasi virtual DOM atau recycling row) dengan kriteria:
   - Gunakan `Constructable Stylesheets` bersama.
   - Dukung DSD (Declarative Shadow DOM) untuk 20 data pertama saat SSR.
   - Tidak boleh ada kebocoran memori saat data grid di-remove dan di-append kembali ke document body secara dinamis sebanyak 50 kali berulang.

---

### 14. Challenge

**Studi Kasus Arsitektur Tanpa Framework:**
Rancang sebuah micro-frontend modal layer berbasis Web Components: `<enterprise-modal>`.
1. Komponen harus menggunakan `<dialog>` native di dalam Shadow Root-nya namun mengekspos slot untuk `header`, `body`, dan `actions`.
2. Jika browser melakukan request SSR, modal harus bisa menampilkan initial layout menggunakan Declarative Shadow DOM.
3. Saat dibuka (`showModal()`), elemen harus menangani *Focus Trap* secara mandiri dan mengembalikan fokus ke tombol pemanggil saat ditutup (baik via tombol Escape, click overlay, maupun programmatic call).
4. Sediakan *theming contract* yang ketat menggunakan CSS custom properties dan CSS `::part()` sehingga aplikasi host dari framework mana pun dapat mengontrol radius sudut, backdrop blur, dan elevasi bayangan tanpa merusak aksesibilitas `aria-modal`.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Apa tujuan utama dari spesifikasi Declarative Shadow DOM (DSD)?**
   - A. Menghapus kebutuhan CSS di Web Components.
   - B. Memungkinkan browser merender Shadow DOM langsung dari server tanpa JavaScript untuk mencegah FOUC.
   - C. Menggantikan pustaka React dan Vue secara global.
   - D. Menjadikan semua variabel CSS private.

2. **Atribut apa yang harus ada pada elemen `<template>` untuk mengaktifkan DSD?**
   - A. `dsd="true"`
   - B. `shadowroot="open"`
   - C. `shadowrootmode="open"`
   - D. `declarative="shadow"`

3. **Bagian manakah dari lifecycle Custom Elements yang pertama kali dijalankan saat elemen ditambahkan ke DOM dokumen?**
   - A. `constructor()`
   - B. `connectedCallback()`
   - C. `attributeChangedCallback()`
   - D. `adoptedCallback()`

4. **Apa fungsi dari array statis `observedAttributes`?**
   - A. Mendaftarkan atribut yang jika berubah nilainya akan memicu pemanggilan `attributeChangedCallback`.
   - B. Membuat atribut otomatis berubah menjadi huruf kapital.
   - C. Mengonversi tipe data atribut menjadi JSON.
   - D. Mengunci atribut agar nilainya tidak bisa dimanipulasi dari DevTools.

5. **Apa keuntungan performa menggunakan `Constructable Stylesheets` dibandingkan menyisipkan string `<style>` berulang di setiap Shadow Root?**
   - A. File CSS langsung dienkripsi.
   - B. Parsing CSS hanya dilakukan satu kali dan instance memori yang sama dibagikan ke semua instance komponen.
   - C. Tidak memerlukan browser engine rendering.
   - D. Otomatis mengubah CSS biasa menjadi SASS.

#### Intermediate (5 Soal)
6. **Kapan `adoptedCallback()` dieksekusi pada Custom Element?**
   - A. Ketika elemen diadopsi oleh framework lain.
   - B. Ketika elemen dipindahkan ke dalam dokumen atau iframe yang berbeda menggunakan `document.adoptNode()`.
   - C. Ketika ada slot yang berubah isinya.
   - D. Ketika komponen mewarisi class dari komponen lain.

7. **Pada Form-Associated Custom Elements, properti statis apa yang WAJIB dideklarasikan bernilai `true` agar komponen terdaftar sebagai form control resmi?**
   - A. `static isForm = true;`
   - B. `static formAssociated = true;`
   - C. `static enableInternals = true;`
   - D. `static formControl = true;`

8. **Bagaimana cara yang paling benar untuk mencegah memory leak dari event listener dokumen global di dalam Custom Component?**
   - A. Tidak pernah menggunakan event listener global.
   - B. Memanggil `window.removeEventListener()` di `connectedCallback()`.
   - C. Menggunakan `AbortController` dan menyuplai `signal`-nya ke setiap listener, lalu mengeksekusi `controller.abort()` di `disconnectedCallback()`.
   - D. Menyetel elemen ke `display: none`.

9. **Jika sebuah selector di host document menulis `enterprise-input::part(input) { color: red; }`, elemen internal Shadow Root mana yang akan terpengaruh?**
   - A. Semua elemen `<input>` di dalam Shadow Root.
   - B. Elemen internal yang memiliki atribut `part="input"`.
   - C. Elemen yang memiliki class `.input`.
   - D. Elemen di dalam `<slot name="input">`.

10. **Apa yang terjadi jika Anda memanggil `this.attachShadow({ mode: 'open' })` pada komponen yang telah di-render via Declarative Shadow DOM di server?**
    - A. Shadow root akan otomatis ter-overwrite tanpa kendala.
    - B. Browser melemparkan `DOMException` karena host telah memiliki shadow root.
    - C. DSD akan di-refresh dari awal.
    - D. Halaman web memuat ulang (*reload*).

#### Kasus Skenario Produksi (3 Soal)
11. **Skenario 1**: Sebuah tim membangun Design System dengan Web Components. Pengguna mengeluhkan bahwa saat mereka menekan tombol *Reset* pada form HTML native (`<button type="reset">`), nilai komponen kustom mereka tidak kembali ke nilai awal. Apa API internal yang terlewat untuk diimplementasikan oleh tim tersebut?
    - A. `disconnectedCallback`
    - B. `formResetCallback()` pada implementasi Form-Associated Custom Elements.
    - C. `attributeChangedCallback` untuk atribut `value`.
    - D. `shadowRoot.reset()`

12. **Skenario 2**: Anda melihat lonjakan alokasi memori yang masif saat aplikasi Single Page Application (SPA) memuat tabel dengan 50.000 data baris yang masing-masing menggunakan Web Component. Setelah profiling heap snapshot, ditemukan 50.000 objek CSSStyleSheet identik dialokasikan. Solusi arsitektural apa yang harus diterapkan?
    - A. Mengganti Shadow DOM menjadi Light DOM murni.
    - B. Menghapus semua CSS dari komponen dan memindahkannya ke inline-style atribut `style=""`.
    - C. Menginstansiasi satu `CSSStyleSheet` tunggal di luar class komponen dan memasukkannya ke array `this.shadowRoot.adoptedStyleSheets` setiap instans.
    - D. Mengubah mode shadow root dari `'open'` menjadi `'closed'`.

13. **Skenario 3**: Sebuah aplikasi e-commerce menggunakan Declarative Shadow DOM untuk komponen keranjang belanja di SSR. Namun, begitu bundle JavaScript dimuat, UI berkedip dan event klik pada tombol checkout berhenti berfungsi. Di console muncul warning *customElements definition failed*. Kemungkinan besar penyebab akar masalahnya adalah:
    - A. Server merender DSD dengan `shadowrootmode="closed"`.
    - B. Komponen di JavaScript memanggil `this.attachShadow()` tanpa mengecek `if (!this.shadowRoot)`, sehingga inisialisasi script gagal total (crash) akibat exception runtime.
    - C. Browser tidak mendukung JavaScript modern.
    - D. File CSS Constructable stylesheet corrupt.

---

### Kunci Jawaban Quiz

1. **B** — DSD memungkinkan browser langsung merender Shadow tree dari payload HTML tanpa menunggu unduhan/eksekusi JS.
2. **C** — Standar atribut W3C modern untuk DSD adalah `shadowrootmode="open"` (atau `"closed"`).
3. **A** — `constructor()` adalah fungsi pertama yang dieksekusi oleh JavaScript runtime saat instance class dibuat sebelum dihubungkan ke DOM (`connectedCallback`).
4. **A** — Array `observedAttributes` mendefinisikan whitelist atribut yang dimonitor oleh browser engine.
5. **B** — `Constructable Stylesheets` di-parse satu kali dan memorinya dapat dibagi (*shared*) ke ribuan Shadow Root via `adoptedStyleSheets`.
6. **B** — `adoptedCallback()` terpanggil saat Custom Element dipindahkan ke dokumen berbeda (misalnya via `iframe`).
7. **B** — Properti statis `formAssociated = true` wajib dideklarasikan agar browser mengaktifkan fitur `ElementInternals`.
8. **C** — Menggunakan `AbortController` memastikan pelepasan event listener deterministik dan mencegah kebocoran memori tanpa perlu mendaftar pemanggilan `removeEventListener` satu per satu.
9. **B** — Selektor `::part(x)` hanya menargetkan elemen di dalam shadow tree yang secara eksplisit mengekspos diri melalui atribut `part="x"`.
10. **B** — Browser akan melemparkan exception runtime karena sebuah host DOM tidak boleh memiliki dua Shadow Root bertipe sama.
11. **B** — Spesifikasi Form-Associated Custom Elements menyediakan lifecycle callback native `formResetCallback()` yang dipanggil browser saat form induk di-reset.
12. **C** — Membuat satu instance CSSStyleSheet yang di-share antar instance mencegah instansiasi berulang ratusan ribu node style tree di memori.
13. **B** — Jika constructor langsung mencoba memanggil `attachShadow()` tanpa memeriksa apakah `this.shadowRoot` sudah ada dari parser DSD, engine JavaScript akan melempar exception fatal dan memutus hidrasi interaktivitas komponen.

---

### 16. Summary

Implementasi Web Components tingkat lanjut di lingkungan enterprise bukan sekadar membungkus elemen dengan `attachShadow()`. Arsitektur modern menuntut pemahaman mendalam tentang ekosistem platform web standar:
1. **SSR & Eliminasi FOUC**: Penggunaan **Declarative Shadow DOM (DSD)** memastikan rendering komponen instan sejak transmisi stream HTML pertama dari server ke client.
2. **Efisiensi Memori**: **Constructable Stylesheets** (`adoptedStyleSheets`) menyelesaikan problem memory footprint berlebih pada aplikasi skala besar dengan membagi satu instance parser CSS ke ribuan shadow tree.
3. **Semantik Form Native**: Melalui **Form-Associated Custom Elements (FACE)** dan **ElementInternals**, Custom Components kini menjadi warga kelas satu (*first-class citizens*) dalam ekosistem form HTML5, validasi native, dan AOM (Accessibility Object Model) tanpa ketergantungan framework client apa pun.
4. **Higienitas Memori**: Manajemen lifecycle menggunakan `AbortController` memastikan tidak ada sisa event listener yang menggantung saat komponen di-unmount, menjamin stabilitas performa jangka panjang.